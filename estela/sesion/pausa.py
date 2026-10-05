"""Pausa por inactividad de la sesión (T22.b).

La sesión se pausa si la usuaria sale del encuadre o deja de hacer el
ejercicio, y retoma donde iba. A diferencia de otras apps, que reinician los
contadores tras un rato sin actividad, aquí **pausar nunca reinicia**: perder
las repeticiones hechas frustra a la persona.

Dos motivos:

``sin_persona``  `sin_persona_s` seguidos sin detectar a nadie. Se retoma en
                 cuanto vuelve la persona con la orientación correcta.
``inactividad``  `inactividad_s` con la persona delante pero sin progreso en el
                 ejercicio (ni fase, ni repetición, ni contadores cambian).
                 Solo se arma cuando el ejercicio ya empezó, para no pausar
                 mientras la persona se coloca. Se retoma cuando vuelve a haber
                 progreso con la orientación correcta.

La quietud de un isométrico no es inactividad: en posición, el segmentador
suma un segundo cada segundo y eso cuenta como progreso.

`DetectorPausa` es lógica pura (sin voz ni reloj propio) para poder probarlo
aislado; la sesión decide qué decir con los eventos que devuelve.

`[?]` Los dos umbrales son provisionales: se fijaron por criterio, no
medidos con usuarias (EXP-008).
"""

from __future__ import annotations

from typing import Hashable, Optional

SIN_PERSONA = "sin_persona"
INACTIVIDAD = "inactividad"

EVENTO_PAUSA = "pausa"
EVENTO_REANUDA = "reanuda"

#: segundos sin persona antes de pausar
PAUSA_SIN_PERSONA_S = 5.0
#: segundos sin progreso en el ejercicio antes de pausar (más que el anterior:
#: un descanso corto entre repeticiones no debe pausar)
PAUSA_INACTIVIDAD_S = 8.0


class DetectorPausa:
    """Estado de pausa de un paso de la rutina.

    `actualizar` se llama una vez por frame con:

    * `persona`: si el estimador detectó a alguien.
    * `progreso`: algo comparable que cambia cuando la usuaria avanza en el
      ejercicio (p. ej. fase, repetición y contadores), o None si el
      ejercicio aún no empezó (no se vigila la inactividad).
    * `orientacion_ok`: si está colocada como pide el ejercicio.

    Devuelve `EVENTO_PAUSA`, `EVENTO_REANUDA` o None.
    """

    def __init__(self, sin_persona_s: float = PAUSA_SIN_PERSONA_S,
                 inactividad_s: float = PAUSA_INACTIVIDAD_S) -> None:
        self.sin_persona_ms = sin_persona_s * 1000.0
        self.inactividad_ms = inactividad_s * 1000.0
        self.motivo: Optional[str] = None
        self.veces = 0
        self._pausado_ms = 0
        self._desde_ms: Optional[int] = None
        self._ult_persona_ms: Optional[int] = None
        self._ult_progreso_ms: Optional[int] = None
        self._progreso: Optional[Hashable] = None

    @property
    def pausada(self) -> bool:
        return self.motivo is not None

    def tiempo_pausado_ms(self, t_ms: int) -> int:
        """Tiempo total en pausa, incluida la pausa en curso hasta `t_ms`."""
        en_curso = t_ms - self._desde_ms if self._desde_ms is not None else 0
        return self._pausado_ms + max(0, en_curso)

    def actualizar(self, t_ms: int, persona: bool,
                   progreso: Optional[Hashable] = None,
                   orientacion_ok: bool = True) -> Optional[str]:
        if self.pausada:
            return self._quizas_reanudar(t_ms, persona, progreso, orientacion_ok)

        if self._ult_persona_ms is None:
            self._ult_persona_ms = t_ms            # el paso acaba de empezar
        if not persona:
            if t_ms - self._ult_persona_ms >= self.sin_persona_ms:
                return self._pausar(t_ms, SIN_PERSONA)
            return None
        self._ult_persona_ms = t_ms

        if progreso is None or progreso != self._progreso:
            self._progreso, self._ult_progreso_ms = progreso, t_ms
            return None
        if t_ms - self._ult_progreso_ms >= self.inactividad_ms:
            return self._pausar(t_ms, INACTIVIDAD)
        return None

    def _quizas_reanudar(self, t_ms: int, persona: bool,
                         progreso: Optional[Hashable],
                         orientacion_ok: bool) -> Optional[str]:
        if not persona or not orientacion_ok:
            return None
        if self.motivo == INACTIVIDAD and progreso == self._progreso:
            return None
        self._pausado_ms = self.tiempo_pausado_ms(t_ms)
        self.motivo, self._desde_ms = None, None
        self._ult_persona_ms = self._ult_progreso_ms = t_ms
        self._progreso = progreso
        return EVENTO_REANUDA

    def _pausar(self, t_ms: int, motivo: str) -> str:
        self.motivo, self._desde_ms = motivo, t_ms
        self.veces += 1
        return EVENTO_PAUSA


__all__ = ["DetectorPausa", "SIN_PERSONA", "INACTIVIDAD", "EVENTO_PAUSA",
           "EVENTO_REANUDA", "PAUSA_SIN_PERSONA_S", "PAUSA_INACTIVIDAD_S"]
