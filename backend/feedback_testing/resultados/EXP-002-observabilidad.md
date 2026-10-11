# EXP-002 — Observabilidad monocular por orientación

- Poses sintéticas: 5 (de_pie, sentadilla_fondo, brazos_arriba, rodilla_izq_arriba, jumping_jack_abierto)
- Orientaciones: 0° a 90° en pasos de 5°
- Verdad de referencia: la misma medida calculada en 3D.
- Medida observada: proyección ortográfica al plano de imagen (peor caso, sin profundidad utilizable).

## Error absoluto máximo sobre todas las poses

| Medida | Plano declarado | 0° | 15° | 30° | 45° | 60° | 75° | 90° |
|---|---|---|---|---|---|---|---|---|
| `rodilla_izq` | sagital | 79.1 | 66.1 | 41.6 | 23.1 | 10.6 | 3.2 | 2.5 |
| `rodilla_der` | sagital | 79.1 | 52.5 | 31.0 | 15.8 | 6.1 | 1.9 | 2.5 |
| `cadera_izq` | sagital | 59.8 | 64.0 | 42.9 | 25.8 | 13.3 | 17.9 | 24.3 |
| `cadera_der` | sagital | 59.8 | 38.6 | 21.9 | 10.1 | 12.0 | 17.9 | 24.3 |
| `codo_izq` | sagital | 16.2 | 9.7 | 5.3 | 6.2 | 7.2 | 12.4 | 18.7 |
| `codo_der` | sagital | 16.2 | 15.4 | 10.3 | 6.5 | 7.2 | 12.4 | 18.7 |
| `hombro_izq` | frontal | 31.0 | 44.6 | 42.7 | 29.3 | 17.8 | 20.2 | 29.6 |
| `hombro_der` | frontal | 31.0 | 23.0 | 32.5 | 25.8 | 17.5 | 20.2 | 29.6 |
| `tronco_inclinacion` | sagital | 27.6 | 19.9 | 13.0 | 7.3 | 3.2 | 0.8 | 0.0 |
| `valgo_rodilla_izq` | frontal | 0.005 | 0.173 | 0.335 | 0.467 | 0.563 | 0.624 | 0.652 |
| `valgo_rodilla_der` | frontal | 0.005 | 0.180 | 0.331 | 0.446 | 0.522 | 0.562 | 0.567 |
| `separacion_pies` | frontal | 0.000 | 0.402 | 0.866 | 0.600 | 0.498 | 3.498 | n/c |

Los ángulos están en grados; `valgo_*` y `separacion_pies` en unidades normalizadas por la escala corporal.

## Orientación máxima utilizable por regla

Para cada regla: hasta qué desviación respecto a su plano ideal el error de proyección se mantiene por debajo del umbral de severidad «moderada» de esa regla. Más allá, un error de medida es indistinguible de un error de ejecución.

Cada regla se evalúa **solo sobre las poses de su ejercicio** (ver `POSES_POR_EJERCICIO`).

| Ejercicio | Regla | Medida | Plano | Umbral moderada | Orientación máx. utilizable |
|---|---|---|---|---|---|
| elevacion_brazos | `rango_brazos_insuficiente` | `hombro_medio` | frontal | 15.000 | ±75° alrededor de 0° |
| elevacion_brazos | `codos_flexionados` | `codo_medio` | sagital | 20.000 | cualquiera |
| elevacion_brazos | `asimetria_brazos` | `hombro_izq` | frontal | 10 | ±60° alrededor de 0° |
| elevacion_brazos | `brazo_izq_bajo` | `hombro_izq` | frontal | 10 | ±60° alrededor de 0° |
| elevacion_brazos | `brazo_der_bajo` | `hombro_der` | frontal | 10 | ±60° alrededor de 0° |
| jumping_jacks | `brazos_no_llegan_arriba` | `hombro_medio` | frontal | 20.000 | ±70° alrededor de 0° |
| jumping_jacks | `apertura_pies_insuficiente` | `separacion_pies` | frontal | 0.300 | ±85° alrededor de 0° |
| jumping_jacks | `codos_flexionados` | `codo_medio` | sagital | 20.000 | cualquiera |
| marcha_rodillas | `tronco_muy_inclinado` | `tronco_inclinacion` | sagital | 8 | cualquiera |
| marcha_rodillas | `rodilla_izq_baja` | `cadera_izq` | sagital | 15 | ±65° alrededor de 90° |
| marcha_rodillas | `rodilla_der_baja` | `cadera_der` | sagital | 15 | cualquiera |
| rotacion_tronco | `rotacion_insuficiente` | `rotacion_tronco` | transversal | — | no medible aquí |
| rotacion_tronco | `cadera_acompana` | `azimut_cadera` | transversal | — | no medible aquí |
| sentadilla | `tronco_muy_inclinado` | `tronco_inclinacion` | sagital | 10 | ±50° alrededor de 90° |
| sentadilla | `valgo_rodilla_izq` | `valgo_rodilla_izq` | frontal | 0.060 | ±5° alrededor de 0° |
| sentadilla | `valgo_rodilla_der` | `valgo_rodilla_der` | frontal | 0.060 | ±0° alrededor de 0° |
| sentadilla | `profundidad_insuficiente` | `rodilla_media` | sagital | 15.000 | ±35° alrededor de 90° |
| sentadilla | `asimetria_rodillas` | `rodilla_izq` | sagital | 10 | ±25° alrededor de 90° |
| sentadilla | `pies_muy_juntos` | `separacion_pies` | frontal | 0.200 | ±85° alrededor de 0° |

## ¿Existe una sola orientación que sirva para todo el ejercicio?

Para cada ejercicio se busca el conjunto de orientaciones en las que **todas** sus reglas medibles se mantienen por debajo de su umbral. Un conjunto vacío significa que una sola cámara fija no puede cubrir ese ejercicio completo.

| Ejercicio | Reglas medibles | Orientaciones válidas para todas | Reglas que se pierden en la mejor orientación |
|---|---|---|---|
| elevacion_brazos | 5 / 5 | 0°–60° | (a 0°) ninguna |
| jumping_jacks | 3 / 3 | 0°–70° | (a 0°) ninguna |
| marcha_rodillas | 3 / 3 | 25°–90° | (a 25°) ninguna |
| rotacion_tronco | 0 | — | todas |
| sentadilla | 6 / 6 | ninguna | (a 65°) `valgo_rodilla_izq`, `valgo_rodilla_der` |

## Lectura

- La columna de la derecha es, literalmente, el valor que debería tener `tolerancia_orientacion_grados` en la política de silencio de cada `skill`. Hoy ese valor está puesto a 30° por defecto en todos los archivos, sin respaldo.
- Las medidas del plano **transversal** (`rotacion_tronco`, `azimut_cadera`) no aparecen: no se pueden calcular sin profundidad. Con una sola cámara dependen por completo de la `z` estimada, y la salvaguarda de plano del motor **no las protege**.
- Cuatro de los cinco ejercicios admiten una orientación única que cubre todas sus reglas. La sentadilla no: sus reglas del plano frontal (valgo) y las del sagital (profundidad, tronco) no comparten ninguna orientación válida.
- El ancho de la ventana válida depende del umbral de la regla, y los umbrales de hoy son provisionales. Recalcular este experimento es obligatorio después de calibrarlos.

