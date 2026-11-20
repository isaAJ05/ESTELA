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

Modo «interrumpir» (`interrumpir_hablando=True`, solo con `llamada`): también se
escucha mientras ESTELA habla, para cortarla con «Estela, pausa». Su voz entra
en el micrófono, así que en ese rato no se corta por frases (su voz también
cuenta como voz): cada segundo se reconocen los últimos 2,5 s (`escuchar_ventana`)
y se busca «Estela» en cualquier punto. Lo que dice la usuaria manda sobre lo
que ESTELA tenía que decir (pedido de Paula, 2026-11-20): al oír «Estela», ESTELA
se calla al momento y le cede el turno (`ColaVoz.ceder`); si venía una orden
(cualquiera) se ejecuta, y si no, queda atenta unos segundos a la orden, como
tras decir «Estela» a secas. `[?]` Sin medir con micrófono real: el eco de su
propia voz y cuánto se entiende la orden por encima de ella.

Turno de la usuaria (`_ceder`): tras oír «Estela» (hablando ESTELA o no),
ESTELA no empieza frases nuevas hasta que llega la orden o pasa la ventana de
`VENTANA_LLAMADA_S`; las correcciones de ese rato se tiran.

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
from ...aplicacion.puertos import PRIORIDAD_AVISO, PRIORIDAD_URGENTE, Voz

log = logging.getLogger(__name__)

#: segundos que la pantalla sigue mostrando lo último que se entendió
MOSTRAR_S = 4.0
#: no pedir repetir más de una vez cada tantos segundos
REPETIR_CADA_S = 6.0
#: modo «interrumpir»: audio que se reconoce de una vez y cada cuánto, y pausa
#: tras actuar para no ejecutar dos veces la misma orden (ventanas solapadas)
VENTANA_S, PASO_S, ENFRIAR_S = 2.5, 1.0, 2.0
#: si la ventana que oyó «Estela» no traía la orden, segundos más que se escuchan
#: (ESTELA ya callada) y se reconocen junto con ella: la orden suele quedar
#: partida entre dos ventanas (Paula, 2026-11-20: «se calla pero no sigue la orden»)
CONTINUAR_S = 1.5


class EscuchaVoz:
    def __init__(self, microfono: Any, reconocedor: Any, voz: Voz,
                 acciones: Mapping[str, Callable[[], None]],
                 como_voy: Optional[Callable[[Any], Optional[str]]] = None,
                 llamada: bool = False, guarda_eco_s: float = 0.0,
                 abrir_microfono: Optional[Callable[[Optional[int]], Any]] = None,
                 interrumpir_hablando: bool = False) -> None:
        """`microfono`: `escuchar_frase(cancelar, espera_s)` y `descartar()`; None si
        se abrirá después con `abrir_microfono(dispositivo)`. Con esa fábrica el
        micrófono se puede apagar de verdad (se cierra), encender y cambiar por otro.
        `reconocedor`: `transcribir(audio) -> str`. `acciones`: funciones
        «pausar», «reanudar», «listo», «siguiente», «anterior», «reiniciar» y
        «terminar»; con `llamada` también «reiniciar_sesion», «reconocer_si»,
        «reconocer_no», «voz_si» y «voz_no». `como_voy`: recibe la sesión y da el texto de respuesta a
        «¿cómo voy?» (puede tardar: corre en este hilo, no en el de la sesión)."""
        self.microfono, self.reconocedor, self.voz = microfono, reconocedor, voz
        self.acciones, self.como_voy = acciones, como_voy
        self._abrir = abrir_microfono
        #: lo que se quiere: escuchar o no, y con qué entrada (None: la de defecto).
        #: Lo aplica el hilo de la escucha (`_aplicar_cambios`), que es el dueño del micrófono.
        self._encendida = True
        self._dispositivo: Optional[int] = getattr(microfono, "dispositivo", None)
        self._hay_cambios = threading.Event()
        if microfono is None:
            self._hay_cambios.set()                 # abrirlo al arrancar
        self._error_microfono: Optional[str] = None
        #: prueba desde los ajustes: hasta cuándo, y lo último que se oyó en ella
        self._prueba_hasta = 0.0
        self._prueba: Optional[Dict[str, Any]] = None
        self._sesion: Any = None
        self._parar = threading.Event()
        self._hilo: Optional[threading.Thread] = None
        self._cerrojo = threading.Lock()
        self._activa = False
        self._ultimo: Dict[str, Any] = {"texto": None, "comando": None, "noEntendi": False, "t": 0.0}
        self._ult_repetir = 0.0
        self.llamada = llamada
        #: escuchar también mientras ESTELA habla (solo con `llamada`)
        self.interrumpir_hablando = bool(interrumpir_hablando and llamada)
        self._enfriar_hasta = 0.0
        #: ventanas reconocidas mientras ESTELA hablaba, y cuántas traían «Estela»
        self.ventanas = 0
        self.ventanas_con_llamada = 0
        #: tras callar ESTELA, estos segundos más se sigue tirando el audio (eco de su voz)
        self.guarda_eco_s = max(0.0, float(guarda_eco_s))
        self._ult_habla = float("-inf")
        #: tras decir solo «Estela», hasta cuándo (monotonic) la frase siguiente cuenta
        self._ventana_hasta = 0.0
        #: orden que espera un sí o un no, y hasta cuándo
        self._pendiente: Optional[str] = None
        self._pendiente_hasta = 0.0
        #: lo último que se pidió cambiar en pantalla por voz; `n` sube con cada orden
        #: `angulos`, `reconocer` y `voz`: solo el ajuste pedido en esa orden lleva valor
        self._pantalla: Dict[str, Any] = {"angulos": None, "reconocer": None, "voz": None, "n": 0}
        self.ignoradas = 0
        marcar = getattr(voz, "no_repetibles", None)
        if marcar is not None:
            marcar(cv.frases_propias())            # «repite eso» no repite las confirmaciones
        #: una entrada por frase oída: texto, orden, motivo y milisegundos de reconocimiento
        self.registro: List[Dict[str, Any]] = []

    # -- conexión ---------------------------------------------------------------
    def arrancar(self) -> None:
        """Arranca el hilo (si no corre). Sin sesión no atiende órdenes, pero
        ya se puede probar el micrófono desde los ajustes."""
        if self._hilo is None or not self._hilo.is_alive():
            self._parar.clear()
            self._hilo = threading.Thread(target=self._bucle, name="estela-escucha", daemon=True)
            self._hilo.start()

    def conectar(self, sesion: Any) -> None:
        """Engancha la escucha a una `Sesion` recién creada y arranca el hilo."""
        self._sesion = sesion
        sesion.oyente = self
        sesion.escucha_siempre = self.llamada
        sesion.escucha_hablando = self.interrumpir_hablando
        self.arrancar()

    # -- ajustes del micrófono (los llama la interfaz desde otro hilo) -------------
    def encender(self, encendida: bool) -> None:
        """Enciende o apaga la voz de entrada. Apagada, el micrófono se cierra
        (si se puede volver a abrir) y no se escucha nada."""
        with self._cerrojo:
            self._encendida = bool(encendida)
        self._hay_cambios.set()

    def elegir_microfono(self, dispositivo: Optional[int]) -> None:
        """Cambia de entrada (índice de `listar_microfonos`; None: la de defecto)."""
        with self._cerrojo:
            self._dispositivo = dispositivo
        self._hay_cambios.set()

    def probar(self, segundos: float = 8.0) -> bool:
        """Durante `segundos` muestra en los ajustes lo que oye y qué entendería,
        sin ejecutar ninguna orden ni guardarlo. False si el micrófono está apagado."""
        if not self._encendida:
            return False
        with self._cerrojo:
            self._prueba = None
            self._prueba_hasta = time.monotonic() + max(1.0, float(segundos))
        self.arrancar()
        return True

    def _probando(self) -> bool:
        return time.monotonic() < self._prueba_hasta

    def ajustes(self) -> Dict[str, Any]:
        """Para la sección «Micrófono» de los ajustes."""
        mic = self.microfono
        with self._cerrojo:
            return {"encendido": self._encendida and mic is not None,
                    "elegido": self._dispositivo,
                    "nombre": getattr(mic, "nombre", None),
                    "nivel": round(min(1.0, float(getattr(mic, "nivel", 0.0) or 0.0)), 4),
                    "probando": self._probando(),
                    "prueba": dict(self._prueba) if self._prueba else None,
                    "error": self._error_microfono,
                    "llamada": self.llamada}

    def indicador(self) -> Dict[str, bool]:
        """Para el punto del micrófono en pantalla: si está encendido, si ahora
        mismo escucha (no mientras habla ESTELA) y si oyó «Estela» y espera la orden."""
        encendido = self._encendida and self.microfono is not None
        ahora = time.monotonic()
        atenta = self.llamada and (ahora < self._ventana_hasta or (
            self._pendiente is not None and ahora < self._pendiente_hasta))
        return {"encendido": encendido,
                "escuchando": bool(encendido and self._se_puede() and not self._en_guarda_de_eco()),
                "atenta": bool(encendido and atenta)}

    def _aplicar_cambios(self) -> None:
        """En el hilo de la escucha: abre, cierra o cambia el micrófono según lo pedido."""
        if not self._hay_cambios.is_set():
            return
        self._hay_cambios.clear()
        with self._cerrojo:
            quiero, dispositivo = self._encendida, self._dispositivo
        if self._abrir is None:                      # micrófono fijo: solo se deja de escuchar
            return
        mic = self.microfono
        if mic is not None and (not quiero or getattr(mic, "dispositivo", None) != dispositivo):
            cerrar = getattr(mic, "cerrar", None)
            if cerrar is not None:
                cerrar()
            self.microfono = None
        if quiero and self.microfono is None:
            try:
                self.microfono = self._abrir(dispositivo)
                self._error_microfono = None
            except Exception as exc:                  # noqa: BLE001 — sin micrófono se sigue sin voz
                log.warning("No se pudo abrir el micrófono: %s: %s", type(exc).__name__, exc)
                self._error_microfono = f"{type(exc).__name__}: {exc}"
                with self._cerrojo:
                    self._encendida = False

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

    def _mostrar_te_escucho(self) -> bool:
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

    def _en_guarda_de_eco(self) -> bool:
        """ESTELA habló hace menos de `guarda_eco_s`: lo que se capta aún puede ser su eco."""
        if getattr(self.voz, "ocupada", False):
            self._ult_habla = time.monotonic()
        return self.guarda_eco_s > 0 and time.monotonic() - self._ult_habla < self.guarda_eco_s

    def _bucle(self) -> None:
        while not self._parar.is_set():
            self._aplicar_cambios()
            mic = self.microfono
            if mic is None or not self._encendida:
                with self._cerrojo:
                    self._activa = False
                if mic is not None:
                    mic.descartar()
                time.sleep(0.1)
                continue
            probando = self._probando()
            if not probando and (not self._se_puede() or self._en_guarda_de_eco()):
                with self._cerrojo:
                    self._activa = False
                mic.descartar()
                time.sleep(0.1)
                continue
            with self._cerrojo:
                self._activa = False if probando else self._mostrar_te_escucho()
            if not probando and self._hablando_ahora() and hasattr(mic, "escuchar_ventana"):
                try:
                    audio = mic.escuchar_ventana(
                        cancelar=lambda: (self._parar.is_set() or self._hay_cambios.is_set()
                                          or not self._se_puede() or not self._hablando_ahora()),
                        ventana_s=VENTANA_S, paso_s=PASO_S)
                    if audio is not None and time.monotonic() >= self._enfriar_hasta:
                        self.atender_hablando(audio)
                except Exception:                         # noqa: BLE001
                    log.exception("fallo en la escucha mientras habla ESTELA")
                    time.sleep(0.5)
                continue
            try:
                audio = mic.escuchar_frase(
                    cancelar=lambda: (self._parar.is_set() or self._hay_cambios.is_set()
                                      or not (self._probando() or self._se_puede())
                                      or (not self._probando() and self._hablando_ahora())))
                if audio is None:
                    continue
                if self._probando():
                    self._atender_prueba(audio)
                elif self._se_puede():                # si ESTELA empezó a hablar, se descarta
                    self.atender(audio)
            except Exception:                             # noqa: BLE001
                log.exception("fallo en la escucha de voz")
                time.sleep(0.5)

    def _hablando_ahora(self) -> bool:
        """¿Toca el modo de ventanas? Solo con «interrumpir» y mientras ESTELA habla."""
        return self.interrumpir_hablando and bool(getattr(self.voz, "ocupada", False))

    def _ceder(self, segundos: float) -> None:
        """Da (o devuelve, con 0) el turno a la usuaria en la cola de voz."""
        ceder = getattr(self.voz, "ceder", None)
        if ceder is not None:
            ceder(segundos)

    def atender_hablando(self, audio: Any) -> Optional[cv.Interpretacion]:
        """Una ventana oída mientras ESTELA habla. Si trae «Estela» (y no es su
        propia voz), ESTELA se calla y cede el turno: con orden, se ejecuta;
        sin orden o sin entenderla, queda atenta a la orden siguiente. Sin
        «Estela», no se contesta ni se guarda."""
        t0 = time.perf_counter()
        texto = (self.reconocedor.transcribir(audio) or "").strip()
        ms = (time.perf_counter() - t0) * 1000.0
        self.ventanas += 1
        llamado, resto = cv.buscar_llamada(texto)
        if not llamado:
            return None
        actual = getattr(self.voz, "texto_hablando", None)
        if actual and any(p in cv.LLAMADAS for p in cv._limpiar(actual).split()):
            return None                              # puede ser su propia voz diciendo «Estela»
        self.ventanas_con_llamada += 1
        # la usuaria manda: ESTELA se calla ya y le deja el turno
        self._ceder(cv.VENTANA_LLAMADA_S)
        cortar = getattr(self.voz, "interrumpir", None)
        if cortar is not None:
            cortar()
        i = cv.interpretar(resto)
        dolor = menciona_dolor(resto)
        if not dolor and i.comando is None:
            texto, i, dolor, ms = self._continuar(audio, texto, i, ms)
        self._enfriar_hasta = time.monotonic() + ENFRIAR_S
        olvidar = getattr(self.microfono, "olvidar_ventana", None)
        if olvidar is not None:
            olvidar()
        if not dolor and i.comando is None:
            # «Estela» sin orden clara (o tapada por su voz): atenta a la siguiente frase
            self._ventana_hasta = time.monotonic() + cv.VENTANA_LLAMADA_S
            self.registro.append({"texto": texto, "comando": None, "motivo": cv.SOLO_LLAMADA,
                                  "reconocer_ms": round(ms), "durante_voz": True})
            self._anota(texto, None, False)
            log.info("Voz (mientras hablaba): «%s» → «Estela»: se calla y escucha (%.0f ms)", texto, ms)
            # urgente: pasa aunque la usuaria tenga el turno, que sigue abierto
            self.voz.decir(cv.DIME, PRIORIDAD_URGENTE)
            return cv.Interpretacion(None, cv.SOLO_LLAMADA, "")
        self.registro.append({"texto": texto, "comando": i.comando,
                              "motivo": "dolor" if dolor else i.motivo,
                              "reconocer_ms": round(ms), "durante_voz": True})
        log.info("Voz (mientras hablaba): «%s» → %s (%.0f ms)", texto,
                 "dolor" if dolor else i.comando, ms)
        self._ceder(0)
        if dolor:
            self._responder_dolor(texto)
        else:
            self._anota(texto, i.comando, False)
            self._ejecutar(i.comando)
        return i

    def _continuar(self, audio: Any, texto: str, i: cv.Interpretacion,
                   ms: float) -> tuple:
        """«Estela» sin orden en la ventana: con ESTELA ya callada, se escucha
        `CONTINUAR_S` más y se reconoce todo junto. Devuelve (texto, interpretación,
        dolor, ms) de lo que haya que usar."""
        seguir = getattr(self.microfono, "escuchar_continuacion", None)
        if seguir is None:
            return texto, i, False, ms
        try:
            import numpy as np
            extra = seguir(CONTINUAR_S, cancelar=lambda: self._parar.is_set() or self._hay_cambios.is_set())
            if extra is None:
                return texto, i, False, ms
            t0 = time.perf_counter()
            texto2 = (self.reconocedor.transcribir(np.concatenate([audio, extra])) or "").strip()
            ms2 = (time.perf_counter() - t0) * 1000.0
        except Exception:                                 # noqa: BLE001
            log.exception("fallo al escuchar la continuación de la orden")
            return texto, i, False, ms
        llamado2, resto2 = cv.buscar_llamada(texto2)
        if not llamado2:
            return texto, i, False, ms
        i2 = cv.interpretar(resto2)
        dolor2 = menciona_dolor(resto2)
        if i2.comando is None and not dolor2:
            return texto, i, False, ms
        log.info("Voz (continuación tras «Estela»): «%s» → %s", texto2, "dolor" if dolor2 else i2.comando)
        return texto2, i2, dolor2, ms + ms2

    def _responder_dolor(self, texto: str) -> None:
        self._anota(texto, None, False)
        # ante dolor se pausa sola (pedido de Paula). La pausa corta lo que
        # suene, así que va antes que la respuesta; esta es urgente para que
        # el «En pausa.» de la sesión no la sustituya en la cola.
        p = self._sesion.paso_actual if self._sesion is not None else None
        if p is not None and not p.pausa.pausada and "pausar" in self.acciones:
            self.acciones["pausar"]()
        self.voz.decir(RESPUESTA_DOLOR, PRIORIDAD_URGENTE)

    def _atender_prueba(self, audio: Any) -> None:
        """Prueba desde los ajustes: qué se oyó y qué se entendería. No actúa ni
        lo guarda en el registro de la sesión."""
        texto = (self.reconocedor.transcribir(audio) or "").strip()
        llamado, orden = cv.separar_llamada(texto) if self.llamada else (True, texto)
        comando = cv.interpretar(orden).comando if llamado else None
        with self._cerrojo:
            n = (self._prueba or {}).get("n", 0) + 1
            self._prueba = {"n": n, "texto": texto, "llamada": bool(llamado) if self.llamada else None,
                            "comando": comando}

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
            self._ceder(0)                            # llegó la orden: ESTELA ya puede contestar
        i = cv.interpretar(orden)
        dolor = menciona_dolor(orden)
        self.registro.append({"texto": texto, "comando": i.comando,
                              "motivo": "dolor" if dolor else i.motivo,
                              "reconocer_ms": round(ms)})
        log.info("Voz: «%s» → %s (%s, %.0f ms)", texto, i.comando,
                 "dolor" if dolor else i.motivo, ms)
        if dolor:
            self._responder_dolor(texto)
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
            self._ceder(cv.VENTANA_LLAMADA_S)          # turno de la usuaria: ESTELA espera la orden
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
            if "reiniciar_sesion" in self.acciones:    # corta lo que suene: antes que la confirmación
                self.acciones["reiniciar_sesion"]()
            self.voz.decir(cv.CONFIRMA_REINICIAR, PRIORIDAD_AVISO)
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
        if comando == cv.CALLAR:                  # solo la frase de ahora; la voz sigue
            self._ceder(0)
            cortar = getattr(self.voz, "interrumpir", None)
            if cortar is not None:
                cortar()
            return
        if comando == cv.REPITE_ESO:
            self.voz.decir(getattr(self.voz, "ultima_repetible", None) or cv.NO_HAY_QUE_REPETIR,
                           PRIORIDAD_AVISO)
            return
        if comando in cv.AJUSTES_DE_PANTALLA:     # lo aplica la pantalla al ver el estado
            ajuste, valor = cv.AJUSTES_DE_PANTALLA[comando]
            with self._cerrojo:
                self._pantalla = {"angulos": None, "reconocer": None, "voz": None,
                                  ajuste: valor, "n": self._pantalla["n"] + 1}
            accion = None if ajuste == "angulos" else comando
        elif comando == cv.PAUSA:
            accion = None if en_pausa else "pausar"
        elif comando == cv.SEGUIR:
            accion = "reanudar" if en_pausa else ("listo" if colocando else None)
        elif comando == cv.SIGUIENTE:
            if not getattr(s, "hay_siguiente", True):     # la sesión no haría nada: se dice
                self.voz.decir(cv.ES_EL_ULTIMO, PRIORIDAD_AVISO)
                return
            accion = "siguiente"
        elif comando == cv.ANTERIOR:
            if not getattr(s, "hay_anterior", True):
                self.voz.decir(cv.ES_EL_PRIMERO, PRIORIDAD_AVISO)
                return
            accion = "anterior"
        elif comando == cv.REINICIAR_EJERCICIO:
            accion = "reiniciar"
        else:
            accion = "terminar"
        # Primero la acción y después la confirmación: las órdenes de navegación
        # cortan lo que suena (`Orquestador._callar`) y cortarían también la
        # confirmación; y con la voz silenciada, «voz activada» no podría oírse.
        if accion is not None and accion in self.acciones:
            self.acciones[accion]()
        if cv.CONFIRMACION[comando] and (accion is not None or comando in cv.ORDENES_DE_AJUSTE):
            self.voz.decir(cv.CONFIRMACION[comando], PRIORIDAD_AVISO)


__all__ = ["EscuchaVoz"]
