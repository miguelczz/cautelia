## Paso 6: INCEPTION - Workflow Planning

Despues de tener requerimientos, stories, y (si aplica) ingenieria inversa, el framework planifica como ejecutar la construccion.

### 6.1 Que hace el Workflow Planning

Claude analiza todo el contexto acumulado y propone:
- Que fases ejecutar y cuales saltar (con justificacion)
- Nivel de profundidad por fase
- Analisis de impacto (que areas cambian: usuario, estructura, datos, API, NFRs)
- Nivel de riesgo del proyecto
- Secuencia de construccion

En nuestro caso: 11 fases a ejecutar, 0 saltadas, riesgo alto (medical AI + multi-tenant + regulatorio).

### 6.2 Aplicacion en diferentes escenarios

El framework funciona para multiples escenarios, no solo Greenfield:

| Escenario | Como funciona |
|-----------|--------------|
| **Greenfield** (nuevo) | Diseno completo desde cero |
| **Brownfield — nuevo feature** | Ingenieria inversa + plan de implementacion |
| **Brownfield — bug fix** | Analiza el codigo, identifica el problema, propone fix |
| **Brownfield — evolucion** | Entiende lo existente y propone cambios incrementales |
| **Brownfield — migracion** | Deberia funcionar bien (pendiente de pruebas formales) |
| **Hibrido** | Brownfield para partes existentes + Greenfield para partes nuevas (nuestro caso) |

> **Nota sobre proyectos hibridos**: En nuestro caso, el proyecto es hibrido — el pipeline DDH existe y funciona en produccion (brownfield), pero la plataforma MLOps, el multi-tenant, y el training pipeline son completamente nuevos (greenfield). La metodologia lo soporta porque el tipo brownfield/greenfield aplica a nivel de **unit** (bounded context), no de proyecto.

---

## Paso 7: INCEPTION - Application Design (Diseno de Aplicacion)

Antes de dividir el producto en unidades de trabajo, el framework establece las bases tecnicas del sistema: **componentes**, **servicios**, y **dependencias**. Estas son definiciones preliminares que proveen la plataforma sobre la cual se van a construir las unidades.

### 7.1 Que genera el Application Design

El framework genera **3 artefactos principales** + 1 de metodos:

| Artefacto | Archivo | Que define |
|-----------|---------|-----------|
| **Componentes** | `components.md` | Definiciones de estilo arquitectonico y capas. Cada componente del sistema con su proposito, responsabilidades e interfaces. |
| **Servicios** | `services.md` | Definiciones preliminares relacionadas con logica de negocio y metodos core. Cada servicio con su patron de orquestacion y comunicacion. |
| **Dependencias** | `component-dependency.md` | Dependencias entre componentes y patron de resolucion. Matrices de dependencia, diagramas de flujo de datos, orden de startup. |
| **Metodos** | `component-methods.md` | Signatures de metodos por componente con tipos de entrada/salida. |

> **No es codigo** — son definiciones de diseño. Los componentes son "que bloques tiene mi sistema", los servicios son "que capacidades provee cada bloque", y las dependencias son "como se relacionan entre si". El codigo viene despues, en la fase de Construction.

### 7.2 Preguntas de diseno

Antes de generar los artefactos, el framework genera preguntas sobre decisiones arquitectonicas que no estan claras. En nuestro caso fueron **7 preguntas** que analizamos con pros/contras detallados:

| Pregunta | Tema | Decision |
|----------|------|----------|
| Q1 | Plugin Architecture | Directorio con convencion (`plugins/ddh/`) |
| Q2 | Base de datos multi-tenant | Single DB + Row-Level Security (RLS) |
| Q3 | Frontend | Monorepo con workspaces (Turborepo) |
| Q4 | Comunicacion sync/async | REST + RabbitMQ + Redis Pub/Sub |
| Q5 | Pipeline Framework | Hibrido: State Machine Pydantic + LangGraph solo para RAG |
| Q6 | Workbench backend | REST sync dedicado con debounce |
| Q7 | Training data model | PostgreSQL + MinIO + capa de abstraccion ExperimentTracker |

> **Tip practico**: Para cada pregunta, pedimos un analisis detallado con todas las opciones, pros/contras, tabla comparativa con ratings, y recomendacion. Esto tomo tiempo pero las decisiones quedaron solidas y documentadas. Generamos un **Architecture Decision Record (ADR)** con todo el analisis — `architecture-decisions.md`.

> **Nota**: El conteo final del proyecto es **56 ADRs** (40 de Inception/Construction + ADR-41 a ADR-56 surgidos en fases cross-cutting y Operations).

> **Pregunta frecuente**: "Por que pone opciones que claramente no son las mejores?"
>
> Porque igual puede haber una razon por la cual en tu contexto especifico SI sea la opcion adecuada. La opcion "obvia" para un equipo grande no es la misma que para un desarrollador solo. El framework presenta todas las opciones para que TU decidas con informacion completa.

### 7.3 Iterar durante el diseno

> **Pregunta frecuente**: "Que pasa si durante una entrevista con el usuario tenemos que reescribir algo que ya habiamos definido? Como volvemos atras?"

Hay dos enfoques segun el tamano del cambio:

| Tamano del cambio | Que hacer |
|-------------------|----------|
| **Cambio pequeño** | Actualizar la documentacion (spec) directamente, mantener consistencia con el codigo, actualizar `aidlc-state.md` y `audit.md`. El agente maneja bien estos ajustes puntuales. |
| **Cambio grueso** | Volver a iniciar el flujo completo. Aunque ya tengas la aplicacion desplegada, el framework te vuelve a pasar por todas las fases. Es rapido porque ya tienes contexto. |

**Regla clave**: Siempre actualizar primero la **especificacion** (requirements, stories) y luego el codigo. Mantener consistencia entre ambos. Los archivos `aidlc-state.md` y `audit.md` son los que permiten retomar donde quedaste.

### 7.4 Cuando NO usar este framework

> **Pregunta frecuente**: "Lo has probado con productos mucho mas tecnicos? Por ejemplo, una libreria, un SDK."

Este framework es para **productos completos** (full projects). Para artefactos mas tecnicos como librerias o SDKs, es mejor usar frameworks mas livianos como OpenSpec. AI-DLC es robusto y completo — esa robustez no se justifica para una libreria de 500 lineas.

---

## Paso 8: INCEPTION - Units Generation (Generacion de Unidades)

Despues del Application Design, el framework divide el producto en **Units** (unidades de trabajo) — que son esencialmente **Bounded Contexts** de DDD (Domain-Driven Design).

### 8.1 Que es una Unit

Una unidad es un **contexto delimitado independiente** con:
- Su propio dominio de negocio
- Sus propios componentes y servicios
- Dependencias claras con otras units
- La capacidad de ser construida de forma independiente

> **Concepto clave**: Las unidades son dominios de contextos separados que facilitan la implementacion paralela. Al ser ligeramente acoplados, se pueden trabajar de forma independiente. Un contexto se comunica con otro porque es parte de un insumo, pero al ser ligeramente acoplados, se puede trabajar en ellos de forma distinta — no solo en la codificacion, sino tambien en el diseno.

### 8.2 Units en nuestro proyecto

El framework identifico **6 unidades de trabajo**:

| # | Unit | Tipo | Que incluye |
|---|------|------|------------|
| 1 | Core Platform | Greenfield | Auth (Keycloak), Gateway (KrakenD), DB con RLS, multi-tenant, RabbitMQ, LiteLLM, OpenTelemetry |
| 2 | CV Pipeline Framework | Hibrido | Los ABCs (Measurement, BaseCriterion, PointDetector) abstraidos a framework generico |
| 3 | DDH Plugin | Brownfield | 15 medidas, 8 detectores, 6 criterios — todo existe y funciona en produccion |
| 4 | Chat & RAG | Hibrido | RAG y chat existen; LiteLLM gateway y admin son nuevos |
| 5 | MLOps Platform | Greenfield | Model registry, training, workbench, lab CV, promotion — todo nuevo |
| 6 | Frontend | Hibrido | MVP medico existe (63 componentes); Admin MLOps es nuevo |

### 8.3 La unidad como base de la Construction Phase

> **Punto clave**: Hasta la parte de Inception se construye el diseno completo del producto. Cuando se pasa a la fase de Construction, ya no se trabaja sobre todo el producto a la vez, sino **por unidades**. Cada unidad pasa por su propio loop de: Functional Design → NFR → Infrastructure → Code → Test.

Esto permite:
- **Paralelismo**: Equipo A trabaja en Unit 1, Equipo B en Unit 2
- **Foco**: Cada ciclo de construccion es de alcance limitado
- **Independencia**: Un error en la Unit 5 (MLOps) no afecta la Unit 3 (DDH Plugin)

### 8.4 Caracteristicas clave de las Units

Cada unidad tiene 4 propiedades fundamentales de DDD:

| Propiedad | Que significa | Ejemplo |
|-----------|--------------|---------|
| **Contexto unico** | Tiene sus propios actores, entidades y acciones que solo funcionan dentro de ese contexto | Unit 3 (DDH Plugin) tiene medidas, detectores y criterios que solo aplican a DDH |
| **Acoplamiento libre** | Dependencias minimas con otras units. No necesito conocer los internos de otra unit | Unit 5 (MLOps) usa `PipelineOrchestrator` de Unit 2 pero no sabe como funciona internamente |
| **Desarrollo independiente** | Cada unit se puede construir por separado, por un equipo o agente diferente | Unit 4 (Chat & RAG) se puede construir en paralelo con Unit 2 (Pipeline) |
| **Abstraccion adecuada** | Solo expone lo necesario. No necesito conocer mas alla de la interfaz | Unit 2 expone ABCs (`Measurement`, `PointDetector`). Unit 3 los implementa sin saber del orchestrator |

> **Punto clave**: Cuando llegas al punto de las unidades, ya tienes tan organizado tu producto — dominios, contextos, historias, comportamientos — que pueden ocurrir multiples cosas:
>
> 1. **Equipo humano**: Cada equipo es dueno de una unidad y trabaja en ella de forma independiente
> 2. **Agentes de IA**: Multiples configuraciones de agentes pueden construir cada unidad por separado
> 3. **Hibrido**: Un equipo trabaja en las units criticas mientras agentes manejan las mas mecanicas
>
> Ya tienes **todo el insumo necesario** para empezar a construir. El diseno completo del producto esta listo.

### 8.5 Secuencia de construccion

No todas las units se pueden construir en paralelo — hay dependencias:

```
Fase 1 ──── Core Platform (base — todas dependen de ella)
              │
Fase 2 ──── CV Pipeline ───────┐ (paralelo — independientes)
              │                  │
              └── Chat & RAG ───┘
              │
Fase 3 ──── DDH Plugin (necesita ABCs del Pipeline)
              │
Fase 4 ──── MLOps Platform (necesita Core + Pipeline)
              │
Fase 5 ──── Frontend (necesita todos los backends)
              │
Fase 6 ──── Integracion & Testing (validacion cross-unit)
```

### 8.6 Que sigue despues de las Units

Con las units definidas, se completa toda la **fase INCEPTION**. El producto esta:
- Documentado (requirements, RE)
- Personificado (personas, stories)
- Disenado (componentes, servicios, dependencias, ADRs)
- Descompuesto (6 units con boundaries, interfaces, y secuencia de build)

La siguiente fase es **CONSTRUCTION**, donde ya no se trabaja sobre todo el producto a la vez, sino **por unidades**. Cada unit pasa por su propio loop:

```
Por cada Unit:
  1. Functional Design (diseño detallado de logica de negocio)
  2. NFR Requirements (performance, seguridad, escalabilidad)
  3. NFR Design (patrones: RLS, rate limiting, OpenTelemetry)
  4. Infrastructure Design (Docker, networking, storage)
  5. Code Generation (implementacion)
  6. Build and Test (tests unitarios, integracion)
```

---
