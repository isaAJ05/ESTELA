"""Segmentación de fases y conteo de repeticiones, configurada por el skill.

El motor de decisión necesita `Observacion.fase` y `Observacion.repeticion`
(las reglas se filtran por fase y los agregados se acumulan por repetición),
y hasta ahora nada los producía. Este módulo los deriva de una única señal
escalar de la `Observacion`, según la sección opcional `segmentacion` del
skill JSON (ver feedback/skills/ESQUEMA.md). Añadir un ejercicio sigue sin
tocar código.

Dos tipos:

``ciclo``  Una señal que va de un valor de *reposo* a un *extremo* y vuelve
           (rodilla en la sentadilla, hombro en la elevación de brazos,
           separación de pies en jumping jacks). Cuatro fases:
           reposo → ida → extremo → vuelta.

``alternante``  Dos señales, una por lado, cada una con su propio ciclo
           (cadera izquierda y derecha en la marcha). Una repetición es una
           elevación de una pierna.

Decisiones de diseño:

* La repetición empieza al **salir del reposo** (no al volver). Así el
  acumulador del motor (`decision.py:_rota_repeticion`) agrega la
  repetición completa, y las reglas evaluadas en la fase de vuelta
  (p. ej. `profundidad_insuficiente` en `ascenso`) ven el mínimo real.
* Una repetición **incompleta** (no llega al extremo pero se da la vuelta)
  también pasa por la fase de vuelta: sin eso el motor jamás podría decir
  «baja más». Solo cuenta en el contador si alcanzó el extremo.
* Histéresis por umbrales + margen de retorno + media móvil corta, para que
  el ruido del estimador no genere repeticiones fantasma.

`[?]` Los umbrales son provisionales. Se fijaron mirando las señales 3D de un
vídeo por ejercicio de PRUEBAS/DATASET, no con un protocolo de calibración.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Mapping, Optional, Sequence, Tuple, Union

from feedback.contrato import Observacion

REPOSO, IDA, EXTREMO, VUELTA = "reposo", "ida", "extremo", "vuelta"

EVENTO_INICIO = "inicio"
EVENTO_COMPLETA = "completa"
EVENTO_INCOMPLETA = "incompleta"


class SegmentacionInvalida(ValueError):
    pass


# ---------------------------------------------------------------------------
# Lectura de la señal
# ---------------------------------------------------------------------------

def leer_senal(obs: Observacion, rutas: Union[str, Sequence[str]],
               confianza_minima: float) -> Optional[float]:
    """Valor de la primera señal de `rutas` con confianza suficiente.

    Cada ruta es `"angulos.<nombre>"` o `"distancias.<nombre>"`. Se admite una
    lista ordenada de preferencia porque con una cámara de perfil la pierna
    lejana queda ocluida: `rodilla_media` hereda la confianza mínima de los dos
    lados (~0.2–0.4 medido en PRUEBAS/DATASET) y hay que caer al lado visible.

    Devuelve None si ninguna sirve: el segmentador conserva su estado en lugar
    de adivinar.
    """
    for ruta in ([rutas] if isinstance(rutas, str) else rutas):
        grupo, _, nombre = ruta.partition(".")
        fuente = obs.angulos if grupo == "angulos" else obs.distancias
        valor = fuente.get(nombre)
        if valor is not None and obs.confianza_de(nombre) >= confianza_minima:
            return valor
    return None


# ---------------------------------------------------------------------------
# Máquina de un ciclo
# ---------------------------------------------------------------------------

@dataclass
class Ciclo:
    """Máquina de estados de un ciclo reposo → extremo → reposo.

    Trabaja internamente en un eje en el que «hacia el extremo» es creciente,
    de modo que la misma lógica sirve para señales que bajan (rodilla) y que
    suben (separación de pies).
    """
    reposo: float
    extremo: float
    margen_retorno: float
    suavizado: int = 3
    estado: str = REPOSO
    alcanzo_extremo: bool = False
    _pico: float = float("-inf")
    _ventana: Deque[float] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if self.reposo == self.extremo:
            raise SegmentacionInvalida("reposo y extremo no pueden coincidir")
        if self.margen_retorno <= 0:
            raise SegmentacionInvalida("margen_retorno debe ser positivo")
        self._sentido = 1.0 if self.extremo > self.reposo else -1.0
        self._ventana = deque(maxlen=max(1, self.suavizado))

    def paso(self, valor: float) -> Optional[str]:
        self._ventana.append(valor)
        x = self._sentido * (sum(self._ventana) / len(self._ventana))
        r, e = self._sentido * self.reposo, self._sentido * self.extremo

        if self.estado == REPOSO:
            if x > r:
                self.estado, self._pico, self.alcanzo_extremo = IDA, x, False
                if x >= e:
                    self.estado, self.alcanzo_extremo = EXTREMO, True
                return EVENTO_INICIO
            return None

        if x <= r:                                  # volvió al reposo
            completa = self.alcanzo_extremo
            self.estado = REPOSO
            return EVENTO_COMPLETA if completa else EVENTO_INCOMPLETA

        if x > self._pico:
            self._pico = x
            if x >= e:
                self.alcanzo_extremo = True
            if self.estado == VUELTA:       # rebote: vuelve a ir al extremo
                self.estado = EXTREMO if x >= e else IDA
        if self.estado == IDA and x >= e:
            self.estado = EXTREMO
        elif self.estado in (IDA, EXTREMO) and self._pico - x >= self.margen_retorno:
            self.estado = VUELTA
        return None

    def reiniciar(self) -> None:
        self.estado, self.alcanzo_extremo = REPOSO, False
        self._pico = float("-inf")
        self._ventana.clear()


# ---------------------------------------------------------------------------
# Estado público
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EstadoSegmento:
    fase: str
    #: índice de la repetición en curso (0 antes de la primera). Nunca None:
    #: con None el motor asume evidencia suficiente (decision.py:220).
    repeticion: int
    completadas: int
    incompletas: int
    evento: Optional[str] = None
    #: False si en este frame la señal faltaba o no era confiable
    senal_valida: bool = True


class Segmentador:
    """Interfaz común. `actualizar(obs)` se llama una vez por frame."""

    def actualizar(self, obs: Observacion) -> EstadoSegmento:  # pragma: no cover
        raise NotImplementedError

    def reiniciar(self) -> None:  # pragma: no cover
        raise NotImplementedError


class SegmentadorCiclo(Segmentador):
    def __init__(self, senal: Union[str, Sequence[str]], reposo: float, extremo: float,
                 fases: Tuple[str, str, str, str], margen_retorno: float,
                 suavizado: int = 3, confianza_minima: float = 0.5) -> None:
        if len(fases) != 4:
            raise SegmentacionInvalida("un ciclo necesita 4 fases")
        self.senal = senal
        self.confianza_minima = confianza_minima
        self._fases = dict(zip((REPOSO, IDA, EXTREMO, VUELTA), fases))
        self._ciclo = Ciclo(reposo, extremo, margen_retorno, suavizado)
        self._rep = self._completadas = self._incompletas = 0

    def actualizar(self, obs: Observacion) -> EstadoSegmento:
        valor = leer_senal(obs, self.senal, self.confianza_minima)
        evento = None if valor is None else self._ciclo.paso(valor)
        if evento == EVENTO_INICIO:
            self._rep += 1
        elif evento == EVENTO_COMPLETA:
            self._completadas += 1
        elif evento == EVENTO_INCOMPLETA:
            self._incompletas += 1
        return EstadoSegmento(self._fases[self._ciclo.estado], self._rep,
                              self._completadas, self._incompletas, evento,
                              senal_valida=valor is not None)

    def reiniciar(self) -> None:
        self._ciclo.reiniciar()
        self._rep = self._completadas = self._incompletas = 0


class SegmentadorAlternante(Segmentador):
    """Dos ciclos (izquierdo, derecho); solo uno puede estar activo a la vez.

    Fases del skill de marcha: con la pierna izquierda arriba la usuaria está
    en `apoyo_der`, y viceversa. La subida de la pierna se etiqueta como
    `transicion` (fase silenciada): las reglas de altura de rodilla usan el
    mínimo de la repetición y, evaluadas mientras la pierna aún sube, darían
    un falso «rodilla baja».
    """

    def __init__(self, senal_izq: Union[str, Sequence[str]],
                 senal_der: Union[str, Sequence[str]], reposo: float,
                 extremo: float, fase_izq_arriba: str, fase_der_arriba: str,
                 fase_transicion: str, margen_retorno: float,
                 suavizado: int = 3, confianza_minima: float = 0.5) -> None:
        self._senales = {"izq": senal_izq, "der": senal_der}
        self._ciclos = {lado: Ciclo(reposo, extremo, margen_retorno, suavizado)
                        for lado in ("izq", "der")}
        self._fase_arriba = {"izq": fase_izq_arriba, "der": fase_der_arriba}
        self._transicion = fase_transicion
        self.confianza_minima = confianza_minima
        self._activo: Optional[str] = None
        self._rep = self._completadas = self._incompletas = 0

    def actualizar(self, obs: Observacion) -> EstadoSegmento:
        evento_final: Optional[str] = None
        validas = 0
        for lado in ("izq", "der"):
            if self._activo not in (None, lado):
                continue                 # la otra pierna manda hasta que baje
            valor = leer_senal(obs, self._senales[lado], self.confianza_minima)
            if valor is None:
                continue
            validas += 1
            evento = self._ciclos[lado].paso(valor)
            if evento == EVENTO_INICIO:
                self._activo = lado
                self._rep += 1
            elif evento in (EVENTO_COMPLETA, EVENTO_INCOMPLETA):
                self._activo = None
                if evento == EVENTO_COMPLETA:
                    self._completadas += 1
                else:
                    self._incompletas += 1
            if evento is not None:
                evento_final = evento
                break

        fase = self._transicion
        if self._activo is not None:
            ciclo = self._ciclos[self._activo]
            if ciclo.estado in (EXTREMO, VUELTA):
                fase = self._fase_arriba[self._activo]
        return EstadoSegmento(fase, self._rep, self._completadas,
                              self._incompletas, evento_final,
                              senal_valida=validas > 0)

    def reiniciar(self) -> None:
        for c in self._ciclos.values():
            c.reiniciar()
        self._activo = None
        self._rep = self._completadas = self._incompletas = 0


# ---------------------------------------------------------------------------
# Construcción desde el JSON del skill
# ---------------------------------------------------------------------------

def _num(d: Mapping[str, Any], campo: str) -> float:
    if campo not in d:
        raise SegmentacionInvalida(f"segmentacion sin campo '{campo}'")
    return float(d[campo])


def segmentador_desde_dict(d: Mapping[str, Any],
                           fases_skill: Tuple[str, ...] = ()) -> Segmentador:
    tipo = d.get("tipo")
    comunes: Dict[str, Any] = dict(
        reposo=_num(d, "reposo"), extremo=_num(d, "extremo"),
        margen_retorno=_num(d, "margen_retorno"),
        suavizado=int(d.get("suavizado", 3)),
        confianza_minima=float(d.get("confianza_minima", 0.5)),
    )
    if tipo == "ciclo":
        fases = tuple(d.get("fases", ()))
        _valida_fases(fases, fases_skill)
        return SegmentadorCiclo(senal=d["senal"], fases=fases, **comunes)
    if tipo == "alternante":
        fases = (d.get("fase_izq_arriba"), d.get("fase_der_arriba"),
                 d.get("fase_transicion"))
        _valida_fases(fases, fases_skill)
        return SegmentadorAlternante(
            senal_izq=d["senal_izq"], senal_der=d["senal_der"],
            fase_izq_arriba=fases[0], fase_der_arriba=fases[1],
            fase_transicion=fases[2], **comunes)
    raise SegmentacionInvalida(f"tipo de segmentacion desconocido: {tipo}")


def _valida_fases(fases: Tuple[Any, ...], fases_skill: Tuple[str, ...]) -> None:
    if any(not f for f in fases):
        raise SegmentacionInvalida("faltan nombres de fase")
    if fases_skill:
        ajenas = [f for f in fases if f not in fases_skill]
        if ajenas:
            raise SegmentacionInvalida(
                f"fases {ajenas} no declaradas en el skill {list(fases_skill)}")


__all__ = [
    "Ciclo", "EstadoSegmento", "Segmentador", "SegmentadorCiclo",
    "SegmentadorAlternante", "SegmentacionInvalida", "segmentador_desde_dict",
    "leer_senal", "EVENTO_INICIO", "EVENTO_COMPLETA", "EVENTO_INCOMPLETA",
]
