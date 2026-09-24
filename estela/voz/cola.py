"""Cola de voz: un hilo que habla sin bloquear el bucle de percepción.

Tiene un único hueco pendiente: si llega una frase nueva mientras otra
espera, la más reciente la sustituye (un feedback de hace 3 s ya no sirve).
Los avisos de la aplicación (cambio de ejercicio, fin de rutina) tienen más
prioridad que las correcciones y no los pisa una corrección.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional

from .motores import MotorVoz

log = logging.getLogger(__name__)

PRIORIDAD_FEEDBACK = 0
PRIORIDAD_AVISO = 1


@dataclass(frozen=True)
class Locucion:
    texto: str
    prioridad: int
    t_encolado: float


class ColaVoz:
    def __init__(self, motor: MotorVoz) -> None:
        self.motor = motor
        self._cv = threading.Condition()
        self._pendiente: Optional[Locucion] = None
        self._hablando = False
        self._cerrada = False
        self.descartadas = 0
        #: (texto, segundos entre encolar y empezar a sonar)
        self.historial: List[tuple] = []
        self._hilo = threading.Thread(target=self._bucle, name="estela-voz",
                                      daemon=True)
        self._hilo.start()

    def decir(self, texto: str, prioridad: int = PRIORIDAD_FEEDBACK) -> bool:
        """Encola una frase. Devuelve False si se descartó."""
        with self._cv:
            if self._cerrada:
                return False
            p = self._pendiente
            if p is not None and p.prioridad > prioridad:
                self.descartadas += 1
                return False
            if p is not None:
                self.descartadas += 1
            self._pendiente = Locucion(texto, prioridad, time.perf_counter())
            self._cv.notify()
            return True

    def precalentar(self, textos: Iterable[str]) -> None:
        """Sintetiza en segundo plano las frases conocidas, sin bloquear.

        Una frase pedida antes de estar lista se sintetiza al momento.
        """
        lista = list(textos)
        threading.Thread(target=self.motor.precalentar, args=(lista,),
                         name="estela-voz-precalentado", daemon=True).start()

    @property
    def ocupada(self) -> bool:
        with self._cv:
            return self._hablando or self._pendiente is not None

    def esperar_vacia(self, timeout: float = 10.0) -> None:
        fin = time.monotonic() + timeout
        while self.ocupada and time.monotonic() < fin:
            time.sleep(0.02)

    def _bucle(self) -> None:
        while True:
            with self._cv:
                while self._pendiente is None and not self._cerrada:
                    self._cv.wait()
                if self._cerrada and self._pendiente is None:
                    return
                loc, self._pendiente = self._pendiente, None
                self._hablando = True
            try:
                self.historial.append((loc.texto,
                                       time.perf_counter() - loc.t_encolado))
                self.motor.hablar(loc.texto)
            except Exception:                     # noqa: BLE001
                log.exception("fallo al hablar: %r", loc.texto)
            finally:
                with self._cv:
                    self._hablando = False

    def cerrar(self, esperar: bool = True) -> None:
        if esperar:
            self.esperar_vacia()
        with self._cv:
            self._cerrada = True
            self._cv.notify()
        self._hilo.join(timeout=2.0)
        self.motor.cerrar()


__all__ = ["ColaVoz", "PRIORIDAD_FEEDBACK", "PRIORIDAD_AVISO"]
