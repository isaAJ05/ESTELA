# Resultados del Mac Studio para el Informe Final

Rama `feature/mac-flujo`. Pasos 0, 3, 4.2, 6, 8 y 9 revisados en `b31d278` (17:20). Pruebas y mediciones de latencia repetidas en `082c2e3` (21:00), que es igual a `origin/feature/mac-flujo` y al código del Mac. Equipo: Mac Studio M2 Ultra, 128 GB.
Etiquetas: `[F]` medido o comprobado aquí el 2026-11-20 · `[F-2]` tomado de un commit, de `ESTADO.md` o de un archivo de resultados anterior · `[?]` no se pudo medir.
Este archivo solo contiene métricas. No contiene audio, vídeo ni el texto de lo que dijo nadie.

**Estado:** borrador. Faltan las mediciones de latencia (pasos 1, 2 y 4.1), porque el Mac no estaba libre (ver «Preguntas»), y los pasos 5 y 7, que hace Paula frente al Mac.

---

## Paso 0 · Preparación

Comandos: `git fetch` y `git status` en la rama (ya estaba al día: 0 commits de diferencia con `origin`, y contiene `3bccd74` y `2874bd9`). Las pruebas se corrieron en el Mac con `cd ~/estela-mac/ESTELA/backend && .venv/bin/python -m pytest -q`.

| Dato | Valor | Etiqueta |
|---|---|---|
| Pruebas que pasan | 731 en `082c2e3` (690 en `b31d278`) | [F] |
| Pruebas que fallan | 0 | [F] |
| Pruebas omitidas | 0 (12 quedan fuera por la marca `metricas`, que `pyproject.toml` excluye por defecto) | [F] |
| Duración | 27,9 s | [F] |
| macOS | 26.3.2 (25D2140) | [F] |
| Procesador | Apple M2 Ultra | [F] |
| Python (entorno de la app) | 3.14.6, entorno creado con uv 0.11.28 | [F] |
| mediapipe | 1.2.3 | [F] |
| Ollama | 0.40.6 | [F] |
| Modelos de Ollama | `qwen3:4b-instruct-2507-q4_K_M` 2,5 GB · `qwen3:14b` 9,3 GB · `llama3.3:70b` 42 GB · `phi4-mini` 2,5 GB · `qwen3:1.7b` 1,4 GB | [F] |
| pywhispercpp | 1.5.1, rueda precompilada `cp314-macosx_11_0_arm64`; informa `MTL: EMBED_LIBRARY = 1` (Metal) | [F] |
| Versión de whisper.cpp dentro de pywhispercpp | no la expone la librería | [?] |
| Modelo de voz de entrada | `ggml-small.bin`, 487 601 967 bytes | [F] |
| Voz de salida | Piper `es_MX-claude-high`; piper-tts 1.8.0 | [F] |
| Ventana | pywebview 6.2.1 | [F] |

Antes, `ESTADO.md` decía «546 pasan en el Mac» `[F-2]`. La cifra de hoy es 690.

---

## Paso 1 · Tiempos con la zancada (OE1) — PENDIENTE

Comandos previstos (desde `backend/`):
```
python -m feedback_testing.informe2 --salida-md feedback_testing/resultados/MAC-cpu-full.md --salida-json feedback_testing/resultados/MAC-cpu-full.json
python -m feedback_testing.informe2 --modelo heavy --delegado gpu --salida-md feedback_testing/resultados/MAC-gpu-heavy.md --salida-json feedback_testing/resultados/MAC-gpu-heavy.json
```

Aún no se han corrido, por dos motivos:

1. **Los vídeos de zancada nuevos no están en el Mac** `[F]`. Esta es la carpeta `docs_estela/.../videos/Zancada atrás estática por pierna/`:

   | Vídeo | En `docs_estela` (`origin/main`) | En el Mac | ¿Lo acepta `informe2`? |
   |---|---|---|---|
   | `der Zancada atrás con Kettlebell…mp4` | sí | sí | sí (prefijo «der») |
   | `izq Zancada hacia atrás con peso corporal…mp4` | sí | sí | sí (prefijo «izq») |
   | `ZANCADA CHICA DERECHA.mp4` | sí | **no** | sí (última palabra «derecha») |
   | `ZANCADA CHICA IZQUIERDA.mp4` | sí | **no** | sí (última palabra «izquierda») |
   | `videoplayback.mp4`, `videoplayback (1).mp4`, `(2)`, `(3)` | sí | sí | **no**: el nombre no dice el lado, así que `_lado_de` devuelve `None` y el vídeo queda excluido `[I]` (por lectura del código) |

   Así que hoy entrarían 2 vídeos de zancada, no 4. En las mediciones anteriores (`8dfd164`, `todo-a-la-vez`), el vídeo `der … Kettlebell` no pasó de la colocación `[F-2]`.
2. **El Mac no estaba libre**: había otra sesión de trabajo corriendo pruebas y dos ventanas de ESTELA abiertas, una de ellas con ~30 % de CPU constante `[F]`. Medir latencias así contaminaría p95.

Archivos de salida (cuando se corra): `backend/feedback_testing/resultados/MAC-cpu-full.{md,json}` y `MAC-gpu-heavy.{md,json}`.

---

## Paso 2 · «Todas las funciones a la vez», repetido — PENDIENTE

Vídeos de la medición anterior (`8dfd164`, según `~/estela-mac/scripts/medir_todo.sh`) `[F]`:
- `Jumping Jacks/7 hombre.mp4` → `jumping_jacks`
- `Abdu…/izq-ok-*.mp4` → `abduccion_cadera_izq`
- `Zancada…/der Zancada*.mp4` → `zancada_atras_der` (no pasó de la colocación)
- `Plancha/*Galvistrainer.mp4` → `plancha`

Además se añadiría un vídeo de zancada nuevo (`ZANCADA CHICA DERECHA.mp4` o el izquierdo), si se copia al Mac.

Comando previsto:
```
python scripts/voz/medir_todo_a_la_vez.py --salida resultados_todo_a_la_vez_v2 --historial datos_locales/historial_ejemplo.jsonl --videos "<jj>:jumping_jacks" "<abd>:abduccion_cadera_izq" "<zancada der>:zancada_atras_der" "<plancha>:plancha" "<ZANCADA CHICA …>:zancada_atras_<lado>"
```

Referencia anterior `[F-2]` (`8dfd164`, 2026-11-16, 7 694 frames por condición):

| | Pose p50 | Pose p95 | Pose máx | Total por frame p95 | Frames > 33 ms | Whisper p50/p95 | Piper p50/p95 |
|---|---|---|---|---|---|---|---|
| base | 11,5 ms | 17,5 ms | 45,7 ms | 20,2 ms | 0 | — | — |
| todo | 11,4 ms | 17,5 ms | 49,6 ms | 19,2 ms | 10 (máx 314 ms) | 91 / 109 ms | 105 / 178 ms |

Después del arreglo de la fuga de memoria (`resultados/tras-fuga2-p4/`, 2026-11-17), con todo encendido: 3 imágenes evaluadas superaron los 33 ms, todas entre 34 y 38 ms `[F-2]` (`ESTADO.md`). Es anterior a `b9b918c`.

---

## Paso 3 · De la detección a la voz con el LLM encendido — NO EXISTE HERRAMIENTA

Revisado en el código `[F]`:

| Herramienta | ¿Mide de la detección a la voz? | ¿Con el LLM? |
|---|---|---|
| `feedback_testing/informe2.py` | Sí: `deteccion_a_voz()` cuenta desde la llegada del frame, pasando por el encolado, hasta el inicio del audio | **No**: crea `Sesion(rutina, catalogo, est, cola)` sin verbalizador, así que usa plantillas |
| `scripts/voz/medir_todo_a_la_vez.py` | **No**: guarda la pose, el total por frame, la duración de cada redacción del LLM (`verbalizacion`), Piper y Whisper | Sí (`--verbalizador llm`) |
| `python -m estela --guardar-metricas` | **No**: guarda latencias por etapa, llamadas al LLM y caídas a plantilla, pero no el inicio del audio respecto de la detección | Sí |

Desde `b9b918c`, el LLM redacta en otro hilo (`VerbalizacionAparte`). La corrección se dice cuando la redacción vuelve, y ese tiempo de ida y vuelta no lo registra nadie.

**Qué habría que cambiar** (no se ha tocado nada; queda a la espera de tu decisión):
- En `informe2.py`: una opción `--verbalizador llm` que pase `VerbalizadorLLMLocal` (Ollama, `qwen3:4b-instruct-2507-q4_K_M`) a `Sesion(..., verbalizador=v, verbalizar_aparte=True)`, como hace `__main__`.
- En `deteccion_a_voz()`: hoy empareja «n-ésimo frame con mensaje» con «n-ésima frase dicha», y con la redacción aparte ese emparejamiento ya no vale. El mensaje lleva el `t_ms` del frame en que se detectó (la `clave` de `_al_redactar`), así que habría que medir desde la llegada de ese frame hasta `t_inicio_audio`. También habría que contar aparte las redacciones que llegan tarde (`redactadas_tarde`) y las sustituidas.
- Una prueba nueva con un verbalizador falso y lento, para comprobar el emparejamiento sin Ollama.

---

## Paso 4 · Cifras del modelo de lenguaje

### 4.1 `medir_llm.py` — PENDIENTE (Mac ocupado)

Comando previsto: `python scripts/medir_llm.py --modelos qwen3:4b-instruct-2507-q4_K_M --piper --salida resultados_llm.json`.

Última corrida en archivo `[F-2]` (`~/estela-mac/resultados/llm/medir_llm.json`, 2026-11-16, 174 llamadas, temperatura 0,3):

| Dato | qwen3:4b-instruct |
|---|---|
| Latencia p50 / p95 / máx | 138,6 / 185,0 / 334,6 ms |
| % fuera del límite (200 / 300 / 400 / 500+ ms) | 1,7 / 0,6 / 0,0 / 0,0 % |
| Rechazadas o fallidas | 34 / 174 (19,5 %): 24 lado inventado, 6 parte del cuerpo ajena, 4 lado omitido |
| Piper, frase nueva p50 / p95 | 67,0 / 83,8 ms |

Ojo: desde `f33ed7c` (2026-11-20), la redacción en la app usa temperatura 0,7 y otro prompt. En `ESTADO.md` hay una medición con `medir_variedad_llm.py`: p50 de 170 a 263 ms, y caídas a plantilla de 18 a 35 de 144 `[F-2]`. `medir_llm.py` mide el modo antiguo (`variar=False`) salvo que se le indique otra cosa `[?]` (sin comprobar).

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

## Paso 5 · Órdenes de voz con micrófono real — GUÍA (lo hace Paula)

Hasta ahora solo hay resultados con audio sintético (`[F-2]`, arriba).

En la Terminal **del Mac**, con el micrófono de las sesiones y a ~2,5 m:
```
mkdir -p ~/estela_privado
cd ~/estela-mac/ESTELA/backend
.venv/bin/python scripts/voz/probar_microfono.py --modo llamada --registro ~/estela_privado/microfono.jsonl --segundos 600
```
Antes, cierra todas las ventanas de ESTELA para que no compitan por el micrófono.

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

**D. (Opcional) Modo «interrumpir»:** `probar_microfono.py` solo tiene los modos `llamada` y `pausa`, así que no puede probar órdenes mientras ESTELA habla. Eso solo se prueba con la app abierta (`python -m estela`), diciendo «Estela, calla» o «Estela, pausa» mientras habla. En ese caso no hay registro `.jsonl` y los conteos se apuntan a mano `[I]`.

Al terminar:
```
.venv/bin/python scripts/voz/analizar_tanda_voz.py --registro ~/estela_privado/microfono.jsonl
```
Las órdenes «confundidas» se obtienen comparando el registro con la lista de arriba. Lo hace Claude en el Mac y solo copia aquí los conteos.

| Dato | Valor | Etiqueta |
|---|---|---|
| Órdenes entendidas / 36 | — | [?] pendiente |
| Confundidas | — | [?] pendiente |
| «No te entendí» | — | [?] pendiente |
| Órdenes falsas en 10 frases sin «Estela» | — | [?] pendiente |
| Órdenes falsas en 2 min de fondo | — | [?] pendiente |
| Reconocimiento p50 / p95 | — | [?] pendiente |

El `.jsonl` contiene el texto de lo que dijiste: se queda en `~/estela_privado/`, fuera del repositorio.

---

## Paso 6 · Caída de la GPU al procesador

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

## Paso 7 · Prueba completa con cámara — LISTA (lo hace Paula)

Antes, cierra todas las ventanas de ESTELA. Después, en la Terminal del Mac: `cd ~/estela-mac/ESTELA/backend && .venv/bin/python -m estela`. No grabes la pantalla ni la cámara.

Fecha: ____ · Hora de inicio: ____

| # | Comprobar | ¿Funcionó? | Qué falló / mensaje raro |
|---|---|---|---|
| 1 | La app abre; se ven el enlace «Sobre nosotros» y la cámara sin tachar | | |
| 2 | Crear un perfil | | |
| 3 | Empezar la rutina recomendada | | |
| 4 | Jumping jacks completo | | |
| 5 | Abducción, pierna izquierda | | |
| 6 | Abducción, pierna derecha | | |
| 7 | Zancada atrás, pierna izquierda | | |
| 8 | Zancada atrás, pierna derecha | | |
| 9 | Plancha | | |
| 10 | Pausar con la voz («Estela, pausa») y seguir («Estela, seguir») | | |
| 11 | Pausar con el botón y seguir. La pausa con el gesto del brazo se quitó en `f4ed26d` (2026-11-20, a pedido de Paula) | | |
| 12 | Entre ejercicios: **desde `3c7d229` la entrenadora no habla ahí, sino que pasa al siguiente**. Anota qué ocurre (ver «Preguntas») | | |
| 13 | Al final: la entrenadora dice un solo «Rutina terminada» y el resumen | | |
| 14 | La sesión aparece en «Mi progreso» | | |
| 15 | Borrar el perfil | | |
| 16 | Repetir la rutina sin perfil | | |
| 17 | Sin perfil, no se guarda nada (Claude lo comprueba después en `historial/`, sin abrir contenidos) | | |

Si algo falla, el registro de la sesión queda en la Terminal: copia solo la línea del error.

---

## Paso 8 · Pasos de instalación (para `Instalación.md`)

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
.venv/bin/python -m pytest -q          # 690 pasan
.venv/bin/python -m estela             # en el Mac: heavy en GPU, LLM, entrenadora y órdenes de voz por defecto
```

Los permisos de cámara y micrófono hay que aceptarlos una vez en la pantalla del Mac, desde la Terminal; por SSH no se puede.

---

## Paso 9 · Hoja a ciegas

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

| Cifra | Antes | Ahora | Etiqueta |
|---|---|---|---|
| Pruebas en el Mac | 546 pasan | 731 pasan, 0 fallan (12 fuera por la marca `metricas`), en `082c2e3` | [F] |
| Frases fijas de corrección | solo las plantillas del catálogo | más 118 variantes nuevas del 70B (de 140 aprobadas; 22 repetidas) y 125 del 14B (de 135; 10 repetidas), que rotan (`cbfb1bb`, `082c2e3`). Las revisó Claude a pedido de Paula, no la licenciada: `revision_pendiente` sigue vigente | [F-2] |
| Entrenadora llama3.3:70b, mediana | 3,27 s | 3,26 s (3 260 ms en `respuestas_llama3.3_70b.json`) | [F-2] |
| whisper.cpp small, p95 | 69 ms | 69 ms sin archivo crudo; 71 ms en `evaluar.log` | [F-2] |
| GPU, máximo de full | 4,6 ms | 4,65 ms (redondea a 4,7) | [F-2] |
| GPU, máximo de heavy | 6,2 ms | 6,26 ms (redondea a 6,3) | [F-2] |
| Vídeos de zancada medibles en el Mac | — | 2 de 8: faltan los 2 «ZANCADA CHICA» y los 4 `videoplayback` se excluyen por no decir el lado | [F] |

Las cifras de latencia de los pasos 1, 2 y 4.1 se añadirán cuando se midan.

---

## Preguntas para el equipo

1. **¿Quién aparece en «ZANCADA CHICA DERECHA.mp4» e «IZQUIERDA.mp4»?** Están en `docs_estela` (`origin/main`). Si es alguien del equipo, no deberían estar en git (Ley 1581/2012 y la regla del proyecto). Además, hoy no están en el Mac.
2. **Los 4 `videoplayback*.mp4` de la carpeta de zancada no dicen el lado.** ¿Se renombran (por ejemplo «izq …» o «der …»), o se dejan fuera?
3. **Entrenadora entre ejercicios:** el paso 7 pide comprobar que hable entre ejercicios, pero `3c7d229` (2026-11-20) lo quitó. ¿Qué vale para el informe?
4. **La clave del A/B está en git** (`b31d278`). ¿Se quita del repo antes de que el equipo califique?
