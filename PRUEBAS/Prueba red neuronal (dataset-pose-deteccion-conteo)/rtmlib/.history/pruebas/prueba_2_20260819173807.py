import cv2
from rtmlib import PoseTracker, Body, draw_skeleton

device = 'cpu'
backend = 'onnxruntime'

openpose_skeleton = False

ruta_gif = r"C:\Users\USUARIO\Downloads\PRUEBAS PF\EJERCICIOS\push-up.gif"

# Abrir GIF
cap = cv2.VideoCapture(ruta_gif)

# Verificar que abrió correctamente
if not cap.isOpened():
    print("❌ No se pudo abrir el GIF")
    exit()

print("✅ GIF abierto correctamente")

# Ver información
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps = cap.get(cv2.CAP_PROP_FPS)

print("Frames:", total_frames)
print("FPS:", fps)

# Crear modelo
pose_tracker = PoseTracker(
    Body,
    det_frequency=10,
    to_openpose=openpose_skeleton,
    backend=backend,
    device=device
)

while True:

    success, frame = cap.read()

    if not success:
        print("⚠️ Fin del GIF")
        break

    print("Procesando frame...")

    # Obtener keypoints
    keypoints, scores = pose_tracker(frame)

    # Dibujar esqueleto
    img_show = frame.copy()

    img_show = draw_skeleton(
        img_show,
        keypoints,
        scores,
        openpose_skeleton=openpose_skeleton,
        kpt_thr=0.43
    )

    # Mostrar
    cv2.imshow("RTMPose - Push Up", img_show)

    # q para salir
    if cv2.waitKey(30) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()

print("Programa terminado")