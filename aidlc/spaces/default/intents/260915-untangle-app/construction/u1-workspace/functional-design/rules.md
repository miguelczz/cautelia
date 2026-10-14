# Reglas de negocio — U1 `workspace`

Las reglas que el comportamiento de la unidad base tiene que cumplir: el
corredor de evaluaciones, el asegurado simulado y el catálogo de textos. Cada
regla es comprobable; ninguna vive solo en la memoria de quien la escribió.

**Fuentes consumidas.** `../../../inception/units-generation/unit-of-work.md`
(las responsabilidades de U1),
`../../../inception/units-generation/unit-of-work-story-map.md` (los quince
criterios de aceptación de US4.4, US4.7 y US5.8),
`../../../inception/requirements-analysis/requirements.md` (FR11.1, FR11.3,
NFR17 y NFR21), `../../../inception/domain-design/components.md` (CopyCatalog y
la parte de Evaluation que le toca a U1) y
`../../../inception/contract-design/contract-summary.md` (C-21, C-22 y C-27).

## Reglas

```yaml
rules:
  - id: BR1.1
    statement: >
      Un solo comando corre las evaluaciones, y el archivo de tareas, el README
      y el flujo de integración continua invocan exactamente ese comando.
    category: policy
    applies_to: Corredor de evaluaciones
    trigger: Cada vez que alguien o la tubería corre las evaluaciones.
    logic: >
      SI se ejecutan las evaluaciones desde cualquier origen, ENTONCES el origen
      invoca el comando nombrado en el archivo de tareas, y no una lista propia
      de pasos.
    violation: La tubería que mantiene su propia lista de pasos es un fallo del chequeo, no una variante aceptable.
    source: FR11.3, AC4.4.1, AC4.4.2, NFR21

  - id: BR1.2
    statement: >
      Sin la clave del modelo en el entorno, la corrida no llama a ningún
      proveedor. Si el conjunto que va a correr necesita esa clave, se detiene
      antes del primer caso nombrando la variable; si no la necesita, corre y
      los casos que sí la necesitaban quedan no medidos con esa causa.
    category: validation
    applies_to: Corredor de evaluaciones
    trigger: Al arrancar la corrida, antes de ejecutar el primer caso.
    logic: >
      SI falta una variable de entorno requerida Y al menos un caso del conjunto
      seleccionado la necesita, ENTONCES la corrida termina con un código
      distinto de cero y un mensaje que nombra la variable, SIN haber llamado a
      ningún proveedor. SI falta Y ningún caso seleccionado la necesita,
      ENTONCES la corrida se ejecuta con normalidad. SI falta Y solo la
      necesitan algunos, ENTONCES esos quedan no medidos con la causa
      `provider_key_missing`, la corrida termina y queda marcada no comparable.
    violation: >
      Arrancar y fallar a mitad gasta cuota y deja resultados parciales que
      parecen medidos. Y detenerse cuando nada de lo seleccionado necesitaba la
      clave rompe la meta de los 15 minutos para quien clona sin cuenta en
      ningún proveedor.
    source: AC4.4.6; enmienda del 2026-09-19 por la corrección de NFR21

  - id: BR1.3
    statement: Sin backend de trazas, la corrida continúa y el reporte marca los enlaces de traza como no disponibles.
    category: policy
    applies_to: Corredor de evaluaciones
    trigger: Al generar el reporte.
    logic: >
      SI el backend de trazas no está disponible, ENTONCES el reporte se genera
      igual y cada resultado queda sin enlace, marcado como no disponible.
    violation: Un reporte que no se genera por falta de observabilidad convierte una herramienta de apoyo en un bloqueo.
    source: AC4.4.6

  - id: BR1.4
    statement: Un caso que no se puede ejecutar por una causa ajena al código se registra como no medido, con su causa, y la corrida continúa.
    category: policy
    applies_to: Corredor de evaluaciones
    trigger: Cuando un caso falla por error del proveedor, cuota agotada, presupuesto agotado o tiempo máximo del corredor.
    logic: >
      SI un caso falla por una causa externa, ENTONCES su resultado queda con
      estado no medido y su causa, la corrida sigue con el caso siguiente, y ese
      resultado NO cuenta como fallo de calidad.
    violation: Contar un fallo de infraestructura como fallo de calidad contamina una métrica publicada.
    source: Decisión Q5 del diseño funcional de U1; regla de `project.md` sobre corridas no comparables

  - id: BR1.5
    statement: Una corrida con al menos un caso no medido se marca como no comparable, con su causa.
    category: constraint
    applies_to: Corrida de evaluación
    trigger: Al cerrar la corrida.
    logic: >
      SI algún resultado de la corrida tiene estado no medido, ENTONCES la
      corrida queda marcada como no comparable y declara la causa; la
      comparación contra la línea base no se publica como si fuera válida.
    violation: Comparar contra la línea base una corrida incompleta produce regresiones falsas.
    source: Decisión Q5 del diseño funcional de U1; `team.md`, compuerta en rojo por causa ajena

  - id: BR1.6
    statement: El subconjunto declarado es una lista versionada de identificadores de caso, con nombre y razón, y el reporte dice que la corrida es parcial y cuál subconjunto usó.
    category: policy
    applies_to: Corredor de evaluaciones
    trigger: Cuando la corrida se invoca con un subconjunto.
    logic: >
      SI la corrida nombra un subconjunto, ENTONCES ejecuta exactamente los
      casos de esa lista, en su orden, y el reporte declara el nombre del
      subconjunto.
    violation: Un subconjunto que no se declara hace que el lector tome una corrida parcial por completa.
    source: AC4.4.4; decisión Q2 del diseño funcional de U1

  - id: BR1.7
    statement: Dos corridas del mismo commit con el mismo subconjunto ejecutan el mismo conjunto de casos, en el mismo orden.
    category: constraint
    applies_to: Corredor de evaluaciones
    trigger: En cada corrida.
    logic: >
      SI el commit y el subconjunto son los mismos, ENTONCES la lista de casos
      ejecutados es idéntica, porque la selección sale de un archivo versionado
      y no de un filtro calculado.
    violation: Una selección que depende del orden o del momento hace incomparables dos corridas del mismo código.
    source: AC4.4.4

  - id: BR1.8
    statement: La duración de la corrida se mide siempre y se publica en el reporte.
    category: calculation
    applies_to: Corrida de evaluación
    trigger: Al cerrar la corrida.
    logic: SI la corrida termina, ENTONCES su duración queda registrada y aparece en el reporte, tanto si cumple la meta como si no.
    violation: Una duración que solo se publica cuando es buena deja de ser una medición.
    source: AC4.4.5, NFR17

  - id: BR1.9
    statement: Los ocho conjuntos de datos existen como archivos por caso con identificador estable y recuento declarado; un conjunto que todavía no se construye lo declara con su razón.
    category: validation
    applies_to: Manifiesto de conjuntos de datos
    trigger: Al validar el manifiesto, en cada corrida del guion de verificación.
    logic: >
      SI un conjunto figura en el manifiesto, ENTONCES existe con sus archivos y
      su recuento coincide; SI figura como no construido, ENTONCES trae la razón
      y no se le exigen archivos.
    violation: Un conjunto declarado y ausente hace que una métrica se publique sin su base.
    source: FR11.1, AC4.4.3

  - id: BR1.10
    statement: De los casos de audio se versionan el guion, las marcas de tiempo y el registro esperado; el audio nunca entra al repositorio y cada voz registra su consentimiento.
    category: policy
    applies_to: Conjunto de datos de audio
    trigger: Al agregar o actualizar un caso de audio.
    logic: >
      SI se agrega un caso de audio, ENTONCES su guion y su registro esperado se
      versionan, el archivo de audio se guarda fuera del historial, y el
      consentimiento de la voz queda registrado.
    violation: Una grabación de una persona real en el historial del repositorio no se puede retirar después.
    source: AC4.4.3, decisión D21 de User Stories

  - id: BR1.11
    statement: El corredor de evaluaciones nunca invoca un modelo de lenguaje para producir las respuestas del asegurado.
    category: constraint
    applies_to: Corredor de evaluaciones y asegurado simulado
    trigger: En cada turno de un caso de conversación.
    logic: >
      SI un caso necesita una respuesta del asegurado, ENTONCES sale del guion
      versionado del caso; NINGUNA sale de un modelo. La simulación con modelo
      existe solo como herramienta exploratoria, fuera de la compuerta.
    violation: Un asegurado simulado por modelo hace que dos corridas del mismo commit dejen de ser comparables.
    source: AC4.7.5

  - id: BR2.1
    statement: El asegurado simulado entrega la respuesta del campo que el turno del sistema declara, sin importar el orden en que se pregunten los campos.
    category: policy
    applies_to: Asegurado simulado
    trigger: En cada turno en que el sistema pide un campo.
    logic: >
      SI el turno declara el campo que pide, ENTONCES el respondedor busca en el
      guion la respuesta de ese campo y la entrega; el orden del guion no
      determina el orden de las respuestas.
    violation: Emparejar por el orden del guion rompe el caso en cuanto la agente pregunta en otro orden, que es la conducta normal.
    source: AC4.7.1; decisión Q1 del diseño funcional de U1

  - id: BR2.2
    statement: Si el turno pide un campo que el caso no tiene, el respondedor contesta que no sabe, en el idioma del caso, y el turno se registra como desvío con el identificador del caso.
    category: policy
    applies_to: Asegurado simulado
    trigger: Cuando el campo pedido no existe en el guion del caso.
    logic: >
      SI el campo pedido no está en el guion, ENTONCES la respuesta es la frase
      de desconocimiento del catálogo en el idioma del caso, y el contador de
      desvíos del resultado sube en uno.
    violation: Inventar una respuesta oculta que el sistema preguntó algo que el caso no contempla.
    source: AC4.7.2

  - id: BR2.3
    statement: Una corrección escrita para un bloque se entrega una sola vez, la primera vez que se lee la confirmación de ese bloque.
    category: policy
    applies_to: Asegurado simulado
    trigger: Cuando el sistema lee la confirmación de un bloque que tiene una corrección en el guion.
    logic: >
      SI el bloque tiene una corrección no entregada, ENTONCES el respondedor la
      entrega y la marca como entregada; SI ya la entregó, ENTONCES confirma sin
      volver a corregir.
    violation: Una corrección que se repite deja el caso en un bucle y nunca produce su registro esperado.
    source: AC4.7.3

  - id: BR2.4
    statement: Ante la misma secuencia de campos pedidos, el respondedor entrega la misma secuencia de respuestas.
    category: constraint
    applies_to: Asegurado simulado
    trigger: En cada corrida.
    logic: SI la secuencia de campos pedidos es la misma, ENTONCES la secuencia de respuestas es idéntica, sin ninguna fuente de azar.
    violation: Una respuesta que varía entre corridas hace que un caso parezca inestable cuando el sistema no cambió.
    source: AC4.7.4

  - id: BR3.1
    statement: Toda clave del catálogo existe en español y en inglés.
    category: validation
    applies_to: Catálogo de textos
    trigger: En cada corrida del guion de verificación.
    logic: SI una clave existe en un idioma, ENTONCES existe en el otro; una clave sin pareja falla el chequeo.
    violation: Una clave sin traducir deja una frase vacía o en el idioma equivocado frente a una persona.
    source: AC5.8.1, principio P12

  - id: BR3.2
    statement: Toda clave del catálogo tiene al menos un consumidor literal en el código.
    category: validation
    applies_to: Catálogo de textos
    trigger: En cada corrida del guion de verificación.
    logic: SI una clave no aparece literalmente en ningún archivo de código, ENTONCES el chequeo la reporta como clave sin consumidor.
    violation: Un catálogo que acumula claves muertas es el fallo que ya muestra la landing del proyecto.
    source: AC5.8.1

  - id: BR3.3
    statement: Ningún texto visible para una persona se escribe en línea en el código.
    category: constraint
    applies_to: Todo el código del aplicativo
    trigger: En cada corrida del guion de verificación.
    logic: SI un nodo, un adaptador o una plantilla contiene una cadena visible, ENTONCES el chequeo falla y nombra el archivo.
    violation: Una frase escrita en línea se salta la paridad por idioma y la revisión de formas prohibidas.
    source: AC5.8.2, convención de estilo del equipo

  - id: BR3.4
    statement: Las claves del catálogo son jerárquicas con puntos y siempre literales; nunca se construyen concatenando en tiempo de ejecución.
    category: constraint
    applies_to: Catálogo de textos y sus consumidores
    trigger: Al agregar una clave o al consumirla.
    logic: >
      SI el código necesita una familia de frases, ENTONCES enumera sus claves
      literales; NUNCA arma la clave a partir de un valor calculado.
    violation: Una clave construida en ejecución hace inexacto el chequeo de claves sin consumidor y obliga a una lista de excepciones que crece.
    source: Decisión Q3 del diseño funcional de U1

  - id: BR3.5
    statement: Una frase con versión mayor que uno declara el identificador de la decisión que la cambió, y la lista de cambios pendientes de llevar a la guía de voz se deriva del catálogo.
    category: validation
    applies_to: Catálogo de textos
    trigger: Al validar el catálogo.
    logic: >
      SI una entrada tiene versión mayor que uno SIN identificador de decisión,
      ENTONCES el chequeo falla; la lista de pendientes se genera con todas las
      entradas que tienen decisión y difieren de la guía.
    violation: Una frase cambiada sin su razón deja la guía de voz y el producto contándose historias distintas.
    source: AC5.8.3; decisión Q4 del diseño funcional de U1

  - id: BR3.6
    statement: Ninguna frase del catálogo contiene una de las formas prohibidas de la lista versionada.
    category: validation
    applies_to: Catálogo de textos
    trigger: En cada corrida del guion de verificación.
    logic: >
      SI una frase coincide con una forma prohibida —trato con género, plazos o
      llamadas que la demostración no cumple, transferencias en vivo, o la jerga
      que la guía prohíbe— ENTONCES el chequeo falla y nombra la clave.
    violation: Una promesa que la demostración no cumple es exactamente lo que el proyecto declara que no hará.
    source: AC5.8.4, principio P7
```

## Resumen

| Grupo | Reglas | De qué responden |
| --- | --- | --- |
| BR1.x | 11 reglas | El corredor de evaluaciones: un solo comando, qué pasa cuando falta algo, subconjuntos reproducibles, duración medida y ningún modelo en la compuerta |
| BR2.x | 4 reglas | El asegurado simulado: responde por campo, dice que no sabe, corrige una sola vez y es determinista |
| BR3.x | 6 reglas | El catálogo de textos: paridad, claves con consumidor, nada en línea, claves literales, versión con su decisión y formas prohibidas |

Tres reglas no nacen de un criterio de aceptación sino de decisiones de este
diseño, y por eso se declaran aparte en la trazabilidad: BR1.4 y BR1.5 (qué pasa
con un caso que no se puede medir) y BR3.4 (claves siempre literales).
