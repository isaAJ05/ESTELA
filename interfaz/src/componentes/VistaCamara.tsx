import { useEffect, useRef } from 'react'
import type { Punto } from '../bridge/tipos'
import { alFrame, useEstado } from '../estado/almacen'

const RASTRO = 6               // esqueletos anteriores que dejan estela
const VISIBLE = 0.5            // visibilidad mínima para dibujar una articulación
// El frame llega a 640 px: más resolución en el lienzo solo cuesta dibujo.
const DPR_MAX = 1.5

function color(nombre: string, respaldo: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(nombre).trim() || respaldo
}

/**
 * Frame de la cámara con el esqueleto encima. No pasa por React: se suscribe
 * a los frames del almacén y dibuja en requestAnimationFrame, siempre el último.
 */
export function VistaCamara() {
  const lienzo = useRef<HTMLCanvasElement>(null)
  const conexiones = useEstado((s) => s.info?.conexiones ?? null)
  const espejo = useEstado((s) => s.info?.espejo ?? true)

  useEffect(() => {
    const canvas = lienzo.current
    if (!canvas || !conexiones) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const reducido = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const linea = color('--color-violeta-suave', '#a99dff')
    const articulacion = color('--color-amarillo', '#ffc94d')
    const fondo = color('--color-superficie', '#171522')

    let imagen: HTMLImageElement | null = null
    let puntos: Punto[] | null = null
    const rastro: Punto[][] = []
    let pendiente = true
    let pedido = 0
    let raf = 0

    const ajustar = () => {
      const r = canvas.getBoundingClientRect()
      const dpr = Math.min(window.devicePixelRatio || 1, DPR_MAX)
      canvas.width = Math.max(1, Math.round(r.width * dpr))
      canvas.height = Math.max(1, Math.round(r.height * dpr))
      pendiente = true
    }
    const observador = new ResizeObserver(ajustar)
    observador.observe(canvas)
    ajustar()

    const esqueleto = (pts: Punto[], x0: number, y0: number, w: number, h: number, alfa: number, grosor: number) => {
      const px = (p: Punto) => x0 + (espejo ? 1 - p[0] : p[0]) * w
      const py = (p: Punto) => y0 + p[1] * h
      ctx.globalAlpha = alfa
      ctx.lineCap = 'round'
      ctx.strokeStyle = linea
      ctx.lineWidth = grosor
      for (const [a, b] of conexiones) {
        const pa = pts[a], pb = pts[b]
        if (!pa || !pb) continue
        ctx.globalAlpha = alfa * (pa[2] > VISIBLE && pb[2] > VISIBLE ? 1 : 0.25)
        ctx.beginPath()
        ctx.moveTo(px(pa), py(pa))
        ctx.lineTo(px(pb), py(pb))
        ctx.stroke()
      }
    }

    const dibujar = () => {
      raf = requestAnimationFrame(dibujar)
      if (!pendiente) return
      pendiente = false
      const W = canvas.width, H = canvas.height
      ctx.setTransform(1, 0, 0, 1, 0, 0)
      ctx.clearRect(0, 0, W, H)
      // encaja el frame sin recortarlo (el cuerpo entero debe verse)
      const aspecto = imagen ? imagen.naturalWidth / imagen.naturalHeight : 16 / 9
      const w = Math.min(W, H * aspecto), h = w / aspecto
      const x0 = (W - w) / 2, y0 = (H - h) / 2
      ctx.globalAlpha = 1
      if (imagen) {
        ctx.save()
        if (espejo) { ctx.translate(x0 + w, y0); ctx.scale(-1, 1) } else ctx.translate(x0, y0)
        ctx.drawImage(imagen, 0, 0, w, h)
        ctx.restore()
        ctx.fillStyle = 'rgba(14, 13, 22, 0.25)'      // baja el vídeo para que resalte el esqueleto
        ctx.fillRect(x0, y0, w, h)
      } else {
        ctx.fillStyle = fondo
        ctx.fillRect(x0, y0, w, h)
      }
      if (!puntos) return
      const grosor = Math.max(3, h / 140)
      if (!reducido) {
        rastro.forEach((viejo, k) => esqueleto(viejo, x0, y0, w, h, 0.07 * (k + 1), grosor * 0.8))
      }
      // brillo: un trazo ancho y translúcido debajo (shadowBlur es caro sin GPU)
      esqueleto(puntos, x0, y0, w, h, 0.22, grosor * 3)
      esqueleto(puntos, x0, y0, w, h, 1, grosor)
      ctx.fillStyle = articulacion
      const indices = new Set(conexiones.flat())
      for (const i of indices) {
        const p = puntos[i]
        if (!p) continue
        ctx.globalAlpha = p[2] > VISIBLE ? 1 : 0.3
        ctx.beginPath()
        ctx.arc(x0 + (espejo ? 1 - p[0] : p[0]) * w, y0 + p[1] * h, grosor * 1.2, 0, 2 * Math.PI)
        ctx.fill()
      }
      ctx.globalAlpha = 1
    }
    raf = requestAnimationFrame(dibujar)

    const quitar = alFrame(({ jpeg, sesion }) => {
      const nuevos = sesion?.puntos ?? null
      const aplicar = (img: HTMLImageElement | null) => {
        if (puntos && nuevos) {
          rastro.push(puntos)
          if (rastro.length > RASTRO) rastro.shift()
        } else if (!nuevos) rastro.length = 0
        imagen = img
        puntos = nuevos
        pendiente = true
      }
      if (!jpeg) return aplicar(null)
      const n = ++pedido
      const img = new Image()
      img.onload = () => { if (n === pedido) aplicar(img) }      // descarta frames viejos
      img.src = `data:image/jpeg;base64,${jpeg}`
    })

    return () => {
      quitar()
      observador.disconnect()
      cancelAnimationFrame(raf)
    }
  }, [conexiones, espejo])

  return <canvas ref={lienzo} className="vista-camara" aria-label="Vista de la cámara con tu esqueleto" role="img" />
}

/** Esqueleto de referencia en pequeño (capacidad «guia»). */
export function GuiaAnimada({ puntos }: { puntos: Punto[] }) {
  const conexiones = useEstado((s) => s.info?.conexiones ?? [])
  return (
    <svg className="guia-animada" viewBox="0 0 1 1" preserveAspectRatio="xMidYMid meet" aria-label="Movimiento de referencia" role="img">
      {conexiones.map(([a, b]) => puntos[a] && puntos[b] && (
        <line key={`${a}-${b}`} x1={puntos[a][0]} y1={puntos[a][1]} x2={puntos[b][0]} y2={puntos[b][1]} />
      ))}
    </svg>
  )
}
