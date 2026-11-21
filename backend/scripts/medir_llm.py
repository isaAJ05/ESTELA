"""Mide el verbalizador LLM (rol C de ADR-004) contra un Ollama local.

    python scripts/medir_llm.py --modelos qwen3:4b-instruct-2507-q4_K_M --salida resultados.json

Para cada modelo recorre los errores del catálogo de los ejercicios vigentes
(regla × severidad × `--repeticiones`) y pide la frase por el mismo camino que
la aplicación (`VerbalizadorLLMLocal`, modo Ollama, salida restringida y
validador). Informa:

  - latencia de la llamada (p50, p95, máx) y qué parte habría caído a
    plantilla con cada tiempo límite de `--limites-ms`;
  - cuántas frases rechazó el validador y por qué;
  - con `--piper`, lo que tarda Piper en sintetizar cada frase nueva (las del
    modelo no están en la caché de voz, a diferencia de las plantillas).

No decide el modelo ni el tiempo límite: da los números para que el equipo
los fije. El tiempo límite de la medición (`--timeout-medicion-ms`) es alto a
propósito, para ver la cola de la distribución.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from estela.adaptadores.llm.llm_local import BACKEND_OLLAMA, VerbalizadorLLMLocal  # noqa: E402
from estela.aplicacion.rutina import cargar_catalogo  # noqa: E402
from estela.dominio.feedback.contrato import ErrorTipificado, Severidad  # noqa: E402

VIGENTES = ("jumping_jacks", "abduccion_cadera_izq", "abduccion_cadera_der", "plancha",
            "zancada_atras_izq", "zancada_atras_der")


def errores(catalogo, ejercicios, repeticiones):
    for sid in ejercicios:
        ej = catalogo[sid]
        for regla in ej.skill.reglas:
            # la dirección la fija el motor según hacia dónde se pasa el umbral;
            # aquí se recorren las que la regla puede dar (ADR-004 §2.5)
            for direccion in (list(regla.direcciones.values()) or [None]):
                for sev in Severidad:
                    for rep in range(repeticiones):
                        yield ErrorTipificado(
                            error_id=regla.error_id, segmento=regla.segmento, lado=regla.lado,
                            severidad=sev, fase="", repeticion=rep, ejercicio_id=sid,
                            mensaje_id=regla.mensaje_id or regla.error_id,
                            direccion=direccion)


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q / 100.0
    i = int(k)
    return xs[i] + (xs[min(i + 1, len(xs) - 1)] - xs[i]) * (k - i)


def resumen(xs):
    return {"n": len(xs), "media": round(statistics.fmean(xs), 1) if xs else None,
            "p50": round(pct(xs, 50), 1) if xs else None,
            "p95": round(pct(xs, 95), 1) if xs else None,
            "max": round(max(xs), 1) if xs else None}


def medir_modelo(modelo, lista, a, piper):
    v = VerbalizadorLLMLocal(url=a.url, modelo=modelo, backend=BACKEND_OLLAMA,
                             timeout_ms=a.timeout_medicion_ms, temperatura=a.temperatura)
    if not v.precalentar(600.0):
        return {"modelo": modelo, "error": "no se pudo cargar el modelo en Ollama"}
    v.verbalizar(lista[0])                       # primera llamada tras cargar, fuera de la medición
    v.llamadas, v.caidas = 0, {}
    lat, tokens, tok_s, motivos, frases, sint = [], [], [], Counter(), Counter(), []
    muestras = []
    for err in lista:
        m = v.verbalizar(err)
        lat.append(m.latencia_ms)
        t = v.ultimos_timings
        if t.get("eval_count") and t.get("eval_duration"):
            tokens.append(t["eval_count"])
            tok_s.append(t["eval_count"] / (t["eval_duration"] / 1e9))
        if m.fallback:
            motivos[m.motivo_rechazo.split(":", 1)[0] if not m.motivo_rechazo.startswith(
                "fallo_backend") else m.motivo_rechazo] += 1
        else:
            if piper is not None and m.texto not in frases:
                sint.append(piper.sintetizar(m.texto)[2] * 1000.0)
            frases[m.texto] += 1
        if len(muestras) < a.muestras:
            muestras.append({"error": f"{err.ejercicio_id}/{err.error_id}/{err.severidad.value}",
                             "texto": m.texto, "plantilla": m.fallback,
                             "motivo": m.motivo_rechazo, "ms": round(m.latencia_ms)})
    n = len(lat)
    return {
        "modelo": modelo, "llamadas": n, "latencia_ms": resumen(lat),
        "tokens_respuesta": resumen(tokens), "tokens_por_s": resumen(tok_s),
        "rechazadas_o_fallidas": sum(motivos.values()),
        "pct_rechazadas_o_fallidas": round(100.0 * sum(motivos.values()) / n, 1),
        "motivos": dict(motivos.most_common()),
        "frases_distintas_aceptadas": len(frases),
        # con cada tiempo límite: % de llamadas que no habrían llegado a tiempo
        "pct_fuera_de_limite": {str(L): round(100.0 * sum(x > L for x in lat) / n, 1)
                                for L in a.limites_ms},
        "piper_sintesis_frase_nueva_ms": resumen(sint) if piper is not None else None,
        "muestras": muestras,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modelos", required=True, help="nombres de `ollama list`, separados por coma")
    p.add_argument("--url", default=None, help="defecto: Ollama local")
    p.add_argument("--ejercicios", default=",".join(VIGENTES))
    p.add_argument("--repeticiones", type=int, default=2)
    p.add_argument("--temperatura", type=float, default=0.3)
    p.add_argument("--timeout-medicion-ms", type=int, default=20000)
    p.add_argument("--limites-ms", default="200,300,400,500,700,1000",
                   type=lambda s: [int(x) for x in s.split(",")])
    p.add_argument("--piper", action="store_true", help="medir la síntesis de las frases nuevas")
    p.add_argument("--muestras", type=int, default=12)
    p.add_argument("--salida", type=Path)
    a = p.parse_args(argv)

    catalogo = cargar_catalogo()
    lista = list(errores(catalogo, a.ejercicios.split(","), a.repeticiones))
    piper = None
    if a.piper:
        from feedback_testing.informe2 import VozPiperSinAudio, ruta_voz_piper
        piper = VozPiperSinAudio(ruta_voz_piper())
        piper.sintetizar("Frase de calentamiento.")
    R = {"equipo": {"so": platform.platform(), "maquina": platform.machine(),
                    "procesador": platform.processor()},
         "errores_por_modelo": len(lista), "temperatura": a.temperatura,
         "timeout_medicion_ms": a.timeout_medicion_ms, "modelos": []}
    for modelo in a.modelos.split(","):
        r = medir_modelo(modelo, lista, a, piper)
        R["modelos"].append(r)
        if "error" in r:
            print(f"{modelo}: {r['error']}")
            continue
        L, f = r["latencia_ms"], r["pct_fuera_de_limite"]
        print(f"\n== {modelo}: {r['llamadas']} llamadas")
        print(f"latencia ms: p50 {L['p50']}  p95 {L['p95']}  máx {L['max']}  | "
              f"tokens/s p50 {r['tokens_por_s']['p50']}")
        print("fuera del límite: " + "  ".join(f"{k} ms: {v} %" for k, v in f.items()))
        print(f"rechazadas o fallidas: {r['pct_rechazadas_o_fallidas']} %  {r['motivos']}")
        print(f"frases distintas aceptadas: {r['frases_distintas_aceptadas']}")
        if r["piper_sintesis_frase_nueva_ms"]:
            s = r["piper_sintesis_frase_nueva_ms"]
            print(f"Piper, frase nueva (ms): p50 {s['p50']}  p95 {s['p95']}  máx {s['max']}")
        for m in r["muestras"]:
            print(f"  [{m['ms']:5d} ms] {'PLANTILLA ' + m['motivo'] if m['plantilla'] else 'llm'}"
                  f" · {m['error']} → {m['texto']}")
    if a.salida:
        a.salida.parent.mkdir(parents=True, exist_ok=True)
        a.salida.write_text(json.dumps(R, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\ndatos: {a.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
