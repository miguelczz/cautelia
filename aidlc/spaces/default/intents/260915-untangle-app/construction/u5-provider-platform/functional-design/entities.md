# Entidades — U5 `provider-platform`

Esta unidad no tiene un dominio propio: tiene **la factura**. Todo lo que cuesta
dinero pasa por aquí, y lo que se guarda existe para responder tres preguntas
que nadie más puede responder: cuánto costó esto, cuánto llevo gastado, y qué
pasó dentro de la llamada.

Cuatro entidades se guardan —el registro de gasto, los contadores de cuota, el
acumulado de la ventana y el resumen de traza— y quince objetos de valor no se
guardan: existen para que un costo no pueda escribirse sin decir si se midió, y
para que ningún tipo de un proveedor cruce hacia el núcleo.

> **Corrección del 2026-09-21, aplicada en la compuerta de la unidad.** Se
> guardan **cinco**. La quinta registra qué llamada de voz ya se cerró, y no
> estaba prevista porque este documento no llegó a preguntarse cómo se hace
> idempotente la devolución del cupo de BR5.5. La respuesta es que hace falta
> estado durable: U16 cierra la sesión siempre, también cuando la llamada se
> cae, así que el doble cierre es el caso normal, y la guarda de "no bajar de
> cero" solo protege al contador del visitante —cuyo límite es uno— y no al del
> sitio, cuyo conteo es grande. Sin marca, el segundo cierre le devuelve al
> sitio un cupo que sí se gastó. Lleva la referencia de la llamada y dos marcas
> de tiempo: ninguna columna de texto libre y ninguna de dato personal, así que
> entra en la lista de exclusión del aislamiento con la misma prohibición
> compensatoria que las otras tres (BR7.1 enmendada, BR7.2).

**Cuatro de las cinco tablas no llevan aseguradora, y eso es el diseño.** El
techo es uno solo para el proyecto y para el gasto que no tiene aseguradora
ninguna —evaluaciones, generación de datos, operación—, así que el dinero y las
cuotas son dato del proyecto (Q1). A cambio aceptan una prohibición más fuerte
que la que pierden, y comprobable: ahí dentro no hay nada personal que aislar
(BR7.2). Esa prohibición no queda en prosa: se apoya en una lista versionada de
nombres de columna considerados dato personal, que vive en el manifiesto
`app/backend/pyproject.toml` al lado de la lista de exclusión que paga, y que la
aserción compara contra el catálogo vivo. La única que sí es dato de un visitante es el resumen de
traza, que lleva su aseguradora y su política como cualquier otra.

El bloque siguiente es la fuente de verdad; el resumen que va después se deriva
de él.

```yaml
entities:

  # --- Lo que se guarda ------------------------------------------------------

  - name: SpendEntry
    description: >
      Una llamada a un proveedor y lo que costó. Es el libro mayor del
      proyecto: una fila por llamada, sin excepción, incluida la que no se pudo
      valorar. No cuelga de nada; nombra el caso al que se atribuye.
    identifier: entry_id
    attributes:
      - name: entry_id
        type: identifier
        required: true
        unique: true
      - name: provider
        type: ProviderName
        required: true
        allowed_values: [gemini, deepgram, cartesia, fallback_tts]
        constraint: "Lista cerrada. Un proveedor nuevo es una entrada nueva, no una cadena libre."
      - name: model
        type: identifier
        required: true
        constraint: "El identificador exacto del modelo o de la voz, nunca un alias móvil (BR1.4)."
      - name: use
        type: Use
        required: true
        allowed_values: [voice, chat, evals, operations]
        constraint: "Decide el proyecto, la clave y el plan; de ahí sale `billable`."
      - name: tenant_ref
        type: identifier
        required: false
        references: "Tenant (U2 `tenancy`)"
        constraint: >
          Atribución, no aislamiento: esta tabla no lleva política de
          aseguradora (BR7.1). Nula cuando el uso no tiene aseguradora
          —evaluaciones, generación, operación—.
      - name: case_ref
        type: identifier
        required: false
        references: "Case (U4 `case_record`)"
        constraint: >
          Lo nombra, no cuelga de él. El reinicio nocturno la deja en nulo y la
          fila sobrevive (BR7.5).
      - name: units
        type: decimal
        required: true
        min: 0
      - name: unit_kind
        type: UnitKind
        required: true
        allowed_values: [input_tokens, output_tokens, embedding_tokens, audio_seconds, characters]
        constraint: "Un proveedor cobra por lo que cobra; convertirlo aquí a una unidad común perdería el precio de lista."
      - name: unit_price_usd
        type: decimal
        required: false
        min: 0
        constraint: "Presente exactamente cuando `cost_status` es `measured` (BR3.4)."
      - name: price_list_version
        type: identifier
        required: false
        constraint: "Presente exactamente cuando `cost_status` es `measured`. Qué lista se usó (AC4.8.4)."
      - name: price_list_effective_date
        type: date
        required: false
        constraint: "Presente exactamente cuando `cost_status` es `measured`. De cuándo es esa lista (AC4.8.4)."
      - name: cost_usd
        type: decimal
        required: false
        min: 0
        constraint: "Presente exactamente cuando `cost_status` es `measured`. Nunca cero por falta de precio (BR3.3)."
      - name: cost_status
        type: CostStatus
        required: true
        allowed_values: [measured, not_measured]
        constraint: "Viaja siempre con el costo. Un costo sin su estado no se puede escribir (BR3.4)."
      - name: billable
        type: boolean
        required: true
        constraint: >
          Si esta llamada se factura de verdad. Sale del plan del uso, que vive
          en configuración versionada. Solo las facturables suman contra el
          techo (BR4.2).
      - name: lane
        type: BudgetLane
        required: true
        default: public
        allowed_values: [public, recording]
        constraint: >
          De qué carril del presupuesto sale. `recording` solo lo puede pedir
          quien entra con credencial de la aseguradora, nunca el enlace público
          (BR4.10).
      - name: source
        type: SpendSource
        required: true
        allowed_values: [provider_reported, counted_locally]
        constraint: "De dónde salió el recuento de unidades. Un conteo propio y uno del proveedor no valen lo mismo y no se mezclan sin decirlo."
      - name: occurred_at
        type: timestamp
        required: true
        constraint: "Cuándo terminó la llamada. Decide en qué ventana y en qué mes cae."
    constraints:
      - "Las cuatro columnas de precio —precio unitario, versión de lista, fecha de lista y costo— están todas presentes o todas ausentes, y eso lo dice `cost_status` (BR3.4)."
      - "La tabla no lleva ninguna columna de texto libre ni de dato personal, y una aserción contra el catálogo vivo lo comprueba (BR7.2)."
    relationships:
      - "Un caso tiene muchas filas de gasto; una fila de gasto nombra a lo sumo un caso, y puede quedarse sin él."
      - "Una aseguradora tiene muchas filas de gasto; una fila puede no tener aseguradora."

  - name: QuotaCounter
    description: >
      Cuánto lleva consumido un sujeto en un periodo. Es lo que impide que un
      visitante abra diez llamadas a la vez y lo que corta el chat cuando el
      plan gratuito se acaba.
    identifier: counter_key
    attributes:
      - name: counter_key
        type: identifier
        required: true
        unique: true
        constraint: "Se deriva de alcance, sujeto y comienzo del periodo. Dos contadores del mismo alcance y sujeto en el mismo periodo son uno."
      - name: scope
        type: QuotaScope
        required: true
        allowed_values: [chat_messages_session, chat_messages_day, voice_calls_visitor_day, voice_calls_site_day]
        constraint: "Lista cerrada de cuatro. Un alcance nuevo es un cambio a esta lista (BR5.1)."
      - name: subject_key
        type: identifier
        required: true
        constraint: >
          El resumen de la clave del navegador, nunca la clave (BR7.3). Para el
          alcance del sitio, el literal `site`: el cupo del sitio no es de
          nadie.
      - name: period_start
        type: timestamp
        required: true
        constraint: "Calculado en la zona horaria configurada, no en la del servidor (BR5.2)."
      - name: count
        type: integer
        required: true
        default: 0
        min: 0
      - name: limit_at_period_start
        type: integer
        required: true
        min: 0
        constraint: >
          El límite vigente cuando se abrió el periodo. El cupo del sitio se
          recalcula cada día (BR5.6); esto deja escrito con cuál se decidió, de
          modo que un rechazo se pueda explicar meses después.
      - name: updated_at
        type: timestamp
        required: true
    constraints:
      - "No lleva columnas de texto libre ni de dato personal (BR7.2)."
    relationships:
      - "Un sujeto tiene un contador por alcance y por periodo."

  - name: BudgetWindow
    description: >
      El acumulado del proyecto en la ventana de 90 días, con su techo, su
      alerta y si la alerta ya salió. Es una sola fila y existe por dos razones
      que el registro de gasto no cubre: el corte tiene que poder decidirse sin
      recorrer el historial, y dos llamadas simultáneas tienen que competir por
      la misma fila para que ninguna pase el techo creyendo que la otra no
      existe.
    identifier: window_start
    attributes:
      - name: window_start
        type: date
        required: true
        unique: true
        constraint: "La ventana vigente empieza el 2026-09-16 (D11)."
      - name: window_end
        type: date
        required: true
        constraint: "Noventa días después del comienzo. La ventana es acumulada, nunca mensual (BR4.1)."
      - name: billable_spent_usd
        type: decimal
        required: true
        default: 0
        min: 0
        constraint: "Suma solo las filas facturables (BR4.2). Se incrementa en la misma transacción que escribe la fila (BR4.6)."
      - name: cap_usd
        type: decimal
        required: true
        default: 5.00
      - name: alert_usd
        type: decimal
        required: true
        default: 3.00
      - name: alert_sent_at
        type: timestamp
        required: false
        constraint: "Se escribe una sola vez. Que exista es lo que impide una segunda alerta (BR4.3)."
      - name: recording_reserve_usd
        type: decimal
        required: true
        default: 0
        min: 0
        constraint: >
          La porción del techo que el enlace público no puede tocar, apartada
          para grabar el video final y para la sesión de escucha (BR4.9, FR3.11).
          Su valor exacto lo fija `nfr-requirements` de esta unidad, con los
          minutos que el video y la sesión necesitan.
      - name: recording_spent_usd
        type: decimal
        required: true
        default: 0
        min: 0
        constraint: >
          Lo que el carril de grabación lleva gastado de su reserva. Está
          incluido en el acumulado facturable; esta columna dice qué parte de él
          es de ese carril.
      - name: unmeasured_billable_calls
        type: integer
        required: true
        default: 0
        min: 0
        constraint: >
          Cuántas llamadas facturables no se pudieron valorar, **de los dos
          carriles juntos**. Viaja con el acumulado para que ninguna pantalla
          pueda mostrar el total sin decir cuánto no se midió (BR3.5).
      - name: unmeasured_recording_calls
        type: integer
        required: true
        default: 0
        min: 0
        constraint: >
          **Corrección del 2026-09-21, aplicada en la compuerta de la unidad.**
          Cuántas de esas llamadas salieron del carril de grabación. Sin esta
          columna la fila sabía cuántas no se valoraron pero no de qué carril,
          y de ahí salían dos errores opuestos: una llamada de grabación sin
          valorar inflaba el restante de su carril sin que nada lo dijera, y a
          la vez cerraba el carril público, que no tenía por qué cerrarse —el
          gasto público se deriva restando los dos acumulados, así que el cero
          de una llamada sin valorar se cancela y ese restante sigue siendo
          exacto—. Nunca supera a `unmeasured_billable_calls`, que es la gemela
          de la contención que ya rige entre los dos importes.
      - name: updated_at
        type: timestamp
        required: true
    constraints:
      - "Existe exactamente una fila por ventana, y a lo sumo una ventana vigente."
      - "La reserva de grabación nunca supera al techo."
      - >
        **Corrección del 2026-09-21, aplicada en la compuerta de la unidad.**
        Esta lista decía además que "lo gastado en ese carril nunca supera a su
        reserva", y esa invariante se retiró porque enfrentaba a dos reglas
        aprobadas y estaba resuelta a favor de la equivocada. BR4.5 acepta un
        exceso —el techo se consulta antes y el costo se registra después, así
        que el de la llamada en vuelo es parte del diseño— y BR3.1 exige que
        **toda** llamada deje su fila, sin excepción. Con la invariante puesta,
        una llamada de grabación con la reserva agotada no podía registrarse:
        la escritura levantaba y la fila se perdía. Manda BR3.1, porque una fila
        de gasto perdida falsea una cifra publicada y no deja rastro de que
        falta, mientras que un restante que llega a cero y se queda ahí no
        falsea nada: el restante ya se informa con piso en cero.
      - "El presupuesto público restante es el techo menos la reserva menos lo que el carril público lleva gastado, y nunca se informa negativo (BR4.9)."
      - >
        El restante de grabación es la reserva menos lo gastado en ese carril,
        tampoco se informa negativo, y queda **no medido** por dos causas
        distinguibles: la reserva no se pudo calcular, o alguna llamada de ese
        carril no se pudo valorar."
      - "No lleva columnas de texto libre ni de dato personal (BR7.2)."

  - name: TraceSummary
    description: >
      Lo que una respuesta del chat enseña de sí misma: por qué nodos pasó,
      cuántas cláusulas recuperó y verificó, cuánto tardó y cuánto costó. Es
      dato de un visitante: solo lo ve el navegador que lo produjo y el reinicio
      nocturno lo borra.
    identifier: trace_id
    attributes:
      - name: trace_id
        type: identifier
        required: true
        unique: true
        constraint: "El mismo identificador que lleva la traza exportada, para poder cruzarlas."
      - name: tenant_id
        type: identifier
        required: true
        references: "Tenant (U2 `tenancy`)"
        constraint: "Toda lectura y escritura pasa por el punto único de sesión que ya lo fijó."
      - name: case_id
        type: identifier
        required: true
        references: "Case (U4 `case_record`)"
        constraint: "Cuelga del caso: el reinicio nocturno se lo lleva con él (BR7.4)."
      - name: visitor_key_hash
        type: identifier
        required: true
        constraint: "El resumen de la clave del navegador, nunca la clave (BR7.3). Decide a quién se le muestra (BR6.6)."
      - name: turn_ref
        type: identifier
        required: false
        references: "TranscriptTurn (U4 `case_record`)"
        constraint: "El turno cuya respuesta resume. Nulo en el resumen de un caso entero."
      - name: nodes
        type: list of NodeTiming
        required: true
        constraint: "Puede estar vacía mientras el estado es `recording`. Vacía y `ready` sería un resumen que miente."
      - name: clauses_retrieved
        type: integer
        required: true
        default: 0
        min: 0
      - name: clauses_verified
        type: integer
        required: true
        default: 0
        min: 0
        constraint: "Nunca mayor que las recuperadas: verificar lo que no se recuperó no significa nada."
      - name: latency_ms
        type: integer
        required: false
        min: 0
        constraint: "Nulo mientras el estado es `recording`."
      - name: cost_usd
        type: decimal
        required: false
        min: 0
      - name: cost_status
        type: CostStatus
        required: true
        allowed_values: [measured, not_measured]
        constraint: "Mismo par que en el registro de gasto: el costo no se escribe sin su estado (BR3.4)."
      - name: status
        type: TraceSummaryStatus
        required: true
        default: recording
        allowed_values: [recording, ready, lost]
        constraint: "`lost` es un valor, no un fallo: el backend de trazas no la recibió y nada se detuvo (BR6.7)."
      - name: created_at
        type: timestamp
        required: true
    constraints:
      - "Las cláusulas verificadas nunca superan a las recuperadas."
      - "Con estado `ready`, la latencia y la lista de nodos están presentes."
    relationships:
      - "Un caso tiene muchos resúmenes de traza, uno por respuesta."
      - "Cada resumen pertenece al navegador que lo produjo y a nadie más."

  # --- Lo que no se guarda ---------------------------------------------------

  - name: Use
    description: >
      Para qué se llama al proveedor. No es una etiqueta: decide el proyecto, la
      clave, el plan y si la llamada se factura.
    kind: value_object
    attributes:
      - name: value
        type: enum
        required: true
        allowed_values: [voice, chat, evals, operations]

  - name: PriceEntry
    description: >
      Una línea de la tabla versionada de precios de lista. Vive en un archivo
      de configuración, no en una tabla: cambiarla es un cambio de código que
      queda en el historial.
    kind: value_object
    attributes:
      - name: provider
        type: ProviderName
        required: true
      - name: model
        type: identifier
        required: true
      - name: unit_kind
        type: UnitKind
        required: true
      - name: unit_price_usd
        type: decimal
        required: true
        min: 0
      - name: list_version
        type: identifier
        required: true
      - name: effective_date
        type: date
        required: true

  - name: Money
    description: >
      Una cantidad de dinero **y si se midió**. No existe un costo suelto en
      esta unidad: el par es el tipo (BR3.4).
    kind: value_object
    attributes:
      - name: amount_usd
        type: decimal
        required: false
      - name: status
        type: CostStatus
        required: true
        allowed_values: [measured, not_measured]
    constraints:
      - "La cantidad está presente exactamente cuando el estado es `measured`."

  - name: SpendTotal
    description: >
      Lo que devuelve **toda** agregación de costo de esta unidad: el total
      medido y cuántas llamadas no se pudieron medir. Un consumidor que quiera
      publicar el total sin el conteo tiene que escribirlo a propósito (BR3.5).
    kind: value_object
    attributes:
      - name: measured_usd
        type: decimal
        required: true
        min: 0
      - name: unmeasured_count
        type: integer
        required: true
        min: 0

  - name: BudgetState
    description: >
      La foto del presupuesto que consumen la consola de voz, el chat y la
      pantalla de gasto.
    kind: value_object
    attributes:
      - name: window_start
        type: date
        required: true
      - name: window_end
        type: date
        required: true
      - name: spent
        type: SpendTotal
        required: true
      - name: cap_usd
        type: decimal
        required: true
      - name: alert_usd
        type: decimal
        required: true
      - name: public_remaining_usd
        type: "decimal | no medido"
        required: true
        constraint: >
          Techo menos reserva de grabación menos lo gastado en el carril público
          (BR4.9). Nunca negativo: por debajo de cero es cero, y el estado ya
          dice que se agotó.
          **Corrección del 2026-09-21, aplicada en la compuerta de la unidad.**
          Este documento lo declaró decimal a secas, y no puede serlo: la reserva
          de grabación está declarada en minutos y su precio por minuto todavía
          no existe en la tabla, así que hay un caso real en el que la resta no
          se puede hacer. Un cero por falta de precio se leería como "no queda
          presupuesto público" y cortaría el enlace público sin que nadie hubiera
          gastado nada, que es la misma clase de mentira que BR3.3 prohíbe para
          el costo.
      - name: recording_remaining_usd
        type: "decimal | no medido"
        required: true
        constraint: >
          Reserva de grabación menos lo gastado en ese carril. Corre aparte del
          anterior. Admite "no medido" por la misma razón y con el efecto
          contrario, que es el peligroso: un cero aquí se leería como "no hay
          reserva" y dejaría que el tráfico público se llevara lo que FR3.11
          aparta para grabar el video final.
      - name: state
        type: enum
        required: true
        allowed_values: [ok, alerted, exhausted, unmeasured]
        constraint: >
          Describe el **carril público**, que es el que ve un visitante.
          `exhausted` con reserva de grabación disponible es un estado normal y
          esperado (BR4.10).
          **Corrección del 2026-09-21, aplicada en la compuerta de la unidad.**
          Son cuatro y no tres desde que `unmeasured` existe. Su conducta es la
          misma que la de `exhausted` —una llamada facturable se rechaza, porque
          el corte falla cerrado para lo que cuesta dinero— pero el estado
          publicado dice la verdad: no es que se haya agotado el presupuesto, es
          que no se pudo calcular. Colapsarlos sería el mismo error que la
          convención 8c del equipo prohíbe entre "no hay cláusula" y "no pude
          verificar". La enmienda está escrita en `contract-summary.md` (C-17),
          que es el documento que leen los consumidores.

  - name: QuotaDecision
    description: >
      La respuesta a "¿puede este sujeto hacer esto ahora?". Es un valor, nunca
      una excepción: una negación es una respuesta normal (BR5.3).
    kind: value_object
    attributes:
      - name: allowed
        type: boolean
        required: true
      - name: reason_code
        type: enum
        required: false
        allowed_values: [rate_limited_session, rate_limited_daily, rate_limited_site, budget_exhausted]
        constraint: >
          Presente exactamente cuando la decisión es negativa. Tres de los
          cuatro son los que C-08 devuelve en la disponibilidad de la voz; el
          cuarto, `rate_limited_session`, es del chat (FR4.6). C-08 añade
          además `provider_unavailable`, que no es una cuota y no se decide
          aquí.
      - name: retry_after_seconds
        type: integer
        required: false
        min: 0
        constraint: "Cuándo tiene sentido volver a intentar. Ausente cuando la causa es el techo: ahí no hay cuándo."

  - name: CallReserve
    description: >
      Lo que se supone que cuesta una llamada completa, según la configuración
      versionada. Es lo que divide el presupuesto restante para sacar el cupo
      del sitio (BR5.6) y lo que decide si la voz principal cabe (BR5.7).
    kind: value_object
    attributes:
      - name: max_call_seconds
        type: integer
        required: true
        min: 1
      - name: reserve_usd
        type: decimal
        required: true
        min: 0
        constraint: "La duración máxima por el precio de lista del minuto del modo de voz más caro."

  - name: VoiceMode
    description: >
      Con qué voz se atiende la llamada. Se decide antes de empezar y no cambia
      a mitad (BR5.7).
    kind: value_object
    attributes:
      - name: value
        type: enum
        required: true
        allowed_values: [primary, fallback]

  - name: PromptRef
    description: >
      Qué prompt se usó. Un archivo por nodo e idioma, con identificador y
      hash; el hash viaja en la traza y en el registro de la corrida, y
      cambiarlo dispara la compuerta (BR1.7).
    kind: value_object
    attributes:
      - name: prompt_id
        type: identifier
        required: true
      - name: node
        type: NodeName
        required: true
        allowed_values: [intake, policy_verification, decision, compliance]
      - name: language
        type: Language
        required: true
        allowed_values: [es, en]
      - name: hash
        type: identifier
        required: true

  - name: GenerationResult
    description: >
      Lo que devuelve el puerto de generación. No lleva ningún tipo del
      proveedor: el adaptador ya lo tradujo (BR2.2).
    kind: value_object
    attributes:
      - name: text
        type: text
        required: false
        constraint: "Ausente cuando la llamada pidió salida estructurada."
      - name: structured
        type: object
        required: false
        constraint: "Ya validado dentro del adaptador; un fallo de validación fue `invalid_response` y no llegó hasta aquí (BR1.5)."
      - name: usage
        type: UsageReport
        required: true
      - name: prompt_ref
        type: PromptRef
        required: true
      - name: finish_reason
        type: enum
        required: true
        allowed_values: [stop, length, safety, other]

  - name: UsageReport
    description: >
      Lo que el adaptador le cuenta a la contabilidad después de cada llamada.
      Es lo que se convierte en una fila de gasto (BR3.1).
    kind: value_object
    attributes:
      - name: provider
        type: ProviderName
        required: true
      - name: model
        type: identifier
        required: true
      - name: units
        type: decimal
        required: true
        min: 0
      - name: unit_kind
        type: UnitKind
        required: true
      - name: source
        type: SpendSource
        required: true
        allowed_values: [provider_reported, counted_locally]

  - name: ProviderError
    description: >
      El único error que un adaptador deja salir. Cuatro tipos y solo cuatro
      (BR2.1); el tipo del proveedor se queda dentro.
    kind: value_object
    attributes:
      - name: kind
        type: enum
        required: true
        allowed_values: [timeout, rate_limited, unavailable, invalid_response]
      - name: provider
        type: ProviderName
        required: true
      - name: attempt
        type: integer
        required: true
        min: 1
        constraint: "Va en el evento de la traza junto al nodo y al tipo (AC4.8.5)."

  - name: BudgetExhausted
    description: >
      Saldo o cuota agotados. **No** es uno de los cuatro tipos de error de
      arriba a propósito: los cuatro admiten política de reintento y este no
      (BR2.3). Es una señal de parada.
    kind: value_object
    attributes:
      - name: scope
        type: enum
        required: true
        allowed_values: [project_cap, provider_quota]
      - name: provider
        type: ProviderName
        required: false

  - name: ProviderCap
    description: >
      Un tope configurado **en el proveedor**, con cuándo se comprobó por última
      vez. Vive en configuración versionada porque su valor real está fuera del
      aplicativo y solo se puede afirmar mirándolo (BR5.8).
    kind: value_object
    attributes:
      - name: provider
        type: ProviderName
        required: true
      - name: use
        type: Use
        required: true
      - name: project_ref
        type: identifier
        required: true
        constraint: "Cada uso vive en su propio proyecto del proveedor, no solo con su clave (ADR-018)."
      - name: cap_kind
        type: enum
        required: true
        allowed_values: [prepaid_balance, monthly_cap, rate_limit, none_available]
        constraint: "`none_available` es el caso que PA-9 tiene que resolver en `nfr-requirements`, y se declara en vez de esconderse."
      - name: cap_value
        type: text
        required: false
      - name: last_checked_at
        type: date
        required: true
        constraint: "Un tope que nadie comprobó en meses es una creencia, no un control."

  - name: NodeTiming
    description: Lo que un nodo aportó a una respuesta, tal como sale en el resumen de traza.
    kind: value_object
    attributes:
      - name: node
        type: NodeName
        required: true
        allowed_values: [intake, policy_verification, decision, compliance]
        constraint: "La misma grafía que el directorio del módulo, el enum de transición y el reporte de evaluación (BR6.2)."
      - name: started_at
        type: timestamp
        required: true
      - name: duration_ms
        type: integer
        required: true
        min: 0
      - name: cost
        type: Money
        required: true
```

## Resumen

### Lo que se guarda

| Entidad | Para qué existe | Lleva aseguradora | La borra el reinicio |
| --- | --- | --- | --- |
| `SpendEntry` | Una fila por llamada, con su costo o su "no medido" | No (dato del proyecto) | No; pierde el caso que nombraba |
| `QuotaCounter` | Cuánto lleva consumido un sujeto en un periodo | No (dato del proyecto) | Los de visitante sí; el del sitio no |
| `BudgetWindow` | El acumulado de la ventana, su techo y su alerta | No (dato del proyecto) | No, nunca (AC5.14.4) |
| `TraceSummary` | Lo que una respuesta enseña de sí misma | Sí, con su política | Sí, con su caso |

### Lo que no se guarda

Quince objetos de valor. Tres merecen su propia frase:

- **`Money`** es el par cantidad-y-estado. Un costo suelto no existe en esta
  unidad, así que la forma de escribir cero por falta de precio no está
  disponible: hay que elegir `not_measured` a propósito.
- **`SpendTotal`** es lo que devuelve toda agregación. Lleva dentro el conteo de
  llamadas no medidas, así que publicar un total sin decir cuánto no se midió
  exige desarmar el tipo.
- **`BudgetExhausted`** está fuera de los cuatro tipos de error del proveedor a
  propósito. Los cuatro admiten política de reintento; este es el único que
  significa "para", y meterlo en la misma lista invitaría a reintentarlo.

### Lo que esta unidad añade al catálogo, y por qué

El catálogo de `domain-design` le asigna a U5 tres entidades: `SpendEntry`,
`QuotaCounter` y `TraceSummary`. Aquí aparece una cuarta, `BudgetWindow`, y dos
columnas nuevas en `SpendEntry` que el catálogo no listaba.

- **`BudgetWindow`** existe porque el corte tiene dos requisitos que sumar el
  historial no cumple: funcionar aunque la observación falle (C-17) y ser una
  decisión que dos llamadas simultáneas no puedan tomar las dos. Una fila única
  se bloquea; una suma no.
- **`cost_status`** y **`billable`** salen de Q2 y Q3. Sin la primera, "no
  medido" sería un nulo que cualquier suma convierte en cero; sin la segunda, el
  chat en plan gratuito se comería el presupuesto de la voz.
- **`price_list_version`** y **`price_list_effective_date`** las pide AC4.8.4
  literalmente: "cada llamada registra el precio usado **y la fecha de esa
  lista**".
