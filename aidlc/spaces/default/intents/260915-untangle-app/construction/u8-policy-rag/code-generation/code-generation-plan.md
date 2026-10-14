# Plan de generación de código — U8 `policy-rag`

U8 es la unidad que hace que una cita signifique algo: ingiere el corpus de U7,
lo indexa por aseguradora, recupera filtrado por póliza, comprueba cada cita
contra el corpus y entrega el nodo `policy_verification`. Es la unidad más
grande del proyecto y `CitationVerifier` es módulo crítico.

**Rama evaluada** (`team.md`): su caso previo son los **40 casos de DS-3**, que
hoy no existen. Se escriben primero, se corren, se comprueba que fallan, y solo
entonces se implementa. No hay atajo: el conjunto contra el que se mide todo lo
demás es lo primero que se escribe.

## Decisiones de esta etapa

| # | Decisión | Por qué |
| --- | --- | --- |
| CG-U8-1 | **Tres tandas, cada una en una sesión de la nube nueva.** Se abre, se le da el encargo, se revisa su rama aquí y se cierra | Las dos tandas de U21 corrieron en la misma ventana y costaron 45 USD, cuatro veces la de U9: cada mensaje vuelve a pagar el contexto acumulado (`docs/reference/sesiones-en-la-nube.md`) |
| CG-U8-2 | Los 40 casos de DS-3 se escriben **desde la tabla de composición de FD-U8-2**, y una prueba comprueba que cada `expected_clause_id` existe en `app/data/`, pertenece a la póliza del caso y no es distractor | Es donde un agente barato puede escribir un identificador plausible y falso. Una prueba lo ataja siempre; una revisión mía, solo esta vez |
| CG-U8-3 | **Una prueba que aísle cada regla de precedencia o de apagado**, escrita antes del código. En U8 son seis: filtrar antes de ordenar, solo lo recuperado se verifica, el endoso que rechaza, `no_clause_found` frente a `unverifiable`, el cierre que no cuenta para la métrica, y el idioma cruzado | Es el ajuste que salió de la evaluación de U9 y lo que destapó el hueco de U21 |
| CG-U8-4 | Ninguna prueba llama al proveedor: el `Embedder` se sustituye por un doble determinista con vectores sembrados. La ingesta real, con la clave, se corre **una vez aquí** | Las claves no salen de esta máquina, y la nube no tiene base de datos ni claves |
| CG-U8-5 | Las pruebas de integración —RLS, aislamiento vectorial, borrado, migración— se **escriben** en la nube y se **corren aquí**, con Docker levantado | El contenedor de la nube no tiene Docker; la rama llega con ellas escritas y la revisión las ejecuta |
| CG-U8-6 | La cláusula con instrucciones vive en un directorio nuevo, `app/evals/fixtures/injection-corpus/`, que se crea en el paso 7, con inquilino de prueba efímero, y nunca se ingiere en los tres de la demo | FD-U8-3: el corpus que se publica no contiene una trampa |

## Pasos

### Tanda 1 — el corpus dentro de la base

- [x] **Step 1 — Estructura, migración y el caso previo.**
  - Tarea nueva `mise run test:u8`, y paquete `policy_rag/` con `corpus/` y
    `citations/` (hoy son directorios vacíos del andamiaje de U1).
  - Se crea la migración `u8_policy_0001_corpus_tables` con las siete tablas,
    todas con RLS y política de inquilino, y clave foránea compuesta
    `(tenant_id, case_id)` en las dos de caso. (TECH-U8.1, BR1.7)
  - **Correr el subconjunto de arranque y ver fallar** lo que esta unidad va a
    sostener: hoy no hay corpus indexado ni verificador. Queda en el resumen con
    su salida. (rama evaluada)
- [x] **Step 2 — DS-3, los 40 casos, antes que el código.**
  - Veinte parejas según la tabla de FD-U8-2: seis corrientes, dos de idioma
    cruzado, tres de distractor, cinco sin cláusula, dos de endoso y dos de
    Knotwell. Identificador estable `DS-3/<idioma>/<nnn>`, un archivo por caso,
    contra el esquema `golden-case.schema.json`.
  - Los dos que no son de DS-3: el número de póliza ajeno va con DS-8 y la
    cláusula con instrucciones con DS-6. (AC2.8.4, AC2.2.4)
  - **La prueba que sostiene el conjunto:** cada `expected_clause_id` existe en
    `app/data/`, es de la aseguradora del caso, pertenece a la póliza y no es
    distractor. (CG-U8-2)
  - Correrlos y **ver fallar los 40**.
- [x] **Step 3 — Ingesta.**
  - Comparación del manifiesto antes de tocar nada; validación completa antes de
    indexar, sin ingesta parcial; una entrada de índice por cláusula.
  - Idempotencia por `content_hash`: sin cambios, cero llamadas al proveedor;
    con una cláusula cambiada, se reindexa esa.
  - `tsvector` con la configuración del idioma de la cláusula, y el
    identificador del modelo de embeddings como parte de la clave del índice.
  - Tarea nueva `mise run corpus:ingest`. (BR1.1 a BR1.7, PERF-U8.1, PERF-U8.2,
    TECH-U8.4, TECH-U8.5)

### Tanda 2 — recuperación y verificación

- [x] **Step 4 — Recuperación filtrada.**
  - Filtro por inquilino, póliza, formulario, versión y endosos vigentes
    **antes** de puntuar, con su prueba que lo aísla.
  - Búsqueda léxica y vectorial exacta, fusión por rango recíproco escrita a
    mano, cierre por relaciones marcado aparte y sin competir por el orden.
  - Póliza fuera de vigencia: conjunto vacío. Póliza de otra aseguradora:
    idéntico a inexistente, sin rama de código distinta.
  - `RetrievalProbe` como evento de traza con los filtros aplicados y el origen
    de cada cláusula. (BR2.1 a BR2.6, SEC-U8.1, SEC-U8.4, OBS-U8.1)
- [x] **Step 5 — El verificador exacto.**
  - Solo se verifica lo que está en el conjunto recuperado de esa respuesta, con
    su prueba que lo aísla.
  - Las cuatro comprobaciones por consulta: existencia, inquilino, póliza,
    vigencia. Ninguna con el modelo.
  - Resultado del conjunto cerrado, y `no_clause_found` frente a `unverifiable`
    como dos valores distintos, con su prueba que los aísla.
  - Una sola cita sin `verified` detiene la respuesta entera. (BR3.1 a BR3.4,
    BR3.8, SEC-U8.2)
- [x] **Step 6 — El endoso vigente y el registro.**
  - Un endoso vigente con relación `endorsement_modifies` hacia una cláusula
    citada la rechaza si la respuesta no lo cita también; queda en `amended_by`
    haya pasado o no. Prueba que lo aísla. (BR3.5, ADR-011)
  - `record_answer` con clave idempotente por caso y turno: reanudar no duplica.
  - Se persiste redactado, y las dos tablas entran al contrato de borrado de U2
    con su prueba. (BR4.1 a BR4.5, REL-U8.5, SEC-U8.6, SEC-U8.7)
- [x] **Step 7 — El texto recuperado como dato.**
  - Las cláusulas entran al prompt como campo delimitado del estado tipado,
    nunca concatenadas al de sistema.
  - Se crea el fixture de inyección en `app/evals/fixtures/injection-corpus/`,
    con inquilino efímero, y su caso nuevo en DS-6, en los dos idiomas.
    (BR2.7, SEC-U8.3, CG-U8-6)

### Tanda 3 — el nodo y el cierre

- [x] **Step 8 — El nodo `policy_verification`.**
  - Puro y cerrado, con su conjunto de escritura declarado, sin importar SDK ni
    canales; contrato de importación que lo comprueba.
  - Política de fallo como dato: un reintento y degradación honesta, aplicada
    por el ejecutor; rastro doble de cada fallo con nodo, tipo de error e
    intento.
  - Forma de la cita por canal: identificador y parte en texto, parte más
    resumen de una frase en voz, sin leer el texto y sin decir montos.
  - Idioma cruzado: la cláusula en su idioma, la respuesta en el de la
    conversación, y la clave nueva del catálogo que avisa de la diferencia, con
    su prueba que la aísla. (BR5.1 a BR5.8, OBS-U8.2)
- [x] **Step 9 — El respaldo de la afirmación.**
  - Segunda pasada del modelo sobre la respuesta ya verificada por código, en el
    ritmo de fondo y **nunca dentro del turno**, con contrato de importación que
    lo comprueba.
  - Apagado cuando el juez no está calibrado: el criterio sale "no medida" con
    su causa y las compuertas de código siguen bloqueando, con su prueba que lo
    aísla. (BR3.6, BR3.7)
- [x] **Step 10 — Compuertas.** Todo en verde, con la suite completa y
  `scripts/verify.sh` una sola vez al final (las tareas nuevas son `test:u8` y
  `corpus:ingest`):
  - `mise run test:u8`, `lint`, `types`, `schema:check`;
  - `copy:check`, `tenancy:literals`, `rls:check`, `migrate:check`;
  - `evals:run -- --subset smoke` y `evals:gate`;
  - `cov`, con 80 % o más agregado y 80 % o más en `policy_rag/citations/`;
  - `contracts:check` y `scripts/verify.sh`.
- [x] **Step 11 — Resumen, manifiesto y trazabilidad.** Los escribe la sesión
  principal: `code-summary.md`, `source-manifest.json` y `traceability.json`.

## Dónde corre cada tanda

Las tres tandas se escriben en la nube con Sonnet, **cada una en una sesión
nueva**, con los comandos de `uv` directos
(`docs/reference/sesiones-en-la-nube.md`). Tres cosas no salen de esta máquina:

- **La ingesta real con la clave de embeddings**, que se corre aquí una vez por
  tanda 1 y deja el índice construido.
- **Las compuertas que necesitan base de datos**: RLS, aislamiento vectorial,
  borrado, migración, `cov` y `scripts/verify.sh`.
- **La revisión de cada tanda y el commit a `main`.**

**Lo que gasta en crédito:** del orden de 11 USD por tanda en sesión limpia,
unos 33 en total, sobre los 190 que quedan hasta el 5 de noviembre.

**Lo que gasta en proveedor:** la ingesta real llama al modelo de embeddings una
vez por cláusula, unas 414 en total contando las copias de Knotwell. Esas
llamadas no tienen precio publicado y se registran como "no medidas", nunca como
cero (`prices.yaml`, PERF-U8.4).

## Qué no entra en esta unidad

- La ejecución de fondo y la precarga del nodo, y el umbral de su tiempo máximo:
  **U12 `graph-runtime`**.
- La cita expandible en pantalla: **U13 `chat`**.
- El contenido del corpus: **U7**. Si una cláusula está mal, la ingesta falla y
  el arreglo es allá.
- La medición contra el despliegue vivo: la pasada de publicación.
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
