# Preguntas de la generación de código — U14 `inbox`

## Plan Approval

**Qué se va a construir:** la bandeja del ajustador. La cola por aseguradora con
sus filtros, la vista de caso que reúne la evidencia de cinco unidades, la
corrección de un campo con rastro, la decisión con comentario que reanuda el
grafo, y la pantalla propia del visitante que entra a su caso con un enlace
firmado de una hora.

**En cuatro tandas**, como U13, por la razón medida que está en
`docs/reference/como-se-escribe-el-codigo.md`: el costo fijo de una tanda no baja
con su tamaño.

1. **La cola y su aislamiento** — las dos tablas con su política de fila, el
   listado con filtros, orden y cursor, y **la compuerta dura de la credencial**.
2. **La vista, la corrección y el aviso en vivo** — los seis bloques reunidos sin
   copia, la corrección con su recibo, y la cola de eventos con reanudación por
   `Last-Event-ID`.
3. **La decisión y el enlace firmado** — comentario obligatorio, registrar antes
   de reanudar, las acciones por configuración, y **las dos compuertas duras del
   enlace**.
4. **Las tres pantallas, los casos de evaluación y el cierre.**

**Las tres compuertas duras se cierran en las tandas 1 y 3**, nunca en la última:
una compuerta dejada para el final es una que se descubre roja cuando ya no hay
tiempo de arreglarla.

**El caso previo que se escribe antes del código:** RT-4 de DS-6 con las
colisiones sembradas de DS-8 —mismas pólizas y mismos nombres en dos
aseguradoras—, un caso derivado de DS-2 con su explicación esperada, y los casos
de clientes de Knotwell. Se corren y se comprueba que fallan.

**Lo que sale del alcance**, por tu decisión del 2026-09-28: la tercera decisión
que C-05 declara (`request_more`). Ninguna historia la describe, ningún criterio
la ejercita y ninguna de las cuatro resoluciones del caso le corresponde. El
contrato se enmienda con esa razón en la tanda 3, y añadirla después es aditivo.

**Lo que gasta:** nada de crédito de la nube. Consume plan, en el mismo orden que
U13: cuatro tandas escritas desde esta sesión, sin agente que vuelva a descubrir
el repositorio.

**Lo que no cambia:** ninguna compuerta, el piso de cobertura del 80 % agregado y
en los cinco módulos críticos, `scripts/verify.sh` como verificación única, y
GitHub Actions sobre `main` como compuerta autoritativa.

[Approval Fingerprint]: sha256:v3:5e1d8c3a4b53564a83e53361a93ccf9fc04bcf044b19ae508b291dc37d99d6cd
[Planned Source]: 4d3e289d409470954dc3b50f6369e7fc61407636b4f97644d3fe06c2364b6666

- "Approve Plan" — proceed to code generation
- "Request Changes" — revise the plan

[Answer]: Approve Plan
