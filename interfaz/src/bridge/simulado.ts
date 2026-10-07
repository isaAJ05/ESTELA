// Backend simulado para trabajar la interfaz sin cámara ni Python (`npm run dev`).
// Imita al orquestador: fases, conteo, mensajes, avisos y una pausa. No tiene
// ninguna lógica de detección real.
//
// Parámetros de la URL: ?simulado            fuerza el simulador en el build
//                       ?velocidad=4         acelera el tiempo
//                       ?escena=resumen|error empieza en esa fase

import type {
  Bridge, Estado, EstadoSesion, Info, MensajeResumen, PasoRutina, Punto, Resumen,
} from './tipos'

const PASOS: PasoRutina[] = [
  { skillId: 'jumping_jacks', nombre: 'Jumping jacks', orientacion: 'frente', unidad: 'repeticiones', objetivo: 10 },
  { skillId: 'abduccion_cadera_izq', nombre: 'Abducción de cadera de pie, pierna izquierda', orientacion: 'frente', unidad: 'repeticiones', objetivo: 8 },
  { skillId: 'abduccion_cadera_der', nombre: 'Abducción de cadera de pie, pierna derecha', orientacion: 'frente', unidad: 'repeticiones', objetivo: 8 },
  { skillId: 'marcha_rodillas', nombre: 'Marcha con elevación de rodillas', orientacion: 'perfil', unidad: 'repeticiones', objetivo: 16 },
  { skillId: 'zancada_atras_izq', nombre: 'Zancada atrás estática, pierna izquierda atrás', orientacion: 'perfil', unidad: 'repeticiones', objetivo: 6 },
  { skillId: 'zancada_atras_der', nombre: 'Zancada atrás estática, pierna derecha atrás', orientacion: 'perfil', unidad: 'repeticiones', objetivo: 6 },
  { skillId: 'plancha', nombre: 'Plancha', orientacion: 'perfil', unidad: 'segundos', objetivo: 20 },
]

const CONEXIONES: [number, number][] = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [11, 23], [12, 24], [23, 24],
  [23, 25], [25, 27], [27, 29], [29, 31], [27, 31], [24, 26], [26, 28], [28, 30], [30, 32], [28, 32],
]

const MENSAJES: Record<string, string[]> = {
  jumping_jacks: ['Sube un poco más los brazos.', '¡Vas muy bien!'],
  abduccion_cadera_izq: ['Mantén el tronco recto, sin inclinarte.'],
  abduccion_cadera_der: ['Mantén el tronco recto, sin inclinarte.'],
  marcha_rodillas: ['Sube un poco más las rodillas.', 'Endereza un poco el tronco.'],
  zancada_atras_izq: ['Endereza un poco el tronco.', 'Baja un poco más la rodilla.'],
  zancada_atras_der: ['Endereza un poco el tronco.'],
  plancha: ['Sube un poco la cadera.'],
}

const SEG_POR_REP = 2.4
const PASO_CON_PAUSA = 1         // índice del paso donde se simula una pausa
const PAUSA = { desdeRep: 3, duracionS: 4 }

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
  let fase: Estado['fase'] = 'inicio'
  let error: Estado['error'] = null
  let resumen: Resumen | null = null
  let sesion: EstadoSesion | null = null
  let reloj = 0                // segundos simulados dentro del paso
  let i = 0                    // paso actual
  let mensajesEmitidos = 0
  let ultimoMensaje: string | null = null
  let hechos: PasoHecho[] = []
  let actual: PasoHecho | null = null
  let temporizador: number | undefined
  const esperando: Array<() => void> = []

  const publicar = () => { version++; esperando.splice(0).forEach((f) => f()) }

  const empezarPaso = () => {
    reloj = 0
    actual = { paso: PASOS[i], completadas: 0, incompletas: 0, duracionS: 0, pausaS: 0, pausas: 0, mensajes: [] }
    hechos.push(actual)
  }

  const cerrar = (terminada: boolean) => {
    clearInterval(temporizador)
    resumen = {
      rutina: 'Calentamiento básico',
      terminada,
      duracionTotalS: Math.round(hechos.reduce((a, h) => a + h.duracionS, 0) * 10) / 10,
      pasos: hechos.map((h) => ({
        skillId: h.paso.skillId, nombre: h.paso.nombre, unidad: h.paso.unidad, objetivo: h.paso.objetivo,
        completadas: h.completadas, incompletas: h.incompletas, correctas: null, conError: null,
        duracionS: Math.round(h.duracionS * 10) / 10, pausas: h.pausas, pausaS: h.pausaS, mensajes: h.mensajes,
      })),
      resumenTexto: null,
    }
    fase = 'resumen'
    sesion = null
    publicar()
  }

  const avanzar = () => {
    i++
    if (i >= PASOS.length) return cerrar(true)
    empezarPaso()
  }

  const tic = (dt: number) => {
    if (!actual) return
    const paso = actual.paso
    reloj += dt
    const enPausa = i === PASO_CON_PAUSA
      && reloj >= PAUSA.desdeRep * SEG_POR_REP && reloj < PAUSA.desdeRep * SEG_POR_REP + PAUSA.duracionS
    if (enPausa) {
      if (actual.pausas === 0) actual.pausas = 1
      actual.pausaS = Math.round((actual.pausaS + dt) * 10) / 10
    } else {
      actual.duracionS += dt
    }
    const activo = reloj - (i === PASO_CON_PAUSA && reloj > PAUSA.desdeRep * SEG_POR_REP
      ? Math.min(PAUSA.duracionS, reloj - PAUSA.desdeRep * SEG_POR_REP) : 0)
    const antes = actual.completadas
    actual.completadas = Math.min(paso.objetivo,
      paso.unidad === 'segundos' ? Math.floor(activo) : Math.floor(activo / SEG_POR_REP))
    if (paso.skillId === 'marcha_rodillas' && antes < 5 && actual.completadas >= 5) actual.incompletas = 1
    if (paso.unidad === 'repeticiones' && actual.completadas !== antes && [2, 4].includes(actual.completadas)) {
      const lista = MENSAJES[paso.skillId] ?? []
      const texto = lista[(actual.completadas / 2 - 1) % Math.max(lista.length, 1)]
      if (texto) {
        ultimoMensaje = texto
        mensajesEmitidos++
        actual.mensajes.push({ tMs: Math.round(reloj * 1000), texto, errorId: texto.startsWith('¡') ? null : 'simulado', repeticion: actual.completadas })
      }
    }
    const cambiaOrientacion = i === 0 || PASOS[i - 1].orientacion !== paso.orientacion
    let aviso: string | null = null
    let avisoTipo: EstadoSesion['avisoTipo'] = null
    if (enPausa) { aviso = 'Pausa. No te veo: vuelve al encuadre para seguir.'; avisoTipo = 'pausa' }
    else if (cambiaOrientacion && reloj < 2.5) {
      aviso = paso.orientacion === 'perfil' ? 'Colócate de perfil a la cámara.' : 'Colócate de frente a la cámara.'
      avisoTipo = 'orientacion'
    }
    sesion = {
      ejercicio: paso.nombre, ejercicioId: paso.skillId, paso: i + 1, totalPasos: PASOS.length,
      objetivo: paso.objetivo, unidad: paso.unidad, completadas: actual.completadas, incompletas: actual.incompletas,
      fase: 'simulada', persona: !enPausa, orientacionGrados: paso.orientacion === 'perfil' ? 88 : 4,
      aviso, avisoTipo, ultimoMensaje, mensajesEmitidos, pausada: enPausa,
      motivoPausa: enPausa ? 'sin_persona' : null,
      puntos: enPausa ? null : esqueleto(paso.skillId, (activo / SEG_POR_REP) % 1),
      terminada: false, correctas: null, conError: null, nivel: null, guia: null,
      depuracion: { fps: 30, latenciaMs: { pose: 18.4, geometria: 0.21, segmentacion: 0.05, motor: 0.12, total: 19.3 }, motivoSilencio: null },
    }
    if (actual.completadas >= paso.objetivo) avanzar()
  }

  const iniciar = async () => {
    if (fase === 'sesion' || fase === 'preparando') return false
    fase = 'preparando'; error = null; resumen = null; sesion = null; publicar()
    await new Promise((r) => setTimeout(r, 700))
    i = 0; hechos = []; mensajesEmitidos = 0; ultimoMensaje = null
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
    capacidades: { nivel: false, correctasConError: false, guia: false, resumenTexto: false, motivoSilencio: false, pausaManual: false, colocacion: false, avisoLuz: false },
    rutina: { nombre: 'Calentamiento básico', pasos: PASOS },
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
    siguiente: async () => { if (fase === 'sesion') avanzar() },
    reiniciar: async () => { if (actual) { actual.completadas = 0; actual.incompletas = 0; reloj = 0 } },
    terminar: async () => { if (fase === 'sesion') cerrar(false) },
    volverAlInicio: async () => { if (fase === 'resumen' || fase === 'error') { fase = 'inicio'; resumen = null; error = null; publicar() } },
    salir: async () => { window.close() },
    pausar: async () => {},
    reanudar: async () => {},
  }
}
