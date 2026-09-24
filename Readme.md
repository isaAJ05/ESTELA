# ESTELA

## Resumen ejecutivo

ESTELA es un prototipo de entrenador personal inteligente orientado a personas que inician la práctica de actividad física sin acompañamiento profesional. El proyecto surge ante la dificultad de recibir retroalimentación oportuna sobre la técnica de los ejercicios cuando se utilizan rutinas o videos de manera autónoma. Las alternativas tradicionales permiten seguir los movimientos o contar repeticiones, pero no necesariamente identifican cómo está ejecutando el movimiento el usuario.

Como solución, ESTELA propone una aplicación de escritorio capaz de observar al usuario mediante una cámara, analizar su movimiento y compararlo con una referencia previamente definida. A partir de la estimación de puntos articulares y la comparación temporal del movimiento mediante Dynamic Time Warping (DTW), el sistema identifica desviaciones relevantes y genera retroalimentación visual y hablada en español durante la ejecución. La inferencia se plantea completamente de forma local, evitando la transmisión del video a servicios externos y permitiendo evaluar el desempeño del sistema mediante métricas de precisión y latencia.

El alcance del proyecto se delimita a un prototipo funcional para un solo usuario, validado mediante una rutina de calentamiento compuesta por cinco ejercicios de bajo impacto. Los ejercicios se definen mediante archivos externos para facilitar la incorporación de nuevas referencias sin modificar la lógica principal del sistema. El proyecto no busca cubrir de manera general todas las disciplinas deportivas ni sustituir la orientación de profesionales de la actividad física, sino demostrar la viabilidad técnica de integrar percepción del movimiento, comparación, interpretación y retroalimentación en tiempo real dentro de una arquitectura de ejecución local.

El principal valor de ESTELA se encuentra en explorar una alternativa de acompañamiento accesible y orientada a la privacidad, mientras se estudia experimentalmente la precisión y latencia necesarias para proporcionar retroalimentación útil durante la práctica de actividad física.

## Cómo ejecutar la v1

Primera versión del flujo completo: cámara → MediaPipe Pose Landmarker → segmentación y conteo de repeticiones → motor de feedback determinista → voz local en español. La instalación detallada está en [Instalación.md](./Instalación.md).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[voz,reconocimiento,dev]"
python scripts/descargar_modelos.py          # modelos de pose y voz Piper (una vez)

python -m estela                              # rutina de calentamiento con la cámara
python -m estela --ejercicio sentadilla --repeticiones 8
python -m estela --auto                       # + sugerencia de ejercicio (BiLSTM)
pytest                                        # tests de estela/ (sin cámara)
python -m unittest discover -s feedback/tests -t .   # tests del módulo de feedback
```

Teclas: `q` salir · `n` siguiente ejercicio · `r` reiniciar el ejercicio.

| Carpeta | Contenido |
|---|---|
| `estela/` | Aplicación: captura, pose, segmentación/conteo, sesión, voz, interfaz, reconocimiento BiLSTM |
| `feedback/` | Motor de decisión + verbalizador (ADR-001) y skills de los ejercicios |
| `rutinas/` | Rutinas de calentamiento (JSON) |
| `tests/` | Tests de la aplicación |
| `PRUEBAS/` | Prototipos, dataset y BiLSTM entrenada |

Decisiones de esta versión: `docs/decisiones/ADR-003-aplicacion-v1.md` (en el espacio de trabajo del proyecto).

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
