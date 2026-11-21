"""Historial de sesiones y panel «Mi progreso» (ADR-008)."""

import json
from datetime import date, datetime, timedelta

import pytest

from estela.adaptadores.interfaz import contrato
from estela.aplicacion.historial import (RECIENTES, VENTANA_INDICACIONES, Historial,
                                         mejor_racha_dias, progreso, racha_dias,
                                         registro_de_sesion)
from estela.aplicacion.sesion import Sesion
from tests.test_interfaz import ZANCADA, catalogo, rutina, secuencia_zancadas  # noqa: F401
from tests.test_sesion import EstimadorFalso, VozFalsa, correr

HOY = date(2026, 11, 6)          # viernes


def paso(skill_id="jumping_jacks", completadas=10, objetivo=10, indicaciones=None,
         unidad="repeticiones", duracion_s=30.0):
    return {"skill_id": skill_id, "unidad": unidad, "objetivo": objetivo,
            "completadas": completadas, "incompletas": 0, "duracion_s": duracion_s,
            "pausas": 0, "indicaciones": indicaciones or {}}


def registro(fecha, *pasos_, rutina="Rutina"):
    pasos_ = pasos_ or (paso(),)
    return {"v": 1, "fecha": fecha if isinstance(fecha, str) else fecha.isoformat(),
            "rutina": rutina, "terminada": True, "motivo_fin": "completada",
            "duracion_s": round(sum(p["duracion_s"] for p in pasos_), 1),
            "pasos": list(pasos_)}


def ind(eid, veces=1, texto=None):
    return {eid: {"veces": veces, "texto": texto or f"frase {eid}"}}


# -- registro de una sesión ------------------------------------------------------

def test_registro_guarda_solo_metricas_minimas(catalogo, rutina):
    s = Sesion(rutina, catalogo, EstimadorFalso(tronco=10), VozFalsa())
    correr(s, secuencia_zancadas(3))
    r = registro_de_sesion(s.resumen(), datetime(2026, 11, 6, 9, 30, 15, 123), "completada")
    assert r["fecha"] == "2026-11-06T09:30:15" and r["motivo_fin"] == "completada"
    assert r["pasos"][0]["skill_id"] == ZANCADA and r["pasos"][0]["completadas"] == 2
    # lista blanca: nada de ángulos por repetición, latencias, abstenciones ni frames
    assert set(r) == {"v", "fecha", "rutina", "terminada", "motivo_fin", "duracion_s", "pasos"}
    assert set(r["pasos"][0]) == {"skill_id", "unidad", "objetivo", "completadas",
                                  "incompletas", "duracion_s", "pausas", "indicaciones"}
    texto = json.dumps(r)
    for prohibido in ("_min", "_max", "latencia", "p95", "landmarks", "puntos", "coste_dtw"):
        assert prohibido not in texto


def test_sesion_sin_nada_hecho_no_se_registra():
    resumen = {"rutina": "R", "terminada": False, "pasos": [
        {"skill_id": "plancha", "unidad": "segundos", "objetivo": 20, "completadas": 0,
         "incompletas": 0, "duracion_s": 0.4, "pausas_sesion": 0, "mensajes": []}]}
    assert registro_de_sesion(resumen, datetime(2026, 11, 6)) is None
    assert registro_de_sesion({"rutina": "R", "pasos": []}, datetime(2026, 11, 6)) is None


def test_indicaciones_por_error_sin_refuerzos():
    mensajes = [
        {"error_id": "codos_flexionados", "texto": "Estira los codos."},
        {"error_id": "codos_flexionados", "texto": "Estira bien los codos."},
        {"error_id": "codos_flexionados", "texto": "Estira los codos."},
        {"error_id": None, "texto": "Lo estás haciendo bien."},
    ]
    resumen = {"rutina": "R", "terminada": True, "pasos": [
        {"skill_id": "jumping_jacks", "unidad": "repeticiones", "objetivo": 10,
         "completadas": 10, "incompletas": 0, "duracion_s": 20.0, "pausas_sesion": 1,
         "mensajes": mensajes}]}
    r = registro_de_sesion(resumen, datetime(2026, 11, 6))
    assert r["pasos"][0]["indicaciones"] == {
        "codos_flexionados": {"veces": 3, "texto": "Estira los codos."}}
    assert r["pasos"][0]["pausas"] == 1


# -- archivo ---------------------------------------------------------------------

def test_archivo_agrega_lee_y_borra(tmp_path):
    h = Historial(tmp_path / "sub" / "sesiones.jsonl")
    assert h.leer() == []
    h.agregar(registro("2026-11-05T10:00:00"))
    h.agregar(registro("2026-11-04T10:00:00"))
    assert [r["fecha"] for r in h.leer()] == ["2026-11-04T10:00:00", "2026-11-05T10:00:00"]
    h.borrar()
    assert h.leer() == [] and not h.ruta.exists()
    h.borrar()                                   # borrar sin archivo no falla


def test_lineas_corruptas_o_de_otra_version_se_ignoran(tmp_path):
    ruta = tmp_path / "sesiones.jsonl"
    buena = json.dumps(registro("2026-11-05T10:00:00"))
    otra = json.dumps({**registro("2026-11-05T11:00:00"), "v": 99})
    ruta.write_text(f"{buena}\n{{roto\n\n{otra}\n{buena[:20]}", encoding="utf-8")
    assert len(Historial(ruta).leer()) == 1


# -- progreso --------------------------------------------------------------------

@pytest.mark.parametrize("dias, esperado", [
    ([], 0),
    ([HOY], 1),
    ([HOY, HOY - timedelta(days=1), HOY - timedelta(days=2)], 3),
    ([HOY - timedelta(days=1), HOY - timedelta(days=2)], 2),    # hoy aún no: sigue
    ([HOY - timedelta(days=2)], 0),                             # un día entero sin moverse
    ([HOY, HOY - timedelta(days=2)], 1),
])
def test_racha_de_dias(dias, esperado):
    assert racha_dias(dias, HOY) == esperado


def test_progreso_vacio():
    p = progreso([], HOY)
    assert p["total_sesiones"] == 0 and p["racha_dias"] == 0 and p["primera_fecha"] is None
    assert len(p["semanas"]) == 8 and all(s["sesiones"] == 0 for s in p["semanas"])
    assert p["ejercicios"] == [] and p["sesiones"] == []


def test_semanas_van_de_lunes_a_domingo():
    regs = [registro("2026-11-02T08:00:00"),        # lunes de esta semana
            registro("2026-11-01T08:00:00"),        # domingo: semana anterior
            registro("2026-09-01T08:00:00")]        # fuera de las 8 semanas
    regs.sort(key=lambda r: r["fecha"])
    p = progreso(regs, HOY)
    assert p["semanas"][-1] == {"inicio": "2026-11-02", "sesiones": 1, "duracion_s": 30.0}
    assert p["semanas"][-2]["inicio"] == "2026-10-26" and p["semanas"][-2]["sesiones"] == 1
    assert sum(s["sesiones"] for s in p["semanas"]) == 2
    assert p["total_sesiones"] == 3 and p["dias_activos"] == 3
    assert p["dias_activos_7"] == 2                  # 31 oct – 6 nov
    assert p["dias_semana_actual"] == 1              # lunes 2 nov – hoy (el domingo no cuenta)


def test_ejercicios_mejor_marca_objetivo_y_solo_lo_hecho():
    regs = [
        registro("2026-11-01T08:00:00", paso(completadas=6), paso("plancha", 15, 20, unidad="segundos")),
        registro("2026-11-03T08:00:00", paso(completadas=10), paso("plancha", 0, 20, unidad="segundos")),
        registro("2026-11-05T08:00:00", paso(completadas=8)),
    ]
    p = progreso(regs, HOY)
    jj, plancha = p["ejercicios"]                    # el usado más recientemente primero
    assert jj["skill_id"] == "jumping_jacks"
    assert (jj["veces"], jj["mejor"], jj["objetivo_cumplido"]) == (3, 10, 1)
    assert jj["ultimo"] == {"completadas": 8, "objetivo": 10}
    assert [r["completadas"] for r in jj["recientes"]] == [6, 10, 8]
    # la plancha saltada (0 s) no cuenta como una vez hecha
    assert plancha["veces"] == 1 and plancha["unidad"] == "segundos"


def test_indicaciones_frecuentes_por_sesiones_en_la_ventana():
    # la más antigua queda fuera de la ventana de las últimas sesiones
    regs = [registro(f"2026-10-{d:02d}T08:00:00", paso(indicaciones=i)) for d, i in [
        (20, ind("vieja", 9)),
        (21, {**ind("codos", 1), **ind("brazos", 5)}),
        (22, ind("codos", 1)),
        (23, ind("codos", 2)),
        (24, ind("brazos", 1)),
        (25, {}),
    ]]
    assert len(regs) == VENTANA_INDICACIONES + 1
    e = progreso(regs, HOY)["ejercicios"][0]
    assert e["indicaciones"]["sesiones"] == VENTANA_INDICACIONES
    frec = e["indicaciones"]["frecuentes"]
    # «codos» aparece en más sesiones aunque «brazos» se dijo más veces
    assert [(f["error_id"], f["sesiones"], f["veces"]) for f in frec] == [
        ("codos", 3, 4), ("brazos", 2, 6)]
    assert frec[0]["texto"] == "frase codos"


def test_sesiones_recientes_primero_y_limitadas():
    regs = [registro(datetime(2026, 1, 1, 8) + timedelta(days=k),
                     paso(indicaciones=ind("codos", 2)), paso("plancha", 20, 20, unidad="segundos"))
            for k in range(RECIENTES + 5)]
    s = progreso(regs, HOY)["sesiones"]
    assert len(s) == RECIENTES and s[0]["fecha"] == regs[-1]["fecha"]
    assert (s[0]["ejercicios"], s[0]["completos"], s[0]["indicaciones"]) == (2, 2, 2)


@pytest.mark.parametrize("dias, esperado", [
    ([], 0),
    ([HOY], 1),
    ([HOY, HOY],  1),                                                    # dos sesiones el mismo día
    ([date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3), HOY], 3),  # la mejor ya pasó
    ([date(2026, 10, 3), date(2026, 10, 1), date(2026, 10, 2)], 3),      # sin orden
])
def test_mejor_racha(dias, esperado):
    assert mejor_racha_dias(dias) == esperado


def test_promedio_y_dias_salen_de_los_mismos_registros():
    regs = [registro("2026-11-04T08:00:00", paso(duracion_s=60.0)),
            registro("2026-11-04T19:00:00", paso(duracion_s=30.0)),
            registro("2026-11-06T08:00:00", paso(duracion_s=90.0))]
    p = progreso(regs, HOY)
    assert p["promedio_sesion_s"] == 60.0
    assert p["dias"] == [{"fecha": "2026-11-04", "sesiones": 2, "duracion_s": 90.0},
                         {"fecha": "2026-11-06", "sesiones": 1, "duracion_s": 90.0}]
    # coherencia: el calendario, las semanas y el total suman lo mismo
    assert sum(d["duracion_s"] for d in p["dias"]) == p["total_duracion_s"] == sum(
        s["duracion_s"] for s in p["semanas"])
    assert progreso([], HOY)["promedio_sesion_s"] == 0.0 and progreso([], HOY)["dias"] == []


def test_semana_comparada_en_el_mismo_tramo():
    # HOY es viernes 6 nov: lun 2 – vie 6 frente a lun 26 oct – vie 30 oct
    regs = [registro("2026-10-20T08:00:00", paso(duracion_s=10.0)),   # hay historial antes
            registro("2026-10-27T08:00:00", paso(duracion_s=60.0)),   # martes pasado: cuenta
            registro("2026-10-31T08:00:00", paso(duracion_s=500.0)),  # sábado pasado: fuera del tramo
            registro("2026-11-03T08:00:00", paso(duracion_s=90.0))]
    c = progreso(regs, HOY)["semana_comparada"]
    assert c == {"dias": 5, "actual_s": 90.0, "anterior_s": 60.0, "diferencia_s": 30.0}


def test_sin_semana_pasada_completa_no_se_compara():
    # el historial empieza el miércoles pasado: el tramo de la semana pasada está a medias
    regs = [registro("2026-10-28T08:00:00"), registro("2026-11-03T08:00:00")]
    assert progreso(regs, HOY)["semana_comparada"] is None
    assert progreso([], HOY)["semana_comparada"] is None


def test_sesiones_llevan_como_terminaron():
    r = registro("2026-11-05T08:00:00")
    viejo = {k: v for k, v in registro("2026-11-04T08:00:00").items() if k != "motivo_fin"}
    s = progreso([viejo, dict(r, motivo_fin="fuente", terminada=False)], HOY)["sesiones"]
    assert [x["motivo_fin"] for x in s] == ["fuente", None]


def test_progreso_para_la_interfaz_con_nombres(catalogo):
    regs = [registro("2026-11-05T08:00:00", paso(indicaciones=ind("codos")), paso("ya_no_existe"))]
    d = contrato.progreso_a_dict(progreso(regs, HOY), catalogo)
    json.dumps(d)
    # la sesión fue ayer: la racha sigue en 1 hasta que pase un día sin moverse
    assert d["totalSesiones"] == 1 and d["rachaDias"] == 1 and d["diasActivos7"] == 1
    assert d["diasSemanaActual"] == 1 and d["metaSemanal"] is None
    nombres = {e["skillId"]: e["nombre"] for e in d["ejercicios"]}
    assert nombres == {"jumping_jacks": "Jumping jacks", "ya_no_existe": "ya_no_existe"}
    assert d["ejercicios"][0]["indicaciones"]["frecuentes"][0]["errorId"] == "codos"
    assert d["sesiones"][0]["pasos"][0]["nombre"] == "Jumping jacks"
    assert d["sesiones"][0]["motivoFin"] == "completada"
    assert d["mejorRachaDias"] == 1 and d["promedioSesionS"] == 60.0 and d["semanaComparada"] is None
    assert d["dias"] == [{"fecha": "2026-11-05", "sesiones": 1, "duracionS": 60.0}]


# Las pruebas con el orquestador están en test_perfiles.py: el historial es de cada perfil.
