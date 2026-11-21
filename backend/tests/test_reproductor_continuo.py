"""Salida de audio continua: cortar desde otro hilo no toca PortAudio (2026-11-20)."""

import threading
import time

import numpy as np

from estela.adaptadores.voz.motores import ReproductorContinuo


class FlujoFalso:
    """Llama al callback cada 10 ms con bloques de 256 muestras, como PortAudio."""

    llamadas_ajenas = 0

    def __init__(self, samplerate, channels, dtype, callback):
        self.cb, self._parar = callback, threading.Event()
        self.hilo = threading.Thread(target=self._bucle, daemon=True)

    def _bucle(self):
        while not self._parar.is_set():
            salida = np.ones((256, 1), np.int16)          # basura: debe quedar en silencio o audio
            self.cb(salida, 256, None, None)
            self.ultima = salida.copy()
            time.sleep(0.01)

    def start(self):
        self.hilo.start()

    def stop(self):
        self._parar.set()

    abort = stop

    def close(self):
        pass


class SdFalso:
    def OutputStream(self, **kw):
        return FlujoFalso(**kw)


def test_suena_entera_y_luego_silencio():
    r = ReproductorContinuo(SdFalso(), 22050)
    datos = np.arange(1, 1001, dtype=np.int16)
    t0 = time.perf_counter()
    r.reproducir(datos)
    assert time.perf_counter() - t0 < 1.0 and r.inicio_audio is not None
    time.sleep(0.03)
    assert not r._flujo.ultima.any()                     # sin repetir el último trozo
    r.cerrar()


def test_cortar_desde_otro_hilo_vuelve_enseguida():
    r = ReproductorContinuo(SdFalso(), 22050)
    largo = np.ones(22050 * 10, np.int16)                 # 10 s
    threading.Timer(0.1, r.detener).start()
    t0 = time.perf_counter()
    r.reproducir(largo)
    assert time.perf_counter() - t0 < 0.5
    time.sleep(0.03)
    assert not r._flujo.ultima.any()
    r.reproducir(np.arange(1, 300, dtype=np.int16))       # lo siguiente suena normal
    r.cerrar()


def test_si_el_flujo_muere_no_se_traba_y_se_vuelve_a_abrir():
    r = ReproductorContinuo(SdFalso(), 22050)
    viejo = r._flujo
    viejo.stop()                                          # dispositivo desconectado
    time.sleep(0.03)
    t0 = time.perf_counter()
    r.reproducir(np.ones(2205, np.int16))                 # 0,1 s + 2 s de tope
    assert time.perf_counter() - t0 < 3.0 and r._flujo is not viejo
    r.cerrar()
