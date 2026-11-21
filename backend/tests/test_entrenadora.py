"""Entrenadora: lista cerrada de acciones, validación de lo que redacta el
modelo, respaldo sin modelo y respuesta fija por dolor. Sin red ni modelo:
el generador es una función de prueba."""

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from estela.adaptadores.llm.entrenadora_ollama import GeneradorOllama
from estela.aplicacion import entrenadora as en
from estela.aplicacion.historial import progreso, registro_de_sesion

NOMBRES = {"zancada_atras_izq": "Zancada atrás estática, pierna izquierda atrás",
           "plancha": "Plancha"}


def paso(completadas=6, objetivo=6, avisos=2, skill="zancada_atras_izq", unidad="repeticiones"):
    return {"skill_id": skill, "objetivo": objetivo, "unidad": unidad,
            "completadas": completadas, "incompletas": 1, "duracion_s": 60.0,
            "pausas_sesion": 0,
            "mensajes": [{"error_id": "paso_corto", "texto": "Alarga un poco el paso.",
                          "t_ms": 1000 * i, "repeticion": i} for i in range(avisos)]
                        + [{"error_id": None, "texto": "Vas bien."}]}


def generador(resumen="Completaste las 6 repeticiones y recibiste 2 avisos.", accion="seguir"):
    pedidos = []

    def g(sistema, datos, permitidas):
        pedidos.append((sistema, datos, tuple(permitidas)))
        return {"resumen": resumen, "accion": accion}
    g.pedidos = pedidos
    return g


def test_respuesta_del_modelo_valida_lleva_la_frase_fija_de_la_accion():
    g = generador()
    r = en.Entrenadora(g, NOMBRES).entre_ejercicios(paso(), "plancha")
    assert (r.origen, r.accion, r.motivo_caida) == (en.ORIGEN_LLM, en.SEGUIR, "")
    assert r.texto == ("Completaste las 6 repeticiones y recibiste 2 avisos. "
                       + en.FRASE_ACCION[en.SEGUIR])
    assert r.nota == ""                           # no se usó el historial


def test_el_modelo_solo_recibe_cifras_derivadas():
    g = generador()
    en.Entrenadora(g, NOMBRES).entre_ejercicios(paso(), "plancha")
    _, datos, permitidas = g.pedidos[0]
    assert permitidas == en.PERMITIDAS[en.ENTRE]
    assert "hechas: 6 repeticiones" in datos and "objetivo: 6 repeticiones" in datos
    assert "aviso dado 2 veces: «Alarga un poco el paso.»" in datos
    assert "ejercicio siguiente: Plancha" in datos
    # nada que permita reconstruir el movimiento ni juzgar la técnica
    for vetado in ("t_ms", "angulo", "keypoint", "correctas", "con_error", "latencia"):
        assert vetado not in datos


@pytest.mark.parametrize("resumen, motivo", [
    ("", "resumen_vacio"),
    ("palabra " * (en.MAX_PALABRAS_RESUMEN + 1), "demasiado_largo"),
    ("Hiciste 9 repeticiones.", "cifra_inventada"),
    ("Recibiste tres avisos en las 6 repeticiones.", "cifra_inventada"),
    ("Cuida la rodilla en las 6 repeticiones.", "segmento_ajeno"),
    ("Hiciste 6 repeticiones con la pierna derecha.", "lado_ajeno"),
    ("Tu técnica fue perfecta en las 6 repeticiones.", "califica_la_tecnica"),
    ("Has mejorado mucho tu técnica.", "califica_la_tecnica"),
    ("Hiciste 6 repeticiones, puede haber una lesión.", "vocabulario_medico"),
    ("Hiciste 6 repeticiones aunque te duele.", "habla_de_dolor"),
])
def test_resumen_rechazado_cae_a_plantilla(resumen, motivo):
    e = en.Entrenadora(generador(resumen), NOMBRES)
    r = e.entre_ejercicios(paso(), "plancha")
    assert r.origen == en.ORIGEN_PLANTILLA
    assert r.motivo_caida.startswith(motivo)
    assert r.texto.startswith("Hiciste 6 de 6 repeticiones")
    assert e.caidas == {motivo: 1}


def test_numeros_con_letras_que_estan_en_los_datos_se_aceptan():
    # «dos avisos» y «seis» están en los datos; «una» es artículo y no cuenta
    g = generador("Hiciste las seis repeticiones, con dos avisos y una repetición incompleta.")
    r = en.Entrenadora(g, NOMBRES).entre_ejercicios(paso(), "plancha")
    assert r.origen == en.ORIGEN_LLM


def test_accion_fuera_de_la_lista_o_no_permitida_cae_a_plantilla():
    r = en.Entrenadora(generador(accion="correr"), NOMBRES).entre_ejercicios(paso(), "plancha")
    assert r.origen == en.ORIGEN_PLANTILLA and r.motivo_caida.startswith("accion_desconocida")
    # al final de la rutina solo se puede terminar
    r = en.Entrenadora(generador("Cumpliste 1 ejercicio.", en.SEGUIR), NOMBRES).al_final([paso()])
    assert r.origen == en.ORIGEN_PLANTILLA and r.motivo_caida == "accion_no_permitida:seguir"
    assert r.accion == en.TERMINAR


def test_fallo_del_modelo_cae_a_plantilla():
    def roto(*a):
        raise TimeoutError("sin respuesta")
    r = en.Entrenadora(roto, NOMBRES).entre_ejercicios(paso(completadas=2), None)
    assert r.origen == en.ORIGEN_PLANTILLA
    assert r.motivo_caida == "fallo_backend:TimeoutError"
    assert r.accion == en.REPETIR               # no cumplió el objetivo
    assert en.FRASE_ACCION[en.REPETIR] in r.texto


def test_sin_modelo_responde_con_plantilla():
    e = en.Entrenadora(None, NOMBRES)
    r = e.entre_ejercicios(paso(), "plancha")
    assert (r.origen, r.accion, r.motivo_caida) == (en.ORIGEN_PLANTILLA, en.SEGUIR, "")
    fin = e.al_final([paso(), paso(completadas=10, objetivo=30, skill="plancha",
                                   unidad="segundos")])
    assert fin.accion == en.TERMINAR
    assert fin.texto == "Cumpliste el objetivo en 1 de 2 ejercicios. " + en.FRASE_FINAL


def test_como_voy_resume_lo_hecho_y_no_propone_nada():
    pasos = [paso(), paso(completadas=10, objetivo=30, avisos=1, skill="plancha", unidad="segundos")]
    # sin modelo: plantilla con las cuentas
    r = en.Entrenadora(None, NOMBRES).como_voy(pasos)
    assert (r.origen, r.accion) == (en.ORIGEN_PLANTILLA, en.SEGUIR)
    assert r.texto == "Llevas 2 ejercicios, 1 con el objetivo cumplido, y 3 correcciones."
    # con modelo: solo el resumen, sin la frase «Te propongo…»
    g = generador("Llevas 2 ejercicios y recibiste 3 avisos.")
    r = en.Entrenadora(g, NOMBRES).como_voy(pasos)
    assert (r.origen, r.texto) == (en.ORIGEN_LLM, "Llevas 2 ejercicios y recibiste 3 avisos.")
    assert g.pedidos[0][2] == en.PERMITIDAS[en.CONSULTA] == (en.SEGUIR,)
    assert "pregunta cómo va" in g.pedidos[0][1]
    assert all(frase not in r.texto for frase in en.FRASE_ACCION.values())
    # una cifra inventada cae a la plantilla, como en los otros momentos
    r = en.Entrenadora(generador("Llevas 7 ejercicios."), NOMBRES).como_voy(pasos)
    assert r.origen == en.ORIGEN_PLANTILLA and r.texto.startswith("Llevas 2 ejercicios")


@pytest.mark.parametrize("frase", ["me duele la rodilla", "Creo que me lesioné",
                                   "siento un tirón", "estoy mareada", "tengo un DOLOR aquí"])
def test_dolor_o_lesion_responde_fijo_sin_llamar_al_modelo(frase):
    g = generador()
    r = en.Entrenadora(g, NOMBRES).entre_ejercicios(paso(), "plancha", dice_usuaria=frase)
    assert (r.origen, r.texto, r.accion) == (en.ORIGEN_DOLOR, en.RESPUESTA_DOLOR, en.TERMINAR)
    assert g.pedidos == []


def test_frase_sin_dolor_no_dispara_la_respuesta_fija():
    assert not en.menciona_dolor("¿cómo voy?")
    assert not en.menciona_dolor("quiero repetir")
    assert not en.menciona_dolor(None)


def test_con_historial_se_dan_cifras_de_constancia_y_la_nota_fija():
    resumen = {"rutina": "Prueba", "terminada": True, "pasos": [paso()]}
    regs = [registro_de_sesion(resumen, datetime(2026, 11, d, 18, 0)) for d in (10, 12, 14)]
    prog = progreso(regs, date(2026, 11, 15))
    g = generador("Llevas 3 sesiones guardadas y hoy hiciste 6 repeticiones.")
    r = en.Entrenadora(g, NOMBRES).entre_ejercicios(paso(), "plancha", prog)
    assert r.origen == en.ORIGEN_LLM
    assert r.nota == en.NOTA_HISTORIAL
    assert "sesiones guardadas antes de hoy: 3" in g.pedidos[0][1]
    # el paso también se acepta en el formato del historial (campo `indicaciones`)
    assert "aviso dado 2 veces" in "\n".join(
        en.hechos_del_paso(regs[0]["pasos"][0], "Zancada"))


def test_esquema_de_ollama_limita_la_accion_a_las_permitidas():
    c = GeneradorOllama("modelo", timeout_s=1.0).cuerpo(en.SISTEMA, "datos", en.PERMITIDAS[en.FINAL])
    assert c["format"]["properties"]["accion"]["enum"] == [en.TERMINAR]
    assert c["think"] is False and c["stream"] is False
    assert c["messages"][0]["content"] == en.SISTEMA


def test_historial_de_ejemplo_desde_sesiones(tmp_path):
    import importlib.util
    ruta = Path(__file__).resolve().parent.parent / "scripts" / "historial_ejemplo.py"
    spec = importlib.util.spec_from_file_location("historial_ejemplo", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (tmp_path / "20261107-003901.json").write_text(json.dumps(
        {"rutina": "R", "terminada": False, "pasos": [paso()]}), encoding="utf-8")
    (tmp_path / "20261107-010519.json").write_text(json.dumps(
        {"rutina": "R", "terminada": False, "pasos": [paso(completadas=0)]}), encoding="utf-8")
    regs = mod.generar(tmp_path)
    assert len(regs) == 1 and regs[0]["fecha"] == "2026-11-07T00:39:01"
    assert regs[0]["pasos"][0]["indicaciones"]["paso_corto"]["veces"] == 2
    repartidos = mod.generar(tmp_path, repartir_dias=10, hoy=datetime(2026, 11, 16, 9, 0))
    assert repartidos[0]["fecha"].startswith("2026-11-15")


# ---------------------------------------------------------------------------
# En la sesión: entre ejercicios y al final, nunca durante el movimiento
# ---------------------------------------------------------------------------

from estela.adaptadores.llm.entrenadora_en_vivo import SIN_COLOCACION, TARDE, EntrenadoraEnVivo
from estela.aplicacion.rutina import cargar_catalogo, rutina_desde_dict
from estela.aplicacion.sesion import AVISO_COLOCADA, COLOCACION_ESTABLE_MS, Sesion
from tests.test_colocacion import EstimadorPlanchaEnImagen
from tests.test_sesion import VozFalsa

DT = 100


@pytest.fixture(scope="module")
def catalogo():
    return cargar_catalogo()


class Reloj:
    """Pasa frames a la sesión con un reloj que no retrocede."""

    def __init__(self, sesion):
        self.sesion, self.t = sesion, 0

    def correr(self, n, frame=0.0):
        estado = None
        for _ in range(n):
            estado = self.sesion.procesar(frame, self.t)
            self.t += DT
        return estado

    def hasta(self, condicion, tope=600):
        for _ in range(tope):
            estado = self.correr(1)
            if condicion(estado):
                return estado
        raise AssertionError("no se llegó a la condición")


def _dos_planchas(catalogo, colocacion=True, **kw):
    rutina = rutina_desde_dict({"nombre": "Prueba", "pasos": [
        {"skill_id": "plancha", "duracion_s": 2},
        {"skill_id": "plancha", "duracion_s": 2}]}, catalogo)
    voz = VozFalsa()
    eventos = []
    s = Sesion(rutina, catalogo, EstimadorPlanchaEnImagen(), voz, colocacion=colocacion,
               al_cerrar_paso=eventos.append, **kw)
    return s, voz, eventos, Reloj(s)


def _anuncios(voz):
    return [t for t, _ in voz.dichas if t.startswith("Ahora, plancha")]


def test_la_colocacion_se_retiene_hasta_que_la_entrenadora_suelta(catalogo):
    s, voz, eventos, reloj = _dos_planchas(catalogo, retencion_max_ms=60_000)
    reloj.hasta(lambda e: len(eventos) == 1)
    ev = eventos[0]
    assert (ev["final"], ev["retenida"], ev["siguiente"]) == (False, True, "plancha")
    assert ev["paso"]["completadas"] >= 2 and ev["pasos"] is None
    assert len(_anuncios(voz)) == 1                    # el del segundo ejercicio espera
    # bien colocada mucho más del tiempo estable: sigue sin empezar
    estado = reloj.correr(3 * COLOCACION_ESTABLE_MS // DT)
    assert estado.colocando and estado.completadas == 0
    assert s.entrenadora_vigente(ev["turno"])
    # mientras habla, su texto se lee donde va la instrucción de colocación
    assert "cabeza a los pies" in estado.instruccion
    assert s.mostrar_entrenadora(ev["turno"], "Hiciste 2 de 2 segundos.")
    assert reloj.correr(1).instruccion == "Hiciste 2 de 2 segundos."
    s.soltar_entrenadora(ev["turno"])
    assert "cabeza a los pies" in reloj.correr(1).instruccion
    assert not s.mostrar_entrenadora(ev["turno"], "tarde")
    assert len(_anuncios(voz)) == 2                    # ahora sí se anuncia
    assert not s.entrenadora_vigente(ev["turno"])
    estado = reloj.hasta(lambda e: not e.colocando)
    s.soltar_entrenadora(ev["turno"])                  # repetir no vuelve a anunciar
    assert len(_anuncios(voz)) == 2


def test_solo_se_puede_escuchar_entre_ejercicios_o_en_pausa_y_con_estela_callada(catalogo):
    s, voz, eventos, reloj = _dos_planchas(catalogo, retencion_max_ms=60_000)
    voz.ocupada = False
    assert s.puede_escuchar and not s.entre_ejercicios      # colocación del primer ejercicio
    reloj.hasta(lambda e: not e.colocando)
    assert not s.puede_escuchar                             # en movimiento no se escucha
    s.pausar()
    assert s.puede_escuchar                                 # en pausa sí
    voz.ocupada = True
    assert not s.puede_escuchar                             # pero no mientras habla ESTELA
    voz.ocupada = False
    s.reanudar()
    reloj.hasta(lambda e: len(eventos) == 1)
    assert s.puede_escuchar and s.entre_ejercicios          # colocación del segundo
    ligero = s.resumen_ligero()
    assert [p["skill_id"] for p in ligero] == ["plancha", "plancha"]
    assert ligero[0]["completadas"] >= 2 and ligero[1]["completadas"] == 0
    assert en.Entrenadora(None, {"plancha": "Plancha"}).como_voy(ligero).texto.startswith(
        "Llevas 2 ejercicios, 1 con el objetivo cumplido")


def test_la_retencion_tiene_tope(catalogo):
    s, voz, eventos, reloj = _dos_planchas(catalogo, retencion_max_ms=1000)
    reloj.hasta(lambda e: len(eventos) == 1)
    reloj.correr(9)
    assert len(_anuncios(voz)) == 1 and s.entrenadora_vigente(eventos[0]["turno"])
    reloj.correr(4)                                    # pasado 1 s se suelta sola
    assert len(_anuncios(voz)) == 2 and not s.entrenadora_vigente(eventos[0]["turno"])
    assert not reloj.hasta(lambda e: not e.colocando).colocando


def test_listo_corta_la_espera_a_la_entrenadora(catalogo):
    s, voz, eventos, reloj = _dos_planchas(catalogo, retencion_max_ms=60_000)
    reloj.hasta(lambda e: len(eventos) == 1)
    s.terminar_colocacion()
    assert not s.entrenadora_vigente(eventos[0]["turno"])
    assert not reloj.correr(1).colocando and len(_anuncios(voz)) == 2


def test_al_final_el_evento_trae_todos_los_pasos(catalogo):
    s, voz, eventos, reloj = _dos_planchas(catalogo, retencion_max_ms=60_000)
    reloj.hasta(lambda e: len(eventos) == 1)
    s.soltar_entrenadora(eventos[0]["turno"])
    reloj.hasta(lambda e: len(eventos) == 2)
    fin = eventos[1]
    assert fin["final"] and not fin["retenida"] and fin["siguiente"] is None
    assert [p["skill_id"] for p in fin["pasos"]] == ["plancha", "plancha"]
    assert s.entrenadora_vigente(fin["turno"])         # terminada: se puede hablar


def test_sin_colocacion_no_hay_retencion_y_el_anuncio_no_espera(catalogo):
    s, voz, eventos, reloj = _dos_planchas(catalogo, colocacion=False, retencion_max_ms=60_000)
    reloj.hasta(lambda e: len(eventos) == 1)
    assert not eventos[0]["retenida"] and len(_anuncios(voz)) == 2
    assert not s.entrenadora_vigente(eventos[0]["turno"])


def test_sin_gancho_la_sesion_no_cambia(catalogo):
    rutina = rutina_desde_dict({"nombre": "Prueba", "pasos": [
        {"skill_id": "plancha", "duracion_s": 2},
        {"skill_id": "plancha", "duracion_s": 2}]}, catalogo)
    voz = VozFalsa()
    s = Sesion(rutina, catalogo, EstimadorPlanchaEnImagen(), voz, colocacion=True)
    reloj = Reloj(s)
    reloj.hasta(lambda e: len(_anuncios(voz)) == 2)
    assert not reloj.hasta(lambda e: not e.colocando).colocando


class VozConEspera(VozFalsa):
    def esperar_vacia(self, timeout=10.0):
        pass


def test_en_vivo_habla_entre_ejercicios_y_suelta(catalogo):
    s, voz, _, reloj = _dos_planchas(catalogo)
    voz = s.voz = VozConEspera()
    vivo = EntrenadoraEnVivo(en.Entrenadora(None, {"plancha": "Plancha"}), voz, entre_ejercicios=True)
    vivo.conectar(s, 60_000)
    reloj.hasta(lambda e: len(vivo.registro) == 1)
    vivo.esperar(5.0)
    dicho = [t for t, _ in voz.dichas]
    i = next(k for k, t in enumerate(dicho) if en.FRASE_ACCION[en.SEGUIR] in t)
    assert dicho[i + 1].startswith("Ahora, plancha")   # primero la entrenadora, luego el anuncio
    assert vivo.registro[0]["dicha"] and vivo.registro[0]["respuesta"]["origen"] == en.ORIGEN_PLANTILLA
    reloj.hasta(lambda e: len(vivo.registro) == 2)     # final de la rutina
    vivo.esperar(5.0)
    assert vivo.registro[1]["momento"] == "final" and vivo.registro[1]["dicha"]
    assert en.FRASE_FINAL in voz.dichas[-1][0]
    assert vivo.resumen()["origenes"] == {en.ORIGEN_PLANTILLA: 2}


def test_en_vivo_descarta_la_respuesta_que_llega_con_el_ejercicio_en_marcha(catalogo):
    s, voz, _, reloj = _dos_planchas(catalogo)
    voz = s.voz = VozConEspera()
    import threading
    puerta = threading.Event()

    def lento(sistema, datos, permitidas):
        puerta.wait(5.0)
        return {"resumen": "Hiciste 2 segundos.", "accion": "seguir"}
    vivo = EntrenadoraEnVivo(en.Entrenadora(lento, {"plancha": "Plancha"}), voz, entre_ejercicios=True)
    vivo.conectar(s, 60_000)
    reloj.hasta(lambda e: len(vivo.registro) == 1)
    s.terminar_colocacion()                            # la usuaria no espera
    reloj.correr(5)
    puerta.set()
    vivo.esperar(5.0)
    assert vivo.registro[0]["motivo"] == TARDE and not vivo.registro[0]["dicha"]
    assert not any(en.FRASE_ACCION[en.SEGUIR] in t for t, _ in voz.dichas)


def test_en_vivo_sin_colocacion_solo_habla_al_final(catalogo):
    s, voz, _, reloj = _dos_planchas(catalogo, colocacion=False)
    voz = s.voz = VozConEspera()
    vivo = EntrenadoraEnVivo(en.Entrenadora(None, {"plancha": "Plancha"}), voz, entre_ejercicios=True)
    vivo.conectar(s, 60_000)
    reloj.hasta(lambda e: s.terminada)
    vivo.esperar(5.0)
    assert [(r["momento"], r["motivo"], r["dicha"]) for r in vivo.registro] == [
        ("entre", SIN_COLOCACION, False), ("final", "", True)]


def test_en_vivo_por_defecto_no_habla_entre_ejercicios_ni_retiene(catalogo):
    """Paula, 2026-11-20: entre ejercicios se pasa al siguiente sin resumen."""
    from estela.adaptadores.llm.entrenadora_en_vivo import APAGADA_ENTRE
    s, voz, _, reloj = _dos_planchas(catalogo)
    voz = s.voz = VozConEspera()
    vivo = EntrenadoraEnVivo(en.Entrenadora(None, {"plancha": "Plancha"}), voz)
    vivo.conectar(s, 60_000)
    assert s.retencion_max_ms == 0
    reloj.hasta(lambda e: s.terminada)
    vivo.esperar(5.0)
    assert [(r["momento"], r["motivo"], r["dicha"]) for r in vivo.registro] == [
        ("entre", APAGADA_ENTRE, False), ("final", "", True)]
    assert not any(en.FRASE_ACCION[en.SEGUIR] in t for t, _ in voz.dichas)


# ---------------------------------------------------------------------------
# Con la cola de voz real (un solo hueco pendiente): nada pisa a la entrenadora
# ---------------------------------------------------------------------------

import time

from estela.adaptadores.voz.cola import ColaVoz
from estela.adaptadores.voz.motores import MotorVoz


class MotorLento(MotorVoz):
    """Tarda un poco en «decir» cada frase y apunta el orden."""
    nombre = "lento"

    def __init__(self, segundos=0.06):
        self.segundos, self.dichas = segundos, []

    def hablar(self, texto):
        self.dichas.append(texto)
        time.sleep(self.segundos)


def test_con_la_cola_real_la_entrenadora_suena_entera_y_antes_del_anuncio(catalogo):
    rutina = rutina_desde_dict({"nombre": "Prueba", "pasos": [
        {"skill_id": "plancha", "duracion_s": 2},
        {"skill_id": "plancha", "duracion_s": 2}]}, catalogo)
    motor = MotorLento()
    cola = ColaVoz(motor)
    try:
        s = Sesion(rutina, catalogo, EstimadorPlanchaEnImagen(), cola, colocacion=True)
        vivo = EntrenadoraEnVivo(en.Entrenadora(None, {"plancha": "Plancha"}), cola, entre_ejercicios=True)
        vivo.conectar(s, 10 * 60_000)             # tope lejano: aquí manda la entrenadora
        t = 0
        limite = time.monotonic() + 20.0
        while not s.terminada and time.monotonic() < limite:
            s.procesar(0.0, t)
            t += DT
            time.sleep(0.002)                     # deja correr al hilo de la voz
        assert s.terminada
        vivo.esperar(10.0)
        cola.esperar_vacia(5.0)
    finally:
        cola.cerrar(esperar=False)
    entre, final = vivo.registro
    assert entre["dicha"] and final["dicha"]
    dichas = motor.dichas
    i_fin_paso = dichas.index("Muy bien, terminaste plancha.")
    i_entre = dichas.index(entre["respuesta"]["texto"])
    i_anuncio = max(k for k, x in enumerate(dichas) if x.startswith("Ahora, plancha"))
    assert i_fin_paso < i_entre < i_anuncio        # resumen, y solo después el ejercicio nuevo
    assert dichas[-1] == final["respuesta"]["texto"]
    # ninguna de las dos respuestas se descartó en la cola
    for r in (entre, final):
        fila = next(f for f in cola.registro if f["texto"] == r["respuesta"]["texto"])
        assert not fila["descartada"] and fila["t_inicio"] is not None
