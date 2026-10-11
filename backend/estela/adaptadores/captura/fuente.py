"""Fuentes de frames.

`FuenteCamara` captura en su propio hilo y deja solo el **último** frame
(PrimerInforme §5.4: la memoria compartida guarda el frame más reciente y
descarta los viejos). Si la percepción va más lenta que la cámara, se saltan
frames en vez de acumular retraso. `[R]` Se usa memoria del proceso en lugar
de `multiprocessing.shared_memory`: con un único consumidor es suficiente y
más simple; pasar a procesos es reversible si la latencia lo exige.

`FuenteVideo` lee un archivo frame a frame con marcas de tiempo derivadas
del FPS del vídeo: es la fuente para pruebas reproducibles.

Los frames **no** se voltean aquí: MediaPipe etiqueta izquierda/derecha
suponiendo una imagen sin espejo, y voltearla invertiría el lado del
feedback. El espejo es solo de visualización (ui/overlay.py).

Ninguna fuente guarda frames en disco.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional, Tuple, Union

import cv2
import numpy as np

Frame = Tuple[np.ndarray, int]       # (imagen BGR, t_ms)


class FuenteVideo:
    def __init__(self, ruta: Union[str, Path], tiempo_real: bool = False) -> None:
        self._cap = cv2.VideoCapture(str(ruta))
        if not self._cap.isOpened():
            raise RuntimeError(f"no se pudo abrir el vídeo {ruta}")
        self.fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.tiempo_real = tiempo_real
        self._i = 0
        self._t0 = time.monotonic()

    def leer(self) -> Optional[Frame]:
        ok, frame = self._cap.read()
        if not ok:
            return None
        t_ms = int(self._i * 1000.0 / self.fps)
        self._i += 1
        if self.tiempo_real:                  # para verlo a velocidad normal
            espera = self._t0 + t_ms / 1000.0 - time.monotonic()
            if espera > 0:
                time.sleep(espera)
        return frame, t_ms

    def cerrar(self) -> None:
        self._cap.release()


class FuenteCamara:
    def __init__(self, indice: int = 0, ancho: int = 1280, alto: int = 720) -> None:
        self._cap = cv2.VideoCapture(indice)
        if not self._cap.isOpened():
            raise RuntimeError(f"no se pudo abrir la cámara {indice}")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)
        self.fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._cv = threading.Condition()
        self._ultimo: Optional[Frame] = None
        self._seq = 0
        self._leido = 0
        self._activa = True
        self.descartados = 0
        self._t0 = time.monotonic()
        self._hilo = threading.Thread(target=self._bucle, name="estela-camara",
                                      daemon=True)
        self._hilo.start()

    def _bucle(self) -> None:
        while self._activa:
            ok, frame = self._cap.read()
            if not ok:
                break
            t_ms = int((time.monotonic() - self._t0) * 1000.0)
            with self._cv:
                if self._seq > self._leido:
                    self.descartados += 1
                self._ultimo = (frame, t_ms)
                self._seq += 1
                self._cv.notify()
        with self._cv:
            self._activa = False
            self._cv.notify_all()

    def leer(self, timeout: float = 2.0) -> Optional[Frame]:
        """Bloquea hasta que haya un frame más nuevo que el último leído."""
        with self._cv:
            if not self._cv.wait_for(
                    lambda: self._seq > self._leido or not self._activa, timeout):
                return None
            if self._seq <= self._leido:
                return None
            self._leido = self._seq
            return self._ultimo

    def cerrar(self) -> None:
        self._activa = False
        self._hilo.join(timeout=2.0)
        self._cap.release()


__all__ = ["FuenteVideo", "FuenteCamara", "Frame"]
