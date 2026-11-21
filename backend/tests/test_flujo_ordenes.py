"""Órdenes de la usuaria frente a lo que ESTELA está diciendo (Paula, 2026-11-17).

- Una orden de navegación (pausa, siguiente, anterior, reiniciar, terminar, listo)
  corta la frase que suena y tira lo pendiente.
"""

import threading
import time

from estela.adaptadores.interfaz.orquestador import Orquestador
from estela.adaptadores.voz.cola import DESCARTE_INTERRUMPIDA, ColaVoz
from estela.adaptadores.voz.motores import MotorVoz
from estela.aplicacion.puertos import PRIORIDAD_AVISO, PRIORIDAD_FEEDBACK
from estela.aplicacion.rutina import rutina_de_un_ejercicio
from tests.test_sesion import VozFalsa, catalogo  # noqa: F401 (fixture)


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
    for orden in ("siguiente", "anterior", "reiniciar", "pausar",
                  "listo", "terminar"):
        antes = voz.cortes
        getattr(o, orden)()
        assert voz.cortes == antes + 1, orden
    o.reanudar()                                                # seguir no corta nada
    assert voz.cortes == 6


