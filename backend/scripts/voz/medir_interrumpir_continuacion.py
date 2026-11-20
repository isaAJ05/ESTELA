"""Interrumpir a ESTELA con la voz: ¿la primera ventana con «Estela» trae la orden?

    .venv/bin/python scripts/voz/medir_interrumpir_continuacion.py SALIDA.json

Como `medir_interrumpir.py` (Piper + voces `say`, sin eco de sala), pero sigue la
lógica de la app: actúa la **primera** ventana que oye «Estela» (después ESTELA
se calla y las ventanas siguientes ya no existen). Compara:
- «antes»: si esa ventana no traía orden, ESTELA se calla y la orden ya dicha se
  pierde (Paula, 2026-11-20: «se calla pero no sigue la orden»).
- «con continuación de N s»: si no traía orden, se reconoce esa ventana junto con
  los N s siguientes, ya sin la voz de ESTELA (se calló al oír «Estela»).
"""
import json, sys, time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import medir_interrumpir as m   # noqa: E402
from estela import config  # noqa: E402
from estela.aplicacion import comandos_voz as cv  # noqa: E402
from estela.adaptadores.voz_entrada.reconocedor import PISTA_LLAMADA, ReconocedorWhisperCpp  # noqa: E402

FS = m.FS
ORDENES = {"pausa": cv.PAUSA, "siguiente": cv.SIGUIENTE, "terminar": cv.TERMINAR,
           "¿cómo voy?": cv.COMO_VOY}
CONTINUACIONES = (1.0, 1.5)


def main():
    rec = ReconocedorWhisperCpp(config.modelo_voz_entrada(), pista=PISTA_LLAMADA)
    tts = [m.piper(t) for t in m.ESTELA]
    filas = []
    t0 = time.perf_counter()
    for voz in m.VOCES:
        for palabra, esperado in ORDENES.items():
            orden = m.say(voz, f"Estela, {palabra}.")
            for k, x in enumerate(tts):
                base = x / m.rms(x) * 0.05
                for db in m.NIVELES_DB:
                    o = orden / m.rms(orden) * 0.05 * 10 ** (db / 20)
                    ini = FS
                    largo = max(len(base), ini + len(o)) + 2 * FS
                    estela = np.zeros(largo, np.float32); estela[:len(base)] = base
                    usuaria = np.zeros(largo, np.float32); usuaria[ini:ini + len(o)] = o
                    mezcla = estela + usuaria
                    fila = {"voz": voz, "orden": palabra, "frase": k, "db": db, "corta": False}
                    for fin, v in m.ventanas(mezcla):
                        llamado, resto = cv.buscar_llamada(rec.transcribir(v))
                        if not llamado:
                            continue
                        fila["corta"] = True
                        c0 = cv.interpretar(resto).comando
                        fila["antes"] = c0 == esperado
                        b = int(fin * FS)
                        for s in CONTINUACIONES:
                            if c0 is not None:
                                fila[f"cont_{s}"] = c0 == esperado
                                continue
                            extra = usuaria[b:b + int(s * FS)]     # ESTELA ya callada
                            l2, r2 = cv.buscar_llamada(rec.transcribir(np.concatenate([v, extra])))
                            fila[f"cont_{s}"] = bool(l2) and cv.interpretar(r2).comando == esperado
                        break
                    filas.append(fila)
    res = {"segundos": round(time.perf_counter() - t0), "por_nivel": {}}
    for db in m.NIVELES_DB:
        f = [r for r in filas if r["db"] == db]
        c = [r for r in f if r["corta"]]
        res["por_nivel"][f"{db:+d} dB"] = {
            "casos": len(f), "se_calla": len(c),
            "hace_la_orden_antes": sum(r["antes"] for r in c),
            **{f"hace_la_orden_cont_{s}s": sum(r[f"cont_{s}"] for r in c) for s in CONTINUACIONES}}
    res["filas"] = filas
    json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "filas"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
