import cv2
from rtmlib import PoseTracker, Body, draw_skeleton

# Configuración
device = 'cpu'
backend = 'onnxruntime'

openpose_skeleton = False

# Ruta de tu GIF
ruta_gif = r"C:\Users\USUARIO\Downloads\PRUEBAS PF\EJERCICIOS\push-up.gif"

# Abrir el GIF
cap = cv2.VideoCapture(ruta_gif)

# Crear el detector de pose
pose_tracker = PoseTracker(
    Body,
    det_frequency=10,
    to_openpose=openpose_skeleton,
    backend=backend,
    device=device
)

while cap.isOpened():

    success, frame = cap.read()

    # Si el GIF terminó, salir
    if not success:
        break

    # Obtener keypoints y scores
    keypoints, scores = pose_tracker(frame)

    # Copiar el frame
    img_show = frame.copy()

    # Dibujar el esqueleto
    img_show = draw_skeleton(
        img_show,
        keypoints,
        scores,
        kpt_thr=0.43,
        to_openpose=openpose_skeleton
    )

    # Cambiar tamaño para visualizar
    img_show = cv2.resize(img_show, (960, 540))

    # Mostrar resultado
    cv2.imshow("RTMPose - Push Up", img_show)

    # Presiona Q para salir
    if cv2.waitKey(10) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()