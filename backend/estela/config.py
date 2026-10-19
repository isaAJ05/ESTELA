"""Rutas por defecto, relativas a `backend/` (la raíz del proyecto Python)."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELOS = RAIZ / "modelos"
VOCES = MODELOS / "voces"
RUTINAS = RAIZ / "rutinas"
SESIONES = RAIZ / "sesiones"
#: episodios de pose etiquetados (adaptadores/grabacion); fuera de git
GRABACIONES = RAIZ / "grabaciones"
#: interfaz de escritorio compilada (frontend/, `npm run build`)
INTERFAZ = RAIZ.parent / "frontend" / "dist"


def modelo_pose(variante: str) -> Path:
    return MODELOS / f"pose_landmarker_{variante}.task"
