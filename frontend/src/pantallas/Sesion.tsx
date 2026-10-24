import { Check, Circle, DraftingCompass, Info, Loader2, Pause, Play, RotateCcw, RotateCw, ScanLine, SkipForward, Sparkles, Square, UserX, Volume2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { Bridge, Colocacion as ColocacionEstado, EstadoSesion, Feedback, PasoRutina, TipoAviso } from '../bridge/tipos'
import { BotonVoz } from '../componentes/ajustes'
import { Aviso, Boton, Marca, plural } from '../componentes/basicos'
import { Figura, textoVista } from '../componentes/Figura'
import { Constelacion, Progreso } from '../componentes/progreso'
import { GuiaAnimada, VistaCamara } from '../componentes/VistaCamara'
import { cambiarAjustes, leerVoz } from '../estado/ajustes'
import { useCapacidad, useEstado } from '../estado/almacen'

const MENSAJE_VISIBLE_MS = 4500
const TRANSICION_VISIBLE_MS = 4000
/** un motivo para no evaluar se mantiene en pantalla al menos esto, para que no parpadee */
const MOTIVO_VISIBLE_MS = 800

/** Lee un campo de la sesión en curso (re-renderiza solo si cambia). */
function useSesion<K extends keyof EstadoSesion>(campo: K): EstadoSesion[K] | null {
  return useEstado((s) => s.estado?.sesion?.[campo] ?? null)
}

export function Sesion({ bridge }: { bridge: Bridge }) {
  const hayDatos = useEstado((s) => s.estado?.sesion != null)
  const pausaManual = useCapacidad('pausaManual')
  const pausada = useSesion('pausada')
  const silenciable = useCapacidad('silenciarVoz')
  const conColocacion = useCapacidad('colocacion')
  const [confirmar, setConfirmar] = useState(false)
  const [depurar, setDepurar] = useState(false)
  const [angulos, setAngulos] = useState(() => {
    try { return localStorage.getItem('estela.angulos') === '1' } catch { return false }
  })
  const alternarAngulos = () => setAngulos((a) => {
    try { localStorage.setItem('estela.angulos', a ? '0' : '1') } catch { /* sin almacenamiento */ }
    return !a
  })

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return
      const k = e.key.toLowerCase()
      if (k === 'escape') setConfirmar((c) => !c)
      else if (confirmar) return
      else if (k === 'n') void bridge.siguiente()
      else if (k === 'r') void bridge.reiniciar()
      else if (k === 'd') setDepurar((d) => !d)
      else if (k === 'a') alternarAngulos()
      else if (k === 'v' && silenciable) cambiarAjustes({ voz: !leerVoz() }, bridge)
      else if (k === ' ' && pausaManual) { e.preventDefault(); void (pausada ? bridge.reanudar() : bridge.pausar()) }
    }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [bridge, confirmar, pausaManual, pausada, silenciable])

  return (
    <main className="pantalla pantalla-sesion">
      <BarraSuperior bridge={bridge} alTerminar={() => setConfirmar(true)}
                     angulos={angulos} alternarAngulos={alternarAngulos} />
      <div className="sesion-cuerpo">
        <div className="escenario-zona">
        <section className="escenario">
          <VistaCamara mostrarAngulos={angulos} />
          {hayDatos ? <>
            <AvisoSesion />
            <BandaMensaje />
            {conColocacion ? <Colocacion bridge={bridge} /> : <Transicion />}
            <Pausa bridge={bridge} alTerminar={() => setConfirmar(true)} />
          </> : (
            <div className="escenario-cargando"><Loader2 className="girando" />Buscándote en la cámara…</div>
          )}
          {depurar && <Depuracion />}
        </section>
        </div>
        <PanelEjercicio />
      </div>
      {confirmar && (
        <Dialogo alSeguir={() => setConfirmar(false)}
                 alTerminar={() => { setConfirmar(false); void bridge.terminar() }} />
      )}
    </main>
  )
}

function BarraSuperior({ bridge, alTerminar, angulos, alternarAngulos }: {
  bridge: Bridge; alTerminar: () => void; angulos: boolean; alternarAngulos: () => void
}) {
  const paso = useSesion('paso') ?? 1
  const total = useEstado((s) => s.estado?.sesion?.totalPasos ?? s.plan?.pasos.length ?? 0)
  const pausaManual = useCapacidad('pausaManual')
  const pausada = useSesion('pausada')
  return (
    <header className="cabecera cabecera-sesion">
      <Marca />
      <div className="cabecera-progreso">
        <Constelacion paso={paso} total={total} />
        <span className="etiqueta">Ejercicio {paso} de {total}</span>
      </div>
      <nav className="acciones-sesion" aria-label="Controles de la sesión">
        {pausaManual && (
          <Boton variante="suave" onClick={() => void (pausada ? bridge.reanudar() : bridge.pausar())}
                 atajo="Space" aria-label={pausada ? 'Reanudar' : 'Pausar'}>
            {pausada ? <Play /> : <Pause />}
          </Boton>
        )}
        <BotonVoz bridge={bridge} />
        <Boton variante={angulos ? 'primario' : 'suave'} onClick={alternarAngulos} atajo="A"
               title="Mostrar u ocultar los ángulos (A)" aria-label="Mostrar ángulos" aria-pressed={angulos}>
          <DraftingCompass /><span className="solo-ancho">Ángulos</span>
        </Boton>
        <Boton variante="suave" onClick={() => void bridge.reiniciar()} atajo="R"
               title="Reiniciar este ejercicio (R)" aria-label="Reiniciar este ejercicio">
          <RotateCcw /><span className="solo-ancho">Reiniciar</span>
        </Boton>
        <Boton variante="suave" onClick={() => void bridge.siguiente()} atajo="N"
               title="Pasar al siguiente ejercicio (N)" aria-label="Siguiente ejercicio">
          <SkipForward /><span className="solo-ancho">Siguiente</span>
        </Boton>
        <Boton variante="secundario" onClick={alTerminar} atajo="Escape"
               title="Terminar la rutina (Esc)" aria-label="Terminar la rutina">
          <Square /><span className="solo-ancho">Terminar</span>
        </Boton>
      </nav>
    </header>
  )
}

function PanelEjercicio() {
  const ejercicio = useSesion('ejercicio')
  const skillId = useSesion('ejercicioId') ?? ''
  const paso = useSesion('paso') ?? 1
  const unidad = useSesion('unidad') ?? 'repeticiones'
  const completadas = useSesion('completadas') ?? 0
  const objetivo = useSesion('objetivo') ?? 0
  const incompletas = useSesion('incompletas') ?? 0
  const correctas = useSesion('correctas')
  const conError = useSesion('conError')
  const guia = useEstado((s) => s.estado?.sesion?.guia ?? null)
  const orientacion = useEstado((s) => s.plan?.pasos[paso - 1]?.orientacion ?? null)
  const proximo = useEstado((s) => s.plan?.pasos[paso] ?? null)
  const conCorrectas = useCapacidad('correctasConError')
  const conGuia = useCapacidad('guia')

  if (!ejercicio) return <aside className="panel-ejercicio" />
  return (
    <aside className="panel-ejercicio" aria-label="Ejercicio actual">
      <div>
        <span className="etiqueta etiqueta-marca">Ahora</span>
        <h2 className="panel-nombre">{ejercicio}</h2>
        <span className="chip">{textoVista(orientacion)}</span>
      </div>

      <Progreso completadas={completadas} objetivo={objetivo} unidad={unidad} />
      <EstadoEvaluacion />

      <div className="panel-detalles">
        {incompletas > 0 && (
          <span>{unidad === 'segundos'
            ? plural(incompletas, 'interrupción', 'interrupciones')
            : plural(incompletas, 'incompleta', 'incompletas')}</span>
        )}
        {conCorrectas && correctas != null && conError != null && (
          <span><b className="texto-exito">{correctas}</b> correctas · <b className="texto-cuidado">{conError}</b> con error</span>
        )}
      </div>

      <figure className="panel-guia">
        {conGuia && guia ? <GuiaAnimada puntos={guia} ejercicioId={skillId} /> : <Figura skillId={skillId} tam={150} />}
        <figcaption>{conGuia && guia ? 'Movimiento de referencia' : 'Postura clave'}</figcaption>
      </figure>

      <Proximo paso={proximo} />
    </aside>
  )
}

/** Solo el ejercicio siguiente (una línea fija, para no cambiar el tamaño del panel). */
function Proximo({ paso }: { paso: PasoRutina | null }) {
  return (
    <div className="panel-siguientes">
      <span className="etiqueta">{paso ? 'A continuación' : 'Último ejercicio'}</span>
      {paso && (
        <p>
          <span>{paso.nombre}</span>
          <b>{paso.objetivo} {paso.unidad === 'segundos' ? 's' : 'rep.'}</b>
        </p>
      )}
    </div>
  )
}

const AYUDA_AVISO: Partial<Record<TipoAviso, string>> = {
  orientacion: 'Gira suavemente hasta que te vea como en la figura.',
  encuadre: 'Retrocede hasta que se vea de la cabeza a los pies.',
  sin_persona: 'Ponte frente a la cámara para continuar.',
}

function AvisoSesion() {
  const aviso = useSesion('aviso')
  const tipo = useSesion('avisoTipo')
  const colocando = useSesion('colocacion') != null
  if (!aviso || tipo === 'pausa' || colocando) return null   // la pausa y la colocación tienen su propia capa
  const icono = tipo === 'orientacion' ? <RotateCw />
    : tipo === 'encuadre' ? <ScanLine /> : tipo === 'sin_persona' ? <UserX /> : <Info />
  return (
    <div className="escenario-arriba">
      <Aviso tipo={tipo === 'sin_persona' ? 'cuidado' : 'info'} icono={icono} titulo={aviso}>
        {tipo ? AYUDA_AVISO[tipo] : undefined}
      </Aviso>
    </div>
  )
}

const NOMBRE_SEGMENTO: Record<string, string> = { muneca: 'muñeca' }
const LADO: Record<string, string> = { izquierdo: 'lado izquierdo', derecho: 'lado derecho' }

/** «Rodilla · lado derecho»: la parte del cuerpo que señala una corrección. */
function parteDelCuerpo(fb: Feedback): string | null {
  if (fb.tipo !== 'correccion' || !fb.segmento) return null
  const nombre = NOMBRE_SEGMENTO[fb.segmento] ?? fb.segmento
  const lado = fb.lado ? LADO[fb.lado] : undefined
  return [nombre[0].toUpperCase() + nombre.slice(1), lado].filter(Boolean).join(' · ')
}

/** La última indicación hablada, mientras suena y un poco después. */
function BandaMensaje() {
  const n = useSesion('mensajesEmitidos') ?? 0
  const texto = useSesion('ultimoMensaje')
  const feedback = useSesion('feedback')
  const paso = useSesion('paso')
  const visto = useRef(n)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    if (n === visto.current) return
    visto.current = n
    setVisible(true)
    const t = setTimeout(() => setVisible(false), MENSAJE_VISIBLE_MS)
    return () => clearTimeout(t)
  }, [n])
  // una indicación del ejercicio anterior no se queda en pantalla en el siguiente
  useEffect(() => { setVisible(false) }, [paso])
  if (!texto) return null
  const refuerzo = feedback?.tipo === 'refuerzo'
  const parte = feedback ? parteDelCuerpo(feedback) : null
  const clases = ['banda-mensaje', visible && 'visible', refuerzo && 'refuerzo',
                  feedback?.severidad && `severidad-${feedback.severidad}`].filter(Boolean).join(' ')
  return (
    <div className={clases} aria-live="polite" aria-hidden={!visible}>
      {refuerzo ? <Sparkles aria-hidden="true" /> : <Volume2 aria-hidden="true" />}
      <span className="banda-texto">
        {parte && <span className="banda-parte">{parte}</span>}
        <span>{texto}</span>
      </span>
    </div>
  )
}

/** Al empezar cada ejercicio: cuál es, cómo colocarse y el objetivo. */
function Transicion() {
  const paso = useSesion('paso') ?? 0
  const info = useEstado((s) => s.plan?.pasos[paso - 1] ?? null)
  const [visible, setVisible] = useState(true)
  useEffect(() => {
    setVisible(true)
    const t = setTimeout(() => setVisible(false), TRANSICION_VISIBLE_MS)
    return () => clearTimeout(t)
  }, [paso])
  if (!info) return null
  return (
    <div className={`transicion ${visible ? 'visible' : ''}`} aria-hidden={!visible}>
      {info.guia
        ? <GuiaAnimada puntos={info.guia} ejercicioId={info.skillId} animar={false} />
        : <Figura skillId={info.skillId} tam={120} />}
      <div>
        <span className="etiqueta etiqueta-marca">{paso === 1 ? 'Empezamos' : 'Siguiente ejercicio'}</span>
        <h3>{info.nombre}</h3>
        <p>
          <strong>{info.orientacion === 'perfil' ? 'Ponte de perfil' : info.orientacion === 'frente' ? 'Ponte de frente' : 'Colócate como prefieras'}</strong>
          {' · '}{info.objetivo} {info.unidad === 'segundos' ? 'segundos' : 'repeticiones'}
        </p>
      </div>
    </div>
  )
}

const COMPROBACIONES: [keyof Omit<ColocacionEstado, 'instruccion'>, string][] = [
  ['persona', 'Te veo'],
  ['orientacion', 'Orientación correcta'],
  ['cuerpoEntero', 'Cuerpo entero en el encuadre'],
]

/** Al empezar cada ejercicio: cómo colocarse y qué se cumple ya. Empieza solo al cumplirse todo. */
function Colocacion({ bridge }: { bridge: Bridge }) {
  const c = useEstado((s) => s.estado?.sesion?.colocacion ?? null,
    (a, b) => a?.persona === b?.persona && a?.orientacion === b?.orientacion
      && a?.cuerpoEntero === b?.cuerpoEntero && a?.instruccion === b?.instruccion)
  const paso = useSesion('paso') ?? 0
  const info = useEstado((s) => s.plan?.pasos[paso - 1] ?? null)
  if (!c || !info) return null
  return (
    <div className="capa-colocacion" role="dialog" aria-labelledby="titulo-colocacion">
      <div className="tarjeta tarjeta-colocacion">
        {info.guia
          ? <GuiaAnimada puntos={info.guia} ejercicioId={info.skillId} animar={false} />
          : <Figura skillId={info.skillId} tam={120} />}
        <div>
          <span className="etiqueta etiqueta-marca">{paso === 1 ? 'Empezamos' : 'Siguiente ejercicio'}</span>
          <h2 id="titulo-colocacion">{info.nombre}</h2>
          {c.instruccion && <p>{c.instruccion}</p>}
          <ul className="comprobaciones">
            {COMPROBACIONES.map(([clave, texto]) => (
              <li key={clave} className={c[clave] ? 'cumplida' : ''}>
                {c[clave] ? <Check aria-hidden="true" /> : <Circle aria-hidden="true" />}
                <span>{texto}</span>
                <span className="solo-lector">{c[clave] ? 'cumplido' : 'pendiente'}</span>
              </li>
            ))}
          </ul>
          <div className="acciones">
            <Boton onClick={() => void bridge.listo()}><Play />Listo, empezar</Boton>
            <span className="colocacion-nota">Empieza solo cuando todo esté en verde.</span>
          </div>
        </div>
      </div>
    </div>
  )
}

/** Si ESTELA está evaluando la técnica ahora y, si no, por qué (prueba de usabilidad). */
function EstadoEvaluacion() {
  const ev = useEstado((s) => s.estado?.sesion?.evaluacion ?? null,
    (a, b) => a?.evaluando === b?.evaluando && a?.motivo === b?.motivo)
  const [motivo, setMotivo] = useState<string | null>(null)
  useEffect(() => {
    if (ev?.motivo) { setMotivo(ev.motivo); return }
    const t = setTimeout(() => setMotivo(null), MOTIVO_VISIBLE_MS)
    return () => clearTimeout(t)
  }, [ev?.motivo])
  if (!ev) return null
  return (
    <p className={`estado-evaluacion ${motivo ? 'sin-evaluar' : 'evaluando'}`} role="status">
      <i aria-hidden="true" />
      {motivo ? <span>Sin evaluar · {motivo}</span> : <span>Evaluando tu técnica</span>}
    </p>
  )
}

function Pausa({ bridge, alTerminar }: { bridge: Bridge; alTerminar: () => void }) {
  const pausada = useSesion('pausada')
  const motivo = useSesion('motivoPausa')
  const pausaManual = useCapacidad('pausaManual')
  if (!pausada) return null
  const sinPersona = motivo === 'sin_persona'
  return (
    <div className="capa-pausa" role="alertdialog" aria-labelledby="titulo-pausa">
      <div className="tarjeta tarjeta-pausa">
        <div className="icono-pausa"><Pause /></div>
        <span className="etiqueta">Sesión en pausa</span>
        <h2 id="titulo-pausa">{sinPersona ? 'Pausa · No te veo' : 'Pausa · Cuando quieras, sigue'}</h2>
        <p>{sinPersona
          ? 'Vuelve al encuadre y seguimos donde ibas. Tus repeticiones están guardadas.'
          : 'Tu progreso está guardado. Retoma el ejercicio y seguimos contando.'}</p>
        <div className="acciones">
          {pausaManual && <Boton onClick={() => void bridge.reanudar()}><Play />Reanudar</Boton>}
          <Boton variante="secundario" onClick={alTerminar}><Square />Terminar</Boton>
        </div>
      </div>
    </div>
  )
}

function Dialogo({ alSeguir, alTerminar }: { alSeguir: () => void; alTerminar: () => void }) {
  const seguir = useRef<HTMLButtonElement>(null)
  useEffect(() => { seguir.current?.focus() }, [])
  return (
    <div className="capa-dialogo" role="dialog" aria-modal="true" aria-labelledby="titulo-confirmar">
      <div className="tarjeta tarjeta-confirmar">
        <span className="etiqueta etiqueta-cuidado">Confirmar</span>
        <h2 id="titulo-confirmar">¿Terminar la rutina?</h2>
        <p>Tu progreso hasta ahora se guarda en el resumen.</p>
        <div className="acciones">
          <button ref={seguir} className="boton boton-primario" onClick={alSeguir}>Seguir entrenando</button>
          <Boton variante="peligro" onClick={alTerminar}>Terminar</Boton>
        </div>
      </div>
    </div>
  )
}

/** Datos para el equipo (tecla D). No es parte de lo que ve la usuaria. */
function Depuracion() {
  const d = useEstado((s) => s.estado?.sesion?.depuracion ?? null,
    (a, b) => a?.fps === b?.fps && a?.latenciaMs.total === b?.latenciaMs.total && a?.latenciaMs.pose === b?.latenciaMs.pose)
  const fase = useSesion('fase')
  const orientacion = useSesion('orientacionGrados')
  const persona = useSesion('persona')
  const motivoPausa = useSesion('motivoPausa')
  const conSilencio = useCapacidad('motivoSilencio')
  const fpsUi = useFpsInterfaz()
  if (!d) return null
  const filas: [string, string][] = [
    ['FPS sesión', d.fps?.toFixed(1) ?? '—'],
    ['FPS interfaz', fpsUi > 0 ? fpsUi.toFixed(0) : '—'],
    ...Object.entries(d.latenciaMs).map(([etapa, ms]): [string, string] => [etapa, `${ms.toFixed(1)} ms`]),
    ['fase', fase || '—'],
    ['orientación', orientacion != null ? `${orientacion.toFixed(0)}°` : '—'],
    ['persona', persona ? 'sí' : 'no'],
    ['pausa', motivoPausa ?? '—'],
    ...(conSilencio ? [['silencio', d.motivoSilencio ?? '—'] as [string, string]] : []),
  ]
  return (
    <aside className="depuracion" aria-label="Depuración">
      <dl>
        {filas.map(([nombre, valor]) => <div key={nombre}><dt>{nombre}</dt><dd>{valor}</dd></div>)}
      </dl>
    </aside>
  )
}

function useFpsInterfaz(): number {
  const [fps, setFps] = useState(0)
  useEffect(() => {
    let cuadros = 0, raf = 0
    let t0 = performance.now()
    const bucle = (t: number) => {
      cuadros++
      if (t - t0 >= 1000) { setFps((cuadros * 1000) / (t - t0)); cuadros = 0; t0 = t }
      raf = requestAnimationFrame(bucle)
    }
    raf = requestAnimationFrame(bucle)
    return () => cancelAnimationFrame(raf)
  }, [])
  return fps
}
