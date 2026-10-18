# ESTELA · backend

Todo el Python de ESTELA. La interfaz está en `../frontend/`.

```bash
pip install -e ".[voz,interfaz,dev]"
python scripts/descargar_modelos.py
python -m estela
pytest
```

## Arquitectura

Cada imagen de la cámara pasa por una línea de etapas (pipeline):

```
cámara → pose → geometría → conteo → motor de decisión → verbalizador → voz
                                                                      ↘ interfaz
```

El código se organiza en tres capas. Las flechas indican quién puede importar a quién:

```
adaptadores  ──►  aplicacion  ──►  dominio
(cámara, pose,    (sesión,         (feedback, conteo:
 voz, ventana)     puertos)         la lógica de los ejercicios)
```

| Capa | Carpeta | Qué hay | Puede importar |
|---|---|---|---|
| **Dominio** | `estela/dominio/feedback/` | Contrato de datos, geometría, motor de decisión determinista, verbalizador, skills de los ejercicios | solo la biblioteca estándar |
| | `estela/dominio/conteo/` | Segmentador de fases y conteo de repeticiones | dominio |
| **Aplicación** | `estela/aplicacion/` | `Sesion` (bucle por frame), rutinas, pausas, métricas de latencia, alineador DTW contra la referencia del skill (`dtw.py`) | dominio, numpy |
| | `estela/aplicacion/puertos.py` | Interfaces que la sesión necesita: `Estimador`, `Voz`, `Fuente`, `ResultadoPose` | dominio |
| **Adaptadores** | `estela/adaptadores/captura/` | Cámara y vídeo (OpenCV) | todo |
| | `estela/adaptadores/pose/` | MediaPipe Pose Landmarker | todo |
| | `estela/adaptadores/voz/` | Cola de voz y motores TTS (Piper, voz del sistema) | todo |
| | `estela/adaptadores/llm/` | Verbalizador con LLM local (`llama-server` por HTTP); opcional, solo lo usa EXP-001 | todo |
| | `estela/adaptadores/interfaz/` | Conexión con el frontend: `contrato.py` (JSON), `orquestador.py` (hilo de la sesión), `ventana.py` (pywebview) y `overlay.py` (ventana OpenCV) | todo |
| **Arranque** | `estela/__main__.py` | Crea los adaptadores y se los pasa a la sesión | todo |

`tests/test_arquitectura.py` comprueba estas reglas: si el dominio o la aplicación importan un adaptador o una librería de cámara, pose, voz, ventana o red, el test falla.

**Por qué así.** El dominio y la sesión se prueban sin cámara ni modelos, porque los tests les pasan estimadores y voces falsos. Cambiar MediaPipe por otro modelo de pose, o la voz por otra, solo toca un adaptador.

## Otras carpetas

| Carpeta | Contenido |
|---|---|
| `tests/` | Tests de la aplicación (`tests/feedback/`: del módulo de feedback) |
| `feedback_testing/` | Banco sintético y métricas de EXP-001 y EXP-002 |
| `rutinas/` | Rutinas de entrenamiento (JSON) |
| `scripts/` | Descarga de modelos; `crear_referencia.py` genera la referencia de un ejercicio a partir de un vídeo (`estela/dominio/feedback/skills/referencias/`) |
| `modelos/`, `sesiones/` | Modelos descargados y métricas guardadas (ignorados por git) |
