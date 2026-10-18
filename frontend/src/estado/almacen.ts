// Almacén del último estado recibido de Python.
//
// Python puede mandar ~30 estados por segundo. Para no re-renderizar toda la
// interfaz en cada uno:
//  - los componentes leen con `useEstado(selector)` y solo se re-renderizan
//    cuando cambia lo que seleccionan;
//  - el frame y el esqueleto no pasan por React: el lienzo se suscribe con
//    `alFrame` y dibuja en requestAnimationFrame.
// El bucle pide el estado siguiente solo cuando terminó con el anterior, así
// que si la interfaz va más lenta, se salta estados en vez de acumular retraso.

import { useRef, useSyncExternalStore } from 'react'
import type { Bridge, Capacidades, Estado, EstadoSesion, Info, OpcionesInicio, PasoRutina } from '../bridge/tipos'

/** La rutina de la sesión en curso o la última (la base, hasta que se elige otra). */
export interface Plan {
  nombre: string
  pasos: PasoRutina[]
}

export interface Instantanea {
  info: Info | null
  estado: Estado | null
  plan: Plan | null
}

export interface FrameNuevo {
  /** JPEG en base64, o null si no hay vídeo (simulador) */
  jpeg: string | null
  sesion: EstadoSesion | null
}

let actual: Instantanea = { info: null, estado: null, plan: null }
const oyentes = new Set<() => void>()
const oyentesFrame = new Set<(f: FrameNuevo) => void>()
let ultimoFrame: FrameNuevo = { jpeg: null, sesion: null }

function suscribir(f: () => void) {
  oyentes.add(f)
  return () => { oyentes.delete(f) }
}

function fijar(cambios: Partial<Instantanea>) {
  actual = { ...actual, ...cambios }
  oyentes.forEach((f) => f())
}

export function alFrame(f: (frame: FrameNuevo) => void): () => void {
  oyentesFrame.add(f)
  f(ultimoFrame)
  return () => { oyentesFrame.delete(f) }
}

/** Arranca el bucle de lectura. Se llama una vez al abrir la interfaz. */
export async function arrancar(bridge: Bridge): Promise<void> {
  const info = await bridge.info()
  fijar({ info, plan: info.rutina })
  let version = -1
  for (;;) {
    let e: Estado | null = null
    try {
      e = await bridge.estado(version)
    } catch (err) {
      console.error('estado()', err)
      await new Promise((r) => setTimeout(r, 500))
      continue
    }
    if (!e) continue
    version = e.version
    const { frame, ...resto } = e
    fijar({ estado: { ...resto, frame: null } })
    ultimoFrame = { jpeg: frame, sesion: e.sesion }
    oyentesFrame.forEach((f) => f(ultimoFrame))
  }
}

/**
 * Empieza la sesión con la rutina elegida. El plan se fija antes de llamar a
 * Python (el estado de la sesión puede llegar antes de que `iniciar` vuelva)
 * y se deshace si Python la rechaza.
 */
export async function iniciarRutina(bridge: Bridge, plan: Plan,
                                    opciones?: OpcionesInicio): Promise<boolean> {
  const anterior = actual.plan
  fijar({ plan })
  const pasos = plan.pasos.map((p) => ({ skillId: p.skillId, objetivo: p.objetivo }))
  let ok = false
  try {
    ok = await bridge.iniciar({ ...opciones, nombre: plan.nombre, pasos })
  } catch (err) {
    console.error('iniciar()', err)
  }
  if (!ok) fijar({ plan: anterior })
  return ok
}

/** Lee una parte del estado; re-renderiza solo si `igual` dice que cambió. */
export function useEstado<T>(selector: (s: Instantanea) => T,
                             igual: (a: T, b: T) => boolean = Object.is): T {
  const cache = useRef<{ valor: T } | null>(null)
  const leer = () => {
    const nuevo = selector(actual)
    if (cache.current && igual(cache.current.valor, nuevo)) return cache.current.valor
    cache.current = { valor: nuevo }
    return nuevo
  }
  return useSyncExternalStore(suscribir, leer)
}

const SIN_CAPACIDADES: Capacidades = {
  nivel: false, correctasConError: false, guia: false, resumenTexto: false,
  motivoSilencio: false, pausaManual: false, colocacion: false, avisoLuz: false,
}

/** ¿El backend ya tiene esta función? Si no, la interfaz no la muestra. */
export function useCapacidad(nombre: keyof Capacidades): boolean {
  return useEstado((s) => (s.info?.capacidades ?? SIN_CAPACIDADES)[nombre] === true)
}

export const iguales = {
  arreglo: <T>(a: readonly T[], b: readonly T[]) => a.length === b.length && a.every((x, i) => Object.is(x, b[i])),
}
