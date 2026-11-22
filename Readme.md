# ESTELA
VIDEO DEMO: https://youtu.be/MGvIow_HVAU

DIAPOSITIVAS AVANCE: https://canva.link/4qllfjw9c5q3am4

## Resumen ejecutivo

ESTELA es un prototipo de entrenador personal inteligente orientado a personas que inician la práctica de actividad física sin acompañamiento profesional. El proyecto surge ante la dificultad de recibir retroalimentación oportuna sobre la técnica de los ejercicios cuando se utilizan rutinas o videos de manera autónoma. Las alternativas tradicionales permiten seguir los movimientos o contar repeticiones, pero no necesariamente identifican cómo está ejecutando el movimiento el usuario.

Como solución, ESTELA propone una aplicación de escritorio capaz de observar al usuario mediante una cámara, analizar su movimiento y compararlo con una referencia previamente definida. A partir de la estimación de puntos articulares y la comparación temporal del movimiento mediante Dynamic Time Warping (DTW), el sistema identifica desviaciones relevantes y genera retroalimentación visual y hablada en español durante la ejecución. La inferencia se plantea completamente de forma local, evitando la transmisión del video a servicios externos y permitiendo evaluar el desempeño del sistema mediante métricas de precisión y latencia.

El alcance del proyecto se delimita a un prototipo funcional para un solo usuario, validado mediante una rutina de bajo impacto compuesta por cuatro ejercicios. Los ejercicios son: jumping jacks, abducción de cadera de pie, plancha y zancada atrás estática, elegidos porque sus errores principales se pueden observar desde una sola vista de cámara. Los ejercicios se definen mediante archivos externos para facilitar la incorporación de nuevas referencias sin modificar la lógica principal del sistema. El proyecto no busca cubrir de manera general todas las disciplinas deportivas ni sustituir la orientación de profesionales de la actividad física, sino demostrar la viabilidad técnica de integrar percepción del movimiento, comparación, interpretación y retroalimentación en tiempo real dentro de una arquitectura de ejecución local.

El principal valor de ESTELA se encuentra en explorar una alternativa de acompañamiento accesible y orientada a la privacidad, mientras se estudia experimentalmente la precisión y latencia necesarias para proporcionar retroalimentación útil durante la práctica de actividad física.

## Cómo ejecutar

Flujo de la aplicación: cámara → MediaPipe Pose Landmarker → segmentación y conteo de repeticiones → comparación con la referencia (DTW) → motor de feedback determinista → voz local en español.

ESTELA tiene dos versiones:

| Rama | Versión | Para qué equipo |
|---|---|---|
| `main` | **Completa**: además de lo anterior, frases redactadas por un modelo de lenguaje local (Ollama), entrenadora con resumen hablado y órdenes de voz («Estela, pausa») | Mac con Apple Silicon |
| `test` | **Básica**: retroalimentación con plantillas y voz Piper, sin modelo de lenguaje ni micrófono | Cualquier computador con Windows, Linux o macOS |

La instalación detallada de cada versión está en [Instalación.md](./Instalación.md). Los pasos básicos son:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[voz,interfaz,dev]"
python scripts/descargar_modelos.py          # modelos de pose y voz Piper (una vez)

python -m estela                              # rutina de entrenamiento en la interfaz de escritorio
python -m estela --interfaz opencv            # ventana simple de OpenCV (pruebas y mediciones)
python -m estela --ejercicio zancada_atras_izq --repeticiones 8
python -m estela --ejercicio plancha --repeticiones 30   # en la plancha son segundos
pytest                                        # todos los tests del backend (sin cámara)
```

Teclas en la interfaz: `Espacio` pausar o seguir · `n` siguiente ejercicio · `p` ejercicio anterior · `r` reiniciar el ejercicio · `v` activar o silenciar la voz · `a` mostrar ángulos · `Esc` terminar · `d` depuración. En la ventana de OpenCV: `q` salir · `n` · `r`.

Ejercicios: jumping jacks, abducción de cadera de pie, zancada atrás estática y plancha. La abducción y la zancada se hacen en una serie por pierna y tienen un skill por pierna (`abduccion_cadera_izq`/`_der` y `zancada_atras_izq`/`_der`).

| Carpeta | Contenido |
|---|---|
| `backend/` | Todo el Python. Arquitectura por capas en [backend/README.md](./backend/README.md) |
| `backend/estela/dominio/` | Núcleo sin dependencias externas: motor de feedback (`feedback/`: decisión determinista + verbalizador, ADR-001, y skills de los ejercicios) y conteo de repeticiones (`conteo/`) |
| `backend/estela/aplicacion/` | Sesión en tiempo real, rutinas, pausas y los puertos (interfaces) que necesita |
| `backend/estela/adaptadores/` | Cámara, pose (MediaPipe), voz, modelo de lenguaje local (Ollama), órdenes de voz (Whisper) y la conexión con la interfaz (pywebview) |
| `backend/feedback_testing/` | Banco sintético y métricas de EXP-001, EXP-002 |
| `backend/rutinas/` · `backend/tests/` | Rutinas de entrenamiento (JSON) · tests |
| `frontend/` | Interfaz de escritorio (React + TypeScript; `dist/` compilado y versionado). Ver [frontend/README.md](./frontend/README.md) |
| `PRUEBAS/` | Prototipos históricos (incluida la BiLSTM retirada), dataset de vídeos y arnés de EXP-008 |

La arquitectura y las decisiones de diseño se describen en el [informe final](./InformeFinal.md).

## Documentación del repositorio

### Primer informe

- [Primer Informe.md](./PrimerInforme.md): Documento que presenta el planteamiento del problema, los objetivos, la solución propuesta, el estado del arte, la metodología de desarrollo y el plan de trabajo del proyecto.

### Segundo informe

- [Segundo Informe.md](./SegundoInforme.md): Documento que presenta el estado actual del proyecto, incluyendo los avances logrados, las validaciones realizadas y los aspectos pendientes.


### Informe final

| Documento | Descripción |
|---|---|
| [InformeFinal.md](./InformeFinal.md) | Documento principal del proyecto |
| [Instalación.md](./Instalación.md) | Guía de instalación, desarrollo y despliegue |
| [Desarrollo.md](./Desarrollo.md) | Detalles técnicos del desarrollo |

## Estudiantes

| Nombre | GitHub |
|---|---|
| Isabella Arrieta Juliao | [@isaAJ05](https://github.com/isaAJ05) |
| Natalia Carpintero Leal | [@carpinteron](https://github.com/carpinteron) |
| Paula Núñez Zarante | [@pzarante](https://github.com/pzarante) |

## Tutores

- Ph.D. Margarita Gamarra
- Augusto Salazar Silva
