// Textos y escalas del panel «Mi progreso» (ADR-008). Sin React, para probarlos
// con `npm test`. Las cifras las calcula Python; aquí solo se presentan.

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
const DIAS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb']

/** «AAAA-MM-DD» o «AAAA-MM-DDTHH:MM:SS» (hora local) → Date local. */
export function leerFecha(iso: string): Date {
  const [d, t = '00:00:00'] = iso.split('T')
  const [a, m, dia] = d.split('-').map(Number)
  const [h, min, s] = t.split(':').map(Number)
  return new Date(a, m - 1, dia, h || 0, min || 0, s || 0)
}

/** «6 nov» */
export function fechaCorta(iso: string): string {
  const f = leerFecha(iso)
  return `${f.getDate()} ${MESES[f.getMonth()]}`
}

/** «vie 6 nov · 9:30» */
export function fechaHora(iso: string): string {
  const f = leerFecha(iso)
  return `${DIAS[f.getDay()]} ${fechaCorta(iso)} · ${f.getHours()}:${String(f.getMinutes()).padStart(2, '0')}`
}

function soloDia(f: Date): number {
  return new Date(f.getFullYear(), f.getMonth(), f.getDate()).getTime()
}

/** «hoy», «ayer», «hace 3 días» o la fecha corta si pasó más de una semana. */
export function fechaRelativa(iso: string, hoy: Date = new Date()): string {
  const dias = Math.round((soloDia(hoy) - soloDia(leerFecha(iso))) / 86_400_000)
  if (dias <= 0) return 'hoy'
  if (dias === 1) return 'ayer'
  if (dias < 7) return `hace ${dias} días`
  return fechaCorta(iso)
}

export function minutos(segundos: number): number {
  return Math.round(segundos / 60)
}

/**
 * Marcas del eje en números redondos: de 0 hasta cubrir `maximo`, con 2 a 4
 * divisiones. Con todo en cero, un eje de 0 a 4.
 */
export function marcasEje(maximo: number): number[] {
  const pasos = [1, 2, 5, 10, 15, 20, 30, 60, 120, 300]
  const tope = Math.max(maximo, 4)
  const paso = pasos.find((p) => tope / p <= 4) ?? Math.ceil(tope / 4)
  const n = Math.ceil(tope / paso)
  return Array.from({ length: n + 1 }, (_, i) => i * paso)
}

/** Racha en dos partes, para que la cifra quepa en una línea: «3 días» + «seguidos». */
export function textoRacha(dias: number): { valor: string; extra: string } {
  if (dias === 0) return { valor: '0 días', extra: 'Muévete hoy para empezar una' }
  return dias === 1 ? { valor: '1 día', extra: 'Vuelve mañana para seguirla' } : { valor: `${dias} días`, extra: 'seguidos' }
}

/** Tiempo acumulado: «45 s», «12 min», «1 h 38 min». (`duracion` da «1:05», que
 *  con totales largos se confunde con una hora del día.) */
export function duracionLarga(segundos: number): string {
  const s = Math.round(segundos)
  if (s < 60) return `${s} s`
  const min = Math.round(s / 60)
  if (min < 60) return `${min} min`
  return min % 60 === 0 ? `${min / 60} h` : `${Math.floor(min / 60)} h ${min % 60} min`
}

/** «En 3 de tus últimas 5 sesiones» · «En tu única sesión» */
export function textoFrecuencia(veces: number, de: number): string {
  if (de === 1) return 'En tu única sesión'
  if (veces === de) return `En tus últimas ${de} sesiones`
  return `En ${veces} de tus últimas ${de} sesiones`
}

/** «12 / 10» o «25 / 20 s» */
export function textoMarca(completadas: number, objetivo: number, unidad: 'repeticiones' | 'segundos'): string {
  return `${completadas} / ${objetivo}${unidad === 'segundos' ? ' s' : ''}`
}

// -- presentación de las cifras nuevas (las calcula Python; aquí solo el texto) --

const MESES_LARGOS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
  'octubre', 'noviembre', 'diciembre']
const DIAS_LARGOS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado']

/** Date local → «AAAA-MM-DD». */
export function isoDia(f: Date): string {
  return `${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, '0')}-${String(f.getDate()).padStart(2, '0')}`
}

/** Semana que empieza el lunes `inicio`: «3 – 9 nov» o «27 oct – 2 nov». */
export function periodoSemana(inicio: string): string {
  const a = leerFecha(inicio)
  const b = new Date(a.getFullYear(), a.getMonth(), a.getDate() + 6)
  return a.getMonth() === b.getMonth()
    ? `${a.getDate()} – ${b.getDate()} ${MESES[b.getMonth()]}`
    : `${a.getDate()} ${MESES[a.getMonth()]} – ${b.getDate()} ${MESES[b.getMonth()]}`
}

/** Tramo comparado de la semana: «el lunes», «de lunes a jueves», «la semana entera». */
export function textoTramo(dias: number): string {
  if (dias <= 1) return 'el lunes'
  if (dias >= 7) return 'la semana entera'
  return `de lunes a ${DIAS_LARGOS[dias % 7]}`
}

/** Diferencia de tiempo redondeada a minutos: «+7 min», «−3 min», «lo mismo». */
export function textoDiferencia(segundos: number): string {
  const m = minutos(segundos)
  if (m === 0) return 'lo mismo'
  return `${m > 0 ? '+' : '−'}${Math.abs(m)} min`
}

/** «jueves 12 de noviembre» */
export function fechaLarga(iso: string): string {
  const f = leerFecha(iso)
  return `${DIAS_LARGOS[f.getDay()]} ${f.getDate()} de ${MESES_LARGOS[f.getMonth()]}`
}

/** «noviembre de 2026» */
export function textoMes(anio: number, mes: number): string {
  return `${MESES_LARGOS[mes]} de ${anio}`
}

/** «9:30» */
export function hora(iso: string): string {
  const f = leerFecha(iso)
  return `${f.getHours()}:${String(f.getMinutes()).padStart(2, '0')}`
}

/**
 * Intensidad del día en el calendario, de 0 (sin actividad) a 3, según su
 * tiempo frente al día más activo del historial. Es solo la escala de color.
 */
export function nivelActividad(duracionS: number, maximoS: number): 0 | 1 | 2 | 3 {
  if (duracionS <= 0 || maximoS <= 0) return 0
  const r = duracionS / maximoS
  return r > 2 / 3 ? 3 : r > 1 / 3 ? 2 : 1
}

/** Semanas (lunes a domingo) del mes: cada celda es el día o null fuera del mes. */
export function semanasDelMes(anio: number, mes: number): (Date | null)[][] {
  const primero = new Date(anio, mes, 1)
  const huecos = (primero.getDay() + 6) % 7
  const total = new Date(anio, mes + 1, 0).getDate()
  const celdas: (Date | null)[] = [
    ...Array.from({ length: huecos }, () => null),
    ...Array.from({ length: total }, (_, i) => new Date(anio, mes, i + 1)),
  ]
  while (celdas.length % 7) celdas.push(null)
  return Array.from({ length: celdas.length / 7 }, (_, k) => celdas.slice(k * 7, k * 7 + 7))
}

export type EstadoSesion = 'completa' | 'antes' | 'interrumpida'

/**
 * Cómo terminó la sesión, con los motivos que guarda el historial:
 * completada → «Rutina terminada» (llegó al final; los objetivos se cuentan aparte); usuaria → «Terminada antes»;
 * cámara perdida, cierre o error → «Interrumpida». Sin motivo (registros
 * antiguos) se usa `terminada`.
 */
export function estadoSesion(terminada: boolean, motivo: string | null): { clave: EstadoSesion; texto: string } {
  if (motivo === 'fuente' || motivo === 'cierre' || motivo === 'error') return { clave: 'interrumpida', texto: 'Interrumpida' }
  if (motivo === 'usuaria' || (motivo == null && !terminada)) return { clave: 'antes', texto: 'Terminada antes' }
  return { clave: 'completa', texto: 'Rutina terminada' }
}
