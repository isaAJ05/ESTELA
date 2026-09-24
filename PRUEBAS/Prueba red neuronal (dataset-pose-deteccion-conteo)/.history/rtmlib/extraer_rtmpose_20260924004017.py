import cv2
import numpy as np

from pathlib import Path
from rtmlib import PoseTracker, Body


# ============================================================
# CONFIGURACIÓN
# ============================================================

RUTA_VIDEOS = Path(
    r"C:\Users\USUARIO\Downloads\Prueba2\DATASET"
)

RUTA_SALIDA = Path(
    r"C:\Users\USUARIO\Downloads\Prueba2\DATASET\dataset_rtmpose"
)


EJERCICIOS = [
    "elevacion_brazos",
    "jumping_jack",
    "marcha_rodillas",
    "sentadilla"
]


# RTMPose
DEVICE = "cpu"
BACKEND = "onnxruntime"

OPENPOSE_SKELETON = False


# ============================================================
# CREAR CARPETA DE SALIDA
# ============================================================

RUTA_SALIDA.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# CREAR MODELO RTMPOSE
# ============================================================

print("=" * 70)
print("INICIALIZANDO RTMPOSE")
print("=" * 70)

pose_tracker = PoseTracker(
    Body,
    det_frequency=10,
    to_openpose=OPENPOSE_SKELETON,
    backend=BACKEND,
    device=DEVICE
)

print("✅ RTMPose inicializado")


# ============================================================
# PROCESAR EJERCICIOS
# ============================================================

for ejercicio in EJERCICIOS:

    carpeta_videos = RUTA_VIDEOS / ejercicio

    carpeta_salida = RUTA_SALIDA / ejercicio

    carpeta_salida.mkdir(
        parents=True,
        exist_ok=True
    )


    print("\n")
    print("=" * 70)
    print(f"EJERCICIO: {ejercicio}")
    print("=" * 70)


    # --------------------------------------------------------
    # COMPROBAR CARPETA
    # --------------------------------------------------------

    if not carpeta_videos.exists():

        print(
            f"⚠️ No existe la carpeta:"
        )

        print(
            carpeta_videos
        )

        continue


    # --------------------------------------------------------
    # BUSCAR VIDEOS
    # --------------------------------------------------------

    extensiones = [
        "*.mp4",
        "*.avi",
        "*.mov",
        "*.mkv"
    ]

    videos = []

    for extension in extensiones:

        videos.extend(
            carpeta_videos.glob(extension)
        )


    videos = sorted(videos)


    print(
        f"Videos encontrados: {len(videos)}"
    )


    # --------------------------------------------------------
    # PROCESAR CADA VIDEO
    # --------------------------------------------------------

    for video_path in videos:

        print("\n")
        print("-" * 70)

        print(
            f"VIDEO: {video_path.name}"
        )

        print("-" * 70)


        # ----------------------------------------------------
        # ABRIR VIDEO
        # ----------------------------------------------------

        cap = cv2.VideoCapture(
            str(video_path)
        )


        if not cap.isOpened():

            print(
                "❌ No se pudo abrir el video"
            )

            continue


        total_frames = int(
            cap.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
        )

        fps = cap.get(
            cv2.CAP_PROP_FPS
        )


        print(
            f"Frames: {total_frames}"
        )

        print(
            f"FPS: {fps:.2f}"
        )


        # ----------------------------------------------------
        # VARIABLES
        # ----------------------------------------------------

        secuencia = []

        frame_idx = 0

        frames_detectados = 0

        frames_sin_deteccion = 0


        # ----------------------------------------------------
        # PROCESAR FRAMES
        # ----------------------------------------------------

        while True:

            success, frame = cap.read()


            if not success:

                break


            frame_idx += 1


            # =================================================
            # RTMPOSE
            # =================================================

            keypoints, scores = pose_tracker(
                frame
            )


            # =================================================
            # SELECCIONAR PERSONA
            # =================================================

            if (
                keypoints is not None
                and len(keypoints) > 0
            ):

                frames_detectados += 1


                # ------------------------------------------------
                # Si hay varias personas, usamos la primera.
                #
                # Para ESTELA queremos trabajar con una persona.
                # ------------------------------------------------

                persona = keypoints[0]

                persona_scores = scores[0]


                # ------------------------------------------------
                # RTMPose entrega normalmente:
                #
                # persona:
                # (17, 2)
                #
                # scores:
                # (17,)
                # ------------------------------------------------

                frame_keypoints = np.column_stack(
                    (
                        persona[:, 0],
                        persona[:, 1],
                        persona_scores
                    )
                )


                frame_keypoints = np.asarray(
                    frame_keypoints,
                    dtype=np.float32
                )


            else:

                frames_sin_deteccion += 1


                # ------------------------------------------------
                # No se detectó persona
                #
                # Guardamos NaN para conservar la posición
                # temporal del frame.
                # ------------------------------------------------

                frame_keypoints = np.full(
                    (17, 3),
                    np.nan,
                    dtype=np.float32
                )


            # =================================================
            # GUARDAR FRAME
            # =================================================

            secuencia.append(
                frame_keypoints
            )


            # =================================================
            # MOSTRAR PROGRESO
            # =================================================

            print(
                f"\rProcesando frame "
                f"{frame_idx}/{total_frames}",
                end=""
            )


        # =====================================================
        # CERRAR VIDEO
        # =====================================================

        cap.release()


        # =====================================================
        # CONVERTIR A NUMPY
        # =====================================================

        secuencia = np.array(
            secuencia,
            dtype=np.float32
        )


        # =====================================================
        # ESTADÍSTICAS
        # =====================================================

        if total_frames > 0:

            porcentaje_deteccion = (
                frames_detectados
                / total_frames
                * 100
            )

        else:

            porcentaje_deteccion = 0


        print("\n")


        print(
            f"Frames procesados: "
            f"{frame_idx}"
        )

        print(
            f"Frames con detección: "
            f"{frames_detectados}"
        )

        print(
            f"Frames sin detección: "
            f"{frames_sin_deteccion}"
        )

        print(
            f"Porcentaje de detección: "
            f"{porcentaje_deteccion:.2f}%"
        )


        print(
            f"Forma del archivo: "
            f"{secuencia.shape}"
        )


        # =====================================================
        # GUARDAR NPY
        # =====================================================

        nombre_salida = (
            carpeta_salida
            / f"{video_path.stem}.npy"
        )


        np.save(
            nombre_salida,
            secuencia
        )


        print(
            "✅ Guardado:"
        )

        print(
            nombre_salida
        )


# ============================================================
# FINAL
# ============================================================

print("\n")
print("=" * 70)

print(
    "✅ EXTRACCIÓN RTMPOSE TERMINADA"
)

print("=" * 70)

print(
    "\nDataset guardado en:"
)

print(
    RUTA_SALIDA
)