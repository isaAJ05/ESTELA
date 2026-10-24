"""Arnés de medición del Informe 2.

Reproduce vídeos por la `Sesion` real (MediaPipe + motor + plantillas + cola
de voz) y calcula las métricas de `metricas_informe`. Escribe:

    feedback_testing/resultados/INFORME2-metricas.md    (para pegar en el informe)
    feedback_testing/resultados/INFORME2-metricas.json  (datos por vídeo y por frame)

Uso (desde `backend/`):

    python -m feedback_testing.informe2                      # todo, vídeos por defecto
    python -m feedback_testing.informe2 --rapido             # 1 vídeo por ejercicio, 8 s
    python -m feedback_testing.informe2 --videos a.mp4:jumping_jacks b.mp4:plancha
    python -m feedback_testing.informe2 --anotaciones datos_locales/anotaciones
    python -m feedback_testing.informe2 --camara 0 --ejercicio jumping_jacks --duracion-s 60

Qué corre:

1. **Corrida principal** (modelo `--modelo`, por defecto full) a ritmo real con
   las dos políticas de fuente: `ultimo` (como `FuenteCamara`: se procesa el
   frame más reciente y se descartan los viejos) y `cola` (como `FuenteVideo`:
   todos los frames, el retraso se acumula). Latencia por etapa, FPS, retraso,
   silencios, detección → voz y mensajes.
2. **Variantes de MediaPipe** lite / full / heavy (EXP-004) a ritmo máximo:
   latencia de pose, capacidad en FPS, % de frames con persona y jitter en la
   plancha mantenida.
3. **DTW incremental sin banda frente a banda Sakoe-Chiba** (EXP-010): se
   repiten las observaciones de la corrida principal por los dos alineadores.
4. **Plantilla frente a LLM** (EXP-001) con el banco sintético de `runner.py`;
   la condición F necesita `llama-server` (solo en la Mac).
5. **RTF de Piper** sobre `frases_de_rutina`.
6. **Precisión, recobrado, sobrecorrección, mensajes correctos y κ** si hay
   anotaciones (`metricas_informe`, formato `estela-anotacion-v1`).

Lo que no se puede medir sale como «pendiente de medición: <qué falta>».
Ningún vídeo, imagen ni landmark se escribe a disco; el JSON lleva solo
métricas derivadas (tiempos, motivos, mensajes).
"""

from __future__ import annotations

import os

os.environ.setdefault("GLOG_minloglevel", "2")        # silencia logs de mediapipe
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import argparse
import hashlib
import importlib.metadata
import io
import json
import math
import platform
import subprocess
import sys
import threading
import time
import urllib.request
import wave
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from estela import config
from estela.adaptadores.voz.cola import ColaVoz
from estela.adaptadores.voz.motores import MotorVoz, buscar_voz_piper
from estela.aplicacion.dtw import AlineadorDTW
from estela.aplicacion.puertos import PRIORIDAD_FEEDBACK
from estela.aplicacion.rutina import cargar_catalogo, cargar_rutina, rutina_de_un_ejercicio
from estela.aplicacion.sesion import Sesion, frases_de_rutina

from . import metricas_informe as mi

BACKEND = config.RAIZ
PROYECTO = BACKEND.parent
#: datos locales que nunca se suben (Ley 1581/2012): anotaciones y vídeos de personas
DATOS_LOCALES = BACKEND / "datos_locales"
RESULTADOS = Path(__file__).resolve().parent / "resultados"
SALIDA_MD = RESULTADOS / "INFORME2-metricas.md"
SALIDA_JSON = RESULTADOS / "INFORME2-metricas.json"

#: vídeos públicos de internet (no son personas del proyecto)
RAICES_VIDEO = (
    PROYECTO / "PRUEBAS" / "Prueba red neuronal (dataset-pose-deteccion-conteo)" / "DATASET" / "videos",
    PROYECTO.parent / "docs_estela" / "investigacion" / "fuentes" / "datasets" / "videos",
)
#: carpeta → ejercicio. La abducción se decide por el prefijo del archivo.
CARPETAS = {
    "jumping_jack": "jumping_jacks", "Jumping Jacks": "jumping_jacks",
    "marcha_rodillas": "marcha_rodillas", "Marcha rodillas": "marcha_rodillas",
    "Plancha": "plancha", "Abdución de caderas pies": "abduccion",
}
MODELOS_POSE = ("lite", "full", "heavy")
URL_LLM = "http://127.0.0.1:8080"
#: objetivo «infinito» para que la sesión no termine a mitad de vídeo
OBJETIVO_SIN_FIN = 10_000


# ---------------------------------------------------------------------------
# Equipo y entorno
# ---------------------------------------------------------------------------

def _version(paquete: str) -> Optional[str]:
    try:
        return importlib.metadata.version(paquete)
    except importlib.metadata.PackageNotFoundError:
        return None


def _cpu() -> str:
    try:
        if platform.system() == "Darwin":
            return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                  capture_output=True, text=True).stdout.strip()
        for linea in Path("/proc/cpuinfo").read_text().splitlines():
            if linea.startswith("model name"):
                return linea.split(":", 1)[1].strip()
    except Exception:                                     # noqa: BLE001
        pass
    return platform.processor() or "desconocida"


def _memoria_gb() -> Optional[float]:
    try:
        if platform.system() == "Darwin":
            b = int(subprocess.run(["sysctl", "-n", "hw.memsize"],
                                   capture_output=True, text=True).stdout)
            return round(b / 2**30, 1)
        for linea in Path("/proc/meminfo").read_text().splitlines():
            if linea.startswith("MemTotal"):
                return round(int(linea.split()[1]) / 2**20, 1)
    except Exception:                                     # noqa: BLE001
        pass
    return None


def equipo() -> Dict[str, Any]:
    """Qué máquina produjo las cifras, para no mezclar equipos."""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BACKEND,
                                capture_output=True, text=True).stdout.strip() or None
    except Exception:                                     # noqa: BLE001
        commit = None
    return {
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "so": platform.platform(),
        "arquitectura": platform.machine(),
        "cpu": _cpu(),
        "nucleos_logicos": os.cpu_count(),
        "memoria_gb": _memoria_gb(),
        "python": platform.python_version(),
        "mediapipe": _version("mediapipe"),
        "numpy": _version("numpy"),
        "opencv": _version("opencv-python") or _version("opencv-python-headless"),
        "piper_tts": _version("piper-tts"),
        "commit": commit,
    }


def _dirs_modelos() -> List[Path]:
    """`$ESTELA_MODELOS` si está definida, `backend/modelos/` (config) y
    `ESTELA/modelos/` (ubicación anterior a la separación del backend)."""
    extra = [Path(os.environ["ESTELA_MODELOS"])] if os.environ.get("ESTELA_MODELOS") else []
    return extra + [config.MODELOS, PROYECTO / "modelos"]


def ruta_modelo_pose(variante: str) -> Optional[Path]:
    for d in _dirs_modelos():
        p = d / f"pose_landmarker_{variante}.task"
        if p.is_file():
            return p
    return None


def ruta_voz_piper() -> Optional[Path]:
    for d in [x / "voces" for x in _dirs_modelos()]:
        v = buscar_voz_piper(d)
        if v is not None:
            return v
    return None


def importar_cv2() -> Tuple[Any, Optional[str]]:
    """(cv2, None) o (None, motivo exacto)."""
    try:
        import cv2
        return cv2, None
    except Exception as e:                                # noqa: BLE001
        return None, f"no se puede importar cv2 ({type(e).__name__}: {e})"


# ---------------------------------------------------------------------------
# Vídeos
# ---------------------------------------------------------------------------

@dataclass
class Video:
    ruta: Path
    ejercicio_id: str
    fps: float = 0.0
    frames: int = 0
    ancho: int = 0
    alto: int = 0
    sha1: str = ""
    #: vídeo del que sale la referencia DTW del ejercicio (EXP-009: no usarlo para juzgar)
    es_referencia: bool = False
    anotacion: Optional[mi.Anotacion] = None

    @property
    def nombre(self) -> str:
        return self.ruta.name

    @property
    def duracion_s(self) -> float:
        return self.frames / self.fps if self.fps else 0.0

    def a_dict(self) -> Dict[str, Any]:
        return {"video": self.nombre, "carpeta": self.ruta.parent.name,
                "ejercicio_id": self.ejercicio_id, "fps": round(self.fps, 3),
                "frames": self.frames, "resolucion": f"{self.ancho}x{self.alto}",
                "duracion_s": round(self.duracion_s, 1), "sha1": self.sha1[:12],
                "es_referencia": self.es_referencia}


def _ejercicio_de(ruta: Path) -> Tuple[Optional[str], str]:
    """(ejercicio_id, motivo de exclusión)."""
    carpeta = CARPETAS.get(ruta.parent.name)
    if carpeta is None:
        return None, f"carpeta '{ruta.parent.name}' fuera de los 4 ejercicios (ADR-005/007)"
    if carpeta != "abduccion":
        return carpeta, ""
    nombre = ruta.name.lower()
    if "aducci" in nombre and "abducci" not in nombre:
        return None, "aducción, no abducción"
    if nombre.startswith(("izq", "izquierda")):
        return "abduccion_cadera_izq", ""
    if nombre.startswith("der"):
        return "abduccion_cadera_der", ""
    return None, "abducción sin lado en el nombre (izq/der)"


def _sha1(ruta: Path) -> str:
    h = hashlib.sha1()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _videos_de_referencia(catalogo) -> Dict[str, str]:
    return {sid: (ej.referencia or {}).get("fuente", {}).get("video", "")
            for sid, ej in catalogo.items()}


def describir_video(cv2, ruta: Path, ejercicio_id: str, catalogo) -> Video:
    cap = cv2.VideoCapture(str(ruta))
    try:
        if not cap.isOpened():
            raise RuntimeError(f"no se pudo abrir {ruta}")
        v = Video(ruta, ejercicio_id, fps=float(cap.get(cv2.CAP_PROP_FPS) or 30.0),
                  frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                  ancho=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                  alto=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    finally:
        cap.release()
    v.sha1 = _sha1(ruta)
    v.es_referencia = ruta.name == _videos_de_referencia(catalogo).get(ejercicio_id)
    return v


def descubrir_videos(cv2, catalogo, raices: Iterable[Path] = RAICES_VIDEO
                     ) -> Tuple[List[Video], List[Dict[str, str]]]:
    """Vídeos de los 4 ejercicios en las carpetas conocidas, sin duplicados
    (mismo SHA-1). Devuelve (vídeos, excluidos con su motivo)."""
    videos: List[Video] = []
    excluidos: List[Dict[str, str]] = []
    vistos: Dict[str, str] = {}
    for raiz in raices:
        if not raiz.is_dir():
            excluidos.append({"video": str(raiz), "motivo": "carpeta no encontrada"})
            continue
        for ruta in sorted(raiz.glob("*/*.mp4")):
            ej, motivo = _ejercicio_de(ruta)
            if ej is None:
                excluidos.append({"video": f"{ruta.parent.name}/{ruta.name}", "motivo": motivo})
                continue
            v = describir_video(cv2, ruta, ej, catalogo)
            if v.sha1 in vistos:
                excluidos.append({"video": f"{ruta.parent.name}/{ruta.name}",
                                  "motivo": f"duplicado de {vistos[v.sha1]}"})
                continue
            vistos[v.sha1] = f"{ruta.parent.name}/{ruta.name}"
            videos.append(v)
    return videos, excluidos


# ---------------------------------------------------------------------------
# Voz
# ---------------------------------------------------------------------------

class VozMuda(MotorVoz):
    """Voz de texto sin imprimir: la frase no ocupa tiempo."""
    nombre = "texto"

    def hablar(self, texto: str) -> None:
        self.ultimo_inicio_audio = time.perf_counter()


class VozPiperSinAudio(MotorVoz):
    """Piper de verdad (síntesis con caché, como `VozPiper`), pero en lugar de
    reproducir espera lo que dura el audio. Mide síntesis y ocupación de la
    cola sin sonar; no incluye la latencia del dispositivo de audio `[?]`."""
    nombre = "piper-sin-audio"

    def __init__(self, ruta_voz: Path) -> None:
        from piper import PiperVoice
        self._voz = PiperVoice.load(str(ruta_voz))
        self._cache: Dict[str, Tuple[bytes, float]] = {}
        self._lock = threading.Lock()
        self.ruta_voz = ruta_voz

    def sintetizar(self, texto: str) -> Tuple[bytes, float, float]:
        """(wav, duración del audio en s, segundos de síntesis; 0 si en caché)."""
        with self._lock:
            if texto in self._cache:
                wav, dur = self._cache[texto]
                return wav, dur, 0.0
            t0 = time.perf_counter()
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                self._voz.synthesize_wav(texto, w)
            t_sint = time.perf_counter() - t0
            wav = buf.getvalue()
            with wave.open(io.BytesIO(wav)) as r:
                dur = r.getnframes() / float(r.getframerate())
            self._cache[texto] = (wav, dur)
            return wav, dur, t_sint

    def precalentar(self, textos: Iterable[str]) -> None:
        for t in textos:
            self.sintetizar(t)

    def hablar(self, texto: str) -> None:
        _, dur, _ = self.sintetizar(texto)
        self.ultimo_inicio_audio = time.perf_counter()
        time.sleep(dur)


def crear_voz(nombre: str) -> Tuple[MotorVoz, str]:
    """(motor, descripción). `auto` = Piper sin audio si hay voz; si no, texto."""
    if nombre in ("auto", "piper-sin-audio", "piper"):
        ruta = ruta_voz_piper()
        try:
            if ruta is None:
                raise FileNotFoundError("no hay ninguna voz Piper es_*.onnx")
            if nombre == "piper":
                from estela.adaptadores.voz.motores import VozPiper
                return VozPiper(ruta), f"Piper con audio ({ruta.name})"
            return VozPiperSinAudio(ruta), f"Piper sin audio ({ruta.name})"
        except Exception as e:                            # noqa: BLE001
            if nombre != "auto":
                raise
            return VozMuda(), f"texto (Piper no disponible: {e})"
    return VozMuda(), "texto"


# ---------------------------------------------------------------------------
# Reproducción de una fuente por la sesión
# ---------------------------------------------------------------------------

@dataclass
class Corrida:
    """Resultado de pasar una fuente por la sesión."""
    etiqueta: str
    fuente: Dict[str, Any]
    ejercicio_id: str
    politica: str                       # "ultimo" o "cola"
    ritmo: str                          # "real" o "max"
    modelo: str
    frames_fuente: int = 0
    #: por frame procesado: t_ms, llegada, inicio y fin (perf_counter, s)
    t_ms: List[int] = field(default_factory=list)
    llegada: List[float] = field(default_factory=list)
    inicio: List[float] = field(default_factory=list)
    fin: List[float] = field(default_factory=list)
    registro: List[Dict[str, Any]] = field(default_factory=list)
    voz: List[Dict[str, Any]] = field(default_factory=list)
    resumen: Dict[str, Any] = field(default_factory=dict)
    calentamiento_ms: Optional[float] = None

    @property
    def duracion_pared_s(self) -> float:
        return (self.fin[-1] - self.llegada[0]) if self.fin else 0.0

    def rendimiento(self) -> Dict[str, Any]:
        return mi.rendimiento(self.frames_fuente, len(self.t_ms), self.duracion_pared_s)

    def retraso(self) -> Dict[str, Any]:
        if self.ritmo != "real":
            return mi.retraso_acumulado([], [])
        return mi.retraso_acumulado(self.llegada, self.fin)

    def mensajes(self) -> List[mi.MensajeEmitido]:
        return [mi.MensajeEmitido(e["t_ms"], e["mensaje"]["error_id"],
                                  e["mensaje"]["segmento"], e["mensaje"]["lado"],
                                  e["mensaje"]["severidad"], e["mensaje"]["texto"],
                                  e["skill_id"])
                for e in self.registro if e.get("mensaje")]

    def deteccion_a_voz(self) -> List[Dict[str, Any]]:
        """Por mensaje (corrección o refuerzo): llegada del frame → encolado →
        inicio de audio. La n-ésima llamada a `decir` con prioridad de
        feedback es el n-ésimo mensaje de la sesión."""
        con_msg = [i for i, e in enumerate(self.registro) if e.get("mensaje")]
        feedback = [v for v in self.voz if v["prioridad"] == PRIORIDAD_FEEDBACK]
        res = []
        for i, v in zip(con_msg, feedback):
            e = self.registro[i]
            d = {"t_ms": e["t_ms"], "refuerzo": e["mensaje"]["refuerzo"],
                 "descartada": v["descartada"],
                 "frame_a_encolado_s": v["t_encolado"] - self.llegada[i]}
            if v.get("t_inicio_audio") is not None:
                d["encolado_a_audio_s"] = v["t_inicio_audio"] - v["t_encolado"]
                d["total_s"] = v["t_inicio_audio"] - self.llegada[i]
            res.append(d)
        return res

    def sin_medidas(self) -> List[Dict[str, Any]]:
        """Registro sin las medidas de la observación (no van a disco)."""
        return [{k: v for k, v in e.items() if k != "medidas"} for e in self.registro]


class _EmisorComoCamara:
    """Publica los frames de un vídeo a su ritmo nominal y se queda solo con
    el último, como `FuenteCamara` (mismo esquema de secuencia y descarte)."""

    def __init__(self, cv2, ruta: Path, fps: float, t0: float,
                 frame_ini: int, frame_fin: Optional[int]) -> None:
        self._cap = cv2.VideoCapture(str(ruta))
        if frame_ini:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_ini)
        self.fps, self.t0 = fps, t0
        self._i, self._fin = frame_ini, frame_fin
        self._i0 = frame_ini
        self._cv = threading.Condition()
        self._ultimo: Optional[Tuple[Any, int, float]] = None
        self._seq = self._leido = 0
        self._activa = True
        self.descartados = 0
        self.emitidos = 0
        self._hilo = threading.Thread(target=self._bucle, daemon=True,
                                      name="informe2-emisor")
        self._hilo.start()

    def _bucle(self) -> None:
        while self._activa and (self._fin is None or self._i < self._fin):
            ok, frame = self._cap.read()
            if not ok:
                break
            t_ms = int(self._i * 1000.0 / self.fps)
            llegada = self.t0 + (self._i - self._i0) / self.fps
            self._i += 1
            espera = llegada - time.perf_counter()
            if espera > 0:
                time.sleep(espera)
            with self._cv:
                if self._seq > self._leido:
                    self.descartados += 1
                self._ultimo = (frame, t_ms, llegada)
                self._seq += 1
                self.emitidos += 1
                self._cv.notify()
        with self._cv:
            self._activa = False
            self._cv.notify_all()

    def leer(self, timeout: float = 5.0):
        with self._cv:
            if not self._cv.wait_for(lambda: self._seq > self._leido or not self._activa,
                                     timeout):
                return None
            if self._seq <= self._leido:
                return None
            self._leido = self._seq
            return self._ultimo

    def cerrar(self) -> None:
        self._activa = False
        self._hilo.join(timeout=2.0)
        self._cap.release()


def _nuevo_estimador(modelo: str):
    from estela.adaptadores.pose.estimador import EstimadorPose
    import numpy as np
    ruta = ruta_modelo_pose(modelo)
    if ruta is None:
        raise FileNotFoundError(f"no existe pose_landmarker_{modelo}.task "
                                "(python scripts/descargar_modelos.py --heavy)")
    est = EstimadorPose(ruta)
    # La primera inferencia es lenta (carga del grafo): se paga fuera de la
    # medición y se reporta aparte.
    negro = np.zeros((256, 256, 3), np.uint8)
    t0 = time.perf_counter()
    est.estimar(negro, 0)
    calentamiento = (time.perf_counter() - t0) * 1000.0
    est.estimar(negro, 1)
    return est, calentamiento


def reproducir_video(cv2, video: Video, catalogo, modelo: str, politica: str,
                     ritmo: str, motor_voz: MotorVoz, max_s: Optional[float] = None,
                     tramo_ms: Optional[Tuple[int, int]] = None) -> Corrida:
    """Pasa un vídeo por una `Sesion` de un solo ejercicio.

    `politica` "cola": se procesan todos los frames en orden (`FuenteVideo`);
    con `ritmo` "real" cada frame no se procesa antes de su marca nominal.
    `politica` "ultimo": un hilo publica los frames a ritmo real y la sesión
    toma siempre el más reciente (`FuenteCamara`); exige ritmo real.
    """
    if politica == "ultimo" and ritmo != "real":
        raise ValueError("la política 'ultimo' solo tiene sentido a ritmo real")
    est, calentamiento = _nuevo_estimador(modelo)
    cola = ColaVoz(motor_voz)
    rutina = rutina_de_un_ejercicio(video.ejercicio_id, OBJETIVO_SIN_FIN, catalogo)
    sesion = Sesion(rutina, catalogo, est, cola, registrar=True)
    frame_ini = int(math.ceil(tramo_ms[0] * video.fps / 1000.0)) if tramo_ms else 0
    frame_fin = int(tramo_ms[1] * video.fps / 1000.0) if tramo_ms else None
    if max_s is not None:
        tope = frame_ini + int(max_s * video.fps)
        frame_fin = tope if frame_fin is None else min(frame_fin, tope)
    c = Corrida(f"{video.nombre} · {modelo} · {politica} · {ritmo}",
                {"tipo": "video", **video.a_dict()}, video.ejercicio_id,
                politica, ritmo, modelo, calentamiento_ms=calentamiento)
    try:
        t0 = time.perf_counter() + 0.05
        if politica == "ultimo":
            emisor = _EmisorComoCamara(cv2, video.ruta, video.fps, t0, frame_ini, frame_fin)
            try:
                while True:
                    leido = emisor.leer()
                    if leido is None:
                        break
                    frame, t_ms, llegada = leido
                    _procesa(c, sesion, frame, t_ms, llegada)
            finally:
                emisor.cerrar()
            c.frames_fuente = emisor.emitidos
        else:
            cap = cv2.VideoCapture(str(video.ruta))
            if frame_ini:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_ini)
            i = frame_ini
            try:
                while frame_fin is None or i < frame_fin:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    t_ms = int(i * 1000.0 / video.fps)
                    llegada = t0 + (i - frame_ini) / video.fps
                    if ritmo == "real":
                        espera = llegada - time.perf_counter()
                        if espera > 0:
                            time.sleep(espera)
                    else:
                        llegada = time.perf_counter()
                    _procesa(c, sesion, frame, t_ms, llegada)
                    i += 1
            finally:
                cap.release()
            c.frames_fuente = len(c.t_ms)
    finally:
        cola.cerrar(esperar=True)
        est.cerrar()
    c.registro = sesion.registro
    c.voz = list(cola.registro)
    c.resumen = sesion.resumen()
    return c


def _procesa(c: Corrida, sesion: Sesion, frame, t_ms: int, llegada: float) -> None:
    inicio = time.perf_counter()
    sesion.procesar(frame, t_ms)
    c.t_ms.append(t_ms)
    c.llegada.append(llegada)
    c.inicio.append(inicio)
    c.fin.append(time.perf_counter())


def reproducir_camara(indice: int, ejercicio_id: str, catalogo, modelo: str,
                      motor_voz: MotorVoz, duracion_s: float) -> Corrida:
    """Cámara real con `FuenteCamara` (política «último frame»). Graba a la
    persona que está delante: solo con su consentimiento; no guarda frames."""
    from estela.adaptadores.captura.fuente import FuenteCamara
    est, calentamiento = _nuevo_estimador(modelo)
    fuente = FuenteCamara(indice)
    cola = ColaVoz(motor_voz)
    rutina = rutina_de_un_ejercicio(ejercicio_id, OBJETIVO_SIN_FIN, catalogo)
    sesion = Sesion(rutina, catalogo, est, cola, registrar=True)
    import cv2
    ancho = int(fuente._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto = int(fuente._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    c = Corrida(f"cámara {indice} · {modelo} · ultimo · real",
                {"tipo": "camara", "indice": indice, "resolucion": f"{ancho}x{alto}",
                 "fps": fuente.fps, "ejercicio_id": ejercicio_id},
                ejercicio_id, "ultimo", "real", modelo, calentamiento_ms=calentamiento)
    # FuenteCamara marca con time.monotonic(); se pasa al reloj de perf_counter
    desfase = time.perf_counter() - time.monotonic()
    fin = time.perf_counter() + duracion_s
    try:
        while time.perf_counter() < fin:
            leido = fuente.leer()
            if leido is None:
                break
            frame, t_ms = leido
            _procesa(c, sesion, frame, t_ms, fuente._t0 + t_ms / 1000.0 + desfase)
    finally:
        fuente.cerrar()
        cola.cerrar(esperar=True)
        est.cerrar()
    c.frames_fuente = len(c.t_ms) + fuente.descartados
    c.registro, c.voz, c.resumen = sesion.registro, list(cola.registro), sesion.resumen()
    return c


# ---------------------------------------------------------------------------
# Análisis de corridas
# ---------------------------------------------------------------------------

ETAPAS = ("pose", "geometria", "segmentacion", "dtw", "decision", "verbalizacion",
          "motor", "total")


def latencias_por_etapa(corridas: Sequence[Corrida]) -> Dict[str, Dict[str, Any]]:
    vals: Dict[str, List[float]] = {e: [] for e in ETAPAS}
    procesar: List[float] = []
    for c in corridas:
        for e in c.registro:
            for etapa, ms in e["lat"].items():
                vals.setdefault(etapa, []).append(ms)
        procesar += [(f - i) * 1000.0 for i, f in zip(c.inicio, c.fin)]
    res = {etapa: mi.resumen_serie(v) for etapa, v in vals.items()}
    res["procesar (pared)"] = mi.resumen_serie(procesar)
    return res


def jitter_plancha(c: Corrida, medidas: Sequence[str], ventana: int = 15
                   ) -> Dict[str, Optional[float]]:
    """Jitter de cada medida en la plancha mantenida (fase `mantenimiento`),
    con confianza ≥ 0,5. Fuera de ese tramo queda None (hueco)."""
    res = {}
    for nombre in medidas:
        serie: List[Optional[float]] = []
        for e in c.registro:
            m = e.get("medidas")
            if not m or e.get("fase") != "mantenimiento":
                serie.append(None)
                continue
            valor = m["angulos"].get(nombre, m["distancias"].get(nombre))
            conf = m["confianza"].get(nombre, 0.0)
            serie.append(float(valor) if valor is not None and conf >= 0.5 else None)
        res[nombre] = mi.jitter(serie, ventana)
    return res


def replicar_dtw(corridas: Sequence[Corrida], catalogo,
                 bandas_frac: Sequence[float]) -> Dict[str, Any]:
    """EXP-010: repite las observaciones de cada corrida por el DTW incremental
    sin banda y con las bandas, frame a frame, con las mismas llamadas que hace
    la sesión (todo frame con persona, también en pausa). La banda en frames
    es `fracción × longitud de la referencia` (mínimo 1) y se pasa como
    `dtw.banda` de la referencia, igual que en `referencia.json`."""
    acum: Dict[str, Dict[str, Any]] = {}
    global_: Dict[str, Tuple[List[int], List[float]]] = {}
    for c in corridas:
        ref = catalogo[c.ejercicio_id].referencia
        clasico = AlineadorDTW(_con_banda(ref, None))
        if not clasico.disponible:
            acum.setdefault(c.ejercicio_id, {"disponible": False})
            continue
        m = clasico.longitud_referencia
        variantes: Dict[str, AlineadorDTW] = {"sin banda": clasico}
        for f in bandas_frac:
            variantes[f"banda {f:.0%}"] = AlineadorDTW(_con_banda(ref, max(1, round(f * m))))
        d = acum.setdefault(c.ejercicio_id, {
            "disponible": True, "longitud_referencia": m,
            "variantes": {k: {"banda": al.banda, "longitud": [], "latencia_ms": [],
                              "con_resultado": 0, "frames": 0, "progreso_1": 0,
                              "dif_progreso": [], "dif_ref": [], "dif_coste": []}
                          for k, al in variantes.items()}})
        for e in c.registro:
            med = e.get("medidas")
            if not med:
                continue
            conf = med["confianza"]
            obs = SimpleNamespace(repeticion=e["repeticion"], t_ms=e["t_ms"],
                                  angulos=med["angulos"], distancias=med["distancias"],
                                  confianza_de=lambda n, conf=conf: float(conf.get(n, 0.0)))
            resultados = {}
            for k, al in variantes.items():
                t0 = time.perf_counter()
                r = al.actualizar(obs)
                ms = (time.perf_counter() - t0) * 1000.0
                v = d["variantes"][k]
                v["longitud"].append(al.longitud_prefijo)
                v["latencia_ms"].append(ms)
                v["frames"] += 1
                g = global_.setdefault(k, ([], []))
                g[0].append(al.longitud_prefijo)
                g[1].append(ms)
                if r is not None:
                    v["con_resultado"] += 1
                    v["progreso_1"] += int(r.progreso == 1.0)
                resultados[k] = r
            base = resultados["sin banda"]
            for k, r in resultados.items():
                if k == "sin banda" or base is None or r is None:
                    continue
                v = d["variantes"][k]
                v["dif_progreso"].append(abs(r.progreso - base.progreso))
                comunes = set(r.angulos_ref) & set(base.angulos_ref)
                if comunes:
                    v["dif_ref"].append(max(abs(r.angulos_ref[x] - base.angulos_ref[x])
                                            for x in comunes))
                v["dif_coste"].append(abs(r.coste - base.coste))
    res: Dict[str, Any] = {}
    for ej, d in acum.items():
        if not d["disponible"]:
            res[ej] = {"disponible": False}
            continue
        filas = {}
        for k, v in d["variantes"].items():
            filas[k] = {
                "banda": v["banda"], "frames": v["frames"],
                "con_resultado": v["con_resultado"],
                "fraccion_con_resultado": v["con_resultado"] / v["frames"] if v["frames"] else None,
                "fraccion_progreso_1": v["progreso_1"] / v["con_resultado"] if v["con_resultado"] else None,
                "latencia": mi.resumen_serie(v["latencia_ms"]),
                "por_longitud": mi.latencia_por_longitud(v["longitud"], v["latencia_ms"]),
                "dif_progreso_max": max(v["dif_progreso"]) if v["dif_progreso"] else None,
                "dif_angulos_ref_max": max(v["dif_ref"]) if v["dif_ref"] else None,
                "dif_coste": mi.resumen_serie(v["dif_coste"]),
            }
        res[ej] = {"disponible": True, "longitud_referencia": d["longitud_referencia"],
                   "variantes": filas}
    res["_global"] = {k: mi.latencia_por_longitud(lon, lat) for k, (lon, lat) in global_.items()}
    return res


def _con_banda(ref: Optional[Mapping[str, Any]], banda: Optional[int]
               ) -> Optional[Dict[str, Any]]:
    """Copia de la referencia con `dtw.banda` cambiada (None = sin banda)."""
    if ref is None:
        return None
    return {**ref, "dtw": {**(ref.get("dtw") or {}), "banda": banda}}


def llm_disponible(url: str = URL_LLM, timeout: float = 0.5) -> Tuple[bool, str]:
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=timeout) as r:
            return r.status == 200, f"llama-server responde en {url}"
    except Exception as e:                                # noqa: BLE001
        return False, f"llama-server no responde en {url} ({type(e).__name__})"


def exp001(condiciones: Sequence[str] = ("A", "F"), repeticiones: int = 3
           ) -> Dict[str, Any]:
    """Plantilla (A) frente a LLM local (F) en el banco sintético de EXP-001."""
    from .metricas import (m2_aserciones_no_soportadas, m3_sobrecorreccion,
                           m4_latencias, m5_determinismo, m7_fallback)
    from .runner import ejecutar
    res: Dict[str, Any] = {}
    for cond in condiciones:
        if cond != "A":
            ok, motivo = llm_disponible()
            if not ok:
                res[cond] = {"pendiente": f"pendiente de medición en la Mac: {motivo}"}
                continue
        resultados, secuencias = ejecutar(cond, repeticiones)
        m4 = m4_latencias(resultados)
        res[cond] = {
            "episodios": len(resultados),
            "M2": m2_aserciones_no_soportadas(resultados),
            "M3": m3_sobrecorreccion(resultados),
            "M5": m5_determinismo(secuencias),
            "M7": m7_fallback(resultados),
            "M4": {k: (None if isinstance(v, float) and math.isnan(v) else v)
                   for k, v in m4.items()},
        }
    return res


def rtf_piper(rutina, catalogo) -> Dict[str, Any]:
    """Tiempo de síntesis / duración del audio para cada frase conocida."""
    ruta = ruta_voz_piper()
    if ruta is None:
        return {"pendiente": "pendiente de medición: no hay voz Piper (scripts/descargar_modelos.py)"}
    try:
        voz = VozPiperSinAudio(ruta)
    except Exception as e:                                # noqa: BLE001
        return {"pendiente": f"pendiente de medición: Piper no carga ({type(e).__name__}: {e})"}
    frases = sorted(frases_de_rutina(rutina, catalogo))
    t_frio = None
    sint, dur, rtf = [], [], []
    for i, f in enumerate(frases):
        _, d, t = voz.sintetizar(f)
        if i == 0:
            t_frio = t                       # la primera paga la inicialización
            continue
        sint.append(t * 1000.0)
        dur.append(d)
        rtf.append(t / d if d else float("nan"))
    return {"voz": ruta.name, "frases": len(frases), "primera_frase_ms": (t_frio or 0) * 1000.0,
            "sintesis_ms": mi.resumen_serie(sint), "duracion_audio_s": mi.resumen_serie(dur),
            "rtf": mi.resumen_serie(rtf), "_motor": voz}


# ---------------------------------------------------------------------------
# Anotaciones
# ---------------------------------------------------------------------------

def buscar_anotaciones(rutas: Sequence[Path]) -> Tuple[List[Tuple[Path, mi.Anotacion]], List[str]]:
    encontradas, errores = [], []
    archivos: List[Path] = []
    for r in rutas:
        if r.is_dir():
            archivos += sorted(r.glob("*.json"))
        elif r.is_file():
            archivos.append(r)
    for a in archivos:
        try:
            encontradas.append((a, mi.cargar_anotacion(a)))
        except Exception as e:                            # noqa: BLE001
            errores.append(f"{a.name}: {e}")
    return encontradas, errores


def _ruta_video_anotado(archivo: Path, anot: mi.Anotacion) -> Optional[Path]:
    for d in (archivo.parent, DATOS_LOCALES / "videos", archivo.parent.parent / "videos"):
        p = d / anot.video
        if p.is_file():
            return p
    return None


def reglas_de(catalogo) -> Dict[str, Tuple[str, str]]:
    return {r.error_id: (r.segmento, r.lado.value)
            for ej in catalogo.values() for r in ej.skill.reglas}


def evaluar_anotaciones(cv2, catalogo, anotaciones, modelo: str,
                        tolerancia_ms: int) -> Dict[str, Any]:
    """Corre cada vídeo anotado (ritmo máximo, sin descarte: determinista) y
    compara con la anotación. κ para pares de anotadoras del mismo vídeo.

    Si un vídeo tiene varias anotaciones, la precisión y el recobrado se
    calculan contra **una**: la de `anotadora: "consenso"` si existe; si no,
    la primera por orden alfabético de anotadora. Las demás solo cuentan
    para κ (sumarlas contaría dos veces cada repetición).
    """
    reglas = reglas_de(catalogo)
    por_video: Dict[Tuple[str, str], List[Tuple[Path, mi.Anotacion]]] = {}
    for archivo, anot in anotaciones:
        por_video.setdefault((anot.video, anot.ejercicio_id), []).append((archivo, anot))
    elegidas = [min(lista, key=lambda x: (x[1].anotadora != "consenso", x[1].anotadora))
                for lista in por_video.values()]
    por_ejercicio: Dict[str, Dict[str, mi.Conteo]] = {}
    crudo: Dict[str, Dict[str, mi.Conteo]] = {}
    sobre = {"repeticiones_correctas": 0, "con_correccion": 0}
    correctos = {"mensajes": 0, "correctos": 0}
    vistas: Dict[Tuple[str, str], Corrida] = {}
    detalle, kappas, sin_video = [], [], []
    for archivo, anot in elegidas:
        ruta = _ruta_video_anotado(archivo, anot)
        if ruta is None:
            sin_video.append(f"{archivo.name}: no se encuentra el vídeo '{anot.video}'")
            continue
        clave = (str(ruta), anot.ejercicio_id)
        if clave not in vistas:
            v = describir_video(cv2, ruta, anot.ejercicio_id, catalogo)
            vistas[clave] = reproducir_video(cv2, v, catalogo, modelo, "cola", "max",
                                             VozMuda(), tramo_ms=anot.tramo_ms)
        c = vistas[clave]
        msgs = c.mensajes()
        ids = [r.error_id for r in catalogo[anot.ejercicio_id].skill.reglas]
        conteos = mi.conteos_por_error(anot.repeticiones, msgs, tolerancia_ms, ids)
        disparos = [(e["t_ms"], eid) for e in c.registro for eid in e.get("disparadas", [])]
        cr = mi.deteccion_cruda(anot.repeticiones, disparos)
        for eid, k in conteos.items():
            por_ejercicio.setdefault(anot.ejercicio_id, {}).setdefault(eid, mi.Conteo()).__iadd__(k)
        for eid, k in cr.items():
            crudo.setdefault(anot.ejercicio_id, {}).setdefault(eid, mi.Conteo()).__iadd__(k)
        s = mi.sobrecorreccion(anot.repeticiones, msgs, tolerancia_ms)
        mc = mi.mensajes_correctos(anot.repeticiones, msgs, reglas, tolerancia_ms)
        sobre["repeticiones_correctas"] += s["repeticiones_correctas"]
        sobre["con_correccion"] += s["con_correccion"]
        correctos["mensajes"] += mc["mensajes"]
        correctos["correctos"] += mc["correctos"]
        detalle.append({"anotacion": archivo.name, "video": anot.video,
                        "ejercicio_id": anot.ejercicio_id, "anotadora": anot.anotadora,
                        "repeticiones": len(anot.repeticiones), "mensajes": len(msgs),
                        "sobrecorreccion": s, "mensajes_correctos": mc,
                        "refuerzos_indebidos": mi.refuerzos_indebidos(anot.repeticiones, msgs)})
    # κ: pares de anotadoras distintas sobre el mismo vídeo y ejercicio
    grupos: Dict[Tuple[str, str], List[mi.Anotacion]] = {}
    for _, a in anotaciones:
        if a.anotadora != "consenso":
            grupos.setdefault((a.video, a.ejercicio_id), []).append(a)
    for (video, ej), lista in grupos.items():
        for i in range(len(lista)):
            for j in range(i + 1, len(lista)):
                if lista[i].anotadora == lista[j].anotadora:
                    continue
                ids = [r.error_id for r in catalogo[ej].skill.reglas] if ej in catalogo else []
                k = mi.kappa_anotadoras(lista[i], lista[j], ids)
                kappas.append({"video": video, "ejercicio_id": ej, **k})
    return {
        "por_ejercicio": {ej: {eid: k.a_dict() for eid, k in d.items()}
                          for ej, d in por_ejercicio.items()},
        "total_por_ejercicio": {ej: mi.agregar(d.values()).a_dict()
                                for ej, d in por_ejercicio.items()},
        "cruda_por_ejercicio": {ej: mi.agregar(d.values()).a_dict() for ej, d in crudo.items()},
        "sobrecorreccion": {**sobre, "tasa": (sobre["con_correccion"] / sobre["repeticiones_correctas"]
                                              if sobre["repeticiones_correctas"] else None)},
        "mensajes_correctos": {**correctos, "tasa": (correctos["correctos"] / correctos["mensajes"]
                                                     if correctos["mensajes"] else None)},
        "kappa": kappas, "detalle": detalle, "sin_video": sin_video,
        "tolerancia_ms": tolerancia_ms,
    }


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

@dataclass
class Opciones:
    videos: Optional[List[Tuple[Path, str]]] = None      # None = descubrir
    raices: Tuple[Path, ...] = RAICES_VIDEO
    modelo: str = "full"
    politicas: Tuple[str, ...] = ("ultimo", "cola")
    modelos: Tuple[str, ...] = MODELOS_POSE
    voz: str = "auto"
    max_s: Optional[float] = None
    max_s_modelos: Optional[float] = 30.0
    bandas_frac: Tuple[float, ...] = (0.1, 0.2)
    anotaciones: Tuple[Path, ...] = (DATOS_LOCALES / "anotaciones",)
    tolerancia_ms: int = 1000
    rapido: bool = False
    camara: Optional[int] = None
    ejercicio: Optional[str] = None
    duracion_s: float = 60.0
    sin_modelos: bool = False
    sin_exp001: bool = False
    sin_piper: bool = False
    salida_md: Path = SALIDA_MD
    salida_json: Path = SALIDA_JSON


def _relativa(p: Path) -> str:
    for base in (PROYECTO.parent, PROYECTO):
        try:
            return str(Path(p).resolve().relative_to(base.resolve()))
        except ValueError:
            continue
    return Path(p).name


def _log(msg: str) -> None:
    print(f"[informe2 {datetime.now():%H:%M:%S}] {msg}", flush=True)


def ejecutar(op: Opciones) -> Dict[str, Any]:
    """Corre todo lo que se pueda y devuelve los resultados (sin escribir)."""
    catalogo = cargar_catalogo()
    rutina = cargar_rutina(config.RUTINAS / "calentamiento_basico.json", catalogo)
    R: Dict[str, Any] = {"equipo": equipo(), "pendientes": {}, "opciones": {
        k: (str(v) if isinstance(v, Path) else v) for k, v in vars(op).items()
        if k not in ("salida_md", "salida_json", "raices", "anotaciones", "videos")}}
    P = R["pendientes"]
    # rutas relativas al proyecto cuando se puede (no se publican rutas personales)
    R["opciones"]["anotaciones"] = [_relativa(a) for a in op.anotaciones]
    R["opciones"]["raices"] = [_relativa(r) for r in op.raices]
    if op.videos is not None:
        R["opciones"]["videos"] = [f"{_relativa(p)}:{e}" for p, e in op.videos]

    # -- voz (y RTF de Piper, que además deja la caché caliente) -------------
    motor, desc_voz = crear_voz(op.voz)
    R["voz"] = desc_voz
    if not op.sin_piper:
        _log("RTF de Piper")
        rtf = rtf_piper(rutina, catalogo)
        motor_rtf = rtf.pop("_motor", None)
        if isinstance(motor, VozPiperSinAudio) and motor_rtf is not None:
            motor = motor_rtf                      # misma voz, caché ya llena
        R["piper"] = rtf
        if "pendiente" in rtf:
            P["piper_rtf"] = rtf["pendiente"]
    if isinstance(motor, VozPiperSinAudio):
        # como en la app: las frases conocidas se sintetizan antes de la sesión;
        # se añaden los anuncios con el objetivo «sin fin» que usa el arnés
        frases = set(frases_de_rutina(rutina, catalogo))
        frases.update(Sesion._anuncio(ej, OBJETIVO_SIN_FIN) for ej in catalogo.values()
                      if ej.soportado)
        t0 = time.perf_counter()
        motor.precalentar(sorted(frases))
        R["voz_precalentado_s"] = time.perf_counter() - t0
    elif "Piper" not in desc_voz:
        P["deteccion_voz_real"] = ("detección → voz medida con voz de texto: no incluye "
                                   "síntesis ni ocupación de la cola por el audio "
                                   f"({desc_voz})")

    # -- EXP-001 ---------------------------------------------------------------
    if not op.sin_exp001:
        _log("EXP-001: plantilla frente a LLM (banco sintético)")
        R["exp001"] = exp001()
        for cond, v in R["exp001"].items():
            if "pendiente" in v:
                P[f"exp001_{cond}"] = v["pendiente"]

    # -- vídeo -----------------------------------------------------------------
    cv2, motivo = importar_cv2()
    if cv2 is None:
        for clave in ("pose", "fps", "retraso", "deteccion_voz", "silencios",
                      "modelos", "dtw", "anotaciones"):
            P[clave] = f"pendiente de medición: {motivo}"
        return R
    if ruta_modelo_pose(op.modelo) is None:
        P["pose"] = f"pendiente de medición: falta pose_landmarker_{op.modelo}.task"
        return R

    corridas: List[Corrida] = []
    if op.camara is not None:
        if not op.ejercicio:
            raise SystemExit("--camara exige --ejercicio")
        _log(f"cámara {op.camara}: {op.duracion_s:.0f} s de {op.ejercicio}")
        corridas.append(reproducir_camara(op.camara, op.ejercicio, catalogo, op.modelo,
                                          motor, op.duracion_s))
        R["videos"], R["excluidos"] = [], []
    else:
        if op.videos is None:
            videos, excluidos = descubrir_videos(cv2, catalogo, op.raices)
        else:
            videos = [describir_video(cv2, p, e, catalogo) for p, e in op.videos]
            excluidos = []
        if op.rapido:
            # uno por ejercicio; el de referencia solo si no hay otro (plancha)
            uno: Dict[str, Video] = {}
            for v in sorted(videos, key=lambda v: v.es_referencia):
                uno.setdefault(v.ejercicio_id, v)
            videos = list(uno.values())
        R["videos"] = [v.a_dict() for v in videos]
        R["excluidos"] = excluidos
        max_s = 8.0 if op.rapido else op.max_s
        if not videos:
            P["pose"] = "pendiente de medición: no se encontró ningún vídeo"
        for politica in op.politicas:
            for v in videos:
                _log(f"{v.nombre} ({v.ejercicio_id}) · {op.modelo} · {politica} · ritmo real")
                corridas.append(reproducir_video(cv2, v, catalogo, op.modelo, politica,
                                                 "real", motor, max_s=max_s))
    R["corridas"] = corridas

    # -- variantes de MediaPipe ------------------------------------------------
    if not op.sin_modelos and op.camara is None and R["videos"]:
        R["modelos"] = {}
        for m in op.modelos:
            if ruta_modelo_pose(m) is None:
                P[f"modelo_{m}"] = (f"pendiente de medición: falta pose_landmarker_{m}.task "
                                    "(python scripts/descargar_modelos.py --heavy)")
                continue
            cs = []
            for v in videos:
                _log(f"{v.nombre} · {m} · cola · ritmo máximo")
                cs.append(reproducir_video(cv2, v, catalogo, m, "cola", "max", VozMuda(),
                                           max_s=8.0 if op.rapido else op.max_s_modelos))
            R["modelos"][m] = cs
        if not any(v.ejercicio_id == "plancha" for v in videos):
            P["jitter"] = "pendiente de medición: no hay vídeo de plancha (único tramo quieto)"

    # -- DTW (EXP-010) -----------------------------------------------------------
    base = [c for c in corridas if c.politica == "cola"] or corridas
    if base:
        _log("EXP-010: réplica DTW sin banda frente a banda")
        R["dtw"] = replicar_dtw(base, catalogo, op.bandas_frac)

    # -- anotaciones -------------------------------------------------------------
    anotaciones, errores = buscar_anotaciones(op.anotaciones)
    R["anotaciones_con_error"] = errores
    if anotaciones:
        _log(f"{len(anotaciones)} anotaciones")
        R["anotaciones"] = evaluar_anotaciones(cv2, catalogo, anotaciones, op.modelo,
                                               op.tolerancia_ms)
        if not R["anotaciones"]["kappa"]:
            P["kappa"] = ("pendiente de medición: ningún vídeo tiene dos anotaciones "
                          "de anotadoras distintas")
    else:
        donde = ", ".join(_relativa(a) for a in op.anotaciones)
        P["anotaciones"] = ("pendiente de medición: no hay anotaciones humanas "
                            f"(formato estela-anotacion-v1 en {donde}); las 5 sesiones "
                            "grabadas aún no existen")
    return R


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------

def _n(x: Any, dec: int = 1, sufijo: str = "") -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/d"
    if isinstance(x, int) and not isinstance(x, bool):
        return f"{x}{sufijo}"
    return f"{x:.{dec}f}".replace(".", ",") + sufijo


def _pct(x: Optional[float]) -> str:
    return "n/d" if x is None or (isinstance(x, float) and math.isnan(x)) else _n(100 * x, 1, " %")


def _fila_resumen(nombre: str, r: Mapping[str, Any], dec: int = 2) -> str:
    return (f"| {nombre} | {r['n']} | {_n(r['media'], dec)} | {_n(r['p50'], dec)} | "
            f"{_n(r['p95'], dec)} | {_n(r['max'], dec)} |")


def _fps_por_video(corridas: Sequence[Corrida]) -> List[Dict[str, Any]]:
    filas = []
    for c in corridas:
        r = c.rendimiento()
        filas.append({"video": c.fuente.get("video", c.etiqueta), "ejercicio": c.ejercicio_id,
                      "fps_fuente": c.fuente.get("fps"), **r, "retraso": c.retraso()})
    return filas


def objetivos(R: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Una fila por objetivo de `OBJETIVOS_INFORME2`: medido, estado y fuente."""
    P = R["pendientes"]
    filas = []
    corridas = R.get("corridas", [])
    ultimo = [c for c in corridas if c.politica == "ultimo"] or corridas

    def fila(clave, valor, medido, nota):
        estado = mi.evaluar(clave, valor)
        filas.append({"clave": clave, "descripcion": mi.OBJETIVOS_INFORME2[clave]["descripcion"],
                      "objetivo": mi.texto_objetivo(clave), "medido": medido if valor is not None else nota,
                      "valor": valor, "estado": estado})

    lat = latencias_por_etapa(ultimo) if ultimo else None
    p95 = lat["pose"]["p95"] if lat else None
    fila("pose_p95_ms", p95, f"{_n(p95, 1)} ms (modelo {R['opciones']['modelo']}, n = {lat['pose']['n'] if lat else 0})",
         P.get("pose", "pendiente de medición: sin corrida de vídeo"))

    evaluables = [f for f in _fps_por_video([c for c in corridas if c.politica == "ultimo"])
                  if (f["fps_fuente"] or 0) >= 25 and f["fps_sostenidos"] is not None]
    minimo = min((f["fps_sostenidos"] for f in evaluables), default=None)
    fila("fps_sostenidos", minimo,
         f"mínimo por vídeo {_n(minimo, 1)} fps ({len(evaluables)} vídeos con fuente ≥ 25 fps, "
         "política «último frame»)",
         P.get("fps", "pendiente de medición: ningún vídeo con fuente ≥ 25 fps a ritmo real"))

    totales = [d["total_s"] for c in ultimo for d in c.deteccion_a_voz()
               if not d["refuerzo"] and "total_s" in d]
    p95v = mi.percentil(totales, 95)
    fila("deteccion_voz_p95_s", p95v,
         f"{_n(p95v, 2)} s (n = {len(totales)} correcciones habladas; {R.get('voz', '')})",
         P.get("deteccion_voz", "pendiente de medición: ninguna corrección hablada"))

    an = R.get("anotaciones")
    pend = P.get("anotaciones", "pendiente de medición: sin anotaciones")
    if an and an["total_por_ejercicio"]:
        precs = {ej: t["precision"] for ej, t in an["total_por_ejercicio"].items()}
        recs = {ej: t["recobrado"] for ej, t in an["total_por_ejercicio"].items()}
        pmin = min((v for v in precs.values() if v is not None), default=None)
        rmin = min((v for v in recs.values() if v is not None), default=None)
        fila("precision", pmin, f"mínimo por ejercicio {_pct(pmin)}", pend)
        fila("recobrado", rmin, f"mínimo por ejercicio {_pct(rmin)}", pend)
        s = an["sobrecorreccion"]
        fila("sobrecorreccion", s["tasa"],
             f"{_pct(s['tasa'])} ({s['con_correccion']}/{s['repeticiones_correctas']} reps)",
             "pendiente de medición: ninguna repetición anotada como correcta")
        mc = an["mensajes_correctos"]
        fila("mensajes_correctos", mc["tasa"],
             f"{_pct(mc['tasa'])} ({mc['correctos']}/{mc['mensajes']})",
             "pendiente de medición: ninguna corrección en los vídeos anotados")
    else:
        for clave in ("precision", "recobrado", "sobrecorreccion", "mensajes_correctos"):
            fila(clave, None, "", pend)
    return filas


def escribir_markdown(R: Mapping[str, Any]) -> str:
    eq = R["equipo"]
    corridas: List[Corrida] = R.get("corridas", [])
    ultimo = [c for c in corridas if c.politica == "ultimo"]
    cola = [c for c in corridas if c.politica == "cola"]
    principal = ultimo or corridas
    P = R["pendientes"]
    L: List[str] = []
    L += ["# Informe 2 — métricas medidas", "",
          "> **Cifras preliminares.** Medidas en el equipo de desarrollo indicado abajo, "
          "con vídeos públicos sin anotar. No son el hardware final (Mac Studio M2 Ultra) "
          "ni sesiones de las participantes. Generado por `python -m feedback_testing.informe2`; "
          "no editar a mano.", "",
          "Convención: `[F]` medido aquí · `[I]` inferencia · `[R]` recomendación · `[?]` pendiente.", "",
          "## Equipo", "",
          "| Campo | Valor |", "|---|---|"]
    for k in ("fecha", "so", "arquitectura", "cpu", "nucleos_logicos", "memoria_gb", "python",
              "mediapipe", "numpy", "opencv", "piper_tts", "commit"):
        L.append(f"| {k} | {eq.get(k) if eq.get(k) is not None else 'n/d'} |")
    L.append(f"| modelo de pose (corrida principal) | pose_landmarker_{R['opciones']['modelo']} |")
    L.append(f"| voz | {R.get('voz', 'n/d')} |")
    if "voz_precalentado_s" in R:
        L.append(f"| precalentado de la voz | {_n(R['voz_precalentado_s'], 1)} s antes de medir, "
                 "sin contar las frases ya sintetizadas al medir el RTF (en la app es en segundo "
                 "plano al arrancar) |")
    L.append("")

    # -- objetivos
    L += ["## Resumen frente a los objetivos", "",
          "| Métrica | Objetivo | Medido | Estado |", "|---|---|---|---|"]
    for f in objetivos(R):
        L.append(f"| {f['descripcion']} | {f['objetivo']} | {f['medido']} | **{f['estado']}** |")
    L += ["", "Objetivos aceptados por el equipo (`OBJETIVOS_INFORME2` en "
          "`feedback_testing/metricas_informe.py`).", ""]

    # -- fuentes
    if R.get("videos"):
        L += ["## 1. Fuentes", "",
              "Vídeos públicos de internet (no son personas del proyecto), deduplicados por SHA-1.", "",
              "| Vídeo | Carpeta | Ejercicio | FPS | Resolución | Duración | Referencia DTW |",
              "|---|---|---|---|---|---|---|"]
        for v in R["videos"]:
            L.append(f"| {v['video']} | {v['carpeta']} | {v['ejercicio_id']} | {_n(v['fps'], 2)} | "
                     f"{v['resolucion']} | {_n(v['duracion_s'], 1)} s | {'sí' if v['es_referencia'] else ''} |")
        if R.get("excluidos"):
            L += ["", "Excluidos:", ""]
            for e in R["excluidos"]:
                L.append(f"- `{e['video']}`: {e['motivo']}")
        L.append("")
    elif corridas and corridas[0].fuente.get("tipo") == "camara":
        f = corridas[0].fuente
        L += ["## 1. Fuente", "", f"Cámara {f['indice']}, {f['resolucion']}, {_n(f['fps'], 1)} fps nominales, "
              f"ejercicio {f['ejercicio_id']}.", ""]

    if corridas:
        # -- latencia por etapa
        lat = latencias_por_etapa(principal)
        pol = "último frame" if ultimo else "cola"
        L += [f"## 2. Latencia por etapa (ms) — modelo {R['opciones']['modelo']}, política «{pol}», ritmo real", "",
              "| Etapa | n | media | p50 | p95 | máx |", "|---|---|---|---|---|---|"]
        for etapa in ETAPAS + ("procesar (pared)",):
            if lat.get(etapa) and lat[etapa]["n"]:
                L.append(_fila_resumen(etapa, lat[etapa]))
        cal = [c.calentamiento_ms for c in principal if c.calentamiento_ms is not None]
        L += ["", "`total` solo existe en los frames que llegan al motor (con persona y sin pausa); "
              "`procesar (pared)` es `Sesion.procesar` entero en todos los frames. `verbalizacion` solo "
              "en los frames con mensaje. `motor` = decisión + verbalización.",
              f"La primera inferencia de cada estimador (calentamiento, fuera de la medición) tardó "
              f"{_n(mi.percentil(cal, 50), 0)} ms de mediana." if cal else "", ""]
        L += ["Pose por ejercicio:", "", "| Ejercicio | n | media | p50 | p95 | máx |",
              "|---|---|---|---|---|---|"]
        for ej in sorted({c.ejercicio_id for c in principal}):
            vals = [e["lat"]["pose"] for c in principal if c.ejercicio_id == ej for e in c.registro]
            L.append(_fila_resumen(ej, mi.resumen_serie(vals)))
        L.append("")

        # -- FPS y retraso
        L += ["## 3. FPS sostenidos, frames descartados y retraso acumulado", "",
              "Retraso por frame = fin de su procesamiento − su marca nominal de llegada (ms). "
              "Deriva = pendiente del retraso frente al tiempo (ms por s): ≈ 0 si el sistema da abasto.", ""]
        for nombre, cs in (("último frame (como `FuenteCamara`)", ultimo),
                           ("cola sin descarte (como `FuenteVideo`)", cola)):
            if not cs:
                continue
            L += [f"### Política «{nombre}»", "",
                  "| Vídeo | Ejercicio | FPS fuente | FPS sostenidos | Descartados | Retraso p50 | p95 | máx | final | Deriva |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
            for f in _fps_por_video(cs):
                r = f["retraso"]
                L.append(f"| {f['video']} | {f['ejercicio']} | {_n(f['fps_fuente'], 2)} | "
                         f"{_n(f['fps_sostenidos'], 1)} | {f['descartados']} ({_pct(f['fraccion_descartada'])}) | "
                         f"{_n(r['p50'], 0)} | {_n(r['p95'], 0)} | {_n(r['max'], 0)} | {_n(r['final'], 0)} | "
                         f"{_n(r['deriva_ms_por_s'], 2)} |")
            r = mi.resumen_serie([(f - l) * 1000 for c in cs for l, f in zip(c.llegada, c.fin)])
            proc = sum(len(c.t_ms) for c in cs)
            fuente = sum(c.frames_fuente for c in cs)
            L += ["", f"Total: {proc} de {fuente} frames procesados ({_pct((fuente - proc) / fuente if fuente else None)} "
                  f"descartados); retraso p50 {_n(r['p50'], 0)} ms, p95 {_n(r['p95'], 0)} ms, máx {_n(r['max'], 0)} ms.", ""]
        L += ["`[I]` En vídeo los FPS sostenidos no pueden superar los FPS de la fuente: el objetivo de "
              "25 fps solo se evalúa en vídeos de ≥ 25 fps. La capacidad del equipo (FPS a ritmo máximo) "
              "está en la sección 7.", ""]

        # -- detección → voz
        dv = [d for c in principal for d in c.deteccion_a_voz()]
        corr = [d for d in dv if not d["refuerzo"]]
        L += ["## 4. Detección → inicio de voz", "",
              f"Voz: {R.get('voz', 'n/d')}. Por mensaje: llegada del frame que lo dispara → encolado en "
              "`ColaVoz` → empieza a sonar. Política «último frame», ritmo real.", "",
              "| Tramo (s) | n | media | p50 | p95 | máx |", "|---|---|---|---|---|---|"]
        for nombre, clave in (("frame → encolado", "frame_a_encolado_s"),
                              ("encolado → audio", "encolado_a_audio_s"),
                              ("total (correcciones)", "total_s")):
            L.append(_fila_resumen(nombre, mi.resumen_serie([d[clave] for d in corr if clave in d]), 3))
        esperaron = [d for d in corr if d.get("encolado_a_audio_s", 0) > 0.1]
        libres = [d["total_s"] for d in corr if "total_s" in d and d not in esperaron]
        r_libre = mi.resumen_serie(libres)
        L += ["", f"Correcciones que esperaron a que terminara otra frase (> 0,1 s en la cola): "
              f"{len(esperaron)} de {len([d for d in corr if 'total_s' in d])}. Con la cola libre, "
              f"total p50 {_n(r_libre['p50'], 3)} s, p95 {_n(r_libre['p95'], 3)} s (n = {r_libre['n']}). "
              "`[I]` La espera la causan sobre todo el anuncio del ejercicio al empezar y la frase "
              "anterior: la cola tiene un solo hueco y no interrumpe lo que está sonando."]
        perdidas = sum(1 for d in corr if d["descartada"])
        L += ["", f"Correcciones emitidas: {len(corr)}; no llegaron a sonar (sustituidas en la cola o "
              f"tapadas por un aviso): {perdidas} ({_pct(perdidas / len(corr) if corr else None)}). "
              f"Refuerzos: {len(dv) - len(corr)}.",
              "`[?]` No incluye la latencia del dispositivo de audio." if "sin audio" in R.get("voz", "") else "",
              ""]

        # -- silencios
        sil = mi.tasas_silencio([e for c in principal for e in c.registro])
        L += ["## 5. Silencios por causa", "",
              f"Frames: {sil['frames']}; sin persona: {sil['sin_persona']} ({_pct(sil['tasa_sin_persona'])}); "
              f"en pausa: {sum(sil['pausada'].values())} ({_pct(sil['tasa_pausada'])}) "
              f"{dict(sil['pausada']) if sil['pausada'] else ''}; evaluados por el motor: {sil['evaluados']}.", "",
              "| Motivo (`MOTIVO_*`) | Frames | % de los evaluados |", "|---|---|---|"]
        for m, v in sil["motivos"].items():
            L.append(f"| `{m}` | {v} | {_pct(sil['tasa_motivos'][m])} |")
        L += [f"| corrección | {sil['correcciones']} | {_pct(sil['correcciones'] / sil['evaluados'] if sil['evaluados'] else None)} |",
              f"| refuerzo | {sil['refuerzos']} | {_pct(sil['refuerzos'] / sil['evaluados'] if sil['evaluados'] else None)} |", ""]
        L += ["Por ejercicio (% de los frames evaluados):", "",
              "| Ejercicio | Frames | Sin persona | En pausa | Evaluados | sin_error | confianza_baja | plano_no_observable | evidencia_insuficiente | refractario | fase_silenciada | otros | mensajes |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for ej in sorted({c.ejercicio_id for c in principal}):
            s = mi.tasas_silencio([e for c in principal if c.ejercicio_id == ej for e in c.registro])
            t = s["tasa_motivos"]
            conocidos = ("sin_error", "confianza_baja", "plano_no_observable",
                         "evidencia_insuficiente", "periodo_refractario", "fase_silenciada")
            otros = sum(v for k, v in t.items() if k not in conocidos)
            ev = s["evaluados"]
            L.append(f"| {ej} | {s['frames']} | {_pct(s['tasa_sin_persona'])} | {_pct(s['tasa_pausada'])} | {ev} | " + " | ".join(_pct(t.get(k)) if ev else "n/d" for k in conocidos)
                     + f" | {_pct(otros) if ev else 'n/d'} | {s['correcciones'] + s['refuerzos']} |")
        L.append("")

        # -- mensajes y exactitud
        L += ["## 6. Exactitud del feedback frente a anotación humana", ""]
        an = R.get("anotaciones")
        if an:
            L += [f"Tolerancia de atribución: ± {an['tolerancia_ms']} ms. Vídeos a ritmo máximo, sin descarte "
                  "(determinista).", "",
                  "| Ejercicio | Mensajes | VP | FP | Fuera | Precisión | Episodios | Detectados | Recobrado | F1 | Precisión cruda | Recobrado crudo |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|"]
            for ej, t in an["total_por_ejercicio"].items():
                cr = an["cruda_por_ejercicio"].get(ej, {})
                L.append(f"| {ej} | {t['vp'] + t['fp']} | {t['vp']} | {t['fp']} | {t['fuera']} | "
                         f"{_pct(t['precision'])} | {t['episodios']} | {t['detectados']} | "
                         f"{_pct(t['recobrado'])} | {_pct(t['f1'])} | {_pct(cr.get('precision'))} | "
                         f"{_pct(cr.get('recobrado'))} |")
            L += ["", "| Ejercicio | error_id | VP | FP | Precisión | Episodios | Recobrado | F1 |",
                  "|---|---|---|---|---|---|---|---|"]
            for ej, d in an["por_ejercicio"].items():
                for eid, t in d.items():
                    L.append(f"| {ej} | `{eid}` | {t['vp']} | {t['fp']} | {_pct(t['precision'])} | "
                             f"{t['episodios']} | {_pct(t['recobrado'])} | {_pct(t['f1'])} |")
            s, mc = an["sobrecorreccion"], an["mensajes_correctos"]
            L += ["", f"- Sobrecorrección: {_pct(s['tasa'])} ({s['con_correccion']} de "
                  f"{s['repeticiones_correctas']} repeticiones correctas).",
                  f"- Mensajes correctos: {_pct(mc['tasa'])} ({mc['correctos']} de {mc['mensajes']})."]
            if an["kappa"]:
                L += ["", "| Vídeo | Ejercicio | Anotadoras | Pares | κ |", "|---|---|---|---|---|"]
                for k in an["kappa"]:
                    L.append(f"| {k['video']} | {k['ejercicio_id']} | {' / '.join(k['anotadoras'])} | "
                             f"{k['pares']} | {_n(k['kappa'], 2)} |")
            for x in an["sin_video"]:
                L.append(f"- {x}")
            L.append("")
        else:
            L += [f"**{P.get('anotaciones', 'pendiente de medición')}.** Precisión, recobrado, F1, "
                  "sobrecorrección, mensajes correctos y κ necesitan la hoja de anotación "
                  "(`estela-anotacion-v1`, ver README).", ""]
        msgs = [m for c in principal for m in c.mensajes()]
        m2 = mi.tasa_aserciones_no_soportadas(msgs)
        L += [f"Aserciones no soportadas (M2 de EXP-001) en los mensajes emitidos sobre los vídeos: "
              f"{_pct(m2['tasa'])} ({m2['no_soportadas']} de {m2['mensajes']} correcciones). No necesita anotación.", "",
              "**Correcciones en los vídeos de control (descriptivo, no es la sobrecorrección).** "
              "EXP-009 §4 trata estos vídeos como ejecuciones supuestamente correctas, pero nadie los ha "
              "anotado: una corrección aquí es un candidato a falso positivo, no un falso positivo.", "",
              "| Vídeo | Ejercicio | Reps contadas | Correcciones (error_id × veces) | Refuerzos |",
              "|---|---|---|---|---|"]
        for c in principal:
            cuenta: Dict[str, int] = {}
            ref = 0
            for m in c.mensajes():
                if m.error_id is None:
                    ref += 1
                else:
                    cuenta[m.error_id] = cuenta.get(m.error_id, 0) + 1
            paso = c.resumen["pasos"][0] if c.resumen.get("pasos") else {}
            texto = ", ".join(f"`{k}` × {v}" for k, v in sorted(cuenta.items())) or "—"
            L.append(f"| {c.fuente.get('video', c.etiqueta)}{' (ref.)' if c.fuente.get('es_referencia') else ''} | "
                     f"{c.ejercicio_id} | {paso.get('completadas', 'n/d')} | {texto} | {ref} |")
        L.append("")

    # -- modelos
    if R.get("modelos"):
        L += ["## 7. Variantes de MediaPipe (EXP-004) — ritmo máximo, cola sin descarte", "",
              f"Mismos vídeos, recortados a {_n(R['opciones']['max_s_modelos'] or 0, 0)} s. "
              "Capacidad = frames / tiempo de pared procesando a ritmo máximo (incluye decodificar el vídeo).", "",
              "| Modelo | Frames | Pose media | p50 | p95 | máx | Capacidad (fps) | % frames con persona | Reps contadas | Correcciones |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for m, cs in R["modelos"].items():
            pose = mi.resumen_serie([e["lat"]["pose"] for c in cs for e in c.registro])
            frames = sum(len(c.t_ms) for c in cs)
            pared = sum(c.duracion_pared_s for c in cs)
            persona = sum(1 for c in cs for e in c.registro if e["persona"])
            reps = sum(c.resumen["pasos"][0]["completadas"] for c in cs if c.ejercicio_id != "plancha")
            corr = sum(1 for c in cs for msg in c.mensajes() if msg.error_id)
            L.append(f"| {m} | {frames} | {_n(pose['media'], 1)} | {_n(pose['p50'], 1)} | {_n(pose['p95'], 1)} | "
                     f"{_n(pose['max'], 1)} | {_n(frames / pared if pared else None, 1)} | "
                     f"{_pct(persona / frames if frames else None)} | {reps} | {corr} |")
        L += ["", "p95 de pose frente al objetivo (≤ 33 ms): " + ", ".join(
            f"{m} **{mi.evaluar('pose_p95_ms', mi.resumen_serie([e['lat']['pose'] for c in cs for e in c.registro])['p95'])}**"
            for m, cs in R["modelos"].items()) + ".", ""]
        planchas = {m: [c for c in cs if c.ejercicio_id == "plancha"] for m, cs in R["modelos"].items()}
        if any(planchas.values()):
            medidas = ("tronco_inclinacion", "cabeza_adelantada", "alineacion_cadera")
            L += ["Jitter en la plancha mantenida (fase `mantenimiento`, confianza ≥ 0,5): desviación del "
                  "residuo frente a una media móvil de 15 frames. Es el único tramo quieto de los vídeos; "
                  "en los demás el temblor se mezcla con el movimiento.", "",
                  "| Modelo | " + " | ".join(medidas) + " |", "|---" * (len(medidas) + 1) + "|"]
            for m, cs in planchas.items():
                j = {k: [] for k in medidas}
                for c in cs:
                    for k, v in jitter_plancha(c, medidas).items():
                        if v is not None:
                            j[k].append(v)
                L.append(f"| {m} | " + " | ".join(_n(sum(v) / len(v), 3) if v else "n/d" for v in j.values()) + " |")
            L += ["", "Unidades: grados en los ángulos; escalas corporales en `alineacion_cadera`.", ""]
        elif "jitter" in P:
            L += [f"Jitter: {P['jitter']}.", ""]

    # -- DTW
    if R.get("dtw"):
        L += ["## 8. DTW incremental sin banda frente a banda Sakoe-Chiba (EXP-010)", "",
              "Réplica fuera de línea de las observaciones de la corrida «cola» (modelo "
              f"{R['opciones']['modelo']}), con las mismas llamadas que hace la sesión. Banda en frames "
              f"= fracción × longitud de la referencia ({', '.join(_n(f, 2) for f in R['opciones']['bandas_frac'])}).", "",
              "| Ejercicio | Ref. (frames) | Variante | Frames | Con resultado | Latencia media | p50 | p95 | máx | ms por frame de prefijo | Prefijo máx | progreso = 1 | Δ progreso máx | Δ ángulos_ref máx |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for ej, d in R["dtw"].items():
            if ej.startswith("_"):
                continue
            if not d["disponible"]:
                L.append(f"| {ej} | — | sin referencia DTW (isométrico o ausente) | | | | | | | | | | | |")
                continue
            for nombre, v in d["variantes"].items():
                lat = v["latencia"]
                if v["banda"] is not None:
                    nombre = f"{nombre} ({v['banda']} fr)"
                L.append(f"| {ej} | {d['longitud_referencia']} | {nombre} | {v['frames']} | "
                         f"{_pct(v['fraccion_con_resultado'])} | {_n(lat['media'], 2)} | {_n(lat['p50'], 2)} | "
                         f"{_n(lat['p95'], 2)} | {_n(lat['max'], 2)} | "
                         f"{_n(v['por_longitud']['pendiente_ms_por_frame'], 3)} | "
                         f"{v['por_longitud']['longitud_max']} | {_pct(v['fraccion_progreso_1'])} | "
                         f"{_n(v['dif_progreso_max'], 3)} | {_n(v['dif_angulos_ref_max'], 2)} |")
        glob = R["dtw"].get("_global", {})
        if glob:
            L += ["", "Latencia según la longitud del prefijo, todos los ejercicios juntos (ms):", "",
                  "| Prefijo (frames) | Variante | n | media | p50 | p95 | máx |",
                  "|---|---|---|---|---|---|---|"]
            for nombre, g in glob.items():
                for f in g["tramos"]:
                    tramo = f"{f['desde']}–{f['hasta'] if f['hasta'] is not None else '∞'}"
                    L.append(f"| {tramo} | {nombre} | {f['n']} | {_n(f['media'], 2)} | "
                             f"{_n(f['p50'], 2)} | {_n(f['p95'], 2)} | {_n(f['max'], 2)} |")
        L += ["", "El DTW es incremental y de final abierto: cada frame actualiza una columna de la "
              "matriz en O(m) y se reinicia en cada repetición, así que la latencia no debería crecer con el "
              "prefijo (columna «ms por frame de prefijo»). La banda se centra en el instante que tocaría al "
              "ritmo de la referencia; las columnas «Δ» comparan cada banda con la variante sin banda.", ""]

    # -- EXP-001
    if R.get("exp001"):
        L += ["## 9. Plantilla frente a LLM local (EXP-001, banco sintético)", "",
              "| Condición | Episodios | M2 aserciones no soportadas | M3 sobrecorrección | M5 determinismo | M7 fallback | Verbalización p50 (ms) | p95 | máx |",
              "|---|---|---|---|---|---|---|---|---|"]
        for cond, v in R["exp001"].items():
            if "pendiente" in v:
                L.append(f"| {cond} | {v['pendiente']} | | | | | | | |")
                continue
            m4 = v["M4"]
            L.append(f"| {cond} | {v['episodios']} | {_pct(v['M2'][0])} ({v['M2'][1]}) | {_pct(v['M3'][0])} ({v['M3'][1]}) | "
                     f"{_pct(v['M5'][0])} | {_pct(v['M7'][0])} | {_n(m4['verbalizacion_p50_ms'], 4)} | "
                     f"{_n(m4['verbalizacion_p95_ms'], 4)} | {_n(m4['verbalizacion_max_ms'], 4)} |")
        L += ["", "La M1 real (exactitud de contenido) y la comparación sobre vídeo necesitan las anotaciones "
              "(sección 6). La condición F solo puede correr donde haya `llama-server` (la Mac).", ""]

    # -- Piper
    if R.get("piper"):
        p = R["piper"]
        L += ["## 10. Piper: factor de tiempo real", ""]
        if "pendiente" in p:
            L += [p["pendiente"], ""]
        else:
            L += [f"Voz `{p['voz']}`, {p['frases']} frases de `frases_de_rutina` (calentamiento básico). "
                  f"RTF = tiempo de síntesis / duración del audio; < 1 es más rápido que el tiempo real. "
                  f"La primera frase (inicialización) tardó {_n(p['primera_frase_ms'], 0)} ms y no entra en la tabla.", "",
                  "| Medida | n | media | p50 | p95 | máx |", "|---|---|---|---|---|---|",
                  _fila_resumen("síntesis (ms)", p["sintesis_ms"], 1),
                  _fila_resumen("duración del audio (s)", p["duracion_audio_s"], 2),
                  _fila_resumen("RTF", p["rtf"], 3), ""]

    # -- pendientes
    L += ["## Pendiente de medición", ""]
    if P:
        for k, v in P.items():
            L.append(f"- **{k}**: {v}")
    L += ["- **hardware final**: todas las cifras de tiempo hay que repetirlas en la Mac Studio M2 Ultra.",
          "- **sesiones reales**: las 5 participantes aún no han grabado la rutina; ninguna cifra de esta "
          "página procede de ellas.", ""]
    return "\n".join(x for x in L if x is not None)


def a_json(R: Mapping[str, Any]) -> Dict[str, Any]:
    """Datos crudos: por corrida, series por frame (sin medidas corporales)."""
    def corrida(c: Corrida) -> Dict[str, Any]:
        return {
            "etiqueta": c.etiqueta, "fuente": c.fuente, "ejercicio_id": c.ejercicio_id,
            "politica": c.politica, "ritmo": c.ritmo, "modelo": c.modelo,
            "calentamiento_ms": c.calentamiento_ms, "rendimiento": c.rendimiento(),
            "retraso": c.retraso(), "silencios": mi.tasas_silencio(c.registro),
            "resumen_sesion": c.resumen, "deteccion_a_voz": c.deteccion_a_voz(),
            "por_frame": {
                "t_ms": c.t_ms,
                "retraso_ms": ([round((f - l) * 1000, 2) for l, f in zip(c.llegada, c.fin)]
                               if c.ritmo == "real" else None),
                "procesar_ms": [round((f - i) * 1000, 2) for i, f in zip(c.inicio, c.fin)],
                "lat": [{k: round(v, 3) for k, v in e["lat"].items()} for e in c.registro],
                "motivo": [e["motivo_silencio"] or ("mensaje" if e["mensaje"] else
                           ("pausa" if e["pausada"] else (None if e["persona"] else "sin_persona")))
                           for e in c.registro],
                "repeticion": [e["repeticion"] for e in c.registro],
            },
        }
    out = {k: v for k, v in R.items() if k not in ("corridas", "modelos")}
    out["objetivos"] = objetivos(R)
    out["objetivos_definicion"] = mi.OBJETIVOS_INFORME2
    out["corridas"] = [corrida(c) for c in R.get("corridas", [])]
    if R.get("modelos"):
        out["modelos"] = {m: [corrida(c) for c in cs] for m, cs in R["modelos"].items()}
    return out


def escribir(R: Mapping[str, Any], salida_md: Path = SALIDA_MD,
             salida_json: Path = SALIDA_JSON) -> str:
    md = escribir_markdown(R)
    salida_md.parent.mkdir(parents=True, exist_ok=True)
    salida_md.write_text(md + "\n", encoding="utf-8")
    salida_json.write_text(json.dumps(a_json(R), ensure_ascii=False, default=str),
                           encoding="utf-8")
    return md


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _argumentos(argv=None) -> Opciones:
    p = argparse.ArgumentParser(prog="python -m feedback_testing.informe2",
                                description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--videos", nargs="+", metavar="RUTA:EJERCICIO",
                   help="vídeos concretos (si no, los de PRUEBAS/ y docs_estela/)")
    p.add_argument("--raices", nargs="+", type=Path, default=list(RAICES_VIDEO),
                   help="carpetas con subcarpetas por ejercicio (defecto: PRUEBAS/ y docs_estela/)")
    p.add_argument("--modelo", choices=MODELOS_POSE, default="full")
    p.add_argument("--modelos", default=",".join(MODELOS_POSE),
                   help="variantes para la comparación (coma)")
    p.add_argument("--politicas", default="ultimo,cola")
    p.add_argument("--voz", choices=("auto", "texto", "piper-sin-audio", "piper"), default="auto",
                   help="auto = Piper sin audio si hay voz, si no texto; piper = con altavoz")
    p.add_argument("--max-segundos", type=float, default=None,
                   help="recorta cada vídeo en la corrida principal")
    p.add_argument("--max-segundos-modelos", type=float, default=30.0)
    p.add_argument("--bandas-frac", default="0.1,0.2")
    p.add_argument("--anotaciones", nargs="*", type=Path,
                   default=[DATOS_LOCALES / "anotaciones"])
    p.add_argument("--tolerancia-ms", type=int, default=1000)
    p.add_argument("--rapido", action="store_true", help="1 vídeo por ejercicio, 8 s")
    p.add_argument("--camara", type=int, help="medir con la cámara (consentimiento)")
    p.add_argument("--ejercicio", help="ejercicio con --camara")
    p.add_argument("--duracion-s", type=float, default=60.0)
    p.add_argument("--sin-modelos", action="store_true")
    p.add_argument("--sin-exp001", action="store_true")
    p.add_argument("--sin-piper", action="store_true")
    p.add_argument("--salida-md", type=Path, default=SALIDA_MD)
    p.add_argument("--salida-json", type=Path, default=SALIDA_JSON)
    a = p.parse_args(argv)
    videos = None
    if a.videos:
        videos = []
        for v in a.videos:
            ruta, _, ej = v.rpartition(":")
            if not ruta:
                p.error(f"--videos espera RUTA:EJERCICIO, no '{v}'")
            videos.append((Path(ruta), ej))
    return Opciones(videos=videos, raices=tuple(a.raices), modelo=a.modelo,
                    modelos=tuple(m for m in a.modelos.split(",") if m),
                    politicas=tuple(x for x in a.politicas.split(",") if x), voz=a.voz,
                    max_s=a.max_segundos, max_s_modelos=a.max_segundos_modelos,
                    bandas_frac=tuple(float(x) for x in a.bandas_frac.split(",") if x),
                    anotaciones=tuple(a.anotaciones), tolerancia_ms=a.tolerancia_ms,
                    rapido=a.rapido, camara=a.camara, ejercicio=a.ejercicio,
                    duracion_s=a.duracion_s, sin_modelos=a.sin_modelos,
                    sin_exp001=a.sin_exp001, sin_piper=a.sin_piper,
                    salida_md=a.salida_md, salida_json=a.salida_json)


def main(argv=None) -> int:
    op = _argumentos(argv)
    R = ejecutar(op)
    md = escribir(R, op.salida_md, op.salida_json)
    print(md)
    print(f"\ninforme: {op.salida_md}\ndatos:   {op.salida_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
