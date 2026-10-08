import itertools
import unittest

from feedback.contrato import Direccion, ErrorTipificado, Lado, Severidad
from feedback.motor.skill import cargar_skills, directorio_skills
from feedback.verbalizador.llm_local import (
    VerbalizadorLLMLocal, _descripcion_error,
)
from feedback.verbalizador.plantillas import (
    DIRECCION_ES, VerbalizadorPlantillas,
)
from feedback.verbalizador.validador import (
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
            repeticion=1, ejercicio_id="zancada_atras_izq",
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
