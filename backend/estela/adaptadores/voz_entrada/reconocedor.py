"""Reconocedor de voz local: Whisper con whisper.cpp (`pywhispercpp`).

`[F]` Medido en el Mac Studio el 2026-11-16 con 98 clips sintéticos (72 con
una orden, 26 sin ella; voces Piper y del sistema, limpios y con ruido), con
scripts/voz/evaluar_reconocedores.py y tres pasadas seguidas de los mismos
clips. Con el modelo «small», búsqueda voraz, sin reintento con temperatura y
la pista de vocabulario, whisper.cpp usa la GPU del Mac (Metal) y reconoce un
clip de 2 s en p50 56 ms, p95 69 ms, máximo 73 ms: 64 de 72 órdenes acertadas,
ninguna equivocada y 1 orden falsa en los 26 clips sin orden («Pausa o
siguiente» con ruido, que entendió como pausa). Las tres pasadas dan el mismo
texto en los 98 clips.

Por qué búsqueda voraz y no por haz `[F]`: con haz acierta 1 orden más de 72,
pero el mismo audio da textos distintos entre pasadas (40 de 98 clips) y en
una de cinco pasadas escribió «Seguimos.» sobre silencio. Por qué sin
reintento con temperatura (`temperature_inc=0`) `[F]`: con el reintento la
latencia máxima sube de 73 ms a 1 449 ms y el resultado deja de ser repetible.

Por qué este motor y no otro `[R]`: mlx-whisper con «large-v3-turbo» acierta
más con ruido (71 de 72, p95 158 ms) pero dio 2 órdenes falsas de 26 y
arrastra cerca de 1 GB de dependencias (PyTorch, numba, scipy); faster-whisper
no usa la GPU del Mac (small: p95 1 061 ms). Una orden no entendida solo pide
repetir; una orden falsa actúa sola, así que pesa más no inventarlas. Revisar
con un micrófono real: el ruido de la prueba es sintético.

Whisper es multilingüe y aquí se fija `language="es"`. `pista` es un
`initial_prompt` con las seis órdenes: con «small» sube los aciertos de 52 a
64 de 72.

Todo es local: el audio no sale del equipo y no se guarda.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from .frases import RMS_MINIMO

#: vocabulario que se le da a Whisper como pista
PISTA = "Pausa. Seguir. Siguiente. Repetir. Terminar. ¿Cómo voy?"
#: Whisper marca así el audio sin habla: «[BLANK_AUDIO]», «(música)», «*ruido*»
_ANOTACION = re.compile(r"\[[^\]]*\]|\([^)]*\)|\*[^*]*\*")


def limpiar(texto: str) -> str:
    """Quita las anotaciones de audio sin habla y los espacios sobrantes."""
    return re.sub(r"\s+", " ", _ANOTACION.sub(" ", texto or "")).strip()


class ReconocedorWhisperCpp:
    def __init__(self, ruta_modelo: Path, pista: Optional[str] = PISTA,
                 idioma: str = "es") -> None:
        from pywhispercpp.model import Model
        # la biblioteca anota cada transcripción en el registro: solo avisos
        logging.getLogger("pywhispercpp").setLevel(logging.WARNING)
        ruta_modelo = Path(ruta_modelo)
        if not ruta_modelo.exists():
            raise FileNotFoundError(
                f"No existe el modelo de voz {ruta_modelo}. "
                "Ejecuta: python scripts/descargar_modelos.py")
        self.ruta_modelo, self.pista, self.idioma = ruta_modelo, pista, idioma
        # redirect…=None manda el registro de whisper.cpp a ninguna parte
        # params_sampling_strategy=0: búsqueda voraz (1 sería por haz, no repetible)
        self._modelo = Model(str(ruta_modelo), redirect_whispercpp_logs_to=None,
                             params_sampling_strategy=0,
                             print_progress=False, print_realtime=False)

    def transcribir(self, audio: Any) -> str:
        """Audio mono a 16 kHz (float32, de −1 a 1) → texto en español."""
        # Sin nada que suene no se pregunta al modelo: `[F]` con ceros exactos
        # y la pista, «small» escribe «¿Qué?» (con ruido leve, «[SILENCIO]»).
        if len(audio) == 0 or float(abs(audio).max()) < RMS_MINIMO:
            return ""
        # temperature_inc=0: sin reintento con temperatura (acota la latencia)
        segmentos = self._modelo.transcribe(audio, language=self.idioma,
                                            initial_prompt=self.pista or "",
                                            temperature_inc=0.0)
        return limpiar(" ".join(s.text for s in segmentos))

    def precalentar(self) -> None:
        """Primera inferencia (carga del grafo en la GPU), fuera de la sesión."""
        import numpy as np
        self.transcribir(np.zeros(16000, np.float32))


__all__ = ["ReconocedorWhisperCpp", "PISTA", "limpiar"]
