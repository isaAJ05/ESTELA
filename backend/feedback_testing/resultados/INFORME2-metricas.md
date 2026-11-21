# Informe 2 — métricas medidas

> **Cifras preliminares.** Medidas en el equipo de desarrollo indicado abajo, con vídeos públicos sin anotar. No son el hardware final (Mac Studio M2 Ultra) ni sesiones de las participantes. Generado por `python -m feedback_testing.informe2`; no editar a mano.

Convención: `[F]` medido aquí · `[I]` inferencia · `[R]` recomendación · `[?]` pendiente.

## Equipo

| Campo | Valor |
|---|---|
| fecha | 2026-11-20T21:32:56-05:00 |
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
| commit | 71f4b72 |
| modelo de pose (corrida principal) | pose_landmarker_full |
| voz | Piper sin audio (es_MX-claude-high.onnx) |
| precalentado de la voz | 4,2 s antes de medir, sin contar las frases ya sintetizadas al medir el RTF (en la app es en segundo plano al arrancar) |

## Resumen frente a los objetivos

| Métrica | Objetivo | Medido | Estado |
|---|---|---|---|
| p95 de la estimación de pose | ≤ 33 ms | 82,5 ms (modelo full, n = 8359) | **no cumple** |
| FPS sostenidos | ≥ 25 fps | mínimo por vídeo 13,3 fps (13 vídeos con fuente ≥ 25 fps, política «último frame») | **no cumple** |
| p95 detección → inicio de voz | ≤ 1 s | 0,86 s (n = 17 correcciones habladas; 0 descartadas por esperar más de 1 s; Piper sin audio (es_MX-claude-high.onnx)) | **cumple** |
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
- `Zancada atrás estática por pierna/ZANCADA CHICA DERECHA.mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)
- `Zancada atrás estática por pierna/ZANCADA CHICA IZQUIERDA.mp4`: carpeta 'Zancada atrás estática por pierna' fuera de los 4 ejercicios (ADR-005/007)

## 2. Latencia por etapa (ms) — modelo full, política «último frame», ritmo real

| Etapa | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| pose | 8359 | 43,34 | 35,61 | 82,50 | 2379,71 |
| geometria | 7891 | 1,24 | 0,88 | 2,49 | 350,57 |
| segmentacion | 7891 | 0,06 | 0,04 | 0,11 | 5,89 |
| dtw | 7891 | 0,16 | 0,15 | 0,37 | 20,76 |
| decision | 5364 | 0,12 | 0,07 | 0,29 | 7,08 |
| verbalizacion | 21 | 0,43 | 0,36 | 0,85 | 1,58 |
| motor | 5364 | 0,12 | 0,08 | 0,30 | 7,08 |
| total | 7462 | 47,99 | 40,90 | 86,82 | 639,63 |
| procesar (pared) | 8359 | 49,73 | 40,88 | 95,17 | 2702,87 |

`total` solo existe en los frames que llegan al motor (con persona y sin pausa); `procesar (pared)` es `Sesion.procesar` entero en todos los frames. `verbalizacion` solo en los frames con mensaje. `motor` = decisión + verbalización.
La primera inferencia de cada estimador (calentamiento, fuera de la medición) tardó 27 ms de mediana.

Pose por ejercicio:

| Ejercicio | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| abduccion_cadera_der | 2466 | 33,15 | 30,76 | 53,26 | 167,82 |
| abduccion_cadera_izq | 672 | 42,93 | 35,76 | 82,33 | 200,92 |
| jumping_jacks | 2337 | 37,63 | 34,63 | 61,22 | 179,12 |
| plancha | 2884 | 56,78 | 42,91 | 119,80 | 2379,71 |

## 3. FPS sostenidos, frames descartados y retraso acumulado

Retraso por frame = fin de su procesamiento − su marca nominal de llegada (ms). Deriva = pendiente del retraso frente al tiempo (ms por s): ≈ 0 si el sistema da abasto.

### Política «último frame (como `FuenteCamara`)»

| Vídeo | Ejercicio | FPS fuente | FPS sostenidos | Descartados | Retraso p50 | p95 | máx | final | Deriva |
|---|---|---|---|---|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 23,98 | 21,8 | 22 (8,9 %) | 54 | 99 | 116 | 84 | 0,38 |
| 2 mujer.mp4 | jumping_jacks | 25,00 | 14,8 | 59 (40,4 %) | 89 | 120 | 169 | 96 | 1,09 |
| 3 mujer.mp4 | jumping_jacks | 29,97 | 20,9 | 159 (30,3 %) | 63 | 102 | 207 | 50 | -2,18 |
| 4 mujer.mp4 | jumping_jacks | 25,00 | 24,4 | 3 (2,6 %) | 40 | 79 | 90 | 32 | -3,24 |
| 5 hombre.mp4 | jumping_jacks | 25,00 | 24,9 | 1 (0,5 %) | 39 | 74 | 94 | 28 | -2,62 |
| 6 mujer.mp4 | jumping_jacks | 30,00 | 27,4 | 9 (8,6 %) | 53 | 73 | 84 | 43 | -2,12 |
| 7 hombre.mp4 | jumping_jacks | 59,94 | 22,0 | 1377 (63,3 %) | 53 | 81 | 154 | 60 | -0,20 |
| 8 hombre.mp4 | jumping_jacks | 30,00 | 25,4 | 57 (15,2 %) | 56 | 77 | 104 | 51 | -0,44 |
| 9 mujer.mp4 | jumping_jacks | 23,98 | 23,8 | 1 (0,7 %) | 38 | 71 | 88 | 33 | -2,35 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 29,97 | 28,1 | 20 (6,3 %) | 49 | 70 | 78 | 29 | 0,47 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 18,00 | 17,5 | 50 (3,0 %) | 38 | 101 | 251 | 31 | 0,28 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | abduccion_cadera_der | 18,00 | 17,9 | 2 (0,4 %) | 36 | 54 | 231 | 32 | -0,21 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | abduccion_cadera_izq | 18,00 | 17,7 | 9 (1,6 %) | 38 | 81 | 202 | 50 | 0,87 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 24,00 | 11,7 | 122 (50,8 %) | 100 | 219 | 270 | 99 | 0,19 |
| plancha correcta hombre.mp4 | plancha | 29,97 | 23,5 | 89 (21,4 %) | 60 | 81 | 98 | 42 | -0,47 |
| plancha incorrecta 2.mp4 | plancha | 29,97 | 21,0 | 17 (29,8 %) | 66 | 83 | 85 | 39 | -2,17 |
| plancha incorrrecta 1.mp4 | plancha | 29,97 | 22,0 | 29 (25,4 %) | 62 | 94 | 111 | 90 | 4,32 |
| PlanchaCorrecta1 (2).mp4 | plancha | 30,00 | 18,6 | 316 (37,8 %) | 72 | 97 | 255 | 51 | -0,14 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 29,97 | 13,3 | 2388 (55,5 %) | 76 | 271 | 4509 | 25 | 0,53 |

Total: 8359 de 13089 frames procesados (36,1 % descartados); retraso p50 53 ms, p95 123 ms, máx 4509 ms.

### Política «cola sin descarte (como `FuenteVideo`)»

| Vídeo | Ejercicio | FPS fuente | FPS sostenidos | Descartados | Retraso p50 | p95 | máx | final | Deriva |
|---|---|---|---|---|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 23,98 | 23,0 | 0 (0,0 %) | 210 | 650 | 666 | 500 | 66,88 |
| 2 mujer.mp4 | jumping_jacks | 25,00 | 22,0 | 0 (0,0 %) | 75 | 847 | 858 | 846 | 173,47 |
| 3 mujer.mp4 | jumping_jacks | 29,97 | 24,0 | 0 (0,0 %) | 1888 | 4054 | 4358 | 4358 | 243,11 |
| 4 mujer.mp4 | jumping_jacks | 25,00 | 21,5 | 0 (0,0 %) | 93 | 668 | 781 | 781 | 148,60 |
| 5 hombre.mp4 | jumping_jacks | 25,00 | 23,7 | 0 (0,0 %) | 203 | 453 | 467 | 447 | 50,59 |
| 6 mujer.mp4 | jumping_jacks | 30,00 | 24,5 | 0 (0,0 %) | 492 | 783 | 825 | 825 | 220,74 |
| 7 hombre.mp4 | jumping_jacks | 59,94 | 21,6 | 0 (0,0 %) | 32792 | 61569 | 64406 | 64406 | 1791,96 |
| 8 hombre.mp4 | jumping_jacks | 30,00 | 22,7 | 0 (0,0 %) | 1751 | 3782 | 4039 | 4039 | 278,37 |
| 9 mujer.mp4 | jumping_jacks | 23,98 | 22,7 | 0 (0,0 %) | 413 | 497 | 504 | 381 | 85,16 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 29,97 | 23,7 | 0 (0,0 %) | 828 | 2477 | 2797 | 2797 | 276,72 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 18,00 | 6,1 | 0 (0,0 %) | 65322 | 172805 | 178597 | 178597 | 2179,12 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | abduccion_cadera_der | 18,00 | 7,9 | 0 (0,0 %) | 26966 | 39857 | 40487 | 40487 | 1003,46 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | abduccion_cadera_izq | 18,00 | 10,3 | 0 (0,0 %) | 14773 | 22523 | 23684 | 23684 | 692,87 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 24,00 | 10,8 | 0 (0,0 %) | 8078 | 11735 | 12229 | 12229 | 1072,61 |
| plancha correcta hombre.mp4 | plancha | 29,97 | 11,8 | 0 (0,0 %) | 13802 | 20975 | 21426 | 21426 | 1514,64 |
| plancha incorrecta 2.mp4 | plancha | 29,97 | 16,5 | 0 (0,0 %) | 814 | 1468 | 1589 | 1589 | 840,79 |
| plancha incorrrecta 1.mp4 | plancha | 29,97 | 19,8 | 0 (0,0 %) | 1031 | 1883 | 1995 | 1995 | 517,78 |
| PlanchaCorrecta1 (2).mp4 | plancha | 30,00 | 14,7 | 0 (0,0 %) | 12956 | 27852 | 29161 | 29161 | 993,92 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 29,97 | 17,5 | 0 (0,0 %) | 53200 | 97805 | 101988 | 101988 | 752,80 |

Total: 13089 de 13089 frames procesados (0,0 % descartados); retraso p50 21112 ms, p95 100604 ms, máx 178597 ms.

`[I]` En vídeo los FPS sostenidos no pueden superar los FPS de la fuente: el objetivo de 25 fps solo se evalúa en vídeos de ≥ 25 fps. La capacidad del equipo (FPS a ritmo máximo) está en la sección 7.

## 4. Detección → inicio de voz

Voz: Piper sin audio (es_MX-claude-high.onnx). Por mensaje: llegada del frame que lo dispara → encolado en `ColaVoz` → empieza a sonar. Política «último frame», ritmo real.

| Tramo (s) | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| frame → encolado | 17 | 0,285 | 0,057 | 0,858 | 3,889 |
| encolado → audio | 17 | 0,001 | 0,001 | 0,002 | 0,002 |
| total (correcciones) | 17 | 0,285 | 0,057 | 0,860 | 3,891 |

Correcciones que esperaron a que terminara otra frase (> 0,1 s en la cola): 0 de 17. Con la cola libre, total p50 0,057 s, p95 0,860 s (n = 17). `[I]` La espera la causan sobre todo el anuncio del ejercicio al empezar y la frase anterior: la cola tiene un solo hueco y no interrumpe lo que está sonando.

Correcciones emitidas: 17; no llegaron a sonar: 0 (0,0 %; por causa: ninguna). «sustituida»: llegó otra más reciente; «aviso»: el hueco lo tenía un aviso; «caducada»: esperó más de 1 s (`MAX_ESPERA_FEEDBACK_S`). El p95 de arriba solo cuenta las que sonaron. Refuerzos: 4.
`[?]` No incluye la latencia del dispositivo de audio.

## 5. Silencios por causa

Frames: 8359; sin persona: 468 (5,6 %); en pausa: 429 (5,1 %) {'inactividad': 429}; evaluados por el motor: 5364.

| Motivo (`MOTIVO_*`) | Frames | % de los evaluados |
|---|---|---|
| `sin_error` | 3824 | 71,3 % |
| `periodo_refractario` | 922 | 17,2 % |
| `evidencia_insuficiente` | 315 | 5,9 % |
| `desvanecimiento` | 267 | 5,0 % |
| `plano_no_observable` | 15 | 0,3 % |
| corrección | 17 | 0,3 % |
| refuerzo | 4 | 0,1 % |

Por ejercicio (% de los frames evaluados):

| Ejercicio | Frames | Sin persona | En pausa | Evaluados | sin_error | confianza_baja | plano_no_observable | evidencia_insuficiente | refractario | fase_silenciada | otros | mensajes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abduccion_cadera_der | 2466 | 8,4 % | 0,0 % | 1852 | 76,1 % | n/d | n/d | 2,0 % | 18,5 % | n/d | 3,0 % | 6 |
| abduccion_cadera_izq | 672 | 0,6 % | 2,2 % | 415 | 75,2 % | n/d | n/d | 8,4 % | 15,7 % | n/d | 0 % | 3 |
| jumping_jacks | 2337 | 0,5 % | 0,0 % | 1283 | 95,3 % | n/d | n/d | 3,6 % | 0,8 % | n/d | 0 % | 4 |
| plancha | 2884 | 8,5 % | 14,4 % | 1814 | 48,5 % | n/d | 0,8 % | 10,9 % | 27,8 % | n/d | 11,6 % | 8 |

## 6. Exactitud del feedback frente a anotación humana

**pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA\backend\datos_locales\anotaciones); las 5 sesiones grabadas aún no existen.** Precisión, recobrado, F1, sobrecorrección, mensajes correctos y κ necesitan la hoja de anotación (`estela-anotacion-v1`, ver README).

Aserciones no soportadas (M2 de EXP-001) en los mensajes emitidos sobre los vídeos: 0,0 % (0 de 17 correcciones). No necesita anotación.

**Correcciones en los vídeos de control (descriptivo, no es la sobrecorrección).** EXP-009 §4 trata estos vídeos como ejecuciones supuestamente correctas, pero nadie los ha anotado: una corrección aquí es un candidato a falso positivo, no un falso positivo.

| Vídeo | Ejercicio | Reps contadas | Correcciones (error_id × veces) | Refuerzos |
|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 10 | — | 0 |
| 2 mujer.mp4 | jumping_jacks | 6 | — | 0 |
| 3 mujer.mp4 | jumping_jacks | 6 | `codos_flexionados` × 1 | 0 |
| 4 mujer.mp4 | jumping_jacks | 5 | — | 0 |
| 5 hombre.mp4 | jumping_jacks | 8 | — | 0 |
| 6 mujer.mp4 | jumping_jacks | 3 | — | 0 |
| 7 hombre.mp4 (ref.) | jumping_jacks | 35 | — | 2 |
| 8 hombre.mp4 | jumping_jacks | 15 | — | 1 |
| 9 mujer.mp4 | jumping_jacks | 3 | — | 0 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 2 | — | 0 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 26 | `cadera_der_sube` × 4 | 0 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 (ref.) | abduccion_cadera_der | 11 | `cadera_der_sube` × 2 | 0 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 (ref.) | abduccion_cadera_izq | 11 | `cadera_izq_sube` × 2, `tronco_inclinado_der` × 1 | 0 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 1 | — | 0 |
| plancha correcta hombre.mp4 (ref.) | plancha | 12 | `cadera_elevada` × 1, `rodilla_der_flexionada` × 1 | 0 |
| plancha incorrecta 2.mp4 | plancha | 0 | — | 0 |
| plancha incorrrecta 1.mp4 | plancha | 2 | — | 0 |
| PlanchaCorrecta1 (2).mp4 | plancha | 26 | — | 1 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 52 | `cadera_elevada` × 3, `hombros_adelantados` × 1, `rodilla_der_flexionada` × 1 | 0 |

## 7. Variantes de MediaPipe (EXP-004) — ritmo máximo, cola sin descarte

Mismos vídeos, recortados a 30 s. Capacidad = frames / tiempo de pared procesando a ritmo máximo (incluye decodificar el vídeo).

| Modelo | Frames | Pose media | p50 | p95 | máx | Capacidad (fps) | % frames con persona | Reps contadas | Correcciones |
|---|---|---|---|---|---|---|---|---|---|
| lite | 8143 | 31,4 | 29,4 | 47,7 | 142,6 | 22,7 | 97,4 % | 112 | 15 |
| full | 8143 | 33,3 | 31,3 | 48,0 | 414,4 | 23,3 | 97,3 % | 115 | 16 |

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
| jumping_jacks | 62 | sin banda | 4012 | 98,0 % | 0,14 | 0,11 | 0,27 | 2,57 | -0,000 | 328 | 0,9 % | n/d | n/d |
| jumping_jacks | 62 | banda 10% (6 fr) | 4012 | 98,0 % | 0,08 | 0,06 | 0,14 | 0,95 | -0,000 | 328 | 8,4 % | 0,918 | 123,68 |
| jumping_jacks | 62 | banda 20% (12 fr) | 4012 | 98,0 % | 0,08 | 0,06 | 0,14 | 0,68 | -0,000 | 328 | 8,2 % | 0,902 | 124,14 |
| abduccion_cadera_der | 55 | sin banda | 2325 | 97,0 % | 0,11 | 0,10 | 0,21 | 0,83 | 0,000 | 204 | 1,7 % | n/d | n/d |
| abduccion_cadera_der | 55 | banda 10% (6 fr) | 2325 | 94,0 % | 0,06 | 0,05 | 0,11 | 0,41 | 0,000 | 204 | 7,5 % | 0,722 | 45,96 |
| abduccion_cadera_der | 55 | banda 20% (11 fr) | 2325 | 94,0 % | 0,06 | 0,05 | 0,12 | 0,44 | 0,000 | 204 | 7,0 % | 0,722 | 36,48 |
| abduccion_cadera_izq | 55 | sin banda | 797 | 98,6 % | 0,15 | 0,14 | 0,25 | 0,68 | -0,000 | 232 | 1,1 % | n/d | n/d |
| abduccion_cadera_izq | 55 | banda 10% (6 fr) | 797 | 98,6 % | 0,09 | 0,08 | 0,14 | 0,42 | -0,000 | 232 | 0,9 % | 0,481 | 23,75 |
| abduccion_cadera_izq | 55 | banda 20% (11 fr) | 797 | 98,6 % | 0,09 | 0,08 | 0,14 | 0,28 | -0,000 | 232 | 1,1 % | 0,148 | 20,24 |
| plancha | — | sin referencia DTW (isométrico o ausente) | | | | | | | | | | | |

Latencia según la longitud del prefijo, todos los ejercicios juntos (ms):

| Prefijo (frames) | Variante | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|---|
| 1–15 | sin banda | 2189 | 0,13 | 0,11 | 0,25 | 1,09 |
| 16–30 | sin banda | 1765 | 0,13 | 0,11 | 0,26 | 2,57 |
| 31–60 | sin banda | 2295 | 0,13 | 0,12 | 0,25 | 1,22 |
| 61–120 | sin banda | 318 | 0,13 | 0,11 | 0,23 | 0,97 |
| 121–240 | sin banda | 316 | 0,12 | 0,11 | 0,20 | 0,42 |
| 241–∞ | sin banda | 88 | 0,13 | 0,11 | 0,23 | 0,54 |
| 1–15 | banda 10% | 2252 | 0,07 | 0,06 | 0,13 | 0,95 |
| 16–30 | banda 10% | 1750 | 0,08 | 0,06 | 0,13 | 0,65 |
| 31–60 | banda 10% | 2265 | 0,08 | 0,07 | 0,14 | 0,79 |
| 61–120 | banda 10% | 300 | 0,08 | 0,06 | 0,13 | 0,47 |
| 121–240 | banda 10% | 316 | 0,07 | 0,06 | 0,11 | 0,42 |
| 241–∞ | banda 10% | 88 | 0,07 | 0,06 | 0,13 | 0,29 |
| 1–15 | banda 20% | 2252 | 0,07 | 0,06 | 0,13 | 0,58 |
| 16–30 | banda 20% | 1750 | 0,08 | 0,06 | 0,14 | 0,38 |
| 31–60 | banda 20% | 2265 | 0,08 | 0,07 | 0,14 | 0,68 |
| 61–120 | banda 20% | 300 | 0,08 | 0,06 | 0,12 | 0,32 |
| 121–240 | banda 20% | 316 | 0,07 | 0,05 | 0,10 | 0,21 |
| 241–∞ | banda 20% | 88 | 0,07 | 0,06 | 0,11 | 0,29 |

El DTW es incremental y de final abierto: cada frame actualiza una columna de la matriz en O(m) y se reinicia en cada repetición, así que la latencia no debería crecer con el prefijo (columna «ms por frame de prefijo»). La banda se centra en el instante que tocaría al ritmo de la referencia; las columnas «Δ» comparan cada banda con la variante sin banda.

## 9. Plantilla frente a LLM local (EXP-001, banco sintético)

| Condición | Episodios | M2 aserciones no soportadas | M3 sobrecorrección | M5 determinismo | M7 fallback | Verbalización p50 (ms) | p95 | máx |
|---|---|---|---|---|---|---|---|---|
| A | 163 | 0,0 % (174) | 0,0 % (18) | 100,0 % | 0,0 % | 0,2020 | 0,3830 | 0,4826 |
| F | pendiente de medición en la Mac: llama-server no responde en http://127.0.0.1:8080 (URLError) | | | | | | | |

La M1 real (exactitud de contenido) y la comparación sobre vídeo necesitan las anotaciones (sección 6). La condición F solo puede correr donde haya `llama-server` (la Mac).

## 10. Piper: factor de tiempo real

Voz `es_MX-claude-high.onnx`, 110 frases de `frases_de_rutina` (calentamiento básico). RTF = tiempo de síntesis / duración del audio; < 1 es más rápido que el tiempo real. La primera frase (inicialización) tardó 6032 ms y no entra en la tabla.

| Medida | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| síntesis (ms) | 109 | 379,0 | 365,1 | 600,5 | 874,2 |
| duración del audio (s) | 109 | 3,66 | 3,54 | 5,64 | 7,57 |
| RTF | 109 | 0,104 | 0,101 | 0,132 | 0,179 |

## Pendiente de medición

- **exp001_F**: pendiente de medición en la Mac: llama-server no responde en http://127.0.0.1:8080 (URLError)
- **modelo_heavy**: pendiente de medición: falta pose_landmarker_heavy.task (python scripts/descargar_modelos.py --heavy)
- **anotaciones**: pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA\backend\datos_locales\anotaciones); las 5 sesiones grabadas aún no existen
- **hardware final**: todas las cifras de tiempo hay que repetirlas en la Mac Studio M2 Ultra.
- **sesiones reales**: las 5 participantes aún no han grabado la rutina; ninguna cifra de esta página procede de ellas.

