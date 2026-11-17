"""Voz de entrada sin micrófono ni modelo: el corte de frases con audio
sintético y la escucha con un micrófono y un reconocedor de prueba."""

import time

import numpy as np
import pytest

from estela.adaptadores.voz_entrada.escucha import EscuchaVoz
from estela.adaptadores.voz_entrada.frases import BLOQUE, FS, DetectorDeFrase
from estela.aplicacion import comandos_voz as cv
from estela.aplicacion.entrenadora import RESPUESTA_DOLOR
from estela.aplicacion.puertos import PRIORIDAD_AVISO


# -- corte de frases -----------------------------------------------------------

def _tono(segundos, amplitud=0.2, f=220.0):
    t = np.arange(int(segundos * FS)) / FS
    return (amplitud * np.sin(2 * np.pi * f * t)).astype(np.float32)


def _silencio(segundos, ruido=0.001, semilla=0):
    return np.random.default_rng(semilla).normal(0, ruido, int(segundos * FS)).astype(np.float32)


def _pasar(detector, audio):
    frases = []
    for i in range(0, len(audio) - BLOQUE + 1, BLOQUE):
        f = detector.alimentar(audio[i:i + BLOQUE])
        if f is not None:
            frases.append(f)
    return frases


def test_corta_una_frase_entre_silencios():
    audio = np.concatenate([_silencio(0.8), _tono(1.0), _silencio(1.2)])
    frases = _pasar(DetectorDeFrase(), audio)
    assert len(frases) == 1
    assert 1.0 <= len(frases[0]) / FS <= 2.1          # la voz, algo de antes y el silencio que la cierra


def test_dos_frases_separadas_salen_por_separado():
    audio = np.concatenate([_silencio(0.5), _tono(0.6), _silencio(1.0), _tono(0.6), _silencio(1.0)])
    assert len(_pasar(DetectorDeFrase(), audio)) == 2


def test_silencio_y_chasquido_no_son_frase():
    assert _pasar(DetectorDeFrase(), _silencio(3.0)) == []
    chasquido = np.concatenate([_silencio(0.5), _tono(0.06, 0.5), _silencio(1.5)])
    assert _pasar(DetectorDeFrase(), chasquido) == []


def test_frase_interminable_se_corta_en_el_tope():
    frases = _pasar(DetectorDeFrase(), np.concatenate([_silencio(0.3), _tono(8.0)]))
    assert frases and len(frases[0]) / FS <= 5.1


def test_el_ruido_de_fondo_sube_el_umbral():
    d = DetectorDeFrase()
    fondo = _silencio(2.0, ruido=0.02)                 # sala ruidosa
    assert _pasar(d, fondo) == []
    assert len(_pasar(d, np.concatenate([_tono(0.8, 0.3), _silencio(1.0, ruido=0.02)]))) == 1


# -- escucha -------------------------------------------------------------------

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
        self.puede_escuchar = pausada or colocando
        self.oyente = None


class Reconocedor:
    def __init__(self, texto):
        self.texto = texto

    def transcribir(self, audio):
        return self.texto


class MicrofonoNulo:
    def descartar(self):
        pass

    def escuchar_frase(self, cancelar, espera_s=1.0):
        time.sleep(0.01)
        return None


def _escucha(texto, sesion, como_voy=None):
    hechas, voz = [], VozFalsa()
    acciones = {a: (lambda a=a: hechas.append(a)) for a in
                ("pausar", "reanudar", "listo", "siguiente", "anterior", "reiniciar", "terminar")}
    e = EscuchaVoz(MicrofonoNulo(), Reconocedor(texto), voz, acciones, como_voy)
    e._sesion = sesion
    return e, hechas, voz


@pytest.mark.parametrize("texto, sesion, accion", [
    ("Pausa.", SesionFalsa(colocando=True), "pausar"),
    ("Seguir", SesionFalsa(pausada=True), "reanudar"),
    ("Sigue", SesionFalsa(colocando=True), "listo"),
    ("Siguiente", SesionFalsa(pausada=True), "siguiente"),
    ("Anterior", SesionFalsa(colocando=True, entre=True), "anterior"),
    ("Reinicia el ejercicio", SesionFalsa(pausada=True), "reiniciar"),
    ("Terminar", SesionFalsa(pausada=True), "terminar"),
])
def test_cada_orden_llama_a_la_accion_de_los_botones(texto, sesion, accion):
    e, hechas, voz = _escucha(texto, sesion)
    i = e.atender(np.zeros(FS, np.float32))
    assert hechas == [accion]
    assert voz.dichas == [(cv.CONFIRMACION[i.comando], PRIORIDAD_AVISO)]
    assert e.estado()["comando"] == i.comando and not e.estado()["noEntendi"]


def test_pausa_estando_en_pausa_no_hace_nada():
    e, hechas, _ = _escucha("pausa", SesionFalsa(pausada=True))
    e.atender(np.zeros(FS, np.float32))
    assert hechas == []


def test_como_voy_responde_la_entrenadora_y_no_toca_la_sesion():
    e, hechas, voz = _escucha("¿Cómo voy?", SesionFalsa(pausada=True),
                              como_voy=lambda sesion: "Llevas 2 ejercicios.")
    e.atender(np.zeros(FS, np.float32))
    assert hechas == [] and voz.dichas == [("Llevas 2 ejercicios.", PRIORIDAD_AVISO)]


def test_sin_orden_clara_pide_repetir_una_vez_y_no_actua():
    e, hechas, voz = _escucha("qué calor hace", SesionFalsa(pausada=True))
    e.atender(np.zeros(FS, np.float32))
    e.atender(np.zeros(FS, np.float32))                # enseguida otra vez: no insiste
    assert hechas == [] and voz.dichas == [(cv.NO_ENTENDI, PRIORIDAD_AVISO)]
    assert e.estado() == {"activa": False, "texto": "qué calor hace", "comando": None,
                          "noEntendi": True}


def test_silencio_reconocido_no_dice_nada():
    e, hechas, voz = _escucha("", SesionFalsa(pausada=True))
    e.atender(np.zeros(FS, np.float32))
    assert hechas == [] and voz.dichas == [] and e.estado() is None


def test_dolor_da_la_respuesta_fija_y_no_ejecuta_nada():
    e, hechas, voz = _escucha("me duele la rodilla, mejor terminar", SesionFalsa(pausada=True))
    e.atender(np.zeros(FS, np.float32))
    assert hechas == [] and voz.dichas == [(RESPUESTA_DOLOR, PRIORIDAD_AVISO)]
    assert e.registro[-1]["motivo"] == "dolor"


class MicrofonoDeUnaFrase:
    """Entrega una frase solo cuando se le deja escuchar, y cuenta lo descartado."""

    def __init__(self):
        self.entregadas, self.descartes = 0, 0

    def descartar(self):
        self.descartes += 1

    def escuchar_frase(self, cancelar, espera_s=1.0):
        if cancelar():
            return None
        time.sleep(0.01)
        if self.entregadas == 0:
            self.entregadas += 1
            return np.zeros(FS, np.float32)
        return None


def test_el_hilo_solo_atiende_cuando_la_sesion_deja_escuchar():
    sesion = SesionFalsa()                             # en movimiento: no se escucha
    voz, hechas, mic = VozFalsa(), [], MicrofonoDeUnaFrase()
    e = EscuchaVoz(mic, Reconocedor("siguiente"), voz, {"siguiente": lambda: hechas.append("siguiente")})
    e.conectar(sesion)
    try:
        time.sleep(0.3)
        assert hechas == [] and mic.entregadas == 0 and mic.descartes > 0
        assert e.estado() is None and sesion.oyente is e
        sesion.puede_escuchar = True                   # se pausa: ahora sí
        sesion.paso_actual = _Paso(pausada=True)
        fin = time.monotonic() + 3.0
        while not hechas and time.monotonic() < fin:
            time.sleep(0.02)
        assert hechas == ["siguiente"]
        assert e.estado()["activa"] and e.estado()["comando"] == cv.SIGUIENTE
    finally:
        e.cerrar()
