"""Variantes de las frases de corrección, escritas por un LLM local y revisadas.

    python scripts/generar_variantes.py --modelo qwen3:14b --salida DIR

Rol A de ADR-004: redactor **fuera de línea**. Para cada error del catálogo de
los ejercicios vigentes (regla × dirección × severidad) pide al modelo varias
formas de decir la corrección y las pasa por el validador de siempre, con el
tope de 12 palabras: sin partes del cuerpo ni lados ajenos, sin vocabulario
médico y sin pedir la dirección contraria. Las que pasan van a
`variantes_para_revisar.csv`, con la columna `decision` vacía para que una
persona escriba «ok» o «descartar». Las rechazadas quedan aparte, con el motivo.

Nada de esto entra solo a la aplicación: son candidatas. El validador no
comprueba que la frase conserve el sentido ni que esté en imperativo; para eso
es la revisión humana.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from estela.adaptadores.llm.llm_local import _descripcion_error  # noqa: E402
from estela.aplicacion.rutina import cargar_catalogo  # noqa: E402
from estela.dominio.feedback.contrato import ErrorTipificado, Severidad  # noqa: E402
from estela.dominio.feedback.verbalizador.plantillas import VerbalizadorPlantillas  # noqa: E402
from estela.dominio.feedback.verbalizador.validador import normalizar, validar  # noqa: E402

VIGENTES = ("jumping_jacks", "abduccion_cadera_izq", "abduccion_cadera_der", "plancha",
            "zancada_atras_izq", "zancada_atras_der")
MAX_PALABRAS = 12
URL = "http://127.0.0.1:11434/api/chat"

SISTEMA = (
    "Escribes frases cortas para la voz de un asistente de entrenamiento. Recibes un error "
    "de técnica ya detectado y una frase de ejemplo. Escribe {n} formas distintas de pedir "
    "la misma corrección.\n"
    "Reglas estrictas:\n"
    "1. Cada frase dice lo mismo que el ejemplo: no cambies qué se corrige ni cuánto.\n"
    "2. Nombra únicamente la parte del cuerpo indicada. Si se indica un lado, nómbralo tal "
    "cual; si no, no menciones lados.\n"
    "3. En imperativo y en segunda persona de singular (tú). Máximo {m} palabras. Una sola frase.\n"
    "4. Si se indica la corrección pedida, pídela en ese sentido y nunca en el contrario.\n"
    "5. No hables de dolor, lesiones ni salud. No expliques, no saludes, no animes.\n"
    "6. Que las {n} frases sean distintas entre sí y distintas del ejemplo.\n"
    "7. Responde en JSON con la forma {{\"variantes\": [\"...\", \"...\"]}}."
)


def errores(catalogo, ejercicios):
    for sid in ejercicios:
        ej = catalogo[sid]
        for regla in ej.skill.reglas:
            for direccion in (list(regla.direcciones.values()) or [None]):
                for sev in Severidad:
                    yield ErrorTipificado(
                        error_id=regla.error_id, segmento=regla.segmento, lado=regla.lado,
                        severidad=sev, fase="", repeticion=0, ejercicio_id=sid,
                        mensaje_id=regla.mensaje_id or regla.error_id, direccion=direccion)


def pedir(modelo, error, plantilla, n, temperatura, timeout_s):
    cuerpo = {
        "model": modelo, "stream": False, "think": False, "keep_alive": "30m",
        "options": {"temperature": temperatura, "num_predict": 400, "num_ctx": 4096},
        "format": {"type": "object",
                   "properties": {"variantes": {"type": "array", "items": {"type": "string"},
                                                "minItems": n, "maxItems": n}},
                   "required": ["variantes"], "additionalProperties": False},
        "messages": [
            {"role": "system", "content": SISTEMA.format(n=n, m=MAX_PALABRAS)},
            {"role": "user", "content": _descripcion_error(error) + f"\nfrase de ejemplo: {plantilla}"}],
    }
    req = urllib.request.Request(URL, data=json.dumps(cuerpo).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        resp = json.loads(r.read().decode("utf-8"))
    return [str(v).strip() for v in json.loads(resp["message"]["content"])["variantes"]]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modelo", required=True)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--por-error", type=int, default=4, help="variantes que se piden por error")
    p.add_argument("--temperatura", type=float, default=0.8)
    p.add_argument("--timeout-s", type=float, default=180.0)
    p.add_argument("--ejercicios", default=",".join(VIGENTES))
    a = p.parse_args(argv)

    catalogo = cargar_catalogo()
    plantillas = VerbalizadorPlantillas()
    buenas, malas, motivos, vistos = [], [], Counter(), set()
    fallos_modelo, t0 = 0, time.perf_counter()
    lista = list(errores(catalogo, a.ejercicios.split(",")))
    for k, err in enumerate(lista, 1):
        plantilla = plantillas.verbalizar(err).texto
        try:
            variantes = pedir(a.modelo, err, plantilla, a.por_error, a.temperatura, a.timeout_s)
        except Exception as e:                            # noqa: BLE001
            fallos_modelo += 1
            print(f"[{k}/{len(lista)}] {err.ejercicio_id}/{err.error_id}: fallo del modelo ({type(e).__name__})")
            continue
        base = {"ejercicio": err.ejercicio_id, "error_id": err.error_id,
                "severidad": err.severidad.value,
                "direccion": err.direccion.value if err.direccion else "",
                "parte": err.segmento, "lado": err.lado.value, "plantilla_actual": plantilla}
        for v in variantes:
            clave = (err.ejercicio_id, err.error_id, err.severidad.value, base["direccion"], normalizar(v))
            if clave in vistos or normalizar(v) == normalizar(plantilla):
                motivos["repetida"] += 1
                continue
            vistos.add(clave)
            res = validar(v, err, max_palabras=MAX_PALABRAS)
            fila = {**base, "variante": v, "palabras": len(normalizar(v).split()), "modelo": a.modelo}
            if res.valido:
                buenas.append({**fila, "decision": "", "notas": ""})
            else:
                motivos[res.motivo.split(":", 1)[0]] += 1
                malas.append({**fila, "motivo_rechazo": res.motivo})
        if k % 10 == 0:
            print(f"[{k}/{len(lista)}] {len(buenas)} válidas, {len(malas)} rechazadas", flush=True)

    a.salida.mkdir(parents=True, exist_ok=True)
    for nombre, filas in (("variantes_para_revisar.csv", buenas), ("variantes_rechazadas.csv", malas)):
        if filas:
            with open(a.salida / nombre, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(filas[0]))
                w.writeheader()
                w.writerows(filas)
    resumen = {"modelo": a.modelo, "errores": len(lista), "pedidas_por_error": a.por_error,
               "validas": len(buenas), "rechazadas": len(malas), "motivos": dict(motivos.most_common()),
               "fallos_del_modelo": fallos_modelo, "segundos": round(time.perf_counter() - t0)}
    (a.salida / "resumen_variantes.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1),
                                                    encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
