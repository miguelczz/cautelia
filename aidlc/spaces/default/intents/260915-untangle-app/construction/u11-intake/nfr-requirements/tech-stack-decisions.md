# Decisiones de stack — U11 `intake`

U11 no trae dependencias nuevas de ejecución ni tablas nuevas. Lo que sí trae es
**configuración versionada**, y dónde vive cada pieza es lo que este documento
fija.

| ID | Decisión | Por qué |
| --- | --- | --- |
| TECH-U11.1 | Los prompts de extracción y de composición viven versionados en `app/config/prompts/`, uno por idioma, y no en cadenas dentro del código | Es la nota de implementación de la unidad y lo que hace que un cambio de prompt sea un cambio de código que dispara la compuerta de evaluación. El README de esa carpeta ya dice que solo U11 y U12 escriben ahí |
| TECH-U11.2 | Las reglas de normalización —fechas relativas, placas, pólizas, cédulas, teléfonos y los separadores que la transcripción pega a los códigos— viven en configuración versionada y se aplican en código | FD-U11-2: si normalizara el modelo, dos corridas del mismo commit escribirían valores distintos y NFR8.2 dejaría de ser reproducible |
| TECH-U11.3 | La tabla de letras confundibles y su palabra de deletreo es una sola, versionada, y la usan el texto y la voz | Dos tablas acabarían diciendo cosas distintas para el mismo código, y quien lo compara por teléfono es la persona |
| TECH-U11.4 | Las listas de frases prohibidas —las que culpan, las que minimizan, las de registro— viven versionadas y las comprueba el código sobre el texto ya compuesto | FD-U11-4: es lo que se publica aunque el juez esté descalibrado (AC1.13.5) |
| TECH-U11.5 | Cuántos insultos disparan la frase de calma y cuántos el cierre viven en la configuración de **cada aseguradora**, no en el código | AC1.13.3 dice "número que fija la configuración", y la convención 9 prohíbe una diferencia entre aseguradoras metida en una rama de código |
| TECH-U11.6 | Ninguna dependencia de ejecución nueva | Extracción con el modelo que ya existe, normalización con la biblioteca estándar. Si al implementar apareciera una candidata, se justifica en una línea o no entra |
| NFR18.3 | U11 **no** lleva piso de cobertura propio: no está en la lista de módulos críticos de `team.md`. El agregado del aplicativo sigue en 80 % | La lista son cinco —reglas, citas, aislamiento, esquema del caso y redacción— y se amplía por decisión de Miguel, no por analogía |

## Dónde vive el código

`app/backend/src/untangle/orchestration/nodes/intake/`, por la convención 3: el
código de un nodo vive en el directorio de su token, aunque lo construya esta
unidad. Sin tablas nuevas y sin migración: U11 escribe en las entidades del caso
por la API de U4 (`entities: []` en el catálogo de componentes).

## Comandos nuevos

| Comando | Qué hace |
| --- | --- |
| `mise run test:u11` | Las pruebas de la unidad: las unitarias del nodo y las de integración que escriben en el caso |

Es **tarea nueva** que crea la generación de código; hoy no existe.

## Sources

- `../functional-design/entities.md` — por qué no hay tabla nueva.
- `../functional-design/functional-spec.md` — FD-U11-2, FD-U11-4, FD-U11-6.
- `../../../inception/units-generation/unit-of-work.md` — notas de
  implementación y dónde vive el código; tabla de metas: NFR18 es de U1.
- `../../../../codekb/untangle/technology-stack.md` — el escaneo de
  pre-incepción no anota nada que toque a esta unidad: su fila de modelo y
  proveedor la resolvió ADR-006 en Domain Design.
- `../../../inception/contract-design/contract-summary.md` — C-15 (la forma del
  nodo), C-12 (el caso), C-16 (el modelo), C-18 (la póliza emitida) y C-20 (las
  señales que levanta U10 dentro del turno). U11 no añade contrato propio: su
  superficie es la del nodo.
- `aidlc/spaces/default/memory/team.md` — la lista de módulos críticos, que no
  incluye la captura.

## Assumptions & Open Questions

- **[assumption]** `app/config/prompts/` existe hoy con su README y sin ningún
  prompt dentro. U11 es la primera unidad que escribe ahí, así que la forma del
  archivo —nombre, idioma, versión— la fija esta unidad y U12 la hereda.
