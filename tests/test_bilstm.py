"""La BiLSTM en numpy reproduce el resultado de Keras sobre el test split."""

import json

import numpy as np
import pytest

from estela import config
from estela.reconocimiento.bilstm import (RedBiLSTM, ReconocedorBiLSTM, accuracy,
                                          normalizar_secuencia)

pytest.importorskip("h5py")
DATASET = config.BILSTM.parent.parent / "dataset_bilstm" / "mediapipe" / "coords"
requiere_modelo = pytest.mark.skipif(
    not (config.BILSTM / "modelo.h5").exists() or not (DATASET / "test.npz").exists(),
    reason="modelo o dataset BiLSTM no disponible")


@requiere_modelo
def test_accuracy_igual_a_la_registrada_en_entrenamiento():
    red = RedBiLSTM(config.BILSTM / "modelo.h5")
    norm = np.load(config.BILSTM / "normalizacion.npz")
    test = np.load(DATASET / "test.npz")
    esperado = json.loads((config.BILSTM / "metricas.json").read_text())["accuracy"]
    acc = accuracy(red, norm["media"], norm["desviacion"], test["X"], test["y"])
    assert acc == pytest.approx(esperado, abs=1e-6)


def test_normalizacion_centra_en_cadera_y_escala_por_torso():
    s = np.zeros((1, 33, 4), np.float32)
    s[0, [23, 24], :2] = [[0.4, 0.6], [0.6, 0.6]]       # cadera media (0.5, 0.6)
    s[0, [11, 12], :2] = [[0.4, 0.4], [0.6, 0.4]]       # hombro medio (0.5, 0.4)
    s[0, 0, :3] = [0.5, 0.2, 0.1]
    n = normalizar_secuencia(s)
    assert n[0, 0, 0] == pytest.approx(0.0, abs=1e-4)
    assert n[0, 0, 1] == pytest.approx(-2.0, abs=1e-3)   # (0.2-0.6)/0.2
    assert n[0, 0, 2] == pytest.approx(0.5, abs=1e-3)


@requiere_modelo
def test_reconocedor_en_linea_sin_persona_no_falla():
    r = ReconocedorBiLSTM(config.BILSTM)
    assert r.agregar(None).skill_id is None
    for _ in range(40):
        sug = r.agregar(np.random.default_rng(0).random((33, 4), dtype=np.float32))
    assert sug.skill_id in (None, "elevacion_brazos", "jumping_jacks",
                            "marcha_rodillas", "sentadilla")
