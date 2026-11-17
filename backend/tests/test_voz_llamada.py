"""Modo «llamada» de la voz de entrada: «Estela» + orden, también en movimiento,
y lo que no empieza por «Estela» se ignora sin decir nada."""

import time

import numpy as np
import pytest

from estela.adaptadores.voz_entrada.escucha import EscuchaVoz
from estela.adaptadores.voz_entrada.frases import FS
from estela.aplicacion import comandos_voz as cv
from estela.aplicacion.puertos import PRIORIDAD_AVISO



class VozFalsa:
    def __init__(self):
        self.dichas, self.ocupada = [], False

    def decir(self, texto, prioridad=0):
        self.dichas.append((texto, prioridad))
        return True


class _Pausa:
    def __init__(self, pausada):
        self.pausada = pausada


class _Paso:
    def __init__(self, pausada=False, colocando=False):
        self.pausa, self.colocando = _Pausa(pausada), colocando


class SesionFalsa:
    def __init__(self, pausada=False, colocando=False, entre=False):
        self.paso_actual = _Paso(pausada, colocando)
        self.entre_ejercicios = entre
        self.puede_escuchar = True            # con «llamada», también en movimiento
        self.oyente = None
        self.escucha_siempre = False


class MicrofonoNulo:
    def descartar(self):
        pass

    def escuchar_frase(self, cancelar, espera_s=1.0):
        time.sleep(0.01)
        return None

ACCIONES = ("pausar", "reanudar", "listo", "siguiente", "anterior", "reiniciar", "terminar",
            "reiniciar_sesion", "reconocer_si", "reconocer_no")
AUDIO = np.zeros(FS, np.float32)


class ReconocedorDeLista:
    """Devuelve una frase distinta en cada llamada."""

    def __init__(self, *textos):
        self.textos = list(textos)

    def transcribir(self, audio):
        return self.textos.pop(0)


def _escucha(*textos, sesion=None, llamada=True, como_voy=None):
    hechas, voz = [], VozFalsa()
    acciones = {a: (lambda a=a: hechas.append(a)) for a in ACCIONES}
    e = EscuchaVoz(MicrofonoNulo(), ReconocedorDeLista(*textos), voz, acciones, como_voy,
                   llamada=llamada)
    e._sesion = sesion or SesionFalsa()                  # en movimiento
    return e, hechas, voz


# -- «Estela» y la orden -------------------------------------------------------

@pytest.mark.parametrize("dicho, comando", [
    ("Estela, pausa", cv.PAUSA),
    ("Estela pausa por favor", cv.PAUSA),
    ("Oye Estela, siguiente", cv.SIGUIENTE),
    ("estela anterior", cv.ANTERIOR),
    ("Estela, reiniciar ejercicio", cv.REINICIAR_EJERCICIO),
    ("Estela, reconocer activado", cv.RECONOCER_SI),
    ("Estela, reconocer desactivado", cv.RECONOCER_NO),
    ("Estela, ángulos activados", cv.ANGULOS_SI),
    ("Estela, desactiva los ángulos", cv.ANGULOS_NO),
    ("Estella, terminar", cv.TERMINAR),
    ("Estela, ¿cómo voy?", cv.COMO_VOY),
])
def test_la_llamada_se_separa_y_la_orden_se_entiende(dicho, comando):
    llamado, resto = cv.separar_llamada(dicho)
    assert llamado and cv.interpretar(resto).comando == comando


@pytest.mark.parametrize("dicho", ["pausa", "hola buenos días", "ella dijo pausa",
                                   "la estrella pausa", "mira esta estela de humo"])
def test_sin_llamada_no_es_llamada(dicho):
    assert cv.separar_llamada(dicho)[0] is False


@pytest.mark.parametrize("dicho, comando", [
    ("Oye Stella, siguiente.", cv.SIGUIENTE),          # lo que escribió Whisper con la voz Mónica
    ("Estila.", None),
    ("Estela, activa los águlos.", cv.ANGULOS_SI),
    ("Estela. Desactiva los águlos.", cv.ANGULOS_NO),
])
def test_grafias_que_whisper_escribio_en_la_prueba(dicho, comando):
    llamado, resto = cv.separar_llamada(dicho)
    assert llamado and cv.interpretar(resto).comando == comando


def test_el_lexico_nuevo_no_se_confunde_con_el_resto():
    for forma in sum((cv.LEXICO[c] for c in cv.COMANDOS), ()):
        assert cv.interpretar(forma).comando is not None
    # reiniciar a secas, sin decir qué, no se adivina
    assert cv.interpretar("reiniciar").motivo == cv.SIN_COMANDO


# -- escuchar con el ejercicio en marcha ----------------------------------------

def test_en_modo_llamada_se_escucha_durante_el_ejercicio_y_en_el_otro_modo_no():
    assert cv.puede_escuchar(en_pausa=False, colocando=False, hablando=False, siempre=True)
    assert not cv.puede_escuchar(en_pausa=False, colocando=False, hablando=True, siempre=True)
    assert not cv.puede_escuchar(en_pausa=False, colocando=False, hablando=False, terminada=True,
                                 siempre=True)
    assert not cv.puede_escuchar(en_pausa=False, colocando=False, hablando=False)


def test_pausa_durante_el_ejercicio_con_llamada_pausa():
    e, hechas, voz = _escucha("Estela, pausa")
    e.atender(AUDIO)
    assert hechas == ["pausar"] and voz.dichas == [("Pausa.", PRIORIDAD_AVISO)]


def test_sin_estela_se_ignora_en_silencio_y_no_se_guarda_el_texto():
    e, hechas, voz = _escucha("pausa", "qué calor hace hoy, vamos a comer", "Hola, buenos días")
    for _ in range(3):
        e.atender(AUDIO)
    assert hechas == [] and voz.dichas == []                 # ni acción ni «no te entendí»
    assert e.ignoradas == 3
    assert all(r["texto"] is None and r["motivo"] == cv.SIN_LLAMADA for r in e.registro)
    assert e.registro[1]["palabras"] == 7
    assert "calor" not in repr(e.registro)                   # nunca el texto de lo ignorado
    assert e.estado() is None


def test_llamada_con_algo_que_no_es_orden_pide_repetir():
    e, hechas, voz = _escucha("Estela, qué calor hace")
    e.atender(AUDIO)
    assert hechas == [] and voz.dichas == [(cv.NO_ENTENDI, PRIORIDAD_AVISO)]
    assert e.estado()["noEntendi"]


def test_el_modo_antiguo_sigue_interpretando_todo():
    e, hechas, _ = _escucha("pausa", llamada=False, sesion=SesionFalsa(colocando=True))
    e.atender(AUDIO)
    assert hechas == ["pausar"]


# -- solo «Estela», y la orden en la frase siguiente -----------------------------

def test_solo_estela_abre_una_ventana_para_la_frase_siguiente():
    e, hechas, voz = _escucha("Estela.", "siguiente")
    e.atender(AUDIO)
    assert hechas == [] and voz.dichas == [] and e.estado()["activa"] is False
    assert e._indicador()                                    # muestra «Te escucho»
    e.atender(AUDIO)
    assert hechas == ["siguiente"]


def test_la_ventana_se_gasta_con_una_frase_y_caduca():
    e, hechas, _ = _escucha("estela", "siguiente", "pausa")
    e.atender(AUDIO)
    e.atender(AUDIO)
    e.atender(AUDIO)                                         # ya sin ventana: se ignora
    assert hechas == ["siguiente"] and e.ignoradas == 1
    e, hechas, _ = _escucha("estela", "siguiente")
    e.atender(AUDIO)
    e._ventana_hasta = time.monotonic() - 1                  # pasó el tiempo
    e.atender(AUDIO)
    assert hechas == [] and e.ignoradas == 1


# -- órdenes nuevas -------------------------------------------------------------

@pytest.mark.parametrize("dicho, accion, confirmacion", [
    ("Estela, anterior", "anterior", "Ejercicio anterior."),
    ("Estela, reiniciar ejercicio", "reiniciar", "Reiniciamos el ejercicio."),
    ("Estela, reconocer activado", "reconocer_si", "Reconocimiento activado."),
    ("Estela, reconocer desactivado", "reconocer_no", "Reconocimiento desactivado."),
    ("Estela, terminar", "terminar", "Terminamos."),
])
def test_ordenes_nuevas_llaman_a_la_accion(dicho, accion, confirmacion):
    e, hechas, voz = _escucha(dicho)
    e.atender(AUDIO)
    assert hechas == [accion] and voz.dichas == [(confirmacion, PRIORIDAD_AVISO)]


def test_angulos_no_tocan_la_sesion_pero_cambian_lo_que_muestra_la_pantalla():
    e, hechas, voz = _escucha("Estela, activa los ángulos", "Estela, oculta los ángulos")
    e.atender(AUDIO)
    assert hechas == [] and voz.dichas == [("Ángulos activados.", PRIORIDAD_AVISO)]
    assert e.estado()["pantalla"] == {"angulos": True, "n": 1}
    e.atender(AUDIO)
    assert e.estado()["pantalla"] == {"angulos": False, "n": 2}


def test_seguir_durante_el_ejercicio_no_dice_seguimos():
    e, hechas, voz = _escucha("Estela, seguir")
    e.atender(AUDIO)
    assert hechas == [] and voz.dichas == []


def test_dolor_tambien_pide_llamar_a_estela():
    e, hechas, voz = _escucha("me duele la rodilla")
    e.atender(AUDIO)
    assert voz.dichas == [] and e.ignoradas == 1
    e, hechas, voz = _escucha("Estela, me duele la rodilla")
    e.atender(AUDIO)
    assert hechas == [] and len(voz.dichas) == 1 and e.registro[-1]["motivo"] == "dolor"


# -- reiniciar la sesión pide confirmación -----------------------------------------

def test_reiniciar_sesion_pregunta_y_solo_con_un_si_lo_hace():
    e, hechas, voz = _escucha("Estela, reiniciar sesión", "Estela, sí")
    e.atender(AUDIO)
    assert hechas == [] and voz.dichas == [(cv.PREGUNTA_REINICIAR, PRIORIDAD_AVISO)]
    e.atender(AUDIO)
    assert hechas == ["reiniciar_sesion"]
    assert voz.dichas[-1] == (cv.CONFIRMA_REINICIAR, PRIORIDAD_AVISO)


def test_el_si_solo_vale_sin_decir_estela_mientras_espera():
    e, hechas, _ = _escucha("Estela, reinicia la sesión", "sí")
    e.atender(AUDIO)
    e.atender(AUDIO)
    assert hechas == ["reiniciar_sesion"]


@pytest.mark.parametrize("respuesta", ["no", "Estela, no", "cancela"])
def test_un_no_cancela(respuesta):
    e, hechas, _ = _escucha("Estela, reiniciar sesión", respuesta, "sí")
    e.atender(AUDIO)
    e.atender(AUDIO)
    e.atender(AUDIO)                                         # un sí tardío ya no vale
    assert hechas == []


def test_sin_respuesta_a_tiempo_no_se_reinicia_nada():
    e, hechas, _ = _escucha("Estela, reiniciar sesión", "Estela, sí")
    e.atender(AUDIO)
    e._pendiente_hasta = time.monotonic() - 1
    e.atender(AUDIO)                                         # «Estela, sí» ya no es respuesta
    assert hechas == []


def test_otra_cosa_mientras_espera_el_si_se_ignora_y_sigue_esperando():
    e, hechas, _ = _escucha("Estela, reiniciar sesión", "qué calor", "sí")
    e.atender(AUDIO)
    e.atender(AUDIO)
    e.atender(AUDIO)
    assert hechas == ["reiniciar_sesion"] and e.ignoradas == 1


def test_la_pista_del_modo_llamada_nombra_a_estela_una_sola_vez():
    """Con «Estela» repetida en la pista, Whisper la escribió sobre ruido puro."""
    from estela.adaptadores.voz_entrada.reconocedor import PISTA, PISTA_LLAMADA
    assert PISTA_LLAMADA.lower().count("estela") == 1 and "estela" not in PISTA.lower()
