"""El ajustador de IA (plan 09, fase 5, 2026-11-03).

Cuando un caso llega al ajustador, lo decide un subagente de IA que explica su decision con
fuentes y un proceso visible. El diseno entero esta en
`docs/propuesta-2026-10/11-ajustador-de-ia.md`.

Esta es la capa justo encima de `untangle.inbox` --llama a su `decide`-- y por debajo de
`untangle.server`, que es el unico que la importa y quien le enchufa los puertos
(`WebResearcher`, `TextGenerator`) construidos con el adaptador. Nada de aqui importa un SDK
ni un adaptador, y `untangle.orchestration` no sabe que existe.

La tanda 1 trae los cimientos: la configuracion versionada (`config`), el tope diario de casos
(`quota`) y la tabla de la corrida (`repository`). El proceso que decide es de la tanda 2.
"""
