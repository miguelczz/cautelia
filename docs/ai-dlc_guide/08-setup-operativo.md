## Paso 11 — Setup Operativo (antes de Code Generation)

> **Objetivo**: Convertir el diseño completo en un entorno de trabajo real — herramientas de PM configuradas, repo listo, ambiente de desarrollo funcional. Sin este paso, el code gen arranca sin estructura y colapsa en la unidad 3.

### 11.1 — Crear el ambiente virtual (venv)

Dentro del workspace del proyecto, crear un ambiente virtual de Python para aislar dependencias:

```bash
cd {workspace_root}
python3 -m venv venv
source venv/bin/activate
```

> **Tip**: Agrega `venv/` al `.gitignore` para no subir el ambiente al repo.

### 11.2 — Setup de Project Management (Linear)

El backlog de user stories debe vivir en una herramienta visible para todo el equipo — no solo en el aidlc-state.md que es un tracker interno del AI-DLC.

#### Que crear en Linear (o herramienta equivalente)

```
Workspace: {nombre del equipo}
  └── Team: {nombre del proyecto}
       └── Project: {nombre de la plataforma}
             ├── 1 Epic por unidad de construccion
             └── 1 Issue por user story
```

#### Labels recomendados

| Categoria | Labels | Proposito |
|-----------|--------|-----------|
| **Unit** | `unit:{nombre}` por cada unidad | Filtrar issues por bounded context |
| **Persona** | `persona:{nombre}` por cada persona del proyecto | Filtrar por usuario final |
| **Tipo** | `type:greenfield`, `type:brownfield` | Distinguir codigo nuevo vs existente |

#### Prompt para crear la estructura

```
Crea en Linear la estructura del proyecto:
1. Un proyecto llamado "{nombre}"
2. Labels: unit:{nombre} por cada unidad, persona:{nombre} por cada persona, type:greenfield, type:brownfield
3. Un epic por cada unidad de construccion (usa la tabla de aidlc-docs/inception/plans/linear-setup.md)
4. Un issue por cada user story (usa la tabla completa de linear-setup.md)
5. Todos los issues en estado "Backlog"
6. Asigna los labels correspondientes a cada issue
```

#### Workflow de estados durante code gen

```
Backlog → Todo → In Progress → In Review → Done
```

- **Backlog**: Todas las stories al inicio
- **Todo**: Stories priorizadas para el unit activo
- **In Progress**: Claude (o el dev) esta implementando
- **In Review**: Codigo generado, pendiente review/merge
- **Done**: PR mergeado, issue cerrado automaticamente via `Closes LIN-{id}`

#### Convencion de commits con Linear

```bash
# Referencia (no cierra el issue):
feat(core/tenant): implement CreateTenant use case — refs LIN-2

# En el PR (cierra el issue al merge):
Closes LIN-2
```

#### Linkeo GitHub ↔ Linear

1. Linear > Settings > Integrations > GitHub: conectar el repo
2. Habilitar: "Close issues when PR is merged with `Closes LIN-{id}`"
3. Opcional: auto-link PRs cuando el branch name contiene el issue ID

### 11.3 — Checklist de Setup Operativo

Antes de generar la primera linea de codigo, verificar que todo esta en su lugar:

```
HERRAMIENTAS DE PM:
  [ ] Proyecto creado en Linear (o equivalente)
  [ ] Labels configurados (unit:*, persona:*, type:*)
  [ ] Epics creados (uno por unidad)
  [ ] Issues creados (uno por user story) — todos en "Backlog"
  [ ] Integracion GitHub ↔ Linear activa

REPOSITORIO:
  [ ] Repo GitHub creado (privado recomendado)
  [ ] Branch main protegido (require PR, no direct push)
  [ ] .gitignore configurado (venv/, __pycache__/, .env, etc.)

AMBIENTE DE DESARROLLO:
  [ ] venv creado y activado
  [ ] pyproject.toml (o equivalente) con dependencias base
  [ ] docker-compose.yml con servicios de desarrollo
  [ ] make bootstrap (o equivalente) funciona desde cero
  [ ] Pre-commit hooks instalados (linter + secrets scan)

DOCUMENTACION:
  [ ] CLAUDE.md tiene el playbook de code gen
  [ ] Guias practicas creadas (git workflow, local dev setup, code gen workflow)
  [ ] aidlc-state.md actualizado: proxima etapa = Code Gen Unit 1
```

### 11.4 — Flujo de Construction (por Unit)

Una vez completo el setup, la construccion sigue este flujo **por cada unidad**:

```
┌─────────────────────────────────────────────────────┐
│  UNIT N                                             │
│                                                     │
│  1. Leer Linear → seleccionar story del epic activo │
│  2. Mover issue → "In Progress"                     │
│  3. Generar codigo (orden hexagonal):                │
│     domain/ + tests → application/ + tests →        │
│     infrastructure/ + tests → api/ + tests          │
│  4. Quality gate (imports, tests pasan)              │
│  5. Commit: feat({unit}): ... — Closes LIN-{id}     │
│  6. Repetir 1-5 para cada story del unit            │
│  7. PR: unit/{N}-{name} → main                      │
│  8. CI/CD corre todos los tests                     │
│  9. Review + Merge + Tag                            │
│ 10. Retrospectiva lessons learned                   │
│                                                     │
│  ✅ Unit N completo → avanzar a Unit N+1            │
└─────────────────────────────────────────────────────┘
```

> **Regla de oro**: No avanzas al Unit N+1 hasta que el Unit N esta mergeado y tagueado. Cada unit llega probado, no se "construye todo y luego se prueba".

### 11.5 — Estrategia de Testing (que corre y cuando)

```
POR CADA STORY (durante code gen):
  └─ pytest tests/unit/{unit}/     ← tests unitarios de lo que se genero

POR CADA PR (antes de merge):
  ├─ pytest tests/unit/            ← todos los unit tests
  ├─ pytest tests/contracts/       ← si toca interfaces entre units
  ├─ pytest tests/integration/     ← DB, cache, message broker reales
  ├─ pytest tests/clinical/        ← si toca logica clinica (proyectos medicos)
  ├─ linter (ruff, eslint, etc.)   ← formato y calidad de codigo
  └─ secrets scan (gitleaks, etc.) ← no secrets hardcodeados

AL FINAL (todos los units completos):
  ├─ Integration testing cross-unit ← interacciones entre modulos
  ├─ E2E tests                     ← flujos de usuario completos
  ├─ Performance tests             ← si aplica
  └─ Security tests                ← si aplica
```

#### Prompt para iniciar una sesion de code gen

```
Inicia una sesion de code generation.
1. Lee aidlc-state.md para ver el unit activo y stories pendientes
2. Corre git log unit/{N} --oneline para ver que stories ya tienen commit
3. Lee el functional design del unit activo
4. Identifica la siguiente story sin commit
5. Genera el codigo siguiendo el orden hexagonal (domain → application → infrastructure → api)
6. Corre los tests y verifica que pasan
7. Haz commit con la convencion: feat({unit}): descripcion — Closes LIN-{id}
```

#### Prompt para retomar una sesion interrumpida

```
Retoma la sesion de code gen:
1. git log unit/{N} --oneline → que stories tienen commit
2. git status → hay trabajo sin commitear? Completa y commitea primero
3. Retoma desde la siguiente story pendiente
```

### 11.6 — Secuencia de Build (dependencias entre units)

No todos los units se construyen en serie. La secuencia depende de las dependencias:

```
Unit 1: Core Platform           ← PRIMERO (no depende de nadie)
    │
    ├── Unit 2: CV Pipeline ──┐  ← dependen de Core
    ├── Unit 4: Chat & RAG  ──┤  ← pueden construirse en paralelo
    │                          │
    │   Unit 3: DDH Plugin  ←─┘  ← depende de Pipeline
    │
    │   Unit 5: MLOps        ← depende de Core + Pipeline
    │
    └── Unit 6: Frontend     ← depende de todos los backend
```

> **Tip**: Si el equipo tiene multiples desarrolladores, Unit 2 y Unit 4 se pueden construir en paralelo porque no comparten dependencias directas.

#### Prompt para generar la secuencia de build

```
Analiza las dependencias entre las unidades de construccion y genera:
1. La secuencia de build (orden de construccion)
2. Que units se pueden paralelizar
3. En que momento cada unit puede empezar (cuando el unit padre tiene domain/ + application/ports/ estables)
```

---

## Paso 15: SETUP OPERATIVO — Preparar todo antes de code gen

Antes de escribir la primera linea de codigo, hay que preparar la infraestructura operativa del proyecto. Esta fase no la genera el framework automaticamente — es responsabilidad del equipo.

### 15.1 El checklist completo

| # | Tarea | Que hace | Estado esperado |
|---|-------|---------|----------------|
| 1 | **Project Management (Linear/Jira)** | Crear proyecto, labels, issues (1 por user story) | Backlog completo visible |
| 2 | **Repositorio GitHub** | Crear repo, README, .gitignore, LICENSE | Repo vacio listo |
| 3 | **Pre-commit hooks** | Linter + secrets scan | Calidad desde el commit 1 |
| 4 | **Proyecto base** | pyproject.toml, docker-compose, Makefile, estructura carpetas | Ambiente funcional |
| 5 | **CLAUDE.md en repo de codigo** | Copiar playbook + reglas al repo nuevo | Agente sabe como trabajar |
| 6 | **PM tool <-> GitHub** | Conectar integracion para cierre automatico de issues | `Closes LIN-{id}` funciona |

> **Por que esto importa**: Sin esta infraestructura, el code gen produce codigo sin trazabilidad, sin calidad automatizada, y sin visibilidad para el equipo. Los 30 minutos que toma este setup ahorran horas de desorden despues.

### 15.2 Crear proyecto en herramienta de PM

Independientemente de si usas Linear, Jira, GitHub Projects, o cualquier otra herramienta, la estructura es la misma:

```
Proyecto: [Nombre del producto]
  ├── Labels:
  │     ├── unit:{nombre-unidad}  (1 por unidad de construccion)
  │     ├── persona:{nombre}      (1 por persona/actor del sistema)
  │     └── type:{greenfield|brownfield}
  │
  ├── Epics/Milestones: 1 por unidad de construccion
  │     ├── Unit 1 — [nombre] (prioridad: 1)
  │     ├── Unit 2 — [nombre] (prioridad: 2)
  │     └── ...
  │
  └── Issues: 1 por user story
        ├── Titulo: US-XXX: [descripcion]
        ├── Labels: unit + persona + type
        ├── Estado inicial: Backlog
        └── Descripcion: user story + referencia a stories.md
```

#### Prompt para crear la estructura de PM

```
Basandote en las user stories en aidlc-docs/inception/user-stories/stories.md
y las unidades en aidlc-docs/inception/units/unit-of-work.md, genera:

1. Lista de labels necesarios (unit:*, persona:*, type:*)
2. Lista de epics (1 por unidad, con prioridad segun build sequence)
3. Lista completa de issues (1 por user story) con:
   - Titulo: US-{ID}: descripcion
   - Labels asignados
   - Epic al que pertenece
   - Descripcion con template estandar

Genera todo en formato que pueda ejecutarse via API o copiarse directamente.
```

> **Tip sobre Linear**: Si usas Linear, puedes crear issues via la API GraphQL directamente desde Claude Code usando `curl`. No necesitas un MCP — la API es sencilla y te da control total. Guarda el script para poder recrear el backlog si es necesario.

### 15.3 Flujo de Construction — como se construye cada unit

Una vez que el setup operativo esta completo, la construccion sigue este flujo **incremental por unit**:

```
Unit 1: [primer unit — sin dependencias]
  └─ AIDLC loop (Functional Design → NFR → Infra → Code Gen)
  └─ Tests unitarios + integracion
  └─ PR → CI/CD → Review → Merge → Tag v0.1.0
  └─ Funciona solo

Unit 2 + Unit N (paralelos si no dependen entre si):
  └─ Mismo loop
  └─ Tests + tests de contrato con Unit 1
  └─ PR → Merge → Tag
  └─ Funciona con Unit 1

... asi sucesivamente segun build sequence ...

Al completar todos los units:
  └─ Integration testing cross-unit
  └─ E2E tests (flujos usuario completos)
  └─ Performance tests
  └─ Build & Test final del AIDLC
```

**Lo importante**: No se construye todo y luego se prueba. **Cada unit se construye, se prueba, se mergea, y luego se avanza**. Si Unit 1 falla, no se avanza a Unit 2.

### 15.4 Flujo de Testing — que pruebas corren y cuando

```
POR CADA STORY (durante code gen):
  └─ pytest tests/unit/{unit}/     ← tests unitarios de lo generado

POR CADA PR (al completar un unit):
  ├─ pytest tests/unit/            ← todos los unit tests
  ├─ pytest tests/contracts/       ← contratos entre units (si aplica)
  ├─ pytest tests/integration/     ← DB, cache, storage reales
  ├─ linter (ruff, eslint, etc.)   ← formato + calidad
  └─ secrets scan (gitleaks, etc.) ← no secrets en el codigo

AL FINAL (todos los units completos):
  ├─ Integration testing cross-unit ← flujos que cruzan units
  ├─ E2E tests                      ← flujos usuario completos
  ├─ Performance tests               ← latencia, throughput
  └─ Security tests                  ← OWASP, headers, auth
```

> **Regla de oro**: Cada capa de tests tiene un proposito diferente. Los unit tests verifican logica aislada. Los de integracion verifican que los componentes hablan entre si. Los E2E verifican que el flujo completo del usuario funciona. No son intercambiables — se necesitan todos.

### 15.5 El flujo completo de un story durante code gen

Dentro de cada sesion de code gen, cada user story sigue este ciclo:

```
1. Leer PM tool → seleccionar siguiente story en Backlog
2. Mover issue → "In Progress"
3. Generar codigo (orden hexagonal si aplica):
   domain/ + tests → application/ + tests →
   infrastructure/ + tests → api/ + tests
4. Quality gate:
   - [ ] Tests pasan
   - [ ] Linter pasa
   - [ ] No imports circulares
5. Commit: feat({unit}): descripcion - Closes LIN-{id}
6. Push al branch del unit
7. Repetir 1-6 para cada story del unit
8. PR: branch del unit → main
9. CI/CD corre todos los tests
10. Review + Merge + Tag
```

#### Prompt para iniciar sesion de code gen

```
Estoy iniciando una sesion de code generation.

1. Lee aidlc-docs/aidlc-state.md para confirmar que unit esta activo
2. Lee el functional design del unit activo
3. Revisa git log para ver que stories ya tienen commit
4. Identifica la siguiente story pendiente
5. Implementala siguiendo el orden hexagonal:
   domain/ → application/ → infrastructure/ → api/
   con tests en cada capa

Al terminar, haz commit con: feat({unit}): descripcion - Closes LIN-{id}
```

#### Prompt para retomar sesion interrumpida

```
Retomando sesion de code gen.
1. Corre git log y git status para ver donde quedamos
2. Si hay trabajo sin commitear, completalo y commitea
3. Identifica la siguiente story pendiente
4. Continua la implementacion
```

### 15.6 Git Strategy — ramas, commits, y PRs

La estrategia recomendada para proyectos con multiples unidades:

```
main (protegida — solo PRs)
  │
  ├── unit/1-core-platform      ← 1 branch por unit
  │     ├── commit: feat(core): US-M08 login — Closes LIN-1
  │     ├── commit: feat(core): US-S01 tenant — Closes LIN-2
  │     └── ... (1 commit por story)
  │     └── PR → main (al completar el unit)
  │
  ├── unit/2-cv-pipeline
  │     └── ... mismo patron
  │
  └── unit/N-nombre
        └── ...
```

**Convenciones**:
- Branch: `unit/{N}-{nombre}`
- Commits: `feat|fix|test({scope}): descripcion — Closes LIN-{id}`
- PRs: 1 por unit, cierra todas las stories del unit
- Tags: `v0.{N}.0-{nombre-unit}` al mergear
- Merge: `--no-ff` para mantener historial claro

#### Prompt para formalizar la estrategia git

```
Basandote en las unidades de construccion y la build sequence, genera:

1. ADR para la estrategia git del proyecto (branch naming, commit convention,
   PR strategy, merge policy)
2. Guia practica paso a paso para el equipo:
   - Como crear un branch de unit
   - Como hacer commits durante code gen
   - Como crear el PR al completar un unit
   - Como hacer merge y tagging
```

### 15.7 Dependency Management — herramientas y pre-commit

Definir desde el inicio como se manejan las dependencias y la calidad automatica:

**Para proyectos Python**:
```
pyproject.toml          ← dependencias + config de linter + config de tipos
uv                      ← gestor de dependencias (rapido, moderno)
.pre-commit-config.yaml ← hooks que corren antes de cada commit
  ├── ruff              ← format + lint (reemplaza black + isort + flake8)
  └── gitleaks          ← scan de secrets (no negociable en proyectos con datos sensibles)
```

**Para proyectos Node/TypeScript**:
```
package.json / pnpm-workspace.yaml
eslint + prettier
husky + lint-staged
```

#### Prompt para definir dependency management

```
Define la estrategia de gestion de dependencias para este proyecto:

1. Archivo de dependencias (pyproject.toml / package.json)
2. Gestor de paquetes (uv / pnpm / npm)
3. Pre-commit hooks: que checks automaticos corren antes de cada commit
4. Configuracion de linter y formatter
5. Si hay codigo brownfield: como aislar sus dependencias del greenfield

Genera los archivos de configuracion base (.pre-commit-config.yaml,
seccion [tool.ruff] en pyproject.toml, etc.)
```

### 15.8 Dev Bootstrap — levantar el ambiente local

Para que cualquier desarrollador del equipo pueda empezar a trabajar:

```
# Clonar
git clone [repo-url]
cd [proyecto]

# Levantar servicios (DB, cache, storage, etc.)
docker compose --profile dev up -d

# Seed de datos iniciales (tenant demo, admin, etc.)
make bootstrap

# Instalar dependencias de desarrollo
uv sync --dev          # Python
pnpm install           # Node

# Instalar hooks
pre-commit install

# Verificar que todo funciona
make test
```

#### Prompt para generar la guia de dev bootstrap

```
Genera una guia de setup local para desarrolladores nuevos:

1. Prerrequisitos (Docker, Python, Node, etc.)
2. Pasos de instalacion (clone, docker up, bootstrap, deps)
3. Que servicios levanta docker compose y en que puertos
4. Como verificar que todo esta funcionando
5. Troubleshooting de problemas comunes

La guia debe ser ejecutable de principio a fin sin pedir ayuda.
```

### 15.9 CLAUDE.md — el playbook del agente

Si usas un agente de IA para code gen (Claude Code, Cursor, etc.), necesita instrucciones claras. El `CLAUDE.md` (o equivalente) es el archivo que le dice al agente **como** trabajar en el proyecto.

**Contenido minimo recomendado**:

```markdown
# Code Generation Playbook

## Al iniciar sesion
1. Leer aidlc-state.md → confirmar unit activo
2. git log → ver que stories tienen commit
3. Leer functional design del unit
4. Identificar siguiente story pendiente

## Orden de generacion (hexagonal)
domain/ → application/ → infrastructure/ → api/
Tests junto con cada capa.

## Granularidad
- 1 story = 1 commit
- NUNCA mezclar 2 stories en un commit
- NUNCA commitear sin tests

## Quality gate antes de commit
- Tests pasan
- Linter pasa
- No imports circulares entre capas
```

#### Prompt para generar el CLAUDE.md

```
Genera un CLAUDE.md para el repo de codigo con:

1. Protocolo de inicio de sesion (que leer, que verificar)
2. Orden de generacion de codigo (hexagonal si aplica)
3. Reglas de granularidad (1 story = 1 commit)
4. Quality gate checklist antes de commitear
5. Protocolo para retomar sesiones interrumpidas
6. Manejo de stories cross-unit

Basate en los ADRs de arquitectura y el functional design existente.
```

---

## Resumen: De Inception a Construction

```
INCEPTION (QUE construir)
  ├── Workspace Detection
  ├── Reverse Engineering (brownfield)
  ├── Requirements Analysis
  ├── User Stories + Personas
  ├── Workflow Planning
  ├── Application Design (ADRs, componentes)
  └── Units Generation (bounded contexts, dependencias)

REVISION ESTRATEGICA PRE-CODE-GEN
  ├── Lessons Learned (retrospectiva de inception)
  ├── Revision arquitectonica
  ├── PM tool setup (Linear/Jira)
  ├── Git strategy (branches, commits, PRs)
  ├── Code gen playbook (CLAUDE.md)
  ├── Dev bootstrap guide
  └── Dependency management

SETUP OPERATIVO
  ├── PM tool: proyecto + labels + issues
  ├── GitHub: repo + branch protection
  ├── Pre-commit: linter + secrets scan
  ├── Proyecto base: deps + docker + makefile
  ├── CLAUDE.md en repo de codigo
  └── PM tool <-> GitHub integration

CONSTRUCTION (COMO construirlo)
  Por cada Unit (en orden de build sequence):
    ├── Functional Design (si aplica)
    ├── NFR Requirements (si aplica)
    ├── NFR Design (si aplica)
    ├── Infrastructure Design (si aplica)
    ├── Code Generation (siempre)
    └── Tests + PR + Merge + Tag

  Build & Test Final:
    ├── Integration testing cross-unit
    ├── E2E tests
    ├── Performance tests
    └── Security tests
```

> **El resultado final**: Un producto construido con trazabilidad completa — desde el requerimiento de negocio hasta el commit de codigo, pasando por user stories, ADRs, functional design, y tests. Cualquier persona puede recorrer esa cadena hacia atras para entender por que se tomo cada decision.

---

## Paso 16: SETUP OPERATIVO — Crear repositorio y scaffold del proyecto

### 16.1 Crear el repositorio en GitHub

> **LECCION APRENDIDA — Error comun que debes evitar:**
>
> NO crees el repo en una carpeta separada y luego copies archivos al workspace AIDLC. La metodologia AIDLC requiere que el codigo viva **dentro del workspace** (la misma carpeta donde estan `aidlc-docs/`, `CLAUDE.md`, y el PRD). Si clonas el repo en otra carpeta, terminas con dos ubicaciones desincronizadas, git anidado, y desorden.
>
> **Lo correcto**: Inicializa git **dentro del workspace AIDLC**, crea el repo vacio en GitHub, y configura el remote desde ahi. Nunca al reves.

```
# 1. Ir al workspace AIDLC (donde ya estan aidlc-docs/, CLAUDE.md, PRD)
cd [tu-workspace-aidlc]/

# 2. Inicializar git AQUI (dentro del workspace)
git init
git branch -M main

# 3. Crear repo VACIO en GitHub (sin README, sin .gitignore, sin licencia)
gh repo create [nombre-proyecto] --private --description "Descripcion" --source=. --remote=origin

# O si prefieres crear el repo desde la web de GitHub:
# - Crear repo vacio (sin inicializar)
# - Luego agregar el remote manualmente:
git remote add origin https://github.com/[usuario]/[nombre-proyecto].git
```

> **Por que crear el repo vacio?** Si GitHub inicializa el repo con README o .gitignore, tendras conflictos al pushear desde tu workspace que ya tiene archivos. Siempre crea el repo vacio y pushea desde el workspace AIDLC.

La estructura final debe verse asi:
```
[carpeta-padre]/
├── [tu-workspace-aidlc]/         ← ESTE es el git repo
│   ├── .git/                     ← git vive AQUI
│   ├── CLAUDE.md                 ← reglas AIDLC + playbook
│   ├── PRD_[proyecto].md         ← documento de producto
│   ├── aidlc-docs/               ← documentacion del proyecto
│   ├── [paquete_codigo]/         ← codigo de la aplicacion
│   ├── tests/
│   ├── pyproject.toml
│   └── ...
└── [guia-generica].md            ← (opcional) guia para el equipo, fuera del repo
```

### 16.2 Estructura de carpetas segun arquitectura

Si tu proyecto usa arquitectura hexagonal (como la define ADR-41 en el framework), la estructura de carpetas refleja las capas:

```
[proyecto]/
├── [paquete_principal]/           # Python package principal
│   ├── __init__.py
│   ├── [unit_1]/                  # 1 carpeta por unit de construccion
│   │   ├── domain/                # Entidades, value objects, repos ABCs
│   │   ├── application/           # Commands, queries, handlers, ports
│   │   ├── infrastructure/        # Adapters (DB, cache, messaging)
│   │   └── api/                   # Routes, schemas, dependencies
│   ├── [unit_2]/
│   │   └── ... (misma estructura)
│   └── workers/                   # Background workers (si aplica)
│
├── plugins/                       # Plugins/modulos independientes
│   └── [plugin_name]/
│       ├── plugin.yaml            # Manifest del plugin
│       └── requirements.txt       # Deps aisladas (brownfield)
│
├── tests/                         # Tests organizados por tipo
│   ├── unit/                      # 1 subcarpeta por unit
│   ├── integration/               # Tests con infra real
│   ├── contracts/                 # Tests de contrato entre units
│   └── fixtures/                  # Datos de prueba
│
├── docker/                        # Configuracion Docker
│   ├── docker-compose.yml
│   ├── .env.example
│   └── services/                  # Configs por servicio
│
├── migrations/                    # Migraciones de BD (Alembic, Flyway, etc.)
│
├── pyproject.toml                 # Dependencias + tools config
├── .pre-commit-config.yaml        # Hooks de calidad
├── .gitignore
├── Makefile                       # Comandos del proyecto
├── CLAUDE.md                      # Playbook para agente de IA
└── README.md                      # Documentacion basica
```

> **Importante**: No crees todas las carpetas internas de cada unit manualmente. Solo crea la estructura de primer nivel. Las subcarpetas detalladas (entities/, value_objects/, etc.) se crean durante code gen cuando realmente se necesitan.

### 16.3 Archivos base minimos

El commit inicial debe incluir estos archivos funcionales (no solo carpetas vacias):

| Archivo | Contenido clave |
|---------|----------------|
| `pyproject.toml` | Dependencias, config ruff, mypy, pytest |
| `.pre-commit-config.yaml` | ruff (lint+format) + gitleaks (secrets) |
| `.gitignore` | Python, Docker, IDE, modelos, secrets |
| `Makefile` | dev, test, lint, format, bootstrap |
| `.env.example` | Variables de entorno sin secrets reales |
| `CLAUDE.md` | Playbook de code gen para el agente |
| `README.md` | Quick start minimo |
| `tests/conftest.py` | Fixtures compartidas base |

### 16.4 El commit inicial

```bash
# Crear estructura
mkdir -p [paquete]/{unit1,unit2,...}/{domain,application,infrastructure,api}
mkdir -p tests/{unit,integration,contracts}
mkdir -p docker/services

# Agregar __init__.py en todos los paquetes Python
find [paquete] tests plugins -type d -exec touch {}/__init__.py \;

# Crear archivos base (pyproject.toml, Makefile, etc.)
# ... (generados previamente)

# Commit y push
git add -A
git commit -m "chore: initial project scaffold — [arquitectura] ([ADR-XX])"
git push -u origin main
```

#### Prompt para generar el scaffold

```
Basandote en:
1. La arquitectura definida en los ADRs (hexagonal, plugins, etc.)
2. Las unidades de construccion y su mapeo a carpetas
3. La estrategia de dependencias (ADR de dependency management)
4. El stack tecnologico definido en infrastructure design

Genera la estructura de carpetas completa del proyecto con:
- Todos los __init__.py necesarios
- pyproject.toml con dependencias base + config de tools
- .pre-commit-config.yaml con ruff + gitleaks
- .gitignore completo
- Makefile con targets: dev, test, lint, format, bootstrap, migrate
- .env.example con todas las variables de conexion (sin secrets reales)
- CLAUDE.md con el playbook de code gen
- README.md con quick start

Pushea el commit inicial al repo.
```

### 16.5 Conectar herramienta de PM con GitHub

Para que los commits cierren issues automaticamente:

**Linear**:
1. Linear > Settings > Integrations > GitHub > conectar el repo
2. Habilitar "Close issues when PR merged with `Closes LIN-{id}`"

**Jira**:
1. Instalar GitHub for Jira app
2. Conectar repositorio
3. Usar `[PROJ-123]` en commits/PRs

**GitHub Projects**:
1. Ya esta integrado — usar `Closes #123` en commits/PRs

### 16.6 Instalar pre-commit hooks localmente

```bash
# Instalar dependencias de desarrollo
uv sync --dev        # Python
# o: pnpm install    # Node

# Instalar hooks de pre-commit
pre-commit install

# Verificar que funcionan
pre-commit run --all-files
```

> **Tip**: Cada desarrollador del equipo debe correr `pre-commit install` despues de clonar. Si no lo hacen, pueden pushear codigo sin formatear o con secrets. Considera documentar esto en el README.

### Lecciones de Operations y Harness (LL-015 a LL-027)

Las siguientes lecciones surgieron durante la fase de Operations y la implementacion de Harness Engineering:

| LL | Issue | Causa | Solucion |
|----|-------|-------|----------|
| LL-015 | Linear issues batch-updated post-facto | Issues actualizados DESPUES del trabajo, no durante | Linear DEBE actualizar en tiempo real per ADR-45 |
| LL-016 | Auth middleware AttributeError | 500 en vez de 401 al faltar app.state | Try/except AttributeError para todos los app.state access |
| LL-017 | Tests contra .env incompleto | Secrets no verificados antes de E2E — false passes | Secrets Verification Gate: `verify-env.sh` MANDATORIO |
| LL-018 | Operations marcado complete sin ejecucion | Stage 3/5 nunca corrieron; tag creado anyway | Definition of Done: TODOS los tests deben ejecutarse contra stack vivo |
| LL-019 | Summary contradice aidlc-state.md | Summary decia "7/7 complete" pero state decia "Stage 3 IN PROGRESS" | State Consistency Check: `aidlc-state.md` GANA siempre |
| LL-020 | Code orphans (get_langfuse, setup_otel) | Funciones definidas pero 0 consumers — marcadas "complete" | Code Wiring: grep para consumers; 0 consumers = no completado |
| LL-021 | Docker service name mismatch | 8 archivos usan `postgres` pero servicio es `postgresql` | Verificar con `docker compose config --services` antes de referenciar |
| LL-022 | Skip defensivo enmascara failures | `if 404: pytest.skip()` oculta bugs reales como skips | Fail explicitamente; usar `skip_if_stack_down` solo para ConnectionError |
| LL-023 | MLOps routes sin autenticacion | Cualquier usuario autenticado puede promover modelos | Auth coverage test detecta rutas desprotegidas automaticamente |
| LL-024 | close_issue_with_evidence CI broken | `gh run list --commit <short-sha>` retorna vacio | _resolve_full_sha() + --repo flag; SHA de 40 chars requerido |
| LL-025 | ADR count index mismatch | State decia 55 ADRs; index solo tenia 48 | ADR files individuales DEBEN indexarse en archivo maestro |
| LL-026 | Actualizacion parcial de metricas | Test count actualizado en state pero no en todas las tablas | Cuando metrica cambia: grep ALL aidlc-docs/, actualizar CADA ocurrencia |
| LL-027 | Script changes sin ADR updates (reincidente) | close_issue_with_evidence.py modificado pero ADR-055 no actualizado | Check #13 en stop_gate.py detecta ADR staleness programaticamente |

**Total**: 27 lecciones capturadas (14 en Construction + 13 en Operations).

### Mecanismos Preventivos Adicionales (post-Construction)

Despues de las primeras 14 lecciones, se implementaron mecanismos programaticos que previenen la recurrencia:

1. **Harness Engineering** (ADR-049): 16 gates programaticos en `scripts/harness-check.sh` que verifican automaticamente reglas del proyecto. Ver Paso 32 en [12-harness-engineering.md](12-harness-engineering.md).

2. **Progressive Disclosure** (ADR-056): Las 18 reglas obligatorias se distribuyeron en 5 archivos `.claude/rules/` que se cargan segun el contexto (always, before-code-gen, during-code-gen, before-commit, documentation).

3. **Stop Gate** (`scripts/harness/stop_gate.py`): 13+ verificaciones al final de cada sesion, incluyendo ADR staleness, doc metrics, y CLAUDE.md line count.

4. **close_issue_with_evidence.py**: Script que automatiza el cierre de issues en Linear con evidencia de CI, SHA verification, y workflow de In Progress. Bloquea cierre sin CI green (LL-026).

5. **CI Feedback Loop**: Cuando CI detecta un error que el harness no atrapa, se agrega al harness local como check `(CI-SYNC)`. Ejemplo: ruff format y mypy strict.

---

## Lecciones adicionales de ExpertIA aplicables a cualquier proyecto AIDLC

### Working tree limpio entre sesiones (LL-032)

Al inicio de cada sesion el working tree debe estar limpio (0 modified, 0 untracked no esperados). Si `git status` muestra >3 archivos sin commitear de sesiones anteriores, PARAR y limpiar ANTES de empezar trabajo nuevo. En un proyecto con pre-commit hooks y doc-code coupling, un working tree sucio genera dependencias cruzadas entre archivos de distintas sesiones que convierten un commit de 5 minutos en 45 minutos de debugging de hooks.

**Regla**: nunca cerrar una sesion con archivos sin commitear. Cada unidad de trabajo se commitea completa en la misma sesion.

### Spec antes de codigo — sin excepciones (LL-033)

Incluso para harness scripts, linters, gates y meta-infraestructura: spec primero, codigo despues. Cuando se escribe codigo "rapido" sin spec, el resultado tipico es: (1) bugs silenciosos por no pensar en edge cases, (2) specs superficiales retroactivas que no documentan el por que, (3) sin tests porque "es solo un script". El flujo AIDLC no tiene excepciones por tipo de artefacto.

### Doc-code coupling obligatorio (LL-028)

Cuando se modifica un script documentado en un ADR, el ADR debe actualizarse en el mismo commit. Cuando se agrega un nuevo script, wrapper, skill o agente, la documentacion correspondiente debe crearse en el mismo commit. La documentacion es un contrato vivo, no un evento one-shot. Un pre-commit hook que detecte archivos nuevos en directorios clave sin actualizacion de docs es la prevencion mecanica ideal.

### Feedback memories sin enforcement mecanico se olvidan (LL-030)

Las memorias de feedback (correcciones del usuario) que no tienen un check ejecutable en el harness se olvidan bajo presion de contexto. Si una leccion puede verificarse estaticamente (existencia de archivo, grep de patron, consistencia de metricas), debe convertirse en un check del harness — no depender de que Claude la recuerde. El patron es: memoria → check ejecutable → enforcement automatico.

### Nunca usar MCP para crear issues — solo el pipeline correcto (LL-036)

MCP es un pass-through crudo a APIs externas. No ejecuta la logica de negocio del proyecto: auto-routing a proyectos, auto-assign, preservacion de markdown, labels, jerarquia de issues. Si existe un script o funcion que encapsula esa logica, usarlo siempre. MCP permitido solo para lectura (list, search, get).

