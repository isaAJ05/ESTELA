"""¿Está haciendo el ejercicio elegido? (EXP-010, variante `dtw_multi+rel`).

Aviso de operación de la sesión, como el de orientación o el de encuadre:
no corrige técnica y no pasa por el motor de feedback (ADR-001, ADR-004).
Avisa «ese movimiento no es el de ahora» sin nombrar qué ejercicio parece,
porque equivocarse de nombre confunde más que no darlo (EXP-010 §7.2).

Cómo decide, cada frame:

* Todos los ejercicios se comparan en un **vector común** de 11 medidas
  (`MEDIDAS`), cada una dividida por su dispersión entre referencias. Las
  referencias del catálogo no sirven para esto: cada una mira medidas
  distintas (EXP-010 §5.1).
* Hay varias referencias por ejercicio (`referencias/reconocimiento.json`,
  `scripts/crear_referencias_reconocimiento.py`), cada una con su espejo
  izquierda↔derecha. Las cíclicas se comparan con DTW de subsecuencia
  (inicio y final abiertos, O(m) por frame); la plancha, con su postura media.
* Coste de un ejercicio = mínimo entre sus referencias, y luego mínimo en los
  últimos `VENTANA_MS` (una repetición «termina» solo de vez en cuando).
* Movimiento equivocado si el elegido no se parece (coste > `TAU_NO`) u otro
  se parece claramente más (coste < `TAU_SI` y < `RATIO` × el del elegido).
  Si no hay otro claro, solo cuenta con movimiento (`ACTIVIDAD_MIN`): quedarse
  quieta no es «otro ejercicio».
* Si el segmentador del elegido cerró una repetición (o un segundo de
  plancha) en los últimos `VENTANA_MS`, el caso «no se parece» no avisa: solo
  el de «otro se parece claramente más». Es la variante de `+seg` que EXP-010
  §7.3 propuso para cortar falsas alarmas cuando la usuaria hace el ejercicio
  a su manera; `[?]` sin medir todavía.
* El estado tiene que durar `SOSTENIDO_MS`, y nada se decide en los primeros
  `CALENTAMIENTO_MS`.

`[F]` EXP-010 §10 (15 vídeos, umbrales elegidos sobre esos mismos datos, así
que optimistas): falsa alarma 1/12 con el ejercicio correcto, detección 81 %
con otro de los cuatro, latencia p95 ~1,5 ms por frame. `[?]` Falta medir con
vídeos propios grabados con la orientación de ADR-005 (EXP-010 §7.3).
"""

from __future__ import annotations

import json
import math
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from ..dominio.feedback.motor.skill import directorio_skills

#: vector común: lo que distingue los cuatro ejercicios entre sí (EXP-010 §3)
MEDIDAS = ("hombro_izq", "hombro_der", "codo_medio", "separacion_pies_hombros",
           "abduccion_cadera_izq", "abduccion_cadera_der", "cadera_izq", "cadera_der",
           "rodilla_izq", "rodilla_der", "tronco_inclinacion")
CLASE_DE_SKILL = {"jumping_jacks": "jumping_jacks",
                  "abduccion_cadera_izq": "abduccion", "abduccion_cadera_der": "abduccion",
                  "marcha_rodillas": "marcha_rodillas", "plancha": "plancha"}
CONFIANZA_MINIMA = 0.5
#: de perfil los hombros se superponen y el cociente pies/hombros se dispara
MAXIMO = {"separacion_pies_hombros": 3.0}
#: escala mínima por medida para la actividad (grados; la separación es un cociente)
ESCALA_MIN = {"separacion_pies_hombros": 0.15}
ESCALA_MIN_ANGULO = 8.0

#: umbrales de EXP-010 §7 y §10 `[I]` provisionales
TAU_NO = 0.75
TAU_SI = 0.75
RATIO = 0.7
ACTIVIDAD_MIN = 0.25
VENTANA_MS = 4000
ACTIVIDAD_VENTANA_MS = 2000
SOSTENIDO_MS = 3000
CALENTAMIENTO_MS = 2000
#: coste local de un frame de referencia sin medidas comparables: grande pero
#: finito, para que la suma acumulada del DTW no dé inf − inf
_SIN_DATO = 1e6


def ruta_por_defecto() -> Path:
    return Path(directorio_skills()) / "referencias" / "reconocimiento.json"


def espejo(nombre: str) -> str:
    if nombre.endswith("_izq"):
        return nombre[:-4] + "_der"
    if nombre.endswith("_der"):
        return nombre[:-4] + "_izq"
    return nombre


def vector_comun(obs) -> np.ndarray:
    """Las medidas de `MEDIDAS` de una observación; NaN si falta o es poco fiable."""
    x = np.full(len(MEDIDAS), np.nan)
    for j, nombre in enumerate(MEDIDAS):
        v = obs.angulos.get(nombre, obs.distancias.get(nombre))
        if v is None or obs.confianza.get(nombre, 0.0) < CONFIANZA_MINIMA:
            continue
        if nombre in MAXIMO and v > MAXIMO[nombre]:
            continue
        x[j] = v
    return x


# ---------------------------------------------------------------------------
# Comparadores
# ---------------------------------------------------------------------------

class Subsecuencia:
    """Mejor coincidencia de la referencia completa que termina en el frame
    actual, empezando en cualquier frame anterior (DTW de subsecuencia).

    Misma recurrencia que `AlineadorDTW` (pasos simétricos, una columna de m
    celdas), con inicio abierto. El coste se divide por m y no por la
    longitud del camino: así, quedarse en el reposo de la referencia no
    diluye el extremo (EXP-010 §3).
    """

    def __init__(self, media: np.ndarray, escala: np.ndarray) -> None:
        self.media, self.escala = media, escala
        self.m = len(media)
        self._col = np.full(self.m, np.inf)

    def actualizar(self, x: np.ndarray) -> float:
        dif = np.abs(self.media - x) / self.escala
        validas = np.isfinite(dif)
        n = validas.sum(axis=1)
        if not n.any():
            return math.inf                # frame sin medidas: no mueve nada
        local = np.where(n > 0, np.where(validas, dif, 0).sum(axis=1) / np.maximum(n, 1),
                         _SIN_DATO)
        # col[j] = local[j] + min(previo[j-1], previo[j], col[j-1]), con
        # col[0] = local[0] (inicio abierto). La dependencia de col[j-1] se
        # resuelve sin bucle: col = L + mínimo acumulado de (b − L[j-1]),
        # con L la suma acumulada de `local` y b = min(previo[j-1], previo[j]).
        b = np.empty(self.m)
        b[0] = 0.0
        b[1:] = np.minimum(self._col[:-1], self._col[1:])
        acum = np.cumsum(local)
        previa = np.concatenate(([0.0], acum[:-1]))
        self._col = acum + np.minimum.accumulate(b - previa)
        return float(self._col[-1] / self.m)


class Postura:
    """Plancha: diferencia media con la postura media, sin DTW."""

    def __init__(self, media: np.ndarray, escala: np.ndarray) -> None:
        self.media, self.escala = media, escala

    def actualizar(self, x: np.ndarray) -> float:
        d = np.abs(self.media - x) / self.escala
        return float(np.nanmean(d)) if np.isfinite(d).any() else math.inf


class Referencias:
    """Contenido de `reconocimiento.json`: por clase, (tipo, media) de cada
    referencia en el vector común, más la escala por medida."""

    def __init__(self, datos: Mapping) -> None:
        if tuple(datos["medidas"]) != MEDIDAS:
            raise ValueError("las referencias de reconocimiento usan otras medidas")
        self.escala = np.asarray(datos["escala"], float)
        self.por_clase: Dict[str, List[Tuple[str, np.ndarray]]] = {}
        for r in datos["referencias"]:
            media = np.array([[np.nan if v is None else v for v in fila] for fila in r["media"]],
                             float)
            self.por_clase.setdefault(r["clase"], []).append((r["tipo"], media))

    @classmethod
    def cargar(cls, ruta: Optional[Path] = None) -> Optional["Referencias"]:
        ruta = Path(ruta or ruta_por_defecto())
        if not ruta.is_file():
            return None
        with open(ruta, encoding="utf-8") as f:
            return cls(json.load(f))

    def comparadores(self) -> Dict[str, list]:
        """Comparadores nuevos (con su estado), cada referencia con su espejo."""
        perm = [MEDIDAS.index(espejo(m)) for m in MEDIDAS]
        out: Dict[str, list] = {}
        for clase, lista in self.por_clase.items():
            for tipo, media in lista:
                for mm in (media, media[:, perm]):
                    comp = (Postura(mm[0], self.escala) if tipo == "isometrico"
                            else Subsecuencia(mm, self.escala))
                    out.setdefault(clase, []).append(comp)
        return out


# ---------------------------------------------------------------------------
# Decisión
# ---------------------------------------------------------------------------

class ReconocedorEjercicio:
    """Dice, frame a frame, si la usuaria lleva `SOSTENIDO_MS` haciendo un
    movimiento que no es el ejercicio elegido."""

    def __init__(self, clase: str, referencias: Referencias) -> None:
        if clase not in referencias.por_clase:
            raise ValueError(f"sin referencias de reconocimiento para '{clase}'")
        self.clase = clase
        self._comps = referencias.comparadores()
        self._costes: Dict[str, Deque[Tuple[int, float]]] = {c: deque() for c in self._comps}
        self._recientes: Deque[Tuple[int, np.ndarray]] = deque()
        self._esc_act = np.array([ESCALA_MIN.get(m, ESCALA_MIN_ANGULO) for m in MEDIDAS])
        self._t0: Optional[int] = None
        self._desde: Optional[int] = None
        self._ult_propio: Optional[int] = None

    def actualizar(self, obs, cuenta_propio: bool = False) -> bool:
        """`cuenta_propio`: el segmentador del ejercicio elegido cerró una
        repetición (completa o no) en este frame."""
        t = obs.t_ms
        if self._t0 is None:
            self._t0 = t
        if cuenta_propio:
            self._ult_propio = t
        x = vector_comun(obs)
        coste = {}
        for clase, comps in self._comps.items():
            c = min(comp.actualizar(x) for comp in comps)
            cola = self._costes[clase]
            cola.append((t, c))
            while t - cola[0][0] > VENTANA_MS:
                cola.popleft()
            coste[clase] = min(v for _, v in cola)
        self._recientes.append((t, x))
        while t - self._recientes[0][0] > ACTIVIDAD_VENTANA_MS:
            self._recientes.popleft()

        propio_reciente = self._ult_propio is not None and t - self._ult_propio <= VENTANA_MS
        if (t - self._t0 < CALENTAMIENTO_MS
                or not self.equivocado(coste, self.actividad(), propio_reciente)):
            self._desde = None
            return False
        if self._desde is None:
            self._desde = t
        return t - self._desde >= SOSTENIDO_MS

    def equivocado(self, coste: Mapping[str, float], actividad: float,
                   propio_reciente: bool = False) -> bool:
        """La regla de `dtw_multi+rel` (EXP-010 §10), sin nombrar el otro
        ejercicio. Con `propio_reciente`, solo avisa si otro es claro."""
        propio = coste[self.clase]
        otros = [v for c, v in coste.items() if c != self.clase]
        otro = min(otros) if otros else math.inf
        claro = otro < TAU_SI and otro < RATIO * propio
        if not (propio > TAU_NO or claro):
            return False
        if propio_reciente and not claro:
            return False
        return claro or actividad >= ACTIVIDAD_MIN

    def actividad(self) -> float:
        """Mediana entre medidas de su σ en `ACTIVIDAD_VENTANA_MS`, en unidades
        de `ESCALA_MIN`: quieta ≈ jitter."""
        if len(self._recientes) < 2:
            return 0.0
        x = np.array([v for _, v in self._recientes])
        validas = np.isfinite(x).sum(axis=0) >= 2
        if not validas.any():
            return 0.0
        s = np.nanstd(x[:, validas], axis=0) / self._esc_act[validas]
        return float(np.median(s))


_CACHE: Dict[str, Optional[Referencias]] = {}


def reconocedor_para(skill_id: str, ruta: Optional[Path] = None
                     ) -> Optional[ReconocedorEjercicio]:
    """El reconocedor del ejercicio, o None si el skill no es uno de los
    cuatro o no hay referencias de reconocimiento."""
    clase = CLASE_DE_SKILL.get(skill_id)
    if clase is None:
        return None
    clave = str(ruta or ruta_por_defecto())
    if clave not in _CACHE:
        _CACHE[clave] = Referencias.cargar(Path(clave))
    refs = _CACHE[clave]
    if refs is None or clase not in refs.por_clase:
        return None
    return ReconocedorEjercicio(clase, refs)


__all__ = ["MEDIDAS", "CLASE_DE_SKILL", "Referencias", "ReconocedorEjercicio",
           "reconocedor_para", "vector_comun", "ruta_por_defecto"]
