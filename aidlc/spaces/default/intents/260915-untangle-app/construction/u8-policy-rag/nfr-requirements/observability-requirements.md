# Requisitos de observabilidad — U8 `policy-rag`

Cuando una respuesta de cobertura no sale, hay que poder decir **por qué** sin
volver a correrla. Eso es lo que esta sección exige.

## Qué queda registrado

| Evento | Cuándo | Qué lleva | Regla |
| --- | --- | --- | --- |
| Recuperación | En cada `retrieve` | Los filtros aplicados antes de ordenar (inquilino, póliza, formulario, versión, endosos), los identificadores recuperados en orden, y de dónde vino cada uno: léxica, vectorial o cierre | BR2.1, BR2.4 |
| Comprobación de cita | En cada cita | El identificador, el resultado, los motivos como claves cerradas, y los endosos que la modifican cuando los hay | BR3.2, BR3.5, BR4.4 |
| Fallo del nodo | En cada fallo | El nodo, el tipo de error de la taxonomía cerrada del proveedor y el número de intento | BR5.3 |
| Respuesta de cobertura | Al registrar | El resultado, el idioma de la respuesta y el de las cláusulas, y las comprobaciones enlazadas | BR4.1, BR5.8 |

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| OBS-U8.1 | Comprobaciones de cita sin motivo registrado (AC2.2.1) | **Exactamente 0** | Tarea nueva `mise run test:u8` |
| OBS-U8.2 | Fallos del nodo sin evento de traza con nodo, tipo de error e intento (AC2.6.2) | **Exactamente 0** | Tarea nueva `mise run test:u8` |
| OBS-U8.3 | Motivos escritos como prosa libre en vez de clave del conjunto cerrado (BR4.4) | **Exactamente 0** | `mise run types` |
| NFR11.7 | Datos personales dentro de los eventos de traza de esta unidad (NFR11, dueña U3) | **Exactamente 0** | `mise run evals:gate` (segundo detector de U21) |

El rastro de la recuperación no es adorno: es lo único que permite saber si un
fallo de REL-U8.1 fue de la búsqueda léxica, de la vectorial o del cierre por
relaciones, y sin esa distinción una caída de la métrica no se puede arreglar,
solo lamentar.

## Sources

- `../functional-design/rules.md` — BR2.1, BR2.4, BR3.2, BR3.5, BR4.1, BR4.4,
  BR5.3, BR5.8.
- `../functional-design/entities.md` — `RetrievalProbe`, que existe para esto.
- `../../../inception/units-generation/unit-of-work.md` — tabla de metas: NFR11
  es de U3.
