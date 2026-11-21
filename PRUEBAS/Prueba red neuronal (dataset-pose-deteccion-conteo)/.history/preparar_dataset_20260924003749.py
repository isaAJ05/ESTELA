"""
preparar_dataset.py
====================

Fase 2 del pipeline ESTELA: toma los .npy generados por
extraer_mediapipe.py o extraer_rtmpose.py y produce un dataset
listo para el BiLSTM (Fase 3), con:

  1. Interpolación de frames sin detección (NaN).
  2. Normalización respecto al torso (centro en cadera, escala por
     distancia hombro-cadera) -> invariante a posición/tamaño en cámara.
  3. Cálculo de features según FEATURE_MODE:
         "coords"            -> x,y (y z si aplica) normalizados
         "angles_distances"  -> ángulos articulares + distancias normalizadas
         "combined"          -> las dos anteriores concatenadas
  4. Generación de ventanas deslizantes de WINDOW_SIZE frames.
  5. División TRAIN/VAL/TEST por VIDEO (nunca por ventana), para que
     ventanas del mismo video no aparezcan en dos particiones distintas.

Se ejecuta UNA VEZ por cada estimador de pose (cambiando POSE_MODEL),
así se generan por separado:

    dataset_bilstm/mediapipe/...
    dataset_bilstm/rtmpose/...

listos para comparar bajo el mismo pipeline de entrenamiento.
"""

import numpy as np
from pathlib import Path
import json


# ============================================================
# CONFIGURACIÓN
# ============================================================

# Cuál estimador de pose estamos preparando en esta corrida.
# Ejecuta el script dos veces: una con "mediapipe" y otra con "rtmpose".
POSE_MODEL = "mediapipe"  # "mediapipe" | "rtmpose"

# Qué representación de movimiento usar como entrada del BiLSTM.
FEATURE_MODE = "coords"  # "coords" | "angles_distances" | "combined"

RUTA_DATASETS = {
    "mediapipe": Path(r"C:\Users\USUARIO\Downloads\ESTELA_DATASET\dataset_mediapipe"),
    "rtmpose": Path(r"C:\Users\USUARIO\Downloads\ESTELA_DATASET\dataset_rtmpose"),
}

RUTA_SALIDA = Path(r"C:\Users\USUARIO\Downloads\ESTELA_DATASET\dataset_bilstm")

EJERCICIOS = [
    "elevacion_brazos",
    "jumping_jack",
    "marcha_rodillas",
    "sentadilla",
]

WINDOW_SIZE = 30
STRIDE = 15  # 50% de solapamiento entre ventanas

# Proporciones aproximadas para la división por video.
TRAIN_RATIO = 0.60
VAL_RATIO = 0.15
TEST_RATIO = 0.25

# Si un video tiene más de este % de frames sin detección, se descarta.
MAX_PORC_NAN = 40.0

# Semilla para que la división por video sea reproducible.
SEED = 42


# ============================================================
# MAPEOS DE ARTICULACIONES (comunes a ambos estimadores)
# ============================================================

MEDIAPIPE_JOINTS = {
    "nose": 0,
    "l_shoulder": 11, "r_shoulder": 12,
    "l_elbow": 13, "r_elbow": 14,
    "l_wrist": 15, "r_wrist": 16,
    "l_hip": 23, "r_hip": 24,
    "l_knee": 25, "r_knee": 26,
    "l_ankle": 27, "r_ankle": 28,
}

RTMPOSE_JOINTS = {
    "nose": 0,
    "l_shoulder": 5, "r_shoulder": 6,
    "l_elbow": 7, "r_elbow": 8,
    "l_wrist": 9, "r_wrist": 10,
    "l_hip": 11, "r_hip": 12,
    "l_knee": 13, "r_knee": 14,
    "l_ankle": 15, "r_ankle": 16,
}


def obtener_joints(model):
    return MEDIAPIPE_JOINTS if model == "mediapipe" else RTMPOSE_JOINTS


# ============================================================
# UTILIDADES GEOMÉTRICAS
# ============================================================

def punto(frame, idx):
    """Devuelve (x, y) de un landmark/keypoint en un frame."""
    return frame[idx, 0], frame[idx, 1]


def midpoint(a, b):
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def distancia(a, b):
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def angulo(a, b, c):
    """Ángulo (en grados) en el vértice b, formado por a-b-c."""
    a = np.array(a, dtype=np.float32)
    b = np.array(b, dtype=np.float32)
    c = np.array(c, dtype=np.float32)

    ba = a - b
    bc = c - b

    denom = (np.linalg.norm(ba) * np.linalg.norm(bc)) + 1e-8
    coseno = np.dot(ba, bc) / denom
    coseno = np.clip(coseno, -1.0, 1.0)

    return float(np.degrees(np.arccos(coseno)))


# ============================================================
# INTERPOLACIÓN DE FRAMES SIN DETECCIÓN
# ============================================================

def interpolar_nans(secuencia):
    """
    secuencia: (frames, landmarks, canales)
    Interpola linealmente en el tiempo cada coordenada que tenga NaN.
    Si una columna es NaN en todos los frames, se deja en 0.
    """
    frames, n_landmarks, canales = secuencia.shape
    plano = secuencia.reshape(frames, -1).copy()

    idx = np.arange(frames)

    for col in range(plano.shape[1]):
        serie = plano[:, col]
        nans = np.isnan(serie)

        if nans.all():
            serie[:] = 0.0
        elif nans.any():
            serie[nans] = np.interp(idx[nans], idx[~nans], serie[~nans])

        plano[:, col] = serie

    return plano.reshape(frames, n_landmarks, canales)


# ============================================================
# NORMALIZACIÓN (centro en cadera, escala por torso)
# ============================================================

def normalizar_coordenadas(secuencia, joints):
    """
    secuencia: (frames, landmarks, canales) ya sin NaN.
    Centra x,y en el punto medio de la cadera y escala por la
    distancia hombro-cadera (tamaño de torso), frame a frame.
    """
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

        # Si hay canal z (MediaPipe), también se escala.
        if secuencia.shape[2] >= 4:
            out[f, :, 2] = frame[:, 2] / torso

    return out


# ============================================================
# FEATURES: ÁNGULOS + DISTANCIAS
# ============================================================

def features_angulos_distancias(frame_normalizado, joints):
    j = joints

    def P(nombre):
        return punto(frame_normalizado, j[nombre])

    l_knee_angle = angulo(P("l_hip"), P("l_knee"), P("l_ankle"))
    r_knee_angle = angulo(P("r_hip"), P("r_knee"), P("r_ankle"))
    l_elbow_angle = angulo(P("l_shoulder"), P("l_elbow"), P("l_wrist"))
    r_elbow_angle = angulo(P("r_shoulder"), P("r_elbow"), P("r_wrist"))
    l_hip_angle = angulo(P("l_shoulder"), P("l_hip"), P("l_knee"))
    r_hip_angle = angulo(P("r_shoulder"), P("r_hip"), P("r_knee"))

    d_wrist_shoulder_l = distancia(P("l_wrist"), P("l_shoulder"))
    d_wrist_shoulder_r = distancia(P("r_wrist"), P("r_shoulder"))
    d_ankle_ankle = distancia(P("l_ankle"), P("r_ankle"))
    d_wrist_wrist = distancia(P("l_wrist"), P("r_wrist"))
    d_knee_knee = distancia(P("l_knee"), P("r_knee"))

    return np.array([
        l_knee_angle, r_knee_angle,
        l_elbow_angle, r_elbow_angle,
        l_hip_angle, r_hip_angle,
        d_wrist_shoulder_l, d_wrist_shoulder_r,
        d_ankle_ankle, d_wrist_wrist, d_knee_knee,
    ], dtype=np.float32)


def construir_features(secuencia_normalizada, joints, feature_mode):
    """
    secuencia_normalizada: (frames, landmarks, canales)
    Devuelve: (frames, n_features)
    """
    frames = secuencia_normalizada.shape[0]

    if feature_mode == "coords":
        return secuencia_normalizada.reshape(frames, -1).astype(np.float32)

    angulos_dist = np.array([
        features_angulos_distancias(secuencia_normalizada[f], joints)
        for f in range(frames)
    ], dtype=np.float32)

    if feature_mode == "angles_distances":
        return angulos_dist

    if feature_mode == "combined":
        coords = secuencia_normalizada.reshape(frames, -1).astype(np.float32)
        return np.concatenate([coords, angulos_dist], axis=1)

    raise ValueError(f"FEATURE_MODE desconocido: {feature_mode}")


# ============================================================
# VENTANAS DESLIZANTES
# ============================================================

def generar_ventanas(features, window_size, stride):
    n_frames = features.shape[0]
    ventanas = []

    for inicio in range(0, n_frames - window_size + 1, stride):
        ventanas.append(features[inicio:inicio + window_size])

    if len(ventanas) == 0:
        return np.empty((0, window_size, features.shape[1]), dtype=np.float32)

    return np.array(ventanas, dtype=np.float32)


# ============================================================
# DIVISIÓN POR VIDEO (no por ventana)
# ============================================================

def dividir_videos(lista_videos, seed=SEED):
    """
    Recibe la lista de archivos .npy de UN ejercicio y los reparte
    en train/val/test por video, garantizando al menos 1 en val y
    1 en test cuando hay suficientes videos.
    """
    rng = np.random.default_rng(seed)
    videos = list(lista_videos)
    rng.shuffle(videos)

    n = len(videos)

    if n == 0:
        return [], [], []

    if n < 3:
        # Muy pocos videos: todo a entrenamiento, se avisa por consola.
        return videos, [], []

    n_test = max(1, round(n * TEST_RATIO))
    n_val = max(1, round(n * VAL_RATIO))
    n_train = n - n_val - n_test

    if n_train < 1:
        n_train = 1
        n_val = max(0, n - n_train - n_test)

    train = videos[:n_train]
    val = videos[n_train:n_train + n_val]
    test = videos[n_train + n_val:]

    return train, val, test


# ============================================================
# PROCESAMIENTO DE UN VIDEO
# ============================================================

N_LANDMARKS_ESPERADOS = {
    "mediapipe": 33,
    "rtmpose": 17,
}


def procesar_video(path_npy, joints, feature_mode):
    secuencia = np.load(path_npy)  # (frames, landmarks, canales)

    esperado = N_LANDMARKS_ESPERADOS[POSE_MODEL]
    if secuencia.ndim != 3 or secuencia.shape[1] != esperado:
        raise ValueError(
            f"\n❌ {path_npy.name} tiene forma {secuencia.shape}, "
            f"pero POSE_MODEL='{POSE_MODEL}' espera (frames, {esperado}, C).\n"
            f"   Revisa RUTA_DATASETS['{POSE_MODEL}']: probablemente apunta "
            f"a la carpeta del OTRO estimador de pose, o ese video no se "
            f"extrajo con el script correcto."
        )

    total_frames = secuencia.shape[0]
    frames_nan = int(np.isnan(secuencia[:, 0, 0]).sum())
    porcentaje_nan = (frames_nan / total_frames * 100) if total_frames > 0 else 100

    if porcentaje_nan > MAX_PORC_NAN:
        return None, porcentaje_nan

    secuencia = interpolar_nans(secuencia)
    secuencia = normalizar_coordenadas(secuencia, joints)
    features = construir_features(secuencia, joints, feature_mode)
    ventanas = generar_ventanas(features, WINDOW_SIZE, STRIDE)

    return ventanas, porcentaje_nan


# ============================================================
# PRINCIPAL
# ============================================================

def main():
    joints = obtener_joints(POSE_MODEL)
    ruta_entrada = RUTA_DATASETS[POSE_MODEL]
    ruta_salida = RUTA_SALIDA / POSE_MODEL / FEATURE_MODE
    ruta_salida.mkdir(parents=True, exist_ok=True)

    splits = {"train": [], "val": [], "test": []}
    origenes = {"train": [], "val": [], "test": []}
    etiquetas = {"train": [], "val": [], "test": []}

    resumen = []

    print("=" * 70)
    print(f"POSE_MODEL   = {POSE_MODEL}")
    print(f"FEATURE_MODE = {FEATURE_MODE}")
    print("=" * 70)

    for clase_idx, ejercicio in enumerate(EJERCICIOS):
        carpeta = ruta_entrada / ejercicio

        if not carpeta.exists():
            print(f"\n⚠️ No existe: {carpeta}")
            continue

        videos = sorted(carpeta.glob("*.npy"))
        print(f"\n{ejercicio}: {len(videos)} videos encontrados")

        train_v, val_v, test_v = dividir_videos(videos)

        for nombre_split, lista in [("train", train_v), ("val", val_v), ("test", test_v)]:
            for video_path in lista:
                ventanas, porc_nan = procesar_video(video_path, joints, FEATURE_MODE)

                if ventanas is None:
                    print(f"  ❌ Descartado ({porc_nan:.1f}% NaN): {video_path.name}")
                    continue

                if ventanas.shape[0] == 0:
                    print(f"  ⚠️ Sin ventanas (video muy corto): {video_path.name}")
                    continue

                splits[nombre_split].append(ventanas)
                origenes[nombre_split].extend([video_path.stem] * ventanas.shape[0])
                etiquetas[nombre_split].extend([clase_idx] * ventanas.shape[0])

                resumen.append({
                    "video": video_path.name,
                    "ejercicio": ejercicio,
                    "split": nombre_split,
                    "frames": int(porc_nan),
                    "ventanas": int(ventanas.shape[0]),
                })

        print(f"  train={len(train_v)} videos | val={len(val_v)} videos | test={len(test_v)} videos")

    # --------------------------------------------------------
    # CONCATENAR Y GUARDAR
    # --------------------------------------------------------

    for nombre_split in ["train", "val", "test"]:
        if len(splits[nombre_split]) == 0:
            print(f"\n⚠️ El split '{nombre_split}' quedó vacío.")
            continue

        X = np.concatenate(splits[nombre_split], axis=0)
        y = np.array(etiquetas[nombre_split], dtype=np.int64)
        origen = np.array(origenes[nombre_split])

        np.savez(
            ruta_salida / f"{nombre_split}.npz",
            X=X, y=y, origen=origen,
            clases=np.array(EJERCICIOS),
        )

        print(f"\n✅ {nombre_split}.npz -> X={X.shape}, y={y.shape}")

    with open(ruta_salida / "resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f"✅ Dataset guardado en: {ruta_salida}")
    print("=" * 70)


if __name__ == "__main__":
    main()