"""Los scripts de voz: el analizador de la tanda y la medición de «Estela» (sin correrla)."""

import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


def _modulo(nombre):
    spec = importlib.util.spec_from_file_location(nombre, RAIZ / "scripts" / "voz" / f"{nombre}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


an = _modulo("analizar_tanda_voz")


def test_alucinaciones_texto_repetido_o_larguisimo():
    assert an.es_alucinacion("Sí, " + "no, " * 30)
    assert an.es_alucinacion("¿Qué? ¿Qué? ¿Qué? ¿Qué?")
    assert an.es_alucinacion(" ".join(f"palabra{i}" for i in range(30)))
    assert not an.es_alucinacion("Estela, pausa por favor")
    assert not an.es_alucinacion("No, no sé qué decirte")


def test_grafias_solo_si_van_con_una_orden_o_solas():
    textos = ["Estelaa, pausa", "Estelaa siguiente", "esta casa es bonita", "Estelaa"]
    g = an.grafias_de_estela(textos)
    assert g == ["estelaa (3)"]
    # ya aceptadas como llamada («Stella», «Estila»): no se proponen
    assert an.grafias_de_estela(["Stella, pausa", "Estila, siguiente"]) == []


def test_analiza_un_registro_mezclado():
    filas = [
        {"texto": "Estela, pausa", "reconocer_ms": 90, "volumen_rms": 0.05},
        {"texto": "Oye Estela, ángulos activados", "reconocer_ms": 100, "volumen_rms": 0.05},
        {"texto": "Estela.", "reconocer_ms": 80, "volumen_rms": 0.002},
        {"texto": "Estela, qué calor", "reconocer_ms": 95},
        {"texto": "Estela, me duele la rodilla", "reconocer_ms": 95},
        {"texto": "Hola buenos días", "reconocer_ms": 70},
        {"texto": "Sí, " + "no, " * 30, "reconocer_ms": 700},
        {"texto": None, "ignorada": True, "palabras": 5, "reconocer_ms": 60},
    ]
    r = an.analizar(filas)
    assert r["con_estela"] == 5 and r["estela_sola"] == 1
    assert r["ordenes"] == {"pausa": 1, "angulos_si": 1}
    assert r["sin_orden_clara"] == ["que calor"] and r["dolor"] == 1
    assert r["sin_estela"] == 3 and r["ignoradas_sin_texto"] == 1
    assert len(r["alucinaciones"]) == 1 and r["volumen_bajo"] == 1
    assert r["ms_p95"] >= r["ms_p50"]
    assert "«que calor»" in an.informe(r)


def test_lee_el_jsonl_y_los_tres_formatos_del_log(tmp_path):
    j = tmp_path / "m.jsonl"
    j.write_text(json.dumps({"texto": "Estela, siguiente", "reconocer_ms": 80}) + "\n\n", encoding="utf-8")
    assert an.cargar_jsonl(j)[0]["texto"] == "Estela, siguiente"
    log = tmp_path / "s.log"
    log.write_text(
        "INFO x.escucha: Voz: «Estela, pausa» → pausa (entendido, 75 ms)\n"
        "Voz oída: «Estela, pausa» → pausa (75 ms)\n"                      # repetida del resumen
        "Voz oída: «Estela, anterior» → anterior (90 ms)\n"
        "Voz ignorada (sin «Estela»): 7 palabras (61 ms)\n"
        "otra línea cualquiera\n", encoding="utf-8")
    filas = an.cargar_log(log)
    assert [f.get("texto") for f in filas] == ["Estela, pausa", "Estela, anterior", None]
    assert filas[2]["palabras"] == 7


def test_el_script_de_medicion_se_importa_en_cualquier_equipo_y_trae_las_pistas():
    m = _modulo("medir_llamada")
    p = m.pistas()
    assert set(p) == {"actual", "llamada", "estela_repetida", "sin_pista"}
    assert p["sin_pista"] is None and p["llamada"].lower().count("estela") == 1
    assert p["estela_repetida"].lower().count("estela") > 1
