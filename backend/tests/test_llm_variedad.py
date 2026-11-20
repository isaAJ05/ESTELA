"""El LLM que redacta varía la frase de una misma corrección (Paula, 2026-11-20)."""

import json

from estela.adaptadores.llm.llm_local import (
    BACKEND_OLLAMA, SISTEMA, SISTEMA_ANTERIOR, VerbalizadorLLMLocal,
)
from estela.dominio.feedback.contrato import Direccion, ErrorTipificado, Lado, Severidad


def _error(rep=0):
    return ErrorTipificado(error_id="cadera_hundida", segmento="cadera", lado=Lado.BILATERAL,
                           severidad=Severidad.MODERADA, fase="", repeticion=rep,
                           ejercicio_id="plancha", mensaje_id="cadera_hundida",
                           direccion=Direccion.SUBIR)


class LLMFalso(VerbalizadorLLMLocal):
    def __init__(self, respuestas, **kw):
        super().__init__(backend=BACKEND_OLLAMA, modelo="m", **kw)
        self.respuestas, self.cuerpos = list(respuestas), []

    def _post(self, cuerpo, timeout_s):
        self.cuerpos.append(cuerpo)
        return {"message": {"content": json.dumps({"mensaje": self.respuestas.pop(0)})}}


def test_pide_otras_palabras_con_la_referencia_y_lo_ya_dicho():
    v = LLMFalso(["Sube la cadera un poco.", "Vamos, eleva la cadera."])
    assert v.verbalizar(_error(0)).texto == "Sube la cadera un poco."
    v.verbalizar(_error(1))
    sistema, usuario = (m["content"] for m in v.cuerpos[1]["messages"])
    assert sistema == SISTEMA
    assert "frase de referencia" in usuario and "«Sube la cadera un poco.»" in usuario
    assert "veces que ya se corrigió esto en este ejercicio: 1" in usuario
    assert v.temperatura == 0.7


def test_lo_que_cae_a_plantilla_tambien_cuenta_como_dicho():
    v = LLMFalso(["Sube la rodilla."])                  # parte ajena: el validador la rechaza
    m = v.verbalizar(_error(0))
    assert m.fallback and v._dichas[v._clave(_error())][-1] == m.texto


def test_sin_variar_es_el_comportamiento_de_antes():
    v = LLMFalso(["Sube la cadera."], variar=False)
    v.verbalizar(_error(0))
    sistema, usuario = (m["content"] for m in v.cuerpos[0]["messages"])
    assert sistema == SISTEMA_ANTERIOR and "referencia" not in usuario
    assert v.temperatura == 0.3 and not v._dichas


def test_un_animo_sin_la_correccion_cae_a_plantilla():
    v = LLMFalso(["Cadera, así, muy bien."])
    m = v.verbalizar(_error(0))
    assert m.fallback and m.motivo_rechazo == "sin_correccion"


def test_otra_direccion_compatible_vale_y_el_tronco_se_describe_hacia_un_lado():
    from estela.adaptadores.llm.llm_local import _descripcion_variada
    v = LLMFalso(["Vamos, eleva la cadera."])
    assert not v.verbalizar(_error(0)).fallback
    e = ErrorTipificado(error_id="tronco_inclinado_der", segmento="tronco", lado=Lado.DERECHO,
                        severidad=Severidad.LEVE, fase="", repeticion=0,
                        ejercicio_id="abduccion_cadera_izq")
    d = _descripcion_variada(e, "No inclines el tronco hacia la derecha.", (), 0)
    assert "hacia la derecha" in d and "tronco derecho" not in d
