# Decisiones de herramientas — U9 `rules-decision`

**Ninguna dependencia nueva.** Las reglas se leen con el `RuleSet` de U2
(Pydantic y PyYAML), y se evalúan con código propio sobre un conjunto cerrado de
operadores (FD-U9-1).

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| TECH-U9.1 | Reglas sin prueba, pruebas de regla en rojo, o aseguradoras fuera del rango de 10 a 20 reglas | **Exactamente 0** | Tarea nueva `mise run test:u9` y `mise run schema:check` |

## Sources

- `../functional-design/functional-spec.md` — FD-U9-1 a FD-U9-4.
- `aidlc/spaces/default/codekb/untangle/technology-stack.md` — stack del
  aplicativo.

## Assumptions & Open Questions

- Ninguna.
