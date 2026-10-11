"""Regla de dependencias entre capas:  dominio ← aplicacion ← adaptadores.

- `dominio` (feedback, conteo) no importa nada de las otras capas ni
  librerías de cámara, pose, voz o ventana.
- `aplicacion` (sesión, rutina, puertos) solo importa `dominio`.
- `adaptadores` pueden importar ambas. `__main__` lo conecta todo.

Se comprueba leyendo los imports, sin ejecutar nada.
"""

import ast
from pathlib import Path

import pytest

PAQUETE = Path(__file__).resolve().parent.parent / "estela"
INFRAESTRUCTURA = {"cv2", "mediapipe", "webview", "piper", "sounddevice", "PIL"}
PROHIBIDO = {
    "dominio": {"estela.aplicacion", "estela.adaptadores"} | INFRAESTRUCTURA,
    "aplicacion": {"estela.adaptadores"} | INFRAESTRUCTURA,
}


def _imports(ruta: Path):
    """Módulos importados por `ruta`, con los relativos resueltos a absolutos."""
    paquete = ["estela", *ruta.relative_to(PAQUETE).parent.parts]
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            yield from (a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                base = paquete[:len(paquete) - nodo.level + 1]
                yield ".".join(base + ([nodo.module] if nodo.module else []))
            else:
                yield nodo.module


def _viola(modulo: str, prohibidos) -> bool:
    return any(modulo == p or modulo.startswith(p + ".") for p in prohibidos)


@pytest.mark.parametrize("capa", sorted(PROHIBIDO))
def test_capa_no_depende_de_capas_externas(capa):
    violaciones = [
        f"{ruta.relative_to(PAQUETE)} importa {mod}"
        for ruta in sorted((PAQUETE / capa).rglob("*.py"))
        for mod in _imports(ruta)
        if _viola(mod, PROHIBIDO[capa])
    ]
    assert not violaciones, "\n".join(violaciones)
