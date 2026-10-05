"""DetectorPausa aislado: cuándo pausa, cuándo retoma y cuánto tiempo cuenta."""

from estela.sesion.pausa import (EVENTO_PAUSA, EVENTO_REANUDA, INACTIVIDAD,
                                 SIN_PERSONA, DetectorPausa)


def test_sin_persona_pausa_tras_el_umbral_y_retoma_al_volver():
    d = DetectorPausa(sin_persona_s=5, inactividad_s=8)
    assert d.actualizar(0, persona=True) is None
    assert d.actualizar(4900, persona=False) is None
    assert d.actualizar(5000, persona=False) == EVENTO_PAUSA
    assert d.pausada and d.motivo == SIN_PERSONA
    assert d.actualizar(6000, persona=False) is None
    assert d.actualizar(7000, persona=True) == EVENTO_REANUDA
    assert not d.pausada and d.veces == 1
    assert d.tiempo_pausado_ms(9000) == 2000


def test_no_retoma_si_vuelve_mal_orientada():
    d = DetectorPausa(sin_persona_s=1)
    d.actualizar(0, persona=False)
    assert d.actualizar(1000, persona=False) == EVENTO_PAUSA
    assert d.actualizar(1500, persona=True, orientacion_ok=False) is None
    assert d.actualizar(2000, persona=True, orientacion_ok=True) == EVENTO_REANUDA


def test_inactividad_solo_cuenta_cuando_el_ejercicio_empezo():
    d = DetectorPausa(sin_persona_s=5, inactividad_s=8)
    for t in range(0, 20000, 100):                  # colocándose: sin progreso
        assert d.actualizar(t, True, progreso=None) is None


def test_inactividad_pausa_y_retoma_con_progreso():
    d = DetectorPausa(sin_persona_s=5, inactividad_s=8)
    d.actualizar(0, True, progreso=("reposo", 1, 1, 0))
    assert d.actualizar(7900, True, progreso=("reposo", 1, 1, 0)) is None
    assert d.actualizar(8000, True, progreso=("reposo", 1, 1, 0)) == EVENTO_PAUSA
    assert d.motivo == INACTIVIDAD
    # presente y bien orientada, pero quieta: sigue en pausa
    assert d.actualizar(9000, True, progreso=("reposo", 1, 1, 0)) is None
    assert d.actualizar(9500, True, progreso=("ida", 2, 1, 0)) == EVENTO_REANUDA


def test_el_progreso_reinicia_la_espera():
    d = DetectorPausa(inactividad_s=8)
    for i, t in enumerate(range(0, 30000, 1000)):   # una repetición por segundo
        assert d.actualizar(t, True, progreso=("ida", i, i, 0)) is None


def test_tiempo_pausado_incluye_la_pausa_en_curso():
    d = DetectorPausa(sin_persona_s=1)
    d.actualizar(0, persona=False)
    d.actualizar(1000, persona=False)
    assert d.tiempo_pausado_ms(4000) == 3000
