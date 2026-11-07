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
