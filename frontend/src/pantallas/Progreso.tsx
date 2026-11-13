import {
  AlertTriangle, ArrowLeft, ArrowRight, CalendarDays, Check, ChevronDown, ChevronLeft, ChevronRight, Clock, Flame,
  History, Loader2, Lock, MessageCircle, RotateCcw, Target, Trash2,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import type { Bridge, DiaProgreso, EjercicioProgreso, Progreso, SemanaComparada, SemanaProgreso, SesionHistorial } from '../bridge/tipos'
import { Aviso, Boton, plural } from '../componentes/basicos'
import { FiguraEjercicio } from '../componentes/rutina'
import { useEstado } from '../estado/almacen'
import {
  duracionLarga, estadoSesion, fechaCorta, fechaLarga, fechaRelativa, hora, isoDia, leerFecha, marcasEje, minutos,
  nivelActividad, periodoSemana, semanasDelMes, textoDiferencia, textoFrecuencia, textoMarca, textoMes, textoRacha,
  textoTramo,
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
          <div className="progreso-actividad">
            <article className="tarjeta progreso-semanas">
              <div className="progreso-semanas-cabeza">
                <div>
                  <h2>Minutos en movimiento por semana</h2>
                  <p className="progreso-sub">
                    Últimas {datos.semanas.length} semanas, de lunes a domingo. Es el mismo tiempo que suma «Tiempo en movimiento», sin pausas.
                  </p>
                </div>
                <ComparacionSemana semanas={datos.semanas} comparada={datos.semanaComparada} />
              </div>
              <GraficoSemanas semanas={datos.semanas} />
            </article>
            <CalendarioActividad dias={datos.dias} sesiones={datos.sesiones} />
          </div>
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

// -- cifras generales -----------------------------------------------------------

function Cifras({ datos }: { datos: Progreso }) {
  const racha = textoRacha(datos.rachaDias)
  const mejor = datos.mejorRachaDias
  // la mejor racha solo se nombra si aporta: si es más larga que la actual, o si la actual la iguala
  const detalleRacha = mejor > datos.rachaDias ? `Tu mejor racha: ${plural(mejor, 'día', 'días')}`
    : datos.rachaDias > 1 ? 'Es tu mejor racha' : undefined
  return (
    <div className="progreso-cifras">
      {datos.metaSemanal != null
        ? <CifraMeta dias={datos.diasSemanaActual} meta={datos.metaSemanal} />
        : <Cifra icono={<CalendarDays />} etiqueta="Días activos" valor={`${datos.diasActivos7} de 7`} extra="en los últimos 7 días" />}
      <Cifra icono={<Flame />} etiqueta="Racha" valor={racha.valor} extra={racha.extra} detalle={detalleRacha}
             destacada={datos.rachaDias > 0} />
      <Cifra icono={<Clock />} etiqueta="Tiempo en movimiento" valor={duracionLarga(datos.totalDuracionS)}
             extra={`en ${plural(datos.totalSesiones, 'sesión', 'sesiones')}`}
             detalle={`≈ ${duracionLarga(datos.promedioSesionS)} por sesión`} />
      <Cifra icono={<History />} etiqueta="Actividad desde" valor={datos.primeraFecha ? fechaCorta(datos.primeraFecha) : '—'}
             extra={plural(datos.diasActivos, 'día activo', 'días activos')} />
    </div>
  )
}

/** Meta semanal del perfil (ADR-009): días con sesión de lunes a hoy frente a la meta. */
function CifraMeta({ dias, meta }: { dias: number; meta: number }) {
  const cumplida = dias >= meta
  return (
    <div className={`tarjeta cifra ${cumplida ? 'cifra-cumplida' : ''}`}>
      <span className="cifra-etiqueta" title="Meta de esta semana"><Target /><span>Meta de esta semana</span></span>
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

function Cifra({ icono, etiqueta, valor, extra, detalle, destacada = false }: {
  icono: ReactNode; etiqueta: string; valor: string; extra?: string; detalle?: string; destacada?: boolean
}) {
  return (
    <div className={`tarjeta cifra ${destacada ? 'cifra-destacada' : ''}`}>
      <span className="cifra-etiqueta" title={etiqueta}>{icono}<span>{etiqueta}</span></span>
      <strong>{valor}</strong>
      {extra && <span className="cifra-extra">{extra}</span>}
      {detalle && <span className="cifra-detalle">{detalle}</span>}
    </div>
  )
}

// -- gráfico de semanas ---------------------------------------------------------

/** Esta semana y, si el historial lo permite, frente al mismo tramo de la pasada. */
function ComparacionSemana({ semanas, comparada }: { semanas: SemanaProgreso[]; comparada: SemanaComparada | null }) {
  const actual = semanas.at(-1)
  if (!actual) return null
  const signo = comparada ? Math.sign(minutos(comparada.diferenciaS)) : 0
  return (
    <div className="comparacion-semana">
      <span className="comparacion-actual">Esta semana <strong>{minutos(actual.duracionS)} min</strong></span>
      {comparada && (
        <span className={`comparacion-delta ${signo > 0 ? 'sube' : signo < 0 ? 'baja' : ''}`}>
          <b>{textoDiferencia(comparada.diferenciaS)}</b> frente a la semana pasada, {textoTramo(comparada.dias)}
          {' '}({minutos(comparada.anteriorS)} min)
        </span>
      )}
    </div>
  )
}

/** alto mínimo del gráfico; con el calendario al lado ocupa el alto de la fila */
const ALTO_MINIMO = 220
const MARGEN = { arriba: 26, derecha: 8, abajo: 28, izquierda: 34 }

/** Columnas de una sola serie: minutos por semana. Pasar el ratón, el foco o
 *  tocar una semana muestra su periodo, minutos y sesiones; la tabla da los mismos datos. */
function GraficoSemanas({ semanas }: { semanas: SemanaProgreso[] }) {
  const caja = useRef<HTMLDivElement>(null)
  const [{ ancho, ALTO }, setTam] = useState({ ancho: 560, ALTO: ALTO_MINIMO })
  const [encima, setEncima] = useState<number | null>(null)
  const [fija, setFija] = useState<number | null>(null)
  useEffect(() => {
    const el = caja.current
    if (!el) return
    // el lienzo no depende del SVG (va en absoluto): medirlo no hace crecer la tarjeta
    const obs = new ResizeObserver(([e]) => setTam({
      ancho: Math.max(280, e.contentRect.width), ALTO: Math.max(ALTO_MINIMO, Math.round(e.contentRect.height)),
    }))
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const valores = semanas.map((s) => minutos(s.duracionS))
  const marcas = marcasEje(Math.max(...valores, 0))
  const tope = marcas.at(-1)!
  const altoUtil = ALTO - MARGEN.arriba - MARGEN.abajo
  const banda = (ancho - MARGEN.izquierda - MARGEN.derecha) / semanas.length
  const grosor = Math.min(32, banda * 0.56)
  const y = (v: number) => MARGEN.arriba + altoUtil * (1 - v / tope)
  const base = y(0)
  const x = (i: number) => MARGEN.izquierda + banda * i + banda / 2
  const ultima = semanas.length - 1
  const activa = encima ?? fija
  // con poco ancho, las fechas del eje se alternan para que no se pisen
  const saltar = banda < 52

  return (
    <div className="grafico-semanas">
      <div className="grafico-lienzo" ref={caja} onMouseLeave={() => setEncima(null)}>
      <svg width={ancho} height={ALTO} role="img"
           aria-label={`Minutos en movimiento por semana. Esta semana: ${valores[ultima]} minutos.`}>
        <text className="eje-unidad" x={MARGEN.izquierda - 8} y={10} textAnchor="end">min</text>
        {marcas.map((m) => (
          <g key={m}>
            <line className={m === 0 ? 'eje-base' : 'eje-rejilla'} x1={MARGEN.izquierda} x2={ancho - MARGEN.derecha} y1={y(m)} y2={y(m)} />
            <text className="eje-texto" x={MARGEN.izquierda - 8} y={y(m)} dy="0.32em" textAnchor="end">{m}</text>
          </g>
        ))}
        {semanas.map((s, i) => {
          const v = valores[i]
          const alto = base - y(v)
          const r = Math.min(5, alto, grosor / 2)
          const x0 = x(i) - grosor / 2
          // esquinas redondeadas arriba, rectas en la línea base
          const d = alto <= 0 ? '' : `M${x0},${base} V${base - alto + r} Q${x0},${base - alto} ${x0 + r},${base - alto}
            H${x0 + grosor - r} Q${x0 + grosor},${base - alto} ${x0 + grosor},${base - alto + r} V${base} Z`
          const etiqueta = i === ultima ? 'Esta semana' : fechaCorta(s.inicio)
          return (
            <g key={s.inicio} className={`columna ${activa === i ? 'activa' : ''} ${i === ultima ? 'actual' : ''} ${v === 0 ? 'vacia' : ''}`}
               tabIndex={0} role="button" aria-pressed={fija === i}
               aria-label={`${i === ultima ? 'Esta semana' : 'Semana'} del ${periodoSemana(s.inicio)}: ${s.sesiones === 0 ? 'sin actividad' : `${v} minutos en ${plural(s.sesiones, 'sesión', 'sesiones')}`}`}
               onMouseEnter={() => setEncima(i)}
               onFocus={() => setEncima(i)} onBlur={() => setEncima(null)}
               onClick={() => setFija(fija === i ? null : i)}
               onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); setFija(fija === i ? null : i) } }}>
              {/* zona sensible más grande que la columna */}
              <rect className="columna-zona" x={x(i) - banda / 2} y={MARGEN.arriba} width={banda} height={altoUtil} rx={6} />
              {/* una semana sin actividad se ve como una marca en la base, no como un hueco */}
              {d ? <path d={d} /> : <rect className="columna-vacia" x={x(i) - grosor / 2} y={base - 3} width={grosor} height={3} rx={1.5} />}
              {i === ultima && v > 0 && <text className="columna-valor" x={x(i)} y={base - alto - 7} textAnchor="middle">{v}</text>}
              {(!saltar || i === ultima || (ultima - i) % 2 === 0) && (
                <text className="eje-texto" x={x(i)} y={ALTO - 8} textAnchor="middle">{etiqueta}</text>
              )}
            </g>
          )
        })}
      </svg>
      {activa !== null && (
        <div className="grafico-tooltip" role="status"
             style={{ left: Math.min(Math.max(x(activa), 96), ancho - 96), top: Math.max(0, y(valores[activa]) - 74) }}>
          <strong>{activa === ultima ? 'Esta semana' : 'Semana'} · {periodoSemana(semanas[activa].inicio)}</strong>
          <span>
            {semanas[activa].sesiones === 0 ? 'Sin actividad'
              : `${valores[activa]} min · ${plural(semanas[activa].sesiones, 'sesión', 'sesiones')}`}
            {activa === ultima && ' · hasta hoy'}
          </span>
        </div>
      )}
      </div>
      <details className="grafico-tabla">
        <summary>Ver como tabla</summary>
        <table>
          <thead><tr><th>Semana</th><th>Sesiones</th><th>Minutos</th></tr></thead>
          <tbody>
            {semanas.map((s) => (
              <tr key={s.inicio}><td>{periodoSemana(s.inicio)}</td><td>{s.sesiones}</td><td>{minutos(s.duracionS)}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}

// -- calendario de actividad ------------------------------------------------------

const INICIALES = ['L', 'M', 'X', 'J', 'V', 'S', 'D']

/** Mes con los días activos en violeta (más intenso, más minutos) y el detalle del día elegido. */
function CalendarioActividad({ dias, sesiones }: { dias: DiaProgreso[]; sesiones: SesionHistorial[] }) {
  const hoy = new Date()
  const hoyIso = isoDia(hoy)
  const porFecha = new Map(dias.map((d) => [d.fecha, d]))
  const maximo = Math.max(0, ...dias.map((d) => d.duracionS))
  const primero = dias.length ? leerFecha(dias[0].fecha) : hoy
  const [vista, setVista] = useState({ anio: hoy.getFullYear(), mes: hoy.getMonth() })
  const [elegido, setElegido] = useState<string | null>(null)

  const indice = (a: number, m: number) => a * 12 + m
  const hayAnterior = indice(vista.anio, vista.mes) > indice(primero.getFullYear(), primero.getMonth())
  const haySiguiente = indice(vista.anio, vista.mes) < indice(hoy.getFullYear(), hoy.getMonth())
  const mover = (delta: number) => {
    const n = indice(vista.anio, vista.mes) + delta
    setVista({ anio: Math.floor(n / 12), mes: n % 12 })
  }
  const activosMes = dias.filter((d) => {
    const f = leerFecha(d.fecha)
    return f.getFullYear() === vista.anio && f.getMonth() === vista.mes
  }).length

  const dia = elegido ? porFecha.get(elegido) ?? null : null
  const delDia = elegido ? sesiones.filter((s) => s.fecha.startsWith(elegido)) : []

  return (
    <article className="tarjeta calendario">
      <div className="calendario-cabeza">
        <div>
          <h2>Calendario de actividad</h2>
          <p className="progreso-sub">{plural(activosMes, 'día activo', 'días activos')} este mes</p>
        </div>
        <div className="calendario-nav">
          <button type="button" onClick={() => mover(-1)} disabled={!hayAnterior} aria-label="Mes anterior"><ChevronLeft /></button>
          <span aria-live="polite">{textoMes(vista.anio, vista.mes)}</span>
          <button type="button" onClick={() => mover(1)} disabled={!haySiguiente} aria-label="Mes siguiente"><ChevronRight /></button>
        </div>
      </div>

      <div className="calendario-rejilla" role="grid" aria-label={`Actividad de ${textoMes(vista.anio, vista.mes)}`}>
        <div role="row" className="calendario-fila">
          {INICIALES.map((l) => <span key={l} role="columnheader" className="calendario-dia-semana">{l}</span>)}
        </div>
        {semanasDelMes(vista.anio, vista.mes).map((semana, k) => (
          <div role="row" className="calendario-fila" key={k}>
            {semana.map((f, j) => {
              if (!f) return <span key={j} role="gridcell" className="calendario-celda fuera" />
              const iso = isoDia(f)
              const d = porFecha.get(iso)
              const nivel = d ? nivelActividad(d.duracionS, maximo) : 0
              const futuro = iso > hoyIso
              return (
                <span key={j} role="gridcell">
                  <button type="button" disabled={futuro}
                          className={`calendario-celda nivel-${nivel} ${iso === hoyIso ? 'hoy' : ''} ${elegido === iso ? 'elegida' : ''}`}
                          aria-pressed={elegido === iso}
                          aria-label={`${fechaLarga(iso)}: ${d ? `${plural(d.sesiones, 'sesión', 'sesiones')}, ${duracionLarga(d.duracionS)}` : 'sin actividad'}`}
                          onClick={() => setElegido(elegido === iso ? null : iso)}>
                    {f.getDate()}
                  </button>
                </span>
              )
            })}
          </div>
        ))}
      </div>

      <div className="calendario-leyenda" aria-hidden="true">
        <span>Menos</span>
        {[0, 1, 2, 3].map((n) => <i key={n} className={`nivel-${n}`} />)}
        <span>Más minutos</span>
      </div>

      <div className="calendario-detalle" aria-live="polite">
        {!elegido ? (
          <p className="calendario-pista">Elige un día para ver sus sesiones.</p>
        ) : !dia ? (
          <p><strong>{fechaLarga(elegido)}</strong> · sin actividad</p>
        ) : (
          <>
            <p><strong>{fechaLarga(elegido)}</strong> · {plural(dia.sesiones, 'sesión', 'sesiones')} · {duracionLarga(dia.duracionS)}</p>
            {delDia.length > 0 && (
              <ul>
                {delDia.map((s) => {
                  const estado = estadoSesion(s.terminada, s.motivoFin)
                  return (
                    <li key={s.fecha}>
                      <span>{hora(s.fecha)}</span>
                      <span>{duracionLarga(s.duracionS)}</span>
                      <span className={`estado-sesion ${estado.clave}`}>{estado.texto}</span>
                    </li>
                  )
                })}
              </ul>
            )}
            {delDia.length < dia.sesiones && (
              <p className="calendario-pista">El detalle de cada sesión se guarda para las {sesiones.length} más recientes.</p>
            )}
          </>
        )}
      </div>
    </article>
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
      <div className="progreso-historial-cabeza">
        <h2>Sesiones recientes</h2>
        <p className="progreso-sub">Toca una sesión para ver cada ejercicio.</p>
      </div>
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
  const f = leerFecha(s.fecha)
  const estado = estadoSesion(s.terminada, s.motivoFin)
  return (
    <li>
      <details className="fila-sesion">
        <summary>
          <span className="fila-sesion-dia" aria-hidden="true"><b>{f.getDate()}</b><small>{fechaCorta(s.fecha).split(' ')[1]}</small></span>
          <span className="fila-sesion-principal">
            <strong>{s.rutina}</strong>
            <span>{fechaLarga(s.fecha)} · {hora(s.fecha)}</span>
          </span>
          <span className={`estado-sesion ${estado.clave}`}>{estado.texto}</span>
          <span className="fila-sesion-dato"><Clock aria-hidden="true" />{duracionLarga(s.duracionS)}</span>
          <span className="fila-sesion-dato"><Target aria-hidden="true" />{s.completos} de {s.ejercicios} objetivos</span>
          <ChevronDown className="flecha" aria-hidden="true" />
        </summary>
        <div className="fila-sesion-detalle">
          <ul>
            {s.pasos.map((p, i) => {
              const ok = p.completadas >= p.objetivo
              return (
                <li key={`${p.skillId}-${i}`}>
                  <span>{p.nombre}</span>
                  <b className={ok ? 'texto-exito' : undefined}>
                    {textoMarca(p.completadas, p.objetivo, p.unidad)}
                    {ok && <Check aria-label="objetivo alcanzado" />}
                  </b>
                </li>
              )
            })}
          </ul>
          <p className="fila-sesion-nota">
            <MessageCircle aria-hidden="true" />
            {s.indicaciones === 0 ? 'Sin indicaciones de técnica' : plural(s.indicaciones, 'indicación de técnica', 'indicaciones de técnica')}
          </p>
        </div>
      </details>
    </li>
  )
}

// -- borrar el historial --------------------------------------------------------------

function BorrarHistorial({ bridge, alBorrar }: { bridge: Bridge; alBorrar: () => void }) {
  const [abierto, setAbierto] = useState(false)
  return (
    <div className="progreso-borrar">
      <Boton variante="suave" onClick={() => setAbierto(true)}><Trash2 />Borrar historial</Boton>
      {abierto && <DialogoBorrar bridge={bridge} alCerrar={() => setAbierto(false)} alBorrar={alBorrar} />}
    </div>
  )
}

/** Confirmación modal: explica qué se pierde y qué se queda; Esc o «Cancelar» lo cierran. */
function DialogoBorrar({ bridge, alCerrar, alBorrar }: { bridge: Bridge; alCerrar: () => void; alBorrar: () => void }) {
  const cancelar = useRef<HTMLButtonElement>(null)
  const [borrando, setBorrando] = useState(false)
  const [fallo, setFallo] = useState(false)
  useEffect(() => {
    cancelar.current?.focus()
    const tecla = (ev: KeyboardEvent) => { if (ev.key === 'Escape' && !borrando) alCerrar() }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [alCerrar, borrando])
  const borrar = async () => {
    setBorrando(true)
    const ok = await bridge.borrarHistorial().catch(() => false)
    setBorrando(false)
    if (ok) { alCerrar(); alBorrar() } else setFallo(true)
  }
  return (
    <div className="capa-dialogo" onClick={(ev) => { if (ev.target === ev.currentTarget && !borrando) alCerrar() }}>
      <div className="tarjeta tarjeta-confirmar dialogo-borrar" role="alertdialog" aria-modal="true"
           aria-labelledby="titulo-borrar" aria-describedby="texto-borrar">
        <span className="etiqueta etiqueta-cuidado">Borrar historial</span>
        <h2 id="titulo-borrar">¿Borrar todo tu historial?</h2>
        <div id="texto-borrar" className="dialogo-borrar-texto">
          <p>Se eliminarán de este equipo todas tus sesiones guardadas y las estadísticas que salen de ellas:</p>
          <ul>
            <li>racha, meta de la semana y tiempo en movimiento;</li>
            <li>marcas por ejercicio e indicaciones recibidas;</li>
            <li>el calendario y las sesiones recientes.</li>
          </ul>
          <p>Tu perfil y tu rutina se mantienen. <strong>No se puede deshacer.</strong></p>
        </div>
        {fallo && <p className="texto-peligro" role="alert">No se pudo borrar el historial. Inténtalo de nuevo.</p>}
        <div className="acciones">
          <button ref={cancelar} type="button" className="boton boton-secundario" onClick={alCerrar} disabled={borrando}>
            Cancelar
          </button>
          <Boton variante="peligro" onClick={() => void borrar()} disabled={borrando}>
            {borrando ? <><Loader2 className="girando" />Borrando…</> : <><Trash2 />Sí, borrar historial</>}
          </Boton>
        </div>
      </div>
    </div>
  )
}
