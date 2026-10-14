# Plan de generación de código — U16 `voice-call`

Seis tandas. Cada una termina con sus pruebas en verde, su revisión por el
procedimiento de `revisar-tanda` y su commit; ninguna deja una pieza a medias
para la siguiente.

El orden no es el de las historias sino el de las dependencias reales: primero
lo que sostiene una llamada (la fila, el token, el protocolo), después lo que la
hace conversar, después lo que la hace cómoda, y al final la pantalla. La consola
va la última a propósito: es lo único que Miguel puede querer cambiar de
aspecto, y para entonces el servidor ya está probado.

## Rama de pruebas

**Evaluada.** Realiza M13 y M6. Sus casos previos son las grabaciones de DS-5 en
inglés; lo que no cabe en DS-5 —confianza baja, transcripción vacía, ruido, eco,
cortes en cada fase— va con el reconocedor y la síntesis simulados, que son
dobles de esta unidad.

DS-5 corre **por hito**, no por entrega: las grabaciones son de personas reales,
viven fuera del repositorio y medirlas gasta. Lo que corre en cada entrega es la
rama determinista completa con los dobles, y ahí es donde están las 38 reglas.

## Dónde vive

| Qué | Dónde |
| --- | --- |
| El canal de voz | `app/backend/src/untangle/voice/` |
| Las rutas de C-08 y el socket | `app/backend/src/untangle/server/` |
| La consola | `app/frontend/src/pages/voice/`, nuevo |
| El conductor de audio para las evaluaciones | `app/backend/src/untangle/evals/drivers/` |
| Las pruebas | `app/backend/tests/unit/voice/` e `integration/voice/`, nuevos |

---

## Tanda 1 — El transporte, la sesión y su tabla

Lo que tiene que existir antes de que nadie hable.

1. `voice/models.py` — `CallSession`, `CallState` (tres), `EndReason` (cinco),
   con la forma de `entities.md`. Sin campo de audio, y esa ausencia comentada.
2. Migración `u16_voice_0001_call_sessions`: la tabla con su `tenant_id`, su RLS
   habilitado y su política, como exige la aserción de esquema que ya existe.
3. `voice/tokens.py` — firma y verificación del token de llamada, con su cabecera
   explicando por qué no es el enlace firmado de U2.
4. `voice/wire.py` — el vocabulario cerrado de los cuadros, en los dos sentidos,
   con sus serializadores. La unión cerrada es lo que obliga al comprobador de
   tipos a cubrir todas las ramas.
5. `voice/session.py` — crear, buscar viva por navegador, atar caso, terminar con
   motivo.

**Pruebas.** El esquema y la RLS con una colisión sembrada; las cuatro formas de
token malo, todas con la misma respuesta; ida y vuelta de cada cuadro del
protocolo; la tabla de motivos cubierta entera.

**Reglas que cierra:** BR1.3, BR1.4, BR1.5, BR1.6, BR7.3.

## Tanda 2 — La apertura, el turno y los silencios

El corazón: una llamada que conversa.

1. `voice/opening.py` — como `chat/opening.py`, con claves `voice.opening.*` y
   el canal `voice` en el registro de U10. La hora que se registra es la del
   **fin** de la emisión.
2. Claves nuevas del catálogo, en los dos idiomas: la apertura de voz —copiada
   literal de AC1.22.1—, las tres frases de silencio, la de no haber entendido,
   la oferta de la tercera vez y el cierre.
3. `voice/turn_detection.py` — el fin del habla de BR3.1, con su temporizador y
   su marca de tiempo del último final.
4. `voice/silence.py` — la escalera de tres, con el reloj que se detiene mientras
   la agente habla.
5. `voice/call.py` — el ciclo: escuchar, detectar, armar `InboundTurn` con
   `channel="voice"`, consumir `handle_turn`, hablar cada uno de los cinco
   eventos.
6. `voice/latency.py` — los eventos `voice.speech_end` y `voice.first_audio`.
7. Los dobles: reconocedor con guion de tiempos y síntesis instrumentada, los dos
   heredando de los `Protocol` de C-16.

**Pruebas.** Un turno de punta a punta con el doble; la compuerta de divulgación
con un turno entregado antes de tiempo; la escalera de "no te entendí" con sus
tres peldaños y su reinicio; los tres silencios en orden y el reloj que se
detiene; los dos eventos de latencia presentes en cada turno.

**Reglas que cierra:** BR2.1 a BR2.4, BR3.1, BR3.2, BR3.3, BR3.4, BR3.6, BR3.8,
BR5.1, BR5.2, BR5.3, BR8.1.

## Tanda 3 — Interrumpir, deletrear y cerrar

Lo que separa una llamada usable de una demostración.

1. `voice/barge_in.py` — el piso de palabras y de confianza, la parada de la
   síntesis y el cuadro `stop_audio`.
2. La retoma sin repetir: confirmar solo el dato corregido.
3. La apertura interrumpida que se repite entera.
4. El deletreo: llamar a `spell_for_readback` de U11 y esperar confirmación antes
   de anotar. **Esta unidad es su primer consumidor de producción.**
5. El cierre con el número dicho uno a uno, con "zero" y nunca "oh".
6. El evento `voice.barge_in_stop`.

**Pruebas.** Interrupción con el reloj inyectado, midiendo desde la marca; ruido
de una sílaba que no interrumpe; eco que no interrumpe; apertura cortada que se
repite; una placa dictada con una letra confundible que no se anota sin
confirmar; el número del cierre con los seis dígitos separados y sin "oh".

**Reglas que cierra:** BR3.5, BR3.7, BR4.1, BR4.3, BR4.4, BR4.5, BR8.2.

## Tanda 4 — El corte y la retoma

1. `voice/resume.py` — buscar caso abierto **solo** por el resumen de la clave
   del visitante, ofrecer continuar, abrir uno nuevo si la persona dice que llama
   por otro accidente, resumir la decisión si ya la hay.
2. El cierre del socket sin colgar: caso `esperando al asegurado`, lo confirmado
   y `resume_until`.
3. El evento `voice.resume_after_drop`, enlazado al caso original.

**Pruebas.** El criterio `[bloquea]` AC1.27.3, con un caso de otro navegador y la
misma póliza de ejemplo, comprobando que ni se ofrece ni se menciona; el corte en
las cuatro fases —apertura, turno de la persona, respuesta de la agente, entre
turnos—; la retoma que no vuelve a preguntar un campo confirmado; el caso
anterior intacto al abrir uno nuevo.

**Reglas que cierra:** BR6.1 a BR6.5, BR8.3.

## Tanda 5 — Las rutas, el contrato y la composición

1. `server/voice_routes.py` — `GET /voice/availability`, `POST /voice/sessions`,
   `DELETE /voice/sessions/{call_id}` y la ruta del WebSocket.
2. El contrato OpenAPI de C-08, con el objeto `transport` ya concreto, y el
   cliente generado que consume la consola.
3. La composición: la plataforma de voz de U15 conectada al canal, y el canal
   conectado al grafo. **Con un llamador de producción para cada pieza**, que es
   la comprobación que este proyecto ha fallado cinco veces.
4. `voice/api.py` — la superficie pública del módulo.
5. Los contratos de importación: `untangle.voice` sin LangGraph y sin SDK.

**Pruebas.** Las tres rutas con sus presupuestos cronometrados; el socket con y
sin autenticación; el chequeo de contratos generados; los contratos de
importación con una violación plantada y retirada.

**Reglas que cierra:** BR1.1, BR1.2 (su mitad de servidor), BR3.3.

## Tanda 6 — La consola y el conductor de evaluaciones

1. `pages/voice/voice-page.tsx` y sus piezas, con la jerarquía de
   `frontend-components.md`.
2. Los dos `AudioWorklet`: captura a PCM de 24 kHz y reproducción con cola
   vaciable.
3. `voice-copy.ts`, con la misma forma que `chat-copy.ts`, y su entrada en el
   chequeo de frases que ya existe.
4. `voice-events.ts`: un reductor puro del flujo de cuadros, probado sin
   navegador.
5. `evals/drivers/voice.py` — el conductor que inyecta una grabación por el
   transporte y registra en el corredor.
6. Las tareas `test:u16` y `voice:call-live`.

**Pruebas.** El reductor con cada cuadro; la pantalla con el micrófono negado, sin
crear nada; el vaciado de la cola al recibir `stop_audio`, cronometrado; la
prueba de accesibilidad de la consola en el arnés.

**Reglas que cierra:** BR1.2 (su mitad de navegador), BR4.2, BR7.1, BR7.2, BR8.4.

---

## Lo que no se toca

- **U15.** Los adaptadores, los puertos y la configuración de voz están cerrados
  y esta unidad los consume tal cual. Si hiciera falta un dato que el puerto no
  da —el `speech_final` de Deepgram—, no se amplía el puerto: se deriva aquí
  (decisión D4).
- **El grafo.** U16 no añade nodos ni cambia transiciones.
- **El chat.** Comparten `handle_turn` y la clave del visitante, y nada más.

## Lo que queda anotado y no se abre

Los defectos ya diagnosticados en `docs/PENDIENTES-MIGUEL.md` no se abren en esta
unidad, por decisión de Miguel del 2026-09-29: cerrar las unidades primero.

Uno de ellos toca esta unidad y hay que decirlo con precisión: **1.12, que nadie
confirma los campos del caso**. Tres de los siete campos del esquema exigen
lectura de confirmación para contar como completos, y hoy el camino de captura
solo los deja `stated`. La consecuencia en voz es la misma que en el chat —la
agente vuelve a preguntar lo ya contestado— y no la arregla esta unidad.

Lo que sí hace U16 es **no construir un segundo camino de confirmación propio**.
El deletreo de la tanda 3 confirma un dato que se dicta carácter a carácter, que
es otra cosa: es AC1.23.2 y es de voz. La confirmación de bloque de AC1.24.2 se
apoya en el estado del caso tal como esté. El día que se arregle 1.12, la voz lo
hereda sin tocarse.

## Cómo se revisa cada tanda

Por `.claude/skills/revisar-tanda/SKILL.md`, y empezando por los dobles: esta
unidad tiene dos grandes —el reconocedor y la síntesis— y la forma 12 del
catálogo es exactamente lo que se rompe cuando un doble es más permisivo que la
pieza real. Cada regla que la tanda dice cumplir se rompe a propósito y se anota
qué prueba se cayó.

## Sources

- `../functional-design/functional-spec.md`, `rules.md`, `entities.md`, `frontend-components.md`
- `../nfr-requirements/` — los cinco documentos de esta unidad
- `../../../inception/units-generation/unit-of-work.md` — U16
- `../../u15-speech-providers/code-generation/code-summary.md`
- `docs/reference/como-se-revisa-el-codigo.md`

## Assumptions & Open Questions

None.

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
