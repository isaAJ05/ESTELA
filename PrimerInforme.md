# ESTELA Informe N.º 1

## Resumen / Abstract

Las personas que inician la práctica de actividad física por su cuenta ejecutan los movimientos sin ninguna verificación externa de su técnica. Cuando no hay un instructor presente, el error **puede repetirse durante la sesión sin recibir una corrección oportuna**. Las alternativas digitales disponibles hoy no cierran ese vacío: el video pregrabado no observa al usuario, las aplicaciones de conteo automático de repeticiones informan cuántas se hicieron pero no cómo, y las soluciones que sí analizan la ejecución dependen de procesamiento en la nube, lo que introduce latencia y obliga a transmitir video del cuerpo del usuario a un tercero.

Este proyecto propone Estela Trainer, un prototipo de aplicación de escritorio que observa al usuario a través de una cámara y le entrega retroalimentación hablada en español, en tiempo real, sobre la ejecución de una rutina de calentamiento de bajo impacto, con toda la inferencia ejecutándose localmente. La arquitectura se organiza alrededor de un ejercicio preprocesado una única vez a partir de un video de referencia local, del cual se extraen la secuencia de ángulos articulares, una representación animada tipo stick figure como guía visual, y los parámetros de evaluación. Durante la sesión, un modelo de estimación de pose extrae los puntos articulares del usuario, la secuencia se alinea temporalmente contra la referencia mediante **un componente de razonamiento que, a partir de las desviaciones detectadas y el contexto de la ejecución, determina la retroalimentación que debe comunicarse.**

El alcance comprende un prototipo funcional para un único usuario, validado sobre una selección de cinco ejercicios físicos de complejidad controlada, definidos en archivos externos al código para facilitar la incorporación de nuevos ejercicios sin modificar la lógica principal del sistema. La selección busca incluir movimientos en los que la técnica pueda caracterizarse mediante puntos y ángulos articulares y en los que una ejecución incorrecta pueda ser identificada y comunicada mediante retroalimentación oportuna. En consecuencia, el prototipo no pretende cubrir de manera general cualquier modalidad de actividad física, sino demostrar la viabilidad del enfoque propuesto sobre un conjunto delimitado de ejercicios. La medición del propio sistema es una actividad central del proyecto: la precisión de la comparación de movimiento y la latencia por etapa se tratan como criterios de aceptación, no como subproducto. El desarrollo sigue un enfoque de prototipado iterativo, con fases de construcción para la detección de puntos articulares, la comparación de movimiento, la interpretación y el razonamiento, y la generación de retroalimentación, cada una cerrada con medición instrumentada en ambiente controlado, precedidas por una fase de preparación del entorno y seguidas por una de validación consolidada y documentación.

## 1. Introducción

La práctica regular de actividad física constituye un componente importante para el bienestar y la salud de la población; sin embargo, una proporción significativa de los adultos no alcanza los niveles recomendados de actividad física. La Organización Mundial de la Salud estima que el 31 % de la población adulta mundial, cerca de 1 800 millones de personas, no alcanza los niveles recomendados de actividad física, una cifra que podría llegar al 35 % en 2030 si la tendencia continúa. Esto representaría un costo estimado para los sistemas de salud de aproximadamente US$ 300 000 millones entre 2020 y 2030 [1]. En Colombia, la serie anual de estimaciones del Observatorio Mundial de la Salud también muestra un aumento en la prevalencia de actividad física insuficiente entre los adultos, pasando del 24,8 % en 2000 al 34,5 % en 2022. Frente a este panorama, las tecnologías aplicadas a la actividad física han evolucionado de ofrecer únicamente contenidos y rutinas de ejercicio a desempeñar un papel más activo durante su ejecución, incorporando mecanismos de seguimiento y retroalimentación que permiten acompañar al usuario durante la práctica y responder a su desempeño. Esta evolución ha sido favorecida por el desarrollo de técnicas de percepción y procesamiento capaces de analizar el movimiento humano en tiempo real. En particular, la estimación de pose humana a partir de una sola cámara ha mostrado resultados que permiten su ejecución en tiempo real en equipos de propósito general, incluyendo escenarios de procesamiento local [12][14].  De manera similar, los avances en modelos de inteligencia artificial para el análisis e interpretación de información visual y numérica, así como en síntesis de voz, permiten considerar arquitecturas capaces de generar retroalimentación en lenguaje natural y comunicarla al usuario sin depender necesariamente de servicios externos [18] .Estas capacidades permiten plantear una arquitectura que integre percepción del movimiento, análisis de la ejecución y generación de retroalimentación dentro del mismo equipo, sin depender del envío de imágenes o datos a servicios remotos, abre una oportunidad para el desarrollo de sistemas capaces de proporcionar acompañamiento y retroalimentación durante la actividad física.

Sin embargo, las soluciones disponibles presentan diferentes niveles de acompañamiento durante la ejecución y pueden agruparse, de manera general, en tres familias: los videos y bibliotecas de rutinas, que muestran los movimientos pero no verifican la ejecución del usuario; las aplicaciones de conteo automático de repeticiones, cuyo objetivo principal es determinar la cantidad de movimientos realizados y que pueden incorporar mecanismos de análisis basados en estimación de pose y umbrales articulares [16]; y los sistemas comerciales de análisis de movimiento, que incorporan seguimiento y retroalimentación, pero suelen depender de hardware especializado o modelos de suscripción, como Peloton Guide [20] y Tempo [23]. Aunque estas alternativas facilitan el acceso a rutinas y permiten cierto nivel de seguimiento, persiste una limitación en la disponibilidad de retroalimentación técnica accesible y oportuna sobre la ejecución del usuario durante la práctica.

Esta situación plantea un desafío técnico específico: desarrollar un sistema capaz de observar el movimiento de una persona, compararlo con una referencia del ejercicio, identificar desviaciones relevantes y proporcionar retroalimentación durante la ejecución. Para que esta retroalimentación resulte útil, el procesamiento debe realizarse con una latencia suficientemente baja para acompañar la interacción sin interrumpirla. Además, la literatura sobre aprendizaje motor señala que la retroalimentación aumentada puede contribuir al aprendizaje del movimiento y que sus efectos dependen, entre otros factores, de la forma en que se presenta [3]. En este contexto, el procesamiento local constituye una alternativa de interés, ya que permite realizar el análisis directamente en el dispositivo y evita depender del envío de los fotogramas capturados a servicios externos. Esto permite plantear una solución que integre estimación de pose, comparación del movimiento y generación de retroalimentación dentro de una misma arquitectura, cuya precisión y latencia puedan ser evaluadas de forma independiente.

Este informe presenta **Estela Trainer**, un prototipo de sistema inteligente para proporcionar retroalimentación sobre la ejecución de ejercicios físicos. El sistema captura el movimiento del usuario mediante una cámara, estima sus puntos articulares y compara la ejecución con una referencia previamente definida para identificar posibles desviaciones. A partir de esta información, el sistema determina la retroalimentación correspondiente y la presenta de forma visual y mediante síntesis de voz en español. La inferencia se ejecuta localmente (sin depender de servicios remotos) durante la sesión. Su evaluación se centra en dos aspectos principales: la precisión de la comparación entre el movimiento del usuario y la referencia, y la latencia asociada a las diferentes etapas del procesamiento. De esta manera, el proyecto busca demostrar la viabilidad técnica de integrar percepción del movimiento, comparación temporal e interpretación de la ejecución en un prototipo funcional capaz de proporcionar retroalimentación durante la práctica de un conjunto delimitado de ejercicios.

## 2. Planteamiento del problema

### 2.1 Descripción del problema

En la práctica autónoma de actividad física, las personas sin experiencia previa en ejercicio estructurado pueden no disponer de mecanismos suficientes para evaluar su propia ejecución durante el movimiento. En este escenario, quien sigue un video de rutina en casa o repite de memoria una secuencia que observó previamente no dispone necesariamente de un mecanismo objetivo que le permita determinar si su postura, alineación o duración del movimiento corresponden a la referencia propuesta. Las desviaciones respecto a la ejecución de referencia pueden pasar inadvertidas durante la práctica, lo que dificulta que el usuario identifique oportunamente los aspectos de su movimiento que requieren mejora.

Esta situación puede explicarse por varios factores. La práctica autónoma no cuenta de forma permanente con un observador que pueda analizar la ejecución mientras ocurre y contrastarla con un patrón de referencia. A esto se suma que gran parte del contenido digital utilizado para apoyar la práctica, como videos, imágenes o descripciones textuales, funciona de manera unidireccional: proporciona información al usuario, pero no recibe información sobre su ejecución, de modo que ofrece una referencia para realizar el movimiento sin permitir determinar cómo está siendo ejecutado. Finalmente, incluso cuando existe algún mecanismo de revisión, como la grabación de una sesión para analizarla posteriormente, la retroalimentación puede producirse después de que el movimiento ya ha sido realizado, y tanto la forma como el momento de entrega de la retroalimentación aumentada pueden influir en su efectividad [3].

Esta situación afecta principalmente a las personas que se inician en la actividad física sin acompañamiento profesional, dentro del rango de edad definido para este proyecto (aproximadamente entre 18 y 40 años). Dado que la prevalencia de actividad física insuficiente en Colombia alcanzó el 34,5 % en 2022 [2], esta población constituye el grupo de interés del prototipo y delimita el contexto de validación del sistema.

La ausencia de observación y retroalimentación durante la ejecución puede generar varias dificultades. El usuario dispone de menos oportunidades para identificar y ajustar su ejecución en el momento en que realiza el movimiento, pese a que la retroalimentación aumentada puede favorecer el aprendizaje y ajuste de habilidades motoras [3]. Además, las desviaciones respecto al movimiento de referencia pueden pasar inadvertidas, dificultando que la persona determine qué aspectos de su técnica debería mejorar. 

### 2.2 Justificación

El problema descrito resulta relevante porque la práctica autónoma de actividad física no siempre ofrece al usuario mecanismos para verificar y ajustar su ejecución durante el movimiento. Atender esta situación representa un reto que involucra aspectos técnicos, académicos, sociales y prácticos. Desde esta perspectiva, el desarrollo de ESTELA se justifica no únicamente por la posibilidad de construir una aplicación de entrenamiento, sino por la oportunidad de estudiar la integración de diferentes tecnologías de inteligencia artificial en una arquitectura local capaz de observar, analizar y comunicar información sobre el movimiento en tiempo real.

Resolver esta problemática no consiste únicamente en seleccionar una herramienta existente. Los estimadores de pose disponibles, como MediaPipe Pose Landmarker y RTMPose, proporcionan información sobre la posición de los puntos articulares por fotograma, pero por sí mismos no resuelven tareas posteriores como la evaluación de la calidad de la ejecución, la comparación temporal de movimientos o la generación de retroalimentación al usuario [13], [14]. Por tanto, es necesario diseñar componentes capaces de transformar estas observaciones geométricas en una interpretación contextualizada y técnicamente sustentada, y posteriormente en una retroalimentación comprensible para el usuario.

La literatura evidencia que distintos componentes del problema ya han sido abordados de forma independiente o parcial, incluyendo comparación temporal del movimiento, análisis de postura y generación de retroalimentación. Sin embargo, estos trabajos responden a configuraciones y objetivos específicos. En este contexto, el proyecto propone estudiar la integración de estos componentes en una arquitectura de ejecución local, evaluando de manera conjunta la precisión de la comparación, la latencia del procesamiento y la viabilidad de generar retroalimentación durante la ejecución.

Las soluciones destinadas a proporcionar retroalimentación sobre el movimiento requieren procesar información visual del usuario y, potencialmente, datos derivados de su postura corporal. En Colombia, la Ley 1581 de 2012 clasifica los datos biométricos como datos sensibles, sujetos a un régimen especial de protección [5]. Por esta razón, el proyecto considera como condición de diseño que la inferencia se ejecutará localmente y las capturas de video serán procesadas durante la sesión sin requerir su transmisión a servicios externos ni su almacenamiento como parte del funcionamiento habitual del prototipo. Las métricas derivadas de la ejecución podrán conservarse para fines de evaluación y seguimiento de la sesión. Además de reducir la exposición de esta información, esta decisión permite estudiar el comportamiento de la arquitectura sin introducir dependencia de servicios remotos. La forma concreta en que se implementará el procesamiento local y su impacto sobre el desempeño serán determinados durante el desarrollo y la evaluación experimental.

El proyecto dispone de infraestructura suficiente para desarrollar y evaluar alternativas de procesamiento local. El equipo principal disponible es un Mac Studio con M2 Ultra y 128 GB de memoria unificada, que constituye el equipo de inferencia previsto para el desarrollo y las pruebas [19]. Esta infraestructura permite concentrar el esfuerzo del proyecto en la integración, experimentación y medición de la arquitectura propuesta.

### 2.3 Restricciones y supuestos iniciales

#### Restricciones de tiempo y equipo humano

| Restricción | Descripción |
| --- | --- |
| Duración | Un semestre académico (periodo 202630). El cronograma de la Sección 7.4 se ajusta a esa ventana. |
| Equipo | Tres estudiantes, con dedicación parcial compartida con el resto de la carga académica. |
| Consecuencia | Se prioriza **profundidad sobre cobertura**: pocos ejercicios funcionando bien y medidos, en lugar de muchos ejercicios sin evidencia de desempeño. |

#### Restricciones de infraestructura

| Restricción | Descripción |
| --- | --- |
| Hardware de inferencia | Un único equipo (Mac Studio M2 Ultra, 128 GB) accesible por SSH. No hay hardware redundante ni de respaldo. |
| Ejecución | La inferencia del sistema se realizará completamente de manera local. No se contempla el uso de servicios de nube para la ejecución de los modelos. |
| Cámara | Un dispositivo de captura conectado directamente al equipo de inferencia. La evaluación de una segunda cámara queda planteada como línea de exploración, no como requisito. |
| Presupuesto de latencia | Se establece inicialmente un objetivo de latencia para el ciclo de percepción y generación de retroalimentación, cuyo valor será revisado a partir de las mediciones experimentales. |
| Almacenamiento | El video capturado durante la sesión no se almacenará de forma permanente. Se conservarán únicamente las métricas o datos derivados definidos para la evaluación y seguimiento del ejercicio. |

#### Restricciones del entorno de uso

Derivadas del análisis de limitaciones del equipo:

- **Un solo usuario a la vez.** El prototipo estará diseñado para la interacción con una sola persona frente a la cámara. Esta restricción permite delimitar el problema de detección, seguimiento y generación de retroalimentación y evita introducir, en esta primera versión, la complejidad asociada al análisis simultáneo de varios usuarios.
- **Espacio suficiente para cubrir el cuerpo completo en el encuadre.** La documentación *legacy* de MediaPipe Pose indica que los conjuntos de validación internos (Yoga, Dance, HIIT) utilizaron imágenes con una sola persona ubicada entre 2 y 4 metros de la cámara [25]. Es una condición de validación interna del modelo, **no** un requisito de uso publicado, y así se trata en este informe.
- **No se exige iluminación de estudio ni fondo controlado.** No existe documentación oficial que especifique requisitos de iluminación o fondo para los modelos considerados; las condiciones reales de operación se determinarán empíricamente y se documentarán como parte de la validación.
- **Nivel de ruido compatible con escuchar la retroalimentación hablada.** El canal de salida principal es la voz.
- Ejercicios seleccionados por su viabilidad de análisis mediante estimación de pose y comparación con una referencia definida.

#### Supuestos

1. Los videos de referencia se entregan como archivos locales y son técnicamente aptos para extraer los puntos articulares. **La verificación exhaustiva de su calidad técnica no forma parte del alcance.**
2. Los componentes de estimación de pose, análisis e interpretación y síntesis de voz seleccionados estarán disponibles bajo condiciones de licencia compatibles con el uso académico previsto y podrán ejecutarse localmente.
3. El equipo dispone de acceso continuo al Mac Studio durante el semestre.
4. Es posible reclutar usuarios de prueba dentro de la población objetivo para las sesiones de validación.
5. La comparación con una referencia constituye una aproximación inicial para identificar desviaciones respecto a criterios de ejecución definidos para los ejercicios incluidos en el prototipo.

#### Restricciones explícitas de responsabilidad

El sistema **no** realiza diagnóstico médico, fisioterapéutico ni rehabilitación clínica, y **no** reemplaza la orientación de un instructor o profesional certificado. El prototipo proporciona retroalimentación sobre la ejecución respecto a los criterios definidos para los ejercicios incluidos. Esta delimitación es una restricción de diseño, no un descargo de responsabilidad añadido al final: condiciona qué mensajes puede emitir el sistema y qué ejercicios entran en el alcance.

# 3. Alcance del proyecto

## Incluye

- Desarrollo de una aplicación de escritorio con ejecución e inferencia completamente locales, dirigida a personas sin experiencia previa en ejercicio estructurado, sin rutina definida, o que estén iniciando en la práctica de actividad física (aproximadamente entre 14 y 40 años).
- Recursos técnicos: hardware disponible (Mac Studio M2 Ultra, 128 GB RAM) para la ejecución local de los modelos, videos de referencia entregados como archivo local para cada estiramiento de la rutina, y librerías/motores de inferencia de código abierto (RTMPose o MediaPipe, dtw-python o FastDTW, Kokoro TTS).
- Definición, por parte del usuario, de metas básicas de la sesión (duración, repeticiones, sets) y selección del ejercicio o rutina a practicar.
- Generación de una interfaz de retroalimentación visual y hablada, junto con un panel de estadísticas de sesión (duración, historial de retroalimentación, recomendaciones generales sobre fallas o aspectos por mejorar).
- Instrumentación y medición del sistema como actividad propia del proyecto, con el fin de sustentar el desempeño del prototipo mediante evidencia cuantitativa.
- Validación del prototipo mediante una rutina de calentamiento compuesta por varios estiramientos de bajo impacto, como caso de uso representativo.
- Prototipo funcional, validado mediante un caso de uso representativo (rutina de calentamiento con múltiples estiramientos).

## No incluye

- Generación automática de rutinas nuevas a partir de instrucciones libres del usuario (prompt).
- Modo de operación diferenciado según el entorno físico (casa, gimnasio, entre otros).
- Soporte para múltiples usuarios de manera simultánea.
- Funcionamiento mediante servicios en la nube.
- Cobertura de disciplinas físicas distintas al calentamiento de bajo impacto.
- Diagnóstico médico, fisioterapéutico o rehabilitación clínica; el sistema no reemplaza la orientación de un instructor o profesional certificado.
- Verificación exhaustiva de la calidad técnica de los videos de referencia entregados al sistema.
- Implementación a escala productiva, despliegue público o soporte operativo posterior al proyecto.

---

# 4. Objetivos

## 4.1 Objetivo general

Diseñar e implementar un prototipo de entrenador personal inteligente que permita a personas sin experiencia previa en ejercicio estructurado practicar una rutina de calentamiento de bajo impacto con retroalimentación hablada y en tiempo real, evaluando la viabilidad de una arquitectura de inferencia local mediante métricas de precisión y latencia durante el desarrollo del proyecto.

## 4.2 Objetivos específicos

- Determinar la desviación del movimiento del usuario respecto a una referencia mediante detección de postura y alineación temporal dinámica (DTW).
- Establecer una representación visual del movimiento de referencia que oriente al usuario para cada ejercicio.
- Generar retroalimentación hablada, en tiempo real y en español, sobre la ejecución del movimiento del usuario.
- Evaluar el desempeño de la arquitectura propuesta mediante métricas de precisión de la comparación de movimiento y de latencia por etapa del sistema.
- Documentar los resultados de la validación del prototipo en una rutina de calentamiento compuesta por varios estiramientos de bajo impacto.

## 5. Solución propuesta

### 5.1 Qué se propone construir

**Estela Trainer** es una aplicación de escritorio que actúa como asistente durante la práctica de una rutina de calentamiento. El usuario se ubica frente a la cámara y comienza a ejecutar el ejercicio seleccionado o identificado por el sistema; este muestra en pantalla una guía del movimiento esperado, observa la ejecución y analiza su correspondencia con la referencia para generar retroalimentación en español durante la práctica. Toda la inferencia se plantea para ejecutarse en el equipo local, evitando la transmisión de los fotogramas a servicios externos.

La respuesta al problema planteado en la Sección 2 se articula en tres decisiones de diseño:

| Decisión | Qué resuelve del problema |
| --- | --- |
| Observación continua por cámara con estimación de pose local | Suple la **ausencia del observador competente** (causa 1) sin depender de un tercero remoto. |
| Retroalimentación hablada emitida durante la ejecución | Elimina la **unidireccionalidad del contenido** (causa 2) y el **retardo entre ejecución y corrección** (causa 3). |
| Presupuesto de latencia como criterio de aceptación, con mensajes de plantilla como respaldo | Busca que la retroalimentación pueda generarse y entregarse mientras la ejecución aún ocurre |

### 5.2 Usuarios y Roles 
| Perfil | Descripción |
| --- | --- |
| **Usuario principal** | Persona entre ~18 y 40 años, sin experiencia previa en ejercicio estructurado ni rutina definida, que practica en un espacio propio, sin instructor presente. Interactúa seleccionando la rutina, definiendo metas básicas de la sesión (duración, repeticiones, sets) y ejecutando el movimiento frente a la cámara. |
| Rol de configuración técnica  | Corresponde al equipo de desarrollo y permite incorporar nuevos ejercicios mediante la preparación de sus recursos de referencia. Este rol no forma parte de la interacción habitual del usuario final. |

### 5.3 El concepto de skill 
Una skill se construye a partir de un video de referencia local y contiene los recursos necesarios para representar y evaluar el ejercicio durante la sesión. Entre estos recursos pueden incluirse la representación del movimiento de referencia, una guía visual tipo stick figure y la configuración específica requerida por el método de evaluación seleccionado.

La representación exacta utilizada para la comparación, por ejemplo, ángulos articulares, coordenadas normalizadas u otra representación derivada de la pose, será determinada durante la experimentación. 

### 5.4 Arquitectura funcional propuesta

La arquitectura presentada corresponde al flujo de referencia planteado al cierre de este informe. Algunas etapas y tecnologías permanecen abiertas y serán evaluadas experimentalmente durante el desarrollo, particularmente el método de identificación del ejercicio, la representación del movimiento y el método de comparación. ****

**Fase de construcción (offline, una sola vez por ejercicio):**

```text
Video de referencia (archivo local)
        │
        ↓
Estimación de pose ──→ Normalización ──→ Secuencia de ángulos de referencia
        │                                      │
        └──────────→ Generación de stick figure ─┤
                                                 ↓
                              Configuración de evaluación
                              (articulaciones, umbrales)
                                                 │
                                                 ↓
                                            SKILL almacenada
```
                                  
**Fase de ejecución (en tiempo real, durante la sesión):**
```text
                      Cámara
                        │
                        ▼
              ┌───────────────────┐
              │  Memoria          │   Una sola escritura del fotograma;
              │  compartida       │   los consumidores leen del mismo lugar
              └───────────────────┘
                 │      │      │
     ┌───────────┘      │      └──────────────┐
     ▼                  ▼                     ▼
Estimación de pose   Modelo multimodal     Pantalla
     │               (keyframes)               │
     ▼                  ▲                      │
Normalización           │                      │
     │                  │                      │
     ▼                  │                      │
Comparación con la      │                 Stick figure de
referencia (DTW) ───────┘                 la skill + estado
     │
     ▼
Desviación resumida por articulación
     │
     ▼
Decisión de retroalimentación
(qué decir, cuándo decirlo, cuándo callar)
     │
     ▼
Síntesis de voz local (español)
     │
     ▼
Voz al usuario
```
### 5.5 Módulos y tecnologías candidatas

| Módulo | Función | Tecnología candidata | Estado de la decisión |
| --- | --- | --- | --- |
| Percepción | Convertir cada fotograma en puntos articulares | RTMPose [14] o MediaPipe Pose Landmarker [12], [13] | **Pendiente.** Requiere prueba comparativa directa en el hardware del proyecto (ver 5.7). |
| Normalización | Hacer la representación independiente del encuadre y de la morfología | Ángulos articulares derivados de coordenadas de mundo 3D | Enfoque definido; parámetros por determinar. |
| Comparación temporal | Alinear la ejecución del usuario con la referencia a velocidades distintas | DTW [15], vía `dtw-python` o FastDTW / alternativas | Candidato principal. Cuenta con precedentes en [7] y [9]; su configuración y desempeño se validarán durante el desarrollo. |
| Interpretación | Traducir la desviación numérica y el contexto visual en una valoración de desempeño | Modelo multimodal pequeño de ejecución local | **Pendiente**, incluida la verificación de su tasa de alucinación (ver 5.7). |
| Decisión de retroalimentación | Determinar qué corregir, cuándo hablar y cuándo callar | Modelo de lenguaje local + mensajes de plantilla como respaldo | Enfoque definido; modelo por confirmar. |
| Síntesis de voz | Emitir la corrección en español | Kokoro TTS (82 M parámetros, licencia Apache 2.0, ejecución local) [18] | Candidato principal; soporte de español por verificar empíricamente. |
| Transporte de fotogramas | Evitar copias del fotograma entre módulos | Memoria compartida (*shared memory interface mapping*) | Enfoque definido. |

### 5.6 Por qué es una respuesta adecuada dentro del alcance

- **Es acotada.** El alcance se limita a una rutina de calentamiento de bajo impacto, un usuario y una selección explícita del ejercicio. Esas tres restricciones eliminan los problemas más difíciles del dominio (segmentación de actividad no supervisada, seguimiento multipersona, movimientos de alta velocidad) sin eliminar el problema central: observar y corregir.
- **Es medible.** Los objetivos específicos 1 y 4 exigen cifras: desviación respecto a la referencia y latencia por etapa. La medición no es un anexo del proyecto, es un entregable.
- **Es extensible.** La separación entre *pipeline* y *skills* permite pasar de dos ejercicios a diez sin rediseñar el sistema, que es exactamente la trayectoria de crecimiento recomendada por los asesores.
- **Es realizable con los recursos disponibles.** El proyecto cuenta con infraestructura de cómputo y modelos de código abierto que permiten experimentar con diferentes alternativas sin que sea necesario adquirir hardware adicional.
- **Reduce la exposición de la información capturada.** Al mantener la inferencia local y evitar la transmisión de los fotogramas a servicios externos, el diseño reduce los riesgos asociados al envío de información corporal a terceros.

### 5.7 Decisiones abiertas al cierre de este informe

Se declaran explícitamente para que el lector distinga lo definido de lo pendiente:

1. **Estimador de pose: RTMPose o MediaPipe.** Ninguna documentación oficial publica cifras de latencia para el hardware y la configuración exactas del proyecto. La decisión requiere una prueba comparativa propia sobre los mismos videos, midiendo FPS y latencia reales, consumo de CPU/RAM en inferencia en vivo, y estabilidad de los puntos articulares en los estiramientos concretos de la rutina.
2. **Modelo multimodal y modelo de lenguaje.** Requieren, antes de integrarse, un *benchmark* propio de imágenes anotadas que cuantifique su tasa de alucinación. No se delegará ninguna decisión de retroalimentación a un modelo cuyo comportamiento no se haya medido.
3. **Número de cámaras.** Se explorará si una sola cámara captura adecuadamente los estiramientos seleccionados o si alguno requiere una segunda vista. El diseño no se cerrará sobre una sola cámara de forma irreversible.
4. **Método de representación y comparación del movimiento.** Se evaluarán diferentes formas de representar la ejecución del usuario y compararla con la referencia. DTW constituye una de las alternativas consideradas, pero la selección final dependerá de su comportamiento en precisión, robustez ante diferentes velocidades de ejecución y costo computacional.
5. **Identificación del ejercicio.** Se evaluará si resulta más conveniente que el usuario seleccione explícitamente el ejercicio o incorporar un mecanismo de clasificación automática. La segunda alternativa podrá requerir un modelo entrenado o ajustado con datos específicos, cuya viabilidad se determinará durante el desarrollo.
## 6. Estado del arte / soluciones relacionadas

Esta revisión se organiza en productos comerciales, soluciones de código abierto y enfoques técnicos documentados en la literatura. Se distingue de forma explícita entre **dato verificado** en fuente primaria y **observación o indicio** pendiente de verificación, y las cifras de desempeño no se comparan entre sí cuando provienen de configuraciones o hardware distintos.

### 6.1 Productos comerciales

**Peloton Guide.** *Las especificaciones de este párrafo provienen de una fuente secundaria [20] y no de documentación oficial del fabricante; se reportan como tales.* Dispositivo anunciado en noviembre de 2021 y lanzado el 5 de abril de 2022 a US$ 295, con una cámara gran angular de 12 megapíxeles capaz de transmitir video 4K a hasta 60 fotogramas por segundo. Se conecta a un televisor por HDMI y estudia los movimientos del usuario para hacer seguimiento del entrenamiento y ofrecer retroalimentación y recomendaciones de clases; al terminar, presenta un desglose de los músculos trabajados [20]. Es el ejemplo más cercano en concepto al presente proyecto: cámara fija, análisis de movimiento y recomendaciones. Sus limitaciones son estructurales: requiere hardware propietario, suscripción, un televisor, y su retroalimentación está ligada al catálogo de clases del proveedor. **Observación (24 de agosto de 2026):** al consultar la URL histórica del producto (`onepeloton.com/guide`), la página servida no describe el Guide sino el catálogo vigente de dispositivos del fabricante —Bike, Bike+, Tread, Tread+ y Row+—, en el que el Guide no figura [24]. No se localizó un anuncio oficial de descontinuación, por lo que se reporta como ausencia observada del catálogo y no como discontinuación confirmada.

**Tempo.** Plataforma de entrenamiento de fuerza que combina hardware doméstico con planes adaptativos, escaneo corporal 3D para seguimiento de composición corporal y entrenamiento personal virtual desde US$ 39 mensuales más el costo del equipo. El sitio oficial no publica detalles sobre la arquitectura del sensor, si el procesamiento ocurre en el dispositivo o en la nube, ni declaraciones de privacidad sobre el manejo del video [23]. Esa opacidad es, en sí misma, un hallazgo relevante: el usuario no puede determinar dónde se procesa la imagen de su cuerpo.

**Kaia Health.** Plataforma de manejo digital de dolor musculoesquelético, con programas desarrollados por fisioterapeutas. Según su propio sitio, cuenta con resultados clínicos en once ensayos y se distribuye a través de más de 2 500 empleadores y aseguradoras, no directamente al consumidor; ambas cifras son declaraciones del proveedor y no se verificaron en fuente independiente. La documentación pública consultada no especifica si el procesamiento de imagen es local o remoto [22]. Su dominio es clínico —rehabilitación y dolor—, explícitamente **fuera** del alcance de este proyecto, pero es relevante como referencia de que el análisis de ejercicio por cámara ya opera en contextos donde la exigencia de calidad es alta.

**Fragilidad de la oferta comercial (observación).** Durante esta revisión, el sitio de uno de los proveedores de análisis de movimiento por cámara consultados (`vay.ai`) devolvió una página de dominio expirado en lugar de contenido del producto (consultado el 24 de agosto de 2026). Se reporta como observación puntual, no como conclusión sobre el estado de la empresa; su valor es ilustrar que la dependencia funcional de un servicio remoto de terceros implica un riesgo de continuidad real para el usuario final.

### 6.2 Soluciones de código abierto

**Estimadores de pose.** Son la base disponible, y su límite es nítido:

- **MediaPipe Pose Landmarker** (basado en BlazePose GHUM [21]) entrega 33 puntos articulares por fotograma en coordenadas normalizadas de imagen y en coordenadas de mundo 3D en metros, con campos de `visibility` y `presence`, y está optimizado para ejecución local sin nube [13]. BlazePose fue diseñado explícitamente para seguimiento corporal en dispositivo [12]. Está diseñado y validado para **una sola persona**; el parámetro `num_poses` existe pero su fiabilidad no está garantizada por la documentación oficial [17].
- **RTMPose** (familia MMPose) reporta 75,8 % AP en COCO y más de 90 FPS en una CPU Intel i7-11700 para la variante **RTMPose-m**, y más de 70 FPS en un Snapdragon 865 para la variante **RTMPose-s** (72,2 % AP) [14]. Son configuraciones y hardware distintos y no se comparan entre sí.

Lo decisivo, para este proyecto, es lo que **ninguno** de los dos hace: no clasifican el ejercicio, no evalúan la calidad del movimiento, no calculan una puntuación, no detectan errores técnicos y no generan lenguaje natural [13], [14]. Entregan la materia prima. Todo el resto es trabajo por construir.

**Conteo de repeticiones.** La solución `AIGym` de Ultralytics ejecuta estimación de pose y cuenta repeticiones midiendo el ángulo formado por tres puntos articulares conforme un miembro se mueve entre dos umbrales configurables (`up_angle`, `down_angle`), con ejemplos para flexiones, dominadas, sentadillas y extensiones de pierna [16]. Es un buen ejemplo del techo de esta familia de soluciones: registra **qué** se hace y cuántas veces, no **qué tan bien** [16]. El licenciamiento de la librería (AGPL-3.0 para uso de código abierto, según la documentación del proyecto) es además una restricción a considerar en cualquier derivación posterior, y conviene verificarlo directamente en el repositorio antes de asumir compatibilidad.

### 6.3 Enfoques técnicos en la literatura

| Trabajo | Enfoque | Resultados reportados | Limitaciones declaradas |
| --- | --- | --- | --- |
| **Pose Trainer** [7] — Chen y Yang, Stanford | Estimación de pose + geometría vectorial + DTW como métrica de distancia entre secuencias de puntos articulares, con clasificador de vecino más cercano; filtrado de mediana para reducir ruido del estimador | F1 por ejercicio: elevación frontal 1,00; curl de bíceps 0,85; encogimiento de hombros 0,85; press de hombros 0,73. Conjunto propio de más de 100 videos de forma correcta e incorrecta | Cuatro ejercicios; requiere PC con GPU; alcance restringido |
| **AIFit** [6] — Fieraru *et al.*, CVPR 2021 | Reconstrucción de pose y movimiento 3D + "entrenador estadístico" con parámetro global ajustable según nivel del aprendiz; retroalimentación en lenguaje natural con anclaje espaciotemporal | Conjunto **Fit3D**: más de 3 millones de imágenes con verdad de referencia de forma y movimiento 3D, más de 37 ejercicios repetidos, con instructores y aprendices | La exactitud de la retroalimentación depende de la precisión del método de reconstrucción |
| **Yoga pose recognition** [9] — Yeh y Yang, 2025 | OpenPose + algoritmos basados en reglas + DTW para trayectorias dinámicas; puntuación por ángulo articular con fórmula ponderada y cinco niveles de retroalimentación | 99,9 % en posturas estáticas y 99,0 % en acciones dinámicas, sobre cinco ejercicios; implementado en una NVIDIA Jetson Nano con webcam | Conjunto de prueba limitado en tamaño y diversidad; el desempeño en acciones dinámicas se ve afectado por variación de fondo y ángulo de cámara; la retroalimentación es basada en reglas, no adaptativa |
| **Clasificación y conteo en tiempo real** [8] — Riccio, 2024 | BiLSTM sobre secuencias de 30 fotogramas, combinando ángulos invariantes con coordenadas crudas (x, y, z); integrado en una aplicación web | Más de 99 % de exactitud en el conjunto de prueba, sobre cuatro ejercicios (sentadilla, flexión, press de hombros, curl de bíceps), sin selección manual del ejercicio | Entrenado sobre mezcla de datos sintéticos (InfiniteRep) y videos reales; el trabajo se centra en clasificación y conteo, no en corrección de la técnica |
| **Revisión de IA en fitness** [10] — Phalke *et al.*, 2025 | Revisión de PoseNet, OpenPose, HRNet, BlazePose y ConvNeXtPose; retroalimentación mediante función de costo sobre distancia euclidiana entre articulaciones del usuario y objetivo, entregada como superposición visual o avatar | No reporta cifras de exactitud; valoraciones cualitativas | Requiere grandes volúmenes de datos; puede fallar si el modelo no se ajusta a distintos tipos de cuerpo; disyuntiva exactitud/eficiencia en modelos livianos; conjuntos de datos limitados para ejercicios específicos |
| **FLAG3D** [11] — Tang *et al.*, CVPR 2023 | Conjunto de datos de 180 000 secuencias y 60 categorías de actividad, con pose 3D de captura de movimiento e **instrucción profesional en lenguaje** que describe cómo ejecutar cada actividad | Habilita reconocimiento de acción entre dominios, recuperación de malla humana dinámica y generación de acción guiada por lenguaje | Es un recurso de datos, no un sistema de retroalimentación |

**Dos observaciones sobre este cuerpo de trabajo.** Primera: **DTW cuenta con antecedentes en la comparación de ejecuciones de un mismo movimiento a velocidades distintas**, como muestran [7] y [9]. Esto proporciona un precedente técnico para considerar dicho método en el proyecto. 

Segunda: la retroalimentación en la literatura es, o basada en reglas y umbrales fijos [9], o generada desde reconstrucción 3D con un modelo estadístico [6], o simplemente visual [10]. No se localizó, en las fuentes consultadas, un trabajo que interponga un modelo multimodal y un modelo de lenguaje ejecutados localmente entre la medición geométrica y el mensaje hablado, ni que reporte el presupuesto de latencia extremo a extremo como criterio de aceptación. Una fuente secundaria de la investigación interna del equipo reporta un sistema de evaluación postural en dispositivo con 50 ms de latencia por fotograma en un teléfono con NPU, en un dominio distinto (postura de chelista); se menciona como indicio de viabilidad y queda pendiente de verificación directa.

### 6.4 Comparación

| Criterio | Video pregrabado | Conteo open source (p. ej. [16]) | Comercial con cámara ([20], [23]) | Literatura académica ([6], [7], [9]) | Estela Trainer (propuesta) |
| --- | --- | --- | --- | --- | --- |
| Observa la ejecución | No | Sí | Sí | Sí | Sí |
| Evalúa la calidad, no solo la cantidad | No | No | No verificable públicamente | Sí, en algunos trabajos | Sí, objetivo |
| Retroalimentación hablada en tiempo real | No | No | No verificable de forma homogénea | Parcial | Sí, objetivo |
| Ejecución local (sin nube) | Sí | Sí | No documentado de forma homogénea | Sí en [9] | Sí, restricción de diseño |
| Costo de hardware | Nulo | Equipo propio | US$ 295 + suscripción [20]; desde US$ 39/mes + equipo [23] | Equipo propio + GPU en [7] | Equipo disponible |
| Extensible a nuevos ejercicios sin modificar la lógica principal | N/A | Parcial | No es objetivo declarado | No es objetivo declarado | Sí, objetivo mediante skills |
| En español | Variable | N/A | Variable | No identificado como requisito | Sí, requisito |
| Presupuesto de latencia como criterio de aceptación | N/A | No reportado | No publicado | No reportado | Sí, objetivo |
| Escalabilidad a múltiples usuarios simultáneos | Alta | No documentado | No comparable | No es objetivo declarado | Fuera de alcance |
| Riesgo de continuidad del servicio | Bajo | Bajo | Dependiente del proveedor | N/A | Bajo, al ejecutarse localmente |

### 6.5 Vacío identificado y oportunidad de desarrollo

De la revisión realizada se identifican cuatro oportunidades principales:

1. **La conjunción de capacidades no fue identificada en las fuentes consultadas.** Existen soluciones locales que proporcionan estimación de pose, soluciones que incorporan evaluación del movimiento y sistemas que generan retroalimentación, pero no se identificó en las fuentes revisadas una propuesta que combine ejecución local, evaluación de la ejecución, retroalimentación hablada en tiempo real, soporte en español y una arquitectura extensible mediante la definición externa de ejercicios.
2. **La latencia extremo a extremo presenta una oportunidad de evaluación.** Los trabajos revisados reportan principalmente métricas de clasificación, reconocimiento o puntuación, mientras que no se identificó un criterio de aceptación basado en la latencia del proceso completo desde la captura del movimiento hasta la generación de la retroalimentación. Para un sistema de asistencia durante la ejecución, esta dimensión resulta relevante, dado que el momento de entrega de la retroalimentación puede influir en su utilidad [3].
3. **La interpretación de las desviaciones constituye un componente abierto.** La medición geométrica de un movimiento y la generación de una instrucción comprensible son problemas diferentes. Los trabajos revisados emplean principalmente reglas, umbrales o mecanismos estadísticos para producir retroalimentación [6], [9]. Esto abre la posibilidad de estudiar alternativas de interpretación local, cuya precisión y comportamiento deberán ser evaluados antes de incorporarlas al sistema.
4. **La extensibilidad constituye una oportunidad arquitectónica.** Los sistemas de retroalimentación revisados suelen estar construidos alrededor de un conjunto limitado de ejercicios y reglas específicas para cada uno [7], [8], [9]. Aunque existen conjuntos de datos con un número considerable de actividades [6], [11], estos no corresponden directamente a sistemas de retroalimentación en operación. La separación entre el *pipeline* de análisis y la definición de cada ejercicio constituye, por tanto, una característica que puede explorarse en el diseño propuesto.

En consecuencia, la revisión sugiere una oportunidad de investigación y desarrollo: evaluar una arquitectura que integre capacidades de estimación de pose, comparación del movimiento e interpretación de la ejecución bajo las restricciones de procesamiento local, retroalimentación en tiempo real y privacidad definidas para el proyecto. El proyecto abordará esta oportunidad mediante un prototipo cuya arquitectura y componentes concretos serán validados experimentalmente.

## 7. Metodología de desarrollo y plan de trabajo

Describe el enfoque metodológico que orientará el desarrollo del proyecto y la forma en que este se traducirá en actividades, iteraciones y entregables concretos. Debe explicar cómo se construirá, validará y refinará la solución a lo largo del proceso.

### 7.1 Enfoque metodológico

Explica la metodología adoptada para el desarrollo del proyecto, justificando su elección. En particular, debe describirse el uso de un enfoque de prototipado iterativo, indicando cómo se plantea avanzar mediante ciclos sucesivos de diseño, construcción, prueba y ajuste de la solución.

### 7.2 Iteraciones o fases de desarrollo

Describe las principales fases o iteraciones previstas para el proyecto, indicando el propósito de cada una, las actividades principales a realizar y la manera en que cada ciclo contribuirá al refinamiento progresivo de la solución.

### 7.3 Estrategia de validación

Explica cómo se evaluarán los avances en cada iteración, por ejemplo mediante retroalimentación de usuarios, pruebas funcionales, revisión de requerimientos o validaciones técnicas y de usabilidad.

### 7.4 Plan de trabajo, cronograma o hitos

Presenta la planificación general del proyecto en forma de cronograma, tabla o listado de hitos, indicando las actividades principales, los entregables esperados y, cuando aplique, la temporalidad estimada de cada fase.

## 8. Referencias

[1] World Health Organization, "Physical activity," *Fact sheets*, 26 de junio de 2024. [En línea]. Disponible: https://www.who.int/news-room/fact-sheets/detail/physical-activity

[2] World Health Organization, "Prevalence of insufficient physical activity among adults aged 18+ years (age-standardized estimate) — Colombia," *Global Health Observatory*, indicador NCD_PAC, serie anual 2000–2022. Consulta filtrada por país. [En línea]. Disponible: https://ghoapi.azureedge.net/api/NCD_PAC?$filter=SpatialDim eq 'COL'

[3] R. Sigrist, G. Rauter, R. Riener y P. Wolf, "Augmented visual, auditory, haptic, and multimodal feedback in motor learning: A review," *Psychonomic Bulletin & Review*, vol. 20, n.º 1, pp. 21–53, 2013, doi: 10.3758/s13423-012-0333-8.

[4] J. Nielsen, "Response times: The 3 important limits," *Nielsen Norman Group*, 1993 (extraído de *Usability Engineering*, 1993). [En línea]. Disponible: https://www.nngroup.com/articles/response-times-3-important-limits/

[5] Congreso de la República de Colombia, *Ley 1581 de 2012 — Por la cual se dictan disposiciones generales para la protección de datos personales*, arts. 1 y 5. Los datos biométricos se clasifican como datos sensibles.

[6] M. Fieraru, M. Zanfir, S. C. Pirlea, V. Olaru y C. Sminchisescu, "AIFit: Automatic 3D human-interpretable feedback models for fitness training," en *Proc. IEEE/CVF Conf. on Computer Vision and Pattern Recognition (CVPR)*, 2021, pp. 9919–9928.

[7] S. Chen y R. R. Yang, "Pose Trainer: Correcting exercise posture using pose estimation," Dept. of Computer Science, Stanford University, arXiv:2006.11718, 2020.

[8] R. Riccio, "Real-time fitness exercise classification and counting from video frames," arXiv:2411.11548 [cs.CV], 2024.

[9] S.-C. Yeh y C.-K. Yang, "Yoga pose recognition and motion analysis for a home-based fitness monitoring and health management system," *Signal, Image and Video Processing*, vol. 19, art. 841, 2025, doi: 10.1007/s11760-025-04436-6.

[10] D. A. Phalke, V. Kotipalli, P. Ranjan, Y. Pawar y P. Bharat, "Artificial intelligence in fitness: Pose estimation and movement correction," *Cureus Journal of Computer Science*, vol. 2, n.º 1, 28 de marzo de 2025, doi: 10.7759/s44389-024-00747-w.

[11] Y. Tang *et al.*, "FLAG3D: A 3D fitness activity dataset with language instruction," en *Proc. IEEE/CVF Conf. on Computer Vision and Pattern Recognition (CVPR)*, 2023, arXiv:2212.04638.

[12] V. Bazarevsky, I. Grishchenko, K. Raveendran, T. Zhu, F. Zhang y M. Grundmann, "BlazePose: On-device real-time body pose tracking," *CVPR Workshop on Computer Vision for Augmented and Virtual Reality*, 2020, arXiv:2006.10204.

[13] Google, "Pose landmark detection guide," *MediaPipe Solutions documentation*, actualizado el 17 de agosto de 2026. [En línea]. Disponible: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker

[14] T. Jiang, P. Lu, L. Zhang, N. Ma, R. Han, C. Lyu, Y. Li y K. Chen, "RTMPose: Real-time multi-person pose estimation based on MMPose," arXiv:2303.07399 [cs.CV], 2023.

[15] H. Sakoe y S. Chiba, "Dynamic programming algorithm optimization for spoken word recognition," *IEEE Transactions on Acoustics, Speech, and Signal Processing*, vol. 26, n.º 1, pp. 43–49, 1978.

[16] Ultralytics, "Workouts monitoring using Ultralytics YOLO," *Ultralytics Docs*. [En línea]. Disponible: https://docs.ultralytics.com/guides/workouts-monitoring/

[17] Google AI Edge, "Issue #5842: `num_poses` and single-person support," *google-ai-edge/mediapipe*, GitHub, 2025. [En línea]. Disponible: https://github.com/google-ai-edge/mediapipe/issues/5842

[18] hexgrad, "Kokoro-82M," *Hugging Face*. Modelo de síntesis de voz de 82 millones de parámetros, pesos bajo licencia Apache 2.0. [En línea]. Disponible: https://huggingface.co/hexgrad/Kokoro-82M

[19] Apple, "Apple introduces M2 Ultra," *Apple Newsroom*, 5 de junio de 2023. [En línea]. Disponible: https://www.apple.com/newsroom/2023/06/apple-introduces-m2-ultra/

[20] "Peloton Interactive," *Wikipedia* (fuente secundaria; especificaciones de Peloton Guide: cámara de 12 MP, US$ 295, lanzamiento 5 de abril de 2022). Consultado el 24 de agosto de 2026.

[21] I. Grishchenko *et al.*, "BlazePose GHUM Holistic: Real-time 3D human landmarks and pose estimation," arXiv:2206.11678, 2022.

[22] Kaia Health, sitio oficial. [En línea]. Disponible: https://kaiahealth.com/ (consultado el 24 de agosto de 2026).

[23] Tempo, sitio oficial. [En línea]. Disponible: https://www.tempo.fit/ (consultado el 24 de agosto de 2026).

[24] Peloton Interactive, URL histórica del producto Guide, sitio oficial. [En línea]. Disponible: https://www.onepeloton.com/guide (consultado el 24 de agosto de 2026; la página servida presenta el catálogo vigente de dispositivos —Bike, Bike+, Tread, Tread+ y Row+— sin describir el Guide).

[25] Google AI Edge, "MediaPipe Pose (documentación *legacy*)," *google-ai-edge/mediapipe*, GitHub. Conjuntos de validación internos (Yoga, Dance, HIIT) con una sola persona a 2–4 m de la cámara. [En línea]. Disponible: https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/pose.md
