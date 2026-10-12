"""Alineamiento DTW en línea contra la referencia de un skill."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class ResultadoDTW:
    angulos_ref: Dict[str, float]
    progreso: float
    coste: float


class AlineadorDTW:
    """Alinea el prefijo de la repetición actual con una referencia media."""

    def __init__(self, referencia: Optional[Mapping[str, Any]]) -> None:
        self.referencia = referencia
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
        coste, camino = _dtw(actual, self._media)
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


def _dtw(a: np.ndarray, b: np.ndarray) -> Tuple[float, list[Tuple[int, int]]]:
    n, m = len(a), len(b)
    acumulado = np.full((n + 1, m + 1), np.inf)
    acumulado[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
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


__all__ = ["AlineadorDTW", "ResultadoDTW"]
