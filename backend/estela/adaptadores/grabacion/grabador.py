"""Grabar episodios etiquetados con la cámara (o convertir un vídeo).

Cámara, ventana de OpenCV:
    espacio   empezar (cuenta atrás de 3 s) / parar la toma
    g         guardar la toma          d   descartarla
    q / Esc   salir

Con vídeo la toma es el vídeo entero y se guarda sin preguntar: sirve para
pasar a pose los vídeos que ya se tienen (y después poder borrarlos).

Mientras se graba corre el segmentador del skill, para ver en pantalla si el
sistema cuenta las repeticiones: una toma en la que no cuenta ninguna no
servirá para la referencia.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw

from ...aplicacion.puertos import Estimador
from ...aplicacion.rutina import Ejercicio, cargar_catalogo
from ...dominio.feedback.motor.geometria import observacion_desde_pose
from ...dominio.feedback.motor.skill import directorio_skills
from ..interfaz.overlay import BLANCO, GRIS, NARANJA, VERDE, _esqueleto, _fuente, _panel
from .episodio import Grabacion, guardar, ruta_episodio, validar_etiqueta

log = logging.getLogger(__name__)

CUENTA_ATRAS_S = 3.0
#: `[F]` referencias por debajo de 25 fps se descartaron (RESUMEN-decision-referencias)
FPS_MINIMO_REFERENCIA = 25.0


def buscar_ejercicio(skill_id: str) -> Ejercicio:
    """Busca el skill en el catálogo y, si no está, entre los retirados: se
    graba también para ejercicios que aún no están en la rutina."""
    for directorio in (directorio_skills(), os.path.join(directorio_skills(), "retirados")):
        catalogo = cargar_catalogo(directorio)
        if skill_id in catalogo:
            return catalogo[skill_id]
    raise KeyError(f"no existe el skill '{skill_id}' (ni en skills/ ni en retirados/)")


class _Toma:
    """Una toma en curso: la grabación y un segmentador nuevo para contar."""

    def __init__(self, ejercicio: Ejercicio, nueva: Callable[[], Grabacion]) -> None:
        self.ejercicio = ejercicio
        self.grabacion = nueva()
        self.segmentador = ejercicio.nuevo_segmentador() if ejercicio.soportado else None
        self.completadas = 0

    def agregar(self, t_ms: int, resultado) -> None:
        if resultado.muestra is None:
            self.grabacion.agregar(t_ms, None, None)
            return
        mundo = np.array([[k.x, k.y, k.z, k.visibilidad]
                          for k in resultado.muestra.keypoints.values()], np.float32)
        self.grabacion.agregar(t_ms, mundo, resultado.imagen)
        if self.segmentador is not None:
            obs = observacion_desde_pose(resultado.muestra, self.ejercicio.skill.skill_id)
            self.completadas = self.segmentador.actualizar(obs).completadas

    def resumen(self) -> str:
        g = self.grabacion
        s = g.duracion_ms / 1000.0
        fps = (g.n_frames - 1) / s if s > 0 else 0.0
        unidad = "s" if self.ejercicio.unidad == "segundos" else "reps"
        return f"{s:.1f} s · {g.n_frames} frames · {fps:.1f} fps · {self.completadas} {unidad}"

    def avisos(self) -> List[str]:
        g = self.grabacion
        s = g.duracion_ms / 1000.0
        avisos = []
        if s > 0 and (g.n_frames - 1) / s < FPS_MINIMO_REFERENCIA:
            avisos.append(f"menos de {FPS_MINIMO_REFERENCIA:.0f} fps: no sirve como referencia")
        if self.segmentador is not None and self.completadas == 0:
            avisos.append("no se contó ninguna repetición")
        return avisos


def _ruta_guardada(toma: _Toma, raiz: Path) -> Path:
    ep = toma.grabacion.episodio({"completadas": toma.completadas})
    return guardar(ep, ruta_episodio(raiz, ep))


def grabar_video(ejercicio: Ejercicio, nueva: Callable[[], Grabacion], fuente,
                 estimador: Estimador, raiz: Path) -> Path:
    toma = _Toma(ejercicio, nueva)
    while (leido := fuente.leer()) is not None:
        frame, t_ms = leido
        toma.agregar(t_ms, estimador.estimar(frame, t_ms))
    ruta = _ruta_guardada(toma, raiz)
    print(f"Guardado {ruta} ({toma.resumen()})")
    for aviso in toma.avisos():
        print(f"  aviso: {aviso}")
    return ruta


def _dibujar(frame: np.ndarray, imagen: Optional[np.ndarray],
             lineas: List[Tuple[str, Tuple[int, int, int]]]) -> np.ndarray:
    img = cv2.flip(frame, 1)                       # espejo solo para mostrar
    if imagen is not None:
        _esqueleto(img, imagen, espejo=True)
    h, w = img.shape[:2]
    t = lambda px: max(12, int(px * h / 720.0))   # noqa: E731
    _panel(img, 0, 0, w, t(30 + 40 * len(lineas)))
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    for k, (texto, color) in enumerate(lineas):
        tam = t(34 if k == 0 else 26)
        d.text((t(20), t(12 + 40 * k)), texto, font=_fuente(tam), fill=color,
               stroke_width=max(1, tam // 18), stroke_fill=(0, 0, 0))
    return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)


def grabar_camara(ejercicio: Ejercicio, nueva: Callable[[], Grabacion], fuente,
                  estimador: Estimador, raiz: Path, titulo: str) -> List[Path]:
    guardadas: List[Path] = []
    estado, toma, cuenta_hasta = "espera", None, 0.0
    ultimo = ""
    cv2.namedWindow("ESTELA · grabar", cv2.WINDOW_NORMAL)
    while True:
        leido = fuente.leer()
        if leido is None:
            break
        frame, t_ms = leido
        resultado = estimador.estimar(frame, t_ms)
        ahora = time.monotonic()
        if estado == "cuenta" and ahora >= cuenta_hasta:
            estado, toma = "grabando", _Toma(ejercicio, nueva)
        if estado == "grabando":
            toma.agregar(t_ms, resultado)

        lineas = [(titulo, BLANCO)]
        if estado == "espera":
            lineas.append(("espacio: grabar · q: salir", GRIS))
            if ultimo:
                lineas.append((ultimo, VERDE))
        elif estado == "cuenta":
            lineas.append((f"empieza en {cuenta_hasta - ahora:.0f}…", NARANJA))
        elif estado == "grabando":
            lineas.append((f"● GRABANDO  {toma.resumen()}", NARANJA))
            lineas.append(("espacio: parar", GRIS))
        else:
            lineas.append((toma.resumen(), BLANCO))
            lineas += [(f"aviso: {a}", NARANJA) for a in toma.avisos()]
            lineas.append(("g: guardar · d: descartar", VERDE))
        if resultado.muestra is None:
            lineas.append(("no se ve a nadie", NARANJA))
        cv2.imshow("ESTELA · grabar", _dibujar(frame, resultado.imagen, lineas))

        tecla = cv2.waitKey(1) & 0xFF
        if tecla in (ord("q"), 27) and estado != "grabando":
            if estado == "revision":
                print("Toma sin guardar descartada")
            break
        if tecla == ord(" "):
            if estado == "espera":
                estado, cuenta_hasta = "cuenta", ahora + CUENTA_ATRAS_S
            elif estado == "grabando":
                estado = "revision"
        elif estado == "revision" and tecla == ord("g"):
            ruta = _ruta_guardada(toma, raiz)
            guardadas.append(ruta)
            ultimo = f"guardada: {ruta.name} ({len(guardadas)} en esta sesión)"
            print(f"Guardado {ruta} ({toma.resumen()})")
            estado, toma = "espera", None
        elif estado == "revision" and tecla == ord("d"):
            ultimo = "toma descartada"
            estado, toma = "espera", None
    cv2.destroyAllWindows()
    return guardadas


def correr(skill_id: str, etiqueta: str, persona: str, raiz: Path,
           crear_estimador: Callable[[], Estimador], abrir_fuente: Callable[[], object],
           modelo_pose: str, video: Optional[Path] = None, notas: str = "") -> int:
    ejercicio = buscar_ejercicio(skill_id)
    validar_etiqueta(ejercicio.skill, etiqueta)
    if ejercicio.skill.estado == "descartado":
        log.warning("'%s' está retirado: se graba, pero no está en la rutina", skill_id)

    def nueva() -> Grabacion:
        return Grabacion(ejercicio.skill, etiqueta, persona,
                         f"video:{video.name}" if video else "camara",
                         modelo_pose, notas)

    nueva()                                        # valida persona y etiqueta ya
    estimador, fuente = crear_estimador(), abrir_fuente()
    try:
        if video is not None:
            grabar_video(ejercicio, nueva, fuente, estimador, raiz)
        else:
            titulo = f"{ejercicio.skill.nombre} · {etiqueta} · {persona}"
            guardadas = grabar_camara(ejercicio, nueva, fuente, estimador, raiz, titulo)
            print(f"{len(guardadas)} episodio(s) guardado(s) en {raiz / skill_id / etiqueta}")
    finally:
        fuente.cerrar()
        estimador.cerrar()
    return 0


__all__ = ["buscar_ejercicio", "correr", "grabar_video", "grabar_camara"]
