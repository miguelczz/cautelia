# Requisitos de rendimiento — U17 `voice-public-link`

Versión corta. Dos objetivos.

| # | Objetivo | Valor | Cómo se mide |
| --- | --- | --- | --- |
| PERF-U17.1 | La decisión de los dos carriles, sumada | p95 ≤ 1 ms | Prueba cronometrada con los contadores dados como argumento, en `test:u17`. Es el mismo presupuesto que los cinco controles del chat, y por la misma razón: la decisión es pura, así que el número mide la decisión y no la máquina |
| PERF-U17.2 | La consola dice si hay voz **antes** de pedir el micrófono | Siempre, sin excepción | No es un número: es un orden. Se comprueba con la prueba que exige que la petición del micrófono no ocurra antes de tener la disponibilidad (BR3.1) |

**La latencia de la llamada no es de esta unidad.** Las tres metas de tiempo de la voz
—fin del habla al primer audio, y las dos de parada— son de U16 y se miden por hito
contra los proveedores de verdad. Lo que esta unidad añade a la consola es **mostrar**
la del último turno, y su requisito es que **coincida con la traza** (BR3.3), que es una
cuestión de honestidad y no de velocidad.

## Sources

- `../functional-design/rules.md` — BR1.2, BR3.1, BR3.3
- El presupuesto de `chat/limits.py` (PERF-U13.1), que esta decisión copia

## Assumptions & Open Questions

None.
