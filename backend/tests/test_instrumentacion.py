"""Instrumentación para el Informe 2: no cambia el comportamiento por defecto.

- `Latencias.resumen()` añade media y máximo sin quitar las claves que lee la
  interfaz.
- `AlineadorDTW(banda=None)` es el DTW clásico; con banda, Sakoe-Chiba.
- `MotorDecision.disparadas` (detección cruda) no altera las decisiones.
- `Sesion(registrar=True)` guarda un registro por frame y decide igual.
- `ColaVoz.registro` mide encolado → inicio de habla.
"""

import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from estela.adaptadores.voz.cola import PRIORIDAD_AVISO, PRIORIDAD_FEEDBACK, ColaVoz
from estela.adaptadores.voz.motores import MotorVoz
from estela.aplicacion import dtw as modulo_dtw
from estela.aplicacion.dtw import AlineadorDTW, ventana_banda
from estela.aplicacion.metricas import Latencias
from estela.aplicacion.rutina import cargar_catalogo, rutina_de_un_ejercicio
from estela.aplicacion.sesion import Sesion
from tests.test_sesion import EstimadorPlancha, VozFalsa, correr


@pytest.fixture(scope="module")
def catalogo():
    return cargar_catalogo()


# -- Latencias ---------------------------------------------------------------

def test_resumen_de_latencias_anade_media_y_maximo():
    lat = Latencias()
    for v in (1.0, 2.0, 3.0, 10.0):
        lat.anota("pose", v)
    r = lat.resumen()["pose"]
    assert {"n", "p50_ms", "p95_ms"} <= set(r)          # lo que lee la interfaz
    assert r["n"] == 4 and r["media_ms"] == 4.0 and r["max_ms"] == 10.0
    assert r["p50_ms"] == 2.5
    assert lat.valores("pose") == [1.0, 2.0, 3.0, 10.0]
    assert lat.valores("nada") == []


# -- DTW -----------------------------------------------------------------------

def _referencia(m=20):
    u = np.linspace(0, 1, m)
    media = np.stack([100 * u, 50 * np.sin(np.pi * u)], axis=1)
    return {"medidas": ["a", "b"], "angulos": {"media": media.tolist()}}


def _obs(fila, rep=1):
    return SimpleNamespace(repeticion=rep, angulos={"a": fila[0], "b": fila[1]},
                           distancias={})


def _serie(n, m=20):
    u = np.linspace(0, 1, n)
    return np.stack([100 * u, 50 * np.sin(np.pi * u)], axis=1)


def test_dtw_sin_banda_igual_que_banda_enorme():
    ref = _referencia()
    a, b = AlineadorDTW(ref), AlineadorDTW(ref, banda=10_000)
    for fila in _serie(30):
        ra, rb = a.actualizar(_obs(fila)), b.actualizar(_obs(fila))
        assert ra == rb


def test_ventana_banda_contiene_las_esquinas():
    assert ventana_banda(1, 10, 10, None) == (1, 10)
    assert ventana_banda(1, 10, 10, 2) == (1, 3)
    assert ventana_banda(10, 10, 10, 2) == (8, 10)
    lo, hi = ventana_banda(1, 5, 40, 3)
    assert lo == 1 and hi == 4


def test_dtw_con_banda_limita_las_celdas_calculadas(monkeypatch):
    """Con banda b se calculan como mucho n·(2b+1) celdas."""
    llamadas = {"n": 0}
    original = modulo_dtw.np.mean

    def contar(*args, **kwargs):
        llamadas["n"] += 1
        return original(*args, **kwargs)

    a, b = _serie(30), _serie(30)
    monkeypatch.setattr(modulo_dtw.np, "mean", contar)
    modulo_dtw._dtw(a, b)
    clasico = llamadas["n"]
    llamadas["n"] = 0
    coste, camino = modulo_dtw._dtw(a, b, banda=2)
    assert clasico == 30 * 30
    assert llamadas["n"] <= 30 * 5
    assert coste == pytest.approx(0.0) and camino[-1] == (29, 29)


def test_dtw_con_banda_sin_camino_en_prefijos_muy_cortos():
    """Un prefijo de 2 frames contra 20 exige pendiente 19 > 2·1+1: sin camino."""
    al = AlineadorDTW(_referencia(20), banda=1)
    serie = _serie(20)
    assert al.actualizar(_obs(serie[0])) is None
    assert al.actualizar(_obs(serie[1])) is None
    assert al.longitud_prefijo == 2
    # con el prefijo completo sí hay camino
    for fila in serie[2:]:
        r = al.actualizar(_obs(fila))
    assert r is not None and r.coste == pytest.approx(0.0)


def test_dtw_clasico_cierra_siempre_en_la_ultima_celda():
    """Documenta el comportamiento actual (EXP-010): el camino acaba en (n, m),
    así que `progreso` es 1,0 aunque el prefijo vaya a mitad de repetición.
    Si se pasa a un DTW de extremo abierto, este test debe cambiar."""
    al = AlineadorDTW(_referencia(20))
    for fila in _serie(20)[:8]:
        r = al.actualizar(_obs(fila))
    assert r is not None and r.progreso == 1.0


def test_banda_negativa_se_rechaza():
    with pytest.raises(ValueError):
        AlineadorDTW(_referencia(), banda=-1)


# -- Sesión: registro por frame -----------------------------------------------

def _sesion(catalogo, registrar):
    return Sesion(rutina_de_un_ejercicio("plancha", 99, catalogo), catalogo,
                  EstimadorPlancha(), VozFalsa(), registrar=registrar)


def test_registro_no_cambia_las_decisiones(catalogo):
    angulos = [0.08] * 150
    con, sin = _sesion(catalogo, True), _sesion(catalogo, False)
    correr(con, angulos)
    correr(sin, angulos)
    assert con.resumen()["pasos"][0]["mensajes"] == sin.resumen()["pasos"][0]["mensajes"]
    assert sin.registro == []
    assert len(con.registro) == 150


def test_registro_por_frame_tiene_lo_que_piden_las_metricas(catalogo):
    s = _sesion(catalogo, True)
    correr(s, [0.08] * 150)
    reg = s.registro
    assert all({"t_ms", "persona", "pausada", "evaluado", "motivo_silencio",
                "mensaje", "disparadas", "repeticion", "lat"} <= set(e) for e in reg)
    con_mensaje = [e for e in reg if e["mensaje"]]
    msgs = s.resumen()["pasos"][0]["mensajes"]
    assert [e["t_ms"] for e in con_mensaje] == [m["t_ms"] for m in msgs]
    assert con_mensaje[0]["mensaje"]["error_id"] == "cadera_hundida"
    # detección cruda: la regla se dispara antes de que la política deje hablar
    primer_disparo = next(e["t_ms"] for e in reg if "cadera_hundida" in e["disparadas"])
    assert primer_disparo < con_mensaje[0]["t_ms"]
    # todo frame evaluado sin mensaje tiene motivo de silencio
    assert all(e["motivo_silencio"] for e in reg if e["evaluado"] and not e["mensaje"])
    # decisión y verbalización por separado
    assert "decision" in con_mensaje[0]["lat"] and "verbalizacion" in con_mensaje[0]["lat"]
    resumen = s.resumen()["latencias"]
    assert resumen["decision"]["n"] > resumen["verbalizacion"]["n"] >= 1


# -- Cola de voz ---------------------------------------------------------------

class MotorLento(MotorVoz):
    nombre = "lento"

    def __init__(self, espera=0.05):
        self.espera = espera

    def hablar(self, texto):
        time.sleep(self.espera)
        self.ultimo_inicio_audio = time.perf_counter()


def test_registro_de_la_cola_mide_encolado_a_inicio():
    cola = ColaVoz(MotorLento())
    cola.decir("uno")
    time.sleep(0.01)
    cola.decir("dos")                    # espera a que acabe «uno»
    cola.decir("tres")                   # sustituye a «dos»
    cola.cerrar()
    r = {e["texto"]: e for e in cola.registro}
    assert r["dos"]["descartada"] and r["dos"]["t_inicio"] is None
    assert not r["tres"]["descartada"]
    assert r["tres"]["t_inicio"] >= r["uno"]["t_fin"] - 1e-6
    # el motor avisa de cuándo empieza a sonar (tras «sintetizar»)
    assert r["uno"]["t_inicio_audio"] - r["uno"]["t_inicio"] >= 0.04
    assert len(cola.historial) == 2      # el historial antiguo no cambia


def test_registro_de_la_cola_marca_el_feedback_rechazado_por_un_aviso():
    evento = threading.Event()

    class Bloqueado(MotorVoz):
        def hablar(self, texto):
            evento.wait(1.0)

    cola = ColaVoz(Bloqueado())
    cola.decir("sonando")
    time.sleep(0.02)
    cola.decir("aviso", PRIORIDAD_AVISO)
    assert not cola.decir("corrección", PRIORIDAD_FEEDBACK)
    evento.set()
    cola.cerrar()
    r = {e["texto"]: e for e in cola.registro}
    assert r["corrección"]["descartada"] and not r["aviso"]["descartada"]
