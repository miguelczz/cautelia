# Requisitos de rendimiento — U11 `intake`

U11 es la primera unidad que corre **dentro del turno**, con una persona
esperando. Eso convierte el presupuesto de tokens en una restricción real y no
en una preferencia.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| PERF-U11.1 | Tokens de entrada del prompt de extracción más el de composición, por turno de voz (ADR-006), **contados por el proveedor** | **3.900 o menos**; se publica desde la primera corrida con conductor de canal | `mise run evals:gate` (enmendada el 2026-09-27, ver abajo) |
| PERF-U11.2 | Llamadas al modelo por turno de la persona | **Se publica desde la primera corrida**; el techo lo fija U12 con el presupuesto del turno | `mise run evals:gate` |
| PERF-U11.3 | Duración de la parte de U11 en un turno, sin la llamada al proveedor, p50 y p95 | **Se publica desde la primera corrida**, sin umbral | `mise run evals:gate` |
| NFR4.1 | Aporte de U11 a la latencia del chat (NFR4, dueña U13: p95 menor que 3 s del envío a la primera palabra) | Se publica; el umbral es de U13 | `mise run evals:gate` |
| NFR14.1 | Costo por turno de captura, con el modelo y el precio de lista usados (NFR14, dueña U5) | Se publica por versión | `mise run spend:report` |

## Por qué dos de ellas se publican y no bloquean

Por la misma razón que en U8: **el presupuesto de latencia del turno es de U12**,
que es quien aplica la política de fallo y decide cuánto puede esperar el ritmo
del turno antes de degradar. Ese ejecutor todavía no existe. Poner aquí un
número sería inventarlo; medirlo y publicarlo desde la primera corrida hace que
U12 fije su umbral contra algo real.

PERF-U11.1 es distinta y **sí tiene número**: los 3.900 tokens salen de ADR-006,
que es una decisión aprobada, y se comprueban contando el prompt, no
estimándolo.

### Enmienda del 2026-09-27: quién cuenta los tokens

Decisión de Miguel, durante la revisión de la tanda 2 de U11. La primera
redacción dejaba el comando en `mise run test:u11`, es decir, en una cuenta hecha
sin red. **Ninguna cuenta hecha sin red cumple "contando, no estimando"**: ni
Gemini ni ningún proveedor de este proyecto publica un contador que corra sin
llamar, y "ninguna prueba llama al proveedor" es una regla más dura que este
presupuesto. La cuenta que se escribió —palabras y signos de puntuación— además
**estima por debajo**: un tokenizador de subpalabras parte las palabras largas, y
en español da bastante más de un token que palabras, así que un prompt que la
pasara todavía podía no caber.

El conteo exacto existe, es gratis y llega con cada respuesta:
`usageMetadata.promptTokenCount`, que el adaptador de U5 ya lee y registra por
nodo en la traza. **Ese es el número que mide PERF-U11.1**, y se publica desde la
primera corrida con conductor de canal (U13) — la misma forma y por la misma
razón que PERF-U11.2 y PERF-U11.3. Hasta entonces el criterio se reporta como
**"no medida"** con esa causa, que es lo que la práctica exige y lo contrario de
omitirlo.

La cuenta sin red **se queda** como guardia previa, con lo que de verdad
certifica escrito en su propio módulo: si un prompt ya no cabe ahí, no cabe. Que
devuelva verde no certifica lo contrario.

Se descartó instalar una dependencia de tokenizador para contar sin red: sería
una dependencia de runtime cuyo único trabajo es aproximar lo que el proveedor ya
dice gratis.

## Restricción de recursos

- **El prompt de extracción crece con cada campo.** Siete campos, cada uno con
  su estado y su evidencia, más el texto de la persona. Cuando no quepa en el
  presupuesto, se recorta **lo que se le manda al modelo** —el historial, los
  ejemplos— y nunca lo que se le exige: un prompt más corto que extraiga peor
  mueve NFR8.2, que es una meta publicada.
- **Una llamada al modelo por turno, no dos.** La extracción y la composición
  caben en la misma llamada mientras el presupuesto lo permita; separarlas
  duplica el costo y la latencia del turno que la persona espera.
- **Ninguna prueba llama al proveedor** (mismo criterio que U8): dobles
  deterministas, y la medición real contra DS-2 cuando U13 traiga su conductor.

## Sources

- `../functional-design/rules.md` — BR2.1, BR3.4.
- `../../../inception/domain-design/components.md` — ADR-006 y el presupuesto de
  3.900 tokens por turno de voz.
- `../../../inception/units-generation/unit-of-work.md` — notas de
  implementación de U11; tabla de metas: NFR4 es de U13 y NFR14 de U5.

## Assumptions & Open Questions

- **[Q]** ¿Cuántas llamadas al modelo caben en un turno? Se asigna a **U12**,
  que es quien lleva el presupuesto del turno y los dos ritmos. U11 entrega la
  medición de PERF-U11.2 y se ajusta a lo que U12 decida.
