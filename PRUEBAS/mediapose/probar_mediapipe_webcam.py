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

# Indices de MediaPipe Pose (33 puntos), lado izquierdo y derecho
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

UMBRAL_VISIBILIDAD = 0.6  # entre 0 y 1; ajustar segun se observe en pruebas


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

    DURACION_SEGUNDOS = 10
    print(f"Grabando {DURACION_SEGUNDOS} segundos. Ubicate frente a la camara.")
    print(f"Umbral de visibilidad: {UMBRAL_VISIBILIDAD}")

    historial = {nombre: [] for nombre in DEFINICIONES_ANGULOS}
    descartados = {nombre: 0 for nombre in DEFINICIONES_ANGULOS}

    with PoseLandmarker.create_from_options(options) as landmarker:
        inicio = time.time()
        frame_num = 0

        while (time.time() - inicio) < DURACION_SEGUNDOS:
            ok, frame = cap.read()
            if not ok:
                print("No se pudo leer la camara")
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            timestamp_ms = int((time.time() - inicio) * 1000)

            resultado = landmarker.detect_for_video(mp_image, timestamp_ms)

            if resultado.pose_world_landmarks:
                lm = resultado.pose_world_landmarks[0]

                angulos_frame = {}
                for nombre, (idx_a, idx_b, idx_c) in DEFINICIONES_ANGULOS.items():
                    lm_a, lm_b, lm_c = lm[idx_a], lm[idx_b], lm[idx_c]

                    if (punto_confiable(lm_a, UMBRAL_VISIBILIDAD)
                            and punto_confiable(lm_b, UMBRAL_VISIBILIDAD)
                            and punto_confiable(lm_c, UMBRAL_VISIBILIDAD)):
                        a = [lm_a.x, lm_a.y, lm_a.z]
                        b = [lm_b.x, lm_b.y, lm_b.z]
                        c = [lm_c.x, lm_c.y, lm_c.z]
                        angulo = calcular_angulo(a, b, c)
                        angulos_frame[nombre] = angulo
                        historial[nombre].append(angulo)
                    else:
                        angulos_frame[nombre] = None
                        descartados[nombre] += 1

                if frame_num % 10 == 0:
                    partes = []
                    for n, v in angulos_frame.items():
                        partes.append(f"{n}={v:.0f}" if v is not None else f"{n}=NC")
                    print(f"Fotograma {frame_num}: {', '.join(partes)}")
            else:
                if frame_num % 10 == 0:
                    print(f"Fotograma {frame_num}: sin persona detectada")

            frame_num += 1

    cap.release()

    print(f"\nTotal de fotogramas procesados: {frame_num}")
    print("(NC = no confiable, descartado por baja visibilidad)")
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
        print("\nSecuencia guardada en angulos_sesion.npz (solo articulaciones con datos validos)")
    else:
        print("\nNo se guardo nada: ninguna articulacion tuvo datos confiables.")


if __name__ == "__main__":
    main()
