"""EXP-010 · Paso 1: una pasada de pose por vídeo, guardada en caché.

Desde ESTELA/, con el entorno de backend/:

    python PRUEBAS/exp010_reconocimiento/extraer.py [--modelo lite]

Pasa cada vídeo del banco (`BANCO`, solo `docs_estela/.../datasets/videos/`) por el mismo pipeline de la sesión
(Pose Landmarker → `observacion_desde_pose` → `_SaltoCadera`) y guarda en
`cache/<id>.npz` todas las medidas por frame con su confianza. Solo medidas
derivadas, nunca frames. `cache/` está ignorado por git.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List, Tuple

import numpy as np

AQUI = Path(__file__).resolve().parent
ESTELA = AQUI.parents[1]
BACKEND = ESTELA / "backend"
sys.path.insert(0, str(BACKEND))

CACHE = AQUI / "cache"
#: solo los vídeos del proyecto (docs_estela), no los de PRUEBAS/DATASET
DOCS = ESTELA.parent / "docs_estela" / "investigacion" / "fuentes" / "datasets" / "videos"

# (id, ruta, clase real, lado, ¿fuente de una referencia del catálogo?)
# clase "otro" = movimiento que no es ninguno de los cuatro ejercicios.
_AB = DOCS / "Abdución de caderas pies"
_JJ = DOCS / "Jumping Jacks"
_MA = DOCS / "Marcha rodillas"
BANCO: List[Tuple[str, Path, str, str, bool]] = (
    [("jj_1_hombre", _JJ / "1 hombre.mp4", "jumping_jacks", "", False),
     ("jj_2_mujer", _JJ / "2 mujer.mp4", "jumping_jacks", "", False),
     ("jj_7_hombre", _JJ / "7 hombre.mp4", "jumping_jacks", "", True),
     ("marcha_5_hombre", _MA / "5 hombre.mp4", "marcha_rodillas", "", False),
     ("marcha_6_mujer", _MA / "6 mujer.mp4", "marcha_rodillas", "", False),
     ("marcha_high_knees", _MA / "How to do high knees for beginners (online-video-cutter.com).mp4",
      "marcha_rodillas", "", True)]
    + [
        ("abd_bipedestacion", _AB / "Abducción activa de cadera en bipedestación.mp4",
         "abduccion", "", False),
        ("abd_apoyo_ictus", _AB / "Abducción de cadera de pie con apoyo_ El ejercicio tras un ataque o derrame cerebral.mp4",
         "abduccion", "", False),
        ("abd_der_silla", _AB / "der 876. Abducción de cadera con apoyo en silla.mp4",
         "abduccion", "der", False),
        # vídeo completo del que se recortaron las dos referencias: solapa con ellas
        ("abd_der_banda_completo", _AB / "der Abducción de cadera con banda_ técnica paso a paso.mp4",
         "abduccion", "der", True),
        ("abd_der_ref", _AB / "der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4",
         "abduccion", "der", True),
        ("abd_izq_ref", _AB / "izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4",
         "abduccion", "izq", True),
        ("abd_izq_abductor", _AB / "izquierda abductor.mp4", "abduccion", "izq", False),
        ("otro_aduccion_maquina", _AB / "izq Aducción de cadera de pie con máquina.mp4",
         "otro", "", False),
    ]
    + [(f"plancha_{i}", p, "plancha", "", p.stem == "plancha correcta hombre")
       for i, p in enumerate(sorted((DOCS / "Plancha").glob("*.mp4")))]
    + [(f"otro_zancada_{i}", p, "otro", "", False)
       for i, p in enumerate(sorted((DOCS / "Zancada atrás estática por pierna").glob("*.mp4")))]
)

# vídeos propios anotados con registrar.py (registro.csv, ignorado por git)
from registrar import leer as _leer_registro  # noqa: E402

BANCO += [(f["id"], Path(f["ruta"]), f["clase"], f["lado"], False) for f in _leer_registro()]


def extraer(ruta: Path, modelo: str) -> dict:
    from estela import config
    from estela.adaptadores.captura.fuente import FuenteVideo
    from estela.adaptadores.pose.estimador import EstimadorPose
    from estela.aplicacion.sesion import _SaltoCadera
    from estela.dominio.feedback.motor.geometria import observacion_desde_pose

    fuente, estimador = FuenteVideo(ruta), EstimadorPose(config.modelo_pose(modelo))
    salto = _SaltoCadera()
    filas, t_ms_l, orient, pose_ms = [], [], [], []
    try:
        while (leido := fuente.leer()) is not None:
            frame, t_ms = leido
            res = estimador.estimar(frame, t_ms)
            pose_ms.append(res.latencia_ms)
            t_ms_l.append(t_ms)
            if res.muestra is None:
                filas.append(None)
                orient.append(np.nan)
                continue
            obs = salto.aplicar(observacion_desde_pose(res.muestra, "exp010"), res.imagen)
            filas.append(obs)
            orient.append(np.nan if obs.orientacion is None else obs.orientacion)
    finally:
        fuente.cerrar()
        estimador.cerrar()

    nombres = sorted({n for o in filas if o for n in (*o.angulos, *o.distancias)})
    k = {n: i for i, n in enumerate(nombres)}
    valores = np.full((len(filas), len(nombres)), np.nan, dtype=np.float32)
    confianza = np.zeros_like(valores)
    for i, o in enumerate(filas):
        if o is None:
            continue
        for n, v in (*o.angulos.items(), *o.distancias.items()):
            valores[i, k[n]] = v
            confianza[i, k[n]] = o.confianza_de(n)
    distancias = {n for o in filas if o for n in o.distancias}
    return {"nombres": np.array(nombres), "valores": valores, "confianza": confianza,
            "es_distancia": np.array([n in distancias for n in nombres]),
            "t_ms": np.array(t_ms_l, dtype=np.int64),
            "presente": np.array([o is not None for o in filas]),
            "orientacion": np.array(orient, dtype=np.float32),
            "pose_ms": np.array(pose_ms, dtype=np.float32),
            "fps": np.float32(fuente.fps or 30.0), "modelo": modelo}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--modelo", default="lite", choices=("lite", "full", "heavy"))
    p.add_argument("--rehacer", action="store_true")
    a = p.parse_args()
    CACHE.mkdir(exist_ok=True)
    for vid, ruta, clase, lado, es_ref in BANCO:
        destino = CACHE / f"{vid}.npz"
        if destino.exists() and not a.rehacer:
            continue
        if not ruta.exists():
            print(f"FALTA {ruta}")
            continue
        t0 = time.time()
        datos = extraer(ruta, a.modelo)
        np.savez_compressed(destino, clase=clase, lado=lado, es_ref=es_ref,
                            video=str(ruta.name), **datos)
        print(f"{vid:32s} {clase:16s} {len(datos['t_ms']):5d} frames  "
              f"presente {datos['presente'].mean():.0%}  {time.time() - t0:5.1f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
