"""Rutas por defecto, relativas a la raíz del repositorio."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELOS = RAIZ / "modelos"
VOCES = MODELOS / "voces"
RUTINAS = RAIZ / "rutinas"
SESIONES = RAIZ / "sesiones"
#: interfaz de escritorio compilada (interfaz/, `npm run build`)
INTERFAZ = RAIZ / "interfaz" / "dist"


def modelo_pose(variante: str) -> Path:
    return MODELOS / f"pose_landmarker_{variante}.task"
