"""Micrófono con `sounddevice`: entrega frases cortadas por `DetectorDeFrase`."""

from __future__ import annotations

import queue
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import numpy as np

from .frases import BLOQUE, FS, DetectorDeFrase


#: motivo de `hay_microfono` cuando el audio funciona pero no hay ninguna entrada
SIN_MICROFONO = "no hay ningún micrófono conectado"


class SinMicrofono(RuntimeError):
    """No hay ninguna entrada de audio: se puede conectar una y volver a encender."""


def _entradas() -> List[Dict[str, Any]]:
    import sounddevice as sd
    return [d for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]


def volver_a_buscar() -> None:
    """Vuelve a leer los dispositivos de audio. PortAudio los lee al arrancar: un
    micrófono conectado después no aparece hasta reiniciarlo. Solo se llama sin
    ninguna entrada abierta. `[?]` no probado con un micrófono conectado en caliente."""
    try:
        import sounddevice as sd
        sd._terminate()
        sd._initialize()
    except Exception:                                     # noqa: BLE001 — se sigue con lo que había
        pass


def hay_microfono() -> Tuple[bool, str]:
    """(hay, motivo si no). No lanza."""
    try:
        entradas = _entradas()
    except Exception as exc:                              # noqa: BLE001
        return False, f"no se pudo consultar el audio ({type(exc).__name__}: {exc})"
    if not entradas:
        return False, SIN_MICROFONO
    return True, ""


def listar_microfonos() -> List[Dict[str, Any]]:
    """Entradas de audio que ve el sistema: [{"indice", "nombre", "porDefecto"}].
    No lanza: sin audio devuelve []. La lista se vuelve a leer al encender el micrófono
    (`Microfono` llama a `volver_a_buscar` si no ve ninguna entrada)."""
    try:
        import sounddevice as sd
        dispositivos = list(sd.query_devices())
        por_defecto = sd.default.device[0]
    except Exception:                                     # noqa: BLE001
        return []
    return [{"indice": i, "nombre": str(d.get("name", f"Micrófono {i}")),
             "porDefecto": i == por_defecto}
            for i, d in enumerate(dispositivos) if d.get("max_input_channels", 0) > 0]


class Microfono:
    """Abre una entrada a 16 kHz mono (`dispositivo` None: la de defecto del
    sistema). `escuchar_frase` bloquea hasta que hay una frase, se cancela o
    pasa `espera_s`. `nivel` es el volumen reciente (RMS, 0–1) para pintarlo."""

    def __init__(self, dispositivo: Optional[int] = None) -> None:
        import sounddevice as sd
        if not _entradas():                       # puede ser un micrófono recién conectado
            volver_a_buscar()
            if not _entradas():
                raise SinMicrofono(SIN_MICROFONO)
        self.dispositivo = dispositivo
        self._cola: "queue.Queue[np.ndarray]" = queue.Queue()
        self._detector = DetectorDeFrase()
        self.nivel = 0.0
        self._flujo = sd.InputStream(samplerate=FS, channels=1, dtype="float32",
                                     blocksize=BLOQUE, callback=self._al_llegar,
                                     device=dispositivo)
        self._flujo.start()
        try:
            self.nombre: Optional[str] = str(sd.query_devices(
                dispositivo if dispositivo is not None else sd.default.device[0])["name"])
        except Exception:                                 # noqa: BLE001
            self.nombre = None

    def _al_llegar(self, datos, frames, tiempo, estado) -> None:   # hilo de audio
        bloque = datos[:, 0].copy()
        # volumen suavizado: sube enseguida y baja despacio, para que se lea en pantalla
        rms = float(np.sqrt(np.mean(bloque ** 2))) if len(bloque) else 0.0
        self.nivel = rms if rms > self.nivel else 0.8 * self.nivel + 0.2 * rms
        self._cola.put(bloque)

    def descartar(self) -> None:
        """Tira lo capturado hasta ahora (p. ej. mientras hablaba ESTELA)."""
        while not self._cola.empty():
            try:
                self._cola.get_nowait()
            except queue.Empty:
                break
        self._detector.reiniciar()

    def escuchar_ventana(self, cancelar: Callable[[], bool], ventana_s: float = 2.5,
                         paso_s: float = 1.0) -> Optional[np.ndarray]:
        """Mientras ESTELA habla, el corte por energía no sirve (su voz también
        cuenta como voz). Aquí se junta audio durante `paso_s` y se devuelven los
        últimos `ventana_s` segundos, solapados con la ventana anterior, para que
        una orden no quede partida. None si se cancela."""
        import time
        n = int(ventana_s * FS / BLOQUE)
        if not hasattr(self, "_ventana") or self._ventana.maxlen != n:
            self._ventana: Deque[np.ndarray] = deque(maxlen=n)
        fin = time.monotonic() + paso_s
        while time.monotonic() < fin:
            if cancelar():
                return None
            try:
                self._ventana.append(self._cola.get(timeout=0.1))
            except queue.Empty:
                continue
        self._detector.reiniciar()          # al volver al corte por frases, empieza limpio
        return np.concatenate(list(self._ventana)) if self._ventana else None

    def olvidar_ventana(self) -> None:
        """Tras actuar sobre una ventana, que la siguiente no vuelva a oír lo mismo."""
        if hasattr(self, "_ventana"):
            self._ventana.clear()

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


__all__ = ["Microfono", "SIN_MICROFONO", "SinMicrofono", "hay_microfono",
           "listar_microfonos", "volver_a_buscar"]
