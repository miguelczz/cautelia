# Preguntas — Generación de código de U13 `chat`

## Plan Approval

Cubre `code-generation-plan.md`, con su contrato de pruebas embebido, y
`unit-test-instructions.md`.

**Qué se construye:** el chat público. La primera superficie que alguien de fuera
puede abrir: la conversación con su divulgación, sus límites, el streaming, la cita
expandible, el resumen de traza, el aviso de lo que decidió el ajustador y la retoma
de un caso desde el navegador. Dos tablas nuevas con su migración.

**Cómo se construye, y esto cambia respecto de todas las anteriores:** en **cuatro
tandas**, escritas en esta sesión sin despachar agentes. Es la decisión que salió de
la evaluación del 2026-09-28 (`docs/reference/como-se-escribe-el-codigo.md`): U12
pagó siete veces el costo fijo de una tanda para lo que cabía en dos, y cada agente
despachado gastaba entre 395.000 y 773.000 tokens releyendo el repositorio.

**Las tres compuertas duras que toca, y dónde se cierran:** que nada del visitante se
procese antes de la divulgación (tanda 1), y que un caso de otro navegador y uno de
otra aseguradora respondan **idéntico** a uno que no existe (tanda 3). Ninguna se
deja para la última tanda: una compuerta dura dejada para el final es una que se
descubre roja cuando ya no hay tiempo de arreglarla.

**El caso previo que hoy no existe:** los ejes de DS-2 por el canal chat y el
escenario RT-10 de DS-6 —cambio de idioma para esquivar los controles—, en los dos
idiomas. Se escriben antes del código y se ven fallar.

**Lo que salió del alcance:** la vista de comparación entre aseguradoras, por tu
decisión del 2026-09-28. Es de U23 `comparison-view`, después de U14.

**Lo que gasta:** nada de crédito de la nube. Consume plan, y menos que U12 porque no
hay agente que vuelva a descubrir el repositorio en cada tanda.

**Lo que no cambia:** ninguna compuerta, el piso de cobertura del 80 % agregado y en
los cinco módulos críticos, `scripts/verify.sh` como verificación única, y GitHub
Actions sobre `main` como compuerta autoritativa.

[Approval Fingerprint]: sha256:v3:4cc2e8333c73626cbe77cd100e488a13392426510417502dc0a22e11417eaf96
[Planned Source]: 78056f13d9617566b21c32b1540288b4994c26b70fc42f006dcd4030bf4a0da7

- "Approve Plan" — proceed to code generation
- "Request Changes" — revise the plan

[Answer]: Approve Plan
