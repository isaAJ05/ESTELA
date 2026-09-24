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
from typing import Dict, List, Optional, Tuple, Union

from ..contrato import (
    ErrorTipificado, Lado, Observacion, Severidad, Silencio, Plano,
    MOTIVO_CONFIANZA_BAJA, MOTIVO_DESVANECIMIENTO,
    MOTIVO_EVIDENCIA_INSUFICIENTE, MOTIVO_FASE_SILENCIADA,
    MOTIVO_PLANO_NO_OBSERVABLE, MOTIVO_REFRACTARIO, MOTIVO_SIN_ERROR,
)
from .skill import Medida, Regla, Skill

Decision = Union[ErrorTipificado, Silencio]


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
        self._acum = _AcumuladorRepeticion()
        self._repeticion_actual: Optional[int] = None
        self._estado: Dict[str, _EstadoError] = {}
        self._t_ultima_emision_ms: Optional[int] = None
        #: diagnóstico: cuántas veces se abstuvo por cada motivo
        self.contador_abstenciones: Dict[str, int] = {}

    # -- utilidades internas ------------------------------------------------

    def _estado_de(self, error_id: str) -> _EstadoError:
        return self._estado.setdefault(error_id, _EstadoError())

    def _cuenta(self, motivo: str) -> None:
        self.contador_abstenciones[motivo] = (
            self.contador_abstenciones.get(motivo, 0) + 1)

    def _rota_repeticion(self, obs: Observacion) -> None:
        if obs.repeticion != self._repeticion_actual:
            self._repeticion_actual = obs.repeticion
            self._acum = _AcumuladorRepeticion()

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

    def _candidatos(self, obs: Observacion
                    ) -> Tuple[List[Tuple[Regla, float, float]], List[str], int]:
        """Devuelve (candidatos, motivos_de_abstencion, reglas_evaluadas).

        Cada candidato es (regla, exceso, confianza). `reglas_evaluadas` cuenta
        las reglas que sí se pudieron comprobar: distingue «no hay error» de
        «no pude mirar», que es una distinción que el sistema debe poder hacer
        y reportar.
        """
        candidatos: List[Tuple[Regla, float, float]] = []
        motivos: List[str] = []
        evaluadas = 0

        for regla in self.skill.reglas:
            if regla.fases and obs.fase not in regla.fases:
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

            evaluadas += 1
            if regla.condicion.evalua(valor):
                candidatos.append((regla, regla.condicion.exceso(valor), conf))

        return candidatos, motivos, evaluadas

    def _actualiza_evidencia(self, obs: Observacion,
                             disparadas: List[str]) -> None:
        """Cuenta repeticiones consecutivas con el mismo error.

        Se actualiza una vez por repetición, no una vez por frame: lo que
        importa para el *bandwidth feedback* es la persistencia del error entre
        repeticiones, no su persistencia entre frames contiguos (que es casi
        automática y no es evidencia de nada).
        """
        rep = obs.repeticion
        if rep is None:
            for eid in disparadas:
                st = self._estado_de(eid)
                st.repeticiones_consecutivas = max(
                    st.repeticiones_consecutivas,
                    self.politica.repeticiones_evidencia)
            return

        for eid in disparadas:
            st = self._estado_de(eid)
            if st.ultima_repeticion_vista == rep:
                continue
            if (st.ultima_repeticion_vista is None
                    or rep - st.ultima_repeticion_vista > 1):
                # La cadena se rompió: la repetición anterior no tuvo el error.
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

    # -- API pública --------------------------------------------------------

    def observar(self, obs: Observacion) -> Decision:
        """Procesa una observación y devuelve una decisión."""
        if obs.ejercicio_id != self.skill.skill_id:
            raise ValueError(
                f"observación de '{obs.ejercicio_id}' entregada al motor de "
                f"'{self.skill.skill_id}'")

        self._rota_repeticion(obs)
        self._anota(obs)

        candidatos, motivos, evaluadas = self._candidatos(obs)
        self._actualiza_evidencia(obs, [r.error_id for r, _, _ in candidatos])

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
        candidatos.sort(key=lambda c: (c[0].prioridad, -c[1], c[0].error_id))
        regla, exceso, conf = candidatos[0]

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
        )

    def reiniciar(self) -> None:
        """Reinicia el estado de sesión conservando el skill."""
        self._acum = _AcumuladorRepeticion()
        self._repeticion_actual = None
        self._estado.clear()
        self._t_ultima_emision_ms = None
        self.contador_abstenciones.clear()


__all__ = ["MotorDecision", "Decision", "plano_observable"]
