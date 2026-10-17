"""DTW incremental de final abierto (aplicacion/dtw.py, ADR-004 §2.3, EXP-006).

Referencia sintética de 40 frames a 30 fps con tres medidas: `a` y `b` hacen
el movimiento (guían el alineamiento) y `c` es una medida de postura con poco
recorrido.
"""

import math

import numpy as np
import pytest

from estela.aplicacion.dtw import (ALINEADO, COSTE_ALTO, SIN_CAMINO, SIN_MEDIDAS,
                                   SIN_REFERENCIA, SIN_REPETICION, AlineadorDTW)
from estela.aplicacion.rutina import cargar_catalogo
from estela.dominio.feedback.contrato import (MOTIVO_DTW_NO_DISPONIBLE, ErrorTipificado,
                                              Observacion, Silencio)
from estela.dominio.feedback.motor.decision import MotorDecision
from estela.dominio.feedback.motor.skill import skill_desde_dict

M, FPS = 40, 30.0
NOMBRES = ("a", "b", "c")
_U = np.linspace(0, 1, M)
MEDIA = np.stack([20 + 100 * np.sin(np.pi * _U),
                  160 - 50 * np.sin(np.pi * _U) ** 2,
                  5 + 2 * np.sin(2 * np.pi * _U)], axis=1)


def referencia(media=MEDIA, **dtw):
    return {"medidas": list(NOMBRES), "fps": FPS, "tipo": "ciclico",
            "angulos": {"media": np.asarray(media).tolist()}, "dtw": dtw}


def obs(fila, t_ms, rep=1, confianza=None):
    angulos = {n: float(v) for n, v in zip(NOMBRES, fila) if v is not None}
    conf = confianza or {n: 0.9 for n in angulos}
    return Observacion(t_ms=t_ms, ejercicio_id="x", angulos=angulos,
                       confianza=conf, repeticion=rep)


def alinear(al, serie, rep=1, t0=0, fps=FPS):
    return [al.actualizar(obs(f, t0 + round(i * 1000 / fps), rep))
            for i, f in enumerate(serie)]


# ---------------------------------------------------------------------------
# Alineamiento
# ---------------------------------------------------------------------------

def test_misma_secuencia_coste_cero_y_progreso_lineal():
    res = alinear(AlineadorDTW(referencia()), MEDIA)
    assert [r.indice for r in res] == list(range(M))
    assert all(r.coste == 0.0 for r in res)
    assert res[0].progreso == 0.0 and res[-1].progreso == 1.0
    assert res[10].angulos_ref == pytest.approx(dict(zip(NOMBRES, MEDIA[10])))


def test_secuencia_mas_lenta_se_alinea():
    """Cada frame de la referencia dura dos frames: va a la mitad de ritmo."""
    res = alinear(AlineadorDTW(referencia()), np.repeat(MEDIA, 2, axis=0))
    assert [r.indice for r in res] == [i // 2 for i in range(2 * M)]
    assert all(r.coste == 0.0 for r in res)


def test_secuencia_mas_rapida_se_alinea():
    """Un frame de cada dos: va al doble de ritmo."""
    res = alinear(AlineadorDTW(referencia()), MEDIA[::2])
    assert all(abs(r.indice - 2 * i) <= 1 for i, r in enumerate(res))
    # cada frame saltado suma una diferencia entre frames vecinos: el coste
    # queda por debajo de lo que cambia la referencia de un frame al siguiente
    paso_medio = np.abs(np.diff(MEDIA, axis=0)).mean()
    assert res[-1].coste < paso_medio


def test_angulo_desplazado_20_grados_da_desviacion_de_20():
    """`c` no guía el alineamiento: el desplazamiento se mide casi entero.

    En el pico (frames 19 y 20, simétricos en `a` y `b`) el DTW elige el frame
    vecino en el que `c` queda más cerca y se come una fracción de grado.
    """
    desplazada = MEDIA + [0.0, 0.0, 20.0]
    al = AlineadorDTW(referencia())
    for i, fila in enumerate(desplazada):
        o = obs(fila, round(i * 1000 / FPS))
        r = al.actualizar(o)
        assert abs(r.indice - i) <= 1
        con_ref = Observacion(t_ms=o.t_ms, ejercicio_id="x", angulos=o.angulos,
                              confianza=o.confianza, angulos_ref=r.angulos_ref)
        assert con_ref.desviacion_de("c") == pytest.approx(20.0, abs=0.5)
        assert con_ref.desviacion_de("a") == pytest.approx(0.0, abs=0.5)


def test_reposo_largo_dentro_de_la_repeticion_queda_al_final():
    serie = np.vstack([MEDIA, np.repeat(MEDIA[-1:], 300, axis=0)])
    al = AlineadorDTW(referencia())
    res = alinear(al, serie)
    assert res[-1].indice == M - 1 and res[-1].coste == 0.0
    # solo se guarda una columna: el trabajo por frame no crece con la repetición
    assert len(al._acumulado) == M


# ---------------------------------------------------------------------------
# Máscara de confianza: excluir, nunca rellenar
# ---------------------------------------------------------------------------

def test_medida_con_confianza_baja_no_cuenta():
    sucia = AlineadorDTW(referencia())
    limpia = AlineadorDTW(referencia())
    for i, fila in enumerate(MEDIA):
        t = round(i * 1000 / FPS)
        conf = {"a": 0.9, "b": 0.9, "c": 0.2}
        r = sucia.actualizar(obs([fila[0], fila[1], 999.0], t, confianza=conf))
        esperado = limpia.actualizar(obs([fila[0], fila[1], None], t))
        assert (r.indice, r.coste) == (esperado.indice, esperado.coste)
    # la referencia sí tiene `c`: el motor decide con la confianza de la medida
    assert "c" in r.angulos_ref


def test_frame_sin_medidas_no_rompe_el_alineamiento():
    al = AlineadorDTW(referencia())
    res = []
    for i, fila in enumerate(MEDIA):
        conf = {n: 0.1 for n in NOMBRES} if i == 20 else None
        res.append(al.actualizar(obs(fila, round(i * 1000 / FPS), confianza=conf)))
    assert res[20] is None and al.motivos[SIN_MEDIDAS] == 1
    assert [r.indice for i, r in enumerate(res) if i != 20] == [
        i for i in range(M) if i != 20]
    # el frame 20 de la referencia se queda sin pareja: una diferencia mínima
    assert res[-1].coste < 0.01


# ---------------------------------------------------------------------------
# Repeticiones y disponibilidad
# ---------------------------------------------------------------------------

def test_reinicia_al_empezar_cada_repeticion():
    al = AlineadorDTW(referencia())
    alinear(al, MEDIA, rep=1)
    segunda = alinear(al, MEDIA[:5], rep=2, t0=5000)
    assert [r.indice for r in segunda] == [0, 1, 2, 3, 4]


def test_sin_repeticion_en_curso_no_alinea():
    al = AlineadorDTW(referencia())
    assert al.actualizar(obs(MEDIA[0], 0, rep=0)) is None
    assert al.actualizar(obs(MEDIA[0], 33, rep=None)) is None
    assert al.motivos == {SIN_REPETICION: 2}
    # tras reiniciar el segmentador la repetición 1 vuelve a empezar de cero
    alinear(al, MEDIA, rep=1)
    al.actualizar(obs(MEDIA[0], 5000, rep=0))
    assert al.actualizar(obs(MEDIA[0], 5033, rep=1)).indice == 0


def test_sin_referencia_ciclica_no_alinea():
    plancha = cargar_catalogo()["plancha"].referencia      # postura media, sin DTW
    for ref in (None, {}, plancha):
        al = AlineadorDTW(ref)
        assert not al.disponible
        assert al.actualizar(obs(MEDIA[0], 0)) is None
        assert al.motivos == {SIN_REFERENCIA: 1}


def test_coste_por_encima_del_limite_se_abstiene():
    desplazada = MEDIA + [0.0, 0.0, 20.0]          # coste local 20/3 ≈ 6,7
    estricto = AlineadorDTW(referencia(coste_maximo=5.0))
    assert alinear(estricto, desplazada)[-1] is None
    assert estricto.motivos == {COSTE_ALTO: M}
    holgado = AlineadorDTW(referencia(coste_maximo=10.0))
    assert alinear(holgado, desplazada)[-1].coste == pytest.approx(20 / 3)
    assert holgado.motivos == {ALINEADO: M}


def test_referencia_real_con_nulos_se_carga_como_nan():
    media = MEDIA.tolist()
    media[3][2] = None
    al = AlineadorDTW(referencia(media))
    res = alinear(al, MEDIA)
    assert res[3].indice == 3 and "c" not in res[3].angulos_ref
    assert res[-1].coste == 0.0


@pytest.mark.parametrize("skill_id", ["jumping_jacks", "abduccion_cadera_izq",
                                      "abduccion_cadera_der", "marcha_rodillas"])
def test_las_referencias_ciclicas_del_catalogo_se_alinean(skill_id):
    ref = cargar_catalogo()[skill_id].referencia
    media = np.asarray(ref["angulos"]["media"], dtype=float)
    al = AlineadorDTW(ref)
    for i, fila in enumerate(media):
        valores = dict(zip(ref["medidas"], fila))
        o = Observacion(t_ms=round(i * 1000 / ref["fps"]), ejercicio_id=skill_id,
                        angulos=valores, confianza={n: 0.9 for n in valores},
                        repeticion=1)
        r = al.actualizar(o)
    assert r.indice == len(media) - 1 and r.coste == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Banda Sakoe-Chiba
# ---------------------------------------------------------------------------

def test_banda_no_cambia_nada_al_ritmo_de_la_referencia():
    sin = alinear(AlineadorDTW(referencia()), MEDIA)
    con = alinear(AlineadorDTW(referencia(banda=4)), MEDIA)
    assert [(r.indice, r.coste) for r in con] == [(r.indice, r.coste) for r in sin]


def test_banda_limita_cuanto_se_deforma_el_tiempo():
    """Tres veces más lento que la referencia: sin banda se alinea bien; con
    banda el camino no puede alejarse del ritmo de la referencia y el coste
    lo delata."""
    lenta = np.repeat(MEDIA, 3, axis=0)
    sin = alinear(AlineadorDTW(referencia()), lenta)
    con = alinear(AlineadorDTW(referencia(banda=4)), lenta)
    assert [r.indice for r in sin] == [i // 3 for i in range(3 * M)]
    for i, r in enumerate(con):
        assert abs(r.indice - min(i, M - 1)) <= 4 + 1
    assert con[M // 2].coste > 5 * (sin[M // 2].coste + 1)


def test_banda_tras_la_duracion_de_la_referencia_se_queda_al_final():
    serie = np.vstack([MEDIA, np.repeat(MEDIA[-1:], 60, axis=0)])
    res = alinear(AlineadorDTW(referencia(banda=3)), serie)
    assert res[-1].indice == M - 1 and res[-1].coste == 0.0


def test_banda_tras_un_hueco_largo_pierde_el_camino():
    """Sin frames durante 1 s (sin persona) el centro de la banda salta: no
    hay camino hasta la siguiente repetición."""
    al = AlineadorDTW(referencia(banda=3))
    alinear(al, MEDIA[:5])
    assert al.actualizar(obs(MEDIA[5], 5 * 33 + 1000)) is None
    assert al.motivos[SIN_CAMINO] == 1
    assert al.actualizar(obs(MEDIA[0], 2000, rep=2)).indice == 0


# ---------------------------------------------------------------------------
# Interfaz con el motor: lo que consume una regla `desviacion`
# ---------------------------------------------------------------------------

def _motor_desviacion(nombre):
    return MotorDecision(skill_desde_dict({
        "skill_id": "x", "nombre": "X", "version": "0",
        "politica_silencio": {"repeticiones_evidencia": 1, "refractario_ms": 0,
                              "refractario_mismo_error_ms": 0},
        "reglas": [{"error_id": "desviada", "medida": {"tipo": "desviacion", "nombre": nombre},
                    "condicion": {"op": ">", "umbral": 10}, "segmento": "tronco",
                    "lado": "na", "plano": "cualquiera", "prioridad": 1}]}))


def _con_dtw(o, r):
    """Lo que hace la sesión: copia la salida del DTW en la observación."""
    if r is None:
        return o
    return Observacion(t_ms=o.t_ms, ejercicio_id=o.ejercicio_id, angulos=o.angulos,
                       distancias=o.distancias, confianza=o.confianza,
                       repeticion=o.repeticion, angulos_ref=r.angulos_ref,
                       progreso=r.progreso, coste_dtw=r.coste)


def test_regla_desviacion_se_evalua_con_la_salida_del_dtw():
    motor, al = _motor_desviacion("c"), AlineadorDTW(referencia())
    decisiones = []
    for i, fila in enumerate(MEDIA + [0.0, 0.0, 20.0]):
        o = obs(fila, round(i * 1000 / FPS))
        decisiones.append(motor.observar(_con_dtw(o, al.actualizar(o))))
    assert any(isinstance(d, ErrorTipificado) and d.error_id == "desviada"
               for d in decisiones)


def test_regla_desviacion_sobre_una_distancia():
    """La referencia guarda distancias (p. ej. `separacion_pies`) junto a los
    ángulos en `angulos_ref`; la desviación sale de `distancias`."""
    o = Observacion(t_ms=0, ejercicio_id="x", angulos={}, distancias={"c": 32.0},
                    confianza={"c": 0.9}, repeticion=1,
                    angulos_ref={"c": 20.0}, coste_dtw=1.0)
    assert o.desviacion_de("c") == pytest.approx(12.0)
    assert isinstance(_motor_desviacion("c").observar(o), ErrorTipificado)


def test_sin_dtw_la_regla_desviacion_se_abstiene_con_motivo_propio():
    motor = _motor_desviacion("c")
    for i, fila in enumerate(MEDIA + [0.0, 0.0, 20.0]):
        d = motor.observar(obs(fila, round(i * 1000 / FPS)))      # sin angulos_ref
        assert isinstance(d, Silencio) and d.motivo == MOTIVO_DTW_NO_DISPONIBLE
    assert motor.contador_abstenciones == {MOTIVO_DTW_NO_DISPONIBLE: M}


# ---------------------------------------------------------------------------
# La columna incremental da lo mismo que recalcular la repetición entera
# ---------------------------------------------------------------------------

def _dtw_completo(serie, media):
    """O(n·m), como `scripts/crear_referencia.py`, con final abierto."""
    n, m = len(serie), len(media)
    local = np.full((n, m), np.inf)
    for i in range(n):
        for j in range(m):
            d = np.abs(serie[i] - media[j])
            if np.isfinite(d).any():
                local[i, j] = d[np.isfinite(d)].mean()
    acum = np.full((n + 1, m + 1), np.inf)
    acum[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if np.isfinite(local[i - 1, j - 1]):
                acum[i, j] = local[i - 1, j - 1] + min(
                    acum[i - 1, j - 1], acum[i - 1, j], acum[i, j - 1])
    j = int(np.argmin(acum[n, 1:])) + 1
    i, jj, largo = n, j, 0
    while i > 0 and jj > 0:
        largo += 1
        k = int(np.argmin((acum[i - 1, jj - 1], acum[i - 1, jj], acum[i, jj - 1])))
        i, jj = ((i - 1, jj - 1), (i - 1, jj), (i, jj - 1))[k]
    return j - 1, acum[n, j] / largo


def test_incremental_igual_que_recalcular_todo():
    rng = np.random.default_rng(7)
    media = rng.normal(0, 30, (25, 3))
    media[rng.random(media.shape) < 0.1] = np.nan
    media[:, 0] = np.where(np.isnan(media[:, 0]), 0.0, media[:, 0])   # filas comparables
    serie = rng.normal(0, 30, (35, 3))
    serie[rng.random(serie.shape) < 0.2] = np.nan
    serie[:, 0] = np.where(np.isnan(serie[:, 0]), 1.0, serie[:, 0])
    al = AlineadorDTW(referencia(media))
    for i in range(len(serie)):
        fila = [None if math.isnan(v) else v for v in serie[i]]
        r = al.actualizar(obs(fila, round(i * 1000 / FPS)))
        indice, coste = _dtw_completo(serie[:i + 1], media)
        assert r.indice == indice
        assert r.coste == pytest.approx(coste, rel=1e-12)
