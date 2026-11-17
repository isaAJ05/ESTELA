import { Camera, Loader2, Mic, MicOff, Monitor, Moon, ScanEye, Settings, Sun, Volume2, VolumeX, X } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import type { Bridge, Camaras, Microfonos } from '../bridge/tipos'
import { useCapacidad, useEstado } from '../estado/almacen'
import { cambiarAjustes, temaVisible, useAjustes, type TamanoTexto, type Tema } from '../estado/ajustes'
import { Boton } from './basicos'

const oscuroDelSistema = () => typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches

/** Iconos de la cabecera: cambiar entre claro y oscuro, y abrir los ajustes. */
export function ControlesCabecera({ bridge }: { bridge: Bridge }) {
  const [abierto, setAbierto] = useState(false)
  return (
    <div className="controles-cabecera">
      <BotonTema />
      <button className="boton-icono" onClick={() => setAbierto(true)} title="Ajustes" aria-label="Ajustes"
              aria-haspopup="dialog">
        <Settings />
      </button>
      {abierto && <PanelAjustes bridge={bridge} alCerrar={() => setAbierto(false)} />}
    </div>
  )
}

function BotonTema() {
  const { tema } = useAjustes()
  const visible = temaVisible(tema, oscuroDelSistema())
  const destino = visible === 'oscuro' ? 'claro' : 'oscuro'
  return (
    <button className="boton-icono" onClick={() => cambiarAjustes({ tema: destino })}
            title={`Cambiar a modo ${destino}`} aria-label={`Cambiar a modo ${destino}`}>
      {visible === 'oscuro' ? <Sun /> : <Moon />}
    </button>
  )
}

/** Silenciar o activar la voz durante la sesión (tecla V). */
export function BotonVoz({ bridge }: { bridge: Bridge }) {
  const { voz } = useAjustes()
  if (!useCapacidad('silenciarVoz')) return null
  return (
    <Boton variante={voz ? 'suave' : 'secundario'} onClick={() => cambiarAjustes({ voz: !voz }, bridge)} atajo="V"
           title={voz ? 'Silenciar la voz (V)' : 'Activar la voz (V)'} aria-label="Indicaciones habladas" aria-pressed={voz}>
      {voz ? <Volume2 /> : <VolumeX />}
    </Boton>
  )
}

/** Activar o desactivar el aviso «ese movimiento no es el de ahora» (EXP-010).
 *  Empieza desactivado: el reconocimiento aún puede saltar con el ejercicio correcto. */
export function BotonReconocer({ bridge }: { bridge: Bridge }) {
  const { reconocer } = useAjustes()
  if (!useCapacidad('reconocerEjercicio')) return null
  return (
    <Boton variante={reconocer ? 'primario' : 'suave'} onClick={() => cambiarAjustes({ reconocer: !reconocer }, bridge)}
           title={reconocer ? 'Dejar de avisar si haces otro ejercicio' : 'Avisar si haces otro ejercicio (en pruebas)'}
           aria-label="Reconocer el ejercicio" aria-pressed={reconocer}>
      <ScanEye /><span className="solo-ancho">Reconocer</span>
    </Boton>
  )
}

function PanelAjustes({ bridge, alCerrar }: { bridge: Bridge; alCerrar: () => void }) {
  const ajustes = useAjustes()
  const conVoz = useCapacidad('silenciarVoz')

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') alCerrar() }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [alCerrar])

  return (
    <div className="capa-dialogo" onClick={(e) => { if (e.target === e.currentTarget) alCerrar() }}>
      <section className="tarjeta panel-ajustes" role="dialog" aria-modal="true" aria-labelledby="titulo-ajustes">
        <header className="panel-ajustes-cabeza">
          <h2 id="titulo-ajustes">Ajustes</h2>
          <button className="boton-icono" onClick={alCerrar} aria-label="Cerrar" autoFocus><X /></button>
        </header>

        <Opcion titulo="Apariencia" ayuda="«Automático» sigue el modo del sistema.">
          <Segmentos<Tema> valor={ajustes.tema} alCambiar={(tema) => cambiarAjustes({ tema })} etiqueta="Apariencia"
            opciones={[['oscuro', <><Moon />Oscuro</>], ['claro', <><Sun />Claro</>], ['sistema', <><Monitor />Automático</>]]} />
        </Opcion>

        {conVoz && (
          <Opcion titulo="Indicaciones habladas"
                  ayuda={ajustes.voz ? 'Te digo en voz alta cómo mejorar tu técnica.'
                    : 'Sin voz: las indicaciones solo aparecen en pantalla.'}>
            <button className={`interruptor${ajustes.voz ? ' activo' : ''}`} role="switch" aria-checked={ajustes.voz}
                    aria-label="Indicaciones habladas" onClick={() => cambiarAjustes({ voz: !ajustes.voz }, bridge)}>
              <span />
            </button>
          </Opcion>
        )}

        <OpcionCamara bridge={bridge} />

        <OpcionMicrofono bridge={bridge} />

        <Opcion titulo="Tamaño del texto" ayuda="Útil si miras la pantalla desde lejos.">
          <Segmentos<TamanoTexto> valor={ajustes.texto} alCambiar={(texto) => cambiarAjustes({ texto })} etiqueta="Tamaño del texto"
            opciones={[['normal', 'Normal'], ['grande', 'Grande'], ['muy-grande', 'Muy grande']]} />
        </Opcion>
      </section>
    </div>
  )
}

/** Elegir la cámara de la próxima sesión (capacidad «elegirCamara»). Python la
 *  recuerda hasta cerrar la aplicación; aquí no se guarda. */
function OpcionCamara({ bridge }: { bridge: Bridge }) {
  const capacidad = useCapacidad('elegirCamara')
  const fuente = useEstado((s) => s.info?.fuente ?? 'camara')
  const conCamara = capacidad && fuente === 'camara'
  const [camaras, setCamaras] = useState<Camaras | null | undefined>(undefined)   // undefined: buscando
  useEffect(() => {
    if (!conCamara) return
    let vigente = true
    bridge.camaras().then((c) => { if (vigente) setCamaras(c) }, () => { if (vigente) setCamaras(null) })
    return () => { vigente = false }
  }, [bridge, conCamara])
  if (!conCamara || camaras === null) return null

  const elegir = (indice: number) => {
    setCamaras((c) => c && { ...c, elegida: indice })
    void bridge.configurar({ camara: indice })
  }
  const lista = camaras?.lista ?? []
  const elegida = camaras?.elegida ?? lista[0]?.indice
  return (
    <Opcion titulo="Cámara"
            ayuda={camaras === undefined ? 'Buscando cámaras…'
              : lista.length === 0 ? 'No encuentro ninguna cámara. Comprueba que esté conectada.'
              : lista.length === 1 ? 'Es la única cámara que encuentro.'
              : 'Se usa desde la próxima sesión.'}>
      {camaras === undefined ? <Loader2 className="girando" aria-label="Buscando cámaras" />
        : lista.length === 1 ? <span className="camara-unica"><Camera />{lista[0].nombre}</span>
        : lista.length > 1 && (
          <Segmentos<string> valor={String(elegida)} alCambiar={(v) => elegir(Number(v))} etiqueta="Cámara"
            opciones={lista.map((c) => [String(c.indice), <><Camera />{c.nombre}</>])} />
        )}
    </Opcion>
  )
}

/** Cómo se llama en pantalla cada orden que la prueba del micrófono puede entender. */
const ORDEN_PROBADA: Record<string, string> = {
  pausa: 'Pausa', seguir: 'Seguir', siguiente: 'Siguiente', anterior: 'Anterior', terminar: 'Terminar',
  como_voy: '¿Cómo voy?', reiniciar_ejercicio: 'Reiniciar ejercicio', reiniciar_sesion: 'Reiniciar sesión',
  reconocer_si: 'Reconocer activado', reconocer_no: 'Reconocer desactivado',
  angulos_si: 'Ángulos activados', angulos_no: 'Ángulos desactivados',
  repite_eso: 'Repite eso', voz_si: 'Voz activada', voz_no: 'Silencio',
}

/** Micrófono de las órdenes de voz (capacidad «vozEntrada»): encenderlo o apagarlo,
 *  elegir la entrada y probar que te oye. Python lo recuerda hasta cerrar la
 *  aplicación; aquí no se guarda. Mientras el panel está abierto se consulta el
 *  nivel de entrada varias veces por segundo. */
function OpcionMicrofono({ bridge }: { bridge: Bridge }) {
  const capacidad = useCapacidad('vozEntrada')
  const [m, setM] = useState<Microfonos | null | undefined>(undefined)   // undefined: consultando
  useEffect(() => {
    if (!capacidad) return
    let vigente = true
    const leer = () => bridge.microfono().then((x) => { if (vigente) setM(x) }, () => { if (vigente) setM(null) })
    void leer()
    const id = window.setInterval(leer, 300)
    return () => { vigente = false; window.clearInterval(id) }
  }, [bridge, capacidad])
  if (!capacidad || m === null) return null

  const encendido = m?.encendido ?? false
  const encender = (si: boolean) => {
    setM((x) => x && { ...x, encendido: si })
    void bridge.configurar({ vozEntrada: si })
  }
  const elegir = (valor: string) => {
    const indice = valor === '' ? null : Number(valor)
    setM((x) => x && { ...x, elegido: indice })
    void bridge.configurar({ microfono: indice })
  }
  const prueba = m?.prueba ?? null
  const orden = prueba?.comando ? ORDEN_PROBADA[prueba.comando] ?? prueba.comando : null
  return (
    <>
      <Opcion titulo="Micrófono"
              ayuda={m === undefined ? 'Consultando el micrófono…'
                : m.error ? `No pude abrir el micrófono (${m.error}). Comprueba que esté conectado y vuelve a encenderlo.`
                : !encendido ? 'Apagado: no te escucho y las órdenes de voz no funcionan.'
                : m.llamada ? 'Di «Estela» y una orden, también durante el ejercicio. El audio no se guarda.'
                : 'Te escucho en pausa y entre ejercicios. El audio no se guarda.'}>
        {m === undefined ? <Loader2 className="girando" aria-label="Consultando el micrófono" />
          : (
            <button className={`interruptor${encendido ? ' activo' : ''}`} role="switch" aria-checked={encendido}
                    aria-label="Micrófono" onClick={() => encender(!encendido)}>
              <span />
            </button>
          )}
      </Opcion>
      {m && encendido && (
        <div className="microfono-detalle">
          <label className="microfono-entrada">
            <Mic aria-hidden="true" />
            <select value={m.elegido === null ? '' : String(m.elegido)} onChange={(e) => elegir(e.target.value)}
                    aria-label="Entrada de audio">
              <option value="">Por defecto del sistema{m.elegido === null && m.nombre ? ` (${m.nombre})` : ''}</option>
              {m.lista.map((e) => <option key={e.indice} value={String(e.indice)}>{e.nombre}</option>)}
            </select>
          </label>
          <div className="nivel-entrada" role="meter" aria-label="Nivel de entrada" aria-valuemin={0}
               aria-valuemax={100} aria-valuenow={Math.round(Math.min(1, m.nivel * 6) * 100)}>
            <i style={{ width: `${Math.round(Math.min(1, m.nivel * 6) * 100)}%` }} />
          </div>
          <div className="microfono-prueba">
            <Boton variante="suave" onClick={() => void bridge.probarMicrofono()} disabled={m.probando}>
              {m.probando ? <><Loader2 className="girando" />Escuchando…</> : <>Probar</>}
            </Boton>
            <span role="status" aria-live="polite">
              {prueba ? <>Oí «{prueba.texto || '…'}»{' → '}
                {prueba.llamada === false ? 'sin «Estela»: no haría caso'
                  : orden ? <b>{orden}</b> : 'no es una orden'}</>
                : m.probando ? (m.llamada ? 'Di, por ejemplo, «Estela, pausa».' : 'Di, por ejemplo, «pausa».')
                : 'Habla y mira si la barra se mueve; «Probar» muestra lo que entiendo.'}
            </span>
          </div>
        </div>
      )}
      {m && !encendido && !m.error && (
        <div className="microfono-detalle microfono-apagado"><MicOff aria-hidden="true" />El micrófono está cerrado.</div>
      )}
    </>
  )
}

function Opcion({ titulo, ayuda, children }: { titulo: string; ayuda: string; children: ReactNode }) {
  return (
    <div className="opcion-ajuste">
      <div>
        <strong>{titulo}</strong>
        <span>{ayuda}</span>
      </div>
      {children}
    </div>
  )
}

function Segmentos<T extends string>({ valor, opciones, alCambiar, etiqueta }: {
  valor: T; opciones: [T, ReactNode][]; alCambiar: (v: T) => void; etiqueta: string
}) {
  return (
    <div className="selector-nivel segmentos" role="radiogroup" aria-label={etiqueta}>
      {opciones.map(([v, contenido]) => (
        <button key={v} role="radio" aria-checked={valor === v}
                className={valor === v ? 'activo' : undefined} onClick={() => alCambiar(v)}>
          {contenido}
        </button>
      ))}
    </div>
  )
}
