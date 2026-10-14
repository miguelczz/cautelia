# Reglas de negocio — U6 `web-shell`

Son 44 reglas en ocho familias: el modo claro u oscuro, el idioma y los
textos, el cliente de la API con sus errores, las superficies y el inicio, la
salud del proceso con sus páginas de estado, el proceso servido, la
accesibilidad y la telemetría de activación.

Ninguna decide algo del seguro. Deciden lo que cualquier pantalla posterior
hereda sin pedirlo, y la familia que más pesa es la cuarta: es la que convierte
en construcción la prohibición de `project.md` de prometer lo que no existe.

## Reglas

El bloque siguiente es la fuente de verdad; la tabla resumen que va después se
deriva de él.

```yaml
rules:

  # --- BR1: el modo claro u oscuro --------------------------------------------

  - id: BR1.1
    statement: >
      Sin elección guardada, el modo es el del dispositivo; con elección
      guardada, el guardado.
    category: policy
    applies_to: "ResolvedTheme"
    trigger: "Al cargar cualquier página."
    logic: >
      SI ThemePreference.value es nulo ENTONCES se usa la preferencia de color
      del sistema; SI NO, el valor guardado.
    violation: "La prueba de primera visita y la de visita con elección guardada fallan."
    source: "design-system-mapping.md (Modos de tema), interaction-spec.md (ThemeToggle), project.md (Corrections: claro y oscuro)"

  - id: BR1.2
    statement: >
      El modo se aplica antes del primer pintado: la página nunca muestra el
      modo contrario ni un cuadro sin modo.
    category: constraint
    applies_to: "Documento de la interfaz"
    trigger: "Antes de pintar cualquier página."
    logic: >
      SI la página va a pintarse ENTONCES el modo resuelto ya está aplicado al
      documento, por un paso que corre antes de cargar la aplicación.
    violation: "La prueba de extremo a extremo que mide el color del primer cuadro falla."
    source: "design-system-mapping.md (Sin salto al cargar)"

  - id: BR1.3
    statement: >
      El cambio de modo es inmediato y total; ninguna navegación lo cambia y
      ninguna pantalla impone el suyo.
    category: constraint
    applies_to: "ThemeToggle y todas las pantallas"
    trigger: "Al pulsar el selector y al navegar."
    logic: >
      SI la persona elige un modo ENTONCES todo el documento cambia sin
      transición animada y la elección se guarda; SI la persona navega
      ENTONCES el modo no cambia. Ninguna ruta declara un modo propio.
    violation: "La prueba que navega por todas las rutas registradas comprueba el mismo modo en cada una."
    source: "project.md (Corrections: claro y oscuro son modos completos), U-20"

  - id: BR1.4
    statement: >
      Una preferencia guardada ilegible se trata como ausente, sin error
      visible.
    category: validation
    applies_to: "ThemePreference"
    trigger: "Al leer la preferencia."
    logic: >
      SI el almacenamiento no está disponible o el valor no es light ni dark
      ENTONCES se sigue al dispositivo y se deja constancia en la consola del
      navegador, sin mensaje para la persona.
    violation: "La prueba con valor corrupto y con almacenamiento bloqueado falla."
    source: "phases/construction.md (manejo de errores en fronteras)"

  - id: BR1.5
    statement: >
      Todo color sale de los tokens del sistema de diseño, y el cobre de la
      marca nunca es texto sobre un fondo claro.
    category: constraint
    applies_to: "Estilos de la interfaz"
    trigger: "En cada corrida del guion de verificación."
    logic: >
      SI un estilo usa un color ENTONCES es una variable de token; SI el modo es
      claro ENTONCES el texto de marca usa la tinta #9A4F12 y no el cobre
      #E0873A.
    violation: "El chequeo de estilos rechaza colores literales fuera del archivo de tokens; axe detecta el contraste."
    source: "project.md (Corrections: el cobre nunca como texto sobre claro), design-system-mapping.md (Tokens de color)"

  - id: BR1.6
    statement: >
      El acento de una aseguradora sale de su configuración y solo marca su
      identidad; los estados de éxito, aviso y error nunca lo usan.
    category: constraint
    applies_to: "TenantBrand, estilos"
    trigger: "Al dibujar una pantalla de aseguradora."
    logic: >
      SI la pantalla pertenece a una aseguradora ENTONCES su acento se inyecta
      como variable desde TenantBrand, sin condición por aseguradora en el
      código; SI un elemento comunica éxito, aviso o error ENTONCES usa el token
      semántico, no el acento.
    violation: "La regla de la convención 9 (sin tenant_id literal) y la prueba de estilos fallan."
    source: "design-system-mapping.md (Aseguradoras ficticias), team.md convención 9, project.md (Forbidden: tenant_id literal)"

  # --- BR2: el idioma y los textos --------------------------------------------

  - id: BR2.1
    statement: >
      Una página sin aseguradora se abre en español si el idioma del
      dispositivo empieza por español, y en inglés en cualquier otro caso.
    category: policy
    applies_to: "LanguageChoice en el inicio y las páginas de estado"
    trigger: "Al cargar una página sin aseguradora sin idioma ya elegido en la pestaña."
    logic: >
      SI el primer idioma preferido del navegador empieza por "es" ENTONCES es;
      SI NO, en.
    violation: "Las pruebas con navegador en es-CO, en-US y fr-FR fallan."
    source: "Q2 de esta etapa, P12"

  - id: BR2.2
    statement: >
      Una página de aseguradora se abre en su idioma por defecto.
    category: policy
    applies_to: "LanguageChoice en las páginas de aseguradora"
    trigger: "Al abrir una página de aseguradora."
    logic: >
      SI la página pertenece a una aseguradora ENTONCES el idioma inicial es su
      default_language de la configuración, salvo elección hecha en la pestaña.
    violation: "La prueba de las tres aseguradoras falla."
    source: "C-25 (default_language), FR4.1"

  - id: BR2.3
    statement: >
      Todo texto visible sale del catálogo por una clave tipada; una clave
      inexistente es un error de tipos, no un texto vacío.
    category: constraint
    applies_to: "Todas las pantallas"
    trigger: "Al compilar la interfaz y en cada corrida del guion de verificación."
    logic: >
      SI un componente muestra texto ENTONCES lo pide al catálogo con una clave
      del módulo generado; SI la clave no existe ENTONCES la compilación falla.
    violation: "El comprobador de tipos y los chequeos de paridad y de claves sin consumidor fallan."
    source: "C-21, ADR-017, team.md convención 4"

  - id: BR2.4
    statement: >
      El documento declara su idioma, y cada mensaje o bloque en otro idioma
      declara el suyo.
    category: constraint
    applies_to: "Documento y componentes de texto"
    trigger: "Al dibujar texto."
    logic: >
      SI el idioma de un mensaje o bloque difiere del de la página ENTONCES ese
      elemento lleva su propio atributo de idioma.
    violation: "La prueba de un bloque en español dentro de una página en inglés, y al revés, falla."
    source: "AC1.33.5, accessibility-checklist.md"

  - id: BR2.5
    statement: >
      El selector de idioma muestra los nombres completos, anuncia el cambio
      una vez y deja el foco donde estaba; solo recuerda la elección entre
      visitas donde se le pide.
    category: policy
    applies_to: "LanguageSelector"
    trigger: "Al elegir un idioma."
    logic: >
      SI la persona elige un idioma ENTONCES la página cambia, se anuncia
      "Idioma: español" o "Language: English" una vez, el foco sigue en el
      selector; SI persist es falso ENTONCES la elección dura la pestaña.
    violation: "La prueba de teclado y la de anuncios fallan."
    source: "interaction-spec.md (LanguageSelector), U-04"

  # --- BR3: el cliente de la API y sus errores ---------------------------------

  - id: BR3.1
    statement: >
      Toda llamada al servidor usa el cliente generado desde el esquema de la
      API; ninguna se escribe a mano.
    category: constraint
    applies_to: "Interfaz"
    trigger: "En cada corrida del guion de verificación."
    logic: >
      SI un módulo de la interfaz habla con el servidor ENTONCES importa el
      cliente generado; SI el esquema cambió sin regenerar ENTONCES la
      comprobación de deriva falla.
    violation: "La regla de fronteras del linter y la comprobación de deriva de C-28 fallan."
    source: "C-28, ADR-002"

  - id: BR3.2
    statement: >
      Un error del servidor se muestra por la clave de catálogo de su código;
      el título y el detalle técnicos nunca se muestran.
    category: policy
    applies_to: "ProblemView"
    trigger: "Al recibir una respuesta de error."
    logic: >
      SI la respuesta es un error de C-01 ENTONCES la interfaz busca la clave
      de su code en una única tabla y muestra ese texto; title y detail solo
      van a la consola del navegador.
    violation: "La prueba que recorre todos los códigos de C-01 comprueba texto del catálogo y ausencia del detalle técnico."
    source: "C-01 (Errores), team.md convención 4, interaction-spec.md (Reglas de texto)"

  - id: BR3.3
    statement: >
      Un código de error que la interfaz no conoce cae en una rama por defecto
      con texto del catálogo, nunca en una pantalla vacía ni en texto crudo.
    category: validation
    applies_to: "ProblemView"
    trigger: "Al recibir un code fuera de la tabla."
    logic: >
      SI el code no está en la tabla ENTONCES se muestra el mensaje de "servicio
      no disponible" con su acción de reintentar, y se registra el code en la
      consola.
    violation: "La prueba con un code inventado falla."
    source: "C-01 (la rama por defecto es obligatoria en el cliente)"

  - id: BR3.4
    statement: >
      Una respuesta que no es un error de C-01 ni la esperada —cuerpo ilegible,
      red caída, tiempo agotado— se trata como servicio no disponible.
    category: validation
    applies_to: "Cliente de la API"
    trigger: "Al fallar una llamada sin error de C-01."
    logic: >
      SI la llamada falla por red, tiempo o cuerpo ilegible ENTONCES se produce
      un ProblemView con code unknown y la clave de servicio no disponible.
    violation: "Las pruebas de red caída y de cuerpo HTML en lugar de JSON fallan."
    source: "phases/construction.md (errores en fronteras), M11 (Servicio no disponible)"

  - id: BR3.5
    statement: >
      Los datos de un caso viven solo en la memoria de la pestaña; nada de un
      caso se guarda en el almacenamiento del navegador.
    category: policy
    applies_to: "Cliente de la API y caché de datos"
    trigger: "Siempre."
    logic: >
      SI un dato viene de una ruta de caso, chat o bandeja ENTONCES se guarda
      solo en la caché en memoria; ninguna capa persistente de la caché se
      activa. Lo único que la interfaz escribe en el almacenamiento son las
      preferencias de modo y, con persist, de idioma.
    violation: "La prueba que inspecciona el almacenamiento del navegador tras un recorrido falla si encuentra otra clave."
    source: "unit-of-work.md U6 (el navegador no guarda datos de casos más allá de la sesión), WebClient"

  # --- BR4: las superficies y el inicio ---------------------------------------

  - id: BR4.1
    statement: >
      La interfaz solo muestra la acción de una superficie que el servidor
      declara montada; ningún botón lleva a algo no construido.
    category: policy
    applies_to: "SiteDirectory, inicio y navegación"
    trigger: "Al dibujar el inicio y la navegación."
    logic: >
      SI la superficie no está en SiteDirectory.surfaces ENTONCES su botón, su
      enlace y su paso de "Cómo funciona" no existen en la página.
    violation: "La prueba del inicio sin superficies montadas y con una sola montada falla."
    source: "Q1 de esta etapa, project.md (Forbidden: prometer una capacidad no construida), P7"

  - id: BR4.2
    statement: >
      El inicio muestra de cada aseguradora solo lo que su configuración trae;
      lo que falta no se muestra ni se inventa.
    category: constraint
    applies_to: "TenantPresentation"
    trigger: "Al dibujar las filas de aseguradoras."
    logic: >
      SI un dato de la fila (titular, vehículo) no existe en la configuración o
      en el corpus ENTONCES la fila se dibuja sin él, sin marcador de relleno.
    violation: "La prueba de la fila con la configuración actual falla si aparece un nombre o un vehículo."
    source: "CLAUDE.md global (nunca inventar un valor de relleno), M1"

  - id: BR4.3
    statement: >
      Sin ningún canal montado, el inicio dice en una línea que la
      demostración todavía no tiene canales abiertos, y no muestra el título,
      "Cómo funciona" ni "Qué puedes probar".
    category: policy
    applies_to: "Inicio"
    trigger: "Al dibujar el inicio con SiteDirectory.surfaces sin chat ni voice_console."
    logic: >
      SI no hay chat ni consola de voz montados ENTONCES se muestra la línea del
      catálogo home.no_channels y se omiten las tres secciones que describen
      canales.
    violation: "La prueba del inicio sin canales falla."
    source: "Q1 de esta etapa"

  - id: BR4.4
    statement: >
      Los enlaces externos (README, video) aparecen solo si están configurados
      con una dirección pública.
    category: policy
    applies_to: "SiteDirectory.links"
    trigger: "Al dibujar la página de no disponible y el pie."
    logic: >
      SI la dirección no está configurada ENTONCES el enlace no se dibuja; nunca
      se enlaza el repositorio mientras sea privado.
    violation: "La prueba sin direcciones configuradas falla si aparece un enlace."
    source: "project.md (Forbidden: prometer lo no construido), D-017 (repositorio privado hasta la semana 12)"

  - id: BR4.5
    statement: >
      El número de póliza de ejemplo se muestra completo y agrupado para
      leerlo, con la frase que dice para qué sirve.
    category: policy
    applies_to: "SamplePolicyCard"
    trigger: "Al dibujar una póliza de ejemplo."
    logic: >
      SI se muestra una póliza de ejemplo ENTONCES va entera, en fuente de datos,
      con la ayuda del catálogo que dice que es la que la agente pedirá.
    violation: "La prueba de la fila falla."
    source: "M1 (Anotaciones), U-02, C-25 (forma POL- y seis dígitos)"

  # --- BR5: la salud del proceso y las páginas de estado ----------------------

  - id: BR5.1
    statement: >
      Vivo responde sin tocar la base ni los proveedores; listo comprueba la
      base, la configuración de aseguradoras y las superficies montadas en 1
      segundo, sin llamar a ningún proveedor ni gastar dinero.
    category: constraint
    applies_to: "HealthReport"
    trigger: "En cada consulta de salud."
    logic: >
      SI se consulta vivo ENTONCES responde 200 mientras el proceso corre; SI se
      consulta listo ENTONCES responde 200 con el reporte o 503 con el error de
      C-01, dentro de 1 segundo.
    violation: "La prueba de salud con base caída y la de presupuesto de tiempo fallan."
    source: "C-02"

  - id: BR5.2
    statement: >
      Toda superficie montada declara una sonda barata que no llama al modelo,
      a la voz ni a ningún proveedor y no consume límites de visitantes;
      montarla sin sonda impide arrancar.
    category: constraint
    applies_to: "SurfaceSpec, SurfaceProbe"
    trigger: "Al arrancar y en cada consulta de listo."
    logic: >
      SI un módulo declara una superficie sin sonda ENTONCES el arranque falla
      nombrando el módulo; SI una sonda llama a un puerto de proveedor
      ENTONCES la prueba de la sonda falla.
    violation: "El arranque falla con el nombre del módulo; la prueba de sondas con puertos de proveedor espiados falla."
    source: "AC5.16.1, C-24 (un módulo declarado sin su función falla al arrancar)"

  - id: BR5.3
    statement: >
      El reporte de salud solo lista superficies montadas; una sonda que falla
      o se pasa de su tiempo marca su superficie como caída.
    category: validation
    applies_to: "HealthReport.checks.surfaces"
    trigger: "En cada consulta de listo."
    logic: >
      SI una sonda falla o supera timeout_ms ENTONCES su resultado es down;
      nunca se escribe ok para una superficie no montada.
    violation: "La prueba con una sonda lenta y otra que lanza error falla."
    source: "AC5.16.1, team.md convención 8 (no colapsar un fallo en un valor neutro)"

  - id: BR5.4
    statement: >
      Mientras el proceso no está listo, la interfaz muestra "la demo está
      despertando", vuelve a consultar cada 5 segundos, y a los 60 segundos
      pasa a "no disponible"; al estar listo vuelve sola a la ruta pedida.
    category: policy
    applies_to: "ReadinessWatch"
    trigger: "Al cargar la aplicación y ante un 503 de listo o una red caída."
    logic: >
      SI listo responde 503 o no responde ENTONCES el estado pasa a waking y se
      consulta cada 5 s; SI pasan 60 s sin estar listo ENTONCES unavailable; SI
      responde 200 ENTONCES ready y se abre requested_route.
    violation: "Las pruebas con reloj simulado de los tres caminos fallan."
    source: "AC5.16.4, M11, interaction-spec.md (StatusPage)"

  - id: BR5.5
    statement: >
      Las páginas de estado son siete, con una sola plantilla, y ninguna
      muestra detalles técnicos ni nombres de aseguradoras.
    category: constraint
    applies_to: "StatusPageKind"
    trigger: "Al mostrar una página de estado."
    logic: >
      SI se muestra una página de estado ENTONCES es uno de los siete tipos,
      con título, explicación y una acción del catálogo, sin códigos ni trazas.
    violation: "La prueba de las siete páginas en los dos idiomas falla."
    source: "M11, interaction-spec.md (Reglas de texto: los errores no muestran códigos)"

  - id: BR5.6
    statement: >
      Un enlace manipulado y un caso que no existe muestran exactamente la
      misma página.
    category: constraint
    applies_to: "StatusPageKind link_invalid"
    trigger: "Al recibir link_invalid o not_found desde una ruta de caso."
    logic: >
      SI el servidor responde link_invalid o not_found en una ruta de caso
      ENTONCES la interfaz muestra link_invalid, con el mismo texto en los dos
      casos.
    violation: "La prueba que compara las dos páginas falla."
    source: "C-01 (Aislamiento: CD-10), M11"

  - id: BR5.7
    statement: >
      Con movimiento reducido, la página de espera no anima el hilo: dice
      "Despertando" en texto.
    category: constraint
    applies_to: "StatusPage waking"
    trigger: "Con la preferencia de movimiento reducido."
    logic: >
      SI el sistema pide movimiento reducido ENTONCES el hilo no avanza y se
      muestra el texto; el hilo es decorativo y el estado se lee en el título.
    violation: "La prueba con movimiento reducido emulado falla."
    source: "M11, AC1.33.6"

  # --- BR6: el proceso servido -------------------------------------------------

  - id: BR6.1
    statement: >
      La interfaz y la API se sirven desde el mismo origen; una ruta de la
      interfaz devuelve la aplicación y una ruta desconocida bajo /api devuelve
      el error de C-01, nunca la aplicación.
    category: constraint
    applies_to: "Proceso servido"
    trigger: "En cada petición."
    logic: >
      SI la ruta empieza por /api ENTONCES la atiende la API y una ruta
      inexistente responde 404 con not_found; SI es un archivo compilado
      ENTONCES se sirve; SI NO, se sirve la aplicación para que el enrutador
      de la interfaz muestre la pantalla o "no encontrada".
    violation: "Las pruebas de las tres ramas fallan."
    source: "C-01 (Base /api, mismo origen), ADR-002 (Entrega)"

  - id: BR6.2
    statement: >
      Toda respuesta del proceso lleva el mismo conjunto de cabeceras de
      seguridad.
    category: constraint
    applies_to: "SecurityHeaderSet"
    trigger: "En cada respuesta, de la API y de los estáticos, incluidos los errores."
    logic: >
      SI el proceso responde ENTONCES la respuesta lleva el conjunto completo;
      el valor de la política de contenido lo fija NFR Design.
    violation: "La prueba que recorre respuestas de las tres ramas y de error comprueba el conjunto."
    source: "unit-of-work.md U6 (Cabeceras de seguridad), ADR-002 (la política de contenido en NFR Design)"

  - id: BR6.3
    statement: >
      Los archivos compilados con huella en el nombre se guardan en caché por
      mucho tiempo; la página de entrada no se guarda nunca.
    category: policy
    applies_to: "Proceso servido"
    trigger: "Al servir estáticos."
    logic: >
      SI el archivo lleva huella de contenido ENTONCES se marca inmutable; SI es
      la página de entrada ENTONCES se marca sin caché, para que un despliegue
      nuevo se vea en la siguiente carga.
    violation: "La prueba de cabeceras de caché falla."
    source: "ADR-002 (Entrega), AC5.16.4 (la página de espera tiene que cargar rápido)"

  - id: BR6.4
    statement: >
      Toda respuesta lleva el identificador de traza, y todo error de la API
      sale con la forma de C-01.
    category: constraint
    applies_to: "Proceso servido"
    trigger: "En cada respuesta."
    logic: >
      SI el proceso responde ENTONCES la cabecera de traza está presente; SI la
      respuesta es un error de la API ENTONCES es application/problem+json con
      code y trace_id, incluidos los errores no previstos, que salen con code
      internal y sin detalle interno.
    violation: "La prueba que provoca una excepción no prevista comprueba la forma y la ausencia del detalle."
    source: "C-01 (Correlación, Errores)"

  # --- BR7: la accesibilidad ---------------------------------------------------

  - id: BR7.1
    statement: >
      Toda pantalla a la que se puede llegar está en el registro del arnés; una
      ruta de la interfaz sin registrar hace fallar la comprobación.
    category: constraint
    applies_to: "VisitableRoute"
    trigger: "En cada corrida del guion de verificación."
    logic: >
      SI el enrutador declara una ruta que no está en el registro ENTONCES la
      comprobación de completitud falla nombrando la ruta.
    violation: "El paso del arnés devuelve distinto de cero con el nombre de la ruta."
    source: "unit-of-work.md U6 (arnés que corre cada pantalla visitable), AC1.33.1"

  - id: BR7.2
    statement: >
      El arnés recorre cada pantalla registrada en español y en inglés, en modo
      claro y en oscuro; un hallazgo serio o crítico en una pantalla de
      visitante bloquea la entrega.
    category: constraint
    applies_to: "Arnés de accesibilidad"
    trigger: "En cada corrida del guion de verificación."
    logic: >
      SI el analizador automático encuentra un hallazgo serio o crítico en una
      pantalla con audience visitor, en cualquier idioma o modo, ENTONCES el
      paso falla; en una pantalla staff se reporta sin bloquear (D25).
    violation: "El paso del arnés devuelve distinto de cero y el reporte nombra pantalla, idioma, modo y regla."
    source: "AC1.33.1, US1.33 (D25), design-system-mapping.md (dos modos completos)"

  - id: BR7.3
    statement: >
      A 360 por 640 píxeles ninguna pantalla se desplaza en horizontal, y todo
      control táctil mide al menos 44 por 44.
    category: constraint
    applies_to: "Arnés de accesibilidad, primitivas"
    trigger: "En cada corrida del arnés."
    logic: >
      SI el ancho de la página supera el de la ventana a 360 px ENTONCES falla;
      SI un control interactivo mide menos de 44 × 44 ENTONCES falla.
    violation: "El paso del arnés nombra la pantalla y el control."
    source: "AC1.33.2, design-system-mapping.md (target.min)"

  - id: BR7.4
    statement: >
      Todo se alcanza con el teclado, con el foco visible y sin trampas, y el
      primer elemento de cada pantalla es el enlace para saltar al contenido.
    category: constraint
    applies_to: "Todas las pantallas, arnés"
    trigger: "En cada corrida del arnés."
    logic: >
      SI se recorre la pantalla con Tab ENTONCES cada control interactivo
      recibe el foco con el anillo visible, en orden lógico, y el recorrido
      sale de la pantalla; la única excepción es la hoja modal del teléfono,
      que se cierra con Escape.
    violation: "La prueba de recorrido con teclado de cada pantalla registrada falla."
    source: "AC1.33.3, interaction-spec.md (Teclado y foco por pantalla)"

  - id: BR7.5
    statement: >
      Cada pantalla tiene un solo anunciador cortés y uno de alerta; un mensaje
      que llega palabra por palabra se anuncia una sola vez, completo.
    category: constraint
    applies_to: "Anunciador compartido"
    trigger: "Al anunciar."
    logic: >
      SI un componente necesita anunciar ENTONCES usa el anunciador compartido
      con su tipo (estado o alerta); SI el texto se transmite por partes
      ENTONCES se anuncia al terminar.
    violation: "La prueba del anunciador con un texto transmitido en diez partes cuenta un solo anuncio."
    source: "AC1.33.4, interaction-spec.md (Anuncios para lectores de pantalla)"

  - id: BR7.6
    statement: >
      Ningún estado se comunica solo por color ni solo por movimiento; los
      textos pasan contraste AA, a 200 % de zoom no se pierde contenido y con
      movimiento reducido no hay desplazamientos ni escalas.
    category: constraint
    applies_to: "Todas las pantallas, primitivas"
    trigger: "En cada corrida del arnés."
    logic: >
      SI un elemento comunica estado ENTONCES lleva texto o un ícono con
      etiqueta; SI el sistema pide movimiento reducido ENTONCES solo quedan
      cambios de opacidad y color de hasta 160 ms.
    violation: "axe (contraste), la prueba de zoom al 200 % y la de movimiento reducido fallan."
    source: "AC1.33.6, design-system-mapping.md (Movimiento)"

  - id: BR7.7
    statement: >
      Un ícono nunca reemplaza la etiqueta de una acción, y los íconos
      decorativos están ocultos para el lector de pantalla.
    category: constraint
    applies_to: "Primitivas"
    trigger: "Al dibujar un ícono."
    logic: >
      SI un ícono acompaña una acción ENTONCES la acción tiene texto; SI es
      decorativo ENTONCES está oculto para las tecnologías de apoyo.
    violation: "Las reglas de accesibilidad de JSX del linter y axe fallan."
    source: "design-system-mapping.md (Íconos)"

  # --- BR8: la telemetría de activación ----------------------------------------

  - id: BR8.1
    statement: >
      Hay tres hitos por sesión —primer mensaje, tercer turno y ciclo cerrado
      en la bandeja— y cada uno cuenta una sola vez por sesión.
    category: calculation
    applies_to: "ActivationProgress, ActivationDaily"
    trigger: "Cuando el chat o la bandeja informan un hito."
    logic: >
      SI la sesión (aseguradora y clave del navegador) no tenía el hito
      ENTONCES se guarda el avance y se suma uno al conteo de ese día,
      aseguradora e hito, en la misma transacción; SI ya lo tenía ENTONCES no
      pasa nada.
    violation: "La prueba que informa el mismo hito tres veces comprueba un solo conteo."
    source: "AC5.16.6, Q3 de esta etapa"

  - id: BR8.2
    statement: >
      Lo único que sobrevive a la noche es el conteo por día, aseguradora e
      hito; el avance de cada sesión es dato de visitante y se borra en el
      reinicio nocturno.
    category: policy
    applies_to: "ActivationProgress, ActivationDaily"
    trigger: "En el reinicio nocturno."
    logic: >
      SI corre el reinicio nocturno ENTONCES el purgador de U6 borra
      ActivationProgress; ActivationDaily se conserva y no tiene ninguna columna
      que apunte a una persona o a un navegador.
    violation: "La prueba de completitud del registro de purgadores y la de columnas prohibidas fallan."
    source: "AC5.16.6, UG-3, C-11, project.md (Mandated: retención acotada por el reinicio nocturno)"

  - id: BR8.3
    statement: >
      Registrar un hito nunca rompe ni demora el turno que lo produjo; si falla,
      queda un evento en la traza y el turno sigue.
    category: policy
    applies_to: "Registro de hitos"
    trigger: "Al fallar el registro de un hito."
    logic: >
      SI el registro falla ENTONCES se emite un evento de fallo con el hito y el
      tipo de error y la llamada devuelve sin lanzar; el conteo de ese día
      queda por debajo y lo dice la traza.
    violation: "La prueba con la base caída comprueba que el turno termina y que existe el evento."
    source: "phases/construction.md (fallas no silenciosas), team.md convención 8d (rastro doble)"

  - id: BR8.4
    statement: >
      El chequeo periódico y las evaluaciones no cuentan como sesiones.
    category: validation
    applies_to: "Registro de hitos"
    trigger: "Cuando la petición viene del chequeo periódico o del corredor de evaluaciones."
    logic: >
      SI la petición es del chequeo periódico o del corredor ENTONCES no se
      registra ningún hito.
    violation: "La prueba que corre la sonda y un caso del corredor comprueba conteos en cero."
    source: "AC5.16.1 (no consume límites de visitantes), AC5.16.6"

  - id: BR8.5
    statement: >
      Donde se publique, la activación se muestra solo como conteos por día y
      por aseguradora, nunca por sesión.
    category: policy
    applies_to: "ActivationDaily"
    trigger: "Al leer la activación para un panel o un reporte."
    logic: >
      SI una superficie lee la activación ENTONCES recibe solo ActivationDaily;
      ActivationProgress no tiene ruta de lectura.
    violation: "La prueba de la interfaz pública de la activación comprueba que no hay lectura por sesión."
    source: "project.md (Corrections: superficies públicas solo con recuentos)"
```

## Resumen

| ID | Familia | Regla | Categoría |
| --- | --- | --- | --- |
| BR1.1 | Modo | Dispositivo sin elección; la guardada con elección | policy |
| BR1.2 | Modo | Aplicado antes del primer pintado | constraint |
| BR1.3 | Modo | Cambio inmediato; ninguna pantalla impone modo | constraint |
| BR1.4 | Modo | Preferencia ilegible = ausente, sin error visible | validation |
| BR1.5 | Modo | Solo tokens; el cobre nunca es texto sobre claro | constraint |
| BR1.6 | Modo | Acento de aseguradora desde la configuración, nunca semántico | constraint |
| BR2.1 | Idioma | Sin aseguradora: español si el dispositivo es español, si no inglés | policy |
| BR2.2 | Idioma | Con aseguradora: su idioma por defecto | policy |
| BR2.3 | Idioma | Todo texto por clave tipada del catálogo | constraint |
| BR2.4 | Idioma | Idioma declarado por documento y por bloque | constraint |
| BR2.5 | Idioma | Selector con nombres completos, un anuncio, foco estable | policy |
| BR3.1 | API | Solo el cliente generado | constraint |
| BR3.2 | API | Error por clave de catálogo; nunca el detalle técnico | policy |
| BR3.3 | API | Código desconocido: rama por defecto | validation |
| BR3.4 | API | Red caída o cuerpo ilegible: servicio no disponible | validation |
| BR3.5 | API | Datos de caso solo en memoria | policy |
| BR4.1 | Superficies | Solo acciones de superficies montadas | policy |
| BR4.2 | Superficies | Solo datos que existen; nada inventado | constraint |
| BR4.3 | Superficies | Sin canales: una línea honesta | policy |
| BR4.4 | Superficies | Enlaces externos solo si están configurados | policy |
| BR4.5 | Superficies | Póliza de ejemplo completa y con su para qué | policy |
| BR5.1 | Salud | Vivo sin dependencias; listo en 1 s sin proveedores | constraint |
| BR5.2 | Salud | Toda superficie con sonda barata o no arranca | constraint |
| BR5.3 | Salud | Solo superficies montadas; fallo = caída | validation |
| BR5.4 | Salud | Despertando cada 5 s; a los 60 s no disponible | policy |
| BR5.5 | Salud | Siete páginas de estado, sin detalle técnico | constraint |
| BR5.6 | Salud | Enlace manipulado = caso inexistente | constraint |
| BR5.7 | Salud | Movimiento reducido: texto en lugar del hilo | constraint |
| BR6.1 | Servido | Mismo origen; /api nunca devuelve la aplicación | constraint |
| BR6.2 | Servido | Mismas cabeceras de seguridad en toda respuesta | constraint |
| BR6.3 | Servido | Caché larga con huella; entrada sin caché | policy |
| BR6.4 | Servido | Traza en toda respuesta; errores con la forma de C-01 | constraint |
| BR7.1 | Accesibilidad | Toda ruta registrada en el arnés | constraint |
| BR7.2 | Accesibilidad | Dos idiomas y dos modos; serio o crítico bloquea | constraint |
| BR7.3 | Accesibilidad | 360 px sin desplazamiento; controles de 44 px | constraint |
| BR7.4 | Accesibilidad | Teclado completo, foco visible, saltar al contenido | constraint |
| BR7.5 | Accesibilidad | Un anunciador; lo transmitido se anuncia una vez | constraint |
| BR7.6 | Accesibilidad | Ni color ni movimiento solos; AA; zoom 200 % | constraint |
| BR7.7 | Accesibilidad | Ícono nunca sin etiqueta | constraint |
| BR8.1 | Activación | Tres hitos, una vez por sesión | calculation |
| BR8.2 | Activación | Sobrevive solo el conteo diario | policy |
| BR8.3 | Activación | Registrar un hito nunca rompe el turno | policy |
| BR8.4 | Activación | El chequeo y las evaluaciones no cuentan | validation |
| BR8.5 | Activación | Solo conteos, nunca por sesión | policy |
