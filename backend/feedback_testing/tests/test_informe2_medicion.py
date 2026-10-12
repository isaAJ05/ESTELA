"""Medición del Informe 2 sobre los vídeos disponibles (marcador `metricas`).

No corre con `pytest` a secas (`addopts = -m 'not metricas'` en pyproject).
Para medir e imprimir las tablas:

    pytest -m metricas -s

Escribe `feedback_testing/resultados/INFORME2-metricas.{md,json}`. Cada test
comprueba una sección; si falta un prerrequisito (cv2, modelo, vídeo,
anotación, LLM, voz) se salta con el motivo exacto, que es el mismo que el
informe muestra como «pendiente de medición».

Variables de entorno opcionales:
    ESTELA_INFORME2_RAPIDO=1        un vídeo por ejercicio, 8 s
    ESTELA_INFORME2_RAICES=a:b      carpetas de vídeos (separadas por os.pathsep)
    ESTELA_INFORME2_MAX_S=20        recorta cada vídeo de la corrida principal
    ESTELA_INFORME2_ANOTACIONES=d   carpeta o archivo de anotaciones
    ESTELA_INFORME2_SALIDA=dir      dónde escribir el informe
    ESTELA_INFORME2_VOZ=auto        auto | texto | piper-sin-audio | piper
    ESTELA_MODELOS=dir              modelos de pose y voces fuera de backend/modelos
"""

import math
import os
from pathlib import Path

import pytest

from feedback_testing import informe2
from feedback_testing import metricas_informe as mi

pytestmark = pytest.mark.metricas


def _opciones() -> informe2.Opciones:
    env = os.environ.get
    op = informe2.Opciones(rapido=env("ESTELA_INFORME2_RAPIDO") == "1",
                           voz=env("ESTELA_INFORME2_VOZ", "auto"))
    if env("ESTELA_INFORME2_RAICES"):
        op.raices = tuple(Path(r) for r in env("ESTELA_INFORME2_RAICES").split(os.pathsep) if r)
    if env("ESTELA_INFORME2_MAX_S"):
        op.max_s = float(env("ESTELA_INFORME2_MAX_S"))
    if env("ESTELA_INFORME2_ANOTACIONES"):
        op.anotaciones = (Path(env("ESTELA_INFORME2_ANOTACIONES")),)
    if env("ESTELA_INFORME2_SALIDA"):
        d = Path(env("ESTELA_INFORME2_SALIDA"))
        op.salida_md, op.salida_json = d / informe2.SALIDA_MD.name, d / informe2.SALIDA_JSON.name
    return op


@pytest.fixture(scope="module")
def R():
    op = _opciones()
    res = informe2.ejecutar(op)
    md = informe2.escribir(res, op.salida_md, op.salida_json)
    print("\n" + md)
    print(f"\ninforme: {op.salida_md}\ndatos:   {op.salida_json}")
    res["_salida_md"] = op.salida_md
    return res


def _salta_si(R, *claves):
    for k in claves:
        if k in R["pendientes"]:
            pytest.skip(R["pendientes"][k])


def test_informe_escrito_con_todos_los_objetivos(R):
    md = Path(R["_salida_md"]).read_text(encoding="utf-8")
    for clave, obj in mi.OBJETIVOS_INFORME2.items():
        assert obj["descripcion"] in md
    assert "Cifras preliminares" in md and R["equipo"]["cpu"] in md


def test_pose_latencia_fps_y_retraso(R):
    _salta_si(R, "pose")
    corridas = R["corridas"]
    assert corridas, "no hubo ninguna corrida de vídeo"
    lat = informe2.latencias_por_etapa(corridas)
    assert lat["pose"]["n"] > 0 and lat["pose"]["p95"] > 0
    for c in corridas:
        r = c.rendimiento()
        assert 0 < r["procesados"] <= r["frames_fuente"]
        if c.politica == "cola":
            assert r["descartados"] == 0


def test_silencios_por_causa(R):
    _salta_si(R, "pose")
    s = mi.tasas_silencio([e for c in R["corridas"] for e in c.registro])
    assert s["frames"] == sum(len(c.t_ms) for c in R["corridas"])
    assert s["evaluados"] == (sum(s["motivos"].values()) + s["correcciones"] + s["refuerzos"])


def test_deteccion_a_voz(R):
    _salta_si(R, "pose")
    dv = [d for c in R["corridas"] for d in c.deteccion_a_voz() if "total_s" in d]
    if not dv:
        pytest.skip("pendiente de medición: ningún mensaje llegó a sonar en los vídeos")
    assert all(d["total_s"] >= 0 for d in dv)


def test_variantes_de_mediapipe(R):
    _salta_si(R, "pose")
    if not R.get("modelos"):
        pytest.skip("pendiente de medición: comparación de modelos desactivada o sin vídeos")
    for m in informe2.MODELOS_POSE:
        _salta_si(R, f"modelo_{m}")
        assert R["modelos"][m], m


def test_jitter_en_la_plancha(R):
    _salta_si(R, "pose", "jitter")
    if not R.get("modelos"):
        pytest.skip("pendiente de medición: comparación de modelos desactivada")
    planchas = [c for c in R["modelos"]["full"] if c.ejercicio_id == "plancha"]
    j = informe2.jitter_plancha(planchas[0], ("tronco_inclinacion",))
    if j["tronco_inclinacion"] is None:
        pytest.skip("pendiente de medición: la plancha no llegó a la fase de mantenimiento")
    assert j["tronco_inclinacion"] >= 0


def test_dtw_clasico_frente_a_banda(R):
    _salta_si(R, "pose")
    dtw = {k: v for k, v in R.get("dtw", {}).items() if not k.startswith("_")}
    con_ref = {k: v for k, v in dtw.items() if v["disponible"]}
    if not con_ref:
        pytest.skip("pendiente de medición: ningún vídeo de un ejercicio con referencia DTW")
    for ej, d in con_ref.items():
        clasico = d["variantes"]["clásico"]
        for nombre, v in d["variantes"].items():
            # la banda nunca calcula más celdas que el clásico
            if nombre != "clásico" and v["latencia"]["n"]:
                assert v["latencia"]["media"] <= clasico["latencia"]["media"] * 1.5, (ej, nombre)


def test_exp001_plantilla(R):
    if "exp001" not in R:
        pytest.skip("EXP-001 desactivado")
    a = R["exp001"]["A"]
    assert a["M2"][0] == 0.0          # plantillas: 0 % por construcción


def test_exp001_llm_local(R):
    _salta_si(R, "exp001_F")
    f = R["exp001"]["F"]
    assert not math.isnan(f["M2"][0])


def test_piper_rtf(R):
    _salta_si(R, "piper_rtf")
    if "piper" not in R:
        pytest.skip("RTF de Piper desactivado")
    assert R["piper"]["rtf"]["n"] > 0


def test_precision_recobrado_frente_a_anotacion(R):
    _salta_si(R, "pose", "anotaciones")
    an = R["anotaciones"]
    if an["sin_video"] and not an["detalle"]:
        pytest.skip("pendiente de medición: " + "; ".join(an["sin_video"]))
    assert an["total_por_ejercicio"]


def test_kappa_entre_anotadoras(R):
    _salta_si(R, "pose", "anotaciones", "kappa")
    assert R["anotaciones"]["kappa"]
