# Informe 2 — métricas medidas

> **Cifras preliminares.** Medidas en el Mac Studio M2 Ultra del proyecto (tabla de abajo), con vídeos públicos sin anotar. No son sesiones de las participantes. Generado por `python -m feedback_testing.informe2`; no editar a mano.

Convención: `[F]` medido aquí · `[I]` inferencia · `[R]` recomendación · `[?]` pendiente.

## Equipo

| Campo | Valor |
|---|---|
| fecha | 2026-11-22T17:59:42-05:00 |
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
| quién redacta las correcciones | LLM `qwen3:4b-instruct-2507-q4_K_M` por ollama, tiempo límite 400 ms, temperatura 0,7; fuera del bucle por imagen. Modelo cargado antes de medir (0,0 s) |
| precalentado de la voz | 0,6 s antes de medir, sin contar las frases ya sintetizadas al medir el RTF (en la app es en segundo plano al arrancar) |

## Resumen frente a los objetivos

| Métrica | Objetivo | Medido | Estado |
|---|---|---|---|
| p95 de la estimación de pose | ≤ 33 ms | 16,2 ms (modelo heavy, n = 16125) | **cumple** |
| FPS sostenidos | ≥ 25 fps | mínimo por vídeo 25,0 fps (15 vídeos con fuente ≥ 25 fps, política «último frame») | **cumple** |
| p95 detección → inicio de voz | ≤ 1 s | 0,39 s (n = 21 correcciones habladas; 0 descartadas por esperar más de 1 s; Piper sin audio (es_MX-claude-high.onnx); redactadas por el LLM, incluida la redacción) | **cumple** |
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
| pose | 16125 | 13,08 | 13,51 | 16,23 | 199,51 |
| geometria | 15328 | 0,87 | 0,90 | 1,29 | 1,83 |
| segmentacion | 15328 | 0,04 | 0,04 | 0,06 | 0,22 |
| dtw | 15328 | 0,12 | 0,11 | 0,25 | 0,60 |
| decision | 11656 | 0,09 | 0,07 | 0,19 | 0,54 |
| verbalizacion | 3 | 0,12 | 0,13 | 0,17 | 0,18 |
| motor | 11656 | 0,09 | 0,07 | 0,20 | 0,76 |
| total | 15328 | 15,57 | 16,11 | 20,35 | 200,17 |
| procesar (pared) | 16125 | 15,75 | 16,18 | 20,85 | 200,18 |

`total` solo existe en los frames que llegan al motor (con persona y sin pausa); `procesar (pared)` es `Sesion.procesar` entero en todos los frames. `verbalizacion` solo en los frames con mensaje. `motor` = decisión + verbalización.
La primera inferencia de cada estimador (calentamiento, fuera de la medición) tardó 9 ms de mediana.

Pose por ejercicio:

| Ejercicio | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| abduccion_cadera_der | 2538 | 15,11 | 14,82 | 20,44 | 44,26 |
| abduccion_cadera_izq | 803 | 14,09 | 14,18 | 15,68 | 39,31 |
| jumping_jacks | 4024 | 10,82 | 9,42 | 14,93 | 55,55 |
| plancha | 5718 | 12,70 | 12,89 | 14,91 | 199,51 |
| zancada_atras_der | 973 | 14,09 | 14,12 | 15,60 | 40,57 |
| zancada_atras_izq | 2069 | 15,17 | 14,90 | 20,89 | 42,64 |

## 3. FPS sostenidos, frames descartados y retraso acumulado

Retraso por frame = fin de su procesamiento − su marca nominal de llegada (ms). Deriva = pendiente del retraso frente al tiempo (ms por s): ≈ 0 si el sistema da abasto.

### Política «último frame (como `FuenteCamara`)»

| Vídeo | Ejercicio | FPS fuente | FPS sostenidos | Descartados | Retraso p50 | p95 | máx | final | Deriva |
|---|---|---|---|---|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 23,98 | 24,0 | 0 (0,0 %) | 21 | 23 | 61 | 22 | 0,05 |
| 2 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 21 | 24 | 44 | 23 | 0,40 |
| 3 mujer.mp4 | jumping_jacks | 29,97 | 30,0 | 0 (0,0 %) | 21 | 23 | 45 | 24 | -0,01 |
| 4 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 21 | 23 | 45 | 21 | 0,15 |
| 5 hombre.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 22 | 23 | 46 | 23 | 0,16 |
| 6 mujer.mp4 | jumping_jacks | 30,00 | 30,1 | 0 (0,0 %) | 19 | 23 | 46 | 17 | 0,71 |
| 7 hombre.mp4 | jumping_jacks | 59,94 | 59,9 | 1 (0,0 %) | 13 | 18 | 53 | 45 | 0,01 |
| 8 hombre.mp4 | jumping_jacks | 30,00 | 30,0 | 0 (0,0 %) | 21 | 24 | 44 | 24 | 0,20 |
| 9 mujer.mp4 | jumping_jacks | 23,98 | 24,1 | 0 (0,0 %) | 22 | 24 | 45 | 22 | 0,18 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 29,97 | 30,0 | 0 (0,0 %) | 20 | 22 | 50 | 40 | 0,09 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 23 | 27 | 49 | 26 | 0,03 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 25 | 27 | 46 | 26 | 0,01 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | abduccion_cadera_izq | 18,00 | 18,0 | 0 (0,0 %) | 25 | 27 | 46 | 26 | 0,03 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 24,00 | 24,1 | 0 (0,0 %) | 21 | 23 | 44 | 19 | 0,10 |
| PlanchaCorrecta1 (2).mp4 | plancha | 30,00 | 30,0 | 0 (0,0 %) | 20 | 23 | 45 | 17 | -0,02 |
| plancha correcta hombre.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 20 | 22 | 43 | 16 | 0,02 |
| plancha incorrecta 2.mp4 | plancha | 29,97 | 30,2 | 0 (0,0 %) | 18 | 22 | 44 | 22 | 2,01 |
| plancha incorrrecta 1.mp4 | plancha | 29,97 | 30,1 | 0 (0,0 %) | 19 | 22 | 44 | 18 | 0,82 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 29,97 | 29,9 | 5 (0,1 %) | 20 | 23 | 207 | 17 | 0,01 |
| ZANCADA CHICA DERECHA.mp4 | zancada_atras_der | 25,00 | 25,0 | 0 (0,0 %) | 21 | 23 | 46 | 18 | 0,01 |
| ZANCADA CHICA IZQUIERDA.mp4 | zancada_atras_izq | 25,00 | 25,0 | 0 (0,0 %) | 20 | 23 | 44 | 22 | 0,08 |
| der Zancada atrás con Kettlebell Derecha - Ejercicios de la App Malagaentrena.mp4 | zancada_atras_der | 24,00 | 24,0 | 0 (0,0 %) | 27 | 29 | 44 | 25 | 0,15 |
| izq Zancada hacia atrás con peso corporal_ técnica paso a paso.mp4 | zancada_atras_izq | 18,00 | 18,0 | 0 (0,0 %) | 24 | 29 | 53 | 26 | -0,02 |

Total: 16125 de 16131 frames procesados (0,0 % descartados); retraso p50 21 ms, p95 27 ms, máx 207 ms.

### Política «cola sin descarte (como `FuenteVideo`)»

| Vídeo | Ejercicio | FPS fuente | FPS sostenidos | Descartados | Retraso p50 | p95 | máx | final | Deriva |
|---|---|---|---|---|---|---|---|---|---|
| 1 hombre.mp4 | jumping_jacks | 23,98 | 24,0 | 0 (0,0 %) | 19 | 21 | 51 | 21 | 0,14 |
| 2 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 19 | 21 | 44 | 21 | 0,40 |
| 3 mujer.mp4 | jumping_jacks | 29,97 | 30,0 | 0 (0,0 %) | 18 | 19 | 46 | 21 | -0,00 |
| 4 mujer.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 20 | 22 | 46 | 22 | 0,34 |
| 5 hombre.mp4 | jumping_jacks | 25,00 | 25,1 | 0 (0,0 %) | 20 | 22 | 47 | 21 | 0,18 |
| 6 mujer.mp4 | jumping_jacks | 30,00 | 30,1 | 0 (0,0 %) | 16 | 19 | 45 | 19 | 0,58 |
| 7 hombre.mp4 | jumping_jacks | 59,94 | 60,0 | 0 (0,0 %) | 10 | 10 | 43 | 10 | -0,00 |
| 8 hombre.mp4 | jumping_jacks | 30,00 | 30,0 | 0 (0,0 %) | 17 | 20 | 45 | 20 | 0,07 |
| 9 mujer.mp4 | jumping_jacks | 23,98 | 24,1 | 0 (0,0 %) | 20 | 23 | 45 | 22 | 0,37 |
| der 876. Abducción de cadera con apoyo en silla.mp4 | abduccion_cadera_der | 29,97 | 30,0 | 0 (0,0 %) | 17 | 19 | 46 | 39 | 0,07 |
| der Abducción de cadera con banda_ técnica paso a paso.mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 23 | 25 | 46 | 26 | 0,02 |
| der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4 | abduccion_cadera_der | 18,00 | 18,0 | 0 (0,0 %) | 26 | 31 | 46 | 32 | 0,12 |
| izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4 | abduccion_cadera_izq | 18,00 | 18,0 | 0 (0,0 %) | 31 | 33 | 90 | 26 | -0,04 |
| izquierda abductor.mp4 | abduccion_cadera_izq | 24,00 | 24,0 | 0 (0,0 %) | 23 | 26 | 53 | 23 | 0,04 |
| PlanchaCorrecta1 (2).mp4 | plancha | 30,00 | 30,0 | 0 (0,0 %) | 18 | 23 | 50 | 27 | -0,02 |
| plancha correcta hombre.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 18 | 24 | 53 | 16 | 0,04 |
| plancha incorrecta 2.mp4 | plancha | 29,97 | 30,2 | 0 (0,0 %) | 16 | 22 | 54 | 17 | -1,56 |
| plancha incorrrecta 1.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 18 | 24 | 49 | 27 | -0,27 |
| 👉Como hacer plancha abdominal correctamente ✅ Galvistrainer.mp4 | plancha | 29,97 | 30,0 | 0 (0,0 %) | 19 | 25 | 206 | 20 | 0,00 |
| ZANCADA CHICA DERECHA.mp4 | zancada_atras_der | 25,00 | 25,0 | 0 (0,0 %) | 21 | 26 | 52 | 15 | 0,01 |
| ZANCADA CHICA IZQUIERDA.mp4 | zancada_atras_izq | 25,00 | 25,0 | 0 (0,0 %) | 21 | 26 | 52 | 21 | 0,05 |
| der Zancada atrás con Kettlebell Derecha - Ejercicios de la App Malagaentrena.mp4 | zancada_atras_der | 24,00 | 24,0 | 0 (0,0 %) | 19 | 25 | 50 | 21 | 0,01 |
| izq Zancada hacia atrás con peso corporal_ técnica paso a paso.mp4 | zancada_atras_izq | 18,00 | 18,0 | 0 (0,0 %) | 22 | 30 | 54 | 29 | 0,04 |

Total: 16131 de 16131 frames procesados (0,0 % descartados); retraso p50 19 ms, p95 29 ms, máx 206 ms.

`[I]` En vídeo los FPS sostenidos no pueden superar los FPS de la fuente: el objetivo de 25 fps solo se evalúa en vídeos de ≥ 25 fps. La capacidad del equipo (FPS a ritmo máximo) está en la sección 7.

## 4. Detección → inicio de voz

Voz: Piper sin audio (es_MX-claude-high.onnx). Por mensaje: llegada del frame que lo dispara → encolado en `ColaVoz` → empieza a sonar. Política «último frame», ritmo real.

| Tramo (s) | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| frame → encolado | 21 | 0,287 | 0,286 | 0,317 | 0,357 |
| encolado → audio | 21 | 0,073 | 0,072 | 0,085 | 0,085 |
| total (correcciones) | 21 | 0,360 | 0,352 | 0,394 | 0,442 |

Correcciones que esperaron a que terminara otra frase (> 0,1 s en la cola): 0 de 21. Con la cola libre, total p50 0,352 s, p95 0,394 s (n = 21). `[I]` La espera la causan sobre todo el anuncio del ejercicio al empezar y la frase anterior: la cola tiene un solo hueco y no interrumpe lo que está sonando.

Correcciones emitidas: 21; no llegaron a sonar: 0 (0,0 %; por causa: ninguna). «sustituida»: llegó otra más reciente; «aviso»: el hueco lo tenía un aviso; «caducada»: esperó más de 1 s (`MAX_ESPERA_FEEDBACK_S`). El p95 de arriba solo cuenta las que sonaron. Refuerzos: 3.
`[?]` No incluye la latencia del dispositivo de audio.

### Redacción con el LLM

`qwen3:4b-instruct-2507-q4_K_M` por ollama, tiempo límite 400 ms. El motor decide en el frame y el LLM redacta en otro hilo: la corrección se encola cuando la redacción vuelve, así que «frame → encolado» (arriba) incluye ese tiempo. Si el LLM falla, pasa del tiempo límite o el validador rechaza su frase, se dice la plantilla.

| Correcciones | n |
|---|---|
| decididas por el motor (pedidas al LLM) | 21 |
| sustituidas sin redactar (llegó otra mientras esperaban al LLM) | 0 |
| redactadas | 21 |
| — con la frase del LLM | 20 |
| — caídas a plantilla | 1 (por motivo: `sin_correccion` 1) |
| redactadas tarde (al volver ya no tocaba decirlas) | 0 |
| encoladas en la voz | 21 |

| Tiempo de cada redacción (ms) | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| todas | 21 | 265,6 | 264,7 | 294,4 | 330,8 |
| con la frase del LLM | 20 | 266,4 | 265,0 | 296,2 | 330,8 |
| caídas a plantilla | 1 | 249,5 | 249,5 | 249,5 | 249,5 |

Detección → inicio de voz de las correcciones que sonaron, por ejercicio (s):

| Ejercicio | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| abduccion_cadera_der | 6 | 0,350 | 0,350 | 0,369 | 0,372 |
| abduccion_cadera_izq | 3 | 0,400 | 0,394 | 0,437 | 0,442 |
| jumping_jacks | 1 | 0,352 | 0,352 | 0,352 | 0,352 |
| plancha | 11 | 0,355 | 0,351 | 0,390 | 0,392 |
| zancada_atras_der | 0 | n/d | n/d | n/d | n/d |
| zancada_atras_izq | 0 | n/d | n/d | n/d | n/d |

## 5. Silencios por causa

Frames: 16125; sin persona: 797 (4,9 %); en pausa: 0 (0,0 %) ; evaluados por el motor: 11656.

| Motivo (`MOTIVO_*`) | Frames | % de los evaluados |
|---|---|---|
| `sin_error` | 7792 | 66,8 % |
| `periodo_refractario` | 2201 | 18,9 % |
| `desvanecimiento` | 924 | 7,9 % |
| `evidencia_insuficiente` | 453 | 3,9 % |
| `confianza_baja` | 166 | 1,4 % |
| `plano_no_observable` | 96 | 0,8 % |
| corrección | 21 | 0,2 % |
| refuerzo | 3 | 0,0 % |

Por ejercicio (% de los frames evaluados):

| Ejercicio | Frames | Sin persona | En pausa | Evaluados | sin_error | confianza_baja | plano_no_observable | evidencia_insuficiente | refractario | fase_silenciada | otros | mensajes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abduccion_cadera_der | 2538 | 10,6 % | 0,0 % | 1844 | 69,0 % | n/d | n/d | 2,8 % | 23,9 % | n/d | 4,0 % | 6 |
| abduccion_cadera_izq | 803 | 0,0 % | 0,0 % | 422 | 73,7 % | n/d | n/d | 3,3 % | 22,3 % | n/d | 0 % | 3 |
| jumping_jacks | 4024 | 0,3 % | 0,0 % | 2605 | 95,5 % | 0,3 % | n/d | 3,3 % | 0,8 % | n/d | 0 % | 4 |
| plancha | 5718 | 4,4 % | 0,0 % | 4730 | 39,9 % | n/d | 0,8 % | 6,3 % | 34,8 % | n/d | 18,0 % | 11 |
| zancada_atras_der | 973 | 0,0 % | 0,0 % | 504 | 87,9 % | n/d | 11,9 % | 0,2 % | n/d | n/d | 0 % | 0 |
| zancada_atras_izq | 2069 | 12,7 % | 0,0 % | 1551 | 89,7 % | 10,3 % | n/d | n/d | n/d | n/d | 0 % | 0 |

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

## 8. DTW incremental sin banda frente a banda Sakoe-Chiba (EXP-010)

Réplica fuera de línea de las observaciones de la corrida «cola» (modelo heavy), con las mismas llamadas que hace la sesión. Banda en frames = fracción × longitud de la referencia (0,10, 0,20).

| Ejercicio | Ref. (frames) | Variante | Frames | Con resultado | Latencia media | p50 | p95 | máx | ms por frame de prefijo | Prefijo máx | progreso = 1 | Δ progreso máx | Δ ángulos_ref máx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jumping_jacks | 62 | sin banda | 4012 | 98,0 % | 0,02 | 0,02 | 0,02 | 0,08 | 0,000 | 330 | 0,4 % | n/d | n/d |
| jumping_jacks | 62 | banda 10% (6 fr) | 4012 | 98,0 % | 0,01 | 0,01 | 0,02 | 0,03 | 0,000 | 330 | 8,0 % | 0,918 | 124,14 |
| jumping_jacks | 62 | banda 20% (12 fr) | 4012 | 98,0 % | 0,02 | 0,02 | 0,02 | 0,05 | -0,000 | 330 | 7,7 % | 0,902 | 124,14 |
| abduccion_cadera_der | 55 | sin banda | 2268 | 96,9 % | 0,02 | 0,02 | 0,02 | 0,04 | 0,000 | 114 | 1,0 % | n/d | n/d |
| abduccion_cadera_der | 55 | banda 10% (6 fr) | 2268 | 96,4 % | 0,01 | 0,01 | 0,02 | 0,04 | 0,000 | 114 | 2,5 % | 0,593 | 44,44 |
| abduccion_cadera_der | 55 | banda 20% (11 fr) | 2268 | 96,4 % | 0,02 | 0,02 | 0,02 | 0,04 | 0,000 | 114 | 1,6 % | 0,556 | 34,96 |
| abduccion_cadera_izq | 55 | sin banda | 803 | 69,2 % | 0,01 | 0,02 | 0,02 | 0,03 | 0,000 | 56 | 0,0 % | n/d | n/d |
| abduccion_cadera_izq | 55 | banda 10% (6 fr) | 803 | 69,2 % | 0,01 | 0,01 | 0,02 | 0,02 | 0,000 | 56 | 0,5 % | 0,463 | 8,22 |
| abduccion_cadera_izq | 55 | banda 20% (11 fr) | 803 | 69,2 % | 0,01 | 0,02 | 0,02 | 0,02 | 0,000 | 56 | 0,5 % | 0,463 | 8,22 |
| plancha | — | sin referencia DTW (isométrico o ausente) | | | | | | | | | | | |
| zancada_atras_der | 44 | sin banda | 973 | 97,1 % | 0,02 | 0,02 | 0,02 | 0,05 | 0,000 | 69 | 11,4 % | n/d | n/d |
| zancada_atras_der | 44 | banda 10% (4 fr) | 973 | 97,1 % | 0,01 | 0,01 | 0,02 | 0,04 | 0,000 | 69 | 11,3 % | 0,814 | 64,99 |
| zancada_atras_der | 44 | banda 20% (9 fr) | 973 | 97,1 % | 0,01 | 0,01 | 0,02 | 0,03 | 0,000 | 69 | 11,4 % | 0,791 | 64,99 |
| zancada_atras_izq | 45 | sin banda | 1806 | 99,2 % | 0,02 | 0,02 | 0,02 | 0,04 | 0,000 | 125 | 0,0 % | n/d | n/d |
| zancada_atras_izq | 45 | banda 10% (4 fr) | 1806 | 98,7 % | 0,01 | 0,01 | 0,01 | 0,04 | -0,000 | 125 | 35,1 % | 0,841 | 80,44 |
| zancada_atras_izq | 45 | banda 20% (9 fr) | 1806 | 98,7 % | 0,01 | 0,01 | 0,02 | 0,04 | -0,000 | 125 | 29,7 % | 0,841 | 78,87 |

Latencia según la longitud del prefijo, todos los ejercicios juntos (ms):

| Prefijo (frames) | Variante | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|---|
| 1–15 | sin banda | 2951 | 0,02 | 0,02 | 0,02 | 0,08 |
| 16–30 | sin banda | 2497 | 0,02 | 0,02 | 0,02 | 0,05 |
| 31–60 | sin banda | 3259 | 0,02 | 0,02 | 0,02 | 0,04 |
| 61–120 | sin banda | 499 | 0,02 | 0,02 | 0,02 | 0,04 |
| 121–240 | sin banda | 125 | 0,02 | 0,02 | 0,02 | 0,03 |
| 241–∞ | sin banda | 90 | 0,02 | 0,02 | 0,03 | 0,04 |
| 1–15 | banda 10% | 2956 | 0,01 | 0,01 | 0,02 | 0,03 |
| 16–30 | banda 10% | 2492 | 0,01 | 0,01 | 0,02 | 0,04 |
| 31–60 | banda 10% | 3259 | 0,01 | 0,01 | 0,02 | 0,04 |
| 61–120 | banda 10% | 499 | 0,01 | 0,01 | 0,02 | 0,04 |
| 121–240 | banda 10% | 125 | 0,01 | 0,01 | 0,02 | 0,02 |
| 241–∞ | banda 10% | 90 | 0,01 | 0,01 | 0,01 | 0,02 |
| 1–15 | banda 20% | 2956 | 0,02 | 0,02 | 0,02 | 0,05 |
| 16–30 | banda 20% | 2492 | 0,02 | 0,02 | 0,02 | 0,03 |
| 31–60 | banda 20% | 3259 | 0,02 | 0,02 | 0,02 | 0,04 |
| 61–120 | banda 20% | 499 | 0,01 | 0,01 | 0,02 | 0,03 |
| 121–240 | banda 20% | 125 | 0,01 | 0,01 | 0,02 | 0,02 |
| 241–∞ | banda 20% | 90 | 0,01 | 0,01 | 0,02 | 0,02 |

El DTW es incremental y de final abierto: cada frame actualiza una columna de la matriz en O(m) y se reinicia en cada repetición, así que la latencia no debería crecer con el prefijo (columna «ms por frame de prefijo»). La banda se centra en el instante que tocaría al ritmo de la referencia; las columnas «Δ» comparan cada banda con la variante sin banda.

## 9. Plantilla frente a LLM local (EXP-001, banco sintético)

| Condición | Episodios | M2 aserciones no soportadas | M3 sobrecorrección | M5 determinismo | M7 fallback | Verbalización p50 (ms) | p95 | máx |
|---|---|---|---|---|---|---|---|---|
| A | 163 | 0,0 % (174) | 0,0 % (18) | 100,0 % | 0,0 % | 0,0480 | 0,0667 | 0,0718 |
| F | pendiente de medición en la Mac: llama-server no responde en http://127.0.0.1:8080 (URLError) | | | | | | | |

La M1 real (exactitud de contenido) y la comparación sobre vídeo necesitan las anotaciones (sección 6). La condición F solo puede correr donde haya `llama-server` (la Mac).

## 10. Piper: factor de tiempo real

Voz `es_MX-claude-high.onnx`, 207 frases de `frases_de_rutina` (calentamiento básico). RTF = tiempo de síntesis / duración del audio; < 1 es más rápido que el tiempo real. La primera frase (inicialización) tardó 37 ms y no entra en la tabla.

| Medida | n | media | p50 | p95 | máx |
|---|---|---|---|---|---|
| síntesis (ms) | 206 | 47,3 | 43,7 | 79,9 | 125,4 |
| duración del audio (s) | 206 | 3,09 | 2,87 | 5,15 | 7,59 |
| RTF | 206 | 0,016 | 0,015 | 0,018 | 0,022 |

## Pendiente de medición

- **exp001_F**: pendiente de medición en la Mac: llama-server no responde en http://127.0.0.1:8080 (URLError)
- **anotaciones**: pendiente de medición: no hay anotaciones humanas (formato estela-anotacion-v1 en ESTELA/backend/datos_locales/anotaciones); las 5 sesiones grabadas aún no existen
- **sesiones reales**: las 5 participantes aún no han grabado la rutina; ninguna cifra de esta página procede de ellas.

