"""`sesion._EntreRepeticiones`: lo que pasa entre una repetición y la siguiente
(brazos abajo y ritmo), que se publica durante la repetición siguiente."""

import pytest

from estela.aplicacion.sesion import _EntreRepeticiones
from estela.dominio.conteo.segmentador import (EVENTO_COMPLETA, EVENTO_INICIO,
                                               EstadoSegmento)
from estela.dominio.feedback.contrato import Observacion


def _obs(t, brazos):
    return Observacion(t_ms=t, ejercicio_id="jumping_jacks", angulos={"apertura_brazos": brazos},
                       confianza={"apertura_brazos": 0.9})


def _seg(rep, evento=None):
    return EstadoSegmento("x", rep, 0, 0, evento)


def _ciclo(entre, t0, duracion, abajo, rep):
    """Una repetición: inicio en t0, brazos arriba, cierre y reposo con los
    brazos en `abajo`. Devuelve la observación del inicio."""
    o = entre.aplicar(_obs(t0, 60.0), _seg(rep, EVENTO_INICIO))
    entre.aplicar(_obs(t0 + duracion // 3, 160.0), _seg(rep))
    entre.aplicar(_obs(t0 + duracion // 2, 50.0), _seg(rep, EVENTO_COMPLETA))
    entre.aplicar(_obs(t0 + duracion - 50, abajo), _seg(rep))
    return o


def test_brazos_abajo_es_el_minimo_del_reposo_anterior():
    e = _EntreRepeticiones()
    e.aplicar(_obs(0, 15.0), _seg(0))                  # de pie antes de empezar
    o1 = _ciclo(e, 100, 900, abajo=55.0, rep=1)
    assert o1.distancias["brazos_abajo"] == pytest.approx(15.0)
    o2 = e.aplicar(_obs(1000, 70.0), _seg(2, EVENTO_INICIO))
    # el mínimo es el del reposo tras la rep 1 (55), no los 160 de arriba
    assert o2.distancias["brazos_abajo"] == pytest.approx(50.0)
    assert o2.confianza["brazos_abajo"] == 1.0
    # sigue publicado durante toda la repetición
    assert e.aplicar(_obs(1200, 160.0), _seg(2)).distancias["brazos_abajo"] == pytest.approx(50.0)


def test_ritmo_necesita_tres_ciclos_previos():
    e = _EntreRepeticiones()
    t = 0
    for rep in range(1, 5):
        o = _ciclo(e, t, 900, 20.0, rep)
        assert "ritmo_irregular" not in o.distancias
        t += 900
    o = _ciclo(e, t, 900, 20.0, 5)
    assert o.distancias["ritmo_irregular"] == pytest.approx(0.0)


def test_un_ciclo_mucho_mas_largo_es_ritmo_irregular():
    e = _EntreRepeticiones()
    t = 0
    for rep, dur in enumerate((900, 900, 900, 1800), start=1):
        _ciclo(e, t, dur, 20.0, rep)
        t += dur
    o = _ciclo(e, t, 900, 20.0, 5)
    assert o.distancias["ritmo_irregular"] == pytest.approx(1.0)   # 1800 frente a 900


def test_un_descanso_reinicia_el_ritmo():
    e = _EntreRepeticiones()
    t = 0
    for rep, dur in enumerate((900, 900, 900, 5000, 900), start=1):
        o = _ciclo(e, t, dur, 20.0, rep)
        t += dur
    # tras el descanso de 5 s solo hay un ciclo nuevo: aún no hay ritmo
    o = _ciclo(e, t, 900, 20.0, 6)
    assert "ritmo_irregular" not in o.distancias
