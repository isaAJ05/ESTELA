from estela.adaptadores.voz.motores import (MotorVoz, VozConPronunciacion,
                                            con_pronunciacion)


class Anotador(MotorVoz):
    nombre = "anota"

    def __init__(self):
        self.dichas = []
        self.precalentadas = []

    def hablar(self, texto):
        self.dichas.append(texto)

    def precalentar(self, textos):
        self.precalentadas.extend(textos)


def test_cambia_jumping_jacks_en_sus_variantes():
    for original in ("jumping jacks", "Jumping Jacks", "jumping-jack", "JUMPING_JACKS"):
        assert con_pronunciacion(f"Hagamos {original}") == "Hagamos yámping yaks"


def test_no_toca_otras_palabras():
    assert con_pronunciacion("Baja la cadera") == "Baja la cadera"


def test_la_envoltura_cambia_lo_que_se_dice_y_deja_pasar_el_resto():
    m = Anotador()
    v = VozConPronunciacion(m)
    v.hablar("Ahora, jumping jacks")
    v.precalentar(["Hola jumping jack", "Baja la cadera"])
    assert m.dichas == ["Ahora, yámping yaks"]
    assert m.precalentadas == ["Hola yámping yaks", "Baja la cadera"]
    assert v.nombre == "anota"
    assert v.ultimo_inicio_audio is None
