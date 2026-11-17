"""Resume lo que dejó la prueba de voz y propone qué añadir al léxico.

    python scripts/voz/analizar_tanda_voz.py --registro microfono.jsonl [--log sesion.log]

Lee el `.jsonl` de `probar_microfono.py --registro` y/o el `sesion.log` de la sesión
(las líneas «Voz: «…» → …», «Voz oída: …» y «Voz ignorada …») y cuenta: llamadas,
órdenes entendidas, no entendidas, «Estela» solas, frases ignoradas, alucinaciones de
Whisper (texto larguísimo o repetido), volumen bajo y tiempos de reconocimiento.
Además propone:
- **Grafías de «Estela»**: primeras palabras parecidas a «Estela» que hoy no cuentan como llamada.
- **Órdenes por añadir**: lo que se dijo tras «Estela» y no se entendió como orden.

No cambia nada: solo imprime. Añadir una forma al léxico es decisión de quien revisa.
El `.jsonl` guarda el texto de lo que dijiste (la aplicación, en cambio, no guarda el
de lo que ignora): trátalo como un archivo personal y no lo subas al repositorio.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ))

from estela.adaptadores.voz_entrada.frases import RMS_MINIMO  # noqa: E402
from estela.aplicacion import comandos_voz as cv  # noqa: E402
from estela.aplicacion.entrenadora import menciona_dolor  # noqa: E402

_LOG_INFO = re.compile(r"Voz: «(?P<t>.*)» → (?P<c>\S+) \((?P<m>[a-z_]+), (?P<ms>\d+) ms\)")
_LOG_RESUMEN = re.compile(r"Voz oída: «(?P<t>.*)» → (?P<c>\S+) \((?P<ms>\d+) ms\)")
_LOG_IGNORADA = re.compile(r"Voz ignorada \(sin «Estela»\): (?P<n>\d+) palabras \((?P<ms>\d+) ms\)")


def cargar_jsonl(ruta: Path) -> List[Dict[str, Any]]:
    filas = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            filas.append(json.loads(linea))
    return filas


def cargar_log(ruta: Path) -> List[Dict[str, Any]]:
    """Frases que aparecen en el registro de una sesión (dos formatos y las ignoradas)."""
    filas = []
    vistas = set()
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        if (m := _LOG_IGNORADA.search(linea)):
            filas.append({"texto": None, "ignorada": True, "palabras": int(m["n"]),
                          "reconocer_ms": int(m["ms"])})
        elif (m := _LOG_INFO.search(linea)):
            filas.append({"texto": m["t"], "comando": None if m["c"] == "None" else m["c"],
                          "motivo": m["m"], "reconocer_ms": int(m["ms"])})
            vistas.add((m["t"], int(m["ms"])))
        elif (m := _LOG_RESUMEN.search(linea)):
            if (m["t"], int(m["ms"])) in vistas:         # ya salió en la línea de `log.info`
                continue
            filas.append({"texto": m["t"], "comando": None if m["c"] in ("None", "") else m["c"],
                          "reconocer_ms": int(m["ms"])})
    return filas


def _percentil(valores: List[float], q: float) -> Optional[float]:
    if not valores:
        return None
    v = sorted(valores)
    return v[min(len(v) - 1, int(round(q / 100 * (len(v) - 1))))]


def es_alucinacion(texto: str) -> bool:
    """Texto larguísimo o con una palabra repetida muchas veces seguidas."""
    palabras = cv._limpiar(texto).split()
    if len(palabras) > 25:
        return True
    racha = 1
    for a, b in zip(palabras, palabras[1:]):
        racha = racha + 1 if a == b else 1
        if racha >= 4:
            return True
    return len(palabras) >= 8 and len(set(palabras)) / len(palabras) < 0.35


def grafias_de_estela(textos: List[str]) -> List[str]:
    """Primeras palabras parecidas a «Estela» que hoy no cuentan como llamada y van
    seguidas de una orden (o van solas): lo que hay que añadir a `LLAMADAS`. Sin ese
    filtro saldrían palabras comunes («esta», «este») que no son una llamada."""
    candidatas: Counter = Counter()
    for t in textos:
        if cv.separar_llamada(t)[0]:
            continue
        palabras = cv._limpiar(t).split()
        i = 1 if palabras and palabras[0] in cv._ANTES_DE_LLAMAR else 0
        if i >= len(palabras):
            continue
        w, resto = palabras[i], " ".join(palabras[i + 1:])
        parecida = difflib.SequenceMatcher(None, w, "estela").ratio() >= 0.6
        if parecida and (not resto or cv.interpretar(resto).comando is not None):
            candidatas[w] += 1
    return [f"{w} ({n})" for w, n in candidatas.most_common()]


def analizar(filas: List[Dict[str, Any]]) -> Dict[str, Any]:
    con_texto = [f for f in filas if f.get("texto") is not None]
    ignoradas_log = [f for f in filas if f.get("ignorada")]
    llamadas, solas, ordenes, sin_orden, no_llamadas, huecos = [], 0, Counter(), [], [], []
    halluc, bajos = [], 0
    for f in con_texto:
        t = f["texto"]
        llamado, resto = cv.separar_llamada(t)
        if es_alucinacion(t):
            halluc.append(t)
        rms = f.get("volumen_rms")
        if rms is not None and rms < 1.5 * RMS_MINIMO:
            bajos += 1
        if not llamado:
            no_llamadas.append(t)
            continue
        llamadas.append(t)
        if not resto:
            solas += 1
            continue
        i = cv.interpretar(resto)
        if i.comando:
            ordenes[i.comando] += 1
        elif i.pedir_repetir and not menciona_dolor(resto):
            sin_orden.append(resto)
        else:
            huecos.append(resto)
    ms = [f["reconocer_ms"] for f in filas if f.get("reconocer_ms") is not None]
    return {
        "frases_con_texto": len(con_texto), "ignoradas_sin_texto": len(ignoradas_log),
        "sin_estela": len(no_llamadas) + len(ignoradas_log), "con_estela": len(llamadas),
        "estela_sola": solas, "ordenes": dict(ordenes), "sin_orden_clara": sin_orden,
        "alucinaciones": halluc, "volumen_bajo": bajos,
        "grafias_de_estela": grafias_de_estela(no_llamadas),
        "ms_p50": _percentil(ms, 50), "ms_p95": _percentil(ms, 95),
        "dolor": sum(1 for t in llamadas if menciona_dolor(cv.separar_llamada(t)[1])),
    }


def informe(an: Dict[str, Any]) -> str:
    L = ["# Voz de entrada: resumen de la prueba", "",
         f"- Frases con texto: {an['frases_con_texto']} (más {an['ignoradas_sin_texto']} "
         "ignoradas de las que solo se guardó cuántas palabras tenían)",
         f"- Con «Estela»: {an['con_estela']} (solo «Estela»: {an['estela_sola']}); "
         f"sin «Estela»: {an['sin_estela']}",
         f"- Órdenes entendidas: {sum(an['ordenes'].values())} "
         + (", ".join(f"{c} {n}" for c, n in sorted(an['ordenes'].items())) or "ninguna"),
         f"- Con «Estela» pero sin orden clara: {len(an['sin_orden_clara'])}",
         f"- Con «Estela» que mencionan dolor: {an['dolor']}",
         f"- Volumen bajo (< 1,5 × el mínimo): {an['volumen_bajo']}",
         "- Reconocer: p50 "
         + (f"{an['ms_p50']:.0f} ms, p95 {an['ms_p95']:.0f} ms" if an["ms_p50"] is not None else "no medido")]
    L += ["", "## Alucinaciones de Whisper (texto larguísimo o repetido)"]
    L += [f"- «{t[:80]}»" for t in an["alucinaciones"]] or ["- ninguna"]
    L += ["", "## Posibles grafías de «Estela» que hoy no cuentan como llamada",
          "(si de verdad dijiste «Estela», añadir a `comandos_voz.LLAMADAS`)"]
    L += [f"- {g}" for g in an["grafias_de_estela"]] or ["- ninguna"]
    L += ["", "## Dijiste «Estela» y no se entendió una orden",
          "(si era una orden, añadir la forma a `comandos_voz.LEXICO`)"]
    L += [f"- «{t}»" for t in an["sin_orden_clara"]] or ["- ninguna"]
    return "\n".join(L)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--registro", type=Path, help="el .jsonl de probar_microfono.py")
    p.add_argument("--log", type=Path, help="el sesion.log de la sesión")
    a = p.parse_args(argv)
    if not a.registro and not a.log:
        p.error("falta --registro o --log")
    filas: List[Dict[str, Any]] = []
    for ruta, cargar in ((a.registro, cargar_jsonl), (a.log, cargar_log)):
        if ruta:
            if not ruta.exists():
                print(f"No existe {ruta}")
                return 2
            filas += cargar(ruta)
    print(informe(analizar(filas)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
