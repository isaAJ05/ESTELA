"""Espera de las correcciones en la cola de voz.

- Una corrección que espera más de `MAX_ESPERA_FEEDBACK_S` se descarta como
  «caducada» y se cuenta; la vigente suena; los avisos no caducan.
- `ColaVoz.anunciando` es True mientras suena o espera un aviso.
- La sesión no evalúa la técnica mientras suena un aviso (`MOTIVO_ANUNCIO`).
"""

import threading
import time

from estela.adaptadores.voz.cola import (DESCARTE_AVISO, DESCARTE_CADUCADA,
                                         DESCARTE_SUSTITUIDA, MAX_ESPERA_FEEDBACK_S,
                                         PRIORIDAD_AVISO, PRIORIDAD_FEEDBACK, ColaVoz)
from estela.adaptadores.voz.motores import MotorVoz
from estela.aplicacion.rutina import cargar_catalogo, rutina_de_un_ejercicio
from estela.aplicacion.sesion import MOTIVO_ANUNCIO, Sesion
from tests.test_sesion import EstimadorPlancha, VozFalsa, correr


class MotorControlado(MotorVoz):
    """Habla hasta que el test suelta `fin`; apunta lo que dijo."""
    nombre = "controlado"

    def __init__(self):
        self.fin = threading.Event()
        self.empezo = threading.Event()
        self.dichas = []

    def hablar(self, texto):
        self.dichas.append(texto)
        self.empezo.set()
        self.fin.wait(2.0)


def _espera(condicion, timeout=1.0):
    fin = time.monotonic() + timeout
    while not condicion() and time.monotonic() < fin:
        time.sleep(0.005)
    return condicion()


def test_el_defecto_es_un_segundo():
    assert MAX_ESPERA_FEEDBACK_S == 1.0


def test_correccion_que_espera_demasiado_se_descarta_como_caducada():
    motor = MotorControlado()
    cola = ColaVoz(motor, max_espera_feedback_s=0.05)
    cola.decir("Ahora, plancha.", PRIORIDAD_AVISO)
    assert motor.empezo.wait(1.0)
    cola.decir("Sube la cadera.", PRIORIDAD_FEEDBACK)   # espera al aviso
    time.sleep(0.1)                                     # > 0,05 s
    motor.fin.set()
    cola.cerrar()
    assert motor.dichas == ["Ahora, plancha."]
    r = {e["texto"]: e for e in cola.registro}
    assert r["Sube la cadera."]["descartada"]
    assert r["Sube la cadera."]["motivo_descarte"] == DESCARTE_CADUCADA
    assert r["Sube la cadera."]["t_inicio"] is None
    assert cola.descartes == {DESCARTE_CADUCADA: 1} and cola.descartadas == 1


def test_correccion_vigente_suena():
    motor = MotorControlado()
    motor.fin.set()                                     # habla al instante
    cola = ColaVoz(motor, max_espera_feedback_s=0.5)
    cola.decir("Sube la cadera.", PRIORIDAD_FEEDBACK)
    cola.cerrar()
    assert motor.dichas == ["Sube la cadera."]
    assert not cola.registro[0]["descartada"] and cola.descartes == {}


def test_los_avisos_no_caducan():
    motor = MotorControlado()
    cola = ColaVoz(motor, max_espera_feedback_s=0.01)
    cola.decir("Corrección.", PRIORIDAD_FEEDBACK)
    assert motor.empezo.wait(1.0)
    cola.decir("Pausa.", PRIORIDAD_AVISO)               # espera a la corrección
    time.sleep(0.05)
    motor.fin.set()
    cola.cerrar()
    assert motor.dichas == ["Corrección.", "Pausa."]


def test_descartes_por_causa():
    motor = MotorControlado()
    cola = ColaVoz(motor)
    cola.decir("sonando", PRIORIDAD_FEEDBACK)
    assert motor.empezo.wait(1.0)
    cola.decir("vieja", PRIORIDAD_FEEDBACK)
    cola.decir("nueva", PRIORIDAD_FEEDBACK)             # sustituye a «vieja»
    cola.decir("aviso", PRIORIDAD_AVISO)                # sustituye a «nueva»
    assert not cola.decir("tapada", PRIORIDAD_FEEDBACK)  # el hueco es del aviso
    motor.fin.set()
    cola.cerrar()
    r = {e["texto"]: e["motivo_descarte"] for e in cola.registro}
    assert r == {"sonando": None, "vieja": DESCARTE_SUSTITUIDA,
                 "nueva": DESCARTE_SUSTITUIDA, "aviso": None, "tapada": DESCARTE_AVISO}
    assert cola.descartes == {DESCARTE_SUSTITUIDA: 2, DESCARTE_AVISO: 1}


def test_anunciando_mientras_suena_o_espera_un_aviso():
    motor = MotorControlado()
    cola = ColaVoz(motor)
    assert not cola.anunciando
    cola.decir("Corrección.", PRIORIDAD_FEEDBACK)
    assert motor.empezo.wait(1.0)
    assert not cola.anunciando                          # suena una corrección
    cola.decir("Ahora, plancha.", PRIORIDAD_AVISO)
    assert cola.anunciando                              # el aviso espera
    motor.empezo.clear()
    motor.fin.set()
    assert motor.empezo.wait(1.0)
    assert _espera(lambda: motor.dichas == ["Corrección.", "Ahora, plancha."])
    cola.cerrar()
    assert not cola.anunciando


# -- sesión ---------------------------------------------------------------------

class VozAnunciando(VozFalsa):
    """Voz con un aviso sonando durante los primeros `hasta_ms` de vídeo."""

    def __init__(self, sesion_t_ms, hasta_ms):
        super().__init__()
        self._t_ms, self.hasta_ms = sesion_t_ms, hasta_ms

    @property
    def anunciando(self):
        return self._t_ms() < self.hasta_ms


def test_la_sesion_no_corrige_mientras_suena_un_aviso():
    catalogo = cargar_catalogo()
    rutina = rutina_de_un_ejercicio("plancha", 99, catalogo)
    s = Sesion(rutina, catalogo, EstimadorPlancha(), VozFalsa())
    voz = VozAnunciando(lambda: s._t_ms, hasta_ms=1e9)  # todo el rato
    s.voz = voz
    estados = correr(s, [0.08] * 150)                   # 15 s con la cadera caída
    assert voz.correcciones == []
    assert s.resumen()["pasos"][0]["mensajes"] == []
    assert {e.motivo_silencio for e in estados} == {MOTIVO_ANUNCIO}
    assert estados[-1].completadas > 0                  # el conteo sigue


def test_la_sesion_corrige_cuando_acaba_el_aviso():
    catalogo = cargar_catalogo()
    rutina = rutina_de_un_ejercicio("plancha", 99, catalogo)
    s = Sesion(rutina, catalogo, EstimadorPlancha(), VozFalsa(), registrar=True)
    voz = VozAnunciando(lambda: s._t_ms, hasta_ms=3000)
    s.voz = voz
    correr(s, [0.08] * 200)                             # 20 s
    msgs = s.resumen()["pasos"][0]["mensajes"]
    assert msgs and all(m["t_ms"] >= 3000 for m in msgs)
    assert {m["error_id"] for m in msgs} == {"cadera_hundida"}
    durante = [e for e in s.registro if e["t_ms"] < 3000]
    assert durante and not any(e["evaluado"] for e in durante)
    assert all(e["motivo_silencio"] == MOTIVO_ANUNCIO for e in durante)
