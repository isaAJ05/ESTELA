# `feedback_testing` — banco sintético y experimentos

Arnés para medir el módulo de feedback (`estela/dominio/feedback/`) **antes** de que exista una sola grabación. Depende de él; no al revés. Los comandos se ejecutan desde `backend/`.

## Lo primero: qué se puede y qué no se puede concluir de aquí

El banco genera directamente las *medidas* que el motor consume, colocadas al lado correcto del umbral de cada regla. **No simula biomecánica humana.** Un episodio «con valgo de rodilla» es un número, no un valgo.

| Se mide aquí | No se mide aquí |
|---|---|
| Determinismo del motor | Si los umbrales son correctos |
| Tasa de sobrecorrección en ejecuciones correctas | Exactitud de contenido sobre vídeo real (M1 de ADR-001) |
| Aserciones no soportadas en el mensaje | Naturalidad percibida (M6) |
| Latencia de decisión y verbalización | Latencia en el hardware del proyecto |
| Abstención por oclusión y por plano | Oclusión real por equipamiento |
| Coherencia entre el error inducido y el señalado | Si el error se parece a lo que hace una persona |

La M1 real de EXP-001 exige el banco grabado de 60–100 episodios con etiquetado manual de ADR-001 §5. Esto no lo sustituye: lo precede, para llegar a esa grabación con el motor ya depurado y con el arnés de métricas ya escrito.

## Contenido

| Archivo | Qué es |
|---|---|
| `generador_episodios.py` | Construye el banco. Completamente determinista, sin aleatoriedad. |
| `metricas.py` | M1\*, M2, M3, M4, M5, M7 y abstención, como funciones puras. |
| `runner.py` | Ejecuta una condición de verbalizador sobre el banco y emite el informe. |
| `exp002_observabilidad.py` | EXP-002: error de la medida monocular según la orientación del sujeto. |
| `metricas_informe.py` | Métricas del Informe 2 como funciones puras y `OBJETIVOS_INFORME2`. |
| `informe2.py` | Arnés del Informe 2: vídeos por la `Sesion` real → `resultados/INFORME2-metricas.{md,json}`. |
| `anotaciones/` | Ejemplo **sintético** del formato de anotación. Las anotaciones reales van en `backend/datos_locales/` (ignorado por git). |
| `resultados/` | Informes generados. Se regeneran con los comandos de abajo. |
| `tests/` | Pruebas del propio arnés. |

## Cómo correrlo

```bash
python3 -m unittest discover -s feedback_testing/tests -t .

# EXP-001, condición A (plantillas). No necesita nada instalado.
python3 -m feedback_testing.runner --salida feedback_testing/resultados/EXP-001-piloto-A.md

# EXP-001, condición F (LLM local). Requiere llama-server en 127.0.0.1:8080.
python3 -m feedback_testing.runner --condicion F  --salida feedback_testing/resultados/EXP-001-piloto-F.md
python3 -m feedback_testing.runner --condicion Fp --salida feedback_testing/resultados/EXP-001-piloto-Fp.md

# EXP-002
python3 -m feedback_testing.exp002_observabilidad
```

Las condiciones **F** y **F′** no se han ejecutado nunca: no hay ningún modelo disponible en el entorno donde se escribió esto. El código está, las cifras no.

## Composición del banco

Por cada regla de cada `skill`:

- 3 episodios con el error inducido (severidad leve, moderada, alta) → el sistema **debe** hablar y señalar ese error;
- 1 episodio con el error presente pero la medida ocluida (confianza 0,25) → el sistema **debe** callar;
- 1 episodio con el error presente y el sujeto orientado en el plano equivocado → el sistema **debe** callar (solo para reglas de plano frontal o sagital; las del transversal no tienen orientación válida con una cámara).

Y por cada `skill`, 3 ejecuciones **correctas**. Su inclusión no es opcional: es lo único que mide la sobrecorrección, y es exactamente el sesgo que hundió a CoachMe (30,4 % según ADR-001 §2.3).

Cada episodio son 8 repeticiones × 6 frames = 48 observaciones, 24 s nominales.

## Informe 2: métricas sobre vídeo (`informe2.py`)

Reproduce vídeos por la `Sesion` real (MediaPipe, motor, plantillas, cola de voz) y mide lo que pide el Informe 2. Los objetivos aceptados están en un solo sitio, `OBJETIVOS_INFORME2` (`metricas_informe.py`), y el informe marca cada uno como **cumple**, **no cumple** o **pendiente**. Lo que no se puede medir sale como «pendiente de medición: <qué falta>», nunca como un número.

```bash
pytest -m metricas -s                                   # medición completa (~30 min) + tablas en consola
ESTELA_INFORME2_RAPIDO=1 pytest -m metricas -s          # 1 vídeo por ejercicio, 8 s (~4 min)
python -m feedback_testing.informe2 --help              # lo mismo por CLI, con más opciones
python -m feedback_testing.informe2 --anotaciones datos_locales/anotaciones
python -m feedback_testing.informe2 --camara 0 --ejercicio jumping_jacks --duracion-s 60   # con consentimiento
```

`pytest` a secas **no** corre la medición (`addopts = -m 'not metricas'`). En Linux sin `libGL` hay que entrar antes en el entorno FHS (`nix-shell ../../shell.nix`). Si los modelos no están en `backend/modelos/`, `ESTELA_MODELOS=<carpeta>` los busca en otra (también `ESTELA/modelos/`). El docstring de `tests/test_informe2_medicion.py` lista el resto de variables.

Qué corre y qué sale:

| Sección | Cómo | Notas |
|---|---|---|
| Latencia por etapa (n, media, p50, p95, máx) | Corrida principal, modelo `full`, ritmo real | pose, geometría, segmentación, DTW, decisión, verbalización, total |
| FPS sostenidos, descartados, retraso acumulado y deriva | Dos políticas: «último frame» (como `FuenteCamara`) y «cola» (como `FuenteVideo`) | En vídeo los FPS no superan los de la fuente: el objetivo de 25 fps solo se evalúa con fuentes ≥ 25 fps |
| Detección → inicio de voz | `ColaVoz.registro`; voz `auto` = Piper sin altavoz (sintetiza y espera lo que dura el audio) | No incluye la latencia del dispositivo de audio; `--voz piper` suena de verdad |
| Silencios por causa | `Sesion(registrar=True)`: motivo por frame | Sin persona, pausa y `MOTIVO_*` |
| MediaPipe lite / full / heavy (EXP-004) | Ritmo máximo, mismos vídeos | Latencia, capacidad en FPS, % frames con persona, jitter en la plancha mantenida |
| DTW incremental sin banda frente a banda (EXP-010) | Réplica fuera de línea de la corrida «cola» | Latencia según longitud del prefijo y diferencias de resultado |
| Plantilla frente a LLM (EXP-001) | `runner.py` sobre el banco sintético | F sale pendiente sin `llama-server` (solo en la Mac) |
| RTF de Piper | `frases_de_rutina` | |
| Precisión, recobrado, F1, sobrecorrección, mensajes correctos, κ | Solo con anotaciones | Vídeo a ritmo máximo sin descarte (determinista) |

Cada informe registra el equipo (SO, CPU, núcleos, memoria, Python, versiones de mediapipe/numpy/opencv/piper, commit) y la fuente (vídeo con resolución y FPS, o cámara con índice y resolución), para no mezclar cifras de máquinas distintas. El JSON lleva tiempos, motivos y mensajes por frame; **nunca** imágenes, landmarks ni ángulos.

### Formato de anotación (`estela-anotacion-v1`)

Un archivo JSON por vídeo y anotadora; ejemplo completo en `anotaciones/ejemplo_sintetico.json`. Las anotaciones de personas y sus vídeos van en `backend/datos_locales/anotaciones/` y `backend/datos_locales/videos/` (ignorados por git; Ley 1581/2012).

```json
{
  "formato": "estela-anotacion-v1",
  "video": "p03_rutina.mp4",
  "ejercicio_id": "jumping_jacks",
  "anotadora": "A1",
  "bloque": null,
  "tramo_ms": [12000, 48000],
  "repeticiones": [
    {"t_ini_ms": 12000, "t_fin_ms": 13500, "bloque": 1, "errores": []},
    {"t_ini_ms": 30000, "t_fin_ms": 31600, "bloque": 3, "errores": ["brazos_no_llegan_arriba"]},
    {"t_ini_ms": 40000, "t_fin_ms": 41500, "bloque": 4,
     "errores": [{"error_id": "codos_flexionados", "segmento": "codo", "lado": "bilateral"}]}
  ]
}
```

- Tiempos en ms **del vídeo** (lo que marca el reproductor), no índices del segmentador: el segmentador puede equivocarse y eso es parte de lo que se mide.
- `errores: []` = repetición correcta. Los `error_id` son los del skill. `segmento` y `lado` son opcionales; si faltan se usan los de la regla.
- `bloque` (1–4 de EXP-009) va en el archivo o en cada repetición. `tramo_ms` (opcional) limita el vídeo a un ejercicio cuando se graba la rutina entera.
- Varias anotaciones del mismo vídeo: la precisión y el recobrado usan la de `"anotadora": "consenso"` si existe y, si no, la primera por orden alfabético; todas cuentan para κ.

### Definiciones

- **Atribución**: un mensaje se asigna a la repetición que contiene su `t_ms`; con tolerancia (± 1000 ms por defecto, `--tolerancia-ms`) puede ir a la vecina si esa sí tiene el error (el mensaje llega al empezar la repetición siguiente).
- **Precisión** por `error_id`: mensajes atribuidos a una repetición con ese error / mensajes de ese error. Un mensaje fuera de toda repetición anotada es FP.
- **Recobrado por episodios**: repeticiones consecutivas con el mismo error forman un episodio, porque la política de silencio exige 2–3 repeticiones y luego un refractario; un episodio está detectado si hay al menos un mensaje de ese error dentro (± tolerancia).
- **Detección cruda**: lo mismo por repetición con las reglas disparadas antes de la política de silencio (`MotorDecision.disparadas`).
- **Sobrecorrección**: % de repeticiones correctas a las que se atribuye alguna corrección.
- **Mensajes correctos**: % de correcciones cuyo `error_id`, segmento y lado coinciden con un error anotado en su repetición. Se reporta también la tasa de aserciones no soportadas (M2 de EXP-001), que no necesita anotación.
- **κ de Cohen**: binario por (repetición emparejada × `error_id`); las repeticiones de dos anotadoras se emparejan por solapamiento (IoU ≥ 0,5).

### Qué se puede y qué no se puede concluir

| Se puede | No se puede |
|---|---|
| Latencia, FPS y retraso **en el equipo que corrió el informe** | Las mismas cifras en la Mac Studio M2 Ultra (hay que repetirlo allí) |
| Qué etapa se come el presupuesto y cómo crece el DTW con el prefijo | Exactitud del feedback sin anotaciones humanas |
| Cuántas correcciones salen sobre vídeos públicos (candidatos a falso positivo) | Que esas correcciones sean falsos positivos: nadie anotó esos vídeos |
| Diferencias entre lite/full/heavy en latencia, detección de persona y jitter en la plancha | Exactitud de los ángulos (no hay verdad de terreno) |
| Latencia detección → voz sin el dispositivo de audio | La latencia de los altavoces de cada portátil |
