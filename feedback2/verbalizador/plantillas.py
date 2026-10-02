"""Verbalizador A: plantillas parametrizadas.

Condición A de EXP-001 y *fallback* obligatorio de todo el sistema
(ADR-001, §4.3, compromiso 3): si cualquier otro verbalizador falla o excede
el presupuesto de latencia, el sistema habla igualmente con esto.

Propiedades que lo hacen el suelo del sistema:

  - No puede afirmar nada fuera del contrato: el texto se compone a partir del
    `ErrorTipificado` y de nada más.
  - Es determinista: misma entrada -> mismo texto.
  - Latencia despreciable, medible y sin varianza relevante.
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional

from ..contrato import ErrorTipificado, Lado, MensajeFeedback
from .base import Verbalizador
from .validador import ResultadoValidacion, validar

#: Forma de superficie y género gramatical de cada segmento.
#: El género es necesario para concordar el adjetivo de lado en español:
#: «rodilla izquierda» pero «codo izquierdo».
SEGMENTO_ES: Dict[str, Dict[str, str]] = {
    "rodilla":  {"sg": "rodilla",  "pl": "rodillas",  "genero": "f"},
    "cadera":   {"sg": "cadera",   "pl": "caderas",   "genero": "f"},
    "tronco":   {"sg": "tronco",   "pl": "tronco",    "genero": "m"},
    "hombro":   {"sg": "hombro",   "pl": "hombros",   "genero": "m"},
    "codo":     {"sg": "codo",     "pl": "codos",     "genero": "m"},
    "muneca":   {"sg": "muñeca",   "pl": "muñecas",   "genero": "f"},
    "tobillo":  {"sg": "tobillo",  "pl": "tobillos",  "genero": "m"},
    "pie":      {"sg": "pie",      "pl": "pies",      "genero": "m"},
    "cuello":   {"sg": "cuello",   "pl": "cuello",    "genero": "m"},
    "cabeza":   {"sg": "cabeza",   "pl": "cabeza",    "genero": "f"},
    "brazo":    {"sg": "brazo",    "pl": "brazos",    "genero": "m"},
    "pierna":   {"sg": "pierna",   "pl": "piernas",   "genero": "f"},
    "espalda":  {"sg": "espalda",  "pl": "espalda",   "genero": "f"},
}

LADO_ES: Dict[Lado, Dict[str, str]] = {
    Lado.IZQUIERDO: {"m": "izquierdo", "f": "izquierda"},
    Lado.DERECHO:   {"m": "derecho",   "f": "derecha"},
}


def ruta_plantillas_por_defecto() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "plantillas_es.json")


class VerbalizadorPlantillas(Verbalizador):
    nombre = "A_plantillas"

    def __init__(self, ruta: Optional[str] = None, validar_salida: bool = True):
        self.ruta = ruta or ruta_plantillas_por_defecto()
        with open(self.ruta, "r", encoding="utf-8") as f:
            self.plantillas: Dict[str, Dict[str, List[str]]] = json.load(f)
        self.plantillas.pop("_meta", None)
        self.validar_salida = validar_salida

    # -- composición --------------------------------------------------------

    def _variantes(self, error: ErrorTipificado) -> List[str]:
        clave = error.mensaje_id or error.error_id
        bloque = self.plantillas.get(clave)
        if bloque is None:
            bloque = self.plantillas["_generico"]
        variantes = bloque.get(error.severidad.value)
        if not variantes:
            # Degradación ordenada: si falta la severidad pedida, se usa la
            # más suave disponible. Nunca se sube de tono por defecto.
            for sev in ("leve", "moderada", "alta"):
                if bloque.get(sev):
                    variantes = bloque[sev]
                    break
        return list(variantes or self.plantillas["_generico"]["leve"])

    def _rellenar(self, plantilla: str, error: ErrorTipificado) -> str:
        info = SEGMENTO_ES.get(error.segmento)
        if info is None:
            raise KeyError(f"segmento sin forma en español: {error.segmento}")
        lado_txt = ""
        if error.lado in LADO_ES:
            lado_txt = LADO_ES[error.lado][info["genero"]]
        fem = info["genero"] == "f"
        texto = (plantilla
                 .replace("{segmento_pl}", info["pl"])
                 .replace("{segmento}", info["sg"])
                 .replace("{art_pl}", "las" if fem else "los")
                 .replace("{de_art}", "de la" if fem else "del")
                 .replace("{art}", "la" if fem else "el")
                 .replace("{lado}", lado_txt))
        return " ".join(texto.split())

    # -- API ----------------------------------------------------------------

    def verbalizar(self, error: ErrorTipificado) -> MensajeFeedback:
        t0 = time.perf_counter()
        variantes = self._variantes(error)
        # Selección determinista: la misma entrada produce siempre el mismo
        # texto, y el texto rota entre repeticiones para no sonar a grabación.
        idx = (error.repeticion or 0) % len(variantes)
        texto = self._rellenar(variantes[idx], error)

        motivo = ""
        if self.validar_salida:
            res: ResultadoValidacion = validar(texto, error)
            if not res.valido:
                # Una plantilla que no valida es un defecto del archivo de
                # plantillas, no una situación de ejecución. Se degrada al
                # mensaje genérico y se deja constancia para que un test lo
                # detecte.
                motivo = res.motivo
                texto = self._rellenar(
                    self.plantillas["_generico"][error.severidad.value][0], error)

        dt = (time.perf_counter() - t0) * 1000.0
        return MensajeFeedback(
            texto=texto,
            error=error,
            verbalizador=self.nombre,
            latencia_ms=dt,
            fallback=bool(motivo),
            motivo_rechazo=motivo,
        )


__all__ = ["VerbalizadorPlantillas", "SEGMENTO_ES", "LADO_ES"]
