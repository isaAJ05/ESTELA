import { Ban, Check, Loader2, Undo2 } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import type { DatosPerfil, EstadoPerfiles, Perfil, ResultadoPerfil } from '../bridge/tipos'
import { iniciales, problemaNombre } from '../estado/perfiles'
import { Boton } from './basicos'
import { ICONOS_UNIVERSO, IconoUniverso } from './IconoUniverso'

/** Avatar ilustrado (con el color del perfil como aro) o, sin él, las iniciales
 *  sobre un círculo de ese color. Decorativo: el nombre va siempre al lado. */
export function Avatar({ nombre, color, icono, tam = 'md' }: {
  nombre: string; color: string; icono?: string | null; tam?: 'sm' | 'md' | 'lg' | 'xl'
}) {
  const conIcono = icono != null && icono in ICONOS_UNIVERSO
  return (
    <span className={`avatar avatar-${tam}${conIcono ? ' avatar-imagen' : ''}`} data-color={color} aria-hidden="true">
      {conIcono ? <IconoUniverso icono={icono} /> : iniciales(nombre)}
    </span>
  )
}

/** Botón de la cabecera con quién entrena; abre «Mi perfil». */
export function ChipPerfil({ perfil, onClick, activa }: { perfil: Perfil | null; onClick: () => void; activa: boolean }) {
  return (
    <button className={`chip-perfil ${activa ? 'activa' : ''}`} onClick={onClick}
            aria-current={activa ? 'page' : undefined}
            title={perfil ? `Mi perfil: ${perfil.nombre}` : 'Entrenando sin perfil'}>
      {perfil ? <Avatar nombre={perfil.nombre} color={perfil.color} icono={perfil.icono} tam="sm" /> : <span className="avatar avatar-sm avatar-vacio" aria-hidden="true">?</span>}
      <span className="chip-perfil-nombre">{perfil ? perfil.nombre : 'Sin perfil'}</span>
    </button>
  )
}

/** Lo que se está editando en el formulario y aún no se guardó. */
export interface BorradorPerfil { nombre: string; color: string; icono: string | null; metaSemanal: number | null }

const NOMBRE_COLOR: Record<string, string> = {
  violeta: 'Violeta', naranja: 'Naranja', turquesa: 'Turquesa', rosa: 'Rosa', azul: 'Azul', mostaza: 'Mostaza',
}

/**
 * Nombre, color, icono y meta semanal. Sirve para crear (sin `inicial`) y editar.
 * El aviso del nombre es inmediato, pero el que vale es el de Python.
 */
export function FormularioPerfil({ estado, inicial, textoGuardar, alGuardar, alCancelar, alPrevisualizar }: {
  estado: EstadoPerfiles
  inicial?: Perfil
  textoGuardar: string
  alGuardar: (datos: DatosPerfil) => Promise<ResultadoPerfil>
  alCancelar?: () => void
  /** al editar: lo escrito mientras difiera de lo guardado (null si no hay cambios) */
  alPrevisualizar?: (borrador: BorradorPerfil | null) => void
}) {
  const id = useId()
  const [nombre, setNombre] = useState(inicial?.nombre ?? '')
  const [color, setColor] = useState(inicial?.color ?? estado.colores[estado.perfiles.length % estado.colores.length])
  const [icono, setIcono] = useState<string | null>(inicial?.icono ?? null)
  const [meta, setMeta] = useState<number | null>(inicial ? inicial.metaSemanal : 3)
  // solo los que Python ofrece y la interfaz sabe dibujar
  const iconos = (estado.iconos ?? []).filter((i) => i in ICONOS_UNIVERSO)
  // «sin color» solo tiene sentido con un avatar ilustrado: las iniciales necesitan un fondo
  const sinColor = estado.sinColor ?? null
  const puedeSinColor = sinColor !== null && icono !== null
  /** Elegir avatar; al volver a las iniciales sin color, se les da el primero. */
  const elegirIcono = (i: string | null) => {
    setIcono(i)
    if (i === null && color === sinColor) setColor(estado.colores[0])
    setGuardado(false)
  }
  const [tocado, setTocado] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [errorPython, setErrorPython] = useState<string | null>(null)
  const [guardado, setGuardado] = useState(false)

  const otros = estado.perfiles.filter((p) => p.id !== inicial?.id)
  const problema = problemaNombre(nombre, otros, estado.maxNombre)
  const [minMeta, maxMeta] = estado.meta
  const sinCambios = inicial != null && nombre.trim() === inicial.nombre && color === inicial.color
    && icono === (inicial.icono ?? null) && meta === inicial.metaSemanal

  useEffect(() => {
    alPrevisualizar?.(sinCambios || !inicial ? null : { nombre, color, icono, metaSemanal: meta })
  }, [alPrevisualizar, sinCambios, inicial, nombre, color, icono, meta])
  // al salir de «Mi perfil» no queda una vista previa colgada
  useEffect(() => () => alPrevisualizar?.(null), [alPrevisualizar])

  /** Vuelve a lo guardado. */
  const descartar = () => {
    if (!inicial) return
    setNombre(inicial.nombre); setColor(inicial.color); setIcono(inicial.icono ?? null); setMeta(inicial.metaSemanal)
    setTocado(false); setErrorPython(null); setGuardado(false)
  }

  const enviar = async () => {
    setTocado(true)
    if (problema || guardando) return
    setGuardando(true)
    setErrorPython(null)
    // sin iconos disponibles no se manda el campo: Python conserva lo que hubiera
    const r = await alGuardar(iconos.length > 0 ? { nombre, color, icono, metaSemanal: meta } : { nombre, color, metaSemanal: meta })
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
          <Avatar nombre={nombre} color={color} icono={icono} tam="lg" />
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
          {/* al final: aparecer o no, no mueve los colores */}
          {puedeSinColor && (
            <button type="button" role="radio" aria-checked={color === sinColor} aria-label="Sin color"
                    title="Sin color: solo el dibujo" className="muestra muestra-sin-color"
                    onClick={() => { setColor(sinColor); setGuardado(false) }}>
              {color === sinColor ? <Check aria-hidden="true" /> : <Ban aria-hidden="true" />}
            </button>
          )}
        </div>
      </fieldset>

      {iconos.length > 0 && (
        <fieldset className="campo">
          <legend>Avatar</legend>
          <div className="iconos-avatar" role="radiogroup" aria-label="Avatar">
            <button type="button" role="radio" aria-checked={icono === null} title="Tus iniciales"
                    className="icono-opcion" data-color={color} onClick={() => elegirIcono(null)}>
              <span className="icono-opcion-iniciales">{iniciales(nombre) || 'Aa'}</span>
            </button>
            {iconos.map((i) => (
              <button key={i} type="button" role="radio" aria-checked={icono === i} title={ICONOS_UNIVERSO[i].nombre}
                      aria-label={ICONOS_UNIVERSO[i].nombre} className="icono-opcion" data-color={color}
                      onClick={() => elegirIcono(i)}>
                <IconoUniverso icono={i} />
              </button>
            ))}
          </div>
        </fieldset>
      )}

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
        {inicial && (
          <Boton variante="suave" onClick={descartar} disabled={guardando || sinCambios}
                 title="Volver a lo que estaba guardado"><Undo2 />Descartar</Boton>
        )}
        {alCancelar && <Boton variante="suave" onClick={alCancelar}>Cancelar</Boton>}
      </div>
      <p className="formulario-perfil-nota">No pedimos edad, peso ni datos de salud: ESTELA no los usa.</p>
    </form>
  )
}
