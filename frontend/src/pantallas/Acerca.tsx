import { ExternalLink, Lock, MessageCircle, ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import { BotonVolver } from '../componentes/basicos'
import { Estrella } from '../componentes/Estrella'
import { Avatar } from '../componentes/perfil'

/** Página pública del proyecto. */
const PAGINA = 'https://estela-trainer.vercel.app/'

const EQUIPO: [string, string][] = [
  ['Natalia Carpintero', 'turquesa'],
  ['Isabella Arrieta', 'violeta'],
  ['Paula Núñez', 'rosa'],
]

/**
 * Apartado «Acerca de»: qué es ESTELA, qué la hace distinta y quién la hizo.
 */
export function PanelAcerca({ alVolver }: { alVolver: () => void }) {
  return (
    <section className="ayuda-cuerpo">
      <div className="ayuda-cabeza">
        <BotonVolver onClick={alVolver} />
        <span className="etiqueta etiqueta-marca">Acerca de</span>
        <h1>Conoce a <em>ESTELA</em></h1>
      </div>

      <article className="tarjeta acerca-presentacion">
        <Estrella pose="saludo" />
        <p>
          ESTELA te acompaña en una rutina de calentamiento de bajo impacto: te observa con la cámara
          y te dice por voz, en español, cómo mejorar tu técnica en cada ejercicio.
        </p>
      </article>

      <div className="acerca-rasgos">
        <Rasgo icono={<MessageCircle />} titulo="Te corrige por voz">
          Una indicación clara cuando algo se puede mejorar, sin tener que mirar la pantalla.
        </Rasgo>
        <Rasgo icono={<Lock />} titulo="Todo en tu equipo">
          La imagen de la cámara se analiza en este computador; no se guarda ni se envía a ningún sitio.
        </Rasgo>
        <Rasgo icono={<ShieldCheck />} titulo="Sin diagnósticos">
          Te ayuda con la técnica; no reemplaza a un profesional de la salud.
        </Rasgo>
      </div>

      <article className="tarjeta acerca-equipo">
        <div>
          <span className="etiqueta">El equipo</span>
          <h3>Hecha por NIP Creations</h3>
          <p>Estudiantes de Ingeniería de Sistemas de la Universidad del Norte.</p>
        </div>
        <ul className="acerca-personas">
          {EQUIPO.map(([nombre, color]) => (
            <li key={nombre}><Avatar nombre={nombre} color={color} tam="lg" /><span>{nombre}</span></li>
          ))}
        </ul>
        {/* pywebview abre los enlaces con target="_blank" en el navegador del sistema */}
        <a className="boton boton-secundario acerca-enlace" href={PAGINA} target="_blank" rel="noopener noreferrer">
          Visita nuestra página<ExternalLink aria-hidden="true" />
        </a>
      </article>
    </section>
  )
}

function Rasgo({ icono, titulo, children }: { icono: ReactNode; titulo: string; children: ReactNode }) {
  return (
    <article className="tarjeta acerca-rasgo">
      <span className="ayuda-icono" aria-hidden="true">{icono}</span>
      <h3>{titulo}</h3>
      <p>{children}</p>
    </article>
  )
}
