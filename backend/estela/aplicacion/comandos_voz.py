"""Comandos de voz: de un texto reconocido a una orden de una lista cerrada.

La usuaria puede mandar con la voz seis cosas: pausa, seguir, siguiente,
repetir, terminar y «¿cómo voy?». El reconocedor de voz (un adaptador) entrega
texto; aquí se decide, **con reglas fijas y sin ningún modelo de lenguaje**,
qué orden es. Si el texto no contiene ninguna orden, o contiene dos distintas,
no se adivina: se pide repetir.

Primera versión: solo se escucha en pausas y entre ejercicios, y nunca
mientras ESTELA habla, para que no se oiga a sí misma (`puede_escuchar`).

Capa de aplicación: no importa micrófono ni reconocedor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from ..dominio.feedback.verbalizador.validador import normalizar

PAUSA, SEGUIR, SIGUIENTE, REPETIR, TERMINAR, COMO_VOY = (
    "pausa", "seguir", "siguiente", "repetir", "terminar", "como_voy")
#: lista cerrada de órdenes
COMANDOS: Tuple[str, ...] = (PAUSA, SEGUIR, SIGUIENTE, REPETIR, TERMINAR, COMO_VOY)

#: Formas de decir cada orden, sin tildes y en minúsculas. Se buscan como
#: palabras enteras. `[R]` Léxico corto a propósito: cada forma nueva es una
#: forma más de confundirse; ampliarlo con lo que se oiga en las pruebas.
LEXICO: Dict[str, Tuple[str, ...]] = {
    PAUSA: ("pausa", "pausar", "pausalo", "pausemos", "espera", "esperame"),
    SEGUIR: ("seguir", "sigue", "sigamos", "seguimos", "continuar", "continua",
             "continuemos", "reanudar", "reanuda"),
    SIGUIENTE: ("siguiente", "proximo", "saltar", "salta", "saltemos"),
    REPETIR: ("repetir", "repite", "repitamos", "otra vez", "de nuevo"),
    TERMINAR: ("terminar", "termina", "terminemos", "terminamos", "acabar", "finalizar"),
    COMO_VOY: ("como voy", "como vamos", "como lo estoy haciendo", "que tal voy"),
}

#: lo que ESTELA dice al confirmar cada orden (texto fijo)
CONFIRMACION: Dict[str, str] = {
    PAUSA: "Pausa.",
    SEGUIR: "Seguimos.",
    SIGUIENTE: "Siguiente ejercicio.",
    REPETIR: "Repetimos.",
    TERMINAR: "Terminamos.",
    COMO_VOY: "",                       # responde la entrenadora
}
#: lo que se dice cuando hubo palabras pero ninguna orden clara (texto fijo)
NO_ENTENDI = "No te entendí. Repite, por favor."

#: motivos de `Interpretacion.motivo`
ENTENDIDO, VACIO, SIN_COMANDO, AMBIGUO = "entendido", "vacio", "sin_comando", "ambiguo"

#: Whisper, ante silencio o ruido, a veces escribe frases que nadie dijo. Estas
#: se tratan como silencio para no pedir repetir sin motivo. `[I]` Lista
#: mínima con lo visto en las pruebas con audio sintético; ampliable.
_ALUCINACIONES = ("subtitulos realizados por la comunidad de amara org",
                  "gracias por ver el video", "gracias por ver", "suscribete")


@dataclass(frozen=True)
class Interpretacion:
    #: una de `COMANDOS`, o None
    comando: Optional[str]
    #: `ENTENDIDO`, `VACIO` (nada que valga la pena contestar), `SIN_COMANDO`
    #: o `AMBIGUO` (en estos dos se pide repetir)
    motivo: str
    #: el texto tal como se comparó (minúsculas, sin tildes ni signos)
    texto: str

    @property
    def pedir_repetir(self) -> bool:
        return self.motivo in (SIN_COMANDO, AMBIGUO)


def _limpiar(texto: Optional[str]) -> str:
    t = normalizar(texto or "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-zñ0-9 ]", " ", t)).strip()


def interpretar(texto: Optional[str]) -> Interpretacion:
    """Texto reconocido → orden. Nunca adivina: una sola orden o ninguna."""
    t = _limpiar(texto)
    if not t or t in _ALUCINACIONES:
        return Interpretacion(None, VACIO, t)
    relleno = f" {t} "
    halladas = [c for c in COMANDOS
                if any(f" {forma} " in relleno for forma in LEXICO[c])]
    if len(halladas) == 1:
        return Interpretacion(halladas[0], ENTENDIDO, t)
    return Interpretacion(None, AMBIGUO if halladas else SIN_COMANDO, t)


def puede_escuchar(en_pausa: bool, colocando: bool, hablando: bool,
                   terminada: bool = False) -> bool:
    """Solo en pausa o entre ejercicios (colocación), y nunca mientras suena
    la voz de ESTELA ni con la rutina terminada."""
    return (en_pausa or colocando) and not hablando and not terminada


__all__ = ["COMANDOS", "PAUSA", "SEGUIR", "SIGUIENTE", "REPETIR", "TERMINAR", "COMO_VOY",
           "LEXICO", "CONFIRMACION", "NO_ENTENDI", "ENTENDIDO", "VACIO", "SIN_COMANDO",
           "AMBIGUO", "Interpretacion", "interpretar", "puede_escuchar"]
