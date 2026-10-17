# Instalación y despliegue

## 1. Descripción general de la solución

### 1.1 Lenguajes y tecnologías utilizadas

| Componente | Tecnología |
|---|---|
| Lenguaje | Python ≥ 3.10 (validado con 3.14) |
| Estimación de pose | MediaPipe Pose Landmarker (Tasks API, `mediapipe` ≥ 1.0.1), world landmarks |
| Captura y visualización | OpenCV, Pillow (texto con tildes) |
| Interfaz de escritorio | React + TypeScript (Vite) en una ventana pywebview: WKWebView en macOS, WebKitGTK o Qt en Linux |
| Feedback | Motor determinista + plantillas en español (`backend/estela/dominio/feedback/`, solo biblioteca estándar) |
| Voz | Piper (`piper-tts`), con caída a espeak-ng / `say` o solo texto |

### 1.2 Componentes de la solución

```
Cámara (hilo) → último frame → Pose Landmarker → geometría (dominio/feedback/motor/geometria.py)
  → segmentador de fases y conteo (dominio/conteo) → motor de decisión + plantillas (dominio/feedback)
  → cola de voz (hilo) → Piper
                     └→ orquestador (adaptadores/interfaz) → ventana de escritorio (frontend/)
```

- `backend/` tiene todo el Python, en tres capas: `estela/dominio/` (feedback y conteo, sin dependencias externas), `estela/aplicacion/` (sesión) y `estela/adaptadores/` (cámara, pose, voz, ventana). Detalle en `backend/README.md`.
- Los ejercicios se definen en `backend/estela/dominio/feedback/skills/*.json` y las rutinas en `backend/rutinas/*.json`.
- `frontend/` contiene las pantallas (inicio, sesión y resumen). Su contrato con Python y cómo se conectan están en `frontend/README.md`.

## 2. Requisitos previos

### 2.1 Software requerido

- Python 3.10 o superior, con `venv`.
- Una cámara web, que no es necesaria para las pruebas con vídeo.
- Audio. En Linux, `sounddevice` necesita PortAudio; si falta, se usa `pw-play`, `paplay` o `aplay`. En macOS se usa `afplay`.
- Opcional: `espeak-ng`, como voz de respaldo en Linux.
- Para la ventana de escritorio en Linux: WebKitGTK (`webkit2gtk-4.1`) y PyGObject, o Qt. En macOS no hace falta nada más.
- Node.js ≥ 20, **solo** para modificar la interfaz. Para ejecutarla no hace falta, porque `frontend/dist/` está versionado.
- Conexión a internet **solo** para la instalación y la descarga de modelos. La sesión funciona sin red.

### 2.2 Variables de entorno

No se necesitan. Las rutas de los modelos se resuelven respecto a `backend/` (`backend/estela/config.py`).

## 3. Instalación para ambiente de desarrollo

### 3.1 Desarrollo sin contenedores

#### 3.1.1 Clonar el repositorio

```bash
git clone <url-del-repositorio> ESTELA && cd ESTELA
```

#### 3.1.2 Instalar dependencias

```bash
cd backend                  # todo lo de Python se ejecuta desde aquí
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[voz,interfaz,dev]"
```

Extras opcionales:
- `voz` instala Piper.
- `interfaz` instala pywebview, para la ventana de escritorio.
- `dev` instala pytest.

#### 3.1.3 Configurar variables de entorno

No aplica.

#### 3.1.4 Ejecutar servicios requeridos

No hay servicios. Solo hay que descargar los modelos una vez:

```bash
python scripts/descargar_modelos.py      # pose lite + full, voz es_MX-claude-high
```

Quedan en `backend/modelos/`, que está ignorado por git.

#### 3.1.5 Iniciar la aplicación

```bash
python -m estela                                   # rutina rutinas/calentamiento_basico.json
python -m estela --ejercicio marcha_rodillas --repeticiones 8
python -m estela --ejercicio plancha --repeticiones 30   # en la plancha son segundos
python -m estela --voz texto                       # sin audio
python -m estela --modelo lite                     # pose más rápida y menos precisa
python -m estela --ejercicio abduccion_cadera --video ruta.mp4 --voz texto --sin-ventana --guardar-metricas
python -m estela --interfaz opencv                 # ventana simple de OpenCV, para pruebas y mediciones
```

Por defecto se abre la interfaz de escritorio, que empieza en la pantalla de inicio. La sesión arranca con **Comenzar sesión**. Al terminar se muestra el resumen, que también se imprime en la consola. Desde el resumen se puede repetir la rutina sin cerrar la ventana.

Teclas en la interfaz: `n` siguiente ejercicio · `r` reiniciar el ejercicio · `Esc` terminar · `d` datos de depuración (FPS y latencia por etapa).
Teclas en la ventana de OpenCV: `q` salir · `n` siguiente ejercicio · `r` reiniciar el ejercicio.

#### 3.1.6 Modificar la interfaz

```bash
cd frontend
npm install
npm run dev        # en el navegador con un backend simulado, sin cámara
npm run build      # recompila frontend/dist/ (súbelo junto con los cambios de src/)
```

### 3.2 Desarrollo con contenedores

No aplica en la v1: la aplicación necesita acceso directo a la cámara y al audio del equipo.

## 4. Despliegue (en caso de ser aplicable)

No aplica: es un prototipo de escritorio de ejecución local.

## 5. Verificación de funcionamiento

```bash
cd backend && pytest                               # todos los tests del backend (sin cámara ni modelos)
cd frontend && npm run typecheck                   # tipos de la interfaz
```

Para una prueba reproducible sin cámara, ejecutar un vídeo del dataset con `--sin-ventana`. El resumen final muestra:
- repeticiones completas e incompletas
- correcciones emitidas
- pausas de la sesión y tiempo en pausa (la duración de cada ejercicio no las incluye)
- latencia p50/p95 por etapa

## 6. Solución de problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `No existe el modelo de pose …` | No se descargaron los modelos | `python scripts/descargar_modelos.py` |
| `Voz 'piper' no disponible` | Falta el extra `voz` o la voz | `pip install -e ".[voz]"` y volver a descargar los modelos |
| El contador no avanza | Orientación distinta de la del ejercicio, o baja visibilidad | Seguir el aviso en pantalla («de perfil» / «de frente») y encuadrar el cuerpo entero |
| La sesión dice «Pausa» | 5 s fuera del encuadre, u 8 s sin avanzar en un ejercicio ya empezado (`backend/estela/aplicacion/pausa.py`) | Volver al encuadre con la orientación pedida, o seguir con el ejercicio: retoma solo y conserva las repeticiones |
| FPS bajos | Pose *full* en una CPU lenta | `--modelo lite` |
| `Falta pywebview` | No está el extra `interfaz` | `pip install -e ".[interfaz]"`, o usar `--interfaz opencv` |
| `No existe frontend/dist/index.html` | La interfaz no está compilada | `cd frontend && npm install && npm run build` |
| La ventana no abre en Linux (`GTK cannot be loaded`) | Falta WebKitGTK/PyGObject o Qt | Instalarlos, o usar `--interfaz opencv` |
| «No se detecta la cámara» en la pantalla de inicio | Cámara desconectada u ocupada por otra aplicación | Liberarla y pulsar **Reintentar** |
| `mp.solutions` no existe | Scripts antiguos de `PRUEBAS/` | Esos scripts usan la API legacy, que ya no existe en mediapipe 1.x |

## 7. Mantenimiento y actualización

- Para **añadir un ejercicio**, crear un nuevo `backend/estela/dominio/feedback/skills/<id>.json` con reglas y una sección `segmentacion` (ver `ESQUEMA.md` en esa carpeta) y añadirlo a una rutina. No se modifica código.
- Para **cambiar la rutina**, editar o crear un JSON en `backend/rutinas/` y pasarlo con `--rutina`. El objetivo de cada paso es `"repeticiones"`, salvo en los ejercicios isométricos (plancha), que usan `"duracion_s"`.

## 8. Referencias relacionadas

- `docs/decisiones/ADR-001`, `ADR-002` y `ADR-003` (espacio de trabajo del proyecto).
- `backend/estela/dominio/feedback/README.md` y `skills/ESQUEMA.md`.
