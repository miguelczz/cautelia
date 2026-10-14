# Plan de generación de código — U2 `tenancy`

La segunda unidad, y la primera con tablas. Construye el aislamiento entre
aseguradoras, la identidad del personal de la bandeja y el acceso del visitante
por enlace firmado.

**Fuentes consumidas.** Los artefactos de diseño de U2
(`functional-design/`, `nfr-requirements/`, `nfr-design/`,
`infrastructure-design/`), los tres archivos `correcciones-tras-revision.md` que
rigen donde contradigan a sus documentos congelados,
`../../../inception/units-generation/unit-of-work.md`,
`../../../inception/contract-design/contract-summary.md` (C-07, C-10, C-11,
C-25, C-30) y `../../../inception/requirements-analysis/requirements.md`.

## Qué rama de pruebas le toca a esta unidad

U2 está en la **rama evaluada**: realiza M9. El contrato de pruebas exige que
sus casos previos se escriban, se corran y **se compruebe que fallan** antes de
implementar nada. Sus casos previos, que `unit-of-work.md` nombra, son:

- **DS-8**, las fixtures de aislamiento con colisiones a propósito entre
  aseguradoras.
- **DS-6 / RT-4**, el escenario adversarial de acceso a un caso o póliza ajena,
  con al menos un criterio verificable en el canal de texto.

Y como unidad de la rama evaluada, usa **además** la rama determinista para las
capas que la sostienen, en el orden que fija el contrato: modelo de datos y
conducta de la base, repositorio y acceso a datos, lógica de negocio, y
endpoint. La capa de interfaz no aplica: U2 es de tipo `library` y las pantallas
que consumen sus contratos son de U14 y U6.

## Decisiones de esta etapa

| ID | Decisión | Por qué |
| --- | --- | --- |
| CG-U2-1 | La capa de endpoint no se construye en U2 | El contrato C-07 reparte el enlace firmado: U2 es dueña del token, U14 de la ruta que lo canjea. U2 expone el canje como función del módulo, no como ruta HTTP |
| CG-U2-2 | Las tres carpetas de aseguradora se crean completas en esta unidad, con datos mínimos válidos | FR9.3 exige que añadir una cuarta sea añadir una carpeta; eso no se puede probar con una sola carpeta. El corpus y las pólizas de ejemplo los llena U7 |
| CG-U2-3 | Las tablas de U2 son dos, y ninguna guarda datos de personas | `entities.md` deja `Tenant`, `StaffPrincipal` y `RolePermission` en configuración versionada. Solo `CaseAccessLink` y `VisitorKey` necesitan poder revocarse y borrarse cada noche |

## Bloque A — Los casos previos, antes de implementar nada

- [x] **Paso 1.** Comprobar que el runner de pruebas y el corredor de
      evaluaciones que dejó U1 son ejecutables, y registrar el comando acotado a
      U2 en `unit-test-instructions.md`. El contrato exige runner listo antes del
      primer caso.
- [x] **Paso 2.** Escribir las fixtures de **DS-8** en
      `app/data/fixtures/ds8_isolation.json`: dos aseguradoras con el mismo
      número de póliza y el mismo nombre de asegurado, a propósito, más un caso
      por aseguradora.
- [x] **Paso 3.** Escribir el caso de **DS-6 / RT-4** en
      `app/evals/cases/ds6/rt4/` con su identificador estable, en los dos
      idiomas, con su criterio de aceptación y su veredicto esperado: intentar
      abrir un caso ajeno no devuelve nada.
- [x] **Paso 4.** Escribir las pruebas de aislamiento que consumen DS-8 en
      `app/backend/tests/integration/u2/test_isolation.py`, **correrlas y
      registrar que fallan**. Sin base de datos ni sesión, deben fallar; si
      pasaran, la prueba no estaría probando nada.

## Bloque B — Modelo de datos y conducta de la base

- [x] **Paso 5.** Instalar Alembic con una sola cabeza y su configuración, y el
      rol del aplicativo **sin privilegio de salto** en el arranque de la base
      local y en la base efímera de pruebas.
- [x] **Paso 6.** Base efímera para pruebas con contenedores, con la misma
      imagen anclada por huella del entorno local, conectándose con el rol del
      aplicativo y **nunca** con el superusuario. Una sola por corrida de la
      suite.
- [x] **Paso 7.** Primera revisión de migración, `u2_tenancy_0001_tenancy_tables`:
      crea `case_access_link` y `visitor_key`, cada una con su columna de
      aseguradora, aislamiento habilitado, aislamiento forzado y su política
      **escritos literales en la misma revisión** (decisión Q1 del diseño de
      calidad), más su `downgrade()` que funciona.
- [x] **Paso 8.** `rls:check`: pregunta al catálogo vivo qué tablas hay en el
      esquema del aplicativo y exige las tres cosas de cada una; pregunta al rol
      vivo si puede saltarse las políticas y falla si puede. Lista de exclusión
      versionada con su razón por entrada.
- [x] **Paso 9.** `migrate:check`: sube, baja y vuelve a subir contra su propia
      base efímera; falla ante dos cabezas y ante una tabla creada sin su
      aislamiento.
- [x] **Paso 10.** Pruebas de esta capa: la aserción falla ante una tabla sin
      política, falla ante un rol con privilegio de salto, y pasa con el esquema
      correcto.

## Bloque C — Punto único de sesión

- [x] **Paso 11.** `tenancy/session.py`: `session_for(tenant_id)` que resuelve la
      aseguradora, **falla en el acto si no existe** (decisión Q5 del diseño
      funcional), abre transacción, fija la variable de sesión y cierra; más
      `current_tenant()`.
- [x] **Paso 12.** La variable de sesión se lee tolerando el valor vacío, de modo
      que sin aseguradora fijada las políticas no ven nada: falla cerrado, nunca
      abierto.
- [x] **Paso 13.** Contratos de importación en `app/backend/.importlinter`:
      (a) ningún módulo fuera de `tenancy` importa el cliente de base de datos ni
      el mapeador; (b) **contrato de capas interno** de `tenancy` con el orden
      `api` → piezas → `session` → `config`; (c) **contrato prohibido**: `evals`
      no importa la raíz de composición ni `tenancy.session`, que es lo que
      mantiene el camino del clon al reporte sin base de datos.
- [x] **Paso 14.** Pruebas de esta capa: una consulta sin filtro desde una sesión
      fijada devuelve solo lo suyo; sin aseguradora fijada devuelve cero filas;
      una aseguradora inexistente falla antes de abrir transacción.

## Bloque D — Configuración por aseguradora

- [x] **Paso 15.** `tenant.schema.json` y `ruleset.schema.json`, validados por
      `schema:check` como el resto de archivos versionados.
- [x] **Paso 16.** Las tres carpetas: `stonecroft`, `sunmeadow` y `knotwell`, con
      sus nombres, tipo, idioma, jurisdicción y personas de bandeja tal como los
      fija FR9.5 y FR9.6. Sin credenciales dentro.
- [x] **Paso 17.** `tenancy/config.py`: carga y valida cada carpeta por separado;
      una rota deja su aseguradora no disponible nombrando archivo y clave, y las
      demás siguen vivas.
- [x] **Paso 18.** `tenancy:literals`: busca identificadores de aseguradora
      literales fuera del cargador y de las fixtures.
- [x] **Paso 19.** Pruebas de esta capa: una carpeta rota no tumba a las otras
      dos; añadir una cuarta carpeta la deja disponible sin tocar código; el
      chequeo de literales encuentra uno plantado a propósito.

## Bloque E — Identidad del personal de la bandeja

- [x] **Paso 20.** `tenancy/staff_identity.py`: emisión de credencial con PyJWT,
      con aseguradora, persona, rol, emisión y caducidad a las **doce horas**.
- [x] **Paso 21.** La tabla de permisos versionada por rol y acción, con las
      cinco acciones que hoy nombran las historias; lo no declarado se deniega.
- [x] **Paso 22.** Verificación en cada petición: firma, caducidad, aseguradora y
      permiso. Las tres causas de credencial inválida devuelven una respuesta
      **idéntica byte a byte**.
- [x] **Paso 23.** El evento de rechazo con aseguradora intentada, rol afirmado y
      causa real, emitido por el punto único de salida.
- [x] **Paso 24.** Comando de emisión de credenciales, que escribe a la salida
      estándar y **nunca** a un archivo del repositorio.
- [x] **Paso 25.** Pruebas de esta capa: la credencial lleva los cuatro campos;
      una caducada, una alterada y una de otra aseguradora producen respuestas
      idénticas comparadas entre sí; el rol de agente de cuenta no decide; rotar
      la clave invalida en el acto lo firmado antes.

## Bloque F — Acceso del visitante

- [x] **Paso 26.** `tenancy/visitor_access.py`: emisión del enlace con vida de una
      hora hacia un solo caso, guardando **solo el resumen del token**; firma con
      la biblioteca estándar y **su propia clave**, distinta de la de la bandeja.
- [x] **Paso 27.** Canje: busca por resumen en tiempo constante, comprueba
      existencia, caducidad y revocación, sube el contador y entrega credencial
      con el tiempo que le quede al enlace. **Reutilizable** mientras valga.
- [x] **Paso 28.** Las cuatro causas de rechazo —inválido, caducado, revocado, de
      otro caso— responden exactamente igual, como un caso inexistente.
- [x] **Paso 29.** Clave del navegador con su aseguradora, sin ningún dato que
      identifique a una persona.
- [x] **Paso 30.** El `Protocol` del purgador, el registro **explícito** en la
      raíz de composición y los dos purgadores de U2; más la prueba que compara
      el registro contra las tablas con datos de visitante y falla si falta uno.
- [x] **Paso 31.** Pruebas de esta capa: el enlace se canjea dos veces dentro de
      su hora; a las dos horas responde como inexistente; las cuatro causas dan
      respuestas idénticas; una clave de navegador usada en dos aseguradoras
      tiene dos filas y ninguna ve la otra; el reinicio borra las dos tablas.

## Bloque G — Cierre y compuertas

- [x] **Paso 32.** Correr los casos previos del Bloque A y **comprobar que ahora
      pasan**. Es lo que cierra la rama evaluada.
- [x] **Paso 33.** `.env.example` gana las **dos** claves de firma por nombre, y
      `env:check` las compara contra lo que el código lee, en las dos
      direcciones.
- [x] **Paso 34.** Las tres tareas nuevas entran en el paso 6 del guion de
      verificación, junto a las cuatro que ya están. El guion sigue teniendo
      nueve pasos.
- [x] **Paso 35.** Cobertura: el agregado sigue en 80 % o más, y se enciende el
      piso por módulo crítico para `tenancy` (NFR18.2). El umbral **no se baja**;
      si no se alcanza, se escriben más pruebas.
- [x] **Paso 36.** Corrida completa de `scripts/verify.sh` con sus nueve pasos en
      verde, y medición del coste real que añaden las bases efímeras.

## Trazabilidad de pasos a historias

| Historia | Criterios | Pasos que los realizan |
| --- | --- | --- |
| US4.11 | AC4.11.1 | 7, 8, 9, 10 |
| US4.11 | AC4.11.2 | 11, 12, 13, 14 |
| US4.11 | AC4.11.3 | 2, 4, 14, 32 |
| US4.11 | AC4.11.4 | 34, 36 |
| US4.11 | AC4.11.5 | 3, 32 |
| US5.7 | AC5.7.1 | 20, 22, 25 |
| US5.7 | AC5.7.2 | 22, 25 |
| US5.7 | AC5.7.3 | 21, 25 |
| US5.7 | AC5.7.4 | 24, 26, 33 |

## Lo que este plan no construye

- Las pantallas de la bandeja y la vista del caso del visitante (U14, U6).
- La ruta HTTP que canjea el enlace (U14, por el reparto de C-07).
- El reinicio nocturno que llama a los purgadores (U20).
- El corpus y las pólizas de ejemplo de cada aseguradora (U7).
- El aislamiento de las tablas de puntos de control del grafo (U12).

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
