"""`aplicacion/reconocimiento.py` (EXP-010): avisa si el movimiento no es el
ejercicio elegido, sin falsas alarmas con el ejercicio correcto ni estando quieta."""

import json
import math

import numpy as np
import pytest

from estela.aplicacion import reconocimiento as R
from estela.dominio.feedback.contrato import Observacion

FPS = 30
BASE = {"hombro_izq": 20.0, "hombro_der": 20.0, "codo_medio": 170.0,
        "separacion_pies_hombros": 0.6, "abduccion_cadera_izq": 5.0,
        "abduccion_cadera_der": 5.0, "cadera_izq": 175.0, "cadera_der": 175.0,
        "rodilla_izq": 175.0, "rodilla_der": 175.0, "tronco_inclinacion": 5.0}


def _jj(fase):           # fase en [0, 1): brazos arriba y pies abiertos a la vez
    a = math.sin(math.pi * fase)
    return {**BASE, "hombro_izq": 20 + 140 * a, "hombro_der": 20 + 140 * a,
            "separacion_pies_hombros": 0.6 + 1.2 * a}


def _marcha(fase):       # una rodilla y luego la otra
    izq = math.sin(2 * math.pi * fase) if fase < 0.5 else 0.0
    der = math.sin(2 * math.pi * (fase - 0.5)) if fase >= 0.5 else 0.0
    return {**BASE, "cadera_izq": 175 - 80 * izq, "cadera_der": 175 - 80 * der,
            "rodilla_izq": 175 - 90 * izq, "rodilla_der": 175 - 90 * der}


def _referencia(movimiento, frames=30):
    return [[movimiento(i / frames)[m] for m in R.MEDIDAS] for i in range(frames)]


def _refs():
    return R.Referencias({
        "medidas": list(R.MEDIDAS),
        "escala": [10.0 if m != "separacion_pies_hombros" else 0.2 for m in R.MEDIDAS],
        "referencias": [{"clase": "jumping_jacks", "tipo": "ciclico", "media": _referencia(_jj)},
                        {"clase": "marcha_rodillas", "tipo": "ciclico",
                         "media": _referencia(_marcha)}]})


def _obs(t_ms, medidas):
    dist = {"separacion_pies_hombros": medidas["separacion_pies_hombros"]}
    ang = {k: v for k, v in medidas.items() if k not in dist}
    return Observacion(t_ms=t_ms, ejercicio_id="x", angulos=ang, distancias=dist,
                       confianza={k: 1.0 for k in medidas})


def _sentadilla(fase):    # no se parece a ninguna referencia ni a otra clase
    a = math.sin(math.pi * fase)
    return {**BASE, "codo_medio": 170 - 110 * a, "tronco_inclinacion": 5 + 40 * a,
            "cadera_izq": 175 - 80 * a, "cadera_der": 175 - 80 * a,
            "rodilla_izq": 175 - 80 * a, "rodilla_der": 175 - 80 * a}


def _avisos(elegido, movimiento, segundos=12, periodo_s=1.0, cuenta_propio=False):
    """`cuenta_propio`: el segmentador del elegido cierra una repetición por periodo."""
    rec = R.ReconocedorEjercicio(elegido, _refs())
    salida = []
    for i in range(segundos * FPS):
        t = round(i * 1000 / FPS)
        fase = (i / FPS / periodo_s) % 1.0
        cierra = cuenta_propio and i % round(periodo_s * FPS) == 0
        salida.append(rec.actualizar(_obs(t, movimiento(fase)), cierra))
    return salida


def test_con_el_ejercicio_elegido_no_avisa():
    assert not any(_avisos("jumping_jacks", _jj))
    assert not any(_avisos("marcha_rodillas", _marcha))


def test_con_otro_ejercicio_avisa_despues_de_sostenerlo():
    avisos = _avisos("jumping_jacks", _marcha)
    assert avisos[-1]
    primero = avisos.index(True) / FPS
    # calentamiento (2 s) + estado sostenido (3 s), y no mucho más
    assert R.CALENTAMIENTO_MS / 1000 + R.SOSTENIDO_MS / 1000 <= primero <= 7.0


def test_a_otro_ritmo_sigue_siendo_el_mismo_ejercicio():
    assert not any(_avisos("jumping_jacks", _jj, periodo_s=1.6))


def test_quieta_no_es_otro_ejercicio():
    assert not any(_avisos("jumping_jacks", lambda f: BASE))


def test_si_su_segmentador_cuenta_no_avisa_no_reconocido():
    """Variante `+seg` de EXP-010 §7.3: el elegido se hace «a su manera» (no se
    parece a ninguna referencia) pero su segmentador cuenta repeticiones."""
    assert any(_avisos("jumping_jacks", _sentadilla))
    assert not any(_avisos("jumping_jacks", _sentadilla, cuenta_propio=True))


def test_si_otro_se_parece_claramente_mas_avisa_aunque_su_segmentador_cuente():
    """El segmentador de abducción cuenta las aperturas de un jumping jack
    (EXP-010 §11): el caso «claro» no se calla."""
    rec = R.ReconocedorEjercicio("jumping_jacks", _refs())
    coste = {"jumping_jacks": 2.0, "marcha_rodillas": 0.3}
    assert rec.equivocado(coste, actividad=1.0, propio_reciente=True)
    coste = {"jumping_jacks": 2.0, "marcha_rodillas": 1.5}
    assert rec.equivocado(coste, actividad=1.0)
    assert not rec.equivocado(coste, actividad=1.0, propio_reciente=True)


def test_sin_referencias_o_sin_clase_no_hay_reconocedor(tmp_path):
    assert R.reconocedor_para("jumping_jacks", tmp_path / "no_existe.json") is None
    ruta = tmp_path / "rec.json"
    ruta.write_text(json.dumps({"medidas": list(R.MEDIDAS), "escala": [1.0] * len(R.MEDIDAS),
                                "referencias": [{"clase": "plancha", "tipo": "isometrico",
                                                 "media": [[None] * len(R.MEDIDAS)]}]}))
    assert R.reconocedor_para("zancada_atras_izq", ruta) is None
    assert R.reconocedor_para("jumping_jacks", ruta) is None      # sin referencias de JJ
    assert R.reconocedor_para("plancha", ruta) is not None


def test_subsecuencia_vectorizada_igual_que_el_bucle():
    """La columna sin bucle da lo mismo que la recurrencia de EXP-010."""
    rng = np.random.default_rng(0)
    media = rng.normal(size=(25, 3))
    media[4, 1] = np.nan
    escala = np.ones(3)
    rapida, col = R.Subsecuencia(media, escala), np.full(25, np.inf)
    for _ in range(60):
        x = rng.normal(size=3)
        dif = np.abs(media - x) / escala
        local = np.nanmean(dif, axis=1)
        nueva = np.empty(25)
        nueva[0] = local[0]
        for j in range(1, 25):
            nueva[j] = local[j] + min(col[j - 1], col[j], nueva[j - 1])
        col = nueva
        assert rapida.actualizar(x) == pytest.approx(col[-1] / 25)


def test_el_espejo_cambia_izquierda_por_derecha():
    m = R.Referencias({"medidas": list(R.MEDIDAS), "escala": [1.0] * len(R.MEDIDAS),
                       "referencias": [{"clase": "x", "tipo": "isometrico",
                                        "media": [list(range(len(R.MEDIDAS)))]}]})
    original, espejo = m.comparadores()["x"]
    i, d = R.MEDIDAS.index("cadera_izq"), R.MEDIDAS.index("cadera_der")
    assert espejo.media[i] == original.media[d] and espejo.media[d] == original.media[i]
    assert np.array_equal(espejo.media[R.MEDIDAS.index("codo_medio")],
                          original.media[R.MEDIDAS.index("codo_medio")])
