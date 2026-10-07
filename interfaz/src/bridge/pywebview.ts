import type { Bridge, Estado, Info, OpcionesInicio } from './tipos'

// Métodos de `estela/ui/ventana.py:Api`, publicados por pywebview.
interface ApiPython {
  info(): Promise<Info>
  estado(desde: number): Promise<Estado | null>
  iniciar(opciones: OpcionesInicio | null): Promise<boolean>
  siguiente(): Promise<void>
  reiniciar(): Promise<void>
  terminar(): Promise<void>
  volver_al_inicio(): Promise<void>
  salir(): Promise<void>
  // aún no existen en Python (capacidad «pausaManual»)
  pausar?(): Promise<void>
  reanudar?(): Promise<void>
}

declare global {
  interface Window {
    pywebview?: { api: ApiPython }
  }
}

/** Espera a que pywebview publique la API, o null si no estamos en la ventana. */
export function esperarPywebview(timeoutMs: number): Promise<ApiPython | null> {
  return new Promise((resolve) => {
    const lista = () => (window.pywebview?.api && 'estado' in window.pywebview.api
      ? window.pywebview.api : null)
    if (lista()) return resolve(lista())
    const alListo = () => resolve(lista())
    window.addEventListener('pywebviewready', alListo, { once: true })
    setTimeout(() => {
      window.removeEventListener('pywebviewready', alListo)
      resolve(lista())
    }, timeoutMs)
  })
}

export function bridgePywebview(api: ApiPython): Bridge {
  return {
    info: () => api.info(),
    estado: (desde) => api.estado(desde),
    iniciar: (opciones) => api.iniciar(opciones ?? null),
    siguiente: () => api.siguiente(),
    reiniciar: () => api.reiniciar(),
    terminar: () => api.terminar(),
    volverAlInicio: () => api.volver_al_inicio(),
    salir: () => api.salir(),
    pausar: async () => { await api.pausar?.() },
    reanudar: async () => { await api.reanudar?.() },
  }
}
