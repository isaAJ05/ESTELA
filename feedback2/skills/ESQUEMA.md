# Esquema de un archivo de `skill`

Un `skill` contiene **todo** lo que el sistema sabe de un ejercicio. Añadir un ejercicio es añadir un archivo `.json` en este directorio; no se modifica el motor.

El cargador (`motor/skill.py`) valida el esquema y falla ruidosamente. Un archivo mal formado no se carga a medias.

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
  "mensaje_id": "valgo_rodilla"      // clave en plantillas_es.json; varias reglas pueden compartirla
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

## `segmentacion` (opcional; la usa `estela/`, no el motor)

El motor no lee esta sección: `motor/skill.py` ignora las claves que no conoce. La usa la aplicación (`estela/conteo/segmentador.py`) para producir `Observacion.fase` y `Observacion.repeticion` y para contar repeticiones. Un skill sin `segmentacion` se carga, pero no se puede usar en sesión (hoy: `rotacion_tronco`).

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
```

- `senal` es `"angulos.<nombre>"` o `"distancias.<nombre>"` de la `Observacion`, o una **lista ordenada**: se usa la primera con confianza suficiente. Hace falta porque de perfil la pierna lejana queda ocluida y `rodilla_media` hereda la confianza mínima de los dos lados.
- El sentido (señal que baja o que sube) se deduce de `reposo` y `extremo`.
- Los nombres de fase deben estar en `fases` del skill; el cargador lo comprueba.
- La repetición empieza al salir del reposo. Una repetición que no llega al extremo también pasa por la fase de vuelta (para que se evalúen reglas como `profundidad_insuficiente`) pero se cuenta como *incompleta*.
- En `alternante`, mientras la pierna sube la fase es `fase_transicion`; la fase de apoyo empieza cuando la pierna llega arriba o se da la vuelta. Así las reglas de altura, que usan el mínimo de la repetición, no se evalúan antes del pico.
- Todos los umbrales actuales son `[?]` provisionales: se fijaron mirando las señales 3D de un vídeo por ejercicio de `PRUEBAS/.../DATASET`.

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
