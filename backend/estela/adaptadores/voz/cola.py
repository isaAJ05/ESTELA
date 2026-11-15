"""Cola de voz: un hilo que habla sin bloquear el bucle de percepción.

Tiene un único hueco pendiente: si llega una frase nueva mientras otra
espera, la más reciente la sustituye (un feedback de hace 3 s ya no sirve).
Los avisos de la aplicación (cambio de ejercicio, fin de rutina) tienen más
prioridad que las correcciones y no los pisa una corrección.
Una corrección que lleva más de `MAX_ESPERA_FEEDBACK_S` esperando cuando el
hueco queda libre se descarta sin sonar: llegaría tarde para la repetición
que corrige. Los avisos no caducan. `anunciando` dice si suena o espera un
aviso; la sesión no evalúa la técnica mientras tanto.
Silenciada (ajuste de la interfaz), descarta todo lo que se le pide.

`registro` guarda, por frase, cuándo se encoló, cuándo empezó a sonar y si
se descartó y por qué (`DESCARTE_*`; marcas de `time.perf_counter()`, en
segundos). Con él el arnés del Informe 2 mide la latencia detección → inicio
de voz.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from ...aplicacion.puertos import PRIORIDAD_AVISO, PRIORIDAD_FEEDBACK

from .motores import MotorVoz

log = logging.getLogger(__name__)

#: segundos que una corrección puede esperar en la cola antes de descartarse
MAX_ESPERA_FEEDBACK_S = 1.0
#: por qué no sonó una frase (`registro[i]["motivo_descarte"]`)
DESCARTE_SUSTITUIDA = "sustituida"      # llegó otra más reciente al hueco
DESCARTE_AVISO = "aviso"                # el hueco lo tenía un aviso
DESCARTE_CADUCADA = "caducada"          # esperó más de MAX_ESPERA_FEEDBACK_S
DESCARTE_SILENCIADA = "silenciada"      # la interfaz silenció la voz

@dataclass(frozen=True)
class Locucion:
    texto: str
    prioridad: int
    t_encolado: float
    #: posición de la frase en `ColaVoz.registro`
    indice: int = -1


class ColaVoz:
    def __init__(self, motor: MotorVoz,
                 max_espera_feedback_s: float = MAX_ESPERA_FEEDBACK_S) -> None:
        self.motor = motor
        self.max_espera_feedback_s = max_espera_feedback_s
        self._cv = threading.Condition()
        self._pendiente: Optional[Locucion] = None
        self._hablando = False
        self._prioridad_hablando: Optional[int] = None
        self._cerrada = False
        self._silenciada = False
        self.descartadas = 0
        #: descartadas por causa (`DESCARTE_*`)
        self.descartes: Dict[str, int] = {}
        #: (texto, segundos entre encolar y empezar a sonar)
        self.historial: List[tuple] = []
        #: una entrada por llamada a `decir`: texto, prioridad, t_encolado,
        #: t_inicio (empieza `hablar`), t_inicio_audio (empieza a sonar, si
        #: el motor lo sabe; si no, = t_inicio), t_fin, descartada y
        #: motivo_descarte
        self.registro: List[Dict[str, Any]] = []
        self._hilo = threading.Thread(target=self._bucle, name="estela-voz",
                                      daemon=True)
        self._hilo.start()

    def decir(self, texto: str, prioridad: int = PRIORIDAD_FEEDBACK) -> bool:
        """Encola una frase. Devuelve False si se descartó."""
        with self._cv:
            if self._cerrada or self._silenciada:
                return False
            ahora = time.perf_counter()
            entrada = {"texto": texto, "prioridad": prioridad,
                       "t_encolado": ahora, "t_inicio": None,
                       "t_inicio_audio": None, "t_fin": None,
                       "descartada": False, "motivo_descarte": None}
            self.registro.append(entrada)
            p = self._pendiente
            if p is not None and p.prioridad > prioridad:
                self._descarta(len(self.registro) - 1, DESCARTE_AVISO)
                return False
            if p is not None:
                self._descarta(p.indice, DESCARTE_SUSTITUIDA)
            self._pendiente = Locucion(texto, prioridad, ahora,
                                       len(self.registro) - 1)
            self._cv.notify()
            return True

    def silenciar(self, silenciada: bool = True) -> None:
        """Deja de hablar (lo que ya suena termina) o vuelve a hablar."""
        with self._cv:
            self._silenciada = silenciada
            if silenciada and self._pendiente is not None:
                self._descarta(self._pendiente.indice, DESCARTE_SILENCIADA)
                self._pendiente = None

    @property
    def silenciada(self) -> bool:
        return self._silenciada

    def precalentar(self, textos: Iterable[str]) -> None:
        """Sintetiza en segundo plano las frases conocidas, sin bloquear.

        Una frase pedida antes de estar lista se sintetiza al momento.
        """
        lista = list(textos)
        threading.Thread(target=self.motor.precalentar, args=(lista,),
                         name="estela-voz-precalentado", daemon=True).start()

    @property
    def anunciando(self) -> bool:
        """Suena o espera un aviso (cambio de ejercicio, pausa, colocación)."""
        with self._cv:
            return (self._prioridad_hablando == PRIORIDAD_AVISO
                    or (self._pendiente is not None
                        and self._pendiente.prioridad == PRIORIDAD_AVISO))

    @property
    def ocupada(self) -> bool:
        with self._cv:
            return self._hablando or self._pendiente is not None

    def esperar_vacia(self, timeout: float = 10.0) -> None:
        fin = time.monotonic() + timeout
        while self.ocupada and time.monotonic() < fin:
            time.sleep(0.02)

    def _bucle(self) -> None:
        while True:
            with self._cv:
                while self._pendiente is None and not self._cerrada:
                    self._cv.wait()
                if self._cerrada and self._pendiente is None:
                    return
                loc, self._pendiente = self._pendiente, None
                if (loc.prioridad == PRIORIDAD_FEEDBACK and time.perf_counter()
                        - loc.t_encolado > self.max_espera_feedback_s):
                    self._descarta(loc.indice, DESCARTE_CADUCADA)
                    continue
                self._hablando = True
                self._prioridad_hablando = loc.prioridad
            entrada = self.registro[loc.indice]
            try:
                t_inicio = time.perf_counter()
                entrada["t_inicio"] = t_inicio
                self.historial.append((loc.texto, t_inicio - loc.t_encolado))
                self.motor.hablar(loc.texto)
                audio = getattr(self.motor, "ultimo_inicio_audio", None)
                # un valor anterior a t_inicio es de la frase previa
                entrada["t_inicio_audio"] = (audio if audio is not None
                                             and audio >= t_inicio else t_inicio)
            except Exception:                     # noqa: BLE001
                log.exception("fallo al hablar: %r", loc.texto)
            finally:
                entrada["t_fin"] = time.perf_counter()
                with self._cv:
                    self._hablando = False
                    self._prioridad_hablando = None

    def _descarta(self, indice: int, motivo: str) -> None:
        """Con `_cv` tomado."""
        self.descartadas += 1
        self.descartes[motivo] = self.descartes.get(motivo, 0) + 1
        self.registro[indice]["descartada"] = True
        self.registro[indice]["motivo_descarte"] = motivo

    def cerrar(self, esperar: bool = True) -> None:
        if esperar:
            self.esperar_vacia()
        with self._cv:
            self._cerrada = True
            self._cv.notify()
        self._hilo.join(timeout=2.0)
        self.motor.cerrar()


__all__ = ["ColaVoz", "PRIORIDAD_FEEDBACK", "PRIORIDAD_AVISO", "MAX_ESPERA_FEEDBACK_S",
           "DESCARTE_SUSTITUIDA", "DESCARTE_AVISO", "DESCARTE_CADUCADA",
           "DESCARTE_SILENCIADA"]
