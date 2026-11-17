"""Latencia de la pose con todo corriendo a la vez, frente a la pose sola.

    python scripts/voz/medir_todo_a_la_vez.py --salida DIR \\
        --videos "a.mp4:jumping_jacks" "b.mp4:plancha" [--historial h.jsonl]

Corre cada vídeo dos veces, a ritmo real y sin ventana, con `python -m estela`:

- «base»: solo la pose y el motor de reglas (plantillas, sin entrenadora, voz
  en texto, sin reconocimiento de voz).
- «todo»: lo mismo más el LLM que redacta las correcciones, la entrenadora
  con LLM, Piper sintetizando de verdad y Whisper reconociendo una orden cada
  `--cada-s` segundos durante toda la sesión.

Qué no es igual que en una sesión con una persona, para leer bien el número:

- Piper sintetiza pero no suena: tras sintetizar espera lo que dura el audio
  (por SSH no hay altavoz que valga). El cálculo es el real.
- Whisper no escucha un micrófono: transcribe en bucle los clips sintéticos
  de `tests/datos/voz/`. En la aplicación solo se escucha en pausa y entre
  ejercicios; aquí reconoce también durante el movimiento, así que la carga
  es mayor que la de uso.
- La rutina es el mismo ejercicio dos veces, para que la entrenadora hable en
  medio mientras se siguen procesando frames.

Da p50 y p95 de la etapa `pose` y del `total` por frame, juntando los frames
de todos los vídeos. No decide nada: solo mide.
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import tempfile
import threading
import time
import wave
from collections import defaultdict
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ))

CLIPS = ("pausa.wav", "seguir.wav", "siguiente.wav", "terminar.wav", "como_voy.wav")


def _rutina(skill: str, catalogo) -> dict:
    """El mismo ejercicio dos veces: corto y luego largo."""
    por_tiempo = catalogo[skill].unidad != "repeticiones"
    corto, largo = ({"duracion_s": 5}, {"duracion_s": 120}) if por_tiempo else (
        {"repeticiones": 3}, {"repeticiones": 60})
    return {"nombre": "Medición", "pasos": [{"skill_id": skill, **corto}, {"skill_id": skill, **largo}]}


def uno(a: argparse.Namespace) -> int:
    """Una sesión (un vídeo, una condición) en este proceso."""
    from estela import __main__ as principal
    from estela import config
    from estela.adaptadores.voz import motores
    from estela.aplicacion.metricas import Latencias
    from estela.aplicacion.rutina import cargar_catalogo

    muestras = defaultdict(list)
    anota = Latencias.anota

    def anota_y_guarda(self, etapa, ms):
        muestras[etapa].append(ms)
        anota(self, etapa, ms)
    Latencias.anota = anota_y_guarda

    resumenes = []
    principal._imprimir_resumen = resumenes.append
    todo = a.uno == "todo"
    sintesis_ms, reconocer_ms, parar = [], [], threading.Event()

    if todo:
        class PiperSinAltavoz(motores.VozPiper):
            nombre = "piper (sintetiza, no suena)"

            def hablar(self, texto: str) -> None:
                nueva, t0 = texto not in self._cache, time.perf_counter()
                wav = self._sintetizar(texto)
                if nueva:
                    sintesis_ms.append((time.perf_counter() - t0) * 1000)
                self.ultimo_inicio_audio = time.perf_counter()
                with wave.open(io.BytesIO(wav)) as r:
                    time.sleep(r.getnframes() / r.getframerate())

        motores.crear_motor = lambda preferido, ruta: PiperSinAltavoz(ruta)

        from estela.adaptadores.voz_entrada.reconocedor import ReconocedorWhisperCpp
        reconocedor = ReconocedorWhisperCpp(config.modelo_voz_entrada())
        reconocedor.precalentar()
        clips = []
        for nombre in CLIPS:
            with wave.open(str(RAIZ / "tests" / "datos" / "voz" / nombre)) as w:
                clips.append(np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0)

        def reconocer_en_bucle():
            k = 0
            while not parar.wait(a.cada_s):
                t0 = time.perf_counter()
                reconocedor.transcribir(clips[k % len(clips)])
                reconocer_ms.append((time.perf_counter() - t0) * 1000)
                k += 1
        threading.Thread(target=reconocer_en_bucle, name="carga-whisper", daemon=True).start()

    catalogo = cargar_catalogo()
    with tempfile.TemporaryDirectory() as d:
        ruta = Path(d) / "rutina.json"
        ruta.write_text(json.dumps(_rutina(a.skill, catalogo)), encoding="utf-8")
        argv = ["--rutina", str(ruta), "--video", a.video, "--sin-ventana", "--tiempo-real",
                "--voz-entrada", "no", "--sin-historial"]
        argv += (["--verbalizador", "llm", "--entrenadora", "llm", "--voz", "piper"]
                 + (["--entrenadora-historial", a.historial] if a.historial else [])
                 if todo else ["--verbalizador", "plantillas", "--entrenadora", "no", "--voz", "texto"])
        for opcion in ("modelo", "delegado"):
            if getattr(a, opcion):
                argv += [f"--{opcion}", getattr(a, opcion)]
        t0 = time.perf_counter()
        codigo = principal.main(argv)
        dura = time.perf_counter() - t0
    parar.set()
    r = resumenes[-1] if resumenes else {}
    Path(a.salida).write_text(json.dumps({
        "condicion": a.uno, "video": Path(a.video).name, "skill": a.skill, "codigo": codigo,
        "segundos": round(dura, 1), "frames": r.get("frames"),
        "frames_sin_persona": r.get("frames_sin_persona"),
        "muestras": {k: [round(v, 3) for v in vs] for k, vs in muestras.items()
                     if k in ("pose", "total", "verbalizacion")},
        "sintesis_ms": [round(v) for v in sintesis_ms],
        "reconocer_ms": [round(v) for v in reconocer_ms],
        "llm": r.get("llm"), "voz": r.get("voz"),
        "entrenadora": [{"momento": e["momento"], "dicha": e["dicha"],
                         "origen": (e["respuesta"] or {}).get("origen"),
                         "latencia_ms": (e["respuesta"] or {}).get("latencia_ms")}
                        for e in (r.get("entrenadora") or {}).get("respuestas", ())],
        "correcciones": sum(len(p.get("mensajes", ())) for p in r.get("pasos", ())),
    }, ensure_ascii=False), encoding="utf-8")
    return 0


def _pct(vs, q):
    return round(float(np.percentile(vs, q)), 2) if vs else None


def _fila(vs):
    return {"n": len(vs), "p50_ms": _pct(vs, 50), "p95_ms": _pct(vs, 95), "p99_ms": _pct(vs, 99),
            "max_ms": round(max(vs), 2) if vs else None,
            "sobre_33ms": sum(v > 33.3 for v in vs)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--videos", nargs="+", help="ruta.mp4:skill_id")
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--historial", help="historial de ejemplo para la entrenadora")
    p.add_argument("--cada-s", type=float, default=2.0, help="segundos entre dos órdenes reconocidas")
    p.add_argument("--modelo", help="modelo de pose (defecto: el del equipo)")
    p.add_argument("--delegado", help="cpu o gpu (defecto: el del equipo)")
    p.add_argument("--condiciones", default="base,todo")
    p.add_argument("--uno", choices=("base", "todo"), help=argparse.SUPPRESS)
    p.add_argument("--video", help=argparse.SUPPRESS)
    p.add_argument("--skill", help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    if a.uno:
        return uno(a)

    a.salida.mkdir(parents=True, exist_ok=True)
    corridas = []
    for condicion in a.condiciones.split(","):
        for k, par in enumerate(a.videos):
            video, skill = par.rsplit(":", 1)
            destino = a.salida / f"{condicion}_{k:02d}_{skill}.json"
            orden = [sys.executable, __file__, "--uno", condicion, "--video", video, "--skill", skill,
                     "--salida", str(destino), "--cada-s", str(a.cada_s)]
            for opcion in ("historial", "modelo", "delegado"):
                if getattr(a, opcion):
                    orden += [f"--{opcion}", getattr(a, opcion)]
            print(f"[{condicion}] {Path(video).name} ({skill})…", flush=True)
            registro = a.salida / f"{condicion}_{k:02d}_{skill}.log"
            with open(registro, "w", encoding="utf-8") as fh:
                subprocess.run(orden, stdout=fh, stderr=subprocess.STDOUT, check=False)
            if destino.exists():
                corridas.append(json.loads(destino.read_text(encoding="utf-8")))
            else:
                print(f"   FALLÓ: ver {registro}", flush=True)

    informe = {"cada_s": a.cada_s, "modelo": a.modelo or "defecto del equipo",
               "delegado": a.delegado or "defecto del equipo", "condiciones": {}}
    for condicion in a.condiciones.split(","):
        suyas = [c for c in corridas if c["condicion"] == condicion]
        junta = lambda clave: [v for c in suyas for v in c["muestras"].get(clave, ())]   # noqa: E731
        informe["condiciones"][condicion] = {
            "videos": len(suyas), "frames": sum(c["frames"] or 0 for c in suyas),
            "pose": _fila(junta("pose")), "total": _fila(junta("total")),
            "verbalizacion_llm": _fila(junta("verbalizacion")),
            "sintesis_piper": _fila([v for c in suyas for v in c["sintesis_ms"]]),
            "reconocer_whisper": _fila([v for c in suyas for v in c["reconocer_ms"]]),
            "entrenadora": [e for c in suyas for e in c["entrenadora"]],
            "correcciones": sum(c["correcciones"] for c in suyas),
            "por_video": [{"video": c["video"], "skill": c["skill"], "frames": c["frames"],
                           "pose": _fila(c["muestras"].get("pose", [])),
                           "total": _fila(c["muestras"].get("total", []))} for c in suyas],
        }
        f = informe["condiciones"][condicion]
        print(f"{condicion:5} | {f['videos']} vídeos, {f['frames']} frames | pose p50 {f['pose']['p50_ms']} "
              f"p95 {f['pose']['p95_ms']} máx {f['pose']['max_ms']} ms | total p50 {f['total']['p50_ms']} "
              f"p95 {f['total']['p95_ms']} ms | frames con total > 33 ms: {f['total']['sobre_33ms']}", flush=True)
    (a.salida / "todo_a_la_vez.json").write_text(json.dumps(informe, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    print(f"datos: {a.salida / 'todo_a_la_vez.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
