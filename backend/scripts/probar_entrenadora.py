"""Prueba la entrenadora sobre sesiones guardadas y mide su latencia.

    python scripts/historial_ejemplo.py --repartir-dias 14
    python scripts/probar_entrenadora.py --modelo qwen3:14b --timeout-s 60 \\
        --historial datos_locales/historial_ejemplo.jsonl --salida resultados.json
    python scripts/probar_entrenadora.py                 # sin modelo: solo plantillas

Para cada sesión de `sesiones/*.json` con algo hecho pide la respuesta «entre
ejercicios» de cada paso y la del «final», como haría la aplicación, y además
unas frases de la usuaria con y sin dolor. Imprime cada respuesta con su
origen (llm, plantilla o fija_dolor), la acción propuesta y la latencia.

No decide el modelo ni el tiempo límite: da los números. `--timeout-s` aquí es
el de la medición (alto, para ver la cola de la distribución).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from estela.aplicacion.entrenadora import Entrenadora  # noqa: E402
from estela.aplicacion.historial import Historial, progreso  # noqa: E402
from estela.aplicacion.rutina import cargar_catalogo  # noqa: E402

FRASES_USUARIA = ("me duele la rodilla", "creo que me lastimé el tobillo", "estoy mareada",
                  "¿cómo voy?", "quiero seguir", "estoy cansada")


def pct(xs, q):
    xs = sorted(xs)
    k = (len(xs) - 1) * q / 100.0
    i = int(k)
    return xs[i] + (xs[min(i + 1, len(xs) - 1)] - xs[i]) * (k - i)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modelo", help="nombre de `ollama list`; sin él, solo plantillas")
    p.add_argument("--timeout-s", type=float, default=120.0)
    p.add_argument("--url", default=None)
    p.add_argument("--sesiones", type=Path, default=RAIZ / "sesiones")
    p.add_argument("--historial", type=Path, help="JSONL (scripts/historial_ejemplo.py)")
    p.add_argument("--repeticiones", type=int, default=1, help="veces que se pide cada situación")
    p.add_argument("--salida", type=Path)
    a = p.parse_args(argv)

    catalogo = cargar_catalogo()
    nombres = {sid: ej.skill.nombre for sid, ej in catalogo.items()}
    generador = None
    if a.modelo:
        from estela.adaptadores.llm.entrenadora_ollama import URL_OLLAMA, GeneradorOllama
        generador = GeneradorOllama(a.modelo, a.timeout_s, url=a.url or URL_OLLAMA)
        if not generador.precalentar(900.0):
            print(f"no se pudo cargar {a.modelo} en Ollama")
            return 1
    e = Entrenadora(generador, nombres)
    prog = progreso(Historial(a.historial).leer(), date.today()) if a.historial else None

    filas = []

    def anota(situacion, r):
        t = generador.ultimos_timings if generador and r.origen == "llm" else {}
        filas.append({"situacion": situacion, **r.a_dict(),
                      "tokens": t.get("eval_count"),
                      "tok_s": (round(t["eval_count"] / (t["eval_duration"] / 1e9), 1)
                                if t.get("eval_duration") else None)})
        print(f"[{r.latencia_ms:7.0f} ms · {r.origen:10} · {r.accion:9}"
              f"{' · ' + r.motivo_caida if r.motivo_caida else ''}] {situacion}\n    {r.texto}")

    sesiones = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(a.sesiones.glob("*.json"))]
    sesiones = [s for s in sesiones if any(p_["completadas"] > 0 for p_ in s["pasos"])]
    if generador is not None and sesiones:           # primera respuesta tras cargar: fuera
        e.al_final(sesiones[0]["pasos"], prog)
        e.origenes.clear()
        e.caidas.clear()
    for _ in range(a.repeticiones):
        for i, s in enumerate(sesiones):
            pasos = [p_ for p_ in s["pasos"] if p_["skill_id"] in nombres]
            for k, paso in enumerate(pasos):
                sig = pasos[k + 1]["skill_id"] if k + 1 < len(pasos) else None
                anota(f"sesión {i} · entre · {paso['skill_id']} "
                      f"{paso['completadas']}/{paso['objetivo']}",
                      e.entre_ejercicios(paso, sig, prog))
            if pasos:
                anota(f"sesión {i} · final", e.al_final(pasos, prog))
    if sesiones:
        paso = sesiones[0]["pasos"][0]
        for frase in FRASES_USUARIA:
            anota(f"usuaria dice «{frase}»", e.entre_ejercicios(paso, None, prog, frase))

    lat = [f["latencia_ms"] for f in filas if f["origen"] == "llm"]
    print(f"\n{len(filas)} situaciones · orígenes {dict(e.origenes)} · caídas {dict(e.caidas)}")
    if lat:
        print(f"latencia de las respuestas del modelo (ms): p50 {pct(lat, 50):.0f}  "
              f"p95 {pct(lat, 95):.0f}  máx {max(lat):.0f}  (n = {len(lat)})")
    acciones = Counter(f["accion"] for f in filas if f["origen"] == "llm")
    if acciones:
        print(f"acciones propuestas por el modelo: {dict(acciones)}")
    if a.salida:
        a.salida.parent.mkdir(parents=True, exist_ok=True)
        a.salida.write_text(json.dumps(
            {"modelo": a.modelo, "historial": bool(prog), "origenes": dict(e.origenes),
             "caidas": dict(e.caidas), "filas": filas}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"datos: {a.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
