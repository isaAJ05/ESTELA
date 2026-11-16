"""Genera un historial de EJEMPLO para probar «Mi progreso» y la entrenadora.

    python scripts/historial_ejemplo.py                       # → datos_locales/historial_ejemplo.jsonl
    python scripts/historial_ejemplo.py --salida otra.jsonl --repartir-dias 14

Lee los resúmenes de `sesiones/*.json` (los que deja `--guardar-metricas`) y
los pasa por `historial.registro_de_sesion`, así que el ejemplo tiene
exactamente los campos que guarda la aplicación (ADR-008): fecha, objetivo,
completadas, duración y avisos dados. Las sesiones en que no se llegó a hacer
nada no generan registro, igual que en la aplicación.

No toca el historial real (`historial/`). La salida por defecto está en
`datos_locales/`, que git ignora.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from estela.aplicacion.historial import registro_de_sesion  # noqa: E402


def generar(sesiones: Path, repartir_dias: int = 0, hoy: datetime | None = None) -> list:
    """Registros de historial, en orden de fecha. Con `repartir_dias` > 0 las
    sesiones se reparten hacia atrás desde `hoy`, una cada dos días como mucho,
    para poder probar rachas y semanas (las fechas dejan de ser las reales)."""
    archivos = sorted(sesiones.glob("*.json"))
    registros = []
    for a in archivos:
        try:
            fecha = datetime.strptime(a.stem, "%Y%m%d-%H%M%S")
            r = registro_de_sesion(json.loads(a.read_text(encoding="utf-8")), fecha)
        except (ValueError, KeyError, TypeError):
            continue
        if r is not None:
            registros.append(r)
    if repartir_dias > 0 and registros:
        hoy = hoy or datetime.now()
        paso = max(1, repartir_dias // len(registros))
        for i, r in enumerate(reversed(registros)):
            hora = datetime.fromisoformat(r["fecha"]).time()
            dia = (hoy - timedelta(days=1 + i * paso)).date()
            r["fecha"] = datetime.combine(dia, hora).isoformat()
        registros.sort(key=lambda r: r["fecha"])
    return registros


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sesiones", type=Path, default=RAIZ / "sesiones")
    p.add_argument("--salida", type=Path,
                   default=RAIZ / "datos_locales" / "historial_ejemplo.jsonl")
    p.add_argument("--repartir-dias", type=int, default=0)
    a = p.parse_args(argv)
    registros = generar(a.sesiones, a.repartir_dias)
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    a.salida.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in registros),
                        encoding="utf-8")
    print(f"{len(registros)} registros de {len(list(a.sesiones.glob('*.json')))} sesiones → {a.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
