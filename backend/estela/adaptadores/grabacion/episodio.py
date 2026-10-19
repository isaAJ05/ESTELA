"""Episodios de pose etiquetados: el banco grabado para referencias y umbrales.

Un episodio es una toma de un ejercicio con **una** etiqueta: `correcto` o
uno de los `error_id` del skill. Se guarda solo la pose que da el estimador
(33 landmarks de mundo y de imagen por frame), **nunca** frames de vídeo
(CLAUDE.md §6). Con la pose se pueden recalcular todas las medidas de
`geometria.py` aunque cambien, y dibujar el esqueleto para revisar la toma.

Formato: un `.npz` comprimido por episodio, cargable sin pickle.

=========  ================  ==========================================
clave      forma             contenido
=========  ================  ==========================================
formato    ()                `FORMATO`
meta       ()                JSON: skill, etiqueta, persona, fuente...
t_ms       (n,) int64        tiempo desde el inicio de la toma
presente   (n,) bool         False si el estimador no vio a nadie
mundo      (n, 33, 4) f32    landmarks de mundo [x, y, z, vis]; NaN
imagen     (n, 33, 4) f32    landmarks de imagen [x, y, z, vis]; NaN
=========  ================  ==========================================

`[F]` Los landmarks de mundo y de imagen son biométricos derivados de una
persona: con consentimiento (Ley 1581/2012) y fuera del repositorio
(`grabaciones/` está en `.gitignore`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple, Union

import numpy as np

from ...dominio.feedback.contrato import MuestraPose
from ...dominio.feedback.motor.skill import Skill
from ..pose.landmarks import NOMBRES_MEDIAPIPE, muestra_desde_arrays

FORMATO = "estela-episodio-pose/1"
CORRECTO = "correcto"
_N = len(NOMBRES_MEDIAPIPE)


class EtiquetaInvalida(ValueError):
    pass


def etiquetas_validas(skill: Skill) -> List[str]:
    """`correcto` y los errores del catálogo cerrado del skill (ADR-004 §2.1)."""
    return [CORRECTO, *dict.fromkeys(r.error_id for r in skill.reglas)]


def validar_etiqueta(skill: Skill, etiqueta: str) -> None:
    validas = etiquetas_validas(skill)
    if etiqueta not in validas:
        raise EtiquetaInvalida(
            f"etiqueta '{etiqueta}' no existe en {skill.skill_id}; "
            f"válidas: {', '.join(validas)}")


@dataclass
class Episodio:
    meta: Dict[str, Any]
    t_ms: np.ndarray
    presente: np.ndarray
    mundo: np.ndarray
    imagen: np.ndarray

    @property
    def n_frames(self) -> int:
        return len(self.t_ms)

    @property
    def fps_efectivo(self) -> float:
        """Frames por segundo que llegó a procesar el estimador (puede ser
        menor que el de la cámara: la fuente descarta los frames viejos)."""
        if self.n_frames < 2:
            return 0.0
        return 1000.0 * (self.n_frames - 1) / max(float(self.t_ms[-1] - self.t_ms[0]), 1.0)

    def muestras(self) -> Iterator[Tuple[int, Optional[MuestraPose], Optional[np.ndarray]]]:
        """(t_ms, muestra, landmarks de imagen) por frame, como el estimador."""
        fuente = self.meta.get("modelo_pose", "episodio")
        for i in range(self.n_frames):
            t = int(self.t_ms[i])
            if not self.presente[i]:
                yield t, None, None
                continue
            yield t, muestra_desde_arrays(t, self.mundo[i], self.imagen[i], fuente), self.imagen[i]


@dataclass
class Grabacion:
    """Acumula los frames de una toma en memoria hasta guardarla o descartarla."""
    skill: Skill
    etiqueta: str
    persona: str
    fuente: str
    modelo_pose: str
    notas: str = ""
    _t: List[int] = field(default_factory=list)
    _mundo: List[Optional[np.ndarray]] = field(default_factory=list)
    _imagen: List[Optional[np.ndarray]] = field(default_factory=list)
    _t0: Optional[int] = None
    inicio: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        validar_etiqueta(self.skill, self.etiqueta)
        if not self.persona.strip():
            raise ValueError("falta el código de persona (p. ej. p01)")

    @property
    def n_frames(self) -> int:
        return len(self._t)

    @property
    def duracion_ms(self) -> int:
        return self._t[-1] if self._t else 0

    def agregar(self, t_ms: int, mundo: Optional[np.ndarray],
                imagen: Optional[np.ndarray]) -> None:
        if self._t0 is None:
            self._t0 = int(t_ms)
        self._t.append(int(t_ms) - self._t0)
        self._mundo.append(None if mundo is None else np.asarray(mundo, np.float32))
        self._imagen.append(None if imagen is None else np.asarray(imagen, np.float32))

    def episodio(self, extra: Optional[Dict[str, Any]] = None) -> Episodio:
        n = self.n_frames
        mundo = np.full((n, _N, 4), np.nan, np.float32)
        imagen = np.full((n, _N, 4), np.nan, np.float32)
        presente = np.zeros(n, bool)
        for i, (m, im) in enumerate(zip(self._mundo, self._imagen)):
            if m is not None and im is not None:
                mundo[i], imagen[i], presente[i] = m, im, True
        meta = {
            "skill_id": self.skill.skill_id,
            "skill_version": self.skill.version,
            "etiqueta": self.etiqueta,
            "persona": self.persona,
            "fuente": self.fuente,
            "modelo_pose": self.modelo_pose,
            "inicio": self.inicio.isoformat(timespec="seconds"),
            "notas": self.notas,
            **(extra or {}),
        }
        return Episodio(meta, np.asarray(self._t, np.int64), presente, mundo, imagen)


def ruta_episodio(raiz: Union[str, Path], ep: Episodio) -> Path:
    """`<raiz>/<skill_id>/<etiqueta>/<persona>_<AAAAMMDD-HHMMSS>.npz`"""
    m = ep.meta
    sello = datetime.fromisoformat(m["inicio"]).strftime("%Y%m%d-%H%M%S")
    base = Path(raiz) / m["skill_id"] / m["etiqueta"]
    ruta, k = base / f"{m['persona']}_{sello}.npz", 1
    while ruta.exists():
        k += 1
        ruta = base / f"{m['persona']}_{sello}_{k}.npz"
    return ruta


def guardar(ep: Episodio, ruta: Union[str, Path]) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    meta = {**ep.meta, "n_frames": ep.n_frames,
            "fps_efectivo": round(ep.fps_efectivo, 2),
            "frames_sin_persona": int((~ep.presente).sum())}
    np.savez_compressed(ruta, formato=np.array(FORMATO),
                        meta=np.array(json.dumps(meta, ensure_ascii=False)),
                        t_ms=ep.t_ms, presente=ep.presente,
                        mundo=ep.mundo, imagen=ep.imagen)
    return ruta


def leer(ruta: Union[str, Path]) -> Episodio:
    with np.load(ruta, allow_pickle=False) as d:
        if str(d["formato"]) != FORMATO:
            raise ValueError(f"{ruta}: formato desconocido {d['formato']}")
        return Episodio(json.loads(str(d["meta"])), d["t_ms"], d["presente"],
                        d["mundo"], d["imagen"])


def buscar(raiz: Union[str, Path], skill_id: str,
           etiquetas: Optional[Sequence[str]] = None) -> List[Path]:
    """Episodios de un skill, opcionalmente filtrados por etiqueta."""
    base = Path(raiz) / skill_id
    if not base.is_dir():
        return []
    return sorted(p for p in base.glob("*/*.npz")
                  if etiquetas is None or p.parent.name in etiquetas)


__all__ = ["FORMATO", "CORRECTO", "Episodio", "Grabacion", "EtiquetaInvalida",
           "etiquetas_validas", "validar_etiqueta", "ruta_episodio", "guardar",
           "leer", "buscar"]
