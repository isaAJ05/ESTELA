"""Micrófono con `sounddevice`: entrega frases cortadas por `DetectorDeFrase`."""

from __future__ import annotations

import queue
from typing import Callable, Optional, Tuple

import numpy as np

from .frases import BLOQUE, FS, DetectorDeFrase


def hay_microfono() -> Tuple[bool, str]:
    """(hay, motivo si no). No lanza."""
    try:
        import sounddevice as sd
        entradas = [d for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]
    except Exception as exc:                              # noqa: BLE001
        return False, f"no se pudo consultar el audio ({type(exc).__name__}: {exc})"
    if not entradas:
        return False, "no hay ningún micrófono conectado"
    return True, ""


class Microfono:
    """Abre la entrada por defecto a 16 kHz mono. `escuchar_frase` bloquea
    hasta que hay una frase, se cancela o pasa `espera_s`."""

    def __init__(self) -> None:
        import sounddevice as sd
        self._cola: "queue.Queue[np.ndarray]" = queue.Queue()
        self._detector = DetectorDeFrase()
        self._flujo = sd.InputStream(samplerate=FS, channels=1, dtype="float32",
                                     blocksize=BLOQUE, callback=self._al_llegar)
        self._flujo.start()

    def _al_llegar(self, datos, frames, tiempo, estado) -> None:   # hilo de audio
        self._cola.put(datos[:, 0].copy())

    def descartar(self) -> None:
        """Tira lo capturado hasta ahora (p. ej. mientras hablaba ESTELA)."""
        while not self._cola.empty():
            try:
                self._cola.get_nowait()
            except queue.Empty:
                break
        self._detector.reiniciar()

    def escuchar_frase(self, cancelar: Callable[[], bool],
                       espera_s: float = 1.0) -> Optional[np.ndarray]:
        import time
        fin = time.monotonic() + espera_s
        while not cancelar():
            if time.monotonic() > fin and not self._detector.en_frase:
                return None
            try:
                bloque = self._cola.get(timeout=0.1)
            except queue.Empty:
                continue
            frase = self._detector.alimentar(bloque)
            if frase is not None:
                return frase
        self.descartar()
        return None

    def cerrar(self) -> None:
        try:
            self._flujo.stop()
            self._flujo.close()
        except Exception:                                 # noqa: BLE001
            pass


__all__ = ["Microfono", "hay_microfono"]
