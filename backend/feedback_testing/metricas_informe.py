"""Métricas del Informe 2 como funciones puras (sin cámara, sin modelos, sin cv2).

Las usa `feedback_testing.informe2`, que reproduce vídeos por la `Sesion`
real; aquí solo hay aritmética sobre registros ya medidos, para poder
probarla con datos de resultado conocido.

Convención: una métrica que no se puede calcular devuelve `None` (o NaN en κ)
y el informe la muestra como «pendiente de medición», nunca como 0.

Objetivos aceptados por el equipo para el Informe 2: `OBJETIVOS_INFORME2`.
Es el único sitio donde están; el informe marca cada uno como cumple, no
cumple o pendiente con `evaluar`.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import (Any, Dict, Iterable, List, Mapping, Optional, Sequence,
                    Tuple, Union)

from estela.dominio.feedback.contrato import ErrorTipificado, Lado, Severidad
from estela.dominio.feedback.verbalizador.validador import afirmaciones_no_soportadas

# ---------------------------------------------------------------------------
# Objetivos
# ---------------------------------------------------------------------------

#: Objetivos aceptados para el Informe 2 `[R]` (acuerdo del equipo, no
#: literatura). `op`: el valor medido debe cumplir `medido op valor`.
OBJETIVOS_INFORME2: Dict[str, Dict[str, Any]] = {
    "pose_p95_ms": {"descripcion": "p95 de la estimación de pose",
                    "op": "<=", "valor": 33.0, "unidad": "ms"},
    "fps_sostenidos": {"descripcion": "FPS sostenidos",
                       "op": ">=", "valor": 25.0, "unidad": "fps"},
    "deteccion_voz_p95_s": {"descripcion": "p95 detección → inicio de voz",
                            "op": "<=", "valor": 1.0, "unidad": "s"},
    "precision": {"descripcion": "Precisión por ejercicio",
                  "op": ">=", "valor": 0.80, "unidad": ""},
    "recobrado": {"descripcion": "Recobrado por ejercicio",
                  "op": ">=", "valor": 0.70, "unidad": ""},
    "sobrecorreccion": {"descripcion": "Sobrecorrección en repeticiones correctas",
                        "op": "<=", "valor": 0.10, "unidad": ""},
    "mensajes_correctos": {"descripcion": "Mensajes correctos",
                           "op": ">=", "valor": 0.90, "unidad": ""},
}

CUMPLE = "cumple"
NO_CUMPLE = "no cumple"
PENDIENTE = "pendiente"


def evaluar(clave: str, valor: Optional[float]) -> str:
    """cumple / no cumple / pendiente (si no hay valor medido)."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return PENDIENTE
    obj = OBJETIVOS_INFORME2[clave]
    ok = valor <= obj["valor"] if obj["op"] == "<=" else valor >= obj["valor"]
    return CUMPLE if ok else NO_CUMPLE


def texto_objetivo(clave: str) -> str:
    obj = OBJETIVOS_INFORME2[clave]
    valor = obj["valor"]
    if obj["unidad"] == "":
        return f"{obj['op'].replace('<=', '≤').replace('>=', '≥')} {valor * 100:.0f} %"
    return f"{obj['op'].replace('<=', '≤').replace('>=', '≥')} {valor:g} {obj['unidad']}"


# ---------------------------------------------------------------------------
# Estadística básica
# ---------------------------------------------------------------------------

def percentil(valores: Sequence[float], p: float) -> Optional[float]:
    """Interpolación lineal (como numpy 'linear'). None si no hay datos."""
    if not valores:
        return None
    xs = sorted(valores)
    k = (len(xs) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def resumen_serie(valores: Sequence[float]) -> Dict[str, Optional[float]]:
    """n, media, p50, p95 y máximo. Con la lista vacía todo es None salvo n."""
    vs = [float(v) for v in valores]
    if not vs:
        return {"n": 0, "media": None, "p50": None, "p95": None, "max": None}
    return {"n": len(vs), "media": sum(vs) / len(vs), "p50": percentil(vs, 50),
            "p95": percentil(vs, 95), "max": max(vs)}


def pendiente(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """Pendiente por mínimos cuadrados. None con < 2 puntos o x constante."""
    if len(xs) != len(ys):
        raise ValueError("xs e ys deben tener la misma longitud")
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx


# ---------------------------------------------------------------------------
# Rendimiento: FPS, frames descartados y retraso acumulado
# ---------------------------------------------------------------------------

def rendimiento(frames_fuente: int, procesados: int, duracion_s: float
                ) -> Dict[str, Optional[float]]:
    """FPS sostenidos = frames procesados / tiempo de pared.

    `frames_fuente` son los que entregó la fuente (vídeo o cámara);
    `descartados` = fuente − procesados (política «último frame»; con la cola
    sin descarte es 0). `[I]` En un vídeo los FPS sostenidos nunca superan los
    FPS nominales de la fuente: un vídeo a 24 fps no puede dar 25.
    """
    if procesados > frames_fuente:
        raise ValueError("no se pueden procesar más frames de los que hay")
    return {
        "frames_fuente": frames_fuente,
        "procesados": procesados,
        "descartados": frames_fuente - procesados,
        "fraccion_descartada": ((frames_fuente - procesados) / frames_fuente
                                if frames_fuente else None),
        "fps_sostenidos": procesados / duracion_s if duracion_s > 0 else None,
    }


def retraso_acumulado(llegadas_s: Sequence[float], fines_s: Sequence[float]
                      ) -> Dict[str, Optional[float]]:
    """Retraso por frame = fin de su procesamiento − marca nominal de llegada.

    Las marcas son de un mismo reloj (p. ej. `time.perf_counter()`), en
    segundos; el resultado va en ms. `deriva_ms_por_s` es la pendiente del
    retraso frente al tiempo de llegada: ≈ 0 si el sistema da abasto; > 0 si
    el retraso crece sin límite (cola sin descarte más lenta que la fuente).
    Con la política «último frame» el retraso queda acotado y lo que crece son
    los descartados.
    """
    if len(llegadas_s) != len(fines_s):
        raise ValueError("llegadas y fines deben tener la misma longitud")
    retrasos = [(f - l) * 1000.0 for l, f in zip(llegadas_s, fines_s)]
    r = resumen_serie(retrasos)
    rel = [l - llegadas_s[0] for l in llegadas_s] if llegadas_s else []
    r["final"] = retrasos[-1] if retrasos else None
    r["deriva_ms_por_s"] = pendiente(rel, retrasos) if retrasos else None
    return r


# ---------------------------------------------------------------------------
# Silencios por causa (registro por frame de `Sesion(registrar=True)`)
# ---------------------------------------------------------------------------

def tasas_silencio(registro: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Cuenta los frames por causa.

    - `sin_persona`: el estimador no vio a nadie.
    - `pausada`: la sesión estaba en pausa (por motivo de pausa); el motor no
      se llamó.
    - `evaluados`: el motor se llamó. Cada uno termina en un mensaje
      (corrección o refuerzo) o en un silencio con motivo (`MOTIVO_*` de
      `contrato.py`). Las tasas por motivo son sobre los evaluados.
    """
    total = sin_persona = evaluados = correcciones = refuerzos = 0
    pausas: Dict[str, int] = {}
    motivos: Dict[str, int] = {}
    for e in registro:
        total += 1
        if not e.get("persona"):
            sin_persona += 1
            continue
        if not e.get("evaluado"):
            if e.get("pausada"):
                m = e.get("motivo_pausa") or "desconocido"
                pausas[m] = pausas.get(m, 0) + 1
            continue
        evaluados += 1
        msg = e.get("mensaje")
        if msg:
            if msg.get("refuerzo"):
                refuerzos += 1
            else:
                correcciones += 1
        else:
            m = e.get("motivo_silencio") or "desconocido"
            motivos[m] = motivos.get(m, 0) + 1
    return {
        "frames": total,
        "sin_persona": sin_persona,
        "pausada": dict(sorted(pausas.items())),
        "evaluados": evaluados,
        "correcciones": correcciones,
        "refuerzos": refuerzos,
        "motivos": dict(sorted(motivos.items(), key=lambda kv: -kv[1])),
        "tasa_motivos": {m: v / evaluados for m, v in motivos.items()} if evaluados else {},
        "tasa_sin_persona": sin_persona / total if total else None,
        "tasa_pausada": sum(pausas.values()) / total if total else None,
    }


# ---------------------------------------------------------------------------
# Anotación humana (formato `estela-anotacion-v1`; ver README)
# ---------------------------------------------------------------------------

FORMATO_ANOTACION = "estela-anotacion-v1"


@dataclass(frozen=True)
class ErrorAnotado:
    error_id: str
    #: opcionales: si la anotadora los da, `mensajes_correctos` los compara
    #: con los del mensaje; si no, se usan los de la regla del skill
    segmento: Optional[str] = None
    lado: Optional[str] = None


@dataclass(frozen=True)
class RepAnotada:
    t_ini_ms: int
    t_fin_ms: int
    errores: Tuple[ErrorAnotado, ...] = ()
    ejercicio_id: str = ""
    bloque: Optional[int] = None

    @property
    def ids(self) -> Tuple[str, ...]:
        return tuple(e.error_id for e in self.errores)

    @property
    def correcta(self) -> bool:
        return not self.errores


@dataclass(frozen=True)
class Anotacion:
    video: str
    ejercicio_id: str
    anotadora: str
    repeticiones: Tuple[RepAnotada, ...]
    bloque: Optional[int] = None
    notas: str = ""
    #: tramo del vídeo que se evalúa (ms); None = el vídeo entero
    tramo_ms: Optional[Tuple[int, int]] = None


def anotacion_desde_dict(d: Mapping[str, Any]) -> Anotacion:
    """Valida y convierte. Lanza ValueError con un mensaje legible."""
    if d.get("formato") != FORMATO_ANOTACION:
        raise ValueError(f"formato distinto de '{FORMATO_ANOTACION}'")
    for clave in ("video", "ejercicio_id", "anotadora", "repeticiones"):
        if clave not in d:
            raise ValueError(f"falta la clave '{clave}'")
    bloque = d.get("bloque")
    if bloque is not None and bloque not in (1, 2, 3, 4):
        raise ValueError("bloque debe ser 1-4 (EXP-009) o null")
    reps: List[RepAnotada] = []
    for i, r in enumerate(d["repeticiones"]):
        ini, fin = int(r["t_ini_ms"]), int(r["t_fin_ms"])
        if fin <= ini:
            raise ValueError(f"repetición {i}: t_fin_ms debe ser > t_ini_ms")
        errores = []
        for e in r.get("errores", []):
            if isinstance(e, str):
                errores.append(ErrorAnotado(e))
            else:
                errores.append(ErrorAnotado(e["error_id"], e.get("segmento"),
                                            e.get("lado")))
        rb = r.get("bloque", bloque)
        if rb is not None and rb not in (1, 2, 3, 4):
            raise ValueError(f"repetición {i}: bloque debe ser 1-4")
        reps.append(RepAnotada(ini, fin, tuple(errores),
                               r.get("ejercicio_id", d["ejercicio_id"]), rb))
    reps.sort(key=lambda r: r.t_ini_ms)
    for a, b in zip(reps, reps[1:]):
        if b.t_ini_ms < a.t_fin_ms:
            raise ValueError(f"repeticiones solapadas en {b.t_ini_ms} ms")
    tramo = d.get("tramo_ms")
    return Anotacion(d["video"], d["ejercicio_id"], d["anotadora"], tuple(reps),
                     bloque, d.get("notas", ""),
                     (int(tramo[0]), int(tramo[1])) if tramo else None)


def cargar_anotacion(ruta: Union[str, Path]) -> Anotacion:
    with open(ruta, encoding="utf-8") as f:
        return anotacion_desde_dict(json.load(f))


# ---------------------------------------------------------------------------
# Precisión, recobrado y F1 frente a la anotación
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MensajeEmitido:
    """Un mensaje de la sesión. `error_id` None = refuerzo (elogio)."""
    t_ms: int
    error_id: Optional[str]
    segmento: Optional[str] = None
    lado: Optional[str] = None
    severidad: Optional[str] = None
    texto: str = ""
    ejercicio_id: str = ""


def _distancia(t: int, r: RepAnotada) -> int:
    if r.t_ini_ms <= t <= r.t_fin_ms:
        return 0
    return min(abs(t - r.t_ini_ms), abs(t - r.t_fin_ms))


def atribuir(t_ms: int, error_id: Optional[str], reps: Sequence[RepAnotada],
             tolerancia_ms: int) -> Optional[int]:
    """Índice de la repetición a la que se atribuye un mensaje, o None.

    Candidatas: las repeticiones cuyo intervalo, ampliado ± `tolerancia_ms`,
    contiene `t_ms`. Si alguna candidata tiene anotado ese `error_id`, gana la
    más cercana de esas (la tolerancia cubre el mensaje que llega al empezar
    la repetición siguiente). Si no, la más cercana de todas. Sin candidatas:
    None (el mensaje cae fuera de toda repetición anotada).
    """
    cands = [i for i, r in enumerate(reps)
             if r.t_ini_ms - tolerancia_ms <= t_ms <= r.t_fin_ms + tolerancia_ms]
    if not cands:
        return None
    con_error = [i for i in cands if error_id is not None and error_id in reps[i].ids]
    elegibles = con_error or cands
    return min(elegibles, key=lambda i: (_distancia(t_ms, reps[i]), i))


def episodios(reps: Sequence[RepAnotada], error_id: str) -> List[Tuple[int, int]]:
    """Tramos máximos de repeticiones consecutivas con `error_id` anotado.

    Se agrupan porque la política de silencio exige 2–3 repeticiones seguidas
    y luego un refractario: el sistema no puede hablar en cada repetición.
    """
    tramos: List[Tuple[int, int]] = []
    inicio = None
    for i, r in enumerate(reps):
        if error_id in r.ids:
            if inicio is None:
                inicio = i
        elif inicio is not None:
            tramos.append((inicio, i - 1))
            inicio = None
    if inicio is not None:
        tramos.append((inicio, len(reps) - 1))
    return tramos


@dataclass
class Conteo:
    """Conteos sumables entre vídeos y anotaciones."""
    vp: int = 0                 # mensajes atribuidos a una rep con ese error
    fp: int = 0                 # el resto (incluidos los que caen fuera)
    fuera: int = 0              # mensajes sin repetición anotada (ya en fp)
    episodios: int = 0
    detectados: int = 0

    def __iadd__(self, o: "Conteo") -> "Conteo":
        self.vp += o.vp
        self.fp += o.fp
        self.fuera += o.fuera
        self.episodios += o.episodios
        self.detectados += o.detectados
        return self

    @property
    def precision(self) -> Optional[float]:
        n = self.vp + self.fp
        return self.vp / n if n else None

    @property
    def recobrado(self) -> Optional[float]:
        return self.detectados / self.episodios if self.episodios else None

    @property
    def f1(self) -> Optional[float]:
        p, r = self.precision, self.recobrado
        if p is None or r is None or p + r == 0:
            return None
        return 2 * p * r / (p + r)

    def a_dict(self) -> Dict[str, Any]:
        return {"vp": self.vp, "fp": self.fp, "fuera": self.fuera,
                "episodios": self.episodios, "detectados": self.detectados,
                "precision": self.precision, "recobrado": self.recobrado,
                "f1": self.f1}


def conteos_por_error(reps: Sequence[RepAnotada],
                      mensajes: Sequence[MensajeEmitido],
                      tolerancia_ms: int = 1000,
                      error_ids: Iterable[str] = ()) -> Dict[str, Conteo]:
    """Precisión y recobrado por `error_id` frente a una anotación.

    - Precisión: un mensaje de corrección es VP si la repetición a la que se
      atribuye (`atribuir`) tiene anotado su `error_id`; si no, FP. Un mensaje
      fuera de toda repetición anotada cuenta como FP (y en `fuera`).
    - Recobrado por episodios (`episodios`): un episodio cuenta como detectado
      si hay al menos un mensaje con ese `error_id` cuyo `t_ms` cae dentro del
      tramo del episodio ampliado ± `tolerancia_ms`.
    - Los refuerzos (`error_id` None) no entran: se miden aparte.

    `error_ids` añade errores del catálogo sin mensajes ni anotaciones, para
    que salgan en la tabla con ceros.
    """
    reps = sorted(reps, key=lambda r: r.t_ini_ms)
    ids = set(error_ids)
    ids.update(e for r in reps for e in r.ids)
    ids.update(m.error_id for m in mensajes if m.error_id)
    res = {e: Conteo() for e in sorted(ids)}
    for m in mensajes:
        if m.error_id is None:
            continue
        i = atribuir(m.t_ms, m.error_id, reps, tolerancia_ms)
        c = res[m.error_id]
        if i is None:
            c.fp += 1
            c.fuera += 1
        elif m.error_id in reps[i].ids:
            c.vp += 1
        else:
            c.fp += 1
    for e, c in res.items():
        tiempos = [m.t_ms for m in mensajes if m.error_id == e]
        for a, b in episodios(reps, e):
            c.episodios += 1
            ini = reps[a].t_ini_ms - tolerancia_ms
            fin = reps[b].t_fin_ms + tolerancia_ms
            if any(ini <= t <= fin for t in tiempos):
                c.detectados += 1
    return res


def agregar(conteos: Iterable[Conteo]) -> Conteo:
    total = Conteo()
    for c in conteos:
        total += c
    return total


def deteccion_cruda(reps: Sequence[RepAnotada],
                    disparos: Sequence[Tuple[int, str]],
                    tolerancia_ms: int = 0) -> Dict[str, Conteo]:
    """Detección **antes** de la política de silencio, por repetición.

    `disparos`: (t_ms, error_id) de cada frame en que la regla se disparó
    (`MotorDecision.disparadas`). Por repetición y error: VP si se disparó y
    está anotado; FP si se disparó y no lo está; el recobrado cuenta cada
    repetición anotada con el error como un «episodio» de una repetición.
    """
    reps = sorted(reps, key=lambda r: r.t_ini_ms)
    vistos: List[set] = [set() for _ in reps]
    fuera: Dict[str, int] = {}
    for t, e in disparos:
        i = atribuir(t, e, reps, tolerancia_ms)
        if i is None:
            fuera[e] = fuera.get(e, 0) + 1
        else:
            vistos[i].add(e)
    ids = {e for r in reps for e in r.ids} | {e for _, e in disparos}
    res = {e: Conteo() for e in sorted(ids)}
    for r, vs in zip(reps, vistos):
        for e in ids:
            anotado, disparado = e in r.ids, e in vs
            c = res[e]
            if anotado:
                c.episodios += 1
                c.detectados += int(disparado)
            if disparado:
                c.vp += int(anotado)
                c.fp += int(not anotado)
    for e, n in fuera.items():
        # una repetición «fuera» por error, no un FP por frame
        res[e].fuera += 1
        res[e].fp += 1
    return res


def sobrecorreccion(reps: Sequence[RepAnotada], mensajes: Sequence[MensajeEmitido],
                    tolerancia_ms: int = 1000) -> Dict[str, Optional[float]]:
    """% de repeticiones anotadas como correctas a las que se atribuye alguna
    corrección (con la misma atribución que la precisión)."""
    reps = sorted(reps, key=lambda r: r.t_ini_ms)
    correctas = [i for i, r in enumerate(reps) if r.correcta]
    corregidas = set()
    for m in mensajes:
        if m.error_id is None:
            continue
        i = atribuir(m.t_ms, m.error_id, reps, tolerancia_ms)
        if i is not None and reps[i].correcta:
            corregidas.add(i)
    return {"repeticiones_correctas": len(correctas),
            "con_correccion": len(corregidas),
            "tasa": len(corregidas) / len(correctas) if correctas else None}


def mensajes_correctos(reps: Sequence[RepAnotada], mensajes: Sequence[MensajeEmitido],
                       reglas: Mapping[str, Tuple[str, str]],
                       tolerancia_ms: int = 1000) -> Dict[str, Optional[float]]:
    """% de correcciones cuyo `error_id`, segmento y lado coinciden con un
    error anotado en la repetición atribuida.

    `reglas`: error_id → (segmento, lado) del skill; se usa cuando la
    anotadora no escribió segmento o lado. Con plantillas, si el `error_id`
    coincide, segmento y lado también (salen de la regla); la comparación
    importa con un verbalizador o un catálogo que no los fije.
    """
    reps = sorted(reps, key=lambda r: r.t_ini_ms)
    n = ok = 0
    for m in mensajes:
        if m.error_id is None:
            continue
        n += 1
        i = atribuir(m.t_ms, m.error_id, reps, tolerancia_ms)
        if i is None:
            continue
        for e in reps[i].errores:
            if e.error_id != m.error_id:
                continue
            seg, lado = reglas.get(e.error_id, (None, None))
            seg = e.segmento or seg
            lado = e.lado or lado
            if (seg is None or seg == m.segmento) and (lado is None or lado == m.lado):
                ok += 1
                break
    return {"mensajes": n, "correctos": ok, "tasa": ok / n if n else None}


def refuerzos_indebidos(reps: Sequence[RepAnotada], mensajes: Sequence[MensajeEmitido],
                        tolerancia_ms: int = 0) -> Dict[str, Optional[float]]:
    """Elogios atribuidos a una repetición con algún error anotado."""
    reps = sorted(reps, key=lambda r: r.t_ini_ms)
    elogios = [m for m in mensajes if m.error_id is None]
    malos = 0
    for m in elogios:
        i = atribuir(m.t_ms, None, reps, tolerancia_ms)
        if i is not None and not reps[i].correcta:
            malos += 1
    return {"refuerzos": len(elogios), "indebidos": malos,
            "tasa": malos / len(elogios) if elogios else None}


def tasa_aserciones_no_soportadas(mensajes: Sequence[MensajeEmitido]
                                  ) -> Dict[str, Optional[float]]:
    """M2 de EXP-001 sobre los mensajes reales: correcciones cuyo texto nombra
    un segmento o lado que no está en su error tipificado."""
    n = malos = 0
    for m in mensajes:
        if m.error_id is None or not m.texto or not m.segmento:
            continue
        err = ErrorTipificado(
            error_id=m.error_id, segmento=m.segmento, lado=Lado(m.lado or "na"),
            severidad=Severidad(m.severidad or "leve"), fase="", repeticion=None,
            ejercicio_id=m.ejercicio_id)
        n += 1
        if afirmaciones_no_soportadas(m.texto, err):
            malos += 1
    return {"mensajes": n, "no_soportadas": malos, "tasa": malos / n if n else None}


# ---------------------------------------------------------------------------
# Acuerdo entre anotadoras
# ---------------------------------------------------------------------------

def kappa_cohen(a: Sequence[bool], b: Sequence[bool]) -> float:
    """κ de Cohen binario. NaN si no hay datos o si el acuerdo esperado es 1
    (las dos ponen siempre la misma etiqueta: κ indefinido)."""
    if len(a) != len(b):
        raise ValueError("las dos anotaciones deben tener la misma longitud")
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(1 for x, y in zip(a, b) if bool(x) == bool(y)) / n
    pa, pb = sum(map(bool, a)) / n, sum(map(bool, b)) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe >= 1.0:
        return float("nan")
    return (po - pe) / (1 - pe)


def _iou(a: RepAnotada, b: RepAnotada) -> float:
    inter = min(a.t_fin_ms, b.t_fin_ms) - max(a.t_ini_ms, b.t_ini_ms)
    if inter <= 0:
        return 0.0
    union = max(a.t_fin_ms, b.t_fin_ms) - min(a.t_ini_ms, b.t_ini_ms)
    return inter / union


def emparejar_repeticiones(a: Sequence[RepAnotada], b: Sequence[RepAnotada],
                           iou_minimo: float = 0.5) -> List[Tuple[int, int]]:
    """Empareja las repeticiones de dos anotadoras por solapamiento temporal
    (IoU), de mayor a menor, cada una como mucho una vez."""
    pares = sorted(((_iou(x, y), i, j) for i, x in enumerate(a)
                    for j, y in enumerate(b)), reverse=True)
    usados_a, usados_b, res = set(), set(), []
    for iou, i, j in pares:
        if iou < iou_minimo:
            break
        if i in usados_a or j in usados_b:
            continue
        usados_a.add(i)
        usados_b.add(j)
        res.append((i, j))
    return sorted(res)


def kappa_anotadoras(a: Anotacion, b: Anotacion, error_ids: Iterable[str] = (),
                     iou_minimo: float = 0.5) -> Dict[str, Any]:
    """κ entre dos anotaciones del mismo vídeo: una etiqueta binaria por
    (repetición emparejada × error_id). `error_ids` (los del skill) se
    añaden a los que aparezcan anotados."""
    if a.video != b.video:
        raise ValueError("las anotaciones son de vídeos distintos")
    pares = emparejar_repeticiones(a.repeticiones, b.repeticiones, iou_minimo)
    ids = sorted(set(error_ids) | {e for r in a.repeticiones for e in r.ids}
                 | {e for r in b.repeticiones for e in r.ids})
    xa: List[bool] = []
    xb: List[bool] = []
    por_error: Dict[str, float] = {}
    for e in ids:
        ea = [e in a.repeticiones[i].ids for i, _ in pares]
        eb = [e in b.repeticiones[j].ids for _, j in pares]
        por_error[e] = kappa_cohen(ea, eb)
        xa += ea
        xb += eb
    return {"kappa": kappa_cohen(xa, xb), "pares": len(pares),
            "sin_pareja_a": len(a.repeticiones) - len(pares),
            "sin_pareja_b": len(b.repeticiones) - len(pares),
            "por_error": por_error,
            "anotadoras": (a.anotadora, b.anotadora)}


# ---------------------------------------------------------------------------
# Pose y DTW
# ---------------------------------------------------------------------------

def jitter(serie: Sequence[Optional[float]], ventana: int = 15) -> Optional[float]:
    """Desviación típica del residuo frente a una media móvil centrada de
    `ventana` frames, sobre los tramos sin huecos (None/NaN). Mide el temblor
    de la estimación en un tramo **quieto**; en movimiento mezcla el temblor
    con el propio movimiento. None si no hay ningún tramo de `ventana` frames.
    """
    if ventana < 3 or ventana % 2 == 0:
        raise ValueError("la ventana debe ser impar y ≥ 3")
    medio = ventana // 2
    residuos: List[float] = []
    tramo: List[float] = []

    def cerrar(t: List[float]) -> None:
        for i in range(medio, len(t) - medio):
            media = sum(t[i - medio:i + medio + 1]) / ventana
            residuos.append(t[i] - media)

    for v in list(serie) + [None]:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            cerrar(tramo)
            tramo = []
        else:
            tramo.append(float(v))
    if len(residuos) < 2:
        return None
    m = sum(residuos) / len(residuos)
    return math.sqrt(sum((r - m) ** 2 for r in residuos) / (len(residuos) - 1))


def latencia_por_longitud(longitudes: Sequence[int], latencias_ms: Sequence[float],
                          tramos: Sequence[int] = (0, 15, 30, 60, 120, 240)
                          ) -> Dict[str, Any]:
    """Latencia del DTW según la longitud del prefijo: p50/p95 por tramo y
    pendiente (ms por frame de prefijo)."""
    if len(longitudes) != len(latencias_ms):
        raise ValueError("longitudes y latencias deben tener la misma longitud")
    filas = []
    limites = list(tramos) + [math.inf]
    for lo, hi in zip(limites, limites[1:]):
        vs = [l for n, l in zip(longitudes, latencias_ms) if lo < n <= hi]
        if vs:
            filas.append({"desde": lo + 1, "hasta": None if hi == math.inf else hi,
                          **resumen_serie(vs)})
    return {"tramos": filas,
            "pendiente_ms_por_frame": pendiente([float(n) for n in longitudes],
                                                list(latencias_ms)),
            "longitud_max": max(longitudes) if longitudes else None}


__all__ = [
    "OBJETIVOS_INFORME2", "CUMPLE", "NO_CUMPLE", "PENDIENTE", "evaluar",
    "texto_objetivo", "percentil", "resumen_serie", "pendiente", "rendimiento",
    "retraso_acumulado", "tasas_silencio", "FORMATO_ANOTACION", "ErrorAnotado",
    "RepAnotada", "Anotacion", "anotacion_desde_dict", "cargar_anotacion",
    "MensajeEmitido", "atribuir", "episodios", "Conteo", "conteos_por_error",
    "agregar", "deteccion_cruda", "sobrecorreccion", "mensajes_correctos",
    "refuerzos_indebidos", "tasa_aserciones_no_soportadas", "kappa_cohen",
    "emparejar_repeticiones", "kappa_anotadoras", "jitter",
    "latencia_por_longitud",
]
