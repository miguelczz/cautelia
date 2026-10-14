## Paso 32: Harness Engineering — Enforcement Programatico

### 32.1 Que es Harness Engineering

Harness Engineering es la disciplina de disenar sistemas de control alrededor del modelo de IA. No se trata de lo que el modelo "sabe" — se trata de lo que el entorno le permite y le impide hacer.

**La evidencia es contundente**: el mismo modelo con un harness optimizado paso de 52.8% a 66.5% en Terminal Bench 2.0. No cambiaron los pesos del modelo, no cambiaron los prompts base. Cambio el harness — los hooks, los scripts de validacion, las reglas programaticas que envuelven al agente. El harness define el techo de lo que el agente puede hacer.

En el proyecto ExpertIA, esta leccion se aprendio de la forma dolorosa: 23 errores documentados (LL-001 a LL-023) fueron causados por reglas escritas como texto en CLAUDE.md que el agente olvido bajo presion de contexto. La solucion: convertir CADA regla de texto en un check programatico.

### 32.2 Por que importa

El problema fundamental es simple: un agente de IA opera con un contexto finito. A medida que el contexto crece, las instrucciones mas antiguas pierden peso. Las reglas escritas como texto — por mas claras que sean — eventualmente se olvidan.

Ejemplos reales de ExpertIA:

- **LL-009**: Secrets hardcodeados en defaults de funciones. La regla "no hardcodees secrets" estaba en CLAUDE.md. El agente la olvido en la Unit 4.
- **LL-020**: Codigo huerfano generado en directorios que ya no se usaban. No habia nada que detectara archivos sin importar.
- **LL-021**: Nombres de servicios Docker inconsistentes entre docker-compose.yml y el codigo. Una regla de texto no puede prevenir esto.
- **LL-022**: El agente agregaba `skip` a tests que fallaban en vez de arreglarlos. Solo un linter puede detectar `@pytest.mark.skip` sin justificacion.

**La conclusion**: las reglas de texto son necesarias para comunicar la intencion, pero insuficientes para garantizar el cumplimiento. El enforcement programatico es el unico mecanismo confiable.

### 32.3 Piramide de Enforcement — 5 niveles

Cada regla del proyecto debe vivir en el nivel mas alto posible de esta piramide:

| Nivel | Nombre | Descripcion | Ejemplo en ExpertIA |
|:-----:|--------|-------------|---------------------|
| **5** | Imposibilidad Mecanica | Hooks que bloquean el commit. Si el check falla, el commit NO se crea. | `pre-commit` ejecuta `harness-check.sh` — si falla, git rechaza el commit |
| **4** | Validacion Automatica | Scripts post-cambio que verifican estado. No bloquean el commit pero detectan inmediatamente. | `stop_gate.py` corre al cerrar sesion y reporta inconsistencias |
| **3** | Scaffolding Forzado | Templates que generan la estructura correcta por defecto. El agente no tiene que recordar el formato. | `scripts/new_unit.sh` genera la estructura de archivos con imports correctos |
| **2** | Wrappers Obligatorios | Scripts seguros que reemplazan comandos peligrosos. | `close_issue_with_evidence.py` reemplaza `mcp update_issue` directo |
| **1** | Texto en CLAUDE.md | Sugerencias que el agente lee pero puede olvidar bajo presion de contexto. | "Siempre actualiza aidlc-state.md" — olvidado 3 veces en ExpertIA |

**Meta**: mover cada regla del Nivel 1 al nivel mas alto posible. Cada vez que el agente comete un error por olvidar una regla de texto, la respuesta correcta NO es repetir la regla mas fuerte en CLAUDE.md — es convertirla en un check programatico.

### 32.4 Los 16 Checks de harness-check.sh

`harness-check.sh` es el script central que ejecuta todos los checks. Se invoca desde el hook de pre-commit y desde `stop_gate.py`. Cada check es independiente y retorna 0 (pass) o 1 (fail).

| # | Check | Origen | Script | Nivel |
|:-:|-------|--------|--------|:-----:|
| 1 | Hexagonal Boundaries | ADR-41 | `scripts/linters/hexagonal_boundaries.py` | 5 |
| 2 | Orphan Code Detector | LL-020 | `scripts/linters/orphan_detector.py` | 5 |
| 3 | Auth Coverage | SECURITY-01 | `scripts/linters/auth_coverage.py` | 5 |
| 4 | Defensive Skip Detector | LL-022 | `scripts/linters/defensive_skip_detector.py` | 5 |
| 5 | Secrets in Defaults | LL-009 | `scripts/linters/secrets_in_defaults.py` | 5 |
| 6 | Docker Service Names | LL-021 | `scripts/linters/docker_service_names.py` | 5 |
| 7 | State Consistency | LL-019 | `scripts/harness/state_consistency_check.py` | 4 |
| 8 | Ruff Format | CI-SYNC | `ruff format --check` | 5 |
| 9 | Mypy Type Check | CI-SYNC | `mypy --strict` | 5 |
| 10 | Structural Tests | — | `pytest tests/structural/` (6 tests) | 5 |
| 11 | Deferred Work Tracker | — | informacional | — |
| 12 | Linear Issue Sync | — | informacional | — |
| 13 | ADR Staleness | LL-027 | `stop_gate.py` | 4 |
| 14 | Doc Metrics Validator | — | `stop_gate.py` | 4 |
| 15 | Reservado | — | — | — |
| 16 | Reservado | — | — | — |

**Regla critica de mensajes de error**: cada check que falla DEBE producir un mensaje con tres componentes:

1. **QUE fallo** — descripcion concreta del error encontrado
2. **POR QUE existe la regla** — referencia al LL-XXX, ADR-XXX o SECURITY-XX que motivo el check
3. **COMO arreglarlo** — instruccion paso a paso para resolver

Ejemplo de mensaje correcto:

```
FAIL: Check #4 — Defensive Skip Detector
QUE: Found @pytest.mark.skip without justification in tests/unit/test_auth.py:42
POR QUE: LL-022 — Agent was adding skips to failing tests instead of fixing them
COMO: Remove the skip decorator and fix the underlying test failure, or add
      a justification comment: # SKIP: [reason] — tracked in LL-XXX
```

Ejemplo de mensaje incorrecto:

```
FAIL: skip detected
```

El primer formato permite que el agente se auto-corrija sin asistencia humana. El segundo genera confusion y mas errores.

### 32.5 CI Feedback Loop

Los checks marcados **CI-SYNC** en la tabla anterior representan un patron importante: checks que originalmente solo existian en CI y que se trajeron al harness local despues de fallar repetidamente.

**El patron es**:

```
1. CI tiene un check que el harness local no tiene
2. El agente hace push → CI falla
3. El agente corrige → push → CI falla de nuevo (variante diferente)
4. Leccion aprendida: agregar el check al harness local
5. Ahora el check falla ANTES del push, ahorrando ciclos
```

**Ejemplo real**: `ruff format` y `mypy` no estaban en el harness original de ExpertIA. El agente hacia push, CI fallaba por formato o tipos, el agente corrigia un archivo pero rompia otro. Despues de 3 ciclos fallidos, ambos checks se agregaron al harness local como Check #8 y #9. Desde entonces, cero fallos de CI por formato o tipos.

**Regla**: si un check de CI falla 2 o mas veces por la misma categoria de error, ese check debe migrarse al harness local.

### 32.6 Hooks en .claude/settings.json

Claude Code soporta hooks que se ejecutan automaticamente en momentos clave. En ExpertIA, se configuraron 4 tipos:

#### PreToolUse — antes de git commit

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "git commit",
        "command": "bash scripts/harness-check.sh"
      }
    ]
  }
}
```

Si `harness-check.sh` retorna exit code != 0, el commit se bloquea. Este es el mecanismo de Nivel 5.

#### PreToolUse — antes de git tag

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "git tag",
        "command": "bash scripts/verify_all_gates.sh"
      }
    ]
  }
}
```

Tags marcan milestones formales. `verify_all_gates.sh` ejecuta los 16 checks mas validaciones adicionales de estado.

#### PostToolUse — despues de cambios de codigo

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "bash scripts/incremental_check.sh"
      }
    ]
  }
}
```

Despues de cada edicion de archivo, se ejecutan checks incrementales relevantes al archivo modificado. No los 16 — solo los que aplican.

#### Stop — al cerrar sesion

```json
{
  "hooks": {
    "Stop": [
      {
        "command": "python scripts/stop_gate.py"
      }
    ]
  }
}
```

`stop_gate.py` es el guardian final. Ejecuta 13+ checks incluyendo:

- ADR Staleness — ningun ADR referencia archivos que ya no existen
- Doc Metrics Validator — metricas en documentos son consistentes entre archivos
- CLAUDE.md Line Count — CLAUDE.md no excede el limite de lineas (evita bloat)
- State Consistency — aidlc-state.md refleja el estado real del proyecto
- Linear Sync — issues en Linear coinciden con el estado local

Si `stop_gate.py` falla, el agente recibe un warning con los items que debe resolver antes de cerrar.

### 32.7 Progressive Disclosure — .claude/rules/

No todas las reglas aplican en todo momento. Cargar 370 lineas de reglas al inicio de cada sesion desperdicia contexto. La solucion (ADR-056): **5 archivos de reglas que se cargan por contexto**.

| Archivo | Cuando se carga | Contenido |
|---------|----------------|-----------|
| `always.md` | En toda sesion | 3-Step Closure, ADR Compliance, State Consistency, Linear protocol |
| `before-code-gen.md` | Antes de generar codigo | Setup Gate, Secrets Gate, Playbook de la unidad |
| `during-code-gen.md` | Durante generacion | Lessons Capture, Code Wiring, Design-to-Code mapping |
| `before-commit.md` | Antes de commit | Docker Names check, Checkbox Enforcement, harness-check.sh |
| `documentation.md` | Al editar docs | Definition of Done, Content Validation, metricas consistency |

**El principio**: el agente solo ve las reglas relevantes al momento actual. Esto reduce ruido de contexto y aumenta la probabilidad de cumplimiento. Las reglas en `always.md` son las unicas que compiten permanentemente por atencion de contexto — deben ser minimas y criticas.

### 32.8 Formula de Conversion — Regla a Enforcement

Cuando aparece un error nuevo (o se repite uno existente), usar este arbol de decision para determinar el nivel de enforcement:

```
¿Se puede detectar la violacion programaticamente?
│
├── SI → ¿Se puede bloquear ANTES del commit?
│         │
│         ├── SI → Pre-commit hook (Nivel 5)
│         │        Ejemplo: hexagonal_boundaries.py detecta
│         │        imports cruzados entre capas → bloquea commit
│         │
│         └── NO → Test arquitectonico post-cambio (Nivel 4)
│                  Ejemplo: state_consistency_check.py verifica
│                  coherencia entre archivos → reporta en stop_gate
│
└── NO → ¿Se puede generar la estructura correcta automaticamente?
          │
          ├── SI → Script de scaffolding (Nivel 3)
          │        Ejemplo: new_unit.sh genera la estructura
          │        de directorios con imports correctos
          │
          └── NO → ¿Se puede encapsular en un wrapper seguro?
                    │
                    ├── SI → Wrapper obligatorio (Nivel 2)
                    │        Ejemplo: close_issue_with_evidence.py
                    │        reemplaza update_issue directo
                    │
                    └── NO → Queda como texto en CLAUDE.md (Nivel 1)
                             Ejemplo: "Comunicar cambios de plan
                             al usuario antes de ejecutar"
```

**Nota**: el Nivel 1 es el ultimo recurso, no el default. Si una regla lleva mas de 2 sesiones en Nivel 1 y el agente la ha violado, es evidencia de que necesita subir de nivel.

### 32.9 Las 8 Lecciones del Harness Engineering

Lecciones destiladas del caso OpenAI/Codex y validadas con la experiencia de ExpertIA:

| # | Leccion | Significado | Aplicacion en ExpertIA |
|:-:|---------|-------------|----------------------|
| 1 | **Map not manual** | Si el modelo puede derivar la accion de un mapa, no escribas instrucciones paso a paso | ADR index reemplaza instrucciones de "donde poner cada decision" |
| 2 | **Design environment** | Los resultados del modelo son funcion del entorno, no solo del prompt | 16 checks en harness-check.sh definen lo que el agente puede producir |
| 3 | **Enforce mechanically** | Toda regla que pueda violarse, sera violada. Bloquea mecanicamente. | pre-commit hooks bloquean commits que violan arquitectura hexagonal |
| 4 | **Boring tech** | Usa tecnologia aburrida y probada. El agente no necesita innovar en tooling. | bash + python scripts, no frameworks custom de enforcement |
| 5 | **Entropy as GC** | Trata la entropia como garbage collection — limpiala continuamente | orphan_detector.py elimina codigo muerto cada commit |
| 6 | **Context engineering** | El contexto es un recurso escaso. Optimiza que ve el modelo y cuando. | .claude/rules/ con 5 archivos por contexto (ADR-056) |
| 7 | **Agent-to-agent review** | Un agente no puede revisar su propio trabajo. Usa otro agente o un script. | harness-check.sh es el "segundo agente" que revisa cada commit |
| 8 | **Feedback loops** | Cada fallo debe generar un nuevo check. El harness crece con cada error. | LL-022 → defensive_skip_detector.py. LL-020 → orphan_detector.py |

### 32.10 Anti-Patrones

Errores comunes en la implementacion de harness engineering. Cada uno fue observado en ExpertIA o en proyectos similares:

| # | Anti-Patron | Descripcion | Consecuencia |
|:-:|-------------|-------------|--------------|
| 1 | **CLAUDE.md monolitico** | Un archivo de 370+ lineas con todas las reglas | El agente olvida reglas al final del archivo |
| 2 | **Check sin mensaje de error** | El script retorna exit 1 sin explicar que fallo | El agente no puede auto-corregir |
| 3 | **Check sin POR QUE** | El mensaje dice que fallo pero no por que existe la regla | El agente "arregla" el sintoma sin entender la causa |
| 4 | **Check sin COMO** | El mensaje explica el error pero no como resolverlo | El agente inventa una solucion que puede ser incorrecta |
| 5 | **Harness que no crece** | Los mismos checks desde el dia 1. No se agregan nuevos tras errores. | Los errores se repiten porque no hay feedback loop |
| 6 | **Over-enforcement** | Checks tan estrictos que bloquean trabajo legitimo | El agente gasta ciclos luchando contra el harness |
| 7 | **Checks lentos** | El harness tarda 60+ segundos en ejecutar | El desarrollador/agente lo desactiva o lo ignora |
| 8 | **Checks duplicados** | El mismo check en pre-commit, CI y stop_gate sin razon | Tiempo desperdiciado, confusion sobre cual es la fuente de verdad |
| 9 | **Regla de texto disfrazada** | Un "check" que solo imprime un recordatorio sin verificar nada | Falsa sensacion de enforcement |
| 10 | **Harness invisible** | Los checks existen pero el agente no sabe que existen | El agente no incorpora los checks en su flujo de trabajo |
| 11 | **Skip sin auditoria** | Permitir `--skip-checks` sin registrar quien y por que | Se normaliza saltarse el harness |
| 12 | **Check acoplado** | Un check que depende del estado de otro check | Fallos en cascada dificiles de diagnosticar |
| 13 | **Enforcement reactivo puro** | Solo agregar checks despues de errores, nunca proactivamente | Se pierden categorias enteras de errores prevenibles |
| 14 | **Harness sin tests** | Los scripts de linting no tienen sus propios tests | Un bug en el linter causa falsos positivos/negativos |
| 15 | **Config hardcodeada** | Paths, nombres de servicios y umbrales hardcodeados en los scripts | Rompe al cambiar estructura del proyecto |

### 32.11 Como Agregar un Nuevo Linter

Procedimiento paso a paso para agregar un check nuevo al harness:

**Paso 1: Crear el script**

```bash
# scripts/linters/nuevo_check.py
"""
Check #XX — Nombre del Check
Origen: LL-XXX / ADR-XXX / SECURITY-XX
"""
import sys

def check():
    errors = []
    # ... logica de deteccion ...

    if errors:
        print("FAIL: Check #XX — Nombre del Check")
        for e in errors:
            print(f"  QUE: {e['what']}")
            print(f"  POR QUE: {e['why']}")
            print(f"  COMO: {e['how']}")
            print()
        return 1

    print("PASS: Check #XX — Nombre del Check")
    return 0

if __name__ == "__main__":
    sys.exit(check())
```

**Reglas del script**:
- Retorna 0 si pasa, 1 si falla
- Los mensajes de error SIEMPRE tienen QUE / POR QUE / COMO
- El script debe ejecutarse en < 5 segundos
- Sin dependencias externas mas alla de la stdlib cuando sea posible

**Paso 2: Agregar a harness-check.sh**

```bash
# En harness-check.sh, agregar al array de checks:
checks+=("python scripts/linters/nuevo_check.py")
```

**Paso 3: Crear test estructural**

```python
# tests/structural/test_nuevo_check.py
"""Verifica que el linter detecta violaciones conocidas."""

def test_detecta_violacion():
    """Fixture con violacion conocida → debe retornar 1."""
    # ...

def test_permite_codigo_correcto():
    """Fixture sin violacion → debe retornar 0."""
    # ...
```

**Paso 4: Documentar**

- Agregar entrada en la tabla de checks (seccion 32.4 de esta guia)
- Si el check origino de un Lessons Learned, actualizar el LL correspondiente con referencia al check
- Si origino de un ADR, agregar referencia cruzada en el ADR

**Paso 5: Verificar integracion**

```bash
bash scripts/harness-check.sh  # debe incluir el nuevo check
pytest tests/structural/       # debe pasar incluyendo el nuevo test
```

### 32.12 CLAUDE.md Minimo que Funciona

El anti-patron mas comun es un CLAUDE.md de 370+ lineas con todas las reglas del proyecto escritas como texto. El agente lee las primeras 100 lineas con atencion, las siguientes 100 con menos atencion, y las ultimas 170 las ignora bajo presion de contexto.

**La solucion**: CLAUDE.md como indice de ~100 lineas que apunta a enforcement scripts y `.claude/rules/`.

Estructura del CLAUDE.md refactorizado:

```markdown
# CLAUDE.md — ExpertIA

## Proyecto
ExpertIA — AI-powered competency management platform
Stack: FastAPI + PostgreSQL + Hexagonal Architecture

## Enforcement
ALL rules are enforced programmatically. See:
- Pre-commit: scripts/harness-check.sh (16 checks)
- Session exit: scripts/stop_gate.py (13+ gates)
- Context rules: .claude/rules/ (5 files, loaded by context)

## Quick Reference
- Architecture: ADR index → aidlc-docs/adr/
- Lessons: aidlc-docs/lessons-learned.md
- State: aidlc-docs/aidlc-state.md
- Linear: [project URL]

## Critical (always active)
1. 3-Step Closure: state → audit → Linear (on every commit)
2. ADR Compliance: check ADR index before architectural decisions
3. harness-check.sh must pass before every commit
```

**El principio**: 30 lineas que apuntan a enforcement son mas efectivas que 370 lineas de reglas que se olvidan. El poder no esta en el texto — esta en los scripts que el texto referencia.

Cada linea de CLAUDE.md debe ganarse su lugar. Si una regla puede ser un check programatico, no necesita estar en CLAUDE.md. Si una regla no puede ser un check, necesita estar en `.claude/rules/` con el contexto apropiado. CLAUDE.md solo debe contener lo que el agente necesita saber en TODA sesion — el minimo absoluto.
