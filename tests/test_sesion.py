"""Flujo completo de la sesión con un estimador falso (sin cámara ni modelo).

Se sintetizan esqueletos 3D para probar el flujo de sesión sin cámara ni modelo.
La plancha se prueba aparte, con un esqueleto horizontal.
"""

import math

import numpy as np
import pytest

from estela.pose.estimador import ResultadoPose
from estela.pose.landmarks import NOMBRES_MEDIAPIPE, muestra_desde_arrays
from estela import config
from estela.sesion.rutina import (RutinaInvalida, cargar_catalogo, cargar_rutina,
                                  rutina_de_un_ejercicio, rutina_desde_dict)
from estela.sesion.sesion import (AVISO_PAUSA, AVISO_REANUDA, Sesion,
                                  frases_de_rutina)
from estela.voz.cola import PRIORIDAD_AVISO

IDX = {n: i for i, n in enumerate(NOMBRES_MEDIAPIPE)}


def esqueleto_perfil(rodilla_grados: float, tronco_grados: float) -> np.ndarray:
    """Sujeto de perfil (mira hacia +x), coordenadas de mundo con y hacia abajo.

    Los hombros se separan en z (profundidad): así `orientacion_camara` ≈ 90°.
    """
    pts = np.zeros((33, 4), np.float32)
    pts[:, 3] = 0.99
    flex = math.radians(180 - rodilla_grados)
    muslo = pierna = 0.45
    # Postura de zancada: la izquierda atrás (s = -1), la derecha delante
    # (s = +1); así los tobillos quedan separados (longitud_paso ≈ 0,8).
    for lado, dz, s in (("left", 0.1, -1.0), ("right", -0.1, 1.0)):
        cadera = np.array([0.0, 0.0, dz])
        # el muslo se inclina hacia delante a medida que se flexiona la rodilla
        muslo_ang = flex / 2 + s * 0.4
        rodilla = cadera + [muslo * math.sin(muslo_ang), muslo * math.cos(muslo_ang), 0]
        tobillo = rodilla + [pierna * math.sin(muslo_ang - flex),
                             pierna * math.cos(muslo_ang - flex), 0]
        t = math.radians(tronco_grados)
        hombro = cadera + [0.5 * math.sin(t), -0.5 * math.cos(t), 0]
        codo = hombro + [0.0, 0.28, 0]
        muneca = codo + [0.0, 0.25, 0]
        for nombre, p in (("hip", cadera), ("knee", rodilla), ("ankle", tobillo),
                          ("shoulder", hombro), ("elbow", codo), ("wrist", muneca)):
            pts[IDX[f"{lado}_{nombre}"], :3] = p
    return pts


class EstimadorFalso:
    def __init__(self, tronco: float):
        self.tronco = tronco

    def estimar(self, frame, t_ms):
        rodilla = float(frame)                  # el "frame" lleva el ángulo
        if math.isnan(rodilla):
            return ResultadoPose(None, None, 1.0)
        mundo = esqueleto_perfil(rodilla, self.tronco if rodilla < 150 else 5.0)
        return ResultadoPose(muestra_desde_arrays(t_ms, mundo, mundo), mundo, 1.0)


class VozFalsa:
    def __init__(self):
        self.dichas = []

    def decir(self, texto, prioridad=0):
        self.dichas.append((texto, prioridad))
        return True

    @property
    def correcciones(self):
        return [t for t, p in self.dichas if p != PRIORIDAD_AVISO]


def correr(sesion, angulos, dt_ms=100):
    estados = []
    for i, a in enumerate(angulos):
        estados.append(sesion.procesar(a, i * dt_ms))
    return estados


@pytest.fixture(scope="module")
def catalogo():
    return cargar_catalogo()


def test_sin_persona_avisa_y_no_rompe(catalogo):
    voz = VozFalsa()
    s = Sesion(rutina_de_un_ejercicio("jumping_jacks", 5, catalogo), catalogo,
               EstimadorFalso(tronco=10), voz)
    estados = correr(s, [float("nan")] * 30)
    assert estados[-1].aviso and not estados[-1].persona
    assert s.resumen()["frames_sin_persona"] == 30


def test_orientacion_incorrecta_se_avisa_por_voz(catalogo):
    """Jumping jacks exige frente; el esqueleto sintético está de perfil."""
    voz = VozFalsa()
    s = Sesion(rutina_de_un_ejercicio("jumping_jacks", 5, catalogo), catalogo,
               EstimadorFalso(tronco=10), voz)
    estados = correr(s, [170.0] * 40)
    assert estados[-1].aviso == "Colócate de frente a la cámara."
    assert ("Colócate de frente a la cámara.", PRIORIDAD_AVISO) in voz.dichas


def test_ejercicio_retirado_se_rechaza(catalogo):
    """ADR-005: sentadilla, elevación de brazos y rotación de tronco salieron."""
    for retirado in ("sentadilla", "elevacion_brazos", "rotacion_tronco"):
        with pytest.raises(RutinaInvalida):
            rutina_de_un_ejercicio(retirado, 5, catalogo)


# ---------------------------------------------------------------------------
# Plancha: postura mantenida, objetivo en segundos
# ---------------------------------------------------------------------------

def esqueleto_plancha(hundimiento: float = 0.0) -> np.ndarray:
    """Cuerpo horizontal de perfil (cabeza hacia +x), y hacia abajo.

    Con `hundimiento` = 0 la cadera queda sobre la recta hombro-tobillo y la
    cabeza en la prolongación del tronco.
    """
    pts = np.zeros((33, 4), np.float32)
    pts[:, 3] = 0.99
    for lado, dz in (("left", 0.12), ("right", -0.12)):
        for nombre, p in (("shoulder", (0.5, -0.05, dz)),
                          ("elbow", (0.5, 0.25, dz)), ("wrist", (0.75, 0.25, dz)),
                          ("hip", (0.0, -0.0107 + hundimiento, dz)),
                          ("knee", (-0.45, 0.0247, dz)), ("ankle", (-0.9, 0.06, dz)),
                          ("ear", (0.7, -0.0657, dz * 0.6))):
            pts[IDX[f"{lado}_{nombre}"], :3] = p
    return pts


class EstimadorPlancha:
    """El «frame» es el hundimiento de la cadera en metros (NaN = sin persona)."""

    def estimar(self, frame, t_ms):
        mundo = esqueleto_plancha(float(frame))
        return ResultadoPose(muestra_desde_arrays(t_ms, mundo, mundo), mundo, 1.0)


def test_plancha_cuenta_segundos_y_avanza(catalogo):
    voz = VozFalsa()
    s = Sesion(rutina_de_un_ejercicio("plancha", 6, catalogo), catalogo,
               EstimadorPlancha(), voz)
    estados = correr(s, [0.0] * 100)              # 10 s a 10 fps
    assert ("Ahora, plancha. 6 segundos. Colócate de perfil a la cámara.",
            PRIORIDAD_AVISO) in voz.dichas
    assert s.terminada
    assert estados[30].unidad == "segundos" and estados[30].fase == "mantenimiento"
    paso = s.resumen()["pasos"][0]
    assert paso["unidad"] == "segundos" and paso["completadas"] >= 6
    assert [m for m in paso["mensajes"] if m["error_id"]] == []


def test_plancha_cadera_hundida_se_corrige_tras_dos_bloques(catalogo):
    voz = VozFalsa()
    s = Sesion(rutina_de_un_ejercicio("plancha", 99, catalogo), catalogo,
               EstimadorPlancha(), voz)
    correr(s, [0.08] * 150)                       # 15 s con la cadera caída
    msgs = s.resumen()["pasos"][0]["mensajes"]
    assert {m["error_id"] for m in msgs} == {"cadera_hundida"}
    # bloques de 5 s y repeticiones_evidencia = 2: nunca en el primer bloque
    assert all(m["repeticion"] >= 2 for m in msgs)
    assert any("caderas" in t.lower() for t in voz.correcciones)


class EstimadorPlanchaConHuecos(EstimadorPlancha):
    def estimar(self, frame, t_ms):
        if math.isnan(float(frame)):
            return ResultadoPose(None, None, 1.0)
        return super().estimar(frame, t_ms)


def test_plancha_no_suma_el_tiempo_sin_persona(catalogo):
    """3 s en posición, 3 s sin persona, 3 s en posición: el hueco no cuenta."""
    s = Sesion(rutina_de_un_ejercicio("plancha", 99, catalogo), catalogo,
               EstimadorPlanchaConHuecos(), VozFalsa())
    estados = correr(s, [0.0] * 30 + [float("nan")] * 30 + [0.0] * 30)
    assert estados[-1].completadas <= 5            # ~2 s + ~3 s, no ~8 s


def test_plancha_quieta_en_posicion_no_se_pausa(catalogo):
    voz = VozFalsa()
    s = Sesion(rutina_de_un_ejercicio("plancha", 99, catalogo), catalogo,
               EstimadorPlancha(), voz)
    estados = correr(s, [0.0] * 200)               # 20 s sin moverse
    assert not any(e.pausada for e in estados)
    assert not any(t.startswith("Pausa") for t, _ in voz.dichas)


# ---------------------------------------------------------------------------
# Pausa por inactividad (T22.b): pausar nunca reinicia los contadores
# ---------------------------------------------------------------------------

def test_tras_la_pausa_no_retoma_si_vuelve_mal_orientada(catalogo):
    """Jumping jacks pide frente; el esqueleto sintético vuelve de perfil."""
    voz = VozFalsa()
    s = Sesion(rutina_de_un_ejercicio("jumping_jacks", 5, catalogo), catalogo,
               EstimadorFalso(tronco=10), voz)
    estados = correr(s, [float("nan")] * 60 + [170.0] * 40)
    assert estados[-1].pausada
    assert estados[-1].aviso == "Colócate de frente a la cámara."
    assert (AVISO_REANUDA, PRIORIDAD_AVISO) not in voz.dichas


def test_la_rutina_por_defecto_carga_los_ejercicios(catalogo):
    rutina = cargar_rutina(config.RUTINAS / "calentamiento_basico.json", catalogo)
    ids = [p.skill_id for p in rutina.pasos]
    assert ids == ["jumping_jacks", "abduccion_cadera_izq", "abduccion_cadera_der",
                   "marcha_rodillas", "plancha"]
    plancha = rutina.pasos[-1]
    assert catalogo[plancha.skill_id].unidad == "segundos" and plancha.repeticiones == 20