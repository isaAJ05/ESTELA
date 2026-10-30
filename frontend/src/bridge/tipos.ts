// Contrato de datos con Python. Espejo de `backend/estela/adaptadores/interfaz/contrato.py`:
// si cambia un nombre allí, cambia aquí.

export type Unidad = 'repeticiones' | 'segundos'
export type Orientacion = 'frente' | 'perfil'
export type Nivel = 'principiante' | 'avanzado'
export type Fase = 'inicio' | 'preparando' | 'sesion' | 'resumen' | 'error'
export type TipoAviso = 'encuadre' | 'sin_persona' | 'orientacion' | 'pausa' | 'otro'
export type MotivoPausa = 'sin_persona' | 'inactividad'
export type Lado = 'izquierdo' | 'derecho' | 'bilateral' | 'na'
export type Severidad = 'leve' | 'moderada' | 'alta'

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
  /** la usuaria puede elegir ejercicios y objetivos antes de empezar */
  rutinaPersonalizada?: boolean
  /** la usuaria puede silenciar las indicaciones habladas (`configurar`) */
  silenciarVoz?: boolean
  /** se puede analizar un vídeo elegido en el inicio (prueba del equipo) */
  probarVideo?: boolean
}

export interface PasoRutina {
  skillId: string
  nombre: string
  orientacion: Orientacion | null
  unidad: Unidad
  objetivo: number
  /** Postura representativa de la referencia, sin animación. */
  guia: Punto[] | null
}

/** Cómo se cuenta: ciclo completo, una por cada pierna que se eleva, o segundos. */
export type Conteo = 'ciclo' | 'alternante' | 'isometrico'

/** Un ejercicio que se puede añadir a la rutina, con los límites de su objetivo. */
export interface EjercicioCatalogo extends PasoRutina {
  descripcion: string | null
  conteo: Conteo
  minimo: number
  maximo: number
}

export interface Info {
  version: number
  capacidades: Capacidades
  rutina: { nombre: string; pasos: PasoRutina[] }
  /** ejercicios disponibles (capacidad «rutinaPersonalizada») */
  catalogo?: EjercicioCatalogo[]
  /** pares de índices de los puntos que forman el esqueleto */
  conexiones: [number, number][]
  /** dibujar en espejo (cámara en vivo) */
  espejo: boolean
  fuente: 'camara' | 'video'
}

/**
 * Última indicación del motor de feedback, ya decidida por el backend.
 * Un refuerzo («vas bien») no nombra segmento ni lado.
 */
export interface Feedback {
  texto: string
  tipo: 'correccion' | 'refuerzo'
  errorId: string | null
  segmento: string | null
  lado: Lado | null
  severidad: Severidad | null
  /** índices de las articulaciones del segmento, para resaltarlas */
  puntos: number[]
  /** ángulos de la medida que disparó la corrección (para señalarlos) */
  angulos: string[]
  /** cuánto se pasó del umbral, en grados o unidades de la medida */
  magnitud: number | null
  direccion: string | null
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
  feedback: Feedback | null
  pausada: boolean
  motivoPausa: MotivoPausa | null
  puntos: Punto[] | null
  /** ángulos medidos en el frame (los mismos que usa el motor), para mostrarlos */
  angulos?: {
    /** importante: es uno de los ángulos que cuentan en este ejercicio */
    /** indices: dónde dibujarlo; se usa el más visible (p. ej. la oreja que se ve de perfil) */
    articulaciones: { nombre: string; indices: number[]; grados: number; importante: boolean }[]
    /** ángulos importantes que no están en una articulación (tronco, pelvis…) */
    otros: { nombre: string; grados: number }[]
  } | null
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
  segmento: string | null
  lado: Lado | null
  severidad: Severidad | null
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
  /** fuente de la sesión actual o la última (puede ser un vídeo de prueba) */
  fuente?: 'camara' | 'video'
  espejo?: boolean
  /** nombre del vídeo de prueba, o null */
  video?: string | null
}

export interface PasoElegido {
  skillId: string
  objetivo: number
}

export interface OpcionesInicio {
  nivel?: Nivel
  /** rutina elegida por la usuaria; sin ella se repite la última */
  nombre?: string
  pasos?: PasoElegido[]
  /** ruta de un vídeo a analizar en lugar de la cámara (capacidad «probarVideo») */
  video?: string
}

/** Ajustes que Python aplica en cualquier fase (capacidad «silenciarVoz»). */
export interface AjustesPython {
  voz?: boolean
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
  configurar(ajustes: AjustesPython): Promise<void>
  /** Diálogo para elegir un vídeo de prueba: su ruta, o null si se cancela. */
  elegirVideo(): Promise<string | null>
  /** Solo con la capacidad «pausaManual». */
  pausar(): Promise<void>
  reanudar(): Promise<void>
}
