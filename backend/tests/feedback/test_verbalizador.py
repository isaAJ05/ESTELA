import itertools
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from estela.dominio.feedback.contrato import Direccion, ErrorTipificado, Lado, Severidad
from estela.dominio.feedback.motor.skill import cargar_skills, directorio_skills
from estela.adaptadores.llm.llm_local import (
    BACKEND_OLLAMA, ESQUEMA_SALIDA, URL_LLAMA, URL_OLLAMA, VerbalizadorLLMLocal,
    _descripcion_error,
)
from estela.dominio.feedback.verbalizador.plantillas import (
    DIRECCION_ES, VerbalizadorPlantillas,
)
from estela.dominio.feedback.verbalizador.validador import (
    afirmaciones_no_soportadas, direcciones_pedidas, lados_mencionados,
    segmentos_mencionados, validar,
)

SKILLS = cargar_skills(directorio_skills())


def err(error_id="tronco_muy_inclinado", segmento="tronco", lado=Lado.NA,
        severidad=Severidad.MODERADA, rep=1, mensaje_id=None, direccion=None):
    return ErrorTipificado(
        error_id=error_id, segmento=segmento, lado=lado, severidad=severidad,
        fase="descenso", repeticion=rep, ejercicio_id="sentadilla",
        mensaje_id=mensaje_id if mensaje_id is not None else error_id,
        direccion=direccion)


class TestValidador(unittest.TestCase):
    def test_acepta_mensaje_correcto(self):
        self.assertTrue(validar("Endereza el tronco.", err()))

    def test_rechaza_segmento_ajeno(self):
        r = validar("Endereza el tronco y sube la rodilla.", err())
        self.assertFalse(r.valido)
        self.assertTrue(r.motivo.startswith("segmento_ajeno"))

    def test_rechaza_lado_incorrecto(self):
        e = err("valgo_rodilla_izq", "rodilla", Lado.IZQUIERDO)
        r = validar("Abre la rodilla derecha.", e)
        self.assertFalse(r.valido)
        self.assertTrue(r.motivo.startswith("lado_incorrecto"))

    def test_rechaza_lado_inventado_en_bilateral(self):
        e = err("profundidad_insuficiente", "rodilla", Lado.BILATERAL)
        r = validar("Baja más la rodilla izquierda.", e)
        self.assertFalse(r.valido)
        self.assertTrue(r.motivo.startswith("lado_inventado"))

    def test_exige_el_lado_cuando_el_contrato_lo_trae(self):
        e = err("valgo_rodilla_izq", "rodilla", Lado.IZQUIERDO)
        r = validar("Abre la rodilla.", e)
        self.assertFalse(r.valido)
        self.assertEqual(r.motivo, "lado_omitido")

    def test_rechaza_vocabulario_medico(self):
        r = validar("Endereza el tronco o te vas a lesionar.", err())
        self.assertFalse(r.valido)
        self.assertTrue(r.motivo.startswith("vocabulario_medico"))

    def test_rechaza_mensaje_demasiado_largo(self):
        r = validar("Endereza " * 30 + "el tronco.", err())
        self.assertFalse(r.valido)
        self.assertTrue(r.motivo.startswith("demasiado_largo"))

    def test_es_insensible_a_tildes_y_mayusculas(self):
        self.assertEqual(segmentos_mencionados("Sube la MUÑECA"), ("muneca",))
        self.assertEqual(lados_mencionados("Brazo IZQUIERDO"),
                         (Lado.IZQUIERDO,))

    def test_m2_sin_afirmaciones_no_soportadas(self):
        self.assertEqual(afirmaciones_no_soportadas("Endereza el tronco.", err()), ())
        self.assertNotEqual(
            afirmaciones_no_soportadas("Endereza el tronco y el cuello.", err()), ())


class TestValidadorDireccion(unittest.TestCase):
    def test_acepta_la_direccion_pedida(self):
        e = err("profundidad", "rodilla", Lado.BILATERAL,
                direccion=Direccion.MAS_FLEXION)
        self.assertTrue(validar("Baja más, flexiona las rodillas.", e))

    def test_rechaza_la_direccion_contraria(self):
        e = err("profundidad", "rodilla", Lado.BILATERAL,
                direccion=Direccion.MAS_FLEXION)
        r = validar("Estira las rodillas.", e)
        self.assertFalse(r.valido)
        self.assertEqual(r.motivo, "direccion_contradictoria:menos_flexion")

    def test_la_negacion_invierte_la_direccion(self):
        e = err("cadera_sube", "cadera", Lado.IZQUIERDO, direccion=Direccion.BAJAR)
        self.assertTrue(validar("No subas la cadera izquierda.", e))
        self.assertTrue(validar("Cadera izquierda nivelada, no la subas.", e))
        self.assertFalse(validar("No bajes la cadera izquierda.", e))
        self.assertEqual(direcciones_pedidas("No la subas"), (Direccion.BAJAR,))

    def test_describir_el_error_no_es_pedir_la_direccion(self):
        e = err("cadera_sube", "cadera", Lado.DERECHO, direccion=Direccion.BAJAR)
        self.assertTrue(validar("Baja la cadera derecha, la estás subiendo.", e))
        e = err("profundidad", "rodilla", Lado.IZQUIERDO,
                direccion=Direccion.MAS_FLEXION)
        self.assertTrue(validar("Baja más, la rodilla izquierda no se flexiona.", e))

    def test_sin_direccion_no_se_comprueba(self):
        e = err("profundidad", "rodilla", Lado.BILATERAL)
        self.assertTrue(validar("Estira las rodillas.", e))


class TestLLMLocalSinServidor(unittest.TestCase):
    """Lo que se puede comprobar del verbalizador LLM sin modelo: qué se le
    envía y qué se hace con su respuesta. La calidad del texto que genera solo
    se mide con un modelo real (EXP-001, T23)."""

    def _error(self, direccion=Direccion.MAS_FLEXION):
        return ErrorTipificado(
            error_id="profundidad_insuficiente_der", segmento="rodilla",
            lado=Lado.DERECHO, severidad=Severidad.ALTA, fase="ascenso",
            repeticion=1, ejercicio_id="marcha_rodillas",
            mensaje_id="profundidad_rodilla", magnitud=30.0,
            direccion=direccion)

    def _llm_que_responde(self, texto):
        llm = VerbalizadorLLMLocal()
        llm._llamar = lambda error: texto
        return llm

    def test_el_prompt_lleva_la_direccion_y_no_la_magnitud(self):
        d = _descripcion_error(self._error())
        self.assertIn("corrección pedida: flexionar más", d)
        self.assertIn("rodilla derecha", d)
        self.assertNotIn("30", d)

    def test_sin_direccion_el_prompt_no_la_menciona(self):
        self.assertNotIn("corrección pedida", _descripcion_error(self._error(None)))

    def test_toda_direccion_tiene_forma_en_espanol_coherente_con_el_validador(self):
        for direccion in Direccion:
            self.assertIn(direccion, DIRECCION_ES)
            self.assertIn(direccion, direcciones_pedidas(DIRECCION_ES[direccion]))

    def test_respuesta_que_contradice_la_direccion_cae_a_plantilla(self):
        m = self._llm_que_responde("Estira la rodilla derecha.").verbalizar(self._error())
        self.assertTrue(m.fallback)
        self.assertEqual(m.motivo_rechazo, "direccion_contradictoria:menos_flexion")
        self.assertTrue(validar(m.texto, self._error()))

    def test_respuesta_en_la_direccion_pedida_se_acepta(self):
        m = self._llm_que_responde("Baja más y flexiona la rodilla derecha.").verbalizar(
            self._error())
        self.assertFalse(m.fallback)
        self.assertEqual(m.texto, "Baja más y flexiona la rodilla derecha.")

    def test_servidor_caido_cae_a_plantilla(self):
        llm = VerbalizadorLLMLocal(url="http://127.0.0.1:9/no-hay-servidor",
                                   timeout_ms=200)
        m = llm.verbalizar(self._error())
        self.assertTrue(m.fallback)
        self.assertTrue(m.motivo_rechazo.startswith("fallo_backend"))


class _OllamaFalso:
    """Servidor HTTP local que imita `POST /api/chat` de Ollama."""

    def __init__(self, contenido='{"mensaje": "Baja más y flexiona la rodilla derecha."}',
                 demora_s=0.0):
        falso = self
        self.pedidos = []

        class Manejador(BaseHTTPRequestHandler):
            def do_POST(self):                             # noqa: N802
                cuerpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                falso.pedidos.append((self.path, cuerpo))
                time.sleep(demora_s)
                resp = json.dumps({
                    "model": cuerpo["model"], "done": True,
                    "message": {"role": "assistant", "content": contenido},
                    "total_duration": 5_000_000, "eval_count": 12,
                    "eval_duration": 3_000_000}).encode("utf-8")
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)
                except OSError:                            # el cliente ya se fue
                    pass

            def do_GET(self):                              # noqa: N802
                resp = json.dumps({"models": [{"name": n} for n in falso.modelos]}).encode("utf-8")
                self.send_response(200 if self.path == "/api/tags" else 404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)

            def log_message(self, *a):                     # silencio en los tests
                pass

        self.modelos = ["modelo-de-prueba", "otro:latest"]
        self.servidor = HTTPServer(("127.0.0.1", 0), Manejador)
        self.url = f"http://127.0.0.1:{self.servidor.server_port}/api/chat"
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()

    def cerrar(self):
        self.servidor.shutdown()
        self.servidor.server_close()


class TestLLMModoOllama(unittest.TestCase):
    """El modo Ollama contra un servidor falso: qué se pide y qué se hace con
    la respuesta. La latencia y la calidad solo se miden con un modelo real."""

    def _error(self):
        return ErrorTipificado(
            error_id="profundidad_insuficiente_der", segmento="rodilla",
            lado=Lado.DERECHO, severidad=Severidad.ALTA, fase="ascenso",
            repeticion=1, ejercicio_id="zancada_atras_der",
            mensaje_id="profundidad_rodilla", direccion=Direccion.MAS_FLEXION)

    def _llm(self, falso, **kw):
        self.addCleanup(falso.cerrar)
        kw.setdefault("timeout_ms", 2000)
        return VerbalizadorLLMLocal(url=falso.url, modelo="modelo-de-prueba",
                                    backend=BACKEND_OLLAMA, **kw)

    def test_url_por_defecto_segun_el_backend(self):
        self.assertEqual(VerbalizadorLLMLocal().url, URL_LLAMA)
        self.assertEqual(VerbalizadorLLMLocal(backend=BACKEND_OLLAMA).url, URL_OLLAMA)
        with self.assertRaises(ValueError):
            VerbalizadorLLMLocal(backend="otro")

    def test_pide_esquema_sin_pensar_y_sin_flujo(self):
        falso = _OllamaFalso()
        m = self._llm(falso).verbalizar(self._error())
        self.assertFalse(m.fallback)
        self.assertEqual(m.texto, "Baja más y flexiona la rodilla derecha.")
        ruta, cuerpo = falso.pedidos[0]
        self.assertEqual(ruta, "/api/chat")
        self.assertEqual(cuerpo["model"], "modelo-de-prueba")
        self.assertEqual(cuerpo["format"], ESQUEMA_SALIDA)
        self.assertIs(cuerpo["think"], False)
        self.assertIs(cuerpo["stream"], False)
        self.assertIn("num_predict", cuerpo["options"])
        # el modelo solo recibe el error tipificado, nunca ángulos ni frames
        self.assertEqual([x["role"] for x in cuerpo["messages"]], ["system", "user"])
        self.assertIn("rodilla derecha", cuerpo["messages"][1]["content"])

    def test_el_modo_llama_server_no_cambia(self):
        cuerpo = VerbalizadorLLMLocal()._cuerpo(self._error())
        self.assertEqual(cuerpo["response_format"]["type"], "json_schema")
        self.assertNotIn("format", cuerpo)
        self.assertNotIn("think", cuerpo)

    def test_sin_restriccion_no_envia_esquema(self):
        cuerpo = VerbalizadorLLMLocal(backend=BACKEND_OLLAMA,
                                      restringido=False)._cuerpo(self._error())
        self.assertNotIn("format", cuerpo)

    def test_respuesta_rechazada_por_el_validador_cae_a_plantilla(self):
        llm = self._llm(_OllamaFalso('{"mensaje": "Estira la rodilla derecha."}'))
        m = llm.verbalizar(self._error())
        self.assertTrue(m.fallback)
        self.assertTrue(validar(m.texto, self._error()))
        self.assertEqual(llm.caidas, {"direccion_contradictoria": 1})

    def test_respuesta_que_no_es_json_cae_a_plantilla(self):
        llm = self._llm(_OllamaFalso("Baja más."))
        m = llm.verbalizar(self._error())
        self.assertTrue(m.fallback)
        self.assertTrue(m.motivo_rechazo.startswith("fallo_backend"))

    def test_pasado_el_tiempo_limite_cae_a_plantilla(self):
        llm = self._llm(_OllamaFalso(demora_s=0.6), timeout_ms=100)
        t0 = time.perf_counter()
        m = llm.verbalizar(self._error())
        self.assertLess(time.perf_counter() - t0, 0.5)
        self.assertTrue(m.fallback)
        self.assertEqual(llm.llamadas, 1)
        self.assertEqual(sum(llm.caidas.values()), 1)

    def test_precalentar_no_lanza_sin_servidor(self):
        llm = VerbalizadorLLMLocal(url="http://127.0.0.1:9/api/chat",
                                   backend=BACKEND_OLLAMA)
        self.assertFalse(llm.precalentar(timeout_s=0.2))
        falso = _OllamaFalso()
        self.assertTrue(self._llm(falso).precalentar(timeout_s=2))
        self.assertEqual(falso.pedidos[0][1]["messages"], [])


class TestDefectosSegunElEquipo(unittest.TestCase):
    """Rama feature/mac-flujo: en el Mac va encendido por defecto lo que
    aprovecha ese equipo; en los demás, todo queda como antes. `en_mac` se pasa
    a mano para que el test valga igual en Linux y en el Mac."""

    def _args(self, argv=(), en_mac=False):
        from estela.__main__ import _argumentos
        return _argumentos(list(argv), en_mac=en_mac)

    def test_fuera_del_mac_nada_cambia(self):
        a = self._args()
        self.assertEqual((a.modelo, a.delegado, a.verbalizador, a.entrenadora, a.voz_entrada,
                          a.tiempo_real), ("lite", "cpu", "plantillas", "no", "no", False))

    def test_en_el_mac_va_encendido_lo_que_aprovecha_el_equipo(self):
        from estela import config
        a = self._args(en_mac=True)
        self.assertEqual((a.modelo, a.delegado, a.verbalizador, a.entrenadora, a.voz_entrada),
                         ("heavy", "gpu", "llm", "llm", "si"))
        self.assertEqual((a.llm_modelo, a.llm_timeout_ms),
                         (config.LLM_MODELO, config.LLM_TIMEOUT_MS))
        self.assertEqual((a.entrenadora_modelo, a.entrenadora_timeout_s),
                         (config.ENTRENADORA_MODELO, config.ENTRENADORA_TIMEOUT_S))

    def test_lo_que_se_pide_gana_al_defecto_tambien_en_el_mac(self):
        a = self._args(["--modelo", "lite", "--delegado", "cpu", "--verbalizador", "plantillas",
                        "--entrenadora", "no", "--llm-timeout-ms", "250"], en_mac=True)
        self.assertEqual((a.modelo, a.delegado, a.verbalizador, a.entrenadora, a.llm_timeout_ms),
                         ("lite", "cpu", "plantillas", "no", 250))
        with self.assertRaises(SystemExit):
            self._args(["--delegado", "otro"])

    def test_cada_defecto_es_un_valor_que_la_linea_de_comandos_acepta(self):
        from estela import config
        for en_mac in (False, True):
            d = config.defectos(en_mac)
            self.assertEqual(sorted(d), ["delegado", "entrenadora", "modelo", "verbalizador",
                                         "voz_entrada", "voz_entrada_modo"])
            argv = [x for k, v in d.items() for x in (f"--{k.replace('_', '-')}", v)]
            a = self._args(argv, en_mac=not en_mac)
            self.assertEqual({k: getattr(a, k) for k in d}, d)


class TestArranqueDelLLM(unittest.TestCase):
    """Con el LLM encendido por defecto, el arranque comprueba que Ollama
    responde y tiene el modelo; si no, se sigue con plantillas."""

    def _args(self, *extra):
        from estela.__main__ import _argumentos
        return _argumentos(["--verbalizador", "llm", *extra], en_mac=False)

    def test_modelo_disponible(self):
        from estela.adaptadores.llm.ollama import modelo_disponible
        falso = _OllamaFalso()
        self.addCleanup(falso.cerrar)
        self.assertEqual(modelo_disponible("modelo-de-prueba", falso.url), (True, ""))
        self.assertEqual(modelo_disponible("otro", falso.url), (True, ""))      # «otro:latest»
        listo, motivo = modelo_disponible("no-esta", falso.url)
        self.assertFalse(listo)
        self.assertIn("ollama pull no-esta", motivo)
        listo, motivo = modelo_disponible("m", "http://127.0.0.1:9/api/chat", timeout_s=0.3)
        self.assertFalse(listo)
        self.assertIn("no responde", motivo)

    def test_sin_ollama_o_sin_el_modelo_se_usan_plantillas(self):
        from estela.__main__ import _crear_verbalizador
        self.assertIsNone(_crear_verbalizador(
            self._args("--llm-url", "http://127.0.0.1:9/api/chat")))
        falso = _OllamaFalso()
        self.addCleanup(falso.cerrar)
        self.assertIsNone(_crear_verbalizador(
            self._args("--llm-url", falso.url, "--llm-modelo", "no-esta")))

    def test_con_ollama_y_el_modelo_se_crea_el_verbalizador(self):
        from estela.__main__ import _argumentos, _crear_verbalizador
        falso = _OllamaFalso()
        self.addCleanup(falso.cerrar)
        v = _crear_verbalizador(self._args("--llm-url", falso.url, "--llm-modelo",
                                           "modelo-de-prueba", "--llm-timeout-ms", "300"))
        self.assertEqual((v.modelo, v.timeout_ms, v.backend),
                         ("modelo-de-prueba", 300, BACKEND_OLLAMA))
        self.assertIsNone(_crear_verbalizador(_argumentos([], en_mac=False)))   # plantillas

    def test_la_entrenadora_sin_modelo_disponible_sigue_con_plantilla(self):
        from estela.__main__ import _argumentos, _crear_entrenadora
        from tests.test_sesion import VozFalsa
        a = _argumentos(["--entrenadora", "llm", "--entrenadora-url",
                         "http://127.0.0.1:9/api/chat"], en_mac=False)
        en_vivo, retencion_ms = _crear_entrenadora(a, {}, VozFalsa())
        self.assertIsNone(en_vivo.entrenadora.generador)      # responde con plantillas
        self.assertGreater(retencion_ms, 0)
        self.assertEqual(_crear_entrenadora(_argumentos([], en_mac=False), {}, VozFalsa()),
                         (None, 0))


class TestArranqueDeLaVozDeEntrada(unittest.TestCase):
    def test_apagada_no_crea_nada(self):
        from estela.__main__ import _argumentos, _crear_escucha
        self.assertIsNone(_crear_escucha(_argumentos([], en_mac=False), None, {}, None))

    def test_sin_microfono_o_sin_modelo_la_sesion_sigue_sin_ordenes_de_voz(self):
        from unittest import mock
        from estela.__main__ import _argumentos, _crear_escucha
        a = _argumentos(["--voz-entrada", "si"], en_mac=False)
        mic = "estela.adaptadores.voz_entrada.microfono.hay_microfono"
        with mock.patch(mic, return_value=(False, "no hay ningún micrófono conectado")):
            with self.assertLogs("estela", level="WARNING") as reg:
                self.assertIsNone(_crear_escucha(a, None, {}, None))
        self.assertIn("micrófono", reg.output[0])
        with mock.patch(mic, return_value=(True, "")), \
                mock.patch("estela.config.modelo_voz_entrada",
                           return_value=__import__("pathlib").Path("/no/existe/ggml-small.bin")):
            with self.assertLogs("estela", level="WARNING") as reg:
                self.assertIsNone(_crear_escucha(a, None, {}, None))
        self.assertIn("descargar_modelos.py --voz-entrada", reg.output[0])

    def test_el_reconocedor_quita_las_anotaciones_de_audio_sin_habla(self):
        from estela.adaptadores.voz_entrada.reconocedor import limpiar
        self.assertEqual(limpiar(" [BLANK_AUDIO] "), "")
        self.assertEqual(limpiar("(música) Pausa. *ruido*"), "Pausa.")
        self.assertEqual(limpiar("¿Cómo   voy?"), "¿Cómo voy?")


class TestPlantillas(unittest.TestCase):
    def setUp(self):
        self.v = VerbalizadorPlantillas()

    def test_concordancia_de_genero(self):
        e = err("valgo_rodilla_izq", "rodilla", Lado.IZQUIERDO,
                mensaje_id="valgo_rodilla")
        self.assertIn("izquierda", self.v.verbalizar(e).texto)
        e2 = err("brazo_bajo", "brazo", Lado.IZQUIERDO)
        self.assertIn("izquierdo", self.v.verbalizar(e2).texto)

    def test_determinismo(self):
        e = err()
        textos = {self.v.verbalizar(e).texto for _ in range(10)}
        self.assertEqual(len(textos), 1)

    def test_varia_entre_repeticiones(self):
        e1 = err(rep=1)
        e2 = err(rep=2)
        # No se exige que difieran siempre (depende del nº de variantes), pero
        # sí que el mecanismo esté activo cuando hay más de una variante.
        variantes = self.v._variantes(e1)
        if len(variantes) > 1:
            self.assertNotEqual(self.v.verbalizar(e1).texto,
                                self.v.verbalizar(e2).texto)

    def test_error_desconocido_cae_al_generico_sin_romper(self):
        e = err(error_id="error_que_no_existe", segmento="cadera",
                lado=Lado.BILATERAL)
        m = self.v.verbalizar(e)
        self.assertTrue(m.texto)
        self.assertTrue(validar(m.texto, e))
        self.assertTrue(m.texto.endswith("cadera."), m.texto)

    def test_el_generico_nombra_el_lado_cuando_el_contrato_lo_trae(self):
        # El respaldo es el último recurso: si omite el lado, el sistema dice
        # una frase que su propio validador rechaza (lado_omitido).
        for segmento, lado, esperado in (
                ("rodilla", Lado.IZQUIERDO, "izquierda"),
                ("codo", Lado.DERECHO, "derecho")):
            for sev in Severidad:
                e = err(error_id="error_que_no_existe", segmento=segmento,
                        lado=lado, severidad=sev)
                m = self.v.verbalizar(e)
                self.assertIn(esperado, m.texto)
                self.assertTrue(validar(m.texto, e), m.texto)
                self.assertFalse(m.fallback, m.motivo_rechazo)


class TestCoberturaDePlantillas(unittest.TestCase):
    """Regresión clave: toda regla de todo skill debe producir, en las tres
    severidades, un mensaje que pase el validador. Es lo que garantiza que el
    sistema puede hablar siempre sin inventar nada."""

    def test_todas_las_reglas_verbalizan_y_validan(self):
        v = VerbalizadorPlantillas()
        fallos = []
        for skill in SKILLS.values():
            for regla in skill.reglas:
                # Cada dirección que la regla puede emitir, o ninguna: la
                # plantilla no debe contradecirla.
                direcciones = list(dict.fromkeys(regla.direcciones.values())) or [None]
                for sev, rep, direccion in itertools.product(
                        Severidad, (1, 2, 3), direcciones):
                    e = ErrorTipificado(
                        error_id=regla.error_id,
                        mensaje_id=regla.mensaje_id or regla.error_id,
                        segmento=regla.segmento, lado=regla.lado,
                        severidad=sev, fase="x", repeticion=rep,
                        ejercicio_id=skill.skill_id, direccion=direccion)
                    m = v.verbalizar(e)
                    if m.fallback:
                        fallos.append(
                            f"{skill.skill_id}/{regla.error_id}/{sev.value}"
                            f" -> {m.motivo_rechazo}")
                    r = validar(m.texto, e)
                    if not r.valido:
                        fallos.append(
                            f"{skill.skill_id}/{regla.error_id}/{sev.value}"
                            f" -> {r.motivo} :: {m.texto}")
        self.assertEqual(fallos, [], "\n".join(fallos))


if __name__ == "__main__":
    unittest.main()
