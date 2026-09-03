import cv2
import mediapipe as mp
import time

BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

options = PoseLandmarkerOptions(
    base_options=BaseOptions(model_asset_path="pose_landmarker.task"),
    running_mode=VisionRunningMode.VIDEO,
    num_poses=1,
)

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("No se pudo abrir la camara.")
        return

    print("Presiona 'q' (con la ventana enfocada) para salir.")
    with PoseLandmarker.create_from_options(options) as landmarker:
        inicio = time.time()
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            timestamp_ms = int((time.time() - inicio) * 1000)

            resultado = landmarker.detect_for_video(mp_image, timestamp_ms)

            if resultado.pose_landmarks:
                for pose in resultado.pose_landmarks:
                    for landmark in pose:
                        x = int(landmark.x * frame.shape[1])
                        y = int(landmark.y * frame.shape[0])
                        cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)

            cv2.imshow("MediaPipe Pose - Estela", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()
    print("Cerrado correctamente.")

if __name__ == "__main__":
    main()
