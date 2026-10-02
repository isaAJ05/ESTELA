"""Verbalizador F: modelo de lenguaje local con salida restringida.

**Estado: no verificado.** El código está escrito y es ejecutable, pero en
este entorno no hay ningún `llama-server` ni modelo disponible, así que
**no ha sido probado contra un modelo real y no existe ninguna medición de
latencia ni de calidad para esta condición.** Cualquier cifra sobre F en la
documentación del proyecto debe provenir de una ejecución en el hardware del
proyecto, no de aquí.

Diseño (ADR-001, §4.3):

  - Recibe un `ErrorTipificado` ya decidido. **Nunca** recibe ángulos,
    keypoints ni frames, y por tanto no puede decidir qué está mal.
  - `restringido=True` (condición F): se envía `json_schema` para forzar la
    forma de la salida y se pasa el resultado por el validador. Un mensaje
    rechazado cae a plantilla.
  - `restringido=False` (condición F'): control de EXP-001. Sin esquema y
    sin validador, para medir cuánto aporta realmente la restricción.

  `[F]` llama.cpp documenta que el esquema JSON solo restringe la salida y
  **no se inyecta en el prompt**; por eso la estructura se describe también
  en el mensaje de sistema.

  `[?]` El presupuesto de latencia (`timeout_ms`) es un parámetro de diseño
  sin respaldo empírico todavía: hay que fijarlo con la medición de
  `llama-bench` en el M2 Ultra del proyecto (ADR-001, §5).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Dict, Optional

from ..contrato import ErrorTipificado, Lado, MensajeFeedback
from .base import Verbalizador
from .plantillas import LADO_ES, SEGMENTO_ES, VerbalizadorPlantillas
from .validador import validar

ESQUEMA_SALIDA: Dict = {
    "type": "object",
    "properties": {
        "mensaje": {"type": "string", "maxLength": 90},
    },
    "required": ["mensaje"],
    "additionalProperties": False,
}

SISTEMA = (
    "Eres la voz de un asistente de entrenamiento. Recibes un error ya "
    "detectado por un sistema de medición y solo lo pones en palabras.\n"
    "Reglas estrictas:\n"
    "1. Menciona únicamente la parte del cuerpo que se te indica. Ninguna otra.\n"
    "2. Si se te indica un lado, nómbralo exactamente como se te da. Si no se "
    "te indica ninguno, no menciones lados.\n"
    "3. No diagnostiques, no hables de lesiones ni de dolor.\n"
    "4. Una sola frase, máximo 12 palabras, en imperativo y en segunda persona.\n"
    "5. Responde en JSON con la forma {\"mensaje\": \"...\"}."
)


def _descripcion_error(error: ErrorTipificado) -> str:
    info = SEGMENTO_ES.get(error.segmento, {"sg": error.segmento, "genero": "m"})
    lado = ""
    if error.lado in LADO_ES:
        lado = " " + LADO_ES[error.lado][info["genero"]]
    return (
        f"ejercicio: {error.ejercicio_id}\n"
        f"parte del cuerpo: {info['sg']}{lado}\n"
        f"error detectado: {error.error_id}\n"
        f"severidad: {error.severidad.value}\n"
        f"fase del movimiento: {error.fase}"
    )


class VerbalizadorLLMLocal(Verbalizador):
    """Cliente de `llama-server` (endpoint compatible OpenAI `/v1/chat/completions`)."""

    def __init__(self,
                 url: str = "http://127.0.0.1:8080/v1/chat/completions",
                 modelo: str = "local",
                 restringido: bool = True,
                 timeout_ms: int = 700,
                 temperatura: float = 0.3,
                 fallback: Optional[VerbalizadorPlantillas] = None) -> None:
        self.url = url
        self.modelo = modelo
        self.restringido = restringido
        self.timeout_ms = timeout_ms
        self.temperatura = temperatura
        self.fallback = fallback or VerbalizadorPlantillas()
        self.nombre = "F_llm_restringido" if restringido else "Fp_llm_libre"
        #: última información de tiempos devuelta por llama-server, si la hay
        self.ultimos_timings: Dict = {}

    def _cuerpo(self, error: ErrorTipificado) -> Dict:
        cuerpo: Dict = {
            "model": self.modelo,
            "messages": [
                {"role": "system", "content": SISTEMA},
                {"role": "user", "content": _descripcion_error(error)},
            ],
            "temperature": self.temperatura,
            "max_tokens": 48,
        }
        if self.restringido:
            cuerpo["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "feedback", "schema": ESQUEMA_SALIDA},
            }
        return cuerpo

    def _llamar(self, error: ErrorTipificado) -> str:
        datos = json.dumps(self._cuerpo(error)).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=datos,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout_ms / 1000.0) as r:
            resp = json.loads(r.read().decode("utf-8"))
        self.ultimos_timings = resp.get("timings", {})
        contenido = resp["choices"][0]["message"]["content"]
        if self.restringido:
            return json.loads(contenido)["mensaje"]
        return contenido.strip()

    def verbalizar(self, error: ErrorTipificado) -> MensajeFeedback:
        t0 = time.perf_counter()
        try:
            texto = self._llamar(error)
        except Exception as exc:  # red, timeout, JSON inválido, todo cae igual
            msg = self.fallback.verbalizar(error)
            return MensajeFeedback(
                texto=msg.texto, error=error, verbalizador=self.nombre,
                latencia_ms=(time.perf_counter() - t0) * 1000.0,
                fallback=True,
                motivo_rechazo=f"fallo_backend:{type(exc).__name__}")

        motivo = ""
        if self.restringido:
            res = validar(texto, error)
            if not res.valido:
                motivo = res.motivo
                msg = self.fallback.verbalizar(error)
                return MensajeFeedback(
                    texto=msg.texto, error=error, verbalizador=self.nombre,
                    latencia_ms=(time.perf_counter() - t0) * 1000.0,
                    fallback=True, motivo_rechazo=motivo)

        return MensajeFeedback(
            texto=texto, error=error, verbalizador=self.nombre,
            latencia_ms=(time.perf_counter() - t0) * 1000.0,
            fallback=False, motivo_rechazo=motivo)


__all__ = ["VerbalizadorLLMLocal", "ESQUEMA_SALIDA", "SISTEMA"]
