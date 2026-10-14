## Paso 17: SEGURIDAD — Extension de seguridad del framework AIDLC

El framework AIDLC incluye una **extension de seguridad** como constraint cross-cutting obligatorio. No es opcional — es un sistema de 15 reglas que se evaluan en cada fase del workflow.

### 17.1 Que es la extension de seguridad

La extension de seguridad vive en `.aidlc-rule-details/extensions/security/baseline/security-baseline.md`. Define **15 reglas obligatorias** (SECURITY-01 a SECURITY-15) que cubren todo el espectro de seguridad de una aplicacion.

**Comportamiento clave**:
- Son **constraints bloqueantes** — si una regla no se cumple, el framework NO permite avanzar a la siguiente fase
- Se evaluan en cada stage applicable (no en todos — el framework determina cuales aplican)
- Al completar cada stage, se reporta compliance (cumple / no cumple / N/A) por cada regla

### 17.2 Las 15 reglas de seguridad

| Regla | Nombre | Que cubre |
|-------|--------|-----------|
| **SECURITY-01** | Encryption at Rest & Transit | TLS 1.2+, cifrado en BD y storage, gestion de secrets |
| **SECURITY-02** | Access Logging | Logs en API gateways, load balancers, CDN |
| **SECURITY-03** | Application Logging | Structured logs, correlation ID, NO secrets/PII en logs |
| **SECURITY-04** | HTTP Security Headers | CSP, HSTS, X-Frame-Options, X-Content-Type-Options |
| **SECURITY-05** | Input Validation | Type checking, length bounds, sanitizacion XSS, queries parametrizadas |
| **SECURITY-06** | Least Privilege | No wildcards en permisos, separar read/write, principio de minimo privilegio |
| **SECURITY-07** | Network Config | Deny-by-default, no 0.0.0.0/0 excepto LBs publicos, endpoints privados |
| **SECURITY-08** | Access Control | Deny-by-default en rutas, IDOR prevention, CORS restrictivo, validacion server-side |
| **SECURITY-09** | Hardening | No credenciales default, error messages genericos, patches actualizados |
| **SECURITY-10** | Supply Chain | Dependencias pineadas, vulnerability scanning, SBOM, fuentes confiables |
| **SECURITY-11** | Secure Design | Defense in depth, rate limiting, casos de abuso, separacion de logica critica |
| **SECURITY-12** | Authentication | Password policy, hashing adaptativo, MFA admin, proteccion fuerza bruta |
| **SECURITY-13** | Integrity | Deserializacion segura, checksums de artefactos, SRI para scripts externos |
| **SECURITY-14** | Monitoring & Alerting | Alertas auth failures, logs append-only, retencion 90 dias, dashboards |
| **SECURITY-15** | Exception Handling | Fail-closed, cleanup de recursos, error handler global, no stack traces expuestos |

### 17.3 Mapeo a OWASP Top 10 (2025)

Las reglas estan alineadas directamente con OWASP:

| OWASP 2025 | Regla AIDLC |
|------------|-------------|
| A01 — Broken Access Control | SECURITY-08 |
| A02 — Security Misconfiguration | SECURITY-09 |
| A03 — Supply Chain Failures | SECURITY-10 |
| A06 — Insecure Design | SECURITY-11 |
| A07 — Authentication Failures | SECURITY-12 |
| A08 — Integrity Failures | SECURITY-13 |
| A09 — Logging & Alerting Failures | SECURITY-14 |
| A10 — Exception Handling | SECURITY-15 |

### 17.4 Cuando se activa la extension

Durante **Requirements Analysis**, el framework hace esta pregunta:

```
## Question: Security Extensions
Should security extension rules be enforced for this project?

A) Yes — enforce all SECURITY rules as blocking constraints
   (recomendado para aplicaciones de produccion)
B) No — skip all SECURITY rules
   (aceptable para PoCs, prototipos, proyectos experimentales)
```

La respuesta se guarda en `aidlc-state.md` bajo `## Extension Configuration`. Si no hay configuracion, **se aplica por defecto**.

### 17.5 Como funciona el enforcement

```
Al completar cada stage de Construction:

1. El framework evalua cuales reglas SECURITY-XX aplican al stage
2. Para cada regla aplicable:
   - Cumple → reporta "compliant"
   - No cumple → BLOQUEA avance, solo permite "Request Changes"
   - No aplica → reporta "N/A" con justificacion

3. Si hay findings bloqueantes:
   - Se registra en el audit log con el ID de la regla
   - No se puede avanzar hasta resolver
```

### 17.6 Donde aparece la seguridad en el workflow

```
INCEPTION
  ├── Requirements Analysis → pregunta de activacion + requisitos de seguridad
  └── User Stories → "Security Enhancements" como indicador de alta prioridad

CONSTRUCTION (por unit)
  ├── NFR Requirements → preguntas de data protection, compliance, auth, threat models
  ├── NFR Design → patrones de seguridad (middleware chain, RLS, PII redaction)
  ├── Code Generation → quality gate incluye checks de seguridad
  └── Build and Test → genera security-test-instructions.md

BUILD & TEST FINAL
  └── Security Tests → vulnerability scanning, dependency checks, auth/authz, input validation
```

### 17.7 Compliance frameworks futuros

El framework tiene placeholders para:
- **HIPAA** — cumplimiento para datos de salud
- **PCI-DSS** — cumplimiento para datos de pago
- **SOC 2** — cumplimiento para servicios cloud
- **Customer-specific** — reglas de clientes especificos

Estos estan en `.aidlc-rule-details/extensions/security/compliance/` como `.gitkeep` — no implementados aun pero la estructura esta lista.

#### Prompt para revisar compliance de seguridad

```
Revisa el estado actual de compliance de seguridad del proyecto:

1. Lee .aidlc-rule-details/extensions/security/baseline/security-baseline.md
2. Evalua cada regla SECURITY-01 a SECURITY-15 contra:
   - Los ADRs existentes
   - Los NFR requirements
   - La configuracion de infraestructura
3. Genera un reporte de compliance:
   - Reglas cubiertas (con referencia al ADR/NFR)
   - Reglas parcialmente cubiertas (que falta)
   - Reglas no cubiertas (riesgo)
4. Sugiere acciones para cerrar los gaps
```

> **Experiencia**: En proyectos medicos como ExpertIA, la seguridad no es negociable. Las reglas SECURITY-01 (encryption), SECURITY-03 (no PII en logs), SECURITY-08 (access control con RLS), y SECURITY-12 (authentication) son las mas criticas. El framework las evalua automaticamente — si generas codigo que viola alguna, te bloquea hasta que lo corrijas.

---

## 18. Best Practice: Checkpoint de Validacion entre Units

> **Aprendizaje del proyecto ExpertIA** (2026-03-20): Descubierto durante Code Generation Unit 1.

### El problema

El workflow AI-DLC define que **Build & Test** se ejecuta despues de que **todas las unidades** completen code generation. Pero en proyectos con multiples unidades dependientes (Unit 1 es foundation de Units 2-6), esperar hasta el final para validar puede ser costoso:

- Un error en el schema de DB se arrastra a 5 unidades
- Una violacion hexagonal no detectada se replica en cada unit
- Routes stub ("Not wired yet") acumulan deuda tecnica silenciosamente
- Incompatibilidades de version de Python (ej: `datetime.UTC` es 3.11+, pero el env es 3.10) se descubren tarde

### La solucion: Checkpoint Parcial post-Unit

Despues de completar el code generation de cada unit **foundation** (la que las demas dependen), ejecutar un checkpoint de validacion parcial **antes** de avanzar a la siguiente unidad. No es un Build & Test completo — es una validacion rapida de 3 puntos:

```
Checkpoint de Validacion Parcial
================================
1. Alembic migrations  — generar las migrations reales desde los modelos SQLAlchemy
                         → Valida que los modelos compilan y el schema es correcto
                         → Detecta errores de FK, tipos, naming conventions

2. DI Wiring           — conectar handlers reales a las routes via Depends
                         → Elimina stubs "Not wired yet"
                         → Valida que la cadena domain→application→infrastructure→api funciona end-to-end

3. Lint completo       — ruff check + ruff format + verificacion hexagonal de imports
                         → Detecta imports ilegales (application→infrastructure)
                         → Normaliza formato antes de que el codebase crezca
```

### Cuando aplicar

| Situacion | Checkpoint? | Razon |
|-----------|:-----------:|-------|
| Unit es foundation (Unit 1 en ExpertIA) | **SI** | Todas las demas dependen de ella |
| Unit tiene >30 archivos generados | **SI** | Alto riesgo de errores acumulados |
| Unit es pequena y aislada | No | El Build & Test final es suficiente |
| 2 units se generan en paralelo | **SI** despues de ambas | Validar los ports compartidos |

### Costo vs beneficio

- **Costo**: ~15-20 minutos por checkpoint
- **Beneficio**: Detectar errores de base que costarian horas corregir si se descubren 3 units despues

### Ejemplo real (ExpertIA Unit 1)

El checkpoint descubrio 3 problemas que se habrian propagado:

1. **`datetime.UTC` no existe en Python 3.10** — pyproject.toml decia `>=3.11` pero el env local era 3.10. Ruff con `target-version = "py311"` "upgradeaba" `timezone.utc` a `UTC`, rompiendo el runtime. Solucion: cambiar target a `py310`.

2. **6 archivos en `application/` importaban `infrastructure/logging`** — violacion hexagonal que los unit tests no detectaron (los tests tambien importaban infrastructure). El check de imports AST lo encontro. Solucion: reemplazar por `structlog.get_logger()` directo.

3. **Routes eran stubs** — 12 endpoints retornaban 501 "Not wired yet". Sin el checkpoint, habriamos generado Unit 2 asumiendo que las routes funcionaban. Solucion: crear modulo DI y conectar handlers.

### Prompt para ejecutar el checkpoint

```
Ejecuta el checkpoint de validacion parcial para Unit {N}:

1. Genera Alembic migrations desde los modelos SQLAlchemy
   - Verifica que las tablas, FKs, y RLS policies son correctas
   - Si no hay DB disponible, crea la migration manualmente

2. Wire DI — conecta los handlers a las routes
   - Crea dependencies/services.py con factory functions
   - Reemplaza stubs "Not wired yet" con handlers reales
   - Registra los routers en app.py

3. Lint completo
   - ruff check + ruff format
   - Verificar import rules hexagonales:
     domain/ NO importa de infrastructure/ ni api/
     application/ NO importa de infrastructure/
   - Re-run todos los unit tests

Reporta: tests pasando, errores de lint, violaciones hexagonales encontradas.
```

> **Nota**: Este checkpoint NO reemplaza el Build & Test formal. Solo valida que la base esta solida antes de construir encima. El Build & Test completo (integration tests, Docker Compose, CI/CD) se ejecuta despues de generar todas las unidades.
