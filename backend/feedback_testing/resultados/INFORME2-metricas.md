# Informe 2 — métricas medidas

> **Cifras preliminares.** Medidas en el equipo de desarrollo indicado abajo, con vídeos públicos sin anotar. No son el hardware final (Mac Studio M2 Ultra) ni sesiones de las participantes. Generado por `python -m feedback_testing.informe2`; no editar a mano.

Convención: `[F]` medido aquí · `[I]` inferencia · `[R]` recomendación · `[?]` pendiente.

## Equipo

| Campo | Valor |
|---|---|
| fecha | 2026-10-12T19:23:51+00:00 |
| so | Linux-6.12.87-x86_64-with-glibc2.40 |
| arquitectura | x86_64 |
| cpu | 12th Gen Intel(R) Core(TM) i5-1235U |
| nucleos_logicos | 12 |
| memoria_gb | 7.5 |
| python | 3.12.14 |
| mediapipe | 1.0.1 |
| numpy | 2.5.2 |
| opencv | 5.0.0.93 |
| piper_tts | 1.8.0 |
| commit | a412696 |
| modelo de pose (corrida principal) | pose_landmarker_full |
| voz | Piper sin audio (es_MX-claude-high.onnx) |
| precalentado de la voz | 2,6 s antes de medir, sin contar las frases ya sintetizadas al medir el RTF (en la app es en segundo plano al arrancar) |

## Resumen frente a los objetivos

| Métrica | Objetivo | Medido | Estado |
|---|---|---|---|
| p95 de la estimación de pose | ≤ 33 ms | 28,7 ms (modelo full, n = 10753) | **cumple** |
| FPS sostenidos | ≥ 25 fps | mínimo por vídeo 23,1 fps (13 vídeos con fuente ≥ 25 fps, política «último frame») | **no cumple** |
| p95 detección → inicio de voz | ≤ 1 s | 3,66 s (n = 21 correcciones habladas; Piper sin audio (es_MX-claude-high.onnx)) | **no cumple** |
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
| 1 mujer.mp4 | marcha_rodillas | marcha_rodillas | 30,00 | 1280x720 | 14,2 s |  |
| 2 mujer.mp4 | marcha_rodillas | marcha_rodillas | 29,97 | 1280x720 | 28,3 s |  |
| 3 mujer.mp4 | marcha_rodillas | marcha_rodillas | 30,00 | 1274x720 | 50,7 s |  |
| 4 hombre.mp4 | marcha_rodillas | marcha_rodillas | 23,98 | 1280x720 | 8,7 s |  |
| 5 hombre.mp4 | marcha_rodillas | marcha_rodillas | 29,97 | 1280x720 | 11,3 s | sí |
| 6 mujer.mp4 | marcha_rodillas | marcha_rodillas | 23,98 | 1280x720 | 16,3 s |  |
| der 876. Abducción de cadera con apoyo en silla.mp4 | Abdución de caderas pies | abduccion_cadera_der | 29,97 | 1280x720 | 10,6 s |  |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | Abdución de caderas pies | abduccion_cadera_der | 18,00 | 1280x720 | 92,3 s |  |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | Abdución de caderas pies | abduccion_cadera_der | 18,00 | 684x566 | 31,3 s | sí |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | Abdución de caderas pies | abduccion_cadera_izq | 18,00 | 684x566 | 31,3 s | sí |
| izquierda abductor.mp4 | Abdución de caderas pies | abduccion_cadera_izq | 24,00 | 1280x720 | 10,0 s |  |
| Ejercicio De Plancha.mp4 | Plancha | plancha | 25,00 | 1280x720 | 34,9 s | sí |

Excluidos:

- `elevacion_brazos/1 mujer.mp4`: carpeta 'elevacion_brazos' fuera de los 4 ejercicios (ADR-005/007)
- `elevacion_brazos/2 hombre.mp4`: carpeta 'elevacion_brazos' fuera de los 4 ejercicios (ADR-005/007)
- `elevacion_brazos/3 hombre.mp4`: carpeta 'elevacion_brazos' fuera de los 4 ejercicios (ADR-005/007)
- `elevacion_brazos/4 mujer.mp4`: carpeta 'elevacion_brazos' fuera de los 4 ejercicios (ADR-005/007)
- `elevacion_brazos/5 hombre.mp4`: carpeta 'elevacion_brazos' fuera de los 4 ejercicios (ADR-005/007)
- `sentadilla/1e2c254b-0d5a-4fd6-a6d4-2681333d927b.mp4`: carpeta 'sentadilla' fuera de los 4 ejercicios (ADR-005/007)
- `sentadilla/2a516b63-bccf-490e-807a-e6102303381f.mp4`: carpeta 'sentadilla' fuera de los 4 ejercicios (ADR-005/007)
- `sentadilla/385c01f2-e604-46d4-a84b-949b733395dd.mp4`: carpeta 'sentadilla' fuera de los 4 ejercicios (ADR-005/007)
- `sentadilla/6dddd176-2460-48cf-bd01-3eaaa0dc754f.mp4`: carpeta 'sentadilla' fuera de los 4 ejercicios (ADR-005/007)
- `sentadilla/71ef5d06-bfea-449b-8ff3-b428ae7dbaa7.mp4`: carpeta 'sentadilla' fuera de los 4 ejercicios (ADR-005/007)
- `sentadilla/7ddd38c8-0649-4092-8ddc-5ce2ba0bd4d1.mp4`: carpeta 'sentadilla' fuera de los 4 ejercicios (ADR-005/007)
- `sentadilla/897f5a21-f1a1-477e-aa8b-11b7ee9378d2.mp4`: carpeta 'sentadilla' fuera de los 4 ejercicios (ADR-005/007)
- `Abdución de caderas pies/Abducción activa de cadera en bipedestación.mp4`: abducción sin lado en el nombre (izq/der)
- `Abdución de caderas pies/Abducción de cadera de pie con apoyo_ El ejercicio tras un ataque o derrame cerebral.mp4`: abducción sin lado en el nombre (izq/der)
- `Abdución de caderas pies/izq Aducción de cadera de pie con máquina.mp4`: aducción, no abducción
- `Jumping Jacks/1 hombre.mp4`: duplicado de jumping_jack/1 hombre.mp4
- `Jumping Jacks/2 mujer.mp4`: duplicado de jumping_jack/2 mujer.mp4
- `Jumping Jacks/7 hombre.mp4`: duplicado de jumping_jack/7 hombre.mp4
- `Marcha rodillas/5 hombre.mp4`: duplicado de marcha_rodillas/5 hombre.mp4
- `Marcha rodillas/6 mujer.mp4`: duplicado de marcha_rodillas/6 mujer.mp4
- `Zancada atrás estática por pierna/der Zancada atrás con Kettlebell Derecha - Ejercicios de la App Malagaentrena.mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)
- `Zancada atrás estática por pierna/izq Zancada hacia atrás con peso corporal_ técnica paso a paso.mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)

## 2. Latencia por etapa (ms) — modelo full, política «último frame», ritmo real

| Etapa | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| pose | 10753 | 19,56 | 18,20 | 28,67 | 117,47 |
| geometria | 9908 | 0,19 | 0,17 | 0,32 | 2,47 |
| segmentacion | 9908 | 0,03 | 0,02 | 0,04 | 0,57 |
| dtw | 9908 | 5,79 | 2,55 | 20,89 | 71,94 |
| decision | 9750 | 0,04 | 0,03 | 0,07 | 0,31 |
| verbalizacion | 28 | 0,12 | 0,11 | 0,21 | 0,25 |
| motor | 9750 | 0,04 | 0,03 | 0,07 | 0,40 |
| total | 9750 | 27,25 | 25,10 | 45,07 | 122,38 |
| procesar (pared) | 10753 | 26,69 | 24,51 | 44,45 | 122,44 |

`total` solo existe en los frames que llegan al motor (con persona y sin pausa); `procesar (pared)` es `Sesion.procesar` entero en todos los frames. `verbalizacion` solo en los frames con mensaje. `motor` = decisión + verbalización.
La primera inferencia de cada estimador (calentamiento, fuera de la medición) tardó 12 ms de mediana.

Pose por ejercicio:

| Ejercicio | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| abduccion_cadera_der | 2472 | 19,46 | 18,61 | 26,74 | 57,66 |
| abduccion_cadera_izq | 747 | 19,66 | 18,86 | 27,56 | 60,15 |
| jumping_jacks | 2966 | 19,27 | 17,58 | 28,30 | 62,59 |
| marcha_rodillas | 3703 | 19,22 | 17,71 | 29,18 | 117,47 |
| plancha | 865 | 22,21 | 20,71 | 36,44 | 113,84 |

## 3. FPS sostenidos, frames descartados y retraso acumulado

Retraso por frame = fin de su procesamiento − su marca nominal de llegada (ms). Deriva = pendiente del retraso frente al tiempo (ms por s): ≈ 0 si el sistema da abasto.

### Política «último frame (como `FuenteCamara`)»

| Vídeo | Ejercicio | FPS fuente | FPS sostenidos | Descartados | Retraso p50 | p95 | máx | final | Deriva |
|---|---|---|---|---|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 23,98 | 24,0 | 0 (0,0 %) | 25 | 35 | 55 | 22 | 0,10 |
| 2 mujer.mp4 | jumping_jacks | 25,00 | 24,7 | 1 (0,7 %) | 25 | 42 | 84 | 73 | 2,21 |
| 3 mujer.mp4 | jumping_jacks | 29,97 | 23,1 | 120 (22,9 %) | 41 | 96 | 120 | 28 | 0,40 |
| 4 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 24 | 34 | 39 | 24 | -0,29 |
| 5 hombre.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 25 | 36 | 52 | 23 | 0,08 |
| 6 mujer.mp4 | jumping_jacks | 30,00 | 30,1 | 0 (0,0 %) | 25 | 41 | 54 | 22 | -0,27 |
| 7 hombre.mp4 | jumping_jacks | 59,94 | 34,3 | 930 (42,7 %) | 39 | 56 | 122 | 54 | 0,19 |
| 8 hombre.mp4 | jumping_jacks | 30,00 | 29,4 | 8 (2,1 %) | 24 | 59 | 83 | 20 | -1,49 |
| 9 mujer.mp4 | jumping_jacks | 23,98 | 24,0 | 0 (0,0 %) | 28 | 40 | 77 | 24 | -0,43 |
| 1 mujer.mp4 | marcha_rodillas | 30,00 | 30,0 | 0 (0,0 %) | 20 | 30 | 51 | 14 | 0,28 |
| 2 mujer.mp4 | marcha_rodillas | 29,97 | 29,6 | 12 (1,4 %) | 21 | 42 | 90 | 27 | -0,16 |
| 3 mujer.mp4 | marcha_rodillas | 30,00 | 29,8 | 12 (0,8 %) | 21 | 36 | 137 | 18 | 0,04 |
| 4 hombre.mp4 | marcha_rodillas | 23,98 | 24,0 | 0 (0,0 %) | 22 | 37 | 51 | 19 | -0,30 |
| 5 hombre.mp4 | marcha_rodillas | 29,97 | 30,0 | 0 (0,0 %) | 20 | 29 | 47 | 26 | 0,02 |
| 6 mujer.mp4 | marcha_rodillas | 23,98 | 24,0 | 0 (0,0 %) | 22 | 33 | 60 | 22 | -0,40 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 29,97 | 23,7 | 66 (20,9 %) | 51 | 89 | 100 | 32 | 5,24 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 28 | 44 | 91 | 22 | -0,09 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 28 | 41 | 56 | 28 | 0,02 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | abduccion_cadera_izq | 18,00 | 18,0 | 0 (0,0 %) | 28 | 38 | 64 | 28 | -0,05 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 24,00 | 18,3 | 56 (23,3 %) | 67 | 111 | 122 | 79 | 8,37 |
| Ejercicio De Plancha.mp4 | plancha | 25,00 | 24,9 | 4 (0,5 %) | 23 | 41 | 151 | 15 | 0,12 |

Total: 10753 de 11962 frames procesados (10,1 % descartados); retraso p50 26 ms, p95 56 ms, máx 151 ms.

### Política «cola sin descarte (como `FuenteVideo`)»

| Vídeo | Ejercicio | FPS fuente | FPS sostenidos | Descartados | Retraso p50 | p95 | máx | final | Deriva |
|---|---|---|---|---|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 23,98 | 24,0 | 0 (0,0 %) | 22 | 34 | 46 | 28 | 0,35 |
| 2 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 23 | 38 | 65 | 25 | -0,82 |
| 3 mujer.mp4 | jumping_jacks | 29,97 | 17,5 | 0 (0,0 %) | 2447 | 12987 | 13207 | 12497 | 949,94 |
| 4 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 22 | 33 | 54 | 24 | -0,22 |
| 5 hombre.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 22 | 35 | 49 | 22 | -0,31 |
| 6 mujer.mp4 | jumping_jacks | 30,00 | 30,1 | 0 (0,0 %) | 22 | 33 | 44 | 24 | 1,34 |
| 7 hombre.mp4 | jumping_jacks | 59,94 | 31,6 | 0 (0,0 %) | 16541 | 31029 | 32513 | 32513 | 890,61 |
| 8 hombre.mp4 | jumping_jacks | 30,00 | 30,0 | 0 (0,0 %) | 26 | 297 | 422 | 22 | -10,50 |
| 9 mujer.mp4 | jumping_jacks | 23,98 | 24,0 | 0 (0,0 %) | 25 | 37 | 46 | 27 | -0,14 |
| 1 mujer.mp4 | marcha_rodillas | 30,00 | 30,0 | 0 (0,0 %) | 17 | 26 | 49 | 14 | 0,26 |
| 2 mujer.mp4 | marcha_rodillas | 29,97 | 30,0 | 0 (0,0 %) | 17 | 24 | 45 | 15 | -0,02 |
| 3 mujer.mp4 | marcha_rodillas | 30,00 | 30,0 | 0 (0,0 %) | 18 | 28 | 94 | 20 | 0,07 |
| 4 hombre.mp4 | marcha_rodillas | 23,98 | 24,0 | 0 (0,0 %) | 24 | 65 | 101 | 17 | 0,77 |
| 5 hombre.mp4 | marcha_rodillas | 29,97 | 30,0 | 0 (0,0 %) | 21 | 414 | 448 | 25 | 15,16 |
| 6 mujer.mp4 | marcha_rodillas | 23,98 | 24,0 | 0 (0,0 %) | 21 | 39 | 83 | 27 | -0,22 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 29,97 | 20,8 | 0 (0,0 %) | 549 | 3987 | 4704 | 4691 | 359,87 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 27 | 39 | 67 | 18 | -0,06 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 28 | 40 | 73 | 36 | 0,01 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | abduccion_cadera_izq | 18,00 | 18,0 | 0 (0,0 %) | 28 | 38 | 69 | 32 | -0,03 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 24,00 | 16,5 | 0 (0,0 %) | 549 | 3985 | 4546 | 4546 | 424,88 |
| Ejercicio De Plancha.mp4 | plancha | 25,00 | 25,0 | 0 (0,0 %) | 19 | 27 | 43 | 17 | 0,00 |

Total: 11962 de 11962 frames procesados (0,0 % descartados); retraso p50 25 ms, p95 23553 ms, máx 32513 ms.

`[I]` En vídeo los FPS sostenidos no pueden superar los FPS de la fuente: el objetivo de 25 fps solo se evalúa en vídeos de ≥ 25 fps. La capacidad del equipo (FPS a ritmo máximo) está en la sección 7.

## 4. Detección → inicio de voz

Voz: Piper sin audio (es_MX-claude-high.onnx). Por mensaje: llegada del frame que lo dispara → encolado en `ColaVoz` → empieza a sonar. Política «último frame», ritmo real.

| Tramo (s) | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| frame → encolado | 21 | 0,031 | 0,025 | 0,052 | 0,093 |
| encolado → audio | 21 | 1,045 | 0,000 | 3,633 | 3,959 |
| total (correcciones) | 21 | 1,076 | 0,035 | 3,657 | 3,984 |

Correcciones que esperaron a que terminara otra frase (> 0,1 s en la cola): 8 de 21. Con la cola libre, total p50 0,027 s, p95 0,043 s (n = 13). `[I]` La espera la causan sobre todo el anuncio del ejercicio al empezar y la frase anterior: la cola tiene un solo hueco y no interrumpe lo que está sonando.

Correcciones emitidas: 21; no llegaron a sonar (sustituidas en la cola o tapadas por un aviso): 0 (0,0 %). Refuerzos: 7.
`[?]` No incluye la latencia del dispositivo de audio.

## 5. Silencios por causa

Frames: 10753; sin persona: 845 (7,9 %); en pausa: 158 (1,5 %) {'inactividad': 20, 'sin_persona': 138}; evaluados por el motor: 9750.

| Motivo (`MOTIVO_*`) | Frames | % de los evaluados |
|---|---|---|
| `sin_error` | 6568 | 67,4 % |
| `plano_no_observable` | 1492 | 15,3 % |
| `periodo_refractario` | 1300 | 13,3 % |
| `evidencia_insuficiente` | 305 | 3,1 % |
| `desvanecimiento` | 57 | 0,6 % |
| corrección | 21 | 0,2 % |
| refuerzo | 7 | 0,1 % |

Por ejercicio (% de los frames evaluados):

| Ejercicio | Frames | Sin persona | En pausa | Evaluados | sin_error | confianza_baja | plano_no_observable | evidencia_insuficiente | refractario | fase_silenciada | otros | mensajes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abduccion_cadera_der | 2472 | 10,8 % | 0,0 % | 2205 | 74,6 % | n/d | 0,0 % | 3,0 % | 19,4 % | n/d | 2,6 % | 8 |
| abduccion_cadera_izq | 747 | 0,8 % | 2,7 % | 721 | 79,6 % | n/d | n/d | 7,6 % | 12,2 % | n/d | 0 % | 4 |
| jumping_jacks | 2966 | 0,4 % | 0,0 % | 2953 | 65,0 % | n/d | 3,6 % | 4,5 % | 26,6 % | n/d | 0 % | 10 |
| marcha_rodillas | 3703 | 12,6 % | 3,7 % | 3098 | 55,1 % | n/d | 44,7 % | n/d | n/d | n/d | 0 % | 5 |
| plancha | 865 | 10,6 % | 0,0 % | 773 | 93,4 % | n/d | n/d | 6,5 % | n/d | n/d | 0 % | 1 |

## 6. Exactitud del feedback frente a anotación humana

**pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA/backend/datos_locales/anotaciones); las 5 sesiones grabadas aún no existen.** Precisión, recobrado, F1, sobrecorrección, mensajes correctos y κ necesitan la hoja de anotación (`estela-anotacion-v1`, ver README).

Aserciones no soportadas (M2 de EXP-001) en los mensajes emitidos sobre los vídeos: 0,0 % (0 de 21 correcciones). No necesita anotación.

**Correcciones en los vídeos de control (descriptivo, no es la sobrecorrección).** EXP-009 §4 trata estos vídeos como ejecuciones supuestamente correctas, pero nadie los ha anotado: una corrección aquí es un candidato a falso positivo, no un falso positivo.

| Vídeo | Ejercicio | Reps contadas | Correcciones (error_id × veces) | Refuerzos |
|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 11 | `codos_flexionados` × 1 | 0 |
| 2 mujer.mp4 | jumping_jacks | 6 | — | 1 |
| 3 mujer.mp4 | jumping_jacks | 6 | `brazos_no_llegan_arriba` × 1, `codos_flexionados` × 1 | 0 |
| 4 mujer.mp4 | jumping_jacks | 5 | — | 0 |
| 5 hombre.mp4 | jumping_jacks | 9 | — | 0 |
| 6 mujer.mp4 | jumping_jacks | 4 | — | 0 |
| 7 hombre.mp4 (ref.) | jumping_jacks | 35 | `brazos_no_llegan_arriba` × 2, `codos_flexionados` × 2 | 0 |
| 8 hombre.mp4 | jumping_jacks | 15 | `brazos_no_llegan_arriba` × 1, `codos_flexionados` × 1 | 0 |
| 9 mujer.mp4 | jumping_jacks | 3 | — | 0 |
| 1 mujer.mp4 | marcha_rodillas | 19 | — | 1 |
| 2 mujer.mp4 | marcha_rodillas | 45 | — | 1 |
| 3 mujer.mp4 | marcha_rodillas | 87 | — | 2 |
| 4 hombre.mp4 | marcha_rodillas | 21 | — | 0 |
| 5 hombre.mp4 (ref.) | marcha_rodillas | 28 | — | 0 |
| 6 mujer.mp4 | marcha_rodillas | 41 | — | 1 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 2 | `cadera_der_sube` × 1, `tronco_inclinado_izq` × 1 | 0 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 26 | `cadera_der_sube` × 4 | 0 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 (ref.) | abduccion_cadera_der | 11 | `cadera_der_sube` × 2 | 0 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 (ref.) | abduccion_cadera_izq | 11 | `cadera_izq_sube` × 2, `tronco_inclinado_der` × 2 | 0 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 1 | — | 0 |
| Ejercicio De Plancha.mp4 (ref.) | plancha | 26 | — | 1 |

## 7. Variantes de MediaPipe (EXP-004) — ritmo máximo, cola sin descarte

Mismos vídeos, recortados a 30 s. Capacidad = frames / tiempo de pared procesando a ritmo máximo (incluye decodificar el vídeo).

| Modelo | Frames | Pose media | p50 | p95 | máx | Capacidad (fps) | % frames con persona | Reps contadas | Correcciones |
|---|---|---|---|---|---|---|---|---|---|
| lite | 9678 | 13,1 | 11,7 | 20,1 | 47,7 | 43,8 | 93,8 % | 312 | 20 |
| full | 9678 | 21,0 | 18,3 | 35,0 | 110,6 | 29,8 | 93,8 % | 322 | 19 |
| heavy | 9678 | 60,3 | 58,0 | 87,1 | 308,6 | 12,4 | 93,8 % | 288 | 22 |

p95 de pose frente al objetivo (≤ 33 ms): lite **cumple**, full **no cumple**, heavy **no cumple**.

Jitter en la plancha mantenida (fase `mantenimiento`, confianza ≥ 0,5): desviación del residuo frente a una media móvil de 15 frames. Es el único tramo quieto de los vídeos; en los demás el temblor se mezcla con el movimiento.

| Modelo | tronco_inclinacion | cabeza_adelantada | alineacion_cadera |
|---|---|---|---|
| lite | 0,081 | 0,256 | 0,001 |
| full | 0,085 | 0,123 | 0,001 |
| heavy | 0,059 | 0,113 | 0,001 |

Unidades: grados en los ángulos; escalas corporales en `alineacion_cadera`.

## 8. DTW clásico frente a banda Sakoe-Chiba (EXP-010)

Réplica fuera de línea de las observaciones de la corrida «cola» (modelo full), con las mismas llamadas que hace la sesión. Banda en frames = fracción × longitud de la referencia (0,10, 0,20).

| Ejercicio | Ref. (frames) | Variante | Frames | Con resultado | Latencia media | p50 | p95 | máx | ms por frame de prefijo | Prefijo máx | progreso = 1 | Δ progreso máx | Δ ángulos_ref máx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jumping_jacks | 61 | clásico | 4012 | 100,0 % | 12,04 | 7,89 | 34,65 | 140,28 | 0,330 | 309 | 100,0 % | n/d | n/d |
| jumping_jacks | 61 | banda 10% (6 fr) | 4012 | 88,3 % | 2,41 | 1,60 | 6,97 | 27,53 | 0,066 | 309 | 100,0 % | 0,000 | 0,00 |
| jumping_jacks | 61 | banda 20% (12 fr) | 4012 | 93,0 % | 4,34 | 2,83 | 12,79 | 39,77 | 0,120 | 309 | 100,0 % | 0,000 | 0,00 |
| marcha_rodillas | 11 | clásico | 3260 | 100,0 % | 0,58 | 0,49 | 1,43 | 4,06 | 0,066 | 47 | 100,0 % | n/d | n/d |
| marcha_rodillas | 11 | banda 10% (1 fr) | 3260 | 68,1 % | 0,14 | 0,13 | 0,33 | 1,33 | 0,016 | 47 | 100,0 % | 0,000 | 0,00 |
| marcha_rodillas | 11 | banda 20% (2 fr) | 3260 | 84,0 % | 0,21 | 0,19 | 0,53 | 2,01 | 0,026 | 47 | 100,0 % | 0,000 | 0,00 |
| abduccion_cadera_der | 57 | clásico | 2272 | 100,0 % | 11,45 | 9,38 | 32,14 | 66,33 | 0,306 | 206 | 100,0 % | n/d | n/d |
| abduccion_cadera_der | 57 | banda 10% (6 fr) | 2272 | 91,2 % | 2,41 | 2,00 | 6,70 | 17,28 | 0,064 | 206 | 100,0 % | 0,000 | 0,00 |
| abduccion_cadera_der | 57 | banda 20% (11 fr) | 2272 | 94,7 % | 4,07 | 3,35 | 11,49 | 27,11 | 0,109 | 206 | 100,0 % | 0,000 | 0,00 |
| abduccion_cadera_izq | 57 | clásico | 797 | 100,0 % | 17,50 | 11,16 | 64,19 | 103,85 | 0,323 | 234 | 100,0 % | n/d | n/d |
| abduccion_cadera_izq | 57 | banda 10% (6 fr) | 797 | 92,5 % | 3,68 | 2,37 | 13,49 | 19,08 | 0,067 | 234 | 100,0 % | 0,000 | 0,00 |
| abduccion_cadera_izq | 57 | banda 20% (11 fr) | 797 | 95,5 % | 6,25 | 3,92 | 23,07 | 41,93 | 0,116 | 234 | 100,0 % | 0,000 | 0,00 |
| plancha | — | sin referencia DTW (isométrico o ausente) | | | | | | | | | | | |

Latencia según la longitud del prefijo, todos los ejercicios juntos (ms):

| Prefijo (frames) | Variante | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|---|
| 1–15 | clásico | 5153 | 1,50 | 0,72 | 4,70 | 8,51 |
| 16–30 | clásico | 2037 | 6,70 | 7,03 | 9,93 | 20,16 |
| 31–60 | clásico | 2332 | 14,21 | 14,03 | 18,97 | 26,91 |
| 61–120 | clásico | 430 | 26,07 | 24,80 | 37,48 | 44,48 |
| 121–240 | clásico | 320 | 56,94 | 55,87 | 76,37 | 140,28 |
| 241–∞ | clásico | 69 | 90,26 | 90,07 | 99,23 | 117,61 |
| 1–15 | banda 10% | 5153 | 0,32 | 0,15 | 1,01 | 2,01 |
| 16–30 | banda 10% | 2037 | 1,40 | 1,48 | 2,03 | 3,53 |
| 31–60 | banda 10% | 2332 | 2,89 | 2,87 | 3,77 | 11,35 |
| 61–120 | banda 10% | 430 | 5,28 | 4,97 | 7,47 | 8,96 |
| 121–240 | banda 10% | 320 | 11,82 | 11,50 | 16,15 | 27,53 |
| 241–∞ | banda 10% | 69 | 18,00 | 17,94 | 19,86 | 21,54 |
| 1–15 | banda 20% | 5153 | 0,53 | 0,24 | 1,71 | 3,36 |
| 16–30 | banda 20% | 2037 | 2,42 | 2,54 | 3,54 | 10,53 |
| 31–60 | banda 20% | 2332 | 5,09 | 5,03 | 6,82 | 11,19 |
| 61–120 | banda 20% | 430 | 9,33 | 8,85 | 13,52 | 16,73 |
| 121–240 | banda 20% | 320 | 20,45 | 19,86 | 27,86 | 41,93 |
| 241–∞ | banda 20% | 69 | 32,86 | 33,03 | 37,26 | 39,77 |

`[F]` Con el DTW actual el camino termina siempre en la última celda (n, m): `progreso` sale 1,0 y `angulos_ref` es el último frame de la referencia en todos los frames con resultado (columna «progreso = 1»). Hoy no cambia ninguna decisión porque ninguna regla usa `desviacion` (EXP-009 §9). La banda no lo corrige: solo recorta celdas. `[R]` Un DTW de extremo abierto (mínimo sobre la última fila) es el paso previo a usar la referencia; queda para el equipo.

`[I]` Si el segmentador no cierra la repetición (antes de la primera, en pausa o sin conteo), el prefijo crece sin límite y el coste del DTW clásico con él.

## 9. Plantilla frente a LLM local (EXP-001, banco sintético)

| Condición | Episodios | M2 aserciones no soportadas | M3 sobrecorrección | M5 determinismo | M7 fallback | Verbalización p50 (ms) | p95 | máx |
|---|---|---|---|---|---|---|---|---|
| A | 100 | 0,0 % (102) | 0,0 % (15) | 100,0 % | 0,0 % | 0,1378 | 0,1760 | 0,2519 |
| F | pendiente de medición en la Mac: llama-server no responde en http://127.0.0.1:8080 (URLError) | | | | | | | |

La M1 real (exactitud de contenido) y la comparación sobre vídeo necesitan las anotaciones (sección 6). La condición F solo puede correr donde haya `llama-server` (la Mac).

## 10. Piper: factor de tiempo real

Voz `es_MX-claude-high.onnx`, 77 frases de `frases_de_rutina` (calentamiento básico). RTF = tiempo de síntesis / duración del audio; < 1 es más rápido que el tiempo real. La primera frase (inicialización) tardó 378 ms y no entra en la tabla.

| Medida | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| síntesis (ms) | 76 | 305,8 | 300,7 | 447,1 | 647,3 |
| duración del audio (s) | 76 | 3,55 | 3,50 | 5,26 | 7,57 |
| RTF | 76 | 0,086 | 0,085 | 0,099 | 0,116 |

## Pendiente de medición

- **exp001_F**: pendiente de medición en la Mac: llama-server no responde en http://127.0.0.1:8080 (URLError)
- **anotaciones**: pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA/backend/datos_locales/anotaciones); las 5 sesiones grabadas aún no existen
- **hardware final**: todas las cifras de tiempo hay que repetirlas en la Mac Studio M2 Ultra.
- **sesiones reales**: las 5 participantes aún no han grabado la rutina; ninguna cifra de esta página procede de ellas.

