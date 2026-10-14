# Preguntas — Generación de código de U11 `intake`

## Plan Approval

Cubre `code-generation-plan.md`, con su contrato de pruebas embebido, y
`unit-test-instructions.md`.

**Qué se construye:** el nodo de captura. Identifica a la persona contra su
póliza sin revelar nada ajeno, extrae solo lo dicho con la evidencia del turno,
normaliza lo dictado con reglas versionadas, pregunta en el orden fijo leyéndolo
del caso, y lee la confirmación de cada bloque. Sin tablas nuevas y sin
migración: escribe en el caso de U4. Diez pasos en dos tandas.

**Por qué importa:** es la primera unidad que corre **dentro del turno**, con
una persona esperando, y la que decide qué queda escrito en su caso. Realiza
siete metas del hito que son de otras unidades —completitud, exactitud de
extracción, fidelidad de la lectura, turnos por caso, rúbrica de estilo—.

**Los dieciséis casos previos que hoy no existen:** diez ejes de DS-2 —relato
ordenado, desordenado, dato adelantado, llanto y enojo, por idioma— y seis de
DS-6 —RT-7, RT-9 y RT-11, por idioma—. Se escriben antes del código y se ven
fallar, igual que DS-3 en U8.

**Lo que gasta:** de 15 a 30 USD de crédito por tanda, sobre los 103 que quedan.
Nada en proveedores: ninguna prueba llama al modelo.

**Dónde se escribe:** las dos tandas van a la nube con Sonnet, cada una en una
sesión nueva. Aquí se quedan las compuertas con base de datos, la revisión y el
commit.

**Lo que necesita de ti:** abrir una sesión de la nube por tanda y pasarme el
informe. Nada más.

**Seis decisiones que el plan toma:** CG-U11-1 a CG-U11-6 (dos tandas en
sesiones limpias, los dieciséis casos previos antes del código, una prueba que
aísle cada una de las siete reglas de precedencia, ninguna prueba llama al
proveedor, las de integración se escriben allá y se corren aquí, y los datos
grandes se consultan con un guion en vez de leerlos archivo por archivo).

[Approval Fingerprint]: sha256:v3:6be0502b700260ad5628a9fbe62ff8c9c4c5b1fa6c69d42f6d612bf6459a62fd
[Planned Source]: 016c73895224dcf3dca475ed2f19eca6b856615dd1be3d844ce3295f2b355fe4

- "Approve Plan" — proceed to code generation
- "Request Changes" — revise the plan

[Answer]: Approve Plan
