"""Arnés de EXP-001: ejecuta una condición de verbalizador sobre el banco.

Uso:

    python3 -m feedback_testing.runner                # condición A
    python3 -m feedback_testing.runner --condicion F  # requiere llama-server
    python3 -m feedback_testing.runner --salida resultados/piloto.md

El módulo de **detección es idéntico** en todas las condiciones; lo único que
cambia es el verbalizador. Ese es el diseño de un solo factor de ADR-001 §5.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feedback.contrato import MensajeFeedback, Silencio
from feedback.motor.skill import Skill, cargar_skills, directorio_skills
from feedback.pipeline import MotorFeedback
from feedback.verbalizador.base import Verbalizador
from feedback.verbalizador.plantillas import VerbalizadorPlantillas

from .generador_episodios import (
    FRAMES_POR_REPETICION, MS_POR_REPETICION, REPETICIONES, Episodio,
    generar_banco,
)
from .metricas import (
    ResultadoEpisodio, abstencion, m1_sintetica, m2_aserciones_no_soportadas,
    m3_sobrecorreccion, m4_latencias, m5_determinismo, m7_fallback,
    mensajes_por_minuto,
)


def construir_verbalizador(condicion: str) -> Verbalizador:
    if condicion == "A":
        return VerbalizadorPlantillas()
    if condicion in ("F", "Fp"):
        from feedback.verbalizador.llm_local import VerbalizadorLLMLocal
        return VerbalizadorLLMLocal(restringido=(condicion == "F"))
    raise SystemExit(f"condición desconocida: {condicion}")


def ejecutar_episodio(skill: Skill, episodio: Episodio,
                      verbalizador: Verbalizador) -> ResultadoEpisodio:
    motor = MotorFeedback(skill, verbalizador)
    res = ResultadoEpisodio(
        episodio_id=episodio.episodio_id,
        ejercicio_id=episodio.ejercicio_id,
        condicion=episodio.condicion,
        error_referencia=episodio.error_referencia,
    )
    for obs in episodio.observaciones:
        salida = motor.procesar(obs)
        res.latencias_decision_ms.append(motor.ultimos_tiempos.decision_ms)
        if isinstance(salida, MensajeFeedback):
            res.mensajes.append(salida)
            res.latencias_verbalizacion_ms.append(
                motor.ultimos_tiempos.verbalizacion_ms)
        else:
            res.motivos_silencio[salida.motivo] = (
                res.motivos_silencio.get(salida.motivo, 0) + 1)
    return res


def ejecutar(condicion: str, repeticiones_determinismo: int = 10
             ) -> Tuple[List[ResultadoEpisodio], List[List[Tuple[str, ...]]]]:
    skills = cargar_skills(directorio_skills())
    banco = generar_banco(skills)
    verb = construir_verbalizador(condicion)

    resultados = [ejecutar_episodio(skills[e.ejercicio_id], e, verb)
                  for e in banco]

    # M5: se repite el banco completo N veces y se comparan las secuencias.
    secuencias: List[List[Tuple[str, ...]]] = []
    for e in banco:
        reps = [ejecutar_episodio(skills[e.ejercicio_id], e, verb).secuencia_errores
                for _ in range(repeticiones_determinismo)]
        secuencias.append(reps)

    return resultados, secuencias


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------

def _pct(x: float) -> str:
    return "n/d" if x != x else f"{100 * x:.1f} %"


def _ms(x: float) -> str:
    return "n/d" if x != x else f"{x:.4f}"


def informe(condicion: str, resultados: Sequence[ResultadoEpisodio],
            secuencias, repeticiones_determinismo: int) -> str:
    ms_episodio = REPETICIONES * MS_POR_REPETICION
    m1, n1 = m1_sintetica(resultados)
    m2, n2 = m2_aserciones_no_soportadas(resultados)
    m3, n3 = m3_sobrecorreccion(resultados)
    m4 = m4_latencias(resultados)
    m5, n5 = m5_determinismo(secuencias)
    m7, n7 = m7_fallback(resultados)
    abs_ocl, n_ocl = abstencion(resultados, "ocluido")
    abs_pln, n_pln = abstencion(resultados, "plano_malo")

    err = [r for r in resultados if r.condicion == "error"]
    sin_mensaje = [r for r in err if not r.hubo_mensaje]

    motivos: Dict[str, int] = {}
    for r in resultados:
        for k, v in r.motivos_silencio.items():
            motivos[k] = motivos.get(k, 0) + v

    L: List[str] = []
    L.append(f"# EXP-001 piloto — condición {condicion} (banco sintético)")
    L.append("")
    L.append(f"- Episodios: **{len(resultados)}**")
    L.append(f"- Observaciones por episodio: {REPETICIONES * FRAMES_POR_REPETICION} "
             f"({REPETICIONES} repeticiones x {FRAMES_POR_REPETICION} frames)")
    L.append(f"- Duración nominal de un episodio: {ms_episodio/1000:.0f} s")
    L.append(f"- Repeticiones para M5: {repeticiones_determinismo}")
    L.append("")
    L.append("## Métricas")
    L.append("")
    L.append("| # | Métrica | Valor | n |")
    L.append("|---|---|---|---|")
    L.append(f"| M1* | Coherencia detector-referencia (sintética) | {_pct(m1)} | {n1} |")
    L.append(f"| M2 | Aserciones no soportadas | {_pct(m2)} | {n2} mensajes |")
    L.append(f"| M3 | Sobrecorrección en ejecuciones correctas | {_pct(m3)} | {n3} |")
    L.append(f"| M5 | Determinismo | {_pct(m5)} | {n5} |")
    L.append(f"| M7 | Caída a fallback | {_pct(m7)} | {n7} mensajes |")
    L.append(f"| — | Abstención con medida ocluida | {_pct(abs_ocl)} | {n_ocl} |")
    L.append(f"| — | Abstención con plano no observable | {_pct(abs_pln)} | {n_pln} |")
    L.append(f"| — | Mensajes por minuto de ejercicio | "
             f"{mensajes_por_minuto(resultados, ms_episodio):.2f} | — |")
    L.append("")
    L.append("**M1\\*** no es la M1 de ADR-001 §5: mide coherencia del motor sobre "
             "entrada sintética, no exactitud de contenido sobre vídeo real.")
    L.append("")
    L.append("## M4 — latencia por etapa (ms)")
    L.append("")
    L.append("| Etapa | p50 | p95 | máx | n |")
    L.append("|---|---|---|---|---|")
    L.append(f"| Decisión | {_ms(m4['decision_p50_ms'])} | {_ms(m4['decision_p95_ms'])} "
             f"| {_ms(m4['decision_max_ms'])} | {m4['n_decisiones']} |")
    L.append(f"| Verbalización | {_ms(m4['verbalizacion_p50_ms'])} | "
             f"{_ms(m4['verbalizacion_p95_ms'])} | {_ms(m4['verbalizacion_max_ms'])} "
             f"| {m4['n_verbalizaciones']} |")
    L.append("")
    L.append("Medido en el entorno de desarrollo, no en el hardware del proyecto. "
             "No sustituye la medición en el M2 Ultra. No incluye pose, DTW ni TTS.")
    L.append("")
    L.append("## Motivos de silencio")
    L.append("")
    L.append("| Motivo | Veces |")
    L.append("|---|---|")
    for k, v in sorted(motivos.items(), key=lambda kv: -kv[1]):
        L.append(f"| `{k}` | {v} |")
    L.append("")
    if sin_mensaje:
        L.append("## Episodios con error inducido que NO produjeron mensaje")
        L.append("")
        for r in sin_mensaje:
            top = sorted(r.motivos_silencio.items(), key=lambda kv: -kv[1])[:2]
            L.append(f"- `{r.episodio_id}` -> " +
                     ", ".join(f"{k}x{v}" for k, v in top))
        L.append("")
    L.append("## Muestra de mensajes emitidos")
    L.append("")
    vistos = set()
    for r in resultados:
        for m in r.mensajes:
            if m.error is None:
                continue
            clave = (m.error.error_id, m.error.severidad.value)
            if clave in vistos:
                continue
            vistos.add(clave)
            L.append(f"- `{m.error.ejercicio_id}` / `{m.error.error_id}` / "
                     f"{m.error.severidad.value} -> «{m.texto}»")
    L.append("")
    return "\n".join(L)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Arnés de EXP-001")
    ap.add_argument("--condicion", default="A", choices=["A", "F", "Fp"])
    ap.add_argument("--repeticiones-determinismo", type=int, default=10)
    ap.add_argument("--salida", default="")
    args = ap.parse_args(argv)

    resultados, secuencias = ejecutar(args.condicion,
                                      args.repeticiones_determinismo)
    txt = informe(args.condicion, resultados, secuencias,
                  args.repeticiones_determinismo)
    if args.salida:
        os.makedirs(os.path.dirname(args.salida) or ".", exist_ok=True)
        with open(args.salida, "w", encoding="utf-8") as f:
            f.write(txt + "\n")
        print(f"informe escrito en {args.salida}")
    else:
        print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
