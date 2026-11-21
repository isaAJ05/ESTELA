"""Visor de calibración: qué mide cada regla de un skill en un vídeo y dónde dispara.

Uso (desde `backend/`):

    python scripts/visor_calibracion.py --ejercicio jumping_jacks --video ruta.mp4 [--salida grafica.png]

Pasa el vídeo por la sesión real (pose → geometría → segmentador → motor) y
guarda una gráfica con un panel por regla:

- curva: el valor de la medida en los frames en que la regla se pudo evaluar
  (los huecos son frames en que no aplica o el motor se abstiene);
- línea discontinua: el umbral de la regla;
- puntos rojos: frames en que la regla dispara;
- triángulos: momentos en que el sistema lo dijo en voz alta (la política de
  silencio hace que sean muchos menos que los disparos);
- líneas verticales: inicio de cada repetición.

Solo se guardan curvas de medidas derivadas, nunca frames del vídeo.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from estela import config
from estela.aplicacion.rutina import cargar_catalogo, rutina_de_un_ejercicio
from estela.aplicacion.sesion import Sesion


class _VozMuda:
    def decir(self, texto, prioridad=0):
        return True


def medir(video: Path, ejercicio_id: str, modelo: str = "lite") -> Dict[str, Any]:
    """Por regla: `(t_s, valor, disparó)` de cada frame en que se evaluó."""
    from estela.adaptadores.captura.fuente import FuenteVideo
    from estela.adaptadores.pose.estimador import EstimadorPose

    catalogo = cargar_catalogo()
    if ejercicio_id not in catalogo:
        raise SystemExit(f"ejercicio desconocido: {ejercicio_id}. Hay: {', '.join(catalogo)}")
    if not video.is_file():
        raise SystemExit(f"no existe el vídeo: {video}")
    s = Sesion(rutina_de_un_ejercicio(ejercicio_id, 999, catalogo), catalogo,
               EstimadorPose(config.modelo_pose(modelo)), _VozMuda())
    decision = s.paso_actual.motor.decision
    series: Dict[str, List[tuple]] = {r.error_id: [] for r in decision.skill.reglas}
    repeticiones: List[float] = []
    ultima = [0]
    candidatos_originales = decision._candidatos

    # mismo gancho que PRUEBAS/exp006_dtw/comparar_reglas.py: el motor no expone
    # el valor de las reglas que evaluó y no dispararon
    def registrar(obs):
        cand, motivos, evaluadas = candidatos_originales(obs)
        t = obs.t_ms / 1000.0
        if (obs.repeticion or 0) != ultima[0]:
            ultima[0] = obs.repeticion or 0
            repeticiones.append(t)
        disparadas = {c[0].error_id: c[1] for c in cand}
        for error_id in evaluadas:
            regla = decision.skill.regla_de(error_id)
            valor = disparadas.get(error_id, decision.valor_de_medida(regla.medida, obs))
            if valor is not None:
                series[error_id].append((t, valor, error_id in disparadas))
        return cand, motivos, evaluadas

    decision._candidatos = registrar
    fuente = FuenteVideo(video)
    try:
        while (leido := fuente.leer()) is not None:
            s.procesar(*leido)
    finally:
        fuente.cerrar()
        s.estimador.cerrar()
    paso = s.resumen()["pasos"][0]
    return {"skill": decision.skill, "series": series, "repeticiones": repeticiones,
            "mensajes": paso["mensajes"], "completadas": paso["completadas"],
            "abstenciones": paso["abstenciones"]}


def graficar(datos: Dict[str, Any], titulo: str, salida: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    reglas = datos["skill"].reglas
    fig, ejes = plt.subplots(len(reglas), 1, figsize=(11, 2.4 * len(reglas)),
                             sharex=True, squeeze=False)
    for eje, regla in zip(ejes[:, 0], reglas):
        puntos = datos["series"][regla.error_id]
        c = regla.condicion
        # shortcut: solo umbrales absolutos (el modo por defecto); con
        # `--umbrales referencia` el umbral cambia en cada frame y habría que
        # dibujarlo como curva
        for umbral in (c.umbral, c.min, c.max):
            if umbral is not None:
                eje.axhline(umbral, color="tab:orange", linestyle="--", linewidth=1)
        for t in datos["repeticiones"]:
            eje.axvline(t, color="0.85", linewidth=0.8, zorder=0)
        if puntos:
            # un hueco de más de 0,2 s corta la curva: ahí la regla no se evaluó
            ts, vs = [], []
            for anterior, (t, v, _) in zip([None] + puntos[:-1], puntos):
                if anterior is not None and t - anterior[0] > 0.2:
                    ts.append(None)
                    vs.append(None)
                ts.append(t)
                vs.append(v)
            eje.plot(ts, vs, color="tab:blue", linewidth=1.2)
            eje.plot([t for t, _, d in puntos if d], [v for _, v, d in puntos if d],
                     "o", color="tab:red", markersize=3)
            dichos = [m["t_ms"] / 1000.0 for m in datos["mensajes"]
                      if m["error_id"] == regla.error_id]
            if dichos:
                base = eje.get_ylim()[0]
                eje.plot(dichos, [base] * len(dichos), "^", color="black", markersize=7,
                         clip_on=False)
        disparos = sum(d for _, _, d in puntos)
        limite = (f"{c.op} {c.umbral:g}" if c.umbral is not None
                  else f"{c.op} [{c.min:g}, {c.max:g}]")
        eje.set_title(f"{regla.error_id} · {regla.medida.nombre or '/'.join(regla.medida.nombres)}"
                      f" {limite} · dispara en {disparos} de {len(puntos)} frames evaluados",
                      fontsize=9, loc="left")
        eje.grid(alpha=0.2)
    ejes[-1, 0].set_xlabel("tiempo (s)")
    fig.suptitle(titulo, fontsize=11)
    fig.tight_layout()
    fig.savefig(salida, dpi=120)
    plt.close(fig)


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ejercicio", required=True)
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--salida", type=Path, default=None,
                   help="PNG de salida (defecto: visor_<ejercicio>_<vídeo>.png)")
    p.add_argument("--modelo", choices=("lite", "full", "heavy"), default="lite",
                   help="modelo de pose (defecto lite, el de la sesión)")
    a = p.parse_args(argv)
    datos = medir(a.video, a.ejercicio, a.modelo)
    salida = a.salida or Path(f"visor_{a.ejercicio}_{a.video.stem}.png")
    titulo = (f"{datos['skill'].nombre} · {a.video.name} · {datos['completadas']} completadas · "
              f"{len(datos['mensajes'])} mensajes · abstenciones {datos['abstenciones'] or 'ninguna'}")
    graficar(datos, titulo, salida)
    for regla in datos["skill"].reglas:
        puntos = datos["series"][regla.error_id]
        print(f"{regla.error_id:34s} evaluada {len(puntos):5d} frames · "
              f"dispara {sum(d for _, _, d in puntos):5d}")
    print(f"escrito {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
