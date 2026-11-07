"""Perfiles locales: varias personas en el mismo equipo, cada una con su
historial (ADR-009, sobre ADR-008).

Un perfil es solo lo necesario para reconocerse y fijarse una meta: nombre o
apodo, un color para el avatar (las iniciales se dibujan en la interfaz),
si se quiere, cuántos días por semana moverse, y la última rutina que armó
en «Mi rutina» (ejercicios en orden y su objetivo). **No** guarda edad, peso,
estatura ni nada del cuerpo: ESTELA no los usa y serían datos sensibles sin
propósito (CLAUDE.md §6).

Archivos, todos en el directorio del historial (`config.HISTORIAL`):

    perfiles.json      lista de perfiles (se reescribe entera, de forma atómica)
    <id>.jsonl         sesiones de cada perfil (`historial.Historial`)

No hay contraseñas: quien use el equipo puede ver los perfiles. La interfaz lo
dice. Sin perfil («invitado») no se guarda nada.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .historial import Historial

log = logging.getLogger(__name__)

#: colores del avatar (la interfaz los traduce a su paleta)
COLORES = ("violeta", "naranja", "turquesa", "rosa", "azul", "mostaza")
MAX_PERFILES = 8
MAX_NOMBRE = 30
META_MIN, META_MAX = 1, 7
#: historial de antes de los perfiles (ADR-008): lo hereda el primer perfil
HISTORIAL_ANTIGUO = "sesiones.jsonl"
#: más pasos que ejercicios hay en el catálogo no tiene sentido; es una cota de seguridad
MAX_PASOS_RUTINA = 20


class PerfilInvalido(ValueError):
    """Datos de un perfil que no se pueden guardar; el mensaje es para la usuaria."""


def _limpiar(datos: Mapping[str, Any], otros: List[Dict[str, Any]],
             actual: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Valida nombre, color y meta. `actual`: el perfil que se edita (los
    campos que no vienen se conservan)."""
    base = actual or {}
    nombre = datos.get("nombre", base.get("nombre"))
    nombre = " ".join(str(nombre or "").split())
    if not nombre:
        raise PerfilInvalido("Escribe un nombre o apodo.")
    if len(nombre) > MAX_NOMBRE:
        raise PerfilInvalido(f"El nombre puede tener hasta {MAX_NOMBRE} caracteres.")
    if any(p["nombre"].casefold() == nombre.casefold() for p in otros):
        raise PerfilInvalido("Ya hay un perfil con ese nombre.")
    color = datos.get("color", base.get("color", COLORES[0]))
    if color not in COLORES:
        raise PerfilInvalido("Elige uno de los colores disponibles.")
    meta = datos.get("meta_semanal", base.get("meta_semanal"))
    if meta is not None:
        if isinstance(meta, bool) or not isinstance(meta, int) or not META_MIN <= meta <= META_MAX:
            raise PerfilInvalido(f"La meta debe estar entre {META_MIN} y {META_MAX} días por semana.")
    return {"nombre": nombre, "color": color, "meta_semanal": meta}


def rutina_de(perfil: Mapping[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """Rutina guardada del perfil, [{skill_id, objetivo}], sin entradas mal
    formadas; None si no guardó ninguna. Que cada ejercicio siga existiendo y
    su objetivo esté en los límites lo comprueba quien la usa con el catálogo."""
    crudo = perfil.get("rutina")
    if not isinstance(crudo, list):
        return None
    return [{"skill_id": p["skill_id"], "objetivo": p["objetivo"]} for p in crudo[:MAX_PASOS_RUTINA]
            if isinstance(p, dict) and isinstance(p.get("skill_id"), str)
            and isinstance(p.get("objetivo"), int) and not isinstance(p.get("objetivo"), bool)]


def _valido(p: Any) -> bool:
    return (isinstance(p, dict) and isinstance(p.get("id"), str)
            and isinstance(p.get("nombre"), str) and p.get("color") in COLORES)


class Perfiles:
    """Perfiles y sus historiales. Seguro entre hilos."""

    def __init__(self, directorio: Path) -> None:
        self.directorio = Path(directorio)
        self._ruta = self.directorio / "perfiles.json"
        self._candado = threading.RLock()

    # -- lectura ---------------------------------------------------------------

    def listar(self) -> List[Dict[str, Any]]:
        with self._candado:
            try:
                datos = json.loads(self._ruta.read_text(encoding="utf-8"))
            except FileNotFoundError:
                return []
            except (OSError, ValueError):
                log.warning("perfiles: %s ilegible; se ignora", self._ruta)
                return []
            lista = datos.get("perfiles") if isinstance(datos, dict) else None
            return [dict(p) for p in (lista or []) if _valido(p)]

    def obtener(self, perfil_id: Optional[str]) -> Optional[Dict[str, Any]]:
        return next((p for p in self.listar() if p["id"] == perfil_id), None)

    def historial_de(self, perfil_id: str) -> Historial:
        if not perfil_id.isalnum():               # el id es parte del nombre del archivo
            raise PerfilInvalido("perfil desconocido")
        return Historial(self.directorio / f"{perfil_id}.jsonl")

    # -- cambios ---------------------------------------------------------------

    def _escribir(self, perfiles: List[Dict[str, Any]]) -> None:
        self.directorio.mkdir(parents=True, exist_ok=True)
        tmp = self._ruta.with_suffix(".tmp")
        tmp.write_text(json.dumps({"v": 1, "perfiles": perfiles}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, self._ruta)               # un corte no deja el archivo a medias

    def crear(self, datos: Mapping[str, Any], ahora: Optional[datetime] = None) -> Dict[str, Any]:
        with self._candado:
            perfiles = self.listar()
            if len(perfiles) >= MAX_PERFILES:
                raise PerfilInvalido(f"Ya hay {MAX_PERFILES} perfiles; borra uno para crear otro.")
            perfil = {"id": "p" + secrets.token_hex(4), **_limpiar(datos, perfiles),
                      "creado": (ahora or datetime.now()).replace(microsecond=0).isoformat()}
            perfiles.append(perfil)
            self._escribir(perfiles)
            if len(perfiles) == 1:
                self._heredar_historial_antiguo(perfil["id"])
            return perfil

    def editar(self, perfil_id: str, datos: Mapping[str, Any]) -> Dict[str, Any]:
        with self._candado:
            perfiles = self.listar()
            i = next((k for k, p in enumerate(perfiles) if p["id"] == perfil_id), None)
            if i is None:
                raise PerfilInvalido("Ese perfil ya no existe.")
            otros = perfiles[:i] + perfiles[i + 1:]
            perfiles[i] = {**perfiles[i], **_limpiar(datos, otros, perfiles[i])}
            self._escribir(perfiles)
            return perfiles[i]

    def guardar_rutina(self, perfil_id: str, pasos: List[Mapping[str, Any]]) -> Dict[str, Any]:
        """Guarda la rutina del perfil tal cual ([{skill_id, objetivo}]). La
        validación contra el catálogo (ejercicio soportado, objetivo en sus
        límites) la hace el orquestador antes de llamar aquí."""
        if len(pasos) > MAX_PASOS_RUTINA:
            raise PerfilInvalido("La rutina tiene demasiados ejercicios.")
        limpios = rutina_de({"rutina": list(pasos)}) or []
        if len(limpios) != len(pasos):
            raise PerfilInvalido("La rutina tiene pasos que no se pueden guardar.")
        with self._candado:
            perfiles = self.listar()
            i = next((k for k, p in enumerate(perfiles) if p["id"] == perfil_id), None)
            if i is None:
                raise PerfilInvalido("Ese perfil ya no existe.")
            perfiles[i] = {**perfiles[i], "rutina": limpios}
            self._escribir(perfiles)
            return perfiles[i]

    def borrar(self, perfil_id: str) -> bool:
        """Borra el perfil y su historial. False si no existía."""
        with self._candado:
            perfiles = self.listar()
            quedan = [p for p in perfiles if p["id"] != perfil_id]
            if len(quedan) == len(perfiles):
                return False
            self.historial_de(perfil_id).borrar()
            self._escribir(quedan)
            return True

    def _heredar_historial_antiguo(self, perfil_id: str) -> None:
        """El historial de una sola usuaria (ADR-008) pasa al primer perfil."""
        antiguo = self.directorio / HISTORIAL_ANTIGUO
        if antiguo.exists():
            os.replace(antiguo, self.historial_de(perfil_id).ruta)
            log.info("historial anterior asignado al perfil %s", perfil_id)


__all__ = ["COLORES", "MAX_NOMBRE", "MAX_PASOS_RUTINA", "MAX_PERFILES", "META_MAX", "META_MIN",
           "PerfilInvalido", "Perfiles", "rutina_de"]
