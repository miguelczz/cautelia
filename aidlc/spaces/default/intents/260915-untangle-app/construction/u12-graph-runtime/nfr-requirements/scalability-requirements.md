# Requisitos de escalabilidad — U12 `graph-runtime`

El techo de esta unidad no es el tráfico: es que **todo corre en un proceso**, y el
trabajo de fondo son tareas de ese mismo proceso, sin broker (ADR-004). Así que
"escalar" aquí significa dos cosas concretas y ninguna abstracta: que una
conversación no le quite el turno a otra, y que lo que se guarda no crezca sin
fondo.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| SCALE-U12.1 | Latencia del turno con varias conversaciones a la vez, p95, frente a la de una sola | **No más del doble** con cinco conversaciones concurrentes | Tarea nueva `mise run test:u12` |
| SCALE-U12.2 | Turnos bloqueados por el trabajo de CPU de otra conversación | **Exactamente 0** | Tarea nueva `mise run test:u12` |
| SCALE-U12.3 | Filas de las tres tablas de esta unidad que sobreviven al reinicio nocturno de los datos de demostración | **Exactamente 0** para casos de visitante | Tarea nueva `mise run test:u12` |
| SCALE-U12.4 | Trabajo de fondo pendiente acumulado al arrancar, tras sembrar ejecuciones sin terminar | **Se publica**; el barrido lo vacía | Tarea nueva `mise run test:u12` |

## Cinco conversaciones, y por qué cinco

No es una cifra de capacidad: es la de la demostración. El enlace público tiene
límite por visitante y por día, y lo que hay que descartar no es un pico de
tráfico —no va a haber— sino **que dos visitantes a la vez se estorben**, que es lo
que un evaluador puede ver en treinta segundos abriendo dos pestañas.

Por eso SCALE-U12.1 admite el doble y no un margen estrecho: con un solo proceso,
dos conversaciones comparten el bucle de eventos y una degradación es esperable. Lo
que no es esperable es que una se detenga, y eso es SCALE-U12.2.

## De dónde sale SCALE-U12.2

El trabajo de CPU del turno —la redacción de datos personales y los chequeos de
forma— es síncrono, y medido en 5,3 ms p95 (ver `performance-requirements.md`). En
un solo proceso, 5 ms de CPU bloquean el bucle de eventos para todos. Con cinco
conversaciones, eso son 25 ms de cola en el peor caso: aceptable. Con el trabajo de
CPU **dentro** del bucle y una operación que tardara cien veces más, no lo sería, y
ese es el fallo que TECH-U12.4 evita sacándolo del bucle.

## Lo que esta unidad no promete

- **Más de un proceso.** Con dos, lo que hoy es una tarea asíncrona necesita el
  arrendamiento y el latido para no duplicarse; por eso existen desde ahora
  (BR5.5). Pero nada de esto se prueba con dos procesos: eso es del intent `infra`
  si algún día hay dos.
- **Crecimiento indefinido de los puntos de control.** La demostración se reinicia
  cada noche y ahí se borran (BR6.4). Un despliegue que no se reiniciara necesitaría
  una política de retención, y no la tiene.

## Sources

- `../functional-design/rules.md` — BR5.4, BR5.5, BR6.4.
- `../../../inception/domain-design/components.md` — ADR-004 y su enmienda del
  2026-09-17 (el trabajo de CPU fuera del bucle de eventos).
- `performance-requirements.md` — la medición de 5,3 ms p95 del trabajo propio.
- `../../../inception/requirements-analysis/requirements.md` — FR2.3, FR7.1.

## Assumptions & Open Questions

- **[Assumption]** Cinco conversaciones concurrentes es el techo que la
  demostración necesita descartar. Si el enlace público se publica con un límite
  mayor, esta cifra se revisa con él y no por su cuenta.
