// Backend simulado para trabajar la interfaz sin cámara ni Python (`npm run dev`).
// Imita al orquestador: fases, conteo, mensajes, avisos y una pausa. No tiene
// ninguna lógica de detección real.
//
// Parámetros de la URL: ?simulado            fuerza el simulador en el build
//                       ?velocidad=4         acelera el tiempo
//                       ?escena=resumen|error empieza en esa fase
//                       ?escena=progreso-vacio  «Mi progreso» sin sesiones
//                       ?escena=sin-perfiles    primera vez: aún no hay perfiles

import type {
  Bridge, DatosPerfil, EjercicioCatalogo, Estado, EstadoSesion, Feedback, Info, Lado, MensajeResumen, OpcionesInicio,
  PasoRutina, Perfil, Progreso, Punto, Resumen, ResultadoPerfil, Severidad,
} from './tipos'

const PASOS: PasoRutina[] = [
  { skillId: 'jumping_jacks', nombre: 'Jumping jacks', orientacion: 'frente', unidad: 'repeticiones', objetivo: 10, guia: null },
  { skillId: 'abduccion_cadera_izq', nombre: 'Abducción de cadera de pie, pierna izquierda', orientacion: 'frente', unidad: 'repeticiones', objetivo: 8, guia: null },
  { skillId: 'abduccion_cadera_der', nombre: 'Abducción de cadera de pie, pierna derecha', orientacion: 'frente', unidad: 'repeticiones', objetivo: 8, guia: null },
  { skillId: 'marcha_rodillas', nombre: 'Marcha con elevación de rodillas', orientacion: 'perfil', unidad: 'repeticiones', objetivo: 16, guia: null },
  { skillId: 'zancada_atras_izq', nombre: 'Zancada atrás estática, pierna izquierda atrás', orientacion: 'perfil', unidad: 'repeticiones', objetivo: 6, guia: null },
  { skillId: 'zancada_atras_der', nombre: 'Zancada atrás estática, pierna derecha atrás', orientacion: 'perfil', unidad: 'repeticiones', objetivo: 6, guia: null },
  { skillId: 'plancha', nombre: 'Plancha', orientacion: 'perfil', unidad: 'segundos', objetivo: 20, guia: null },
]

const DESCRIPCION: Record<string, string> = {
  jumping_jacks: 'Abre y cierra brazos y piernas a la vez, con un pequeño salto.',
  abduccion_cadera_izq: 'De pie, eleva la pierna izquierda hacia el lado sin inclinar el tronco.',
  abduccion_cadera_der: 'De pie, eleva la pierna derecha hacia el lado sin inclinar el tronco.',
  marcha_rodillas: 'Marcha en el sitio subiendo las rodillas, con el tronco erguido.',
  plancha: 'Sostén el cuerpo en línea recta apoyado en antebrazos y puntas de los pies.',
}

const CATALOGO: EjercicioCatalogo[] = PASOS.filter((p) => !p.skillId.startsWith('zancada')).map((p) => ({
  ...p,
  descripcion: DESCRIPCION[p.skillId] ?? null,
  conteo: p.unidad === 'segundos' ? 'isometrico' : p.skillId === 'marcha_rodillas' ? 'alternante' : 'ciclo',
  minimo: p.unidad === 'segundos' ? 5 : 1,
  maximo: p.unidad === 'segundos' ? 180 : 50,
}))

const VACIO: Progreso = {
  totalSesiones: 0, totalDuracionS: 0, diasActivos: 0, diasActivos7: 0, diasSemanaActual: 0, metaSemanal: null,
  rachaDias: 0, primeraFecha: null, semanas: [], ejercicios: [], sesiones: [],
}

// Perfiles en memoria, con las mismas reglas que `backend/estela/aplicacion/perfiles.py`.
const COLORES = ['violeta', 'naranja', 'turquesa', 'rosa', 'azul', 'mostaza']
const MAX_PERFILES = 8
const MAX_NOMBRE = 30

function limpiarPerfil(d: DatosPerfil, otros: Perfil[], base?: Perfil): Omit<Perfil, 'id' | 'creado' | 'rutina'> | string {
  const nombre = (d.nombre ?? base?.nombre ?? '').trim().split(/\s+/).filter(Boolean).join(' ')
  if (!nombre) return 'Escribe un nombre o apodo.'
  if (nombre.length > MAX_NOMBRE) return `El nombre puede tener hasta ${MAX_NOMBRE} caracteres.`
  if (otros.some((p) => p.nombre.toLowerCase() === nombre.toLowerCase())) return 'Ya hay un perfil con ese nombre.'
  const color = d.color ?? base?.color ?? COLORES[0]
  if (!COLORES.includes(color)) return 'Elige uno de los colores disponibles.'
  const metaSemanal = 'metaSemanal' in d ? d.metaSemanal ?? null : base?.metaSemanal ?? null
  if (metaSemanal != null && (metaSemanal < 1 || metaSemanal > 7)) return 'La meta debe estar entre 1 y 7 días por semana.'
  return { nombre, color, metaSemanal }
}

const iso = (d: Date) => {
  const dos = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())}T${dos(d.getHours())}:${dos(d.getMinutes())}:00`
}

/** Historial inventado de unas semanas, con huecos, para ver el panel sin Python. */
function progresoSimulado(hoy = new Date()): Progreso {
  const dia = (hace: number, hora = 8) => new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - hace, hora, 15)
  const haceDias = [0, 1, 2, 4, 6, 9, 10, 13, 16, 20, 23, 27, 30, 34, 41, 48]
  const lunes = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - ((hoy.getDay() + 6) % 7))
  const semanas = Array.from({ length: 8 }, (_, k) => {
    const inicio = new Date(lunes.getFullYear(), lunes.getMonth(), lunes.getDate() - 7 * (7 - k))
    const fin = new Date(inicio.getFullYear(), inicio.getMonth(), inicio.getDate() + 7)
    const n = haceDias.filter((h) => { const d = dia(h); return d >= inicio && d < fin }).length
    return { inicio: iso(inicio).slice(0, 10), sesiones: n, duracionS: n * (240 + 25 * k) }
  })
  const pasos = (k: number) => [
    { skillId: 'jumping_jacks', nombre: 'Jumping jacks', unidad: 'repeticiones' as const, completadas: Math.min(10, 6 + (k % 5)), objetivo: 10 },
    { skillId: 'marcha_rodillas', nombre: 'Marcha con elevación de rodillas', unidad: 'repeticiones' as const, completadas: 16, objetivo: 16 },
    { skillId: 'plancha', nombre: 'Plancha', unidad: 'segundos' as const, completadas: 12 + (k % 9), objetivo: 20 },
  ]
  const sesiones = haceDias.map((h, k) => {
    const ps = pasos(haceDias.length - k)
    return {
      fecha: iso(dia(h, 7 + (k % 3) * 5)), rutina: 'Rutina de entrenamiento', terminada: k !== 3,
      duracionS: 240 + 17 * k, ejercicios: ps.length, completos: ps.filter((p) => p.completadas >= p.objetivo).length,
      indicaciones: k % 4, pasos: ps,
    }
  })
  const recientes = (sid: string) => sesiones.slice(0, 10).reverse().map((s) => {
    const p = s.pasos.find((q) => q.skillId === sid)!
    return { fecha: s.fecha, completadas: p.completadas, objetivo: p.objetivo }
  })
  const ejercicio = (sid: string, nombre: string, unidad: 'repeticiones' | 'segundos',
                     frecuentes: Progreso['ejercicios'][number]['indicaciones']['frecuentes']) => {
    const r = recientes(sid)
    return {
      skillId: sid, nombre, unidad, veces: sesiones.length, ultimaFecha: sesiones[0].fecha,
      ultimo: { completadas: r.at(-1)!.completadas, objetivo: r.at(-1)!.objetivo },
      mejor: Math.max(...r.map((x) => x.completadas)),
      objetivoCumplido: sesiones.filter((s) => s.pasos.some((q) => q.skillId === sid && q.completadas >= q.objetivo)).length,
      recientes: r, indicaciones: { sesiones: 5, frecuentes },
    }
  }
  return {
    totalSesiones: sesiones.length,
    totalDuracionS: sesiones.reduce((a, s) => a + s.duracionS, 0),
    diasActivos: sesiones.length,
    diasActivos7: haceDias.filter((h) => h < 7).length,
    diasSemanaActual: haceDias.filter((h) => h <= (hoy.getDay() + 6) % 7).length,
    metaSemanal: null,
    rachaDias: 3,
    primeraFecha: sesiones.at(-1)!.fecha,
    semanas,
    ejercicios: [
      ejercicio('jumping_jacks', 'Jumping jacks', 'repeticiones', [
        { errorId: 'brazos_no_llegan_arriba', texto: 'Sube un poco más los brazos.', sesiones: 3, veces: 5 },
        { errorId: 'codos_flexionados', texto: 'Estira los codos al abrir.', sesiones: 1, veces: 1 }]),
      ejercicio('marcha_rodillas', 'Marcha con elevación de rodillas', 'repeticiones', []),
      ejercicio('plancha', 'Plancha', 'segundos', [
        { errorId: 'cadera_hundida', texto: 'Sube un poco la cadera.', sesiones: 4, veces: 7 }]),
    ],
    sesiones,
  }
}

const CONEXIONES: [number, number][] = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [11, 23], [12, 24], [23, 24],
  [23, 25], [25, 27], [27, 29], [29, 31], [27, 31], [24, 26], [26, 28], [28, 30], [30, 32], [28, 32],
]

// Mismos índices que `puntos_de_segmento` en backend/estela/adaptadores/pose/landmarks.py
const correccion = (texto: string, segmento: string, lado: Lado, severidad: Severidad, puntos: number[]): Feedback =>
  ({ texto, tipo: 'correccion', errorId: `${segmento}_simulado`, segmento, lado, severidad, puntos, angulos: [], magnitud: null, direccion: null })
const refuerzo = (texto: string): Feedback =>
  ({ texto, tipo: 'refuerzo', errorId: null, segmento: null, lado: null, severidad: null, puntos: [], angulos: [], magnitud: null, direccion: null })
const TRONCO = [11, 12, 23, 24]

const MENSAJES: Record<string, Feedback[]> = {
  jumping_jacks: [correccion('Sube un poco más los brazos.', 'brazo', 'bilateral', 'moderada', [11, 12, 13, 14, 15, 16]), refuerzo('¡Vas muy bien!')],
  abduccion_cadera_izq: [correccion('Mantén el tronco recto, sin inclinarte.', 'tronco', 'na', 'leve', TRONCO)],
  abduccion_cadera_der: [correccion('Mantén el tronco recto, sin inclinarte.', 'tronco', 'na', 'leve', TRONCO)],
  marcha_rodillas: [correccion('Sube un poco más las rodillas.', 'rodilla', 'bilateral', 'moderada', [25, 26]), correccion('Endereza un poco el tronco.', 'tronco', 'na', 'alta', TRONCO)],
  zancada_atras_izq: [correccion('Endereza un poco el tronco.', 'tronco', 'na', 'moderada', TRONCO), correccion('Baja un poco más la rodilla.', 'rodilla', 'derecho', 'leve', [26])],
  zancada_atras_der: [correccion('Endereza un poco el tronco.', 'tronco', 'na', 'moderada', TRONCO)],
  plancha: [correccion('Sube un poco la cadera.', 'cadera', 'bilateral', 'alta', [23, 24])],
}

const SEG_POR_REP = 2.4
const PASO_CON_PAUSA = 1         // índice del paso donde se simula una pausa
const PAUSA = { desdeRep: 3, duracionS: 4 }
// colocación al empezar cada paso: se cumplen persona, orientación y cuerpo entero
// en estos segundos y a los COLOCACION_S empieza a contar (o con «Listo»)
const COLOCACION = { persona: 0.4, orientacion: 1.2, cuerpoEntero: 2.0 }
const COLOCACION_S = 3.5

// -- esqueleto sintético ------------------------------------------------------

function esqueleto(skillId: string, fase: number): Punto[] {
  const p: Punto[] = Array.from({ length: 33 }, () => [0.5, 0.5, 0.95])
  const s = (1 - Math.cos(2 * Math.PI * fase)) / 2            // 0 → 1 → 0
  const set = (i: number, x: number, y: number, v = 0.95) => { p[i] = [x, y, v] }
  const cara = (x: number, y: number) => { for (let i = 0; i <= 10; i++) set(i, x + (i % 3 - 1) * 0.008, y + (i > 8 ? 0.02 : -0.005)) }
  const pie = (tobillo: number, talon: number, punta: number, x: number, y: number, dir = 1) => {
    set(tobillo, x, y); set(talon, x - 0.012 * dir, y + 0.02); set(punta, x + 0.03 * dir, y + 0.025)
  }
  const mano = (muneca: number, x: number, y: number) => { set(muneca, x, y); for (const i of [17, 19, 21, 18, 20, 22]) if ((i % 2) === (muneca % 2)) set(i, x, y + 0.015) }

  if (skillId === 'plancha') {
    const y = 0.62 + 0.004 * Math.sin(2 * Math.PI * fase)
    cara(0.24, y - 0.05)
    set(11, 0.3, y - 0.02); set(12, 0.3, y - 0.02, 0.4)
    set(13, 0.31, y + 0.1); set(14, 0.31, y + 0.1, 0.4)
    mano(15, 0.36, y + 0.11); mano(16, 0.36, y + 0.11)
    set(23, 0.52, y); set(24, 0.52, y, 0.4)
    set(25, 0.66, y + 0.03); set(26, 0.66, y + 0.03, 0.4)
    pie(27, 29, 31, 0.8, y + 0.06); pie(28, 30, 32, 0.8, y + 0.06)
    return p
  }

  const perfil = skillId.startsWith('marcha') || skillId.startsWith('zancada')
  if (!perfil) {
    const brazos = skillId === 'jumping_jacks' ? s : 0.1
    const abre = skillId === 'jumping_jacks' ? s * 0.07 : 0
    const izq = skillId === 'abduccion_cadera_izq' ? s : 0
    const der = skillId === 'abduccion_cadera_der' ? s : 0
    cara(0.5, 0.17)
    set(11, 0.56, 0.27); set(12, 0.44, 0.27)
    const ang = (0.15 + brazos * 0.8) * Math.PI
    set(13, 0.56 + 0.11 * Math.sin(ang), 0.27 + 0.11 * Math.cos(ang))
    set(14, 0.44 - 0.11 * Math.sin(ang), 0.27 + 0.11 * Math.cos(ang))
    mano(15, 0.56 + 0.21 * Math.sin(ang), 0.27 + 0.21 * Math.cos(ang))
    mano(16, 0.44 - 0.21 * Math.sin(ang), 0.27 + 0.21 * Math.cos(ang))
    set(23, 0.535, 0.5); set(24, 0.465, 0.5)
    const pierna = (rodilla: number, tob: number, tal: number, pun: number, x0: number, lado: number, abd: number) => {
      const a = abd * 0.45 + abre * 2.2
      set(rodilla, x0 + lado * 0.18 * Math.sin(a), 0.5 + 0.18 * Math.cos(a))
      pie(tob, tal, pun, x0 + lado * 0.36 * Math.sin(a), 0.5 + 0.36 * Math.cos(a), lado)
    }
    pierna(25, 27, 29, 31, 0.535, 1, izq)
    pierna(26, 28, 30, 32, 0.465, -1, der)
    return p
  }

  // de perfil, mirando hacia la derecha
  const zancada = skillId.startsWith('zancada')
  const baja = zancada ? s * 0.12 : 0
  const x = 0.5
  cara(x + 0.02, 0.17 + baja)
  set(11, x, 0.27 + baja); set(12, x, 0.27 + baja, 0.45)
  set(13, x + 0.01, 0.38 + baja); set(14, x + 0.01, 0.38 + baja, 0.45)
  mano(15, x + 0.03, 0.48 + baja); mano(16, x + 0.03, 0.48 + baja)
  const yc = 0.5 + baja
  set(23, x, yc); set(24, x, yc, 0.45)
  if (zancada) {
    // pierna delantera y pierna de atrás; las dos rodillas se flexionan
    set(25, x + 0.1 + 0.06 * s, yc + 0.16 - 0.04 * s); pie(27, 29, 31, x + 0.12, 0.86, 1)
    set(26, x - 0.08, yc + 0.17 + 0.02 * s, 0.6); pie(28, 30, 32, x - 0.2, 0.86, 1)
  } else {
    const izq = fase < 0.5 ? Math.sin(2 * Math.PI * fase) : 0
    const der = fase >= 0.5 ? -Math.sin(2 * Math.PI * fase) : 0
    set(25, x + 0.16 * izq, yc + 0.18 - 0.1 * izq); pie(27, 29, 31, x + 0.12 * izq, 0.86 - 0.18 * izq, 1)
    set(26, x + 0.16 * der, yc + 0.18 - 0.1 * der, 0.6); pie(28, 30, 32, x + 0.12 * der, 0.86 - 0.18 * der, 1)
  }
  return p
}

// -- simulación ---------------------------------------------------------------

interface PasoHecho {
  paso: PasoRutina
  completadas: number
  incompletas: number
  correctas: number
  conError: number
  duracionS: number
  pausaS: number
  pausas: number
  mensajes: MensajeResumen[]
}

export function bridgeSimulado(): Bridge {
  const url = new URLSearchParams(location.search)
  const velocidad = Number(url.get('velocidad')) || 1
  const escena = url.get('escena')

  let version = 0
  let pasos: PasoRutina[] = CATALOGO
  let nombreRutina = 'Rutina de entrenamiento'
  let fase: Estado['fase'] = 'inicio'
  let error: Estado['error'] = null
  let resumen: Resumen | null = null
  let sesion: EstadoSesion | null = null
  let reloj = 0                // segundos simulados dentro del paso
  let colocadoEn: number | null = null   // reloj al terminar la colocación
  let camara: number | null = null
  let pausaUsuaria = false     // la usuaria pulsó «Pausar»: el reloj se detiene
  let i = 0                    // paso actual
  let mensajesEmitidos = 0
  let ultimoMensaje: string | null = null
  let feedback: Feedback | null = null
  let hechos: PasoHecho[] = []
  let actual: PasoHecho | null = null
  let temporizador: number | undefined
  const esperando: Array<() => void> = []

  const publicar = () => { version++; esperando.splice(0).forEach((f) => f()) }

  const empezarPaso = () => {
    reloj = 0
    pausaUsuaria = false
    colocadoEn = null
    actual = { paso: pasos[i], completadas: 0, incompletas: 0, correctas: 0, conError: 0, duracionS: 0, pausaS: 0, pausas: 0, mensajes: [] }
    hechos[i] = actual           // al volver con «anterior», el intento nuevo sustituye al viejo
  }

  const cerrar = (terminada: boolean) => {
    clearInterval(temporizador)
    resumen = {
      rutina: nombreRutina,
      terminada,
      duracionTotalS: Math.round(hechos.reduce((a, h) => a + h.duracionS, 0) * 10) / 10,
      pasos: hechos.map((h) => ({
        skillId: h.paso.skillId, nombre: h.paso.nombre, unidad: h.paso.unidad, objetivo: h.paso.objetivo,
        completadas: h.completadas, incompletas: h.incompletas, correctas: h.correctas, conError: h.conError,
        duracionS: Math.round(h.duracionS * 10) / 10, pausas: h.pausas, pausaS: h.pausaS, mensajes: h.mensajes,
        abstenciones: { evidencia_insuficiente: h.completadas > 0 ? 2 : 0 },
        umbrales: 'absolutos', respaldos: {}, dtw: { alineado: Math.round(h.duracionS * 27), sin_referencia: 0 },
      })),
      resumenTexto: null,
      guardadaEnHistorial: activo ? hechos.some((h) => h.completadas > 0) : null,
      motivoFin: terminada ? 'completada' : 'usuaria',
      tecnico: {
        frames: Math.round(hechos.reduce((a, h) => a + h.duracionS, 0) * 30),
        framesSinPersona: 120,
        latencias: { pose: { p50Ms: 18.2, p95Ms: 24.9, n: 4200 }, total: { p50Ms: 19.1, p95Ms: 26.3, n: 4200 } },
        voz: { motor: 'simulada', descartadas: 1, descartes: { caducada: 1 } },
      },
    }
    fase = 'resumen'
    sesion = null
    publicar()
  }

  const avanzar = () => {
    i++
    if (i >= pasos.length) return cerrar(true)
    empezarPaso()
  }

  const tic = (dt: number) => {
    if (!actual) return
    const paso = actual.paso
    if (pausaUsuaria) {
      actual.pausaS = Math.round((actual.pausaS + dt) * 10) / 10
      if (sesion) sesion = { ...sesion, pausada: true, motivoPausa: 'usuaria', aviso: 'En pausa.', avisoTipo: 'pausa',
                             evaluacion: { evaluando: false, motivo: 'En pausa' } }
      return
    }
    reloj += dt
    if (colocadoEn === null && reloj >= COLOCACION_S) colocadoEn = reloj
    if (colocadoEn === null) {
      sesion = estadoColocando(paso)
      return
    }
    const t = reloj - colocadoEn       // segundos desde que empezó a contar
    const enPausa = i === PASO_CON_PAUSA
      && t >= PAUSA.desdeRep * SEG_POR_REP && t < PAUSA.desdeRep * SEG_POR_REP + PAUSA.duracionS
    if (enPausa) {
      if (actual.pausas === 0) actual.pausas = 1
      actual.pausaS = Math.round((actual.pausaS + dt) * 10) / 10
    } else {
      actual.duracionS += dt
    }
    const activo = t - (i === PASO_CON_PAUSA && t > PAUSA.desdeRep * SEG_POR_REP
      ? Math.min(PAUSA.duracionS, t - PAUSA.desdeRep * SEG_POR_REP) : 0)
    const antes = actual.completadas
    actual.completadas = Math.min(paso.objetivo,
      paso.unidad === 'segundos' ? Math.floor(activo) : Math.floor(activo / SEG_POR_REP))
    if (paso.skillId === 'marcha_rodillas' && antes < 5 && actual.completadas >= 5) actual.incompletas = 1
    // cada repetición (o segundo) nueva: con error si es de las que llevan corrección
    for (let k = antes + 1; k <= actual.completadas; k++) {
      const conError = paso.unidad === 'segundos' ? k > 6 && k <= 10 : [2, 4].includes(k)
      if (conError) actual.conError++
      else actual.correctas++
    }
    if (paso.unidad === 'repeticiones' && actual.completadas !== antes && [2, 4].includes(actual.completadas)) {
      const lista = MENSAJES[paso.skillId] ?? []
      const fb = lista[(actual.completadas / 2 - 1) % Math.max(lista.length, 1)]
      if (fb) {
        ultimoMensaje = fb.texto
        feedback = fb
        mensajesEmitidos++
        actual.mensajes.push({ tMs: Math.round(t * 1000), texto: fb.texto, errorId: fb.errorId, segmento: fb.segmento,
                               lado: fb.lado, severidad: fb.severidad, repeticion: actual.completadas })
      }
    }
    let aviso: string | null = null
    let avisoTipo: EstadoSesion['avisoTipo'] = null
    if (enPausa) { aviso = 'Pausa. No te veo: vuelve al encuadre para seguir.'; avisoTipo = 'pausa' }
    // tras el anuncio hablado de cada ejercicio, un momento sin evaluar
    const anuncio = t < 1.2
    sesion = {
      ejercicio: paso.nombre, ejercicioId: paso.skillId, paso: i + 1, totalPasos: pasos.length,
      objetivo: paso.objetivo, unidad: paso.unidad, completadas: actual.completadas, incompletas: actual.incompletas,
      fase: 'simulada', persona: !enPausa, orientacionGrados: paso.orientacion === 'perfil' ? 88 : 4,
      aviso, avisoTipo, ultimoMensaje, mensajesEmitidos, feedback, pausada: enPausa,
      motivoPausa: enPausa ? 'sin_persona' : null,
      puntos: enPausa ? null : esqueleto(paso.skillId, (activo / SEG_POR_REP) % 1),
      terminada: false, correctas: actual.correctas, conError: actual.conError, nivel: null, guia: null,
      colocacion: null,
      evaluacion: enPausa ? { evaluando: false, motivo: 'En pausa' }
        : anuncio ? { evaluando: false, motivo: 'Escuchando una indicación' } : { evaluando: true, motivo: null },
      depuracion: { fps: 30, latenciaMs: { pose: 18.4, geometria: 0.21, segmentacion: 0.05, motor: 0.12, total: 19.3 },
                    motivoSilencio: enPausa ? null : anuncio ? 'anuncio' : 'sin_error' },
    }
    if (actual.completadas >= paso.objetivo) avanzar()
  }

  const estadoColocando = (paso: PasoRutina): EstadoSesion => {
    const persona = reloj >= COLOCACION.persona
    const orientacion = reloj >= COLOCACION.orientacion
    const cuerpoEntero = reloj >= COLOCACION.cuerpoEntero
    const vista = paso.orientacion === 'perfil' ? 'de perfil' : 'de frente'
    return {
      ejercicio: paso.nombre, ejercicioId: paso.skillId, paso: i + 1, totalPasos: pasos.length,
      objetivo: paso.objetivo, unidad: paso.unidad, completadas: 0, incompletas: 0,
      fase: 'colocacion', persona, orientacionGrados: paso.orientacion === 'perfil' ? 88 : 4,
      aviso: null, avisoTipo: null, ultimoMensaje, mensajesEmitidos, feedback, pausada: false, motivoPausa: null,
      puntos: persona ? esqueleto(paso.skillId, 0) : null,
      terminada: false, correctas: 0, conError: 0, nivel: null, guia: null,
      colocacion: { instruccion: `Colócate ${vista} a la cámara. Aléjate hasta que se te vea de la cabeza a los pies.`,
                    persona, orientacion, cuerpoEntero },
      evaluacion: { evaluando: false, motivo: 'Colocándote' },
      depuracion: { fps: 30, latenciaMs: { pose: 18.4, geometria: 0.21, total: 18.8 }, motivoSilencio: null },
    }
  }

  const iniciar = async (opciones?: OpcionesInicio) => {
    if (fase === 'sesion' || fase === 'preparando') return false
    if (opciones?.pasos?.length) {
      const elegidos = opciones.pasos.map((e) => {
        const ej = CATALOGO.find((c) => c.skillId === e.skillId)
        return ej && e.objetivo >= ej.minimo && e.objetivo <= ej.maximo ? { ...ej, objetivo: e.objetivo } : null
      })
      if (elegidos.some((e) => e === null)) return false
      pasos = elegidos as PasoRutina[]
      nombreRutina = opciones.nombre ?? 'Rutina de entrenamiento'
    }
    fase = 'preparando'; error = null; resumen = null; sesion = null; publicar()
    await new Promise((r) => setTimeout(r, 700))
    i = 0; hechos = []; mensajesEmitidos = 0; ultimoMensaje = null; feedback = null
    empezarPaso()
    fase = 'sesion'
    let t = performance.now()
    temporizador = window.setInterval(() => {
      const ahora = performance.now()
      tic(Math.min(0.1, (ahora - t) / 1000) * velocidad)   // sin saltos si el navegador frena los timers
      t = ahora
      publicar()
    }, 33)
    return true
  }

  let perfiles: Perfil[] = escena === 'sin-perfiles' ? [] : [
    { id: 'pana', nombre: 'Ana', color: 'rosa', metaSemanal: 4, creado: '2026-09-19T07:15:00',
      rutina: [{ skillId: 'plancha', objetivo: 30 }, { skillId: 'marcha_rodillas', objetivo: 20 }] },
    { id: 'pluis', nombre: 'Luis', color: 'azul', metaSemanal: null, creado: '2026-10-02T18:00:00', rutina: null },
  ]
  let activo: string | null = null
  let elegido = false
  // historial de cada perfil: Ana trae semanas de ejemplo, el resto empieza vacío
  const historiales = new Map<string, Progreso>([['pana', escena === 'progreso-vacio' ? VACIO : progresoSimulado()]])
  const cambiarPerfil = (id: string | null, d: DatosPerfil): ResultadoPerfil => {
    const base = perfiles.find((p) => p.id === id)
    if (id && !base) return { ok: false, error: 'Ese perfil ya no existe.' }
    if (!id && perfiles.length >= MAX_PERFILES) return { ok: false, error: `Ya hay ${MAX_PERFILES} perfiles; borra uno para crear otro.` }
    const limpio = limpiarPerfil(d, perfiles.filter((p) => p.id !== id), base)
    if (typeof limpio === 'string') return { ok: false, error: limpio }
    const perfil: Perfil = base ? { ...base, ...limpio } : { id: `p${Date.now().toString(36)}`, creado: iso(new Date()), rutina: null, ...limpio }
    perfiles = base ? perfiles.map((p) => (p.id === id ? perfil : p)) : [...perfiles, perfil]
    if (!base) { activo = perfil.id; elegido = true }
    return { ok: true, perfil }
  }

  if (escena === 'error') {
    fase = 'error'
    error = { tipo: 'fuente', mensaje: 'no se pudo abrir la cámara 0' }
  } else if (escena === 'resumen') {
    const enResumen = () => fase === 'resumen'
    i = 0; empezarPaso()
    for (let k = 0; k < 4000 && !enResumen(); k++) tic(0.1)
    if (!enResumen()) cerrar(true)
  }

  const info: Info = {
    version: 1,
    capacidades: { nivel: false, correctasConError: true, guia: true, resumenTexto: false, motivoSilencio: true, pausaManual: true, colocacion: true, avisoLuz: false, rutinaPersonalizada: true, silenciarVoz: true, elegirCamara: true, reconocerEjercicio: true, pasoAnterior: true, gestoPausa: true, historial: true, perfiles: true },
    rutina: { nombre: 'Rutina de entrenamiento', pasos: CATALOGO },
    catalogo: CATALOGO,
    conexiones: CONEXIONES,
    espejo: true,
    fuente: 'camara',
  }

  return {
    info: async () => info,
    estado: (desde) => new Promise((resolve) => {
      const responder = () => resolve({ version, fase, error, sesion, resumen, frame: null })
      if (version > desde) return responder()
      esperando.push(responder)
      setTimeout(() => {
        const k = esperando.indexOf(responder)
        if (k >= 0) { esperando.splice(k, 1); resolve(null) }
      }, 500)
    }),
    iniciar,
    siguiente: async () => { if (fase === 'sesion' && i < pasos.length - 1) avanzar() },
    anterior: async () => { if (fase === 'sesion' && i > 0) { i--; empezarPaso() } },
    reiniciar: async () => { if (actual) { actual.completadas = 0; actual.incompletas = 0; actual.correctas = 0; actual.conError = 0; reloj = 0; colocadoEn = null } },
    listo: async () => { if (fase === 'sesion' && colocadoEn === null) colocadoEn = reloj },
    terminar: async () => { if (fase === 'sesion') cerrar(false) },
    volverAlInicio: async () => { if (fase === 'resumen' || fase === 'error') { fase = 'inicio'; resumen = null; error = null; publicar() } },
    salir: async () => { window.close() },
    configurar: async (ajustes) => { if (ajustes.camara !== undefined) camara = ajustes.camara },
    camaras: async () => {
      if (fase === 'sesion' || fase === 'preparando') return null
      await new Promise((r) => setTimeout(r, 600))       // abrir cada cámara tarda
      return { lista: [{ indice: 0, nombre: 'FaceTime HD Camera' }, { indice: 1, nombre: 'Cámara de iPhone' }], elegida: camara }
    },
    historial: async () => {
      await new Promise((r) => setTimeout(r, 250))
      const perfil = perfiles.find((p) => p.id === activo)
      if (!perfil) return null
      return { ...(historiales.get(perfil.id) ?? VACIO), metaSemanal: perfil.metaSemanal }
    },
    borrarHistorial: async () => { if (!activo) return false; historiales.delete(activo); return true },
    perfiles: async () => ({ perfiles, activo, elegido, colores: COLORES, maxPerfiles: MAX_PERFILES, maxNombre: MAX_NOMBRE, meta: [1, 7] }),
    elegirPerfil: async (id) => {
      if (id !== null && !perfiles.some((p) => p.id === id)) return false
      activo = id; elegido = true
      return true
    },
    crearPerfil: async (d) => cambiarPerfil(null, d),
    editarPerfil: async (id, d) => cambiarPerfil(id, d),
    guardarRutina: async (id, pasos) => {
      const base = perfiles.find((p) => p.id === id)
      if (!base) return { ok: false, error: 'Ese perfil ya no existe.' }
      for (const paso of pasos) {
        const ej = CATALOGO.find((c) => c.skillId === paso.skillId)
        if (!ej) return { ok: false, error: `ejercicio desconocido en la rutina: ${paso.skillId}` }
        if (!(paso.objetivo >= ej.minimo && paso.objetivo <= ej.maximo)) {
          return { ok: false, error: `el objetivo de '${paso.skillId}' debe estar entre ${ej.minimo} y ${ej.maximo} ${ej.unidad}` }
        }
      }
      const perfil: Perfil = { ...base, rutina: pasos.map((x) => ({ skillId: x.skillId, objetivo: x.objetivo })) }
      perfiles = perfiles.map((p) => (p.id === id ? perfil : p))
      return { ok: true, perfil }
    },
    borrarPerfil: async (id) => {
      if (!perfiles.some((p) => p.id === id)) return false
      perfiles = perfiles.filter((p) => p.id !== id)
      historiales.delete(id)
      if (activo === id) { activo = null; elegido = false }
      return true
    },
    pausar: async () => { if (fase === 'sesion' && actual && !pausaUsuaria) { pausaUsuaria = true; actual.pausas++ } },
    reanudar: async () => { pausaUsuaria = false },
  }
}
