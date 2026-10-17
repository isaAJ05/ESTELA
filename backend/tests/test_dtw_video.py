"""Sesión completa con DTW sobre un vídeo real (T12, EXP-006).

Usa un vídeo público del dataset de PRUEBAS (jumping jacks, «1 hombre.mp4»)
que no es el de la referencia. Necesita el modelo de pose
(`python scripts/descargar_modelos.py`); sin él o sin el vídeo, se salta.
Tarda unos segundos: `pytest -m "not video"` lo deja fuera.
"""

import statistics

import pytest

from estela import config
from estela.aplicacion.rutina import cargar_catalogo, rutina_de_un_ejercicio
from estela.aplicacion.sesion import Sesion

VIDEO = (config.RAIZ.parent / "PRUEBAS" / "Prueba red neuronal (dataset-pose-deteccion-conteo)"
         / "DATASET" / "videos" / "jumping_jack" / "1 hombre.mp4")
MODELO = config.modelo_pose("full")

pytestmark = [
    pytest.mark.video,
    pytest.mark.skipif(not (VIDEO.is_file() and MODELO.is_file()),
                       reason="falta el vídeo de prueba o el modelo de pose"),
]


class VozMuda:
    def decir(self, texto, prioridad=0):
        return True


def correr_video() -> Sesion:
    from estela.adaptadores.captura.fuente import FuenteVideo
    from estela.adaptadores.pose.estimador import EstimadorPose

    catalogo = cargar_catalogo()
    s = Sesion(rutina_de_un_ejercicio("jumping_jacks", 999, catalogo), catalogo,
               EstimadorPose(MODELO), VozMuda())
    fuente = FuenteVideo(VIDEO)
    try:
        while (leido := fuente.leer()) is not None:
            s.procesar(*leido)
    finally:
        fuente.cerrar()
        s.estimador.cerrar()
    return s


@pytest.fixture(scope="module")
def dos_pasadas():
    return correr_video().resumen(), correr_video().resumen()


def test_el_dtw_alinea_las_repeticiones_del_video(dos_pasadas):
    r = dos_pasadas[0]
    paso = r["pasos"][0]
    assert paso["completadas"] >= 8
    assert paso["dtw"]["alineado"] >= 0.8 * r["frames"]
    # al volver al reposo, el alineamiento está donde empieza el reposo de la
    # referencia (frame 38 de 62, progreso ≈ 0,62)
    cierres = [f["progreso_dtw"] for f in paso["repeticiones"] if f["resultado"] == "cuenta"]
    assert 0.55 <= statistics.median(cierres) <= 0.7


def test_el_dtw_es_despreciable_frente_a_la_pose(dos_pasadas):
    lat = dos_pasadas[0]["latencias"]
    assert lat["dtw"]["p95_ms"] < 0.1 * lat["pose"]["p50_ms"]


def test_el_mismo_video_da_la_misma_sesion(dos_pasadas):
    a, b = ({k: v for k, v in r.items() if k != "latencias"} for r in dos_pasadas)
    assert a == b
