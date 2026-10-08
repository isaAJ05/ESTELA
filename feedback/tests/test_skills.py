import os
import unittest

from feedback.contrato import SEGMENTOS
from feedback.motor.skill import (
    SkillInvalido, cargar_skills, directorio_skills, skill_desde_dict,
)


class TestCargaDeSkills(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = cargar_skills(directorio_skills())

    def test_son_los_ejercicios_de_adr_004(self):
        # 5 ejercicios (ADR-005); abducción y zancada, un skill por pierna.
        self.assertEqual(set(self.skills), {
            "jumping_jacks", "marcha_rodillas", "plancha",
            "abduccion_cadera_izq", "abduccion_cadera_der",
            "zancada_atras_izq", "zancada_atras_der"})

    def test_los_retirados_no_se_cargan_pero_siguen_siendo_validos(self):
        retirados = os.path.join(directorio_skills(), "retirados")
        viejos = cargar_skills(retirados)
        self.assertEqual(set(viejos), {"sentadilla", "elevacion_brazos", "rotacion_tronco"})
        self.assertFalse(set(viejos) & set(self.skills))
        self.assertEqual({s.estado for s in viejos.values()}, {"descartado"})

    def test_todas_las_reglas_usan_segmentos_del_vocabulario(self):
        for skill in self.skills.values():
            for regla in skill.reglas:
                self.assertIn(regla.segmento, SEGMENTOS,
                              f"{skill.skill_id}:{regla.error_id}")

    def test_las_fases_de_las_reglas_existen_en_el_skill(self):
        for skill in self.skills.values():
            for regla in skill.reglas:
                for fase in regla.fases:
                    self.assertIn(fase, skill.fases,
                                  f"{skill.skill_id}:{regla.error_id}:{fase}")

    def test_toda_regla_es_observable_en_la_orientacion_del_ejercicio(self):
        """Sin esto una regla no podría dispararse nunca en sesión y, como el
        refuerzo exige comprobar todas las reglas aplicables (ADR-006 §2.9),
        el ejercicio tampoco podría felicitar nunca."""
        from feedback.motor.decision import _PLANO_IDEAL_GRADOS, plano_observable
        for skill in self.skills.values():
            ideal = _PLANO_IDEAL_GRADOS.get(skill.orientacion_preferida)
            for regla in skill.reglas:
                self.assertTrue(
                    plano_observable(regla, ideal, skill.politica.tolerancia_orientacion_grados),
                    f"{skill.skill_id}:{regla.error_id} ({regla.plano.value})")

    def test_todo_umbral_declara_su_origen(self):
        """Ningún umbral puede pasar como si estuviera justificado."""
        for skill in self.skills.values():
            for regla in skill.reglas:
                self.assertTrue(regla.umbral_origen.strip(),
                                f"{skill.skill_id}:{regla.error_id}")


class TestValidacionDelEsquema(unittest.TestCase):
    def _base(self, **kw):
        d = {
            "skill_id": "x", "nombre": "X", "version": "0.1.0",
            "fases": ["a"],
            "reglas": [{
                "error_id": "e1", "medida": {"tipo": "angulo", "nombre": "k"},
                "condicion": {"op": ">", "umbral": 1},
                "segmento": "rodilla", "lado": "bilateral",
                "plano": "sagital", "prioridad": 1,
            }],
        }
        d.update(kw)
        return d

    def test_rechaza_segmento_fuera_del_vocabulario(self):
        d = self._base()
        d["reglas"][0]["segmento"] = "biceps"
        with self.assertRaises(SkillInvalido):
            skill_desde_dict(d)

    def test_rechaza_prioridades_duplicadas(self):
        d = self._base()
        d["reglas"].append(dict(d["reglas"][0], error_id="e2"))
        with self.assertRaises(SkillInvalido):
            skill_desde_dict(d)

    def test_rechaza_operador_desconocido(self):
        d = self._base()
        d["reglas"][0]["condicion"] = {"op": "~=", "umbral": 1}
        with self.assertRaises(SkillInvalido):
            skill_desde_dict(d)

    def test_rechaza_estado_desconocido(self):
        with self.assertRaises(SkillInvalido):
            skill_desde_dict(self._base(estado="retirado"))
        self.assertEqual(skill_desde_dict(self._base(estado="descartado")).estado,
                         "descartado")

    def test_solo_lado_visible_exige_una_medida_de_un_lado(self):
        d = self._base()
        d["reglas"][0]["solo_lado_visible"] = True   # medida «k», sin lado
        with self.assertRaises(SkillInvalido):
            skill_desde_dict(d)

    def test_solo_lado_visible_exige_que_el_lado_coincida(self):
        d = self._base()
        d["reglas"][0].update(medida={"tipo": "angulo", "nombre": "rodilla_izq"},
                              lado="derecho", solo_lado_visible=True)
        with self.assertRaises(SkillInvalido):
            skill_desde_dict(d)

    def test_silenciada_por_debe_nombrar_otra_regla(self):
        for otra in ("no_existe", "e1"):
            d = self._base()
            d["reglas"][0]["silenciada_por"] = [otra]
            with self.assertRaises(SkillInvalido):
                skill_desde_dict(d)

    def test_rechaza_asimetria_con_un_solo_nombre(self):
        d = self._base()
        d["reglas"][0]["medida"] = {"tipo": "asimetria", "nombres": ["a"]}
        with self.assertRaises(SkillInvalido):
            skill_desde_dict(d)


if __name__ == "__main__":
    unittest.main()
