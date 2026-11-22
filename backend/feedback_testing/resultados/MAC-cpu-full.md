# Informe 2 — métricas medidas

> **Cifras preliminares.** Medidas en el Mac Studio M2 Ultra del proyecto (tabla de abajo), con vídeos públicos sin anotar. No son sesiones de las participantes. Generado por `python -m feedback_testing.informe2`; no editar a mano.

Convención: `[F]` medido aquí · `[I]` inferencia · `[R]` recomendación · `[?]` pendiente.

## Equipo

| Campo | Valor |
|---|---|
| fecha | 2026-11-22T16:19:36-05:00 |
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
| commit | n/d |
| modelo de pose (corrida principal) | pose_landmarker_full |
| delegado de pose | cpu |
| voz | Piper sin audio (es_MX-claude-high.onnx) |
| precalentado de la voz | 0,6 s antes de medir, sin contar las frases ya sintetizadas al medir el RTF (en la app es en segundo plano al arrancar) |

## Resumen frente a los objetivos

| Métrica | Objetivo | Medido | Estado |
|---|---|---|---|
| p95 de la estimación de pose | ≤ 33 ms | 21,3 ms (modelo full, n = 16131) | **cumple** |
| FPS sostenidos | ≥ 25 fps | mínimo por vídeo 25,0 fps (15 vídeos con fuente ≥ 25 fps, política «último frame») | **cumple** |
| p95 detección → inicio de voz | ≤ 1 s | 0,07 s (n = 17 correcciones habladas; 0 descartadas por esperar más de 1 s; Piper sin audio (es_MX-claude-high.onnx)) | **cumple** |
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
| ZANCADA CHICA DERECHA.mp4 | Zancada atrás estática por pierna | zancada_atras_der | 25,00 | 720x1280 | 12,9 s | sí |
| ZANCADA CHICA IZQUIERDA.mp4 | Zancada atrás estática por pierna | zancada_atras_izq | 25,00 | 720x1280 | 12,8 s | sí |
| der Zancada atrás con Kettlebell Derecha - Ejercicios de la App Malagaentrena.mp4 | Zancada atrás estática por pierna | zancada_atras_der | 24,00 | 1280x720 | 27,3 s |  |
| izq Zancada hacia atrás con peso corporal_ técnica paso a paso.mp4 | Zancada atrás estática por pierna | zancada_atras_izq | 18,00 | 1280x720 | 97,3 s |  |

Excluidos:

- `Abdución de caderas pies/ABDUCCIÓN DE CADERA CON BANDA ELÁSTICA DE PIE.mp4`: abduccion sin lado en el nombre (izq/der)
- `Abdución de caderas pies/Abducción activa de cadera en bipedestación.mp4`: abduccion sin lado en el nombre (izq/der)
- `Abdución de caderas pies/Abducción de cadera de pie con apoyo_ El ejercicio tras un ataque o derrame cerebral.mp4`: abduccion sin lado en el nombre (izq/der)
- `Abdución de caderas pies/izq Aducción de cadera de pie con máquina.mp4`: aducción, no abducción
- `Jumping Jacks/1 hombre.mp4`: duplicado de jumping_jack/1 hombre.mp4
- `Jumping Jacks/2 mujer.mp4`: duplicado de jumping_jack/2 mujer.mp4
- `Jumping Jacks/7 hombre.mp4`: duplicado de jumping_jack/7 hombre.mp4
- `Zancada atrás estática por pierna/videoplayback (1).mp4`: zancada sin lado en el nombre (izq/der)
- `Zancada atrás estática por pierna/videoplayback (2).mp4`: zancada sin lado en el nombre (izq/der)
- `Zancada atrás estática por pierna/videoplayback (3).mp4`: zancada sin lado en el nombre (izq/der)
- `Zancada atrás estática por pierna/videoplayback.mp4`: zancada sin lado en el nombre (izq/der)

## 2. Latencia por etapa (ms) — modelo full, política «último frame», ritmo real

| Etapa | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| pose | 16131 | 15,97 | 14,47 | 21,33 | 45,44 |
| geometria | 15454 | 0,19 | 0,18 | 0,24 | 0,41 |
| segmentacion | 15454 | 0,01 | 0,01 | 0,01 | 0,04 |
| dtw | 15454 | 0,03 | 0,03 | 0,05 | 0,09 |
| decision | 11732 | 0,02 | 0,02 | 0,04 | 0,15 |
| verbalizacion | 25 | 0,08 | 0,08 | 0,10 | 0,11 |
| motor | 11732 | 0,02 | 0,02 | 0,04 | 0,15 |
| total | 15454 | 16,64 | 15,18 | 22,08 | 46,95 |
| procesar (pared) | 16131 | 16,69 | 15,20 | 22,11 | 46,96 |

`total` solo existe en los frames que llegan al motor (con persona y sin pausa); `procesar (pared)` es `Sesion.procesar` entero en todos los frames. `verbalizacion` solo en los frames con mensaje. `motor` = decisión + verbalización.
La primera inferencia de cada estimador (calentamiento, fuera de la medición) tardó 9 ms de mediana.

Pose por ejercicio:

| Ejercicio | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| abduccion_cadera_der | 2538 | 19,10 | 19,60 | 22,05 | 45,44 |
| abduccion_cadera_izq | 803 | 18,68 | 19,50 | 21,89 | 29,59 |
| jumping_jacks | 4025 | 14,09 | 14,00 | 15,41 | 38,36 |
| plancha | 5723 | 14,29 | 14,26 | 15,00 | 28,13 |
| zancada_atras_der | 973 | 15,58 | 15,55 | 17,19 | 27,61 |
| zancada_atras_izq | 2069 | 19,54 | 20,01 | 22,74 | 43,43 |

## 3. FPS sostenidos, frames descartados y retraso acumulado

Retraso por frame = fin de su procesamiento − su marca nominal de llegada (ms). Deriva = pendiente del retraso frente al tiempo (ms por s): ≈ 0 si el sistema da abasto.

### Política «último frame (como `FuenteCamara`)»

| Vídeo | Ejercicio | FPS fuente | FPS sostenidos | Descartados | Retraso p50 | p95 | máx | final | Deriva |
|---|---|---|---|---|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 23,98 | 24,0 | 0 (0,0 %) | 21 | 22 | 44 | 26 | -0,03 |
| 2 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 21 | 22 | 32 | 20 | -0,04 |
| 3 mujer.mp4 | jumping_jacks | 29,97 | 30,0 | 0 (0,0 %) | 20 | 21 | 34 | 20 | -0,00 |
| 4 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 20 | 22 | 34 | 20 | -0,18 |
| 5 hombre.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 20 | 21 | 34 | 20 | -0,11 |
| 6 mujer.mp4 | jumping_jacks | 30,00 | 30,1 | 0 (0,0 %) | 20 | 21 | 35 | 20 | -0,24 |
| 7 hombre.mp4 | jumping_jacks | 59,94 | 59,9 | 0 (0,0 %) | 17 | 18 | 26 | 17 | 0,00 |
| 8 hombre.mp4 | jumping_jacks | 30,00 | 30,0 | 0 (0,0 %) | 20 | 21 | 32 | 20 | -0,01 |
| 9 mujer.mp4 | jumping_jacks | 23,98 | 24,1 | 0 (0,0 %) | 21 | 23 | 33 | 20 | -0,36 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 29,97 | 30,0 | 0 (0,0 %) | 20 | 21 | 38 | 14 | -0,04 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 26 | 28 | 52 | 25 | -0,00 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 26 | 28 | 34 | 26 | 0,01 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | abduccion_cadera_izq | 18,00 | 18,0 | 0 (0,0 %) | 26 | 28 | 36 | 27 | 0,01 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 24,00 | 24,0 | 0 (0,0 %) | 21 | 23 | 36 | 23 | 0,03 |
| PlanchaCorrecta1 (2).mp4 | plancha | 30,00 | 30,0 | 0 (0,0 %) | 20 | 21 | 38 | 21 | 0,00 |
| plancha correcta hombre.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 20 | 21 | 34 | 20 | -0,01 |
| plancha incorrecta 2.mp4 | plancha | 29,97 | 30,2 | 0 (0,0 %) | 20 | 21 | 32 | 21 | -0,59 |
| plancha incorrrecta 1.mp4 | plancha | 29,97 | 30,1 | 0 (0,0 %) | 20 | 21 | 32 | 21 | -0,09 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 20 | 21 | 34 | 20 | -0,00 |
| ZANCADA CHICA DERECHA.mp4 | zancada_atras_der | 25,00 | 25,0 | 0 (0,0 %) | 20 | 21 | 34 | 21 | -0,01 |
| ZANCADA CHICA IZQUIERDA.mp4 | zancada_atras_izq | 25,00 | 25,0 | 0 (0,0 %) | 21 | 22 | 32 | 20 | 0,02 |
| der Zancada atrás con Kettlebell Derecha - Ejercicios de la App Malagaentrena.mp4 | zancada_atras_der | 24,00 | 24,0 | 0 (0,0 %) | 22 | 23 | 32 | 23 | 0,01 |
| izq Zancada hacia atrás con peso corporal_ técnica paso a paso.mp4 | zancada_atras_izq | 18,00 | 18,0 | 0 (0,0 %) | 26 | 29 | 50 | 24 | -0,00 |

Total: 16131 de 16131 frames procesados (0,0 % descartados); retraso p50 20 ms, p95 27 ms, máx 52 ms.

### Política «cola sin descarte (como `FuenteVideo`)»

| Vídeo | Ejercicio | FPS fuente | FPS sostenidos | Descartados | Retraso p50 | p95 | máx | final | Deriva |
|---|---|---|---|---|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 23,98 | 24,0 | 0 (0,0 %) | 20 | 21 | 41 | 21 | 0,04 |
| 2 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 20 | 21 | 33 | 20 | -0,11 |
| 3 mujer.mp4 | jumping_jacks | 29,97 | 30,0 | 0 (0,0 %) | 18 | 19 | 34 | 19 | -0,01 |
| 4 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 20 | 21 | 33 | 20 | -0,08 |
| 5 hombre.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 20 | 21 | 33 | 20 | -0,06 |
| 6 mujer.mp4 | jumping_jacks | 30,00 | 30,1 | 0 (0,0 %) | 18 | 19 | 34 | 19 | -0,18 |
| 7 hombre.mp4 | jumping_jacks | 59,94 | 59,9 | 0 (0,0 %) | 15 | 15 | 25 | 14 | -0,00 |
| 8 hombre.mp4 | jumping_jacks | 30,00 | 30,0 | 0 (0,0 %) | 19 | 19 | 31 | 19 | -0,00 |
| 9 mujer.mp4 | jumping_jacks | 23,98 | 24,1 | 0 (0,0 %) | 20 | 22 | 32 | 21 | -0,19 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 29,97 | 30,0 | 0 (0,0 %) | 18 | 19 | 34 | 13 | 0,01 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 24 | 26 | 55 | 24 | -0,00 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 25 | 28 | 36 | 26 | 0,01 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | abduccion_cadera_izq | 18,00 | 18,0 | 0 (0,0 %) | 26 | 29 | 37 | 26 | -0,00 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 24,00 | 24,1 | 0 (0,0 %) | 20 | 21 | 35 | 21 | -0,01 |
| PlanchaCorrecta1 (2).mp4 | plancha | 30,00 | 30,0 | 0 (0,0 %) | 19 | 19 | 37 | 18 | -0,01 |
| plancha correcta hombre.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 19 | 19 | 32 | 19 | -0,00 |
| plancha incorrecta 2.mp4 | plancha | 29,97 | 30,2 | 0 (0,0 %) | 18 | 19 | 33 | 19 | -0,38 |
| plancha incorrrecta 1.mp4 | plancha | 29,97 | 30,1 | 0 (0,0 %) | 18 | 20 | 31 | 19 | -0,10 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 18 | 19 | 78 | 19 | 0,00 |
| ZANCADA CHICA DERECHA.mp4 | zancada_atras_der | 25,00 | 25,0 | 0 (0,0 %) | 20 | 21 | 32 | 20 | 0,00 |
| ZANCADA CHICA IZQUIERDA.mp4 | zancada_atras_izq | 25,00 | 25,0 | 0 (0,0 %) | 20 | 21 | 33 | 20 | -0,02 |
| der Zancada atrás con Kettlebell Derecha - Ejercicios de la App Malagaentrena.mp4 | zancada_atras_der | 24,00 | 24,0 | 0 (0,0 %) | 20 | 21 | 31 | 21 | -0,00 |
| izq Zancada hacia atrás con peso corporal_ técnica paso a paso.mp4 | zancada_atras_izq | 18,00 | 18,0 | 0 (0,0 %) | 25 | 30 | 55 | 30 | 0,03 |

Total: 16131 de 16131 frames procesados (0,0 % descartados); retraso p50 19 ms, p95 26 ms, máx 78 ms.

`[I]` En vídeo los FPS sostenidos no pueden superar los FPS de la fuente: el objetivo de 25 fps solo se evalúa en vídeos de ≥ 25 fps. La capacidad del equipo (FPS a ritmo máximo) está en la sección 7.

## 4. Detección → inicio de voz

Voz: Piper sin audio (es_MX-claude-high.onnx). Por mensaje: llegada del frame que lo dispara → encolado en `ColaVoz` → empieza a sonar. Política «último frame», ritmo real.

| Tramo (s) | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| frame → encolado | 17 | 0,023 | 0,022 | 0,026 | 0,028 |
| encolado → audio | 17 | 0,020 | 0,000 | 0,049 | 0,049 |
| total (correcciones) | 17 | 0,043 | 0,026 | 0,069 | 0,070 |

Correcciones que esperaron a que terminara otra frase (> 0,1 s en la cola): 0 de 17. Con la cola libre, total p50 0,026 s, p95 0,069 s (n = 17). `[I]` La espera la causan sobre todo el anuncio del ejercicio al empezar y la frase anterior: la cola tiene un solo hueco y no interrumpe lo que está sonando.

Correcciones emitidas: 17; no llegaron a sonar: 0 (0,0 %; por causa: ninguna). «sustituida»: llegó otra más reciente; «aviso»: el hueco lo tenía un aviso; «caducada»: esperó más de 1 s (`MAX_ESPERA_FEEDBACK_S`). El p95 de arriba solo cuenta las que sonaron. Refuerzos: 8.
`[?]` No incluye la latencia del dispositivo de audio.

## 5. Silencios por causa

Frames: 16131; sin persona: 677 (4,2 %); en pausa: 0 (0,0 %) ; evaluados por el motor: 11732.

| Motivo (`MOTIVO_*`) | Frames | % de los evaluados |
|---|---|---|
| `sin_error` | 8765 | 74,7 % |
| `periodo_refractario` | 1371 | 11,7 % |
| `desvanecimiento` | 887 | 7,6 % |
| `evidencia_insuficiente` | 416 | 3,5 % |
| `plano_no_observable` | 268 | 2,3 % |
| corrección | 17 | 0,1 % |
| refuerzo | 8 | 0,1 % |

Por ejercicio (% de los frames evaluados):

| Ejercicio | Frames | Sin persona | En pausa | Evaluados | sin_error | confianza_baja | plano_no_observable | evidencia_insuficiente | refractario | fase_silenciada | otros | mensajes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abduccion_cadera_der | 2538 | 8,1 % | 0,0 % | 1913 | 76,5 % | n/d | n/d | 1,9 % | 18,2 % | n/d | 3,0 % | 6 |
| abduccion_cadera_izq | 803 | 0,0 % | 0,0 % | 422 | 74,4 % | n/d | n/d | 9,2 % | 15,6 % | n/d | 0 % | 3 |
| jumping_jacks | 4025 | 0,3 % | 0,0 % | 2563 | 97,5 % | n/d | n/d | 1,8 % | 0,5 % | n/d | 0 % | 5 |
| plancha | 5723 | 4,4 % | 0,0 % | 4726 | 54,8 % | n/d | 1,3 % | 6,2 % | 20,0 % | n/d | 17,6 % | 8 |
| zancada_atras_der | 973 | 0,0 % | 0,0 % | 506 | 69,8 % | n/d | 30,2 % | n/d | n/d | n/d | 0 % | 0 |
| zancada_atras_izq | 2069 | 10,1 % | 0,0 % | 1602 | 96,6 % | n/d | 3,2 % | n/d | n/d | n/d | 0 % | 3 |

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
| ZANCADA CHICA DERECHA.mp4 (ref.) | zancada_atras_der | 7 | — | 0 |
| ZANCADA CHICA IZQUIERDA.mp4 (ref.) | zancada_atras_izq | 7 | — | 0 |
| der Zancada atrás con Kettlebell Derecha - Ejercicios de la App Malagaentrena.mp4 | zancada_atras_der | 11 | — | 0 |
| izq Zancada hacia atrás con peso corporal_ técnica paso a paso.mp4 | zancada_atras_izq | 29 | — | 3 |

## 7. Variantes de MediaPipe (EXP-004) — ritmo máximo, cola sin descarte

Mismos vídeos, recortados a 30 s. Capacidad = frames / tiempo de pared procesando a ritmo máximo (incluye decodificar el vídeo).

| Modelo | Frames | Pose media | p50 | p95 | máx | Capacidad (fps) | % frames con persona | Reps contadas | Correcciones |
|---|---|---|---|---|---|---|---|---|---|
| lite | 9976 | 8,5 | 8,3 | 8,9 | 21,0 | 106,9 | 97,2 % | 146 | 16 |
| full | 9976 | 13,6 | 13,6 | 14,5 | 27,2 | 68,8 | 97,2 % | 149 | 16 |
| heavy | 9976 | 55,6 | 56,3 | 59,5 | 73,0 | 17,7 | 97,2 % | 150 | 21 |

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
| jumping_jacks | 62 | sin banda | 4012 | 98,0 % | 0,02 | 0,02 | 0,03 | 0,04 | 0,000 | 329 | 0,9 % | n/d | n/d |
| jumping_jacks | 62 | banda 10% (6 fr) | 4012 | 98,0 % | 0,02 | 0,01 | 0,02 | 0,03 | 0,000 | 329 | 8,4 % | 0,918 | 123,68 |
| jumping_jacks | 62 | banda 20% (12 fr) | 4012 | 98,0 % | 0,02 | 0,02 | 0,02 | 0,03 | -0,000 | 329 | 8,2 % | 0,902 | 124,14 |
| abduccion_cadera_der | 55 | sin banda | 2333 | 97,0 % | 0,02 | 0,02 | 0,02 | 0,03 | 0,000 | 205 | 1,9 % | n/d | n/d |
| abduccion_cadera_der | 55 | banda 10% (6 fr) | 2333 | 93,7 % | 0,01 | 0,01 | 0,02 | 0,02 | 0,000 | 205 | 7,5 % | 0,722 | 44,44 |
| abduccion_cadera_der | 55 | banda 20% (11 fr) | 2333 | 93,7 % | 0,02 | 0,02 | 0,02 | 0,02 | 0,000 | 205 | 7,0 % | 0,722 | 34,96 |
| abduccion_cadera_izq | 55 | sin banda | 803 | 69,0 % | 0,02 | 0,02 | 0,02 | 0,03 | 0,000 | 57 | 1,6 % | n/d | n/d |
| abduccion_cadera_izq | 55 | banda 10% (6 fr) | 803 | 69,0 % | 0,01 | 0,01 | 0,02 | 0,02 | 0,000 | 57 | 1,3 % | 0,278 | 11,10 |
| abduccion_cadera_izq | 55 | banda 20% (11 fr) | 803 | 69,0 % | 0,01 | 0,02 | 0,02 | 0,02 | 0,000 | 57 | 1,6 % | 0,019 | 1,38 |
| plancha | — | sin referencia DTW (isométrico o ausente) | | | | | | | | | | | |
| zancada_atras_der | 44 | sin banda | 973 | 97,2 % | 0,02 | 0,02 | 0,02 | 0,03 | 0,000 | 69 | 4,4 % | n/d | n/d |
| zancada_atras_der | 44 | banda 10% (4 fr) | 973 | 97,2 % | 0,01 | 0,01 | 0,01 | 0,02 | 0,000 | 69 | 11,6 % | 0,721 | 54,59 |
| zancada_atras_der | 44 | banda 20% (9 fr) | 973 | 97,2 % | 0,01 | 0,01 | 0,02 | 0,02 | 0,000 | 69 | 9,3 % | 0,698 | 53,47 |
| zancada_atras_izq | 45 | sin banda | 1861 | 99,2 % | 0,02 | 0,02 | 0,02 | 0,03 | 0,000 | 73 | 7,0 % | n/d | n/d |
| zancada_atras_izq | 45 | banda 10% (4 fr) | 1861 | 95,8 % | 0,01 | 0,01 | 0,01 | 0,02 | 0,000 | 65 | 9,2 % | 0,955 | 66,22 |
| zancada_atras_izq | 45 | banda 20% (9 fr) | 1861 | 99,2 % | 0,01 | 0,01 | 0,02 | 0,02 | -0,000 | 73 | 11,1 % | 0,955 | 82,17 |

Latencia según la longitud del prefijo, todos los ejercicios juntos (ms):

| Prefijo (frames) | Variante | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|---|
| 1–15 | sin banda | 3014 | 0,02 | 0,02 | 0,02 | 0,04 |
| 16–30 | sin banda | 2568 | 0,02 | 0,02 | 0,02 | 0,04 |
| 31–60 | sin banda | 3363 | 0,02 | 0,02 | 0,02 | 0,04 |
| 61–120 | sin banda | 300 | 0,02 | 0,02 | 0,02 | 0,03 |
| 121–240 | sin banda | 205 | 0,02 | 0,02 | 0,03 | 0,03 |
| 241–∞ | sin banda | 89 | 0,02 | 0,02 | 0,03 | 0,03 |
| 1–15 | banda 10% | 3142 | 0,01 | 0,01 | 0,02 | 0,03 |
| 16–30 | banda 10% | 2538 | 0,01 | 0,01 | 0,02 | 0,03 |
| 31–60 | banda 10% | 3303 | 0,01 | 0,01 | 0,02 | 0,02 |
| 61–120 | banda 10% | 262 | 0,01 | 0,01 | 0,02 | 0,02 |
| 121–240 | banda 10% | 205 | 0,01 | 0,01 | 0,02 | 0,03 |
| 241–∞ | banda 10% | 89 | 0,01 | 0,01 | 0,02 | 0,02 |
| 1–15 | banda 20% | 3084 | 0,02 | 0,02 | 0,02 | 0,03 |
| 16–30 | banda 20% | 2553 | 0,02 | 0,02 | 0,02 | 0,03 |
| 31–60 | banda 20% | 3333 | 0,02 | 0,02 | 0,02 | 0,03 |
| 61–120 | banda 20% | 275 | 0,02 | 0,02 | 0,02 | 0,03 |
| 121–240 | banda 20% | 205 | 0,01 | 0,01 | 0,02 | 0,02 |
| 241–∞ | banda 20% | 89 | 0,02 | 0,02 | 0,02 | 0,02 |

El DTW es incremental y de final abierto: cada frame actualiza una columna de la matriz en O(m) y se reinicia en cada repetición, así que la latencia no debería crecer con el prefijo (columna «ms por frame de prefijo»). La banda se centra en el instante que tocaría al ritmo de la referencia; las columnas «Δ» comparan cada banda con la variante sin banda.

## 9. Plantilla frente a LLM local (EXP-001, banco sintético)

| Condición | Episodios | M2 aserciones no soportadas | M3 sobrecorrección | M5 determinismo | M7 fallback | Verbalización p50 (ms) | p95 | máx |
|---|---|---|---|---|---|---|---|---|
| A | 163 | 0,0 % (174) | 0,0 % (18) | 100,0 % | 0,0 % | 0,0451 | 0,0647 | 0,0780 |
| F | pendiente de medición en la Mac: llama-server no responde en http://127.0.0.1:8080 (URLError) | | | | | | | |

La M1 real (exactitud de contenido) y la comparación sobre vídeo necesitan las anotaciones (sección 6). La condición F solo puede correr donde haya `llama-server` (la Mac).

## 10. Piper: factor de tiempo real

Voz `es_MX-claude-high.onnx`, 207 frases de `frases_de_rutina` (calentamiento básico). RTF = tiempo de síntesis / duración del audio; < 1 es más rápido que el tiempo real. La primera frase (inicialización) tardó 57 ms y no entra en la tabla.

| Medida | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| síntesis (ms) | 206 | 47,3 | 44,4 | 81,2 | 117,4 |
| duración del audio (s) | 206 | 3,08 | 2,87 | 5,20 | 7,42 |
| RTF | 206 | 0,016 | 0,015 | 0,018 | 0,020 |

## Pendiente de medición

- **exp001_F**: pendiente de medición en la Mac: llama-server no responde en http://127.0.0.1:8080 (URLError)
- **anotaciones**: pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA/backend/datos_locales/anotaciones); las 5 sesiones grabadas aún no existen
- **sesiones reales**: las 5 participantes aún no han grabado la rutina; ninguna cifra de esta página procede de ellas.

