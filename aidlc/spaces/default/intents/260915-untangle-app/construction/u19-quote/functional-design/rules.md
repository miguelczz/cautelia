# Reglas — U19 `quote`

Quince reglas en cuatro familias: la captura de la solicitud, la elegibilidad, lo que
no se puede decir, y la decisión del suscriptor.

Dos llevan `[bloquea]`, y las dos protegen principios: que ninguna respuesta de la
cotización contenga un importe (AC6.2.2) y que ninguna credencial sin el rol de
suscriptor decida una solicitud (AC6.3.3). La primera existe porque un precio
inventado es la promesa más cara de deshacer; la segunda, porque una decisión de
elegibilidad es una decisión que firma una persona con ese papel.

```yaml
rules:
  # --- La captura de la solicitud (US6.1) -------------------------------------
  - id: BR1.1
    statement: El grafo no gana nodos al soportar cotización.
    category: constraint
    applies_to: "El grafo"
    trigger: "Al listar sus nodos."
    logic: >
      Los cuatro nodos son `intake`, `policy_verification`, `decision` y `compliance`,
      y la cotización es un tipo de registro más sobre ellos. Un nodo nuevo por un
      tipo de registro convertiría el grafo en una rama por caso de uso, que es
      exactamente lo que la decisión de transición en código existe para evitar.
    violation: "El grafo declara un nodo que no es uno de los cuatro."
    source: FR13.1, AC6.1.1

  - id: BR1.2
    statement: La solicitud se captura en cuatro bloques, una idea a la vez, con confirmación por bloque.
    category: policy
    applies_to: "El nodo de captura"
    trigger: "Cuando el caso es de tipo solicitud de cotización."
    logic: >
      Los cuatro bloques --conductor, vehículo, uso, historial-- son la estructura que
      AC6.1.2 nombra, y la confirmación por bloque es el mismo mecanismo de los siete
      bloques del siniestro. Preguntarlo todo de una vez es el formulario que esta
      demostración existe para no ser.
    violation: "La captura pide dos bloques en un turno, o cierra un bloque sin confirmarlo."
    source: AC6.1.2

  - id: BR1.3
    statement: Ningún campo que lean las reglas existe sin el bloque de captura que lo escribe.
    category: constraint
    applies_to: "El vocabulario de campos del motor de reglas"
    trigger: "Al declarar un campo de elegibilidad."
    logic: >
      El vocabulario es cerrado y `required_inputs()` es lo que le dice a la captura
      qué escribir. Un campo declarado que nadie escribe no falla: **no dispara**,
      porque un campo ausente no satisface ninguna condición, y la regla que lo nombra
      queda muerta sin que nada se ponga rojo. Es el hueco que hoy tienen seis campos
      del triage de siniestros, y esta unidad no lo repite.
    violation: "Un campo del vocabulario de elegibilidad no lo escribe ningún bloque de captura."
    source: FD-U19-3

  - id: BR1.4
    statement: La antigüedad del vehículo es un campo derivado, calculado en un solo sitio desde el año y el reloj.
    category: constraint
    applies_to: "La captura del bloque de vehículo"
    trigger: "Al escribir el bloque."
    logic: >
      Una regla que comparara contra un año literal envejece sola: el año que viene
      significa otra cosa y no falla nada. La derivación va en un solo sitio, con el
      reloj que la captura ya inyecta, y la regla compara contra una antigüedad.
    violation: "Una regla compara contra un año del calendario, o la antigüedad se calcula en dos sitios."
    source: FD-U19-4

  - id: BR1.5
    statement: La agente ofrece cotizar solo donde la aseguradora lo tiene activo, y donde no, dice que no cotiza y ofrece lo que sí puede.
    category: policy
    applies_to: "La apertura y la respuesta a la petición de cotizar"
    trigger: "En la apertura, y cuando alguien pide cotizar."
    logic: >
      `quote_enabled` ya existe en la configuración de cada aseguradora. Ofrecer lo que
      esa aseguradora no tiene activo es prometer una capacidad que no está: el mismo
      principio que prohíbe ofrecer la devolución de llamada.
    violation: "La apertura ofrece cotizar con la cotización apagada, o la petición se queda sin respuesta útil."
    source: AC6.1.3, D4

  # --- La elegibilidad (US6.2) ------------------------------------------------
  - id: BR2.1
    statement: La salida es elegible, no elegible o derivación al suscriptor, con las reglas que la deciden y una banda de riesgo.
    category: policy
    applies_to: "La decisión de elegibilidad"
    trigger: "Cuando los cuatro bloques están capturados."
    logic: >
      Las tres salidas son cerradas y las decide el motor de reglas, no el modelo. La
      banda acompaña a las tres porque una salida sin banda deja a quien pregunta sin
      saber dónde está.
    violation: "La salida es un cuarto valor, o no nombra las reglas que la decidieron, o no trae banda."
    source: AC6.2.1, FR13.2

  - id: BR2.2
    statement: La banda de riesgo tiene cuatro valores cerrados, y la derivación dice «todavía no se sabe».
    category: policy
    applies_to: "La banda"
    trigger: "Al decidir."
    logic: >
      `standard_risk`, `elevated_risk`, `pending_review` y `outside_appetite`. La
      derivación lleva `pending_review` y no una de las otras tres: afirmar una banda
      donde decide una persona es afirmar lo que nadie ha decidido, y dejarla vacía
      diría por omisión que es la peor. Es la misma distinción entre "esto está mal" y
      "no lo sé" que el proyecto sostiene en todas partes.
    violation: "Una derivación sale con banda de riesgo afirmada, o la banda viene vacía."
    source: AC6.2.1, respuesta Q1

  - id: BR2.3
    statement: La razón se dice en lenguaje llano, sin identificadores de regla.
    category: policy
    applies_to: "La explicación al prospecto"
    trigger: "Al explicar una salida."
    logic: >
      Sale de la clave de explicación de la regla que decidió, que vive en el catálogo
      de textos por idioma y no nombra la regla ni la aseguradora. Quien pregunta lee
      la condición que no se cumple, no un código.
    violation: "La explicación contiene un identificador de regla, o no nombra la condición."
    source: AC6.2.3

  - id: BR2.4
    statement: Cada regla de elegibilidad está versionada y trae sus propios casos de prueba.
    category: constraint
    applies_to: "El conjunto de reglas de elegibilidad de cada aseguradora"
    trigger: "Al cargar el conjunto."
    logic: >
      Es la práctica afirmada del proyecto para toda regla del motor, y el formato ya
      existe: `tests` dentro del propio YAML, con su `given` y su `expect`. Una regla
      sin casos no se puede cambiar sin miedo.
    violation: "Una regla de elegibilidad se carga sin casos de prueba."
    source: Práctica afirmada; la forma de `rules/triage.yaml`

  - id: BR2.5
    statement: La elegibilidad se decide en el ritmo de fondo, nunca dentro del turno.
    category: constraint
    applies_to: "La evaluación del conjunto de elegibilidad"
    trigger: "Cuando los cuatro bloques quedan capturados."
    logic: >
      Es la misma prohibición que ya rige para la verificación, las reglas y el
      cumplimiento: el turno no hace ese trabajo, lee lo que el fondo dejó en el estado
      o emite una frase de espera del catálogo. Meterlo en el turno haría que el
      presupuesto de latencia del turno dependiera de cuántas reglas tenga una
      aseguradora.
    violation: "El manejador del turno invoca el motor de reglas de elegibilidad."
    source: Prohibición afirmada del proyecto; el ritmo de fondo del grafo

  # --- Lo que no se puede decir (US6.2) --------------------------------------
  - id: BR3.1
    statement: "[bloquea] Ninguna respuesta de la cotización contiene un importe, un símbolo o un código de moneda, ni un porcentaje, en ningún idioma."
    category: constraint
    applies_to: "Todo texto que llega a quien pregunta"
    trigger: "En cada turno, y en cada caso de DS-4."
    logic: >
      Esta demostración no calcula precios, y una cifra sería la promesa más cara de
      deshacer: quien la lea creerá que hay un motor de tarifas detrás. Lo aplica la
      guardia de salida, que ya existe y ya trae los patrones; esta unidad **no
      construye un segundo detector**, porque un segundo umbral es un umbral que un día
      discrepa del primero.
    violation: "Una respuesta de DS-4 contiene un importe, una moneda o un porcentaje."
    source: AC6.2.2, FR13.2, FD-U19-1

  - id: BR3.2
    statement: Ante la insistencia en un precio, la respuesta es una frase fija del catálogo que no da ninguna cifra y ofrece la banda.
    category: policy
    applies_to: "La respuesta a la presión por un precio"
    trigger: "Cuando quien pregunta insiste en cuánto cuesta."
    logic: >
      Dejar que el modelo improvise la negativa es dejarle la oportunidad de ceder,
      que es justo lo que los casos adversariales del proyecto buscan. La frase es del
      catálogo, en los dos idiomas, y pasa por la guardia como cualquier otra.
    violation: "La respuesta a la insistencia se genera libremente, o cede una cifra."
    source: AC6.2.4

  # --- La decisión del suscriptor (US6.3) ------------------------------------
  - id: BR4.1
    statement: "[bloquea] Solo el rol de suscriptor decide una solicitud de cotización, en la pantalla y en la API."
    category: constraint
    applies_to: "La acción de decidir una solicitud de cotización"
    trigger: "En cada petición de decisión."
    logic: >
      El rol es un valor más del enum y su permiso una fila más en la tabla, no una
      rama en el código. Y se comprueba en el servidor: una pantalla que esconda el
      botón no impide una petición directa, que es exactamente lo que AC6.3.3 prueba.
    violation: "Una credencial de ajustador o de agente de cuenta decide una solicitud, o la decide por la API."
    source: AC6.3.3, FD-U19-5

  - id: BR4.2
    statement: La bandeja del suscriptor muestra solo solicitudes de cotización derivadas.
    category: policy
    applies_to: "La lista de la bandeja"
    trigger: "Al abrirla con credencial de suscriptor."
    logic: >
      Ni siniestros, ni solicitudes que las reglas ya resolvieron. El filtro es del
      servidor y no de la pantalla, por la misma razón que el permiso.
    violation: "La lista del suscriptor trae un siniestro o una solicitud no derivada."
    source: AC6.3.1

  - id: BR4.3
    statement: La decisión se registra antes de reanudar el grafo, y la reanudación corre de fondo.
    category: constraint
    applies_to: "La decisión de una solicitud derivada"
    trigger: "Al decidirla."
    logic: >
      Al revés, un caso puede quedar reanudado sin decisión escrita, y eso no se ve.
      Se reusa el puerto de reanudación que ya existe: esperar la reanudación colgaría
      la pantalla de quien decide.
    violation: "El grafo se reanuda sin decisión registrada, o la pantalla espera la reanudación."
    source: AC6.3.2, FD-U19-7
```

## Trazabilidad

| Familia | Reglas | `[bloquea]` |
| --- | --- | --- |
| La captura de la solicitud | BR1.1 – BR1.5 | — |
| La elegibilidad | BR2.1 – BR2.5 | — |
| Lo que no se puede decir | BR3.1 – BR3.2 | BR3.1 |
| La decisión del suscriptor | BR4.1 – BR4.3 | BR4.1 |

## Sources

- `functional-design-questions.md` — las tres respuestas y las ocho decisiones
- `../../../inception/user-stories/stories.md` — US6.1, US6.2, US6.3
- `docs/reference/estructura-solicitud-cotizacion.md` — los cuatro bloques

## Assumptions & Open Questions

None.
