"""Nombres de los 33 landmarks de MediaPipe Pose y conversión al contrato.

Se declaran aquí (en vez de leerlos de `mediapipe.tasks...PoseLandmark`) para
que la conversión se pueda probar sin tener mediapipe instalado. El orden es
el de `vision.PoseLandmark` en mediapipe 1.0.1 (verificado con `.name`).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ...dominio.feedback.contrato import Keypoint, MuestraPose

NOMBRES_MEDIAPIPE: Tuple[str, ...] = (
    "nose", "left_eye_inner", "left_eye", "left_eye_outer",
    "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear", "mouth_left", "mouth_right",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_pinky", "right_pinky",
    "left_index", "right_index", "left_thumb", "right_thumb",
    "left_hip", "right_hip", "left_knee", "right_knee",
    "left_ankle", "right_ankle", "left_heel", "right_heel",
    "left_foot_index", "right_foot_index",
)

#: Conexiones del esqueleto para dibujar (subconjunto de POSE_CONNECTIONS).
#: De la cara solo se dibuja cuello (hombro → oreja) y cabeza (oreja → nariz):
#: lo necesario para ver hacia dónde mira, p. ej. en la plancha.
CONEXIONES: Tuple[Tuple[int, int], ...] = (
    (11, 7), (12, 8), (7, 0), (8, 0),
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (27, 29), (29, 31), (27, 31),
    (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),
)


#: Articulaciones de cada segmento del contrato (`feedback.contrato.SEGMENTOS`)
#: como (lado izquierdo, lado derecho) de la persona, que es el `left_*` de
#: MediaPipe. La interfaz las resalta cuando llega una corrección.
_PUNTOS_SEGMENTO: Dict[str, Tuple[Tuple[int, ...], Tuple[int, ...]]] = {
    "hombro": ((11,), (12,)),
    "codo": ((13,), (14,)),
    "muneca": ((15,), (16,)),
    "brazo": ((11, 13, 15), (12, 14, 16)),
    "cadera": ((23,), (24,)),
    "rodilla": ((25,), (26,)),
    "tobillo": ((27,), (28,)),
    "pie": ((27, 29, 31), (28, 30, 32)),
    "pierna": ((23, 25, 27), (24, 26, 28)),
    "tronco": ((11, 23), (12, 24)),
    "espalda": ((11, 23), (12, 24)),
    "cuello": ((0, 11), (0, 12)),
    "cabeza": ((0,), (0,)),
}


def puntos_de_segmento(segmento: str, lado: str) -> List[int]:
    """Índices de los landmarks de un segmento; ambos lados si el lado es
    «bilateral» o «na». Lista vacía si el segmento no se conoce."""
    izq, der = _PUNTOS_SEGMENTO.get(segmento, ((), ()))
    if lado == "izquierdo":
        return list(izq)
    if lado == "derecho":
        return list(der)
    return sorted(set(izq) | set(der))


def a_array(landmarks: Sequence) -> np.ndarray:
    """Lista de landmarks de mediapipe → array (33, 4) [x, y, z, visibilidad]."""
    return np.array([[p.x, p.y, p.z, p.visibility or 0.0] for p in landmarks],
                    dtype=np.float32)


def muestra_desde_arrays(t_ms: int, mundo: np.ndarray,
                         imagen: Optional[np.ndarray] = None,
                         fuente: str = "mediapipe_tasks") -> MuestraPose:
    """Construye la `MuestraPose` en espacio métrico ("mundo_m").

    La visibilidad se toma de los landmarks de imagen cuando existen: es la
    que MediaPipe calcula sobre el frame; si no, la de los de mundo.
    """
    if mundo.shape != (len(NOMBRES_MEDIAPIPE), 4):
        raise ValueError(f"se esperaban 33x4 landmarks, llegó {mundo.shape}")
    vis = imagen[:, 3] if imagen is not None else mundo[:, 3]
    kps = {
        nombre: Keypoint(float(mundo[i, 0]), float(mundo[i, 1]),
                         float(mundo[i, 2]), float(vis[i]))
        for i, nombre in enumerate(NOMBRES_MEDIAPIPE)
    }
    return MuestraPose(t_ms=t_ms, keypoints=kps, espacio="mundo_m", fuente=fuente)


__all__ = ["NOMBRES_MEDIAPIPE", "CONEXIONES", "a_array", "muestra_desde_arrays",
           "puntos_de_segmento"]
