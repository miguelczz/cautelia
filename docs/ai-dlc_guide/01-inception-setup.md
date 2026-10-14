## Paso 1: Descarga del framework AI-DLC e inicializacion del proyecto

### Prerequisitos

Necesitas tener dos cosas listas **antes** de empezar:

1. **El framework AI-DLC descargado** - Es solo una carpeta, no hay que instalar nada.
2. **Tu PRD** (Product Requirements Document) - El documento con los requerimientos de tu producto.

### 1.1 Descargar el framework AI-DLC v0.1.5

Repositorio oficial: https://github.com/awslabs/aidlc-workflows
Release: https://github.com/awslabs/aidlc-workflows/releases/tag/v0.1.5

```sh
curl -sL https://github.com/awslabs/aidlc-workflows/archive/refs/tags/v0.1.5.tar.gz -o /tmp/aidlc-v0.1.5.tar.gz
tar -xzf /tmp/aidlc-v0.1.5.tar.gz -C /tmp/
```

Esto descarga y extrae el framework en `/tmp/aidlc-workflows-0.1.5/`. Es solo una carpeta con archivos `.md`, no hay que instalar nada mas.

### 1.2 Crear el directorio del proyecto

```sh
mkdir -p ~/projects/mi-proyecto
cd ~/projects/mi-proyecto
```

> **IMPORTANTE**: La carpeta del proyecto ES la raiz del repo git. NO crear carpetas intermedias (ver seccion 1.6 para la explicacion). El nombre debe ser el nombre definitivo del proyecto/repo.

### 1.3 Copiar el PRD al proyecto

```sh
cp /ruta/a/tu/prd.md PRD_mi_proyecto.md
```

> Ejemplo: `cp ~/specs/prd.md PRD_expertia_platform.md`

### 1.4 Copiar el framework al proyecto

Este es el paso clave. Lo que hacemos es:

- **Renombrar** el archivo `core-workflow.md` del framework a `CLAUDE.md`. Este archivo es el que Claude Code lee como instrucciones base. No se llama CLAUDE.md porque si, se llama asi porque es el archivo que Claude Code reconoce automaticamente como sus instrucciones de trabajo.
- **Copiar las reglas detalladas** del framework a una carpeta oculta `.aidlc-rule-details/`.

```sh
cp /tmp/aidlc-workflows-0.1.5/aidlc-rules/aws-aidlc-rules/core-workflow.md ./CLAUDE.md
mkdir -p .aidlc-rule-details
cp -R /tmp/aidlc-workflows-0.1.5/aidlc-rules/aws-aidlc-rule-details/* .aidlc-rule-details/
```

### 1.5 Inicializar el repositorio git y crear el repo en GitHub

```sh
git init
gh repo create tu-usuario/nombre-proyecto --private --description "Descripcion del proyecto"
git remote add origin https://github.com/tu-usuario/nombre-proyecto.git
```

> **Recomendacion**: Crea el repo de GitHub apuntando directamente a esta carpeta. Ver seccion 1.6 para las razones.

### 1.6 Leccion aprendida: Estructura de repositorio y workspace

El framework AIDLC define esta estructura en `CLAUDE.md`:

```
<WORKSPACE-ROOT>/                   # Application code
├── [project-specific structure]    # Codigo fuente
├── aidlc-docs/                     # AIDLC documentation
│   ├── inception/                  # Inception phase artifacts
│   ├── construction/               # Construction phase artifacts
│   ├── operations/                 # Operations phase artifacts
│   ├── audit/                      # Audit trail
│   └── aidlc-state.md              # Source of truth
├── .aidlc-rule-details/            # AIDLC framework (DO NOT MODIFY)
└── scripts/harness/                # Programmatic enforcement
```

El framework no opina sobre repositorios de GitHub — solo dice que todo vive bajo `<WORKSPACE-ROOT>/`. Pero en la practica, la forma en que organizas tus repos de GitHub determina si el framework funciona o se rompe.

---

**Leccion aprendida del equipo ExpertIA (LL-037)**:

En nuestro caso, creamos el proyecto dentro de una carpeta padre: `ai-dlc/agentic_interviewer_ai/`. El repo de GitHub apuntaba a `ai-dlc/` (el padre), no al proyecto. Cuando llego el momento de pasar a produccion, intentamos separar el codigo en un repo aparte dejando `aidlc-docs/` en el repo original. Esto rompio el framework porque:

1. **3-Step Closure**: Requiere commit atomico de artefacto + `aidlc-state.md` + audit. Con specs y codigo en repos separados, es imposible hacer un solo commit.
2. **Harness y linters**: 82 referencias a `aidlc-docs/` en scripts Python y reglas `.claude/rules/` — todas rotas.
3. **Hooks de `.claude/settings.json`**: 6 hooks apuntando a paths incorrectos.
4. **Costo**: Una sesion completa de trabajo para migrar, corregir paths y verificar integridad.

**Nuestra recomendacion basada en esta experiencia**:

Que la carpeta del proyecto sea la raiz del repo de GitHub. Asi `aidlc-docs/`, el codigo, los scripts de harness y todo lo demas quedan en un solo repositorio, que es lo que el framework asume con `<WORKSPACE-ROOT>/`.

```
# Lo que funciono para nosotros:
~/projects/mi-proyecto/             # <-- raiz del repo GitHub = workspace root de AIDLC
├── .git/
├── .aidlc-rule-details/
├── aidlc-docs/                     # specs JUNTO al codigo
├── src/                            # codigo
├── tests/
├── scripts/harness/
└── CLAUDE.md
```

```
# Lo que nos causo problemas:
~/projects/padre/                   # <-- repo apuntaba aqui
├── .git/
├── mi-proyecto/                    # subcarpeta, workspace root de AIDLC aqui
│   ├── aidlc-docs/
│   ├── src/
│   └── CLAUDE.md
└── otras-cosas/                    # no relacionadas al proyecto
```

**Checklist antes de continuar al Paso 2:**

- [ ] `git remote -v` muestra el repo correcto
- [ ] `.git/`, `CLAUDE.md` y `.aidlc-rule-details/` estan en la misma carpeta
- [ ] `aidlc-docs/` se creara aqui mismo cuando el framework arranque (Paso 2)

### Resultado final

Al abrir la carpeta del proyecto solo debes ver dos archivos visibles:

```
mi-proyecto/                          # <-- raiz del repo GitHub
├── .aidlc-rule-details/              # (oculta) Reglas detalladas que el framework necesita
├── .git/                             # (oculta) Repositorio git
├── CLAUDE.md                         # El workflow del framework, renombrado para que Claude lo lea
└── PRD_mi_proyecto.md                # Tu PRD, el documento de requerimientos
```

Eso es todo. No se necesita nada mas. Con esto ya puedes abrir el proyecto en tu editor (Cursor, VS Code, etc.) y empezar a trabajar con Claude.

---

## Paso 2: Iniciar el workflow AI-DLC

Una vez tienes tu carpeta de proyecto lista (Paso 1), abres el proyecto en tu editor con Claude Code (Cursor, VS Code, etc.) y le das el prompt inicial.

### 2.1 El prompt inicial

Abres Claude Code dentro de la carpeta `agentic_interviewer_ai/` y le pegas el prompt que describe tu proyecto. Este prompt debe:

- Describir **que vas a construir** y **por que**
- Referenciar tu PRD con `@PRD_agentic_interviewer_ai.md`

Ejemplo del prompt que usamos:

```
Usando AI-DLC, construiremos ExpertIA, una plataforma de morfometria automatizada
en imagenes medicas — es decir, analisis y medicion de estructuras anatomicas en
estudios radiologicos — que transforma estos estudios en datos estructurados y
evidencia trazable para medicos generales y especialistas en America Latina.
Reemplazamos la opacidad de los diagnosticos tradicionales con una 'Caja de Cristal'
que audita, asiste y explica cada medicion, permitiendo decisiones objetivas e
inmediatas. Iniciando con el caso de uso de Displasia del Desarrollo de Cadera (DDH),
el sistema integra redes de segmentacion propias, un motor de reglas deterministico y
un agente con RAG especializado para eliminar la espera de semanas por resultados
criticos; todo con base en la vision de escalabilidad transversal para morfometria
clinica. con base en el Product Requirements Document (PRD) @PRD_agentic_interviewer_ai.md
```

### 2.2 Que pasa cuando le das el prompt

Claude lee el `CLAUDE.md` (que es el framework AI-DLC) y arranca automaticamente el workflow. Lo primero que hace es:

1. **Escanear el PRD** - Lee todo tu documento de requerimientos
2. **Actividad Cero: Workspace Detection** - Analiza el estado del workspace:
   - Informacion del proyecto por el que va a trabajar
   - Estado del workspace: si es proyecto nuevo (**Greenfield** = desde cero) o existente (**Brownfield** = codigo previo)
   - Donde estan las reglas del framework (el `CLAUDE.md` y `.aidlc-rule-details/`)
   - Preparacion del ambiente
3. **Mostrar mensaje de bienvenida** - Explica las 3 fases del ciclo y como funciona
4. **Crear la estructura de carpetas** - Crea `aidlc-docs/` con todo lo necesario

### 2.3 Las 3 fases del AI-DLC

El framework trabaja en 3 fases secuenciales:

| Fase | Proposito | Pregunta que responde |
|------|-----------|----------------------|
| **INCEPTION** | Planificacion y diseno | QUE construir y POR QUE |
| **CONSTRUCTION** | Implementacion y testing | COMO construirlo |
| **OPERATIONS** | Despliegue (placeholder futuro) | COMO desplegarlo |

### 2.4 La estructura de carpetas que crea

Cuando le das permiso, Claude crea la carpeta `aidlc-docs/` con **una subcarpeta por cada fase**. Solo 3 carpetas:

```
agentic_interviewer_ai/
├── .aidlc-rule-details/              # (oculta) Reglas del framework
├── CLAUDE.md                          # Core workflow
├── PRD_agentic_interviewer_ai.md      # Tu PRD
└── aidlc-docs/                        # TODO el proceso AI-DLC vive aqui
    ├── aidlc-state.md                 # Trackeo de progreso (en que fase vamos)
    ├── audit.md                       # Log de todo lo que pasa
    ├── inception/                     # Fase 1: Planificacion
    │   ├── requirements/              #   - Analisis de requerimientos
    │   ├── user-stories/              #   - Historias de usuario
    │   ├── application-design/        #   - Diseno de la aplicacion
    │   └── plans/                     #   - Planes del workflow
    ├── construction/                  # Fase 2: Implementacion
    │   ├── plans/
    │   └── build-and-test/
    └── operations/                    # Fase 3: Despliegue (futuro)
```

> **Importante**: Todo lo que genera el framework (documentos, planes, disenos) va dentro de `aidlc-docs/`. El codigo de la aplicacion va en la raiz del proyecto, **nunca** dentro de `aidlc-docs/`.

### 2.5 El archivo aidlc-state.md

Este archivo es el "cerebro" del tracking. Registra:
- Tipo de proyecto (Greenfield/Brownfield)
- En que fase y etapa estamos
- Que etapas se han completado y cuales faltan

Si la sesion se interrumpe, Claude lee este archivo para retomar donde quedamos.

### 2.6 Como funciona la interaccion

El framework es **interactivo y pide aprobacion** en cada etapa:

1. Claude analiza y genera artefactos (documentos, preguntas, disenos)
2. Te crea un archivo `.md` con preguntas de opcion multiple
3. Tu abres el archivo, respondes con la letra (A, B, C, D...) despues del `[Answer]:`
4. Le dices a Claude que ya respondiste
5. Claude analiza tus respuestas y avanza a la siguiente etapa
6. **No avanza sin tu aprobacion** - siempre espera tu visto bueno

> Es como tener un arquitecto de software senior que te guia paso a paso, te pregunta cuando tiene dudas, y documenta absolutamente todo.

---
