"""Contrato JSON y orquestador de la interfaz de escritorio (sin ventana).

El orquestador se prueba con la misma fuente sintética que `test_sesion`:
el «frame» lleva el ángulo de rodilla y el estimador falso construye el
esqueleto. Así se recorre el flujo inicio → sesión → resumen sin cámara.

Como banco de pruebas se usa la zancada atrás, retirada del catálogo (ADR-005
§6, PR #8) pero todavía válida en `retirados/`, igual que en `test_decision`:
el esqueleto sintético de perfil es una zancada y estos tests prueban el
contrato y el orquestador, no el conjunto de ejercicios.
"""

import json
import time
from pathlib import Path

import numpy as np
import pytest

from estela.aplicacion.rutina import (RutinaInvalida, cargar_catalogo,
                                      rutina_de_un_ejercicio, rutina_desde_dict)
from estela.dominio.feedback.motor.skill import directorio_skills
from estela.aplicacion.sesion import (AVISO_ENCUADRE, AVISO_PAUSA, AVISO_SIN_PERSONA,
                                  Sesion, _preparar_guia)
from estela.adaptadores.interfaz import contrato
from estela.adaptadores.interfaz.orquestador import ERROR, INICIO, RESUMEN, SESION, Orquestador
from estela.adaptadores.interfaz.ventana import Api
from estela.adaptadores.voz.cola import ColaVoz
from estela.adaptadores.voz.motores import VozTexto
from tests.test_sesion import EstimadorFalso, VozFalsa, correr

ZANCADA = "zancada_atras_izq"


def secuencia_zancadas(n, minimo=80):
    una = list(np.linspace(170, minimo, 15)) + list(np.linspace(minimo, 170, 15)) + [170] * 10
    return una * n


@pytest.fixture(scope="module")
def catalogo():
    retirados = cargar_catalogo(Path(directorio_skills()) / "retirados")
    return {**cargar_catalogo(), ZANCADA: retirados[ZANCADA]}


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
    # solo las que ya tienen backend; el resto la interfaz no las muestra
    assert [k for k, v in d["capacidades"].items() if v] == [
        "correctasConError", "guia", "motivoSilencio", "colocacion", "rutinaPersonalizada",
        "silenciarVoz"]
    json.dumps(d)


def test_info_trae_el_catalogo_con_objetivos_por_defecto(catalogo, rutina):
    d = contrato.info(rutina, catalogo, espejo=True)
    por_id = {e["skillId"]: e for e in d["catalogo"]}
    assert por_id[ZANCADA]["objetivo"] == 2              # el de la rutina base
    assert por_id["plancha"]["unidad"] == "segundos"
    assert por_id["jumping_jacks"]["objetivo"] == contrato.OBJETIVO_POR_DEFECTO["repeticiones"]
    assert por_id["marcha_rodillas"]["conteo"] == "alternante"   # cada pierna cuenta una
    assert por_id["plancha"]["conteo"] == "isometrico"
    assert all(por_id[sid]["descripcion"] for sid in
               ("jumping_jacks", "abduccion_cadera_izq", "abduccion_cadera_der",
                "marcha_rodillas", "plancha"))
    assert (por_id["plancha"]["minimo"], por_id["plancha"]["maximo"]) ==         contrato.LIMITES_OBJETIVO["segundos"]


def test_rutina_desde_opciones(catalogo):
    r = contrato.rutina_desde_opciones(
        {"pasos": [{"skillId": "plancha", "objetivo": 30},
                   {"skillId": "jumping_jacks", "objetivo": 12}]}, catalogo)
    assert [(p.skill_id, p.repeticiones) for p in r.pasos] == [
        ("plancha", 30), ("jumping_jacks", 12)]
    assert r.nombre == "Rutina de entrenamiento"
    for malo in ({"pasos": []},
                 {"pasos": [{"skillId": "no_existe", "objetivo": 5}]},
                 {"pasos": [{"skillId": "plancha", "objetivo": 1}]},      # < 5 s
                 {"pasos": [{"skillId": "jumping_jacks", "objetivo": 500}]},
                 {"pasos": [{"skillId": "jumping_jacks", "objetivo": "x"}]}):
        with pytest.raises(RutinaInvalida):
            contrato.rutina_desde_opciones(malo, catalogo)


def test_estado_es_json_y_trae_campos_futuros_en_null(catalogo, rutina):
    s = Sesion(rutina, catalogo, EstimadorFalso(tronco=10), VozFalsa())
    estado = correr(s, secuencia_zancadas(1))[-1]
    d = contrato.estado_a_dict(estado, fps=29.97)
    json.dumps(d)
    assert d["ejercicioId"] == ZANCADA and d["completadas"] == 1
    assert len(d["puntos"]) == 33 and len(d["puntos"][0]) == 3
    assert d["depuracion"]["fps"] == 30.0
    assert d["nivel"] is None                       # aún sin backend
    assert isinstance(d["correctas"], int) and isinstance(d["conError"], int)
    assert d["guia"] is None  # la zancada de prueba no tiene referencia
    # el motor sí corrió en este frame: dice por qué no habló
    assert d["depuracion"]["motivoSilencio"] is not None


def test_estado_entrega_guia_animada_desde_referencia(catalogo):
    s = Sesion(rutina_de_un_ejercicio("jumping_jacks", 5, catalogo),
               catalogo, EstimadorFalso(tronco=10), VozFalsa())
    estado = s.procesar(170.0, 1000)
    d = contrato.estado_a_dict(estado)
    assert len(d["guia"]) == 33 and len(d["guia"][0]) == 3
    primero = d["guia"]
    estado = s.procesar(170.0, 1000 + round(1000 / 59.94005994005994))
    assert contrato.estado_a_dict(estado)["guia"] != primero


def test_referencias_de_guia_se_encuadran_sin_alterar_su_duracion(catalogo):
    for skill_id in ("jumping_jacks", "abduccion_cadera_izq",
                     "abduccion_cadera_der", "marcha_rodillas", "plancha"):
        referencia = catalogo[skill_id].referencia
        assert referencia is not None
        assert referencia["keypoints_2d"]
        assert referencia["fps"] > 0
        guia, _ = _preparar_guia(referencia)
        assert guia is not None
        assert guia.shape[1:] == (33, 4)
        assert np.all((guia[:, :, :2] >= 0) & (guia[:, :, :2] <= 1))


def test_feedback_tipado_llega_a_la_interfaz(catalogo):
    """Tronco muy inclinado: la corrección llega con segmento, lado,
    severidad y las articulaciones que la interfaz resalta."""
    rutina = rutina_desde_dict({"pasos": [{"skill_id": ZANCADA, "repeticiones": 99}]},
                               catalogo)
    s = Sesion(rutina, catalogo, EstimadorFalso(tronco=70), VozFalsa())
    estados = correr(s, secuencia_zancadas(4))
    d = contrato.estado_a_dict(estados[-1])
    json.dumps(d)
    fb = d["feedback"]
    assert fb["tipo"] == "correccion" and fb["texto"] == d["ultimoMensaje"]
    assert fb["segmento"] == "tronco" and fb["severidad"] in ("leve", "moderada", "alta")
    assert fb["errorId"] and fb["lado"]
    assert set(fb["puntos"]) <= set(range(33)) and fb["puntos"]
    # el resumen conserva el segmento de cada indicación
    r = contrato.resumen_a_dict(s.resumen(), catalogo)
    assert r["pasos"][0]["mensajes"][0]["segmento"] == "tronco"


def test_feedback_sin_mensajes_es_null(catalogo, rutina):
    s = Sesion(rutina, catalogo, EstimadorFalso(tronco=10), VozFalsa())
    d = contrato.estado_a_dict(correr(s, secuencia_zancadas(1))[-1])
    assert d["feedback"] is None


def test_refuerzo_no_nombra_segmento():
    from estela.dominio.feedback.contrato import MensajeFeedback
    fb = contrato.feedback_a_dict(MensajeFeedback("Vas bien.", None, "plantillas"))
    assert fb["tipo"] == "refuerzo" and fb["segmento"] is None and fb["puntos"] == []


@pytest.mark.parametrize("lado, esperado", [("izquierdo", [25]), ("derecho", [26]),
                                            ("bilateral", [25, 26]), ("na", [25, 26])])
def test_puntos_de_segmento_por_lado(lado, esperado):
    from estela.adaptadores.pose.landmarks import puntos_de_segmento
    assert puntos_de_segmento("rodilla", lado) == esperado
    assert puntos_de_segmento("desconocido", lado) == []


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
    p0 = r["pasos"][0]
    assert p0["correctas"] + p0["conError"] <= p0["completadas"] and r["resumenTexto"] is None
    assert r["duracionTotalS"] == round(sum(p["duracionS"] for p in r["pasos"]), 1)
    # panel técnico de T29: abstenciones por paso y latencia p50/p95 por etapa
    assert isinstance(r["pasos"][0]["abstenciones"], dict)
    assert r["tecnico"]["frames"] == s.frames
    assert {"p50Ms", "p95Ms", "n"} <= set(r["tecnico"]["latencias"]["pose"])
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
    # los esqueletos sintéticos no tienen coordenadas de imagen: sin colocación
    kw.setdefault("colocacion", False)
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
    assert e["resumen"]["motivoFin"] == "fuente"      # el «vídeo» se acabó
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
    assert fin["resumen"]["motivoFin"] == "usuaria"
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


def test_iniciar_con_rutina_personalizada_y_repetirla(catalogo, rutina):
    orq, _, _ = nuevo_orquestador(catalogo, rutina, secuencia_zancadas(1))
    api = Api(orq)
    assert not api.iniciar({"pasos": [{"skillId": ZANCADA, "objetivo": 999}]})
    assert orq.fase == INICIO
    assert api.iniciar({"pasos": [{"skillId": ZANCADA, "objetivo": 1}]})
    fin = esperar_fase(orq, RESUMEN)
    assert [(p["skillId"], p["objetivo"]) for p in fin["resumen"]["pasos"]] == [(ZANCADA, 1)]
    assert fin["resumen"]["motivoFin"] == "completada"
    # «Repetir rutina» repite la personalizada; info() sigue describiendo la base
    assert api.iniciar(None)
    fin = esperar_fase(orq, RESUMEN)
    assert [p["objetivo"] for p in fin["resumen"]["pasos"]] == [1]
    assert len(orq.info()["rutina"]["pasos"]) == 2


def test_configurar_silencia_y_reactiva_la_voz(catalogo, rutina):
    cola = ColaVoz(VozTexto())
    orq = Orquestador(rutina, catalogo, EstimadorCerrable, lambda: FuenteLista([], False),
                      cola, espejo=True)
    api = Api(orq)
    api.configurar({"voz": False})
    assert cola.silenciada
    api.configurar({"voz": "no"})          # solo booleanos
    api.configurar(None)
    assert cola.silenciada
    api.configurar({"voz": True})
    assert not cola.silenciada
    Api(nuevo_orquestador(catalogo, rutina, [])[0]).configurar({"voz": False})  # voz sin silenciar()
    cola.cerrar(esperar=False)


def test_rutina_personalizada_respeta_el_orden_y_terminar_libera_recursos(catalogo, rutina):
    orq, creados, _ = nuevo_orquestador(catalogo, rutina, [170.0] * 10_000, bloquear=True)
    assert Api(orq).iniciar({"pasos": [{"skillId": "plancha", "objetivo": 30},
                                       {"skillId": ZANCADA, "objetivo": 3}]})
    e = esperar_fase(orq, SESION)
    while e["sesion"] is None:
        e = orq.estado(e["version"], 1.0) or e
    assert (e["sesion"]["ejercicioId"], e["sesion"]["objetivo"]) == ("plancha", 30)
    assert e["sesion"]["totalPasos"] == 2
    orq.terminar()
    fin = esperar_fase(orq, RESUMEN)
    assert fin["resumen"]["motivoFin"] == "usuaria"
    assert [p["skillId"] for p in fin["resumen"]["pasos"]] == ["plancha"]
    assert creados["fuentes"][0].cerrada and creados["estimadores"][0].cerrado


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


def test_rutina_completa_termina_como_completada(catalogo):
    rutina = rutina_desde_dict({"pasos": [{"skill_id": ZANCADA, "repeticiones": 1}]}, catalogo)
    orq, _, _ = nuevo_orquestador(catalogo, rutina, secuencia_zancadas(3), bloquear=True)
    orq.iniciar()
    fin = esperar_fase(orq, RESUMEN)
    assert fin["resumen"]["terminada"] and fin["resumen"]["motivoFin"] == "completada"


def test_todo_segmento_del_contrato_se_puede_resaltar():
    from estela.adaptadores.pose.landmarks import puntos_de_segmento
    from estela.dominio.feedback.contrato import SEGMENTOS
    assert all(puntos_de_segmento(s, "bilateral") for s in SEGMENTOS)


def test_error_en_distancia_senala_un_angulo_sin_grados_falsos():
    """EXP-009: la cadera de la plancha se mide en distancia; en pantalla se
    señala la línea hombro–cadera–tobillo y no se muestran «0° fuera»."""
    from estela.dominio.feedback.contrato import (
        ErrorTipificado, Lado, MensajeFeedback, Severidad)
    err = ErrorTipificado("cadera_hundida", "cadera", Lado.BILATERAL, Severidad.LEVE,
                          "mantenimiento", 2, "plancha", magnitud=0.04,
                          medida="distancia:alineacion_cadera")
    fb = contrato.feedback_a_dict(MensajeFeedback("Sube la cadera.", err, "plantillas"))
    assert fb["angulos"] == ["alineacion_cuerpo_izq", "alineacion_cuerpo_der"]
    assert fb["magnitud"] is None
