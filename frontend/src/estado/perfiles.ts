// Perfiles (ADR-009): quién entrena. Python guarda los perfiles y decide qué
// vale; aquí solo se guarda la última lista recibida para que la cabecera,
// el inicio y el resumen la lean sin volver a pedirla.

import { useSyncExternalStore } from 'react'
import type {
  Bridge, DatosPerfil, DatosRutina, EstadoPerfiles, PasoElegido, Perfil, ResultadoPerfil, RutinaGuardada,
} from '../bridge/tipos'

let actual: EstadoPerfiles | null = null
const oyentes = new Set<() => void>()

function fijar(e: EstadoPerfiles | null) {
  actual = e
  oyentes.forEach((f) => f())
}

export function usePerfiles(): EstadoPerfiles | null {
  return useSyncExternalStore((f) => { oyentes.add(f); return () => { oyentes.delete(f) } }, () => actual)
}

export function perfilActivo(e: EstadoPerfiles | null): Perfil | null {
  return e?.perfiles.find((p) => p.id === e.activo) ?? null
}

export function usePerfilActivo(): Perfil | null {
  return perfilActivo(usePerfiles())
}

export async function cargarPerfiles(bridge: Bridge): Promise<void> {
  try {
    fijar(await bridge.perfiles())
  } catch (err) {
    console.error('perfiles()', err)
  }
}

export async function elegirPerfil(bridge: Bridge, id: string | null): Promise<boolean> {
  const ok = await bridge.elegirPerfil(id).catch(() => false)
  await cargarPerfiles(bridge)
  return ok
}

export async function crearPerfil(bridge: Bridge, datos: DatosPerfil): Promise<ResultadoPerfil> {
  const r = await bridge.crearPerfil(datos).catch(() => FALLO)
  await cargarPerfiles(bridge)
  return r
}

export async function editarPerfil(bridge: Bridge, id: string, datos: DatosPerfil): Promise<ResultadoPerfil> {
  const r = await bridge.editarPerfil(id, datos).catch(() => FALLO)
  await cargarPerfiles(bridge)
  return r
}

export async function borrarPerfil(bridge: Bridge, id: string): Promise<boolean> {
  const ok = await bridge.borrarPerfil(id).catch(() => false)
  await cargarPerfiles(bridge)
  return ok
}

/** Espera tras el último cambio de «Mi rutina» antes de guardarla en el perfil. */
export const ESPERA_GUARDAR_RUTINA_MS = 500
let pendiente: { perfilId: string; temporizador: ReturnType<typeof setTimeout>; enviar: () => void } | null = null

/**
 * Guarda la rutina en el perfil cuando se deja de cambiar. Lleva el id del
 * perfil: si se cambia de perfil antes de que se envíe, se guarda igual en el
 * que la armó.
 */
export function guardarRutinaDiferido(bridge: Bridge, perfilId: string, pasos: PasoElegido[]): void {
  if (pendiente?.perfilId === perfilId) clearTimeout(pendiente.temporizador)   // la sustituye la nueva
  else guardarRutinaYa()                                                     // la de otro perfil se envía ya
  const enviar = () => {
    pendiente = null
    void bridge.guardarRutina(perfilId, pasos)
      .then((r) => { if (!r.ok) console.warn('guardarRutina()', r.error) })
      .catch((err) => console.error('guardarRutina()', err))
      .then(() => cargarPerfiles(bridge))
  }
  pendiente = { perfilId, temporizador: setTimeout(enviar, ESPERA_GUARDAR_RUTINA_MS), enviar }
}

/** Envía ya el guardado pendiente (p. ej. al empezar la sesión o cambiar de perfil). */
export function guardarRutinaYa(): void {
  if (!pendiente) return
  clearTimeout(pendiente.temporizador)
  pendiente.enviar()
}

/** Crea (sin `id`) o actualiza una rutina guardada con nombre. */
export async function guardarRutinaNombrada(bridge: Bridge, perfilId: string, datos: DatosRutina): Promise<ResultadoPerfil> {
  const r = await bridge.guardarRutinaNombrada(perfilId, datos).catch(() => FALLO)
  await cargarPerfiles(bridge)
  return r
}

export async function borrarRutinaNombrada(bridge: Bridge, perfilId: string, rutinaId: string): Promise<ResultadoPerfil> {
  const r = await bridge.borrarRutinaNombrada(perfilId, rutinaId).catch(() => FALLO)
  await cargarPerfiles(bridge)
  return r
}

const FALLO: ResultadoPerfil = { ok: false, error: 'No se pudo hablar con ESTELA. Inténtalo de nuevo.' }

// -- sin React (se prueban con `npm test`) --------------------------------------

/** «Ana María» → «AM», «luis» → «L», «  » → «?». */
export function iniciales(nombre: string): string {
  const partes = nombre.trim().split(/\s+/).filter(Boolean)
  if (partes.length === 0) return '?'
  const letras = partes.length === 1 ? [partes[0]] : [partes[0], partes[partes.length - 1]]
  return letras.map((p) => [...p][0].toLocaleUpperCase('es')).join('')
}

/**
 * Aviso inmediato mientras se escribe el nombre. Python vuelve a validarlo al
 * guardar y su mensaje es el que vale.
 */
export function problemaNombre(nombre: string, otros: readonly Perfil[], max: number): string | null {
  const limpio = nombre.trim().split(/\s+/).filter(Boolean).join(' ')
  if (!limpio) return 'Escribe un nombre o apodo.'
  if (limpio.length > max) return `El nombre puede tener hasta ${max} caracteres.`
  if (otros.some((p) => p.nombre.toLocaleLowerCase('es') === limpio.toLocaleLowerCase('es'))) {
    return 'Ya hay un perfil con ese nombre.'
  }
  return null
}

/**
 * Aviso inmediato para el nombre de una rutina guardada; `otras`: las demás
 * rutinas del perfil (sin la que se renombra). Python vuelve a validarlo.
 */
export function problemaNombreRutina(nombre: string, otras: readonly RutinaGuardada[], max: number): string | null {
  const limpio = nombre.trim().split(/\s+/).filter(Boolean).join(' ')
  if (!limpio) return 'Ponle un nombre a la rutina.'
  if (limpio.length > max) return `El nombre puede tener hasta ${max} caracteres.`
  if (otras.some((r) => r.nombre.toLocaleLowerCase('es') === limpio.toLocaleLowerCase('es'))) {
    return 'Ya tienes una rutina con ese nombre.'
  }
  return null
}

/** «3 días por semana» · «Sin meta» */
export function textoMeta(meta: number | null): string {
  if (meta == null) return 'Sin meta semanal'
  return meta === 1 ? '1 día por semana' : `${meta} días por semana`
}
