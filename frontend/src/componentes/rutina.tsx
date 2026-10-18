import { AlertTriangle, ArrowDown, ArrowUp, Check, Clock, Dumbbell, Loader2, Minus, Play, Plus, RotateCcw, X } from 'lucide-react'
import { useEffect, useId, useState, type ReactNode } from 'react'
import type { EjercicioCatalogo, PasoRutina } from '../bridge/tipos'
import { Aviso, Boton, plural } from './basicos'
import { Figura, textoVista } from './Figura'
import { GuiaAnimada } from './VistaCamara'
import { leerObjetivo, limitar, pasoDe } from '../estado/rutina'

/** «Repeticiones», «Segundos en posición»… según cómo cuenta el backend. */
export function textoUnidad(ej: Pick<EjercicioCatalogo, 'unidad' | 'conteo'>): string {
  if (ej.unidad === 'segundos') return 'Segundos en posición'
  return ej.conteo === 'alternante' ? 'Repeticiones · cada pierna cuenta 1' : 'Repeticiones'
}

export function textoObjetivo(p: Pick<PasoRutina, 'objetivo' | 'unidad'>): string {
  return `${p.objetivo} ${p.unidad === 'segundos' ? 's' : 'rep.'}`
}

/** «≈ 4 min», «menos de 1 min». */
export function textoEstimado(segundos: number): string {
  return segundos < 60 ? 'menos de 1 min' : `≈ ${Math.round(segundos / 60)} min`
}

/** Postura de referencia del ejercicio (o la figura dibujada si no hay referencia). */
export function FiguraEjercicio({ paso, tam = 44 }: { paso: Pick<PasoRutina, 'skillId' | 'guia'>; tam?: number }) {
  return paso.guia
    ? <GuiaAnimada puntos={paso.guia} ejercicioId={paso.skillId} animar={false} />
    : <Figura skillId={paso.skillId} tam={tam} resaltar={false} />
}

/**
 * Objetivo del ejercicio: botones − / + y campo para escribirlo. Lo escrito
 * se valida al momento; si no vale, se avisa y no se cambia la rutina.
 */
export function ControlObjetivo({ ej, valor, alCambiar, alValidar }: {
  ej: EjercicioCatalogo
  valor: number
  alCambiar: (valor: number) => void
  alValidar: (valido: boolean) => void
}) {
  const id = useId()
  const [texto, setTexto] = useState(String(valor))
  const [error, setError] = useState<string | null>(null)

  // si el valor cambia desde fuera (− / +, restablecer), el campo lo refleja
  useEffect(() => { setTexto(String(valor)); setError(null); alValidar(true) }, [valor]) // eslint-disable-line react-hooks/exhaustive-deps

  const escribir = (t: string) => {
    setTexto(t)
    const r = leerObjetivo(t, ej)
    setError(r.ok ? null : r.error)
    alValidar(r.ok)
    if (r.ok && r.valor !== valor) alCambiar(r.valor)
  }
  const sumar = (signo: 1 | -1) => alCambiar(limitar(valor + signo * pasoDe(ej.unidad), ej))

  return (
    <div className="control-objetivo">
      <label htmlFor={id} className="etiqueta">{textoUnidad(ej)}</label>
      <div className={`stepper ${error ? 'invalido' : ''}`}>
        <button type="button" onClick={() => sumar(-1)} disabled={valor <= ej.minimo}
                aria-label={`Menos ${ej.unidad}`}><Minus /></button>
        <input id={id} inputMode="numeric" value={texto} aria-invalid={error != null}
               aria-describedby={error ? `${id}-error` : undefined}
               onChange={(e) => escribir(e.target.value)}
               onBlur={() => { if (!error) setTexto(String(valor)) }} />
        <button type="button" onClick={() => sumar(1)} disabled={valor >= ej.maximo}
                aria-label={`Más ${ej.unidad}`}><Plus /></button>
      </div>
      {error
        ? <span id={`${id}-error`} className="control-error" role="alert">{error}</span>
        : <span className="control-ayuda">De {ej.minimo} a {ej.maximo}</span>}
    </div>
  )
}

/** Tarjeta de un ejercicio del catálogo: elegirlo, quitarlo y ajustar su objetivo. */
export function TarjetaEjercicio({ ej, posicion, objetivo, alAlternar, alCambiarObjetivo, alValidar }: {
  ej: EjercicioCatalogo
  /** posición en la rutina (1, 2…) o null si no está elegido */
  posicion: number | null
  objetivo: number
  alAlternar: () => void
  alCambiarObjetivo: (valor: number) => void
  alValidar: (valido: boolean) => void
}) {
  const elegido = posicion !== null
  return (
    <article className={`tarjeta-ejercicio ${elegido ? 'elegida' : ''}`}>
      <button type="button" className="tarjeta-ejercicio-figura" onClick={alAlternar}
              aria-pressed={elegido} aria-label={`${elegido ? 'Quitar' : 'Añadir'} ${ej.nombre}`}>
        <FiguraEjercicio paso={ej} tam={96} />
        <span className="tarjeta-ejercicio-marca" aria-hidden="true">
          {elegido ? <><Check />{posicion}</> : <Plus />}
        </span>
      </button>

      <div className="tarjeta-ejercicio-cuerpo">
        <h3>{ej.nombre}</h3>
        <div className="tarjeta-ejercicio-chips">
          <span className="chip">{textoVista(ej.orientacion)}</span>
          <span className="chip">{ej.unidad === 'segundos' ? 'Por tiempo' : 'Por repeticiones'}</span>
        </div>
        {ej.descripcion && <p>{ej.descripcion}</p>}
      </div>

      <div className="tarjeta-ejercicio-pie">
        {elegido ? <>
          <ControlObjetivo ej={ej} valor={objetivo} alCambiar={alCambiarObjetivo} alValidar={alValidar} />
          <button type="button" className="enlace-quitar" onClick={alAlternar}><X />Quitar de la rutina</button>
        </> : (
          <Boton variante="suave" onClick={alAlternar}><Plus />Añadir · {textoObjetivo(ej)}</Boton>
        )}
      </div>
    </article>
  )
}

/** Resumen lateral: orden, objetivos, duración aproximada y el botón para empezar. */
export function ResumenRutina({ nombre, pasos, estimadoS, avisos, modificada, preparando, error,
                                alMover, alQuitar, alRestablecer, alComenzar, extra }: {
  nombre: string
  pasos: PasoRutina[]
  estimadoS: number
  /** por qué no se puede empezar todavía (vacía, objetivo inválido…) */
  avisos: string[]
  modificada: boolean
  preparando: boolean
  error: { titulo: string; ayuda: string } | null
  alMover: (i: number, delta: -1 | 1) => void
  alQuitar: (skillId: string) => void
  alRestablecer: () => void
  alComenzar: () => void
  extra?: ReactNode
}) {
  return (
    <aside className="tarjeta resumen-rutina" aria-label="Tu rutina">
      <div className="resumen-rutina-cabeza">
        <div>
          <span className="etiqueta etiqueta-marca">Tu rutina</span>
          <h2>{nombre}</h2>
        </div>
        {modificada && (
          <Boton variante="suave" onClick={alRestablecer} title="Volver a la rutina recomendada">
            <RotateCcw /><span>Restablecer</span>
          </Boton>
        )}
      </div>

      <div className="resumen-rutina-cifras">
        <span><Dumbbell aria-hidden="true" />{plural(pasos.length, 'ejercicio', 'ejercicios')}</span>
        {pasos.length > 0 && (
          <span title="Aproximado: unos 3 s por repetición y 10 s entre ejercicios">
            <Clock aria-hidden="true" />{textoEstimado(estimadoS)}
          </span>
        )}
      </div>

      {pasos.length === 0 ? (
        <div className="resumen-rutina-vacia">
          <Dumbbell aria-hidden="true" />
          <strong>Tu rutina está vacía</strong>
          <span>Toca un ejercicio para añadirlo.</span>
        </div>
      ) : (
        <ol className="resumen-rutina-lista">
          {pasos.map((p, i) => (
            <li key={p.skillId}>
              <span className="resumen-rutina-numero">{i + 1}</span>
              <span className="paso-figura"><FiguraEjercicio paso={p} /></span>
              <span className="resumen-rutina-nombre">
                <strong>{p.nombre}</strong>
                <span>{textoObjetivo(p)} · {textoVista(p.orientacion)}</span>
              </span>
              <span className="resumen-rutina-acciones">
                <button type="button" onClick={() => alMover(i, -1)} disabled={i === 0}
                        aria-label={`Subir ${p.nombre}`} title="Subir"><ArrowUp /></button>
                <button type="button" onClick={() => alMover(i, 1)} disabled={i === pasos.length - 1}
                        aria-label={`Bajar ${p.nombre}`} title="Bajar"><ArrowDown /></button>
                <button type="button" onClick={() => alQuitar(p.skillId)}
                        aria-label={`Quitar ${p.nombre}`} title="Quitar"><X /></button>
              </span>
            </li>
          ))}
        </ol>
      )}

      {extra}

      {error && (
        <Aviso tipo="bloqueo" icono={<AlertTriangle />} titulo={error.titulo}>{error.ayuda}</Aviso>
      )}

      <div className="resumen-rutina-pie">
        <Boton onClick={alComenzar} disabled={preparando || avisos.length > 0}>
          {preparando ? <><Loader2 className="girando" />Preparando la cámara…</>
            : error ? <><RotateCcw />Reintentar</> : <><Play />Comenzar rutina</>}
        </Boton>
        {avisos.length > 0 && !preparando && <span className="resumen-rutina-aviso" role="status">{avisos[0]}</span>}
      </div>
    </aside>
  )
}
