"""Catálogo de ejercicios y rutina de entrenamiento.

El catálogo son los skills de `estela/dominio/feedback/skills/` más su sección opcional
`segmentacion`. Un skill sin `segmentacion` se carga (el motor lo acepta) pero
no se puede usar en sesión. Los skills retirados (`estela/dominio/feedback/skills/retirados/`,
ADR-005) no forman parte del catálogo.

El objetivo de cada paso se mide en repeticiones, salvo en los ejercicios
isométricos (segmentación `isometrico`, p. ej. la plancha), que se miden en
segundos y en la rutina se escriben con `duracion_s`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from ..dominio.feedback.motor.skill import Skill, directorio_skills, skill_desde_dict

from ..dominio.conteo.segmentador import Segmentador, segmentador_desde_dict
from .umbrales import UMBRALES, con_umbrales_de_referencia


class RutinaInvalida(ValueError):
    pass


@dataclass(frozen=True)
class Ejercicio:
    skill: Skill
    segmentacion: Optional[Mapping[str, Any]]
    referencia: Optional[Mapping[str, Any]] = None
    #: con qué umbrales se cargó el skill (`aplicacion/umbrales.py`)
    umbrales: str = "absolutos"
    #: frase corta para la usuaria (campo opcional `descripcion` del skill)
    descripcion: Optional[str] = None

    @property
    def soportado(self) -> bool:
        return self.segmentacion is not None

    @property
    def unidad(self) -> str:
        """En qué se cuenta el objetivo: «repeticiones» o «segundos»."""
        tipo = (self.segmentacion or {}).get("tipo")
        return "segundos" if tipo == "isometrico" else "repeticiones"

    def nuevo_segmentador(self) -> Segmentador:
        if self.segmentacion is None:
            raise RutinaInvalida(
                f"'{self.skill.skill_id}' no tiene sección 'segmentacion' en su "
                "skill: no se puede contar ni segmentar en sesión.")
        return segmentador_desde_dict(self.segmentacion, tuple(self.skill.fases))


def cargar_catalogo(directorio: Optional[Union[str, Path]] = None,
                    umbrales: str = "absolutos") -> Dict[str, Ejercicio]:
    """`umbrales="referencia"`: las reglas con `relativa` se miden contra la
    referencia del ejercicio (ADR-004 §2.2, EXP-006)."""
    if umbrales not in UMBRALES:
        raise RutinaInvalida(f"umbrales desconocidos: {umbrales}")
    directorio = Path(directorio or directorio_skills())
    catalogo: Dict[str, Ejercicio] = {}
    for nombre in sorted(os.listdir(directorio)):
        if not nombre.endswith(".json"):
            continue
        with open(directorio / nombre, encoding="utf-8") as f:
            d = json.load(f)
        referencia = None
        ruta_referencia = directorio / "referencias" / d["skill_id"] / "referencia.json"
        if ruta_referencia.is_file():
            with open(ruta_referencia, encoding="utf-8") as ref:
                referencia = json.load(ref)
        skill = skill_desde_dict(d)
        if umbrales == "referencia":
            skill = con_umbrales_de_referencia(skill, referencia)
        ej = Ejercicio(skill, d.get("segmentacion"), referencia, umbrales,
                       d.get("descripcion"))
        if ej.soportado:
            ej.nuevo_segmentador()            # valida la configuración ya
        catalogo[ej.skill.skill_id] = ej
    return catalogo


@dataclass(frozen=True)
class PasoRutina:
    skill_id: str
    #: objetivo del paso, en la unidad del ejercicio (`Ejercicio.unidad`):
    #: repeticiones, o segundos si es un ejercicio isométrico
    repeticiones: int


@dataclass(frozen=True)
class Rutina:
    nombre: str
    pasos: Tuple[PasoRutina, ...]


def rutina_desde_dict(d: Mapping[str, Any],
                      catalogo: Mapping[str, Ejercicio]) -> Rutina:
    pasos: List[PasoRutina] = []
    for p in d.get("pasos", []):
        sid = p.get("skill_id")
        if sid not in catalogo:
            raise RutinaInvalida(f"ejercicio desconocido en la rutina: {sid}")
        if not catalogo[sid].soportado:
            raise RutinaInvalida(
                f"'{sid}' no está soportado en sesión (sin 'segmentacion').")
        clave = "duracion_s" if catalogo[sid].unidad == "segundos" else "repeticiones"
        reps = int(p.get(clave, 10))
        if reps <= 0:
            raise RutinaInvalida(f"{clave} debe ser positivo en '{sid}'")
        pasos.append(PasoRutina(sid, reps))
    if not pasos:
        raise RutinaInvalida("la rutina no tiene pasos")
    return Rutina(d.get("nombre", "Rutina"), tuple(pasos))


def cargar_rutina(ruta: Union[str, Path],
                  catalogo: Mapping[str, Ejercicio]) -> Rutina:
    with open(ruta, encoding="utf-8") as f:
        return rutina_desde_dict(json.load(f), catalogo)


def rutina_de_un_ejercicio(skill_id: str, repeticiones: int,
                           catalogo: Mapping[str, Ejercicio]) -> Rutina:
    """`repeticiones` va en la unidad del ejercicio (segundos si es isométrico)."""
    ej = catalogo.get(skill_id)
    clave = "duracion_s" if ej is not None and ej.unidad == "segundos" else "repeticiones"
    return rutina_desde_dict(
        {"nombre": skill_id,
         "pasos": [{"skill_id": skill_id, clave: repeticiones}]},
        catalogo)


__all__ = ["Ejercicio", "PasoRutina", "Rutina", "RutinaInvalida",
           "cargar_catalogo", "cargar_rutina", "rutina_desde_dict",
           "rutina_de_un_ejercicio"]
