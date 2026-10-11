import { AlertTriangle, Loader2, Play, RotateCcw, Ruler, ScanLine, Sun } from 'lucide-react'
import { useState } from 'react'
import type { Bridge, Nivel } from '../bridge/tipos'
import { Aviso, Boton, Marca, plural } from '../componentes/basicos'
import { Figura, IconoVista, textoVista } from '../componentes/Figura'
import { useCapacidad, useEstado } from '../estado/almacen'

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

export function Inicio({ bridge }: { bridge: Bridge }) {
  const rutina = useEstado((s) => s.info?.rutina ?? null)
  const fuente = useEstado((s) => s.info?.fuente ?? 'camara')
  const fase = useEstado((s) => s.estado?.fase ?? 'inicio')
  const error = useEstado((s) => s.estado?.error ?? null)
  const conNivel = useCapacidad('nivel')
  const [nivel, setNivel] = useState<Nivel>('principiante')
  const preparando = fase === 'preparando'

  const comenzar = () => { void bridge.iniciar(conNivel ? { nivel } : undefined) }

  return (
    <main className="pantalla pantalla-inicio">
      <header className="cabecera">
        <Marca />
        <span className="etiqueta">Calentamiento guiado</span>
      </header>

      <section className="inicio-cuerpo">
        <div className="inicio-texto">
          <span className="etiqueta etiqueta-marca">Sesión de hoy</span>
          <h1>Tu sesión,<br /><em>a tu ritmo.</em></h1>
          <p className="inicio-proposito">
            Te observo con la cámara mientras calientas y te doy indicaciones habladas sobre tu técnica.
          </p>

          <ul className="consejos" aria-label="Antes de empezar">
            <li><Ruler aria-hidden="true" />Aléjate unos 2,5–3 m de la pantalla</li>
            <li><ScanLine aria-hidden="true" />Que se vea tu cuerpo entero</li>
            <li><Sun aria-hidden="true" />Busca un lugar con buena luz</li>
          </ul>

          {conNivel && (
            <div className="selector-nivel" role="radiogroup" aria-label="Nivel">
              {(['principiante', 'avanzado'] as Nivel[]).map((n) => (
                <button key={n} role="radio" aria-checked={nivel === n}
                        className={nivel === n ? 'activo' : undefined} onClick={() => setNivel(n)}>
                  {n === 'principiante' ? 'Principiante' : 'Avanzado'}
                </button>
              ))}
            </div>
          )}

          {error && (
            <Aviso tipo="bloqueo" icono={<AlertTriangle />} titulo={textoError(error.tipo, fuente).titulo}
                   accion={<Boton variante="secundario" onClick={comenzar}><RotateCcw />Reintentar</Boton>}>
              {textoError(error.tipo, fuente).ayuda}
            </Aviso>
          )}

          {!error && (
            <div className="acciones">
              <Boton onClick={comenzar} disabled={preparando || !rutina}>
                {preparando ? <><Loader2 className="girando" />Preparando la cámara…</> : <><Play />Comenzar sesión</>}
              </Boton>
            </div>
          )}
          <p className="descargo">
            ESTELA te da indicaciones sobre tu técnica; no reemplaza a un profesional ni hace diagnósticos.
          </p>
        </div>

        {rutina && (
          <article className="tarjeta tarjeta-rutina">
            <span className="etiqueta">{plural(rutina.pasos.length, 'ejercicio', 'ejercicios')}</span>
            <h2>{rutina.nombre}</h2>
            <ol className="lista-pasos">
              {rutina.pasos.map((p, i) => (
                <li key={`${p.skillId}-${i}`}>
                  <span className="paso-figura"><Figura skillId={p.skillId} tam={44} resaltar={false} /></span>
                  <div>
                    <strong>{p.nombre}</strong>
                    <span><IconoVista vista={p.orientacion} />{textoVista(p.orientacion)}</span>
                  </div>
                  <span className="paso-objetivo">
                    {p.objetivo} {p.unidad === 'segundos' ? 's' : 'rep.'}
                  </span>
                </li>
              ))}
            </ol>
          </article>
        )}
      </section>
    </main>
  )
}
