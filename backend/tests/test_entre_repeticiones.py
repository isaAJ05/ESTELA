"""`sesion._EntreRepeticiones`: lo que pasa entre una repetición y la siguiente
(brazos abajo y ritmo), que se publica durante la repetición siguiente."""

import pytest

from estela.aplicacion.sesion import _EntreRepeticiones
from estela.dominio.conteo.segmentador import (EVENTO_COMPLETA, EVENTO_INCOMPLETA, EVENTO_INICIO,
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


def _obs_jj(t, brazos, pies):
    """Brazos (`hombro_medio` y `apertura_brazos`) y pies (`separacion_pies_hombros`)."""
    return Observacion(t_ms=t, ejercicio_id="jumping_jacks",
                       angulos={"apertura_brazos": brazos, "hombro_medio": brazos},
                       distancias={"separacion_pies_hombros": pies},
                       confianza={"apertura_brazos": 0.9, "hombro_medio": 0.9,
                                  "separacion_pies_hombros": 0.9})


def _ciclo_jj(e, t0, rep, t_brazos, t_pies, pies_cerrado):
    """Repetición de 1000 ms con los brazos arriba en t0 + t_brazos y los pies
    abiertos en t0 + t_pies; al cerrar, los pies quedan en `pies_cerrado`."""
    o = e.aplicar(_obs_jj(t0, 60.0, 0.5), _seg(rep, EVENTO_INICIO))
    e.aplicar(_obs_jj(t0 + t_brazos, 160.0, 1.0), _seg(rep))
    e.aplicar(_obs_jj(t0 + t_pies, 120.0, 1.8), _seg(rep))
    e.aplicar(_obs_jj(t0 + 1000, 40.0, 1.5), _seg(rep, EVENTO_COMPLETA))
    e.aplicar(_obs_jj(t0 + 1100, 15.0, pies_cerrado), _seg(rep))
    return o


def test_pies_juntos_es_el_minimo_del_reposo_anterior():
    e = _EntreRepeticiones()
    _ciclo_jj(e, 0, 1, 400, 400, pies_cerrado=0.35)
    o = _ciclo_jj(e, 1200, 2, 400, 400, pies_cerrado=1.1)
    assert o.distancias["pies_juntos"] == pytest.approx(0.35)
    o = e.aplicar(_obs_jj(2400, 60.0, 1.2), _seg(3, EVENTO_INICIO))
    assert o.distancias["pies_juntos"] == pytest.approx(1.1)     # no se juntaron


def test_desfase_brazos_pies_es_fraccion_de_la_repeticion():
    e = _EntreRepeticiones()
    _ciclo_jj(e, 0, 1, t_brazos=400, t_pies=420, pies_cerrado=0.35)
    o = e.aplicar(_obs_jj(1200, 60.0, 0.5), _seg(2, EVENTO_INICIO))
    assert o.distancias["desfase_brazos_pies"] == pytest.approx(0.02)   # a la vez
    _ciclo_jj(e, 1200, 2, t_brazos=200, t_pies=700, pies_cerrado=0.35)
    o = e.aplicar(_obs_jj(2400, 60.0, 0.5), _seg(3, EVENTO_INICIO))
    assert o.distancias["desfase_brazos_pies"] == pytest.approx(0.5)    # a destiempo


def test_sin_repeticion_completa_no_hay_desfase():
    e = _EntreRepeticiones()
    e.aplicar(_obs_jj(0, 60.0, 0.5), _seg(1, EVENTO_INICIO))
    e.aplicar(_obs_jj(300, 160.0, 1.8), _seg(1))
    e.aplicar(_obs_jj(900, 40.0, 0.4), _seg(1, EVENTO_INCOMPLETA))
    o = e.aplicar(_obs_jj(1200, 60.0, 0.5), _seg(2, EVENTO_INICIO))
    assert "desfase_brazos_pies" not in o.distancias
