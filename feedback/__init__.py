"""Módulo de retroalimentación de ESTELA.

Frontera: recibe `Observacion` (ángulos, keypoints derivados, desviaciones y
confianza) y produce `MensajeFeedback` o `Silencio`. No accede a la cámara, ni
al estimador de pose, ni al comparador temporal.
"""

from .contrato import (
    ErrorTipificado, Keypoint, Lado, MensajeFeedback, MuestraPose,
    Observacion, Severidad, Silencio,
)
from .motor.decision import MotorDecision
from .motor.skill import Skill, cargar_skill, cargar_skills, directorio_skills
from .pipeline import MotorFeedback
from .verbalizador.plantillas import VerbalizadorPlantillas

__version__ = "0.1.0"

__all__ = [
    "ErrorTipificado", "Keypoint", "Lado", "MensajeFeedback", "MuestraPose",
    "Observacion", "Severidad", "Silencio",
    "MotorDecision", "MotorFeedback", "Skill",
    "cargar_skill", "cargar_skills", "directorio_skills",
    "VerbalizadorPlantillas", "__version__",
]
