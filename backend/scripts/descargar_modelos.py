"""Descarga los modelos locales que ESTELA necesita (una sola vez).

    python scripts/descargar_modelos.py            # pose lite+full y voz es_MX
    python scripts/descargar_modelos.py --heavy    # añade pose heavy
    python scripts/descargar_modelos.py --voz es_ES-davefx-medium

Todo queda en `modelos/` (ignorado por git). Tras la descarga no se
necesita red: la inferencia de pose y la voz son locales.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELOS = RAIZ / "modelos"
URL_POSE = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
            "pose_landmarker_{v}/float16/latest/pose_landmarker_{v}.task")
VOZ_DEFECTO = "es_MX-claude-high"


def descargar(url: str, destino: Path) -> None:
    if destino.exists():
        print(f"ya existe {destino.relative_to(RAIZ)}")
        return
    print(f"descargando {destino.name} ...")
    tmp = destino.with_suffix(destino.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.rename(destino)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--heavy", action="store_true")
    p.add_argument("--voz", default=VOZ_DEFECTO,
                   help=f"voz Piper (defecto {VOZ_DEFECTO})")
    p.add_argument("--sin-voz", action="store_true")
    a = p.parse_args()

    MODELOS.mkdir(exist_ok=True)
    for v in ("lite", "full") + (("heavy",) if a.heavy else ()):
        descargar(URL_POSE.format(v=v), MODELOS / f"pose_landmarker_{v}.task")

    if not a.sin_voz:
        voces = MODELOS / "voces"
        voces.mkdir(exist_ok=True)
        if (voces / f"{a.voz}.onnx").exists():
            print(f"ya existe la voz {a.voz}")
        else:
            r = subprocess.run([sys.executable, "-m", "piper.download_voices",
                                "--download-dir", str(voces), a.voz])
            if r.returncode != 0:
                print("No se pudo descargar la voz (¿está instalado el extra [voz]?)."
                      " ESTELA usará la voz del sistema o solo texto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
