import { useEffect, useRef, useState } from 'react'
import type { Unidad } from '../bridge/tipos'

/** Contador grande, legible a 3 m. Destella al sumar (sin decir si fue correcta). */
export function Contador({ completadas, objetivo }: { completadas: number; objetivo: number }) {
  const [destello, setDestello] = useState(false)
  const previo = useRef(completadas)
  useEffect(() => {
    if (completadas > previo.current) {
      setDestello(true)
      const t = setTimeout(() => setDestello(false), 800)
      previo.current = completadas
      return () => clearTimeout(t)
    }
    previo.current = completadas
  }, [completadas])
  const avance = objetivo > 0 ? Math.min(1, completadas / objetivo) : 0
  return (
    <div className="contador" aria-live="polite" aria-label={`${completadas} de ${objetivo} repeticiones`}>
      <div className="contador-cifras">
        <strong className={destello ? 'destello' : undefined}>{completadas}</strong>
        <span>/ {objetivo}</span>
      </div>
      <span className="contador-unidad">repeticiones</span>
      <div className="barra"><i style={{ width: `${avance * 100}%` }} /></div>
    </div>
  )
}

/** Temporizador circular para los isométricos (segundos en posición). */
export function Temporizador({ segundos, objetivo }: { segundos: number; objetivo: number }) {
  const r = 54
  const circ = 2 * Math.PI * r
  const avance = objetivo > 0 ? Math.min(1, segundos / objetivo) : 0
  return (
    <div className="temporizador" aria-live="polite" aria-label={`${segundos} de ${objetivo} segundos en posición`}>
      <svg viewBox="0 0 128 128" aria-hidden="true">
        <circle className="temporizador-fondo" cx="64" cy="64" r={r} />
        <circle className="temporizador-avance" cx="64" cy="64" r={r}
                strokeDasharray={circ} strokeDashoffset={circ * (1 - avance)} />
      </svg>
      <div className="temporizador-cifras">
        <strong>{segundos}</strong>
        <span>/ {objetivo} s</span>
      </div>
    </div>
  )
}

export function Progreso({ completadas, objetivo, unidad }: { completadas: number; objetivo: number; unidad: Unidad }) {
  return unidad === 'segundos'
    ? <Temporizador segundos={completadas} objetivo={objetivo} />
    : <Contador completadas={completadas} objetivo={objetivo} />
}

/** Los pasos de la rutina como puntos unidos: hechos, actual y por hacer. */
export function Constelacion({ paso, total }: { paso: number; total: number }) {
  return (
    <ol className="constelacion" aria-label={`Ejercicio ${paso} de ${total}`}>
      {Array.from({ length: total }, (_, i) => (
        <li key={i} className={i + 1 < paso ? 'hecho' : i + 1 === paso ? 'actual' : undefined} />
      ))}
    </ol>
  )
}
