"""Orquestador del módulo: observación -> decisión -> mensaje.

Es la única clase que la aplicación de escritorio necesita conocer. El
verbalizador se inyecta, y ese punto de inyección es exactamente el factor
único que EXP-001 manipula.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from .contrato import ErrorTipificado, MensajeFeedback, Observacion, Silencio
from .motor.decision import MotorDecision
from .motor.skill import Skill
from .verbalizador.base import Verbalizador
from .verbalizador.plantillas import VerbalizadorPlantillas

Salida = Union[MensajeFeedback, Silencio]


@dataclass
class Tiempos:
    """Latencia por etapa, en milisegundos. Es la métrica M4 de EXP-001."""
    decision_ms: float = 0.0
    verbalizacion_ms: float = 0.0

    @property
    def total_ms(self) -> float:
        return self.decision_ms + self.verbalizacion_ms


class MotorFeedback:
    def __init__(self, skill: Skill,
                 verbalizador: Optional[Verbalizador] = None) -> None:
        self.skill = skill
        self.decision = MotorDecision(skill)
        self.verbalizador = verbalizador or VerbalizadorPlantillas()
        self.ultimos_tiempos = Tiempos()
        #: historial de la sesión, para depuración y para el arnés de EXP-001
        self.historial: List[Salida] = []

    def procesar(self, obs: Observacion) -> Salida:
        t0 = time.perf_counter()
        decision = self.decision.observar(obs)
        t1 = time.perf_counter()

        if isinstance(decision, Silencio):
            self.ultimos_tiempos = Tiempos((t1 - t0) * 1000.0, 0.0)
            self.historial.append(decision)
            return decision

        mensaje = self.verbalizador.verbalizar(decision)
        t2 = time.perf_counter()
        self.ultimos_tiempos = Tiempos((t1 - t0) * 1000.0, (t2 - t1) * 1000.0)
        self.historial.append(mensaje)
        return mensaje

    def procesar_episodio(self, observaciones) -> List[Salida]:
        return [self.procesar(o) for o in observaciones]

    def reiniciar(self) -> None:
        self.decision.reiniciar()
        self.historial.clear()

    @property
    def abstenciones(self) -> Dict[str, int]:
        return dict(self.decision.contador_abstenciones)


__all__ = ["MotorFeedback", "Tiempos", "Salida"]
