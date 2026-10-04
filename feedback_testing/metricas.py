"""Métricas de EXP-001 sobre el banco sintético.

Nomenclatura alineada con ADR-001 §5. Donde una métrica no se puede obtener
con datos sintéticos se dice explícitamente en su docstring y **no** se
sustituye por un sucedáneo con el mismo nombre.

Desde que el motor da refuerzo positivo (`contrato.Refuerzo`), un
`MensajeFeedback` puede ser una corrección (`error` presente) o un elogio
(`error is None`). Las métricas de corrección cuentan solo correcciones, como
dicen sus definiciones; el elogio se mide aparte con M8, el espejo de M3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from feedback.contrato import MensajeFeedback, Silencio
from feedback.verbalizador.validador import afirmaciones_no_soportadas


@dataclass
class ResultadoEpisodio:
    episodio_id: str
    ejercicio_id: str
    condicion: str
    error_referencia: Optional[str]
    mensajes: List[MensajeFeedback] = field(default_factory=list)
    motivos_silencio: Dict[str, int] = field(default_factory=dict)
    latencias_decision_ms: List[float] = field(default_factory=list)
    latencias_verbalizacion_ms: List[float] = field(default_factory=list)

    @property
    def correcciones(self) -> List[MensajeFeedback]:
        return [m for m in self.mensajes if m.error is not None]

    @property
    def refuerzos(self) -> List[MensajeFeedback]:
        return [m for m in self.mensajes if m.error is None]

    @property
    def hubo_mensaje(self) -> bool:
        """Cualquier mensaje, corrección o elogio. Solo para la densidad."""
        return bool(self.mensajes)

    @property
    def hubo_correccion(self) -> bool:
        return bool(self.correcciones)

    @property
    def hubo_refuerzo(self) -> bool:
        return bool(self.refuerzos)

    @property
    def primer_error_id(self) -> Optional[str]:
        """`error_id` de la primera **corrección** (un elogio previo no cuenta)."""
        correcciones = self.correcciones
        return correcciones[0].error.error_id if correcciones else None

    @property
    def secuencia_errores(self) -> Tuple[str, ...]:
        return tuple(m.error.error_id for m in self.mensajes if m.error)


def percentil(valores: Sequence[float], p: float) -> float:
    """Percentil por interpolación lineal. p en [0, 100]."""
    if not valores:
        return float("nan")
    vs = sorted(valores)
    if len(vs) == 1:
        return vs[0]
    k = (len(vs) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(vs) - 1)
    return vs[f] + (vs[c] - vs[f]) * (k - f)


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------

def m1_sintetica(resultados: Sequence[ResultadoEpisodio]) -> Tuple[float, int]:
    """Coherencia detector-referencia sobre entrada sintética.

    **No es la M1 de ADR-001.** M1 mide si el mensaje nombra el segmento y el
    lado del error de referencia anotado por una persona sobre vídeo real.
    Aquí el «error de referencia» lo puso el propio generador a partir del
    umbral del skill, así que esta cifra solo demuestra que el motor señala el
    error que se le indujo y no otro. Es una prueba de integridad del motor,
    no una medida de exactitud clínica.
    """
    casos = [r for r in resultados if r.condicion == "error"]
    if not casos:
        return float("nan"), 0
    ok = sum(1 for r in casos if r.primer_error_id == r.error_referencia)
    return ok / len(casos), len(casos)


def m2_aserciones_no_soportadas(resultados: Sequence[ResultadoEpisodio]) -> Tuple[float, int]:
    """Fracción de mensajes que afirman algo ausente del contrato de entrada.

    Es el proxy de alucinación de ADR-001. Para el verbalizador de plantillas
    debe ser exactamente 0 por construcción; si no lo es, hay un defecto en el
    archivo de plantillas.
    """
    total = 0
    malos = 0
    for r in resultados:
        for m in r.mensajes:
            if m.error is None:
                continue
            total += 1
            if afirmaciones_no_soportadas(m.texto, m.error):
                malos += 1
    if total == 0:
        return float("nan"), 0
    return malos / total, total


def m3_sobrecorreccion(resultados: Sequence[ResultadoEpisodio]) -> Tuple[float, int]:
    """Fracción de episodios **correctos** que reciben alguna corrección.

    `[F]` CoachMe reporta 30,4 % en esta métrica (ADR-001 §2.3). Es la cifra
    de comparación.
    """
    casos = [r for r in resultados if r.condicion == "correcto"]
    if not casos:
        return float("nan"), 0
    return sum(1 for r in casos if r.hubo_correccion) / len(casos), len(casos)


def m4_latencias(resultados: Sequence[ResultadoEpisodio]) -> Dict[str, float]:
    dec: List[float] = []
    ver: List[float] = []
    for r in resultados:
        dec.extend(r.latencias_decision_ms)
        ver.extend(r.latencias_verbalizacion_ms)
    tot = [d for d in dec]
    return {
        "n_decisiones": len(dec),
        "decision_p50_ms": percentil(dec, 50),
        "decision_p95_ms": percentil(dec, 95),
        "decision_max_ms": max(dec) if dec else float("nan"),
        "n_verbalizaciones": len(ver),
        "verbalizacion_p50_ms": percentil(ver, 50),
        "verbalizacion_p95_ms": percentil(ver, 95),
        "verbalizacion_max_ms": max(ver) if ver else float("nan"),
    }


def m5_determinismo(secuencias: Sequence[Sequence[Tuple[str, ...]]]) -> Tuple[float, int]:
    """Fracción de episodios cuya secuencia de errores es idéntica en las N
    ejecuciones repetidas."""
    if not secuencias:
        return float("nan"), 0
    iguales = sum(1 for reps in secuencias if len(set(reps)) == 1)
    return iguales / len(secuencias), len(secuencias)


def m7_fallback(resultados: Sequence[ResultadoEpisodio]) -> Tuple[float, int]:
    total = sum(len(r.mensajes) for r in resultados)
    if total == 0:
        return float("nan"), 0
    malos = sum(1 for r in resultados for m in r.mensajes if m.fallback)
    return malos / total, total


#: Condiciones del banco en las que el error está presente pero el sistema no
#: puede verlo (medida ocluida o sujeto mal orientado).
CONDICIONES_NO_OBSERVABLES = ("ocluido", "plano_malo")


def m8_refuerzo_indebido(resultados: Sequence[ResultadoEpisodio],
                         condiciones: Sequence[str] = ("error",)
                         ) -> Tuple[float, int]:
    """Fracción de episodios **con un error presente** que reciben algún
    elogio. Es el espejo de M3: M3 es corregir cuando no hay nada mal; M8 es
    felicitar cuando sí lo hay.

    Con la condición `error` (error inducido y observable) debe ser 0: el
    refuerzo exige repeticiones limpias. Con las condiciones no observables
    (`CONDICIONES_NO_OBSERVABLES`) mide otra cosa: el elogio que se da porque
    las reglas que sí se ven están bien, aunque haya un error que la cámara no
    ve. No es un fallo del motor tal como está definido el refuerzo
    (`contrato.Refuerzo`: «no se detectaron errores»), pero es lo que oye la
    usuaria, y por eso se reporta aparte.
    """
    casos = [r for r in resultados if r.condicion in condiciones]
    if not casos:
        return float("nan"), 0
    return sum(1 for r in casos if r.hubo_refuerzo) / len(casos), len(casos)


def refuerzo_en_correctas(resultados: Sequence[ResultadoEpisodio]) -> Tuple[float, int]:
    """Fracción de ejecuciones correctas que reciben algún elogio. No es una
    métrica de error: dice si el refuerzo llega a darse donde corresponde."""
    casos = [r for r in resultados if r.condicion == "correcto"]
    if not casos:
        return float("nan"), 0
    return sum(1 for r in casos if r.hubo_refuerzo) / len(casos), len(casos)


def abstencion(resultados: Sequence[ResultadoEpisodio], condicion: str) -> Tuple[float, int]:
    """Fracción de episodios de una condición adversa en los que el sistema no
    corrigió, que es lo correcto. Un elogio no es una corrección: se mide con
    `m8_refuerzo_indebido`."""
    casos = [r for r in resultados if r.condicion == condicion]
    if not casos:
        return float("nan"), 0
    return sum(1 for r in casos if not r.hubo_correccion) / len(casos), len(casos)


def mensajes_por_minuto(resultados: Sequence[ResultadoEpisodio],
                        ms_por_episodio: float, tipo: str = "todos") -> float:
    """Densidad de feedback. `[F]` Sigrist et al.: el feedback permanente
    induce dependencia; esta cifra es la que hay que mantener baja.

    `tipo`: "todos", "correccion" o "refuerzo"."""
    if not resultados or ms_por_episodio <= 0:
        return float("nan")
    elegir = {"todos": lambda r: r.mensajes, "correccion": lambda r: r.correcciones,
              "refuerzo": lambda r: r.refuerzos}[tipo]
    total = sum(len(elegir(r)) for r in resultados)
    minutos = len(resultados) * ms_por_episodio / 60000.0
    return total / minutos if minutos else float("nan")


__all__ = [
    "ResultadoEpisodio", "percentil", "m1_sintetica",
    "m2_aserciones_no_soportadas", "m3_sobrecorreccion", "m4_latencias",
    "m5_determinismo", "m7_fallback", "m8_refuerzo_indebido",
    "refuerzo_en_correctas", "CONDICIONES_NO_OBSERVABLES", "abstencion",
    "mensajes_por_minuto",
]
