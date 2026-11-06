// Ajustes de la usuaria (src/estado/ajustes.ts): lectura de lo guardado y tema visible.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { AJUSTES_POR_DEFECTO, leerAjustes, temaVisible } from '../src/estado/ajustes.ts'

test('sin nada guardado o corrupto: valores por defecto', () => {
  assert.deepEqual(leerAjustes(null), AJUSTES_POR_DEFECTO)
  assert.deepEqual(leerAjustes('{no es json'), AJUSTES_POR_DEFECTO)
  assert.deepEqual(leerAjustes('null'), AJUSTES_POR_DEFECTO)
})

test('se conserva lo válido y se descarta lo desconocido', () => {
  assert.deepEqual(leerAjustes('{"tema":"claro","voz":false,"texto":"grande"}'),
    { tema: 'claro', voz: false, texto: 'grande', reconocer: false })
  assert.deepEqual(leerAjustes('{"tema":"rosa","voz":"no","texto":42}'), AJUSTES_POR_DEFECTO)
})

test('el reconocimiento del ejercicio siempre empieza desactivado', () => {
  assert.equal(AJUSTES_POR_DEFECTO.reconocer, false)
  assert.equal(leerAjustes('{"reconocer":true}').reconocer, false)
})

test('«sistema» sigue al sistema operativo', () => {
  assert.equal(temaVisible('sistema', true), 'oscuro')
  assert.equal(temaVisible('sistema', false), 'claro')
  assert.equal(temaVisible('claro', true), 'claro')
  assert.equal(temaVisible('oscuro', false), 'oscuro')
})
