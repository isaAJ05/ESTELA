"""Mide cómo escribe Whisper «Estela» con distintas pistas de vocabulario (solo macOS).

    python scripts/voz/medir_llamada.py [--pistas actual,llamada,sin_pista]
                                        [--voces Paulina,Mónica] [--salida resultado.json]

Sintetiza con `say` frases con «Estela» (con su orden), frases sin ella y ruidos
sintéticos (aleatorio, golpes secos, grave), las pasa por Whisper con cada pista y
cuenta: llamadas detectadas, órdenes correctas y **falsas llamadas con ruido**
(lo que más importa: un «Estela» inventado en pleno ejercicio).

Qué es y qué no es `[F]`: audio sintético; no es la voz de Paula ni un micrófono real.
Sirve para comparar pistas entre sí y para repetir la medición con otro modelo. La
medición del 2026-11-16 (voces Paulina y Mónica) está en `reconocedor.PISTA_LLAMADA`.
Los tiempos son solo del reconocimiento (sin contar la síntesis de la voz).

No guarda audio: los clips son temporales y se borran al terminar.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path
from typing import Dict, List, Optional

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ))

from estela.aplicacion import comandos_voz as cv  # noqa: E402

CON_ESTELA = [
    ("Estela, pausa", cv.PAUSA), ("Estela, seguir", cv.SEGUIR),
    ("Oye Estela, siguiente", cv.SIGUIENTE), ("Estela, anterior", cv.ANTERIOR),
    ("Estela, reiniciar ejercicio", cv.REINICIAR_EJERCICIO),
    ("Estela, reiniciar sesión", cv.REINICIAR_SESION),
    ("Estela, activa los ángulos", cv.ANGULOS_SI), ("Estela, desactiva los ángulos", cv.ANGULOS_NO),
    ("Estela, reconocer activado", cv.RECONOCER_SI), ("Estela, reconocer desactivado", cv.RECONOCER_NO),
    ("Estela, terminar", cv.TERMINAR), ("Estela, ¿cómo voy?", cv.COMO_VOY),
    ("Estela", None),
]
SIN_ESTELA = ["Hola, buenos días", "Qué calor hace hoy", "Pausa", "Siguiente ejercicio por favor",
              "Me gusta mucho esta canción", "Voy a comer algo luego",
              "La estrella brilla esta noche", "Ella dijo que no viene"]


def pistas() -> Dict[str, Optional[str]]:
    from estela.adaptadores.voz_entrada.reconocedor import PISTA, PISTA_LLAMADA
    return {
        "actual": PISTA,
        "llamada": PISTA_LLAMADA,
        # descartada el 2026-11-16: con «Estela» en cada orden, Whisper la escribía sobre ruido
        "estela_repetida": ("Estela, pausa. Estela, seguir. Oye Estela, siguiente. Estela, anterior. "
                            "Estela, reiniciar ejercicio. Estela, reiniciar sesión. "
                            "Estela, ángulos activados. Estela, reconocer desactivado. "
                            "Estela, terminar. Estela, ¿cómo voy?"),
        "sin_pista": None,
    }


def ruidos(rng, np) -> List[tuple]:
    salida = []
    for amp in (0.02, 0.05, 0.1, 0.2):
        for _ in range(3):
            salida.append((f"aleatorio {amp}", rng.normal(0, amp, 32000).astype(np.float32)))
    for _ in range(6):
        g = np.zeros(32000, np.float32)
        for pos in rng.integers(2000, 30000, 4):
            g[pos:pos + 400] += rng.normal(0, 0.4, 400).astype(np.float32)
        salida.append(("golpes secos", g))
        b = np.cumsum(rng.normal(0, 0.01, 32000)).astype(np.float32)
        salida.append(("grave", b - np.convolve(b, np.ones(800) / 800, "same")))
    return salida


def clip(voz: str, texto: str, carpeta: Path, np):
    ruta = carpeta / f"{abs(hash((voz, texto)))}.wav"
    subprocess.run(["say", "-v", voz, "-o", str(ruta), "--data-format=LEI16@16000", texto], check=True)
    with wave.open(str(ruta)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return np.concatenate([np.zeros(8000, np.float32), a, np.zeros(8000, np.float32)])


def correr(nombre: str, pista: Optional[str], voces: List[str], carpeta: Path) -> dict:
    import numpy as np
    from estela import config
    from estela.adaptadores.voz_entrada.reconocedor import ReconocedorWhisperCpp
    r = ReconocedorWhisperCpp(config.modelo_voz_entrada(), pista=pista)
    r.precalentar()
    out: dict = {"pista": nombre, "con": [], "sin": [], "ruido": [], "ms": []}
    for v in voces:
        for texto, esperado in CON_ESTELA:
            audio = clip(v, texto, carpeta, np)
            t0 = time.perf_counter()
            oido = r.transcribir(audio)
            out["ms"].append((time.perf_counter() - t0) * 1000)
            llamado, resto = cv.separar_llamada(oido)
            comando = cv.interpretar(resto).comando if llamado else None
            out["con"].append({"voz": v, "dicho": texto, "oyo": oido, "llamada": llamado,
                               "ok": bool(llamado and comando == esperado)})
        for texto in SIN_ESTELA:
            oido = r.transcribir(clip(v, texto, carpeta, np))
            out["sin"].append({"voz": v, "dicho": texto, "oyo": oido,
                               "llamada": cv.separar_llamada(oido)[0]})
    for tipo, audio in ruidos(np.random.default_rng(0), np):
        oido = r.transcribir(audio)
        out["ruido"].append({"tipo": tipo, "oyo": oido, "llamada": cv.separar_llamada(oido)[0]})
    return out


def resumen(o: dict) -> str:
    import numpy as np
    con, sin, ruido = o["con"], o["sin"], o["ruido"]
    esperables = len([1 for _, c in CON_ESTELA if c is not None]) * (len(con) // len(CON_ESTELA))
    lineas = [f"== pista {o['pista']}",
              f"  con «Estela»: llamada detectada {sum(x['llamada'] for x in con)}/{len(con)}; "
              f"orden correcta {sum(x['ok'] for x in con if x['dicho'] != 'Estela')}/{esperables}",
              f"  sin «Estela»: falsa llamada {sum(x['llamada'] for x in sin)}/{len(sin)}",
              f"  ruido: falsa llamada {sum(x['llamada'] for x in ruido)}/{len(ruido)}; "
              f"con algún texto {sum(bool(x['oyo']) for x in ruido)}/{len(ruido)}",
              f"  reconocer p50 {np.percentile(o['ms'], 50):.0f} ms, p95 {np.percentile(o['ms'], 95):.0f} ms"]
    lineas += [f"   falla: {x['voz']} | {x['dicho']} → {x['oyo']!r}" for x in con if not x["ok"]
               and x["dicho"] != "Estela"]
    lineas += [f"   falsa llamada: {x['voz']} | {x['dicho']} → {x['oyo'][:60]!r}" for x in sin if x["llamada"]]
    lineas += [f"   ruido {x['tipo']} → {x['oyo'][:60]!r}" for x in ruido if x["oyo"]]
    return "\n".join(lineas)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pistas", default="actual,llamada,sin_pista",
                   help="nombres separados por coma: actual, llamada, estela_repetida, sin_pista")
    p.add_argument("--voces", default="Paulina,Mónica", help="voces de `say` separadas por coma")
    p.add_argument("--salida", type=Path, help="guardar el resultado completo en JSON")
    a = p.parse_args(argv)
    if platform.system() != "Darwin" or not shutil.which("say"):
        print("Este script usa `say`: solo funciona en macOS.")
        return 2
    todas = pistas()
    elegidas = [n.strip() for n in a.pistas.split(",") if n.strip()]
    for n in elegidas:
        if n not in todas:
            print(f"Pista desconocida: {n}. Opciones: {', '.join(todas)}")
            return 2
    voces = [v.strip() for v in a.voces.split(",") if v.strip()]
    carpeta = Path(tempfile.mkdtemp(prefix="estela_llamada_"))
    try:
        resultados = [correr(n, todas[n], voces, carpeta) for n in elegidas]
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
    for o in resultados:
        print(resumen(o))
    if a.salida:
        a.salida.write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nResultado completo en {a.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
