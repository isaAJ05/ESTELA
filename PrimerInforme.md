# Guía para el primer informe del proyecto

## Resumen / Abstract

Presenta una síntesis breve del problema abordado, la solución propuesta, el alcance del proyecto, la metodología de desarrollo y el plan general de trabajo. Debe permitir al lector comprender la esencia del proyecto sin necesidad de leer el documento completo.

## 1. Introducción

Redacta la introducción como un texto continuo de 4 párrafos. El primero debe describir el dominio o sector del proyecto, las tendencias tecnológicas relevantes y el rol del software en ese contexto. El segundo debe exponer la situación actual: limitaciones del mercado, carencias funcionales y el impacto en los usuarios. El tercero debe presentar la necesidad técnica identificada y la oportunidad de diseño tecnológico. El cuarto, opcional, debe cerrar con una presentación general de la solución propuesta (nombre, funcionalidades clave e impacto esperado), sirviendo de transición hacia las secciones siguientes.

### Contextos

- **Dominio o sector** (ej. educación, industria, salud, ciudades inteligentes, TI).
- **Tendencias tecnológicas relevantes**.
- **Rol de los sistemas de información / software / datos** en ese contexto.

### Situación actual

- **Limitaciones del mercado actual**.
- **Carencias funcionales o de diseño**.
- **Impacto en usuarios**.

### Necesidad identificada

- **Necesidad técnica clara**.
- **Oportunidad de diseño tecnológico**.

### Propuesta general

- **Nombre del sistema**.
- **Funcionalidades clave**.
- **Impacto esperado**.

## 2. Planteamiento del problema

Define y delimita el problema central, explicando qué se busca resolver y por qué es relevante.

El problema se define como una **carencia o déficit** que se manifiesta como un **estado negativo** en una situación real (no teórica), localizado en una **población objetivo bien definida**. No debe confundirse con la falta de un servicio específico ni con la inexistencia de una solución tecnológica. El problema no es "hace falta un sistema que integre X", sino la evidencia de una situación deficiente: por ejemplo, "existen aplicaciones diferentes e incompatibles en los distintos departamentos de la empresa, lo que genera desconexión entre las unidades y pérdida de calidad en la información para la toma de decisiones". Tampoco se trata de un trabajo para una empresa en particular, sino de una **problemática transferible** a contextos similares.

### 2.1 Descripción del problema

Expone con claridad la problemática, sus causas, a quién afecta y cuáles son sus principales consecuencias.

### 2.2 Justificación

Explica por qué el problema debe ser atendido y cuál es la pertinencia académica, técnica, social o práctica del proyecto.

### 2.3 Restricciones y supuestos iniciales

Indica las principales limitaciones y condiciones asumidas para plantear la solución, tales como tiempo, recursos, acceso a información, disponibilidad de usuarios, infraestructura o restricciones técnicas.

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

Incluye las fuentes consultadas y citadas en el documento, en el formato de citación definido para el curso o proyecto.
