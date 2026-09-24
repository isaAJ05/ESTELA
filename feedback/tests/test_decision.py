import unittest

from feedback.contrato import (
    ErrorTipificado, Lado, Observacion, Silencio,
    MOTIVO_CONFIANZA_BAJA, MOTIVO_EVIDENCIA_INSUFICIENTE,
    MOTIVO_FASE_SILENCIADA, MOTIVO_PLANO_NO_OBSERVABLE, MOTIVO_REFRACTARIO,
)
from feedback.motor.decision import MotorDecision
from feedback.motor.skill import cargar_skills, directorio_skills

SKILLS = cargar_skills(directorio_skills())


def obs(t_ms, rep, fase="descenso", tronco=60.0, conf=1.0, orientacion=90.0,
        **extra):
    angulos = {"tronco_inclinacion": tronco}
    angulos.update(extra.pop("angulos", {}))
    confianza = {k: conf for k in angulos}
    confianza.update(extra.pop("confianza", {}))
    return Observacion(
        t_ms=t_ms, ejercicio_id="sentadilla", angulos=angulos,
        confianza=confianza, fase=fase, repeticion=rep,
        orientacion=orientacion, **extra)


class TestAbstencion(unittest.TestCase):
    def setUp(self):
        self.motor = MotorDecision(SKILLS["sentadilla"])

    def test_confianza_baja_no_dispara_nunca(self):
        for rep in range(1, 6):
            d = self.motor.observar(obs(rep * 1000, rep, conf=0.2))
            self.assertIsInstance(d, Silencio)
            self.assertEqual(d.motivo, MOTIVO_CONFIANZA_BAJA)

    def test_plano_no_observable_no_dispara(self):
        # regla de tronco es sagital (ideal 90); sujeto de frente (0) fuera de
        # la tolerancia de 30 grados
        for rep in range(1, 6):
            d = self.motor.observar(obs(rep * 1000, rep, orientacion=0.0))
            self.assertIsInstance(d, Silencio)
            self.assertEqual(d.motivo, MOTIVO_PLANO_NO_OBSERVABLE)

    def test_sin_orientacion_la_salvaguarda_esta_desactivada(self):
        d1 = self.motor.observar(obs(1000, 1, orientacion=None))
        d2 = self.motor.observar(obs(2000, 2, orientacion=None))
        self.assertIsInstance(d2, ErrorTipificado)
        self.assertEqual(d2.error_id, "tronco_muy_inclinado")


class TestEvidenciaYSilencio(unittest.TestCase):
    def setUp(self):
        self.motor = MotorDecision(SKILLS["sentadilla"])

    def test_una_sola_repeticion_no_basta(self):
        d = self.motor.observar(obs(1000, 1))
        self.assertIsInstance(d, Silencio)
        self.assertEqual(d.motivo, MOTIVO_EVIDENCIA_INSUFICIENTE)

    def test_dos_repeticiones_consecutivas_disparan(self):
        self.motor.observar(obs(1000, 1))
        d = self.motor.observar(obs(2000, 2))
        self.assertIsInstance(d, ErrorTipificado)
        self.assertEqual(d.error_id, "tronco_muy_inclinado")
        self.assertEqual(d.lado, Lado.NA)

    def test_periodo_refractario_impide_repetir_de_inmediato(self):
        self.motor.observar(obs(1000, 1))
        self.motor.observar(obs(2000, 2))
        d = self.motor.observar(obs(2500, 3))
        self.assertIsInstance(d, Silencio)
        self.assertEqual(d.motivo, MOTIVO_REFRACTARIO)

    def test_fase_silenciada(self):
        m = MotorDecision(SKILLS["sentadilla"])
        m.observar(obs(1000, 1, fase="fondo"))
        d = m.observar(obs(2000, 2, fase="fondo"))
        self.assertIsInstance(d, Silencio)
        self.assertEqual(d.motivo, MOTIVO_FASE_SILENCIADA)

    def test_evidencia_se_reinicia_si_el_error_desaparece(self):
        self.motor.observar(obs(1000, 1))
        self.motor.observar(obs(2000, 2, tronco=10.0))   # sin error
        d = self.motor.observar(obs(3000, 3))
        self.assertIsInstance(d, Silencio)
        self.assertEqual(d.motivo, MOTIVO_EVIDENCIA_INSUFICIENTE)

    def test_desvanecimiento_corta_tras_max_emisiones(self):
        m = MotorDecision(SKILLS["sentadilla"])
        emitidos = 0
        for rep in range(1, 200):
            d = m.observar(obs(rep * 60000, rep))   # separación amplia
            if isinstance(d, ErrorTipificado):
                emitidos += 1
        self.assertEqual(
            emitidos, SKILLS["sentadilla"].politica.max_emisiones_mismo_error)


class TestPrioridadYDeterminismo(unittest.TestCase):
    def _obs_con_dos_errores(self, t, rep):
        return Observacion(
            t_ms=t, ejercicio_id="sentadilla",
            angulos={"tronco_inclinacion": 60.0},
            distancias={"valgo_rodilla_izq": 0.30},
            confianza={"tronco_inclinacion": 1.0, "valgo_rodilla_izq": 1.0},
            fase="descenso", repeticion=rep, orientacion=None)

    def test_se_elige_una_sola_prioridad_la_mas_alta(self):
        m = MotorDecision(SKILLS["sentadilla"])
        m.observar(self._obs_con_dos_errores(1000, 1))
        d = m.observar(self._obs_con_dos_errores(2000, 2))
        self.assertIsInstance(d, ErrorTipificado)
        # prioridad 1 = tronco, prioridad 2 = valgo izquierdo
        self.assertEqual(d.error_id, "tronco_muy_inclinado")

    def test_determinismo_diez_ejecuciones_identicas(self):
        salidas = []
        for _ in range(10):
            m = MotorDecision(SKILLS["sentadilla"])
            m.observar(self._obs_con_dos_errores(1000, 1))
            d = m.observar(self._obs_con_dos_errores(2000, 2))
            salidas.append((d.error_id, d.lado, d.severidad, d.magnitud))
        self.assertEqual(len(set(salidas)), 1)

    def test_severidad_crece_con_el_exceso(self):
        def severidad(tronco):
            m = MotorDecision(SKILLS["sentadilla"])
            m.observar(obs(1000, 1, tronco=tronco, orientacion=None))
            return m.observar(obs(2000, 2, tronco=tronco,
                                  orientacion=None)).severidad.value
        self.assertEqual(severidad(50.0), "leve")
        self.assertEqual(severidad(58.0), "moderada")
        self.assertEqual(severidad(70.0), "alta")


class TestAgregados(unittest.TestCase):
    def test_min_por_repeticion_se_reinicia_en_cada_repeticion(self):
        m = MotorDecision(SKILLS["sentadilla"])
        # rep 1: rodilla baja hasta 80 -> profundidad correcta
        for t, ang in ((0, 170.0), (100, 120.0), (200, 80.0)):
            m.observar(Observacion(t_ms=t, ejercicio_id="sentadilla",
                                   angulos={"rodilla_media": ang},
                                   confianza={"rodilla_media": 1.0},
                                   fase="descenso", repeticion=1))
        d = m.observar(Observacion(t_ms=300, ejercicio_id="sentadilla",
                                   angulos={"rodilla_media": 120.0},
                                   confianza={"rodilla_media": 1.0},
                                   fase="ascenso", repeticion=1))
        self.assertIsInstance(d, Silencio)
        # rep 2: solo baja hasta 130 -> profundidad insuficiente
        for t, ang in ((400, 170.0), (500, 130.0)):
            m.observar(Observacion(t_ms=t, ejercicio_id="sentadilla",
                                   angulos={"rodilla_media": ang},
                                   confianza={"rodilla_media": 1.0},
                                   fase="descenso", repeticion=2))
        d = m.observar(Observacion(t_ms=600, ejercicio_id="sentadilla",
                                   angulos={"rodilla_media": 140.0},
                                   confianza={"rodilla_media": 1.0},
                                   fase="ascenso", repeticion=2))
        self.assertIsInstance(d, Silencio)  # falta evidencia (1 repeticion)


class TestContratoDeEntrada(unittest.TestCase):
    def test_observacion_de_otro_ejercicio_es_error_de_programacion(self):
        m = MotorDecision(SKILLS["sentadilla"])
        with self.assertRaises(ValueError):
            m.observar(Observacion(t_ms=0, ejercicio_id="jumping_jacks",
                                   angulos={}, confianza={}))


if __name__ == "__main__":
    unittest.main()
