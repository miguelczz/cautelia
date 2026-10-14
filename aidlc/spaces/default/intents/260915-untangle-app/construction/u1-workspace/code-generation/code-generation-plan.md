# Plan de generación de código — U1 `workspace`

El primer commit de código del aplicativo. Veintiséis pasos en orden, cada uno
con lo que produce y la historia que realiza. La práctica del equipo exige que el
andamiaje completo entre **en el mismo commit** que el primer archivo de código:
no hay un commit intermedio con código y sin herramientas.

**Fuentes consumidas.** `../functional-design/functional-spec.md` (los tres
flujos y los estados de una corrida), `../functional-design/rules.md` (BR1.1 a
BR3.6), `../functional-design/entities.md` (las seis entidades),
`../nfr-requirements/tech-stack-decisions.md` (lo que U1 instala y NFR18),
`../nfr-design/` (los seis documentos de diseño no funcional),
`../infrastructure-design/` (servicios locales, monitoreo y tubería),
`../../../inception/contract-design/contract-summary.md` (C-21, C-22, C-24,
C-27, C-28), `../../../inception/units-generation/unit-of-work.md` (qué contiene
U1 y dónde vive en el código) y
`../../../inception/requirements-analysis/requirements.md` (FR11.1, FR11.3,
NFR17, NFR18, NFR21).

El contrato de pruebas que gobierna el orden de este plan está al final del
documento, pegado sin cambios como lo emite la herramienta.

## Dos decisiones de este plan

Las dos resuelven una contradicción entre documentos aprobados aplicando una
regla afirmada, así que se registran aquí en lugar de preguntarse; pero cambian
lo que se construye, así que se dicen antes de la aprobación y no después.

### CG-1 — U1 no crea ninguna tabla de base de datos

`unit-of-work.md` asigna a U1 las entidades `CopyEntry`, `GoldenCase`, `EvalRun`
y `CaseResult`. Este plan las construye como **modelos tipados y archivos**, no
como tablas.

La razón es una regla afirmada del proyecto: *toda tabla del aplicativo lleva
aislamiento a nivel de fila con su política, y cada tabla nueva llega con su test
de aislamiento*. El punto único de sesión y la aserción de esquema que hacen
cumplir esa regla son de **U2**, que todavía no existe. Crear tablas en U1
significaría o romper la regla, o improvisar en U1 una pieza que ya tiene dueño.

Qué se construye en su lugar, que es además lo que el diseño ya pedía:

- El reporte de la corrida y el resultado por caso se escriben como **archivos**
  con su commit y su fecha, que es lo que la tubería publica como artefacto.
- El registro en base de datos era ya **un oyente opcional** en el diseño de
  observabilidad; llega cuando exista el punto único de sesión.

**Consecuencia buena y no buscada:** el camino de los 15 minutos deja de
necesitar la base de datos. Pasa de cinco pasos a tres —instalar herramientas,
instalar dependencias, correr el subconjunto— y el presupuesto de 14 minutos se
queda en unos 8. `docker-compose.yml` se crea igual, porque las unidades
siguientes lo necesitan, pero **no arranca** en el camino del arranque.

### CG-2 — El subconjunto de arranque nace con casos propios, no vacío

El diseño de rendimiento dejó `smoke` como lista vacía que cada unidad rellena.
Una lista vacía produce un reporte de cero casos, y el primer Bolt no podría
demostrar su propio criterio de terminado ("clonar y llegar al reporte").

Este plan la llena con los casos que **U1 sí puede producir**: los chequeos
deterministas que no llaman a ningún modelo —esquema de un caso de ejemplo,
paridad del catálogo, claves sin consumidor, formas prohibidas, texto de cláusula
ajena—. Son casos reales del sistema, con identificador estable, no casos de
adorno. Los de conversación se añaden cuando exista el conductor de texto (B14).

## Orden de pruebas

U1 está en la **rama evaluada** porque realiza M8, pero es la primera unidad y no
existe todavía ningún caso de DS-2, DS-3 ni DS-6 que correr. La regla del
proyecto lo resuelve explícitamente: *la primera unidad de la rama evaluada que
realiza M8 sin conducta propia se construye con la rama determinista, y su caso
previo es la primera corrida de los casos que escriban las unidades siguientes*.

Así que este plan sigue la **rama determinista** del contrato, capa por capa:
modelo de datos → acceso a datos → lógica de negocio → API → interfaz. Se
implementa la capa y a continuación se escriben y corren sus pruebas, antes de
pasar a la siguiente. El runner, la cobertura y el corredor quedan ejecutables
**antes** de la primera prueba, porque no existe ninguno que verificar.

## Pasos

### Bloque A — Andamiaje y herramientas (pasos 1 a 5)

Nada de esto tiene pruebas propias: es lo que hace posible que existan pruebas.
El paso 5 es el de "runner listo" que el contrato exige antes de la primera.

- [x] **Paso 1 — Toolchain y archivo de tareas.** `mise.toml` en la raíz con
      Python 3.13, uv, Node 24 LTS y pnpm 12 anclados por versión exacta, y el
      archivo de tareas con el nombre de cada acción del proyecto: `bootstrap`,
      `deps:install`, `fmt`, `lint`, `types`, `test`, `cov`, `evals:run`,
      `contracts:gen`, `services:up`, `verify`. *(BR1.1; convención 10)*
- [x] **Paso 2 — Proyecto Python.** `app/backend/pyproject.toml` con uv,
      `uv.lock` con hashes, Ruff como formatter y linter con las reglas `S` de
      seguridad, mypy estricto con el plugin de Pydantic, pytest con
      `pytest-cov`, y el alcance de las cuatro herramientas declarado al prefijo
      `app/backend/`. *(TD-09; `team.md` Code Style)*
- [x] **Paso 3 — Proyecto TypeScript.** `app/frontend/package.json` con pnpm 12,
      `pnpm-lock.yaml`, TypeScript estricto, ESLint 10 con configuración plana
      más `typescript-eslint`, `eslint-plugin-security` y reglas de
      accesibilidad, Prettier, y Vitest con cobertura. Alcance declarado a
      `app/frontend/`. *(ADR-002)*
- [x] **Paso 4 — Árbol de módulos y contratos de importación.** Los directorios
      de módulo bajo `app/backend/src/untangle/` con sus `__init__.py` vacíos, y
      la configuración de `import-linter` con los contratos de ADR-001: capas,
      `forbidden` sobre los SDK de proveedor, `forbidden` sobre `untangle.evals`
      desde el código de producción, `protected` sobre la raíz de composición,
      `independence` entre nodos. *(ADR-001; convenciones 1, 2, 5)*
- [x] **Paso 5 — Runner listo, y su comando exacto.** Correr por primera vez los
      dos runners sobre un caso trivial, comprobar que pasan, y escribir el
      comando exacto de cada uno en `unit-test-instructions.md` y en el archivo
      de tareas. **Ninguna prueba de los pasos siguientes se escribe antes de que
      este paso esté verde.** *(contrato: `runner_ready_before_first_test`)*

### Bloque B — Modelo de datos (pasos 6 y 7)

Primera capa de la rama determinista.

- [x] **Paso 6 — Modelos tipados de las seis entidades.** `CopyEntry`,
      `GoldenCase`, `ScriptAnswer`, `SubsetDefinition`, `EvalRun` y `CaseResult`
      como modelos congelados de Pydantic, con los enums cerrados de
      `entities.md`, incluida la causa `provider_key_missing`. Sin tablas: ver
      CG-1. *(entities.md)*
- [x] **Paso 7 — Pruebas del modelo.** Que un `CaseResult` con estado
      `not_measured` sin causa sea inválido; que uno `failed` sin criterio fallido
      sea inválido; que dos `ScriptAnswer` del mismo campo no compartan secuencia;
      que una `EvalRun` con un caso no medido no pueda declararse comparable.
      *(entities.md, `entity_constraints`)*

### Bloque C — Acceso a datos (pasos 8 y 9)

Segunda capa: para U1 el "almacén" son archivos versionados, no una base.

- [x] **Paso 8 — Carga desde archivos.** Lector del catálogo por idioma desde
      `app/config/copy/`, lector de casos desde `app/evals/cases/`, lector de
      subconjuntos desde `app/evals/subsets/`, y los esquemas JSON generados
      desde los modelos hacia `app/contracts/schemas/`. Listado **ordenado
      explícitamente**: el orden del sistema de archivos no es una garantía.
      *(C-21, C-27, C-28; REL-U1.1)*
- [x] **Paso 9 — Pruebas de la carga.** Que un identificador del subconjunto que
      no existe como archivo detenga la carga nombrándolo; que el orden de los
      casos sea idéntico en dos cargas del mismo commit; que un caso que no valida
      su esquema falle nombrando el archivo y la clave. *(BR1.6, BR1.7, REL-U1.1)*

### Bloque D — Lógica de negocio (pasos 10 a 15)

Tercera capa, y el grueso de la unidad.

- [x] **Paso 10 — Catálogo de textos.** `copy_catalog/api.py` con `t(key,
      locale, **vars)` y `keys_for(surface)`, carga única al arrancar como
      estructura inmutable, y devolución de la clave misma con registro del evento
      cuando falta una entrada, nunca una cadena vacía. *(C-21, US5.8)*
- [x] **Paso 11 — Pruebas del catálogo.** Seis: resolución en los dos idiomas,
      sustitución de variables, clave ausente devuelve la clave y registra, carga
      fallida nombra el archivo, e inmutabilidad de la estructura cargada.
      *(AC5.8.1; estrategia Standard)*
- [x] **Paso 12 — Los seis chequeos del catálogo.** Paridad español-inglés,
      consumidor literal en el código, ninguna cadena visible en línea, claves
      jerárquicas y literales, versión mayor que uno con su decisión declarada, y
      ninguna forma de la lista versionada de formas prohibidas. Cada uno termina
      con código distinto de cero nombrando la clave o el archivo. *(BR3.1 a
      BR3.6; Flujo 3)*
- [x] **Paso 13 — Pruebas de los chequeos.** Una por chequeo, cada una con un
      catálogo de prueba que lo rompe a propósito y comprueba que el mensaje
      nombra la clave culpable. Más una que comprueba que un catálogo sano pasa
      los seis. *(AC5.8.1 a AC5.8.4)*
- [x] **Paso 14 — Asegurado simulado por reglas.** Responde el campo que el turno
      declara, en cualquier orden; entrega una corrección una sola vez; ante un
      campo que el guion no tiene responde con la frase de desconocimiento del
      catálogo y suma un desvío. **Sin ninguna fuente de azar y sin llamar a
      ningún modelo.** *(BR2.1 a BR2.4, BR1.11; US4.7)*
- [x] **Paso 15 — Pruebas del asegurado simulado.** Seis: orden alterado de
      campos, corrección entregada una vez y confirmada la segunda, campo fuera
      del guion con su desvío, determinismo sobre la misma secuencia, y la prueba
      de que ninguna llamada a un cliente de modelo aparece en su cadena.
      *(AC4.7.1 a AC4.7.5)*

### Bloque E — Corredor y su API de comando (pasos 16 a 19)

Cuarta capa: la superficie que se invoca.

- [x] **Paso 16 — Corredor de evaluaciones.** Los ocho pasos del Flujo 1:
      validar entorno según lo que el conjunto seleccionado necesita, cargar y
      validar el manifiesto de conjuntos, resolver los casos, abrir la corrida,
      ejecutar cada caso por su conductor, cerrar con su duración, generar el
      reporte por caso, criterio e idioma, y devolver el código de salida. Con la
      política de fallo de tres capas: taxonomía traducida, un reintento para lo
      pasajero y cero para la cuota, y corte a los tres fallos seguidos.
      *(Flujo 1; BR1.2 a BR1.9; US4.4)*
- [x] **Paso 17 — Registro de objetivos y conductores.** `evals/runner/api.py`
      con `register_targets`, el `Protocol` de `EvalDriver` y `register_driver`,
      más un conductor de prueba que no llama a ningún proveedor. *(C-22; UG-4)*
- [x] **Paso 18 — Pruebas del corredor.** Ocho: sin la variable que el conjunto
      necesita corta antes de la primera llamada nombrándola; sin la variable que
      no necesita corre normal; un caso que la necesita queda no medido con
      `provider_key_missing`; sin backend de trazas el reporte sale con los
      enlaces marcados; un error de proveedor inyectado deja el caso no medido y
      la corrida sigue; tres cuotas agotadas seguidas abren el corte; dos corridas
      del mismo commit ejecutan los mismos casos en el mismo orden; y el reporte
      muestra los dos idiomas en columnas separadas sin campo donde promediar.
      *(AC4.4.1 a AC4.4.6; REL-U1.1 a REL-U1.5)*
- [x] **Paso 19 — Raíz de composición y salud.** `server/composition.py` con la
      fábrica de la aplicación, el objeto de configuración que valida el entorno
      y el endpoint de salud, más su prueba de que un módulo declarado sin su
      función falla al arrancar nombrándolo. *(C-24)*

### Bloque F — Interfaz, verificación y entorno (pasos 20 a 24)

Quinta capa y el envoltorio.

- [x] **Paso 20 — Módulo tipado de claves y su prueba.** Generado desde el mismo
      catálogo hacia `app/frontend/src/shared/copy/`, con su prueba de Vitest de
      que una clave inexistente es un error de tipos. *(frontend-components.md,
      C-28)*
- [x] **Paso 21 — Chequeos de contenido.** Frases prohibidas, ausencia de texto
      de cláusula de ISO o ACORD distinguiendo estructura de texto, y la lista de
      exclusiones versionada con la razón de cada entrada. Más sus pruebas.
      *(`team.md`, Chequeos de contenido)*
- [x] **Paso 22 — Cobertura agregada.** El comando que corre las dos
      herramientas, combina sus reportes sumando líneas cubiertas sobre líneas
      totales, compara contra el 80 % y devuelve distinto de cero si no se
      alcanza; con la lista de exclusión versionada. *(NFR18.1, NFR18.3)*
- [x] **Paso 23 — Guion único de verificación.** `scripts/verify.sh` con los
      nueve pasos en el orden de `team.md`, las banderas `--only secrets` y
      `--skip secrets`, corte inmediato solo en el escaneo y continuación en los
      otros ocho con una sola lista al final. *(decisión Q1 del diseño no
      funcional)*
- [x] **Paso 24 — Entorno, secretos y tubería.** `.env.example` con nombres
      agrupados por uso; comprobación de que el `.gitignore` ya lo exceptúa;
      `docker-compose.yml` con la base de datos y el perfil `traces`, ambos
      anclados por huella con su etiqueta legible al lado y el comando que
      resuelve la huella; los dos flujos de GitHub Actions (verificación de dos
      trabajos y medición semanal en entorno limpio). *(SEC-U1.1 a SEC-U1.5;
      infraestructura)*

### Bloque G — Cierre (pasos 25 y 26)

- [x] **Paso 25 — Subconjunto de arranque y su corrida.** `app/evals/subsets/smoke.yaml`
      con los casos deterministas de CG-2, y la corrida completa del camino:
      clonar limpio, instalar, correr, ver el reporte. Se cronometra y se anota el
      tiempo real por paso. *(NFR21.1; CG-2)*
- [x] **Paso 26 — Trazabilidad y manifiesto.** `traceability.json` con los
      quince criterios de aceptación y los identificadores no funcionales, cada
      uno apuntando a un archivo que existe; y `source-manifest.json` con cada
      ruta creada. *(contrato de la etapa)*

## Trazabilidad de historia a paso

| Historia | Qué pide | Pasos |
| --- | --- | --- |
| US4.4 — correr las evaluaciones con un comando | Comando único, reporte, códigos de salida, degradación honesta | 1, 8, 9, 16, 17, 18, 23, 25 |
| US4.7 — responder como asegurado simulado | Respuesta por campo, corrección una vez, desvío, determinismo | 6, 7, 14, 15 |
| US5.8 — catálogo de textos con sus chequeos | Resolución por idioma, paridad, consumidores, formas prohibidas | 10, 11, 12, 13, 20 |
| Andamiaje (criterio de terminado del Bolt, no historia) | Herramientas, contratos de importación, guion, tubería, servicios | 2, 3, 4, 5, 19, 21, 22, 24, 26 |

## Recuento de pruebas

| Componente | Pruebas | Tipo |
| --- | --- | --- |
| Modelos de las seis entidades | 5 | Unitarias |
| Carga desde archivos | 4 | Unitarias más una de integración con el árbol real |
| Catálogo de textos | 6 | Unitarias |
| Chequeos del catálogo | 7 | Unitarias, una por chequeo más el caso sano |
| Asegurado simulado | 6 | Unitarias |
| Corredor de evaluaciones | 8 | Unitarias más integración con el conductor de prueba |
| Raíz de composición | 3 | Integración |
| Chequeos de contenido | 3 | Unitarias |
| Módulo tipado de claves | 2 | Unitarias de TypeScript |
| **Total** | **44** | 36 de Python, 2 de TypeScript, 6 de integración |

Cinco a ocho por componente, como pide la estrategia `Standard`, más las de
integración en las fronteras que la misma estrategia exige.

## Lo que este plan no construye

| Pieza | De quién es |
| --- | --- |
| Tablas, migraciones y punto único de sesión | U2 |
| Reporte con regresión, juez calibrado, segundo detector | U21 |
| Base visual de la interfaz y el proceso servido | U6 |
| Casos de conversación de DS-2, DS-3 y DS-6 | Las unidades que miden cada conducta |
| Conductores de canal | U13 (texto) y U16 (audio) |

## Plan Approval

Ver `code-generation-questions.md`.

## Testing Contract

```json
{
  "version": 1,
  "methodology": "custom",
  "source": "team",
  "ordering": "Clasifica cada unidad en una de dos ramas y no dejes ninguna sin rama. Rama evaluada: toda unidad cuyo comportamiento observable aparece en la tabla de criterios de PRD 11.2 o que realiza uno de M1, M4, M5, M6, M8, M9, M13 o M15; para ella se escribe o se extiende primero su caso de golden set (DS-2, DS-3, DS-5, DS-6) con su identificador estable, su criterio de aceptación y su veredicto esperado, se corre y se comprueba que falla, se implementa, y se vuelve a correr hasta que pase. Rama determinista: toda unidad restante sin excepción, recorrida capa por capa en el orden Data model / database behavior, Repository / data access, Business logic, API / endpoint, Frontend behavior; se implementa la capa y a continuación se escriben y corren las pruebas de esa capa antes de pasar a la siguiente. Una unidad de la rama evaluada usa además la rama determinista para las capas que la sostienen. El runner de pruebas, la configuración de cobertura y el corredor de evals se dejan instalados y ejecutables antes del primer caso de cualquiera de las dos ramas, porque no existe ninguno que verificar.",
  "scope": "classic",
  "test_strategy": "standard",
  "project_type": "brownfield",
  "applicable_notes": [
    {
      "layer": "org",
      "text": "We treat tests as a first-class deliverable in every Bolt. The specific\nmethodology (TDD, BDD, ATDD, or classic test-after) is affirmed at\npractices-discovery and recorded in `team.md` under this heading with explicit\n`Methodology` and `Ordering` fields; Code Generation resolves those fields\nindependently from coverage, tooling, and scope notes.\n\nWhen no posture has been affirmed, our default per scope is:\n- **Methodology**: test-after\n- **Ordering**: implement each applicable testable layer, then write and run\n  that layer's tests.\n- `mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage\n  floor and CI execution before merge.\n- `bugfix`, `security-patch` add a targeted regression for the specific\n  bug/vulnerability and require the existing suite to remain green.\n- `express` uses the Minimal strategy: requirement-driven unit tests (one per\n  requirement, with a happy-path floor per component); existing tests remain\n  green.\n- `poc`, `refactor`, `workshop` add no extra new-test floor and require the\n  existing suite to remain green.\n\nThe active `Test Strategy` still applies in every scope and determines test\nvolume/types. Scope floors are additive; they never reduce or replace the\nselected strategy.\n\nBuild and Test verifies defined coverage floors and affirmed quality targets;\nthey may not be weakened to make a step pass.\n\nAffirm a stricter posture in `team.md` if the team commits to one."
    },
    {
      "layer": "team",
      "text": "- **Methodology**: custom\n- **Ordering**: Clasifica cada unidad en una de dos ramas y no dejes ninguna sin rama. Rama evaluada: toda unidad cuyo comportamiento observable aparece en la tabla de criterios de PRD 11.2 o que realiza uno de M1, M4, M5, M6, M8, M9, M13 o M15; para ella se escribe o se extiende primero su caso de golden set (DS-2, DS-3, DS-5, DS-6) con su identificador estable, su criterio de aceptación y su veredicto esperado, se corre y se comprueba que falla, se implementa, y se vuelve a correr hasta que pase. Rama determinista: toda unidad restante sin excepción, recorrida capa por capa en el orden Data model / database behavior, Repository / data access, Business logic, API / endpoint, Frontend behavior; se implementa la capa y a continuación se escriben y corren las pruebas de esa capa antes de pasar a la siguiente. Una unidad de la rama evaluada usa además la rama determinista para las capas que la sostienen. El runner de pruebas, la configuración de cobertura y el corredor de evals se dejan instalados y ejecutables antes del primer caso de cualquiera de las dos ramas, porque no existe ninguno que verificar.\n\nLa metodología es `custom` porque la cadencia es mixta a propósito, y decir\n`tdd` o `test-after` a secas sería falso. Lo que el PRD evalúa (extracción,\ncitación, adherencia a la guía de voz, conducta adversarial) se define **antes**\nde implementarlo, porque está prohibido publicar una métrica sin su golden set\n(P5) y porque un ataque de red-team exitoso se convierte en caso de DS-6 que\ndebe pasar. El código determinista que sostiene esos comportamientos se prueba\npor capa, con la prueba escrita junto a la capa y no semanas después.\n\n**Punto de partida.** No existe ningún runner de pruebas, ninguna configuración\nde cobertura y ningún corredor de evals: la línea base es cero. El flujo declara\n`Project Type: Brownfield` porque la landing existe, pero **el aplicativo es\ngreenfield y su andamiaje se crea, no se verifica**. El primer Bolt que toque\ncódigo de aplicación deja instalados y ejecutables, antes de su primera prueba,\nel runner del lenguaje, la configuración de cobertura y el corredor de evals de\nun solo comando (M17), y registra ese comando exacto en el README.\n\n**Piso de cobertura.** 80 % de líneas **agregado** sobre el código del\naplicativo, con piso del 80 % también en los módulos críticos: motor de reglas,\nverificador de citas, aislamiento por tenant y esquema del caso. La interfaz y\nlos adaptadores de proveedor pueden quedar por debajo mientras el agregado se\ncumpla. La medición se hace con la herramienta de cobertura del lenguaje\nelegido, con un umbral configurado en el manifiesto que **haga fallar el\ncomando** cuando no se alcanza, y ese comando es el mismo que corren\n`build-and-test` y el flujo de GitHub Actions. Se excluyen del cálculo, mediante\nuna **lista de exclusión versionada** en la configuración: la landing (`site/`,\nfuera del alcance por D-005 y D-013), el corpus y los datasets generados, y las\nmigraciones. El piso es obligación propia del equipo, con su comando y su lista;\nno se apoya en que el scope lo active, y no se baja para que un paso pase.\n\n**Datos de prueba.** Los casos de los golden sets viven versionados en el\nrepositorio como archivos de datos, **un archivo por caso**, con identificador\nestable (`DS-2/es/017`), nunca generados en tiempo de corrida. El generador\nsintético (MOD-12) es determinista y sembrado: su salida (corpus DS-1, fixtures\nDS-8) se regenera solo con un comando explícito y el resultado se commitea, de\nmodo que dos corridas del mismo commit vean el mismo corpus. Los identificadores\nson la moneda de todo el sistema: el reporte por caso, el diff contra la línea\nbase, la sección \"Cómo falla\" del README y los casos nacidos de un red-team o\ndel muestreo del chat en vivo los usan sin traducción.\n\n**Forma de las pruebas.** Cada prueba es independiente del orden de ejecución y\nde estado compartido, y se puede correr sola. Cada prueba afirma un\ncomportamiento, no una implementación: se prueba lo que el requisito exige, no\ncómo se codificó. Ninguna prueba pasa con independencia de la implementación.\nCada caso de red-team exitoso entra a DS-6 con el identificador `RT-<n>` en su\nnombre, y el hallazgo no se cierra hasta que ese caso pase (PRD 11.4).\n\n**Pruebas deterministas no negociables**, cada una atada a un Must:\n\n- Motor de reglas por tenant: reglas versionadas, cada una con su test unitario (M5).\n- Verificador exacto de citas: existencia, pertenencia al tenant y a la póliza, vigencia (M4, P2).\n- Aislamiento entre tenants: RLS en la base de datos **y** punto único de adquisición de sesión que fija el `tenant_id` antes de devolverla, con fixtures que provocan colisiones detectables y una aserción sobre el esquema que falla si alguna tabla del aplicativo carece de RLS o de política (M9, F9.1, F9.4, DS-8).\n- Redacción de PII en cada punto de salida, con un segundo detector de **mecanismo distinto** al primero y reconocedores propios para placa, cédula, teléfono y número de póliza en los dos idiomas; se mide por idioma y por tipo de entidad, nunca como promedio (M6, RT-14, RT-15, P12).\n- Esquema del caso: JSON válido, y solo se citan identificadores recuperados (M1).\n- Chequeos de contenido con identificador estable (frases prohibidas, ausencia de texto de cláusula de ISO o ACORD, paridad de claves EN↔ES), para que aparezcan en el reporte por caso y en el diff contra la línea base como cualquier otra prueba.\n\n**Golden sets en cada corrida del flujo**: DS-2 (60 conversaciones de texto, 30\npor idioma), DS-3 (40 preguntas de citación con distractores) y DS-6\n(adversarial). Corren en el tier gratuito del LLM, con duración objetivo de 10\nminutos o menos, y producen un reporte por caso, por criterio y por idioma, con\nenlace a su traza.\n\n**Compuertas duras** (`[bloquea]` en PRD 11.2): cero citas inexistentes; cero\nturnos que afirmen cobertura, montos o culpa, o den consejo legal; cero\nhallazgos de seguridad (PII en trazas, fuga entre tenants, adversarial). Son\npasa o falla por caso y un solo fallo detiene la entrega. Cada criterio\n`[bloquea]` y cada umbral cuantificado del Segmento 10 se registra además como\nobjetivo medible en `nfr-requirements`, con identificador estable, valor\nesperado y el comando que produce su valor real, para que aparezca como fila\npropia en la `## Target Verification Matrix` de `build-and-test`; ningún\ncriterio `[bloquea]` se cierra con `N/A`.\n\n**Tipos de prueba obligatorios pese a la estrategia.** La estrategia activa es\n`Standard` (cinco a ocho pruebas por componente; unitarias más integración en\nlas fronteras). Además, y con independencia de la estrategia, `build-and-test`\ngenera instrucciones de prueba de **seguridad** (aislamiento entre tenants,\nredacción de PII en cada punto de salida, casos adversariales de DS-6) y de\n**rendimiento** (latencias de turno y de parada sobre DS-5, duración de la\ncorrida de evals), porque el PRD las marca como compuertas duras y como umbrales\npublicables, no como aspiraciones.\n\n**Definición de regresión.** Bloquea la entrega: (a) cualquier compuerta dura en\nrojo, sin excepción ni promedio; (b) en métricas de **denominador grande**\n—extracción por campo, fidelidad de la lectura de confirmación, latencias— una\ncaída mayor de 2 puntos porcentuales frente a la línea base versionada sin\nexplicación escrita; (c) en métricas de **nivel de caso** sobre DS-2, DS-3 y\nDS-6, donde el denominador por idioma es pequeño, **cualquier caso que pase a\nfallar** sin explicación escrita. La explicación nombra los identificadores de\nlos casos que cambiaron y su causa raíz según la taxonomía del PRD 11.3; una\nexplicación que no nombre casos no cuenta como explicación.\n\nEl umbral porcentual se reserva para el denominador grande porque en los\nconjuntos pequeños no distingue señal de ruido:\n\n| Dataset | Casos por idioma | Cuánto mueve un caso |\n| --- | --- | --- |\n| DS-2 (golden set de texto) | 30 | 3,3 pp |\n| DS-3 (citación) | 20 | 5,0 pp |\n| DS-6 (adversarial, v0) | 10 | 10,0 pp |\n\n**Determinismo de la corrida.** La corrida de evals fija todo lo que se pueda\nfijar: temperatura en 0 y semilla fija donde el proveedor lo permita, versión\ndel modelo anclada por identificador exacto (nunca un alias móvil), prompts y\nrúbricas versionados en el repositorio, y el respondedor del asegurado por\nreglas indexado por campo del PRD 11.1. Cuando un caso siga siendo inestable\nentre corridas idénticas, se marca como inestable con su identificador en un\narchivo versionado, deja de contar para la compuerta, se reporta aparte con esa\netiqueta y su estabilización se abre como trabajo; nunca se borra del set (P5).\n\n**Compuerta en rojo por causa ajena al cambio.** Cuando la compuerta se pone\nroja por una caída del proveedor, un cambio de versión del modelo o una cuota\nagotada, se registra la causa y el identificador de la corrida, la corrida se\nmarca como **no comparable** y se repite; si sigue roja, bloquea. **El umbral no\nse toca nunca** y la marca queda en el registro. Una compuerta que no se pudo\nejecutar se declara \"no medida\" en el reporte, nunca se omite.\n\n**Juez descalibrado.** Los veredictos del juez (LLM) solo cuentan mientras sus\ndos tasas contra las etiquetas humanas de DS-7, la de fallos que detecta (TNR) y\nla de aciertos que confirma (TPR), medidas por criterio y por idioma sobre la\npartición de prueba y con intervalo de confianza, estén en el umbral que fija\n`nfr-requirements` (decisión de Miguel del 2026-09-17, que reemplaza el 85 % de\nacuerdo; ADR-014). Si caen por debajo, o si cambia el modelo del juez o la\nrúbrica sin recalibrar, sus\nveredictos dejan de contar: los criterios que dependen de él se reportan como\n\"no medida\" con esa causa, no bloquean, y la recalibración se abre como trabajo\ncon fecha. Las compuertas duras juzgadas por código —citas inexistentes,\naislamiento, PII en trazas, esquema— no dependen del juez y siguen bloqueando.\n\n**Presupuesto de la corrida.** La corrida de evals de texto tiene un objetivo de\n10 minutos y su duración se mide y se publica como métrica desde la línea base\nv0 (Segmento 10.5). El corredor admite ejecutar un subconjunto declarado y\nreproducible; si la corrida completa deja de caber en el presupuesto o en los\nlímites del tier gratuito, la compuerta corre ese subconjunto declarado —nunca\nse apaga— y la corrida completa pasa a ser obligatoria por hito y antes de\npublicar cualquier línea base.\n\n**Dónde corre la compuerta.** El ejecutor autoritativo es el flujo de GitHub\nActions sobre `main`, invocando el guion único de verificación. Dentro de este\nintent, la etapa `build-and-test` ejecuta ese mismo comando. Las prácticas no\ncambian cuando cambia el ejecutor: solo cambia quién lo dispara.\n\n**Lo que no corre en cada corrida**: los golden sets de audio (DS-5, 20\ngrabaciones) corren por hito, no por cambio, porque el costo de voz está topado\ny las grabaciones dependen de terceros.\n\n**Paridad por idioma**: los mismos casos, las mismas métricas y las mismas metas\nen español e inglés; el reporte muestra los dos lados a lado y nunca un promedio\ncombinado (P12).\n\n**Herramientas**: el runner de pruebas del lenguaje elegido, más un corredor de\nevals propio con un juez propio calibrado para la compuerta (decisión de Miguel\ndel 2026-09-17, ADR-014; reemplaza \"`promptfoo` o `DeepEval`\"), `promptfoo` solo\npara red-teaming por hito y Langfuse para la anotación humana. El corredor de evals se\ninvoca con un solo comando y ese comando está en el archivo de tareas y en el\nREADME (M17)."
    },
    {
      "layer": "project",
      "text": "- Los criterios de aceptación se escriben en Gherkin con las palabras clave en español (Dado / Cuando / Entonces / Y), cada paso empieza con la palabra clave sin coma y ningún \"Dado\" depende de lo que dejó otro criterio: es el formato Given/When/Then de la regla de fase, Gherkin lo reconoce y las pruebas se automatizan sin traducirlo. (learned 2026-09-16) \n\n- Las unidades que realizan M8 sin conducta propia que evaluar (corredor de evaluaciones, reporte, respondedor simulado y compuerta) siguen en la rama evaluada, pero su caso previo es una corrida de casos ya existentes de DS-2, DS-3 o DS-6 que se comprueba que falla antes de implementarlas: no se inventa un caso de golden set artificial, y lo declaran en su campo Rama. (learned 2026-09-16) \n\n- Todo escenario de red-team (RT-1 a RT-15) necesita al menos un criterio verificable en el canal de texto, porque DS-6 corre por el adaptador de texto en cada entrega; un escenario cubierto solo en la voz queda fuera de esa compuerta y se comprueba solo por hito. (learned 2026-09-16) \n\n- Las pruebas de límites de gasto y de cuota no consumen el presupuesto que protegen: el tope en el proveedor se comprueba con una clave de prueba de tope mínimo y la aplicación detenida, y el techo de gasto con un acumulado forzado en pruebas, nunca llevando una clave real hasta su tope. (learned 2026-09-16) \n\n- La primera unidad de la rama evaluada que realiza M8 sin conducta propia (el corredor de evaluaciones) no tiene casos existentes que correr: se construye con la rama determinista y su caso previo es la primera corrida de los casos que escriban las unidades siguientes; nunca se inventa un caso de golden set para ella. Decisión de Units Generation (U1), 2026-09-17. (learned 2026-09-17)"
    }
  ],
  "obligations": {
    "strategy": "standard",
    "strategy_volume": [
      "Five to eight tests per component.",
      "Unit tests plus integration tests for key boundaries.",
      "Add E2E, performance, or security tests when requirements demand them."
    ],
    "scope_floor": [
      "Keep the existing test suite green.",
      "This scope adds no extra new-test floor beyond the selected test strategy."
    ],
    "combination_rule": "Apply every selected-strategy obligation and every scope-floor obligation; neither replaces the other, and a targeted scope regression may add the narrowest necessary test type beyond the strategy default."
  },
  "plan_profile": {
    "methodology": "custom",
    "runner_step": "Verify the existing test runner/configuration and record the exact unit-scoped command.",
    "runner_ready_before_first_test": true,
    "testable_layers": [
      "Data model / database behavior",
      "Repository / data access",
      "Business logic",
      "API / endpoint",
      "Frontend behavior"
    ],
    "steps": [
      "Project structure and production configuration skeleton.",
      "Verify the existing test runner/configuration and record the exact unit-scoped command.",
      "Custom ordering - Clasifica cada unidad en una de dos ramas y no dejes ninguna sin rama. Rama evaluada: toda unidad cuyo comportamiento observable aparece en la tabla de criterios de PRD 11.2 o que realiza uno de M1, M4, M5, M6, M8, M9, M13 o M15; para ella se escribe o se extiende primero su caso de golden set (DS-2, DS-3, DS-5, DS-6) con su identificador estable, su criterio de aceptación y su veredicto esperado, se corre y se comprueba que falla, se implementa, y se vuelve a correr hasta que pase. Rama determinista: toda unidad restante sin excepción, recorrida capa por capa en el orden Data model / database behavior, Repository / data access, Business logic, API / endpoint, Frontend behavior; se implementa la capa y a continuación se escriben y corren las pruebas de esa capa antes de pasar a la siguiente. Una unidad de la rama evaluada usa además la rama determinista para las capas que la sostienen. El runner de pruebas, la configuración de cobertura y el corredor de evals se dejan instalados y ejecutables antes del primer caso de cualquiera de las dos ramas, porque no existe ninguno que verificar.",
      "Implementation and tests - preserve that exact ordering; do not convert it to layer-local TDD.",
      "Environment/build configuration.",
      "Documentation and traceability."
    ]
  },
  "input_sha256": "sha256:88c2ca4650e46887cd5f31beed1f23d9196f0eb88b73102b7484568d569dc788",
  "contract_sha256": "sha256:ecd6baaff481debd09a47e197c49d615466b5ba253abef4650127cbdb03f813f"
}
```
