/**
 * Estela, la mascota. Solo aparece en momentos puntuales (bienvenida, fin de
 * la sesión, meta semanal cumplida); nunca sobre la cámara ni junto a una
 * corrección, para no restar claridad ni seriedad al feedback. Las imágenes
 * salen de la hoja de stickers de la marca (ver README, «Mascota»).
 */
export type Pose = 'saludo' | 'feliz' | 'tranquila' | 'enfoque' | 'victoria'

export function Estrella({ pose, mensaje, tam = 'md' }: {
  pose: Pose
  /** frase en un globo al lado; sin ella, solo la imagen */
  mensaje?: string
  tam?: 'sm' | 'md'
}) {
  return (
    <div className={`estrella estrella-${tam}`}>
      {/* decorativa: el mensaje ya dice lo importante */}
      {/* key: al cambiar de pose vuelve a entrar con su animación */}
      <img key={pose} className="estrella-imagen" src={`${import.meta.env.BASE_URL}estela/${pose}.png`} alt=""
           draggable={false} />
      {mensaje && <p className="estrella-globo">{mensaje}</p>}
    </div>
  )
}
