"""Órdenes de voz de punta a punta con audio sintético (nadie fue grabado):
corte de la frase, reconocimiento con Whisper y orden. Necesita el motor
(`pywhispercpp`) y el modelo descargado; si faltan, estos tests se saltan.
Los audios están en `tests/datos/voz/` (ver su LEEME.md)."""

import wave
from pathlib import Path

import numpy as np
import pytest

from estela import config
from estela.adaptadores.voz_entrada.frases import BLOQUE, FS, DetectorDeFrase
from estela.aplicacion import comandos_voz as cv
from estela.aplicacion.entrenadora import menciona_dolor

DATOS = Path(__file__).resolve().parent / "datos" / "voz"
pytest.importorskip("pywhispercpp", reason="falta el extra [voz-entrada]")
if not config.modelo_voz_entrada().exists():
    pytest.skip("falta el modelo de voz (scripts/descargar_modelos.py --voz-entrada)",
                allow_module_level=True)


def leer(nombre):
    with wave.open(str(DATOS / nombre)) as w:
        assert (w.getframerate(), w.getnchannels()) == (FS, 1)
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0


def frases_de(audio):
    d, sal = DetectorDeFrase(), []
    cola = np.concatenate([audio, np.zeros(FS, np.float32)])     # silencio que cierra la frase
    for i in range(0, len(cola) - BLOQUE + 1, BLOQUE):
        f = d.alimentar(cola[i:i + BLOQUE])
        if f is not None:
            sal.append(f)
    return sal


@pytest.fixture(scope="module")
def reconocedor():
    from estela.adaptadores.voz_entrada.reconocedor import ReconocedorWhisperCpp
    r = ReconocedorWhisperCpp(config.modelo_voz_entrada())
    r.precalentar()
    return r


@pytest.mark.parametrize("archivo, orden", [
    ("pausa.wav", cv.PAUSA), ("seguir.wav", cv.SEGUIR), ("siguiente.wav", cv.SIGUIENTE),
    ("terminar.wav", cv.TERMINAR), ("como_voy.wav", cv.COMO_VOY),
])
def test_cada_orden_hablada_se_corta_se_reconoce_y_se_entiende(reconocedor, archivo, orden):
    frases = frases_de(leer(archivo))
    assert len(frases) == 1                              # el detector saca una sola frase
    i = cv.interpretar(reconocedor.transcribir(frases[0]))
    assert (i.comando, i.motivo) == (orden, cv.ENTENDIDO)


def test_frase_sin_orden_pide_repetir(reconocedor):
    i = cv.interpretar(reconocedor.transcribir(leer("sin_orden.wav")))
    assert i.comando is None and i.pedir_repetir


def test_frase_de_dolor_se_reconoce_como_dolor_y_no_como_orden(reconocedor):
    texto = reconocedor.transcribir(leer("dolor.wav"))
    assert menciona_dolor(texto) and cv.interpretar(texto).comando is None


def test_silencio_no_produce_frase_ni_orden(reconocedor):
    silencio = leer("silencio.wav")
    assert frases_de(silencio) == []
    i = cv.interpretar(reconocedor.transcribir(silencio))
    assert i.comando is None and not i.pedir_repetir     # ni actúa ni pide repetir
