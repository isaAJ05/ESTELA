"""Genera muestras a ciegas de voces candidatas y mide lo que tarda cada una.

    python scripts/voz/muestras_voces.py --salida DIR --piper actual.onnx otra.onnx \
        --kokoro DIR_MODELOS

Las mismas 10 frases con: la voz Piper actual y otras voces Piper, voces en
español del sistema macOS (`say`) y Kokoro (TTS neuronal). Cada voz recibe una letra
al azar: los audios se llaman `A_01.wav` … y la correspondencia letra → voz
queda en `clave_NO_ABRIR/clave_voces.json`, para oír sin saber cuál es cuál.
`latencia_voces.json` trae el tiempo de síntesis por frase (p50, p95) y el
factor de tiempo real de cada letra; `hoja_voces.csv` es para calificar.

El tiempo es el de tener el audio completo de la frase, que es lo que la
aplicación espera antes de empezar a sonar. En las voces de `say` incluye
arrancar el programa y convertir el archivo.

Licencias `[F]` (fichas de cada modelo, vistas el 2026-11-16): Kokoro-82M
Apache-2.0, con el aviso de su ficha de que fuera del inglés el soporte puede
ser flojo; voces Piper: es_MX-claude apache-2.0, es_MX-ald Unlicense,
es_AR-daniela CC BY-SA 4.0. Las voces de `say` son de Apple y solo sirven en
macOS.

Nadie se graba: todo es síntesis.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

FRASES = [
    "Ahora, plancha. 20 segundos. Colócate de perfil a la cámara.",
    "Ya te veo bien. Empieza cuando quieras.",
    "Sube los brazos por encima de la cabeza.",
    "Baja un poco las caderas, alinea el cuerpo.",
    "Alarga un poco el paso, para bajar con control.",
    "Endereza un poco el tronco, se va hacia la derecha.",
    "Muy bien, terminaste jumping jacks.",
    "Hiciste 6 de 6 repeticiones y recibiste 2 avisos. Te propongo seguir con el siguiente ejercicio.",
    "No te entendí. Repite, por favor.",
    "Rutina terminada. Buen trabajo.",
]


def _guardar(ruta: Path, x: np.ndarray, fs: int) -> None:
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(fs)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def piper(ruta_voz: Path):
    from piper import PiperVoice
    voz = PiperVoice.load(str(ruta_voz))

    def sintetizar(texto):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            voz.synthesize_wav(texto, w)
        buf.seek(0)
        with wave.open(buf) as r:
            return (np.frombuffer(r.readframes(r.getnframes()), np.int16).astype(np.float32) / 32768.0,
                    r.getframerate())
    return sintetizar


def say(nombre: str):
    def sintetizar(texto):
        with tempfile.TemporaryDirectory() as d:
            aiff, wav = Path(d) / "a.aiff", Path(d) / "a.wav"
            subprocess.run(["say", "-v", nombre, "-o", str(aiff), texto], check=True)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@22050", "-c", "1",
                            str(aiff), str(wav)], check=True)
            with wave.open(str(wav)) as r:
                return (np.frombuffer(r.readframes(r.getnframes()), np.int16).astype(np.float32) / 32768.0,
                        r.getframerate())
    return sintetizar


def kokoro(dir_modelos: Path, voz: str):
    from kokoro_onnx import Kokoro
    k = Kokoro(str(dir_modelos / "kokoro-v1.0.onnx"), str(dir_modelos / "voices-v1.0.bin"))

    def sintetizar(texto):
        x, fs = k.create(texto, voice=voz, speed=1.0, lang="es")
        return np.asarray(x, np.float32), int(fs)
    return sintetizar


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--piper", type=Path, nargs="*", default=[],
                   help="archivos .onnx de voces Piper; el primero es la voz actual")
    p.add_argument("--say", default="Paulina,Mónica,Flo (Spanish (Mexico))")
    p.add_argument("--kokoro", type=Path, help="carpeta con kokoro-v1.0.onnx y voices-v1.0.bin")
    p.add_argument("--voces-kokoro", default="ef_dora,em_alex")
    p.add_argument("--semilla", type=int, default=20261116)
    a = p.parse_args(argv)

    candidatas = []                                    # (descripción, licencia, crear)
    licencias_piper = {"es_MX-claude-high": "apache-2.0", "es_MX-ald-medium": "Unlicense",
                       "es_AR-daniela-high": "CC BY-SA 4.0", "es_ES-davefx-medium": "CC0",
                       "es_ES-sharvard-medium": "CC BY 3.0"}
    for k, ruta in enumerate(r for r in a.piper if r.exists()):
        candidatas.append((f"Piper {ruta.stem}" + (" (la actual)" if k == 0 else ""),
                           licencias_piper.get(ruta.stem, "ver la ficha de la voz"),
                           lambda ruta=ruta: piper(ruta)))
    if shutil.which("say") and shutil.which("afconvert"):
        for v in [x for x in a.say.split(",") if x]:
            candidatas.append((f"macOS say · {v}", "voz del sistema de Apple (solo macOS)",
                               lambda v=v: say(v)))
    if a.kokoro and (a.kokoro / "kokoro-v1.0.onnx").exists():
        for v in [x for x in a.voces_kokoro.split(",") if x]:
            candidatas.append((f"Kokoro-82M · {v}", "Apache-2.0", lambda v=v: kokoro(a.kokoro, v)))

    a.salida.mkdir(parents=True, exist_ok=True)
    (a.salida / "clave_NO_ABRIR").mkdir(exist_ok=True)
    letras = [chr(ord("A") + i) for i in range(len(candidatas))]
    random.Random(a.semilla).shuffle(letras)
    clave, latencias = {}, {}
    for letra, (desc, licencia, crear) in zip(letras, candidatas):
        try:
            t0 = time.perf_counter()
            sintetizar = crear()
            sintetizar("Hola.")                            # carga y calentamiento, fuera de la medida
            carga = time.perf_counter() - t0
            ms, rtf = [], []
            for i, frase in enumerate(FRASES, 1):
                t0 = time.perf_counter()
                x, fs = sintetizar(frase)
                dt = time.perf_counter() - t0
                _guardar(a.salida / f"{letra}_{i:02d}.wav", x, fs)
                ms.append(dt * 1000)
                rtf.append(dt / (len(x) / fs))
        except Exception as e:                            # noqa: BLE001
            print(f"NO DISPONIBLE: {desc}: {type(e).__name__}: {str(e)[:200]}")
            clave[letra] = {"voz": desc, "licencia": licencia, "error": f"{type(e).__name__}: {e}"[:300]}
            continue
        clave[letra] = {"voz": desc, "licencia": licencia}
        latencias[letra] = {"carga_s": round(carga, 2), "sintesis_p50_ms": round(float(np.percentile(ms, 50))),
                            "sintesis_p95_ms": round(float(np.percentile(ms, 95))),
                            "sintesis_max_ms": round(max(ms)), "rtf_medio": round(float(np.mean(rtf)), 3)}
        print(f"voz {letra}: lista ({latencias[letra]})", flush=True)
    (a.salida / "clave_NO_ABRIR" / "clave_voces.json").write_text(
        json.dumps(clave, ensure_ascii=False, indent=1), encoding="utf-8")
    (a.salida / "latencia_voces.json").write_text(
        json.dumps(dict(sorted(latencias.items())), ensure_ascii=False, indent=1), encoding="utf-8")
    (a.salida / "frases.txt").write_text(
        "".join(f"{i:02d}  {f}\n" for i, f in enumerate(FRASES, 1)), encoding="utf-8")
    with open(a.salida / "hoja_voces.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["voz", "naturalidad_1a5", "claridad_1a5", "la_usarias_si_o_no", "notas"])
        for letra in sorted(latencias):
            w.writerow([letra, "", "", "", ""])
    print(f"{len(latencias)} voces × {len(FRASES)} frases → {a.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
