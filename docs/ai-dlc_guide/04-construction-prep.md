## Paso 9: CONSTRUCTION - Retomar el Framework y Prepararse

### 9.1 Como retomar el framework entre sesiones

Cuando cierras Claude Code y vuelves a abrir (ya sea porque agotaste tokens, te fuiste a descansar, o paso tiempo), el framework sabe retomar donde quedaste gracias a `aidlc-state.md` y `audit.md`.

**Prompt para retomar:**
```
Confirmame en que fase de AI-DLC nos encontramos para avanzar
```

Claude lee el estado guardado, te muestra un resumen de donde estas (que fases estan completas, cual es la siguiente), y te permite continuar. Asi de simple.

> **Importante**: Retoma siempre con la **misma herramienta** con la que instalaste el framework. Si empezaste con Claude Code, sigue con Claude Code. Si empezaste con Cursor, sigue con Cursor. Cada herramienta configura el framework de forma diferente (`CLAUDE.md` para Claude Code, otra configuracion para Cursor, otra para Kiro). Mezclar herramientas puede generar inconsistencias.

### 9.2 Sobre el consumo de tokens

- **Inception es la fase mas intensiva en tokens** — genera una gran cantidad de documentacion, analisis y decisiones. Es normal que en un proyecto grande se consuman todos los tokens disponibles en esta fase.
- **Construction consume significativamente menos tokens** porque el trabajo esta enfocado por unidad, no sobre todo el producto a la vez.
- Si se agotan los tokens, simplemente espera el tiempo de recarga, vuelve a abrir Claude Code y retoma con el prompt de arriba. El progreso no se pierde.
- La fase de Inception puede durar 1-2 horas con el framework, pero esas horas generan un volumen de documentacion y decisiones que tradicionalmente tomaria dias o semanas.

> **Cambio de mentalidad**: Con agentes de IA, pasamos de **sprints de semanas** a **sprints de horas**. La velocidad cambia, pero la disciplina del proceso se mantiene.

### 9.3 Olas de construccion (Waves) y paralelismo

Las unidades se organizan en **olas de construccion** (waves) basadas en sus dependencias. El framework las identifica automaticamente — no hay que indicarle nada.

**Las olas NO son sprints**. Son el **orden** en que puedes empezar a ejecutar las unidades:

- **Ola 1**: Unidades sin dependencias — se pueden trabajar en paralelo
- **Ola 2**: Unidades que dependen de la Ola 1 — solo se pueden empezar cuando la Ola 1 este completa
- **Ola N**: Y asi sucesivamente

> **Piensa en las olas como releases**: Cada ola es un conjunto de unidades que se pueden construir y entregar juntas.

**Lo que determina las olas** es la capacidad que tengas:
- Si eres un desarrollador solo: trabajas las unidades de cada ola secuencialmente
- Si tienes equipo: asignas cada unidad de la ola a un equipo o agente diferente y trabajan en paralelo
- Si usas agentes: multiples configuraciones de agentes pueden construir cada unidad por separado

> **Nota**: No todos los proyectos generan olas explicitamente. Lo importante es que el artefacto de **dependencias** (`unit-of-work-dependency.md`) siempre muestra las relaciones entre unidades. Con eso puedes deducir el orden de construccion. Si no ves olas, revisa las dependencias y arma tu propia secuencia.

### 9.4 Los tres artefactos de Units — repaso

Al completar Units Generation, siempre se producen 3 artefactos:

| Artefacto | Archivo | Que muestra |
|-----------|---------|-------------|
| **Definicion de unidades** | `unit-of-work.md` | Cada unidad con su proposito, componentes, y las historias de usuario asociadas |
| **Mapeo de historias** | `unit-of-work-story-map.md` | Que historias pertenecen a cada unidad. Algunas historias pueden estar en multiples unidades (integraciones) |
| **Dependencias** | `unit-of-work-dependency.md` | Como se relacionan las unidades entre si, secuencia de construccion, interfaces entre ellas |

**Punto importante sobre historias cross-unit**: No necesariamente una historia se desarrolla en una sola unidad. Historias de integracion pueden tener partes en varias unidades. El mapeo muestra estas relaciones.

### 9.5 El framework identifica la paralelizacion automaticamente

Una de las capacidades mas valiosas del framework: **identifica automaticamente cuales unidades se pueden construir en paralelo y cuales tienen dependencias**. No hay que indicarle nada. El analiza los componentes, servicios, dependencias e interfaces y determina la secuencia optima.

> **Pregunta frecuente**: "No hay forma de usar varios modelos para no agotar tokens?"
>
> La documentacion del framework especifica que debes instalarlo para una herramienta especifica. Cada herramienta (Claude Code, Cursor, Kiro) configura los archivos de forma diferente. No se recomienda mezclar. La solucion es hacer un uso eficiente de tokens y aprovechar que Construction consume menos que Inception.

---

## Paso 10: CONSTRUCTION - Per-Unit Loop

### 10.1 Objetivo de la fase Construction

**Transformar las especificaciones en codigo funcional y probado, a traves de etapas disciplinadas.**

Lo importante no es solo el codigo al final — es **el proceso** para llegar a ese codigo. La disciplina del proceso es lo que garantiza la calidad.

### 10.2 Que cambia respecto a Inception

| Aspecto | Inception | Construction |
|---------|-----------|-------------|
| **Alcance** | Todo el producto completo | Una unidad a la vez |
| **Enfoque** | QUE construir | COMO construirlo |
| **Artefactos** | Documentacion de diseno | Codigo funcional + tests |
| **Tokens** | Consume mucho (gran volumen de analisis) | Consume menos (enfocado por unidad) |
| **Velocidad** | Horas para todo el diseno | Horas por unidad |

### 10.3 El loop por unidad

Cada unidad pasa por estas etapas en secuencia:

```
Por cada Unit:
  1. Functional Design (modelo de dominio, logica de negocio, reglas)
  2. NFR Requirements (performance, seguridad, escalabilidad)
  3. NFR Design (patrones tecnicos para cumplir los NFRs)
  4. Infrastructure Design (Docker, networking, storage)
  5. Code Generation (implementacion del codigo)
  6. Build and Test (tests unitarios, integracion, aceptacion)
```

> **Sobre los datos y la implementacion**: Si durante Inception definiste que tu sistema consume datos de ciertas fuentes, es en Functional Design (etapa 1 de Construction) donde se detalla **como** van a fluir esos datos, que esquemas tienen, como se transforman, y donde se almacenan. La fase de Inception define el **que** (necesito estos datos); Construction define el **como** (asi fluyen, asi se procesan, asi se persisten).

### 10.4 Continuidad con la informacion de Inception

Toda la informacion generada en Inception alimenta directamente la Construction:
- Los **requerimientos** definen que debe cumplir cada unidad
- Las **historias de usuario** con sus escenarios Gherkin se convierten en tests de aceptacion
- Los **componentes y servicios** del Application Design se refinan en Functional Design
- Las **decisiones arquitectonicas (ADR)** guian el diseno tecnico
- Las **dependencias** entre unidades determinan interfaces y contratos

> **No se pierde nada**: Todo lo que se construyo en Inception es insumo directo para Construction. No hay que repetir decisiones ni redescubrir contexto.

---
