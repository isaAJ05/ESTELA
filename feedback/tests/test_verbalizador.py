import unittest

from feedback.contrato import ErrorTipificado, Lado, Severidad
from feedback.motor.skill import cargar_skills, directorio_skills
from feedback.verbalizador.plantillas import VerbalizadorPlantillas
from feedback.verbalizador.validador import (
    afirmaciones_no_soportadas, lados_mencionados, segmentos_mencionados,
    validar,
)

SKILLS = cargar_skills(directorio_skills())


def err(error_id="tronco_muy_inclinado", segmento="tronco", lado=Lado.NA,
        severidad=Severidad.MODERADA, rep=1, mensaje_id=None):
    return ErrorTipificado(
        error_id=error_id, segmento=segmento, lado=lado, severidad=severidad,
        fase="descenso", repeticion=rep, ejercicio_id="sentadilla",
        mensaje_id=mensaje_id if mensaje_id is not None else error_id)


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


class TestCoberturaDePlantillas(unittest.TestCase):
    """Regresión clave: toda regla de todo skill debe producir, en las tres
    severidades, un mensaje que pase el validador. Es lo que garantiza que el
    sistema puede hablar siempre sin inventar nada."""

    def test_todas_las_reglas_verbalizan_y_validan(self):
        v = VerbalizadorPlantillas()
        fallos = []
        for skill in SKILLS.values():
            for regla in skill.reglas:
                for sev in Severidad:
                    for rep in (1, 2, 3):
                        e = ErrorTipificado(
                            error_id=regla.error_id,
                            mensaje_id=regla.mensaje_id or regla.error_id,
                            segmento=regla.segmento, lado=regla.lado,
                            severidad=sev, fase="x", repeticion=rep,
                            ejercicio_id=skill.skill_id)
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
