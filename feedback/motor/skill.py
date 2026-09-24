"""Carga y validación de archivos de `skill`.

Un `skill` es el archivo externo que define todo lo que el sistema sabe de un
ejercicio: qué medidas necesita, qué cuenta como error, con qué prioridad y
cuándo callar. Añadir un ejercicio es añadir un archivo; no se toca el motor
(CLAUDE.md §5).

El esquema está documentado en `feedback/skills/ESQUEMA.md`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from ..contrato import Lado, Plano, SEGMENTOS

OPERADORES = (">", ">=", "<", "<=", "fuera_de", "dentro_de")
TIPOS_MEDIDA = ("angulo", "desviacion", "distancia", "agregado", "asimetria")
FUNCIONES_AGREGADO = ("min", "max", "rango", "media")


class SkillInvalido(ValueError):
    """El archivo de skill no cumple el esquema."""


@dataclass(frozen=True)
class Medida:
    tipo: str
    nombre: str = ""
    nombres: Sequence[str] = ()
    fn: str = ""
    ventana: str = "repeticion"

    def clave(self) -> str:
        if self.tipo == "agregado":
            return f"{self.fn}({self.nombre})@{self.ventana}"
        if self.tipo == "asimetria":
            return f"asimetria({','.join(self.nombres)})"
        return f"{self.tipo}:{self.nombre}"

    def angulos_implicados(self) -> Sequence[str]:
        if self.tipo == "asimetria":
            return tuple(self.nombres)
        return (self.nombre,) if self.nombre else ()


@dataclass(frozen=True)
class Condicion:
    op: str
    umbral: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None

    def evalua(self, valor: float) -> bool:
        if self.op == ">":
            return valor > self.umbral
        if self.op == ">=":
            return valor >= self.umbral
        if self.op == "<":
            return valor < self.umbral
        if self.op == "<=":
            return valor <= self.umbral
        if self.op == "fuera_de":
            return valor < self.min or valor > self.max
        if self.op == "dentro_de":
            return self.min <= valor <= self.max
        raise SkillInvalido(f"operador desconocido: {self.op}")

    def exceso(self, valor: float) -> float:
        """Cuánto se rebasa el umbral. Alimenta la severidad."""
        if self.op in (">", ">="):
            return max(0.0, valor - float(self.umbral))
        if self.op in ("<", "<="):
            return max(0.0, float(self.umbral) - valor)
        if self.op == "fuera_de":
            if valor < self.min:
                return self.min - valor
            if valor > self.max:
                return valor - self.max
            return 0.0
        if self.op == "dentro_de":
            return 0.0
        return 0.0


@dataclass(frozen=True)
class Regla:
    error_id: str
    descripcion: str
    medida: Medida
    condicion: Condicion
    segmento: str
    lado: Lado
    plano: Plano
    prioridad: int          # 1 = más importante
    fases: Sequence[str] = ()   # vacío = cualquier fase
    umbrales_severidad: Dict[str, float] = field(default_factory=dict)
    umbral_origen: str = "[?] provisional, sin calibrar"
    mensaje_id: str = ""

    def severidad_de(self, exceso: float) -> str:
        alta = self.umbrales_severidad.get("alta")
        moderada = self.umbrales_severidad.get("moderada")
        if alta is not None and exceso >= alta:
            return "alta"
        if moderada is not None and exceso >= moderada:
            return "moderada"
        return "leve"


@dataclass(frozen=True)
class PoliticaSilencio:
    """Política de cuándo hablar y cuándo callar.

    Los cuatro mecanismos tienen respaldo en la literatura de aprendizaje
    motor y en los modos de fallo documentados en ADR-001:

    - `refractario_ms` y `refractario_mismo_error_ms`: evitan el feedback
      permanente, que `[F]` induce dependencia del feedback (Sigrist et al.,
      2013; hipótesis de la guía).
    - `repeticiones_evidencia`: un error debe observarse en N repeticiones
      consecutivas antes de hablar. Es *bandwidth feedback* aplicado en el eje
      temporal, y es lo que evita corregir por un frame ruidoso.
    - `desvanecimiento`: cada vez que se emite el mismo error, su periodo
      refractario se multiplica por `factor_desvanecimiento`. `[F]` Sigrist
      recomienda que la frecuencia baje con el nivel de habilidad; `[?]` la
      tasa óptima de desvanecimiento es desconocida en la literatura, así que
      el factor es un parámetro a calibrar, no una constante justificada.
    - `fases_silenciadas`: no se habla mientras la usuaria está bajo esfuerzo.
    """
    refractario_ms: int = 4000
    refractario_mismo_error_ms: int = 12000
    repeticiones_evidencia: int = 2
    factor_desvanecimiento: float = 1.5
    max_emisiones_mismo_error: int = 4
    fases_silenciadas: Sequence[str] = ()
    confianza_minima: float = 0.6
    #: Tolerancia de orientación: cuánto puede desviarse el sujeto del plano
    #: ideal de una regla antes de que la regla se considere no observable.
    #: El valor por defecto proviene de EXP-002.
    tolerancia_orientacion_grados: float = 30.0


@dataclass(frozen=True)
class Skill:
    skill_id: str
    nombre: str
    version: str
    estado: str
    fases: Sequence[str]
    reglas: Sequence[Regla]
    politica: PoliticaSilencio
    angulos_requeridos: Sequence[str] = ()
    orientacion_preferida: Plano = Plano.CUALQUIERA
    notas: str = ""

    def regla_de(self, error_id: str) -> Optional[Regla]:
        for r in self.reglas:
            if r.error_id == error_id:
                return r
        return None


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

def _medida_desde(d: Dict[str, Any]) -> Medida:
    tipo = d.get("tipo")
    if tipo not in TIPOS_MEDIDA:
        raise SkillInvalido(f"tipo de medida desconocido: {tipo}")
    if tipo == "agregado" and d.get("fn") not in FUNCIONES_AGREGADO:
        raise SkillInvalido(f"funcion de agregado desconocida: {d.get('fn')}")
    if tipo == "asimetria":
        nombres = tuple(d.get("nombres", ()))
        if len(nombres) != 2:
            raise SkillInvalido("asimetria requiere exactamente 2 nombres")
        return Medida(tipo=tipo, nombres=nombres)
    if not d.get("nombre"):
        raise SkillInvalido(f"medida de tipo {tipo} requiere 'nombre'")
    return Medida(
        tipo=tipo,
        nombre=d["nombre"],
        fn=d.get("fn", ""),
        ventana=d.get("ventana", "repeticion"),
    )


def _condicion_desde(d: Dict[str, Any]) -> Condicion:
    op = d.get("op")
    if op not in OPERADORES:
        raise SkillInvalido(f"operador desconocido: {op}")
    if op in ("fuera_de", "dentro_de"):
        if d.get("min") is None or d.get("max") is None:
            raise SkillInvalido(f"'{op}' requiere 'min' y 'max'")
        return Condicion(op=op, min=float(d["min"]), max=float(d["max"]))
    if d.get("umbral") is None:
        raise SkillInvalido(f"'{op}' requiere 'umbral'")
    return Condicion(op=op, umbral=float(d["umbral"]))


def _regla_desde(d: Dict[str, Any]) -> Regla:
    for campo in ("error_id", "medida", "condicion", "segmento", "lado",
                  "plano", "prioridad"):
        if campo not in d:
            raise SkillInvalido(f"regla sin campo obligatorio '{campo}'")
    if d["segmento"] not in SEGMENTOS:
        raise SkillInvalido(
            f"segmento '{d['segmento']}' fuera del vocabulario cerrado")
    return Regla(
        error_id=d["error_id"],
        descripcion=d.get("descripcion", ""),
        medida=_medida_desde(d["medida"]),
        condicion=_condicion_desde(d["condicion"]),
        segmento=d["segmento"],
        lado=Lado(d["lado"]),
        plano=Plano(d["plano"]),
        prioridad=int(d["prioridad"]),
        fases=tuple(d.get("fases", ())),
        umbrales_severidad=dict(d.get("severidad", {})),
        umbral_origen=d.get("umbral_origen", "[?] provisional, sin calibrar"),
        mensaje_id=d.get("mensaje_id", d["error_id"]),
    )


def skill_desde_dict(d: Dict[str, Any]) -> Skill:
    for campo in ("skill_id", "nombre", "version", "reglas"):
        if campo not in d:
            raise SkillInvalido(f"skill sin campo obligatorio '{campo}'")
    reglas = [_regla_desde(r) for r in d["reglas"]]
    ids = [r.error_id for r in reglas]
    if len(ids) != len(set(ids)):
        raise SkillInvalido("error_id duplicado dentro del skill")
    prioridades = [r.prioridad for r in reglas]
    if len(prioridades) != len(set(prioridades)):
        raise SkillInvalido(
            "prioridades duplicadas: el desempate quedaría indefinido y el "
            "motor dejaría de ser determinista")
    pol = d.get("politica_silencio", {})
    politica = PoliticaSilencio(
        refractario_ms=int(pol.get("refractario_ms", 4000)),
        refractario_mismo_error_ms=int(pol.get("refractario_mismo_error_ms", 12000)),
        repeticiones_evidencia=int(pol.get("repeticiones_evidencia", 2)),
        factor_desvanecimiento=float(pol.get("factor_desvanecimiento", 1.5)),
        max_emisiones_mismo_error=int(pol.get("max_emisiones_mismo_error", 4)),
        fases_silenciadas=tuple(pol.get("fases_silenciadas", ())),
        confianza_minima=float(pol.get("confianza_minima", 0.6)),
        tolerancia_orientacion_grados=float(
            pol.get("tolerancia_orientacion_grados", 30.0)),
    )
    return Skill(
        skill_id=d["skill_id"],
        nombre=d["nombre"],
        version=d["version"],
        estado=d.get("estado", "candidato"),
        fases=tuple(d.get("fases", ())),
        reglas=tuple(reglas),
        politica=politica,
        angulos_requeridos=tuple(d.get("angulos_requeridos", ())),
        orientacion_preferida=Plano(d.get("orientacion_preferida", "cualquiera")),
        notas=d.get("notas", ""),
    )


def cargar_skill(ruta: str) -> Skill:
    with open(ruta, "r", encoding="utf-8") as f:
        return skill_desde_dict(json.load(f))


def cargar_skills(directorio: str) -> Dict[str, Skill]:
    """Carga todos los `*.json` de un directorio. Falla ruidosamente."""
    skills: Dict[str, Skill] = {}
    for nombre in sorted(os.listdir(directorio)):
        if not nombre.endswith(".json"):
            continue
        skill = cargar_skill(os.path.join(directorio, nombre))
        if skill.skill_id in skills:
            raise SkillInvalido(f"skill_id duplicado: {skill.skill_id}")
        skills[skill.skill_id] = skill
    return skills


def directorio_skills() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "skills")


__all__ = [
    "Skill", "Regla", "Medida", "Condicion", "PoliticaSilencio",
    "SkillInvalido", "cargar_skill", "cargar_skills", "skill_desde_dict",
    "directorio_skills",
]
