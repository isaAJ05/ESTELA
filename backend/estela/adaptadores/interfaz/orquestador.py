"""Orquestación de la sesión para la interfaz de escritorio.

`Orquestador` corre la sesión en su propio hilo (fuente → `Sesion.procesar`)
y la interfaz la controla con métodos que se pueden llamar desde cualquier
hilo. No sabe nada de ventanas: `ventana.py` lo expone a la interfaz y los
tests lo usan con fuentes y estimadores falsos.

Fases (las mismas que muestra la interfaz):

    inicio ─iniciar()─► preparando ─► sesion ─► resumen ─iniciar()─► …
                            │                      │
                            └──► error             └─volver_al_inicio()─► inicio

Flujo de datos: el hilo de la sesión **no espera nunca a la interfaz**. Solo
deja el último `EstadoFrame` y el último frame; la interfaz los pide con
`estado(desde)`, que espera hasta que haya una versión más nueva (long
polling). Si la interfaz dibuja más lento que la cámara, se salta estados en
vez de acumular retraso, igual que `FuenteCamara` con los frames. La
conversión a JSON y la compresión JPEG del frame ocurren en el hilo de la
interfaz, no en el de la sesión.

Ningún frame se guarda: el JPEG se genera en memoria para la ventana local.
Con `perfiles`, al terminar cada sesión se añade su registro mínimo
(ADR-008) al historial del perfil que entrenaba (ADR-009), desde el hilo de
la sesión y ya fuera del bucle por frame. Sin perfil elegido (invitada) no se
guarda nada.
"""

from __future__ import annotations

import base64
import logging
import queue
import threading
import time
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Mapping, Optional

import numpy as np

from ...aplicacion.historial import progreso, registro_de_sesion
from ...aplicacion.perfiles import PerfilInvalido, Perfiles
from ...aplicacion.puertos import Estimador, Fuente
from ...aplicacion.rutina import Ejercicio, Rutina, RutinaInvalida
from ...aplicacion.sesion import EstadoFrame, Sesion, frases_de_rutina
from . import contrato

log = logging.getLogger(__name__)

INICIO, PREPARANDO, SESION, RESUMEN, ERROR = (
    "inicio", "preparando", "sesion", "resumen", "error")

#: ancho del frame que se envía a la ventana (solo para verlo)
ANCHO_VIDEO = 640
CALIDAD_JPEG = 70
#: vista previa de la cámara en los ajustes: más pequeña, y se cierra sola
#: si la interfaz deja de pedirla (p. ej. se cerró el panel sin avisar)
ANCHO_VISTA = 480
VISTA_INACTIVA_S = 3.0


def _jpeg_base64(frame: Any, ancho: int = ANCHO_VIDEO) -> Optional[str]:
    if not isinstance(frame, np.ndarray) or frame.ndim != 3:
        return None
    import cv2

    h, w = frame.shape[:2]
    if w > ancho:
        frame = cv2.resize(frame, (ancho, round(h * ancho / w)),
                           interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, CALIDAD_JPEG])
    return base64.b64encode(buf).decode("ascii") if ok else None


class Orquestador:
    def __init__(self, rutina: Rutina, catalogo: Mapping[str, Ejercicio],
                 crear_estimador: Callable[[], Estimador],
                 abrir_fuente: Callable[[], Fuente], voz: Any, *,
                 espejo: bool, fuente: str = "camara",
                 al_terminar: Optional[Callable[[Dict[str, Any]], None]] = None,
                 verbalizador: Any = None, sin_dtw: bool = False,
                 colocacion: bool = True,
                 reconocer: bool = False,
                 camara: Optional[int] = None,
                 listar_camaras: Optional[Callable[[], List[Dict[str, Any]]]] = None,
                 abrir_camara: Optional[Callable[[int], Fuente]] = None,
                 perfiles: Optional[Perfiles] = None,
                 preparar_sesion: Optional[Callable[[Sesion], None]] = None) -> None:
        """`crear_estimador` y `abrir_fuente` se llaman en cada sesión: así
        «Repetir rutina» empieza con la cámara recién abierta y con marcas de
        tiempo desde cero. `al_terminar` recibe `Sesion.resumen()`.

        `camara` es el índice que `abrir_fuente` debe usar (lo lee de
        `self.camara`); la interfaz lo cambia con `configurar` entre sesiones.
        Sin `listar_camaras` (p. ej. con un vídeo) no se puede elegir.
        `abrir_camara(indice)` abre una cámara solo para verla desde los
        ajustes (`vista_camara`); sin ella no hay vista previa.

        `perfiles`: perfiles y sus historiales (None: no se guarda nada ni
        se ofrecen perfiles ni panel de progreso)."""
        self.rutina = rutina
        #: la rutina de `rutina`: la que se describe en `info()`
        self._rutina_base = rutina
        self.catalogo = catalogo
        self._crear_estimador = crear_estimador
        self._abrir_fuente = abrir_fuente
        self._voz = voz
        self._espejo = espejo
        self._fuente = fuente
        self._al_terminar = al_terminar
        self._verbalizador = verbalizador
        self._sin_dtw = sin_dtw
        self._colocacion = colocacion
        #: aviso de EXP-010; la interfaz lo cambia con `configurar`
        self._reconocer = reconocer
        self._perfiles = perfiles
        #: se llama con cada `Sesion` recién creada, en el hilo de la sesión
        #: (p. ej. para engancharle la entrenadora)
        self._preparar_sesion = preparar_sesion
        #: quién entrena; None con `elegido` = invitada
        self._perfil_activo: Optional[str] = None
        self._perfil_elegido = False
        #: el perfil de la sesión en curso, fijado al iniciarla
        self._perfil_sesion: Optional[str] = None
        #: cámara de la próxima sesión; la interfaz la cambia con `configurar`
        self.camara = camara
        self._listar_camaras = listar_camaras
        self._abrir_camara = abrir_camara
        #: cámara abierta para la vista previa de los ajustes (fuera de sesión)
        self._vista: Optional[Fuente] = None
        self._vista_indice: Optional[int] = None
        self._vista_lock = threading.Lock()
        self._vista_reloj: Optional[threading.Timer] = None
        #: sube con cada frame pedido: distingue el último reloj de los viejos
        self._vista_turno = 0
        #: voz de entrada (`EscuchaVoz`) y cómo listar los micrófonos; los pone
        #: quien arranca la aplicación con `conectar_voz_entrada`
        self._voz_entrada: Any = None
        self._listar_microfonos: Optional[Callable[[], List[Dict[str, Any]]]] = None

        self._cv = threading.Condition()
        self._version = 0
        self._fase = INICIO
        self._error: Optional[Dict[str, str]] = None
        self._estado: Optional[EstadoFrame] = None
        self._fps: Optional[float] = None
        self._frame: Any = None
        self._resumen: Optional[Dict[str, Any]] = None

        self._comandos: "queue.SimpleQueue[str]" = queue.SimpleQueue()
        self._parar = threading.Event()
        self._hilo: Optional[threading.Thread] = None

    # -- consultas (cualquier hilo) ------------------------------------------

    def info(self) -> Dict[str, Any]:
        d = contrato.info(self._rutina_base, self.catalogo, self._espejo)
        d["fuente"] = self._fuente
        d["capacidades"]["historial"] = self._perfiles is not None
        d["capacidades"]["perfiles"] = self._perfiles is not None
        d["capacidades"]["vozEntrada"] = self._voz_entrada is not None
        return d

    def conectar_voz_entrada(self, escucha: Any,
                             listar_microfonos: Optional[Callable[[], List[Dict[str, Any]]]] = None
                             ) -> None:
        """Da a la interfaz la sección «Micrófono»: elegir, encender, apagar y probar."""
        self._voz_entrada = escucha
        self._listar_microfonos = listar_microfonos

    def microfono(self) -> Optional[Dict[str, Any]]:
        """Estado del micrófono para los ajustes (encendido, elegido, nivel, lo
        último oído en la prueba) y la lista de entradas; None sin voz de entrada."""
        if self._voz_entrada is None:
            return None
        d = dict(self._voz_entrada.ajustes())
        d["lista"] = self._listar_microfonos() if self._listar_microfonos is not None else []
        return d

    def probar_microfono(self) -> bool:
        """Empieza una prueba corta: los ajustes muestran lo que se oye, sin actuar."""
        return bool(self._voz_entrada is not None and self._voz_entrada.probar())

    def camaras(self) -> Optional[Dict[str, Any]]:
        """Cámaras que se pueden elegir y la elegida, o None si no se puede
        elegir (vídeo) o hay una sesión usando la cámara."""
        if self._listar_camaras is None or self._fase in (PREPARANDO, SESION):
            return None
        # listar abre cada cámara: la de la vista previa tiene que estar libre
        self.cerrar_vista_camara()
        return {"lista": self._listar_camaras(), "elegida": self.camara}

    def vista_camara(self) -> Optional[str]:
        """Último frame de la cámara elegida, en JPEG base64, para comprobarla
        desde los ajustes. La abre en la primera llamada y la mantiene abierta
        mientras se siga pidiendo; None si no hay vista previa, hay una sesión
        o la cámara no abre. El frame no se guarda ni pasa por el estimador."""
        if self._abrir_camara is None:
            return None
        with self._vista_lock:
            if self._fase in (PREPARANDO, SESION):
                self._soltar_vista()
                return None
            indice = self.camara if self.camara is not None else 0
            if self._vista is None or self._vista_indice != indice:
                self._soltar_vista()
                try:
                    self._vista = self._abrir_camara(indice)
                except Exception as e:             # ocupada, desconectada…
                    log.warning("No se pudo abrir la cámara %s para la vista previa: %s",
                                indice, e)
                    return None
                self._vista_indice = indice
            leido = self._vista.leer()
            if leido is None:
                self._soltar_vista()
                return None
            self._vista_turno += 1
            if self._vista_reloj is not None:
                self._vista_reloj.cancel()
            self._vista_reloj = threading.Timer(VISTA_INACTIVA_S, self._caducar_vista,
                                                args=(self._vista_turno,))
            self._vista_reloj.daemon = True
            self._vista_reloj.start()
            return _jpeg_base64(leido[0], ANCHO_VISTA)

    def _caducar_vista(self, turno: int) -> None:
        with self._vista_lock:
            # un reloj viejo que esperaba el candado no cierra una vista que
            # se volvió a pedir después
            if turno == self._vista_turno:
                self._soltar_vista()

    def cerrar_vista_camara(self) -> None:
        """Suelta la cámara de la vista previa (si estaba abierta)."""
        with self._vista_lock:
            self._soltar_vista()

    def _soltar_vista(self) -> None:
        # con `_vista_lock` tomado
        if self._vista_reloj is not None:
            self._vista_reloj.cancel()
            self._vista_reloj = None
        if self._vista is not None:
            try:
                self._vista.cerrar()
            except Exception:
                log.exception("Error al cerrar la vista previa de la cámara")
            self._vista, self._vista_indice = None, None

    def historial(self, hoy: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """Panel «Mi progreso» del perfil activo, o None (sin perfiles o invitada)."""
        perfil = self._perfiles.obtener(self._perfil_activo) if self._perfiles else None
        if perfil is None:
            return None
        registros = self._perfiles.historial_de(perfil["id"]).leer()
        return contrato.progreso_a_dict(progreso(registros, hoy or date.today()),
                                        self.catalogo, perfil.get("meta_semanal"))

    def progreso_activo(self, hoy: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """`historial.progreso()` del perfil activo, sin dar formato, o None."""
        perfil = self._perfiles.obtener(self._perfil_activo) if self._perfiles else None
        if perfil is None:
            return None
        return progreso(self._perfiles.historial_de(perfil["id"]).leer(), hoy or date.today())

    def borrar_historial(self) -> bool:
        """Vacía el historial del perfil activo (el perfil se queda)."""
        if self._perfiles is None or self._perfiles.obtener(self._perfil_activo) is None:
            return False
        try:
            self._perfiles.historial_de(self._perfil_activo).borrar()
        except OSError:
            log.exception("No se pudo borrar el historial")
            return False
        return True

    # -- perfiles (cualquier hilo) ---------------------------------------------

    def perfiles(self) -> Optional[Dict[str, Any]]:
        if self._perfiles is None:
            return None
        lista = self._perfiles.listar()
        if self._perfil_activo not in {p["id"] for p in lista}:
            self._perfil_activo = None                 # se borró fuera de la app
        return contrato.perfiles_a_dict(lista, self._perfil_activo, self._perfil_elegido)

    def elegir_perfil(self, perfil_id: Optional[str]) -> bool:
        """Quién entrena a partir de la próxima sesión; None = invitada."""
        if self._perfiles is None:
            return False
        if perfil_id is not None and self._perfiles.obtener(perfil_id) is None:
            return False
        self._perfil_activo, self._perfil_elegido = perfil_id, True
        return True

    def crear_perfil(self, datos: Mapping[str, Any]) -> Dict[str, Any]:
        """Crea el perfil y lo deja elegido: {"ok", "perfil"} o {"ok": False, "error"}."""
        return self._cambiar_perfil(lambda p: p.crear(contrato.datos_de_perfil(datos)), elegir=True)

    def editar_perfil(self, perfil_id: str, datos: Mapping[str, Any]) -> Dict[str, Any]:
        return self._cambiar_perfil(lambda p: p.editar(perfil_id, contrato.datos_de_perfil(datos)))

    def borrar_perfil(self, perfil_id: str) -> bool:
        """Borra el perfil y su historial. Si era el activo, se vuelve a
        preguntar quién entrena."""
        if self._perfiles is None:
            return False
        try:
            borrado = self._perfiles.borrar(perfil_id)
        except (OSError, PerfilInvalido):
            log.exception("No se pudo borrar el perfil")
            return False
        if borrado and perfil_id == self._perfil_activo:
            self._perfil_activo, self._perfil_elegido = None, False
        return borrado

    def guardar_rutina(self, perfil_id: str, pasos: Any) -> Dict[str, Any]:
        """Guarda en el perfil la rutina de «Mi rutina» ([{"skillId", "objetivo"}]).
        Se valida igual que al iniciar una sesión; una lista vacía también vale
        (el perfil quitó todos los ejercicios). Lleva el id del perfil para que
        un guardado tardío no caiga en otro perfil si se cambió entretanto."""
        limpios = self._pasos_de_rutina(pasos)
        if isinstance(limpios, dict):
            return limpios
        return self._cambiar_perfil(lambda p: p.guardar_rutina(perfil_id, limpios))

    def guardar_rutina_nombrada(self, perfil_id: str, datos: Any) -> Dict[str, Any]:
        """Crea (`id` ausente o null) o actualiza una rutina guardada con
        nombre: {"id"?, "nombre", "pasos": [{"skillId", "objetivo"}]}."""
        if not isinstance(datos, Mapping):
            return {"ok": False, "error": "La rutina no tiene el formato esperado."}
        limpios = self._pasos_de_rutina(datos.get("pasos"))
        if isinstance(limpios, dict):
            return limpios
        rutina_id = datos.get("id") if isinstance(datos.get("id"), str) else None
        return self._cambiar_perfil(
            lambda p: p.guardar_rutina_nombrada(perfil_id, rutina_id, datos.get("nombre"), limpios))

    def borrar_rutina_nombrada(self, perfil_id: str, rutina_id: str) -> Dict[str, Any]:
        return self._cambiar_perfil(lambda p: p.borrar_rutina_nombrada(perfil_id, rutina_id))

    def _pasos_de_rutina(self, pasos: Any) -> Any:
        """[{"skillId", "objetivo"}] → [{"skill_id", "objetivo"}] validados
        como en `iniciar` (una lista vacía también), o el dict de error."""
        if not isinstance(pasos, list):
            return {"ok": False, "error": "La rutina no tiene el formato esperado."}
        if not pasos:
            return []
        try:
            rutina = contrato.rutina_desde_opciones({"pasos": pasos}, self.catalogo)
        except (RutinaInvalida, AttributeError) as e:
            return {"ok": False, "error": str(e) or "La rutina no es válida."}
        return [{"skill_id": p.skill_id, "objetivo": p.repeticiones} for p in rutina.pasos]

    def _cambiar_perfil(self, accion: Callable[[Perfiles], Dict[str, Any]],
                        elegir: bool = False) -> Dict[str, Any]:
        if self._perfiles is None:
            return {"ok": False, "error": "Los perfiles no están disponibles."}
        try:
            perfil = accion(self._perfiles)
        except PerfilInvalido as e:
            return {"ok": False, "error": str(e)}
        except OSError:
            log.exception("No se pudo guardar el perfil")
            return {"ok": False, "error": "No se pudo guardar el perfil en este equipo."}
        if elegir:
            self._perfil_activo, self._perfil_elegido = perfil["id"], True
        return {"ok": True, "perfil": contrato.perfil_a_dict(perfil)}

    @property
    def fase(self) -> str:
        return self._fase

    def estado(self, desde: int = -1, espera_s: float = 0.5,
               con_video: bool = True) -> Optional[Dict[str, Any]]:
        """Estado más nuevo que la versión `desde`, o None si no llega en
        `espera_s` segundos (la interfaz vuelve a preguntar)."""
        with self._cv:
            if not self._cv.wait_for(lambda: self._version > desde, espera_s):
                return None
            version, fase, error = self._version, self._fase, self._error
            estado, fps, frame, resumen = self._estado, self._fps, self._frame, self._resumen
        return {
            "version": version,
            "fase": fase,
            "error": error,
            "sesion": (contrato.estado_a_dict(estado, fps)
                       if estado is not None and fase == SESION else None),
            "resumen": resumen if fase == RESUMEN else None,
            "frame": _jpeg_base64(frame) if con_video and fase == SESION else None,
        }

    # -- comandos (cualquier hilo) -------------------------------------------

    def iniciar(self, rutina: Optional[Rutina] = None) -> bool:
        """Empieza una sesión nueva desde el inicio, el resumen o un error.
        Con `rutina`, la usa a partir de ahora («Repetir rutina» repite la
        última); sin ella, repite la que había."""
        with self._cv:
            if self._fase not in (INICIO, RESUMEN, ERROR):
                return False
            if rutina is not None and rutina != self.rutina:
                self.rutina = rutina
                if hasattr(self._voz, "precalentar"):
                    self._voz.precalentar(frases_de_rutina(rutina, self.catalogo))
            if self._hilo is not None:
                self._hilo.join()
            self._parar.clear()
            # la sesión se guarda en el perfil de ahora aunque se cambie durante ella
            self._perfil_sesion = self._perfil_activo
            while not self._comandos.empty():
                self._comandos.get_nowait()
            self._publicar(fase=PREPARANDO, error=None, estado=None, frame=None,
                           resumen=None)
            # la sesión necesita la cámara libre; con la fase ya cambiada,
            # `vista_camara` no vuelve a abrirla
            self.cerrar_vista_camara()
            self._hilo = threading.Thread(target=self._correr, name="estela-sesion",
                                          daemon=True)
            self._hilo.start()
        return True

    def _callar(self) -> None:
        """Una orden de la usuaria manda sobre lo que ESTELA estuviera diciendo
        (una corrección, la entrenadora, un anuncio): se corta y se tira lo
        pendiente. Pedido de Paula (2026-11-17): al saltar o pausar por voz las
        frases se enredaban y se sobreponían."""
        interrumpir = getattr(self._voz, "interrumpir", None)
        if interrumpir is not None:
            interrumpir()

    def siguiente(self) -> None:
        self._callar()
        self._comandos.put("siguiente")

    def anterior(self) -> None:
        self._callar()
        self._comandos.put("anterior")

    def reiniciar(self) -> None:
        self._callar()
        self._comandos.put("reiniciar")

    def reiniciar_sesion(self) -> None:
        """Vuelve al primer ejercicio y borra lo hecho (orden de voz)."""
        self._callar()
        self._comandos.put("reiniciar_sesion")

    def reconocer_si(self) -> None:
        self.configurar(reconocer=True)

    def reconocer_no(self) -> None:
        self.configurar(reconocer=False)

    def voz_si(self) -> None:
        self.configurar(voz=True)

    def voz_no(self) -> None:
        self.configurar(voz=False)

    def listo(self) -> None:
        """Termina la fase de colocación del ejercicio actual (botón «Listo»).
        Corta a la entrenadora si estaba hablando: la usuaria ya quiere empezar."""
        self._callar()
        self._comandos.put("listo")

    def pausar(self) -> None:
        """Pausa pedida por la usuaria (botón o espacio); no se quita sola."""
        self._callar()
        self._comandos.put("pausar")

    def reanudar(self) -> None:
        self._comandos.put("reanudar")

    def terminar(self) -> None:
        """Termina la sesión en curso y pasa al resumen."""
        self._callar()
        self._comandos.put("terminar")

    def configurar(self, voz: Optional[bool] = None,
                   reconocer: Optional[bool] = None,
                   camara: Optional[int] = None,
                   voz_entrada: Optional[bool] = None,
                   microfono: Any = ...) -> None:
        """Ajustes de la interfaz que se pueden cambiar en cualquier momento.
        `reconocer` vale para la sesión en curso y para las siguientes;
        `camara`, desde la próxima sesión. `voz_entrada` enciende o apaga el
        micrófono y `microfono` elige la entrada (índice, o None: la de defecto
        del sistema); los dos valen al momento."""
        if self._voz_entrada is not None:
            if microfono is not ...:
                self._voz_entrada.elegir_microfono(microfono)
            if voz_entrada is not None:
                self._voz_entrada.encender(voz_entrada)
        if camara is not None and self._listar_camaras is not None:
            self.camara = camara
        if voz is not None and hasattr(self._voz, "silenciar"):
            self._voz.silenciar(not voz)
        if reconocer is not None:
            self._reconocer = reconocer
            self._comandos.put("reconocer")

    def volver_al_inicio(self) -> None:
        with self._cv:
            if self._fase in (RESUMEN, ERROR):
                self._publicar(fase=INICIO, error=None, resumen=None)

    def cerrar(self, timeout: float = 5.0) -> None:
        self._parar.set()
        self.cerrar_vista_camara()
        if self._hilo is not None:
            self._hilo.join(timeout)

    # -- hilo de la sesión ---------------------------------------------------

    def _publicar(self, **cambios: Any) -> None:
        with self._cv:
            for k, v in cambios.items():
                setattr(self, f"_{k}", v)
            self._version += 1
            self._cv.notify_all()

    def _correr(self) -> None:
        try:
            fuente = self._abrir_fuente()
        except Exception as e:                 # cámara ocupada, vídeo inexistente…
            log.error("No se pudo abrir la fuente: %s", e)
            self._publicar(fase=ERROR, error={"tipo": "fuente", "mensaje": str(e)})
            return
        try:
            estimador = self._crear_estimador()
        except Exception as e:
            fuente.cerrar()
            log.error("No se pudo cargar el modelo de pose: %s", e)
            self._publicar(fase=ERROR, error={"tipo": "modelo", "mensaje": str(e)})
            return

        sesion = Sesion(self.rutina, self.catalogo, estimador, self._voz,
                        self._verbalizador, sin_dtw=self._sin_dtw,
                        colocacion=self._colocacion,
                        reconocer=self._reconocer, verbalizar_aparte=True)
        if self._preparar_sesion is not None:
            self._preparar_sesion(sesion)
        self._publicar(fase=SESION)
        fps, t_prev = None, time.perf_counter()
        motivo = contrato.FIN_CIERRE
        try:
            while not self._parar.is_set():
                if self._aplicar_comandos(sesion):
                    motivo = (contrato.FIN_COMPLETADA if sesion.terminada
                              else contrato.FIN_USUARIA)
                    break
                leido = fuente.leer()
                if leido is None:              # fin del vídeo o cámara perdida
                    motivo = contrato.FIN_FUENTE
                    break
                frame, t_ms = leido
                estado = sesion.procesar(frame, t_ms)
                ahora = time.perf_counter()
                inst = 1.0 / max(ahora - t_prev, 1e-6)
                fps = inst if fps is None else 0.9 * fps + 0.1 * inst
                t_prev = ahora
                self._publicar(estado=estado, fps=fps, frame=frame)
                if sesion.terminada:
                    motivo = contrato.FIN_COMPLETADA
                    break
        except Exception:
            log.exception("Error en la sesión")
            motivo = contrato.FIN_ERROR
        finally:
            fuente.cerrar()
            estimador.cerrar()
            sesion.cerrar()

        resumen = sesion.resumen()
        if self._al_terminar is not None:
            try:
                self._al_terminar(resumen)
            except Exception:
                log.exception("Error al cerrar la sesión")
        guardada = self._guardar(resumen, motivo)
        self._publicar(fase=RESUMEN, estado=None, frame=None,
                       resumen=contrato.resumen_a_dict(resumen, self.catalogo, motivo,
                                                       guardada))

    def _guardar(self, resumen: Dict[str, Any], motivo: str) -> Optional[bool]:
        """Añade la sesión al historial. False si no había nada que guardar
        o falló la escritura; un fallo no impide ver el resumen."""
        if self._perfiles is None or self._perfil_sesion is None:
            return None                               # sin perfiles, o invitada
        registro = registro_de_sesion(resumen, datetime.now(), motivo)
        if registro is None:
            return False
        try:
            if self._perfiles.obtener(self._perfil_sesion) is None:
                return False                          # se borró durante la sesión
            self._perfiles.historial_de(self._perfil_sesion).agregar(registro)
        except OSError:
            log.exception("No se pudo guardar la sesión en el historial")
            return False
        return True

    def _aplicar_comandos(self, sesion: Sesion) -> bool:
        """Aplica los comandos pendientes en el hilo de la sesión (que no es
        segura entre hilos). Devuelve True si hay que terminar."""
        while True:
            try:
                cmd = self._comandos.get_nowait()
            except queue.Empty:
                return False
            if cmd == "terminar":
                return True
            if cmd == "siguiente":
                sesion.siguiente()
                if sesion.terminada:
                    return True
            elif cmd == "anterior":
                sesion.anterior()
            elif cmd == "reiniciar":
                sesion.reiniciar_ejercicio()
            elif cmd == "reiniciar_sesion":
                sesion.reiniciar_sesion()
            elif cmd == "listo":
                sesion.terminar_colocacion()
            elif cmd == "pausar":
                sesion.pausar()
            elif cmd == "reanudar":
                sesion.reanudar()
            elif cmd == "reconocer":
                if sesion.reconocer != self._reconocer:
                    sesion.activar_reconocimiento(self._reconocer)


__all__ = ["Orquestador", "INICIO", "PREPARANDO", "SESION", "RESUMEN", "ERROR"]
