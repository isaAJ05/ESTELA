"""Imprime la tabla de `evaluar_reconocedores.py` y, con --fallos, qué clips fallaron."""
import json
import sys

R = json.load(open(sys.argv[1]))
print(R["clips"], "clips; duración media", R["duracion_media_s"], "s")
for f in R["filas"]:
    if "error" in f:
        print(f["motor"], f["modelo"], "NO DISPONIBLE:", f["error"][:120])
        continue
    print("{:10} {:15} pista={} carga {:5.1f} s | p50 {:5d} p95 {:5d} máx {:5d} ms | órdenes {}/{} (limpio {}/{}) equivocadas {} | "
          "falsas {}/{} | repetir en silencio {} | {}".format(
              f["motor"], f["modelo"], int(f["pista"]), f["carga_s"], f["lat_p50_ms"], f["lat_p95_ms"], f["lat_max_ms"],
              f["acertadas"], f["ordenes"], f["acertadas_limpio"], f["ordenes_limpio"], f["orden_equivocada"],
              f["orden_falsa"], f["sin_orden"], f["pide_repetir_en_silencio"], f["desc"]))
    if len(sys.argv) > 2 and sys.argv[2] == "--fallos" and (len(sys.argv) < 4 or sys.argv[3] in f["motor"] + ":" + f["modelo"]):
        for d in f["fallos"]:
            print("      {:22} {:9} {:7} «{}» → «{}» = {}".format(d["voz"], d["condicion"], "", d["frase"], d["texto"], d["comando"]))
