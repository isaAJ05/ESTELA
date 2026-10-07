"""Contrato JSON entre la sesión (Python) y la interfaz de escritorio.

La interfaz no decide nada: solo muestra lo que recibe. Este módulo traduce
los objetos de la sesión (`EstadoFrame`, `Rutina`, `Sesion.resumen()`) a
diccionarios serializables con las claves que espera `interfaz/src/bridge/
tipos.ts`. Si cambia un nombre aquí, cambia también allí.

Funciones que el backend todavía no tiene
-----------------------------------------
La interfaz ya trae el espacio visual para algunas funciones que aún no
existen en el backend (nivel, correctas/con error, guía animada, resumen en
lenguaje natural...). Mientras su capacidad esté en False en `CAPACIDADES`,
la interfaz no las muestra. Para activarlas:

1. Implementar la función en el backend.
2. Si trae un dato por frame, añadirlo a `EstadoFrame` con el nombre de la
   columna «campo» de abajo: `estado_a_dict` lo recoge solo (`getattr`).
   Si es del resumen, añadirlo a cada paso de `Sesion.resumen()` o al
   resumen general con ese mismo nombre.
3. Poner la capacidad en True.

=================  ==================================  =====================
capacidad          campo                               tarea
=================  ==================================  =====================
nivel              EstadoFrame.nivel                   T22.a
correctasConError  EstadoFrame.correctas / con_error   T29.a
                   y en cada paso del resumen
guia               EstadoFrame.guia (33×[x, y, vis])   T14
resumenTexto       resumen["resumen_texto"]            T27 (LLM rol B)
motivoSilencio     EstadoFrame.motivo_silencio         modo depuración
pausaManual        (comando `pausar`/`reanudar`)       —
colocacion         (fase previa de colocación)         —
avisoLuz           (aviso de poca luz)                 —
=================  ==================================  =====================
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

import numpy as np

from feedback.contrato import Plano

from ..pose.landmarks import CONEXIONES
from ..sesion.rutina import Ejercicio, Rutina
from ..sesion.sesion import (AVISO_ENCUADRE, AVISO_PAUSA, AVISO_SIN_PERSONA,
                             _COLOCACION, EstadoFrame)

VERSION = 1

CAPACIDADES: Dict[str, bool] = {
    "nivel": False,
    "correctasConError": False,
    "guia": False,
    "resumenTexto": False,
    "motivoSilencio": False,
    "pausaManual": False,
    "colocacion": False,
    "avisoLuz": False,
}

_ORIENTACION = {Plano.FRONTAL: "frente", Plano.SAGITAL: "perfil"}


def tipo_aviso(texto: Optional[str]) -> Optional[str]:
    """Clasifica un aviso operativo para elegir su ícono en la interfaz."""
    if texto is None:
        return None
    if texto == AVISO_ENCUADRE:
        return "encuadre"
    if texto == AVISO_SIN_PERSONA:
        return "sin_persona"
    if texto in _COLOCACION.values():
        return "orientacion"
    if texto in AVISO_PAUSA.values():
        return "pausa"
    return "otro"


def _puntos(lm: Optional[np.ndarray]) -> Optional[List[List[float]]]:
    """(33, 4) [x, y, z, vis] → [[x, y, vis], ...] redondeado (solo para dibujar)."""
    if lm is None:
        return None
    return [[round(float(p[0]), 4), round(float(p[1]), 4), round(float(p[-1]), 3)]
            for p in lm]


def estado_a_dict(estado: EstadoFrame, fps: Optional[float] = None) -> Dict[str, Any]:
    opcional = lambda nombre: getattr(estado, nombre, None)      # noqa: E731
    guia = opcional("guia")
    return {
        "ejercicio": estado.ejercicio,
        "ejercicioId": estado.ejercicio_id,
        "paso": estado.paso,
        "totalPasos": estado.total_pasos,
        "objetivo": estado.objetivo,
        "unidad": estado.unidad,
        "completadas": estado.completadas,
        "incompletas": estado.incompletas,
        "fase": estado.fase,
        "persona": estado.persona,
        "orientacionGrados": (round(estado.orientacion, 1)
                              if estado.orientacion is not None else None),
        "aviso": estado.aviso,
        "avisoTipo": tipo_aviso(estado.aviso),
        "ultimoMensaje": estado.ultimo_mensaje,
        "mensajesEmitidos": estado.mensajes_emitidos,
        "pausada": estado.pausada,
        "motivoPausa": estado.motivo_pausa,
        "puntos": _puntos(estado.landmarks),
        "terminada": estado.terminada,
        # aún sin backend (ver CAPACIDADES): llegan null
        "correctas": opcional("correctas"),
        "conError": opcional("con_error"),
        "nivel": opcional("nivel"),
        "guia": _puntos(np.asarray(guia)) if guia is not None else None,
        "depuracion": {
            "fps": round(fps, 1) if fps is not None else None,
            "latenciaMs": {k: round(v, 2) for k, v in estado.latencia_ms.items()},
            "motivoSilencio": opcional("motivo_silencio"),
        },
    }


def rutina_a_dict(rutina: Rutina, catalogo: Mapping[str, Ejercicio]) -> Dict[str, Any]:
    pasos = []
    for p in rutina.pasos:
        ej = catalogo[p.skill_id]
        pasos.append({
            "skillId": p.skill_id,
            "nombre": ej.skill.nombre,
            "orientacion": _ORIENTACION.get(ej.skill.orientacion_preferida),
            "unidad": ej.unidad,
            "objetivo": p.repeticiones,
        })
    return {"nombre": rutina.nombre, "pasos": pasos}


def resumen_a_dict(resumen: Mapping[str, Any],
                   catalogo: Mapping[str, Ejercicio]) -> Dict[str, Any]:
    """`Sesion.resumen()` → resumen para la pantalla final (solo métricas derivadas)."""
    pasos = []
    for p in resumen["pasos"]:
        ej = catalogo.get(p["skill_id"])
        pasos.append({
            "skillId": p["skill_id"],
            "nombre": ej.skill.nombre if ej else p["skill_id"],
            "unidad": p["unidad"],
            "objetivo": p["objetivo"],
            "completadas": p["completadas"],
            "incompletas": p["incompletas"],
            "correctas": p.get("correctas"),
            "conError": p.get("con_error"),
            "duracionS": p["duracion_s"],
            "pausas": p["pausas_sesion"],
            "pausaS": p["pausa_s"],
            "mensajes": [{"tMs": m["t_ms"], "texto": m["texto"],
                          "errorId": m["error_id"], "repeticion": m["repeticion"]}
                         for m in p["mensajes"]],
        })
    return {
        "rutina": resumen["rutina"],
        "terminada": resumen["terminada"],
        "duracionTotalS": round(sum(p["duracionS"] for p in pasos), 1),
        "pasos": pasos,
        "resumenTexto": resumen.get("resumen_texto"),
    }


def info(rutina: Rutina, catalogo: Mapping[str, Ejercicio], espejo: bool) -> Dict[str, Any]:
    """Datos fijos de la aplicación: se piden una vez al abrir la ventana."""
    return {
        "version": VERSION,
        "capacidades": dict(CAPACIDADES),
        "rutina": rutina_a_dict(rutina, catalogo),
        "conexiones": [list(c) for c in CONEXIONES],
        "espejo": espejo,
    }


__all__ = ["CAPACIDADES", "VERSION", "estado_a_dict", "info", "resumen_a_dict",
           "rutina_a_dict", "tipo_aviso"]
