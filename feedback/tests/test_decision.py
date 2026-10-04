import os
import unittest

from feedback.contrato import (
    ErrorTipificado, Lado, Observacion, Refuerzo, Silencio,
    MOTIVO_CONFIANZA_BAJA, MOTIVO_EVIDENCIA_INSUFICIENTE,
    MOTIVO_FASE_SILENCIADA, MOTIVO_PLANO_NO_OBSERVABLE, MOTIVO_REFRACTARIO,
)
from feedback.motor.decision import MotorDecision
from feedback.motor.skill import cargar_skill, cargar_skills, directorio_skills

SKILLS = cargar_skills(directorio_skills())
#: Los tests de mecánica del motor (abstención, evidencia, prioridad, refuerzo)
#: usan como banco de pruebas el skill retirado de sentadilla (ADR-005): sus
#: reglas cubren todos esos casos y sus umbrales quedan fijos. No está en el
#: catálogo; las reglas de los ejercicios actuales se prueban en TestSkillsActuales.
SKILLS["sentadilla"] = cargar_skill(
    os.path.join(directorio_skills(), "retirados", "sentadilla.json"))


def obs(t_ms, rep, fase="descenso", tronco=60.0, conf=1.0, orientacion=90.0,
        ejercicio="sentadilla", **extra):
    angulos = {"tronco_inclinacion": tronco}
    angulos.update(extra.pop("angulos", {}))
    confianza = {k: conf for k in angulos}
    confianza.update(extra.pop("confianza", {}))
    return Observacion(
        t_ms=t_ms, ejercicio_id=ejercicio, angulos=angulos,
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

    def test_repeticion_no_evaluable_no_rompe_la_cadena(self):
        self.motor.observar(obs(1000, 1))
        self.motor.observar(obs(2000, 2, conf=0.1))      # no se pudo mirar
        d = self.motor.observar(obs(3000, 3))
        self.assertIsInstance(d, ErrorTipificado)

    def test_regla_de_un_lado_en_ejercicio_alterno_acumula_evidencia(self):
        """En la marcha, la regla de la rodilla izquierda solo se comprueba en
        las repeticiones de esa pierna (1, 3, 5…). Antes la cadena se rompía
        siempre y la regla no hablaba nunca."""
        m = MotorDecision(SKILLS["marcha_rodillas"])
        dichos = []
        for rep in range(1, 9):
            izq = rep % 2 == 1
            angulos = {"cadera_izq": 140.0 if izq else 170.0,
                       "cadera_der": 170.0 if izq else 100.0,
                       "tronco_inclinacion": 5.0}
            d = m.observar(Observacion(
                t_ms=rep * 3000, ejercicio_id="marcha_rodillas", angulos=angulos,
                confianza={k: 1.0 for k in angulos},
                fase="apoyo_der" if izq else "apoyo_izq", repeticion=rep))
            if isinstance(d, ErrorTipificado):
                dichos.append((rep, d.error_id, d.lado))
        # repeticiones_evidencia = 3: la tercera elevación izquierda es la 5.
        self.assertEqual(dichos[0], (5, "rodilla_izq_baja", Lado.IZQUIERDO))

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


ZANCADA = "zancada_atras_izq"


def obs_z(t_ms, rep, **kw):
    """Observación de la zancada: en «descenso» la única regla aplicable es la
    del tronco, que de perfil siempre se puede comprobar."""
    return obs(t_ms, rep, ejercicio=ZANCADA, **kw)


class TestRefuerzo(unittest.TestCase):
    """`zancada_atras_izq` tiene politica_refuerzo.activa=true,
    repeticiones_limpias=3, refractario_ms=15000. No se usa la sentadilla
    retirada: sus reglas de valgo son frontales y de perfil nunca se pueden
    comprobar, así que con ADR-006 §2.9 no felicita nunca (es correcto)."""

    def setUp(self):
        self.motor = MotorDecision(SKILLS[ZANCADA])

    def test_racha_limpia_dispara_refuerzo(self):
        for rep in (1, 2, 3):
            d = self.motor.observar(obs_z(rep * 1000, rep, tronco=20.0))
            self.assertIsInstance(d, Silencio)
        # al empezar la repeticion 4 se cierra la racha de 3 limpias.
        d = self.motor.observar(obs_z(4000, 4, tronco=20.0))
        self.assertIsInstance(d, Refuerzo)
        self.assertEqual(d.racha, 3)
        self.assertEqual(d.ejercicio_id, ZANCADA)

    def test_una_repeticion_sucia_rompe_la_racha(self):
        self.motor.observar(obs_z(1000, 1, tronco=20.0))
        self.motor.observar(obs_z(2000, 2, tronco=20.0))
        self.motor.observar(obs_z(3000, 3, tronco=60.0))  # error: rompe la racha
        self.motor.observar(obs_z(4000, 4, tronco=20.0))
        self.motor.observar(obs_z(5000, 5, tronco=20.0))
        self.motor.observar(obs_z(6000, 6, tronco=20.0))
        d = self.motor.observar(obs_z(7000, 7, tronco=20.0))
        self.assertIsInstance(d, Refuerzo)
        self.assertEqual(d.racha, 3)  # solo cuenta desde la repeticion 4

    def test_repeticion_no_evaluable_no_cuenta_ni_rompe(self):
        self.motor.observar(obs_z(1000, 1, tronco=20.0))
        self.motor.observar(obs_z(2000, 2, tronco=20.0))
        # repeticion 3 totalmente ciega (confianza baja en todo): el motor no
        # pudo ver nada, así que no cuenta como limpia ni rompe la racha.
        d_ciega = self.motor.observar(obs_z(2500, 3, tronco=20.0, conf=0.1))
        self.assertIsInstance(d_ciega, Silencio)
        d_tras_ciega = self.motor.observar(obs_z(3000, 4, tronco=20.0))
        self.assertIsInstance(d_tras_ciega, Silencio)  # racha sigue en 2
        d = self.motor.observar(obs_z(4000, 5, tronco=20.0))
        self.assertIsInstance(d, Refuerzo)
        self.assertEqual(d.racha, 3)

    def test_refractario_impide_dos_refuerzos_seguidos(self):
        for rep in range(1, 4):
            self.motor.observar(obs_z(rep * 1000, rep, tronco=20.0))
        d1 = self.motor.observar(obs_z(4000, 4, tronco=20.0))
        self.assertIsInstance(d1, Refuerzo)  # racha=3

        d2 = None
        for rep, t in ((5, 5000), (6, 6000), (7, 7000)):
            d2 = self.motor.observar(obs_z(t, rep, tronco=20.0))
        # al cerrar la repeticion 6 la racha llega a 6 (multiplo de 3), pero
        # pasaron solo 3000 ms desde el ultimo refuerzo (refractario 15000).
        self.assertIsInstance(d2, Silencio)

    def test_no_felicita_si_una_regla_aplicable_no_se_pudo_comprobar(self):
        """La rodilla delantera está ocluida en todas las repeticiones: no se
        corrige (no se ve) y tampoco se felicita (no se ha comprobado)."""
        def repeticion(rep, conf_rodilla):
            t = rep * 1000
            bajada = self.motor.observar(obs_z(t, rep, tronco=10.0))
            subida = self.motor.observar(Observacion(
                t_ms=t + 500, ejercicio_id=ZANCADA,
                angulos={"tronco_inclinacion": 10.0, "rodilla_der": 90.0},
                confianza={"tronco_inclinacion": 1.0, "rodilla_der": conf_rodilla},
                fase="ascenso", repeticion=rep, orientacion=90.0))
            return [bajada, subida]
        dichos = [d for r in range(1, 9) for d in repeticion(r, 0.2)]
        self.assertFalse(any(isinstance(d, (Refuerzo, ErrorTipificado)) for d in dichos))
        # La misma ejecución con la rodilla visible sí se felicita.
        self.motor = MotorDecision(SKILLS[ZANCADA])
        dichos = [d for r in range(1, 6) for d in repeticion(r, 1.0)]
        self.assertTrue(any(isinstance(d, Refuerzo) for d in dichos))

    def test_no_felicita_si_la_orientacion_impide_comprobar_una_regla(self):
        m = MotorDecision(SKILLS["abduccion_cadera_izq"])
        dichos = []
        for rep in range(1, 9):
            for fase in ("subida", "arriba"):
                angulos = {"inclinacion_lateral": 0.0, "oblicuidad_pelvis": 0.0}
                dichos.append(m.observar(Observacion(
                    t_ms=rep * 1000, ejercicio_id="abduccion_cadera_izq",
                    angulos=angulos, confianza={k: 1.0 for k in angulos},
                    fase=fase, repeticion=rep, orientacion=90.0)))
        self.assertFalse(any(isinstance(d, Refuerzo) for d in dichos))

    def test_desactivado_por_defecto_en_un_skill_sin_politica(self):
        # jumping_jacks sí tiene politica_refuerzo propia; comprobamos que un
        # skill cargado desde un dict sin la clave queda con activa=False.
        from feedback.motor.skill import skill_desde_dict
        base = {
            "skill_id": "x", "nombre": "x", "version": "0.1.0",
            "reglas": [{
                "error_id": "e", "medida": {"tipo": "angulo", "nombre": "a"},
                "condicion": {"op": ">", "umbral": 1}, "segmento": "tronco",
                "lado": "na", "plano": "cualquiera", "prioridad": 1,
            }],
        }
        skill = skill_desde_dict(base)
        self.assertFalse(skill.politica_refuerzo.activa)


class TestSkillsActuales(unittest.TestCase):
    """Reglas de los ejercicios de ADR-005 con observaciones mínimas."""

    def _obs(self, skill_id, t, rep, fase, angulos=None, distancias=None,
             orientacion=None):
        angulos, distancias = angulos or {}, distancias or {}
        return Observacion(
            t_ms=t, ejercicio_id=skill_id, angulos=angulos, distancias=distancias,
            confianza={k: 1.0 for k in list(angulos) + list(distancias)},
            fase=fase, repeticion=rep, orientacion=orientacion)

    def _dos_repeticiones(self, skill_id, **kw):
        m = MotorDecision(SKILLS[skill_id])
        m.observar(self._obs(skill_id, 1000, 1, **kw))
        return m.observar(self._obs(skill_id, 2000, 2, **kw))

    def test_abduccion_tronco_hacia_el_lado_contrario(self):
        for skill_id, incl, error_id, lado in (
                ("abduccion_cadera_izq", -15.0, "tronco_inclinado_der", Lado.DERECHO),
                ("abduccion_cadera_der", 15.0, "tronco_inclinado_izq", Lado.IZQUIERDO)):
            d = self._dos_repeticiones(
                skill_id, fase="arriba", orientacion=0.0,
                angulos={"inclinacion_lateral": incl, "oblicuidad_pelvis": 0.0})
            self.assertIsInstance(d, ErrorTipificado, skill_id)
            self.assertEqual((d.error_id, d.lado), (error_id, lado))

    def test_abduccion_la_compensacion_del_tronco_va_antes_que_la_cadera(self):
        d = self._dos_repeticiones(
            "abduccion_cadera_izq", fase="arriba", orientacion=0.0,
            angulos={"inclinacion_lateral": -15.0, "oblicuidad_pelvis": 10.0})
        self.assertEqual(d.error_id, "tronco_inclinado_der")

    def test_abduccion_solo_corrige_la_cadera_de_la_pierna_que_sube(self):
        d = self._dos_repeticiones(
            "abduccion_cadera_izq", fase="arriba", orientacion=0.0,
            angulos={"inclinacion_lateral": 0.0, "oblicuidad_pelvis": 10.0})
        self.assertEqual((d.error_id, d.lado), ("cadera_izq_sube", Lado.IZQUIERDO))
        # En la serie de la pierna derecha, que la izquierda quede más alta no
        # es «subir la cadera derecha».
        d = self._dos_repeticiones(
            "abduccion_cadera_der", fase="arriba", orientacion=0.0,
            angulos={"inclinacion_lateral": 0.0, "oblicuidad_pelvis": 10.0})
        self.assertIsInstance(d, Silencio)

    def test_abduccion_de_perfil_no_es_observable(self):
        d = self._dos_repeticiones(
            "abduccion_cadera_izq", fase="arriba", orientacion=90.0,
            angulos={"inclinacion_lateral": -15.0})
        self.assertIsInstance(d, Silencio)
        self.assertEqual(d.motivo, MOTIVO_PLANO_NO_OBSERVABLE)

    def test_zancada_mide_la_rodilla_delantera(self):
        for skill_id, rodilla, lado in (("zancada_atras_izq", "rodilla_der", Lado.DERECHO),
                                        ("zancada_atras_der", "rodilla_izq", Lado.IZQUIERDO)):
            d = self._dos_repeticiones(skill_id, fase="ascenso", orientacion=90.0,
                                       angulos={rodilla: 140.0, "tronco_inclinacion": 10.0})
            self.assertIsInstance(d, ErrorTipificado, skill_id)
            self.assertEqual(d.lado, lado)
            self.assertTrue(d.error_id.startswith("profundidad_insuficiente"))

    def test_plancha_cadera_hundida_solo_en_mantenimiento(self):
        d = self._dos_repeticiones("plancha", fase="mantenimiento", orientacion=90.0,
                                   distancias={"alineacion_cadera": 0.2},
                                   angulos={"cabeza_adelantada": 5.0})
        self.assertEqual((d.error_id, d.segmento), ("cadera_hundida", "cadera"))
        d = self._dos_repeticiones("plancha", fase="preparacion", orientacion=90.0,
                                   distancias={"alineacion_cadera": 0.2})
        self.assertIsInstance(d, Silencio)

    def test_plancha_cadera_elevada_y_cabeza(self):
        d = self._dos_repeticiones("plancha", fase="mantenimiento", orientacion=90.0,
                                   distancias={"alineacion_cadera": -0.25})
        self.assertEqual(d.error_id, "cadera_elevada")
        d = self._dos_repeticiones("plancha", fase="mantenimiento", orientacion=90.0,
                                   distancias={"alineacion_cadera": 0.0},
                                   angulos={"cabeza_adelantada": 45.0})
        self.assertEqual((d.error_id, d.segmento), ("cabeza_desalineada", "cabeza"))


class TestContratoDeEntrada(unittest.TestCase):
    def test_observacion_de_otro_ejercicio_es_error_de_programacion(self):
        m = MotorDecision(SKILLS["sentadilla"])
        with self.assertRaises(ValueError):
            m.observar(Observacion(t_ms=0, ejercicio_id="jumping_jacks",
                                   angulos={}, confianza={}))


if __name__ == "__main__":
    unittest.main()
