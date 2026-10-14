# Requisitos de confiabilidad — U1 `workspace`

U1 no es un servicio en línea: no tiene disponibilidad que medir en porcentaje.
Su confiabilidad es otra cosa, y es medible: **que la misma entrada produzca el
mismo resultado**, y que un fallo ajeno al código no se disfrace de fallo de
calidad.

**Fuentes consumidas.** `../functional-design/functional-spec.md` (los estados de
una corrida y el Flujo 2), `../functional-design/rules.md` (BR1.2, BR1.3, BR1.4,
BR1.5, BR1.7, BR2.4), `../../../inception/requirements-analysis/requirements.md`
(FR11.2 y FR11.5, que fijan el determinismo y la regresión por casos),
`../../../inception/contract-design/contract-summary.md` (C-27) y
`../../../../codekb/untangle/technology-stack.md`.

## Metas

| ID | Qué exige | Valor esperado | Cómo se comprueba |
| --- | --- | --- | --- |
| REL-U1.1 | Determinismo de la corrida | Dos corridas del mismo commit con el mismo subconjunto ejecutan los mismos casos, en el mismo orden | Correr dos veces y comparar la lista de casos ejecutados |
| REL-U1.2 | Determinismo del asegurado simulado | Misma secuencia de campos pedidos, misma secuencia de respuestas | Prueba que repite la secuencia y compara |
| REL-U1.3 | Degradación honesta sin backend de trazas | El reporte se genera con los enlaces marcados como no disponibles | Correr con el backend apagado |
| REL-U1.4 | Fallo cerrado sin clave del modelo | Se detiene antes de la primera llamada y nombra la variable | Correr sin la variable |
| REL-U1.5 | Un caso no medible no rompe la corrida | El caso queda no medido con su causa, la corrida termina y se marca no comparable | Inyectar un error de proveedor en un caso |

**Sin SLA ni SLO de disponibilidad.** Esta unidad no se despliega y no atiende
tráfico; ponerle un porcentaje de disponibilidad sería inventar una métrica.

## Recuperación

| Situación | Qué se pierde | Qué se hace |
| --- | --- | --- |
| La corrida se interrumpe a mitad | Los resultados de esa corrida | Se vuelve a correr; nada queda a medias, porque el reporte se escribe al final |
| El registro local de corridas se pierde | El historial local | Nada bloqueante: la línea base y los casos viven versionados en el repositorio |
| Una corrida se pone roja por causa ajena | Nada | Se marca **no comparable** con su causa, se repite, y el umbral no se toca |
