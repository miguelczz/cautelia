## Paso 30: Ejecucion de Operations (7 Stages)

### 30.1 Que es Operations

Operations es la **tercera y ultima fase** del framework AI-DLC. Si Inception responde "QUE construir" y Construction responde "COMO construirlo", Operations responde **"COMO desplegarlo y operarlo"**.

Operations toma el codigo que salio de Construction (tag `v0.1.0-construction`) y lo convierte en un sistema listo para produccion: servicios configurados, CI/CD verde, tests ejecutados contra la stack real, observabilidad conectada, y procedimientos de incidentes documentados.

```
INCEPTION (QUE)  →  CONSTRUCTION (COMO)  →  OPERATIONS (COMO desplegarlo)
                                                ├── Stage 0: Kickoff
                                                ├── Stage 1: Service Config & Hardening
                                                ├── Stage 2: Deployment & CI/CD
                                                ├── Stage 3: Deferred Testing
                                                ├── Stage 4: Monitoring & Observability
                                                ├── Stage 5: Production Readiness
                                                └── Stage 6: Incident Response & Maintenance
```

### 30.2 Stage 0: Kickoff

**Que hace**: Crea la infraestructura de trabajo para Operations — branch, epic en Linear, y plan de ejecucion.

**Artefactos generados**:
- Branch `operations` desde tag `v0.1.0-construction`
- Epic de Operations en Linear con issues por stage
- `operations-plan.md` con scope, stages, y criterios de cierre

**Criterio de cierre**: Branch creado, epic poblado, plan aprobado por el usuario.

**Completado**: 2026-03-20

**Leccion**: No crear el branch desde `main` — crearlo desde el **tag de Construction**. Esto garantiza que Operations parte exactamente del punto que paso Build & Test.

### 30.3 Stage 1: Service Configuration & Hardening

**Que hace**: Configura TODOS los servicios del sistema para que arranquen correctamente, con seguridad y aislamiento multi-tenant.

**Artefactos generados**:
- **Keycloak `realm.json`**: Roles (`admin`, `clinician`, `viewer`), clients (`expertia-backend`, `expertia-frontend`), tenant groups. Importacion automatica al arrancar el contenedor.
- **Docker Compose con 16 servicios**: Cada servicio con health check definido. Sin health checks, `docker compose up` no puede distinguir "arrancando" de "colgado".
- **PostgreSQL con RLS multi-tenancy**: Row-Level Security policies que aislan datos por tenant. Verificado con tests que prueban cross-tenant leaks.
- **Auditoria de variables de entorno**: `.env.example` con 63 variables documentadas (nombre, proposito, valor default o placeholder).
- **Password policy enforcement**: Longitud minima 12, complejidad (mayuscula + minuscula + digito + especial), historial de 3 passwords anteriores.

**Criterio de cierre**: `docker compose up -d` arranca 16 servicios healthy. `.env.example` completo. Keycloak realm importado automaticamente.

### 30.4 Stage 2: Deployment Procedures & CI/CD

**Que hace**: Configura el pipeline de CI/CD y el API Gateway para que cada push a `main` sea verificado automaticamente.

**Artefactos generados**:
- **GitHub Actions pipeline con 7 jobs**:

| Job | Que verifica |
|-----|-------------|
| lint | Ruff + gitleaks (codigo limpio, sin secrets) |
| typecheck | mypy strict (tipos correctos) |
| unit | pytest tests/unit/ (logica aislada) |
| integration | pytest tests/integration/ contra PG + Redis (logica con infra) |
| contract | pytest tests/contracts/ (interfaces entre capas) |
| gateway-tests | pytest tests/infra/ con KrakenD (rutas del gateway) |
| docker-build | docker compose build (imagen construye sin error) |

- **KrakenD API Gateway**: Configuracion de rutas, rate limiting, CORS, JWT validation.
- **Docker build verification**: Cada PR verifica que la imagen se construye correctamente.

**Criterio de cierre**: Push a branch → 7/7 jobs green. KrakenD rutas verificadas con tests.

### 30.5 Stage 3: Deferred Testing Execution

**Que hace**: Ejecuta los tests que se **escribieron** durante Construction pero **nunca se corrieron** contra la stack real. Construction genera instrucciones de testing; Operations las ejecuta.

**Tipos de tests ejecutados**:
- **E2E tests**: Flujos completos de usuario contra la API real
- **Security tests**: Password policy, CORS, headers, token validation
- **Clinical tests**: Validacion de datos clinicos, rangos, formatos
- **Performance tests**: Tiempos de respuesta, carga concurrente

**Resultado**: 263 tests totales con CI green.

**Lecciones aprendidas criticas**:

> **LL-022: Los skips defensivos enmascaran fallos reales.** Durante la ejecucion inicial, muchos tests tenian `if response.status_code == 404: pytest.skip("endpoint not available")`. Esto hacia que el test suite reportara "263 passed, 12 skipped" — parecia verde pero esos 12 skips eran **bugs reales** (endpoints mal configurados, rutas faltantes en el gateway). **Regla**: Un skip en un test SOLO es valido si la condicion de skip es algo que genuinamente no aplica al entorno, no si es un error que deberia investigarse.

> **LL-017: Verificar secrets antes de ejecutar tests.** Multiples tests fallaron con errores crípticos porque las variables de entorno no estaban configuradas. Antes de correr el suite completo, ejecutar `env | grep -c EXPERTIA` y verificar que coincide con `.env.example`.

### 30.6 Stage 4: Monitoring & Observability

**Que hace**: Conecta la telemetria del sistema para que se pueda **ver** que pasa en produccion.

**Artefactos generados**:
- **OTel Collector**: Recibe traces y metricas de la aplicacion via OpenTelemetry
- **LangFuse**: Traza llamadas a LLMs (prompts, tokens, latencia, costos)
- **Grafana dashboards**: Visualizacion de metricas, logs, y traces
- **ObservabilityMiddleware**: Wired en `app.py` lifespan — cada request genera un trace automaticamente
- **Loki + Promtail**: Agregacion de logs de todos los contenedores Docker

**Criterio de cierre**: Request a la API → trace visible en Grafana. Llamada a LLM → trace en LangFuse. Logs de todos los servicios en Loki.

**Leccion aprendida critica**:

> **LL-020: Codigo sin consumidores es codigo muerto.** En el proyecto ExpertIA, las funciones `get_langfuse()` y `setup_otel()` existian desde Construction — estaban perfectamente escritas, con tests unitarios que pasaban. Pero **nadie las llamaba**. No estaban wired en el lifespan de FastAPI. El test unitario mockeaba la conexion, asi que pasaba. Pero en realidad, el sistema no generaba ni un solo trace. **Regla**: Despues de escribir codigo de infraestructura (observabilidad, cache, auth), verificar que existe un **consumidor real** que lo invoca. Un `grep -r "get_langfuse()" --include="*.py" | grep -v test | grep -v __pycache__` debe retornar al menos una linea en codigo de produccion.

### 30.7 Stage 5: Production Readiness

**Que hace**: Evalua el sistema contra un checklist formal de 27 items que cubren todos los aspectos de un sistema production-ready.

**Checklist de 27 items**:

| Categoria | Items | Que cubre |
|-----------|-------|-----------|
| Security | 6 | TLS, secrets management, CORS, password policy, gitleaks |
| Data Protection | 4 | RLS, backups, encryption, audit trail |
| Reliability | 4 | Health checks, graceful shutdown, retry logic, circuit breakers |
| Backup | 3 | Cron schedule, retention policy, restore procedure |
| Observability | 4 | Traces, metrics, logs, dashboards |
| CI/CD | 3 | Pipeline green, docker build, pre-commit |
| Documentation | 3 | Runbooks, ADRs, deployment guide |

**Resultado**: **27/27 PASS**. 6 items marcados N/A con justificacion (son requisitos de produccion cloud que no aplican a un deployment Docker local):
- HTTPS / TLS termination (sin reverse proxy en local)
- HSTS headers (requiere HTTPS)
- Rate limiting en gateway (configurado pero no enforceable sin proxy)
- DICOM purge schedule (sin datos DICOM en MVP)
- Dead Letter Queue (sin message broker en MVP)
- Alert notification channel (alertas definidas, sin Slack/PagerDuty configurado)

**Backup cron**: Ejecucion diaria a las 02:00 COT. Retencion: 7 backups diarios + 4 semanales.

**Lecciones aprendidas**:

> **LL-018: Nunca marcar complete sin verificacion real.** En ExpertIA, el checklist se marco 27/27 en la primera pasada. Pero al verificar item por item con comandos reales (`docker compose exec db pg_dump ...`, `curl -I localhost:8000 | grep Strict`), 4 items fallaron. **Regla**: Cada item del checklist debe tener un **comando de verificacion** y su **salida real** registrada.

> **LL-019: aidlc-state.md GANA sobre documentos de resumen cuando hay contradiccion.** El summary de Operations decia "263 tests" pero `aidlc-state.md` decia "257 tests". El state es la fuente de verdad porque se actualiza con cada commit; los summaries se generan una vez y se desactualizan. **Regla**: Antes del cierre, ejecutar un State Consistency Check — comparar metricas clave entre `aidlc-state.md` y los summaries.

### 30.8 Stage 6: Incident Response & Maintenance

**Que hace**: Documenta que hacer cuando algo falla en produccion y como mantener el sistema operativo.

**Artefactos generados**:
- **Runbooks (9+ escenarios)**: Procedimientos paso a paso para incidentes comunes (DB down, service OOM, auth failure, backup restore, migration rollback, etc.)
- **Alert rules (6 en Grafana)**: Container down, high error rate, slow response, disk usage, backup failure, certificate expiry
- **On-call procedures**: Escalation path, response SLAs, communication templates
- **Maintenance workflows**: Update procedures, dependency upgrades, security patches

**Criterio de cierre**: Runbooks cubren los 9 escenarios mas probables. Alert rules configuradas en Grafana. Procedimientos de on-call documentados.

### 30.9 Resumen de Operations

| Stage | Nombre | Completado | Tests | Artefactos clave |
|:-----:|--------|:----------:|:-----:|-----------------|
| 0 | Kickoff | 2026-03-20 | — | Branch, epic, plan |
| 1 | Service Config & Hardening | 2026-03-20 | 16 health checks | realm.json, docker-compose, .env.example |
| 2 | Deployment & CI/CD | 2026-03-21 | 7 CI jobs | GitHub Actions, KrakenD config |
| 3 | Deferred Testing | 2026-03-21 | 263 tests | E2E, security, clinical, performance |
| 4 | Monitoring & Observability | 2026-03-21 | — | OTel, LangFuse, Grafana, Loki |
| 5 | Production Readiness | 2026-03-22 | 27/27 checklist | Production readiness report |
| 6 | Incident Response | 2026-03-22 | — | 9 runbooks, 6 alert rules |

---

## Paso 31: Operations Closure Protocol

### 31.1 Que es el Closure Protocol

El cierre de Operations NO es simplemente marcar el ultimo stage como COMPLETE. Es un **protocolo formal** con 13 fases de ejecucion que garantiza que el sistema esta realmente listo y que no quedan cabos sueltos.

La razon de tener un protocolo tan riguroso: en Construction se aprendio (LL-007, LL-012) que marcar cosas como "complete" sin verificacion real genera la deuda tecnica mas grave del proyecto. Operations aplica esa leccion al extremo.

### 31.2 Las 13 Fases de ejecucion

El closure se ejecuta como una secuencia de fases, cada una con un objetivo especifico:

| Fase | Objetivo | Que se verifica |
|:----:|----------|----------------|
| 1 | Bug fixes | Resolver todos los bugs encontrados durante Operations |
| 2 | Docker stack | `docker compose up` → 16 servicios healthy |
| 3 | Offline tests | Tests que no requieren stack (unit, contract, structural) |
| 4 | Stack tests | Tests contra la stack real (integration, infra, security) |
| 5 | Production readiness | 27/27 checklist items PASS |
| 6 | CI/CD | 7/7 jobs green en GitHub Actions |
| 7 | Documentation | Todos los artefactos generados y actualizados |
| 8 | Infrastructure tests | Tests del gateway, health checks, service discovery |
| 9 | Traceability | Cada issue de Linear tiene commits asociados |
| 10 | Security tests | Suite de seguridad completo ejecutado |
| 11 | AIDLC docs | aidlc-state.md, audit, summaries consistentes |
| 12 | Resolve skips | 0 pytest.skip() defensivos — todos resueltos o justificados |
| 13 | Formal closure | Tag + 3-Step Closure |

### 31.3 Definition of Done — regla absoluta

El cierre de Operations tiene una regla no negociable:

> **0 skips, 0 fails.**

No se permite cerrar con tests skipped "porque el endpoint no esta disponible" ni con tests failed "porque es un flaky". Cada skip y cada fail se investiga y se resuelve. Si un test genuinamente no aplica, se marca como `@pytest.mark.skip(reason="N/A: requiere GPU")` con una justificacion explicita que NO sea "el endpoint devuelve 404".

En el proyecto ExpertIA, esta regla obligo a resolver 12 skips defensivos que estaban enmascarando bugs reales (LL-022). Sin esta regla, esos bugs habrian llegado a produccion.

### 31.4 State Consistency Check

Antes del cierre formal, se ejecuta una verificacion de consistencia:

```
Para cada metrica clave (test count, ADR count, LL count, checklist score):
  1. Leer el valor en aidlc-state.md
  2. Leer el valor en el summary correspondiente
  3. Si difieren → corregir el summary (aidlc-state.md gana)
```

Esta verificacion existe porque los summaries se generan una vez y se desactualizan a medida que se resuelven bugs y se agregan tests. El `aidlc-state.md` se actualiza con cada commit (enforced por el harness), asi que siempre tiene el valor correcto.

### 31.5 Formal Closure — tag + 3-Step Closure

El cierre formal consiste en:

1. **Tag de milestone**: `git tag v0.2.1-operations && git push origin v0.2.1-operations`
2. **3-Step Closure** (el mismo protocolo que se usa en cada stage):
   - **Artefacto**: Summary de Operations actualizado con metricas finales
   - **aidlc-state.md**: Fase Operations marcada COMPLETE con timestamp
   - **Audit log**: Entrada formal de cierre con metricas y aprobacion del usuario

### 31.6 Deferred Work Tracker

No todo se puede resolver en Operations. Los items que requieren prerequisitos que no existen aun (ej: cluster Kubernetes, dominio DNS, certificado SSL) se registran en un **Deferred Work Tracker**:

```
| Item | Prerequisito | Trigger |
| HTTPS/TLS | Dominio + cert | Cuando se configure el dominio de produccion |
| Rate limiting enforcement | Reverse proxy | Cuando se despliegue detras de nginx/traefik |
| Alert notifications | Slack workspace | Cuando se configure el canal de ops |
```

Cada item tiene un **trigger** — la condicion que debe cumplirse para que el item se pueda resolver. Esto evita que el item se olvide y al mismo tiempo evita bloquear el cierre por algo que genuinamente no se puede hacer todavia.

### 31.7 Metricas finales alcanzadas

El proyecto ExpertIA cerro Operations con las siguientes metricas:

| Metrica | Valor |
|---------|-------|
| **Tests totales** | 317 (175 unit + 32 contract + 50 integration + 6 structural + 43 infrastructure + 11 security) |
| **CI/CD** | 7/7 jobs green |
| **Production readiness** | 27/27 PASS (6 N/A justificados) |
| **Harness checks** | 16/16 PASS |
| **ADRs totales** | 56 |
| **Lessons Learned** | 27 |
| **Skips defensivos** | 0 (12 resueltos durante closure) |
| **Fails** | 0 |

### 31.8 Lecciones aprendidas especificas de Operations

Estas lecciones emergieron durante Operations y son criticas para futuros proyectos:

| # | Leccion | Tipo | Detalle |
|:-:|---------|------|---------|
| LL-018 | Nunca marcar complete sin verificacion | anti-patron | El checklist de production readiness se marco 27/27 sin ejecutar los comandos de verificacion. 4 items fallaron al verificar con comandos reales. **Regla**: cada item necesita un comando y su salida registrada. |
| LL-019 | State consistency — aidlc-state.md es fuente de verdad | patron-exitoso | Cuando hay contradiccion entre `aidlc-state.md` y un summary, el state gana. Los summaries se desactualizan; el state se actualiza con cada commit. |
| LL-020 | Verificacion de wiring (consumidores) | anti-patron | Codigo de infraestructura (`get_langfuse()`, `setup_otel()`) existia con tests unitarios pasando, pero nadie lo llamaba en produccion. **Regla**: despues de escribir codigo de infra, grep para verificar que existe un consumidor real. |
| LL-021 | Verificacion de nombres de servicios Docker | anti-patron | Tests de infraestructura fallaban porque el nombre del servicio en el test (`postgres`) no coincidia con el nombre en `docker-compose.yml` (`db`). **Regla**: los nombres de servicios en tests deben leerse del compose, no hardcodearse. |
| LL-022 | No defensive skips en tests | anti-patron | `if 404: pytest.skip()` enmascaro 12 bugs reales. La suite reportaba verde con 12 skips que nadie investigaba. **Regla**: un skip SOLO es valido si la condicion genuinamente no aplica al entorno (ej: requiere GPU), nunca para errores HTTP. |

> **Regla de oro para Operations**: Si un test no pasa, el problema esta en el codigo o en la configuracion — NO en el test. Ajustar el test para que "pase" sin resolver la causa raiz es la forma mas rapida de acumular deuda tecnica invisible.

---

## Lecciones adicionales de ExpertIA para Operations

### Nunca marcar fase COMPLETE sin verificar contra el sistema real (LL-018)

En ExpertIA, Operations se marco como COMPLETE, se creo el tag v0.2.0 y se mergeo a main. Sin embargo, Stage 3 (Deferred Testing) nunca ejecuto tests contra un stack Docker vivo, y Stage 5 (Production Readiness) tenia 0/27 items verificados. Es exactamente el mismo patron de LL-012 (Build & Test marcado COMPLETE sin ejecutar). Las reglas preventivas de Construction no se generalizaron a Operations.

**Regla**: las Definition of Done en CLAUDE.md deben cubrir TODAS las fases, no solo Construction. Para Operations, el gate de cierre debe requerir: (1) todos los tests ejecutados contra stack vivo con resultados documentados, (2) Production Readiness Checklist con X/N items verificados, (3) cero contradicciones entre aidlc-state.md y summaries.

### State consistency — un solo source of truth (LL-019)

`aidlc-state.md` es siempre la fuente de verdad. Cuando hay contradiccion entre el state y un summary, el state GANA. En ExpertIA, el summary decia "7 stages completed" mientras el state decia "Stage 3: IN PROGRESS". El tag de release se creo siguiendo al summary optimista. **Paso 0 del 3-Step Closure**: verificar que no hay contradicciones entre aidlc-state.md y otros documentos de estado.

### Orquestador de sesiones paralelas debe hacer review sustantivo (LL-045)

Si se usa un modelo de sesiones paralelas (multiples agentes trabajando en branches), el orquestador no debe limitarse a verificar CI green y doc metrics. Debe leer el diff completo de cada PR y evaluar: decisiones de arquitectura correctas para el contexto, implicaciones de seguridad, consistencia entre ADRs, y "riesgos aceptados" que contradicen requisitos del proyecto. En ExpertIA, 2 waves se aprobaron con decisiones inseguras que el humano tuvo que detectar.

### Nombres de servicios Docker: verificar con compose, no asumir (LL-021)

Scripts de backup, restore y mantenimiento que referencian servicios Docker deben usar el nombre exacto del `docker-compose.yml`, no asumir por convencion. En ExpertIA, 8 archivos usaban `docker compose exec postgres` pero el servicio se llamaba `postgresql`. Estos scripts nunca se ejecutaron contra el stack real — de haberse probado, habrian fallado inmediatamente.
