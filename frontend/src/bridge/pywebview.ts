import type {
  AjustesPython, Bridge, DatosPerfil, Estado, EstadoPerfiles, Info, OpcionesInicio, PasoElegido, Progreso,
  ResultadoPerfil,
} from './tipos'

// Métodos de `backend/estela/adaptadores/interfaz/ventana.py:Api`, publicados por pywebview.
interface ApiPython {
  info(): Promise<Info>
  estado(desde: number): Promise<Estado | null>
  iniciar(opciones: OpcionesInicio | null): Promise<boolean>
  siguiente(): Promise<void>
  reiniciar(): Promise<void>
  terminar(): Promise<void>
  volver_al_inicio(): Promise<void>
  salir(): Promise<void>
  // solo con la capacidad «silenciarVoz»
  configurar?(ajustes: AjustesPython): Promise<void>
  // solo con la capacidad «historial»
  historial?(): Promise<Progreso | null>
  borrar_historial?(): Promise<boolean>
  // solo con la capacidad «perfiles»
  perfiles?(): Promise<EstadoPerfiles | null>
  elegir_perfil?(id: string | null): Promise<boolean>
  crear_perfil?(datos: DatosPerfil): Promise<ResultadoPerfil>
  editar_perfil?(id: string, datos: DatosPerfil): Promise<ResultadoPerfil>
  borrar_perfil?(id: string): Promise<boolean>
  guardar_rutina?(perfilId: string, pasos: PasoElegido[]): Promise<ResultadoPerfil>
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

const SIN_PERFILES: ResultadoPerfil = { ok: false, error: 'Los perfiles no están disponibles.' }

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
    configurar: async (ajustes) => { await api.configurar?.(ajustes) },
    historial: async () => (await api.historial?.()) ?? null,
    borrarHistorial: async () => (await api.borrar_historial?.()) ?? false,
    perfiles: async () => (await api.perfiles?.()) ?? null,
    elegirPerfil: async (id) => (await api.elegir_perfil?.(id)) ?? false,
    crearPerfil: async (datos) => (await api.crear_perfil?.(datos)) ?? SIN_PERFILES,
    editarPerfil: async (id, datos) => (await api.editar_perfil?.(id, datos)) ?? SIN_PERFILES,
    borrarPerfil: async (id) => (await api.borrar_perfil?.(id)) ?? false,
    guardarRutina: async (perfilId, pasos) => (await api.guardar_rutina?.(perfilId, pasos)) ?? SIN_PERFILES,
    pausar: async () => { await api.pausar?.() },
    reanudar: async () => { await api.reanudar?.() },
  }
}
