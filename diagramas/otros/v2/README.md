# Diagramas v2

Versión actualizada de `diagramas/` (los originales no se modificaron), contrastada con el código de `test` y de `feature/reconocimiento-ejercicio` (reconocimiento del ejercicio, EXP-010). Fuente en PlantUML (`.wsd`); imágenes generadas con PlantUML 1.2025.4 y Graphviz 15.1.

Cada diagrama tiene una versión completa para el informe (esta carpeta, imágenes en `img/`) y una versión corta para diapositivas (`diapositivas/`, imágenes en `diapositivas/img/`). El nombre empieza por el tipo de diagrama.

| Sección del informe | Informe | Diapositivas | Leyenda breve propuesta |
| --- | --- | --- | --- |
| §10.2 | `ARQUITECTURA_sistema` | `ARQUITECTURA_sistema_corto` | Actores, componentes principales y servicios de terceros. Todo se ejecuta en el equipo de la usuaria; la preparación de referencias es offline. |
| §10.3 | `INTERACCION_modulos` | `INTERACCION_modulos_corto` | Componentes de cada capa (adaptadores, aplicación, dominio), sus puertos y las tecnologías externas que usa cada adaptador. |
| §10.3 (complementaria) | `DEPENDENCIAS_modulos` | — | Importaciones reales entre módulos de `backend/estela`; todas apuntan hacia el dominio. |
| §10.4 | `SECUENCIA_flujo_por_fotograma` | `SECUENCIA_flujo_por_fotograma_corto` | Procesamiento de un fotograma: pose, medidas, conteo, DTW, reconocimiento, pausa, decisión y voz. |
| §10.4 | `SECUENCIA_sesion_desde_interfaz` | `SECUENCIA_sesion_desde_interfaz_corto` | Inicio de la sesión desde la interfaz, sondeo largo del estado, comandos de la usuaria y cierre con el resumen. |
| §12 | `DESPLIEGUE_sistema` | `DESPLIEGUE_sistema_corto` | Dónde se ejecuta cada componente en el computador de la usuaria y cómo se conectan. |

`descartados/` guarda versiones que no se usan: el verbalizador con LLM (`fallback-llm`), la secuencia detallada del fotograma y la primera versión del diagrama de interacción entre módulos.

Para regenerar las imágenes (con Graphviz instalado), desde esta carpeta:

```bash
java -jar plantuml.jar -charset UTF-8 -tpng -o img *.wsd
java -jar plantuml.jar -charset UTF-8 -tsvg -o img *.wsd
java -jar plantuml.jar -charset UTF-8 -tpng -o img diapositivas/*.wsd
java -jar plantuml.jar -charset UTF-8 -tsvg -o img diapositivas/*.wsd
```
