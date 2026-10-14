# Reglas — U18 `voice-spanish`

Veintiuna reglas, repartidas en cinco familias: el idioma de arranque, la
petición de cambio, la detección automática, el idioma que no se atiende y la
paridad entre los dos.

Dos llevan `[bloquea]`. Una es de estado —cambiar de idioma no pierde nada de lo
confirmado— y la otra es de aislamiento por otro nombre: el idioma del caso no lo
mueve un turno, porque moverlo sería la forma de RT-10 con dos palabras.

```yaml
rules:
  # --- El idioma de arranque (US1.28) -----------------------------------------
  - id: BR1.1
    statement: Una llamada sin idioma elegido arranca en el de la aseguradora.
    category: policy
    applies_to: "La apertura de una llamada"
    trigger: "Al abrir la sesión de voz."
    logic: >
      El cuerpo de abrir lleva el idioma **solo cuando la persona lo eligió**. La
      consola lo sabe porque el selector de U6 distingue las tres procedencias; el
      servidor no puede saberlo, así que no lo adivina: sin campo, usa
      `default_language` de la carpeta de la aseguradora.
    violation: "La prueba de AC1.28.4 falla: Stonecroft abre en inglés."
    source: AC1.28.4, C-08, C-25

  - id: BR1.2
    statement: Las dos configuraciones de voz de una aseguradora declaran la misma identidad.
    category: constraint
    applies_to: "La carpeta de cada aseguradora"
    trigger: "Al cargar la configuración, y en cada corrida del chequeo."
    logic: >
      No es conducta de código: es una propiedad de la carpeta versionada. La voz
      de español y la de inglés nombran el mismo identificador, o dos de la misma
      voz localizada declarados así en ADR-008. Quien cambie una y no la otra parte
      a la agente en dos personas distintas a mitad de conversación.
    violation: "La prueba de AC1.28.2 falla nombrando la aseguradora."
    source: AC1.28.2, ADR-008, C-25

  - id: BR1.3
    statement: El nombre de la agente sale del catálogo por idioma, nunca del código.
    category: constraint
    applies_to: "La composición de la apertura"
    trigger: "Al componer cualquier frase que la nombre."
    logic: >
      Catalina en inglés y Valentina en español salen de la misma clave
      `insurer.agent.name` resuelta en el idioma del turno. Ya funciona así desde
      U16; se escribe como regla porque es lo que impide que un día alguien meta el
      nombre en una f-string y la agente cambie de nombre al cambiar de idioma.
    violation: "El chequeo de claves sin consumidor deja de encontrar la clave."
    source: AC1.28.1, convención 4 de `team.md`

  # --- La petición de cambio (US1.31) -----------------------------------------
  - id: BR2.1
    statement: La petición explícita de cambio de idioma la reconoce código, no un modelo.
    category: constraint
    applies_to: "Cada turno de la persona"
    trigger: "Antes de decidir en qué idioma se responde."
    logic: >
      Una lista cerrada y versionada de formas de pedirlo en los dos idiomas. Es la
      misma razón por la que la transición del grafo no la decide un LLM: una
      petición de cambio de idioma cambia el estado de la conversación, y eso se
      decide con una lista que se puede leer en un diff.
    violation: "La prueba de AC1.31.1 falla."
    source: AC1.31.1, AC1.31.2, ADR-003

  - id: BR2.2
    statement: La petición manda sobre el detector.
    category: policy
    applies_to: "El turno que pide el cambio"
    trigger: "Cuando el turno coincide con la lista de peticiones."
    logic: >
      "In English, please" está dicho **en inglés** y el detector lo leería como
      inglés por accidente; "¿me lo puede decir in English?" está dicho en español
      y el detector diría español. Los dos son la misma petición. Si el orden fuera
      el contrario, la petición funcionaría en un sentido y no en el otro, y nadie
      sabría por qué.
    violation: "La prueba de la petición dicha en el idioma actual falla."
    source: AC1.31.1, AC1.31.2

  - id: BR2.3
    statement: "[bloquea] Cambiar de idioma no pierde ningún bloque confirmado."
    category: constraint
    applies_to: "El estado del caso al cambiar de idioma"
    trigger: "En cada cambio, pedido o automático."
    logic: >
      La llamada no se reinicia, el caso no se vuelve a abrir y lo confirmado sigue
      confirmado. Es lo que separa "cambiar de idioma" de "empezar otra vez", y la
      persona que pide el cambio a mitad de un reporte no tiene por qué pagarlo
      repitiendo lo que ya dijo.
    violation: "La prueba de AC1.31.1 falla: la completitud baja tras el cambio."
    source: AC1.31.1

  - id: BR2.4
    statement: El turno que pide el cambio se contesta ya en el idioma nuevo.
    category: policy
    applies_to: "La respuesta al turno de la petición"
    trigger: "Al reconocer la petición."
    logic: >
      AC1.31.1 dice "el turno siguiente es en inglés", y el turno siguiente a la
      petición es su propia respuesta. Contestar la petición en el idioma viejo y
      cambiar después obligaría a la persona a oír una frase en el idioma que acaba
      de pedir dejar.
    violation: "La prueba de AC1.31.1 falla."
    source: AC1.31.1

  - id: BR2.5
    statement: La frase que la agente está diciendo no se corta para cambiar de idioma.
    category: policy
    applies_to: "La síntesis en curso"
    trigger: "Cuando la petición llega mientras la agente habla."
    logic: >
      Si la persona interrumpió, la interrupción ya la calla por el camino de U16
      (BR4.1) y esta regla no aplica. Si no interrumpió, la frase termina. Cortar la
      síntesis a mitad de palabra suena a fallo y no a atención.
    violation: "La prueba de la petición durante la síntesis falla."
    source: AC1.31.1, BR4.1 de U16

  - id: BR2.6
    statement: La identidad de voz no cambia con el idioma.
    category: constraint
    applies_to: "La síntesis después de un cambio"
    trigger: "En el primer turno tras cambiar."
    logic: >
      La misma persona sigue hablando. Cambiar de voz al cambiar de idioma
      convertiría un cambio de idioma en un cambio de interlocutor, que es
      exactamente lo contrario de lo que la historia pide.
    violation: "La prueba de AC1.31.3 falla."
    source: AC1.31.3, AC1.28.2

  # --- La detección automática (US1.32, Should) -------------------------------
  - id: BR3.1
    statement: La detección automática es un dato de la aseguradora y viene apagada.
    category: constraint
    applies_to: "La configuración de voz de cada aseguradora"
    trigger: "Al cargar la configuración."
    logic: >
      AC1.31.5 escribe explícitamente la conducta con la detección apagada, así que
      las dos ramas existen en el criterio y la que decide es la carpeta versionada,
      nunca un `if` por aseguradora (convención 9). Apagada por omisión porque
      US1.32 es la última historia en la regla de corte del PRD: si se corta, lo que
      queda es la conducta que ya está escrita.
    violation: "La prueba de AC1.31.5 falla con la detección activa sin declararlo."
    source: AC1.31.5, US1.32, convención 9 de `team.md`

  - id: BR3.2
    statement: Hacen falta dos turnos seguidos en el otro idioma para cambiar solo.
    category: policy
    applies_to: "La detección automática"
    trigger: "Con la detección activa, en cada turno con señal suficiente."
    logic: >
      Un turno suelto no es un cambio de idioma: es una frase. AC1.32.1 pide que la
      respuesta a t+1 ya sea en el otro idioma, y ese "t+1" es el segundo, no el
      primero. Con uno solo, una cita o una frase hecha movería la conversación
      entera.
    violation: "La prueba de AC1.32.1 falla, o la de AC1.32.2 pasa a cambiar de idioma."
    source: AC1.32.1

  - id: BR3.3
    statement: Una palabra suelta, un nombre propio o una marca nunca cambian el idioma.
    category: constraint
    applies_to: "Todo turno, con la detección activa o apagada"
    trigger: "Antes de mirar el detector."
    logic: >
      El piso de cuatro palabras descarta "okay", "el Toyota Highlander" y un nombre
      propio antes de que ningún detector los vea. No es un número elegido: es donde
      un mensaje deja de ser un identificador y empieza a ser una frase, medido en
      U13 --"Marcela Rios" recibía 0,92 de confianza en español y cambiaba el idioma
      de la conversación--.
    violation: "La prueba de AC1.32.2 falla."
    source: AC1.32.2, AC1.2.3, `chat/language.py`

  - id: BR3.4
    statement: El detector vive en un módulo hoja y hay uno solo en el proyecto.
    category: constraint
    applies_to: "Los dos canales"
    trigger: "En cada corrida del lint."
    logic: >
      Dos detectores con los mismos umbrales son dos números que se separan el día
      que alguien afina uno, en un proyecto que publica adherencia de idioma **por
      idioma**. Sube a `untangle/language.py` --hoja, como `base.py` y
      `surface_spec.py`-- y los dos canales lo consumen desde ahí; no queda
      reexportador, porque dos caminos al mismo sitio es como uno se queda atrás.
    violation: "Aparece un segundo módulo con umbrales de idioma."
    source: D1, contrato de capas

  # --- El idioma que no se atiende (AC1.31.4) ---------------------------------
  - id: BR4.1
    statement: La llamada nunca se responde en un tercer idioma, y nunca se ignora el turno.
    category: policy
    applies_to: "El turno que no se pudo entender"
    trigger: "Confianza baja o transcripción vacía."
    logic: >
      La llamada sigue en su idioma. Es la misma regla que el chat ya cumple (BR2.3
      de U13) y la que impide que la demostración prometa lo que no atiende.
    violation: "La prueba de AC1.31.4 falla."
    source: AC1.31.4, BR2.3 de U13

  - id: BR4.2
    statement: En la voz, un tercer idioma no se distingue de no haber entendido, y el disparador es el mismo.
    category: constraint
    applies_to: "La escalera de no haber entendido"
    trigger: "Confianza baja dos turnos seguidos."
    logic: >
      El reconocedor corre en modo multiidioma y devuelve el idioma de cada
      transcrito, pero el puerto de C-16 lo tipa `Locale | None`: cualquier idioma
      que no sea español o inglés **se colapsa a nulo**, igual que si el proveedor
      no lo hubiera dicho. Y lo que llega transcrito de alguien hablando portugués
      no es texto en portugués: son palabras que se le parecieron. No se amplía el
      puerto --es la misma decisión que U16 tomó con el `speech_final`-- así que el
      disparador es el que AC1.31.4 escribe en su *Dado*: baja confianza dos veces.
    violation: "Aparece una rama que pretende reconocer un tercer idioma en la voz."
    source: AC1.31.4, AC1.31.5, D6, BR3.1 de U15

  - id: BR4.3
    statement: Esa frase es una sola clave por idioma con las dos lenguas dentro.
    category: constraint
    applies_to: "El catálogo"
    trigger: "Al componerla."
    logic: >
      Quien la oye la oye una vez, y componerla de dos claves que alguien concatena
      deja que un día salga media. La clave lleva las dos frases, dice que se puede
      pedir el cambio y ofrece que una persona revise el caso.
    violation: "El chequeo de paridad o el de claves sin consumidor falla."
    source: AC1.31.4, convención 4 de `team.md`
  - id: BR4.4
    statement: El segundo peldaño dice la frase de los dos idiomas; el primero y el tercero no cambian.
    category: policy
    applies_to: "La escalera de U16"
    trigger: "En el segundo turno seguido sin entender."
    logic: >
      Primero "no le escuché bien"; segundo, lo que la demostración atiende y que
      se puede pedir el cambio; tercero, la oferta de guardar el caso o pasarlo a un
      ajustador. Repetir la misma frase dos veces no ayuda a quien está al
      teléfono: es lo que hace colgar a la gente.

      **Dos criterios aprobados describen este momento distinto** --AC1.29.3 pide
      repetir y AC1.31.4 pide la frase de los dos idiomas-- y la elección está en
      `functional-design-questions.md`, Q2, con su recomendación. Cambiarla es una
      línea.
    violation: "La prueba del segundo peldaño falla."
    source: AC1.31.4, AC1.29.3, Q2


  # --- La paridad entre los dos idiomas (US1.29, US1.30) ----------------------
  - id: BR5.1
    statement: "[bloquea] El idioma del caso no lo cambia un turno."
    category: constraint
    applies_to: "El registro del caso"
    trigger: "En cada cambio de idioma de la llamada."
    logic: >
      El cambio escribe el idioma de la **llamada** y no el del caso. Un caso
      abierto en español y terminado en inglés aparece en la bandeja como español,
      a propósito: si el caso cambiara con el último turno, alguien movería su caso
      de cola diciendo dos palabras, que es la forma de RT-10. Lo que queda en los
      dos idiomas es la transcripción, turno por turno.
    violation: "La prueba de RT-10 falla: el caso cambia de idioma."
    source: RT-10, D4, AC1.31.1

  - id: BR5.2
    statement: Ninguna pieza de la llamada se ramifica por idioma dentro de esta unidad.
    category: constraint
    applies_to: "Todo lo que U18 escriba"
    trigger: "En cada revisión de tanda."
    logic: >
      Una rama `if language == "es"` aquí sería la señal de que la pieza de U16
      estaba escrita para un solo idioma. La corrección va allí, donde el defecto
      está, y no aquí, donde nadie lo buscaría. Lo que esta unidad añade son las
      piezas que **solo existen** cuando hay dos idiomas.
    violation: "Aparece una rama por idioma en el código de esta unidad."
    source: US1.29, US1.30, D9

  - id: BR5.3
    statement: Las metas se reportan por idioma y nunca como promedio combinado.
    category: constraint
    applies_to: "El reporte de la corrida"
    trigger: "En cada corrida que incluya casos en los dos idiomas."
    logic: >
      Es P12 y ya lo cumple el corredor: lo que esta unidad añade son los casos en
      español para que la columna exista. Sin grabaciones, la columna se declara
      **no medida**, nunca se omite ni se rellena con la del otro idioma.
    violation: "El reporte muestra un promedio, o una columna vacía sin decirlo."
    source: P12, AC1.30.5, AC1.29.x

  - id: BR5.4
    statement: El registro de la voz en español se comprueba por código donde se puede.
    category: constraint
    applies_to: "El catálogo en español y las transcripciones de las corridas"
    trigger: "En cada corrida del guion de verificación."
    logic: >
      Ninguna forma de tuteo y "pues" como mucho una vez por turno: un chequeo de
      contenido con identificador estable, como los tres que ya existen. La otra
      mitad --la calidez del usted, el registro paisa ligero-- la juzga el juez, y
      si se descalibra ese criterio se reporta "no medida" mientras esta mitad sigue
      bloqueando.
    violation: "Aparece una forma de tuteo en el catálogo en español."
    source: AC1.28.3, D8
```

## Resumen

| Familia | Reglas | `[bloquea]` |
| --- | --- | --- |
| El idioma de arranque | BR1.1 – BR1.3 | — |
| La petición de cambio | BR2.1 – BR2.6 | BR2.3 |
| La detección automática | BR3.1 – BR3.4 | — |
| El idioma que no se atiende | BR4.1 – BR4.4 | — |
| La paridad entre los dos | BR5.1 – BR5.4 | BR5.1 |

## Sources

- `../../../inception/user-stories/stories.md` — US1.28 a US1.32
- `functional-design-questions.md` — las nueve decisiones
- `../../u16-voice-call/functional-design/rules.md` — las 38 que esta unidad no repite

## Assumptions & Open Questions

None.
