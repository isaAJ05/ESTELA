"""EXP-004 — extracción: MediaPipe (+ contorno de la máscara) y SpinePose.

Procesa un vídeo o la cámara y guarda, por frame, solo datos derivados: los
puntos 2D de los dos modelos, las distancias del contorno dorsal y las
latencias. **Nunca guarda frames.** Con la cámara, la grabación de una
condición no deja vídeo en disco.

SpinePose recibe la caja de la persona a partir de los landmarks de MediaPipe
del mismo frame, en vez de ejecutar su propio detector: el detector RF-DETR
que trae tarda ~340 ms por frame en la CPU de desarrollo, y en ESTELA siempre
habrá una sola persona ya localizada por MediaPipe.

    # vídeo existente
    python PRUEBAS/exp004_puntos_tronco/extraer.py --video RUTA \\
        --sujeto ucf_g01 --condicion sentadilla_libre --vista perfil

    # cámara: cuenta atrás de 5 s y 10 s de registro de la condición
    python PRUEBAS/exp004_puntos_tronco/extraer.py --camara 0 --duracion 10 \\
        --sujeto S1 --condicion bisagra_neutra --vista perfil
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
sys.path.insert(0, str(AQUI))

import tronco as T  # noqa: E402

#: Pesos de SpinePose: "simspine" = v2 ('latest' en spinepose 2.1.0),
#: "spinetrack" = v1. Se usa la salida cruda del modelo: el suavizado que
#: spinepose aplica a v1 (media de vecinos) enderezaría la cadena que se mide.
VERSIONES_SPINEPOSE = {"v2": "simspine", "v1": "spinetrack"}


def crear_mediapipe(ruta_modelo: Path, mascara: bool):
    from mediapipe.tasks.python import BaseOptions, vision
    opciones = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(ruta_modelo)),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        output_segmentation_masks=mascara,
    )
    return vision.PoseLandmarker.create_from_options(opciones)


def crear_spinepose(modo: str, version: str = "v2"):
    """Solo el modelo de pose (RTMPose-SpineTrack) de SpinePose, sin detector."""
    from spinepose.pose_estimator import SpinePoseEstimator
    from spinepose.tools.pose_estimation import RTMPose
    cfg = SpinePoseEstimator.MODE[modo]
    url = cfg["pose"] % VERSIONES_SPINEPOSE[version] if "%s" in cfg["pose"] else cfg["pose"]
    return RTMPose(url, model_input_size=cfg["pose_input_size"],
                   hardware_acceleration=False), url.rsplit("/", 1)[-1]


def caja_desde_landmarks(img_px: np.ndarray, w: int, h: int, margen: float = 0.05):
    x1, y1 = img_px[:, :2].min(axis=0)
    x2, y2 = img_px[:, :2].max(axis=0)
    mx, my = margen * (x2 - x1), margen * (y2 - y1)
    return [max(0.0, x1 - mx), max(0.0, y1 - my), min(w - 1.0, x2 + mx), min(h - 1.0, y2 + my)]


def dibujar(frame, img_px, sp_kp, texto, espejo=False):
    """Vista previa: tronco de MediaPipe en gris y columna de SpinePose en
    naranja. El espejo es solo de visualización, como en estela/ui."""
    vista = frame.copy()
    if img_px is not None:
        for a, b in ((11, 12), (23, 24), (11, 23), (12, 24)):
            cv2.line(vista, tuple(map(int, img_px[a, :2])), tuple(map(int, img_px[b, :2])),
                     (200, 200, 200), 2)
    if sp_kp is not None:
        cadena = [sp_kp[T.SP[n]] for n in T.CADENA_TRONCO]
        for a, b in zip(cadena[:-1], cadena[1:]):
            cv2.line(vista, tuple(map(int, a)), tuple(map(int, b)), (60, 140, 255), 3)
        for p in cadena:
            cv2.circle(vista, tuple(map(int, p)), 4, (0, 0, 255), -1)
    if espejo:
        vista = cv2.flip(vista, 1)
    cv2.putText(vista, texto, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    return vista


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    fuente = ap.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--video", type=Path)
    fuente.add_argument("--camara", type=int)
    ap.add_argument("--sujeto", required=True)
    ap.add_argument("--condicion", required=True)
    ap.add_argument("--vista", choices=("perfil", "frontal"), required=True)
    ap.add_argument("--ropa", default="ajustada", help="ajustada | holgada")
    ap.add_argument("--duracion", type=float, default=10.0, help="s de registro (cámara)")
    ap.add_argument("--espera", type=float, default=5.0, help="s de cuenta atrás (cámara)")
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--modelo-mp", type=Path, default=RAIZ / "modelos" / "pose_landmarker_full.task")
    ap.add_argument("--spinepose", default="small",
                    choices=("small", "medium", "large", "ninguno"))
    ap.add_argument("--version-sp", choices=tuple(VERSIONES_SPINEPOSE), default="v2")
    ap.add_argument("--sin-mascara", action="store_true")
    ap.add_argument("--ventana", action="store_true", help="vista previa (siempre con cámara)")
    ap.add_argument("--salida", type=Path, default=AQUI / "resultados")
    args = ap.parse_args()

    mp_det = crear_mediapipe(args.modelo_mp, not args.sin_mascara)
    sp_mod, sp_nombre = ((None, None) if args.spinepose == "ninguno"
                         else crear_spinepose(args.spinepose, args.version_sp))

    import mediapipe as mp
    cap = cv2.VideoCapture(str(args.video) if args.video else args.camara)
    if not cap.isOpened():
        sys.exit(f"no se pudo abrir {args.video or args.camara}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    ventana = args.ventana or args.camara is not None

    filas = {k: [] for k in ("t_ms", "mp_img", "mp_mundo", "sp_kp", "sp_score",
                             "contorno", "lat_mp", "lat_contorno", "lat_sp")}
    t_inicio = time.monotonic()
    t_registro = t_inicio + (args.espera if args.camara is not None else 0.0)
    i, ultimo_t = 0, -1
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        ahora = time.monotonic()
        if args.camara is not None and ahora < t_registro:   # cuenta atrás, no se registra
            if ventana:
                cv2.imshow("EXP-004", dibujar(frame, None, None,
                           f"{args.condicion}: empieza en {t_registro - ahora:.0f} s", True))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            continue
        if args.camara is not None and ahora - t_registro > args.duracion:
            break
        h, w = frame.shape[:2]
        t_ms = int(i * 1000.0 / fps) if args.video else int((ahora - t_registro) * 1000)
        t_ms = max(t_ms, ultimo_t + 1)
        ultimo_t = t_ms

        imagen = mp.Image(image_format=mp.ImageFormat.SRGB,
                          data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        t0 = time.perf_counter()
        r = mp_det.detect_for_video(imagen, t_ms)
        lat_mp = (time.perf_counter() - t0) * 1000.0

        img_px = mundo = None
        contorno = np.full((len(T.FRACCIONES_CONTORNO), 2), np.nan)
        lat_cont = lat_sp = np.nan
        sp_kp = np.full((37, 2), np.nan)
        sp_sc = np.full(37, np.nan)
        if r.pose_landmarks:
            img_px = np.array([[p.x * w, p.y * h, p.z, p.visibility or 0.0]
                               for p in r.pose_landmarks[0]])
            mundo = np.array([[p.x, p.y, p.z, p.visibility or 0.0]
                              for p in r.pose_world_landmarks[0]])
            if r.segmentation_masks:
                t0 = time.perf_counter()
                cm = (img_px[T.MP["cadera_izq"], :2] + img_px[T.MP["cadera_der"], :2]) / 2
                hm = (img_px[T.MP["hombro_izq"], :2] + img_px[T.MP["hombro_der"], :2]) / 2
                contorno = T.distancias_contorno(r.segmentation_masks[0].numpy_view(), cm, hm)
                lat_cont = (time.perf_counter() - t0) * 1000.0
            if sp_mod is not None:
                t0 = time.perf_counter()
                k, s = sp_mod(frame, bboxes=[caja_desde_landmarks(img_px, w, h)])
                lat_sp = (time.perf_counter() - t0) * 1000.0
                sp_kp, sp_sc = k[0], s[0]

        filas["t_ms"].append(t_ms)
        filas["mp_img"].append(img_px if img_px is not None else np.full((33, 4), np.nan))
        filas["mp_mundo"].append(mundo if mundo is not None else np.full((33, 4), np.nan))
        filas["sp_kp"].append(sp_kp)
        filas["sp_score"].append(sp_sc)
        filas["contorno"].append(contorno)
        filas["lat_mp"].append(lat_mp)
        filas["lat_contorno"].append(lat_cont)
        filas["lat_sp"].append(lat_sp)
        i += 1

        if ventana:
            cv2.imshow("EXP-004", dibujar(frame, img_px, sp_kp if img_px is not None else None,
                                          f"{args.condicion}  {lat_mp:.0f}+{lat_sp:.0f} ms",
                                          args.camara is not None))
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        if args.max_frames and i >= args.max_frames:
            break

    cap.release()
    mp_det.close()
    if ventana:
        cv2.destroyAllWindows()
    if i == 0:
        sys.exit("no se procesó ningún frame")

    meta = {
        "sujeto": args.sujeto, "condicion": args.condicion, "vista": args.vista,
        "ropa": args.ropa, "fuente": str(args.video) if args.video else f"camara:{args.camara}",
        "fps": fps, "ancho": int(w), "alto": int(h), "frames": i,
        "modelo_mp": args.modelo_mp.name, "mascara": not args.sin_mascara,
        "modelo_sp": sp_nombre, "fecha": time.strftime("%Y-%m-%d %H:%M"),
    }
    args.salida.mkdir(parents=True, exist_ok=True)
    base = f"{args.sujeto}_{args.condicion}_{args.vista}"
    n = 1
    while (args.salida / f"{base}_{n:02d}.npz").exists():
        n += 1
    ruta = args.salida / f"{base}_{n:02d}.npz"
    np.savez_compressed(ruta, meta=json.dumps(meta),
                        **{k: np.asarray(v, dtype=np.float32 if k != "t_ms" else np.int64)
                           for k, v in filas.items()})
    lat = np.asarray(filas["lat_mp"][10:] or filas["lat_mp"])
    print(f"{ruta.relative_to(RAIZ) if ruta.is_relative_to(RAIZ) else ruta}: {i} frames, "
          f"MediaPipe p50 {np.percentile(lat, 50):.1f} ms")


if __name__ == "__main__":
    main()
