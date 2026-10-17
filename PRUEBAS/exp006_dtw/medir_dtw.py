"""EXP-006 · DTW en sesión: coste por frame y calidad del alineamiento.

Dos modos (desde ESTELA/, con el entorno de backend/):

    python PRUEBAS/exp006_dtw/medir_dtw.py sintetico
    python PRUEBAS/exp006_dtw/medir_dtw.py video --ejercicio jumping_jacks --video RUTA.mp4

`sintetico` no necesita cámara ni modelo: alimenta el alineador con la media
de cada referencia del catálogo, remuestreada a 30 fps y seguida de un reposo
largo dentro de la misma repetición, y mide el tiempo por frame de la versión
anterior (recalculaba la repetición entera, PR #8) y de la incremental.

`video` pasa el estimador de pose una sola vez por el vídeo y reproduce esos
mismos resultados en la sesión tres veces: sin DTW, con el DTW anterior y con
el incremental. Las tres pasadas ven exactamente la misma pose. Además mide la
calidad del alineamiento (progreso al cerrar cada repetición, retrocesos) y,
con `--desplazar`, cuánto de un desplazamiento artificial de cada ángulo
llega a la desviación que mide el DTW.

Escribe un JSON en `PRUEBAS/exp006_dtw/resultados/` (ignorado por git: solo
métricas derivadas, nunca frames).
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from estela.aplicacion import sesion as modulo_sesion                    # noqa: E402
from estela.aplicacion.dtw import AlineadorDTW, ResultadoDTW              # noqa: E402
from estela.aplicacion.metricas import percentil                         # noqa: E402
from estela.aplicacion.rutina import cargar_catalogo, rutina_de_un_ejercicio  # noqa: E402
from estela.dominio.feedback.contrato import Observacion                 # noqa: E402

RESULTADOS = Path(__file__).resolve().parent / "resultados"
FPS_VIVO = 30.0


# ---------------------------------------------------------------------------
# Versión anterior (PR #8), copiada tal cual para medir el antes y el después
# ---------------------------------------------------------------------------

class AlineadorAnterior:
    """Recalcula el DTW completo de la repetición en cada frame, O(n·m)."""

    def __init__(self, referencia):
        self.referencia = referencia
        self._repeticion = None
        self._serie = []
        self._nombres, self._media = (), np.empty((0, 0), dtype=float)
        nombres = tuple((referencia or {}).get("medidas", ()))
        media = ((referencia or {}).get("angulos") or {}).get("media", ())
        if nombres and media:
            matriz = np.asarray(media, dtype=float)
            if matriz.ndim == 2 and matriz.shape[1] == len(nombres):
                self._nombres, self._media = nombres, matriz
        self.motivos: Dict[str, int] = {}

    @property
    def disponible(self):
        return bool(self._nombres) and len(self._media) > 0

    def reiniciar(self):
        self._repeticion = None
        self._serie.clear()

    def actualizar(self, obs):
        if not self.disponible:
            return None
        rep = obs.repeticion
        if rep is not None and rep > 0:
            if self._repeticion is not None and rep != self._repeticion:
                self._serie.clear()
            self._repeticion = rep
        valores = [obs.angulos.get(n, obs.distancias.get(n, np.nan)) for n in self._nombres]
        self._serie.append(np.asarray([np.nan if v is None else v for v in valores], float))
        coste, camino = _dtw_anterior(np.asarray(self._serie, float), self._media)
        if not camino:
            return None
        i, j = camino[-1]
        return ResultadoDTW({n: float(self._media[j, k]) for k, n in enumerate(self._nombres)
                             if np.isfinite(self._media[j, k])},
                            j / max(len(self._media) - 1, 1), coste, j)


def _dtw_anterior(a, b):
    n, m = len(a), len(b)
    acumulado = np.full((n + 1, m + 1), np.inf)
    acumulado[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diferencia = np.abs(a[i - 1] - b[j - 1])
            validas = np.isfinite(diferencia)
            if not np.any(validas):
                continue
            acumulado[i, j] = float(np.mean(diferencia[validas])) + min(
                acumulado[i - 1, j], acumulado[i, j - 1], acumulado[i - 1, j - 1])
    if not np.isfinite(acumulado[n, m]):
        return float("inf"), []
    i, j, camino = n, m, []
    while i > 0 and j > 0:
        camino.append((i - 1, j - 1))
        k = int(np.argmin((acumulado[i - 1, j - 1], acumulado[i - 1, j], acumulado[i, j - 1])))
        i, j = ((i - 1, j - 1), (i - 1, j), (i, j - 1))[k]
    camino.reverse()
    return float(acumulado[n, m] / len(camino)), camino


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _resumen(valores: List[float]) -> Dict[str, float]:
    if not valores:
        return {"n": 0}
    return {"n": len(valores), "p50": round(percentil(valores, 50), 4),
            "p95": round(percentil(valores, 95), 4), "max": round(max(valores), 4)}


def _entorno() -> Dict[str, Any]:
    return {"fecha": datetime.now().isoformat(timespec="seconds"),
            "maquina": platform.platform(), "procesador": platform.processor(),
            "python": platform.python_version(), "numpy": np.__version__}


def _guardar(nombre: str, datos: Dict[str, Any]) -> Path:
    RESULTADOS.mkdir(exist_ok=True)
    ruta = RESULTADOS / f"{datetime.now():%Y%m%d-%H%M%S}-{nombre}.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


def _obs(skill_id: str, nombres, fila, t_ms: int, rep: int) -> Observacion:
    valores = {n: float(v) for n, v in zip(nombres, fila) if np.isfinite(v)}
    return Observacion(t_ms=t_ms, ejercicio_id=skill_id, angulos=valores,
                       confianza={n: 0.9 for n in valores}, repeticion=rep)


# ---------------------------------------------------------------------------
# Modo sintético
# ---------------------------------------------------------------------------

def modo_sintetico(args) -> Dict[str, Any]:
    catalogo = cargar_catalogo()
    rng = np.random.default_rng(0)
    salida: Dict[str, Any] = {"entorno": _entorno(), "fps_vivo": FPS_VIVO,
                              "reposo_s": args.reposo, "ejercicios": {}}
    for skill_id, ej in catalogo.items():
        ref = ej.referencia or {}
        if "angulos" not in ref:
            continue
        media = np.asarray(ref["angulos"]["media"], dtype=float)
        t_ref = np.arange(len(media)) / ref["fps"]
        t = np.arange(0, t_ref[-1], 1 / FPS_VIVO)
        serie = np.stack([np.interp(t, t_ref, media[:, k]) for k in range(media.shape[1])], 1)
        serie = np.vstack([serie, np.repeat(serie[-1:], int(args.reposo * FPS_VIVO), 0)])
        serie = serie + rng.normal(0, 1.0, serie.shape)
        fila_ej: Dict[str, Any] = {"m": len(media), "fps_ref": ref["fps"], "frames": len(serie)}
        for nombre, clase in (("anterior", AlineadorAnterior), ("incremental", AlineadorDTW)):
            al = clase(ref)
            tiempos = []
            for i, f in enumerate(serie):
                o = _obs(skill_id, ref["medidas"], f, round(i * 1000 / FPS_VIVO), 1)
                t0 = time.perf_counter()
                al.actualizar(o)
                tiempos.append((time.perf_counter() - t0) * 1000)
            fila_ej[nombre] = {
                # tiempo por frame según cuántos frames lleva la repetición
                "por_n": {str(n): round(float(np.median(tiempos[max(0, n - 5):n + 5])), 4)
                          for n in (1, 30, 60, 90, 150, 300, 450) if n <= len(tiempos)},
                "global_ms": _resumen(tiempos)}
            print(f"{skill_id:22s} {nombre:12s} m={len(media):3d} "
                  + "  ".join(f"n={n}: {v:8.3f} ms" for n, v in fila_ej[nombre]["por_n"].items()))
        salida["ejercicios"][skill_id] = fila_ej
    return salida


# ---------------------------------------------------------------------------
# Modo vídeo
# ---------------------------------------------------------------------------

class _VozMuda:
    def decir(self, texto, prioridad=0):
        return True


class _EstimadorGrabado:
    """Devuelve los resultados de una pasada real del estimador, en orden."""

    def __init__(self, resultados):
        self._resultados = iter(resultados)

    def estimar(self, frame, t_ms):
        return next(self._resultados)

    def cerrar(self):
        pass


def _con_traza(clase):
    class ConTraza(clase):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.traza: List[Tuple[Observacion, Optional[ResultadoDTW]]] = []

        def actualizar(self, obs):
            r = super().actualizar(obs)
            self.traza.append((obs, r))
            return r
    return ConTraza


def _pasar_pose(video: Path, modelo: str) -> Tuple[List[Any], List[int], float]:
    from estela import config
    from estela.adaptadores.captura.fuente import FuenteVideo
    from estela.adaptadores.pose.estimador import EstimadorPose

    fuente, estimador = FuenteVideo(video), EstimadorPose(config.modelo_pose(modelo))
    resultados, tiempos = [], []
    try:
        while (leido := fuente.leer()) is not None:
            frame, t_ms = leido
            resultados.append(estimador.estimar(frame, t_ms))
            tiempos.append(t_ms)
    finally:
        fuente.cerrar()
        estimador.cerrar()
    return resultados, tiempos, fuente.fps


def _reproducir(skill_id: str, catalogo, resultados, tiempos, alineador) -> Dict[str, Any]:
    """Una pasada de la sesión sobre la pose grabada. `alineador` None = sin DTW."""
    original = modulo_sesion.comparador_de_referencia
    if alineador is not None:
        modulo_sesion.comparador_de_referencia = _con_traza(alineador)
    try:
        s = modulo_sesion.Sesion(rutina_de_un_ejercicio(skill_id, 999, catalogo), catalogo,
                                 _EstimadorGrabado(resultados), _VozMuda(),
                                 sin_dtw=alineador is None)
        totales = []
        for t_ms in tiempos:
            estado = s.procesar(None, t_ms)
            if "total" in estado.latencia_ms:
                totales.append(estado.latencia_ms["total"])
        paso = s.paso_actual
        traza = paso.alineador.traza if paso.alineador is not None else []
        # `total` de la sesión con la pose ya hecha: geometría, segmentador,
        # DTW y motor
        return {"resumen": s.resumen(), "traza": traza,
                "dtw_ms": list(s.latencias._datos.get("dtw", [])),
                "sesion_sin_pose_ms": totales}
    finally:
        modulo_sesion.comparador_de_referencia = original


def _calidad(ref, traza, seg) -> Dict[str, Any]:
    """Progreso esperado al cerrar cada repetición y retrocesos del instante
    alineado dentro de una misma repetición."""
    esperado = None
    if seg.get("tipo") == "ciclo":
        # el frame que cierra la repetición es el anterior al primer reposo
        reposo = seg["fases"][0]
        tramos = [t for t in ref.get("fases", ()) if t["fase"] == reposo]
        if tramos:
            esperado = (tramos[-1]["inicio"] - 1) / max(len(ref["angulos"]["media"]) - 1, 1)
    retrocesos, saltos, previo, rep_previa = 0, [], None, None
    alineados = 0
    for obs, r in traza:
        if r is None:
            continue
        alineados += 1
        if obs.repeticion == rep_previa and previo is not None and r.indice < previo:
            retrocesos += 1
            saltos.append(previo - r.indice)
        previo, rep_previa = r.indice, obs.repeticion
    return {"frames_alineados": alineados, "retrocesos": retrocesos,
            "retroceso_max_frames_ref": max(saltos) if saltos else 0,
            "progreso_esperado_al_cerrar": round(esperado, 3) if esperado is not None else None}


def _desplazamientos(ref, traza, delta: float) -> Dict[str, Any]:
    """Suma `delta` a una medida cada vez y mide cuánto llega a la desviación.

    Por frame: (desviación con el desplazamiento) − (desviación sin él). Si el
    alineamiento no cambia vale exactamente `delta`; si el DTW deforma el
    tiempo para acercarse, vale menos.
    """
    observaciones = [o for o, _ in traza]
    base = [r for _, r in traza]
    salida = {}
    for nombre in ref["medidas"]:
        if not any(nombre in o.angulos for o in observaciones):
            salida[nombre] = "solo distancias: no se desplaza en grados"
            continue
        al = AlineadorDTW(ref)
        llega = []
        for o, r0 in zip(observaciones, base):
            if nombre in o.angulos:
                o = replace(o, angulos={**o.angulos, nombre: o.angulos[nombre] + delta})
            r = al.actualizar(o)
            if (r is not None and r0 is not None and nombre in r.angulos_ref
                    and nombre in r0.angulos_ref and nombre in o.angulos
                    and o.confianza_de(nombre) >= al.confianza_minima):
                llega.append(delta - (r.angulos_ref[nombre] - r0.angulos_ref[nombre]))
        salida[nombre] = {"n": len(llega),
                          "p10": round(percentil(llega, 10), 2) if llega else None,
                          "p50": round(percentil(llega, 50), 2) if llega else None,
                          "p90": round(percentil(llega, 90), 2) if llega else None}
    return salida


def modo_video(args) -> Dict[str, Any]:
    catalogo = cargar_catalogo()
    ej = catalogo[args.ejercicio]
    print(f"Pose sobre {args.video.name} ({args.modelo})…")
    resultados, tiempos, fps = _pasar_pose(args.video, args.modelo)
    pose_ms = [r.latencia_ms for r in resultados]
    print(f"  {len(resultados)} frames a {fps:.2f} fps · pose p50 "
          f"{percentil(pose_ms, 50):.1f} ms, p95 {percentil(pose_ms, 95):.1f} ms")

    salida: Dict[str, Any] = {
        "entorno": _entorno(), "video": args.video.name, "ejercicio": args.ejercicio,
        "modelo_pose": args.modelo, "fps_video": fps, "frames": len(resultados),
        "pose_ms": _resumen(pose_ms), "pasadas": {}}
    for nombre, clase in (("sin_dtw", None), ("anterior", AlineadorAnterior),
                          ("incremental", AlineadorDTW)):
        if nombre == "anterior" and args.sin_anterior:
            continue
        datos = _reproducir(args.ejercicio, catalogo, resultados, tiempos, clase)
        paso = datos["resumen"]["pasos"][0]
        fila: Dict[str, Any] = {
            "dtw_ms": _resumen(datos["dtw_ms"]),
            "sesion_sin_pose_ms": _resumen(datos["sesion_sin_pose_ms"]),
            "completadas": paso["completadas"], "incompletas": paso["incompletas"],
            "mensajes": [(m["repeticion"], m["error_id"]) for m in paso["mensajes"]],
            "motivos_dtw": paso["dtw"],
        }
        if nombre == "incremental":
            fila["calidad"] = _calidad(ej.referencia or {}, datos["traza"], ej.segmentacion or {})
            fila["repeticiones"] = [
                {k: f.get(k) for k in ("rep", "resultado", "duracion_s", "coste_dtw",
                                       "progreso_dtw")}
                for f in paso["repeticiones"]]
            costes = [f["coste_dtw"] for f in fila["repeticiones"]
                      if f["coste_dtw"] is not None and f["resultado"] == "cuenta"]
            fila["coste_dtw_al_cerrar"] = _resumen(costes)
            if args.desplazar:
                fila["desplazamiento"] = {"delta": args.desplazar, **_desplazamientos(
                    ej.referencia or {}, datos["traza"], args.desplazar)}
        salida["pasadas"][nombre] = fila
        d = fila["dtw_ms"]
        print(f"  {nombre:12s} dtw p50 {d.get('p50', 0):9.3f} ms  p95 {d.get('p95', 0):9.3f} ms"
              f"  max {d.get('max', 0):9.3f} ms · {fila['completadas']} completas,"
              f" {fila['incompletas']} incompletas, {len(fila['mensajes'])} mensajes")
    if "anterior" in salida["pasadas"]:
        iguales = (salida["pasadas"]["anterior"]["mensajes"]
                   == salida["pasadas"]["sin_dtw"]["mensajes"]
                   == salida["pasadas"]["incremental"]["mensajes"])
        salida["mismos_mensajes_en_las_tres_pasadas"] = iguales
    inc = salida["pasadas"]["incremental"]
    print(f"  calidad: {inc['calidad']}")
    print(f"  coste al cerrar (repeticiones que cuentan): {inc['coste_dtw_al_cerrar']}")
    for f in inc["repeticiones"]:
        print(f"    rep {f['rep']:3d} {f['resultado']:9s} {f['duracion_s']} s · coste {f['coste_dtw']}"
              f" · progreso {f['progreso_dtw']}")
    if "desplazamiento" in inc:
        print(f"  desplazamiento +{args.desplazar}: {inc['desplazamiento']}")
    return salida


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="modo", required=True)
    s = sub.add_parser("sintetico")
    s.add_argument("--reposo", type=float, default=15.0,
                   help="segundos de reposo dentro de la misma repetición (defecto 15)")
    v = sub.add_parser("video")
    v.add_argument("--ejercicio", required=True)
    v.add_argument("--video", type=Path, required=True)
    v.add_argument("--modelo", choices=("lite", "full", "heavy"), default="full")
    v.add_argument("--desplazar", type=float, default=0.0,
                   help="grados que se suman a cada ángulo de la referencia, uno cada vez")
    v.add_argument("--sin-anterior", action="store_true",
                   help="no medir la versión anterior (es lenta en vídeos largos)")
    args = p.parse_args()
    datos = modo_sintetico(args) if args.modo == "sintetico" else modo_video(args)
    nombre = "sintetico" if args.modo == "sintetico" else f"{args.ejercicio}-{args.video.stem}"
    print(f"Resultados en {_guardar(nombre.replace(' ', '_'), datos)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
