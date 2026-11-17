"""Sin micrófono al arrancar: la escucha existe igual (la sección «Micrófono» de los
ajustes se ve), dice qué falta y al encenderla se vuelve a buscar la entrada."""

import argparse
import sys
import time
import types

import pytest

from estela import __main__ as principal
from estela import config
from estela.adaptadores.voz_entrada import microfono as mic


class _SdFalso(types.ModuleType):
    """`sounddevice` de mentira: `rondas` son las listas de dispositivos que verá,
    una por cada lectura tras volver a inicializar."""

    def __init__(self, rondas):
        super().__init__("sounddevice")
        self.rondas, self.ronda, self.reinicios = rondas, 0, 0
        self.default = types.SimpleNamespace(device=[0, 1])

    def query_devices(self, device=None):
        lista = self.rondas[min(self.ronda, len(self.rondas) - 1)]
        return lista if device is None else lista[device]

    def _terminate(self):
        self.reinicios += 1

    def _initialize(self):
        self.ronda += 1

    class InputStream:
        def __init__(self, **kw):
            self.kw = kw

        def start(self):
            pass

        def stop(self):
            pass

        def close(self):
            pass


ENTRADA = {"name": "iPhone", "max_input_channels": 1}
SALIDA = {"name": "Altavoces", "max_input_channels": 0}


def _usar(monkeypatch, rondas):
    falso = _SdFalso(rondas)
    monkeypatch.setitem(sys.modules, "sounddevice", falso)
    return falso


def test_sin_entradas_avisa_que_no_hay_microfono(monkeypatch):
    sd = _usar(monkeypatch, [[SALIDA]])
    assert mic.hay_microfono() == (False, mic.SIN_MICROFONO)
    with pytest.raises(mic.SinMicrofono):
        mic.Microfono()
    assert sd.reinicios == 1            # lo intentó una vez volviendo a leer el audio


def test_un_microfono_conectado_despues_se_encuentra_al_encender(monkeypatch):
    sd = _usar(monkeypatch, [[SALIDA], [SALIDA, ENTRADA]])
    m = mic.Microfono()
    assert sd.reinicios == 1 and m.dispositivo is None
    m.cerrar()


def test_con_microfono_no_se_reinicia_el_audio(monkeypatch):
    sd = _usar(monkeypatch, [[SALIDA, ENTRADA]])
    mic.Microfono().cerrar()
    assert sd.reinicios == 0


def _args():
    return argparse.Namespace(voz_entrada="si", voz_entrada_modo="llamada", guarda_eco=0.0)


def test_la_escucha_se_crea_sin_microfono_y_la_seccion_se_ve(monkeypatch, tmp_path):
    _usar(monkeypatch, [[SALIDA]])
    modelo = tmp_path / "ggml-small.bin"
    modelo.write_bytes(b"")
    monkeypatch.setattr(config, "modelo_voz_entrada", lambda *a, **k: modelo)

    class Reconocedor:
        def __init__(self, *a, **k):
            pass

        def precalentar(self):
            pass

    monkeypatch.setattr("estela.adaptadores.voz_entrada.reconocedor.ReconocedorWhisperCpp",
                        Reconocedor)
    escucha = principal._crear_escucha(_args(), voz=None, acciones={}, como_voy=lambda s: "")
    assert escucha is not None
    escucha.arrancar()
    try:
        for _ in range(50):             # el hilo intenta abrirlo y no puede
            if escucha.ajustes()["error"]:
                break
            time.sleep(0.05)
        ajustes = escucha.ajustes()
        assert "SinMicrofono" in ajustes["error"] and ajustes["encendido"] is False
    finally:
        escucha.cerrar()


def test_sin_modelo_sigue_sin_escucha(monkeypatch, tmp_path):
    _usar(monkeypatch, [[SALIDA, ENTRADA]])
    monkeypatch.setattr(config, "modelo_voz_entrada", lambda *a, **k: tmp_path / "no_existe.bin")
    assert principal._crear_escucha(_args(), voz=None, acciones={}, como_voy=lambda s: "") is None
