"""EXP-008 — análisis. Lee los .npz de `extraer.py` y escribe el informe.

    python PRUEBAS/exp008_puntos_tronco/analizar.py PRUEBAS/exp008_puntos_tronco/resultados/*.npz \\
        --salida PRUEBAS/exp008_puntos_tronco/resultados/informe.md

Tres bloques:

1. Latencia por componente (p50/p95, sin los 10 primeros frames).
2. Por grabación: valor, ruido entre frames y redundancia (r²) con la medida
   de tronco que ESTELA ya tiene (`mp_tronco`). Sirve también para vídeos sin
   etiquetar.
3. Contrastes neutra/inducida del protocolo (README). Por sujeto, cada intento
   se resume en un número; una medida *separa* la condición si todos los
   intentos inducidos quedan del lado esperado de todos los neutros. Con 3+3
   intentos, la probabilidad de separar por azar es 1/20 (unilateral).
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from collections import defaultdict
from itertools import groupby
from math import comb
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tronco as T  # noqa: E402

CALENTAMIENTO = 10          # frames iniciales excluidos de la latencia
VIS_MIN_MP = 0.5            # visibilidad mínima de hombros y caderas
SCORE_MIN_SP = 0.3          # score SimCC mínimo de la cadena (no es probabilidad)

#: Medidas que se comparan, por vista. `mp_tronco` es la línea base.
MEDIDAS = {
    "perfil": ("mp_tronco", "mp_cabeza", "mp_virtual_flecha", "mp_contorno_flecha",
               "sp_hombros_cadera", "sp_tronco", "sp_toracolumbar",
               "sp_flecha", "sp_flecha_lumbar", "sp_flecha_toracica"),
    "frontal": ("mp_tronco", "mp_oblic_pelvis", "mp_oblic_hombros",
                "sp_tronco", "sp_flecha"),
}

#: Protocolo. `esperado`: +1 / -1 = sentido previsto, 0 = cualquiera.
#: `resumen`: cómo se reduce un intento a un número (`mediana` en posturas
#: mantenidas; `extremo` = p95 si se espera subida, p5 si bajada; `rango`).
#: `control`: medidas que, por diseño, NO deberían cambiar.
CONTRASTES = [
    {"neutra": "de_pie_neutro", "inducida": "de_pie_encorvado", "vista": "perfil",
     "resumen": "mediana",
     "esperado": {"sp_flecha": +1, "sp_flecha_toracica": +1, "sp_toracolumbar": +1,
                  "mp_contorno_flecha": +1, "mp_cabeza": +1, "mp_tronco": 0}},
    {"neutra": "de_pie_neutro", "inducida": "de_pie_arqueado", "vista": "perfil",
     "resumen": "mediana",
     "esperado": {"sp_flecha": -1, "sp_flecha_lumbar": -1, "mp_contorno_flecha": -1,
                  "mp_tronco": 0}},
    {"neutra": "bisagra_neutra", "inducida": "bisagra_redondeada", "vista": "perfil",
     "resumen": "mediana", "control": ("mp_tronco", "sp_hombros_cadera"),
     "esperado": {"sp_flecha": +1, "sp_flecha_lumbar": +1, "sp_flecha_toracica": +1,
                  "sp_toracolumbar": +1, "mp_contorno_flecha": +1}},
    {"neutra": "sentadilla_neutra", "inducida": "sentadilla_redondeada", "vista": "perfil",
     "resumen": "extremo",
     "esperado": {"sp_flecha": +1, "sp_flecha_lumbar": +1, "sp_toracolumbar": +1,
                  "mp_contorno_flecha": +1, "mp_tronco": +1}},
    {"neutra": "elevacion_brazos_neutra", "inducida": "elevacion_brazos_arqueada",
     "vista": "perfil", "resumen": "extremo",
     "esperado": {"sp_flecha": -1, "sp_flecha_lumbar": -1, "mp_contorno_flecha": -1,
                  "mp_tronco": -1}},
    {"neutra": "de_pie_neutro_frontal", "inducida": "inclinacion_lateral", "vista": "frontal",
     "resumen": "mediana",
     "esperado": {"mp_tronco": 0, "mp_oblic_hombros": 0, "sp_tronco": 0, "sp_flecha": 0}},
    {"neutra": "marcha_neutra", "inducida": "marcha_cadera_caida", "vista": "frontal",
     "resumen": "rango",
     "esperado": {"mp_oblic_pelvis": +1, "mp_tronco": +1}},
]


# ---------------------------------------------------------------------------
# Carga y medidas
# ---------------------------------------------------------------------------

def cargar(ruta: Path) -> dict:
    d = np.load(ruta)
    rec = {k: d[k] for k in d.files if k != "meta"}
    rec["meta"] = json.loads(str(d["meta"]))
    rec["ruta"] = ruta
    return rec


def medidas(rec: dict) -> dict:
    """Todas las medidas de una grabación, con NaN donde no son válidas."""
    mp = rec["mp_img"].astype(float)
    sp = rec["sp_kp"].astype(float)
    if rec["meta"]["vista"] == "perfil":
        s = T.sentido_mirada(mp[:, [T.MP["talon_izq"], T.MP["talon_der"]], :2],
                             mp[:, [T.MP["punta_izq"], T.MP["punta_der"]], :2])
    else:
        s = 1.0
    cadena = [T.SP[n] for n in T.CADENA_TRONCO]
    with warnings.catch_warnings():             # frames sin persona: todo NaN
        warnings.simplefilter("ignore", RuntimeWarning)
        ok_mp = np.nanmin(mp[:, [11, 12, 23, 24], 3], axis=1) >= VIS_MIN_MP
        ok_sp = np.nanmin(rec["sp_score"][:, cadena], axis=1) >= SCORE_MIN_SP

    out = {}
    for k, v in T.metricas_mediapipe(mp, s).items():
        out[k] = np.where(ok_mp, v, np.nan)
    largo = np.linalg.norm(T.medio(mp[:, 11, :2], mp[:, 12, :2])
                           - T.medio(mp[:, 23, :2], mp[:, 24, :2]), axis=1)
    out["mp_contorno_flecha"] = np.where(
        ok_mp, T.flecha_contorno(rec["contorno"].astype(float), largo, s), np.nan)
    for k, v in T.metricas_spinepose(sp, s).items():
        out[k] = np.where(ok_sp, v, np.nan)
    out["_validos_mp"] = ok_mp
    out["_validos_sp"] = ok_sp
    return out


def ruido(x: np.ndarray) -> float:
    """Desviación típica del ruido entre frames, estimada de forma robusta a
    partir de las diferencias sucesivas (1,4826·MAD/√2). En posturas
    mantenidas es casi todo ruido; en movimiento, una cota superior."""
    d = np.diff(x)
    d = d[np.isfinite(d)]
    if d.size < 5:
        return float("nan")
    return float(1.4826 * np.median(np.abs(d - np.median(d))) / np.sqrt(2))


def r2(x: np.ndarray, y: np.ndarray) -> float:
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 10 or np.std(x[ok]) < 1e-9 or np.std(y[ok]) < 1e-9:
        return float("nan")
    return float(np.corrcoef(x[ok], y[ok])[0, 1] ** 2)


def resumir(x: np.ndarray, modo: str, sentido: int) -> float:
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan")
    if modo == "mediana":
        return float(np.median(x))
    if modo == "rango":
        return float(np.percentile(x, 95) - np.percentile(x, 5))
    return float(np.percentile(x, 5 if sentido < 0 else 95))      # extremo


# ---------------------------------------------------------------------------
# Bloques del informe
# ---------------------------------------------------------------------------

def p50_p95(x) -> str:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return "—"
    return f"{np.percentile(x, 50):.1f} / {np.percentile(x, 95):.1f}"


def bloque_latencia(recs) -> list:
    filas = ["| Componente | Modelo | Frames | p50 / p95 (ms) |", "|---|---|---|---|"]
    clave = lambda r: (r["meta"]["modelo_mp"], r["meta"]["mascara"], r["meta"]["modelo_sp"] or "—")
    for (mp, masc, sp), grupo in groupby(sorted(recs, key=clave), key=clave):
        g = list(grupo)
        cat = lambda k: np.concatenate([r[k][CALENTAMIENTO:] for r in g])
        n = sum(max(0, len(r["lat_mp"]) - CALENTAMIENTO) for r in g)
        filas.append(f"| MediaPipe | {mp}{' + máscara' if masc else ''} | {n} | {p50_p95(cat('lat_mp'))} |")
        if masc:
            filas.append(f"| Contorno dorsal | — | {n} | {p50_p95(cat('lat_contorno'))} |")
        if sp != "—":
            filas.append(f"| SpinePose (solo pose) | {sp} | {n} | {p50_p95(cat('lat_sp'))} |")
            total = cat("lat_mp") + np.nan_to_num(cat("lat_contorno")) + cat("lat_sp")
            filas.append(f"| **Total secuencial** | | {n} | **{p50_p95(total)}** |")
    return filas


def bloque_grabaciones(recs, meds) -> list:
    filas = []
    for r, m in zip(recs, meds):
        meta = r["meta"]
        filas += ["", f"#### `{r['ruta'].name}` — {meta['sujeto']}, {meta['condicion']}, "
                      f"{meta['vista']}, {meta['ancho']}×{meta['alto']}, {meta['frames']} frames",
                  "", f"Frames válidos: MediaPipe {m['_validos_mp'].mean():.0%}, "
                      f"SpinePose {m['_validos_sp'].mean():.0%}.", "",
                  "| Medida | p5 | p50 | p95 | ruido entre frames | (p95−p5)/ruido | r² con `mp_tronco` |",
                  "|---|---|---|---|---|---|---|"]
        for k in MEDIDAS[meta["vista"]]:
            x = m[k]
            if not np.isfinite(x).any():
                continue
            q5, q50, q95 = np.nanpercentile(x, [5, 50, 95])
            rd = ruido(x)
            snr = (q95 - q5) / rd if rd > 1e-9 else float("inf")
            filas.append(f"| `{k}` | {q5:.3f} | {q50:.3f} | {q95:.3f} | {rd:.3f} | "
                         f"{snr:.1f} | {r2(m['mp_tronco'], x):.2f} |")
    return filas


def bloque_contrastes(recs, meds) -> list:
    por = defaultdict(list)            # (sujeto, ropa, condicion, vista) -> [medidas]
    for r, m in zip(recs, meds):
        meta = r["meta"]
        por[(meta["sujeto"], meta.get("ropa", "?"), meta["condicion"], meta["vista"])].append(m)

    filas = []
    for c in CONTRASTES:
        sujetos = sorted({(s, ropa) for (s, ropa, cond, v) in por
                          if cond == c["neutra"] and v == c["vista"]
                          and (s, ropa, c["inducida"], v) in por})
        if not sujetos:
            continue
        filas += ["", f"### {c['neutra']} → {c['inducida']} ({c['vista']}, resumen: {c['resumen']})", "",
                  "| Medida | Esperado | Sujeto | Neutra (intentos) | Inducida (intentos) | Δ medianas | ¿Separa? | p |",
                  "|---|---|---|---|---|---|---|---|"]
        medidas_c = list(c["esperado"].items()) + [(k, None) for k in c.get("control", ())]
        for k, esp in medidas_c:
            for s, ropa in sujetos:
                sent = esp or 0
                neu = [resumir(m[k], c["resumen"], sent)
                       for m in por[(s, ropa, c["neutra"], c["vista"])] if k in m]
                ind = [resumir(m[k], c["resumen"], sent)
                       for m in por[(s, ropa, c["inducida"], c["vista"])] if k in m]
                neu, ind = [x for x in neu if np.isfinite(x)], [x for x in ind if np.isfinite(x)]
                if not neu or not ind:
                    continue
                delta = np.median(ind) - np.median(neu)
                arriba, abajo = min(ind) > max(neu), max(ind) < min(neu)
                if esp is None:
                    separa, p = ("sí (no debería)" if arriba or abajo else "no (correcto)"), None
                elif esp > 0:
                    separa, p = arriba, 1 / comb(len(neu) + len(ind), len(ind))
                elif esp < 0:
                    separa, p = abajo, 1 / comb(len(neu) + len(ind), len(ind))
                else:
                    separa, p = arriba or abajo, 2 / comb(len(neu) + len(ind), len(ind))
                txt_sep = separa if isinstance(separa, str) else ("**sí**" if separa else "no")
                txt_p = f"{p:.3f}" if (p is not None and separa is True) else "—"
                fmt = lambda xs: ", ".join(f"{x:.3f}" for x in xs)
                etiqueta = {1: "+", -1: "−", 0: "±", None: "control"}[esp]
                filas.append(f"| `{k}` | {etiqueta} | {s} ({ropa}) | {fmt(neu)} | {fmt(ind)} | "
                             f"{delta:+.3f} | {txt_sep} | {txt_p} |")
    if not filas:
        filas = ["", "Sin pares neutra/inducida en las grabaciones: no hay contrastes que evaluar."]
    return filas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("npz", nargs="+", type=Path)
    ap.add_argument("--salida", type=Path)
    ap.add_argument("--sin-detalle", action="store_true",
                    help="omite la tabla por grabación")
    args = ap.parse_args()

    recs = [cargar(p) for p in sorted(args.npz)]
    meds = [medidas(r) for r in recs]
    lineas = ["# EXP-008 — informe generado", "",
              f"Grabaciones: {len(recs)}. Generado con `analizar.py`; no editar a mano.", "",
              "## Latencia por frame", ""] + bloque_latencia(recs)
    lineas += ["", "## Contrastes neutra → inducida"] + bloque_contrastes(recs, meds)
    if not args.sin_detalle:
        lineas += ["", "## Por grabación"] + bloque_grabaciones(recs, meds)
    texto = "\n".join(lineas) + "\n"
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(texto, encoding="utf-8")
        print(f"informe: {args.salida}")
    else:
        print(texto)


if __name__ == "__main__":
    main()
