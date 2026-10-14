# Requisitos de observabilidad — U16 `voice-call`

Una llamada no deja rastro por sí sola: se oye y se va. Lo que se pueda decir
después sobre ella es exactamente lo que esta unidad escriba mientras corre.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| OBS-U16.1 | Turnos sin evento de fin del habla o sin evento de primer audio | **Cero** | Tarea nueva `mise run test:u16` |
| OBS-U16.2 | Interrupciones sin marca de parada (AC1.24.5) | **Cero** | Tarea nueva `mise run test:u16` |
| OBS-U16.3 | Retomas sin marca de recuperación enlazada al caso original (AC1.27.6) | **Cero** | Tarea nueva `mise run test:u16` |
| OBS-U16.4 | Eventos de traza con texto sin redactar | **Cero** | `mise run redaction:report` y la tarea nueva `mise run test:u16` |
| OBS-U16.5 | Llamadas sin costo, latencia y tokens por nodo en la traza | **Cero** | Heredado de U5; la voz añade su consumo de audio |

## Los cuatro eventos de latencia (FR10.2)

Son los que el contrato C-29 ya prometía y los únicos que esta unidad añade a la
traza:

| Evento | Cuándo | Para qué |
| --- | --- | --- |
| `voice.speech_end` | Al cerrarse el turno de la persona | Extremo izquierdo de NFR1 |
| `voice.first_audio` | Al salir el primer byte sintetizado del turno | Extremo derecho de NFR1 |
| `voice.barge_in_stop` | Al confirmarse una interrupción | NFR2 |
| `voice.resume_after_drop` | Al retomar un caso cortado | NFR3, enlazado al caso original |

Llevan tiempos e identificadores, nunca contenido. Es ADR-013 y es lo que cierra
RT-14.

## Lo que se ve desde fuera mientras la llamada corre

El estado de la llamada viaja por el socket para que la consola lo dibuje
—`connecting`, `listening`, `speaking`, `ended`— pero **no se persiste**: nadie
lo consulta después, y una tabla de estados por segundo sería un registro de
audio por otro nombre.

Lo que sí queda es la fila de `CallSession` con sus tiempos y su motivo de final,
que es lo que permite contar llamadas, duraciones y causas sin mirar a nadie en
particular.

## El panel público no cambia

La regla del proyecto es dura y no se toca: las superficies públicas muestran
recuentos, totales y distribuciones, nunca un número de caso ni un identificador
de visitante. Lo que la voz aporta al panel de U22 son recuentos de llamadas,
distribuciones de duración y de motivo de final, y las latencias agregadas. Nada
por llamada.

## Lo que no es de esta unidad

Los paneles y el chequeo periódico son de la pasada de publicación (U20, U22).
Esta unidad deja los eventos; quien los dibuja viene después.
