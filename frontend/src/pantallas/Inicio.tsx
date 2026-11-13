import { AlertTriangle, ArrowLeft, ArrowRight, Loader2, Play, RotateCcw, Ruler, ScanLine, SlidersHorizontal, Sun } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Bridge, EjercicioCatalogo, Nivel, PasoRutina, RutinaGuardada } from '../bridge/tipos'
import { ControlesCabecera } from '../componentes/ajustes'
import { Aviso, Boton, Marca, plural } from '../componentes/basicos'
import { textoVista } from '../componentes/Figura'
import { GuardarRutina, VistaRutinas, type DatosTarjetaRutina } from '../componentes/misRutinas'
import { FiguraEjercicio, ResumenRutina, TarjetaEjercicio, textoEstimado, textoObjetivo } from '../componentes/rutina'
import { ChipPerfil } from '../componentes/perfil'
import { PanelPerfil, SelectorPerfil } from './Perfiles'
import { PanelProgreso, ResumenSemana } from './Progreso'
import { iniciarRutina, useCapacidad, useEstado } from '../estado/almacen'
import {
  borrarRutinaNombrada, guardarRutinaDiferido, guardarRutinaNombrada, guardarRutinaYa, perfilActivo, usePerfiles,
} from '../estado/perfiles'
import {
  alternar, cargarGuardada, estimarSegundos, fijarObjetivo, guardar, iguales, leerSeleccion, mover, planDe,
  problemas, seleccionDe, type Seleccion,
} from '../estado/rutina'

/** «Mi rutina» de quien entrena sin perfil: solo mientras la aplicación está abierta. */
let rutinaSinPerfil: Seleccion | null = null

type Seccion = 'bienvenida' | 'rutina' | 'progreso' | 'perfil'

/** Sección con la que abrir el inicio la próxima vez (p. ej. «Ver mi progreso» en el resumen). */
let seccionPendiente: Seccion | null = null

/** Vuelve al inicio directamente en «Mi progreso». */
export function irAProgreso(bridge: Bridge): void {
  seccionPendiente = 'progreso'
  void bridge.volverAlInicio()
}

const SIN_CATALOGO: EjercicioCatalogo[] = []
const SIN_RUTINAS: RutinaGuardada[] = []

function textoError(tipo: 'fuente' | 'modelo', fuente: 'camara' | 'video', elegirCamara: boolean) {
  if (tipo === 'modelo') {
    return { titulo: 'No se pudo preparar el reconocimiento de movimiento',
             ayuda: 'Falta el modelo de pose. Ejecuta: python scripts/descargar_modelos.py' }
  }
  return fuente === 'video'
    ? { titulo: 'No se pudo abrir el vídeo', ayuda: 'Revisa la ruta del archivo.' }
    : { titulo: 'No se detecta la cámara',
        ayuda: 'Comprueba que esté conectada y que ninguna otra aplicación la esté usando.'
          + (elegirCamara ? ' También puedes elegir otra cámara en Ajustes.' : '') }
}

/**
 * Inicio en dos secciones: la bienvenida y «Mi rutina», donde se eligen los
 * ejercicios, su orden y su objetivo. La sección es estado de la interfaz;
 * la fase (inicio/preparando/error) la sigue mandando Python.
 */
export function Inicio({ bridge }: { bridge: Bridge }) {
  const base = useEstado((s) => s.info?.rutina ?? null)
  const catalogo = useEstado((s) => s.info?.catalogo ?? SIN_CATALOGO)
  const fuente = useEstado((s) => s.info?.fuente ?? 'camara')
  const fase = useEstado((s) => s.estado?.fase ?? 'inicio')
  const errorApp = useEstado((s) => s.estado?.error ?? null)
  const conNivel = useCapacidad('nivel')
  const elegirCamara = useCapacidad('elegirCamara')
  const personalizable = useCapacidad('rutinaPersonalizada') && catalogo.length > 0
  const conHistorial = useCapacidad('historial')
  const conPerfiles = useCapacidad('perfiles')
  const perfiles = usePerfiles()
  const activo = perfilActivo(perfiles)
  const sinPerfil = conPerfiles && perfiles?.elegido === true && activo === null
  // el progreso es de un perfil: sin perfil no hay panel
  const conProgreso = conHistorial && (!conPerfiles || activo !== null)
  // «Cambiar de perfil» vuelve a preguntar quién entrena sin tocar Python
  const [cambiando, setCambiando] = useState(false)
  const preguntar = conPerfiles && perfiles !== null && (!perfiles.elegido || cambiando)
  const [nivel, setNivel] = useState<Nivel>('principiante')
  // sin limpiar aquí: StrictMode llama dos veces al inicializador
  const [seccion, setSeccion] = useState<Seccion>(() => seccionPendiente ?? 'bienvenida')
  useEffect(() => { seccionPendiente = null }, [])
  const [rechazada, setRechazada] = useState(false)
  const preparando = fase === 'preparando'

  const recomendada = useMemo(() => seleccionDe(base?.pasos ?? [], catalogo), [base, catalogo])
  const [seleccion, setSeleccion] = useState<Seleccion | null>(null)
  // campos de objetivo con un valor escrito que no vale
  const [invalidos, setInvalidos] = useState<ReadonlySet<string>>(new Set())

  // De quién es «Mi rutina» (ADR-009): del perfil que entrena (se guarda en
  // Python), de quien entrena sin perfil (solo en memoria) o, sin la capacidad
  // «perfiles», del navegador como antes. null: aún no se sabe quién entrena.
  const deQuien = !conPerfiles ? 'navegador' : activo ? activo.id : perfiles?.elegido ? 'sin-perfil' : null
  const rutinaDelPerfil = activo?.rutina ?? null

  // Rutinas guardadas con nombre del perfil, tal como valen hoy (sin ejercicios
  // retirados y con el objetivo en sus límites). `rutinaId`: la que se está usando.
  const rutinasPerfil = activo?.rutinas ?? SIN_RUTINAS
  const guardadas = useMemo<RutinaGuardada[]>(() => rutinasPerfil.flatMap((r) => {
    const pasos = leerSeleccion(r.pasos, catalogo)
    return pasos ? [{ id: r.id, nombre: r.nombre, pasos }] : []
  }), [rutinasPerfil, catalogo])
  const [rutinaId, setRutinaId] = useState<string | null>(null)
  const actual = guardadas.find((r) => r.id === rutinaId) ?? null

  // al llegar el catálogo o cambiar quién entrena, se carga su rutina (o la recomendada)
  useEffect(() => {
    if (deQuien === null || catalogo.length === 0) return
    guardarRutinaYa()                      // lo pendiente del perfil anterior no se pierde
    setInvalidos(new Set())
    setRechazada(false)
    const inicial = deQuien === 'navegador' ? cargarGuardada(catalogo)
      : deQuien === 'sin-perfil' ? rutinaSinPerfil
      : leerSeleccion(rutinaDelPerfil, catalogo)
    setSeleccion(inicial)
    // si lo último que armó es una de sus rutinas guardadas, sigue siendo esa
    setRutinaId(guardadas.find((r) => iguales(r.pasos, inicial ?? recomendada))?.id ?? null)
    // solo al cambiar de persona o de catálogo: la rutina del perfil se lee en ese momento
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deQuien, catalogo])

  const sel = seleccion ?? recomendada
  const cambiar = (nueva: Seleccion) => {
    setSeleccion(nueva)
    setRechazada(false)
    if (!conPerfiles) guardar(nueva)
    else if (activo) guardarRutinaDiferido(bridge, activo.id, nueva)
    else rutinaSinPerfil = nueva
  }
  const validar = (skillId: string, valido: boolean) => setInvalidos((prev) => {
    if (valido === !prev.has(skillId)) return prev
    const sig = new Set(prev)
    if (valido) sig.delete(skillId)
    else sig.add(skillId)
    return sig
  })

  const plan: PasoRutina[] = personalizable ? planDe(sel, catalogo) : (base?.pasos ?? [])
  // modificada respecto a la rutina guardada que se usa o, si no, a la recomendada
  const modificada = personalizable && !iguales(sel, actual ? actual.pasos : recomendada)
  const nombre = actual ? actual.nombre : modificada || !base ? 'Rutina de entrenamiento' : base.nombre
  const estimadoS = estimarSegundos(sel, catalogo)
  const avisos = personalizable
    ? [...problemas(sel.filter((p) => !invalidos.has(p.skillId)), catalogo),
       ...(sel.some((p) => invalidos.has(p.skillId)) ? ['Corrige los objetivos marcados en rojo.'] : [])]
    : base ? [] : ['Cargando la rutina…']
  const error = errorApp ? textoError(errorApp.tipo, fuente, elegirCamara)
    : rechazada ? { titulo: 'No se pudo iniciar esta rutina', ayuda: 'Revisa los ejercicios y sus objetivos.' }
    : null

  /** Empieza la rutina elegida o, con `con`, otra (desde una tarjeta de «Mis rutinas»). */
  const comenzar = async (con?: { pasos: Seleccion; nombre: string }) => {
    guardarRutinaYa()                      // la rutina con la que se entrena queda guardada
    const opciones = conNivel ? { nivel } : undefined
    if (!personalizable) { void bridge.iniciar(opciones); return }
    if (con ? problemas(con.pasos, catalogo).length > 0 : avisos.length > 0) return
    setRechazada(!(await iniciarRutina(bridge,
      con ? { nombre: con.nombre, pasos: planDe(con.pasos, catalogo) } : { nombre, pasos: plan }, opciones)))
  }

  // -- «Mis rutinas» (con perfil): primero las tarjetas; «Editar» abre la vista de personalizar --
  const conTarjetas = personalizable && activo !== null
  const [editando, setEditando] = useState(false)
  const irARutinas = () => { setSeccion('rutina'); setEditando(false) }
  const nombreRecomendada = base?.nombre ?? 'Rutina recomendada'
  const maxRutinas = perfiles?.maxRutinas ?? 10
  const pasosDe = (clave: string): { id: string | null; pasos: Seleccion; nombre: string } =>
    clave === 'borrador' ? { id: null, pasos: sel, nombre: 'Rutina de entrenamiento' }
      : clave === 'recomendada' ? { id: null, pasos: recomendada, nombre: nombreRecomendada }
      : (() => { const r = guardadas.find((g) => g.id === clave); return { id: r?.id ?? null, pasos: r?.pasos ?? [], nombre: r?.nombre ?? '' } })()
  const tarjeta = (clave: string, tipo: DatosTarjetaRutina['tipo'], nombreT: string, pasos: Seleccion,
                   enUso: boolean): DatosTarjetaRutina => ({
    clave, tipo, nombre: nombreT, plan: planDe(pasos, catalogo), estimadoS: estimarSegundos(pasos, catalogo),
    enUso, conCambios: enUso && tipo === 'guardada' && modificada,
  })
  const tarjetas: DatosTarjetaRutina[] = [
    // lo armado sin guardar no se pierde: se ofrece como una tarjeta más
    ...(rutinaId === null && modificada && sel.length > 0
      ? [tarjeta('borrador', 'borrador', 'Rutina personalizada', sel, true)] : []),
    tarjeta('recomendada', 'recomendada', nombreRecomendada, recomendada, rutinaId === null && !modificada),
    ...guardadas.map((r) => tarjeta(r.id, 'guardada', r.nombre, r.pasos, r.id === rutinaId)),
  ]
  /** Deja en uso la rutina de esa tarjeta. Al editar, la que ya estaba en uso conserva sus cambios. */
  const usar = (clave: string, paraEditar: boolean) => {
    const r = pasosDe(clave)
    setRutinaId(r.id)
    setInvalidos(new Set())
    const conservar = paraEditar && (clave === 'borrador' || (r.id !== null && r.id === rutinaId))
    if (!conservar) cambiar(r.pasos)
    return r
  }
  const vistaRutinas = (
    <VistaRutinas tarjetas={tarjetas} lleno={guardadas.length >= maxRutinas} maxRutinas={maxRutinas}
      preparando={preparando} alVolver={() => setSeccion('bienvenida')}
      alComenzar={(clave) => {
        const r = usar(clave, false)
        setSeccion('bienvenida')            // ahí se ve «Preparando la cámara…» o el error
        void comenzar(r)
      }}
      alEditar={(clave) => { usar(clave, true); setEditando(true) }}
      alNueva={() => { setRutinaId(null); setInvalidos(new Set()); cambiar([]); setEditando(true) }}
      alBorrar={async (clave) => {
        if (!activo) return null
        const r = await borrarRutinaNombrada(bridge, activo.id, clave)
        if (!r.ok) return r.error
        if (clave === rutinaId) setRutinaId(null)   // sus ejercicios siguen elegidos, sin guardar
        return null
      }} />
  )
  const guardado = !personalizable ? null : activo ? (
    <GuardarRutina actual={actual} rutinas={guardadas} modificada={modificada}
      puedeGuardar={sel.length > 0 && avisos.length === 0} lleno={guardadas.length >= maxRutinas}
      maxNombre={perfiles?.maxNombreRutina ?? 40}
      alGuardar={async (n) => {
        const r = await guardarRutinaNombrada(bridge, activo.id, { id: actual?.id, nombre: n, pasos: sel })
        if (!r.ok) return r.error
        // una nueva pasa a ser la rutina en uso
        if (!actual) setRutinaId(r.perfil.rutinas.find((x) => !rutinasPerfil.some((y) => y.id === x.id))?.id ?? null)
        return null
      }} />
  ) : sinPerfil ? (
    <p className="guardar-rutina-nota">Con un perfil puedes guardar tus rutinas con un nombre.</p>
  ) : null

  if (preguntar || (conPerfiles && perfiles === null)) {
    return (
      <main className="pantalla pantalla-inicio">
        <header className="cabecera">
          {/* si ya había perfil y se está cambiando, el logo cancela el cambio */}
          <Marca alInicio={perfiles?.elegido && cambiando
            ? () => { setCambiando(false); setSeccion('bienvenida') } : undefined} />
          <div className="cabecera-derecha"><ControlesCabecera bridge={bridge} /></div>
        </header>
        {perfiles && (
          <SelectorPerfil bridge={bridge} estado={perfiles}
                          alElegir={() => { setCambiando(false); setSeccion('bienvenida') }} />
        )}
      </main>
    )
  }

  return (
    <main className="pantalla pantalla-inicio">
      <header className="cabecera">
        <Marca alInicio={() => setSeccion('bienvenida')} />
        {(personalizable || conProgreso) && (
          <nav className="navegacion" aria-label="Secciones">
            <button className={seccion === 'bienvenida' ? 'activa' : undefined}
                    aria-current={seccion === 'bienvenida' ? 'page' : undefined}
                    onClick={() => setSeccion('bienvenida')}>Inicio</button>
            {personalizable && (
              <button className={seccion === 'rutina' ? 'activa' : undefined}
                      aria-current={seccion === 'rutina' ? 'page' : undefined}
                      onClick={irARutinas}>
                {conTarjetas ? 'Mis rutinas' : <>Mi rutina <span className="navegacion-cuenta">{sel.length}</span></>}
              </button>
            )}
            {conProgreso && (
              <button className={seccion === 'progreso' ? 'activa' : undefined}
                      aria-current={seccion === 'progreso' ? 'page' : undefined}
                      onClick={() => setSeccion('progreso')}>
                Mi progreso
              </button>
            )}
          </nav>
        )}
        <div className="cabecera-derecha">
          {conPerfiles && perfiles?.elegido && (
            <ChipPerfil perfil={activo} activa={seccion === 'perfil'} onClick={() => setSeccion('perfil')} />
          )}
          <ControlesCabecera bridge={bridge} />
        </div>
      </header>

      {seccion === 'perfil' && conPerfiles && perfiles ? (
        <PanelPerfil bridge={bridge} estado={perfiles} alVolver={() => setSeccion('bienvenida')}
                     alCambiar={() => setCambiando(true)}
                     alProgreso={conProgreso ? () => setSeccion('progreso') : undefined} />
      ) : seccion === 'progreso' && conProgreso ? (
        // key: al cambiar de perfil se vuelve a pedir su historial
        <PanelProgreso key={activo?.id ?? 'sin'} bridge={bridge} alVolver={() => setSeccion('bienvenida')} />
      ) : seccion === 'rutina' && conTarjetas && !editando ? (
        vistaRutinas
      ) : seccion === 'rutina' && personalizable ? (
        <section className="elegir-cuerpo">
          <div className="elegir-catalogo">
            {conTarjetas ? (
              <button className="enlace-volver" onClick={() => setEditando(false)}>
                <ArrowLeft />Volver a mis rutinas
              </button>
            ) : (
              <button className="enlace-volver" onClick={() => setSeccion('bienvenida')}>
                <ArrowLeft />Volver al inicio
              </button>
            )}
            <span className="etiqueta etiqueta-marca">Paso 1 · Elige y ajusta</span>
            <h1>Personaliza tu rutina</h1>
            <p className="elegir-ayuda">
              Toca un ejercicio para añadirlo o quitarlo y ajusta sus repeticiones o segundos.
              Se harán en el orden que ves en «Tu rutina», y ahí puedes cambiarlo.
            </p>
            <div className="rejilla-ejercicios">
              {catalogo.map((ej) => {
                const i = sel.findIndex((p) => p.skillId === ej.skillId)
                return (
                  <TarjetaEjercicio key={ej.skillId} ej={ej} posicion={i >= 0 ? i + 1 : null}
                    objetivo={i >= 0 ? sel[i].objetivo : ej.objetivo}
                    alAlternar={() => { validar(ej.skillId, true); cambiar(alternar(sel, ej)) }}
                    alCambiarObjetivo={(v) => cambiar(fijarObjetivo(sel, ej.skillId, v))}
                    alValidar={(ok) => validar(ej.skillId, ok)} />
                )
              })}
            </div>
          </div>

          <ResumenRutina nombre={nombre} pasos={plan} estimadoS={estimadoS} avisos={avisos}
            modificada={modificada} preparando={preparando} error={error}
            alMover={(i, d) => cambiar(mover(sel, i, d))}
            alQuitar={(id) => { validar(id, true); cambiar(sel.filter((p) => p.skillId !== id)) }}
            alRestablecer={() => { setInvalidos(new Set()); cambiar(actual ? actual.pasos : recomendada) }}
            textoRestablecer={actual ? `Volver a «${actual.nombre}» como está guardada` : undefined}
            alComenzar={() => void comenzar()}
            guardado={guardado}
            extra={conNivel && <SelectorNivel nivel={nivel} alCambiar={setNivel} />} />
        </section>
      ) : (
        <Bienvenida nombre={nombre} saludo={activo?.nombre ?? null} sinPerfil={sinPerfil}
          plan={plan} estimadoS={personalizable ? estimadoS : null}
          personalizable={personalizable} preparando={preparando} error={error} avisos={avisos}
          alPersonalizar={irARutinas} alComenzar={() => void comenzar()} conTarjetas={conTarjetas}
          nivel={conNivel ? <SelectorNivel nivel={nivel} alCambiar={setNivel} /> : null}
          semana={conProgreso && activo
            ? <ResumenSemana key={activo.id} bridge={bridge} alVer={() => setSeccion('progreso')} />
            : null} />
      )}
    </main>
  )
}

function Bienvenida({ nombre, saludo, sinPerfil, plan, estimadoS, personalizable, preparando, error, avisos,
                      alPersonalizar, alComenzar, conTarjetas, nivel, semana }: {
  nombre: string
  /** nombre del perfil que entrena (ADR-009) */
  saludo: string | null
  sinPerfil: boolean
  plan: PasoRutina[]
  estimadoS: number | null
  personalizable: boolean
  preparando: boolean
  error: { titulo: string; ayuda: string } | null
  avisos: string[]
  alPersonalizar: () => void
  alComenzar: () => void
  /** con perfil, «Personalizar» lleva a las tarjetas de «Mis rutinas» */
  conTarjetas: boolean
  nivel: ReactNode
  /** meta y racha del perfil (ADR-009); null sin perfil o sin historial */
  semana: ReactNode
}) {
  return (
    <section className="inicio-cuerpo">
      <div className="inicio-texto">
        <span className="etiqueta etiqueta-marca">{saludo ? `Hola, ${saludo} · Sesión de hoy` : 'Sesión de hoy'}</span>
        <h1>Tu sesión,<br /><em>a tu ritmo.</em></h1>
        <p className="inicio-proposito">
          Analizo tus movimientos en tiempo real y te doy indicaciones por voz para ayudarte a mejorar tu técnica.
        </p>

        <ul className="consejos" aria-label="Antes de empezar">
          <li><Ruler aria-hidden="true" />Aléjate unos 2,5–3 m de la pantalla</li>
          <li><ScanLine aria-hidden="true" />Que se vea tu cuerpo entero</li>
          <li><Sun aria-hidden="true" />Busca un lugar con buena luz</li>
        </ul>

        {nivel}

        {error && (
          <Aviso tipo="bloqueo" icono={<AlertTriangle />} titulo={error.titulo}
                 accion={<Boton variante="secundario" onClick={alComenzar}><RotateCcw />Reintentar</Boton>}>
            {error.ayuda}
          </Aviso>
        )}

        {!error && (
          <div className="acciones">
            {/* empezar es lo principal del inicio; personalizar queda como alternativa */}
            <Boton onClick={alComenzar} disabled={preparando || avisos.length > 0}>
              {preparando ? <><Loader2 className="girando" />Preparando la cámara…</>
                : <><Play />Comenzar sesión</>}
            </Boton>
            {personalizable && (
              <Boton variante="secundario" onClick={alPersonalizar} disabled={preparando}>
                <SlidersHorizontal />{conTarjetas ? 'Mis rutinas' : 'Personalizar rutina'}
              </Boton>
            )}
          </div>
        )}
        {sinPerfil && <p className="campo-ayuda">Entrenas sin perfil: esta sesión no se guardará.</p>}
        <p className="descargo">
          ESTELA te da indicaciones sobre tu técnica; no reemplaza a un profesional ni hace diagnósticos.
        </p>
      </div>

      <div className="inicio-lateral">
      {semana}
      <article className="tarjeta tarjeta-rutina">
        <span className="etiqueta">
          {plural(plan.length, 'ejercicio', 'ejercicios')}{estimadoS != null && plan.length > 0 && ` · ${textoEstimado(estimadoS)}`}
        </span>
        <h2>{nombre}</h2>
        {plan.length === 0 ? (
          <p className="tarjeta-rutina-vacia">Todavía no has elegido ejercicios.</p>
        ) : (
          <ol className="lista-pasos">
            {plan.map((p, i) => (
              <li key={`${p.skillId}-${i}`}>
                <span className="paso-figura"><FiguraEjercicio paso={p} /></span>
                <div>
                  <strong>{p.nombre}</strong>
                  <span>{textoVista(p.orientacion)}</span>
                </div>
                <span className="paso-objetivo">{textoObjetivo(p)}</span>
              </li>
            ))}
          </ol>
        )}
        {personalizable && (
          <button className="enlace-editar" onClick={alPersonalizar}>
            {conTarjetas ? 'Cambiar o editar rutina' : 'Editar ejercicios y objetivos'}<ArrowRight />
          </button>
        )}
      </article>
      </div>
    </section>
  )
}

function SelectorNivel({ nivel, alCambiar }: { nivel: Nivel; alCambiar: (n: Nivel) => void }) {
  return (
    <div className="selector-nivel" role="radiogroup" aria-label="Nivel">
      {(['principiante', 'avanzado'] as Nivel[]).map((n) => (
        <button key={n} role="radio" aria-checked={nivel === n}
                className={nivel === n ? 'activo' : undefined} onClick={() => alCambiar(n)}>
          {n === 'principiante' ? 'Principiante' : 'Avanzado'}
        </button>
      ))}
    </div>
  )
}
