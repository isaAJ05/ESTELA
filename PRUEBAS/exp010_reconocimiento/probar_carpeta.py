"""EXP-010 · Probar la detección con una carpeta de vídeos propios.

Desde ESTELA/, con el entorno de backend/:

    python PRUEBAS/exp010_reconocimiento/probar_carpeta.py --carpeta "C:/Users/USUARIO/Downloads/VIDEOS"

El nombre de cada vídeo dice qué se hizo y en qué orden, por ejemplo
`jumping_jacks_abduccion_derecha.MOV` = primero jumping jacks y luego
abducción derecha. Palabras que entiende (con o sin tildes, `_` o espacios):

    jumping [jack(s)] · abduccion / abductor · marcha [rodillas] · plancha
    zancada / aduccion (= «otro»: no es ninguno de los cuatro)
    derecha / der / d · izquierda / izq / i  (lado del ejercicio anterior;
    «abductor_izquierda_derecha» = abducción izquierda y luego derecha)

Los vídeos sin ninguna de esas palabras se saltan.

Por cada vídeo y cada uno de los 4 ejercicios «elegido» simula la sesión
(`dtw_multi+rel`, como `probar_video.py`) y comprueba, tramo a tramo:
- si el tramo es el ejercicio elegido, que **no** avise (si avisa = falsa alarma);
- si es otro, que avise y diga cuál (o «no reconozco», si es «otro»).

Dónde cambia de ejercicio: si en la carpeta hay un `tiempos.csv` con filas
`video,cambios` (segundos separados por espacios, p. ej.
`jumping_jacks_abduccion_derecha.MOV,25`), se usan esos tiempos. Si no, se
supone que cada tramo dura lo mismo, y el informe lo marca como «estimado».
Los avisos de los `MARGEN_S` segundos tras un cambio no cuentan como falsa
alarma: el detector necesita unos segundos para darse cuenta.

La pose se calcula a 1280 px de ancho y como mucho 30 fps, como la cámara de
la sesión, y se guarda (solo medidas, nunca imágenes) en
`cache/propios/` para no repetirla. Informe en
`resultados/<fecha>-carpeta.md` y `.json`. Todo ignorado por git.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import extraer as E          # noqa: E402
import probar_video as P     # noqa: E402
import reconocer as R        # noqa: E402

EXTENSIONES = {".mov", ".mp4", ".avi", ".mkv", ".m4v"}
ANCHO_MAX, FPS_MAX = 1280, 30.0
MARGEN_S = 8.0     # ~ ventana de 4 s + 3 s sostenido: lo que tarda en reaccionar
PALABRAS = {"jumping": "jumping_jacks", "abduccion": "abduccion", "abductor": "abduccion",
            "marcha": "marcha_rodillas", "plancha": "plancha",
            "zancada": "otro", "aduccion": "otro"}
IGNORAR = {"jack", "jacks", "rodillas", "de", "y", "luego", "con"}
LADOS = {"derecha": "der", "der": "der", "d": "der", "izquierda": "izq", "izq": "izq", "i": "izq"}
NOMBRE = {**P.NOMBRE, "otro": "otro movimiento"}

Tramo = Tuple[str, str]     # (clase, lado)


def leer_nombre(nombre: str) -> Tuple[List[Tramo], List[str]]:
    """'abductor_izquierda_derecha_jumping' → [(abduccion, izq), (abduccion, der),
    (jumping_jacks, '')]. Devuelve también las palabras que no entendió."""
    s = unicodedata.normalize("NFKD", nombre.lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    tramos: List[Tramo] = []
    raras = []
    for p in re.findall(r"[a-z]+", s):
        if p in PALABRAS:
            tramos.append((PALABRAS[p], ""))
        elif p in LADOS and tramos:
            clase, lado = tramos[-1]
            if lado:                       # ya tenía lado: mismo ejercicio, otro lado
                tramos.append((clase, LADOS[p]))
            else:
                tramos[-1] = (clase, LADOS[p])
        elif p not in IGNORAR:
            raras.append(p)
    return tramos, raras


def leer_tiempos(carpeta: Path) -> Dict[str, List[float]]:
    ruta = carpeta / "tiempos.csv"
    if not ruta.exists():
        return {}
    out = {}
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        for fila in csv.reader(f):
            if len(fila) >= 2 and not fila[0].startswith("#") and fila[0] != "video":
                out[fila[0].strip().lower()] = [float(x) for x in fila[1].split()]
    return out


def pose(ruta: Path, modelo: str) -> R.Video:
    """Medidas por frame desde `cache/propios/` o extraídas y guardadas."""
    destino = R.CACHE / "propios" / f"{ruta.stem}-{modelo}-{ANCHO_MAX}.npz"
    tam = ruta.stat().st_size
    if destino.exists():
        with np.load(destino) as d:
            if int(d["tam"]) == tam:
                return R.Video(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    datos = E.extraer(ruta, modelo, ancho_max=ANCHO_MAX, fps_max=FPS_MAX)
    np.savez_compressed(destino, clase="?", lado="", es_ref=False, video=ruta.name,
                        tam=tam, **datos)
    print(f"   pose en {time.time() - t0:.0f} s", flush=True)
    return R.Video(destino)


def tramos_con_tiempo(tramos: List[Tramo], duracion: float,
                      cambios: Optional[List[float]]) -> List[Tuple[str, str, float, float]]:
    """[(clase, lados, desde, hasta)], uniendo tramos seguidos del mismo
    ejercicio (abducción izq → der es el mismo ejercicio elegido)."""
    if cambios is None or len(cambios) != len(tramos) - 1:
        cambios = [duracion * k / len(tramos) for k in range(1, len(tramos))]
    bordes = [0.0, *cambios, duracion]
    out: List[Tuple[str, str, float, float]] = []
    for (clase, lado), a, b in zip(tramos, bordes, bordes[1:]):
        if out and out[-1][0] == clase:
            c, l, a0, _ = out[-1]
            out[-1] = (c, "+".join(x for x in (l, lado) if x), a0, b)
        else:
            out.append((clase, lado, a, b))
    return out


def juzgar(tramos, avisos: List[Tuple[float, str]], elegido: str) -> List[dict]:
    """Un resultado por tramo, para este ejercicio elegido."""
    res = []
    for k, (clase, lado, a, b) in enumerate(tramos):
        ini = a + (MARGEN_S if k > 0 else 0.0)   # tras un cambio, margen para reaccionar
        if clase == elegido:
            malos = [x for x in avisos if ini <= x[0] < b]
            res.append({"tramo": k, "clase": clase, "tipo": "correcto",
                        "ok": not malos, "avisos": malos})
        else:
            fin = b + (MARGEN_S if k < len(tramos) - 1 else 0.0)
            dentro = [x for x in avisos if a <= x[0] < fin]
            esperado = "no_reconocido" if clase == "otro" else clase
            res.append({"tramo": k, "clase": clase, "tipo": "otro" if clase == "otro" else "equivocado",
                        "ok": bool(dentro), "nombre_ok": bool(dentro) and dentro[0][1] == esperado,
                        "avisos": dentro})
    return res


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--carpeta", type=Path, required=True)
    p.add_argument("--modelo", default="lite", choices=("lite", "full", "heavy"))
    p.add_argument("--referencias", default="multi", choices=("multi", "una"))
    p.add_argument("--tau-no", type=float, default=0.75)
    p.add_argument("--tau-si", type=float, default=0.75)
    p.add_argument("--ratio", type=float, default=0.7)
    p.add_argument("--act-min", type=float, default=0.25)
    a = p.parse_args()
    warnings.filterwarnings("ignore", category=RuntimeWarning)

    videos = sorted(f for f in a.carpeta.iterdir() if f.suffix.lower() in EXTENSIONES)
    tiempos = leer_tiempos(a.carpeta)
    plan = []
    for f in videos:
        tramos, raras = leer_nombre(f.stem)
        if not tramos:
            print(f"salto {f.name}: el nombre no dice ningún ejercicio")
            continue
        aviso = f"   (no entiendo: {', '.join(raras)})" if raras else ""
        print(f"{f.name:45s} → " + " → ".join(f"{c}{' ' + l if l else ''}" for c, l in tramos) + aviso)
        plan.append((f, tramos))
    if not plan:
        return 1

    catalogo = R.cargar_catalogo()
    if a.referencias == "una":
        refs, _ = R.refs_comunes(catalogo, P._referencias(a.modelo, R.VIDEO_REF.values()))
        metodo, con_seg, relativo = "dtw_comun", True, False
    else:
        ids = [vid for vid, _, clase, *_ in E.BANCO if clase in R.CLASES and not vid.startswith("propio_")]
        refs = R.refs_multi(R.crudas_multi(catalogo, P._referencias(a.modelo, ids))[0])
        metodo, con_seg, relativo = "dtw_multi", False, True
    det = f"{metodo}{'+seg' if con_seg else ''}{'+rel' if relativo else ''}"

    lineas = [f"# Prueba de carpeta · {datetime.now():%Y-%m-%d %H:%M}", "",
              f"`{a.carpeta}` · {det} · τ_no {a.tau_no} · τ_si {a.tau_si} · ratio {a.ratio} · "
              f"pose {a.modelo} a {ANCHO_MAX} px y ≤ {FPS_MAX:.0f} fps · margen tras un cambio {MARGEN_S:.0f} s", ""]
    todos, por_video = [], {}
    for n, (f, tramos) in enumerate(plan, 1):
        print(f"\n[{n}/{len(plan)}] {f.name}", flush=True)
        v = pose(f, a.modelo)
        dur = len(v) / R.FPS
        cambios = tiempos.get(f.name.lower())
        tt = tramos_con_tiempo(tramos, dur, cambios)
        estimado = cambios is None or len(cambios) != len(tramos) - 1
        punt, _ = R.puntuar(v, refs)
        comp, act = R.completadas(v, catalogo), R.actividad(v)

        lineas += [f"## {f.name}", "",
                   f"{dur:.1f} s · persona visible {v.presente.mean():.0%} · tramos "
                   + " → ".join(f"{NOMBRE[c]}{' ' + l if l else ''} ({x:.0f}–{y:.0f} s)" for c, l, x, y in tt)
                   + (" · **tiempos estimados** (sin `tiempos.csv`)" if estimado else ""), "",
                   "| Elegido | Avisos | Resultado |", "|---|---|---|"]
        por_video[f.name] = {"duracion_s": round(dur, 1), "tramos": tt, "tiempos_estimados": estimado,
                             "elegidos": {}}
        for el in R.CLASES:
            av = R.decidir(el, len(v), punt, comp, act, metodo, a.tau_no, a.tau_si,
                           a.act_min, con_seg, a.ratio, relativo)
            res = juzgar(tt, av, el)
            todos += [{**r, "video": f.name, "elegido": el} for r in res]
            por_video[f.name]["elegidos"][el] = {"avisos": av, "juicio": res}
            txt_av = "; ".join(f"{t:.0f} s {'«no reconozco»' if e == 'no_reconocido' else NOMBRE[e]}"
                               for t, e in av) or "ninguno"
            txt_res = []
            for r in res:
                if r["tipo"] == "correcto":
                    txt_res.append("✔ calla en su tramo" if r["ok"] else
                                   f"✘ falsa alarma ({', '.join(f'{t:.0f} s' for t, _ in r['avisos'])})")
                elif not r["ok"]:
                    txt_res.append(f"✘ no avisa en {NOMBRE[r['clase']]}")
                else:
                    txt_res.append(f"✔ avisa en {NOMBRE[r['clase']]}" + ("" if r["nombre_ok"] else " (nombre ✘)"))
            lineas.append(f"| {NOMBRE[el]} | {txt_av} | {' · '.join(txt_res)} |")
            print(f"   elegido {el:16s} {txt_av}")
        lineas.append("")

    def frac(xs):
        return f"{sum(xs)}/{len(xs)} ({sum(xs) / len(xs):.0%})" if xs else "—"
    corr = [r["ok"] for r in todos if r["tipo"] == "correcto"]
    mal = [r for r in todos if r["tipo"] == "equivocado"]
    otro = [r for r in todos if r["tipo"] == "otro"]
    resumen = [
        "## Resumen", "",
        "| | Casos | Bien |", "|---|---|---|",
        f"| Calla cuando hace el ejercicio elegido (sin falsa alarma) | {len(corr)} | {frac(corr)} |",
        f"| Avisa cuando hace otro de los cuatro | {len(mal)} | {frac([r['ok'] for r in mal])} |",
        f"| … y dice bien cuál es | {len(mal)} | {frac([r['nombre_ok'] for r in mal])} |",
        f"| Avisa cuando hace otra cosa (zancada, aducción) | {len(otro)} | {frac([r['ok'] for r in otro])} |",
        f"| … y dice «no reconozco» | {len(otro)} | {frac([r['nombre_ok'] for r in otro])} |",
        "",
        "Falsas alarmas:",
        *[f"- {r['video']} · elegido {NOMBRE[r['elegido']]} · {', '.join(f'{t:.0f} s' for t, _ in r['avisos'])}"
          for r in todos if r["tipo"] == "correcto" and not r["ok"]],
        "",
    ]
    lineas[4:4] = resumen
    R.RESULTADOS.mkdir(exist_ok=True)
    base = R.RESULTADOS / f"{datetime.now():%Y%m%d-%H%M%S}-carpeta"
    base.with_suffix(".md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    base.with_suffix(".json").write_text(json.dumps({"detector": det, "videos": por_video},
                                                    ensure_ascii=False, indent=1, default=str),
                                         encoding="utf-8")
    print("\n" + "\n".join(resumen))
    print(f"informe: {base}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
