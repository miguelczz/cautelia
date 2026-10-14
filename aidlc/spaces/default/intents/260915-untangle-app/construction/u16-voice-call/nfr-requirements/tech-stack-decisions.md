# Decisiones de herramientas — U16 `voice-call`

**Ninguna dependencia nueva en el servidor.** FastAPI ya sirve WebSockets con
Starlette, que ya está en el manifiesto. `websockets` ya es dependencia de
ejecución desde U15 y esta unidad no la necesita: la usa el adaptador, no el
canal.

**Ninguna dependencia nueva en el navegador.** `AudioWorklet`, `getUserMedia` y
`WebSocket` son API del navegador. La alternativa era una librería de cliente de
voz, que habría traído su propio transporte y su propio formato: exactamente lo
que D1 decidió no hacer.

| Pieza | Con qué | Por qué |
| --- | --- | --- |
| Transporte navegador ↔ servidor | WebSocket del mismo origen, PCM16LE mono 24 kHz | D1; cierra C-29 |
| Captura y reproducción | `AudioWorklet` en un módulo propio | API estándar; el hilo de audio no compite con React |
| Transcripción y síntesis | Los puertos de C-16 que llenó U15 | No se toca nada de U15 |
| Turno | `handle_turn` de C-14 | El mismo grafo que el chat |
| Deletreo | `spell_for_readback` de U11 | Ya existía versionada y con pruebas |
| Reconocedor y síntesis simulados | Dobles propios de esta unidad | Todo se prueba sin gastar y sin red |

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| TECH-U16.1 | Pruebas de la unidad, incluidas las del transporte y las de la consola | **En verde en cada entrega** | `mise run test:u16` (tarea nueva) |
| TECH-U16.2 | Pruebas que abren una conexión de red real | **Cero** | La misma guardia que U15 dejó puesta |
| TECH-U16.3 | Contratos de importación de `untangle.voice` | **En verde**: sin LangGraph y sin SDK de proveedor | `mise run lint` |
| TECH-U16.4 | La llamada completa contra los proveedores reales, con una grabación inyectada | **Se oye y se mide**, por hito | Tarea nueva `mise run voice:call-live`, a mano |

## Los dobles, y por qué se escriben con cuidado

La forma de defecto que más ha costado en este proyecto es un doble más
permisivo que la pieza real: el chat estuvo sin atender a nadie con 2.363
pruebas en verde porque sus dobles aceptaban un turno sin caso donde la pieza
real lo rechazaba.

Esta unidad tiene dos dobles grandes —el reconocedor y la síntesis— y los dos
son fáciles de escribir mal, porque el reconocedor real entrega parciales
desordenados, con confianza nula a veces, y la síntesis real tarda. Tres reglas:

1. **Los dobles heredan de los mismos `Protocol` de C-16**, para que el
   comprobador de tipos los compare con la pieza real.
2. **El doble del reconocedor entrega un guion de tiempos**, con parciales,
   finales y silencios, y no un texto de una vez. Un doble que devuelve el
   transcrito completo de golpe no puede probar la detección de turno, que es la
   mitad de esta unidad.
3. **Al menos una prueba recorre la costura con la pieza real**: la del
   transporte corre contra el adaptador de verdad con su respuesta grabada, que
   es lo que U15 ya dejó montado.

## El comando de hito

`voice:call-live` es el equivalente de `voice:contract-live` de U15: corre a
mano, gasta, y no entra en `verify.sh`. Inyecta una grabación por el transporte
como si viniera del navegador, mide los cuatro eventos de latencia y publica las
dos variantes del fin del habla que pide AC1.23.5.

No corre sin que Miguel lo diga. Las metas NFR1, NFR2 y NFR3 son de hito, y
hasta que se midan se reportan **no medidas** con esa causa, nunca en verde.

## Sources

- `../functional-design/functional-design-questions.md` — D1 a D8
- `../functional-design/rules.md` — las 38 reglas
- `../../../inception/contract-design/contract-summary.md` — C-08, C-14, C-16, C-29
- `../../u15-speech-providers/code-generation/code-summary.md` — los puertos ya llenos y la guardia de red
- `docs/reference/como-se-revisa-el-codigo.md` — la forma 12, los dobles

## Assumptions & Open Questions

None.
