"""Catálogo de ejercicios y rutina de calentamiento.

El catálogo son los skills de `feedback/skills/` más su sección opcional
`segmentacion`. Un skill sin `segmentacion` se carga (el motor lo acepta) pero
no se puede usar en sesión: hoy es el caso de `rotacion_tronco`, que no es
observable con una cámara (EXP-002, IC-001).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from feedback.motor.skill import Skill, directorio_skills, skill_desde_dict

from ..conteo.segmentador import Segmentador, segmentador_desde_dict


class RutinaInvalida(ValueError):
    pass


@dataclass(frozen=True)
class Ejercicio:
    skill: Skill
    segmentacion: Optional[Mapping[str, Any]]

    @property
    def soportado(self) -> bool:
        return self.segmentacion is not None

    def nuevo_segmentador(self) -> Segmentador:
        if self.segmentacion is None:
            raise RutinaInvalida(
                f"'{self.skill.skill_id}' no tiene sección 'segmentacion' en su "
                "skill: no se puede contar ni segmentar en sesión.")
        return segmentador_desde_dict(self.segmentacion, tuple(self.skill.fases))


def cargar_catalogo(directorio: Optional[Union[str, Path]] = None
                    ) -> Dict[str, Ejercicio]:
    directorio = Path(directorio or directorio_skills())
    catalogo: Dict[str, Ejercicio] = {}
    for nombre in sorted(os.listdir(directorio)):
        if not nombre.endswith(".json"):
            continue
        with open(directorio / nombre, encoding="utf-8") as f:
            d = json.load(f)
        ej = Ejercicio(skill_desde_dict(d), d.get("segmentacion"))
        if ej.soportado:
            ej.nuevo_segmentador()            # valida la configuración ya
        catalogo[ej.skill.skill_id] = ej
    return catalogo


@dataclass(frozen=True)
class PasoRutina:
    skill_id: str
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
        reps = int(p.get("repeticiones", 10))
        if reps <= 0:
            raise RutinaInvalida(f"repeticiones debe ser positivo en '{sid}'")
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
    return rutina_desde_dict(
        {"nombre": skill_id,
         "pasos": [{"skill_id": skill_id, "repeticiones": repeticiones}]},
        catalogo)


__all__ = ["Ejercicio", "PasoRutina", "Rutina", "RutinaInvalida",
           "cargar_catalogo", "cargar_rutina", "rutina_desde_dict",
           "rutina_de_un_ejercicio"]
