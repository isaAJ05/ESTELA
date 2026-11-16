"""Hilo que escucha órdenes de voz y las manda por el camino de los botones.

Solo trabaja cuando la sesión dice que se puede (`Sesion.puede_escuchar`: en
pausa o entre ejercicios y con ESTELA callada). Lo que capta mientras no se
puede se tira, así ESTELA no se oye a sí misma. El texto reconocido pasa por
`comandos_voz.interpretar`: una orden de la lista cerrada, o se pide repetir.
Dolor o lesión: respuesta fija de la entrenadora, sin modelo.

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
                 como_voy: Optional[Callable[[Any], Optional[str]]] = None) -> None:
        """`microfono`: `escuchar_frase(cancelar, espera_s)` y `descartar()`.
        `reconocedor`: `transcribir(audio) -> str`. `acciones`: funciones
        «pausar», «reanudar», «listo», «siguiente», «anterior», «reiniciar» y
        «terminar». `como_voy`: recibe la sesión y da el texto de respuesta a
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
        #: una entrada por frase oída: texto, orden, motivo y milisegundos de reconocimiento
        self.registro: List[Dict[str, Any]] = []

    # -- conexión ---------------------------------------------------------------
    def conectar(self, sesion: Any) -> None:
        """Engancha la escucha a una `Sesion` recién creada y arranca el hilo."""
        self._sesion = sesion
        sesion.oyente = self
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
            if not self._activa and not reciente:
                return None
            return {"activa": self._activa,
                    "texto": self._ultimo["texto"] if reciente else None,
                    "comando": self._ultimo["comando"] if reciente else None,
                    "noEntendi": bool(self._ultimo["noEntendi"]) if reciente else False}

    def _anota(self, texto: Optional[str], comando: Optional[str], no_entendi: bool) -> None:
        with self._cerrojo:
            self._ultimo = {"texto": texto, "comando": comando, "noEntendi": no_entendi,
                            "t": time.monotonic()}

    # -- hilo propio ------------------------------------------------------------
    def _se_puede(self) -> bool:
        s = self._sesion
        return s is not None and bool(s.puede_escuchar)

    def _bucle(self) -> None:
        while not self._parar.is_set():
            if not self._se_puede():
                with self._cerrojo:
                    self._activa = False
                self.microfono.descartar()
                time.sleep(0.1)
                continue
            with self._cerrojo:
                self._activa = True
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
        i = cv.interpretar(texto)
        self.registro.append({"texto": texto, "comando": i.comando, "motivo": i.motivo,
                              "reconocer_ms": round(ms)})
        log.info("Voz: «%s» → %s (%s, %.0f ms)", texto, i.comando, i.motivo, ms)
        if menciona_dolor(texto):
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
        if comando == cv.PAUSA:
            accion = None if en_pausa else "pausar"
        elif comando == cv.SEGUIR:
            accion = "reanudar" if en_pausa else ("listo" if colocando else None)
        elif comando == cv.SIGUIENTE:
            accion = "siguiente"
        elif comando == cv.REPETIR:
            # entre ejercicios se repite el que acaba de terminar; en pausa, el actual
            accion = "anterior" if (colocando and not en_pausa and bool(s.entre_ejercicios)) else "reiniciar"
        else:
            accion = "terminar"
        if cv.CONFIRMACION[comando]:
            self.voz.decir(cv.CONFIRMACION[comando], PRIORIDAD_AVISO)
        if accion is not None and accion in self.acciones:
            self.acciones[accion]()


__all__ = ["EscuchaVoz"]
