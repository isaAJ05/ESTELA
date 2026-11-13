// Ayudas sin React de los perfiles (src/estado/perfiles.ts).
import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { Perfil } from '../src/bridge/tipos.ts'
import * as p from '../src/estado/perfiles.ts'

const ana: Perfil = { id: 'pa', nombre: 'Ana María', color: 'rosa', metaSemanal: 3, creado: null }

test('iniciales del avatar', () => {
  assert.equal(p.iniciales('Ana María'), 'AM')
  assert.equal(p.iniciales('  luis  '), 'L')
  assert.equal(p.iniciales('María José de la Cruz'), 'MC')
  assert.equal(p.iniciales('Ñandú'), 'Ñ')
  assert.equal(p.iniciales('   '), '?')
})

test('aviso del nombre mientras se escribe', () => {
  assert.equal(p.problemaNombre('  ', [], 30), 'Escribe un nombre o apodo.')
  assert.equal(p.problemaNombre('x'.repeat(31), [], 30), 'El nombre puede tener hasta 30 caracteres.')
  assert.equal(p.problemaNombre('ana   maría', [ana], 30), 'Ya hay un perfil con ese nombre.')
  assert.equal(p.problemaNombre('Luis', [ana], 30), null)
})

test('aviso del nombre de una rutina guardada', () => {
  const mananas = { id: 'ra', nombre: 'Mañanas rápidas', pasos: [{ skillId: 'plancha', objetivo: 30 }] }
  assert.equal(p.problemaNombreRutina('  ', [], 40), 'Ponle un nombre a la rutina.')
  assert.equal(p.problemaNombreRutina('x'.repeat(41), [], 40), 'El nombre puede tener hasta 40 caracteres.')
  assert.equal(p.problemaNombreRutina('MAÑANAS   rápidas', [mananas], 40), 'Ya tienes una rutina con ese nombre.')
  assert.equal(p.problemaNombreRutina('Piernas', [mananas], 40), null)
})

test('perfil activo y texto de la meta', () => {
  const estado = { perfiles: [ana], activo: 'pa', elegido: true, colores: [], maxPerfiles: 8, maxNombre: 30, meta: [1, 7] as [number, number] }
  assert.equal(p.perfilActivo(estado)?.nombre, 'Ana María')
  assert.equal(p.perfilActivo({ ...estado, activo: null }), null)
  assert.equal(p.perfilActivo(null), null)
  assert.equal(p.textoMeta(null), 'Sin meta semanal')
  assert.equal(p.textoMeta(1), '1 día por semana')
  assert.equal(p.textoMeta(4), '4 días por semana')
})
