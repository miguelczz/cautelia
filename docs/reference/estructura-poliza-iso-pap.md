# Estructura de la póliza de auto personal ISO (PP 00 01) — referencia para el corpus sintético

Fuente: specimen público de un regulador estatal (Maine Bureau of Insurance, formulario PP 00 01 06 94; también existe el PP 00 01 09 18 en el regulador de Virginia). Solo se registra la **estructura** (secciones y numeración). El texto del formulario es material con derechos de ISO y no se copia ni se incluye en el repositorio (ver `critica.md`, C14).

## Secciones del formulario

1. **Agreement** (acuerdo)
2. **Definitions** (definiciones con letras: "you", "your", "we", "bodily injury", "property damage", "your covered auto", "trailer", etc.)
3. **Part A – Liability Coverage**: Insuring Agreement; Supplementary Payments; Exclusions (A. numeradas 1 a 9 aproximadamente, B. numeradas 1 a 3); Limit of Liability; Out of State Coverage; Financial Responsibility; Other Insurance
4. **Part B – Medical Payments Coverage**: Insuring Agreement; Exclusions (numeradas); Limit of Liability; Other Insurance
5. **Part C – Uninsured Motorists Coverage**: Insuring Agreement (incluye hit-and-run); Exclusions; Limit of Liability; Other Insurance; Arbitration
6. **Part D – Coverage for Damage to Your Auto**: Insuring Agreement (Collision y Other Than Collision); Transportation Expenses; Exclusions (numeradas 1 a 13 aproximadamente, con sub-apartados); Limit of Liability; Payment of Loss; No Benefit to Bailee; Other Sources of Recovery; Appraisal
7. **Part E – Duties After an Accident or Loss**: A. aviso oportuno (cómo, cuándo, dónde, lesionados y testigos); B. cooperación, envío de documentos, exámenes y autorizaciones, prueba de pérdida; C. deberes adicionales para motoristas sin seguro (policía en hit-and-run, copias de papeles legales); D. deberes para Part D (proteger el vehículo, avisar a la policía si hay robo, permitir inspección y tasación)
8. **Part F – General Provisions**: Bankruptcy; Changes; Fraud; Legal Action Against Us; Our Right to Recover Payment; Policy Period and Territory; Termination; Transfer of Your Interest; Two or More Auto Policies

## Cómo se usa en Untangle

- Cada póliza sintética de cada aseguradora ficticia sigue estas secciones con **texto original** y con **identificadores estables** de cláusula, por ejemplo `A.EXCL.A.3`, `D.INS.COLLISION`, `D.EXCL.7`, `E.DUTIES.A.1`, `F.FRAUD`.
- Las diferencias entre aseguradoras se introducen a propósito: definiciones distintas de "your covered auto", exclusiones que un endoso reabre, deducibles y límites distintos, y cláusulas casi idénticas que obligan a distinguir (distractores para la eval de citación).
- Las preguntas típicas de FNOL se mapean a secciones: "¿está cubierto el choque?" → Part D (Collision) y sus exclusiones; "¿qué debo hacer ahora?" → Part E; "¿cubre al conductor que no soy yo?" → Definitions y Part A; "¿qué pasa si el otro no tiene seguro?" → Part C.
- El texto extraído del specimen queda solo en el scratchpad de la sesión de investigación; no se versiona.
