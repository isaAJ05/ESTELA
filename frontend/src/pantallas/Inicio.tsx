import { AlertTriangle, ArrowLeft, ArrowRight, FileVideo, Loader2, Play, RotateCcw, Ruler, ScanLine, SlidersHorizontal, Sun } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Bridge, EjercicioCatalogo, Nivel, PasoRutina } from '../bridge/tipos'
import { ControlesCabecera } from '../componentes/ajustes'
import { Aviso, Boton, Marca, plural } from '../componentes/basicos'
import { textoVista } from '../componentes/Figura'
import { FiguraEjercicio, ResumenRutina, TarjetaEjercicio, textoEstimado, textoObjetivo } from '../componentes/rutina'
import { iniciarRutina, useCapacidad, useEstado } from '../estado/almacen'
import {
  alternar, cargarGuardada, estimarSegundos, fijarObjetivo, guardar, iguales, mover, planDe, problemas,
  seleccionDe, type Seleccion,
} from '../estado/rutina'

type Seccion = 'bienvenida' | 'rutina'

const SIN_CATALOGO: EjercicioCatalogo[] = []

function textoError(tipo: 'fuente' | 'modelo', fuente: 'camara' | 'video') {
  if (tipo === 'modelo') {
    return { titulo: 'No se pudo preparar el reconocimiento de movimiento',
             ayuda: 'Falta el modelo de pose. Ejecuta: python scripts/descargar_modelos.py' }
  }
  return fuente === 'video'
    ? { titulo: 'No se pudo abrir el vídeo', ayuda: 'Revisa la ruta del archivo.' }
    : { titulo: 'No se detecta la cámara',
        ayuda: 'Comprueba que esté conectada y que ninguna otra aplicación la esté usando.' }
}

/**
 * Inicio en dos secciones: la bienvenida y «Mi rutina», donde se eligen los
 * ejercicios, su orden y su objetivo. La sección es estado de la interfaz;
 * la fase (inicio/preparando/error) la sigue mandando Python.
 */
export function Inicio({ bridge }: { bridge: Bridge }) {
  const base = useEstado((s) => s.info?.rutina ?? null)
  const catalogo = useEstado((s) => s.info?.catalogo ?? SIN_CATALOGO)
  const fuente = useEstado((s) => s.estado?.fuente ?? s.info?.fuente ?? 'camara')
  const fase = useEstado((s) => s.estado?.fase ?? 'inicio')
  const errorApp = useEstado((s) => s.estado?.error ?? null)
  const conNivel = useCapacidad('nivel')
  const probarVideo = useCapacidad('probarVideo')
  const personalizable = useCapacidad('rutinaPersonalizada') && catalogo.length > 0
  const [nivel, setNivel] = useState<Nivel>('principiante')
  const [seccion, setSeccion] = useState<Seccion>('bienvenida')
  const [rechazada, setRechazada] = useState(false)
  const preparando = fase === 'preparando'

  const recomendada = useMemo(() => seleccionDe(base?.pasos ?? [], catalogo), [base, catalogo])
  const [seleccion, setSeleccion] = useState<Seleccion | null>(null)
  // campos de objetivo con un valor escrito que no vale
  const [invalidos, setInvalidos] = useState<ReadonlySet<string>>(new Set())

  // la selección se arma cuando llega el catálogo: la última guardada o la recomendada
  useEffect(() => {
    if (seleccion === null && catalogo.length > 0) setSeleccion(cargarGuardada(catalogo) ?? recomendada)
  }, [catalogo, recomendada, seleccion])

  const sel = seleccion ?? recomendada
  const cambiar = (nueva: Seleccion) => {
    setSeleccion(nueva)
    setRechazada(false)
    guardar(nueva)
  }
  const validar = (skillId: string, valido: boolean) => setInvalidos((prev) => {
    if (valido === !prev.has(skillId)) return prev
    const sig = new Set(prev)
    if (valido) sig.delete(skillId)
    else sig.add(skillId)
    return sig
  })

  const plan: PasoRutina[] = personalizable ? planDe(sel, catalogo) : (base?.pasos ?? [])
  const modificada = personalizable && !iguales(sel, recomendada)
  const nombre = modificada || !base ? 'Rutina de entrenamiento' : base.nombre
  const estimadoS = estimarSegundos(sel, catalogo)
  const avisos = personalizable
    ? [...problemas(sel.filter((p) => !invalidos.has(p.skillId)), catalogo),
       ...(sel.some((p) => invalidos.has(p.skillId)) ? ['Corrige los objetivos marcados en rojo.'] : [])]
    : base ? [] : ['Cargando la rutina…']
  const error = errorApp ? textoError(errorApp.tipo, fuente)
    : rechazada ? { titulo: 'No se pudo iniciar esta rutina', ayuda: 'Revisa los ejercicios y sus objetivos.' }
    : null

  // sin `video` se usa la cámara (no se repite un vídeo de prueba anterior)
  const comenzar = async (video?: string) => {
    const opciones = { ...(conNivel ? { nivel } : {}), ...(video ? { video } : {}) }
    if (!personalizable) { void bridge.iniciar(opciones); return }
    if (avisos.length > 0) return
    setRechazada(!(await iniciarRutina(bridge, { nombre, pasos: plan }, opciones)))
  }
  const comenzarConVideo = async () => {
    const ruta = await bridge.elegirVideo()
    if (ruta) await comenzar(ruta)
  }

  return (
    <main className="pantalla pantalla-inicio">
      <header className="cabecera">
        <Marca />
        {personalizable && (
          <nav className="navegacion" aria-label="Secciones">
            <button className={seccion === 'bienvenida' ? 'activa' : undefined}
                    aria-current={seccion === 'bienvenida' ? 'page' : undefined}
                    onClick={() => setSeccion('bienvenida')}>Inicio</button>
            <button className={seccion === 'rutina' ? 'activa' : undefined}
                    aria-current={seccion === 'rutina' ? 'page' : undefined}
                    onClick={() => setSeccion('rutina')}>
              Mi rutina <span className="navegacion-cuenta">{sel.length}</span>
            </button>
          </nav>
        )}
        <div className="cabecera-derecha">
          <ControlesCabecera bridge={bridge} />
        </div>
      </header>

      {seccion === 'rutina' && personalizable ? (
        <section className="elegir-cuerpo">
          <div className="elegir-catalogo">
            <button className="enlace-volver" onClick={() => setSeccion('bienvenida')}>
              <ArrowLeft />Volver al inicio
            </button>
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
            alRestablecer={() => { setInvalidos(new Set()); cambiar(recomendada) }}
            alComenzar={() => void comenzar()}
            extra={conNivel && <SelectorNivel nivel={nivel} alCambiar={setNivel} />} />
        </section>
      ) : (
        <Bienvenida nombre={nombre} plan={plan} estimadoS={personalizable ? estimadoS : null}
          personalizable={personalizable} preparando={preparando} error={error} avisos={avisos}
          fuente={fuente} alPersonalizar={() => setSeccion('rutina')} alComenzar={() => void comenzar()}
          alProbarVideo={probarVideo ? () => void comenzarConVideo() : null}
          nivel={conNivel ? <SelectorNivel nivel={nivel} alCambiar={setNivel} /> : null} />
      )}
    </main>
  )
}

function Bienvenida({ nombre, plan, estimadoS, personalizable, preparando, error, avisos,
                      fuente, alPersonalizar, alComenzar, alProbarVideo, nivel }: {
  nombre: string
  plan: PasoRutina[]
  estimadoS: number | null
  personalizable: boolean
  preparando: boolean
  error: { titulo: string; ayuda: string } | null
  avisos: string[]
  fuente: 'camara' | 'video'
  alPersonalizar: () => void
  alComenzar: () => void
  /** «Probar con un vídeo», solo con la capacidad «probarVideo» */
  alProbarVideo: (() => void) | null
  nivel: ReactNode
}) {
  return (
    <section className="inicio-cuerpo">
      <div className="inicio-texto">
        <span className="etiqueta etiqueta-marca">Sesión de hoy</span>
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
            {personalizable && (
              <Boton onClick={alPersonalizar} disabled={preparando}><SlidersHorizontal />Personalizar mi rutina</Boton>
            )}
            <Boton variante={personalizable ? 'secundario' : 'primario'} onClick={alComenzar}
                   disabled={preparando || avisos.length > 0}>
              {preparando ? <><Loader2 className="girando" />{fuente === 'video' ? 'Abriendo el vídeo…' : 'Preparando la cámara…'}</>
                : <><Play />{personalizable ? 'Empezar ya' : 'Comenzar sesión'}</>}
            </Boton>
            {alProbarVideo && (
              <Boton variante="suave" onClick={alProbarVideo} disabled={preparando || avisos.length > 0}>
                <FileVideo />Probar con un vídeo
              </Boton>
            )}
          </div>
        )}
        <p className="descargo">
          ESTELA te da indicaciones sobre tu técnica; no reemplaza a un profesional ni hace diagnósticos.
        </p>
      </div>

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
            Editar ejercicios y objetivos<ArrowRight />
          </button>
        )}
      </article>
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
