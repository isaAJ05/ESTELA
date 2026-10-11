import type { Bridge } from './bridge/tipos'
import { useEstado } from './estado/almacen'
import { Inicio } from './pantallas/Inicio'
import { Resumen } from './pantallas/Resumen'
import { Sesion } from './pantallas/Sesion'

/** La pantalla la decide la fase que manda Python; la interfaz no lleva su propio flujo. */
export function App({ bridge }: { bridge: Bridge }) {
  const fase = useEstado((s) => s.estado?.fase ?? 'inicio')
  if (fase === 'sesion') return <Sesion bridge={bridge} />
  if (fase === 'resumen') return <Resumen bridge={bridge} />
  return <Inicio bridge={bridge} />          // inicio, preparando y error
}

export function SinConexion() {
  return (
    <main className="pantalla pantalla-centro">
      <div className="tarjeta">
        <h2>Abre ESTELA desde Python</h2>
        <p>Esta interfaz funciona dentro de la ventana de la aplicación: <code>python -m estela</code>.</p>
        <p>Para probarla en el navegador sin cámara, añade <code>?simulado</code> a la dirección.</p>
      </div>
    </main>
  )
}
