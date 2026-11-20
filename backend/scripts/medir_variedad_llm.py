"""Compara el verbalizador LLM de antes y el de ahora en variedad y naturalidad.

    python scripts/medir_variedad_llm.py --veces 6 --salida variedad.json

Pedido de Paula (2026-11-20): «sigue repitiendo bastante las mismas cosas en
lugar de hacer la misma corrección con palabras diferentes». Para cada regla de
los ejercicios vigentes (con su primera dirección y severidad moderada) pide la
misma corrección `--veces` seguidas, como pasaría en una sesión, con:

  - `antes`: `variar=False` (mismo mensaje cada vez, temperatura 0,3);
  - `ahora`: `variar=True` (frase de referencia, frases ya dichas, 0,8).

Mide por condición: frases distintas sobre las pedidas, cuántas cayeron a
plantilla y por qué, latencia (p50, p95, máx) y cuántas caerían con el límite
de la app (`config.LLM_TIMEOUT_MS`). No mide naturalidad: guarda las frases
para leerlas.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from estela import config  # noqa: E402
from estela.adaptadores.llm.llm_local import BACKEND_OLLAMA, VerbalizadorLLMLocal  # noqa: E402
from estela.aplicacion.rutina import cargar_catalogo  # noqa: E402
from estela.dominio.feedback.contrato import ErrorTipificado, Severidad  # noqa: E402

from medir_llm import VIGENTES, resumen  # noqa: E402


def casos(catalogo):
    vistos = set()
    for sid in VIGENTES:
        for regla in catalogo[sid].skill.reglas:
            clave = (regla.mensaje_id or regla.error_id, regla.lado)
            if clave in vistos:
                continue
            vistos.add(clave)
            dirs = list(regla.direcciones.values()) or [None]
            yield sid, regla, dirs[0]


def correr(variar, modelo, url, veces, catalogo):
    v = VerbalizadorLLMLocal(url=url, modelo=modelo, backend=BACKEND_OLLAMA,
                             timeout_ms=5000, variar=variar)
    v.precalentar()
    filas, lat, caidas = [], [], Counter()
    for sid, regla, direccion in casos(catalogo):
        textos = []
        for rep in range(veces):
            e = ErrorTipificado(error_id=regla.error_id, segmento=regla.segmento, lado=regla.lado,
                                severidad=Severidad.MODERADA, fase="", repeticion=rep,
                                ejercicio_id=sid, mensaje_id=regla.mensaje_id or regla.error_id,
                                direccion=direccion)
            t0 = time.perf_counter()
            m = v.verbalizar(e)
            ms = (time.perf_counter() - t0) * 1000.0
            if not m.fallback:
                lat.append(ms)
            else:
                caidas[m.motivo_rechazo.split(":")[0]] += 1
            textos.append({"texto": m.texto, "plantilla": m.fallback,
                           "motivo": m.motivo_rechazo, "ms": round(ms)})
        distintas = len({t["texto"].lower().strip(" .") for t in textos})
        filas.append({"ejercicio": sid, "error": regla.error_id, "distintas": distintas,
                      "frases": textos})
    pedidas = sum(len(f["frases"]) for f in filas)
    return {"variar": variar, "temperatura": v.temperatura,
            "pedidas": pedidas,
            "distintas": sum(f["distintas"] for f in filas),
            "a_plantilla": sum(caidas.values()), "motivos": dict(caidas),
            "latencia_ms": resumen(lat),
            "sobre_limite_app": sum(1 for x in lat if x > config.LLM_TIMEOUT_MS),
            "limite_app_ms": config.LLM_TIMEOUT_MS, "errores": filas}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default=config.LLM_MODELO)
    ap.add_argument("--url", default=None)
    ap.add_argument("--veces", type=int, default=6)
    ap.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args()
    catalogo = cargar_catalogo()
    res = {"modelo": a.modelo, "veces": a.veces,
           "antes": correr(False, a.modelo, a.url, a.veces, catalogo),
           "ahora": correr(True, a.modelo, a.url, a.veces, catalogo)}
    a.salida.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for k in ("antes", "ahora"):
        r = res[k]
        print(f"{k}: {r['distintas']}/{r['pedidas']} frases distintas, "
              f"{r['a_plantilla']} a plantilla {r['motivos']}, latencia {r['latencia_ms']}, "
              f"{r['sobre_limite_app']} sobre {r['limite_app_ms']} ms")


if __name__ == "__main__":
    main()
