"""Orquestador de la sesión en tiempo real.

Por frame:

    ResultadoPose ─► observacion_desde_pose ─► Segmentador (fase, repetición)
                 ─► MotorFeedback (decisión determinista + plantilla) ─► voz

`Sesion` no sabe nada de cámaras ni de ventanas: recibe `(frame, t_ms)` y
devuelve un `EstadoFrame` para dibujar. Eso permite probar el flujo entero
con un estimador falso y reproducirlo con un vídeo.

Además del feedback de técnica (que decide solo el motor), la sesión emite
avisos de *operación*: qué ejercicio toca, cómo colocarse y cuándo se
termina. No son correcciones de movimiento, por eso no pasan por el motor.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Mapping, Optional, Protocol, Set

import numpy as np

from feedback.contrato import ErrorTipificado, MensajeFeedback, Plano, Severidad
from feedback.motor.geometria import observacion_desde_pose
from feedback.pipeline import MotorFeedback
from feedback.verbalizador.base import Verbalizador
from feedback.verbalizador.plantillas import VerbalizadorPlantillas

from ..conteo.segmentador import EVENTO_COMPLETA, EstadoSegmento, Segmentador
from ..pose.estimador import ResultadoPose
from ..voz.cola import PRIORIDAD_AVISO, PRIORIDAD_FEEDBACK
from .metricas import Latencias
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

_IDEAL = {Plano.FRONTAL: 0.0, Plano.SAGITAL: 90.0}
_COLOCACION = {Plano.FRONTAL: "Colócate de frente a la cámara.",
               Plano.SAGITAL: "Colócate de perfil a la cámara."}


class Estimador(Protocol):
    def estimar(self, frame: np.ndarray, t_ms: int) -> ResultadoPose: ...


class Voz(Protocol):
    def decir(self, texto: str, prioridad: int = ...) -> bool: ...


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
    sugerencia: Optional[str]          # ejercicio que sugiere la BiLSTM
    landmarks: Optional[np.ndarray]    # (33, 4) de imagen, para dibujar
    latencia_ms: Dict[str, float]
    terminada: bool


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


class Sesion:
    def __init__(self, rutina: Rutina, catalogo: Mapping[str, Ejercicio],
                 estimador: Estimador, voz: Voz,
                 verbalizador: Optional[Verbalizador] = None,
                 reconocedor: Any = None) -> None:
        self.rutina = rutina
        self.catalogo = catalogo
        self.estimador = estimador
        self.voz = voz
        self.verbalizador = verbalizador or VerbalizadorPlantillas()
        self.reconocedor = reconocedor
        self.latencias = Latencias()
        self.frames = 0
        self.frames_sin_persona = 0
        self._pasos: List[_Paso] = []
        self._i = -1
        self._ultimo_mensaje: Optional[str] = None
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
            self.voz.decir(f"Muy bien, terminaste {actual.ejercicio.skill.nombre.lower()}.",
                           PRIORIDAD_AVISO)
        self._i += 1
        if self.terminada:
            self.voz.decir("Rutina terminada. Buen trabajo.", PRIORIDAD_AVISO)
            return
        p = self.rutina.pasos[self._i]
        ej = self.catalogo[p.skill_id]
        self._pasos.append(_Paso(ej, p.repeticiones,
                                 MotorFeedback(ej.skill, self.verbalizador),
                                 ej.nuevo_segmentador()))
        if self.reconocedor is not None:
            self.reconocedor.reiniciar()
        self._mal_orientada_desde = None
        self._ult_aviso_orient_ms = None
        self._ult_senal_ms = None
        self.voz.decir(self._anuncio(ej, p.repeticiones), PRIORIDAD_AVISO)

    @staticmethod
    def _anuncio(ej: Ejercicio, reps: int) -> str:
        colocacion = _COLOCACION.get(ej.skill.orientacion_preferida, "")
        return f"Ahora, {ej.skill.nombre.lower()}. {reps} repeticiones. {colocacion}".strip()

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

    # -- bucle --------------------------------------------------------------

    def procesar(self, frame: np.ndarray, t_ms: int) -> EstadoFrame:
        t_ini = time.perf_counter()
        self._t_ms = t_ms
        self.frames += 1
        p = self.paso_actual
        if p is None:
            return self._estado(None, None, None, {}, None)
        if p.inicio_ms is None:
            p.inicio_ms = t_ms

        res = self.estimador.estimar(frame, t_ms)
        self.latencias.anota("pose", res.latencia_ms)
        lat = {"pose": res.latencia_ms}

        sugerencia = None
        if self.reconocedor is not None:
            t0 = time.perf_counter()
            sugerencia = self.reconocedor.agregar(res.imagen).skill_id
            lat["reconocimiento"] = (time.perf_counter() - t0) * 1000.0
            self.latencias.anota("reconocimiento", lat["reconocimiento"])

        if res.muestra is None:
            self.frames_sin_persona += 1
            aviso = None
            if (self._ult_persona_ms is None
                    or t_ms - self._ult_persona_ms > SIN_PERSONA_S * 1000):
                aviso = "No te veo: colócate dentro del encuadre."
            return self._estado(p, None, aviso, lat, sugerencia)
        self._ult_persona_ms = t_ms

        skill = p.ejercicio.skill
        t0 = time.perf_counter()
        obs = observacion_desde_pose(res.muestra, skill.skill_id)
        t1 = time.perf_counter()
        seg = p.segmentador.actualizar(obs)
        p.seg = seg
        obs = replace(obs, fase=seg.fase, repeticion=seg.repeticion)
        t2 = time.perf_counter()
        salida = p.motor.procesar(obs)
        t3 = time.perf_counter()
        lat.update(geometria=(t1 - t0) * 1000, segmentacion=(t2 - t1) * 1000,
                   motor=(t3 - t2) * 1000)
        for etapa in ("geometria", "segmentacion", "motor"):
            self.latencias.anota(etapa, lat[etapa])

        if isinstance(salida, MensajeFeedback):
            self._ultimo_mensaje = salida.texto
            self.voz.decir(salida.texto, PRIORIDAD_FEEDBACK)
            p.mensajes.append({"t_ms": t_ms, "texto": salida.texto,
                               "error_id": salida.error.error_id if salida.error else None,
                               "repeticion": seg.repeticion})

        aviso = (self._revisa_orientacion(skill, obs.orientacion, t_ms)
                 or self._revisa_encuadre(seg.senal_valida, t_ms))
        estado = self._estado(p, res, aviso, lat, sugerencia, obs.orientacion)

        if seg.evento == EVENTO_COMPLETA and seg.completadas >= p.objetivo:
            self._avanzar()
        lat["total"] = (time.perf_counter() - t_ini) * 1000
        self.latencias.anota("total", lat["total"])
        return estado

    def _revisa_orientacion(self, skill, orientacion: Optional[float],
                            t_ms: int) -> Optional[str]:
        ideal = _IDEAL.get(skill.orientacion_preferida)
        if ideal is None or orientacion is None:
            return None
        if abs(orientacion - ideal) <= skill.politica.tolerancia_orientacion_grados:
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
                sugerencia: Optional[str],
                orientacion: Optional[float] = None) -> EstadoFrame:
        if p is None:
            return EstadoFrame("", "", len(self.rutina.pasos), len(self.rutina.pasos),
                               0, 0, 0, "", False, None, None, self._ultimo_mensaje,
                               None, None, lat, True)
        seg = p.seg
        return EstadoFrame(
            ejercicio=p.ejercicio.skill.nombre,
            ejercicio_id=p.ejercicio.skill.skill_id, paso=self._i + 1,
            total_pasos=len(self.rutina.pasos), objetivo=p.objetivo,
            completadas=seg.completadas if seg else 0,
            incompletas=seg.incompletas if seg else 0,
            fase=seg.fase if seg else "", persona=res is not None,
            orientacion=orientacion, aviso=aviso,
            ultimo_mensaje=self._ultimo_mensaje, sugerencia=sugerencia,
            landmarks=res.imagen if res is not None else None,
            latencia_ms=lat, terminada=False)

    # -- resumen ------------------------------------------------------------

    def resumen(self) -> Dict[str, Any]:

        pasos = []
        for p in self._pasos:
            seg = p.seg
            pasos.append({
                "skill_id": p.ejercicio.skill.skill_id,
                "objetivo": p.objetivo,
                "completadas": seg.completadas if seg else 0,
                "incompletas": seg.incompletas if seg else 0,
                "duracion_s": (round(((p.fin_ms if p.fin_ms is not None else self._t_ms)
                                      - p.inicio_ms) / 1000.0, 1)
                               if p.inicio_ms is not None else 0.0),
                "mensajes": p.mensajes,
                "abstenciones": p.motor.abstenciones,
            })
        return {
            "rutina": self.rutina.nombre,
            "terminada": self.terminada,
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
    for paso in rutina.pasos:
        ej = catalogo[paso.skill_id]
        frases.add(Sesion._anuncio(ej, paso.repeticiones))
        frases.add(f"Muy bien, terminaste {ej.skill.nombre.lower()}.")
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
