# Referencia rápida de archivos — Estela

| Archivo | Qué es | Para qué sirve | Cuándo ejecutarlo | Qué contiene |
|---|---|---|---|---|
| `.venv/` | Entorno virtual de Python | Aísla las librerías del proyecto (mediapipe, opencv, etc.) del resto del sistema | No se ejecuta; se activa con `source .venv/bin/activate` | Python + librerías instaladas + variables de entorno (LD_LIBRARY_PATH, QT_PLUGIN_PATH, etc.) |
| `pose_landmarker.task` | Modelo de red neuronal ya entrenado (BlazePose) | Es el "cerebro" que detecta los 33 puntos articulares | Nunca se ejecuta directo; lo cargan los scripts de Python | Pesos entrenados, formato binario de MediaPipe |
| `probar_mediapipe_ventana.py` | Script de cámara en vivo, con ventana | Ver en tiempo real los puntos detectados sobre tu cuerpo | Cuando quieras verificar visualmente el encuadre o probar algo en vivo | Abre cámara, dibuja puntos, muestra ventana (cierra con `q`) |
| `probar_mediapipe_video.py` | Script de grabación sin ventana | Guardar un video con los puntos dibujados, para revisar después | Cuando la ventana en vivo falla, o quieres guardar evidencia | Graba 10 segundos y guarda `salida_con_puntos.mp4` |
| `probar_mediapipe_webcam.py` | Script principal de captura de datos | Extraer y guardar los ángulos articulares reales (con filtro de confianza) | Cada vez que quieras capturar una sesión para analizar con DTW | Calcula 8 ángulos, descarta los poco confiables, guarda `angulos_sesion.npz` |
| `angulos_sesion.npz` | Resultado de la última captura | Guarda los ángulos medidos en la última sesión | No se ejecuta; se abre desde Python o el notebook | Series numéricas por articulación (se sobrescribe cada vez que corres `probar_mediapipe_webcam.py`) |
| `salida_con_puntos.mp4` | Video de la última grabación | Revisar visualmente cómo se vio la detección | Se abre con doble clic (reproductor de video) | Video con puntos verdes superpuestos (se sobrescribe cada vez que corres `probar_mediapipe_video.py`) |
| `explorar_angulos.ipynb` | Notebook de Jupyter | Ver y graficar los ángulos guardados en el `.npz` | Después de capturar una sesión, para revisar los datos | Celdas de código: resumen numérico + gráfica de ángulos en el tiempo |
| `notas.md` | Tus notas del proyecto | Registro personal de decisiones, dudas, pendientes | Cuando quieras anotar algo | Texto libre |

## Flujo típico de uso

1. Activar entorno: `source .venv/bin/activate`
2. Verificar encuadre con `probar_mediapipe_ventana.py` (ventana en vivo)
3. Capturar datos reales con `probar_mediapipe_webcam.py` (genera `angulos_sesion.npz`)
4. Revisar resultados en `explorar_angulos.ipynb`
5. (Opcional) Grabar evidencia en video con `probar_mediapipe_video.py`