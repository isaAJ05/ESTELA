"""EXP-009 §10 · Zancada de perfil: qué lado ve la cámara, hacia dónde mira la
persona, qué pierna va atrás, ángulos de rodilla y longitud de paso por frame.

Desde ESTELA/, con el entorno de backend/ (necesita el modelo de pose):

    python PRUEBAS/exp009_zancada/volcado_frames.py RUTA.mp4 [--desde S] [--hasta S]

Escribe `resultados/<vídeo>.csv` (un frame por fila; no se versiona) y un
resumen por tramos: cada vez que cambian la dirección de la mirada o la pierna
de atrás empieza un tramo nuevo. Así, en un vídeo con varias series, se puede
comparar lo que detecta con lo que se hizo.

Reglas, las de EXP-009 §10.3:
- mira: nariz respecto al punto medio de las orejas, en la imagen.
- pierna de atrás: el tobillo más retrasado respecto a la cadera según la mirada.
- cercana: la rodilla con más visibilidad (la que evalúa `solo_lado_visible`).
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from itertools import groupby
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))

import cv2  # noqa: E402

from estela import config  # noqa: E402
from estela.adaptadores.pose.estimador import EstimadorPose  # noqa: E402
from estela.adaptadores.pose.landmarks import NOMBRES_MEDIAPIPE  # noqa: E402
from estela.dominio.feedback.motor import geometria as G  # noqa: E402

I = {n: i for i, n in enumerate(NOMBRES_MEDIAPIPE)}
ABAJO = 110.0       # rodilla visible por debajo: punto bajo de la repetición
MIN_TRAMO_S = 1.0   # tramos más cortos se tratan como ruido en el resumen
PIES_JUNTOS = 0.3   # paso por debajo: no hay pierna de atrás (zancada dinámica, arriba)


def roles(x):
    """`x(nombre)` → x normalizada en la imagen. Devuelve (mira, atras)."""
    signo = 1 if x("nose") > (x("left_ear") + x("right_ear")) / 2 else -1
    cadera = (x("left_hip") + x("right_hip")) / 2
    adelante_izq = (x("left_ankle") - cadera) * signo
    adelante_der = (x("right_ankle") - cadera) * signo
    return ("der" if signo > 0 else "izq"), ("izq" if adelante_izq < adelante_der else "der")


# Comprobación mínima: mira a la derecha con el pie izquierdo atrás, y al revés.
_P = {"nose": .6, "left_ear": .5, "right_ear": .5, "left_hip": .5, "right_hip": .5,
      "left_ankle": .3, "right_ankle": .7}
assert roles(_P.get) == ("der", "izq")
assert roles({**_P, "nose": .4}.get) == ("izq", "der")


def volcar(video: str, desde: float, hasta: float) -> list:
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    est = EstimadorPose(config.modelo_pose("lite"))
    filas, n = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = n / fps
        n += 1
        res = est.estimar(frame, int(t * 1000))   # también antes de `desde`: el tracking necesita continuidad
        if t > hasta:
            break
        if t < desde or res.muestra is None:
            continue
        kps, img = res.muestra.keypoints, res.imagen
        obs = G.observacion_desde_pose(res.muestra, "volcado")
        a, c = obs.angulos, obs.confianza
        if "rodilla_izq" not in a or "rodilla_der" not in a:
            continue
        mira, atras = roles(lambda k: float(img[I[k], 0]))
        cercana = "izq" if c.get("rodilla_izq", 0) >= c.get("rodilla_der", 0) else "der"
        filas.append({
            "t": round(t, 2), "mira": mira, "atras": atras, "cercana": cercana,
            "cercana_z": "izq" if kps["left_shoulder"].z < kps["right_shoulder"].z else "der",
            "rodilla_izq": round(a["rodilla_izq"], 1), "rodilla_der": round(a["rodilla_der"], 1),
            "conf_izq": round(c.get("rodilla_izq", 0), 2), "conf_der": round(c.get("rodilla_der", 0), 2),
            "tronco": round(a.get("tronco_inclinacion", float("nan")), 1),
            "paso": round(obs.distancias.get("longitud_paso", float("nan")), 2),
        })
    est.cerrar()
    print(f"{Path(video).name}: {fps:.2f} fps, {len(filas)} frames con persona")
    return filas


def resumen(filas: list) -> None:
    def q(v, p):
        v = sorted(v)
        return v[int(p * (len(v) - 1))] if v else float("nan")

    previa = None
    for f in filas:     # con los pies juntos la pierna de atrás no existe: se hereda
        if not f["paso"] < PIES_JUNTOS:   # también si el paso es NaN
            previa = f["atras"]
        f["tramo"] = (f["mira"], previa or f["atras"])
    for (mira, atras), grupo in groupby(filas, key=lambda f: f["tramo"]):
        g = list(grupo)
        if g[-1]["t"] - g[0]["t"] < MIN_TRAMO_S:
            continue
        abajo = [f for f in g if min(f["rodilla_izq"], f["rodilla_der"]) < ABAJO]
        delante = "der" if atras == "izq" else "izq"
        cerca = statistics.mode(f["cercana"] for f in g)
        print(f"\n{g[0]['t']:6.1f}–{g[-1]['t']:6.1f} s · mira a la {mira} · pierna {atras} atrás · "
              f"la cámara ve la rodilla {'trasera' if cerca == atras else 'delantera'} ({cerca})")
        if not abajo:
            print("   sin frames abajo (rodilla < 110°)")
            continue
        print(f"   frames abajo: {len(abajo)} · rodilla delantera mín {min(f['rodilla_' + delante] for f in abajo):.0f}° · "
              f"trasera mín {min(f['rodilla_' + atras] for f in abajo):.0f}° · "
              f"confianza cercana/lejana p50 {q([f['conf_' + cerca] for f in g], .5):.2f}/"
              f"{q([f['conf_' + ('der' if cerca == 'izq' else 'izq')] for f in g], .5):.2f}")
        print(f"   paso abajo p10–p90 {q([f['paso'] for f in abajo], .1):.2f}–{q([f['paso'] for f in abajo], .9):.2f} · "
              f"tronco p90 {q([f['tronco'] for f in g], .9):.0f}° · "
              f"media de rodillas arriba (p90) {q([(f['rodilla_izq'] + f['rodilla_der']) / 2 for f in g], .9):.0f}° "
              f"(el conteo reinicia por encima de 145°)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("video")
    p.add_argument("--desde", type=float, default=0.0)
    p.add_argument("--hasta", type=float, default=float("inf"))
    args = p.parse_args()
    filas = volcar(args.video, args.desde, args.hasta)
    if not filas:
        sys.exit("ningún frame con persona")
    salida = Path(__file__).parent / "resultados" / (Path(args.video).stem + ".csv")
    salida.parent.mkdir(exist_ok=True)
    with open(salida, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]), delimiter=";")
        w.writeheader()
        w.writerows(filas)
    resumen(filas)
    print(f"\nCSV por frame: {salida}")


if __name__ == "__main__":
    main()
