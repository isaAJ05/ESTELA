"""Orquestación de la sesión para la interfaz de escritorio.

`Orquestador` corre la sesión en su propio hilo (fuente → `Sesion.procesar`)
y la interfaz la controla con métodos que se pueden llamar desde cualquier
hilo. No sabe nada de ventanas: `ventana.py` lo expone a la interfaz y los
tests lo usan con fuentes y estimadores falsos.

Fases (las mismas que muestra la interfaz):

    inicio ─iniciar()─► preparando ─► sesion ─► resumen ─iniciar()─► …
                            │                      │
                            └──► error             └─volver_al_inicio()─► inicio

Flujo de datos: el hilo de la sesión **no espera nunca a la interfaz**. Solo
deja el último `EstadoFrame` y el último frame; la interfaz los pide con
`estado(desde)`, que espera hasta que haya una versión más nueva (long
polling). Si la interfaz dibuja más lento que la cámara, se salta estados en
vez de acumular retraso, igual que `FuenteCamara` con los frames. La
conversión a JSON y la compresión JPEG del frame ocurren en el hilo de la
interfaz, no en el de la sesión.

Ningún frame se guarda: el JPEG se genera en memoria para la ventana local.
"""

from __future__ import annotations

import base64
import logging
import queue
import threading
import time
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, Tuple

import numpy as np

from ..sesion.rutina import Ejercicio, Rutina
from ..sesion.sesion import EstadoFrame, Sesion
from . import contrato

log = logging.getLogger(__name__)

INICIO, PREPARANDO, SESION, RESUMEN, ERROR = (
    "inicio", "preparando", "sesion", "resumen", "error")

#: ancho del frame que se envía a la ventana (solo para verlo)
ANCHO_VIDEO = 640
CALIDAD_JPEG = 70


class Fuente(Protocol):
    def leer(self) -> Optional[Tuple[Any, int]]: ...
    def cerrar(self) -> None: ...


class Estimador(Protocol):
    def estimar(self, frame: Any, t_ms: int) -> Any: ...
    def cerrar(self) -> None: ...


def _jpeg_base64(frame: Any, ancho: int = ANCHO_VIDEO) -> Optional[str]:
    if not isinstance(frame, np.ndarray) or frame.ndim != 3:
        return None
    import cv2

    h, w = frame.shape[:2]
    if w > ancho:
        frame = cv2.resize(frame, (ancho, round(h * ancho / w)),
                           interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, CALIDAD_JPEG])
    return base64.b64encode(buf).decode("ascii") if ok else None


class Orquestador:
    def __init__(self, rutina: Rutina, catalogo: Mapping[str, Ejercicio],
                 crear_estimador: Callable[[], Estimador],
                 abrir_fuente: Callable[[], Fuente], voz: Any, *,
                 espejo: bool, fuente: str = "camara",
                 al_terminar: Optional[Callable[[Dict[str, Any]], None]] = None,
                 verbalizador: Any = None) -> None:
        """`crear_estimador` y `abrir_fuente` se llaman en cada sesión: así
        «Repetir rutina» empieza con la cámara recién abierta y con marcas de
        tiempo desde cero. `al_terminar` recibe `Sesion.resumen()`."""
        self.rutina = rutina
        self.catalogo = catalogo
        self._crear_estimador = crear_estimador
        self._abrir_fuente = abrir_fuente
        self._voz = voz
        self._espejo = espejo
        self._fuente = fuente
        self._al_terminar = al_terminar
        self._verbalizador = verbalizador

        self._cv = threading.Condition()
        self._version = 0
        self._fase = INICIO
        self._error: Optional[Dict[str, str]] = None
        self._estado: Optional[EstadoFrame] = None
        self._fps: Optional[float] = None
        self._frame: Any = None
        self._resumen: Optional[Dict[str, Any]] = None

        self._comandos: "queue.SimpleQueue[str]" = queue.SimpleQueue()
        self._parar = threading.Event()
        self._hilo: Optional[threading.Thread] = None

    # -- consultas (cualquier hilo) ------------------------------------------

    def info(self) -> Dict[str, Any]:
        d = contrato.info(self.rutina, self.catalogo, self._espejo)
        d["fuente"] = self._fuente
        return d

    @property
    def fase(self) -> str:
        return self._fase

    def estado(self, desde: int = -1, espera_s: float = 0.5,
               con_video: bool = True) -> Optional[Dict[str, Any]]:
        """Estado más nuevo que la versión `desde`, o None si no llega en
        `espera_s` segundos (la interfaz vuelve a preguntar)."""
        with self._cv:
            if not self._cv.wait_for(lambda: self._version > desde, espera_s):
                return None
            version, fase, error = self._version, self._fase, self._error
            estado, fps, frame, resumen = self._estado, self._fps, self._frame, self._resumen
        return {
            "version": version,
            "fase": fase,
            "error": error,
            "sesion": (contrato.estado_a_dict(estado, fps)
                       if estado is not None and fase == SESION else None),
            "resumen": resumen if fase == RESUMEN else None,
            "frame": _jpeg_base64(frame) if con_video and fase == SESION else None,
        }

    # -- comandos (cualquier hilo) -------------------------------------------

    def iniciar(self) -> bool:
        """Empieza una sesión nueva desde el inicio, el resumen o un error."""
        with self._cv:
            if self._fase not in (INICIO, RESUMEN, ERROR):
                return False
            if self._hilo is not None:
                self._hilo.join()
            self._parar.clear()
            while not self._comandos.empty():
                self._comandos.get_nowait()
            self._publicar(fase=PREPARANDO, error=None, estado=None, frame=None,
                           resumen=None)
            self._hilo = threading.Thread(target=self._correr, name="estela-sesion",
                                          daemon=True)
            self._hilo.start()
        return True

    def siguiente(self) -> None:
        self._comandos.put("siguiente")

    def reiniciar(self) -> None:
        self._comandos.put("reiniciar")

    def terminar(self) -> None:
        """Termina la sesión en curso y pasa al resumen."""
        self._comandos.put("terminar")

    def volver_al_inicio(self) -> None:
        with self._cv:
            if self._fase in (RESUMEN, ERROR):
                self._publicar(fase=INICIO, error=None, resumen=None)

    def cerrar(self, timeout: float = 5.0) -> None:
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(timeout)

    # -- hilo de la sesión ---------------------------------------------------

    def _publicar(self, **cambios: Any) -> None:
        with self._cv:
            for k, v in cambios.items():
                setattr(self, f"_{k}", v)
            self._version += 1
            self._cv.notify_all()

    def _correr(self) -> None:
        try:
            fuente = self._abrir_fuente()
        except Exception as e:                 # cámara ocupada, vídeo inexistente…
            log.error("No se pudo abrir la fuente: %s", e)
            self._publicar(fase=ERROR, error={"tipo": "fuente", "mensaje": str(e)})
            return
        try:
            estimador = self._crear_estimador()
        except Exception as e:
            fuente.cerrar()
            log.error("No se pudo cargar el modelo de pose: %s", e)
            self._publicar(fase=ERROR, error={"tipo": "modelo", "mensaje": str(e)})
            return

        sesion = Sesion(self.rutina, self.catalogo, estimador, self._voz,
                        self._verbalizador)
        self._publicar(fase=SESION)
        fps, t_prev = None, time.perf_counter()
        try:
            while not self._parar.is_set():
                if self._aplicar_comandos(sesion):
                    break
                leido = fuente.leer()
                if leido is None:              # fin del vídeo o cámara perdida
                    break
                frame, t_ms = leido
                estado = sesion.procesar(frame, t_ms)
                ahora = time.perf_counter()
                inst = 1.0 / max(ahora - t_prev, 1e-6)
                fps = inst if fps is None else 0.9 * fps + 0.1 * inst
                t_prev = ahora
                self._publicar(estado=estado, fps=fps, frame=frame)
                if sesion.terminada:
                    break
        except Exception:
            log.exception("Error en la sesión")
        finally:
            fuente.cerrar()
            estimador.cerrar()

        resumen = sesion.resumen()
        if self._al_terminar is not None:
            try:
                self._al_terminar(resumen)
            except Exception:
                log.exception("Error al cerrar la sesión")
        self._publicar(fase=RESUMEN, estado=None, frame=None,
                       resumen=contrato.resumen_a_dict(resumen, self.catalogo))

    def _aplicar_comandos(self, sesion: Sesion) -> bool:
        """Aplica los comandos pendientes en el hilo de la sesión (que no es
        segura entre hilos). Devuelve True si hay que terminar."""
        while True:
            try:
                cmd = self._comandos.get_nowait()
            except queue.Empty:
                return False
            if cmd == "terminar":
                return True
            if cmd == "siguiente":
                sesion.siguiente()
                if sesion.terminada:
                    return True
            elif cmd == "reiniciar":
                sesion.reiniciar_ejercicio()


__all__ = ["Orquestador", "INICIO", "PREPARANDO", "SESION", "RESUMEN", "ERROR"]
