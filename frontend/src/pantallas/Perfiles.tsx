import { ArrowLeft, Lock, Plus, Target, Trash2, TrendingUp, UserRound, Users } from 'lucide-react'
import { useState } from 'react'
import type { Bridge, EstadoPerfiles } from '../bridge/tipos'
import { Aviso, Boton } from '../componentes/basicos'
import { Avatar, FormularioPerfil } from '../componentes/perfil'
import { fechaCorta } from '../estado/progreso'
import { borrarPerfil, crearPerfil, editarPerfil, elegirPerfil, perfilActivo, textoMeta } from '../estado/perfiles'

const AVISO_PRIVACIDAD = 'Cada perfil guarda su progreso solo en este equipo. No hay contraseña: quien use este equipo puede ver los perfiles.'

/**
 * «¿Quién entrena hoy?»: se muestra al abrir la aplicación y al cambiar de
 * perfil. Sin perfiles, empieza directamente en el formulario para crear uno.
 */
export function SelectorPerfil({ bridge, estado, alElegir }: {
  bridge: Bridge
  estado: EstadoPerfiles
  alElegir: () => void
}) {
  const [creando, setCreando] = useState(estado.perfiles.length === 0)
  const lleno = estado.perfiles.length >= estado.maxPerfiles
  const elegir = async (id: string | null) => { if (await elegirPerfil(bridge, id)) alElegir() }

  const primeraVez = estado.perfiles.length === 0
  return (
    <section className="perfiles-cuerpo perfiles-selector">
      <div className="perfiles-cabeza">
        <span className="etiqueta etiqueta-marca">Antes de empezar</span>
        <h1>{creando && primeraVez ? <>Crea tu <em>perfil.</em></> : <>¿Quién entrena <em>hoy?</em></>}</h1>
        {!creando && <p className="perfiles-sub">Elige tu perfil para guardar tu progreso y seguir tu meta semanal.</p>}
      </div>

      {creando ? (
        <article className="tarjeta tarjeta-formulario">
          {/* la primera vez el título ya dice «Crea tu perfil» */}
          {!primeraVez && <h2>Nuevo perfil</h2>}
          <FormularioPerfil estado={estado} textoGuardar="Crear perfil"
            alGuardar={async (datos) => {
              const r = await crearPerfil(bridge, datos)    // Python lo deja elegido
              if (r.ok) alElegir()
              return r
            }}
            alCancelar={estado.perfiles.length > 0 ? () => setCreando(false) : undefined} />
        </article>
      ) : (
        <ul className="rejilla-perfiles">
          {estado.perfiles.map((p) => (
            <li key={p.id}>
              <button className={`tarjeta tarjeta-perfil ${p.id === estado.activo ? 'actual' : ''}`} onClick={() => void elegir(p.id)}>
                <Avatar nombre={p.nombre} color={p.color} tam="xl" />
                <strong>{p.nombre}</strong>
                <span>{textoMeta(p.metaSemanal)}</span>
              </button>
            </li>
          ))}
          {!lleno && (
            <li>
              <button className="tarjeta tarjeta-perfil tarjeta-perfil-nuevo" onClick={() => setCreando(true)}>
                <span className="avatar avatar-xl avatar-vacio" aria-hidden="true"><Plus /></span>
                <strong>Nuevo perfil</strong>
                <span>Nombre, color y meta</span>
              </button>
            </li>
          )}
        </ul>
      )}
      {lleno && !creando && <p className="campo-ayuda">Hay {estado.maxPerfiles} perfiles, el máximo. Para crear otro, borra uno desde «Mi perfil».</p>}

      <button className="enlace-volver enlace-sin-perfil" onClick={() => void elegir(null)}>
        <UserRound aria-hidden="true" />Entrenar sin perfil <span>· no se guarda la sesión</span>
      </button>
      {/* ADR-009 §2.5: el aviso va en el selector; abajo, para no tapar la elección */}
      <p className="progreso-privacidad perfiles-privacidad"><Lock aria-hidden="true" />{AVISO_PRIVACIDAD}</p>
    </section>
  )
}

/** «Mi perfil»: editar nombre, color y meta; cambiar de perfil; borrarlo. */
export function PanelPerfil({ bridge, estado, alVolver, alCambiar, alProgreso }: {
  bridge: Bridge
  estado: EstadoPerfiles
  alVolver: () => void
  alCambiar: () => void
  /** abre «Mi progreso»; sin historial no se ofrece */
  alProgreso?: () => void
}) {
  const perfil = perfilActivo(estado)
  const [confirmar, setConfirmar] = useState(false)
  const [fallo, setFallo] = useState(false)

  return (
    <section className="perfiles-cuerpo">
      <div className="perfiles-cabeza">
        <button className="enlace-volver" onClick={alVolver}><ArrowLeft />Volver al inicio</button>
        <span className="etiqueta etiqueta-marca">Mi perfil</span>
        {perfil ? (
          <div className="perfil-titulo">
            <Avatar nombre={perfil.nombre} color={perfil.color} tam="lg" />
            <div>
              <h1>{perfil.nombre}</h1>
              {perfil.creado && <span>Perfil creado el {fechaCorta(perfil.creado)}</span>}
            </div>
          </div>
        ) : (
          <h1>Estás entrenando<br /><em>sin perfil.</em></h1>
        )}
        <p className="progreso-privacidad"><Lock aria-hidden="true" />{AVISO_PRIVACIDAD}</p>
      </div>

      {perfil ? (
        <div className="perfil-rejilla">
          <article className="tarjeta tarjeta-formulario">
            <h2>Editar perfil</h2>
            {/* key: si cambia el perfil activo, el formulario empieza de nuevo */}
            <FormularioPerfil key={perfil.id} estado={estado} inicial={perfil} textoGuardar="Guardar cambios"
              alGuardar={(datos) => editarPerfil(bridge, perfil.id, datos)} />
          </article>

          <aside className="perfil-lateral">
            <article className="tarjeta perfil-opciones">
              <h2>Meta y opciones</h2>
              <p className="meta-actual"><Target aria-hidden="true" />{textoMeta(perfil.metaSemanal)}</p>
              <div className="perfil-opciones-botones">
                {alProgreso && <Boton variante="secundario" onClick={alProgreso}><TrendingUp />Ver mi progreso</Boton>}
                <Boton variante="secundario" onClick={alCambiar}><Users />Cambiar de perfil</Boton>
              </div>
            </article>

            <article className="tarjeta zona-cuidado">
              <h2>Borrar perfil</h2>
              <p>Se borran de este equipo el perfil y todo su historial.</p>
              {confirmar ? (
              <Aviso tipo="cuidado" icono={<Trash2 />} titulo={`¿Borrar el perfil de ${perfil.nombre}?`}
                     accion={<div className="acciones">
                       <Boton variante="peligro" onClick={async () => {
                         const ok = await borrarPerfil(bridge, perfil.id)   // Python vuelve a preguntar quién entrena
                         setFallo(!ok)
                         setConfirmar(false)
                       }}>Sí, borrar</Boton>
                       <Boton variante="suave" onClick={() => setConfirmar(false)}>Cancelar</Boton>
                     </div>}>
                No se puede deshacer.
              </Aviso>
            ) : (
              <Boton variante="peligro" onClick={() => setConfirmar(true)}><Trash2 />Borrar este perfil</Boton>
            )}
              {fallo && <p className="texto-peligro">No se pudo borrar el perfil. Inténtalo de nuevo.</p>}
            </article>
          </aside>
        </div>
      ) : (
        <article className="tarjeta perfil-invitado">
          <p>Tus sesiones no se guardan y no tienes panel de progreso. Elige o crea un perfil para llevar tu seguimiento.</p>
          <div className="acciones">
            <Boton onClick={alCambiar}><Users />Elegir o crear un perfil</Boton>
          </div>
        </article>
      )}
    </section>
  )
}
