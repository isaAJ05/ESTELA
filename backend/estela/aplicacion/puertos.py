"""Puertos: lo que la aplicación necesita del mundo exterior.

La sesión y el orquestador dependen solo de estas interfaces. Las
implementaciones concretas (MediaPipe, OpenCV, Piper, pywebview) viven en
`estela.adaptadores` y se conectan en `estela.__main__`. Los tests usan
versiones falsas sin cámara ni modelos.

Regla de dependencias:  dominio ← aplicacion ← adaptadores ← __main__
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, Tuple

import numpy as np

from ..dominio.feedback.contrato import MuestraPose

#: prioridad de una frase en la cola de voz: un aviso de la aplicación
#: (cambio de ejercicio, pausa, fin) no lo pisa una corrección
PRIORIDAD_FEEDBACK = 0
PRIORIDAD_AVISO = 1


@dataclass(frozen=True)
class ResultadoPose:
    muestra: Optional[MuestraPose]          # None si no hay persona
    imagen: Optional[np.ndarray]            # (33, 4) normalizado al frame
    latencia_ms: float


class Estimador(Protocol):
    def estimar(self, frame: np.ndarray, t_ms: int) -> ResultadoPose: ...
    def cerrar(self) -> None: ...


class Voz(Protocol):
    def decir(self, texto: str, prioridad: int = ...) -> bool: ...


class Fuente(Protocol):
    """Cámara o vídeo: `leer()` devuelve (frame, t_ms) o None al terminar."""
    def leer(self) -> Optional[Tuple[Any, int]]: ...
    def cerrar(self) -> None: ...


__all__ = ["Estimador", "Fuente", "PRIORIDAD_AVISO", "PRIORIDAD_FEEDBACK",
           "ResultadoPose", "Voz"]
