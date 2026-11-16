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

Es un adaptador, no dominio: habla por HTTP con un servidor externo
(`llama-server` u Ollama). Cumple la interfaz `Verbalizador` del dominio y
reutiliza sus plantillas y su validador.

Modo Ollama (`backend="ollama"`, plan del Mac Studio, 2026-11-16):

  - Usa el API nativo `POST /api/chat`. `[F]` La documentación de Ollama
    (docs.ollama.com, «Structured outputs») dice que el campo `format`
    acepta `"json"` o un esquema JSON, y recomienda describir además el
    esquema en el prompt y bajar la temperatura. Aquí se envía
    `ESQUEMA_SALIDA` en `format`; el mensaje de sistema ya describe la forma.
  - `[F]` `think: false` pide que no haya razonamiento («Thinking» en la
    misma documentación); sin él, un modelo como qwen3 gasta el presupuesto
    de tokens pensando. Se envía siempre salvo `pensar=None`.
  - `stream: false`: la respuesta llega entera, y `timeout_ms` (tiempo de
    espera del socket) actúa de tiempo límite de la llamada.
  - `precalentar()` carga el modelo antes de la sesión: la primera llamada
    tras cargar tarda segundos y caería siempre a plantilla.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from ...dominio.feedback.contrato import ErrorTipificado, Lado, MensajeFeedback
from ...dominio.feedback.verbalizador.base import Verbalizador
from ...dominio.feedback.verbalizador.plantillas import (
    DIRECCION_ES, LADO_ES, SEGMENTO_ES, VerbalizadorPlantillas,
)
from ...dominio.feedback.verbalizador.validador import validar

ESQUEMA_SALIDA: Dict = {
    "type": "object",
    "properties": {
        "mensaje": {"type": "string", "maxLength": 90},
    },
    "required": ["mensaje"],
    "additionalProperties": False,
}

BACKEND_LLAMA = "llama-server"
BACKEND_OLLAMA = "ollama"
BACKENDS = (BACKEND_LLAMA, BACKEND_OLLAMA)
URL_LLAMA = "http://127.0.0.1:8080/v1/chat/completions"
URL_OLLAMA = "http://127.0.0.1:11434/api/chat"
#: tope de tokens de la respuesta (12 palabras caben de sobra)
MAX_TOKENS = 48
#: cuánto deja Ollama el modelo en memoria tras la última llamada. El defecto
#: de Ollama (5 min) puede vencer entre dos correcciones de una misma sesión.
MANTENER_CARGADO = "30m"
#: Ventana de contexto que se pide a Ollama. `[F]` Medido en el Mac Studio el
#: 2026-11-16: sin fijarla, qwen3:4b-instruct se carga con su contexto por
#: defecto (262 144 tokens) y ocupa 43 GB. Aquí el prompt y la respuesta suman
#: unos cientos de tokens.
NUM_CTX = 2048

SISTEMA = (
    "Eres la voz de un asistente de entrenamiento. Recibes un error ya "
    "detectado por un sistema de medición y solo lo pones en palabras.\n"
    "Reglas estrictas:\n"
    "1. Menciona únicamente la parte del cuerpo que se te indica. Ninguna otra.\n"
    "2. Si se te indica un lado, nómbralo exactamente como se te da. Si no se "
    "te indica ninguno, no menciones lados.\n"
    "3. No diagnostiques, no hables de lesiones ni de dolor.\n"
    "4. Una sola frase, máximo 12 palabras, en imperativo y en segunda persona.\n"
    "5. Si se te indica la corrección pedida, pídela en ese sentido y nunca en "
    "el contrario. Si no se indica, no inventes hacia dónde corregir.\n"
    "6. Responde en JSON con la forma {\"mensaje\": \"...\"}."
)


def _descripcion_error(error: ErrorTipificado) -> str:
    """Lo único que el modelo sabe del error.

    Incluye `direccion` (ADR-004 §2.5): el motor ya sabe hacia dónde corregir
    y el modelo no debe adivinarlo. **No** incluye `magnitud`: es el exceso
    sobre un umbral sin calibrar `[?]` y el modelo podría convertirlo en una
    cifra hablada («baja 30 grados») que nada verifica; la severidad ya dice
    cuánto corregir. Reconsiderar tras EXP-005.
    """
    info = SEGMENTO_ES.get(error.segmento, {"sg": error.segmento, "genero": "m"})
    lado = ""
    if error.lado in LADO_ES:
        lado = " " + LADO_ES[error.lado][info["genero"]]
    lineas = [
        f"ejercicio: {error.ejercicio_id}",
        f"parte del cuerpo: {info['sg']}{lado}",
        f"error detectado: {error.error_id}",
        f"severidad: {error.severidad.value}",
        f"fase del movimiento: {error.fase}",
    ]
    if error.direccion is not None:
        lineas.append(f"corrección pedida: {DIRECCION_ES[error.direccion]}")
    return "\n".join(lineas)


class VerbalizadorLLMLocal(Verbalizador):
    """Cliente de `llama-server` (endpoint compatible OpenAI
    `/v1/chat/completions`) o de Ollama (`/api/chat`), según `backend`."""

    def __init__(self,
                 url: Optional[str] = None,
                 modelo: str = "local",
                 restringido: bool = True,
                 timeout_ms: int = 700,
                 temperatura: float = 0.3,
                 fallback: Optional[VerbalizadorPlantillas] = None,
                 backend: str = BACKEND_LLAMA,
                 pensar: Optional[bool] = False) -> None:
        if backend not in BACKENDS:
            raise ValueError(f"backend desconocido: {backend!r} (use {BACKENDS})")
        self.backend = backend
        self.url = url or (URL_OLLAMA if backend == BACKEND_OLLAMA else URL_LLAMA)
        self.modelo = modelo
        self.restringido = restringido
        self.timeout_ms = timeout_ms
        self.temperatura = temperatura
        #: solo Ollama: valor de `think` (None = no enviarlo)
        self.pensar = pensar
        self.fallback = fallback or VerbalizadorPlantillas()
        self.nombre = "F_llm_restringido" if restringido else "Fp_llm_libre"
        #: última información de tiempos devuelta por el servidor, si la hay
        self.ultimos_timings: Dict = {}
        #: cuenta de llamadas y de caídas a plantilla por motivo (para el resumen)
        self.llamadas = 0
        self.caidas: Dict[str, int] = {}

    def _mensajes(self, error: ErrorTipificado) -> list:
        return [{"role": "system", "content": SISTEMA},
                {"role": "user", "content": _descripcion_error(error)}]

    def _cuerpo_ollama(self, error: ErrorTipificado) -> Dict:
        cuerpo: Dict[str, Any] = {
            "model": self.modelo,
            "messages": self._mensajes(error),
            "stream": False,
            "keep_alive": MANTENER_CARGADO,
            "options": {"temperature": self.temperatura,
                        "num_predict": MAX_TOKENS, "num_ctx": NUM_CTX},
        }
        if self.pensar is not None:
            cuerpo["think"] = self.pensar
        if self.restringido:
            cuerpo["format"] = ESQUEMA_SALIDA
        return cuerpo

    def _cuerpo(self, error: ErrorTipificado) -> Dict:
        if self.backend == BACKEND_OLLAMA:
            return self._cuerpo_ollama(error)
        cuerpo: Dict = {
            "model": self.modelo,
            "messages": [
                {"role": "system", "content": SISTEMA},
                {"role": "user", "content": _descripcion_error(error)},
            ],
            "temperature": self.temperatura,
            "max_tokens": MAX_TOKENS,
        }
        if self.restringido:
            cuerpo["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "feedback", "schema": ESQUEMA_SALIDA},
            }
        return cuerpo

    def _post(self, cuerpo: Dict, timeout_s: float) -> Dict:
        req = urllib.request.Request(
            self.url, data=json.dumps(cuerpo).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            return json.loads(r.read().decode("utf-8"))

    def _llamar(self, error: ErrorTipificado) -> str:
        resp = self._post(self._cuerpo(error), self.timeout_ms / 1000.0)
        if self.backend == BACKEND_OLLAMA:
            # duraciones en nanosegundos, tal como las da Ollama
            self.ultimos_timings = {k: resp[k] for k in (
                "total_duration", "load_duration", "prompt_eval_count",
                "prompt_eval_duration", "eval_count", "eval_duration")
                if k in resp}
            contenido = resp["message"]["content"]
        else:
            self.ultimos_timings = resp.get("timings", {})
            contenido = resp["choices"][0]["message"]["content"]
        if self.restringido:
            return json.loads(contenido)["mensaje"]
        return contenido.strip()

    def precalentar(self, timeout_s: float = 120.0) -> bool:
        """Carga el modelo en el servidor antes de la sesión. No lanza.

        Solo hace algo con Ollama: una petición sin mensajes carga el modelo
        `[F]` (documentación del API, «Load a model»). Devuelve si respondió.
        """
        if self.backend != BACKEND_OLLAMA:
            return False
        try:
            self._post({"model": self.modelo, "messages": [],
                        "keep_alive": MANTENER_CARGADO,
                        "options": {"num_ctx": NUM_CTX}}, timeout_s)
            return True
        except Exception:                                 # noqa: BLE001
            return False

    def _anota_caida(self, motivo: str) -> None:
        # del validador solo el tipo de rechazo; del servidor, también la excepción
        clave = motivo if motivo.startswith("fallo_backend") else motivo.split(":", 1)[0]
        self.caidas[clave] = self.caidas.get(clave, 0) + 1

    def verbalizar(self, error: ErrorTipificado) -> MensajeFeedback:
        t0 = time.perf_counter()
        self.llamadas += 1
        try:
            texto = self._llamar(error)
        except Exception as exc:  # red, timeout, JSON inválido, todo cae igual
            self._anota_caida(f"fallo_backend:{type(exc).__name__}")
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
                self._anota_caida(motivo)
                msg = self.fallback.verbalizar(error)
                return MensajeFeedback(
                    texto=msg.texto, error=error, verbalizador=self.nombre,
                    latencia_ms=(time.perf_counter() - t0) * 1000.0,
                    fallback=True, motivo_rechazo=motivo)

        return MensajeFeedback(
            texto=texto, error=error, verbalizador=self.nombre,
            latencia_ms=(time.perf_counter() - t0) * 1000.0,
            fallback=False, motivo_rechazo=motivo)


__all__ = ["VerbalizadorLLMLocal", "ESQUEMA_SALIDA", "SISTEMA",
           "BACKEND_LLAMA", "BACKEND_OLLAMA", "BACKENDS", "URL_LLAMA", "URL_OLLAMA"]
