# Preguntas — Generación de código de U5 `provider-platform`

## Plan Approval

Cubre `code-generation-plan.md` —veinticuatro pasos en seis bloques, con su
contrato de pruebas embebido— y `unit-test-instructions.md`, con el comando
acotado a esta unidad y el reparto de pruebas por pieza.

**Lo que hay que saber antes de aprobar**, en tres frases:

1. **Se construye la unidad entera**: los cuatro puertos de proveedor con el
   adaptador de Gemini detrás, la contabilidad con su techo de 5 USD y sus
   cuotas, y las trazas con sus resúmenes. Cuatro tablas, tres de ellas fuera
   del aislamiento por aseguradora con su aserción nueva que lo paga.
2. **Dos pasos tocan archivos de otras unidades**: el paso 11 añade la aserción
   de columnas a `rls_assertion.py`, que es de U2 y sostiene el aislamiento del
   proyecto entero; el paso 2 añade la comprobación de vigencia de los topes a
   `schema_check.py`, que es de U1. Los dos cambios son aditivos y las pruebas
   propias de esas unidades tienen que seguir verdes.
3. **El adaptador no se prueba contra Gemini en esta entrega.** Grabar una
   respuesta real exige una clave y un poco de cuota; las pruebas del paso 18
   inyectan errores con `respx`, sin clave y sin costo. La grabación se hace la
   primera vez que haya clave, y esa prueba corre por hito.

[Approval Fingerprint]: sha256:v3:52830d22026d9b8996fef2ea34fcbc8a5852297b2ed73cd5cfa9c2c125415eff
[Planned Source]: 2aea078d435896fbbc595ee92817858698ca7ed9ff77995d6adcd8d8d85f05a5

- Approve Plan
- Request Changes

[Answer]: Approve Plan
