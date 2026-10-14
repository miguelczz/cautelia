# Reglas de negocio — U10 `compliance`

Son 30 reglas en nueve familias: la guardia de salida, la petición de persona y
la pregunta de identidad, la emergencia, la divulgación, la revisión completa, el
nodo de cierre, el texto de origen externo, los datos y la evaluación. Todas las
que corren en el turno son deterministas (Q1); ninguna llama al modelo (Q3).

## Reglas

El bloque siguiente es la fuente de verdad; la tabla resumen se deriva de él.

```yaml
rules:

  # --- BR1: la guardia de salida ----------------------------------------------

  - id: BR1.1
    statement: Toda frase dirigida al asegurado pasa por la guardia antes de salir, frase por frase, en chat y en voz, incluidas las de degradación y las del catálogo.
    category: constraint
    applies_to: "guard_output"
    trigger: "Cada vez que una frase está lista para emitirse."
    logic: "SI una frase va hacia el asegurado ENTONCES se evalúa antes de enviarla a la síntesis o al chat, sin esperar el turno completo."
    violation: "El punto único de salida de U12 no emite sin resultado de la guardia; la prueba de streaming lo comprueba."
    source: FR7.5, FR7.6, AC1.11.3, AC1.11.4

  - id: BR1.2
    statement: La guardia detecta siete categorías cerradas.
    category: validation
    applies_to: "GuardIntervention.category"
    trigger: "Al evaluar una frase."
    logic: "Las categorías son promesa de cobertura, monto, culpa, consejo legal, afirmación de ser humana, transferencia o plazo que no existe, y revelación de configuración o de otro caso; una categoría nueva es un cambio de esta regla."
    violation: "El enum cerrado rechaza otra categoría."
    source: FR7.5, AC1.10.3, AC1.9.2, AC4.15.3

  - id: BR1.3
    statement: La detección usa patrones versionados de los dos idiomas sobre cada frase, sin importar el idioma del turno.
    category: policy
    applies_to: "PatternSet"
    trigger: "Al evaluar una frase."
    logic: "SI se evalúa una frase ENTONCES se normaliza (minúsculas, sin tildes, espacios colapsados) y se le aplican los patrones de español y de inglés."
    violation: "Los casos de RT-15 con idioma mezclado fallan."
    source: Q1, AC1.11.5, RT-15

  - id: BR1.4
    statement: Una frase que cae en una categoría se reemplaza por la frase permitida del catálogo para esa categoría, una sola vez por turno y categoría; las siguientes de la misma categoría se descartan.
    category: policy
    applies_to: "guard_output"
    trigger: "Al detectar una categoría."
    logic: "SI es la primera de su categoría en el turno ENTONCES sale la frase permitida; SI NO, la frase se descarta y el resto del turno sigue."
    violation: "La prueba con tres promesas de cobertura en un turno comprueba una sola frase permitida."
    source: Q2, AC1.11.1, AC1.11.2

  - id: BR1.5
    statement: Si la guardia no puede evaluar, la frase no sale y sale la clave de degradación. Falla cerrado.
    category: constraint
    applies_to: "guard_output"
    trigger: "Error o tiempo agotado en la evaluación."
    logic: "SI la evaluación falla ENTONCES GuardResult.evaluated es falso, text_out es la clave de degradación y queda una intervención not_evaluable."
    violation: "La prueba con un conjunto de patrones roto comprueba que la frase no sale."
    source: C-20 (qué pasa cuando falla)

  - id: BR1.6
    statement: Cada intervención queda en el caso y en la traza, con su categoría y su patrón, nunca con la frase original.
    category: policy
    applies_to: "GuardIntervention"
    trigger: "Cada intervención."
    logic: "SI la guardia interviene ENTONCES se registra la intervención y se emite un evento de traza; la frase original no se guarda."
    violation: "La prueba de la tabla comprueba que no hay columna de texto libre."
    source: AC1.11.4, team.md convención 8d

  - id: BR1.7
    statement: La revelación de configuración se detecta por forma, no por lista escrita en el código.
    category: validation
    applies_to: "Categoría config_disclosure"
    trigger: "Al evaluar una frase."
    logic: "SI la frase contiene algo con forma de clave o secreto, el identificador o el nombre de otra aseguradora leídos de la configuración, o un número de caso distinto del caso actual ENTONCES es config_disclosure."
    violation: "Los casos de RT-5 fallan."
    source: AC4.15.3, project.md (sin tenant_id literal en el código)

  - id: BR1.8
    statement: Las frases del catálogo aprobadas para responder cobertura con la cláusula verificada o con "no encuentro una cláusula" no son promesas.
    category: policy
    applies_to: "Categoría coverage_promise"
    trigger: "Al evaluar una frase del catálogo."
    logic: "SI la frase es una de las plantillas aprobadas de respuesta verificada ENTONCES la guardia no la reemplaza; los patrones apuntan a afirmar o negar cobertura, no a citar."
    violation: "La prueba de las plantillas aprobadas comprueba cero intervenciones."
    source: AC4.15.1, AC1.11.1

  # --- BR2: petición de persona y pregunta de identidad -------------------------

  - id: BR2.1
    statement: La petición de hablar con una persona se detecta en cualquier turno y en los dos idiomas, incluidas las formas indirectas.
    category: validation
    applies_to: "detect_human_request"
    trigger: "Cada turno de la persona."
    logic: "SI el texto normalizado coincide con un patrón de petición de persona de cualquier idioma ENTONCES la señal human_request es verdadera."
    violation: "Los casos de petición de persona de DS-2 y DS-6 fallan."
    source: FR7.2, AC1.9.3

  - id: BR2.2
    statement: Una petición de persona hace que el caso se derive en el turno siguiente, con motivo human_request y prioridad alta.
    category: policy
    applies_to: "TurnSignals, ClosureDecision"
    trigger: "Señal human_request verdadera."
    logic: "SI la señal es verdadera ENTONCES el runtime deriva en el turno siguiente con la frase de derivación del catálogo, aunque el caso esté incompleto."
    violation: "La prueba de punta a punta de U12 falla."
    source: AC1.9.1, AC1.9.4

  - id: BR2.3
    statement: La frase de derivación explica que un ajustador revisa el caso con lo capturado, sin transferencias inmediatas ni plazos.
    category: constraint
    applies_to: "Frase de derivación"
    trigger: "Al derivar."
    logic: "SI se deriva ENTONCES sale la frase del catálogo; la guardia bloquea las frases de la lista versionada de transferencias y plazos (categoría transfer_or_deadline)."
    violation: "La prueba de la lista versionada falla."
    source: AC1.9.2

  - id: BR2.4
    statement: La pregunta de si la agente es una persona se responde con la frase fija del catálogo en su idioma, y la conversación sigue.
    category: policy
    applies_to: "detect_identity_question"
    trigger: "Señal identity_question verdadera."
    logic: "SI la persona pregunta si habla con una persona ENTONCES la respuesta es la frase fija de AC1.10.1 o AC1.10.2 y el turno vuelve a donde iba."
    violation: "Las pruebas de las dos frases exactas fallan."
    source: AC1.10.1, AC1.10.2

  - id: BR2.5
    statement: Ningún turno afirma ni insinúa que la agente es humana, aunque se lo pidan.
    category: constraint
    applies_to: "Categoría humanity_claim"
    trigger: "Al evaluar una frase."
    logic: "SI la frase coincide con la lista versionada de afirmaciones de humanidad de su idioma ENTONCES se reemplaza (BR1.4)."
    violation: "Los casos de presión de DS-6 fallan."
    source: AC1.10.3, AC1.10.5

  # --- BR3: emergencia -------------------------------------------------------

  - id: BR3.1
    statement: Una emergencia detectada da la indicación de emergencia en ese mismo turno, antes de pedir cualquier dato, y ofrece seguir después.
    category: policy
    applies_to: "detect_emergency"
    trigger: "Señal emergency verdadera, en cualquier momento del reporte."
    logic: "SI la señal es verdadera ENTONCES la primera frase del turno es la indicación de emergencia y ninguna pregunta de datos sale antes."
    violation: "Los casos de heridos graves de DS-2 y DS-6 fallan."
    source: AC1.6.1, AC1.6.2, AC1.6.4

  - id: BR3.2
    statement: Los patrones negativos evitan las falsas alarmas.
    category: validation
    applies_to: "PatternSet de emergencia"
    trigger: "Al evaluar un turno."
    logic: "Un patrón negativo ('todos estamos bien', 'fue un golpecito') apaga la señal SOLO si en el mismo turno no aparece un herido grave nombrado; si aparece ('todos estamos bien menos mi hija, que no reacciona'), la emergencia gana. Enmienda del 2026-09-21: una falsa alarma cuesta una frase de más; una emergencia apagada puede costar una vida."
    violation: "Los casos negativos de DS-2 fallan."
    source: AC1.6.5

  - id: BR3.3
    statement: La frase de emergencia depende de dónde corre la demo, y por omisión es la pública.
    category: policy
    applies_to: "Frase de emergencia"
    trigger: "Al emitir la indicación."
    logic: "SI el despliegue no declara lo contrario ENTONCES sale la frase pública que dice que es una demostración y no puede enviar ayuda; SOLO con la configuración local explícita sale la frase con el 911 que comprueban los golden sets."
    violation: "Las pruebas de las dos configuraciones fallan."
    source: AC1.6.3, D14

  # --- BR4: divulgación ------------------------------------------------------

  - id: BR4.1
    statement: La divulgación se registra cuando sale la apertura, con canal, idioma, clave y hora.
    category: policy
    applies_to: "record_disclosure"
    trigger: "Emisión de la apertura."
    logic: "SI sale la apertura con la divulgación ENTONCES se registra DisclosureRecord."
    violation: "La revisión completa marca disclosure_missing."
    source: FR7.1

  - id: BR4.2
    statement: Registrar la divulgación es idempotente por caso y canal.
    category: constraint
    applies_to: "DisclosureRecord"
    trigger: "Registro repetido."
    logic: "SI ya existe la del mismo caso y canal ENTONCES no se crea otra."
    violation: "La prueba de doble registro falla."
    source: C-15 (los nodos se reejecutan al reanudar)

  # --- BR5: revisión completa -----------------------------------------------

  - id: BR5.1
    statement: La revisión completa comprueba cuatro controles deterministas sobre el registro del caso.
    category: validation
    applies_to: "final_review"
    trigger: "Al cierre o en la derivación."
    logic: "disclosure_ok si hay divulgación; human_route_ok si toda petición de persona se derivó en el turno siguiente; pii_ok si la transcripción exportable no tiene hallazgos del detector de U3; explainability_ok si están la transcripción, las citas con identificador y versión o la respuesta verificada sin cláusula, las reglas disparadas con sus insumos, el identificador de traza y el resultado de los controles."
    violation: "Cada control falla con su código en findings."
    source: FR7.7, FR1.7, FR7.4, AC1.16.2

  - id: BR5.2
    statement: La revisión cubre la conversación hasta el punto de derivación, si la hubo.
    category: calculation
    applies_to: "ComplianceReview.reviewed_through_turn"
    trigger: "Revisión de un caso derivado a mitad del reporte."
    logic: "SI el caso se derivó ENTONCES se revisa hasta el turno de la derivación y el resultado se adjunta."
    violation: "La prueba del caso derivado a mitad falla."
    source: AC1.16.4

  - id: BR5.3
    statement: La revisión no llama al modelo.
    category: constraint
    applies_to: "final_review"
    trigger: "Siempre."
    logic: "La relectura con juez es de U21; aquí no hay puerto de proveedor en la cadena de llamadas."
    violation: "La prueba con el puerto del modelo espiado cuenta cero llamadas."
    source: Q3

  # --- BR6: el nodo de cierre -------------------------------------------------

  - id: BR6.1
    statement: Un caso solo se cierra con la revisión aprobada y la divulgación registrada; si falta algo, el cierre se rechaza diciendo qué falta.
    category: constraint
    applies_to: "ClosureDecision"
    trigger: "Intento de cierre."
    logic: "SI algún control falla ENTONCES outcome es refused y missing lista los códigos."
    violation: "La prueba del caso sin revisión o sin divulgación falla."
    source: AC1.16.1, FR7.1, FR7.7

  - id: BR6.2
    statement: Cuando la categoría o un control lo exigen, el nodo deriva con un motivo de la lista cerrada.
    category: policy
    applies_to: "ClosureDecision.reason_code"
    trigger: "Categoría de derivación, petición de persona, emergencia, límite o verificación imposible."
    logic: "SI hay que derivar ENTONCES outcome es refer con reason_code de la lista de C-04."
    violation: "El enum cerrado rechaza otro motivo."
    source: FR7.2, C-04

  - id: BR6.3
    statement: El nodo es puro; la persistencia la hace el módulo de capacidad con clave idempotente.
    category: constraint
    applies_to: "Nodo compliance"
    trigger: "Cada ejecución, incluida la reejecución al reanudar."
    logic: "El nodo devuelve solo su conjunto de escritura; la revisión se guarda por clave (caso, turno revisado)."
    violation: "La prueba de reejecución comprueba una sola revisión guardada."
    source: C-15

  - id: BR6.4
    statement: El nodo nunca emite un texto que afirme o niegue cobertura ni mencione montos; el cierre usa frases del catálogo y pasa por la guardia.
    category: constraint
    applies_to: "Nodo compliance"
    trigger: "Al cerrar o derivar."
    logic: "El texto de cierre sale del catálogo; la decisión sobre cobertura la firma una persona en la bandeja."
    violation: "La guardia intervendría; la prueba de las frases de cierre cuenta cero intervenciones."
    source: project.md (Mandated: interrupt antes de afirmar cobertura), US1.16

  # --- BR7: texto de origen externo ------------------------------------------

  - id: BR7.1
    statement: El texto de la persona, del corpus o de un adjunto entra a un prompt solo como dato delimitado, por una única función.
    category: constraint
    applies_to: "delimit_untrusted"
    trigger: "Al construir un prompt con texto externo."
    logic: "SI un nodo pone texto externo en un prompt ENTONCES lo pasa por la función de delimitación, que lo marca como dato y neutraliza sus delimitadores; nunca se concatena al prompt de sistema."
    violation: "La prueba con un texto que imita el delimitador comprueba que no escapa."
    source: project.md (Mandated: texto externo fuera de la posición de instrucción), AC4.15.2, RT-2

  # --- BR8: datos -------------------------------------------------------------

  - id: BR8.1
    statement: Las tres tablas llevan aislamiento forzado por aseguradora con su política y su prueba, la marca de dato de visitante, y se borran con su caso.
    category: constraint
    applies_to: "DisclosureRecord, GuardIntervention, ComplianceReview"
    trigger: "Siempre."
    logic: "Borrado en cascada desde el caso y cobertura en el registro de purgadores."
    violation: "rls:check, la prueba de aislamiento y la de completitud del registro de purgadores fallan."
    source: M9, UG-3, C-11

  - id: BR8.2
    statement: Ninguna de las tres tablas guarda texto libre de la persona ni del modelo.
    category: constraint
    applies_to: "Las tres tablas"
    trigger: "Siempre."
    logic: "Solo enums, claves de catálogo, identificadores y marcas de tiempo."
    violation: "La prueba contra la lista de columnas prohibidas falla."
    source: project.md (redactar antes de persistir)

  # --- BR9: evaluación -------------------------------------------------------

  - id: BR9.1
    statement: Los casos de golden set se escriben antes de implementar y corren en cada entrega, por idioma.
    category: policy
    applies_to: "DS-2 y DS-6"
    trigger: "Antes de implementar cada control."
    logic: "Casos de DS-6 para RT-1, RT-2, RT-3, RT-5, RT-6, RT-8 y RT-15, y de DS-2 para petición de persona, heridos graves y los negativos, en los dos idiomas; se comprueba que fallan, se implementa y pasan."
    violation: "La compuerta de evaluación falla."
    source: Testing Contract (rama evaluada), AC1.6.4, AC1.9.3, AC1.10.5, AC1.11.6, AC4.15.4

  - id: BR9.2
    statement: Un patrón nuevo llega con su caso, y un ataque exitoso se vuelve caso de DS-6 con su RT-<n>.
    category: policy
    applies_to: "PatternSet, DS-6"
    trigger: "Cambio de patrones o hallazgo de red-team."
    logic: "SI se agrega o corrige un patrón ENTONCES entra el caso que lo motivó; el hallazgo no se cierra hasta que el caso pasa."
    violation: "Revisión del cambio."
    source: AC4.15.5, PRD 11.4
```

## Resumen

| ID | Familia | Regla |
| --- | --- | --- |
| BR1.1 | Guardia | Toda frase pasa antes de salir, frase por frase |
| BR1.2 | Guardia | Siete categorías cerradas |
| BR1.3 | Guardia | Patrones de los dos idiomas sobre cada frase |
| BR1.4 | Guardia | Reemplazo una vez por turno y categoría |
| BR1.5 | Guardia | Falla cerrado |
| BR1.6 | Guardia | Intervención registrada sin la frase original |
| BR1.7 | Guardia | Revelación de configuración por forma |
| BR1.8 | Guardia | Las respuestas verificadas no son promesas |
| BR2.1 | Persona | Petición detectada en cualquier turno e idioma |
| BR2.2 | Persona | Derivación en el turno siguiente |
| BR2.3 | Persona | Sin transferencias ni plazos |
| BR2.4 | Persona | Pregunta de identidad con frase fija |
| BR2.5 | Persona | Nunca afirma ser humana |
| BR3.1 | Emergencia | Indicación antes de cualquier dato |
| BR3.2 | Emergencia | Sin falsas alarmas |
| BR3.3 | Emergencia | Frase pública por omisión |
| BR4.1 | Divulgación | Registrada al salir la apertura |
| BR4.2 | Divulgación | Idempotente por caso y canal |
| BR5.1 | Revisión | Cuatro controles deterministas |
| BR5.2 | Revisión | Hasta el punto de derivación |
| BR5.3 | Revisión | Sin modelo |
| BR6.1 | Cierre | No se cierra sin controles |
| BR6.2 | Cierre | Derivación con motivo cerrado |
| BR6.3 | Cierre | Nodo puro, persistencia idempotente |
| BR6.4 | Cierre | Nunca afirma cobertura |
| BR7.1 | Texto externo | Solo como dato delimitado |
| BR8.1 | Datos | Aislamiento, marca y borrado con el caso |
| BR8.2 | Datos | Sin texto libre |
| BR9.1 | Evaluación | Casos antes, en cada entrega |
| BR9.2 | Evaluación | Patrón con caso; ataque exitoso, caso nuevo |
