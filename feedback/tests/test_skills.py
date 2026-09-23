import unittest

from feedback.contrato import SEGMENTOS
from feedback.motor.skill import (
    SkillInvalido, cargar_skills, directorio_skills, skill_desde_dict,
)


class TestCargaDeSkills(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = cargar_skills(directorio_skills())

    def test_hay_cinco_skills(self):
        self.assertEqual(len(self.skills), 5, sorted(self.skills))

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

    def test_rechaza_asimetria_con_un_solo_nombre(self):
        d = self._base()
        d["reglas"][0]["medida"] = {"tipo": "asimetria", "nombres": ["a"]}
        with self.assertRaises(SkillInvalido):
            skill_desde_dict(d)


if __name__ == "__main__":
    unittest.main()
