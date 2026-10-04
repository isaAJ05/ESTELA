"""Rutas por defecto, relativas a la raíz del repositorio."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELOS = RAIZ / "modelos"
VOCES = MODELOS / "voces"
RUTINAS = RAIZ / "rutinas"
SESIONES = RAIZ / "sesiones"
#: BiLSTM de mejor accuracy (0.847) entrenada en PRUEBAS/ con coords MediaPipe
BILSTM = (RAIZ / "PRUEBAS" / "Prueba red neuronal (dataset-pose-deteccion-conteo)"
          / "DATASET" / "resultados" / "mediapipe_coords")


def modelo_pose(variante: str) -> Path:
    return MODELOS / f"pose_landmarker_{variante}.task"
