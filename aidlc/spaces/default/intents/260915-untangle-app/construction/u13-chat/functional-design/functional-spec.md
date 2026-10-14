# Diseño funcional — U13 `chat`

U13 es la primera superficie pública del aplicativo. Doce unidades construyeron el
aislamiento, la redacción, las citas verificadas y el grafo; esta unidad las pone
detrás de una página que cualquiera puede abrir, y su trabajo es no deshacer nada de
eso al hacerlo.

## El recorrido de un turno por el chat

1. **Llega el mensaje** con la clave del navegador y el origen. Antes de nada, los
   límites: por sesión, por origen y por día, más el intervalo mínimo y el tamaño
   máximo. Lo rechazado **no llega al modelo** (BR3.1, BR3.2).
2. **La conversación se resuelve** por el resumen de la clave del navegador: su
   aseguradora, su idioma y su caso si ya tiene uno.
3. **Si es el primer mensaje**, la divulgación ya se emitió al cargar la página
   (BR1.1) y quedó registrada (BR1.2). El primer mensaje del visitante no es la
   primera cosa que se ve.
4. **Se resuelve el idioma** del turno: el del texto si trae señal, el de la
   conversación si no (BR2.1, BR2.2), y la frase del catálogo si no es ninguno de
   los dos (BR2.3).
5. **Se entrega el turno a U12** por `handle_turn`, con su forma de C-14. Los
   eventos que vuelven se traducen a lo que el navegador entiende: el texto parcial
   a medida que llega, el final, la frase de espera, la derivación o el error.
6. **Se escribe el turno en la transcripción** con su canal marcado (BR6.4), y el
   contador de la sesión sube.

Nada de este recorrido decide sobre cobertura, monto ni culpa: eso ya lo decidió el
grafo, y lo único que esta unidad puede afirmar por su cuenta es el resultado de una
decisión humana ya registrada (BR5.2).

## Las tres superficies

| Superficie | Qué es |
| --- | --- |
| La página de chat por aseguradora | La conversación, con su divulgación, su selector de idioma y sus citas expandibles |
| El resumen de traza | Una página sin credencial que muestra cómo se llegó a una respuesta, redactada, y solo de la conversación del propio navegador |
| El aviso de la decisión | Lo que el ajustador decidió, apareciendo en la conversación donde se reportó |

## Decisiones de esta etapa

| Id | Decisión | Por qué |
| --- | --- | --- |
| FD-U13-1 | La conversación es una fila (`chat_session`), no una cookie con estado dentro | Un contador de límites que vive en el cliente se reinicia solo, y el aviso de una decisión llega cuando el navegador no está |
| FD-U13-2 | Se guarda el **resumen** de la clave del navegador, nunca la clave | Un volcado de la base no sirve para hacerse pasar por nadie. Es la misma forma que U2 ya usa para los enlaces firmados |
| FD-U13-3 | El idioma vive en la fila de la conversación, no en el navegador | El selector muestra el idioma en que **responde** la agente; si el dato viviera en el cliente, lo que se ve y lo que pasa podrían separarse |
| FD-U13-4 | Los límites se comprueban **antes** de resolver la conversación | Una ráfaga contra una conversación que no existe también cuesta consultas; el rechazo más barato es el primero |
| FD-U13-5 | La cita y el resumen de traza se leen de U8 y U5, no se copian | Dos versiones de la misma cláusula son una versión y una que envejece |
| FD-U13-6 | El aviso de la decisión pasa por la guardia con el identificador de la decisión humana | Es el único camino por el que una salida de este sistema puede afirmar cobertura, y lo que lo autoriza es la firma de una persona, no el texto |

## Lo que U13 no hace

- **No decide nada sobre el caso.** Ni cobertura, ni categoría, ni cierre: entrega
  turnos al grafo y presenta lo que vuelve.
- **No construye la bandeja ni la vista de caso por enlace.** Son de U14. Esta unidad
  solo muestra el **aviso** de lo que allí se decidió.
- **No construye la vista de comparación entre aseguradoras.** Salió del alcance el
  2026-09-28 por decisión de Miguel y es de **U23 `comparison-view`**, después de
  U14. La razón no fue el tiempo: esa vista convence cuando hay casos reales detrás,
  y hoy solo hay tres pólizas de ejemplo.
- **No toca la voz.** El mismo caso puede venir de la voz (BR6.4), pero el transporte
  de voz es U16.
- **No aplica la redacción por su cuenta.** Pasa por el punto único de salida de U3 y
  por la guardia de U10; un punto de salida nuevo sin redacción tiene que ser
  imposible por construcción, no evitado por disciplina.
- **No publica los límites en el proveedor.** Que la clave del chat tenga su tope
  configurado allí (BR3.3) se verifica aquí, pero configurarlo es de la pasada de
  publicación.

## Fronteras con lo ya construido

| Con quién | Qué le pide | Contrato |
| --- | --- | --- |
| U12 `graph-runtime` | Entregar turnos y recibir salidas tipadas | C-14 |
| U4 `case-record` | El caso, su transcripción por turno con el canal, sus transiciones | C-12 |
| U2 `tenancy` | La clave del navegador, el enlace firmado, la sesión con la aseguradora | C-25, C-26 |
| U5 `provider-platform` | El resumen de la traza y el registro de uso por turno | C-17, C-23 |
| U10 `compliance` | La guardia de salida para todo texto, incluido el aviso | C-20 |
| U1 `workspace` | El catálogo por idioma y el conductor de texto del corredor | C-1 |
| U6 `web-shell` | El armazón, el enrutador y el selector de idioma | C-27 |
| U14 `inbox` | Nada: U14 escribe la decisión, esta unidad la lee | C-12 |

## Riesgos de esta unidad

- **Es la primera superficie que ve alguien de fuera, así que un fallo de aislamiento
  aquí es un incidente y no un defecto.** Dos de las tres compuertas duras de esta
  unidad son de aislamiento (BR6.2, BR6.3), y las dos se verifican comparando
  contra la respuesta ante lo inexistente, no comprobando que el dato ajeno no
  aparezca. La lección es de U12: **la filtración no es el dato, es la distinción.**
- **El límite que vive solo en la aplicación falla abierto cuando lo que falla es la
  aplicación.** Por eso BR3.3 exige el tope también en el proveedor, y por eso la
  clave del chat es propia: una cuota agotada no puede tumbar la voz ni las
  evaluaciones.
- **El streaming parcial es texto que llega antes de que la respuesta esté completa.**
  Si el texto parcial no pasara por la guardia, la guardia no serviría: bastaría leer
  rápido. Todo evento sale por el punto único, también el parcial.

## Sources

- `[Q1]` Las siete historias de U13 con sus criterios: US1.1, US1.2, US5.13, US1.18,
  US2.3, US1.20, US2.9 en `inception/user-stories/stories.md`.
- `[scope]` `inception/units-generation/unit-of-work.md`, entrada U13: tipo, rama de
  pruebas, componentes, dependencias y el contrato de borrado de visitante (UG-3).
- `[Q1]` `inception/contract-design/contract-summary.md`: C-14 (la interfaz del
  turno), C-12, C-17, C-20, C-23, C-25, C-26, C-27.
- `[desc]` PRD, Segmento 4 (el canal de texto), 8 (la clasificación de S2 y S5) y
  11.2 (la adherencia de idioma y las compuertas duras).
- `[memory:M1]` `aidlc/spaces/default/memory/project.md`: las prohibiciones sobre
  prometer lo no construido, publicar sin límites y escribir fuera del punto único de
  salida.

## Assumptions & Open Questions

- **US1.20 es Should (S2) y es la primera en la regla de corte del PRD.** Se construye
  porque su criterio AC1.20.2 y AC1.20.3 son compuertas duras que el chat necesita de
  todos modos —responder igual ante un caso ajeno que ante uno inexistente— y porque
  el punto de control que hace posible retomar ya existe desde U12. Si se cortara, lo
  que queda en pie es AC1.19.5, que fija qué hace el chat sin retoma.
- **US2.9 salió del alcance de esta unidad** el 2026-09-28 (decisión de Miguel, Q1
  de esta etapa) y pasa a **U23 `comparison-view`**, declarada después de U14. Es
  Should (S5) y ya estaba marcada en el orden de corte del PRD; el motivo de moverla
  no fue el tiempo, sino que la vista convence cuando hay casos reales detrás.
- **La meta de latencia del chat (AC2.3.5, NFR4) es de esta unidad, y su umbral se
  fija en los requisitos de calidad**, con el entorno de la medición declarado. El
  aporte de U12 a esa latencia ya está declarado como NFR4.2.
- `None.`
