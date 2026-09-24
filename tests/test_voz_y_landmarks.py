import threading
import time

import numpy as np
import pytest

from estela.pose.landmarks import NOMBRES_MEDIAPIPE, muestra_desde_arrays
from estela.voz.cola import PRIORIDAD_AVISO, PRIORIDAD_FEEDBACK, ColaVoz
from estela.voz.motores import MotorVoz, crear_motor


class MotorLento(MotorVoz):
    nombre = "lento"

    def __init__(self):
        self.dichas = []
        self.puede_seguir = threading.Event()

    def hablar(self, texto):
        self.dichas.append(texto)
        self.puede_seguir.wait(2.0)


def test_cola_se_queda_con_la_frase_mas_reciente():
    m = MotorLento()
    cola = ColaVoz(m)
    cola.decir("uno")
    time.sleep(0.05)                    # "uno" está sonando
    cola.decir("dos")
    cola.decir("tres")                  # sustituye a "dos"
    m.puede_seguir.set()
    cola.cerrar()
    assert m.dichas == ["uno", "tres"]
    assert cola.descartadas == 1


def test_un_feedback_no_pisa_un_aviso_pendiente():
    m = MotorLento()
    cola = ColaVoz(m)
    cola.decir("sonando")
    time.sleep(0.05)
    cola.decir("Ahora, sentadilla.", PRIORIDAD_AVISO)
    assert not cola.decir("Endereza el tronco.", PRIORIDAD_FEEDBACK)
    m.puede_seguir.set()
    cola.cerrar()
    assert m.dichas == ["sonando", "Ahora, sentadilla."]


def test_crear_motor_cae_a_texto_sin_piper():
    assert crear_motor("piper", None).nombre in ("sistema", "texto")
    assert crear_motor("texto", None).nombre == "texto"
    with pytest.raises(ValueError):
        crear_motor("otro", None)


def test_muestra_desde_arrays_mapea_los_33_nombres():
    mundo = np.arange(33 * 4, dtype=np.float32).reshape(33, 4)
    imagen = np.zeros((33, 4), np.float32)
    imagen[:, 3] = 0.5
    m = muestra_desde_arrays(10, mundo, imagen)
    assert len(m.keypoints) == 33 and m.espacio == "mundo_m"
    kp = m.keypoints["left_knee"]
    i = NOMBRES_MEDIAPIPE.index("left_knee")
    assert (kp.x, kp.y, kp.z) == tuple(mundo[i, :3]) and kp.visibilidad == 0.5
    with pytest.raises(ValueError):
        muestra_desde_arrays(0, np.zeros((17, 4)))


def test_nombres_coinciden_con_mediapipe():
    vision = pytest.importorskip("mediapipe.tasks.python.vision")
    assert tuple(p.name.lower() for p in vision.PoseLandmark) == NOMBRES_MEDIAPIPE
