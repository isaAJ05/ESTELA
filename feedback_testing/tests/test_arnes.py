import unittest

from feedback.motor.skill import cargar_skills, directorio_skills
from feedback.verbalizador.plantillas import VerbalizadorPlantillas
from feedback_testing.generador_episodios import construir_episodio, generar_banco
from feedback_testing.metricas import percentil
from feedback_testing.runner import ejecutar_episodio

SKILLS = cargar_skills(directorio_skills())
BANCO = generar_banco(SKILLS)


class TestBanco(unittest.TestCase):
    def test_el_banco_es_determinista(self):
        otro = generar_banco(SKILLS)
        self.assertEqual([e.episodio_id for e in BANCO],
                         [e.episodio_id for e in otro])
        a = BANCO[0].observaciones[0]
        b = otro[0].observaciones[0]
        self.assertEqual(a.angulos, b.angulos)

    def test_incluye_ejecuciones_correctas(self):
        correctos = [e for e in BANCO if e.condicion == "correcto"]
        self.assertEqual(len(correctos), 3 * len(SKILLS))

    def test_cubre_todas_las_reglas(self):
        cubiertos = {e.error_referencia for e in BANCO if e.error_referencia}
        todas = {r.error_id for s in SKILLS.values() for r in s.reglas}
        self.assertEqual(cubiertos, todas)


class TestComportamientoEsperado(unittest.TestCase):
    def setUp(self):
        self.v = VerbalizadorPlantillas()

    def _ej(self, episodio):
        return ejecutar_episodio(SKILLS[episodio.ejercicio_id], episodio, self.v)

    def test_los_episodios_correctos_no_reciben_correccion(self):
        fallos = [e.episodio_id for e in BANCO
                  if e.condicion == "correcto" and self._ej(e).hubo_mensaje]
        self.assertEqual(fallos, [])

    def test_los_episodios_con_error_senalan_ese_error(self):
        fallos = []
        for e in BANCO:
            if e.condicion != "error":
                continue
            r = self._ej(e)
            if r.primer_error_id != e.error_referencia:
                fallos.append(f"{e.episodio_id} -> {r.primer_error_id}")
        self.assertEqual(fallos, [])

    def test_el_sistema_calla_cuando_la_medida_esta_ocluida(self):
        fallos = [e.episodio_id for e in BANCO
                  if e.condicion == "ocluido" and self._ej(e).hubo_mensaje]
        self.assertEqual(fallos, [])

    def test_el_sistema_calla_cuando_el_plano_no_es_observable(self):
        fallos = [e.episodio_id for e in BANCO
                  if e.condicion == "plano_malo" and self._ej(e).hubo_mensaje]
        self.assertEqual(fallos, [])

    def test_ningun_mensaje_afirma_algo_fuera_del_contrato(self):
        from feedback.verbalizador.validador import afirmaciones_no_soportadas
        fallos = []
        for e in BANCO:
            for m in self._ej(e).mensajes:
                extra = afirmaciones_no_soportadas(m.texto, m.error)
                if extra:
                    fallos.append(f"{m.texto} -> {extra}")
        self.assertEqual(fallos, [])


class TestMetricas(unittest.TestCase):
    def test_percentil(self):
        self.assertAlmostEqual(percentil([1, 2, 3, 4], 50), 2.5)
        self.assertAlmostEqual(percentil([5], 95), 5.0)
        self.assertNotEqual(percentil([], 50), percentil([], 50))  # NaN


if __name__ == "__main__":
    unittest.main()
