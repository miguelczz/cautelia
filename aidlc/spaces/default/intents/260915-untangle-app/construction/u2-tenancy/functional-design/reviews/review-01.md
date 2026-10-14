## Review

**Verdict:** NOT-READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-09-20T15:48:19Z
**Iteration:** 1

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Critical | `construction/u2-tenancy/functional-design/functional-design-questions.md` > Q3, y su aplicación en `rules.md` > BR3.2 y `functional-spec.md` > Flujo 4 (Canje) | La pregunta Q3 afirma que "ningún documento aprobado resuelve" si el enlace firmado se puede canjear más de una vez, y a partir de esa premisa el diseño decide que es reutilizable mientras no caduque (BR3.2, FD-U2-3). Pero el contrato aprobado ya fija lo contrario: la tabla de decisiones de Contract Design registra explícitamente, como una de las siete decisiones que Miguel respondió en esa etapa, `CD-5 — Cómo viaja la credencial: "... el enlace firmado se canjea una vez ..."` (`inception/contract-design/contract-summary.md`, tabla "Decisiones de esta etapa", fila CD-5), y el propio texto de C-07 repite la misma frase ("la pantalla lo lee, lo canjea una vez y limpia la dirección", sección `## C-07 — Acceso del visitante por enlace firmado`). U2 construyó BR3.2, BR3.3 y BR3.4 (y el estado "canjeado → canjeado" del diagrama de estados) sobre una lectura de "reutilizable" que contradice ese CD-5 aprobado, sin señalar la contradicción a Miguel: la pregunta Q3 se le presentó como una decisión nueva y libre, no como una posible reversión de algo que él ya había decidido en Contract Design. | Antes de aprobar, reconciliar explícitamente con Miguel: o (a) se confirma que CD-5/C-07 hablaba solo del mecanismo de lectura del fragmento en el cliente (una llamada de canje por carga de página) y no de invalidar el token en el servidor tras el primer uso, y esa lectura se dice por escrito en `contract-summary.md` para que no vuelva a leerse como "un solo uso"; o (b) se revierte Q3 a un solo canje por token y se corrigen BR3.2, BR3.3, BR3.4, el estado "canjeado" del diagrama y el escenario 5 de punta a punta en `functional-spec.md`. Cualquiera de las dos requiere una decisión humana, no una corrección silenciosa, porque cambia el comportamiento de seguridad del enlace y lo que U14 va a construir sobre él. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| `python3 -m json.tool traceability.json` | PASS | El JSON parsea sin errores. |
| Verificación cruzada `traceability.json` ↔ `rules.md` | PASS | Los 27 `BRx.y` de `rules.md` (BR1.1–BR1.11, BR2.1–BR2.6, BR3.1–BR3.6, BR4.1–BR4.4) aparecen todos, cada uno una sola vez, entre `coverage[].target` y `reverse[].target`; no hay ninguno huérfano ni citado sin existir. |
| Verificación cruzada `traceability.json` ↔ `stories.md` | PASS | Los nueve `AC4.11.1`–`AC4.11.5` y `AC5.7.1`–`AC5.7.4` citados en `upstream_ids` y `coverage` existen en `stories.md` con esa numeración exacta, y su texto (política por tabla, punto único de sesión, consulta cruzada vacía, compuerta en cada entrega, escenario contra el despliegue vivo, caducidad y verificación de la credencial, rechazo indistinguible, agente de cuenta sin aprobar, ninguna credencial publicada) corresponde a las reglas que la trazabilidad les asigna. |
| Verificación cruzada `entities.md`/`rules.md` ↔ `components.md` (`TenantIdentity`) | PASS (con precisiones documentadas) | Las cuatro entidades del catálogo aprobado (`Tenant`, `StaffPrincipal`, `CaseAccessLink`, `VisitorKey`) están presentes con sus atributos base; los campos añadidos (`token_digest`, `redeemed_count` en `CaseAccessLink`; `tenant_id` en `VisitorKey`; los campos de C-25 en `Tenant`) están cada uno justificado por una regla o un contrato citado, y el propio documento los declara como precisiones, no como divergencias silenciosas. |
| Verificación cruzada con contratos C-07, C-10, C-11, C-25, C-30 | 4 de 5 consistentes; C-07 en contradicción (ver R-01) | C-10 (sesión única, `assert_rls_complete`, `NOBYPASSRLS`, `NULLIF`), C-11 (`VisitorDataPurger`, `PurgeResult` con `name`/`deleted`/`kept`) y C-25 (esquema de `tenant.yaml`, `config_version`, validación aislada por carpeta) coinciden dato por dato con `entities.md` y `rules.md`. C-30 (una tabla trae su aislamiento en la misma revisión, una sola cabeza, reversible) coincide con BR1.10 y BR1.11. C-07 es el único que no coincide, por el motivo de R-01. |

### Summary

El modelo de entidades, el mapa de aislamiento por punto único de sesión y la trazabilidad hacia US4.11/US5.7 están completos, son comprobables y no tienen referencias rotas. El único problema de fondo es de bulto: el diseño funcional decidió, presentándolo como una pregunta abierta, algo que Contract Design ya había decidido con Miguel en sentido contrario (CD-5, "el enlace firmado se canjea una vez"), y construyó tres reglas de negocio sobre esa reversión sin decírselo. Es corregible con una pregunta a Miguel, pero no debería aprobarse sin que él la responda sabiendo que hay una contradicción y no una decisión nueva.
