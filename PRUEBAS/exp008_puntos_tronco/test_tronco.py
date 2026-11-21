"""Pruebas de la geometría de EXP-008. Sin modelos: solo numpy.

    python -m unittest PRUEBAS/exp008_puntos_tronco/test_tronco.py
"""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tronco as T  # noqa: E402


def pose_mp(cadera_media, hombro_medio, ancho=40.0, n=1):
    """Pose de MediaPipe mínima (N, 33, 4) con caderas, hombros y pies."""
    kp = np.zeros((n, 33, 4))
    cm, hm = np.asarray(cadera_media, float), np.asarray(hombro_medio, float)
    for nombre, base, dx in (("cadera_izq", cm, -ancho / 2), ("cadera_der", cm, ancho / 2),
                             ("hombro_izq", hm, -ancho / 2), ("hombro_der", hm, ancho / 2)):
        kp[:, T.MP[nombre], :2] = base + [dx, 0]
    kp[:, T.MP["oreja_izq"], :2] = hm + [0, -30]
    kp[:, T.MP["oreja_der"], :2] = hm + [0, -30]
    return kp


class PuntosVirtuales(unittest.TestCase):
    """La propuesta inicial: subdividir el tronco interpolando MediaPipe."""

    def test_la_cadena_virtual_es_recta_en_cualquier_pose(self):
        rng = np.random.default_rng(0)
        kp = rng.uniform(0, 1000, size=(500, 33, 4))
        self.assertTrue(np.allclose(T.flecha(T.cadena_virtual_mp(kp)), 0.0, atol=1e-9))

    def test_cada_segmento_virtual_tiene_la_orientacion_del_tronco(self):
        kp = pose_mp((300, 400), (380, 220))
        cadena = T.cadena_virtual_mp(kp)[0]
        tronco = T.orientacion(cadena[-1] - cadena[0])
        for a, b in zip(cadena[:-1], cadena[1:]):
            self.assertAlmostEqual(float(T.orientacion(b - a)), float(tronco), places=9)


class Orientacion(unittest.TestCase):
    def test_signo_hacia_donde_mira(self):
        adelante = np.array([1.0, -1.0])            # arriba y a la derecha
        self.assertAlmostEqual(float(T.orientacion(adelante, +1)), 45.0)
        self.assertAlmostEqual(float(T.orientacion(adelante, -1)), -45.0)
        self.assertAlmostEqual(float(T.orientacion(np.array([0.0, -1.0]))), 0.0)

    def test_sentido_mirada_por_los_pies(self):
        talones = np.array([[[100, 500], [110, 500]]] * 5, float)
        self.assertEqual(T.sentido_mirada(talones, talones + [30, 0]), 1.0)
        self.assertEqual(T.sentido_mirada(talones, talones - [30, 0]), -1.0)

    def test_oblicuidad_positiva_si_la_izquierda_baja(self):
        self.assertGreater(float(T.oblicuidad(np.array([100., 410.]), np.array([140., 400.]))), 0)


class Flecha(unittest.TestCase):
    def cadena_arco(self, abombamiento, sentido=1.0):
        """Cadena vertical de abajo arriba con el centro desplazado
        `abombamiento` px hacia la espalda (la persona mira a `sentido`)."""
        y = np.linspace(400, 100, 7)
        x = 200 - sentido * abombamiento * np.sin(np.linspace(0, np.pi, 7))
        return np.stack([x, y], axis=-1)

    def test_espalda_redondeada_es_positiva_y_lordosis_negativa(self):
        for s in (1.0, -1.0):
            self.assertGreater(float(T.flecha(self.cadena_arco(20, s), s)), 0)
            self.assertLess(float(T.flecha(self.cadena_arco(-20, s), s)), 0)

    def test_es_invariante_a_la_inclinacion_del_tronco(self):
        c = self.cadena_arco(20)
        a = np.radians(40)
        rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        girada = (c - c[0]) @ rot.T + c[0]
        self.assertAlmostEqual(float(T.flecha(c)), float(T.flecha(girada)), places=9)


class MetricasSpinePose(unittest.TestCase):
    def pose_sp(self, sacro, l1, c7, cadera=(0, 0)):
        kp = np.zeros((1, 37, 2))
        cadera = np.asarray(cadera, float)
        kp[0, T.SP["cadera_izq"]] = cadera
        kp[0, T.SP["cadera_der"]] = cadera
        kp[0, T.SP["sacro"]] = sacro
        kp[0, T.SP["l1"]] = l1
        kp[0, T.SP["c7"]] = c7
        for n, f in (("l5", 1 / 3), ("l3", 2 / 3)):
            kp[0, T.SP[n]] = np.add(sacro, f * np.subtract(l1, sacro))
        for n, f in (("t8", 1 / 3), ("t3", 2 / 3)):
            kp[0, T.SP[n]] = np.add(l1, f * np.subtract(c7, l1))
        kp[0, T.SP["hombro_izq"]] = c7
        kp[0, T.SP["hombro_der"]] = c7
        return kp

    def test_redondear_la_parte_alta_sube_toracolumbar_y_flecha(self):
        # Mira a la derecha (+x). Misma lumbar; la parte alta se adelanta.
        neutro = T.metricas_spinepose(self.pose_sp((0, 0), (0, -120), (0, -300)))
        redondo = T.metricas_spinepose(self.pose_sp((0, 0), (0, -120), (60, -290)))
        self.assertGreater(redondo["sp_toracolumbar"][0], neutro["sp_toracolumbar"][0] + 10)
        self.assertGreater(redondo["sp_flecha"][0], neutro["sp_flecha"][0])

    def test_cadena_recta_da_flechas_nulas(self):
        m = T.metricas_spinepose(self.pose_sp((0, 0), (20, -120), (50, -300)))
        for k in ("sp_flecha_lumbar", "sp_flecha_toracica"):
            self.assertAlmostEqual(float(m[k][0]), 0.0, places=9)


class Contorno(unittest.TestCase):
    def test_espalda_convexa_da_flecha_positiva(self):
        h, w = 400, 400
        cadera, hombro = np.array([200.0, 350.0]), np.array([200.0, 50.0])
        ys = np.arange(h)
        mascara = np.zeros((h, w), np.float32)
        t = np.clip((350 - ys) / 300, 0, 1)
        espalda = 200 - 40 - 25 * np.sin(np.pi * t)       # mira a la derecha: espalda a la izquierda
        for y in range(50, 351):
            mascara[y, int(espalda[y]):240] = 1.0
        d = T.distancias_contorno(mascara, cadera, hombro)
        f = T.flecha_contorno(d[None], np.array([300.0]), sentido=1.0)
        self.assertGreater(float(f[0]), 0.02)


class Contrastes(unittest.TestCase):
    """La regla de decisión de analizar.py, sin modelos."""

    def grabaciones(self, delta_flecha, delta_tronco):
        from pathlib import Path
        recs, meds = [], []
        rng = np.random.default_rng(1)
        for i, cond in enumerate(["bisagra_neutra", "bisagra_redondeada"] * 3):
            d = delta_flecha if cond.endswith("redondeada") else 0.0
            t = delta_tronco if cond.endswith("redondeada") else 0.0
            recs.append({"meta": {"sujeto": "S1", "ropa": "ajustada", "condicion": cond,
                                  "vista": "perfil"}, "ruta": Path(f"{i}.npz")})
            meds.append({"sp_flecha": 0.01 + d + rng.normal(0, 0.002, 200),
                         "mp_tronco": 45 + t + rng.normal(0, 1, 200),
                         "sp_hombros_cadera": 45 + t + rng.normal(0, 1, 200)})
        return recs, meds

    def fila(self, filas, medida):
        return next(f for f in filas if f.startswith(f"| `{medida}`"))

    def test_separa_si_cambia_la_columna_y_no_el_tronco(self):
        import analizar as A
        filas = A.bloque_contrastes(*self.grabaciones(0.05, 0.0))
        self.assertIn("**sí**", self.fila(filas, "sp_flecha"))
        self.assertIn("0.050", self.fila(filas, "sp_flecha"))          # p = 1/20
        self.assertIn("no (correcto)", self.fila(filas, "mp_tronco"))

    def test_avisa_si_el_control_tambien_cambia(self):
        import analizar as A
        filas = A.bloque_contrastes(*self.grabaciones(0.05, 15.0))
        self.assertIn("sí (no debería)", self.fila(filas, "mp_tronco"))

    def test_no_separa_sin_efecto(self):
        import analizar as A
        filas = A.bloque_contrastes(*self.grabaciones(0.0, 0.0))
        self.assertNotIn("**sí**", self.fila(filas, "sp_flecha"))


if __name__ == "__main__":
    unittest.main()
