"""Flujo completo de la sesión con un estimador falso (sin cámara ni modelo).

Se sintetizan esqueletos 3D de perfil haciendo sentadillas: con el tronco
recto no debe haber correcciones; con el tronco muy inclinado el motor debe
hablar tras las repeticiones de evidencia, y la rutina debe avanzar al
alcanzar el objetivo.
"""

import math

import numpy as np
import pytest

from estela.pose.estimador import ResultadoPose
from estela.pose.landmarks import NOMBRES_MEDIAPIPE, muestra_desde_arrays
from estela.sesion.rutina import (RutinaInvalida, cargar_catalogo,
                                  rutina_de_un_ejercicio, rutina_desde_dict)
from estela.sesion.sesion import Sesion, frases_de_rutina
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
    for lado, dz in (("left", 0.1), ("right", -0.1)):
        cadera = np.array([0.0, 0.0, dz])
        # el muslo se inclina hacia delante a medida que se flexiona la rodilla
        rodilla = cadera + [muslo * math.sin(flex / 2), muslo * math.cos(flex / 2), 0]
        tobillo = rodilla + [-pierna * math.sin(flex / 2), pierna * math.cos(flex / 2), 0]
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


def secuencia_sentadillas(n, minimo=80):
    una = list(np.linspace(170, minimo, 15)) + list(np.linspace(minimo, 170, 15)) + [170] * 10
    return una * n


def correr(sesion, angulos, dt_ms=100):
    estados = []
    for i, a in enumerate(angulos):
        estados.append(sesion.procesar(a, i * dt_ms))
    return estados


@pytest.fixture(scope="module")
def catalogo():
    return cargar_catalogo()


def test_sentadillas_correctas_se_cuentan_sin_corregir(catalogo):
    voz = VozFalsa()
    s = Sesion(rutina_de_un_ejercicio("sentadilla", 99, catalogo), catalogo,
               EstimadorFalso(tronco=15), voz)
    estados = correr(s, secuencia_sentadillas(5))
    assert estados[-1].completadas == 5
    assert voz.correcciones == []


def test_tronco_inclinado_produce_feedback_hablado(catalogo):
    voz = VozFalsa()
    s = Sesion(rutina_de_un_ejercicio("sentadilla", 99, catalogo), catalogo,
               EstimadorFalso(tronco=70), voz)
    correr(s, secuencia_sentadillas(5))
    assert voz.correcciones, "el motor debía corregir el tronco"
    assert any("tronco" in t.lower() or "pecho" in t.lower() for t in voz.correcciones)
    msgs = s.resumen()["pasos"][0]["mensajes"]
    # repeticiones_evidencia = 2: nunca en la primera repetición
    assert all(m["repeticion"] >= 2 for m in msgs)
    assert {m["error_id"] for m in msgs} == {"tronco_muy_inclinado"}


def test_la_rutina_avanza_al_alcanzar_el_objetivo(catalogo):
    voz = VozFalsa()
    rutina = rutina_desde_dict({"pasos": [
        {"skill_id": "sentadilla", "repeticiones": 2},
        {"skill_id": "sentadilla", "repeticiones": 1}]}, catalogo)
    s = Sesion(rutina, catalogo, EstimadorFalso(tronco=10), voz)
    correr(s, secuencia_sentadillas(3))
    assert s.terminada
    avisos = [t for t, p in voz.dichas if p == PRIORIDAD_AVISO]
    assert avisos[0].startswith("Ahora, sentadilla. 2 repeticiones")
    assert avisos[-1] == "Rutina terminada. Buen trabajo."
    r = s.resumen()
    assert [p["completadas"] for p in r["pasos"]] == [2, 1]


def test_sin_persona_avisa_y_no_rompe(catalogo):
    voz = VozFalsa()
    s = Sesion(rutina_de_un_ejercicio("sentadilla", 5, catalogo), catalogo,
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


def test_el_resumen_no_contiene_datos_biometricos(catalogo):
    s = Sesion(rutina_de_un_ejercicio("sentadilla", 5, catalogo), catalogo,
               EstimadorFalso(tronco=10), VozFalsa())
    correr(s, secuencia_sentadillas(1))
    texto = str(s.resumen())
    assert "keypoints" not in texto and "landmarks" not in texto


def test_rotacion_tronco_se_rechaza_en_sesion(catalogo):
    with pytest.raises(RutinaInvalida):
        rutina_de_un_ejercicio("rotacion_tronco", 5, catalogo)


def test_frases_precalculables_incluyen_plantillas(catalogo):
    rutina = rutina_de_un_ejercicio("sentadilla", 5, catalogo)
    frases = frases_de_rutina(rutina, catalogo)
    assert "Ahora, sentadilla. 5 repeticiones. Colócate de perfil a la cámara." in frases
    assert any("rodilla" in f.lower() for f in frases)
    assert len(frases) > 20


def test_articulaciones_fuera_de_encuadre_piden_alejarse(catalogo):
    """Persona detectada pero rodillas con visibilidad baja (tobillos fuera)."""
    class EstimadorPiernasOcultas(EstimadorFalso):
        def estimar(self, frame, t_ms):
            mundo = esqueleto_perfil(float(frame), 10.0)
            for n in ("knee", "ankle"):
                for lado in ("left", "right"):
                    mundo[IDX[f"{lado}_{n}"], 3] = 0.2
            return ResultadoPose(muestra_desde_arrays(t_ms, mundo, mundo), mundo, 1.0)

    voz = VozFalsa()
    s = Sesion(rutina_de_un_ejercicio("sentadilla", 5, catalogo), catalogo,
               EstimadorPiernasOcultas(tronco=10), voz)
    estados = correr(s, secuencia_sentadillas(2))
    assert estados[-1].completadas == 0            # no cuenta a ciegas
    assert estados[-1].aviso == "Aléjate un poco: necesito verte el cuerpo entero."
    assert sum(1 for t, _ in voz.dichas if t.startswith("Aléjate")) == 1
