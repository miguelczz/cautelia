# Preguntas — Generación de código de U9 `rules-decision`

## Plan Approval

Cubre `code-generation-plan.md`, con su contrato de pruebas embebido, y
`unit-test-instructions.md`.

**Qué se construye:** el motor de reglas de las tres aseguradoras y el nodo
`decision`. Decide la categoría de cada caso sin modelo: cierre directo,
revisión estándar o derivación. Cada categoría sale con sus reglas disparadas,
sus insumos y una explicación en los dos idiomas. Primero se escriben 12 casos
de DS-2 y se ven fallar. Son diez pasos en dos tandas cortas.

**Lo que gasta:** nada en proveedores; U9 no llama a ningún modelo.

**Es la prueba del modo ligero:** Sonnet, comentarios cortos y suite completa
una vez por tanda. El plan fija cuatro condiciones para dar por bueno el modo:
pasa, queda alineado, queda bien escrito y sale más barato.

**Cinco decisiones que el plan toma:** CG-U9-1 a CG-U9-5 (reglas por perfil
de aseguradora, 12 casos, cuatro criterios, llave compuesta y dos tandas).

[Approval Fingerprint]: sha256:v3:258f20ed64a196b8390c414fbf9c0db01b6bb154b1b0e811a62a603f03ad6930
[Planned Source]: b093cfb51ae519285366c52b912ecde0fc2bad425cd8e265d76d94593c70e8fb

- "Approve Plan" — proceed to code generation
- "Request Changes" — revise the plan

[Answer]: Approve Plan
