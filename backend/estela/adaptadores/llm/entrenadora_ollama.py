"""Generador de la entrenadora con Ollama (`POST /api/chat`).

Da a `aplicacion.entrenadora.Entrenadora` la función que redacta: recibe el
mensaje de sistema, los datos y las acciones permitidas, y devuelve
`{"resumen": ..., "accion": ...}`.

`[F]` Documentación de Ollama (docs.ollama.com, «Structured outputs» y
«Thinking»): `format` acepta un esquema JSON y `think: false` pide que no haya
razonamiento. El esquema limita `accion` a las permitidas (`enum`); aun así la
entrenadora vuelve a validar la respuesta, porque el esquema solo restringe la
forma. Todo es local: la petición va a `127.0.0.1`.

No decide nada del movimiento y no se llama durante un ejercicio: quien la usa
(`__main__`) la lanza en un hilo aparte entre ejercicios y al final.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict, Mapping, Optional, Sequence

URL_OLLAMA = "http://127.0.0.1:11434/api/chat"
#: tope de tokens de la respuesta (el resumen es de una o dos frases)
MAX_TOKENS = 160
MANTENER_CARGADO = "30m"
#: ventana de contexto (ver `llm_local.NUM_CTX`): los datos de una rutina son
#: unos cientos de tokens
NUM_CTX = 4096


class GeneradorOllama:
    def __init__(self, modelo: str, timeout_s: float, url: str = URL_OLLAMA,
                 temperatura: float = 0.3, pensar: Optional[bool] = False) -> None:
        self.modelo = modelo
        self.timeout_s = timeout_s
        self.url = url
        self.temperatura = temperatura
        self.pensar = pensar
        #: tiempos de la última respuesta (nanosegundos, como los da Ollama)
        self.ultimos_timings: Dict[str, Any] = {}

    def _post(self, cuerpo: Dict[str, Any], timeout_s: float) -> Dict[str, Any]:
        req = urllib.request.Request(
            self.url, data=json.dumps(cuerpo).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            return json.loads(r.read().decode("utf-8"))

    def cuerpo(self, sistema: str, datos: str, permitidas: Sequence[str]) -> Dict[str, Any]:
        c: Dict[str, Any] = {
            "model": self.modelo,
            "messages": [{"role": "system", "content": sistema},
                         {"role": "user", "content": datos}],
            "stream": False,
            "keep_alive": MANTENER_CARGADO,
            "options": {"temperature": self.temperatura, "num_predict": MAX_TOKENS,
                        "num_ctx": NUM_CTX},
            "format": {
                "type": "object",
                "properties": {"resumen": {"type": "string"},
                               "accion": {"type": "string", "enum": list(permitidas)}},
                "required": ["resumen", "accion"],
                "additionalProperties": False,
            },
        }
        if self.pensar is not None:
            c["think"] = self.pensar
        return c

    def __call__(self, sistema: str, datos: str,
                 permitidas: Sequence[str]) -> Mapping[str, Any]:
        resp = self._post(self.cuerpo(sistema, datos, permitidas), self.timeout_s)
        self.ultimos_timings = {k: resp[k] for k in (
            "total_duration", "load_duration", "prompt_eval_count",
            "prompt_eval_duration", "eval_count", "eval_duration") if k in resp}
        return json.loads(resp["message"]["content"])

    def precalentar(self, timeout_s: float = 180.0) -> bool:
        """Carga el modelo antes de usarlo. No lanza."""
        try:
            self._post({"model": self.modelo, "messages": [],
                        "keep_alive": MANTENER_CARGADO,
                        "options": {"num_ctx": NUM_CTX}}, timeout_s)
            return True
        except Exception:                                 # noqa: BLE001
            return False


__all__ = ["GeneradorOllama", "URL_OLLAMA"]
