# Resultados del Mac Studio para el Informe Final

Rama `feature/mac-flujo`. Código medido: el de `6424b08` (`main` del 22-nov), copiado a la copia de medición del Mac (`~/estela-mac/ESTELA`); la herramienta del paso 3 es la de `37e9520`. Equipo: Mac Studio M2 Ultra, 128 GB, macOS 26.3.2.
Fechas: los pasos 0, 1, 2 y 3 se midieron el 2026-11-22. Las secciones con «(20-nov)» en el título se midieron o revisaron el 2026-11-20 en el mismo equipo y no se repitieron.
Etiquetas: `[F]` medido o comprobado en este Mac en la fecha de su sección · `[F-2]` tomado de un commit, de `ESTADO.md` o de un archivo de resultados anterior · `[?]` no se pudo medir · `[I]` deducido de lo medido o del código.
Este archivo solo contiene métricas. No contiene audio, vídeo ni el texto de lo que dijo nadie.
Commits de este trabajo en la rama: `37e9520` lleva la herramienta del paso 3, su prueba y el arreglo de una línea del paso 5 (su mensaje dice «Actualizacion de Informe» y metió por error `backend/.DS_Store`, que `1bba5af` quita); `42bd098` trae los pasos 0, 1 y 2, y el paso 3 llega con el commit de esta versión.

**Estado:** medidos los pasos 0, 1, 2 y 3. Quedan pendientes los pasos 5 y 7, que se hacen frente al Mac; su guía está más abajo.

---

## Paso 0 · Preparación (22-nov)

Comandos, en el clon (`~/Desktop/estela/ESTELA`):
```
git fetch origin
git checkout feature/mac-flujo
git merge --ff-only origin/feature/mac-flujo    # 267bfd9 → 702ce21, 18 commits
git merge --ff-only origin/main                 # 702ce21 → 6424b08, 32 commits
git config core.hooksPath .githooks             # no estaba definido
diff -rq <clon>/backend/{estela,scripts,feedback_testing,tests} ~/estela-mac/ESTELA/backend/…
```
y, en la copia de medición: `cd ~/estela-mac/ESTELA/backend && .venv/bin/python -m pytest -q -rs`.

| Dato | Valor | Etiqueta |
|---|---|---|
| Rama local | Tras los dos avances rápidos, sin commit de fusión, `feature/mac-flujo` quedó en `6424b08`, igual a `origin/main`. Encima van los commits de este trabajo (ver la cabecera) | [F] |
| Commits pedidos | `267bfd9` y `4336bdf` están en la rama | [F] |
| `main` respecto a `origin/feature/mac-flujo` | 32 commits por delante (el encargo decía 29). Los 3 nuevos (`754f2d8`, `111f705`, `6424b08`) solo tocan documentos | [F] |
| Código que difiere entre el clon y la copia de medición | Lo esperado: `scripts/visor_calibracion.py` (solo en el clon), `tests/test_dtw_video.py` y `tests/test_gesto.py` | [F] |
| Otras diferencias | Archivos de resultados: tres `INFORME2-metricas_*` que llegaron con `main` y un `INFORME2-metricas.json` ignorado por git en la copia. No son código | [F] |
| Cambio local sin confirmar en el clon | `backend/estela/__main__.py` estaba modificado (20-nov, 20:31): es idéntico al del commit `d4c2742` (17-nov). La versión confirmada (`373b6b1`) es la misma en `6424b08`, en `267bfd9` y en la copia de medición, así que las mediciones usan la versión confirmada. Con autorización, el 22-nov se restauró en el clon a la versión confirmada; la copia vieja quedó fuera del repo, en `~/revision-experimentos/respaldo-clon/` | [F] |
| Hook de commits | `core.hooksPath` no estaba definido; se puso `.githooks` | [F] |
| Pruebas que pasan | 732 en `6424b08`, con los tres archivos ya copiados (731 en `082c2e3`, el 20-nov) | [F] |
| Pruebas que fallan | 0 | [F] |
| Pruebas omitidas | 0 | [F] |
| Fuera por la marca `metricas` | 12 (`pyproject.toml` las excluye por defecto) | [F] |
| Duración | 33,9 s | [F] |
| Diferencia con Windows (720 pasan y 5 se omiten, según `InformeFinal.md`) | En Windows se omiten las 4 pruebas de `tests/test_dtw_video.py` (falta el vídeo de prueba) y el módulo `tests/test_voz_entrada_real.py` entero (falta Whisper), que cuenta como una omisión y tiene 8 pruebas (lectura del código). En el Mac están el vídeo y Whisper: corren las 12, y 720 + 12 = 732 | [F] |

Los tres archivos se copiaron del clon a la copia de medición; los dos que ya existían quedaron como `.bak`. Son dos pruebas y un script que la app no usa: no cambian las mediciones. Los pasos 1 y 2 se midieron antes de copiarlos.

Entorno (leído el 20-nov; el 22-nov se volvieron a leer macOS, Python, mediapipe y Ollama, sin cambios):

| Dato | Valor | Etiqueta |
|---|---|---|
| macOS | 26.3.2 (25D2140) | [F] |
| Procesador | Apple M2 Ultra, 128 GB | [F] |
| Python (entorno de la app) | 3.14.6, entorno creado con uv 0.11.28 | [F] |
| mediapipe | 1.2.3 | [F] |
| Ollama | 0.40.6 | [F] |
| Modelos de Ollama | `qwen3:4b-instruct-2507-q4_K_M` 2,5 GB · `qwen3:14b` 9,3 GB · `llama3.3:70b` 42 GB · `phi4-mini` 2,5 GB · `qwen3:1.7b` 1,4 GB | [F] |
| pywhispercpp | 1.5.1, rueda precompilada `cp314-macosx_11_0_arm64`; informa `MTL: EMBED_LIBRARY = 1` (Metal) | [F] |
| Versión de whisper.cpp dentro de pywhispercpp | no la expone la librería | [?] |
| Modelo de voz de entrada | `ggml-small.bin`, 487 601 967 bytes | [F] |
| Voz de salida | Piper `es_MX-claude-high`; piper-tts 1.8.0 | [F] |
| Ventana | pywebview 6.2.1 | [F] |

Resultados: `~/estela-mac/resultados/MAC-pytest-paso0.log`.

---

## Paso 1 · Tiempos con la zancada (OE1) (22-nov)

Comandos, desde `~/estela-mac/ESTELA/backend`, una corrida tras otra con `nohup` y `/usr/bin/time -l` delante (para leer la memoria máxima):
```
.venv/bin/python -m feedback_testing.informe2 --salida-md feedback_testing/resultados/MAC-cpu-full.md --salida-json feedback_testing/resultados/MAC-cpu-full.json
.venv/bin/python -m feedback_testing.informe2 --modelo heavy --delegado gpu --salida-md feedback_testing/resultados/MAC-gpu-heavy.md --salida-json feedback_testing/resultados/MAC-gpu-heavy.json
```
Antes de cada corrida no había ventanas de ESTELA abiertas ni ningún proceso por encima del 7 % de CPU (`top`; el más alto era el propio `top`). Las dos terminaron sin errores: a) de 16:19 a 16:54 y b) de 16:54 a 17:18.

Vídeos: 23 (621 s), que son los 19 de la medición anterior más 4 de zancada. Se reproducen a ritmo real. Las cifras son de la política «último frame», la que se comporta como la cámara y la que usa el informe.

### Totales

| Métrica (objetivo) | a) *full* en CPU | b) *heavy* en GPU, la configuración del Mac | Etiqueta |
|---|---|---|---|
| Imágenes procesadas | 16 131 | 16 125 | [F] |
| Pose p50 / p95 / máx (p95 ≤ 33 ms) | 14,5 / 21,3 / 45,4 ms | 13,6 / 16,5 / 199,7 ms | [F] |
| Imágenes con la pose por encima de 33 ms | 9 (0,06 %) | 42 (0,26 %); dos pasan de 60 ms (67 y 200 ms) | [F] |
| Total por imagen, p95 | 22,08 ms | 20,55 ms | [F] |
| Mínimo de imágenes por segundo en los vídeos de 25 o más (≥ 25) | 25,0 (15 vídeos) | 25,0 (15 vídeos) | [F] |
| Imágenes descartadas | 0 de 16 131 | 6 de 16 131 (0,04 %): 5 en la plancha larga y 1 en *jumping jacks* | [F] |
| De la detección a la voz, p95 (≤ 1 s) | 0,07 s (17 correcciones) | 0,10 s (21 correcciones) | [F] |
| Correcciones que esperaron a otra frase (> 0,1 s en la cola) | 0 de 17 | 0 de 21 | [F] |
| Mensajes no respaldados (0 %) | 0 de 17 | 0 de 21 | [F] |
| Memoria máxima del proceso de medición | 1,47 GB | 3,82 GB | [F] |

- El mínimo de imágenes por segundo sale en las dos corridas del mismo vídeo, `ZANCADA CHICA DERECHA.mp4`, de 25 por segundo: 25,04 en a) y 25,03 en b). Un vídeo no puede dar más imágenes por segundo que las que tiene.
- La memoria es el máximo de todo el proceso de `informe2`, que crea un estimador nuevo en cada reproducción (115 por corrida). No es la memoria de la app, que usa un solo estimador.
- Con los mismos 19 vídeos de la medición anterior, la corrida a) da 20,6 ms de pose (p95) en 13 089 imágenes, un mínimo de 25,1 imágenes por segundo y 0 descartadas `[F]`. La medición anterior daba 20,7 ms, 25,1 y 0 `[F-2]`. La zancada añade 3 042 imágenes.

### Por ejercicio

| Ejercicio | Vídeos | a) Imágenes | a) Pose p50 / p95 | a) Mín. imágenes/s | a) Descartadas | b) Imágenes | b) Pose p50 / p95 | b) Mín. imágenes/s | b) Descartadas | Etiqueta |
|---|---|---|---|---|---|---|---|---|---|---|
| *Jumping jacks* | 9 | 4 025 | 14,0 / 15,4 ms | 25,1 (7 vídeos) | 0 | 4 024 | 9,7 / 14,9 ms | 25,1 (7) | 1 | [F] |
| Abducción derecha | 3 | 2 538 | 19,6 / 22,1 ms | 30,0 (1) | 0 | 2 538 | 14,9 / 20,0 ms | 30,0 (1) | 0 | [F] |
| Abducción izquierda | 2 | 803 | 19,5 / 21,9 ms | sin vídeos de ≥ 25 | 0 | 803 | 14,3 / 15,7 ms | sin vídeos de ≥ 25 | 0 | [F] |
| Plancha | 5 | 5 723 | 14,3 / 15,0 ms | 30,0 (5) | 0 | 5 718 | 13,0 / 15,3 ms | 29,9 (5) | 5 | [F] |
| **Zancada derecha** | 2 | 973 | 15,6 / 17,2 ms | 25,0 (1) | 0 | 973 | 14,3 / 15,8 ms | 25,0 (1) | 0 | [F] |
| **Zancada izquierda** | 2 | 2 069 | 20,0 / 22,7 ms | 25,0 (1) | 0 | 2 069 | 15,3 / 20,6 ms | 25,0 (1) | 0 | [F] |
| Zancada, las dos piernas | 4 | 3 042 | 19,1 / 22,2 ms | 25,0 (2) | 0 | 3 042 | 14,9 / 20,1 ms | 25,0 (2) | 0 | [F] |
| **Total** | 23 | 16 131 | 14,5 / 21,3 ms | 25,0 (15) | 0 | 16 125 | 13,6 / 16,5 ms | 25,0 (15) | 6 | [F] |

| Ejercicio | a) Correcciones | a) Detección a voz, p95 | a) No respaldados | b) Correcciones | b) Detección a voz, p95 | b) No respaldados | Etiqueta |
|---|---|---|---|---|---|---|---|
| *Jumping jacks* | 1 (y 4 refuerzos) | 0,02 s | 0 de 1 | 1 (y 3 refuerzos) | 0,02 s | 0 de 1 | [F] |
| Abducción derecha | 6 | 0,07 s | 0 de 6 | 6 | 0,10 s | 0 de 6 | [F] |
| Abducción izquierda | 3 | 0,06 s | 0 de 3 | 3 | 0,08 s | 0 de 3 | [F] |
| Plancha | 7 (y 1 refuerzo) | 0,07 s | 0 de 7 | 11 | 0,11 s | 0 de 11 | [F] |
| Zancada derecha | 0 | sin correcciones | — | 0 | sin correcciones | — | [F] |
| Zancada izquierda | 0 (y 3 refuerzos) | sin correcciones | — | 0 | sin correcciones | — | [F] |
| **Total** | 17 (y 8 refuerzos) | 0,07 s | 0 de 17 | 21 (y 3 refuerzos) | 0,10 s | 0 de 21 | [F] |

Ninguna corrección esperó a otra frase en ningún ejercicio. En la zancada el motor no decidió ninguna corrección, así que no hay tiempo de la detección a la voz que medir para ese ejercicio.

**Por qué la voz ya no empieza a 0,03 s.** Desde `cbfb1bb` y `082c2e3` (20-nov) cada corrección rota entre más frases fijas, pero el precalentado de la voz (`frases_de_rutina`) solo sintetiza las tres primeras variantes de cada regla. Una frase que no estaba sintetizada se sintetiza al decirla. Comprobado frase a frase contra el JSON `[F]`:

| | a) *full* en CPU | b) *heavy* en GPU |
|---|---|---|
| Correcciones con la frase ya sintetizada | 9: la voz empieza a 0,03 s (p95) | 10: 0,03 s |
| Correcciones con una variante sin sintetizar | 8: tardan entre 36 y 49 ms más; 0,07 s (p95) | 11: tardan hasta 82 ms más; 0,11 s (p95) |

En la segunda pasada de cada corrida (política «cola»), con todas las frases ya sintetizadas, el p95 vuelve a 0,03 s en las dos.

### Motivos de silencio

Imágenes que evaluó el motor y en qué acabó cada una:

| Motivo | a) *full* en CPU (11 732) | b) *heavy* en GPU (11 731) | Etiqueta |
|---|---|---|---|
| Sin error (`sin_error`) | 74,7 % | 67,1 % | [F] |
| Tiempo mínimo entre mensajes (`periodo_refractario`) | 11,7 % | 18,8 % | [F] |
| Intervalo creciente antes de repetir (`desvanecimiento`) | 7,6 % | 7,9 % | [F] |
| Evidencia insuficiente (`evidencia_insuficiente`) | 3,5 % | 3,8 % | [F] |
| Orientación (`plano_no_observable`) | 2,3 % | 0,8 % | [F] |
| Confianza baja (`confianza_baja`) | 0 % | 1,4 % | [F] |
| Mensaje (corrección o refuerzo) | 0,2 % (25) | 0,2 % (24) | [F] |

Sin persona: 677 imágenes (4,2 %) en a) y 797 (4,9 %) en b). En pausa: ninguna.

En la zancada:

| | a) Evaluadas | a) Reparto | b) Evaluadas | b) Reparto | Etiqueta |
|---|---|---|---|---|---|
| Zancada derecha | 506 de 973 | 69,8 % sin error; 30,2 % orientación | 514 de 973 | 88,1 % sin error; 11,7 % orientación; 0,2 % evidencia insuficiente | [F] |
| Zancada izquierda | 1 602 de 2 069 (208 sin persona) | 96,6 % sin error; 3,2 % orientación; 0,2 % refuerzos | 1 555 de 2 069 (263 sin persona) | 89,6 % sin error; 10,4 % confianza baja | [F] |

### Vídeos de zancada

| Vídeo | ¿Entró? | Repeticiones contadas a) / b) | Imágenes evaluadas a) / b) | Etiqueta |
|---|---|---|---|---|
| `ZANCADA CHICA DERECHA.mp4` (12,9 s, 25 imágenes/s) | Sí, derecha | 7 / 7 | 133 / 136 | [F] |
| `ZANCADA CHICA IZQUIERDA.mp4` (12,8 s, 25 imágenes/s) | Sí, izquierda | 7 / 7 | 139 / 139 | [F] |
| `der Zancada atrás con Kettlebell…mp4` (27,3 s, 24 imágenes/s) | Sí, derecha | 11 / 11 | 373 / 378 | [F] |
| `izq Zancada hacia atrás con peso corporal…mp4` (97,3 s, 18 imágenes/s) | Sí, izquierda | 29 / 24 | 1 463 / 1 416 | [F] |
| `videoplayback.mp4`, `(1)`, `(2)` y `(3)` | No: el nombre no dice el lado | — | — | [F] |

- Los dos «ZANCADA CHICA» se sacaron de `docs_estela` (`origin/main`) a `~/estela-mac/docs_estela/…/Zancada atrás estática por pierna/`, sin añadirlos a ningún repositorio. Son además los vídeos de referencia de la zancada. Los `videoplayback` no se renombraron.
- `informe2` no pasa por la fase de colocación (su sesión cuenta desde la primera imagen), así que aquí no se puede ver si un vídeo «no pasa de la colocación». Eso se mira en el paso 2, que sí usa la app completa.

### Comparación de modelos (misma herramienta, 9 976 imágenes, lo más rápido posible)

| Modelo | CPU: pose p95 / capacidad | GPU: pose p95 / capacidad | Etiqueta |
|---|---|---|---|
| *lite* | 8,9 ms / 107 imágenes/s | 3,5 ms / 234 | [F] |
| *full* | 14,5 ms / 69 | 3,6 ms / 231 | [F] |
| *heavy* | 59,5 ms / 18 | 5,4 ms / 167 | [F] |

En el informe (19 vídeos) son 8,7, 14,0 y 58,4 ms en CPU `[F-2]`. Piper sintetizó cada frase en 44 ms de mediana (factor de tiempo real de 0,015) en las dos corridas `[F]`; el informe dice 52,6 ms `[F-2]`.

Resultados: `backend/feedback_testing/resultados/MAC-cpu-full.{md,json}` y `MAC-gpu-heavy.{md,json}` (en el repositorio). Registros: `~/estela-mac/resultados/MAC-cpu-full.log` y `MAC-gpu-heavy.log`.

---

## Paso 2 · «Todas las funciones a la vez», repetido (22-nov)

Comando, desde `~/estela-mac/ESTELA/backend` (la segunda corrida es igual con `--cada-s 0.3` y la salida `todo-a-la-vez-v2-cada03`):
```
.venv/bin/python scripts/voz/medir_todo_a_la_vez.py --salida ~/estela-mac/resultados/todo-a-la-vez-v2 --historial datos_locales/historial_ejemplo.jsonl --videos \
  "<Jumping Jacks/7 hombre.mp4>:jumping_jacks" "<Abdu…/izq-ok-….mp4>:abduccion_cadera_izq" \
  "<Zancada…/der Zancada atrás con Kettlebell….mp4>:zancada_atras_der" "<Plancha/…Galvistrainer.mp4>:plancha" \
  "<Zancada…/ZANCADA CHICA DERECHA.mp4>:zancada_atras_der" "<Zancada…/ZANCADA CHICA IZQUIERDA.mp4>:zancada_atras_izq"
```
Son los 4 vídeos de `8dfd164` más los dos de zancada nuevos: 8 334 imágenes por condición, de las que 7 017 tienen tiempo total (hay persona y no hay pausa). Modelo y delegado por defecto del Mac (*heavy* en GPU). «base» es la pose con las reglas; «todo» añade el LLM que redacta, Piper sintetizando y Whisper reconociendo una orden cada 2,0 s o cada 0,3 s. Las dos corridas terminaron sin errores (17:18–17:27 y 17:27–17:36).

| Corrida | Condición | Pose p50 / p95 / máx | Total por imagen, p95 | Imágenes > 33 ms y máximo | Whisper p50 / p95 | Piper p50 / p95 | Etiqueta |
|---|---|---|---|---|---|---|---|
| Cada 2,0 s | base | 10,8 / 14,3 / 275 ms | 20,1 ms | 3 de 7 017; 276 ms | — | — | [F] |
| Cada 2,0 s | todo | 10,5 / 14,4 / 196 ms | 20,0 ms | 4 de 7 017; 196 ms | 94 / 113 ms (129 órdenes) | 70 / 154 ms (17 frases) | [F] |
| Cada 0,3 s | base | 10,9 / 14,5 / 279 ms | 20,2 ms | 3 de 7 017; 280 ms | — | — | [F] |
| Cada 0,3 s | todo | 9,5 / 14,7 / 198 ms | 18,9 ms | 1 de 7 017; 198 ms | 73 / 90 ms (734 órdenes) | 58 / 142 ms (15 frases) | [F] |

«Imágenes > 33 ms» son las que tienen un tiempo total por encima de 33,3 ms, que es como las cuenta el script.

El LLM redactó 11 correcciones en la corrida de 2,0 s (p50 de 260 ms, p95 de 351 ms, máximo de 403,5 ms; una cayó a plantilla por pasar del límite de 400 ms: fue la primera llamada al modelo desde que se reinició el Mac) y 12 en la de 0,3 s (260, 308 y 319 ms; tres cayeron a plantilla porque el validador rechazó la frase: dos por omitir el lado y una por no pedir la corrección) `[F]`. Esas redacciones ya no están dentro del tiempo de ninguna imagen.

### Comparación con las mediciones anteriores

Solo los 4 vídeos de entonces (7 694 imágenes), con todo encendido:

| Medición | Imágenes > 33 ms | Máximo | Con la pose sola | Etiqueta |
|---|---|---|---|---|
| `8dfd164` (16-nov), con el LLM dentro del ciclo de cada imagen | 10 | 314 ms | 0 | [F-2] |
| Después de `b9b918c` (17-nov, `ESTADO.md`) | 1 | 37,6 ms | 0 | [F-2] |
| 20-nov, con `--cada-s 0.3` (`resultados/todo-a-la-vez-aviso/`) | 1 | 207 ms | 3 (máximo 272 ms) | [F-2] |
| Hoy, cada 2,0 s | 4 | 196 ms | 3 (máximo 276 ms) | [F] |
| Hoy, cada 0,3 s | 1 | 198 ms | 3 (máximo 280 ms) | [F] |

Los dos vídeos de zancada nuevos no tienen ninguna en ninguna condición: su tiempo total máximo es de 22 ms `[F]`.

**No se confirma que ninguna imagen pase de 33 ms.** Lo que sí se confirma es que el LLM ya no las causa:

- **La imagen más lenta es la renovación del detector de la GPU, no el LLM.** Aparece en las cuatro sesiones del vídeo largo de plancha, también con la pose sola, y el registro de cada una anota una renovación `[F]`. En «base» es exactamente la imagen 3 600 (275 y 279 ms) y en «todo» la 3 006 (196 y 198 ms) `[F]`. El detector se renueva cada 1 800 imágenes para soltar la memoria que retiene MediaPipe con la GPU, y el cambio espera a un momento sin evaluación (un aviso, una pausa o la colocación) con tope en 3 600 (`estimador.py`). En «todo» cayó durante un aviso hablado; en «base» la voz es de texto, no hay momento libre y se hace al llegar al tope `[I]`. Es decir: en dos minutos seguidos sin ningún aviso, una imagen tarda unos 280 ms.
- **Las demás pasan de 33 ms por poco:** entre 33,5 y 40,4 ms, y hay tantas con la pose sola (2 por corrida) como con todo encendido (3 y 0) `[F]`.
- Aparte, la primera imagen de cada una de las 24 sesiones tarda entre 40 y 55 ms en la pose `[F]`. Cae en la colocación, donde no se evalúa nada, y por eso no entra en el tiempo total ni en la cuenta de arriba.

### Colocación en los vídeos de zancada

| Vídeo | Imágenes con tiempo total (de las del vídeo) | ¿Pasó de la colocación? | Correcciones | Etiqueta |
|---|---|---|---|---|
| `der Zancada atrás con Kettlebell…mp4` | 153 de 653 | Sí. En `8dfd164` fueron 0 de 653 `[F-2]` | 0 | [F] |
| `ZANCADA CHICA DERECHA.mp4` | 242 de 320 | Sí | 0 | [F] |
| `ZANCADA CHICA IZQUIERDA.mp4` | 242 de 320 | Sí | 0 | [F] |

Las cifras son iguales en las cuatro sesiones de cada vídeo (dos corridas, dos condiciones).

### Qué no cubre esta medición

- **La entrenadora no llegó a hablar** en ninguna de las 12 sesiones «todo» `[F]`. Desde `3c7d229` no habla entre ejercicios y el vídeo se acaba antes del final de la rutina, así que «todo» ya no incluye llamadas al modelo de la entrenadora. En `8dfd164` sí hablaba entre los dos pasos (1,0–1,4 s por respuesta) `[F-2]`. Para incluirla habría que lanzar la app con `--entrenadora-entre si` desde el script, que hoy no lo permite.
- **Antes de la corrida de 0,3 s, el Monitor de Actividad estaba al 13,3 % de CPU** (`top`), por encima del 10 % acordado. En las demás corridas del día estaba en torno al 1 %. Se decidió no repetirla (22-nov); sus cifras son parecidas a las de la corrida de 2,0 s y a las del 20-nov.
- Memoria: el proceso más grande de cada corrida llegó a 3,95 GB de RSS (`/usr/bin/time -l`) `[F]`. No se sabe cuál de las 12 sesiones fue; las de «todo» cargan además Whisper y Piper en el mismo proceso.

Resultados: `~/estela-mac/resultados/todo-a-la-vez-v2/` y `todo-a-la-vez-v2-cada03/` (`todo_a_la_vez.json` y un `.json` y un `.log` por sesión), con sus registros `todo-a-la-vez-v2.log` y `todo-a-la-vez-v2-cada03.log`. No están en el repositorio.

---

## Paso 3 · De la detección a la voz con el LLM encendido (OE4) (22-nov)

Hasta hoy ninguna herramienta medía de la detección a la voz con el LLM encendido: `informe2.py` usaba siempre plantillas.

**Herramienta nueva (commit `37e9520`):** `informe2.py --verbalizador llm`.
- Crea el verbalizador igual que la app (`__main__._crear_verbalizador`: mismo modelo, backend y límite de tiempo), espera a que el modelo esté cargado y lo pasa a `Sesion(..., verbalizador=v, verbalizar_aparte=True)`.
- `deteccion_a_voz()` mide cada frase desde la llegada de la imagen en que se detectó el error hasta que empieza a sonar. Cuenta aparte las correcciones sustituidas mientras esperaban al LLM y las que volvieron tarde.
- Apunta el tiempo de cada redacción y si cayó a plantilla (y por qué).
- Prueba nueva: `tests/test_informe2_llm.py`, 5 casos con un verbalizador falso y lento, sin Ollama.

### Comprobación: sin `--verbalizador llm` sale lo mismo que antes

Comando: el de la corrida b) del paso 1 con `--sin-modelos`, ya con el código nuevo y con la salida en `~/estela-mac/resultados/paso3-sin-llm/` (17:38–17:59).

| | Paso 1 b), código anterior | Código nuevo, sin LLM | Etiqueta |
|---|---|---|---|
| Imágenes procesadas | 16 125 | 16 125 | [F] |
| Pose p95 | 16,5 ms | 16,0 ms | [F] |
| Correcciones (y refuerzos) | 21 (y 3) | 21 (y 3), las mismas por ejercicio: 1, 6, 3 y 11, y ninguna en la zancada | [F] |
| De la detección a la voz, p50 / p95 / máx | 0,03 / 0,10 / 0,11 s | 0,03 / 0,10 / 0,10 s | [F] |
| Segunda pasada («cola») | 22 correcciones; 0,03 s (p95) | 22 correcciones; 0,03 s (p95) | [F] |
| Pruebas en la copia de medición | 732 pasan | 737 pasan (las 5 nuevas), 0 fallan, 0 omitidas, en 35,9 s | [F] |

### Medición con el LLM

Comando (18:00–18:21), con la configuración real del Mac:
```
.venv/bin/python -m feedback_testing.informe2 --modelo heavy --delegado gpu --verbalizador llm --sin-modelos --salida-md feedback_testing/resultados/MAC-gpu-heavy-llm.md --salida-json feedback_testing/resultados/MAC-gpu-heavy-llm.json
```
Modelo `qwen3:4b-instruct-2507-q4_K_M` por Ollama, límite de 400 ms por frase y temperatura 0,7: los valores de la app. El modelo ya estaba cargado al empezar. Antes de la corrida ningún proceso pasaba del 7 % de CPU. Son los mismos 23 vídeos a ritmo real, con la política «último frame» y Piper sin audio.

| De la detección a la voz | Correcciones | p50 | p95 | Máximo | Etiqueta |
|---|---|---|---|---|---|
| **Total** | 21 | 0,35 s | 0,39 s | 0,44 s | [F] |
| *Jumping jacks* | 1 | 0,35 s | — | 0,35 s | [F] |
| Abducción derecha | 6 | 0,35 s | 0,37 s | 0,37 s | [F] |
| Abducción izquierda | 3 | 0,39 s | 0,44 s | 0,44 s | [F] |
| Plancha | 11 | 0,35 s | 0,39 s | 0,39 s | [F] |
| Zancada derecha e izquierda | 0 | — | — | — | [F] |

De ese tiempo, 0,29 s de mediana (0,32 s de p95) van de la imagen al encolado, que es sobre todo la redacción. Otros 0,07 s (0,085 s de p95) van del encolado al audio: es Piper sintetizando una frase que no podía estar preparada `[F]`. Ninguna corrección esperó a otra frase.

| Qué pasó con las correcciones | n | Etiqueta |
|---|---|---|
| Decididas por el motor | 21 | [F] |
| Redactadas por el LLM | 20 | [F] |
| Caídas a plantilla | 1: el validador rechazó la frase porque no pedía la corrección (`sin_correccion`) | [F] |
| Sustituidas antes de redactarse | 0 | [F] |
| Redactadas tarde | 0 | [F] |
| Encoladas y dichas | 21 de 21 | [F] |
| Mensajes no respaldados | 0 de 21 | [F] |

| Tiempo de cada redacción | n | p50 | p95 | Máximo | Etiqueta |
|---|---|---|---|---|---|
| Todas | 21 | 265 ms | 294 ms | 331 ms | [F] |
| Con la frase del LLM | 20 | 265 ms | 296 ms | 331 ms | [F] |

Comparación:

| | De la detección a la voz, p95 | Etiqueta |
|---|---|---|
| Plantillas, medición anterior (*full* en CPU) | 0,03 s (17 correcciones) | [F-2] |
| Plantillas hoy, con *heavy* en GPU (paso 1 b) | 0,10 s (21) | [F] |
| LLM hoy, con *heavy* en GPU | 0,39 s (21); máximo de 0,44 s | [F] |
| Meta | ≤ 1 s | |

El informe estimaba que quedaría por debajo de 0,5 s, y así es. La pose no cambia con el LLM: 16,2 ms (p95), mínimo de 25,0 imágenes por segundo y 6 descartadas de 16 131, como en el paso 1 b) `[F]`. En la segunda pasada («cola») hubo 22 correcciones, con 0,41 s de p95 y 0,45 s de máximo `[F]`. Memoria máxima del proceso de medición: 3,75 GB.

Límites de esta medición:
- Son 21 correcciones y ninguna es de zancada.
- No hubo ninguna corrección sustituida ni tardía. Esos dos contadores quedaron en cero sin ponerse a prueba con vídeo; sí los cubre la prueba automática.
- No incluye la latencia del dispositivo de audio.

Resultados: `backend/feedback_testing/resultados/MAC-gpu-heavy-llm.{md,json}` (en el repositorio) y, fuera de él, `~/estela-mac/resultados/paso3-sin-llm/`. Registros: `~/estela-mac/resultados/MAC-gpu-heavy-llm.log`, `MAC-gpu-heavy-sin-llm.log` y `MAC-pytest-paso3.log`.

---

## Paso 4 · Cifras del modelo de lenguaje (20-nov)

### 4.1 · No se repite

`medir_llm.py` no se volvió a correr: el informe ya usa las cifras confirmadas en 4.2, y el tiempo del LLM en la configuración actual de la app (temperatura 0,7 y el prompt de `f33ed7c`) sale del paso 3.

Última corrida en archivo (`~/estela-mac/resultados/llm/medir_llm.json`, 2026-11-16, 174 llamadas, temperatura 0,3, Mac Studio):

| Dato | qwen3:4b-instruct | Etiqueta |
|---|---|---|
| Latencia p50 / p95 / máx | 138,6 / 185,0 / 334,6 ms | [F-2] |
| % fuera del límite (200 / 300 / 400 / 500+ ms) | 1,7 / 0,6 / 0,0 / 0,0 % | [F-2] |
| Rechazadas o fallidas | 34 / 174 (19,5 %): 24 lado inventado, 6 parte del cuerpo ajena, 4 lado omitido | [F-2] |
| Piper, frase nueva p50 / p95 | 67,0 / 83,8 ms | [F-2] |

Esa corrida es anterior a `f33ed7c` (2026-11-20): mide el prompt anterior. Si se repitiera hoy, `medir_llm.py` usaría el prompt nuevo (`variar=True` es el defecto de `VerbalizadorLLMLocal`), pero con su propia temperatura (0,3 por defecto) y no la de la app (0,7) `[F]` (lectura del código, 22-nov). En `ESTADO.md` hay otra medición con `medir_variedad_llm.py`: p50 de 170 a 263 ms y caídas a plantilla de 18 a 35 de 144 `[F-2]`.

### 4.2 Archivos de resultados en el Mac y comprobación de cifras

| Origen | Ruta en el Mac (`~/estela-mac/…`) |
|---|---|
| GPU (`19dd8db`) | `resultados/exp004-gpu/latencia_por_candidato.csv` (+ `.npz`); registro en `resultados/medir_exp004.log`. `resultados/EXP-004-mac-gpu/` está vacía |
| Fuga de memoria (`9df14b6`) | `resultados/comparacion-8gb/ram-con-fuga/muestras.txt`, `…/ram/muestras.txt`, `fuga.sh`, `fuga_mp.py`, `fuga_mp2.py`; después del arreglo: `resultados/tras-fuga-p4/`, `resultados/tras-fuga2-p4/` |
| Todo a la vez (`8dfd164`) | `resultados/todo-a-la-vez/` (+ `todo-a-la-vez-p3/`, `medir_todo*.log`) |
| `generar_variantes` (`86cc06a`, `d60b3c1`) | `resultados/variantes/qwen3-14b/` y `resultados/variantes/llama3.3-70b/` (`resumen_variantes.json`, `variantes_para_revisar.csv`, `variantes_rechazadas.csv`) |
| `hoja_ab` (`d60b3c1`) | `resultados/ab/` (`respuestas_*.json`, `situaciones.json`, `hoja_ab.csv`); copia para calificar en `tanda/ab/` |
| `evaluar_reconocedores` | `resultados/voz-entrada/reconocedores.json`, `reconocedores_haz.json`, `evaluar.log`, `evaluar_haz.log`, `estabilidad_whispercpp*.txt` |

| Cifra del informe | Lo que dice el archivo | Resultado |
|---|---|---|
| LLM 4B: 185 ms p95 | 185,0 ms (`llm/medir_llm.json`) | Confirmada [F-2] |
| Variantes rechazadas: 19/261 con qwen3:14b | 242 válidas + 19 rechazadas = 261; motivos: 6 demasiado largas, 5 lado inventado, 3 lado incorrecto, 3 parte ajena, 2 dirección contraria | Confirmada [F-2] |
| Variantes rechazadas: 16/261 con llama3.3:70b | 245 + 16 = 261; motivos: 9 lado omitido, 7 lado inventado | Confirmada [F-2] |
| Entrenadora qwen3:14b: 1,19 s de mediana, 17/20 aceptadas | p50 1 180,5 ms, máx 2 001 ms; 17 aceptadas, 2 «habla de dolor», 1 «cifra inventada» | Confirmada [F-2] |
| Entrenadora llama3.3:70b: 3,27 s, 18/20 | p50 **3 260 ms** (3,26 s), máx 5 380 ms; 18 aceptadas, 2 «parte del cuerpo ajena» | Corregir a 3,26 s [F-2] |
| whisper.cpp small: 64/72 órdenes, 1 falsa de 26 | 64/72 (limpio 34/36), 0 equivocadas, 1/26 falsas (`evaluar.log`, con pista) | Confirmada [F-2] |
| whisper.cpp small: 69 ms p95 | `evaluar.log`: p50 57, **p95 71 ms** (con pista). Los 69 ms solo constan en `ESTADO.md` (búsqueda voraz, sin reintento, la configuración elegida); no encontré el archivo crudo de esa corrida | Sin confirmar [F-2]: 69 ms en `ESTADO.md`, 71 ms en el archivo |
| GPU: lite y full 3,1–4,6 ms | p95 por vídeo y pasada: lite (A4) 3,08–4,60 ms; full (A5) 3,15–4,65 ms | Confirmada (el máximo de full redondea a 4,7) [F-2] |
| GPU: heavy 4,8–6,2 ms | p95 heavy (A6) 4,80–6,26 ms | Confirmada (el máximo redondea a 6,3) [F-2] |
| Memoria sin arreglo: de 0,7 a 15 GB | RSS máximo de la app: 15,25 GB en 125 muestras (`ram-con-fuga/muestras.txt`) | Máximo confirmado; el 0,7 inicial no se puede leer del archivo (las muestras empiezan en el arranque) [F-2] |
| Memoria con arreglo: 0,6–2,1 GB | No encontré el archivo crudo; consta en `9df14b6` y `ESTADO.md`. En `ram/muestras.txt` (primer arreglo, plancha, con LLM y entrenadora encendidos) el RSS va de 1,26 a 2,96 GB | Sin archivo [F-2] |

La correspondencia A4/A5/A6 con lite/full/heavy está tomada de EXP-004 y del commit `19dd8db` `[F-2]`.

---

## Paso 5 · Órdenes de voz con micrófono real — GUÍA (lo hace Paula; pendiente)

Hasta ahora solo hay resultados con audio sintético (`[F-2]`, paso 4.2).

**Arreglo previo (hecho, commit `37e9520`):** `scripts/voz/probar_microfono.py` usaba `cv.separar_llamada`, que exige que «Estela» sea la primera palabra. La app usa `cv.hallar_llamada` desde `8248abb`, que la acepta en cualquier punto de la frase. Se cambió solo esa llamada. El script sigue sin el aviso temprano ni las ventanas parciales de la app: mide el reconocimiento de cada frase, no la sesión completa. Con el cambio, las pruebas siguen pasando: 737, 0 fallan `[F]` (22-nov).

**Condiciones:** el micrófono de las sesiones, a unos 2,5 m, en la sala de las sesiones, con todas las ventanas de ESTELA cerradas para que no compitan por el micrófono. En la Terminal **del Mac**:
```
mkdir -p ~/estela_privado
cd ~/estela-mac/ESTELA/backend
.venv/bin/python scripts/voz/probar_microfono.py --modo llamada --registro ~/estela_privado/microfono.jsonl --segundos 600
```
El script numera cada frase que oye. **Apunta el número de la última frase de la parte A y el de la última de la parte B**: el registro no guarda la hora, y sin esos dos números no se pueden separar las tres partes al contar.

**A. 36 órdenes** (12 órdenes × 3, en orden aleatorio con semilla 20261120). Haz una pausa de unos 2 s entre una y otra:

| | | | | | |
|---|---|---|---|---|---|
| 1 pausa | 2 repite eso | 3 siguiente | 4 quita los ángulos | 5 activa los ángulos | 6 anterior |
| 7 anterior | 8 repite eso | 9 ¿cómo voy? | 10 reinicia el ejercicio | 11 activa los ángulos | 12 activa los ángulos |
| 13 seguir | 14 pausa | 15 desactiva el reconocimiento | 16 siguiente | 17 calla | 18 terminar |
| 19 terminar | 20 desactiva el reconocimiento | 21 calla | 22 siguiente | 23 ¿cómo voy? | 24 quita los ángulos |
| 25 seguir | 26 terminar | 27 calla | 28 anterior | 29 repite eso | 30 reinicia el ejercicio |
| 31 desactiva el reconocimiento | 32 seguir | 33 ¿cómo voy? | 34 pausa | 35 quita los ángulos | 36 reinicia el ejercicio |

Cada una empieza por «Estela, …» (por ejemplo, «Estela, pausa»).

**B. 10 frases normales SIN «Estela»**, por ejemplo: «qué calor hace hoy», «pásame el agua», «vamos a seguir mañana», «ya casi termino», «espera un momento que me ato», «la siguiente vez lo hago mejor», «hay que pausar el video», «me duele un poco la cabeza», «¿cómo vas tú?», «repite la canción». Varias contienen a propósito palabras de órdenes: si alguna activa una orden, cuenta como orden falsa.

**C. 2 minutos** de conversación o música de fondo, sin hablarle a ESTELA.

**D. (Opcional) Modo «interrumpir»:** `probar_microfono.py` solo tiene los modos `llamada` y `pausa`, así que no puede probar órdenes mientras ESTELA habla. Eso se prueba con la app abierta (`.venv/bin/python -m estela`): di 12 veces «Estela, calla» o «Estela, pausa» mientras ESTELA habla y apunta a mano cuántas veces se calló o se pausó. No queda registro `.jsonl`.

Al terminar:
```
.venv/bin/python scripts/voz/analizar_tanda_voz.py --registro ~/estela_privado/microfono.jsonl
```
Las órdenes entendidas y las confundidas se cuentan comparando, en orden, el `comando` que el registro guarda en cada frase con la lista de arriba. `analizar_tanda_voz.py` da además los tiempos de reconocimiento, pero todavía clasifica con `separar_llamada`: si Whisper escribe algo antes de «Estela», su cuenta de frases «con Estela» puede quedar por debajo de la del registro `[F]` (lectura del código, 22-nov).

| Dato | Valor | Etiqueta |
|---|---|---|
| Órdenes entendidas / 36 | — | [?] pendiente |
| Confundidas | — | [?] pendiente |
| «No te entendí» | — | [?] pendiente |
| Órdenes falsas en 10 frases sin «Estela» | — | [?] pendiente |
| Órdenes falsas en 2 min de fondo | — | [?] pendiente |
| Reconocimiento p50 / p95 | — | [?] pendiente |
| Modo «interrumpir» (opcional): veces que obedeció / 12 | — | [?] pendiente |

El `.jsonl` contiene el texto de lo que dijiste: se queda en `~/estela_privado/`, fuera del repositorio. Aquí solo se copian los conteos.

---

## Paso 6 · Caída de la GPU al procesador (20-nov)

**Sin modificar el código no hay forma de forzar el fallo** `[F]` (lectura del código):
- `config.py` no lee variables de entorno, y `--modelo` solo acepta `lite`, `full` o `heavy`.
- Si falta el archivo del modelo, `FileNotFoundError` se relanza y la app no arranca: no cae a CPU. La excepción es que falte solo `heavy`: entonces pasa a `full` en CPU, pero por otro camino, no por un fallo de la GPU.
- Por SSH el delegado GPU sí arranca (`estimador.py`, `19dd8db`), así que esa vía tampoco sirve.

**Comprobación hecha sin cambiar el repositorio**: un arnés externo que sustituye en memoria `EstimadorPose.__init__` para que lance un error con `delegado="gpu"` y llama a `__main__._crear_estimador(modelo="heavy", delegado="gpu")` `[F]`:

| Dato | Resultado | Etiqueta |
|---|---|---|
| ¿Pasa a full en CPU? | Sí: `mediapipe_tasks:pose_landmarker_full`, delegado `cpu` | [F] |
| ¿Lo avisa? | En el registro sí: `WARNING estela: El delegado GPU no arrancó (…): se usa full en CPU.` | [F] |
| ¿Lo avisa en la ventana? | No: el aviso solo va al registro (`log.warning`); ni la interfaz ni el frontend lo muestran | [F] (lectura del código) |
| Fallo real de Metal | No reproducido | [?] |

---

## Paso 7 · Prueba completa con cámara — LISTA (lo hace Paula; pendiente)

Antes, cierra todas las ventanas de ESTELA. Después, en la Terminal del Mac: `cd ~/estela-mac/ESTELA/backend && .venv/bin/python -m estela`, sin opciones. No grabes la pantalla ni la cámara.

Fecha: ____ · Hora de inicio: ____

| # | Comprobar | ¿Funcionó? | Qué falló / mensaje raro |
|---|---|---|---|
| 1 | La app abre; en la cabecera se ve «Acerca de» (antes «Sobre nosotros», cambió en `8c22827`) y la cámara sin tachar | | |
| 2 | Crear un perfil | | |
| 3 | Empezar la rutina recomendada | | |
| 4 | Jumping jacks completo | | |
| 5 | Abducción, pierna izquierda | | |
| 6 | Abducción, pierna derecha | | |
| 7 | Zancada atrás, pierna izquierda | | |
| 8 | Zancada atrás, pierna derecha | | |
| 9 | Plancha | | |
| 10 | Pausar con la voz («Estela, pausa») y seguir («Estela, seguir») | | |
| 11 | Pausar con el botón y seguir. La pausa con el gesto del brazo se quitó en `f4ed26d` | | |
| 12 | Entre ejercicios: por defecto la entrenadora no habla y se pasa al siguiente (`3c7d229`). Anota qué ocurre. Solo si Paula lo pide, se repite con `--entrenadora-entre si` | | |
| 13 | Al final: la entrenadora dice un solo «Rutina terminada» y el resumen | | |
| 14 | La sesión aparece en «Mi progreso» | | |
| 15 | Borrar el perfil | | |
| 16 | Repetir la rutina sin perfil | | |
| 17 | Sin perfil, no se guarda nada (se comprueba después mirando solo los nombres y las fechas de `historial/`, sin abrir el contenido) | | |

Si algo falla, el registro de la sesión queda en la Terminal: copia solo la línea del error.

---

## Paso 8 · Pasos de instalación (para `Instalación.md`) (20-nov)

Comprobado contra lo instalado `[F]`. Lo marcado con `[?]` no consta en ningún registro de este Mac.

```bash
# 1. Ollama: app oficial de macOS en /Applications (Ollama.app, versión 0.40.6). [?] El origen de la descarga no consta (se instaló antes del plan).
#    En shells no interactivos (SSH) hay que añadir al PATH:
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH

# 2. Modelos (comandos del plan; los dos están en `ollama list`)
ollama pull qwen3:4b-instruct-2507-q4_K_M   # 2,5 GB: redacta las correcciones
ollama pull qwen3:14b                       # 9,3 GB: entrenadora

# 3. Entorno de la app con uv (Python 3.14.6 gestionado por uv 0.11.28)
cd ESTELA/backend
uv sync --extra voz --extra voz-entrada --extra interfaz --extra dev   # [?] reconstruido: instala lo que hay (piper-tts 1.8.0, sounddevice 0.5.6, pywhispercpp 1.5.1, pywebview 6.2.1, pytest 9.2.0); el comando exacto no quedó registrado
#    pywhispercpp llega como rueda precompilada para macOS arm64 con Metal incluido: no hace falta compilar whisper.cpp ni instalar nada con Homebrew

# 4. Modelos de pose, voz y voz de entrada
.venv/bin/python scripts/descargar_modelos.py --heavy --voz-entrada   # en un Mac arm64, heavy y voz de entrada se bajan aunque no se pidan
#    → modelos/pose_landmarker_{lite,full,heavy}.task, modelos/voces/es_MX-claude-high.onnx,
#      modelos/voz_entrada/ggml-small.bin (de huggingface.co/ggerganov/whisper.cpp)

# 5. Comprobar
.venv/bin/python -m pytest -q          # 732 pasan (22-nov, `6424b08`)
.venv/bin/python -m estela             # en el Mac: heavy en GPU, LLM, entrenadora y órdenes de voz por defecto
```

Los permisos de cámara y micrófono hay que aceptarlos una vez en la pantalla del Mac, desde la Terminal; por SSH no se puede.

---

## Paso 9 · Hoja a ciegas (20-nov)

| Dato | Valor | Etiqueta |
|---|---|---|
| Hoja para calificar | `~/estela-mac/tanda/ab/hoja_ab.csv` (20 situaciones) | [F] |
| Clave | `~/estela-mac/tanda/ab/clave_NO_ABRIR/clave_ab.json`, sin abrir | [F] |
| Copia en git | `PRUEBAS/ab_entrenadora_14b_70b/` (commit `b31d278`) **incluye la clave** | [F] |

No hizo falta regenerarla. Dos cosas que conviene saber:
1. Cualquiera con acceso al repo puede ver la clave, así que la hoja deja de ser a ciegas para quien la abra.
2. Desde `3c7d229` la entrenadora no habla entre ejercicios. Por eso 9 de las 20 situaciones («Resumen entre dos ejercicios») ya no corresponden a la app, y otras 4 (dolor y órdenes ambiguas) las contesta un texto fijo. Solo 7 situaciones reflejan lo que hace hoy la entrenadora `[F]` (conteo de la columna `situacion`).

---

## Cifras del informe que cambian

Respecto a `InformeFinal.md` en `main` (`6424b08`, 22-nov). Las medidas son del Mac Studio M2 Ultra.

| Cifra | Sección del informe | Antes | Ahora | Etiqueta |
|---|---|---|---|---|
| OE1, zancada | 14.3 y 14.8 | «Falta medir la zancada». Con 19 vídeos y 13 089 imágenes (*full* en CPU): pose de 20,7 ms (p95), mínimo de 25,1 imágenes/s y 0 descartadas | Con la zancada (23 vídeos, 16 131 imágenes): pose de 21,3 ms (p95), mínimo de 25,0 imágenes/s y 0 descartadas. Zancada sola (4 vídeos, 3 042 imágenes): 22,2 ms; derecha 17,2 ms e izquierda 22,7 ms. Los cuatro ejercicios cumplen | [F] |
| OE1 con la configuración del Mac | 14.8 | «Con *heavy* en GPU, 13–14 ms» | Con la misma herramienta y los 23 vídeos: 16,5 ms (p95) en 16 125 imágenes, mínimo de 25,0 imágenes/s y 6 descartadas de 16 131. Zancada: 20,1 ms | [F] |
| De la detección a la voz, con plantillas | 14.3, 14.6 y 14.8 (OE4) | 0,03 s (p95) en 17 correcciones; ninguna esperó | 0,07 s en 17 correcciones (*full* en CPU) y 0,10 s en 21 (*heavy* en GPU); ninguna esperó. Sigue en 0,03 s cuando la frase ya estaba sintetizada (ver paso 1) | [F] |
| Mensajes no respaldados en vídeo | 14.3 y 14.8 (OE3) | 0 de 17 | 0 de 17 (CPU) y 0 de 21 (GPU) | [F] |
| Motivos de silencio | 14.3 | 8 499 imágenes evaluadas: 67,8 % sin error; 16,1 % tiempo mínimo entre mensajes; 10,3 % intervalo antes de repetir; 4,7 % evidencia insuficiente; 0,8 % orientación; 0,3 % mensajes | 11 732 imágenes evaluadas (*full* en CPU, con la zancada): 74,7 % · 11,7 % · 7,6 % · 3,5 % · 2,3 % · 0,2 % | [F] |
| Variantes de MediaPipe en CPU | 14.3 y 14.6 | *lite* 8,7 ms, *full* 14,0 ms y *heavy* 58,4 ms (p95); 107 / 69 / 18 imágenes/s | 8,9, 14,5 y 59,5 ms con los 23 vídeos; 107 / 69 / 18 imágenes/s | [F] |
| Piper | 14.3 | 52,6 ms de mediana por frase | 44 ms (207 frases); factor de tiempo real de 0,015, igual | [F] |
| Imágenes por encima de 33 ms con todo encendido | 14.3 y 14.6 («Falta repetir la medición») | 10 de 7 694 (máximo de 314 ms), todas por la llamada al LLM dentro del ciclo de cada imagen | Con los mismos 4 vídeos: 4 de 7 694 (máximo de 196 ms) reconociendo una orden cada 2,0 s, y 1 (198 ms) cada 0,3 s. Con la pose sola hay 3 (276–280 ms). La más lenta es la renovación del detector de la GPU y ninguna la causa el LLM, que redacta fuera del ciclo (260 ms de mediana por frase) | [F] |
| Pose con todo encendido | 14.3 y 14.6 | 17,5 ms (p95), igual sola que con todo; Whisper 109 ms y Piper 178 ms (p95) | Con 6 vídeos (8 334 imágenes): 14,4 ms con todo y 14,3 ms sola; Whisper 113 ms y Piper 154 ms (p95) | [F] |
| Pruebas del backend en el Mac | 11.2 | 731 el 20-nov (`082c2e3`) | 732 en `6424b08` (`main`): 0 fallan y 0 se omiten. Con la herramienta del paso 3 (`37e9520`) son 737. Las 12 de más respecto a las 720 de Windows son las que allí se omiten por faltar el vídeo de prueba y Whisper | [F] |
| OE4 con el LLM encendido | 14.4 y 14.8 | «Estimado y sin medir»: debería quedar por debajo de 0,5 s | Medido con la configuración del Mac (*heavy* en GPU, Qwen3 4B, límite de 400 ms): 0,39 s (p95) y 0,44 s de máximo en 21 correcciones. 20 las redactó el LLM (265 ms de mediana por frase) y 1 cayó a plantilla; 0 no respaldadas. Cumple la meta de 1 s | [F] |
| Órdenes con micrófono real | 14.4 | Sin medir | Sigue sin medir: el paso 5 quedó pendiente el 22-nov | [?] |
| Prueba completa con cámara | 13.2 | «Su resultado no se registró» | Sigue sin hacerse: el paso 7 quedó pendiente el 22-nov | [?] |

Las correcciones que proponía el borrador del 20-nov (3,26 s de la entrenadora con el 70B, 69–71 ms de whisper.cpp, 4,7 y 6,3 ms como máximos en GPU y las 243 frases nuevas) ya están en `InformeFinal.md` `[F]` (leído el 22-nov).

---

## Preguntas para el equipo

1. **Precalentado de la voz.** Desde las variantes del 20-nov solo se sintetizan de antemano las tres primeras frases de cada regla, y la voz empieza a 0,07–0,10 s de la detección (p95) en vez de a 0,03 s. ¿Se amplía el precalentado en `frases_de_rutina`, o el informe pasa a decir 0,07–0,10 s?
2. **Pose con *heavy* en GPU.** El informe dice «13–14 ms» dentro de la aplicación. Con la herramienta general y los 23 vídeos son 16,5 ms (p95), y 14,4 ms en «todo a la vez». ¿Cuál de las tres va en OE1?
3. **Renovación del detector de la GPU.** En dos minutos seguidos sin avisos, una imagen tarda unos 280 ms (paso 2). ¿Se describe en el informe como límite conocido, junto a la fila «Falta repetir la medición» de 14.6?
4. **La entrenadora ya no entra en «todo a la vez»**, porque desde `3c7d229` no habla entre ejercicios. ¿Se repite la prueba con `--entrenadora-entre si` (hay que cambiar el script), o el informe dice que la prueba ya no la incluye?
5. **Zancada sin correcciones.** En ninguna corrida produjo correcciones un vídeo de zancada, así que para ese ejercicio no hay tiempo de la detección a la voz, ni con plantillas ni con el LLM. ¿Se dice así en OE4, o se busca un vídeo de zancada con errores?
