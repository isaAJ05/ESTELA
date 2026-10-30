// Ajustes de la usuaria: tema, voz, tamaño del texto y reconocimiento.
//
// El tema y el texto son solo de la interfaz (atributo `data-tema` y variable
// `--escala` en <html>). La voz la aplica Python con `configurar` (capacidad
// «silenciarVoz»). Se guardan en localStorage; si no hay, valen los de defecto.
// El reconocimiento del ejercicio (EXP-010, capacidad «reconocerEjercicio»)
// no se recupera: cada vez que se abre la aplicación empieza desactivado,
// igual que en Python.

import { useSyncExternalStore } from 'react'
import type { Bridge } from '../bridge/tipos'

export type Tema = 'oscuro' | 'claro' | 'sistema'
export type TamanoTexto = 'normal' | 'grande' | 'muy-grande'

export interface Ajustes {
  tema: Tema
  voz: boolean
  texto: TamanoTexto
  reconocer: boolean
}

export const AJUSTES_POR_DEFECTO: Ajustes = { tema: 'oscuro', voz: true, texto: 'normal', reconocer: false }

export const ESCALA_TEXTO: Record<TamanoTexto, number> = { normal: 1, grande: 1.12, 'muy-grande': 1.25 }

const CLAVE = 'estela.ajustes'
const TEMAS: Tema[] = ['oscuro', 'claro', 'sistema']
const TAMANOS: TamanoTexto[] = ['normal', 'grande', 'muy-grande']

/** Lee lo guardado y descarta lo que no sea un valor conocido. */
export function leerAjustes(texto: string | null): Ajustes {
  let d: Partial<Record<keyof Ajustes, unknown>> = {}
  try { d = JSON.parse(texto ?? '{}') ?? {} } catch { /* corrupto: valores por defecto */ }
  return {
    tema: TEMAS.includes(d.tema as Tema) ? d.tema as Tema : AJUSTES_POR_DEFECTO.tema,
    voz: typeof d.voz === 'boolean' ? d.voz : AJUSTES_POR_DEFECTO.voz,
    texto: TAMANOS.includes(d.texto as TamanoTexto) ? d.texto as TamanoTexto : AJUSTES_POR_DEFECTO.texto,
    reconocer: AJUSTES_POR_DEFECTO.reconocer,
  }
}

/** El tema que se ve: «sistema» sigue al sistema operativo. */
export function temaVisible(tema: Tema, sistemaOscuro: boolean): 'oscuro' | 'claro' {
  return tema === 'sistema' ? (sistemaOscuro ? 'oscuro' : 'claro') : tema
}

function cargar(): Ajustes {
  try { return leerAjustes(localStorage.getItem(CLAVE)) } catch { return AJUSTES_POR_DEFECTO }
}

let actual: Ajustes = cargar()
const oyentes = new Set<() => void>()
const consultaOscuro = typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: dark)') : null

/** Pone el tema y el tamaño del texto en <html>. */
export function aplicarAjustes(a: Ajustes = actual): void {
  const raiz = document.documentElement
  raiz.dataset.tema = temaVisible(a.tema, consultaOscuro?.matches ?? true)
  raiz.style.setProperty('--escala', String(ESCALA_TEXTO[a.texto]))
}

consultaOscuro?.addEventListener('change', () => { if (actual.tema === 'sistema') aplicarAjustes() })

/** Cambia ajustes, los aplica y los guarda. Con `bridge`, le pasa la voz y el reconocimiento a Python. */
export function cambiarAjustes(cambios: Partial<Ajustes>, bridge?: Bridge): void {
  actual = { ...actual, ...cambios }
  aplicarAjustes()
  try { localStorage.setItem(CLAVE, JSON.stringify(actual)) } catch { /* sin almacenamiento */ }
  if (bridge && cambios.voz !== undefined) void bridge.configurar({ voz: cambios.voz })
  if (bridge && cambios.reconocer !== undefined) void bridge.configurar({ reconocer: cambios.reconocer })
  oyentes.forEach((f) => f())
}

/** Al abrir la interfaz: si quedó la voz silenciada, que Python lo sepa. */
export function sincronizarVoz(bridge: Bridge): void {
  if (!actual.voz) void bridge.configurar({ voz: false })
}

/** La voz ahora mismo (para atajos de teclado, fuera de React). */
export const leerVoz = (): boolean => actual.voz

export function useAjustes(): Ajustes {
  return useSyncExternalStore(
    (f) => { oyentes.add(f); return () => { oyentes.delete(f) } },
    () => actual,
  )
}
