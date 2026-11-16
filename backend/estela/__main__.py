"""ESTELA v1 — sesión en vivo: cámara → pose → conteo → feedback → voz.

Ejemplos:
     
    python -m estela --ejercicio zancada_atras_izq --repeticiones 6
    python -m estela --ejercicio plancha --repeticiones 30          # segundos
    python -m estela --ejercicio abduccion_cadera --video ruta.mp4 --voz texto --sin-ventana

Por defecto abre la interfaz de escritorio (frontend/, pywebview). En su
inicio se eligen los ejercicios, su orden y su objetivo antes de empezar;
--rutina o --ejercicio solo fijan la rutina recomendada que aparece al abrir.
Con --interfaz opencv se usa la ventana de OpenCV, más simple, para pruebas y
mediciones (sin pantalla de selección: usa --rutina o --ejercicio).

Teclas en la interfaz: n siguiente ejercicio · r reiniciar ejercicio · v voz ·
Esc terminar · d datos de depuración.
Teclas en la ventana de OpenCV: q/Esc salir · n siguiente · r reiniciar.
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
from typing import Optional

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
                   help="objetivo con --ejercicio: repeticiones, o segundos en "
                        "un ejercicio isométrico como la plancha (defecto 10)")
    p.add_argument("--video", type=Path, help="usar un vídeo en lugar de la cámara")
    p.add_argument("--camara", type=int, default=0, help="índice de cámara")
    p.add_argument("--modelo", choices=("lite", "full", "heavy"), default="lite",
                   help="variante de Pose Landmarker")
    p.add_argument("--voz", choices=("piper", "sistema", "texto"), default="piper")
    p.add_argument("--interfaz", choices=("ventana", "opencv"), default="ventana",
                   help="interfaz de escritorio (defecto) o ventana de OpenCV")
    p.add_argument("--sin-ventana", action="store_true",
                   help="sin interfaz gráfica (pruebas con vídeo)")
    p.add_argument("--sin-dtw", action="store_true",
                   help="desactivar la comparación con la referencia DTW")
    p.add_argument("--sin-colocacion", action="store_true",
                   help="empezar a contar sin la fase de colocación de cada ejercicio")
    p.add_argument("--reconocer", action="store_true",
                   help="avisar si el movimiento no es el ejercicio elegido (EXP-010); "
                        "solo con --interfaz opencv: en la ventana se activa desde la sesión")
    p.add_argument("--umbrales", choices=("absolutos", "referencia"), default="absolutos",
                   help="«referencia»: las reglas con forma relativa se miden contra la "
                        "referencia del ejercicio (EXP-006); defecto «absolutos»")
    p.add_argument("--guardar-metricas", action="store_true",
                   help="guardar el resumen (solo métricas derivadas) en sesiones/")
    p.add_argument("--sin-historial", action="store_true",
                   help="sin perfiles ni historial de «Mi progreso» (ADR-008, "
                        "ADR-009); con --video nunca se guardan")
    llm = p.add_argument_group(
        "verbalizador LLM (opcional)",
        "El motor determinista decide el error y si se habla; el LLM solo "
        "redacta la frase, con salida restringida y validador, y cae a la "
        "plantilla si falla o tarda más del tiempo límite.")
    llm.add_argument("--verbalizador", choices=("plantillas", "llm"), default="plantillas",
                     help="quién redacta las correcciones (defecto: plantillas)")
    llm.add_argument("--llm-backend", choices=("ollama", "llama-server"), default="ollama")
    llm.add_argument("--llm-url", help="defecto: el local del backend elegido")
    llm.add_argument("--llm-modelo", help="obligatorio con --verbalizador llm "
                                          "(p. ej. el nombre que da `ollama list`)")
    llm.add_argument("--llm-timeout-ms", type=int,
                     help="obligatorio con --verbalizador llm: tiempo límite por frase; "
                          "pasado ese tiempo suena la plantilla")
    ent = p.add_argument_group(
        "entrenadora (opcional)",
        "Resumen hablado entre ejercicios y al final, nunca durante el movimiento. "
        "Propone una acción de una lista cerrada (repetir, descansar, seguir, terminar); "
        "no la ejecuta. Dolor o lesión: respuesta fija, sin modelo.")
    ent.add_argument("--entrenadora", choices=("no", "plantilla", "llm"), default="no",
                     help="plantilla: sin modelo; llm: modelo local por Ollama con "
                          "respaldo a plantilla (defecto: no)")
    ent.add_argument("--entrenadora-modelo", help="obligatorio con --entrenadora llm")
    ent.add_argument("--entrenadora-timeout-s", type=float,
                     help="obligatorio con --entrenadora llm: tiempo límite de la respuesta; "
                          "pasado, se dice la plantilla")
    ent.add_argument("--entrenadora-url", help="defecto: Ollama local")
    ent.add_argument("--entrenadora-historial", type=Path,
                     help="archivo JSONL de historial (p. ej. el de "
                          "scripts/historial_ejemplo.py) cuando no hay perfiles")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    if args.entrenadora == "llm" and (not args.entrenadora_modelo
                                      or args.entrenadora_timeout_s is None):
        p.error("--entrenadora llm necesita --entrenadora-modelo y --entrenadora-timeout-s")
    if args.verbalizador == "llm" and (not args.llm_modelo or args.llm_timeout_ms is None):
        # sin valores por defecto a propósito: el modelo y el tiempo límite son
        # decisiones del equipo (ADR-004, rol C), no del código
        p.error("--verbalizador llm necesita --llm-modelo y --llm-timeout-ms")
    return args


def _crear_verbalizador(args: argparse.Namespace):
    """None = plantillas (el defecto de `Sesion`)."""
    if args.verbalizador != "llm":
        return None
    import threading
    from .adaptadores.llm.llm_local import VerbalizadorLLMLocal
    v = VerbalizadorLLMLocal(url=args.llm_url, modelo=args.llm_modelo,
                             timeout_ms=args.llm_timeout_ms, backend=args.llm_backend)
    log.info("Verbalizador: LLM %s por %s (%s), tiempo límite %d ms",
             v.modelo, v.backend, v.url, v.timeout_ms)
    # cargar el modelo no debe retrasar el arranque de la interfaz
    threading.Thread(target=v.precalentar, name="estela-llm-precalentado",
                     daemon=True).start()
    return v


def _imprimir_resumen(r: dict) -> None:
    print("\n=== Resumen de la sesión ===")
    for paso in r["pasos"]:
        hechas = (" s en posición, {} pausas" if paso["unidad"] == "segundos"
                  else " completas, {} incompletas").format(paso["incompletas"])
        print(f"- {paso['skill_id']}: {paso['completadas']}/{paso['objetivo']}"
              f"{hechas}, "
              f"{len(paso['mensajes'])} correcciones, {paso['duracion_s']} s"
              + (f" (en pausa {paso['pausas_sesion']} veces, {paso['pausa_s']} s)"
                 if paso["pausas_sesion"] else ""))
        for m in paso["mensajes"]:
            print(f"    [{m['t_ms'] / 1000:6.1f} s · rep {m['repeticion']}] {m['texto']}")
        if paso.get("dtw"):
            print("    DTW (frames): " + ", ".join(
                f"{motivo} {n}" for motivo, n in sorted(paso["dtw"].items())))
        if paso.get("umbrales") == "referencia":
            print("    Umbrales relativos a la referencia; respaldo absoluto (frames): "
                  + (", ".join(f"{e} {n}" for e, n in sorted(paso["respaldos"].items()))
                     or "ninguno"))
    print(f"Frames: {r['frames']} (sin persona: {r['frames_sin_persona']})")
    for e in (r.get("entrenadora") or {}).get("respuestas", ()):
        resp = e["respuesta"] or {}
        print(f"Entrenadora [{e['momento']}] "
              + ("dicha" if e["dicha"] else f"no dicha ({e['motivo']})")
              + (f" · {resp['origen']} · acción {resp['accion']} · "
                 f"{resp['latencia_ms']:.0f} ms: {resp['texto']}" if resp else ""))
    if r.get("llm"):
        m = r["llm"]
        caidas = ", ".join(f"{k} {n}" for k, n in sorted(m["caidas_a_plantilla"].items()))
        print(f"LLM {m['modelo']} (límite {m['timeout_ms']} ms): {m['llamadas']} frases pedidas, "
              f"{sum(m['caidas_a_plantilla'].values())} cayeron a plantilla"
              + (f" ({caidas})" if caidas else ""))
    print("Latencia por etapa (ms):")
    for etapa, v in r["latencias"].items():
        print(f"    {etapa:15s} p50 {v['p50_ms']:8.3f}   p95 {v['p95_ms']:8.3f}   n={v['n']}")


def main(argv=None) -> int:
    # Windows puede iniciar Python con la consola heredada en CP1252. La
    # ayuda y los mensajes en español contienen caracteres fuera de ese
    # conjunto.
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = _argumentos(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    from .aplicacion.rutina import (RutinaInvalida, cargar_catalogo, cargar_rutina,
                                rutina_de_un_ejercicio)
    from .aplicacion.registro import escribir_csv
    from .aplicacion.sesion import frases_de_rutina
    from .adaptadores.voz.cola import ColaVoz
    from .adaptadores.voz.motores import buscar_voz_piper, crear_motor

    catalogo = cargar_catalogo(umbrales=args.umbrales)
    try:
        rutina = (rutina_de_un_ejercicio(args.ejercicio, args.repeticiones, catalogo)
                  if args.ejercicio else cargar_rutina(args.rutina, catalogo))
    except (RutinaInvalida, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    if not args.sin_ventana and args.interfaz == "ventana":
        from .adaptadores.interfaz.ventana import InterfazNoDisponible, comprobar
        try:
            comprobar(config.INTERFAZ)
        except InterfazNoDisponible as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2

    motor_voz = crear_motor(args.voz, buscar_voz_piper(config.VOCES))
    log.info("Voz: %s", motor_voz.nombre)
    voz = ColaVoz(motor_voz)
    voz.precalentar(frases_de_rutina(rutina, catalogo))

    verbalizador = _crear_verbalizador(args)

    #: la crea el modo elegido (necesita la sesión o el orquestador)
    entrenadora = {"en_vivo": None, "esperar": True}

    def cerrar_sesion(resumen: dict) -> None:
        if entrenadora["en_vivo"] is not None:
            if entrenadora["esperar"]:
                # sin interfaz el programa acaba aquí: se espera a que el resumen
                # final (que va tras «Rutina terminada») llegue a sonar
                entrenadora["en_vivo"].esperar((args.entrenadora_timeout_s or 0.0)
                                               + MARGEN_VOZ_ENTRENADORA_S)
            resumen["entrenadora"] = entrenadora["en_vivo"].resumen()
        resumen["voz"] = {"motor": motor_voz.nombre, "descartadas": voz.descartadas,
                          "descartes": dict(voz.descartes)}
        if verbalizador is not None:
            resumen["llm"] = {"modelo": verbalizador.modelo, "backend": verbalizador.backend,
                              "timeout_ms": verbalizador.timeout_ms,
                              "llamadas": verbalizador.llamadas,
                              "caidas_a_plantilla": dict(verbalizador.caidas)}
        _imprimir_resumen(resumen)
        if args.guardar_metricas:
            config.SESIONES.mkdir(exist_ok=True)
            ruta = config.SESIONES / f"{datetime.now():%Y%m%d-%H%M%S}.json"
            ruta.write_text(json.dumps(resumen, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            print(f"Métricas guardadas en {ruta}")
            ruta_csv = ruta.with_name(ruta.stem + "-repeticiones.csv")
            escribir_csv(resumen["pasos"], ruta_csv)
            print(f"Repeticiones guardadas en {ruta_csv}")

    if args.sin_ventana or args.interfaz == "opencv":
        return _correr_opencv(args, rutina, catalogo, voz, cerrar_sesion, verbalizador,
                              entrenadora)
    return _correr_interfaz(args, rutina, catalogo, voz, cerrar_sesion, verbalizador,
                            entrenadora)


#: margen sobre el tiempo límite del modelo para decir la respuesta antes de
#: soltar la colocación (la frase dura unos segundos)
MARGEN_VOZ_ENTRENADORA_S = 15.0


def _crear_entrenadora(args: argparse.Namespace, catalogo, voz, progreso=None):
    """(EntrenadoraEnVivo, retención máxima en ms) o (None, 0)."""
    if args.entrenadora == "no":
        return None, 0
    from .adaptadores.llm.entrenadora_en_vivo import EntrenadoraEnVivo
    from .aplicacion.entrenadora import Entrenadora
    generador, limite_s = None, 0.0
    if args.entrenadora == "llm":
        import threading
        from .adaptadores.llm.entrenadora_ollama import URL_OLLAMA, GeneradorOllama
        limite_s = args.entrenadora_timeout_s
        generador = GeneradorOllama(args.entrenadora_modelo, limite_s,
                                    url=args.entrenadora_url or URL_OLLAMA)
        threading.Thread(target=generador.precalentar, name="estela-entrenadora-precalentado",
                         daemon=True).start()
        log.info("Entrenadora: LLM %s (límite %.1f s)", generador.modelo, limite_s)
    if progreso is None and args.entrenadora_historial:
        from datetime import date
        from .aplicacion.historial import Historial, progreso as resumir

        def progreso():
            return resumir(Historial(args.entrenadora_historial).leer(), date.today())
    nombres = {sid: ej.skill.nombre for sid, ej in catalogo.items()}
    en_vivo = EntrenadoraEnVivo(Entrenadora(generador, nombres), voz, progreso)
    return en_vivo, int((limite_s + MARGEN_VOZ_ENTRENADORA_S) * 1000)


def _abrir_fuente(args: argparse.Namespace, tiempo_real: bool,
                  camara: Optional[int] = None):
    if args.video:
        from .adaptadores.captura.fuente import FuenteVideo
        return FuenteVideo(args.video, tiempo_real=tiempo_real)
    from .adaptadores.captura.fuente import FuenteCamara
    return FuenteCamara(args.camara if camara is None else camara)


def _correr_interfaz(args, rutina, catalogo, voz, cerrar_sesion,
                     verbalizador=None, entrenadora=None) -> int:
    """Interfaz de escritorio: la sesión corre en un hilo del orquestador y
    la ventana ocupa el hilo principal."""
    from .adaptadores.pose.estimador import EstimadorPose
    from .adaptadores.captura.fuente import listar_camaras
    from .adaptadores.interfaz.orquestador import Orquestador
    from .adaptadores.interfaz.ventana import abrir
    from .aplicacion.perfiles import Perfiles

    # un vídeo no es una sesión de la usuaria: no entra en ningún historial
    perfiles = (None if args.sin_historial or args.video
                else Perfiles(config.HISTORIAL))
    orquestador = Orquestador(
        rutina, catalogo,
        crear_estimador=lambda: EstimadorPose(config.modelo_pose(args.modelo)),
        # la cámara la puede cambiar la interfaz entre sesiones
        abrir_fuente=lambda: _abrir_fuente(args, tiempo_real=True,
                                           camara=orquestador.camara),
        camara=None if args.video else args.camara,
        listar_camaras=None if args.video else listar_camaras,
        voz=voz, espejo=args.video is None,
        fuente="video" if args.video else "camara",
        al_terminar=cerrar_sesion, verbalizador=verbalizador, sin_dtw=args.sin_dtw,
        colocacion=not args.sin_colocacion, perfiles=perfiles,
        preparar_sesion=lambda sesion: (en_vivo.conectar(sesion, retencion_ms)
                                        if en_vivo is not None else None))
    en_vivo, retencion_ms = _crear_entrenadora(
        args, catalogo, voz, progreso=lambda: orquestador.progreso_activo())
    if entrenadora is not None:
        # con interfaz la pantalla de resumen no espera a la entrenadora
        entrenadora.update(en_vivo=en_vivo, esperar=False)
    try:
        abrir(orquestador, config.INTERFAZ, depurar=args.verbose)
    finally:
        orquestador.cerrar()
        voz.cerrar(esperar=True)
    return 0


def _correr_opencv(args, rutina, catalogo, voz, cerrar_sesion,
                   verbalizador=None, entrenadora=None) -> int:
    from .adaptadores.pose.estimador import EstimadorPose
    from .aplicacion.sesion import Sesion

    estimador = EstimadorPose(config.modelo_pose(args.modelo))
    fuente = _abrir_fuente(args, tiempo_real=not args.sin_ventana)
    espejo = args.video is None

    sesion = Sesion(rutina, catalogo, estimador, voz, verbalizador=verbalizador,
                    sin_dtw=args.sin_dtw,
                    colocacion=not args.sin_colocacion,
                    reconocer=args.reconocer)
    en_vivo, retencion_ms = _crear_entrenadora(args, catalogo, voz)
    if en_vivo is not None:
        en_vivo.conectar(sesion, retencion_ms)
        if entrenadora is not None:
            entrenadora["en_vivo"] = en_vivo

    ventana = not args.sin_ventana
    if ventana:
        import cv2
        from .adaptadores.interfaz.overlay import dibujar
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
        estimador.cerrar()
        if ventana:
            cv2.destroyAllWindows()

    # la voz se cierra después: el resumen final de la entrenadora aún puede sonar
    try:
        cerrar_sesion(sesion.resumen())
    finally:
        voz.cerrar(esperar=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
