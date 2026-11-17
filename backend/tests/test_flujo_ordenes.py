"""Órdenes de la usuaria frente a lo que ESTELA está diciendo (Paula, 2026-11-17).

- Una orden de navegación (pausa, siguiente, anterior, reiniciar, terminar, listo)
  corta la frase que suena y tira lo pendiente.
- «Siguiente» a mitad de un ejercicio es un salto: sin «Muy bien, terminaste…» y
  sin resumen de la entrenadora.
- La confirmación de una orden suena después de la acción (no la corta).
- El LLM redacta las correcciones fuera del bucle por imagen.
"""

import threading
import time

import numpy as np

from estela.adaptadores.interfaz.orquestador import Orquestador
from estela.adaptadores.voz.cola import DESCARTE_INTERRUMPIDA, ColaVoz
from estela.adaptadores.voz.motores import MotorVoz
from estela.adaptadores.voz_entrada.escucha import EscuchaVoz
from estela.aplicacion import comandos_voz as cv
from estela.aplicacion.puertos import PRIORIDAD_AVISO, PRIORIDAD_FEEDBACK
from estela.aplicacion.rutina import rutina_de_un_ejercicio
from estela.aplicacion.sesion import Sesion
from estela.dominio.feedback.contrato import MensajeFeedback
from estela.dominio.feedback.verbalizador.plantillas import VerbalizadorPlantillas
from tests.test_entrenadora import _dos_planchas, catalogo  # noqa: F401 (fixture)
from tests.test_sesion import EstimadorPlancha, VozFalsa


class MotorQueEspera(MotorVoz):
    """«Habla» hasta que lo detienen (o pasan 5 s) y apunta lo dicho."""
    nombre = "espera"

    def __init__(self):
        self.empezadas, self.detenido = [], threading.Event()

    def hablar(self, texto):
        self.empezadas.append(texto)
        self.detenido.wait(5.0)
        self.detenido.clear()

    def detener(self):
        self.detenido.set()


def _esperar(cond, s=2.0):
    fin = time.monotonic() + s
    while not cond() and time.monotonic() < fin:
        time.sleep(0.005)
    return cond()


def test_interrumpir_corta_lo_que_suena_y_tira_lo_pendiente():
    motor = MotorQueEspera()
    cola = ColaVoz(motor)
    try:
        cola.decir("Te propongo seguir con el siguiente ejercicio.", PRIORIDAD_AVISO)
        assert _esperar(lambda: motor.empezadas)
        cola.decir("Ahora, plancha.", PRIORIDAD_AVISO)          # pendiente
        t0 = time.perf_counter()
        cola.interrumpir()
        assert _esperar(lambda: not cola.ocupada, 1.0)
        assert time.perf_counter() - t0 < 0.5                   # no esperó a que acabara
        assert cola.registro[0]["interrumpida"] and cola.interrumpidas == 1
        assert cola.registro[1]["motivo_descarte"] == DESCARTE_INTERRUMPIDA
        cola.decir("En pausa.", PRIORIDAD_AVISO)                # lo de después suena
        assert _esperar(lambda: motor.empezadas[-1] == "En pausa.")
    finally:
        motor.detener()
        cola.cerrar(esperar=False)


def test_silenciar_tambien_corta_lo_que_suena():
    motor = MotorQueEspera()
    cola = ColaVoz(motor)
    try:
        cola.decir("Una corrección larga.", PRIORIDAD_FEEDBACK)
        assert _esperar(lambda: motor.empezadas)
        cola.silenciar(True)
        assert _esperar(lambda: not cola.ocupada, 1.0)
    finally:
        cola.cerrar(esperar=False)


class VozQueSeCorta(VozFalsa):
    def __init__(self):
        super().__init__()
        self.cortes = 0

    def interrumpir(self):
        self.cortes += 1
        self.dichas.append(("<corte>", None))


def test_las_ordenes_de_navegacion_cortan_la_voz_y_reanudar_no(catalogo):
    voz = VozQueSeCorta()
    o = Orquestador(rutina_de_un_ejercicio("plancha", 5, catalogo), catalogo,
                    lambda: None, lambda: None, voz, espejo=False)
    for orden in ("siguiente", "anterior", "reiniciar", "reiniciar_sesion", "pausar",
                  "listo", "terminar"):
        antes = voz.cortes
        getattr(o, orden)()
        assert voz.cortes == antes + 1, orden
    o.reanudar()                                                # seguir no corta nada
    assert voz.cortes == 7


def test_siguiente_a_medias_no_felicita_ni_llama_a_la_entrenadora(catalogo):
    s, voz, eventos, reloj = _dos_planchas(catalogo, retencion_max_ms=60_000)
    s.terminar_colocacion()
    reloj.correr(5)
    s.siguiente()
    dichas = [t for t, _ in voz.dichas]
    assert not any(t.startswith("Muy bien, terminaste") for t in dichas)
    assert eventos == []                                      # sin resumen de un ejercicio a medias
    assert dichas[-1].startswith("Ahora, plancha")            # el anuncio sale ya, sin retener


def test_terminar_de_verdad_si_felicita_y_avisa_a_la_entrenadora(catalogo):
    s, voz, eventos, reloj = _dos_planchas(catalogo, retencion_max_ms=60_000)
    reloj.hasta(lambda e: len(eventos) == 1)
    assert ("Muy bien, terminaste plancha.", PRIORIDAD_AVISO) in voz.dichas


class SesionFalsa:
    def __init__(self):
        self.paso_actual = None
        self.puede_escuchar = True
        self.hay_siguiente = self.hay_anterior = True


def test_la_confirmacion_suena_despues_de_la_accion():
    orden = []

    class Voz(VozFalsa):
        def decir(self, texto, prioridad=0):
            orden.append(("dice", texto))
            return True

    acciones = {n: (lambda n=n: orden.append(("hace", n)))
                for n in ("terminar", "reiniciar", "pausar", "siguiente")}

    class Reconocedor:
        texto = ""

        def transcribir(self, audio):
            return self.texto

    rec = Reconocedor()
    e = EscuchaVoz(object(), rec, Voz(), acciones, llamada=True)
    e._sesion = SesionFalsa()
    rec.texto = "Estela, terminar"
    e.atender(np.zeros(160, np.float32))
    assert orden == [("hace", "terminar"), ("dice", cv.CONFIRMACION[cv.TERMINAR])]


# ---------------------------------------------------------------------------
# LLM fuera del bucle por imagen
# ---------------------------------------------------------------------------

class VerbalizadorLento(VerbalizadorPlantillas):
    """Tarda como un LLM y firma sus frases; tiene `fallback` como el de verdad."""
    nombre = "lento"

    def __init__(self, segundos=0.25):
        super().__init__()
        self.segundos = segundos
        self.fallback = VerbalizadorPlantillas()
        self.llamadas = 0

    def verbalizar(self, error):
        self.llamadas += 1
        time.sleep(self.segundos)
        return MensajeFeedback(texto="LLM: baja la cadera.", error=error, verbalizador=self.nombre)


def test_con_redaccion_aparte_el_bucle_no_espera_al_llm(catalogo):
    voz = VozFalsa()
    lento = VerbalizadorLento()
    s = Sesion(rutina_de_un_ejercicio("plancha", 99, catalogo), catalogo,
               EstimadorPlancha(), voz, verbalizador=lento, verbalizar_aparte=True)
    try:
        peor = 0.0
        for i in range(150):                                  # 15 s con la cadera caída
            t0 = time.perf_counter()
            s.procesar(0.08, i * 100)
            peor = max(peor, time.perf_counter() - t0)
            time.sleep(0.004)
        s._aparte.esperar(2.0)
        assert lento.llamadas >= 1
        assert peor < lento.segundos                          # ninguna imagen esperó al LLM
        correcciones = [t for t, p in voz.dichas if p == PRIORIDAD_FEEDBACK]
        assert correcciones and all(t == "LLM: baja la cadera." for t in correcciones)
        mensajes = s.resumen()["pasos"][0]["mensajes"]
        assert {m["texto"] for m in mensajes} == {"LLM: baja la cadera."}
        assert s.resumen()["verbalizacion_aparte"]["pedidas"] >= 1
        assert s.latencias.resumen()["verbalizacion"]["n"] >= 1
    finally:
        s.cerrar()


def test_la_redaccion_que_llega_en_pausa_no_se_dice(catalogo):
    voz = VozFalsa()
    lento = VerbalizadorLento(segundos=0.3)
    s = Sesion(rutina_de_un_ejercicio("plancha", 99, catalogo), catalogo,
               EstimadorPlancha(), voz, verbalizador=lento, verbalizar_aparte=True)
    try:
        i = 0
        while lento.llamadas == 0 and i < 300:
            s.procesar(0.08, i * 100)
            i += 1
        s.pausar()
        s._aparte.esperar(2.0)
        assert s.redactadas_tarde >= 1
        assert not any(t.startswith("LLM") for t, _ in voz.dichas)
    finally:
        s.cerrar()


def test_sin_redaccion_aparte_todo_sigue_como_antes(catalogo):
    voz = VozFalsa()
    s = Sesion(rutina_de_un_ejercicio("plancha", 99, catalogo), catalogo,
               EstimadorPlancha(), voz, verbalizador=VerbalizadorLento(0.0))
    for i in range(150):
        s.procesar(0.08, i * 100)
    assert s._aparte is None and "verbalizacion_aparte" not in s.resumen()
    assert any(t == "LLM: baja la cadera." for t, _ in voz.dichas)


# ---------------------------------------------------------------------------
# Modo «interrumpir»: escuchar mientras ESTELA habla (pregunta 11, 2026-11-17)
# ---------------------------------------------------------------------------

def test_buscar_llamada_la_encuentra_detras_de_la_voz_de_estela():
    assert cv.buscar_llamada("te propongo seguir con el Estela, pausa") == (True, "pausa")
    assert cv.buscar_llamada("Oye Estela siguiente") == (True, "siguiente")
    assert cv.buscar_llamada("baja la cadera") == (False, "baja la cadera")


def test_la_pregunta_de_reinicio_no_dice_estela():
    """Si ESTELA se oyera decir «Estela, sí», confirmaría sola el reinicio."""
    assert not any(p in cv.LLAMADAS for p in cv._limpiar(cv.PREGUNTA_REINICIAR).split())


class VozHablando(VozFalsa):
    ocupada = True
    texto_hablando = "Has hecho 3 repeticiones de jumping jacks."


def _escucha_hablando(texto, voz=None):
    hechas = []
    acciones = {n: (lambda n=n: hechas.append(n))
                for n in ("pausar", "reanudar", "listo", "siguiente", "anterior", "reiniciar",
                          "terminar", "voz_no")}

    class Rec:
        def transcribir(self, audio):
            return texto
    voz = voz or VozHablando()
    e = EscuchaVoz(object(), Rec(), voz, acciones, llamada=True, interrumpir_hablando=True)
    e._sesion = SesionFalsa()
    return e, hechas, voz


def test_mientras_habla_estela_pausa_corta_y_se_ejecuta():
    e, hechas, _ = _escucha_hablando("con el siguiente ejercicio Estela pausa")
    i = e.atender_hablando(np.zeros(160, np.float32))
    assert i.comando == cv.PAUSA and hechas == ["pausar"]
    assert e.registro[-1]["durante_voz"]


def test_mientras_habla_lo_que_no_interrumpe_se_ignora_callado():
    for dicho in ("Estela, ¿cómo voy?", "Estela, reiniciar todo", "Estela, blablá",
                  "te propongo seguir"):
        e, hechas, voz = _escucha_hablando(dicho)
        assert e.atender_hablando(np.zeros(160, np.float32)) is None
        assert hechas == [] and voz.dichas == [] and e.registro == []


def test_si_lo_que_suena_dice_estela_no_se_toma_por_orden():
    voz = VozHablando()
    voz.texto_hablando = "Soy Estela, pausa un momento si lo necesitas."
    e, hechas, _ = _escucha_hablando("Soy Estela pausa un momento", voz)
    assert e.atender_hablando(np.zeros(160, np.float32)) is None and hechas == []


def test_la_sesion_deja_escuchar_mientras_habla_solo_en_modo_interrumpir(catalogo):
    class VozOcupada(VozFalsa):
        ocupada = True
    s = Sesion(rutina_de_un_ejercicio("plancha", 5, catalogo), catalogo,
               EstimadorPlancha(), VozOcupada(), colocacion=True)
    s.procesar(0.0, 0)
    s.escucha_siempre = True
    assert not s.puede_escuchar
    s.escucha_hablando = True
    assert s.puede_escuchar


def test_interrumpir_sin_modo_llamada_no_se_activa():
    e = EscuchaVoz(object(), None, VozFalsa(), {}, llamada=False, interrumpir_hablando=True)
    assert not e.interrumpir_hablando


def test_la_sesion_avisa_al_estimador_de_los_momentos_sin_evaluacion(catalogo):
    """Con GPU, el cambio de detector (primera imagen lenta) espera a estos momentos."""
    class EstimadorQueEscucha(EstimadorPlancha):
        libres = 0

        def momento_libre(self):
            self.libres += 1
    est = EstimadorQueEscucha()
    s = Sesion(rutina_de_un_ejercicio("plancha", 99, catalogo), catalogo, est, VozFalsa(),
               colocacion=True)
    for i in range(5):
        s.procesar(0.0, i * 100)                  # colocándose
    assert est.libres == 5
    s.terminar_colocacion()
    antes = est.libres
    for i in range(5, 10):
        s.procesar(0.0, i * 100)                  # en marcha y sin aviso sonando
    assert est.libres == antes
