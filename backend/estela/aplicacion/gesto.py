"""Gesto para pausar y reanudar sin tocar el teclado.

Mantener el brazo derecho totalmente arriba `GESTO_PAUSA_S` segundos alterna
la pausa: si la sesión corre, la pausa (como el botón «Pausar»); si está en
pausa, por el motivo que sea, la reanuda.

«Totalmente arriba», en landmarks de imagen (y hacia abajo):

* muñeca derecha por encima de la nariz y del codo derecho, y
* codo derecho por encima del hombro derecho.

Además el brazo izquierdo **no** debe estar arriba (muñeca izquierda visible
por encima de su hombro): con los dos brazos arriba es un jumping jack o un
estiramiento, no el gesto. Si el brazo izquierdo no se ve (p. ej. de perfil),
no bloquea. «Derecho» es el brazo derecho de la persona (landmarks `right_*`
de MediaPipe sobre la imagen sin espejar).

Tras disparar, el gesto no vuelve a contar hasta que se baja el brazo: si no,
seguir con el brazo arriba 6 s pausaría y reanudaría seguido. Un frame suelto
sin el brazo arriba (ruido de la pose) no reinicia la cuenta si dura menos de
`TOLERANCIA_MS`.

`[?]` Los 3 s los pidió el equipo; la geometría y la tolerancia son
provisionales, sin medir con usuarias.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

#: segundos con el brazo arriba para pausar o reanudar
GESTO_PAUSA_S = 3.0
#: un hueco sin el brazo arriba más corto que esto no reinicia la cuenta
TOLERANCIA_MS = 300
#: la interfaz muestra el progreso a partir de aquí (evita destellos al
#: levantar el brazo un momento)
MOSTRAR_DESDE_MS = 600
_VISIBILIDAD_MINIMA = 0.5

_NARIZ = 0
_HOMBRO_IZQ, _HOMBRO_DER = 11, 12
_CODO_DER = 14
_MUNECA_IZQ, _MUNECA_DER = 15, 16


def brazo_derecho_arriba(puntos: Optional[np.ndarray]) -> bool:
    """¿El brazo derecho está totalmente arriba y el izquierdo no? `puntos`:
    landmarks de imagen (33, 4) normalizados, y hacia abajo, visibilidad al
    final."""
    if puntos is None:
        return False

    def visible(i: int) -> bool:
        return float(puntos[i, -1]) >= _VISIBILIDAD_MINIMA

    def y(i: int) -> float:
        return float(puntos[i, 1])

    if not all(visible(i) for i in (_NARIZ, _HOMBRO_DER, _CODO_DER, _MUNECA_DER)):
        return False
    derecho = (y(_MUNECA_DER) < y(_NARIZ) and y(_MUNECA_DER) < y(_CODO_DER)
               and y(_CODO_DER) < y(_HOMBRO_DER))
    izquierdo = (visible(_MUNECA_IZQ) and visible(_HOMBRO_IZQ)
                 and y(_MUNECA_IZQ) < y(_HOMBRO_IZQ))
    return derecho and not izquierdo


class DetectorGesto:
    """Cuenta cuánto lleva el brazo derecho arriba. `actualizar` devuelve True
    en el frame en que se cumplen los `GESTO_PAUSA_S` segundos."""

    def __init__(self, duracion_s: float = GESTO_PAUSA_S) -> None:
        self.duracion_ms = duracion_s * 1000.0
        self._desde: Optional[int] = None       # desde cuándo está arriba
        self._ult_arriba: Optional[int] = None
        self._armado = True                     # False hasta que baje el brazo

    def reiniciar(self) -> None:
        self._desde = self._ult_arriba = None
        self._armado = True

    def actualizar(self, t_ms: int, puntos: Optional[np.ndarray]) -> bool:
        if not brazo_derecho_arriba(puntos):
            if self._ult_arriba is None or t_ms - self._ult_arriba > TOLERANCIA_MS:
                self._desde = self._ult_arriba = None
                self._armado = True
            return False
        self._ult_arriba = t_ms
        if not self._armado:
            return False
        if self._desde is None:
            self._desde = t_ms
        if t_ms - self._desde >= self.duracion_ms:
            self._desde = None
            self._armado = False
            return True
        return False

    def progreso(self, t_ms: int) -> Optional[float]:
        """Fracción (0–1) del gesto en curso para mostrarla, o None."""
        if not self._armado or self._desde is None:
            return None
        transcurrido = t_ms - self._desde
        if transcurrido < MOSTRAR_DESDE_MS:
            return None
        return min(1.0, transcurrido / self.duracion_ms)


__all__ = ["DetectorGesto", "brazo_derecho_arriba", "GESTO_PAUSA_S"]
