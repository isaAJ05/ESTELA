# Informe 2 — métricas medidas

> **Cifras preliminares.** Medidas en el Mac Studio M2 Ultra del proyecto (tabla de abajo), con vídeos públicos sin anotar. No son sesiones de las participantes. Generado por `python -m feedback_testing.informe2`; no editar a mano.

Convención: `[F]` medido aquí · `[I]` inferencia · `[R]` recomendación · `[?]` pendiente.

## Equipo

| Campo | Valor |
|---|---|
| fecha | 2026-11-22T16:54:26-05:00 |
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
| modelo de pose (corrida principal) | pose_landmarker_heavy |
| delegado de pose | gpu |
| voz | Piper sin audio (es_MX-claude-high.onnx) |
| precalentado de la voz | 0,6 s antes de medir, sin contar las frases ya sintetizadas al medir el RTF (en la app es en segundo plano al arrancar) |

## Resumen frente a los objetivos

| Métrica | Objetivo | Medido | Estado |
|---|---|---|---|
| p95 de la estimación de pose | ≤ 33 ms | 16,5 ms (modelo heavy, n = 16125) | **cumple** |
| FPS sostenidos | ≥ 25 fps | mínimo por vídeo 25,0 fps (15 vídeos con fuente ≥ 25 fps, política «último frame») | **cumple** |
| p95 detección → inicio de voz | ≤ 1 s | 0,10 s (n = 21 correcciones habladas; 0 descartadas por esperar más de 1 s; Piper sin audio (es_MX-claude-high.onnx)) | **cumple** |
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

## 2. Latencia por etapa (ms) — modelo heavy, política «último frame», ritmo real

| Etapa | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| pose | 16125 | 13,23 | 13,61 | 16,51 | 199,67 |
| geometria | 15328 | 0,86 | 0,91 | 1,19 | 2,12 |
| segmentacion | 15328 | 0,04 | 0,04 | 0,06 | 0,17 |
| dtw | 15328 | 0,12 | 0,11 | 0,23 | 0,55 |
| decision | 11731 | 0,09 | 0,07 | 0,19 | 0,91 |
| verbalizacion | 24 | 0,33 | 0,34 | 0,47 | 0,55 |
| motor | 11731 | 0,09 | 0,08 | 0,20 | 0,92 |
| total | 15328 | 15,74 | 16,25 | 20,55 | 200,31 |
| procesar (pared) | 16125 | 15,90 | 16,33 | 20,86 | 200,32 |

`total` solo existe en los frames que llegan al motor (con persona y sin pausa); `procesar (pared)` es `Sesion.procesar` entero en todos los frames. `verbalizacion` solo en los frames con mensaje. `motor` = decisión + verbalización.
La primera inferencia de cada estimador (calentamiento, fuera de la medición) tardó 9 ms de mediana.

Pose por ejercicio:

| Ejercicio | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| abduccion_cadera_der | 2538 | 15,11 | 14,87 | 20,04 | 47,64 |
| abduccion_cadera_izq | 803 | 14,13 | 14,32 | 15,68 | 40,61 |
| jumping_jacks | 4024 | 10,86 | 9,72 | 14,88 | 67,27 |
| plancha | 5718 | 12,94 | 13,03 | 15,32 | 199,67 |
| zancada_atras_der | 973 | 14,15 | 14,28 | 15,82 | 40,58 |
| zancada_atras_izq | 2069 | 15,59 | 15,32 | 20,61 | 40,89 |

## 3. FPS sostenidos, frames descartados y retraso acumulado

Retraso por frame = fin de su procesamiento − su marca nominal de llegada (ms). Deriva = pendiente del retraso frente al tiempo (ms por s): ≈ 0 si el sistema da abasto.

### Política «último frame (como `FuenteCamara`)»

| Vídeo | Ejercicio | FPS fuente | FPS sostenidos | Descartados | Retraso p50 | p95 | máx | final | Deriva |
|---|---|---|---|---|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 23,98 | 24,0 | 0 (0,0 %) | 21 | 23 | 73 | 21 | 0,13 |
| 2 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 21 | 23 | 45 | 20 | 0,25 |
| 3 mujer.mp4 | jumping_jacks | 29,97 | 30,0 | 0 (0,0 %) | 21 | 23 | 44 | 23 | 0,06 |
| 4 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 22 | 24 | 45 | 19 | -0,09 |
| 5 hombre.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 22 | 23 | 47 | 20 | 0,16 |
| 6 mujer.mp4 | jumping_jacks | 30,00 | 30,1 | 0 (0,0 %) | 19 | 22 | 45 | 21 | 0,88 |
| 7 hombre.mp4 | jumping_jacks | 59,94 | 59,9 | 1 (0,0 %) | 13 | 18 | 39 | 14 | -0,00 |
| 8 hombre.mp4 | jumping_jacks | 30,00 | 30,0 | 0 (0,0 %) | 20 | 23 | 72 | 21 | 0,09 |
| 9 mujer.mp4 | jumping_jacks | 23,98 | 24,1 | 0 (0,0 %) | 22 | 24 | 46 | 19 | 0,22 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 29,97 | 30,0 | 0 (0,0 %) | 21 | 24 | 53 | 33 | 0,14 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 23 | 31 | 50 | 30 | 0,09 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 31 | 32 | 52 | 31 | 0,04 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | abduccion_cadera_izq | 18,00 | 18,0 | 0 (0,0 %) | 30 | 32 | 52 | 31 | 0,01 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 24,00 | 24,0 | 0 (0,0 %) | 26 | 28 | 51 | 24 | 0,14 |
| PlanchaCorrecta1 (2).mp4 | plancha | 30,00 | 30,0 | 0 (0,0 %) | 25 | 28 | 51 | 27 | -0,01 |
| plancha correcta hombre.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 25 | 27 | 50 | 27 | -0,08 |
| plancha incorrecta 2.mp4 | plancha | 29,97 | 30,1 | 0 (0,0 %) | 23 | 27 | 49 | 27 | 3,29 |
| plancha incorrrecta 1.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 24 | 27 | 49 | 25 | -0,07 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 29,97 | 29,9 | 5 (0,1 %) | 25 | 28 | 212 | 27 | 0,00 |
| ZANCADA CHICA DERECHA.mp4 | zancada_atras_der | 25,00 | 25,0 | 0 (0,0 %) | 26 | 29 | 51 | 26 | 0,02 |
| ZANCADA CHICA IZQUIERDA.mp4 | zancada_atras_izq | 25,00 | 25,0 | 0 (0,0 %) | 25 | 28 | 50 | 23 | 0,08 |
| der Zancada atrás con Kettlebell Derecha - Ejercicios de la App Malagaentrena.mp4 | zancada_atras_der | 24,00 | 24,0 | 0 (0,0 %) | 27 | 29 | 50 | 28 | 0,06 |
| izq Zancada hacia atrás con peso corporal_ técnica paso a paso.mp4 | zancada_atras_izq | 18,00 | 18,0 | 0 (0,0 %) | 28 | 31 | 52 | 32 | 0,03 |

Total: 16125 de 16131 frames procesados (0,0 % descartados); retraso p50 24 ms, p95 31 ms, máx 212 ms.

### Política «cola sin descarte (como `FuenteVideo`)»

| Vídeo | Ejercicio | FPS fuente | FPS sostenidos | Descartados | Retraso p50 | p95 | máx | final | Deriva |
|---|---|---|---|---|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 23,98 | 24,0 | 0 (0,0 %) | 23 | 26 | 57 | 25 | 0,10 |
| 2 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 23 | 27 | 49 | 25 | 0,18 |
| 3 mujer.mp4 | jumping_jacks | 29,97 | 30,0 | 0 (0,0 %) | 20 | 23 | 51 | 23 | 0,01 |
| 4 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 24 | 27 | 51 | 26 | 0,23 |
| 5 hombre.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 24 | 28 | 50 | 25 | 0,07 |
| 6 mujer.mp4 | jumping_jacks | 30,00 | 30,1 | 0 (0,0 %) | 19 | 24 | 49 | 20 | 0,37 |
| 7 hombre.mp4 | jumping_jacks | 59,94 | 59,9 | 0 (0,0 %) | 11 | 12 | 38 | 12 | 0,00 |
| 8 hombre.mp4 | jumping_jacks | 30,00 | 30,0 | 0 (0,0 %) | 20 | 26 | 49 | 15 | 0,06 |
| 9 mujer.mp4 | jumping_jacks | 23,98 | 24,0 | 0 (0,0 %) | 22 | 27 | 51 | 24 | -0,22 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 29,97 | 30,0 | 0 (0,0 %) | 19 | 25 | 52 | 40 | 0,05 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 24 | 30 | 51 | 32 | 0,05 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 25 | 31 | 54 | 24 | 0,04 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | abduccion_cadera_izq | 18,00 | 18,0 | 0 (0,0 %) | 26 | 32 | 56 | 31 | 0,04 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 24,00 | 24,0 | 0 (0,0 %) | 22 | 26 | 51 | 28 | 0,05 |
| PlanchaCorrecta1 (2).mp4 | plancha | 30,00 | 30,0 | 0 (0,0 %) | 18 | 24 | 52 | 22 | -0,02 |
| plancha correcta hombre.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 19 | 26 | 49 | 17 | -0,01 |
| plancha incorrecta 2.mp4 | plancha | 29,97 | 30,2 | 0 (0,0 %) | 17 | 25 | 52 | 17 | 0,62 |
| plancha incorrrecta 1.mp4 | plancha | 29,97 | 30,1 | 0 (0,0 %) | 18 | 24 | 50 | 15 | -0,33 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 17 | 22 | 196 | 17 | -0,01 |
| ZANCADA CHICA DERECHA.mp4 | zancada_atras_der | 25,00 | 25,0 | 0 (0,0 %) | 19 | 22 | 44 | 22 | 0,18 |
| ZANCADA CHICA IZQUIERDA.mp4 | zancada_atras_izq | 25,00 | 25,0 | 0 (0,0 %) | 18 | 22 | 44 | 22 | 0,08 |
| der Zancada atrás con Kettlebell Derecha - Ejercicios de la App Malagaentrena.mp4 | zancada_atras_der | 24,00 | 24,0 | 0 (0,0 %) | 20 | 22 | 43 | 22 | 0,04 |
| izq Zancada hacia atrás con peso corporal_ técnica paso a paso.mp4 | zancada_atras_izq | 18,00 | 18,0 | 0 (0,0 %) | 23 | 25 | 44 | 25 | 0,01 |

Total: 16131 de 16131 frames procesados (0,0 % descartados); retraso p50 19 ms, p95 28 ms, máx 196 ms.

`[I]` En vídeo los FPS sostenidos no pueden superar los FPS de la fuente: el objetivo de 25 fps solo se evalúa en vídeos de ≥ 25 fps. La capacidad del equipo (FPS a ritmo máximo) está en la sección 7.

## 4. Detección → inicio de voz

Voz: Piper sin audio (es_MX-claude-high.onnx). Por mensaje: llegada del frame que lo dispara → encolado en `ColaVoz` → empieza a sonar. Política «último frame», ritmo real.

| Tramo (s) | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| frame → encolado | 21 | 0,025 | 0,025 | 0,032 | 0,032 |
| encolado → audio | 21 | 0,032 | 0,000 | 0,078 | 0,082 |
| total (correcciones) | 21 | 0,057 | 0,033 | 0,104 | 0,108 |

Correcciones que esperaron a que terminara otra frase (> 0,1 s en la cola): 0 de 21. Con la cola libre, total p50 0,033 s, p95 0,104 s (n = 21). `[I]` La espera la causan sobre todo el anuncio del ejercicio al empezar y la frase anterior: la cola tiene un solo hueco y no interrumpe lo que está sonando.

Correcciones emitidas: 21; no llegaron a sonar: 0 (0,0 %; por causa: ninguna). «sustituida»: llegó otra más reciente; «aviso»: el hueco lo tenía un aviso; «caducada»: esperó más de 1 s (`MAX_ESPERA_FEEDBACK_S`). El p95 de arriba solo cuenta las que sonaron. Refuerzos: 3.
`[?]` No incluye la latencia del dispositivo de audio.

## 5. Silencios por causa

Frames: 16125; sin persona: 797 (4,9 %); en pausa: 0 (0,0 %) ; evaluados por el motor: 11731.

| Motivo (`MOTIVO_*`) | Frames | % de los evaluados |
|---|---|---|
| `sin_error` | 7869 | 67,1 % |
| `periodo_refractario` | 2201 | 18,8 % |
| `desvanecimiento` | 924 | 7,9 % |
| `evidencia_insuficiente` | 449 | 3,8 % |
| `confianza_baja` | 168 | 1,4 % |
| `plano_no_observable` | 96 | 0,8 % |
| corrección | 21 | 0,2 % |
| refuerzo | 3 | 0,0 % |

Por ejercicio (% de los frames evaluados):

| Ejercicio | Frames | Sin persona | En pausa | Evaluados | sin_error | confianza_baja | plano_no_observable | evidencia_insuficiente | refractario | fase_silenciada | otros | mensajes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abduccion_cadera_der | 2538 | 10,6 % | 0,0 % | 1855 | 68,9 % | n/d | n/d | 3,1 % | 23,7 % | n/d | 4,0 % | 6 |
| abduccion_cadera_izq | 803 | 0,0 % | 0,0 % | 423 | 73,8 % | n/d | n/d | 3,3 % | 22,2 % | n/d | 0 % | 3 |
| jumping_jacks | 4024 | 0,3 % | 0,0 % | 2652 | 95,8 % | 0,3 % | n/d | 3,1 % | 0,8 % | n/d | 0 % | 4 |
| plancha | 5718 | 4,4 % | 0,0 % | 4732 | 40,0 % | n/d | 0,8 % | 6,3 % | 34,8 % | n/d | 18,0 % | 11 |
| zancada_atras_der | 973 | 0,0 % | 0,0 % | 514 | 88,1 % | n/d | 11,7 % | 0,2 % | n/d | n/d | 0 % | 0 |
| zancada_atras_izq | 2069 | 12,7 % | 0,0 % | 1555 | 89,6 % | 10,4 % | n/d | n/d | n/d | n/d | 0 % | 0 |

## 6. Exactitud del feedback frente a anotación humana

**pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA/backend/datos_locales/anotaciones); las 5 sesiones grabadas aún no existen.** Precisión, recobrado, F1, sobrecorrección, mensajes correctos y κ necesitan la hoja de anotación (`estela-anotacion-v1`, ver README).

Aserciones no soportadas (M2 de EXP-001) en los mensajes emitidos sobre los vídeos: 0,0 % (0 de 21 correcciones). No necesita anotación.

**Correcciones en los vídeos de control (descriptivo, no es la sobrecorrección).** EXP-009 §4 trata estos vídeos como ejecuciones supuestamente correctas, pero nadie los ha anotado: una corrección aquí es un candidato a falso positivo, no un falso positivo.

| Vídeo | Ejercicio | Reps contadas | Correcciones (error_id × veces) | Refuerzos |
|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 10 | — | 0 |
| 2 mujer.mp4 | jumping_jacks | 6 | — | 0 |
| 3 mujer.mp4 | jumping_jacks | 6 | `codos_flexionados` × 1 | 0 |
| 4 mujer.mp4 | jumping_jacks | 5 | — | 0 |
| 5 hombre.mp4 | jumping_jacks | 8 | — | 0 |
| 6 mujer.mp4 | jumping_jacks | 4 | — | 0 |
| 7 hombre.mp4 (ref.) | jumping_jacks | 35 | — | 2 |
| 8 hombre.mp4 | jumping_jacks | 15 | — | 1 |
| 9 mujer.mp4 | jumping_jacks | 3 | — | 0 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 3 | — | 0 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 27 | `cadera_der_sube` × 4 | 0 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 (ref.) | abduccion_cadera_der | 11 | `cadera_der_sube` × 2 | 0 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 (ref.) | abduccion_cadera_izq | 11 | `cadera_izq_sube` × 1, `tronco_inclinado_der` × 2 | 0 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 0 | — | 0 |
| PlanchaCorrecta1 (2).mp4 | plancha | 26 | `codo_der_fuera_de_90` × 2 | 0 |
| plancha correcta hombre.mp4 (ref.) | plancha | 12 | `cadera_elevada` × 1, `codo_der_fuera_de_90` × 1 | 0 |
| plancha incorrecta 2.mp4 | plancha | 0 | — | 0 |
| plancha incorrrecta 1.mp4 | plancha | 2 | — | 0 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 55 | `cadera_elevada` × 3, `cadera_hundida` × 1, `codo_der_fuera_de_90` × 1, `hombros_adelantados` × 2 | 0 |
| ZANCADA CHICA DERECHA.mp4 (ref.) | zancada_atras_der | 7 | — | 0 |
| ZANCADA CHICA IZQUIERDA.mp4 (ref.) | zancada_atras_izq | 7 | — | 0 |
| der Zancada atrás con Kettlebell Derecha - Ejercicios de la App Malagaentrena.mp4 | zancada_atras_der | 11 | — | 0 |
| izq Zancada hacia atrás con peso corporal_ técnica paso a paso.mp4 | zancada_atras_izq | 24 | — | 0 |

## 7. Variantes de MediaPipe (EXP-004) — ritmo máximo, cola sin descarte

Mismos vídeos, recortados a 30 s. Capacidad = frames / tiempo de pared procesando a ritmo máximo (incluye decodificar el vídeo).

| Modelo | Frames | Pose media | p50 | p95 | máx | Capacidad (fps) | % frames con persona | Reps contadas | Correcciones |
|---|---|---|---|---|---|---|---|---|---|
| lite | 9976 | 3,4 | 3,2 | 3,5 | 36,6 | 233,6 | 97,3 % | 147 | 19 |
| full | 9976 | 3,4 | 3,2 | 3,6 | 38,3 | 231,4 | 97,2 % | 147 | 19 |
| heavy | 9976 | 5,1 | 4,9 | 5,4 | 39,6 | 167,1 | 97,2 % | 149 | 19 |

p95 de pose frente al objetivo (≤ 33 ms): lite **cumple**, full **cumple**, heavy **cumple**.

Jitter en la plancha mantenida (fase `mantenimiento`, confianza ≥ 0,5): desviación del residuo frente a una media móvil de 15 frames. Es el único tramo quieto de los vídeos; en los demás el temblor se mezcla con el movimiento.

| Modelo | tronco_inclinacion | cabeza_adelantada | alineacion_cadera |
|---|---|---|---|
| lite | 0,357 | 0,855 | 0,006 |
| full | 0,237 | 0,495 | 0,004 |
| heavy | 0,202 | 0,480 | 0,004 |

Unidades: grados en los ángulos; escalas corporales en `alineacion_cadera`.

## 8. DTW incremental sin banda frente a banda Sakoe-Chiba (EXP-010)

Réplica fuera de línea de las observaciones de la corrida «cola» (modelo heavy), con las mismas llamadas que hace la sesión. Banda en frames = fracción × longitud de la referencia (0,10, 0,20).

| Ejercicio | Ref. (frames) | Variante | Frames | Con resultado | Latencia media | p50 | p95 | máx | ms por frame de prefijo | Prefijo máx | progreso = 1 | Δ progreso máx | Δ ángulos_ref máx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jumping_jacks | 62 | sin banda | 4012 | 98,0 % | 0,02 | 0,02 | 0,03 | 0,05 | 0,000 | 330 | 0,4 % | n/d | n/d |
| jumping_jacks | 62 | banda 10% (6 fr) | 4012 | 98,0 % | 0,02 | 0,02 | 0,02 | 0,03 | 0,000 | 330 | 8,0 % | 0,918 | 124,14 |
| jumping_jacks | 62 | banda 20% (12 fr) | 4012 | 98,0 % | 0,02 | 0,02 | 0,02 | 0,04 | -0,000 | 330 | 7,7 % | 0,902 | 124,14 |
| abduccion_cadera_der | 55 | sin banda | 2268 | 96,9 % | 0,02 | 0,02 | 0,02 | 0,03 | 0,000 | 114 | 1,0 % | n/d | n/d |
| abduccion_cadera_der | 55 | banda 10% (6 fr) | 2268 | 96,4 % | 0,01 | 0,02 | 0,02 | 0,02 | 0,000 | 114 | 2,5 % | 0,593 | 44,44 |
| abduccion_cadera_der | 55 | banda 20% (11 fr) | 2268 | 96,4 % | 0,02 | 0,02 | 0,02 | 0,02 | 0,000 | 114 | 1,6 % | 0,556 | 34,96 |
| abduccion_cadera_izq | 55 | sin banda | 803 | 69,2 % | 0,02 | 0,02 | 0,02 | 0,03 | 0,000 | 56 | 0,0 % | n/d | n/d |
| abduccion_cadera_izq | 55 | banda 10% (6 fr) | 803 | 69,2 % | 0,01 | 0,01 | 0,02 | 0,02 | 0,000 | 56 | 0,5 % | 0,463 | 8,22 |
| abduccion_cadera_izq | 55 | banda 20% (11 fr) | 803 | 69,2 % | 0,01 | 0,02 | 0,02 | 0,02 | 0,000 | 56 | 0,5 % | 0,463 | 8,22 |
| plancha | — | sin referencia DTW (isométrico o ausente) | | | | | | | | | | | |
| zancada_atras_der | 44 | sin banda | 973 | 97,1 % | 0,02 | 0,02 | 0,02 | 0,03 | 0,000 | 69 | 11,4 % | n/d | n/d |
| zancada_atras_der | 44 | banda 10% (4 fr) | 973 | 97,1 % | 0,01 | 0,01 | 0,01 | 0,02 | 0,000 | 69 | 11,3 % | 0,814 | 64,99 |
| zancada_atras_der | 44 | banda 20% (9 fr) | 973 | 97,1 % | 0,01 | 0,02 | 0,02 | 0,02 | 0,000 | 69 | 11,4 % | 0,791 | 64,99 |
| zancada_atras_izq | 45 | sin banda | 1806 | 99,2 % | 0,02 | 0,02 | 0,02 | 0,03 | 0,000 | 125 | 0,0 % | n/d | n/d |
| zancada_atras_izq | 45 | banda 10% (4 fr) | 1806 | 98,7 % | 0,01 | 0,01 | 0,01 | 0,02 | -0,000 | 125 | 35,1 % | 0,841 | 80,44 |
| zancada_atras_izq | 45 | banda 20% (9 fr) | 1806 | 98,7 % | 0,01 | 0,01 | 0,02 | 0,03 | -0,000 | 125 | 29,7 % | 0,841 | 78,87 |

Latencia según la longitud del prefijo, todos los ejercicios juntos (ms):

| Prefijo (frames) | Variante | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|---|
| 1–15 | sin banda | 2951 | 0,02 | 0,02 | 0,02 | 0,05 |
| 16–30 | sin banda | 2497 | 0,02 | 0,02 | 0,02 | 0,04 |
| 31–60 | sin banda | 3259 | 0,02 | 0,02 | 0,02 | 0,04 |
| 61–120 | sin banda | 499 | 0,02 | 0,02 | 0,02 | 0,04 |
| 121–240 | sin banda | 125 | 0,02 | 0,02 | 0,03 | 0,04 |
| 241–∞ | sin banda | 90 | 0,02 | 0,02 | 0,03 | 0,03 |
| 1–15 | banda 10% | 2956 | 0,02 | 0,01 | 0,02 | 0,03 |
| 16–30 | banda 10% | 2492 | 0,02 | 0,02 | 0,02 | 0,03 |
| 31–60 | banda 10% | 3259 | 0,01 | 0,01 | 0,02 | 0,02 |
| 61–120 | banda 10% | 499 | 0,01 | 0,01 | 0,02 | 0,02 |
| 121–240 | banda 10% | 125 | 0,01 | 0,01 | 0,02 | 0,02 |
| 241–∞ | banda 10% | 90 | 0,01 | 0,01 | 0,02 | 0,02 |
| 1–15 | banda 20% | 2956 | 0,02 | 0,02 | 0,02 | 0,04 |
| 16–30 | banda 20% | 2492 | 0,02 | 0,02 | 0,02 | 0,03 |
| 31–60 | banda 20% | 3259 | 0,02 | 0,02 | 0,02 | 0,03 |
| 61–120 | banda 20% | 499 | 0,01 | 0,01 | 0,02 | 0,02 |
| 121–240 | banda 20% | 125 | 0,02 | 0,02 | 0,02 | 0,03 |
| 241–∞ | banda 20% | 90 | 0,02 | 0,02 | 0,02 | 0,02 |

El DTW es incremental y de final abierto: cada frame actualiza una columna de la matriz en O(m) y se reinicia en cada repetición, así que la latencia no debería crecer con el prefijo (columna «ms por frame de prefijo»). La banda se centra en el instante que tocaría al ritmo de la referencia; las columnas «Δ» comparan cada banda con la variante sin banda.

## 9. Plantilla frente a LLM local (EXP-001, banco sintético)

| Condición | Episodios | M2 aserciones no soportadas | M3 sobrecorrección | M5 determinismo | M7 fallback | Verbalización p50 (ms) | p95 | máx |
|---|---|---|---|---|---|---|---|---|
| A | 163 | 0,0 % (174) | 0,0 % (18) | 100,0 % | 0,0 % | 0,0480 | 0,0668 | 0,0769 |
| F | pendiente de medición en la Mac: llama-server no responde en http://127.0.0.1:8080 (URLError) | | | | | | | |

La M1 real (exactitud de contenido) y la comparación sobre vídeo necesitan las anotaciones (sección 6). La condición F solo puede correr donde haya `llama-server` (la Mac).

## 10. Piper: factor de tiempo real

Voz `es_MX-claude-high.onnx`, 207 frases de `frases_de_rutina` (calentamiento básico). RTF = tiempo de síntesis / duración del audio; < 1 es más rápido que el tiempo real. La primera frase (inicialización) tardó 54 ms y no entra en la tabla.

| Medida | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| síntesis (ms) | 206 | 47,3 | 43,9 | 76,6 | 124,0 |
| duración del audio (s) | 206 | 3,09 | 2,89 | 5,24 | 7,49 |
| RTF | 206 | 0,016 | 0,015 | 0,018 | 0,024 |

## Pendiente de medición

- **exp001_F**: pendiente de medición en la Mac: llama-server no responde en http://127.0.0.1:8080 (URLError)
- **anotaciones**: pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA/backend/datos_locales/anotaciones); las 5 sesiones grabadas aún no existen
- **sesiones reales**: las 5 participantes aún no han grabado la rutina; ninguna cifra de esta página procede de ellas.

