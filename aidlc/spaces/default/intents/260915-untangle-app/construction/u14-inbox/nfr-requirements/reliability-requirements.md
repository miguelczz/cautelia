# Requisitos de confiabilidad — U14 `inbox`

Dos promesas: una decisión nunca se aplica dos veces, y una pantalla abierta
nunca se queda mostrando un estado viejo sin decirlo.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| REL-U14.1 | Decisiones duplicadas al repetir la misma clave de idempotencia | **Exactamente 0**: devuelve la primera | Tarea nueva `mise run test:u14` |
| REL-U14.2 | Peticiones distintas que reciclan una clave ya usada y reciben el resultado de la otra | **Exactamente 0**: es un conflicto, no un resultado | Tarea nueva `mise run test:u14` |
| REL-U14.3 | Eventos perdidos entre una desconexión y su reanudación por `Last-Event-ID` (BR6.2) | **Exactamente 0** | Tarea nueva `mise run test:u14` |
| REL-U14.4 | Decisiones registradas cuya reanudación del grafo falló y quedaron sin rastro | **Exactamente 0**: la decisión queda y el fallo deja su evento | Tarea nueva `mise run test:u14` |
| REL-U14.5 | Correcciones que escriben el campo sin su entrada de historial, o al revés | **Exactamente 0** (lo garantiza la transacción de U4) | Tarea nueva `mise run test:u14` |

## Por qué la clave reciclada es un conflicto y no un resultado

REL-U14.2 distingue dos cosas que se parecen: **la misma petición otra vez** y
**otra petición con la clave de la anterior**. La primera devuelve lo que se
escribió; la segunda tiene que fallar. Devolverle a alguien el resultado de una
petición que no hizo es peor que rechazarlo: creería que su decisión se aplicó.

Por eso el recibo guarda el resumen de lo que se pidió y no solo la clave.

## La decisión sobrevive al fallo de la reanudación

REL-U14.4 fija la dirección: **primero se registra la decisión, después se
reanuda el grafo**. Si el grafo falla, la decisión sigue tomada y el fallo deja
su evento para reintentarlo; si se hiciera al revés, un fallo de la reanudación
perdería la firma de una persona, que es lo único que este proyecto no puede
reconstruir.

## Lo que esta unidad no sostiene

La reanudación en sí es de U12 y su política de fallo es suya. La emisión del
enlace y su vigencia son de U2.
