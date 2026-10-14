# Preguntas — Generación de código de U6 `web-shell`

## Plan Approval

Cubre `code-generation-plan.md` con su contrato de pruebas embebido, y
`unit-test-instructions.md`.

**Qué se construye:** la primera interfaz visible de Untangle y la parte servida
que la sostiene. Veinticinco pasos en ocho bloques, por la rama determinista
capa por capa: tablas y servicio de activación, superficies y salud, directorio
del sitio, rutas y cabeceras del proceso, cliente generado de la API, tokens y
modos, primitivas, el marco con el inicio y las siete páginas de estado, y el
arnés de accesibilidad con los escenarios de tiempo en teléfono.

**Tres decisiones que el plan toma y conviene mirar antes de aprobar**, porque en
el modo ligero ya no pasan por NFR Design ni por Infrastructure Design:

- **CG-U6-1 y CG-U6-2 — Política de contenido estricta.** Todo desde el propio
  origen, sin scripts en línea: el paso que aplica el modo antes de pintar es un
  archivo pequeño propio en vez de un script en línea autorizado por su huella.
  Es más simple que lo que decía el documento de seguridad y cumple lo mismo.
- **CG-U6-4 — Marca de aseguradora opcional.** Corrige el hallazgo mayor de la
  revisión del diseño: C-25 pide que una clave nueva llegue opcional.
- **CG-U6-8 — Se retira el `/health` de U1** a favor de la salud de C-02.

[Approval Fingerprint]: sha256:v3:ebed7f0a38db1fd4a2d26ddd63803523fb656c00b6cb7a654cf1bcb635af889b
[Planned Source]: 49579f94a7d774087ae8bc32d31943fd1d5b2f105f5380b2c60bc1097dc9d952

- "Approve Plan" — proceed to code generation
- "Request Changes" — revise the plan

[Answer]: Approve Plan
