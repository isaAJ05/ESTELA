# ESTELA Informe N.º 2 
En el segundo informe se reflejará el trabajo desarrollado durante el semestre y se avanzará hacia una estructura más formal y cercana a la versión final del documento​
​
Por esta razón, cada componente deberá desarrollarse con un mínimo de tres párrafos, con el fin de asegurar el nivel de profundidad y coherencia esperado en un informe final.

## Resumen / Abstract

Presenta una síntesis del proyecto, incluyendo el problema abordado, la solución propuesta, el estado actual del desarrollo, los principales avances logrados, las validaciones realizadas hasta el momento y los aspectos pendientes hacia la entrega final.

## 1. Introducción

Presenta el contexto del proyecto, la necesidad u oportunidad identificada y una breve descripción del estado actual del trabajo.

Ver detalle completo en el [Primer Informe](./PrimerInforme.md#1-introducción).

## 2. Marco conceptual

ESTELA no resuelve un único problema técnico, sino una cadena de cuatro problemas encadenados, cada uno con su propio vocabulario y sus propios modos de fallo. El sistema debe primero **percibir** el cuerpo del usuario a partir de una imagen convertir píxeles en una descripción geométrica del esqueleto; luego **comparar** esa descripción con una referencia del ejercicio, teniendo en cuenta que el usuario no ejecuta a la misma velocidad que el video de referencia; después **decidir** si alguna de las diferencias observadas constituye un error que merezca ser comunicado, y si este es el momento adecuado para comunicarlo; y finalmente **comunicar** esa decisión en español hablado. Comprender el proyecto exige distinguir estas cuatro etapas, porque la evidencia disponible en la literatura indica que no son igual de difíciles ni igual de maduras: la percepción es hoy un problema con soluciones de ingeniería disponibles, mientras que la decisión sobre *qué* corregir y *cuándo* callar sigue siendo un problema abierto tanto en visión por computador como en la literatura de aprendizaje motor.

Esta separación no es solo expositiva: es la decisión arquitectónica central del proyecto. Cada frontera entre etapas se define como un contrato de datos explícito, de modo que un módulo pueda desarrollarse, probarse y sustituirse sin que los demás se enteren. El módulo de retroalimentación, por ejemplo, no accede a la cámara ni al estimador de pose: recibe una estructura de medidas ya calculadas y produce una frase o un silencio. Esto permite que ese módulo se pruebe de forma automatizada sin ninguna imagen real, y permite también cambiar de estimador de pose sin tocar la lógica de corrección. La contrapartida es que los contratos deben especificarse con precisión qué unidades, qué nombres, qué garantías de fiabilidad, y esa especificación es en sí misma un objeto de diseño del proyecto.

### 2.1 Estimación de pose humana monocular

La **estimación de pose humana** es la tarea de localizar, a partir de una imagen o un video, un conjunto predefinido de puntos anatómicos del cuerpo llamados *keypoints* o *landmarks* habitualmente hombros, codos, muñecas, caderas, rodillas y tobillos, junto con puntos de la cara y de conectarlos según una topología esquelética fija. El caso relevante para este proyecto es el **monocular**: una sola cámara RGB convencional, sin sensor de profundidad y sin marcadores adheridos al cuerpo. El proyecto adopta **MediaPipe Pose Landmarker** como estimador, basado en la familia de modelos BlazePose y su evolución BlazePose GHUM, diseñada explícitamente para inferencia en el dispositivo y no en un servidor remoto [12], [13], [21]. La alternativa considerada, RTMPose [14], se documenta en la sección 9 junto con los criterios de comparación empleados.

MediaPipe Pose Landmarker entrega dos salidas que no son intercambiables y cuya distinción condiciona el resto de la arquitectura. Los *image landmarks* son coordenadas en el plano de la imagen, normalizadas al ancho y alto del fotograma; los *world landmarks* son coordenadas métricas tridimensionales con origen en el centro de la cadera. ESTELA trabaja preferentemente sobre los segundos, porque un ángulo calculado en ese espacio no depende de la posición del usuario dentro del encuadre ni de su distancia a la cámara, mientras que el mismo ángulo calculado sobre coordenadas de imagen sí depende de ambas. Cada punto se acompaña además de un valor de **visibilidad**, que indica cuán fiable es su localización, y que es la materia prima de la política de abstención descrita en la subsección 2.7.

Un punto conceptual que condiciona todo lo que viene después es que un estimador de pose no resuelve el problema de ESTELA, solo lo habilita. El estimador entrega dónde están los puntos articulares en cada fotograma; no dice si la ejecución es correcta, no compara con ninguna referencia y no genera ninguna instrucción. La arquitectura del proyecto aísla esta dependencia detrás de un contrato de datos, de modo que el mapeo entre nombres anatómicos e índices del modelo vive en el módulo de percepción: si en el futuro el estimador se sustituye, el módulo de retroalimentación no cambia. Conviene advertir también que la tridimensionalidad de los *world landmarks* es una estimación inferida de una sola vista, no una medición de profundidad, y que su fiabilidad no debe suponerse: la subsección 2.3 desarrolla las consecuencias de esta limitación.

### 2.2 Representación del movimiento: ángulos articulares y normalización

Los puntos articulares crudos no son una representación adecuada para comparar la ejecución de dos personas distintas, ni siquiera de la misma persona en dos sesiones. Dos usuarios con estatura, longitud de extremidades o posición frente a la cámara diferentes producirán coordenadas numéricamente muy distintas aunque estén ejecutando el mismo movimiento de forma equivalente. Por eso la práctica habitual en los sistemas de análisis de ejercicio es transformar los puntos en una **representación normalizada**, es decir, en un conjunto de magnitudes que describan la *forma* del movimiento con independencia de la escala corporal, de la traslación dentro del encuadre y, en lo posible, de la orientación del sujeto. Los sistemas de referencia del área construyen esta representación a partir de ángulos articulares y de distancias relativas [6], [7], [9].

El **ángulo articular** es la magnitud central de esta representación. Se define sobre una terna ordenada de puntos por ejemplo cadera, rodilla y tobillo para el ángulo de rodilla y corresponde al ángulo que forman los dos segmentos que comparten el vértice. Su ventaja es que es invariante a traslación y a escala por construcción: no importa dónde esté la persona ni cuán larga sea su pierna, la flexión de la rodilla es la misma magnitud. Junto a los ángulos, ESTELA utiliza **distancias normalizadas por la escala corporal**, obtenidas dividiendo una distancia entre dos puntos por una longitud de referencia del propio sujeto, típicamente la distancia entre el punto medio de los hombros y el punto medio de las caderas. Esto permite expresar medidas que no son angulares la separación entre los pies, o el desplazamiento lateral de una rodilla respecto a la línea del pie, que caracteriza el *valgo de rodilla* en unidades comparables entre personas. La regla general del proyecto es que ninguna medida se expresa en píxeles y ninguna se expresa en metros absolutos.

Esta representación es también la unidad sobre la que se construyen los **nombres canónicos** del sistema. Cada ángulo y cada distancia tiene un nombre estable `rodilla_izquierda`, `tronco_inclinacion` que es independiente del estimador de pose que los produzca. Ese vocabulario cerrado cumple una función que va más allá del orden: permite que un validador posterior rechace cualquier mensaje que nombre un segmento corporal que no figure en el contrato, lo que constituye la defensa del sistema contra la clase de error descrita en la subsección 2.7. La contrapartida es que el vocabulario debe ampliarse de forma deliberada cada vez que se incorpore un ejercicio con una medida nueva, y que esa ampliación es una modificación del contrato, no un detalle de implementación.

### 2.3 Planos anatómicos y observabilidad monocular

La anatomía describe el movimiento humano sobre tres **planos** ortogonales. El *plano sagital* divide el cuerpo en mitad izquierda y mitad derecha, y contiene los movimientos de flexión y extensión: la profundidad de una sentadilla o la inclinación del tronco se leen en este plano, y se observan bien desde un perfil. El *plano frontal* divide el cuerpo en parte anterior y posterior, y contiene los movimientos de abducción y aducción: el desplazamiento lateral de una rodilla hacia dentro, o la separación de los pies, se leen aquí, y se observan bien desde el frente. El *plano transversal* es horizontal y contiene las rotaciones alrededor del eje longitudinal del cuerpo. Cada criterio técnico que ESTELA evalúa pertenece a uno de estos planos, y esa pertenencia determina desde qué orientación puede observarse.

De aquí surge el concepto de **observabilidad monocular**, que es la restricción geométrica más importante del proyecto. Una sola cámara proyecta una escena tridimensional sobre un plano bidimensional, y en esa proyección las magnitudes que se desarrollan en la dirección de la línea de visión se acortan o desaparecen. Medir un ángulo en el plano de la imagen en lugar de en tres dimensiones introduce por tanto un **error de proyección** que depende de la orientación del sujeto respecto a la cámara. La caracterización de este error para los ejercicios candidatos del proyecto se realizó en el experimento EXP-002 y se documenta en la sección 13; el resultado conceptualmente relevante aquí es que ese error puede alcanzar magnitudes del mismo orden —o mayores— que los umbrales con los que se pretende discriminar un error de ejecución, lo que significa que una medida tomada desde la orientación equivocada no es simplemente imprecisa: es inutilizable.

La consecuencia de diseño es que la orientación del usuario deja de ser un detalle del montaje y pasa a ser un parámetro del sistema. Cada regla declara el plano en el que es observable, cada ejercicio declara una **orientación preferida**, y el motor de decisión compara la orientación estimada del sujeto con la que la regla necesita antes de evaluarla. Cuando la orientación no es compatible, la regla no se evalúa: el sistema calla en lugar de afirmar algo que no puede ver. Esta salvaguarda tiene un límite conocido y explícito: las medidas del plano transversal no son observables desde ninguna orientación con una sola cámara, porque dependen íntegramente de la profundidad estimada, y por esa razón los ejercicios cuyos criterios técnicos viven en ese plano quedan fuera del conjunto validado del prototipo.

### 2.4 Comparación temporal: Dynamic Time Warping

Comparar la ejecución del usuario con la referencia del ejercicio no es una comparación fotograma a fotograma. El usuario no ejecuta a la misma velocidad que el video de referencia, no empieza en el mismo instante, y ni siquiera mantiene una velocidad constante dentro de una misma repetición: puede descender despacio y subir rápido. Una comparación que emparejara el fotograma *n* del usuario con el fotograma *n* de la referencia reportaría diferencias enormes que no corresponden a ningún error de técnica, sino simplemente a un desfase temporal. El problema que hay que resolver es el de **alineamiento temporal no lineal** entre dos series de longitudes y velocidades distintas.

**Dynamic Time Warping (DTW)** es el algoritmo clásico para este problema. Formulado originalmente para reconocimiento de voz [15], DTW busca, mediante programación dinámica, la correspondencia entre los índices de dos series temporales que minimiza el coste acumulado de emparejarlas, permitiendo que un elemento de una serie se empareje con varios de la otra. El resultado es doble: un **camino de alineamiento** (*warping path*), que indica qué instante de la ejecución del usuario corresponde a qué instante de la referencia, y un **coste de alineamiento**, que resume cuán distinta es la ejecución de la referencia una vez descontadas las diferencias de velocidad. Para ESTELA, el camino es lo que permite preguntar «en el instante en que la referencia estaba en el fondo del movimiento, ¿qué ángulo de rodilla tenía el usuario?», y esa pregunta es la que convierte una medida instantánea en una **desviación** respecto a la referencia. DTW cuenta con precedentes documentados en sistemas de análisis de ejercicio y de postura [7], [9].

Aplicar DTW en tiempo real introduce consideraciones adicionales que el algoritmo clásico no contempla. DTW se define sobre secuencias completas, mientras que durante una sesión la ejecución del usuario llega fotograma a fotograma y no se conoce su final. Esto obliga a trabajar sobre ventanas típicamente la repetición en curso y hace necesario un mecanismo de **segmentación de repeticiones** que determine dónde empieza y dónde termina cada ciclo del movimiento, así como en qué **fase** dentro del ciclo se encuentra el usuario en cada instante. La fase no es un adorno: muchos criterios técnicos solo tienen sentido en una parte del movimiento, y evaluarlos fuera de ella produce falsos positivos. El coste computacional de DTW, cuadrático en el caso general, y la existencia de variantes restringidas o aproximadas que lo reducen, forman parte de los criterios de evaluación de alternativas de la sección 9.


### 2.5 Detección de desviaciones: reglas, umbrales y severidad

Una vez disponibles los ángulos del usuario, los de la referencia alineada y las distancias normalizadas, falta el paso que convierte números en juicios: decidir qué diferencia constituye un error. ESTELA lo resuelve mediante **reglas declarativas**. Una regla asocia una medida un ángulo, una distancia, una desviación respecto a la referencia, un agregado dentro de la repetición como el mínimo o el rango, o una asimetría entre dos medidas homólogas con una condición de comparación y un **umbral**. Cuando la condición se cumple, la regla identifica un error tipificado, con un identificador estable, un segmento corporal, un lado y una fase del movimiento. Las reglas viven en el archivo de configuración de cada ejercicio, no en el código del motor, lo que permite añadir o ajustar criterios técnicos sin modificar la lógica del sistema.

El **umbral** es, en la literatura, el problema abierto de esta etapa, y conviene nombrarlo con precisión porque condiciona cualquier afirmación de exactitud que el proyecto pueda hacer. En AIFit, el sistema de referencia en generación automática de retroalimentación de fitness, el umbral que decide si una diferencia se reporta es un parámetro global ajustado manualmente, del que depende directamente la exactitud del feedback y que no se deriva de ninguna consideración biomecánica [6]. En la literatura de aprendizaje motor, el mismo problema aparece bajo el nombre de *bandwidth feedback* corregir únicamente cuando el error supera un margen de tolerancia, descrito como una estrategia eficaz pero cuyo ajuste concreto se señala como problema práctico no resuelto [3]. Dos disciplinas distintas, con años de diferencia, describen la misma laguna. La consecuencia metodológica para ESTELA es directa: los umbrales del prototipo se documentan explícitamente como provisionales y sin calibrar, y ninguna cifra de exactitud del sistema es interpretable hasta que se calibren con datos propios.

Sobre el umbral se construye además la noción de **severidad**. No toda desviación que cruza el umbral merece el mismo tratamiento: el exceso sobre el umbral se clasifica en niveles leve, moderada, alta— que después modulan tanto la prioridad del error como la formulación del mensaje. Y cuando varias reglas se activan simultáneamente, el sistema debe elegir **una sola**, porque comunicar tres correcciones a la vez durante la ejecución de un movimiento no es retroalimentación, es ruido. Esa elección se resuelve mediante un orden de prioridad declarado por ejercicio y obligatoriamente único, condición que garantiza que el comportamiento del motor sea **determinista**: ante la misma secuencia de entradas, la misma secuencia de decisiones.

### 2.6 Retroalimentación aumentada en aprendizaje motor: qué decir, cuándo y cuándo callar

La literatura de aprendizaje motor denomina **retroalimentación aumentada** a la información sobre la ejecución que un aprendiz recibe de una fuente externa, en contraposición a la retroalimentación *intrínseca*, que proviene de sus propios sentidos y, en particular, de la propiocepción. Dentro de la aumentada se distingue el *conocimiento de resultados* información sobre el desenlace, como cuántas repeticiones se completaron del *conocimiento de la ejecución*, que describe cómo se realizó el movimiento. ESTELA se sitúa deliberadamente en el segundo: el vacío que el proyecto identifica es precisamente que las aplicaciones de conteo de repeticiones informan el resultado pero no la ejecución. La revisión de Sigrist et al. sobre retroalimentación aumentada visual, auditiva, háptica y multimodal constituye la referencia central del proyecto en esta materia [3].

La dimensión temporal de la retroalimentación es tanto o más importante que su contenido. La retroalimentación *concurrente* se entrega durante el movimiento; la *terminal*, después de completarlo. La concurrente es la que ESTELA persigue, porque el problema que motiva el proyecto es que el usuario no dispone de corrección mientras ejecuta. Pero la literatura advierte de un efecto contrario: la retroalimentación permanente durante la fase de adquisición puede generar **dependencia del feedback**, llevando al aprendiz a ignorar su propia propiocepción y a rendir peor cuando la ayuda se retira lo que se conoce como *hipótesis de la guía* y recomienda que la frecuencia de la retroalimentación **disminuya** a medida que aumenta el nivel de habilidad, aunque la tasa óptima de ese desvanecimiento se reconoce como desconocida [3]. Conviene matizar que esta advertencia se ha estudiado sobre todo en tareas simples, y que en tareas complejas y en fases tempranas del aprendizaje la retroalimentación concurrente resulta más prometedora; los ejercicios de bajo impacto y las usuarias principiantes de ESTELA se sitúan del lado favorable de esa distinción, pero no existe ningún estudio que traslade la hipótesis de la guía a sistemas de corrección por cámara y mida retención motora, de modo que se trata de un vacío en la literatura y no de un aval.

De estas consideraciones se deriva un objeto de diseño propio del proyecto: la **política de silencio**. En lugar de tratar el silencio como la ausencia de salida, ESTELA lo trata como una salida de primera clase, con un motivo asociado y contabilizable. La política se articula mediante varios mecanismos: un *periodo refractario* que impone un tiempo mínimo entre dos mensajes cualesquiera y otro, más largo, antes de repetir el mismo error; una *política de evidencia* que exige que el error se observe en un número mínimo de repeticiones consecutivas antes de hablar, lo que traslada la idea de *bandwidth feedback* al eje temporal y evita corregir por un fotograma ruidoso; un *factor de desvanecimiento* que alarga progresivamente el intervalo entre repeticiones del mismo mensaje; un tope de emisiones por sesión; y la posibilidad de silenciar fases enteras del movimiento. Que el sistema hable menos no es una limitación: es un requisito derivado de la evidencia.


### 2.7 Confianza, abstención y el fallo silencioso

El modo de fallo más peligroso de un sistema de retroalimentación por cámara no es un mensaje mal redactado. Es un mensaje **correctamente** redactado, con el segmento y el lado adecuados y un tono competente, emitido sobre una medida que la cámara no podía ver. Un mensaje así es formalmente impecable, y por tanto ningún mecanismo de validación lingüística lo detecta; el usuario, que no tiene forma de saber que la medida era inválida, lo trata como una corrección legítima. Este es el **fallo silencioso**, y la literatura consultada lo documenta en la generación de retroalimentación por modelos de lenguaje: la evaluación de instrucciones generadas automáticamente reporta identificación errónea de la parte del cuerpo en una fracción no trivial de los casos [26], y los benchmarks de comprensión visual centrada en el cuerpo humano muestran que los modelos multimodales de propósito general tienen dificultad sistemática para distinguir izquierda de derecha en manos y pies [27].

La defensa de ESTELA frente a este fallo es un principio de orden: **la abstención se resuelve antes que la detección**. Antes de preguntar «¿está mal esta medida?», el motor pregunta «¿puedo ver esta medida?». La respuesta se construye sobre dos señales. La primera es la **confianza por medida**, un valor entre cero y uno que acompaña obligatoriamente a cada ángulo y cada distancia entregados por el módulo de percepción. Su semántica es deliberadamente pesimista: la confianza de una medida compuesta es el **mínimo** de la visibilidad de los puntos que intervienen en ella, no la media, porque un ángulo de rodilla calculado con el tobillo ocluido no es un ángulo con confianza intermedia, es una medida inválida; y una medida que llega sin confianza declarada se trata como confianza cero, nunca como uno. La segunda señal es la **orientación** del sujeto, que habilita la salvaguarda de plano descrita en 2.3.

Cuando cualquiera de estas comprobaciones falla, el sistema emite un silencio con motivo explícito confianza insuficiente, plano no observable, evidencia insuficiente, periodo refractario, fase silenciada en lugar de una corrección. Esto tiene una consecuencia que conviene subrayar porque convierte una limitación en un instrumento de medición: la frecuencia con que el sistema calla por cada motivo es una **métrica de calidad de la captura**. Una tasa alta de silencios por plano no observable indica que la cámara está mal colocada o que el ejercicio necesita otra orientación; una tasa alta de silencios por confianza baja indica oclusión o iluminación insuficiente. Ninguna de estas dos señales existiría si el sistema se limitara a corregir siempre que detectara una diferencia.


### 2.8 Generación y verbalización de la retroalimentación

Existen al menos cinco enfoques documentados para convertir una desviación numérica en una instrucción comprensible, y conviene distinguirlos porque el proyecto adopta uno y descarta explícitamente otro que figuraba en el planteamiento inicial. El primero es el enfoque **determinista de reglas y plantillas parametrizadas**: la desviación se tipifica mediante reglas y el mensaje se produce rellenando una plantilla de texto redactada de antemano. El segundo es el **clasificador estadístico** entrenado sobre un corpus etiquetado de errores de ejecución. El tercero es el uso de un **modelo de lenguaje** que recibe datos de pose y redacta la instrucción. El cuarto son los **modelos multimodales** (VLM), que reciben directamente fotogramas de la ejecución. El quinto son los **enfoques híbridos**, que separan la detección del error de su verbalización, y que constituyen el patrón dominante en los sistemas verificados de la literatura [6], [26], [29], [30].

Dos hallazgos de esa revisión ordenan la decisión del proyecto. El primero es que **la detección del error, y no la verbalización, es el cuello de botella**: un modelo de lenguaje pequeño alimentado por una detección estructurada supera de forma sustancial, tanto en evaluación automática como humana, a un modelo generalista muy superior en tamaño que trabaja sin esa estructura [26]. La calidad de la retroalimentación no proviene del tamaño del modelo de lenguaje, sino de que la detección sea correcta antes de verbalizar. El segundo es que los modelos multimodales de propósito general **todavía no son fiables para postura fina**: además de la dificultad con izquierda y derecha ya mencionada [27], su desempeño en evaluación de ejecución de ejercicio en condiciones no supervisadas es bajo [28]. Existe además un tercer hallazgo, de signo contrario al intuitivo: entrenar o instruir un modelo únicamente con ejemplos correctivos produce **sobrecorrección**, es decir, señalar errores en ejecuciones que eran correctas, en una proporción que la literatura cuantifica como sustancial [26]. De ahí se deriva un requisito de diseño del banco de evaluación del proyecto: debe incluir obligatoriamente ejecuciones correctas, porque sin ellas la sobrecorrección es invisible.

En consecuencia, ESTELA adopta una arquitectura en la que **el motor determinista decide el contenido y el verbalizador decide únicamente la forma**. El motor produce una estructura tipificada identificador de error, segmento, lado, severidad, fase, repetición, magnitud y confianza que constituye un contrato estable, y el verbalizador recibe esa estructura sin acceso alguno a ángulos ni a imágenes. Por construcción, el verbalizador no puede inventar el contenido: solo puede redactarlo mal. Esta frontera admite dos implementaciones intercambiables: un **verbalizador por plantillas**, determinista y de latencia despreciable, que es la línea base obligatoria y el mecanismo de respaldo permanente del sistema; y un **verbalizador por modelo de lenguaje local pequeño** con **salida restringida** mediante gramáticas formales o esquemas que acotan lo que el modelo puede producir [31] seguido de un **validador determinista** que rechaza todo mensaje que nombre un segmento o un lado distinto del recibido en el contrato, que emplee vocabulario clínico prohibido o que exceda la longitud admitida. Un mensaje rechazado cae automáticamente a la plantilla, de modo que el sistema habla siempre, incluso cuando el componente incierto falla. La comparación entre ambos verbalizadores, manteniendo la detección constante, es el objeto del experimento EXP-001 descrito en la sección 13, y constituye una comparación que no se localizó realizada en la literatura consultada.

El modelo multimodal que el planteamiento inicial situaba dentro del bucle de tiempo real queda, por tanto, **fuera de él**. Esta es una actualización explícita respecto al Informe 1 y se justifica en la evidencia citada: era el componente con peor relación entre evidencia disponible y riesgo asumido, y además el que más acoplaba la arquitectura. Si un modelo multimodal se incorpora en el futuro, será en la fase de construcción offline de la referencia de un ejercicio o como experimento aislado, nunca como dependencia de la retroalimentación en vivo.


### 2.9 Síntesis de voz y ejecución local: latencia y privacidad

La **síntesis de voz** (*text-to-speech*, TTS) es la etapa final de la cadena: convertir el mensaje textual en audio en español. Los conceptos relevantes para evaluar un motor de TTS en este contexto son tres. La **conversión grafema-fonema** (G2P) determina cómo el sistema deduce la pronunciación a partir del texto escrito y es el punto donde el soporte de un idioma se degrada con más frecuencia. El **factor de tiempo real** (RTF) expresa cuántos segundos de cómputo cuesta producir un segundo de audio, y es la métrica que decide si el TTS cabe dentro del presupuesto de latencia del ciclo. Y el **modelo de licenciamiento** de los pesos y del código determina si el componente puede utilizarse en el marco académico del proyecto, cuestión que no siempre coincide entre uno y otro.

La **latencia** merece tratarse como concepto propio y no como un atributo genérico de rendimiento, porque en este sistema no es una molestia sino una condición de validez: una corrección que llega después de que la repetición terminó ya no es retroalimentación concurrente, es retroalimentación terminal, y pertenece a otra categoría pedagógica (2.6). El proyecto la mide por **etapas** percepción, comparación, decisión, verbalización y síntesis y reporta percentiles, no solo promedios: el percentil 95 describe el comportamiento en el peor caso habitual, que es el que el usuario percibe como fallo, mientras que el promedio puede ocultarlo por completo. Como referencia de diseño para los umbrales de percepción de respuesta inmediata en interacción, el proyecto se apoya en los límites clásicos de tiempo de respuesta descritos en la literatura de usabilidad [4].

La **inferencia local** es, por último, una restricción de diseño con doble justificación. Desde el punto de vista técnico, ejecutar todos los modelos en el mismo equipo elimina la latencia de red y la variabilidad asociada a un servicio remoto, y hace que el presupuesto de latencia dependa únicamente de hardware bajo control del proyecto. Desde el punto de vista normativo, la Ley 1581 de 2012 clasifica los datos biométricos como datos sensibles sujetos a un régimen especial de protección [5], y procesar el video durante la sesión sin transmitirlo a terceros ni almacenarlo de forma permanente reduce la exposición de esa información. Ambas justificaciones convergen en la misma decisión, pero son independientes: la primera sobreviviría aunque la segunda no existiera.

**Sobre el motor de síntesis de voz VARIANTE A (abierto):** la selección del motor de TTS permanece abierta al cierre de este informe. Los candidatos considerados se comparan en la sección 9 según soporte real de español, calidad de las voces disponibles, factor de tiempo real medido en el hardware del proyecto y licencia; ninguna de estas cuatro dimensiones puede resolverse con la documentación pública disponible, y en particular no existen cifras publicadas de factor de tiempo real para los candidatos en el hardware del proyecto, por lo que deben medirse.

**Sobre el motor de síntesis de voz VARIANTE B (Piper como candidato principal, TTS aún por confirmar):** el candidato principal es Piper, que ofrece voces en español peninsular y latinoamericano con pesos bajo licencia permisiva [32], y desplaza al candidato inicialmente propuesto en el Informe 1 [18], cuyo soporte de español se limita a un número muy reducido de voces y cuya propia documentación advierte de la posible debilidad del soporte para idiomas distintos del inglés. La confirmación depende de medir el factor de tiempo real y la calidad percibida de la voz en español sobre el hardware del proyecto, mediciones que no existen publicadas. La comparación completa se desarrolla en la sección 9.



### 2.10 La *skill* como unidad de conocimiento por ejercicio

Todo el conocimiento específico de un ejercicio se concentra en una unidad de configuración externa al código que el proyecto denomina **skill**. Una *skill* contiene el identificador del ejercicio, la secuencia de fases del movimiento, la orientación preferida, las medidas requeridas, la política de silencio aplicable y el conjunto de reglas con sus umbrales, severidades, planos, segmentos, lados y prioridades. El principio de diseño es que **añadir un ejercicio sea añadir un archivo**, no modificar el motor. Esto materializa el criterio de extensibilidad declarado en el planteamiento del proyecto y, de forma más inmediata, permite que las decisiones técnicas sobre criterios de ejecución se revisen y ajusten sin tocar la lógica del sistema.

Esta separación tiene además una consecuencia metodológica sobre la honestidad del prototipo. Como los umbrales viven en el archivo de *skill* y no dispersos en el código, cada uno puede llevar anotado el **origen de su valor**: si procede de una calibración con datos propios, de una fuente bibliográfica o de una estimación provisional. En el estado actual del proyecto, todos los umbrales están marcados como provisionales y sin calibrar, y esa marca es visible en el propio archivo de configuración. El cargador de *skills* valida el esquema y falla de forma ruidosa ante un archivo mal formado, en lugar de cargarlo parcialmente: un ejercicio mal definido no se ejecuta a medias.

El cargador impone además dos reglas de higiene que no son arbitrarias. La primera es que el segmento corporal declarado en cada regla debe pertenecer al vocabulario cerrado del sistema, condición que es precisamente la que habilita al validador de salida a rechazar mensajes que nombren otra parte del cuerpo (2.8). La segunda es que las prioridades no pueden repetirse dentro de un mismo ejercicio, porque un empate dejaría el desempate indefinido y el motor perdería el determinismo, que es una garantía explícita del contrato (2.5). Ambas reglas ilustran el mismo patrón de diseño presente en toda la arquitectura: las propiedades que el sistema promete se sostienen en restricciones verificables, no en la disciplina de quien escribe la configuración.


### 2.11 Tabla de términos

| Término | Definición operativa en ESTELA |
|---|---|
| **Keypoint / landmark** | Punto anatómico localizado por el estimador de pose en cada fotograma. |
| **Image landmarks** | Coordenadas del punto en el plano de la imagen, dependientes del encuadre y la distancia. |
| **World landmarks** | Coordenadas métricas 3D con origen en el centro de la cadera, independientes de la posición en el encuadre. |
| **Visibilidad** | Valor asociado a un keypoint que indica la fiabilidad de su localización. |
| **Confianza de una medida** | Valor 0–1 por ángulo o distancia; se define como el **mínimo** de la visibilidad de los keypoints que intervienen. Su ausencia se interpreta como cero. |
| **Ángulo articular** | Ángulo formado por dos segmentos que comparten un vértice, definido sobre una terna ordenada de keypoints. Invariante a traslación y escala. |
| **Distancia normalizada** | Distancia entre dos puntos dividida por una longitud de referencia del propio sujeto (escala corporal). Nunca en píxeles ni en metros absolutos. |
| **Plano frontal / sagital / transversal** | Planos anatómicos que determinan desde qué orientación es observable un criterio técnico. |
| **Orientación** | Ángulo del sujeto respecto a la cámara; 0° de frente, 90° de perfil. Habilita la salvaguarda de plano. |
| **Error de proyección** | Discrepancia entre una magnitud medida en el plano de imagen y su valor tridimensional real, dependiente de la orientación. |
| **Observabilidad monocular** | Condición de que una medida pueda obtenerse con fiabilidad desde una sola cámara en la orientación disponible. |
| **DTW (Dynamic Time Warping)** | Algoritmo de alineamiento temporal no lineal entre dos secuencias de velocidades distintas [15]. |
| **Warping path** | Correspondencia de índices entre la ejecución del usuario y la referencia producida por DTW. |
| **Desviación** | Diferencia entre una medida del usuario y la de la referencia en el instante alineado por DTW. |
| **Fase** | Tramo del ciclo del movimiento (p. ej. descenso, fondo, ascenso) en que se encuentra el usuario. |
| **Repetición** | Ciclo completo del movimiento, delimitado por el segmentador. |
| **Regla** | Asociación declarativa entre una medida, una condición y un umbral, que tipifica un error. |
| **Umbral** | Valor a partir del cual una desviación se considera error. Problema abierto tanto en visión por computador como en aprendizaje motor [3], [6]. |
| **Severidad** | Nivel (leve, moderada, alta) derivado del exceso de la medida sobre el umbral. |
| **Error tipificado** | Estructura de salida del motor de decisión: `{error_id, segmento, lado, severidad, fase, repetición, magnitud, confianza}`. |
| **Retroalimentación aumentada** | Información sobre la ejecución procedente de una fuente externa al aprendiz [3]. |
| **Conocimiento de la ejecución / de resultados** | Retroalimentación sobre *cómo* se hizo el movimiento frente a *qué* se consiguió. |
| **Retroalimentación concurrente / terminal** | Entregada durante el movimiento frente a entregada después de completarlo. |
| **Hipótesis de la guía** | Efecto por el cual la retroalimentación permanente genera dependencia y degrada el rendimiento al retirarla [3]. |
| **Bandwidth feedback** | Estrategia de corregir solo cuando el error supera un margen de tolerancia [3]. |
| **Política de silencio** | Conjunto de mecanismos (refractario, evidencia, desvanecimiento, tope de emisiones, fases silenciadas) que determinan cuándo el sistema no habla. |
| **Abstención** | Decisión de no evaluar una regla por confianza insuficiente o plano no observable. Se resuelve **antes** que la detección. |
| **Fallo silencioso** | Mensaje correctamente formulado emitido sobre una medida no observable; indetectable por validación lingüística. |
| **Sobrecorrección** | Señalar un error en una ejecución que era correcta [26]. |
| **Verbalizador** | Componente que convierte el error tipificado en texto. No accede a ángulos ni imágenes. |
| **Salida restringida** | Limitación formal (gramática o esquema) de lo que un modelo de lenguaje puede generar [31]. |
| **Validador de salida** | Componente determinista que rechaza mensajes incompatibles con el contrato y fuerza la caída a plantilla. |
| **Skill** | Archivo externo que concentra todo el conocimiento de un ejercicio: fases, orientación, reglas, umbrales y política de silencio. |
| **Determinismo** | Garantía de que la misma secuencia de entradas produce la misma secuencia de decisiones. |
| **RTF (factor de tiempo real)** | Segundos de cómputo por segundo de audio sintetizado. |
| **G2P (grafema-fonema)** | Conversión de texto escrito a representación fonética; punto habitual de degradación del soporte por idioma. |
| **Inferencia local** | Ejecución de todos los modelos en el equipo del usuario, sin transmisión a servicios remotos. |

---

## 3. Planteamiento del problema

Define el problema central que aborda el proyecto y su relevancia.

Ver detalle completo en el [Primer Informe](./PrimerInforme.md#2-planteamiento-del-problema).

### 3.1 Descripción del problema

Expone la problemática, sus causas, a quién afecta y sus principales consecuencias.

### 3.2 Restricciones y supuestos de diseño

Indica las limitaciones y condiciones consideradas para el desarrollo de la solución.

### 3.3 Alcance actualizado

Delimita qué incluye y qué no incluye el proyecto en su estado actual, señalando si hubo ajustes respecto al planteamiento inicial.

Ver detalle completo en el [Primer Informe](./PrimerInforme.md#3-alcance-del-proyecto).

## 4. Objetivos

Presenta el objetivo general y los objetivos específicos que orientan el proyecto.

Ver detalle completo en el [Primer Informe](./PrimerInforme.md#4-objetivos).

## 5. Estado del arte / soluciones relacionadas

Resume soluciones o antecedentes relevantes y explica cómo se posiciona la propuesta frente a ellos.

Ver detalle completo en el [Primer Informe](./PrimerInforme.md#6-estado-del-arte--soluciones-relacionadas).

## 6. Solución propuesta

### 6.1 Enfoque general

ESTELA es un prototipo de aplicación de escritorio que observa a una persona a través de una cámara mientras ejecuta un ejercicio físico y le entrega, en español y en tiempo real, retroalimentación hablada sobre su técnica. El sistema no analiza la imagen de un extremo a otro con un único modelo: la organiza como una cadena de cuatro etapas, percibir, comparar, decidir y comunicar, separadas por contratos de datos explícitos, de modo que cada una pueda desarrollarse, medirse y sustituirse sin obligar a rediseñar las demás (subsección 2.1). Esta separación es la decisión arquitectónica central del proyecto: cada frontera entre etapas está especificada con precisión, y esa especificación permite razonar sobre el sistema componente por componente, como hace la sección 9.

En la configuración construida, un estimador de pose (MediaPipe Pose Landmarker [12], [13], [21]) convierte cada fotograma en coordenadas articulares tridimensionales; un mecanismo de comparación temporal alinea esa secuencia con la de un video de referencia procesado una única vez; un motor basado en reglas decide, a partir de las desviaciones observadas, si hay algo que comunicar y en qué momento, siguiendo una política de silencio que prioriza abstenerse antes que corregir sobre una medida incierta (2.6-2.7); y un verbalizador convierte esa decisión en una frase, sintetizada como voz con Piper [32]. Toda la inferencia ocurre en el equipo local: ningún fotograma ni derivado biométrico se transmite a un tercero durante la sesión, lo que responde tanto a una restricción de diseño del proyecto como al tratamiento de los datos biométricos como datos sensibles bajo la Ley 1581 de 2012.

El motor de decisión basado en reglas explícitas es la única etapa que interpreta las desviaciones del movimiento, y su salida, un error tipificado con segmento, lado, severidad y fase, es lo único que recibe el verbalizador, que no accede a ángulos ni a imágenes y por construcción no puede introducir contenido que el motor no haya decidido (sección 2.8). La identificación del ejercicio se resuelve mediante selección explícita de la usuaria a partir de la rutina definida en las skills, de modo que el sistema siempre aplica el conjunto correcto de reglas antes de empezar a observar. Esta combinación, reglas deterministas, verbalización acotada y selección explícita, es la que sostiene, dentro del presupuesto de latencia y de recursos del proyecto, la retroalimentación en tiempo real que define a ESTELA.

### 6.2 Qué se construye

Concretamente, ESTELA es una aplicación de escritorio para un único usuario, pensada para ejecutarse en su equipo sin dependencia de red durante la sesión. El prototipo se valida sobre cuatro ejercicios (elevación de brazos, jumping jacks, marcha con elevación de rodillas y sentadilla), cada uno con sus fases, su orientación preferida y sus reglas de desviación definidas en un archivo de skill independiente (subsección 2.10). Al iniciar una rutina, la persona selecciona el ejercicio desde ese catálogo; el sistema muestra en pantalla una guía visual del movimiento esperado, una representación tipo stick figure derivada del video de referencia, y comienza a observar la ejecución con una sola cámara, para la cual cada ejercicio declara la orientación en que debe colocarse (sección 2.3). Mientras el usuario se mueve, el sistema compara su ejecución contra la referencia, detecta desviaciones relevantes según reglas y umbrales definidos por ejercicio, y decide si corresponde hablar, callar o esperar, de modo que la corrección llegue mientras el movimiento todavía se está ejecutando y no después.

Todo el conocimiento específico de cada ejercicio, fases, orientación esperada, reglas, umbrales y política de silencio, vive en archivos de skill externos al código, lo que permite incorporar ejercicios nuevos sin modificar la lógica del sistema (subsección 2.10). Esta decisión es también la que hace posible que el catálogo de ejercicios crezca sin que el motor de decisión, el verbalizador o el motor de voz tengan que cambiar.

Además de observar y corregir, ESTELA construye un panel de información de la sesión que resume las métricas derivadas de la ejecución, repeticiones detectadas, desviaciones emitidas y motivos de silencio por sesión, de modo que la instrumentación no es un añadido posterior sino parte de lo que se construye desde el inicio (sección 3.3). Este panel cumple una función doble: le da al usuario un cierre visible de la sesión y le da al equipo la evidencia que exige la sección 7.3 para validar el prototipo. La arquitectura está además preparada para degradarse en lugar de detenerse: si una articulación queda ocluida, si el motor de voz falla o si el verbalizador por modelo de lenguaje no llega a tiempo, el sistema sigue observando y recurre a un respaldo determinista antes que interrumpir la sesión (sección 9), de modo que lo que se construye no es solo el camino en el que todo funciona, sino también el comportamiento previsto ante cada fallo parcial.

### 6.3 Usuarios objetivo

ESTELA está dirigido a una usuaria principal: una persona adulta, aproximadamente entre 18 y 40 años, sin experiencia previa en ejercicio estructurado, que inicia una práctica de actividad física por su cuenta y ejecuta los movimientos sin la presencia de un instructor. Es precisamente esta ausencia de acompañamiento, y no la falta de acceso a contenido de ejercicio, que abunda en video y aplicaciones de conteo, la que define al usuario objetivo: alguien que ya sabe qué movimiento debe hacer, pero no cuenta con un mecanismo que le indique, mientras lo hace, si lo está haciendo bien.

Existe además un rol de configuración técnica, correspondiente al equipo de desarrollo, que prepara los recursos de referencia y la definición de cada ejercicio nuevo mediante los archivos de skill. Este rol no participa de la interacción habitual del usuario final: opera antes de la sesión, sobre los recursos que el sistema usará durante ella, y es independiente de cómo la usuaria principal interactúa con el prototipo.

Este perfil de usuario no se eligió por conveniencia técnica, sino porque es ahí donde pesa más el problema descrito en la sección 2: quien empieza a ejercitarse por su cuenta, sin instructor ni comunidad de práctica alrededor, es también quien menos mecanismos tiene para notar cuándo su técnica se aleja de la referencia, y quien más se beneficia de una corrección que llegue mientras el movimiento todavía ocurre. ESTELA no compite con un entrenador personal ni con una plataforma de rehabilitación clínica, ambas explícitamente fuera de su alcance (sección 3.3), sino que atiende el tramo intermedio, hoy desatendido, entre no tener ninguna observación y necesitar supervisión profesional continua.

### 6.4 Propuesta de valor

El vacío que ESTELA cierra es el que se describe en la sección 2: la práctica autónoma de actividad física no ofrece, hoy, un mecanismo que observe la ejecución mientras ocurre y comunique una corrección oportuna, sin depender de un instructor presente ni de enviar video del cuerpo del usuario a un servicio en la nube. Los videos de rutina son unidireccionales, las aplicaciones de conteo automático informan cuántas repeticiones se hicieron pero no cómo, y los sistemas comerciales que sí analizan la ejecución suelen requerir hardware propietario, suscripción o procesamiento remoto.

La propuesta de valor de ESTELA es específica frente a ese panorama: retroalimentación hablada, en español, durante la ejecución y con toda la inferencia corriendo en el equipo local. Esa combinación se sostiene en decisiones concretas de la arquitectura: mantener fuera del bucle de tiempo real cualquier componente que exija una segunda inferencia continua sobre fotogramas, para no competir por los mismos recursos con la estimación de pose; sintetizar la voz con Piper, ejecutado también de forma local, para no depender de un servicio de síntesis en la nube; y aplicar una política de silencio que prefiere callar ante la duda a corregir sobre una medida que la cámara no observó con confianza, de modo que la retroalimentación, cuando se emite, sea una señal en la que la usuaria puede confiar.

La comparación con el estado del arte revisado en este informe refuerza esta propuesta de valor en un punto concreto: los trabajos académicos que analizan la ejecución de ejercicio mediante estimación de pose suelen reportar precisión de clasificación o de detección, pero no declaran un presupuesto de latencia de extremo a extremo como criterio de aceptación, y ninguno combina retroalimentación hablada en español con inferencia completamente local. ESTELA no pretende superar a esos trabajos en exactitud, sino ocupar un punto del espacio de soluciones que ellos no cubren: el de un sistema que se compromete, desde el diseño, a medir cuánto tarda en reaccionar y a no exigir conexión a internet para hacerlo.

### 6.5 Relación con el problema y el alcance definidos

La solución responde de manera directa a las tres causas del problema descritas en la sección 2: la ausencia de un observador durante la práctica autónoma se resuelve con la cámara y el estimador de pose corriendo de forma continua durante la sesión; el carácter unidireccional del contenido digital de ejercicio se resuelve con el ciclo completo de comparación, decisión y comunicación, que sí recibe y responde a la ejecución del usuario; y la demora entre el error y su corrección se resuelve por diseño, al emitir la retroalimentación mientras el movimiento todavía ocurre, en vez de al final de la sesión.

La solución construida respeta, sin ampliarlo ni reducirlo, el alcance fijado en la sección 3.3. Se trata de un prototipo para un único usuario, validado sobre un conjunto delimitado de cuatro ejercicios de complejidad controlada, con la precisión de la comparación de movimiento y la latencia por etapa como criterios de aceptación medidos y no como subproducto. La sección 9 documenta, componente por componente, la evidencia que sostiene esa arquitectura dentro del mismo alcance y del mismo presupuesto de tiempo, y deja señaladas las validaciones que todavía faltan antes de dar por cerrada cada decisión.

La relación con el alcance es, además, una relación de exclusión deliberada: ESTELA no ofrece diagnóstico médico ni rehabilitación clínica, no atiende a varios usuarios a la vez y no depende de la nube para funcionar durante la sesión. Cada una de esas exclusiones simplifica un problema que, sin ellas, sería demasiado amplio para resolverse con la evidencia y el tiempo disponibles en el semestre, y es lo que permite afirmar que la solución construida responde exactamente al problema y al alcance que este informe define, y no a uno más ambicioso ni a uno distinto.

## 7. Metodología de desarrollo

Describe el enfoque metodológico seguido durante el proyecto, las iteraciones realizadas, las validaciones ejecutadas y los ajustes introducidos a partir de los hallazgos obtenidos.

Ver detalle completo en el [Primer Informe](./PrimerInforme.md#7-metodología-de-desarrollo-y-plan-de-trabajo).

## 8. Requerimientos

Presenta los requerimientos que guían el desarrollo de la solución.

### 8.1 Funcionales

Describe las funcionalidades y comportamientos que el sistema debe ofrecer.

### 8.2 No funcionales

Define atributos de calidad y restricciones del sistema, como rendimiento, seguridad, usabilidad, mantenibilidad o escalabilidad.

## 9. Evaluación de alternativas

ESTELA es una aplicación de escritorio de inferencia local para un único usuario por sesión, así que cada criterio se interpreta bajo esos términos, en lugar de los de un sistema cliente-servidor con múltiples usuarios conectados.

### ¿Cuál alternativa ofrece mejor desempeño bajo la carga esperada?

Como ESTELA no tiene usuarios concurrentes, su carga real es el flujo continuo de imágenes de la cámara durante una sesión (30-60 por segundo) junto con varios modelos ejecutándose al mismo tiempo sobre el mismo equipo. Por eso el desempeño se evalúa en esos términos: tiempo por etapa en promedio y en el peor caso (percepción, comparación, decisión, redacción del feedback y síntesis de voz; sección 2.9), fotogramas por segundo que el detector de pose sostiene sin acumular retraso, y cuánto se degrada esa latencia cuando los módulos compiten por el procesador, en lugar de por número de usuarios.

RTMPose reporta más de 90 cuadros por segundo en un procesador de consumo [14], una cifra favorable en aislamiento. Sin embargo, se adopta MediaPipe Pose Landmarker, diseñado para ejecutarse en el propio dispositivo compartiendo recursos con otros procesos [12], [13], y que entrega de fábrica las coordenadas tridimensionales del cuerpo y un valor de visibilidad por articulación que el resto del sistema exige como parte de su contrato de datos (secciones 2.1, 2.7). La latencia máxima y la tasa de fotogramas bajo ejecución simultánea con el resto del pipeline quedan pendientes de medición propia.

En el motor de voz, el desempeño se mide por el tiempo de cómputo por segundo de audio generado; ni Kokoro ni Piper tienen esa cifra publicada para el hardware del proyecto (sección 2.9), por lo que la elección permanece abierta hasta medirla (sección 13).

Sobre la comparación temporal, DTW en su forma clásica no restringe el camino de alineamiento, lo que maximiza su flexibilidad a costa de un coste computacional cuadrático en la longitud de las secuencias. Las variantes acotadas reducen ese coste limitando cuánto puede desviarse el camino de alineamiento, a costa de asumir un desfase limitado entre usuario y referencia; las variantes aproximadas, como FastDTW, sacrifican la garantía de optimalidad a cambio de menor complejidad. Como ESTELA compara solo la repetición en curso y no sesiones completas (sección 2.4), el tamaño real de las secuencias es pequeño, lo que reduce la ventaja teórica de las variantes aproximadas. La elección entre la forma clásica y una variante acotada queda igualmente pendiente de medición (sección 13).

### ¿Qué grado de acoplamiento introduce cada opción?

Dado que el sistema no depende de ningún servicio en la nube por decisión de diseño, la dependencia de servicios externos que se evalúa aquí no corresponde a plataformas de terceros, sino a si una alternativa requiere un proceso de inferencia aparte, ejecutándose en paralelo al programa principal. Sobre esa misma base se compara qué tanto se afectan entre sí los distintos módulos y qué tan fácil resultaría sustituir uno por otro.

El generador de mensajes preescritos no depende de ningún proceso externo: es una función determinista que vive dentro del mismo proceso, con un nivel de dependencia mínimo. El generador basado en un modelo de lenguaje sí introduce una dependencia real, un motor de inferencia que corre aparte y se expone mediante una conexión local, lo que representa un punto adicional de posible falla que la opción determinista no tiene. En cuanto a la interdependencia entre módulos, ambas opciones se comportan de forma equivalente, porque el generador de mensajes solo recibe una estructura ya resumida del error (segmento corporal, lado, severidad y fase del movimiento) sin acceso directo a los ángulos ni a las imágenes (sección 2.8). Esa misma forma de comunicación entre módulos es lo que permite sustituir una implementación por otra sin modificar el motor de decisión ni el módulo de percepción. Por esta razón, se adopta la opción determinista como base obligatoria, mientras que el generador basado en modelo de lenguaje se mantiene como alternativa intercambiable que respeta el mismo contrato, no como su reemplazo.

### ¿Qué nivel de disponibilidad y tolerancia a fallos ofrece cada alternativa?

Al no existir un servidor que deba mantenerse disponible de forma continua, lo relevante aquí es si ESTELA logra completar una sesión entregando retroalimentación válida incluso cuando algún componente falla o produce un resultado poco confiable, más que un porcentaje de tiempo en operación.

El generador de mensajes preescritos tiene un modo de fallo mucho más acotado que el basado en modelo de lenguaje: al limitarse a completar una estructura fija con datos ya validados, el margen de error se reduce prácticamente al de un fallo de programación, no al de una generación de contenido impredecible. El generador basado en modelo de lenguaje sí puede fallar de forma propia de su naturaleza, nombrando un segmento corporal o un lado incorrecto, excediendo la longitud permitida, o empleando vocabulario no autorizado, y frente a ese tipo específico de fallo, en lugar de depender de reintentos o redundancia, su mecanismo de recuperación consiste en un validador determinista que revisa el mensaje y, si no cumple las condiciones establecidas, lo descarta y recurre a la opción preescrita correspondiente (sección 2.8). Esta cobertura, sin embargo, es explícita solo para fallos de contenido: el comportamiento del sistema ante un fallo total del proceso de inferencia, por ejemplo, si el motor de lenguaje no responde dentro del presupuesto de latencia o el proceso deja de estar disponible, no está aún especificado, y queda como validación pendiente.

De manera análoga, cuando el sistema no cuenta con suficiente confianza sobre una medida de entrada, sea por una articulación ocluida o por una orientación de la cámara incompatible con la regla que se quiere evaluar, responde con silencio en lugar de emitir una corrección sobre datos poco confiables (sección 2.7). Este mecanismo cubre un tipo de fallo distinto al del verbalizador: no es que el componente que genera el mensaje falle, sino que la información que recibiría no es lo bastante confiable para actuar sobre ella, y el sistema lo trata igual, absteniéndose en vez de arriesgar una afirmación.

Toda la arquitectura privilegia este tipo de manejo controlado de errores por encima de mecanismos clásicos de redundancia, porque el fallo que más compromete a ESTELA no es que el sistema se detenga, sino que comunique una corrección incorrecta con apariencia de certeza, lo que la sección 2.7 define como fallo silencioso. La caída a la opción preescrita y la abstención por baja confianza son los dos mecanismos con los que el proyecto contiene ese riesgo antes de que llegue al usuario, cada uno frente a un tipo de fallo distinto y ya especificado; su cobertura frente a un fallo de disponibilidad del propio proceso de inferencia, en cambio, no se ha definido todavía y se documenta como pendiente.

## 10. Diseño y arquitectura

Explica cómo se estructura la solución a nivel conceptual y técnico.

### 10.1 Descripción general de la arquitectura

**Objetivo:** que el lector entienda cómo está pensado el sistema antes de ver cualquier representación visual.

Debe incluir:

- Tipo de arquitectura (cliente-servidor, basada en Backend as a Service, etc.).
- Enfoque general de la solución.
- Relación con la alternativa seleccionada previamente.

### 10.2 Componentes del sistema

Deben identificarse y explicarse:

- **Componentes principales** del sistema (frontend, backend, base de datos, servicios externos).
- **Responsabilidad** de cada uno.
- **Relación con los requerimientos** del sistema.

Esta parte debe terminar con el **diagrama de arquitectura del sistema**.

### 10.3 Interacción entre módulos

Debe explicarse:

- Cómo se comunican los componentes.
- Flujos de datos.
- Dependencias.
- Nivel de acoplamiento.

Esta parte debe terminar con el **diagrama de interacción entre módulos**.

### 10.4 Comportamiento

Debe explicarse cómo se comportan los componentes, describiendo las principales secuencias de la arquitectura y respondiendo preguntas como:

- ¿El flujo es eficiente? (latencia, pasos innecesarios).
- ¿Existen cuellos de botella?
- ¿La interacción refleja buen desacoplamiento?

En esta parte se utilizan **diagramas de secuencia**.

## 11. Implementación y avance actual

Documenta el estado real de construcción del sistema y el grado de avance alcanzado.

### 11.1 Stack tecnológico

Lista y justifica las tecnologías, frameworks, librerías y herramientas utilizadas.

### 11.2 Componentes implementados

Describe qué módulos o componentes ya fueron construidos, qué funcionalidades cubren y cuál es su estado actual.

### 11.3 Integraciones realizadas

Explica las integraciones ya desarrolladas con servicios externos, bases de datos, autenticación u otros componentes.

### 11.4 Pendientes para la entrega final

Indica qué elementos faltan por implementar, integrar, corregir o validar antes del cierre del proyecto.

## 12. Despliegue y operación preliminar

Describe cómo se ejecuta actualmente la solución, en qué entorno funciona, qué dependencias requiere y cuál es su estado de despliegue o configuración.

## 13. Validación preliminar

Presenta las pruebas o validaciones realizadas hasta el momento para verificar el comportamiento del sistema y su grado de cumplimiento frente a los requerimientos.

### 13.1 Pruebas por componentes

### 13.2 Pruebas de integración

### 13.3 Pruebas de usabilidad

## 14. Resultados parciales y discusión

Presenta los principales hallazgos obtenidos hasta el momento, interpreta su significado y analiza el nivel de avance del proyecto frente a los objetivos planteados.

## 15. Plan de cierre hacia la entrega final

Describe las actividades restantes, prioridades, riesgos y estrategia de cierre para completar el proyecto en las semanas finales.

## 16. Referencias

Incluye las fuentes consultadas y citadas en el documento.

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

[26] W.-H. Yeh *et al.*, "CoachMe: Decoding sport elements with a reference-based coaching instruction generation model," arXiv:2509.11698v1, sep. 2025. *(El documento consultado no declara venue; verificar antes de citarlo como publicado.)*

[27] Y. Liu *et al.*, "Human-MME: A holistic evaluation benchmark for human-centric multimodal LLMs," arXiv:2509.26165, sep. 2025.

[28] Qualcomm AI Research y TwentyBN, "What to say and when to say it: Live fitness coaching as a testbed for situated interaction," arXiv:2407.08101. *(Conjunto de datos QEVD. La lista nominal de autores no pudo extraerse del documento consultado; verificar antes de la entrega final.)*

[29] C. Wang *et al.*, "UbiPhysio: Support daily functioning, fitness, and rehabilitation with action understanding and feedback in natural language," *Proc. ACM IMWUT*, 2024, arXiv:2308.10526v3.

[30] G. Delmas, P. Weinzaepfel, F. Moreno-Noguer y G. Rogez, "PoseFix: Correcting 3D human poses with natural language," arXiv:2309.08480. *(Venue no declarado en el documento consultado.)*

[31] ggml-org, "GBNF grammars" (`grammars/README.md`) y "LLaMA.cpp HTTP server" (`tools/server/README.md`), *llama.cpp*, GitHub. [En línea]. Disponible: https://github.com/ggml-org/llama.cpp

[32] OHF-Voice, "Voices", *piper1-gpl*, GitHub; pesos de voz bajo licencia MIT en `rhasspy/piper-voices`. [En línea]. Disponible: https://github.com/OHF-Voice/piper1-gpl 

