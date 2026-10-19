import numpy as np
import pytest

from estela.adaptadores.grabacion import episodio as ep
from estela.adaptadores.grabacion.grabador import buscar_ejercicio, grabar_video
from estela.adaptadores.pose.landmarks import NOMBRES_MEDIAPIPE, muestra_desde_arrays
from estela.aplicacion.puertos import ResultadoPose

N = len(NOMBRES_MEDIAPIPE)


def _pose(rng):
    mundo = rng.normal(size=(N, 4)).astype(np.float32)
    imagen = rng.uniform(size=(N, 4)).astype(np.float32)
    return mundo, imagen


def _grabacion(etiqueta="correcto", persona="p01"):
    skill = buscar_ejercicio("zancada_atras_izq").skill
    return ep.Grabacion(skill, etiqueta, persona, "camara", "mediapipe_tasks:lite")


def test_busca_skills_retirados():
    assert buscar_ejercicio("zancada_atras_izq").skill.estado == "descartado"
    assert buscar_ejercicio("marcha_rodillas").skill.estado != "descartado"
    with pytest.raises(KeyError):
        buscar_ejercicio("no_existe")


def test_etiquetas_son_correcto_y_los_errores_del_skill():
    skill = buscar_ejercicio("zancada_atras_izq").skill
    validas = ep.etiquetas_validas(skill)
    assert validas[0] == "correcto"
    assert set(validas[1:]) == {r.error_id for r in skill.reglas}
    with pytest.raises(ep.EtiquetaInvalida):
        _grabacion("rodilla_rara")
    with pytest.raises(ValueError):
        _grabacion(persona=" ")


def test_guardar_y_leer_conserva_la_pose_sin_frames(tmp_path):
    rng = np.random.default_rng(0)
    g = _grabacion("paso_corto")
    poses = [_pose(rng) for _ in range(3)]
    g.agregar(1000, *poses[0])
    g.agregar(1033, None, None)                     # sin persona
    g.agregar(1066, *poses[2])
    original = g.episodio({"completadas": 0})
    ruta = ep.guardar(original, ep.ruta_episodio(tmp_path, original))

    assert ruta.parent == tmp_path / "zancada_atras_izq" / "paso_corto"
    assert ruta.name.startswith("p01_")
    with np.load(ruta, allow_pickle=False) as d:     # sin pickle y sin vídeo
        assert set(d.files) == {"formato", "meta", "t_ms", "presente", "mundo", "imagen"}

    leido = ep.leer(ruta)
    assert leido.meta["etiqueta"] == "paso_corto"
    assert leido.meta["n_frames"] == 3 and leido.meta["frames_sin_persona"] == 1
    assert leido.t_ms.tolist() == [0, 33, 66]
    assert leido.presente.tolist() == [True, False, True]
    np.testing.assert_array_equal(leido.mundo[2], poses[2][0])
    assert np.isnan(leido.mundo[1]).all()
    assert ep.buscar(tmp_path, "zancada_atras_izq", ["paso_corto"]) == [ruta]
    assert ep.buscar(tmp_path, "zancada_atras_izq", ["correcto"]) == []


def test_las_muestras_leidas_son_las_del_estimador(tmp_path):
    rng = np.random.default_rng(1)
    mundo, imagen = _pose(rng)
    g = _grabacion()
    g.agregar(500, mundo, imagen)
    leido = ep.leer(ep.guardar(g.episodio(), tmp_path / "e.npz"))
    (t, muestra, im), = list(leido.muestras())
    esperada = muestra_desde_arrays(0, mundo, imagen)
    assert t == 0
    for nombre in NOMBRES_MEDIAPIPE:
        a, b = muestra.keypoints[nombre], esperada.keypoints[nombre]
        assert (a.x, a.y, a.z, a.visibilidad) == pytest.approx((b.x, b.y, b.z, b.visibilidad))


def test_dos_tomas_en_el_mismo_segundo_no_se_pisan(tmp_path):
    g = _grabacion()
    e = g.episodio()
    a = ep.guardar(e, ep.ruta_episodio(tmp_path, e))
    b = ep.guardar(e, ep.ruta_episodio(tmp_path, e))
    assert a != b and a.exists() and b.exists()


class _Fuente:
    def __init__(self, n):
        self._i, self._n = 0, n

    def leer(self):
        if self._i >= self._n:
            return None
        self._i += 1
        return np.zeros((4, 4, 3), np.uint8), (self._i - 1) * 40


class _Estimador:
    def __init__(self):
        self._rng = np.random.default_rng(2)

    def estimar(self, frame, t_ms):
        mundo, imagen = _pose(self._rng)
        return ResultadoPose(muestra_desde_arrays(t_ms, mundo, imagen), imagen, 1.0)


def test_grabar_video_guarda_un_episodio_con_todos_los_frames(tmp_path):
    ejercicio = buscar_ejercicio("zancada_atras_izq")
    ruta = grabar_video(ejercicio, lambda: _grabacion(), _Fuente(10), _Estimador(), tmp_path)
    leido = ep.leer(ruta)
    assert leido.n_frames == 10 and leido.presente.all()
    assert leido.fps_efectivo == pytest.approx(25.0)
