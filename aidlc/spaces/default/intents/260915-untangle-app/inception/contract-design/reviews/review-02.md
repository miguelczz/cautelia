## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-09-18T23:25:41Z
**Iteration:** 1

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | `contract-summary.md` > C-19 — Motor de reglas | C-19 no listaba a U11 `intake` como consumidor pese a la arista aprobada U11→U9. Ver evidencia de verificación abajo. | Añadir U11 a los consumidores y declarar la función correspondiente. | Resolved |
| R-02 | Major | `contract-summary.md` > punto de integración "Migraciones" | Uno de los 14 puntos de integración no tenía contrato dedicado. Ver evidencia de verificación abajo. | Añadir un contrato para Migraciones o justificar por qué no lo necesita. | Resolved |
| R-03 | Major | `contract-summary.md` > C-16 — Puertos de proveedor | C-16 listaba a U16 en vez de U15 como consumidor, contradiciendo la arista aprobada U15→U5. Ver evidencia de verificación abajo. | Corregir la lista de consumidores a U15, o justificar por qué U16 la necesita. | Resolved |
| R-04 | Minor | `contract-summary.md` > Reglas de propiedad de los contratos, regla 1 | La regla "un contrato, un dueño" se contradecía con siete contratos de dueño compartido. Ver evidencia de verificación abajo. | Aclarar la regla para admitir dueño compuesto con reparto escrito, o dividir los contratos. | Resolved |

### Evidencia de verificación por hallazgo

**R-01.** U11 ahora aparece en la lista de consumidores de C-19, con un párrafo "Por qué U11 está aquí" que cita la arista, la razón textual del mapa (US1.4/US1.12) y la regla UG-8 (dependencia de prueba, no de turno). Se añadió `required_inputs()` en `rules/api.py`, con la obligación explícita de que la captura escriba los campos que las reglas leen y una prueba que compara ambos conjuntos. Verificado contra `unit-of-work-dependency.md` línea 252 (U11 → U9) y líneas 258/273 (U12, U14 → U9) y línea 293 (U19 → U9): los cuatro consumidores de C-19 (U11, U12, U14, U19) tienen arista aprobada.

**R-02.** Se añadió C-30 "Migraciones de base de datos", con dueño compuesto explícito (U2 dueña de la convención y la aserción; cada unidad dueña de sus propias revisiones), mecanismo (una sola historia lineal Alembic + SQL explícito, ADR-002), y modo de fallo declarado (DDL transaccional, `assert_rls_complete` nombra la tabla sin RLS y pone roja la compuerta, segunda cabeza de migraciones bloquea). El contrato está colocado junto a C-10 (sesión de base de datos) sin renumerar el resto, tal como afirma el documento; verificado: hay exactamente 30 secciones `## C-NN` y 30 filas en la tabla de contratos, y coincide con el punto de integración "Migraciones" de `unit-of-work-dependency.md` (línea 317).

**R-03.** C-16 lista ahora a U15 (junto con U7, U8, U10, U11, U21) y excluye explícitamente a U16, con la razón escrita: la llamada de voz usa los adaptadores que U15 construye sobre el puerto, inyectados desde la raíz de composición, y la arista U16→U5 del mapa existe por otra razón (eventos de latencia y registro de uso, cubierta por C-23/C-17). Verificado contra `unit-of-work-dependency.md`: línea 277 confirma U15→U5 es "fábrica por uso, taxonomía de errores, registro de uso y techo" (lo que C-16 cubre), y línea 280 confirma U16→U5 es "eventos de latencia y registro de uso" (lo que C-16 dice que NO cubre). La distinción evita exactamente la violación de la convención 5b de `team.md` (SDK de proveedor solo en su adaptador) que el hallazgo original señalaba como riesgo.

**R-04.** La regla 1 se reescribió: "Cada parte de un contrato tiene un solo dueño... Siete unen dos superficies que no se pueden separar sin partir el acuerdo en dos mitades inútiles, y entonces el dueño es compuesto y con el reparto escrito", nombrando explícitamente los siete contratos (C-07, C-08, C-15, C-16, C-25, C-27, C-28) con el reparto de cada uno. Se verificó que cada uno de los siete efectivamente declara su reparto en su propia sección (por ejemplo C-16: "U5 el puerto de modelo y embeddings, U15 los de voz"). La regla ya no se contradice con la tabla.

### Nuevos hallazgos de esta revisión

Ninguno. No se encontraron contradicciones nuevas ni referencias rotas.

### Verificación del cambio `/api/v1` → `/api`

Comprobado con `grep` sobre todo el documento: las únicas dos apariciones de "v1" son (a) la nota histórica de CD-2, que documenta explícitamente que la primera versión de este documento proponía `/api/v1` y ya no la usa, y (b) la frase "la ruta sin versión queda congelada como v1" al describir el disparador futuro de introducir `/api/v2` — coherente con la decisión y no un `/api/v1` huérfano. `C-01` fija la base en `servers: [{ url: /api }]` dentro del bloque OpenAPI compartido, y `C-07` usa `Path=/api` en su cookie. La regla de propiedad 3 (cambios rompientes) se actualizó para reflejar el mismo mecanismo: "mientras el único consumidor sea la interfaz de este repositorio, el cambio rompiente... entra en el mismo commit... el día que aparezca un consumidor fuera del repositorio se introduce `/api/v2`". No se encontró ningún rastro de `/api/v1` fuera de la nota histórica ni ninguna sección que siga usando el prefijo antiguo en una ruta, cabecera o ejemplo de código. El cambio quedó aplicado de forma consistente en CD-2, C-01, C-07 y la regla de propiedad 3, tal como pedía el resumen de cambios.

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| grep sobre `v1`/`api/v` | 4 coincidencias, todas explicables (nota histórica + descripción del disparador futuro) | Sin `/api/v1` huérfano |
| Conteo de secciones `## C-NN` | 30 | Coincide con la tabla de contratos (30 filas) y con la afirmación "de 29 a 30 contratos" |
| Cruce de consumidores de C-19 contra `unit-of-work-dependency.md` | U11, U12, U14, U19 — las cuatro aristas existen y con la razón citada | Confirma R-01 resuelto |
| Cruce de consumidores de C-16 contra `unit-of-work-dependency.md` | U15 (no U16) coincide con la razón registrada de cada arista (línea 277 vs 280) | Confirma R-03 resuelto |
| Búsqueda del punto de integración "Migraciones" en `unit-of-work-dependency.md` | Presente (línea 317), cubierto ahora por C-30 | Confirma R-02 resuelto |

### Summary

Las cuatro observaciones de la pasada anterior quedaron resueltas con evidencia verificable contra las fuentes aguas arriba (`unit-of-work-dependency.md`, `unit-of-work.md`), y el cambio de Miguel sobre el versionado de la API (`/api` en vez de `/api/v1`) se aplicó de forma consistente en CD-2, C-01, C-07 y la regla de propiedad 3, sin dejar ningún `/api/v1` huérfano. El nuevo contrato C-30 tiene dueño, mecanismo y modo de fallo declarados, y no contradice ninguna decisión aprobada (ADR-002, M9/F9.1). El documento queda listo para servir de base a Construcción.
