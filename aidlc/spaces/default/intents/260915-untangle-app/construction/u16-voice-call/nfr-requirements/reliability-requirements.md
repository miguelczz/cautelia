# Requisitos de fiabilidad — U16 `voice-call`

Una llamada es la superficie más frágil del aplicativo: depende de dos
proveedores externos en tiempo real, de una conexión que puede caerse a mitad de
una frase y de un micrófono que puede dejar de entregar muestras sin avisar.

La forma de esta unidad ante el fallo es una sola: **la llamada nunca queda
abierta en silencio**. Algo se dice, o se termina con su motivo.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| REL-U16.1 | Llamadas que terminan sin motivo del conjunto cerrado | **Cero** | Tarea nueva `mise run test:u16` |
| REL-U16.2 | Casos que quedan sin estado tras un corte | **Cero** | Tarea nueva `mise run test:u16`, cortando el socket en cada fase |
| REL-U16.3 | Retomas que vuelven a preguntar un campo ya confirmado | **Cero** | Tarea nueva `mise run test:u16`; por hito, AC1.27.6 sobre DS-5 |
| REL-U16.4 | Fallos del reconocedor o de la síntesis que dejan la llamada muda | **Cero**: se dice la frase de degradación y se sigue o se termina | Tarea nueva `mise run test:u16` con los cuatro errores de la taxonomía |
| REL-U16.5 | Recuperación tras interrupción sin perder estado (NFR3) | **> 90 %** | Comando de hito sobre DS-5 |

## Los cuatro errores del proveedor, dichos en voz alta

La taxonomía cerrada de la frontera ya existe —`timeout`, `rate_limited`,
`unavailable`, `invalid_response`— y los adaptadores de U15 la traducen. Lo que
esta unidad añade es qué se **oye** en cada caso, y la respuesta es la misma en
los cuatro: la frase de degradación del catálogo, por el punto único de salida, y
la decisión de seguir o terminar según qué se rompió.

| Qué se rompió | Qué pasa |
| --- | --- |
| La síntesis | La llamada termina con `error` y la consola dice por qué; la transcripción queda |
| El reconocedor | La agente lo dice y pide volver a intentar; a la segunda, termina |
| El modelo | Ya está resuelto aguas arriba: `TurnError` llega por C-14 y se habla como cualquier evento |
| La base | La llamada termina con `error`; el caso es lo que quedó escrito antes |

Ningún nodo captura su propio fallo para seguir adelante: esa regla del proyecto
vale igual aquí, y el camino del turno de voz no la esquiva porque tenga prisa.

## El corte no es un final

Un socket que se cierra sin cuadro de colgar deja el caso `esperando al
asegurado` con lo confirmado y con `resume_until` (BR6.1). Eso es lo que hace
posible REL-U16.3, y la prueba corta la conexión **en cada fase** —durante la
apertura, en mitad de un turno de la persona, en mitad de una respuesta de la
agente, entre turnos— porque las cuatro dejan el estado en sitios distintos.

## Lo que degrada y lo que corta

- **Voz apagada en la configuración de la aseguradora**: la disponibilidad lo
  dice antes de pedir el micrófono, con su motivo, y el chat sigue vivo. Ya está
  construido en U15 (BR2.2 de aquella unidad); esta unidad lo muestra.
- **Duración máxima agotada**: la llamada termina con `max_duration`. Hoy el
  valor sale de la configuración; los carriles públicos son de U17.
- **Tercer silencio**: termina con `silence` y el caso espera al asegurado.

## Lo que no se construye aquí

Reintentos automáticos de la llamada. Si la conexión se cae, la persona vuelve a
llamar y la retoma la encuentra: reconectar solo el socket por debajo, sin que se
note, suena bien y es exactamente donde se pierden turnos a medio confirmar.
