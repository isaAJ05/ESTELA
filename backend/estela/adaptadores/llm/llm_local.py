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

Variedad y naturalidad (`variar=True`, pedido de Paula el 2026-11-20: «sigue
repitiendo las mismas cosas en lugar de hacer la misma corrección con palabras
diferentes»). Antes cada llamada mandaba exactamente el mismo mensaje con
temperatura 0,3, así que el modelo devolvía casi siempre la misma frase. Ahora:
  - se le da la plantilla como «lo que hay que pedir» (ancla el sentido: evita
    frases que lo cambian, como «Eleva la pierna» para `sin_salto`);
  - recuerda, por error y lado, las últimas frases dichas y cuántas veces se ha
    corregido, y le pide no repetirlas ni empezar igual;
  - el mensaje de sistema describe el tono de una entrenadora que habla en voz
    alta, con ejemplos de giros variados;
  - temperatura 0,7. El validador sigue igual: lo que cambie la parte del
    cuerpo, el lado o la dirección cae a plantilla. Y además, solo aquí, si el
    error trae dirección y la frase no pide ninguna (un ánimo sin corrección,
    como «Hombro, así, muy bien.»), cae a plantilla (`sin_correccion`). Pedir
    otra dirección compatible vale («baja más la rodilla» por «flexiona»); la
    contraria ya la rechaza el validador.
  - Si la parte es el tronco y trae lado, se le describe como «se inclina
    hacia la derecha» (con «tronco derecho» el modelo lo confundía con «recto»).
`variar=False` reproduce el comportamiento anterior (para comparar).
"""

from __future__ import annotations

import json
import threading
from collections import deque
import time
import urllib.error
import urllib.request
from typing import Any, Deque, Dict, Optional, Tuple

from ...dominio.feedback.contrato import ErrorTipificado, Lado, MensajeFeedback
from ...dominio.feedback.verbalizador.base import Verbalizador
from ...dominio.feedback.verbalizador.plantillas import (
    DIRECCION_ES, LADO_ES, SEGMENTO_ES, VerbalizadorPlantillas,
)
from ...dominio.feedback.verbalizador.validador import direcciones_pedidas, validar

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
#: segundos mínimos entre dos recargas del modelo tras un fallo del servidor
RECARGA_CADA_S = 5.0
#: Ventana de contexto que se pide a Ollama. `[F]` Medido en el Mac Studio el
#: 2026-11-16: sin fijarla, qwen3:4b-instruct se carga con su contexto por
#: defecto (262 144 tokens) y ocupa 43 GB. Aquí el prompt y la respuesta suman
#: unos cientos de tokens.
NUM_CTX = 2048

#: frases dichas que se recuerdan por error y lado (para no repetirlas)
RECORDAR = 3

SISTEMA_ANTERIOR = (
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

SISTEMA = (
    "Eres Estela, una entrenadora personal cercana que corrige en voz alta a "
    "una persona mientras hace ejercicio. Un sistema de medición ya detectó el "
    "error; tú solo lo dices como lo diría una buena entrenadora en persona: "
    "claro, cálido y en español neutro.\n"
    "Reglas estrictas:\n"
    "1. Pide exactamente lo mismo que la frase de referencia, con otras "
    "palabras. No cambies el sentido ni añadas otra corrección.\n"
    "2. Menciona únicamente la parte del cuerpo indicada (o ninguna). Nunca otra.\n"
    "3. Si se indica un lado, nómbralo siempre y exactamente así. Si no, no "
    "menciones lados ni la palabra «derecho» o «derecha». Si la parte es el "
    "tronco, el lado es hacia dónde se inclina: dilo «hacia la derecha» o «hacia "
    "la izquierda», nunca «tronco derecho» (se confunde con «recto»).\n"
    "4. Si se indica la corrección pedida, pídela en ese sentido, nunca en el contrario.\n"
    "5. No diagnostiques ni hables de lesiones, dolor ni riesgo.\n"
    "6. Una sola frase de 4 a 12 palabras, tuteando a la persona, con el "
    "verbo en imperativo bien escrito («baja», «abre», «sube», «estira»; nunca "
    "«bajas», «abré» ni «bajar»). Háblale a ella, nunca a la parte del cuerpo "
    "(«pierna, salta» está mal). La frase siempre debe pedir la corrección: "
    "un ánimo solo («Codo izquierdo, muy bien») no sirve.\n"
    "7. Nada de metáforas ni comparaciones («como si…», «como una…»).\n"
    "8. No repitas las frases ya dichas ni empieces igual que ellas: cambia el "
    "verbo por un sinónimo, el orden o el remate. Puedes abrir con un ánimo "
    "breve («Vamos,», «Casi,», «Eso es,», «Muy bien, ahora») o cerrar con uno "
    "(«¡tú puedes!», «así, muy bien»), pero no siempre.\n"
    "9. Si ya se corrigió varias veces, sé más breve y alentadora, sin regañar.\n"
    "Ejemplos de tono para «Sube la cadera.»: «Vamos, un poco más arriba esa "
    "cadera.», «Eleva la cadera, así, muy bien.», «Casi, sube la cadera.».\n"
    "10. Responde en JSON con la forma {\"mensaje\": \"...\"}."
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
        f"ejercicio: {error.ejercicio_id.replace('_', ' ')}",
        f"parte del cuerpo: {info['sg']}{lado}",
        f"error detectado: {error.error_id}",
        f"severidad: {error.severidad.value}",
        f"fase del movimiento: {error.fase}",
    ]
    if error.direccion is not None:
        lineas.append(f"corrección pedida: {DIRECCION_ES[error.direccion]}")
    return "\n".join(lineas)


def _descripcion_variada(error: ErrorTipificado, referencia: str,
                         dichas: Tuple[str, ...], veces: int) -> str:
    """`_descripcion_error` más la frase de referencia (la plantilla: fija el
    sentido), cuántas veces se corrigió ya y lo ya dicho, para no repetirlo."""
    base = _descripcion_error(error)
    if error.segmento == "tronco" and error.lado in (Lado.IZQUIERDO, Lado.DERECHO):
        hacia = "derecha" if error.lado == Lado.DERECHO else "izquierda"
        base = "\n".join(f"parte del cuerpo: tronco (se inclina hacia la {hacia}; "
                         f"di «hacia la {hacia}»)" if ln.startswith("parte del cuerpo:") else ln
                         for ln in base.split("\n"))
    lineas = [base,
              f"frase de referencia (mismo sentido, otras palabras): «{referencia}»",
              f"veces que ya se corrigió esto en este ejercicio: {veces}"]
    if dichas:
        lineas.append("frases ya dichas (no las repitas ni empieces igual): "
                      + "; ".join(f"«{d}»" for d in dichas))
    return "\n".join(lineas)


class VerbalizadorLLMLocal(Verbalizador):
    """Cliente de `llama-server` (endpoint compatible OpenAI
    `/v1/chat/completions`) o de Ollama (`/api/chat`), según `backend`."""

    def __init__(self,
                 url: Optional[str] = None,
                 modelo: str = "local",
                 restringido: bool = True,
                 timeout_ms: int = 700,
                 temperatura: Optional[float] = None,
                 fallback: Optional[VerbalizadorPlantillas] = None,
                 backend: str = BACKEND_LLAMA,
                 pensar: Optional[bool] = False,
                 variar: bool = True) -> None:
        if backend not in BACKENDS:
            raise ValueError(f"backend desconocido: {backend!r} (use {BACKENDS})")
        self.backend = backend
        self.url = url or (URL_OLLAMA if backend == BACKEND_OLLAMA else URL_LLAMA)
        self.modelo = modelo
        self.restringido = restringido
        self.timeout_ms = timeout_ms
        #: con `variar`, más alta: la misma petición debe dar frases distintas
        self.variar = variar
        self.temperatura = temperatura if temperatura is not None else (0.7 if variar else 0.3)
        #: por (clase de mensaje, ejercicio, lado): últimas frases dichas y cuántas veces
        self._dichas: Dict[Tuple[str, str, str], Deque[str]] = {}
        self._veces: Dict[Tuple[str, str, str], int] = {}
        #: solo Ollama: valor de `think` (None = no enviarlo)
        self.pensar = pensar
        self.fallback = fallback or VerbalizadorPlantillas()
        self.nombre = "F_llm_restringido" if restringido else "Fp_llm_libre"
        #: última información de tiempos devuelta por el servidor, si la hay
        self.ultimos_timings: Dict = {}
        #: cuenta de llamadas y de caídas a plantilla por motivo (para el resumen)
        self.llamadas = 0
        self.caidas: Dict[str, int] = {}
        #: veces que hubo que volver a cargar el modelo tras un fallo del servidor
        self.recargas = 0
        #: última frase del modelo que no pasó la revisión (para medir)
        self.ultimo_rechazado: Optional[str] = None
        self._recargando = threading.Lock()
        self._ult_recarga = float("-inf")

    @staticmethod
    def _clave(error: ErrorTipificado) -> Tuple[str, str, str]:
        return (error.mensaje_id or error.error_id, error.ejercicio_id, str(error.lado.value))

    def _mensajes(self, error: ErrorTipificado) -> list:
        if not self.variar:
            return [{"role": "system", "content": SISTEMA_ANTERIOR},
                    {"role": "user", "content": _descripcion_error(error)}]
        clave = self._clave(error)
        referencia = self.fallback.verbalizar(error).texto
        return [{"role": "system", "content": SISTEMA},
                {"role": "user", "content": _descripcion_variada(
                    error, referencia, tuple(self._dichas.get(clave, ())),
                    self._veces.get(clave, 0))}]

    def _recordar(self, error: ErrorTipificado, texto: str) -> None:
        """Apunta lo que se va a decir (también si cayó a plantilla)."""
        clave = self._clave(error)
        self._dichas.setdefault(clave, deque(maxlen=RECORDAR)).append(texto)
        self._veces[clave] = self._veces.get(clave, 0) + 1

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
            "messages": self._mensajes(error),
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

    def _recargar_en_segundo_plano(self) -> None:
        """Tras un fallo del servidor: vuelve a cargar el modelo sin bloquear.

        `[F]` Medido en el Mac Studio el 2026-11-16: Ollama descarga el modelo
        tras `keep_alive` sin uso; con él descargado, 5 de 5 llamadas con límite
        de 400 ms fallaron por tiempo y el modelo siguió sin cargarse (al cortar
        la espera, la carga se aborta), una llamada paciente lo cargó en 732 ms
        y después 5 de 5 respondieron en 98–133 ms. Es lo que pasó en la sesión
        de Paula de ese día (5 frases, 5 a plantilla por `TimeoutError`). Con
        esto solo cae a plantilla la primera frase tras la descarga.
        """
        if self.backend != BACKEND_OLLAMA:
            return
        ahora = time.monotonic()
        if ahora - self._ult_recarga < RECARGA_CADA_S or not self._recargando.acquire(blocking=False):
            return
        self._ult_recarga = ahora
        self.recargas += 1

        def recargar() -> None:
            try:
                self.precalentar()
            finally:
                self._recargando.release()
        threading.Thread(target=recargar, name="estela-llm-recarga", daemon=True).start()

    def _anota_caida(self, motivo: str) -> None:
        # del validador solo el tipo de rechazo; del servidor, también la excepción
        clave = motivo if motivo.startswith("fallo_backend") else motivo.split(":", 1)[0]
        self.caidas[clave] = self.caidas.get(clave, 0) + 1

    def verbalizar(self, error: ErrorTipificado) -> MensajeFeedback:
        msg = self._verbalizar(error)
        if self.variar:
            self._recordar(error, msg.texto)
        return msg

    def _verbalizar(self, error: ErrorTipificado) -> MensajeFeedback:
        t0 = time.perf_counter()
        self.llamadas += 1
        try:
            texto = self._llamar(error)
        except Exception as exc:  # red, timeout, JSON inválido, todo cae igual
            self._anota_caida(f"fallo_backend:{type(exc).__name__}")
            if isinstance(exc, OSError):          # tiempo o conexión (no una respuesta mal formada)
                self._recargar_en_segundo_plano()
            msg = self.fallback.verbalizar(error)
            return MensajeFeedback(
                texto=msg.texto, error=error, verbalizador=self.nombre,
                latencia_ms=(time.perf_counter() - t0) * 1000.0,
                fallback=True,
                motivo_rechazo=f"fallo_backend:{type(exc).__name__}")

        motivo = ""
        if self.restringido:
            res = validar(texto, error)
            if (res.valido and self.variar and error.direccion is not None
                    and not direcciones_pedidas(texto)):
                res = type(res)(False, "sin_correccion")
            if not res.valido:
                motivo = res.motivo
                self.ultimo_rechazado = texto
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


__all__ = ["VerbalizadorLLMLocal", "ESQUEMA_SALIDA", "SISTEMA", "SISTEMA_ANTERIOR",
           "BACKEND_LLAMA", "BACKEND_OLLAMA", "BACKENDS", "URL_LLAMA", "URL_OLLAMA"]
