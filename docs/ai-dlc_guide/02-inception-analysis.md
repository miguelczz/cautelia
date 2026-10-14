## Paso 3: INCEPTION - Requirements Analysis (Analisis de Requerimientos)

Esta es la primera actividad real del framework despues del Workspace Detection. Claude asume el rol de **Product Owner** y analiza tu PRD para entender que construir.

### 3.1 Que hace Claude en este paso

1. **Intent Analysis** - Clasifica tu solicitud:
   - Claridad: Clara / Vaga / Incompleta
   - Tipo: Nuevo Proyecto / Bug Fix / Refactoring / etc.
   - Alcance: Archivo unico / Componente / Multi-componente / Sistema completo
   - Complejidad: Trivial / Simple / Moderada / Compleja

2. **Determina la profundidad** del analisis:
   - **Minimal**: Solicitud simple y clara
   - **Standard**: Complejidad normal, necesita clarificaciones
   - **Comprehensive**: Proyecto complejo, alto riesgo (nuestro caso)

3. **Genera preguntas de verificacion** - Crea un archivo con preguntas sobre aspectos que el PRD no deja 100% claros para la implementacion

### 3.2 El archivo de preguntas

Claude crea el archivo en: `aidlc-docs/inception/requirements/requirement-verification-questions.md`

En nuestro caso genero **10 preguntas** cubriendo:
- Codigo existente de versiones previas (V5.0)
- Alcance del build (MVP completo vs. por partes)
- Confirmacion del tech stack
- Target de deployment
- Estado de los modelos de ML entrenados
- Generacion de imagenes anotadas (Caja de Cristal)
- Datos clinicos de referencia (thresholds)
- Composicion del equipo
- Inclusion del agente RAG
- Generacion de reportes PDF

### 3.3 Como responder

Abres el archivo de preguntas y para cada pregunta colocas la letra de tu respuesta:

```markdown
## Question 1
The PRD mentions DDH Agent V5.0...

A) Yes, there is an existing codebase...
B) Yes, there are trained models...
C) No, this is a completely new build...
D) Other (please describe)

[Answer]: B    <-- Aqui pones tu respuesta
```

Cuando terminas todas, le dices a Claude: "Ya respondi" y el continua.

> **Si ninguna opcion aplica**, elige la ultima opcion (Other) y describe tu caso despues del `[Answer]:`.

---

## Paso 4: INCEPTION - User Stories (Historias de Usuario)

Despues de aprobar los requerimientos, el framework genera dos artefactos clave: **Personas** y **Historias de Usuario**. Este paso es **opcional** — el framework evalua si agrega valor. En nuestro caso lo incluimos porque:
- Tenemos multiples tipos de usuario (medico, admin MLOps, super admin)
- Sistema complejo con muchos flujos diferentes
- Necesitamos criterios de aceptacion claros para testing

> **Velocidad**: Lo que tradicionalmente toma dias de trabajo con un equipo de producto, aqui se genera en minutos u horas. La agilidad que se gana en este proceso es impresionante.

### 4.1 Que hace Claude en este paso

1. **Assessment** - Evalua si las User Stories son necesarias (en nuestro caso: Si, alta prioridad)
2. **Story Generation Plan** - Crea un plan con preguntas sobre como organizar las stories
3. **Espera respuestas** - Tu respondes las preguntas de planificacion
4. **Genera las stories** - Crea dos archivos:
   - `personas.md` - Arquetipos de usuario (quien usa el sistema)
   - `stories.md` - Historias de usuario con criterios de aceptacion

### 4.2 Artefacto 1: Personas (`personas.md`)

**Que es una Persona**: Es una personificacion real de un tipo de usuario de tu producto. No hablamos de "usuarios" genericos — hablamos de personas con nombre, contexto, necesidades y puntos de dolor especificos. Es el concepto de **User Persona** que se usa en UX/UI.

Cada persona tiene:
- **Nombre real** (ej: "Dr. Carlos Mendez", no "Usuario tipo A")
- **Rol y contexto** (que hace, donde trabaja, como es su dia a dia)
- **Puntos de dolor** (que le frustra del proceso actual)
- **Motivaciones** (que lo llevaria a usar tu producto)
- **Nivel tecnico** (que tan comodo esta con la tecnologia)
- **Necesidades claras** dentro del producto
- **RFs aplicables** (que requerimientos funcionales le tocan)

> **Conexion con UX/UI**: Las personas que genera el framework son exactamente las mismas que un disenador UX/UI usaria para mapear el flujo de una persona a traves del producto. Si necesitas que un disenador UX haga el user flow, este artefacto es su punto de partida — ya tiene la personificacion completa.

**Que contiene una persona en detalle**: Cada persona incluye como utilizaria el producto, cuales son sus metricas de exito (ej: NPS, duracion del proceso, criterios de aceptacion personales), y sus puntos de dolor reales. Por ejemplo, si una persona es un candidato a una vacante, sus puntos de dolor pueden ser: procesos de aplicacion complejos, interacciones roboticas sin personalidad, tiempos de espera excesivos. Esos puntos de dolor son reales y validables.

En nuestro caso se generaron **5 personas**:

| Persona | Rol | Ejemplo de necesidad |
|---------|-----|---------------------|
| Dr. Carlos Mendez | Ortopedista pediatrico | Subir DICOM → recibir mediciones → descargar PDF |
| Ing. Felipe Rangel | Admin MLOps | Gestionar modelos, evaluar precision, promover a produccion |
| Dra. Ana Lucia Torres | Clinical Analyst | Ingresar ground truth, comparar modelo vs medico |
| Santiago Diaz | CV Engineer | Entrenar modelos, debuggear pipeline, iterar medidas |
| Laura Gomez | Super Admin | Aprovisionar tenants, auditar privacidad, monitorear |

### 4.3 Artefacto 2: Historias de Usuario (`stories.md`)

Despues de las personas, el framework genera las historias de usuario organizadas **por persona**. Cada story sigue el formato:

```
Como [persona], quiero [accion], para [beneficio]
```

Y cumple los criterios **INVEST**:
- **I**ndependent - Se puede implementar sola
- **N**egotiable - Se puede ajustar
- **V**aluable - Tiene valor para el usuario
- **E**stimable - Se puede estimar esfuerzo
- **S**mall - Es suficientemente pequena
- **T**estable - Se puede verificar con acceptance criteria

**Formato de Acceptance Criteria**: Usamos BDD (Behavior Driven Development) con sintaxis Gherkin:
```gherkin
Scenario: Upload exitoso de DICOM valido
  Given que estoy autenticado en la plataforma
  When arrastro un archivo DICOM al area de upload
  Then el sistema muestra una miniatura de la imagen
  And extrae automaticamente edad y sexo
```

> **Las stories son vivas**: No se generan una vez y se olvidan. En nuestro caso, despues de hacer la ingenieria inversa del codebase existente (Paso 3b), volvimos a las stories y encontramos 8 gaps que agregamos. Tambien revisamos las screenshots del frontend real y actualizamos 6 stories con detalles de UI que faltaban. El resultado final fue de 49 stories con ~185 scenarios.

### 4.4 El plan de generacion

Claude crea el plan en: `aidlc-docs/inception/plans/story-generation-plan.md`

Las preguntas de planificacion cubren:
- Como organizar las stories (por persona, por epic, por journey)
- Nivel de detalle de los acceptance criteria (exhaustivo BDD Gherkin recomendado)
- Tipos de usuario adicionales
- Prioridad de modulos
- Como manejar stories de seguridad y privacidad
- Alcance de features como RAG

### 4.5 Validacion con usuarios reales — Cuando y como pedir feedback

> **Pregunta frecuente**: "Cual es el momento indicado para empezar a recibir feedback del usuario final? Hasta que generemos todo el producto o empezamos a hacer iteraciones?"

La fase de Inception (requerimientos + stories + personas) en la practica dura **1 a 2 horas** con el framework. Por eso, la validacion no tiene que esperar al producto terminado — se puede hacer **en este momento**, con las personas y stories como instrumento.

**Como validar las personas**:
1. Tomas la persona generada (ej: "Maria, candidata") y vas con usuarios reales de ese perfil
2. Les preguntas: "Se siente identificado con esto? Estos son sus puntos de dolor?"
3. El usuario te dira: "Si" o "No, sabe que? Mire, las entrevistas deberian durar menos de 25 minutos porque es un screening inicial, no deberian ser tan demoradas"
4. Con ese feedback, vuelves al framework y **pides ajustes** en las personas o en las historias de usuario

**Como validar las stories**:
- Revisa que cada historia resuelve un punto de dolor de la persona
- Verifica que los criterios de aceptacion tienen sentido para el usuario real
- Valida las metricas de exito: NPS esperado, tiempos maximos, limites de aceptacion

> **El framework es iterativo**: Puedes pausar en cualquier momento. Si durante los requerimientos necesitas aclarar algo con una persona de negocio que no esta disponible, guardas el progreso (el `aidlc-state.md` registra donde quedaste) y retomas cuando tengas la respuesta. Cada fase tiene puntos claros donde pedir feedback externo.

**Momento adecuado para validar por fase**:

| Fase | Que validar | Con quien |
|------|------------|-----------|
| Personas generadas | Identificacion, puntos de dolor, metricas de exito | Usuarios reales de cada perfil |
| Historias de usuario | Criterios de aceptacion, flujos, prioridades | Product Owner, usuarios clave |
| Workflow Planning | Secuencia de implementacion, dependencias | Equipo tecnico |
| Application Design | Arquitectura, componentes, interfaces | Arquitecto, tech lead |
| Construction | Funcionalidad implementada, UX | Usuarios beta |

### 4.6 Calidad de las stories generadas

> **Observacion de experiencia**: A veces ni los Product Owners expertos te crean historias de usuario con este nivel de calidad. Frecuentemente omiten los criterios de aceptacion, no usan el formato adecuado, o no incluyen escenarios. El framework genera stories con formato consistente, escenarios Gherkin completos, y trazabilidad a los requerimientos.

Cada historia esta:
- **Organizada por epicas** (agrupacion de stories relacionadas)
- **Vinculada a una persona** (que persona se beneficia)
- **Trazable a los RFs** (que requerimiento funcional cubre)
- **Con estimacion implicita** basada en la complejidad de los criterios de aceptacion

**Punto de revision critico**: Antes de aprobar y continuar a la siguiente fase, revisa:
1. Cada persona: tiene los comportamientos correctos? Le falta un punto de dolor?
2. Cada historia: resuelve un punto de dolor de la persona correcta?
3. Los criterios de aceptacion: son verificables y realistas?
4. La cobertura: todos los RFs estan cubiertos por al menos una story?

Si todo esta correcto, apruebas y el framework continua a Workflow Planning.

### 4.7 Integracion con herramientas de gestion

> **Pregunta frecuente**: "He intentado subir esto a Jira para hacer seguimiento, funciona?"
>
> Las stories generadas por el framework se pueden integrar con herramientas de gestion de proyectos. En nuestro caso, la integracion se hace con **Linear** (en las estaciones 6 y 7 del programa), donde se lleva el control de epicas, stories y tareas. Tambien seria posible conectar con Jira u otras herramientas via MCP (Model Context Protocol) servers.

---

## Paso 5: INCEPTION - Reverse Engineering (Solo para Brownfield)

Si tu proyecto tiene **codigo existente** (Brownfield), el framework puede hacer ingenieria inversa para documentar todo el sistema antes de planificar cambios.

### 5.1 Cuando aplica

- **Greenfield** (desde cero): Se salta este paso
- **Brownfield** (codigo existente): Se ejecuta automaticamente

> **Tip practico**: Si tienes multiples repositorios, crea una carpeta superior y clona todos los repos ahi. El framework analiza todo lo que este dentro de la carpeta raiz. Si tienes documentacion en Confluence o wikis, descargala en Markdown y ponla en la carpeta — enriquece el contexto.

### 5.2 Que analiza

Claude analiza todo el codebase y genera artefactos de documentacion:

| Artefacto | Que documenta |
|-----------|--------------|
| `technology-stack.md` | Lenguajes, frameworks, versiones |
| `component-inventory.md` | Inventario completo de modulos y componentes |
| `business-overview.md` | Contexto de negocio y transacciones |
| `architecture.md` | Diagramas, topologia Docker, flujo de datos |
| `code-structure.md` | Modulos, clases, patrones de diseno |
| `api-documentation.md` | Endpoints, modelos, schema de BD |
| `dependencies.md` | Dependencias internas y externas |
| `code-quality-assessment.md` | Tests, linting, deuda tecnica |

> **Artefactos custom**: Puedes pedir artefactos adicionales segun tu caso. Nosotros agregamos `abstraction-analysis.md` (que es generico vs DDH-especifico) y `multi-tenancy-readiness.md` (que cambiar para multi-tenant).

### 5.3 Tecnicas para cajas negras

Si tu sistema interactua con servicios externos que no tienes el codigo (ej: Salesforce, APIs de terceros):
- **Si tienes codigo que consume el API**: ese codigo te da contexto de como funciona la integracion
- **Si es una caja negra total**: dale ejemplos de request/response (100 ejemplos de como envia y resuelve enriquece mucho el contexto)
- **Si tienes trazas**: logs de invocaciones, mensajes, responses — todo eso ayuda
- **API docs**: si tiene documentacion de API, usala
- **MCP de Playwright**: para hacer ingenieria inversa *dinamica* de una aplicacion web desplegada (se cubre en estaciones posteriores)

### 5.4 Resultado

Despues de la ingenieria inversa, el framework "sabe" que tienes: repositorios de frontend, backend, infraestructura, microservicios, documentaciones de API, etc. Cuando te proponga un plan de trabajo, ya sabe donde estan las clases, los servicios, y las dependencias. Te dice: "para hacer el ajuste o la nueva funcionalidad, utiliza estos repositorios, utiliza estas clases."

En nuestro caso genero **11 artefactos** (5,438 lineas) que documentaron: 8 servicios Docker, 13 agentes LangGraph, 23 servicios backend, 40 API endpoints, 63 componentes React, 15 medidas clinicas, 8 detectores de puntos anatomicos, y 6 criterios diagnosticos.

---
