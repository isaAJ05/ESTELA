"""Segmentador de fases con señales sintéticas: fases, conteo y robustez."""

import pytest

from feedback.contrato import Observacion

from estela.conteo.segmentador import (
    EVENTO_COMPLETA, EVENTO_INCOMPLETA, SegmentacionInvalida,
    SegmentadorAlternante, SegmentadorCiclo, leer_senal, segmentador_desde_dict,
)
from estela.sesion.rutina import cargar_catalogo

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
    soportados = {k for k, e in catalogo.items() if e.soportado}
    assert soportados == {"sentadilla", "elevacion_brazos", "jumping_jacks",
                          "marcha_rodillas"}
    assert not catalogo["rotacion_tronco"].soportado
    for e in catalogo.values():
        if e.soportado:
            e.nuevo_segmentador()
