"""Ventana de escritorio de ESTELA (pywebview).

Abre la interfaz compilada (`interfaz/dist/`) en una ventana nativa: WKWebView
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
from pathlib import Path
from typing import Any, Dict, Optional

from .orquestador import Orquestador

log = logging.getLogger(__name__)


class InterfazNoDisponible(RuntimeError):
    pass


class Api:
    """Métodos que la interfaz puede llamar (ver `interfaz/src/bridge/`).

    Los atributos con «_» no se exponen a JavaScript."""

    def __init__(self, orquestador: Orquestador) -> None:
        self._orq = orquestador
        self._ventana: Any = None

    def info(self) -> Dict[str, Any]:
        return self._orq.info()

    def estado(self, desde: int) -> Optional[Dict[str, Any]]:
        return self._orq.estado(int(desde))

    def iniciar(self, opciones: Optional[Dict[str, Any]] = None) -> bool:
        # `opciones` trae lo que elige la usuaria en el inicio, p. ej. {"nivel":
        # "avanzado"} cuando exista la capacidad «nivel» (T22.a). Hoy no se usa.
        return self._orq.iniciar()

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
            f"No existe {indice}. Compila la interfaz: cd interfaz && npm install "
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
    webview.start(http_server=True, debug=depurar, private_mode=True)


__all__ = ["Api", "InterfazNoDisponible", "abrir", "comprobar"]
