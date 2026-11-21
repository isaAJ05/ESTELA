import cv2
from rtmlib import PoseTracker, Body, draw_skeleton

# =========================
# CONFIGURACIÓN
# =========================

device = 'cpu'
backend = 'onnxruntime'

openpose_skeleton = False

# GIF de entrada
ruta_gif = r"C:\Users\USUARIO\Downloads\PRUEBAS PF\EJERCICIOS\multipersona\jumping-jacks.gif"

# Archivo de salida con los resultados
ruta_txt = r"C:\Users\USUARIO\Downloads\PRUEBAS PF\EJERCICIOS\multipersona\resultados_keypoints.txt"

# Video de salida
ruta_video = r"C:\Users\USUARIO\Downloads\PRUEBAS PF\EJERCICIOS\multipersona\resultado.mp4"


# =========================
# ABRIR GIF
# =========================

cap = cv2.VideoCapture(ruta_gif)

if not cap.isOpened():
    print("❌ No se pudo abrir el GIF")
    exit()

print("✅ GIF abierto correctamente")

total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps = cap.get(cv2.CAP_PROP_FPS)

print("Frames:", total_frames)
print("FPS:", fps)


# =========================
# CREAR MODELO
# =========================

pose_tracker = PoseTracker(
    Body,
    det_frequency=10,
    to_openpose=openpose_skeleton,
    backend=backend,
    device=device
)


# =========================
# CONFIGURAR VIDEO DE SALIDA
# =========================

ancho = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
alto = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

fourcc = cv2.VideoWriter_fourcc(*'mp4v')

out = cv2.VideoWriter(
    ruta_video,
    fourcc,
    fps,
    (ancho, alto)
)


# =========================
# PROCESAR FRAMES
# =========================

frame_idx = 0

with open(ruta_txt, "w", encoding="utf-8") as archivo:

    archivo.write("RESULTADOS RTMPOSE\n")
    archivo.write("=" * 50 + "\n\n")

    while cap.isOpened():

        success, frame = cap.read()

        if not success:
            print("⚠️ Fin del GIF")
            break

        frame_idx += 1

        print(f"\nProcesando frame {frame_idx}...")

        # =========================
        # OBTENER KEYPOINTS Y SCORES
        # =========================

        keypoints, scores = pose_tracker(frame)

        # =========================
        # GUARDAR RESULTADOS EN TXT
        # =========================

        archivo.write(f"FRAME {frame_idx}\n")
        archivo.write("-" * 30 + "\n")

        if len(keypoints) == 0:

            archivo.write("No se detectó ninguna persona.\n\n")

        else:

            for persona_idx, persona in enumerate(keypoints):

                archivo.write(
                    f"PERSONA {persona_idx + 1}\n"
                )

                for i, punto in enumerate(persona):

                    x = punto[0]
                    y = punto[1]

                    score = scores[persona_idx][i]

                    archivo.write(
                        f"Keypoint {i}: "
                        f"({x:.2f}, {y:.2f}) "
                        f"| Score: {score:.4f}\n"
                    )

                archivo.write("\n")

        archivo.write("\n")

        # =========================
        # DIBUJAR ESQUELETO
        # =========================

        img_show = frame.copy()

        img_show = draw_skeleton(
            img_show,
            keypoints,
            scores,
            openpose_skeleton=openpose_skeleton,
            kpt_thr=0.43
        )

        # =========================
        # GUARDAR FRAME EN VIDEO
        # =========================

        out.write(img_show)

        # =========================
        # MOSTRAR EN PANTALLA
        # =========================

        cv2.imshow(
            "RTMPose - Push Up",
            img_show
        )

        if cv2.waitKey(1000) & 0xFF == ord("q"):
            break


# =========================
# CERRAR TODO
# =========================

cap.release()
out.release()
cv2.destroyAllWindows()

print("\n✅ Programa terminado")
print("📄 Resultados TXT:", ruta_txt)
print("🎥 Video generado:", ruta_video)