# EXP-001 piloto — condición A (banco sintético)

- Episodios: **120**
- Observaciones por episodio: 48 (8 repeticiones x 6 frames)
- Duración nominal de un episodio: 24 s
- Repeticiones para M5: 10

## Métricas

| # | Métrica | Valor | n |
|---|---|---|---|
| M1* | Coherencia detector-referencia (sintética) | 100.0 % | 63 |
| M2 | Aserciones no soportadas | 0.0 % | 126 mensajes |
| M3 | Sobrecorrección en ejecuciones correctas | 0.0 % | 15 |
| M5 | Determinismo | 100.0 % | 120 |
| M7 | Caída a fallback | 0.0 % | 147 mensajes |
| M8 | Refuerzo indebido: elogio con un error inducido y observable | 0.0 % | 63 |
| M8′ | Elogio con un error presente pero no observable | 14.3 % | 42 |
| — | Elogio en ejecuciones correctas | 100.0 % | 15 |
| — | Abstención (sin corrección) con medida ocluida | 100.0 % | 21 |
| — | Abstención (sin corrección) con plano no observable | 100.0 % | 21 |
| — | Mensajes por minuto (correcciones + elogios) | 3.06 (2.62 + 0.44) | — |

**M1\*** no es la M1 de ADR-001 §5: mide coherencia del motor sobre entrada sintética, no exactitud de contenido sobre vídeo real.

M3, M1\* y la abstención cuentan solo **correcciones**. El elogio (refuerzo positivo) se mide con M8, el espejo de M3: M8 debe ser 0; M8′ es el elogio que se da porque las reglas visibles están bien aunque haya un error que la cámara no ve.

## M4 — latencia por etapa (ms)

| Etapa | p50 | p95 | máx | n |
|---|---|---|---|---|
| Decisión | 0.0159 | 0.1261 | 5.9697 | 5760 |
| Verbalización | 0.2617 | 1.1112 | 3.3029 | 147 |

Medido en el entorno de desarrollo, no en el hardware del proyecto. No sustituye la medición en el M2 Ultra. No incluye pose, DTW ni TTS.

## Motivos de silencio

| Motivo | Veces |
|---|---|
| `sin_error` | 4723 |
| `periodo_refractario` | 381 |
| `plano_no_observable` | 368 |
| `evidencia_insuficiente` | 117 |
| `confianza_baja` | 24 |

## Muestra de mensajes emitidos

- `abduccion_cadera_der` / `tronco_inclinado_izq` / leve -> «Endereza un poco el tronco, se va hacia la izquierda.»
- `abduccion_cadera_der` / `tronco_inclinado_izq` / moderada -> «No inclines el tronco hacia la izquierda.»
- `abduccion_cadera_der` / `tronco_inclinado_izq` / alta -> «Endereza el tronco, te estás inclinando hacia la izquierda.»
- `abduccion_cadera_der` / `cadera_der_sube` / leve -> «Mantén la cadera derecha un poco más baja.»
- `abduccion_cadera_der` / `cadera_der_sube` / moderada -> «No subas la cadera derecha, mantenla nivelada.»
- `abduccion_cadera_der` / `cadera_der_sube` / alta -> «Baja la cadera derecha, la estás subiendo mucho.»
- `abduccion_cadera_der` / `abduccion_insuficiente_der` / leve -> «Lleva la pierna derecha un poco más hacia el lado, con control.»
- `abduccion_cadera_der` / `abduccion_insuficiente_der` / moderada -> «Abre más la pierna derecha hacia el lado, sin perder estabilidad.»
- `abduccion_cadera_der` / `abduccion_insuficiente_der` / alta -> «Separa bastante más la pierna derecha, solo si te mantienes estable.»
- `abduccion_cadera_izq` / `tronco_inclinado_der` / leve -> «Endereza un poco el tronco, se va hacia la derecha.»
- `abduccion_cadera_izq` / `tronco_inclinado_der` / moderada -> «No inclines el tronco hacia la derecha.»
- `abduccion_cadera_izq` / `tronco_inclinado_der` / alta -> «Endereza el tronco, te estás inclinando hacia la derecha.»
- `abduccion_cadera_izq` / `cadera_izq_sube` / leve -> «Mantén la cadera izquierda un poco más baja.»
- `abduccion_cadera_izq` / `cadera_izq_sube` / moderada -> «No subas la cadera izquierda, mantenla nivelada.»
- `abduccion_cadera_izq` / `cadera_izq_sube` / alta -> «Baja la cadera izquierda, la estás subiendo mucho.»
- `abduccion_cadera_izq` / `abduccion_insuficiente_izq` / leve -> «Lleva la pierna izquierda un poco más hacia el lado, con control.»
- `abduccion_cadera_izq` / `abduccion_insuficiente_izq` / moderada -> «Abre más la pierna izquierda hacia el lado, sin perder estabilidad.»
- `abduccion_cadera_izq` / `abduccion_insuficiente_izq` / alta -> «Separa bastante más la pierna izquierda, solo si te mantienes estable.»
- `jumping_jacks` / `brazos_no_llegan_arriba` / leve -> «Sube un poco más los brazos, hasta donde te resulte cómodo.»
- `jumping_jacks` / `brazos_no_llegan_arriba` / moderada -> «Eleva un poco más los brazos, sin forzar.»
- `jumping_jacks` / `brazos_no_llegan_arriba` / alta -> «Intenta subir bastante más los brazos, sin forzar.»
- `jumping_jacks` / `apertura_pies_insuficiente` / leve -> «Abre un poco más los pies, con control.»
- `jumping_jacks` / `apertura_pies_insuficiente` / moderada -> «Abre más los pies en cada salto, sin perder el control.»
- `jumping_jacks` / `apertura_pies_insuficiente` / alta -> «Separa bastante más los pies, manteniendo el control.»
- `jumping_jacks` / `codos_flexionados` / leve -> «Estira un poco más los codos, sin bloquearlos.»
- `jumping_jacks` / `codos_flexionados` / moderada -> «Estira más los codos, sin llegar a bloquearlos.»
- `jumping_jacks` / `codos_flexionados` / alta -> «Estira bastante más los codos, sin bloquearlos.»
- `marcha_rodillas` / `tronco_muy_inclinado` / leve -> «Sube un poco el pecho.»
- `marcha_rodillas` / `tronco_muy_inclinado` / moderada -> «Mantén el tronco más vertical.»
- `marcha_rodillas` / `tronco_muy_inclinado` / alta -> «Endereza bien el tronco, sin irte hacia delante ni hacia atrás.»
- `marcha_rodillas` / `rodilla_izq_baja` / leve -> «Sube un poco más la rodilla izquierda, si mantienes el equilibrio.»
- `marcha_rodillas` / `rodilla_izq_baja` / moderada -> «Sube un poco más la rodilla izquierda en cada paso, con control.»
- `marcha_rodillas` / `rodilla_izq_baja` / alta -> «Intenta subir bastante más la rodilla izquierda, con equilibrio.»
- `marcha_rodillas` / `rodilla_der_baja` / leve -> «Sube un poco más la rodilla derecha, si mantienes el equilibrio.»
- `marcha_rodillas` / `rodilla_der_baja` / moderada -> «Sube un poco más la rodilla derecha en cada paso, con control.»
- `marcha_rodillas` / `rodilla_der_baja` / alta -> «Intenta subir bastante más la rodilla derecha, con equilibrio.»
- `marcha_rodillas` / `rodilla_izq_extendida` / leve -> «Dobla un poco más la rodilla izquierda al subirla.»
- `marcha_rodillas` / `rodilla_izq_extendida` / moderada -> «Flexiona la rodilla izquierda en cada paso.»
- `marcha_rodillas` / `rodilla_izq_extendida` / alta -> «Dobla bien la rodilla izquierda, la estás subiendo estirada.»
- `marcha_rodillas` / `rodilla_der_extendida` / leve -> «Dobla un poco más la rodilla derecha al subirla.»
- `marcha_rodillas` / `rodilla_der_extendida` / moderada -> «Flexiona la rodilla derecha en cada paso.»
- `marcha_rodillas` / `rodilla_der_extendida` / alta -> «Dobla bien la rodilla derecha, la estás subiendo estirada.»
- `plancha` / `cadera_hundida` / leve -> «Sube un poco las caderas.»
- `plancha` / `cadera_hundida` / moderada -> «Sube las caderas, no las dejes caer.»
- `plancha` / `cadera_hundida` / alta -> «Sube bien las caderas, se están hundiendo.»
- `plancha` / `cadera_elevada` / leve -> «Baja un poco las caderas.»
- `plancha` / `cadera_elevada` / moderada -> «Baja las caderas, alinea el cuerpo.»
- `plancha` / `cadera_elevada` / alta -> «Baja bien las caderas, las tienes muy altas.»
- `plancha` / `cabeza_desalineada` / leve -> «Alinea un poco la cabeza con el cuerpo.»
- `plancha` / `cabeza_desalineada` / moderada -> «Mantén la cabeza en línea con el cuerpo.»
- `plancha` / `cabeza_desalineada` / alta -> «Coloca la cabeza en línea, ni caída ni levantada.»
- `plancha` / `hombros_adelantados` / leve -> «Lleva los hombros un poco hacia atrás.»
- `plancha` / `hombros_adelantados` / moderada -> «Lleva los hombros hacia atrás, sobre el apoyo.»
- `plancha` / `hombros_adelantados` / alta -> «Lleva bien los hombros hacia atrás, sobre el apoyo.»
- `plancha` / `hombros_retrasados` / leve -> «Lleva los hombros un poco hacia delante.»
- `plancha` / `hombros_retrasados` / moderada -> «Adelanta los hombros, justo sobre el apoyo.»
- `plancha` / `hombros_retrasados` / alta -> «Lleva bien los hombros hacia delante, sobre el apoyo.»
- `plancha` / `rodilla_izq_flexionada` / leve -> «Estira un poco más la rodilla izquierda.»
- `plancha` / `rodilla_izq_flexionada` / alta -> «Estira bien la rodilla izquierda, la tienes muy doblada.»
- `plancha` / `rodilla_der_flexionada` / leve -> «Estira un poco más la rodilla derecha.»
- `plancha` / `rodilla_der_flexionada` / alta -> «Estira bien la rodilla derecha, la tienes muy doblada.»

