"""Dibujo del estado de la sesión sobre el frame (OpenCV + Pillow).

Pillow se usa solo para el texto: las fuentes Hershey de OpenCV no tienen
tildes ni «ñ». El espejo (vista tipo espejo para la usuaria) se aplica solo
aquí, nunca antes del estimador de pose.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..pose.landmarks import CONEXIONES
from ..sesion.sesion import EstadoFrame

_FUENTES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:/Windows/Fonts/arialbd.ttf",
)

BLANCO = (255, 255, 255)
VERDE = (80, 220, 120)
AMARILLO = (255, 200, 60)
NARANJA = (255, 140, 40)
GRIS = (190, 190, 190)


@lru_cache(maxsize=8)
def _fuente(tam: int) -> ImageFont.ImageFont:
    for ruta in _FUENTES:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, tam)
    return ImageFont.load_default(size=tam)


def _esqueleto(img: np.ndarray, lm: np.ndarray, espejo: bool) -> None:
    h, w = img.shape[:2]
    xs = (1.0 - lm[:, 0]) if espejo else lm[:, 0]
    pts = [(int(x * w), int(y * h)) for x, y in zip(xs, lm[:, 1])]
    vis = lm[:, 3]
    for a, b in CONEXIONES:
        if vis[a] > 0.5 and vis[b] > 0.5:
            cv2.line(img, pts[a], pts[b], (230, 230, 230), 3, cv2.LINE_AA)
    for i in {i for c in CONEXIONES for i in c}:
        color = (120, 220, 80) if vis[i] > 0.6 else (60, 60, 200)
        cv2.circle(img, pts[i], 5, color, -1, cv2.LINE_AA)


def _panel(img: np.ndarray, x0: int, y0: int, x1: int, y1: int,
           alfa: float = 0.55) -> None:
    sub = img[y0:y1, x0:x1]
    img[y0:y1, x0:x1] = (sub * (1 - alfa)).astype(np.uint8)


def dibujar(frame: np.ndarray, estado: EstadoFrame, espejo: bool = True,
            fps: Optional[float] = None) -> np.ndarray:
    img = cv2.flip(frame, 1) if espejo else frame.copy()
    h, w = img.shape[:2]
    if estado.landmarks is not None:
        _esqueleto(img, estado.landmarks, espejo)

    escala = h / 720.0
    t = lambda px: max(12, int(px * escala))         # noqa: E731
    _panel(img, 0, 0, w, t(120))
    _panel(img, 0, h - t(90), w, h)

    textos: List[Tuple[Tuple[int, int], str, int, Tuple[int, int, int]]] = []
    if estado.terminada:
        textos.append(((t(20), t(30)), "Rutina terminada", t(44), VERDE))
    else:
        textos.append(((t(20), t(12)),
                       f"Ejercicio {estado.paso}/{estado.total_pasos} · {estado.ejercicio}",
                       t(30), BLANCO))
        textos.append(((t(20), t(52)),
                       f"{estado.completadas} / {estado.objetivo}", t(56), VERDE))
        detalle = f"fase: {estado.fase or '—'}"
        if estado.incompletas:
            detalle += f"   incompletas: {estado.incompletas}"
        textos.append(((t(250), t(70)), detalle, t(26), GRIS))

    derecha = []
    if fps is not None:
        derecha.append(f"{fps:4.1f} FPS")
    if "pose" in estado.latencia_ms:
        derecha.append(f"pose {estado.latencia_ms['pose']:.0f} ms")
    if estado.orientacion is not None:
        derecha.append(f"orientación {estado.orientacion:.0f}°")
    for k, linea in enumerate(derecha):
        textos.append(((w - t(260), t(12 + 30 * k)), linea, t(22), GRIS))

    if estado.sugerencia:
        distinto = estado.sugerencia != estado.ejercicio_id
        textos.append(((w - t(260), t(12 + 30 * len(derecha))),
                       f"BiLSTM: {estado.sugerencia}" + ("  ≠ rutina" if distinto else ""),
                       t(22), NARANJA if distinto else GRIS))
    if estado.aviso:
        textos.append(((t(20), t(135)), estado.aviso, t(30), NARANJA))
    if estado.ultimo_mensaje:
        textos.append(((t(20), h - t(70)), estado.ultimo_mensaje, t(40), AMARILLO))

    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    for pos, texto, tam, color in textos:
        d.text(pos, texto, font=_fuente(tam), fill=color,
               stroke_width=max(1, tam // 18), stroke_fill=(0, 0, 0))
    return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)


__all__ = ["dibujar"]
