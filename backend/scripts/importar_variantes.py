"""Pasa las variantes aprobadas (decision = ok) de una hoja revisada a `plantillas_es.json`.

    python scripts/importar_variantes.py ../PRUEBAS/variantes_70b/variantes_70b_revisadas.csv [--escribir]

Rol A de ADR-004: frases redactadas por un LLM fuera de línea, revisadas por una persona y
usadas como plantillas fijas (rotan por repetición; el LLM en vivo las recibe además como
frase de referencia). Sin `--escribir` solo informa.

Para cada fila con `decision` = ok:
- el `error_id` se traduce al `mensaje_id` de su regla (varios errores comparten mensaje);
- el lado se vuelve hueco: «izquierda/derecha/izquierdo/derecho» → `{lado}` y «a la / hacia la
  derecha» → `{hacia_lado}` en la inclinación lateral, para que una frase sirva a los dos lados;
- se añade el punto final y se descartan las repetidas;
- se rellena con **cada** regla que usa ese mensaje (los dos lados, cada dirección) y se pasa por
  el mismo validador que el LLM (`validar`). Si falla en alguna, no se importa y se dice por qué.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from estela.aplicacion.rutina import cargar_catalogo  # noqa: E402
from estela.dominio.feedback.contrato import ErrorTipificado, Severidad  # noqa: E402
from estela.dominio.feedback.verbalizador.plantillas import (  # noqa: E402
    VerbalizadorPlantillas, ruta_plantillas_por_defecto,
)
from estela.dominio.feedback.verbalizador.validador import validar  # noqa: E402

_LADO = re.compile(r"\b(izquierd[ao]|derech[ao])\b", re.IGNORECASE)
_HACIA = re.compile(r"\b(a|hacia) la (izquierda|derecha)\b", re.IGNORECASE)


def insertar(texto: str, mensaje: str, sev: str, nuevas: list) -> str:
    """Añade `nuevas` a la línea `"sev": [...]` del bloque `"mensaje": {` sin tocar el resto
    del archivo (que está escrito a mano, con su formato)."""
    inicio = texto.index(f'\n  "{mensaje}": {{')
    fin = texto.index("\n  }", inicio)
    bloque = texto[inicio:fin]
    patron = re.compile(r'(\n    "' + re.escape(sev) + r'": )(\[.*\])')
    m = patron.search(bloque)
    lista = json.loads(m.group(2)) + nuevas
    bloque = bloque[:m.start(2)] + json.dumps(lista, ensure_ascii=False) + bloque[m.end(2):]
    return texto[:inicio] + bloque + texto[fin:]


def con_huecos(texto: str, mensaje_id: str) -> str:
    t = " ".join(texto.split()).rstrip(".")
    if mensaje_id == "inclinacion_lateral":
        t = _HACIA.sub("{hacia_lado}", t)
    t = _LADO.sub("{lado}", t)
    return t[0].upper() + t[1:] + "."


def reglas_por_mensaje(catalogo):
    por = {}
    for sid, ej in catalogo.items():
        for r in ej.skill.reglas:
            por.setdefault(r.mensaje_id or r.error_id, []).append((sid, r))
    return por


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("hoja", type=Path)
    ap.add_argument("--escribir", action="store_true")
    a = ap.parse_args()

    catalogo = cargar_catalogo()
    error_a_mensaje = {r.error_id: (r.mensaje_id or r.error_id)
                       for ej in catalogo.values() for r in ej.skill.reglas}
    reglas = reglas_por_mensaje(catalogo)
    ruta = Path(ruta_plantillas_por_defecto())
    datos = json.loads(ruta.read_text(encoding="utf-8"))

    nuevas, rechazadas, repetidas = {}, [], 0
    for fila in csv.DictReader(a.hoja.open(encoding="utf-8")):
        if fila["decision"].strip().lower() != "ok":
            continue
        mensaje = error_a_mensaje.get(fila["error_id"])
        if mensaje is None or mensaje not in datos:
            rechazadas.append((fila["variante"], f"sin mensaje para {fila['error_id']}"))
            continue
        sev = fila["severidad"]
        plantilla = con_huecos(fila["variante"], mensaje)
        existentes = {p.lower() for p in datos[mensaje].get(sev, [])} | {
            p.lower() for p in nuevas.get((mensaje, sev), [])}
        if plantilla.lower() in existentes:
            repetidas += 1
            continue
        motivo = ""
        prueba = VerbalizadorPlantillas(validar_salida=False)
        for sid, r in reglas[mensaje]:
            for direccion in (list(r.direcciones.values()) or [None]):
                e = ErrorTipificado(error_id=r.error_id, segmento=r.segmento, lado=r.lado,
                                    severidad=Severidad(sev), fase="", repeticion=0,
                                    ejercicio_id=sid, mensaje_id=mensaje, direccion=direccion)
                texto = prueba._rellenar(plantilla, e)
                res = validar(texto, e)
                if not res.valido:
                    motivo = f"{res.motivo} en {r.error_id}: «{texto}»"
                    break
            if motivo:
                break
        if motivo:
            rechazadas.append((fila["variante"], motivo))
            continue
        nuevas.setdefault((mensaje, sev), []).append(plantilla)

    total = sum(len(v) for v in nuevas.values())
    print(f"nuevas plantillas: {total} en {len(nuevas)} (mensaje, gravedad); "
          f"repetidas: {repetidas}; rechazadas por el validador: {len(rechazadas)}")
    for v, m in rechazadas:
        print(f"  rechazada «{v}»: {m}")
    for (m, s), lista in sorted(nuevas.items()):
        print(f"  {m} · {s}: " + " | ".join(lista))
    if a.escribir:
        texto = ruta.read_text(encoding="utf-8")
        for (m, s), lista in nuevas.items():
            texto = insertar(texto, m, s, lista)
        clave = "variantes_" + a.hoja.stem.split("_")[1]          # variantes_70b, variantes_14b…
        nota = (f'    "{clave}": "2026-11-20: añadidas las variantes aprobadas en '
                f'PRUEBAS/{a.hoja.parent.name}/{a.hoja.name} (scripts/importar_variantes.py)",\n')
        if f'"{clave}"' not in texto:
            texto = texto.replace('    "revision_pendiente"', nota + '    "revision_pendiente"', 1)
        json.loads(texto)                           # sigue siendo JSON válido
        ruta.write_text(texto, encoding="utf-8")
        print(f"escrito: {ruta}")


if __name__ == "__main__":
    main()
