"""Contratos de datos del módulo de retroalimentación de ESTELA.

Este archivo define la frontera entre el módulo de percepción (pose, DTW,
normalización) y el módulo de retroalimentación. Nada de lo que hay aquí
depende de la cámara, del estimador de pose ni del modelo de comparación:
el módulo de retroalimentación es testeable sin hardware.

Tres niveles:

    MuestraPose    -> lo que produce el estimador de pose (crudo)
    Observacion    -> lo que el módulo de retroalimentación consume
    ErrorTipificado-> lo que el motor determinista decide
    MensajeFeedback-> lo que el verbalizador produce

Convención epistémica del proyecto: `[F]` evidencia verificada, `[I]`
inferencia, `[R]` recomendación, `[?]` pendiente de medición.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Vocabulario cerrado
# ---------------------------------------------------------------------------

class Lado(str, Enum):
    IZQUIERDO = "izquierdo"
    DERECHO = "derecho"
    BILATERAL = "bilateral"
    NA = "na"


class Severidad(str, Enum):
    LEVE = "leve"
    MODERADA = "moderada"
    ALTA = "alta"


class Plano(str, Enum):
    """Plano en el que una medida es observable con una sola cámara."""
    SAGITAL = "sagital"      # visible de perfil
    FRONTAL = "frontal"      # visible de frente
    TRANSVERSAL = "transversal"
    CUALQUIERA = "cualquiera"


#: Segmentos corporales que el sistema puede nombrar. El validador de salida
#: rechaza cualquier mensaje que mencione un segmento fuera de esta lista o
#: distinto del que viene en el contrato.
SEGMENTOS = (
    "rodilla", "cadera", "tronco", "hombro", "codo", "muneca",
    "tobillo", "pie", "cuello", "cabeza", "brazo", "pierna", "espalda",
)

#: Vocabulario prohibido: ESTELA no hace diagnóstico médico ni rehabilitación
#: (Informe 1, §2.3). Un mensaje que contenga cualquiera de estos términos es
#: rechazado por el validador, venga de una plantilla o de un modelo.
VOCABULARIO_PROHIBIDO = (
    "lesion", "lesión", "lesionar", "diagnostico", "diagnóstico", "patologia",
    "patología", "hernia", "tendinitis", "esguince", "desgarro", "fractura",
    "rehabilitacion", "rehabilitación", "terapia", "dolor cronico",
    "dolor crónico", "sintoma", "síntoma", "tratamiento", "medicamento",
)


# ---------------------------------------------------------------------------
# Nivel 1: lo que entrega el estimador de pose
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Keypoint:
    """Un punto articular.

    `x`, `y`, `z` en el espacio declarado por `MuestraPose.espacio`.
    `visibilidad` en [0, 1]; es el insumo de la política de abstención.
    """
    x: float
    y: float
    z: Optional[float] = None
    visibilidad: float = 1.0


@dataclass(frozen=True)
class MuestraPose:
    """Una muestra de pose de un único frame, de una única persona.

    `espacio`:
      - "imagen_norm": coordenadas normalizadas al frame, origen esquina
        superior izquierda. La profundidad, si existe, no es métrica.
      - "mundo_m": coordenadas métricas con origen en el centro de la cadera.
        `[R]` Es el espacio preferido: los ángulos calculados en él no dependen
        de la posición ni de la distancia del sujeto a la cámara.

    `fuente` documenta qué estimador produjo la muestra, para poder reproducir
    resultados cuando el equipo cambie de modelo.
    """
    t_ms: int
    keypoints: Dict[str, Keypoint]
    espacio: str = "mundo_m"
    fuente: str = "desconocida"


# ---------------------------------------------------------------------------
# Nivel 2: lo que consume el módulo de retroalimentación
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Observacion:
    """Estado del movimiento en un instante, ya normalizado y alineado.

    Este es **el contrato de entrada del módulo de retroalimentación**. Es lo
    que el equipo de percepción debe producir. Todo lo que el motor de decisión
    necesita está aquí; el motor no accede a los frames ni a la cámara.

    Campos obligatorios:
      t_ms          instante de la muestra.
      ejercicio_id  identificador del `skill` activo.
      angulos       ángulos articulares en grados, nombres canónicos.
      confianza     confianza en [0,1] por ángulo. Es obligatoria: sin ella el
                    motor no puede abstenerse y corregiría a ciegas.

    Campos opcionales pero recomendados:
      fase          fase del ciclo según el segmentador/DTW.
      repeticion    índice de repetición, empezando en 1.
      progreso      posición dentro del ciclo en [0,1] (salida del DTW).
      angulos_ref   ángulo de la referencia en el instante alineado por DTW.
      distancias    medidas escalares normalizadas por escala corporal
                    (p. ej. separación de pies / ancho de caderas).
      orientacion   ángulo en grados entre el plano frontal del sujeto y el
                    plano de imagen. 0 = de frente, 90 = de perfil.
                    `[R]` Sin este dato el motor no puede saber qué reglas son
                    observables; ver EXP-002.
      coste_dtw     coste de alineamiento, como señal de confianza global.

    `desviaciones` es derivado: si `angulos_ref` está presente, el motor
    calcula `angulos - angulos_ref`; si el equipo de percepción ya lo calcula,
    puede entregarlo directamente y se usará tal cual.
    """
    t_ms: int
    ejercicio_id: str
    angulos: Dict[str, float]
    confianza: Dict[str, float]
    fase: str = "desconocida"
    repeticion: Optional[int] = None
    progreso: Optional[float] = None
    angulos_ref: Dict[str, float] = field(default_factory=dict)
    desviaciones: Dict[str, float] = field(default_factory=dict)
    distancias: Dict[str, float] = field(default_factory=dict)
    orientacion: Optional[float] = None
    coste_dtw: Optional[float] = None

    def desviacion_de(self, nombre: str) -> Optional[float]:
        """Desviación respecto a la referencia, o None si no es calculable."""
        if nombre in self.desviaciones:
            return self.desviaciones[nombre]
        if nombre in self.angulos and nombre in self.angulos_ref:
            return self.angulos[nombre] - self.angulos_ref[nombre]
        return None

    def confianza_de(self, nombre: str) -> float:
        """Confianza de una medida. Ausente => 0.0, nunca 1.0.

        `[R]` El valor por defecto es deliberadamente pesimista: una medida sin
        confianza declarada no debe poder disparar una corrección.
        """
        return float(self.confianza.get(nombre, 0.0))


# ---------------------------------------------------------------------------
# Nivel 3: salida del motor determinista
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ErrorTipificado:
    """Frontera estable entre decisión y verbalización (ADR-001, §4.3).

    El verbalizador —plantilla o modelo— recibe exactamente esto y nada más.
    No recibe keypoints, ni ángulos crudos, ni el vídeo. Por construcción no
    puede afirmar nada que no esté aquí.
    """
    error_id: str
    segmento: str
    lado: Lado
    severidad: Severidad
    fase: str
    repeticion: Optional[int]
    ejercicio_id: str
    #: clase de mensaje a usar. Varios `error_id` pueden compartirla
    #: (p. ej. `valgo_rodilla_izq` y `valgo_rodilla_der`). Vacío => `error_id`.
    mensaje_id: str = ""
    #: magnitud del exceso sobre el umbral, en grados o unidades normalizadas
    magnitud: float = 0.0
    #: nombre de la medida que disparó la regla, para trazabilidad
    medida: str = ""
    #: confianza de la medida que disparó la regla
    confianza: float = 0.0

    def __post_init__(self) -> None:
        if self.segmento not in SEGMENTOS:
            raise ValueError(
                f"segmento '{self.segmento}' fuera del vocabulario cerrado"
            )


@dataclass(frozen=True)
class MensajeFeedback:
    """Mensaje listo para TTS."""
    texto: str
    error: Optional[ErrorTipificado]
    verbalizador: str
    latencia_ms: float = 0.0
    #: True si el verbalizador principal falló y se usó la plantilla
    fallback: bool = False
    #: motivo de rechazo del validador, si lo hubo
    motivo_rechazo: str = ""


@dataclass(frozen=True)
class Silencio:
    """Resultado explícito de 'no hay nada que decir ahora'.

    `[R]` El silencio es una salida de primera clase, no la ausencia de
    salida. Tiene motivo, y el motivo se mide (EXP-001, M3).
    """
    motivo: str
    t_ms: int = 0


#: Motivos de silencio. Se miden por separado porque significan cosas
#: distintas: `sin_error` es el sistema funcionando bien; `confianza_baja`
#: y `plano_no_observable` son limitaciones de la percepción, y su frecuencia
#: es la señal de que hace falta otra cámara o reubicar la actual.
MOTIVO_SIN_ERROR = "sin_error"
MOTIVO_CONFIANZA_BAJA = "confianza_baja"
MOTIVO_PLANO_NO_OBSERVABLE = "plano_no_observable"
MOTIVO_REFRACTARIO = "periodo_refractario"
MOTIVO_EVIDENCIA_INSUFICIENTE = "evidencia_insuficiente"
MOTIVO_DESVANECIMIENTO = "desvanecimiento"
MOTIVO_FASE_SILENCIADA = "fase_silenciada"


__all__ = [
    "Lado", "Severidad", "Plano", "SEGMENTOS", "VOCABULARIO_PROHIBIDO",
    "Keypoint", "MuestraPose", "Observacion", "ErrorTipificado",
    "MensajeFeedback", "Silencio",
    "MOTIVO_SIN_ERROR", "MOTIVO_CONFIANZA_BAJA", "MOTIVO_PLANO_NO_OBSERVABLE",
    "MOTIVO_REFRACTARIO", "MOTIVO_EVIDENCIA_INSUFICIENTE",
    "MOTIVO_DESVANECIMIENTO", "MOTIVO_FASE_SILENCIADA",
]
