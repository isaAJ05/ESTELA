"""Registro por repetición, para revisar a mano lo que vio el sistema (EXP-009).

Por cada repetición (o cada bloque de segundos en un ejercicio isométrico)
guarda si contó, y el mínimo y el máximo de cada medida que importa en el
ejercicio: las de sus reglas, las de su segmentación y sus
`angulos_requeridos`. Con eso se puede contestar «¿por qué contó esa
repetición?» o «¿por qué no corrigió los codos?» sin guardar vídeo: solo
métricas derivadas (CLAUDE.md §6).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ..dominio.conteo.segmentador import (
    EVENTO_COMPLETA, EVENTO_INCOMPLETA, EVENTO_INICIO, EstadoSegmento,
)
from ..dominio.feedback.contrato import Observacion
from .rutina import Ejercicio


def _nombres_de_senal(senal: Any) -> List[str]:
    rutas = [senal] if isinstance(senal, str) else list(senal or ())
    return [r.partition(".")[2] for r in rutas]


def medidas_del_ejercicio(ej: Ejercicio) -> Tuple[str, ...]:
    nombres: List[str] = []
    seg = ej.segmentacion or {}
    for clave in ("senal", "senal_izq", "senal_der"):
        nombres += _nombres_de_senal(seg.get(clave))
    for c in list(seg.get("condiciones", ())) + list(seg.get("requiere", ())):
        nombres += _nombres_de_senal(c.get("senal"))
    for regla in ej.skill.reglas:
        nombres += list(regla.medida.angulos_implicados())
    nombres += list(ej.skill.angulos_requeridos)
    return tuple(dict.fromkeys(n for n in nombres if n))


class RegistroRepeticiones:
    def __init__(self, ej: Ejercicio) -> None:
        self.medidas = medidas_del_ejercicio(ej)
        self.isometrico = ej.unidad == "segundos"
        self.filas: List[Dict[str, Any]] = []
        self._rango: Dict[str, List[float]] = {}
        self._rep: Optional[int] = None
        self._inicio_ms: Optional[int] = None

    def _cierra(self, rep: int, resultado: str, t_ms: int,
                obs: Optional[Observacion] = None) -> None:
        fila: Dict[str, Any] = {
            "rep": rep, "resultado": resultado,
            "t_s": round(t_ms / 1000.0, 1),
            "duracion_s": (round((t_ms - self._inicio_ms) / 1000.0, 1)
                           if self._inicio_ms is not None else None),
        }
        for n in self.medidas:
            r = self._rango.get(n)
            fila[f"{n}_min"] = round(r[0], 2) if r else None
            fila[f"{n}_max"] = round(r[1], 2) if r else None
        if obs is not None:
            # DTW en el frame que cierra la repetición (vuelta al reposo): coste
            # medio del movimiento y hasta dónde llegó en la referencia (EXP-006)
            fila["coste_dtw"] = (round(obs.coste_dtw, 2)
                                 if obs.coste_dtw is not None else None)
            fila["progreso_dtw"] = (round(obs.progreso, 2)
                                    if obs.progreso is not None else None)
        self.filas.append(fila)
        self._rango = {}
        self._inicio_ms = t_ms

    def actualizar(self, obs: Observacion, seg: EstadoSegmento) -> None:
        if seg.repeticion <= 0:
            return
        if self.isometrico:
            if self._rep is not None and seg.repeticion != self._rep:
                self._cierra(self._rep, "bloque", obs.t_ms)
            if self._inicio_ms is None:
                self._inicio_ms = obs.t_ms
        elif seg.evento == EVENTO_INICIO:
            self._rango, self._inicio_ms = {}, obs.t_ms
        self._rep = seg.repeticion
        for n in self.medidas:
            v = obs.angulos.get(n, obs.distancias.get(n))
            if v is None:
                continue
            r = self._rango.setdefault(n, [v, v])
            r[0], r[1] = min(r[0], v), max(r[1], v)
        if not self.isometrico and seg.evento in (EVENTO_COMPLETA, EVENTO_INCOMPLETA):
            self._cierra(seg.repeticion,
                         "cuenta" if seg.evento == EVENTO_COMPLETA else "no_cuenta",
                         obs.t_ms, obs)

    def cerrar(self, t_ms: int) -> None:
        """Bloque isométrico en curso al terminar el paso."""
        if self.isometrico and self._rep is not None and self._rango:
            self._cierra(self._rep, "bloque", t_ms)


def _num(v: Any) -> Any:
    """Coma decimal: el CSV se abre con Excel en español."""
    return str(v).replace(".", ",") if isinstance(v, float) else v


def escribir_csv(pasos: Sequence[Mapping[str, Any]], ruta: Path) -> None:
    """Una fila por repetición de todos los pasos, con las frases dichas en ella."""
    columnas = ["ejercicio", "rep", "resultado", "t_s", "duracion_s", "frases"]
    filas: List[Dict[str, Any]] = []
    for paso in pasos:
        frases: Dict[int, List[str]] = {}
        for m in paso.get("mensajes", ()):
            frases.setdefault(m.get("repeticion"), []).append(m["texto"])
        for f in paso.get("repeticiones", ()):
            fila = {"ejercicio": paso["skill_id"],
                    "frases": " | ".join(frases.get(f["rep"], ())), **f}
            columnas += [k for k in f if k not in columnas]
            filas.append(fila)
    with open(ruta, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=columnas, delimiter=";")
        w.writeheader()
        for fila in filas:
            w.writerow({k: _num(v) for k, v in fila.items()})
