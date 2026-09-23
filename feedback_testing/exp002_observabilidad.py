"""EXP-002 — Observabilidad de cada medida con una sola cámara.

Pregunta
--------
¿Cuánto error introduce medir en el plano de imagen (2D) en lugar de en 3D,
en función de la orientación del sujeto respecto a la cámara, y a partir de
qué orientación ese error supera el umbral de las reglas de ESTELA?

De la respuesta depende una decisión concreta: **si hace falta una segunda
cámara, o basta con una sola más una política de abstención por plano.**

Método
------
1. Se definen esqueletos 3D sintéticos en poses representativas de los cinco
   ejercicios candidatos.
2. Se rota el esqueleto alrededor del eje vertical entre 0° (de frente) y 90°
   (de perfil), en pasos de 5°.
3. Se calcula cada medida canónica dos veces: sobre las coordenadas 3D
   (verdad de referencia) y sobre su **proyección ortográfica** al plano de
   imagen (lo que ve una cámara sin información de profundidad).
4. Se reporta el error absoluto por medida y orientación, y se compara con el
   umbral de severidad «moderada» de cada regla.

Alcance y límites — leer antes de citar cualquier cifra
-------------------------------------------------------
`[I]` Esto mide **el error geométrico de la proyección**, no el error de un
estimador de pose concreto. Es el **peor caso**: supone que la profundidad es
inutilizable. Un modelo que entregue *world landmarks* 3D fiables tendrá un
error menor.

`[?]` Cuánto menor es una pregunta abierta que este experimento **no**
responde: exige comparar el estimador elegido contra una verdad 3D
(por ejemplo MOCAP), que el proyecto no tiene.

`[?]` Tampoco modela oclusión por equipamiento del gimnasio, ni error de
detección de keypoints, ni ruido temporal. Esos degradan la medida por vías
distintas y se suman a esta.

`[F]` La proyección es ortográfica. Una cámara real es proyectiva; a las
distancias de trabajo habituales (2–4 m) la diferencia es pequeña, pero no
nula. No se reporta esa diferencia porque no se ha medido.
"""

from __future__ import annotations

import math
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feedback.contrato import Keypoint, MuestraPose, Plano
from feedback.motor import geometria as g
from feedback.motor.skill import Skill, cargar_skills, directorio_skills

ORIENTACIONES = list(range(0, 95, 5))

#: Poses sintéticas. Coordenadas en metros, origen en el centro de la cadera.
#: Convención: x = lateral (derecha positiva), y = vertical **hacia abajo**,
#: z = profundidad (hacia la cámara positiva). Es la convención que usa el
#: resto del módulo.
#: `[R]` Son poses plausibles construidas a mano, no capturas reales. Sirven
#: para medir el efecto de la proyección, que es puramente geométrico y no
#: depende de que la pose sea antropométricamente exacta.
POSES: Dict[str, Dict[str, Tuple[float, float, float]]] = {
    "de_pie": {
        "left_hip": (-0.10, 0.00, 0.00), "right_hip": (0.10, 0.00, 0.00),
        "left_shoulder": (-0.18, -0.50, 0.00), "right_shoulder": (0.18, -0.50, 0.00),
        "left_elbow": (-0.20, -0.25, 0.00), "right_elbow": (0.20, -0.25, 0.00),
        "left_wrist": (-0.21, 0.00, 0.00), "right_wrist": (0.21, 0.00, 0.00),
        "left_knee": (-0.10, 0.45, 0.00), "right_knee": (0.10, 0.45, 0.00),
        "left_ankle": (-0.10, 0.90, 0.00), "right_ankle": (0.10, 0.90, 0.00),
    },
    "sentadilla_fondo": {
        "left_hip": (-0.11, 0.00, 0.00), "right_hip": (0.11, 0.00, 0.00),
        "left_shoulder": (-0.18, -0.42, 0.22), "right_shoulder": (0.18, -0.42, 0.22),
        "left_elbow": (-0.22, -0.20, 0.30), "right_elbow": (0.22, -0.20, 0.30),
        "left_wrist": (-0.24, -0.05, 0.42), "right_wrist": (0.24, -0.05, 0.42),
        "left_knee": (-0.13, 0.28, 0.28), "right_knee": (0.13, 0.28, 0.28),
        "left_ankle": (-0.11, 0.62, -0.02), "right_ankle": (0.11, 0.62, -0.02),
    },
    "brazos_arriba": {
        "left_hip": (-0.10, 0.00, 0.00), "right_hip": (0.10, 0.00, 0.00),
        "left_shoulder": (-0.18, -0.50, 0.00), "right_shoulder": (0.18, -0.50, 0.00),
        "left_elbow": (-0.30, -0.72, 0.00), "right_elbow": (0.30, -0.72, 0.00),
        "left_wrist": (-0.36, -0.95, 0.00), "right_wrist": (0.36, -0.95, 0.00),
        "left_knee": (-0.10, 0.45, 0.00), "right_knee": (0.10, 0.45, 0.00),
        "left_ankle": (-0.12, 0.90, 0.00), "right_ankle": (0.12, 0.90, 0.00),
    },
    "rodilla_izq_arriba": {
        "left_hip": (-0.10, 0.00, 0.00), "right_hip": (0.10, 0.00, 0.00),
        "left_shoulder": (-0.18, -0.50, 0.00), "right_shoulder": (0.18, -0.50, 0.00),
        "left_elbow": (-0.22, -0.28, 0.12), "right_elbow": (0.22, -0.28, -0.12),
        "left_wrist": (-0.24, -0.05, 0.22), "right_wrist": (0.24, -0.05, -0.22),
        "left_knee": (-0.11, 0.02, 0.32), "right_knee": (0.10, 0.45, 0.00),
        "left_ankle": (-0.11, 0.38, 0.30), "right_ankle": (0.10, 0.90, 0.00),
    },
    "jumping_jack_abierto": {
        "left_hip": (-0.10, 0.00, 0.00), "right_hip": (0.10, 0.00, 0.00),
        "left_shoulder": (-0.18, -0.50, 0.00), "right_shoulder": (0.18, -0.50, 0.00),
        "left_elbow": (-0.34, -0.70, 0.00), "right_elbow": (0.34, -0.70, 0.00),
        "left_wrist": (-0.42, -0.92, 0.00), "right_wrist": (0.42, -0.92, 0.00),
        "left_knee": (-0.22, 0.44, 0.00), "right_knee": (0.22, 0.44, 0.00),
        "left_ankle": (-0.32, 0.86, 0.00), "right_ankle": (0.32, 0.86, 0.00),
    },
}

#: Medidas angulares evaluadas (grados) y medidas de distancia (normalizadas).
MEDIDAS_ANGULARES = ("rodilla_izq", "rodilla_der", "cadera_izq", "cadera_der",
                     "codo_izq", "codo_der", "hombro_izq", "hombro_der",
                     "tronco_inclinacion")
MEDIDAS_DISTANCIA = ("valgo_rodilla_izq", "valgo_rodilla_der", "separacion_pies")

#: Qué poses son pertinentes para cada ejercicio. Evaluar la regla de un
#: ejercicio sobre la pose de otro no dice nada útil: el error de proyección
#: del hombro en una sentadilla no condiciona la elevación de brazos.
POSES_POR_EJERCICIO: Dict[str, Tuple[str, ...]] = {
    "sentadilla": ("de_pie", "sentadilla_fondo"),
    "elevacion_brazos": ("de_pie", "brazos_arriba"),
    "jumping_jacks": ("de_pie", "jumping_jack_abierto"),
    "marcha_rodillas": ("de_pie", "rodilla_izq_arriba"),
    "rotacion_tronco": ("de_pie",),
}


def rotar(p: Tuple[float, float, float], grados: float) -> Tuple[float, float, float]:
    """Rotación alrededor del eje vertical (y)."""
    t = math.radians(grados)
    x, y, z = p
    return (x * math.cos(t) + z * math.sin(t), y,
            -x * math.sin(t) + z * math.cos(t))


def _kps(pose: Dict[str, Tuple[float, float, float]], grados: float,
         con_z: bool) -> Dict[str, Keypoint]:
    out = {}
    for nombre, p in pose.items():
        x, y, z = rotar(p, grados)
        out[nombre] = Keypoint(x=x, y=y, z=(z if con_z else None), visibilidad=1.0)
    return out


def _medidas(kps: Dict[str, Keypoint], usar_z: bool) -> Dict[str, float]:
    m: Dict[str, float] = {}
    for nombre, terna in g.ANGULOS_TERNA.items():
        if any(k not in kps for k in terna):
            continue
        pts = []
        for k in terna:
            kp = kps[k]
            pts.append((kp.x, kp.y, kp.z) if (usar_z and kp.z is not None)
                       else (kp.x, kp.y))
        a = g.angulo_entre(*pts)
        if a is not None:
            m[nombre] = a
    t = g.inclinacion_tronco(kps, usar_z)
    if t is not None:
        m["tronco_inclinacion"] = t
    for lado in ("izq", "der"):
        v = g.desviacion_lateral_rodilla(kps, lado)
        if v is not None:
            m[f"valgo_rodilla_{lado}"] = v
    for nombre, (a, b) in g.ANGULOS_MEDIOS.items():
        if a in m and b in m:
            m[nombre] = (m[a] + m[b]) / 2.0
    s = g.separacion_pies(kps)
    if s is not None:
        m["separacion_pies"] = s
    return m


def barrido(nombres_pose: Optional[Sequence[str]] = None) -> Dict[str, List[List[float]]]:
    """errores[medida][i] = lista de |error| en la orientación i, una por pose.

    Una pose en la que la medida no es calculable (denominador degenerado)
    simplemente no aporta valor a esa celda; esa ausencia es por sí misma
    informativa y se reporta aparte.
    """
    n = len(ORIENTACIONES)
    errores: Dict[str, List[List[float]]] = {}
    seleccion = [POSES[k] for k in (nombres_pose or list(POSES))]
    for pose in seleccion:
        verdad = _medidas(_kps(pose, 0.0, con_z=True), usar_z=True)
        for i, grados in enumerate(ORIENTACIONES):
            proyectado = _medidas(_kps(pose, grados, con_z=False), usar_z=False)
            for medida, v_verdad in verdad.items():
                celdas = errores.setdefault(medida, [[] for _ in range(n)])
                if medida in proyectado:
                    celdas[i].append(abs(proyectado[medida] - v_verdad))
    return errores


def error_max_por_orientacion(errores) -> Dict[str, List[float]]:
    """Peor pose para cada medida y orientación. Es la cifra que importa: la
    salvaguarda tiene que aguantar el caso malo, no el promedio.

    Una celda sin ninguna pose calculable se reporta como infinito: la medida
    no existe en esa orientación, que a efectos de la regla es tan malo como
    un error enorme.
    """
    out: Dict[str, List[float]] = {}
    for medida, celdas in errores.items():
        out[medida] = [max(c) if c else float("inf") for c in celdas]
    return out


def tolerancia_util(serie: Sequence[float], umbral: float,
                    ideal: int) -> Optional[int]:
    """Desviación máxima respecto al plano ideal de la regla en la que el
    error se mantiene por debajo del umbral de forma continua.

    Se recorre desde la orientación ideal hacia fuera. Devuelve None si el
    umbral ya se supera en la propia orientación ideal: eso significa que la
    medida no sirve ni en la mejor de sus posiciones.
    """
    if ideal not in ORIENTACIONES:
        return None
    i0 = ORIENTACIONES.index(ideal)
    if serie[i0] > umbral:
        return None
    paso = ORIENTACIONES[1] - ORIENTACIONES[0]
    tol = 0
    for d in range(1, len(ORIENTACIONES)):
        ok = True
        visto = False
        for j in (i0 - d, i0 + d):
            if 0 <= j < len(ORIENTACIONES):
                visto = True
                if serie[j] > umbral:
                    ok = False
        if not visto or not ok:
            break
        tol = d * paso
    return tol


def umbral_de_regla(regla) -> Optional[float]:
    """Umbral de severidad «moderada» de una regla; a falta de él, el menor
    declarado. Es el margen de error que la regla puede tolerar antes de que
    un error de medida se confunda con un error de ejecución."""
    if not regla.umbrales_severidad:
        return None
    return regla.umbrales_severidad.get(
        "moderada", min(regla.umbrales_severidad.values()))


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------

def informe(skills: Dict[str, Skill]) -> str:
    errores = barrido()
    peor = error_max_por_orientacion(errores)
    peor_por_ejercicio = {
        ej: error_max_por_orientacion(barrido(poses))
        for ej, poses in POSES_POR_EJERCICIO.items()
    }

    L: List[str] = []
    L.append("# EXP-002 — Observabilidad monocular por orientación")
    L.append("")
    L.append(f"- Poses sintéticas: {len(POSES)} ({', '.join(POSES)})")
    L.append(f"- Orientaciones: {ORIENTACIONES[0]}° a {ORIENTACIONES[-1]}° "
             f"en pasos de {ORIENTACIONES[1] - ORIENTACIONES[0]}°")
    L.append("- Verdad de referencia: la misma medida calculada en 3D.")
    L.append("- Medida observada: proyección ortográfica al plano de imagen "
             "(peor caso, sin profundidad utilizable).")
    L.append("")
    L.append("## Error absoluto máximo sobre todas las poses")
    L.append("")
    cols = [gr for gr in ORIENTACIONES if gr % 15 == 0]
    idx = [ORIENTACIONES.index(c) for c in cols]
    L.append("| Medida | Plano declarado | " +
             " | ".join(f"{c}°" for c in cols) + " |")
    L.append("|---|---|" + "---|" * len(cols))
    for medida in list(MEDIDAS_ANGULARES) + list(MEDIDAS_DISTANCIA):
        if medida not in peor:
            continue
        plano = g.PLANO_DE_ANGULO.get(medida, Plano.CUALQUIERA).value
        unidad = "" if medida in MEDIDAS_ANGULARES else ""
        def _f(v: float) -> str:
            if v == float("inf"):
                return "n/c"
            return f"{v:.1f}" if medida in MEDIDAS_ANGULARES else f"{v:.3f}"
        fila = " | ".join(_f(peor[medida][i]) for i in idx)
        L.append(f"| `{medida}` | {plano} | {fila} |")
    L.append("")
    L.append("Los ángulos están en grados; `valgo_*` y `separacion_pies` en "
             "unidades normalizadas por la escala corporal.")
    L.append("")

    L.append("## Orientación máxima utilizable por regla")
    L.append("")
    L.append("Para cada regla: hasta qué desviación respecto a su plano ideal "
             "el error de proyección se mantiene por debajo del umbral de "
             "severidad «moderada» de esa regla. Más allá, un error de medida "
             "es indistinguible de un error de ejecución.")
    L.append("")
    L.append("Cada regla se evalúa **solo sobre las poses de su ejercicio** "
             "(ver `POSES_POR_EJERCICIO`).")
    L.append("")
    L.append("| Ejercicio | Regla | Medida | Plano | Umbral moderada | "
             "Orientación máx. utilizable |")
    L.append("|---|---|---|---|---|---|")
    resumen: List[Tuple[str, str, Optional[int]]] = []
    for skill in skills.values():
        peor_ej = peor_por_ejercicio.get(skill.skill_id, peor)
        for regla in skill.reglas:
            nombres = regla.medida.angulos_implicados()
            if not nombres:
                continue
            medida = nombres[0]
            if medida not in peor_ej:
                estado = "no medible aquí"
                resumen.append((skill.skill_id, regla.error_id, None))
                L.append(f"| {skill.skill_id} | `{regla.error_id}` | "
                         f"`{medida}` | {regla.plano.value} | — | {estado} |")
                continue
            umbral = umbral_de_regla(regla)
            if umbral is None:
                L.append(f"| {skill.skill_id} | `{regla.error_id}` | "
                         f"`{medida}` | {regla.plano.value} | — | sin umbral |")
                continue
            ideal = {"frontal": 0, "sagital": 90}.get(regla.plano.value)
            tol = (None if ideal is None
                   else tolerancia_util(peor_ej[medida], umbral, ideal))
            if ideal is None:
                texto = "sin plano ideal de una cámara"
            elif tol is None:
                texto = "**no utilizable en ninguna orientación**"
            elif tol >= 90:
                texto = "cualquiera"
            else:
                texto = f"±{tol}° alrededor de {ideal}°"
            resumen.append((skill.skill_id, regla.error_id, tol))
            fmt = f"{umbral:.0f}" if medida in MEDIDAS_ANGULARES else f"{umbral:.3f}"
            L.append(f"| {skill.skill_id} | `{regla.error_id}` | `{medida}` | "
                     f"{regla.plano.value} | {fmt} | {texto} |")
    L.append("")

    L.append("## ¿Existe una sola orientación que sirva para todo el ejercicio?")
    L.append("")
    L.append("Para cada ejercicio se busca el conjunto de orientaciones en las "
             "que **todas** sus reglas medibles se mantienen por debajo de su "
             "umbral. Un conjunto vacío significa que una sola cámara fija no "
             "puede cubrir ese ejercicio completo.")
    L.append("")
    L.append("| Ejercicio | Reglas medibles | Orientaciones válidas para todas | "
             "Reglas que se pierden en la mejor orientación |")
    L.append("|---|---|---|---|")
    for skill in skills.values():
        peor_ej = peor_por_ejercicio.get(skill.skill_id, peor)
        medibles = []
        for regla in skill.reglas:
            nombres = regla.medida.angulos_implicados()
            umbral = umbral_de_regla(regla)
            if not nombres or umbral is None or nombres[0] not in peor_ej:
                continue
            medibles.append((regla, nombres[0], umbral))
        if not medibles:
            L.append(f"| {skill.skill_id} | 0 | — | todas |")
            continue
        validas = []
        for i, grados in enumerate(ORIENTACIONES):
            if all(peor_ej[m][i] <= u for _, m, u in medibles):
                validas.append(grados)
        # mejor orientación: la que deja fuera menos reglas
        mejor, perdidas_min = None, None
        for i, grados in enumerate(ORIENTACIONES):
            perdidas = [r.error_id for r, m, u in medibles if peor_ej[m][i] > u]
            if perdidas_min is None or len(perdidas) < len(perdidas_min):
                mejor, perdidas_min = grados, perdidas
        rango = ("ninguna" if not validas
                 else f"{validas[0]}°–{validas[-1]}°" if len(validas) > 1
                 else f"{validas[0]}°")
        perdidas_txt = ("ninguna" if not perdidas_min
                        else ", ".join(f"`{p}`" for p in perdidas_min))
        L.append(f"| {skill.skill_id} | {len(medibles)} / {len(skill.reglas)} | "
                 f"{rango} | (a {mejor}°) {perdidas_txt} |")
    L.append("")
    L.append("## Lectura")
    L.append("")
    L.append("- La columna de la derecha es, literalmente, el valor que debería "
             "tener `tolerancia_orientacion_grados` en la política de silencio "
             "de cada `skill`. Hoy ese valor está puesto a 30° por defecto en "
             "todos los archivos, sin respaldo.")
    L.append("- Las medidas del plano **transversal** (`rotacion_tronco`, "
             "`azimut_cadera`) no aparecen: no se pueden calcular sin "
             "profundidad. Con una sola cámara dependen por completo de la `z` "
             "estimada, y la salvaguarda de plano del motor **no las protege**.")
    L.append("- Cuatro de los cinco ejercicios admiten una orientación única "
             "que cubre todas sus reglas. La sentadilla no: sus reglas del "
             "plano frontal (valgo) y las del sagital (profundidad, tronco) "
             "no comparten ninguna orientación válida.")
    L.append("- El ancho de la ventana válida depende del umbral de la regla, "
             "y los umbrales de hoy son provisionales. Recalcular este "
             "experimento es obligatorio después de calibrarlos.")
    L.append("")
    return "\n".join(L)


def main() -> int:
    skills = cargar_skills(directorio_skills())
    txt = informe(skills)
    destino = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "resultados", "EXP-002-observabilidad.md")
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
