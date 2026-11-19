# Guía para el informe final del proyecto

## Resumen / Abstract

Presenta una síntesis del proyecto que incluya el problema abordado, la solución propuesta, la metodología empleada, los principales resultados y las conclusiones más relevantes. Debe ser autocontenido y permitir al lector comprender la esencia del trabajo sin leer el documento completo.

## 1. Introducción

Presenta el contexto del proyecto, describe la situación actual y explica la necesidad u oportunidad identificada que motiva el desarrollo de la solución.

## 2. Marco conceptual

Presenta los conceptos, métodos, técnicas y términos fundamentales necesarios para comprender adecuadamente el problema, la solución propuesta y las decisiones técnicas del proyecto.

## 3. Planteamiento del problema

Define y delimita el problema central, explicando qué se busca resolver y por qué es relevante.

### 3.1 Descripción del problema

Expone con claridad la problemática, sus causas, a quién afecta y cuáles son sus principales consecuencias.

### 3.2 Restricciones y supuestos de diseño

Indica las limitaciones técnicas, económicas, de tiempo, normativas u otras relevantes, así como los supuestos bajo los cuales se plantea la solución.

### 3.3 Alcance

Especifica qué incluye y qué no incluye el proyecto, delimitando entregables, funcionalidades y fronteras del trabajo.

## 4. Objetivos

Establece el objetivo principal del proyecto y lo descompone en objetivos específicos medibles que guían el desarrollo.

## 5. Estado del arte / soluciones relacionadas

Resume y compara soluciones existentes, académicas o comerciales, identificando enfoques relevantes, ventajas, limitaciones y oportunidades de mejora.

## 6. Solución propuesta

Describe a alto nivel la solución desarrollada para abordar el problema planteado. Explica el enfoque general, los principios que guían la propuesta, su valor frente a las soluciones existentes y las razones por las cuales constituye una respuesta adecuada dentro del alcance, las restricciones y los objetivos del proyecto. Esta sección debe responder qué se construyó y por qué, sin entrar aún en detalles de diseño o implementación.

## 7. Metodología de desarrollo

Describe el enfoque metodológico utilizado para desarrollar el proyecto, justificando su elección. Explica cómo se estructuraron las iteraciones o fases de trabajo, cómo se construyeron y refinaron los prototipos, qué mecanismos de validación se emplearon y qué artefactos o resultados surgieron durante el proceso.

## 8. Requerimientos

Detalla lo que el sistema debe cumplir para ser considerado correcto y útil.

### 8.1 Funcionales

Describe las funciones y comportamientos que el sistema debe ofrecer, es decir, qué hace el sistema.

### 8.2 No funcionales

Define atributos de calidad y restricciones del sistema, como rendimiento, seguridad, usabilidad, escalabilidad y mantenibilidad.

## 9. Evaluación de alternativas

Antes de definir cómo se construirá el sistema, es necesario analizar diferentes formas posibles de implementarlo.

Ver detalle completo en el [Segundo Informe](./SegundoInforme.md#8-evaluación-de-alternativas).

## 10. Diseño y arquitectura

Explica cómo se estructurará la solución a nivel conceptual y técnico, justificando decisiones clave.

### 10.1 Arquitectura

La arquitectura describe la estructura fundamental del sistema, incluyendo sus componentes, las relaciones entre ellos y la forma en que interactúan para cumplir con los requerimientos planteados.

#### 10.1.1 Descripción general de la arquitectura

Su objetivo es permitir que el lector entienda cómo está pensado el sistema antes de ver cualquier representación visual.

Debe incluir:

- tipo de arquitectura, por ejemplo cliente-servidor, basada en Backend as a Service u otra;
- enfoque general de la solución;
- relación con la alternativa seleccionada previamente.

#### 10.1.2 Componentes del sistema e interacción

##### 10.1.2.1 Descripción de componentes

Deben identificarse y explicarse:

- los componentes principales del sistema, por ejemplo frontend, backend, base de datos y servicios externos;
- la responsabilidad de cada componente;
- la relación de cada componente con los requerimientos del sistema.

Esta parte debe terminar con el **diagrama de arquitectura del sistema**.

##### 10.1.2.2 Interacción entre módulos

Debe explicarse:

- cómo se comunican los componentes;
- los flujos de datos;
- las dependencias;
- el nivel de acoplamiento.

Esta parte debe terminar con el **diagrama de interacción entre módulos**.

##### 10.1.2.3 Comportamiento

Debe explicarse cómo se comportan los componentes, describiendo las principales secuencias de la arquitectura y respondiendo preguntas como:

- ¿el flujo es eficiente?
- ¿existen pasos innecesarios?
- ¿hay problemas de latencia?
- ¿existen cuellos de botella?
- ¿la interacción refleja un buen desacoplamiento?

En esta parte se utilizan **diagramas de secuencia**.

## 11. Implementación

Documenta lo construido hasta el momento, mostrando el avance funcional y técnico del proyecto.

### 11.1 Stack tecnológico

Lista y justifica las tecnologías, frameworks, librerías y herramientas utilizadas.

### 11.2 Componentes

Documenta los componentes o módulos efectivamente implementados, indicando su estado de desarrollo, las funcionalidades que cubren, las decisiones técnicas relevantes tomadas durante su construcción y, cuando aplique, las diferencias entre el diseño propuesto y la implementación realizada.

### 11.3 Integraciones

Explica las conexiones con servicios externos, como APIs, bases de datos, autenticación o terceros, e indica su estado de funcionamiento.

## 12. Despliegue y operación

Describe cómo se ejecuta, configura y opera la solución en su entorno previsto, incluyendo aspectos de instalación, infraestructura, dependencias, puesta en marcha y condiciones de operación, según aplique al proyecto.

## 13. Validación

Presenta el informe de pruebas realizadas para verificar que el sistema funciona correctamente y cumple los requerimientos establecidos.

### 13.1 Pruebas por componentes

Documenta las pruebas unitarias o por módulo ejecutadas, los criterios de éxito, los casos evaluados y los resultados obtenidos.

### 13.2 Pruebas de integración

Describe las pruebas realizadas sobre la interacción entre componentes y servicios, incluyendo flujos completos, manejo de errores y resultados observados.

### 13.3 Pruebas de usabilidad

Expone las pruebas de usabilidad aplicadas para evaluar la experiencia del usuario, indicando metodología, criterios de aceptación, hallazgos y nivel de cumplimiento.

## 14. Resultados, discusión y conclusiones

Presenta los resultados obtenidos a partir del desarrollo y la validación del sistema, e interpreta su significado frente a los objetivos, requerimientos, decisiones de diseño y limitaciones del proyecto.

## 15. Trabajo futuro

Las líneas que quedan abiertas se agrupan en validación, desempeño y extensión del sistema.

### 15.1 Validación con personas y calibración de umbrales

Los umbrales de los ejercicios son provisionales: provienen de la revisión con la licenciada en educación física y de vídeos públicos, y los seis skills permanecen en estado `candidato`. El paso siguiente es grabar y anotar sesiones con participantes (protocolo V-01), con lo que se podrán medir la precisión, el recobrado y la sobrecorrección del feedback, que hoy están pendientes, y calibrar el factor `k` de los umbrales relativos a la referencia (EXP-005). Hasta entonces, los umbrales relativos y el alineamiento con DTW están implementados pero desactivados por defecto.

### 15.2 Latencia de la voz

En las mediciones preliminares del segundo informe, el tiempo entre la detección de un error y el inicio de la voz (p95 de 3,66 s) no cumple el objetivo de 1 s. La línea de trabajo prevista es sintetizar por adelantado las frases de las plantillas, de modo que durante la sesión solo se reproduzcan, y repetir la medición en el equipo final.

### 15.3 Incorporación de nuevos ejercicios

El sistema define cada ejercicio de forma externa: un archivo de skill con sus reglas, una referencia grabada y sus frases, sin modificar el motor de decisión. Solo se requiere programar cuando un ejercicio necesita una medida geométrica que aún no se calcula. Lo que falta es un procedimiento que indique cuándo un ejercicio está listo. Se dejó propuesto, sin adoptar, un protocolo de alta con seis pasos (filtro de observabilidad con una cámara, grabación de calibración, skill y referencia, revisión con el visor, revisión de la licenciada y puerta de adopción), documentado en `experimentos/PROTOCOLO-ALTA-EJERCICIO.md` del repositorio de documentación.

### 15.4 Modo entrenador

La arquitectura separa una fase de autoría, en la que se crean y ajustan los ejercicios, de la sesión en tiempo real. La sesión cuenta con interfaz; la autoría se hace hoy con herramientas de consola. Como primer paso se desarrolló un visor de calibración (`backend/scripts/visor_calibracion.py`, rama `feature/visor-calibracion`) que, a partir de un vídeo, grafica lo que mide cada regla, su umbral, los instantes en que detecta un error y aquellos en que el sistema lo dice en voz alta.

Queda como trabajo futuro llevar esa herramienta a la interfaz, en una vista para quien da de alta los ejercicios: primero un vídeo anotado que resalte sobre el esqueleto el segmento con error, luego una pantalla de consulta con el vídeo y las curvas sincronizados y, por último, la edición de umbrales desde la propia pantalla. El detalle, las etapas y las decisiones abiertas están en `TRABAJO-FUTURO-modo-entrenador.md` del repositorio de documentación.

### 15.5 Verbalización y reconocimiento

El uso de un modelo de lenguaje local como verbalizador en vivo no se adoptó; queda sujeto al experimento EXP-001 con criterios acordados de antemano, manteniendo las plantillas deterministas como respaldo. El reconocimiento del ejercicio que se está realizando está integrado como función opcional y desactivada por defecto; sus tasas de acierto se midieron con un conjunto pequeño de vídeos anterior a la incorporación de la zancada, por lo que deben volver a medirse.

## 16. Referencias

Incluye todas las fuentes consultadas y citadas en el documento, en el formato de citación definido para el curso o proyecto.
