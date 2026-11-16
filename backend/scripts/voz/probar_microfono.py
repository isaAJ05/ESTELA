"""Prueba las órdenes de voz con el micrófono, sin cámara ni sesión.

    python scripts/voz/probar_microfono.py [--registro hoja.jsonl] [--segundos 120]

Abre el micrófono, corta cada frase igual que la aplicación, la reconoce con
Whisper y dice qué orden entendió. Sirve para comprobar el micrófono y los
umbrales del corte de frases antes de probar con la sesión completa.

Por cada frase imprime lo que oyó, la orden, cuánto duró la frase, su volumen
y lo que tardó en reconocerla. Con `--registro` guarda esas mismas líneas (el
texto y los números). **El audio no se guarda** en ningún caso.

Para salir: Ctrl+C.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ))

from estela import config  # noqa: E402
from estela.adaptadores.voz_entrada.frases import FS, RMS_MINIMO  # noqa: E402
from estela.adaptadores.voz_entrada.microfono import Microfono, hay_microfono  # noqa: E402
from estela.adaptadores.voz_entrada.reconocedor import ReconocedorWhisperCpp  # noqa: E402
from estela.aplicacion import comandos_voz as cv  # noqa: E402
from estela.aplicacion.entrenadora import menciona_dolor  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--registro", type=Path, help="archivo .jsonl donde anotar lo oído (sin audio)")
    p.add_argument("--segundos", type=float, default=0.0, help="parar sola tras este tiempo (0 = no)")
    a = p.parse_args(argv)

    hay, motivo = hay_microfono()
    if not hay:
        print(f"No se puede probar: {motivo}.")
        return 2
    ruta = config.modelo_voz_entrada()
    if not ruta.exists():
        print(f"Falta el modelo {ruta.name}: python scripts/descargar_modelos.py --voz-entrada")
        return 2
    try:
        import sounddevice as sd
        print("Micrófono:", sd.query_devices(kind="input")["name"])
    except Exception as e:                                # noqa: BLE001
        print(f"No se pudo leer el micrófono por defecto ({type(e).__name__}: {e}).")
        return 2
    print("Cargando el reconocedor…", flush=True)
    reconocedor = ReconocedorWhisperCpp(ruta)
    reconocedor.precalentar()
    microfono = Microfono()
    print("Te escucho. Di: pausa, seguir, siguiente, repetir, terminar o ¿cómo voy?  (Ctrl+C para salir)\n",
          flush=True)
    fin = time.monotonic() + a.segundos if a.segundos > 0 else None
    n = 0
    try:
        while fin is None or time.monotonic() < fin:
            audio = microfono.escuchar_frase(cancelar=lambda: False, espera_s=1.0)
            if audio is None:
                continue
            t0 = time.perf_counter()
            texto = reconocedor.transcribir(audio)
            ms = (time.perf_counter() - t0) * 1000
            i = cv.interpretar(texto)
            dolor = menciona_dolor(texto)
            entendido = ("DOLOR (respuesta fija)" if dolor else i.comando.upper() if i.comando
                         else "no entendí (pediría repetir)" if i.pedir_repetir else "nada (no contesta)")
            fila = {"n": (n := n + 1), "texto": texto, "comando": i.comando, "motivo": i.motivo,
                    "dolor": dolor, "duracion_s": round(len(audio) / FS, 2),
                    "volumen_rms": round(float(np.sqrt(np.mean(audio ** 2))), 4),
                    "volumen_pico": round(float(np.abs(audio).max()), 3),
                    "reconocer_ms": round(ms)}
            print(f"{n:3d}. oí «{texto}» → {entendido}   [{fila['duracion_s']} s, volumen "
                  f"{fila['volumen_rms']} (mínimo {RMS_MINIMO}), {fila['reconocer_ms']} ms]", flush=True)
            if a.registro:
                with open(a.registro, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
    except KeyboardInterrupt:
        pass
    finally:
        microfono.cerrar()
    print(f"\n{n} frases oídas." + (f" Anotadas en {a.registro}" if a.registro and n else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
