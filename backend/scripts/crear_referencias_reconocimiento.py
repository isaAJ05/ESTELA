"""Construye `referencias/reconocimiento.json`, las referencias con que la
sesión reconoce si se está haciendo el ejercicio elegido (EXP-010,
`dtw_multi`; ver `estela/aplicacion/reconocimiento.py`).

Uso (desde `backend/`):

    python scripts/crear_referencias_reconocimiento.py --videos ../../docs_estela/investigacion/fuentes/datasets/videos ../../grabaciones/zancada/recortados

Si falta algún vídeo de `VIDEOS` en esas carpetas, termina con error sin escribir.

Una referencia por cada vídeo correcto de `docs_estela/.../datasets/videos/`
de `VIDEOS`, en el vector común de medidas; la clase de cada una es el
`clase_reconocimiento` de su skill. Cada
vídeo pasa por el pipeline de la sesión (pose → `observacion_desde_pose` →
`_SaltoCadera`), se remuestrea a 30 fps y se corta con el segmentador de su
skill; la referencia es la media alineada al medoide de sus repeticiones
completas, como en `crear_referencia.py`. La plancha guarda su postura media.

Solo se guardan medidas derivadas, nunca frames. No se usan vídeos de
técnica incorrecta ni de movimientos «otro».
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crear_referencia import estadistica_alineada, medoide  # noqa: E402

from estela import config  # noqa: E402
from estela.aplicacion.reconocimiento import (ESCALA_MIN,  # noqa: E402
                                              ESCALA_MIN_ANGULO, MEDIDAS,
                                              ruta_por_defecto, vector_comun)
from estela.aplicacion.rutina import cargar_catalogo  # noqa: E402
from estela.dominio.conteo.segmentador import EVENTO_COMPLETA  # noqa: E402

FPS = 30.0
MIN_REPETICIONES = 2
DOCS = Path(__file__).resolve().parents[3] / "docs_estela" / "investigacion" / "fuentes" / "datasets" / "videos"

#: (nombre del archivo, skills con que se corta). Los mismos de EXP-010 §9:
#: con varios skills (abducción sin lado conocido) se queda el que cuenta más.
VIDEOS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("1 hombre.mp4", ("jumping_jacks",)),
    ("2 mujer.mp4", ("jumping_jacks",)),
    ("7 hombre.mp4", ("jumping_jacks",)),
    ("Abducción activa de cadera en bipedestación.mp4",
     ("abduccion_cadera_izq", "abduccion_cadera_der")),
    ("Abducción de cadera de pie con apoyo_ El ejercicio tras un ataque o derrame cerebral.mp4",
     ("abduccion_cadera_izq", "abduccion_cadera_der")),
    ("der 876. Abducción de cadera con apoyo en silla.mp4", ("abduccion_cadera_der",)),
    ("der Abducción de cadera con banda_ técnica paso a paso.mp4", ("abduccion_cadera_der",)),
    ("der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4",
     ("abduccion_cadera_der",)),
    ("izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4",
     ("abduccion_cadera_izq",)),
    ("izquierda abductor.mp4", ("abduccion_cadera_izq",)),
    ("der Zancada atrás con Kettlebell Derecha - Ejercicios de la App Malagaentrena.mp4",
     ("zancada_atras_der",)),
    ("izq Zancada hacia atrás con peso corporal_ técnica paso a paso.mp4", ("zancada_atras_izq",)),
    # recortes de vídeos online (EXP-010 §12); sin lado conocido se queda el que cuenta más
    ("zancada_dinamica_alterna.mp4", ("zancada_atras_izq", "zancada_atras_der")),
    ("zancada_estatica_der_mujer.mp4", ("zancada_atras_der",)),
    ("zancada_estatica_mancuernas.mp4", ("zancada_atras_izq", "zancada_atras_der")),
    ("zancada_estatica_hombre.mp4", ("zancada_atras_izq", "zancada_atras_der")),
    ("PlanchaCorrecta1 (2).mp4", ("plancha",)),
    ("plancha correcta hombre.mp4", ("plancha",)),
    ("👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4", ("plancha",)),
)


def extraer(ruta: Path, modelo: str) -> List[Tuple[int, Any]]:
    """(t_ms, Observacion o None) de cada frame, remuestreado a `FPS`: en
    cada instante de la rejilla, el frame más reciente."""
    from estela.adaptadores.captura.fuente import FuenteVideo
    from estela.adaptadores.pose.estimador import EstimadorPose
    from estela.aplicacion.sesion import _SaltoCadera
    from estela.dominio.feedback.motor.geometria import observacion_desde_pose

    fuente, estimador = FuenteVideo(ruta), EstimadorPose(config.modelo_pose(modelo))
    salto, frames = _SaltoCadera(), []
    try:
        while (leido := fuente.leer()) is not None:
            frame, t_ms = leido
            res = estimador.estimar(frame, t_ms)
            obs = (None if res.muestra is None
                   else salto.aplicar(observacion_desde_pose(res.muestra, "reconocimiento"),
                                      res.imagen))
            frames.append((int(t_ms), obs))
    finally:
        fuente.cerrar()
        estimador.cerrar()
    if not frames:
        return []
    t = np.array([f[0] for f in frames])
    rejilla = np.arange(0, t[-1] + 1, 1000.0 / FPS)
    idx = np.clip(np.searchsorted(t, rejilla, side="right") - 1, 0, len(t) - 1)
    return [(int(round(r)), frames[i][1]) for r, i in zip(rejilla, idx)]


def cortar(frames: Sequence[Tuple[int, Any]], ej) -> Optional[Tuple[str, np.ndarray, Dict[str, Any]]]:
    """(tipo, media, info) con el segmentador del skill, o None si no da
    una referencia utilizable."""
    seg = ej.nuevo_segmentador()
    filas: List[np.ndarray] = []
    if (ej.segmentacion or {}).get("tipo") == "isometrico":
        for _, obs in frames:
            if obs is not None and seg.actualizar(obs).fase == ej.skill.fases[1]:
                filas.append(vector_comun(obs))
        if len(filas) < FPS:                       # menos de 1 s en posición
            return None
        with np.errstate(all="ignore"):
            media = np.nanmean(np.array(filas), axis=0, keepdims=True)
        return "isometrico", media, {"frames_en_posicion": len(filas)}
    grupos: Dict[int, List[np.ndarray]] = {}
    completas = set()
    for _, obs in frames:
        if obs is None:
            continue
        e = seg.actualizar(obs)
        if e.repeticion > 0:
            grupos.setdefault(e.repeticion, []).append(vector_comun(obs))
            if e.evento == EVENTO_COMPLETA:
                completas.add(e.repeticion)
    reps = [np.array(grupos[r]) for r in sorted(completas)]
    reps = [r for r in reps if np.isfinite(r).any(axis=1).sum() >= 5]
    if len(reps) < MIN_REPETICIONES:
        return None
    im, _ = medoide(reps)
    with np.errstate(all="ignore"):
        media, _, _ = estadistica_alineada(reps, im)
    return "ciclico", media, {"repeticiones": len(reps), "frames": len(media)}


def escala(medias: Sequence[np.ndarray]) -> np.ndarray:
    """σ de cada medida entre todas las referencias, con un mínimo."""
    with np.errstate(all="ignore"):
        s = np.nanstd(np.vstack(medias), axis=0)
    minimo = np.array([ESCALA_MIN.get(m, ESCALA_MIN_ANGULO) for m in MEDIDAS])
    return np.fmax(np.nan_to_num(s, nan=0.0), minimo)


def _lista(a: np.ndarray) -> List[List[Optional[float]]]:
    return [[None if not np.isfinite(v) else round(float(v), 3) for v in fila] for fila in a]


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--videos", type=Path, nargs="+", default=[DOCS],
                   help="carpetas donde se busca cada archivo de VIDEOS (defecto: docs_estela)")
    p.add_argument("--modelo", choices=("lite", "full", "heavy"), default="lite",
                   help="el de la sesión (defecto lite, como en EXP-010)")
    p.add_argument("--salida", type=Path, default=ruta_por_defecto())
    a = p.parse_args(argv)

    catalogo = cargar_catalogo()
    # sin todos los vídeos el JSON saldría con menos referencias y sin avisar
    ruta_de = {n: next((r for c in a.videos for r in c.rglob(n)), None) for n, _ in VIDEOS}
    if faltan := [n for n, r in ruta_de.items() if r is None]:
        print("Faltan vídeos (pasa sus carpetas con --videos); no se escribe nada:", *faltan, sep="\n  ")
        return 1
    referencias, fuentes = [], []
    for nombre, skills in VIDEOS:
        frames = extraer(ruta_de[nombre], a.modelo)
        mejor = None
        for sid in skills:
            r = cortar(frames, catalogo[sid])
            if r and (mejor is None or r[2].get("repeticiones", 0) > mejor[1][2].get("repeticiones", 0)):
                mejor = (sid, r)
        if mejor is None:
            print(f"descartado {nombre}: menos de {MIN_REPETICIONES} repeticiones completas")
            continue
        sid, (tipo, media, info) = mejor
        clase = catalogo[sid].skill.clase_reconocimiento
        referencias.append({"clase": clase, "tipo": tipo, "media": media})
        fuentes.append({"video": nombre, "clase": clase, "skill": sid, **info})
        print(f"{clase:16s} {sid:22s} {info}  {nombre}", flush=True)

    esc = escala([r["media"] for r in referencias])
    datos = {
        "version": "1",
        "origen": "EXP-010 §9–10 (dtw_multi); scripts/crear_referencias_reconocimiento.py",
        "fecha": date.today().isoformat(),
        "modelo_pose": a.modelo,
        "fps": FPS,
        "medidas": list(MEDIDAS),
        "escala": [round(float(s), 4) for s in esc],
        "fuentes": fuentes,
        "referencias": [{**r, "media": _lista(r["media"])} for r in referencias],
    }
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    a.salida.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(referencias)} referencias en {a.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
