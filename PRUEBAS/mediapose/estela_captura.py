import cv2
import mediapipe as mp
import numpy as np
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

HOMBRO_I, HOMBRO_D = 11, 12
CODO_I, CODO_D = 13, 14
MUNECA_I, MUNECA_D = 15, 16
CADERA_I, CADERA_D = 23, 24
RODILLA_I, RODILLA_D = 25, 26
TOBILLO_I, TOBILLO_D = 27, 28

DEFINICIONES_ANGULOS = {
    "codo_izq":     (HOMBRO_I, CODO_I, MUNECA_I),
    "codo_der":     (HOMBRO_D, CODO_D, MUNECA_D),
    "hombro_izq":   (CODO_I, HOMBRO_I, CADERA_I),
    "hombro_der":   (CODO_D, HOMBRO_D, CADERA_D),
    "cadera_izq":   (HOMBRO_I, CADERA_I, RODILLA_I),
    "cadera_der":   (HOMBRO_D, CADERA_D, RODILLA_D),
    "rodilla_izq":  (CADERA_I, RODILLA_I, TOBILLO_I),
    "rodilla_der":  (CADERA_D, RODILLA_D, TOBILLO_D),
}

UMBRAL_VISIBILIDAD = 0.6
NOMBRE_VENTANA = "MediaPipe Pose - Estela"


def calcular_angulo(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    ba = a - b
    bc = c - b
    coseno = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
    coseno = np.clip(coseno, -1.0, 1.0)
    return np.degrees(np.arccos(coseno))


def punto_confiable(landmark, umbral):
    return landmark.visibility >= umbral


def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("No se pudo abrir la camara.")
        return

    ancho = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    salida = cv2.VideoWriter("salida_con_puntos.mp4", fourcc, 20.0, (ancho, alto))

    historial = {nombre: [] for nombre in DEFINICIONES_ANGULOS}
    descartados = {nombre: 0 for nombre in DEFINICIONES_ANGULOS}

    print("Presiona 'q' o cierra la ventana con la X para salir.")
    cv2.namedWindow(NOMBRE_VENTANA, cv2.WINDOW_NORMAL)

    with PoseLandmarker.create_from_options(options) as landmarker:
        inicio = time.time()
        frame_num = 0

        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            timestamp_ms = int((time.time() - inicio) * 1000)

            resultado = landmarker.detect_for_video(mp_image, timestamp_ms)

            if resultado.pose_landmarks and resultado.pose_world_landmarks:
                puntos_dibujo = resultado.pose_landmarks[0]
                for landmark in puntos_dibujo:
                    x = int(landmark.x * frame.shape[1])
                    y = int(landmark.y * frame.shape[0])
                    cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)

                lm = resultado.pose_world_landmarks[0]
                for nombre, (idx_a, idx_b, idx_c) in DEFINICIONES_ANGULOS.items():
                    lm_a, lm_b, lm_c = lm[idx_a], lm[idx_b], lm[idx_c]
                    if (punto_confiable(lm_a, UMBRAL_VISIBILIDAD)
                            and punto_confiable(lm_b, UMBRAL_VISIBILIDAD)
                            and punto_confiable(lm_c, UMBRAL_VISIBILIDAD)):
                        a = [lm_a.x, lm_a.y, lm_a.z]
                        b = [lm_b.x, lm_b.y, lm_b.z]
                        c = [lm_c.x, lm_c.y, lm_c.z]
                        angulo = calcular_angulo(a, b, c)
                        historial[nombre].append(angulo)
                    else:
                        descartados[nombre] += 1

            salida.write(frame)
            cv2.imshow(NOMBRE_VENTANA, frame)

            tecla = cv2.waitKey(1) & 0xFF
            ventana_cerrada = cv2.getWindowProperty(NOMBRE_VENTANA, cv2.WND_PROP_VISIBLE) < 1

            if tecla == ord("q") or ventana_cerrada:
                break

            frame_num += 1

    cap.release()
    salida.release()
    cv2.destroyAllWindows()

    print(f"\nVideo guardado en salida_con_puntos.mp4")
    print(f"Total de fotogramas procesados: {frame_num}")
    print("\nResumen por articulacion:")
    for nombre in DEFINICIONES_ANGULOS:
        valores = historial[nombre]
        n_desc = descartados[nombre]
        if valores:
            print(f"  {nombre}: {min(valores):.1f} - {max(valores):.1f} grados "
                  f"({len(valores)} validos, {n_desc} descartados)")
        else:
            print(f"  {nombre}: sin datos confiables ({n_desc} descartados)")

    datos_a_guardar = {k: np.array(v) for k, v in historial.items() if v}
    if datos_a_guardar:
        np.savez("angulos_sesion.npz", **datos_a_guardar)
        print("\nAngulos guardados en angulos_sesion.npz")
    else:
        print("\nNo se guardo ningun angulo: ninguna articulacion tuvo datos confiables.")


if __name__ == "__main__":
    main()
