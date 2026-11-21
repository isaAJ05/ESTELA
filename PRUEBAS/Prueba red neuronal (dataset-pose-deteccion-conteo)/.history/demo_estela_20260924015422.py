"""
demo_estela.py
================
Demo en tiempo real de ESTELA:

    CÁMARA -> MediaPipe -> buffer de 30 frames -> BiLSTM
           -> ejercicio detectado -> contador de repeticiones -> feedback

Dos modos, cambiables con el teclado mientras corre:

    - Modo AUTOMÁTICO (por defecto): el BiLSTM clasifica el ejercicio
      cada vez que hay 30 frames nuevos en el buffer.
    - Modo MANUAL: tú eliges el ejercicio con las teclas 1-4 y el
      contador usa ese ejercicio directamente (sin pasar por el BiLSTM).

Teclas:
    1 -> elevacion_brazos  (fuerza modo manual)
    2 -> jumping_jack      (fuerza modo manual)
    3 -> marcha_rodillas   (fuerza modo manual)
    4 -> sentadilla        (fuerza modo manual)
    a -> volver a modo automático (BiLSTM)
    r -> reiniciar todos los contadores
    q -> salir

Usa el modelo entrenado con feature_mode="coords" sobre MediaPipe
(el de mejor accuracy: 84.7%) y el archivo de normalización que
generó entrenar_bilstm.py para esa misma combinación.
"""

import time
from collections import deque, Counter
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
import tensorflow as tf


# ============================================================
# CONFIGURACIÓN — AJUSTA ESTAS RUTAS A TU CARPETA REAL
# ============================================================

RUTA_MODELO = Path(
    r"C:\Users\USUARIO\Downloads\Prueba2\resultados\mediapipe_coords\modelo.h5"
)
RUTA_NORMALIZACION = Path(
    r"C:\Users\USUARIO\Downloads\Prueba2\resultados\mediapipe_coords\normalizacion.npz"
)

EJERCICIOS = [
    "elevacion_brazos",
    "jumping_jack",
    "marcha_rodillas",
    "sentadilla",
]

WINDOW_SIZE = 30
CONFIANZA_MINIMA = 0.60     # por debajo de esto, se muestra "Detectando..."
VOTOS_SUAVIZADO = 5         # mayoría entre las últimas N predicciones (evita parpadeo)

CAMARA_ID = 0

MEDIAPIPE_JOINTS = {
    "nose": 0,
    "l_shoulder": 11, "r_shoulder": 12,
    "l_elbow": 13, "r_elbow": 14,
    "l_wrist": 15, "r_wrist": 16,
    "l_hip": 23, "r_hip": 24,
    "l_knee": 25, "r_knee": 26,
    "l_ankle": 27, "r_ankle": 28,
}

# --------------------------------------------------------
# UMBRALES DEL CONTADOR — ajústalos viendo tu propia cámara.
# Son normalizados por el "tamaño de torso" (hombro-cadera),
# así que en teoría no dependen mucho de qué tan lejos estés
# de la cámara.
# --------------------------------------------------------

UMBRAL_RODILLA_ARRIBA = 160.0     # grados; pierna casi extendida
UMBRAL_RODILLA_ABAJO = 110.0      # grados; pierna flexionada (sentadilla)

UMBRAL_JJ_ABIERTO = 0.55          # distancia tobillo-tobillo / torso
UMBRAL_JJ_CERRADO = 0.25

UMBRAL_BRAZO_ARRIBA_REL = -0.15   # (muñeca_y - hombro_y) / torso; negativo = muñecas arriba
UMBRAL_BRAZO_ABAJO_REL = 0.15

UMBRAL_MARCHA_RODILLA_REL = -0.05  # (rodilla_y - cadera_y) / torso; negativo = rodilla elevada


# ============================================================
# UTILIDADES GEOMÉTRICAS (mismas fórmulas que preparar_dataset.py)
# ============================================================

def punto(frame, idx):
    return frame[idx, 0], frame[idx, 1]


def midpoint(a, b):
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def distancia(a, b):
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def angulo(a, b, c):
    a = np.array(a, dtype=np.float32)
    b = np.array(b, dtype=np.float32)
    c = np.array(c, dtype=np.float32)
    ba = a - b
    bc = c - b
    denom = (np.linalg.norm(ba) * np.linalg.norm(bc)) + 1e-8
    coseno = np.clip(np.dot(ba, bc) / denom, -1.0, 1.0)
    return float(np.degrees(np.arccos(coseno)))


def torso_size(frame, joints):
    l_hip = punto(frame, joints["l_hip"])
    r_hip = punto(frame, joints["r_hip"])
    l_sh = punto(frame, joints["l_shoulder"])
    r_sh = punto(frame, joints["r_shoulder"])
    mid_hip = midpoint(l_hip, r_hip)
    mid_sh = midpoint(l_sh, r_sh)
    return distancia(mid_sh, mid_hip) + 1e-6


def normalizar_secuencia(secuencia, joints):
    """Idéntico a la normalización usada en preparar_dataset.py:
    centra x,y en la cadera y escala por el tamaño del torso."""
    out = secuencia.copy()
    for f in range(secuencia.shape[0]):
        frame = secuencia[f]
        l_hip = punto(frame, joints["l_hip"])
        r_hip = punto(frame, joints["r_hip"])
        l_sh = punto(frame, joints["l_shoulder"])
        r_sh = punto(frame, joints["r_shoulder"])
        mid_hip = midpoint(l_hip, r_hip)
        mid_sh = midpoint(l_sh, r_sh)
        torso = distancia(mid_sh, mid_hip) + 1e-6

        out[f, :, 0] = (frame[:, 0] - mid_hip[0]) / torso
        out[f, :, 1] = (frame[:, 1] - mid_hip[1]) / torso
        if secuencia.shape[2] >= 4:
            out[f, :, 2] = frame[:, 2] / torso
    return out


# ============================================================
# CONTADOR DE REPETICIONES (máquina de estados por ejercicio)
# ============================================================

class ContadorRepeticiones:
    def __init__(self):
        self.contadores = {ej: 0 for ej in EJERCICIOS}
        self.estados = {ej: None for ej in EJERCICIOS}

    def reiniciar(self):
        for ej in EJERCICIOS:
            self.contadores[ej] = 0
            self.estados[ej] = None

    def actualizar(self, ejercicio, frame_landmarks, joints):
        if ejercicio == "sentadilla":
            self._sentadilla(frame_landmarks, joints)
        elif ejercicio == "jumping_jack":
            self._jumping_jack(frame_landmarks, joints)
        elif ejercicio == "elevacion_brazos":
            self._elevacion_brazos(frame_landmarks, joints)
        elif ejercicio == "marcha_rodillas":
            self._marcha_rodillas(frame_landmarks, joints)

    def _contar_en_transicion(self, ejercicio, nuevo_estado, de_estado, a_estado):
        anterior = self.estados[ejercicio]
        if anterior == de_estado and nuevo_estado == a_estado:
            self.contadores[ejercicio] += 1
        self.estados[ejercicio] = nuevo_estado

    def _sentadilla(self, frame, joints):
        ang_izq = angulo(
            punto(frame, joints["l_hip"]), punto(frame, joints["l_knee"]),
            punto(frame, joints["l_ankle"]),
        )
        ang_der = angulo(
            punto(frame, joints["r_hip"]), punto(frame, joints["r_knee"]),
            punto(frame, joints["r_ankle"]),
        )
        ang = (ang_izq + ang_der) / 2.0

        estado_actual = self.estados["sentadilla"]
        if ang > UMBRAL_RODILLA_ARRIBA:
            nuevo = "up"
        elif ang < UMBRAL_RODILLA_ABAJO:
            nuevo = "down"
        else:
            nuevo = estado_actual

        # Una repetición = bajar y volver a subir.
        self._contar_en_transicion("sentadilla", nuevo, de_estado="down", a_estado="up")

    def _jumping_jack(self, frame, joints):
        torso = torso_size(frame, joints)
        d = distancia(punto(frame, joints["l_ankle"]), punto(frame, joints["r_ankle"])) / torso

        estado_actual = self.estados["jumping_jack"]
        if d > UMBRAL_JJ_ABIERTO:
            nuevo = "abierto"
        elif d < UMBRAL_JJ_CERRADO:
            nuevo = "cerrado"
        else:
            nuevo = estado_actual

        # Una repetición = abrir y volver a cerrar.
        self._contar_en_transicion("jumping_jack", nuevo, de_estado="abierto", a_estado="cerrado")

    def _elevacion_brazos(self, frame, joints):
        torso = torso_size(frame, joints)
        _, hombro_y = midpoint(punto(frame, joints["l_shoulder"]), punto(frame, joints["r_shoulder"]))
        _, muneca_izq_y = punto(frame, joints["l_wrist"])
        _, muneca_der_y = punto(frame, joints["r_wrist"])
        muneca_y = (muneca_izq_y + muneca_der_y) / 2.0

        rel = (muneca_y - hombro_y) / torso  # negativo = muñecas arriba del hombro

        estado_actual = self.estados["elevacion_brazos"]
        if rel < UMBRAL_BRAZO_ARRIBA_REL:
            nuevo = "up"
        elif rel > UMBRAL_BRAZO_ABAJO_REL:
            nuevo = "down"
        else:
            nuevo = estado_actual

        # Una repetición = subir los brazos y volver a bajarlos.
        self._contar_en_transicion("elevacion_brazos", nuevo, de_estado="up", a_estado="down")

    def _marcha_rodillas(self, frame, joints):
        torso = torso_size(frame, joints)
        _, cadera_y = midpoint(punto(frame, joints["l_hip"]), punto(frame, joints["r_hip"]))
        _, rodilla_izq_y = punto(frame, joints["l_knee"])
        _, rodilla_der_y = punto(frame, joints["r_knee"])

        rel_izq = (rodilla_izq_y - cadera_y) / torso
        rel_der = (rodilla_der_y - cadera_y) / torso

        pierna_arriba = None
        if rel_izq < UMBRAL_MARCHA_RODILLA_REL and rel_izq < rel_der:
            pierna_arriba = "izquierda"
        elif rel_der < UMBRAL_MARCHA_RODILLA_REL and rel_der < rel_izq:
            pierna_arriba = "derecha"

        estado_actual = self.estados["marcha_rodillas"]  # última pierna elevada

        # Una repetición = cada vez que se eleva la pierna CONTRARIA a
        # la última que estuvo arriba (alternancia real, no solo "arriba").
        if pierna_arriba is not None and pierna_arriba != estado_actual:
            self.contadores["marcha_rodillas"] += 1
            self.estados["marcha_rodillas"] = pierna_arriba


# ============================================================
# PRINCIPAL
# ============================================================

def main():
    print("Cargando modelo BiLSTM...")
    modelo = tf.keras.models.load_model(str(RUTA_MODELO))

    normal = np.load(RUTA_NORMALIZACION)
    media = normal["media"]
    desviacion = normal["desviacion"]

    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils

    contador = ContadorRepeticiones()

    buffer_landmarks = deque(maxlen=WINDOW_SIZE)
    historial_predicciones = deque(maxlen=VOTOS_SUAVIZADO)

    modo_manual = False
    ejercicio_manual = EJERCICIOS[0]
    ejercicio_activo = None

    prediccion_texto = ""
    confianza_texto = ""

    cap = cv2.VideoCapture(CAMARA_ID)
    if not cap.isOpened():
        raise RuntimeError("No se pudo abrir la cámara. Revisa CAMARA_ID.")

    with mp_pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        smooth_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as pose:

        prev_time = time.time()

        while True:
            ok, frame_bgr = cap.read()
            if not ok:
                break

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            resultado = pose.process(frame_rgb)

            if resultado.pose_landmarks is not None:
                landmarks = resultado.pose_landmarks.landmark
                frame_landmarks = np.array(
                    [[lm.x, lm.y, lm.z, lm.visibility] for lm in landmarks],
                    dtype=np.float32,
                )

                mp_drawing.draw_landmarks(
                    frame_bgr, resultado.pose_landmarks, mp_pose.POSE_CONNECTIONS
                )

                buffer_landmarks.append(frame_landmarks)

                # ------------------------------------------------
                # CLASIFICACIÓN CON EL BiLSTM (cuando hay 30 frames)
                # ------------------------------------------------
                if len(buffer_landmarks) == WINDOW_SIZE:
                    secuencia = np.array(buffer_landmarks, dtype=np.float32)
                    secuencia_norm = normalizar_secuencia(secuencia, MEDIAPIPE_JOINTS)
                    features = secuencia_norm.reshape(1, WINDOW_SIZE, -1)
                    features = (features - media) / desviacion

                    probs = modelo.predict(features, verbose=0)[0]
                    idx_pred = int(np.argmax(probs))
                    confianza = float(probs[idx_pred])

                    historial_predicciones.append(idx_pred)
                    prediccion_texto = EJERCICIOS[idx_pred]
                    confianza_texto = f"{confianza * 100:.0f}%"

                    if not modo_manual:
                        mas_comun, _ = Counter(historial_predicciones).most_common(1)[0]
                        ejercicio_activo = EJERCICIOS[mas_comun] if confianza >= CONFIANZA_MINIMA else None

                if modo_manual:
                    ejercicio_activo = ejercicio_manual

                if ejercicio_activo is not None:
                    contador.actualizar(ejercicio_activo, frame_landmarks, MEDIAPIPE_JOINTS)
            else:
                ejercicio_activo = None if not modo_manual else ejercicio_manual

            # --------------------------------------------------------
            # FPS
            # --------------------------------------------------------
            ahora = time.time()
            fps = 1.0 / (ahora - prev_time) if ahora > prev_time else 0.0
            prev_time = ahora

            # --------------------------------------------------------
            # OVERLAY EN PANTALLA
            # --------------------------------------------------------
            modo_texto = "MANUAL" if modo_manual else "AUTOMATICO (BiLSTM)"
            cv2.putText(frame_bgr, f"Modo: {modo_texto}", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

            if ejercicio_activo is not None:
                cv2.putText(frame_bgr, f"Ejercicio: {ejercicio_activo}", (10, 55),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(frame_bgr, f"Repeticiones: {contador.contadores[ejercicio_activo]}",
                            (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            else:
                cv2.putText(frame_bgr, "Detectando ejercicio...", (10, 55),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)

            if not modo_manual and prediccion_texto:
                cv2.putText(frame_bgr, f"BiLSTM: {prediccion_texto} ({confianza_texto})",
                            (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

            cv2.putText(frame_bgr, f"FPS: {fps:.1f}", (10, frame_bgr.shape[0] - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            cv2.putText(
                frame_bgr,
                "1-4: elegir ejercicio | a: automatico | r: reiniciar | q: salir",
                (10, frame_bgr.shape[0] - 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
            )

            cv2.imshow("ESTELA - Demo", frame_bgr)

            tecla = cv2.waitKey(1) & 0xFF
            if tecla == ord("q"):
                break
            elif tecla == ord("a"):
                modo_manual = False
                ejercicio_activo = None
                historial_predicciones.clear()
            elif tecla == ord("r"):
                contador.reiniciar()
            elif tecla in (ord("1"), ord("2"), ord("3"), ord("4")):
                idx = tecla - ord("1")
                modo_manual = True
                ejercicio_manual = EJERCICIOS[idx]
                ejercicio_activo = ejercicio_manual

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()