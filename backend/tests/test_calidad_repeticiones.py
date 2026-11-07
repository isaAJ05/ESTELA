"""Repeticiones correctas y con error (T29.a).

- El motor da a cada repetición cerrada un resultado con el mismo criterio que
  la racha de refuerzo: con error si alguna regla detectó un error (aunque la
  política de silencio no lo dijera), correcta si ninguna lo detectó y todas
  las aplicables se comprobaron, y no evaluada en otro caso.
- La sesión cuenta las repeticiones completadas (o los segundos, en la
  plancha) correctas y con error; las no evaluadas no suman a ninguna.
"""

from dataclasses import replace

import pytest

from estela.adaptadores.interfaz import contrato
from estela.aplicacion.rutina import cargar_catalogo, rutina_de_un_ejercicio
from estela.aplicacion.sesion import Sesion
from estela.dominio.conteo.segmentador import EVENTO_COMPLETA
from estela.dominio.feedback.contrato import Observacion
from estela.dominio.feedback.motor.decision import (CALIDAD_CON_ERROR, CALIDAD_CORRECTA,
                                                    CALIDAD_NO_EVALUADA, MotorDecision)
from tests.test_segmentador import rampa
from tests.test_sesion import EstimadorPlancha, VozFalsa, correr


@pytest.fixture(scope="module")
def catalogo():
    return cargar_catalogo()


def _jumping_jacks(n, codo=170.0):
    """n repeticiones completas: brazos arriba, pies abiertos y salto."""
    frames = []
    for _ in range(n):
        for h in rampa(20, 150, 8) + rampa(150, 20, 8) + [20] * 4:
            arriba = h >= 100
            frames.append(({"hombro_medio": h, "codo_medio": codo},
                           {"separacion_pies_hombros": 1.5 if arriba else 0.5,
                            "salto_cadera": 0.3 if arriba else 0.0}))
    return frames


def _calidades(catalogo, skill_id, frames):
    """Segmentador y motor del catálogo, como en la sesión."""
    ej = catalogo[skill_id]
    seg, motor, completas = ej.nuevo_segmentador(), MotorDecision(ej.skill), []
    for i, (angulos, distancias) in enumerate(frames):
        o = Observacion(t_ms=i * 33, ejercicio_id=skill_id, angulos=angulos,
                        distancias=distancias, orientacion=0.0,
                        confianza={k: 1.0 for k in list(angulos) + list(distancias)})
        s = seg.actualizar(o)
        motor.observar(replace(o, fase=s.fase, repeticion=s.repeticion))
        if s.evento == EVENTO_COMPLETA:
            completas.append(s.repeticion)
    motor.cerrar_repeticion()
    return completas, motor.calidad_por_repeticion


def test_repeticiones_bien_hechas_son_correctas(catalogo):
    completas, calidad = _calidades(catalogo, "jumping_jacks", _jumping_jacks(4))
    assert len(completas) == 4
    assert {calidad[r] for r in completas} == {CALIDAD_CORRECTA}


def test_un_error_detectado_marca_la_repeticion_aunque_no_se_diga(catalogo):
    """Codos doblados (70°, umbral 90°) en todas: la política de silencio solo habla tras varias
    repeticiones, pero todas cuentan como con error."""
    completas, calidad = _calidades(catalogo, "jumping_jacks", _jumping_jacks(4, codo=70.0))
    assert len(completas) == 4
    assert {calidad[r] for r in completas} == {CALIDAD_CON_ERROR}


def test_sin_poder_comprobar_las_reglas_no_es_correcta(catalogo):
    """Sin la medida de los codos la regla de codos no se comprueba: el motor
    no sabe si la repetición estuvo bien."""
    frames = [({"hombro_medio": a["hombro_medio"]}, d) for a, d in _jumping_jacks(3)]
    completas, calidad = _calidades(catalogo, "jumping_jacks", frames)
    assert completas and {calidad[r] for r in completas} == {CALIDAD_NO_EVALUADA}


def test_reiniciar_el_motor_borra_los_resultados(catalogo):
    motor = MotorDecision(catalogo["jumping_jacks"].skill)
    motor.calidad_por_repeticion[1] = CALIDAD_CORRECTA
    motor.reiniciar()
    assert motor.calidad_por_repeticion == {}


# -- sesión: plancha (segundos) ----------------------------------------------------

def test_plancha_bien_hecha_suma_segundos_correctos(catalogo):
    s = Sesion(rutina_de_un_ejercicio("plancha", 99, catalogo), catalogo,
               EstimadorPlancha(), VozFalsa())
    estados = correr(s, [0.0] * 150)                 # 15 s
    e = estados[-1]
    assert e.correctas > 0 and e.con_error == 0
    assert e.correctas <= e.completadas              # el bloque en curso aún no cuenta


def test_plancha_con_la_cadera_caida_suma_segundos_con_error(catalogo):
    s = Sesion(rutina_de_un_ejercicio("plancha", 99, catalogo), catalogo,
               EstimadorPlancha(), VozFalsa())
    e = correr(s, [0.08] * 150)[-1]
    assert e.con_error > 0
    assert e.correctas + e.con_error <= e.completadas


def test_resumen_y_registro_llevan_el_resultado(catalogo):
    s = Sesion(rutina_de_un_ejercicio("plancha", 10, catalogo), catalogo,
               EstimadorPlancha(), VozFalsa())
    correr(s, [0.08] * 160)                          # termina los 10 s
    assert s.terminada
    paso = s.resumen()["pasos"][0]
    # al terminar el ejercicio se cierra el último bloque: cuentan todos los segundos
    assert paso["correctas"] + paso["con_error"] == paso["completadas"] == 10
    assert paso["con_error"] > 0
    assert {f["calidad"] for f in paso["repeticiones"]} <= {
        CALIDAD_CORRECTA, CALIDAD_CON_ERROR, CALIDAD_NO_EVALUADA}
    d = contrato.resumen_a_dict(s.resumen(), catalogo)
    assert (d["pasos"][0]["correctas"], d["pasos"][0]["conError"]) == (
        paso["correctas"], paso["con_error"])


def test_contrato_activa_correctas_con_error(catalogo):
    assert contrato.CAPACIDADES["correctasConError"] is True
    s = Sesion(rutina_de_un_ejercicio("plancha", 99, catalogo), catalogo,
               EstimadorPlancha(), VozFalsa())
    e = correr(s, [0.08] * 150)[-1]
    d = contrato.estado_a_dict(e)
    assert (d["correctas"], d["conError"]) == (e.correctas, e.con_error)


def test_reiniciar_el_ejercicio_vuelve_a_cero(catalogo):
    s = Sesion(rutina_de_un_ejercicio("plancha", 99, catalogo), catalogo,
               EstimadorPlancha(), VozFalsa())
    assert correr(s, [0.08] * 150)[-1].con_error > 0
    s.reiniciar_ejercicio()
    e = s.procesar(0.08, 15_100)
    assert (e.correctas, e.con_error) == (0, 0)
