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


class TestObservacion(unittest.TestCase):
    def test_construye_angulos_y_medios(self):
        kps = TestMedidas()._cuerpo()
        obs = g.observacion_desde_pose(
            MuestraPose(t_ms=0, keypoints=kps), "sentadilla")
        for nombre in ("rodilla_izq", "rodilla_der", "rodilla_media",
                       "tronco_inclinacion"):
            self.assertIn(nombre, obs.angulos, nombre)
        self.assertIn("separacion_pies", obs.distancias)

    def test_confianza_ausente_es_cero_no_uno(self):
        obs = g.observacion_desde_pose(
            MuestraPose(t_ms=0, keypoints={}), "sentadilla")
        self.assertEqual(obs.confianza_de("rodilla_izq"), 0.0)


if __name__ == "__main__":
    unittest.main()
