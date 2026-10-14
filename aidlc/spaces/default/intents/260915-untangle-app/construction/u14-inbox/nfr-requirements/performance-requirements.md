# Requisitos de rendimiento — U14 `inbox`

Un presupuesto del contrato y una meta humana. La meta humana es la que de
verdad define la unidad: **decidir un caso en menos de tres minutos**.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| PERF-U14.1 | Latencia de la cola con la base tibia (C-05) | **p95 ≤ 1 s** | Tarea nueva `mise run test:u14` (cronometrada) |
| PERF-U14.2 | Latencia de la vista de caso con sus seis bloques, con la base tibia (C-05) | **p95 ≤ 1 s** | Tarea nueva `mise run test:u14` (cronometrada) |
| PERF-U14.3 | Consultas a la base por vista de caso | **≤ 7**: una por bloque más el caso | Tarea nueva `mise run test:u14` |
| PERF-U14.4 | Respuesta del `POST` de decisión, que no espera al grafo (BR4.2) | **p95 ≤ 300 ms** | Tarea nueva `mise run test:u14` (cronometrada) |
| AC3.2.5 | Tiempo de decidir un caso, de abrir a decidir | **< 3 min por caso**, medido con cronómetro | Validación del día 30, registrada con fecha y commit |

## Por qué se cuentan las consultas y no solo el reloj

PERF-U14.3 existe porque la vista reúne seis bloques de cinco unidades distintas,
y la forma natural de escribirla —pedir cada cosa donde hace falta— produce una
consulta por campo, por cita y por turno. Con la base tibia y un caso pequeño eso
cabe en el segundo, así que el reloj no lo detecta; con un caso de cincuenta
turnos, no. Contar las consultas lo detecta en el caso pequeño, que es el que
corren las pruebas.

## La meta humana no se cierra con `N/A`

AC3.2.5 no se puede medir con una prueba: es un criterio sobre una persona
leyendo. Se mide en la validación del día 30, con cronómetro, sobre un conjunto
declarado de casos sembrados, y se registra con su fecha y su commit. Hasta
entonces se reporta **no medida** con esa causa, nunca omitida y nunca en verde.

Lo que esta unidad sí puede hacer para que esa meta sea alcanzable ya está en el
diseño: el encabezado que no se va, tres bloques abiertos y tres plegados con su
resultado a la vista.

## Lo que no se mide aquí

La latencia del turno de chat y de voz es de U13 y U16. La reanudación del grafo
tras la decisión corre de fondo y su presupuesto es de U12: la bandeja responde
`202` y no la espera.
