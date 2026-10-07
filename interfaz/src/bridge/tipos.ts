// Contrato de datos con Python. Espejo de `estela/ui/contrato.py`:
// si cambia un nombre allí, cambia aquí.

export type Unidad = 'repeticiones' | 'segundos'
export type Orientacion = 'frente' | 'perfil'
export type Nivel = 'principiante' | 'avanzado'
export type Fase = 'inicio' | 'preparando' | 'sesion' | 'resumen' | 'error'
export type TipoAviso = 'encuadre' | 'sin_persona' | 'orientacion' | 'pausa' | 'otro'
export type MotivoPausa = 'sin_persona' | 'inactividad'

/** [x, y, visibilidad], x e y normalizados al frame (0..1). */
export type Punto = [number, number, number]

/**
 * Funciones que dependen de algo que el backend todavía no tiene.
 * Mientras estén en false, la interfaz no las muestra (ver `contrato.py`).
 */
export interface Capacidades {
  nivel: boolean
  correctasConError: boolean
  guia: boolean
  resumenTexto: boolean
  motivoSilencio: boolean
  pausaManual: boolean
  colocacion: boolean
  avisoLuz: boolean
}

export interface PasoRutina {
  skillId: string
  nombre: string
  orientacion: Orientacion | null
  unidad: Unidad
  objetivo: number
}

export interface Info {
  version: number
  capacidades: Capacidades
  rutina: { nombre: string; pasos: PasoRutina[] }
  /** pares de índices de los puntos que forman el esqueleto */
  conexiones: [number, number][]
  /** dibujar en espejo (cámara en vivo) */
  espejo: boolean
  fuente: 'camara' | 'video'
}

export interface EstadoSesion {
  ejercicio: string
  ejercicioId: string
  paso: number
  totalPasos: number
  objetivo: number
  unidad: Unidad
  completadas: number
  incompletas: number
  fase: string
  persona: boolean
  orientacionGrados: number | null
  aviso: string | null
  avisoTipo: TipoAviso | null
  ultimoMensaje: string | null
  /** cambia con cada mensaje nuevo, aunque el texto se repita */
  mensajesEmitidos: number
  pausada: boolean
  motivoPausa: MotivoPausa | null
  puntos: Punto[] | null
  terminada: boolean
  // Aún sin backend: llegan null (ver Capacidades).
  correctas: number | null
  conError: number | null
  nivel: Nivel | null
  guia: Punto[] | null
  depuracion: {
    fps: number | null
    latenciaMs: Record<string, number>
    motivoSilencio: string | null
  }
}

export interface MensajeResumen {
  tMs: number
  texto: string
  errorId: string | null
  repeticion: number
}

export interface PasoResumen {
  skillId: string
  nombre: string
  unidad: Unidad
  objetivo: number
  completadas: number
  incompletas: number
  correctas: number | null
  conError: number | null
  duracionS: number
  pausas: number
  pausaS: number
  mensajes: MensajeResumen[]
  /** veces que el motor no corrigió, por motivo (panel técnico) */
  abstenciones: Record<string, number>
}

/** completada · usuaria (pulsó terminar) · fuente (vídeo acabado o cámara perdida) · cierre · error */
export type MotivoFin = 'completada' | 'usuaria' | 'fuente' | 'cierre' | 'error'

export interface Resumen {
  rutina: string
  terminada: boolean
  motivoFin: MotivoFin | null
  duracionTotalS: number
  pasos: PasoResumen[]
  resumenTexto: string | null
  /** para el equipo (tecla D), no para la usuaria */
  tecnico: {
    frames: number
    framesSinPersona: number
    latencias: Record<string, { p50Ms: number; p95Ms: number; n: number }>
  }
}

export interface ErrorApp {
  tipo: 'fuente' | 'modelo'
  mensaje: string
}

export interface Estado {
  version: number
  fase: Fase
  error: ErrorApp | null
  sesion: EstadoSesion | null
  resumen: Resumen | null
  /** JPEG en base64 del último frame (sin espejo), o null */
  frame: string | null
}

export interface OpcionesInicio {
  nivel?: Nivel
}

/** Lo que la interfaz puede pedirle a Python. */
export interface Bridge {
  info(): Promise<Info>
  /** Estado más nuevo que `desde`, o null si no hubo cambios (long polling). */
  estado(desde: number): Promise<Estado | null>
  iniciar(opciones?: OpcionesInicio): Promise<boolean>
  siguiente(): Promise<void>
  reiniciar(): Promise<void>
  terminar(): Promise<void>
  volverAlInicio(): Promise<void>
  salir(): Promise<void>
  /** Solo con la capacidad «pausaManual». */
  pausar(): Promise<void>
  reanudar(): Promise<void>
}
