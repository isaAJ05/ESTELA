"""Micrófono con `sounddevice`: entrega frases cortadas por `DetectorDeFrase`."""

from __future__ import annotations

import queue
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import numpy as np

from .frases import BLOQUE, FS, MAX_FRASE_S, DetectorDeFrase


#: motivo de `hay_microfono` cuando el audio funciona pero no hay ninguna entrada
SIN_MICROFONO = "no hay ningún micrófono conectado"

#: audio reciente que se guarda pase lo que pase (s): de ahí sale la ventana mientras
#: ESTELA habla, así no se pierde lo dicho justo al empezar o al acabar ella
RECIENTE_S = 3.0
#: al callarse ESTELA, lo último que se antepone a la frase siguiente (s)
CEBO_S = 1.0
#: aviso temprano de «Estela» (`escuchar_frase(al_avanzar=…)`): a partir de
#: `AVISO_MIN_S` de frase, cada `AVISO_CADA_S` se pasan sus últimos `AVISO_VENTANA_S`.
#: `[?]` Valores de ingeniería: «Estela» dura ~0,5 s; medidos solo con audio sintético.
AVISO_MIN_S, AVISO_CADA_S, AVISO_VENTANA_S = 0.4, 0.3, 2.0


class SinMicrofono(RuntimeError):
    """No hay ninguna entrada de audio: se puede conectar una y volver a encender."""


def _entradas() -> List[Dict[str, Any]]:
    import sounddevice as sd
    return [d for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]


def volver_a_buscar() -> None:
    """Vuelve a leer los dispositivos de audio. PortAudio los lee al arrancar: un
    micrófono conectado después no aparece hasta reiniciarlo. Solo se llama sin
    ninguna entrada abierta. `[?]` no probado con un micrófono conectado en caliente."""
    try:
        import sounddevice as sd
        sd._terminate()
        sd._initialize()
    except Exception:                                     # noqa: BLE001 — se sigue con lo que había
        pass


def hay_microfono() -> Tuple[bool, str]:
    """(hay, motivo si no). No lanza."""
    try:
        entradas = _entradas()
    except Exception as exc:                              # noqa: BLE001
        return False, f"no se pudo consultar el audio ({type(exc).__name__}: {exc})"
    if not entradas:
        return False, SIN_MICROFONO
    return True, ""


def listar_microfonos() -> List[Dict[str, Any]]:
    """Entradas de audio que ve el sistema: [{"indice", "nombre", "porDefecto"}].
    No lanza: sin audio devuelve []. La lista se vuelve a leer al encender el micrófono
    (`Microfono` llama a `volver_a_buscar` si no ve ninguna entrada)."""
    try:
        import sounddevice as sd
        dispositivos = list(sd.query_devices())
        por_defecto = sd.default.device[0]
    except Exception:                                     # noqa: BLE001
        return []
    return [{"indice": i, "nombre": str(d.get("name", f"Micrófono {i}")),
             "porDefecto": i == por_defecto}
            for i, d in enumerate(dispositivos) if d.get("max_input_channels", 0) > 0]


class Microfono:
    """Abre una entrada a 16 kHz mono (`dispositivo` None: la de defecto del
    sistema). `escuchar_frase` bloquea hasta que hay una frase, se cancela o
    pasa `espera_s`. `nivel` es el volumen reciente (RMS, 0–1) para pintarlo."""

    #: `escuchar_frase` acepta `al_avanzar` (la escucha lo mira antes de pasarlo)
    avisa_temprano = True

    def __init__(self, dispositivo: Optional[int] = None) -> None:
        import sounddevice as sd
        if not _entradas():                       # puede ser un micrófono recién conectado
            volver_a_buscar()
            if not _entradas():
                raise SinMicrofono(SIN_MICROFONO)
        self.dispositivo = dispositivo
        self._preparar()
        self._flujo = sd.InputStream(samplerate=FS, channels=1, dtype="float32",
                                     blocksize=BLOQUE, callback=self._al_llegar,
                                     device=dispositivo)
        self._flujo.start()
        try:
            self.nombre: Optional[str] = str(sd.query_devices(
                dispositivo if dispositivo is not None else sd.default.device[0])["name"])
        except Exception:                                 # noqa: BLE001
            self.nombre = None

    def _preparar(self) -> None:
        """Estado sin dispositivo (los tests lo usan con `Microfono.__new__`)."""
        self._cola: "queue.Queue[np.ndarray]" = queue.Queue()
        self._detector = DetectorDeFrase()
        self._reciente: Deque[np.ndarray] = deque(maxlen=int(RECIENTE_S * FS / BLOQUE))
        self._nuevos = 0                  # bloques llegados desde la última ventana
        self.nivel = 0.0

    def _al_llegar(self, datos, frames, tiempo, estado) -> None:   # hilo de audio
        bloque = datos[:, 0].copy()
        # volumen suavizado: sube enseguida y baja despacio, para que se lea en pantalla
        rms = float(np.sqrt(np.mean(bloque ** 2))) if len(bloque) else 0.0
        self.nivel = rms if rms > self.nivel else 0.8 * self.nivel + 0.2 * rms
        self._cola.put(bloque)

    def _tomar(self, timeout: float = 0.1) -> np.ndarray:
        """Siguiente bloque de la cola (lanza `queue.Empty`); queda en `_reciente`."""
        bloque = self._cola.get(timeout=timeout)
        self._reciente.append(bloque)
        self._nuevos += 1
        return bloque

    def descartar(self) -> None:
        """Tira lo capturado hasta ahora (p. ej. mientras hablaba ESTELA)."""
        while not self._cola.empty():
            try:
                self._cola.get_nowait()
            except queue.Empty:
                break
        self._reciente.clear()
        self._detector.reiniciar()

    def _ultimos(self, segundos: float) -> List[np.ndarray]:
        n = max(1, int(segundos * FS / BLOQUE))
        return list(self._reciente)[-n:]

    def escuchar_ventana(self, cancelar: Callable[[], bool], ventana_s: float = 2.5,
                         paso_s: float = 1.0,
                         hasta: Optional[Callable[[], bool]] = None) -> Optional[np.ndarray]:
        """Mientras ESTELA habla, el corte por energía no sirve (su voz también
        cuenta como voz). Aquí se junta audio durante `paso_s` y se devuelven los
        últimos `ventana_s` segundos, solapados con la ventana anterior, para que
        una orden no quede partida. None si se cancela.

        La ventana sale del audio reciente, también del que oyó el corte por frases
        justo antes: lo dicho al empezar ESTELA a hablar no se pierde. Si `hasta()`
        se cumple (ESTELA se calló), se devuelve ya lo que haya, para mirarlo una
        última vez, y la frase siguiente empieza con el último `CEBO_S`: lo dicho
        justo al acabar ella tampoco se pierde."""
        import time
        fin = time.monotonic() + paso_s
        while time.monotonic() < fin:
            if cancelar():
                return None
            if hasta is not None and hasta():
                hay_nuevo = self._nuevos > 0
                self._detector.reiniciar(conservar_ruido=True)
                self._detector.cebar(self._ultimos(CEBO_S))
                self._nuevos = 0
                return np.concatenate(self._ultimos(ventana_s)) if hay_nuevo and self._reciente else None
            try:
                self._tomar()
            except queue.Empty:
                continue
        self._detector.reiniciar(conservar_ruido=True)   # al volver al corte por frases, empieza limpio
        self._nuevos = 0
        return np.concatenate(self._ultimos(ventana_s)) if self._reciente else None

    def escuchar_continuacion(self, segundos: float,
                              cancelar: Callable[[], bool]) -> Optional[np.ndarray]:
        """El audio de los próximos `segundos` (ESTELA ya callada): lo que la usuaria
        siga diciendo tras «Estela». None si se cancela o no llega nada."""
        import time
        fin = time.monotonic() + segundos
        bloques: List[np.ndarray] = []
        while time.monotonic() < fin:
            if cancelar():
                return None
            try:
                bloques.append(self._tomar())
            except queue.Empty:
                continue
        self._detector.reiniciar(conservar_ruido=True)
        return np.concatenate(bloques) if bloques else None

    def olvidar_ventana(self) -> None:
        """Tras actuar sobre una ventana, que la siguiente (ni la frase que siga) no
        vuelva a oír lo mismo."""
        self._reciente.clear()
        self._nuevos = 0
        self._detector.reiniciar(conservar_ruido=True)

    def escuchar_frase(self, cancelar: Callable[[], bool], espera_s: float = 1.0,
                       al_avanzar: Optional[Callable[[np.ndarray], Any]] = None
                       ) -> Optional[np.ndarray]:
        """La frase siguiente, cortada por energía. `al_avanzar(audio)`: con la frase
        aún en curso, se llama cada `AVISO_CADA_S` (aviso temprano de «Estela»), con
        sus últimos `AVISO_VENTANA_S`. Si devuelve "oida" (o True), la frase se
        recorta a ese trozo (`recortar`) y desde ahí se le pasa la frase entera; si
        devuelve "lista", la frase se entrega ya, sin esperar el silencio (con ruido
        de ejercicio el silencio no llega y la frase solo se cerraba en el tope).

        Si se cancela (p. ej. ESTELA empieza a hablar) no se tira el audio: queda
        en el reciente para la ventana de `escuchar_ventana`. Quien llama decide si
        lo tira (`descartar`)."""
        import time
        fin = time.monotonic() + espera_s
        avisada, ultimo = False, 0.0
        while not cancelar():
            d = self._detector
            if time.monotonic() > fin and not d.en_frase:
                return None
            try:
                bloque = self._tomar()
            except queue.Empty:
                continue
            frase = d.alimentar(bloque)
            if frase is not None:
                # ya atendida: que una ventana de justo después no la vuelva a oír
                # (p. ej. mientras ESTELA confirma la orden); si no, «siguiente» saltaría dos
                self._reciente.clear()
                self._nuevos = 0
                return frase
            if al_avanzar is None:
                continue
            if not d.en_frase:
                avisada, ultimo = False, 0.0
                continue
            dur = d.segundos_en_frase
            if dur >= AVISO_MIN_S and dur - ultimo >= AVISO_CADA_S:
                ultimo = dur
                r = al_avanzar(d.ultimos(MAX_FRASE_S if avisada else AVISO_VENTANA_S))
                if r is True or (r == "oida" and not avisada):
                    avisada = True
                    d.recortar(AVISO_VENTANA_S)
                    ultimo = d.segundos_en_frase
                elif r == "lista":
                    frase = d.entregar()
                    if frase is not None:
                        self._reciente.clear()
                        self._nuevos = 0
                        return frase
        self._detector.reiniciar(conservar_ruido=True)
        return None

    def cerrar(self) -> None:
        try:
            self._flujo.stop()
            self._flujo.close()
        except Exception:                                 # noqa: BLE001
            pass


__all__ = ["Microfono", "SIN_MICROFONO", "AVISO_MIN_S", "AVISO_CADA_S", "AVISO_VENTANA_S", "SinMicrofono", "hay_microfono",
           "listar_microfonos", "volver_a_buscar"]
