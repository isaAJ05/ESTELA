"""DetectorPausa aislado: cuándo pausa, cuándo retoma y cuánto tiempo cuenta."""

from estela.aplicacion.pausa import (EVENTO_PAUSA, EVENTO_REANUDA, INACTIVIDAD,
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


def test_sin_senal_valida_no_se_vigila_la_inactividad():
    d = DetectorPausa(inactividad_s=8)
    d.actualizar(0, True, progreso=("reposo", 1, 1, 0))
    for t in range(100, 20000, 100):                # piernas fuera del encuadre
        assert d.actualizar(t, True, progreso=None) is None


def test_pausa_por_inactividad_no_retoma_sin_senal():
    d = DetectorPausa(inactividad_s=8)
    d.actualizar(0, True, progreso=("reposo", 1, 1, 0))
    assert d.actualizar(8000, True, progreso=("reposo", 1, 1, 0)) == EVENTO_PAUSA
    assert d.actualizar(8100, True, progreso=None) is None
    assert d.pausada


def test_si_sale_del_encuadre_durante_la_inactividad_cambia_el_motivo():
    d = DetectorPausa(sin_persona_s=5, inactividad_s=8)
    d.actualizar(0, True, progreso=("reposo", 1, 1, 0))
    assert d.actualizar(8000, True, progreso=("reposo", 1, 1, 0)) == EVENTO_PAUSA
    assert d.actualizar(12000, persona=False) is None
    assert d.motivo == INACTIVIDAD                  # aún no pasan 5 s sin verla
    assert d.actualizar(13000, persona=False) is None
    assert d.motivo == SIN_PERSONA and d.veces == 1
    # al volver bien orientada retoma aunque no se haya movido todavía
    assert d.actualizar(14000, True, progreso=("reposo", 1, 1, 0)) == EVENTO_REANUDA

def test_otro_ejercicio_no_es_inactividad():
    d = DetectorPausa(inactividad_s=8)
    for t in range(0, 20000, 100):                  # el elegido no avanza
        assert d.actualizar(t, True, progreso=("reposo", 1, 1, 0), otro_ejercicio=True) is None
    assert not d.pausada
    # al dejar el otro ejercicio (último frame en 19 900), la espera empieza de cero
    assert d.actualizar(27800, True, progreso=("reposo", 1, 1, 0)) is None
    assert d.actualizar(27900, True, progreso=("reposo", 1, 1, 0)) == EVENTO_PAUSA


def test_otro_ejercicio_quita_la_pausa_por_inactividad():
    d = DetectorPausa(inactividad_s=8)
    d.actualizar(0, True, progreso=("reposo", 1, 1, 0))
    assert d.actualizar(8000, True, progreso=("reposo", 1, 1, 0)) == EVENTO_PAUSA
    assert d.actualizar(9000, True, progreso=("reposo", 1, 1, 0),
                        otro_ejercicio=True) == EVENTO_REANUDA
    assert not d.pausada


def test_otro_ejercicio_no_quita_la_pausa_sin_persona():
    d = DetectorPausa(sin_persona_s=1)
    d.actualizar(0, persona=False)
    assert d.actualizar(1000, persona=False) == EVENTO_PAUSA
    assert d.actualizar(1500, persona=False, otro_ejercicio=True) is None
    assert d.pausada and d.motivo == SIN_PERSONA
