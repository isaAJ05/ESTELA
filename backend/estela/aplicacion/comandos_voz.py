"""Comandos de voz: de un texto reconocido a una orden de una lista cerrada.

La usuaria puede mandar con la voz: pausa, seguir, siguiente, anterior,
reiniciar el ejercicio o la sesión, repetir el último aviso («repite eso»), activar o desactivar el
reconocimiento y los ángulos, terminar y «¿cómo voy?». El reconocedor de voz
(un adaptador) entrega texto; aquí se decide, **con reglas fijas y sin ningún
modelo de lenguaje**, qué orden es. Si el texto no contiene ninguna orden, o
contiene dos distintas, no se adivina: se pide repetir.

Dos modos de escucha (`puede_escuchar`), y nunca mientras ESTELA habla, para
que no se oiga a sí misma:
- «pausa» (primera versión): solo en pausas y entre ejercicios; todo lo que
  se oye se interpreta.
- «llamada» (estilo asistente de voz): también durante el ejercicio, pero una
  frase solo cuenta si empieza por «Estela» o «Oye Estela» (`separar_llamada`).
  Lo demás se ignora en silencio, para que hablar de otras cosas no genere
  «no te entendí».

Capa de aplicación: no importa micrófono ni reconocedor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from ..dominio.feedback.verbalizador.validador import normalizar

PAUSA, SEGUIR, SIGUIENTE, TERMINAR, COMO_VOY = (
    "pausa", "seguir", "siguiente", "terminar", "como_voy")
ANTERIOR, REINICIAR_EJERCICIO, REINICIAR_SESION = (
    "anterior", "reiniciar_ejercicio", "reiniciar_sesion")
RECONOCER_SI, RECONOCER_NO, ANGULOS_SI, ANGULOS_NO = (
    "reconocer_si", "reconocer_no", "angulos_si", "angulos_no")
REPITE_ESO, VOZ_SI, VOZ_NO = "repite_eso", "voz_si", "voz_no"
#: lista cerrada de órdenes
COMANDOS: Tuple[str, ...] = (PAUSA, SEGUIR, SIGUIENTE, TERMINAR, COMO_VOY,
                             ANTERIOR, REINICIAR_EJERCICIO, REINICIAR_SESION,
                             RECONOCER_SI, RECONOCER_NO, ANGULOS_SI, ANGULOS_NO,
                             REPITE_ESO, VOZ_SI, VOZ_NO)
#: Órdenes que cambian un ajuste de la pantalla, no el curso de la rutina: (ajuste, valor).
#: La escucha las publica en `pantalla` para que los botones de la interfaz las sigan.
AJUSTES_DE_PANTALLA: Dict[str, Tuple[str, bool]] = {
    ANGULOS_SI: ("angulos", True), ANGULOS_NO: ("angulos", False),
    RECONOCER_SI: ("reconocer", True), RECONOCER_NO: ("reconocer", False),
    VOZ_SI: ("voz", True), VOZ_NO: ("voz", False)}
ORDENES_DE_AJUSTE: Tuple[str, ...] = tuple(AJUSTES_DE_PANTALLA)

#: Formas de decir cada orden, sin tildes y en minúsculas. Se buscan como
#: palabras enteras. `[R]` Léxico corto a propósito: cada forma nueva es una
#: forma más de confundirse; ampliarlo con lo que se oiga en las pruebas.
LEXICO: Dict[str, Tuple[str, ...]] = {
    PAUSA: ("pausa", "pausar", "pausalo", "pausemos", "espera", "esperame"),
    # `[F]` «seguire»: así escribió Whisper «seguir» en la sesión de Paula del 2026-11-16
    SEGUIR: ("seguir", "sigue", "sigamos", "seguimos", "seguire", "continuar", "continua",
             "continuemos", "reanudar", "reanuda"),
    SIGUIENTE: ("siguiente", "proximo", "saltar", "salta", "saltemos"),
    TERMINAR: ("terminar", "termina", "terminemos", "terminamos", "acabar", "finalizar"),
    COMO_VOY: ("como voy", "como vamos", "como lo estoy haciendo", "que tal voy"),
    ANTERIOR: ("anterior", "ejercicio anterior", "regresar", "regresa", "vuelve al anterior"),
    REINICIAR_EJERCICIO: ("reiniciar ejercicio", "reinicia ejercicio", "reiniciar el ejercicio",
                          "reinicia el ejercicio"),
    REINICIAR_SESION: ("reiniciar sesion", "reinicia sesion", "reiniciar la sesion",
                       "reinicia la sesion", "reiniciar rutina", "reinicia la rutina",
                       "reiniciar la rutina"),
    RECONOCER_SI: ("reconocer activado", "reconocer encendido", "activar reconocer",
                   "activa reconocer", "reconocimiento activado", "activar el reconocimiento",
                   "activa el reconocimiento",
                   # `[F]` dichas por Paula en su sesión del 2026-11-16 y no entendidas
                   "activa reconocimiento", "activar reconocimiento", "activa y reconoce"),
    RECONOCER_NO: ("reconocer desactivado", "reconocer apagado", "desactivar reconocer",
                   "desactiva reconocer", "reconocimiento desactivado",
                   "desactivar el reconocimiento", "desactiva el reconocimiento",
                   "desactiva reconocimiento", "desactivar reconocimiento"),
    ANGULOS_SI: ("angulos activado", "angulos activados", "activar angulos", "activa angulos",
                 "activar los angulos", "activa los angulos", "muestra los angulos",
                 "mostrar angulos", "muestra angulos"),
    ANGULOS_NO: ("angulos desactivado", "angulos desactivados", "desactivar angulos",
                 "desactiva angulos", "desactivar los angulos", "desactiva los angulos",
                 "oculta los angulos", "ocultar angulos", "oculta angulos"),
    REPITE_ESO: ("repite eso", "repite lo ultimo", "repite el aviso", "que dijiste",
                 "dilo otra vez"),
    # «Estela, háblame» / «Estela, silencio»: pedidos por Paula (2026-11-16)
    VOZ_SI: ("voz activada", "activa la voz", "activar la voz", "enciende la voz",
             "hablame", "habla", "vuelve a hablar"),
    VOZ_NO: ("voz desactivada", "desactiva la voz", "desactivar la voz", "apaga la voz",
             "silencia la voz", "silencio", "callate"),
}

#: Lo que ESTELA dice al confirmar cada orden (texto fijo). Vacío donde la sesión
#: ya lo anuncia al ejecutar la acción («En pausa.», «Seguimos.», «Ahora, …»): si
#: la escucha también lo dijera, sonaría dos veces (visto en la sesión de Paula
#: del 2026-11-16: «Seguimos.» repetido al reanudar por voz).
CONFIRMACION: Dict[str, str] = {
    PAUSA: "",
    SEGUIR: "",
    SIGUIENTE: "",
    TERMINAR: "Terminamos.",
    COMO_VOY: "",                       # responde la entrenadora
    ANTERIOR: "",
    REINICIAR_EJERCICIO: "Reiniciamos el ejercicio.",
    REINICIAR_SESION: "",               # antes pide confirmación (`PREGUNTA_REINICIAR`)
    RECONOCER_SI: "Reconocimiento activado.",
    RECONOCER_NO: "Reconocimiento desactivado.",
    ANGULOS_SI: "Ángulos activados.",
    ANGULOS_NO: "Ángulos desactivados.",
    REPITE_ESO: "",                     # repite lo último que se dijo
    VOZ_SI: "Voz activada.",
    VOZ_NO: "",                         # silenciada: no puede decir nada
}
#: si no se ha dicho nada que repetir
NO_HAY_QUE_REPETIR = "No tengo nada que repetir."
#: «siguiente» en el último ejercicio y «anterior» en el primero no hacen nada: se dice
ES_EL_ULTIMO = "Este es el último ejercicio."
ES_EL_PRIMERO = "Este es el primer ejercicio."


def frases_propias() -> Tuple[str, ...]:
    """Lo que la escucha dice por su cuenta; «repite eso» no lo repite."""
    return tuple(t for t in (*CONFIRMACION.values(), NO_ENTENDI, PREGUNTA_REINICIAR,
                             CONFIRMA_REINICIAR, NO_HAY_QUE_REPETIR, ES_EL_ULTIMO,
                             ES_EL_PRIMERO) if t)
#: reiniciar toda la sesión borra el avance: se pide confirmación (texto fijo)
PREGUNTA_REINICIAR = "¿Reinicio toda la sesión? Di: Estela, sí."
CONFIRMA_REINICIAR = "Reiniciamos la sesión."
#: lo que se dice cuando hubo palabras pero ninguna orden clara (texto fijo)
NO_ENTENDI = "No te entendí. Repite, por favor."

#: motivos de `Interpretacion.motivo`. `SIN_LLAMADA`: modo «llamada» y la frase
#: no empezaba por «Estela»; se ignora sin decir nada.
ENTENDIDO, VACIO, SIN_COMANDO, AMBIGUO = "entendido", "vacio", "sin_comando", "ambiguo"
SIN_LLAMADA = "sin_llamada"
#: dijo solo «Estela»: la frase siguiente cuenta como orden
SOLO_LLAMADA = "solo_llamada"

#: Cómo puede escribir el reconocedor «Estela». `[F]` «Stella» y «Estila» salieron
#: en la prueba con voces sintéticas del Mac (2 de 26 llamadas, 2026-11-16).
#: `[?]` Sin calibrar con la voz de Paula y el micrófono real; ampliar con lo
#: que se oiga en las pruebas.
LLAMADAS: Tuple[str, ...] = ("estela", "estella", "estel", "stela", "stella", "estila",
                             "esthela")
#: palabras que pueden ir antes: «Oye Estela»
_ANTES_DE_LLAMAR: Tuple[str, ...] = ("oye", "hey", "ey")
#: segundos que, tras decir solo «Estela», la siguiente frase cuenta como orden
VENTANA_LLAMADA_S = 6.0
#: segundos para confirmar una pregunta («¿Reinicio toda la sesión?»); incluyen lo
#: que tarda ESTELA en hacerla, porque mientras habla no escucha
VENTANA_CONFIRMACION_S = 12.0
_SI = ("si", "confirmo", "confirmar", "dale", "hazlo", "adelante")
_NO = ("no", "cancela", "cancelar", "mejor no", "olvidalo")

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
    t = re.sub(r"\s+", " ", re.sub(r"[^a-zñ0-9 ]", " ", t)).strip()
    # `[F]` con la voz Mónica, Whisper escribió «águlos» por «ángulos»
    return re.sub(r"\bagulos\b", "angulos", t)


def _es_subfrase(corta: str, larga: str) -> bool:
    """`corta` está dentro de `larga` (palabras enteras) y no es igual."""
    return corta != larga and f" {corta} " in f" {larga} "


def interpretar(texto: Optional[str]) -> Interpretacion:
    """Texto reconocido → orden. Nunca adivina: una sola orden o ninguna."""
    t = _limpiar(texto)
    if not t or t in _ALUCINACIONES:
        return Interpretacion(None, VACIO, t)
    relleno = f" {t} "
    formas = {c: [f for f in LEXICO[c] if f" {f} " in relleno] for c in COMANDOS}
    halladas = [c for c in COMANDOS if formas[c]]
    # «repite eso» contiene «repite»: gana la forma más larga, no es ambiguo
    halladas = [c for c in halladas
                if not any(_es_subfrase(f, g) for f in formas[c]
                           for d in halladas if d != c for g in formas[d])]
    if len(halladas) == 1:
        return Interpretacion(halladas[0], ENTENDIDO, t)
    return Interpretacion(None, AMBIGUO if halladas else SIN_COMANDO, t)


def separar_llamada(texto: Optional[str]) -> Tuple[bool, str]:
    """(¿empieza por «Estela» u «Oye Estela»?, lo que sigue ya limpio)."""
    palabras = _limpiar(texto).split()
    i = 1 if palabras and palabras[0] in _ANTES_DE_LLAMAR else 0
    if i < len(palabras) and palabras[i] in LLAMADAS:
        return True, " ".join(palabras[i + 1:])
    return False, " ".join(palabras)


def respuesta_de_confirmacion(texto: Optional[str]) -> Optional[bool]:
    """True si dice sí, False si dice no o cancela, None si es otra cosa. Solo
    se usa tras una pregunta, y con frases cortas."""
    t = _limpiar(texto)
    palabras = t.split()
    if not palabras or len(palabras) > 4:
        return None
    relleno = f" {t} "
    dice_no = any(f" {f} " in relleno for f in _NO)
    dice_si = any(f" {f} " in relleno for f in _SI)
    if dice_si == dice_no:
        return None
    return dice_si


def puede_escuchar(en_pausa: bool, colocando: bool, hablando: bool,
                   terminada: bool = False, siempre: bool = False) -> bool:
    """Por defecto, solo en pausa o entre ejercicios (colocación). Con
    `siempre` (modo «llamada») también durante el ejercicio. En los dos casos,
    nunca mientras suena la voz de ESTELA ni con la rutina terminada."""
    return (siempre or en_pausa or colocando) and not hablando and not terminada


__all__ = ["COMANDOS", "PAUSA", "SEGUIR", "SIGUIENTE", "TERMINAR", "COMO_VOY",
           "ANTERIOR", "REINICIAR_EJERCICIO", "REINICIAR_SESION", "RECONOCER_SI",
           "RECONOCER_NO", "ANGULOS_SI", "ANGULOS_NO", "REPITE_ESO", "VOZ_SI", "VOZ_NO",
           "AJUSTES_DE_PANTALLA", "ORDENES_DE_AJUSTE", "NO_HAY_QUE_REPETIR", "ES_EL_ULTIMO", "ES_EL_PRIMERO", "frases_propias",
           "LEXICO", "CONFIRMACION", "PREGUNTA_REINICIAR", "CONFIRMA_REINICIAR",
           "NO_ENTENDI", "ENTENDIDO", "VACIO", "SIN_COMANDO", "AMBIGUO", "SIN_LLAMADA", "SOLO_LLAMADA",
           "LLAMADAS", "VENTANA_LLAMADA_S", "VENTANA_CONFIRMACION_S", "Interpretacion",
           "interpretar", "separar_llamada", "respuesta_de_confirmacion", "puede_escuchar"]
