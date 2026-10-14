# Reglas — U20 `demo-operations`

Trece reglas en tres familias: el aprovisionamiento, el reinicio y su fallo.

Dos llevan `[bloquea]`: que tras el reinicio no quede ningún dato de visitante —tampoco
en el backend de trazas— y que el registro de gasto sobreviva. La primera es la promesa
que hace publicable la demo; la segunda es lo único que no se puede volver a calcular.

```yaml
rules:
  # --- Aprovisionar (US5.1) ---------------------------------------------------
  - id: BR1.1
    statement: La carpeta se valida entera antes de crear nada, y el fallo nombra el archivo y el campo.
    category: constraint
    applies_to: "El comando de aprovisionar"
    trigger: "Al empezar."
    logic: >
      Una aseguradora a medias no la borra nada y no la completa nada: se queda
      existiendo mal, y quien mire después creerá que el aprovisionamiento funciona.
      Nombrar el archivo y el campo es la diferencia entre un error que se arregla en un
      minuto y uno que se investiga una hora.
    violation: "El comando crea algo y luego falla, o falla sin nombrar el archivo y el campo."
    source: AC5.1.3

  - id: BR1.2
    statement: Aprovisionar es idempotente: la misma configuración deja el mismo estado y no duplica nada.
    category: constraint
    applies_to: "El comando de aprovisionar"
    trigger: "Al correrlo sobre una aseguradora ya aprovisionada."
    logic: >
      Es la mitad de su valor: un comando que no se puede repetir es un comando que
      nadie corre con confianza, y el que lo corre a medias deja el estado peor que
      antes.
    violation: "Correrlo dos veces duplica algo, o el estado resultante difiere."
    source: AC5.1.5

  - id: BR1.3
    statement: El aprovisionamiento invoca la tarea de ingesta que ya existe, no escribe su propia ingesta.
    category: constraint
    applies_to: "El paso de corpus"
    trigger: "Al aprovisionar."
    logic: >
      El comentario de esa tarea ya lo dejó escrito para esta unidad. Una segunda
      ingesta sería un segundo sitio donde el corpus se indexa distinto, y la diferencia
      aparecería como una cita que no se encuentra.
    violation: "El aprovisionamiento indexa el corpus por su cuenta."
    source: FD-U20-4; el comentario de `corpus:ingest`

  - id: BR1.4
    statement: Agregar una aseguradora no cambia ningún archivo de código.
    category: constraint
    applies_to: "El commit que la agrega"
    trigger: "Al revisar el cambio."
    logic: >
      Es la demostración de que el sistema es multi-tenant de verdad, y se comprueba con
      el chequeo que ya corre: ningún identificador de aseguradora fuera del cargador de
      configuración y de las fixtures.
    violation: "El commit que agrega una aseguradora toca código del aplicativo."
    source: AC5.1.1, AC5.1.4

  # --- El reinicio nocturno (US5.15) -----------------------------------------
  - id: BR2.1
    statement: "[bloquea] Tras el reinicio no queda ningún dato de visitante, tampoco en el backend de trazas."
    category: constraint
    applies_to: "Todo lo que dejó un visitante"
    trigger: "Al terminar el reinicio."
    logic: >
      Es la promesa que hace publicable la demo: lo que entra por una superficie pública
      es dato de una persona real aunque el corpus sea sintético, y la retención está
      acotada por esta corrida. El backend de trazas se nombra aparte porque es el sitio
      que se olvida: no está en la base y no sale en una consulta.
    violation: "Después del reinicio queda un caso, una transcripción, un enlace o una traza de visitante."
    source: AC5.15.1, NFR19

  - id: BR2.2
    statement: "[bloquea] El registro de gasto sobrevive al reinicio."
    category: constraint
    applies_to: "La ventana de presupuesto y el libro mayor"
    trigger: "Al terminar el reinicio."
    logic: >
      Es lo único que no se puede volver a calcular: el gasto ya ocurrió, y un
      acumulado que empieza en cero cada noche convierte el techo en un adorno. Lo que
      se conserva no lo decide esta unidad: lo declara el purgador de su dueño, que
      borra los contadores de visitante y de sesión y conserva el del sitio, la ventana
      y el libro mayor.
    violation: "Después del reinicio el acumulado de gasto bajó."
    source: AC5.15.1; el purgador de U5 y su razón escrita

  - id: BR2.3
    statement: El reinicio no borra ninguna tabla: llama a los purgadores registrados, en el orden del registro.
    category: constraint
    applies_to: "El reinicio"
    trigger: "En cada corrida."
    logic: >
      El registro está escrito a mano, una línea por dueño, y nunca se descubre solo: un
      descubrimiento deja de encontrar lo que alguien nombró distinto. Una consulta de
      borrado escrita aquí sería el sitio donde la retención deja de estar acotada sin
      que nadie lo note, porque nadie la revisaría al añadir una tabla.
    violation: "El reinicio ejecuta una sentencia de borrado propia."
    source: UG-3, FD-U20-1

  - id: BR2.4
    statement: La orquestación del reinicio es pura sobre el contrato, recibe el reloj y no abre sesión.
    category: constraint
    applies_to: "La orquestación"
    trigger: "En cada corrida."
    logic: >
      Recibe los purgadores, el reloj y el corte como argumentos y devuelve qué se borró
      y qué falló. Es lo que la deja probable entera con dobles y sin base, y lo que
      permite comprobar el camino del fallo sin tener que romper una base de verdad.
    violation: "La orquestación abre una sesión o mira el reloj del proceso."
    source: FD-U20-2

  - id: BR2.5
    statement: Ningún número de caso y ningún enlace firmado se repite después del reinicio.
    category: constraint
    applies_to: "Los identificadores emitidos"
    trigger: "Al emitir uno nuevo tras un reinicio."
    logic: >
      Un número repetido haría que un enlace viejo abriera un caso nuevo de otra
      persona. Es una fuga de datos con forma de coincidencia.
    violation: "Un número de caso o un enlace emitido después coincide con uno de antes."
    source: AC5.15.4

  - id: BR2.6
    statement: Una conversación abierta a la hora del reinicio recibe el aviso del catálogo y su mensaje siguiente abre un caso nuevo, sin error.
    category: policy
    applies_to: "Las conversaciones vivas"
    trigger: "Cuando el reinicio borra su caso."
    logic: >
      Sin el aviso, quien estaba escribiendo ve que su conversación dejó de tener
      sentido y no sabe por qué. Y sin abrir un caso nuevo, el mensaje siguiente apunta
      a un caso que ya no existe, que es un error que la persona no puede arreglar.
    violation: "Una conversación viva no recibe el aviso, o su mensaje siguiente falla."
    source: AC5.15.3

  # --- Cuando el reinicio falla (AC5.15.5) -----------------------------------
  - id: BR3.1
    statement: Cada corrida del reinicio deja su registro, y un fallo sale como alerta y se reintenta.
    category: constraint
    applies_to: "Cada corrida"
    trigger: "Al terminar, bien o mal."
    logic: >
      Sin registro no hay nada que alertar ni con qué comparar, y el dato que dice si la
      demo estuvo limpia anoche no existiría. Un fallo silencioso del reinicio es la
      forma más discreta de acumular datos de personas reales.
    violation: "Una corrida termina sin registro, o un fallo no levanta alerta."
    source: AC5.15.5

  - id: BR3.3
    statement: Una conversación o una llamada ya abierta termina normalmente cuando las superficies se estrechan.
    category: policy
    applies_to: "Lo que ya estaba abierto"
    trigger: "Cuando pasan 24 horas sin reinicio exitoso."
    logic: >
      Se dejan de aceptar **casos nuevos**, que es lo que el criterio dice, y quien está
      a mitad de reportar un siniestro lo termina: perder un reporte por un fallo de
      operación que no es suyo es un precio que no paga quien lo causó. El compromiso
      que esto acepta está escrito: los datos de esa conversación se quedan una noche
      más. Lo que mantiene la ventana acotada es que la alerta ya salió y el reintento
      sigue corriendo. La demo se estrecha en vez de caerse.
    violation: "Una conversación o llamada abierta se corta por el estrechamiento, o se aceptan casos nuevos."
    source: AC5.15.5, respuesta Q1

  - id: BR3.2
    statement: Sin un reinicio exitoso en 24 horas, el chat y la voz públicos dejan de aceptar casos nuevos con el mensaje del catálogo, y el reloj cuenta desde el último exitoso.
    category: constraint
    applies_to: "Las superficies públicas"
    trigger: "Cuando pasan 24 horas sin reinicio exitoso."
    logic: >
      El reloj es el del último **exitoso** y no el del último intento: tres intentos
      fallidos seguidos no reinician el contador, y ese es justo el caso en el que la
      retención dejó de estar acotada. Cerrar casos nuevos es degradar a propósito, que
      es mejor que seguir recibiendo datos que nadie va a borrar.
    violation: "Se aceptan casos nuevos con más de 24 horas sin reinicio exitoso, o el contador se reinicia con un intento fallido."
    source: AC5.15.5
```

## Trazabilidad

| Familia | Reglas | `[bloquea]` |
| --- | --- | --- |
| Aprovisionar | BR1.1 – BR1.4 | — |
| El reinicio nocturno | BR2.1 – BR2.6 | BR2.1, BR2.2 |
| Cuando falla | BR3.1 – BR3.3 | — |

## Sources

- `functional-design-questions.md` — la pregunta y las nueve decisiones
- `../../../inception/user-stories/stories.md` — US5.1, US5.15

## Assumptions & Open Questions

None.
