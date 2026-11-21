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
from typing import Any, Dict, List, Optional, Tuple, Union

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


def _nombre_camara(indice: int) -> Optional[str]:
    """Nombre del dispositivo si el sistema lo da sin dependencias (Linux).
    `[?]` En macOS OpenCV no da nombres y el orden de AVFoundation no se
    puede cruzar con el índice sin PyObjC: queda «Cámara N»."""
    try:
        nombre = Path(f"/sys/class/video4linux/video{indice}/name").read_text().strip()
    except OSError:
        return None
    # V4L lo corta a 31 caracteres y suele repetirlo tras «:»
    return nombre.split(":")[0].strip() or None


def listar_camaras(maximo: int = 5) -> List[Dict[str, Any]]:
    """Índices de cámara que OpenCV puede abrir. Abre y cierra cada una, así
    que tarda (~0,5–1 s por cámara) y no debe llamarse con una sesión en
    curso."""
    camaras = []
    for i in range(maximo):
        cap = cv2.VideoCapture(i)
        try:
            if cap.isOpened():
                nombre = _nombre_camara(i) or f"Cámara {i + 1}"
                if any(c["nombre"] == nombre for c in camaras):
                    nombre = f"{nombre} ({i + 1})"   # p. ej. la cámara IR del mismo equipo
                camaras.append({"indice": i, "nombre": nombre})
        finally:
            cap.release()
    return camaras


__all__ = ["FuenteVideo", "FuenteCamara", "Frame", "listar_camaras"]
