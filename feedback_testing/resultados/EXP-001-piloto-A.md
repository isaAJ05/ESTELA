# EXP-001 piloto — condición A (banco sintético)

- Episodios: **108**
- Observaciones por episodio: 48 (8 repeticiones x 6 frames)
- Duración nominal de un episodio: 24 s
- Repeticiones para M5: 10

## Métricas

| # | Métrica | Valor | n |
|---|---|---|---|
| M1* | Coherencia detector-referencia (sintética) | 100.0 % | 57 |
| M2 | Aserciones no soportadas | 0.0 % | 114 mensajes |
| M3 | Sobrecorrección en ejecuciones correctas | 0.0 % | 15 |
| M5 | Determinismo | 100.0 % | 108 |
| M7 | Caída a fallback | 0.0 % | 114 mensajes |
| — | Abstención con medida ocluida | 100.0 % | 19 |
| — | Abstención con plano no observable | 100.0 % | 17 |
| — | Mensajes por minuto de ejercicio | 2.64 | — |

**M1\*** no es la M1 de ADR-001 §5: mide coherencia del motor sobre entrada sintética, no exactitud de contenido sobre vídeo real.

## M4 — latencia por etapa (ms)

| Etapa | p50 | p95 | máx | n |
|---|---|---|---|---|
| Decisión | 0.0041 | 0.0117 | 0.0858 | 5184 |
| Verbalización | 0.0711 | 0.1063 | 0.2983 | 114 |

Medido en el entorno de desarrollo, no en el hardware del proyecto. No sustituye la medición en el M2 Ultra. No incluye pose, DTW ni TTS.

## Motivos de silencio

| Motivo | Veces |
|---|---|
| `sin_error` | 3832 |
| `plano_no_observable` | 752 |
| `periodo_refractario` | 351 |
| `evidencia_insuficiente` | 111 |
| `confianza_baja` | 24 |

## Muestra de mensajes emitidos

- `elevacion_brazos` / `rango_brazos_insuficiente` / leve -> «Sube un poco más los brazos.»
- `elevacion_brazos` / `rango_brazos_insuficiente` / moderada -> «Sube más los brazos.»
- `elevacion_brazos` / `rango_brazos_insuficiente` / alta -> «Sube mucho más los brazos, te estás quedando corta.»
- `elevacion_brazos` / `codos_flexionados` / leve -> «Estira un poco más los codos.»
- `elevacion_brazos` / `codos_flexionados` / moderada -> «Estira los codos.»
- `elevacion_brazos` / `codos_flexionados` / alta -> «Estira bien los codos, los tienes muy doblados.»
- `elevacion_brazos` / `asimetria_brazos` / leve -> «Iguala la altura de los dos brazos.»
- `elevacion_brazos` / `asimetria_brazos` / moderada -> «Sube los dos brazos a la misma altura.»
- `elevacion_brazos` / `asimetria_brazos` / alta -> «Los brazos están muy desiguales, súbelos parejos.»
- `elevacion_brazos` / `brazo_izq_bajo` / leve -> «Sube un poco más el brazo izquierdo.»
- `elevacion_brazos` / `brazo_izq_bajo` / moderada -> «Sube más el brazo izquierdo.»
- `elevacion_brazos` / `brazo_izq_bajo` / alta -> «Sube bien el brazo izquierdo, está mucho más bajo.»
- `elevacion_brazos` / `brazo_der_bajo` / leve -> «Sube un poco más el brazo derecho.»
- `elevacion_brazos` / `brazo_der_bajo` / moderada -> «Sube más el brazo derecho.»
- `elevacion_brazos` / `brazo_der_bajo` / alta -> «Sube bien el brazo derecho, está mucho más bajo.»
- `jumping_jacks` / `brazos_no_llegan_arriba` / leve -> «Sube un poco más los brazos.»
- `jumping_jacks` / `brazos_no_llegan_arriba` / moderada -> «Te falta recorrido, eleva más los brazos.»
- `jumping_jacks` / `brazos_no_llegan_arriba` / alta -> «Sube mucho más los brazos, te estás quedando corta.»
- `jumping_jacks` / `apertura_pies_insuficiente` / leve -> «Abre un poco más los pies al saltar.»
- `jumping_jacks` / `apertura_pies_insuficiente` / moderada -> «Abre más los pies en cada salto.»
- `jumping_jacks` / `apertura_pies_insuficiente` / alta -> «Abre mucho más los pies, casi no te separas.»
- `marcha_rodillas` / `tronco_muy_inclinado` / leve -> «Sube un poco el pecho.»
- `marcha_rodillas` / `tronco_muy_inclinado` / moderada -> «Mantén el tronco más vertical.»
- `marcha_rodillas` / `tronco_muy_inclinado` / alta -> «Endereza bien el tronco, te estás yendo hacia delante.»
- `marcha_rodillas` / `rodilla_izq_baja` / leve -> «Sube un poco más la rodilla izquierda.»
- `marcha_rodillas` / `rodilla_izq_baja` / moderada -> «Eleva más la rodilla izquierda en cada paso.»
- `marcha_rodillas` / `rodilla_izq_baja` / alta -> «Sube bien la rodilla izquierda, apenas la estás levantando.»
- `marcha_rodillas` / `rodilla_der_baja` / leve -> «Sube un poco más la rodilla derecha.»
- `marcha_rodillas` / `rodilla_der_baja` / moderada -> «Eleva más la rodilla derecha en cada paso.»
- `marcha_rodillas` / `rodilla_der_baja` / alta -> «Sube bien la rodilla derecha, apenas la estás levantando.»
- `rotacion_tronco` / `rotacion_insuficiente` / leve -> «Gira un poco más el tronco.»
- `rotacion_tronco` / `rotacion_insuficiente` / moderada -> «Gira más el tronco en cada lado.»
- `rotacion_tronco` / `rotacion_insuficiente` / alta -> «Gira mucho más el tronco, casi no rotas.»
- `rotacion_tronco` / `cadera_acompana` / leve -> «Mantén las caderas un poco más quietas.»
- `rotacion_tronco` / `cadera_acompana` / moderada -> «Mantén las caderas fijas mientras giras.»
- `rotacion_tronco` / `cadera_acompana` / alta -> «No muevas las caderas, el giro es solo de arriba.»
- `sentadilla` / `valgo_rodilla_izq` / leve -> «Abre un poco la rodilla izquierda.»
- `sentadilla` / `valgo_rodilla_izq` / moderada -> «Abre la rodilla izquierda hacia fuera.»
- `sentadilla` / `valgo_rodilla_izq` / alta -> «Abre bien la rodilla izquierda, se está metiendo hacia dentro.»
- `sentadilla` / `valgo_rodilla_der` / leve -> «Abre un poco la rodilla derecha.»
- `sentadilla` / `valgo_rodilla_der` / moderada -> «Abre la rodilla derecha hacia fuera.»
- `sentadilla` / `valgo_rodilla_der` / alta -> «Abre bien la rodilla derecha, se está metiendo hacia dentro.»
- `sentadilla` / `profundidad_insuficiente` / leve -> «Baja un poco más las rodillas.»
- `sentadilla` / `profundidad_insuficiente` / moderada -> «Baja más, flexiona bien las rodillas.»
- `sentadilla` / `profundidad_insuficiente` / alta -> «Baja mucho más, flexiona las rodillas hasta el fondo.»
- `sentadilla` / `asimetria_rodillas` / leve -> «Reparte el peso entre las dos rodillas.»
- `sentadilla` / `asimetria_rodillas` / moderada -> «Flexiona las dos rodillas por igual.»
- `sentadilla` / `asimetria_rodillas` / alta -> «Estás cargando un lado, iguala las dos rodillas.»
- `sentadilla` / `pies_muy_juntos` / leve -> «Separa un poco los pies.»
- `sentadilla` / `pies_muy_juntos` / moderada -> «Abre más los pies.»
- `sentadilla` / `pies_muy_juntos` / alta -> «Abre bien los pies, los tienes muy juntos.»

