import { useEffect, useRef } from 'react'
import type { EstadoSesion, Punto, Severidad } from '../bridge/tipos'
import { alFrame, useEstado } from '../estado/almacen'

const VISIBLE = 0.5            // visibilidad mínima para dibujar una articulación
// El frame llega a 640 px: más resolución en el lienzo solo cuesta dibujo.
const DPR_MAX = 1.5
// Cuánto dura resaltada la parte del cuerpo de una corrección (igual que la banda del mensaje).
const RESALTE_MS = 4500

function color(nombre: string, respaldo: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(nombre).trim() || respaldo
}

/**
 * Frame de la cámara con el esqueleto encima. No pasa por React: se suscribe
 * a los frames del almacén y dibuja en requestAnimationFrame, siempre el último.
 */
// Nombres legibles de los ángulos importantes que no están en una articulación.
const NOMBRE_ANGULO: Record<string, string> = {
  tronco_inclinacion: 'Tronco',
  inclinacion_lateral: 'Inclinación lateral',
  oblicuidad_pelvis: 'Pelvis',
  abduccion_cadera_izq: 'Abducción cadera izq.',
  abduccion_cadera_der: 'Abducción cadera der.',
  cabeza_adelantada: 'Cabeza',
}

// Hacia dónde corregir (`Direccion` del backend), en corto para la etiqueta.
const FLECHA: Record<string, string> = {
  mas_flexion: 'dobla más', menos_flexion: 'estira', subir: 'sube', bajar: 'baja',
  abrir: 'abre', cerrar: 'cierra', adelante: 'adelante', atras: 'atrás',
  alargar: 'alarga', acortar: 'acorta',
}

export function VistaCamara({ mostrarAngulos = false }: { mostrarAngulos?: boolean }) {
  const lienzo = useRef<HTMLCanvasElement>(null)
  // en una ref para que activar o quitar los ángulos no reinicie el lienzo
  const verAngulos = useRef(mostrarAngulos)
  const repintar = useRef<() => void>(() => {})
  useEffect(() => { verAngulos.current = mostrarAngulos; repintar.current() }, [mostrarAngulos])
  const conexiones = useEstado((s) => s.info?.conexiones ?? null)
  const espejo = useEstado((s) => s.info?.espejo ?? true)

  useEffect(() => {
    const canvas = lienzo.current
    if (!canvas || !conexiones) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const linea = color('--color-violeta-suave', '#a99dff')
    const articulacion = color('--color-amarillo', '#ffc94d')
    const fondo = color('--color-superficie', '#171522')
    const colorSeveridad: Record<Severidad, string> = {
      leve: articulacion,
      moderada: color('--color-ambar', '#f4a340'),
      alta: color('--color-peligro', '#e98591'),
    }

    let imagen: HTMLImageElement | null = null
    let puntos: Punto[] | null = null
    let angulos: EstadoSesion['angulos'] = null
    let pendiente = true
    repintar.current = () => { pendiente = true }
    // articulaciones de la última corrección y hasta cuándo se resaltan
    let mensajes = -1
    let resalte: { puntos: Set<number>; color: string; hasta: number; angulos: Set<string>; detalle: string } | null = null
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

    const resaltar = (pts: Punto[], x0: number, y0: number, w: number, h: number, grosor: number) => {
      if (!resalte) return
      if (performance.now() > resalte.hasta) { resalte = null; return }
      const { puntos: indices, color: tono } = resalte
      const px = (p: Punto) => x0 + (espejo ? 1 - p[0] : p[0]) * w
      const py = (p: Punto) => y0 + p[1] * h
      ctx.strokeStyle = tono
      ctx.fillStyle = tono
      for (const [a, b] of conexiones) {
        const pa = pts[a], pb = pts[b]
        if (!pa || !pb || !indices.has(a) || !indices.has(b)) continue
        ctx.globalAlpha = 1
        ctx.lineWidth = grosor * 1.6
        ctx.beginPath()
        ctx.moveTo(px(pa), py(pa))
        ctx.lineTo(px(pb), py(pb))
        ctx.stroke()
      }
      for (const i of indices) {
        const p = pts[i]
        if (!p || p[2] <= VISIBLE) continue
        ctx.globalAlpha = 0.3
        ctx.beginPath()
        ctx.arc(px(p), py(p), grosor * 4, 0, 2 * Math.PI)
        ctx.fill()
        ctx.globalAlpha = 1
        ctx.beginPath()
        ctx.arc(px(p), py(p), grosor * 2, 0, 2 * Math.PI)
        ctx.fill()
      }
      ctx.globalAlpha = 1
    }

    // ángulo junto a cada articulación: los importantes del ejercicio, grandes
    // y en amarillo; el resto, pequeños y tenues. Los importantes que no están
    // en una articulación (tronco, pelvis…) van en una lista en una esquina.
    // Mientras dura una corrección, el ángulo que no se cumple va en el color
    // de la gravedad, con un círculo y cuánto falta/sobra.
    const fallo = (nombre: string) =>
      resalte && performance.now() <= resalte.hasta && resalte.angulos.has(nombre) ? resalte : null
    const etiquetas = (pts: Punto[], x0: number, y0: number, w: number, h: number) => {
      if (!angulos) return
      // con los ángulos ocultos, solo se señala el que no se cumple
      const todos = verAngulos.current
      const base = Math.max(11, Math.round(h / 40))
      ctx.textBaseline = 'middle'
      ctx.lineJoin = 'round'
      ctx.strokeStyle = 'rgba(0, 0, 0, 0.85)'
      const texto = (t: string, x: number, y: number, tam: number, tono: string, alfa: number) => {
        ctx.globalAlpha = alfa
        ctx.font = `${tam > base ? 700 : 500} ${tam}px system-ui, sans-serif`
        ctx.lineWidth = Math.max(3, tam / 4)
        ctx.strokeText(t, x, y)
        ctx.fillStyle = tono
        ctx.fillText(t, x, y)
      }
      for (const a of angulos.articulaciones) {
        const p = a.indices.map((i) => pts[i]).filter(Boolean).sort((u, v) => v[2] - u[2])[0]
        if (!p || p[2] <= VISIBLE) continue
        const f = fallo(a.nombre)
        if (!f && !todos) continue
        const tam = f ? Math.round(base * 1.8) : a.importante ? Math.round(base * 1.5) : base
        const x = x0 + (espejo ? 1 - p[0] : p[0]) * w, y = y0 + p[1] * h
        if (f) {
          ctx.globalAlpha = 1
          ctx.strokeStyle = f.color
          ctx.lineWidth = Math.max(2, tam / 6)
          ctx.beginPath()
          ctx.arc(x, y, tam * 0.9, 0, 2 * Math.PI)
          ctx.stroke()
          ctx.strokeStyle = 'rgba(0, 0, 0, 0.85)'
        }
        texto(`${a.grados}°${f ? f.detalle : ''}`, x + tam * (f ? 1.1 : 0.6), y,
              tam, f ? f.color : a.importante ? articulacion : '#ffffff', f || a.importante ? 1 : 0.6)
      }
      const tam = Math.round(base * 1.3)
      const otros = angulos.otros.filter((a) => todos || fallo(a.nombre))
      otros.forEach((a, k) => {
        const f = fallo(a.nombre)
        texto(`${NOMBRE_ANGULO[a.nombre] ?? a.nombre} ${a.grados}°${f ? f.detalle : ''}`,
              x0 + tam * 0.6, y0 + h - tam * (1 + 1.4 * (otros.length - 1 - k)),
              f ? Math.round(tam * 1.15) : tam, f ? f.color : articulacion, 1)
      })
      ctx.globalAlpha = 1
    }

    const dibujar = () => {
      raf = requestAnimationFrame(dibujar)
      // el resalte se apaga solo aunque no lleguen frames nuevos
      if (resalte && performance.now() > resalte.hasta) pendiente = true
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
      resaltar(puntos, x0, y0, w, h, grosor)
      etiquetas(puntos, x0, y0, w, h)
      ctx.globalAlpha = 1
    }
    raf = requestAnimationFrame(dibujar)

    const quitar = alFrame(({ jpeg, sesion }) => {
      const nuevos = sesion?.puntos ?? null
      const fb = sesion?.feedback ?? null
      if (sesion && sesion.mensajesEmitidos !== mensajes) {
        // el primer estado recibido no resalta un mensaje que ya pasó
        const nuevo = mensajes >= 0
        mensajes = sesion.mensajesEmitidos
        resalte = nuevo && fb?.tipo === 'correccion' && fb.puntos.length > 0
          ? {
              puntos: new Set(fb.puntos), color: colorSeveridad[fb.severidad ?? 'leve'],
              hasta: performance.now() + RESALTE_MS, angulos: new Set(fb.angulos ?? []),
              detalle: [fb.magnitud ? `${Math.round(fb.magnitud)}° fuera` : '', fb.direccion ? FLECHA[fb.direccion] ?? '' : '']
                .filter(Boolean).map((t) => ` · ${t}`).join(''),
            }
          : null
      }
      if (!sesion) { mensajes = -1; resalte = null }
      const aplicar = (img: HTMLImageElement | null) => {
        imagen = img
        puntos = nuevos
        angulos = sesion?.angulos ?? null
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
      repintar.current = () => {}
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
