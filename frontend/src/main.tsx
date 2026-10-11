import '@fontsource-variable/manrope'
import './estilos/tokens.css'
import './estilos/base.css'
import './estilos/pantallas.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App, SinConexion } from './App'
import { conectar } from './bridge'
import { arrancar } from './estado/almacen'

const raiz = createRoot(document.getElementById('raiz')!)

conectar().then((bridge) => {
  if (!bridge) {
    raiz.render(<SinConexion />)
    return
  }
  void arrancar(bridge)
  raiz.render(<StrictMode><App bridge={bridge} /></StrictMode>)
})
