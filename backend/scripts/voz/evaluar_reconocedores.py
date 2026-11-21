"""Compara motores locales de reconocimiento de voz con las órdenes de ESTELA.

    python scripts/voz/evaluar_reconocedores.py --audio DIR --salida resultados.json

Motores: whisper.cpp (pywhispercpp), mlx-whisper y faster-whisper, cada uno con
varios tamaños del modelo multilingüe de Whisper, en español (`language="es"`).
Para cada combinación mide: carga, latencia por clip (p50, p95), órdenes
acertadas, órdenes falsas (dijo una orden donde no la había) y cuántas veces
pediría repetir. La orden se saca con `estela.aplicacion.comandos_voz`, igual
que en la aplicación. Se prueba con y sin `initial_prompt` (las seis órdenes
como pista de vocabulario).

No elige: da los números. Audio sintético (`generar_audio_comandos.py`).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ))

from estela.aplicacion.comandos_voz import interpretar  # noqa: E402

PISTA = "Pausa. Seguir. Siguiente. Repetir. Terminar. ¿Cómo voy?"
MLX = {"tiny": ["mlx-community/whisper-tiny", "mlx-community/whisper-tiny-mlx"],
       "base": ["mlx-community/whisper-base-mlx", "mlx-community/whisper-base"],
       "small": ["mlx-community/whisper-small-mlx", "mlx-community/whisper-small"],
       "large-v3-turbo": ["mlx-community/whisper-large-v3-turbo"]}


def leer(ruta: Path) -> np.ndarray:
    with wave.open(str(ruta)) as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


def motor_mlx(tam, cache):
    import mlx_whisper
    ultimo = None
    for repo in MLX[tam]:
        try:
            mlx_whisper.transcribe(np.zeros(16000, np.float32), path_or_hf_repo=repo, language="es")
            return lambda x, pista: mlx_whisper.transcribe(
                x, path_or_hf_repo=repo, language="es", temperature=0.0,
                condition_on_previous_text=False, initial_prompt=pista, verbose=None)["text"], repo
        except Exception as e:                            # noqa: BLE001
            ultimo = e
    raise ultimo


def motor_faster(tam, cache):
    from faster_whisper import WhisperModel
    m = WhisperModel(tam, device="cpu", compute_type="int8", download_root=str(cache / "faster"))

    def f(x, pista):
        segs, _ = m.transcribe(x, language="es", beam_size=5, temperature=0.0,
                               condition_on_previous_text=False, initial_prompt=pista)
        return "".join(s.text for s in segs)
    return f, f"faster-whisper {tam} int8 cpu"


def motor_whispercpp(tam, cache, haz=False):
    from pywhispercpp.model import Model
    reg = cache / f"whispercpp-{tam}.log"
    # params_sampling_strategy: 0 = voraz (el defecto), 1 = búsqueda por haz
    m = Model(tam, models_dir=str(cache / "whispercpp"), redirect_whispercpp_logs_to=str(reg),
              params_sampling_strategy=1 if haz else 0, print_progress=False, print_realtime=False)

    def f(x, pista):
        return " ".join(s.text for s in m.transcribe(x, language="es", initial_prompt=pista or ""))
    gpu = ""
    try:
        t = reg.read_text(errors="ignore").lower()
        gpu = "metal" if "metal" in t else ("gpu" if "use gpu    = 1" in t else "sin gpu en el registro")
    except OSError:
        pass
    return f, f"whisper.cpp {tam} ({gpu}{', haz' if haz else ''})"


def motor_whispercpp_haz(tam, cache):
    return motor_whispercpp(tam, cache, haz=True)


MOTORES = {"whispercpp": (motor_whispercpp, ["tiny", "base", "small", "large-v3-turbo"]),
           "whispercpp-haz": (motor_whispercpp_haz, ["small", "large-v3-turbo"]),
           "mlx": (motor_mlx, ["tiny", "base", "small", "large-v3-turbo"]),
           "faster": (motor_faster, ["tiny", "base", "small"])}


def pct(xs, q):
    return float(np.percentile(xs, q)) if xs else None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--audio", type=Path, required=True)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--cache", type=Path, default=Path.home() / "estela-mac" / "cache")
    p.add_argument("--motores", default="whispercpp,mlx,faster")
    p.add_argument("--tamanos", default="")
    a = p.parse_args(argv)
    os.environ.setdefault("HF_HOME", str(a.cache / "hf"))
    clave = json.loads((a.audio / "clave.json").read_text(encoding="utf-8"))
    audios = {c["archivo"]: leer(a.audio / c["archivo"]) for c in clave}
    dur = float(np.mean([len(x) / 16000 for x in audios.values()]))
    R = {"clips": len(clave), "duracion_media_s": round(dur, 2), "pista": PISTA, "filas": []}
    for nombre in a.motores.split(","):
        crear, tamanos = MOTORES[nombre]
        for tam in (a.tamanos.split(",") if a.tamanos else tamanos):
            if tam not in tamanos:
                continue
            try:
                t0 = time.perf_counter()
                f, desc = crear(tam, a.cache)
                f(np.zeros(16000, np.float32), None)          # primera inferencia: carga y calienta
                carga = time.perf_counter() - t0
            except Exception as e:                        # noqa: BLE001
                print(f"{nombre} {tam}: NO DISPONIBLE: {type(e).__name__}: {str(e)[:160]}", flush=True)
                R["filas"].append({"motor": nombre, "modelo": tam, "error": f"{type(e).__name__}: {str(e)[:200]}"})
                continue
            for pista in (None, PISTA):
                lat, det = [], []
                for c in clave:
                    t0 = time.perf_counter()
                    try:
                        texto = f(audios[c["archivo"]], pista)
                    except Exception as e:                # noqa: BLE001
                        texto = f"<<error {type(e).__name__}>>"
                    lat.append((time.perf_counter() - t0) * 1000)
                    i = interpretar(texto)
                    det.append({**c, "texto": texto.strip(), "comando": i.comando, "motivo": i.motivo})
                ordenes = [d for d in det if d["orden"]]
                otros = [d for d in det if not d["orden"]]
                fila = {
                    "motor": nombre, "modelo": tam, "desc": desc, "pista": pista is not None,
                    "carga_s": round(carga, 2), "lat_p50_ms": round(pct(lat, 50)), "lat_p95_ms": round(pct(lat, 95)),
                    "lat_max_ms": round(max(lat)),
                    "ordenes": len(ordenes), "acertadas": sum(d["comando"] == d["orden"] for d in ordenes),
                    "orden_equivocada": sum(d["comando"] not in (None, d["orden"]) for d in ordenes),
                    "acertadas_limpio": sum(d["comando"] == d["orden"] for d in ordenes if d["condicion"] == "limpio"),
                    "ordenes_limpio": sum(d["condicion"] == "limpio" for d in ordenes),
                    "sin_orden": len(otros), "orden_falsa": sum(d["comando"] is not None for d in otros),
                    "pide_repetir_en_silencio": sum(d["motivo"] in ("sin_comando", "ambiguo")
                                                    for d in otros if d["tipo"] == "silencio"),
                    "fallos": [{k: d[k] for k in ("archivo", "frase", "voz", "condicion", "texto", "comando")}
                               for d in det if d["comando"] != d["orden"]][:40],
                }
                R["filas"].append(fila)
                print(f"{nombre:10} {tam:15} pista={'sí' if pista else 'no'} | carga {carga:5.1f} s | "
                      f"p50 {fila['lat_p50_ms']:5d} ms p95 {fila['lat_p95_ms']:5d} ms | "
                      f"órdenes {fila['acertadas']}/{fila['ordenes']} (limpio {fila['acertadas_limpio']}/{fila['ordenes_limpio']}), "
                      f"equivocadas {fila['orden_equivocada']} | falsas {fila['orden_falsa']}/{fila['sin_orden']} | {desc}",
                      flush=True)
            a.salida.parent.mkdir(parents=True, exist_ok=True)
            a.salida.write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"datos: {a.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
