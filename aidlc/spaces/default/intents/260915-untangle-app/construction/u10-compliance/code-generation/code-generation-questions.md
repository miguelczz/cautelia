# Preguntas — Generación de código de U10 `compliance`

## Plan Approval

Cubre `code-generation-plan.md` con su contrato de pruebas embebido, y
`unit-test-instructions.md`.

**Qué se construye:** los controles que impiden que la agente prometa cobertura,
montos o culpa, que diga ser humana o que revele configuración; la detección de
quien pide hablar con una persona o reporta heridos graves; el registro de la
divulgación; la revisión de cierre y el nodo que cierra o deriva. Dieciséis pasos
por la rama evaluada: los casos de ataque y de conversación se escriben primero,
se ven fallar y después se implementa hasta que pasan.

**Cuatro decisiones que el plan toma**, porque en el modo ligero ya no pasan por
diseño de calidad ni de infraestructura:

- **CG-U10-1** — Los patrones son archivos de datos por idioma, con esquema: uno
  mal escrito impide arrancar.
- **CG-U10-2** — La frase de emergencia es la pública por omisión ("esta es una
  demostración y no puede enviar ayuda"); la del 911 solo con configuración
  local explícita.
- **CG-U10-3** — Las tres tablas se borran con su caso.
- **CG-U10-4** — Se mide cuánto tarda la guardia por frase y se publica, sin
  umbral propio: el presupuesto del turno lo fija U12.

[Approval Fingerprint]: sha256:v3:492a873de66ff377e98b93249fc37b404cc44b38b7d4a55061b485d02fd4cf59
[Planned Source]: 66e77ebc85cde5afbd354f7bcd111ed509e689b3ebefac276ec0e7471084d4d1

- "Approve Plan" — proceed to code generation
- "Request Changes" — revise the plan

[Answer]: Approve Plan
