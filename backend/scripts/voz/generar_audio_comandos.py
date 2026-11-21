"""Genera audio sintético de órdenes de voz para probar el reconocimiento.

    python scripts/voz/generar_audio_comandos.py --salida DIR

Nadie se graba: las frases se sintetizan con Piper (la voz de ESTELA) y, en
macOS, con las voces del sistema (`say`). Cada frase sale limpia y con ruido
blanco añadido (relación señal-ruido de 15 dB), a 16 kHz mono, con medio
segundo de silencio antes y después. Además un clip de silencio y otro de solo
ruido. `clave.json` dice qué orden se espera de cada archivo.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ))

FS = 16000
#: (frase, orden esperada o None, tipo)
FRASES = [
    ("Pausa.", "pausa", "orden"), ("Seguir.", "seguir", "orden"),
    ("Siguiente.", "siguiente", "orden"),
    ("Terminar.", "terminar", "orden"), ("¿Cómo voy?", "como_voy", "orden"),
    ("Estela, pausa por favor.", "pausa", "orden_en_frase"),
    ("Sigue, por favor.", "seguir", "orden_en_frase"),
    ("Vamos con el siguiente.", "siguiente", "orden_en_frase"),
    ("Quiero terminar.", "terminar", "orden_en_frase"),
    ("¿Cómo vamos?", "como_voy", "orden_en_frase"),
    ("Hola, buenos días.", None, "sin_orden"), ("Qué calor hace hoy.", None, "sin_orden"),
    ("Me duele la rodilla.", None, "dolor"), ("Pausa o siguiente.", None, "ambigua"),
]


def _a_16k(datos: np.ndarray, fs: int) -> np.ndarray:
    if fs == FS:
        return datos
    n = int(round(len(datos) * FS / fs))
    return np.interp(np.linspace(0, len(datos) - 1, n), np.arange(len(datos)), datos)


def _leer_wav(ruta_o_bytes) -> np.ndarray:
    with wave.open(ruta_o_bytes) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        if w.getnchannels() > 1:
            x = x.reshape(-1, w.getnchannels()).mean(axis=1)
        return _a_16k(x, w.getframerate()).astype(np.float32)


def con_piper(textos):
    from estela import config
    from estela.adaptadores.voz.motores import buscar_voz_piper
    from piper import PiperVoice
    ruta = buscar_voz_piper(config.VOCES)
    if ruta is None:
        return None, {}
    voz = PiperVoice.load(str(ruta))
    sal = {}
    for t in textos:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            voz.synthesize_wav(t, w)
        buf.seek(0)
        sal[t] = _leer_wav(buf)
    return f"piper:{ruta.stem}", sal


def con_say(voz, textos):
    if shutil.which("say") is None or shutil.which("afconvert") is None:
        return {}
    sal = {}
    with tempfile.TemporaryDirectory() as d:
        for i, t in enumerate(textos):
            aiff, wav = Path(d) / f"{i}.aiff", Path(d) / f"{i}.wav"
            if subprocess.run(["say", "-v", voz, "-o", str(aiff), t]).returncode != 0:
                return {}
            subprocess.run(["afconvert", "-f", "WAVE", "-d", f"LEI16@{FS}", "-c", "1",
                            str(aiff), str(wav)], check=True)
            sal[t] = _leer_wav(str(wav))
    return sal


def _guardar(ruta: Path, x: np.ndarray) -> None:
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(FS)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--voces-say", default="Paulina,Mónica")
    p.add_argument("--snr-db", type=float, default=15.0)
    a = p.parse_args(argv)
    a.salida.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    textos = [f for f, _, _ in FRASES]
    fuentes = {}
    nombre, audios = con_piper(textos)
    if audios:
        fuentes[nombre] = audios
    for v in [x for x in a.voces_say.split(",") if x]:
        audios = con_say(v, textos)
        if audios:
            fuentes[f"say:{v}"] = audios
    clave, pad = [], np.zeros(FS // 2, np.float32)
    for k, (fuente, audios) in enumerate(fuentes.items()):
        for j, (frase, orden, tipo) in enumerate(FRASES):
            x = np.concatenate([pad, audios[frase], pad])
            ruido = rng.normal(0, 1, len(x)).astype(np.float32)
            ruido *= np.sqrt(np.mean(audios[frase] ** 2) / 10 ** (a.snr_db / 10)) / np.sqrt(np.mean(ruido ** 2))
            for cond, y in (("limpio", x), ("ruido", x + ruido)):
                nombre = f"v{k}_{j:02d}_{cond}.wav"
                _guardar(a.salida / nombre, y)
                clave.append({"archivo": nombre, "frase": frase, "orden": orden, "tipo": tipo,
                              "voz": fuente, "condicion": cond})
    _guardar(a.salida / "silencio.wav", np.zeros(2 * FS, np.float32))
    clave.append({"archivo": "silencio.wav", "frase": "", "orden": None, "tipo": "silencio",
                  "voz": "-", "condicion": "limpio"})
    _guardar(a.salida / "solo_ruido.wav", rng.normal(0, 0.02, 2 * FS).astype(np.float32))
    clave.append({"archivo": "solo_ruido.wav", "frase": "", "orden": None, "tipo": "silencio",
                  "voz": "-", "condicion": "ruido"})
    (a.salida / "clave.json").write_text(json.dumps(clave, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(clave)} clips de {len(fuentes)} voces ({', '.join(fuentes)}) → {a.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
