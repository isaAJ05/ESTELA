"""Perfiles locales con un historial cada uno (ADR-009)."""

import json
from datetime import datetime

import pytest

from estela.adaptadores.interfaz import contrato
from estela.adaptadores.interfaz.ventana import Api
from estela.aplicacion.perfiles import MAX_PERFILES, PerfilInvalido, Perfiles, rutina_de
from tests.test_historial import registro
from tests.test_interfaz import (RESUMEN, ZANCADA, catalogo, esperar_fase,  # noqa: F401
                                 nuevo_orquestador, rutina, secuencia_zancadas)


@pytest.fixture
def perfiles(tmp_path):
    return Perfiles(tmp_path / "historial")


# -- archivo de perfiles -----------------------------------------------------------

def test_crear_listar_editar(perfiles):
    assert perfiles.listar() == []
    ana = perfiles.crear({"nombre": "  Ana   María ", "color": "rosa", "meta_semanal": 3},
                         ahora=datetime(2026, 11, 6, 9, 0, 0, 5))
    assert ana["nombre"] == "Ana María" and ana["creado"] == "2026-11-06T09:00:00"
    assert ana["id"].startswith("p") and ana["id"].isalnum()
    luis = perfiles.crear({"nombre": "Luis"})
    assert luis["color"] == "violeta" and luis["meta_semanal"] is None
    assert [p["nombre"] for p in perfiles.listar()] == ["Ana María", "Luis"]
    # editar solo el color conserva la meta; quitar la meta con None
    assert perfiles.editar(ana["id"], {"color": "azul"})["meta_semanal"] == 3
    assert perfiles.editar(ana["id"], {"meta_semanal": None})["meta_semanal"] is None
    assert perfiles.editar(ana["id"], {"nombre": "ana maría"})["nombre"] == "ana maría"   # el mismo


@pytest.mark.parametrize("datos, mensaje", [
    ({"nombre": "   "}, "nombre"),
    ({"nombre": "x" * 31}, "30 caracteres"),
    ({"nombre": "LUIS"}, "Ya hay un perfil"),
    ({"nombre": "Eva", "color": "#ff0000"}, "colores"),
    ({"nombre": "Eva", "meta_semanal": 0}, "entre 1 y 7"),
    ({"nombre": "Eva", "meta_semanal": 8}, "entre 1 y 7"),
    ({"nombre": "Eva", "meta_semanal": True}, "entre 1 y 7"),
    ({"nombre": "Eva", "meta_semanal": "3"}, "entre 1 y 7"),
])
def test_datos_invalidos(perfiles, datos, mensaje):
    perfiles.crear({"nombre": "Luis"})
    with pytest.raises(PerfilInvalido, match=mensaje):
        perfiles.crear(datos)
    assert len(perfiles.listar()) == 1


def test_limite_de_perfiles(perfiles):
    for k in range(MAX_PERFILES):
        perfiles.crear({"nombre": f"P{k}"})
    with pytest.raises(PerfilInvalido, match="borra uno"):
        perfiles.crear({"nombre": "Otra"})


def test_borrar_perfil_borra_su_historial_y_no_el_de_otros(perfiles):
    ana, luis = perfiles.crear({"nombre": "Ana"}), perfiles.crear({"nombre": "Luis"})
    perfiles.historial_de(ana["id"]).agregar(registro("2026-11-05T08:00:00"))
    perfiles.historial_de(luis["id"]).agregar(registro("2026-11-05T09:00:00"))
    assert perfiles.borrar(ana["id"]) is True
    assert not perfiles.historial_de(ana["id"]).ruta.exists()
    assert len(perfiles.historial_de(luis["id"]).leer()) == 1
    assert [p["nombre"] for p in perfiles.listar()] == ["Luis"]
    assert perfiles.borrar(ana["id"]) is False


def test_archivo_ilegible_o_entradas_malas_se_ignoran(perfiles):
    perfiles.directorio.mkdir(parents=True)
    ruta = perfiles.directorio / "perfiles.json"
    ruta.write_text("{roto", encoding="utf-8")
    assert perfiles.listar() == []
    ruta.write_text(json.dumps({"v": 1, "perfiles": [
        {"id": "pabc", "nombre": "Ana", "color": "rosa"}, {"id": 3}, "x",
        {"id": "pdef", "nombre": "Luis", "color": "dorado"}]}), encoding="utf-8")
    assert [p["id"] for p in perfiles.listar()] == ["pabc"]


def test_el_id_no_puede_salirse_del_directorio(perfiles):
    with pytest.raises(PerfilInvalido):
        perfiles.historial_de("../perfiles")


def test_el_primer_perfil_hereda_el_historial_de_una_sola_usuaria(perfiles):
    """Antes de los perfiles (ADR-008) había un solo `sesiones.jsonl`."""
    perfiles.directorio.mkdir(parents=True)
    (perfiles.directorio / "sesiones.jsonl").write_text(
        json.dumps(registro("2026-11-05T08:00:00")) + "\n", encoding="utf-8")
    ana = perfiles.crear({"nombre": "Ana"})
    luis = perfiles.crear({"nombre": "Luis"})
    assert len(perfiles.historial_de(ana["id"]).leer()) == 1
    assert perfiles.historial_de(luis["id"]).leer() == []
    assert not (perfiles.directorio / "sesiones.jsonl").exists()


# -- contrato ------------------------------------------------------------------------

def test_contrato_de_perfiles():
    p = {"id": "pabc", "nombre": "Ana", "color": "rosa", "meta_semanal": 3, "creado": "2026-11-06T09:00:00"}
    d = contrato.perfiles_a_dict([p], "pabc", True)
    json.dumps(d)
    assert d["perfiles"][0] == {"id": "pabc", "nombre": "Ana", "color": "rosa", "rutina": None,
                                "metaSemanal": 3, "creado": "2026-11-06T09:00:00"}
    assert d["activo"] == "pabc" and d["elegido"] is True and d["maxPerfiles"] == MAX_PERFILES
    assert "rosa" in d["colores"] and d["meta"] == [1, 7]
    # solo pasan las claves que llegan, y nada más
    assert contrato.datos_de_perfil({"metaSemanal": None, "otra": 1}) == {"meta_semanal": None}
    assert contrato.datos_de_perfil(None) == {}


# -- orquestador ---------------------------------------------------------------------

def test_sin_elegir_perfil_no_hay_panel_ni_se_guarda(perfiles, catalogo, rutina):
    orq, _, _ = nuevo_orquestador(catalogo, rutina, secuencia_zancadas(2), perfiles=perfiles)
    caps = orq.info()["capacidades"]
    assert caps["perfiles"] is True and caps["historial"] is True
    assert orq.perfiles()["elegido"] is False          # la interfaz pregunta quién entrena
    orq.iniciar()
    assert esperar_fase(orq, RESUMEN)["resumen"]["guardadaEnHistorial"] is None
    assert orq.historial() is None


def test_invitada_no_guarda_nada(perfiles, catalogo, rutina):
    perfiles.crear({"nombre": "Ana"})
    orq, _, _ = nuevo_orquestador(catalogo, rutina, secuencia_zancadas(2), perfiles=perfiles)
    assert orq.elegir_perfil(None) is True
    assert orq.perfiles()["elegido"] is True and orq.perfiles()["activo"] is None
    orq.iniciar()
    assert esperar_fase(orq, RESUMEN)["resumen"]["guardadaEnHistorial"] is None
    assert not list(perfiles.directorio.glob("*.jsonl"))


def test_cada_perfil_tiene_su_historial_y_su_meta(perfiles, catalogo, rutina):
    orq, _, _ = nuevo_orquestador(catalogo, rutina, secuencia_zancadas(2), perfiles=perfiles)
    r = orq.crear_perfil({"nombre": "Ana", "color": "rosa", "metaSemanal": 3})
    assert r["ok"] and orq.perfiles()["activo"] == r["perfil"]["id"]     # queda elegido
    orq.iniciar()
    assert esperar_fase(orq, RESUMEN)["resumen"]["guardadaEnHistorial"] is True
    panel = orq.historial()
    json.dumps(panel)
    assert panel["totalSesiones"] == 1 and panel["metaSemanal"] == 3
    assert panel["ejercicios"][0]["skillId"] == ZANCADA and panel["diasSemanaActual"] == 1

    luis = orq.crear_perfil({"nombre": "Luis"})["perfil"]
    assert orq.historial()["totalSesiones"] == 0 and orq.historial()["metaSemanal"] is None
    assert orq.elegir_perfil(r["perfil"]["id"]) and orq.historial()["totalSesiones"] == 1
    # borrar el historial deja el perfil
    assert orq.borrar_historial() is True and orq.historial()["totalSesiones"] == 0
    assert len(orq.perfiles()["perfiles"]) == 2
    assert orq.elegir_perfil("pnoexiste") is False and orq.perfiles()["activo"] == r["perfil"]["id"]
    assert orq.editar_perfil(luis["id"], {"nombre": "Ana"}) == {
        "ok": False, "error": "Ya hay un perfil con ese nombre."}


def test_la_sesion_se_guarda_en_el_perfil_con_el_que_empezo(perfiles, catalogo, rutina):
    ana, luis = perfiles.crear({"nombre": "Ana"}), perfiles.crear({"nombre": "Luis"})
    orq, _, _ = nuevo_orquestador(catalogo, rutina, secuencia_zancadas(50), bloquear=True,
                                  perfiles=perfiles)
    orq.elegir_perfil(ana["id"])
    orq.iniciar()
    e = esperar_fase(orq, "sesion")
    while not (e["sesion"] and e["sesion"]["completadas"] > 0):    # algo que guardar
        e = orq.estado(e["version"], 1.0) or e
    orq.elegir_perfil(luis["id"])                      # alguien cambia de perfil a mitad
    orq.terminar()
    assert esperar_fase(orq, RESUMEN)["resumen"]["guardadaEnHistorial"] is True
    assert len(perfiles.historial_de(ana["id"]).leer()) == 1
    assert perfiles.historial_de(luis["id"]).leer() == []
    orq.cerrar()


def test_borrar_el_perfil_activo_vuelve_a_preguntar(perfiles, catalogo, rutina):
    orq, _, _ = nuevo_orquestador(catalogo, rutina, [], perfiles=perfiles)
    pid = orq.crear_perfil({"nombre": "Ana"})["perfil"]["id"]
    assert orq.borrar_perfil(pid) is True
    estado = orq.perfiles()
    assert estado["perfiles"] == [] and estado["activo"] is None and estado["elegido"] is False
    assert orq.borrar_perfil(pid) is False and orq.historial() is None


def test_sesion_sin_nada_hecho_no_entra_en_el_historial(perfiles, catalogo, rutina):
    orq, _, _ = nuevo_orquestador(catalogo, rutina, [170.0] * 5, perfiles=perfiles)
    pid = orq.crear_perfil({"nombre": "Ana"})["perfil"]["id"]
    orq.iniciar()
    assert esperar_fase(orq, RESUMEN)["resumen"]["guardadaEnHistorial"] is False
    assert perfiles.historial_de(pid).leer() == []


def test_sin_perfiles_no_hay_panel_ni_se_guarda(catalogo, rutina):
    orq, _, _ = nuevo_orquestador(catalogo, rutina, secuencia_zancadas(2))
    caps = orq.info()["capacidades"]
    assert caps["historial"] is False and caps["perfiles"] is False
    orq.iniciar()
    assert esperar_fase(orq, RESUMEN)["resumen"]["guardadaEnHistorial"] is None
    assert orq.historial() is None and orq.borrar_historial() is False
    assert orq.perfiles() is None and orq.crear_perfil({"nombre": "Ana"})["ok"] is False


def test_error_al_escribir_no_impide_el_resumen(perfiles, catalogo, rutina, monkeypatch):
    orq, _, resumenes = nuevo_orquestador(catalogo, rutina, secuencia_zancadas(2), perfiles=perfiles)
    orq.crear_perfil({"nombre": "Ana"})

    def falla(self, registro):
        raise PermissionError("solo lectura")
    monkeypatch.setattr("estela.aplicacion.historial.Historial.agregar", falla)
    orq.iniciar()
    fin = esperar_fase(orq, RESUMEN)
    assert fin["resumen"]["guardadaEnHistorial"] is False and len(resumenes) == 1


def test_api_de_la_ventana_valida_lo_que_llega_de_javascript(perfiles, catalogo, rutina):
    orq, _, _ = nuevo_orquestador(catalogo, rutina, [], perfiles=perfiles)
    api = Api(orq)
    assert api.crear_perfil("no es un dict")["ok"] is False          # sin nombre
    pid = api.crear_perfil({"nombre": "Ana", "metaSemanal": 2})["perfil"]["id"]
    assert api.elegir_perfil(123) is True and api.perfiles()["activo"] is None   # invitada
    assert api.editar_perfil(pid, {"color": "azul"})["perfil"]["color"] == "azul"
    assert api.borrar_perfil(pid) is True


# -- rutina de cada perfil ------------------------------------------------------------

def test_la_rutina_se_guarda_en_el_perfil_y_editar_no_la_borra(perfiles):
    ana, luis = perfiles.crear({"nombre": "Ana"}), perfiles.crear({"nombre": "Luis"})
    assert rutina_de(ana) is None                       # aún no armó ninguna
    perfiles.guardar_rutina(ana["id"], [{"skill_id": "plancha", "objetivo": 30},
                                        {"skill_id": "jumping_jacks", "objetivo": 12}])
    perfiles.editar(ana["id"], {"color": "azul"})
    assert rutina_de(perfiles.obtener(ana["id"])) == [
        {"skill_id": "plancha", "objetivo": 30}, {"skill_id": "jumping_jacks", "objetivo": 12}]
    assert rutina_de(perfiles.obtener(luis["id"])) is None
    perfiles.guardar_rutina(ana["id"], [])
    assert rutina_de(perfiles.obtener(ana["id"])) == []


@pytest.mark.parametrize("pasos", [
    [{"skill_id": "plancha", "objetivo": "30"}],
    [{"skill_id": 3, "objetivo": 30}],
    [{"skill_id": "plancha", "objetivo": True}],
    ["plancha"],
    [{"skill_id": "plancha", "objetivo": 30}] * 21,
])
def test_rutina_mal_formada_no_se_guarda(perfiles, pasos):
    ana = perfiles.crear({"nombre": "Ana"})
    with pytest.raises(PerfilInvalido):
        perfiles.guardar_rutina(ana["id"], pasos)
    assert rutina_de(perfiles.obtener(ana["id"])) is None


def test_rutina_en_el_archivo_con_entradas_malas_se_limpia_al_leer():
    p = {"id": "pa", "nombre": "Ana", "color": "rosa", "rutina": [
        {"skill_id": "plancha", "objetivo": 30}, {"skill_id": "x"}, "basura", {"skill_id": "jj", "objetivo": 1.5}]}
    assert rutina_de(p) == [{"skill_id": "plancha", "objetivo": 30}]
    assert rutina_de({**p, "rutina": "no es lista"}) is None


def test_orquestador_valida_y_guarda_la_rutina_del_perfil(perfiles, catalogo, rutina):
    orq, _, _ = nuevo_orquestador(catalogo, rutina, [], perfiles=perfiles)
    ana = orq.crear_perfil({"nombre": "Ana"})["perfil"]
    luis = orq.crear_perfil({"nombre": "Luis"})["perfil"]
    assert ana["rutina"] is None
    r = orq.guardar_rutina(ana["id"], [{"skillId": "plancha", "objetivo": 45},
                                       {"skillId": "zancada_atras_izq", "objetivo": 12}])
    assert r["ok"] and r["perfil"]["rutina"] == [{"skillId": "plancha", "objetivo": 45},
                                                 {"skillId": "zancada_atras_izq", "objetivo": 12}]
    # se guarda en el perfil indicado aunque el activo sea otro (guardado tardío)
    assert orq.perfiles()["activo"] == luis["id"]
    por_id = {p["id"]: p for p in orq.perfiles()["perfiles"]}
    assert por_id[ana["id"]]["rutina"][0] == {"skillId": "plancha", "objetivo": 45}
    assert por_id[luis["id"]]["rutina"] is None
    # mismas reglas que al iniciar una sesión
    assert orq.guardar_rutina(ana["id"], [{"skillId": "no_existe", "objetivo": 5}])["ok"] is False
    assert orq.guardar_rutina(ana["id"], [{"skillId": "plancha", "objetivo": 999}])["ok"] is False
    assert orq.guardar_rutina(ana["id"], [{"skillId": "plancha", "objetivo": "x"}])["ok"] is False
    assert orq.guardar_rutina(ana["id"], ["plancha"])["ok"] is False
    assert orq.guardar_rutina(ana["id"], "nada")["ok"] is False
    assert orq.guardar_rutina("pnoexiste", [])["ok"] is False
    # vaciarla sí vale
    assert orq.guardar_rutina(ana["id"], [])["perfil"]["rutina"] == []


def test_api_guarda_la_rutina(perfiles, catalogo, rutina):
    orq, _, _ = nuevo_orquestador(catalogo, rutina, [], perfiles=perfiles)
    api = Api(orq)
    pid = api.crear_perfil({"nombre": "Ana"})["perfil"]["id"]
    assert api.guardar_rutina(pid, [{"skillId": "plancha", "objetivo": 20}])["ok"] is True
    assert api.perfiles()["perfiles"][0]["rutina"] == [{"skillId": "plancha", "objetivo": 20}]
    assert api.guardar_rutina(pid)["ok"] is False                       # sin pasos: no es una lista
