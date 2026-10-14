# Preguntas — Generación de código de U7 `synthetic-data`

## Plan Approval

Cubre `code-generation-plan.md`, con su contrato de pruebas embebido, y
`unit-test-instructions.md`.

**Qué se construye:** el generador de datos sintéticos. Produce el corpus de
Stonecroft en español y el de Sunmeadow en inglés, las copias de Knotwell, las
pólizas emitidas, un caso sembrado en cada estado, DS-8 y los valores
personales ficticios, todo desde textos revisados y con los mismos bytes en
cada corrida. Además deja la compuerta que impide texto de formularios de
terceros y el comando que carga los casos en la base. Son quince pasos por la
rama determinista.

**Lo que gasta:** solo la redacción, unas veinte llamadas a Gemini en plan
gratuito, que no cuestan y quedan en el registro de gasto. Si la cuota del día
se agota, el paso se retoma otro día (CG-U7-7).

**Lo que necesita de Miguel, más adelante:**
- Los specimens públicos del formulario PP 00 01 en `tmp/specimens/`, antes del
  paso 11.
- Su veredicto sobre las dos muestras de diez cláusulas, antes de cerrar la
  unidad.

**Siete decisiones que el plan toma**, en el modo ligero:

- **CG-U7-1** — El azar sale de SHA-256, no del generador aleatorio de Python.
- **CG-U7-2** — Los repertorios de personas y vehículos, y los turnos cortos de
  los casos, se escriben a mano.
- **CG-U7-3** — La redacción usa el modelo del uso `operations`.
- **CG-U7-4** — `synthetic:check` regenera y compara byte a byte en cada
  entrega.
- **CG-U7-5** — Las huellas leen el specimen en PDF con `pypdf`, dependencia
  nueva solo de desarrollo, o en texto plano.
- **CG-U7-6** — DS-8 conserva su ruta y su contenido.
- **CG-U7-7** — Cuota agotada: se detiene y se retoma, sin recargar.

[Approval Fingerprint]: sha256:v3:8a79c534e09b7c7c5965537959518dda06c8cea70ca0a1cc607dec2fb472b753
[Planned Source]: a51b155c9f84b7a7ccff47a8c06c31c301d82797c5c5dfb16389f1524535f0cf

- "Approve Plan" — proceed to code generation
- "Request Changes" — revise the plan

[Answer]: Approve Plan
