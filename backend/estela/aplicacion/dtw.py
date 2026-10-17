"""Alineamiento DTW en línea contra la referencia de un skill (ADR-004 §2.3).

Completa la `Observacion` con `angulos_ref`, `progreso` y `coste_dtw` antes
del motor. Vive en `aplicacion` y no en `dominio` porque usa numpy, y el
dominio se limita a la biblioteca estándar (ADR-007).

DTW incremental de final abierto, reiniciado en cada repetición:

* Solo se guarda la última columna de la matriz de coste acumulado: una celda
  por frame de la referencia (m = 11–62 en las referencias actuales). Cada
  frame nuevo la actualiza en O(m), así que el coste por frame no crece con lo
  que dure la repetición. La versión anterior recalculaba la repetición
  entera en cada frame, O(n·m), y en sesiones reales llegó a un p95 de 240 ms
  por frame (EXP-006).
* Pasos simétricos (diagonal, vertical, horizontal) y coste local = media de
  |medida − referencia| sobre las medidas válidas, igual que
  `scripts/crear_referencia.py`. Así `coste_dtw` se mide igual que el
  `coste_medoide_a_resto` de la referencia.
* Final abierto: el instante de la referencia alineado con el frame actual es
  el mínimo de la columna. `coste_dtw` = coste acumulado hasta ese instante /
  longitud del camino.
* Las medidas con confianza < `CONFIANZA_MINIMA` se excluyen del vector y
  nunca se rellenan. Un frame sin ninguna medida válida no mueve el
  alineamiento.
* Banda Sakoe-Chiba opcional (`dtw.banda` de `referencia.json`, en frames de
  la referencia) alrededor del instante que tocaría al ritmo de la
  referencia.
* Sin repetición en curso (`repeticion` 0 o None) no se alinea.

Cuando no puede alinear devuelve None y anota el motivo en `motivos`. El motor
se abstiene entonces en las reglas `desviacion` (`MOTIVO_DTW_NO_DISPONIBLE`).

`[F]` Limitación medida en EXP-006 §2.4: si la medida desviada es la que guía
el alineamiento (`hombro_medio` en jumping jacks, la abducción en abducción),
el DTW la «absorbe» deformando el tiempo. De un +20° llega el 10–30 % a la
desviación; en tronco, pelvis y codos llega entero. `[R]` La amplitud del
movimiento principal se juzga mejor con agregados por repetición, y
`desviacion`, con las medidas que no guían el alineamiento.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np

#: la misma confianza mínima con la que `scripts/crear_referencia.py` guarda
#: las medidas de la referencia (por debajo, `null`)
CONFIANZA_MINIMA = 0.5

#: resultado de cada `actualizar`, contado en `AlineadorDTW.motivos`
ALINEADO = "alineado"
SIN_REFERENCIA = "sin_referencia"    # sin referencia cíclica (p. ej. plancha)
SIN_REPETICION = "sin_repeticion"    # aún no ha empezado ninguna repetición
SIN_MEDIDAS = "sin_medidas"          # ninguna medida con confianza suficiente
SIN_CAMINO = "sin_camino"            # ninguna celda alcanzable (fuera de la banda)
COSTE_ALTO = "coste_alto"            # coste por encima de `dtw.coste_maximo`

_INF = math.inf


@dataclass(frozen=True)
class ResultadoDTW:
    angulos_ref: Dict[str, float]
    progreso: float
    coste: float
    #: frame de la referencia alineado con el frame actual
    indice: int


class AlineadorDTW:
    """Alinea la repetición en curso con la referencia media, frame a frame."""

    def __init__(self, referencia: Optional[Mapping[str, Any]],
                 confianza_minima: float = CONFIANZA_MINIMA) -> None:
        self.referencia = referencia
        self.confianza_minima = confianza_minima
        #: cuántos frames acabaron en cada resultado (`ALINEADO`, `SIN_*`...)
        self.motivos: Dict[str, int] = {}

        ref = referencia or {}
        self._nombres: Tuple[str, ...] = ()
        self._media = np.empty((0, 0), dtype=float)
        nombres = tuple(ref.get("medidas", ()))
        media = (ref.get("angulos") or {}).get("media", ())
        if nombres and media:
            matriz = np.asarray(media, dtype=float)      # null -> nan
            if matriz.ndim == 2 and matriz.shape[1] == len(nombres):
                self._nombres, self._media = nombres, matriz

        dtw = ref.get("dtw") or {}
        self.banda: Optional[int] = (int(dtw["banda"]) if dtw.get("banda") is not None
                                     else None)
        self.coste_maximo: Optional[float] = (float(dtw["coste_maximo"])
                                              if dtw.get("coste_maximo") is not None
                                              else None)
        self.fps: Optional[float] = ref.get("fps")
        self.reiniciar()

    @property
    def disponible(self) -> bool:
        return bool(self._nombres) and len(self._media) > 0

    def reiniciar(self) -> None:
        self._repeticion: Optional[int] = None
        self._t0_ms = 0
        #: última columna: coste acumulado y longitud del camino por frame de
        #: la referencia (None antes del primer frame de la repetición)
        self._acumulado: Optional[List[float]] = None
        self._longitud: List[int] = []

    def actualizar(self, obs: Any) -> Optional[ResultadoDTW]:
        resultado, motivo = self._alinear(obs)
        self.motivos[motivo] = self.motivos.get(motivo, 0) + 1
        return resultado

    # -- internos -------------------------------------------------------------

    def _alinear(self, obs: Any) -> Tuple[Optional[ResultadoDTW], str]:
        if not self.disponible:
            return None, SIN_REFERENCIA
        if not obs.repeticion:
            self.reiniciar()
            return None, SIN_REPETICION
        if obs.repeticion != self._repeticion:
            self.reiniciar()
            self._repeticion, self._t0_ms = obs.repeticion, obs.t_ms

        valores = self._vector(obs)
        if not np.isfinite(valores).any():
            return None, SIN_MEDIDAS
        columna = self._columna(self._coste_local(valores), obs.t_ms)
        if columna is None:
            return None, SIN_CAMINO
        self._acumulado, self._longitud, j = columna

        coste = self._acumulado[j] / self._longitud[j]
        if self.coste_maximo is not None and coste > self.coste_maximo:
            return None, COSTE_ALTO
        return ResultadoDTW(
            angulos_ref={nombre: float(v) for nombre, v in zip(self._nombres, self._media[j])
                         if np.isfinite(v)},
            progreso=j / max(len(self._media) - 1, 1),
            coste=coste,
            indice=j,
        ), ALINEADO

    def _vector(self, obs: Any) -> np.ndarray:
        valores = np.full(len(self._nombres), np.nan)
        for k, nombre in enumerate(self._nombres):
            v = obs.angulos.get(nombre, obs.distancias.get(nombre))
            if v is not None and obs.confianza_de(nombre) >= self.confianza_minima:
                valores[k] = v
        return valores

    def _coste_local(self, valores: np.ndarray) -> List[float]:
        """Media de |valor − referencia| sobre las medidas válidas, por frame
        de la referencia; inf si no queda ninguna medida comparable."""
        diferencia = np.abs(self._media - valores)
        validas = np.isfinite(diferencia)
        n = validas.sum(axis=1)
        suma = np.where(validas, diferencia, 0.0).sum(axis=1)
        return np.where(n > 0, suma / np.maximum(n, 1), _INF).tolist()

    def _limites(self, t_ms: int, m: int) -> Tuple[int, int]:
        """Frames de la referencia alcanzables: todos, o la banda alrededor
        del instante que tocaría al ritmo de la referencia."""
        if self.banda is None or not self.fps:
            return 0, m - 1
        centro = min((t_ms - self._t0_ms) * self.fps / 1000.0, m - 1)
        return (max(0, math.floor(centro - self.banda)),
                min(m - 1, math.ceil(centro + self.banda)))

    def _columna(self, local: List[float], t_ms: int
                 ) -> Optional[Tuple[List[float], List[int], int]]:
        """Columna nueva a partir de la anterior, en O(m).

        Devuelve (coste acumulado, longitud del camino, frame de coste mínimo),
        o None si ninguna celda es alcanzable. Los predecesores se desempatan
        como en `crear_referencia.dtw` (diagonal, vertical, horizontal), así
        que coste y camino coinciden con recalcular la repetición entera.
        """
        m = len(local)
        lo, hi = self._limites(t_ms, m)
        acumulado, longitud = [_INF] * m, [0] * m
        previo, largo_previo = self._acumulado, self._longitud
        minimo: Optional[int] = None
        for j in range(lo, hi + 1):
            c = local[j]
            if c == _INF:
                continue
            if previo is None:              # primer frame: el camino sale de (0, 0)
                diagonal, l_diagonal = (0.0 if j == 0 else _INF), 0
                vertical, l_vertical = _INF, 0
            else:
                diagonal, l_diagonal = ((previo[j - 1], largo_previo[j - 1]) if j
                                        else (_INF, 0))
                vertical, l_vertical = previo[j], largo_previo[j]
            horizontal, l_horizontal = (acumulado[j - 1], longitud[j - 1]) if j else (_INF, 0)
            if diagonal <= vertical and diagonal <= horizontal:
                base, largo = diagonal, l_diagonal
            elif vertical <= horizontal:
                base, largo = vertical, l_vertical
            else:
                base, largo = horizontal, l_horizontal
            if base == _INF:
                continue
            acumulado[j], longitud[j] = c + base, largo + 1
            if minimo is None or acumulado[j] < acumulado[minimo]:
                minimo = j
        if minimo is None:
            return None
        return acumulado, longitud, minimo


__all__ = ["AlineadorDTW", "ResultadoDTW", "CONFIANZA_MINIMA", "ALINEADO",
           "SIN_REFERENCIA", "SIN_REPETICION", "SIN_MEDIDAS", "SIN_CAMINO",
           "COSTE_ALTO"]
