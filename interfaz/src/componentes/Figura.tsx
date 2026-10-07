import type { Orientacion } from '../bridge/tipos'

// Postura clave de cada ejercicio, dibujada con la misma línea y proporciones.
// Es una ilustración fija de la interfaz; la guía animada a partir de la
// referencia grabada llega del backend (capacidad «guia»).

export type Postura = 'jack' | 'abduccion' | 'rodilla' | 'zancada' | 'plancha'

export function posturaDe(skillId: string): Postura {
  if (skillId.startsWith('jumping')) return 'jack'
  if (skillId.startsWith('abduccion')) return 'abduccion'
  if (skillId.startsWith('marcha')) return 'rodilla'
  if (skillId.startsWith('plancha')) return 'plancha'
  return 'zancada'
}

const PIERNAS: Record<Postura, string> = {
  plancha: 'M60 78L24 105L9 105 M24 105L78 105',
  jack: 'M60 78L25 140 M60 78L95 140',
  abduccion: 'M60 78L26 140 M60 78L96 104L112 78',
  rodilla: 'M60 78L37 140 M60 78L88 103L106 78',
  zancada: 'M60 78L40 112L24 142 M60 78L87 99L105 99',
}

const BRAZOS: Record<Postura, string> = {
  plancha: 'M60 43L38 65 M60 43L82 65',
  jack: 'M60 43L18 13 M60 43L102 13',
  abduccion: 'M60 43L38 65 M60 43L82 65',
  rodilla: 'M60 43L38 65 M60 43L82 65',
  zancada: 'M60 43L38 65 M60 43L82 65',
}

export function Figura({ skillId, tam = 160, resaltar = true }: {
  skillId: string
  tam?: number
  resaltar?: boolean
}) {
  const postura = posturaDe(skillId)
  return (
    <svg className={`figura figura-${postura}`} viewBox="0 0 120 160" width={tam * 0.75} height={tam}
         role="img" aria-label="Postura clave del ejercicio">
      <circle className="figura-cabeza" cx="60" cy="20" r="9" />
      <path className="figura-linea" d={`M60 30V78 ${BRAZOS[postura]}`} />
      <path className={`figura-linea ${resaltar ? 'figura-resalte' : ''}`} d={PIERNAS[postura]} />
    </svg>
  )
}

export function IconoVista({ vista }: { vista: Orientacion | null }) {
  return (
    <span className={`icono-vista ${vista === 'perfil' ? 'perfil' : 'frente'}`} aria-hidden="true">
      <i /><i />
    </span>
  )
}

export function textoVista(vista: Orientacion | null): string {
  return vista === 'perfil' ? 'De perfil' : vista === 'frente' ? 'De frente' : 'Libre'
}
