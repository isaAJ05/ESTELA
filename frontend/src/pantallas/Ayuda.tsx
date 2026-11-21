import {
  ArrowLeft, ArrowRight, Check, Hand, Keyboard, LifeBuoy, ListChecks, Mic, Ruler, ScanLine, Sun,
} from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Boton, BotonVolver } from '../componentes/basicos'
import { Estrella, type Pose } from '../componentes/Estrella'
import { useCapacidad } from '../estado/almacen'

interface Diapositiva {
  pose: Pose
  titulo: string
  texto: string
  consejos: { icono: ReactNode; texto: string }[]
}

/**
 * «Ayuda»: un recorrido de pocas tarjetas, una idea cada vez (como el tutorial
 * de una app), y debajo lo que solo se consulta (atajos y problemas) cerrado.
 *
 * Una sola guía para todos los equipos: cada parte sale solo si el equipo la
 * tiene (las capacidades que manda Python). En el Mac, con órdenes de voz
 * (`vozEntrada`), aparece su tarjeta; en un computador sin micrófono, no.
 */
export function PanelAyuda({ alVolver }: { alVolver: () => void }) {
  const conRutinas = useCapacidad('rutinaPersonalizada')
  const conProgreso = useCapacidad('historial')
  const conGesto = useCapacidad('gestoPausa')
  const conVozEntrada = useCapacidad('vozEntrada')

  const diapositivas: Diapositiva[] = [
    {
      pose: 'saludo', titulo: 'Prepara tu espacio',
      texto: 'Antes de empezar, colócate donde la cámara te vea bien.',
      consejos: [
        { icono: <Ruler />, texto: 'A unos 2,5–3 m de la pantalla' },
        { icono: <ScanLine />, texto: 'Que se vea tu cuerpo entero' },
        { icono: <Sun />, texto: 'En un lugar con buena luz' },
      ],
    },
    {
      pose: 'feliz', titulo: conRutinas ? 'Elige tu rutina' : 'Revisa tu rutina',
      texto: conRutinas
        ? 'Usa la rutina recomendada o crea la tuya en «Mis rutinas».'
        : 'En el inicio ves los ejercicios de hoy y su objetivo.',
      consejos: conRutinas ? [
        { icono: <ListChecks />, texto: 'Elige los ejercicios y su orden' },
        { icono: <Check />, texto: 'Ajusta repeticiones o segundos' },
      ] : [],
    },
    {
      pose: 'enfoque', titulo: 'Entrena con ESTELA',
      texto: 'Pulsa «Comenzar sesión». ESTELA cuenta tus repeticiones y te corrige por voz.',
      consejos: [
        { icono: <ScanLine />, texto: 'La pantalla te dice si ponerte de frente o de perfil' },
        ...(conGesto ? [{ icono: <Hand />, texto: 'Para pausar, levanta el brazo derecho 3 segundos' }] : []),
        { icono: <Sun />, texto: 'Si el contador se detiene, lee el aviso en pantalla' },
      ],
    },
    ...(conVozEntrada ? [{
      pose: 'tranquila' as Pose, titulo: 'Habla con ESTELA',
      texto: 'Di «Estela» y, después, lo que quieres hacer.',
      consejos: [
        { icono: <Mic />, texto: '«Estela, pausa» · «Estela, seguir»' },
        { icono: <Mic />, texto: '«Estela, siguiente» · «Estela, terminar»' },
        { icono: <Mic />, texto: '«Estela, ¿cómo voy?»' },
      ],
    }] : []),
    {
      pose: 'victoria', titulo: 'Mira cómo te fue',
      texto: conProgreso
        ? 'Al terminar ves tu resumen, y en «Mi progreso», tu avance semana a semana.'
        : 'Al terminar ves un resumen de cada ejercicio.',
      consejos: [],
    },
  ]

  const [i, setI] = useState(0)
  const d = diapositivas[Math.min(i, diapositivas.length - 1)]
  const ultima = i >= diapositivas.length - 1
  // flechas del teclado para pasar las tarjetas
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') setI((n) => Math.min(n + 1, diapositivas.length - 1))
      else if (e.key === 'ArrowLeft') setI((n) => Math.max(n - 1, 0))
    }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [diapositivas.length])

  return (
    <section className="ayuda-cuerpo">
      <div className="ayuda-cabeza">
        <BotonVolver onClick={alVolver} />
        <span className="etiqueta etiqueta-marca">Ayuda</span>
        <h1>Cómo usar <em>ESTELA</em></h1>
      </div>

      <article className="tarjeta ayuda-tour" aria-roledescription="carrusel" aria-label="Cómo funciona">
        <div className="ayuda-tour-figura"><Estrella pose={d.pose} /></div>
        <div className="ayuda-tour-texto" aria-live="polite">
          <span className="etiqueta">Paso {i + 1} de {diapositivas.length}</span>
          <h2>{d.titulo}</h2>
          <p>{d.texto}</p>
          {d.consejos.length > 0 && (
            <ul className="ayuda-tour-consejos">
              {d.consejos.map((c) => <li key={c.texto}><span aria-hidden="true">{c.icono}</span>{c.texto}</li>)}
            </ul>
          )}
        </div>
        <footer className="ayuda-tour-pie">
          <div className="ayuda-tour-puntos" role="tablist" aria-label="Pasos">
            {diapositivas.map((x, k) => (
              <button key={x.titulo} role="tab" aria-selected={k === i} aria-label={`Paso ${k + 1}: ${x.titulo}`}
                      className={k === i ? 'activo' : undefined} onClick={() => setI(k)} />
            ))}
          </div>
          <div className="ayuda-tour-botones">
            {i > 0 && <Boton variante="suave" onClick={() => setI(i - 1)}><ArrowLeft />Anterior</Boton>}
            {ultima
              ? <Boton onClick={alVolver}><Check />Entendido</Boton>
              : <Boton onClick={() => setI(i + 1)}>Siguiente<ArrowRight /></Boton>}
          </div>
        </footer>
      </article>

      {/* lo que solo se consulta: cerrado hasta que se toca */}
      <div className="ayuda-extra">
        <Desplegable icono={<Keyboard />} titulo="Atajos de teclado" sub="Para controlar la sesión desde el teclado">
          <Atajos />
        </Desplegable>
        <Desplegable icono={<LifeBuoy />} titulo="Si algo no va bien" sub="Cámara, voz y detección">
          <Problemas />
        </Desplegable>
      </div>

      <p className="descargo ayuda-descargo">
        Si sientes dolor o mareo, detente. ESTELA te da indicaciones sobre tu técnica; no reemplaza a un profesional
        ni hace diagnósticos. La imagen de la cámara no se guarda ni sale de este equipo.
      </p>
    </section>
  )
}

function Desplegable({ icono, titulo, sub, children }: { icono: ReactNode; titulo: string; sub: string; children: ReactNode }) {
  return (
    <details className="tarjeta ayuda-desplegable">
      <summary>
        <span className="ayuda-icono" aria-hidden="true">{icono}</span>
        <span><strong>{titulo}</strong><small>{sub}</small></span>
      </summary>
      <div className="ayuda-desplegable-cuerpo">{children}</div>
    </details>
  )
}

/** Solo las teclas de lo que este equipo tiene. */
function Atajos() {
  const conPausa = useCapacidad('pausaManual')
  const conSilenciar = useCapacidad('silenciarVoz')
  const conAnterior = useCapacidad('pasoAnterior')
  const atajos: [string, string][] = [
    ...(conPausa ? [['Espacio', 'Pausar o seguir'] as [string, string]] : []),
    ['N', 'Siguiente ejercicio'],
    ...(conAnterior ? [['P', 'Ejercicio anterior'] as [string, string]] : []),
    ['R', 'Repetir este ejercicio'],
    ...(conSilenciar ? [['V', 'Silenciar la voz'] as [string, string]] : []),
    ['A', 'Ver los ángulos'],
    ['Esc', 'Terminar la rutina'],
  ]
  return (
    <ul className="ayuda-atajos">
      {atajos.map(([k, t]) => <li key={k}><kbd>{k}</kbd>{t}</li>)}
    </ul>
  )
}

function Problemas() {
  const conCamaras = useCapacidad('elegirCamara')
  const conSilenciar = useCapacidad('silenciarVoz')
  const filas: [string, string][] = [
    ['No se detecta la cámara',
     'Revisa que esté conectada y que ninguna otra aplicación la use.'
       + (conCamaras ? ' Puedes elegir otra en Ajustes → Cámara.' : '')],
    ['ESTELA no me ve o no cuenta', 'Aléjate hasta que se vea tu cuerpo entero, busca más luz y ponte de frente o de perfil como pide el ejercicio.'],
    ['No oigo las indicaciones',
     'Sube el volumen del equipo' + (conSilenciar ? ' y revisa que la voz no esté silenciada (tecla V).' : '.')],
    ['El texto se ve pequeño', 'Agrándalo en Ajustes → Tamaño del texto.'],
  ]
  return (
    <dl className="ayuda-problemas">
      {filas.map(([p, r]) => <div key={p}><dt>{p}</dt><dd>{r}</dd></div>)}
    </dl>
  )
}
