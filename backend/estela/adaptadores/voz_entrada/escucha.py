"""Hilo que escucha órdenes de voz y las manda por el camino de los botones.

Solo trabaja cuando la sesión dice que se puede (`Sesion.puede_escuchar`; con
ESTELA callada). Lo que capta mientras no se puede se tira, así ESTELA no se
oye a sí misma. El texto reconocido pasa por `comandos_voz.interpretar`: una
orden de la lista cerrada, o se pide repetir. Dolor o lesión: respuesta fija
de la entrenadora, sin modelo.

Dos modos:
- `llamada=False` (primera versión): se escucha solo en pausa y entre ejercicios
  y se interpreta todo lo que se oye.
- `llamada=True` (estilo asistente de voz): se escucha también durante el
  ejercicio, pero solo cuenta lo que empieza por «Estela» u «Oye Estela»; lo
  demás se ignora en silencio (no se dice «no te entendí» a una conversación).
  Si solo dice «Estela», la frase siguiente cuenta como orden unos segundos.
  «Reiniciar sesión» pide confirmación. De lo ignorado se guarda solo cuántas
  palabras y cuánto tardó, **nunca el texto** (podría ser una conversación);
  el texto sale únicamente en el registro de depuración (`-v`).

La orden no toca la sesión desde este hilo: llama a `acciones`, que son las
mismas funciones de los botones (en la interfaz, la cola del orquestador).
`estado()` da lo que la pantalla muestra: si escucha y qué entendió.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Mapping, Optional

from ...aplicacion import comandos_voz as cv
from ...aplicacion.entrenadora import RESPUESTA_DOLOR, menciona_dolor
from ...aplicacion.puertos import PRIORIDAD_AVISO, Voz

log = logging.getLogger(__name__)

#: segundos que la pantalla sigue mostrando lo último que se entendió
MOSTRAR_S = 4.0
#: no pedir repetir más de una vez cada tantos segundos
REPETIR_CADA_S = 6.0


class EscuchaVoz:
    def __init__(self, microfono: Any, reconocedor: Any, voz: Voz,
                 acciones: Mapping[str, Callable[[], None]],
                 como_voy: Optional[Callable[[Any], Optional[str]]] = None,
                 llamada: bool = False) -> None:
        """`microfono`: `escuchar_frase(cancelar, espera_s)` y `descartar()`.
        `reconocedor`: `transcribir(audio) -> str`. `acciones`: funciones
        «pausar», «reanudar», «listo», «siguiente», «anterior», «reiniciar» y
        «terminar»; con `llamada` también «reiniciar_sesion», «reconocer_si» y
        «reconocer_no». `como_voy`: recibe la sesión y da el texto de respuesta a
        «¿cómo voy?» (puede tardar: corre en este hilo, no en el de la sesión)."""
        self.microfono, self.reconocedor, self.voz = microfono, reconocedor, voz
        self.acciones, self.como_voy = acciones, como_voy
        self._sesion: Any = None
        self._parar = threading.Event()
        self._hilo: Optional[threading.Thread] = None
        self._cerrojo = threading.Lock()
        self._activa = False
        self._ultimo: Dict[str, Any] = {"texto": None, "comando": None, "noEntendi": False, "t": 0.0}
        self._ult_repetir = 0.0
        self.llamada = llamada
        #: tras decir solo «Estela», hasta cuándo (monotonic) la frase siguiente cuenta
        self._ventana_hasta = 0.0
        #: orden que espera un sí o un no, y hasta cuándo
        self._pendiente: Optional[str] = None
        self._pendiente_hasta = 0.0
        #: lo último que se pidió cambiar en pantalla por voz; `n` sube con cada orden
        self._pantalla: Dict[str, Any] = {"angulos": None, "n": 0}
        self.ignoradas = 0
        #: una entrada por frase oída: texto, orden, motivo y milisegundos de reconocimiento
        self.registro: List[Dict[str, Any]] = []

    # -- conexión ---------------------------------------------------------------
    def conectar(self, sesion: Any) -> None:
        """Engancha la escucha a una `Sesion` recién creada y arranca el hilo."""
        self._sesion = sesion
        sesion.oyente = self
        sesion.escucha_siempre = self.llamada
        if self._hilo is None or not self._hilo.is_alive():
            self._parar.clear()
            self._hilo = threading.Thread(target=self._bucle, name="estela-escucha", daemon=True)
            self._hilo.start()

    def cerrar(self) -> None:
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(timeout=3.0)
        cerrar = getattr(self.microfono, "cerrar", None)
        if cerrar is not None:
            cerrar()

    # -- lo que muestra la pantalla (lo lee el hilo de la sesión) ----------------
    def estado(self) -> Optional[Dict[str, Any]]:
        with self._cerrojo:
            reciente = time.monotonic() - self._ultimo["t"] < MOSTRAR_S
            hay_pantalla = self._pantalla["n"] > 0
            if not self._activa and not reciente and not hay_pantalla:
                return None
            estado: Dict[str, Any] = {
                "activa": self._activa,
                "texto": self._ultimo["texto"] if reciente else None,
                "comando": self._ultimo["comando"] if reciente else None,
                "noEntendi": bool(self._ultimo["noEntendi"]) if reciente else False}
            if self.llamada:
                estado["llamada"] = True
            if hay_pantalla:
                estado["pantalla"] = dict(self._pantalla)
            return estado

    def _anota(self, texto: Optional[str], comando: Optional[str], no_entendi: bool) -> None:
        with self._cerrojo:
            self._ultimo = {"texto": texto, "comando": comando, "noEntendi": no_entendi,
                            "t": time.monotonic()}

    # -- hilo propio ------------------------------------------------------------
    def _se_puede(self) -> bool:
        s = self._sesion
        return s is not None and bool(s.puede_escuchar)

    def _indicador(self) -> bool:
        """¿Se muestra «Te escucho»? En modo «llamada» se escucha todo el rato,
        pero el aviso solo sale cuando es un buen momento para hablar (pausa,
        colocación) o tras decir «Estela»; durante el ejercicio no estorba."""
        if not self.llamada:
            return True
        ahora = time.monotonic()
        if ahora < self._ventana_hasta or (self._pendiente is not None
                                           and ahora < self._pendiente_hasta):
            return True
        p = self._sesion.paso_actual if self._sesion is not None else None
        return p is None or bool(p.pausa.pausada or p.colocando)

    def _bucle(self) -> None:
        while not self._parar.is_set():
            if not self._se_puede():
                with self._cerrojo:
                    self._activa = False
                self.microfono.descartar()
                time.sleep(0.1)
                continue
            with self._cerrojo:
                self._activa = self._indicador()
            try:
                audio = self.microfono.escuchar_frase(
                    cancelar=lambda: self._parar.is_set() or not self._se_puede())
                if audio is None or not self._se_puede():
                    continue                      # nada, o ESTELA empezó a hablar: se descarta
                self.atender(audio)
            except Exception:                             # noqa: BLE001
                log.exception("fallo en la escucha de voz")
                time.sleep(0.5)

    def atender(self, audio: Any) -> cv.Interpretacion:
        """Una frase ya cortada: reconocer, interpretar y actuar."""
        t0 = time.perf_counter()
        texto = (self.reconocedor.transcribir(audio) or "").strip()
        ms = (time.perf_counter() - t0) * 1000.0
        orden = texto
        if self.llamada:
            ya = self._filtrar_llamada(texto, ms)
            if isinstance(ya, cv.Interpretacion):
                return ya
            orden = ya
        i = cv.interpretar(orden)
        self.registro.append({"texto": texto, "comando": i.comando, "motivo": i.motivo,
                              "reconocer_ms": round(ms)})
        log.info("Voz: «%s» → %s (%s, %.0f ms)", texto, i.comando, i.motivo, ms)
        if menciona_dolor(orden):
            self._anota(texto, None, False)
            self.voz.decir(RESPUESTA_DOLOR, PRIORIDAD_AVISO)
            self.registro[-1]["motivo"] = "dolor"
            return i
        if i.comando is not None:
            self._anota(texto, i.comando, False)
            self._ejecutar(i.comando)
        elif i.pedir_repetir:
            self._anota(texto, None, True)
            if time.monotonic() - self._ult_repetir > REPETIR_CADA_S:
                self._ult_repetir = time.monotonic()
                self.voz.decir(cv.NO_ENTENDI, PRIORIDAD_AVISO)
        return i

    def _filtrar_llamada(self, texto: str, ms: float) -> Any:
        """Modo «llamada». Devuelve el texto que hay que interpretar como orden
        o, si la frase ya quedó resuelta (ignorada, solo «Estela», un sí o un
        no), la `Interpretacion` con la que `atender` termina."""
        ahora = time.monotonic()
        llamado, resto = cv.separar_llamada(texto)
        esperando_si = self._pendiente is not None and ahora < self._pendiente_hasta
        if self._pendiente is not None and not esperando_si:
            self._pendiente = None
        if esperando_si:
            respuesta = cv.respuesta_de_confirmacion(resto if llamado else texto)
            if respuesta is not None:
                return self._resolver_pregunta(respuesta, texto, ms)
            if not llamado:
                return self._ignorar(texto, ms)       # ruido mientras espera el sí
            self._pendiente = None                    # le habló de otra cosa: se cancela
        if not llamado and ahora >= self._ventana_hasta:
            return self._ignorar(texto, ms)
        self._ventana_hasta = 0.0
        if llamado and not resto:
            self._ventana_hasta = ahora + cv.VENTANA_LLAMADA_S
            self.registro.append({"texto": texto, "comando": None, "motivo": cv.SOLO_LLAMADA,
                                  "reconocer_ms": round(ms)})
            self._anota(texto, None, False)
            return cv.Interpretacion(None, cv.SOLO_LLAMADA, "")
        return resto if llamado else cv._limpiar(texto)

    def _ignorar(self, texto: str, ms: float) -> cv.Interpretacion:
        """Frase sin «Estela»: no se dice ni se muestra nada. Se guarda solo
        cuántas palabras tenía, no qué decía."""
        self.ignoradas += 1
        self.registro.append({"texto": None, "comando": None, "motivo": cv.SIN_LLAMADA,
                              "palabras": len(texto.split()), "reconocer_ms": round(ms)})
        log.debug("Voz ignorada (sin «Estela»): «%s»", texto)
        return cv.Interpretacion(None, cv.SIN_LLAMADA, "")

    def _resolver_pregunta(self, si: bool, texto: str, ms: float) -> cv.Interpretacion:
        orden, self._pendiente = self._pendiente, None
        self.registro.append({"texto": texto, "comando": orden if si else None,
                              "motivo": "confirmado" if si else "cancelado",
                              "reconocer_ms": round(ms)})
        if si and orden == cv.REINICIAR_SESION:
            self._anota(texto, orden, False)
            self.voz.decir(cv.CONFIRMA_REINICIAR, PRIORIDAD_AVISO)
            if "reiniciar_sesion" in self.acciones:
                self.acciones["reiniciar_sesion"]()
        return cv.Interpretacion(orden if si else None, cv.ENTENDIDO, "")

    def _ejecutar(self, comando: str) -> None:
        s = self._sesion
        p = s.paso_actual if s is not None else None
        en_pausa = bool(p is not None and p.pausa.pausada)
        colocando = bool(p is not None and p.colocando)
        if comando == cv.COMO_VOY:
            texto = self.como_voy(s) if self.como_voy is not None else None
            if texto and self._se_puede():        # si ya se reanudó, no se habla encima
                self.voz.decir(texto, PRIORIDAD_AVISO)
            return
        if comando == cv.REINICIAR_SESION:        # borra el avance: antes pide confirmación
            self._pendiente = cv.REINICIAR_SESION
            self._pendiente_hasta = time.monotonic() + cv.VENTANA_CONFIRMACION_S
            self.voz.decir(cv.PREGUNTA_REINICIAR, PRIORIDAD_AVISO)
            return
        if comando in (cv.ANGULOS_SI, cv.ANGULOS_NO):  # lo aplica la pantalla al ver el estado
            with self._cerrojo:
                self._pantalla = {"angulos": comando == cv.ANGULOS_SI,
                                  "n": self._pantalla["n"] + 1}
            accion = None
        elif comando == cv.PAUSA:
            accion = None if en_pausa else "pausar"
        elif comando == cv.SEGUIR:
            accion = "reanudar" if en_pausa else ("listo" if colocando else None)
        elif comando == cv.SIGUIENTE:
            accion = "siguiente"
        elif comando == cv.ANTERIOR:
            accion = "anterior"
        elif comando == cv.REINICIAR_EJERCICIO:
            accion = "reiniciar"
        elif comando == cv.REPETIR:
            # entre ejercicios se repite el que acaba de terminar; en pausa, el actual
            accion = "anterior" if (colocando and not en_pausa and bool(s.entre_ejercicios)) else "reiniciar"
        elif comando in (cv.RECONOCER_SI, cv.RECONOCER_NO):
            accion = comando
        else:
            accion = "terminar"
        if cv.CONFIRMACION[comando] and (accion is not None or comando in cv.ORDENES_DE_AJUSTE):
            self.voz.decir(cv.CONFIRMACION[comando], PRIORIDAD_AVISO)
        if accion is not None and accion in self.acciones:
            self.acciones[accion]()


__all__ = ["EscuchaVoz"]
