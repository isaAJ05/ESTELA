# Instalación y despliegue

Guía para instalar y ejecutar ESTELA desde el código fuente. El código está en dos ramas:

| Rama | Versión | Para qué equipo | Qué incluye |
|---|---|---|---|
| `main` | **Completa** (la que describe el Informe Final) | Mac con Apple Silicon, probada en un Mac Studio M2 Ultra | Todo lo de `test`, más pose *heavy* en GPU, frases redactadas por un modelo de lenguaje local (Ollama), entrenadora con resumen hablado y órdenes de voz (Whisper) |
| `test` | **Básica**, multiplataforma | Cualquier computador con Windows, Linux o macOS, incluso uno modesto (p. ej. un portátil con Intel i5 de 10.ª generación y 8 GB de RAM) | Pose *lite* en CPU, retroalimentación con plantillas y voz Piper. No usa modelo de lenguaje ni micrófono |

La versión completa también arranca en Windows o Linux: si no está en un Mac con Apple Silicon, se comporta como la básica (sección 3.1.5).

## 1. Descripción general de la solución

### 1.1 Lenguajes y tecnologías utilizadas

| Componente | Tecnología | Rama |
|---|---|---|
| Lenguaje | Python ≥ 3.10 (validado con 3.13 en Windows y 3.14 en Linux) | ambas |
| Estimación de pose | MediaPipe Pose Landmarker (Tasks API, `mediapipe` ≥ 1.0.1, < 2) | ambas |
| Captura de video | OpenCV; Pillow para el texto con tildes | ambas |
| Comparación con la referencia | DTW incremental (numpy) | ambas |
| Interfaz de escritorio | React + TypeScript (Vite) dentro de una ventana pywebview: WebView2 en Windows, WKWebView en macOS, WebKitGTK o Qt en Linux | ambas |
| Retroalimentación | Motor de decisión determinista y plantillas en español (solo biblioteca estándar) | ambas |
| Voz de salida | Piper (`piper-tts`), con respaldo en la voz del sistema o solo texto | ambas |
| Modelo de lenguaje local | Ollama con `qwen3:4b-instruct-2507-q4_K_M` (redacta las correcciones) y `qwen3:14b` (entrenadora) | `main` |
| Órdenes de voz | whisper.cpp mediante `pywhispercpp` (modelo `small`), micrófono con `sounddevice` | `main` |

### 1.2 Componentes de la solución

```
Cámara (hilo) → último frame → Pose Landmarker → geometría → conteo de repeticiones
  → DTW contra la referencia → motor de decisión determinista → verbalizador → cola de voz → Piper
                                                                  │                        └→ interfaz (pywebview)
                                     (main) LLM local por Ollama, con respaldo en plantillas
(main) Micrófono → whisper.cpp → órdenes de voz («Estela, pausa») → sesión
```

- `backend/` contiene todo el Python, organizado en tres capas: `estela/dominio/` (feedback y conteo, sin dependencias externas), `estela/aplicacion/` (sesión, DTW, pausas, métricas) y `estela/adaptadores/` (cámara, pose, voz, LLM, ventana). Detalle en `backend/README.md`.
- Los ejercicios se definen en `backend/estela/dominio/feedback/skills/*.json` (jumping jacks, abducción de cadera, plancha y zancada atrás) y las rutinas en `backend/rutinas/*.json`.
- `frontend/` contiene las pantallas de la interfaz. La versión compilada (`frontend/dist/`) está en el repositorio, así que no hace falta compilarla para ejecutar la aplicación.

El motor determinista siempre decide qué error hubo y si se dice algo. El modelo de lenguaje solo redacta la frase y, si falla o tarda más de 400 ms, suena la plantilla.

## 2. Requisitos previos

### 2.1 Software requerido

**Ambas versiones:**

- Git.
- Python 3.10 o superior, con `venv`.
- Una cámara web. No hace falta para las pruebas con video.
- Salida de audio. En Linux, `sounddevice` necesita PortAudio; si falta, se usa `pw-play`, `paplay` o `aplay`. En macOS se usa `afplay`.
- El componente de ventanas web del sistema: WebView2 en Windows (viene con Windows 10/11 y Edge), nada adicional en macOS, WebKitGTK (`webkit2gtk-4.1`) y PyGObject, o Qt, en Linux. Si no está disponible, se puede usar `--interfaz opencv`.
- Conexión a internet **solo** para instalar dependencias y descargar modelos. Las sesiones funcionan sin red.
- Node.js ≥ 20, **solo** para modificar la interfaz.

**Además, para la versión completa (`main`):**

- Mac con Apple Silicon (M1 o posterior).
- [Ollama](https://ollama.com/download) instalado.
- Memoria: la aplicación con los dos modelos ocupa unos 14,4 GB sin contar macOS (modelo 14B ≈ 9,0 GB, modelo 4B ≈ 2,9 GB, aplicación ≈ 1,8 GB, medido en el Mac Studio). Se estima un mínimo de 24 GB de memoria unificada; con 16 GB queda justo. Sin la entrenadora son unos 4,7 GB. Estos mínimos son estimaciones, no se midieron en equipos con poca memoria.
- Micrófono, para las órdenes de voz. Sin micrófono la sesión sigue, solo que sin órdenes de voz.

### 2.2 Variables de entorno

No se necesitan. Las rutas de los modelos, rutinas, historial e interfaz se calculan respecto a la carpeta `backend/` (`backend/estela/config.py`). Ollama se busca en su dirección local por defecto (`http://127.0.0.1:11434`); otra dirección se indica con `--llm-url` y `--entrenadora-url`.

## 3. Instalación para ambiente de desarrollo

### 3.1 Desarrollo sin contenedores

#### 3.1.1 Clonar el repositorio

Elegir la rama según el equipo (ver la tabla del inicio):

```bash
# Versión completa (Mac con Apple Silicon)
git clone https://github.com/isaAJ05/ESTELA.git          # main, la rama por defecto
# Versión básica (cualquier equipo)
git clone -b test https://github.com/isaAJ05/ESTELA.git

cd ESTELA
```

Si ya se clonó el repositorio, se cambia de rama con `git checkout main` o `git checkout test`.

#### 3.1.2 Instalar dependencias

Todo lo de Python se instala y ejecuta desde `backend/`.

macOS y Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[voz,interfaz,dev]"
```

Windows (PowerShell):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[voz,interfaz,dev]"
```

Si PowerShell no permite activar el entorno, se habilita una vez con `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

En la versión completa, se añade el extra de órdenes de voz:

```bash
pip install -e ".[voz,voz-entrada,interfaz,dev]"
```

| Extra | Qué instala | Rama |
|---|---|---|
| `voz` | Piper y sounddevice (voz de salida) | ambas |
| `interfaz` | pywebview (ventana de escritorio) | ambas |
| `dev` | pytest | ambas |
| `voz-entrada` | pywhispercpp y sounddevice (órdenes de voz) | `main` |

#### 3.1.3 Configurar variables de entorno

No aplica (ver 2.2).

#### 3.1.4 Ejecutar servicios requeridos

**Ambas versiones.** Descargar los modelos una vez, con el entorno activado y desde `backend/`:

```bash
python scripts/descargar_modelos.py
```

Descarga los modelos de pose *lite* y *full* y la voz Piper `es_MX-claude-high` en `backend/modelos/`, que git ignora. En un Mac con Apple Silicon, el script de `main` también descarga la pose *heavy* y el modelo de Whisper para las órdenes de voz. En otro equipo se pueden pedir con `--heavy` y `--voz-entrada`.

**Solo versión completa.** Instalar Ollama, comprobar que está corriendo (la aplicación de Ollama lo deja activo en segundo plano; si no, `ollama serve`) y descargar los dos modelos de lenguaje:

```bash
ollama pull qwen3:4b-instruct-2507-q4_K_M     # redacta las correcciones
ollama pull qwen3:14b                         # entrenadora: resumen final y «¿cómo voy?»
ollama list                                   # deben aparecer los dos
```

No hay otros servicios: no hay base de datos ni servidor web. La interfaz y Ollama se comunican con Python dentro del mismo equipo.

#### 3.1.5 Iniciar la aplicación

Con el entorno activado y desde `backend/`:

```bash
python -m estela
```

Se abre la ventana de escritorio en la pantalla de inicio. La aplicación pregunta **¿Quién entrena hoy?**: se elige un perfil, se crea uno o se entrena sin perfil. Luego se arma o elige la rutina y se pulsa **Comenzar sesión**. Al terminar se muestra el resumen, que también se imprime en la consola.

Qué se enciende por defecto depende del equipo (`estela.config.defectos`):

| Opción | Mac con Apple Silicon (`main`) | Otros equipos, o rama `test` |
|---|---|---|
| Modelo de pose | *heavy* en GPU (Metal) | *lite* en CPU |
| Correcciones | redactadas por el LLM, con respaldo en plantillas | plantillas |
| Entrenadora | con LLM | apagada |
| Órdenes de voz | encendidas, modo «llamada» («Estela, …») | apagadas |

Si en el Mac falta algo (GPU, Ollama, un modelo o el micrófono), la aplicación lo avisa en la consola y sigue con la opción básica de esa parte.

Opciones útiles:

```bash
python -m estela --ejercicio zancada_atras_izq --repeticiones 6   # un solo ejercicio
python -m estela --ejercicio plancha --repeticiones 30            # en la plancha son segundos
python -m estela --modelo full                                    # otra variante de pose (lite, full, heavy)
python -m estela --voz texto                                      # sin audio, frases en pantalla
python -m estela --interfaz opencv                                # ventana simple de OpenCV
python -m estela --sin-historial                                  # sin perfiles ni «Mi progreso»
python -m estela --sin-dtw                                        # sin comparación con la referencia
python -m estela --video ruta.mp4 --voz texto --sin-ventana --guardar-metricas   # prueba con video
python -m estela --help                                           # todas las opciones
```

Solo en `main`:

```bash
python -m estela --verbalizador plantillas --entrenadora no   # apaga el LLM y la entrenadora
python -m estela --voz-entrada no                             # apaga las órdenes de voz
python -m estela --voz-entrada-modo pausa                     # solo escucha en pausa y entre ejercicios
python -m estela --delegado cpu                               # pose en CPU en lugar de GPU
```

Teclas durante la sesión: `Espacio` pausa o reanuda · `N` / `P` ejercicio siguiente o anterior · `R` reinicia el ejercicio · `A` muestra u oculta los ángulos · `V` silencia o activa la voz · `Esc` pide confirmación para terminar · `D` muestra FPS y latencia por etapa. En la ventana de OpenCV: `q` sale, `n` pasa al siguiente ejercicio y `r` lo reinicia.

En la versión completa, las mismas acciones se piden con la voz: «Estela, pausa», «Estela, seguir», «Estela, siguiente», «Estela, terminar», «Estela, ¿cómo voy?». En los ajustes, la sección **Micrófono** permite elegir la entrada, ver su nivel y probar qué entendería el sistema.

**Datos que guarda la aplicación.** Con un perfil, cada sesión con cámara se guarda en `backend/historial/` (fecha, objetivo, lo completado, duración, pausas e indicaciones dichas). No se guardan imágenes, puntos del cuerpo ni audio. Sin perfil, con `--video` o con `--sin-historial` no se guarda nada. El historial se borra desde **Mi progreso** y el perfil desde **Mi perfil**. Las métricas de `--guardar-metricas` van a `backend/sesiones/`. Ambas carpetas están ignoradas por git.

#### 3.1.6 Modificar la interfaz

```bash
cd frontend
npm install
npm run dev        # en el navegador, con un backend simulado y sin cámara
npm run build      # recompila frontend/dist/; subirlo junto con los cambios de src/
```

### 3.2 Desarrollo con contenedores

No aplica. Se evaluó dockerizar ESTELA y se descartó, con el visto bueno de los tutores: la aplicación necesita acceso directo a la cámara, el micrófono, la salida de audio, la ventana gráfica y, en el Mac, la GPU (Metal). En Windows y macOS un contenedor no tiene acceso directo a esos dispositivos, y en Linux exigiría pasar cada dispositivo y el servidor gráfico al contenedor. Para facilitar la instalación, los tutores recomendaron empaquetar la aplicación como ejecutable (sección 4).

#### 3.2.1 Construcción de contenedores

No aplica.

#### 3.2.2 Ejecución del entorno

No aplica.

#### 3.2.3 Servicios disponibles

No aplica.

#### 3.2.4 Apagado del entorno

No aplica.

## 4. Despliegue (en caso de ser aplicable)

### 4.1 Arquitectura de despliegue

ESTELA es una aplicación de escritorio de ejecución local. No usa servidores ni nube: todo corre en un único computador, al que se conectan la cámara, el micrófono y los parlantes. La interfaz (pywebview) y, en el Mac, Ollama se comunican con el proceso de Python dentro del mismo equipo (`127.0.0.1`). Durante la sesión ningún dato sale del equipo. Ver el diagrama de despliegue en `diagramas/`.

Hoy la forma de desplegar es la instalación desde el código (sección 3.1).

### 4.2 Proceso de actualización

Desde la carpeta del repositorio:

```bash
git pull
cd backend
source .venv/bin/activate              # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[voz,interfaz,dev]"   # en main, añadir voz-entrada
python scripts/descargar_modelos.py    # solo baja lo que falte
```

Los perfiles y el historial (`backend/historial/`) no se tocan al actualizar.

### 4.3 Despliegue sin contenedores

> **Estado: pendiente.** El ejecutable aún no existe; ninguna rama tiene configuración de PyInstaller. Esta sección describe la forma de despliegue propuesta y lo que hay que resolver para hacerla. Los comandos no se han probado.

La propuesta, siguiendo la recomendación de los tutores, es empaquetar ESTELA con **PyInstaller**: un `.app` para macOS (versión completa) y un `.exe` para Windows (versión básica). PyInstaller no compila de forma cruzada, así que cada ejecutable se genera en su propio sistema operativo.

#### 4.3.1 Preparación del servidor

No hay servidor. Se prepara el equipo donde se genera el ejecutable: el mismo entorno de la sección 3.1, con los modelos ya descargados, más `pip install pyinstaller`.

#### 4.3.2 Instalación de dependencias

Qué iría dentro del ejecutable y qué no:

| Incluido en el ejecutable | Instalación aparte |
|---|---|
| Python y las dependencias del backend | Ollama y sus dos modelos (versión completa, ≈ 12 GB): no se pueden empaquetar con PyInstaller |
| Modelos de pose y voz Piper de `backend/modelos/` | WebView2 en Windows, si el equipo no lo tiene |
| Skills, referencias, rutinas y `frontend/dist/` | |
| Modelo de Whisper (versión completa) | |

#### 4.3.3 Configuración de la aplicación

Ajustes que el empaquetado necesita y que hoy no están hechos:

1. **Rutas.** `config.py` calcula todo respecto a `backend/` (`RAIZ = Path(__file__).parent.parent`) y la interfaz en `../frontend/dist`. Dentro del ejecutable esas rutas cambian. Hay que añadir los datos con `--add-data` (o en el `.spec`) y resolver las rutas de lectura con `sys._MEIPASS` cuando la aplicación está congelada.
2. **Datos del usuario.** El historial y las métricas se escriben dentro de `backend/`. Dentro de un `.app` o en `Program Files` esa carpeta puede no tener permisos de escritura y se borraría al reemplazar el ejecutable. Hay que guardarlos en la carpeta de datos del usuario (`~/Library/Application Support/ESTELA` en macOS, `%APPDATA%\ESTELA` en Windows).
3. **Dependencias con archivos propios.** MediaPipe, Piper (con los datos de espeak-ng), pywebview y pywhispercpp traen bibliotecas y datos que PyInstaller no siempre detecta. Hay que incluirlos con `--collect-all` o *hooks*.
4. **Permisos en macOS.** El `.app` necesita `NSCameraUsageDescription` y `NSMicrophoneUsageDescription` en su `Info.plist`, o macOS bloquea la cámara y el micrófono. Sin firma de desarrollador, la primera vez se abre con clic derecho → Abrir.

#### 4.3.4 Ejecución de la aplicación

Comando de partida, para iterar sobre él desde `backend/` (sin probar):

```bash
pyinstaller --name ESTELA --windowed \
  --collect-all mediapipe --collect-all piper --collect-all webview \
  --add-data "modelos:modelos" --add-data "rutinas:rutinas" \
  --add-data "../frontend/dist:frontend/dist" \
  estela/__main__.py
```

En Windows, el separador de `--add-data` es `;` en lugar de `:`. El resultado queda en `dist/ESTELA/` (Windows) o `dist/ESTELA.app` (macOS). Para el usuario final, la instalación sería copiar esa carpeta o el `.app` y abrirlo; en la versión completa, además, instalar Ollama y ejecutar los dos `ollama pull` de la sección 3.1.4.

#### 4.3.5 Actualización de versiones

Con el ejecutable, actualizar sería generar uno nuevo y reemplazar el anterior. Por eso los perfiles y el historial deben vivir fuera del ejecutable (punto 2 de 4.3.3).

### 4.4 Despliegue con contenedores

No aplica (ver 3.2).

#### 4.4.1 Construcción de imágenes

No aplica.

#### 4.4.2 Ejecución en servidor

No aplica.

#### 4.4.3 Variables de entorno y secretos

No aplica. ESTELA no usa claves ni servicios externos.

#### 4.4.4 Persistencia y redes

No aplica.

#### 4.4.5 Actualización del despliegue

No aplica.

## 5. Verificación de funcionamiento

1. **Pruebas automáticas** (no necesitan cámara ni modelos), desde `backend/` con el entorno activado:

   ```bash
   pytest                      # pruebas del backend
   pytest -m "not video"       # omite la prueba que necesita el modelo de pose
   ```

   En `main`, cuatro pruebas se omiten fuera del Mac. Las mediciones lentas del Informe 2 se ejecutan aparte con `pytest -m metricas -s`.

   Interfaz, desde `frontend/` (requiere Node.js): `npm run typecheck` y `npm test`.

2. **Prueba reproducible sin cámara**, con un video:

   ```bash
   python -m estela --ejercicio jumping_jacks --video ruta.mp4 --voz texto --sin-ventana
   ```

   El resumen final muestra las repeticiones completas e incompletas, las correcciones emitidas, las pausas y la latencia p50/p95 por etapa.

3. **Prueba con cámara.** `python -m estela`, pulsar **Comenzar sesión** y comprobar que la figura sigue el cuerpo, que el contador avanza y que se oyen las indicaciones. Con `D` se ven los FPS y la latencia.

4. **Versión completa.** Al arrancar, la consola no debe mostrar avisos de que falta Ollama, un modelo o la GPU. Decir «Estela, ¿cómo voy?» durante una pausa debe producir una respuesta hablada.

## 6. Solución de problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `No existe el modelo de pose …` | No se descargaron los modelos | `python scripts/descargar_modelos.py` |
| `Voz 'piper' no disponible` | Falta el extra `voz` o la voz | `pip install -e ".[voz]"` y volver a descargar los modelos |
| `Falta pywebview` | Falta el extra `interfaz` | `pip install -e ".[interfaz]"`, o usar `--interfaz opencv` |
| `No existe frontend/dist/index.html` | La interfaz no está compilada | `cd frontend && npm install && npm run build` |
| La ventana no abre en Linux (`GTK cannot be loaded`) | Falta WebKitGTK/PyGObject o Qt | Instalarlos, o usar `--interfaz opencv` |
| No se puede activar `.venv` en PowerShell | Política de ejecución de scripts | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| «No se detecta la cámara» en la pantalla de inicio | Cámara desconectada u ocupada por otra aplicación | Liberarla y pulsar **Reintentar**; con varias cámaras, probar `--camara 1` |
| macOS no deja usar la cámara o el micrófono | Falta el permiso para la terminal | Ajustes del Sistema → Privacidad y seguridad → Cámara / Micrófono, activar la terminal y reiniciarla |
| El contador no avanza | Orientación distinta a la del ejercicio, o el cuerpo no se ve entero | Seguir el aviso en pantalla («de perfil» / «de frente») y encuadrar el cuerpo completo |
| La sesión dice «Pausa» | 5 s fuera del encuadre, u 8 s sin avanzar en un ejercicio ya empezado | Volver al encuadre o seguir el ejercicio; se reanuda solo y conserva las repeticiones |
| FPS bajos | Modelo de pose demasiado pesado para la CPU | `--modelo lite` |
| `falta el modelo … en Ollama` (main) | No se descargó el modelo | `ollama pull <modelo>` (sección 3.1.4) |
| Las correcciones siempre suenan igual (main) | Ollama no está corriendo o no responde en 400 ms, y se usa la plantilla | Abrir Ollama o ejecutar `ollama serve`; revisar los avisos de la consola |
| Las órdenes de voz no responden (main) | Falta el extra `voz-entrada`, el modelo de Whisper o el permiso del micrófono | `pip install -e ".[voz-entrada]"`, `python scripts/descargar_modelos.py --voz-entrada` y revisar el micrófono en los ajustes |
| `mp.solutions` no existe | Scripts antiguos de `PRUEBAS/` | Usan la API anterior de MediaPipe, que ya no existe en la versión 1.x |

## 7. Mantenimiento y actualización

- **Añadir un ejercicio:** crear `backend/estela/dominio/feedback/skills/<id>.json` con sus reglas y su sección `segmentacion` (ver `skills/ESQUEMA.md`) y añadirlo a una rutina. No se modifica código. La referencia para el DTW se genera desde un video con `python scripts/crear_referencia.py`.
- **Cambiar la rutina:** editar o crear un JSON en `backend/rutinas/` y pasarlo con `--rutina`. El objetivo de cada paso es `"repeticiones"`, salvo en los ejercicios isométricos (plancha), que usan `"duracion_s"`. Desde la interfaz, cada perfil también puede armar su rutina en **Mi rutina**.
- **Cambiar los modelos de lenguaje (main):** con `--llm-modelo` y `--entrenadora-modelo`, o cambiando `LLM_MODELO` y `ENTRENADORA_MODELO` en `backend/estela/config.py`. El nombre es el que muestra `ollama list`.
- **Actualizar dependencias:** las versiones mínimas están en `backend/pyproject.toml`. Después de actualizar, ejecutar `pytest`.

## 8. Referencias relacionadas

- `InformeFinal.md`, sección 12 (despliegue y operación).
- `backend/README.md`: arquitectura del backend y reglas entre capas.
- `frontend/README.md`: contrato entre la interfaz y Python.
- `backend/estela/dominio/feedback/README.md` y `skills/ESQUEMA.md`: formato de los ejercicios.
- `diagramas/`: diagramas de arquitectura y despliegue de cada rama.
- Decisiones de arquitectura (ADR) en el repositorio de documentación del proyecto.
