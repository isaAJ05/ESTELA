import { AlertTriangle, Check, ChevronDown, Home, LogOut, MessageCircle, RotateCcw, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { Bridge, PasoResumen, PasoRutina, Resumen as DatosResumen } from '../bridge/tipos'
import { Aviso, Boton, Marca, duracion, plural } from '../componentes/basicos'
import { Figura } from '../componentes/Figura'
import { useCapacidad, useEstado } from '../estado/almacen'

export function Resumen({ bridge }: { bridge: Bridge }) {
  const resumen = useEstado((s) => s.estado?.resumen ?? null)
  const plan = useEstado((s) => s.info?.rutina.pasos ?? [])
  const fuente = useEstado((s) => s.info?.fuente ?? 'camara')
  const conTexto = useCapacidad('resumenTexto')
  const [tecnico, setTecnico] = useState(false)
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => { if (e.key.toLowerCase() === 'd' && !e.repeat) setTecnico((t) => !t) }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [])
  if (!resumen) return null

  const completos = resumen.pasos.filter((p) => p.completadas >= p.objetivo).length
  // los pasos a los que no se llegó (si se terminó antes) se listan aparte
  const pendientes = plan.slice(resumen.pasos.length)

  return (
    <main className="pantalla pantalla-resumen">
      <header className="cabecera">
        <Marca />
        <span className="etiqueta">Resumen de la sesión</span>
      </header>

      <section className="resumen-cuerpo">
        <div className="resumen-cabeza">
          <span className="etiqueta etiqueta-marca">{resumen.rutina}</span>
          <h1>{resumen.terminada ? <>Muy bien,<br /><em>hoy te moviste.</em></> : <>Hasta aquí<br /><em>por hoy.</em></>}</h1>
          <p className="resumen-cifras">
            <span><strong>{duracion(resumen.duracionTotalS)}</strong> en movimiento</span>
            <span><strong>{completos}</strong> de {plan.length || resumen.pasos.length} ejercicios completos</span>
          </p>
          {resumen.motivoFin === 'fuente' && fuente === 'camara' && (
            <Aviso tipo="cuidado" icono={<AlertTriangle />} titulo="La cámara dejó de enviar imagen">
              Guardamos lo que llevabas. Revisa la conexión antes de repetir.
            </Aviso>
          )}
          {resumen.motivoFin === 'error' && (
            <Aviso tipo="cuidado" icono={<AlertTriangle />} titulo="La sesión se detuvo por un problema">
              Guardamos lo que llevabas. Puedes repetir la rutina.
            </Aviso>
          )}
          {conTexto && resumen.resumenTexto && (
            <p className="resumen-texto"><Sparkles aria-hidden="true" />{resumen.resumenTexto}</p>
          )}
          <div className="acciones">
            <Boton onClick={() => void bridge.iniciar()}><RotateCcw />Repetir rutina</Boton>
            <Boton variante="secundario" onClick={() => void bridge.volverAlInicio()}><Home />Inicio</Boton>
            <Boton variante="suave" onClick={() => void bridge.salir()}><LogOut />Salir</Boton>
          </div>
        </div>

        {tecnico ? <PanelTecnico resumen={resumen} /> : (
          <ol className="tarjeta lista-resumen">
            {resumen.pasos.map((p, i) => <FilaResumen key={`${p.skillId}-${i}`} paso={p} />)}
            {pendientes.map((p, i) => <FilaPendiente key={`p-${p.skillId}-${i}`} paso={p} />)}
          </ol>
        )}
      </section>
    </main>
  )
}

function agrupar(paso: PasoResumen): [string, number][] {
  const veces = new Map<string, number>()
  for (const m of paso.mensajes) if (m.errorId) veces.set(m.texto, (veces.get(m.texto) ?? 0) + 1)
  return [...veces.entries()].sort((a, b) => b[1] - a[1])
}

function FilaResumen({ paso }: { paso: PasoResumen }) {
  const conCorrectas = useCapacidad('correctasConError')
  const correcciones = agrupar(paso)
  const [abierta, setAbierta] = useState(false)
  const completo = paso.completadas >= paso.objetivo
  const segundos = paso.unidad === 'segundos'
  const saltado = paso.completadas === 0 && paso.duracionS < 1
  const detalles = [
    saltado ? 'Saltado' : duracion(paso.duracionS),
    paso.incompletas > 0 && (segundos
      ? plural(paso.incompletas, 'interrupción', 'interrupciones')
      : plural(paso.incompletas, 'incompleta', 'incompletas')),
    paso.pausas > 0 && `${plural(paso.pausas, 'pausa', 'pausas')} (${duracion(paso.pausaS)})`,
  ].filter(Boolean)

  return (
    <li className={`fila-resumen ${abierta ? 'abierta' : ''}`}>
      <button className="fila-resumen-cabeza" onClick={() => setAbierta(!abierta)}
              aria-expanded={abierta} disabled={correcciones.length === 0}>
        <span className="paso-figura"><Figura skillId={paso.skillId} tam={44} resaltar={false} /></span>
        <span className="fila-resumen-nombre">
          <strong>{paso.nombre}</strong>
          <span>{detalles.join(' · ')}</span>
        </span>
        <span className="fila-resumen-cifras">
          <strong className={completo ? 'texto-exito' : undefined}>
            {paso.completadas} / {paso.objetivo}{segundos ? ' s' : ''}
          </strong>
          {conCorrectas && paso.correctas != null && paso.conError != null
            ? <span>{paso.correctas} correctas · {paso.conError} con error</span>
            : <span>{segundos ? 'en posición' : 'repeticiones'}</span>}
        </span>
        <span className="fila-resumen-icono" aria-hidden="true">
          {correcciones.length > 0
            ? <><MessageCircle /><b>{correcciones.reduce((a, [, n]) => a + n, 0)}</b><ChevronDown className="flecha" /></>
            : completo ? <Check className="texto-exito" /> : null}
        </span>
      </button>
      {abierta && (
        <div className="correcciones">
          <strong>Indicaciones que recibiste</strong>
          <ul>
            {correcciones.map(([texto, n]) => <li key={texto}>{texto} {n > 1 && <b>×{n}</b>}</li>)}
          </ul>
        </div>
      )}
    </li>
  )
}

function FilaPendiente({ paso }: { paso: PasoRutina }) {
  return (
    <li className="fila-resumen pendiente">
      <div className="fila-resumen-cabeza">
        <span className="paso-figura"><Figura skillId={paso.skillId} tam={44} resaltar={false} /></span>
        <span className="fila-resumen-nombre">
          <strong>{paso.nombre}</strong>
          <span>Sin empezar</span>
        </span>
        <span className="fila-resumen-cifras">
          <strong>— / {paso.objetivo}{paso.unidad === 'segundos' ? ' s' : ''}</strong>
        </span>
        <span className="fila-resumen-icono" />
      </div>
    </li>
  )
}

/** Métricas para el equipo (tecla D): abstenciones del motor y latencia por etapa. */
function PanelTecnico({ resumen }: { resumen: DatosResumen }) {
  const t = resumen.tecnico
  return (
    <section className="tarjeta panel-tecnico" aria-label="Datos técnicos de la sesión">
      <span className="etiqueta">Datos técnicos · tecla D para volver</span>
      <p>{t.frames} frames · {t.framesSinPersona} sin persona · fin: {resumen.motivoFin ?? '—'}</p>
      <table>
        <thead><tr><th>Etapa</th><th>p50</th><th>p95</th><th>n</th></tr></thead>
        <tbody>
          {Object.entries(t.latencias).map(([etapa, v]) => (
            <tr key={etapa}><td>{etapa}</td><td>{v.p50Ms.toFixed(1)} ms</td><td>{v.p95Ms.toFixed(1)} ms</td><td>{v.n}</td></tr>
          ))}
        </tbody>
      </table>
      <table>
        <thead><tr><th>Ejercicio</th><th>Completadas</th><th>Correcciones</th><th>Abstenciones</th></tr></thead>
        <tbody>
          {resumen.pasos.map((p, i) => (
            <tr key={`${p.skillId}-${i}`}>
              <td>{p.skillId}</td>
              <td>{p.completadas} / {p.objetivo}</td>
              <td>{p.mensajes.filter((m) => m.errorId).length}</td>
              <td>{Object.entries(p.abstenciones).map(([motivo, n]) => `${motivo} ×${n}`).join(', ') || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
