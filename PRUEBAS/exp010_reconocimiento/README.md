# EXP-010 · ¿Está haciendo el ejercicio elegido?

Arnés de `docs_estela/experimentos/EXP-010-reconocimiento-ejercicio.md`. Mide si la sesión puede avisar «ese no es el ejercicio» sin falsas alarmas, y si el DTW aporta algo frente a una línea base sin DTW.

No toca `estela/` ni añade dependencias.

| Archivo | Qué es |
|---|---|
| `extraer.py` | Una pasada de pose por vídeo del banco (`BANCO`) con el pipeline de la sesión. Guarda las medidas por frame en `cache/` |
| `reconocer.py` | Simula, por cada vídeo y cada ejercicio «elegido», cuándo saltaría el aviso. Compara tres detectores: `segmentadores` (sin DTW), `dtw_propias` (referencias del catálogo) y `dtw_comun` (referencias con un vector común de medidas) |
| `probar_video.py` | Prueba con un vídeo propio: `--video RUTA --elegido jumping_jacks\|abduccion\|marcha_rodillas\|plancha`. Imprime los avisos que daría la sesión y una línea de tiempo con el coste de cada ejercicio. No guarda nada |
| `cache/`, `resultados/` | Ignorados por git: solo métricas derivadas, pero de personas reales |

## Comandos

Desde `ESTELA/`, con el entorno de `backend/` y el modelo de pose (`python backend/scripts/descargar_modelos.py`):

```bash
python PRUEBAS/exp010_reconocimiento/extraer.py          # ~10 min la primera vez
python PRUEBAS/exp010_reconocimiento/reconocer.py

# un vídeo propio (grabado fuera del repositorio)
python PRUEBAS/exp010_reconocimiento/probar_video.py --video "C:/ruta/mi_video.mp4" --elegido jumping_jacks
```

Solo se usan los vídeos de `docs_estela/investigacion/fuentes/datasets/videos/`. No se versionan.
