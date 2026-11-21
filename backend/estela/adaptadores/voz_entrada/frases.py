"""Corta una frase hablada de un flujo de audio, por energía.

`DetectorDeFrase` recibe bloques de audio (16 kHz, mono, float32) y devuelve
la frase cuando termina: empieza al subir la energía sobre el ruido de fondo y
acaba tras un rato de silencio o al llegar al tope. Es aritmética sobre los
bloques, sin micrófono, así que se prueba con audio sintético.

`[?]` Los valores (cuánto por encima del ruido, cuánto silencio cierra la
frase) son de ingeniería y solo se han probado con audio sintético: hay que
ajustarlos con un micrófono real en la sala.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, List, Optional

import numpy as np

FS = 16000
BLOQUE = 480                      # 30 ms
#: energía mínima absoluta para considerar voz (RMS, escala −1 a 1)
RMS_MINIMO = 0.01
#: la voz debe superar el ruido de fondo estimado por este factor
FACTOR_RUIDO = 3.0
#: cuánto puede subir la estimación del ruido de un bloque al siguiente
SUBIDA_RUIDO = 1.02
#: silencio que cierra la frase y duración máxima de una frase (s)
SILENCIO_FIN_S = 0.6
MAX_FRASE_S = 5.0
#: voz mínima para que cuente como frase (s) y audio previo que se conserva (s)
MIN_VOZ_S = 0.2
PREVIO_S = 0.3


class DetectorDeFrase:
    def __init__(self, fs: int = FS, bloque: int = BLOQUE) -> None:
        self.fs, self.bloque = fs, bloque
        self.reiniciar()

    def reiniciar(self, conservar_ruido: bool = False) -> None:
        """Empieza limpio. `conservar_ruido`: mantiene el ruido de fondo estimado
        (al volver de escuchar mientras hablaba ESTELA, la sala es la misma)."""
        if not conservar_ruido or not hasattr(self, "_ruido"):
            self._ruido: Optional[float] = None
        self._previo: Deque[np.ndarray] = self._previo_normal()
        self._frase: List[np.ndarray] = []
        self._voz = 0                 # bloques con voz en la frase en curso
        self._silencio = 0            # bloques de silencio seguidos tras la voz

    def _previo_normal(self) -> Deque[np.ndarray]:
        return deque(maxlen=max(1, int(PREVIO_S * self.fs / self.bloque)))

    def cebar(self, bloques: List[np.ndarray]) -> None:
        """Audio ya oído que se antepone a la próxima frase si empieza enseguida.
        Al callarse ESTELA, la usuaria puede estar a media palabra («Este-»): sin
        esto la frase empezaría en «-la, pausa» y no se oiría la llamada."""
        if self._frase or not bloques:
            return
        self._previo = deque(bloques, maxlen=max(len(bloques), self._previo.maxlen or 1))

    @property
    def en_frase(self) -> bool:
        return bool(self._frase)

    @property
    def segundos_en_frase(self) -> float:
        return len(self._frase) * self.bloque / self.fs

    def ultimos(self, segundos: float) -> Optional[np.ndarray]:
        """Los últimos `segundos` de la frase en curso (None si no hay frase)."""
        if not self._frase:
            return None
        n = max(1, int(segundos * self.fs / self.bloque))
        return np.concatenate(self._frase[-n:])

    def entregar(self) -> Optional[np.ndarray]:
        """Da ya la frase en curso (sin esperar el silencio) y empieza otra."""
        if not self._frase:
            return None
        frase = np.concatenate(self._frase)
        self._frase, self._voz, self._silencio = [], 0, 0
        self._previo = self._previo_normal()
        return frase

    def recortar(self, segundos: float) -> None:
        """Deja en la frase en curso solo sus últimos `segundos`. Al oír «Estela» a
        media frase, lo de antes era ruido o charla: así el tope de `MAX_FRASE_S`
        vuelve a contar desde ahí y no corta la orden que viene."""
        n = max(1, int(segundos * self.fs / self.bloque))
        if len(self._frase) > n:
            self._frase = self._frase[-n:]
            self._voz = min(self._voz, n)

    def _umbral(self) -> float:
        return max(RMS_MINIMO, FACTOR_RUIDO * (self._ruido or 0.0))

    def alimentar(self, bloque: np.ndarray) -> Optional[np.ndarray]:
        """Añade un bloque. Devuelve la frase completa cuando termina, o None."""
        bloque = np.asarray(bloque, dtype=np.float32).reshape(-1)
        rms = float(np.sqrt(np.mean(bloque ** 2))) if len(bloque) else 0.0
        # Ruido de fondo: baja de golpe y sube despacio (un 2 % por bloque), así
        # sigue al ruido constante de la sala y no a la voz, que tiene huecos.
        # Se actualiza también dentro de la frase: si no, un ruido presente
        # desde el primer bloque se tomaría por voz para siempre.
        self._ruido = rms if self._ruido is None else min(rms, self._ruido * SUBIDA_RUIDO + 1e-5)
        hay_voz = rms > self._umbral()
        if not self._frase:
            if not hay_voz:
                self._previo.append(bloque)
                return None
            self._frase = list(self._previo) + [bloque]
            self._voz, self._silencio = 1, 0
            return None
        self._frase.append(bloque)
        if hay_voz:
            self._voz += 1
            self._silencio = 0
        else:
            self._silencio += 1
        por_bloque = self.bloque / self.fs
        termino = self._silencio * por_bloque >= SILENCIO_FIN_S
        tope = len(self._frase) * por_bloque >= MAX_FRASE_S
        if not (termino or tope):
            return None
        frase, voz = np.concatenate(self._frase), self._voz
        self._frase, self._voz, self._silencio = [], 0, 0
        self._previo = self._previo_normal()
        return frase if voz * por_bloque >= MIN_VOZ_S else None


__all__ = ["DetectorDeFrase", "FS", "BLOQUE"]
