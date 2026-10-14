# Requisitos de seguridad — U9 `rules-decision`

U9 protege dos cosas: que ninguna categoría la decida un modelo, y que ningún
caso que toque cobertura o dinero se cierre sin una persona. También que su
tabla quede aislada por aseguradora y se borre con el caso.

**`mise run test:u9` no existe todavía**: es una tarea nueva que crea la
generación de código de esta unidad. Los demás comandos existen hoy.

## Modelo de amenazas

| Amenaza | Qué podría pasar | Control | Requisito |
| --- | --- | --- | --- |
| Categoría por modelo | Un cliente de modelo entra en la cadena de decisión y la categoría deja de ser reproducible | Contrato de importación y prueba de determinismo | SEC-U9.1 |
| Dinero sin firma | Una regla de dinero dispara y el caso sale como cierre directo | Precedencia con marca de dinero | SEC-U9.2 |
| Regla sin prueba o rota | Una regla mal escrita cambia decisiones sin que nadie lo note | Validación al cargar y pruebas por regla | TECH-U9.1 |
| Fuga entre aseguradoras | Una evaluación de una aseguradora aparece en otra | Aislamiento por aseguradora y llave compuesta hacia el caso | NFR10.8 |

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| SEC-U9.1 | Rutas de importación desde `rules` o el nodo `decision` hacia un cliente de modelo (AC1.15.3) | **Exactamente 0** | `mise run lint` (contrato de importación) |
| SEC-U9.2 | Evaluaciones con una regla de dinero disparada y categoría distinta de derivación, sobre los casos sembrados y los de DS-2 de U9 (AC1.17.3, `[bloquea]`) | **Exactamente 0** | Tarea nueva `mise run test:u9` y `mise run evals:run -- --subset smoke` |
| NFR10.8 | Filas de `rule_evaluation` visibles desde otra aseguradora, y llaves hacia el caso sin la aseguradora | **Exactamente 0** (NFR10, dueña U2) | `mise run rls:check` y tarea nueva `mise run test:u9` |
| NFR13.1 | Casos de DS-2 de U9 cuya categoría o derivación difiere de la esperada, por aseguradora e idioma | **Exactamente 0** en los casos de U9; la meta de NFR13 sobre DS-2 completo es de U21 | `mise run evals:run -- --subset smoke` |
| NFR18.5 | Cobertura de líneas del motor de reglas, módulo crítico | **80 % o más** (NFR18, dueña U1) | `mise run cov` |

## Sources

- `../functional-design/rules.md` — BR1.1 a BR4.1.
- `../../../inception/requirements-analysis/requirements.md` — FR6.1 a FR6.5,
  NFR10, NFR13 y NFR18.
- `../../../inception/contract-design/contract-summary.md` — C-19.

## Assumptions & Open Questions

- Ninguna.
