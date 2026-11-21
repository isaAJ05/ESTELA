# EXP-008 — Puntos adicionales de tronco y pelvis

Arnés del experimento descrito en `docs/experimentos/EXP-008-puntos-tronco.md` (espacio de trabajo del proyecto). Pregunta: **¿añadir puntos de columna y pelvis aporta información sobre el movimiento de la lumbar, la columna y la cadera que los 33 puntos de MediaPipe no tienen, y a qué coste de latencia?**

No toca `estela/` ni `feedback/`, ni añade dependencias a `pyproject.toml`.

| Archivo | Qué es |
|---|---|
| `tronco.py` | Geometría 2D de las medidas de tronco. Solo numpy. |
| `extraer.py` | MediaPipe (+ contorno de la máscara) y SpinePose sobre un vídeo o la cámara. Guarda puntos y latencias en `.npz`; **nunca guarda frames**. |
| `analizar.py` | Latencia, ruido, redundancia con `mp_tronco` y contrastes neutra/inducida. Escribe un informe en Markdown. |
| `test_tronco.py` | Pruebas de la geometría y de la regla de decisión. |
| `resultados/` | Salida. Ignorada por git: contiene puntos de personas reales. |

## Instalación

```bash
source .venv/bin/activate                    # el entorno de ESTELA
pip install -r PRUEBAS/exp008_puntos_tronco/requirements.txt
pip install --no-deps spinepose==2.1.0       # sin torch: el código no lo usa
```

La primera ejecución descarga los pesos de SpinePose en `~/.cache/spinepose` (≈ 23 MB el modelo `small`). Es la única conexión: la inferencia es local.

**Licencia:** `spinepose` (código y pesos) es CC-BY-NC-4.0. Vale para un prototipo académico; no para un uso comercial.

## Comandos

```bash
python -m unittest PRUEBAS/exp008_puntos_tronco/test_tronco.py

# Un vídeo existente (sin etiqueta de condición: solo latencia y descriptivos)
python PRUEBAS/exp008_puntos_tronco/extraer.py --video RUTA.mp4 \
    --sujeto ucf_g01 --condicion sentadilla_libre --vista perfil

# Un intento del protocolo con la cámara: 5 s de cuenta atrás, 8 s de registro
python PRUEBAS/exp008_puntos_tronco/extraer.py --camara 0 --espera 5 --duracion 8 \
    --sujeto S1 --condicion bisagra_neutra --vista perfil

python PRUEBAS/exp008_puntos_tronco/analizar.py PRUEBAS/exp008_puntos_tronco/resultados/*.npz \
    --salida PRUEBAS/exp008_puntos_tronco/resultados/informe.md
```

Cada ejecución crea `resultados/<sujeto>_<condicion>_<vista>_NN.npz` con el siguiente número libre, así que repetir el comando es registrar otro intento.

Opciones útiles de `extraer.py`: `--spinepose small|medium|ninguno`, `--version-sp v2|v1`, `--sin-mascara`, `--ropa ajustada|holgada`, `--max-frames N`, `--ventana`.

### Reproducir la fase 0 (vídeos de sentadilla de perfil del dataset)

```bash
D="PRUEBAS/Prueba red neuronal (dataset-pose-deteccion-conteo)/DATASET/videos/sentadilla"
for v in v_BodyWeightSquats_g01_c01.avi v_BodyWeightSquats_g01_c02.avi v_BodyWeightSquats_g02_c03.avi \
         v_BodyWeightSquats_g04_c03.avi v_BodyWeightSquats_g04_c04.avi 1e2c254b-0d5a-4fd6-a6d4-2681333d927b.mp4; do
  python PRUEBAS/exp008_puntos_tronco/extraer.py --video "$D/$v" --sujeto "${v%%.*}" \
      --condicion sentadilla_libre --vista perfil --salida PRUEBAS/exp008_puntos_tronco/resultados/fase0
done
python PRUEBAS/exp008_puntos_tronco/analizar.py PRUEBAS/exp008_puntos_tronco/resultados/fase0/*.npz \
    --salida PRUEBAS/exp008_puntos_tronco/resultados/fase0/informe.md
```

La latencia varía entre ejecuciones (el p50 de MediaPipe osciló entre 33 y 51 ms en la máquina de desarrollo); las cifras de la geometría son deterministas.

## Protocolo de grabación

**Montaje.** Cámara fija a 2,5–3 m, a la altura de la cadera (≈ 1 m), cuerpo entero en el encuadre y fondo despejado. *Perfil* = la cámara mira perpendicular al costado de la persona (90°); *frontal* = de frente (0°). Primera pasada con ropa ajustada en el tronco; si hay tiempo, una segunda con `--ropa holgada`.

**Orden.** Por cada contraste, 3 intentos de cada condición **intercalados** (N, I, N, I, N, I), para que el cansancio o un cambio de colocación no se confundan con la condición. Un sujeto por vez; mínimo 3 sujetos.

**Seguridad.** Solo peso corporal, rango cómodo, sin carga. Las posturas «inducidas» son posturas cotidianas exageradas, no esfuerzos. Si algo resulta incómodo, se omite esa condición.

| Prioridad | Contraste (`--condicion`) | Vista | Duración | Instrucción para la condición inducida |
|---|---|---|---|---|
| **1** | `bisagra_neutra` → `bisagra_redondeada` | perfil | 8 s mantenido | Misma inclinación del tronco (~45°, manos apoyadas en el mismo punto de los muslos), pero redondeando la espalda. **Es la prueba central**: el tronco de MediaPipe no debería cambiar y la columna sí. |
| **1** | `de_pie_neutro` → `de_pie_encorvado` | perfil | 8 s | Dejar caer los hombros hacia delante y redondear la parte alta de la espalda, mirando al frente. |
| **1** | `de_pie_neutro` → `de_pie_arqueado` | perfil | 8 s | Arquear la zona lumbar (sacar glúteos) sin inclinar el tronco. |
| 2 | `sentadilla_neutra` → `sentadilla_redondeada` | perfil | 5 repeticiones | Dejar que la zona lumbar se redondee al llegar abajo. |
| 2 | `elevacion_brazos_neutra` → `elevacion_brazos_arqueada` | perfil | 5 repeticiones | Arquear la zona lumbar al subir los brazos. |
| 3 | `de_pie_neutro_frontal` → `inclinacion_lateral` | frontal | 8 s | Inclinar el tronco hacia un lado y mantener. |
| 3 | `marcha_neutra` → `marcha_cadera_caida` | frontal | 10 pasos | Dejar caer la cadera del lado de la pierna que sube. |

`de_pie_neutro` se graba una sola vez por sujeto (3 intentos) y sirve para los dos contrastes que lo usan.

Ejemplo de una serie completa de la prueba central:

```bash
for i in 1 2 3; do
  for c in bisagra_neutra bisagra_redondeada; do
    read -p "Siguiente: $c (intento $i). Enter para empezar " _
    python PRUEBAS/exp008_puntos_tronco/extraer.py --camara 0 --duracion 8 \
        --sujeto S1 --condicion $c --vista perfil
  done
done
```

## Cómo leer el informe

- **Latencia**: p50/p95 por componente y total secuencial, sin los 10 primeros frames.
- **Contrastes**: por sujeto, cada intento se reduce a un número (mediana si la postura es mantenida; p95 o p5 si es dinámica). Una medida *separa* si los 3 intentos inducidos quedan, todos, del lado esperado de los 3 neutros: por azar ocurre 1 de cada 20 veces (p = 0,05). Las filas `control` deben decir «no (correcto)»: si dicen «sí (no debería)», el contraste no aisló la columna y su resultado no vale.
- **Por grabación**: `(p95−p5)/ruido` indica cuánto se mueve la medida respecto a su ruido entre frames; `r²` con `mp_tronco` indica cuánto de esa variación ya explica la medida de tronco actual. `mp_virtual_flecha` es siempre 0: es el control de los puntos interpolados.
