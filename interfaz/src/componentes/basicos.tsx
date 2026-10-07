import type { ReactNode } from 'react'

export function Marca() {
  return (
    <div className="marca">
      <span className="marca-signo"><span /></span>
      <span>estela</span>
    </div>
  )
}

export function Boton({ children, variante = 'primario', onClick, disabled, atajo, ...resto }: {
  children: ReactNode
  variante?: 'primario' | 'secundario' | 'suave' | 'peligro'
  onClick?: () => void
  disabled?: boolean
  atajo?: string
  'aria-label'?: string
  title?: string
}) {
  return (
    <button className={`boton boton-${variante}`} onClick={onClick} disabled={disabled}
            aria-keyshortcuts={atajo} {...resto}>
      {children}
    </button>
  )
}

export function Aviso({ tipo, icono, titulo, children, accion }: {
  tipo: 'info' | 'cuidado' | 'bloqueo'
  icono: ReactNode
  titulo: string
  children?: ReactNode
  accion?: ReactNode
}) {
  return (
    <div className={`aviso aviso-${tipo}`} role={tipo === 'bloqueo' ? 'alert' : 'status'}>
      {icono}
      <div>
        <strong>{titulo}</strong>
        {children && <span>{children}</span>}
      </div>
      {accion}
    </div>
  )
}

/** «1:05», «45 s». */
export function duracion(segundos: number): string {
  const s = Math.round(segundos)
  if (s < 60) return `${s} s`
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export function plural(n: number, uno: string, varios: string): string {
  return `${n} ${n === 1 ? uno : varios}`
}
