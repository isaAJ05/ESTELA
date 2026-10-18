"""Ventana de escritorio de ESTELA (pywebview).

Abre la interfaz compilada (`frontend/dist/`) en una ventana nativa: WKWebView
en macOS, WebKitGTK o Qt en Linux. La interfaz habla con Python solo a través
de `Api`, que pywebview publica como `window.pywebview.api` en JavaScript.
Cada llamada de JavaScript corre en su propio hilo de Python, así que
`Api.estado` puede esperar un estado nuevo sin bloquear la ventana.

La página se sirve con el servidor HTTP local de pywebview (127.0.0.1): los
módulos JavaScript no cargan desde `file://` en WKWebView. No hay ninguna
conexión a internet.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from ...aplicacion.rutina import RutinaInvalida
from . import contrato
from .orquestador import Orquestador

log = logging.getLogger(__name__)


class InterfazNoDisponible(RuntimeError):
    pass


class Api:
    """Métodos que la interfaz puede llamar (ver `frontend/src/bridge/`).

    Los atributos con «_» no se exponen a JavaScript."""

    def __init__(self, orquestador: Orquestador) -> None:
        self._orq = orquestador
        self._ventana: Any = None

    def info(self) -> Dict[str, Any]:
        return self._orq.info()

    def estado(self, desde: int) -> Optional[Dict[str, Any]]:
        return self._orq.estado(int(desde))

    def iniciar(self, opciones: Optional[Dict[str, Any]] = None) -> bool:
        # `opciones` trae lo que elige la usuaria en el inicio: la rutina
        # personalizada en "pasos" y, cuando exista la capacidad «nivel»
        # (T22.a), {"nivel": "avanzado"}, que hoy no se usa.
        rutina = None
        if opciones and opciones.get("pasos"):
            try:
                rutina = contrato.rutina_desde_opciones(opciones, self._orq.catalogo)
            except RutinaInvalida as e:
                log.warning("Rutina de la interfaz rechazada: %s", e)
                return False
        return self._orq.iniciar(rutina)

    def configurar(self, ajustes: Optional[Dict[str, Any]] = None) -> None:
        # {"voz": false} silencia las indicaciones habladas
        voz = (ajustes or {}).get("voz")
        self._orq.configurar(voz=voz if isinstance(voz, bool) else None)

    def siguiente(self) -> None:
        self._orq.siguiente()

    def reiniciar(self) -> None:
        self._orq.reiniciar()

    def terminar(self) -> None:
        self._orq.terminar()

    def volver_al_inicio(self) -> None:
        self._orq.volver_al_inicio()

    def salir(self) -> None:
        if self._ventana is not None:
            self._ventana.destroy()


def comprobar(dist: Path) -> Path:
    """Devuelve la ruta de `index.html` o explica qué falta para abrir la ventana."""
    try:
        import webview  # noqa: F401
    except ImportError as e:
        raise InterfazNoDisponible(
            "Falta pywebview. Instálalo con: pip install -e \".[interfaz]\" "
            "(o usa --interfaz opencv).") from e
    indice = Path(dist) / "index.html"
    if not indice.exists():
        raise InterfazNoDisponible(
            f"No existe {indice}. Compila la interfaz: cd frontend && npm install "
            "&& npm run build (o usa --interfaz opencv).")
    return indice


def abrir(orquestador: Orquestador, dist: Path, depurar: bool = False) -> None:
    """Abre la ventana y bloquea hasta que se cierra (debe ir en el hilo principal)."""
    indice = comprobar(dist)
    import webview

    api = Api(orquestador)
    ventana = webview.create_window(
        "ESTELA", url=str(indice.resolve()), js_api=api,
        width=1280, height=800, min_size=(960, 600), maximized=True,
        background_color="#0E0D16")
    api._ventana = ventana
    ventana.events.closed += lambda: orquestador.cerrar()
    icono = indice.parent / "icono.ico"
    _identificar_en_barra_de_tareas()
    ventana.events.shown += lambda: _identificar_ventana("ESTELA")
    webview.start(http_server=True, debug=depurar, private_mode=True,
                  icon=str(icono) if icono.is_file() else None)


def _identificar_en_barra_de_tareas() -> None:
    """En Windows, la barra de tareas agrupa la ventana con python.exe y le
    pone su icono; con un AppUserModelID propio usa el de la ventana."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_ID)
    except (AttributeError, OSError):
        log.debug("no se pudo fijar el AppUserModelID", exc_info=True)


_APP_ID = "estela.app"


def _identificar_ventana(titulo: str) -> None:
    """Lo mismo, pero en la ventana. Hace falta con el Python de la Microsoft
    Store: como app empaquetada, ignora el AppUserModelID del proceso."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD),
                        ("d3", wintypes.WORD), ("d4", ctypes.c_ubyte * 8)]

        class PROPERTYKEY(ctypes.Structure):
            _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]

        class PROPVARIANT(ctypes.Structure):
            _fields_ = [("vt", wintypes.USHORT), ("r1", wintypes.USHORT),
                        ("r2", wintypes.USHORT), ("r3", wintypes.USHORT),
                        ("valor", ctypes.c_wchar_p), ("relleno", ctypes.c_void_p)]

        def guid(d1, d2, d3, d4):
            return GUID(d1, d2, d3, (ctypes.c_ubyte * 8)(*d4))

        hwnd = ctypes.windll.user32.FindWindowW(None, titulo)
        if not hwnd:
            return
        # IPropertyStore {886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}
        iid = guid(0x886D8EEB, 0x8CF2, 0x4446, (0x8D, 0x02, 0xCD, 0xBA, 0x1D, 0xBD, 0xCF, 0x99))
        almacen = ctypes.c_void_p()
        ctypes.windll.shell32.SHGetPropertyStoreForWindow(
            wintypes.HWND(hwnd), ctypes.byref(iid), ctypes.byref(almacen))
        if not almacen:
            return
        # PKEY_AppUserModel_ID = {9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}, 5
        clave = PROPERTYKEY(guid(0x9F4C2855, 0x9F79, 0x4B39,
                                 (0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3)), 5)
        valor = PROPVARIANT(vt=31, valor=_APP_ID)              # VT_LPWSTR
        tabla = ctypes.cast(almacen, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        metodo = lambda i, *tipos: ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *tipos)(tabla[i])
        metodo(6, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))(
            almacen, ctypes.byref(clave), ctypes.byref(valor))  # SetValue
        metodo(7)(almacen)                                      # Commit
        metodo(2)(almacen)                                      # Release
    except (AttributeError, OSError, ValueError):
        log.debug("no se pudo fijar el AppUserModelID de la ventana", exc_info=True)


__all__ = ["Api", "InterfazNoDisponible", "abrir", "comprobar"]
