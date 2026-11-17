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
#: Modelo de Whisper para las órdenes de voz (formato ggml de whisper.cpp).
#: `[R]` «small»: en el Mac Studio reconoce una orden en p95 69 ms, con los
#: mismos aciertos que «large-v3-turbo» (64 de 72; p95 172 ms) en la prueba sintética.
VOZ_ENTRADA_MODELO = "small"
URL_WHISPER_CPP = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{modelo}.bin"


def modelo_voz_entrada(modelo: str = VOZ_ENTRADA_MODELO) -> Path:
    return MODELOS / "voz_entrada" / f"ggml-{modelo}.bin"


def defectos(en_mac: Optional[bool] = None) -> Dict[str, str]:
    """Qué se enciende cuando no se pide nada por la línea de comandos.

    En el Mac va encendido todo lo que aprovecha ese equipo: pose heavy en la
    GPU (p95 6 ms en benchmark; en CPU son 58 ms y no cabe), las frases
    redactadas por el LLM, la entrenadora con LLM y las órdenes de voz (en modo
    «llamada»: «Estela» y la orden, también durante el ejercicio). En los demás equipos todo
    queda como antes. Si en el Mac falta algo (GPU, Ollama o un modelo), el
    arranque cae a lo de antes y lo avisa (`__main__`). Lo mismo si no hay
    micrófono o falta el modelo de voz: la sesión sigue sin órdenes de voz.
    """
    if EN_MAC if en_mac is None else en_mac:
        return {"modelo": "heavy", "delegado": "gpu",
                "verbalizador": "llm", "entrenadora": "llm", "voz_entrada": "si",
                "voz_entrada_modo": "llamada"}
    return {"modelo": "lite", "delegado": "cpu",
            "verbalizador": "plantillas", "entrenadora": "no", "voz_entrada": "no",
            "voz_entrada_modo": "pausa"}
