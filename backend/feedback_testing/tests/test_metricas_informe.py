"""Métricas del Informe 2 con datos de resultado conocido (sin cámara ni cv2)."""

import math
import unittest
from pathlib import Path

from feedback_testing.metricas_informe import (
    CUMPLE, NO_CUMPLE, OBJETIVOS_INFORME2, PENDIENTE, Anotacion, Conteo,
    MensajeEmitido, RepAnotada, ErrorAnotado, agregar, anotacion_desde_dict,
    atribuir, cargar_anotacion, conteos_por_error, deteccion_cruda,
    emparejar_repeticiones, episodios, evaluar, jitter, kappa_anotadoras,
    kappa_cohen, latencia_por_longitud, mensajes_correctos, pendiente,
    refuerzos_indebidos, rendimiento, resumen_serie, retraso_acumulado,
    sobrecorreccion, tasa_aserciones_no_soportadas, tasas_silencio,
)

EJEMPLO = Path(__file__).resolve().parent.parent / "anotaciones" / "ejemplo_sintetico.json"


def rep(ini, fin, *errores):
    return RepAnotada(ini, fin, tuple(ErrorAnotado(e) for e in errores), "jj")


def msg(t, error_id, segmento=None, lado=None, texto="", severidad="leve"):
    return MensajeEmitido(t, error_id, segmento, lado, severidad, texto, "jj")


class TestObjetivos(unittest.TestCase):
    def test_un_solo_sitio_con_los_seis_objetivos(self):
        self.assertEqual(set(OBJETIVOS_INFORME2), {
            "pose_p95_ms", "fps_sostenidos", "deteccion_voz_p95_s", "precision",
            "recobrado", "sobrecorreccion", "mensajes_correctos"})

    def test_evaluar(self):
        self.assertEqual(evaluar("pose_p95_ms", 33.0), CUMPLE)
        self.assertEqual(evaluar("pose_p95_ms", 33.1), NO_CUMPLE)
        self.assertEqual(evaluar("fps_sostenidos", 24.9), NO_CUMPLE)
        self.assertEqual(evaluar("precision", None), PENDIENTE)
        self.assertEqual(evaluar("recobrado", float("nan")), PENDIENTE)


class TestEstadistica(unittest.TestCase):
    def test_resumen_vacio(self):
        r = resumen_serie([])
        self.assertEqual(r["n"], 0)
        self.assertIsNone(r["p95"])

    def test_resumen_conocido(self):
        r = resumen_serie([1, 2, 3, 4, 5])
        self.assertEqual((r["media"], r["p50"], r["max"]), (3.0, 3.0, 5.0))
        self.assertAlmostEqual(r["p95"], 4.8)

    def test_pendiente(self):
        self.assertAlmostEqual(pendiente([0, 1, 2], [1, 3, 5]), 2.0)
        self.assertIsNone(pendiente([1], [1]))
        self.assertIsNone(pendiente([2, 2], [1, 3]))


class TestRendimiento(unittest.TestCase):
    def test_fps_y_descartados(self):
        r = rendimiento(frames_fuente=300, procesados=250, duracion_s=10.0)
        self.assertEqual(r["fps_sostenidos"], 25.0)
        self.assertEqual(r["descartados"], 50)
        self.assertAlmostEqual(r["fraccion_descartada"], 50 / 300)

    def test_sin_tiempo_ni_frames(self):
        r = rendimiento(0, 0, 0.0)
        self.assertIsNone(r["fps_sostenidos"])
        self.assertIsNone(r["fraccion_descartada"])

    def test_retraso_constante_no_deriva(self):
        llegadas = [i / 30 for i in range(30)]
        fines = [t + 0.020 for t in llegadas]
        r = retraso_acumulado(llegadas, fines)
        self.assertAlmostEqual(r["p50"], 20.0)
        self.assertAlmostEqual(r["deriva_ms_por_s"], 0.0, places=6)

    def test_cola_lenta_deriva(self):
        """Fuente a 30 fps (33,3 ms) y 50 ms por frame sin descartar: el
        retraso crece 50/33,3 − 1 = 0,5 s por segundo de vídeo."""
        llegadas = [i / 30 for i in range(90)]
        fines, fin = [], 0.0
        for l in llegadas:
            fin = max(fin, l) + 0.050
            fines.append(fin)
        r = retraso_acumulado(llegadas, fines)
        self.assertAlmostEqual(r["deriva_ms_por_s"], 500.0, delta=1.0)
        self.assertAlmostEqual(r["final"], (90 * 0.05 - 89 / 30) * 1000, places=6)

    def test_retraso_vacio(self):
        r = retraso_acumulado([], [])
        self.assertEqual(r["n"], 0)
        self.assertIsNone(r["final"])
        self.assertIsNone(r["deriva_ms_por_s"])


class TestSilencios(unittest.TestCase):
    def test_tasas_por_causa(self):
        reg = (
            [{"persona": False}] * 2
            + [{"persona": True, "evaluado": False, "pausada": True,
                "motivo_pausa": "inactividad"}]
            + [{"persona": True, "evaluado": True, "motivo_silencio": "sin_error"}] * 6
            + [{"persona": True, "evaluado": True, "motivo_silencio": "confianza_baja"}] * 2
            + [{"persona": True, "evaluado": True, "mensaje": {"refuerzo": False}},
               {"persona": True, "evaluado": True, "mensaje": {"refuerzo": True}}])
        r = tasas_silencio(reg)
        self.assertEqual((r["frames"], r["sin_persona"], r["evaluados"]), (13, 2, 10))
        self.assertEqual(r["pausada"], {"inactividad": 1})
        self.assertEqual(r["motivos"], {"sin_error": 6, "confianza_baja": 2})
        self.assertAlmostEqual(r["tasa_motivos"]["sin_error"], 0.6)
        self.assertEqual((r["correcciones"], r["refuerzos"]), (1, 1))

    def test_registro_vacio(self):
        r = tasas_silencio([])
        self.assertEqual(r["frames"], 0)
        self.assertIsNone(r["tasa_sin_persona"])
        self.assertEqual(r["tasa_motivos"], {})


class TestAnotacion(unittest.TestCase):
    def test_el_ejemplo_sintetico_es_valido(self):
        a = cargar_anotacion(EJEMPLO)
        self.assertEqual(a.ejercicio_id, "jumping_jacks")
        self.assertEqual({r.bloque for r in a.repeticiones}, {1, 2, 3, 4})
        self.assertTrue(a.repeticiones[0].correcta)
        self.assertEqual(a.repeticiones[9].errores[0].segmento, "codo")

    def test_rechaza_formato_y_solapes(self):
        base = {"formato": "estela-anotacion-v1", "video": "v", "ejercicio_id": "jj",
                "anotadora": "A", "repeticiones": []}
        with self.assertRaises(ValueError):
            anotacion_desde_dict({**base, "formato": "otro"})
        with self.assertRaises(ValueError):
            anotacion_desde_dict({**base, "repeticiones": [
                {"t_ini_ms": 0, "t_fin_ms": 100}, {"t_ini_ms": 50, "t_fin_ms": 150}]})
        with self.assertRaises(ValueError):
            anotacion_desde_dict({**base, "repeticiones": [{"t_ini_ms": 10, "t_fin_ms": 10}]})
        with self.assertRaises(ValueError):
            anotacion_desde_dict({**base, "bloque": 5})


class TestPrecisionRecobrado(unittest.TestCase):
    # 6 repeticiones de 1 s: codos en 1-3 (un episodio), brazos en 5
    REPS = [rep(0, 1000), rep(1000, 2000, "codos"), rep(2000, 3000, "codos"),
            rep(3000, 4000, "codos"), rep(4000, 5000), rep(5000, 6000, "brazos")]

    def test_episodios(self):
        self.assertEqual(episodios(self.REPS, "codos"), [(1, 3)])
        self.assertEqual(episodios(self.REPS, "brazos"), [(5, 5)])
        self.assertEqual(episodios(self.REPS, "otro"), [])

    def test_atribucion_con_tolerancia(self):
        # 4300 ms está en la rep 4 (correcta), pero a 300 ms de la rep 3 con codos
        self.assertEqual(atribuir(4300, "codos", self.REPS, 500), 3)
        self.assertEqual(atribuir(4300, "codos", self.REPS, 0), 4)
        self.assertEqual(atribuir(4300, "brazos", self.REPS, 500), 4)
        self.assertIsNone(atribuir(9000, "codos", self.REPS, 500))

    def test_conteos_conocidos(self):
        mensajes = [msg(2500, "codos"), msg(4300, "codos"), msg(500, "brazos"),
                    msg(9000, "codos"), msg(4500, None)]
        c = conteos_por_error(self.REPS, mensajes, tolerancia_ms=500,
                              error_ids=["pies"])
        self.assertEqual((c["codos"].vp, c["codos"].fp, c["codos"].fuera), (2, 1, 1))
        self.assertEqual((c["codos"].episodios, c["codos"].detectados), (1, 1))
        self.assertAlmostEqual(c["codos"].precision, 2 / 3)
        self.assertEqual(c["codos"].recobrado, 1.0)
        self.assertAlmostEqual(c["codos"].f1, 0.8)
        # brazos: un FP y el episodio de la rep 5 sin detectar
        self.assertEqual((c["brazos"].vp, c["brazos"].fp), (0, 1))
        self.assertEqual(c["brazos"].recobrado, 0.0)
        self.assertIsNone(c["brazos"].f1)
        # error del catálogo sin datos: todo None
        self.assertIsNone(c["pies"].precision)
        self.assertIsNone(c["pies"].recobrado)
        total = agregar(c.values())
        self.assertEqual((total.vp, total.fp, total.episodios, total.detectados),
                         (2, 2, 2, 1))

    def test_sin_mensajes_ni_anotacion(self):
        self.assertEqual(conteos_por_error([], []), {})
        c = Conteo()
        self.assertIsNone(c.precision)
        self.assertIsNone(c.f1)

    def test_deteccion_cruda_por_repeticion(self):
        disparos = [(1100, "codos"), (1200, "codos"), (2500, "codos"),
                    (4500, "codos"), (5500, "brazos")]
        c = deteccion_cruda(self.REPS, disparos)
        # codos: reps 1 y 2 detectadas (VP), rep 3 no; rep 4 disparada (FP)
        self.assertEqual((c["codos"].vp, c["codos"].fp), (2, 1))
        self.assertEqual((c["codos"].episodios, c["codos"].detectados), (3, 2))
        self.assertEqual((c["brazos"].vp, c["brazos"].detectados), (1, 1))

    def test_sobrecorreccion(self):
        mensajes = [msg(500, "brazos"), msg(4300, "codos"), msg(4600, "codos")]
        r = sobrecorreccion(self.REPS, mensajes, tolerancia_ms=500)
        # rep 0 corregida; 4300 se atribuye a la rep 3 (codos); 4600 a la rep 4
        self.assertEqual(r["repeticiones_correctas"], 2)
        self.assertEqual(r["con_correccion"], 2)
        self.assertEqual(r["tasa"], 1.0)
        self.assertIsNone(sobrecorreccion([rep(0, 10, "x")], [])["tasa"])

    def test_mensajes_correctos_compara_segmento_y_lado(self):
        reps = [RepAnotada(0, 1000, (ErrorAnotado("valgo", "rodilla", "izquierdo"),)),
                RepAnotada(1000, 2000, (ErrorAnotado("valgo"),))]
        reglas = {"valgo": ("rodilla", "derecho")}
        mensajes = [msg(500, "valgo", "rodilla", "izquierdo"),   # coincide
                    msg(600, "valgo", "rodilla", "derecho"),     # lado anotado distinto
                    msg(1500, "valgo", "rodilla", "derecho"),    # usa la regla: coincide
                    msg(1600, "otro", "codo", "na")]             # no anotado
        r = mensajes_correctos(reps, mensajes, reglas, tolerancia_ms=0)
        self.assertEqual((r["mensajes"], r["correctos"]), (4, 2))
        self.assertEqual(r["tasa"], 0.5)
        self.assertIsNone(mensajes_correctos(reps, [], reglas)["tasa"])

    def test_refuerzos_indebidos(self):
        r = refuerzos_indebidos(self.REPS, [msg(500, None), msg(1500, None)])
        self.assertEqual((r["refuerzos"], r["indebidos"]), (2, 1))

    def test_aserciones_no_soportadas(self):
        bien = msg(0, "codos_flexionados", "codo", "bilateral",
                   texto="Estira más los codos.")
        mal = msg(0, "codos_flexionados", "codo", "bilateral",
                  texto="Estira la rodilla izquierda.")
        r = tasa_aserciones_no_soportadas([bien, mal, msg(0, None)])
        self.assertEqual((r["mensajes"], r["no_soportadas"]), (2, 1))
        self.assertIsNone(tasa_aserciones_no_soportadas([])["tasa"])


class TestKappa(unittest.TestCase):
    def test_acuerdo_perfecto(self):
        self.assertEqual(kappa_cohen([1, 0, 1, 0], [1, 0, 1, 0]), 1.0)

    def test_valor_conocido(self):
        # po = 0,7; pa = 0,5; pb = 0,6; pe = 0,5 → κ = 0,4
        a = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]
        b = [1, 1, 1, 1, 0, 1, 1, 0, 0, 0]
        self.assertAlmostEqual(kappa_cohen(a, b), 0.4)

    def test_indefinido(self):
        self.assertTrue(math.isnan(kappa_cohen([], [])))
        self.assertTrue(math.isnan(kappa_cohen([0, 0, 0], [0, 0, 0])))

    def test_emparejar_y_kappa_entre_anotadoras(self):
        a = Anotacion("v", "jj", "A1", (rep(0, 1000), rep(1000, 2000, "codos"),
                                        rep(2000, 3000, "codos")))
        b = Anotacion("v", "jj", "A2", (rep(50, 1050), rep(1050, 2000, "codos"),
                                        rep(2000, 2900), rep(5000, 6000)))
        self.assertEqual(emparejar_repeticiones(a.repeticiones, b.repeticiones),
                         [(0, 0), (1, 1), (2, 2)])
        r = kappa_anotadoras(a, b, error_ids=["brazos"])
        self.assertEqual((r["pares"], r["sin_pareja_a"], r["sin_pareja_b"]), (3, 0, 1))
        # codos: [0,1,1] vs [0,1,0] → po=2/3, pe=(2/3)(1/3)+(1/3)(2/3)=4/9 → κ=0,4
        self.assertAlmostEqual(r["por_error"]["codos"], 0.4)
        self.assertTrue(math.isnan(r["por_error"]["brazos"]))
        with self.assertRaises(ValueError):
            kappa_anotadoras(a, Anotacion("otro", "jj", "A2", ()))


class TestPoseYDTW(unittest.TestCase):
    def test_jitter_de_una_senal_constante_es_cero(self):
        self.assertAlmostEqual(jitter([10.0] * 40, 5), 0.0)

    def test_jitter_de_una_alternancia_conocida(self):
        # ±1 alternado con ventana 3: la media local es ∓1/3, así que el
        # residuo es ±4/3 → desviación ≈ 1,33 (algo más por el n − 1)
        serie = [1.0 if i % 2 else -1.0 for i in range(41)]
        self.assertAlmostEqual(jitter(serie, 3), 4 / 3, delta=0.03)

    def test_jitter_con_huecos_y_sin_datos(self):
        self.assertIsNone(jitter([1.0, None, 2.0], 3))
        self.assertIsNone(jitter([], 3))
        self.assertAlmostEqual(jitter([5.0] * 10 + [None] + [7.0] * 10, 3), 0.0)
        with self.assertRaises(ValueError):
            jitter([1.0] * 10, 4)

    def test_latencia_por_longitud(self):
        n = list(range(1, 101))
        lat = [0.3 * x + 1 for x in n]
        r = latencia_por_longitud(n, lat, tramos=(0, 50))
        self.assertAlmostEqual(r["pendiente_ms_por_frame"], 0.3)
        self.assertEqual([f["n"] for f in r["tramos"]], [50, 50])
        self.assertEqual(r["longitud_max"], 100)
        self.assertEqual(latencia_por_longitud([], [])["tramos"], [])


if __name__ == "__main__":
    unittest.main()
