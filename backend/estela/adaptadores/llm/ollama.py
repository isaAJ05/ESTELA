"""Comprobación de arranque contra Ollama: ¿responde y tiene el modelo?

Con lo que aprovecha el Mac encendido por defecto (`config.defectos`), el
programa no puede dar por hecho que Ollama está corriendo ni que el modelo
está descargado. Se pregunta una vez al arrancar; si falta algo, quien llama
sigue con las plantillas y lo avisa.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Tuple


def modelo_disponible(modelo: str, url_chat: str, timeout_s: float = 1.5) -> Tuple[bool, str]:
    """(está, motivo si no). `url_chat` es la URL de `/api/chat`."""
    base = url_chat.split("/api/")[0]
    try:
        with urllib.request.urlopen(base + "/api/tags", timeout=timeout_s) as r:
            nombres = {m.get("name") for m in json.loads(r.read().decode("utf-8")).get("models", [])}
    except Exception as exc:                              # noqa: BLE001
        return False, f"Ollama no responde en {base} ({type(exc).__name__})"
    if modelo in nombres or f"{modelo}:latest" in nombres:
        return True, ""
    return False, f"falta el modelo {modelo} en Ollama (ollama pull {modelo})"


__all__ = ["modelo_disponible"]
