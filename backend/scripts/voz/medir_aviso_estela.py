"""¿Cuándo avisa ESTELA de que oyó «Estela», y cuántas se pierden? Simulación a ritmo real (Mac).

    .venv/bin/python scripts/voz/medir_aviso_estela.py --codigo DIR_BACKEND --salida X.json

Hace pasar audio sintético por la escucha de verdad: `EscuchaVoz` con su hilo,
`Microfono` sin dispositivo (los bloques de 30 ms entran en su cola al ritmo del
reloj, como del micrófono) y Whisper small con la pista de llamada. `--codigo` es
la carpeta `backend` de la versión que se mide: así se compara la de antes con la
nueva con el mismo audio. Lo que no es la app: la voz de la usuaria es `say`
(Paulina, Mónica), la de ESTELA es Piper, sin sala ni eco (se suman las señales);
el ruido de ejercicio es sintético (pasos y respiración); cuando ESTELA «confirma»
una orden no suena nada, solo cuenta como hablando 0,8 s; el aviso sonoro entra
en el micrófono al mismo volumen que la voz de la usuaria.

Escenas por voz: «Estela» sola; «Estela, <orden>» seguida; con 1 s entre «Estela»
y la orden; con algo antes («Uf», «Bueno»); con ruido de ejercicio; empezando a
hablar justo cuando ESTELA empieza o acaba de hablar (la usuaria +6 dB). Y frases
sin «Estela» y ruido solo, para contar avisos y órdenes falsas.

Mide, contra el final de la palabra «Estela» en el audio: cuándo avisa (sonido o
punto «Te escucho»; en la versión de antes solo existe el punto). Contra el final
de lo dicho: cuándo se ejecuta la orden. Y cuánto trabaja Whisper.
"""
import argparse
import json
import logging
import queue
import sys
import threading
import time
from pathlib import Path

import numpy as np

FS = 16000
BLOQUE = 480
NIVEL = 0.05                     # RMS de la voz de la usuaria (y de ESTELA a 0 dB)
VOCES = ["Paulina", "Mónica"]
ORDENES = {"pausa": "pausar", "siguiente": "siguiente", "terminar": "terminar",
           "¿cómo voy?": "como_voy"}
ESTELA_DICE = "Endereza un poco el tronco, se va hacia la derecha."
SIN_ESTELA = ["Hola, buenos días", "Qué calor hace hoy", "Pausa", "Siguiente ejercicio por favor",
              "Me gusta mucho esta canción", "Voy a comer algo luego",
              "La estrella brilla esta noche", "Ella dijo que no viene"]


def recortar(x, umbral=0.01):
    e = np.convolve(np.abs(x), np.ones(160) / 160, "same")
    i = np.flatnonzero(e > umbral)
    return x[i[0]:i[-1] + 1] if len(i) else x


def ruido_ejercicio(seg, rng):
    """Pasos (golpes graves cada 0,45 s) y respiración (ruido que sube y baja)."""
    n = int(seg * FS)
    x = np.zeros(n, np.float32)
    k = int(0.06 * FS)
    for pos in range(int(0.2 * FS), n - k, int(0.45 * FS)):
        b = np.convolve(rng.normal(0, 0.15, k) * np.hanning(k), np.ones(8) / 8, "same")
        x[pos:pos + k] += b.astype(np.float32)
    env = 0.5 + 0.5 * np.sin(2 * np.pi * np.arange(n) / FS / 1.6)
    return x + (rng.normal(0, 0.02, n) * env).astype(np.float32)


class Escena:
    def __init__(self, nombre, grupo, usuaria, esperado, fin_llamada=None, fin_voz=None,
                 estela=None, ini_estela=0.0, extra=None):
        self.nombre, self.grupo, self.esperado = nombre, grupo, esperado
        self.fin_llamada, self.fin_voz = fin_llamada, fin_voz
        n = max(len(usuaria), int(ini_estela * FS) + (len(estela) if estela is not None else 0))
        n += int(3.0 * FS)
        self.usuaria = np.zeros(n, np.float32); self.usuaria[:len(usuaria)] = usuaria
        self.estela = None
        if estela is not None:
            self.estela = np.zeros(n, np.float32)
            a = int(ini_estela * FS); self.estela[a:a + len(estela)] = estela
            self.estela_ini, self.estela_fin = a, a + len(estela)
        self.extra = np.zeros(n, np.float32)
        if extra is not None:
            self.extra[:min(n, len(extra))] = extra[:n]


def construir(m, rng, rapido):
    """Lista de escenas (audio ya mezclable)."""
    escenas = []
    pre = int(0.6 * FS)
    tts = m.piper(ESTELA_DICE)
    tts = tts / m.rms(tts) * NIVEL
    voces = VOCES[:1] if rapido else VOCES

    def voz(v, t):
        x = recortar(m.say(v, t))
        return x / m.rms(x) * NIVEL

    for v in voces:
        estela = voz(v, "Estela.")
        ordenes = {p: voz(v, p.capitalize() + ".") for p in ORDENES}

        def junta(*partes):
            """(audio, fin de «Estela», fin de la voz) con `pre` de silencio delante."""
            x, fin_ll, t = [np.zeros(pre, np.float32)], None, pre
            for p in partes:
                if isinstance(p, float):
                    x.append(np.zeros(int(p * FS), np.float32)); t += int(p * FS)
                    continue
                x.append(p); t += len(p)
                if p is estela:
                    fin_ll = t / FS
            return np.concatenate(x), fin_ll, t / FS

        a, fl, fv = junta(estela)
        escenas.append(Escena(f"{v}: «Estela» sola", "A sola", a, None, fl, fv))
        for p, acc in ORDENES.items():
            a, fl, fv = junta(estela, 0.15, ordenes[p])
            escenas.append(Escena(f"{v}: «Estela, {p}» seguida", "B seguida", a, acc, fl, fv))
        for p in ("pausa", "siguiente"):
            a, fl, fv = junta(estela, 1.0, ordenes[p])
            escenas.append(Escena(f"{v}: «Estela» 1 s «{p}»", "C con hueco", a, ORDENES[p], fl, fv))
        for antes, p in (("Uf.", "pausa"), ("Bueno.", "siguiente")):
            a, fl, fv = junta(voz(v, antes), 0.1, estela, 0.15, ordenes[p])
            escenas.append(Escena(f"{v}: «{antes} Estela, {p}»", "D algo antes", a, ORDENES[p], fl, fv))
        for p in ("pausa", "siguiente"):
            a, fl, fv = junta(1.5, estela, 0.15, ordenes[p])
            escenas.append(Escena(f"{v}: «Estela, {p}» con ruido de ejercicio", "E ejercicio", a,
                                  ORDENES[p], fl, fv, extra=ruido_ejercicio(len(a) / FS + 3.0, rng)))
        for p in ("pausa", "siguiente"):
            a, fl, fv = junta(estela, 0.15, ordenes[p])
            a = a * 2.0                                   # +6 dB sobre ESTELA
            dur_u = (len(a) - pre) / FS
            # ESTELA empieza 0,3 s después de que la usuaria empiece a hablar
            escenas.append(Escena(f"{v}: «Estela, {p}» y ESTELA empieza a hablar", "F transición", a,
                                  ORDENES[p], fl, fv, estela=tts, ini_estela=pre / FS + 0.3))
            # la usuaria empieza 0,4 s antes de que ESTELA acabe
            ini = 0.6
            fin_e = ini + len(tts) / FS
            desp = int((fin_e - 0.4) * FS) - pre
            u = np.concatenate([np.zeros(max(0, desp), np.float32), a])
            escenas.append(Escena(f"{v}: «Estela, {p}» cuando ESTELA acaba", "F transición", u,
                                  ORDENES[p], fl + desp / FS, fv + desp / FS, estela=tts, ini_estela=ini))
            del dur_u
        for t in SIN_ESTELA:
            a, _, fv = junta(voz(v, t))
            escenas.append(Escena(f"{v}: «{t}» (sin Estela)", "G falsas", a, None, None, fv))
    for k in range(1 if rapido else 2):
        escenas.append(Escena(f"ruido de ejercicio {k}", "G falsas", np.zeros(int(8 * FS), np.float32),
                              None, extra=ruido_ejercicio(11.0, rng)))
    escenas.append(Escena("ruido blanco 0,05", "G falsas", np.zeros(int(8 * FS), np.float32), None,
                          extra=rng.normal(0, 0.05, int(11 * FS)).astype(np.float32)))
    return escenas


class Textos(logging.Handler):
    """Lo que la escucha anota (qué oyó Whisper y qué decidió), por escena."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lineas = []

    def emit(self, r):
        self.lineas.append(r.getMessage())


TEXTOS = Textos()


def correr(escena, rec, mods, tono, con_sonido=True):
    cv, mm, EscuchaVoz, DetectorDeFrase = mods
    rng = np.random.default_rng(1)
    piso = rng.normal(0, 0.002, len(escena.usuaria)).astype(np.float32)
    estado = {"i": 0, "corte": None, "habla_hasta": 0.0}
    sonidos, sucesos = [], []

    class MicSim(mm.Microfono):
        def __init__(self):
            self.dispositivo, self.nombre = None, "simulado"
            if hasattr(self, "_preparar"):
                self._preparar()
            else:
                self._cola, self._detector, self.nivel = queue.Queue(), DetectorDeFrase(), 0.0

        def cerrar(self):
            pass

    def estela_suena():
        e = escena
        if e.estela is None:
            return False
        i = estado["i"]
        fin = e.estela_fin if estado["corte"] is None else min(e.estela_fin, estado["corte"])
        return e.estela_ini <= i < fin

    class VozSim:
        def __init__(self):
            self.dichas = []

        @property
        def ocupada(self):
            return estela_suena() or time.perf_counter() < estado["habla_hasta"]

        @property
        def texto_hablando(self):
            return ESTELA_DICE if estela_suena() else None

        def interrumpir(self):
            if estela_suena():
                estado["corte"] = estado["i"]
            estado["habla_hasta"] = 0.0

        def ceder(self, s):
            pass

        def decir(self, texto, prioridad=0):
            self.dichas.append(texto)
            sucesos.append(("dice", time.perf_counter(), texto))
            estado["habla_hasta"] = time.perf_counter() + 0.8
            return True

    class Paso:
        colocando = False

        class pausa:
            pausada = False

    voz = VozSim()

    class SesionSim:
        terminada, hay_siguiente, hay_anterior = False, True, True
        paso_actual = Paso()
        oyente, escucha_siempre, escucha_hablando = None, False, False

        @property
        def puede_escuchar(self):
            return cv.puede_escuchar(False, False, hablando=(not self.escucha_hablando and voz.ocupada),
                                     terminada=False, siempre=self.escucha_siempre)

    def accion(nombre):
        return lambda: sucesos.append(("accion", time.perf_counter(), nombre))

    acciones = {a: accion(a) for a in ("pausar", "reanudar", "listo", "siguiente", "anterior",
                                       "reiniciar", "terminar", "reiniciar_sesion", "reconocer_si",
                                       "reconocer_no", "voz_si", "voz_no")}

    def como_voy(_s):
        sucesos.append(("accion", time.perf_counter(), "como_voy"))
        return None

    def sonar():
        sonidos.append(time.perf_counter())
        a = estado["i"] + int(0.05 * FS)                  # latencia de salida supuesta
        b = min(len(escena.extra), a + len(tono))
        if b > a:
            escena.extra[a:b] += tono[:b - a]

    mic = MicSim()
    TEXTOS.lineas = []
    kw = dict(llamada=True, interrumpir_hablando=True)
    try:
        e = EscuchaVoz(mic, rec, voz, acciones, como_voy, sonido=sonar if con_sonido else None, **kw)
    except TypeError:                                     # versión de antes: sin sonido
        e = EscuchaVoz(mic, rec, voz, acciones, como_voy, **kw)
    e.conectar(SesionSim())
    t0 = time.perf_counter()
    atenta = []

    def vigilar():
        while not parar.is_set():
            if not atenta and e.indicador().get("atenta"):
                atenta.append(time.perf_counter())
            time.sleep(0.01)

    parar = threading.Event()
    hv = threading.Thread(target=vigilar, daemon=True); hv.start()
    n = len(escena.usuaria) // BLOQUE
    for k in range(n):
        objetivo = t0 + (k + 1) * BLOQUE / FS
        espera = objetivo - time.perf_counter()
        if espera > 0:
            time.sleep(espera)
        a, b = k * BLOQUE, (k + 1) * BLOQUE
        estado["i"] = a
        x = escena.usuaria[a:b] + escena.extra[a:b] + piso[a:b]
        if escena.estela is not None and estela_suena():
            x = x + escena.estela[a:b]
        mic._cola.put(x.astype(np.float32))
    time.sleep(0.8)
    parar.set(); e.cerrar(); hv.join(1)
    rel = lambda t: round(t - t0, 3)                    # noqa: E731
    acciones_hechas = [(rel(t), a) for k, t, a in sucesos if k == "accion"]
    aviso = min([*sonidos[:1], *atenta[:1]]) if (sonidos or atenta) else None
    fila = {"escena": escena.nombre, "grupo": escena.grupo, "esperado": escena.esperado,
            "acciones": acciones_hechas, "dichas": [x for k, _, x in sucesos if k == "dice"],
            "sonidos": len(sonidos), "aviso_s": rel(aviso) if aviso else None,
            "fin_llamada_s": escena.fin_llamada, "fin_voz_s": escena.fin_voz,
            "temprano": getattr(e, "avisos_tempranos", None), "oido": list(TEXTOS.lineas)}
    if aviso and escena.fin_llamada is not None:
        fila["aviso_tras_estela_s"] = round(rel(aviso) - escena.fin_llamada, 3)
    hechas = [a for _, a in acciones_hechas]
    if escena.grupo == "G falsas":
        fila["ok"] = not hechas and aviso is None
    elif escena.esperado is None:
        fila["ok"] = not hechas and aviso is not None
    else:
        fila["ok"] = hechas == [escena.esperado]
        if fila["ok"]:
            fila["orden_tras_voz_s"] = round(acciones_hechas[0][0] - escena.fin_voz, 3)
    return fila


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codigo", required=True, help="carpeta backend de la versión a medir")
    ap.add_argument("--salida", required=True)
    ap.add_argument("--rapido", action="store_true", help="una voz y menos ruido (prueba)")
    ap.add_argument("--solo", help="solo los grupos que empiezan así (p. ej. F)")
    ap.add_argument("--sin-sonido", action="store_true", help="sin el aviso sonoro")
    args = ap.parse_args()
    sys.path.insert(0, str(Path(args.codigo).resolve()))
    from estela import config
    from estela.aplicacion import comandos_voz as cv
    from estela.adaptadores.voz_entrada import microfono as mm
    from estela.adaptadores.voz_entrada.escucha import EscuchaVoz
    from estela.adaptadores.voz_entrada.frases import DetectorDeFrase
    from estela.adaptadores.voz_entrada.reconocedor import PISTA_LLAMADA, ReconocedorWhisperCpp
    import estela
    sys.path.insert(1, str(Path(__file__).resolve().parent))
    import medir_interrumpir as m                         # say, piper, rms (ya con el `estela` de arriba)
    print("código:", Path(estela.__file__).parent, flush=True)
    lg = logging.getLogger("estela.adaptadores.voz_entrada.escucha")
    lg.setLevel(logging.DEBUG); lg.addHandler(TEXTOS)

    rec0 = ReconocedorWhisperCpp(config.modelo_voz_entrada(), pista=PISTA_LLAMADA)
    rec0.precalentar()
    carga = {"n": 0, "ms": 0.0}

    class Rec:
        def transcribir(self, audio):
            t = time.perf_counter()
            r = rec0.transcribir(audio)
            carga["n"] += 1; carga["ms"] += (time.perf_counter() - t) * 1000
            return r

    rng = np.random.default_rng(0)
    escenas = construir(m, rng, args.rapido)
    if args.solo:
        escenas = [x for x in escenas if x.grupo.startswith(args.solo)]
    t = np.arange(int(0.21 * FS)) / FS
    tono = np.zeros(len(t), np.float32)                   # el aviso a 16 kHz, mismo RMS que la voz
    try:
        from estela.adaptadores.voz.sonido import FS_SONIDO, tono_llamada
        tt = tono_llamada().astype(np.float32)
        tono = np.interp(np.arange(0, len(tt) / FS_SONIDO, 1 / FS),
                         np.arange(len(tt)) / FS_SONIDO, tt).astype(np.float32)
        tono = tono / m.rms(tono) * NIVEL
    except ImportError:
        pass
    filas = []
    t_audio = 0.0
    for k, esc in enumerate(escenas):
        f = correr(esc, Rec(), (cv, mm, EscuchaVoz, DetectorDeFrase), tono, not args.sin_sonido)
        t_audio += len(esc.usuaria) / FS
        filas.append(f)
        print(f"{k + 1}/{len(escenas)} {'ok ' if f['ok'] else 'MAL'} {f['escena']}: "
              f"acciones={f['acciones']} aviso_tras={f.get('aviso_tras_estela_s')} "
              f"sonidos={f['sonidos']} dichas={f['dichas']}", flush=True)
        if not f["ok"]:
            for linea in f["oido"]:
                print("      ", linea, flush=True)
    grupos = {}
    for f in filas:
        g = grupos.setdefault(f["grupo"], {"n": 0, "ok": 0, "aviso": [], "orden": []})
        g["n"] += 1; g["ok"] += bool(f["ok"])
        if f.get("aviso_tras_estela_s") is not None:
            g["aviso"].append(f["aviso_tras_estela_s"])
        if f.get("orden_tras_voz_s") is not None:
            g["orden"].append(f["orden_tras_voz_s"])
    resumen = {}
    for nombre, g in sorted(grupos.items()):
        r = {"bien": f"{g['ok']}/{g['n']}"}
        for clave in ("aviso", "orden"):
            if g[clave]:
                v = np.array(g[clave])
                r[f"{clave}_p50_s"] = round(float(np.median(v)), 2)
                r[f"{clave}_max_s"] = round(float(v.max()), 2)
                r[f"{clave}_n"] = len(v)
        resumen[nombre] = r
    resumen["whisper"] = {"llamadas": carga["n"], "ms_total": round(carga["ms"]),
                          "ms_por_s_de_audio": round(carga["ms"] / t_audio, 1),
                          "segundos_de_audio": round(t_audio)}
    json.dump({"codigo": str(Path(estela.__file__).parent), "resumen": resumen, "filas": filas},
              open(args.salida, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(resumen, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
