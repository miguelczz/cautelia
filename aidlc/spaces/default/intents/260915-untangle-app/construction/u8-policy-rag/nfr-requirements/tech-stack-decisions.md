# Decisiones de stack — U8 `policy-rag`

U8 no trae dependencias nuevas de ejecución. Todo lo que necesita ya está en el
proyecto: PostgreSQL con pgvector desde el primer commit de U2, el puerto
`Embedder` desde U5 y el corpus desde U7.

| ID | Decisión | Por qué |
| --- | --- | --- |
| TECH-U8.1 | El índice léxico y el vectorial viven en la misma base que el resto del aplicativo, sin servicio de búsqueda aparte | Es ADR-010. Una búsqueda que vive fuera de la base es una búsqueda fuera de la política de fila, y el aislamiento entre aseguradoras es compuerta dura |
| TECH-U8.2 | Búsqueda vectorial exacta, sin índice HNSW ni IVFFlat | Con 104 cláusulas por corpus, un índice aproximado añade una estructura que mantener y afinar a cambio de nada medible. El umbral que lo revisaría se escribe al lado del código, no se hereda en silencio (FD-U8-6) |
| TECH-U8.3 | La fusión por rango recíproco se escribe a mano, sin biblioteca nueva | Son cinco líneas y una constante; una dependencia de ejecución tendría que justificar qué hace que la biblioteca estándar no haga |
| TECH-U8.4 | La configuración del `tsvector` sale del idioma de la cláusula: `spanish` para el corpus de Stonecroft, `english` para el de Sunmeadow, y la que corresponda a cada copia dentro de Knotwell | El lematizador de un idioma sobre el texto del otro degrada la búsqueda léxica justo donde más se nota, y el corpus ya declara su idioma por cláusula |
| TECH-U8.5 | El identificador del modelo de embeddings y su dimensión se leen de `app/config/providers/providers.yaml` —hoy `gemini-embedding-001` con 768 dimensiones, truncadas y normalizadas— y el identificador es parte de la clave del índice | Es ADR-006 y ADR-010: cambiar el modelo o la dimensión invalida el índice entero, y eso tiene que verse en un diff y disparar la compuerta de evaluación |
| TECH-U8.6 | El corpus se ingiere desde los archivos de `app/data/`, nunca se lee en caliente durante un turno | El turno consulta la base; los archivos son la fuente versionada que la ingesta traduce. Leer archivos en el turno pondría el disco en el camino de una respuesta |
| NFR18.1 | `policy_rag/citations/` lleva piso propio de cobertura del **80 %**, como módulo crítico; el agregado del aplicativo sigue en 80 % | Es la lista de módulos críticos de `team.md`: el verificador de citas está en ella desde el principio |

## Tablas nuevas y migración

Una migración, `u8_policy_0001_corpus_tables`, con las siete tablas de la
unidad: `policy_forms`, `clauses`, `clause_index`, `clause_relations`,
`issued_policies`, `citation_checks` y `coverage_answers`. Todas con RLS
habilitada y política de inquilino, como exige la aserción de esquema que ya
corre en `mise run rls:check`; las dos últimas con clave foránea compuesta
`(tenant_id, case_id)` hacia el caso, igual que hizo U9 con su tabla de
evaluaciones.

## Comandos nuevos

| Comando | Qué hace |
| --- | --- |
| `mise run test:u8` | Las pruebas de la unidad: unitarias de `policy_rag/` y de integración de U8 |
| `mise run corpus:ingest` | Ingiere el corpus de `app/data/` en la base, comprobando el manifiesto primero |

Los dos son **tareas nuevas** que crea la generación de código; hoy no existen.
`mise run corpus:ingest` es además el comando que U20 `demo-operations` invocará
al aprovisionar, en vez de escribir el suyo.

## Sources

- `../functional-design/entities.md` — las siete entidades y sus desviaciones
  frente al catálogo.
- `../functional-design/rules.md` — BR1.6, BR2.3, BR3.2.
- `../../../inception/domain-design/components.md` — ADR-006 y ADR-010.
- `../../../inception/units-generation/unit-of-work.md` — tabla de metas: NFR18
  es de U1 y U8 lleva su piso propio como módulo crítico.
- `app/config/providers/providers.yaml` — el modelo de embeddings y su dimensión.
- `aidlc/spaces/default/memory/team.md` — la lista de módulos críticos.
- `../../../../codekb/untangle/technology-stack.md` — el escaneo de
  pre-incepción anotó "pgvector dentro del mismo Postgres (un solo mecanismo de
  aislamiento)" como **hipótesis** pendiente de un ADR. TECH-U8.1 es la unidad
  donde esa hipótesis se ejecuta: ADR-010 la confirmó y U8 la construye. Ninguna
  otra fila de ese documento toca a esta unidad.

## Assumptions & Open Questions

- **[assumption]** No se añade ninguna dependencia de ejecución. Si al
  implementar apareciera una candidata, se justifica en una línea —qué hace, por
  qué no la biblioteca estándar, y su licencia— o no entra.
