"""Motor de decisión determinista.

Entrada: una secuencia de `Observacion`.
Salida: `ErrorTipificado` o `Silencio`, nunca texto.

Este módulo es el que decide **qué** está mal y **si** hay que decirlo. Es
determinista por construcción: la misma secuencia de observaciones produce
siempre la misma secuencia de decisiones. Ningún modelo generativo participa
aquí (ADR-001, §4.3, compromiso 4).

Orden de evaluación en cada observación:

    1. ¿Es esta medida observable?  (confianza + plano)   -> si no, abstención
    2. ¿Se cumple alguna condición de error?              -> candidatos
    3. ¿Hay evidencia suficiente en el tiempo?            -> bandwidth
    4. ¿Cuál es el error más importante?                  -> UNA prioridad
    5. ¿Toca hablar ahora?                                -> política de silencio

La abstención va **primero** a propósito. En un gimnasio con equipamiento y
oclusión, la pregunta «¿puedo ver esto?» debe resolverse antes que «¿está
mal?»; invertir el orden produce correcciones seguras sobre datos inválidos,
que es el peor fallo posible porque es silencioso.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Union

from ..contrato import (
    ErrorTipificado, Lado, Observacion, Refuerzo, Severidad, Silencio, Plano,
    MOTIVO_CONFIANZA_BAJA, MOTIVO_DESVANECIMIENTO,
    MOTIVO_EVIDENCIA_INSUFICIENTE, MOTIVO_FASE_SILENCIADA,
    MOTIVO_PLANO_NO_OBSERVABLE, MOTIVO_REFRACTARIO, MOTIVO_SIN_ERROR,
)
from .skill import Medida, PoliticaRefuerzo, Regla, Skill

Decision = Union[ErrorTipificado, Refuerzo, Silencio]


# ---------------------------------------------------------------------------
# Acumuladores por repetición
# ---------------------------------------------------------------------------

@dataclass
class _AcumuladorRepeticion:
    """Agregados por repetición (min, max, rango, media) de cada ángulo."""
    valores: Dict[str, List[float]] = field(default_factory=dict)

    def anota(self, nombre: str, valor: float) -> None:
        self.valores.setdefault(nombre, []).append(valor)

    def agregado(self, fn: str, nombre: str) -> Optional[float]:
        vs = self.valores.get(nombre)
        if not vs:
            return None
        if fn == "min":
            return min(vs)
        if fn == "max":
            return max(vs)
        if fn == "rango":
            return max(vs) - min(vs)
        if fn == "media":
            return sum(vs) / len(vs)
        return None


@dataclass
class _EstadoError:
    """Historial de un error concreto dentro de la sesión."""
    repeticiones_consecutivas: int = 0
    ultima_repeticion_vista: Optional[int] = None
    emisiones: int = 0
    t_ultima_emision_ms: Optional[int] = None
    #: última repetición en la que la regla se pudo comprobar, y la anterior
    rep_evaluada: Optional[int] = None
    rep_evaluada_anterior: Optional[int] = None


@dataclass
class _EstadoRefuerzo:
    """Historial de la racha de repeticiones limpias dentro de la sesión."""
    repeticiones_limpias_consecutivas: int = 0
    emisiones: int = 0
    t_ultima_emision_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Observabilidad
# ---------------------------------------------------------------------------

_PLANO_IDEAL_GRADOS = {
    Plano.FRONTAL: 0.0,
    Plano.SAGITAL: 90.0,
}


def plano_observable(regla: Regla, orientacion: Optional[float],
                     tolerancia: float) -> bool:
    """¿Es observable esta regla con la orientación actual del sujeto?

    `orientacion` = 0 significa sujeto de frente, 90 de perfil.
    Si no hay dato de orientación se devuelve True: no se puede abstener por
    algo que no se mide. `[R]` Por eso `orientacion` debería ser obligatorio
    en el contrato de entrada en cuanto percepción pueda entregarlo; sin él,
    esta salvaguarda está desactivada.
    """
    if regla.plano in (Plano.CUALQUIERA, Plano.TRANSVERSAL):
        return True
    if orientacion is None:
        return True
    ideal = _PLANO_IDEAL_GRADOS.get(regla.plano)
    if ideal is None:
        return True
    return abs(orientacion - ideal) <= tolerancia


# ---------------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------------

class MotorDecision:
    """Motor determinista para un `skill`. Una instancia por sesión."""

    def __init__(self, skill: Skill) -> None:
        self.skill = skill
        self.politica = skill.politica
        self.politica_refuerzo = skill.politica_refuerzo
        self._acum = _AcumuladorRepeticion()
        self._repeticion_actual: Optional[int] = None
        self._estado: Dict[str, _EstadoError] = {}
        self._t_ultima_emision_ms: Optional[int] = None
        #: diagnóstico: cuántas veces se abstuvo por cada motivo
        self.contador_abstenciones: Dict[str, int] = {}
        #: estado de la racha de repeticiones limpias (refuerzo positivo)
        self._refuerzo = _EstadoRefuerzo()
        #: reglas aplicables (por fase) y reglas comprobadas en la repetición
        #: en curso: el refuerzo exige que coincidan (ADR-006 §2.9)
        self._rep_aplicables: Set[str] = set()
        self._rep_comprobadas: Set[str] = set()
        #: ¿se disparó algún candidato durante la repetición en curso?
        self._rep_sucia = False
        #: reglas que se dispararon en la repetición en curso (`silenciada_por`)
        self._rep_disparadas: Set[str] = set()
        #: una racha se acaba de cerrar limpia y toca decidir si se habla
        self._racha_cerrada_pendiente = False

    # -- utilidades internas ------------------------------------------------

    def _estado_de(self, error_id: str) -> _EstadoError:
        return self._estado.setdefault(error_id, _EstadoError())

    def _cuenta(self, motivo: str) -> None:
        self.contador_abstenciones[motivo] = (
            self.contador_abstenciones.get(motivo, 0) + 1)

    def _rota_repeticion(self, obs: Observacion) -> None:
        if obs.repeticion != self._repeticion_actual:
            self._cierra_repeticion_anterior()
            self._repeticion_actual = obs.repeticion
            self._acum = _AcumuladorRepeticion()
            self._rep_aplicables = set()
            self._rep_comprobadas = set()
            self._rep_sucia = False
            self._rep_disparadas = set()

    def _cierra_repeticion_anterior(self) -> None:
        """Decide si la repetición que acaba de terminar fue 'limpia'.

        - Si alguna regla detectó un error, la racha se rompe.
        - Solo suma a la racha si **todas** las reglas aplicables en las fases
          que recorrió la repetición se pudieron comprobar al menos una vez, y
          ninguna detectó error. Solo se felicita lo que se ha comprobado.
        - Si alguna regla aplicable no se pudo comprobar (confianza baja o
          plano no observable), la repetición no suma ni rompe: el motor no
          sabe si estuvo bien.

        Antes bastaba con que se comprobara **una** regla, y el sistema
        felicitaba aunque hubiera un error que la cámara no veía (EXP-001 §8.4,
        M8′ = 39,5 %).
        """
        if self._repeticion_actual is None or not self._rep_aplicables:
            return
        if self._rep_sucia:
            self._refuerzo.repeticiones_limpias_consecutivas = 0
        elif self._rep_aplicables <= self._rep_comprobadas:
            self._refuerzo.repeticiones_limpias_consecutivas += 1
            self._racha_cerrada_pendiente = True

    def _anota(self, obs: Observacion) -> None:
        for nombre, valor in obs.angulos.items():
            self._acum.anota(nombre, valor)
        for nombre, valor in obs.distancias.items():
            self._acum.anota(nombre, valor)

    # -- resolución de medidas ---------------------------------------------

    def valor_de_medida(self, medida: Medida, obs: Observacion) -> Optional[float]:
        if medida.tipo == "angulo":
            return obs.angulos.get(medida.nombre)
        if medida.tipo == "distancia":
            return obs.distancias.get(medida.nombre)
        if medida.tipo == "desviacion":
            return obs.desviacion_de(medida.nombre)
        if medida.tipo == "agregado":
            return self._acum.agregado(medida.fn, medida.nombre)
        if medida.tipo == "asimetria":
            a, b = medida.nombres
            va = obs.angulos.get(a, obs.distancias.get(a))
            vb = obs.angulos.get(b, obs.distancias.get(b))
            if va is None or vb is None:
                return None
            return abs(va - vb)
        return None

    def confianza_de_medida(self, medida: Medida, obs: Observacion) -> float:
        implicados = medida.angulos_implicados()
        if not implicados:
            return 0.0
        return min(obs.confianza_de(n) for n in implicados)

    # -- evaluación ---------------------------------------------------------

    def _lado_visible(self, regla: Regla, obs: Observacion) -> bool:
        """¿Es el lado de la regla el que mejor se ve? (`solo_lado_visible`)

        Se compara la confianza de la medida con la de su espejo en el mismo
        frame. Empate => se aplica: de frente se ven los dos lados.
        """
        if not regla.solo_lado_visible:
            return True
        espejo = regla.medida_espejo()
        return obs.confianza_de(regla.medida.nombre) >= obs.confianza_de(espejo)

    def _silenciada(self, regla: Regla) -> bool:
        return any(e in self._rep_disparadas for e in regla.silenciada_por)

    def _aplica(self, regla: Regla, obs: Observacion) -> bool:
        """¿Toca mirar esta regla ahora? Una regla que no aplica no se evalúa,
        no acumula evidencia y no cuenta para el refuerzo: no es una
        abstención, es que no corresponde (otra fase, el lado tapado, o la
        tapa un error de más precedencia)."""
        if regla.fases and obs.fase not in regla.fases:
            return False
        return self._lado_visible(regla, obs) and not self._silenciada(regla)

    def _candidatos(self, obs: Observacion
                    ) -> Tuple[List[Tuple[Regla, float, float]], List[str], List[str]]:
        """Devuelve (candidatos, motivos_de_abstencion, reglas_evaluadas).

        Cada candidato es (regla, valor, confianza); el exceso y la dirección
        se derivan del valor. `reglas_evaluadas` son los `error_id` de las
        reglas que sí se pudieron comprobar: distingue
        «no hay error» de «no pude mirar», que es una distinción que el sistema
        debe poder hacer y reportar.
        """
        candidatos: List[Tuple[Regla, float, float]] = []
        motivos: List[str] = []
        evaluadas: List[str] = []

        for regla in self.skill.reglas:
            if not self._aplica(regla, obs):
                continue

            conf = self.confianza_de_medida(regla.medida, obs)
            if conf < self.politica.confianza_minima:
                motivos.append(MOTIVO_CONFIANZA_BAJA)
                continue

            if not plano_observable(regla, obs.orientacion,
                                    self.politica.tolerancia_orientacion_grados):
                motivos.append(MOTIVO_PLANO_NO_OBSERVABLE)
                continue

            valor = self.valor_de_medida(regla.medida, obs)
            if valor is None:
                motivos.append(MOTIVO_CONFIANZA_BAJA)
                continue

            evaluadas.append(regla.error_id)
            if regla.condicion.evalua(valor):
                candidatos.append((regla, valor, conf))

        return candidatos, motivos, evaluadas

    def _actualiza_evidencia(self, obs: Observacion, disparadas: List[str],
                             evaluadas: List[str]) -> None:
        """Cuenta repeticiones consecutivas con el mismo error.

        Se actualiza una vez por repetición, no una vez por frame: lo que
        importa para el *bandwidth feedback* es la persistencia del error entre
        repeticiones, no su persistencia entre frames contiguos (que es casi
        automática y no es evidencia de nada).

        «Consecutivas» se cuenta entre las repeticiones en las que la regla se
        pudo comprobar. La cadena se rompe si la regla se comprobó en una
        repetición y no tuvo el error; una repetición en la que no se pudo
        mirar (otra fase, confianza baja) no suma ni rompe. Sin esto, en un
        ejercicio alterno las reglas de un lado, que solo se comprueban en las
        repeticiones de esa pierna (1, 3, 5…), no acumulaban evidencia nunca.
        """
        rep = obs.repeticion
        if rep is None:
            for eid in disparadas:
                st = self._estado_de(eid)
                st.repeticiones_consecutivas = max(
                    st.repeticiones_consecutivas,
                    self.politica.repeticiones_evidencia)
            return

        for eid in evaluadas:
            st = self._estado_de(eid)
            if st.rep_evaluada != rep:
                st.rep_evaluada_anterior, st.rep_evaluada = st.rep_evaluada, rep

        for eid in disparadas:
            st = self._estado_de(eid)
            if st.ultima_repeticion_vista == rep:
                continue
            if (st.ultima_repeticion_vista is None
                    or st.rep_evaluada_anterior != st.ultima_repeticion_vista):
                # La cadena se rompió: la última repetición en la que se pudo
                # comprobar la regla no tuvo el error.
                st.repeticiones_consecutivas = 1
            else:
                st.repeticiones_consecutivas += 1
            st.ultima_repeticion_vista = rep

    def _puede_hablar(self, regla: Regla, obs: Observacion) -> Optional[str]:
        """None si se puede hablar; si no, el motivo del silencio."""
        if obs.fase in self.politica.fases_silenciadas:
            return MOTIVO_FASE_SILENCIADA

        st = self._estado_de(regla.error_id)
        if st.repeticiones_consecutivas < self.politica.repeticiones_evidencia:
            return MOTIVO_EVIDENCIA_INSUFICIENTE

        if st.emisiones >= self.politica.max_emisiones_mismo_error:
            return MOTIVO_DESVANECIMIENTO

        if (self._t_ultima_emision_ms is not None
                and obs.t_ms - self._t_ultima_emision_ms < self.politica.refractario_ms):
            return MOTIVO_REFRACTARIO

        if st.t_ultima_emision_ms is not None:
            espera = (self.politica.refractario_mismo_error_ms
                      * (self.politica.factor_desvanecimiento ** (st.emisiones - 1)))
            if obs.t_ms - st.t_ultima_emision_ms < espera:
                return MOTIVO_REFRACTARIO

        return None

    def _revisa_refuerzo_pendiente(self, obs: Observacion) -> Optional[Refuerzo]:
        """Si se acaba de cerrar una racha limpia, decide si corresponde
        emitir un `Refuerzo` ahora. Consume la bandera en cualquier caso:
        una racha que no llega a hablar (p. ej. por refractario) no se
        reintenta frame a frame, solo la próxima vez que se cierre otra
        repetición limpia.
        """
        pr = self.politica_refuerzo
        pendiente = self._racha_cerrada_pendiente
        self._racha_cerrada_pendiente = False

        if not pr.activa or not pendiente:
            return None

        racha = self._refuerzo.repeticiones_limpias_consecutivas
        if racha == 0 or racha % pr.repeticiones_limpias != 0:
            return None
        if self._refuerzo.emisiones >= pr.max_emisiones:
            return None
        if (self._t_ultima_emision_ms is not None
                and obs.t_ms - self._t_ultima_emision_ms < pr.refractario_ms):
            return None
        if (self._refuerzo.t_ultima_emision_ms is not None
                and obs.t_ms - self._refuerzo.t_ultima_emision_ms < pr.refractario_ms):
            return None

        self._refuerzo.emisiones += 1
        self._refuerzo.t_ultima_emision_ms = obs.t_ms
        self._t_ultima_emision_ms = obs.t_ms
        return Refuerzo(
            ejercicio_id=self.skill.skill_id,
            repeticion=obs.repeticion,
            racha=racha,
            t_ms=obs.t_ms,
        )

    # -- API pública --------------------------------------------------------

    def observar(self, obs: Observacion) -> Decision:
        """Procesa una observación y devuelve una decisión."""
        if obs.ejercicio_id != self.skill.skill_id:
            raise ValueError(
                f"observación de '{obs.ejercicio_id}' entregada al motor de "
                f"'{self.skill.skill_id}'")

        self._rota_repeticion(obs)
        self._anota(obs)

        # Si una racha limpia se acaba de cerrar, el refuerzo tiene prioridad
        # sobre la evaluación de errores de este frame: así no queda diluido
        # detrás de una corrección en el mismo instante. El coste es que este
        # frame puntual no se usa para evaluar errores, lo cual es aceptable
        # frente a ~30 frames por repetición.
        refuerzo = self._revisa_refuerzo_pendiente(obs)
        if refuerzo is not None:
            return refuerzo

        candidatos, motivos, evaluadas_ids = self._candidatos(obs)
        # Precedencia: lo que se dispara en este frame ya silencia a las
        # reglas que declaran `silenciada_por`, también en este mismo frame.
        self._rep_disparadas.update(r.error_id for r, _, _ in candidatos)
        candidatos = [c for c in candidatos if not self._silenciada(c[0])]
        evaluadas_ids = [e for e in evaluadas_ids
                         if not self._silenciada(self.skill.regla_de(e))]
        evaluadas = len(evaluadas_ids)
        self._rep_aplicables.update(
            r.error_id for r in self.skill.reglas if self._aplica(r, obs))
        self._rep_comprobadas.update(evaluadas_ids)
        if candidatos:
            self._rep_sucia = True
        self._actualiza_evidencia(obs, [r.error_id for r, _, _ in candidatos],
                                  evaluadas_ids)

        # Las abstenciones se contabilizan siempre, aunque otra regla sí se
        # haya podido evaluar: su frecuencia es la señal de que la cámara está
        # mal colocada o de que hace falta otra vista.
        for m in motivos:
            self._cuenta(m)

        if not candidatos:
            # «Ninguna regla se disparó» solo puede reportarse como ausencia de
            # error si al menos una regla se pudo comprobar. Si no se pudo
            # comprobar ninguna, el sistema no sabe nada y lo dice.
            if evaluadas > 0:
                motivo = MOTIVO_SIN_ERROR
            else:
                motivo = motivos[0] if motivos else MOTIVO_SIN_ERROR
            if motivo == MOTIVO_SIN_ERROR:
                self._cuenta(motivo)
            return Silencio(motivo=motivo, t_ms=obs.t_ms)

        # Una sola prioridad. Desempate determinista: prioridad, luego mayor
        # exceso, luego error_id alfabético.
        candidatos.sort(key=lambda c: (c[0].prioridad,
                                       -c[0].condicion.exceso(c[1]),
                                       c[0].error_id))
        regla, valor, conf = candidatos[0]
        exceso = regla.condicion.exceso(valor)

        motivo = self._puede_hablar(regla, obs)
        if motivo is not None:
            self._cuenta(motivo)
            return Silencio(motivo=motivo, t_ms=obs.t_ms)

        st = self._estado_de(regla.error_id)
        st.emisiones += 1
        st.t_ultima_emision_ms = obs.t_ms
        self._t_ultima_emision_ms = obs.t_ms

        return ErrorTipificado(
            error_id=regla.error_id,
            segmento=regla.segmento,
            lado=regla.lado,
            severidad=Severidad(regla.severidad_de(exceso)),
            fase=obs.fase,
            repeticion=obs.repeticion,
            ejercicio_id=self.skill.skill_id,
            mensaje_id=regla.mensaje_id or regla.error_id,
            magnitud=round(exceso, 3),
            medida=regla.medida.clave(),
            confianza=round(conf, 3),
            direccion=regla.direccion_de(valor),
        )

    def reiniciar(self) -> None:
        """Reinicia el estado de sesión conservando el skill."""
        self._acum = _AcumuladorRepeticion()
        self._repeticion_actual = None
        self._estado.clear()
        self._t_ultima_emision_ms = None
        self.contador_abstenciones.clear()
        self._refuerzo = _EstadoRefuerzo()
        self._rep_aplicables = set()
        self._rep_comprobadas = set()
        self._rep_sucia = False
        self._rep_disparadas = set()
        self._racha_cerrada_pendiente = False


__all__ = ["MotorDecision", "Decision", "plano_observable"]


