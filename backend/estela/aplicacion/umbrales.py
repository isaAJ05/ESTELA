"""Umbrales relativos a la referencia (ADR-004 §2.1–2.2, EXP-006).

Con umbrales «referencia», cada regla que declara `relativa` en su skill se
evalúa contra la referencia del ejercicio, y su forma absoluta queda de
respaldo:

* `desviacion` con `k`: el motor calcula el umbral en cada frame,
  `k × max(σ_ref, ruido)`, con el σ del instante alineado. En los frames sin
  referencia (sin DTW, coste alto) evalúa el respaldo absoluto.
* agregado `max`/`min` con `extremo`: el umbral se resuelve aquí, una sola
  vez, contra el extremo de la referencia: `extremo ∓ k × max(σ, ruido)`, con
  el σ del frame del extremo. Es estático y no necesita DTW.

Si la referencia no trae la medida, la regla se queda absoluta. Con umbrales
«absolutos» (por defecto) el skill no cambia.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Optional

from ..dominio.feedback.motor.skill import Condicion, Regla, Skill

UMBRALES = ("absolutos", "referencia")


def con_umbrales_de_referencia(skill: Skill, referencia: Optional[Mapping[str, Any]],
                               k: Optional[float] = None) -> Skill:
    """`k`, si se da, sustituye la de todas las reglas relativas (barridos de
    EXP-005 y EXP-006)."""
    return replace(skill, reglas=tuple(_relativa(r, referencia or {}, k)
                                       for r in skill.reglas))


def _relativa(regla: Regla, referencia: Mapping[str, Any], k: Optional[float]) -> Regla:
    forma = regla.relativa
    if forma is None or forma.medida.nombre not in referencia.get("medidas", ()):
        return regla
    condicion = forma.condicion if k is None else replace(forma.condicion, k=k)
    respaldo = (regla.medida, regla.condicion)
    if condicion.extremo is not None:
        umbral = umbral_de_extremo(referencia, forma.medida.nombre, condicion)
        if umbral is None:
            return regla
        condicion, respaldo = Condicion(op=condicion.op, umbral=umbral), None
    return replace(regla, medida=forma.medida, condicion=condicion, respaldo=respaldo,
                   umbral_origen=forma.umbral_origen,
                   umbrales_severidad=forma.umbrales_severidad or regla.umbrales_severidad,
                   relativa=None)


def umbral_de_extremo(referencia: Mapping[str, Any], nombre: str,
                      condicion: Condicion) -> Optional[float]:
    """`extremo − k·escala` con `<`/`<=` y `extremo + k·escala` con `>`/`>=`,
    donde escala = max(σ en el frame del extremo, ruido). None si la
    referencia no es cíclica o no tiene la medida."""
    angulos = referencia.get("angulos") or {}
    nombres = list(referencia.get("medidas", ()))
    if nombre not in nombres or not angulos.get("media"):
        return None
    columna = nombres.index(nombre)
    validos = [(fila[columna], i) for i, fila in enumerate(angulos["media"])
               if fila[columna] is not None]
    if not validos:
        return None
    valor, i = (max if condicion.extremo == "max" else min)(validos)
    sigmas = angulos.get("sigma") or []
    sigma = sigmas[i][columna] if i < len(sigmas) else None
    escala = max(sigma or 0.0, condicion.ruido)
    signo = -1.0 if condicion.op in ("<", "<=") else 1.0
    return valor + signo * condicion.k * escala


__all__ = ["UMBRALES", "con_umbrales_de_referencia", "umbral_de_extremo"]
