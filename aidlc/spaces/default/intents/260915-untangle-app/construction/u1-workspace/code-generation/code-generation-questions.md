# Preguntas — Generación de código de U1 `workspace`

## Plan Approval

Cubre `code-generation-plan.md` con su contrato de pruebas embebido, y
`unit-test-instructions.md`.

**Qué se construye:** el primer commit de código del aplicativo. Veintiséis pasos
en siete bloques, siguiendo la rama determinista capa por capa, con 44 pruebas
repartidas en nueve componentes. Dos andamiajes (Python y TypeScript) con sus
herramientas, contratos de importación, catálogo de textos con sus seis chequeos,
corredor de evaluaciones con el asegurado simulado, guion único de verificación,
los dos flujos de GitHub Actions y los servicios locales.

**Dos decisiones que el plan toma y conviene mirar antes de aprobar:**

- **CG-1 — U1 no crea tablas de base de datos.** Las cuatro entidades se
  construyen como modelos tipados y archivos. La razón es que toda tabla del
  aplicativo debe llegar con su aislamiento a nivel de fila y su test, y la pieza
  que lo hace cumplir es de U2, que todavía no existe. El efecto secundario es
  bueno: el camino de los 15 minutos deja de necesitar la base de datos y baja de
  14 a unos 8 minutos de presupuesto.
- **CG-2 — El subconjunto de arranque nace con casos propios.** El diseño lo
  dejaba vacío, lo que produciría un reporte de cero casos. Se llena con los
  chequeos deterministas que U1 sí puede producir, que son casos reales del
  sistema y no de adorno.

[Approval Fingerprint]: sha256:v3:d063c204d3309e56ea7d108b60f141e1f393826afa7e54ea3052b890c6f22a99
[Planned Source]: c51a879940880c1552095ee468f7d93247f9cbdda25038560bba1a83bc117a53

- "Approve Plan" — proceed to code generation
- "Request Changes" — revise the plan

[Answer]: Approve Plan
