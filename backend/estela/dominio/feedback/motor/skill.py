"""Carga y validación de archivos de `skill`.

Un `skill` es el archivo externo que define todo lo que el sistema sabe de un
ejercicio: qué medidas necesita, qué cuenta como error, con qué prioridad y
cuándo callar. Añadir un ejercicio es añadir un archivo; no se toca el motor.

El esquema está documentado en `estela/dominio/feedback/skills/ESQUEMA.md`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..contrato import Direccion, Lado, Plano, SEGMENTOS

OPERADORES = (">", ">=", "<", "<=", "fuera_de", "dentro_de")
TIPOS_MEDIDA = ("angulo", "desviacion", "distancia", "agregado", "asimetria")
FUNCIONES_AGREGADO = ("min", "max", "rango", "media")
#: `fn` de una `desviacion`: vacío = el frame actual; `mediana` = mediana de
#: los frames de la repetición en curso en que la regla aplica.
FUNCIONES_DESVIACION = ("", "mediana")
#: Extremo de la referencia con que se compara un agregado `max` o `min`.
EXTREMOS = ("max", "min")
#: Sentido en que debe moverse el *valor de la medida* para volver al rango.
SENTIDOS = ("aumentar", "disminuir")
#: `descartado` = fuera del conjunto de ejercicios (ADR-005); vive en `retirados/`.
ESTADOS = ("candidato", "candidato_en_duda", "adoptado", "descartado")
#: Sufijos de lado en los nombres de medida, y su lado en el contrato.
SUFIJOS_LADO = {"_izq": Lado.IZQUIERDO, "_der": Lado.DERECHO}


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
        if self.tipo == "desviacion" and self.fn:
            return f"{self.fn}(desviacion:{self.nombre})@repeticion"
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
    #: Forma relativa (ADR-004 §2.2): el umbral es `k × max(σ_ref, ruido)`, en
    #: las unidades de la medida. Sin `extremo` se calcula en cada frame con el
    #: σ del instante alineado (`con_escala`, medidas `desviacion`). Con
    #: `extremo` se resuelve una vez contra el máximo o el mínimo de la
    #: referencia (`aplicacion/umbrales.py`).
    k: Optional[float] = None
    ruido: float = 0.0
    extremo: Optional[str] = None

    @property
    def relativa(self) -> bool:
        return self.k is not None

    def con_escala(self, escala: float) -> "Condicion":
        """La condición concreta de una desviación cuya escala es
        `max(σ_ref, ruido)`: `>` → +k·escala, `<` → −k·escala y `fuera_de` →
        fuera de ±k·escala."""
        limite = self.k * escala
        if self.op == "fuera_de":
            return Condicion(op="fuera_de", min=-limite, max=limite)
        signo = 1.0 if self.op in (">", ">=") else -1.0
        return Condicion(op=self.op, umbral=signo * limite)

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

    def sentido(self, valor: float) -> Optional[str]:
        """Hacia dónde debe moverse el valor para dejar de cumplir la condición.

        `>` -> «disminuir», `<` -> «aumentar»; `fuera_de` depende del lado por
        el que se sale. `dentro_de` no tiene sentido único: None.
        """
        if self.op in (">", ">="):
            return "disminuir"
        if self.op in ("<", "<="):
            return "aumentar"
        if self.op == "fuera_de":
            if valor < self.min:
                return "aumentar"
            if valor > self.max:
                return "disminuir"
        return None


@dataclass(frozen=True)
class FormaRelativa:
    """La regla medida contra la referencia (ADR-004 §2.1, EXP-006).

    Solo se usa con umbrales «referencia» (`aplicacion/umbrales.py`): pasa a
    ser la forma principal de la regla y la absoluta queda de respaldo.
    """
    medida: Medida
    condicion: Condicion
    umbral_origen: str = "[?] provisional, sin calibrar"
    #: vacío = la misma severidad que la forma absoluta (mismas unidades)
    umbrales_severidad: Dict[str, float] = field(default_factory=dict)


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
    #: traducción del sentido de la medida a dirección de movimiento
    #: (ADR-004 §2.5), p. ej. {"disminuir": MAS_FLEXION} para un ángulo de
    #: rodilla. Vacío => el error sale sin `direccion`.
    direcciones: Dict[str, Direccion] = field(default_factory=dict)
    #: la regla solo se aplica si su lado es el que mejor ve la cámara
    #: (catálogo v2, DEC-013): en los ejercicios de perfil la pierna lejana
    #: queda tapada y no se evalúa, ni cuenta como abstención.
    solo_lado_visible: bool = False
    #: si alguna de estas reglas se disparó en la repetición en curso, esta
    #: calla el resto de la repetición (precedencia entre errores).
    silenciada_por: Sequence[str] = ()
    #: forma relativa a la referencia, sin usar con umbrales «absolutos»
    relativa: Optional[FormaRelativa] = None
    #: medida y condición absolutas que se evalúan en los frames en que la
    #: forma principal necesita la referencia y no la hay (sin DTW, coste alto)
    respaldo: Optional[Tuple[Medida, Condicion]] = None

    def medida_espejo(self) -> Optional[str]:
        """La misma medida del otro lado: `rodilla_izq` <-> `rodilla_der`."""
        nombre = self.medida.nombre
        for suf, otro in (("_izq", "_der"), ("_der", "_izq")):
            if nombre.endswith(suf):
                return nombre[: -len(suf)] + otro
        return None

    def direccion_de(self, valor: float,
                     condicion: Optional[Condicion] = None) -> Optional[Direccion]:
        """`condicion`: la que se evaluó en este frame (relativa o respaldo)."""
        sentido = (condicion or self.condicion).sentido(valor)
        return self.direcciones.get(sentido) if sentido else None

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
class PoliticaRefuerzo:
    """Política de cuándo elogiar.

    Simétrica a `PoliticaSilencio`: tan importante es no corregir de más
    como no quedarse muda cuando la ejecución va bien. Desactivada por
    defecto (`activa=False`): un skill nuevo no gana este comportamiento
    sin que alguien lo declare explícitamente en su JSON.
    """
    activa: bool = False
    #: repeticiones limpias consecutivas necesarias antes de hablar
    repeticiones_limpias: int = 3
    #: no elogiar más seguido que esto, en milisegundos
    refractario_ms: int = 15000
    #: tope de elogios por sesión, para que no pierda valor por repetirse
    max_emisiones: int = 3


@dataclass(frozen=True)
class Skill:
    skill_id: str
    nombre: str
    version: str
    estado: str
    fases: Sequence[str]
    reglas: Sequence[Regla]
    politica: PoliticaSilencio
    politica_refuerzo: PoliticaRefuerzo = field(default_factory=PoliticaRefuerzo)
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
    if tipo == "desviacion" and d.get("fn", "") not in FUNCIONES_DESVIACION:
        raise SkillInvalido(f"una desviacion solo admite fn 'mediana': {d.get('fn')}")
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
    if d.get("k") is not None:
        k, extremo = float(d["k"]), d.get("extremo")
        if k <= 0 or op == "dentro_de":
            raise SkillInvalido(f"forma relativa no válida: k={k} con '{op}'")
        if extremo is not None and (extremo not in EXTREMOS or op == "fuera_de"):
            raise SkillInvalido(f"extremo '{extremo}' no válido con '{op}'")
        return Condicion(op=op, k=k, ruido=float(d.get("ruido", 0.0)), extremo=extremo)
    if op in ("fuera_de", "dentro_de"):
        if d.get("min") is None or d.get("max") is None:
            raise SkillInvalido(f"'{op}' requiere 'min' y 'max'")
        return Condicion(op=op, min=float(d["min"]), max=float(d["max"]))
    if d.get("umbral") is None:
        raise SkillInvalido(f"'{op}' requiere 'umbral'")
    return Condicion(op=op, umbral=float(d["umbral"]))


def _direcciones_desde(d: Dict[str, Any]) -> Dict[str, Direccion]:
    direcciones: Dict[str, Direccion] = {}
    for sentido, valor in d.items():
        if sentido not in SENTIDOS:
            raise SkillInvalido(f"sentido de direccion desconocido: {sentido}")
        try:
            direcciones[sentido] = Direccion(valor)
        except ValueError:
            raise SkillInvalido(f"direccion fuera del vocabulario cerrado: {valor}")
    return direcciones


def _regla_desde(d: Dict[str, Any]) -> Regla:
    regla = _regla_sin_validar(d)
    if regla.solo_lado_visible:
        sufijo = next((s for s in SUFIJOS_LADO if regla.medida.nombre.endswith(s)), None)
        if regla.medida.tipo not in ("angulo", "distancia", "agregado") or sufijo is None:
            raise SkillInvalido(
                f"{regla.error_id}: solo_lado_visible necesita una medida de un "
                f"lado (nombre terminado en _izq o _der)")
        if SUFIJOS_LADO[sufijo] != regla.lado:
            raise SkillInvalido(
                f"{regla.error_id}: el lado de la regla no coincide con el de "
                f"su medida ({regla.medida.nombre})")
    return regla


def _comprueba_forma(error_id: str, medida: Medida, condicion: Condicion,
                     en_relativa: bool) -> None:
    """Una condición con `k` compara una `desviacion` frame a frame o, con
    `extremo` (solo dentro de `relativa`), un agregado `max`/`min` con el
    extremo de la referencia."""
    if condicion.extremo is not None:
        if not en_relativa:
            raise SkillInvalido(f"{error_id}: 'extremo' solo va dentro de 'relativa'")
        if medida.tipo != "agregado" or medida.fn not in EXTREMOS:
            raise SkillInvalido(
                f"{error_id}: el extremo de la referencia se compara con un "
                f"agregado max o min")
    elif condicion.relativa and medida.tipo != "desviacion":
        raise SkillInvalido(f"{error_id}: una condición con 'k' necesita una 'desviacion'")


def _forma_relativa_desde(d: Dict[str, Any], absoluta: Medida,
                          error_id: str) -> FormaRelativa:
    if "condicion" not in d:
        raise SkillInvalido(f"{error_id}: 'relativa' requiere 'condicion'")
    medida = _medida_desde(d["medida"]) if "medida" in d else absoluta
    condicion = _condicion_desde(d["condicion"])
    if not condicion.relativa:
        raise SkillInvalido(f"{error_id}: la condición de 'relativa' necesita 'k'")
    _comprueba_forma(error_id, medida, condicion, en_relativa=True)
    return FormaRelativa(
        medida=medida, condicion=condicion,
        umbral_origen=d.get("umbral_origen", "[?] provisional, sin calibrar"),
        umbrales_severidad=dict(d.get("severidad", {})),
    )


def _regla_sin_validar(d: Dict[str, Any]) -> Regla:
    for campo in ("error_id", "medida", "condicion", "segmento", "lado",
                  "plano", "prioridad"):
        if campo not in d:
            raise SkillInvalido(f"regla sin campo obligatorio '{campo}'")
    if d["segmento"] not in SEGMENTOS:
        raise SkillInvalido(
            f"segmento '{d['segmento']}' fuera del vocabulario cerrado")
    medida, condicion = _medida_desde(d["medida"]), _condicion_desde(d["condicion"])
    _comprueba_forma(d["error_id"], medida, condicion, en_relativa=False)
    return Regla(
        error_id=d["error_id"],
        descripcion=d.get("descripcion", ""),
        medida=medida,
        condicion=condicion,
        segmento=d["segmento"],
        lado=Lado(d["lado"]),
        plano=Plano(d["plano"]),
        prioridad=int(d["prioridad"]),
        fases=tuple(d.get("fases", ())),
        umbrales_severidad=dict(d.get("severidad", {})),
        umbral_origen=d.get("umbral_origen", "[?] provisional, sin calibrar"),
        mensaje_id=d.get("mensaje_id", d["error_id"]),
        direcciones=_direcciones_desde(d.get("direccion", {})),
        solo_lado_visible=bool(d.get("solo_lado_visible", False)),
        silenciada_por=tuple(d.get("silenciada_por", ())),
        relativa=(_forma_relativa_desde(d["relativa"], medida, d["error_id"])
                  if "relativa" in d else None),
    )


def skill_desde_dict(d: Dict[str, Any]) -> Skill:
    for campo in ("skill_id", "nombre", "version", "reglas"):
        if campo not in d:
            raise SkillInvalido(f"skill sin campo obligatorio '{campo}'")
    reglas = [_regla_desde(r) for r in d["reglas"]]
    ids = [r.error_id for r in reglas]
    if len(ids) != len(set(ids)):
        raise SkillInvalido("error_id duplicado dentro del skill")
    for r in reglas:
        for otra in r.silenciada_por:
            if otra not in ids or otra == r.error_id:
                raise SkillInvalido(
                    f"{r.error_id}: silenciada_por '{otra}' no es otra regla del skill")
    estado = d.get("estado", "candidato")
    if estado not in ESTADOS:
        raise SkillInvalido(f"estado desconocido: {estado}")
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
    pr = d.get("politica_refuerzo", {})
    politica_refuerzo = PoliticaRefuerzo(
        activa=bool(pr.get("activa", False)),
        repeticiones_limpias=int(pr.get("repeticiones_limpias", 3)),
        refractario_ms=int(pr.get("refractario_ms", 15000)),
        max_emisiones=int(pr.get("max_emisiones", 3)),
    )
    return Skill(
        skill_id=d["skill_id"],
        nombre=d["nombre"],
        version=d["version"],
        estado=estado,
        fases=tuple(d.get("fases", ())),
        reglas=tuple(reglas),
        politica=politica,
        politica_refuerzo=politica_refuerzo,
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
    "Skill", "Regla", "Medida", "Condicion", "FormaRelativa", "PoliticaSilencio",
    "PoliticaRefuerzo", "SkillInvalido", "cargar_skill", "cargar_skills",
    "skill_desde_dict", "directorio_skills",
]
