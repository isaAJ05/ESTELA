"""Entrenadora: resumen hablado entre ejercicios y al final de la rutina.

Solo actúa **entre ejercicios y al final, nunca durante el movimiento**. Un
modelo de lenguaje local (rol B de ADR-004, ampliado; pendiente de ADR) redacta
un resumen corto de lo ocurrido y **propone** una acción de una lista cerrada.
El código valida las dos cosas y, si algo falla, responde con una plantilla.

Reparto de responsabilidades (CLAUDE.md §5):

  - El modelo NO decide qué error de movimiento hubo ni si se corrige: recibe
    solo cifras ya derivadas (hechas, objetivo, avisos dados) y nunca frames,
    puntos del cuerpo ni ángulos.
  - La acción es una propuesta. Sale de `ACCIONES`, el código comprueba que
    esté permitida en ese momento y la frase que la anuncia es fija
    (`FRASE_ACCION`), así el texto y la acción no se pueden contradecir.
    Ejecutarla sigue siendo cosa de la usuaria.
  - Dolor o lesión: respuesta fija, sin modelo (`RESPUESTA_DOLOR`).
  - El historial mide constancia y avisos recibidos, **no la técnica**
    (`historial.py`, ADR-008 §2.4): `NOTA_HISTORIAL` lo dice con palabras
    fijas y el validador rechaza un resumen que califique la técnica.

Capa de aplicación: no importa red ni adaptadores. El modelo entra como una
función `Generador`; `adaptadores/llm/entrenadora_ollama.py` da una con Ollama.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from ..dominio.feedback.contrato import VOCABULARIO_PROHIBIDO
from ..dominio.feedback.verbalizador.validador import (
    lados_mencionados, normalizar, segmentos_mencionados,
)

REPETIR, DESCANSAR, SEGUIR, TERMINAR = "repetir", "descansar", "seguir", "terminar"
#: lista cerrada de acciones que la entrenadora puede proponer
ACCIONES: Tuple[str, ...] = (REPETIR, DESCANSAR, SEGUIR, TERMINAR)

ENTRE, FINAL, CONSULTA = "entre", "final", "consulta"
#: acciones permitidas según el momento. Al final de la rutina no queda
#: ejercicio siguiente ni actual: solo se puede terminar. En una consulta
#: («¿cómo voy?») no se propone nada: solo se resume.
PERMITIDAS: Dict[str, Tuple[str, ...]] = {
    ENTRE: (REPETIR, DESCANSAR, SEGUIR, TERMINAR),
    FINAL: (TERMINAR,),
    CONSULTA: (SEGUIR,),
}

#: frase fija que anuncia la acción propuesta (la dice el código, no el modelo)
FRASE_ACCION: Dict[str, str] = {
    REPETIR: "Te propongo repetir este ejercicio.",
    DESCANSAR: "Te propongo descansar un momento antes de seguir.",
    SEGUIR: "Te propongo seguir con el siguiente ejercicio.",
    TERMINAR: "Te propongo terminar por hoy.",
}
FRASE_FINAL = "Rutina terminada."

#: Tope de palabras del resumen que redacta el modelo. Aprobado por Paula el
#: 2026-11-16 para la rama feature/mac-flujo. Es una guarda técnica, sin
#: respaldo experimental: revisarlo tras la tanda de pruebas con voz real.
MAX_PALABRAS_RESUMEN = 40

#: Lo que el historial puede y no puede decir (ADR-008 §2.4). Texto fijo.
NOTA_HISTORIAL = ("El historial cuenta tu constancia y los avisos que recibiste; "
                  "no mide tu técnica.")

#: Respuesta fija ante dolor o lesión: no pasa por el modelo. No diagnostica.
#: Redacción aprobada por Paula el 2026-11-16 para la rama feature/mac-flujo.
#: Versión breve pedida por Paula el 2026-11-16 (la anterior era más larga). No valora
#: el dolor: pide parar y remite a un profesional. Con voz de entrada, además se pausa.
RESPUESTA_DOLOR = ("Si te duele, no sigas. Si la molestia continúa, "
                   "consulta a un profesional de la salud.")

#: Señales de dolor o lesión en lo que dice la usuaria (sin tildes, minúsculas).
#: Lista corta y amplia a propósito: ante la duda, respuesta fija.
LEXICO_DOLOR: Tuple[str, ...] = (
    "dolor", "duele", "duelen", "dolio", "doliendo", "lesion", "lesione", "lastim",
    "molestia", "molesta", "mareo", "mareada", "mareado", "marea", "tiron",
    "calambre", "torci", "torcedura", "pinchazo", "punzada", "herida", "golpe",
    "desmay", "no puedo respirar", "me falta el aire", "hormigueo", "crujio",
)

#: El resumen no puede calificar la técnica (el historial no la mide).
_JUICIO_TECNICA = re.compile(
    r"\btecnica\b.{0,40}\b(mejor\w*|peor\w*|perfect\w*|excelente|correcta|buena|mala|impecable)\b"
    r"|\b(mejor\w*|peor\w*|perfect\w*|excelente|correcta|buena|mala|impecable)\b.{0,40}\btecnica\b")

ORIGEN_LLM, ORIGEN_PLANTILLA, ORIGEN_DOLOR = "llm", "plantilla", "fija_dolor"

SISTEMA = (
    "Eres la entrenadora de una aplicación de calentamiento. Hablas en español, "
    "en segunda persona, con frases cortas y tono amable.\n"
    "Recibes datos ya medidos de un ejercicio o de la rutina. Con ellos:\n"
    "1. Escribe un resumen de una o dos frases, como máximo "
    f"{MAX_PALABRAS_RESUMEN} palabras, solo con los datos que se te dan.\n"
    "2. No inventes cifras: usa únicamente los números que aparecen en los datos.\n"
    "3. No califiques la técnica ni digas que mejoró o empeoró: los datos "
    "cuentan repeticiones y avisos, no miden la técnica.\n"
    "4. No hables de dolor, lesiones ni salud. No diagnostiques.\n"
    "5. No nombres partes del cuerpo que no aparezcan en los datos.\n"
    "6. No propongas qué hacer en el resumen: elige la acción en el campo "
    "\"accion\", que debe ser una de las permitidas.\n"
    "7. Responde en JSON con la forma {\"resumen\": \"...\", \"accion\": \"...\"}."
)

#: (mensaje de sistema, mensaje de usuario, acciones permitidas) → dict con
#: «resumen» y «accion». Puede lanzar: la entrenadora cae a plantilla.
Generador = Callable[[str, str, Sequence[str]], Mapping[str, Any]]


@dataclass(frozen=True)
class Respuesta:
    #: lo que se dice: resumen + frase fija de la acción
    texto: str
    accion: str
    #: `ORIGEN_LLM`, `ORIGEN_PLANTILLA` o `ORIGEN_DOLOR`
    origen: str
    momento: str
    #: por qué no se usó el modelo (vacío si se usó o no había)
    motivo_caida: str = ""
    latencia_ms: float = 0.0
    #: aclaración fija si la respuesta usó datos del historial
    nota: str = ""

    def a_dict(self) -> Dict[str, Any]:
        return {"texto": self.texto, "accion": self.accion, "origen": self.origen,
                "momento": self.momento, "motivo_caida": self.motivo_caida,
                "latencia_ms": round(self.latencia_ms, 1), "nota": self.nota}


# ---------------------------------------------------------------------------
# Hechos: lo único que ve el modelo
# ---------------------------------------------------------------------------

def menciona_dolor(texto: Optional[str]) -> bool:
    if not texto:
        return False
    t = normalizar(texto)
    return any(p in t for p in LEXICO_DOLOR)


def _indicaciones(paso: Mapping[str, Any]) -> List[Tuple[int, str]]:
    """(veces, frase) de cada aviso dado en el paso, de más a menos frecuente.
    Acepta un paso de `Sesion.resumen()` (`mensajes`) o del historial
    (`indicaciones`)."""
    if "indicaciones" in paso:
        pares = [(int(d.get("veces", 0)), str(d.get("texto", "")))
                 for d in (paso.get("indicaciones") or {}).values()]
    else:
        cuenta: Dict[str, Dict[str, int]] = {}
        for m in paso.get("mensajes", ()):
            if m.get("error_id"):
                frases = cuenta.setdefault(m["error_id"], {})
                frases[m.get("texto") or ""] = frases.get(m.get("texto") or "", 0) + 1
        pares = [(sum(f.values()), max(f, key=f.get)) for f in cuenta.values()]
    return sorted((p for p in pares if p[0] > 0), key=lambda p: (-p[0], p[1]))


def hechos_del_paso(paso: Mapping[str, Any], nombre: str,
                    siguiente: Optional[str] = None) -> List[str]:
    """Líneas de datos del ejercicio que acaba de terminar."""
    lineas = [
        f"ejercicio terminado: {nombre}",
        f"objetivo: {int(paso['objetivo'])} {paso['unidad']}",
        f"hechas: {int(paso['completadas'])} {paso['unidad']}",
    ]
    if paso["unidad"] == "repeticiones" and int(paso.get("incompletas", 0)):
        lineas.append(f"repeticiones incompletas: {int(paso['incompletas'])}")
    pausas = int(paso.get("pausas_sesion", paso.get("pausas", 0)))
    if pausas:
        lineas.append(f"pausas: {pausas}")
    avisos = _indicaciones(paso)
    if avisos:
        for veces, frase in avisos[:3]:
            lineas.append(f"aviso dado {veces} veces: «{frase}»")
    else:
        lineas.append("avisos dados: ninguno")
    lineas.append(f"ejercicio siguiente: {siguiente}" if siguiente
                  else "ejercicio siguiente: ninguno, era el último")
    return lineas


def hechos_de_la_rutina(pasos: Sequence[Mapping[str, Any]],
                        nombres: Mapping[str, str]) -> List[str]:
    """Líneas de datos de la rutina entera, para el resumen final."""
    completos = sum(1 for p in pasos if int(p["completadas"]) >= int(p["objetivo"]))
    minutos = round(sum(float(p.get("duracion_s", 0.0)) for p in pasos) / 60.0)
    lineas = [f"ejercicios de la rutina: {len(pasos)}",
              f"ejercicios con el objetivo cumplido: {completos}",
              f"minutos de ejercicio: {minutos}"]
    for p in pasos:
        avisos = sum(v for v, _ in _indicaciones(p))
        lineas.append(f"{nombres.get(p['skill_id'], p['skill_id'])}: "
                      f"{int(p['completadas'])} de {int(p['objetivo'])} {p['unidad']}, "
                      f"{avisos} avisos")
    return lineas


def hechos_del_historial(progreso: Optional[Mapping[str, Any]]) -> List[str]:
    """Líneas de constancia sacadas de `historial.progreso()`. Solo constancia:
    sesiones, días y racha. Vacío si no hay historial."""
    if not progreso or not progreso.get("total_sesiones"):
        return []
    return [f"sesiones guardadas antes de hoy: {int(progreso['total_sesiones'])}",
            f"días con sesión en los últimos 7: {int(progreso.get('dias_activos_7', 0))}",
            f"racha actual en días: {int(progreso.get('racha_dias', 0))}"]


# ---------------------------------------------------------------------------
# Validación de lo que devuelve el modelo
# ---------------------------------------------------------------------------

#: Números escritos con letras (sin tildes). No está «un/una/uno»: casi siempre
#: es artículo («una pausa») y daría rechazos falsos.
_NUMEROS_EN_LETRAS: Dict[str, int] = {
    "cero": 0, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13,
    "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18,
    "diecinueve": 19, "veinte": 20, "treinta": 30, "cuarenta": 40, "cincuenta": 50,
    "sesenta": 60,
}


def _numeros(texto: str) -> List[str]:
    """Cifras del texto, también las escritas con letras («dos veces» → 2)."""
    cifras = re.findall(r"\d+", texto)
    for palabra in re.findall(r"[a-zñ]+", normalizar(texto)):
        if palabra in _NUMEROS_EN_LETRAS:
            cifras.append(str(_NUMEROS_EN_LETRAS[palabra]))
    return cifras


def validar_resumen(resumen: Any, hechos: Sequence[str]) -> str:
    """"" si el resumen es aceptable; si no, el motivo del rechazo."""
    if not isinstance(resumen, str) or not resumen.strip():
        return "resumen_vacio"
    palabras = normalizar(resumen).split()
    if len(palabras) > MAX_PALABRAS_RESUMEN:
        return f"demasiado_largo:{len(palabras)}"
    norm = normalizar(resumen)
    for prohibida in VOCABULARIO_PROHIBIDO:
        if normalizar(prohibida) in norm:
            return f"vocabulario_medico:{prohibida}"
    if menciona_dolor(resumen):
        return "habla_de_dolor"
    if _JUICIO_TECNICA.search(norm):
        return "califica_la_tecnica"
    base = "\n".join(hechos)
    ajenos = sorted(set(_numeros(resumen)) - set(_numeros(base)))
    if ajenos:
        return f"cifra_inventada:{','.join(ajenos)}"
    segmentos = set(segmentos_mencionados(resumen)) - set(segmentos_mencionados(base))
    if segmentos:
        return f"segmento_ajeno:{','.join(sorted(segmentos))}"
    lados = set(lados_mencionados(resumen)) - set(lados_mencionados(base))
    if lados:
        return f"lado_ajeno:{','.join(sorted(l.value for l in lados))}"
    return ""


def validar_accion(accion: Any, momento: str) -> str:
    if accion not in ACCIONES:
        return f"accion_desconocida:{accion!r}"[:60]
    if accion not in PERMITIDAS[momento]:
        return f"accion_no_permitida:{accion}"
    return ""


# ---------------------------------------------------------------------------
# Respaldo determinista
# ---------------------------------------------------------------------------

def accion_por_defecto(momento: str, paso: Optional[Mapping[str, Any]] = None) -> str:
    """`[R]` Regla del respaldo: seguir si se cumplió el objetivo y repetir si
    no; al final, terminar."""
    if momento == CONSULTA:
        return SEGUIR
    if momento == FINAL or paso is None:
        return TERMINAR
    return SEGUIR if int(paso["completadas"]) >= int(paso["objetivo"]) else REPETIR


def resumen_plantilla(momento: str, paso: Optional[Mapping[str, Any]], nombre: str,
                      pasos: Sequence[Mapping[str, Any]] = ()) -> str:
    if momento == CONSULTA:
        completos = sum(1 for p in pasos if int(p["completadas"]) >= int(p["objetivo"]))
        avisos = sum(v for p in pasos for v, _ in _indicaciones(p))
        return (f"Llevas {len(pasos)} {'ejercicio' if len(pasos) == 1 else 'ejercicios'}, "
                f"{completos} con el objetivo cumplido, y {avisos} "
                f"{'aviso' if avisos == 1 else 'avisos'}.")
    if momento == FINAL:
        completos = sum(1 for p in pasos if int(p["completadas"]) >= int(p["objetivo"]))
        return f"Cumpliste el objetivo en {completos} de {len(pasos)} ejercicios."
    assert paso is not None
    texto = (f"Hiciste {int(paso['completadas'])} de {int(paso['objetivo'])} "
             f"{paso['unidad']} de {nombre.lower()}.")
    avisos = _indicaciones(paso)
    if avisos:
        veces, frase = avisos[0]
        texto += (f" El aviso más repetido, {veces} "
                  f"{'vez' if veces == 1 else 'veces'}: «{frase}»")
    return texto


# ---------------------------------------------------------------------------
# Entrenadora
# ---------------------------------------------------------------------------

class Entrenadora:
    """`generador=None`: siempre plantilla (sin modelo)."""

    def __init__(self, generador: Optional[Generador] = None,
                 nombres: Optional[Mapping[str, str]] = None) -> None:
        self.generador = generador
        #: skill_id → nombre que se dice
        self.nombres = dict(nombres or {})
        #: cuántas respuestas de cada origen y caídas por motivo
        self.origenes: Dict[str, int] = {}
        self.caidas: Dict[str, int] = {}

    def _nombre(self, skill_id: Optional[str]) -> Optional[str]:
        return None if skill_id is None else self.nombres.get(skill_id, skill_id)

    def _cierra(self, r: Respuesta) -> Respuesta:
        self.origenes[r.origen] = self.origenes.get(r.origen, 0) + 1
        if r.motivo_caida:
            clave = r.motivo_caida.split(":", 1)[0]
            self.caidas[clave] = self.caidas.get(clave, 0) + 1
        return r

    def entre_ejercicios(self, paso: Mapping[str, Any], siguiente: Optional[str] = None,
                         progreso: Optional[Mapping[str, Any]] = None,
                         dice_usuaria: Optional[str] = None) -> Respuesta:
        """Tras terminar `paso` (un paso de `Sesion.resumen()`); `siguiente`
        es el `skill_id` del que viene, si hay."""
        nombre = self._nombre(paso["skill_id"]) or ""
        hechos = hechos_del_paso(paso, nombre, self._nombre(siguiente))
        return self._responder(ENTRE, hechos, hechos_del_historial(progreso),
                               paso, nombre, (), dice_usuaria)

    def al_final(self, pasos: Sequence[Mapping[str, Any]],
                 progreso: Optional[Mapping[str, Any]] = None,
                 dice_usuaria: Optional[str] = None) -> Respuesta:
        hechos = hechos_de_la_rutina(pasos, self.nombres)
        return self._responder(FINAL, hechos, hechos_del_historial(progreso),
                               None, "", pasos, dice_usuaria)

    def como_voy(self, pasos: Sequence[Mapping[str, Any]],
                 progreso: Optional[Mapping[str, Any]] = None,
                 dice_usuaria: Optional[str] = None) -> Respuesta:
        """Respuesta a «¿cómo voy?» con lo hecho hasta ahora en la rutina.
        No propone ninguna acción: `accion` queda en seguir y no se anuncia."""
        # el total de avisos va como dato: la plantilla lo dice y, sin él, el
        # validador rechazaría por cifra inventada al modelo que los sumara
        avisos = sum(v for p in pasos for v, _ in _indicaciones(p))
        hechos = hechos_de_la_rutina(pasos, self.nombres) + [f"avisos en total: {avisos}"]
        return self._responder(CONSULTA, hechos, hechos_del_historial(progreso),
                               None, "", pasos, dice_usuaria)

    def _responder(self, momento: str, hechos: List[str], historial: List[str],
                   paso: Optional[Mapping[str, Any]], nombre: str,
                   pasos: Sequence[Mapping[str, Any]],
                   dice_usuaria: Optional[str]) -> Respuesta:
        t0 = time.perf_counter()
        ms = lambda: (time.perf_counter() - t0) * 1000.0     # noqa: E731
        if menciona_dolor(dice_usuaria):
            return self._cierra(Respuesta(RESPUESTA_DOLOR, TERMINAR, ORIGEN_DOLOR,
                                          momento, latencia_ms=ms()))
        nota = NOTA_HISTORIAL if historial else ""
        permitidas = PERMITIDAS[momento]
        motivo = ""
        if self.generador is not None:
            datos = "\n".join(hechos + historial + [
                "momento: " + {ENTRE: "entre dos ejercicios", FINAL: "final de la rutina",
                               CONSULTA: "la persona pregunta cómo va, a mitad de la rutina"
                               }[momento],
                "acciones permitidas: " + ", ".join(permitidas)])
            try:
                salida = self.generador(SISTEMA, datos, permitidas)
                resumen, accion = salida.get("resumen"), salida.get("accion")
                motivo = (validar_accion(accion, momento)
                          or validar_resumen(resumen, hechos + historial))
            except Exception as exc:                      # noqa: BLE001
                motivo = f"fallo_backend:{type(exc).__name__}"
            if not motivo:
                return self._cierra(Respuesta(
                    self._texto(resumen.strip(), accion, momento), accion, ORIGEN_LLM,
                    momento, latencia_ms=ms(), nota=nota))
        accion = accion_por_defecto(momento, paso)
        resumen = resumen_plantilla(momento, paso, nombre, pasos)
        return self._cierra(Respuesta(self._texto(resumen, accion, momento), accion,
                                      ORIGEN_PLANTILLA, momento, motivo_caida=motivo,
                                      latencia_ms=ms(), nota=nota))

    @staticmethod
    def _texto(resumen: str, accion: str, momento: str) -> str:
        if resumen and resumen[-1] not in ".!?»":
            resumen += "."
        if momento == CONSULTA:                     # solo el resumen, sin propuesta
            return resumen
        cierre = FRASE_FINAL if momento == FINAL else FRASE_ACCION[accion]
        return f"{resumen} {cierre}"


__all__ = [
    "ACCIONES", "PERMITIDAS", "REPETIR", "DESCANSAR", "SEGUIR", "TERMINAR", "ENTRE", "FINAL", "CONSULTA",
    "FRASE_ACCION", "MAX_PALABRAS_RESUMEN", "NOTA_HISTORIAL", "RESPUESTA_DOLOR",
    "LEXICO_DOLOR", "SISTEMA", "Generador", "Respuesta", "Entrenadora",
    "ORIGEN_LLM", "ORIGEN_PLANTILLA", "ORIGEN_DOLOR",
    "menciona_dolor", "hechos_del_paso", "hechos_de_la_rutina", "hechos_del_historial",
    "validar_resumen", "validar_accion", "accion_por_defecto", "resumen_plantilla",
]
