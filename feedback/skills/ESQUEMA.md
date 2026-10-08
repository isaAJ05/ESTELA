# Esquema de un archivo de `skill`

Un `skill` contiene **todo** lo que el sistema sabe de un ejercicio. Añadir un ejercicio es añadir un archivo `.json` en este directorio; no se modifica el motor.

El cargador (`motor/skill.py`) valida el esquema y falla ruidosamente. Un archivo mal formado no se carga a medias.

Solo se cargan los `.json` de este directorio, no los de subdirectorios. `retirados/` guarda los skills que salieron del conjunto de ejercicios en ADR-005 (sentadilla, elevación de brazos, rotación de tronco), marcados `"estado": "descartado"`: siguen siendo válidos y los tests del motor usan la sentadilla como banco de pruebas, pero no forman parte del catálogo.

Ejercicios actuales (ADR-005): `jumping_jacks`, `abduccion_cadera_izq` + `abduccion_cadera_der`, `marcha_rodillas`, `zancada_atras_izq` + `zancada_atras_der` y `plancha`. Los que se hacen en serie por pierna tienen un archivo por pierna.

## Estructura

```jsonc
{
  "skill_id": "sentadilla",          // único; debe coincidir con Observacion.ejercicio_id
  "nombre": "Sentadilla",
  "version": "0.1.0",
  "estado": "candidato",             // candidato | candidato_en_duda | adoptado
  "notas": "…",
  "fases": ["arriba", "descenso", "fondo", "ascenso"],
  "orientacion_preferida": "sagital", // frontal | sagital | transversal | cualquiera
  "angulos_requeridos": ["rodilla_media", "tronco_inclinacion"],

  "politica_silencio": { … },
  "reglas": [ … ]
}
```

## `politica_silencio`

| Campo | Defecto | Qué hace |
|---|---|---|
| `refractario_ms` | 4000 | Tiempo mínimo entre dos mensajes cualesquiera. |
| `refractario_mismo_error_ms` | 12000 | Tiempo mínimo antes de repetir **el mismo** error. |
| `repeticiones_evidencia` | 2 | Repeticiones consecutivas con el error antes de hablar. Es *bandwidth feedback* en el eje temporal: evita corregir por un frame ruidoso. |
| `factor_desvanecimiento` | 1.5 | Cada emisión del mismo error multiplica su periodo refractario por este factor. `[?]` La tasa óptima de desvanecimiento es desconocida en la literatura. |
| `max_emisiones_mismo_error` | 4 | Tope por sesión. Después, silencio. |
| `fases_silenciadas` | `[]` | Fases en las que no se habla (p. ej. mientras la usuaria está bajo esfuerzo). |
| `confianza_minima` | 0.6 | Por debajo, la regla no se evalúa. |
| `tolerancia_orientacion_grados` | 30.0 | Desviación admitida respecto al plano ideal de la regla. **Este valor debe salir de EXP-002, no del defecto.** |

## `reglas`

```jsonc
{
  "error_id": "valgo_rodilla_izq",   // único dentro del skill
  "descripcion": "…",
  "medida":    { … },                // qué se mide
  "condicion": { … },                // cuándo es error
  "fases": ["descenso", "fondo"],    // vacío = cualquier fase
  "plano": "frontal",                // frontal | sagital | transversal | cualquiera
  "segmento": "rodilla",             // del vocabulario cerrado de contrato.SEGMENTOS
  "lado": "izquierdo",               // izquierdo | derecho | bilateral | na
  "prioridad": 2,                    // 1 = más importante. ÚNICA dentro del skill
  "severidad": { "moderada": 0.06, "alta": 0.15 },
  "umbral_origen": "[?] provisional, sin calibrar",
  "mensaje_id": "valgo_rodilla",     // clave en plantillas_es.json; varias reglas pueden compartirla
  "direccion": { … }                 // opcional; ver abajo
}
```

### `medida`

| `tipo` | Campos | Significado |
|---|---|---|
| `angulo` | `nombre` | Valor instantáneo de `Observacion.angulos[nombre]`. |
| `distancia` | `nombre` | Valor instantáneo de `Observacion.distancias[nombre]`. |
| `desviacion` | `nombre` | `angulos[nombre] - angulos_ref[nombre]` (o el valor que entregue percepción). |
| `agregado` | `fn` (`min`\|`max`\|`rango`\|`media`), `nombre`, `ventana` (`repeticion`) | Agregado acumulado dentro de la repetición actual. |
| `asimetria` | `nombres` (exactamente 2) | Valor absoluto de la diferencia entre las dos medidas. |

### `condicion`

| `op` | Campos | Error cuando |
|---|---|---|
| `>` `>=` `<` `<=` | `umbral` | el valor compara así con el umbral |
| `fuera_de` | `min`, `max` | el valor está fuera del intervalo |
| `dentro_de` | `min`, `max` | el valor está dentro del intervalo |

El **exceso** (cuánto se rebasa el umbral) determina la severidad mediante el bloque `severidad`: `alta` si el exceso la alcanza, si no `moderada`, si no `leve`.

### `direccion` (opcional, ADR-004 §2.5)

Traduce el sentido en que debe moverse **el valor de la medida** a una dirección de movimiento que la usuaria entiende. El motor calcula el sentido a partir de la condición y el valor: `>`/`>=` → `disminuir`, `<`/`<=` → `aumentar`, `fuera_de` según el lado por el que se sale, `dentro_de` sin sentido. Luego busca ese sentido aquí y lo emite en `ErrorTipificado.direccion`; el exceso sale en `magnitud`.

| Clave | Valores |
|---|---|
| `aumentar`, `disminuir` | `mas_flexion` \| `menos_flexion` \| `subir` \| `bajar` \| `abrir` \| `cerrar` |

Ejemplo: rodilla de la zancada, `min(rodilla_der) > 110` → hay que **disminuir** el ángulo → `{"disminuir": "mas_flexion"}`. Sin este bloque el error sale con `direccion = null` y el validador no comprueba la dirección. Las reglas que piden «enderezar» o «alinear» (inclinación del tronco, cabeza) no lo declaran: no encajan en un par de opuestos.

El validador rechaza un mensaje que pida la dirección opuesta (`direccion_contradictoria`), con el léxico de `verbalizador/validador.py::LEXICO_DIRECCIONES`; «no subas» cuenta como pedir bajar.

## `segmentacion` (opcional; la usa `estela/`, no el motor)

El motor no lee esta sección: `motor/skill.py` ignora las claves que no conoce. La usa la aplicación (`estela/conteo/segmentador.py`) para producir `Observacion.fase` y `Observacion.repeticion` y para contar repeticiones. Un skill sin `segmentacion` se carga, pero no se puede usar en sesión.

```jsonc
// ciclo: una señal que va del reposo al extremo y vuelve
"segmentacion": {
  "tipo": "ciclo",
  "senal": ["angulos.rodilla_media", "angulos.rodilla_izq", "angulos.rodilla_der"],
  "reposo": 155,           // más allá de este valor empieza la repetición
  "extremo": 110,          // alcanzarlo la hace «completa» (cuenta)
  "margen_retorno": 10,    // retroceso desde el pico que marca la fase de vuelta
  "fases": ["arriba", "descenso", "fondo", "ascenso"],  // reposo, ida, extremo, vuelta
  "suavizado": 3,          // media móvil, en frames
  "confianza_minima": 0.5  // por debajo, la señal se ignora y el estado se congela
}

// alternante: un ciclo por pierna; una repetición = una elevación
"segmentacion": {
  "tipo": "alternante",
  "senal_izq": "angulos.cadera_izq", "senal_der": "angulos.cadera_der",
  "reposo": 150, "extremo": 115, "margen_retorno": 10,
  "fase_izq_arriba": "apoyo_der", "fase_der_arriba": "apoyo_izq",
  "fase_transicion": "transicion"
}

// isometrico: una postura sostenida (plancha, ADR-005); el objetivo va en segundos
"segmentacion": {
  "tipo": "isometrico",
  "condiciones": [                             // en posición = se cumplen todas
    {"senal": "angulos.tronco_inclinacion", "min": 55},
    {"senal": ["angulos.rodilla_media", "angulos.rodilla_izq", "angulos.rodilla_der"], "min": 145}
  ],
  "fases": ["preparacion", "mantenimiento"],   // fuera de la postura, en la postura
  "entrada_ms": 1000,      // tiempo cumpliendo las condiciones antes de empezar a contar
  "salida_ms": 1500,       // tiempo sin cumplirlas antes de dar la postura por interrumpida
  "bloque_s": 5,           // cada bloque es una «repetición» para el motor
  "confianza_minima": 0.5
}
```

- `senal` es `"angulos.<nombre>"` o `"distancias.<nombre>"` de la `Observacion`, o una **lista ordenada**: se usa la primera con confianza suficiente. Hace falta porque de perfil la pierna lejana queda ocluida y `rodilla_media` hereda la confianza mínima de los dos lados.
- El sentido (señal que baja o que sube) se deduce de `reposo` y `extremo`.
- Los nombres de fase deben estar en `fases` del skill; el cargador lo comprueba.
- La repetición empieza al salir del reposo. Una repetición que no llega al extremo también pasa por la fase de vuelta (para que se evalúen reglas como `profundidad_insuficiente`) pero se cuenta como *incompleta*.
- En `alternante`, mientras la pierna sube la fase es `fase_transicion`; la fase de apoyo empieza cuando la pierna llega arriba o se da la vuelta. Así las reglas de altura, que usan el mínimo de la repetición, no se evalúan antes del pico.
- En `isometrico`, `completadas` son los segundos en posición (el objetivo de la rutina se escribe `"duracion_s"` en lugar de `"repeticiones"`), `incompletas` cuenta las interrupciones y cada bloque de `bloque_s` segundos es una repetición para el motor: un error tiene que mantenerse `repeticiones_evidencia` bloques antes de decirse, y los agregados y el refuerzo se calculan por bloque. Las condiciones evitan contar posturas parecidas (a cuatro patas no es plancha porque las rodillas están flexionadas).
- Todos los umbrales actuales son `[?]` provisionales. Los de marcha y jumping jacks se fijaron mirando las señales 3D de un vídeo por ejercicio de `PRUEBAS/.../DATASET`; los de abducción, zancada y plancha no tienen vídeo de referencia.

## Medidas disponibles

Las calcula `motor/geometria.py` a partir de la pose; el plano es el de `PLANO_DE_ANGULO` (desde dónde es observable con una cámara, EXP-002). Una medida nueva es una ampliación del contrato (ADR-002, ADR-006), no un detalle de implementación.

| Medida | Tipo | Plano | Qué es |
|---|---|---|---|
| `codo_*`, `hombro_*`, `cadera_*`, `rodilla_*` (`_izq`, `_der`, `_media`/`_medio`) | ángulo | sagital (hombro: frontal) | Ángulo articular de la terna; 180 = extendido |
| `tronco_inclinacion` | ángulo | sagital | Tronco respecto a la vertical, sin signo |
| `inclinacion_lateral` | ángulo | frontal | Tronco hacia los lados, con signo: + = hacia la izquierda de la persona |
| `oblicuidad_pelvis`, `oblicuidad_hombros` | ángulo | frontal | Línea de caderas / hombros respecto a la horizontal: + = lado izquierdo más alto |
| `cabeza_adelantada` | ángulo | sagital | Cuello respecto a la prolongación del tronco, sin signo; 0 = alineada |
| `abduccion_cadera_izq`, `_der` | ángulo | frontal | Muslo respecto a la vertical en el plano frontal: + = hacia fuera |
| `rotacion_tronco`, `azimut_cadera` | ángulo | transversal | No observables con una cámara (EXP-002) |
| `separacion_pies` | distancia | frontal | Separación de tobillos / separación de caderas |
| `valgo_rodilla_izq`, `_der` | distancia | frontal | Rodilla hacia la línea media, en escalas corporales |
| `alineacion_cadera` | distancia | sagital | Cadera respecto a la recta hombro–tobillo, en escalas corporales: + = hundida. Solo tiene sentido con el cuerpo horizontal (plancha) |

## Referencias offline

`[R]` El script `scripts/crear_referencia.py` convierte un vídeo de
referencia en `referencia.json` sin crear un pipeline alternativo: usa
`EstimadorPose`, `observacion_desde_pose` y el `Segmentador` configurado en el
skill. Para ejercicios cíclicos agrupa las repeticiones completas, calcula el
medoide por coste DTW y guarda la media, la desviación estándar y el número de
observaciones válidas por instante. Los valores con confianza menor que 0,5 se
guardan como `null`; nunca se rellenan.

Para la plancha (`tipo: "isometrico"`) se calcula la postura media y su sigma
sobre los frames de la fase `mantenimiento`, sin DTW. En ambos formatos se
guardan los keypoints 2D normalizados del medoide o de la postura media para
dibujar la stick figure.

```text
python scripts/crear_referencia.py --selftest
python scripts/crear_referencia.py --ejercicio jumping_jacks \
  --video ruta.mp4 \
  --salida feedback/skills/referencias/jumping_jacks/referencia.json
```

El JSON cíclico contiene `angulos.media`, `angulos.sigma`, `angulos.n`,
`fases`, `keypoints_2d` y `dtw`. El JSON isométrico contiene `postura.media`,
`postura.sigma`, `postura.n` y `keypoints_2d`. El gráfico de control se revisa
antes de usar los valores para sustituir umbrales provisionales.

## Reglas de higiene que el cargador impone

- `segmento` debe estar en el vocabulario cerrado (`contrato.SEGMENTOS`). Es lo que permite al validador de salida rechazar mensajes que nombren otra parte del cuerpo.
- Las **prioridades no pueden repetirse**: con un empate el desempate quedaría indefinido y el motor dejaría de ser determinista.
- Los `error_id` no pueden repetirse dentro del skill.

## Cómo calibrar un umbral (pendiente)

Ningún umbral de este directorio está calibrado. El procedimiento previsto, que todavía no se ha ejecutado:

1. Grabar la referencia del ejercicio con la ejecución correcta validada por la licenciada en educación física.
2. Grabar ejecuciones con el error inducido según guion.
3. Medir la distribución de la medida en ambos grupos.
4. Fijar el umbral y reportar la tasa de falsos positivos y falsos negativos que produce, no solo el valor elegido.
5. Volver a ejecutar EXP-002: el ancho de la ventana de orientación válida depende del umbral.
