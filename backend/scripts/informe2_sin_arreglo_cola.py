"""Medición «antes» de la cola de voz en el Mac: el código actual con el arreglo
del commit 3799a55 apagado en memoria (no modifica ningún archivo).

Apaga las dos piezas de ese arreglo:
  - la caducidad de las correcciones (MAX_ESPERA_FEEDBACK_S), y
  - que la sesión no evalúe la técnica mientras suena un aviso (ColaVoz.anunciando).
Todo lo demás (skills, vídeos, modelo, voz) es igual que en la corrida «después».

Uso (desde ESTELA/backend):  .venv/bin/python ../../scripts/informe2_sin_arreglo_cola.py <args de informe2>
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from estela.adaptadores.voz import cola
from feedback_testing import informe2

cola.MAX_ESPERA_FEEDBACK_S = 1e9
cola.ColaVoz.__init__.__defaults__ = (1e9,)
cola.ColaVoz.anunciando = property(lambda self: False)
assert cola.ColaVoz(cola.MotorVoz()).max_espera_feedback_s == 1e9
sys.exit(informe2.main(sys.argv[1:]))
