import { bridgePywebview, esperarPywebview } from './pywebview'
import { bridgeSimulado } from './simulado'
import type { Bridge } from './tipos'

export type { Bridge } from './tipos'

/**
 * Dentro de la ventana de `python -m estela` usa la API de Python. En el
 * navegador (`npm run dev`, o `?simulado` en el build) usa el simulador.
 * Devuelve null si el build se abrió fuera de la ventana.
 */
export async function conectar(): Promise<Bridge | null> {
  const forzarSimulado = new URLSearchParams(location.search).has('simulado')
  if (!forzarSimulado) {
    const api = await esperarPywebview(import.meta.env.DEV ? 400 : 3000)
    if (api) return bridgePywebview(api)
  }
  if (forzarSimulado || import.meta.env.DEV) return bridgeSimulado()
  return null
}
