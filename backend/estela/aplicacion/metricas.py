from __future__ import annotations

from typing import Dict, List, Sequence


def percentil(valores: Sequence[float], p: float) -> float:
    """Percentil con interpolación lineal (igual que numpy 'linear')."""
    if not valores:
        return 0.0
    xs = sorted(valores)
    k = (len(xs) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


class Latencias:
    def __init__(self) -> None:
        self._datos: Dict[str, List[float]] = {}

    def anota(self, etapa: str, ms: float) -> None:
        self._datos.setdefault(etapa, []).append(ms)

    def ultimo(self, etapa: str) -> float:
        vs = self._datos.get(etapa)
        return vs[-1] if vs else 0.0

    def valores(self, etapa: str) -> List[float]:
        """Copia de las muestras de una etapa (para el arnés de métricas)."""
        return list(self._datos.get(etapa, ()))

    def resumen(self) -> Dict[str, Dict[str, float]]:
        """Por etapa: n, media, p50, p95 y máximo (ms). La interfaz solo lee
        `n`, `p50_ms` y `p95_ms`; `media_ms` y `max_ms` son para el Informe 2."""
        return {
            etapa: {"n": len(vs), "p50_ms": round(percentil(vs, 50), 3),
                    "p95_ms": round(percentil(vs, 95), 3),
                    "media_ms": round(sum(vs) / len(vs), 3) if vs else 0.0,
                    "max_ms": round(max(vs), 3) if vs else 0.0}
            for etapa, vs in self._datos.items()
        }


__all__ = ["Latencias", "percentil"]
