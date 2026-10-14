# Requisitos de escalabilidad — U13 `chat`

La escala real de este proyecto es modesta y conviene decirlo con números en vez de
con adjetivos: un proceso único en hospedaje gratuito, con visitantes que llegan de un
enlace en una landing y en un perfil de LinkedIn. Lo que esta unidad tiene que
garantizar no es escalar: es **degradar de forma honesta** cuando la escala se pase, y
que pasarse no cueste dinero.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| SCALE-U13.1 | Conversaciones simultáneas con streaming abierto que el proceso sostiene sin degradar NFR4 | **20 o más**, medido y publicado | Tarea nueva `mise run test:u13`, prueba de carga acotada |
| SCALE-U13.2 | Conexiones de streaming huérfanas tras cerrar la pestaña, un minuto después | **Exactamente 0** | Tarea nueva `mise run test:u13` |
| SCALE-U13.3 | Consultas a la base por mensaje entrante | **3 o menos**: la conversación, el contador de origen y el del día | Tarea nueva `mise run test:u13` |
| SCALE-U13.4 | Filas de `chat_session` que sobreviven al reinicio nocturno | **Exactamente 0** | Tarea nueva `mise run test:u13` |

## Por qué veinte y no doscientas

Veinte conversaciones simultáneas es más de lo que esta demostración va a ver en su
vida, y es un número que se puede **medir de verdad** en una prueba acotada en la
máquina de desarrollo. Doscientas necesitarían un entorno que no existe y una
herramienta de carga que nadie va a mantener; el número quedaría escrito sin que nadie
lo hubiera comprobado nunca, que es peor que no tenerlo.

Si algún día la demostración recibe más, lo que la protege no es este número: son los
límites de BR3.1, que rechazan antes de gastar.

## Por qué las conexiones huérfanas son cero

Una conexión de streaming que nadie cerró mantiene vivo un turno que nadie va a leer,
y en el ritmo de fondo eso significa trabajo que se sigue pagando. Es el modo de fallo
propio de SSE y el que no se ve en las pruebas normales, porque en una prueba la
conexión siempre se cierra bien.

## Lo que esta unidad no escala y no finge escalar

- **No hay más de un proceso.** El trabajo de fondo son tareas asíncronas del mismo
  proceso, sin broker (ADR-004), y el arrendamiento con latido de U12 es lo que
  permite que un reinicio retome lo que quedó a medias.
- **No hay caché de respuestas.** Dos personas que pregunten lo mismo consumen dos
  turnos: cachear respuestas de cobertura entre conversaciones sería la forma más
  directa de mezclar datos entre visitantes, que es justo lo que las compuertas duras
  de esta unidad prohíben.
- **El tope de gasto no es un asunto de escala.** El chat corre en el plan gratuito;
  lo que lo protege es el límite de mensajes y la clave propia con su tope en el
  proveedor (BR3.3).
