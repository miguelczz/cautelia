# Guia: Harness Engineering, Skills y Agentes para Claude Code

> **Proposito:** Referencia de proyecto para que Claude Code entienda y aplique Harness Engineering, Skills (SKILL.md) y sub-agentes. Usar como CLAUDE.md o archivo de contexto del proyecto.

---

## 1. Que es Harness Engineering

Harness Engineering es la disciplina de disenar los **sistemas de control** --- entornos, restricciones, feedback loops --- que hacen que los agentes de IA sean confiables a escala. No es prompt engineering. No es model engineering. Es el diseno del sistema alrededor del modelo.

En Claude Code, el harness es el sistema operativo que:
- Gestiona recursos (contexto, tokens, herramientas disponibles)
- Enforza limites (module boundaries, architectural constraints)
- Maneja errores (feedback loops, self-repair, rollback)
- Provee drivers (tools nativas + servidores MCP)
- Mantiene state (memory, context history, task tracking)

### 1.1 Por que importa el Harness

El harness define el *techo* de lo que el agente puede hacer; el modelo determina la *calidad de razonamiento* al elegir y usar herramientas. Los modelos se entrenan EN PRESENCIA del harness --- son co-evolucionarios. Un harness bien disenado puede hacer que un modelo modesto supere a uno mayor con harness pobre.

Evidencia: mismo modelo + harness optimizado = salto de 52.8% a 66.5% en Terminal Bench 2.0 (LangChain). Solo cambio el harness.

### 1.2 El Loop Central de Claude Code

```
while (model returns tool calls) {
    execute tool (Bash, Read, Write, Edit, Grep, Glob, Agent, WebSearch...)
    -> capture result
    -> append to context
    -> call model again
}
```

Todo lo que hace Claude Code gira alrededor de este loop. Cada herramienta, skill y sub-agente es una extension de este ciclo.

---

## 2. Las 8 Lecciones del Harness Engineering

Extraidas del caso OpenAI/Codex (1M+ lineas de codigo, CERO escritas a mano, en 5 meses) y aplicadas al contexto de Claude Code.

### Leccion 1: Dale un mapa, no un manual de 1,000 paginas
- El contexto es un recurso escaso. Un archivo monolitico de instrucciones desplaza la tarea y el codigo relevante.
- **Aplicacion en Claude Code:** Usar CLAUDE.md como indice compacto que apunta a documentacion especifica. Progressive Disclosure --- no volcar todo al system prompt.

### Leccion 2: Disena el entorno, especifica la intencion
- El rol del ingeniero ya no es escribir codigo, sino disenar entornos, especificar intencion y construir feedback loops.
- **Aplicacion en Claude Code:** Escribir CLAUDE.md con reglas claras, definir Skills para tareas repetitivas, configurar hooks para validacion automatica.

### Leccion 3: Enforce architecture mechanically
- Linters customizados con instrucciones de remediacion en los mensajes de error.
- **Aplicacion en Claude Code:** Configurar pre-commit hooks, ESLint/Ruff rules, y que los mensajes de error incluyan el *porque* y el *como arreglar*. Claude Code lee esos mensajes y aprende de ellos.

```
ERROR: ModuleBoundaryViolation
File: src/payments/order.ts
Issue: Direct import from 'src/inventory' violates module boundary.
Why: Payments and Inventory are separate bounded contexts.
Fix: Use the InventoryService interface in 'src/shared/interfaces/inventory.ts'
```

### Leccion 4: Boring technology primero
- Claude Code es replicador de patrones. Tecnologia aburrida (anos de respuestas en Stack Overflow) = base mas confiable.
- **Aplicacion:** Elegir tech stacks bien documentados. Claude Code funciona mejor con frameworks populares y convenciones estandar.

### Leccion 5: Gestion de entropia como garbage collection
- **Aplicacion en Claude Code:** Crear tareas programadas (scheduled tasks) que escanean el codebase por desviaciones y auto-corrigen. Hygiene continua, no limpieza trimestral.

### Leccion 6: Context engineering continuo
- Cuando Claude Code lucha con una tarea, tratar como senal: identificar que falta y alimentarlo de vuelta al proyecto.
- **Aplicacion:** Actualizar CLAUDE.md, crear/refinar Skills, agregar ejemplos en la documentacion del proyecto.

### Leccion 7: Code review agente-a-agente
- **Aplicacion en Claude Code:** Usar la tool `Agent` para delegar sub-agentes de revision. Un sub-agente implementa, otro verifica. Los humanos se escalan solo para juicio genuino.

### Leccion 8: Feedback loops como primera clase
- **Aplicacion en Claude Code:** Snapshot BEFORE -> ejecutar cambio -> correr tests -> verificar resultado -> apply fix si necesario. Usar MCP de Chrome DevTools para validar UI en tiempo real.

---

## 3. Componentes del Harness en Claude Code

### 3.1 Context Engineering
- **CLAUDE.md como indice:** mapa compacto que apunta a donde encontrar que. No manual exhaustivo.
- **Skills:** conocimiento especializado que se carga bajo demanda (Progressive Disclosure).
- **Memory (.auto-memory/):** persistencia entre conversaciones para preferencias, feedback, contexto de proyecto.
- **Contexto dinamico:** acceso a logs, metricas y comportamiento real via MCP servers.

### 3.2 Herramientas Nativas de Claude Code

| Herramienta | Funcion |
|---|---|
| **Bash** | Ejecutar comandos del sistema, instalar dependencias, correr tests, git |
| **Read** | Leer archivos, imagenes, PDFs, notebooks Jupyter |
| **Write** | Crear archivos nuevos |
| **Edit** | Modificar archivos existentes (reemplazo exacto de strings) |
| **Grep** | Busqueda de contenido en archivos (regex, glob filters) |
| **Glob** | Busqueda de archivos por patron de nombre |
| **Agent** | Delegar tareas a sub-agentes especializados (en paralelo si son independientes) |
| **WebSearch** | Busqueda web |
| **WebFetch** | Obtener contenido de URLs |
| **TodoWrite** | Gestionar lista de tareas con estados (pending/in_progress/completed) |
| **AskUserQuestion** | Preguntar al usuario con opciones multiples |
| **Skill** | Invocar skills especializados (pdf, docx, pptx, xlsx, etc.) |

### 3.3 Extensiones via MCP

El Model Context Protocol (MCP) es el mecanismo estandar para anadir capacidades sin modificar Claude Code:
- **Browser automation:** Playwright MCP, Chrome DevTools MCP
- **Servicios externos:** Slack MCP, GitHub MCP, Notion MCP, Canva MCP
- **Datos:** BigQuery MCP, PostgreSQL MCP
- **Busqueda:** Brave Search MCP, Tavily MCP

Si falta una herramienta, buscar primero si existe un MCP server disponible.

### 3.4 Sub-Agentes (Tool Agent)

Claude Code puede lanzar sub-agentes especializados para tareas complejas:

```
Agent types disponibles:
- general-purpose: investigacion, busqueda de codigo, tareas multi-paso
- Explore: exploracion rapida del codebase (quick/medium/very thorough)
- Plan: diseno de planes de implementacion
- claude-code-guide: preguntas sobre Claude Code, Agent SDK, Claude API
```

**Principios de uso:**
- Lanzar multiples agentes en paralelo cuando las tareas son independientes.
- Usar `isolation: "worktree"` para que el agente trabaje en copia aislada del repo.
- Proveer descripcion completa de la tarea --- cada agente empieza desde cero.

### 3.5 Architectural Enforcement
- **Custom linters:** error messages que incluyen el *porque* de la regla y *como* arreglarla.
- **Pre-commit hooks:** validacion automatica antes de cada commit.
- **Structural tests:** verificacion determinista de limites de modulo.
- **Boring tech stack:** reducir superficie de comportamiento opaco.

### 3.6 Automated Validation
- **Test suite:** Pass->Fail es inaceptable (regresion). Fail->Pass es criterio de aceptacion.
- **Agent-to-agent review:** sub-agente implementa, otro sub-agente verifica.
- **Scheduled hygiene tasks:** detectan y corrigen desviaciones continuamente.
- **Feedback loops:** snapshot before/after, correr tests, self-repair.

### 3.7 Principio de Herramienta Minima Suficiente

Demasiadas herramientas -> Claude Code tiende a elegir las complejas cuando una simple bastaria, aumentando latencia y costo. Disenar el harness con el subconjunto minimo de herramientas para el caso de uso mejora la fiabilidad.

---

## 4. Agent Skills y SKILL.md en Claude Code

### 4.1 Que es un Agent Skill

Un Agent Skill es la unidad de extension de Claude Code. Encapsula instrucciones, contexto, scripts y referencias que se cargan cuando son relevantes para ejecutar una tarea especializada de manera fiable.

**Diferencia clave:**
- **Prompt:** texto efimero del humano en cada conversacion. No reutilizable.
- **Tool:** funcion nativa de Claude Code (Bash, Read, Edit...). Ejecucion puntual.
- **Skill:** paquete de conocimiento + instrucciones + scripts. Se activa cuando es relevante, referencia multiples tools, persiste en el proyecto.

### 4.2 Anatomia de un SKILL.md

```yaml
---
name: pdf-processing          # ID unico (lowercase, hyphens, max 64 chars)
description: >                # Max 1024 chars, sin XML tags
  Extracts text and tables from PDF files, fills forms, and merges
  documents. Use when working with PDF files or when the user
  mentions PDFs, forms, or document extraction.
---
```

**Reglas del frontmatter:**
- `name`: solo minusculas, numeros y guiones. No puede contener 'anthropic' ni 'claude'. Max 64 chars.
- `description`: NO vacia, max 1024 chars, sin XML tags. Es la clave de discovery --- Claude Code usa esto para decidir si activar el skill.
- Escribir en tercera persona: "Processes Excel files..." (correcto) vs "I can help you..." (incorrecto).

**Campos avanzados opcionales:**
- `user-invocable: true` --- el usuario puede llamarlo con `/skill-name`.
- `allowed-tools: Bash Read Write Edit Grep Glob` --- limita que herramientas puede usar el skill.
- `argument-hint: (descripcion)` --- reduce activaciones incorrectas.

### 4.3 Progressive Disclosure (Las 4 Capas)

Claude Code NO carga todo el contenido de todos los Skills al inicio:

| Capa | Que se carga | Cuando | Costo de tokens |
|---|---|---|---|
| 1 - Startup | Solo `name` + `description` de TODOS los skills | Siempre | Minimo |
| 2 - Activacion | SKILL.md completo | Cuando el skill es relevante | Moderado |
| 3 - Referencias | FORMS.md, REFERENCE.md, etc. | Solo si se necesitan | Zero hasta ser leidos |
| 4 - Scripts | Scripts se EJECUTAN via Bash | Solo al invocarlos | Solo el OUTPUT consume tokens |

**Estructura de ejemplo:**
```
skills/
  pdf/
    SKILL.md          <- Capa 2: se carga cuando el skill se activa
    FORMS.md          <- Capa 3: Read tool solo si necesita formularios
    REFERENCE.md      <- Capa 3: Read tool solo si necesita la API completa
    scripts/
      analyze_form.py <- Capa 4: Bash tool lo ejecuta, codigo no entra al contexto
      validate.py     <- Capa 4: Bash tool lo ejecuta, solo output al contexto
```

### 4.4 Activacion en Claude Code

| Activacion Implicita | Activacion Explicita |
|---|---|
| El usuario dice: "convierte este PDF a texto" | El usuario dice: `/pdf` o "usa el skill de PDF" |
| Claude Code compara la peticion con descriptions de los Skills | Claude Code busca el Skill por nombre y lo carga |
| Requiere description con keywords relevantes | El usuario conoce el nombre exacto |

### 4.5 Tres Principios de Concision

**Principio 1: Claude ya es inteligente --- no sobre-expliques**
- Verboso (150 tokens): "PDF files are a common format that contains text, images..."
- Conciso (50 tokens): `Extract PDF text: import pdfplumber; with pdfplumber.open('f.pdf') as p: text = p.pages[0].extract_text()`

**Principio 2: Curar != acumular**
- Un skill por dominio claramente diferenciado. No dos skills con superposicion.
- Si dos skills compiten por la misma peticion, fusionalos o reescribe descriptions.
- Maximo ~20 Skills activos por proyecto.
- SKILL.md body < 500 lineas. Si excedes, usa archivos de referencia.

**Principio 3: Composicion > Monolito**
- Referencias a archivos markdown adicionales (con Read tool, bajo demanda).
- Scripts externos que se ejecutan via Bash sin leerse en contexto.
- Logica condicional: "si necesita X, lee FORMA_X.md; si necesita Y, lee FORMA_Y.md".

### 4.6 Patrones de Diseno de Skills

**Patron 1: High-level guide con referencias**
```markdown
---
name: pdf-processing
description: Extracts text/tables from PDFs, fills forms, merges documents.
---
# PDF Processing
## Quick start
[codigo minimo]

## Advanced features
- Form filling: See FORMS.md (use Read tool)
- API reference: See REFERENCE.md (use Read tool)
```

**Patron 2: Organizacion por dominio**
```
bigquery-skill/
  SKILL.md           <- overview + navegacion
  reference/
    finance.md       <- revenue, ARR, billing
    sales.md         <- pipeline, oportunidades
    product.md       <- API usage, features
```
Claude Code lee SKILL.md, ve la referencia relevante y usa Read tool para cargar solo ese archivo.

**Patron 3: Libertad calibrada**

| Nivel | Cuando usarlo | Ejemplo |
|---|---|---|
| Alta libertad | Multiples enfoques validos | Code review: analiza estructura, sugiere mejoras |
| Libertad media | Patron preferido con variacion | Generar reporte: usa este template, ajusta segun datos |
| Baja libertad | Operacion fragil, secuencia critica | Migracion de BD: corre exactamente este script |

### 4.7 Scripts en Skills

**Ejecutar vs Leer:**
- **Ejecutar** (mas comun): "Run `bash scripts/analyze_form.py`" -> el codigo NO entra al contexto, solo el OUTPUT.
- **Leer como referencia**: "Read `scripts/analyze_form.py` for the algorithm" -> el codigo SI entra al contexto. Solo cuando Claude Code debe entender el algoritmo.

**Principio: Solve, don't punt** --- los scripts deben manejar errores, no delegarlos a Claude Code:
```python
# MAL: punt a Claude Code
def process_file(path):
    return open(path).read()  # falla y Claude Code tiene que averiguar

# BIEN: solve en el script
def process_file(path):
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        print(f'{path} not found, creating default')
        open(path, 'w').write('')
        return ''
```

### 4.8 Workflow Plan-Validate-Execute

Para operaciones complejas, forzar un ciclo de validacion:

```
1. Bash: python scripts/analyze_form.py input.pdf -> lee la estructura
2. Claude Code genera changes.json -> plan de cambios (observable y corregible)
3. Bash: python scripts/validate_fields.py changes.json -> verifica campos
   Si falla: error especifico ("Field X not found. Available: A, B, C")
4. AskUserQuestion -> "Apruebas estos cambios?" [mostrar resumen]
5. Bash: python scripts/fill_form.py changes.json -> aplica cambios
6. Bash: python scripts/verify_output.py output.pdf -> comprueba resultado
```

---

## 5. Prueba Adversarial de Skills

### 5.1 Las 6 Fases del Stress-Test

| # | Fase | Que hace |
|---|---|---|
| 1 | Extract & Decompose | Descompone en: Decisions, Assumptions, Dependencies, Interfaces, Ordering, Invariants, Recovery paths |
| 2 | Verify via Search | Verifica cada claim contra docs reales con Grep/Read/WebSearch --- no razona de memoria |
| 3 | Identify POCs | Separa: resuelto por evidencia vs necesita prueba practica (runtime, integracion) |
| 4 | Get Approval | AskUserQuestion: presenta POCs, agrupa por riesgo, espera aprobacion explicita |
| 5 | Execute POCs | Crea directorio temporal, corre POCs aprobados (Agent en paralelo), captura output |
| 6 | Walk Findings | Organiza: Confirmed / Unresolved / Accepted Risks. Presenta hallazgos. Limpia |

### 5.2 Evaluation-Driven Development

Construir evaluaciones ANTES de documentacion extensa:
1. Identificar gaps: correr Claude Code en tareas reales SIN el Skill. Documentar fallos.
2. Crear evaluaciones: minimo 3 escenarios que cubran esos gaps.
3. Baseline: medir performance sin el Skill.
4. Escribir instrucciones minimas: lo suficiente para pasar las evaluaciones.
5. Iterar: ejecutar, comparar contra baseline, refinar.

---

## 6. Enforcement Programatico: Reglas que No se Pueden Ignorar

> **Principio central:** Las reglas textuales en CLAUDE.md NO son suficientes para prevenir violaciones. Claude Code lee las reglas, las entiende, y las ignora cuando prioriza velocidad bajo presion de contexto. La solucion no es mas texto --- es enforcement programatico que haga IMPOSIBLE repetir los errores.

Un CLAUDE.md de 370+ lineas es texto que Claude Code lee una vez y olvida. Los mecanismos de esta seccion convierten cada regla en un **muro** que Claude Code no puede atravesar --- solo rodear haciendo lo correcto.

### 6.1 La Piramide de Enforcement

De mas debil (texto) a mas fuerte (imposibilidad mecanica):

```
Nivel 5: IMPOSIBILIDAD MECANICA  ← el codigo no compila / el test falla / el hook bloquea
Nivel 4: VALIDACION AUTOMATICA   ← scripts de verificacion post-cambio
Nivel 3: SCAFFOLDING FORZADO     ← templates que pre-enforzan la estructura correcta
Nivel 2: WRAPPERS OBLIGATORIOS   ← scripts que reemplazan comandos directos
Nivel 1: TEXTO EN CLAUDE.md      ← sugerencia que se olvida bajo presion de contexto
```

Mover cada regla del Nivel 1 al nivel mas alto posible.

### 6.2 Pre-commit Hooks que Bloquean

En lugar de escribir "no importes directamente de src/internal", crear un hook que lo haga imposible:

```bash
#!/bin/bash
# .git/hooks/pre-commit (o via husky/lefthook)

# Bloquea imports prohibidos
if grep -rn "from src/internal" --include="*.py" src/api/; then
  echo "ERROR: Direct import from src/internal in src/api/"
  echo "WHY: api/ must use interfaces in src/shared/"
  echo "FIX: import from src/shared/interfaces instead"
  exit 1
fi

# Bloquea archivos sin type hints
if grep -rn "def .*(.*):" --include="*.py" src/ | grep -v "->"; then
  echo "ERROR: Function without return type hint"
  echo "WHY: Type hints are required for all public functions"
  echo "FIX: Add -> ReturnType to the function signature"
  exit 1
fi
```

Claude Code ejecuta `git commit`, el hook falla, Claude Code lee el mensaje de error y se auto-corrige. No necesita recordar la regla --- el hook se la recuerda en el momento exacto.

**Clave:** El mensaje de error debe contener tres elementos:
1. **QUE** fallo (la violacion concreta)
2. **POR QUE** existe la regla (el contexto)
3. **COMO** arreglarlo (la accion especifica)

### 6.3 Linters con Mensajes que Ensenan

Linters customizados donde el error message ES la documentacion:

```python
# scripts/lint_architecture.py
"""Linter arquitectonico --- correr antes de cada commit."""
import ast, sys, glob

BOUNDARIES = {
    "src/api/": {"forbidden": ["src/internal/", "src/db/models/"],
                 "fix": "Create interface in src/shared/contracts/"},
    "src/workers/": {"forbidden": ["src/api/routes/"],
                     "fix": "Use event bus in src/shared/events/"},
}

violations = []
for scope, rules in BOUNDARIES.items():
    for pyfile in glob.glob(f"{scope}**/*.py", recursive=True):
        with open(pyfile) as f:
            content = f.read()
        for forbidden in rules["forbidden"]:
            if f"from {forbidden}" in content or f"import {forbidden}" in content:
                violations.append((pyfile, forbidden, rules["fix"]))

if violations:
    for file, imp, fix in violations:
        print(f"VIOLATION: {file} imports from {imp}")
        print(f"  WHY: Module boundary - these layers must not know about each other")
        print(f"  FIX: {fix}")
        print()
    sys.exit(1)
else:
    print("Architecture check passed.")
```

### 6.4 Tests Arquitectonicos (no solo funcionales)

Tests que verifican la *estructura* del codigo, no solo su comportamiento:

```python
# tests/test_architecture.py
"""Tests que Claude Code DEBE pasar despues de cada cambio."""
import os, ast, glob

def test_no_raw_sql_outside_repositories():
    """SQL queries must only exist in src/repositories/"""
    for root, _, files in os.walk("src/"):
        if "/repositories/" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                content = open(path).read()
                for keyword in ["SELECT ", "INSERT ", "UPDATE ", "DELETE "]:
                    assert keyword not in content, \
                        f"Raw SQL in {path} - move to src/repositories/"

def test_no_business_logic_in_routes():
    """Routes must only call services, never implement logic"""
    for f in glob.glob("src/api/routes/*.py"):
        tree = ast.parse(open(f).read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While)):
                assert False, f"Loop in route {f} - extract to src/services/"

def test_all_endpoints_have_error_handling():
    """Every route function must have try/except"""
    for f in glob.glob("src/api/routes/*.py"):
        tree = ast.parse(open(f).read())
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith(("get_", "post_", "put_", "delete_")):
                has_try = any(isinstance(child, ast.Try) for child in ast.walk(node))
                assert has_try, f"Route {node.name} in {f} has no try/except - add error handling"

def test_no_hardcoded_secrets():
    """No API keys, passwords or tokens in source code"""
    patterns = ["API_KEY=", "SECRET=", "PASSWORD=", "TOKEN=", "Bearer "]
    for root, _, files in os.walk("src/"):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                content = open(path).read()
                for pattern in patterns:
                    assert pattern not in content, \
                        f"Hardcoded secret '{pattern}' in {path} - use env vars"
```

Claude Code corre `pytest tests/test_architecture.py` despues de cada cambio. Fail = correccion automatica con mensaje claro.

### 6.5 Scaffolding que Pre-Enforza Estructura

En vez de decir "cada endpoint debe tener validacion, logging y error handling", dar un script que genere el skeleton correcto:

```python
# scripts/scaffold_endpoint.py
"""Genera endpoint con estructura correcta pre-enforced."""
import sys, os

name = sys.argv[1]  # ej: "create_user"
module = sys.argv[2]  # ej: "users"

ROUTE_TEMPLATE = '''from fastapi import APIRouter, HTTPException
from src.services.{module} import {module}_service
from src.schemas.{module} import {Name}Request, {Name}Response
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/{module}/{name}", response_model={Name}Response)
async def {name}(request: {Name}Request):
    """TODO: Add endpoint description."""
    try:
        result = await {module}_service.{name}(request)
        logger.info("{name} completed", extra={{"request_id": request.id}})
        return result
    except ValueError as e:
        logger.warning("{name} validation error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("{name} failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
'''

# Genera route, schema, test, y registra en router
# ... (genera archivos con estructura correcta)
print(f"Endpoint {name} scaffolded in src/api/routes/{module}.py")
print(f"Schema created in src/schemas/{module}.py")
print(f"Test created in tests/api/test_{name}.py")
print("Fill in the TODO sections. Structure is pre-enforced.")
```

Claude Code ejecuta el scaffold y solo llena los blancos. La estructura correcta es el default.

### 6.6 Wrappers que Reemplazan Comandos Directos

Si Claude Code tiende a hacer algo mal (ej: migraciones sin backup), crear un wrapper obligatorio:

```python
# scripts/safe_migrate.py
"""NUNCA correr alembic directo. Usar este wrapper."""
import subprocess, sys, datetime

# Paso 1: backup automatico (no opcional)
backup = f"backups/pre-migration-{datetime.datetime.now():%Y%m%d-%H%M}.sql"
subprocess.run(["pg_dump", "-f", backup], check=True)
print(f"OK: Backup created: {backup}")

# Paso 2: dry-run primero
result = subprocess.run(["alembic", "upgrade", "head", "--sql"], capture_output=True)
print("DRY RUN OUTPUT:")
print(result.stdout.decode())

# Paso 3: ejecutar real
subprocess.run(["alembic", "upgrade", "head"], check=True)
print("OK: Migration applied successfully.")
print(f"ROLLBACK: Restore from {backup} if needed.")
```

### 6.7 Scheduled Tasks de Hygiene Continua

No esperar a que Claude Code viole una regla --- correr agentes de limpieza que detecten drift:

```
Scheduled task: cada sesion o bajo demanda
-> Bash: python scripts/lint_architecture.py
-> Bash: pytest tests/test_architecture.py
-> Bash: python scripts/check_naming_conventions.py
-> Bash: python scripts/detect_circular_imports.py
-> Reporta desviaciones con mensajes accionables
```

### 6.8 El CLAUDE.md Minimo que SI Funciona

El CLAUDE.md no desaparece --- pero cambia de **manual de reglas** a **indice de enforcement**:

```markdown
# CLAUDE.md (30 lineas, no 370)

## Antes de cualquier cambio
- Correr: `python scripts/lint_architecture.py`
- Correr: `pytest tests/test_architecture.py -x`

## Para crear endpoints
`python scripts/scaffold_endpoint.py <nombre> <modulo>`

## Para migraciones
`python scripts/safe_migrate.py` (NUNCA alembic directo)

## Para deploy
`bash scripts/safe_deploy.sh` (incluye rollback automatico)

## Convenciones
- Enforced by ruff (ver pyproject.toml) --- no leer, solo correr `ruff check .`
- Enforced by pre-commit hooks --- se validan automaticamente al commitear

## Arquitectura
- Ver docs/ARCHITECTURE.md (solo si necesitas contexto, no memorizar)
- Boundaries enforced by tests/test_architecture.py
```

30 lineas que apuntan a enforcement programatico > 370 lineas de reglas que se olvidan.

### 6.9 Formula de Conversion: Regla -> Enforcement

Para cada regla existente en CLAUDE.md, aplicar esta decision:

```
¿Se puede detectar la violacion programaticamente?
  SI -> ¿Se puede bloquear ANTES del commit?
          SI -> Pre-commit hook (Nivel 5)
          NO -> Test arquitectonico post-cambio (Nivel 4)
  NO -> ¿Se puede generar la estructura correcta automaticamente?
          SI -> Script de scaffolding (Nivel 3)
          NO -> ¿Se puede encapsular en un wrapper seguro?
                  SI -> Wrapper obligatorio (Nivel 2)
                  NO -> Queda como texto en CLAUDE.md (Nivel 1)
                        PERO: debe ser < 5 lineas, especifica, accionable
```

Solo las reglas que no pueden automatizarse quedan como texto. Tipicamente: decisiones de producto, trade-offs de diseno, preferencias de UX. Esas si son ~30 lineas.

---

## 7. Anti-Patrones a Evitar (incluye los de Enforcement)

| Anti-Patron | Problema y Solucion |
|---|---|
| CLAUDE.md monolitico | Desplaza tarea y codigo del contexto. Usar como indice con Progressive Disclosure. |
| Referencias anidadas profundas | SKILL.md -> advanced.md -> details.md: partial reads. Mantener a 1 nivel. |
| Demasiadas opciones | "Puedes usar pypdf, o pdfplumber, o PyMuPDF..." -> confusion. Dar UN default. |
| Paths Windows (backslash) | `scripts\helper.py` falla. Siempre forward slash. |
| Info time-sensitive | Fechas hardcodeadas. Usar seccion 'Old patterns' colapsable. |
| Terminologia inconsistente | Mezclar 'endpoint' / 'URL' / 'path'. Elegir uno y usarlo siempre. |
| Demasiados Skills (50+) | Contexto pesado en Capa 1. Curar conjunto minimo sin superposicion (~20 max). |
| SKILL.md > 500 lineas | Contexto costoso en Capa 2. Mover a archivos de referencia. |
| Magic numbers en scripts | TIMEOUT = 47 sin explicacion. Documentar cada constante. |
| No usar TodoWrite | Claude Code pierde track de tareas complejas. Siempre usar para 3+ pasos. |
| No usar AskUserQuestion | Empezar a trabajar sin clarificar requisitos ambiguos. Preguntar primero. |
| Reglas solo en texto | CLAUDE.md de 370 lineas = texto que se olvida. Convertir a hooks/tests/scripts. |
| Error messages sin contexto | "Error: validation failed" no ayuda. Incluir QUE/POR QUE/COMO en cada error. |
| Enforcement solo al final | Validar solo en CI/CD = feedback tardio. Mover a pre-commit y post-cambio. |
| Confiar en "no hagas X" | Instrucciones negativas se ignoran bajo presion. Hacer X imposible mecanicamente. |

---

## 8. Checklist de Skill Listo para Produccion

### Calidad Core
- [ ] Description especifica con keywords relevantes (que hace + cuando usarlo)
- [ ] Description en tercera persona, max 1024 chars
- [ ] SKILL.md body < 500 lineas
- [ ] Archivos de referencia adicionales si supera el limite
- [ ] Sin informacion time-sensitive en el cuerpo principal
- [ ] Terminologia consistente
- [ ] Ejemplos concretos con herramientas de Claude Code (Bash, Read, Edit...)
- [ ] Referencias a 1 nivel de profundidad
- [ ] Progressive disclosure implementado (4 capas)
- [ ] Workflows con pasos claros y numerados

### Scripts y Codigo
- [ ] Scripts resuelven errores --- no delegan a Claude Code (solve, don't punt)
- [ ] Error handling explicito con mensajes utiles
- [ ] Sin magic numbers --- cada constante documentada
- [ ] Dependencias listadas (pip/npm) con comando de instalacion
- [ ] Paths con forward slash
- [ ] Loops de validacion para operaciones criticas
- [ ] Distincion clara entre 'ejecutar via Bash' vs 'leer via Read'

### Testing y Validacion
- [ ] Minimo 3 evaluaciones ANTES de finalizar
- [ ] Probado con modelos objetivo (Haiku, Sonnet, Opus)
- [ ] Probado con escenarios reales --- no solo happy path
- [ ] Stress-test adversarial ejecutado
- [ ] Feedback del equipo incorporado

---

## 9. El Nuevo Rol del Ingeniero con Claude Code

| Antes: Ingeniero como codificador | Ahora: Ingeniero como arquitecto de harness |
|---|---|
| Escribe codigo linea por linea | Disena CLAUDE.md, Skills, restricciones y feedback loops |
| Revisa PRs de colegas | Define acceptance criteria; sub-agentes hacen revision mecanica |
| Depura bugs en el codigo | Identifica que capacidad falta cuando Claude Code falla en una tarea |
| Mantiene documentacion | Disena estructura de docs que Claude Code puede navegar (Progressive Disclosure) |
| Escoge librerias por preferencia | Escoge tecnologias por 'AI-friendliness' y predecibilidad |
| Gestiona deuda tecnica manualmente | Configura scheduled tasks de hygiene que corren continuamente |

> "El rigor no desaparece; se relocaliza del codigo al diseno del sistema." --- Chad Fowler

---

## 10. Estructura Recomendada de Proyecto para Claude Code

```
proyecto/
  CLAUDE.md                    <- Indice compacto: reglas, convenciones, punteros
  .claude/
    settings.json              <- Configuracion de Claude Code
  .skills/
    skills/
      pdf/
        SKILL.md               <- Skill de PDF processing
        scripts/
      docx/
        SKILL.md               <- Skill de Word documents
        scripts/
      xlsx/
        SKILL.md               <- Skill de Excel
        scripts/
      custom-skill/
        SKILL.md               <- Skill propio del proyecto
        REFERENCE.md           <- Documentacion extendida
        scripts/
  .auto-memory/
    MEMORY.md                  <- Indice de memorias persistentes
    user_role.md               <- Quien es el usuario
    feedback_*.md              <- Correcciones y preferencias
    project_*.md               <- Contexto del proyecto
  src/                         <- Codigo fuente
  tests/                       <- Tests (el agente los corre para validar)
  docs/                        <- Documentacion que Claude Code puede leer
```

---

## 11. Referencias

- **OpenAI Engineering** --- Harness Engineering: openai.com/index/harness-engineering/
- **Latent.Space** --- Is Harness Engineering real?: latent.space/p/ainews-is-harness-engineering-real
- **Martin Fowler** --- Harness Engineering: martinfowler.com/articles/exploring-gen-ai/harness-engineering.html
- **Anthropic** --- Agent Skills Best Practices: platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- **SKILL.md standard**: platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- **Claude Code Skills**: code.claude.com/docs/en/skills
- **MCP Protocol**: modelcontextprotocol.io

---

*Guia enfocada exclusivamente en Claude Code.*
*Sintetizada de: harness_engineering.docx, agent_harness_tools.docx, agent_skills_skillmd.docx*
