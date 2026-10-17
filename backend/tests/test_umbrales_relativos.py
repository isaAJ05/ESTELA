"""Reglas relativas a la referencia (ADR-004 §2.1–2.2, EXP-006 fase 1).

- `desviacion` con `k`: umbral `k × max(σ_ref, ruido)` en cada frame, o sobre
  la mediana de la repetición (`fn: mediana`).
- agregado `max`/`min` con `extremo`: umbral contra el extremo de la referencia.
- Con umbrales «referencia» la forma relativa manda y la absoluta queda de
  respaldo para los frames sin referencia.
"""

import pytest

from estela.aplicacion.dtw import (ALINEADO, SIN_REPETICION, AlineadorDTW,
                                   ReferenciaPostura, comparador_de_referencia)
from estela.aplicacion.rutina import (RutinaInvalida, cargar_catalogo,
                                      rutina_de_un_ejercicio)
from estela.aplicacion.umbrales import con_umbrales_de_referencia, umbral_de_extremo
from estela.dominio.feedback.contrato import (MOTIVO_DTW_NO_DISPONIBLE, Direccion,
                                              ErrorTipificado, Observacion, Silencio)
from estela.dominio.feedback.motor.decision import MotorDecision
from estela.dominio.feedback.motor.skill import SkillInvalido, skill_desde_dict


def regla(**cambios):
    base = {"error_id": "tronco", "medida": {"tipo": "angulo", "nombre": "tronco"},
            "condicion": {"op": ">", "umbral": 8}, "segmento": "tronco", "lado": "na",
            "plano": "cualquiera", "prioridad": 1, "severidad": {"moderada": 5, "alta": 12},
            "direccion": {"disminuir": "atras"}}
    base.update(cambios)
    return base


def skill(*reglas):
    return skill_desde_dict({
        "skill_id": "x", "nombre": "X", "version": "0", "reglas": list(reglas),
        "politica_silencio": {"repeticiones_evidencia": 1, "refractario_ms": 0,
                              "refractario_mismo_error_ms": 0}})


RELATIVA = {"medida": {"tipo": "desviacion", "nombre": "tronco"},
            "condicion": {"op": ">", "k": 3, "ruido": 2}}


def obs(tronco, t=0, rep=1, ref=None, sigma=None, coste=1.0):
    con_ref = ref is not None
    return Observacion(t_ms=t, ejercicio_id="x", angulos={"tronco": tronco},
                       confianza={"tronco": 0.9}, repeticion=rep,
                       angulos_ref={"tronco": ref} if con_ref else {},
                       sigma_ref={"tronco": sigma} if sigma is not None else {},
                       coste_dtw=coste if con_ref else None)


REFERENCIA = {"medidas": ["tronco", "brazo"], "tipo": "ciclico", "fps": 30.0,
              "angulos": {"media": [[0.0, 10.0], [1.0, 120.0], [2.0, 40.0]],
                          "sigma": [[0.5, 1.0], [0.5, 4.0], [0.5, 2.0]]}}


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mala", [
    regla(condicion={"op": ">", "k": 3}),                                  # k sin desviacion
    regla(relativa={"condicion": {"op": ">", "umbral": 3}}),              # relativa sin k
    regla(relativa={"medida": {"tipo": "desviacion", "nombre": "tronco"},
                    "condicion": {"op": ">", "k": 3, "extremo": "max"}}),  # extremo sin agregado
    regla(medida={"tipo": "desviacion", "nombre": "tronco"},
          condicion={"op": ">", "k": 3, "extremo": "max"}),                # extremo fuera de relativa
    regla(relativa={"medida": {"tipo": "desviacion", "nombre": "tronco", "fn": "media"},
                    "condicion": {"op": ">", "k": 3}}),                    # fn de desviacion
    regla(relativa={"medida": {"tipo": "desviacion", "nombre": "tronco"},
                    "condicion": {"op": "dentro_de", "k": 3}}),
])
def test_formas_relativas_mal_declaradas_se_rechazan(mala):
    with pytest.raises(SkillInvalido):
        skill(mala)


def test_la_forma_relativa_se_carga_sin_cambiar_la_regla():
    r = skill(regla(relativa=RELATIVA)).reglas[0]
    assert r.medida.tipo == "angulo" and r.condicion.umbral == 8
    assert r.relativa.medida.tipo == "desviacion" and r.relativa.condicion.k == 3
    assert r.respaldo is None


# ---------------------------------------------------------------------------
# Motor: umbral k × max(σ_ref, ruido)
# ---------------------------------------------------------------------------

def test_desviacion_relativa_frame_a_frame():
    motor = MotorDecision(skill(regla(medida=RELATIVA["medida"],
                                      condicion=RELATIVA["condicion"])))
    # σ = 4 > ruido = 2: umbral 12. Desviación 10: no; 13: sí
    assert isinstance(motor.observar(obs(20, ref=10, sigma=4)), Silencio)
    err = motor.observar(obs(23, t=100, ref=10, sigma=4))
    assert isinstance(err, ErrorTipificado)
    assert err.magnitud == pytest.approx(1.0)                 # en grados sobre el umbral
    assert err.medida == "desviacion:tronco" and err.direccion == Direccion.ATRAS


def test_el_ruido_es_el_piso_de_la_escala():
    motor = MotorDecision(skill(regla(medida=RELATIVA["medida"],
                                      condicion=RELATIVA["condicion"])))
    # σ = 0,5 < ruido = 2: el umbral es 6, no 1,5
    assert isinstance(motor.observar(obs(15, ref=10, sigma=0.5)), Silencio)
    assert isinstance(motor.observar(obs(17, t=100, ref=10, sigma=0.5)), ErrorTipificado)


def test_fuera_de_relativo_mira_los_dos_lados():
    motor = MotorDecision(skill(regla(medida=RELATIVA["medida"],
                                      condicion={"op": "fuera_de", "k": 2, "ruido": 1},
                                      direccion={})))
    assert isinstance(motor.observar(obs(7, ref=10, sigma=1)), ErrorTipificado)
    assert isinstance(MotorDecision(motor.skill).observar(obs(13, ref=10, sigma=1)),
                      ErrorTipificado)
    assert isinstance(MotorDecision(motor.skill).observar(obs(11, ref=10, sigma=1)),
                      Silencio)


def test_mediana_de_la_repeticion_ignora_un_frame_suelto():
    mediana = {"tipo": "desviacion", "nombre": "tronco", "fn": "mediana"}
    motor = MotorDecision(skill(regla(medida=mediana, condicion=RELATIVA["condicion"])))
    # un pico de 30 grados entre frames normales no cambia la mediana
    for i, tronco in enumerate([10, 11, 40, 10, 11]):
        d = motor.observar(obs(tronco, t=i * 33, ref=10, sigma=1))
        assert isinstance(d, Silencio), i
    # una desviación sostenida sí, en cuanto hay `MIN_MUESTRAS_MEDIANA` (3)
    motor = MotorDecision(motor.skill)
    decisiones = [motor.observar(obs(20, t=i * 33, ref=10, sigma=1)) for i in range(3)]
    assert [type(d).__name__ for d in decisiones] == ["Silencio", "Silencio", "ErrorTipificado"]
    assert decisiones[2].medida == "mediana(desviacion:tronco)@repeticion"


def test_la_mediana_se_reinicia_en_cada_repeticion():
    mediana = {"tipo": "desviacion", "nombre": "tronco", "fn": "mediana"}
    motor = MotorDecision(skill(regla(medida=mediana, condicion=RELATIVA["condicion"])))
    for i in range(2):
        motor.observar(obs(20, t=i * 33, rep=1, ref=10, sigma=1))
    # repetición nueva: las dos muestras de la anterior no cuentan
    assert isinstance(motor.observar(obs(20, t=100, rep=2, ref=10, sigma=1)), Silencio)


def test_sin_referencia_evalua_el_respaldo_absoluto():
    compilado = con_umbrales_de_referencia(skill(regla(relativa=RELATIVA)),
                                           {"medidas": ["tronco"]})
    r = compilado.reglas[0]
    assert r.medida.tipo == "desviacion" and r.respaldo[1].umbral == 8
    motor = MotorDecision(compilado)
    err = motor.observar(obs(9))                    # sin DTW: absoluta, 9 > 8
    assert isinstance(err, ErrorTipificado) and err.medida == "angulo:tronco"
    assert motor.contador_respaldo == {"tronco": 1}
    assert MOTIVO_DTW_NO_DISPONIBLE not in motor.contador_abstenciones


def test_sin_respaldo_la_desviacion_se_abstiene():
    motor = MotorDecision(skill(regla(medida=RELATIVA["medida"],
                                      condicion=RELATIVA["condicion"])))
    assert motor.observar(obs(30)).motivo == MOTIVO_DTW_NO_DISPONIBLE
    # con referencia pero sin σ ni ruido no hay escala: tampoco se evalúa
    sin_ruido = {"op": ">", "k": 3}
    motor = MotorDecision(skill(regla(medida=RELATIVA["medida"], condicion=sin_ruido)))
    assert motor.observar(obs(30, ref=10)).motivo == MOTIVO_DTW_NO_DISPONIBLE


# ---------------------------------------------------------------------------
# Umbrales contra el extremo de la referencia
# ---------------------------------------------------------------------------

def test_umbral_de_extremo():
    sk = skill(regla(error_id="amplitud",
                     medida={"tipo": "agregado", "fn": "max", "nombre": "brazo"},
                     condicion={"op": "<", "umbral": 100},
                     relativa={"condicion": {"op": "<", "k": 2, "ruido": 3, "extremo": "max"}}))
    cond = sk.reglas[0].relativa.condicion
    # máximo 120 con σ 4 en ese frame: 120 − 2·max(4, 3) = 112
    assert umbral_de_extremo(REFERENCIA, "brazo", cond) == pytest.approx(112.0)
    r = con_umbrales_de_referencia(sk, REFERENCIA).reglas[0]
    assert (r.condicion.umbral, r.condicion.k, r.respaldo, r.relativa) == (
        pytest.approx(112.0), None, None, None)
    # k para todo el skill (barridos)
    assert con_umbrales_de_referencia(sk, REFERENCIA, k=1).reglas[0].condicion.umbral == \
        pytest.approx(116.0)


def test_sin_la_medida_en_la_referencia_la_regla_se_queda_absoluta():
    sk = skill(regla(relativa={"medida": {"tipo": "desviacion", "nombre": "otra"},
                               "condicion": {"op": ">", "k": 3}}))
    for ref in (None, {}, REFERENCIA):
        assert con_umbrales_de_referencia(sk, ref).reglas[0] == sk.reglas[0]


# ---------------------------------------------------------------------------
# Comparadores y sesión
# ---------------------------------------------------------------------------

def test_el_dtw_entrega_sigma_ref_del_instante_alineado():
    al = AlineadorDTW(REFERENCIA)
    for i, fila in enumerate(REFERENCIA["angulos"]["media"]):
        r = al.actualizar(Observacion(t_ms=i * 33, ejercicio_id="x",
                                      angulos=dict(zip(REFERENCIA["medidas"], fila)),
                                      confianza={"tronco": 0.9, "brazo": 0.9}, repeticion=1))
    assert r.indice == 2 and r.sigma_ref == {"tronco": 0.5, "brazo": 2.0}


def test_la_plancha_se_compara_con_su_postura_media():
    plancha = cargar_catalogo()["plancha"].referencia
    comparador = comparador_de_referencia(plancha)
    assert isinstance(comparador, ReferenciaPostura)
    assert isinstance(comparador_de_referencia(REFERENCIA), AlineadorDTW)
    o = Observacion(t_ms=0, ejercicio_id="plancha", angulos={"cabeza_adelantada": 15.0},
                    distancias={"alineacion_cadera": 0.0},
                    confianza={"cabeza_adelantada": 0.9, "alineacion_cadera": 0.9},
                    repeticion=1)
    r = comparador.actualizar(o)
    medias = dict(zip(plancha["medidas"], plancha["postura"]["media"]))
    assert r.angulos_ref == pytest.approx(medias) and r.progreso is None
    assert r.sigma_ref["alineacion_cadera"] == pytest.approx(0.061)
    assert comparador.actualizar(Observacion(t_ms=1, ejercicio_id="plancha", angulos={},
                                             confianza={}, repeticion=0)) is None
    assert comparador.motivos == {ALINEADO: 1, SIN_REPETICION: 1}


def test_catalogo_con_umbrales_de_referencia():
    with pytest.raises(RutinaInvalida):
        cargar_catalogo(umbrales="otros")
    absolutos, relativos = cargar_catalogo(), cargar_catalogo(umbrales="referencia")
    assert {e.umbrales for e in relativos.values()} == {"referencia"}
    for sid, ej in relativos.items():
        for antes, ahora in zip(absolutos[sid].skill.reglas, ej.skill.reglas):
            if antes.relativa is None:
                assert ahora == antes
            else:
                # toda forma relativa del catálogo encuentra su medida en la referencia
                assert ahora.relativa is None, f"{sid}/{antes.error_id}"
                assert ahora.medida == antes.relativa.medida


def test_sesion_con_umbrales_de_referencia_lo_dice_en_el_resumen():
    catalogo = cargar_catalogo(umbrales="referencia")

    class Muda:
        def decir(self, texto, prioridad=0):
            return True

    from estela.aplicacion.sesion import Sesion
    s = Sesion(rutina_de_un_ejercicio("jumping_jacks", 5, catalogo), catalogo,
               estimador=None, voz=Muda())
    paso = s.resumen()["pasos"][0]
    assert paso["umbrales"] == "referencia" and paso["respaldos"] == {}
