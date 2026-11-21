from estela.dominio.conteo.segmentador import SegmentadorAlternante, SegmentadorCiclo, CondicionPostura
from estela.dominio.feedback.contrato import Observacion


def _marcha(alternar):
    return SegmentadorAlternante("angulos.i", "angulos.d", 150, 125, "a_der", "a_izq", "t", 10,
                                 suavizado=1, alternar=alternar)


def _elevar(seg, lado):
    for v in (170, 100, 170):
        e = seg.actualizar(Observacion(t_ms=0, ejercicio_id="x", fase="", repeticion=0,
                                       angulos={"i": 170.0, "d": 170.0, lado: float(v)},
                                       confianza={"i": 1.0, "d": 1.0}))
    return e


def test_misma_pierna_dos_veces_no_cuenta_dos():
    seg = _marcha(True)
    _elevar(seg, "i"); e = _elevar(seg, "i")
    assert (e.completadas, e.incompletas) == (1, 1)
    e = _elevar(seg, "d")
    assert e.completadas == 2


def test_sin_alternar_cuentan_todas():
    seg = _marcha(False)
    _elevar(seg, "i"); e = _elevar(seg, "i")
    assert e.completadas == 2


def test_jumping_jack_sin_salto_no_cuenta():
    seg = SegmentadorCiclo("angulos.b", 45, 100, ("c", "a", "x", "v"), 15, suavizado=1,
                           requiere=[CondicionPostura("distancias.salto_cadera", min=0.10)])
    def rep(salto):
        for b in (20, 130, 20):
            e = seg.actualizar(Observacion(t_ms=0, ejercicio_id="x", fase="", repeticion=0,
                                           angulos={"b": float(b)}, distancias={"salto_cadera": salto},
                                           confianza={"b": 1.0, "salto_cadera": 1.0}))
        return e
    assert rep(0.02).incompletas == 1
    assert rep(0.25).completadas == 1
