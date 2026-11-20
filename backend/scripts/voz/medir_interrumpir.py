"""¿Se entiende «Estela, <orden>» mientras ESTELA habla? Audio sintético (Mac).

Voz de ESTELA: Piper. Usuaria: voces `say` (Paulina, Mónica). La orden empieza a
1,0 s de la frase de ESTELA, con su volumen relativo a ella en dB. Se reconoce
como en la app (ventanas de 2,5 s cada 1,0 s, Whisper small con la pista de
llamada) y se aplica `buscar_llamada` + `interpretar`. No hay eco de sala,
distancia ni micrófono real: es un límite optimista en lo acústico.
Uso (desde ESTELA/backend): .venv/bin/python scripts/voz/medir_interrumpir.py SALIDA.json

Versión del 2026-11-20 (la usuaria manda sobre lo que dice ESTELA): «Estela» la
calla siempre y vale cualquier orden, así que además de la orden correcta se
cuenta si ESTELA se habría callado (`corta`: alguna ventana con «Estela») y las
falsas llamadas con ESTELA sola (cualquier «Estela», no solo con orden). Se
añaden «Estela» a secas y «Estela, ¿cómo voy?». La primera versión (2026-11-17)
está en `resultados/comparacion-8gb/` del Mac.
"""
import glob, io, json, os, subprocess, sys, tempfile, time, wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from estela import config
from estela.aplicacion import comandos_voz as cv
from estela.adaptadores.voz.motores import con_pronunciacion
from estela.adaptadores.voz_entrada.reconocedor import PISTA_LLAMADA, ReconocedorWhisperCpp

FS = 16000
ESTELA = [
    "Has hecho 3 repeticiones de jumping jacks. No se han dado avisos. Te propongo seguir con el siguiente ejercicio.",
    "Ahora, abducción de cadera de pie, pierna izquierda. 8 repeticiones. Colócate de frente a la cámara.",
    "Has hecho 5 segundos de plancha. Se te avisó 1 vez para bajar la cadera. Hoy es el día 1 de racha.",
    "Endereza un poco el tronco, se va hacia la derecha.",
    "Sube los brazos hasta arriba, sin forzar.",
    "Ya te veo bien. Empieza cuando quieras.",
]
ORDENES = {"pausa": cv.PAUSA, "siguiente": cv.SIGUIENTE, "terminar": cv.TERMINAR,
           "¿cómo voy?": cv.COMO_VOY, "": None}          # "" = «Estela» a secas
VOCES = ["Paulina", "Mónica"]
NIVELES_DB = [6, 0, -6, -12]


def leer_wav(b):
    with wave.open(io.BytesIO(b)) as r:
        x = np.frombuffer(r.readframes(r.getnframes()), np.int16).astype(np.float32) / 32768
        fs = r.getframerate()
    if fs != FS:
        t = np.arange(0, len(x) / fs, 1 / FS)
        x = np.interp(t, np.arange(len(x)) / fs, x).astype(np.float32)
    return x


def piper(texto):
    from piper import PiperVoice
    global _voz
    if "_voz" not in globals():
        _voz = PiperVoice.load(sorted(glob.glob("modelos/voces/*.onnx"))[0])
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        _voz.synthesize_wav(con_pronunciacion(texto), w)
    return leer_wav(b.getvalue())


def say(voz, texto):
    with tempfile.TemporaryDirectory() as d:
        ruta = os.path.join(d, "x.wav")
        subprocess.run(["say", "-v", voz, "-o", ruta, "--data-format=LEI16@16000", texto], check=True)
        return leer_wav(open(ruta, "rb").read())


def rms(x):
    return float(np.sqrt(np.mean(x ** 2))) + 1e-9


def ventanas(x, ventana=2.5, paso=1.0):
    fin = paso
    while True:
        a = max(0, int((fin - ventana) * FS)); b = int(fin * FS)
        yield fin, x[a:min(b, len(x))]
        if b >= len(x):
            break
        fin += paso


def detecta(rec, x):
    """[(fin_ventana, comando o None, texto)] de las ventanas con «Estela»: en la
    app, cada una calla a ESTELA; con orden, además se ejecuta."""
    hallado = []
    for fin, v in ventanas(x):
        texto = rec.transcribir(v)
        llamado, resto = cv.buscar_llamada(texto)
        if llamado:
            hallado.append((fin, cv.interpretar(resto).comando, texto))
    return hallado


def main():
    rec = ReconocedorWhisperCpp(config.modelo_voz_entrada(), pista=PISTA_LLAMADA)
    tts = [piper(t) for t in ESTELA]
    filas, falsas = [], []
    for k, x in enumerate(tts):                       # ESTELA sola: ¿se toma por orden?
        for fin, c, texto in detecta(rec, x / rms(x) * 0.05):
            falsas.append({"frase": k, "comando": c, "texto": texto})
    t0 = time.perf_counter()
    for voz in VOCES:
        for palabra, esperado in ORDENES.items():
            orden = say(voz, f"Estela, {palabra}." if palabra else "Estela.")
            for k, x in enumerate(tts):
                base = x / rms(x) * 0.05
                for db in NIVELES_DB:
                    o = orden / rms(orden) * 0.05 * 10 ** (db / 20)
                    ini = FS                          # a 1,0 s
                    mezcla = np.concatenate([base, np.zeros(max(0, ini + len(o) - len(base)), np.float32)])
                    mezcla[ini:ini + len(o)] += o
                    mezcla = np.concatenate([mezcla, np.zeros(FS, np.float32)])   # 1 s de cola
                    fin_orden = (ini + len(o)) / FS
                    h = detecta(rec, mezcla)
                    buenos = [f for f, c, _ in h if c == esperado]
                    filas.append({"voz": voz, "orden": palabra or "(solo Estela)", "frase": k, "db": db,
                                  "corta": bool(h),
                                  "corta_s": round(h[0][0] - ini / FS, 2) if h else None,
                                  "acierto": bool(buenos),
                                  "otra": any(c is not None and c != esperado for _, c, _ in h),
                                  "latencia_s": round(buenos[0] - fin_orden, 2) if buenos else None})
    res = {"segundos": round(time.perf_counter() - t0), "falsas_con_estela_sola": falsas,
           "ventanas_estela_sola": sum(1 for x in tts for _ in ventanas(x)), "por_nivel": {}}
    for db in NIVELES_DB:
        f = [r for r in filas if r["db"] == db]
        lat = [r["latencia_s"] for r in f if r["acierto"]]
        cs = [r["corta_s"] for r in f if r["corta"]]
        res["por_nivel"][f"{db:+d} dB"] = {
            "se_calla": f"{sum(r['corta'] for r in f)}/{len(f)}",
            "se_calla_p50_s_desde_inicio_orden": float(np.median(cs)) if cs else None,
            "aciertos": f"{sum(r['acierto'] for r in f)}/{len(f)}",
            "otra_orden": sum(r["otra"] for r in f),
            "latencia_p50_s": float(np.median(lat)) if lat else None,
            "latencia_max_s": max(lat) if lat else None}
    res["filas"] = filas
    json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "filas"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
