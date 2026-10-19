"""EXP-010 · Probar el reconocedor con un vídeo propio.

Desde ESTELA/, con el entorno de backend/:

    python PRUEBAS/exp010_reconocimiento/probar_video.py --video RUTA.mp4 --elegido jumping_jacks

Simula que en la sesión se eligió `--elegido` y dice en qué segundo saltaría
el aviso «ese no es el ejercicio», con el detector recomendado en EXP-010 §7
(`dtw_comun+seg`, τ_no 0,75 · τ_si 0,75 · ratio 0,7). Debajo imprime una
línea de tiempo cada `--paso` segundos para compararla con lo que se hizo de
verdad.

No guarda nada: la pose se calcula en memoria y se descarta. Graba los vídeos
fuera del repositorio (Ley 1581/2012, CLAUDE.md §6).

La primera vez extrae la pose de los 5 vídeos de referencia
(`docs_estela/.../datasets/videos/`) a `cache/`, unos minutos.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import extraer as E      # noqa: E402
import reconocer as R    # noqa: E402

NOMBRE = {"jumping_jacks": "jumping jacks", "abduccion": "abducción de cadera",
          "marcha_rodillas": "marcha con rodillas", "plancha": "plancha"}
#: también se aceptan los skill_id del catálogo
ALIAS = {"abduccion_cadera_izq": "abduccion", "abduccion_cadera_der": "abduccion"}


def _video(ruta: Path, modelo: str, clase: str = "?") -> R.Video:
    datos = E.extraer(ruta, modelo)
    with tempfile.TemporaryDirectory() as tmp:
        npz = Path(tmp) / "video.npz"
        np.savez(npz, clase=clase, lado="", es_ref=False, video=ruta.name, **datos)
        return R.Video(npz)


def _referencias(modelo: str):
    """Vídeos de referencia desde `cache/`; los que falten se extraen."""
    por_id = {vid: ruta for vid, ruta, *_ in E.BANCO}
    videos = {}
    for vid in R.VIDEO_REF.values():
        npz = R.CACHE / f"{vid}.npz"
        if not npz.exists():
            print(f"extrayendo la referencia {vid} ...", flush=True)
            R.CACHE.mkdir(exist_ok=True)
            fila = next(b for b in E.BANCO if b[0] == vid)
            np.savez_compressed(npz, clase=fila[2], lado=fila[3], es_ref=fila[4],
                                video=fila[1].name, **E.extraer(por_id[vid], modelo))
        videos[vid] = R.Video(npz)
    return videos


def _mensaje(etiqueta: str, elegido: str) -> str:
    toca = f"Ahora toca {NOMBRE[elegido]}."
    if etiqueta == "no_reconocido":
        return f"No reconozco ese movimiento. {toca}"
    return f"Parece que estás haciendo {NOMBRE[etiqueta]}. {toca}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--elegido", required=True, choices=(*R.CLASES, *ALIAS))
    p.add_argument("--modelo", default="lite", choices=("lite", "full", "heavy"))
    p.add_argument("--tau-no", type=float, default=0.75)
    p.add_argument("--tau-si", type=float, default=0.75)
    p.add_argument("--ratio", type=float, default=0.7)
    p.add_argument("--act-min", type=float, default=0.25)
    p.add_argument("--sin-seg", action="store_true",
                   help="no callar el aviso cuando el segmentador del elegido cuenta")
    p.add_argument("--paso", type=float, default=2.0, help="segundos entre filas de la línea de tiempo")
    a = p.parse_args()
    if not a.video.exists():
        p.error(f"no existe {a.video}")
    elegido = ALIAS.get(a.elegido, a.elegido)

    catalogo = R.cargar_catalogo()
    refs, _ = R.refs_comunes(catalogo, _referencias(a.modelo))
    print(f"analizando {a.video.name} ...", flush=True)
    v = _video(a.video, a.modelo)
    punt, _ = R.puntuar(v, refs)
    comp = R.completadas(v, catalogo)
    act = R.actividad(v)
    avisos = R.decidir(elegido, len(v), punt, comp, act, "dtw_comun",
                       a.tau_no, a.tau_si, a.act_min, not a.sin_seg, a.ratio)

    print(f"\nVídeo: {a.video.name} · {len(v) / R.FPS:.1f} s · persona visible "
          f"{v.presente.mean():.0%} · elegido: {NOMBRE[elegido]}")
    print(f"\n=== Avisos ({len(avisos)}) ===")
    for t, etiqueta in avisos:
        print(f"  {t:6.1f} s  {_mensaje(etiqueta, elegido)}")
    if not avisos:
        print("  ninguno")

    print("\n=== Línea de tiempo ===")
    print("  costes: menor = se parece más (con vector común; el elegido entre [ ])")
    print("     t   " + "  ".join(f"{c[:10]:>10s}" for c in R.CLASES)
          + "   parecido a       movimiento  reps del elegido")
    w = int(R.VENTANA_S * R.FPS)
    for i in range(int(R.CALENTAMIENTO_S * R.FPS), len(v), max(1, int(a.paso * R.FPS))):
        costes = {c: punt[c][i] for c in R.CLASES}
        celdas = "  ".join((f"[{x:8.2f}]" if c == elegido else f"{x:10.2f}")
                           if np.isfinite(x) else f"{'—':>10s}" for c, x in costes.items())
        finitos = {c: x for c, x in costes.items() if np.isfinite(x)}
        mejor = min(finitos, key=finitos.get) if finitos else "—"
        reps = int(comp[elegido][max(0, i - w + 1):i + 1].sum())
        mov = "sí" if act[i] >= a.act_min else "quieta"
        print(f"  {i / R.FPS:5.1f}  {celdas}   {mejor:16s} {mov:10s}  {reps}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
