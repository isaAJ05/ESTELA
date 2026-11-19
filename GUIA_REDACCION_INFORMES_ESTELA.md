# Guía de redacción para los informes de ESTELA

## 1. Propósito de esta guía

Esta guía establece el estilo que debe seguirse al redactar, revisar o ampliar los informes académicos del proyecto ESTELA.

El objetivo es producir un documento universitario riguroso, claro y bien organizado, pero escrito con un lenguaje natural. El informe debe demostrar que el equipo comprende el problema, las decisiones tomadas, la solución desarrollada y sus resultados. No debe sonar como un artículo excesivamente especializado ni utilizar tecnicismos solo para aparentar complejidad.

**Principio central:** explicar con precisión, usando el lenguaje más sencillo que permita conservar el significado técnico.

Esta guía complementa la plantilla oficial del informe. No la reemplaza ni modifica sus requisitos.

## 2. Voz y tono

Escribe con un tono:

- **Académico:** apropiado para un informe final de Ingeniería de Sistemas.
- **Natural:** fluido y fácil de seguir, sin frases artificiales o rebuscadas.
- **Profesional:** preciso, objetivo y respetuoso.
- **Claro:** pensado para que un lector de la carrera pueda comprender el proyecto aunque no sea especialista en visión por computador, biomecánica o aprendizaje motor.
- **Honesto:** distingue lo que se implementó, lo que se probó, lo que se observó y lo que todavía está pendiente.

La voz debe sentirse como la de un equipo de estudiantes que explica un proyecto que desarrolló y conoce. No debe parecer publicidad del producto ni una publicación científica escrita para especialistas.

Evita tanto el extremo demasiado coloquial como el extremo excesivamente técnico.

## 3. Cómo construir los párrafos

### 3.1 Una idea principal por párrafo

Cada párrafo debe desarrollar una idea central. Si contiene varias explicaciones independientes, divídelo.

Como orientación general:
- Prioriza párrafos de entre 3 y 6 oraciones.
- Alterna párrafos breves y medianos según la complejidad del tema.
- Evita bloques muy extensos que obliguen al lector a releer.
- No dividas artificialmente una explicación que necesita continuidad.

### 3.2 Oraciones directas

Prefiere oraciones de estructura sencilla: sujeto, acción y explicación.

Evita acumular aclaraciones, incisos, listas y subordinadas dentro de una sola oración. Si una oración contiene demasiadas comas, revisa si conviene dividirla.

No es necesario que todas las oraciones sean cortas. Lo importante es que cada una exprese una idea con claridad.

### 3.3 Orden recomendado para explicar una idea

Cuando sea posible, sigue esta secuencia:

1. Presenta la idea.
2. Explica qué significa.
3. Relaciónala con ESTELA.
4. Menciona la decisión o consecuencia que tiene para el proyecto.

No comiences con una definición extremadamente especializada si primero puedes ofrecer una explicación sencilla que ubique al lector.

## 4. Uso de términos técnicos

ESTELA es un proyecto de Ingeniería de Sistemas, por lo que debe conservar su precisión técnica. No elimines términos necesarios ni reemplaces conceptos específicos por expresiones vagas.

Sin embargo:

- Introduce cada término especializado con una explicación breve la primera vez que aparezca.
- Después de definirlo, utiliza el mismo término de forma consistente.
- Incluye el nombre en inglés entre paréntesis cuando sea útil para reconocer una tecnología o concepto.
- Evita encadenar varios términos técnicos sin explicar cómo se relacionan.
- No repitas definiciones completas en distintas secciones. Si hace falta, recuerda brevemente el concepto y continúa.
- No utilices sinónimos distintos para un mismo componente si eso puede generar confusión.

### Ejemplo

**Evitar:**

> El alineador DTW incremental ejecuta un proceso de alineamiento temporal no lineal sobre secuencias de características normalizadas, permitiendo obtener un camino de correspondencia entre los índices de ambas series.

**Preferir:**

> ESTELA utiliza Dynamic Time Warping (DTW) para comparar el movimiento del usuario con una ejecución de referencia. Esta técnica permite comparar dos movimientos aunque se realicen a velocidades diferentes. Así, el sistema puede identificar qué momentos de ambos movimientos corresponden entre sí.

La segunda versión conserva el concepto y explica para qué se utiliza.

## 5. Explicar desde el proyecto

Siempre que sea posible, conecta las explicaciones generales con una decisión o una situación concreta de ESTELA.

Por ejemplo, en lugar de limitarte a definir la estimación de pose, explica que ESTELA utiliza la cámara para identificar puntos del cuerpo, como hombros, caderas, rodillas y tobillos. A partir de esos puntos calcula medidas que permiten analizar la ejecución de los ejercicios.

Utiliza ejemplos concretos cuando ayuden a comprender:
- cómo se identifica una postura;
- por qué el usuario debe ubicarse frente a la cámara o de perfil;
- cómo se compara una repetición con una referencia;
- por qué el sistema puede decidir no emitir una corrección;
- cómo se organiza la información de cada ejercicio;
- qué ocurre durante una sesión y al finalizarla.

No inventes ejemplos de comportamiento que no estén implementados. Si el ejemplo es hipotético, indícalo como tal.

## 6. Evitar una redacción innecesariamente rebuscada

No utilices expresiones complejas cuando una alternativa sencilla comunica lo mismo.

| Evitar cuando no aporta precisión | Preferir |
|---|---|
| En virtud de lo anteriormente expuesto | Por esta razón |
| Cabe destacar que | Es importante señalar que (solo si realmente aporta) |
| En este sentido, resulta pertinente mencionar | Además / Por otra parte |
| La presente solución tecnológica | ESTELA / La aplicación |
| Se procede a realizar la identificación | El sistema identifica |
| Efectúa la transformación de los datos | Transforma los datos |
| Constituye un elemento fundamental para | Es importante para |
| A nivel de la arquitectura | En la arquitectura |
| Dicha funcionalidad permite llevar a cabo | Esta función permite |
| En el marco del presente proyecto | En el proyecto |

No reemplaces mecánicamente todas estas expresiones. Evalúa cada caso y conserva las formulaciones que sean necesarias para la precisión o la cohesión.

Evita también:
- Comenzar muchos párrafos con «En este sentido», «De esta manera», «Por otra parte» o «Cabe destacar».
- Usar palabras grandilocuentes como «revolucionario», «innovador» o «disruptivo» sin evidencia.
- Crear frases dramáticas para describir decisiones técnicas.
- Utilizar metáforas que dificulten la comprensión.
- Presentar cada decisión como si fuera una contribución científica novedosa.

## 7. Evitar repeticiones

Antes de redactar una sección, identifica qué información ya fue explicada y qué debe aportar esa sección.

Cada apartado tiene una función. Por ejemplo:

- **Marco conceptual:** explica los conceptos necesarios para comprender el proyecto.
- **Planteamiento del problema:** presenta la necesidad, las restricciones y el alcance.
- **Solución propuesta:** explica qué solución se construyó y cómo responde al problema.
- **Diseño y arquitectura:** describe cómo se organiza el sistema y cómo se relacionan sus componentes.
- **Implementación:** documenta qué se desarrolló realmente y con qué tecnologías.
- **Validación:** presenta cómo se comprobó el funcionamiento y qué resultados se obtuvieron.
- **Resultados y conclusiones:** interpreta los hallazgos y explica qué se logró frente a los objetivos.

No vuelvas a explicar toda la arquitectura en la solución propuesta, ni repitas el marco conceptual en cada sección. Utiliza referencias internas a otras secciones cuando sea conveniente.

## 8. Precisión y honestidad académica

La claridad nunca debe conseguirse alterando los hechos.

Es obligatorio:

- Conservar los datos, porcentajes, fechas, nombres de tecnologías, versiones, resultados y referencias del material fuente.
- No inventar resultados ni completar valores desconocidos mediante estimaciones.
- No presentar una prueba planeada como si ya se hubiera realizado.
- No afirmar que una funcionalidad está terminada si el material indica que está pendiente o parcialmente implementada.
- Diferenciar resultados medidos, observaciones cualitativas, hipótesis y trabajo futuro.
- Mantener las limitaciones del sistema y explicar su impacto de manera comprensible.
- Conservar las citas asociadas a las afirmaciones que respaldan.
- No inventar referencias bibliográficas ni atribuir conclusiones a fuentes que no las sostienen.
- Señalar cualquier contradicción, dato faltante o afirmación que necesite confirmación del equipo.

Si una afirmación no está respaldada por los documentos o por evidencia disponible, no la presentes como un hecho. Marca la información para revisión.

## 9. Cómo presentar decisiones técnicas

Explica las decisiones técnicas desde su propósito y sus consecuencias.

Cuando describas una tecnología, módulo o herramienta, procura responder:

1. ¿Qué es o qué función cumple?
2. ¿Por qué se eligió para ESTELA?
3. ¿Cómo se utiliza dentro del sistema?
4. ¿Qué aporta y qué limitaciones tiene?

No es necesario responder las cuatro preguntas en todos los casos. Incluye únicamente lo que ayude al lector a comprender la decisión.

Evita convertir cada descripción en una lista extensa de características de una herramienta. El informe debe explicar por qué esa herramienta tiene sentido en el proyecto, no reproducir su documentación oficial.

## 10. Tablas, listas, figuras y diagramas

- Utiliza tablas cuando permitan comparar información o consultar datos con mayor facilidad.
- No conviertas todo el contenido en tablas. Las explicaciones y los argumentos deben desarrollarse principalmente en prosa.
- Usa listas para enumerar requerimientos, pasos, componentes o elementos que realmente se beneficien de ese formato.
- Introduce cada figura o diagrama explicando qué representa y por qué es relevante.
- Después de una figura importante, interpreta los elementos que el lector debe observar. No te limites a colocar la imagen.
- Mantén los nombres de módulos, tecnologías y elementos de los diagramas consistentes con el texto.

## 11. Reglas de estilo y formato

- Redacta en español, salvo nombres oficiales, términos técnicos y fragmentos de código.
- Mantén los nombres propios de tecnologías y herramientas: MediaPipe Pose Landmarker, Dynamic Time Warping (DTW), Piper, entre otros.
- Usa cursiva para términos extranjeros cuando corresponda y de forma consistente.
- Conserva los identificadores técnicos, nombres de archivos, clases, funciones y configuraciones en formato de código.
- Utiliza siglas después de presentar su significado la primera vez.
- Evita el uso excesivo de negritas. Resérvalas para conceptos o elementos que realmente necesiten destacarse.
- Mantén la numeración y jerarquía de títulos de la plantilla oficial.
- Revisa la puntuación, las concordancias y las transiciones entre párrafos.
- No utilices frases como «como se mencionó anteriormente» repetidamente. Cuando sea útil, indica la sección concreta.

## 12. Instrucciones para revisar un texto existente

Cuando recibas una sección ya redactada:

1. Lee la sección completa y comprende qué quiere comunicar.
2. Identifica las ideas, los datos y las afirmaciones que deben conservarse.
3. Reescribe las oraciones complejas para que sean más directas y naturales.
4. Divide los párrafos que desarrollen demasiadas ideas.
5. Reduce tecnicismos innecesarios, pero conserva los términos que aportan precisión.
6. Elimina repeticiones dentro de la sección y con otras partes del informe.
7. Comprueba que la nueva versión conserve el significado original.
8. Revisa que las citas sigan respaldando las mismas afirmaciones.
9. Señala los datos dudosos, las contradicciones y los pendientes; no los resuelvas inventando información.

**No hagas una simple sustitución de palabras.** Mejora la explicación, el orden de las ideas y la fluidez del texto.

## 13. Instrucciones para redactar una sección nueva

Antes de escribir:

- Consulta la plantilla oficial y respeta el propósito del apartado.
- Revisa los informes anteriores y los documentos del proyecto que sean pertinentes.
- Identifica qué información está confirmada y cuál sigue pendiente.
- Evita duplicar contenido que ya tiene una ubicación adecuada en el documento.

Al redactar:

- Comienza con una explicación que ubique al lector.
- Desarrolla las ideas en un orden lógico.
- Relaciona los conceptos con ESTELA.
- Incluye el nivel de detalle que requiere esa sección, sin anticipar explicaciones que corresponden a apartados posteriores.
- Finaliza conectando las ideas o preparando la transición hacia el siguiente tema, cuando sea necesario.

## 14. Ejemplo del estilo esperado

**Versión demasiado técnica:**

> La arquitectura se organiza como una cadena de etapas separadas por contratos de datos: un estimador de pose convierte cada fotograma en puntos articulares; un módulo de geometría los transforma en ángulos y distancias normalizadas; un segmentador identifica fases y repeticiones; y un alineador DTW compara la repetición en curso con una referencia del ejercicio.

**Versión recomendada:**

> ESTELA analiza los movimientos del usuario mediante varias etapas que trabajan de manera conjunta. Primero, utiliza la cámara para identificar puntos del cuerpo, como los hombros, las caderas y las rodillas. Con esta información calcula ángulos y distancias que permiten estudiar cómo se está realizando cada ejercicio. Después, identifica las fases y repeticiones del movimiento y las compara con una referencia mediante DTW, una técnica que permite tener en cuenta las diferencias de velocidad. A partir de esta comparación, el sistema determina si debe emitir una recomendación o si es mejor no intervenir.

La versión recomendada no elimina los conceptos técnicos. Los presenta en un orden más fácil de seguir y explica su función dentro del proyecto.

## 15. Lista de comprobación antes de entregar un apartado

Antes de considerar terminada una sección, verifica lo siguiente:

- [ ] ¿Se entiende en una primera lectura?
- [ ] ¿El tono es académico, pero natural?
- [ ] ¿Cada párrafo desarrolla una idea principal?
- [ ] ¿Las oraciones son claras y no demasiado extensas?
- [ ] ¿Los términos técnicos están explicados cuando hace falta?
- [ ] ¿Se relaciona la explicación con el proyecto ESTELA?
- [ ] ¿Se evitaron repeticiones y frases de relleno?
- [ ] ¿Se conserva la información técnica importante?
- [ ] ¿Los datos y resultados están respaldados por las fuentes?
- [ ] ¿Se distingue lo implementado de lo pendiente?
- [ ] ¿Se respetan la plantilla, las citas y la estructura del informe?

## 16. Prompt de uso para Claude

Al trabajar en el informe final de ESTELA, sigue siempre esta guía de redacción y la plantilla oficial del proyecto.

Quiero un informe académico de Ingeniería de Sistemas con un lenguaje claro, natural y profesional. Redacta como un equipo de estudiantes que conoce y comprende lo que desarrolló. Conserva el rigor técnico, pero evita el lenguaje innecesariamente complejo, las oraciones extensas, los párrafos densos y las explicaciones que parecen escritas para demostrar sofisticación.

Prioriza la claridad y la comprensión del lector. Explica los términos especializados cuando aparezcan por primera vez y relaciónalos con el funcionamiento real de ESTELA. No elimines información técnica importante ni simplifiques hasta perder precisión.

Respeta estrictamente los documentos fuente, los resultados medidos, las referencias y el estado real de implementación. No inventes información para completar vacíos. Si encuentras contradicciones o datos pendientes, indícalos para que el equipo los revise.

Antes de entregar cada texto, léelo como si fueras un lector que conoce Ingeniería de Sistemas, pero que no participó en el desarrollo de ESTELA. Si una oración resulta difícil de entender, vuelve a escribirla de forma más directa.

No cambies la estructura de la plantilla oficial sin autorización. Cuando revises una sección existente, entrega el texto completo corregido y conserva su contenido sustancial, sus citas y sus datos verificables.

**La meta no es que el informe suene más técnico. La meta es que explique mejor el trabajo realizado.**
