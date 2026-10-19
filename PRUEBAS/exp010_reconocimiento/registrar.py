"""EXP-010 · Añadir un vídeo propio al banco.

Desde ESTELA/:

    python PRUEBAS/exp010_reconocimiento/registrar.py --video RUTA.mp4 --clase jumping_jacks --vista frente --consentimiento 2026-10-19
    python PRUEBAS/exp010_reconocimiento/registrar.py --lista

Añade una fila a `registro.csv` (ignorado por git). `extraer.py` y
`reconocer.py` toman esas filas además de los vídeos de docs_estela, con id
`propio_<n>`. El vídeo se queda donde está: debe estar fuera de los
repositorios (Ley 1581/2012, CLAUDE.md §6).
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ESTELA = AQUI.parents[1]
REGISTRO = AQUI / "registro.csv"
CAMPOS = ("id", "ruta", "clase", "lado", "vista", "consentimiento", "notas")
CLASES = ("jumping_jacks", "abduccion", "marcha_rodillas", "plancha", "otro")


def leer() -> list[dict]:
    if not REGISTRO.exists():
        return []
    with REGISTRO.open(encoding="utf-8-sig", newline="") as f:
        return [fila for fila in csv.DictReader(f)
                if fila.get("id") and not fila["id"].startswith("#")]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--video", type=Path)
    p.add_argument("--clase", choices=CLASES, help="lo que se hace de verdad en el vídeo")
    p.add_argument("--lado", default="", choices=("", "izq", "der"), help="solo abducción")
    p.add_argument("--vista", default="", choices=("", "frente", "lado", "diagonal"))
    p.add_argument("--consentimiento", default="",
                   help="fecha del consentimiento informado de la persona grabada")
    p.add_argument("--notas", default="")
    p.add_argument("--lista", action="store_true", help="muestra el registro y sale")
    a = p.parse_args()

    filas = leer()
    if a.lista:
        for f in filas:
            existe = "" if Path(f["ruta"]).exists() else "  (NO EXISTE)"
            print(f"{f['id']:11s} {f['clase']:16s} {f['lado']:4s} {f['vista']:9s} {f['ruta']}{existe}")
        print(f"{len(filas)} vídeos propios")
        return 0

    if not a.video or not a.clase:
        p.error("hacen falta --video y --clase")
    ruta = a.video.resolve()
    if not ruta.is_file():
        p.error(f"no existe {ruta}")
    for repo in (ESTELA, ESTELA.parent / "docs_estela"):
        if ruta.is_relative_to(repo.resolve()):
            p.error(f"el vídeo está dentro de {repo.name}/: muévelo fuera del repositorio")
    if not a.consentimiento:
        p.error("indica --consentimiento (fecha) si la persona grabada dio su consentimiento")
    if any(Path(f["ruta"]).resolve() == ruta for f in filas):
        p.error("ese vídeo ya está registrado")

    n = 1 + max((int(f["id"].split("_")[1]) for f in filas), default=0)
    fila = {"id": f"propio_{n}", "ruta": str(ruta), "clase": a.clase, "lado": a.lado,
            "vista": a.vista, "consentimiento": a.consentimiento, "notas": a.notas}
    nuevo = not REGISTRO.exists()
    with REGISTRO.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if nuevo:
            w.writeheader()
        w.writerow(fila)
    print(f"registrado {fila['id']}: {a.clase} · {ruta.name}")
    print("siguiente: python PRUEBAS/exp010_reconocimiento/extraer.py  y luego  reconocer.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
