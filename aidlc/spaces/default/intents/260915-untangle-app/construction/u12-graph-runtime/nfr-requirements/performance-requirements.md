# Requisitos de rendimiento — U12 `graph-runtime`

Esta es la etapa que tres unidades están esperando. U8, U9 y U11 escribieron su
tiempo máximo con la misma nota —*"el presupuesto real de este nodo antes de
degradar es de U12, que todavía no existe"*— y este documento es donde deja de ser
una nota.

Y el punto de partida no es una preferencia: **la latencia del turno ya tiene un
número aprobado**, y su dueña es U16 para la voz y U13 para el chat; lo que U12
aporta se declara con identificador propio (NFR1.1, NFR4.2) para que la matriz de
verificación no cuente dos veces lo mismo. Decisión de Miguel del 2026-09-15, fijada en el PRD: del fin del
habla al primer audio, **p50 menor que 500 ms y p95 menor que 800 ms, por idioma**.
Todo lo de abajo se deriva de ahí o se mide; nada se elige.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| PERF-U12.1 | Latencia del turno: del fin del habla al primer audio, p50 y p95 **por idioma** | **p50 < 500 ms, p95 < 800 ms** (PRD, decisión del 2026-09-15) | `mise run evals:gate` |
| PERF-U12.2 | Los tres controles del turno, sumados, p95 | **10 ms o menos** (enmendado el 2026-10-03; era 1 ms) | Tarea nueva `mise run test:u12`, prueba cronometrada |
| PERF-U12.3 | El trabajo propio del nodo del turno, sin la llamada al proveedor, p95 | **50 ms o menos** | Tarea nueva `mise run test:u12` |
| PERF-U12.4 | El tiempo máximo de un nodo del **ritmo del turno** antes de degradar | **1.600 ms o menos**, dos veces la meta p95 del turno | Tarea nueva `mise run test:u12`, sobre el `NodeSpec` declarado |
| PERF-U12.5 | Silencio antes de la frase de espera cuando el trabajo de fondo no ha vuelto | **menor que 2 s** (AC1.25.3) | `mise run evals:gate` |
| PERF-U12.6 | Llamadas al modelo por turno de la persona | **Exactamente 1** (ADR-004) | Tarea nueva `mise run test:u12` |
| PERF-U12.7 | Latencia de la decisión de fondo, p50 y p95 por idioma | **Se publica; sin umbral**, porque nadie la espera | `mise run evals:gate` |
| PERF-U12.8 | Duración del barrido al arrancar, con trabajo pendiente sembrado | **Se publica desde la primera corrida** | Tarea nueva `mise run test:u12` |
| NFR1.1 | Aporte de U12 a la latencia del turno de voz (NFR1, dueña U16): su trabajo propio dentro del turno | **Se publica**; el umbral del turno completo es de U16 | `mise run evals:gate` |
| NFR4.2 | Aporte de U12 a la latencia del chat (NFR4, dueña U13): su trabajo propio dentro del turno | **Se publica**; el umbral es de U13 | `mise run evals:gate` |

## De dónde sale cada número, medido hoy

Los tres controles del turno y el trabajo propio del nodo **se midieron**, en esta
máquina, el 2026-09-27, sin proveedor y sin base de datos, sobre seis turnos y tres
frases representativos en los dos idiomas:

| Qué | p50 | p95 | Muestras |
| --- | --- | --- | --- |
| Las dos deteccciones del turno, juntas (`read_turn_signals`) | 0,029 ms | **0,039 ms** | 1.800 |
| La guardia de salida (`guard_output`) | 0,052 ms | **0,059 ms** | 900 |
| El nodo de captura completo, sin la llamada al proveedor | 4,876 ms | **5,275 ms** | 500 |

Con eso, el reparto del presupuesto de 800 ms queda así, y la conclusión es la
parte útil:

- Los tres controles: **0,098 ms**, una diezmilésima del presupuesto.
- El trabajo propio del grafo y de la captura: **5,3 ms**, el 0,7 %.
- **Lo que queda, unos 794 ms, es enteramente la cadena de proveedores**:
  finalización de la transcripción, la llamada al modelo y el primer byte de la
  síntesis. Ninguno de los tres es de esta unidad.

**Por qué los umbrales están diez veces por encima de lo medido.** El trabajo de
PERF-U12.2 y PERF-U12.3 no es certificar los 0,098 ms: es **fallar el día que uno
de esos controles deje de ser barato**. La forma en que eso pasa es concreta
—alguien le añade una consulta a la base, una lectura de archivo o una llamada de
red— y cualquiera de las tres salta a milisegundos o decenas de ellos. Un umbral
pegado a la medición fallaría por el ruido de la máquina; uno diez veces por encima
solo falla cuando cambió la naturaleza del control.

**Por qué PERF-U12.4 son 1.600 ms y no los 8.000 declarados.** Un tiempo máximo no
es una meta: es cuándo se deja de esperar. Pero un nodo del ritmo del turno con
8.000 ms de tiempo máximo **no puede participar de un turno cuya meta p95 son
800 ms**: cuando ese tiempo máximo se cumpliera, el turno ya habría fallado su meta
diez veces. La regla que se fija aquí es el doble de la meta p95 —suficiente margen
para que una llamada simplemente lenta termine, poco para que una colgada retenga a
la persona ocho segundos— y de ahí salen los 1.600 ms. El valor exacto se revisa
contra la primera medición real con el conductor de canal de U13; la regla, no.

Los nodos del **ritmo de fondo** no cambian: nadie los espera, y el uso `corpus`
tolera la cola del plan gratuito. Los 60.000 ms de `policy_verification` siguen
siendo correctos por la razón que su propio módulo escribe.

## Lo que esto le cambia a otra unidad

`orchestration/nodes/intake/node.py` declara `timeout_ms = 8_000` "mientras U12 no
fije el suyo desde la medición". Esta etapa lo fija: **1.600 ms**. Es el único
cambio que este documento produce fuera de U12, y es exactamente el que la nota de
U11 invitaba a hacer.

## La pregunta abierta de U11, respondida

U11 dejó escrito: *"¿Cuántas llamadas al modelo caben en un turno? Se asigna a
U12"*. La respuesta es **una** (PERF-U12.6), y no es una elección de esta etapa:
ADR-004 ya la fijó en su enmienda del 2026-09-17 —"el turno de voz hace una sola
llamada al modelo"— y el reparto de arriba dice por qué no cabe otra. Con 794 ms
para la cadena entera de proveedores, dos llamadas al modelo dentro del mismo turno
no caben en 800 ms ni con el proveedor respondiendo perfecto.

Hoy la captura ya cumple: extrae con una llamada y compone con el catálogo, sin
modelo.

## Sources

- `docs/specs/prd.md` — Segmento 10.(a) y la decisión del 2026-09-15: p50 < 500 ms
  y p95 < 800 ms, del fin del habla al primer audio, por idioma.
- `../functional-design/rules.md` — BR2.2, BR2.3, BR2.4.
- `../../../inception/domain-design/components.md` — ADR-004 y su enmienda del
  2026-09-17.
- `../../u11-intake/nfr-requirements/performance-requirements.md` — la pregunta
  abierta que este documento responde.
- `orchestration/nodes/policy_verification/node.py`,
  `orchestration/nodes/decision/node.py`,
  `orchestration/nodes/compliance/node.py`,
  `orchestration/nodes/intake/node.py` — los cuatro tiempos máximos declarados.
- La medición del 2026-09-27. La tarea nueva `mise run test:u12`, que esta unidad crea, la reproduce.

## Assumptions & Open Questions

- **[Assumption, resuelta el 2026-10-03]** La medición de los tres controles y del
  nodo se hizo en la máquina de desarrollo. El flujo de GitHub Actions corre en una
  máquina más lenta y puede mover el p95; los umbrales de PERF-U12.2 y PERF-U12.3
  tienen margen de sobra para eso, y si alguna vez no lo tuvieran, lo que se ajusta
  es el umbral con su medición escrita al lado, **nunca el control**.

  **No lo tuvo, y se ajustó por ese camino.** PERF-U12.2 puso `main` en rojo
  midiendo 1,0507 ms contra su umbral de 1 ms, con los controles sin tocar: la
  máquina del flujo es entre seis y diez veces más lenta que la de desarrollo, que
  ese mismo día medía 0,17 ms. El umbral pasa a **10 ms**, que son diez veces la
  medición del flujo —la máquina que de verdad corre la compuerta— y siguen siendo
  el 1,25 % del presupuesto de 800 ms del turno. Lo que la prueba detecta no
  cambia: una consulta a la base, una lectura de archivo o una llamada de red
  cuestan milisegundos o decenas, y las tres siguen cayendo.

  **PERF-U12.3 no se toca, y la diferencia importa.** Sus 50 ms no salen de un
  margen sobre una medición: salen del presupuesto del turno, donde son el 6 % de
  los 800 ms. Un umbral derivado del presupuesto se respeta aunque la máquina
  aprete; uno derivado de una medición se recalibra cuando la máquina cambia. Dicho
  esto, su margen en el flujo es estrecho: aquí mide 5,1 ms, y la misma proporción
  que puso a PERF-U12.2 en 1,05 lo dejaría cerca de 30 ms de los 50. Es una
  inferencia, no una medición, y si ese día llega la respuesta es abaratar el nodo,
  no subir el número.
- **[Q]** ¿Cuánto de los 794 ms se lleva cada proveedor? Es de U15
  `speech-providers` y de U5, y se publica desde la primera corrida con el
  conductor de canal. Hasta entonces PERF-U12.1 se reporta como "no medida" con esa
  causa.
