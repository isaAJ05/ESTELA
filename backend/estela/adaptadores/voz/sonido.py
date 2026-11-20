"""Sonido corto de «te escucho» al oír «Estela».

Paula (2026-11-20): «apenas digo "Estela" quiero que me indique que me está
escuchando». Hasta ahora, tras «Estela» a secas solo cambiaba el punto del
micrófono en pantalla, y haciendo el ejercicio no se mira la pantalla.

Son dos notas que suben (660 → 990 Hz, 0,2 s en total), como el aviso de los
asistentes de voz. No pasan por la cola de voz: si pasaran, ESTELA contaría como
«hablando» y la escucha cortaría la frase que la usuaria está diciendo. Tienen
su propia salida de audio, abierta una vez (como `ReproductorContinuo`: abrir y
cerrar flujos por frase dio errores de CoreAudio en el Mac). Si no hay salida de
audio, no suena y no pasa nada más.

`[?]` El tono, el volumen y la duración son una elección mía (reversible:
`--voz-entrada-sonido no` lo quita); no los ha oído Paula.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

import numpy as np

from .motores import ReproductorContinuo

log = logging.getLogger(__name__)

FS_SONIDO = 22050
#: notas (Hz), duración de cada una y silencio entre ellas (s), y volumen (0–1)
NOTAS = (660.0, 990.0)
NOTA_S, HUECO_S, VOLUMEN = 0.08, 0.03, 0.3


def tono_llamada(fs: int = FS_SONIDO) -> np.ndarray:
    """Las dos notas en int16, con entrada y salida suaves (sin chasquidos)."""
    n = int(NOTA_S * fs)
    t = np.arange(n) / fs
    rampa = int(0.01 * fs)
    envolvente = np.ones(n)
    envolvente[:rampa] = np.linspace(0.0, 1.0, rampa)
    envolvente[-rampa:] = np.linspace(1.0, 0.0, rampa)
    partes = []
    for k, f in enumerate(NOTAS):
        if k:
            partes.append(np.zeros(int(HUECO_S * fs)))
        partes.append(np.sin(2 * np.pi * f * t) * envolvente)
    return (np.concatenate(partes) * VOLUMEN * 32767).astype(np.int16)


class SonidoLlamada:
    def __init__(self) -> None:
        self._datos = tono_llamada()
        self._salida: Optional[ReproductorContinuo] = None
        try:
            import sounddevice as sd
            sd.query_devices(kind="output")
            self._salida = ReproductorContinuo(sd, FS_SONIDO)
        except Exception as exc:                          # noqa: BLE001 — sin salida, sin sonido
            log.warning("Sin sonido de «te escucho»: %s: %s", type(exc).__name__, exc)

    def sonar(self) -> None:
        """No bloquea: suena en un hilo aparte."""
        if self._salida is not None:
            threading.Thread(target=self._salida.reproducir, args=(self._datos,),
                             name="estela-sonido-llamada", daemon=True).start()

    def cerrar(self) -> None:
        if self._salida is not None:
            self._salida.cerrar()


__all__ = ["SonidoLlamada", "tono_llamada", "FS_SONIDO"]
