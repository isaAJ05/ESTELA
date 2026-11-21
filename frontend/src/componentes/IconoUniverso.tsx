import { useId, type ReactNode } from 'react'

/**
 * Avatares ilustrados con el estilo de la mascota (hoja de marca de ESTELA):
 * caritas kawaii, degradado amarillo cálido → lila, destellos dorados y cielo
 * morado. «Estrella» es la propia mascota (public/estela/feliz.png); el resto
 * está dibujado aquí en SVG. Llenan el círculo del avatar; el color del perfil
 * queda como aro alrededor. Los nombres son los que guarda Python
 * (`perfiles.ICONOS`); uno desconocido no dibuja nada y se ven las iniciales.
 *
 * Los degradados llevan un prefijo único por instancia (`useId`): con el mismo
 * id repetido, un avatar oculto podía dejar a los demás sin color.
 */
type Dibujo = (p: string) => ReactNode

const TINTA = '#2b1656'
const ORO = '#ffd66b'

/** Ojos brillantes, mejillas y sonrisa abierta, como la mascota. `feliz`: ojos ^ ^. */
function cara(x: number, y: number, s = 1, feliz = false): ReactNode {
  const ojo = (ex: number) => feliz
    ? <path d={`M${ex - 1.7 * s} ${y + 0.6 * s}Q${ex} ${y - 1.8 * s} ${ex + 1.7 * s} ${y + 0.6 * s}`}
            stroke={TINTA} strokeWidth={1.1 * s} strokeLinecap="round" fill="none" />
    : <g>
        <ellipse cx={ex} cy={y} rx={1.9 * s} ry={2.3 * s} fill={TINTA} />
        <circle cx={ex - 0.6 * s} cy={y - 0.9 * s} r={0.75 * s} fill="#fff" />
        <circle cx={ex + 0.65 * s} cy={y + 0.75 * s} r={0.35 * s} fill="#fff" />
      </g>
  return (
    <g>
      {ojo(x - 4.2 * s)}{ojo(x + 4.2 * s)}
      <ellipse cx={x - 7 * s} cy={y + 2.6 * s} rx={1.7 * s} ry={0.95 * s} fill="#ff8fc0" opacity=".6" />
      <ellipse cx={x + 7 * s} cy={y + 2.6 * s} rx={1.7 * s} ry={0.95 * s} fill="#ff8fc0" opacity=".6" />
      <path d={`M${x - 1.9 * s} ${y + 1.7 * s}Q${x} ${y + 5 * s} ${x + 1.9 * s} ${y + 1.7 * s}Z`} fill={TINTA} />
      <ellipse cx={x} cy={y + 3.4 * s} rx={0.95 * s} ry={0.55 * s} fill="#ff7aa8" />
    </g>
  )
}

/** Destello dorado de cuatro puntas, el de la hoja de marca. */
const destello = (x: number, y: number, r: number, color = ORO, opacidad = 1) => (
  <path d={`M${x} ${y - r}Q${x + r * 0.18} ${y - r * 0.18} ${x + r} ${y}Q${x + r * 0.18} ${y + r * 0.18} ${x} ${y + r}`
         + `Q${x - r * 0.18} ${y + r * 0.18} ${x - r} ${y}Q${x - r * 0.18} ${y - r * 0.18} ${x} ${y - r}Z`}
        fill={color} opacity={opacidad} />
)

const puntos = (lista: [number, number, number][]) =>
  lista.map(([x, y, r], k) => <circle key={k} cx={x} cy={y} r={r} fill="#e9dcff" opacity={0.7} />)

/** Degradados comunes: cielo, cuerpo (amarillo → lila), oro y halo. */
function comunes(p: string): ReactNode {
  return (
    <defs>
      <radialGradient id={`${p}cielo`} cx="32%" cy="25%" r="90%">
        <stop offset="0" stopColor="#5a33b5" /><stop offset=".6" stopColor="#2c1870" /><stop offset="1" stopColor="#150c38" />
      </radialGradient>
      <linearGradient id={`${p}cuerpo`} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#fff3bf" /><stop offset=".5" stopColor="#f6d8b8" /><stop offset="1" stopColor="#c4a0ff" />
      </linearGradient>
      <linearGradient id={`${p}oro`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#fff0a6" /><stop offset="1" stopColor="#ffb347" />
      </linearGradient>
      <linearGradient id={`${p}lila`} x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stopColor="#b48cff" /><stop offset="1" stopColor="#7a4ff0" />
      </linearGradient>
      <radialGradient id={`${p}halo`}>
        <stop offset="0" stopColor="#ffe9a8" stopOpacity=".45" /><stop offset="1" stopColor="#ffe9a8" stopOpacity="0" />
      </radialGradient>
    </defs>
  )
}

const BASE = import.meta.env.BASE_URL

const DIBUJOS: Record<string, { nombre: string; dibujo: Dibujo }> = {
  estrella: {
    nombre: 'Estrella',
    dibujo: () => <>
      {puntos([[10, 14, 0.8], [54, 52, 0.8], [12, 50, 0.6]])}
      <image href={`${BASE}estela/feliz.png`} x="6" y="6" width="53" height="53" />
    </>,
  },
  planeta: {
    nombre: 'Planeta',
    dibujo: (p) => <>
      {puntos([[10, 12, 0.8], [54, 50, 0.8], [8, 46, 0.6]])}
      {destello(50, 13, 3.4)}{destello(12, 24, 2)}
      <circle cx="32" cy="35" r="19" fill={`url(#${p}halo)`} />
      <g transform="rotate(-16 32 35)">
        <ellipse cx="32" cy="35" rx="25" ry="6.8" fill="none" stroke={`url(#${p}oro)`} strokeWidth="3" opacity=".9" />
      </g>
      <circle cx="32" cy="35" r="14" fill={`url(#${p}cuerpo)`} />
      <ellipse cx="26" cy="27.5" rx="4" ry="2.2" fill="#fff" opacity=".55" transform="rotate(-30 26 27.5)" />
      {cara(32, 35.5, 1.05)}
      <g transform="rotate(-16 32 35)">
        <path d="M7 35A25 6.8 0 0 0 57 35" fill="none" stroke={`url(#${p}oro)`} strokeWidth="3" strokeLinecap="round" />
      </g>
      <circle cx="54" cy="29" r="2.4" fill={`url(#${p}oro)`} />
    </>,
  },
  luna: {
    nombre: 'Luna',
    dibujo: (p) => <>
      <defs>
        <mask id={`${p}cuarto`}>
          <rect width="64" height="64" fill="#fff" /><circle cx="41" cy="25" r="14.5" fill="#000" />
        </mask>
      </defs>
      {puntos([[12, 12, 0.7], [52, 54, 0.8], [56, 40, 0.6]])}
      {destello(50, 12, 3.6)}{destello(46, 46, 2.2)}
      <circle cx="30" cy="34" r="22" fill={`url(#${p}halo)`} />
      <circle cx="30" cy="34" r="18" fill={`url(#${p}cuerpo)`} mask={`url(#${p}cuarto)`} />
      <ellipse cx="21" cy="26" rx="3" ry="1.8" fill="#fff" opacity=".5" transform="rotate(-40 21 26)" />
      {cara(24.5, 39, 0.9, true)}
    </>,
  },
  sol: {
    nombre: 'Sol',
    dibujo: (p) => <>
      <defs>
        <radialGradient id={`${p}sol`} cx="40%" cy="35%" r="75%">
          <stop offset="0" stopColor="#fff6c2" /><stop offset=".6" stopColor="#ffd56b" /><stop offset="1" stopColor="#ffa75e" />
        </radialGradient>
      </defs>
      {puntos([[10, 54, 0.7], [56, 10, 0.7]])}
      <circle cx="32" cy="33" r="24" fill={`url(#${p}halo)`} />
      <g fill={`url(#${p}oro)`}>
        {Array.from({ length: 8 }, (_, k) => (
          <path key={k} d="M32 6.5q3 5.5 0 10q-3-4.5 0-10z" transform={`rotate(${k * 45} 32 33)`} />
        ))}
      </g>
      <circle cx="32" cy="33" r="14.5" fill={`url(#${p}sol)`} />
      <ellipse cx="26.5" cy="26" rx="3.6" ry="2" fill="#fff" opacity=".6" transform="rotate(-30 26.5 26)" />
      {cara(32, 33.5, 1.1, true)}
    </>,
  },
  cohete: {
    nombre: 'Cohete',
    dibujo: (p) => <>
      <defs>
        <linearGradient id={`${p}fuego`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff3a8" /><stop offset=".55" stopColor="#ffb347" /><stop offset="1" stopColor="#ff7aa8" stopOpacity="0" />
        </linearGradient>
      </defs>
      {puntos([[12, 12, 0.8], [50, 54, 0.7], [8, 38, 0.6]])}
      {destello(52, 12, 3.4)}{destello(14, 50, 2.2)}
      <g transform="rotate(32 32 32)">
        <path d="M26.5 45Q32 63 37.5 45Z" fill={`url(#${p}fuego)`} />
        <path d="M24.5 33l-7 9.5v4.5l7-3.5zM39.5 33l7 9.5v4.5l-7-3.5z" fill={`url(#${p}lila)`} />
        <path d="M32 8c6.5 5.5 8.5 14 8.5 25v12h-17V33c0-11 2-19.5 8.5-25z" fill={`url(#${p}cuerpo)`} />
        <path d="M32 8c3.6 3 5.8 7.4 7 12H25c1.2-4.6 3.4-9 7-12z" fill={`url(#${p}oro)`} />
        <ellipse cx="28" cy="25" rx="1.6" ry="4" fill="#fff" opacity=".5" />
        {cara(32, 32, 0.72)}
        <rect x="27.5" y="43" width="9" height="3" rx="1.2" fill="#9b7bea" />
      </g>
    </>,
  },
  astronauta: {
    nombre: 'Astronauta',
    dibujo: (p) => <>
      <defs>
        <radialGradient id={`${p}casco`} cx="35%" cy="30%" r="80%">
          <stop offset="0" stopColor="#ffffff" /><stop offset="1" stopColor="#d9c8ff" />
        </radialGradient>
        <linearGradient id={`${p}visor`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#5b3fc4" /><stop offset="1" stopColor="#1d1150" />
        </linearGradient>
      </defs>
      {puntos([[10, 14, 0.8], [56, 22, 0.7], [8, 40, 0.6]])}
      {destello(50, 10, 3)}{destello(12, 30, 2)}
      <path d="M13 64c0-11 8.5-17 19-17s19 6 19 17z" fill={`url(#${p}cuerpo)`} />
      <rect x="27" y="53" width="10" height="6" rx="2" fill={`url(#${p}lila)`} />
      {destello(32, 56, 2.2)}
      <path d="M32 6.5v4" stroke="#d9c8ff" strokeWidth="1.6" strokeLinecap="round" />
      {destello(32, 5.5, 2.6)}
      <rect x="14.5" y="24" width="5" height="11" rx="2.5" fill={`url(#${p}lila)`} />
      <rect x="44.5" y="24" width="5" height="11" rx="2.5" fill={`url(#${p}lila)`} />
      <circle cx="32" cy="29" r="15" fill={`url(#${p}casco)`} />
      <rect x="20.5" y="21.5" width="23" height="17" rx="8.5" fill={`url(#${p}visor)`} />
      <path d="M24 25.5q2.6-2.4 6.2-2.4" stroke="#fff" strokeOpacity=".7" strokeWidth="1.5" strokeLinecap="round" fill="none" />
      {/* la cara brilla dentro del visor */}
      <g>
        <ellipse cx="27.6" cy="30.5" rx="1.9" ry="2.3" fill="#fff3bf" />
        <ellipse cx="36.4" cy="30.5" rx="1.9" ry="2.3" fill="#fff3bf" />
        <ellipse cx="24.5" cy="33.6" rx="1.5" ry=".8" fill="#ff8fc0" opacity=".7" />
        <ellipse cx="39.5" cy="33.6" rx="1.5" ry=".8" fill="#ff8fc0" opacity=".7" />
        <path d="M30.2 33q1.8 2.6 3.6 0" stroke="#fff3bf" strokeWidth="1.2" strokeLinecap="round" fill="none" />
      </g>
    </>,
  },
  cometa: {
    nombre: 'Cometa',
    dibujo: (p) => <>
      <defs>
        <linearGradient id={`${p}estela`} x1="1" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffd66b" /><stop offset=".45" stopColor="#a77bff" /><stop offset="1" stopColor="#7a4ff0" stopOpacity="0" />
        </linearGradient>
      </defs>
      {puntos([[14, 12, 0.8], [54, 50, 0.8], [26, 56, 0.6]])}
      {destello(52, 10, 3)}{destello(16, 30, 2.2)}
      <path d="M34 24Q20 32 8 50" stroke={`url(#${p}estela)`} strokeWidth="5.5" strokeLinecap="round" fill="none" />
      <path d="M38 30Q27 39 18 56" stroke={`url(#${p}estela)`} strokeWidth="4" strokeLinecap="round" fill="none" />
      <path d="M31 19Q19 23 9 33" stroke={`url(#${p}estela)`} strokeWidth="3" strokeLinecap="round" fill="none" />
      <circle cx="41" cy="23" r="15" fill={`url(#${p}halo)`} />
      <circle cx="41" cy="23" r="11" fill={`url(#${p}cuerpo)`} />
      <ellipse cx="36.5" cy="17" rx="3" ry="1.8" fill="#fff" opacity=".55" transform="rotate(-30 36.5 17)" />
      {cara(41, 23.5, 0.85)}
    </>,
  },
  galaxia: {
    nombre: 'Galaxia',
    dibujo: (p) => <>
      {puntos([[10, 12, 0.8], [54, 54, 0.8], [56, 14, 0.6], [8, 50, 0.6]])}
      {destello(50, 50, 2.6)}{destello(13, 16, 2.4)}
      <circle cx="32" cy="32" r="24" fill={`url(#${p}halo)`} />
      <g fill="none" strokeLinecap="round">
        <path d="M32 21C19 21 11 31 15 42" stroke={`url(#${p}lila)`} strokeWidth="5" />
        <path d="M32 43C45 43 53 33 49 22" stroke={`url(#${p}lila)`} strokeWidth="5" />
        <path d="M24 16C12 20 8 34 14 46" stroke={`url(#${p}oro)`} strokeWidth="2.4" opacity=".85" />
        <path d="M40 48C52 44 56 30 50 18" stroke={`url(#${p}oro)`} strokeWidth="2.4" opacity=".85" />
      </g>
      {destello(12, 42, 1.8)}{destello(52, 22, 1.8)}
      <circle cx="32" cy="32" r="10.5" fill={`url(#${p}cuerpo)`} />
      <ellipse cx="28" cy="26.8" rx="2.8" ry="1.6" fill="#fff" opacity=".55" transform="rotate(-30 28 26.8)" />
      {cara(32, 32.5, 0.82)}
    </>,
  },
  constelacion: {
    nombre: 'Constelación',
    dibujo: (p) => <>
      {puntos([[30, 8, 0.6], [58, 34, 0.6], [6, 30, 0.6]])}
      <path d="M11 47L20 30L26.5 28M48.4 28L53 14M43.6 42.5L50 50" stroke={ORO} strokeOpacity=".7" strokeWidth="1.2"
            strokeLinecap="round" fill="none" strokeDasharray="0.5 2.4" />
      {destello(11, 47, 3)}{destello(20, 30, 2.6)}{destello(53, 14, 3.2)}{destello(50, 50, 2.6)}
      <circle cx="36" cy="32" r="16" fill={`url(#${p}halo)`} />
      <path d="M36 19L39.8 26.7L48.4 28L42.2 34L43.6 42.5L36 38.5L28.4 42.5L29.8 34L23.6 28L32.2 26.7Z"
            fill={`url(#${p}cuerpo)`} stroke={`url(#${p}cuerpo)`} strokeWidth="3.2" strokeLinejoin="round" />
      <ellipse cx="32.5" cy="26" rx="2.4" ry="1.3" fill="#fff" opacity=".6" transform="rotate(-30 32.5 26)" />
      {cara(36, 32, 0.68)}
    </>,
  },
  ovni: {
    nombre: 'Ovni',
    dibujo: (p) => <>
      <defs>
        <linearGradient id={`${p}rayo`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffe9a8" stopOpacity=".55" /><stop offset="1" stopColor="#ffe9a8" stopOpacity="0" />
        </linearGradient>
        <radialGradient id={`${p}cupula`} cx="40%" cy="30%" r="80%">
          <stop offset="0" stopColor="#ffffff" stopOpacity=".95" /><stop offset="1" stopColor="#bfe9ff" stopOpacity=".85" />
        </radialGradient>
      </defs>
      {puntos([[10, 12, 0.8], [54, 12, 0.7], [8, 36, 0.6]])}
      {destello(50, 16, 3.2)}{destello(14, 20, 2.2)}
      <path d="M24 44L15 64H49L40 44Z" fill={`url(#${p}rayo)`} />
      <ellipse cx="32" cy="41" rx="21" ry="6.5" fill={`url(#${p}lila)`} />
      <ellipse cx="32" cy="39.2" rx="21" ry="4.6" fill={`url(#${p}cuerpo)`} />
      <path d="M19 38.5a13 13 0 0 1 26 0z" fill={`url(#${p}cupula)`} />
      {cara(32, 31.5, 0.68)}
      <ellipse cx="25" cy="29.5" rx="2.4" ry="1.3" fill="#fff" opacity=".85" transform="rotate(-35 25 29.5)" />
      <circle cx="19" cy="42.6" r="1.5" fill={ORO} /><circle cx="32" cy="44.6" r="1.5" fill={ORO} /><circle cx="45" cy="42.6" r="1.5" fill={ORO} />
    </>,
  },
}

/** Nombre visible de cada avatar, para los botones de elegir. */
export const ICONOS_UNIVERSO: Record<string, { nombre: string }> =
  Object.fromEntries(Object.entries(DIBUJOS).map(([k, v]) => [k, { nombre: v.nombre }]))

/** La ilustración de un avatar, o null si el nombre no existe. */
export function IconoUniverso({ icono }: { icono: string | null | undefined }) {
  const p = useId().replace(/:/g, '')
  const d = icono ? DIBUJOS[icono] : undefined
  if (!d) return null
  return (
    <svg className="icono-universo" viewBox="0 0 64 64" aria-hidden="true">
      {comunes(p)}
      <defs><clipPath id={`${p}circulo`}><circle cx="32" cy="32" r="32" /></clipPath></defs>
      <g clipPath={`url(#${p}circulo)`}>
        <rect width="64" height="64" fill={`url(#${p}cielo)`} />
        {d.dibujo(p)}
      </g>
    </svg>
  )
}
