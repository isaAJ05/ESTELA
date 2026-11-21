# Audio sintético de órdenes de voz

Nadie fue grabado. Son frases sintetizadas con Piper (voz `es_MX-claude-high`) por
`scripts/voz/generar_audio_comandos.py` el 2026-11-16: 16 kHz, mono, con medio segundo de
silencio antes y después. `silencio.wav` son dos segundos de ceros.

| Archivo | Frase | Orden esperada |
|---|---|---|
| `pausa.wav` | «Pausa.» | pausa |
| `seguir.wav` | «Seguir.» | seguir |
| `siguiente.wav` | «Siguiente.» | siguiente |
| `repetir.wav` | «Repetir.» | repetir |
| `terminar.wav` | «Terminar.» | terminar |
| `como_voy.wav` | «¿Cómo voy?» | como_voy |
| `sin_orden.wav` | «Hola, buenos días.» | ninguna: se pide repetir |
| `dolor.wav` | «Me duele la rodilla.» | ninguna: respuesta fija de dolor |
| `silencio.wav` | — | ninguna: no se dice nada |
