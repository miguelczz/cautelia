# Plan de generación de código — U4 `case-record`

Treinta y seis pasos en nueve bloques. Cada bloque cierra con sus pruebas
corriendo, porque el contrato de pruebas recorre capa por capa y exige que la
prueba de una capa pase antes de empezar la siguiente.

## La rama de pruebas de esta unidad, y una precisión honesta

La ficha de U4 la clasifica en la **rama evaluada**: realiza M1, y sus casos
previos serían de DS-2 con el estado y la resolución finales en el registro
esperado.

**Esos casos no existen todavía.** DS-2 está declarado `built: false` en el
manifiesto de conjuntos, y no hay ningún subconjunto declarado para él: hoy solo
existen `smoke`, `rt14` y `rt4-live`. El corpus y sus conversaciones los genera
U7 `synthetic-data`, que llega después.

Es exactamente la situación que el proyecto ya resolvió una vez, en U1: *"la
primera unidad de la rama evaluada que realiza M8 sin conducta propia no tiene
casos existentes que correr: se construye con la rama determinista y su caso
previo es la primera corrida de los casos que escriban las unidades
siguientes"*. Aquí se aplica el mismo criterio con la misma forma:

- **U4 se construye por la rama determinista**, capa por capa en el orden del
  contrato: modelo de datos, repositorio, lógica de negocio, superficie.
- **Su caso previo de la rama evaluada queda declarado y sin inventar.** No se
  fabrica un caso de DS-2 artificial para cumplir la forma. Los dos objetivos de
  U4 que se miden sobre DS-2 —que el 100 % de los casos completos termine
  cerrado o derivado, y que el estado y la resolución finales coincidan con el
  registro esperado— ya están declarados en `nfr-requirements` con su comando y
  reportados como **"no medida"** con su causa, que es lo que la práctica
  afirmada exige y lo contrario de cerrarlos con `N/A`.
- **Lo que U4 sí puede sembrar hoy, lo siembra**: fixtures de caso en cada
  estado, con su estado y su resolución esperados, que son datos versionados con
  identificador estable y que las pruebas deterministas de esta unidad corren.
  Cuando DS-2 exista, esas mismas expectativas se leen desde allí sin traducir.

## Traza de historia a paso

| Historia | Qué exige | Pasos |
| --- | --- | --- |
| US4.10 — el caso cambia de estado solo por las transiciones declaradas | Modelo cerrado de siete estados, tabla versionada de doce transiciones, rechazo con evento, resolución de conjunto cerrado, completitud por tipo, origen del caso | 1–4, 13–18 |
| US1.8 — registrar a las demás personas y vehículos | Grupos repetibles con rol, datos pendientes sin adivinar, "ninguno" explícito solo si se dijo | 3, 5, 15, 21–24 |
| US1.14 — cerrar el reporte con número de caso | Número legible con prefijo de tres letras y seis dígitos, único e inmutable | 6, 16, 25–26 |
| Contrato C-12 | Las seis operaciones de la superficie, con el tipo redactado en la transcripción | 25–28 |
| Contrato C-11 | El purgador de datos de visitante y su registro explícito | 29–31 |
| PA-8 y el diseño de seguridad | Tipo sellado, punto único de cifrado, clave del entorno, identificador de clave por fila | 9–12 |

## Bloque 1 — Esquema versionado y modelo de datos

- [ ] **Paso 1.** Crear `app/backend/src/untangle/case_record/schema/fields.yaml`: los campos declarados por tipo de registro. Siniestro con sus siete campos centrales (`identity_and_policy`, `incident_datetime`, `location`, `description`, `vehicle_and_driver`, `other_parties`, `injuries`), consulta de cobertura con sus dos (`identity_and_policy`, `question_asked`), solicitud de cotización sin campos declarados. Cada campo declara si exige lectura de confirmación.
- [ ] **Paso 2.** Crear `app/backend/src/untangle/case_record/schema/transitions.yaml`: las doce filas T1–T12 con su estado de origen, su destino y su condición. La única con condiciones compuestas es T12.
- [ ] **Paso 3.** Crear `app/backend/src/untangle/case_record/models.py`: las cinco entidades, los enums cerrados (estado, resolución, tipo de registro, motivo de derivación, canal, origen, prioridad, rol de parte, tipo de actor, tipo de cambio, estado de campo, estado de adjunto) y los siete objetos de valor. No importa nada del módulo.
- [ ] **Paso 4.** Generar los JSON Schema de los dos archivos versionados con `mise run contracts:gen`, y comprobar que `mise run schema:check` los valida.
- [ ] **Paso 5.** Escribir y correr las pruebas de esta capa: que el esquema del siniestro declare exactamente sus siete campos, que el de la consulta declare dos, que un tipo sin campos no se pueda usar para crear, que los enums rechacen un valor fuera de su conjunto, y que la tabla de transiciones cargue las doce filas y ninguna más.

## Bloque 2 — El número de caso

- [ ] **Paso 6.** Añadir `case_number_prefix` a las tres carpetas de configuración de aseguradora (`STO`, `SUN`, `KNO`) y a su validación de configuración, de modo que un prefijo ausente o repetido haga fallar el arranque.
- [ ] **Paso 7.** Implementar la generación del número en `case_record/numbering.py`: prefijo de tres letras de la aseguradora, guion, seis dígitos con ceros a la izquierda, único dentro de la aseguradora.
- [ ] **Paso 8.** Escribir y correr sus pruebas: la forma del número, la unicidad dentro de la aseguradora, que dos aseguradoras con el mismo prefijo hagan fallar el arranque, y que el número no se pueda cambiar después de creado.

## Bloque 3 — El cifrado

- [ ] **Paso 9.** Crear `app/backend/src/untangle/case_record/crypto.py`: el tipo sellado con su constructor privado, `seal` y `unseal`, la lectura de la clave desde la variable de entorno, el identificador de clave, y el fallo cerrado al arrancar si la clave falta o no tiene la forma esperada.
- [ ] **Paso 10.** Añadir el nombre de la variable de la clave a `.env.example`, sin valor, y comprobar que `mise run env:check` pasa en las dos direcciones.
- [ ] **Paso 11.** Crear `app/backend/src/untangle/workspace/case_constructor.py`: el análisis estático que falla si alguien fabrica un valor sellado fuera de `crypto.py`, con `cast`, con una anotación más `type: ignore` o llamando al constructor. Es hermano del que U3 instaló para el tipo redactado.
- [ ] **Paso 12.** Escribir y correr las pruebas del cifrado: que el valor sellado no contenga el original ni por fragmentos, que descifrar devuelva el original, que una clave equivocada produzca el valor no disponible y no una excepción que tumbe la lectura, que el identificador de clave viaje con la fila, y que el análisis estático falle ante cada una de las tres formas de saltarse el punto único.

## Bloque 4 — La migración

- [ ] **Paso 13.** Crear la revisión de Alembic con las cinco tablas —caso, campo, parte, turno de transcripción y cambio—, cada una con su columna de aseguradora, `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY` y su política `tenant_isolation` que lee `app.tenant_id`, todo en la misma revisión que crea la tabla.
- [ ] **Paso 14.** Añadir el comentario con la marca `visitor-data` a las cinco tablas en esa misma revisión, y escribir su `downgrade()` completo.
- [ ] **Paso 15.** Correr `mise run migrate:check` y `mise run rls:check` y comprobar que las dos pasan: la primera sube, baja y vuelve a subir contra una base efímera; la segunda interroga al catálogo vivo.

## Bloque 5 — La lógica de negocio

- [ ] **Paso 16.** Implementar en `case_record/rules.py` el ejecutor de transiciones: busca la pareja en la tabla versionada, rechaza lo que no esté dejando su entrada, y evalúa las cuatro condiciones de T12 con el reloj inyectado.
- [ ] **Paso 17.** Implementar el cálculo de completitud: un campo cuenta cuando alcanza el estado que su propio campo exige, y el denominador sale del tipo de registro del caso.
- [ ] **Paso 18.** Implementar la evidencia por campo: exactamente una de las dos —turno o entrada de historial— cuando el estado no es "no dicho", y ninguna cuando lo es.
- [ ] **Paso 19.** Implementar la validación de cierre: resolución del conjunto cerrado y los cinco adjuntos, distinguiendo vacío de no evaluado.
- [ ] **Paso 20.** Escribir y correr las pruebas de esta capa, incluidas las dos del reloj inyectado en 14:59 y 15:01 que exige la decisión de arquitectura, y una prueba de propiedad que compruebe que ninguna secuencia de transiciones llega a un estado ilegal.

## Bloque 6 — Las partes y la transcripción

- [ ] **Paso 21.** Implementar el registro de partes con su rol y sus atributos opcionales, sin rellenar ninguno con un valor supuesto.
- [ ] **Paso 22.** Implementar el estado y la evidencia de confirmación de la placa del otro vehículo.
- [ ] **Paso 23.** Implementar el anexado de turnos exigiendo el tipo redactado de U3 en la firma, y llamando a la redacción antes de persistir.
- [ ] **Paso 24.** Escribir y correr sus pruebas: cuatro partes que se recuperan íntegras, una placa pendiente que no cuenta como completa, "ninguno" explícito que sí cuenta, y un turno sin redactar que no compila.

## Bloque 7 — Persistencia y superficie

- [ ] **Paso 25.** Implementar `case_record/repository.py`: toda consulta por el punto único de sesión de U2, sin abrir conexión propia, cifrando por `crypto.py` antes de escribir y descifrando al leer.
- [ ] **Paso 26.** Implementar `case_record/history.py`: el historial de solo anexar, con las cuatro clases de entrada, incluidos los rechazos.
- [ ] **Paso 27.** Implementar `case_record/api.py`: las seis operaciones que declara el contrato C-12, con sus tipos congelados.
- [ ] **Paso 28.** Escribir y correr sus pruebas: que un caso de otra aseguradora responda igual que uno inexistente, que el historial no exponga edición ni borrado, que cada operación de la superficie devuelva lo que el contrato declara, y que la regla de importación falle ante una conexión plantada.

## Bloque 8 — El borrado

- [ ] **Paso 29.** Implementar `case_record/purge.py` contra el contrato de purgador de U2, borrando el caso completo en cascada.
- [ ] **Paso 30.** Añadir el purgador a la tupla explícita de la raíz de composición.
- [ ] **Paso 31.** Escribir y correr sus pruebas: un caso público sembrado con las cinco tablas pobladas que desaparece entero, un caso local que se conserva, y la prueba de U2 que interroga al catálogo y ya no encuentra ninguna tabla marcada sin purgador.

## Bloque 9 — Tubería, textos y cierre

- [ ] **Paso 32.** Añadir a `mise.toml` las tres tareas: `test:u4`, `case:constructor` y `case:transitions`.
- [ ] **Paso 33.** Implementar `case:transitions`: regenera el diagrama del ciclo de vida desde la tabla versionada y falla si no coincide con el escrito.
- [ ] **Paso 34.** Encadenar `case:constructor` y `case:transitions` dentro de la línea del paso 6 de `scripts/verify.sh`, sin añadir pasos.
- [ ] **Paso 35.** Añadir las claves del catálogo de textos en los dos idiomas: los siete estados, las cuatro resoluciones, los tres tipos de registro, los tres motivos de derivación y la marca del campo no disponible. Y añadir la fila del módulo crítico a `[tool.untangle.coverage]`.
- [ ] **Paso 36.** Escribir `code-summary.md`, `source-manifest.json` y `traceability.json`, y correr `scripts/verify.sh` entero comprobando que los nueve pasos quedan en verde y que `mise run cov` alcanza el 80 % agregado y el 80 % del módulo.

## Cómo se comprueba que el plan se cumplió

| Obligación | Comando |
| --- | --- |
| Las pruebas de la unidad pasan | `mise run test:u4` |
| El piso del módulo y el agregado se alcanzan | `mise run cov` |
| Cada tabla nueva tiene aislamiento y política | `mise run rls:check` |
| La migración sube, baja y vuelve a subir | `mise run migrate:check` |
| Nadie fabrica un valor sellado fuera de su punto único | `mise run case:constructor` |
| El diagrama del ciclo de vida no se desvía de la tabla | `mise run case:transitions` |
| Los archivos versionados son válidos y los contratos no derivaron | `mise run schema:check` y `mise run contracts:check` |
| La variable de la clave está declarada y se lee | `mise run env:check` |
| La compuerta entera | `scripts/verify.sh` |
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
