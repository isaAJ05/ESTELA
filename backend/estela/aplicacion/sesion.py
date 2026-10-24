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

import time
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Any, Deque, Dict, List, Mapping, Optional, Set, Tuple

import numpy as np

from ..dominio.feedback.contrato import ErrorTipificado, MensajeFeedback, Plano, Severidad, Silencio
from ..dominio.feedback.motor.geometria import observacion_desde_pose
from ..dominio.feedback.pipeline import MotorFeedback
from ..dominio.feedback.verbalizador.base import Verbalizador
from ..dominio.feedback.verbalizador.plantillas import VerbalizadorPlantillas

from ..dominio.conteo.segmentador import EVENTO_COMPLETA, EstadoSegmento, Segmentador, leer_senal
from .dtw import Comparador, comparador_de_referencia
from .metricas import Latencias
from .puertos import PRIORIDAD_AVISO, PRIORIDAD_FEEDBACK, Estimador, ResultadoPose, Voz
from .pausa import EVENTO_PAUSA, EVENTO_REANUDA, INACTIVIDAD, SIN_PERSONA, DetectorPausa
from .reconocimiento import ReconocedorEjercicio, reconocedor_para
from .registro import RegistroRepeticiones
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
               INACTIVIDAD: "Pausa. Cuando quieras, sigue con el ejercicio."}
AVISO_REANUDA = "Seguimos."
#: aviso de EXP-010: no nombra el ejercicio que parece, solo el que toca
AVISO_OTRO_EJERCICIO = "Ese movimiento no es el de ahora. Toca {nombre}."
#: milisegundos sosteniendo el movimiento equivocado antes de avisar
MOVIMIENTO_EQUIVOCADO_MS = 1000
#: `motivo_silencio` mientras suena un aviso (anuncio del ejercicio,
#: colocación...): la persona aún se está colocando y una corrección
#: esperaría en la cola a que acabe el aviso
MOTIVO_ANUNCIO = "anuncio"

_IDEAL = {Plano.FRONTAL: 0.0, Plano.SAGITAL: 90.0}
_COLOCACION = {Plano.FRONTAL: "Colócate de frente a la cámara.",
               Plano.SAGITAL: "Colócate de perfil a la cámara."}


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
    motivo_pausa: Optional[str] = None  # pausa.SIN_PERSONA o pausa.INACTIVIDAD
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
    #: los ángulos que importan en este ejercicio (`angulos_requeridos` de la skill)
    angulos_importantes: Tuple[str, ...] = ()
    #: postura de referencia del frame actual, en formato (33, 4)
    guia: Optional[np.ndarray] = None


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


class Sesion:
    def __init__(self, rutina: Rutina, catalogo: Mapping[str, Ejercicio],
                 estimador: Estimador, voz: Voz,
                 verbalizador: Optional[Verbalizador] = None,
                 sin_dtw: bool = False, reconocer: bool = True,
                 registrar: bool = False) -> None:
        self.rutina = rutina
        self.catalogo = catalogo
        self.estimador = estimador
        self.voz = voz
        self.verbalizador = verbalizador or VerbalizadorPlantillas()
        self.sin_dtw = sin_dtw
        self.reconocer = reconocer
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
        actual = self.paso_actual
        if actual is not None:
            actual.fin_ms = self._t_ms
            if actual.registro is not None:
                actual.registro.cerrar(self._t_ms)
            self.voz.decir(f"Muy bien, terminaste {actual.ejercicio.skill.nombre.lower()}.",
                           PRIORIDAD_AVISO)
        self._i += 1
        if self.terminada:
            self.voz.decir("Rutina terminada. Buen trabajo.", PRIORIDAD_AVISO)
            return
        p = self.rutina.pasos[self._i]
        ej = self.catalogo[p.skill_id]
        guia, guia_fps = _preparar_guia(ej.referencia)
        self._pasos.append(_Paso(ej, p.repeticiones,
                                 MotorFeedback(ej.skill, self.verbalizador),
                                 ej.nuevo_segmentador(),
                                 alineador=(None if self.sin_dtw
                                            else comparador_de_referencia(ej.referencia)),
                                 registro=RegistroRepeticiones(ej),
                                 guia=guia, guia_fps=guia_fps,
                                 reconocedor=(reconocedor_para(ej.skill.skill_id)
                                              if self.reconocer else None)))
        self._mal_orientada_desde = None
        self._ult_aviso_orient_ms = None
        self._ult_senal_ms = None
        self.voz.decir(self._anuncio(ej, p.repeticiones), PRIORIDAD_AVISO)

    @staticmethod
    def _anuncio(ej: Ejercicio, reps: int) -> str:
        colocacion = _COLOCACION.get(ej.skill.orientacion_preferida, "")
        return f"Ahora, {ej.skill.nombre.lower()}. {reps} {ej.unidad}. {colocacion}".strip()

    def siguiente(self) -> None:
        """Salta al siguiente ejercicio (tecla de la interfaz)."""
        if not self.terminada:
            self._avanzar()

    def reiniciar_ejercicio(self) -> None:
        p = self.paso_actual
        if p is not None:
            p.motor.reiniciar()
            p.segmentador.reiniciar()
            p.seg = None
            if p.alineador is not None:
                p.alineador.reiniciar()

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

        res = self.estimador.estimar(frame, t_ms)
        self.latencias.anota("pose", res.latencia_ms)
        lat = {"pose": res.latencia_ms}

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
        seg = p.segmentador.actualizar(obs)
        p.seg = seg
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
            otro_ejercicio = p.reconocedor.actualizar(obs)
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
                               angulos=obs.angulos)

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
            if isinstance(salida, MensajeFeedback):
                lat["verbalizacion"] = p.motor.ultimos_tiempos.verbalizacion_ms
        for etapa in ("geometria", "segmentacion", "dtw", "reconocimiento",
                      "motor", "decision", "verbalizacion"):
            if etapa not in lat:
                continue
            self.latencias.anota(etapa, lat[etapa])

        if isinstance(salida, MensajeFeedback):
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
                               "repeticion": seg.repeticion})

        aviso = (self._revisa_orientacion(skill, obs.orientacion, t_ms)
                 or self._revisa_encuadre(seg.senal_valida, t_ms)
                 or self._revisa_movimiento_equivocado(p, obs, seg, t_ms)
                 or self._revisa_otro_ejercicio(p, otro_ejercicio, t_ms))
        estado = self._estado(p, res, aviso, lat, obs.orientacion,
                              salida.motivo if isinstance(salida, Silencio) else None,
                              angulos=obs.angulos)

        if seg.evento == EVENTO_COMPLETA and seg.completadas >= p.objetivo:
            self._avanzar()
        lat["total"] = (time.perf_counter() - t_ini) * 1000
        self.latencias.anota("total", lat["total"])
        self._registra(p, t_ms, lat, obs=obs, seg=seg, dtw=dtw, salida=salida)
        return estado

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
                angulos: Optional[Dict[str, float]] = None) -> EstadoFrame:
        if p is None:
            return EstadoFrame("", "", len(self.rutina.pasos), len(self.rutina.pasos),
                               0, 0, 0, "", False, None, None, self._ultimo_mensaje,
                               None, lat, True,
                               mensajes_emitidos=self._mensajes_emitidos,
                               feedback=self._ultimo_feedback)
        seg = p.seg
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
            angulos_importantes=tuple(p.ejercicio.skill.angulos_requeridos),
            guia=_guia_actual(p, self._t_ms))

    # -- resumen ------------------------------------------------------------

    def _filas(self, p: _Paso) -> List[Dict[str, Any]]:
        if p.registro is None:
            return []
        p.registro.cerrar(p.fin_ms if p.fin_ms is not None else self._t_ms)
        return list(p.registro.filas)

    def resumen(self) -> Dict[str, Any]:

        pasos = []
        for p in self._pasos:
            seg = p.seg
            fin_ms = p.fin_ms if p.fin_ms is not None else self._t_ms
            pausa_ms = p.pausa.tiempo_pausado_ms(fin_ms)
            pasos.append({
                "skill_id": p.ejercicio.skill.skill_id,
                "objetivo": p.objetivo,
                "unidad": p.ejercicio.unidad,
                "completadas": seg.completadas if seg else 0,
                "incompletas": seg.incompletas if seg else 0,
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
            })
        return {
            "rutina": self.rutina.nombre,
            "terminada": self.terminada,
            "sin_dtw": self.sin_dtw,
            "frames": self.frames,
            "frames_sin_persona": self.frames_sin_persona,
            "latencias": self.latencias.resumen(),
            "pasos": pasos,
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
