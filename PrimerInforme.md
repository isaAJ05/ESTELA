# Guía para el primer informe del proyecto

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

Describe a alto nivel la solución planteada para abordar el problema identificado. Explica qué se propone construir, quiénes serían sus usuarios, cómo funcionaría de manera general y por qué constituye una respuesta adecuada dentro del alcance definido.

## 6. Estado del arte / soluciones relacionadas

Presenta antecedentes o soluciones existentes relevantes, con el fin de contextualizar la propuesta y mostrar oportunidades de diferenciación, mejora o aporte.

Responde a las preguntas: ¿qué soluciones existen hoy?, ¿cómo abordan el problema?, ¿qué limitaciones presentan?

### Revisar

- Productos comerciales.
- Soluciones open-source.
- Arquitecturas o enfoques técnicos relevantes.

### Comparar

- Funcionalidad.
- Escalabilidad.
- Costos.
- Usabilidad.
- Limitaciones técnicas.

### Resultados esperados

- Identificación de **vacíos, oportunidades o problemas no resueltos**.
- **Justificación técnica** de por qué se requiere una nueva solución.

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
