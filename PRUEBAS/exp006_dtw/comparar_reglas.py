"""EXP-006 fase 1 (T32): reglas absolutas frente a reglas relativas a la referencia.

Desde ESTELA/, con el entorno de backend/ (necesita el modelo de pose):

    python PRUEBAS/exp006_dtw/comparar_reglas.py ruido
    python PRUEBAS/exp006_dtw/comparar_reglas.py banco [--k 2 3 4]

`ruido` estima el jitter de cada medida, el piso de ruido de ADR-004 §2.2, en
los frames quietos de los vídeos del banco (reposo; en la plancha, la
postura mantenida). Es la desviación típica robusta de la diferencia entre
frames consecutivos, dividida entre √2. Provisional hasta EXP-004.

`banco` es el **banco piloto semisintético**: vídeos públicos con
ejecuciones correctas y, sobre esa misma pose, errores inducidos en la
observación, con etiqueta conocida. Las tres condiciones ven la misma pose:

    absolutos            umbrales actuales de los skills
    referencia           formas relativas: DTW + extremos de la referencia
    referencia_sin_dtw   formas relativas sin DTW: las desviaciones caen al
                         respaldo absoluto y los extremos siguen

La unidad es la repetición: una regla «detecta» en una repetición si su
condición se cumple en algún frame de ella (después de `silenciada_por`).
No sustituye al banco grabado de T24/T26: un error inducido por software no es
un error real.

Escribe un JSON en `PRUEBAS/exp006_dtw/resultados/` y una tabla en Markdown.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import medir_dtw as M                                                   # noqa: E402
from estela.aplicacion import sesion as modulo_sesion                  # noqa: E402
from estela.aplicacion.metricas import percentil                       # noqa: E402
from estela.aplicacion.rutina import cargar_catalogo, rutina_de_un_ejercicio  # noqa: E402
from estela.aplicacion.umbrales import con_umbrales_de_referencia      # noqa: E402
from estela.dominio.conteo.segmentador import SegmentadorIsometrico    # noqa: E402
from estela.dominio.feedback.contrato import Observacion               # noqa: E402
from estela.dominio.feedback.motor.geometria import observacion_desde_pose  # noqa: E402

ESTELA = Path(__file__).resolve().parents[2]
_JJ = ESTELA / "PRUEBAS" / "Prueba red neuronal (dataset-pose-deteccion-conteo)" / "DATASET" / "videos" / "jumping_jack"
_DOCS = ESTELA.parent / "docs_estela" / "investigacion" / "fuentes" / "datasets" / "videos"
_ABD = _DOCS / "Abdución de caderas pies"

#: (skill, vídeo, papel). «referencia»: el vídeo del que salió la referencia, o
#: su versión sin cortar; «fuera»: otra persona u otro vídeo.
BANCO: Tuple[Tuple[str, Path, str], ...] = (
    *(("jumping_jacks", _JJ / f"{n}.mp4", "fuera") for n in (
        "1 hombre", "2 mujer", "3 mujer", "4 mujer", "5 hombre", "6 mujer", "8 hombre", "9 mujer")),
    ("jumping_jacks", _JJ / "7 hombre.mp4", "referencia"),
    ("abduccion_cadera_izq", _ABD / "izq-ok-abduccion-de-cadera-con-banda-tecnica-paso-a-paso-online-video-cutter_FovKZRDc.mp4", "referencia"),
    ("abduccion_cadera_izq", _ABD / "Abducción activa de cadera en bipedestación.mp4", "fuera"),
    ("abduccion_cadera_der", _ABD / "der ok Abducción de cadera con banda_ técnica paso a paso (online-video-cutter.com).mp4", "referencia"),
    ("abduccion_cadera_der", _ABD / "der Abducción de cadera con banda_ técnica paso a paso.mp4", "referencia"),
    ("abduccion_cadera_der", _ABD / "Abducción de cadera de pie con apoyo_ El ejercicio tras un ataque o derrame cerebral.mp4", "fuera"),
    ("abduccion_cadera_der", _ABD / "izquierda abductor.mp4", "fuera"),
    ("abduccion_cadera_der", _ABD / "der 876. Abducción de cadera con apoyo en silla.mp4", "fuera"),
    ("plancha", _DOCS / "Plancha" / "Ejercicio De Plancha.mp4", "referencia"),
)

CONDICIONES = ("absolutos", "referencia", "referencia_sin_dtw")


# ---------------------------------------------------------------------------
# Errores inducidos
# ---------------------------------------------------------------------------

def _valores(obs: Sequence[Observacion], nombre: str) -> List[float]:
    return [v for o in obs if (v := o.angulos.get(nombre, o.distancias.get(nombre))) is not None]


def _modifica(o: Observacion, nombres: Sequence[str], fn: Callable[[float], float]) -> Observacion:
    angulos, distancias = dict(o.angulos), dict(o.distancias)
    for n in nombres:
        if n in angulos:
            angulos[n] = fn(angulos[n])
        if n in distancias:
            distancias[n] = fn(distancias[n])
    return replace(o, angulos=angulos, distancias=distancias)


def amplitud(nombres: Sequence[str], alfa: float):
    """Recorta el recorrido hacia el reposo: x' = base + α·(x − base), con
    base = percentil 5 del vídeo. Brazos, pies o pierna que no llegan."""
    def construir(obs):
        bases = {n: percentil(_valores(obs, n), 5) for n in nombres}
        return lambda o: _modifica_por_nombre(o, {n: (lambda x, b=bases[n]: b + alfa * (x - b))
                                                  for n in nombres})
    return construir


def suma(nombres: Sequence[str], delta: float, guia: Optional[str] = None):
    """Suma `delta` a las medidas. Con `guia`, en proporción a cuánto se ha
    movido la medida guía (0 en reposo, 1 en el pico): una compensación que
    aparece al subir la pierna."""
    def construir(obs):
        if guia is None:
            return lambda o: _modifica(o, nombres, lambda x: x + delta)
        g = _valores(obs, guia)
        base, pico = percentil(g, 5), percentil(g, 95)

        def f(o):
            v = o.angulos.get(guia, o.distancias.get(guia))
            p = 0.0 if v is None else min(1.0, max(0.0, (v - base) / max(pico - base, 1e-6)))
            return _modifica(o, nombres, lambda x: x + delta * p)
        return f
    return construir


def _modifica_por_nombre(o: Observacion, fns: Dict[str, Callable[[float], float]]) -> Observacion:
    for n, fn in fns.items():
        o = _modifica(o, (n,), fn)
    return o


_TRONCO = ("inclinacion_lateral", "inclinacion_lateral_tronco")
_PELVIS = ("oblicuidad_pelvis", "inclinacion_pelvis")

#: skill -> [(variante, etiqueta, magnitud legible, transformación)]
VARIANTES: Dict[str, List[Tuple[str, Optional[str], str, Any]]] = {
    "jumping_jacks": [
        ("brazos_cortos", "brazos_no_llegan_arriba", "α 0,7", amplitud(["hombro_medio"], 0.7)),
        ("brazos_cortos", "brazos_no_llegan_arriba", "α 0,5", amplitud(["hombro_medio"], 0.5)),
        ("pies_cortos", "apertura_pies_insuficiente", "α 0,6",
         amplitud(["separacion_pies", "separacion_pies_hombros"], 0.6)),
        ("pies_cortos", "apertura_pies_insuficiente", "α 0,4",
         amplitud(["separacion_pies", "separacion_pies_hombros"], 0.4)),
        ("codos", "codos_flexionados", "−25°", suma(["codo_medio"], -25)),
        ("codos", "codos_flexionados", "−45°", suma(["codo_medio"], -45)),
    ],
    "abduccion_cadera_izq": [
        ("tronco", "tronco_inclinado_der", "−10°", suma(_TRONCO, -10, "abduccion_cadera_izq")),
        ("tronco", "tronco_inclinado_der", "−15°", suma(_TRONCO, -15, "abduccion_cadera_izq")),
        ("cadera", "cadera_izq_sube", "+6°", suma(_PELVIS, 6, "abduccion_cadera_izq")),
        ("cadera", "cadera_izq_sube", "+10°", suma(_PELVIS, 10, "abduccion_cadera_izq")),
        ("abduccion_corta", "abduccion_insuficiente_izq", "α 0,6",
         amplitud(["abduccion_cadera_izq"], 0.6)),
        ("abduccion_corta", "abduccion_insuficiente_izq", "α 0,4",
         amplitud(["abduccion_cadera_izq"], 0.4)),
    ],
    "abduccion_cadera_der": [
        ("tronco", "tronco_inclinado_izq", "+10°", suma(_TRONCO, 10, "abduccion_cadera_der")),
        ("tronco", "tronco_inclinado_izq", "+15°", suma(_TRONCO, 15, "abduccion_cadera_der")),
        ("cadera", "cadera_der_sube", "−6°", suma(_PELVIS, -6, "abduccion_cadera_der")),
        ("cadera", "cadera_der_sube", "−10°", suma(_PELVIS, -10, "abduccion_cadera_der")),
        ("abduccion_corta", "abduccion_insuficiente_der", "α 0,6",
         amplitud(["abduccion_cadera_der"], 0.6)),
        ("abduccion_corta", "abduccion_insuficiente_der", "α 0,4",
         amplitud(["abduccion_cadera_der"], 0.4)),
    ],
    "plancha": [
        ("cadera_hundida", "cadera_hundida", "+0,15", suma(["alineacion_cadera"], 0.15)),
        ("cadera_hundida", "cadera_hundida", "+0,25", suma(["alineacion_cadera"], 0.25)),
        ("cadera_elevada", "cadera_elevada", "−0,15", suma(["alineacion_cadera"], -0.15)),
        ("cadera_elevada", "cadera_elevada", "−0,25", suma(["alineacion_cadera"], -0.25)),
        ("cabeza", "cabeza_desalineada", "+15°", suma(["cabeza_adelantada"], 15)),
        ("cabeza", "cabeza_desalineada", "+25°", suma(["cabeza_adelantada"], 25)),
    ],
}


# ---------------------------------------------------------------------------
# Pose y observaciones
# ---------------------------------------------------------------------------

_CACHE: Dict[Path, Tuple[List[Any], List[int], float]] = {}


def pose(video: Path):
    if video not in _CACHE:
        print(f"  pose: {video.name}", flush=True)
        _CACHE[video] = M._pasar_pose(video, "full")
    return _CACHE[video]


def observaciones(skill_id: str, resultados) -> List[Observacion]:
    return [observacion_desde_pose(r.muestra, skill_id) for r in resultados if r.muestra is not None]


# ---------------------------------------------------------------------------
# ruido
# ---------------------------------------------------------------------------

def modo_ruido(args) -> Dict[str, Any]:
    catalogo = cargar_catalogo()
    por_medida: Dict[str, Dict[str, float]] = {}
    for skill_id, video, _ in BANCO:
        ej = catalogo[skill_id]
        resultados, _, _ = pose(video)
        seg = ej.nuevo_segmentador()
        quieta = (ej.segmentacion["fases"][1] if isinstance(seg, SegmentadorIsometrico)
                  else ej.segmentacion["fases"][0])
        medidas = set(ej.referencia.get("medidas", ())) if ej.referencia else set()
        medidas |= {n for r in ej.skill.reglas for n in r.medida.angulos_implicados()}
        previo: Optional[Observacion] = None
        difs: Dict[str, List[float]] = {}
        for r in resultados:
            if r.muestra is None:
                previo = None
                continue
            o = observacion_desde_pose(r.muestra, skill_id)
            if seg.actualizar(o).fase != quieta:
                previo = None
                continue
            if previo is not None:
                for n in medidas:
                    a = o.angulos.get(n, o.distancias.get(n))
                    b = previo.angulos.get(n, previo.distancias.get(n))
                    if (a is not None and b is not None and o.confianza_de(n) >= 0.5
                            and previo.confianza_de(n) >= 0.5):
                        difs.setdefault(n, []).append(a - b)
            previo = o
        for n, d in difs.items():
            if len(d) >= 20:
                mad = statistics.median(abs(x - statistics.median(d)) for x in d)
                por_medida.setdefault(n, {})[video.stem] = round(1.4826 * mad / np.sqrt(2), 4)
    resumen = {n: {"videos": v, "mediana": round(statistics.median(v.values()), 4),
                   "max": round(max(v.values()), 4)} for n, v in sorted(por_medida.items())}
    for n, r in resumen.items():
        print(f"  {n:28s} mediana {r['mediana']:8.4f}  máx {r['max']:8.4f}  ({len(r['videos'])} vídeos)")
    return {"entorno": M._entorno(), "ruido": resumen}


# ---------------------------------------------------------------------------
# banco
# ---------------------------------------------------------------------------

def _pasada(ej, catalogo, resultados, tiempos, transformar, sin_dtw: bool) -> Dict[str, Any]:
    """Una sesión sobre la pose grabada, con el error inducido en la observación."""
    original = modulo_sesion.observacion_desde_pose
    if transformar is not None:
        modulo_sesion.observacion_desde_pose = lambda m, sid: transformar(original(m, sid))
    try:
        s = modulo_sesion.Sesion(rutina_de_un_ejercicio(ej.skill.skill_id, 999, catalogo),
                                 catalogo, M._EstimadorGrabado(resultados), M._VozMuda(),
                                 sin_dtw=sin_dtw)
        decision = s.paso_actual.motor.decision
        disparos: Set[Tuple[int, str]] = set()
        evaluadas: Set[Tuple[int, str]] = set()
        frames = [0]
        candidatos_originales = decision._candidatos

        def registrar(obs):
            cand, motivos, ev = candidatos_originales(obs)
            frames[0] += 1
            rep = obs.repeticion or 0
            disparos.update((rep, c[0].error_id) for c in cand)
            evaluadas.update((rep, e) for e in ev)
            return cand, motivos, ev

        decision._candidatos = registrar
        for t_ms in tiempos:
            s.procesar(None, t_ms)
        paso = s.resumen()["pasos"][0]
        lat = s.latencias.resumen()
        return {"disparos": disparos, "evaluadas": evaluadas, "frames_motor": frames[0],
                "abstenciones": paso["abstenciones"], "respaldos": paso["respaldos"],
                "mensajes": [m["error_id"] for m in paso["mensajes"]],
                "dtw_ms": lat.get("dtw", {}), "motor_ms": lat.get("motor", {}),
                "completadas": paso["completadas"], "incompletas": paso["incompletas"]}
    finally:
        modulo_sesion.observacion_desde_pose = original


def _efectivos(disparos: Set[Tuple[int, str]], skill) -> Set[Tuple[int, str]]:
    """Quita los disparos que `silenciada_por` calla en su repetición."""
    return {(rep, e) for rep, e in disparos
            if not any((rep, otro) in disparos for otro in skill.regla_de(e).silenciada_por)}


def _catalogo(condicion: str, k: Optional[float], base):
    if condicion == "absolutos":
        return base
    return {sid: replace(ej, skill=con_umbrales_de_referencia(ej.skill, ej.referencia, k=k),
                         umbrales="referencia")
            for sid, ej in base.items()}


def modo_banco(args) -> Dict[str, Any]:
    base = cargar_catalogo()
    episodios: List[Dict[str, Any]] = []
    for skill_id, video, papel in BANCO:
        resultados, tiempos, _ = pose(video)
        obs = observaciones(skill_id, resultados)
        variantes = [("correcta", None, "", None)] + [
            (v, e, mag, construir(obs)) for v, e, mag, construir in VARIANTES[skill_id]]
        for condicion in CONDICIONES:
            for k in ((None,) if condicion == "absolutos" else args.k):
                catalogo = _catalogo(condicion, k, base)
                ej = catalogo[skill_id]
                for variante, etiqueta, mag, transformar in variantes:
                    r = _pasada(ej, catalogo, resultados, tiempos, transformar,
                                sin_dtw=condicion == "referencia_sin_dtw")
                    efectivos = _efectivos(r["disparos"], ej.skill)
                    reps = sorted({rep for rep, _ in r["evaluadas"] if rep > 0})
                    episodios.append({
                        "skill": skill_id, "video": video.name, "papel": papel,
                        "condicion": condicion, "k": k, "variante": variante,
                        "etiqueta": etiqueta, "magnitud": mag, "reps": reps,
                        "evaluadas": sorted(r["evaluadas"]), "disparos": sorted(efectivos),
                        "frames_motor": r["frames_motor"], "abstenciones": r["abstenciones"],
                        "respaldos": r["respaldos"], "mensajes": r["mensajes"],
                        "dtw_ms": r["dtw_ms"], "motor_ms": r["motor_ms"],
                        "completadas": r["completadas"], "incompletas": r["incompletas"]})
        print(f"  {skill_id} · {video.name}: hecho", flush=True)
    return {"entorno": M._entorno(), "k": args.k, "episodios": episodios}


# ---------------------------------------------------------------------------
# Métricas y tablas
# ---------------------------------------------------------------------------

def _tasa(episodios, regla: str) -> Tuple[int, int]:
    """(repeticiones con disparo, repeticiones en que la regla se evaluó)."""
    disparadas = evaluadas = 0
    for e in episodios:
        ev = {rep for rep, r in e["evaluadas"] if r == regla and rep > 0}
        di = {rep for rep, r in e["disparos"] if r == regla and rep > 0}
        evaluadas += len(ev)
        disparadas += len(di & ev)
    return disparadas, evaluadas


def _exactitud(episodios) -> Tuple[int, int]:
    """Repeticiones en que lo que se dispara es exactamente la etiqueta (nada
    en las correctas), sobre las repeticiones en que se evaluó alguna regla."""
    bien = total = 0
    for e in episodios:
        esperado = {e["etiqueta"]} if e["etiqueta"] else set()
        evaluadas = set(e["evaluadas"])
        for rep in e["reps"]:
            disparadas = {r for rp, r in e["disparos"] if rp == rep}
            if e["etiqueta"] and (rep, e["etiqueta"]) not in evaluadas:
                continue
            total += 1
            bien += disparadas == esperado
    return bien, total


def _con_alguna(episodios) -> Tuple[int, int]:
    """Repeticiones correctas en que dispara alguna regla: lo que oiría la usuaria."""
    con = total = 0
    for e in episodios:
        disparadas = {rp for rp, _ in e["disparos"]}
        total += len(e["reps"])
        con += len(set(e["reps"]) & disparadas)
    return con, total


def _no_evaluable(episodios) -> Tuple[int, int]:
    """Repeticiones con error inducido en que la regla de la etiqueta no se
    pudo evaluar (p. ej. la calla `silenciada_por`)."""
    sin = total = 0
    for e in episodios:
        evaluadas = set(e["evaluadas"])
        for rep in e["reps"]:
            total += 1
            sin += (rep, e["etiqueta"]) not in evaluadas
    return sin, total


def _pct(a: int, b: int) -> str:
    return "—" if b == 0 else f"{100 * a / b:.0f} % ({a}/{b})"


def tablas(datos: Dict[str, Any], k_tabla: float) -> str:
    eps = datos["episodios"]
    for e in eps:
        e["evaluadas"] = [tuple(x) for x in e["evaluadas"]]
        e["disparos"] = [tuple(x) for x in e["disparos"]]
    lineas: List[str] = []

    def sel(cond, k=None, **filtros):
        return [e for e in eps if e["condicion"] == cond
                and (cond == "absolutos" or e["k"] == k)
                and all(e[c] == v for c, v in filtros.items())]

    conds = [("absolutos", None), ("referencia", k_tabla), ("referencia_sin_dtw", k_tabla)]
    lineas.append(f"### Por regla (k = {k_tabla} en las condiciones con referencia)\n")
    lineas.append("FP = repeticiones correctas en que la regla dispara. "
                  "Detección = repeticiones con el error inducido en que dispara.\n")
    cab = "| Ejercicio | Regla | Error inducido | " + " | ".join(
        f"{c}: FP fuera · FP ref. · detección" for c, _ in conds) + " |"
    lineas += [cab, "|" + "---|" * (3 + len(conds))]
    for skill_id in VARIANTES:
        reglas = sorted({et for _, et, _, _ in VARIANTES[skill_id]})
        for regla in reglas:
            mags = sorted({mag for _, et, mag, _ in VARIANTES[skill_id] if et == regla})
            for mag in mags:
                celdas = []
                for c, k in conds:
                    fp_f = _tasa(sel(c, k, skill=skill_id, variante="correcta", papel="fuera"), regla)
                    fp_r = _tasa(sel(c, k, skill=skill_id, variante="correcta", papel="referencia"), regla)
                    det = _tasa(sel(c, k, skill=skill_id, etiqueta=regla, magnitud=mag), regla)
                    celdas.append(f"{_pct(*fp_f)} · {_pct(*fp_r)} · {_pct(*det)}")
                lineas.append(f"| {skill_id} | `{regla}` | {mag} | " + " | ".join(celdas) + " |")

    lineas.append("\n### Resumen por condición y k, solo vídeos «fuera»\n")
    lineas.append("Sin la plancha, que no tiene vídeo fuera de la referencia. "
                  "«No evaluable» = repeticiones con error en que la regla de la etiqueta no se "
                  "pudo evaluar (p. ej. la calló `silenciada_por`).\n")
    lineas.append("| Condición | k | Reps correctas con alguna corrección | FP por regla "
                  "| Detección | Error no evaluable | Exactitud por repetición "
                  "| Frames con respaldo | DTW p95 (ms) |")
    lineas.append("|---|---|---|---|---|---|---|---|---|")
    for c in CONDICIONES:
        for k in ((None,) if c == "absolutos" else datos["k"]):
            todos = sel(c, k, papel="fuera")
            correctas = [e for e in todos if e["variante"] == "correcta"]
            errores = [e for e in todos if e["etiqueta"]]
            fp = [0, 0]
            for e in correctas:
                for regla in {r for _, r in e["evaluadas"]}:
                    a, b = _tasa([e], regla)
                    fp[0] += a
                    fp[1] += b
            det = [0, 0]
            for e in errores:
                a, b = _tasa([e], e["etiqueta"])
                det[0] += a
                det[1] += b
            frames = sum(e["frames_motor"] for e in todos)
            respaldo = sum(sum(e["respaldos"].values()) for e in todos)
            p95 = [e["dtw_ms"].get("p95_ms") for e in sel(c, k) if e["dtw_ms"]]
            lineas.append(
                f"| {c} | {'—' if k is None else k} | {_pct(*_con_alguna(correctas))} "
                f"| {_pct(*fp)} | {_pct(*det)} | {_pct(*_no_evaluable(errores))} "
                f"| {_pct(*_exactitud(todos))} | {_pct(respaldo, frames)} "
                f"| {max(p95) if p95 else '—'} |")
    return "\n".join(lineas)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="modo", required=True)
    sub.add_parser("ruido")
    b = sub.add_parser("banco")
    b.add_argument("--k", type=float, nargs="+", default=[2.0, 3.0, 4.0])
    b.add_argument("--k-tabla", type=float, default=3.0,
                   help="k de la tabla por regla (defecto 3)")
    t = sub.add_parser("tablas", help="rehace las tablas de un JSON de `banco` ya guardado")
    t.add_argument("json", type=Path)
    t.add_argument("--k-tabla", type=float, default=3.0)
    args = p.parse_args()
    if args.modo == "ruido":
        datos = modo_ruido(args)
        print(f"Resultados en {M._guardar('ruido', datos)}")
        return 0
    if args.modo == "tablas":
        import json
        datos = json.loads(args.json.read_text(encoding="utf-8"))
        md = tablas(datos, args.k_tabla)
        args.json.with_suffix(".md").write_text(md, encoding="utf-8")
        print(md)
        return 0
    datos = modo_banco(args)
    ruta = M._guardar("banco", datos)
    md = tablas(datos, args.k_tabla)
    ruta.with_suffix(".md").write_text(md, encoding="utf-8")
    print(md)
    print(f"Resultados en {ruta} y {ruta.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
