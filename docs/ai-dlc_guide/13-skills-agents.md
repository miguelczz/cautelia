## Paso 33 — Agent Skills y Sub-Agentes

> **Objetivo**: Dominar el sistema de extensiones de Claude Code — Skills y Sub-Agentes — para encapsular conocimiento del dominio, automatizar tareas repetitivas y escalar operaciones complejas con agentes paralelos. Sin Skills, cada sesion empieza de cero. Con Skills bien disenados, el agente opera como un miembro senior del equipo.

---

### 33.1 — Que es un Agent Skill

Un **Skill** es la unidad de extension de Claude Code. Encapsula instrucciones, contexto, scripts y referencias que se cargan cuando son relevantes para ejecutar tareas especializadas de forma confiable.

La diferencia con otros conceptos es sutil pero critica:

| Concepto | Que es | Persistencia |
|----------|--------|-------------|
| **Prompt** | Texto efimero del usuario | No reutilizable — se pierde al cerrar la sesion |
| **Tool** | Funcion nativa de Claude Code (Bash, Read, Edit...) | Ejecucion puntual — siempre disponible pero sin memoria |
| **Skill** | Paquete de conocimiento + instrucciones + scripts | Persiste en el proyecto, se activa cuando es relevante |

**Analogia**: Un prompt es una instruccion verbal. Un tool es un destornillador. Un Skill es un manual de procedimientos con herramientas incluidas que el agente consulta automaticamente cuando aplica.

**Leccion del proyecto ExpertIA**: Antes de implementar Skills, cada sesion de code generation requeria re-explicar las convenciones hexagonales, los patrones de RLS, y la estructura de migraciones. Con el Skill `new-domain-entity`, esas 47 reglas se cargan automaticamente cuando el usuario pide crear una entidad.

---

### 33.2 — Anatomia de un SKILL.md

Todo Skill vive en un archivo `SKILL.md` dentro de `.claude/skills/{nombre-del-skill}/`. El archivo tiene dos partes: frontmatter YAML y cuerpo Markdown.

#### Frontmatter obligatorio

```yaml
---
name: pdf-processing          # lowercase, hyphens, max 64 chars
description: >                # Max 1024 chars, no XML tags
  Extracts text and tables from PDF files,
  converts to structured JSON, and validates
  against expected schemas.
---
```

#### Reglas del frontmatter

| Campo | Reglas | Ejemplo valido | Ejemplo invalido |
|-------|--------|----------------|------------------|
| `name` | Solo lowercase + numeros + hyphens. No puede contener 'anthropic' ni 'claude' | `new-domain-entity` | `My_Skill`, `claude-helper` |
| `description` | No vacia, max 1024 chars, sin tags XML. Tercera persona | `"Genera entidades de dominio..."` | `"Yo puedo ayudarte a..."` |

#### Campos opcionales

| Campo | Proposito | Ejemplo |
|-------|-----------|---------|
| `user-invocable` | Si el usuario puede invocarlo con `/nombre` | `true` |
| `allowed-tools` | Restringe que tools puede usar el Skill | `["Bash", "Read", "Edit"]` |
| `argument-hint` | Texto de ayuda para el argumento | `"<entity-name>"` |

#### Cuerpo del SKILL.md

Despues del frontmatter viene Markdown libre con las instrucciones. Aqui va el conocimiento del dominio, reglas, ejemplos y referencias.

```markdown
---
name: new-domain-entity
description: >
  Generates a domain entity with value objects,
  repository ABC, and Alembic migration following
  hexagonal architecture conventions.
---

## Instructions

When the user asks to create a new domain entity:

1. Read `REFERENCE.md` for naming conventions
2. Generate files following the template in `FORMS.md`
3. Run validation script: `bash scripts/validate-entity.sh`

## Rules

- All entities MUST have `tenant_id` field (RLS requirement)
- Repository interface goes in `domain/ports/`, implementation in `infra/adapters/`
- Never generate the migration without confirming the entity fields first
```

---

### 33.3 — Progressive Disclosure (4 Capas)

El sistema de Skills no carga todo de golpe. Usa **Progressive Disclosure** para minimizar el consumo de tokens:

| Capa | Que se carga | Cuando | Costo en tokens |
|------|-------------|--------|----------------|
| **1 - Startup** | Solo `name` + `description` de TODOS los Skills | Siempre, al iniciar sesion | Minimo (~50 tokens por Skill) |
| **2 - Activacion** | El `SKILL.md` completo | Cuando el contexto es relevante | Moderado (~500-2000 tokens) |
| **3 - Referencias** | `FORMS.md`, `REFERENCE.md`, archivos auxiliares | Solo si el Skill los lee explicitamente | Cero hasta que se leen |
| **4 - Scripts** | Scripts se EJECUTAN via Bash | Solo cuando se invocan | Solo el OUTPUT consume tokens |

#### Estructura de directorio

```
.claude/
└── skills/
    ├── new-domain-entity/
    │   ├── SKILL.md              # Capa 2: instrucciones principales
    │   ├── FORMS.md              # Capa 3: templates de archivos
    │   ├── REFERENCE.md          # Capa 3: convenciones del proyecto
    │   └── scripts/
    │       └── validate-entity.sh  # Capa 4: validacion automatica
    ├── new-migration/
    │   ├── SKILL.md
    │   └── scripts/
    │       └── check-rls.py
    └── review-hexagonal/
        ├── SKILL.md
        └── REFERENCE.md
```

**Implicacion practica**: Un proyecto con 20 Skills solo paga ~1000 tokens al inicio. El Skill activo paga su SKILL.md completo. Los archivos de referencia solo se pagan si el agente los necesita. Los scripts solo pagan su output.

**Leccion del proyecto ExpertIA**: Inicialmente se metieron todas las reglas hexagonales en CLAUDE.md (3200 tokens cargados SIEMPRE). Al moverlas a `review-hexagonal/REFERENCE.md`, esos tokens solo se consumen cuando el agente revisa boundaries — un ahorro del 90% en sesiones que no tocan arquitectura.

---

### 33.4 — Activacion: Implicita vs Explicita

Un Skill puede activarse de dos formas:

| Tipo | Como se activa | Ejemplo del usuario | Que pasa internamente |
|------|---------------|--------------------|-----------------------|
| **Implicita** | El modelo detecta relevancia por el contexto | *"Crea la entidad Subscription con campos name y price"* | Claude lee las descriptions de todos los Skills, determina que `new-domain-entity` aplica, y carga su SKILL.md |
| **Explicita** | El usuario invoca con `/nombre` | *"/new-domain-entity Subscription"* | Claude carga el SKILL.md directamente sin evaluar relevancia |

#### Cuando usar cada una

- **Implicita**: Para usuarios que no conocen los Skills disponibles. Funciona bien cuando la `description` es precisa y el contexto es claro.
- **Explicita**: Para operaciones criticas donde quieres asegurar que el Skill correcto se active. Tambien cuando el contexto es ambiguo.

> **Tip**: Si un Skill no se activa implicitamente cuando deberia, el problema casi siempre esta en la `description`. Reescribela con verbos de accion y contexto especifico.

---

### 33.5 — Tres Principios de Concision

#### Principio 1: Claude ya es inteligente — no sobre-expliques

Claude Code tiene conocimiento profundo de programacion, patrones de diseno y mejores practicas. El Skill debe aportar lo que Claude NO sabe: convenciones especificas del proyecto, reglas de negocio, patrones propietarios.

```markdown
# MAL — sobre-explicacion
## How to create a Python class
A class in Python is defined using the `class` keyword...

# BIEN — conocimiento del proyecto
## Entity conventions
- All entities extend `BaseEntity` from `domain/shared/`
- tenant_id is REQUIRED (RLS policy depends on it)
- Use `EntityId` value object, never raw UUID
```

#### Principio 2: Curar ≠ Acumular

Un proyecto sano tiene **maximo ~20 Skills activos**. Cada SKILL.md debe tener **menos de 500 lineas**. Si un Skill crece mas, es senal de que necesita dividirse o mover contenido a archivos de referencia.

| Senal | Accion |
|-------|--------|
| SKILL.md > 500 lineas | Extraer secciones a REFERENCE.md |
| > 20 Skills en el proyecto | Consolidar Skills relacionados o archivar los obsoletos |
| Skill cubre 3+ dominios | Dividir en Skills por dominio |

#### Principio 3: Composicion > Monolito

Un Skill efectivo es un orquestador ligero que compone referencias y scripts bajo demanda — no un bloque monolitico que intenta cubrir todo.

```
# Monolito (malo): 1 archivo de 800 lineas
new-domain-entity/SKILL.md  → 800 lineas con todo adentro

# Composicion (bueno): orquestador + referencias
new-domain-entity/
├── SKILL.md          → 120 lineas: flujo + decisiones
├── FORMS.md          → Templates de archivos generados
├── REFERENCE.md      → Convenciones de naming y estructura
└── scripts/
    └── validate.sh   → Verificacion automatica post-generacion
```

---

### 33.6 — Patrones de Diseno para Skills

#### Patron 1: Guia de alto nivel con referencias

El SKILL.md es un flujo de decision corto. Los detalles viven en archivos de referencia que se leen bajo demanda.

```
review-hexagonal/
├── SKILL.md          # "Cuando el usuario pide review, lee REFERENCE.md
│                     #  y verifica imports cruzados entre capas"
├── REFERENCE.md      # Reglas detalladas de boundaries hexagonales
└── scripts/
    └── check-imports.py  # Detecta imports prohibidos automaticamente
```

**Cuando usarlo**: Skills de verificacion/review donde las reglas son muchas pero el flujo es simple.

#### Patron 2: Organizacion por dominio

Para proyectos grandes, un solo directorio de Skill con subdirectorios por area funcional.

```
bigquery-skill/
├── SKILL.md              # Punto de entrada, routing por tipo de tarea
├── queries/
│   ├── REFERENCE.md      # Convenciones de queries
│   └── templates/        # Templates SQL
├── migrations/
│   ├── REFERENCE.md      # Reglas de migracion de schemas
│   └── scripts/
│       └── validate.sh
└── monitoring/
    └── REFERENCE.md      # Dashboards y alertas
```

**Cuando usarlo**: Cuando un dominio tecnico (BigQuery, Kubernetes, etc.) tiene multiples operaciones distintas.

#### Patron 3: Libertad calibrada

El Skill define niveles de libertad segun la operacion:

```markdown
## Freedom levels

### HIGH freedom (creative tasks)
- Naming de variables locales
- Estructura interna de funciones privadas
- Mensajes de log

### MEDIUM freedom (constrained choices)
- Patrones de error handling (elegir entre 3 opciones documentadas)
- Estructura de tests (seguir template pero adaptar assertions)

### LOW freedom (strict compliance)
- Naming de entidades de dominio (MUST match glossary)
- Estructura de directorios (MUST follow hexagonal layout)
- Campos de migracion (MUST include tenant_id)
```

**Cuando usarlo**: Cuando el mismo Skill maneja tanto tareas creativas como tareas con reglas estrictas.

---

### 33.7 — Scripts en Skills

#### Execute vs Read

Los scripts en Skills tienen dos modos de uso:

| Modo | Que hace Claude | Cuando usar |
|------|----------------|-------------|
| **Execute** | Corre el script via `Bash` y usa el output | Validaciones, generacion de codigo, checks automaticos |
| **Read** | Lee el script como referencia sin ejecutarlo | Cuando el script es un ejemplo o template |

#### Principio: Solve, Don't Punt

Un buen script **resuelve** el problema — no solo lo detecta y le dice al usuario que lo arregle.

```python
# MAL — punt (detecta pero no resuelve)
def check_rls():
    for table in get_tables():
        if not has_rls_policy(table):
            print(f"WARNING: {table} missing RLS policy")
    # ...y ahora que? El usuario debe arreglar manualmente

# BIEN — solve (detecta Y corrige)
def ensure_rls():
    for table in get_tables():
        if not has_rls_policy(table):
            migration = generate_rls_migration(table)
            write_migration(migration)
            print(f"FIXED: Generated RLS migration for {table}")
```

#### Ejemplo real del proyecto ExpertIA

```bash
#!/bin/bash
# scripts/validate-entity.sh
# Ejecutado por el Skill new-domain-entity despues de generar archivos

ENTITY_DIR="$1"

# 1. Verificar que existe el archivo de entidad
[ -f "$ENTITY_DIR/entity.py" ] || { echo "FAIL: entity.py not found"; exit 1; }

# 2. Verificar tenant_id
grep -q "tenant_id" "$ENTITY_DIR/entity.py" || { echo "FAIL: missing tenant_id"; exit 1; }

# 3. Verificar repository ABC
[ -f "$ENTITY_DIR/repository.py" ] || { echo "FAIL: repository.py not found"; exit 1; }

# 4. Verificar que no hay imports de infra en domain
grep -rn "from.*infra" "$ENTITY_DIR/" && { echo "FAIL: domain importing from infra"; exit 1; }

echo "PASS: Entity validation complete"
```

---

### 33.8 — Workflow Plan-Validate-Execute

Para operaciones complejas (migraciones, refactors, cambios multi-archivo), el Skill debe seguir un workflow de 6 pasos:

| Paso | Accion | Ejemplo |
|------|--------|---------|
| **1. Analizar** | Leer el estado actual del codigo y entender el contexto | Leer la entidad existente, sus dependencias, tests actuales |
| **2. Generar plan** | Producir un plan detallado de cambios ANTES de tocar archivos | "Voy a crear 4 archivos, modificar 2, y agregar 1 migracion" |
| **3. Validar** | Verificar que el plan no viola restricciones del proyecto | Chequear que no hay conflictos de naming, imports circulares, etc. |
| **4. Pedir aprobacion** | Presentar el plan al usuario y esperar confirmacion explicita | "Este es el plan. Procedo?" |
| **5. Aplicar** | Ejecutar los cambios siguiendo el plan aprobado | Crear archivos, editar imports, generar migracion |
| **6. Verificar** | Correr scripts de validacion post-cambio | `bash scripts/validate-entity.sh` + `pytest` |

**Regla critica**: El paso 4 (aprobacion) NO es opcional para operaciones destructivas o irreversibles. Un Skill que modifica migraciones de base de datos o elimina archivos DEBE pedir confirmacion.

```markdown
# En el SKILL.md:
## Workflow

1. Read current entity structure
2. Generate change plan (list all files to create/modify/delete)
3. Validate plan against REFERENCE.md rules
4. **STOP: Present plan to user and wait for explicit approval**
5. Apply changes following approved plan
6. Run `bash scripts/validate-entity.sh {entity_dir}`
   - If FAIL: fix automatically and re-run
   - If PASS: report success
```

---

### 33.9 — Skills del Proyecto ExpertIA (ADR-043)

El proyecto ExpertIA implemento Skills como parte de su madurez operativa. La decision esta documentada en **ADR-043**.

#### Tier 1 — Implementados y activos

| Skill | Que hace | Archivos que genera |
|-------|----------|-------------------|
| `new-domain-entity` | Genera entidad + value objects + repository ABC | `entity.py`, `value_objects.py`, `repository.py` |
| `new-use-case` | Genera command/query handler + ports | `handler.py`, `command.py` o `query.py`, `port.py` |
| `new-migration` | Genera migracion Alembic con RLS | `versions/{timestamp}_{name}.py` |
| `review-hexagonal` | Verifica boundaries hexagonales | Reporte de violaciones (no genera archivos) |

#### Tier 2 — Planificados (EXP-903, EXP-933)

| Skill | Proposito | Issue |
|-------|-----------|-------|
| `verify-unit` | Corre tests + coverage de una unidad especifica | EXP-903 |
| `review-pr` | Review automatizado de PR contra convenciones | EXP-903 |
| `close-phase` | Cierra una fase AIDLC con todos los artefactos | EXP-903 |
| `session-init` | Inicializa sesion cargando estado actual del proyecto | EXP-933 |
| `smoke-test` | Ejecuta smoke tests post-deploy | EXP-933 |
| `scaffold-route` | Genera endpoint FastAPI con todos los layers | EXP-933 |
| `safe-migrate` | Migracion con backup automatico y rollback | EXP-933 |

---

### 33.10 — Sub-Agentes en Claude Code

Claude Code puede lanzar **sub-agentes** — instancias independientes que ejecutan tareas en paralelo o en aislamiento.

#### Tipos de agentes disponibles

| Tipo | Proposito | Caracteristica clave |
|------|-----------|---------------------|
| **General-purpose** | Tareas delegadas completas | Acceso completo a tools |
| **Explore** | Investigacion y busqueda | Solo lectura, no modifica archivos |
| **Plan** | Generacion de planes de accion | Solo lectura, produce plan estructurado |
| **claude-code-guide** | Consultas sobre Claude Code mismo | Acceso a documentacion interna |

#### Reglas para sub-agentes

1. **Lanzar en paralelo cuando las tareas son independientes**. Si necesitas revisar 3 modulos y ninguno depende del otro, lanza 3 agentes simultaneos.

2. **Usar `isolation: "worktree"`** para copias aisladas del repo. Cada agente trabaja en su propia copia — sin conflictos de archivos.

3. **Descripcion completa de la tarea**. Cada agente arranca sin contexto previo. La descripcion debe incluir TODO lo necesario: que hacer, donde buscar, que reglas seguir.

```markdown
# Ejemplo: delegar review de 3 modulos en paralelo

Lanza 3 agentes Explore en paralelo:

Agent 1: "Revisa el modulo `core/tenant/` — verifica que todos los
imports respetan boundaries hexagonales. Reporta violaciones."

Agent 2: "Revisa el modulo `core/subscription/` — verifica que todos
los imports respetan boundaries hexagonales. Reporta violaciones."

Agent 3: "Revisa el modulo `core/billing/` — verifica que todos los
imports respetan boundaries hexagonales. Reporta violaciones."
```

#### Sub-agentes adversariales planificados (EXP-904)

| Agente | Rol | Que verifica |
|--------|-----|-------------|
| **Verifier** | Verificacion tecnica | Que el codigo generado compila, pasa tests, respeta tipos |
| **Reviewer** | Review de convenciones | Que sigue los patrones del proyecto, naming, estructura |
| **Hygiene** | Limpieza operativa | Que los docs estan actualizados, no hay archivos huerfanos, no hay TODOs olvidados |

---

### 33.11 — Prueba Adversarial de Skills (6 Fases)

Antes de marcar un Skill como "produccion", debe pasar por una prueba adversarial rigurosa:

| Fase | Que hace | Resultado esperado |
|------|----------|-------------------|
| **1. Extraer y Descomponer** | Descomponer el Skill en: decisiones, suposiciones, dependencias, interfaces | Lista categorizada de cada elemento |
| **2. Verificar via Busqueda** | Verificar cada claim contra documentacion real (no confiar en memoria) | Claims marcados como Verificado / No verificado |
| **3. Identificar POCs** | Separar lo resuelto de lo que necesita prueba practica | Lista de POCs necesarios con prioridad |
| **4. Obtener Aprobacion** | Presentar POCs agrupados por riesgo al usuario | Aprobacion explicita para ejecutar |
| **5. Ejecutar POCs** | Correr en directorio temporal, con agentes paralelos si es posible | Resultados concretos (PASS/FAIL) por POC |
| **6. Recorrer Hallazgos** | Organizar resultados en 3 categorias | Confirmado / No resuelto / Riesgo aceptado |

#### Evaluation-Driven Development

Complementario a la prueba adversarial, el desarrollo de Skills sigue un proceso de 5 pasos basado en evaluaciones:

| Paso | Accion |
|------|--------|
| **1** | Identificar gaps — donde falla el Skill sin instrucciones |
| **2** | Crear evaluaciones — casos de prueba concretos con resultado esperado |
| **3** | Baseline — correr evaluaciones sin el Skill para medir el punto de partida |
| **4** | Instrucciones minimas — agregar la menor cantidad de instrucciones que mejoren los resultados |
| **5** | Iterar — repetir pasos 2-4 hasta alcanzar el umbral de calidad |

> **Leccion ExpertIA**: El Skill `new-migration` paso de 60% de acierto (sin instrucciones especificas de RLS) a 95% al agregar 3 lineas sobre `tenant_id` y la convencion de naming de migraciones. La clave fue medir antes de instruir.

---

### 33.12 — Checklist de Skill Listo para Produccion

Antes de considerar un Skill como listo para uso en produccion, verificar cada item:

#### Core Quality

```
[ ] description es clara, en tercera persona, < 1024 chars
[ ] SKILL.md tiene < 500 lineas
[ ] Referencias extraidas a FORMS.md / REFERENCE.md cuando aplica
[ ] Terminologia consistente con el glosario del proyecto
[ ] Al menos 2 ejemplos concretos de uso en el SKILL.md
[ ] Nivel de libertad definido para cada tipo de decision
[ ] Workflow documentado con pasos numerados
[ ] Condiciones de error documentadas (que hacer cuando falla)
[ ] No duplica conocimiento que ya esta en CLAUDE.md
[ ] name cumple formato: lowercase + hyphens, sin 'anthropic'/'claude'
```

#### Scripts y Codigo

```
[ ] Todos los scripts tienen manejo de errores (exit codes, mensajes claros)
[ ] No hay magic numbers — constantes documentadas
[ ] Paths son relativos al proyecto, no absolutos hardcodeados
[ ] Dependencias externas documentadas (que debe estar instalado)
[ ] Scripts siguen principio Solve Don't Punt
[ ] Output de scripts es parseable (JSON o formato estructurado)
[ ] Scripts son idempotentes — correr 2x produce el mismo resultado
```

#### Testing y Validacion

```
[ ] Al menos 3 evaluaciones (caso feliz, caso edge, caso de error)
[ ] Probado con diferentes modelos (Opus, Sonnet) si es posible
[ ] Stress test: funciona con input inesperado sin romper el proyecto
[ ] Prueba adversarial de 6 fases completada
[ ] Resultados documentados en ADR correspondiente
```

---

### 33.13 — Prompt ejemplo

```
Quiero crear un Skill para generar endpoints FastAPI completos
(scaffold-route). Debe seguir la arquitectura hexagonal del proyecto:
- Route en api/routes/
- Schema Pydantic en api/schemas/
- Use case handler en application/
- Port en domain/ports/

Usa el patron de guia de alto nivel con referencias.
Incluye un script de validacion que verifique que no hay imports
cruzados entre capas.
```
