# Informe 2 — métricas medidas

> **Cifras preliminares.** Medidas en el equipo de desarrollo indicado abajo, con vídeos públicos sin anotar. No son el hardware final (Mac Studio M2 Ultra) ni sesiones de las participantes. Generado por `python -m feedback_testing.informe2`; no editar a mano.

Convención: `[F]` medido aquí · `[I]` inferencia · `[R]` recomendación · `[?]` pendiente.

## Equipo

| Campo | Valor |
|---|---|
| fecha | 2026-11-16T17:20:56-05:00 |
| so | Windows-11-10.0.26300-SP0 |
| arquitectura | AMD64 |
| cpu | Intel64 Family 6 Model 126 Stepping 5, GenuineIntel |
| nucleos_logicos | 8 |
| memoria_gb | n/d |
| python | 3.13.5 |
| mediapipe | 1.1.0 |
| numpy | 2.5.4 |
| opencv | 5.0.0.93 |
| piper_tts | 1.8.0 |
| commit | 2474225 |
| modelo de pose (corrida principal) | pose_landmarker_full |
| voz | Piper sin audio (es_MX-claude-high.onnx) |
| precalentado de la voz | 4,2 s antes de medir, sin contar las frases ya sintetizadas al medir el RTF (en la app es en segundo plano al arrancar) |

## Resumen frente a los objetivos

| Métrica | Objetivo | Medido | Estado |
|---|---|---|---|
| p95 de la estimación de pose | ≤ 33 ms | 53,2 ms (modelo full, n = 10260) | **no cumple** |
| FPS sostenidos | ≥ 25 fps | mínimo por vídeo 16,8 fps (13 vídeos con fuente ≥ 25 fps, política «último frame») | **no cumple** |
| p95 detección → inicio de voz | ≤ 1 s | 0,08 s (n = 19 correcciones habladas; 0 descartadas por esperar más de 1 s; Piper sin audio (es_MX-claude-high.onnx)) | **cumple** |
| Precisión por ejercicio | ≥ 80 % | pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA\backend\datos_locales\anotaciones); las 5 sesiones grabadas aún no existen | **pendiente** |
| Recobrado por ejercicio | ≥ 70 % | pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA\backend\datos_locales\anotaciones); las 5 sesiones grabadas aún no existen | **pendiente** |
| Sobrecorrección en repeticiones correctas | ≤ 10 % | pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA\backend\datos_locales\anotaciones); las 5 sesiones grabadas aún no existen | **pendiente** |
| Mensajes correctos | ≥ 90 % | pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA\backend\datos_locales\anotaciones); las 5 sesiones grabadas aún no existen | **pendiente** |

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
| plancha correcta hombre.mp4 | Plancha | plancha | 29,97 | 1280x720 | 13,8 s | sí |
| plancha incorrecta 2.mp4 | Plancha | plancha | 29,97 | 1280x720 | 1,9 s |  |
| plancha incorrrecta 1.mp4 | Plancha | plancha | 29,97 | 1280x720 | 3,8 s |  |
| PlanchaCorrecta1 (2).mp4 | Plancha | plancha | 30,00 | 1920x1080 | 27,8 s |  |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | Plancha | plancha | 29,97 | 1280x720 | 143,6 s |  |

Excluidos:

- `elevacion_brazos/1 mujer.mp4`: carpeta 'elevacion_brazos' fuera de los 4 ejercicios (ADR-005/007)
- `elevacion_brazos/2 hombre.mp4`: carpeta 'elevacion_brazos' fuera de los 4 ejercicios (ADR-005/007)
- `elevacion_brazos/3 hombre.mp4`: carpeta 'elevacion_brazos' fuera de los 4 ejercicios (ADR-005/007)
- `elevacion_brazos/4 mujer.mp4`: carpeta 'elevacion_brazos' fuera de los 4 ejercicios (ADR-005/007)
- `elevacion_brazos/5 hombre.mp4`: carpeta 'elevacion_brazos' fuera de los 4 ejercicios (ADR-005/007)
- `marcha_rodillas/1 mujer.mp4`: carpeta 'marcha_rodillas' fuera de los 4 ejercicios (ADR-005/007)
- `marcha_rodillas/2 mujer.mp4`: carpeta 'marcha_rodillas' fuera de los 4 ejercicios (ADR-005/007)
- `marcha_rodillas/3 mujer.mp4`: carpeta 'marcha_rodillas' fuera de los 4 ejercicios (ADR-005/007)
- `marcha_rodillas/4 hombre.mp4`: carpeta 'marcha_rodillas' fuera de los 4 ejercicios (ADR-005/007)
- `marcha_rodillas/5 hombre.mp4`: carpeta 'marcha_rodillas' fuera de los 4 ejercicios (ADR-005/007)
- `marcha_rodillas/6 mujer.mp4`: carpeta 'marcha_rodillas' fuera de los 4 ejercicios (ADR-005/007)
- `sentadilla/1e2c254b-0d5a-4fd6-a6d4-2681333d927b.mp4`: carpeta 'sentadilla' fuera de los 4 ejercicios (ADR-005/007)
- `sentadilla/2a516b63-bccf-490e-807a-e6102303381f.mp4`: carpeta 'sentadilla' fuera de los 4 ejercicios (ADR-005/007)
- `sentadilla/385c01f2-e604-46d4-a84b-949b733395dd.mp4`: carpeta 'sentadilla' fuera de los 4 ejercicios (ADR-005/007)
- `sentadilla/6dddd176-2460-48cf-bd01-3eaaa0dc754f.mp4`: carpeta 'sentadilla' fuera de los 4 ejercicios (ADR-005/007)
- `sentadilla/71ef5d06-bfea-449b-8ff3-b428ae7dbaa7.mp4`: carpeta 'sentadilla' fuera de los 4 ejercicios (ADR-005/007)
- `sentadilla/7ddd38c8-0649-4092-8ddc-5ce2ba0bd4d1.mp4`: carpeta 'sentadilla' fuera de los 4 ejercicios (ADR-005/007)
- `sentadilla/897f5a21-f1a1-477e-aa8b-11b7ee9378d2.mp4`: carpeta 'sentadilla' fuera de los 4 ejercicios (ADR-005/007)
- `Abdución de caderas pies/Abducción activa de cadera en bipedestación.mp4`: abducción sin lado en el nombre (izq/der)
- `Abdución de caderas pies/ABDUCCIÓN DE CADERA CON BANDA ELÁSTICA DE PIE.mp4`: abducción sin lado en el nombre (izq/der)
- `Abdución de caderas pies/Abducción de cadera de pie con apoyo_ El ejercicio tras un ataque o derrame cerebral.mp4`: abducción sin lado en el nombre (izq/der)
- `Abdución de caderas pies/izq Aducción de cadera de pie con máquina.mp4`: aducción, no abducción
- `Jumping Jacks/1 hombre.mp4`: duplicado de jumping_jack/1 hombre.mp4
- `Jumping Jacks/2 mujer.mp4`: duplicado de jumping_jack/2 mujer.mp4
- `Jumping Jacks/7 hombre.mp4`: duplicado de jumping_jack/7 hombre.mp4
- `Marcha rodillas/5 hombre.mp4`: carpeta 'Marcha rodillas' fuera de los 4 ejercicios (ADR-005/007)
- `Marcha rodillas/6 mujer.mp4`: carpeta 'Marcha rodillas' fuera de los 4 ejercicios (ADR-005/007)
- `Marcha rodillas/How to do high knees for beginners (online-video-cutter.com).mp4`: carpeta 'Marcha rodillas' fuera de los 4 ejercicios (ADR-005/007)
- `Zancada atrás estática por pierna/der Zancada atrás con Kettlebell Derecha - Ejercicios de la App Malagaentrena.mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)
- `Zancada atrás estática por pierna/izq Zancada hacia atrás con peso corporal_ técnica paso a paso.mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)
- `Zancada atrás estática por pierna/videoplayback (1).mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)
- `Zancada atrás estática por pierna/videoplayback (2).mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)
- `Zancada atrás estática por pierna/videoplayback (3).mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)
- `Zancada atrás estática por pierna/videoplayback.mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)

## 2. Latencia por etapa (ms) — modelo full, política «último frame», ritmo real

| Etapa | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| pose | 10260 | 35,19 | 33,02 | 53,17 | 302,68 |
| geometria | 9801 | 0,98 | 0,83 | 1,65 | 91,93 |
| segmentacion | 9801 | 0,05 | 0,04 | 0,08 | 19,98 |
| dtw | 9801 | 0,13 | 0,12 | 0,33 | 3,13 |
| decision | 6468 | 0,11 | 0,08 | 0,22 | 50,80 |
| verbalizacion | 23 | 0,31 | 0,24 | 0,60 | 0,90 |
| motor | 6468 | 0,12 | 0,08 | 0,24 | 50,81 |
| total | 8716 | 41,53 | 38,71 | 61,35 | 553,53 |
| procesar (pared) | 10260 | 40,63 | 37,94 | 60,26 | 553,65 |

`total` solo existe en los frames que llegan al motor (con persona y sin pausa); `procesar (pared)` es `Sesion.procesar` entero en todos los frames. `verbalizacion` solo en los frames con mensaje. `motor` = decisión + verbalización.
La primera inferencia de cada estimador (calentamiento, fuera de la medición) tardó 24 ms de mediana.

Pose por ejercicio:

| Ejercicio | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| abduccion_cadera_der | 2397 | 35,41 | 33,57 | 53,55 | 137,30 |
| abduccion_cadera_izq | 802 | 32,63 | 31,41 | 45,19 | 78,19 |
| jumping_jacks | 2322 | 38,39 | 36,05 | 61,00 | 113,45 |
| plancha | 4739 | 33,95 | 31,73 | 48,57 | 302,68 |

## 3. FPS sostenidos, frames descartados y retraso acumulado

Retraso por frame = fin de su procesamiento − su marca nominal de llegada (ms). Deriva = pendiente del retraso frente al tiempo (ms por s): ≈ 0 si el sistema da abasto.

### Política «último frame (como `FuenteCamara`)»

| Vídeo | Ejercicio | FPS fuente | FPS sostenidos | Descartados | Retraso p50 | p95 | máx | final | Deriva |
|---|---|---|---|---|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 23,98 | 19,6 | 44 (17,7 %) | 75 | 101 | 128 | 107 | 0,95 |
| 2 mujer.mp4 | jumping_jacks | 25,00 | 21,8 | 17 (11,6 %) | 64 | 89 | 121 | 121 | 3,21 |
| 3 mujer.mp4 | jumping_jacks | 29,97 | 24,7 | 91 (17,3 %) | 55 | 81 | 93 | 69 | -1,70 |
| 4 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 40 | 76 | 80 | 29 | -0,29 |
| 5 hombre.mp4 | jumping_jacks | 25,00 | 24,5 | 4 (2,1 %) | 40 | 75 | 96 | 45 | 2,02 |
| 6 mujer.mp4 | jumping_jacks | 30,00 | 21,3 | 30 (28,6 %) | 63 | 89 | 110 | 61 | -6,12 |
| 7 hombre.mp4 | jumping_jacks | 59,94 | 23,0 | 1339 (61,5 %) | 51 | 79 | 228 | 68 | 0,36 |
| 8 hombre.mp4 | jumping_jacks | 30,00 | 21,2 | 109 (29,1 %) | 63 | 91 | 118 | 58 | 0,41 |
| 9 mujer.mp4 | jumping_jacks | 23,98 | 12,6 | 69 (46,9 %) | 101 | 144 | 168 | 125 | 3,67 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 29,97 | 17,0 | 137 (43,4 %) | 77 | 104 | 152 | 33 | -3,07 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 18,00 | 18,0 | 1 (0,1 %) | 39 | 65 | 113 | 28 | -0,17 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | abduccion_cadera_der | 18,00 | 17,9 | 3 (0,5 %) | 39 | 54 | 208 | 52 | 0,05 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | abduccion_cadera_izq | 18,00 | 18,0 | 0 (0,0 %) | 37 | 52 | 84 | 35 | -0,05 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 24,00 | 23,9 | 1 (0,4 %) | 36 | 59 | 97 | 51 | -0,98 |
| plancha correcta hombre.mp4 | plancha | 29,97 | 25,7 | 58 (14,0 %) | 51 | 77 | 107 | 60 | 1,88 |
| plancha incorrecta 2.mp4 | plancha | 29,97 | 26,4 | 6 (10,5 %) | 53 | 77 | 92 | 60 | -9,52 |
| plancha incorrrecta 1.mp4 | plancha | 29,97 | 27,5 | 9 (7,9 %) | 51 | 74 | 85 | 47 | -4,15 |
| PlanchaCorrecta1 (2).mp4 | plancha | 30,00 | 16,8 | 350 (41,9 %) | 65 | 346 | 1509 | 1036 | 18,49 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 29,97 | 26,1 | 561 (13,0 %) | 53 | 78 | 212 | 23 | -0,06 |

Total: 10260 de 13089 frames procesados (21,6 % descartados); retraso p50 50 ms, p95 83 ms, máx 1509 ms.

### Política «cola sin descarte (como `FuenteVideo`)»

| Vídeo | Ejercicio | FPS fuente | FPS sostenidos | Descartados | Retraso p50 | p95 | máx | final | Deriva |
|---|---|---|---|---|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 23,98 | 24,0 | 0 (0,0 %) | 32 | 80 | 101 | 27 | -1,67 |
| 2 mujer.mp4 | jumping_jacks | 25,00 | 24,9 | 0 (0,0 %) | 34 | 68 | 74 | 67 | 0,66 |
| 3 mujer.mp4 | jumping_jacks | 29,97 | 27,7 | 0 (0,0 %) | 563 | 1389 | 1472 | 1463 | 81,92 |
| 4 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 37 | 86 | 100 | 30 | -5,61 |
| 5 hombre.mp4 | jumping_jacks | 25,00 | 25,0 | 0 (0,0 %) | 35 | 69 | 80 | 42 | -1,72 |
| 6 mujer.mp4 | jumping_jacks | 30,00 | 26,0 | 0 (0,0 %) | 413 | 532 | 568 | 567 | 137,79 |
| 7 hombre.mp4 | jumping_jacks | 59,94 | 27,8 | 0 (0,0 %) | 21545 | 39839 | 41933 | 41933 | 1156,66 |
| 8 hombre.mp4 | jumping_jacks | 30,00 | 25,7 | 0 (0,0 %) | 821 | 1844 | 2130 | 2130 | 143,76 |
| 9 mujer.mp4 | jumping_jacks | 23,98 | 24,0 | 0 (0,0 %) | 36 | 86 | 109 | 31 | -0,56 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 29,97 | 26,3 | 0 (0,0 %) | 914 | 1435 | 1504 | 1484 | 149,22 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 42 | 2795 | 2971 | 36 | -1,38 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | abduccion_cadera_der | 18,00 | 17,7 | 0 (0,0 %) | 44 | 560 | 738 | 505 | 8,05 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | abduccion_cadera_izq | 18,00 | 18,0 | 0 (0,0 %) | 38 | 55 | 100 | 56 | -0,09 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 24,00 | 24,0 | 0 (0,0 %) | 255 | 412 | 455 | 29 | -4,40 |
| plancha correcta hombre.mp4 | plancha | 29,97 | 15,6 | 0 (0,0 %) | 8063 | 12723 | 12786 | 12784 | 1026,33 |
| plancha incorrecta 2.mp4 | plancha | 29,97 | 26,2 | 0 (0,0 %) | 172 | 303 | 306 | 306 | 145,95 |
| plancha incorrrecta 1.mp4 | plancha | 29,97 | 24,8 | 0 (0,0 %) | 393 | 798 | 824 | 824 | 246,68 |
| PlanchaCorrecta1 (2).mp4 | plancha | 30,00 | 19,3 | 0 (0,0 %) | 6813 | 14787 | 15372 | 15372 | 573,76 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 29,97 | 23,5 | 0 (0,0 %) | 29452 | 39516 | 40123 | 39450 | 294,72 |

Total: 13089 de 13089 frames procesados (0,0 % descartados); retraso p50 4914 ms, p95 38369 ms, máx 41933 ms.

`[I]` En vídeo los FPS sostenidos no pueden superar los FPS de la fuente: el objetivo de 25 fps solo se evalúa en vídeos de ≥ 25 fps. La capacidad del equipo (FPS a ritmo máximo) está en la sección 7.

## 4. Detección → inicio de voz

Voz: Piper sin audio (es_MX-claude-high.onnx). Por mensaje: llegada del frame que lo dispara → encolado en `ColaVoz` → empieza a sonar. Política «último frame», ritmo real.

| Tramo (s) | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| frame → encolado | 19 | 0,051 | 0,051 | 0,079 | 0,084 |
| encolado → audio | 19 | 0,000 | 0,000 | 0,001 | 0,001 |
| total (correcciones) | 19 | 0,052 | 0,052 | 0,079 | 0,084 |

Correcciones que esperaron a que terminara otra frase (> 0,1 s en la cola): 0 de 19. Con la cola libre, total p50 0,052 s, p95 0,079 s (n = 19). `[I]` La espera la causan sobre todo el anuncio del ejercicio al empezar y la frase anterior: la cola tiene un solo hueco y no interrumpe lo que está sonando.

Correcciones emitidas: 19; no llegaron a sonar: 0 (0,0 %; por causa: ninguna). «sustituida»: llegó otra más reciente; «aviso»: el hueco lo tenía un aviso; «caducada»: esperó más de 1 s (`MAX_ESPERA_FEEDBACK_S`). El p95 de arriba solo cuenta las que sonaron. Refuerzos: 4.
`[?]` No incluye la latencia del dispositivo de audio.

## 5. Silencios por causa

Frames: 10260; sin persona: 459 (4,5 %); en pausa: 1085 (10,6 %) {'inactividad': 1085}; evaluados por el motor: 6468.

| Motivo (`MOTIVO_*`) | Frames | % de los evaluados |
|---|---|---|
| `sin_error` | 4064 | 62,8 % |
| `periodo_refractario` | 1249 | 19,3 % |
| `desvanecimiento` | 783 | 12,1 % |
| `evidencia_insuficiente` | 319 | 4,9 % |
| `plano_no_observable` | 30 | 0,5 % |
| corrección | 19 | 0,3 % |
| refuerzo | 4 | 0,1 % |

Por ejercicio (% de los frames evaluados):

| Ejercicio | Frames | Sin persona | En pausa | Evaluados | sin_error | confianza_baja | plano_no_observable | evidencia_insuficiente | refractario | fase_silenciada | otros | mensajes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abduccion_cadera_der | 2397 | 8,7 % | 0,0 % | 1879 | 76,4 % | n/d | n/d | 2,0 % | 18,4 % | n/d | 2,9 % | 6 |
| abduccion_cadera_izq | 802 | 0,6 % | 4,4 % | 426 | 74,6 % | n/d | n/d | 6,1 % | 18,5 % | n/d | 0 % | 3 |
| jumping_jacks | 2322 | 0,6 % | 0,0 % | 1300 | 95,0 % | n/d | 0,1 % | 3,5 % | 1,0 % | n/d | 0 % | 5 |
| plancha | 4739 | 4,9 % | 22,2 % | 2863 | 37,6 % | n/d | 1,0 % | 7,3 % | 28,4 % | n/d | 25,4 % | 9 |

## 6. Exactitud del feedback frente a anotación humana

**pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA\backend\datos_locales\anotaciones); las 5 sesiones grabadas aún no existen.** Precisión, recobrado, F1, sobrecorrección, mensajes correctos y κ necesitan la hoja de anotación (`estela-anotacion-v1`, ver README).

Aserciones no soportadas (M2 de EXP-001) en los mensajes emitidos sobre los vídeos: 0,0 % (0 de 19 correcciones). No necesita anotación.

**Correcciones en los vídeos de control (descriptivo, no es la sobrecorrección).** EXP-009 §4 trata estos vídeos como ejecuciones supuestamente correctas, pero nadie los ha anotado: una corrección aquí es un candidato a falso positivo, no un falso positivo.

| Vídeo | Ejercicio | Reps contadas | Correcciones (error_id × veces) | Refuerzos |
|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 7 | `sin_salto` × 1 | 0 |
| 2 mujer.mp4 | jumping_jacks | 6 | — | 0 |
| 3 mujer.mp4 | jumping_jacks | 6 | `codos_flexionados` × 1 | 0 |
| 4 mujer.mp4 | jumping_jacks | 5 | — | 0 |
| 5 hombre.mp4 | jumping_jacks | 7 | — | 0 |
| 6 mujer.mp4 | jumping_jacks | 4 | — | 0 |
| 7 hombre.mp4 (ref.) | jumping_jacks | 35 | — | 2 |
| 8 hombre.mp4 | jumping_jacks | 15 | — | 1 |
| 9 mujer.mp4 | jumping_jacks | 3 | — | 0 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 2 | — | 0 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 26 | `cadera_der_sube` × 4 | 0 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 (ref.) | abduccion_cadera_der | 11 | `cadera_der_sube` × 2 | 0 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 (ref.) | abduccion_cadera_izq | 11 | `cadera_izq_sube` × 1, `tronco_inclinado_der` × 2 | 0 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 1 | — | 0 |
| plancha correcta hombre.mp4 (ref.) | plancha | 12 | `cadera_elevada` × 1, `rodilla_der_flexionada` × 1 | 0 |
| plancha incorrecta 2.mp4 | plancha | 0 | — | 0 |
| plancha incorrrecta 1.mp4 | plancha | 2 | — | 0 |
| PlanchaCorrecta1 (2).mp4 | plancha | 26 | — | 1 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 52 | `cadera_elevada` × 3, `hombros_adelantados` × 2, `rodilla_der_flexionada` × 1 | 0 |

## 7. Variantes de MediaPipe (EXP-004) — ritmo máximo, cola sin descarte

Mismos vídeos, recortados a 30 s. Capacidad = frames / tiempo de pared procesando a ritmo máximo (incluye decodificar el vídeo).

| Modelo | Frames | Pose media | p50 | p95 | máx | Capacidad (fps) | % frames con persona | Reps contadas | Correcciones |
|---|---|---|---|---|---|---|---|---|---|
| lite | 8143 | 27,0 | 24,1 | 46,3 | 288,0 | 26,3 | 97,4 % | 112 | 15 |
| full | 8143 | 36,7 | 34,3 | 57,1 | 152,0 | 21,4 | 97,3 % | 115 | 16 |

p95 de pose frente al objetivo (≤ 33 ms): lite **no cumple**, full **no cumple**.

Jitter en la plancha mantenida (fase `mantenimiento`, confianza ≥ 0,5): desviación del residuo frente a una media móvil de 15 frames. Es el único tramo quieto de los vídeos; en los demás el temblor se mezcla con el movimiento.

| Modelo | tronco_inclinacion | cabeza_adelantada | alineacion_cadera |
|---|---|---|---|
| lite | 0,276 | 0,487 | 0,005 |
| full | 0,224 | 0,580 | 0,004 |

Unidades: grados en los ángulos; escalas corporales en `alineacion_cadera`.

## 8. DTW incremental sin banda frente a banda Sakoe-Chiba (EXP-010)

Réplica fuera de línea de las observaciones de la corrida «cola» (modelo full), con las mismas llamadas que hace la sesión. Banda en frames = fracción × longitud de la referencia (0,10, 0,20).

| Ejercicio | Ref. (frames) | Variante | Frames | Con resultado | Latencia media | p50 | p95 | máx | ms por frame de prefijo | Prefijo máx | progreso = 1 | Δ progreso máx | Δ ángulos_ref máx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jumping_jacks | 62 | sin banda | 4012 | 98,0 % | 0,16 | 0,11 | 0,49 | 1,79 | 0,000 | 328 | 0,9 % | n/d | n/d |
| jumping_jacks | 62 | banda 10% (6 fr) | 4012 | 98,0 % | 0,08 | 0,06 | 0,20 | 1,03 | 0,000 | 328 | 8,4 % | 0,918 | 123,68 |
| jumping_jacks | 62 | banda 20% (12 fr) | 4012 | 98,0 % | 0,08 | 0,06 | 0,19 | 1,10 | 0,000 | 328 | 8,2 % | 0,902 | 124,14 |
| abduccion_cadera_der | 55 | sin banda | 2325 | 97,0 % | 0,19 | 0,13 | 0,55 | 2,29 | -0,000 | 204 | 1,7 % | n/d | n/d |
| abduccion_cadera_der | 55 | banda 10% (6 fr) | 2325 | 94,0 % | 0,11 | 0,07 | 0,28 | 2,61 | -0,000 | 204 | 7,5 % | 0,722 | 45,96 |
| abduccion_cadera_der | 55 | banda 20% (11 fr) | 2325 | 94,0 % | 0,10 | 0,07 | 0,25 | 1,93 | -0,000 | 204 | 7,0 % | 0,722 | 36,48 |
| abduccion_cadera_izq | 55 | sin banda | 797 | 98,6 % | 0,20 | 0,15 | 0,53 | 1,29 | 0,001 | 232 | 1,1 % | n/d | n/d |
| abduccion_cadera_izq | 55 | banda 10% (6 fr) | 797 | 98,6 % | 0,12 | 0,09 | 0,28 | 2,28 | 0,001 | 232 | 0,9 % | 0,481 | 23,75 |
| abduccion_cadera_izq | 55 | banda 20% (11 fr) | 797 | 98,6 % | 0,11 | 0,09 | 0,26 | 1,34 | 0,001 | 232 | 1,1 % | 0,148 | 20,24 |
| plancha | — | sin referencia DTW (isométrico o ausente) | | | | | | | | | | | |

Latencia según la longitud del prefijo, todos los ejercicios juntos (ms):

| Prefijo (frames) | Variante | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|---|
| 1–15 | sin banda | 2189 | 0,17 | 0,11 | 0,50 | 1,70 |
| 16–30 | sin banda | 1765 | 0,17 | 0,11 | 0,52 | 1,79 |
| 31–60 | sin banda | 2295 | 0,18 | 0,12 | 0,53 | 2,29 |
| 61–120 | sin banda | 318 | 0,19 | 0,14 | 0,49 | 1,67 |
| 121–240 | sin banda | 316 | 0,20 | 0,13 | 0,59 | 1,18 |
| 241–∞ | sin banda | 88 | 0,15 | 0,11 | 0,35 | 0,88 |
| 1–15 | banda 10% | 2252 | 0,09 | 0,06 | 0,22 | 1,20 |
| 16–30 | banda 10% | 1750 | 0,09 | 0,06 | 0,23 | 0,78 |
| 31–60 | banda 10% | 2265 | 0,10 | 0,07 | 0,24 | 2,61 |
| 61–120 | banda 10% | 300 | 0,10 | 0,08 | 0,26 | 0,85 |
| 121–240 | banda 10% | 316 | 0,13 | 0,07 | 0,41 | 2,28 |
| 241–∞ | banda 10% | 88 | 0,09 | 0,06 | 0,26 | 0,64 |
| 1–15 | banda 20% | 2252 | 0,09 | 0,06 | 0,22 | 1,36 |
| 16–30 | banda 20% | 1750 | 0,09 | 0,06 | 0,21 | 1,93 |
| 31–60 | banda 20% | 2265 | 0,09 | 0,07 | 0,23 | 0,88 |
| 61–120 | banda 20% | 300 | 0,10 | 0,07 | 0,24 | 0,83 |
| 121–240 | banda 20% | 316 | 0,12 | 0,07 | 0,33 | 1,34 |
| 241–∞ | banda 20% | 88 | 0,07 | 0,06 | 0,18 | 0,25 |

El DTW es incremental y de final abierto: cada frame actualiza una columna de la matriz en O(m) y se reinicia en cada repetición, así que la latencia no debería crecer con el prefijo (columna «ms por frame de prefijo»). La banda se centra en el instante que tocaría al ritmo de la referencia; las columnas «Δ» comparan cada banda con la variante sin banda.

## 9. Plantilla frente a LLM local (EXP-001, banco sintético)

| Condición | Episodios | M2 aserciones no soportadas | M3 sobrecorrección | M5 determinismo | M7 fallback | Verbalización p50 (ms) | p95 | máx |
|---|---|---|---|---|---|---|---|---|
| A | 163 | 0,0 % (174) | 0,0 % (18) | 100,0 % | 0,0 % | 0,2105 | 0,6579 | 1,4734 |
| F | pendiente de medición en la Mac: llama-server no responde en http://127.0.0.1:8080 (URLError) | | | | | | | |

La M1 real (exactitud de contenido) y la comparación sobre vídeo necesitan las anotaciones (sección 6). La condición F solo puede correr donde haya `llama-server` (la Mac).

## 10. Piper: factor de tiempo real

Voz `es_MX-claude-high.onnx`, 110 frases de `frases_de_rutina` (calentamiento básico). RTF = tiempo de síntesis / duración del audio; < 1 es más rápido que el tiempo real. La primera frase (inicialización) tardó 3042 ms y no entra en la tabla.

| Medida | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| síntesis (ms) | 109 | 375,4 | 363,5 | 564,3 | 880,6 |
| duración del audio (s) | 109 | 3,67 | 3,49 | 5,67 | 7,58 |
| RTF | 109 | 0,103 | 0,100 | 0,123 | 0,184 |

## Pendiente de medición

- **exp001_F**: pendiente de medición en la Mac: llama-server no responde en http://127.0.0.1:8080 (URLError)
- **modelo_heavy**: pendiente de medición: falta pose_landmarker_heavy.task (python scripts/descargar_modelos.py --heavy)
- **anotaciones**: pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA\backend\datos_locales\anotaciones); las 5 sesiones grabadas aún no existen
- **hardware final**: todas las cifras de tiempo hay que repetirlas en la Mac Studio M2 Ultra.
- **sesiones reales**: las 5 participantes aún no han grabado la rutina; ninguna cifra de esta página procede de ellas.

