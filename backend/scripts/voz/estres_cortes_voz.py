"""Cola de voz real con Piper, en silencio, y cortes desde otros hilos: ¿se traba?

    .venv/bin/python scripts/voz/estres_cortes_voz.py 120 2>&1 | grep -c PaMacCore

2026-11-20, Mac: con `sd.play`/`sd.stop` 240 errores de CoreAudio en 120 cortes; con
`ReproductorContinuo`, 0. No suena: cada frase se cambia por silencio del mismo largo.
"""
import io, random, sys, threading, time, wave, glob
sys.path.insert(0, ".")
import numpy as np
from estela import config
from estela.adaptadores.voz.cola import ColaVoz
from estela.adaptadores.voz.motores import VozPiper
from estela.aplicacion.puertos import PRIORIDAD_AVISO, PRIORIDAD_FEEDBACK

m = VozPiper(sorted(glob.glob("modelos/voces/*.onnx"))[0])
orig = m._sintetizar
def mudo(texto):                       # mismo largo, sin sonido
    wav = orig(texto)
    with wave.open(io.BytesIO(wav)) as r:
        n, fs = r.getnframes(), r.getframerate()
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(fs); w.writeframes(np.zeros(n, np.int16).tobytes())
    return b.getvalue()
m._sintetizar = mudo
cola = ColaVoz(m)
frases = ["En pausa.", "Seguimos.", "Sube un poco más las caderas.", "Ahora, plancha. 8 segundos. Colócate de perfil a la cámara.",
          "Rutina terminada. Buen trabajo."]
random.seed(1); trabas = 0; t0 = time.perf_counter()
for i in range(int(sys.argv[1]) if len(sys.argv) > 1 else 120):
    cola.decir(random.choice(frases), random.choice([PRIORIDAD_AVISO, PRIORIDAD_FEEDBACK]))
    time.sleep(random.uniform(0.0, 0.6))
    # como «Estela, pausa»: la escucha corta y el orquestador vuelve a cortar enseguida
    hs = [threading.Thread(target=cola.interrumpir) for _ in range(random.choice([1, 2, 3]))]
    for h in hs: h.start()
    for h in hs: h.join(timeout=5)
    if any(h.is_alive() for h in hs):
        trabas += 1; print("interrumpir no volvió en 5 s, vuelta", i, flush=True)
    fin = time.monotonic() + 8
    while cola.ocupada and time.monotonic() < fin: time.sleep(0.01)
    if cola.ocupada:
        trabas += 1; print("la cola quedó ocupada > 8 s, vuelta", i, flush=True); break
print(f"vueltas={i+1} trabas={trabas} interrumpidas={cola.interrumpidas} {time.perf_counter()-t0:.0f} s", flush=True)
import os; os._exit(0)
