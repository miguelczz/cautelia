# AI-DLC Guide - Indice

> Guia personalizada del equipo para implementar el framework AI-DLC. Cubre Pasos 1-33 (Inception, Construction, Operations, Harness Engineering, Skills).
> Dividida por fase para facilitar navegacion y reducir contexto.

---

## Archivos

| # | Archivo | Contenido | Pasos |
|---|---------|-----------|-------|
| 0 | [00-overview.md](00-overview.md) | Vision general del framework, las 3 fases, relacion Inception-Construction | — |
| 1 | [01-inception-setup.md](01-inception-setup.md) | Descarga del framework, inicializacion del proyecto, estructura de carpetas | 1-2 |
| 2 | [02-inception-analysis.md](02-inception-analysis.md) | Requirements Analysis, User Stories, Personas, Reverse Engineering | 3-5 |
| 3 | [03-inception-design.md](03-inception-design.md) | Workflow Planning, Application Design, Units Generation | 6-8 |
| 4 | [04-construction-prep.md](04-construction-prep.md) | Retomar framework entre sesiones, olas de construccion, per-unit loop | 9-10 |
| 5 | [05-construction-design.md](05-construction-design.md) | Diseno Funcional, NFR Requirements, NFR Design, Infrastructure Design | 11-14 |
| 6 | [06-construction-units-codegen.md](06-construction-units-codegen.md) | Loop de Construction aplicado a las 6 Units, Code Generation prep | 15-16 |
| 7 | [07-pre-codegen-strategy.md](07-pre-codegen-strategy.md) | Revision estrategica, Guias, Git Strategy, Playbook, Bootstrap, Deps, Roadmap | 17-23 |
| 8 | [08-setup-operativo.md](08-setup-operativo.md) | Setup operativo consolidado: PM (Linear), repo GitHub, pre-commit, dev bootstrap, CLAUDE.md | 11*-16* |
| 9 | [09-security-validation.md](09-security-validation.md) | Extension de seguridad AIDLC (15 reglas), Checkpoints de validacion entre Units | 17*-18* |
| 10 | [10-build-test-cierre.md](10-build-test-cierre.md) | Build & Test formal, Auditoría de compliance, Aprobacion formal, Linear setup | 26-29 |
| 11 | [11-operations.md](11-operations.md) | Fase Operations: 7 stages, infrastructure tests, production readiness, closure protocol | 30-31 |
| 12 | [12-harness-engineering.md](12-harness-engineering.md) | Harness Engineering: piramide de enforcement, 16 gates, CI feedback loop, hooks, progressive disclosure | 32 |
| 13 | [13-skills-agents.md](13-skills-agents.md) | Agent Skills y Sub-Agentes: anatomia SKILL.md, patrones, sub-agentes, prueba adversarial | 33 |

## Documento complementario

| Archivo | Contenido |
|---------|-----------|
| [GUIA_HARNESS_SKILLS_AGENTES.md](GUIA_HARNESS_SKILLS_AGENTES.md) | Referencia completa de Harness Engineering, Skills y Agentes para Claude Code. Sintetizada de 3 fuentes (harness_engineering.docx, agent_harness_tools.docx, agent_skills_skillmd.docx). Incluye las 8 lecciones del caso OpenAI/Codex, piramide de enforcement, anatomia de SKILL.md, anti-patrones, y checklist de produccion. |

> **Nota**: Los archivos 08 y 09 tienen numeracion de pasos con `*` porque consolidan secciones que se agregaron despues y complementan los pasos originales (07).

## Como usar

1. **Identifica en que fase estas** del framework AI-DLC
2. **Abre solo el archivo relevante** — cada uno es autocontenido
3. **Si necesitas la vision general**, empieza por `00-overview.md`

## Origen

Estos archivos se generaron a partir de `ai-dlc_guide.md` (4,109 lineas) para mejorar la navegacion y reducir el contexto necesario al consultar una fase especifica.
