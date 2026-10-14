# Preguntas — Generación de código de U8 `policy-rag`

## Plan Approval

Cubre `code-generation-plan.md`, con su contrato de pruebas embebido, y
`unit-test-instructions.md`.

**Qué se construye:** el corpus dentro de la base, la recuperación filtrada, el
verificador exacto de citas y el nodo `policy_verification`. Siete tablas nuevas
con aislamiento por aseguradora, y los 40 casos de DS-3, que hoy no existen.
Once pasos en tres tandas.

**Por qué importa más que las otras:** es la unidad que hace que una cita
signifique algo. Siete de sus reglas son compuerta dura y el verificador es
módulo crítico con piso de cobertura propio.

**Lo que gasta:** unos 11 USD de crédito por tanda, 33 en total, sobre los 190
que quedan. En proveedor, la ingesta real llama al modelo de embeddings una vez
por cláusula —414 en total— y esas llamadas se registran como "no medidas"
porque el modelo salió de la página de precios de Google.

**Dónde se escribe:** las tres tandas van a la nube con Sonnet, **cada una en
una sesión nueva**. Aquí se quedan la ingesta real con la clave, las compuertas
que necesitan base de datos, la revisión y el commit.

**Lo que necesita de ti:** abrir una sesión de la nube por tanda y pegarme el
informe cuando cada una termine. Nada más.

**Seis decisiones que el plan toma:** CG-U8-1 a CG-U8-6 (tres tandas en sesiones
limpias, DS-3 con una prueba que comprueba cada identificador contra el corpus,
una prueba que aísle cada una de las seis reglas de precedencia, ninguna prueba
llama al proveedor, las de integración se escriben allá y se corren aquí, y el
corpus con instrucciones fuera de los tres inquilinos de la demo).

[Approval Fingerprint]: sha256:v3:0248de6ca250aa11b9bc1ee8eaf275d22190ced9e391ff3606cfb1b87ef2aae7
[Planned Source]: 029314bb8eb236f9f141c9444d79d9bab34c7629f8936933740aed89938fddc6

- "Approve Plan" — proceed to code generation
- "Request Changes" — revise the plan

[Answer]: Approve Plan
