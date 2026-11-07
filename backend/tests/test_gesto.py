"""Gesto de pausa (brazo derecho arriba 3 s) y navegación entre ejercicios."""

import numpy as np
import pytest

from estela.aplicacion.gesto import GESTO_PAUSA_S, DetectorGesto, brazo_derecho_arriba
from estela.aplicacion.pausa import USUARIA
from estela.aplicacion.puertos import ResultadoPose
from estela.aplicacion.rutina import cargar_catalogo, rutina_de_un_ejercicio, rutina_desde_dict
from estela.aplicacion.sesion import AVISO_PAUSA, AVISO_REANUDA, Sesion
from estela.adaptadores.pose.landmarks import muestra_desde_arrays

from tests.test_sesion import IDX, EstimadorFalso, VozFalsa, esqueleto_perfil

# ---------------------------------------------------------------------------
# Detector, con landmarks de imagen (y hacia abajo)
# ---------------------------------------------------------------------------


def puntos(derecho=True, izquierdo=False, vis_muneca=0.99):
    p = np.zeros((33, 4), np.float32)
    p[:, 3] = 0.99
    p[0, :2] = (0.5, 0.2)                                  # nariz
    for lado, x, arriba in (("left", 0.6, izquierdo), ("right", 0.4, derecho)):
        p[IDX[f"{lado}_shoulder"], :2] = (x, 0.35)
        p[IDX[f"{lado}_elbow"], :2] = (x, 0.22 if arriba else 0.5)
        p[IDX[f"{lado}_wrist"], :2] = (x, 0.08 if arriba else 0.65)
    p[IDX["right_wrist"], 3] = vis_muneca
    return p


def test_reconoce_solo_el_brazo_derecho_arriba():
    assert brazo_derecho_arriba(puntos())
    assert not brazo_derecho_arriba(puntos(derecho=False))
    assert not brazo_derecho_arriba(puntos(derecho=False, izquierdo=True))
    # los dos arriba es un jumping jack, no el gesto
    assert not brazo_derecho_arriba(puntos(izquierdo=True))
    assert not brazo_derecho_arriba(puntos(vis_muneca=0.2))
    assert not brazo_derecho_arriba(None)


def mantener(det, desde_ms, hasta_ms, pts, dt=100):
    return [t for t in range(desde_ms, hasta_ms, dt) if det.actualizar(t, pts)]


def test_dispara_una_vez_a_los_4_s_y_espera_a_que_baje_el_brazo():
    det = DetectorGesto()
    disparos = mantener(det, 0, 10_000, puntos())
    assert disparos == [int(GESTO_PAUSA_S * 1000)]      # seguir arriba no repite
    assert mantener(det, 10_000, 11_000, puntos(derecho=False)) == []
    assert mantener(det, 11_000, 16_000, puntos()) == [14_000]


def test_un_hueco_corto_no_reinicia_la_cuenta_y_uno_largo_si():
    det = DetectorGesto()
    mantener(det, 0, 2_000, puntos())
    mantener(det, 2_000, 2_200, puntos(derecho=False))        # 200 ms: ruido
    assert mantener(det, 2_200, 4_500, puntos()) == [3_000]

    det = DetectorGesto()
    mantener(det, 0, 2_000, puntos())
    mantener(det, 2_000, 2_600, puntos(derecho=False))        # 600 ms: lo bajó
    assert mantener(det, 2_600, 6_000, puntos()) == [5_600]    # cuenta desde 2,6 s


def test_progreso_para_la_interfaz():
    det = DetectorGesto()
    det.actualizar(0, puntos())
    det.actualizar(300, puntos())
    assert det.progreso(300) is None                          # aún no se muestra
    det.actualizar(1_500, puntos())
    assert det.progreso(1_500) == pytest.approx(0.5)
    det.actualizar(3_000, puntos())                           # dispara
    assert det.progreso(3_000) is None

# ---------------------------------------------------------------------------
# En la sesión
# ---------------------------------------------------------------------------


class EstimadorBrazo(EstimadorFalso):
    """De perfil, con el brazo derecho arriba cuando `arriba` es True."""

    def __init__(self):
        super().__init__(tronco=10)
        self.arriba = False

    def estimar(self, frame, t_ms):
        mundo = esqueleto_perfil(float(frame), self.tronco)
        hombro = mundo[IDX["right_shoulder"], :3].copy()
        mundo[0, :3] = hombro + [0.0, -0.2, 0.0]                 # nariz
        if self.arriba:
            mundo[IDX["right_elbow"], :3] = hombro + [0.0, -0.28, 0.0]
            mundo[IDX["right_wrist"], :3] = hombro + [0.0, -0.53, 0.0]
        return ResultadoPose(muestra_desde_arrays(t_ms, mundo, mundo), mundo, 1.0)


@pytest.fixture(scope="module")
def catalogo():
    return cargar_catalogo()


class Reloj:
    def __init__(self, sesion):
        self.sesion, self.t = sesion, 0

    def correr(self, segundos, dt=100):
        estados = []
        for _ in range(int(segundos * 1000 / dt)):
            estados.append(self.sesion.procesar(170.0, self.t))
            self.t += dt
        return estados


def test_el_gesto_pausa_y_luego_reanuda(catalogo):
    voz, est = VozFalsa(), EstimadorBrazo()
    s = Sesion(rutina_de_un_ejercicio("marcha_rodillas", 5, catalogo), catalogo, est, voz)
    r = Reloj(s)
    r.correr(1)
    est.arriba = True
    estados = r.correr(3.5)
    assert any(e.gesto == {"progreso": 0.5, "accion": "pausar"} for e in estados)
    assert estados[-1].pausada and estados[-1].motivo_pausa == USUARIA
    assert AVISO_PAUSA[USUARIA] in [t for t, _ in voz.dichas]
    # seguir con el brazo arriba no reanuda
    assert r.correr(5)[-1].motivo_pausa == USUARIA
    est.arriba = False
    assert r.correr(1)[-1].motivo_pausa == USUARIA          # no se quita sola
    est.arriba = True
    estados = r.correr(3.5)
    assert any(e.gesto and e.gesto["accion"] == "reanudar" for e in estados)
    assert not estados[-1].pausada
    assert AVISO_REANUDA in [t for t, _ in voz.dichas]


def test_el_gesto_reanuda_la_pausa_del_boton(catalogo):
    est = EstimadorBrazo()
    s = Sesion(rutina_de_un_ejercicio("marcha_rodillas", 5, catalogo), catalogo, est, VozFalsa())
    r = Reloj(s)
    r.correr(1)
    s.pausar()
    assert r.correr(1)[-1].motivo_pausa == USUARIA
    est.arriba = True
    assert not r.correr(3.5)[-1].pausada

# ---------------------------------------------------------------------------
# Anterior / siguiente
# ---------------------------------------------------------------------------


def test_anterior_y_siguiente_solo_si_aplica(catalogo):
    rutina = rutina_desde_dict({"nombre": "t", "pasos": [
        {"skill_id": "marcha_rodillas", "repeticiones": 3},
        {"skill_id": "jumping_jacks", "repeticiones": 3},
        {"skill_id": "plancha", "duracion_s": 10}]}, catalogo)
    voz = VozFalsa()
    s = Sesion(rutina, catalogo, EstimadorFalso(tronco=10), voz)
    paso = lambda: s.procesar(170.0, 0).paso                   # noqa: E731

    s.anterior()
    assert paso() == 1                                        # ya es el primero
    s.siguiente()
    s.siguiente()
    assert paso() == 3
    s.siguiente()
    assert paso() == 3 and not s.terminada                    # ya es el último

    dichas = len(voz.dichas)
    s.anterior()
    assert paso() == 2
    assert not any("terminaste" in t for t, _ in voz.dichas[dichas:])
    # el resumen tiene un paso por ejercicio, sin duplicar el repetido
    assert [p["skill_id"] for p in s.resumen()["pasos"]] == [
        "marcha_rodillas", "jumping_jacks", "plancha"]
