# Requisitos de seguridad — U23 `comparison-view`

Versión corta. Tres requisitos, y ninguno introduce un mecanismo nuevo.

| # | Requisito | Cómo se comprueba |
| --- | --- | --- |
| SEC-U23.1 | Cada columna recupera solo del corpus de su aseguradora y ninguna cita una cláusula de otra | Prueba que lee **las trazas** de las tres columnas de una pregunta sembrada (AC2.9.3, BR3.1). Es compuerta dura |
| SEC-U23.2 | Lo que escribe el visitante entra como dato delimitado y nunca en la posición de instrucción del prompt, en las tres columnas | Es el mismo camino del chat: la vista no compone ningún prompt. Se comprueba con el caso adversarial que ya existe, corrido por esta superficie |
| SEC-U23.3 | Las tres conversaciones y los tres casos que la vista abre son datos de visitante, y los borra el contrato que ya existe | La prueba que le pregunta al catálogo de la base qué tablas llevan la marca de dato de visitante y exige purgador para cada una; esta vista no añade tabla (UG-3, FD-U23-5) |

**La vista es pública y no pide credencial**, así que no muestra números ni
identificadores de casos de visitantes: muestra respuestas de cobertura sobre pólizas
de ejemplo. Es la misma regla que rige el panel de cifras.

## Sources

- `../functional-design/rules.md` — BR3.1
- `../../../inception/user-stories/stories.md` — AC2.9.3

## Assumptions & Open Questions

None.
