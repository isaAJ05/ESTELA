# EXP-010 · ¿Está haciendo el ejercicio elegido?

Arnés de `docs_estela/experimentos/EXP-010-reconocimiento-ejercicio.md`. Mide si la sesión puede avisar «ese no es el ejercicio» sin falsas alarmas, y si el DTW aporta algo frente a una línea base sin DTW.

No toca `estela/` ni añade dependencias.

| Archivo | Qué es |
|---|---|
| `extraer.py` | Una pasada de pose por vídeo del banco (`BANCO`) con el pipeline de la sesión. Guarda las medidas por frame en `cache/` |
| `reconocer.py` | Simula, por cada vídeo y cada ejercicio «elegido», cuándo saltaría el aviso. Compara cuatro detectores: `segmentadores` (sin DTW), `dtw_propias` (referencias del catálogo), `dtw_comun` (las mismas referencias con un vector común de medidas) y `dtw_multi` (una referencia por cada vídeo de docs_estela del ejercicio, validado dejando uno fuera) |
| `probar_video.py` | Prueba con un vídeo propio: `--video RUTA --elegido jumping_jacks\|abduccion\|marcha_rodillas\|plancha`. Usa `dtw_multi+rel` (`--referencias una` para `dtw_comun+seg`). Imprime los avisos que daría la sesión y una línea de tiempo con el coste de cada ejercicio. Guarda ese texto en `resultados/<fecha>-probar-<vídeo>-<elegido>.txt` |
| `probar_carpeta.py` | Prueba todos los vídeos de una carpeta: `--carpeta RUTA`. El nombre de cada vídeo dice los ejercicios en orden (`jumping_jacks_abduccion_derecha.MOV`). Comprueba por tramo que calle con el ejercicio elegido y avise con los demás. Tiempos de cambio opcionales en `tiempos.csv` dentro de la carpeta. Pose a 1280 px y ≤ 30 fps, guardada en `cache/propios/`. Informe en `resultados/<fecha>-carpeta.md` |
| `registrar.py` | Añade un vídeo propio al banco: `--video RUTA --clase X [--lado izq\|der] [--vista frente\|lado\|diagonal] --consentimiento FECHA`. `--lista` muestra lo registrado |
| `cache/`, `resultados/`, `registro.csv` | Ignorados por git: solo métricas derivadas y rutas, pero de personas reales |

## Comandos

Desde `ESTELA/`, con el entorno de `backend/` y el modelo de pose (`python backend/scripts/descargar_modelos.py`):

```bash
python PRUEBAS/exp010_reconocimiento/extraer.py          # ~10 min la primera vez
python PRUEBAS/exp010_reconocimiento/reconocer.py

# un vídeo propio (grabado fuera del repositorio)
python PRUEBAS/exp010_reconocimiento/probar_video.py --video "C:/ruta/mi_video.mp4" --elegido jumping_jacks
```

```bash
# una carpeta de vídeos propios (el nombre dice los ejercicios en orden)
python PRUEBAS/exp010_reconocimiento/probar_carpeta.py --carpeta "C:/Users/USUARIO/Downloads/VIDEOS"
```

```bash
# añadir vídeos propios al banco y volver a medir
python PRUEBAS/exp010_reconocimiento/registrar.py --video "C:/Users/USUARIO/Videos/estela_pruebas/jj_frente_01.mp4" --clase jumping_jacks --vista frente --consentimiento 2026-10-19
python PRUEBAS/exp010_reconocimiento/registrar.py --lista
python PRUEBAS/exp010_reconocimiento/extraer.py      # solo extrae los nuevos
python PRUEBAS/exp010_reconocimiento/reconocer.py    # añade el subconjunto «propios» a la tabla
```

El banco son los vídeos de `docs_estela/investigacion/fuentes/datasets/videos/` más los de `registro.csv` (ids `propio_<n>`, nunca referencias). Ningún vídeo se versiona; `registrar.py` rechaza vídeos dentro de los repositorios y pide la fecha del consentimiento.
