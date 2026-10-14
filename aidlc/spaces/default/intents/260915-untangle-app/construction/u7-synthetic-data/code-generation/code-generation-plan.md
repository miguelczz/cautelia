# Plan de generación de código — U7 `synthetic-data`

Lo que se construye es el generador de datos sintéticos:
- la redacción de los textos fuente con el modelo y su revisión;
- la composición determinista del corpus de las dos emisoras y las copias de
  Knotwell, con las pólizas emitidas, los casos sembrados, DS-8 y los valores
  personales ficticios;
- las huellas de los formularios de terceros, con su compuerta;
- la carga de los casos sembrados por la API de U4.

**Fuentes:**
- `../functional-design/`: 30 reglas y FD-U7-1 a FD-U7-6.
- `../nfr-requirements/`: SEC-U7.1 a SEC-U7.5, TECH-U7.1 a TECH-U7.4,
  NFR10.7, NFR11.10 y NFR20.4.
- Contratos C-16, C-26 y C-28, y ADR-016.

Modo ligero (DP-12) y núcleo ahora (DP-14). Rama determinista.

## Decisiones de este plan

| # | Decisión | Por qué |
| --- | --- | --- |
| CG-U7-1 | El azar sale de SHA-256 sobre semilla, ruta de salida y contador; `random` no se usa | La documentación de Python solo garantiza la secuencia de `random()` entre versiones (`tech-stack-decisions.md`, BR1.2) |
| CG-U7-2 | Los repertorios de personas, vehículos y los turnos cortos de los casos sembrados se escriben a mano (`drafted_with: hand`) y se revisan igual | Son listas y frases de una línea, no prosa de póliza; el modelo no aporta y sí exige otra ronda de revisión |
| CG-U7-3 | La redacción usa el modelo del uso `operations` que ya ancla `app/config/providers/providers.yaml` | Una sola forma de llamar al modelo (ADR-016, BR2.1) |
| CG-U7-4 | `synthetic:check` regenera en un directorio temporal, compara byte a byte con `app/data/` y lo corre `scripts/verify.sh` en el paso de chequeos de contenido | TECH-U7.1: lo versionado es exactamente lo que produce el generador |
| CG-U7-5 | Las huellas aceptan el specimen en PDF, leído con `pypdf` (dependencia nueva, solo de desarrollo), o en texto plano | Los reguladores publican PDF; el texto plano sirve si la extracción falla |
| CG-U7-6 | DS-8 conserva su ruta y su contenido; solo cambian `generated` a `true` y su motivo | BR7.3: las pruebas de aislamiento de U2 no cambian |
| CG-U7-7 | Si la cuota gratuita de Gemini se agota durante la redacción, el paso se detiene y se retoma otro día, sin cambiar de plan ni de clave | La regla de no recargar ni contratar; el trabajo no tiene prisa por horas |

## Pasos

### Bloque A — Estructura y pruebas listas

- [x] **Step 1 — Estructura.** Paquete `synthetic_data/` con sus módulos:
  fuentes, composición, escritura canónica, manifiesto, huellas, redacción,
  siembra y comando. Incluye `pypdf` en el grupo de desarrollo, con su línea de
  justificación. Se comprueba que `tmp/synthetic-drafts/` y `tmp/specimens/`
  quedan ignorados. (US5.3)
- [x] **Step 2 — Pruebas ejecutables.** Tareas nuevas en `mise.toml`:
  `test:u7`, `synthetic:generate`, `synthetic:check`, `synthetic:draft`,
  `synthetic:fingerprints`, `synthetic:sample` y `synthetic:seed`. Se comprueba
  que `test:u7` corre.

### Bloque B — Modelo de datos (esquemas y validación)

- [x] **Step 3 — Modelos.** `SourceText`, `GenerationManifest`, `FormRecord`,
  `ClauseRecord`, `ClauseRelationRecord`, `IssuedPolicyRecord`, `PersonaRef`,
  `VehicleRef`, `SeededCaseRecord`, `FingerprintSet` y `ReviewSample`.
  - Llevan las validaciones de BR2.2, BR3.2, BR3.4, BR3.6 y BR7.1.
  - Sus JSON Schema se generan a `app/contracts/schemas/`, incluido
    `manifest.schema.json` (C-28).
  - `schema:check` se amplía con el manifiesto (TECH-U7.2).
- [x] **Step 4 — Pruebas de los modelos.** Cada forma de romper una regla falla
  con el archivo y la clave. (BR2.2, BR3.2, BR3.4, BR3.6, BR7.1)

### Bloque C — Lógica: núcleo determinista, redacción y corpus

- [x] **Step 5 — Núcleo determinista.** El elegidor sembrado (CG-U7-1), la
  escritura canónica y el manifiesto con los hashes de entradas y salidas.
  Generar valida todo antes de escribir, y si algo falla no escribe nada.
  - Pruebas: dos generaciones dan los mismos bytes; añadir una salida no cambia
    las demás; nada depende del reloj; el entorno vacío y un espía en la
    fábrica muestran cero llamadas. (BR1.1 a BR1.5, SEC-U7.5)
- [x] **Step 6 — Comando de redacción.**
  - Arma el prompt desde la referencia de estructura y una plantilla versionada.
  - Llama por la fábrica de U5 con el uso `operations`, pasando por el techo y
    el gasto, y escribe en `tmp/synthetic-drafts/`.
  - Pruebas con el doble del proveedor: el prompt nunca lleva contenido de
    `tmp/specimens/`, y un borrador plantado no cambia la salida.
    (BR2.1, BR2.3, SEC-U7.4)
- [x] **Step 7 — Redactar y promover los textos fuente.**
  - Se corre `synthetic:draft` por parte, aseguradora e idioma: unas veinte
    llamadas al plan gratuito.
  - El agente revisa cada borrador contra las partes y numerales de la
    referencia, contra P8 y contra los criterios: el endoso de transporte solo
    en Sunmeadow, cinco endosos y ocho distractores por emisora, y el documento
    de Corvane.
  - Lo aprobado se promueve a `app/data/sources/` (carpeta nueva), con
    `reviewed_by: conductor`.
  - Los repertorios de personas y vehículos y los turnos de los casos se
    escriben a mano (CG-U7-2).
  - Si la cuota se agota, aplica CG-U7-7.
- [x] **Step 8 — Composición.** Genera `app/data/`, carpeta que se crea con este
  paso:
  - los formularios, los endosos, los distractores y las relaciones;
  - las copias de Knotwell;
  - las personas y los vehículos;
  - las pólizas emitidas, con las tres `example_policy`;
  - los casos sembrados: siete estados por tres aseguradoras por dos idiomas,
    y un cerrado con cada resolución, con `used_by`;
  - DS-8 regenerado (CG-U7-6);
  - la lista de valores personales y las diferencias declaradas.
- [x] **Step 9 — Pruebas de la composición.**
  - Partes completas y cuentas de endosos y distractores.
  - Knotwell: una copia alterada falla la validación.
  - Casos: todas las combinaciones de estado, aseguradora e idioma
    (TECH-U7.3, NFR20.4).
  - Rangos ficticios (SEC-U7.3).
  - La redacción de U3 encuentra cada valor sembrado, por tipo e idioma
    (NFR11.10).
  - DS-8 igual al de U2, con `test:u2` en verde (NFR10.7).
  - Las diferencias declaradas coinciden con el corpus.
  (BR3.1 a BR7.3)

### Bloque D — Texto propio

- [x] **Step 10 — Huellas y compuerta.**
  - `synthetic:fingerprints` lee los specimens: normaliza, quita encabezados y
    numeración, corta secuencias de ocho palabras y guarda solo los SHA-256 en
    `app/config/content/third-party-shingles.json`, archivo nuevo.
  - `content:check` falla ante una sola secuencia compartida, y queda "no
    medido" y falla si el archivo de huellas falta.
  - Las pruebas usan un specimen inventado para el caso, nunca uno real.
  (BR5.1 a BR5.3, SEC-U7.1, SEC-U7.2)
- [x] **Step 11 — Huellas reales.**
  - Con los specimens públicos en `tmp/specimens/`, se corre
    `synthetic:fingerprints` y después `content:check`.
  - Si una cláusula coincide, se reescribe con su revisión y se regenera. El
    umbral no se toca.

### Bloque E — Siembra, muestra y fronteras

- [x] **Step 12 — Siembra y fronteras.**
  - `synthetic:seed` carga los casos por la API de U4 con origen `generator`.
  - La fixture de pruebas los carga dentro de la transacción de la prueba y la
    revierte al terminar.
  - Contratos de importación nuevos:
    - `evals` no importa `synthetic_data` (BR8.1);
    - la composición no importa `providers` (BR1.5);
    - `synthetic_data` solo llega a la base por la API de U4 (BR6.3).
  - Pruebas: dos pruebas en paralelo sobre el mismo caso no se ven, y cada
    contrato se prueba con una violación plantada y retirada.
  (BR6.3, BR6.4, BR8.1)
- [x] **Step 13 — Muestra humana y regeneración en cada entrega.**
  - `synthetic:sample` elige diez cláusulas por emisora con una semilla
    registrada y escribe la muestra en `app/data/sources/reviews/`, carpeta
    nueva.
  - `synthetic:check` entra en `scripts/verify.sh` (CG-U7-4), y se mide su
    duración (TECH-U7.4).
  (BR5.4, TECH-U7.1)

### Bloque F — Compuertas

- [x] **Step 14 — Guion completo.** En verde:
  - `mise run contracts:check`, `lint`, `types`, `schema:check` y
    `content:check`;
  - `cov`, con 80 % o más y sin exclusiones nuevas;
  - `scripts/verify.sh`.

### Bloque G — Documentación y trazabilidad

- [x] **Step 15 — Resumen, manifiesto y trazabilidad.**
  - `code-summary.md`;
  - `source-manifest.json`;
  - `traceability.json`, con los 20 criterios, las 30 reglas y los `NFRx.y` de
    U7.

  U7 no se cierra hasta que las dos muestras tengan el veredicto de Miguel
  (AC5.4.5, AC5.5.6).
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
      "text": "- **Methodology**: custom\n- **Ordering**: Clasifica cada unidad en una de dos ramas y no dejes ninguna sin rama. Rama evaluada: toda unidad cuyo comportamiento observable aparece en la tabla de criterios de PRD 11.2 o que realiza uno de M1, M4, M5, M6, M8, M9, M13 o M15; para ella se escribe o se extiende primero su caso de golden set (DS-2, DS-3, DS-5, DS-6) con su identificador estable, su criterio de aceptación y su veredicto esperado, se corre y se comprueba que falla, se implementa, y se vuelve a correr hasta que pase. Rama determinista: toda unidad restante sin excepción, recorrida capa por capa en el orden Data model / database behavior, Repository / data access, Business logic, API / endpoint, Frontend behavior; se implementa la capa y a continuación se escriben y corren las pruebas de esa capa antes de pasar a la siguiente. Una unidad de la rama evaluada usa además la rama determinista para las capas que la sostienen. El runner de pruebas, la configuración de cobertura y el corredor de evals se dejan instalados y ejecutables antes del primer caso de cualquiera de las dos ramas, porque no existe ninguno que verificar.\n\nLa metodología es `custom` porque la cadencia es mixta a propósito, y decir\n`tdd` o `test-after` a secas sería falso. Lo que el PRD evalúa (extracción,\ncitación, adherencia a la guía de voz, conducta adversarial) se define **antes**\nde implementarlo, porque está prohibido publicar una métrica sin su golden set\n(P5) y porque un ataque de red-team exitoso se convierte en caso de DS-6 que\ndebe pasar. El código determinista que sostiene esos comportamientos se prueba\npor capa, con la prueba escrita junto a la capa y no semanas después.\n\n**Punto de partida.** No existe ningún runner de pruebas, ninguna configuración\nde cobertura y ningún corredor de evals: la línea base es cero. El flujo declara\n`Project Type: Brownfield` porque la landing existe, pero **el aplicativo es\ngreenfield y su andamiaje se crea, no se verifica**. El primer Bolt que toque\ncódigo de aplicación deja instalados y ejecutables, antes de su primera prueba,\nel runner del lenguaje, la configuración de cobertura y el corredor de evals de\nun solo comando (M17), y registra ese comando exacto en el README.\n\n**Piso de cobertura.** 80 % de líneas **agregado** sobre el código del\naplicativo, con piso del 80 % también en los módulos críticos: motor de reglas,\nverificador de citas, aislamiento por tenant, esquema del caso y **redacción de\ndatos personales** (esta última añadida por decisión de Miguel el 2026-09-20:\nsu compuerta detiene la entrega con un solo hallazgo y su fallo es silencioso,\nporque una redacción rota no rompe ninguna pantalla ni levanta ningún error). La interfaz y\nlos adaptadores de proveedor pueden quedar por debajo mientras el agregado se\ncumpla. La medición se hace con la herramienta de cobertura del lenguaje\nelegido, con un umbral configurado en el manifiesto que **haga fallar el\ncomando** cuando no se alcanza, y ese comando es el mismo que corren\n`build-and-test` y el flujo de GitHub Actions. Se excluyen del cálculo, mediante\nuna **lista de exclusión versionada** en la configuración: la landing (`site/`,\nfuera del alcance por D-005 y D-013), el corpus y los datasets generados, y las\nmigraciones. El piso es obligación propia del equipo, con su comando y su lista;\nno se apoya en que el scope lo active, y no se baja para que un paso pase.\n\n**Datos de prueba.** Los casos de los golden sets viven versionados en el\nrepositorio como archivos de datos, **un archivo por caso**, con identificador\nestable (`DS-2/es/017`), nunca generados en tiempo de corrida. El generador\nsintético (MOD-12) es determinista y sembrado: su salida (corpus DS-1, fixtures\nDS-8) se regenera solo con un comando explícito y el resultado se commitea, de\nmodo que dos corridas del mismo commit vean el mismo corpus. Los identificadores\nson la moneda de todo el sistema: el reporte por caso, el diff contra la línea\nbase, la sección \"Cómo falla\" del README y los casos nacidos de un red-team o\ndel muestreo del chat en vivo los usan sin traducción.\n\n**Forma de las pruebas.** Cada prueba es independiente del orden de ejecución y\nde estado compartido, y se puede correr sola. Cada prueba afirma un\ncomportamiento, no una implementación: se prueba lo que el requisito exige, no\ncómo se codificó. Ninguna prueba pasa con independencia de la implementación.\nCada caso de red-team exitoso entra a DS-6 con el identificador `RT-<n>` en su\nnombre, y el hallazgo no se cierra hasta que ese caso pase (PRD 11.4).\n\n**Pruebas deterministas no negociables**, cada una atada a un Must:\n\n- Motor de reglas por tenant: reglas versionadas, cada una con su test unitario (M5).\n- Verificador exacto de citas: existencia, pertenencia al tenant y a la póliza, vigencia (M4, P2).\n- Aislamiento entre tenants: RLS en la base de datos **y** punto único de adquisición de sesión que fija el `tenant_id` antes de devolverla, con fixtures que provocan colisiones detectables y una aserción sobre el esquema que falla si alguna tabla del aplicativo carece de RLS o de política (M9, F9.1, F9.4, DS-8).\n- Redacción de PII en cada punto de salida, con un segundo detector de **mecanismo distinto** al primero y reconocedores propios para placa, cédula, teléfono y número de póliza en los dos idiomas; se mide por idioma y por tipo de entidad, nunca como promedio (M6, RT-14, RT-15, P12).\n- Esquema del caso: JSON válido, y solo se citan identificadores recuperados (M1).\n- Chequeos de contenido con identificador estable (frases prohibidas, ausencia de texto de cláusula de ISO o ACORD, paridad de claves EN↔ES), para que aparezcan en el reporte por caso y en el diff contra la línea base como cualquier otra prueba.\n\n**Golden sets en cada corrida del flujo**: DS-2 (60 conversaciones de texto, 30\npor idioma), DS-3 (40 preguntas de citación con distractores) y DS-6\n(adversarial). Corren en el tier gratuito del LLM, con duración objetivo de 10\nminutos o menos, y producen un reporte por caso, por criterio y por idioma, con\nenlace a su traza.\n\n**Compuertas duras** (`[bloquea]` en PRD 11.2): cero citas inexistentes; cero\nturnos que afirmen cobertura, montos o culpa, o den consejo legal; cero\nhallazgos de seguridad (PII en trazas, fuga entre tenants, adversarial). Son\npasa o falla por caso y un solo fallo detiene la entrega. Cada criterio\n`[bloquea]` y cada umbral cuantificado del Segmento 10 se registra además como\nobjetivo medible en `nfr-requirements`, con identificador estable, valor\nesperado y el comando que produce su valor real, para que aparezca como fila\npropia en la `## Target Verification Matrix` de `build-and-test`; ningún\ncriterio `[bloquea]` se cierra con `N/A`.\n\n**Tipos de prueba obligatorios pese a la estrategia.** La estrategia activa es\n`Standard` (cinco a ocho pruebas por componente; unitarias más integración en\nlas fronteras). Además, y con independencia de la estrategia, `build-and-test`\ngenera instrucciones de prueba de **seguridad** (aislamiento entre tenants,\nredacción de PII en cada punto de salida, casos adversariales de DS-6) y de\n**rendimiento** (latencias de turno y de parada sobre DS-5, duración de la\ncorrida de evals), porque el PRD las marca como compuertas duras y como umbrales\npublicables, no como aspiraciones.\n\n**Definición de regresión.** Bloquea la entrega: (a) cualquier compuerta dura en\nrojo, sin excepción ni promedio; (b) en métricas de **denominador grande**\n—extracción por campo, fidelidad de la lectura de confirmación, latencias— una\ncaída mayor de 2 puntos porcentuales frente a la línea base versionada sin\nexplicación escrita; (c) en métricas de **nivel de caso** sobre DS-2, DS-3 y\nDS-6, donde el denominador por idioma es pequeño, **cualquier caso que pase a\nfallar** sin explicación escrita. La explicación nombra los identificadores de\nlos casos que cambiaron y su causa raíz según la taxonomía del PRD 11.3; una\nexplicación que no nombre casos no cuenta como explicación.\n\nEl umbral porcentual se reserva para el denominador grande porque en los\nconjuntos pequeños no distingue señal de ruido:\n\n| Dataset | Casos por idioma | Cuánto mueve un caso |\n| --- | --- | --- |\n| DS-2 (golden set de texto) | 30 | 3,3 pp |\n| DS-3 (citación) | 20 | 5,0 pp |\n| DS-6 (adversarial, v0) | 10 | 10,0 pp |\n\n**Determinismo de la corrida.** La corrida de evals fija todo lo que se pueda\nfijar: temperatura en 0 y semilla fija donde el proveedor lo permita, versión\ndel modelo anclada por identificador exacto (nunca un alias móvil), prompts y\nrúbricas versionados en el repositorio, y el respondedor del asegurado por\nreglas indexado por campo del PRD 11.1. Cuando un caso siga siendo inestable\nentre corridas idénticas, se marca como inestable con su identificador en un\narchivo versionado, deja de contar para la compuerta, se reporta aparte con esa\netiqueta y su estabilización se abre como trabajo; nunca se borra del set (P5).\n\n**Compuerta en rojo por causa ajena al cambio.** Cuando la compuerta se pone\nroja por una caída del proveedor, un cambio de versión del modelo o una cuota\nagotada, se registra la causa y el identificador de la corrida, la corrida se\nmarca como **no comparable** y se repite; si sigue roja, bloquea. **El umbral no\nse toca nunca** y la marca queda en el registro. Una compuerta que no se pudo\nejecutar se declara \"no medida\" en el reporte, nunca se omite.\n\n**Juez descalibrado.** Los veredictos del juez (LLM) solo cuentan mientras sus\ndos tasas contra las etiquetas humanas de DS-7, la de fallos que detecta (TNR) y\nla de aciertos que confirma (TPR), medidas por criterio y por idioma sobre la\npartición de prueba y con intervalo de confianza, estén en el umbral que fija\n`nfr-requirements` (decisión de Miguel del 2026-09-17, que reemplaza el 85 % de\nacuerdo; ADR-014). Si caen por debajo, o si cambia el modelo del juez o la\nrúbrica sin recalibrar, sus\nveredictos dejan de contar: los criterios que dependen de él se reportan como\n\"no medida\" con esa causa, no bloquean, y la recalibración se abre como trabajo\ncon fecha. Las compuertas duras juzgadas por código —citas inexistentes,\naislamiento, PII en trazas, esquema— no dependen del juez y siguen bloqueando.\n\n**Presupuesto de la corrida.** La corrida de evals de texto tiene un objetivo de\n10 minutos y su duración se mide y se publica como métrica desde la línea base\nv0 (Segmento 10.5). El corredor admite ejecutar un subconjunto declarado y\nreproducible; si la corrida completa deja de caber en el presupuesto o en los\nlímites del tier gratuito, la compuerta corre ese subconjunto declarado —nunca\nse apaga— y la corrida completa pasa a ser obligatoria por hito y antes de\npublicar cualquier línea base.\n\n**Dónde corre la compuerta.** El ejecutor autoritativo es el flujo de GitHub\nActions sobre `main`, invocando el guion único de verificación. Dentro de este\nintent, la etapa `build-and-test` ejecuta ese mismo comando. Las prácticas no\ncambian cuando cambia el ejecutor: solo cambia quién lo dispara.\n\n**Lo que no corre en cada corrida**: los golden sets de audio (DS-5, 20\ngrabaciones) corren por hito, no por cambio, porque el costo de voz está topado\ny las grabaciones dependen de terceros.\n\n**Paridad por idioma**: los mismos casos, las mismas métricas y las mismas metas\nen español e inglés; el reporte muestra los dos lados a lado y nunca un promedio\ncombinado (P12).\n\n**Herramientas**: el runner de pruebas del lenguaje elegido, más un corredor de\nevals propio con un juez propio calibrado para la compuerta (decisión de Miguel\ndel 2026-09-17, ADR-014; reemplaza \"`promptfoo` o `DeepEval`\"), `promptfoo` solo\npara red-teaming por hito y Langfuse para la anotación humana. El corredor de evals se\ninvoca con un solo comando y ese comando está en el archivo de tareas y en el\nREADME (M17)."
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
  "input_sha256": "sha256:0226cf570c9568fe6fa1de61b29a94e7b0709fc04b42d102e273b1d2645d69a9",
  "contract_sha256": "sha256:6373b3c2e4592ca33a8ad34e18f87d9ef32d8f0a12fc3ba68ba53a709c613250"
}
```
