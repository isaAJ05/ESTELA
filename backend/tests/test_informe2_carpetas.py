"""Qué ejercicio asigna el arnés del Informe 2 a cada vídeo, según su carpeta y su nombre."""

from pathlib import Path

import pytest

from feedback_testing.informe2 import _ejercicio_de

ZANCADA = "Zancada atrás estática por pierna"
ABDUCCION = "Abdución de caderas pies"


@pytest.mark.parametrize("carpeta, archivo, esperado", [
    ("jumping_jack", "1 hombre.mp4", "jumping_jacks"),
    ("Plancha", "plancha correcta hombre.mp4", "plancha"),
    (ABDUCCION, "der 876. Abducción de cadera con apoyo en silla.mp4", "abduccion_cadera_der"),
    (ABDUCCION, "izquierda abductor.mp4", "abduccion_cadera_izq"),
    (ZANCADA, "izq Zancada hacia atrás con peso corporal_ técnica paso a paso.mp4", "zancada_atras_izq"),
    (ZANCADA, "der Zancada atrás con Kettlebell Derecha.mp4", "zancada_atras_der"),
    (ZANCADA, "ZANCADA CHICA IZQUIERDA.mp4", "zancada_atras_izq"),
    (ZANCADA, "ZANCADA CHICA DERECHA.mp4", "zancada_atras_der"),
])
def test_asigna_el_ejercicio_y_el_lado(carpeta, archivo, esperado):
    assert _ejercicio_de(Path(carpeta) / archivo) == (esperado, "")


@pytest.mark.parametrize("carpeta, archivo, motivo", [
    (ZANCADA, "videoplayback (1).mp4", "sin lado"),
    (ABDUCCION, "Abducción activa de cadera en bipedestación.mp4", "sin lado"),
    (ABDUCCION, "izq Aducción de cadera de pie con máquina.mp4", "aducción"),
    ("marcha_rodillas", "1 mujer.mp4", "fuera de los 4 ejercicios"),
])
def test_excluye_con_motivo(carpeta, archivo, motivo):
    ejercicio, porque = _ejercicio_de(Path(carpeta) / archivo)
    assert ejercicio is None
    assert motivo in porque
