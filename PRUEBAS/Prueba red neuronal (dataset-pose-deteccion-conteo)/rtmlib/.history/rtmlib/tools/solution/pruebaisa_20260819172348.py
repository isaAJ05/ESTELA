import cv2
from rtmlib import Body, PoseTracker

device = 'cpu'
backend = 'onnxruntime'

pose_tracker = PoseTracker(
    Body,
    mode='balanced',
    backend=backend,
    device=device
)

cap = cv2.VideoCapture(0)

while cap.isOpened():

    success, frame = cap.read()

    if not success:
        break

    # AQUÍ OBTENEMOS LOS DATOS IMPORTANTES
    keypoints, scores = pose_tracker(frame)

    print("KEYPOINTS:")
    print(keypoints)

    print("SCORES:")
    print(scores)

    cv2.imshow("Webcam", frame)

    # Presiona Q para salir
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()