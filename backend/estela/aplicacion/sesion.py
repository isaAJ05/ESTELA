"""Orquestador de la sesión en tiempo real.

Por frame:

    ResultadoPose ─► observacion_desde_pose ─► Segmentador (fase, repetición)
                 ─► AlineadorDTW (referencia; desactivable con `sin_dtw`)
                 ─► MotorFeedback (decisión determinista + plantilla) ─► voz

`Sesion` no sabe nada de cámaras ni de ventanas: recibe `(frame, t_ms)` y
devuelve un `EstadoFrame` para dibujar. Eso permite probar el flujo entero
con un estimador falso y reproducirlo con un vídeo.

Además del feedback de técnica (que decide solo el motor), la sesión emite
avisos de *operación*: qué ejercicio toca, cómo colocarse y cuándo se
termina. No son correcciones de movimiento, por eso no pasan por el motor.

Si la usuaria sale del encuadre o deja de hacer el ejercicio, el paso se
pausa (`pausa.DetectorPausa`): el motor no corrige, el tiempo del paso no
corre y los contadores se conservan hasta que retoma.

Con `registrar=True` la sesión guarda en memoria un registro por frame
(`Sesion.registro`) para las métricas del Informe 2: marca de tiempo, motivo
de silencio, latencias, mensaje y reglas disparadas. Incluye las medidas de la
observación (ángulos y distancias) para el jitter y la réplica del DTW; no
guarda imágenes ni landmarks, y el arnés no escribe las medidas a disco.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Deque, Dict, List, Mapping, Optional, Set, Tuple

import numpy as np

from ..dominio.feedback.contrato import ErrorTipificado, MensajeFeedback, Plano, Severidad, Silencio
from ..dominio.feedback.motor.decision import CALIDAD_CON_ERROR, CALIDAD_CORRECTA
from ..dominio.feedback.motor.geometria import observacion_desde_pose
from ..dominio.feedback.pipeline import MotorFeedback
from ..dominio.feedback.verbalizador.base import Verbalizador
from ..dominio.feedback.verbalizador.plantillas import VerbalizadorPlantillas

from ..dominio.conteo.segmentador import (EVENTO_COMPLETA, EVENTO_INCOMPLETA, EstadoSegmento,
                                          Segmentador, leer_senal)
from .dtw import CONFIANZA_MINIMA, Comparador, comparador_de_referencia
from .comandos_voz import puede_escuchar
from .gesto import DetectorGesto
from .metricas import Latencias
from .puertos import PRIORIDAD_AVISO, PRIORIDAD_FEEDBACK, Estimador, ResultadoPose, Voz
from .pausa import (EVENTO_PAUSA, EVENTO_REANUDA, INACTIVIDAD, SIN_PERSONA, USUARIA,
                    DetectorPausa)
from .reconocimiento import ReconocedorEjercicio, reconocedor_para
from .registro import RegistroRepeticiones
from .verbalizacion_aparte import VerbalizacionAparte
from .rutina import Ejercicio, Rutina

#: segundos seguidos mal orientada antes de avisar por voz, y separación
#: mínima entre dos avisos de orientación.
ORIENTACION_ESPERA_S = 2.0
ORIENTACION_REPETIR_S = 15.0
#: segundos sin persona antes de mostrar el aviso
SIN_PERSONA_S = 1.5
#: segundos con persona pero sin la señal del ejercicio (articulaciones fuera
#: del encuadre u ocluidas) antes de pedir que se aleje
SIN_SENAL_S = 2.0
AVISO_ENCUADRE = "Aléjate un poco: necesito verte el cuerpo entero."
AVISO_SIN_PERSONA = "No te veo: colócate dentro del encuadre."
AVISO_PAUSA = {SIN_PERSONA: "Pausa. No te veo: vuelve al encuadre para seguir.",
               INACTIVIDAD: "Pausa. Cuando quieras, sigue con el ejercicio.",
               USUARIA: "En pausa."}
AVISO_REANUDA = "Seguimos."
#: aviso de EXP-010: no nombra el ejercicio que parece, solo el que toca
AVISO_OTRO_EJERCICIO = "Ese movimiento no es el de ahora. Toca {nombre}."
#: milisegundos sosteniendo el movimiento equivocado antes de avisar
MOVIMIENTO_EQUIVOCADO_MS = 1000
#: `motivo_silencio` mientras suena un aviso (anuncio del ejercicio,
#: colocación...): la persona aún se está colocando y una corrección
#: esperaría en la cola a que acabe el aviso
MOTIVO_ANUNCIO = "anuncio"
#: Fase de colocación (T29): al empezar cada ejercicio no se cuenta ni se
#: corrige hasta que hay persona, la orientación es la del ejercicio y se ve
#: el cuerpo entero durante `COLOCACION_ESTABLE_MS` seguidos (o se pulsa
#: «Listo»). Una comprobación que falla reinicia la espera.
COLOCACION_ESTABLE_MS = 1500
AVISO_COLOCADA = "Ya te veo bien. Empieza cuando quieras."
#: cuerpo entero = de cada grupo se ve al menos un punto (de perfil, el lado
#: lejano puede quedar tapado): nariz, hombros, caderas, rodillas y tobillos
_CUERPO_ENTERO = ((0,), (11, 12), (23, 24), (25, 26), (27, 28))
_VISIBILIDAD_MINIMA = 0.5

_IDEAL = {Plano.FRONTAL: 0.0, Plano.SAGITAL: 90.0}
_COLOCACION = {Plano.FRONTAL: "Colócate de frente a la cámara.",
               Plano.SAGITAL: "Colócate de perfil a la cámara."}

log = logging.getLogger(__name__)


def aspecto_guia(referencia: Mapping[str, Any]) -> float:
    """Ancho/alto del vídeo de la referencia, si se guardó (`fuente.ancho`,
    `fuente.alto`); si no, 1. Los keypoints van normalizados a la imagen
    (x por el ancho, y por el alto), y la guía se dibuja en un cuadro 1×1:
    sin esta corrección, un vídeo vertical sale estirado a lo ancho."""
    fuente = referencia.get("fuente") or {}
    try:
        ancho, alto = float(fuente["ancho"]), float(fuente["alto"])
    except (KeyError, TypeError, ValueError):
        return 1.0
    return ancho / alto if ancho > 0 and alto > 0 else 1.0


def _preparar_guia(referencia: Optional[Mapping[str, Any]]
                   ) -> Tuple[Optional[np.ndarray], float]:
    if not referencia:
        return None, 30.0
    puntos = np.asarray(referencia.get("keypoints_2d", ()), dtype=np.float32)
    fps = float(referencia.get("fps", 30.0))
    if (puntos.ndim != 3 or puntos.shape[1:] != (33, 2)
            or puntos.shape[0] == 0 or not np.isfinite(fps) or fps <= 0):
        return None, 30.0
    validos = np.isfinite(puntos).all(axis=(0, 2))
    if not validos.all():
        return None, 30.0
    puntos = puntos * np.array([aspecto_guia(referencia), 1.0], dtype=np.float32)
    minimo = puntos.min(axis=(0, 1))
    maximo = puntos.max(axis=(0, 1))
    centro = (minimo + maximo) / 2.0
    escala = 0.76 / max(float(maximo[0] - minimo[0]),
                        float(maximo[1] - minimo[1]), 1e-6)
    puntos = (puntos - centro) * escala + 0.5
    guia = np.zeros((puntos.shape[0], 33, 4), dtype=np.float32)
    guia[:, :, :2] = puntos
    guia[:, :, 3] = 1.0
    return guia, fps


def _cuerpo_entero(imagen: Optional[np.ndarray]) -> bool:
    """Se ve al menos un punto de cada grupo de `_CUERPO_ENTERO`, dentro del
    frame y con visibilidad suficiente (landmarks de imagen, 0..1)."""
    if imagen is None:
        return False
    def visible(i: int) -> bool:
        x, y, vis = float(imagen[i, 0]), float(imagen[i, 1]), float(imagen[i, -1])
        return vis >= _VISIBILIDAD_MINIMA and 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0
    return all(any(visible(i) for i in grupo) for grupo in _CUERPO_ENTERO)


def _angulos_visibles(obs) -> Dict[str, float]:
    """Ángulos del frame para la interfaz, sin los de keypoints mal vistos.

    Con las piernas fuera de cuadro MediaPipe sigue devolviendo rodillas
    inventadas, y la abducción de cadera salía en pantalla con valores
    absurdos (-154°). Se usa el mismo corte que el DTW.
    """
    return {n: v for n, v in obs.angulos.items()
            if obs.confianza_de(n) >= CONFIANZA_MINIMA}


def _guia_actual(paso: _Paso, t_ms: int) -> Optional[np.ndarray]:
    if paso.guia is None or paso.inicio_ms is None:
        return None
    indice = int(max(0, t_ms - paso.inicio_ms) * paso.guia_fps / 1000.0)
    return paso.guia[indice % len(paso.guia)]


@dataclass(frozen=True)
class EstadoFrame:
    ejercicio: str
    ejercicio_id: str
    paso: int                          # 1-based
    total_pasos: int
    objetivo: int
    completadas: int
    incompletas: int
    fase: str
    persona: bool
    orientacion: Optional[float]
    aviso: Optional[str]
    ultimo_mensaje: Optional[str]
    landmarks: Optional[np.ndarray]    # (33, 4) de imagen, para dibujar
    latencia_ms: Dict[str, float]
    terminada: bool
    unidad: str = "repeticiones"       # o "segundos" en ejercicios isométricos
    pausada: bool = False
    motivo_pausa: Optional[str] = None  # pausa.SIN_PERSONA, INACTIVIDAD o USUARIA
    #: correcciones y refuerzos emitidos en toda la sesión; cambia cada vez que
    #: hay un `ultimo_mensaje` nuevo, aunque el texto se repita
    mensajes_emitidos: int = 0
    #: el `ultimo_mensaje` completo: qué error, segmento, lado y severidad
    #: (None en un refuerzo: `feedback.error` es None)
    feedback: Optional[MensajeFeedback] = None
    #: por qué el motor no habló en este frame (`feedback.contrato.MOTIVO_*`)
    motivo_silencio: Optional[str] = None
    #: ángulos medidos en este frame (grados), los mismos que usa el motor;
    #: solo para mostrarlos en la interfaz
    angulos: Optional[Dict[str, float]] = None
    #: el aviso es «ese movimiento no es el de ahora» (EXP-010) o el de
    #: `movimiento_equivocado` de la segmentación (p. ej. la otra pierna)
    otro_movimiento: bool = False
    #: los ángulos que importan en este ejercicio (`angulos_requeridos` de la skill)
    angulos_importantes: Tuple[str, ...] = ()
    #: postura de referencia del frame actual, en formato (33, 4)
    guia: Optional[np.ndarray] = None
    #: repeticiones (o segundos, en la plancha) correctas y con error según
    #: el motor, aunque no se dijera nada (T29.a); las no evaluadas no suman
    correctas: Optional[int] = None
    con_error: Optional[int] = None
    #: fase de colocación: qué hacer y qué se cumple ya
    #: (persona, orientacion, cuerpo_entero)
    colocando: bool = False
    instruccion: Optional[str] = None
    comprobaciones: Optional[Dict[str, bool]] = None
    #: gesto de pausa en curso (brazo derecho arriba, `gesto.py`):
    #: {"progreso": 0–1, "accion": "pausar" | "reanudar"}, o None
    gesto: Optional[Dict[str, Any]] = None
    #: órdenes de voz (`comandos_voz.py`): {"activa": bool, "texto": str | None,
    #: "comando": str | None, "noEntendi": bool}, o None sin voz de entrada
    escucha: Optional[Dict[str, Any]] = None
    #: indicador del micrófono: {"encendido": bool, "escuchando": bool, "atenta": bool},
    #: o None sin voz de entrada. `atenta`: oyó «Estela» y espera la orden
    microfono: Optional[Dict[str, Any]] = None


class _SaltoCadera:
    """Añade `salto_cadera` a la observación: cuánto sube la cadera sobre el
    suelo, en longitudes de tronco. Los landmarks de mundo tienen la cadera de
    origen, así que solo la imagen (y hacia abajo) ve un salto. El suelo es el
    percentil 20 de la altura de los últimos `VENTANA_MS`: en saltos seguidos
    los pies pisan el suelo al menos una parte del tiempo."""
    VENTANA_MS = 3000

    def __init__(self) -> None:
        self._historial: Deque[Tuple[int, float]] = deque()

    def aplicar(self, obs, imagen):
        if imagen is None:
            return obs
        hombros, caderas = imagen[[11, 12]], imagen[[23, 24]]
        tronco = abs(float(caderas[:, 1].mean() - hombros[:, 1].mean()))
        if tronco < 1e-6:
            return obs
        altura = -float(caderas[:, 1].mean()) / tronco
        self._historial.append((obs.t_ms, altura))
        while obs.t_ms - self._historial[0][0] > self.VENTANA_MS:
            self._historial.popleft()
        suelo = float(np.percentile([a for _, a in self._historial], 20))
        conf = float(min(hombros[:, 3].min(), caderas[:, 3].min()))
        return replace(obs, distancias={**obs.distancias, "salto_cadera": altura - suelo},
                       confianza={**obs.confianza, "salto_cadera": conf})


@dataclass
class _Paso:
    ejercicio: Ejercicio
    objetivo: int
    motor: MotorFeedback
    segmentador: Segmentador
    inicio_ms: Optional[int] = None
    fin_ms: Optional[int] = None
    seg: Optional[EstadoSegmento] = None
    mensajes: List[Dict[str, Any]] = field(default_factory=list)
    pausa: DetectorPausa = field(default_factory=DetectorPausa)
    alineador: Optional[Comparador] = None
    registro: Optional[RegistroRepeticiones] = None
    guia: Optional[np.ndarray] = None
    guia_fps: float = 30.0
    equivocado_desde: Optional[int] = None
    ult_aviso_equivocado_ms: Optional[int] = None
    salto: _SaltoCadera = field(default_factory=_SaltoCadera)
    #: EXP-010: ¿está haciendo este ejercicio? None si no hay referencias
    reconocedor: Optional[ReconocedorEjercicio] = None
    ult_aviso_otro_ms: Optional[int] = None
    #: unidades completadas por repetición del motor: 1 por repetición, o los
    #: segundos de cada bloque en un ejercicio isométrico
    unidades: Dict[int, int] = field(default_factory=dict)
    colocando: bool = False
    #: desde cuándo se cumplen las tres comprobaciones sin interrupción
    colocado_desde: Optional[int] = None
    comprobaciones: Dict[str, bool] = field(default_factory=lambda: {
        "persona": False, "orientacion": False, "cuerpo_entero": False})


class Sesion:
    def __init__(self, rutina: Rutina, catalogo: Mapping[str, Ejercicio],
                 estimador: Estimador, voz: Voz,
                 verbalizador: Optional[Verbalizador] = None,
                 sin_dtw: bool = False, reconocer: bool = False,
                 registrar: bool = False, colocacion: bool = False,
                 al_cerrar_paso: Optional[Callable[[Dict[str, Any]], None]] = None,
                 retencion_max_ms: int = 0, verbalizar_aparte: bool = False) -> None:
        self.rutina = rutina
        self.catalogo = catalogo
        self.estimador = estimador
        self.voz = voz
        self.verbalizador = verbalizador or VerbalizadorPlantillas()
        #: `verbalizar_aparte` con un verbalizador lento (el LLM, que tiene
        #: `fallback`): el motor usa la plantilla al momento y el LLM redacta en
        #: otro hilo (`VerbalizacionAparte`); el bucle por imagen no lo espera.
        respaldo = getattr(self.verbalizador, "fallback", None)
        self._aparte: Optional[VerbalizacionAparte] = None
        self._verbalizador_motor: Verbalizador = self.verbalizador
        if verbalizar_aparte and respaldo is not None:
            self._aparte = VerbalizacionAparte(self.verbalizador, self._al_redactar)
            self._verbalizador_motor = respaldo
        #: correcciones redactadas que llegaron cuando ya no tocaba decirlas
        self.redactadas_tarde = 0
        self._cerrojo_mensajes = threading.Lock()
        self.sin_dtw = sin_dtw
        #: aviso «ese movimiento no es el de ahora» (EXP-010). Desactivado por
        #: defecto hasta medirlo con vídeos propios; se cambia en plena sesión
        #: con `activar_reconocimiento`.
        self.reconocer = reconocer
        #: fase de colocación al empezar cada ejercicio (la aplicación la
        #: activa; las pruebas y el arnés del Informe 2 empiezan a contar ya)
        self.colocacion = colocacion
        self.registrar = registrar
        #: un dict por frame (solo con `registrar`); ver `_registra`
        self.registro: List[Dict[str, Any]] = []
        self.latencias = Latencias()
        self.frames = 0
        self.frames_sin_persona = 0
        self._pasos: List[_Paso] = []
        self._i = -1
        self._ultimo_mensaje: Optional[str] = None
        self._ultimo_feedback: Optional[MensajeFeedback] = None
        self._mensajes_emitidos = 0
        self._ult_persona_ms: Optional[int] = None
        self._mal_orientada_desde: Optional[int] = None
        self._ult_aviso_orient_ms: Optional[int] = None
        self._ult_senal_ms: Optional[int] = None
        self._ult_aviso_encuadre_ms: Optional[int] = None
        self._t_ms = 0
        self._gesto = DetectorGesto()
        #: Entrenadora (entre ejercicios y al final, nunca durante el
        #: movimiento). `al_cerrar_paso` recibe un dict al cerrar cada paso
        #: hacia delante: `turno`, `paso` (su resumen), `siguiente` (skill_id o
        #: None), `final`, `retenida` y, al final, `pasos`. No debe bloquear:
        #: quien lo atiende trabaja en otro hilo y al acabar llama a
        #: `soltar_entrenadora(turno)`. Con colocación activa y
        #: `retencion_max_ms` > 0, el ejercicio siguiente no empieza a contar
        #: hasta entonces, o hasta que pasen esos milisegundos.
        self.al_cerrar_paso = al_cerrar_paso
        self.retencion_max_ms = retencion_max_ms
        #: Voz de entrada (opcional): objeto con `estado()` → dict para
        #: `EstadoFrame.escucha`. La sesión solo lo muestra; quien escucha
        #: pregunta `puede_escuchar` y manda las órdenes por el camino de siempre.
        self.oyente: Any = None
        #: modo «llamada» de la voz de entrada: se escucha también durante el
        #: ejercicio (la escucha lo activa en `conectar`)
        self.escucha_siempre = False
        #: modo «interrumpir»: también se escucha mientras ESTELA habla, para poder
        #: cortarla con la voz (la escucha lo activa en `conectar`)
        self.escucha_hablando = False
        self._turno = 0
        self._retenida = False
        self._retencion_desde: Optional[int] = None
        self._anuncio_pendiente: Optional[str] = None
        #: lo que dice la entrenadora, para leerlo en la capa de colocación
        self._texto_entrenadora: Optional[str] = None
        self._cerrojo_retencion = threading.Lock()
        self._avanzar()

    # -- rutina -------------------------------------------------------------

    @property
    def terminada(self) -> bool:
        return self._i >= len(self.rutina.pasos)

    @property
    def paso_actual(self) -> Optional[_Paso]:
        if self._i < 0 or self.terminada:
            return None
        return self._pasos[self._i]

    def _avanzar(self) -> None:
        self._ir_a(self._i + 1, felicitar=True)

    def _ir_a(self, i: int, felicitar: bool) -> None:
        """Cierra el paso actual y empieza el paso `i` de la rutina desde cero.
        Si ese paso ya se había hecho (se volvió con `anterior`), el intento
        nuevo sustituye al anterior en el resumen. `felicitar`: el paso se
        terminó de verdad (no se saltó); solo entonces se felicita y habla la
        entrenadora, que si no resumiría un ejercicio a medias."""
        actual = self.paso_actual
        cierre: Optional[Dict[str, Any]] = None
        if actual is not None:
            actual.fin_ms = self._t_ms
            actual.motor.decision.cerrar_repeticion()
            if actual.registro is not None:
                actual.registro.cerrar(self._t_ms)
            if self.al_cerrar_paso is not None and i > self._i and felicitar:
                cierre = self._resumen_paso(actual)
            if felicitar:
                self.voz.decir(f"Muy bien, terminaste {actual.ejercicio.skill.nombre.lower()}.",
                               PRIORIDAD_AVISO)
        self._i = i
        self._gesto.reiniciar()
        with self._cerrojo_retencion:
            self._turno += 1
            self._retenida = False
            self._retencion_desde = None
            self._anuncio_pendiente = None
            self._texto_entrenadora = None
        if self.terminada:
            self.voz.decir("Rutina terminada. Buen trabajo.", PRIORIDAD_AVISO)
            self._avisa_cierre(cierre, None)
            return
        p = self.rutina.pasos[self._i]
        ej = self.catalogo[p.skill_id]
        guia, guia_fps = _preparar_guia(ej.referencia)
        nuevo = _Paso(ej, p.repeticiones,
                      MotorFeedback(ej.skill, self._verbalizador_motor),
                      ej.nuevo_segmentador(),
                      alineador=(None if self.sin_dtw
                                 else comparador_de_referencia(ej.referencia)),
                      registro=RegistroRepeticiones(ej),
                      guia=guia, guia_fps=guia_fps,
                      reconocedor=(reconocedor_para(ej.skill.clase_reconocimiento)
                                   if self.reconocer else None),
                      colocando=self.colocacion)
        if self._i < len(self._pasos):
            self._pasos[self._i] = nuevo
        else:
            self._pasos.append(nuevo)
        self._mal_orientada_desde = None
        self._ult_aviso_orient_ms = None
        self._ult_senal_ms = None
        anuncio = self._anuncio(ej, p.repeticiones)
        if cierre is not None and nuevo.colocando and self.retencion_max_ms > 0:
            # la entrenadora habla primero; el anuncio sale al soltar la retención
            self._anuncio_pendiente = anuncio
            self._retenida = True
        else:
            self.voz.decir(anuncio, PRIORIDAD_AVISO)
        self._avisa_cierre(cierre, p.skill_id)

    def _avisa_cierre(self, cierre: Optional[Dict[str, Any]],
                      siguiente: Optional[str]) -> None:
        if cierre is None or self.al_cerrar_paso is None:
            return
        final = self.terminada
        evento = {"turno": self._turno, "paso": cierre, "siguiente": siguiente,
                  "final": final, "retenida": self._retenida,
                  "pasos": [self._resumen_paso(x) for x in self._pasos] if final else None}
        try:
            self.al_cerrar_paso(evento)
        except Exception:                                 # noqa: BLE001
            log.exception("fallo al avisar del cierre del paso")
            self.soltar_entrenadora(evento["turno"])

    @property
    def puede_escuchar(self) -> bool:
        """¿Se pueden oír órdenes de voz ahora? Por defecto solo en pausa o
        entre ejercicios (colocación); con `escucha_siempre`, también durante
        el ejercicio. Nunca mientras suena la voz de ESTELA
        (`comandos_voz.puede_escuchar`), salvo con `escucha_hablando`. Se puede leer desde otro hilo."""
        p = self.paso_actual
        if p is None:
            return False
        return puede_escuchar(en_pausa=p.pausa.pausada, colocando=p.colocando,
                              hablando=(not self.escucha_hablando
                                        and bool(getattr(self.voz, "ocupada", False))),
                              terminada=self.terminada, siempre=self.escucha_siempre)

    @property
    def hay_siguiente(self) -> bool:
        return self._i < len(self.rutina.pasos) - 1

    @property
    def hay_anterior(self) -> bool:
        return 0 < self._i < len(self.rutina.pasos)

    @property
    def entre_ejercicios(self) -> bool:
        """En la colocación de un ejercicio que no es el primero."""
        p = self.paso_actual
        return p is not None and p.colocando and self._i > 0

    def resumen_ligero(self) -> List[Dict[str, Any]]:
        """Cuentas de los pasos hechos hasta ahora, para «¿cómo voy?». Solo
        lee (no cierra registros), así que se puede llamar desde otro hilo."""
        pasos = []
        for p in list(self._pasos):
            seg = p.seg
            pasos.append({
                "skill_id": p.ejercicio.skill.skill_id, "objetivo": p.objetivo,
                "unidad": p.ejercicio.unidad,
                "completadas": seg.completadas if seg else 0,
                "incompletas": seg.incompletas if seg else 0,
                "pausas_sesion": p.pausa.veces, "mensajes": list(p.mensajes),
                "duracion_s": 0.0,
            })
        return pasos

    def entrenadora_vigente(self, turno: int) -> bool:
        """¿Sigue siendo el momento de que hable la entrenadora de `turno`?
        Solo mientras la colocación siga retenida o la rutina haya terminado:
        nunca con el ejercicio en marcha. Se puede llamar desde otro hilo."""
        return turno == self._turno and (self._retenida or self.terminada)

    def mostrar_entrenadora(self, turno: int, texto: str) -> bool:
        """Pone en pantalla lo que la entrenadora va a decir (en el lugar de la
        instrucción de colocación) mientras dure la retención. False si ya no
        es su momento. Se puede llamar desde otro hilo."""
        with self._cerrojo_retencion:
            if turno != self._turno or not self._retenida:
                return False
            self._texto_entrenadora = texto
            return True

    def soltar_entrenadora(self, turno: int) -> None:
        """La entrenadora de `turno` terminó (o falló): se anuncia el
        ejercicio y la colocación puede acabar. Se puede llamar desde otro
        hilo; un turno viejo no hace nada."""
        with self._cerrojo_retencion:
            if turno != self._turno or not self._retenida:
                return
            self._retenida = False
            self._texto_entrenadora = None
            anuncio, self._anuncio_pendiente = self._anuncio_pendiente, None
            # El tiempo de colocación estable vuelve a contar: si la persona ya
            # estaba bien colocada, «Ya te veo bien» se encolaría justo detrás
            # del anuncio y lo sustituiría antes de sonar (un solo hueco).
            p = self.paso_actual
            if p is not None:
                p.colocado_desde = None
        if anuncio:
            self.voz.decir(anuncio, PRIORIDAD_AVISO)

    @staticmethod
    def _anuncio(ej: Ejercicio, reps: int) -> str:
        colocacion = _COLOCACION.get(ej.skill.orientacion_preferida, "")
        return f"Ahora, {ej.skill.nombre.lower()}. {reps} {ej.unidad}. {colocacion}".strip()

    def terminar_colocacion(self) -> None:
        """Da por terminada la colocación (botón «Listo» de la interfaz)."""
        p = self.paso_actual
        if p is not None and p.colocando:
            self.soltar_entrenadora(self._turno)     # «Listo» también corta la espera
            self._fin_colocacion(p, self._t_ms)

    def _fin_colocacion(self, p: _Paso, t_ms: int) -> None:
        p.colocando = False
        p.inicio_ms = t_ms               # la duración cuenta desde aquí
        self._mal_orientada_desde = None
        self._ult_senal_ms = None
        self.voz.decir(AVISO_COLOCADA, PRIORIDAD_AVISO)

    def _coloca(self, p: _Paso, skill, res: ResultadoPose, obs, t_ms: int
                ) -> Optional[str]:
        """Un frame de la fase de colocación. Devuelve el aviso que mostrar."""
        orientacion = self._orientacion_ok(skill, obs.orientacion)
        cuerpo = _cuerpo_entero(res.imagen)
        p.comprobaciones = {"persona": True, "orientacion": orientacion,
                            "cuerpo_entero": cuerpo}
        aviso = (self._revisa_orientacion(skill, obs.orientacion, t_ms)
                 or self._revisa_encuadre(cuerpo, t_ms))
        if not (orientacion and cuerpo):
            p.colocado_desde = None
            return aviso
        if p.colocado_desde is None:
            p.colocado_desde = t_ms
        if t_ms - p.colocado_desde >= COLOCACION_ESTABLE_MS and not self._retenida:
            self._fin_colocacion(p, t_ms)
        return None

    def siguiente(self) -> None:
        """Salta al siguiente ejercicio (tecla, botón u orden de voz). En el
        último no hace nada: para acabar está «Terminar». Es un salto, no un
        ejercicio terminado: ni «Muy bien, terminaste…» ni resumen de la
        entrenadora: resumiría un ejercicio a medias (Paula, 2026-11-17: al
        pasar de ejercicio por voz «se inventa cosas que hice»)."""
        if self._i < len(self.rutina.pasos) - 1:
            self._ir_a(self._i + 1, felicitar=False)

    def anterior(self) -> None:
        """Vuelve al ejercicio anterior y lo empieza desde cero. En el primero
        no hace nada."""
        if 0 < self._i < len(self.rutina.pasos):
            self._ir_a(self._i - 1, felicitar=False)

    def reiniciar_ejercicio(self) -> None:
        p = self.paso_actual
        if p is not None:
            p.motor.reiniciar()
            p.segmentador.reiniciar()
            p.seg = None
            p.unidades.clear()
            if p.alineador is not None:
                p.alineador.reiniciar()

    def reiniciar_sesion(self) -> None:
        """Vuelve al primer ejercicio y borra lo hecho: el resumen final solo
        trae los ejercicios del intento nuevo."""
        if self.terminada:
            return
        self._ir_a(0, felicitar=False)
        del self._pasos[1:]

    def pausar(self) -> None:
        """Pausa pedida por la usuaria: no se cuenta ni se corrige hasta que
        llame a `reanudar` (no se retoma sola)."""
        p = self.paso_actual
        if p is not None:
            self._anuncia_pausa(p, p.pausa.pausar_usuaria(self._t_ms))

    def reanudar(self) -> None:
        p = self.paso_actual
        if p is not None:
            self._anuncia_pausa(p, p.pausa.reanudar_usuaria(self._t_ms))

    def activar_reconocimiento(self, activo: bool) -> None:
        """Enciende o apaga el aviso de EXP-010 desde la interfaz. Al
        encenderlo, el reconocedor empieza de cero (con su calentamiento)."""
        self.reconocer = activo
        p = self.paso_actual
        if p is None:
            return
        p.reconocedor = reconocedor_para(p.ejercicio.skill.clase_reconocimiento) if activo else None
        p.ult_aviso_otro_ms = None

    # -- bucle --------------------------------------------------------------

    def procesar(self, frame: np.ndarray, t_ms: int) -> EstadoFrame:
        t_ini = time.perf_counter()
        self._t_ms = t_ms
        self.frames += 1
        p = self.paso_actual
        if p is None:
            return self._estado(None, None, None, {})
        if p.inicio_ms is None:
            p.inicio_ms = t_ms
        if self._retenida:
            # tope de la espera a la entrenadora: pasado, el ejercicio sigue
            if self._retencion_desde is None:
                self._retencion_desde = t_ms
            elif t_ms - self._retencion_desde > self.retencion_max_ms:
                self.soltar_entrenadora(self._turno)

        # imagen sin evaluación: el estimador puede hacer aquí lo que sea lento
        # (renovar el detector con GPU, `adaptadores/pose/estimador.py`)
        libre = getattr(self.estimador, "momento_libre", None)
        if libre is not None and (p.colocando or p.pausa.pausada
                                  or getattr(self.voz, "anunciando", False)):
            libre()
        res = self.estimador.estimar(frame, t_ms)
        self.latencias.anota("pose", res.latencia_ms)
        lat = {"pose": res.latencia_ms}

        # brazo derecho arriba 3 s: pausa o reanuda (también la pausa a mano).
        # En la colocación no pausa: aún no se cuenta nada, y colocarse (o
        # estirarse) con el brazo arriba la pausaba sin querer (vídeo de zancada
        # derecha, 2026-11-20). Sí reanuda si ya estaba en pausa.
        if p.colocando and not p.pausa.pausada:
            self._gesto.reiniciar()
        elif self._gesto.actualizar(t_ms, res.imagen if res.muestra is not None else None):
            self._anuncia_pausa(p, p.pausa.reanudar_gesto(t_ms) if p.pausa.pausada
                                else p.pausa.pausar_usuaria(t_ms))

        if p.pausa.motivo == USUARIA:
            # en pausa a mano solo se dibuja el esqueleto
            if res.muestra is None:
                self.frames_sin_persona += 1
            self._registra(p, t_ms, lat)
            return self._estado(p, res if res.muestra is not None else None,
                                AVISO_PAUSA[USUARIA], lat)
        if res.muestra is None and p.colocando:
            # colocándose es normal salir del encuadre: ni pausa ni aviso
            self.frames_sin_persona += 1
            p.colocado_desde = None
            p.comprobaciones = {"persona": False, "orientacion": False,
                                "cuerpo_entero": False}
            self._registra(p, t_ms, lat)
            return self._estado(p, None, None, lat)
        if res.muestra is None:
            self.frames_sin_persona += 1
            p.segmentador.interrumpir()
            self._anuncia_pausa(p, p.pausa.actualizar(t_ms, persona=False))
            aviso = None
            if p.pausa.pausada:
                aviso = AVISO_PAUSA[p.pausa.motivo]
            elif (self._ult_persona_ms is None
                    or t_ms - self._ult_persona_ms > SIN_PERSONA_S * 1000):
                aviso = AVISO_SIN_PERSONA
            self._registra(p, t_ms, lat)
            return self._estado(p, None, aviso, lat)
        self._ult_persona_ms = t_ms

        skill = p.ejercicio.skill
        t0 = time.perf_counter()
        obs = observacion_desde_pose(res.muestra, skill.skill_id)
        obs = p.salto.aplicar(obs, res.imagen)
        t1 = time.perf_counter()
        if p.colocando:
            lat["geometria"] = (t1 - t0) * 1000
            self.latencias.anota("geometria", lat["geometria"])
            aviso = self._coloca(p, skill, res, obs, t_ms)
            self._registra(p, t_ms, lat, obs=obs)
            return self._estado(p, res, aviso, lat, obs.orientacion,
                                angulos=_angulos_visibles(obs))
        seg = p.segmentador.actualizar(obs)
        p.seg = seg
        if seg.evento == EVENTO_COMPLETA and seg.repeticion:
            p.unidades[seg.repeticion] = p.unidades.get(seg.repeticion, 0) + 1
        obs = replace(obs, fase=seg.fase, repeticion=seg.repeticion)
        t2 = time.perf_counter()
        lat.update(geometria=(t1 - t0) * 1000, segmentacion=(t2 - t1) * 1000)
        dtw = None
        if p.alineador is not None:
            t_dtw = time.perf_counter()
            dtw = p.alineador.actualizar(obs)
            if dtw is not None:
                obs = replace(obs, angulos_ref=dtw.angulos_ref, sigma_ref=dtw.sigma_ref,
                              progreso=dtw.progreso, coste_dtw=dtw.coste)
            lat["dtw"] = (time.perf_counter() - t_dtw) * 1000
        if p.registro is not None:
            p.registro.actualizar(obs, seg)
        otro_ejercicio = False
        if p.reconocedor is not None:
            t_rec = time.perf_counter()
            otro_ejercicio = p.reconocedor.actualizar(
                obs, seg.evento in (EVENTO_COMPLETA, EVENTO_INCOMPLETA))
            lat["reconocimiento"] = (time.perf_counter() - t_rec) * 1000

        # La inactividad se vigila desde la primera repetición (o el primer
        # bloque en posición) y solo con señal válida: sin señal, el problema
        # es el encuadre y lo avisa `_revisa_encuadre`.
        progreso = ((seg.fase, seg.repeticion, seg.completadas, seg.incompletas)
                    if seg.repeticion > 0 and seg.senal_valida else None)
        self._anuncia_pausa(p, p.pausa.actualizar(
            t_ms, True, progreso, self._orientacion_ok(skill, obs.orientacion),
            otro_ejercicio), callar_reanudacion=otro_ejercicio)
        if p.pausa.pausada:
            for etapa in ("geometria", "segmentacion", "dtw", "reconocimiento"):
                if etapa not in lat:
                    continue
                self.latencias.anota(etapa, lat[etapa])
            aviso = (self._revisa_orientacion(skill, obs.orientacion, t_ms)
                     or self._revisa_encuadre(seg.senal_valida, t_ms)
                     or AVISO_PAUSA[p.pausa.motivo])
            self._registra(p, t_ms, lat, obs=obs, seg=seg, dtw=dtw)
            return self._estado(p, res, aviso, lat, obs.orientacion,
                               angulos=_angulos_visibles(obs))

        if getattr(self.voz, "anunciando", False):
            salida = Silencio(MOTIVO_ANUNCIO, t_ms)
        else:
            t2 = time.perf_counter()
            salida = p.motor.procesar(obs)
            t3 = time.perf_counter()
            lat["motor"] = (t3 - t2) * 1000
            # El pipeline ya separa decisión (motor determinista) y verbalización
            # (plantilla o LLM); la verbalización solo existe si hubo mensaje.
            lat["decision"] = p.motor.ultimos_tiempos.decision_ms
            # con la redacción aparte, su tiempo lo anota `_al_redactar`
            if isinstance(salida, MensajeFeedback) and (self._aparte is None
                                                        or salida.error is None):
                lat["verbalizacion"] = p.motor.ultimos_tiempos.verbalizacion_ms
        for etapa in ("geometria", "segmentacion", "dtw", "reconocimiento",
                      "motor", "decision", "verbalizacion"):
            if etapa not in lat:
                continue
            self.latencias.anota(etapa, lat[etapa])

        if isinstance(salida, MensajeFeedback):
            if self._aparte is not None and salida.error is not None:
                self._aparte.pedir((p, seg.repeticion, t_ms), salida.error)
            else:
                self._emitir(p, salida, seg.repeticion, t_ms)

        aviso = (self._revisa_orientacion(skill, obs.orientacion, t_ms)
                 or self._revisa_encuadre(seg.senal_valida, t_ms))
        otro_movimiento = False
        if aviso is None:
            aviso = (self._revisa_movimiento_equivocado(p, obs, seg, t_ms)
                     or self._revisa_otro_ejercicio(p, otro_ejercicio, t_ms))
            otro_movimiento = aviso is not None
        estado = self._estado(p, res, aviso, lat, obs.orientacion,
                              salida.motivo if isinstance(salida, Silencio) else None,
                              angulos=_angulos_visibles(obs),
                              otro_movimiento=otro_movimiento)

        if seg.evento == EVENTO_COMPLETA and seg.completadas >= p.objetivo:
            self._avanzar()
        lat["total"] = (time.perf_counter() - t_ini) * 1000
        self.latencias.anota("total", lat["total"])
        self._registra(p, t_ms, lat, obs=obs, seg=seg, dtw=dtw, salida=salida)
        return estado

    def _emitir(self, p: _Paso, salida: MensajeFeedback, repeticion: int, t_ms: int) -> None:
        """Muestra y dice una corrección o un refuerzo. Puede llamarse desde el
        hilo de `VerbalizacionAparte`."""
        with self._cerrojo_mensajes:
            self._ultimo_mensaje = salida.texto
            self._ultimo_feedback = salida
            self._mensajes_emitidos += 1
            self.voz.decir(salida.texto, PRIORIDAD_FEEDBACK)
            err = salida.error
            p.mensajes.append({"t_ms": t_ms, "texto": salida.texto,
                               "error_id": err.error_id if err else None,
                               "segmento": err.segmento if err else None,
                               "lado": err.lado.value if err else None,
                               "severidad": err.severidad.value if err else None,
                               "repeticion": repeticion})

    def _al_redactar(self, clave: Tuple[Any, int, int], msg: MensajeFeedback,
                     ms: float) -> None:
        """Vuelve una corrección redactada aparte. Se dice solo si sigue el
        mismo ejercicio y en marcha (no en pausa, ni colocándose)."""
        p, repeticion, t_ms = clave
        self.latencias.anota("verbalizacion", ms)
        if p is not self.paso_actual or p.pausa.pausada or p.colocando:
            self.redactadas_tarde += 1
            return
        self._emitir(p, msg, repeticion, t_ms)

    def cerrar(self) -> None:
        """Para el hilo de la redacción aparte, si lo hay."""
        if self._aparte is not None:
            self._aparte.cerrar()

    def _registra(self, p: _Paso, t_ms: int, lat: Dict[str, float],
                  obs=None, seg: Optional[EstadoSegmento] = None, dtw=None,
                  salida=None) -> None:
        """Una entrada de `registro` por frame. Sin persona: `persona` False.
        En pausa o durante un aviso (`MOTIVO_ANUNCIO`) el motor no se llamó
        (`evaluado` False)."""
        if not self.registrar:
            return
        evaluado = (salida is not None
                    and getattr(salida, "motivo", None) != MOTIVO_ANUNCIO)
        mensaje = None
        if isinstance(salida, MensajeFeedback):
            err = salida.error
            mensaje = {"texto": salida.texto, "refuerzo": err is None,
                       "error_id": err.error_id if err else None,
                       "segmento": err.segmento if err else None,
                       "lado": err.lado.value if err else None,
                       "severidad": err.severidad.value if err else None,
                       "fallback": salida.fallback}
        self.registro.append({
            "t_ms": t_ms,
            "skill_id": p.ejercicio.skill.skill_id,
            "persona": obs is not None,
            "pausada": p.pausa.pausada,
            "motivo_pausa": p.pausa.motivo,
            "evaluado": evaluado,
            "motivo_silencio": salida.motivo if isinstance(salida, Silencio) else None,
            "mensaje": mensaje,
            "disparadas": list(p.motor.decision.disparadas) if evaluado else [],
            "repeticion": seg.repeticion if seg else None,
            "fase": seg.fase if seg else None,
            "senal_valida": seg.senal_valida if seg else None,
            "completadas": seg.completadas if seg else None,
            "dtw": ({"progreso": dtw.progreso, "coste": dtw.coste}
                    if dtw is not None else None),
            "lat": dict(lat),
            # solo en memoria: el arnés no las escribe a disco
            "medidas": ({"angulos": dict(obs.angulos),
                         "distancias": dict(obs.distancias),
                         "confianza": dict(obs.confianza)}
                        if obs is not None else None),
        })

    def _anuncia_pausa(self, p: _Paso, evento: Optional[str],
                       callar_reanudacion: bool = False) -> None:
        """`callar_reanudacion`: la pausa por inactividad se quitó porque
        está haciendo otro ejercicio; «Seguimos» no tocaría, solo el aviso de
        `_revisa_otro_ejercicio`."""
        if evento == EVENTO_PAUSA:
            self.voz.decir(AVISO_PAUSA[p.pausa.motivo], PRIORIDAD_AVISO)
        elif evento == EVENTO_REANUDA:
            p.segmentador.interrumpir()
            self._mal_orientada_desde = None
            self._ult_senal_ms = None
            if not callar_reanudacion:
                self.voz.decir(AVISO_REANUDA, PRIORIDAD_AVISO)

    @staticmethod
    def _orientacion_ok(skill, orientacion: Optional[float]) -> bool:
        """Sin orientación medible o sin preferencia, no se bloquea nada."""
        ideal = _IDEAL.get(skill.orientacion_preferida)
        if ideal is None or orientacion is None:
            return True
        return abs(orientacion - ideal) <= skill.politica.tolerancia_orientacion_grados

    def _revisa_orientacion(self, skill, orientacion: Optional[float],
                            t_ms: int) -> Optional[str]:
        if self._orientacion_ok(skill, orientacion):
            self._mal_orientada_desde = None
            return None
        if self._mal_orientada_desde is None:
            self._mal_orientada_desde = t_ms
        texto = _COLOCACION[skill.orientacion_preferida]
        if (t_ms - self._mal_orientada_desde >= ORIENTACION_ESPERA_S * 1000
                and (self._ult_aviso_orient_ms is None
                     or t_ms - self._ult_aviso_orient_ms >= ORIENTACION_REPETIR_S * 1000)):
            self._ult_aviso_orient_ms = t_ms
            self.voz.decir(texto, PRIORIDAD_AVISO)
        return texto

    def _revisa_movimiento_equivocado(self, p: _Paso, obs, seg: EstadoSegmento,
                                      t_ms: int) -> Optional[str]:
        """Aviso de operación, no corrección de técnica: la usuaria hace otro
        movimiento (p. ej. sube la pierna derecha cuando toca la izquierda).

        Se configura en la segmentación del skill con `movimiento_equivocado`
        ({senal, min y/o max, aviso}) y solo se mira mientras el ejercicio está
        en reposo, sostenido `MOVIMIENTO_EQUIVOCADO_MS`. EXP-009.
        """
        conf = (p.ejercicio.segmentacion or {}).get("movimiento_equivocado")
        fases = (p.ejercicio.segmentacion or {}).get("fases") or ()
        if not conf or not fases or seg.fase != fases[0]:
            p.equivocado_desde = None
            return None
        v = leer_senal(obs, conf["senal"], 0.5)
        if v is None or not ((conf.get("min") is None or v >= conf["min"])
                             and (conf.get("max") is None or v <= conf["max"])):
            p.equivocado_desde = None
            return None
        if p.equivocado_desde is None:
            p.equivocado_desde = t_ms
        if t_ms - p.equivocado_desde < MOVIMIENTO_EQUIVOCADO_MS:
            return None
        if (p.ult_aviso_equivocado_ms is None
                or t_ms - p.ult_aviso_equivocado_ms >= ORIENTACION_REPETIR_S * 1000):
            p.ult_aviso_equivocado_ms = t_ms
            self.voz.decir(conf["aviso"], PRIORIDAD_AVISO)
        return conf["aviso"]

    def _revisa_otro_ejercicio(self, p: _Paso, otro: bool, t_ms: int) -> Optional[str]:
        """Aviso de operación de EXP-010: lleva `reconocimiento.SOSTENIDO_MS`
        haciendo algo que no es el ejercicio elegido. No dice qué parece."""
        if not otro:
            return None
        texto = self._aviso_otro(p.ejercicio)
        if (p.ult_aviso_otro_ms is None
                or t_ms - p.ult_aviso_otro_ms >= ORIENTACION_REPETIR_S * 1000):
            p.ult_aviso_otro_ms = t_ms
            self.voz.decir(texto, PRIORIDAD_AVISO)
        return texto

    @staticmethod
    def _aviso_otro(ej: Ejercicio) -> str:
        return AVISO_OTRO_EJERCICIO.format(nombre=ej.skill.nombre.lower())

    def _revisa_encuadre(self, senal_valida: bool, t_ms: int) -> Optional[str]:
        if senal_valida or self._ult_senal_ms is None:
            self._ult_senal_ms = t_ms
            return None
        if t_ms - self._ult_senal_ms < SIN_SENAL_S * 1000:
            return None
        if (self._ult_aviso_encuadre_ms is None
                or t_ms - self._ult_aviso_encuadre_ms >= ORIENTACION_REPETIR_S * 1000):
            self._ult_aviso_encuadre_ms = t_ms
            self.voz.decir(AVISO_ENCUADRE, PRIORIDAD_AVISO)
        return AVISO_ENCUADRE

    def _estado(self, p: Optional[_Paso], res: Optional[ResultadoPose],
                aviso: Optional[str], lat: Dict[str, float],
                orientacion: Optional[float] = None,
                motivo_silencio: Optional[str] = None,
                angulos: Optional[Dict[str, float]] = None,
                otro_movimiento: bool = False) -> EstadoFrame:
        if p is None:
            return EstadoFrame("", "", len(self.rutina.pasos), len(self.rutina.pasos),
                               0, 0, 0, "", False, None, None, self._ultimo_mensaje,
                               None, lat, True,
                               mensajes_emitidos=self._mensajes_emitidos,
                               feedback=self._ultimo_feedback)
        seg = p.seg
        correctas, con_error = self._calidad(p)
        return EstadoFrame(
            ejercicio=p.ejercicio.skill.nombre,
            ejercicio_id=p.ejercicio.skill.skill_id, paso=self._i + 1,
            total_pasos=len(self.rutina.pasos), objetivo=p.objetivo,
            completadas=seg.completadas if seg else 0,
            incompletas=seg.incompletas if seg else 0,
            fase=seg.fase if seg else "", persona=res is not None,
            orientacion=orientacion, aviso=aviso,
            ultimo_mensaje=self._ultimo_mensaje,
            landmarks=res.imagen if res is not None else None,
            latencia_ms=lat, terminada=False, unidad=p.ejercicio.unidad,
            pausada=p.pausa.pausada,
            motivo_pausa=p.pausa.motivo,
            mensajes_emitidos=self._mensajes_emitidos,
            feedback=self._ultimo_feedback,
            motivo_silencio=motivo_silencio,
            angulos=dict(angulos) if angulos else None,
            otro_movimiento=otro_movimiento,
            angulos_importantes=tuple(p.ejercicio.skill.angulos_requeridos),
            guia=_guia_actual(p, self._t_ms),
            correctas=correctas, con_error=con_error,
            colocando=p.colocando,
            instruccion=((self._texto_entrenadora or self._instruccion(p.ejercicio))
                         if p.colocando else None),
            comprobaciones=dict(p.comprobaciones) if p.colocando else None,
            gesto=self._estado_gesto(p),
            escucha=self.oyente.estado() if self.oyente is not None else None,
            microfono=(self.oyente.indicador() if hasattr(self.oyente, "indicador")
                       else None))

    def _estado_gesto(self, p: _Paso) -> Optional[Dict[str, Any]]:
        progreso = self._gesto.progreso(self._t_ms)
        if progreso is None:
            return None
        return {"progreso": round(progreso, 2),
                "accion": "reanudar" if p.pausa.pausada else "pausar"}

    @staticmethod
    def _calidad(p: _Paso) -> Tuple[int, int]:
        """(correctas, con error) entre las unidades completadas cuya
        repetición ya cerró el motor."""
        calidad = p.motor.decision.calidad_por_repeticion
        correctas = sum(n for r, n in p.unidades.items() if calidad.get(r) == CALIDAD_CORRECTA)
        con_error = sum(n for r, n in p.unidades.items() if calidad.get(r) == CALIDAD_CON_ERROR)
        return correctas, con_error

    @staticmethod
    def _instruccion(ej: Ejercicio) -> str:
        colocacion = _COLOCACION.get(ej.skill.orientacion_preferida, "Colócate frente a la cámara.")
        return f"{colocacion} Aléjate hasta que se te vea de la cabeza a los pies."

    # -- resumen ------------------------------------------------------------

    def _filas(self, p: _Paso) -> List[Dict[str, Any]]:
        if p.registro is None:
            return []
        p.registro.cerrar(p.fin_ms if p.fin_ms is not None else self._t_ms)
        calidad = p.motor.decision.calidad_por_repeticion
        return [{**f, "calidad": calidad.get(f["rep"])} for f in p.registro.filas]

    def _resumen_paso(self, p: _Paso) -> Dict[str, Any]:
        seg = p.seg
        fin_ms = p.fin_ms if p.fin_ms is not None else self._t_ms
        pausa_ms = p.pausa.tiempo_pausado_ms(fin_ms)
        correctas, con_error = self._calidad(p)
        return {
            "skill_id": p.ejercicio.skill.skill_id,
            "objetivo": p.objetivo,
            "unidad": p.ejercicio.unidad,
            "completadas": seg.completadas if seg else 0,
            "incompletas": seg.incompletas if seg else 0,
            "correctas": correctas,
            "con_error": con_error,
            # tiempo activo: sin contar las pausas
            "duracion_s": (round((fin_ms - p.inicio_ms - pausa_ms) / 1000.0, 1)
                           if p.inicio_ms is not None else 0.0),
            "pausas_sesion": p.pausa.veces,
            "pausa_s": round(pausa_ms / 1000.0, 1),
            "mensajes": p.mensajes,
            "abstenciones": p.motor.abstenciones,
            # «absolutos» o «referencia» (aplicacion/umbrales.py), y frames
            # en que cada regla relativa se evaluó con su respaldo absoluto
            "umbrales": p.ejercicio.umbrales,
            "respaldos": p.motor.respaldos,
            # frames por resultado del DTW (`dtw.ALINEADO`, `dtw.SIN_*`...);
            # None con `sin_dtw`
            "dtw": dict(p.alineador.motivos) if p.alineador is not None else None,
            "repeticiones": self._filas(p),
        }

    def resumen(self) -> Dict[str, Any]:
        return {
            "rutina": self.rutina.nombre,
            "terminada": self.terminada,
            "sin_dtw": self.sin_dtw,
            "frames": self.frames,
            "frames_sin_persona": self.frames_sin_persona,
            "latencias": self.latencias.resumen(),
            "pasos": [self._resumen_paso(p) for p in self._pasos],
            **({"verbalizacion_aparte": {"pedidas": self._aparte.pedidas,
                                         "sustituidas": self._aparte.sustituidas,
                                         "tarde": self.redactadas_tarde}}
               if self._aparte is not None else {}),
        }


# ---------------------------------------------------------------------------
# Frases conocidas de antemano (para precalentar el TTS)
# ---------------------------------------------------------------------------

def frases_de_rutina(rutina: Rutina, catalogo: Mapping[str, Ejercicio],
                     verbalizador: Optional[Verbalizador] = None) -> Set[str]:
    """Todas las frases que la sesión puede llegar a decir con plantillas."""
    verb = verbalizador or VerbalizadorPlantillas()
    frases: Set[str] = {"Rutina terminada. Buen trabajo."}
    frases.update(_COLOCACION.values())
    frases.add(AVISO_ENCUADRE)
    frases.update(AVISO_PAUSA.values())
    frases.add(AVISO_REANUDA)
    frases.add(AVISO_COLOCADA)
    for paso in rutina.pasos:
        ej = catalogo[paso.skill_id]
        frases.add(Sesion._anuncio(ej, paso.repeticiones))
        frases.add(f"Muy bien, terminaste {ej.skill.nombre.lower()}.")
        frases.add(Sesion._aviso_otro(ej))
        equivocado = (ej.segmentacion or {}).get("movimiento_equivocado")
        if equivocado:
            frases.add(equivocado["aviso"])
        for regla in ej.skill.reglas:
            for sev in Severidad:
                for rep in range(3):          # las plantillas tienen ≤ 3 variantes
                    err = ErrorTipificado(
                        error_id=regla.error_id, segmento=regla.segmento,
                        lado=regla.lado, severidad=sev, fase="", repeticion=rep,
                        ejercicio_id=ej.skill.skill_id,
                        mensaje_id=regla.mensaje_id or regla.error_id)
                    frases.add(verb.verbalizar(err).texto)
    return frases


__all__ = ["Sesion", "EstadoFrame", "frases_de_rutina"]
