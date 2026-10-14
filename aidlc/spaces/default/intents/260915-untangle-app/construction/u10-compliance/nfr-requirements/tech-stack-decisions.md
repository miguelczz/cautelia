# Decisiones de herramientas — U10 `compliance`

**Ninguna dependencia nueva.** Los controles son patrones sobre texto
normalizado: la biblioteca estándar de Python (`re` para las expresiones,
`unicodedata` para quitar tildes) alcanza, y agregar un motor de reglas o un
clasificador sería una superficie más sin ganar nada que las pruebas no cubran.

| Pieza | Con qué | Por qué |
| --- | --- | --- |
| Patrones por idioma y familia | Archivos YAML versionados en un directorio nuevo, `app/config/compliance/`, que se crea con la generación de código | Son datos, no código (FD-U10-1); cambiarlos es un cambio a la vista que exige su caso (BR9.2) |
| Esquema de los patrones | Modelo de Pydantic con su JSON Schema generado por `mise run contracts:gen` | Igual que los demás esquemas de C-28; un patrón mal escrito impide arrancar |
| Normalización | `unicodedata` y `re` de la biblioteca estándar | Sin dependencia |
| Tablas | Migración de Alembic como las demás, con aislamiento forzado | Convención del proyecto |
| Casos de evaluación | Archivos de DS-2 y DS-6 por caso y frases de prueba por idioma en un directorio nuevo, `app/evals/fixtures/compliance/`, que se crea con la generación de código | El patrón que dejó U3 |

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| TECH-U10.1 | Un archivo de patrones inválido | **Impide arrancar**, nombrando el archivo y el patrón | `mise run test:u10` |
| TECH-U10.2 | El esquema de los patrones se regenera con los contratos | **Sin deriva** | `mise run contracts:check` |

## Sources

- `../functional-design/functional-spec.md` — FD-U10-1 a FD-U10-8.
- `../../../inception/contract-design/contract-summary.md` — C-28.
- `aidlc/spaces/default/codekb/untangle/technology-stack.md` — stack del
  aplicativo.

## Assumptions & Open Questions

- Ninguna.
