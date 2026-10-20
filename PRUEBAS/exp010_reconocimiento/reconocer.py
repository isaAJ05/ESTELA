"""EXP-010 · Paso 2: ¿está haciendo el ejercicio elegido?

Desde ESTELA/, después de `extraer.py`:

    python PRUEBAS/exp010_reconocimiento/reconocer.py

Lee `cache/*.npz` (pose ya hecha) y, para cada vídeo y cada ejercicio
«elegido», simula una sesión y anota si salta el aviso «ese no es el
ejercicio». Compara tres detectores:

``segmentadores``  Línea base sin DTW: los segmentadores de los cinco skills
                   corren en paralelo. Aviso si otro ejercicio cuenta ≥ 2
                   repeticiones (o 2 s de plancha) en la ventana y el elegido
                   ninguna.
``dtw_propias``    DTW de subsecuencia contra las referencias actuales del
                   catálogo, cada una con sus medidas; el coste se divide por
                   el `coste_medoide_a_resto` de la referencia para poder
                   compararlo entre ejercicios.
``dtw_comun``      DTW de subsecuencia contra referencias reconstruidas con un
                   vector común de medidas (brazos + piernas + tronco),
                   normalizado por medida. Se construyen aquí con los mismos
                   vídeos de referencia del catálogo y el segmentador del skill.
``dtw_multi``      Como `dtw_comun`, pero con una referencia por cada vídeo de
                   docs_estela del ejercicio (salvo técnica incorrecta). Se
                   valida dejando uno fuera: cada vídeo se puntúa sin su propia
                   referencia (ni las que comparten frames con él, `GRUPO`), así
                   que «todos» ya es un resultado honesto.

Los dos DTW pueden combinarse con el segmentador del elegido (`+seg`): no se
avisa si el elegido completó una repetición en la ventana.

Escribe `resultados/<fecha>-exp010.json` y `.md` (ignorados por git).
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

AQUI = Path(__file__).resolve().parent
BACKEND = AQUI.parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from crear_referencia import estadistica_alineada, medoide                # noqa: E402
from estela.aplicacion.rutina import cargar_catalogo                      # noqa: E402
from estela.dominio.conteo.segmentador import EVENTO_COMPLETA            # noqa: E402
from estela.dominio.feedback.contrato import Observacion                 # noqa: E402

CACHE = AQUI / "cache"
RESULTADOS = AQUI / "resultados"

FPS = 30.0                 # la sesión ve la cámara a ~30 fps: todo se remuestrea
CONF_MIN = 0.5             # igual que crear_referencia.py y dtw.py
VENTANA_S = 4.0            # ventana de evidencia del aviso
SOSTENIDO_S = 3.0          # el estado «equivocado» debe durar esto antes de avisar
CALENTAMIENTO_S = 2.0      # sin aviso en los primeros segundos

CLASES = ("jumping_jacks", "abduccion", "marcha_rodillas", "plancha")
SKILLS_DE_CLASE = {"jumping_jacks": ("jumping_jacks",),
                   "abduccion": ("abduccion_cadera_izq", "abduccion_cadera_der"),
                   "marcha_rodillas": ("marcha_rodillas",),
                   "plancha": ("plancha",)}
# vídeo de origen de cada referencia del catálogo (ver `referencia.json`)
VIDEO_REF = {"jumping_jacks": "jj_7_hombre", "abduccion_cadera_der": "abd_der_ref",
             "abduccion_cadera_izq": "abd_izq_ref", "marcha_rodillas": "marcha_high_knees",
             "plancha": "plancha_1"}
#: dtw_multi: vídeos que comparten frames; en la validación salen juntos
GRUPO = {"abd_der_banda_completo": "abd_banda", "abd_der_ref": "abd_banda",
         "abd_izq_ref": "abd_banda"}
#: dtw_multi: no se usan como referencia los vídeos de técnica incorrecta a
#: propósito («plancha incorrecta 2», «plancha incorrrecta 1»)
def _es_incorrecto(v: "Video") -> bool:
    return "incorr" in v.video.lower()


MIN_REPS_REF = 2

#: vector común: lo que distingue los cuatro ejercicios entre sí
COMUN = ("hombro_izq", "hombro_der", "codo_medio", "separacion_pies_hombros",
         "abduccion_cadera_izq", "abduccion_cadera_der", "cadera_izq", "cadera_der",
         "rodilla_izq", "rodilla_der", "tronco_inclinacion")
#: escala mínima por medida al normalizar (grados; la separación es un cociente)
ESCALA_MIN = {"separacion_pies_hombros": 0.15}
ESCALA_MIN_ANGULO = 8.0
#: valores imposibles que se descartan (NaN, sin imputar): de perfil los hombros
#: se superponen y el cociente pies/hombros se dispara (medido: escala ~98)
MAXIMO = {"separacion_pies_hombros": 3.0}


def espejo(nombre: str) -> str:
    if nombre.endswith("_izq"):
        return nombre[:-4] + "_der"
    if nombre.endswith("_der"):
        return nombre[:-4] + "_izq"
    return nombre


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------

class Video:
    def __init__(self, ruta: Path) -> None:
        d = np.load(ruta, allow_pickle=False)
        self.id = ruta.stem
        self.clase, self.lado = str(d["clase"]), str(d["lado"])
        self.es_ref = bool(d["es_ref"])
        self.video = str(d["video"])
        self.nombres = [str(n) for n in d["nombres"]]
        es_dist = d["es_distancia"]
        t = d["t_ms"]
        # remuestreo a FPS: el frame más reciente en cada instante de la rejilla
        rejilla = np.arange(0, t[-1] + 1, 1000.0 / FPS)
        idx = np.clip(np.searchsorted(t, rejilla, side="right") - 1, 0, len(t) - 1)
        self.t_ms = np.round(rejilla).astype(int)
        self.valores = d["valores"][idx].astype(float)
        self.confianza = d["confianza"][idx].astype(float)
        self.presente = d["presente"][idx]
        self.orientacion = d["orientacion"][idx]
        self._es_dist = {n: bool(e) for n, e in zip(self.nombres, es_dist)}
        self._k = {n: i for i, n in enumerate(self.nombres)}

    def __len__(self) -> int:
        return len(self.t_ms)

    def serie(self, medidas: Sequence[str]) -> np.ndarray:
        """n × len(medidas), NaN si falta o con confianza < CONF_MIN."""
        out = np.full((len(self), len(medidas)), np.nan)
        for j, m in enumerate(medidas):
            k = self._k.get(m)
            if k is None:
                continue
            v = self.valores[:, k].copy()
            v[self.confianza[:, k] < CONF_MIN] = np.nan
            if m in MAXIMO:
                v[v > MAXIMO[m]] = np.nan
            out[:, j] = v
        out[~self.presente] = np.nan
        return out

    def observaciones(self) -> List[Optional[Observacion]]:
        obs: List[Optional[Observacion]] = []
        for i in range(len(self)):
            if not self.presente[i]:
                obs.append(None)
                continue
            ang, dist, conf = {}, {}, {}
            for n, k in self._k.items():
                v = self.valores[i, k]
                if np.isnan(v):
                    continue
                (dist if self._es_dist[n] else ang)[n] = float(v)
                conf[n] = float(self.confianza[i, k])
            o = self.orientacion[i]
            obs.append(Observacion(t_ms=int(self.t_ms[i]), ejercicio_id="exp010",
                                   angulos=ang, confianza=conf, distancias=dist,
                                   orientacion=None if np.isnan(o) else float(o)))
        return obs


# ---------------------------------------------------------------------------
# DTW de subsecuencia (SPRING): sin segmentador, inicio y final abiertos
# ---------------------------------------------------------------------------

class Subsecuencia:
    """Mejor coincidencia de la referencia completa que termina en el frame
    actual, empezando en cualquier frame anterior.

    Misma recurrencia que `AlineadorDTW._columna` (pasos simétricos, una
    columna de m celdas, O(m) por frame), con dos cambios: la celda 0 puede
    empezar de nuevo en cada frame (inicio abierto) y el coste se divide por
    m, no por la longitud del camino. Con la longitud del camino, quedarse
    quieta en el reposo de la referencia «diluye» el extremo y casi cualquier
    postura de pie parecería una repetición.
    """

    def __init__(self, media: np.ndarray, escala: np.ndarray) -> None:
        self.media, self.escala = media, escala
        self.m = len(media)
        self.reiniciar()

    def reiniciar(self) -> None:
        self._col = np.full(self.m, np.inf)

    def actualizar(self, x: np.ndarray) -> float:
        dif = np.abs(self.media - x) / self.escala
        validas = np.isfinite(dif)
        n = validas.sum(axis=1)
        if not n.any():
            return np.inf                  # frame sin medidas: no mueve nada
        local = np.where(n > 0, np.where(validas, dif, 0).sum(axis=1) / np.maximum(n, 1),
                         np.inf)
        previo, col = self._col, np.empty(self.m)
        col[0] = local[0]                  # inicio abierto: min(0, previo[0]) = 0
        for j in range(1, self.m):
            col[j] = local[j] + min(previo[j - 1], previo[j], col[j - 1])
        self._col = col
        return col[-1] / self.m


class Postura:
    """Plancha: diferencia media con la postura media (sin DTW)."""

    def __init__(self, media: np.ndarray, escala: np.ndarray) -> None:
        self.media, self.escala = media, escala

    def reiniciar(self) -> None:
        pass

    def actualizar(self, x: np.ndarray) -> float:
        d = np.abs(self.media - x) / self.escala
        return float(np.nanmean(d)) if np.isfinite(d).any() else np.inf


# ---------------------------------------------------------------------------
# Referencias
# ---------------------------------------------------------------------------

def _escala(medidas: Sequence[str], matrices: Sequence[np.ndarray]) -> np.ndarray:
    todo = np.vstack(matrices)
    with np.errstate(all="ignore"):
        s = np.nanstd(todo, axis=0)
    minimo = np.array([ESCALA_MIN.get(m, ESCALA_MIN_ANGULO) for m in medidas])
    return np.fmax(np.nan_to_num(s, nan=0.0), minimo)


def refs_propias(catalogo) -> Dict[str, List[Tuple[str, Any]]]:
    """Referencias del catálogo, cada una con sus medidas. Escala: el coste
    típico entre repeticiones correctas (`coste_medoide_a_resto`); en plancha,
    la σ media de la postura."""
    por_clase: Dict[str, List[Tuple[str, Any]]] = {}
    for clase, skills in SKILLS_DE_CLASE.items():
        for sid in skills:
            ref = catalogo[sid].referencia
            medidas = list(ref["medidas"])
            if ref.get("tipo") == "isometrico":
                media = np.array([np.nan if v is None else v for v in ref["postura"]["media"]])
                sigma = np.array([np.nan if v is None else v for v in ref["postura"]["sigma"]])
                esc = np.fmax(np.nan_to_num(sigma, nan=1.0), 1e-3)
                por_clase.setdefault(clase, []).append((sid, (medidas, Postura(media, esc))))
                continue
            media = np.array(ref["angulos"]["media"], dtype=float)
            media = _a_fps(media, float(ref["fps"]))
            c = float(ref["dtw"]["coste_medoide_a_resto"]) or 1.0
            por_clase.setdefault(clase, []).append(
                (sid, (medidas, Subsecuencia(media, np.full(len(medidas), c)))))
    return por_clase


def _a_fps(media: np.ndarray, fps: float) -> np.ndarray:
    t = np.arange(len(media)) / fps
    tt = np.arange(0, t[-1] + 1e-9, 1 / FPS)
    return np.stack([np.interp(tt, t, media[:, k]) if np.isfinite(media[:, k]).sum() > 1
                     else np.full(len(tt), np.nan) for k in range(media.shape[1])], axis=1)


def referencia_cruda(v: Video, catalogo, sid: str) -> Optional[Tuple[str, np.ndarray, Dict[str, Any]]]:
    """(tipo, media, info) de un vídeo en el vector común, cortado con el
    segmentador del skill `sid`. None si no da una referencia utilizable."""
    ej = catalogo[sid]
    seg = ej.nuevo_segmentador()
    x = v.serie(COMUN)
    if (ej.segmentacion or {}).get("tipo") == "isometrico":
        filas = [i for i, o in enumerate(v.observaciones())
                 if o is not None and seg.actualizar(o).fase == ej.skill.fases[1]]
        if len(filas) < FPS:               # menos de 1 s en posición
            return None
        with np.errstate(all="ignore"):
            media = np.nanmean(x[filas], axis=0, keepdims=True)
        return "isometrico", media, {"frames_en_posicion": len(filas)}
    grupos: Dict[int, List[int]] = {}
    completas = set()
    for i, o in enumerate(v.observaciones()):
        if o is None:
            continue
        e = seg.actualizar(o)
        if e.repeticion > 0:
            grupos.setdefault(e.repeticion, []).append(i)
            if e.evento == EVENTO_COMPLETA:
                completas.add(e.repeticion)
    reps = [x[grupos[r]] for r in sorted(completas)]
    reps = [r for r in reps if np.isfinite(r).any(axis=1).sum() >= 5]
    if len(reps) < MIN_REPS_REF:
        return None
    im, dist = medoide(reps)
    with np.errstate(all="ignore"):
        media, _, _ = estadistica_alineada(reps, im)
    return "ciclico", media, {
        "repeticiones": len(reps), "frames": len(media),
        "coste_medoide_a_resto": round(float(dist[im].sum() / max(len(reps) - 1, 1)), 3)}


def componer(crudas: Dict[str, Tuple[str, str, np.ndarray]]) -> Tuple[Dict[str, List[Tuple[str, Any]]],
                                                                      np.ndarray]:
    """{nombre: (clase, tipo, media)} → comparadores por clase, cada
    referencia con su espejo, todas con la misma escala por medida."""
    escala = _escala(COMUN, [m for _, _, m in crudas.values()])
    perm = [COMUN.index(espejo(m)) for m in COMUN]
    por_clase: Dict[str, List[Tuple[str, Any]]] = {}
    for nombre, (clase, tipo, media) in crudas.items():
        for sufijo, mm in (("", media), ("_espejo", media[:, perm])):
            comp = Postura(mm[0], escala) if tipo == "isometrico" else Subsecuencia(mm, escala)
            por_clase.setdefault(clase, []).append((nombre + sufijo, (list(COMUN), comp)))
    return por_clase, escala


def refs_comunes(catalogo, videos: Dict[str, Video]) -> Tuple[Dict[str, List[Tuple[str, Any]]],
                                                              Dict[str, Any]]:
    """Reconstruye cada referencia en el vector común, con el mismo vídeo y
    el mismo segmentador que la del catálogo, y le añade su espejo."""
    crudas: Dict[str, Tuple[str, str, np.ndarray]] = {}
    info: Dict[str, Any] = {}
    clase_de = {sid: c for c, skills in SKILLS_DE_CLASE.items() for sid in skills}
    for sid, vid in VIDEO_REF.items():
        tipo, media, info[sid] = referencia_cruda(videos[vid], catalogo, sid)
        crudas[sid] = (clase_de[sid], tipo, media)
    por_clase, escala = componer(crudas)
    info["escala"] = {m: round(float(s), 3) for m, s in zip(COMUN, escala)}
    return por_clase, info


def grupo(vid: str) -> str:
    return GRUPO.get(vid, vid)


def crudas_multi(catalogo, videos: Dict[str, Video]) -> Tuple[Dict[str, Tuple[str, str, np.ndarray]],
                                                              Dict[str, Any]]:
    """Una referencia por cada vídeo de docs_estela de los cuatro ejercicios
    (no «otro», no vídeos propios, no los de técnica incorrecta). En la
    abducción sin lado conocido se prueba el segmentador de cada pierna y se
    queda el que cuenta más repeticiones."""
    crudas: Dict[str, Tuple[str, str, np.ndarray]] = {}
    info: Dict[str, Any] = {}
    for vid, v in videos.items():
        if v.clase not in CLASES or vid.startswith("propio_") or _es_incorrecto(v):
            continue
        sids = SKILLS_DE_CLASE[v.clase]
        if v.clase == "abduccion" and v.lado:
            sids = (f"abduccion_cadera_{v.lado}",)
        mejor = None
        for sid in sids:
            r = referencia_cruda(v, catalogo, sid)
            if r and (mejor is None or r[2].get("repeticiones", 0) > mejor[1][2].get("repeticiones", 0)):
                mejor = (sid, r)
        if mejor is None:
            info[vid] = "descartado: sin repeticiones completas suficientes"
            continue
        sid, (tipo, media, i) = mejor
        crudas[vid] = (v.clase, tipo, media)
        info[vid] = {"skill": sid, **i}
    return crudas, info


def refs_multi(crudas: Dict[str, Tuple[str, str, np.ndarray]], excluir: str = "") -> Dict[str, List[Tuple[str, Any]]]:
    """Referencias multi sin las del grupo `excluir` (validación deja-uno-fuera)."""
    return componer({k: c for k, c in crudas.items() if not excluir or grupo(k) != grupo(excluir)})[0]


# ---------------------------------------------------------------------------
# Puntuaciones por frame
# ---------------------------------------------------------------------------

def puntuar(v: Video, refs: Dict[str, List[Tuple[str, Any]]]) -> Tuple[Dict[str, np.ndarray], List[float]]:
    """Coste por clase y frame = mínimo en la ventana del mínimo entre sus
    referencias (una repetición «termina» solo de vez en cuando)."""
    crudo: Dict[str, np.ndarray] = {}
    tiempos = np.zeros(len(v))
    for clase, lista in refs.items():
        cols = []
        for _, (medidas, comp) in lista:
            comp.reiniciar()
            x = v.serie(medidas)
            s = np.empty(len(v))
            for i in range(len(v)):
                t0 = time.perf_counter()
                s[i] = comp.actualizar(x[i])
                tiempos[i] += (time.perf_counter() - t0) * 1000
            cols.append(s)
        crudo[clase] = np.min(cols, axis=0)
    w = int(VENTANA_S * FPS)
    ventana = {c: np.array([np.min(s[max(0, i - w + 1):i + 1]) for i in range(len(s))])
               for c, s in crudo.items()}
    return ventana, tiempos.tolist()


def actividad(v: Video) -> np.ndarray:
    """Movimiento en la ventana: media sobre el vector común de la σ temporal
    normalizada por la escala mínima. Quieta ≈ jitter."""
    x = v.serie(COMUN)
    esc = np.array([ESCALA_MIN.get(m, ESCALA_MIN_ANGULO) for m in COMUN])
    w = int(2.0 * FPS)
    out = np.zeros(len(v))
    for i in range(len(v)):
        seg = x[max(0, i - w + 1):i + 1]
        with np.errstate(all="ignore"):
            s = np.nanstd(seg, axis=0) / esc
        out[i] = np.nanmedian(s) if np.isfinite(s).any() else 0.0
    return out


def completadas(v: Video, catalogo) -> Dict[str, np.ndarray]:
    """Por clase: 1 en los frames en que algún skill de la clase completa una
    repetición (o un segundo en posición, en la plancha)."""
    obs = v.observaciones()
    out = {}
    for clase, skills in SKILLS_DE_CLASE.items():
        marca = np.zeros(len(v))
        for sid in skills:
            seg = catalogo[sid].nuevo_segmentador()
            for i, o in enumerate(obs):
                if o is None:
                    seg.interrumpir() if hasattr(seg, "interrumpir") else None
                    continue
                if seg.actualizar(o).evento == EVENTO_COMPLETA:
                    marca[i] = 1
        out[clase] = marca
    return out


# ---------------------------------------------------------------------------
# Decisión (lo que haría la sesión) y métricas
# ---------------------------------------------------------------------------

def decidir(elegida: str, n: int, punt: Optional[Dict[str, np.ndarray]],
            comp: Dict[str, np.ndarray], act: np.ndarray, metodo: str,
            tau_no: float, tau_si: float, act_min: float, con_seg: bool,
            ratio: float = 0.7, relativo: bool = False) -> List[Tuple[float, str]]:
    """Avisos [(t_s, etiqueta)]: etiqueta = clase reconocida o 'no_reconocido'.
    Un aviso por estado sostenido; se repite como mucho cada 8 s."""
    w = int(VENTANA_S * FPS)
    sost = int(SOSTENIDO_S * FPS)
    cum = {c: np.cumsum(m) for c, m in comp.items()}

    def en_ventana(c: str, i: int) -> float:
        return cum[c][i] - (cum[c][i - w] if i >= w else 0)

    avisos: List[Tuple[float, str]] = []
    estado, desde, ultimo = None, 0, -1e9
    for i in range(n):
        e = None
        if i >= CALENTAMIENTO_S * FPS:
            propio = en_ventana(elegida, i)
            if metodo == "segmentadores":
                if propio == 0:
                    otras = [(en_ventana(c, i), c) for c in CLASES if c != elegida]
                    k, c = max(otras)
                    if k >= 2:
                        e = c
                    elif act[i] >= act_min:
                        e = "no_reconocido"
            elif not (con_seg and propio > 0):
                s_el = punt[elegida][i]
                s_o, c = min((punt[c][i], c) for c in CLASES if c != elegida)
                claro = s_o < tau_si and s_o < ratio * s_el
                # relativo: también avisa si otro ejercicio se parece claramente
                # más, aunque el elegido no pase de tau_no
                if s_el > tau_no or (relativo and claro):
                    if claro:
                        e = c
                    elif act[i] >= act_min:
                        e = "no_reconocido"
        if e != estado:
            estado, desde = e, i
        if e is not None and i - desde + 1 >= sost and i / FPS - ultimo >= 8.0:
            avisos.append((round(i / FPS, 2), e))
            ultimo = i / FPS
    return avisos


def evaluar(casos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """casos: {video, real, elegida, es_ref, avisos}."""
    def frac(xs):
        return round(sum(xs) / len(xs), 3) if xs else None
    bien = [c for c in casos if c["real"] == c["elegida"]]
    mal = [c for c in casos if c["real"] != c["elegida"] and c["real"] != "otro"]
    otro = [c for c in casos if c["real"] == "otro"]
    primeros = [c["avisos"][0][0] for c in mal + otro if c["avisos"]]
    return {
        "n_correctos": len(bien),
        "falsa_alarma": frac([bool(c["avisos"]) for c in bien]),
        "falsa_alarma_otro_ejercicio": frac([any(a[1] != "no_reconocido" for a in c["avisos"])
                                             for c in bien]),
        "n_equivocados": len(mal),
        "deteccion": frac([bool(c["avisos"]) for c in mal]),
        "etiqueta_correcta": frac([bool(c["avisos"]) and c["avisos"][0][1] == c["real"]
                                   for c in mal]),
        "n_otros": len(otro) // max(len(CLASES), 1),
        "deteccion_otro": frac([bool(c["avisos"]) for c in otro]),
        "otro_confundido_con_ejercicio": frac([bool(c["avisos"]) and c["avisos"][0][1] != "no_reconocido"
                                               for c in otro]),
        "t_primer_aviso_s_mediana": round(float(np.median(primeros)), 2) if primeros else None,
    }


def confusion(videos, punts, acts, act_min) -> Dict[str, Dict[str, int]]:
    """Frame a frame, con movimiento: clase de menor coste frente a la real."""
    m: Dict[str, Dict[str, int]] = {}
    for v in videos:
        p = punts[v.id]
        for i in range(int(CALENTAMIENTO_S * FPS), len(v)):
            if acts[v.id][i] < act_min and v.clase != "plancha":
                continue
            s = {c: p[c][i] for c in CLASES}
            pred = min(s, key=s.get) if np.isfinite(min(s.values())) else "sin_dato"
            fila = m.setdefault(v.clase, {})
            fila[pred] = fila.get(pred, 0) + 1
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--act-min", type=float, default=0.25)
    a = ap.parse_args()

    catalogo = cargar_catalogo()
    from extraer import BANCO
    videos = {vid: Video(CACHE / f"{vid}.npz") for vid, *_ in BANCO
              if (CACHE / f"{vid}.npz").exists()}
    print(f"{len(videos)} vídeos, {sum(len(v) for v in videos.values())} frames a {FPS:.0f} fps")
    rp = refs_propias(catalogo)
    rc, info_comun = refs_comunes(catalogo, videos)
    print("referencias comunes:", json.dumps(info_comun, ensure_ascii=False))
    cm, info_multi = crudas_multi(catalogo, videos)
    print("referencias multi:", json.dumps(info_multi, ensure_ascii=False))

    acts = {k: actividad(v) for k, v in videos.items()}
    comps = {k: completadas(v, catalogo) for k, v in videos.items()}
    punts: Dict[str, Dict[str, Dict[str, np.ndarray]]] = {"dtw_propias": {}, "dtw_comun": {},
                                                          "dtw_multi": {}}
    lat: Dict[str, List[float]] = {"dtw_propias": [], "dtw_comun": [], "dtw_multi": []}
    for k, v in videos.items():
        # dtw_multi: deja-uno-fuera, el vídeo nunca es su propia referencia
        for nombre, refs in (("dtw_propias", rp), ("dtw_comun", rc),
                             ("dtw_multi", refs_multi(cm, excluir=k))):
            punts[nombre][k], t = puntuar(v, refs)
            lat[nombre] += t

    # actividad: cómo se reparte en cada clase (para fijar act_min)
    act_stats = {c: [round(float(np.percentile(np.concatenate([acts[k] for k, v in videos.items()
                                                                 if v.clase == c]), q)), 3)
                     for q in (10, 50, 90)]
                 for c in (*CLASES, "otro")}

    # distribución de costes del elegido cuando es correcto / incorrecto
    dist = {}
    for nombre in punts:
        bien, mal = [], []
        for k, v in videos.items():
            ini = int(CALENTAMIENTO_S * FPS)
            for c in CLASES:
                s = punts[nombre][k][c][ini:]
                s = s[np.isfinite(s)]
                (bien if c == v.clase else mal).append(s)
        b, m_ = np.concatenate(bien), np.concatenate(mal)
        dist[nombre] = {"elegida_correcta_p50_p95_p99": [round(float(np.percentile(b, q)), 3) for q in (50, 95, 99)],
                        "elegida_incorrecta_p5_p50": [round(float(np.percentile(m_, q)), 3) for q in (5, 50)]}

    configs = [("segmentadores", None, None, False, None, False)]
    for nombre in ("dtw_propias", "dtw_comun", "dtw_multi"):
        for tau_no in (0.5, 0.75, 1.0, 1.5, 2.0):
            for tau_si in (0.75, 1.0, 1.5):
                for ratio in (0.5, 0.7):
                    for con_seg in (False, True):
                        configs.append((nombre, tau_no, tau_si, con_seg, ratio, False))
                    if nombre == "dtw_multi":
                        configs.append((nombre, tau_no, tau_si, False, ratio, True))

    # «propios» = solo los vídeos de registro.csv: datos que no se usaron para ajustar
    subconjuntos = ("todos", "sin_referencias") + (
        ("propios",) if any(k.startswith("propio_") for k in videos) else ())
    tabla = []
    for metodo, tau_no, tau_si, con_seg, ratio, relativo in configs:
        for subconjunto in subconjuntos:
            casos = []
            for k, v in videos.items():
                if subconjunto == "sin_referencias" and v.es_ref:
                    continue
                if subconjunto == "propios" and not k.startswith("propio_"):
                    continue
                for elegida in CLASES:
                    av = decidir(elegida, len(v), punts.get(metodo, {}).get(k), comps[k], acts[k],
                                 metodo, tau_no or 0, tau_si or 0, a.act_min, con_seg,
                                 ratio or 0.7, relativo)
                    casos.append({"video": k, "real": v.clase, "elegida": elegida,
                                  "es_ref": v.es_ref, "avisos": av})
            fila = {"metodo": metodo + ("+seg" if con_seg else "") + ("+rel" if relativo else ""),
                    "tau_no": tau_no,
                    "tau_si": tau_si, "ratio": ratio, "subconjunto": subconjunto,
                    **evaluar(casos)}
            if metodo == "segmentadores" or subconjunto != "todos":
                fila["casos"] = casos
            tabla.append(fila)

    lat_res = {k: {"p50": round(float(np.percentile(x, 50)), 4),
                   "p95": round(float(np.percentile(x, 95)), 4),
                   "max": round(float(np.max(x)), 4)} for k, x in lat.items()}
    conf = {n: confusion(videos.values(), punts[n], acts, a.act_min) for n in punts}
    salida = {"entorno": {"fecha": datetime.now().isoformat(timespec="seconds"),
                          "maquina": platform.platform(), "procesador": platform.processor(),
                          "python": platform.python_version(), "numpy": np.__version__},
              "parametros": {"fps": FPS, "ventana_s": VENTANA_S, "sostenido_s": SOSTENIDO_S,
                             "calentamiento_s": CALENTAMIENTO_S, "act_min": a.act_min,
                             "comun": COMUN},
              "videos": {k: {"clase": v.clase, "lado": v.lado, "es_ref": v.es_ref,
                             "frames": len(v), "presente": round(float(v.presente.mean()), 3)}
                         for k, v in videos.items()},
              "referencias_comunes": info_comun, "referencias_multi": info_multi, "actividad_p10_p50_p90": act_stats,
              "distribucion_costes": dist, "latencia_ms_por_frame": lat_res,
              "confusion_frames": conf, "tabla": tabla}
    RESULTADOS.mkdir(exist_ok=True)
    base = RESULTADOS / f"{datetime.now():%Y%m%d-%H%M%S}-exp010"
    base.with_suffix(".json").write_text(json.dumps(salida, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    print(json.dumps({k: salida[k] for k in ("actividad_p10_p50_p90", "distribucion_costes",
                                             "latencia_ms_por_frame", "confusion_frames")},
                     ensure_ascii=False, indent=1))
    cols = ("metodo", "tau_no", "tau_si", "ratio", "subconjunto", "falsa_alarma",
            "falsa_alarma_otro_ejercicio", "deteccion", "etiqueta_correcta", "deteccion_otro",
            "otro_confundido_con_ejercicio", "t_primer_aviso_s_mediana")
    lineas = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lineas += ["| " + " | ".join(str(f.get(c)) for c in cols) + " |" for f in tabla]
    base.with_suffix(".md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"\n{base}.json / .md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
