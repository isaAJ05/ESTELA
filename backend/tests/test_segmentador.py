"""Segmentador de fases con señales sintéticas: fases, conteo y robustez."""

import pytest

from estela.dominio.feedback.contrato import Observacion

from estela.dominio.conteo.segmentador import (
    EVENTO_COMPLETA, EVENTO_INCOMPLETA, CondicionPostura, SegmentacionInvalida,
    SegmentadorAlternante, SegmentadorCiclo, SegmentadorIsometrico, leer_senal,
    segmentador_desde_dict,
)
from estela.aplicacion.rutina import cargar_catalogo

FASES_SENTADILLA = ("arriba", "descenso", "fondo", "ascenso")


def obs(t=0, angulos=None, distancias=None, conf=1.0, confs=None):
    angulos = angulos or {}
    distancias = distancias or {}
    confianza = {k: conf for k in list(angulos) + list(distancias)}
    confianza.update(confs or {})
    return Observacion(t_ms=t, ejercicio_id="x", angulos=angulos,
                       confianza=confianza, distancias=distancias)


def rampa(a, b, n):
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def sentadilla(minimo=80.0, n=10):
    return rampa(170, minimo, n) + rampa(minimo, 170, n) + [170] * 5


def correr(seg, valores, nombre="rodilla_media"):
    return [seg.actualizar(obs(i * 33, {nombre: v})) for i, v in enumerate(valores)]


def seg_sentadilla(**kw):
    base = dict(senal="angulos.rodilla_media", reposo=155, extremo=110,
                fases=FASES_SENTADILLA, margen_retorno=10, suavizado=1)
    base.update(kw)
    return SegmentadorCiclo(**base)


def test_cuenta_repeticiones_completas():
    estados = correr(seg_sentadilla(), sentadilla() * 3)
    assert estados[-1].completadas == 3
    assert estados[-1].incompletas == 0
    assert estados[-1].repeticion == 3


def test_recorre_las_cuatro_fases_en_orden():
    fases = [e.fase for e in correr(seg_sentadilla(), sentadilla())]
    vistas = [f for i, f in enumerate(fases) if i == 0 or f != fases[i - 1]]
    assert vistas == list(FASES_SENTADILLA) + ["arriba"]


def test_repeticion_parcial_pasa_por_vuelta_pero_no_cuenta():
    """Sin fase de vuelta el motor no podría decir «baja más»."""
    estados = correr(seg_sentadilla(), sentadilla(minimo=125))
    assert "ascenso" in {e.fase for e in estados}
    assert "fondo" not in {e.fase for e in estados}
    assert estados[-1].completadas == 0
    assert estados[-1].incompletas == 1
    assert [e.evento for e in estados if e.evento][-1] == EVENTO_INCOMPLETA


def test_la_repeticion_empieza_al_salir_del_reposo():
    """El acumulador del motor debe ver la repetición entera con el mismo índice."""
    estados = correr(seg_sentadilla(), sentadilla())
    en_movimiento = [e.repeticion for e in estados if e.fase != "arriba"]
    assert set(en_movimiento) == {1}
    assert estados[0].repeticion == 0


def test_ruido_en_el_reposo_no_genera_repeticiones():
    ruido = [170, 168, 171, 166, 172, 169, 167] * 10
    assert correr(seg_sentadilla(), ruido)[-1].repeticion == 0


def test_rebote_en_el_fondo_no_duplica_la_repeticion():
    valores = rampa(170, 85, 8) + [95, 88, 96, 86] + rampa(86, 170, 8) + [170] * 3
    estados = correr(seg_sentadilla(suavizado=1, margen_retorno=10), valores)
    assert estados[-1].completadas == 1


def test_senal_ausente_o_poco_confiable_congela_el_estado():
    seg = seg_sentadilla()
    for v in rampa(170, 80, 10):
        seg.actualizar(obs(0, {"rodilla_media": v}))
    fase = seg.actualizar(obs(0, {"rodilla_media": 80})).fase
    assert seg.actualizar(obs(0, {})).fase == fase
    assert seg.actualizar(obs(0, {"rodilla_media": 170}, conf=0.1)).fase == fase


def test_lista_de_senales_cae_al_lado_visible():
    o = obs(0, {"rodilla_media": 120, "rodilla_izq": 118, "rodilla_der": 122},
            confs={"rodilla_media": 0.3, "rodilla_der": 0.3, "rodilla_izq": 0.95})
    rutas = ["angulos.rodilla_media", "angulos.rodilla_izq", "angulos.rodilla_der"]
    assert leer_senal(o, rutas, 0.5) == 118
    assert leer_senal(o, "angulos.rodilla_media", 0.5) is None


def test_senal_creciente_jumping_jacks():
    seg = SegmentadorCiclo("distancias.separacion_pies", reposo=0.9, extremo=1.4,
                           fases=("cerrado", "apertura", "abierto", "cierre"),
                           margen_retorno=0.2, suavizado=1)
    valores = (rampa(0.5, 2.0, 6) + rampa(2.0, 0.5, 6)) * 4
    estados = [seg.actualizar(obs(0, distancias={"separacion_pies": v})) for v in valores]
    assert estados[-1].completadas == 4
    assert "abierto" in {e.fase for e in estados}


def marcha(lado_valor, otro=170.0):
    return rampa(170, lado_valor, 6) + rampa(lado_valor, 170, 6) + [170] * 2


def seg_marcha():
    return SegmentadorAlternante(
        "angulos.cadera_izq", "angulos.cadera_der", reposo=150, extremo=115,
        fase_izq_arriba="apoyo_der", fase_der_arriba="apoyo_izq",
        fase_transicion="transicion", margen_retorno=10, suavizado=1)


def test_marcha_cuenta_cada_pierna_y_etiqueta_el_apoyo():
    seg = seg_marcha()
    estados = []
    for _ in range(3):
        for v in marcha(80):
            estados.append(seg.actualizar(obs(0, {"cadera_izq": v, "cadera_der": 170})))
        for v in marcha(80):
            estados.append(seg.actualizar(obs(0, {"cadera_izq": 170, "cadera_der": v})))
    assert estados[-1].completadas == 6
    assert estados[-1].repeticion == 6
    assert {"apoyo_der", "apoyo_izq", "transicion"} <= {e.fase for e in estados}


def test_marcha_subida_de_la_pierna_es_transicion():
    """Las reglas de altura se evalúan con la pierna ya arriba, no mientras sube."""
    seg = seg_marcha()
    fases = [seg.actualizar(obs(0, {"cadera_izq": v, "cadera_der": 170})).fase
             for v in rampa(170, 120, 5)]
    assert set(fases) == {"transicion"}


def test_marcha_ignora_la_otra_pierna_mientras_una_esta_arriba():
    seg = seg_marcha()
    for v in rampa(170, 80, 6):
        seg.actualizar(obs(0, {"cadera_izq": v, "cadera_der": 170}))
    # ruido en la pierna de apoyo: no abre una segunda repetición
    e = seg.actualizar(obs(0, {"cadera_izq": 80, "cadera_der": 130}))
    assert e.repeticion == 1 and e.fase == "apoyo_der"


def test_desde_dict_valida_fases_contra_el_skill():
    d = {"tipo": "ciclo", "senal": "angulos.rodilla_media", "reposo": 155,
         "extremo": 110, "margen_retorno": 10, "fases": ["a", "b", "c", "d"]}
    with pytest.raises(SegmentacionInvalida):
        segmentador_desde_dict(d, FASES_SENTADILLA)
    with pytest.raises(SegmentacionInvalida):
        segmentador_desde_dict({**d, "tipo": "otro"})


def test_skills_del_repositorio_cargan_su_segmentacion():
    catalogo = cargar_catalogo()
    assert {k for k, e in catalogo.items() if e.soportado} == set(catalogo)
    assert set(catalogo) == {"jumping_jacks", "marcha_rodillas", "plancha",
                             "abduccion_cadera_izq", "abduccion_cadera_der"}
    for e in catalogo.values():
        e.nuevo_segmentador()
    assert catalogo["plancha"].unidad == "segundos"
    assert {e.unidad for k, e in catalogo.items() if k != "plancha"} == {"repeticiones"}


# ---------------------------------------------------------------------------
# Postura mantenida (plancha)
# ---------------------------------------------------------------------------

def seg_plancha(**kw):
    base = dict(condiciones=[CondicionPostura("angulos.tronco_inclinacion", min=55),
                             CondicionPostura("angulos.rodilla_media", min=145)],
                fases=("preparacion", "mantenimiento"),
                entrada_ms=1000, salida_ms=1500, bloque_s=5)
    base.update(kw)
    return SegmentadorIsometrico(**base)


def sostener(seg, segundos, t0=0, tronco=85.0, rodilla=175.0, dt=100):
    n = int(round(segundos * 1000 / dt))
    return [seg.actualizar(obs(t0 + i * dt, {"tronco_inclinacion": tronco,
                                             "rodilla_media": rodilla}))
            for i in range(n)]


def test_isometrico_entra_tras_la_espera_y_cuenta_segundos():
    estados = sostener(seg_plancha(), 7.0)          # t = 0 … 6,9 s
    assert estados[5].fase == "preparacion"
    assert estados[10].fase == "mantenimiento"      # entra a t = 1 s
    assert estados[-1].completadas == 5             # 5,9 s en posición
    eventos = [e.evento for e in estados if e.evento == EVENTO_COMPLETA]
    assert len(eventos) == 5                        # uno por segundo


def test_isometrico_la_repeticion_es_el_bloque_de_cinco_segundos():
    estados = sostener(seg_plancha(), 13.0)
    assert estados[0].repeticion == 0
    assert sorted({e.repeticion for e in estados}) == [0, 1, 2, 3]


def test_isometrico_un_frame_malo_no_interrumpe():
    seg = seg_plancha()
    sostener(seg, 3.0)
    sostener(seg, 0.1, t0=3000, tronco=20.0)        # un frame de pie
    e = sostener(seg, 2.0, t0=3100)[-1]
    assert e.fase == "mantenimiento" and e.incompletas == 0
    assert e.completadas >= 3


def test_isometrico_salir_de_la_postura_pausa_y_cuenta_la_interrupcion():
    seg = seg_plancha()
    sostener(seg, 4.0)                              # 3 s en posición
    fuera = sostener(seg, 3.0, t0=4000, tronco=10.0)
    assert fuera[-1].fase == "preparacion" and fuera[-1].incompletas == 1
    assert [e.evento for e in fuera if e.evento] == [EVENTO_INCOMPLETA]
    assert fuera[-1].completadas == 2               # el tiempo no suma fuera
    vuelta = sostener(seg, 3.0, t0=7000)            # 1 s de entrada + 2 s
    assert vuelta[-1].fase == "mantenimiento"
    assert vuelta[-1].completadas == 4


def test_isometrico_a_cuatro_patas_no_cuenta_como_plancha():
    estados = sostener(seg_plancha(), 5.0, rodilla=90.0)
    assert {e.fase for e in estados} == {"preparacion"}
    assert estados[-1].completadas == 0


def test_isometrico_sin_senal_congela_y_no_suma():
    seg = seg_plancha()
    sostener(seg, 3.0)
    ciegos = [seg.actualizar(obs(3000 + i * 100, {})) for i in range(20)]
    assert all(not e.senal_valida for e in ciegos)
    assert ciegos[-1].fase == "mantenimiento" and ciegos[-1].completadas == 1
    e = sostener(seg, 1.0, t0=5000)[-1]
    assert e.completadas == 2


def test_isometrico_desde_dict_valida_la_configuracion():
    d = {"tipo": "isometrico", "fases": ["preparacion", "mantenimiento"],
         "condiciones": [{"senal": "angulos.tronco_inclinacion", "min": 55}]}
    assert isinstance(segmentador_desde_dict(d, ("preparacion", "mantenimiento")),
                      SegmentadorIsometrico)
    with pytest.raises(SegmentacionInvalida):
        segmentador_desde_dict({**d, "condiciones": [{"senal": "angulos.x"}]})
    with pytest.raises(SegmentacionInvalida):
        segmentador_desde_dict({**d, "condiciones": []})
    with pytest.raises(SegmentacionInvalida):
        segmentador_desde_dict({**d, "fases": ["a", "b", "c"]})


def test_requiere_coordinacion_brazos_y_piernas():
    """EXP-009: en jumping jacks la repetición la marcan los brazos y solo
    cuenta si los pies también se abrieron."""
    def seg():
        return SegmentadorCiclo("angulos.hombro_medio", reposo=45, extremo=100,
                                fases=("cerrado", "apertura", "abierto", "cierre"),
                                margen_retorno=15, suavizado=1,
                                requiere=[CondicionPostura("distancias.separacion_pies_hombros", min=0.9)])
    brazos = [20, 60, 120, 150, 120, 60, 20]
    s = seg()
    for b in brazos:          # solo brazos: los pies no se abren
        e = s.actualizar(obs(0, angulos={"hombro_medio": b},
                             distancias={"separacion_pies_hombros": 0.4}))
    assert (e.completadas, e.incompletas) == (0, 1)
    s = seg()
    for b in brazos:          # brazos y pies
        pies = 1.5 if b >= 100 else 0.4
        e = s.actualizar(obs(0, angulos={"hombro_medio": b},
                             distancias={"separacion_pies_hombros": pies}))
    assert (e.completadas, e.incompletas) == (1, 0)


# ---------------------------------------------------------------------------
# Repeticiones cortas: el frame que las cierra se evalúa (EXP-009, ronda 2)
# ---------------------------------------------------------------------------

def _dichas(skill_id, frames):
    """Segmentador y motor del catálogo, como en la sesión: errores emitidos."""
    from dataclasses import replace
    from estela.dominio.feedback.contrato import ErrorTipificado
    from estela.dominio.feedback.motor.decision import MotorDecision
    ej = cargar_catalogo()[skill_id]
    seg, motor, dichas = ej.nuevo_segmentador(), MotorDecision(ej.skill), []
    for i, (angulos, distancias) in enumerate(frames):
        o = Observacion(t_ms=i * 33, ejercicio_id=skill_id, angulos=angulos,
                        distancias=distancias, orientacion=90.0 if skill_id == "marcha_rodillas" else 0.0,
                        confianza={k: 1.0 for k in list(angulos) + list(distancias)})
        s = seg.actualizar(o)
        d = motor.observar(replace(o, fase=s.fase, repeticion=s.repeticion))
        if isinstance(d, ErrorTipificado):
            dichas.append(d.error_id)
    return dichas


def test_ciclo_corto_cierra_en_la_vuelta():
    # pico a menos de margen_retorno del reposo: antes no pasaba por la vuelta
    estados = correr(seg_sentadilla(), [170, 150, 148, 150, 170])
    assert estados[-2].evento is None and estados[-1].evento == EVENTO_INCOMPLETA
    assert estados[-1].fase == "ascenso"


def test_jj_brazos_a_media_altura_se_corrigen():
    frames = []
    for _ in range(4):   # brazos hasta ~60°, pies abiertos
        for h in rampa(20, 60, 8) + rampa(60, 20, 8) + [20] * 4:
            frames.append(({"hombro_medio": h, "codo_medio": 160.0}, {"separacion_pies_hombros": 1.5}))
    assert "brazos_no_llegan_arriba" in _dichas("jumping_jacks", frames)


def test_marcha_pierna_estirada_dice_dobla_la_rodilla():
    frames = []
    for _ in range(4):   # la cadera solo llega a ~142° y la rodilla no se dobla
        for c in rampa(172, 142, 10) + rampa(142, 172, 10) + [172] * 6:
            frames.append(({"cadera_izq": c, "cadera_der": 172.0, "rodilla_izq": 172.0,
                            "rodilla_der": 175.0, "tronco_inclinacion": 4.0}, {}))
    assert _dichas("marcha_rodillas", frames)[0] == "rodilla_izq_extendida"
