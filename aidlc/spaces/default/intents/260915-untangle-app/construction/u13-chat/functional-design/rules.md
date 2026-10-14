# Reglas de negocio — U13 `chat`

U13 es la primera unidad que una persona de fuera puede usar. Todo lo que las doce
unidades anteriores construyeron —el aislamiento, la redacción, las citas
verificadas, el grafo— queda detrás de una página pública, y esta unidad es la que
decide qué de eso se ve y qué no.

Seis familias. La primera existe porque quien llega no sabe con quién habla, y las
cinco siguientes son lo que hace falta para que una superficie pública no se convierta
en la puerta por la que se escapa lo que las demás protegen.

**Tres reglas de esta unidad son compuertas duras** (BR1.1, BR6.2, BR6.3): pasa o
falla por caso, un solo fallo detiene la entrega.

Este diseño tuvo una familia más —la vista de comparación entre las tres
aseguradoras— que salió del alcance por decisión de Miguel del 2026-09-28: pasa a
**U23 `comparison-view`**, después de U14, porque esa vista convence cuando hay casos
reales detrás y hoy solo hay tres pólizas de ejemplo. Sus reglas viajan con ella y no
se quedan aquí declaradas sin construirse, que es la deuda que TD-03 dejó en la
landing.

## Reglas

```yaml
rules:

  - id: BR1.1
    statement: La divulgacion va antes de cualquier texto del visitante, siempre.
    category: compliance
    applies_to: "El primer mensaje de la conversacion"
    trigger: "Al cargar la pagina de chat de cualquier aseguradora, antes de que la persona escriba."
    logic: "El primer mensaje dice que habla una asistente de inteligencia artificial de esa aseguradora, que es una demostracion con polizas de ejemplo, que la conversacion se guarda para registrar el caso, que se borra cada noche y que no escriba datos personales reales. Sale del catalogo por idioma, nunca en linea. **Compuerta dura:** no es una cortesia, es la condicion para que lo que entre despues se pueda tratar como dato de demostracion y no como una captura silenciosa."
    violation: "La prueba de AC1.1.1 falla, o el chequeo de contenido encuentra la divulgacion escrita en linea en vez de en el catalogo."
    source: AC1.1.1, FR4.1, FR7.1, M10, M6

  - id: BR1.2
    statement: Un caso sin la divulgacion registrada no se puede cerrar.
    category: validation
    applies_to: "El caso abierto desde el chat"
    trigger: "Al abrir un caso en una conversacion, y al intentar cerrarlo."
    logic: "El caso guarda la divulgacion con su hora, su idioma y el canal chat. Sin ese registro el cierre se rechaza. Es la mitad comprobable de BR1.1: la primera dice que se muestre, esta dice que quede constancia, y sin la segunda la primera se puede saltar sin que nada lo note."
    violation: "La prueba de AC1.1.2 falla: un caso sembrado sin el registro se cierra."
    source: AC1.1.2, FR4.1, M10

  - id: BR1.3
    statement: Lo que la agente ofrece sale de la configuracion de la aseguradora, no de una lista fija.
    category: business_logic
    applies_to: "Las capacidades del primer mensaje"
    trigger: "Al componer el primer mensaje."
    logic: "Reportar un siniestro, resolver dudas de la poliza y pedir que una persona revise el caso van siempre; cotizar solo si esa aseguradora la tiene activa. Prometer una capacidad que la aseguradora no tiene es la forma mas facil de que el README y la pantalla dejen de coincidir, que es lo que la prohibicion del proyecto sobre prometer lo no construido persigue."
    violation: "La prueba de AC1.1.3 falla: la aseguradora con la cotizacion inactiva la ofrece."
    source: AC1.1.3, FR14.4, M17

  - id: BR2.1
    statement: La agente responde en el idioma del mensaje, sin tocar el selector.
    category: business_logic
    applies_to: "El idioma de cada turno"
    trigger: "Con cada mensaje de la persona."
    logic: "El idioma se detecta del texto del turno y manda sobre el idioma con el que abrio la pagina. El selector muestra el idioma en que **responde** la agente, no una preferencia guardada: asi lo que se ve y lo que pasa no se separan."
    violation: "La prueba de AC1.2.1 falla: un primer mensaje en espanol sobre una pagina que abrio en ingles recibe respuesta en ingles."
    source: AC1.2.1, AC1.2.2, FR4.4, M10

  - id: BR2.2
    statement: Un mensaje demasiado corto o sin senal no cambia el idioma.
    category: constraint
    applies_to: "La deteccion de idioma"
    trigger: "Cuando llega un 'ok', una placa, un numero o un nombre propio."
    logic: "Sin senal suficiente, el idioma es el que ya tenia la conversacion. Cambiar de idioma por un 'ok' es peor que no cambiarlo nunca: rompe la conversacion a mitad por un turno que no dice nada."
    violation: "La prueba de AC1.2.3 falla."
    source: AC1.2.3, FR4.4

  - id: BR2.3
    statement: Un idioma que la demo no atiende se dice, no se finge.
    category: business_logic
    applies_to: "La deteccion de idioma"
    trigger: "Cuando el mensaje no esta en espanol ni en ingles."
    logic: "Se responde en el idioma de la pagina con la frase del catalogo que dice que la demostracion atiende esos dos, y se sigue. Nunca se responde en un tercer idioma, y nunca se ignora el turno."
    violation: "La prueba de AC1.2.5 falla."
    source: AC1.2.5, FR4.4, P12

  - id: BR3.1
    statement: Los limites del chat se aplican por sesion, por origen y por dia, y el mensaje al llegar es honesto.
    category: constraint
    applies_to: "Cada mensaje entrante"
    trigger: "Antes de llamar al modelo."
    logic: "Los tres limites vienen de la configuracion y el reloj es inyectado. Al superarse, la respuesta es la frase del catalogo que dice que se llego al limite de la demostracion y cuando se puede seguir --nunca un error generico-- y el caso queda guardado. Los limites se reinician a la hora configurada, comprobado un minuto antes y un minuto despues."
    violation: "La prueba de AC5.13.1 o de AC5.13.2 falla."
    source: AC5.13.1, AC5.13.2, FR4.6, M20, RT-13

  - id: BR3.2
    statement: Una rafaga o un mensaje demasiado largo se rechaza sin llamar al modelo.
    category: constraint
    applies_to: "Cada mensaje entrante"
    trigger: "Cuando llega mas seguido que el intervalo minimo, o mas largo que el maximo."
    logic: "El rechazo ocurre antes del proveedor, no despues: un limite que se comprueba llamando primero al modelo no protege el presupuesto, lo gasta. La frase es del catalogo."
    violation: "La prueba de AC5.13.3 falla, o la traza registra una llamada al proveedor en un turno rechazado."
    source: AC5.13.3, FR4.6, M20

  - id: BR3.3
    statement: La clave del modelo para el chat es propia y tiene su tope en el proveedor.
    category: security
    applies_to: "La configuracion del proveedor del chat"
    trigger: "Al construir el cliente del modelo para este canal."
    logic: "Distinta de la de voz y de la de evaluaciones, con su propio tope configurado **en el proveedor** y no solo en la aplicacion: un limite que vive solo en la aplicacion falla abierto cuando lo que falla es la aplicacion. Con la cuota del chat agotada en pruebas, la voz y las evaluaciones siguen."
    violation: "La prueba de AC5.13.4 falla, o la fabrica de clientes construye el del chat con la clave de otro uso."
    source: AC5.13.4, FR4.6, M20, D-015, P9

  - id: BR4.1
    statement: Una cita se muestra con su identificador, su version y su texto completo expandible.
    category: business_logic
    applies_to: "La respuesta de cobertura en el chat"
    trigger: "Cuando la respuesta trae citas verificadas."
    logic: "El identificador y la version vienen del verificador de U8; el texto completo se expande en la pagina y no se resume. Esta unidad no decide si una clausula aplica --eso ya lo decidio el grafo-- y no reescribe su texto."
    violation: "La prueba de AC2.3.1 falla."
    source: AC2.3.1, FR4.3, FR5.6, M4

  - id: BR4.2
    statement: La clausula en otro idioma se muestra en el suyo, etiquetada, y la explicacion aparte.
    category: compliance
    applies_to: "La cita expandida"
    trigger: "Cuando la clausula esta escrita en un idioma distinto del de la conversacion."
    logic: "El texto literal aparece en su idioma original con esa etiqueta, y la explicacion en el idioma de la persona marcada como resumen. **Nunca se muestra una traduccion automatica como si fuera el texto literal:** lo que la persona compara contra su poliza tiene que ser lo que su poliza dice."
    violation: "La prueba de AC2.3.4 falla."
    source: AC2.3.4, FR5.6, P2

  - id: BR4.3
    statement: El resumen de traza se ve sin credencial, redactado, y solo el de la conversacion del propio navegador.
    category: security
    applies_to: "El resumen de traza enlazado desde una respuesta"
    trigger: "Al abrir el enlace del resumen."
    logic: "Muestra los nodos recorridos, las clausulas recuperadas y verificadas, la latencia y el costo, con los datos personales redactados por el punto unico de salida de U3. Con un identificador de otra conversacion responde igual que ante uno inexistente. Es la misma forma que el resto del proyecto: la respuesta ante lo ajeno y ante lo inexistente no se distinguen."
    violation: "La prueba de AC2.3.2 falla, o el reporte de redaccion encuentra un dato personal en el resumen."
    source: AC2.3.2, FR4.3, M6, M7, RT-4

  - id: BR4.4
    statement: Una traza que todavia se esta registrando se dice asi, nunca 'no encontrado'.
    category: business_logic
    applies_to: "El resumen de traza"
    trigger: "Cuando se abre antes de que la traza termine de escribirse."
    logic: "La pagina dice que se esta registrando y se actualiza sola. 'No encontrado' seria mentir sobre algo que si existe, y ademas confundiria el caso legitimo con el de BR4.3, donde 'no encontrado' es la respuesta correcta."
    violation: "La prueba de AC2.3.3 falla."
    source: AC2.3.3, FR4.3

  - id: BR5.1
    statement: La decision del ajustador aparece en la conversacion donde se reporto, con su comentario y el numero de caso.
    category: business_logic
    applies_to: "El aviso de la decision"
    trigger: "Cuando el ajustador aprueba, rechaza o marca el caso como enviado a la aseguradora."
    logic: "Aparece al volver a la conversacion, o en menos de un minuto si esta abierta. Dice el resultado, el comentario y --en el rechazo-- que puede hacer el asegurado. El aviso de 'enviado a la aseguradora' no promete que esa aseguradora vaya a contactar a nadie, porque el traspaso real no existe."
    violation: "La prueba de AC1.18.1, AC1.18.2 o AC1.18.3 falla."
    source: AC1.18.1, AC1.18.2, AC1.18.3, FR8.5, M11, W1

  - id: BR5.2
    statement: El aviso pasa por la guardia de salida, y sin decision registrada se bloquea.
    category: security
    applies_to: "El aviso de la decision"
    trigger: "Al emitir el aviso al asegurado."
    logic: "La guardia admite que el texto afirme un resultado **porque va ligado al identificador de esa decision humana**; el mismo texto sin una decision registrada se bloquea. El comentario del ajustador se redacta en la traza y en el log. Es el unico camino por el que una salida de este sistema puede afirmar cobertura, y lo que lo autoriza es la firma de una persona."
    violation: "La prueba de AC1.18.4 falla: el texto sin decision registrada llega al asegurado."
    source: AC1.18.4, FR8.5, M11, M6, P1

  - id: BR5.3
    statement: Un caso derivado y aun sin decidir lo dice, sin inventar una fecha.
    category: business_logic
    applies_to: "El estado del caso en la conversacion"
    trigger: "Cuando la persona vuelve a una conversacion cuyo caso espera decision."
    logic: "Dice que un ajustador lo esta revisando y no promete cuando. Prometer un plazo que nadie puede cumplir es la forma barata de que la demo parezca mejor de lo que es."
    violation: "La prueba de AC1.18.5 falla."
    source: AC1.18.5, FR8.5, P7

  - id: BR6.1
    statement: Se retoma un caso desde el propio navegador o con el enlace firmado, y solo lo que falta.
    category: business_logic
    applies_to: "La retoma de un caso por chat"
    trigger: "Cuando la persona escribe un numero de caso desde el navegador que lo creo, o abre su enlace firmado, y se identifica con su poliza."
    logic: "El chat retoma desde el mismo punto de control que dejo U12 y pide solo los campos que faltan. Los campos confirmados no se vuelven a preguntar: es la misma promesa que BR3.2 de U12, vista desde el canal."
    violation: "La prueba de AC1.20.1 falla: se vuelve a pedir un campo ya confirmado."
    source: AC1.20.1, F2.6, F4.6

  - id: BR6.2
    statement: Un numero de caso creado desde otro navegador responde igual que uno que no existe.
    category: security
    applies_to: "La retoma de un caso por chat"
    trigger: "Cuando el numero de caso llega desde un navegador que no es el que lo creo, aunque la poliza coincida."
    logic: "**Compuerta dura.** Identica en texto y en estado a la respuesta ante un numero inexistente. Las tres polizas de ejemplo son publicas a proposito, asi que identificarse con una no prueba nada: lo que ata un caso a una persona es la clave de su navegador o el enlace firmado. Y la filtracion no seria el dato, seria la distincion: recibir algo distinto ya dice que ese caso existe."
    violation: "La prueba de AC1.20.2 falla: las dos respuestas se distinguen en algo."
    source: AC1.20.2, RT-4, M9, F8.7

  - id: BR6.3
    statement: Un numero de caso de otra aseguradora responde igual que uno que no existe.
    category: security
    applies_to: "La retoma de un caso por chat"
    trigger: "Cuando el numero de caso pertenece a otra aseguradora."
    logic: "**Compuerta dura.** Y no lo sostiene una comprobacion de esta unidad: la politica de fila lo filtro antes de que la consulta lo viera, asi que el codigo del chat nunca llega a saber cual de los dos casos era. Esta unidad solo tiene que no reintroducir la distincion al componer la respuesta."
    violation: "La prueba de AC1.20.3 falla."
    source: AC1.20.3, RT-4, M9

  - id: BR6.4
    statement: Un caso empezado por voz y terminado por chat es un unico caso, con el canal marcado en cada turno.
    category: business_logic
    applies_to: "La transcripcion del caso"
    trigger: "Al escribir cada turno del chat en un caso que ya tenia turnos de voz."
    logic: "Un caso, una transcripcion en orden, y cada turno con su canal. Dos casos para una misma persona que cambio de canal es la forma en que un sistema pierde la mitad de lo que le contaron."
    violation: "La prueba de AC1.20.4 falla."
    source: AC1.20.4, F2.6





```

## Resumen

| Regla | Qué protege |
| --- | --- |
| BR1.1 [bloquea] | La divulgación va antes de cualquier texto del visitante |
| BR1.2 | Un caso sin divulgación registrada no se cierra |
| BR1.3 | Lo que se ofrece sale de la configuración de la aseguradora |
| BR2.1 | La respuesta va en el idioma del mensaje |
| BR2.2 | Un mensaje sin señal no cambia el idioma |
| BR2.3 | Un idioma no atendido se dice, no se finge |
| BR3.1 | Límites por sesión, origen y día, con mensaje honesto |
| BR3.2 | La ráfaga se rechaza antes de llamar al modelo |
| BR3.3 | Clave propia del chat con su tope en el proveedor |
| BR4.1 | La cita con su identificador, versión y texto completo |
| BR4.2 | La cláusula en otro idioma no se traduce como si fuera literal |
| BR4.3 | El resumen de traza: redactado, y solo el del propio navegador |
| BR4.4 | Una traza en curso no es "no encontrado" |
| BR5.1 | La decisión del ajustador llega a su conversación |
| BR5.2 | El aviso pasa por la guardia; sin decisión se bloquea |
| BR5.3 | Un caso sin decidir no promete una fecha |
| BR6.1 | Retomar pide solo lo que falta |
| BR6.2 [bloquea] | Caso de otro navegador = caso inexistente |
| BR6.3 [bloquea] | Caso de otra aseguradora = caso inexistente |
| BR6.4 | Un caso, dos canales, cada turno marcado |
