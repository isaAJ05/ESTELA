"""Motores de voz local. Todos implementan `hablar(texto)` bloqueante.

Orden de preferencia (SegundoInforme §2.9): Piper → voz del sistema
(espeak-ng en Linux, `say` en macOS) → solo texto. Ninguno envía nada fuera
de la máquina.
"""

from __future__ import annotations

import io
import logging
import platform
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Dict, Iterable, List, Optional

log = logging.getLogger(__name__)


class MotorVoz:
    nombre = "base"

    def hablar(self, texto: str) -> None:
        raise NotImplementedError

    def precalentar(self, textos: Iterable[str]) -> None:
        """Prepara de antemano frases conocidas (plantillas). Opcional."""

    def cerrar(self) -> None:
        pass


class VozTexto(MotorVoz):
    """Sin audio: la frase solo aparece en pantalla y en consola."""
    nombre = "texto"

    def hablar(self, texto: str) -> None:
        print(f"[voz] {texto}", flush=True)


class VozSistema(MotorVoz):
    """espeak-ng / espeak (Linux) o `say` (macOS)."""
    nombre = "sistema"

    def __init__(self) -> None:
        if platform.system() == "Darwin" and shutil.which("say"):
            self._cmd = ["say", "-v", "Paulina"]
        elif shutil.which("espeak-ng"):
            self._cmd = ["espeak-ng", "-v", "es", "-s", "165"]
        elif shutil.which("espeak"):
            self._cmd = ["espeak", "-v", "es", "-s", "165"]
        else:
            raise RuntimeError("no hay espeak-ng, espeak ni say")

    def hablar(self, texto: str) -> None:
        subprocess.run(self._cmd + [texto], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------------------
# Piper
# ---------------------------------------------------------------------------

def _reproductor_wav() -> Optional[List[str]]:
    for cmd in (["afplay"], ["pw-play"], ["paplay"], ["aplay", "-q"]):
        if shutil.which(cmd[0]):
            return cmd
    return None


class VozPiper(MotorVoz):
    """Piper (piper-tts ≥ 1.3) con caché de audio por texto.

    Las plantillas son un conjunto finito, así que `precalentar` las sintetiza
    todas en segundo plano al inicio (~70 frases, 15–25 s en CPU) y en la
    sesión solo queda reproducir; una frase aún no sintetizada se genera al
    momento. Medido en el equipo
    de desarrollo (CPU x86, voz es_MX-claude-high): ~0.25–0.30 s por frase,
    RTF ≈ 0.11. `[?]` Sin medir en el Mac Studio M2 Ultra.
    """
    nombre = "piper"

    def __init__(self, ruta_voz: Path) -> None:
        from piper import PiperVoice  # dependencia opcional: extra [voz]

        ruta_voz = Path(ruta_voz)
        if not ruta_voz.exists():
            raise FileNotFoundError(f"no existe la voz Piper {ruta_voz}")
        self._voz = PiperVoice.load(str(ruta_voz))
        self._cache: Dict[str, bytes] = {}
        self._lock = threading.Lock()       # precalentado y habla en hilos distintos
        self._dir = Path(tempfile.mkdtemp(prefix="estela_voz_"))
        self._sd = None
        try:
            import sounddevice as sd
            sd.query_devices(kind="output")
            self._sd = sd
        except Exception:                    # sin PortAudio o sin salida
            self._cmd = _reproductor_wav()
            if self._cmd is None:
                raise RuntimeError("no hay forma de reproducir audio")

    def _sintetizar(self, texto: str) -> bytes:
        with self._lock:
            wav = self._cache.get(texto)
            if wav is None:
                buf = io.BytesIO()
                with wave.open(buf, "wb") as w:
                    self._voz.synthesize_wav(texto, w)
                wav = self._cache[texto] = buf.getvalue()
            return wav

    def precalentar(self, textos: Iterable[str]) -> None:
        t0 = time.perf_counter()
        n = 0
        for t in textos:
            if t not in self._cache:
                self._sintetizar(t)
                n += 1
        log.info("Piper: %d frases precalculadas en %.1f s", n,
                 time.perf_counter() - t0)

    def hablar(self, texto: str) -> None:
        wav = self._sintetizar(texto)
        if self._sd is not None:
            import numpy as np
            with wave.open(io.BytesIO(wav)) as r:
                datos = np.frombuffer(r.readframes(r.getnframes()), dtype=np.int16)
                self._sd.play(datos, r.getframerate())
            self._sd.wait()
            return
        ruta = self._dir / f"{abs(hash(texto))}.wav"
        if not ruta.exists():
            ruta.write_bytes(wav)
        subprocess.run(self._cmd + [str(ruta)], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def cerrar(self) -> None:
        shutil.rmtree(self._dir, ignore_errors=True)


def crear_motor(preferido: str, ruta_voz_piper: Optional[Path]) -> MotorVoz:
    """Crea el motor pedido y cae al siguiente si no está disponible."""
    cadena = {"piper": ["piper", "sistema", "texto"],
              "sistema": ["sistema", "texto"],
              "texto": ["texto"]}.get(preferido)
    if cadena is None:
        raise ValueError(f"motor de voz desconocido: {preferido}")
    for nombre in cadena:
        try:
            if nombre == "piper":
                if ruta_voz_piper is None:
                    raise FileNotFoundError("no se encontró ninguna voz Piper")
                return VozPiper(ruta_voz_piper)
            if nombre == "sistema":
                return VozSistema()
            return VozTexto()
        except Exception as e:                # noqa: BLE001 — fallback explícito
            log.warning("Voz '%s' no disponible (%s); probando la siguiente.",
                        nombre, e)
    return VozTexto()


def buscar_voz_piper(directorio: Path) -> Optional[Path]:
    """Primera voz `es_*.onnx` en el directorio, o None."""
    if not directorio.is_dir():
        return None
    voces = sorted(p for p in directorio.glob("es_*.onnx"))
    return voces[0] if voces else None


__all__ = ["MotorVoz", "VozTexto", "VozSistema", "VozPiper", "crear_motor",
           "buscar_voz_piper"]
