"""Registro por repetición y aviso de movimiento equivocado (EXP-009)."""

import csv

import pytest

from estela.aplicacion.registro import RegistroRepeticiones, escribir_csv
from estela.aplicacion.rutina import cargar_catalogo, rutina_de_un_ejercicio
from estela.aplicacion.sesion import Sesion
from estela.dominio.conteo.segmentador import (
    EVENTO_COMPLETA, EVENTO_INCOMPLETA, EVENTO_INICIO, EstadoSegmento,
)
from estela.dominio.feedback.contrato import Observacion


@pytest.fixture(scope="module")
def catalogo():
    return cargar_catalogo()


def obs(t, angulos=None, distancias=None):
    a, d = angulos or {}, distancias or {}
    return Observacion(t_ms=t, ejercicio_id="x", angulos=a, distancias=d,
                       confianza={n: 1.0 for n in list(a) + list(d)})


def test_una_fila_por_repeticion_con_su_rango(catalogo, tmp_path):
    reg = RegistroRepeticiones(catalogo["jumping_jacks"])
    assert "separacion_pies_hombros" in reg.medidas and "codo_medio" in reg.medidas
    pasos = [(0, 1, EVENTO_INICIO, 60), (100, 1, None, 150), (200, 1, EVENTO_COMPLETA, 40),
             (300, 2, EVENTO_INICIO, 60), (400, 2, EVENTO_INCOMPLETA, 40)]
    for t, rep, ev, hombro in pasos:
        reg.actualizar(obs(t, {"hombro_medio": hombro}),
                       EstadoSegmento("x", rep, 0, 0, ev))
    assert [(f["rep"], f["resultado"]) for f in reg.filas] == [(1, "cuenta"), (2, "no_cuenta")]
    assert (reg.filas[0]["hombro_medio_min"], reg.filas[0]["hombro_medio_max"]) == (40, 150)

    ruta = tmp_path / "r.csv"
    escribir_csv([{"skill_id": "jumping_jacks", "repeticiones": reg.filas,
                   "mensajes": [{"repeticion": 2, "texto": "Abre más los pies."}]}], ruta)
    with open(ruta, encoding="utf-8-sig") as fh:
        filas = list(csv.DictReader(fh, delimiter=";"))
    assert filas[1]["frases"] == "Abre más los pies." and filas[0]["hombro_medio_max"] == "150"


def test_la_fila_guarda_el_dtw_del_frame_que_cierra_la_repeticion(catalogo):
    reg = RegistroRepeticiones(catalogo["jumping_jacks"])
    reg.actualizar(obs(0, {"hombro_medio": 60}), EstadoSegmento("x", 1, 0, 0, EVENTO_INICIO))
    cierre = Observacion(t_ms=900, ejercicio_id="x", angulos={"hombro_medio": 40},
                         confianza={"hombro_medio": 1.0}, progreso=0.6129,
                         coste_dtw=2.3456)
    reg.actualizar(cierre, EstadoSegmento("x", 1, 1, 0, EVENTO_COMPLETA))
    reg.actualizar(obs(1000, {"hombro_medio": 60}), EstadoSegmento("x", 2, 1, 0, EVENTO_INICIO))
    reg.actualizar(obs(1900, {"hombro_medio": 40}), EstadoSegmento("x", 2, 1, 1, EVENTO_INCOMPLETA))
    assert (reg.filas[0]["coste_dtw"], reg.filas[0]["progreso_dtw"]) == (2.35, 0.61)
    assert (reg.filas[1]["coste_dtw"], reg.filas[1]["progreso_dtw"]) == (None, None)


def test_isometrico_una_fila_por_bloque(catalogo):
    reg = RegistroRepeticiones(catalogo["plancha"])
    for t, bloque in ((0, 1), (1000, 1), (3000, 2), (4000, 2)):
        reg.actualizar(obs(t, {"rodilla_izq": 170.0 + bloque}), EstadoSegmento("x", bloque, 0, 0))
    reg.cerrar(5000)
    assert [(f["rep"], f["rodilla_izq_max"]) for f in reg.filas] == [(1, 171.0), (2, 172.0)]


class VozFalsa:
    def __init__(self):
        self.dichas = []

    def decir(self, texto, prioridad=0):
        self.dichas.append(texto)
        return True


def test_avisa_si_sube_la_otra_pierna(catalogo):
    voz = VozFalsa()
    s = Sesion(rutina_de_un_ejercicio("abduccion_cadera_izq", 5, catalogo), catalogo,
               estimador=None, voz=voz)
    p = s.paso_actual
    reposo = EstadoSegmento("abajo", 0, 0, 0)
    otra = {"abduccion_cadera_der": 25.0}
    assert s._revisa_movimiento_equivocado(p, obs(0, otra), reposo, 0) is None
    aviso = s._revisa_movimiento_equivocado(p, obs(1200, otra), reposo, 1200)
    assert aviso == "Ahora toca la pierna izquierda." and aviso in voz.dichas
    # subiendo la pierna correcta (fuera del reposo) no se avisa
    assert s._revisa_movimiento_equivocado(
        p, obs(5000, otra), EstadoSegmento("arriba", 1, 0, 0), 5000) is None
