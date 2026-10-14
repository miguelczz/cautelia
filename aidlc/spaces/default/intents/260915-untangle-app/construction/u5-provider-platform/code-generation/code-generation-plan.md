# Plan de generación de código — U5 `provider-platform`

Lo que se construye: los puertos de proveedor con el adaptador de Gemini detrás,
la contabilidad del gasto con su techo y sus cuotas, y las trazas con sus
resúmenes. Tres contratos —C-16, C-17 y C-23— y cuatro tablas.

**Rama de pruebas: determinista.** La ficha de la unidad lo declara así, y es
correcto: ninguna de sus historias realiza M1, M4, M5, M6, M8, M9, M13 ni M15.
Así que se recorre capa por capa en el orden del contrato —modelo de datos,
repositorio, lógica de negocio, superficie— y las pruebas de cada capa se
escriben y se corren **antes** de pasar a la siguiente.

## Lo que ya está decidido y aquí solo se implementa

| Decisión | Dónde se tomó |
| --- | --- |
| Cuatro entidades guardadas, quince objetos de valor, 53 reglas | `../functional-design/` |
| Dinero y cuotas fuera del aislamiento, pagado con la aserción de columnas | FD-U5-1 |
| El costo viaja con su estado; toda agregación devuelve el par | FD-U5-2, BR3.4, BR3.9, BR3.5 |
| Precio de lista siempre; el techo suma solo lo facturable | FD-U5-3, BR3.6, BR4.2 |
| Cupo del sitio derivado del presupuesto público y los días que faltan | FD-U5-4, BR5.6 |
| La llamada del día se consume al abrir y se devuelve si no hubo audio | FD-U5-5, BR5.4, BR5.5 |
| La fila de gasto nombra el caso y no cuelga de él | FD-U5-6, BR7.5 |
| Dos carriles de presupuesto y la reserva de grabación | FD-U5-11, FD-U5-12, BR4.9, BR4.10 |
| Cortacircuitos en el adaptador, por proveedor y por uso | `../nfr-design/reliability-design.md`, Q1 |
| Una sola sentencia que incrementa y devuelve | `../nfr-design/performance-design.md`, Q2 |
| Cola acotada que pasa a síncrona al llenarse | Q3 |
| Lista cerrada de atributos de tramo | Q4, capa 4 del diseño de seguridad |
| Dos tareas nuevas, el paso 6 no crece, cuatro contratos de importación | `../infrastructure-design/cicd-pipeline.md` |

## Trazabilidad de historias a pasos

| Historia / criterio | Pasos que lo implementan |
| --- | --- |
| US4.8 — AC4.8.1 (tres niveles) | 12, 13 |
| US4.8 — AC4.8.2 (grafía de los nodos) | 12 |
| US4.8 — AC4.8.3 (ruta, pausa y reanudación) | 13 |
| US4.8 — AC4.8.4 (precio declarado o "no medido") | 5, 6 |
| US4.8 — AC4.8.5 (los fallos también se trazan) | 11, 12 |
| US5.14 — AC5.14.1 (las vistas del gasto) | 7, 16 |
| US5.14 — AC5.14.2 (alerta una sola vez) | 7 |
| US5.14 — AC5.14.3 (corte en el techo) | 8, 9 |
| US5.14 — AC5.14.4 (el registro sobrevive) | 15 |
| US5.14 — AC5.14.5 (meta del hito) | 5, 16 — la medición sobre DS-5 es de U16 y U21 |
| US5.14 — AC5.14.6 (costo por caso exitoso) | 16 |
| US4.12 — AC4.12.1, .2, .4 (el punto único, por las trazas) | 13, 14 |

## Los pasos

### Bloque A — Configuración versionada y modelos

- [ ] **Paso 1 — La carpeta de configuración de proveedores.**
      `app/config/providers/providers.yaml` (proveedores, modelos anclados por
      identificador exacto, plan por uso con su marca de facturable, parámetros
      del cortacircuitos, límites de la voz y reserva de grabación en minutos) y
      `app/config/providers/prices.yaml` (tabla de precios con su versión y su
      fecha). Dos archivos y no uno porque los precios cambian con su propia
      cadencia y llevan su propia versión.
      Sus modelos Pydantic en `untangle/providers/config.py`, con los JSON
      Schema generados por `contracts:gen` (C-28) y validados por
      `schema:check`.
- [ ] **Paso 2 — Pruebas de la capa de configuración.** Que un modelo declarado
      con alias móvil no cargue; que un uso sin plan declarado no cargue; que un
      tope con figura `none_available` y sin sustituto no cargue; que una fecha
      de comprobación de más de treinta días falle (lógica en `schema_check.py`,
      no restricción de esquema).
- [ ] **Paso 3 — Los modelos del dinero y las cuotas.**
      `untangle/telemetry/spend/models.py`: `Money` (cantidad y estado, que
      viajan juntos), `SpendTotal` (medido y conteo de no medidas), `CostStatus`,
      `Use`, `BudgetLane`, `UnitKind`, `SpendSource`, `QuotaScope`,
      `QuotaDecision`, `VoiceMode`, `BudgetState`, `CallReserve`, `ProviderName`,
      y las cuatro entidades guardadas. **Dinero en `Decimal`, nunca en coma
      flotante**, y el tipo lo impone: `Money` no acepta `float`.
- [ ] **Paso 4 — Pruebas de los modelos.** Que no se pueda construir un costo
      medido sin precio ni fecha (BR3.4); que no se pueda construir una cantidad
      sin estado (BR3.9); que `float` no entre donde va dinero; que las cláusulas
      verificadas no superen a las recuperadas; que `QuotaDecision` negativa
      exija motivo de la lista cerrada.

### Bloque B — Cálculo del costo y del cupo (lógica pura, sin base)

- [ ] **Paso 5 — El cálculo del costo.** `untangle/telemetry/spend/pricing.py`:
      busca en la tabla cargada por (proveedor, modelo, unidad), multiplica en
      decimal, y devuelve `Money` medido con su precio, su versión de lista y su
      fecha, o **no medido** con las cuatro columnas vacías. Nunca cero por falta
      de precio.
- [ ] **Paso 6 — Pruebas del cálculo.** Precio presente, precio ausente, y que
      la suma de veinte fracciones de centavo dé el mismo total en cualquier
      orden (que es lo que la coma flotante no cumple).
- [ ] **Paso 7 — La aritmética del presupuesto.**
      `untangle/telemetry/spend/budget.py`: derivar el estado (`ok`, `alerted`,
      `exhausted`) del acumulado y la marca; el presupuesto público restante
      (techo menos reserva menos gastado público); si esta llamada cruzó la
      alerta; y el par que devuelve toda agregación. Funciones puras.
- [ ] **Paso 8 — La aritmética del cupo.** `untangle/telemetry/spend/quota.py`:
      el cupo del sitio `min(15, piso(público_restante / (días_restantes ×
      reserva_por_llamada)))` con piso en cero; el periodo del día en la zona
      horaria configurada con reloj inyectado; y la decisión de cuota con su
      motivo.
- [ ] **Paso 9 — Pruebas de la aritmética.** Los bordes que los criterios
      nombran: presupuesto a la mitad con la ventana a la mitad (el cupo alcanza
      al día 90); presupuesto agotado (cupo cero); cruce de la alerta una sola
      vez con veinte incrementos seguidos; medianoche de la zona configurada
      frente a la del servidor; y el carril de grabación con el cupo público
      agotado.

### Bloque C — Esquema y repositorio

- [ ] **Paso 10 — La revisión de migración.** Las cuatro tablas. `spend_entry`,
      `quota_counter` y `budget_window` **sin política de aseguradora**, con sus
      tres entradas en la lista de exclusión del manifiesto, cada una con su
      razón. `trace_summary` con su columna de aseguradora, aislamiento
      habilitado y forzado, su política y su marca `visitor-data`. El caso se
      **nombra** desde `spend_entry` con borrado que deja la columna en nulo, y
      se **cuelga** desde `trace_summary` en cascada. Dinero en tipo numérico
      exacto. `downgrade()` completo.
- [ ] **Paso 11 — La aserción de columnas.** Crecer
      `untangle/tenancy/rls_assertion.py` (archivo de U2): una segunda consulta
      al catálogo por las columnas de las tablas excluidas, su modelo, y el
      cambio en `evaluate()` para que una tabla excluida pase de saltada a
      comprobada de otra manera. La lista versionada de nombres de dato personal
      va al manifiesto, al lado de la lista de exclusión que paga.
- [ ] **Paso 12 — El repositorio.**
      `untangle/telemetry/spend/repository.py`: la transacción de dos sentencias
      —inserto de la fila y actualización condicional que devuelve el acumulado
      nuevo—, las lecturas por clave, la consulta de cuota, y las cuatro
      agregaciones del reporte. Todo por el punto único de sesión de U2; ningún
      import directo del driver.
- [ ] **Paso 13 — Pruebas del esquema y del repositorio.** Contra base efímera:
      que la aserción de aislamiento pase con las tres exclusiones escritas; que
      la aserción de columnas falle ante una tabla excluida con `visitor_email`;
      que dos escrituras simultáneas no pasen el techo las dos; que el fallo de
      la segunda sentencia revierta la primera; que borrar un caso deje la
      columna en nulo y la fila viva; que la ventana sobreviva al purgador y al
      cambio de mes con reloj inyectado.

### Bloque D — Trazas

- [ ] **Paso 14 — El ayudante de tramos.**
      `untangle/telemetry/traces/api.py`: `span()` con **lista cerrada** de
      nombres de atributo que el comprobador de tipos exige, los tres niveles
      anidados, el identificador de correlación por contexto, y el resumen de
      traza con sus tres estados y su plazo de diez segundos.
      `untangle/telemetry/traces/export.py`: exportación por lotes, al backend
      cuando hay destino y al archivo cuando no, **siempre por la redacción**.
- [ ] **Paso 15 — Pruebas de las trazas.** Que un turno sembrado con los cuatro
      tipos de dato personal no deje ninguno en ningún atributo de ningún tramo;
      que un nombre de atributo fuera de la lista no compile (prueba de tipos);
      que el resumen pase a `lost` a los diez segundos; que pedirlo con otra
      clave de navegador responda igual que si no existiera; que la caída del
      backend no detenga el gasto ni el corte.

### Bloque E — Proveedores

- [ ] **Paso 16 — Los puertos y la fábrica.** `untangle/providers/ports.py` con
      los cuatro `Protocol`, `GenerationResult`, `UsageReport`, `PromptRef`, la
      taxonomía cerrada de errores y la señal de parada.
      `untangle/providers/factory.py`: un cliente por uso, con su clave y su
      proyecto, construido en un único sitio.
- [ ] **Paso 17 — El adaptador de Gemini.**
      `untangle/providers/adapters/gemini/`: la petición con la instrucción de
      sistema **separada** del contenido externo —nunca concatenadas—, la salida
      estructurada validada dentro, la traducción de los cuatro errores, el
      cortacircuitos por proveedor y uso, y el reporte de uso hacia la
      contabilidad y el tramo hacia las trazas.
- [ ] **Paso 18 — Pruebas del adaptador.** Con `respx`, sin clave y sin costo:
      los cuatro tipos de error y que no salga un quinto; que ante saldo agotado
      no haya reintento; que el adaptador llame exactamente una vez ante
      `rate_limited`; que un fallo de validación sea `invalid_response`; que el
      circuito abra a los cinco fallos y no ante `invalid_response`; y que el
      texto sembrado con una instrucción inyectada quede en la parte de
      contenido y **no** en la instrucción de sistema.

### Bloque F — Superficie, composición y cierre

- [ ] **Paso 19 — La superficie del gasto.**
      `untangle/telemetry/spend/api.py` con las cuatro operaciones de C-17
      —`record_spend`, `budget_state`, `check_quota`, `reserve_primary_voice`—,
      la cola acotada de lo no facturable que pasa a síncrona al llenarse, y el
      tiempo máximo de sentencia que hace el fallo cerrado.
      `untangle/telemetry/spend/purge.py` con el contrato de borrado de C-11.
- [ ] **Paso 20 — Pruebas de la superficie.** Que lo facturable se escriba
      síncrono y lo no facturable no esté en el camino de la respuesta; que con
      la base caída la llamada facturable se rechace y el chat siga; que el
      purgador borre los contadores de visitante y no el del sitio ni la ventana;
      que la cola llena escriba síncrono en vez de descartar.
- [ ] **Paso 21 — Los cuatro contratos de importación.** En
      `app/backend/.importlinter`: SDK de proveedor solo en `adapters`, SDK de
      trazas solo en `telemetry.traces`, la contabilidad no importa las trazas, y
      las capas internas de `telemetry`.
- [ ] **Paso 22 — La raíz de composición y las tareas.** Los cuatro clientes por
      uso, el cifrador de precios, el purgador en su tupla; las tres variables en
      `.env.example` (nombres, nunca valores); `test:u5` y `spend:report` en
      `mise.toml`; las cinco dependencias en el manifiesto con su razón y su
      licencia.
- [ ] **Paso 23 — Las claves del catálogo de textos.** El mensaje de corte de la
      voz, los cuatro motivos de rechazo de cuota y el estado "registrándose", en
      los dos idiomas.
- [ ] **Paso 24 — Verificación y cierre.** Correr el guion completo; escribir
      `source-manifest.json` con cada archivo que la unidad creó o modificó,
      `code-summary.md` y `traceability.json`.

## Lo que este plan deja fuera a propósito

| Qué | Por qué |
| --- | --- |
| Las grabaciones de `vcrpy` para el adaptador | Grabar una respuesta real exige una clave y un poco de cuota. Las pruebas del paso 18 usan `respx`, que no necesita ninguna de las dos. La grabación se hace la primera vez que haya clave, y esa prueba corre por hito, no en cada entrega |
| La transcripción y la síntesis | Son de U15 `speech-providers`, que implementa los dos `Protocol` que este paso 16 ya declara |
| Las pantallas de gasto y de cifras | Son de U22 `public-evidence`; esta unidad entrega los datos |
| La medición sobre DS-5 | Corre por hito y pertenece a U16 y U21; DS-5 no está construido |
| El canal de la alerta | Lo fija el intent `infra` (PA-10); aquí se emite el evento y se escribe la marca |

## Riesgos de este plan, dichos antes

- **El paso 11 toca un archivo de U2 y el paso 2 uno de U1.** No es un préstamo
  inocente: `rls_assertion.py` sostiene el aislamiento del proyecto entero. El
  cambio es aditivo —una consulta más y una rama más en la evaluación— y sus
  pruebas propias de U2 tienen que seguir verdes; si alguna se pone roja, el
  cambio está mal hecho, no la prueba.
- **Tres dependencias nuevas de runtime.** Cada una con su razón de una línea y
  su licencia, y la auditoría del paso 24 las mira. Si alguna trae un aviso
  conocido, se fija la versión que lo cierra en vez de escribir una excepción,
  como se hizo con `cryptography` y con `starlette`.
- **El adaptador no se puede probar contra el proveedor real en esta entrega.**
  Queda declarado arriba, no escondido: lo que corre es inyección de errores.

## Contrato de pruebas

El bloque que sigue es la salida literal de `aidlc engine testing-posture
render`, sin tocar.

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
