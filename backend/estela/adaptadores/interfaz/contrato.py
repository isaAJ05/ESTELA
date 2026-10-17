"""Contrato JSON entre la sesión (Python) y la interfaz de escritorio.

La interfaz no decide nada: solo muestra lo que recibe. Este módulo traduce
los objetos de la sesión (`EstadoFrame`, `Rutina`, `Sesion.resumen()`) a
diccionarios serializables con las claves que espera `frontend/src/bridge/
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
motivoSilencio     EstadoFrame.motivo_silencio         T29 (hecho)
pausaManual        (comando `pausar`/`reanudar`)       —
colocacion         (fase previa de colocación)         —
avisoLuz           (aviso de poca luz)                 —
=================  ==================================  =====================

Feedback
--------
`feedback` lleva la última indicación del motor ya tipada (no solo el texto):
tipo (corrección o refuerzo), error, segmento, lado, severidad y los índices
de las articulaciones del segmento (`puntos`), que la interfaz resalta en el
esqueleto. La interfaz no decide nada: el segmento y el lado los decidió el
motor determinista.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from ...dominio.feedback.contrato import MensajeFeedback, Plano

from ...dominio.feedback.motor.geometria import ANGULOS_MEDIOS, ANGULOS_TERNA
from ..pose.landmarks import CONEXIONES, NOMBRES_MEDIAPIPE, puntos_de_segmento
from ...aplicacion.rutina import Ejercicio, Rutina
from ...aplicacion.sesion import (AVISO_ENCUADRE, AVISO_PAUSA, AVISO_SIN_PERSONA,
                             _COLOCACION, EstadoFrame)

VERSION = 1

CAPACIDADES: Dict[str, bool] = {
    "nivel": False,
    "correctasConError": False,
    "guia": True,
    "resumenTexto": False,
    "motivoSilencio": True,
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


def _angulos_de_medida(clave: str) -> List[str]:
    """Nombres de los ángulos de una medida (`Medida.clave()`): «angulo:x»,
    «min(x)@repeticion» o «asimetria(x,y)». Un ángulo bilateral («_medio»)
    se expande a sus dos lados, que es lo que se dibuja en las articulaciones."""
    if "(" in clave:
        nombres = clave[clave.index("(") + 1:clave.index(")")].split(",")
    else:
        nombres = [clave.split(":", 1)[-1]]
    salida: List[str] = []
    for n in nombres:
        salida.append(n)
        salida.extend(ANGULOS_MEDIOS.get(n, ()))
    return salida


#: Medidas en distancia que no tienen grados propios: en pantalla se señala el
#: ángulo que mejor las representa (EXP-009). Plancha: la cadera, con la línea
#: hombro–cadera–tobillo (180° = recta); los hombros, con el ángulo
#: cadera–hombro–codo (≈ 90° con el hombro sobre el codo).
_ANGULO_EQUIVALENTE: Dict[str, Tuple[str, ...]] = {
    "alineacion_cadera": ("alineacion_cuerpo_izq", "alineacion_cuerpo_der"),
    "hombro_sobre_codo": ("hombro_izq", "hombro_der"),
}


def feedback_a_dict(m: Optional[MensajeFeedback]) -> Optional[Dict[str, Any]]:
    """Último mensaje del motor → indicación tipada para la interfaz."""
    if m is None:
        return None
    err = m.error
    if err is None:                     # refuerzo: no nombra segmento ni lado
        return {"texto": m.texto, "tipo": "refuerzo", "errorId": None,
                "segmento": None, "lado": None, "severidad": None, "puntos": [],
                "angulos": [], "magnitud": None, "direccion": None}
    angulos = _angulos_de_medida(err.medida)
    magnitud: Optional[float] = round(err.magnitud, 1)
    equivalentes = [a for n in angulos for a in _ANGULO_EQUIVALENTE.get(n, ())]
    if equivalentes:
        # la magnitud está en escalas corporales, no en grados: no se muestra
        angulos, magnitud = equivalentes, None
    return {
        "texto": m.texto,
        "tipo": "correccion",
        "errorId": err.error_id,
        "segmento": err.segmento,
        "lado": err.lado.value,
        "severidad": err.severidad.value,
        "puntos": puntos_de_segmento(err.segmento, err.lado.value),
        # qué medida disparó la regla y cuánto se pasó del umbral, para
        # señalar en pantalla el ángulo que no se cumple
        "angulos": angulos,
        "magnitud": magnitud,
        "direccion": err.direccion.value if err.direccion else None,
    }


#: Medidas que no son la terna de una articulación pero sí tienen un sitio en
#: el cuerpo donde mostrarlas: se dibujan en el más visible de esos puntos.
_UBICACION: Dict[str, Tuple[int, ...]] = {
    "cabeza_adelantada": (7, 8),        # cuello: en la oreja
    "cabeza_mirada": (0,),              # hacia dónde mira: en la nariz
    "alineacion_cuerpo_izq": (23,),     # línea hombro–cadera–tobillo: en la cadera
    "alineacion_cuerpo_der": (24,),
}


def _angulos(angulos: Optional[Mapping[str, float]],
             importantes: Sequence[str] = ()) -> Optional[Dict[str, Any]]:
    """Ángulos del frame para mostrarlos sobre el esqueleto.

    `articulaciones` lleva el índice del vértice (dónde dibujar) y si es uno de
    los ángulos que importan en el ejercicio; un ángulo bilateral («_medio»)
    marca los dos lados. `otros` son los ángulos importantes que no están en
    una articulación (tronco, pelvis…) y se muestran aparte.
    """
    if not angulos:
        return None
    marcados = set(importantes)
    for nombre, lados in ANGULOS_MEDIOS.items():
        if nombre in marcados:
            marcados.update(lados)
    articulaciones = []
    for nombre, (_, vertice, _) in ANGULOS_TERNA.items():
        if nombre in angulos:
            articulaciones.append({"nombre": nombre,
                                   "indices": [NOMBRES_MEDIAPIPE.index(vertice)],
                                   "grados": round(angulos[nombre]),
                                   "importante": nombre in marcados})
    for nombre, indices in _UBICACION.items():
        if nombre in angulos:
            articulaciones.append({"nombre": nombre, "indices": list(indices),
                                   "grados": round(angulos[nombre]),
                                   "importante": nombre in marcados})
    otros = [{"nombre": n, "grados": round(angulos[n])} for n in importantes
             if n in angulos and n not in ANGULOS_TERNA and n not in ANGULOS_MEDIOS
             and n not in _UBICACION]
    return {"articulaciones": articulaciones, "otros": otros}


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
        "feedback": feedback_a_dict(opcional("feedback")),
        "pausada": estado.pausada,
        "motivoPausa": estado.motivo_pausa,
        "puntos": _puntos(estado.landmarks),
        "angulos": _angulos(opcional("angulos"), opcional("angulos_importantes") or ()),
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


#: por qué terminó la sesión (lo pone el orquestador)
FIN_COMPLETADA, FIN_USUARIA, FIN_FUENTE, FIN_CIERRE, FIN_ERROR = (
    "completada", "usuaria", "fuente", "cierre", "error")


def resumen_a_dict(resumen: Mapping[str, Any], catalogo: Mapping[str, Ejercicio],
                   motivo_fin: Optional[str] = None) -> Dict[str, Any]:
    """`Sesion.resumen()` → resumen para la pantalla final (solo métricas derivadas).

    `motivo_fin`: completada (la rutina llegó al final), usuaria (pulsó
    terminar), fuente (el vídeo acabó o la cámara dejó de dar imagen), cierre
    (se cerró la ventana) o error."""
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
                          "errorId": m["error_id"], "segmento": m.get("segmento"),
                          "lado": m.get("lado"), "severidad": m.get("severidad"),
                          "repeticion": m["repeticion"]}
                         for m in p["mensajes"]],
            # veces que el motor no corrigió, por motivo (panel técnico)
            "abstenciones": dict(p.get("abstenciones", {})),
        })
    return {
        "rutina": resumen["rutina"],
        "terminada": resumen["terminada"],
        "motivoFin": motivo_fin,
        "duracionTotalS": round(sum(p["duracionS"] for p in pasos), 1),
        "pasos": pasos,
        "resumenTexto": resumen.get("resumen_texto"),
        # para el equipo (tecla D en el resumen), no para la usuaria
        "tecnico": {
            "frames": resumen.get("frames", 0),
            "framesSinPersona": resumen.get("frames_sin_persona", 0),
            "latencias": {etapa: {"p50Ms": v["p50_ms"], "p95Ms": v["p95_ms"], "n": v["n"]}
                          for etapa, v in resumen.get("latencias", {}).items()},
        },
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


__all__ = ["CAPACIDADES", "VERSION", "FIN_CIERRE", "FIN_COMPLETADA", "FIN_ERROR",
           "FIN_FUENTE", "FIN_USUARIA", "estado_a_dict", "feedback_a_dict", "info", "resumen_a_dict",
           "rutina_a_dict", "tipo_aviso"]
