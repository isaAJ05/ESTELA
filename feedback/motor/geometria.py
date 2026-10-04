"""Geometría: de keypoints a ángulos canónicos.

Este módulo existe para que el equipo de retroalimentación pueda trabajar
aunque el equipo de percepción todavía no entregue ángulos: dado un
`MuestraPose` produce una `Observacion` parcial. Si percepción entrega los
ángulos ya calculados, este módulo no se usa en el camino crítico y queda
solo como referencia de la convención de nombres.

Toda la aritmética es stdlib; no hay dependencias externas.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, Optional, Sequence, Tuple

from ..contrato import Keypoint, MuestraPose, Observacion, Plano

Vec = Tuple[float, ...]


# ---------------------------------------------------------------------------
# Nombres de keypoints
# ---------------------------------------------------------------------------
# `[?]` Los nombres siguen la convención de MediaPipe Pose Landmarker. El mapeo
# nombre -> índice NO se fija aquí a propósito: debe confirmarse contra la
# documentación oficial del modelo que finalmente adopte el equipo, y esa
# confirmación es responsabilidad del módulo de percepción. Aquí solo se
# consumen nombres.

KP_REQUERIDOS = (
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
)

#: Definición de cada ángulo canónico como terna (a, vértice, c).
#: El ángulo es el que forman los vectores vértice->a y vértice->c.
ANGULOS_TERNA: Dict[str, Tuple[str, str, str]] = {
    "codo_izq":   ("left_shoulder", "left_elbow", "left_wrist"),
    "codo_der":   ("right_shoulder", "right_elbow", "right_wrist"),
    "hombro_izq": ("left_hip", "left_shoulder", "left_elbow"),
    "hombro_der": ("right_hip", "right_shoulder", "right_elbow"),
    "cadera_izq": ("left_shoulder", "left_hip", "left_knee"),
    "cadera_der": ("right_shoulder", "right_hip", "right_knee"),
    "rodilla_izq": ("left_hip", "left_knee", "left_ankle"),
    "rodilla_der": ("right_hip", "right_knee", "right_ankle"),
}

#: Ángulos bilaterales derivados: media de los dos lados. Existen para que una
#: regla bilateral se exprese con una sola medida en lugar de duplicarse.
#: Su confianza es el mínimo de las dos, no la media.
ANGULOS_MEDIOS: Dict[str, Tuple[str, str]] = {
    "rodilla_media": ("rodilla_izq", "rodilla_der"),
    "cadera_media": ("cadera_izq", "cadera_der"),
    "codo_medio": ("codo_izq", "codo_der"),
    "hombro_medio": ("hombro_izq", "hombro_der"),
}

#: Plano en el que cada medida es fiable con una sola cámara.
#: Los valores provienen de EXP-002 (docs/experimentos/), no de la intuición.
PLANO_DE_ANGULO: Dict[str, Plano] = {
    "codo_izq": Plano.SAGITAL,
    "codo_der": Plano.SAGITAL,
    "codo_medio": Plano.SAGITAL,
    "hombro_izq": Plano.FRONTAL,
    "hombro_der": Plano.FRONTAL,
    "hombro_medio": Plano.FRONTAL,
    "cadera_izq": Plano.SAGITAL,
    "cadera_der": Plano.SAGITAL,
    "cadera_media": Plano.SAGITAL,
    "rodilla_izq": Plano.SAGITAL,
    "rodilla_der": Plano.SAGITAL,
    "rodilla_media": Plano.SAGITAL,
    "tronco_inclinacion": Plano.SAGITAL,
    "valgo_rodilla_izq": Plano.FRONTAL,
    "valgo_rodilla_der": Plano.FRONTAL,
    "separacion_pies": Plano.FRONTAL,
    "rotacion_tronco": Plano.TRANSVERSAL,
    "azimut_cadera": Plano.TRANSVERSAL,
    # ADR-006: medidas con los 33 puntos que no se usaban (EXP-008, brazo A0+).
    # `[I]` Planos asignados por geometría, sin medir aún con EXP-002.
    "oblicuidad_pelvis": Plano.FRONTAL,
    "oblicuidad_hombros": Plano.FRONTAL,
    "inclinacion_lateral": Plano.FRONTAL,
    "cabeza_adelantada": Plano.SAGITAL,
    "abduccion_cadera_izq": Plano.FRONTAL,
    "abduccion_cadera_der": Plano.FRONTAL,
    "alineacion_cadera": Plano.SAGITAL,
}


# ---------------------------------------------------------------------------
# Primitivas vectoriales
# ---------------------------------------------------------------------------

def _coords(kp: Keypoint, usar_z: bool) -> Vec:
    if usar_z and kp.z is not None:
        return (kp.x, kp.y, kp.z)
    return (kp.x, kp.y)


def _resta(a: Vec, b: Vec) -> Vec:
    return tuple(ai - bi for ai, bi in zip(a, b))


def _punto(a: Vec, b: Vec) -> float:
    return sum(ai * bi for ai, bi in zip(a, b))


def _norma(a: Vec) -> float:
    return math.sqrt(_punto(a, a))


def angulo_entre(a: Vec, vertice: Vec, c: Vec) -> Optional[float]:
    """Ángulo en grados en `vertice`, o None si algún vector es degenerado."""
    u = _resta(a, vertice)
    v = _resta(c, vertice)
    nu, nv = _norma(u), _norma(v)
    if nu < 1e-9 or nv < 1e-9:
        return None
    cos = max(-1.0, min(1.0, _punto(u, v) / (nu * nv)))
    return math.degrees(math.acos(cos))


def punto_medio(a: Vec, b: Vec) -> Vec:
    return tuple((ai + bi) / 2.0 for ai, bi in zip(a, b))


# ---------------------------------------------------------------------------
# Medidas derivadas
# ---------------------------------------------------------------------------

def escala_corporal(kps: Dict[str, Keypoint], usar_z: bool = True) -> Optional[float]:
    """Distancia hombro-medio a cadera-media. Unidad de normalización.

    `[R]` Todas las distancias del sistema se expresan como múltiplos de esta
    escala, para que los umbrales no dependan de la estatura del usuario ni de
    su distancia a la cámara.
    """
    req = ("left_shoulder", "right_shoulder", "left_hip", "right_hip")
    if any(k not in kps for k in req):
        return None
    hombro = punto_medio(_coords(kps["left_shoulder"], usar_z),
                         _coords(kps["right_shoulder"], usar_z))
    cadera = punto_medio(_coords(kps["left_hip"], usar_z),
                         _coords(kps["right_hip"], usar_z))
    d = _norma(_resta(hombro, cadera))
    return d if d > 1e-6 else None


def inclinacion_tronco(kps: Dict[str, Keypoint], usar_z: bool = True) -> Optional[float]:
    """Grados de inclinación del tronco respecto a la vertical.

    0 = tronco vertical. Se mide sobre el vector cadera-media -> hombro-medio.
    Asume que el eje vertical de la escena es -y (convención de imagen y de
    `pose_world_landmarks`, donde y crece hacia abajo).
    """
    req = ("left_shoulder", "right_shoulder", "left_hip", "right_hip")
    if any(k not in kps for k in req):
        return None
    hombro = punto_medio(_coords(kps["left_shoulder"], usar_z),
                         _coords(kps["right_shoulder"], usar_z))
    cadera = punto_medio(_coords(kps["left_hip"], usar_z),
                         _coords(kps["right_hip"], usar_z))
    v = _resta(hombro, cadera)
    n = _norma(v)
    if n < 1e-9:
        return None
    vertical = tuple([0.0, -1.0] + ([0.0] if len(v) == 3 else []))
    cos = max(-1.0, min(1.0, _punto(v, vertical) / n))
    return math.degrees(math.acos(cos))


def orientacion_camara(kps: Dict[str, Keypoint]) -> Optional[float]:
    """Orientación del sujeto respecto al plano de imagen, en grados.

    0  = el sujeto está de frente (línea de hombros paralela al plano imagen).
    90 = el sujeto está de perfil.

    Requiere z. Con coordenadas 2D puras se puede aproximar por el
    acortamiento aparente de la línea de hombros, pero esa aproximación es
    ambigua ante cambios de escala; por eso aquí se exige z y se devuelve None
    si no está disponible. `[R]` Preferir `pose_world_landmarks`.
    """
    if "left_shoulder" not in kps or "right_shoulder" not in kps:
        return None
    li, ri = kps["left_shoulder"], kps["right_shoulder"]
    if li.z is None or ri.z is None:
        return None
    dx = ri.x - li.x
    dz = ri.z - li.z
    if abs(dx) < 1e-9 and abs(dz) < 1e-9:
        return None
    ang = math.degrees(math.atan2(abs(dz), abs(dx)))
    return min(90.0, max(0.0, ang))


def desviacion_lateral_rodilla(kps: Dict[str, Keypoint], lado: str) -> Optional[float]:
    """Desplazamiento medio-lateral de la rodilla respecto a la línea
    cadera-tobillo, normalizado por la escala corporal.

    Positivo = la rodilla cae hacia dentro (hacia la línea media del cuerpo).
    Es la medida de valgo dinámico. `[F]` Solo es observable desde el plano
    frontal; ver EXP-002.
    """
    pref = "left" if lado == "izq" else "right"
    req = (f"{pref}_hip", f"{pref}_knee", f"{pref}_ankle",
           "left_hip", "right_hip")
    if any(k not in kps for k in req):
        return None
    esc = escala_corporal(kps)
    if esc is None:
        return None
    cadera = kps[f"{pref}_hip"]
    rodilla = kps[f"{pref}_knee"]
    tobillo = kps[f"{pref}_ankle"]
    # Interpolación de la línea cadera-tobillo a la altura de la rodilla.
    dy = tobillo.y - cadera.y
    if abs(dy) < 1e-9:
        return None
    t = (rodilla.y - cadera.y) / dy
    x_esperado = cadera.x + t * (tobillo.x - cadera.x)
    desplazamiento = rodilla.x - x_esperado
    # Signo: hacia la línea media. La línea media es el punto medio de caderas.
    x_medio = (kps["left_hip"].x + kps["right_hip"].x) / 2.0
    hacia_dentro = 1.0 if cadera.x > x_medio else -1.0
    return -hacia_dentro * desplazamiento / esc


def _azimut(a: Keypoint, b: Keypoint) -> Optional[float]:
    """Ángulo en grados del segmento a->b proyectado sobre el plano
    transversal (XZ). Requiere z."""
    if a.z is None or b.z is None:
        return None
    dx, dz = b.x - a.x, b.z - a.z
    if abs(dx) < 1e-9 and abs(dz) < 1e-9:
        return None
    return math.degrees(math.atan2(dz, dx))


def azimut_cadera(kps: Dict[str, Keypoint]) -> Optional[float]:
    """Orientación de la línea de caderas en el plano transversal."""
    if "left_hip" not in kps or "right_hip" not in kps:
        return None
    return _azimut(kps["left_hip"], kps["right_hip"])


def rotacion_tronco(kps: Dict[str, Keypoint]) -> Optional[float]:
    """Rotación de la línea de hombros respecto a la de caderas, en grados.

    Es la medida de la rotación de tronco disociada de la cadera. `[F]` Es una
    medida del plano **transversal**: con una sola cámara depende enteramente
    de la estimación de profundidad, que es el componente menos fiable de la
    pose monocular. EXP-002 cuantifica el error inducido.
    """
    if any(k not in kps for k in ("left_hip", "right_hip",
                                  "left_shoulder", "right_shoulder")):
        return None
    a = _azimut(kps["left_shoulder"], kps["right_shoulder"])
    b = azimut_cadera(kps)
    if a is None or b is None:
        return None
    d = (a - b + 180.0) % 360.0 - 180.0
    return d


def _horizontal(v: Vec) -> float:
    """Longitud de la parte horizontal de un vector: (x, z) en 3D, x en 2D."""
    return math.hypot(v[0], v[2]) if len(v) == 3 else abs(v[0])


def _oblicuidad(izq: Keypoint, der: Keypoint, usar_z: bool) -> Optional[float]:
    d = _resta(_coords(izq, usar_z), _coords(der, usar_z))
    h = _horizontal(d)
    if h < 1e-9 and abs(d[1]) < 1e-9:
        return None
    # y crece hacia abajo: «izquierdo más alto» es d_y < 0.
    return math.degrees(math.atan2(-d[1], h))


def oblicuidad_pelvis(kps: Dict[str, Keypoint], usar_z: bool = True) -> Optional[float]:
    """Inclinación de la línea de caderas respecto a la horizontal, en grados.

    Positivo = la cadera izquierda está más alta que la derecha. Es la medida
    de «subir la cadera» o de «dejarla caer» de un lado. Con z la horizontal
    incluye la profundidad, así que no depende de cuánto gire la persona; sin z
    solo vale de frente. Plano frontal.
    """
    if "left_hip" not in kps or "right_hip" not in kps:
        return None
    return _oblicuidad(kps["left_hip"], kps["right_hip"], usar_z)


def oblicuidad_hombros(kps: Dict[str, Keypoint], usar_z: bool = True) -> Optional[float]:
    """Igual que `oblicuidad_pelvis`, con la línea de hombros."""
    if "left_shoulder" not in kps or "right_shoulder" not in kps:
        return None
    return _oblicuidad(kps["left_shoulder"], kps["right_shoulder"], usar_z)


def inclinacion_lateral(kps: Dict[str, Keypoint], usar_z: bool = True) -> Optional[float]:
    """Inclinación lateral del tronco con signo, en grados.

    Ángulo del vector cadera media → hombro medio respecto a la vertical,
    medido hacia los lados de la persona. Positivo = el tronco se inclina hacia
    su izquierda. El eje izquierda-derecha se toma de la línea de caderas
    (horizontal), no de la imagen, así que el signo no depende del espejo ni de
    hacia dónde mire. A diferencia de `tronco_inclinacion`, ignora la
    inclinación hacia delante. Plano frontal.
    """
    req = ("left_shoulder", "right_shoulder", "left_hip", "right_hip")
    if any(k not in kps for k in req):
        return None
    hombro = punto_medio(_coords(kps["left_shoulder"], usar_z),
                         _coords(kps["right_shoulder"], usar_z))
    cadera = punto_medio(_coords(kps["left_hip"], usar_z),
                         _coords(kps["right_hip"], usar_z))
    v = _resta(hombro, cadera)
    lr = _resta(_coords(kps["left_hip"], usar_z), _coords(kps["right_hip"], usar_z))
    if len(v) == 3:
        h = math.hypot(lr[0], lr[2])
        if h < 1e-9:
            return None
        u = (lr[0] / h, 0.0, lr[2] / h)
    else:
        if abs(lr[0]) < 1e-9:
            return None
        u = (math.copysign(1.0, lr[0]), 0.0)
    if _norma(v) < 1e-9:
        return None
    return math.degrees(math.atan2(_punto(v, u), -v[1]))


def cabeza_adelantada(kps: Dict[str, Keypoint], usar_z: bool = True) -> Optional[float]:
    """Desalineación de la cabeza respecto al tronco, en grados, sin signo.

    Ángulo entre el eje del tronco (cadera media → hombro medio) y el del cuello
    (hombro medio → oreja media). 0 = la cabeza sigue la prolongación del
    tronco. Crece si la cabeza se adelanta o cae, y también si se echa hacia
    atrás. Vale igual de pie que tumbada (plancha). Plano sagital.
    """
    req = ("left_shoulder", "right_shoulder", "left_hip", "right_hip",
           "left_ear", "right_ear")
    if any(k not in kps for k in req):
        return None
    hombro = punto_medio(_coords(kps["left_shoulder"], usar_z),
                         _coords(kps["right_shoulder"], usar_z))
    cadera = punto_medio(_coords(kps["left_hip"], usar_z),
                         _coords(kps["right_hip"], usar_z))
    oreja = punto_medio(_coords(kps["left_ear"], usar_z),
                        _coords(kps["right_ear"], usar_z))
    ang = angulo_entre(cadera, hombro, oreja)
    return None if ang is None else 180.0 - ang


def abduccion_cadera(kps: Dict[str, Keypoint], lado: str) -> Optional[float]:
    """Separación lateral del muslo respecto a la vertical, en grados.

    Se mide en el plano frontal, solo con (x, y): la abducción vive en ese
    plano, y la profundidad z, que es la componente menos fiable, solo añadiría
    la flexión de cadera. Positivo = el muslo se abre hacia fuera; negativo =
    cruza hacia la línea media. Requiere estar de frente (EXP-002).
    """
    pref, otro = ("left", "right") if lado == "izq" else ("right", "left")
    req = (f"{pref}_hip", f"{pref}_knee", f"{otro}_hip")
    if any(k not in kps for k in req):
        return None
    cadera, rodilla = kps[f"{pref}_hip"], kps[f"{pref}_knee"]
    fuera = cadera.x - kps[f"{otro}_hip"].x
    if abs(fuera) < 1e-9:
        return None
    dx, dy = rodilla.x - cadera.x, rodilla.y - cadera.y
    if math.hypot(dx, dy) < 1e-9:
        return None
    return math.degrees(math.atan2(math.copysign(1.0, fuera) * dx, dy))


def lado_mas_visible(kps: Dict[str, Keypoint], partes: Sequence[str]) -> Optional[str]:
    """`"left"` o `"right"`: el lado cuyos puntos `partes` (p. ej. "hip")
    tienen mayor visibilidad mínima. None si falta algún punto en los dos."""
    mejor, mejor_vis = None, -1.0
    for lado in ("left", "right"):
        nombres = [f"{lado}_{p}" for p in partes]
        if any(n not in kps for n in nombres):
            continue
        vis = confianza_de_terna(kps, nombres)
        if vis > mejor_vis:
            mejor, mejor_vis = lado, vis
    return mejor


PARTES_ALINEACION = ("shoulder", "hip", "ankle")


def alineacion_cadera(kps: Dict[str, Keypoint], usar_z: bool = True,
                      lado: Optional[str] = None) -> Optional[float]:
    """Altura de la cadera respecto a la recta hombro → tobillo, de un lado.

    Distancia vertical con signo de la cadera a esa recta, dividida por la
    distancia hombro-cadera. Positivo = la cadera queda por debajo (hundida);
    negativo = por encima (elevada). Pensada para la plancha, con el cuerpo
    horizontal: de pie la recta es vertical y la medida no significa nada.
    Plano sagital.

    Se calcula con **un** lado (`lado`, o el más visible si no se indica), no
    con los puntos medios: de perfil los dos lados se superponen y el tobillo
    lejano suele quedar tapado. `[F]` En 6 vídeos de perfil su visibilidad
    mediana fue 0,17–0,71, y exigir los dos tobillos dejaba la medida
    evaluable en el 0–19 % de los frames en 5 de ellos (ADR-006 §2.1).
    """
    lado = lado or lado_mas_visible(kps, PARTES_ALINEACION)
    if lado is None:
        return None
    hombro, cadera, tobillo = (_coords(kps[f"{lado}_{p}"], usar_z)
                               for p in PARTES_ALINEACION)
    d = _resta(tobillo, hombro)
    largo2 = _punto(d, d)
    esc = _norma(_resta(hombro, cadera))
    if largo2 < 1e-12 or esc < 1e-6:
        return None
    k = _punto(_resta(cadera, hombro), d) / largo2
    en_recta_y = hombro[1] + k * d[1]
    return (cadera[1] - en_recta_y) / esc


def separacion_pies(kps: Dict[str, Keypoint]) -> Optional[float]:
    """Separación de tobillos dividida por la separación de caderas."""
    req = ("left_ankle", "right_ankle", "left_hip", "right_hip")
    if any(k not in kps for k in req):
        return None
    dt = abs(kps["left_ankle"].x - kps["right_ankle"].x)
    dc = abs(kps["left_hip"].x - kps["right_hip"].x)
    if dc < 1e-9:
        return None
    return dt / dc


# ---------------------------------------------------------------------------
# Confianza
# ---------------------------------------------------------------------------

def confianza_de_terna(kps: Dict[str, Keypoint], nombres: Iterable[str]) -> float:
    """Confianza de una medida = mínimo de la visibilidad de sus keypoints.

    `[R]` El mínimo, no la media. Una medida es tan fiable como su punto peor
    visto: un ángulo de rodilla con el tobillo ocluido no es un ángulo de
    rodilla con 0.66 de confianza, es una medida inválida. Esta elección es la
    que hace que la política de abstención sirva de algo en un gimnasio, donde
    la oclusión por equipamiento y por el propio cuerpo es la norma.
    """
    vals = [kps[n].visibilidad for n in nombres if n in kps]
    if not vals:
        return 0.0
    return min(vals)


# ---------------------------------------------------------------------------
# Construcción de la Observacion
# ---------------------------------------------------------------------------

def observacion_desde_pose(
    muestra: MuestraPose,
    ejercicio_id: str,
    fase: str = "desconocida",
    repeticion: Optional[int] = None,
    angulos_ref: Optional[Dict[str, float]] = None,
) -> Observacion:
    """Convierte una muestra de pose en una `Observacion`.

    Calcula todos los ángulos canónicos calculables y su confianza. Los que no
    se pueden calcular simplemente no aparecen, y el motor los tratará como
    no observados (confianza 0).
    """
    kps = muestra.keypoints
    usar_z = muestra.espacio == "mundo_m"
    angulos: Dict[str, float] = {}
    confianza: Dict[str, float] = {}

    for nombre, terna in ANGULOS_TERNA.items():
        if any(k not in kps for k in terna):
            continue
        pts = [_coords(kps[k], usar_z) for k in terna]
        ang = angulo_entre(pts[0], pts[1], pts[2])
        if ang is None:
            continue
        angulos[nombre] = ang
        confianza[nombre] = confianza_de_terna(kps, terna)

    for nombre, (a, b) in ANGULOS_MEDIOS.items():
        if a in angulos and b in angulos:
            angulos[nombre] = (angulos[a] + angulos[b]) / 2.0
            confianza[nombre] = min(confianza[a], confianza[b])

    conf_tronco = confianza_de_terna(
        kps, ("left_shoulder", "right_shoulder", "left_hip", "right_hip"))
    tronco = inclinacion_tronco(kps, usar_z)
    if tronco is not None:
        angulos["tronco_inclinacion"] = tronco
        confianza["tronco_inclinacion"] = conf_tronco

    rot = rotacion_tronco(kps)
    if rot is not None:
        angulos["rotacion_tronco"] = rot
        confianza["rotacion_tronco"] = conf_tronco
    az = azimut_cadera(kps)
    if az is not None:
        angulos["azimut_cadera"] = az
        confianza["azimut_cadera"] = confianza_de_terna(
            kps, ("left_hip", "right_hip"))

    caderas = ("left_hip", "right_hip")
    hombros = ("left_shoulder", "right_shoulder")
    nuevas = (
        ("oblicuidad_pelvis", oblicuidad_pelvis(kps, usar_z), caderas),
        ("oblicuidad_hombros", oblicuidad_hombros(kps, usar_z), hombros),
        ("inclinacion_lateral", inclinacion_lateral(kps, usar_z), hombros + caderas),
        ("cabeza_adelantada", cabeza_adelantada(kps, usar_z),
         hombros + caderas + ("left_ear", "right_ear")),
        ("abduccion_cadera_izq", abduccion_cadera(kps, "izq"),
         ("left_hip", "left_knee", "right_hip")),
        ("abduccion_cadera_der", abduccion_cadera(kps, "der"),
         ("right_hip", "right_knee", "left_hip")),
    )
    for nombre, valor, implicados in nuevas:
        if valor is not None:
            angulos[nombre] = valor
            confianza[nombre] = confianza_de_terna(kps, implicados)

    distancias: Dict[str, float] = {}
    for lado, suf in (("izq", "left"), ("der", "right")):
        v = desviacion_lateral_rodilla(kps, lado)
        if v is not None:
            distancias[f"valgo_rodilla_{lado}"] = v
            confianza[f"valgo_rodilla_{lado}"] = confianza_de_terna(
                kps, (f"{suf}_hip", f"{suf}_knee", f"{suf}_ankle"))
    sep = separacion_pies(kps)
    if sep is not None:
        distancias["separacion_pies"] = sep
        confianza["separacion_pies"] = confianza_de_terna(
            kps, ("left_ankle", "right_ankle", "left_hip", "right_hip"))
    lado = lado_mas_visible(kps, PARTES_ALINEACION)
    alin = alineacion_cadera(kps, usar_z, lado) if lado else None
    if alin is not None:
        distancias["alineacion_cadera"] = alin
        confianza["alineacion_cadera"] = confianza_de_terna(
            kps, [f"{lado}_{p}" for p in PARTES_ALINEACION])

    return Observacion(
        t_ms=muestra.t_ms,
        ejercicio_id=ejercicio_id,
        angulos=angulos,
        confianza=confianza,
        fase=fase,
        repeticion=repeticion,
        angulos_ref=dict(angulos_ref or {}),
        distancias=distancias,
        orientacion=orientacion_camara(kps),
    )


__all__ = [
    "ANGULOS_TERNA", "ANGULOS_MEDIOS", "PLANO_DE_ANGULO", "KP_REQUERIDOS",
    "angulo_entre", "punto_medio", "escala_corporal", "inclinacion_tronco",
    "orientacion_camara", "desviacion_lateral_rodilla", "separacion_pies",
    "rotacion_tronco", "azimut_cadera",
    "oblicuidad_pelvis", "oblicuidad_hombros", "inclinacion_lateral",
    "cabeza_adelantada", "abduccion_cadera", "alineacion_cadera", "lado_mas_visible",
    "confianza_de_terna", "observacion_desde_pose",
]
