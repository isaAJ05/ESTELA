import { Check, Loader2 } from 'lucide-react'
import { useId, useState } from 'react'
import type { DatosPerfil, EstadoPerfiles, Perfil, ResultadoPerfil } from '../bridge/tipos'
import { iniciales, problemaNombre } from '../estado/perfiles'
import { Boton } from './basicos'

/** Iniciales sobre un círculo del color del perfil. Decorativo: el nombre va siempre al lado. */
export function Avatar({ nombre, color, tam = 'md' }: { nombre: string; color: string; tam?: 'sm' | 'md' | 'lg' | 'xl' }) {
  return <span className={`avatar avatar-${tam}`} data-color={color} aria-hidden="true">{iniciales(nombre)}</span>
}

/** Botón de la cabecera con quién entrena; abre «Mi perfil». */
export function ChipPerfil({ perfil, onClick, activa }: { perfil: Perfil | null; onClick: () => void; activa: boolean }) {
  return (
    <button className={`chip-perfil ${activa ? 'activa' : ''}`} onClick={onClick}
            aria-current={activa ? 'page' : undefined}
            title={perfil ? `Mi perfil: ${perfil.nombre}` : 'Entrenando sin perfil'}>
      {perfil ? <Avatar nombre={perfil.nombre} color={perfil.color} tam="sm" /> : <span className="avatar avatar-sm avatar-vacio" aria-hidden="true">?</span>}
      <span className="chip-perfil-nombre">{perfil ? perfil.nombre : 'Sin perfil'}</span>
    </button>
  )
}

const NOMBRE_COLOR: Record<string, string> = {
  violeta: 'Violeta', naranja: 'Naranja', turquesa: 'Turquesa', rosa: 'Rosa', azul: 'Azul', mostaza: 'Mostaza',
}

/**
 * Nombre, color y meta semanal. Sirve para crear (sin `inicial`) y editar.
 * El aviso del nombre es inmediato, pero el que vale es el de Python.
 */
export function FormularioPerfil({ estado, inicial, textoGuardar, alGuardar, alCancelar }: {
  estado: EstadoPerfiles
  inicial?: Perfil
  textoGuardar: string
  alGuardar: (datos: DatosPerfil) => Promise<ResultadoPerfil>
  alCancelar?: () => void
}) {
  const id = useId()
  const [nombre, setNombre] = useState(inicial?.nombre ?? '')
  const [color, setColor] = useState(inicial?.color ?? estado.colores[estado.perfiles.length % estado.colores.length])
  const [meta, setMeta] = useState<number | null>(inicial ? inicial.metaSemanal : 3)
  const [tocado, setTocado] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [errorPython, setErrorPython] = useState<string | null>(null)
  const [guardado, setGuardado] = useState(false)

  const otros = estado.perfiles.filter((p) => p.id !== inicial?.id)
  const problema = problemaNombre(nombre, otros, estado.maxNombre)
  const [minMeta, maxMeta] = estado.meta
  const sinCambios = inicial != null && nombre.trim() === inicial.nombre && color === inicial.color && meta === inicial.metaSemanal

  const enviar = async () => {
    setTocado(true)
    if (problema || guardando) return
    setGuardando(true)
    setErrorPython(null)
    const r = await alGuardar({ nombre, color, metaSemanal: meta })
    setGuardando(false)
    if (!r.ok) setErrorPython(r.error)
    else if (inicial) { setGuardado(true); setTimeout(() => setGuardado(false), 2500) }
  }

  const aviso = errorPython ?? (tocado ? problema : null)
  return (
    <form className="formulario-perfil" onSubmit={(e) => { e.preventDefault(); void enviar() }} noValidate>
      {/* al crear se ve cómo queda; al editar ya está arriba, en «Mi perfil» */}
      {!inicial && (
        <div className="formulario-perfil-vista">
          <Avatar nombre={nombre} color={color} tam="lg" />
        </div>
      )}

      <label className="campo">
        <span>Nombre o apodo</span>
        <input id={`${id}-nombre`} value={nombre} maxLength={estado.maxNombre} autoFocus={!inicial}
               autoComplete="off" spellCheck={false} aria-invalid={aviso ? true : undefined}
               aria-describedby={aviso ? `${id}-aviso` : undefined}
               onChange={(e) => { setNombre(e.target.value); setErrorPython(null); setGuardado(false) }}
               onBlur={() => setTocado(true)} />
      </label>

      <fieldset className="campo">
        <legend>Color del avatar</legend>
        <div className="muestras" role="radiogroup" aria-label="Color del avatar">
          {estado.colores.map((c) => (
            <button key={c} type="button" role="radio" aria-checked={color === c} aria-label={NOMBRE_COLOR[c] ?? c}
                    title={NOMBRE_COLOR[c] ?? c} className="muestra" data-color={c}
                    onClick={() => { setColor(c); setGuardado(false) }}>
              {color === c && <Check aria-hidden="true" />}
            </button>
          ))}
        </div>
      </fieldset>

      <fieldset className="campo">
        <legend>Meta semanal</legend>
        <span className="campo-ayuda">¿Cuántos días por semana quieres moverte?</span>
        <div className="opciones-meta" role="radiogroup" aria-label="Meta semanal">
          <button type="button" role="radio" aria-checked={meta === null} className={meta === null ? 'activo' : undefined}
                  onClick={() => { setMeta(null); setGuardado(false) }}>Sin meta</button>
          {Array.from({ length: maxMeta - minMeta + 1 }, (_, k) => minMeta + k).map((n) => (
            <button key={n} type="button" role="radio" aria-checked={meta === n} aria-label={`${n} ${n === 1 ? 'día' : 'días'}`}
                    className={meta === n ? 'activo' : undefined} onClick={() => { setMeta(n); setGuardado(false) }}>{n}</button>
          ))}
        </div>
      </fieldset>

      {aviso && <p id={`${id}-aviso`} className="texto-peligro" role="alert">{aviso}</p>}

      <div className="acciones">
        <Boton type="submit" disabled={guardando || sinCambios}>
          {guardando ? <><Loader2 className="girando" />Guardando…</> : guardado ? <><Check />Guardado</> : textoGuardar}
        </Boton>
        {alCancelar && <Boton variante="suave" onClick={alCancelar}>Cancelar</Boton>}
      </div>
      <p className="formulario-perfil-nota">No pedimos edad, peso ni datos de salud: ESTELA no los usa.</p>
    </form>
  )
}
