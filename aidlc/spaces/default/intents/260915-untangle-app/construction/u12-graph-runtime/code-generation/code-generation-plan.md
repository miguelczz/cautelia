# Plan de generación de código — U12 `graph-runtime`

U12 convierte cuatro nodos en un sistema. Deja el estado tipado compuesto desde
sus contratos, la transición pura, el ejecutor común de la política de fallo, los
dos ritmos, los puntos de control con su aislamiento, la pausa hacia la bandeja y
el punto único de salida.

Es la unidad de la que dependen U13, U14, U16, U17 y U18: hasta que exista, no hay
forma de conversar con el sistema de punta a punta, y por eso los 40 casos de DS-3
y el etiquetado de DS-7 siguen esperando.

## Decisiones de esta etapa

| ID | Decisión | Por qué |
| --- | --- | --- |
| CG-U12-1 | **Se construye en esta sesión, no en la nube** | Decisión del 2026-09-27. El motivo por el que el código se fue a la nube —el límite semanal de uso— ya no se cumple, y quedan 54 USD de crédito para nueve unidades. Además, media docena de las reglas de esta unidad solo se pueden comprobar **con base de datos delante** —puntos de control, aislamiento, arrendamientos, migración— que es justo lo que esa sesión no tiene |
| CG-U12-2 | **Las compuertas corren al cerrar cada paso, no al final** | Es la ventaja de construir aquí y sería un desperdicio no usarla: un defecto de aislamiento encontrado en el paso 2 cuesta minutos; encontrado al final, cuesta rehacer lo que se apoyó en él |
| CG-U12-3 | **Ninguna prueba llama al proveedor**; los fallos se inyectan con dobles deterministas | Mismo criterio que U8 y U11. Un ejecutor que solo se probara con el proveedor real no se podría probar en rojo |
| CG-U12-4 | **El envoltorio del checkpointer se construye antes que nada que lo use** | FD-U12-3 lo nombra como el riesgo más probable de esta unidad. Si su pieza no tolera que otro maneje sus transacciones, hay que saberlo el primer día y no con tres pasos construidos encima |

## Pasos

### Paso 1 — Las tres tablas, con su aislamiento

- Migración aditiva encadenada a la cabeza actual: `graph_checkpoint`,
  `human_review_request` y `node_run`, las tres con columna de aseguradora,
  política de fila, `FORCE ROW LEVEL SECURITY` y sus llaves foráneas compuestas.
- El `payload` del punto de control **cifrado con el cifrador del caso** (BR6.3).
- Pruebas: la aserción de esquema las ve; una prueba de integración intenta leer
  una fila de otra aseguradora y no la encuentra; `migrate:check` sube, baja y
  vuelve a subir.
- **Compuertas al cerrar el paso:** `migrate:check`, `rls:check`, `schema:check`.

### Paso 2 — El envoltorio del checkpointer, y su prueba de aislamiento

- La capa delgada de FD-U12-3: las operaciones del checkpointer corren dentro de
  una transacción tomada del punto único de sesión, con la aseguradora fijada.
- Prueba que lo aísla: dos aseguradoras con un hilo del mismo identificador; la
  segunda no ve el punto de control de la primera, ni siquiera que existe.
- **Si la pieza del framework no lo tolera**, se para y se dice: la salida escrita
  es nuestra propia pieza de puntos de control, no un segundo camino a la base.
- **Compuertas al cerrar el paso:** `rls:check` y la prueba de integración nueva.

### Paso 3 — El estado tipado y la transición

- El estado se **compone** de los conjuntos de escritura de los cuatro `NodeSpec`
  y **falla al arrancar** si dos declaran el mismo campo (BR1.5).
- La transición: pura, cerrada, sin cliente de modelo en su cadena; el contrato de
  `import-linter` que lo comprueba.
- Prueba que lo aísla: un estado sembrado en el que el resultado del modelo dice
  "ir a decision" produce la misma ruta que el mismo estado sin ese texto (BR1.3).
- **Compuertas al cerrar el paso:** `lint` (contratos de importación) y `types`.

### Paso 4 — El ejecutor y la política de fallo

- Tiempo máximo, intentos y texto de degradación leídos del `NodeSpec`, **sin
  ninguna rama por nombre de nodo** (BR5.1).
- El campo nuevo de C-15 —quién cuenta los reintentos— aplicado: el único nodo que
  declara `node` es `policy_verification`, y sobre él el ejecutor no reintenta
  (FD-U12-2).
- `NodeRun` por ejecución, con su clave de idempotencia derivada del caso, el nodo
  y la entrada; nunca del reloj ni de un aleatorio (BR5.4).
- Pruebas con fallos y retardos inyectados: un reintento y no más; el texto de
  degradación por el punto único; el caso y el turno conservados; la traza con
  nodo, tipo de error e intento.

### Paso 5 — Los dos ritmos

- El turno responde de inmediato y lanza el fondo sin esperarlo (BR2.2), con la
  precarga al confirmarse la identidad (BR2.1).
- Dentro del turno, solo los tres controles baratos, comprobado analizando la
  cadena de llamadas y no leyendo el código (BR2.3).
- La frase de espera cuando el fondo no ha vuelto (BR2.4).
- El arrendamiento con latido y el barrido al arrancar (BR5.5).
- Pruebas cronometradas de PERF-U12.2, PERF-U12.3 y PERF-U12.4 sobre el
  `NodeSpec` declarado.

### Paso 6 — Puntos de control, pausa y reanudación

- Un punto de control por caso después de cada turno; reanudar no repite lo
  confirmado (BR3.1, BR3.2).
- La sesión abandonada deja el caso esperando al asegurado, con su motivo, **sin
  decidir nada** sobre datos incompletos (BR3.3).
- `interrupt()` hacia la bandeja con su motivo del conjunto cerrado, la
  reanudación con la decisión y el retiro de la pausa (BR4.1, BR4.4).
- **Compuerta dura BR3.4:** dos navegadores con la misma póliza de ejemplo; al
  segundo no se le ofrece ni se le revela el caso del primero, y su respuesta es
  idéntica en texto y en estado a la de una sesión sin casos.
- **Compuertas al cerrar el paso:** la prueba de integración de la reanudación y
  la de la compuerta dura.

### Paso 7 — El punto único de salida y la interfaz del turno

- `handle_turn`, `resume_case` y `preload` con la forma exacta de C-14, y el flujo
  de eventos tipados que termina siempre con `FinalText`, `Handoff` o `TurnError`.
- Todo evento por el punto único, que aplica los tres controles, **también en
  degradación y error** (BR2.5).
- El desvío de cobertura: se responde con lo que el fondo ya dejó y el bloque
  siguiente es el que estaba pendiente (BR4.2, BR4.3).
- La sonda genérica de conversación: recorre el guion de un caso de DS-2 por los
  nodos reales y comprueba lo que el caso declara. Es lo que deja medibles los
  casos que faltan del golden set.

### Paso 8 — Compuertas y cierre

- La suite completa, `scripts/verify.sh` entero y `evals:run` completo.
- El resumen de código, la trazabilidad y el manifiesto de fuentes.

## Dónde corre cada paso

Todo aquí, con la base de datos delante y las compuertas al cerrar cada paso
(CG-U12-1, CG-U12-2). No hay encargo a la nube en esta unidad.

## Qué no entra en esta unidad

- **Los cuatro nodos:** U8, U9, U10 y U11. Esta unidad los ejecuta.
- **El transporte de cada canal:** U13 (chat) y U16 (voz).
- **Las pantallas de la bandeja y la decisión humana:** U14.
- **Los trece casos que le faltan a DS-2:** dos de ellos —pregunta de cobertura a
  mitad y llamada cortada con reanudación— se escriben aquí porque dependen de la
  conducta de esta unidad; los otros once son el encargo reservado para la nube,
  sobre la sonda que el paso 7 deja construida.
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
