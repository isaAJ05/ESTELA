# Informe 2 — métricas medidas

> **Cifras preliminares.** Medidas en el Mac Studio M2 Ultra del proyecto (tabla de abajo), con vídeos públicos sin anotar. No son sesiones de las participantes. Generado por `python -m feedback_testing.informe2`; no editar a mano.

Convención: `[F]` medido aquí · `[I]` inferencia · `[R]` recomendación · `[?]` pendiente.

## Equipo

| Campo | Valor |
|---|---|
| fecha | 2026-11-16T00:51:33-05:00 |
| so | macOS-26.3.2-arm64-arm-64bit-Mach-O |
| arquitectura | arm64 |
| cpu | Apple M2 Ultra |
| nucleos_logicos | 24 |
| memoria_gb | 128.0 |
| python | 3.14.6 |
| mediapipe | 1.2.3 |
| numpy | 2.5.5 |
| opencv | 5.0.0.93 |
| piper_tts | 1.8.0 |
| commit | 50516bc (copia sin git en el Mac) |
| modelo de pose (corrida principal) | pose_landmarker_full |
| voz | Piper sin audio (es_MX-claude-high.onnx) |
| precalentado de la voz | 0,6 s antes de medir, sin contar las frases ya sintetizadas al medir el RTF (en la app es en segundo plano al arrancar) |

## Resumen frente a los objetivos

| Métrica | Objetivo | Medido | Estado |
|---|---|---|---|
| p95 de la estimación de pose | ≤ 33 ms | 20,7 ms (modelo full, n = 13089) | **cumple** |
| FPS sostenidos | ≥ 25 fps | mínimo por vídeo 25,1 fps (13 vídeos con fuente ≥ 25 fps, política «último frame») | **cumple** |
| p95 detección → inicio de voz | ≤ 1 s | 0,03 s (n = 17 correcciones habladas; 0 descartadas por esperar más de 1 s; Piper sin audio (es_MX-claude-high.onnx)) | **cumple** |
| Precisión por ejercicio | ≥ 80 % | pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA/backend/datos_locales/anotaciones); las 5 sesiones grabadas aún no existen | **pendiente** |
| Recobrado por ejercicio | ≥ 70 % | pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA/backend/datos_locales/anotaciones); las 5 sesiones grabadas aún no existen | **pendiente** |
| Sobrecorrección en repeticiones correctas | ≤ 10 % | pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA/backend/datos_locales/anotaciones); las 5 sesiones grabadas aún no existen | **pendiente** |
| Mensajes correctos | ≥ 90 % | pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA/backend/datos_locales/anotaciones); las 5 sesiones grabadas aún no existen | **pendiente** |

Objetivos aceptados por el equipo (`OBJETIVOS_INFORME2` en `feedback_testing/metricas_informe.py`).

## 1. Fuentes

Vídeos públicos de internet (no son personas del proyecto), deduplicados por SHA-1.

| Vídeo | Carpeta | Ejercicio | FPS | Resolución | Duración | Referencia DTW |
|---|---|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jack | jumping_jacks | 23,98 | 1280x720 | 10,4 s |  |
| 2 mujer.mp4 | jumping_jack | jumping_jacks | 25,00 | 720x1280 | 5,9 s |  |
| 3 mujer.mp4 | jumping_jack | jumping_jacks | 29,97 | 1280x720 | 17,5 s |  |
| 4 mujer.mp4 | jumping_jack | jumping_jacks | 25,00 | 1280x720 | 4,6 s |  |
| 5 hombre.mp4 | jumping_jack | jumping_jacks | 25,00 | 1280x720 | 7,5 s |  |
| 6 mujer.mp4 | jumping_jack | jumping_jacks | 30,00 | 720x1280 | 3,5 s |  |
| 7 hombre.mp4 | jumping_jack | jumping_jacks | 59,94 | 720x1280 | 36,4 s | sí |
| 8 hombre.mp4 | jumping_jack | jumping_jacks | 30,00 | 720x1280 | 12,6 s |  |
| 9 mujer.mp4 | jumping_jack | jumping_jacks | 23,98 | 720x1280 | 6,1 s |  |
| der 876. Abducción de cadera con apoyo en silla.mp4 | Abdución de caderas pies | abduccion_cadera_der | 29,97 | 1280x720 | 10,6 s |  |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | Abdución de caderas pies | abduccion_cadera_der | 18,00 | 1280x720 | 92,3 s |  |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | Abdución de caderas pies | abduccion_cadera_der | 18,00 | 684x566 | 31,3 s | sí |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | Abdución de caderas pies | abduccion_cadera_izq | 18,00 | 684x566 | 31,3 s | sí |
| izquierda abductor.mp4 | Abdución de caderas pies | abduccion_cadera_izq | 24,00 | 1280x720 | 10,0 s |  |
| PlanchaCorrecta1 (2).mp4 | Plancha | plancha | 30,00 | 1920x1080 | 27,8 s |  |
| plancha correcta hombre.mp4 | Plancha | plancha | 29,97 | 1280x720 | 13,8 s | sí |
| plancha incorrecta 2.mp4 | Plancha | plancha | 29,97 | 1280x720 | 1,9 s |  |
| plancha incorrrecta 1.mp4 | Plancha | plancha | 29,97 | 1280x720 | 3,8 s |  |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | Plancha | plancha | 29,97 | 1280x720 | 143,6 s |  |

Excluidos:

- `Abdución de caderas pies/ABDUCCIÓN DE CADERA CON BANDA ELÁSTICA DE PIE.mp4`: abducción sin lado en el nombre (izq/der)
- `Abdución de caderas pies/Abducción activa de cadera en bipedestación.mp4`: abducción sin lado en el nombre (izq/der)
- `Abdución de caderas pies/Abducción de cadera de pie con apoyo_ El ejercicio tras un ataque o derrame cerebral.mp4`: abducción sin lado en el nombre (izq/der)
- `Abdución de caderas pies/izq Aducción de cadera de pie con máquina.mp4`: aducción, no abducción
- `Jumping Jacks/1 hombre.mp4`: duplicado de jumping_jack/1 hombre.mp4
- `Jumping Jacks/2 mujer.mp4`: duplicado de jumping_jack/2 mujer.mp4
- `Jumping Jacks/7 hombre.mp4`: duplicado de jumping_jack/7 hombre.mp4
- `Zancada atrás estática por pierna/der Zancada atrás con Kettlebell Derecha - Ejercicios de la App Malagaentrena.mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)
- `Zancada atrás estática por pierna/izq Zancada hacia atrás con peso corporal_ técnica paso a paso.mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)
- `Zancada atrás estática por pierna/videoplayback (1).mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)
- `Zancada atrás estática por pierna/videoplayback (2).mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)
- `Zancada atrás estática por pierna/videoplayback (3).mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)
- `Zancada atrás estática por pierna/videoplayback.mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)

## 2. Latencia por etapa (ms) — modelo full, política «último frame», ritmo real

| Etapa | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| pose | 13089 | 15,42 | 14,23 | 20,69 | 42,28 |
| geometria | 12620 | 0,18 | 0,17 | 0,22 | 0,33 |
| segmentacion | 12620 | 0,01 | 0,01 | 0,01 | 0,02 |
| dtw | 12620 | 0,02 | 0,03 | 0,05 | 0,07 |
| decision | 8499 | 0,02 | 0,02 | 0,04 | 0,12 |
| verbalizacion | 22 | 0,08 | 0,09 | 0,11 | 0,12 |
| motor | 8499 | 0,02 | 0,02 | 0,04 | 0,17 |
| total | 11455 | 16,24 | 14,94 | 21,47 | 43,19 |
| procesar (pared) | 13089 | 16,11 | 14,91 | 21,42 | 43,19 |

`total` solo existe en los frames que llegan al motor (con persona y sin pausa); `procesar (pared)` es `Sesion.procesar` entero en todos los frames. `verbalizacion` solo en los frames con mensaje. `motor` = decisión + verbalización.
La primera inferencia de cada estimador (calentamiento, fuera de la medición) tardó 9 ms de mediana.

Pose por ejercicio:

| Ejercicio | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| abduccion_cadera_der | 2538 | 19,37 | 19,97 | 21,52 | 42,28 |
| abduccion_cadera_izq | 803 | 18,78 | 19,70 | 21,63 | 28,04 |
| jumping_jacks | 4025 | 14,01 | 13,57 | 15,69 | 41,23 |
| plancha | 5723 | 14,19 | 14,17 | 14,79 | 29,88 |

## 3. FPS sostenidos, frames descartados y retraso acumulado

Retraso por frame = fin de su procesamiento − su marca nominal de llegada (ms). Deriva = pendiente del retraso frente al tiempo (ms por s): ≈ 0 si el sistema da abasto.

### Política «último frame (como `FuenteCamara`)»

| Vídeo | Ejercicio | FPS fuente | FPS sostenidos | Descartados | Retraso p50 | p95 | máx | final | Deriva |
|---|---|---|---|---|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 23,98 | 24,0 | 0 (0,0 %) | 21 | 24 | 47 | 21 | 0,03 |
| 2 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 20 | 21 | 33 | 20 | 0,01 |
| 3 mujer.mp4 | jumping_jacks | 29,97 | 30,0 | 0 (0,0 %) | 20 | 21 | 33 | 20 | 0,01 |
| 4 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 20 | 21 | 34 | 20 | -0,31 |
| 5 hombre.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 20 | 22 | 33 | 20 | -0,03 |
| 6 mujer.mp4 | jumping_jacks | 30,00 | 30,1 | 0 (0,0 %) | 20 | 20 | 33 | 20 | -0,22 |
| 7 hombre.mp4 | jumping_jacks | 59,94 | 59,9 | 0 (0,0 %) | 17 | 18 | 25 | 17 | -0,00 |
| 8 hombre.mp4 | jumping_jacks | 30,00 | 30,0 | 0 (0,0 %) | 20 | 20 | 37 | 20 | -0,00 |
| 9 mujer.mp4 | jumping_jacks | 23,98 | 24,1 | 0 (0,0 %) | 22 | 24 | 30 | 22 | 0,57 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 29,97 | 30,0 | 0 (0,0 %) | 20 | 21 | 35 | 14 | -0,00 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 26 | 28 | 48 | 26 | -0,00 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 26 | 27 | 33 | 25 | 0,01 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | abduccion_cadera_izq | 18,00 | 18,0 | 0 (0,0 %) | 26 | 28 | 33 | 26 | -0,01 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 24,00 | 24,1 | 0 (0,0 %) | 21 | 23 | 34 | 20 | 0,01 |
| PlanchaCorrecta1 (2).mp4 | plancha | 30,00 | 30,0 | 0 (0,0 %) | 20 | 21 | 38 | 20 | 0,01 |
| plancha correcta hombre.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 20 | 21 | 32 | 20 | -0,02 |
| plancha incorrecta 2.mp4 | plancha | 29,97 | 30,2 | 0 (0,0 %) | 20 | 20 | 31 | 20 | -0,62 |
| plancha incorrrecta 1.mp4 | plancha | 29,97 | 30,1 | 0 (0,0 %) | 20 | 21 | 32 | 20 | -0,03 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 20 | 21 | 36 | 17 | -0,00 |

Total: 13089 de 13089 frames procesados (0,0 % descartados); retraso p50 20 ms, p95 26 ms, máx 48 ms.

### Política «cola sin descarte (como `FuenteVideo`)»

| Vídeo | Ejercicio | FPS fuente | FPS sostenidos | Descartados | Retraso p50 | p95 | máx | final | Deriva |
|---|---|---|---|---|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 23,98 | 24,0 | 0 (0,0 %) | 20 | 21 | 40 | 21 | 0,06 |
| 2 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 20 | 21 | 32 | 20 | -0,06 |
| 3 mujer.mp4 | jumping_jacks | 29,97 | 30,0 | 0 (0,0 %) | 18 | 19 | 33 | 18 | -0,01 |
| 4 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 20 | 21 | 33 | 20 | -0,07 |
| 5 hombre.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 21 | 22 | 33 | 21 | 0,07 |
| 6 mujer.mp4 | jumping_jacks | 30,00 | 30,1 | 0 (0,0 %) | 18 | 19 | 33 | 18 | -0,16 |
| 7 hombre.mp4 | jumping_jacks | 59,94 | 59,9 | 0 (0,0 %) | 15 | 15 | 26 | 14 | -0,00 |
| 8 hombre.mp4 | jumping_jacks | 30,00 | 30,0 | 0 (0,0 %) | 18 | 19 | 31 | 18 | -0,02 |
| 9 mujer.mp4 | jumping_jacks | 23,98 | 24,1 | 0 (0,0 %) | 20 | 22 | 33 | 22 | 0,09 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 29,97 | 30,0 | 0 (0,0 %) | 18 | 19 | 33 | 13 | 0,02 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 25 | 27 | 46 | 25 | -0,00 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 25 | 27 | 33 | 24 | 0,00 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | abduccion_cadera_izq | 18,00 | 18,0 | 0 (0,0 %) | 26 | 27 | 33 | 25 | 0,01 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 24,00 | 24,0 | 0 (0,0 %) | 20 | 22 | 35 | 21 | 0,02 |
| PlanchaCorrecta1 (2).mp4 | plancha | 30,00 | 30,0 | 0 (0,0 %) | 18 | 19 | 37 | 18 | -0,01 |
| plancha correcta hombre.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 18 | 19 | 32 | 18 | -0,02 |
| plancha incorrecta 2.mp4 | plancha | 29,97 | 30,2 | 0 (0,0 %) | 18 | 19 | 31 | 19 | -0,38 |
| plancha incorrrecta 1.mp4 | plancha | 29,97 | 30,1 | 0 (0,0 %) | 18 | 19 | 31 | 18 | -0,07 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 18 | 19 | 32 | 17 | -0,00 |

Total: 13089 de 13089 frames procesados (0,0 % descartados); retraso p50 18 ms, p95 26 ms, máx 46 ms.

`[I]` En vídeo los FPS sostenidos no pueden superar los FPS de la fuente: el objetivo de 25 fps solo se evalúa en vídeos de ≥ 25 fps. La capacidad del equipo (FPS a ritmo máximo) está en la sección 7.

## 4. Detección → inicio de voz

Voz: Piper sin audio (es_MX-claude-high.onnx). Por mensaje: llegada del frame que lo dispara → encolado en `ColaVoz` → empieza a sonar. Política «último frame», ritmo real.

| Tramo (s) | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| frame → encolado | 17 | 0,023 | 0,024 | 0,026 | 0,028 |
| encolado → audio | 17 | 0,000 | 0,000 | 0,000 | 0,000 |
| total (correcciones) | 17 | 0,023 | 0,024 | 0,027 | 0,028 |

Correcciones que esperaron a que terminara otra frase (> 0,1 s en la cola): 0 de 17. Con la cola libre, total p50 0,024 s, p95 0,027 s (n = 17). `[I]` La espera la causan sobre todo el anuncio del ejercicio al empezar y la frase anterior: la cola tiene un solo hueco y no interrumpe lo que está sonando.

Correcciones emitidas: 17; no llegaron a sonar: 0 (0,0 %; por causa: ninguna). «sustituida»: llegó otra más reciente; «aviso»: el hueco lo tenía un aviso; «caducada»: esperó más de 1 s (`MAX_ESPERA_FEEDBACK_S`). El p95 de arriba solo cuenta las que sonaron. Refuerzos: 5.
`[?]` No incluye la latencia del dispositivo de audio.

## 5. Silencios por causa

Frames: 13089; sin persona: 469 (3,6 %); en pausa: 1165 (8,9 %) {'inactividad': 1165}; evaluados por el motor: 8499.

| Motivo (`MOTIVO_*`) | Frames | % de los evaluados |
|---|---|---|
| `sin_error` | 5761 | 67,8 % |
| `periodo_refractario` | 1371 | 16,1 % |
| `desvanecimiento` | 875 | 10,3 % |
| `evidencia_insuficiente` | 403 | 4,7 % |
| `plano_no_observable` | 67 | 0,8 % |
| corrección | 17 | 0,2 % |
| refuerzo | 5 | 0,1 % |

Por ejercicio (% de los frames evaluados):

| Ejercicio | Frames | Sin persona | En pausa | Evaluados | sin_error | confianza_baja | plano_no_observable | evidencia_insuficiente | refractario | fase_silenciada | otros | mensajes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abduccion_cadera_der | 2538 | 8,1 % | 0,0 % | 1910 | 76,6 % | n/d | n/d | 1,8 % | 18,3 % | n/d | 3,0 % | 6 |
| abduccion_cadera_izq | 803 | 0,0 % | 0,0 % | 425 | 74,6 % | n/d | n/d | 9,2 % | 15,5 % | n/d | 0 % | 3 |
| jumping_jacks | 4025 | 0,3 % | 0,0 % | 2581 | 97,2 % | n/d | 0,2 % | 1,9 % | 0,5 % | n/d | 0 % | 5 |
| plancha | 5723 | 4,4 % | 20,4 % | 3583 | 41,1 % | n/d | 1,8 % | 7,8 % | 26,3 % | n/d | 22,8 % | 8 |

## 6. Exactitud del feedback frente a anotación humana

**pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA/backend/datos_locales/anotaciones); las 5 sesiones grabadas aún no existen.** Precisión, recobrado, F1, sobrecorrección, mensajes correctos y κ necesitan la hoja de anotación (`estela-anotacion-v1`, ver README).

Aserciones no soportadas (M2 de EXP-001) en los mensajes emitidos sobre los vídeos: 0,0 % (0 de 17 correcciones). No necesita anotación.

**Correcciones en los vídeos de control (descriptivo, no es la sobrecorrección).** EXP-009 §4 trata estos vídeos como ejecuciones supuestamente correctas, pero nadie los ha anotado: una corrección aquí es un candidato a falso positivo, no un falso positivo.

| Vídeo | Ejercicio | Reps contadas | Correcciones (error_id × veces) | Refuerzos |
|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 9 | — | 1 |
| 2 mujer.mp4 | jumping_jacks | 6 | — | 0 |
| 3 mujer.mp4 | jumping_jacks | 6 | `codos_flexionados` × 1 | 0 |
| 4 mujer.mp4 | jumping_jacks | 5 | — | 0 |
| 5 hombre.mp4 | jumping_jacks | 8 | — | 0 |
| 6 mujer.mp4 | jumping_jacks | 4 | — | 0 |
| 7 hombre.mp4 (ref.) | jumping_jacks | 35 | — | 2 |
| 8 hombre.mp4 | jumping_jacks | 15 | — | 1 |
| 9 mujer.mp4 | jumping_jacks | 3 | — | 0 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 2 | — | 0 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 26 | `cadera_der_sube` × 4 | 0 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 (ref.) | abduccion_cadera_der | 11 | `cadera_der_sube` × 2 | 0 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 (ref.) | abduccion_cadera_izq | 11 | `cadera_izq_sube` × 2, `tronco_inclinado_der` × 1 | 0 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 0 | — | 0 |
| PlanchaCorrecta1 (2).mp4 | plancha | 26 | — | 1 |
| plancha correcta hombre.mp4 (ref.) | plancha | 12 | `cadera_elevada` × 1 | 0 |
| plancha incorrecta 2.mp4 | plancha | 0 | — | 0 |
| plancha incorrrecta 1.mp4 | plancha | 2 | — | 0 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 52 | `cadera_elevada` × 3, `hombros_adelantados` × 2, `rodilla_der_flexionada` × 1 | 0 |

## 7. Variantes de MediaPipe (EXP-004) — ritmo máximo, cola sin descarte

Mismos vídeos, recortados a 30 s. Capacidad = frames / tiempo de pared procesando a ritmo máximo (incluye decodificar el vídeo).

| Modelo | Frames | Pose media | p50 | p95 | máx | Capacidad (fps) | % frames con persona | Reps contadas | Correcciones |
|---|---|---|---|---|---|---|---|---|---|
| lite | 8143 | 8,4 | 8,3 | 8,7 | 20,6 | 107,4 | 97,4 % | 112 | 15 |
| full | 8143 | 13,6 | 13,6 | 14,0 | 26,4 | 69,1 | 97,4 % | 115 | 16 |
| heavy | 8143 | 55,8 | 56,9 | 58,4 | 72,4 | 17,6 | 97,4 % | 116 | 20 |

p95 de pose frente al objetivo (≤ 33 ms): lite **cumple**, full **cumple**, heavy **no cumple**.

Jitter en la plancha mantenida (fase `mantenimiento`, confianza ≥ 0,5): desviación del residuo frente a una media móvil de 15 frames. Es el único tramo quieto de los vídeos; en los demás el temblor se mezcla con el movimiento.

| Modelo | tronco_inclinacion | cabeza_adelantada | alineacion_cadera |
|---|---|---|---|
| lite | 0,281 | 0,477 | 0,006 |
| full | 0,198 | 0,595 | 0,004 |
| heavy | 0,196 | 0,604 | 0,004 |

Unidades: grados en los ángulos; escalas corporales en `alineacion_cadera`.

## 8. DTW incremental sin banda frente a banda Sakoe-Chiba (EXP-010)

Réplica fuera de línea de las observaciones de la corrida «cola» (modelo full), con las mismas llamadas que hace la sesión. Banda en frames = fracción × longitud de la referencia (0,10, 0,20).

| Ejercicio | Ref. (frames) | Variante | Frames | Con resultado | Latencia media | p50 | p95 | máx | ms por frame de prefijo | Prefijo máx | progreso = 1 | Δ progreso máx | Δ ángulos_ref máx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jumping_jacks | 62 | sin banda | 4012 | 98,0 % | 0,02 | 0,02 | 0,02 | 0,06 | 0,000 | 329 | 0,9 % | n/d | n/d |
| jumping_jacks | 62 | banda 10% (6 fr) | 4012 | 98,0 % | 0,02 | 0,02 | 0,02 | 0,02 | 0,000 | 329 | 8,4 % | 0,918 | 123,68 |
| jumping_jacks | 62 | banda 20% (12 fr) | 4012 | 98,0 % | 0,02 | 0,02 | 0,02 | 0,03 | -0,000 | 329 | 8,2 % | 0,902 | 124,14 |
| abduccion_cadera_der | 55 | sin banda | 2333 | 97,0 % | 0,02 | 0,02 | 0,02 | 0,03 | 0,000 | 205 | 1,9 % | n/d | n/d |
| abduccion_cadera_der | 55 | banda 10% (6 fr) | 2333 | 93,7 % | 0,01 | 0,02 | 0,02 | 0,02 | 0,000 | 205 | 7,5 % | 0,722 | 44,44 |
| abduccion_cadera_der | 55 | banda 20% (11 fr) | 2333 | 93,7 % | 0,02 | 0,02 | 0,02 | 0,02 | 0,000 | 205 | 7,0 % | 0,722 | 34,96 |
| abduccion_cadera_izq | 55 | sin banda | 803 | 69,0 % | 0,02 | 0,02 | 0,02 | 0,03 | 0,000 | 57 | 1,6 % | n/d | n/d |
| abduccion_cadera_izq | 55 | banda 10% (6 fr) | 803 | 69,0 % | 0,01 | 0,02 | 0,02 | 0,02 | 0,000 | 57 | 1,3 % | 0,278 | 11,10 |
| abduccion_cadera_izq | 55 | banda 20% (11 fr) | 803 | 69,0 % | 0,01 | 0,02 | 0,02 | 0,02 | 0,000 | 57 | 1,6 % | 0,019 | 1,38 |
| plancha | — | sin referencia DTW (isométrico o ausente) | | | | | | | | | | | |

Latencia según la longitud del prefijo, todos los ejercicios juntos (ms):

| Prefijo (frames) | Variante | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|---|
| 1–15 | sin banda | 2174 | 0,02 | 0,02 | 0,02 | 0,06 |
| 16–30 | sin banda | 1750 | 0,02 | 0,02 | 0,02 | 0,03 |
| 31–60 | sin banda | 2264 | 0,02 | 0,02 | 0,02 | 0,03 |
| 61–120 | sin banda | 265 | 0,02 | 0,02 | 0,02 | 0,03 |
| 121–240 | sin banda | 205 | 0,02 | 0,02 | 0,02 | 0,03 |
| 241–∞ | sin banda | 89 | 0,02 | 0,02 | 0,03 | 0,03 |
| 1–15 | banda 10% | 2244 | 0,02 | 0,02 | 0,02 | 0,02 |
| 16–30 | banda 10% | 1735 | 0,02 | 0,02 | 0,02 | 0,02 |
| 31–60 | banda 10% | 2234 | 0,02 | 0,02 | 0,02 | 0,02 |
| 61–120 | banda 10% | 240 | 0,01 | 0,01 | 0,02 | 0,02 |
| 121–240 | banda 10% | 205 | 0,01 | 0,01 | 0,02 | 0,02 |
| 241–∞ | banda 10% | 89 | 0,01 | 0,01 | 0,02 | 0,02 |
| 1–15 | banda 20% | 2244 | 0,02 | 0,02 | 0,02 | 0,03 |
| 16–30 | banda 20% | 1735 | 0,02 | 0,02 | 0,02 | 0,03 |
| 31–60 | banda 20% | 2234 | 0,02 | 0,02 | 0,02 | 0,02 |
| 61–120 | banda 20% | 240 | 0,02 | 0,02 | 0,02 | 0,02 |
| 121–240 | banda 20% | 205 | 0,02 | 0,02 | 0,02 | 0,02 |
| 241–∞ | banda 20% | 89 | 0,02 | 0,02 | 0,02 | 0,02 |

El DTW es incremental y de final abierto: cada frame actualiza una columna de la matriz en O(m) y se reinicia en cada repetición, así que la latencia no debería crecer con el prefijo (columna «ms por frame de prefijo»). La banda se centra en el instante que tocaría al ritmo de la referencia; las columnas «Δ» comparan cada banda con la variante sin banda.

## 9. Plantilla frente a LLM local (EXP-001, banco sintético)

| Condición | Episodios | M2 aserciones no soportadas | M3 sobrecorrección | M5 determinismo | M7 fallback | Verbalización p50 (ms) | p95 | máx |
|---|---|---|---|---|---|---|---|---|
| A | 163 | 0,0 % (174) | 0,0 % (18) | 100,0 % | 0,0 % | 0,0531 | 0,0686 | 0,0753 |
| F | pendiente de medición en la Mac: llama-server no responde en http://127.0.0.1:8080 (URLError) | | | | | | | |

La M1 real (exactitud de contenido) y la comparación sobre vídeo necesitan las anotaciones (sección 6). La condición F solo puede correr donde haya `llama-server` (la Mac).

## 10. Piper: factor de tiempo real

Voz `es_MX-claude-high.onnx`, 110 frases de `frases_de_rutina` (calentamiento básico). RTF = tiempo de síntesis / duración del audio; < 1 es más rápido que el tiempo real. La primera frase (inicialización) tardó 96 ms y no entra en la tabla.

| Medida | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| síntesis (ms) | 109 | 55,3 | 52,6 | 85,3 | 125,2 |
| duración del audio (s) | 109 | 3,66 | 3,54 | 5,67 | 7,50 |
| RTF | 109 | 0,015 | 0,015 | 0,017 | 0,019 |

## Pendiente de medición

- **exp001_F**: pendiente de medición en la Mac: llama-server no responde en http://127.0.0.1:8080 (URLError)
- **anotaciones**: pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA/backend/datos_locales/anotaciones); las 5 sesiones grabadas aún no existen
- **hardware final**: todas las cifras de tiempo hay que repetirlas en la Mac Studio M2 Ultra.
- **sesiones reales**: las 5 participantes aún no han grabado la rutina; ninguna cifra de esta página procede de ellas.

