"""Fase de colocación al empezar cada ejercicio (T29) y estado de evaluación.

- Con `colocacion`, la sesión no cuenta ni corrige hasta que hay persona, la
  orientación es la del ejercicio y se ve el cuerpo entero durante
  `COLOCACION_ESTABLE_MS` seguidos, o hasta `terminar_colocacion()` («Listo»).
- Salir del encuadre mientras se coloca no pausa la sesión.
- El contrato expone la colocación y por qué no se evalúa.
"""

import numpy as np
import pytest

from estela.adaptadores.interfaz import contrato
from estela.adaptadores.pose.landmarks import muestra_desde_arrays
from estela.aplicacion.puertos import ResultadoPose
from estela.aplicacion.rutina import cargar_catalogo, rutina_de_un_ejercicio
from estela.aplicacion.sesion import (AVISO_COLOCADA, COLOCACION_ESTABLE_MS, MOTIVO_ANUNCIO,
                                      Sesion, _cuerpo_entero)
from tests.test_sesion import VozFalsa, correr, esqueleto_plancha

DT = 100                                   # ms por frame en `correr`


class EstimadorPlanchaEnImagen:
    """Plancha de perfil con landmarks de imagen dentro del frame.

    El «frame» es el hundimiento de la cadera; NaN = sin persona; None = la
    persona está, pero con los pies fuera del frame."""

    def estimar(self, frame, t_ms):
        if frame is not None and np.isnan(frame):
            return ResultadoPose(None, None, 1.0)
        mundo = esqueleto_plancha(0.0 if frame is None else float(frame))
        imagen = mundo.copy()
        imagen[:, :2] = 0.5 + 0.4 * mundo[:, :2]
        if frame is None:
            imagen[[25, 26, 27, 28], 0] = -0.2           # rodillas y tobillos fuera
        return ResultadoPose(muestra_desde_arrays(t_ms, mundo, imagen), imagen, 1.0)


@pytest.fixture(scope="module")
def catalogo():
    return cargar_catalogo()


def _sesion(catalogo, **kw):
    voz = VozFalsa()
    s = Sesion(rutina_de_un_ejercicio("plancha", 99, catalogo), catalogo,
               EstimadorPlanchaEnImagen(), voz, colocacion=True, **kw)
    return s, voz


def test_no_cuenta_ni_corrige_mientras_se_coloca(catalogo):
    s, voz = _sesion(catalogo)
    estados = correr(s, [None] * 60)                   # 6 s con los pies fuera
    assert all(e.colocando for e in estados)
    assert all(e.completadas == 0 for e in estados)
    assert voz.correcciones == []
    c = estados[-1].comprobaciones
    assert c == {"persona": True, "orientacion": True, "cuerpo_entero": False}
    assert "cabeza a los pies" in estados[-1].instruccion
    assert (AVISO_COLOCADA, 1) not in voz.dichas


def test_empieza_sola_tras_estar_bien_colocada(catalogo):
    s, voz = _sesion(catalogo)
    frames_estables = COLOCACION_ESTABLE_MS // DT
    estados = correr(s, [0.0] * (frames_estables + 1 + 80))
    i = next(k for k, e in enumerate(estados) if not e.colocando)
    assert i == frames_estables                        # 1,5 s después del primer frame bien
    assert any(t == AVISO_COLOCADA for t, _ in voz.dichas)
    assert estados[-1].completadas > 0                 # ya cuenta segundos
    assert estados[-1].comprobaciones is None and estados[-1].instruccion is None


def test_una_comprobacion_que_falla_reinicia_la_espera(catalogo):
    s, _ = _sesion(catalogo)
    # bien hasta 0,9 s, fallo en 1,0 s, bien desde 1,1 s: termina en 2,6 s
    estados = correr(s, [0.0] * 10 + [None] + [0.0] * 15)
    assert all(e.colocando for e in estados)
    assert not s.procesar(0.0, 26 * DT).colocando


def test_listo_termina_la_colocacion(catalogo):
    s, voz = _sesion(catalogo)
    correr(s, [None] * 5)
    s.terminar_colocacion()
    e = s.procesar(None, 5 * DT)
    assert not e.colocando
    assert any(t == AVISO_COLOCADA for t, _ in voz.dichas)


def test_salir_del_encuadre_al_colocarse_no_pausa(catalogo):
    s, voz = _sesion(catalogo)
    estados = correr(s, [float("nan")] * 80)           # 8 s sin persona
    assert not any(e.pausada for e in estados)
    assert all(e.aviso is None for e in estados)
    assert estados[-1].comprobaciones["persona"] is False
    assert not any("Pausa" in t for t, _ in voz.dichas)


def test_sin_colocacion_empieza_a_contar_ya(catalogo):
    voz = VozFalsa()
    s = Sesion(rutina_de_un_ejercicio("plancha", 99, catalogo), catalogo,
               EstimadorPlanchaEnImagen(), voz)
    estados = correr(s, [0.0] * 40)
    assert not any(e.colocando for e in estados) and estados[-1].completadas > 0


def test_cuerpo_entero_vale_con_un_lado_de_cada_grupo():
    imagen = np.full((33, 4), 0.5, np.float32)
    imagen[:, 3] = 0.99
    assert _cuerpo_entero(imagen)
    imagen[[12, 24, 26, 28], 3] = 0.1                  # lado lejano tapado
    assert _cuerpo_entero(imagen)
    imagen[27, 3] = 0.1                                # sin ningún tobillo
    assert not _cuerpo_entero(imagen)
    assert not _cuerpo_entero(None)


# -- contrato -------------------------------------------------------------------

def test_contrato_expone_la_colocacion(catalogo):
    s, _ = _sesion(catalogo)
    d = contrato.estado_a_dict(s.procesar(None, 0))
    assert d["colocacion"] == {"instruccion": s._instruccion(s.paso_actual.ejercicio),
                               "persona": True, "orientacion": True, "cuerpoEntero": False}
    assert d["evaluacion"] == {"evaluando": False, "motivo": contrato.NO_EVALUA_COLOCANDO}


def test_contrato_dice_por_que_no_evalua(catalogo):
    s, _ = _sesion(catalogo)
    s.terminar_colocacion()
    e = s.procesar(0.0, 0)
    assert contrato.estado_a_dict(e)["colocacion"] is None
    base = dict(colocando=False, pausada=False, persona=True, aviso=None, motivo_silencio=None)
    assert contrato.evaluacion(_estado(e, **base)) == {"evaluando": True, "motivo": None}
    casos = {
        "En pausa": dict(pausada=True),
        "No te veo": dict(persona=False),
        "Orientación incorrecta": dict(aviso="Colócate de perfil a la cámara."),
        "Escuchando una indicación": dict(motivo_silencio=MOTIVO_ANUNCIO),
        "No veo bien una parte del cuerpo": dict(motivo_silencio="confianza_baja"),
    }
    for motivo, cambios in casos.items():
        r = contrato.evaluacion(_estado(e, **{**base, **cambios}))
        assert r == {"evaluando": False, "motivo": motivo}, motivo
    # los silencios del motor que no son «no evaluar» siguen contando como evaluar
    for m in ("sin_error", "periodo_refractario", "evidencia_insuficiente"):
        assert contrato.evaluacion(_estado(e, **{**base, "motivo_silencio": m}))["evaluando"]


def _estado(e, **cambios):
    from dataclasses import replace
    return replace(e, **cambios)
