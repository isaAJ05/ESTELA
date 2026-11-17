"""Hoja a ciegas para comparar dos modelos como entrenadora (prueba A/B).

    python scripts/hoja_ab.py --modelos qwen3:14b,llama3.3:70b --salida DIR \\
        --historial datos_locales/historial_ejemplo.jsonl

Arma 20 situaciones con datos de `sesiones/*.json`: resúmenes entre ejercicios,
resúmenes de final de rutina, la pregunta «¿cómo voy?», frases de dolor y
órdenes ambiguas. Pide la respuesta a cada modelo con el mismo mensaje y los
mismos parámetros, y escribe `hoja_ab.csv` con «respuesta A» y «respuesta B»
en orden al azar por situación. Qué modelo es A en cada fila, su latencia y si
el validador de la aplicación la habría aceptado quedan en
`clave_NO_ABRIR/clave_ab.json`.

Las respuestas de cada modelo se guardan (`respuestas_<modelo>.json`): si un
modelo aún no está descargado, se corre el otro y se completa después con el
mismo comando.

Ojo con dos tipos de situación: en la aplicación el dolor lo contesta un texto
fijo y una orden ambigua recibe «No te entendí». Aquí se le pregunta al modelo
de todos modos, para ver qué diría sin esos filtros.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import time
import urllib.error
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from estela.adaptadores.llm.entrenadora_ollama import GeneradorOllama  # noqa: E402
from estela.aplicacion import entrenadora as en  # noqa: E402
from estela.aplicacion.historial import Historial, progreso  # noqa: E402
from estela.aplicacion.rutina import cargar_catalogo  # noqa: E402

#: mensaje de sistema para las situaciones en que la persona dice algo
SISTEMA_LIBRE = (
    en.SISTEMA.split("\n7.")[0]
    + "\n7. La persona acaba de decir algo: contéstale en el resumen, en una o dos frases.\n"
      "8. Si no queda claro qué quiere, pídele que lo repita.\n"
      "9. Responde en JSON con la forma {\"resumen\": \"...\", \"accion\": \"...\"}.")


def situaciones(sesiones, nombres, prog):
    """20 situaciones: (id, tipo, descripción para la hoja, sistema, datos, permitidas, hechos)."""
    S = []

    def datos(hechos, momento, permitidas, dice=None):
        lineas = list(hechos) + en.hechos_del_historial(prog)
        if dice:
            lineas.append(f"la persona dice: «{dice}»")
        lineas += ["momento: " + momento, "acciones permitidas: " + ", ".join(permitidas)]
        return "\n".join(lineas)

    entre, finales = [], []
    for s in sesiones:
        pasos = [p for p in s["pasos"] if p["skill_id"] in nombres]
        for k, p in enumerate(pasos):
            sig = nombres[pasos[k + 1]["skill_id"]] if k + 1 < len(pasos) else None
            entre.append(en.hechos_del_paso(p, nombres[p["skill_id"]], sig))
        if pasos:
            finales.append((en.hechos_de_la_rutina(pasos, nombres), pasos))
    # variedad: sin repetir datos idénticos
    def unicos(xs, clave):
        vistos, sal = set(), []
        for x in xs:
            k = clave(x)
            if k not in vistos:
                vistos.add(k)
                sal.append(x)
        return sal
    entre = unicos(entre, lambda h: "\n".join(h))
    finales = unicos(finales, lambda f: "\n".join(f[0]))
    P_ENTRE, P_FINAL, P_CONS = en.PERMITIDAS[en.ENTRE], en.PERMITIDAS[en.FINAL], en.PERMITIDAS[en.CONSULTA]
    for h in entre[:9]:
        S.append(("entre", "Resumen entre dos ejercicios", en.SISTEMA,
                  datos(h, "entre dos ejercicios", P_ENTRE), P_ENTRE, h))
    for h, _ in finales[:4]:
        S.append(("final", "Resumen al final de la rutina", en.SISTEMA,
                  datos(h, "final de la rutina", P_FINAL), P_FINAL, h))
    for h, pasos in finales[:3]:
        # igual que `Entrenadora.como_voy`: el total de avisos va como dato
        avisos = sum(v for q in pasos for v, _ in en._indicaciones(q))
        h = list(h) + [f"avisos en total: {avisos}"]
        S.append(("como_voy", "La persona pregunta «¿cómo voy?»", en.SISTEMA,
                  datos(h, "la persona pregunta cómo va, a mitad de la rutina", P_CONS), P_CONS, h))
    h0 = entre[0]
    for dice in ("Me duele la rodilla.", "Sentí un tirón en la espalda, ¿sigo?"):
        S.append(("dolor", f"DOLOR (en la app lo contesta un texto fijo): «{dice}»", SISTEMA_LIBRE,
                  datos(h0, "entre dos ejercicios", P_ENTRE, dice), P_ENTRE, h0))
    for dice in ("Pausa o siguiente.", "No sé, lo que tú digas."):
        S.append(("ambigua", f"ORDEN AMBIGUA (en la app: «No te entendí»): «{dice}»", SISTEMA_LIBRE,
                  datos(h0, "entre dos ejercicios", P_ENTRE, dice), P_ENTRE, h0))
    return [(i + 1, *s) for i, s in enumerate(S[:20])]


def _archivo(modelo: str) -> str:
    return "respuestas_" + re.sub(r"[^A-Za-z0-9._-]+", "_", modelo) + ".json"


def correr(modelo, S, timeout_s, url):
    g = GeneradorOllama(modelo, timeout_s, **({"url": url} if url else {}))
    if not g.precalentar(1800.0):
        return None
    filas = {}
    for sid, tipo, desc, sistema, datos, permitidas, hechos in S:
        t0 = time.perf_counter()
        try:
            try:
                sal = g(sistema, datos, permitidas)
            except urllib.error.HTTPError:            # modelo sin modo de pensar: sin `think`
                g.pensar = None
                sal = g(sistema, datos, permitidas)
            resumen, accion, error = str(sal.get("resumen", "")).strip(), sal.get("accion"), ""
        except Exception as e:                            # noqa: BLE001
            resumen, accion, error = "", None, f"{type(e).__name__}: {e}"[:200]
        ms = (time.perf_counter() - t0) * 1000
        momento = {"entre": en.ENTRE, "final": en.FINAL, "como_voy": en.CONSULTA}.get(tipo, en.ENTRE)
        rechazo = error or en.validar_accion(accion, momento) or en.validar_resumen(resumen, hechos)
        texto = en.Entrenadora._texto(resumen, accion, momento) if (resumen and accion in en.ACCIONES) else resumen
        filas[str(sid)] = {"texto": texto, "resumen": resumen, "accion": accion, "ms": round(ms),
                           "validador": rechazo or "aceptada", "tokens": g.ultimos_timings.get("eval_count")}
        print(f"  [{modelo}] {sid:2d} {tipo:9} {ms:6.0f} ms · {rechazo or 'aceptada'} · {texto[:110]}", flush=True)
    return filas


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modelos", required=True, help="dos modelos de `ollama list`, separados por coma")
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--sesiones", type=Path, default=RAIZ / "sesiones")
    p.add_argument("--historial", type=Path)
    p.add_argument("--timeout-s", type=float, default=300.0)
    p.add_argument("--url", default=None)
    p.add_argument("--semilla", type=int, default=20261116)
    p.add_argument("--rehacer", action="store_true", help="volver a pedir aunque ya haya respuestas")
    a = p.parse_args(argv)
    modelos = [m for m in a.modelos.split(",") if m]
    assert len(modelos) == 2, "hacen falta exactamente dos modelos"

    catalogo = cargar_catalogo()
    nombres = {sid: ej.skill.nombre for sid, ej in catalogo.items()}
    sesiones = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(a.sesiones.glob("*.json"))
                if not f.name.startswith("2026111")]          # solo las sesiones de ejemplo originales
    sesiones = [s for s in sesiones if any(x["completadas"] > 0 for x in s["pasos"])]
    prog = progreso(Historial(a.historial).leer(), date.today()) if a.historial else None
    S = situaciones(sesiones, nombres, prog)
    a.salida.mkdir(parents=True, exist_ok=True)
    (a.salida / "situaciones.json").write_text(json.dumps(
        [{"id": s[0], "tipo": s[1], "descripcion": s[2], "datos": s[4]} for s in S],
        ensure_ascii=False, indent=1), encoding="utf-8")

    R = {}
    for m in modelos:
        f = a.salida / _archivo(m)
        if f.exists() and not a.rehacer:
            R[m] = json.loads(f.read_text(encoding="utf-8"))
            print(f"{m}: respuestas ya guardadas ({len(R[m])})")
            continue
        print(f"{m}: pidiendo {len(S)} respuestas…", flush=True)
        filas = correr(m, S, a.timeout_s, a.url)
        if filas is None:
            print(f"{m}: NO DISPONIBLE en Ollama (¿sin descargar?). Se completa después con el mismo comando.")
            continue
        f.write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
        R[m] = filas
    if len(R) < 2:
        print(f"Falta un modelo: la hoja no se arma todavía. Situaciones: {len(S)}.")
        return 0

    rng = random.Random(a.semilla)
    clave, hoja = {}, []
    for sid, tipo, desc, _, datos, _, _ in S:
        orden = modelos[:]
        rng.shuffle(orden)
        ra, rb = R[orden[0]][str(sid)], R[orden[1]][str(sid)]
        clave[str(sid)] = {"A": {"modelo": orden[0], **{k: ra[k] for k in ("ms", "validador", "accion")}},
                           "B": {"modelo": orden[1], **{k: rb[k] for k in ("ms", "validador", "accion")}}}
        hoja.append({"n": sid, "situacion": desc,
                     "datos_que_recibio": datos.replace("\n", " | "),
                     "respuesta_A": ra["texto"] or "(sin respuesta)",
                     "respuesta_B": rb["texto"] or "(sin respuesta)",
                     "mejor_A_B_o_igual": "", "A_dice_algo_falso": "", "B_dice_algo_falso": "",
                     "A_no_suena_natural": "", "B_no_suena_natural": "", "notas": ""})
    with open(a.salida / "hoja_ab.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(hoja[0]))
        w.writeheader()
        w.writerows(hoja)
    (a.salida / "clave_NO_ABRIR").mkdir(exist_ok=True)
    (a.salida / "clave_NO_ABRIR" / "clave_ab.json").write_text(
        json.dumps(clave, ensure_ascii=False, indent=1), encoding="utf-8")
    for m in modelos:
        ms = sorted(v["ms"] for v in R[m].values())
        ok = sum(v["validador"] == "aceptada" for v in R[m].values())
        print(f"{m}: latencia p50 {ms[len(ms) // 2]} ms, máx {ms[-1]} ms; el validador habría aceptado {ok}/{len(ms)}")
    print(f"hoja: {a.salida / 'hoja_ab.csv'} ({len(hoja)} situaciones)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
