"""Geometría del tronco para EXP-004 (puntos adicionales de columna y pelvis).

Todo se calcula en 2D, en píxeles del plano de imagen (x a la derecha, y hacia
abajo). SpinePose solo entrega 2D, y para comparar en igualdad de condiciones
las medidas de MediaPipe también se toman de sus *image landmarks* pasados a
píxeles (no de los normalizados: x e y tienen escalas distintas).

Convención de signo de las orientaciones: grados respecto a la vertical, con
signo positivo hacia donde mira la persona (`sentido` = +1 si mira hacia la
derecha de la imagen, -1 si mira a la izquierda). En vista frontal se usa
`sentido` = +1 y el signo pasa a significar «hacia la derecha de la imagen».

Solo numpy: se puede probar sin MediaPipe ni SpinePose instalados.
"""

from __future__ import annotations

from typing import Dict, Sequence

import numpy as np

# MediaPipe Pose Landmarker, 33 puntos (orden de estela/pose/landmarks.py).
MP = {
    "oreja_izq": 7, "oreja_der": 8,
    "hombro_izq": 11, "hombro_der": 12,
    "cadera_izq": 23, "cadera_der": 24,
    "talon_izq": 29, "talon_der": 30,
    "punta_izq": 31, "punta_der": 32,
}

# SpinePose 2.1.0, 37 puntos (spinepose/metainfo.py). Los comentarios dan la
# vértebra que corresponde a cada punto según los `sigmas` de esa metainfo.
SP = {
    "hombro_izq": 5, "hombro_der": 6,
    "cadera_izq": 11, "cadera_der": 12,
    "c7": 18,          # "neck": base del cuello
    "sacro": 19,       # "hip": punto medio del sacro
    "dedo_izq": 20, "dedo_der": 21,
    "talon_izq": 24, "talon_der": 25,
    "l5": 26, "l3": 27, "l1": 28,   # spine_01..03 (spine_03 = T12/L1)
    "t8": 29, "t3": 30,             # spine_04..05
    "c4": 35, "c1": 36,             # neck_02, neck_03
}

#: Cadena de la columna de tronco, de abajo arriba (sin cervicales).
CADENA_TRONCO = ("sacro", "l5", "l3", "l1", "t8", "t3", "c7")


# ---------------------------------------------------------------------------
# Primitivas
# ---------------------------------------------------------------------------

def medio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a + b) / 2.0


def orientacion(v: np.ndarray, sentido: float = 1.0) -> np.ndarray:
    """Ángulo con signo (grados) de los vectores `v` (..., 2) respecto a la
    vertical hacia arriba. Positivo = inclinado hacia `sentido`."""
    v = np.asarray(v, dtype=float)
    return np.degrees(np.arctan2(sentido * v[..., 0], -v[..., 1]))


def oblicuidad(izq: np.ndarray, der: np.ndarray) -> np.ndarray:
    """Inclinación (grados) de la línea izq-der respecto a la horizontal.

    Positivo = el punto izquierdo está más bajo en la imagen. Es la medida de
    caída de pelvis o de hombros en vista frontal.
    """
    dy = izq[..., 1] - der[..., 1]
    dx = np.abs(izq[..., 0] - der[..., 0])
    return np.degrees(np.arctan2(dy, dx))


def flecha(puntos: np.ndarray, sentido: float = 1.0) -> np.ndarray:
    """Curvatura de una cadena de puntos (..., K, 2), sin unidades.

    Media de la distancia con signo de los puntos interiores a la cuerda
    primero→último, dividida por la longitud de la cuerda. Positivo = la
    cadena se abomba hacia la espalda (convexidad dorsal: tronco redondeado);
    negativo = hacia delante (lordosis). Una cadena recta da 0.

    Se usa la media y no el máximo porque la columna sana tiene forma de S:
    con el máximo el signo saltaría entre la zona lumbar y la dorsal.
    """
    p = np.asarray(puntos, dtype=float)
    cuerda = p[..., -1, :] - p[..., 0, :]
    largo = np.linalg.norm(cuerda, axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        u = cuerda / largo[..., None]
    # Normal dorsal: girar la cuerda 90° hacia la espalda (ver docstring del
    # módulo: la persona mira hacia `sentido`).
    n_dorsal = sentido * np.stack([u[..., 1], -u[..., 0]], axis=-1)
    rel = p[..., 1:-1, :] - p[..., :1, :]
    d = np.einsum("...kc,...c->...k", rel, n_dorsal)
    with np.errstate(invalid="ignore", divide="ignore"):
        return d.mean(axis=-1) / largo


def sentido_mirada(talones: np.ndarray, puntas: np.ndarray) -> float:
    """+1 si la persona mira hacia la derecha de la imagen, -1 si a la
    izquierda. Se decide por grabación (mediana de talón→punta en x), no por
    frame: en un frame suelto el signo puede saltar si los pies se acortan."""
    dx = (puntas[..., 0] - talones[..., 0]).reshape(-1)
    dx = dx[np.isfinite(dx)]
    if dx.size == 0:
        return 1.0
    return 1.0 if np.median(dx) >= 0 else -1.0


# ---------------------------------------------------------------------------
# Puntos virtuales (la idea inicial: subdividir el tronco con MediaPipe)
# ---------------------------------------------------------------------------

FRACCIONES_VIRTUALES = (0.25, 0.5, 0.75)


def puntos_virtuales_mp(kp: np.ndarray) -> Dict[str, np.ndarray]:
    """Puntos de tronco y pelvis «añadidos» a MediaPipe por interpolación.

    Tronco: puntos al 25 %, 50 % y 75 % entre cadera media y hombro medio.
    Pelvis: las dos caderas, la cadera media y un punto «lumbar» al 15 %.

    Todos son combinaciones afines de los 33 puntos existentes. Este es el
    brazo de control del experimento: no pueden contener información que los
    33 no tengan, y la cadena que forman es recta por construcción.
    """
    ci, cd = kp[..., MP["cadera_izq"], :2], kp[..., MP["cadera_der"], :2]
    hi, hd = kp[..., MP["hombro_izq"], :2], kp[..., MP["hombro_der"], :2]
    cm, hm = medio(ci, cd), medio(hi, hd)
    pts = {"cadera_media": cm, "hombro_medio": hm,
           "cadera_izq": ci, "cadera_der": cd,
           "lumbar_15": cm + 0.15 * (hm - cm)}
    for f in FRACCIONES_VIRTUALES:
        pts[f"tronco_{int(f * 100)}"] = cm + f * (hm - cm)
    return pts


def cadena_virtual_mp(kp: np.ndarray) -> np.ndarray:
    v = puntos_virtuales_mp(kp)
    nombres = (["cadera_media", "lumbar_15"]
               + [f"tronco_{int(f * 100)}" for f in FRACCIONES_VIRTUALES]
               + ["hombro_medio"])
    return np.stack([v[n] for n in nombres], axis=-2)


# ---------------------------------------------------------------------------
# Medidas por modelo
# ---------------------------------------------------------------------------

def metricas_mediapipe(kp: np.ndarray, sentido: float = 1.0) -> Dict[str, np.ndarray]:
    """`kp`: (N, 33, >=2) en píxeles. Devuelve arrays (N,)."""
    p = lambda n: kp[:, MP[n], :2]
    cm = medio(p("cadera_izq"), p("cadera_der"))
    hm = medio(p("hombro_izq"), p("hombro_der"))
    om = medio(p("oreja_izq"), p("oreja_der"))
    return {
        # La medida actual de ESTELA (tronco_inclinacion), en 2D y con signo.
        "mp_tronco": orientacion(hm - cm, sentido),
        # Ya disponibles con los 33 puntos y hoy sin usar.
        "mp_cabeza": orientacion(om - hm, sentido),
        "mp_oblic_pelvis": oblicuidad(p("cadera_izq"), p("cadera_der")),
        "mp_oblic_hombros": oblicuidad(p("hombro_izq"), p("hombro_der")),
        # Control: la cadena de puntos virtuales.
        "mp_virtual_flecha": flecha(cadena_virtual_mp(kp), sentido),
    }


def metricas_spinepose(kp: np.ndarray, sentido: float = 1.0) -> Dict[str, np.ndarray]:
    """`kp`: (N, 37, 2) en píxeles. Devuelve arrays (N,).

    No hay medida de inclinación pélvica. Se probó con el vector centro de
    caderas → sacro y es ruido: en los vídeos de PRUEBAS el punto «sacro» de
    SpinePose v2 cae a 1–4,5 % de la longitud del tronco del centro de las
    caderas (1–3 px), así que su orientación tiene un ruido de 6–29° entre frames.
    """
    p = lambda n: kp[:, SP[n], :2]
    cadera_art = medio(p("cadera_izq"), p("cadera_der"))
    hm = medio(p("hombro_izq"), p("hombro_der"))
    lumbar = orientacion(p("l1") - p("sacro"), sentido)
    toracico = orientacion(p("c7") - p("l1"), sentido)
    cad = lambda nombres: np.stack([p(n) for n in nombres], axis=-2)
    return {
        # El mismo vector que mp_tronco, pero con los puntos de SpinePose:
        # aísla lo que aportan los puntos de columna dentro del mismo modelo.
        "sp_hombros_cadera": orientacion(hm - cadera_art, sentido),
        "sp_tronco": orientacion(p("c7") - p("sacro"), sentido),
        "sp_lumbar": lumbar,
        "sp_toracico": toracico,
        # + = la parte alta del tronco se adelanta respecto a la lumbar.
        "sp_toracolumbar": toracico - lumbar,
        # + = convexidad dorsal (redondear); - = lordosis (arquear).
        "sp_flecha": flecha(cad(CADENA_TRONCO), sentido),
        "sp_flecha_lumbar": flecha(cad(("sacro", "l5", "l3", "l1")), sentido),
        "sp_flecha_toracica": flecha(cad(("l1", "t8", "t3", "c7")), sentido),
    }


# ---------------------------------------------------------------------------
# Contorno dorsal a partir de la máscara de segmentación de MediaPipe
# ---------------------------------------------------------------------------

FRACCIONES_CONTORNO = tuple(np.round(np.linspace(0.2, 0.9, 8), 3))


def distancias_contorno(mascara: np.ndarray, cadera: np.ndarray, hombro: np.ndarray,
                        fracciones: Sequence[float] = FRACCIONES_CONTORNO,
                        umbral: float = 0.5, alcance: float = 0.8) -> np.ndarray:
    """Distancia (px) del eje cadera→hombro al borde de la silueta, a los dos
    lados del eje, en varias alturas del tronco.

    Devuelve (len(fracciones), 2): columna 0 hacia la normal n1 = (uy, -ux),
    columna 1 hacia -n1. Qué lado es la espalda se decide después, por
    grabación (ver `flecha_contorno`). NaN si el eje es degenerado.
    """
    h, w = mascara.shape[:2]
    m = mascara.reshape(h, w)
    eje = hombro - cadera
    largo = float(np.hypot(*eje))
    out = np.full((len(fracciones), 2), np.nan)
    if not np.isfinite(largo) or largo < 5:
        return out
    u = eje / largo
    n1 = np.array([u[1], -u[0]])
    pasos = np.arange(0, int(alcance * largo) + 1, dtype=float)
    for i, f in enumerate(fracciones):
        base = cadera + f * eje
        for j, n in enumerate((n1, -n1)):
            xs = np.clip(np.rint(base[0] + pasos * n[0]).astype(int), 0, w - 1)
            ys = np.clip(np.rint(base[1] + pasos * n[1]).astype(int), 0, h - 1)
            fuera = np.nonzero(m[ys, xs] < umbral)[0]
            out[i, j] = pasos[fuera[0]] if fuera.size else pasos[-1]
    return out


def flecha_contorno(dist: np.ndarray, largo: np.ndarray, sentido: float = 1.0,
                    fracciones: Sequence[float] = FRACCIONES_CONTORNO) -> np.ndarray:
    """Curvatura del contorno dorsal, sin unidades (N,).

    `dist`: (N, K, 2) de `distancias_contorno`; `largo`: (N,) longitud del
    eje en px. El lado dorsal es n1 si la persona mira a la derecha (+1) y -n1
    si mira a la izquierda. Positivo = espalda convexa (redondeada).
    """
    lado = 0 if sentido > 0 else 1
    d = dist[:, :, lado] / largo[:, None]            # (N, K), en largos de tronco
    t = np.asarray(fracciones, dtype=float)
    a = (t - t[0]) / (t[-1] - t[0])
    recta = d[:, :1] + a[None, :] * (d[:, -1:] - d[:, :1])
    return (d - recta)[:, 1:-1].mean(axis=1)


__all__ = [
    "MP", "SP", "CADENA_TRONCO", "FRACCIONES_CONTORNO", "FRACCIONES_VIRTUALES",
    "orientacion", "oblicuidad", "flecha", "sentido_mirada",
    "puntos_virtuales_mp", "cadena_virtual_mp",
    "metricas_mediapipe", "metricas_spinepose",
    "distancias_contorno", "flecha_contorno",
]
