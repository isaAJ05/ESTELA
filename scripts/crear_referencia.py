"""Construye una referencia offline a partir de un vídeo de ejercicio.

Uso:
    python scripts/crear_referencia.py --selftest
    python scripts/crear_referencia.py --ejercicio jumping_jacks \
        --video ruta.mp4 --salida feedback/skills/referencias/jumping_jacks/referencia.json

El vídeo usa exactamente el pipeline de sesión: MediaPipe Pose Landmarker,
``observacion_desde_pose`` y el segmentador configurado en el skill. Las
medidas con confianza insuficiente se guardan como ``null`` y no se imputan.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from estela.config import modelo_pose
from estela.conteo.segmentador import (
    EVENTO_COMPLETA,
    SegmentadorIsometrico,
)
from estela.pose.estimador import EstimadorPose
from estela.sesion.rutina import cargar_catalogo
from feedback.motor.geometria import observacion_desde_pose


ESQUEMA_VERSION = "0.1"
CONFIANZA_MINIMA = 0.5
MEDIDAS_POR_EJERCICIO: Dict[str, Tuple[str, ...]] = {
    "jumping_jacks": ("hombro_medio", "codo_medio", "separacion_pies"),
    "abduccion_cadera_izq": (
        "abduccion_cadera_izq", "inclinacion_lateral_tronco",
        "inclinacion_pelvis",
    ),
    "abduccion_cadera_der": (
        "abduccion_cadera_der", "inclinacion_lateral_tronco",
        "inclinacion_pelvis",
    ),
    "marcha_rodillas": (
        "cadera_izq", "cadera_der", "tronco_inclinacion",
    ),
    "zancada_atras_izq": (
        "rodilla_izq", "rodilla_der", "tronco_inclinacion",
    ),
    "zancada_atras_der": (
        "rodilla_izq", "rodilla_der", "tronco_inclinacion",
    ),
    "plancha": (
        "tronco_inclinacion", "cabeza_adelantada", "alineacion_cadera",
    ),
}


def dtw(a: np.ndarray, b: np.ndarray,
        banda: Optional[int] = None) -> Tuple[float, List[Tuple[int, int]]]:
    """Devuelve el coste medio y camino DTW, ignorando valores NaN."""
    n, m = len(a), len(b)
    if not n or not m or a.shape[1] != b.shape[1]:
        raise ValueError("las series DTW deben ser no vacías y tener igual dimensión")
    diff = np.abs(a[:, None, :] - b[None, :, :])
    valid = ~np.isnan(diff)
    count = valid.sum(axis=-1)
    coste = np.divide(
        np.nansum(diff, axis=-1), count,
        out=np.zeros((n, m), dtype=float), where=count > 0,
    )
    coste[count == 0] = np.nan
    acumulado = np.full((n + 1, m + 1), np.inf)
    acumulado[0, 0] = 0.0
    for i in range(1, n + 1):
        lo, hi = 1, m
        if banda is not None:
            centro = i * m / n
            lo = max(1, int(centro - banda))
            hi = min(m, int(centro + banda))
        for j in range(lo, hi + 1):
            if np.isnan(coste[i - 1, j - 1]):
                continue
            acumulado[i, j] = coste[i - 1, j - 1] + min(
                acumulado[i - 1, j], acumulado[i, j - 1],
                acumulado[i - 1, j - 1],
            )
    if not np.isfinite(acumulado[n, m]):
        raise ValueError("DTW no encontró un camino con medidas observables")
    i, j, camino = n, m, []
    while i > 0 and j > 0:
        camino.append((i - 1, j - 1))
        k = int(np.argmin((
            acumulado[i - 1, j - 1], acumulado[i - 1, j],
            acumulado[i, j - 1],
        )))
        i, j = ((i - 1, j - 1), (i - 1, j), (i, j - 1))[k]
    camino.reverse()
    return float(acumulado[n, m] / len(camino)), camino


def medoide(reps: Sequence[np.ndarray],
            banda: Optional[int] = None) -> Tuple[int, np.ndarray]:
    if not reps:
        raise ValueError("se necesita al menos una repetición")
    distancias = np.zeros((len(reps), len(reps)))
    for i in range(len(reps)):
        for j in range(i + 1, len(reps)):
            distancias[i, j] = distancias[j, i] = dtw(
                reps[i], reps[j], banda)[0]
    return int(np.argmin(distancias.sum(axis=1))), distancias


def estadistica_alineada(
    reps: Sequence[np.ndarray], indice_medoide: int,
    banda: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    med = reps[indice_medoide]
    apiladas = np.full((len(reps), len(med), med.shape[1]), np.nan)
    for r, rep in enumerate(reps):
        _, camino = dtw(med, rep, banda)
        for t in range(len(med)):
            valores = [rep[j] for i, j in camino if i == t]
            if valores:
                apiladas[r, t] = np.nanmean(valores, axis=0)
    n = np.sum(~np.isnan(apiladas), axis=0)
    with np.errstate(all="ignore"):
        media = np.nanmean(apiladas, axis=0)
        sigma = np.where(n >= 2, np.nanstd(apiladas, axis=0, ddof=1), np.nan)
    return media, sigma, n


def tramos_de_fase(fases: Sequence[str]) -> List[Dict[str, Any]]:
    if not fases:
        return []
    tramos: List[Dict[str, Any]] = []
    inicio = 0
    for i in range(1, len(fases) + 1):
        if i == len(fases) or fases[i] != fases[inicio]:
            tramos.append({"fase": fases[inicio], "inicio": inicio, "fin": i - 1})
            inicio = i
    return tramos


def _lista(a: np.ndarray) -> List[List[Optional[float]]]:
    return [
        [None if np.isnan(v) else round(float(v), 3) for v in fila]
        for fila in a
    ]


def construir_ciclico(
    ejercicio_id: str, medidas: Sequence[str], reps: Sequence[Dict[str, Any]],
    meta: Dict[str, Any], banda: Optional[int] = None,
) -> Dict[str, Any]:
    series = [r["angulos"] for r in reps]
    indice, distancias = medoide(series, banda)
    media, sigma, n = estadistica_alineada(series, indice, banda)
    med = reps[indice]
    return {
        "esquema_version": ESQUEMA_VERSION,
        "ejercicio_id": ejercicio_id,
        "tipo": "ciclico",
        "fuente": meta,
        "medidas": list(medidas),
        "n_repeticiones": len(reps),
        "indice_medoide": indice,
        "n_frames": int(len(media)),
        "fps": meta["fps"],
        "angulos": {"media": _lista(media), "sigma": _lista(sigma),
                    "n": n.astype(int).tolist()},
        "fases": tramos_de_fase(med["fases"]),
        "keypoints_2d": med["keypoints"],
        "dtw": {
            "banda": banda,
            "coste_medoide_a_resto": round(
                float(distancias[indice].sum() / max(len(reps) - 1, 1)), 4),
        },
    }


def construir_isometrico(
    ejercicio_id: str, medidas: Sequence[str], frames: np.ndarray,
    keypoints: np.ndarray, meta: Dict[str, Any],
) -> Dict[str, Any]:
    n = np.sum(~np.isnan(frames), axis=0)
    with np.errstate(all="ignore"):
        media = np.nanmean(frames, axis=0)
        sigma = np.where(n >= 2, np.nanstd(frames, axis=0, ddof=1), np.nan)
    return {
        "esquema_version": ESQUEMA_VERSION,
        "ejercicio_id": ejercicio_id,
        "tipo": "isometrico",
        "fuente": meta,
        "medidas": list(medidas),
        "n_frames": int(len(frames)),
        "fps": meta["fps"],
        "postura": {
            "media": [None if np.isnan(v) else round(float(v), 3) for v in media],
            "sigma": [None if np.isnan(v) else round(float(v), 3) for v in sigma],
            "n": n.astype(int).tolist(),
        },
        "keypoints_2d": [_lista(keypoints.mean(axis=0))],
    }


def grafico_control(referencia: Dict[str, Any], salida: Path) -> None:
    """Genera la curva media ± sigma para la revisión humana."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "generar el gráfico requiere matplotlib; instala la dependencia "
            "de desarrollo del proyecto"
        ) from exc
    nombres = referencia["medidas"]
    if referencia["tipo"] == "isometrico":
        media = np.asarray(referencia["postura"]["media"], float)
        sigma = np.asarray(referencia["postura"]["sigma"], float)
        fig, eje = plt.subplots(figsize=(8, 3))
        eje.errorbar(np.arange(len(nombres)), media, yerr=sigma, fmt="o",
                     capsize=4)
        eje.set_xticks(np.arange(len(nombres)), nombres, rotation=30,
                       ha="right")
        eje.set_ylabel("valor")
        eje.set_title(f"{referencia['ejercicio_id']} · postura media ± sigma")
        eje.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        fig.savefig(salida, dpi=120)
        plt.close(fig)
        return
    media = np.asarray(referencia["angulos"]["media"], float)
    sigma = np.asarray(referencia["angulos"]["sigma"], float)
    fig, ejes = plt.subplots(
        len(nombres), 1, figsize=(8, max(2.5, 2.2 * len(nombres))),
        squeeze=False,
    )
    for indice, nombre in enumerate(nombres):
        eje = ejes[indice, 0]
        t = np.arange(len(media))
        eje.plot(t, media[:, indice], label="media")
        eje.fill_between(
            t, media[:, indice] - sigma[:, indice],
            media[:, indice] + sigma[:, indice], alpha=0.25, label="±sigma",
        )
        eje.set_ylabel(nombre, fontsize=8)
        eje.grid(alpha=0.2)
    ejes[0, 0].set_title(
        f"{referencia['ejercicio_id']} · "
        f"{referencia['n_repeticiones']} reps · "
        f"medoide #{referencia['indice_medoide']}"
    )
    ejes[-1, 0].set_xlabel("frame de la repetición canónica")
    ejes[0, 0].legend()
    fig.tight_layout()
    fig.savefig(salida, dpi=120)
    plt.close(fig)


def _valor(obs: Any, nombre: str) -> float:
    valores = obs.angulos if nombre in obs.angulos else obs.distancias
    if nombre not in valores or obs.confianza_de(nombre) < CONFIANZA_MINIMA:
        return np.nan
    return float(valores[nombre])


def extraer_series(video: str, ejercicio_id: str) -> Tuple[
    List[str], Any, float
]:
    """Extrae medidas y repeticiones usando el pipeline de sesión."""
    if ejercicio_id not in MEDIDAS_POR_EJERCICIO:
        raise ValueError(f"ejercicio no soportado: {ejercicio_id}")
    catalogo = cargar_catalogo()
    ejercicio = catalogo[ejercicio_id]
    segmentador = ejercicio.nuevo_segmentador()
    fps: Optional[float] = None
    import cv2

    captura = cv2.VideoCapture(video)
    if not captura.isOpened():
        raise FileNotFoundError(f"no se pudo abrir el vídeo: {video}")
    fps = float(captura.get(cv2.CAP_PROP_FPS) or 30.0)
    estimador = EstimadorPose(modelo_pose("full"))
    medidas = list(MEDIDAS_POR_EJERCICIO[ejercicio_id])
    grupos: Dict[int, Dict[str, Any]] = {}
    completadas: set[int] = set()
    iso_valores: List[List[float]] = []
    iso_kps: List[np.ndarray] = []
    frame = 0
    try:
        while True:
            ok, imagen = captura.read()
            if not ok:
                break
            resultado = estimador.estimar(imagen, round(frame * 1000 / fps))
            frame += 1
            if resultado.muestra is None or resultado.imagen is None:
                continue
            obs = observacion_desde_pose(resultado.muestra, ejercicio_id)
            estado = segmentador.actualizar(obs)
            fila = [_valor(obs, nombre) for nombre in medidas]
            puntos = resultado.imagen[:, :2].astype(float).tolist()
            if isinstance(segmentador, SegmentadorIsometrico):
                if estado.fase == ejercicio.skill.fases[1]:
                    iso_valores.append(fila)
                    iso_kps.append(resultado.imagen[:, :2].astype(float))
            elif estado.repeticion > 0:
                grupo = grupos.setdefault(estado.repeticion, {
                    "angulos": [], "fases": [], "keypoints": [],
                })
                grupo["angulos"].append(fila)
                grupo["fases"].append(estado.fase)
                grupo["keypoints"].append(puntos)
                if estado.evento == EVENTO_COMPLETA:
                    completadas.add(estado.repeticion)
    finally:
        captura.release()
        estimador.cerrar()
    if isinstance(segmentador, SegmentadorIsometrico):
        if not iso_valores:
            raise ValueError("el vídeo no contiene frames en la postura de plancha")
        return medidas, {
            "frames": np.asarray(iso_valores, float),
            "keypoints": np.asarray(iso_kps, float),
        }, fps
    reps = [
        {
            "angulos": np.asarray(grupos[i]["angulos"], float),
            "fases": grupos[i]["fases"],
            "keypoints": grupos[i]["keypoints"],
        }
        for i in sorted(completadas) if grupos.get(i, {}).get("angulos")
    ]
    if not reps:
        raise ValueError("el vídeo no contiene repeticiones completas")
    return medidas, reps, fps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--ejercicio")
    parser.add_argument("--video")
    parser.add_argument("--salida")
    parser.add_argument("--banda", type=int, default=None)
    parser.add_argument("--licencia", default="")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return 0
    if not args.ejercicio or not args.video or not args.salida:
        parser.error("--ejercicio, --video y --salida son obligatorios")
    medidas, datos, fps = extraer_series(args.video, args.ejercicio)
    meta = {"video": Path(args.video).name, "fps": fps,
            "licencia": args.licencia}
    if isinstance(datos, dict):
        referencia = construir_isometrico(
            args.ejercicio, medidas, datos["frames"], datos["keypoints"], meta)
    else:
        referencia = construir_ciclico(
            args.ejercicio, medidas, datos, meta, args.banda)
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(referencia, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    grafico_control(referencia, salida.with_suffix(".png"))
    print(f"escrito {salida}")
    return 0


def _selftest() -> None:
    rng = np.random.default_rng(0)
    t = 16
    u = np.linspace(0, 1, t)
    base = np.stack([u, np.sin(np.pi * u)], axis=1)
    reps = [base.copy() for _ in range(4)]
    indice, _ = medoide(reps)
    media, sigma, _ = estadistica_alineada(reps, indice)
    assert len(media) == len(reps[indice])
    assert np.nanmax(sigma) < 1e-12
    coste, camino = dtw(reps[0], reps[0])
    assert coste == 0.0 and len(camino) == len(reps[0])
    print(f"OK - medoide {indice}, {len(media)} frames canónicos")


if __name__ == "__main__":
    sys.exit(main())
