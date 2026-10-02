# Módulo de retroalimentación

Implementación de la alternativa **A** de `docs/decisiones/ADR-001-modulo-retroalimentacion.md`: motor determinista de reglas por `skill` + verbalización por plantillas, con la frontera del híbrido **F** ya construida para que el verbalizador sea intercambiable sin tocar la lógica de decisión.

Estado: **prototipo**. No ha visto una sola imagen real. Los umbrales de los archivos de `skill` son provisionales y están marcados como tales.

## Qué hace y qué no

Recibe medidas ya calculadas (ángulos, distancias normalizadas, desviaciones respecto a la referencia y **confianza por medida**) y produce una frase en español o un silencio con motivo.

No estima pose, no normaliza, no compara con DTW y no sintetiza voz. Esas cuatro cosas son de otros módulos y este no las importa.

## Arquitectura

```
Observacion (ángulos + confianza + fase + orientación)
        │
        ▼
┌──────────────────────────────────────────────┐
│  MotorDecision  (motor/decision.py)          │
│   1. ¿puedo ver esta medida?  confianza      │  → Silencio(confianza_baja)
│   2. ¿está el plano observable? orientación  │  → Silencio(plano_no_observable)
│   3. ¿se cumple alguna regla del skill?      │
│   4. ¿hay evidencia en N repeticiones?       │  → Silencio(evidencia_insuficiente)
│   5. UNA prioridad + política de silencio    │  → Silencio(refractario | desvanecimiento | fase)
└──────────────────────────────────────────────┘
        │
        ▼  contrato estable
   ErrorTipificado{error_id, segmento, lado, severidad, fase, repeticion, magnitud, confianza}
        │
        ├────────────────────────────┐
        ▼                            ▼
 VerbalizadorPlantillas      VerbalizadorLLMLocal   (intercambiables)
 (verbalizador/plantillas)   (verbalizador/llm_local)
        │                            │
        │                      validador.py  ── rechaza → cae a plantilla
        └──────────────┬─────────────┘
                       ▼
                 MensajeFeedback  → TTS (fuera de este módulo)
```

Las tres decisiones que sostienen el diseño:

1. **La abstención va antes que la detección.** La pregunta «¿puedo ver esto?» se resuelve antes que «¿está mal?». Al revés se producen correcciones seguras sobre datos inválidos, que es el peor fallo posible porque suena igual de competente que una correcta.
2. **El verbalizador no decide nada.** Recibe un error ya tipificado. No ve ángulos ni imágenes. Por construcción no puede inventar el contenido, solo la forma.
3. **El silencio es una salida de primera clase**, con motivo, y su motivo se cuenta. La frecuencia de `plano_no_observable` y `confianza_baja` es la señal de que la cámara está mal colocada o de que hace falta otra vista.

## Estructura

| Ruta | Qué es |
|---|---|
| `contrato.py` | Tipos de la frontera: `Observacion`, `ErrorTipificado`, `MensajeFeedback`, `Silencio`, vocabulario cerrado de segmentos y vocabulario médico prohibido. |
| `motor/geometria.py` | De keypoints a ángulos canónicos. Solo se usa si percepción no entrega los ángulos ya calculados. |
| `motor/skill.py` | Carga y validación de los archivos de ejercicio. Falla ruidosamente ante un esquema mal formado. |
| `motor/decision.py` | El motor determinista. |
| `verbalizador/plantillas.py` + `plantillas_es.json` | Condición A y *fallback* del sistema. |
| `verbalizador/validador.py` | Rechaza mensajes que nombren un segmento o un lado distinto del contrato, que usen vocabulario médico o que sean demasiado largos. |
| `verbalizador/llm_local.py` | Condición F/F′. **Escrito pero no probado contra ningún modelo.** |
| `skills/*.json` | Un archivo por ejercicio. Añadir un ejercicio es añadir un archivo. |
| `tests/` | 50 pruebas, sin dependencias externas. |

## Cómo correrlo

Sin instalar nada (solo biblioteca estándar, Python 3.9+):

```bash
python3 -m unittest discover -s feedback/tests -t .   # pruebas
python3 -m feedback.demo_consola                      # demo sin cámara
```

## Qué necesita el módulo de percepción que le entreguen

Esto es lo importante para la integración. Por cada frame, una `Observacion`:

| Campo | Obligatorio | Nota |
|---|---|---|
| `t_ms` | sí | milisegundos desde el inicio de la sesión |
| `ejercicio_id` | sí | debe coincidir con un `skill_id` |
| `angulos` | sí | grados, nombres canónicos (ver `motor/geometria.ANGULOS_TERNA`) |
| `confianza` | **sí** | 0–1 por medida. Sin esto el motor no puede abstenerse. Ausente se trata como 0, nunca como 1 |
| `fase` | recomendado | del segmentador de repeticiones |
| `repeticion` | recomendado | sin esto no hay política de evidencia por repeticiones |
| `orientacion` | recomendado | 0° de frente, 90° de perfil. Sin esto la salvaguarda de plano queda desactivada |
| `angulos_ref` | opcional | ángulo de la referencia en el instante alineado por DTW |
| `desviaciones` | opcional | si no viene, se calcula como `angulos - angulos_ref` |
| `distancias` | opcional | medidas escalares normalizadas por escala corporal |

`motor/geometria.observacion_desde_pose()` construye una `Observacion` a partir de un `MuestraPose` crudo, por si resulta más cómodo entregar keypoints y que este módulo derive los ángulos.

## Limitaciones conocidas

- **Los umbrales no están calibrados.** Todos llevan `umbral_origen: "[?] provisional, sin calibrar"`. Es el mismo problema que ADR-001 §2.1 documenta como no resuelto en la literatura (el δ de AIFit, el *bandwidth* de Sigrist).
- **Las plantillas no las ha revisado nadie con formación en educación física.** Están marcadas en `plantillas_es.json`.
- **La salvaguarda de plano no protege las medidas del plano transversal** (`rotacion_tronco`, `azimut_cadera`): no hay ninguna orientación de una sola cámara que las haga observables. Ver EXP-002.
- **El verbalizador F no ha sido ejecutado nunca.** No hay ninguna cifra de latencia ni de calidad para esa condición.
