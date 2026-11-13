// Textos y escalas del panel «Mi progreso» (src/estado/progreso.ts).
import assert from 'node:assert/strict'
import { test } from 'node:test'
import * as p from '../src/estado/progreso.ts'

test('las fechas se leen en hora local, sin desfase de zona horaria', () => {
  assert.equal(p.fechaCorta('2026-11-02'), '2 nov')
  assert.equal(p.fechaHora('2026-11-06T09:05:00'), 'vie 6 nov · 9:05')
})

test('fecha relativa', () => {
  const hoy = new Date(2026, 10, 6, 8, 0)
  assert.equal(p.fechaRelativa('2026-11-06T07:59:00', hoy), 'hoy')
  assert.equal(p.fechaRelativa('2026-11-05T23:59:00', hoy), 'ayer')
  assert.equal(p.fechaRelativa('2026-11-02T10:00:00', hoy), 'hace 4 días')
  assert.equal(p.fechaRelativa('2026-10-20T10:00:00', hoy), '20 oct')
})

test('marcas del eje redondas y que cubren el máximo', () => {
  assert.deepEqual(p.marcasEje(0), [0, 1, 2, 3, 4])
  assert.deepEqual(p.marcasEje(7), [0, 2, 4, 6, 8])
  assert.deepEqual(p.marcasEje(18), [0, 5, 10, 15, 20])
  assert.deepEqual(p.marcasEje(95), [0, 30, 60, 90, 120])
  for (const m of [3, 11, 41, 250, 999]) {
    const marcas = p.marcasEje(m)
    assert.ok(marcas.at(-1)! >= m && marcas.length >= 3 && marcas.length <= 5, `${m}: ${marcas}`)
  }
})

test('textos de racha y frecuencia', () => {
  assert.equal(p.textoRacha(0).valor, '0 días')
  assert.equal(p.textoRacha(1).valor, '1 día')
  assert.deepEqual(p.textoRacha(4), { valor: '4 días', extra: 'seguidos' })
  assert.equal(p.textoFrecuencia(1, 1), 'En tu única sesión')
  assert.equal(p.textoFrecuencia(5, 5), 'En tus últimas 5 sesiones')
  assert.equal(p.textoFrecuencia(2, 5), 'En 2 de tus últimas 5 sesiones')
  assert.equal(p.textoMarca(25, 20, 'segundos'), '25 / 20 s')
})

test('tiempo acumulado sin parecer una hora del día', () => {
  assert.equal(p.duracionLarga(45), '45 s')
  assert.equal(p.duracionLarga(14 * 60 + 20), '14 min')
  assert.equal(p.duracionLarga(98 * 60), '1 h 38 min')
  assert.equal(p.duracionLarga(120 * 60), '2 h')
})

test('periodo de la semana y tramo comparado', () => {
  assert.equal(p.periodoSemana('2026-11-09'), '9 – 15 nov')
  assert.equal(p.periodoSemana('2026-10-27'), '27 oct – 2 nov')
  assert.equal(p.textoTramo(1), 'el lunes')
  assert.equal(p.textoTramo(4), 'de lunes a jueves')
  assert.equal(p.textoTramo(7), 'la semana entera')
  assert.equal(p.textoDiferencia(420), '+7 min')
  assert.equal(p.textoDiferencia(-185), '−3 min')
  assert.equal(p.textoDiferencia(20), 'lo mismo')
})

test('calendario: semanas de lunes a domingo e intensidad', () => {
  const nov = p.semanasDelMes(2026, 10)                 // 1 nov 2026 es domingo
  assert.equal(nov[0].filter((d) => d === null).length, 6)
  assert.equal(nov[0][6]?.getDate(), 1)
  assert.ok(nov.every((s) => s.length === 7))
  assert.equal(nov.flat().filter(Boolean).length, 30)
  assert.equal(p.isoDia(new Date(2026, 10, 3)), '2026-11-03')
  assert.equal(p.nivelActividad(0, 600), 0)
  assert.equal(p.nivelActividad(100, 600), 1)
  assert.equal(p.nivelActividad(300, 600), 2)
  assert.equal(p.nivelActividad(600, 600), 3)
  assert.equal(p.fechaLarga('2026-11-12'), 'jueves 12 de noviembre')
})

test('estado de la sesión según cómo terminó', () => {
  assert.equal(p.estadoSesion(true, 'completada').clave, 'completa')
  assert.equal(p.estadoSesion(false, 'usuaria').clave, 'antes')
  assert.equal(p.estadoSesion(false, 'fuente').clave, 'interrumpida')
  assert.equal(p.estadoSesion(false, 'cierre').clave, 'interrumpida')
  assert.equal(p.estadoSesion(false, null).clave, 'antes')          // registro sin motivo
  assert.equal(p.estadoSesion(true, null).clave, 'completa')
})
