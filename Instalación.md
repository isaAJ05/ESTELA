# Instalación y despliegue

## 1. Descripción general de la solución

### 1.1 Lenguajes y tecnologías utilizadas

| Componente | Tecnología |
|---|---|
| Lenguaje | Python ≥ 3.10 (validado con 3.14) |
| Estimación de pose | MediaPipe Pose Landmarker (Tasks API, `mediapipe` ≥ 1.0.1), world landmarks |
| Captura y visualización | OpenCV, Pillow (texto con tildes) |
| Feedback | Motor determinista + plantillas en español (`feedback/`, solo biblioteca estándar) |
| Voz | Piper (`piper-tts`), con caída a espeak-ng / `say` o solo texto |
| Reconocimiento de ejercicio (opcional) | BiLSTM entrenada en `PRUEBAS/`, ejecutada en numpy + h5py (sin TensorFlow) |

### 1.2 Componentes de la solución

```
Cámara (hilo) → último frame → Pose Landmarker → geometría (feedback/motor/geometria.py)
  → segmentador de fases y conteo (estela/conteo) → motor de decisión + plantillas (feedback/)
  → cola de voz (hilo) → Piper
```

- `estela/` es la aplicación, y `feedback/` el módulo de retroalimentación (ADR-001).
- Los ejercicios se definen en `feedback/skills/*.json` y las rutinas en `rutinas/*.json`.

## 2. Requisitos previos

### 2.1 Software requerido

- Python 3.10 o superior, con `venv`.
- Una cámara web, que no es necesaria para las pruebas con vídeo.
- Audio. En Linux, `sounddevice` necesita PortAudio; si falta, se usa `pw-play`, `paplay` o `aplay`. En macOS se usa `afplay`.
- Opcional: `espeak-ng`, como voz de respaldo en Linux.
- Conexión a internet **solo** para la instalación y la descarga de modelos. La sesión funciona sin red.

### 2.2 Variables de entorno

No se necesitan. Las rutas de los modelos se resuelven respecto a la raíz del repositorio (`estela/config.py`).

## 3. Instalación para ambiente de desarrollo

### 3.1 Desarrollo sin contenedores

#### 3.1.1 Clonar el repositorio

```bash
git clone <url-del-repositorio> ESTELA && cd ESTELA
```

#### 3.1.2 Instalar dependencias

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[voz,reconocimiento,dev]"
```

Extras opcionales:
- `voz` instala Piper.
- `reconocimiento` instala h5py para la BiLSTM.
- `dev` instala pytest.

#### 3.1.3 Configurar variables de entorno

No aplica.

#### 3.1.4 Ejecutar servicios requeridos

No hay servicios. Solo hay que descargar los modelos una vez:

```bash
python scripts/descargar_modelos.py      # pose lite + full, voz es_MX-claude-high
```

Quedan en `modelos/`, que está ignorado por git.

#### 3.1.5 Iniciar la aplicación

```bash
python -m estela                                   # rutina rutinas/calentamiento_basico.json
python -m estela --ejercicio sentadilla --repeticiones 8
python -m estela --auto                            # + sugerencia BiLSTM
python -m estela --voz texto                       # sin audio
python -m estela --modelo lite                     # pose más rápida y menos precisa
python -m estela --ejercicio sentadilla --video ruta.mp4 --voz texto --sin-ventana --guardar-metricas
```

Teclas: `q` salir · `n` siguiente ejercicio · `r` reiniciar el ejercicio.

### 3.2 Desarrollo con contenedores

No aplica en la v1: la aplicación necesita acceso directo a la cámara y al audio del equipo.

## 4. Despliegue (en caso de ser aplicable)

No aplica: es un prototipo de escritorio de ejecución local.

## 5. Verificación de funcionamiento

```bash
pytest                                             # tests de estela/ (sin cámara ni modelos)
python -m unittest discover -s feedback/tests -t . # tests del módulo de feedback
```

Para una prueba reproducible sin cámara, ejecutar un vídeo del dataset con `--sin-ventana`. El resumen final muestra:
- repeticiones completas e incompletas
- correcciones emitidas
- latencia p50/p95 por etapa

## 6. Solución de problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `No existe el modelo de pose …` | No se descargaron los modelos | `python scripts/descargar_modelos.py` |
| `Voz 'piper' no disponible` | Falta el extra `voz` o la voz | `pip install -e ".[voz]"` y volver a descargar los modelos |
| El contador no avanza | Orientación distinta de la del ejercicio, o baja visibilidad | Seguir el aviso en pantalla («de perfil» / «de frente») y encuadrar el cuerpo entero |
| FPS bajos | Pose *full* en una CPU lenta | `--modelo lite` |
| `mp.solutions` no existe | Scripts antiguos de `PRUEBAS/` | Esos scripts usan la API legacy, que ya no existe en mediapipe 1.x |

## 7. Mantenimiento y actualización

- Para **añadir un ejercicio**, crear un nuevo `feedback/skills/<id>.json` con reglas y una sección `segmentacion` (ver `feedback/skills/ESQUEMA.md`) y añadirlo a una rutina. No se modifica código.
- Para **cambiar la rutina**, editar o crear un JSON en `rutinas/` y pasarlo con `--rutina`.

## 8. Referencias relacionadas

- `docs/decisiones/ADR-001`, `ADR-002` y `ADR-003` (espacio de trabajo del proyecto).
- `feedback/README.md` y `feedback/skills/ESQUEMA.md`.
