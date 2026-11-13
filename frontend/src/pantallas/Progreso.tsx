import { AlertTriangle, ArrowLeft, ArrowRight, CalendarDays, Check, ChevronDown, Clock, Flame, History, Loader2, Lock, RotateCcw, Target, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import type { Bridge, EjercicioProgreso, Progreso, SemanaProgreso, SesionHistorial } from '../bridge/tipos'
import { Aviso, Boton, duracion, plural } from '../componentes/basicos'
import { FiguraEjercicio } from '../componentes/rutina'
import { useEstado } from '../estado/almacen'
import {
  duracionLarga, fechaCorta, fechaHora, fechaRelativa, marcasEje, minutos, textoFrecuencia, textoMarca, textoRacha,
} from '../estado/progreso'

type Carga = { estado: 'cargando' } | { estado: 'error' } | { estado: 'listo'; datos: Progreso }

/**
 * Panel «Mi progreso» (ADR-008): constancia, tiempo en movimiento, marcas por
 * ejercicio e indicaciones que más se repiten. Todo lo calcula Python con el
 * historial guardado en este equipo; la interfaz solo lo muestra.
 */
export function PanelProgreso({ bridge, alVolver }: { bridge: Bridge; alVolver: () => void }) {
  const [carga, setCarga] = useState<Carga>({ estado: 'cargando' })
  const cargar = useCallback(async () => {
    try {
      const datos = await bridge.historial()
      setCarga(datos ? { estado: 'listo', datos } : { estado: 'error' })
    } catch (err) {
      console.error('historial()', err)
      setCarga({ estado: 'error' })
    }
  }, [bridge])
  useEffect(() => { void cargar() }, [cargar])

  const datos = carga.estado === 'listo' ? carga.datos : null
  const vacio = datos?.totalSesiones === 0

  return (
    <section className="progreso-cuerpo">
      <div className="progreso-cabeza">
        <button className="enlace-volver" onClick={alVolver}><ArrowLeft />Volver al inicio</button>
        <span className="etiqueta etiqueta-marca">Mi progreso</span>
        <h1>Tu constancia,<br /><em>sesión a sesión.</em></h1>
        <p className="progreso-privacidad">
          <Lock aria-hidden="true" />
          Tu historial se guarda solo en este equipo y no se envía a ningún sitio. No se guardan imágenes ni tu postura,
          solo lo que hiciste y las indicaciones que recibiste.
        </p>
      </div>

      {carga.estado === 'cargando' && <p className="progreso-cargando"><Loader2 className="girando" />Cargando tu historial…</p>}
      {carga.estado === 'error' && (
        <Aviso tipo="cuidado" icono={<AlertTriangle />} titulo="No se pudo leer tu historial"
               accion={<Boton variante="secundario" onClick={() => void cargar()}><RotateCcw />Reintentar</Boton>} />
      )}
      {vacio && (
        <article className="tarjeta progreso-vacio">
          <History aria-hidden="true" />
          <h2>Aún no hay sesiones guardadas</h2>
          <p>Cuando termines tu primera rutina, aquí verás tus días activos, tu tiempo en movimiento y tus marcas.</p>
        </article>
      )}

      {datos && !vacio && (
        <>
          <Cifras datos={datos} />
          <article className="tarjeta progreso-semanas">
            <h2>Minutos en movimiento por semana</h2>
            <p className="progreso-sub">Últimas {datos.semanas.length} semanas, de lunes a domingo</p>
            <GraficoSemanas semanas={datos.semanas} />
          </article>
          <div className="progreso-ejercicios">
            <h2>Por ejercicio</h2>
            <div className="rejilla-progreso">
              {datos.ejercicios.map((e) => <TarjetaEjercicioProgreso key={e.skillId} e={e} />)}
            </div>
          </div>
          <HistorialSesiones sesiones={datos.sesiones} />
          <p className="descargo">
            Estas cifras muestran tu constancia y las indicaciones que recibiste. No miden tu técnica con precisión
            ni son una evaluación de salud: ESTELA no da una indicación cada vez que ve algo, y a veces no puede ver bien.
          </p>
          <BorrarHistorial bridge={bridge} alBorrar={() => void cargar()} />
        </>
      )}
    </section>
  )
}

/**
 * Tarjeta corta del inicio: meta de la semana y racha del perfil, con acceso a
 * «Mi progreso». Si el historial no se puede leer no muestra nada: el inicio
 * no debe quedar bloqueado por esto.
 */
export function ResumenSemana({ bridge, alVer }: { bridge: Bridge; alVer: () => void }) {
  const [datos, setDatos] = useState<Progreso | null>(null)
  useEffect(() => {
    let vigente = true
    bridge.historial().then((d) => { if (vigente) setDatos(d) }).catch((err) => console.error('historial()', err))
    return () => { vigente = false }
  }, [bridge])
  if (!datos || (datos.totalSesiones === 0 && datos.metaSemanal == null)) return null

  const meta = datos.metaSemanal
  const dias = datos.diasSemanaActual
  const racha = textoRacha(datos.rachaDias)
  return (
    <article className="tarjeta resumen-semana">
      <div className="resumen-semana-datos">
        {meta != null ? (
          <div>
            <span className="cifra-etiqueta"><Target />Meta de esta semana</span>
            <strong>{dias} de {plural(meta, 'día', 'días')}{dias >= meta && <Check className="texto-exito" aria-label="cumplida" />}</strong>
            <span className="medidor" role="meter" aria-valuemin={0} aria-valuemax={meta} aria-valuenow={Math.min(dias, meta)}
                  aria-label={`${dias} de ${meta} días esta semana`}>
              <i style={{ width: `${Math.min(1, dias / meta) * 100}%` }} />
            </span>
          </div>
        ) : (
          <div>
            <span className="cifra-etiqueta"><CalendarDays />Días activos</span>
            <strong>{datos.diasActivos7} de 7</strong>
          </div>
        )}
        <div>
          <span className="cifra-etiqueta"><Flame />Racha</span>
          <strong>{racha.valor}</strong>
        </div>
      </div>
      <button className="enlace-editar" onClick={alVer}>Ver mi progreso<ArrowRight /></button>
    </article>
  )
}

function Cifras({ datos }: { datos: Progreso }) {
  const racha = textoRacha(datos.rachaDias)
  return (
    <div className="progreso-cifras">
      {datos.metaSemanal != null
        ? <CifraMeta dias={datos.diasSemanaActual} meta={datos.metaSemanal} />
        : <Cifra icono={<CalendarDays />} etiqueta="Días activos" valor={`${datos.diasActivos7} de 7`} extra="en los últimos 7 días" />}
      <Cifra icono={<Flame />} etiqueta="Racha" valor={racha.valor} extra={racha.extra} />
      <Cifra icono={<Clock />} etiqueta="Tiempo en movimiento" valor={duracionLarga(datos.totalDuracionS)}
             extra={`en ${plural(datos.totalSesiones, 'sesión', 'sesiones')}`} />
      <Cifra icono={<History />} etiqueta="Desde" valor={datos.primeraFecha ? fechaCorta(datos.primeraFecha) : '—'}
             extra={plural(datos.diasActivos, 'día activo', 'días activos')} />
    </div>
  )
}

/** Meta semanal del perfil (ADR-009): días con sesión de lunes a hoy frente a la meta. */
function CifraMeta({ dias, meta }: { dias: number; meta: number }) {
  const cumplida = dias >= meta
  return (
    <div className="tarjeta cifra">
      <span className="cifra-etiqueta"><Target />Meta de esta semana</span>
      <strong>{dias} de {plural(meta, 'día', 'días')}</strong>
      <span className="medidor" role="meter" aria-valuemin={0} aria-valuemax={meta} aria-valuenow={Math.min(dias, meta)}
            aria-label={`${dias} de ${meta} días esta semana`}>
        <i style={{ width: `${Math.min(1, dias / meta) * 100}%` }} />
      </span>
      <span className="cifra-extra">
        {cumplida ? <><Check className="texto-exito" aria-hidden="true" /> ¡Meta cumplida!</> : `Te ${meta - dias === 1 ? 'falta 1 día' : `faltan ${meta - dias} días`} · de lunes a domingo`}
      </span>
    </div>
  )
}

function Cifra({ icono, etiqueta, valor, extra }: { icono: ReactNode; etiqueta: string; valor: string; extra?: string }) {
  return (
    <div className="tarjeta cifra">
      <span className="cifra-etiqueta">{icono}{etiqueta}</span>
      <strong>{valor}</strong>
      {extra && <span className="cifra-extra">{extra}</span>}
    </div>
  )
}

// -- gráfico de semanas ---------------------------------------------------------

const ALTO = 200
const MARGEN = { arriba: 22, derecha: 8, abajo: 26, izquierda: 34 }

/** Columnas de una sola serie: minutos por semana. Pasar el ratón o el foco por
 *  una semana muestra sus sesiones y su tiempo; la tabla da los mismos datos. */
function GraficoSemanas({ semanas }: { semanas: SemanaProgreso[] }) {
  const caja = useRef<HTMLDivElement>(null)
  const [ancho, setAncho] = useState(560)
  const [activa, setActiva] = useState<number | null>(null)
  useEffect(() => {
    const el = caja.current
    if (!el) return
    const obs = new ResizeObserver(([e]) => setAncho(Math.max(280, e.contentRect.width)))
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const valores = semanas.map((s) => minutos(s.duracionS))
  const marcas = marcasEje(Math.max(...valores, 0))
  const tope = marcas.at(-1)!
  const altoUtil = ALTO - MARGEN.arriba - MARGEN.abajo
  const banda = (ancho - MARGEN.izquierda - MARGEN.derecha) / semanas.length
  const grosor = Math.min(24, banda * 0.5)
  const y = (v: number) => MARGEN.arriba + altoUtil * (1 - v / tope)
  const base = y(0)
  const x = (i: number) => MARGEN.izquierda + banda * i + banda / 2
  const ultima = semanas.length - 1

  return (
    <div className="grafico-semanas" ref={caja}>
      <svg width={ancho} height={ALTO} role="img"
           aria-label={`Minutos en movimiento por semana. Esta semana: ${valores[ultima]} minutos.`}>
        {marcas.map((m) => (
          <g key={m}>
            <line className={m === 0 ? 'eje-base' : 'eje-rejilla'} x1={MARGEN.izquierda} x2={ancho - MARGEN.derecha} y1={y(m)} y2={y(m)} />
            <text className="eje-texto" x={MARGEN.izquierda - 8} y={y(m)} dy="0.32em" textAnchor="end">{m}</text>
          </g>
        ))}
        {semanas.map((s, i) => {
          const v = valores[i]
          const alto = base - y(v)
          const r = Math.min(4, alto, grosor / 2)
          const x0 = x(i) - grosor / 2
          // esquinas redondeadas arriba, rectas en la línea base
          const d = alto <= 0 ? '' : `M${x0},${base} V${base - alto + r} Q${x0},${base - alto} ${x0 + r},${base - alto}
            H${x0 + grosor - r} Q${x0 + grosor},${base - alto} ${x0 + grosor},${base - alto + r} V${base} Z`
          return (
            <g key={s.inicio} className={`columna ${activa === i ? 'activa' : ''} ${i === ultima ? 'actual' : ''}`}
               tabIndex={0} role="img"
               aria-label={`Semana del ${fechaCorta(s.inicio)}: ${plural(s.sesiones, 'sesión', 'sesiones')}, ${duracionLarga(s.duracionS)}`}
               onMouseEnter={() => setActiva(i)} onMouseLeave={() => setActiva(null)}
               onFocus={() => setActiva(i)} onBlur={() => setActiva(null)}>
              {/* zona sensible más grande que la columna */}
              <rect className="columna-zona" x={x(i) - banda / 2} y={MARGEN.arriba} width={banda} height={altoUtil} />
              {d && <path d={d} />}
              {i === ultima && v > 0 && <text className="columna-valor" x={x(i)} y={base - alto - 6} textAnchor="middle">{v}</text>}
              <text className="eje-texto" x={x(i)} y={ALTO - 8} textAnchor="middle">{i === ultima ? 'Esta' : fechaCorta(s.inicio)}</text>
            </g>
          )
        })}
      </svg>
      {activa !== null && (
        <div className="grafico-tooltip" role="status"
             style={{ left: Math.min(Math.max(x(activa), 80), ancho - 80), top: Math.max(0, y(valores[activa]) - 64) }}>
          <strong>{activa === ultima ? 'Esta semana' : `Semana del ${fechaCorta(semanas[activa].inicio)}`}</strong>
          <span>{plural(semanas[activa].sesiones, 'sesión', 'sesiones')} · {duracionLarga(semanas[activa].duracionS)}</span>
        </div>
      )}
      <details className="grafico-tabla">
        <summary>Ver como tabla</summary>
        <table>
          <thead><tr><th>Semana del</th><th>Sesiones</th><th>Tiempo</th></tr></thead>
          <tbody>
            {semanas.map((s) => (
              <tr key={s.inicio}><td>{fechaCorta(s.inicio)}</td><td>{s.sesiones}</td><td>{duracionLarga(s.duracionS)}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}

// -- por ejercicio --------------------------------------------------------------

function TarjetaEjercicioProgreso({ e }: { e: EjercicioProgreso }) {
  const { sesiones, frecuentes } = e.indicaciones
  // la postura de la referencia viene en el catálogo; un ejercicio retirado
  // (ya no está en él) se queda con la figura dibujada
  const guia = useEstado((s) => s.info?.catalogo?.find((c) => c.skillId === e.skillId)?.guia ?? null)
  return (
    <article className="tarjeta tarjeta-progreso">
      <header>
        <span className="paso-figura"><FiguraEjercicio paso={{ skillId: e.skillId, guia }} /></span>
        <div>
          <strong>{e.nombre}</strong>
          <span>{plural(e.veces, 'vez', 'veces')} · última {fechaRelativa(e.ultimaFecha)}</span>
        </div>
      </header>
      <dl className="progreso-marcas">
        <div><dt>Última</dt><dd>{textoMarca(e.ultimo.completadas, e.ultimo.objetivo, e.unidad)}</dd></div>
        <div><dt>Mejor</dt><dd>{e.mejor}{e.unidad === 'segundos' ? ' s' : ''}</dd></div>
        <div><dt>Objetivo alcanzado</dt><dd>{e.objetivoCumplido} de {e.veces}</dd></div>
      </dl>
      <Recientes e={e} />
      <div className="progreso-indicaciones">
        <span className="etiqueta">Indicaciones que más recibiste</span>
        {frecuentes.length === 0 ? (
          <p>No recibiste correcciones {sesiones === 1 ? 'en tu única sesión' : `en tus últimas ${sesiones} sesiones`}.</p>
        ) : (
          <ul>
            {frecuentes.map((f) => (
              <li key={f.errorId}>
                <q>{f.texto}</q>
                <span>{textoFrecuencia(f.sesiones, sesiones)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </article>
  )
}

/** Lo completado en las últimas sesiones del ejercicio (la última en acento). */
function Recientes({ e }: { e: EjercicioProgreso }) {
  if (e.recientes.length < 2) return null
  const tope = Math.max(...e.recientes.map((r) => Math.max(r.completadas, r.objetivo)), 1)
  const ultima = e.recientes.length - 1
  return (
    <div className="recientes" role="img"
         aria-label={`Últimas ${e.recientes.length} veces: ${e.recientes.map((r) => textoMarca(r.completadas, r.objetivo, e.unidad)).join(', ')}`}>
      {e.recientes.map((r, i) => (
        <i key={r.fecha} className={i === ultima ? 'actual' : undefined}
           style={{ height: `${Math.max(6, (r.completadas / tope) * 100)}%` }}
           title={`${fechaCorta(r.fecha)}: ${textoMarca(r.completadas, r.objetivo, e.unidad)}`} />
      ))}
    </div>
  )
}

// -- historial --------------------------------------------------------------------

/** Sesiones mostradas antes de «Ver todas»: con todo el historial la página se hacía muy larga. */
const SESIONES_VISIBLES = 5

function HistorialSesiones({ sesiones }: { sesiones: SesionHistorial[] }) {
  const [todas, setTodas] = useState(false)
  const visibles = todas ? sesiones : sesiones.slice(0, SESIONES_VISIBLES)
  const ocultas = sesiones.length - SESIONES_VISIBLES
  return (
    <article className="tarjeta progreso-historial">
      <h2>Sesiones recientes</h2>
      <ol>{visibles.map((s) => <FilaSesion key={s.fecha} s={s} />)}</ol>
      {ocultas > 0 && (
        <button className="enlace-editar" aria-expanded={todas} onClick={() => setTodas(!todas)}>
          {todas ? 'Ver menos' : `Ver las ${sesiones.length} sesiones`}
          <ChevronDown className={todas ? 'girada' : undefined} aria-hidden="true" />
        </button>
      )}
    </article>
  )
}

function FilaSesion({ s }: { s: SesionHistorial }) {
  return (
    <li>
      <details className="fila-sesion">
        <summary>
          <span className="fila-sesion-fecha">{fechaHora(s.fecha)}</span>
          <span className="fila-sesion-rutina">{s.rutina}</span>
          <span>{duracion(s.duracionS)}</span>
          <span>{s.completos} de {plural(s.ejercicios, 'ejercicio', 'ejercicios')} completos</span>
          <ChevronDown className="flecha" aria-hidden="true" />
        </summary>
        <ul>
          {s.pasos.map((p, i) => (
            <li key={`${p.skillId}-${i}`}>
              <span>{p.nombre}</span>
              <b className={p.completadas >= p.objetivo ? 'texto-exito' : undefined}>
                {textoMarca(p.completadas, p.objetivo, p.unidad)}
              </b>
            </li>
          ))}
          <li className="fila-sesion-nota">
            {s.indicaciones === 0 ? 'Sin correcciones' : plural(s.indicaciones, 'corrección', 'correcciones')}
            {!s.terminada && ' · terminada antes del final'}
          </li>
        </ul>
      </details>
    </li>
  )
}

function BorrarHistorial({ bridge, alBorrar }: { bridge: Bridge; alBorrar: () => void }) {
  const [confirmar, setConfirmar] = useState(false)
  const [fallo, setFallo] = useState(false)
  const borrar = async () => {
    const ok = await bridge.borrarHistorial().catch(() => false)
    setFallo(!ok)
    setConfirmar(false)
    if (ok) alBorrar()
  }
  return (
    <div className="progreso-borrar">
      {confirmar ? (
        <Aviso tipo="cuidado" icono={<Trash2 />} titulo="¿Borrar todas tus sesiones guardadas?"
               accion={<div className="acciones">
                 <Boton variante="peligro" onClick={() => void borrar()}>Sí, borrar</Boton>
                 <Boton variante="suave" onClick={() => setConfirmar(false)}>Cancelar</Boton>
               </div>}>
          Se borra de este equipo y no se puede deshacer.
        </Aviso>
      ) : (
        <Boton variante="suave" onClick={() => setConfirmar(true)}><Trash2 />Borrar historial</Boton>
      )}
      {fallo && <p className="texto-peligro">No se pudo borrar el historial. Inténtalo de nuevo.</p>}
    </div>
  )
}
