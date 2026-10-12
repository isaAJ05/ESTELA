"""Alineamiento DTW en línea contra la referencia de un skill.

Completa la `Observacion` con `angulos_ref`, `progreso` y `coste_dtw` antes
del motor (ADR-004). Vive en `aplicacion` y no en `dominio` porque usa numpy,
y el dominio se limita a la biblioteca estándar (ADR-007).

En cada frame se recalcula el DTW de **todo** el prefijo de la repetición
contra la referencia completa: el coste crece con la longitud del prefijo
(EXP-010 lo mide). `banda` limita el cálculo a una ventana de Sakoe-Chiba;
con `None` (el defecto) el resultado es el del DTW clásico.

`[F]` (medido el 2026-10-12, EXP-010) El camino termina siempre en la última
celda (n, m), así que `progreso` sale 1,0 y `angulos_ref` es el último frame
de la referencia en todos los frames. Hoy no afecta a ninguna decisión porque
ninguna regla usa `desviacion` (EXP-009 §9). `[R]` Un DTW de extremo abierto
(mínimo sobre la última fila) lo resolvería; queda para el equipo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class ResultadoDTW:
    angulos_ref: Dict[str, float]
    progreso: float
    coste: float


class AlineadorDTW:
    """Alinea el prefijo de la repetición actual con una referencia media.

    `banda`: semiancho en frames de la ventana de Sakoe-Chiba, o None para el
    DTW clásico sin restricción.
    """

    def __init__(self, referencia: Optional[Mapping[str, Any]],
                 banda: Optional[int] = None) -> None:
        if banda is not None and banda < 0:
            raise ValueError("la banda DTW no puede ser negativa")
        self.referencia = referencia
        self.banda = banda
        self._repeticion: Optional[int] = None
        self._serie: list[np.ndarray] = []

        self._nombres: Tuple[str, ...] = ()
        self._media = np.empty((0, 0), dtype=float)
        if referencia:
            nombres = tuple(referencia.get("medidas", ()))
            media = referencia.get("angulos", {}).get("media", ())
            if nombres and media:
                matriz = np.asarray(media, dtype=float)
                if matriz.ndim == 2 and matriz.shape[1] == len(nombres):
                    self._nombres = nombres
                    self._media = matriz

    @property
    def disponible(self) -> bool:
        return bool(self._nombres) and len(self._media) > 0

    @property
    def longitud_prefijo(self) -> int:
        """Frames acumulados de la repetición en curso (n del DTW)."""
        return len(self._serie)

    @property
    def longitud_referencia(self) -> int:
        return len(self._media)

    def reiniciar(self) -> None:
        self._repeticion = None
        self._serie.clear()

    def actualizar(self, obs: Any) -> Optional[ResultadoDTW]:
        if not self.disponible:
            return None

        rep = obs.repeticion
        if rep is not None and rep > 0:
            if (self._repeticion is not None and rep != self._repeticion):
                self._serie.clear()
            self._repeticion = rep

        valores = []
        for nombre in self._nombres:
            valor = obs.angulos.get(nombre, obs.distancias.get(nombre, np.nan))
            valores.append(float(valor) if valor is not None else np.nan)
        self._serie.append(np.asarray(valores, dtype=float))
        actual = np.asarray(self._serie, dtype=float)
        coste, camino = _dtw(actual, self._media, self.banda)
        if not camino:
            return None

        limite = _limite_coste(self.referencia or {})
        if limite is not None and coste > limite:
            return None

        i, j = camino[-1]
        referencia = {
            nombre: float(self._media[j, k])
            for k, nombre in enumerate(self._nombres)
            if np.isfinite(self._media[j, k])
        }
        return ResultadoDTW(
            angulos_ref=referencia,
            progreso=j / max(len(self._media) - 1, 1),
            coste=coste,
        )


def _limite_coste(referencia: Mapping[str, Any]) -> Optional[float]:
    dtw = referencia.get("dtw", {})
    for nombre in ("coste_maximo", "umbral_coste", "limite_coste"):
        if dtw.get(nombre) is not None:
            return float(dtw[nombre])
    return None


def ventana_banda(i: int, n: int, m: int, banda: Optional[int]) -> Tuple[int, int]:
    """Columnas [lo, hi] (base 1) que se calculan en la fila i (base 1).

    Sakoe-Chiba sobre la diagonal que une (1, 1) con (n, m), para que las dos
    esquinas queden siempre dentro. `scripts/crear_referencia.py` centra la
    banda en i·m/n; con series de longitud parecida (su caso) es lo mismo.
    Si la pendiente m/n supera 2·banda + 1 las ventanas de dos filas seguidas
    no se tocan y no hay camino: el alineador devuelve None (prefijos muy
    cortos frente a la referencia).
    """
    if banda is None:
        return 1, m
    centro = 1 + (i - 1) * (m - 1) / max(n - 1, 1)
    return max(1, math.ceil(centro - banda)), min(m, math.floor(centro + banda))


def _dtw(a: np.ndarray, b: np.ndarray, banda: Optional[int] = None
         ) -> Tuple[float, list[Tuple[int, int]]]:
    n, m = len(a), len(b)
    acumulado = np.full((n + 1, m + 1), np.inf)
    acumulado[0, 0] = 0.0
    for i in range(1, n + 1):
        lo, hi = ventana_banda(i, n, m, banda)
        for j in range(lo, hi + 1):
            diferencia = np.abs(a[i - 1] - b[j - 1])
            validas = np.isfinite(diferencia)
            if not np.any(validas):
                continue
            coste = float(np.mean(diferencia[validas]))
            acumulado[i, j] = coste + min(
                acumulado[i - 1, j], acumulado[i, j - 1],
                acumulado[i - 1, j - 1],
            )
    if not np.isfinite(acumulado[n, m]):
        return float("inf"), []
    i, j, camino = n, m, []
    while i > 0 and j > 0:
        camino.append((i - 1, j - 1))
        k = int(np.argmin((
            acumulado[i - 1, j - 1], acumulado[i - 1, j],
            acumulado[i, j - 1],
        )))
        i, j = ((i - 1, j - 1), (i - 1, j), (i, j - 1))[k]
    camino.reverse()
    return float(acumulado[n, m] / len(camino)), camino


__all__ = ["AlineadorDTW", "ResultadoDTW", "ventana_banda"]
