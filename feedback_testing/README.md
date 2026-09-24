# `feedback_testing` — banco sintético y experimentos

Arnés para medir el módulo `feedback/` **antes** de que exista una sola grabación. Depende de `feedback/`; no al revés.

## Lo primero: qué se puede y qué no se puede concluir de aquí

El banco genera directamente las *medidas* que el motor consume, colocadas al lado correcto del umbral de cada regla. **No simula biomecánica humana.** Un episodio «con valgo de rodilla» es un número, no un valgo.

| Se mide aquí | No se mide aquí |
|---|---|
| Determinismo del motor | Si los umbrales son correctos |
| Tasa de sobrecorrección en ejecuciones correctas | Exactitud de contenido sobre vídeo real (M1 de ADR-001) |
| Aserciones no soportadas en el mensaje | Naturalidad percibida (M6) |
| Latencia de decisión y verbalización | Latencia en el hardware del proyecto |
| Abstención por oclusión y por plano | Oclusión real por equipamiento |
| Coherencia entre el error inducido y el señalado | Si el error se parece a lo que hace una persona |

La M1 real de EXP-001 exige el banco grabado de 60–100 episodios con etiquetado manual de ADR-001 §5. Esto no lo sustituye: lo precede, para llegar a esa grabación con el motor ya depurado y con el arnés de métricas ya escrito.

## Contenido

| Archivo | Qué es |
|---|---|
| `generador_episodios.py` | Construye el banco. Completamente determinista, sin aleatoriedad. |
| `metricas.py` | M1\*, M2, M3, M4, M5, M7 y abstención, como funciones puras. |
| `runner.py` | Ejecuta una condición de verbalizador sobre el banco y emite el informe. |
| `exp002_observabilidad.py` | EXP-002: error de la medida monocular según la orientación del sujeto. |
| `resultados/` | Informes generados. Se regeneran con los comandos de abajo. |
| `tests/` | Pruebas del propio arnés. |

## Cómo correrlo

```bash
python3 -m unittest discover -s feedback_testing/tests -t .

# EXP-001, condición A (plantillas). No necesita nada instalado.
python3 -m feedback_testing.runner --salida feedback_testing/resultados/EXP-001-piloto-A.md

# EXP-001, condición F (LLM local). Requiere llama-server en 127.0.0.1:8080.
python3 -m feedback_testing.runner --condicion F  --salida feedback_testing/resultados/EXP-001-piloto-F.md
python3 -m feedback_testing.runner --condicion Fp --salida feedback_testing/resultados/EXP-001-piloto-Fp.md

# EXP-002
python3 -m feedback_testing.exp002_observabilidad
```

Las condiciones **F** y **F′** no se han ejecutado nunca: no hay ningún modelo disponible en el entorno donde se escribió esto. El código está, las cifras no.

## Composición del banco

Por cada regla de cada `skill`:

- 3 episodios con el error inducido (severidad leve, moderada, alta) → el sistema **debe** hablar y señalar ese error;
- 1 episodio con el error presente pero la medida ocluida (confianza 0,25) → el sistema **debe** callar;
- 1 episodio con el error presente y el sujeto orientado en el plano equivocado → el sistema **debe** callar (solo para reglas de plano frontal o sagital; las del transversal no tienen orientación válida con una cámara).

Y por cada `skill`, 3 ejecuciones **correctas**. Su inclusión no es opcional: es lo único que mide la sobrecorrección, y es exactamente el sesgo que hundió a CoachMe (30,4 % según ADR-001 §2.3).

Cada episodio son 8 repeticiones × 6 frames = 48 observaciones, 24 s nominales.
