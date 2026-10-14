# Requisitos de rendimiento — U13 `chat`

U13 es **la dueña de NFR4**, la latencia del chat. Las unidades anteriores publicaban
su aporte sin umbral porque el umbral era de esta; aquí deja de haber dónde diferirlo.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| NFR4 | Latencia del chat, del envío a la **primera palabra** que ve la persona, p95, con el entorno de la medición declarado | **menos de 3 s**, por idioma | `mise run evals:gate` |
| PERF-U13.1 | Los tres límites más el intervalo y el tamaño, sumados, antes de resolver la conversación, p95 | **1 ms o menos** | Tarea nueva `mise run test:u13`, prueba cronometrada |
| PERF-U13.2 | Turnos rechazados por un límite que llegaron al proveedor | **Exactamente 0** | Tarea nueva `mise run test:u13` |
| PERF-U13.3 | Tiempo hasta el primer evento de la respuesta (el texto parcial), p50 y p95 | **Se publica** desde la primera corrida; el umbral de la respuesta completa es NFR4 | `mise run evals:gate` |
| PERF-U13.4 | Carga del resumen de traza, p95 | **1,5 s o menos** | Tarea nueva `mise run test:u13` |
| NFR14.2 | Costo por turno de chat, con el modelo y el precio de lista usados (NFR14, dueña U5) | Se publica por versión | `mise run spend:report` |

## Por qué la primera palabra y no la respuesta completa

NFR4 dice "del envío a la primera palabra", y con streaming eso es medible de verdad:
el primer evento de texto parcial. Medir la respuesta completa mediría la longitud de
lo que la agente decidió decir, que no es latencia — un turno que contesta más cosas
tardaría "peor" sin que nada fuera más lento.

De ahí que PERF-U13.3 exista aparte y **se publique sin umbral**: es el mismo
instante que mide NFR4, pero desglosado por percentil para ver de dónde sale el p95
cuando se acerque al límite.

## Por qué PERF-U13.1 es un milisegundo

Los tres límites son aritmética sobre dos filas: no hay llamada al modelo, no hay
recuperación, no hay red. Cualquiera de esas tres saltaría a decenas de
milisegundos. Un umbral pegado a la medición fallaría por el ruido de la máquina; uno
mil veces por encima solo falla cuando cambió la naturaleza del control —por ejemplo,
si alguien metiera una consulta por cada mensaje— y eso es justo lo que se quiere que
falle.

## Por qué PERF-U13.2 es cero y no un porcentaje

Es la mitad medible de BR3.2. Un límite que se comprueba **después** de llamar al
proveedor no protege el presupuesto: lo gasta y luego informa. Un solo turno
rechazado que haya llegado al modelo significa que el orden está invertido, y un
porcentaje escondería ese caso entre los que sí funcionaron.

## Lo que esta unidad no mide

- **La latencia del turno de voz (NFR1)** es de U16. El aporte de U12 está declarado
  como NFR1.1 y esta unidad no lo toca.
- **La duración de la corrida de evaluaciones** es de U21.
- **El techo de gasto de la voz** es de U5; el chat corre en el plan gratuito y su
  límite es de mensajes, no de dinero (BR3.1, BR3.3).
