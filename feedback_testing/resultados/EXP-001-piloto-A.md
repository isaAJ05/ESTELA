# EXP-001 piloto — condición A (banco sintético)

- Episodios: **116**
- Observaciones por episodio: 48 (8 repeticiones x 6 frames)
- Duración nominal de un episodio: 24 s
- Repeticiones para M5: 10

## Métricas

| # | Métrica | Valor | n |
|---|---|---|---|
| M1* | Coherencia detector-referencia (sintética) | 100.0 % | 57 |
| M2 | Aserciones no soportadas | 0.0 % | 114 mensajes |
| M3 | Sobrecorrección en ejecuciones correctas | 0.0 % | 21 |
| M5 | Determinismo | 100.0 % | 116 |
| M7 | Caída a fallback | 0.0 % | 135 mensajes |
| M8 | Refuerzo indebido: elogio con un error inducido y observable | 0.0 % | 57 |
| M8′ | Elogio con un error presente pero no observable | 0.0 % | 38 |
| — | Elogio en ejecuciones correctas | 100.0 % | 21 |
| — | Abstención (sin corrección) con medida ocluida | 100.0 % | 19 |
| — | Abstención (sin corrección) con plano no observable | 100.0 % | 19 |
| — | Mensajes por minuto (correcciones + elogios) | 2.91 (2.46 + 0.45) | — |

**M1\*** no es la M1 de ADR-001 §5: mide coherencia del motor sobre entrada sintética, no exactitud de contenido sobre vídeo real.

M3, M1\* y la abstención cuentan solo **correcciones**. El elogio (refuerzo positivo) se mide con M8, el espejo de M3: M8 debe ser 0; M8′ es el elogio que se da porque las reglas visibles están bien aunque haya un error que la cámara no ve.

## M4 — latencia por etapa (ms)

| Etapa | p50 | p95 | máx | n |
|---|---|---|---|---|
| Decisión | 0.0066 | 0.0280 | 0.1963 | 5568 |
| Verbalización | 0.1485 | 0.3177 | 0.5702 | 135 |

Medido en el entorno de desarrollo, no en el hardware del proyecto. No sustituye la medición en el M2 Ultra. No incluye pose, DTW ni TTS.

## Motivos de silencio

| Motivo | Veces |
|---|---|
| `sin_error` | 4651 |
| `periodo_refractario` | 357 |
| `plano_no_observable` | 272 |
| `evidencia_insuficiente` | 105 |
| `confianza_baja` | 48 |

## Muestra de mensajes emitidos

- `abduccion_cadera_der` / `tronco_inclinado_izq` / leve -> «Endereza un poco el tronco, se va hacia la izquierda.»
- `abduccion_cadera_der` / `tronco_inclinado_izq` / moderada -> «No inclines el tronco hacia la izquierda.»
- `abduccion_cadera_der` / `tronco_inclinado_izq` / alta -> «Endereza el tronco, te estás inclinando hacia la izquierda.»
- `abduccion_cadera_der` / `cadera_der_sube` / leve -> «Mantén la cadera derecha un poco más baja.»
- `abduccion_cadera_der` / `cadera_der_sube` / moderada -> «No subas la cadera derecha, mantenla nivelada.»
- `abduccion_cadera_der` / `cadera_der_sube` / alta -> «Baja la cadera derecha, la estás subiendo mucho.»
- `abduccion_cadera_der` / `abduccion_insuficiente_der` / leve -> «Sube un poco más la pierna derecha hacia el lado.»
- `abduccion_cadera_der` / `abduccion_insuficiente_der` / moderada -> «Abre más la pierna derecha hacia el lado.»
- `abduccion_cadera_der` / `abduccion_insuficiente_der` / alta -> «Sube bien la pierna derecha, casi no la separas.»
- `abduccion_cadera_izq` / `tronco_inclinado_der` / leve -> «Endereza un poco el tronco, se va hacia la derecha.»
- `abduccion_cadera_izq` / `tronco_inclinado_der` / moderada -> «No inclines el tronco hacia la derecha.»
- `abduccion_cadera_izq` / `tronco_inclinado_der` / alta -> «Endereza el tronco, te estás inclinando hacia la derecha.»
- `abduccion_cadera_izq` / `cadera_izq_sube` / leve -> «Mantén la cadera izquierda un poco más baja.»
- `abduccion_cadera_izq` / `cadera_izq_sube` / moderada -> «No subas la cadera izquierda, mantenla nivelada.»
- `abduccion_cadera_izq` / `cadera_izq_sube` / alta -> «Baja la cadera izquierda, la estás subiendo mucho.»
- `abduccion_cadera_izq` / `abduccion_insuficiente_izq` / leve -> «Sube un poco más la pierna izquierda hacia el lado.»
- `abduccion_cadera_izq` / `abduccion_insuficiente_izq` / moderada -> «Abre más la pierna izquierda hacia el lado.»
- `abduccion_cadera_izq` / `abduccion_insuficiente_izq` / alta -> «Sube bien la pierna izquierda, casi no la separas.»
- `jumping_jacks` / `brazos_no_llegan_arriba` / leve -> «Sube un poco más los brazos.»
- `jumping_jacks` / `brazos_no_llegan_arriba` / moderada -> «Te falta recorrido, eleva más los brazos.»
- `jumping_jacks` / `brazos_no_llegan_arriba` / alta -> «Sube mucho más los brazos, te estás quedando corta.»
- `jumping_jacks` / `apertura_pies_insuficiente` / leve -> «Abre un poco más los pies al saltar.»
- `jumping_jacks` / `apertura_pies_insuficiente` / moderada -> «Abre más los pies en cada salto.»
- `jumping_jacks` / `apertura_pies_insuficiente` / alta -> «Abre mucho más los pies, casi no te separas.»
- `jumping_jacks` / `codos_flexionados` / leve -> «Estira un poco más los codos.»
- `jumping_jacks` / `codos_flexionados` / moderada -> «Mantén los codos extendidos.»
- `jumping_jacks` / `codos_flexionados` / alta -> «Estira bien los codos, los tienes muy doblados.»
- `marcha_rodillas` / `tronco_muy_inclinado` / leve -> «Sube un poco el pecho.»
- `marcha_rodillas` / `tronco_muy_inclinado` / moderada -> «Mantén el tronco más vertical.»
- `marcha_rodillas` / `tronco_muy_inclinado` / alta -> «Endereza bien el tronco, te estás yendo hacia delante.»
- `marcha_rodillas` / `rodilla_izq_baja` / leve -> «Sube un poco más la rodilla izquierda.»
- `marcha_rodillas` / `rodilla_izq_baja` / moderada -> «Eleva más la rodilla izquierda en cada paso.»
- `marcha_rodillas` / `rodilla_izq_baja` / alta -> «Sube bien la rodilla izquierda, apenas la estás levantando.»
- `marcha_rodillas` / `rodilla_der_baja` / leve -> «Sube un poco más la rodilla derecha.»
- `marcha_rodillas` / `rodilla_der_baja` / moderada -> «Eleva más la rodilla derecha en cada paso.»
- `marcha_rodillas` / `rodilla_der_baja` / alta -> «Sube bien la rodilla derecha, apenas la estás levantando.»
- `plancha` / `cadera_hundida` / leve -> «Sube un poco las caderas.»
- `plancha` / `cadera_hundida` / moderada -> «Sube las caderas, no las dejes caer.»
- `plancha` / `cadera_hundida` / alta -> «Sube bien las caderas, se están hundiendo.»
- `plancha` / `cadera_elevada` / leve -> «Baja un poco las caderas.»
- `plancha` / `cadera_elevada` / moderada -> «Baja las caderas, alinea el cuerpo.»
- `plancha` / `cadera_elevada` / alta -> «Baja bien las caderas, las tienes muy altas.»
- `plancha` / `cabeza_desalineada` / leve -> «Alinea un poco la cabeza con el cuerpo.»
- `plancha` / `cabeza_desalineada` / moderada -> «Mantén la cabeza en línea con el cuerpo.»
- `plancha` / `cabeza_desalineada` / alta -> «Coloca la cabeza en línea, ni caída ni levantada.»
- `zancada_atras_der` / `profundidad_insuficiente_izq` / leve -> «Baja un poco más, flexiona la rodilla izquierda.»
- `zancada_atras_der` / `profundidad_insuficiente_izq` / moderada -> «Baja más, flexiona bien la rodilla izquierda.»
- `zancada_atras_der` / `profundidad_insuficiente_izq` / alta -> «Baja mucho más, la rodilla izquierda casi no se flexiona.»
- `zancada_atras_izq` / `profundidad_insuficiente_der` / leve -> «Baja un poco más, flexiona la rodilla derecha.»
- `zancada_atras_izq` / `profundidad_insuficiente_der` / moderada -> «Baja más, flexiona bien la rodilla derecha.»
- `zancada_atras_izq` / `profundidad_insuficiente_der` / alta -> «Baja mucho más, la rodilla derecha casi no se flexiona.»

