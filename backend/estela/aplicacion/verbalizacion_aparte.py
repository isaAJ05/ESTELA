"""Redacta las correcciones con un verbalizador lento (LLM) sin parar el bucle.

Antes la llamada al LLM iba dentro del bucle por imagen: mientras el modelo
respondía (p50 173 ms, máx 263 ms en el Mac Studio, Prompt 3) no se procesaba
ninguna imagen. Aquí el motor decide como siempre (determinista, en el bucle) y
la redacción se pide a un hilo propio; cuando vuelve, la sesión la muestra y la
dice. El LLM sigue sin decidir nada: recibe un error ya tipificado.

Un solo hueco pendiente, como la cola de voz: si llega una corrección nueva
mientras otra espera, la más reciente la sustituye. La que se está redactando
termina igualmente (la sesión decide al recibirla si aún toca decirla).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional, Tuple

from ..dominio.feedback.contrato import ErrorTipificado, MensajeFeedback
from ..dominio.feedback.verbalizador.base import Verbalizador

log = logging.getLogger(__name__)


class VerbalizacionAparte:
    def __init__(self, verbalizador: Verbalizador,
                 al_terminar: Callable[[Any, MensajeFeedback, float], None]) -> None:
        """`al_terminar(clave, mensaje, ms)` se llama en este hilo con lo que
        devolvió el verbalizador (o su plantilla si falló) y los milisegundos."""
        self.verbalizador = verbalizador
        self._al_terminar = al_terminar
        self._cv = threading.Condition()
        self._pendiente: Optional[Tuple[Any, ErrorTipificado]] = None
        self._ocupado = False
        self._cerrada = False
        self.pedidas = 0
        self.sustituidas = 0
        self._hilo = threading.Thread(target=self._bucle, name="estela-verbalizador",
                                      daemon=True)
        self._hilo.start()

    def pedir(self, clave: Any, error: ErrorTipificado) -> None:
        with self._cv:
            self.pedidas += 1
            if self._pendiente is not None:
                self.sustituidas += 1
            self._pendiente = (clave, error)
            self._cv.notify()

    @property
    def ocupado(self) -> bool:
        with self._cv:
            return self._ocupado or self._pendiente is not None

    def esperar(self, timeout: float = 5.0) -> None:
        fin = time.monotonic() + timeout
        while self.ocupado and time.monotonic() < fin:
            time.sleep(0.005)

    def _bucle(self) -> None:
        while True:
            with self._cv:
                while self._pendiente is None and not self._cerrada:
                    self._cv.wait()
                if self._cerrada:
                    return
                (clave, error), self._pendiente = self._pendiente, None
                self._ocupado = True
            try:
                t0 = time.perf_counter()
                try:
                    msg = self.verbalizador.verbalizar(error)
                except Exception:                     # noqa: BLE001
                    log.exception("fallo del verbalizador; se usa la plantilla")
                    respaldo = getattr(self.verbalizador, "fallback", None)
                    if respaldo is None:
                        continue
                    msg = respaldo.verbalizar(error)
                self._al_terminar(clave, msg, (time.perf_counter() - t0) * 1000.0)
            except Exception:                         # noqa: BLE001
                log.exception("fallo al entregar la corrección redactada")
            finally:
                with self._cv:
                    self._ocupado = False

    def cerrar(self) -> None:
        with self._cv:
            self._cerrada = True
            self._cv.notify()
        self._hilo.join(timeout=2.0)


__all__ = ["VerbalizacionAparte"]
