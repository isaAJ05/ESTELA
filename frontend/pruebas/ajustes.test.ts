// Ajustes de la usuaria (src/estado/ajustes.ts): lectura de lo guardado y tema visible.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { AJUSTES_POR_DEFECTO, cambiarVozDeSesion, leerAjustes, leerVoz, restaurarVoz, temaVisible } from '../src/estado/ajustes.ts'
import type { Bridge } from '../src/bridge/tipos.ts'

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

test('«Estela, silencio» vale solo por el resto de la sesión', () => {
  const pedidos: unknown[] = []
  const bridge = { configurar: async (a: unknown) => { pedidos.push(a) } } as unknown as Bridge
  assert.equal(leerVoz(), true)
  restaurarVoz(bridge)                               // sin orden hablada no hay nada que deshacer
  assert.deepEqual(pedidos, [])
  cambiarVozDeSesion(false, bridge)                  // «Estela, silencio»
  assert.equal(leerVoz(), false)
  cambiarVozDeSesion(true, bridge)                   // «Estela, háblame»
  cambiarVozDeSesion(false, bridge)
  restaurarVoz(bridge)                               // acaba la sesión: vuelve la preferencia
  assert.equal(leerVoz(), true)
  assert.deepEqual(pedidos, [{ voz: false }, { voz: true }, { voz: false }, { voz: true }])
  restaurarVoz(bridge)                               // y no se repite
  assert.equal(pedidos.length, 4)
})
