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
                 llamada: bool = False, guarda_eco_s: float = 0.0,
                 abrir_microfono: Optional[Callable[[Optional[int]], Any]] = None) -> None:
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
            try:
                audio = mic.escuchar_frase(
                    cancelar=lambda: (self._parar.is_set() or self._hay_cambios.is_set()
                                      or not (self._probando() or self._se_puede())))
                if audio is None:
                    continue
                if self._probando():
                    self._atender_prueba(audio)
                elif self._se_puede():                # si ESTELA empezó a hablar, se descarta
                    self.atender(audio)
            except Exception:                             # noqa: BLE001
                log.exception("fallo en la escucha de voz")
                time.sleep(0.5)

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
        i = cv.interpretar(orden)
        dolor = menciona_dolor(orden)
        self.registro.append({"texto": texto, "comando": i.comando,
                              "motivo": "dolor" if dolor else i.motivo,
                              "reconocer_ms": round(ms)})
        log.info("Voz: «%s» → %s (%s, %.0f ms)", texto, i.comando,
                 "dolor" if dolor else i.motivo, ms)
        if dolor:
            self._anota(texto, None, False)
            self.voz.decir(RESPUESTA_DOLOR, PRIORIDAD_AVISO)
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
        activar_voz = comando == cv.VOZ_SI        # con la voz silenciada no se puede confirmar
        if activar_voz and accion in self.acciones:
            self.acciones[accion]()
        if cv.CONFIRMACION[comando] and (accion is not None or comando in cv.ORDENES_DE_AJUSTE):
            self.voz.decir(cv.CONFIRMACION[comando], PRIORIDAD_AVISO)
        if not activar_voz and accion is not None and accion in self.acciones:
            self.acciones[accion]()


__all__ = ["EscuchaVoz"]
