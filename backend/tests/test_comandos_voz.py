"""Comandos de voz: lista cerrada, sin adivinar, y cuándo se puede escuchar."""

import pytest

from estela.aplicacion import comandos_voz as cv


@pytest.mark.parametrize("dicho, comando", [
    ("pausa", cv.PAUSA), ("Pausa.", cv.PAUSA), ("¡Espera!", cv.PAUSA),
    ("seguir", cv.SEGUIR), ("Sigue.", cv.SEGUIR), ("Continúa", cv.SEGUIR),
    ("siguiente", cv.SIGUIENTE), ("El próximo.", cv.SIGUIENTE),
    ("terminar", cv.TERMINAR), ("Quiero terminar ya", cv.TERMINAR),
    ("¿Cómo voy?", cv.COMO_VOY), ("como voy", cv.COMO_VOY), ("¿Cómo vamos?", cv.COMO_VOY),
])
def test_cada_orden_se_reconoce_con_tildes_signos_y_mayusculas(dicho, comando):
    i = cv.interpretar(dicho)
    assert (i.comando, i.motivo, i.pedir_repetir) == (comando, cv.ENTENDIDO, False)


@pytest.mark.parametrize("dicho", ["hola", "qué calor hace", "pausita", "prosigue",
                                   "seguirle", "termino"])
def test_sin_orden_clara_se_pide_repetir_y_no_se_adivina(dicho):
    i = cv.interpretar(dicho)
    assert (i.comando, i.motivo, i.pedir_repetir) == (None, cv.SIN_COMANDO, True)


@pytest.mark.parametrize("dicho", ["pausa o siguiente", "sigue, no, mejor termina",
                                   "pausa y termina"])
def test_dos_ordenes_distintas_son_ambiguas(dicho):
    i = cv.interpretar(dicho)
    assert (i.comando, i.motivo, i.pedir_repetir) == (None, cv.AMBIGUO, True)


@pytest.mark.parametrize("dicho", ["", "   ", None, "...", "¡!",
                                   "Subtítulos realizados por la comunidad de Amara.org"])
def test_silencio_o_frase_fantasma_no_pide_repetir(dicho):
    i = cv.interpretar(dicho)
    assert (i.comando, i.motivo, i.pedir_repetir) == (None, cv.VACIO, False)


def test_el_lexico_no_se_pisa_entre_ordenes_y_todas_tienen_confirmacion():
    formas = [f for c in cv.COMANDOS for f in cv.LEXICO[c]]
    assert len(formas) == len(set(formas))
    for c in cv.COMANDOS:
        assert cv.LEXICO[c] and c in cv.CONFIRMACION
        for forma in cv.LEXICO[c]:
            assert cv.interpretar(forma).comando == c


def test_solo_se_escucha_en_pausa_o_entre_ejercicios_y_en_silencio():
    assert cv.puede_escuchar(en_pausa=True, colocando=False, hablando=False)
    assert cv.puede_escuchar(en_pausa=False, colocando=True, hablando=False)
    assert not cv.puede_escuchar(en_pausa=False, colocando=False, hablando=False)   # en movimiento
    assert not cv.puede_escuchar(en_pausa=True, colocando=False, hablando=True)     # habla ESTELA
    assert not cv.puede_escuchar(en_pausa=True, colocando=True, hablando=False, terminada=True)
