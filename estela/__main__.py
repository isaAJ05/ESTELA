"""ESTELA v1 — sesión en vivo: cámara → pose → conteo → feedback → voz.

Ejemplos:
    python -m estela --rutina rutinas/calentamiento_basico.json
    python -m estela --ejercicio sentadilla --repeticiones 8
    python -m estela --ejercicio sentadilla --video ruta.mp4 --voz texto --sin-ventana

Teclas (con ventana): q/Esc salir · n siguiente ejercicio · r reiniciar ejercicio.
"""

from __future__ import annotations

import os

os.environ.setdefault("GLOG_minloglevel", "2")        # silencia logs de mediapipe
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from . import config

log = logging.getLogger("estela")


def _argumentos(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m estela", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    grupo = p.add_mutually_exclusive_group()
    grupo.add_argument("--rutina", type=Path,
                     default=config.RUTINAS / "calentamiento_basico.json",
                     help="archivo JSON de rutina")
    grupo.add_argument("--ejercicio", help="un solo ejercicio (skill_id)")
    p.add_argument("--repeticiones", type=int, default=10,
                   help="objetivo con --ejercicio (defecto 10)")
    p.add_argument("--video", type=Path, help="usar un vídeo en lugar de la cámara")
    p.add_argument("--camara", type=int, default=0, help="índice de cámara")
    p.add_argument("--modelo", choices=("lite", "full", "heavy"), default="full",
                   help="variante de Pose Landmarker")
    p.add_argument("--voz", choices=("piper", "sistema", "texto"), default="piper")
    p.add_argument("--auto", action="store_true",
                   help="activar el reconocedor BiLSTM (consultivo)")
    p.add_argument("--sin-ventana", action="store_true",
                   help="sin interfaz gráfica (pruebas con vídeo)")
    p.add_argument("--guardar-metricas", action="store_true",
                   help="guardar el resumen (solo métricas derivadas) en sesiones/")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def _imprimir_resumen(r: dict) -> None:
    print("\n=== Resumen de la sesión ===")
    for paso in r["pasos"]:
        print(f"- {paso['skill_id']}: {paso['completadas']}/{paso['objetivo']} "
              f"completas, {paso['incompletas']} incompletas, "
              f"{len(paso['mensajes'])} correcciones, {paso['duracion_s']} s")
        for m in paso["mensajes"]:
            print(f"    [{m['t_ms'] / 1000:6.1f} s · rep {m['repeticion']}] {m['texto']}")
    print(f"Frames: {r['frames']} (sin persona: {r['frames_sin_persona']})")
    print("Latencia por etapa (ms):")
    for etapa, v in r["latencias"].items():
        print(f"    {etapa:15s} p50 {v['p50_ms']:8.3f}   p95 {v['p95_ms']:8.3f}   n={v['n']}")


def main(argv=None) -> int:
    args = _argumentos(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    from .pose.estimador import EstimadorPose
    from .sesion.rutina import (RutinaInvalida, cargar_catalogo, cargar_rutina,
                                rutina_de_un_ejercicio)
    from .sesion.sesion import Sesion, frases_de_rutina
    from .voz.cola import ColaVoz
    from .voz.motores import buscar_voz_piper, crear_motor

    catalogo = cargar_catalogo()
    try:
        rutina = (rutina_de_un_ejercicio(args.ejercicio, args.repeticiones, catalogo)
                  if args.ejercicio else cargar_rutina(args.rutina, catalogo))
    except (RutinaInvalida, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    estimador = EstimadorPose(config.modelo_pose(args.modelo))

    reconocedor = None
    if args.auto:
        try:
            from .reconocimiento.bilstm import ReconocedorBiLSTM
            reconocedor = ReconocedorBiLSTM(config.BILSTM)
        except Exception as e:                     # noqa: BLE001
            log.warning("Reconocedor BiLSTM desactivado: %s", e)

    motor_voz = crear_motor(args.voz, buscar_voz_piper(config.VOCES))
    log.info("Voz: %s", motor_voz.nombre)
    voz = ColaVoz(motor_voz)
    voz.precalentar(frases_de_rutina(rutina, catalogo))

    if args.video:
        from .captura.fuente import FuenteVideo
        fuente = FuenteVideo(args.video, tiempo_real=not args.sin_ventana)
    else:
        from .captura.fuente import FuenteCamara
        fuente = FuenteCamara(args.camara)
    espejo = args.video is None

    sesion = Sesion(rutina, catalogo, estimador, voz, reconocedor=reconocedor)
    ventana = not args.sin_ventana
    if ventana:
        import cv2
        from .ui.overlay import dibujar
        cv2.namedWindow("ESTELA", cv2.WINDOW_NORMAL)

    fps, t_prev = None, time.perf_counter()
    fin_mostrado = None
    try:
        while True:
            leido = fuente.leer()
            if leido is None:
                break
            frame, t_ms = leido
            estado = sesion.procesar(frame, t_ms)

            ahora = time.perf_counter()
            inst = 1.0 / max(ahora - t_prev, 1e-6)
            fps = inst if fps is None else 0.9 * fps + 0.1 * inst
            t_prev = ahora

            if ventana:
                cv2.imshow("ESTELA", dibujar(frame, estado, espejo, fps))
                tecla = cv2.waitKey(1) & 0xFF
                if tecla in (ord("q"), 27):
                    break
                if tecla == ord("n"):
                    sesion.siguiente()
                elif tecla == ord("r"):
                    sesion.reiniciar_ejercicio()
            if sesion.terminada:
                if not ventana:
                    break
                fin_mostrado = fin_mostrado or ahora
                if ahora - fin_mostrado > 4.0:
                    break
    except KeyboardInterrupt:
        pass
    finally:
        fuente.cerrar()
        voz.cerrar(esperar=True)
        estimador.cerrar()
        if ventana:
            cv2.destroyAllWindows()

    resumen = sesion.resumen()
    resumen["voz"] = {"motor": motor_voz.nombre, "descartadas": voz.descartadas}
    _imprimir_resumen(resumen)
    if args.guardar_metricas:
        config.SESIONES.mkdir(exist_ok=True)
        ruta = config.SESIONES / f"{datetime.now():%Y%m%d-%H%M%S}.json"
        ruta.write_text(json.dumps(resumen, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        print(f"Métricas guardadas en {ruta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
