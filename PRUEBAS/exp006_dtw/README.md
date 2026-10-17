# EXP-006 · DTW en sesión: coste por frame y calidad del alineamiento

Arnés de la parte de DTW de `docs/experimentos/EXP-006-absolutas-vs-referencia.md` (espacio de trabajo del proyecto). Mide lo que ADR-004 §2.3 dejó como `[?]`: coste por frame, efecto de la banda y estabilidad del alineamiento. Sirve también para calibrar `dtw.coste_maximo`.

No toca `estela/` ni añade dependencias.

| Archivo | Qué es |
|---|---|
| `medir_dtw.py` | Fase 0. `sintetico`: tiempo por frame del DTW anterior (PR #8) y del incremental con las referencias del catálogo, sin cámara ni modelo. `video`: pose una vez sobre un vídeo y tres pasadas de la sesión con esa misma pose (sin DTW, anterior, incremental). |
| `comparar_reglas.py` | Fase 1 (T32). `ruido`: piso de ruido provisional por medida (jitter en los frames quietos). `banco`: banco piloto semisintético (vídeos públicos correctos + errores inducidos sobre su pose) con tres condiciones: `absolutos`, `referencia`, `referencia_sin_dtw`. |
| `resultados/` | Salida en JSON (y Markdown del banco). Ignorada por git: solo métricas derivadas, pero de personas reales. |

## Comandos

Desde `ESTELA/`, con el entorno de `backend/` activado (necesita el modelo de pose: `python backend/scripts/descargar_modelos.py`).

```bash
# Sin cámara ni modelo: ~1 min
python PRUEBAS/exp006_dtw/medir_dtw.py sintetico

# Un vídeo: latencia en la sesión + calidad del alineamiento + desplazamiento artificial de +20°
python PRUEBAS/exp006_dtw/medir_dtw.py video --ejercicio jumping_jacks \
    --video "PRUEBAS/Prueba red neuronal (dataset-pose-deteccion-conteo)/DATASET/videos/jumping_jack/1 hombre.mp4" \
    --desplazar 20
```

`--sin-anterior` se salta la versión anterior, que en un vídeo largo tarda minutos.

```bash
# Fase 1 (T32): ~5 min de pose por comando sobre los 15 vídeos del banco
python PRUEBAS/exp006_dtw/comparar_reglas.py ruido
python PRUEBAS/exp006_dtw/comparar_reglas.py banco --k 2 3 4
```

El banco piloto está definido en `BANCO` y `VARIANTES` dentro del script. Para el banco grabado de T24/T26 se sustituyen los vídeos y, en vez de inducir errores, se usan las etiquetas de consenso.

## Qué mide el modo `video`

- `pose_ms`: latencia del estimador en la pasada real.
- `dtw_ms` por pasada: la etapa `dtw` de la sesión (`lat["dtw"]`).
- `calidad`: frames alineados, **retrocesos** (el instante alineado vuelve atrás dentro de una repetición) y el progreso esperado al cerrar la repetición (el frame anterior al reposo en la referencia; solo en segmentación `ciclo`).
- `repeticiones`: `coste_dtw` y `progreso_dtw` del frame que cierra cada repetición (las mismas columnas que el CSV de `--guardar-metricas`).
- `desplazamiento`: suma `+delta` a un ángulo cada vez y mide qué parte llega a la desviación. Si el alineamiento no se mueve, llega entero; si el DTW deforma el tiempo para acercarse, llega menos.
- `mismos_mensajes_en_las_tres_pasadas`: hoy ninguna regla activa usa `desviacion`, así que el DTW no debería cambiar ningún mensaje.

## Medir en otra máquina (p. ej. el Mac de EXP-007)

1. Copiar el repo con el modelo descargado.
2. Correr los dos comandos de arriba.
3. Pasar los JSON de `resultados/` (no contienen frames ni puntos, solo tiempos y métricas por repetición).
