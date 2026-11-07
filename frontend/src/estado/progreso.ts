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
