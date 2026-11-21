"""Aviso al oír «Estela» y escucha sin huecos (Paula, 2026-11-20: «no me está
captando bien… apenas digo "Estela" quiero que me indique que me está
escuchando y que lo capte en cualquier momento»)."""

import time

import numpy as np
import pytest

from estela.adaptadores.voz.sonido import FS_SONIDO, NOTA_S, tono_llamada
from estela.adaptadores.voz_entrada import microfono as mm
from estela.adaptadores.voz_entrada.escucha import EscuchaVoz
from estela.adaptadores.voz_entrada.frases import BLOQUE, FS, DetectorDeFrase
from estela.aplicacion import comandos_voz as cv

POR_BLOQUE = BLOQUE / FS


def _bloques(segundos, rms):
    n = int(round(segundos / POR_BLOQUE))
    rng = np.random.default_rng(0)
    return [(rng.standard_normal(BLOQUE) * rms).astype(np.float32) for _ in range(n)]


def _mic(*tramos):
    """Micrófono sin dispositivo con la cola ya llena: [(segundos, rms), …]."""
    m = mm.Microfono.__new__(mm.Microfono)
    m.dispositivo = None
    m._preparar()
    for seg, rms in tramos:
        for b in _bloques(seg, rms):
            m._cola.put(b)
    return m


NUNCA = lambda: False                                          # noqa: E731


# -- «Estela» aunque no sea la primera palabra --------------------------------

@pytest.mark.parametrize("dicho, resto", [
    ("Uf, Estela, pausa", "pausa"),                    # respiración que Whisper escribió
    ("Ah, ah, vamos, Estela, siguiente", "siguiente"),
    ("Oye Estela", ""),
    ("eh eh eh eh eh Estela pausa", "pausa"),            # lejos, pero detrás viene una orden
    ("ya no puedo más Estela", ""),                     # al final: la orden vendrá después
    ("Estela, Estela, pausa", "estela pausa"),
])
def test_hallar_llamada_tolera_lo_que_va_antes(dicho, resto):
    llamado, r = cv.hallar_llamada(dicho)
    assert llamado and r == resto
    if "pausa" in resto or "siguiente" in resto:
        assert cv.interpretar(r).comando is not None


@pytest.mark.parametrize("dicho", ["pausa", "hola buenos días", "la estrella pausa",
                                   "uno dos tres cuatro estela de humo blanco"])
def test_hallar_llamada_sin_llamada(dicho):
    assert cv.hallar_llamada(dicho)[0] is False


# -- detector: trozo de la frase en curso, recorte y cebo -----------------------

def test_detector_da_el_trozo_en_curso_y_recorta():
    d = DetectorDeFrase()
    for b in _bloques(0.3, 0.001) + _bloques(3.0, 0.1):
        assert d.alimentar(b) is None
    assert d.en_frase and d.segundos_en_frase > 3.0
    assert len(d.ultimos(2.0)) == int(2.0 / POR_BLOQUE) * BLOQUE
    d.recortar(1.0)
    assert d.segundos_en_frase == pytest.approx(int(1.0 / POR_BLOQUE) * POR_BLOQUE)


def test_detector_cebado_antepone_lo_ya_oido():
    d = DetectorDeFrase()
    for b in _bloques(0.5, 0.001):
        d.alimentar(b)
    cebo = _bloques(1.0, 0.05)
    d.cebar(cebo)
    frase = None
    for b in _bloques(0.6, 0.2) + _bloques(0.7, 0.001):
        frase = d.alimentar(b) if frase is None else frase
    assert frase is not None
    assert len(frase) >= (len(cebo) + int(0.6 / POR_BLOQUE)) * BLOQUE      # el cebo entero va delante


# -- micrófono: aviso temprano y audio sin huecos ------------------------------

def test_aviso_temprano_durante_la_frase_recorta_y_sigue_con_la_frase_entera():
    m = _mic((0.3, 0.001), (4.0, 0.1), (0.8, 0.001))
    llamadas = []

    def al_avanzar(audio):
        llamadas.append(len(audio) / FS)
        return "oida" if len(llamadas) == 10 else None                # «Estela» a los ~3 s de frase

    frase = m.escuchar_frase(NUNCA, espera_s=0.01, al_avanzar=al_avanzar)
    assert frase is not None
    assert llamadas[0] >= mm.AVISO_MIN_S - POR_BLOQUE
    assert all(s <= mm.AVISO_VENTANA_S + POR_BLOQUE for s in llamadas[:10])  # antes: trozos de 2 s
    assert llamadas[10] > mm.AVISO_VENTANA_S                          # después: desde el recorte
    assert len(frase) / FS < 0.3 + 4.0 + 0.6 - 0.5                    # lo de antes del recorte no va
    assert not m._reciente                                            # la frase entregada no se vuelve a oír


def test_orden_lista_a_media_frase_se_entrega_sin_esperar_el_silencio():
    m = _mic((0.3, 0.001), (6.0, 0.1))                                # ruido continuo: no hay silencio
    r = iter(["oida", None, "lista"])
    frase = m.escuchar_frase(NUNCA, espera_s=0.01, al_avanzar=lambda a: next(r, None))
    assert frase is not None and len(frase) / FS < 3.5                # sin esperar al tope de 5 s
    assert not m._detector.en_frase and not m._reciente


@pytest.mark.parametrize("dicho, comando, sigue", [
    ("reinicia", cv.REINICIAR_EJERCICIO, True),                       # puede ser «reinicia todo»
    ("reinicia todo", cv.REINICIAR_SESION, False),
    ("vuelve", cv.ANTERIOR, True),                                    # «vuelve a hablar»
    ("pausa", cv.PAUSA, False),
    ("siguiente", cv.SIGUIENTE, False),
])
def test_puede_seguir_en_otra_orden(dicho, comando, sigue):
    assert cv.interpretar(dicho).comando == comando
    assert cv.puede_seguir(dicho, comando) is sigue


def test_sin_aviso_temprano_todo_como_antes():
    m = _mic((0.3, 0.001), (1.0, 0.1), (0.8, 0.001))
    frase = m.escuchar_frase(NUNCA, espera_s=0.01)
    assert frase is not None and len(frase) / FS > 1.0


def test_al_empezar_a_hablar_estela_lo_dicho_pasa_a_la_ventana():
    """Antes, cortar la frase porque ESTELA empezaba a hablar tiraba lo dicho."""
    m = _mic((0.3, 0.001), (0.8, 0.1))
    n = {"i": 0}

    def cancelar():                                                   # ESTELA empieza a mitad de frase
        n["i"] += 1
        return n["i"] > 30

    assert m.escuchar_frase(cancelar, espera_s=5.0) is None
    for b in _bloques(0.3, 0.05):
        m._cola.put(b)
    ventana = m.escuchar_ventana(NUNCA, ventana_s=2.5, paso_s=0.05)
    assert ventana is not None and len(ventana) / FS >= 0.9 + 0.3 - 2 * POR_BLOQUE


def test_al_callarse_estela_se_mira_la_ventana_y_la_frase_sigue_con_el_cebo():
    m = _mic((1.0, 0.05))
    m.escuchar_ventana(NUNCA, ventana_s=2.5, paso_s=0.3)              # hablaba ESTELA
    for b in _bloques(0.2, 0.05):
        m._cola.put(b)
    m.escuchar_ventana(NUNCA, ventana_s=2.5, paso_s=0.3)
    ventana = m.escuchar_ventana(NUNCA, ventana_s=2.5, paso_s=5.0, hasta=lambda: True)
    assert ventana is None                                            # nada nuevo desde la última
    for b in _bloques(0.4, 0.05):
        m._cola.put(b)
    m._tomar(); m._tomar()
    ventana = m.escuchar_ventana(NUNCA, ventana_s=2.5, paso_s=5.0, hasta=lambda: True)
    assert ventana is not None                                        # se mira al momento, sin esperar el paso
    assert len(m._detector._previo) == int(mm.CEBO_S / POR_BLOQUE)    # la frase siguiente lo lleva delante
    m.olvidar_ventana()
    assert not m._reciente and len(m._detector._previo) == 0          # tras actuar, no se vuelve a oír


# -- la escucha: aviso al momento ---------------------------------------------

class Voz:
    def __init__(self):
        self.dichas, self.ocupada, self.cedido = [], False, []

    def decir(self, texto, prioridad=0):
        self.dichas.append(texto)
        return True

    def ceder(self, segundos):
        self.cedido.append(segundos)

    def interrumpir(self):
        pass


class Sesion:
    puede_escuchar = True

    class paso_actual:
        colocando = False

        class pausa:
            pausada = False


class Rec:
    def __init__(self, *textos):
        self.textos = list(textos)

    def transcribir(self, audio):
        return self.textos.pop(0)


AUDIO = np.zeros(FS, np.float32)


def _escucha(*textos, interrumpir=False):
    hechas, sonidos, voz = [], [], Voz()
    acciones = {a: (lambda a=a: hechas.append(a)) for a in ("pausar", "siguiente", "reanudar")}
    e = EscuchaVoz(None, Rec(*textos), voz, acciones, llamada=True,
                   interrumpir_hablando=interrumpir, sonido=lambda: sonidos.append(1))
    e._sesion = Sesion()
    e._encendida = True
    return e, hechas, sonidos, voz


def test_estela_a_media_frase_suena_al_momento_y_la_orden_sale_de_la_frase_entera():
    e, hechas, sonidos, voz = _escucha("Uf, Estela", "Uf, Estela, siguiente")
    assert e._oir_temprano(AUDIO) == "oida"
    assert sonidos == [1] and voz.cedido == [cv.VENTANA_LLAMADA_S]
    e.microfono = object()
    assert e.indicador()["atenta"] is True                            # «Te escucho» antes de que calle
    i = e.atender(AUDIO)
    assert i.comando == cv.SIGUIENTE and hechas == ["siguiente"]
    assert sonidos == [1]                                             # no suena dos veces
    assert e._ventana_hasta == 0.0                                    # la próxima frase necesita «Estela»


def test_trozo_sin_estela_no_avisa():
    e, _, sonidos, _ = _escucha("uf uf")
    assert e._oir_temprano(AUDIO) is None and sonidos == []


def test_misma_orden_en_dos_trozos_seguidos_la_da_por_dicha():
    e, hechas, sonidos, _ = _escucha("Uf, Estela", "Uf, Estela, siguien", "Estela, siguiente",
                                     "Estela, siguiente", "Estela, siguiente")
    assert e._oir_temprano(AUDIO) == "oida"
    assert e._oir_temprano(AUDIO) is None                              # palabra a medias
    assert e._oir_temprano(AUDIO) is None                              # primera vez
    assert e._oir_temprano(AUDIO) == "lista"                           # segunda vez igual
    assert e.atender(AUDIO).comando == cv.SIGUIENTE and hechas == ["siguiente"] and sonidos == [1]


def test_orden_que_puede_seguir_en_otra_espera_al_final():
    e, _, _, _ = _escucha("Estela, reinicia", "Estela, reinicia", "Estela, reinicia")
    assert e._oir_temprano(AUDIO) == "oida"
    assert e._oir_temprano(AUDIO) is None and e._oir_temprano(AUDIO) is None


def test_si_la_frase_entera_ya_no_trae_estela_no_se_ejecuta_nada():
    """El trozo oyó «Estela» pero la frase entera no: puede ser ruido. Nada de
    esta frase se toma por orden; queda atenta a la siguiente."""
    e, hechas, sonidos, _ = _escucha("Estela", "¡Siguiente!")
    e._oir_temprano(AUDIO)
    i = e.atender(AUDIO)
    assert i.motivo == cv.SOLO_LLAMADA and hechas == []
    assert e._ventana_hasta > time.monotonic() and sonidos == [1]


def test_estela_a_secas_al_acabar_la_frase_tambien_suena():
    e, hechas, sonidos, _ = _escucha("Estela", "pausa")
    assert e.atender(AUDIO).motivo == cv.SOLO_LLAMADA and sonidos == [1]
    assert e.atender(AUDIO).comando == cv.PAUSA and hechas == ["pausar"]


def test_mientras_habla_suena_solo_si_falta_la_orden():
    e, hechas, sonidos, voz = _escucha("Estela, pausa", interrumpir=True)
    voz.ocupada = True
    e.atender_hablando(AUDIO)
    assert hechas == ["pausar"] and sonidos == []                     # la confirmación ya avisa
    e, hechas, sonidos, voz = _escucha("y luego Estela", "y luego Estela", interrumpir=True)
    voz.ocupada = True
    e.atender_hablando(AUDIO)
    assert sonidos == [1] and voz.dichas == [cv.DIME]


def test_tono_corto_y_sin_saturar():
    t = tono_llamada()
    assert t.dtype == np.int16 and 0 < np.abs(t).max() < 32767 * 0.5
    assert len(t) / FS_SONIDO < 2 * NOTA_S + 0.1


def test_tras_estela_a_secas_la_orden_sin_estela_tambien_sale_a_media_frase():
    e, hechas, _, _ = _escucha("Estela", "pausa", "pausa", "pausa")
    e.atender(AUDIO)                                                  # «Estela» a secas: atenta
    assert e._oir_temprano(AUDIO) is None and e._oir_temprano(AUDIO) == "lista"
    assert e.atender(AUDIO).comando == cv.PAUSA and hechas == ["pausar"]


def test_sin_estela_ni_ventana_los_trozos_no_dan_orden():
    e, _, sonidos, _ = _escucha("pausa", "pausa")
    assert e._oir_temprano(AUDIO) is None and e._oir_temprano(AUDIO) is None and sonidos == []
