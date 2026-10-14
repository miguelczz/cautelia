# Reglas — U17 `voice-public-link`

Catorce reglas en cuatro familias: los dos carriles, la voz, la consola y los topes del
proveedor.

Dos llevan `[bloquea]`: que ninguna llamada pública se abra sin pasar los dos carriles,
y que la voz no cambie por presupuesto a mitad de llamada. La primera protege el
dinero; la segunda, lo único que quien prueba va a recordar de la voz.

```yaml
rules:
  # --- Los dos carriles diarios (US5.12) --------------------------------------
  - id: BR1.1
    statement: "[bloquea] Ninguna llamada pública se abre sin pasar el carril del visitante y el del sitio."
    category: constraint
    applies_to: "La apertura de una llamada pública"
    trigger: "Antes de pedir el micrófono."
    logic: >
      Son los dos carriles que el contrato ya declara y que hasta ahora nadie aplicaba:
      `VoiceOffCode` los tiene con su frase y su comentario dice que servirlos sin
      aplicarlos sería prometer un límite que nada hace cumplir. Un fallo aquí no da
      una pantalla fea: da una factura.
    violation: "Una llamada se abre con el carril del visitante o el del sitio agotado."
    source: AC5.12.3, FR3.9

  - id: BR1.2
    statement: La decisión de los dos carriles es pura y devuelve cuál carril rechazó, nunca la frase.
    category: constraint
    applies_to: "La decisión de admisión"
    trigger: "En cada intento de llamada."
    logic: >
      Recibe la configuración, lo que los contadores ya dicen y el reloj como
      argumentos; no abre sesión, no llama a nadie y no mira el reloj del proceso. Es
      la forma que los cinco controles del chat ya probaron: deja medir su presupuesto
      sin depender de la máquina y cubrir los bordes sin base de datos. La frase sale
      del catálogo en el punto único de salida.
    violation: "La decisión consulta la base, mira el reloj del proceso o devuelve texto."
    source: FD-U17-1; la forma de `chat/limits.py`

  - id: BR1.3
    statement: Una retoma dentro de la ventana no consume la llamada del día, pero sí cuenta contra las del sitio y contra el techo de gasto.
    category: policy
    applies_to: "Los contadores"
    trigger: "Cuando se vuelve a llamar dentro de la ventana de retoma."
    logic: >
      La asimetría es el diseño, no un descuido: el carril del visitante protege que
      quien prueba pueda terminar lo que empezó, y el del sitio y el techo protegen el
      dinero. Tratarlos igual sacrificaría uno de los dos.
    violation: "Una retoma gasta la llamada del día, o no cuenta contra el sitio o contra el techo."
    source: AC5.12.2

  - id: BR1.4
    statement: El techo de gasto no depende del carril por visitante, y la consola dice "desde esta conexión".
    category: constraint
    applies_to: "El cálculo del techo y el texto de la consola"
    trigger: "Al calcular el techo y al mostrar los límites."
    logic: >
      Un visitante cambia de navegador o de red, así que este carril no es un control
      de gasto. Decir "por persona" prometería un control que no existe.
    violation: "El techo se calcula contando visitantes, o la consola dice «por persona»."
    source: AC5.12.6

  - id: BR1.5
    statement: Los dos carriles son configuración por aseguradora, aditiva y con valor por omisión.
    category: constraint
    applies_to: "`CallConfig`"
    trigger: "Al cargar la configuración."
    logic: >
      Cambiar los valores y desplegar no cambia código, y una aseguradora que todavía
      no los declara sigue cargando igual. Es lo que el propio `CallConfig` dejó
      escrito para esta unidad, y la forma con la que llegó la configuración del chat.
    violation: "Los valores están en el código, o una configuración sin ellos deja de cargar."
    source: AC5.12.4, FD-U17-2

  # --- La voz (US5.11) --------------------------------------------------------
  - id: BR2.1
    statement: "[bloquea] La voz no cambia por presupuesto a mitad de llamada."
    category: constraint
    applies_to: "Una llamada en curso"
    trigger: "Cuando la llamada consume su reserva."
    logic: >
      Se decide una vez, antes de la primera frase, y la llamada entera se atiende con
      esa voz. Cambiar a mitad suena a fallo aunque sea un ahorro, y es lo único que
      quien prueba la voz va a recordar. Un cambio a mitad solo ocurre cuando el
      proveedor falla, y eso es de U16.
    violation: "Una llamada empieza con una voz y termina con otra por presupuesto."
    source: AC5.11.2

  - id: BR2.2
    statement: La elección de la voz se cablea a la decisión que ya existe, no se reescribe.
    category: constraint
    applies_to: "La apertura de la llamada"
    trigger: "Antes de la primera frase."
    logic: >
      `quota.voice_mode(remaining, reserve)` ya existe, es pura y responde "respaldo"
      cuando cualquiera de los dos datos está sin medir. Producción tiene
      `VoiceMode.PRIMARY` escrito a mano en cuatro sitios, y lo que falta es el cable.
      Reescribir la decisión sería un segundo sitio donde decidir lo mismo.
    violation: "Queda un `VoiceMode` escrito a mano en el camino de una llamada pública."
    source: FD-U17-5; `voice/models.py`, que ya dice que esto es de U17

  - id: BR2.3
    statement: El aviso de la voz de respaldo se da antes de la primera frase y dice que puede sonar distinta en cada idioma.
    category: policy
    applies_to: "La consola"
    trigger: "Cuando la llamada se abre en modo respaldo."
    logic: >
      Es la excepción declarada a la voz única en los dos idiomas: se avisa, y se avisa
      antes, porque enterarse a mitad de la llamada es enterarse de que algo va mal.
    violation: "La llamada de respaldo empieza sin aviso, o el aviso no menciona el idioma."
    source: AC5.11.1, AC5.11.3, D17

  - id: BR2.4
    statement: Con el presupuesto restante o la reserva sin medir, se abre con la voz de respaldo.
    category: constraint
    applies_to: "La decisión de la voz"
    trigger: "Cuando alguno de los dos datos no está medido."
    logic: >
      Afirmar que cabe lo que no se sabe cuánto cuesta es la forma de pasarse del techo
      sin haberlo decidido. Cerrado para lo que cuesta dinero.
    violation: "Se abre con la voz principal sin saber si el presupuesto la cubre."
    source: AC5.11.1; `covers_primary_voice`

  # --- La consola pública (US4.17) -------------------------------------------
  - id: BR3.1
    statement: La consola dice la disponibilidad y los límites antes de pedir el micrófono, y si no hay voz dice por qué y ofrece el chat.
    category: policy
    applies_to: "La consola pública"
    trigger: "Al abrirla."
    logic: >
      Pedir el micrófono para después decir que no hay voz es la peor pantalla posible.
      Los cuatro motivos son una lista cerrada con su frase, y existen justamente para
      no tener que hacerlo.
    violation: "La consola pide el micrófono antes de saber si hay voz, o no dice el motivo."
    source: AC4.17.1, AC5.12.3

  - id: BR3.2
    statement: El estado, el tiempo restante y el botón de colgar están siempre visibles, también a 360 px.
    category: policy
    applies_to: "La consola durante la llamada"
    trigger: "Mientras la llamada está en curso."
    logic: >
      Quien tiene una sola llamada al día y tres minutos necesita ver cuánto le queda
      sin buscarlo. Y colgar no puede quedar debajo del pliegue.
    violation: "Alguno de los tres deja de verse al desplazar, o a 360 px."
    source: AC4.17.3

  - id: BR3.3
    statement: La latencia que la consola muestra coincide con los eventos de la traza de ese turno.
    category: constraint
    applies_to: "La latencia del último turno"
    trigger: "Al terminar un turno."
    logic: >
      Dos números con el mismo nombre que no coinciden convierten la consola en una
      pantalla que no se puede creer, y esta es la cifra que quien evalúa va a
      comprobar.
    violation: "La consola muestra una latencia que la traza de ese turno no respalda."
    source: AC4.17.5

  - id: BR3.4
    statement: Al terminar, la consola dice dónde quedó el caso, y si quedó esperando al asegurado ofrece retomarlo o pasarlo ya a un ajustador.
    category: policy
    applies_to: "El final de la llamada"
    trigger: "Al colgar, al cortarse o al llegar al límite."
    logic: >
      Número de caso, estado, y el enlace firmado si quedó derivado o cerrado. Y el que
      quedó esperando no puede quedarse sin salida: o vuelve dentro de la ventana, o lo
      pasa a un ajustador y ve su enlace.
    violation: "La llamada termina sin decir dónde quedó el caso, o un caso esperando queda sin salida."
    source: AC4.17.6, D12

  # --- Los topes del proveedor (US5.12) --------------------------------------
  - id: BR4.1
    statement: Cada proveedor de pago tiene su tope configurado en el proveedor, escrito en una tabla versionada con la fecha de su última comprobación.
    category: constraint
    applies_to: "La tabla de topes"
    trigger: "En cada hito y en el checklist del segundo día."
    logic: >
      Un límite que vive solo en la aplicación falla abierto cuando lo que falla es la
      aplicación. Y un tope configurado hace tres meses y no comprobado no es un tope:
      es un recuerdo. Por eso la fecha es una columna y no una nota al pie.
    violation: "Un proveedor de pago sin fila, o una fila sin fecha de comprobación."
    source: AC5.12.5, y la práctica afirmada de topes por clave
```

## Trazabilidad

| Familia | Reglas | `[bloquea]` |
| --- | --- | --- |
| Los dos carriles diarios | BR1.1 – BR1.5 | BR1.1 |
| La voz | BR2.1 – BR2.4 | BR2.1 |
| La consola pública | BR3.1 – BR3.4 | — |
| Los topes del proveedor | BR4.1 | — |

## Sources

- `functional-design-questions.md` — las diez decisiones
- `../../../inception/user-stories/stories.md` — US5.12, US5.11, US4.17

## Assumptions & Open Questions

None.
