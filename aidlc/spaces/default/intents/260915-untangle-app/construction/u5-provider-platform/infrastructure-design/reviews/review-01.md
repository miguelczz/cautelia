## Review

**Reviewer:** aidlc-architecture-reviewer-agent
**Iteration:** 1
**Verdict:** NOT-READY
**Date:** 2026-09-21T04:35:54Z

### Herramientas de validación

| Herramienta | Resultado | Interpretación |
| --- | --- | --- |
| `python3 scripts/check-artifacts.py aidlc/.../construction/u5-provider-platform` | `u5-provider-platform: sin hallazgos. Total: 0` | Sin problemas mecánicos (secciones, referencias de formato) |
| `aidlc engine sensor fire traceability --stage infrastructure-design --output-path .../traceability.json` | `"result":"passed"` | La trazabilidad hacia arriba (NFR11.5–NFR18.1) resuelve sin IDs huérfanos |

Ninguna de las dos herramientas mira el contenido de la prosa contra el
repositorio vivo ni contra los contratos compartidos, que es donde están los
cuatro hallazgos de abajo.

### Comprobaciones cuantitativas hechas contra la fuente (no contra la prosa)

- Conté el paso 6 de `scripts/verify.sh`: la cadena tiene exactamente 11
  comprobaciones (`schema:check`, `contracts:check`, `env:check`,
  `supply:check`, `rls:check`, `migrate:check`, `tenancy:literals`,
  `redaction:constructor`, `redaction:report`, `case:constructor`,
  `case:transitions`), y el reparto que el documento implica —U1 cuatro, U2
  tres, U3 dos, U4 dos— cuadra. U5 en efecto no añade una duodécima. Correcto.
- Conté la columna "Dueño" de las 30 filas de la tabla de contratos en
  `inception/contract-design/contract-summary.md`: U2 aparece como dueña en
  C-07, C-10, C-11, C-25 y C-30 (cinco), pero **U1 aparece solo en C-21, C-22,
  C-24 y C-27 (cuatro, no cinco)**. Ver hallazgo R-01.
- Comparé `.env.example`, `docker-compose.yml`, `app/backend/.importlinter` y
  `app/backend/pyproject.toml` contra cada fila de "Lo que ya existe y U5 solo
  usa" y "Lo que U5 añade a archivos que ya existen": el perfil `traces` con
  sus dos imágenes ancladas por huella existe tal como se describe;
  `untangle.providers` no está en la lista `source_modules` del contrato
  `sdk-solo-en-su-adaptador`, así que hoy el SDK del proveedor se podría
  importar en cualquier punto de ese paquete, tal como afirma Q1; `app/config/
  providers/` no existe todavía; ninguna migración de U5 existe todavía.
  Correcto en los cuatro casos.
- Leí `app/backend/src/untangle/tenancy/rls_assertion.py` completo: su
  `evaluate()` y su consulta `TABLAS_DEL_ESQUEMA` solo devuelven
  `row_security`, `force_row_security` y `tenant_policies`; no hay ninguna
  columna ni tipo de dato en el resultado. Ver hallazgo R-04.
- Leí `construction/u4-case-record/infrastructure-design/cicd-pipeline.md`
  líneas 89-99 para contrastar la afirmación "primera unidad" del documento
  principal. Ver hallazgo R-02.

### Findings

| ID | Severity | Location | Finding | Required action | Status |
| --- | --- | --- | --- | --- | --- |
| R-01 | Major | `construction/u5-provider-platform/infrastructure-design/infrastructure-specification.md` > sección "Infraestructura compartida", párrafo bajo la tabla | El documento afirma "Tres contratos es bastante para una unidad: solo U1 y U2 ofrecen más —cinco cada una, contadas sobre la tabla de contratos—". Contando la columna "Dueño" de `inception/contract-design/contract-summary.md` (30 filas), U2 sí tiene cinco (C-07, C-10, C-11, C-25, C-30), pero U1 tiene **cuatro** (C-21, C-22, C-24, C-27), no cinco. La cifra de U1 es falsa. | Corregir la frase a la cifra real de U1 (cuatro) o explicar qué quinto contrato se está contando y por qué no aparece como "Dueño" de U1 en `contract-summary.md`. | New |
| R-02 | Major | `construction/u5-provider-platform/infrastructure-design/cicd-pipeline.md` > sección "Vuelta atrás" y decisión INF-U5-7 | El documento afirma "Es la primera unidad del proyecto en la que bajar la migración y volver atrás el código no son lo mismo" (repetido también en `construction/infrastructure-design/memory.md`). Pero `construction/u4-case-record/infrastructure-design/cicd-pipeline.md` (líneas 89-99) ya documenta exactamente el mismo fenómeno para U4: "bajar la revisión **borra las tablas del caso** ... no es una vuelta atrás que preserve datos ... Decirlo aquí evita que alguien la ejecute creyendo otra cosa". U4 llegó primero a esa distinción entre vuelta atrás de esquema y de código, con la misma severidad (pérdida de datos irrecuperables). | Quitar el superlativo "primera unidad" o corregirlo para reconocer el precedente de U4; si la diferencia real es que en U5 el dato perdido es el acumulado de gasto exigido por AC5.14.4 (un caso más grave por ser una invariante financiera y no solo datos de caso), decirlo así en vez de reclamar prioridad temporal falsa. | New |
| R-03 | Major | `construction/u5-provider-platform/infrastructure-design/infrastructure-specification.md` > tabla "Infraestructura compartida", fila "Puertos de proveedor y fábrica por uso" | La fila declara "Unidad dueña" = **U5** exclusivamente, y lista a U15 solo entre las "Unidades consumidoras". Pero `inception/contract-design/contract-summary.md` (C-16) dice explícitamente: "Dueño: U5 (modelo y embeddings), U15 (voz)" — es decir, `providers/ports.py` tiene **dos** dueños que escriben protocolos distintos en el mismo archivo, no un dueño único con un consumidor. El párrafo posterior del mismo documento ("Tres contratos es bastante...") también cuenta C-16 como si fuera enteramente de U5 al calcular sus "tres contratos". | Corregir la fila para reflejar la copropiedad U5/U15 de `providers/ports.py` (modelo/embeddings vs. voz), tal como la fija el contrato compartido, y aclarar si el conteo de "tres contratos propios de U5" sigue sosteniéndose con esa corrección. | New |
| R-04 | Major | `construction/u5-provider-platform/infrastructure-design/cicd-pipeline.md` > tabla "El paso 6 no crece, y eso es noticia" (fila `rls:check`) y tabla "Lo que ya existe y U5 solo usa" (fila `mise run rls:check`) | El documento afirma que la obligación "Ninguna tabla excluida del aislamiento tiene columna de texto ni de dato personal" (SEC-U5.6/SEC-U5.7) la cubre `rls:check`, que "crece por dentro" sin ser una tarea nueva. Pero `app/backend/src/untangle/tenancy/rls_assertion.py` (dueño: U2) no tiene hoy ninguna capacidad de inspección de columnas: su consulta `TABLAS_DEL_ESQUEMA` y su función `evaluate()` solo leen `row_security`, `force_row_security` y `tenant_policies`. Lo mismo aplica a `schema:check` (`app/backend/src/untangle/workspace/schema_check.py`, dueño: U1), que hoy no valida ningún archivo de `app/config/providers/`. A diferencia de cada archivo que U5 sí modifica, ninguno de estos dos aparece en la tabla "Lo que U5 añade a archivos que ya existen", pese a exigir código nuevo no trivial (nueva consulta SQL con columnas, nuevo modelo, nueva lista de nombres de columna sensible) en módulos que otra unidad posee. | Añadir `app/backend/src/untangle/tenancy/rls_assertion.py` (y su modelo `TableIsolation`/`RlsReport`) y `app/backend/src/untangle/workspace/schema_check.py` a la tabla de archivos modificados, con la extensión concreta que necesitan, para que la generación de código no descubra a mitad de camino que "crece por dentro" significaba tocar el modelo de otra unidad. | New |

### Summary

Los dos artefactos con más detalle verificable —`cicd-pipeline.md` e
`infrastructure-specification.md`— tienen cuatro afirmaciones que no resisten
la comprobación contra la fuente: una cifra de contratos falsa sobre U1, una
reclamación de "primera unidad" que un documento hermano (U4) ya contradice
por escrito, una fila de propiedad compartida (C-16) presentada como propiedad
única, y dos tareas que se describen como "ya existen y crecen por dentro"
sin declarar que la extensión necesaria cae en archivos de otras unidades sin
la capacidad hoy instalada para hacerlo. Ninguno rompe la tubería por sí solo,
pero los cuatro son del mismo tipo que ya costó una revisión en la etapa
anterior: cifras y superlativos que no se contaron contra la fuente antes de
escribirse.

---

### Resolución (escrita por la conducción, 2026-09-21)

Veredicto tal cual: **NOT-READY**, con sus cuatro hallazgos y su `Status: New`.
**Los cuatro se reprodujeron contra la fuente y los cuatro eran ciertos.**

| ID | ¿Era cierto? | Cómo se comprobó | Qué se hizo |
|---|---|---|---|
| R-01 | Sí, en el sentido que importa | La cuenta depende de si se cuentan las copropiedades: U1 es dueña única de C-21, C-22 y C-24, y copropietaria de C-27 y C-28. Con copropiedades son cinco; sin ellas, tres. El revisor contó cuatro. **Que tres lecturas den tres números distintos es la prueba de que la frase no se sostenía** | Se quitó la comparación. El punto que hacía no la necesitaba: lo que importa de los tres contratos de U5 es por qué no se pueden fundir, y eso se escribió en su lugar |
| R-02 | Sí | `u4-case-record/infrastructure-design/cicd-pipeline.md`, sección "Vuelta atrás", ya dice que bajar la revisión borra las tablas del caso y que no preserva datos. El fenómeno no era nuevo | Se cambió el superlativo por la distinción real, que sí existe y es la que importa: los datos de U4 se regeneran —el reinicio nocturno se los lleva igual—, y el acumulado de U5 es la única cifra que un criterio exige que sobreviva a todo. De ahí una consecuencia que U4 no necesitaba y ahora está escrita: donde el acumulado signifique dinero, bajar esta revisión exige exportar antes |
| R-03 | Sí | `contract-summary.md` línea 88 y la ficha de C-16: **"Dueños: U5 (modelo y embeddings) y U15 (transcripción y síntesis)"**. La tabla de infraestructura ponía a U5 como dueña única y a U15 como consumidora | La fila dice ahora copropiedad, y se explica el reparto real: U5 escribe `ports.py` con los cuatro `Protocol` e implementa dos; U15 implementa los otros dos sin volver a abrir el archivo |
| R-04 | Sí, y es el que habría costado tiempo | `rls_assertion.py`: su consulta trae información de tabla y **ninguna de columnas**, y `evaluate()` hace `continue` sobre las excluidas. `schema_check.py` recorre una lista fija de archivos y no sabe de vigencias. Ninguno de los dos aparecía en la tabla de archivos que U5 toca | Dos filas nuevas en esa tabla, con lo que hay que escribir en cada uno y **de quién es cada archivo** —U2 y U1—, más un párrafo que dice que "el comando crece por dentro" no significa que no cueste código, solo que no nace una tarea |

**La secuencia, por tercera vez y por la misma razón mecánica.** Los cuatro
arreglos se aplicaron después de registrar el recibo: el registrador rechaza un
veredicto cuyos documentos cambiaron tras el despacho, y la etapa admite una sola
pasada. **Este recibo certifica los bytes que el revisor leyó.**

**Lo que sí funcionó esta vez.** Antes de despachar se corrió una comprobación
propia de coherencia —cada comando citado por un control de la etapa anterior
tiene que aparecer en alguna de las tres tablas del documento— y encontró dos
huecos, `mise run lint` y `mise run redaction:constructor`, que se cerraron antes
de que el revisor los viera. También se detectó y corrigió un superlativo falso
de la etapa anterior contando la tabla de contratos. Los cuatro hallazgos de
arriba son los que esa comprobación no podía ver, que es exactamente el reparto
que se buscaba.

**Comprobaciones después de los arreglos** (ejecutadas): `check-artifacts.py`
devuelve **0 hallazgos** sobre la unidad entera, y el sensor de trazabilidad
pasa.
