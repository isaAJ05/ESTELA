"""`informe2 --verbalizador llm`: detección → voz con el LLM redactando aparte.

Desde `b9b918c` el LLM redacta fuera del bucle por imagen: la corrección se
encola cuando la redacción vuelve, y las sustituidas o tardías no se encolan
nunca. El arnés mide cada frase encolada desde el frame en que se detectó.
Sin Ollama ni vídeo: verbalizador, estimador y captura falsos.
"""

import json
import time
from pathlib import Path

import pytest

from estela import config
from estela.adaptadores.llm.llm_local import VerbalizadorLLMLocal
from estela.aplicacion.puertos import PRIORIDAD_AVISO, PRIORIDAD_FEEDBACK
from estela.dominio.feedback.contrato import MensajeFeedback
from estela.dominio.feedback.verbalizador.plantillas import VerbalizadorPlantillas
from feedback_testing import informe2 as i2
from tests.test_llm_variedad import _error
from tests.test_sesion import EstimadorPlancha, catalogo  # noqa: F401 (fixture)

FRASE_LLM = "LLM: sube la cadera."


class LLMLento(VerbalizadorPlantillas):
    """Tarda como un LLM y firma sus frases; tiene `fallback`, como el de verdad."""
    nombre = "lento"

    def __init__(self, segundos=0.15):
        super().__init__()
        self.segundos = segundos
        self.fallback = VerbalizadorPlantillas()

    def verbalizar(self, error):
        time.sleep(self.segundos)
        return MensajeFeedback(texto=FRASE_LLM, error=error, verbalizador=self.nombre)


class EstimadorPlanchaDeArnes(EstimadorPlancha):
    def cerrar(self):
        pass


class Cv2Falso:
    """Un «vídeo» cuyos frames son el hundimiento de la cadera (plancha con la
    cadera caída), entregados cada pocos milisegundos."""

    def __init__(self, frames, pausa_s=0.004):
        self._frames, self._pausa = frames, pausa_s

    def VideoCapture(self, ruta):
        cv2, pendientes = self, iter([0.08] * self._frames)

        class Captura:
            def read(self):
                time.sleep(cv2._pausa)
                frame = next(pendientes, None)
                return frame is not None, frame

            def release(self):
                pass
        return Captura()


def _plancha(monkeypatch, catalogo, verbalizador=None, frames=250):  # noqa: F811
    """`reproducir_video` de verdad sobre 25 s de plancha con la cadera caída."""
    monkeypatch.setattr(i2, "_nuevo_estimador", lambda modelo: (EstimadorPlanchaDeArnes(), 0.0))
    video = i2.Video(Path("plancha falsa.mp4"), "plancha", fps=10.0, frames=frames)
    return i2.reproducir_video(Cv2Falso(frames), video, catalogo, "falso", "cola", "max",
                               i2.VozMuda(), verbalizador=verbalizador)


def _emparejado_de_antes(c):
    """`Corrida.deteccion_a_voz` tal como era antes de `--verbalizador llm`."""
    con_msg = [i for i, e in enumerate(c.registro) if e.get("mensaje")]
    feedback = [v for v in c.voz if v["prioridad"] == PRIORIDAD_FEEDBACK]
    res = []
    for i, v in zip(con_msg, feedback):
        e = c.registro[i]
        d = {"t_ms": e["t_ms"], "refuerzo": e["mensaje"]["refuerzo"],
             "descartada": v["descartada"], "motivo_descarte": v.get("motivo_descarte"),
             "frame_a_encolado_s": v["t_encolado"] - c.llegada[i]}
        if v.get("t_inicio_audio") is not None:
            d["encolado_a_audio_s"] = v["t_inicio_audio"] - v["t_encolado"]
            d["total_s"] = v["t_inicio_audio"] - c.llegada[i]
        res.append(d)
    return res


def test_con_el_llm_se_mide_desde_el_frame_en_que_se_detecto(monkeypatch, catalogo):  # noqa: F811
    lento = LLMLento()
    c = _plancha(monkeypatch, catalogo, i2.VerbalizadorMedido(lento))
    decididas = [e for e in c.registro if e["mensaje"] and not e["mensaje"]["refuerzo"]]
    red = c.redaccion()
    assert red["detectadas"] == len(decididas) >= 1
    assert red["detectadas"] == red["sustituidas"] + red["redactadas"] and red["sin_terminar"] == 0
    assert red["redactadas"] == red["tarde"] + red["encoladas"]
    assert red["del_llm"] == red["redactadas"] and red["a_plantilla"] == 0

    dichas = [d for d in c.deteccion_a_voz() if not d["refuerzo"]]
    assert len(dichas) == red["encoladas"] >= 1
    for d in dichas:
        assert not d["descartada"]
        assert d["t_ms"] in {e["t_ms"] for e in decididas}        # un frame con corrección decidida
        assert d["frame_a_encolado_s"] >= lento.segundos           # incluye lo que tardó el LLM
        assert d["total_s"] >= d["frame_a_encolado_s"]
    assert all(r["ms"] >= lento.segundos * 1000 for r in red["redacciones"])
    # lo que cuenta como dicho es la frase del LLM; el registro guarda la plantilla del motor
    assert {m.texto for m in c.mensajes() if m.error_id} == {FRASE_LLM}
    assert all(e["mensaje"]["texto"] != FRASE_LLM for e in decididas)


def test_sin_llm_sale_lo_mismo_que_antes(monkeypatch, catalogo):  # noqa: F811
    c = _plancha(monkeypatch, catalogo)
    assert not c.redaccion_aparte and c.redaccion() is None and c.redacciones == []
    antes = _emparejado_de_antes(c)
    assert antes and c.deteccion_a_voz() == antes
    assert [m.texto for m in c.mensajes()] == [e["mensaje"]["texto"] for e in c.registro
                                               if e["mensaje"]]


def test_las_sustituidas_y_las_tardias_no_descolocan_el_emparejamiento():
    """Cuatro correcciones decididas (frames 100, 300, 500 y 700 ms). La de 300
    se sustituyó sin redactarse y la de 500 volvió tarde: se dijeron la de 100 y
    la de 700. Emparejar «n-ésimo frame con mensaje ↔ n-ésima frase» mediría la
    segunda frase desde el frame 300."""
    def decidida(t):
        return {"t_ms": t, "skill_id": "plancha",
                "mensaje": {"texto": "Sube la cadera.", "refuerzo": False,
                            "error_id": "cadera_hundida", "segmento": "cadera",
                            "lado": "bilateral", "severidad": "moderada", "fallback": False}}

    def dicha(t, texto):
        return {"t_ms": t, "texto": texto, "error_id": "cadera_hundida", "segmento": "cadera",
                "lado": "bilateral", "severidad": "moderada", "repeticion": 2}

    def encolada(texto, prioridad, t_encolado, t_audio):
        return {"texto": texto, "prioridad": prioridad, "t_encolado": t_encolado,
                "t_inicio": t_audio, "t_inicio_audio": t_audio, "t_fin": t_audio + 1.0,
                "descartada": False, "motivo_descarte": None}

    c = i2.Corrida("sintética", {"tipo": "video"}, "plancha", "ultimo", "real", "falso")
    c.t_ms = list(range(0, 800, 100))
    c.llegada = [10.0 + t / 1000.0 for t in c.t_ms]
    c.registro = [decidida(t) if t in (100, 300, 500, 700)
                  else {"t_ms": t, "skill_id": "plancha", "mensaje": None} for t in c.t_ms]
    c.resumen = {"pasos": [{"skill_id": "plancha",
                            "mensajes": [dicha(100, "LLM uno"), dicha(700, "Sube la cadera.")]}],
                 "verbalizacion_aparte": {"pedidas": 4, "sustituidas": 1, "tarde": 1}}
    c.voz = [encolada("Ahora, plancha.", PRIORIDAD_AVISO, 9.9, 9.9),
             encolada("LLM uno", PRIORIDAD_FEEDBACK, 10.35, 10.36),
             encolada("Sube la cadera.", PRIORIDAD_FEEDBACK, 11.1, 11.13)]
    c.redacciones = [{"ms": 250.0, "plantilla": False, "motivo": None},
                     {"ms": 240.0, "plantilla": False, "motivo": None},
                     {"ms": 400.0, "plantilla": True, "motivo": "fallo_backend:TimeoutError"}]

    dv = c.deteccion_a_voz()
    assert [d["t_ms"] for d in dv] == [100, 700]
    assert dv[0]["frame_a_encolado_s"] == pytest.approx(0.25)
    assert dv[1]["frame_a_encolado_s"] == pytest.approx(0.40)      # desde el frame 700, no el 300
    assert dv[1]["total_s"] == pytest.approx(0.43)
    assert [m.texto for m in c.mensajes()] == ["LLM uno", "Sube la cadera."]
    red = c.redaccion()
    assert {k: red[k] for k in ("detectadas", "sustituidas", "redactadas", "sin_terminar",
                                "tarde", "encoladas", "del_llm", "a_plantilla")} == {
        "detectadas": 4, "sustituidas": 1, "redactadas": 3, "sin_terminar": 0,
        "tarde": 1, "encoladas": 2, "del_llm": 2, "a_plantilla": 1}
    assert red["caidas"] == {"fallo_backend:TimeoutError": 1}
    md = "\n".join(i2._seccion_redaccion([c], {"modelo": "m", "backend": "ollama",
                                               "timeout_ms": 400}))
    assert "| sustituidas sin redactar (llegó otra mientras esperaban al LLM) | 1 |" in md
    assert "| — caídas a plantilla | 1 (por motivo: `fallo_backend:TimeoutError` 1) |" in md
    assert "| plancha | 2 |" in md                                 # detección → voz por ejercicio


def test_el_verbalizador_es_el_de_la_app_y_apunta_cada_redaccion(monkeypatch):
    """Mismo modelo, backend y tiempo límite que `python -m estela --verbalizador llm`."""
    from estela import __main__ as app
    respuestas = ["Sube la cadera un poco.", TimeoutError(), "Sube la rodilla."]

    def _post(self, cuerpo, timeout_s):
        if not cuerpo["messages"]:                                 # precalentado o recarga
            return {}
        r = respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return {"message": {"content": json.dumps({"mensaje": r})}}

    monkeypatch.setattr(app, "_llm_listo", lambda *a: True)
    monkeypatch.setattr(VerbalizadorLLMLocal, "_post", _post)
    v, desc = i2.crear_verbalizador("llm")
    assert (desc["quien"], desc["modelo"], desc["backend"], desc["timeout_ms"]) == (
        "llm", config.LLM_MODELO, "ollama", config.LLM_TIMEOUT_MS)
    assert isinstance(v.fallback, VerbalizadorPlantillas) and v.modelo == config.LLM_MODELO

    assert v.verbalizar(_error(0)).texto == "Sube la cadera un poco."
    assert v.verbalizar(_error(1)).fallback                        # pasó del tiempo límite
    assert v.verbalizar(_error(2)).fallback                        # parte ajena: lo rechaza el validador
    assert [r["plantilla"] for r in v.redacciones] == [False, True, True]
    assert v.redacciones[0]["motivo"] is None
    assert v.redacciones[1]["motivo"] == "fallo_backend:TimeoutError"
    # los mismos motivos que cuenta la app en su resumen (`caidas`)
    assert {r["motivo"] for r in v.redacciones[1:]} == set(v.caidas) and len(v.caidas) == 2
    assert v.llamadas == 3 and all(r["ms"] >= 0 for r in v.redacciones)


def test_sin_ollama_no_mide_con_plantillas_por_su_cuenta(monkeypatch):
    from estela import __main__ as app
    monkeypatch.setattr(app, "_llm_listo", lambda *a: False)
    with pytest.raises(SystemExit):
        i2.crear_verbalizador("llm")
    assert i2.crear_verbalizador("plantillas") == (None, {"quien": "plantillas"})
    with pytest.raises(SystemExit):
        i2.ejecutar(i2.Opciones(camara=0, ejercicio="plancha", verbalizador="llm"))
