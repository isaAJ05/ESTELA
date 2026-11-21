import type { Orientacion } from '../bridge/tipos'

// Postura clave de cada ejercicio, dibujada con la misma línea y proporciones.
// Es una ilustración fija de la interfaz; la guía animada a partir de la
// referencia grabada llega del backend (capacidad «guia»).
// Un ejercicio nuevo sin figura propia se ve con la figura neutra «de pie»:
// para darle una, añadir su prefijo aquí y sus trazos en PIERNAS y BRAZOS.

export type Postura = 'jack' | 'abduccion-izq' | 'abduccion-der' | 'rodilla' | 'zancada' | 'plancha' | 'depie'

const PREFIJOS: [string, Postura][] = [
  ['jumping', 'jack'],
  ['abduccion_cadera_izq', 'abduccion-izq'],
  ['abduccion_cadera_der', 'abduccion-der'],
  ['marcha', 'rodilla'],
  ['zancada', 'zancada'],
  ['plancha', 'plancha'],
]

export function posturaDe(skillId: string): Postura {
  return PREFIJOS.find(([prefijo]) => skillId.startsWith(prefijo))?.[1] ?? 'depie'
}

const PIERNAS: Record<Postura, string> = {
  plancha: 'M78 78L94 98L111 98 M78 78L90 91L105 91',
  jack: 'M60 78L25 140 M60 78L95 140',
  'abduccion-izq': 'M60 78L42 140 M60 78L84 108L108 108',
  'abduccion-der': 'M60 78L36 108L12 108 M60 78L78 140',
  rodilla: 'M60 78L37 140 M60 78L88 103L106 78',
  zancada: 'M60 78L40 112L24 142 M60 78L87 99L105 99',
  depie: 'M60 78L47 140 M60 78L73 140',
}

const BRAZOS: Record<Postura, string> = {
  plancha: 'M38 73L40 96 M38 73L28 91',
  jack: 'M60 43L18 13 M60 43L102 13',
  'abduccion-izq': 'M60 43L40 68 M60 43L80 68',
  'abduccion-der': 'M60 43L40 68 M60 43L80 68',
  rodilla: 'M60 43L38 65 M60 43L82 65',
  zancada: 'M60 43L38 65 M60 43L82 65',
  depie: 'M60 43L44 72 M60 43L76 72',
}

const CUERPO: Record<Postura, string> = {
  plancha: 'M28 72L78 78',
  jack: 'M60 30V78',
  'abduccion-izq': 'M60 30V78',
  'abduccion-der': 'M60 30V78',
  rodilla: 'M60 30V78',
  zancada: 'M60 30V78',
  depie: 'M60 30V78',
}

const CABEZA: Record<Postura, { x: number; y: number; r: number }> = {
  plancha: { x: 20, y: 70, r: 10 },
  jack: { x: 60, y: 20, r: 9 },
  'abduccion-izq': { x: 60, y: 20, r: 9 },
  'abduccion-der': { x: 60, y: 20, r: 9 },
  rodilla: { x: 60, y: 20, r: 10 },
  zancada: { x: 60, y: 20, r: 9 },
  depie: { x: 60, y: 20, r: 9 },
}

export function Figura({ skillId, tam = 160, resaltar = true }: {
  skillId: string
  tam?: number
  resaltar?: boolean
}) {
  const postura = posturaDe(skillId)
  return (
    <svg className={`figura figura-${postura}`} viewBox="0 0 120 160" width={tam * 0.75} height={tam}
         preserveAspectRatio="xMidYMid meet"
         role="img" aria-label="Postura clave del ejercicio">
      <circle className="figura-cabeza" cx={CABEZA[postura].x} cy={CABEZA[postura].y} r={CABEZA[postura].r} />
      <path className="figura-linea" d={`${CUERPO[postura]} ${BRAZOS[postura]}`} />
      <path className={`figura-linea ${resaltar && postura !== 'depie' ? 'figura-resalte' : ''}`} d={PIERNAS[postura]} />
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
