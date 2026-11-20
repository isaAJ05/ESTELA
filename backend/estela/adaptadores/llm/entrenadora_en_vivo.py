"""Conecta la entrenadora con una sesión en marcha, sin tocar el bucle por frame.

`Sesion` avisa al cerrar cada ejercicio (`al_cerrar_paso`). Aquí se atiende en
un hilo aparte: se pide la respuesta a la entrenadora (modelo local, con su
tiempo límite, o plantilla), se dice por la cola de voz como un aviso y se
suelta la retención para que el ejercicio siguiente pueda empezar.

Nunca durante el movimiento: antes de hablar se comprueba
`Sesion.entrenadora_vigente` (la colocación sigue retenida o la rutina
terminó). Si la respuesta llega tarde, se descarta y se cuenta. Entre
ejercicios solo actúa si la sesión tiene fase de colocación, que es donde se
retiene; al final de la rutina actúa siempre.

`entre_ejercicios=False` (defecto desde el 2026-11-20, pedido de Paula: «no
quiero que esté dando retroalimentación entre los ejercicios sino que siga al
siguiente»): entre ejercicios no habla ni retiene la colocación; solo el
resumen final y «¿cómo voy?».
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Mapping, Optional

from ...aplicacion.entrenadora import Entrenadora, Respuesta
from ...aplicacion.puertos import PRIORIDAD_AVISO, Voz

log = logging.getLogger(__name__)

#: respuesta que no llegó a decirse y por qué
TARDE = "tarde"                          # el ejercicio ya había empezado
SIN_COLOCACION = "sin_colocacion"        # no hay fase donde retener
APAGADA_ENTRE = "apagada_entre"          # entre ejercicios no habla (`entre_ejercicios`)


class EntrenadoraEnVivo:
    def __init__(self, entrenadora: Entrenadora, voz: Voz,
                 progreso: Optional[Callable[[], Optional[Mapping[str, Any]]]] = None,
                 espera_voz_s: float = 20.0, entre_ejercicios: bool = False) -> None:
        self.entrenadora = entrenadora
        #: ¿habla también entre ejercicios? (si no, solo al final y en «¿cómo voy?»)
        self.entre_ejercicios = entre_ejercicios
        self.voz = voz
        #: función que da `historial.progreso()` del perfil activo, o None
        self.progreso = progreso
        #: tope de espera a que la cola de voz quede libre antes y después de hablar
        self.espera_voz_s = espera_voz_s
        #: una entrada por cierre de ejercicio: momento, dicha, motivo y respuesta
        self.registro: List[Dict[str, Any]] = []
        self._hilos: List[threading.Thread] = []
        self._sesion: Any = None

    def conectar(self, sesion: Any, retencion_max_ms: int) -> None:
        """Engancha la entrenadora a `sesion` (una `Sesion` recién creada)."""
        self._sesion = sesion
        # sin resumen entre ejercicios no hay nada que esperar: el siguiente sigue ya
        sesion.retencion_max_ms = retencion_max_ms if self.entre_ejercicios else 0
        sesion.al_cerrar_paso = self._al_cerrar_paso

    # -- hilo de la sesión: no debe bloquear ---------------------------------
    def _al_cerrar_paso(self, evento: Dict[str, Any]) -> None:
        sesion = self._sesion
        if not evento["final"] and (not self.entre_ejercicios or not evento["retenida"]):
            self.registro.append({"momento": "entre", "dicha": False,
                                  "motivo": SIN_COLOCACION if self.entre_ejercicios
                                  else APAGADA_ENTRE, "respuesta": None})
            return
        h = threading.Thread(target=self._trabaja, args=(sesion, evento),
                             name="estela-entrenadora", daemon=True)
        self._hilos.append(h)
        h.start()

    # -- hilo propio -----------------------------------------------------------
    def _voz_libre(self) -> None:
        esperar = getattr(self.voz, "esperar_vacia", None)
        if esperar is not None:
            esperar(self.espera_voz_s)

    def _trabaja(self, sesion: Any, evento: Dict[str, Any]) -> None:
        entrada: Dict[str, Any] = {"momento": "final" if evento["final"] else "entre",
                                   "dicha": False, "motivo": "", "respuesta": None}
        self.registro.append(entrada)
        try:
            progreso = None
            if self.progreso is not None:
                try:
                    progreso = self.progreso()
                except Exception:                         # noqa: BLE001
                    log.exception("no se pudo leer el historial para la entrenadora")
            t0 = time.perf_counter()
            r: Respuesta = (self.entrenadora.al_final(evento["pasos"], progreso)
                            if evento["final"] else
                            self.entrenadora.entre_ejercicios(evento["paso"],
                                                              evento["siguiente"], progreso))
            entrada["respuesta"] = r.a_dict()
            entrada["espera_s"] = round(time.perf_counter() - t0, 2)
            self._voz_libre()                    # que acabe «Muy bien, terminaste…»
            if not sesion.entrenadora_vigente(evento["turno"]):
                entrada["motivo"] = TARDE
                return
            log.info("Entrenadora (%s, %s): %s", r.origen, r.accion, r.texto)
            if not evento["final"]:
                sesion.mostrar_entrenadora(evento["turno"], r.texto)   # también se lee
            entrada["dicha"] = bool(self.voz.decir(r.texto, PRIORIDAD_AVISO))
            self._voz_libre()                    # el anuncio del ejercicio va después
        except Exception:                                 # noqa: BLE001
            log.exception("fallo de la entrenadora")
            entrada["motivo"] = "error"
        finally:
            sesion.soltar_entrenadora(evento["turno"])

    def esperar(self, timeout_s: float) -> None:
        """Espera a que acaben las respuestas en curso (antes de cerrar la voz)."""
        fin = time.monotonic() + timeout_s
        for h in list(self._hilos):
            h.join(max(0.0, fin - time.monotonic()))

    def resumen(self) -> Dict[str, Any]:
        return {"respuestas": list(self.registro),
                "origenes": dict(self.entrenadora.origenes),
                "caidas_a_plantilla": dict(self.entrenadora.caidas)}


__all__ = ["EntrenadoraEnVivo", "TARDE", "SIN_COLOCACION"]
