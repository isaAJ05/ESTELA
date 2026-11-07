import '@fontsource-variable/manrope'
import './estilos/tokens.css'
import './estilos/base.css'
import './estilos/pantallas.css'
import './estilos/rutina.css'
import './estilos/progreso.css'
import './estilos/perfiles.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App, SinConexion } from './App'
import { conectar } from './bridge'
import { aplicarAjustes, sincronizarVoz } from './estado/ajustes'
import { arrancar } from './estado/almacen'
import { cargarPerfiles } from './estado/perfiles'

aplicarAjustes()

const raiz = createRoot(document.getElementById('raiz')!)

conectar().then((bridge) => {
  if (!bridge) {
    raiz.render(<SinConexion />)
    return
  }
  sincronizarVoz(bridge)
  void arrancar(bridge)
  void cargarPerfiles(bridge)
  raiz.render(<StrictMode><App bridge={bridge} /></StrictMode>)
})
