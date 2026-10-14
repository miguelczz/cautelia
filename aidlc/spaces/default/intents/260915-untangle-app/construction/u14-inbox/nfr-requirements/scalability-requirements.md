# Requisitos de escalabilidad — U14 `inbox`

La bandeja de una demostración con tres aseguradoras y un reinicio nocturno. Lo
que hay que evitar no es la carga: es que una cola crezca hasta que la pantalla
deje de responder y nadie lo note.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| SCAL-U14.1 | Filas devueltas por una consulta de la cola sin límite explícito | **Exactamente 0**: siempre paginada por cursor | Tarea nueva `mise run test:u14` |
| SCAL-U14.2 | Flujos de eventos abiertos por navegador | **Como mucho 1** | Tarea nueva `mise run test:u14` |
| SCAL-U14.3 | Eventos acumulados que el purgador nocturno no se lleva | **Exactamente 0** para los de casos de visitante (C-11) | Tarea nueva `mise run test:u14` |

## Por qué el cursor y no el número de página

Una cola que se ordena por prioridad y espera se reordena sola mientras alguien
la lee: un caso nuevo de prioridad alta empuja a los demás. Con números de
página, pasar a la segunda salta filas que se movieron a la primera. El cursor
lleva la posición y no el conteo, así que lo que se saltó se sabe.

## Lo que el reinicio nocturno se lleva

Los avisos de casos de visitante se borran con sus casos, por el mismo contrato
de borrado que U2 fija (C-11) y que esta unidad implementa con su prueba. Sin
eso, la tabla de avisos sería la única que sobreviviría al reinicio con rastro de
conversaciones ya borradas.
