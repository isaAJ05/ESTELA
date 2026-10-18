// Rutina que arma la usuaria en el inicio. Funciones puras: no saben nada de
// React ni del bridge. La validación final la repite Python
// (`contrato.rutina_desde_opciones`); aquí sirve para avisar antes de empezar.

import type { EjercicioCatalogo, PasoElegido, PasoRutina, Unidad } from '../bridge/tipos'

/** Ejercicios elegidos, en el orden en que se harán. */
export type Seleccion = PasoElegido[]

/** Sin dato medido de cuánto dura una repetición: es una estimación [I]. */
export const SEGUNDOS_POR_REPETICION = 3
/** Anuncio del ejercicio y colocación entre un paso y otro (estimación). */
export const SEGUNDOS_TRANSICION = 10

const CLAVE_GUARDADO = 'estela.rutina'

export function seleccionDe(pasos: readonly PasoRutina[], catalogo: readonly EjercicioCatalogo[]): Seleccion {
  const ids = new Set(catalogo.map((e) => e.skillId))
  return pasos.filter((p) => ids.has(p.skillId)).map((p) => ({ skillId: p.skillId, objetivo: p.objetivo }))
}

export function incluido(sel: Seleccion, skillId: string): boolean {
  return sel.some((p) => p.skillId === skillId)
}

/** Añade el ejercicio al final con su objetivo por defecto, o lo quita. */
export function alternar(sel: Seleccion, ej: EjercicioCatalogo): Seleccion {
  return incluido(sel, ej.skillId)
    ? sel.filter((p) => p.skillId !== ej.skillId)
    : [...sel, { skillId: ej.skillId, objetivo: ej.objetivo }]
}

export function fijarObjetivo(sel: Seleccion, skillId: string, objetivo: number): Seleccion {
  return sel.map((p) => (p.skillId === skillId ? { ...p, objetivo } : p))
}

/** Mueve el paso `i` una posición arriba (-1) o abajo (+1). */
export function mover(sel: Seleccion, i: number, delta: -1 | 1): Seleccion {
  const j = i + delta
  if (i < 0 || i >= sel.length || j < 0 || j >= sel.length) return sel
  const copia = [...sel]
  ;[copia[i], copia[j]] = [copia[j], copia[i]]
  return copia
}

/** Paso del stepper: los segundos van de 5 en 5. */
export function pasoDe(unidad: Unidad): number {
  return unidad === 'segundos' ? 5 : 1
}

export function limitar(valor: number, ej: EjercicioCatalogo): number {
  return Math.min(ej.maximo, Math.max(ej.minimo, Math.round(valor)))
}

/**
 * Texto escrito en el campo del objetivo → número válido, o el motivo por el
 * que no vale. Solo enteros: «8,5», «-3» o «abc» se rechazan, no se redondean.
 */
export function leerObjetivo(texto: string, ej: EjercicioCatalogo):
  { ok: true; valor: number } | { ok: false; error: string } {
  const t = texto.trim()
  const unidad = ej.unidad === 'segundos' ? 'segundos' : 'repeticiones'
  if (t === '') return { ok: false, error: 'Escribe un número.' }
  if (!/^\d+$/.test(t)) return { ok: false, error: 'Solo números enteros, sin signos ni decimales.' }
  const valor = Number(t)
  if (valor < ej.minimo || valor > ej.maximo) {
    return { ok: false, error: `Entre ${ej.minimo} y ${ej.maximo} ${unidad}.` }
  }
  return { ok: true, valor }
}

/** Problemas que impiden empezar (vacía, ejercicio desconocido u objetivo fuera de rango). */
export function problemas(sel: Seleccion, catalogo: readonly EjercicioCatalogo[]): string[] {
  if (sel.length === 0) return ['Elige al menos un ejercicio para empezar.']
  const lista: string[] = []
  for (const p of sel) {
    const ej = catalogo.find((e) => e.skillId === p.skillId)
    if (!ej) lista.push(`Ejercicio desconocido: ${p.skillId}.`)
    else if (!Number.isInteger(p.objetivo) || p.objetivo < ej.minimo || p.objetivo > ej.maximo) {
      lista.push(`Revisa el objetivo de «${ej.nombre}».`)
    }
  }
  return lista
}

/** Duración aproximada en segundos; las repeticiones usan una estimación. */
export function estimarSegundos(sel: Seleccion, catalogo: readonly EjercicioCatalogo[]): number {
  return sel.reduce((total, p) => {
    const ej = catalogo.find((e) => e.skillId === p.skillId)
    if (!ej) return total
    const trabajo = ej.unidad === 'segundos' ? p.objetivo : p.objetivo * SEGUNDOS_POR_REPETICION
    return total + trabajo + SEGUNDOS_TRANSICION
  }, 0)
}

/** El plan que verá la sesión: los datos del catálogo con el objetivo elegido. */
export function planDe(sel: Seleccion, catalogo: readonly EjercicioCatalogo[]): PasoRutina[] {
  return sel.flatMap((p) => {
    const ej = catalogo.find((e) => e.skillId === p.skillId)
    return ej ? [{ skillId: ej.skillId, nombre: ej.nombre, orientacion: ej.orientacion,
                   unidad: ej.unidad, objetivo: p.objetivo, guia: ej.guia }] : []
  })
}

export function iguales(a: Seleccion, b: Seleccion): boolean {
  return a.length === b.length && a.every((p, i) => p.skillId === b[i].skillId && p.objetivo === b[i].objetivo)
}

/** Última rutina armada (solo comodidad: si no hay almacenamiento, se usa la base). */
export function cargarGuardada(catalogo: readonly EjercicioCatalogo[]): Seleccion | null {
  try {
    const crudo = localStorage.getItem(CLAVE_GUARDADO)
    if (!crudo) return null
    const datos: unknown = JSON.parse(crudo)
    if (!Array.isArray(datos)) return null
    const sel: Seleccion = []
    for (const d of datos) {
      const ej = catalogo.find((e) => e.skillId === d?.skillId)
      if (ej && typeof d.objetivo === 'number' && !incluido(sel, ej.skillId)) {
        sel.push({ skillId: ej.skillId, objetivo: limitar(d.objetivo, ej) })
      }
    }
    return sel.length > 0 ? sel : null
  } catch {
    return null
  }
}

export function guardar(sel: Seleccion): void {
  try { localStorage.setItem(CLAVE_GUARDADO, JSON.stringify(sel)) } catch { /* sin almacenamiento */ }
}
