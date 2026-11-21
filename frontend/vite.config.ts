import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base './': la ventana carga dist/index.html con rutas relativas, sin servidor propio.
export default defineConfig({
  base: './',
  plugins: [react()],
  build: { outDir: 'dist', emptyOutDir: true, assetsInlineLimit: 0 },
})
