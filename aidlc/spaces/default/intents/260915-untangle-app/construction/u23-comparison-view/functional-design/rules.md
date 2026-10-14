# Reglas — U23 `comparison-view`

Diez reglas en tres familias: lo que se dice antes de preguntar, las tres respuestas, y
lo que la vista no puede hacer.

Una lleva `[bloquea]`: que cada columna recupere solo del corpus de su aseguradora,
comprobado en las trazas. Es la compuerta dura de M9 hecha visible, y la razón por la
que esta vista existe.

```yaml
rules:
  # --- Antes de preguntar (AC2.9.1, AC2.9.6) ----------------------------------
  - id: BR1.1
    statement: La vista dice qué es y qué póliza de ejemplo usa cada columna antes de la primera pregunta.
    category: policy
    applies_to: "La vista de comparación"
    trigger: "Al cargar."
    logic: >
      Asistente de inteligencia artificial, demostración con pólizas de ejemplo, y la
      póliza de cada columna. Ninguna apertura de aseguradora dice lo tercero, y sin
      ello las tres columnas se leen como tres opiniones en vez de tres pólizas.
    violation: "La vista pide una pregunta sin haber dicho las tres cosas."
    source: AC2.9.1

  - id: BR1.2
    statement: La columna de Knotwell nombra la aseguradora que emitió su póliza de ejemplo.
    category: policy
    applies_to: "La columna de la agencia"
    trigger: "Al mostrar su póliza de ejemplo."
    logic: >
      Knotwell es una agencia y no emite pólizas. Sin nombrar a quien emitió, la
      columna afirma algo que no es y quien evalúa saca la conclusión equivocada sobre
      cómo funciona el producto.
    violation: "La columna de la agencia muestra una póliza sin decir quién la emitió."
    source: AC2.9.1

  - id: BR1.4
    statement: La divulgación de la vista queda registrada en los tres casos, como entregada por esta superficie.
    category: constraint
    applies_to: "Los tres casos que la vista abre"
    trigger: "Al mandar la primera pregunta."
    logic: >
      Una pregunta de cobertura **abre un caso**, y un caso sin su registro de
      divulgación no se puede cerrar. La vista no muestra las tres aperturas del chat
      --serían cuatro divulgaciones seguidas y tres ofertas de reportar un siniestro en
      una pantalla que compara coberturas--, así que la divulgación que queda registrada
      es la de la vista, con su hora, su idioma y su superficie. La superficie es un
      dato de la conversación y no una rama por pantalla.
    violation: "Un caso abierto por la vista no tiene divulgación registrada, o la registrada no es la que se mostró."
    source: AC2.9.1, AC1.1.2, respuesta Q1

  - id: BR1.3
    statement: Las preguntas de ejemplo y el texto de fuera de propósito salen del catálogo por idioma.
    category: constraint
    applies_to: "Todo texto de la vista"
    trigger: "Al dibujarla."
    logic: >
      Ninguna cadena visible se escribe en línea, y la paridad español-inglés se
      comprueba sobre el catálogo. Es la regla del proyecto, sin excepción para esta
      pantalla.
    violation: "Una cadena visible de la vista está escrita en el componente."
    source: Regla del proyecto; AC2.9.6

  # --- Las tres respuestas (AC2.9.2 a AC2.9.5) -------------------------------
  - id: BR2.1
    statement: Las tres columnas responden en el idioma de la pregunta.
    category: policy
    applies_to: "Las tres conversaciones que la vista abre"
    trigger: "Al mandar la primera pregunta."
    logic: >
      El idioma lo decide el detector determinista que ya existe, no el modelo. Hace
      falta decirlo porque las tres aseguradoras tienen idioma por defecto distinto
      --`en`, `es`, `en`--: sin esto, la primera pregunta volvería contestada en dos
      idiomas y la comparación compararía también el idioma.
    violation: "Una columna responde en un idioma distinto al de la pregunta."
    source: AC2.9.2, FD-U23-3

  - id: BR2.2
    statement: Cada columna tiene su propio estado de carga, aparece en cuanto está lista, y su fallo no afecta a las otras.
    category: policy
    applies_to: "Las tres columnas"
    trigger: "Mientras llegan las respuestas."
    logic: >
      Tres flujos independientes, uno por aseguradora. Esperar a las tres para mostrar
      la primera convertiría la vista en la más lenta de las tres, y un fallo en una
      dejaría la pantalla vacía cuando dos respuestas ya existen.
    violation: "La vista espera a las tres, o una que falla borra las otras."
    source: AC2.9.5

  - id: BR2.3
    statement: Cada pregunta cuenta como tres respuestas contra los límites del chat público.
    category: constraint
    applies_to: "Los cinco controles del chat"
    trigger: "En cada pregunta de la vista."
    logic: >
      Son tres mensajes por tres rutas que ya llevan sus controles, así que esto no es
      un contador que esta vista mantenga: es lo que pasa. Un contador propio sería un
      segundo sitio donde el límite puede discrepar del que de verdad protege.
    violation: "Una pregunta de la vista descuenta un mensaje en vez de tres."
    source: AC2.9.6, FD-U23-1

  - id: BR2.4
    statement: Un rechazo por límite se dice en la columna que lo recibió, con la frase de su catálogo, y las otras siguen.
    category: policy
    applies_to: "La columna rechazada"
    trigger: "Cuando el chat devuelve un rechazo por límite."
    logic: >
      El rechazo trae **cuál** límite fue y la clave de su frase, nunca el texto. La
      columna la resuelve de su catálogo, igual que el chat.
    violation: "Un rechazo se dice con un texto propio de la vista, o tumba las tres columnas."
    source: AC2.9.6; el contrato del chat

  # --- Lo que la vista no puede hacer ----------------------------------------
  - id: BR3.1
    statement: "[bloquea] Cada columna recupera solo del corpus de su aseguradora, y ninguna cita una cláusula de otra."
    category: constraint
    applies_to: "Las tres respuestas"
    trigger: "En cada pregunta, comprobado en las trazas."
    logic: >
      Es la compuerta dura de M9 hecha visible, y la razón por la que esta vista existe.
      Se cumple por construcción --cada llamada va dirigida a una aseguradora y la
      recuperación ya es por aseguradora-- y se **comprueba** leyendo las trazas de las
      tres columnas, que es lo que el criterio pide.
    violation: "Una traza de una columna muestra recuperación o cita de otro corpus."
    source: AC2.9.3

  - id: BR3.2
    statement: La vista no redacta la diferencia entre columnas.
    category: constraint
    applies_to: "La vista"
    trigger: "Al mostrar respuestas distintas."
    logic: >
      La diferencia se lee en las cláusulas citadas. Una vista que la redactara estaría
      afirmando cobertura sin pasar por donde eso se decide, y afirmar cobertura es lo
      que ninguna salida puede hacer sin que lo firme una persona.
    violation: "La vista muestra un texto propio explicando por qué dos columnas difieren."
    source: AC2.9.4, y la prohibición del proyecto sobre afirmar cobertura
```

## Trazabilidad

| Familia | Reglas | `[bloquea]` |
| --- | --- | --- |
| Antes de preguntar | BR1.1 – BR1.4 | — |
| Las tres respuestas | BR2.1 – BR2.4 | — |
| Lo que no puede hacer | BR3.1 – BR3.2 | BR3.1 |

## Sources

- `functional-design-questions.md` — la pregunta y las siete decisiones
- `../../../inception/user-stories/stories.md` — US2.9

## Assumptions & Open Questions

None.
