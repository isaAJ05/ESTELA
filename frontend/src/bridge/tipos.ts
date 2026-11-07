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
  /** la usuaria puede activar el aviso «ese movimiento no es el de ahora» (`configurar`) */
  reconocerEjercicio?: boolean
  /** las sesiones se guardan en este equipo y hay panel «Mi progreso» (ADR-008) */
  historial?: boolean
  /** varias personas en el equipo, cada una con su historial (ADR-009) */
  perfiles?: boolean
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
  /** si la sesión entró en el historial; null sin la capacidad «historial» */
  guardadaEnHistorial?: boolean | null
  /** para el equipo (tecla D), no para la usuaria */
  tecnico: {
    frames: number
    framesSinPersona: number
    latencias: Record<string, { p50Ms: number; p95Ms: number; n: number }>
  }
}

// -- Historial y progreso (capacidad «historial», ADR-008) ----------------------
// Miden constancia y qué indicaciones se recibieron; no miden la técnica.

export interface SemanaProgreso {
  /** lunes de la semana, AAAA-MM-DD */
  inicio: string
  sesiones: number
  duracionS: number
}

export interface IndicacionFrecuente {
  errorId: string
  /** la frase que se dijo */
  texto: string
  /** en cuántas de las últimas sesiones de este ejercicio apareció */
  sesiones: number
  veces: number
}

export interface EjercicioProgreso {
  skillId: string
  nombre: string
  unidad: Unidad
  /** sesiones en las que se hizo (con algo contado) */
  veces: number
  /** fecha y hora local ISO */
  ultimaFecha: string
  ultimo: { completadas: number; objetivo: number }
  mejor: number
  objetivoCumplido: number
  recientes: { fecha: string; completadas: number; objetivo: number }[]
  indicaciones: { sesiones: number; frecuentes: IndicacionFrecuente[] }
}

export interface SesionHistorial {
  fecha: string
  rutina: string
  terminada: boolean
  duracionS: number
  ejercicios: number
  completos: number
  indicaciones: number
  pasos: { skillId: string; nombre: string; unidad: Unidad; completadas: number; objetivo: number }[]
}

export interface Progreso {
  totalSesiones: number
  totalDuracionS: number
  diasActivos: number
  diasActivos7: number
  /** días con sesión de lunes a hoy (para la meta semanal) */
  diasSemanaActual: number
  /** meta del perfil, en días por semana; null sin meta */
  metaSemanal: number | null
  rachaDias: number
  primeraFecha: string | null
  /** últimas 8 semanas, de la más antigua a la actual */
  semanas: SemanaProgreso[]
  /** el usado más recientemente primero */
  ejercicios: EjercicioProgreso[]
  /** la más reciente primero */
  sesiones: SesionHistorial[]
}

// -- Perfiles (capacidad «perfiles», ADR-009) -------------------------------------
// Solo nombre, color del avatar y meta: nada del cuerpo. Sin contraseña.

export interface Perfil {
  id: string
  nombre: string
  /** una de `EstadoPerfiles.colores`; la interfaz la traduce a su paleta */
  color: string
  /** días por semana; null sin meta */
  metaSemanal: number | null
  creado: string | null
  /** última rutina armada en «Mi rutina»; null si aún no armó ninguna */
  rutina: PasoElegido[] | null
}

export interface EstadoPerfiles {
  perfiles: Perfil[]
  /** quién entrena; null = sin perfil (no se guarda nada) */
  activo: string | null
  /** ya se eligió en esta ejecución (un perfil o «sin perfil»); si no, se pregunta */
  elegido: boolean
  colores: string[]
  maxPerfiles: number
  maxNombre: number
  /** [mínimo, máximo] de la meta semanal */
  meta: [number, number]
}

export interface DatosPerfil {
  nombre?: string
  color?: string
  metaSemanal?: number | null
}

export type ResultadoPerfil = { ok: true; perfil: Perfil } | { ok: false; error: string }

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

export interface PasoElegido {
  skillId: string
  objetivo: number
}

export interface OpcionesInicio {
  nivel?: Nivel
  /** rutina elegida por la usuaria; sin ella se repite la última */
  nombre?: string
  pasos?: PasoElegido[]
}

/** Ajustes que Python aplica en cualquier fase (capacidad «silenciarVoz»). */
export interface AjustesPython {
  voz?: boolean
  /** capacidad «reconocerEjercicio»; empieza desactivado */
  reconocer?: boolean
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
  /** Panel «Mi progreso»; null sin la capacidad «historial». */
  historial(): Promise<Progreso | null>
  borrarHistorial(): Promise<boolean>
  /** Perfiles; null sin la capacidad «perfiles». */
  perfiles(): Promise<EstadoPerfiles | null>
  /** null: entrenar sin perfil */
  elegirPerfil(id: string | null): Promise<boolean>
  crearPerfil(datos: DatosPerfil): Promise<ResultadoPerfil>
  editarPerfil(id: string, datos: DatosPerfil): Promise<ResultadoPerfil>
  borrarPerfil(id: string): Promise<boolean>
  /** Guarda en ese perfil la rutina de «Mi rutina» (Python la valida como en `iniciar`). */
  guardarRutina(perfilId: string, pasos: PasoElegido[]): Promise<ResultadoPerfil>
  /** Solo con la capacidad «pausaManual». */
  pausar(): Promise<void>
  reanudar(): Promise<void>
}
