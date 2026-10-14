# Reglas de negocio — U2 `tenancy`

Las reglas que el aislamiento y la identidad tienen que cumplir. Es la unidad
donde una regla que solo viva en la memoria de quien la escribió se convierte,
tarde o temprano, en una fuga entre aseguradoras: por eso cada una de las
veintisiete de abajo es comprobable por una herramienta o por una prueba.

**Fuentes consumidas.** `../../../inception/units-generation/unit-of-work.md`
(las responsabilidades de U2),
`../../../inception/units-generation/unit-of-work-story-map.md` (los nueve
criterios de aceptación de US4.11 y US5.7),
`../../../inception/requirements-analysis/requirements.md` (FR8.7, FR9.1 a
FR9.6, NFR10), `../../../inception/domain-design/components.md`
(`TenantIdentity`) y
`../../../inception/contract-design/contract-summary.md` (C-07, C-10, C-11,
C-25 y C-30).

## Reglas

```yaml
rules:
  - id: BR1.1
    statement: >
      Toda consulta del aplicativo pasa por un punto único que fija la
      aseguradora de la sesión antes de devolverla. Ningún otro módulo abre una
      conexión ni construye un motor de base de datos.
    category: constraint
    applies_to: Acceso a la base de datos
    trigger: Cada vez que un módulo necesita leer o escribir.
    logic: >
      SI un módulo necesita la base de datos, ENTONCES obtiene su sesión del
      punto único, que abre la transacción, fija la aseguradora y la cierra. SI
      una regla de importación encuentra una apertura de conexión fuera de ese
      punto, ENTONCES la compuerta falla nombrando el archivo.
    violation: >
      Una segunda vía de acceso convierte el aislamiento en una convención que
      alguien puede olvidar, que es exactamente lo que FR9.1 existe para evitar.
    source: FR9.2, AC4.11.2, C-10

  - id: BR1.2
    statement: >
      La aserción de aislamiento le pregunta a la base qué tablas tiene el
      esquema del aplicativo y exige de cada una tres cosas: aislamiento
      habilitado, aislamiento forzado y al menos una política de aseguradora.
      Falla nombrando la tabla y qué le falta.
    category: validation
    applies_to: Esquema de la base de datos
    trigger: En cada corrida del guion de verificación y al arrancar el proceso.
    logic: >
      SI alguna tabla del catálogo vivo, descontada la lista de exclusión
      versionada, carece de cualquiera de las tres, ENTONCES la aserción termina
      con código distinto de cero y el mensaje nombra la tabla y lo que le
      falta.
    violation: >
      Una lista de tablas escrita a mano deja fuera la tabla que nadie se
      acordó de añadir, y esa tabla pasa la compuerta en verde sin estar
      aislada. Se le pregunta a la base, no a un archivo.
    source: FR9.1, AC4.11.1, C-10; decisión Q1 del diseño funcional de U2

  - id: BR1.3
    statement: >
      Una consulta sin filtro de aseguradora, hecha desde una sesión fijada en
      una aseguradora, devuelve solo las filas de esa aseguradora.
    category: constraint
    applies_to: Toda tabla del aplicativo
    trigger: En cada consulta.
    logic: >
      SI la sesión está fijada en una aseguradora Y la consulta no lleva filtro,
      ENTONCES el resultado contiene únicamente filas de esa aseguradora, aunque
      otra tenga filas con el mismo número de póliza o el mismo nombre.
    violation: Un filtro olvidado en el código no puede convertirse en una fuga.
    source: FR9.1, AC4.11.3, NFR10

  - id: BR1.4
    statement: Una sesión sin aseguradora fijada no devuelve ninguna fila, nunca las de otra.
    category: constraint
    applies_to: Toda tabla del aplicativo
    trigger: En cada consulta.
    logic: >
      SI la variable de sesión está vacía o ausente, ENTONCES las políticas no
      ven ninguna fila y la consulta devuelve vacío, y se registra el evento.
      Falla cerrado, nunca abierto.
    violation: >
      Una política que ante la ausencia de valor deje ver todo convierte un
      error de arranque en una fuga total.
    source: FR9.1, AC4.11.3, C-10

  - id: BR1.5
    statement: >
      Pedir una sesión para una aseguradora que no está en la configuración
      falla en el acto, antes de abrir la transacción.
    category: validation
    applies_to: Punto único de sesión
    trigger: Al pedir una sesión.
    logic: >
      SI el identificador de aseguradora no existe en la configuración cargada,
      ENTONCES la petición termina con un error que nombra el identificador, SIN
      abrir transacción. NO se devuelve una sesión sin aseguradora fijada.
    violation: >
      Devolver una sesión vacía convertiría un error del código en "no hay
      datos": la misma confusión que el proyecto prohíbe entre "no hay cláusula"
      y "no pude verificar". Un módulo podría consultar la nada durante semanas
      creyendo que la aseguradora está vacía.
    source: Decisión Q5 del diseño funcional de U2; convención 8c de `team.md`

  - id: BR1.6
    statement: Ninguna consulta se construye concatenando texto.
    category: constraint
    applies_to: Acceso a la base de datos
    trigger: En cada corrida del guion de verificación.
    logic: >
      SI el chequeo encuentra una consulta armada por concatenación o
      interpolación de texto, ENTONCES la compuerta falla nombrando el archivo.
    violation: Una consulta concatenada es la vía por la que un dato de entrada se vuelve instrucción.
    source: AC4.11.2, PRD 12.2

  - id: BR1.7
    statement: >
      El rol con el que el aplicativo se conecta no puede saltarse el
      aislamiento, y las pruebas se conectan con ese mismo rol.
    category: constraint
    applies_to: Conexión a la base de datos
    trigger: Al provisionar la base y al correr las pruebas de aislamiento.
    logic: >
      SI las pruebas se conectan con un rol que puede saltarse las políticas,
      ENTONCES una prueba de aislamiento pasa sin que exista aislamiento. Por
      eso el rol del aplicativo se crea sin esa capacidad y las pruebas usan ese
      rol y no el superusuario.
    violation: >
      Es el fallo que no avisa: la suite entera queda verde midiendo algo que no
      es lo que dice medir.
    source: AC4.11.3, C-10

  - id: BR1.8
    statement: >
      Las tres pruebas de aislamiento corren en cada entrega y cualquiera en
      rojo la detiene: consulta cruzada vacía, recuperación sin cláusulas ajenas
      y credencial ajena sin acceso a la bandeja.
    category: policy
    applies_to: Compuerta de verificación
    trigger: En cada corrida del guion de verificación.
    logic: >
      SI alguna de las tres falla, ENTONCES la entrega se detiene. No hay
      promedio, no hay excepción y el umbral no se toca.
    violation: >
      NFR10 exige exactamente cero fugas; una compuerta que se salta es una
      compuerta que no existe.
    source: FR9.4, AC4.11.4, NFR10

  - id: BR1.9
    statement: >
      El escenario adversarial de acceso a un caso ajeno corre contra el
      despliegue vivo en cada hito, en los dos idiomas, y no solo contra el
      arnés local.
    category: policy
    applies_to: Despliegue público
    trigger: En las semanas 6, 9 y 12.
    logic: >
      SI corre contra el despliegue vivo, ENTONCES no se obtiene ningún caso ni
      póliza ajena en ninguno de los dos idiomas.
    violation: >
      Las fallas de aislamiento son tan a menudo errores de configuración del
      despliegue como errores de código, y el arnés local no ve los primeros.
    source: AC4.11.5, práctica de despliegue de `team.md`

  - id: BR1.10
    statement: >
      La revisión de migración que crea una tabla del aplicativo trae, en la
      misma revisión, su columna de aseguradora, el aislamiento habilitado, el
      aislamiento forzado y su política.
    category: constraint
    applies_to: Migraciones
    trigger: Al escribir una revisión que crea una tabla.
    logic: >
      SI una revisión crea una tabla SIN su aislamiento en la misma revisión,
      ENTONCES la aserción la nombra y la compuerta se pone roja. NO existe una
      revisión posterior "que agrega el aislamiento".
    violation: Entre una revisión y la siguiente habría una ventana con datos sin aislar.
    source: AC4.11.1, C-30

  - id: BR1.11
    statement: >
      Las migraciones son una sola historia lineal con una sola cabeza, y cada
      revisión se puede deshacer.
    category: constraint
    applies_to: Migraciones
    trigger: En cada corrida del guion de verificación.
    logic: >
      SI aparecen dos cabezas, ENTONCES la compuerta las rechaza con las dos
      revisiones en conflicto. La compuerta corre subir, bajar y volver a subir
      contra una base efímera, conectándose con el rol del aplicativo.
    violation: Un conflicto de migraciones que llegue al despliegue se resuelve con la base en producción delante, que es el peor momento.
    source: C-30, ADR-002

  - id: BR2.1
    statement: La credencial de la bandeja lleva aseguradora, rol y caducidad, y va firmada.
    category: validation
    applies_to: Credencial de la bandeja
    trigger: Al emitir una credencial.
    logic: >
      SI se emite una credencial, ENTONCES su contenido firmado incluye el
      identificador de aseguradora, el identificador de la persona, su rol, el
      instante de emisión y el de caducidad.
    violation: Una credencial sin aseguradora obliga a deducirla en cada petición, y deducir es donde se equivoca uno.
    source: FR9.4, AC5.7.1

  - id: BR2.2
    statement: Una credencial de la bandeja caduca doce horas después de emitirse.
    category: policy
    applies_to: Credencial de la bandeja
    trigger: Al emitir una credencial.
    logic: >
      SI se emite a las `T`, ENTONCES caduca en `T + 12 horas`, sin prórroga
      automática. Renovar es volver a correr el comando de emisión.
    violation: >
      Sin número, "con su caducidad" no es comprobable. Doce horas cubren una
      sesión de trabajo o una demostración completa, y una credencial que se
      escape muere el mismo día.
    source: AC5.7.1; decisión Q2 del diseño funcional de U2

  - id: BR2.3
    statement: La credencial se verifica en cada petición, no solo al entrar.
    category: authorization
    applies_to: Toda ruta de la bandeja
    trigger: En cada petición.
    logic: >
      SI llega una petición a la bandeja, ENTONCES se verifica la firma, la
      caducidad y que la aseguradora de la credencial sea la de los datos que
      pide, antes de tocar la base.
    violation: Verificar solo al entrar deja una sesión abierta valiendo más que la credencial que la abrió.
    source: AC5.7.1

  - id: BR2.4
    statement: >
      Una credencial caducada, una con la firma alterada y una de otra
      aseguradora se rechazan con la misma respuesta y sin devolver ningún dato,
      tanto desde la pantalla como desde una petición directa.
    category: authorization
    applies_to: Toda ruta de la bandeja
    trigger: Al verificar una credencial.
    logic: >
      SI la credencial es inválida por cualquiera de las tres causas, ENTONCES
      la respuesta es idéntica en las tres y no distingue cuál fue.
    violation: >
      Una respuesta distinta por causa le dice a quien prueba cuál de las tres
      acertó, y eso convierte el rechazo en un oráculo.
    source: AC5.7.2

  - id: BR2.5
    statement: >
      Lo que puede hacer cada rol lo decide una tabla versionada de rol y
      acción. Una pareja que no aparece en la tabla se deniega.
    category: authorization
    applies_to: Toda acción de la bandeja
    trigger: Antes de ejecutar cualquier acción de la bandeja.
    logic: >
      SI la tabla no declara la pareja (rol, acción) como permitida, ENTONCES la
      acción se rechaza y el caso no cambia, tanto desde la pantalla como desde
      una petición directa. En particular, el rol de agente de cuenta no puede
      decidir un caso.
    violation: >
      Comprobar el rol ruta por ruta significa que la próxima ruta se olvidará
      de hacerlo, y ponerlo en la configuración de cada aseguradora dejaría que
      una se conceda a sí misma la aprobación.
    source: AC5.7.3; decisión Q4 del diseño funcional de U2

  - id: BR2.6
    statement: >
      Ninguna credencial de la bandeja aparece en el repositorio, en el README
      ni en ninguna página pública.
    category: policy
    applies_to: Repositorio y superficies públicas
    trigger: En cada corrida del guion de verificación.
    logic: >
      SI el escáner de secretos o el chequeo de contenido encuentran una
      credencial, ENTONCES la compuerta falla y la clave de firma se rota en su
      origen; borrarla del archivo no cierra el incidente.
    violation: >
      La práctica de despliegue llegó a decir que se publicaban credenciales de
      demostración por aseguradora; esa frase quedó reemplazada, y el visitante
      entra solo con el enlace firmado de su caso.
    source: AC5.7.4, D23

  - id: BR3.1
    statement: >
      El enlace firmado vive una hora, abre exactamente un caso y nunca la lista
      de la aseguradora.
    category: authorization
    applies_to: Enlace de acceso a un caso
    trigger: Al emitir y al usar un enlace.
    logic: >
      SI se emite un enlace, ENTONCES caduca una hora después y su alcance es un
      solo caso. SI con esa credencial se pide la lista de casos, ENTONCES
      responde como si no existiera.
    violation: Mostrar la lista expondría los casos de otros visitantes, que es justo lo que el enlace evita.
    source: FR8.7, AC5.7.4, C-07

  - id: BR3.2
    statement: >
      El enlace se puede canjear más de una vez mientras no haya caducado ni
      sido revocado; cada canje entrega una credencial nueva limitada a ese caso.
    category: policy
    applies_to: Enlace de acceso a un caso
    trigger: En cada canje.
    logic: >
      SI el enlace no ha caducado Y no está revocado, ENTONCES el canje se
      acepta, sube el contador de canjes y entrega la credencial. NO se quema
      con el primer uso.
    violation: >
      Quemar el token con el primer canje deja fuera a quien recargue la página
      o cierre la pestaña, con un "enlace vencido" que quien evalúa la
      demostración lee como un error nuestro. La ventana de riesgo ya la acota
      la hora.
    source: Decisión Q3 del diseño funcional de U2

  - id: BR3.3
    statement: >
      Un token inválido, uno caducado, uno revocado y uno de otro caso responden
      exactamente igual, sin decir cuál de los cuatro fue.
    category: authorization
    applies_to: Canje de enlace
    trigger: Al canjear un token.
    logic: >
      SI el canje falla por cualquiera de las cuatro causas, ENTONCES la
      respuesta es la misma en las cuatro: la de un caso que no existe.
    violation: Distinguir las causas le dice a quien prueba qué enlaces existieron alguna vez.
    source: C-07, convención de aislamiento de la API

  - id: BR3.4
    statement: La credencial que entrega un canje nunca vive más que el enlace que la originó.
    category: constraint
    applies_to: Canje de enlace
    trigger: Al entregar la credencial de un canje.
    logic: >
      SI al enlace le quedan `N` minutos, ENTONCES la credencial dura `N`
      minutos, no una hora completa. Al vencer, la pantalla muestra "enlace
      vencido".
    violation: Una credencial que sobreviva a su enlace extiende el acceso más allá de la hora que se prometió.
    source: FR8.7, C-07

  - id: BR3.5
    statement: >
      La clave del navegador se registra dentro de la aseguradora donde se usó y
      no guarda nada que identifique a una persona.
    category: constraint
    applies_to: Clave de navegador del visitante
    trigger: Al emitir y al usar una clave de navegador.
    logic: >
      SI un navegador se usa en dos aseguradoras, ENTONCES tiene una fila por
      cada una y ninguna ve la de la otra. De la clave se guarda su resumen,
      nunca la clave, y nunca un nombre, un correo ni una dirección de red.
    violation: >
      El catálogo listaba esta entidad sin aseguradora, y eso la habría dejado
      como la única tabla del aplicativo fuera de la aserción de aislamiento.
    source: FR9.1; precisión de este diseño sobre `components.md`

  - id: BR3.6
    statement: >
      Todo dato de visitante tiene un purgador declarado explícitamente, y una
      prueba falla si alguna tabla con datos de visitante no lo tiene.
    category: policy
    applies_to: Datos de visitante
    trigger: En cada corrida del guion de verificación y en el reinicio nocturno.
    logic: >
      SI una tabla guarda datos ligados al origen público o a la clave de
      navegador de un visitante Y no aparece en el registro escrito a mano de
      purgadores, ENTONCES la prueba falla nombrando la tabla. El registro es
      explícito; no se descubre solo.
    violation: >
      Un descubrimiento automático deja de encontrar lo que alguien nombró
      distinto, y la retención acotada deja de estar acotada sin que nadie lo
      note.
    source: C-11, UG-3

  - id: BR4.1
    statement: >
      Cada carpeta de aseguradora valida contra su esquema antes de quedar
      disponible; una carpeta rota apaga solo su aseguradora y nombra el archivo
      y la clave.
    category: validation
    applies_to: Configuración por aseguradora
    trigger: Al arrancar el proceso y en el guion de verificación.
    logic: >
      SI una carpeta no valida, ENTONCES esa aseguradora no queda disponible y
      el mensaje nombra el archivo y la clave rota; las demás siguen vivas. SI
      lo que está roto es la configuración de voz, ENTONCES se apaga la voz de
      esa aseguradora y su chat sigue vivo.
    violation: >
      Un error de una carpeta que tumbe las tres aseguradoras convierte un
      descuido de configuración en una caída total.
    source: FR9.3, C-25

  - id: BR4.2
    statement: >
      Ningún archivo del aplicativo contiene un identificador de aseguradora
      literal fuera del cargador de configuración y de las fixtures.
    category: constraint
    applies_to: Código del aplicativo
    trigger: En cada corrida del guion de verificación.
    logic: >
      SI el chequeo encuentra un identificador literal fuera de esos dos
      lugares, ENTONCES la compuerta falla nombrando el archivo y la línea.
    violation: >
      Una rama por aseguradora dentro del código de decisión es la forma en que
      una diferencia de configuración se convierte en una diferencia de
      comportamiento que nadie puede auditar.
    source: FR9.2, prohibición afirmada en `project.md`

  - id: BR4.3
    statement: Añadir una cuarta aseguradora es añadir una carpeta, sin tocar código.
    category: policy
    applies_to: Configuración por aseguradora
    trigger: Al añadir una aseguradora.
    logic: >
      SI se añade una carpeta que valida contra su esquema, ENTONCES esa
      aseguradora queda disponible sin ningún cambio de código.
    violation: >
      Si hiciera falta tocar código, "multi-tenant" sería un adjetivo y no una
      propiedad del sistema.
    source: FR9.3, C-25

  - id: BR4.4
    statement: >
      Una clave nueva llega opcional y con valor por defecto; quitar o renombrar
      una clave sube la versión de configuración y actualiza las tres carpetas
      en el mismo commit.
    category: constraint
    applies_to: Configuración por aseguradora
    trigger: Al cambiar el esquema de configuración.
    logic: >
      SI se añade una clave opcional con valor por defecto, ENTONCES la versión
      no sube. SI se quita o se renombra una, ENTONCES sube en uno y las tres
      carpetas se actualizan juntas.
    violation: Una carpeta que se quede en una versión vieja arranca su aseguradora con una forma que el código ya no espera.
    source: C-25
```

## Resumen

| Grupo | Reglas | De qué responden |
| --- | --- | --- |
| BR1.x | 11 reglas | El aislamiento en la base de datos: punto único de sesión, la aserción sobre el catálogo vivo, qué pasa sin aseguradora y con una que no existe, el rol que no puede saltarse nada, las pruebas en cada entrega y por hito, y las migraciones que traen su aislamiento |
| BR2.x | 6 reglas | La identidad del personal de la bandeja: qué lleva la credencial, cuánto dura, cuándo se verifica, cómo se rechaza, quién puede hacer qué y que nunca se publica |
| BR3.x | 6 reglas | El acceso del visitante: el enlace de una hora hacia un solo caso, reutilizable mientras valga, con rechazo indistinguible, y la clave de navegador con su contrato de borrado |
| BR4.x | 4 reglas | La configuración por aseguradora: validación aislada, ningún identificador literal, una carpeta nueva sin código y cómo evoluciona el esquema |

Once reglas no nacen de un criterio de aceptación de US4.11 o US5.7 y por eso se
declaran aparte en la trazabilidad. Tres salen de decisiones de este diseño
(BR1.5, BR3.2 y BR3.5) y ocho de contratos aprobados cuyos criterios pertenecen
a otras unidades (BR1.11, BR3.3, BR3.4, BR3.6, BR4.1, BR4.2, BR4.3 y BR4.4). U2
las construye porque es la dueña del contrato, aunque quien las ejercita en
pantalla sea la bandeja de U14 o el reinicio de U20.
