"""Validador determinista de la salida del verbalizador.

Es la contención del riesgo lingüístico. Ataca directamente dos modos de fallo
documentados:

  `[F]` CoachMe: **17,2 %** de las instrucciones peor valoradas contienen
  identificación errónea de la parte del cuerpo (ADR-001, §2.3).
  `[F]` Human-MME: *todos* los modelos evaluados confunden izquierda y derecha
  en manos y pies (ADR-001, §2.4).

Regla central: un mensaje solo puede nombrar el segmento y el lado que vienen
en el `ErrorTipificado`. Cualquier otro segmento o lado es rechazo inmediato,
sin importar lo bien redactado que esté el mensaje.

El validador se aplica a **todos** los verbalizadores, incluido el de
plantillas. Sobre plantillas nunca debería fallar; si falla, hay un error en
la plantilla y es preferible detectarlo en un test que en una sesión.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

from ..contrato import (
    ErrorTipificado, Lado, SEGMENTOS, VOCABULARIO_PROHIBIDO,
)

#: Formas de superficie en español de cada segmento del vocabulario cerrado.
#: Se comparan sin tildes y en minúsculas.
LEXICO_SEGMENTOS: Dict[str, Tuple[str, ...]] = {
    "rodilla": ("rodilla", "rodillas"),
    "cadera": ("cadera", "caderas", "pelvis"),
    "tronco": ("tronco", "torso", "abdomen", "core"),
    "hombro": ("hombro", "hombros"),
    "codo": ("codo", "codos"),
    "muneca": ("muneca", "munecas"),
    "tobillo": ("tobillo", "tobillos"),
    "pie": ("pie", "pies", "talon", "talones", "planta"),
    "cuello": ("cuello", "nuca", "cervical"),
    "cabeza": ("cabeza", "mirada", "barbilla", "menton"),
    "brazo": ("brazo", "brazos", "antebrazo", "antebrazos"),
    "pierna": ("pierna", "piernas", "muslo", "muslos", "pantorrilla"),
    "espalda": ("espalda", "lumbar", "dorsal", "columna"),
}

LEXICO_LADOS: Dict[Lado, Tuple[str, ...]] = {
    Lado.IZQUIERDO: ("izquierdo", "izquierda", "izquierdos", "izquierdas", "izq"),
    Lado.DERECHO: ("derecho", "derecha", "derechos", "derechas", "der"),
}

#: Longitud máxima del mensaje. `[R]` Un mensaje hablado durante la ejecución
#: debe caber en el hueco entre dos repeticiones. El valor es un parámetro de
#: diseño, no una constante con respaldo experimental: `[?]` calibrar contra la
#: duración real del ciclo de cada ejercicio y el RTF del TTS.
MAX_PALABRAS = 14


@dataclass(frozen=True)
class ResultadoValidacion:
    valido: bool
    motivo: str = ""

    def __bool__(self) -> bool:
        return self.valido


def normalizar(texto: str) -> str:
    """Minúsculas sin tildes, para comparar léxico de forma estable."""
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _palabras(texto: str) -> Sequence[str]:
    return re.findall(r"[a-z0-9]+", normalizar(texto))


def segmentos_mencionados(texto: str) -> Tuple[str, ...]:
    palabras = set(_palabras(texto))
    encontrados = []
    for segmento, formas in LEXICO_SEGMENTOS.items():
        if any(f in palabras for f in formas):
            encontrados.append(segmento)
    return tuple(encontrados)


def lados_mencionados(texto: str) -> Tuple[Lado, ...]:
    palabras = set(_palabras(texto))
    encontrados = []
    for lado, formas in LEXICO_LADOS.items():
        if any(f in palabras for f in formas):
            encontrados.append(lado)
    return tuple(encontrados)


def validar(texto: str, error: ErrorTipificado,
            max_palabras: int = MAX_PALABRAS) -> ResultadoValidacion:
    """Valida un mensaje contra el contrato que lo originó."""
    if not texto or not texto.strip():
        return ResultadoValidacion(False, "mensaje_vacio")

    palabras = _palabras(texto)
    if len(palabras) > max_palabras:
        return ResultadoValidacion(False, f"demasiado_largo:{len(palabras)}")

    texto_norm = normalizar(texto)
    for prohibida in VOCABULARIO_PROHIBIDO:
        if normalizar(prohibida) in texto_norm:
            return ResultadoValidacion(False, f"vocabulario_medico:{prohibida}")

    segs = segmentos_mencionados(texto)
    ajenos = [s for s in segs if s != error.segmento]
    if ajenos:
        return ResultadoValidacion(
            False, f"segmento_ajeno:{','.join(sorted(ajenos))}")

    lados = lados_mencionados(texto)
    if error.lado in (Lado.BILATERAL, Lado.NA):
        if lados:
            return ResultadoValidacion(
                False, f"lado_inventado:{','.join(l.value for l in lados)}")
    else:
        ajenos_lado = [l for l in lados if l != error.lado]
        if ajenos_lado:
            return ResultadoValidacion(
                False, f"lado_incorrecto:{','.join(l.value for l in ajenos_lado)}")
        if not lados:
            return ResultadoValidacion(False, "lado_omitido")

    return ResultadoValidacion(True)


def afirmaciones_no_soportadas(texto: str, error: ErrorTipificado) -> Tuple[str, ...]:
    """Métrica M2 de EXP-001: qué afirma el mensaje que no está en el contrato.

    Devuelve la lista de segmentos y lados mencionados que no proceden del
    `ErrorTipificado`. Un verbalizador correcto devuelve tupla vacía siempre.
    """
    fuera = [s for s in segmentos_mencionados(texto) if s != error.segmento]
    if error.lado in (Lado.BILATERAL, Lado.NA):
        fuera += [l.value for l in lados_mencionados(texto)]
    else:
        fuera += [l.value for l in lados_mencionados(texto) if l != error.lado]
    return tuple(fuera)


__all__ = [
    "validar", "ResultadoValidacion", "segmentos_mencionados",
    "lados_mencionados", "afirmaciones_no_soportadas", "normalizar",
    "LEXICO_SEGMENTOS", "LEXICO_LADOS", "MAX_PALABRAS",
]
