**Collaborator:** aidlc-quality-agent

## Contribution

Reviso el borrador desde la posture de pruebas y la calidad verificable. Dejo
estilo, capas y manejo de errores a otros; dejo lint, SAST, secretos y cadena de
suministro a otros. El borrador es sólido en lo que declara: la línea base cero
está bien establecida, las compuertas duras están bien extraídas del PRD 11.2 y
la separación entre "establece" y "sugiere" de `evidence.md` es honesta. Lo que
sigue es lo que falta, lo que está mal medido y lo que la entrevista todavía no
pregunta.

Ordené los hallazgos por consecuencia: primero los tres que rompen algo de forma
mecánica, después los vacíos de contenido, y al final los cambios concretos a las
preguntas.

---

### 1. El `Ordering` propuesto no es implementable tal como está escrito

Esta era la pregunta central del encargo y la respuesta es **no**, por dos
razones separadas: una mecánica y una de contenido.

**La mecánica.** Elegir `custom` no es neutro. El resolutor determinista que
Code Generation consume (`.claude/tools/aidlc-testing-posture.ts`,
`buildPlanProfile`) construye el plan de pruebas de forma distinta según la
metodología. Para `tdd` y para `test-after` expande un paso por cada capa de la
lista fija `TESTABLE_LAYERS` (`Data model / database behavior`,
`Repository / data access`, `Business logic`, `API / endpoint`,
`Frontend behavior`). Para `custom` **no expande nada**: emite exactamente dos
pasos, y el primero es la cadena literal del campo `- **Ordering**:`.

```
"Custom ordering - <el texto literal del campo Ordering>",
"Implementation and tests - preserve that exact ordering; do not convert it to layer-local TDD."
```

Es decir: **con `custom`, la frase de `Ordering` ES el plan de pruebas completo.**
El andamiaje por capas que el engine regalaría con `test-after` desaparece. Todo
lo que la frase no diga, nadie lo dirá. Esto no es teoría: el contrato se
serializa en `## Testing Contract` dentro de `code-generation-plan.md`, se
fingerprintea y se aprueba; lo que no esté en la frase no llega al generador de
código como paso del plan.

Dos consecuencias operativas que el lead debe conocer antes de integrar:

- El campo se parsea con `structuredField`, cuyo regex captura `(.+?)$` sobre
  **una sola línea**. Si en la integración la frase se convierte en una lista de
  viñetas o en un párrafo multilínea, **solo sobrevive la primera línea** y el
  resto se pierde en silencio. `Ordering` debe quedar en una línea, por larga que
  sea.
- `compatibleSpecialization` compara la capa `team` contra la capa `project`. Si
  `team.md` queda en `custom`, cualquier `## Testing Posture` que en el futuro se
  escriba en `project.md` y **no** sea también `custom` lanza un error duro
  (`Testing Posture conflict`) y detiene la resolución. Conviene dejarlo escrito
  en `evidence.md` como consecuencia de la elección, para que nadie añada una
  especialización de proyecto sin saberlo.

**El contenido.** Aun sin el problema mecánico, la frase actual no es decidible.
Leo la línea 72 del borrador y anoto dónde un desarrollador (o un agente) se
detiene a preguntar:

> "para cada comportamiento que el PRD mide con evals, primero se escribe o se
> extiende su caso de golden set y su criterio de aceptación; después se implementa
> la capa; después se escriben y corren sus pruebas unitarias y de integración; y
> antes del merge corre la suite determinista completa más los golden sets de texto."

- *"comportamiento que el PRD mide con evals"* — no hay prueba de pertenencia. No
  se puede decidir, mirando una unit, si cae dentro o fuera. Reaparece como
  discusión en cada pieza de trabajo, que es exactamente lo que el encargo pide
  evitar.
- *"o se extiende"* — deja la decisión abierta sin criterio.
- *"después se implementa la capa"* — el sujeto cambia de "comportamiento" a
  "capa" sin definir el mapeo. ¿Qué capa? ¿Todas? ¿En qué orden?
- *"sus pruebas unitarias y de integración"* — ¿de qué capas?
- **Lo que no dice es lo más grave: no dice nada del código que NO mide un eval.**
  Los adaptadores de proveedor, los repositorios, las migraciones, la bandeja, el
  chat: la mayoría del código del aplicativo no tiene golden set. Para ese código
  la frase calla, y como `custom` borró las capas del engine, no queda ninguna
  regla de respaldo. El resultado práctico es que la mitad del código se escribe
  sin orden afirmado.
- La última cláusula (*"antes del merge corre la suite completa"*) no es orden de
  trabajo, es una compuerta de integración. Mezclarla dentro de `Ordering` hace
  que el paso del plan de una unit incluya una obligación de merge. Debe salir del
  campo y quedarse en la prosa, donde ya está.

**Redacción concreta propuesta.** Sustituir la línea 72 completa por esta, en una
sola línea, con las dos ramas decidibles y exhaustivas:

> `- **Ordering**: Clasifica cada unidad en una de dos ramas y no dejes ninguna sin rama. Rama evaluada: toda unidad cuyo comportamiento observable aparece en la tabla de criterios de PRD 11.2 o realiza uno de M1, M4, M5, M6, M8, M9, M13, M15; para ella se escribe o se extiende primero su caso de golden set (DS-2, DS-3, DS-5, DS-6) con su identificador estable, su criterio de aceptación y su veredicto esperado, se corre y se comprueba que falla, se implementa, y se vuelve a correr hasta que pase. Rama determinista: toda unidad restante, recorrida capa por capa en el orden Data model / database behavior, Repository / data access, Business logic, API / endpoint, Frontend behavior; se implementa la capa y a continuación se escriben y corren las pruebas de esa capa antes de pasar a la siguiente. Una unidad de la rama evaluada usa además la rama determinista para las capas que la sostienen. El corredor de pruebas y el corredor de evals se dejan ejecutables antes del primer caso de cualquiera de las dos ramas.`

Por qué así: la prueba de pertenencia a la rama evaluada es una lista cerrada
(una tabla del PRD y ocho Must), verificable sin juicio; la rama determinista es
exhaustiva por construcción ("toda unidad restante"); los nombres de las capas
se escriben igual que en `TESTABLE_LAYERS` para que el plan no cambie de
vocabulario a mitad; y la última cláusula reinstala explícitamente lo que el
engine ya afirma en el contrato como `runner_ready_before_first_test: true`, que
con `custom` deja de aparecer en los pasos.

---

### 2. `Project Type: Brownfield` hace que el plan diga "verifica el runner existente" cuando no existe ninguno

`buildPlanProfile` elige el paso de runner por tipo de proyecto:

- `greenfield` → `"Bootstrap the minimal test runner/configuration and record the exact unit-scoped command."`
- `brownfield` → `"Verify the existing test runner/configuration and record the exact unit-scoped command."`

`aidlc-state.md` declara `- **Project Type**: Brownfield`, así que **todas las
units de Construcción recibirán el paso "verifica el runner existente"**. No hay
runner existente: `code-quality-assessment.md` lo establece con cero ambigüedad, y
TD-08 ya avisó que Brownfield es correcto solo para `site/` y que el aplicativo es
greenfield. El primer Bolt va a recibir un paso de plan que describe una
verificación imposible en vez de un bootstrap.

No propongo cambiar el `Project Type` desde esta etapa: se fijó en
`reverse-engineering` y ya está aprobado. Propongo **compensarlo en la prosa**,
que es el canal que sí llega: todo el cuerpo visible de `## Testing Posture` viaja
a Code Generation como `applicable_notes`. Añadir a `## Testing Posture`:

> **Punto de partida.** No existe ningún runner de pruebas, ninguna configuración
> de cobertura y ningún corredor de evals: la línea base es cero. El flujo declara
> `Project Type: Brownfield` porque la landing existe, pero el aplicativo es
> greenfield y su andamiaje se crea, no se verifica. El primer Bolt que toque
> código de aplicación deja instalados y ejecutables, antes de su primera prueba,
> el runner del lenguaje, la configuración de cobertura y el corredor de evals de
> un solo comando (M17), y registra ese comando exacto en el README.

---

### 3. El scope `classic` no activa el piso del 80 % en el contrato determinista

Este es un hallazgo mecánico que contradice una afirmación del borrador.
`combineTestObligations` decide el `scope_floor` con una lista literal:

```
if (["mvp", "enterprise", "feature", "infra"].includes(normalizedScope)) {
  scopeFloor = ["Meet an 80% line-coverage floor.", "Run the selected tests in CI before merge."];
}
```

**`classic` no está en esa lista.** El scope cae en el `else` y el contrato emite:

```
scopeFloor = ["Keep the existing test suite green.",
              "This scope adds no extra new-test floor beyond the selected test strategy."]
```

La prosa de `org.md` sí nombra `classic` entre los scopes con piso del 80 %, pero
la herramienta que Code Generation consume no. No hay alias de `classic` a
`feature` en el tooling (lo verifiqué). Conclusión: **el piso del 80 % llega a
Construcción únicamente como prosa de `## Testing Posture`, no como obligación del
contrato.**

Esto no invalida el piso, pero sí cambia qué hay que escribir. La línea 86-91 del
borrador justifica el piso citando `org.md` ("es el piso que el scope `classic`
fija en `org.md`"), y esa justificación es la que no se sostiene mecánicamente. Hay
que escribirlo como obligación propia, medible y con su comando, no como cita.
Redacción propuesta para reemplazar el párrafo de "Piso de cobertura":

> **Piso de cobertura.** 80 % de líneas sobre el código del aplicativo, con piso
> del 80 % también en los módulos críticos (motor de reglas, verificador de citas,
> aislamiento por tenant, esquema del caso). La medición se hace con la herramienta
> de cobertura del lenguaje elegido, con un umbral configurado en el manifiesto que
> haga fallar el comando cuando no se alcanza, y ese comando es el mismo que corre
> `build-and-test`. Se excluyen del cálculo, mediante una lista de exclusión
> versionada en la configuración: la landing (`site/`, fuera del alcance por D-005 y
> D-013), el corpus y los datasets generados, y las migraciones. El piso no se baja
> para que un paso pase.

La lista de exclusión importa: MOD-12 genera corpus, endosos y fixtures. Si ese
material entra en el denominador, el número de cobertura deja de significar nada y
la conversación de Q4 (agregado o por paquete) se vuelve irrelevante frente a un
denominador que nadie controla.

---

### 4. Ninguna compuerta descrita tiene un ejecutor dentro de este intent

Las tres frases "en CI antes del merge" del borrador no tienen dónde correr
durante todo este intent. `aidlc-state.md` lista `3.7 (ci-pipeline)` en
**Stages to Skip** y toda la fase OPERATION también. D-014 manda CI al intent
`infra`. La única etapa que ejecuta verificación aquí es `build-and-test` (3.6).

Una práctica cuyo único ejecutor nombrado no existe durante el intent completo es
una práctica que se erosiona en la semana 1. Hay que nombrar el ejecutor local y
la fecha en que se traslada. Propuesta para `## Testing Posture`:

> **Dónde corre la compuerta.** Mientras el intent `infra` no exista (D-014,
> semanas 3 y 4), el ejecutor de todas las compuertas de esta sección es la etapa
> `build-and-test` corriendo en local con un solo comando, más el mismo comando
> ejecutado a mano antes de cada merge a `main`. El comando es idéntico al que el
> intent `infra` montará en CI: las prácticas no cambian cuando cambia el ejecutor,
> solo cambia quién lo dispara. Una compuerta que hoy no se puede ejecutar se
> declara "no medida" en el reporte, nunca se omite.

La frase final replica la regla del PRD 10 ("una métrica que no se midió se
publica como 'no medida', nunca se omite") y la extiende a las compuertas, que
es donde falta.

---

### 5. Las compuertas duras no llegarán a la matriz de verificación si no se escriben como NFR

`build-and-test` construye su `## Target Verification Matrix` a partir de un
inventario que lee exactamente tres fuentes: los artefactos de
`nfr-requirements/`, los de `nfr-design/`, y los bloques `## Testing Contract`
aprobados en `code-generation-plan.md`. **No lee `team.md`.**

Consecuencia: las compuertas `[bloquea]` del PRD 11.2 y los umbrales del Segmento
10 pueden estar perfectamente escritos en las prácticas y aun así **no aparecer
como filas de la matriz**, que es el único lugar donde reciben un `Expected`, un
`Actual`, una `Evidence` y un `Verdict`. La compuerta quedaría documentada y no
verificada.

Falta una regla en `## Mandated` que cierre ese salto. Propuesta:

> - ALWAYS registrar cada criterio `[bloquea]` de PRD 11.2 y cada umbral
>   cuantificado del Segmento 10 como un objetivo medible en `nfr-requirements`, con
>   identificador estable, valor esperado y el comando que produce su valor real, de
>   modo que aparezca como fila propia en la `## Target Verification Matrix` de
>   `build-and-test`; ningún criterio `[bloquea]` puede cerrarse con `N/A`.
>   *(PRD 11.2, Segmento 10; contrato de `build-and-test`)*

---

### 6. `Test Strategy: Standard` no genera instrucciones de seguridad ni de rendimiento

`build-and-test` genera instrucciones de prueba según la estrategia activa:
**Standard** produce solo `integration-test-instructions.md`.
`performance-test-instructions.md` y `security-test-instructions.md` son de
**Comprehensive** (y aun ahí, condicionadas a que existan NFR).

Pero las compuertas duras de este producto **son** de seguridad (PII en trazas,
aislamiento entre tenants, resistencia adversarial) y los umbrales publicables
**son** de rendimiento (latencia de turno p50 < 500 ms y p95 < 800 ms, latencia
de parada < 300 ms, corrida de evals ≤ 10 min). Con `Standard` por defecto, ninguna
de las dos familias recibe instrucciones.

No recomiendo subir a `Comprehensive`: eso impondría "diez a quince pruebas por
componente" a una persona con 90 días, y el costo cae donde no está el riesgo. La
salida barata y dirigida es afirmarlo como obligación en la prosa, que el propio
stage file admite ("These are soft guidelines"):

> **Tipos de prueba obligatorios pese a la estrategia.** La estrategia activa es
> `Standard` (cinco a ocho pruebas por componente; unitarias más integración en las
> fronteras). Además, y con independencia de la estrategia, `build-and-test` genera
> instrucciones de prueba de **seguridad** (aislamiento entre tenants, redacción de
> PII en cada punto de salida, casos adversariales de DS-6) y de **rendimiento**
> (latencias de turno y de parada sobre DS-5, duración de la corrida de evals),
> porque el PRD las marca como compuertas duras y como umbrales publicables, no
> como aspiraciones.

---

### 7. La regla de regresión de 2 puntos porcentuales se dispara con un solo caso

Es aritmética sobre los tamaños que el propio PRD fija, y es el hallazgo que con
más probabilidad mata este régimen de calidad en la práctica.

Las métricas se reportan **por idioma** (P12), así que el denominador es la mitad
del set:

| Dataset | Casos por idioma | Cuánto mueve **un** caso |
| --- | --- | --- |
| DS-2 (golden set de texto) | 30 | **3,3 pp** |
| DS-3 (citación) | 20 | **5,0 pp** |
| DS-6 (adversarial, v0) | 10 | **10,0 pp** |

El umbral es "caída mayor de 2 puntos porcentuales". En los tres sets, **un solo
caso que cambie de veredicto siempre supera el umbral**. Como la salida del LLM no
es determinista ni siquiera con el mismo prompt, eso significa que la regla, tal
como está escrita, exige una explicación escrita en el pull request en
prácticamente todas las corridas. Una persona sola, con fecha límite, va a
terminar apagando la compuerta o escribiendo explicaciones vacías, y ambas cosas
violan P5.

El PRD marca ese 2 pp como `[por defecto]`, así que ajustarlo es exactamente lo
que esta etapa debe proponer. La excepción legítima son las métricas con
denominador grande: "exactitud de extracción por campo" tiene siete campos por
caso (≈210 observaciones por idioma), donde 2 pp sí es una señal razonable.

Redacción propuesta para reemplazar el párrafo "Definición de regresión":

> **Definición de regresión.** Bloquea el merge: (a) cualquier compuerta dura en
> rojo, sin excepción ni promedio; (b) en métricas de denominador grande
> (extracción por campo, fidelidad de la lectura de confirmación, latencias) una
> caída mayor de 2 puntos porcentuales frente a la línea base versionada sin
> explicación escrita en el pull request; (c) en métricas de nivel de caso sobre
> DS-2, DS-3 y DS-6, donde el denominador por idioma es de 10 a 30 casos y un solo
> caso mueve entre 3 y 10 puntos, **más de un caso en regresión por idioma y por
> dataset** sin explicación escrita. La explicación nombra los identificadores de
> los casos que cambiaron y su causa raíz según la taxonomía del PRD 11.3; una
> explicación que no nombre casos no cuenta como explicación.

Y añadir, porque sin esto la regla anterior sigue midiendo ruido:

> **Determinismo de la corrida.** La corrida de evals fija todo lo que se pueda
> fijar: temperatura en 0 y semilla fija donde el proveedor lo permita, versión del
> modelo anclada por identificador exacto (nunca un alias móvil), prompts y rúbricas
> versionados en el repositorio, y el respondedor del asegurado por reglas indexado
> por campo del PRD 11.1. Cuando un caso siga siendo inestable entre corridas
> idénticas, se marca como inestable con su identificador en un archivo versionado,
> deja de contar para la compuerta, se reporta aparte con esa etiqueta, y su
> estabilización se abre como trabajo; nunca se borra del set (P5).

---

### 8. Vacíos de contenido que el borrador no cubre

Lo que sigue falta por completo en las tres artefactos. Lo ordeno por impacto.

**a. Estrategia de datos de prueba — ausente.** Es la omisión más grande para mi
rol. Ocho datasets sostienen todo el régimen y el borrador no dice cómo viven.
Sin esto, "línea base versionada" no tiene sustrato estable. Propuesta para
`## Testing Posture`:

> **Datos de prueba.** Los casos de los golden sets viven versionados en el
> repositorio como archivos de datos, un archivo por caso, con identificador estable
> (`DS-2/es/017`), nunca generados en tiempo de corrida. El generador sintético
> (MOD-12) es determinista y sembrado: su salida (corpus DS-1, fixtures DS-8) se
> regenera solo con un comando explícito y el resultado se commitea, de modo que dos
> corridas del mismo commit vean el mismo corpus. Los identificadores son la moneda
> de todo el sistema: el reporte por caso, el diff contra la línea base, la sección
> "Cómo falla" del README y los casos nacidos de un red-team o del muestreo del chat
> en vivo los usan sin traducción.

**b. Qué hace una prueba bien hecha — ausente.** El guardarraíl de
`phases/construction.md` prohíbe pruebas que siempre pasan y exige que sean
ejecutables sin montaje manual, pero el borrador no baja eso a regla de equipo:

> **Forma de las pruebas.** Cada prueba es independiente del orden de ejecución y
> de estado compartido, y se puede correr sola. Cada prueba afirma un
> comportamiento, no una implementación: se prueba lo que el requisito exige, no
> cómo se codificó. Ninguna prueba pasa con independencia de la implementación. Cada
> caso de red-team exitoso entra a DS-6 con el identificador `RT-<n>` en su nombre y
> no se cierra el hallazgo hasta que ese caso pase (PRD 11.4).

**c. Qué pasa cuando el juez se descalibra — sin definir.** El borrador dice que
los veredictos del juez solo cuentan tras alcanzar 85 % contra DS-7, pero no dice
qué ocurre con la compuerta cuando cae por debajo a mitad del proyecto. Sin esa
regla, una deriva del juez o bloquea todo o no bloquea nada, según quién la lea:

> **Juez descalibrado.** Si el juez cae por debajo del 85 % de coincidencia con las
> etiquetas humanas de DS-7, o si cambia el modelo del juez o la rúbrica sin
> recalibrar, sus veredictos dejan de contar: los criterios que dependen de él se
> reportan como "no medida" con esa causa, no bloquean el merge, y la recalibración
> se abre como trabajo con fecha. Las compuertas duras juzgadas por código (citas
> inexistentes, aislamiento, PII en trazas, esquema) no dependen del juez y siguen
> bloqueando.

**d. Presupuesto de tiempo de la corrida — declarado pero no protegido.** El
objetivo de ≤ 10 minutos corre sobre el tier gratuito del LLM con 120 casos
multi-turno. Los límites de tasa del tier gratuito no están medidos en ninguna
parte, y si la corrida no cabe en el presupuesto la reacción natural es apagar la
compuerta. Propuesta:

> **Presupuesto de la corrida.** La corrida de evals de texto tiene un objetivo de
> 10 minutos y su duración se mide y se publica como métrica desde la línea base v0
> (Segmento 10.5). El corredor admite ejecutar un subconjunto declarado y
> reproducible; si la corrida completa deja de caber en el presupuesto o en los
> límites del tier gratuito, la compuerta corre ese subconjunto declarado —nunca se
> apaga— y la corrida completa pasa a ser obligatoria por hito y antes de publicar
> cualquier línea base.

**e. Frontera, breve.** Los tres chequeos de contenido que el borrador pone en
`## Code Style` (frases prohibidas, ausencia de texto ISO/ACORD, paridad de claves
EN↔ES) protegen principios con compuerta dura (P6, P8, P12, R9), no estilo. Desde
la perspectiva de calidad rinden más como **casos de prueba deterministas con
identificador estable** dentro de la suite —así aparecen en el reporte por caso,
en el diff contra la línea base y en la matriz de verificación— que como reglas de
linter, que fallan sin caso y sin historia. Dejo la mecánica del linter a
devsecops; solo pido que, viva donde viva, cada uno tenga identificador y aparezca
en el reporte.

---

### 9. Cambios concretos a las preguntas de la entrevista

**Q3 — reescribir el enunciado y añadir una cuarta opción.** La pregunta actual
está bien planteada en lenguaje humano, pero no le dice a Miguel lo que su
respuesta cuesta. Añadir al enunciado, antes de las opciones:

> Tu respuesta se escribe en dos campos que el generador de código lee de forma
> literal. Si la cadencia es mixta, el campo dice `custom`, y entonces la frase de
> orden que escribamos **es** el plan de pruebas completo: el framework deja de
> aportar sus propios pasos por capa, así que todo lo que la frase no diga, nadie lo
> dirá.

Y añadir una cuarta opción, defendible y hoy ausente:

> - `D.` Acceptance-first: el caso de golden set es la prueba de aceptación de cada
>   feature y se escribe antes de implementarla; las pruebas unitarias del código
>   determinista se escriben dentro del paso de implementación. En el campo
>   `- **Methodology**:` eso se escribe `atdd`.

Merece estar porque `atdd` conserva un perfil de plan estructurado de cuatro
pasos que nombra las capas, mientras que `custom` colapsa a dos pasos genéricos.
El costo de `atdd` es que obliga a prueba de aceptación previa también donde no
hay golden set posible (una migración con RLS, el adaptador de Presidio).
**Mi recomendación sigue siendo `A` con `custom`**, porque es la descripción
honesta de la cadencia real, pero solo si la frase de `Ordering` se reescribe como
propongo en el punto 1. Con la frase actual, `D` sería preferible: un plan
estructurado imperfecto vence a una frase ambigua que se convirtió en el plan
entero.

**Q4 — añadir la parte que falta.** La pregunta cubre agregado frente a por
paquete, pero no cubre qué se excluye ni con qué herramienta se hace cumplir sin
CI, que es donde el número se rompe. Añadir al enunciado:

> Y una segunda parte: ¿qué queda fuera del cálculo? Propongo excluir la landing
> (ya está fuera de alcance), el corpus y los datasets que genera el generador
> sintético, y las migraciones; todo ello con una lista de exclusión versionada en
> la configuración, para que el número no dependa de cuánto material generado haya
> ese día.

**Nueva Q7 — el umbral de regresión (Testing Posture).** Es la consecuencia del
punto 7 y necesita decisión humana porque el PRD marca el 2 pp como `[por defecto]`:

> El plan dice que una caída de más de 2 puntos porcentuales frente a la medición
> anterior bloquea el merge. Con 30 casos por idioma, un solo caso que cambie ya
> mueve más de 3 puntos, así que esa regla se dispararía casi siempre, incluso
> cuando no se rompió nada. ¿Cómo prefieres contar una regresión?
>
> - `A.` Contar casos, no porcentajes, en los sets pequeños: bloquea si regresa más de un caso por idioma y por dataset sin explicación escrita que nombre los casos; mantener los 2 puntos solo donde hay muchas observaciones (extracción por campo, latencias).
> - `B.` Mantener 2 puntos para todo y aceptar que habrá que escribir la explicación en casi cada cambio.
> - `C.` Bloquear solo con las compuertas duras y tratar toda caída de métrica como aviso, no como bloqueo.
> - `X. Other (please specify)`
>
> **Recomendación: A.** Conserva el bloqueo donde la señal es real y evita que la
> compuerta se vuelva ruido; `C` es el camino más corto a que las métricas dejen de
> importar, y `B` es el más corto a que alguien apague la compuerta.

**Nueva Q8 — compuerta en rojo por causa ajena al cambio (Testing Posture).**
`org.md` prohíbe bajar un umbral para que un paso pase, y está bien que lo
prohíba. Pero no existe hoy ninguna salida documentada para el caso en que la
compuerta se pone roja por una caída del proveedor, un cambio de versión del
modelo o un límite de cuota. Sin salida escrita, la única acción disponible es la
prohibida:

> A veces la compuerta se va a poner roja por algo que no tiene que ver con tu
> cambio: el proveedor del modelo se cayó, cambió de versión, o se agotó la cuota
> gratuita. ¿Qué hacemos en ese momento?
>
> - `A.` Se marca la corrida como inválida por causa externa, con la causa escrita y el identificador de la corrida, se vuelve a correr, y si sigue roja se bloquea; el umbral no se toca nunca y la marca queda registrada.
> - `B.` Se bloquea igual y se espera a que el proveedor vuelva.
> - `C.` Se permite mergear con la compuerta roja anotando la razón.
> - `X. Other (please specify)`
>
> **Recomendación: A.** Distingue "roto por el cambio" de "roto por el entorno" sin
> tocar ningún umbral, que es lo que `org.md` prohíbe; `C` abre la puerta a saltarse
> la compuerta por costumbre y `B` deja a una persona sola bloqueada por algo que no
> controla.

---

### 10. Dos avisos de integración para el lead

- El cuerpo visible completo de `## Testing Posture` viaja a Code Generation como
  `applicable_notes` del contrato. Cualquier marcador `**[pendiente: ...]**` que
  sobreviva a la integración llegará al generador de código como instrucción
  autorizada. Los cinco marcadores del borrador tienen que desaparecer, resueltos o
  retirados, antes de promover a `team.md`.
- `- **Ordering**:` debe quedar en **una sola línea** (ver punto 1). Si al integrar
  se reparte en viñetas, el contrato se queda con la primera y el resto se pierde sin
  error visible.

## Positions

- AGREE: La lectura de que la línea base es cero y de que no hay práctica que inferir del código existente — `code-quality-assessment.md` lo establece con búsquedas negativas verificables, no con opinión, y eso ancla bien toda la sección.
- AGREE: Mantener el piso del 80 % sin bajarlo y ponerlo además en los módulos críticos — bajarlo contradiría `org.md` y el resolutor rechaza las capas que contradicen la política más amplia.
- AGREE: Que los golden sets de audio (DS-5) corran por hito y no por merge — el tope de 5 USD y la dependencia de grabaciones de terceros lo hacen impracticable por commit, y el borrador lo justifica bien.
- AGREE: Separar las compuertas duras `[bloquea]` de las métricas promediadas — es la decisión correcta del PRD 11.2 y el borrador la transcribe sin diluirla.
- AGREE: Afirmar la obligación de herramienta sin nombrar la herramienta mientras el lenguaje no esté elegido (recomendación A de Q6) — deja la práctica escrita hoy y viva después del ADR de `domain-design`.
- OBJECT: La línea `- **Ordering**:` no es implementable tal como está — con `custom` esa frase sustituye al plan de pruebas completo del engine, y la frase actual no define una prueba de pertenencia para "comportamiento que el PRD mide con evals" ni dice nada del código que ningún eval mide, que es la mayoría.
- OBJECT: El borrador justifica el piso del 80 % citando que "el scope `classic` lo fija en `org.md`" — `combineTestObligations` solo activa ese piso para `mvp`, `enterprise`, `feature` e `infra`; con `classic` el contrato emite "no extra new-test floor", así que el piso sobrevive únicamente como prosa y hay que escribirlo como obligación propia con su comando y su lista de exclusión.
- OBJECT: La definición de regresión de 2 puntos porcentuales es inoperable en sets de 10 a 30 casos por idioma — un solo caso mueve entre 3,3 y 10 puntos, de modo que la compuerta exigiría explicación escrita en casi toda corrida y terminaría apagándose; hay que contar casos, no porcentajes, en los sets pequeños.
- OBJECT: Ninguna de las compuertas descritas tiene ejecutor dentro de este intent — `ci-pipeline` está en Stages to Skip y CI vive en el intent `infra`, así que toda frase "en CI antes del merge" carece de dueño hasta la semana 3 o 4; hay que nombrar `build-and-test` y el comando local como ejecutor provisional.
- OBJECT: Falta por completo la estrategia de datos de prueba — ocho datasets sostienen el régimen y el borrador no dice que vivan versionados como archivos por caso con identificador estable, ni que el generador sea determinista y sembrado con salida commiteada; sin eso la "línea base versionada" no tiene sustrato reproducible.
- OBJECT: Las compuertas duras no llegarán a la `## Target Verification Matrix` de `build-and-test`, que solo inventaría desde `nfr-requirements/`, `nfr-design/` y el `## Testing Contract` — sin una regla que obligue a registrarlas como objetivos medibles en `nfr-requirements`, quedarán documentadas y no verificadas.
- OBJECT: El paso de runner que recibirá cada unit dice "verifica el runner existente" porque `Project Type` es `Brownfield`, y no existe ninguno — hay que compensarlo con una declaración explícita de bootstrap en la prosa de `## Testing Posture`, que es el canal que sí llega al generador.
- OBJECT: Con `Test Strategy: Standard`, `build-and-test` no genera instrucciones de prueba de seguridad ni de rendimiento, y las compuertas duras de este producto son precisamente de seguridad y sus umbrales publicables de rendimiento — hay que exigirlas por escrito en lugar de subir toda la estrategia a `Comprehensive`.
- OBJECT: No está definido qué pasa con la compuerta cuando el juez cae por debajo del 85 % de calibración a mitad del proyecto, ni cuál es la salida cuando una compuerta se pone roja por causa externa al cambio — con `org.md` prohibiendo bajar umbrales, la ausencia de una salida documentada deja como única acción disponible la que está prohibida.
