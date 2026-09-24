import cv2
import numpy as np

from pathlib import Path
import mediapipe as mp


# ============================================================
# CONFIGURACIÓN
# ============================================================

RUTA_VIDEOS = Path(
    r"C:\Users\USUARIO\Downloads\PRU\videos"
)

RUTA_SALIDA = Path(
    r"C:\Users\USUARIO\Downloads\ESTELA_DATASET\dataset_mediapipe"
)


EJERCICIOS = [
    "elevacion_brazos",
    "jumping_jack",
    "marcha_rodillas",
    "sentadilla"
]


# ============================================================
# CREAR CARPETA DE SALIDA
# ============================================================

RUTA_SALIDA.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# MEDIA PIPE
# ============================================================

mp_pose = mp.solutions.pose


# ============================================================
# PROCESAR VIDEOS
# ============================================================

with mp_pose.Pose(

    static_image_mode=False,

    model_complexity=1,

    smooth_landmarks=True,

    enable_segmentation=False,

    min_detection_confidence=0.5,

    min_tracking_confidence=0.5

) as pose:

    # --------------------------------------------------------
    # RECORRER EJERCICIOS
    # --------------------------------------------------------

    for ejercicio in EJERCICIOS:

        carpeta_videos = (
            RUTA_VIDEOS / ejercicio
        )

        carpeta_salida = (
            RUTA_SALIDA / ejercicio
        )

        carpeta_salida.mkdir(
            parents=True,
            exist_ok=True
        )


        if not carpeta_videos.exists():

            print(
                f"\n⚠️ No existe: "
                f"{carpeta_videos}"
            )

            continue


        # ----------------------------------------------------
        # BUSCAR VIDEOS
        # ----------------------------------------------------

        extensiones = [
            "*.mp4",
            "*.avi",
            "*.mov",
            "*.mkv"
        ]

        videos = []

        for extension in extensiones:

            videos.extend(
                carpeta_videos.glob(
                    extension
                )
            )


        print("\n" + "=" * 70)
        print(
            f"EJERCICIO: {ejercicio}"
        )
        print(
            f"Videos encontrados: "
            f"{len(videos)}"
        )
        print("=" * 70)


        # ----------------------------------------------------
        # PROCESAR CADA VIDEO
        # ----------------------------------------------------

        for video_path in videos:

            print("\n" + "-" * 70)

            print(
                f"Procesando: "
                f"{video_path.name}"
            )


            cap = cv2.VideoCapture(
                str(video_path)
            )


            if not cap.isOpened():

                print(
                    "❌ No se pudo abrir "
                    "el video"
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


            # ------------------------------------------------
            # SECUENCIA
            # ------------------------------------------------

            secuencia = []

            frame_idx = 0

            frames_detectados = 0

            frames_no_detectados = 0


            # ------------------------------------------------
            # LEER FRAMES
            # ------------------------------------------------

            while True:

                success, frame = cap.read()


                if not success:

                    break


                frame_idx += 1


                # --------------------------------------------
                # BGR → RGB
                # --------------------------------------------

                frame_rgb = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2RGB
                )


                # --------------------------------------------
                # MEDIA PIPE
                # --------------------------------------------

                resultado = pose.process(
                    frame_rgb
                )


                # --------------------------------------------
                # SI DETECTÓ CUERPO
                # --------------------------------------------

                if (
                    resultado.pose_landmarks
                    is not None
                ):

                    frames_detectados += 1


                    landmarks = (
                        resultado.pose_landmarks
                        .landmark
                    )


                    # ----------------------------------------
                    # 33 LANDMARKS
                    #
                    # Cada uno:
                    #
                    # x
                    # y
                    # z
                    # visibility
                    # ----------------------------------------

                    frame_landmarks = []


                    for landmark in landmarks:

                        frame_landmarks.append([
                            landmark.x,
                            landmark.y,
                            landmark.z,
                            landmark.visibility
                        ])


                    frame_landmarks = np.array(
                        frame_landmarks,
                        dtype=np.float32
                    )


                # --------------------------------------------
                # NO DETECTÓ PERSONA
                # --------------------------------------------

                else:

                    frames_no_detectados += 1


                    frame_landmarks = np.full(
                        (33, 4),
                        np.nan,
                        dtype=np.float32
                    )


                # --------------------------------------------
                # GUARDAR FRAME
                # --------------------------------------------

                secuencia.append(
                    frame_landmarks
                )


                # --------------------------------------------
                # PROGRESO
                # --------------------------------------------

                print(
                    f"\rFrame "
                    f"{frame_idx}/{total_frames}",
                    end=""
                )


            cap.release()


            # =================================================
            # CONVERTIR A NUMPY
            # =================================================

            secuencia = np.array(
                secuencia,
                dtype=np.float32
            )


            # =================================================
            # ESTADÍSTICAS
            # =================================================

            porcentaje = (
                frames_detectados
                / total_frames
                * 100
            ) if total_frames > 0 else 0


            print("\n")


            print(
                f"Frames detectados: "
                f"{frames_detectados}"
            )

            print(
                f"Frames sin detección: "
                f"{frames_no_detectados}"
            )

            print(
                f"Detección: "
                f"{porcentaje:.2f}%"
            )


            print(
                f"Forma final: "
                f"{secuencia.shape}"
            )


            # =================================================
            # GUARDAR
            # =================================================

            nombre_salida = (
                carpeta_salida
                / f"{video_path.stem}.npy"
            )


            np.save(
                nombre_salida,
                secuencia
            )


            print(
                f"✅ Guardado:"
            )

            print(
                nombre_salida
            )


print("\n" + "=" * 70)

print(
    "✅ EXTRACCIÓN MEDIAPIPE TERMINADA"
)

print("=" * 70)

print(
    f"\nDataset guardado en:\n"
    f"{RUTA_SALIDA}"
)