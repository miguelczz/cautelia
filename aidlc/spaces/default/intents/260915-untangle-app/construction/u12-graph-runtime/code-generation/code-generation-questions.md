# Preguntas — Generación de código de U12 `graph-runtime`

## Plan Approval

Cubre `code-generation-plan.md`, con su contrato de pruebas embebido, y
`unit-test-instructions.md`.

**Qué se construye:** el runtime del grafo. El estado tipado compuesto desde los
contratos de los cuatro nodos, la transición pura, el ejecutor común de la
política de fallo, los dos ritmos con precarga y frase de espera, los puntos de
control con su aislamiento, la pausa hacia la bandeja y el punto único de salida.
Tres tablas nuevas con su migración. Ocho pasos.

**Por qué importa:** es la unidad de la que dependen U13, U14, U16, U17 y U18.
Hasta que exista no hay forma de conversar con el sistema de punta a punta, y por
eso los 40 casos de DS-3 y el etiquetado de DS-7 siguen esperando.

**El caso previo que hoy no existe:** el eje de DS-2 de pregunta de cobertura
durante el reporte, en los dos idiomas. Se escribe antes del código y se ve fallar.

**Las dos compuertas duras que toca:** que la póliza de ejemplo no abra el caso de
otra persona (AC1.19.3) y que ninguna tabla —incluidas las de puntos de control—
quede sin aislamiento ni fuera del punto único de sesión (AC4.11.1).

**Dónde se escribe, y esto cambia respecto de U8, U9, U11 y U21:** **aquí, en esta
sesión, no en la nube** (CG-U12-1). Quedan 54 USD de crédito para nueve unidades, y
el motivo por el que el código se fue a la nube —el límite semanal de uso— ya no se
cumple: está en 4 %. Además, media docena de las reglas de esta unidad solo se
pueden comprobar con base de datos delante, que es justo lo que esa sesión no
tiene. Las compuertas corren **al cerrar cada paso** y no todas al final, que es la
ventaja de construir aquí.

**Lo que gasta:** nada de crédito de la nube, y nada en proveedores —ninguna prueba
llama al modelo. Consume plan, que hoy es el recurso que sobra.

**Lo que no cambia:** ninguna compuerta, el piso de cobertura del 80 %, el ritual de
aprobación que estás leyendo, la revisión y el commit a `main` con GitHub Actions
como compuerta autoritativa.

[Approval Fingerprint]: sha256:v3:664d456eca5571ffe2dccdbd04d26f2166b78ab6060ce05ec06d5cb43f600549
[Planned Source]: 00852237ecc2f1d860ae0fcf8fcee526415385bc5ec69cf5d5915bfc8a70d871

[Answer]: Approve Plan
