# Manual de desarrollo

> **Versión que describe este manual.** Rama `main`, *commit* `4336bdf` (21 de noviembre de 2026). Es la versión final de ESTELA, la que presenta el informe final, y la rama también guarda la documentación, los diagramas y la página de presentación. La versión básica, para equipos que no son un Mac con Apple Silicon, está en la rama `test` (sección 3). Salvo que se indique otra cosa, las rutas son relativas a la raíz del repositorio.

## 1. Propósito del documento

Este documento es la guía técnica para comprender, mantener y extender ESTELA. Está dirigido a los equipos que continúen el proyecto y necesiten ubicarse rápido en el repositorio: cómo está organizado, cómo se traduce la arquitectura en código, qué scripts existen, cómo se configura la aplicación y qué prácticas se siguieron durante el desarrollo.

El manual complementa a otros dos documentos y procura no repetirlos. `InformeFinal.md` explica el problema, las alternativas evaluadas, la arquitectura y los resultados; aquí solo se recuerdan cuando hacen falta para trabajar con el código. `Instalación.md` está pensada para quien solo quiere poner en marcha la aplicación. Este manual se dirige a quien va a modificarla.

A lo largo del texto se distingue entre lo que está implementado, lo que se midió y lo que sigue pendiente. Cuando una cifra proviene de una medición, se indica el archivo o el *commit* donde está registrada.

## 2. Descripción general del proyecto desde la perspectiva de desarrollo

ESTELA es una aplicación de escritorio que acompaña una rutina corta de ejercicios de bajo impacto. Observa a la persona con la cámara, identifica los puntos de su cuerpo, cuenta las repeticiones, compara el movimiento con una referencia del ejercicio y da indicaciones habladas en español. Todo se ejecuta en el computador de la persona: no hay servidor, no se usan servicios en la nube durante la sesión y no hay base de datos. Los perfiles y el historial son archivos locales.

Desde el punto de vista técnico, la aplicación es un solo proceso con dos partes. El backend, escrito en Python, contiene toda la lógica: la captura, la estimación de pose, el cálculo de medidas, el conteo, la comparación con la referencia, la decisión de qué decir y la voz. La interfaz, escrita en React y TypeScript, se compila a archivos estáticos y se muestra en una ventana nativa mediante pywebview. La interfaz no toma decisiones: muestra el estado que le envía Python y le devuelve las órdenes de la persona.

El trabajo sobre cada ejercicio ocurre en dos momentos. Fuera de línea se prepara una *skill*, que es un archivo JSON con las fases del movimiento, las reglas de error, sus umbrales y una referencia extraída de un vídeo. Durante la sesión, el sistema procesa cada imagen de la cámara con esa configuración. Gracias a esta separación, añadir un ejercicio consiste en añadir archivos de configuración y no en modificar el núcleo.

La versión final tiene una particularidad: la configuración por defecto depende del equipo. En un Mac con Apple Silicon, como el Mac Studio M2 Ultra del proyecto, se encienden la variante *heavy* de la pose en la tarjeta gráfica, la redacción de las correcciones con un modelo de lenguaje local, la entrenadora y las órdenes de voz. En los demás equipos la aplicación arranca con la configuración básica: pose *lite* en el procesador, frases fijas y sin micrófono. Las dos configuraciones comparten el mismo código (sección 7.2).

### 2.1 Tecnologías principales

- **Interfaz:** React 19 y TypeScript, compilados con Vite. Usa los íconos de `lucide-react` y la fuente Manrope. Se muestra en una ventana de pywebview, que usa WKWebView en macOS, WebView2 en Windows y WebKitGTK o Qt en Linux.
- **Backend:** Python 3.10 o superior, con MediaPipe, OpenCV, NumPy y Pillow como dependencias base. La capa de dominio usa solo la biblioteca estándar.
- **Modelos locales:** MediaPipe Pose Landmarker (variantes *lite*, *full* y *heavy*) para la pose; Piper con la voz `es_MX-claude-high` para hablar; whisper.cpp, mediante `pywhispercpp`, para reconocer las órdenes de voz; y Ollama con Qwen3 4B y Qwen3 14B para redactar correcciones y para la entrenadora.
- **Persistencia:** archivos JSON y JSON Lines en `backend/historial/`. No hay base de datos.
- **Contenedores:** no se usan (sección 5).
- **Pruebas:** pytest en el backend y el ejecutor de pruebas integrado de Node.js en la interfaz.
- **Gestión e infraestructura:** Git y GitHub para el código, ClickUp para las tareas y Vercel para publicar la página de presentación (`landing/`, solo en `main`).

La siguiente tabla reúne las restricciones de versión de `backend/pyproject.toml` y las versiones instaladas en el Mac Studio, según `RESULTADOS-MAC-INFORME-FINAL.md` (pasos 0 y 8).

| Componente | Extra de instalación | Restricción | Versión en el Mac Studio |
|---|---|---|---|
| Python | — | ≥ 3.10 | 3.14.6, entorno creado con uv |
| mediapipe | base | ≥ 1.0.1, < 2 | 1.2.3 |
| opencv-python, numpy, pillow | base | ≥ 4.9, ≥ 1.26 y ≥ 10.1 | sin registrar |
| piper-tts | `voz` | ≥ 1.3, < 2 | 1.8.0 |
| sounddevice | `voz` y `voz-entrada` | ≥ 0.4 | 0.5.6 |
| pywhispercpp | `voz-entrada` | ≥ 1.5, < 2 | 1.5.1, con Metal |
| pywebview | `interfaz` | ≥ 5 | 6.2.1 |
| pytest | `dev` | ≥ 8 | 9.2.0 |
| Ollama | aplicación aparte | — | 0.40.6 |

En la interfaz, `frontend/package.json` fija React ^19.3, TypeScript ^7.0 y Vite ^8.3.

### 2.2 Componentes principales

- **Núcleo de análisis (`backend/estela/`):** ejecuta la sesión. Por cada imagen estima la pose, calcula medidas, cuenta repeticiones, compara con la referencia, decide si hay algo que decir y lo envía a la voz.
- **Interfaz de escritorio (`frontend/`):** pantallas de perfiles, inicio, sesión, resumen, progreso, ayuda y «Acerca de». Consulta el estado a Python de forma continua y le envía las órdenes de la persona.
- **Skills, referencias y rutinas:** archivos JSON que describen cada ejercicio y la rutina recomendada. Son el mecanismo para extender el sistema sin tocar el núcleo.
- **Servicios locales opcionales:** Ollama, al que se accede por HTTP en `127.0.0.1`, y whisper.cpp, que corre como biblioteca dentro del mismo proceso. Si falta alguno, la aplicación sigue con la opción básica y lo deja escrito en el registro.
- **Herramientas fuera de línea (`backend/scripts/`):** descarga de modelos, creación de referencias, generación y revisión de variantes de frases y mediciones.
- **Banco de pruebas y medición (`backend/feedback_testing/`):** banco sintético del motor de decisión y arnés que reproduce vídeos por la sesión real para medir tiempos.
- **Página de presentación (`landing/`, en `main`):** HTML estático publicado en Vercel. No forma parte de la aplicación.

El siguiente esquema muestra el recorrido de cada imagen durante una sesión. Los nombres entre paréntesis son los hilos (*threads*) que crea la aplicación.

```text
Cámara (estela-camara) ─► imagen más reciente
  ─► sesión (estela-sesion): pose ─► geometría ─► segmentador ─► DTW
       ─► motor de decisión ─► error tipificado | felicitación | silencio
       ─► verbalizador: plantilla, o modelo de lenguaje en otro hilo (estela-verbalizador)
       ─► cola de voz (estela-voz) ─► Piper ─► parlantes
  ─► estado de la sesión ─► interfaz (pywebview)

Micrófono ─► whisper.cpp ─► «Estela, pausa» ─► mismo camino que los botones
```

## 3. Estructura del repositorio

El código está en el repositorio de GitHub `isaAJ05/ESTELA`. Tiene dos ramas principales, una por versión:

| Rama | Contenido | Uso |
|---|---|---|
| `main` | La aplicación completa (backend, interfaz, pruebas y scripts, con las funciones del Mac), los informes, este manual, los diagramas y la página de presentación. | Versión final y rama por defecto. Es la que describe este manual y el origen de la publicación en Vercel. |
| `test` | La aplicación sin el modelo de lenguaje en vivo, la entrenadora ni las órdenes de voz, pensada para un computador básico. | Versión básica. Fue la rama de integración de las *pull requests* durante el semestre. |

Un `git clone` sin opciones trae `main`; para la versión básica se clona con `-b test` (sección 8.1). `main` incluye todos los cambios de `test`, pero las dos ramas evolucionan por separado: un cambio hecho en una no pasa solo a la otra (sección 8.4).

Fuera de este repositorio está `docs_estela`, el repositorio de documentación del proyecto. Allí se guardan los registros de decisiones (`decisiones/`), los experimentos (`experimentos/`) y la investigación (`investigacion/`).

### 3.1 Árbol general del repositorio

```text
ESTELA/
├── backend/                          todo el Python
│   ├── estela/                       paquete de la aplicación
│   │   ├── __main__.py               arranque: python -m estela
│   │   ├── config.py                 rutas y valores por defecto según el equipo
│   │   ├── dominio/                  lógica de los ejercicios (solo biblioteca estándar)
│   │   │   ├── conteo/               segmentador de fases y conteo
│   │   │   └── feedback/             contrato de datos, motor, verbalizador y skills
│   │   │       ├── motor/            geometría, carga de skills y decisión
│   │   │       ├── verbalizador/     plantillas, validador y plantillas_es.json
│   │   │       └── skills/           un JSON por ejercicio, referencias/ y retirados/
│   │   ├── aplicacion/               sesión, rutina, DTW, pausas, entrenadora, historial, perfiles
│   │   └── adaptadores/              captura, pose, voz, voz_entrada, llm e interfaz
│   ├── rutinas/                      rutinas en JSON
│   ├── scripts/                      descarga de modelos, referencias, variantes y mediciones
│   │   └── voz/                      pruebas y mediciones de voz
│   ├── feedback_testing/             banco sintético y arnés de medición
│   ├── tests/                        pruebas del backend
│   ├── pyproject.toml                dependencias, extras y configuración de pytest
│   ├── modelos/                      (ignorada por git) modelos descargados
│   ├── historial/                    (ignorada por git) perfiles e historial
│   └── sesiones/                     métricas de --guardar-metricas (ignorada por git, salvo resúmenes de sesiones de prueba)
├── frontend/                         interfaz de escritorio
│   ├── src/                          bridge/, estado/, pantallas/, componentes/, estilos/
│   ├── pruebas/                      pruebas de la lógica de la interfaz
│   ├── public/                       logo y poses de la mascota
│   ├── dist/                         interfaz compilada (versionada)
│   └── package.json
├── PRUEBAS/                          prototipos y arneses de experimentos
├── diagramas/
│   ├── mac_diagrams_def/             diagramas de la versión completa (vigentes)
│   ├── definitivos/                  diagramas de la versión básica
│   └── otros/                        diagramas de una versión anterior
├── diagramas_estela_modelo_profe/    versiones simplificadas de los diagramas
├── landing/                          página de presentación estática
├── vercel.json                       publica landing/ en Vercel
├── design/ESTELA.pdf                 diseño visual
├── .githooks/commit-msg              exige el identificador de ClickUp
├── .gitmessage                       plantilla del mensaje de commit
├── RESULTADOS-MAC-INFORME-FINAL.md   métricas del Mac Studio (borrador)
├── InformeFinal.md, PrimerInforme.md, SegundoInforme.md
└── Readme.md, Instalación.md, Desarrollo.md
```


### 3.2 Descripción de directorios y archivos relevantes

| Ruta | Contenido |
|---|---|
| `backend/estela/__main__.py` | Punto de entrada. Lee las opciones, aplica los valores por defecto del equipo, crea los adaptadores y arranca la interfaz. |
| `backend/estela/config.py` | Rutas, modelos y tiempos límite por defecto, y la función `defectos()`, que decide qué se enciende en cada equipo. |
| `backend/estela/dominio/feedback/skills/` | Una *skill* por ejercicio: `jumping_jacks`, `abduccion_cadera_izq` y `_der`, `zancada_atras_izq` y `_der`, y `plancha`. El formato está documentado en `ESQUEMA.md`. `retirados/` guarda las *skills* descartadas, que las pruebas usan como banco. |
| `backend/estela/dominio/feedback/skills/referencias/` | Una referencia por ejercicio (`<skill_id>/referencia.json`) y `reconocimiento.json`, que usa el reconocimiento del ejercicio. |
| `backend/estela/dominio/feedback/verbalizador/plantillas_es.json` | Frases en español para cada tipo de error, incluidas las variantes revisadas que rotan. |
| `backend/rutinas/calentamiento_basico.json` | Rutina recomendada: jumping jacks, abducción de cadera por pierna, zancada atrás por pierna y plancha. |
| `backend/scripts/` y `backend/scripts/voz/` | Herramientas de consola (sección 6.2). |
| `backend/feedback_testing/` | Banco sintético de EXP-001 y EXP-002 y arnés de medición del Informe 2. |
| `backend/tests/` | Pruebas del backend. `test_arquitectura.py` vigila las reglas entre capas. |
| `backend/pyproject.toml` | Dependencias, extras opcionales y configuración de pytest. |
| `backend/modelos/`, `historial/`, `sesiones/` y `datos_locales/` | Modelos descargados, perfiles e historial, métricas de sesión y datos locales de experimentos. Git los ignora. |
| `frontend/src/` | Código de la interfaz: `bridge/` (contrato y conexión con Python), `estado/` (almacén y lógica), `pantallas/`, `componentes/` y `estilos/`. |
| `frontend/dist/` | Interfaz compilada. Está versionada para que no haga falta Node.js al ejecutar la aplicación. |
| `frontend/pruebas/` | Pruebas de la lógica de la interfaz: rutina, ajustes, progreso y perfiles. |
| `PRUEBAS/` | Prototipos históricos, arneses de experimentos y hojas de revisión (sección 6.2). |
| `.githooks/commit-msg` y `.gitmessage` | Regla del identificador de ClickUp y plantilla del mensaje de *commit* (sección 10.2). |
| `.claude/skills/estela-card-writer/` | Instrucciones para que Claude Code redacte tarjetas de ClickUp con las convenciones del proyecto. |
| `RESULTADOS-MAC-INFORME-FINAL.md` | Métricas del Mac Studio para el informe final, en estado de borrador. |
| `diagramas/` | Diagramas en PlantUML y en imagen: `mac_diagrams_def/` (versión completa, vigentes), `definitivos/` (versión básica) y `otros/` (versión anterior). |
| `landing/` y `vercel.json` | Página de presentación estática y su publicación en Vercel. No forman parte de la aplicación. |

Cada carpeta importante tiene su propio `README.md` con más detalle: `backend/README.md`, `frontend/README.md`, `backend/estela/dominio/feedback/README.md`, `backend/feedback_testing/README.md` y los de `PRUEBAS/`.

## 4. Organización de la solución a nivel de código

### 4.1 Organización por módulos o capas

El backend sigue el patrón de puertos y adaptadores (*ports and adapters*), adoptado en ADR-007. La idea es que la lógica de los ejercicios no dependa de las herramientas concretas que se usan para capturar imágenes, estimar la pose o hablar. Para lograrlo, el código se divide en tres capas, y cada una solo puede importar a las que están a su derecha:

```text
adaptadores  ──►  aplicacion  ──►  dominio
```

| Capa | Carpeta | Qué contiene | Puede importar |
|---|---|---|---|
| Dominio | `estela/dominio/` | Contrato de datos, geometría, segmentador y conteo, motor de decisión, verbalizador por plantillas, validador y *skills*. | Solo la biblioteca estándar |
| Aplicación | `estela/aplicacion/` | Sesión por imagen, rutina, pausas, DTW, umbrales relativos, reconocimiento del ejercicio, entrenadora, interpretación de órdenes de voz, historial y perfiles. En `puertos.py` define las interfaces que necesita: `Estimador`, `Voz`, `Fuente` y `ResultadoPose`. | Dominio y NumPy |
| Adaptadores | `estela/adaptadores/` | Implementaciones concretas: cámara y vídeo (OpenCV), pose (MediaPipe), voz (Piper), micrófono y Whisper, modelo de lenguaje (Ollama o `llama-server`) e interfaz (pywebview y OpenCV). | Todo |

La regla no es solo una convención. `backend/tests/test_arquitectura.py` falla si el dominio o la aplicación importan un adaptador o una biblioteca de cámara, pose, voz, ventana o red. Por eso el motor se puede probar con datos sintéticos y la sesión con estimadores y voces falsos. También por eso cambiar MediaPipe o Piper por otra herramienta solo exige escribir un adaptador nuevo.

La aplicación reparte el trabajo en varios hilos para que ninguna tarea lenta detenga el análisis. La cámara se lee en un hilo propio que conserva solo la imagen más reciente. La sesión corre en el hilo del orquestador. La voz se reproduce en otro hilo, de modo que la sesión deja la frase en la cola y continúa. En el Mac, el modelo de lenguaje redacta en un hilo aparte (`aplicacion/verbalizacion_aparte.py`) y el micrófono se escucha en otro. Esta organización responde al presupuesto de 33 ms por imagen fijado en ADR-003: el único modelo de inteligencia artificial que corre en cada imagen es el estimador de pose.

Dos reglas de diseño atraviesan todas las capas. La primera es que el motor determinista decide qué error ocurrió, con qué prioridad y si se debe hablar. El verbalizador, sea por plantillas o con un modelo de lenguaje, solo redacta un error ya decidido, y un validador rechaza las frases con el lado o la parte del cuerpo equivocados. Si el modelo falla o tarda más de 400 ms, suena la plantilla. La segunda es que la entrenadora solo usa cifras ya calculadas y propone una acción de una lista cerrada (repetir, descansar, seguir o terminar) sin ejecutarla. Si la persona menciona dolor o una lesión, responde con un texto fijo, sin consultar el modelo.

Por último, la diferencia entre el Mac y los demás equipos está concentrada en un único punto: la función `defectos()` de `config.py`. `__main__.py` la aplica solo a las opciones que no se indicaron en la línea de comandos y, después, comprueba que cada pieza esté disponible (`_crear_estimador`, `_llm_listo` y `_crear_escucha`). El resto del código no pregunta en qué equipo está corriendo.

### 4.2 Relación entre componentes del sistema y código fuente

Las rutas de la tabla son relativas a `backend/estela/`, salvo las que empiezan por `frontend/` o `scripts/` (esta última, relativa a `backend/`).

| Componente | Ubicación | Observaciones |
|---|---|---|
| Fuente de vídeo | `adaptadores/captura/fuente.py` | `FuenteCamara` (hilo propio), `FuenteVideo` y `listar_camaras`. |
| Estimador de pose | `adaptadores/pose/estimador.py`, `landmarks.py` | En la GPU reduce la imagen a 640 px (`LADO_MAX_GPU`) y renueva el detector cada 1 800 imágenes (`RENOVAR_CADA`) para evitar una fuga de memoria. |
| Geometría | `dominio/feedback/motor/geometria.py` | Ángulos, distancias, confianza y orientación. Una medida nueva se añade aquí. |
| Segmentador y conteo | `dominio/conteo/segmentador.py` | Fases, repeticiones y segundos de la plancha, según la sección `segmentacion` de la *skill*. |
| Alineador DTW | `aplicacion/dtw.py` | Incremental: el costo por imagen no crece con la duración de la repetición. Se apaga con `--sin-dtw`. |
| Umbrales relativos | `aplicacion/umbrales.py` | Solo actúan con `--umbrales referencia`. |
| Reconocimiento del ejercicio | `aplicacion/reconocimiento.py` | Usa `skills/referencias/reconocimiento.json`. Apagado por defecto. |
| Contrato de datos | `dominio/feedback/contrato.py` | `Observacion`, `ErrorTipificado`, `Refuerzo`, `Silencio` y `MensajeFeedback`. |
| Carga de *skills* | `dominio/feedback/motor/skill.py` | Valida el esquema y falla si un archivo está mal formado. |
| Motor de decisión | `dominio/feedback/motor/decision.py` | Confianza, orientación, reglas, prioridad y política de silencio. |
| Verbalizador y validador | `dominio/feedback/verbalizador/` | `plantillas.py`, `plantillas_es.json` y `validador.py`. |
| Verbalizador con modelo de lenguaje | `adaptadores/llm/llm_local.py`, `ollama.py`; `aplicacion/verbalizacion_aparte.py` | Ollama o `llama-server`, salida restringida a un esquema JSON y tiempo límite de 400 ms. |
| Entrenadora | `aplicacion/entrenadora.py`; `adaptadores/llm/entrenadora_ollama.py`, `entrenadora_en_vivo.py` | Resumen al final de la rutina y respuesta a «¿cómo voy?». |
| Órdenes de voz | `aplicacion/comandos_voz.py`; `adaptadores/voz_entrada/` | Lista cerrada de órdenes interpretadas con reglas fijas, sin modelo de lenguaje. `escucha.py`, `microfono.py`, `reconocedor.py` y `frases.py`. |
| Voz | `adaptadores/voz/cola.py`, `motores.py`, `sonido.py` | Piper, voz del sistema o solo texto. Las órdenes de la persona interrumpen lo que suena. |
| Sesión | `aplicacion/sesion.py` | Bucle por imagen, colocación, `EstadoFrame` y resumen. |
| Rutina y pausas | `aplicacion/rutina.py`, `pausa.py`, `gesto.py` | El gesto de pausa sigue en el código, pero está apagado. |
| Métricas y registro | `aplicacion/metricas.py`, `registro.py` | Percentiles de latencia y registro por repetición, solo con métricas derivadas. |
| Historial y perfiles | `aplicacion/historial.py`, `perfiles.py` | `historial/perfiles.json` y un archivo `<id>.jsonl` por perfil. |
| Orquestador y ventana | `adaptadores/interfaz/orquestador.py`, `ventana.py`, `contrato.py`, `overlay.py` | Hilo de la sesión, API de pywebview, traducción del estado a JSON y ventana de OpenCV. |
| Interfaz | `frontend/src/` | `bridge/tipos.ts` describe el JSON que produce `contrato.py`. |
| Creación de referencias | `scripts/crear_referencia.py`, `scripts/crear_referencias_reconocimiento.py` | Se ejecutan fuera de línea. |

Los módulos del dominio no se conocen entre sí: la sesión es la que pasa la información de uno a otro. La geometría produce una `Observacion` con medidas, confianza y orientación; el segmentador y el DTW le añaden la fase y los valores de la referencia; y el motor devuelve un `ErrorTipificado`, un `Refuerzo` o un `Silencio` con su motivo. Si hay un error, el verbalizador lo convierte en un `MensajeFeedback`. Finalmente, la sesión reúne todo en un `EstadoFrame`, que `contrato.py` traduce a JSON para la interfaz.

El contrato con la interfaz tiene dos lados que deben cambiar juntos: `adaptadores/interfaz/contrato.py` en Python y `frontend/src/bridge/tipos.ts` en TypeScript. La interfaz pide el estado con consultas largas (*long polling*) y, si va más lenta que la sesión, se salta estados en lugar de acumular retraso. La imagen de la cámara viaja como JPEG de 640 px codificado en base64 y no se guarda en ningún lado. Las funciones visibles se encienden o apagan con el diccionario `CAPACIDADES` de `contrato.py`. Las recetas para añadir un dato, un comando o una pantalla están en `frontend/README.md`, en la sección «Cómo añadir o quitar algo».

## 5. Contenedores

### 5.1 Contenedores utilizados

ESTELA no usa contenedores. La aplicación necesita acceso directo a la cámara, al micrófono, a la salida de audio y al sistema de ventanas y, en el Mac, a la tarjeta gráfica mediante Metal. Un contenedor complicaría ese acceso sin aportar beneficios a un programa que corre en un solo equipo. El aislamiento de dependencias se resuelve con un entorno virtual de Python (sección 8.1).

### 5.2 Archivos relacionados con contenedores

No hay `Dockerfile` ni archivos `docker-compose`. Los archivos que cumplen un papel equivalente son `backend/pyproject.toml`, que declara las dependencias de Python; `frontend/package.json` y `frontend/package-lock.json`, que fijan las de la interfaz; y `backend/scripts/descargar_modelos.py`, que descarga los modelos.

### 5.3 Construcción y ejecución de contenedores

No aplica. El equivalente es crear el entorno virtual, instalar el paquete con sus extras y descargar los modelos, como se describe en la sección 8.1.

### 5.4 Redes, puertos y volúmenes

Sin contenedores no hay redes ni volúmenes que configurar. Aun así, conviene conocer los puertos y las carpetas que usa la aplicación dentro del equipo:

| Recurso | Uso |
|---|---|
| `127.0.0.1:11434` | Ollama: `/api/tags` para comprobar que el modelo está descargado y `/api/chat` para redactar. |
| `127.0.0.1:8080` | `llama-server`, alternativa a Ollama (`--llm-backend llama-server`) y condición F de EXP-001. |
| Sin puerto | La ventana carga `frontend/dist/index.html` directamente, con rutas relativas (`base: './'` en `vite.config.ts`). No hay servidor web propio. |
| Servidor de desarrollo de Vite | Solo con `npm run dev`, al trabajar en la interfaz (por defecto en `localhost:5173`). |
| `backend/historial/`, `backend/sesiones/`, `backend/modelos/` | Carpetas en las que la aplicación escribe. |

### 5.5 Recomendaciones para modificar contenedores

Si en el futuro se quisiera usar contenedores, el uso razonable es la integración continua: ejecutar `pytest` y el banco sintético, que no necesitan cámara, modelos ni micrófono. No se recomienda empaquetar la aplicación completa en un contenedor, por las razones de la sección 5.1. Para distribuirla, la alternativa pendiente es un ejecutable de escritorio (sección 11.2).

## 6. Scripts y automatizaciones

### 6.1 Scripts principales

Los comandos del backend se ejecutan desde `backend/` con el entorno virtual activo, y los de la interfaz desde `frontend/`.

| Comando | Para qué sirve |
|---|---|
| `python -m estela` | Abre la aplicación con la configuración por defecto del equipo. |
| `python -m estela --help` | Lista todas las opciones. |
| `python scripts/descargar_modelos.py` | Descarga los modelos de pose *lite* y *full* y la voz de Piper. Con `--heavy` añade la pose *heavy* y con `--voz-entrada` el modelo de Whisper. En un Mac con Apple Silicon ambos se descargan siempre. |
| `pytest` | Ejecuta las pruebas del backend sin cámara ni modelos. Excluye las mediciones lentas. |
| `pytest -m metricas -s` | Medición del Informe 2 sobre vídeos a ritmo real. Tarda bastante. |
| `python -m feedback_testing.informe2` | Arnés de medición con la sesión real. Admite `--modelo`, `--delegado`, `--salida-md` y `--salida-json`. |
| `python -m feedback_testing.runner` | EXP-001 sobre el banco sintético con plantillas (condición A). `--condicion F` necesita `llama-server`. |
| `npm install` | Instala las dependencias de la interfaz. |
| `npm run dev` | Abre la interfaz en el navegador con un backend simulado, sin cámara ni Python. |
| `npm run build` | Revisa los tipos y compila `frontend/dist/`. |
| `npm run typecheck` | Solo revisa los tipos. |
| `npm test` | Pruebas de la lógica de la interfaz. Requiere haber ejecutado `npm install`. |
| `npm run preview` | Sirve la compilación para revisarla en el navegador. |

Las opciones de `python -m estela` más útiles durante el desarrollo son las siguientes. La sección 12.3 del informe final presenta las opciones pensadas para quien usa la aplicación.

| Opción | Efecto |
|---|---|
| `--video RUTA` | Usa un vídeo en lugar de la cámara. Con vídeo nunca se crean perfiles ni historial. |
| `--sin-ventana` | Ejecuta la sesión sin interfaz gráfica; útil para medir con vídeos. |
| `--tiempo-real` | Con `--video` y `--sin-ventana`, reproduce el vídeo a su ritmo, como una cámara. Sirve para probar por SSH lo que depende del reloj: la voz, el modelo de lenguaje y la entrenadora. |
| `--interfaz opencv` | Ventana simple de OpenCV, sin pantallas de selección. |
| `--rutina RUTA` o `--ejercicio ID --repeticiones N` | Fija la rutina o un solo ejercicio. En la plancha, N son segundos. |
| `--modelo {lite,full,heavy}` y `--delegado {cpu,gpu}` | Variante de la pose y dónde se ejecuta. |
| `--verbalizador {plantillas,llm}`, `--llm-backend {ollama,llama-server}`, `--llm-modelo`, `--llm-url`, `--llm-timeout-ms` | Quién redacta las correcciones y con qué servidor, modelo y tiempo límite. |
| `--entrenadora {no,plantilla,llm}`, `--entrenadora-entre {si,no}`, `--entrenadora-historial RUTA` | Modo de la entrenadora, si habla también entre ejercicios y qué historial usa cuando no hay perfiles. |
| `--voz-entrada {si,no}`, `--voz-entrada-modo {llamada,pausa}`, `--voz-entrada-interrumpir {si,no}`, `--voz-entrada-sonido {si,no}`, `--guarda-eco S` | Órdenes de voz y su comportamiento. |
| `--voz {piper,sistema,texto}` | Motor de voz. Con `texto`, las frases solo se muestran. |
| `--sin-dtw`, `--umbrales {absolutos,referencia}`, `--sin-colocacion`, `--reconocer` | Encienden o apagan partes del análisis para experimentos. |
| `--guardar-metricas` | Guarda el resumen técnico en `backend/sesiones/`, solo con métricas derivadas. |
| `--sin-historial` | Desactiva los perfiles y el historial. |
| `-v` | Registro detallado. Incluye el texto que reconoce el micrófono, por lo que no conviene compartirlo. |

### 6.2 Ubicación de scripts auxiliares

**`backend/scripts/`**

| Script | Propósito |
|---|---|
| `descargar_modelos.py` | Descarga los modelos de pose, la voz de Piper y el modelo de Whisper. |
| `crear_referencia.py` | Construye la referencia de un ejercicio a partir de un vídeo. `--selftest` comprueba el script sin vídeo. |
| `crear_referencias_reconocimiento.py` | Genera `referencias/reconocimiento.json` a partir de los vídeos que declara cada *skill* (EXP-010). |
| `generar_variantes.py` | Pide a un modelo local variantes de las frases de corrección para revisión humana (rol A de ADR-004). |
| `importar_variantes.py` | Pasa a `plantillas_es.json` las variantes aprobadas en una hoja revisada. Sin `--escribir`, solo muestra los cambios. |
| `historial_ejemplo.py` | Genera un historial de ejemplo a partir de `sesiones/*.json`, para probar «Mi progreso» y la entrenadora. |
| `probar_entrenadora.py` | Ejecuta la entrenadora sobre sesiones guardadas y mide su latencia. |
| `hoja_ab.py` | Arma una hoja a ciegas para comparar dos modelos como entrenadora. |
| `medir_llm.py` | Mide la latencia del verbalizador con modelo de lenguaje contra un Ollama local. |
| `medir_variedad_llm.py` | Compara la variedad de las frases redactadas por el modelo. |
| `informe2_sin_arreglo_cola.py` | Repite la medición del Informe 2 con el arreglo de la cola de voz apagado en memoria, como referencia del «antes». |

**`backend/scripts/voz/`**

| Script | Propósito |
|---|---|
| `probar_microfono.py` | Prueba las órdenes de voz con el micrófono, sin cámara ni sesión. |
| `analizar_tanda_voz.py` | Resume una prueba de voz y propone palabras para el léxico de órdenes. |
| `generar_audio_comandos.py` | Genera audio sintético de órdenes con Piper y, en macOS, con `say`. No graba a ninguna persona. |
| `evaluar_reconocedores.py` y `resumen_reconocedores.py` | Comparan whisper.cpp, mlx-whisper y faster-whisper con las órdenes de ESTELA. |
| `medir_llamada.py`, `medir_aviso_estela.py`, `medir_interrumpir.py`, `medir_interrumpir_continuacion.py` | Miden cómo se reconoce «Estela» y si una orden se entiende mientras ESTELA habla. Solo macOS. |
| `medir_todo_a_la_vez.py` | Mide la latencia de la pose con todas las funciones encendidas, frente a la pose sola. |
| `estres_cortes_voz.py` | Somete la cola de voz a muchos cortes desde otros hilos para detectar bloqueos. |
| `muestras_voces.py` | Genera muestras a ciegas de voces candidatas y mide cuánto tarda cada una. |

**`backend/feedback_testing/`**

| Archivo | Propósito |
|---|---|
| `generador_episodios.py`, `metricas.py`, `runner.py` | Banco sintético determinista y métricas de EXP-001. |
| `exp002_observabilidad.py` | EXP-002: error de medir en la imagen según la orientación de la persona. |
| `informe2.py`, `metricas_informe.py` | Arnés que reproduce vídeos por la `Sesion` real y calcula las métricas de tiempo. |

**`PRUEBAS/`**

| Carpeta | Contenido |
|---|---|
| `Prueba red neuronal (dataset-pose-deteccion-conteo)/` | Prototipo histórico con la red BiLSTM, retirada en ADR-006, y el conjunto de vídeos públicos en `DATASET/videos/`. |
| `exp006_dtw/` | Comparación de reglas absolutas y relativas a la referencia, y medición del DTW. |
| `exp008_puntos_tronco/` | Puntos adicionales de tronco y pelvis. |
| `exp009_zancada/` | Volcado de imágenes para ajustar los umbrales de la zancada. |
| `exp010_reconocimiento/` | Reconocimiento del ejercicio. |
| `ab_entrenadora_14b_70b/` | Hoja A/B para comparar Qwen3 14B y Llama 3.3 70B como entrenadora. |
| `variantes_14b/`, `variantes_70b/` | Hojas revisadas de variantes de frases y el script que registra las decisiones. |

### 6.3 Consideraciones para su uso

- Los scripts del backend asumen que se ejecutan desde `backend/`, con el entorno virtual activo.
- Varios scripts de `scripts/voz/` solo funcionan en macOS, porque usan `say` o Metal. Su docstring lo indica.
- `generar_variantes.py`, `medir_llm.py`, `medir_variedad_llm.py`, `hoja_ab.py` y `probar_entrenadora.py` con `--modelo` necesitan Ollama en ejecución y los modelos descargados.
- Los resultados que contienen datos de personas, como el texto que dijo alguien, anotaciones o vídeos, se guardan fuera del repositorio o en `backend/datos_locales/`, que git ignora. Las grabaciones de personas requieren consentimiento informado (Ley 1581 de 2012) y nunca se suben al repositorio.
- Antes de medir latencias hay que cerrar otras ventanas de ESTELA y procesos pesados. En el Mac Studio se aplazó una medición porque otra sesión de trabajo usaba el equipo y habría alterado el percentil 95 (`RESULTADOS-MAC-INFORME-FINAL.md`, paso 1).
- `informe2.py` solo acepta vídeos de las carpetas listadas en `CARPETAS`. En los ejercicios por pierna, el nombre del archivo debe empezar por `izq` o `der`, o terminar en «izquierda» o «derecha»; si no, el vídeo se excluye.
- Algunos scripts de `PRUEBAS/` usan `mp.solutions`, la API anterior de MediaPipe, que no existe en mediapipe 1.x. Tienen su propio `requirements.txt` y deben ejecutarse en un entorno aparte.

## 7. Variables de entorno

### 7.1 Variables requeridas

ESTELA no necesita variables de entorno. Las rutas se calculan a partir de la ubicación de `backend/` (`config.RAIZ`) y la configuración se elige con opciones de línea de comandos. Tampoco hay claves de acceso, porque la aplicación no se conecta a servicios externos durante la sesión.

Las pocas variables que aparecen en el código son opcionales o las define el propio programa:

| Variable | Dónde se usa | Para qué |
|---|---|---|
| `GLOG_minloglevel` y `TF_CPP_MIN_LOG_LEVEL` | `estela/__main__.py` y `feedback_testing/informe2.py` | El programa las fija en `2` si no existen, para silenciar los mensajes internos de MediaPipe. |
| `ESTELA_MODELOS` | `feedback_testing/informe2.py` | Opcional. Carpeta adicional donde el arnés busca los modelos de pose. |
| `HF_HOME` | `scripts/voz/evaluar_reconocedores.py` | El script la fija para guardar en su propia caché los modelos que descarga. |
| `PATH` | macOS, en sesiones por SSH | Hay que añadir `/opt/homebrew/bin:/usr/local/bin` para encontrar el comando `ollama`. |

### 7.2 Variables por ambiente

El proyecto no distingue ambientes de desarrollo, pruebas y producción, porque no tiene servidor. Lo que cambia es el equipo. La función `defectos()` de `backend/estela/config.py` decide qué se enciende cuando no se indica una opción:

| Opción | Mac con Apple Silicon | Otros equipos |
|---|---|---|
| `--modelo` | `heavy` | `lite` |
| `--delegado` | `gpu` (Metal) | `cpu` |
| `--verbalizador` | `llm` | `plantillas` |
| `--entrenadora` | `llm` | `no` |
| `--voz-entrada` | `si` | `no` |
| `--voz-entrada-modo` | `llamada` | `pausa` |
| `--voz-entrada-interrumpir` | `si` | `no` |

Cualquier opción indicada en la línea de comandos manda sobre el valor del equipo. Además, si falta una pieza, `__main__.py` lo avisa en el registro y sigue con la opción básica:

- Si falta el modelo *heavy*, usa *full* en el procesador.
- Si el delegado de la GPU no arranca, usa el procesador; en ese caso, *heavy* pasa a *full*, porque *heavy* en el procesador no cabe en 33 ms (percentil 95 de 58 ms en el Mac Studio, según `__main__.py`).
- Si Ollama no responde o le falta el modelo, las correcciones y la entrenadora usan plantillas.
- Si no hay micrófono al arrancar, la sección «Micrófono» de los ajustes lo indica y permite encenderlo después. Si falta el modelo de Whisper, la sesión sigue sin órdenes de voz.

Los modelos y tiempos límite por defecto también están en `config.py`. Los comentarios de ese archivo explican de qué medición sale cada valor.

| Constante | Valor | Significado |
|---|---|---|
| `LLM_MODELO` | `qwen3:4b-instruct-2507-q4_K_M` | Modelo que redacta las correcciones. |
| `LLM_TIMEOUT_MS` | 400 | Tiempo límite por frase; pasado ese tiempo suena la plantilla. |
| `ENTRENADORA_MODELO` | `qwen3:14b` | Modelo de la entrenadora. |
| `ENTRENADORA_TIMEOUT_S` | 5,0 | Tiempo límite de la entrenadora. |
| `VOZ_ENTRADA_MODELO` | `small` | Modelo de Whisper para las órdenes de voz. |
| `GUARDA_ECO_S` | 0,0 | Segundos que la escucha sigue ignorando el audio después de que ESTELA calla. Está sin calibrar con un micrófono real. |

### 7.3 Archivos de configuración

No hay archivos `.env`. La configuración está repartida en los siguientes archivos, todos versionados:

| Archivo | Qué configura |
|---|---|
| `backend/estela/config.py` | Rutas, modelos, tiempos límite y valores por defecto de cada equipo. |
| `backend/pyproject.toml` | Dependencias, extras (`voz`, `voz-entrada`, `interfaz`, `dev`) y pytest, incluidas las marcas `video` y `metricas`. |
| `backend/estela/dominio/feedback/skills/*.json` | Ejercicios: fases, orientación, reglas, umbrales y política de silencio. El formato está en `ESQUEMA.md`. |
| `backend/estela/dominio/feedback/skills/referencias/` | Referencias de cada ejercicio y del reconocimiento. Se generan con los scripts de la sección 6.2. |
| `backend/estela/dominio/feedback/verbalizador/plantillas_es.json` | Frases en español por tipo de error. |
| `backend/rutinas/*.json` | Rutinas: lista de pasos con `repeticiones`, o `duracion_s` en la plancha. |
| `backend/estela/adaptadores/interfaz/contrato.py` | `CAPACIDADES`, que encienden o apagan funciones de la interfaz, y los límites del objetivo que puede elegir la persona. |
| `frontend/vite.config.ts`, `frontend/tsconfig.json` | Compilación de la interfaz. |
| `frontend/src/estilos/tokens.css` | Colores, radios y espaciado de la interfaz. |

La aplicación también escribe archivos mientras funciona. No son configuración, pero conviene saber dónde están: `backend/historial/perfiles.json` y `backend/historial/<id>.jsonl` (perfiles e historial) y `backend/sesiones/*.json` con `*-repeticiones.csv` (métricas de `--guardar-metricas`).

### 7.4 Manejo seguro de secretos

La aplicación no maneja secretos: no hay claves de API, *tokens* ni contraseñas, y Ollama se usa en el mismo equipo sin autenticación. Los perfiles tampoco tienen contraseña, y la interfaz lo advierte.

Lo que sí requiere cuidado son los datos de personas. El historial solo guarda los campos permitidos (fecha, rutina, objetivo, lo completado, duración, pausas e indicaciones dadas) y nunca imágenes, puntos del cuerpo ni ángulos. El audio del micrófono no se guarda, y de lo que se ignora en modo «llamada» solo se registra cuántas palabras tenía y cuánto tardó, nunca el texto, salvo con `-v`. Estas reglas aplican también al desarrollo:

- No subir al repositorio `backend/modelos/`, `backend/sesiones/`, `backend/historial/`, `backend/datos_locales/` ni `INFORME2-metricas.json`. El `.gitignore` ya los excluye.
- No subir grabaciones ni fotografías de personas. Las grabaciones propias del equipo se guardan fuera del repositorio y con consentimiento informado.
- No compartir registros generados con `-v`, porque pueden contener lo que dijo la persona.

Si en el futuro se integrara un servicio que requiera credenciales, estas deberán leerse de variables de entorno o de un archivo excluido por `.gitignore`, nunca escribirse en el código.

## 8. Flujo de trabajo de desarrollo

### 8.1 Preparación del entorno

Los pasos para empezar a desarrollar son los siguientes:

```bash
git clone https://github.com/isaAJ05/ESTELA.git   # versión básica: añadir -b test
cd ESTELA
git config core.hooksPath .githooks     # activa la regla del identificador de ClickUp
git config commit.template .gitmessage  # plantilla del mensaje de commit

cd backend
python3 -m venv .venv
source .venv/bin/activate               # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[voz,interfaz,dev]"    # en el Mac: ".[voz,voz-entrada,interfaz,dev]"
python scripts/descargar_modelos.py     # en el Mac también descarga heavy y Whisper
pytest                                  # no necesita cámara ni modelos
python -m estela
```

En Windows, si PowerShell no permite activar el entorno, se habilita una vez con `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

En el Mac hacen falta, además, tres pasos. Primero, instalar la aplicación de Ollama y descargar los dos modelos con `ollama pull qwen3:4b-instruct-2507-q4_K_M` y `ollama pull qwen3:14b`. Segundo, aceptar los permisos de cámara y micrófono la primera vez, ejecutando la aplicación desde la Terminal frente al equipo; por SSH no se pueden aceptar. Tercero, si se trabaja por SSH, añadir al `PATH` la ruta de Ollama (sección 7.1). En el Mac Studio el entorno se creó con uv (`uv sync --extra voz --extra voz-entrada --extra interfaz --extra dev`), y `pywhispercpp` se instaló como rueda precompilada con Metal, sin compilar whisper.cpp.

La interfaz compilada ya está en el repositorio, así que Node.js solo hace falta para modificarla. En ese caso:

```bash
cd frontend
npm install
npm run dev          # interfaz en el navegador con backend simulado
```

`Instalación.md` indica Node.js 20 o superior. El comando `npm test` usa la opción `--experimental-strip-types`, que requiere una versión de Node.js que la admita (22.6 o posterior).

### 8.2 Desarrollo de nuevas funcionalidades

Cada cambio parte de una tarea en ClickUp, porque su identificador va en los mensajes de *commit*. La rama se crea desde la línea a la que pertenece el cambio: `main` para la versión final, o `test` para la versión básica. Los nombres usados en el proyecto son `feature/<tema>`, `refactor/<tema>` y los que genera ClickUp, con la forma `CU-<id>_<descripción>`.

Antes de escribir código conviene decidir en qué capa va. Si el cambio usa una biblioteca nueva o un dispositivo, va en un adaptador; si necesita que la sesión lo use, la interfaz se declara en `aplicacion/puertos.py`. La lógica de los ejercicios va en el dominio y no puede importar nada fuera de la biblioteca estándar.

Las tareas más frecuentes tienen un camino conocido:

| Tarea | Pasos |
|---|---|
| Añadir un ejercicio | Crear `skills/<id>.json` siguiendo `ESQUEMA.md`, declarar `medidas_referencia` y generar su referencia con `scripts/crear_referencia.py`. Para el reconocimiento, declarar `videos_reconocimiento` y regenerar `reconocimiento.json`. Añadirlo a una rutina. Solo hace falta código si necesita una medida que `geometria.py` no calcula. |
| Cambiar o añadir frases | Editar `plantillas_es.json`. Las variantes redactadas por un modelo pasan por `generar_variantes.py`, una revisión humana e `importar_variantes.py`. |
| Añadir una orden de voz | Ampliar la lista cerrada de `aplicacion/comandos_voz.py` y conectarla con la acción correspondiente del orquestador, que es el mismo camino que usan los botones. |
| Añadir un dato, un comando o una pantalla a la interfaz | Seguir la tabla «Cómo añadir o quitar algo» de `frontend/README.md`. Siempre se cambian juntos `contrato.py` y `tipos.ts`. |
| Cambiar lo que se enciende en cada equipo | Modificar solo `config.defectos()` y su prueba. |

Toda etapa nueva dentro del bucle por imagen debe medirse con el percentil 50 y el percentil 95 frente al presupuesto de 33 ms. Las tareas pesadas o de duración variable, como redactar con un modelo de lenguaje o reconocer la voz, van en un hilo aparte. El proyecto aprendió esto en el Mac: cuando el modelo de lenguaje redactaba dentro del bucle, 10 de 7 694 imágenes superaron los 33 ms, con un máximo de 314 ms (`RESULTADOS-MAC-INFORME-FINAL.md`, paso 2). Por eso la redacción pasó a `VerbalizacionAparte`.

Cuando un cambio afecta la arquitectura, la tecnología, el alcance o la reproducibilidad, se registra un ADR en `docs_estela/decisiones/`. Cuando una alternativa necesita evidencia, se plantea un experimento en `docs_estela/experimentos/` antes de decidir. El `README.md` afectado se actualiza en el mismo cambio.

### 8.3 Ejecución de pruebas y validaciones

| Verificación | Comando | Qué cubre |
|---|---|---|
| Pruebas del backend | `pytest` (desde `backend/`) | Dominio, sesión con piezas simuladas, interfaz, voz, historial, perfiles, entrenadora, órdenes de voz y reglas de arquitectura. No necesita cámara ni modelos. |
| Mediciones con vídeo | `pytest -m metricas -s` | Tiempos del Informe 2 sobre vídeos. Excluidas por defecto en `pyproject.toml`. |
| Tipos de la interfaz | `npm run typecheck` | Errores de TypeScript. |
| Pruebas de la interfaz | `npm test` | Lógica de rutina, ajustes, progreso y perfiles. |
| Compilación | `npm run build` | Genera `frontend/dist/`, que debe subirse junto con los cambios de `src/`. |

Algunas pruebas se omiten solas cuando falta lo que necesitan. `test_voz_entrada_real.py` necesita `pywhispercpp`; `test_dtw_video.py` necesita un vídeo y el modelo de pose; y parte de `test_voz_y_landmarks.py` necesita la API de visión de MediaPipe. En el Mac Studio pasan 731 pruebas, sin fallos ni omisiones, en el *commit* `082c2e3` (`RESULTADOS-MAC-INFORME-FINAL.md`, paso 0). En un portátil con Windows, Python 3.13.5 y mediapipe 1.1.0, la ejecución del 21 de noviembre de 2026 sobre `4336bdf` dio 720 pruebas aprobadas, 5 omitidas y 12 excluidas por la marca `metricas`, en 32 s.

Además de las pruebas automáticas, conviene una prueba de punta a punta sin cámara, que es reproducible:

```bash
python -m estela --ejercicio jumping_jacks --video RUTA.mp4 --voz texto --sin-ventana --guardar-metricas
```

El resumen final muestra las repeticiones completas e incompletas, las correcciones emitidas, las pausas y la latencia por etapa. Dentro de la interfaz, la tecla `D` muestra las imágenes por segundo y la latencia de cada etapa durante la sesión. El repositorio no tiene integración continua, así que estas verificaciones se ejecutan a mano antes de integrar.

### 8.4 Integración de cambios

Los cambios se integran con *pull requests* en GitHub. Durante el semestre, la rama de integración fue `test` (por ejemplo, las *pull requests* #16 a #19 y #21). La versión final se desarrolló en `feature/mac-flujo`, que incorporó `test` mediante fusiones (entre ellas la *pull request* #20) y se integró en `main` con la *pull request* #24. Desde entonces, `main` es la versión final y `test` la básica. Cuando un cambio hecho en una de las dos deba estar también en la otra, hay que llevarlo con una fusión o un *cherry-pick*, sin pasar a `test` lo que depende del Mac.

Antes de abrir una *pull request*, el cambio debería cumplir estos criterios mínimos:

- `pytest` pasa completo y, si se tocó la interfaz, también `npm run typecheck` y `npm test`.
- Si cambió `frontend/src/`, `frontend/dist/` está recompilado e incluido.
- Cada *commit* lleva el identificador de su tarea de ClickUp.
- No incluye modelos, vídeos, datos de personas ni archivos de `sesiones/` o `historial/`.
- Si cambió el comportamiento, el `README.md` correspondiente está actualizado y, si aplica, el ADR o el experimento.
- Si afecta el bucle por imagen, se midió su latencia.

## 9. Dependencias y servicios externos

### 9.1 Servicios externos integrados

Durante una sesión, ESTELA no usa ningún servicio externo: todo ocurre en el equipo. Los servicios de terceros solo intervienen en la instalación y en la gestión del proyecto:

| Servicio | Para qué | Cuándo |
|---|---|---|
| PyPI | Dependencias de Python | Instalación |
| Registro de npm | Dependencias de la interfaz | Solo para modificar la interfaz |
| Google Cloud Storage (`storage.googleapis.com/mediapipe-models`) | Modelos de MediaPipe Pose Landmarker | `descargar_modelos.py` |
| Hugging Face | Voz de Piper (mediante `piper.download_voices`) y modelo `ggml-small.bin` de whisper.cpp | `descargar_modelos.py` |
| Registro de modelos de Ollama | Qwen3 4B y Qwen3 14B | `ollama pull` |
| GitHub | Código, ramas y *pull requests* | Desarrollo |
| ClickUp | Tablero de tareas | Gestión |
| Vercel | Publicación de `landing/` desde `main` | Página de presentación |

Dentro del equipo hay dos servicios locales. Ollama atiende en `127.0.0.1:11434`. La aplicación comprueba al arrancar que el modelo esté descargado y lo precarga en segundo plano. El contexto se limita a 2 048 *tokens* en el verbalizador y a 4 096 en la entrenadora, y la respuesta del verbalizador se restringe a un esquema JSON. Si Ollama descarga el modelo por inactividad, la aplicación lo vuelve a cargar en segundo plano. La alternativa, `llama-server` de llama.cpp, atiende en `127.0.0.1:8080` con una API compatible con OpenAI y se conserva para la condición F de EXP-001.

### 9.2 Requisitos de acceso

La aplicación no requiere cuentas ni credenciales. Para trabajar en el proyecto, en cambio, un equipo nuevo necesita:

- Acceso de escritura al repositorio `isaAJ05/ESTELA` en GitHub.
- Acceso al repositorio de documentación `docs_estela`, donde están los ADR y los experimentos.
- Acceso al espacio del proyecto en ClickUp, para crear tareas y obtener sus identificadores.
- Acceso al proyecto de Vercel vinculado al repositorio, solo si se va a modificar la página de presentación.

Para la configuración completa hace falta un Mac con Apple Silicon. Según la medición hecha por el equipo en el Mac Studio el 20 de noviembre de 2026, con todo encendido Ollama ocupa 12,6 GB (9,0 GB el modelo de 14B y 2,9 GB el de 4B) y la aplicación 1,8 GB, en total unos 14,4 GB sin contar macOS. El mínimo estimado, no medido, es de 24 GB de memoria unificada (leyenda de `diagramas/mac_diagrams_def/codigosdiagramas/completos/DESPLIEGUE_sistema.wsd`).

### 9.3 Consideraciones de desarrollo y pruebas

El proyecto se diseñó para poder desarrollarse sin la persona frente a la cámara y, en buena parte, sin el Mac. Estas son las herramientas disponibles:

- **Piezas simuladas en las pruebas:** la sesión recibe estimadores y voces falsos, y el dominio se prueba con datos sintéticos.
- **Simulador de la interfaz:** `npm run dev` usa `src/bridge/simulado.ts`. Con la versión compilada se abre `dist/index.html?simulado`. Los parámetros `?velocidad=4` y `?escena=resumen` o `?escena=error` aceleran el tiempo o empiezan en una pantalla concreta.
- **Banco sintético:** `feedback_testing/` genera las medidas que consume el motor. Sirve para medir el determinismo, la sobrecorrección y la abstención, pero no para saber si los umbrales son correctos, porque no simula el cuerpo humano (ver `feedback_testing/README.md`).
- **Audio sintético:** las órdenes de voz se prueban con frases generadas por Piper y por `say`, sin grabar a nadie.
- **Vídeos públicos:** `PRUEBAS/Prueba red neuronal (dataset-pose-deteccion-conteo)/DATASET/videos/` en este repositorio, y `investigacion/fuentes/datasets/videos/` en `docs_estela`.
- **Historial de ejemplo:** `scripts/historial_ejemplo.py` permite probar «Mi progreso» y la entrenadora sin sesiones reales.
- **Pruebas remotas:** `--video`, `--tiempo-real` y `--sin-ventana` permiten probar por SSH lo que depende del reloj.

Estas herramientas tienen límites. La GPU, whisper.cpp con Metal y los modelos de lenguaje solo se midieron en el Mac Studio. Las órdenes de voz no se han medido con un micrófono real. El cambio de la GPU al procesador no se puede provocar sin modificar el código y solo se comprobó con un arnés externo (`RESULTADOS-MAC-INFORME-FINAL.md`, paso 6).

## 10. Convenciones del proyecto

### 10.1 Convenciones de código

- **Idioma:** los identificadores, archivos, comentarios, mensajes y documentación están en español (`Sesion`, `cargar_catalogo`, `verbalizar`). Solo se conservan en inglés los nombres de bibliotecas y conceptos técnicos.
- **Capas:** el dominio solo importa la biblioteca estándar, la aplicación además NumPy y los adaptadores lo que necesiten. `test_arquitectura.py` lo comprueba.
- **Python:** se usan `from __future__ import annotations`, anotaciones de tipo y `dataclasses`. Cada módulo empieza con un docstring que explica qué hace y por qué. Las constantes llevan un comentario `#:` que las documenta.
- **Origen de los valores:** cuando un valor sale de una medición, de una recomendación o es desconocido, el comentario lo marca con las etiquetas del proyecto: `[F]` comprobado, `[F-2]` fuente secundaria, `[I]` inferencia, `[R]` recomendación y `[?]` desconocido. Por ejemplo, `GUARDA_ECO_S` está marcado como `[?]`.
- **Errores:** en las fronteras de confianza el código falla de forma explícita; por ejemplo, el cargador de *skills* no acepta un archivo a medias. Con el hardware y los servicios opcionales hace lo contrario: avisa en el registro y sigue con la opción básica.
- **Privacidad:** el historial solo escribe los campos permitidos y nada del cuerpo. Los datos de experimentos salen solo con `--guardar-metricas`.
- **Skills:** `skill_id` en minúsculas con guiones bajos; los ejercicios por pierna terminan en `_izq` o `_der`; cada `error_id` es único dentro de la *skill* y cada regla tiene una prioridad distinta.
- **Interfaz:** la interfaz no decide nada. Cada componente lee solo su parte del estado con `useEstado(selector)`, y el lienzo de la cámara se dibuja fuera de React con `requestAnimationFrame`. Las medidas van en `rem` y los colores salen de `estilos/tokens.css`. Las funciones condicionadas se consultan con `useCapacidad('<nombre>')`.
- **Herramientas de estilo:** el repositorio no tiene un *linter* ni un formateador configurados. La comprobación automática se limita a pytest y a `tsc`, así que se debe seguir el estilo del código existente.

### 10.2 Convenciones de repositorio

**Ramas.** `main` contiene la versión final, la documentación y la página de presentación; `test` contiene la versión básica y fue la rama de integración durante el semestre. Las ramas de trabajo usan los prefijos `feature/` y `refactor/`, o el nombre que genera ClickUp (`CU-<id>_<descripción>`).

**Mensajes de *commit*.** La plantilla `.gitmessage` define el formato `<tipo>(<módulo>): <descripción>`, con los tipos `feat`, `fix`, `refactor`, `docs`, `test`, `perf` y `chore`. El identificador de la tarea de ClickUp es obligatorio y puede escribirse como `CU-abc123`, `#abc123` o `EST-123`. En los *commits* de la versión final, la forma más usada es `CU-1dfdp8dm54b - feat(voz): …`. Los mensajes se escriben en español y suelen explicar el porqué del cambio y, cuando existen, las cifras medidas que lo justifican.

El *hook* `.githooks/commit-msg` rechaza los mensajes sin identificador, pero solo actúa si cada persona lo activa con `git config core.hooksPath .githooks`. Algunos *commits* del historial no llevan identificador, lo que indica que el *hook* no estuvo activo en todos los equipos.

**Versionado.** El repositorio no usa etiquetas de versión. El paquete de Python y la interfaz están en la versión 0.1.0. Cada *skill* tiene su propia `version` y su `estado` (`candidato`, `candidato_en_duda`, `adoptado` o `descartado`); las *skills* vigentes están en la versión 0.2.0, con estado `candidato`. La interfaz compilada (`frontend/dist/`) se versiona junto con el código fuente.

### 10.3 Convenciones de documentación

La documentación se organiza en tres niveles. En la raíz del repositorio están los informes y los manuales. Junto al código están los `README.md` técnicos y `skills/ESQUEMA.md`, que deben actualizarse en el mismo cambio que modifica el comportamiento que describen. En el repositorio `docs_estela` están los ADR, los experimentos y la investigación.

Un ADR se registra cuando una decisión afecta la arquitectura, la tecnología, el alcance o la reproducibilidad, y no para detalles menores. Cada ADR indica su estado (propuesta, aceptada o enmendada). Los experimentos separan la pregunta, las alternativas, el método, las métricas, los resultados medidos, la interpretación y la conclusión, y fijan el criterio de decisión antes de medir. Los resultados medidos nunca se presentan como supuestos ni como hallazgos de la literatura, y se usan las mismas etiquetas de evidencia descritas en la sección 10.1.

Los resultados de las mediciones se guardan en carpetas `resultados/` con la fecha y, cuando aplica, la rama en el nombre; por ejemplo, `INFORME2-metricas_mac-flujo_2026-11-20_1620.md`. Los diagramas se escriben en PlantUML (archivos `.wsd` en `codigosdiagramas/`) y se exportan a imagen.

## 11. Problemas frecuentes y recomendaciones

### 11.1 Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `No existe el modelo de pose …` | No se descargaron los modelos. | `python scripts/descargar_modelos.py` |
| `Voz 'piper' no disponible`, o se oye la voz del sistema | Falta el extra `voz` o la voz no se descargó. | `pip install -e ".[voz]"` y volver a descargar los modelos. |
| En el registro: `Verbalizador LLM: Ollama no responde en http://127.0.0.1:11434 (…). Se usan las plantillas.` | Ollama no está abierto. | Abrir Ollama y reiniciar ESTELA. |
| En el registro: `falta el modelo … en Ollama (ollama pull …)` | El modelo no está descargado. | Ejecutar el `ollama pull` que indica el mensaje. |
| En el registro: `El delegado GPU no arrancó (…): se usa full en CPU.` | Falló el delegado de la GPU de MediaPipe. | Revisar el error en el registro. Este aviso no aparece en la ventana. |
| En el registro: `Falta el modelo heavy …: se usa full en CPU.` | Falta `pose_landmarker_heavy.task`. | `python scripts/descargar_modelos.py --heavy` |
| No hay órdenes de voz | Fuera del Mac están apagadas por defecto; falta el extra `voz-entrada` o el modelo de Whisper; o el micrófono no estaba conectado al arrancar. | `--voz-entrada si`, `pip install -e ".[voz-entrada]"`, `python scripts/descargar_modelos.py --voz-entrada`, o encender el micrófono en Ajustes. |
| macOS no da acceso a la cámara o al micrófono | Los permisos no se aceptaron; por SSH no se pueden aceptar. | Ejecutar una vez desde la Terminal frente al equipo y aceptar los permisos. |
| `ollama: command not found` por SSH | El `PATH` de las sesiones no interactivas no incluye Ollama. | `export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH` |
| Tras un rato sin uso, una corrección suena con la plantilla | Ollama descargó el modelo de memoria y se está recargando. | Esperar a la recarga en segundo plano; el modelo también se precarga al empezar cada sesión. |
| `Falta pywebview` | Falta el extra `interfaz`. | `pip install -e ".[interfaz]"`, o usar `--interfaz opencv`. |
| `No existe frontend/dist/index.html` | La interfaz no está compilada. | `cd frontend && npm install && npm run build` |
| La ventana no abre en Linux (`GTK cannot be loaded`) | Falta WebKitGTK con PyGObject, o Qt. | Instalarlos, o usar `--interfaz opencv`. |
| PowerShell no permite activar el entorno | Política de ejecución de Windows. | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| «No se detecta la cámara» en la pantalla de inicio | Cámara desconectada u ocupada por otra aplicación. | Liberarla y pulsar «Reintentar». |
| El contador no avanza | La orientación no es la del ejercicio, o hay poca visibilidad. | Seguir el aviso de colocación («de frente» o «de perfil») y encuadrar el cuerpo entero. |
| La sesión se pausa sola | Pasaron 5 s sin detectar a la persona (`PAUSA_SIN_PERSONA_S`). | Volver al encuadre con la orientación pedida; la sesión retoma sin perder repeticiones. La pausa por inactividad y la del gesto están apagadas desde `f4ed26d`. |
| Pocas imágenes por segundo | Pose *full* o *heavy* en un procesador lento. | `--modelo lite` |
| `npm test` falla con `ERR_MODULE_NOT_FOUND: Cannot find package 'react'` | No se instalaron las dependencias de la interfaz. | `npm install` en `frontend/`. |
| `mp.solutions` no existe | Script antiguo de `PRUEBAS/` con la API anterior de MediaPipe. | Usar un entorno aparte con el `requirements.txt` de esa carpeta. |
| `informe2` excluye un vídeo | La carpeta no está en `CARPETAS` o el nombre no indica el lado. | Renombrar el archivo con el prefijo `izq` o `der`. |
| Git rechaza el *commit* | Falta el identificador de ClickUp. | Añadir `CU-<id>` al mensaje. |

### 11.2 Deuda técnica conocida

**Calibración y validación pendientes**

- Los umbrales de las *skills* son provisionales y el catálogo de errores sigue pendiente de validación con la especialista (ADR-005). Las reglas relativas a la referencia están implementadas, pero apagadas hasta calibrar `k` con datos reales anotados (EXP-005 y EXP-006).
- El verbalizador con modelo de lenguaje está encendido por defecto en el Mac, pero su adopción depende de EXP-001 (rol C de ADR-004). La condición F de ese experimento nunca se ha ejecutado con sesiones anotadas.
- Las variantes de frases redactadas por los modelos de 70B y 14B (`cbfb1bb` y `082c2e3`) fueron revisadas por Claude a pedido del equipo, no por la especialista. `plantillas_es.json` lo indica con el campo `revision_pendiente`.
- Las órdenes de voz solo se probaron con audio sintético. `GUARDA_ECO_S` está en cero sin calibrar, los valores de corte de frases de `frases.py` son de ingeniería y el modo «interrumpir» no se ha medido con el eco de la sala.
- El reconocimiento del ejercicio está apagado por defecto porque daba falsas alarmas con variaciones del ejercicio correcto.

**Mediciones pendientes o sin herramienta**

- No existe una herramienta que mida el tiempo desde la detección del error hasta el inicio de la voz con el modelo de lenguaje encendido. `informe2.py` usa plantillas, y el paso 3 de `RESULTADOS-MAC-INFORME-FINAL.md` describe qué habría que cambiar.
- En el Mac quedan pendientes las mediciones de latencia con la zancada y la repetición de la medición con todas las funciones a la vez (pasos 1, 2 y 4.1 del mismo archivo). Cuatro vídeos de zancada se excluyen porque su nombre no indica el lado.

**Código**

- La aplicación no comprueba al arrancar que existan las medidas que usan las reglas. Si una regla menciona una medida desconocida, simplemente no se evalúa.
- Cuando la aplicación cae a una opción básica (GPU, Ollama, Whisper), solo lo avisa en el registro; la interfaz no lo muestra.
- El gesto de pausa sigue en el código (`gesto.py`, `Sesion.gesto_pausa = False`) aunque está apagado. Falta decidir si se elimina.
- No hay un ejecutable de escritorio: la aplicación se ejecuta desde el código fuente.
- No hay integración continua ni herramientas de estilo configuradas.

**Repositorio y documentación**

- Algunos documentos quedaron atrás del código. `backend/README.md` dice que el adaptador de modelo de lenguaje solo lo usa EXP-001. `frontend/README.md` presenta el gesto de pausa como activo. El docstring de `aplicacion/pausa.py` describe la pausa por inactividad como si siguiera encendida. La sección 11.2 del informe final indica 656 pruebas, cuando en el Mac pasan 731.
- El informe final cita ADR-008 y ADR-009, pero no existen como archivos en `docs_estela/decisiones/`. La configuración del Mac, la entrenadora y las órdenes de voz no tienen un ADR propio.
- Algunas cifras del Mac solo constan en mensajes de *commit* o en un `ESTADO.md` que vive en el Mac, fuera de git.
- La clave de la hoja A/B de la entrenadora está versionada en `PRUEBAS/ab_entrenadora_14b_70b/clave_NO_ABRIR/`, así que la hoja deja de ser a ciegas para quien la abra. Además, desde `3c7d229` la entrenadora no habla entre ejercicios, por lo que solo 7 de sus 20 situaciones reflejan el comportamiento actual.

### 11.3 Recomendaciones para continuidad

1. **Mantener alineadas las dos versiones.** Llevar a `test` los arreglos de `main` que no dependan del Mac, para que la versión básica no se quede atrás.
2. **Actualizar la documentación desactualizada** de la sección 11.2 antes de añadir funciones nuevas.
3. **Grabar el banco real** con consentimiento informado y anotarlo. Con él se puede calibrar `k` (EXP-005), decidir sobre las reglas relativas (EXP-006) y ejecutar la condición F de EXP-001.
4. **Medir las órdenes de voz con micrófono real**, siguiendo la guía del paso 5 de `RESULTADOS-MAC-INFORME-FINAL.md`, y calibrar `GUARDA_ECO_S`.
5. **Completar la medición de la detección a la voz** con el modelo de lenguaje encendido.
6. **Mostrar en la interfaz** cuándo la aplicación funciona con una opción básica, y validar al arrancar que existen las medidas que usan las reglas.
7. **Configurar integración continua** que ejecute `pytest`, `npm run typecheck` y `npm test` en cada *pull request*.
8. **Registrar los ADR que faltan** (ADR-008, ADR-009 y la configuración del Mac) y retirar del repositorio la clave de la hoja A/B si se va a calificar.
9. **Mantener el presupuesto de 33 ms por imagen** como criterio de aceptación de cualquier etapa nueva.

Como trabajo futuro, el informe final (sección 15) propone un perfil de entrenador que permita crear *skills* sin editar archivos. No forma parte del alcance actual.

## 12. Historial de decisiones técnicas relevantes

Las decisiones principales están registradas como ADR en `docs_estela/decisiones/`. La sección 7.1 del informe final las resume, y aquí se recuerdan por su efecto en el código.

| Registro | Decisión | Efecto en el código | Estado |
|---|---|---|---|
| ADR-001 | Un motor de reglas decide el error y las plantillas lo redactan. Un modelo de lenguaje solo podría redactar un error ya decidido. | Separación entre `motor/decision.py` y `verbalizador/`. | Propuesta, condicionada a EXP-001 |
| ADR-002 | Formato de los datos que recibe el motor. | `dominio/feedback/contrato.py`. | Propuesta |
| ADR-003 | Primera aplicación completa y objetivo de 33 ms por imagen. | `aplicacion/sesion.py` y adaptadores. | Propuesta e implementada |
| ADR-004 | Comparación con una referencia mediante DTW, umbrales relativos y papeles permitidos al modelo de lenguaje. | `aplicacion/dtw.py`, `umbrales.py` y `adaptadores/llm/`. | Aceptada |
| ADR-005 | Solo ejercicios cuyos errores se ven con una cámara, cada uno con su orientación. La zancada reemplazó a la marcha. | *Skills* vigentes y `skills/retirados/`. | Aceptada, con dos enmiendas |
| ADR-006 | Un solo motor; se descartan SpinePose y la red BiLSTM; solo se felicita lo comprobado. | Motor único y política de refuerzo. | Aceptada |
| ADR-007 | Tres capas y separación entre backend e interfaz. | Estructura de `backend/estela/` y `test_arquitectura.py`. | Aceptada |
| ADR-008 | Historial y «Mi progreso» guardados solo en el equipo, sin datos del cuerpo. | `aplicacion/historial.py`. | Propuesta, sin archivo |
| ADR-009 | Perfiles locales para varias personas en el mismo equipo. | `aplicacion/perfiles.py`. | Propuesta, sin archivo |

Otras decisiones de implementación no tienen un ADR, pero cambiaron el código de forma importante:

| Fecha | Decisión | Motivo |
|---|---|---|
| Octubre de 2026 | DTW incremental en lugar de recalcular toda la repetición en cada imagen. | El tiempo del DTW crecía con la duración de la repetición. |
| 24 oct. 2026 (`3799a55`) | Las correcciones no esperan detrás de los avisos en la cola de voz. | Una corrección podía esperar varios segundos al anuncio del ejercicio. |
| 14 nov. 2026 | La marcha se archiva por completo. | El sistema confundía las piernas. |
| 16 nov. 2026 (`19dd8db`, `4e89d47`) | Pose en la GPU del Mac y valores por defecto según el equipo. | En el Mac, *heavy* en la GPU cabe en el presupuesto; en el procesador, no. |
| 17 nov. 2026 (`9df14b6`) | Imagen reducida a 640 px y detector renovado cada 1 800 imágenes en la GPU. | Corregir una fuga de memoria del delegado de la GPU. |
| Noviembre de 2026 | Qwen3 4B para las correcciones, con contexto de 2 048 *tokens*, y Qwen3 14B para la entrenadora. | El 4B redacta con un percentil 95 de 185 ms y el 14B responde con un percentil 95 de 2,1 s. Sin el límite de contexto, el 4B ocupaba 43 GB de memoria. |
| Noviembre de 2026 | Whisper *small* para las órdenes de voz. | Mismos aciertos que *large-v3-turbo* en la prueba sintética (64 de 72), con un percentil 95 de 69 ms frente a 172 ms. |
| 17 nov. 2026 (`b9b918c`) | El modelo de lenguaje redacta fuera del bucle por imagen (`VerbalizacionAparte`). | Dentro del bucle, algunas imágenes superaban los 33 ms. |
| 20 nov. 2026 (`c322753`) | Una sola salida de audio abierta y cortes sin tocar PortAudio desde otros hilos. | Con `sd.play` y `sd.stop` aparecían errores de CoreAudio al cortar la voz. |
| 20 nov. 2026 (`f4ed26d`) | La pausa solo se activa con la voz o a mano; se apagan el gesto y la pausa por inactividad. | Pedido del equipo tras probar la aplicación. Se mantiene la pausa al salir del encuadre. |
| 20 nov. 2026 (`3c7d229`) | La entrenadora no habla entre ejercicios; resume al final. | La rutina pasa al siguiente ejercicio sin interrupciones. |
| 20 nov. 2026 (`cbfb1bb`, `082c2e3`) | Variantes de frases redactadas por modelos grandes, revisadas e importadas como frases fijas que rotan. | Más variedad sin depender del modelo en vivo (rol A de ADR-004). |

Las cifras de los modelos de lenguaje y de Whisper provienen de los comentarios de `config.py` y de `RESULTADOS-MAC-INFORME-FINAL.md`; el consumo de memoria sin límite de contexto, de la sección 11.1 del informe final.

## 13. Referencias relacionadas

**Documentos del repositorio**

- `InformeFinal.md`: problema, arquitectura (sección 10), implementación (sección 11), despliegue y operación (sección 12) y resultados.
- `Instalación.md` y `Readme.md`: puesta en marcha y presentación del proyecto.
- `backend/README.md`, `frontend/README.md`, `backend/estela/dominio/feedback/README.md` y `backend/feedback_testing/README.md`: detalle técnico de cada parte.
- `backend/estela/dominio/feedback/skills/ESQUEMA.md`: formato de una *skill*.
- `RESULTADOS-MAC-INFORME-FINAL.md`: métricas y pasos de instalación comprobados en el Mac Studio.
- `diagramas/mac_diagrams_def/`: diagramas de arquitectura, despliegue, interacción y secuencia de esta versión.

**Repositorio de documentación `docs_estela`**

- `decisiones/`: ADR-001 a ADR-007.
- `experimentos/`: EXP-001 a EXP-011, protocolos y consentimiento.
- `investigacion/`: fuentes, análisis y registro de hallazgos.

**Documentación oficial de las tecnologías**

- MediaPipe Pose Landmarker: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker
- Piper: https://github.com/OHF-Voice/piper1-gpl
- whisper.cpp: https://github.com/ggml-org/whisper.cpp
- Ollama: https://github.com/ollama/ollama
- llama.cpp (`llama-server`): https://github.com/ggml-org/llama.cpp
- pywebview: https://pywebview.flowrl.com
- React: https://react.dev
- Vite: https://vite.dev
