# Requisitos de rendimiento — U19 `quote`

Versión corta. Dos objetivos medibles, y los dos salen de presupuestos que ya existen.

| # | Objetivo | Valor | Cómo se mide |
| --- | --- | --- | --- |
| PERF-U19.1 | La evaluación del conjunto de elegibilidad de una aseguradora, sobre una solicitud completa | p95 ≤ 20 ms | Prueba cronometrada sobre el conjunto sembrado, en `test:u19`. Es pura lógica sobre datos ya cargados: sin base, sin proveedor |
| PERF-U19.2 | El turno de captura de un bloque **no** crece por soportar cotización | Dentro del presupuesto de turno que ya vigila la captura | La elegibilidad corre en el ritmo de fondo (BR2.5), así que el turno no la espera. Se comprueba con la prueba que ya existe para el presupuesto del turno |

**Por qué 20 ms y no un número más generoso.** El conjunto de elegibilidad son cinco
reglas sobre cinco campos en memoria. Un presupuesto holgado no protegería de nada: lo
que este número atrapa es que alguien meta una consulta o una llamada dentro de la
evaluación, y eso se ve en milisegundos.

Las metas de calidad de la unidad —95 % de exactitud por campo, 100 % de derivaciones
correctas, 10 % o menos de derivaciones innecesarias— son de golden set y se miden por
hito sobre DS-4, no en cada entrega. La que sí corre en cada entrega es la compuerta
dura: cero respuestas con importe.

## Sources

- `../functional-design/rules.md` — BR2.5
- `../../../inception/user-stories/stories.md` — AC6.1.4, AC6.2.5
- `../../../inception/requirements-analysis/requirements.md` — NFR13

## Assumptions & Open Questions

None.
