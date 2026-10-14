# Reglas de negocio — U5 `provider-platform`

Cincuenta y tres reglas gobiernan lo único de este proyecto que puede costar
dinero de verdad. Se agrupan en siete familias: los puertos y los adaptadores, la
taxonomía de errores con su parada, el precio y el "no medido", el techo con su
alerta y su corte, las cuotas de la demostración con la reserva de la voz, las
trazas con sus resúmenes, y el aislamiento con el borrado de datos de visitante.

Las dos familias más grandes son el techo y las cuotas, y no por casualidad: son
la única parte del sistema donde un fallo no produce un error sino una factura.

## Reglas

El bloque siguiente es la fuente de verdad; la tabla resumen que va después se
deriva de él.

```yaml
rules:

  # --- BR1: los puertos y los adaptadores ------------------------------------

  - id: BR1.1
    statement: >
      El núcleo habla con cuatro interfaces propias —generar texto, calcular
      embeddings, transcribir en streaming y sintetizar— y nunca con el cliente
      de un proveedor.
    category: constraint
    applies_to: "Puertos de proveedor"
    trigger: "En cualquier llamada a un proveedor desde el núcleo."
    logic: >
      SI un módulo del núcleo necesita un proveedor ENTONCES lo pide por su
      puerto, que recibe inyectado desde la raíz de composición.
    violation: "La regla de importación falla y la entrega se detiene."
    source: C-16, ADR-018, team.md convención 5b

  - id: BR1.2
    statement: >
      El paquete de un proveedor solo se importa dentro del adaptador de ese
      proveedor.
    category: constraint
    applies_to: "Adaptadores"
    trigger: "En cada corrida del guion de verificación."
    logic: >
      SI un archivo fuera de `providers/adapters/<proveedor>/` importa el
      paquete de ese proveedor ENTONCES el contrato `forbidden` de las reglas de
      importación falla.
    violation: "El paso de reglas de importación devuelve distinto de cero y nombra el archivo."
    source: ADR-018, project.md (Forbidden), PRD 12.2

  - id: BR1.3
    statement: >
      Cada uso —voz, chat, evaluaciones y operación— construye su cliente en la
      fábrica por uso, con su propia clave y en su propio proyecto del
      proveedor.
    category: policy
    applies_to: "Fábrica de clientes"
    trigger: "Al arrancar y en cada llamada."
    logic: >
      SI se pide un cliente para un uso ENTONCES la fábrica devuelve el de ese
      uso, con la clave y el proyecto que su configuración declara, y nunca uno
      compartido.
    violation: "Se rechaza la construcción nombrando el uso pedido."
    source: ADR-006, ADR-018 (enmienda del 2026-09-17), project.md (Mandated)

  - id: BR1.4
    statement: >
      El identificador de modelo y de voz es exacto y viene de configuración
      versionada. Nunca un alias que el proveedor pueda mover.
    category: constraint
    applies_to: "Configuración de proveedores"
    trigger: "Al arrancar."
    logic: >
      SI la configuración declara un alias en vez de un identificador exacto
      ENTONCES el proceso no arranca.
    violation: "El arranque falla nombrando el valor encontrado."
    source: team.md (Testing Posture, determinismo), ADR-006

  - id: BR1.5
    statement: >
      La salida estructurada se valida dentro del adaptador. Un fallo de
      validación se traduce a `invalid_response` y el objeto del proveedor no
      sale de ahí.
    category: validation
    applies_to: "Adaptadores"
    trigger: "Al recibir una respuesta con esquema pedido."
    logic: >
      SI la respuesta no valida contra el esquema ENTONCES el adaptador levanta
      un error de tipo `invalid_response`.
    violation: "El nodo decide según su política de fallo; el núcleo nunca ve el objeto crudo."
    source: C-16, ADR-018 (enmienda del 2026-09-17)

  - id: BR1.6
    statement: >
      Cada adaptador tiene prueba de contrato con respuesta grabada, que corre
      en cada entrega, y una contra el proveedor real que corre por hito.
    category: policy
    applies_to: "Adaptadores"
    trigger: "En cada corrida del guion de verificación y en cada hito."
    logic: >
      SI un adaptador no tiene prueba de contrato ENTONCES el paso de pruebas
      falla nombrando el adaptador.
    violation: "La entrega se detiene."
    source: ADR-018, U5 (Contiene)

  - id: BR1.7
    statement: >
      El prompt de cada nodo y cada idioma es un archivo versionado con
      identificador y hash. El hash viaja en la traza y en el registro de la
      corrida de evaluaciones.
    category: policy
    applies_to: "Prompts"
    trigger: "En cada llamada al modelo."
    logic: >
      SI se llama al modelo ENTONCES la llamada nombra el prompt que usó y su
      hash, y ese hash queda en la traza.
      SI el hash cambia entre dos corridas ENTONCES la compuerta de evaluaciones
      lo trata como cambio de código.
    violation: "Una llamada sin prompt identificado no se emite."
    source: ADR-018 (enmienda del 2026-09-17), P5

  # --- BR2: la taxonomía de errores y la parada ------------------------------

  - id: BR2.1
    statement: >
      Un adaptador solo deja salir cuatro tipos de error: `timeout`,
      `rate_limited`, `unavailable` e `invalid_response`.
    category: constraint
    applies_to: "Adaptadores"
    trigger: "Al fallar una llamada."
    logic: >
      SI el paquete del proveedor levanta cualquier error ENTONCES el adaptador
      lo traduce a uno de esos cuatro antes de dejarlo salir.
    violation: "Una prueba de contrato con inyección de errores falla si sale otro tipo."
    source: C-16, ADR-018, team.md convención 8a

  - id: BR2.2
    statement: >
      Ningún tipo del proveedor cruza hacia el núcleo: ni su error, ni su
      objeto de respuesta, ni su cliente.
    category: constraint
    applies_to: "Frontera del proveedor"
    trigger: "En cada retorno de un adaptador."
    logic: >
      SI el valor de retorno o el error de un adaptador lleva un tipo del
      paquete del proveedor ENTONCES el chequeo de tipos falla.
    violation: "El paso de tipos devuelve distinto de cero."
    source: team.md convención 8a, ADR-018

  - id: BR2.3
    statement: >
      Ante saldo o cuota agotados no hay reintento. Sale una señal explícita de
      parada, distinta de los cuatro tipos de error.
    category: policy
    applies_to: "Adaptadores y fábrica"
    trigger: "Cuando el proveedor responde que no queda saldo o cuota, o cuando el techo del proyecto está alcanzado."
    logic: >
      SI se agota el saldo o la cuota ENTONCES la llamada termina con la señal
      de parada, sin reintento y sin degradar a otro proveedor por iniciativa
      propia.
    violation: "El trabajo se detiene y se nombra qué se acabó; nadie recarga por iniciativa propia."
    source: C-16, project.md (regla de cero renovaciones, 2026-09-16)

  - id: BR2.4
    statement: >
      El adaptador no decide reintentar ante `rate_limited`: lo decide la
      política de fallo del nodo, aplicada por el ejecutor común.
    category: policy
    applies_to: "Adaptadores"
    trigger: "Al recibir un error de tipo `rate_limited`."
    logic: >
      SI el error es `rate_limited` ENTONCES el adaptador lo devuelve y no
      reintenta por su cuenta.
    violation: "Una prueba de contrato comprueba que el adaptador hizo exactamente una llamada."
    source: C-16, team.md convención 8b

  - id: BR2.5
    statement: >
      Cada intento fallido deja su propio evento en la traza, con el nodo, el
      tipo de error y el número de intento.
    category: policy
    applies_to: "Adaptadores"
    trigger: "En cada intento que falla."
    logic: >
      SI un intento falla ENTONCES se emite un evento con nodo, tipo de error y
      número de intento, y el siguiente intento emite el suyo.
    violation: "El criterio AC4.8.5 falla: no se puede reconstruir cuántas veces se intentó."
    source: AC4.8.5, team.md convención 8d

  # --- BR3: el precio, el costo y "no medido" --------------------------------

  - id: BR3.1
    statement: >
      Toda llamada a un proveedor deja una fila de gasto, sin excepción,
      incluida la que falló y la que no se pudo valorar.
    category: policy
    applies_to: SpendEntry
    trigger: "Al terminar cada llamada, con éxito o sin él."
    logic: >
      SI una llamada consumió unidades ENTONCES se escribe su fila con lo que se
      sepa de ella.
    violation: "El costo por caso queda por debajo del real y nadie lo nota, que es el fallo silencioso que esta unidad existe para impedir."
    source: FR10.1, FR10.3, AC4.8.1
    amendment_2026_09_21: >
      Aplicada en la compuerta de la unidad, y corrige una contradicción entre
      el `statement` de esta regla y su propio `logic`. El `logic` decía "SI una
      llamada consumió unidades", y justo las dos que el `statement` nombra —la
      que falló y la que no se pudo valorar— son las que no consumieron unidades
      conocidas. Lo correcto es: SI una llamada a un proveedor terminó, con éxito
      o sin él, ENTONCES se escribe su fila. Y se añade lo que faltaba y costó un
      defecto real: **ninguna invariante de presupuesto puede impedir esa
      escritura.** La invariante que impedía a una llamada de grabación
      registrarse con su reserva agotada se retiró por eso (ver BR4.5 y
      `entities.md`).
  - id: BR3.2
    statement: >
      El costo se calcula con la tabla versionada de precios de lista, y la fila
      guarda el precio que usó y la fecha de esa lista.
    category: calculation
    applies_to: SpendEntry
    trigger: "Al escribir la fila de gasto."
    logic: >
      SI la tabla declara un precio para ese proveedor, modelo y unidad
      ENTONCES el costo es unidades por precio, y la fila guarda el precio, la
      versión de la lista y su fecha.
    violation: "Una cifra publicada no se podría reproducir meses después, cuando el precio del proveedor ya cambió."
    source: AC4.8.4, FR10.3

  - id: BR3.3
    statement: >
      Sin precio declarado, el costo se registra como "no medido". Nunca como
      cero.
    category: constraint
    applies_to: SpendEntry
    trigger: "Al escribir la fila de gasto."
    logic: >
      SI la tabla de precios no declara precio para ese proveedor, modelo y
      unidad ENTONCES el estado del costo es `not_measured` y las cuatro
      columnas de precio quedan vacías.
    violation: "Se rechaza la escritura de un costo cero por falta de precio."
    source: AC4.8.4, AC5.14.6, team.md convención 8c

  - id: BR3.4
    statement: >
      El costo y su estado viajan siempre juntos. Un costo sin su estado no se
      puede escribir, y un estado `measured` sin precio ni fecha tampoco.
    category: validation
    applies_to: SpendEntry
    trigger: "En cada escritura de una fila de gasto."
    logic: >
      SI el estado es `measured` ENTONCES el precio unitario, la versión de la
      lista, su fecha y el costo están los cuatro presentes.
      SI el estado es `not_measured` ENTONCES los cuatro están ausentes.
    violation: "Se rechaza la escritura nombrando qué columna sobra o falta."
    source: Q2, AC4.8.4

  - id: BR3.5
    statement: >
      Toda agregación de costo devuelve el par: lo medido y cuántas llamadas no
      se midieron. Ninguna devuelve un número solo.
    category: constraint
    applies_to: "Agregaciones de gasto"
    trigger: "En cada suma de costos, sea por caso, por proveedor, por mes o de la ventana."
    logic: >
      SI se pide un total ENTONCES se devuelve el total medido y el conteo de no
      medidas, y quien publique el primero sin el segundo tiene que desarmar el
      tipo a propósito.
    violation: "Una prueba comprueba que ninguna superficie publica el total sin su conteo."
    source: Q2, AC5.14.6

  - id: BR3.6
    statement: >
      El precio de lista se registra siempre; si la llamada se factura de verdad
      depende del plan del uso, que vive en configuración versionada.
    category: policy
    applies_to: SpendEntry
    trigger: "Al escribir la fila de gasto."
    logic: >
      SI el plan del uso es gratuito ENTONCES la fila lleva su costo a precio de
      lista y `billable` en falso.
      SI el plan es de pago ENTONCES lleva `billable` en verdadero.
    violation: "O el costo por caso del chat desaparece, o el chat gratuito se come el presupuesto de la voz."
    source: Q3, ADR-006, NFR14

  - id: BR3.7
    statement: >
      El costo por caso exitoso divide el costo a precio de lista entre los
      casos que pasaron todas las compuertas, y un componente sin precio
      declarado aparece como no medido, nunca en cero.
    category: calculation
    applies_to: "Reporte de costo"
    trigger: "Al publicar una versión."
    logic: >
      SI se publica el costo por caso exitoso ENTONCES el numerador es el costo
      a precio de lista y el denominador son los casos que pasaron todas las
      compuertas, y el resultado viaja con su conteo de no medidas.
    violation: "La cifra publicada no corresponde a lo que dice medir."
    source: AC5.14.6, NFR14

  - id: BR3.8
    statement: >
      El registro responde cuatro agregaciones y esas cuatro: por caso, por
      proveedor, por mes, y el acumulado de la ventana. Las tres primeras salen
      del registro; el acumulado sale de la fila única de la ventana.
    category: policy
    applies_to: "Registro de gasto"
    trigger: "Al pedir datos para la pantalla de gasto."
    logic: >
      SI se pide el acumulado de la ventana ENTONCES se lee la fila única, no se
      suma el historial.
    violation: "El corte dependería de recorrer un historial que puede crecer sin techo."
    source: AC5.14.1, C-17

  - id: BR3.9
    statement: >
      El costo nunca se escribe sin su estado, en ninguna de las tres formas que
      toma en esta unidad: la fila de gasto, el resumen de traza y el valor que
      devuelven las operaciones.
    category: validation
    applies_to: "SpendEntry, TraceSummary, Money"
    trigger: "En cada escritura y en cada lectura de un costo."
    logic: >
      SI el estado es `measured` ENTONCES la cantidad está presente.
      SI el estado es `not_measured` ENTONCES la cantidad está ausente.
      Esta es la invariante común a las tres; BR3.4 añade la que solo tiene la
      fila de gasto, que además guarda con qué precio y con qué lista se calculó.
    violation: "Se rechaza la escritura. Una cantidad sin estado se suma como si fuera cierta."
    source: Q2, AC4.8.4, AC5.14.6

  # --- BR4: el techo, la alerta y el corte -----------------------------------

  - id: BR4.1
    statement: >
      El techo es acumulado en la ventana de noventa días que empieza el
      2026-09-16. Nunca mensual, y su mensaje de corte no menciona el mes.
    category: constraint
    applies_to: BudgetWindow
    trigger: "En cada consulta del presupuesto."
    logic: >
      SI se pregunta cuánto se lleva gastado ENTONCES se responde con el
      acumulado de la ventana, no con el del mes en curso.
    violation: "Un cambio de mes pondría el contador en cero y el techo no protegería nada."
    source: D11, project.md (Corrections, 2026-09-17)

  - id: BR4.2
    statement: >
      Solo las filas facturables suman contra el techo y contra la alerta.
    category: calculation
    applies_to: BudgetWindow
    trigger: "Al escribir una fila de gasto."
    logic: >
      SI la fila lleva `billable` en verdadero ENTONCES su costo se suma al
      acumulado de la ventana; si no, no se suma.
    violation: "El chat en plan gratuito agotaría el presupuesto de la voz sin que nadie hubiera pagado nada."
    source: Q3, ADR-006

  - id: BR4.3
    statement: >
      La alerta sale una sola vez, al cruzar los 3 USD acumulados, por el canal
      configurado.
    category: policy
    applies_to: BudgetWindow
    trigger: "Al incrementar el acumulado."
    logic: >
      SI el acumulado pasa de menos de la alerta a igual o más, y la marca de
      alerta enviada está vacía ENTONCES se emite la alerta y se escribe la
      marca en la misma transacción.
      SI la marca ya existe ENTONCES no se emite nada.
    violation: "Una alerta por llamada convierte el aviso en ruido y deja de leerse."
    source: AC5.14.2, D-015

  - id: BR4.4
    statement: >
      Agotado el presupuesto público, la voz rechaza las llamadas nuevas **del
      enlace público** antes de pedir el micrófono, con la clave del catálogo en
      el idioma del visitante, y el chat sigue respondiendo. Las llamadas de
      grabación siguen su propio carril (BR4.10).
    category: policy
    applies_to: "Disponibilidad de la voz"
    trigger: "Al preguntar si la voz está disponible y al abrir una llamada."
    logic: >
      SI el presupuesto público restante es cero o menos ENTONCES la
      disponibilidad responde que no, con el motivo `budget_exhausted`, y la
      consola muestra el texto del catálogo sin pedir permiso de micrófono.
      Y el chat, que corre en plan gratuito, sigue atendiendo.
    violation: "Pedir el micrófono para después rechazar la llamada es la forma más cara de decir que no."
    source: AC5.14.3, FR10.4, C-08

  - id: BR4.5
    statement: >
      El techo se consulta **antes** de un uso de pago y el costo se registra
      **después**. El exceso posible es a lo sumo el de **la llamada al
      proveedor que estaba en vuelo**, y esa consecuencia se declara en lugar de
      esconderse.
    category: policy
    applies_to: "Uso de pago"
    trigger: "Antes de cada llamada facturable."
    logic: >
      SI el acumulado ya alcanzó el techo ENTONCES la llamada no se hace.
      SI no ENTONCES la llamada se hace y su costo se suma al terminar, aunque
      ese costo cruce el techo.
    violation: >
      Reservar un estimado antes de llamar evitaría el exceso y exigiría una
      tabla de reservas y una conciliación por llamada. La cota se fija en
      `nfr-requirements` con los precios por minuto medidos; no se afirma aquí
      una cifra que los documentos aprobados todavía no permiten calcular.
    source: Q3, C-17, componente ProviderGateway
    amendment_2026_09_21: >
      Aplicada en la compuerta de la unidad. El `logic` decía que el costo se
      registra aunque cruce **el techo** y callaba sobre la reserva de un carril,
      que es donde estaba el hueco: con la reserva de grabación agotada la
      escritura no cruzaba el techo pero sí la reserva, y una invariante la
      rechazaba, así que la fila se perdía. Se lee ahora "el techo **o la reserva
      de su carril**". Queda dicho también lo que esta regla promete y hoy no se
      puede cumplir: acota el exceso a "la llamada en vuelo" y remite su cifra a
      `nfr-requirements` con los precios por minuto medidos, que no existen; y si
      la llamada en vuelo es precisamente la que no se pudo valorar, el exceso no
      es calculable ni después. Sobre el papel está acotado; en la práctica,
      todavía no.
  - id: BR4.6
    statement: >
      El acumulado se incrementa en la misma transacción que escribe la fila de
      gasto. El corte nunca se decide sumando el historial.
    category: constraint
    applies_to: BudgetWindow
    trigger: "Al registrar un gasto."
    logic: >
      SI se escribe una fila facturable ENTONCES la misma transacción incrementa
      la fila de la ventana; si una de las dos falla, ninguna queda escrita.
    violation: "Dos llamadas simultáneas podrían pasar el techo, cada una leyendo un acumulado que la otra todavía no había escrito."
    source: Q1, C-17

  - id: BR4.7
    statement: >
      El acumulado sobrevive al reinicio nocturno de los datos de demostración y
      al cambio de mes.
    category: constraint
    applies_to: BudgetWindow
    trigger: "En cada reinicio nocturno y en cada cambio de mes."
    logic: >
      SI corre el reinicio nocturno ENTONCES la fila de la ventana no se toca.
      SI cambia el mes ENTONCES tampoco.
    violation: "Una prueba corre el purgador y comprueba que el acumulado sigue igual."
    source: AC5.14.4, U5 (Notas)

  - id: BR4.8
    statement: >
      El corte de gasto no depende de la observación: si el backend de trazas
      cae, el gasto se sigue registrando y el techo sigue cortando.
    category: constraint
    applies_to: "UsageBudget"
    trigger: "Cuando el backend de trazas no responde."
    logic: >
      SI la exportación de trazas falla ENTONCES se registra la pérdida y el
      registro de gasto, el acumulado y el corte siguen funcionando.
    violation: "La regla de importación falla si el módulo de gasto importa el de trazas."
    source: C-17, C-23, catálogo de componentes

  - id: BR4.9
    statement: >
      Una porción del techo es **reserva de grabación** y el enlace público no
      la puede tocar: existe para grabar el video final y para la sesión de
      escucha.
    category: constraint
    applies_to: BudgetWindow
    trigger: "En cada consulta del presupuesto y en cada registro de gasto."
    logic: >
      El presupuesto público restante es el techo menos la reserva de grabación
      menos lo que el carril público lleva gastado.
      SI una llamada del enlace público pediría cruzar ese resto ENTONCES se
      rechaza, aunque quede saldo dentro de la reserva.
    violation: >
      Sin la reserva, un día de tráfico en el enlace público deja el proyecto
      sin presupuesto para grabar el video, que es el entregable de la semana
      doce.
    source: FR3.11 (enmienda del 2026-09-19), NFR15, M18
    amendment_2026_09_21: >
      Aplicada en la compuerta de la unidad: faltaba la mitad simétrica. El
      `logic` define el restante público y calla sobre el de grabación, que tiene
      su propio piso en cero y **dos** causas para quedar sin número —la reserva
      no se pudo calcular, o una llamada de ese carril no se pudo valorar—. Y al
      revés: el restante público **no** se cierra por una llamada de grabación
      sin valorar, porque el gasto público se deriva restando los dos acumulados
      y el cero de esa llamada se cancela, así que ese restante sigue siendo
      exacto. Cerrarlo habría apagado el chat y la voz públicos durante el resto
      de la ventana en cuanto se grabara el primer minuto de la semana doce, que
      es justo la demostración que la grabación existe para mostrar.
  - id: BR4.10
    statement: >
      Una llamada marcada como grabación se sigue atendiendo con el cupo público
      agotado, hasta agotar su reserva, y solo puede marcarla quien entra con
      credencial de la aseguradora. El enlace público nunca la marca.
    category: authorization
    applies_to: "Carril de presupuesto"
    trigger: "Al abrir una llamada."
    logic: >
      SI quien abre la llamada presenta credencial y pide el carril de grabación
      ENTONCES la llamada se sirve mientras quede reserva, y su gasto se
      atribuye al carril de grabación.
      SI la petición llega por el enlace público ENTONCES el carril es el
      público, sin excepción.
    violation: >
      Una marca que el visitante pudiera poner convertiría la reserva en
      presupuesto público con un nombre distinto, y la vaciaría el primer día.
    source: FR3.11, C-08, U2 (credencial de la aseguradora)

  # --- BR5: las cuotas de la demostración y la reserva de la voz -------------
    amendment_2026_09_21: >
      Aplicada en la compuerta de la unidad. Falta en el `logic` que una llamada
      de grabación **sin valorar** cierra su propio carril —cae al respaldo y su
      cupo queda en cero—, por el mismo argumento de fallo cerrado que ya
      gobierna el público: de un piso no sale un restante, y publicar la resta
      como si lo fuera es como se gasta una reserva con el número diciendo que
      queda.
  - id: BR5.1
    statement: >
      Hay cuatro alcances de cuota y solo cuatro: mensajes del chat por sesión,
      mensajes del chat por día, llamadas del visitante por día y llamadas del
      sitio por día.
    category: constraint
    applies_to: QuotaCounter
    trigger: "Al consultar o incrementar una cuota."
    logic: >
      SI el alcance pedido no está en esa lista ENTONCES la consulta se rechaza.
    violation: "Se rechaza nombrando el alcance pedido y los cuatro válidos."
    source: FR3.9, FR4.6, C-17

  - id: BR5.2
    statement: >
      El día de una cuota se cierra en la zona horaria configurada, no en la del
      servidor, y el reloj es inyectable.
    category: constraint
    applies_to: QuotaCounter
    trigger: "Al calcular el comienzo del periodo."
    logic: >
      SI se calcula el periodo de un contador diario ENTONCES se usa la zona
      horaria de la configuración y el reloj inyectado.
    violation: "Un cambio de servidor movería la medianoche y regalaría o quitaría una llamada."
    source: U5 (Contiene), team.md (determinismo)

  - id: BR5.3
    statement: >
      Una negación de cuota nunca levanta una excepción: devuelve un motivo de
      la lista cerrada de cuatro.
    category: policy
    applies_to: QuotaDecision
    trigger: "Al consultar una cuota."
    logic: >
      SI el sujeto superó el límite ENTONCES se devuelve una decisión negativa
      con su motivo —`rate_limited_session`, `rate_limited_daily`,
      `rate_limited_site` o `budget_exhausted`—.
    violation: "Un rechazo que llega como excepción se convierte en un error genérico en la pantalla, que es justo lo que FR4.6 prohíbe."
    source: C-17, C-08, FR4.6

  - id: BR5.4
    statement: >
      La llamada del día de un visitante se consume al **abrir** la sesión, en
      la misma transacción que la crea.
    category: policy
    applies_to: QuotaCounter
    trigger: "Al abrir una sesión de voz."
    logic: >
      SI queda cupo ENTONCES se incrementa el contador y se crea la sesión en
      una sola transacción; si el incremento falla, la sesión no se crea.
    violation: "Contar al terminar dejaría pasar diez llamadas abiertas a la vez, que es el escenario de RT-13."
    source: Q5, FR3.9, RT-13

  - id: BR5.5
    statement: >
      El cupo se devuelve solo si la llamada terminó sin un solo segundo de
      audio facturable, y esa condición se comprueba contra el registro de
      gasto, no contra lo que diga la consola.
    category: policy
    applies_to: QuotaCounter
    trigger: "Al cerrar una sesión de voz."
    logic: >
      SI la sesión no dejó ninguna fila de gasto de audio con unidades mayores
      que cero ENTONCES el contador del visitante se decrementa.
      SI dejó alguna ENTONCES no se toca.
    violation: "Una caída de red antes del primer turno le quitaría el día al visitante, o una consola mentirosa devolvería cupos que sí se gastaron."
    source: Q5, FR3.9
    amendment_2026_09_21: >
      Aplicada en la compuerta de la unidad, y son tres precisiones que el texto
      original dejaba abiertas.
      (a) Se decrementan **los dos** contadores, el del visitante y el del
      sitio, no solo el primero. El `logic` nombraba uno; el flujo F4 nombra los
      dos y tiene razón, porque F3 consume los dos al abrir y devolver uno solo
      dejaría el cupo del sitio gastado por una llamada que no costó nada —y ese
      cupo es justo lo que BR5.6 reparte entre los días que faltan—.
      (b) "Una fila de audio" son los segundos de transcripción **y** los
      caracteres de síntesis: una llamada donde solo sonó el saludo costó dinero,
      y contar solo los segundos devolvería el cupo de algo ya pagado.
      (c) El periodo del que se devuelve sale de cuándo se **abrió** la llamada y
      nunca del reloj del cierre: una llamada que empieza a las 23:58 y se cae a
      las 00:03 tomó el cupo de ayer.
      Queda además una diferencia declarada entre las dos frases de esta misma
      regla: el `statement` dice "audio **facturable**" y el `logic` dice
      unidades mayores que cero. Se implementó el `logic`, que es el lado
      conservador —una fila de audio en plan gratuito también impide la
      devolución— porque equivocarse hacia no devolver le cuesta un cupo a un
      visitante, y equivocarse hacia devolver regala presupuesto que sí se gastó.

  - id: BR5.6
    statement: >
      El cupo diario del sitio se deriva del presupuesto que queda y los días
      que faltan, con tope de quince y piso de cero.
    category: calculation
    applies_to: QuotaCounter
    trigger: "Al abrir el periodo diario del alcance del sitio."
    logic: >
      El cupo del día es el menor entre quince y el piso de dividir el
      presupuesto **público** restante (BR4.9) entre los días que faltan de la
      ventana multiplicados por la reserva por llamada.
      SI el presupuesto público restante es cero o menos ENTONCES el cupo es
      cero, que es el corte del enlace público.
    violation: "Un cupo fijo se llevaría el presupuesto en un día bueno y dejaría sin voz los ochenta y nueve siguientes."
    source: Q4, FR3.9 y FR3.11 (enmiendas del 2026-09-19), NFR15

  - id: BR5.7
    statement: >
      El modo de voz —principal o de respaldo— se decide antes de abrir la
      llamada, comprobando que el presupuesto cubre una llamada completa a la
      voz principal, y no cambia a mitad.
    category: policy
    applies_to: VoiceMode
    trigger: "Al crear la sesión de voz."
    logic: >
      SI el presupuesto restante cubre la reserva por llamada de la voz
      principal ENTONCES el modo es `primary`; si no, `fallback`.
      Y el modo queda fijado en la sesión hasta que termina.
    violation: "Cambiar de voz a mitad de llamada suena a fallo, aunque sea un ahorro."
    source: US5.11, C-08, C-17

  - id: BR5.8
    statement: >
      Los topes están configurados **también en el proveedor**, y una tabla
      versionada guarda cuál es el de cada uso y cuándo se comprobó por última
      vez.
    category: policy
    applies_to: ProviderCap
    trigger: "En cada revisión de la tabla y en el checklist del segundo día."
    logic: >
      SI la aplicación está detenida ENTONCES el proveedor sigue rechazando por
      encima de su propio tope.
      SI un uso no tiene tope disponible en su proveedor ENTONCES se declara
      así en la tabla, con lo que lo sustituye.
    violation: "Un límite que vive solo en la aplicación falla abierto cuando lo que falla es la aplicación."
    source: FR3.10, team.md (Deployment), PA-9

  - id: BR5.9
    statement: >
      Las pruebas de límites no consumen el presupuesto que protegen: el tope
      del proveedor se comprueba con una clave de prueba de tope mínimo y la
      aplicación detenida, y el techo con un acumulado forzado.
    category: policy
    applies_to: "Pruebas de esta unidad"
    trigger: "Al escribir una prueba de límite o de techo."
    logic: >
      SI una prueba necesita el techo alcanzado ENTONCES fuerza el acumulado en
      la base, nunca gasta hasta llegar.
    violation: "Una suite que gasta el presupuesto real deja el proyecto sin voz para demostrarla."
    source: project.md (Testing Posture, 2026-09-16)

  # --- BR6: las trazas y los resúmenes ---------------------------------------

  - id: BR6.1
    statement: >
      La traza tiene tres niveles y los tres existen siempre: por turno, por
      nodo y por llamada a proveedor.
    category: policy
    applies_to: "Trazas"
    trigger: "En cada turno que corre por cualquier canal."
    logic: >
      SI corre un turno ENTONCES hay un tramo del turno, un tramo por cada nodo
      que se ejecutó y un tramo por cada llamada a un proveedor, anidados.
    violation: "El criterio AC4.8.1 falla: no se puede saber qué nodo costó qué."
    source: AC4.8.1, FR10.1
    amendment_2026_09_21: >
      Aplicada en la compuerta de la unidad. Los tres niveles del **turno**
      siguen siendo tres y esta regla no cambia. Lo que se añadió es otro eje:
      los dos momentos del caso que pide BR6.4 —la pausa hacia la bandeja y la
      reanudación— ocurren fuera de cualquier turno, horas después, así que no
      son ninguno de los tres y no pueden colgar de uno. Tienen su propio nivel
      y son tramos raíz que comparten el identificador de traza del caso.
      Dárselos al nivel de turno habría permitido que un nodo colgara de una
      pausa, que es una traza que describe algo que no ocurrió.

  - id: BR6.2
    statement: >
      Los nodos se llaman `intake`, `policy_verification`, `decision` y
      `compliance` en la traza, igual que el directorio de su módulo, el valor
      del enum de transición y la etiqueta del reporte de evaluación.
    category: constraint
    applies_to: "Trazas"
    trigger: "Al emitir un tramo de nodo."
    logic: >
      SI el nombre del tramo no es uno de esos cuatro ENTONCES la prueba de
      grafía falla.
    violation: "Cuatro grafías del mismo nodo obligan a traducir entre la traza, el reporte y el código."
    source: AC4.8.2, team.md convención 3

  - id: BR6.3
    statement: >
      Cada llamada a un proveedor registra modelo, tokens de entrada, tokens de
      salida, latencia y costo, con las convenciones GenAI de OpenTelemetry.
    category: policy
    applies_to: "Trazas"
    trigger: "Al cerrar el tramo de una llamada."
    logic: >
      SI se cierra el tramo de una llamada ENTONCES lleva esos cinco atributos,
      y el costo va con su estado (BR3.4).
    violation: "El criterio AC4.8.1 falla."
    source: AC4.8.1, FR10.1, M7

  - id: BR6.4
    statement: >
      La ruta que recorrió el grafo, la pausa hacia la bandeja con su hora y la
      reanudación con quién decidió viven en la traza del **mismo** caso.
    category: policy
    applies_to: "Trazas"
    trigger: "Al derivar un caso y al reanudarlo desde la bandeja."
    logic: >
      SI un caso se deriva y después se aprueba ENTONCES los dos momentos son
      tramos del mismo caso, con la hora de la pausa y el nombre de quien
      decidió en el de reanudación.
    violation: "Dos trazas separadas obligan a reconstruir a mano lo que pasó entre ellas."
    source: AC4.8.3, FR10.1

  - id: BR6.5
    statement: >
      Toda exportación de trazas pasa por la redacción antes de salir, y también
      lo hace el resumen antes de guardarse.
    category: constraint
    applies_to: "Exportación de trazas"
    trigger: "Antes de exportar y antes de guardar un resumen."
    logic: >
      SI un texto va a salir hacia el backend de trazas o a guardarse en un
      resumen ENTONCES pasa por la redacción de U3.
    violation: "Un dato personal en una traza es el escenario RT-14, y es compuerta dura."
    source: C-23, C-13, project.md (Mandated), RT-14

  - id: BR6.6
    statement: >
      Un resumen de traza solo se le muestra al navegador que lo produjo.
    category: authorization
    applies_to: TraceSummary
    trigger: "Al pedir el resumen de una respuesta."
    logic: >
      SI el resumen de la clave del navegador que pide no coincide con el que
      guarda el resumen ENTONCES no se devuelve, y la respuesta es la misma que
      si no existiera.
    violation: "Un visitante vería lo que preguntó otro."
    source: C-23, project.md (Corrections, 2026-09-16)

  - id: BR6.7
    statement: >
      Si el backend de trazas no recibe la traza, el resumen queda en `lost` y
      nada se detiene: ni el caso, ni el gasto, ni el corte.
    category: policy
    applies_to: TraceSummary
    trigger: "Cuando la exportación falla o expira."
    logic: >
      SI la exportación falla ENTONCES el resumen pasa a `lost`, se registra la
      pérdida y el turno sigue.
    violation: "Un caso que se cae porque el panel de trazas está caído convierte una herramienta de diagnóstico en un punto de fallo."
    source: C-23, team.md convención 8c

  # --- BR7: aislamiento, dato personal y borrado -----------------------------

  - id: BR7.1
    statement: >
      Las tres tablas de dinero y cuotas —registro de gasto, contadores y
      ventana— son dato del proyecto, no de una aseguradora, y están en la lista
      de exclusión versionada de la aserción de aislamiento con su razón
      escrita.
    category: policy
    applies_to: "SpendEntry, QuotaCounter, BudgetWindow"
    trigger: "En cada corrida de la aserción de aislamiento."
    logic: >
      SI la aserción encuentra una de esas tres sin política ENTONCES la deja
      pasar porque está en la lista, y solo por eso.
    violation: "Sin la exclusión, la aserción falla; con ella y sin BR7.2, el aislamiento tendría un agujero sin control que lo compense."
    source: Q1, FR9.1, U2 (aserción de aislamiento)
    amendment_2026_09_21: >
      Aplicada en la compuerta de la unidad: son **cuatro** tablas. La cuarta
      registra qué llamada de voz ya se cerró, y existe porque la devolución del
      cupo (BR5.5) tiene que ser idempotente: U16 cierra la sesión siempre,
      también cuando la llamada se cae, así que el doble cierre es el caso
      normal y no el raro. La guarda de "no bajar de cero" protege al contador
      del visitante, cuyo límite es uno, pero **no** al del sitio, cuyo conteo es
      grande: sin marca durable, el segundo cierre le devuelve al sitio un cupo
      que sí se gastó. No cabía en ninguna tabla existente —el alcance de un
      contador es un conjunto cerrado de cuatro valores por BR5.1, y una fila de
      gasto tiene que ser una llamada a un proveedor por BR3.1—. Lleva la
      referencia de la llamada y dos marcas de tiempo, ninguna columna de texto
      libre y ninguna de dato personal, así que BR7.2 la cubre igual que a las
      otras tres.

  - id: BR7.2
    statement: >
      Ninguna tabla excluida del aislamiento puede tener una columna de texto
      libre ni una columna de dato personal, y una aserción contra el catálogo
      vivo lo comprueba en cada corrida.
    category: constraint
    applies_to: "Tablas excluidas del aislamiento"
    trigger: "En cada corrida del guion de verificación."
    logic: >
      SI una tabla de la lista de exclusión tiene una columna de tipo texto sin
      longitud acotada, o una columna cuyo nombre contiene —sin distinguir
      mayúsculas— una de las entradas de la lista versionada de nombres de dato
      personal ENTONCES la aserción falla nombrando la tabla, la columna y la
      entrada que coincidió.
      Esa lista vive en el manifiesto `app/backend/pyproject.toml`, al lado de
      la lista de exclusión que paga, y cada entrada lleva su razón, igual que
      allí. Arranca con: nombre, name, correo, email, telefono, phone, placa,
      plate, direccion, address, cedula, document, poliza, policy.
    violation: "La entrega se detiene. Es lo que paga la exclusión del aislamiento."
    source: Q1, M6, M9

  - id: BR7.3
    statement: >
      El sujeto de un contador de cuota y el dueño de un resumen de traza son el
      **resumen** de la clave del navegador, nunca la clave.
    category: constraint
    applies_to: "QuotaCounter, TraceSummary"
    trigger: "Al escribir un contador o un resumen."
    logic: >
      SI se escribe el sujeto ENTONCES se escribe su resumen.
    violation: "Guardar la clave permitiría suplantar al visitante con lo que hay en la base."
    source: U2 (VisitorKey), M9

  - id: BR7.4
    statement: >
      El resumen de traza lleva aseguradora y política como cualquier tabla de
      datos de visitante, y el reinicio nocturno lo borra con su caso.
    category: constraint
    applies_to: TraceSummary
    trigger: "En cada escritura y en el reinicio nocturno."
    logic: >
      SI corre el reinicio nocturno ENTONCES los resúmenes de los casos borrados
      se van con ellos, y se pide el borrado en el backend de trazas.
    violation: "El purgador de U2 falla si esta unidad no implementa su contrato de borrado."
    source: C-11, UG-3, U5 (Datos de visitante)

  - id: BR7.5
    statement: >
      La fila de gasto **nombra** el caso y no cuelga de él: cuando el reinicio
      borra el caso, esa columna queda en nulo y la fila sobrevive con su
      proveedor, su uso, su costo y su fecha.
    category: constraint
    applies_to: SpendEntry
    trigger: "Al borrar un caso."
    logic: >
      SI se borra un caso ENTONCES las filas de gasto que lo nombraban quedan
      con esa columna vacía y todo lo demás intacto.
    violation: "Con borrado en cascada, el reinicio nocturno vaciaría el registro de costos, contra AC5.14.4."
    source: Q6, AC5.14.4, C-11

  - id: BR7.6
    statement: >
      Los contadores de cuota de un visitante se borran con el reinicio
      nocturno; el del sitio no, porque no nombra a nadie.
    category: policy
    applies_to: QuotaCounter
    trigger: "En el reinicio nocturno."
    logic: >
      SI el alcance del contador es por visitante o por sesión ENTONCES se
      borra.
      SI es el del sitio ENTONCES se conserva, porque su sujeto es el sitio y su
      cupo protege el presupuesto.
    violation: "Borrar el contador del sitio cada noche le regalaría al día siguiente el cupo que ya se había gastado."
    source: C-11, Q1, FR3.9
```

## Resumen

| Familia | Reglas | De qué responde |
| --- | --- | --- |
| BR1 | 7 | Los puertos, los adaptadores, la fábrica por uso y los prompts versionados |
| BR2 | 5 | Cuatro tipos de error, ningún tipo del proveedor en el núcleo, y la parada sin reintento |
| BR3 | 9 | El precio de lista, el costo, "no medido" y lo que devuelve cada suma |
| BR4 | 10 | El techo acumulado, la alerta única, el corte, la reserva de grabación y de qué no depende |
| BR5 | 9 | Los cuatro alcances de cuota, el cupo del sitio, la reserva de la voz y los topes del proveedor |
| BR6 | 7 | Los tres niveles de traza, la grafía de los nodos y los resúmenes por navegador |
| BR7 | 6 | Por qué tres tablas no llevan aseguradora y qué se paga a cambio |

Cincuenta y tres reglas. Tres parejas merecen leerse juntas, porque son las que
convierten una decisión en algo que una herramienta puede comprobar:

- **BR3.9 y BR3.5** hacen que "no medido" sobreviva a la aritmética. La primera
  impide escribir una cantidad sin su estado, en las tres formas que el costo
  toma aquí; la segunda impide sumarla sin arrastrar el conteo de lo que no se
  midió. BR3.4 añade encima la invariante que solo tiene la fila de gasto, que
  además guarda con qué precio y con qué lista se calculó.
- **BR7.1 y BR7.2** son una sola decisión en dos mitades. La primera saca tres
  tablas del aislamiento por aseguradora; la segunda cobra el precio, y lo cobra
  con una aserción contra el catálogo vivo y una lista versionada de nombres de
  columna, no con una promesa.
- **BR4.9 y BR4.10** son la reserva de grabación y su llave. La primera aparta
  del techo una porción que el enlace público no puede tocar; la segunda dice
  quién puede gastarla, y que el visitante no es esa persona.
