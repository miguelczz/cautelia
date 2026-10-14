## Paso 26: Build & Test Formal — Cierre de la Fase de Construction

### 26.1 Cuando se ejecuta

Despues de completar code generation de TODAS las unidades. Es el ultimo stage de la fase de Construction y el gate formal antes de Operations.

### 26.2 Que incluye per el rule file (`build-and-test.md`)

El stage tiene 10 steps obligatorios:

| Step | Que hacer | Artefacto |
|:----:|-----------|-----------|
| 1 | Analizar que tipos de test aplican al proyecto | — |
| 2 | Generar instrucciones de build | `build-instructions.md` |
| 3 | Generar instrucciones de unit tests | `unit-test-instructions.md` |
| 4 | Generar instrucciones de integration tests | `integration-test-instructions.md` |
| 5 | Generar instrucciones de performance tests *(if applicable)* | `performance-test-instructions.md` |
| 6 | Generar instrucciones adicionales *(as needed)*: e2e, security, contract | `e2e-test-instructions.md`, `security-test-instructions.md` |
| 7 | Generar el summary con resultados reales | `build-and-test-summary.md` |
| 8 | Actualizar `aidlc-state.md` | — |
| 9 | Presentar resultados y pedir aprobacion al usuario | — |
| 10 | Registrar en audit log | — |

### 26.3 Lo que NO se puede omitir

**Leccion del proyecto ExpertIA (LL-007, LL-012)**: Build & Test se marco COMPLETE dos veces sin cumplir los criterios. La primera vez sin ejecucion formal, la segunda sin docker-compose.yml ni integration tests. Esto genero la deuda tecnica mas grave del proyecto.

**Reglas criticas aprendidas**:

1. **Generar docs NO es lo mismo que ejecutar tests**. Los 7 documentos de instrucciones deben existir, PERO los tests de Steps 3 y 4 (unit + integration) deben estar escritos Y ejecutados con resultados reales.

2. **El summary no puede tener "pending" en secciones de resultados**. Si hay items pending, el stage NO esta complete. Esto se llama la "regla anti-pending".

3. **Los tests adicionales (Step 6: e2e, security, performance) son "As Needed"**. El summary permite `N/A` como valor valido. Si se requieren pero dependen de infraestructura no disponible (ej: Keycloak realm, GPU), se documentan como N/A con justificacion y se difieren a Operations.

4. **Docker Compose + migrations + bootstrap deben ejecutarse antes del summary**. Sin infra real no hay integration tests reales. Sin integration tests reales no hay Build & Test real.

### 26.4 Definition of Done — checklist verificable

Antes de marcar Build & Test como COMPLETE, verificar CADA item con un comando:

```
[ ] docker compose up -d → servicios healthy
[ ] alembic upgrade head → migrations aplicadas contra DB real
[ ] python -m expertia.scripts.bootstrap → seed ejecutado
[ ] curl localhost:8000/healthz → 200 OK
[ ] pytest tests/unit/ → PASS
[ ] pytest tests/integration/ -m integration → PASS
[ ] pytest tests/contracts/ -m contract → PASS
[ ] pre-commit run --all-files → PASS (ruff + gitleaks)
[ ] Los 7 docs de build-and-test/ existen
[ ] build-and-test-summary.md NO contiene "pending" en resultados
[ ] bash scripts/verify-setup.sh → exit 0
```

> **Actualizado post-Operations**: El conteo final despues de Operations es **317 tests** (175 unit + 32 contract + 50 integration + 6 structural + 43 infrastructure + 11 security) + 34 Playwright smoke tests + 72 clinical golden dataset. CI/CD 7/7 green. Ver [11-operations.md](11-operations.md) para detalle.

### 26.5 La aprobacion formal

El stage termina con una pregunta explicita al usuario:

> "Build and test instructions complete. Ready to proceed to Operations stage?"

El usuario debe responder con una aprobacion explicita. Esta aprobacion se registra en:
1. `audit/cross-cutting.md` — con timestamp y raw user input
2. `aidlc-state.md` — con timestamp de aprobacion

**Sin esta aprobacion, Construction NO esta cerrada.** En el proyecto ExpertIA, esta aprobacion se dio multiples veces pero nunca se registro formalmente hasta que el usuario detecto la omision.

### 26.6 Despues de la aprobacion

Con Build & Test aprobado, los siguientes pasos son:

1. **Merge PR a main** — usando merge commit (no squash) per git-workflow.md
2. **Tag de milestone** — `git tag v0.1.0-construction && git push origin v0.1.0-construction`
3. **Transicion a Operations** — actualmente placeholder, cubre Docker Compose MVP → Cloud post-MVP

### 26.7 Prompt ejemplo — Build & Test formal

```
Ejecuta el stage Build & Test formal per build-and-test.md.

Pre-requisitos:
- Code gen de las 6 unidades esta COMPLETE
- Docker Compose esta corriendo (docker compose ps)

Pasos:
1. Ejecuta los 10 steps del rule file en orden
2. Genera los 7 documentos de instrucciones
3. Escribe Y ejecuta integration tests contra PG y Redis reales
4. Escribe Y ejecuta contract tests
5. Genera el summary con resultados reales (NO "pending")
6. Presenta resultados y pide mi aprobacion
7. Registra la aprobacion en audit log

NO marques COMPLETE sin mi aprobacion explicita.
```

---

## Paso 27: Leccion Meta — La Metodologia se Audita a Si Misma

### 27.1 El descubrimiento

En el proyecto ExpertIA, despues de completar Build & Test, el usuario pidio una auditoría exhaustiva de compliance AIDLC. El resultado: 9 hallazgos que nadie habia detectado, incluyendo:

- Security extension con 15 reglas que nunca se rastrearon
- 4 units sin audit trail de code generation
- Artefactos de diseño faltantes
- Skills y guias incompletas

**Compliance antes de la auditoría**: ~90%. **Despues de remediacion**: 100%.

### 27.2 La leccion

**Una auditoría formal de compliance AIDLC es OBLIGATORIA antes del primer merge a main.** No importa que tan bien se siguio el proceso — siempre hay gaps invisibles. La auditoría los hace visibles.

### 27.3 Que auditar

~130 checks organizados en 4 bloques:

1. **File existence sweep** (~5 min): verificar que TODOS los artefactos que la metodología define existen en disco. Automatizable con un script.
2. **Content spot-checks** (~10 min): verificar que los artefactos clave tienen el contenido esperado (RF count en requirements, story count, ADR count, no "pending" en summary).
3. **Audit log cross-reference** (~10 min): para cada stage, verificar que existe una entrada en el audit file correspondiente con timestamp.
4. **Findings resolution** (~15 min): remediar cada hallazgo y re-verificar.

### 27.4 Prompt ejemplo — auditoría de compliance

```
Ejecuta una auditoría exhaustiva de compliance AIDLC antes del merge.

Cruza los 16 rule files + extensions contra el estado real del proyecto.
Para cada stage:
1. Verifica que los artefactos existen
2. Verifica contenido clave
3. Verifica audit log entries
4. Verifica security extension compliance

Reporta: PASS/FAIL por check, compliance %, findings con severidad.
Remedia todos los findings antes de presentar el reporte final.
```

### 27.5 Lo que aprendimos (14 lecciones en un solo proyecto)

| # | Leccion | Tipo |
|:-:|---------|------|
| LL-001 | Verificar version REAL de Python del entorno | gap-diseño |
| LL-002 | Check hexagonal de imports es OBLIGATORIO | anti-patron |
| LL-003 | DI wiring es un paso explicito del plan | gap-diseño |
| LL-004 | Checkpoint parcial post-unit foundation | patron-exitoso |
| LL-005 | Smoke tests HTTP detectan bugs que unit tests no ven | patron-exitoso |
| LL-006 | Siempre usar el .venv del proyecto | anti-patron |
| LL-007 | Build & Test debe ejecutarse formalmente | anti-patron |
| LL-008 | 1-commit-per-story no aplica a AI code gen por unit | ajuste-adr |
| LL-009 | NUNCA hardcodear credenciales — ni como defaults | anti-patron |
| LL-010 | Claude DEBE leer ADRs ANTES de decidir | anti-patron |
| LL-011 | Prevención con reglas MANDATORY en CLAUDE.md | patron-exitoso |
| LL-012 | Build & Test sin infra ni integration tests = deuda grave | desvio-arquitectura |
| LL-013 | 5 mecanismos preventivos sistémicos | patron-exitoso |
| LL-014 | Auditoría formal antes del merge descubre gaps invisibles | patron-exitoso |

> **Regla de oro para futuros proyectos**: Si acumulas 3+ lecciones con la misma causa raíz, crea una regla MANDATORY en CLAUDE.md. Las lecciones diagnostican; las reglas previenen.

---

## Paso 28: Aprobacion Formal de Build & Test — Cierre de Construction

### 28.1 Que es la aprobacion formal

El stage Build & Test termina con un mensaje explicito del agente:

> **"Build and test instructions complete. [resumen de resultados]. Ready to proceed to Operations stage?"**

El usuario DEBE responder con una aprobacion explicita. Sin esta respuesta, el stage NO esta cerrado y no se puede hacer merge ni transicionar a Operations.

### 28.2 Que debe estar listo ANTES de pedir aprobacion

Per la Definition of Done en CLAUDE.md:

- [ ] Docker Compose up y servicios healthy
- [ ] Migrations aplicadas contra DB real
- [ ] Bootstrap ejecutado (seed data)
- [ ] Unit tests PASS
- [ ] Integration tests escritos Y ejecutados contra infra real (PG, Redis)
- [ ] Contract tests escritos Y ejecutados
- [ ] TODOS los docs del rule file generados
- [ ] Summary NO contiene "pending"
- [ ] 0 hardcoded secrets (gitleaks PASS)
- [ ] Audit trail completo (todas las units con entries)
- [ ] Lessons learned documentadas

### 28.3 Prompt ejemplo — solicitar aprobacion

```
No necesitas prompt especial. El agente lo hace automaticamente
al terminar Build & Test. Tu solo respondes:

"se aprueba formalmente el Build & Test stage"

Si NO estas seguro, pregunta:
"que falta para que pueda dar la aprobacion?"
```

### 28.4 Que pasa despues de la aprobacion

El agente ejecuta el 3-Step Closure:

1. **Artefacto**: Summary ya actualizado con resultados reales
2. **aidlc-state.md**: Marca Build & Test como COMPLETE con timestamp de aprobacion
3. **Audit log**: Registra la aprobacion textual del usuario en `audit/cross-cutting.md`

Despues de esto:
- Merge del PR a main
- Tag `v{X.Y.Z}-construction`
- Transicion a Operations phase

### 28.5 Leccion aprendida — nunca mas saltarse la aprobacion

En ExpertIA, Build & Test se marco COMPLETE **dos veces** sin aprobacion formal del usuario. La primera vez se desvio a otros temas. La segunda vez se presento el mensaje pero nunca se recibio respuesta explicita.

**Regla**: Si el agente presenta el mensaje de aprobacion y el usuario no responde directamente, el agente DEBE insistir antes de proceder. No asumir aprobacion implicita.

---

## Paso 29: Linear como Herramienta de Valor — No de Burocracia

### 29.1 Para que sirve Linear en un proyecto AIDLC

Linear NO es un checklist para marcar cosas como hechas. Es la fuente de verdad del **backlog futuro** y la herramienta de **trazabilidad commit-a-issue**.

### 29.2 Donde Linear agrega valor real

| Momento | Accion en Linear | Valor concreto |
| ------- | ---------------- | -------------- |
| Inicio de sesion | Leer backlog | Claude sabe que priorizar sin que le repitas contexto |
| Code gen | Mover issue a "In Progress" | Visibilidad de que se esta trabajando |
| Commit/PR | `Closes EXP-XXX` | Auto-cierra issue al merge — trazabilidad automatica |
| Bug encontrado | Crear issue tipo bug | No se pierde — queda en backlog con repro steps |
| Leccion con accion | Crear issue improvement | La accion correctiva no se olvida |
| Fin de sesion | Comentar issues en progreso | La proxima sesion arranca informada |

### 29.3 Donde Linear NO agrega valor

- Crear 50 issues retroactivamente para trabajo ya hecho → housekeeping sin impacto
- Crear issues para cosas que se van a hacer en la misma sesion → overhead sin beneficio
- Mover issues de estado en estado como ritual → burocracia

### 29.4 Setup tecnico requerido — Paso a paso completo

El setup de Linear tiene 4 componentes. Cada uno resuelve un problema diferente:

#### Componente 1: Crear workspace y team en Linear (una sola vez)

1. Ir a [linear.app](https://linear.app) y crear un workspace
2. Crear un team con un key corto (ej: "EXP" para ExpertIA)
3. El key define los IDs de los issues: `EXP-001`, `EXP-002`, etc.

> **Tip**: El key debe ser corto (3-4 letras) porque aparecera en commits y PRs.

#### Componente 2: Integracion GitHub ↔ Linear (una sola vez, manual)

Esta integracion permite que `Closes EXP-XXX` en un PR cierre el issue automaticamente al merge.

1. En Linear: **Settings > Integrations > GitHub**
2. Click "Connect" y autorizar la organizacion de GitHub
3. Verificar que aparece "Connected" con el nombre de tu org

**Verificacion**: al crear un PR con `Closes EXP-XXX` en el body y mergearlo, el issue debe moverse a "Done" automaticamente.

> **Importante**: Esta es una accion manual que NO se puede hacer via API ni MCP. Solo desde el UI de Linear.

#### Componente 3: LINEAR_API_KEY en el shell del dev

El token permite que Claude (via MCP) pueda leer y crear issues.

```bash
# 1. Obtener token en: Linear > Settings > API > Personal API keys
# 2. Agregarlo al shell profile
echo 'export LINEAR_API_KEY="lin_api_TU_TOKEN_AQUI"' >> ~/.zshrc
source ~/.zshrc

# 3. Verificar
echo $LINEAR_API_KEY | head -c 15
# Debe mostrar: lin_api_XXXXXXX
```

> **Seguridad**: El token es personal y da acceso completo a tu workspace. NUNCA commitearlo, NUNCA ponerlo en `.env.example`. Solo en `~/.zshrc` (o equivalente) y en `.env.local` (gitignored).

#### Componente 4: Linear MCP en Claude Code

Este es el componente mas problematico. Documentamos todos los problemas que encontramos y la solucion definitiva.

**Problemas encontrados (y como evitarlos)**:

| Problema | Causa | Solucion |
| -------- | ----- | -------- |
| `@modelcontextprotocol/server-linear` no existe | Paquete npm incorrecto — no es oficial de Anthropic | Usar `@mseep/linear-mcp` (v78+, activamente mantenido) |
| `ERR_MODULE_NOT_FOUND: ajv-provider.js` | Node 18 incompatible con el SDK MCP moderno | Requiere Node >= 20. Usar path explicito a Node 20 |
| `claude mcp add -e KEY=val linear` falla | Bug del CLI — el flag `-e` conflicta con el nombre positional | Configurar directamente en `~/.claude.json`, no via CLI |
| MCP registrado pero "Failed to connect" | Variable LINEAR_API_KEY no disponible en el entorno del MCP | Pasar el token resuelto (valor real, no `$VAR`) en el JSON |
| MCP conecta pero `search_issues` da error JSON | Paquete `linear-mcp-server` (v0.1.0) tiene bug de formato | Usar `@mseep/linear-mcp` en su lugar |
| MCP no se activa despues de configurar | Los MCPs se cargan al iniciar sesion de Claude Code | Hacer Reload Window (Cmd+Shift+P > "Reload Window") |

**Solucion definitiva — configurar directamente en `~/.claude.json`**:

```bash
# 1. Verificar que tienes Node >= 20 disponible
# Si usas nvm:
nvm ls
# Buscar la linea con v20.x.x y anotar el path

# 2. Verificar el path exacto de npx de Node 20
ls ~/.nvm/versions/node/v20.*/bin/npx
# Ejemplo: /Users/tu-user/.nvm/versions/node/v20.17.0/bin/npx

# 3. Configurar en claude.json (reemplazar los 3 valores marcados con <<<)
python3 -c "
import json, os
with open(os.path.expanduser('~/.claude.json'), 'r') as f:
    config = json.load(f)
config.setdefault('mcpServers', {})['linear'] = {
    'command': '/Users/TU-USER/.nvm/versions/node/v20.17.0/bin/npx',  # <<< Path a Node 20
    'args': ['-y', '@mseep/linear-mcp'],
    'env': {
        'LINEAR_API_KEY': os.environ['LINEAR_API_KEY'],  # <<< Se lee del shell
        'PATH': '/Users/TU-USER/.nvm/versions/node/v20.17.0/bin:/usr/bin:/bin'  # <<< Path a Node 20
    }
}
with open(os.path.expanduser('~/.claude.json'), 'w') as f:
    json.dump(config, f, indent=2)
print('Linear MCP configurado')
"

# 4. Reload Window en VS Code (Cmd+Shift+P > "Reload Window")

# 5. Verificar
claude mcp list
# Debe mostrar: linear: ... - ✓ Connected
```

> **Alternativa sin nvm**: Si tienes Node 20+ como version por defecto (`node --version` >= 20), puedes usar simplemente `"command": "npx"` sin path explicito.

**Verificacion completa** (ejecutar en Claude Code despues de Reload):

```
# El agente puede ejecutar:
mcp__linear__list_teams       → debe retornar tu team (ej: ExpertIA, key: EXP)
mcp__linear__list_issues      → debe retornar issues (o lista vacia si no hay)
mcp__linear__create_issue     → debe poder crear un issue de prueba
```

### 29.5 Cuando configurar Linear en el flujo AIDLC

Linear debe configurarse durante el **Setup Operativo** (antes de code gen), no despues. La secuencia correcta es:

```
Setup Operativo
  ├── Paso 1: git clone
  ├── Paso 2: cp .env.example .env
  ├── Paso 3: docker compose up
  ├── Paso 4: make bootstrap
  ├── Paso 5: pre-commit install
  ├── Paso 6: Linear workspace + team (si es proyecto nuevo)     ← NUEVO
  ├── Paso 7: GitHub ↔ Linear integracion (manual en UI)          ← NUEVO
  ├── Paso 8: LINEAR_API_KEY en shell + MCP configurado           ← NUEVO
  └── Paso 9: verificar /healthz + Linear MCP connected
```

**Prompt ejemplo — verificar Linear en Setup Operativo**:

```
Verifica que Linear esta correctamente configurado:
1. LINEAR_API_KEY esta en mi shell
2. Linear MCP conecta (list_teams retorna mi team)
3. GitHub ↔ Linear integracion activa
Si algo falla, guiame paso a paso para corregirlo.
```

### 29.6 Como incluir Linear en el flujo de code gen

Una vez configurado, el agente debe usar Linear en estos puntos del flujo:

**Al inicio de cada sesion**:
```
Claude lee Linear backlog → identifica issues prioritarios → propone plan de trabajo
```

**Durante code gen (cada commit)**:
```
git commit -m "feat(core): implement tenant CRUD - Closes EXP-123"
```
El `Closes EXP-123` es critico — es lo que conecta el commit con el issue y permite que al merge del PR, el issue se cierre automaticamente.

**Al crear un PR**:
```
gh pr create --title "Unit 1: Core Platform" --body "$(cat <<'EOF'
## Summary
- Tenant CRUD with RLS isolation
- Audit log with hash chain
- Rate limiting with Redis sliding window

Closes EXP-123, EXP-124, EXP-125

## Test plan
- 84 unit tests passing
- Integration tests against real PG/Redis
EOF
)"
```

**Al encontrar un bug o deuda tecnica**:
```
Claude detecta bug → crea issue en Linear con repro steps → continua trabajando
```

### 29.7 Regla MANDATORY en CLAUDE.md

Agregar la seccion "MANDATORY: Linear Integration" al CLAUDE.md del proyecto. Esta regla codifica exactamente cuando Claude debe interactuar con Linear y cuando no.

El contenido de la regla debe cubrir:
1. Al inicio de sesion: leer backlog
2. Durante code gen: `Closes EXP-XXX` en commits y PRs
3. Bugs/LL con accion: crear issue
4. Fin de sesion: actualizar issues en progreso

Ver la seccion "MANDATORY: Linear Integration" en el CLAUDE.md de ExpertIA como referencia.

### 29.8 Lecciones aprendidas de Linear en ExpertIA

| # | Problema | Causa raiz | Que hacer diferente |
|:-:|---------|-----------|-------------------|
| 1 | 50 issues creados, 0 referenciados en commits | Linear se configuro pero el agente no tenia la regla de usarlo | Agregar regla MANDATORY en CLAUDE.md |
| 2 | GitHub ↔ Linear no conectado hasta el final | Accion manual que nadie recordo hacer | Incluir en Setup Operativo checklist |
| 3 | `@modelcontextprotocol/server-linear` no existe | Documentacion de MCP desactualizada | Usar `@mseep/linear-mcp` (verificado) |
| 4 | Node 18 incompatible con MCP SDK | nvm default apuntaba a Node 18 | Siempre verificar `node --version >= 20` |
| 5 | CLI `claude mcp add -e` no funciona | Bug del CLI con flag -e y nombre positional | Configurar directamente en `~/.claude.json` |
| 6 | Issues retroactivos no agregan valor | El trabajo ya estaba hecho sin trazabilidad | Configurar Linear ANTES de code gen |

**Conclusion**: Linear agrega valor hacia adelante (planificacion, trazabilidad futura), no hacia atras (documentar lo que ya se hizo). Configurarlo durante Setup Operativo, no despues.

---

## Lecciones adicionales de ExpertIA para Build & Test y Cierre

### Auditoría formal de compliance AIDLC antes del primer merge (LL-014)

Antes de mergear a main por primera vez, ejecutar una auditoria formal de compliance AIDLC. En ExpertIA, esta auditoria de ~130 checks revelo 9 hallazgos que nadie habia detectado: security extension no rastreada, 4 units sin audit trail, artefactos de diseno faltantes, skills no creados. Sin la auditoria, el PR se habria mergeado con gaps de trazabilidad graves.

**Que verificar**:

- Todos los archivos que la metodologia define existen
- aidlc-state.md es consistente con el estado real del proyecto
- Security extension configurada y rastreada (si aplica)
- Audit entries para cada unit que tiene code gen completo
- Todos los artefactos de diseno mencionados en infrastructure-design.md existen en el workspace

La auditoria debe producir un score cuantificable: "86/86 PASS, 0 FAIL, 100% compliance" — un dato objetivo comparable entre proyectos.

### Codigo huerfano es peor que codigo faltante (LL-020)

Codigo de infraestructura que existe, tiene docstrings y tests unitarios, pero nadie lo invoca en la aplicacion. Da la impresion de que la funcionalidad existe ("LangFuse esta integrado") cuando en realidad no lo esta. La Definition of Done debe incluir no solo "archivo existe" sino "archivo se usa". Para codigo de infraestructura (clientes SDK, middleware, adapters), verificar con grep que al menos 1 consumer lo importa y lo invoca.

### Items deferred deben trackearse con issue ID (LL-029)

Skips en tests, TODOs en codigo, issues bloqueados por dependencias — todos deben tener un issue asociado en el tracker (Linear, GitHub Issues). Sin tracking, los items deferred se olvidan y se descubren tarde cuando ya es costoso arreglarlos. El 3-Step Closure se convierte en 4-Step cuando hay dependencias deferred: artefacto + state + audit + **tracker**.

### Cuando una metrica cambia, grep TODO el proyecto (LL-026)

Cuando un conteo cambia (tests, ADRs, skips, status de fase), hacer grep en toda la documentacion por el valor anterior y actualizar CADA ocurrencia. No basta con actualizar "el archivo principal" — la documentacion AIDLC es un sistema de verdad distribuido. Si una tabla dice 20 PASS y otra dice 22 PASS en el mismo archivo, el audit de cierre falla.
