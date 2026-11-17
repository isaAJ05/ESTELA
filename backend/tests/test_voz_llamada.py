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
            "reiniciar_sesion", "reconocer_si", "reconocer_no", "voz_si", "voz_no")
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
    ("Estela, repite eso", cv.REPITE_ESO),
    ("Estela, ¿qué dijiste?", cv.REPITE_ESO),
    ("Estela, voz activada", cv.VOZ_SI),
    ("Estela, desactiva la voz", cv.VOZ_NO),
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
    # decidido por Paula: «reinicia» a secas es el ejercicio; «reiniciar todo», la sesión
    assert cv.interpretar("reiniciar").comando == cv.REINICIAR_EJERCICIO
    assert cv.interpretar("Reinicia.").comando == cv.REINICIAR_EJERCICIO
    assert cv.interpretar("reiniciar todo").comando == cv.REINICIAR_SESION
    assert cv.interpretar("reinicia la sesión").comando == cv.REINICIAR_SESION
    for dicho, comando in (("desactivar ángulos", cv.ANGULOS_NO), ("quita los ángulos", cv.ANGULOS_NO),
                           ("activar reconocimiento", cv.RECONOCER_SI),
                           ("apaga el reconocimiento", cv.RECONOCER_NO)):
        assert cv.interpretar(dicho).comando == comando


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
    assert hechas == ["pausar"] and voz.dichas == []      # «En pausa.» lo dice la sesión


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
    assert e._mostrar_te_escucho()                           # muestra «Te escucho»
    assert e.indicador() == {"encendido": True, "escuchando": True, "atenta": True}
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
    assert e.estado()["pantalla"] == {"angulos": True, "reconocer": None, "voz": None, "n": 1}
    e.atender(AUDIO)
    assert e.estado()["pantalla"] == {"angulos": False, "reconocer": None, "voz": None, "n": 2}


def test_seguir_durante_el_ejercicio_no_dice_seguimos():
    e, hechas, voz = _escucha("Estela, seguir")
    e.atender(AUDIO)
    assert hechas == [] and voz.dichas == []


def test_dolor_tambien_pide_llamar_a_estela():
    e, hechas, voz = _escucha("me duele la rodilla")
    e.atender(AUDIO)
    assert voz.dichas == [] and e.ignoradas == 1
    # no hace falta que sea la rodilla, y ante dolor se pausa sola
    for dicho in ("Estela, me duele la rodilla", "Estela, me duele la espalda", "Estela, tengo dolor"):
        e, hechas, voz = _escucha(dicho)
        e.atender(AUDIO)
        assert hechas == ["pausar"] and len(voz.dichas) == 1, dicho
        assert e.registro[-1]["motivo"] == "dolor"
    e, hechas, _ = _escucha("Estela, me duele", sesion=SesionFalsa(pausada=True))
    e.atender(AUDIO)
    assert hechas == []                                      # ya estaba en pausa


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


# -- guarda de eco ------------------------------------------------------------------

class MicrofonoDeUnaFrase:
    def __init__(self):
        self.entregada, self.descartes = False, 0

    def descartar(self):
        self.descartes += 1

    def escuchar_frase(self, cancelar, espera_s=1.0):
        if cancelar():
            return None
        time.sleep(0.01)
        if not self.entregada:
            self.entregada = True
            return AUDIO
        return None


def _hasta_que(condicion, plazo=3.0):
    fin = time.monotonic() + plazo
    while not condicion() and time.monotonic() < fin:
        time.sleep(0.01)


def test_la_guarda_de_eco_retrasa_la_escucha_tras_callar_estela():
    voz, hechas, mic = VozFalsa(), [], MicrofonoDeUnaFrase()
    voz.ocupada = True                                       # ESTELA habla
    e = EscuchaVoz(mic, ReconocedorDeLista("Estela, pausa"), voz,
                   {"pausar": lambda: hechas.append("pausar")}, llamada=True, guarda_eco_s=0.4)
    e.conectar(SesionFalsa())
    try:
        time.sleep(0.2)
        assert mic.entregada is False and mic.descartes > 0
        voz.ocupada = False                                   # calla
        t0 = time.monotonic()
        time.sleep(0.15)
        assert mic.entregada is False                         # aún en la guarda
        _hasta_que(lambda: hechas)
        assert hechas == ["pausar"] and time.monotonic() - t0 >= 0.25    # la guarda cuenta desde la última vez que se la oyó hablar
    finally:
        e.cerrar()


def test_sin_guarda_se_escucha_en_cuanto_calla_estela():
    voz, hechas, mic = VozFalsa(), [], MicrofonoDeUnaFrase()
    voz.ocupada = True
    e = EscuchaVoz(mic, ReconocedorDeLista("Estela, pausa"), voz,
                   {"pausar": lambda: hechas.append("pausar")}, llamada=True)
    e.conectar(SesionFalsa())
    try:
        time.sleep(0.15)
        voz.ocupada = False
        _hasta_que(lambda: hechas)
        assert hechas == ["pausar"]
    finally:
        e.cerrar()


# -- «repite eso», «voz activada/desactivada» y la precedencia de frases ----------------

def test_repetir_ya_no_es_una_orden_y_repite_eso_si():
    assert cv.interpretar("repite eso").comando == cv.REPITE_ESO
    assert cv.interpretar("dilo otra vez").comando == cv.REPITE_ESO
    # decidido por Paula (2026-11-16): «repetir» a secas se quitó; reiniciar tiene su orden
    for dicho in ("repite", "repetir", "otra vez", "de nuevo"):
        assert cv.interpretar(dicho).comando is None and cv.interpretar(dicho).pedir_repetir
    assert cv.interpretar("reinicia el ejercicio").comando == cv.REINICIAR_EJERCICIO
    # dos órdenes distintas y sin relación de frase siguen siendo ambiguas
    assert cv.interpretar("repite eso y pausa").motivo == cv.AMBIGUO


class VozConUltima(VozFalsa):
    """Como `ColaVoz`: recuerda lo último repetible y deja marcar lo que no lo es."""

    def __init__(self):
        super().__init__()
        self.ultima_repetible = None
        self._no = frozenset()

    def no_repetibles(self, textos):
        self._no = frozenset(textos)

    def decir(self, texto, prioridad=0):
        if texto not in self._no:
            self.ultima_repetible = texto
        return super().decir(texto, prioridad)


def test_repite_eso_repite_la_ultima_correccion_y_no_la_confirmacion_de_otra_orden():
    voz, hechas = VozConUltima(), []
    e = EscuchaVoz(MicrofonoNulo(), ReconocedorDeLista("Estela, pausa", "Estela, repite eso"), voz,
                   {a: (lambda a=a: hechas.append(a)) for a in ACCIONES}, llamada=True)
    e._sesion = SesionFalsa()
    voz.decir("Baja más la cadera", 0)                       # una corrección
    e.atender(AUDIO)                                         # «Pausa.» no cuenta como repetible
    e.atender(AUDIO)
    assert voz.dichas[-1] == ("Baja más la cadera", PRIORIDAD_AVISO)


def test_repite_eso_sin_nada_que_repetir_lo_dice():
    e, hechas, voz = _escucha("Estela, repite eso")
    e.atender(AUDIO)
    assert voz.dichas == [(cv.NO_HAY_QUE_REPETIR, PRIORIDAD_AVISO)] and hechas == []


def test_voz_activada_actua_y_confirma_pero_desactivada_no_dice_nada():
    e, hechas, voz = _escucha("Estela, voz activada", "Estela, voz desactivada")
    e.atender(AUDIO)
    assert hechas == ["voz_si"] and voz.dichas == [("Voz activada.", PRIORIDAD_AVISO)]
    assert e.estado()["pantalla"] == {"angulos": None, "reconocer": None, "voz": True, "n": 1}
    e.atender(AUDIO)
    assert hechas == ["voz_si", "voz_no"] and len(voz.dichas) == 1      # silenciada: no habla
    assert e.estado()["pantalla"]["voz"] is False and e.estado()["pantalla"]["n"] == 2


def test_reconocer_tambien_avisa_a_la_pantalla_para_que_su_boton_lo_siga():
    e, hechas, _ = _escucha("Estela, reconocer activado")
    e.atender(AUDIO)
    assert hechas == ["reconocer_si"]
    assert e.estado()["pantalla"] == {"angulos": None, "reconocer": True, "voz": None, "n": 1}


def test_la_cola_recuerda_lo_ultimo_repetible():
    from estela.adaptadores.voz.cola import ColaVoz
    from estela.adaptadores.voz.motores import MotorVoz

    class Mudo(MotorVoz):
        nombre = "mudo"

        def hablar(self, texto):
            pass

    cola = ColaVoz(Mudo())
    cola.no_repetibles({"Pausa."})
    cola.decir("Baja la cadera")
    cola.esperar_vacia()
    cola.decir("Pausa.")
    cola.esperar_vacia()
    assert cola.ultima_repetible == "Baja la cadera"
    cola.cerrar()


# -- notas de la sesión de Paula (2026-11-16) ----------------------------------------

@pytest.mark.parametrize("dicho, sesion, accion", [
    ("Estela, pausa", None, "pausar"),
    ("Estela, seguir", SesionFalsa(pausada=True), "reanudar"),
    ("Estela, seguir", SesionFalsa(colocando=True), "listo"),
    ("Estela, siguiente", None, "siguiente"),
    ("Estela, anterior", None, "anterior"),
])
def test_lo_que_la_sesion_ya_anuncia_no_se_dice_dos_veces(dicho, sesion, accion):
    e, hechas, voz = _escucha(dicho, sesion=sesion)
    e.atender(AUDIO)
    assert hechas == [accion] and voz.dichas == []


def test_con_la_sesion_real_seguimos_suena_una_sola_vez():
    """Lo que oyó Paula: «Seguimos.» dos veces al reanudar por voz."""
    from estela.aplicacion.rutina import cargar_catalogo, rutina_de_un_ejercicio
    catalogo = cargar_catalogo()
    from estela.aplicacion.sesion import AVISO_PAUSA, AVISO_REANUDA, Sesion
    from estela.aplicacion.pausa import USUARIA
    from tests.test_sesion import EstimadorFalso
    voz = VozFalsa()
    s = Sesion(rutina_de_un_ejercicio("jumping_jacks", 3, catalogo), catalogo,
               EstimadorFalso(tronco=10), voz)
    s.procesar(170.0, 0)
    e = EscuchaVoz(MicrofonoNulo(), ReconocedorDeLista("Estela, pausa", "Estela, seguir"), voz,
                   {"pausar": s.pausar, "reanudar": s.reanudar}, llamada=True)
    e._sesion = s
    antes = len(voz.dichas)
    e.atender(AUDIO)
    e.atender(AUDIO)
    dichas = [t for t, _ in voz.dichas[antes:]]
    assert dichas == [AVISO_PAUSA[USUARIA], AVISO_REANUDA]


def test_siguiente_en_el_ultimo_y_anterior_en_el_primero_lo_dicen_y_no_hacen_nada():
    sesion = SesionFalsa()
    sesion.hay_siguiente, sesion.hay_anterior = False, False
    e, hechas, voz = _escucha("Estela, siguiente", "Estela, anterior", sesion=sesion)
    e.atender(AUDIO)
    e.atender(AUDIO)
    assert hechas == []
    assert [t for t, _ in voz.dichas] == [cv.ES_EL_ULTIMO, cv.ES_EL_PRIMERO]


@pytest.mark.parametrize("dicho, comando", [
    ("Estela, silencio", cv.VOZ_NO), ("Estela, cállate", cv.VOZ_NO),
    ("Estela, háblame", cv.VOZ_SI), ("Estela, vuelve a hablar", cv.VOZ_SI),
    ("Estela, seguire.", cv.SEGUIR),                # así lo escribió Whisper en su sesión
    ("Estela activa reconocimiento.", cv.RECONOCER_SI),     # segunda sesión: no se entendió
    ("Estela activa y reconoce.", cv.RECONOCER_SI),
    ("Estela, desactiva reconocimiento", cv.RECONOCER_NO),
])
def test_silencio_hablame_y_lo_que_whisper_escribio_en_su_sesion(dicho, comando):
    llamado, resto = cv.separar_llamada(dicho)
    assert llamado and cv.interpretar(resto).comando == comando


def test_el_punto_del_microfono_dice_si_esta_encendido_escucha_y_esta_atenta():
    e, _, voz = _escucha("Estela")
    assert e.indicador() == {"encendido": True, "escuchando": True, "atenta": False}
    voz.ocupada = True                                       # habla ESTELA: no escucha
    e._sesion.puede_escuchar = False
    assert e.indicador() == {"encendido": True, "escuchando": False, "atenta": False}
    voz.ocupada, e._sesion.puede_escuchar = False, True
    e.atender(AUDIO)                                         # oyó «Estela»
    assert e.indicador()["atenta"] is True
    e._ventana_hasta = time.monotonic() - 1
    assert e.indicador()["atenta"] is False


# -- micrófono: apagar, encender, elegir y probar --------------------------------------

class MicrofonoDeFabrica(MicrofonoNulo):
    abiertos = []

    def __init__(self, dispositivo=None):
        self.dispositivo, self.cerrado, self.nivel = dispositivo, False, 0.25
        self.nombre = f"Micrófono {dispositivo}"
        self.frases = []
        MicrofonoDeFabrica.abiertos.append(self)

    def escuchar_frase(self, cancelar, espera_s=1.0):
        if cancelar():
            return None
        time.sleep(0.01)
        return self.frases.pop(0) if self.frases else None

    def cerrar(self):
        self.cerrado = True


def _con_fabrica(*textos, abrir=MicrofonoDeFabrica):
    MicrofonoDeFabrica.abiertos = []
    hechas, voz = [], VozFalsa()
    e = EscuchaVoz(None, ReconocedorDeLista(*textos), voz,
                   {a: (lambda a=a: hechas.append(a)) for a in ACCIONES}, llamada=True,
                   abrir_microfono=abrir)
    return e, hechas, voz


def test_apagar_cierra_el_microfono_y_encender_lo_vuelve_a_abrir():
    e, _, _ = _con_fabrica()
    e.arrancar()
    try:
        _hasta_que(lambda: e.microfono is not None)
        primero = e.microfono
        assert e.ajustes()["encendido"] and e.ajustes()["nivel"] == 0.25
        e.encender(False)
        _hasta_que(lambda: e.microfono is None)
        assert primero.cerrado and e.ajustes()["encendido"] is False
        assert e.indicador() == {"encendido": False, "escuchando": False, "atenta": False}
        e.encender(True)
        _hasta_que(lambda: e.microfono is not None)
        assert e.microfono is not primero and e.ajustes()["encendido"]
    finally:
        e.cerrar()


def test_elegir_otro_microfono_cierra_el_anterior_y_abre_el_nuevo():
    e, _, _ = _con_fabrica()
    e.arrancar()
    try:
        _hasta_que(lambda: e.microfono is not None)
        primero = e.microfono
        e.elegir_microfono(3)
        _hasta_que(lambda: e.microfono is not None and e.microfono.dispositivo == 3)
        assert primero.cerrado and e.ajustes()["elegido"] == 3
        assert e.ajustes()["nombre"] == "Micrófono 3"
    finally:
        e.cerrar()


def test_si_el_microfono_no_abre_queda_apagado_y_dice_por_que():
    def falla(dispositivo):
        raise OSError("no hay entrada")
    e, _, _ = _con_fabrica(abrir=falla)
    e.arrancar()
    try:
        _hasta_que(lambda: e.ajustes()["error"] is not None)
        a = e.ajustes()
        assert a["encendido"] is False and "no hay entrada" in a["error"]
    finally:
        e.cerrar()


def test_probar_muestra_lo_que_oye_sin_sesion_y_sin_ejecutar_nada():
    e, hechas, voz = _con_fabrica("Estela, pausa", "qué calor")
    e.arrancar()
    try:
        _hasta_que(lambda: e.microfono is not None)
        e.microfono.frases = [AUDIO]
        assert e.probar(5.0) and e.ajustes()["probando"]
        _hasta_que(lambda: e.ajustes()["prueba"] is not None)
        assert e.ajustes()["prueba"] == {"n": 1, "texto": "Estela, pausa", "llamada": True,
                                         "comando": cv.PAUSA}
        e.microfono.frases = [AUDIO]
        _hasta_que(lambda: e.ajustes()["prueba"]["n"] == 2)
        assert e.ajustes()["prueba"]["llamada"] is False and e.ajustes()["prueba"]["comando"] is None
        assert hechas == [] and voz.dichas == [] and e.registro == []   # ni actúa ni lo guarda
    finally:
        e.cerrar()


def test_no_se_puede_probar_con_el_microfono_apagado():
    e, _, _ = _con_fabrica()
    e.encender(False)
    assert e.probar() is False
