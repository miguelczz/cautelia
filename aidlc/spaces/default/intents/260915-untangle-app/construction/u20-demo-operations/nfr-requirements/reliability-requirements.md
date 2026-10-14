# Requisitos de confiabilidad — U20 `demo-operations`

Versión corta. Es la familia que esta unidad necesita de verdad: el reinicio es una
operación programada que nadie está mirando cuando corre.

| # | Requisito | Valor | Cómo se comprueba |
| --- | --- | --- | --- |
| REL-U20.1 | Cada corrida deja su registro, termine bien o mal | Sin excepción | Prueba con un purgador doble que levanta: la corrida termina, el registro existe y dice cuál falló (BR3.1) |
| REL-U20.2 | Un fallo levanta alerta y se reintenta | Siempre | Prueba con el fallo forzado; la alerta sale con el identificador de la corrida |
| REL-U20.3 | Un reinicio parcial se reporta como parcial | `partial`, nunca colapsado | Prueba con siete purgadores que borran y dos que fallan. Colapsarlo en `failed` haría que el reintento borrara otra vez lo ya borrado; en `succeeded`, dejaría datos con el contador reiniciado |
| REL-U20.4 | El reintento no deja el estado peor que antes | Idempotente | Prueba que repite la corrida tras un parcial |
| REL-U20.5 | El aprovisionamiento es idempotente | Mismo estado | AC5.1.5, BR1.2 |

**El reloj de las 24 horas cuenta desde el último éxito.** Es el requisito más fácil de
implementar mal y el más difícil de notar: con el contador atado al último intento, una
cadena de fallos deja la demo aceptando datos indefinidamente y el tablero en verde.

## Sources

- `../functional-design/rules.md` — BR2.4, BR3.1, BR3.2
- `../functional-design/entities.md` — `ResetRun` y por qué `partial` existe

## Assumptions & Open Questions

None.
