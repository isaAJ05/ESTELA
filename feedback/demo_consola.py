"""Demostración sin cámara ni modelo.

Simula una serie de repeticiones de sentadilla con un error de tronco que
aparece, se corrige y reaparece, e imprime lo que el sistema diría y lo que
callaría, con el motivo.

    python3 -m feedback.demo_consola
"""

from __future__ import annotations

from .contrato import MensajeFeedback, Observacion, Silencio
from .motor.skill import cargar_skills, directorio_skills
from .pipeline import MotorFeedback

#: inclinación de tronco por repetición: mal, mal, mal, bien, bien, mal, mal, mal
GUION = [60.0, 62.0, 58.0, 20.0, 18.0, 64.0, 66.0, 61.0]
FASES = ["arriba", "descenso", "fondo", "ascenso"]


def main() -> int:
    skills = cargar_skills(directorio_skills())
    motor = MotorFeedback(skills["sentadilla"])

    print("Ejercicio: sentadilla · verbalizador: plantillas · sin cámara\n")
    t = 0
    for rep, tronco in enumerate(GUION, start=1):
        print(f"--- repetición {rep} (tronco {tronco:.0f}°)")
        for fase in FASES:
            obs = Observacion(
                t_ms=t, ejercicio_id="sentadilla",
                angulos={"tronco_inclinacion": tronco, "rodilla_media": 85.0},
                confianza={"tronco_inclinacion": 0.95, "rodilla_media": 0.95},
                fase=fase, repeticion=rep, orientacion=85.0)
            salida = motor.procesar(obs)
            t += 750
            if isinstance(salida, MensajeFeedback):
                print(f"    [{fase:9}] HABLA  «{salida.texto}»  "
                      f"({salida.error.severidad.value}, "
                      f"{motor.ultimos_tiempos.total_ms:.3f} ms)")
            elif fase == "descenso":
                print(f"    [{fase:9}] calla  ({salida.motivo})")
    print("\nAbstenciones por motivo:", motor.abstenciones)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
