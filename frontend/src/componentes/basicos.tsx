import type { ReactNode } from 'react'

/**
 * Logo de la cabecera. Con `alInicio` es un botón que lleva al inicio; qué
 * significa «ir al inicio» lo decide cada pantalla (en la sesión, pedir
 * confirmación para terminar; en el resumen, volver a configurar la rutina).
 */
export function Marca({ alInicio, titulo = 'Ir al inicio' }: { alInicio?: () => void; titulo?: string }) {
  const contenido = <>
    <img className="marca-logo" src={`${import.meta.env.BASE_URL}logo.png`} alt="" />
    <span>estela</span>
  </>
  if (!alInicio) return <div className="marca">{contenido}</div>
  return (
    <button type="button" className="marca marca-boton" onClick={alInicio} title={titulo} aria-label={titulo}>
      {contenido}
    </button>
  )
}

export function Boton({ children, variante = 'primario', onClick, disabled, atajo, type = 'button', ...resto }: {
  children: ReactNode
  variante?: 'primario' | 'secundario' | 'suave' | 'peligro'
  onClick?: () => void
  disabled?: boolean
  atajo?: string
  /** «submit» solo para el botón principal de un formulario */
  type?: 'button' | 'submit'
  'aria-label'?: string
  title?: string
  'aria-pressed'?: boolean
}) {
  return (
    <button type={type} className={`boton boton-${variante}`} onClick={onClick} disabled={disabled}
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
