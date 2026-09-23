"""Generador de un banco **sintético** de episodios.

Qué es y qué no es
------------------

`[R]` Este banco existe para poder medir el módulo de retroalimentación
**antes** de que exista una sola grabación. Genera directamente las *medidas*
que el motor consume (ángulos, distancias, desviaciones y confianza) a partir
de los umbrales declarados en cada `skill`.

**No simula biomecánica humana.** Un episodio «con valgo de rodilla» de este
banco no es un valgo real: es un valor numérico colocado al otro lado del
umbral. Por lo tanto:

  - **Sí** mide: determinismo, tasa de sobrecorrección, latencia, política de
    silencio, abstención por confianza y por plano, y coherencia entre el
    error inducido y el error señalado.
  - **No** mide: si los umbrales son correctos, si el error se parece a lo que
    hace una persona real, ni la exactitud de contenido (M1) del ADR-001.

`[F]` La M1 real de EXP-001 exige el banco grabado de 60–100 episodios con
etiquetado manual descrito en ADR-001 §5. Este generador no lo sustituye: lo
precede, y sirve para llegar a esa grabación con el motor ya depurado.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

sys.path.insert(0, __file__.rsplit("/", 2)[0])

from feedback.contrato import Observacion
from feedback.motor.decision import _PLANO_IDEAL_GRADOS
from feedback.motor.skill import Regla, Skill

#: Duración nominal de una repetición, en milisegundos. `[?]` Valor de trabajo:
#: la duración real de cada ejercicio hay que medirla en las grabaciones.
MS_POR_REPETICION = 3000
FRAMES_POR_REPETICION = 6
REPETICIONES = 8

#: Factores de exceso sobre el umbral, por severidad inducida.
FACTOR_SEVERIDAD = {"leve": 0.4, "moderada": 1.2, "alta": 2.5}


@dataclass
class Episodio:
    episodio_id: str
    ejercicio_id: str
    #: `error_id` inducido, o None para una ejecución correcta
    error_referencia: Optional[str]
    severidad_referencia: Optional[str]
    condicion: str            # "error" | "correcto" | "ocluido" | "plano_malo"
    observaciones: List[Observacion] = field(default_factory=list)
    #: qué se espera del sistema en esta condición
    espera_mensaje: bool = True


# ---------------------------------------------------------------------------
# Valores objetivo
# ---------------------------------------------------------------------------

def _margen(regla: Regla) -> float:
    """Escala de referencia del umbral, para desplazarlo de forma sensata."""
    c = regla.condicion
    base = c.umbral if c.umbral is not None else (c.max or 1.0)
    return max(abs(base) * 0.15, 0.02)


def valor_objetivo(regla: Regla, violar: bool, severidad: str = "moderada") -> float:
    """Valor de la medida que viola (o no) la condición de la regla."""
    c = regla.condicion
    d = _margen(regla) * (FACTOR_SEVERIDAD[severidad] if violar else 1.0)
    # Ajuste: el exceso debe superar los umbrales de severidad declarados.
    if violar and regla.umbrales_severidad:
        objetivo = regla.umbrales_severidad.get(
            severidad, min(regla.umbrales_severidad.values()))
        if severidad == "leve":
            d = max(d, objetivo * 0.4) if objetivo else d
        else:
            d = max(d, objetivo * 1.1)
    if c.op in (">", ">="):
        return c.umbral + d if violar else c.umbral - d
    if c.op in ("<", "<="):
        return c.umbral - d if violar else c.umbral + d
    if c.op == "fuera_de":
        return c.max + d if violar else (c.min + c.max) / 2.0
    if c.op == "dentro_de":
        return (c.min + c.max) / 2.0 if violar else c.max + d
    raise ValueError(regla.condicion.op)


# ---------------------------------------------------------------------------
# Escritura de una medida en una observación
# ---------------------------------------------------------------------------

def _escribe(angulos: Dict[str, float], distancias: Dict[str, float],
             desviaciones: Dict[str, float], confianza: Dict[str, float],
             regla: Regla, valor: float, indice_frame: int,
             conf: float) -> None:
    m = regla.medida
    if m.tipo == "angulo":
        angulos[m.nombre] = valor
        confianza[m.nombre] = conf
    elif m.tipo == "distancia":
        distancias[m.nombre] = valor
        confianza[m.nombre] = conf
    elif m.tipo == "desviacion":
        desviaciones[m.nombre] = valor
        confianza[m.nombre] = conf
    elif m.tipo == "agregado":
        # Valor constante a lo largo de la repetición: así `min`, `max` y
        # `media` valen lo previsto en *cualquier* frame, y el resultado no
        # depende de en qué frame caiga la fase de disparo. `rango` es la
        # excepción: necesita dos valores distintos, y por eso su valor solo
        # es correcto a partir del segundo frame de la repetición.
        if m.fn == "rango":
            v = 0.0 if indice_frame == 0 else valor
        else:
            v = valor
        destino = distancias if m.nombre.startswith(("separacion", "valgo")) else angulos
        destino[m.nombre] = v
        confianza[m.nombre] = conf
    elif m.tipo == "asimetria":
        a, b = m.nombres
        angulos[a] = 90.0
        angulos[b] = 90.0 + valor
        confianza[a] = conf
        confianza[b] = conf


def _fase_disparo(skill: Skill, regla: Regla) -> str:
    if regla.fases:
        return regla.fases[0]
    for f in skill.fases:
        if f not in skill.politica.fases_silenciadas:
            return f
    return "desconocida"


def _fase_acumulacion(skill: Skill, regla: Regla) -> str:
    disparo = _fase_disparo(skill, regla)
    for f in skill.fases:
        if f != disparo:
            return f
    return disparo


def _orientacion_para(regla: Regla) -> Optional[float]:
    return _PLANO_IDEAL_GRADOS.get(regla.plano)


# ---------------------------------------------------------------------------
# Construcción de episodios
# ---------------------------------------------------------------------------

def construir_episodio(skill: Skill, objetivo: Optional[Regla],
                       condicion: str, severidad: str = "moderada",
                       repeticiones: int = REPETICIONES) -> Episodio:
    """Construye un episodio completo.

    - `objetivo=None` -> ejecución correcta: **ninguna** regla se viola.
    - `condicion="ocluido"` -> el error está presente pero la confianza de su
      medida es baja: el sistema debe callar.
    - `condicion="plano_malo"` -> el error está presente pero el sujeto está
      orientado en el plano equivocado: el sistema debe callar.
    """
    conf_objetivo = 0.25 if condicion == "ocluido" else 1.0
    orientacion = None
    if objetivo is not None:
        if condicion == "plano_malo":
            ideal = _orientacion_para(objetivo)
            orientacion = None if ideal is None else (90.0 - ideal)
        else:
            orientacion = _orientacion_para(objetivo)

    observaciones: List[Observacion] = []
    t = 0
    for rep in range(1, repeticiones + 1):
        for i in range(FRAMES_POR_REPETICION):
            angulos: Dict[str, float] = {}
            distancias: Dict[str, float] = {}
            desviaciones: Dict[str, float] = {}
            confianza: Dict[str, float] = {}

            # Todas las reglas en valor seguro...
            for regla in skill.reglas:
                _escribe(angulos, distancias, desviaciones, confianza,
                         regla, valor_objetivo(regla, violar=False), i, 1.0)
            # ...salvo la que se induce.
            if objetivo is not None:
                _escribe(angulos, distancias, desviaciones, confianza,
                         objetivo, valor_objetivo(objetivo, True, severidad),
                         i, conf_objetivo)

            ultimo = i == FRAMES_POR_REPETICION - 1
            if objetivo is not None:
                fase = (_fase_disparo(skill, objetivo) if ultimo
                        else _fase_acumulacion(skill, objetivo))
            elif i == 0:
                # El primer frame de cada repetición usa una fase que ninguna
                # regla declara: es el frame en el que los agregados de tipo
                # `rango` todavía no tienen sentido.
                fase = "_inicio"
            else:
                fase = (skill.fases[(i - 1) % len(skill.fases)]
                        if skill.fases else "x")

            observaciones.append(Observacion(
                t_ms=t, ejercicio_id=skill.skill_id, angulos=angulos,
                confianza=confianza, fase=fase, repeticion=rep,
                desviaciones=desviaciones, distancias=distancias,
                orientacion=orientacion))
            t += MS_POR_REPETICION // FRAMES_POR_REPETICION

    espera = condicion == "error"
    return Episodio(
        episodio_id=f"{skill.skill_id}|{objetivo.error_id if objetivo else 'correcto'}|{condicion}|{severidad if objetivo else '-'}",
        ejercicio_id=skill.skill_id,
        error_referencia=objetivo.error_id if objetivo else None,
        severidad_referencia=severidad if objetivo else None,
        condicion=condicion,
        observaciones=observaciones,
        espera_mensaje=espera,
    )


def generar_banco(skills: Dict[str, Skill]) -> List[Episodio]:
    """Banco completo y determinista: no hay aleatoriedad en ningún punto."""
    banco: List[Episodio] = []
    for skill in skills.values():
        for regla in skill.reglas:
            for sev in ("leve", "moderada", "alta"):
                banco.append(construir_episodio(skill, regla, "error", sev))
            banco.append(construir_episodio(skill, regla, "ocluido", "alta"))
            # `plano_malo` solo tiene sentido para reglas con un plano ideal
            # definido. Las reglas del plano TRANSVERSAL quedan fuera a
            # propósito: no existe ninguna orientación de una sola cámara que
            # las haga observables, así que la salvaguarda no puede protegerlas.
            # Es una limitación documentada, no un caso que falte por generar.
            if regla.plano.value in ("frontal", "sagital"):
                banco.append(construir_episodio(skill, regla, "plano_malo", "alta"))
        # Ejecuciones correctas: `[F]` su inclusión es obligatoria, es lo único
        # que mide la sobrecorrección — el sesgo que hundió a CoachMe (30,4 %).
        for i in range(3):
            ep = construir_episodio(skill, None, "correcto")
            ep.episodio_id = f"{ep.episodio_id}#{i}"
            banco.append(ep)
    return banco


__all__ = ["Episodio", "construir_episodio", "generar_banco", "valor_objetivo",
           "REPETICIONES", "MS_POR_REPETICION", "FRAMES_POR_REPETICION"]
