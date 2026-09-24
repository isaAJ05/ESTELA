"""Estimador de pose: MediaPipe Pose Landmarker (Tasks API), modo VIDEO.

SegundoInforme §9.9 selecciona Pose Landmarker con world landmarks. La API
legacy `mp.solutions.pose` que usan los scripts de PRUEBAS/ ya no existe en
mediapipe 1.0.1.

Se usa `RunningMode.VIDEO` (síncrono) en lugar de `LIVE_STREAM`: el hilo
principal procesa siempre el frame más reciente, la latencia por frame se
puede medir directamente y el resultado es determinista con un vídeo.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from feedback.contrato import MuestraPose

from .landmarks import NOMBRES_MEDIAPIPE, a_array, muestra_desde_arrays


@dataclass(frozen=True)
class ResultadoPose:
    muestra: Optional[MuestraPose]          # None si no hay persona
    imagen: Optional[np.ndarray]            # (33, 4) normalizado al frame
    latencia_ms: float


class EstimadorPose:
    def __init__(self, ruta_modelo: Path, confianza_deteccion: float = 0.5,
                 confianza_seguimiento: float = 0.5) -> None:
        from mediapipe.tasks.python import BaseOptions, vision

        ruta_modelo = Path(ruta_modelo)
        if not ruta_modelo.exists():
            raise FileNotFoundError(
                f"No existe el modelo de pose {ruta_modelo}. "
                "Ejecuta: python scripts/descargar_modelos.py")
        opciones = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(ruta_modelo)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=confianza_deteccion,
            min_tracking_confidence=confianza_seguimiento,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(opciones)
        self._ultimo_t = -1
        self.fuente = f"mediapipe_tasks:{ruta_modelo.stem}"

    def estimar(self, frame_bgr: np.ndarray, t_ms: int) -> ResultadoPose:
        import mediapipe as mp

        # detect_for_video exige timestamps estrictamente crecientes.
        t_ms = max(int(t_ms), self._ultimo_t + 1)
        self._ultimo_t = t_ms
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        imagen_mp = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        t0 = time.perf_counter()
        r = self._landmarker.detect_for_video(imagen_mp, t_ms)
        latencia = (time.perf_counter() - t0) * 1000.0

        if not r.pose_world_landmarks or not r.pose_landmarks:
            return ResultadoPose(None, None, latencia)
        mundo = a_array(r.pose_world_landmarks[0])
        imagen = a_array(r.pose_landmarks[0])
        assert len(mundo) == len(NOMBRES_MEDIAPIPE)
        return ResultadoPose(muestra_desde_arrays(t_ms, mundo, imagen, self.fuente),
                             imagen, latencia)

    def cerrar(self) -> None:
        self._landmarker.close()


__all__ = ["EstimadorPose", "ResultadoPose"]
