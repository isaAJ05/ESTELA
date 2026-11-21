"""
entrenar_bilstm.py
====================

Fase 3 del pipeline ESTELA: entrena y evalúa un BiLSTM sobre los
.npz generados por preparar_dataset.py (train.npz / val.npz / test.npz).

Se ejecuta UNA VEZ por cada combinación que quieras comparar, por ejemplo:

    POSE_MODEL = "mediapipe" | FEATURE_MODE = "coords"
    POSE_MODEL = "rtmpose"   | FEATURE_MODE = "coords"
    POSE_MODEL = "mediapipe" | FEATURE_MODE = "angles_distances"
    ...

Cada corrida guarda, en una carpeta separada por combinación:

    modelo.keras
    metricas.json
    matriz_confusion.png
    curvas_entrenamiento.png

para que después puedas armar la tabla comparativa
(Accuracy, Precision, Recall, F1, tiempo de inferencia, FPS, tamaño)
sin mezclar resultados entre experimentos.
"""

import json
import time
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import tensorflow as tf
from tensorflow.keras import layers, models, callbacks

from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

POSE_MODEL = "mediapipe"     # "mediapipe" | "rtmpose"
FEATURE_MODE = "coords"      # "coords" | "angles_distances" | "combined"

RUTA_DATASET = Path(
    rf"C:\Users\USUARIO\Downloads\Prueba2\DATASET\{POSE_MODEL}\{FEATURE_MODE}"
)

RUTA_SALIDA = Path(
    rf"C:\Users\USUARIO\Downloads\Prueba2\DATASET\\resultados\{POSE_MODEL}_{FEATURE_MODE}"
)

EPOCHS = 100
BATCH_SIZE = 16
LEARNING_RATE = 1e-3
PATIENCE = 15  # early stopping

SEED = 42


# ============================================================
# CARGA DE DATOS
# ============================================================

def cargar_split(nombre):
    ruta = RUTA_DATASET / f"{nombre}.npz"
    data = np.load(ruta, allow_pickle=True)
    return data["X"], data["y"], data["origen"], data["clases"]


def main():
    tf.random.set_seed(SEED)
    np.random.seed(SEED)

    RUTA_SALIDA.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"POSE_MODEL   = {POSE_MODEL}")
    print(f"FEATURE_MODE = {FEATURE_MODE}")
    print("=" * 70)

    X_train, y_train, _, clases = cargar_split("train")
    X_val, y_val, _, _ = cargar_split("val")
    X_test, y_test, origen_test, _ = cargar_split("test")

    clases = [str(c) for c in clases]
    n_clases = len(clases)

    print(f"\nTrain: X={X_train.shape}, y={y_train.shape}")
    print(f"Val:   X={X_val.shape}, y={y_val.shape}")
    print(f"Test:  X={X_test.shape}, y={y_test.shape}")
    print(f"Clases: {clases}")

    if X_val.shape[0] == 0:
        raise ValueError(
            "El split de validación está vacío. Revisa preparar_dataset.py "
            "(dividir_videos) o el número de videos por ejercicio."
        )

    window_size = X_train.shape[1]
    n_features = X_train.shape[2]

    # --------------------------------------------------------
    # NORMALIZACIÓN (z-score) usando estadísticas de TRAIN
    # --------------------------------------------------------

    media = X_train.reshape(-1, n_features).mean(axis=0)
    desviacion = X_train.reshape(-1, n_features).std(axis=0) + 1e-6

    X_train = (X_train - media) / desviacion
    X_val = (X_val - media) / desviacion
    X_test = (X_test - media) / desviacion

    np.savez(RUTA_SALIDA / "normalizacion.npz", media=media, desviacion=desviacion)

    # --------------------------------------------------------
    # MODELO
    # --------------------------------------------------------

    modelo = models.Sequential([
        layers.Input(shape=(window_size, n_features)),
        layers.Masking(mask_value=0.0),
        layers.Bidirectional(layers.LSTM(64, return_sequences=True)),
        layers.Dropout(0.3),
        layers.Bidirectional(layers.LSTM(32)),
        layers.Dropout(0.3),
        layers.Dense(32, activation="relu"),
        layers.Dense(n_clases, activation="softmax"),
    ])

    modelo.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    modelo.summary()

    # --------------------------------------------------------
    # CALLBACKS
    # --------------------------------------------------------

    ruta_mejor_modelo = RUTA_SALIDA / "modelo.keras"

    lista_callbacks = [
        callbacks.EarlyStopping(
            monitor="val_loss", patience=PATIENCE, restore_best_weights=True
        ),
        callbacks.ModelCheckpoint(
            str(ruta_mejor_modelo), monitor="val_loss", save_best_only=True
        ),
        callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=7, min_lr=1e-6
        ),
    ]

    # --------------------------------------------------------
    # ENTRENAMIENTO
    # --------------------------------------------------------

    t0 = time.time()

    historial = modelo.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=lista_callbacks,
        verbose=2,
    )

    tiempo_entrenamiento = time.time() - t0

    # --------------------------------------------------------
    # CURVAS DE ENTRENAMIENTO
    # --------------------------------------------------------

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    axes[0].plot(historial.history["loss"], label="train")
    axes[0].plot(historial.history["val_loss"], label="val")
    axes[0].set_title("Loss")
    axes[0].set_xlabel("Época")
    axes[0].legend()

    axes[1].plot(historial.history["accuracy"], label="train")
    axes[1].plot(historial.history["val_accuracy"], label="val")
    axes[1].set_title("Accuracy")
    axes[1].set_xlabel("Época")
    axes[1].legend()

    fig.suptitle(f"{POSE_MODEL} + {FEATURE_MODE}")
    fig.tight_layout()
    fig.savefig(RUTA_SALIDA / "curvas_entrenamiento.png", dpi=150)
    plt.close(fig)

    # --------------------------------------------------------
    # EVALUACIÓN EN TEST
    # --------------------------------------------------------

    t0 = time.time()
    y_pred_probs = modelo.predict(X_test, batch_size=BATCH_SIZE)
    tiempo_inferencia_total = time.time() - t0

    y_pred = np.argmax(y_pred_probs, axis=1)

    n_test = X_test.shape[0]
    tiempo_por_ventana = tiempo_inferencia_total / max(n_test, 1)
    fps_estimado = 1.0 / tiempo_por_ventana if tiempo_por_ventana > 0 else float("inf")

    accuracy = accuracy_score(y_test, y_pred)
    reporte = classification_report(
        y_test, y_pred, target_names=clases, output_dict=True, zero_division=0
    )
    matriz = confusion_matrix(y_test, y_pred)

    print("\n" + "=" * 70)
    print(f"Accuracy en test: {accuracy:.4f}")
    print("=" * 70)
    print(classification_report(y_test, y_pred, target_names=clases, zero_division=0))
    print("Matriz de confusión:")
    print(matriz)

    # --------------------------------------------------------
    # MATRIZ DE CONFUSIÓN (gráfico)
    # --------------------------------------------------------

    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(matriz, cmap="Blues")

    ax.set_xticks(range(n_clases))
    ax.set_yticks(range(n_clases))
    ax.set_xticklabels(clases, rotation=45, ha="right")
    ax.set_yticklabels(clases)
    ax.set_xlabel("Predicho")
    ax.set_ylabel("Real")
    ax.set_title(f"Matriz de confusión\n{POSE_MODEL} + {FEATURE_MODE}")

    for i in range(n_clases):
        for j in range(n_clases):
            ax.text(j, i, str(matriz[i, j]), ha="center", va="center",
                     color="white" if matriz[i, j] > matriz.max() / 2 else "black")

    fig.colorbar(im)
    fig.tight_layout()
    fig.savefig(RUTA_SALIDA / "matriz_confusion.png", dpi=150)
    plt.close(fig)

    # --------------------------------------------------------
    # TAMAÑO DEL MODELO
    # --------------------------------------------------------

    tamano_mb = ruta_mejor_modelo.stat().st_size / (1024 * 1024)

    # --------------------------------------------------------
    # QUÉ EJERCICIO SE CONFUNDE CON CUÁL
    # --------------------------------------------------------

    confusiones = []
    for i in range(n_clases):
        for j in range(n_clases):
            if i != j and matriz[i, j] > 0:
                confusiones.append({
                    "real": clases[i],
                    "predicho": clases[j],
                    "cantidad": int(matriz[i, j]),
                })
    confusiones.sort(key=lambda c: -c["cantidad"])

    # --------------------------------------------------------
    # GUARDAR MÉTRICAS
    # --------------------------------------------------------

    metricas = {
        "pose_model": POSE_MODEL,
        "feature_mode": FEATURE_MODE,
        "clases": clases,
        "n_train": int(X_train.shape[0]),
        "n_val": int(X_val.shape[0]),
        "n_test": int(X_test.shape[0]),
        "accuracy": float(accuracy),
        "reporte_por_clase": reporte,
        "matriz_confusion": matriz.tolist(),
        "confusiones_mas_frecuentes": confusiones,
        "tiempo_entrenamiento_seg": float(tiempo_entrenamiento),
        "epocas_entrenadas": len(historial.history["loss"]),
        "tiempo_inferencia_total_seg": float(tiempo_inferencia_total),
        "tiempo_por_ventana_seg": float(tiempo_por_ventana),
        "fps_estimado": float(fps_estimado),
        "tamano_modelo_mb": float(tamano_mb),
    }

    with open(RUTA_SALIDA / "metricas.json", "w", encoding="utf-8") as f:
        json.dump(metricas, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f"✅ Resultados guardados en: {RUTA_SALIDA}")
    print("=" * 70)
    print(f"  - modelo.keras")
    print(f"  - metricas.json")
    print(f"  - matriz_confusion.png")
    print(f"  - curvas_entrenamiento.png")
    print(f"\nFPS estimado en inferencia: {fps_estimado:.1f}")
    print(f"Tamaño del modelo: {tamano_mb:.2f} MB")


if __name__ == "__main__":
    main()