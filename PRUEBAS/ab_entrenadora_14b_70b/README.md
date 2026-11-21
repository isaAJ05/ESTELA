# Prueba A/B de la entrenadora: `qwen3:14b` contra `llama3.3:70b`

Comparación **a ciegas** de lo que diría la entrenadora con cada modelo en 20 situaciones (resumen entre ejercicios, resumen final, «¿cómo voy?», dolor y una orden ambigua). Generada en el Mac Studio el 2026-11-16 con `backend/scripts/hoja_ab.py` (rama `feature/mac-flujo`).

- `hoja_ab.csv`: la hoja para calificar. En cada fila: `datos_que_recibio`, `respuesta_A`, `respuesta_B`; se llena `mejor_A_B_o_igual` (A, B o igual) y una **x** en `A_dice_algo_falso`, `B_dice_algo_falso`, `A_no_suena_natural` o `B_no_suena_natural` cuando aplique, más `notas`.
- `clave_NO_ABRIR/clave_ab.json`: qué modelo es A y cuál es B en cada fila. **No abrirla antes de calificar.**

En las situaciones de dolor y de orden ambigua la app real no usa el modelo (respuesta fija o «No te entendí»); ahí solo se ve qué diría cada uno sin ese filtro.

Estado (2026-11-20): **sin calificar**. Medido al generarla, en el Mac: 14B p50 1,2 s y máx 2,0 s; 70B p50 3,3 s y máx 5,4 s (una vez pasó el límite de 5 s de la entrenadora). La app usa el 14B; el 70B no corre en la sesión.
