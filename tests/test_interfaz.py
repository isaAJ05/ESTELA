"""Contrato JSON y orquestador de la interfaz de escritorio (sin ventana).

El orquestador se prueba con la misma fuente sintética que `test_sesion`:
el «frame» lleva el ángulo de rodilla y el estimador falso construye el
esqueleto. Así se recorre el flujo inicio → sesión → resumen sin cámara.
"""

import json
import time

import numpy as np
import pytest

from estela.sesion.rutina import cargar_catalogo, rutina_desde_dict
from estela.sesion.sesion import (AVISO_ENCUADRE, AVISO_PAUSA, AVISO_SIN_PERSONA,
                                  Sesion)
from estela.ui import contrato
from estela.ui.orquestador import ERROR, INICIO, RESUMEN, SESION, Orquestador
from tests.test_sesion import (ZANCADA, EstimadorFalso, VozFalsa, correr,
                               secuencia_zancadas)


@pytest.fixture(scope="module")
def catalogo():
    return cargar_catalogo()


@pytest.fixture
def rutina(catalogo):
    return rutina_desde_dict({"nombre": "Prueba", "pasos": [
        {"skill_id": ZANCADA, "repeticiones": 2},
        {"skill_id": "plancha", "duracion_s": 20}]}, catalogo)


class FuenteLista:
    """Entrega los «frames» de una lista con t_ms cada 100 ms."""

    def __init__(self, frames, bloquear_al_final=False):
        self._frames = list(frames)
        self._i = 0
        self._bloquear = bloquear_al_final
        self.cerrada = False

    def leer(self):
        if self._i >= len(self._frames):
            if self._bloquear:                 # como una cámara sin frames nuevos:
                time.sleep(0.05)               # devuelve el último otra vez
                return self._frames[-1], self._i * 100 + 50
            return None
        f = self._frames[self._i]
        self._i += 1
        return f, self._i * 100

    def cerrar(self):
        self.cerrada = True


class EstimadorCerrable(EstimadorFalso):
    def __init__(self, tronco=10.0):
        super().__init__(tronco)
        self.cerrado = False

    def cerrar(self):
        self.cerrado = True


def esperar_fase(orq, fase, timeout=10.0):
    desde, limite = -1, time.monotonic() + timeout
    while time.monotonic() < limite:
        e = orq.estado(desde, espera_s=0.05)
        if e is not None:
            desde = e["version"]
            if e["fase"] == fase:
                return e
    raise AssertionError(f"no se llegó a la fase {fase} (última: {orq.fase})")


# -- contrato ----------------------------------------------------------------

def test_tipo_de_aviso():
    assert contrato.tipo_aviso(None) is None
    assert contrato.tipo_aviso(AVISO_ENCUADRE) == "encuadre"
    assert contrato.tipo_aviso(AVISO_SIN_PERSONA) == "sin_persona"
    assert contrato.tipo_aviso("Colócate de perfil a la cámara.") == "orientacion"
    assert all(contrato.tipo_aviso(t) == "pausa" for t in AVISO_PAUSA.values())
    assert contrato.tipo_aviso("otra cosa") == "otro"


def test_info_describe_la_rutina(catalogo, rutina):
    d = contrato.info(rutina, catalogo, espejo=True)
    assert d["version"] == contrato.VERSION
    assert [p["skillId"] for p in d["rutina"]["pasos"]] == [ZANCADA, "plancha"]
    assert d["rutina"]["pasos"][0]["orientacion"] == "perfil"
    assert d["rutina"]["pasos"][1]["unidad"] == "segundos"
    assert [11, 12] in d["conexiones"]
    # sin backend todavía: la interfaz no debe mostrarlas
    assert not any(d["capacidades"].values())
    json.dumps(d)


def test_estado_es_json_y_trae_campos_futuros_en_null(catalogo, rutina):
    s = Sesion(rutina, catalogo, EstimadorFalso(tronco=10), VozFalsa())
    estado = correr(s, secuencia_zancadas(1))[-1]
    d = contrato.estado_a_dict(estado, fps=29.97)
    json.dumps(d)
    assert d["ejercicioId"] == ZANCADA and d["completadas"] == 1
    assert len(d["puntos"]) == 33 and len(d["puntos"][0]) == 3
    assert d["depuracion"]["fps"] == 30.0
    for futuro in ("correctas", "conError", "nivel", "guia"):
        assert d[futuro] is None
    assert d["depuracion"]["motivoSilencio"] is None


def test_estado_recoge_un_campo_nuevo_del_backend(catalogo, rutina):
    """Cuando el backend añada `correctas` al estado, llega sin tocar el contrato."""
    s = Sesion(rutina, catalogo, EstimadorFalso(tronco=10), VozFalsa())
    estado = correr(s, secuencia_zancadas(1))[-1]

    class ConCorrectas:
        def __init__(self, base):
            self.__dict__.update(vars(base))
            self.correctas, self.con_error = 3, 1

    d = contrato.estado_a_dict(ConCorrectas(estado))
    assert (d["correctas"], d["conError"]) == (3, 1)


def test_pausa_y_mensajes_se_exponen(catalogo, rutina):
    voz = VozFalsa()
    s = Sesion(rutina, catalogo, EstimadorFalso(tronco=70), voz)
    estados = correr(s, secuencia_zancadas(2) + [float("nan")] * 80)
    assert estados[-1].pausada and estados[-1].motivo_pausa == "sin_persona"
    d = contrato.estado_a_dict(estados[-1])
    assert d["motivoPausa"] == "sin_persona" and d["avisoTipo"] == "pausa"


def test_mensajes_emitidos_cambia_aunque_se_repita_el_texto(catalogo):
    rutina = rutina_desde_dict({"pasos": [{"skill_id": ZANCADA, "repeticiones": 99}]},
                               catalogo)
    s = Sesion(rutina, catalogo, EstimadorFalso(tronco=70), VozFalsa())
    estados = correr(s, secuencia_zancadas(12))
    n = estados[-1].mensajes_emitidos
    assert n == sum(len(p["mensajes"]) for p in s.resumen()["pasos"]) and n >= 2


def test_resumen_para_la_interfaz(catalogo, rutina):
    s = Sesion(rutina, catalogo, EstimadorFalso(tronco=10), VozFalsa())
    correr(s, secuencia_zancadas(3))
    r = contrato.resumen_a_dict(s.resumen(), catalogo)
    json.dumps(r)
    assert r["rutina"] == "Prueba"
    assert r["pasos"][0]["nombre"].startswith("Zancada atrás estática")
    assert r["pasos"][0]["completadas"] == 2
    assert r["pasos"][0]["correctas"] is None and r["resumenTexto"] is None
    assert r["duracionTotalS"] == round(sum(p["duracionS"] for p in r["pasos"]), 1)
    texto = json.dumps(r)
    assert "puntos" not in texto and "landmarks" not in texto


# -- orquestador -------------------------------------------------------------

def nuevo_orquestador(catalogo, rutina, frames, bloquear=False, **kw):
    creados = {"fuentes": [], "estimadores": []}

    def abrir_fuente():
        f = FuenteLista(frames, bloquear)
        creados["fuentes"].append(f)
        return f

    def crear_estimador():
        e = EstimadorCerrable()
        creados["estimadores"].append(e)
        return e

    resumenes = []
    orq = Orquestador(rutina, catalogo, crear_estimador, abrir_fuente, VozFalsa(),
                      espejo=True, al_terminar=resumenes.append, **kw)
    return orq, creados, resumenes


def test_flujo_inicio_sesion_resumen(catalogo, rutina):
    frames = secuencia_zancadas(2) + [float("nan")] * 5
    orq, creados, resumenes = nuevo_orquestador(catalogo, rutina, frames)
    assert orq.estado(-1, 0)["fase"] == INICIO
    assert orq.iniciar()
    e = esperar_fase(orq, RESUMEN)
    assert e["sesion"] is None and e["frame"] is None
    assert e["resumen"]["pasos"][0]["completadas"] == 2
    assert len(resumenes) == 1                  # se imprimió/guardó una vez
    assert creados["fuentes"][0].cerrada and creados["estimadores"][0].cerrado
    json.dumps(e)


def test_estado_en_sesion_y_long_polling(catalogo, rutina):
    orq, _, _ = nuevo_orquestador(catalogo, rutina, secuencia_zancadas(50),
                                  bloquear=True)
    orq.iniciar()
    e = esperar_fase(orq, SESION)
    while e["sesion"] is None:
        e = orq.estado(e["version"], 1.0)
    assert e["sesion"]["ejercicioId"] == ZANCADA
    assert e["frame"] is None                   # el «frame» falso no es una imagen
    # sin cambios nuevos, estado() devuelve None tras la espera
    orq.terminar()
    fin = esperar_fase(orq, RESUMEN)
    assert orq.estado(fin["version"], 0.05) is None
    orq.cerrar()


def test_siguiente_y_terminar_desde_la_interfaz(catalogo, rutina):
    orq, _, resumenes = nuevo_orquestador(catalogo, rutina, [170.0] * 10_000,
                                          bloquear=True)
    orq.iniciar()
    e = esperar_fase(orq, SESION)
    orq.siguiente()
    while e["sesion"] is None or e["sesion"]["ejercicioId"] != "plancha":
        e = orq.estado(e["version"], 1.0) or e
    orq.terminar()
    fin = esperar_fase(orq, RESUMEN)
    assert not fin["resumen"]["terminada"]
    assert [p["skillId"] for p in fin["resumen"]["pasos"]] == [ZANCADA, "plancha"]
    assert len(resumenes) == 1


def test_repetir_rutina_abre_fuente_y_estimador_nuevos(catalogo, rutina):
    orq, creados, resumenes = nuevo_orquestador(catalogo, rutina, secuencia_zancadas(1))
    orq.iniciar()
    esperar_fase(orq, RESUMEN)
    assert orq.iniciar()
    esperar_fase(orq, RESUMEN)
    assert len(creados["fuentes"]) == 2 and len(creados["estimadores"]) == 2
    assert len(resumenes) == 2
    orq.volver_al_inicio()
    assert orq.fase == INICIO


def test_no_se_inicia_dos_veces(catalogo, rutina):
    orq, creados, _ = nuevo_orquestador(catalogo, rutina, [170.0] * 10_000,
                                        bloquear=True)
    assert orq.iniciar()
    assert not orq.iniciar()
    orq.terminar()
    esperar_fase(orq, RESUMEN)
    assert len(creados["fuentes"]) == 1


def test_error_al_abrir_la_camara(catalogo, rutina):
    intentos = []

    def abrir_fuente():
        intentos.append(1)
        if len(intentos) == 1:
            raise RuntimeError("no se pudo abrir la cámara 0")
        return FuenteLista(secuencia_zancadas(1))

    orq = Orquestador(rutina, catalogo, EstimadorCerrable, abrir_fuente, VozFalsa(),
                      espejo=True)
    orq.iniciar()
    e = esperar_fase(orq, ERROR)
    assert e["error"]["tipo"] == "fuente" and "cámara" in e["error"]["mensaje"]
    assert orq.iniciar()                        # «Reintentar»
    assert esperar_fase(orq, RESUMEN)["error"] is None


def test_error_al_cargar_el_modelo_cierra_la_fuente(catalogo, rutina):
    fuentes = []

    def abrir_fuente():
        fuentes.append(FuenteLista([]))
        return fuentes[-1]

    def crear_estimador():
        raise FileNotFoundError("No existe el modelo de pose")

    orq = Orquestador(rutina, catalogo, crear_estimador, abrir_fuente, VozFalsa(),
                      espejo=True)
    orq.iniciar()
    assert esperar_fase(orq, ERROR)["error"]["tipo"] == "modelo"
    assert fuentes[0].cerrada


def test_frame_real_se_envia_como_jpeg(catalogo, rutina):
    """Un frame BGR de verdad llega a la interfaz reducido a JPEG en base64."""
    import base64

    class EstimadorSinPersona(EstimadorCerrable):
        def estimar(self, frame, t_ms):
            return super().estimar(float("nan"), t_ms)

    imagen = np.zeros((720, 1280, 3), np.uint8)
    orq = Orquestador(rutina, catalogo, EstimadorSinPersona,
                      lambda: FuenteLista([imagen] * 10_000, True), VozFalsa(),
                      espejo=True)
    orq.iniciar()
    e = esperar_fase(orq, SESION)
    while e["frame"] is None:
        e = orq.estado(e["version"], 1.0) or e
    assert base64.b64decode(e["frame"])[:2] == b"\xff\xd8"     # cabecera JPEG
    assert e["sesion"]["puntos"] is None and not e["sesion"]["persona"]
    orq.terminar()
    esperar_fase(orq, RESUMEN)
