"""Reconocedor de ejercicio con la BiLSTM entrenada en PRUEBAS/.

Es **consultivo**: sugiere qué ejercicio parece estar haciendo la usuaria y
avisa si no coincide con el de la rutina. Nunca cambia la decisión de
feedback (SegundoInforme §6.1: el ejercicio lo fija la rutina).

La inferencia se hace en numpy leyendo los pesos del `.h5` con h5py, sin
TensorFlow: TF 2.21 no publica wheels para Python 3.14 y el grafo es pequeño
(Masking → BiLSTM(64) → BiLSTM(32) → Dense(32, relu) → Dense(4, softmax)).
Los Dropout no actúan en inferencia. La equivalencia con Keras se comprueba
reproduciendo el accuracy del test split (tests/test_bilstm.py).

El preprocesado replica `normalizar_secuencia` de `PRUEBAS/.../demo_estela.py`
(idéntica a `normalizar_coordenadas` de `preparar_dataset.py`): centrar x,y en
la cadera, escalar x,y,z por el torso 2D, y z-score con `normalizacion.npz`.
Las entradas son landmarks **de imagen** (33×[x,y,z,visibilidad]), igual que
en entrenamiento. `[?]` El modelo se entrenó con la API legacy
`mp.solutions.pose`; aquí llegan landmarks de la Tasks API. Se asume
equivalencia (misma familia BlazePose) sin haberla medido.
"""

from __future__ import annotations

import json
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, List, Optional, Sequence

import numpy as np

#: Nombres de clase del entrenamiento → skill_id de feedback/skills.
CLASE_A_SKILL = {
    "elevacion_brazos": "elevacion_brazos",
    "jumping_jack": "jumping_jacks",
    "marcha_rodillas": "marcha_rodillas",
    "sentadilla": "sentadilla",
}

VENTANA = 30
_L_HOMBRO, _R_HOMBRO, _L_CADERA, _R_CADERA = 11, 12, 23, 24


# ---------------------------------------------------------------------------
# Preprocesado
# ---------------------------------------------------------------------------

def normalizar_secuencia(secuencia: np.ndarray) -> np.ndarray:
    """(frames, 33, 4) → misma forma, centrada en cadera y escalada por torso."""
    out = secuencia.astype(np.float32).copy()
    cadera = (secuencia[:, _L_CADERA, :2] + secuencia[:, _R_CADERA, :2]) / 2.0
    hombro = (secuencia[:, _L_HOMBRO, :2] + secuencia[:, _R_HOMBRO, :2]) / 2.0
    torso = np.hypot(*(hombro - cadera).T) + 1e-6          # (frames,)
    out[:, :, 0] = (secuencia[:, :, 0] - cadera[:, None, 0]) / torso[:, None]
    out[:, :, 1] = (secuencia[:, :, 1] - cadera[:, None, 1]) / torso[:, None]
    out[:, :, 2] = secuencia[:, :, 2] / torso[:, None]
    return out


# ---------------------------------------------------------------------------
# Red en numpy
# ---------------------------------------------------------------------------

def _sigmoide(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60.0, 60.0)))


@dataclass
class _LSTM:
    """Celda LSTM de Keras: orden de puertas i, f, c, o; tanh / sigmoide."""
    kernel: np.ndarray            # (entrada, 4u)
    recurrente: np.ndarray        # (u, 4u)
    sesgo: np.ndarray             # (4u,)

    def correr(self, x: np.ndarray, mascara: np.ndarray,
               inverso: bool) -> np.ndarray:
        """x: (B, T, F). Devuelve la secuencia de estados (B, T, u).

        Con máscara, un paso enmascarado conserva el estado y repite la salida
        anterior, como hace Keras.
        """
        b, t, _ = x.shape
        u = self.recurrente.shape[0]
        h = np.zeros((b, u), np.float32)
        c = np.zeros((b, u), np.float32)
        salidas = np.zeros((b, t, u), np.float32)
        proy = x @ self.kernel + self.sesgo                    # (B, T, 4u)
        pasos = range(t - 1, -1, -1) if inverso else range(t)
        for k in pasos:
            z = proy[:, k] + h @ self.recurrente
            i = _sigmoide(z[:, :u])
            f = _sigmoide(z[:, u:2 * u])
            g = np.tanh(z[:, 2 * u:3 * u])
            o = _sigmoide(z[:, 3 * u:])
            c_n = f * c + i * g
            h_n = o * np.tanh(c_n)
            m = mascara[:, k:k + 1]
            c = np.where(m, c_n, c)
            h = np.where(m, h_n, h)
            salidas[:, k] = h
        return salidas


class RedBiLSTM:
    """Forward de la BiLSTM de `entrenar_bilstm.py` a partir del `.h5`."""

    def __init__(self, ruta_h5: Path) -> None:
        import h5py  # dependencia opcional: extra [reconocimiento]

        with h5py.File(ruta_h5, "r") as f:
            w = f["model_weights"]

            def lstm(capa: str, sentido: str) -> _LSTM:
                grupo = w[capa][capa]
                sub = next(k for k in grupo if k.startswith(sentido))
                celda = grupo[sub]["lstm_cell"]
                return _LSTM(celda["kernel:0"][()], celda["recurrent_kernel:0"][()],
                             celda["bias:0"][()])

            def densa(capa: str):
                g = w[capa][capa]
                return g["kernel:0"][()], g["bias:0"][()]

            self._capas = [(lstm("bidirectional", "forward"),
                            lstm("bidirectional", "backward")),
                           (lstm("bidirectional_1", "forward"),
                            lstm("bidirectional_1", "backward"))]
            self._densa1 = densa("dense")
            self._densa2 = densa("dense_1")

    def predecir(self, x: np.ndarray) -> np.ndarray:
        """x: (B, 30, 132) ya z-normalizado → probabilidades (B, 4)."""
        mascara = np.any(x != 0.0, axis=-1)                   # Masking(0.0)
        h = x.astype(np.float32)
        for n, (ida, vuelta) in enumerate(self._capas):
            fw = ida.correr(h, mascara, inverso=False)
            bw = vuelta.correr(h, mascara, inverso=True)
            if n == 0:                                         # return_sequences
                h = np.concatenate([fw, bw], axis=-1)
            else:                                              # último estado
                h = np.concatenate([fw[:, -1], bw[:, 0]], axis=-1)
        k, b = self._densa1
        h = np.maximum(h @ k + b, 0.0)
        k, b = self._densa2
        z = h @ k + b
        z = np.exp(z - z.max(axis=-1, keepdims=True))
        return z / z.sum(axis=-1, keepdims=True)


# ---------------------------------------------------------------------------
# Reconocedor en línea
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Sugerencia:
    skill_id: Optional[str]      # None mientras no hay predicción estable
    confianza: float


class ReconocedorBiLSTM:
    """Ventana deslizante de 30 frames + mayoría de votos (como demo_estela)."""

    def __init__(self, directorio_modelo: Path, confianza_minima: float = 0.6,
                 votos: int = 5, cada_n_frames: int = 5) -> None:
        directorio_modelo = Path(directorio_modelo)
        self.red = RedBiLSTM(directorio_modelo / "modelo.h5")
        norm = np.load(directorio_modelo / "normalizacion.npz")
        self._media = norm["media"].astype(np.float32)
        self._desv = norm["desviacion"].astype(np.float32)
        self.clases: List[str] = _leer_clases(directorio_modelo)
        self.confianza_minima = confianza_minima
        self.cada_n_frames = cada_n_frames
        self._buffer: Deque[np.ndarray] = deque(maxlen=VENTANA)
        self._votos: Deque[int] = deque(maxlen=votos)
        self._frames = 0
        self.ultima = Sugerencia(None, 0.0)

    def preparar(self, secuencia: np.ndarray) -> np.ndarray:
        """(30, 33, 4) de imagen → (1, 30, 132) listo para la red."""
        x = normalizar_secuencia(secuencia).reshape(1, VENTANA, -1)
        return (x - self._media) / self._desv

    def agregar(self, landmarks_imagen: Optional[np.ndarray]) -> Sugerencia:
        """Añade un frame (33, 4). Sin persona detectada se vacía la ventana."""
        if landmarks_imagen is None:
            self._buffer.clear()
            return self.ultima
        self._buffer.append(landmarks_imagen)
        self._frames += 1
        if len(self._buffer) < VENTANA or self._frames % self.cada_n_frames:
            return self.ultima
        probs = self.red.predecir(self.preparar(np.stack(self._buffer)))[0]
        idx = int(np.argmax(probs))
        conf = float(probs[idx])
        if conf >= self.confianza_minima:
            self._votos.append(idx)
        if self._votos:
            mas_comun = Counter(self._votos).most_common(1)[0][0]
            self.ultima = Sugerencia(CLASE_A_SKILL.get(self.clases[mas_comun]), conf)
        return self.ultima

    def reiniciar(self) -> None:
        self._buffer.clear()
        self._votos.clear()
        self.ultima = Sugerencia(None, 0.0)


def _leer_clases(directorio: Path) -> List[str]:
    ruta = directorio / "metricas.json"
    if ruta.exists():
        with open(ruta, encoding="utf-8") as f:
            return list(json.load(f)["clases"])
    return sorted(CLASE_A_SKILL)


def accuracy(red: RedBiLSTM, media: np.ndarray, desv: np.ndarray,
             x: np.ndarray, y: Sequence[int]) -> float:
    """Utilidad para validar la red contra un split guardado."""
    probs = red.predecir((x - media) / desv)
    return float(np.mean(np.argmax(probs, axis=-1) == np.asarray(y)))


__all__ = ["ReconocedorBiLSTM", "RedBiLSTM", "Sugerencia", "CLASE_A_SKILL",
           "normalizar_secuencia", "accuracy"]
