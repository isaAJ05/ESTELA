import { ArrowLeft, Check, Loader2, Pencil, Play, Plus, Save, Trash2 } from 'lucide-react'
import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import type { PasoRutina, RutinaGuardada } from '../bridge/tipos'
import { problemaNombreRutina } from '../estado/perfiles'
import { Boton, plural } from './basicos'
import { FiguraEjercicio, textoEstimado, textoObjetivo } from './rutina'

/** Una tarjeta de «Mis rutinas». */
export interface DatosTarjetaRutina {
  /** id de la rutina guardada, «recomendada» o «borrador» */
  clave: string
  tipo: 'recomendada' | 'borrador' | 'guardada'
  nombre: string
  plan: PasoRutina[]
  estimadoS: number
  /** es la que está elegida ahora */
  enUso: boolean
  /** en uso y con cambios sin guardar */
  conCambios: boolean
}

const ETIQUETA = { recomendada: 'Recomendada', borrador: 'Sin guardar', guardada: 'Guardada' } as const
/** figuras que caben en la zona de arriba; el resto se resume en «+n» */
const MAX_FIGURAS = 4

/**
 * «Mis rutinas»: una tarjeta por rutina para empezarla directamente o
 * editarla. Editar abre la vista de personalizar.
 */
export function VistaRutinas({ tarjetas, lleno, maxRutinas, preparando, alVolver, alComenzar, alEditar, alNueva, alBorrar }: {
  tarjetas: DatosTarjetaRutina[]
  lleno: boolean
  maxRutinas: number
  preparando: boolean
  alVolver: () => void
  alComenzar: (clave: string) => void
  alEditar: (clave: string) => void
  alNueva: () => void
  /** devuelve el error de Python o null si se borró */
  alBorrar: (clave: string) => Promise<string | null>
}) {
  // la confirmación de borrar va en un diálogo, fuera de la tarjeta
  const [aBorrar, setABorrar] = useState<DatosTarjetaRutina | null>(null)
  return (
    <section className="mis-rutinas">
      <div className="mis-rutinas-cabeza">
        <button className="enlace-volver" onClick={alVolver}><ArrowLeft />Volver al inicio</button>
        <span className="etiqueta etiqueta-marca">Mis rutinas</span>
        <h1>Elige tu rutina</h1>
        <p className="elegir-ayuda">Empieza una directamente o edítala para cambiar sus ejercicios y objetivos.</p>
      </div>
      <div className="rejilla-mis-rutinas">
        {tarjetas.map((t) => (
          <TarjetaRutina key={t.clave} datos={t} preparando={preparando}
                         alComenzar={() => alComenzar(t.clave)} alEditar={() => alEditar(t.clave)}
                         alBorrar={() => setABorrar(t)} />
        ))}
        <button type="button" className="tarjeta-nueva-rutina" onClick={alNueva} disabled={lleno || preparando}>
          <span className="tarjeta-nueva-rutina-icono" aria-hidden="true"><Plus /></span>
          <strong>Nueva rutina</strong>
          <span>{lleno ? `Ya tienes ${maxRutinas}; borra una para crear otra.` : 'Elige los ejercicios y ponle un nombre.'}</span>
        </button>
      </div>
      {aBorrar && (
        <DialogoBorrarRutina nombre={aBorrar.nombre} alCerrar={() => setABorrar(null)}
                             alBorrar={() => alBorrar(aBorrar.clave)} />
      )}
    </section>
  )
}

/** Confirmación modal, como la de borrar el historial: Esc, «Cancelar» o tocar fuera la cierran. */
function DialogoBorrarRutina({ nombre, alCerrar, alBorrar }: {
  nombre: string
  alCerrar: () => void
  /** devuelve el error de Python o null si se borró */
  alBorrar: () => Promise<string | null>
}) {
  const cancelar = useRef<HTMLButtonElement>(null)
  const [borrando, setBorrando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    cancelar.current?.focus()
    const tecla = (ev: KeyboardEvent) => { if (ev.key === 'Escape' && !borrando) alCerrar() }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [alCerrar, borrando])
  const borrar = async () => {
    setBorrando(true)
    const fallo = await alBorrar()
    setBorrando(false)
    if (fallo) setError(fallo)
    else alCerrar()
  }
  return (
    <div className="capa-dialogo" onClick={(ev) => { if (ev.target === ev.currentTarget && !borrando) alCerrar() }}>
      <div className="tarjeta tarjeta-confirmar dialogo-borrar" role="alertdialog" aria-modal="true"
           aria-labelledby="titulo-borrar-rutina" aria-describedby="texto-borrar-rutina">
        <span className="etiqueta etiqueta-cuidado">Borrar rutina</span>
        <h2 id="titulo-borrar-rutina">¿Borrar «{nombre}»?</h2>
        <p id="texto-borrar-rutina" className="dialogo-borrar-texto">
          Se quitará de tus rutinas guardadas. Tus sesiones anteriores no cambian. <strong>No se puede deshacer.</strong>
        </p>
        {error && <p className="texto-peligro" role="alert">{error}</p>}
        <div className="acciones">
          <button ref={cancelar} type="button" className="boton boton-secundario" onClick={alCerrar} disabled={borrando}>
            Cancelar
          </button>
          <Boton variante="peligro" onClick={() => void borrar()} disabled={borrando}>
            {borrando ? <><Loader2 className="girando" />Borrando…</> : <><Trash2 />Sí, borrar</>}
          </Boton>
        </div>
      </div>
    </div>
  )
}

function TarjetaRutina({ datos, preparando, alComenzar, alEditar, alBorrar }: {
  datos: DatosTarjetaRutina
  preparando: boolean
  alComenzar: () => void
  alEditar: () => void
  /** abre la confirmación (fuera de la tarjeta) */
  alBorrar: () => void
}) {
  const { nombre, plan, tipo } = datos
  const visibles = plan.slice(0, MAX_FIGURAS)

  return (
    <article className={`tarjeta-mi-rutina ${datos.enUso ? 'en-uso' : ''}`}>
      {/* zona grande con las figuras, como en «Personaliza tu rutina»: abre la rutina para editarla */}
      <button type="button" className="tarjeta-mi-rutina-figuras" onClick={alEditar} disabled={preparando}
              aria-label={`Editar ${nombre}`} title="Editar rutina">
        <span className="tarjeta-mi-rutina-tira" aria-hidden="true">
          {visibles.map((p, i) => (
            <span key={`${p.skillId}-${i}`} className="tarjeta-mi-rutina-mini"><FiguraEjercicio paso={p} tam={56} /></span>
          ))}
          {plan.length > MAX_FIGURAS && <span className="tarjeta-mi-rutina-mas">+{plan.length - MAX_FIGURAS}</span>}
        </span>
        <span className="tarjeta-mi-rutina-cifras">
          {plural(plan.length, 'ejercicio', 'ejercicios')}{plan.length > 0 && ` · ${textoEstimado(datos.estimadoS)}`}
        </span>
      </button>

      <div className="tarjeta-mi-rutina-info">
        <div className="tarjeta-mi-rutina-cabeza">
          <span className="etiqueta">{ETIQUETA[tipo]}</span>
          <span className="tarjeta-mi-rutina-esquina">
            {datos.enUso && <span className="tarjeta-mi-rutina-marca"><Check aria-hidden="true" />En uso</span>}
            {tipo === 'guardada' && (
              <button type="button" className="tarjeta-mi-rutina-borrar" onClick={alBorrar} disabled={preparando}
                      aria-label={`Borrar ${nombre}`} title="Borrar rutina"><Trash2 /></button>
            )}
          </span>
        </div>
        <h3>{nombre}</h3>
        {datos.conCambios && <span className="tarjeta-mi-rutina-nota">Tienes cambios sin guardar</span>}
        <ol className="tarjeta-mi-rutina-pasos" aria-label="Ejercicios">
          {plan.map((p, i) => (
            <li key={`${p.skillId}-${i}`} title={p.nombre}>
              <span className="tarjeta-mi-rutina-numero">{i + 1}</span>
              <span className="tarjeta-mi-rutina-nombre">{p.nombre}</span>
              <span className="tarjeta-mi-rutina-objetivo">{textoObjetivo(p)}</span>
            </li>
          ))}
        </ol>

        {/* pie pegado abajo: las tarjetas de una fila miden lo mismo sin estirar la lista */}
        <div className="tarjeta-mi-rutina-pie">
          <div className="tarjeta-mi-rutina-acciones">
            <Boton onClick={alComenzar} disabled={preparando || plan.length === 0}><Play />Comenzar</Boton>
            <Boton variante="secundario" onClick={alEditar} disabled={preparando}><Pencil />Editar</Boton>
          </div>
        </div>
      </div>
    </article>
  )
}

/**
 * Nombre de la rutina y botón para guardarla, en la vista de personalizar.
 * Con `actual` guarda los cambios (y el nombre) en ella; sin `actual` crea una.
 */
export function GuardarRutina({ actual, rutinas, modificada, puedeGuardar, lleno, maxNombre, alGuardar }: {
  actual: RutinaGuardada | null
  rutinas: readonly RutinaGuardada[]
  modificada: boolean
  puedeGuardar: boolean
  lleno: boolean
  maxNombre: number
  /** devuelve el error de Python o null si se guardó */
  alGuardar: (nombre: string) => Promise<string | null>
}) {
  const id = useId()
  const [nombre, setNombre] = useState(actual?.nombre ?? '')
  const [error, setError] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [hecho, setHecho] = useState(false)
  const limpio = nombre.trim().split(/\s+/).filter(Boolean).join(' ')
  const sinCambios = actual !== null && !modificada && limpio === actual.nombre

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    const problema = problemaNombreRutina(nombre, rutinas.filter((r) => r.id !== actual?.id), maxNombre)
    if (problema) { setError(problema); return }
    setOcupado(true)
    const fallo = await alGuardar(limpio)
    setOcupado(false)
    setError(fallo)
    setHecho(!fallo)
  }

  return (
    <form className="guardar-rutina" onSubmit={(e) => void enviar(e)} noValidate>
      <label htmlFor={id} className="etiqueta">Nombre de la rutina</label>
      <div className="guardar-rutina-fila">
        <input id={id} value={nombre} maxLength={maxNombre} autoComplete="off" spellCheck={false}
               placeholder="Por ejemplo: Mañanas rápidas"
               aria-invalid={error ? true : undefined} aria-describedby={error ? `${id}-error` : undefined}
               onChange={(e) => { setNombre(e.target.value); setError(null); setHecho(false) }} />
        {/* solo el icono; el texto va en el tooltip y en el nombre accesible */}
        <span className="guardar-rutina-boton" title={actual ? 'Guardar cambios' : 'Guardar rutina'}>
          <Boton type="submit" variante="secundario" aria-label={actual ? 'Guardar cambios' : 'Guardar rutina'}
                 disabled={ocupado || !puedeGuardar || sinCambios || (!actual && lleno)}>
            {ocupado ? <Loader2 className="girando" /> : <Save />}
          </Boton>
        </span>
      </div>
      {error && <span id={`${id}-error`} className="control-error" role="alert">{error}</span>}
      {!error && hecho && sinCambios && (
        <span className="guardar-rutina-hecho" role="status"><Check aria-hidden="true" />Rutina guardada.</span>
      )}
      {!error && !actual && lleno && <span className="guardar-rutina-nota">Ya tienes el máximo de rutinas guardadas.</span>}
    </form>
  )
}
