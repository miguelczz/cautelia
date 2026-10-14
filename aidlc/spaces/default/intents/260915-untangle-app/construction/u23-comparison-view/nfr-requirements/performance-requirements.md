# Requisitos de rendimiento — U23 `comparison-view`

Versión corta. Un objetivo, y no es el que se esperaría.

| # | Objetivo | Valor | Cómo se mide |
| --- | --- | --- | --- |
| PERF-U23.1 | La primera columna en responder **no espera** a las otras dos | La primera respuesta se dibuja al llegar, sin depender de las otras | Prueba con dos columnas lentas y una rápida: la rápida aparece primero. No es un número de milisegundos porque lo que importa es la independencia, no la velocidad |

**No hay meta de latencia de punta a punta**, y decirlo es parte del diseño: el tiempo
de una columna es el del chat de esa aseguradora, que ya tiene su propio presupuesto y
depende del modelo. Poner aquí un número sería medir el proveedor y llamarlo esta
vista.

**La vista entra en el arnés de accesibilidad** como pantalla de visitante, con sus dos
idiomas y sus dos modos, y suma a la duración del arnés, que tiene su propio
presupuesto (PERF-U6.3, SCALE-U6.2).

## Sources

- `../functional-design/rules.md` — BR2.2
- `../../../inception/user-stories/stories.md` — AC2.9.5

## Assumptions & Open Questions

None.
