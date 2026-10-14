# Revisión de la tanda 1 — U16 `voice-call`

"El transporte, la sesión y su tabla". Cinco módulos, una migración y 55 pruebas.

## 1. Lo que se rompió, y qué se cayó

Siete roturas, una por regla que la tanda dice cumplir. **Las siete tumbaron una
prueba de conducta**, ninguna un `ImportError`. Todas deshechas después.

| Regla | Qué se rompió | Qué se cayó |
| --- | --- | --- |
| BR1.3 | `to_client` devuelve `{"type": "unknown"}` en vez de fallar ante un cuadro que no conoce | `test_algo_que_no_es_un_cuadro_del_servidor_no_se_serializa` |
| BR1.4 | El cuadro `auth` acepta un token vacío | `test_lo_que_no_es_un_cuadro_conocido_se_rechaza`, 3 casos |
| BR1.4 | `issue` mete la clave de firma dentro del token | 5 pruebas, entre ellas `test_el_token_no_lleva_la_clave_ni_el_navegador` |
| BR1.5 | Un socket sin cuadro de autenticación se admite | `test_sin_token_no_se_abre` (2 casos) y la de las cuatro formas |
| BR1.5 | El token de otra llamada abre esta | `test_el_token_de_otra_llamada_no_abre_esta` y la de las cuatro formas |
| BR1.6 | `end_call` pierde la guarda `state <> 'ended'` | `test_terminar_dos_veces_no_pisa_el_motivo` |
| BR6.3 | La retoma deja de filtrar por `visitor_key_digest` | `test_el_caso_cortado_de_otro_navegador_no_se_ofrece` (criterio `[bloquea]`) |
| BR7.3 | Se quita `CALL_SESSION_PURGER` del registro | 3 pruebas de U2, entre ellas la del inventario escrito a mano |
| Llave compuesta | La llave foránea pasa a ser simple, como la de U10 antes de su parche | `test_la_llave_foranea_es_compuesta_y_no_cruza_aseguradoras` |

La rotura de BR6.3 se hizo como ocurriría de verdad: quitando el filtro de la
consulta y dejando el parámetro en la firma. Una rotura que también borrara el
parámetro habría fallado por otra razón y no habría probado nada.

## 2. Lo que encontró el proyecto antes que yo

**El guardián de borrado de U2 se puso rojo en cuanto apareció la tabla.** La
migración marca `call_session` como dato de visitante, y hay una prueba que le
pregunta al catálogo de la base qué tablas llevan esa marca y falla si alguna no
tiene dueño en el registro de purgadores:

```
estas tablas guardan datos de visitante y nadie se comprometio a borrarlas: ['call_session']
```

Es BR7.3 y UG-3 funcionando, no un fallo. Se escribió `voice/purge.py`.

**Por qué hace falta ese purgador aunque exista la cascada.** `call_session`
cuelga del caso con `ON DELETE CASCADE`, así que borrar el caso se lleva la
llamada. Lo que la cascada no alcanza es **la llamada que nunca llegó a tener
caso**: micrófono concedido, socket abierto y la persona que cuelga antes de
decir nada. Esas filas llevan el resumen de un navegador y se quedarían para
siempre. Está escrito en la cabecera del módulo.

**El chequeo de contenido encontró dos mensajes de error míos** y tenía razón por
una vía que no esperaba: eran una copia del mensaje de U2 sobre la clave de
firma. La solución no fue reescribirlos para esquivar el chequeo, sino **dejar de
duplicarlos**: `visitor_access.require_signing_key` pasa a ser pública —U16 es su
segundo consumidor— y `voice/tokens.py` la llama. Un sitio menos donde decir qué
mide una clave válida.

## 3. Decisiones tomadas al escribir

1. **`test:u16` se creó en esta tanda y no en la sexta**, como decía el plan. No
   cuesta nada y las pruebas ya existen. Es la única desviación del plan.
2. **`verify()` se partió en dos** (`_motivo` y `verify`) porque el linter marcó
   siete caminos de retorno donde admite seis. La forma resultante es mejor: el
   motivo exacto vive en una función y lo que sale del servidor en la otra, que
   es justo la separación que BR1.5 pide.
3. **Firma valida y vencimiento ilegible se juntan en un solo rechazo.** No se
   puede dar sin la clave, pero un `int()` que revienta convertiría un caso
   imposible en un 500.
4. **`find_resumable` no admite un parámetro de póliza**, y hay una prueba que
   comprueba su firma. La regla vive en el tipo y no solo en la consulta: sin
   parámetro, nadie la pasa por descuido.
5. **Una supresión del linter, con su razón al lado**: `S106` en la prueba del
   cuadro `auth`, porque `"t-1"` no es una credencial sino el cuadro que se está
   probando.

## 4. Lo que no se debilitó

Ninguna prueba existente se relajó ni se borró. El único cambio a una prueba
ajena fue **añadir** `call_session` al inventario escrito a mano del registro de
purgadores de U2, que es lo que esa prueba existe para exigir. Ningún umbral,
ningún piso de cobertura, ninguna compuerta saltada.

## 5. Formas del catálogo que se revisaron contra este diff

- **Forma 12, el doble más permisivo que la pieza real.** Esta tanda **no tiene
  dobles**: todo lo que toca la base corre contra la base efímera y el token se
  prueba con la primitiva de verdad. Los dos dobles grandes de la unidad —el
  reconocedor y la síntesis— llegan en la tanda 2, y sus tres reglas están en
  `unit-test-instructions.md`.
- **La aserción que comprueba ausencia en vez de identidad.** Apareció una: la
  prueba de la cascada comprobaba solo que después no quedaba ninguna fila, lo
  que habría pasado igual si la llamada nunca se hubiera creado. Se corrigió para
  que afirme primero que la fila está, con su identificador.
- **La aserción que no puede distinguir.** La prueba de las cuatro formas de
  token malo compara además que los cuatro motivos internos sean **distintos
  entre sí**: sin eso, un módulo que devolviera siempre el mismo motivo pasaría.

## 6. Estado

`mise run test:u16`: 55 pruebas en verde (35 unitarias, 20 de integración).
`mise run migrate:check`: sube, baja y vuelve a subir; aislamiento sobre 30
tablas. `mise run verify:rapido`: en verde.
