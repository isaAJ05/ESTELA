// Lógica de la rutina que arma la usuaria (src/estado/rutina.ts).
// Se corre con `npm test` (runner de Node, sin dependencias: Node ≥ 22.6).
import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { EjercicioCatalogo } from '../src/bridge/tipos.ts'
import * as r from '../src/estado/rutina.ts'

const ej = (skillId: string, unidad: 'repeticiones' | 'segundos', objetivo: number): EjercicioCatalogo => ({
  skillId, nombre: skillId, orientacion: null, unidad, objetivo, guia: null, descripcion: null,
  conteo: unidad === 'segundos' ? 'isometrico' : 'ciclo',
  minimo: unidad === 'segundos' ? 5 : 1, maximo: unidad === 'segundos' ? 180 : 50,
})
const JJ = ej('jumping_jacks', 'repeticiones', 10)
const MARCHA = ej('marcha_rodillas', 'repeticiones', 16)
const PLANCHA = ej('plancha', 'segundos', 20)
const CAT = [JJ, MARCHA, PLANCHA]

test('un solo ejercicio con su objetivo', () => {
  const sel = r.fijarObjetivo(r.alternar([], MARCHA), 'marcha_rodillas', 8)
  assert.deepEqual(sel, [{ skillId: 'marcha_rodillas', objetivo: 8 }])
  assert.deepEqual(r.problemas(sel, CAT), [])
})

test('varios ejercicios conservan orden, unidad y objetivo', () => {
  let sel = r.alternar([], MARCHA)
  sel = r.fijarObjetivo(r.alternar(sel, PLANCHA), 'plancha', 30)
  assert.deepEqual(r.planDe(sel, CAT).map((p) => [p.skillId, p.unidad, p.objetivo]),
    [['marcha_rodillas', 'repeticiones', 16], ['plancha', 'segundos', 30]])
})

test('reordenar respeta los bordes', () => {
  const sel = [{ skillId: 'marcha_rodillas', objetivo: 8 }, { skillId: 'plancha', objetivo: 30 }]
  assert.deepEqual(r.mover(sel, 1, -1).map((p) => p.skillId), ['plancha', 'marcha_rodillas'])
  assert.equal(r.mover(sel, 0, -1), sel)
  assert.equal(r.mover(sel, 1, 1), sel)
})

test('deseleccionar y rutina vacía', () => {
  const sel = r.alternar(r.alternar([], JJ), JJ)
  assert.deepEqual(sel, [])
  assert.deepEqual(r.problemas(sel, CAT), ['Elige al menos un ejercicio para empezar.'])
})

test('objetivos inválidos se rechazan sin redondear', () => {
  for (const t of ['', '  ', '-3', '0', '8.5', '8,5', 'abc', '51', '1e2']) {
    assert.equal(r.leerObjetivo(t, JJ).ok, false, `debería rechazar «${t}»`)
  }
  assert.equal(r.leerObjetivo('4', PLANCHA).ok, false)
  assert.deepEqual(r.leerObjetivo(' 15 ', JJ), { ok: true, valor: 15 })
  assert.equal(r.problemas([{ skillId: 'plancha', objetivo: 2 }], CAT).length, 1)
  assert.equal(r.problemas([{ skillId: 'inventado', objetivo: 2 }], CAT).length, 1)
})

test('stepper: segundos de 5 en 5 y dentro de los límites', () => {
  assert.equal(r.pasoDe('segundos'), 5)
  assert.equal(r.pasoDe('repeticiones'), 1)
  assert.equal(r.limitar(999, JJ), 50)
  assert.equal(r.limitar(0, PLANCHA), 5)
})

test('estimación de duración', () => {
  // 8 rep × 3 s + 30 s + 2 transiciones × 10 s
  assert.equal(r.estimarSegundos([{ skillId: 'marcha_rodillas', objetivo: 8 }, { skillId: 'plancha', objetivo: 30 }], CAT), 74)
})
