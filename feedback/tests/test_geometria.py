import math
import unittest

from feedback.contrato import Keypoint, MuestraPose
from feedback.motor import geometria as g


def kp(x, y, z=0.0, v=1.0):
    return Keypoint(x=x, y=y, z=z, visibilidad=v)


class TestPrimitivas(unittest.TestCase):
    def test_angulo_recto(self):
        a = g.angulo_entre((0.0, 1.0), (0.0, 0.0), (1.0, 0.0))
        self.assertAlmostEqual(a, 90.0, places=6)

    def test_angulo_llano(self):
        a = g.angulo_entre((-1.0, 0.0), (0.0, 0.0), (1.0, 0.0))
        self.assertAlmostEqual(a, 180.0, places=6)

    def test_vector_degenerado_devuelve_none(self):
        self.assertIsNone(g.angulo_entre((0.0, 0.0), (0.0, 0.0), (1.0, 0.0)))


class TestMedidas(unittest.TestCase):
    def _cuerpo(self, **kw):
        base = {
            "left_shoulder": kp(-0.2, -0.5), "right_shoulder": kp(0.2, -0.5),
            "left_hip": kp(-0.1, 0.0), "right_hip": kp(0.1, 0.0),
            "left_knee": kp(-0.1, 0.5), "right_knee": kp(0.1, 0.5),
            "left_ankle": kp(-0.1, 1.0), "right_ankle": kp(0.1, 1.0),
            "left_elbow": kp(-0.2, -0.2), "right_elbow": kp(0.2, -0.2),
            "left_wrist": kp(-0.2, 0.1), "right_wrist": kp(0.2, 0.1),
        }
        base.update(kw)
        return base

    def test_escala_corporal_positiva(self):
        self.assertAlmostEqual(g.escala_corporal(self._cuerpo()), 0.5, places=6)

    def test_tronco_vertical_da_cero(self):
        self.assertAlmostEqual(
            g.inclinacion_tronco(self._cuerpo()), 0.0, places=6)

    def test_tronco_inclinado_hacia_delante(self):
        c = self._cuerpo(left_shoulder=kp(-0.2, -0.5, 0.5),
                         right_shoulder=kp(0.2, -0.5, 0.5))
        ang = g.inclinacion_tronco(c)
        self.assertGreater(ang, 30.0)

    def test_valgo_cero_con_pierna_recta(self):
        v = g.desviacion_lateral_rodilla(self._cuerpo(), "izq")
        self.assertAlmostEqual(v, 0.0, places=6)

    def test_valgo_positivo_cuando_la_rodilla_entra(self):
        # rodilla izquierda (x negativa) desplazada hacia la línea media (x=0)
        c = self._cuerpo(left_knee=kp(-0.02, 0.5))
        v = g.desviacion_lateral_rodilla(c, "izq")
        self.assertGreater(v, 0.0)

    def test_separacion_pies_relativa(self):
        self.assertAlmostEqual(g.separacion_pies(self._cuerpo()), 1.0, places=6)

    def test_confianza_es_el_minimo_no_la_media(self):
        c = self._cuerpo(left_ankle=kp(-0.1, 1.0, v=0.1))
        conf = g.confianza_de_terna(c, ("left_hip", "left_knee", "left_ankle"))
        self.assertAlmostEqual(conf, 0.1, places=6)

    def test_orientacion_de_frente_es_cero(self):
        self.assertAlmostEqual(g.orientacion_camara(self._cuerpo()), 0.0, places=6)

    def test_orientacion_de_perfil_es_noventa(self):
        c = self._cuerpo(left_shoulder=kp(0.0, -0.5, -0.2),
                         right_shoulder=kp(0.0, -0.5, 0.2))
        self.assertAlmostEqual(g.orientacion_camara(c), 90.0, places=6)


class TestMedidasADR004(unittest.TestCase):
    """Medidas añadidas con los 33 puntos existentes (ADR-006)."""

    def _cuerpo(self, **kw):
        c = TestMedidas()._cuerpo(left_ear=kp(-0.08, -0.7), right_ear=kp(0.08, -0.7))
        c.update(kw)
        return c

    def test_oblicuidades_nulas_si_esta_nivelado(self):
        c = self._cuerpo()
        self.assertAlmostEqual(g.oblicuidad_pelvis(c), 0.0, places=6)
        self.assertAlmostEqual(g.oblicuidad_hombros(c), 0.0, places=6)

    def test_oblicuidad_positiva_si_sube_el_lado_izquierdo(self):
        c = self._cuerpo(left_hip=kp(-0.1, -0.03), left_shoulder=kp(-0.2, -0.55))
        self.assertGreater(g.oblicuidad_pelvis(c), 5.0)
        self.assertGreater(g.oblicuidad_hombros(c), 5.0)
        c = self._cuerpo(right_hip=kp(0.1, -0.03))
        self.assertLess(g.oblicuidad_pelvis(c), -5.0)

    def test_inclinacion_lateral_con_signo_de_la_persona(self):
        self.assertAlmostEqual(g.inclinacion_lateral(self._cuerpo()), 0.0, places=6)
        # En este cuerpo el lado izquierdo está en x negativa.
        hacia_izq = self._cuerpo(left_shoulder=kp(-0.3, -0.5), right_shoulder=kp(0.1, -0.5))
        self.assertGreater(g.inclinacion_lateral(hacia_izq), 5.0)

    def test_inclinacion_lateral_no_depende_del_espejo(self):
        c = self._cuerpo(left_shoulder=kp(-0.3, -0.5), right_shoulder=kp(0.1, -0.5))
        espejo = {k: kp(-p.x, p.y, p.z) for k, p in c.items()}
        self.assertAlmostEqual(g.inclinacion_lateral(c), g.inclinacion_lateral(espejo),
                               places=6)

    def test_inclinacion_lateral_ignora_la_flexion_hacia_delante(self):
        c = self._cuerpo(left_shoulder=kp(-0.2, -0.4, 0.3), right_shoulder=kp(0.2, -0.4, 0.3))
        self.assertGreater(g.inclinacion_tronco(c), 30.0)
        self.assertAlmostEqual(g.inclinacion_lateral(c), 0.0, places=6)

    def test_cabeza_alineada_cero_y_adelantada_positiva(self):
        self.assertAlmostEqual(g.cabeza_adelantada(self._cuerpo()), 0.0, places=6)
        c = self._cuerpo(left_ear=kp(-0.08, -0.65, 0.12), right_ear=kp(0.08, -0.65, 0.12))
        self.assertGreater(g.cabeza_adelantada(c), 30.0)

    def test_abduccion_de_la_pierna_que_se_abre(self):
        c = self._cuerpo()
        self.assertAlmostEqual(g.abduccion_cadera(c, "izq"), 0.0, places=6)
        abierta = self._cuerpo(left_knee=kp(-0.1 - 0.5 * math.sin(math.radians(30)),
                                            0.5 * math.cos(math.radians(30))))
        self.assertAlmostEqual(g.abduccion_cadera(abierta, "izq"), 30.0, places=4)
        self.assertAlmostEqual(g.abduccion_cadera(abierta, "der"), 0.0, places=6)

    def test_alineacion_de_cadera_en_plancha(self):
        def plancha(y_cadera):
            return {"left_shoulder": kp(0.5, -0.05, 0.15), "right_shoulder": kp(0.5, -0.05, -0.15),
                    "left_hip": kp(0.0, y_cadera, 0.1), "right_hip": kp(0.0, y_cadera, -0.1),
                    "left_ankle": kp(-0.9, 0.06, 0.1), "right_ankle": kp(-0.9, 0.06, -0.1)}
        recta = g.alineacion_cadera(plancha(-0.0107))
        self.assertAlmostEqual(recta, 0.0, places=2)
        self.assertGreater(g.alineacion_cadera(plancha(0.08)), 0.1)     # hundida
        self.assertLess(g.alineacion_cadera(plancha(-0.12)), -0.1)      # elevada

    def test_alineacion_de_plancha_de_perfil_usa_el_lado_visible(self):
        """De perfil el tobillo lejano queda tapado: la medida se calcula con
        el lado cercano y su confianza es la de ese lado (ADR-006 §2.1)."""
        kps = {"left_shoulder": kp(0.5, -0.05, 0.15), "right_shoulder": kp(0.5, -0.05, -0.15, v=0.9),
               "left_hip": kp(0.0, 0.07, 0.1), "right_hip": kp(0.0, 0.07, -0.1, v=0.9),
               "left_ankle": kp(-0.9, 0.06, 0.1), "right_ankle": kp(-0.9, 0.06, -0.1, v=0.2),
               "left_knee": kp(-0.45, 0.06, 0.1), "right_knee": kp(-0.45, 0.06, -0.1, v=0.3)}
        self.assertEqual(g.lado_mas_visible(kps, g.PARTES_ALINEACION), "left")
        obs = g.observacion_desde_pose(MuestraPose(t_ms=0, keypoints=kps), "plancha")
        self.assertGreater(obs.distancias["alineacion_cadera"], 0.1)
        self.assertEqual(obs.confianza_de("alineacion_cadera"), 1.0)


class TestObservacion(unittest.TestCase):
    def test_construye_angulos_y_medios(self):
        kps = TestMedidas()._cuerpo()
        obs = g.observacion_desde_pose(
            MuestraPose(t_ms=0, keypoints=kps), "sentadilla")
        for nombre in ("rodilla_izq", "rodilla_der", "rodilla_media",
                       "tronco_inclinacion", "oblicuidad_pelvis",
                       "oblicuidad_hombros", "inclinacion_lateral",
                       "abduccion_cadera_izq", "abduccion_cadera_der"):
            self.assertIn(nombre, obs.angulos, nombre)
            self.assertIn(nombre, g.PLANO_DE_ANGULO, nombre)
        self.assertIn("separacion_pies", obs.distancias)
        self.assertIn("alineacion_cadera", obs.distancias)

    def test_cabeza_requiere_orejas(self):
        sin = g.observacion_desde_pose(MuestraPose(t_ms=0, keypoints=TestMedidas()._cuerpo()), "x")
        self.assertNotIn("cabeza_adelantada", sin.angulos)
        con = g.observacion_desde_pose(
            MuestraPose(t_ms=0, keypoints=TestMedidasADR004()._cuerpo()), "x")
        self.assertIn("cabeza_adelantada", con.angulos)

    def test_confianza_ausente_es_cero_no_uno(self):
        obs = g.observacion_desde_pose(
            MuestraPose(t_ms=0, keypoints={}), "sentadilla")
        self.assertEqual(obs.confianza_de("rodilla_izq"), 0.0)


if __name__ == "__main__":
    unittest.main()
