"""Interfaz común de los verbalizadores.

Un verbalizador convierte un `ErrorTipificado` en una frase en español. No
decide nada: recibe el error ya tipificado y produce solo la superficie
lingüística (ADR-001, §4.3, compromiso 1).

Existen tres implementaciones previstas, que son las tres condiciones de
EXP-001:

    A   plantillas parametrizadas        -> `plantillas.VerbalizadorPlantillas`
    F   modelo local con salida restringida + validador
    F'  el mismo modelo sin restricción  (condición de control)

F y F' comparten implementación y se diferencian por el flag `restringido`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..contrato import ErrorTipificado, MensajeFeedback


class Verbalizador(ABC):
    """Contrato que toda condición de EXP-001 debe cumplir."""

    nombre: str = "base"

    @abstractmethod
    def verbalizar(self, error: ErrorTipificado) -> MensajeFeedback:
        """Produce el mensaje. No debe lanzar: ante fallo, devuelve fallback."""
        raise NotImplementedError


__all__ = ["Verbalizador"]
