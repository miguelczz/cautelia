# Preguntas — Generación de código de U21 `eval-gates`

## Plan Approval

Cubre `code-generation-plan.md`, con su contrato de pruebas embebido, y
`unit-test-instructions.md`.

**Qué se construye:** la compuerta de evaluación. La memoria entre corridas
—línea base, casos inestables y explicaciones de regresión—, el reporte con su
diferencia contra la base, un segundo detector de datos personales de mecanismo
distinto al de U3, y la calibración del juez, que deja de contar donde no llega
al umbral. Nueve pasos en dos tandas cortas.

**Lo que gasta:** nada en proveedores durante la construcción. La calibración
real contra DS-7 se corre después, aquí, con la clave del juez.

**Dónde se escribe:** las dos tandas van a una sesión en la nube con Sonnet, con
el crédito, a unos 11 USD cada una. La revisión, las compuertas que necesitan
base de datos y la calibración se quedan en esta máquina.

**Lo que necesita de ti, más adelante:** las 40 transcripciones de DS-7
etiquetadas a mano, 20 por idioma. El paso 6 construye el comando que lo hace
llevadero: muestra un turno y su criterio, guarda el avance y se puede dejar a
medias.

**Seis decisiones que el plan toma:** CG-U21-1 a CG-U21-6 (archivos versionados,
Wilson a mano, detector independiente, el juez calibrado aquí, dos tandas, y una
prueba que aísle cada regla de precedencia).

[Approval Fingerprint]: sha256:v3:0a321b74e464d2201b80bf0fc02d4c716daaeef0ba257436fc12107064a98d4a
[Planned Source]: 241c45fc06edd2b7adcb4ce172f2edef38999e700410013bd3154fdc6a88e50a

- "Approve Plan" — proceed to code generation
- "Request Changes" — revise the plan

[Answer]: Approve Plan
