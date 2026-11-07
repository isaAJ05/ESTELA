"""Historial de sesiones y progreso de la usuaria (ADR-008).

Al terminar cada sesión se guarda **un registro mínimo** en un archivo local
(JSON Lines, una sesión por línea) y el panel «Mi progreso» lo resume.

Qué se guarda y qué no (CLAUDE.md §6, Ley 1581/2012):

- Sí: fecha, nombre de la rutina, cómo terminó, y por ejercicio el objetivo,
  lo completado, la duración activa, las pausas y cuántas veces se dio cada
  indicación (`error_id` y la frase que se dijo, que es una plantilla).
- No: frames, keypoints, ángulos por repetición, latencias, abstenciones del
  motor ni nada que permita reconstruir el cuerpo o el movimiento. Esos datos
  siguen saliendo solo con `--guardar-metricas`, para experimentos.

Qué significan las cifras (ADR-008 §2.4): miden constancia y qué indicaciones
se recibieron. **No miden la técnica**: el motor deja un tiempo mínimo entre
correcciones (`refractario_ms`) y se abstiene cuando no ve bien, así que menos
indicaciones no prueba que se haga mejor. Por eso las indicaciones frecuentes
se cuentan como «en cuántas sesiones apareció», no como una nota.

Todo corre fuera del bucle por frame: se escribe una vez al cerrar la sesión.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

log = logging.getLogger(__name__)

VERSION_REGISTRO = 1
#: semanas que muestra el gráfico de actividad (incluye la actual)
SEMANAS = 8
#: sesiones que lista el historial
RECIENTES = 20
#: sesiones de cada ejercicio en las que se miran las indicaciones frecuentes
VENTANA_INDICACIONES = 5
#: indicaciones frecuentes que se muestran por ejercicio
MAX_INDICACIONES = 3


# ---------------------------------------------------------------------------
# Registro de una sesión
# ---------------------------------------------------------------------------

def _indicaciones(mensajes: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Correcciones dichas, por `error_id`, con la frase más repetida.
    Los refuerzos («vas bien») no tienen `error_id` y no cuentan."""
    veces: Counter = Counter()
    frases: Dict[str, Counter] = {}
    for m in mensajes:
        eid = m.get("error_id")
        if not eid:
            continue
        veces[eid] += 1
        frases.setdefault(eid, Counter())[m.get("texto") or ""] += 1
    return {eid: {"veces": n, "texto": frases[eid].most_common(1)[0][0]}
            for eid, n in veces.items()}


def registro_de_sesion(resumen: Mapping[str, Any], fecha: datetime,
                       motivo_fin: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """`Sesion.resumen()` → registro para el historial, con solo los campos de
    la lista blanca del docstring. None si no se llegó a hacer nada (ningún
    ejercicio con una repetición o un segundo contado): abrir y cerrar no es
    una sesión."""
    pasos = []
    for p in resumen.get("pasos", ()):
        pasos.append({
            "skill_id": p["skill_id"],
            "unidad": p["unidad"],
            "objetivo": int(p["objetivo"]),
            "completadas": int(p["completadas"]),
            "incompletas": int(p.get("incompletas", 0)),
            "duracion_s": float(p.get("duracion_s", 0.0)),
            "pausas": int(p.get("pausas_sesion", 0)),
            "indicaciones": _indicaciones(p.get("mensajes", ())),
        })
    if not any(p["completadas"] > 0 for p in pasos):
        return None
    return {
        "v": VERSION_REGISTRO,
        "fecha": fecha.replace(microsecond=0).isoformat(),
        "rutina": str(resumen.get("rutina", ""))[:60],
        "terminada": bool(resumen.get("terminada")),
        "motivo_fin": motivo_fin,
        "duracion_s": round(sum(p["duracion_s"] for p in pasos), 1),
        "pasos": pasos,
    }


def _valido(r: Any) -> bool:
    if not isinstance(r, dict) or r.get("v") != VERSION_REGISTRO:
        return False
    try:
        datetime.fromisoformat(r["fecha"])
        return all(isinstance(p, dict) and isinstance(p.get("skill_id"), str)
                   and isinstance(p.get("completadas"), int) for p in r["pasos"])
    except (KeyError, TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Archivo
# ---------------------------------------------------------------------------

class Historial:
    """Archivo JSON Lines solo en este equipo. Se añade una línea por sesión,
    así un cierre a medias estropea como mucho la última, que se ignora al
    leer. Seguro entre hilos: escribe el hilo de la sesión y lee el de la
    interfaz."""

    def __init__(self, ruta: Path) -> None:
        self.ruta = Path(ruta)
        self._candado = threading.Lock()

    def agregar(self, registro: Mapping[str, Any]) -> None:
        linea = json.dumps(registro, ensure_ascii=False, separators=(",", ":"))
        with self._candado:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            with open(self.ruta, "a", encoding="utf-8") as fh:
                fh.write(linea + "\n")

    def leer(self) -> List[Dict[str, Any]]:
        """Registros válidos, del más antiguo al más nuevo."""
        with self._candado:
            try:
                lineas = self.ruta.read_text(encoding="utf-8").splitlines()
            except FileNotFoundError:
                return []
        registros, malas = [], 0
        for linea in lineas:
            if not linea.strip():
                continue
            try:
                r = json.loads(linea)
            except ValueError:
                r = None
            if _valido(r):
                registros.append(r)
            else:
                malas += 1
        if malas:
            log.warning("historial: %d líneas ilegibles ignoradas en %s", malas, self.ruta)
        registros.sort(key=lambda r: r["fecha"])
        return registros

    def borrar(self) -> None:
        with self._candado:
            self.ruta.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Progreso
# ---------------------------------------------------------------------------

def _dia(r: Mapping[str, Any]) -> date:
    return datetime.fromisoformat(r["fecha"]).date()


def racha_dias(dias: Sequence[date], hoy: date) -> int:
    """Días seguidos con alguna sesión, contando hacia atrás desde hoy. Si hoy
    todavía no hay sesión, se cuenta desde ayer: la racha no se rompe hasta
    que pasa un día entero sin moverse."""
    activos = set(dias)
    dia = hoy if hoy in activos else hoy - timedelta(days=1)
    n = 0
    while dia in activos:
        n += 1
        dia -= timedelta(days=1)
    return n


def _semanas(registros: Sequence[Mapping[str, Any]], hoy: date,
             n: int) -> List[Dict[str, Any]]:
    """Últimas `n` semanas (lunes a domingo), de la más antigua a la actual."""
    lunes = hoy - timedelta(days=hoy.weekday())
    inicios = [lunes - timedelta(weeks=k) for k in range(n - 1, -1, -1)]
    filas = {d: {"inicio": d.isoformat(), "sesiones": 0, "duracion_s": 0.0} for d in inicios}
    for r in registros:
        d = _dia(r)
        semana = d - timedelta(days=d.weekday())
        if semana in filas:
            filas[semana]["sesiones"] += 1
            filas[semana]["duracion_s"] += r["duracion_s"]
    for f in filas.values():
        f["duracion_s"] = round(f["duracion_s"], 1)
    return [filas[d] for d in inicios]


def _ejercicios(registros: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Por ejercicio, solo las veces que se hizo (completadas > 0)."""
    hechos: Dict[str, List[tuple]] = {}
    for r in registros:                          # ya vienen ordenados por fecha
        for p in r["pasos"]:
            if p["completadas"] > 0:
                hechos.setdefault(p["skill_id"], []).append((r["fecha"], p))
    salida = []
    for sid, lista in hechos.items():
        ultimo_fecha, ultimo = lista[-1]
        ventana = lista[-VENTANA_INDICACIONES:]
        sesiones_con: Counter = Counter()
        veces: Counter = Counter()
        texto: Dict[str, str] = {}
        for _, p in ventana:
            for eid, d in (p.get("indicaciones") or {}).items():
                sesiones_con[eid] += 1
                veces[eid] += int(d.get("veces", 0))
                texto[eid] = d.get("texto") or texto.get(eid, "")
        frecuentes = sorted(sesiones_con, key=lambda e: (-sesiones_con[e], -veces[e], e))
        salida.append({
            "skill_id": sid,
            "unidad": ultimo["unidad"],
            "veces": len(lista),
            "ultima_fecha": ultimo_fecha,
            "ultimo": {"completadas": ultimo["completadas"], "objetivo": ultimo["objetivo"]},
            "mejor": max(p["completadas"] for _, p in lista),
            "objetivo_cumplido": sum(1 for _, p in lista if p["completadas"] >= p["objetivo"]),
            # lo completado frente al objetivo en las últimas sesiones (gráfico pequeño)
            "recientes": [{"fecha": f, "completadas": p["completadas"], "objetivo": p["objetivo"]}
                          for f, p in lista[-10:]],
            "indicaciones": {
                "sesiones": len(ventana),
                "frecuentes": [{"error_id": e, "texto": texto[e], "sesiones": sesiones_con[e],
                                "veces": veces[e]} for e in frecuentes[:MAX_INDICACIONES]],
            },
        })
    salida.sort(key=lambda e: e["ultima_fecha"], reverse=True)
    return salida


def progreso(registros: Sequence[Mapping[str, Any]], hoy: date) -> Dict[str, Any]:
    """Resumen para el panel «Mi progreso». `registros` en orden de fecha
    (`Historial.leer`); `hoy` se pasa para poder probarlo."""
    dias = [_dia(r) for r in registros]
    hace_7 = hoy - timedelta(days=6)
    lunes = hoy - timedelta(days=hoy.weekday())
    sesiones = []
    for r in reversed(registros[-RECIENTES:]):
        pasos = r["pasos"]
        sesiones.append({
            "fecha": r["fecha"],
            "rutina": r["rutina"],
            "terminada": r["terminada"],
            "duracion_s": r["duracion_s"],
            "ejercicios": len(pasos),
            "completos": sum(1 for p in pasos if p["completadas"] >= p["objetivo"]),
            "indicaciones": sum(int(d.get("veces", 0)) for p in pasos
                                for d in (p.get("indicaciones") or {}).values()),
            "pasos": [{"skill_id": p["skill_id"], "unidad": p["unidad"],
                       "completadas": p["completadas"], "objetivo": p["objetivo"]}
                      for p in pasos],
        })
    return {
        "total_sesiones": len(registros),
        "total_duracion_s": round(sum(r["duracion_s"] for r in registros), 1),
        "dias_activos": len(set(dias)),
        "dias_activos_7": len({d for d in dias if hace_7 <= d <= hoy}),
        # días con sesión de lunes a hoy: lo que se compara con la meta semanal (ADR-009)
        "dias_semana_actual": len({d for d in dias if lunes <= d <= hoy}),
        "racha_dias": racha_dias(dias, hoy),
        "primera_fecha": registros[0]["fecha"] if registros else None,
        "semanas": _semanas(registros, hoy, SEMANAS),
        "ejercicios": _ejercicios(registros),
        "sesiones": sesiones,
    }


__all__ = ["Historial", "progreso", "racha_dias", "registro_de_sesion",
           "SEMANAS", "RECIENTES", "VENTANA_INDICACIONES", "VERSION_REGISTRO"]
