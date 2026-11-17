"""Estimador de pose: MediaPipe Pose Landmarker (Tasks API), modo VIDEO.

SegundoInforme §9.9 selecciona Pose Landmarker con world landmarks. La API
legacy `mp.solutions.pose` que usan los scripts de PRUEBAS/ ya no existe en
mediapipe 1.0.1.

Se usa `RunningMode.VIDEO` (síncrono) en lugar de `LIVE_STREAM`: el hilo
principal procesa siempre el frame más reciente, la latencia por frame se
puede medir directamente y el resultado es determinista con un vídeo.

`delegado="gpu"` pide el delegado GPU de MediaPipe (Metal en macOS). `[F]`
Medido en el Mac Studio M2 Ultra el 2026-11-16 con mediapipe 1.2.3 (EXP-004,
candidatos A4–A6): el delegado se crea también por SSH y exige imágenes de 4
canales (SRGBA). El defecto sigue siendo CPU: es lo validado en todos los
equipos del proyecto.

`[F]` Con el delegado GPU, MediaPipe 1.2.3 retiene memoria por cada imagen
(~2 MB por imagen de 1280×720; la app pasó de 0,7 a 15 GB en 2 min; medido en
el Mac el 2026-11-17) y solo la suelta al cerrar el detector. En CPU no pasa.
Por eso, con GPU: (1) la imagen se reduce a `LADO_MAX_GPU` (la retención baja a
la cuarta parte y los puntos cambian 1,8 px de media sobre 1280; el modelo
trabaja a 256 px de todos modos) y (2) cada `RENOVAR_CADA` imágenes se prepara
otro detector en segundo plano y se cambia por el viejo, que se cierra. La
primera imagen del detector nuevo tarda 75–100 ms aunque se caliente en otro
hilo (medido), así que el cambio espera a un momento sin evaluación
(`momento_libre`: colocación, pausa o anuncio), con tope en 2 × `RENOVAR_CADA`.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from ...aplicacion.puertos import ResultadoPose

from .landmarks import NOMBRES_MEDIAPIPE, a_array, muestra_desde_arrays


DELEGADOS = ("cpu", "gpu")
#: con GPU: lado mayor de la imagen que se pasa al modelo, e imágenes entre dos
#: renovaciones del detector (~1 min a 30 fps; retiene ~1 GB como mucho)
LADO_MAX_GPU = 640
RENOVAR_CADA = 1800

log = logging.getLogger(__name__)


class EstimadorPose:
    def __init__(self, ruta_modelo: Path, confianza_deteccion: float = 0.5,
                 confianza_seguimiento: float = 0.5, delegado: str = "cpu") -> None:
        from mediapipe.tasks.python import BaseOptions, vision

        if delegado not in DELEGADOS:
            raise ValueError(f"delegado desconocido: {delegado!r} (use {DELEGADOS})")
        self.delegado = delegado
        ruta_modelo = Path(ruta_modelo)
        if not ruta_modelo.exists():
            raise FileNotFoundError(
                f"No existe el modelo de pose {ruta_modelo}. "
                "Ejecuta: python scripts/descargar_modelos.py")
        opciones = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(
                model_asset_path=str(ruta_modelo),
                delegate=(BaseOptions.Delegate.GPU if delegado == "gpu"
                          else BaseOptions.Delegate.CPU)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=confianza_deteccion,
            min_tracking_confidence=confianza_seguimiento,
        )
        self._opciones = opciones
        self._landmarker = vision.PoseLandmarker.create_from_options(opciones)
        self._ultimo_t = -1
        #: renovación del detector con GPU (ver el docstring del módulo)
        self._frames = 0
        self._nuevo = None
        self._renovando = False
        self._libre = False
        self.renovaciones = 0
        self.fuente = f"mediapipe_tasks:{ruta_modelo.stem}" + (":gpu" if delegado == "gpu" else "")

    def estimar(self, frame_bgr: np.ndarray, t_ms: int) -> ResultadoPose:
        import mediapipe as mp

        # detect_for_video exige timestamps estrictamente crecientes.
        t_ms = max(int(t_ms), self._ultimo_t + 1)
        self._ultimo_t = t_ms
        if self.delegado == "gpu":       # el delegado GPU solo acepta 4 canales
            alto, ancho = frame_bgr.shape[:2]
            escala = LADO_MAX_GPU / max(alto, ancho)
            if escala < 1.0:             # los puntos salen normalizados: no cambian de escala
                frame_bgr = cv2.resize(frame_bgr, (round(ancho * escala), round(alto * escala)),
                                       interpolation=cv2.INTER_AREA)
            imagen_mp = mp.Image(image_format=mp.ImageFormat.SRGBA,
                                 data=cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGBA))
            if self._libre or self._frames >= 2 * RENOVAR_CADA:
                self._cambiar_si_hay_nuevo()
            self._libre = False
        else:
            imagen_mp = mp.Image(image_format=mp.ImageFormat.SRGB,
                                 data=cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))

        t0 = time.perf_counter()
        r = self._landmarker.detect_for_video(imagen_mp, t_ms)
        latencia = (time.perf_counter() - t0) * 1000.0
        if self.delegado == "gpu":
            self._frames += 1
            if self._frames >= RENOVAR_CADA and not self._renovando and self._nuevo is None:
                self._renovar_en_segundo_plano(imagen_mp)

        if not r.pose_world_landmarks or not r.pose_landmarks:
            return ResultadoPose(None, None, latencia)
        mundo = a_array(r.pose_world_landmarks[0])
        imagen = a_array(r.pose_landmarks[0])
        assert len(mundo) == len(NOMBRES_MEDIAPIPE)
        return ResultadoPose(muestra_desde_arrays(t_ms, mundo, imagen, self.fuente),
                             imagen, latencia)

    def momento_libre(self) -> None:
        """La sesión avisa de que esta imagen no se evalúa: buen momento para
        cambiar de detector (su primera imagen es lenta)."""
        self._libre = True

    def _renovar_en_segundo_plano(self, imagen_mp) -> None:
        """Crea otro detector en un hilo y lo calienta con la última imagen (su
        primera imagen tarda ~40 ms); `estimar` lo cambia cuando está listo."""
        from mediapipe.tasks.python import vision
        self._renovando = True

        def trabajo() -> None:
            try:
                nuevo = vision.PoseLandmarker.create_from_options(self._opciones)
                nuevo.detect_for_video(imagen_mp, 0)
                self._nuevo = nuevo
            except Exception:                             # noqa: BLE001
                log.exception("no se pudo renovar el detector de pose; sigue el de antes")
                self._frames = 0
            finally:
                self._renovando = False
        threading.Thread(target=trabajo, name="estela-pose-renovar", daemon=True).start()

    def _cambiar_si_hay_nuevo(self) -> None:
        nuevo, self._nuevo = self._nuevo, None
        if nuevo is None:
            return
        viejo, self._landmarker = self._landmarker, nuevo
        self._frames = 0
        self.renovaciones += 1
        log.info("Pose: detector GPU renovado (%d) para soltar la memoria retenida", self.renovaciones)
        threading.Thread(target=viejo.close, name="estela-pose-cerrar", daemon=True).start()

    def cerrar(self) -> None:
        self._landmarker.close()
        if self._nuevo is not None:
            self._nuevo.close()


__all__ = ["EstimadorPose", "ResultadoPose", "DELEGADOS"]
