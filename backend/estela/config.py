"""Rutas por defecto, relativas a `backend/` (la raíz del proyecto Python)."""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Dict, Optional

RAIZ = Path(__file__).resolve().parent.parent
MODELOS = RAIZ / "modelos"
VOCES = MODELOS / "voces"
RUTINAS = RAIZ / "rutinas"
SESIONES = RAIZ / "sesiones"
#: perfiles y su historial para «Mi progreso» (ADR-008, ADR-009); solo en este equipo
HISTORIAL = RAIZ / "historial"
#: interfaz de escritorio compilada (frontend/, `npm run build`)
INTERFAZ = RAIZ.parent / "frontend" / "dist"


def modelo_pose(variante: str) -> Path:
    return MODELOS / f"pose_landmarker_{variante}.task"


# ---------------------------------------------------------------------------
# Valores por defecto según el equipo (rama feature/mac-flujo)
# ---------------------------------------------------------------------------

#: Mac con Apple Silicon, como el Mac Studio M2 Ultra del proyecto.
EN_MAC = sys.platform == "darwin" and platform.machine() == "arm64"

#: Modelos y tiempos límite por defecto. `[R]` Elegidos con la medición del
#: Mac Studio del 2026-11-16 (ESTADO.md): el 4B redacta una corrección en
#: p95 185 ms y ninguna llamada pasó de 400 ms; el 14B responde como
#: entrenadora en p95 2,1 s. No son una decisión del equipo: adoptar el LLM en
#: vivo sigue dependiendo de EXP-001 (ADR-004, rol C).
LLM_MODELO = "qwen3:4b-instruct-2507-q4_K_M"
LLM_TIMEOUT_MS = 400
ENTRENADORA_MODELO = "qwen3:14b"
ENTRENADORA_TIMEOUT_S = 5.0


def defectos(en_mac: Optional[bool] = None) -> Dict[str, str]:
    """Qué se enciende cuando no se pide nada por la línea de comandos.

    En el Mac va encendido todo lo que aprovecha ese equipo: pose heavy en la
    GPU (p95 6 ms en benchmark; en CPU son 58 ms y no cabe), las frases
    redactadas por el LLM y la entrenadora con LLM. En los demás equipos todo
    queda como antes. Si en el Mac falta algo (GPU, Ollama o un modelo), el
    arranque cae a lo de antes y lo avisa (`__main__`).
    """
    if EN_MAC if en_mac is None else en_mac:
        return {"modelo": "heavy", "delegado": "gpu",
                "verbalizador": "llm", "entrenadora": "llm"}
    return {"modelo": "lite", "delegado": "cpu",
            "verbalizador": "plantillas", "entrenadora": "no"}
