# Reglas de negocio — U3 `pii-redaction`

Las reglas que la redacción tiene que cumplir. Esta es la unidad donde una regla
que solo viva en la memoria de quien la escribió se convierte, tarde o temprano,
en un dato de una persona real dentro de una traza: por eso **cada una de las
veintiocho de abajo es comprobable por una herramienta o por una prueba**, y
las que no lo eran se reescribieron hasta que lo fueran. Tres de ellas —BR1.8, BR2.9 y
BR3.5— nacieron de la revisión y del repaso a fondo que la siguió, que encontró que la garantía central se apoyaba
en un tipo que no existe en tiempo de ejecución y que un criterio no tenía regla
que lo describiera.

Los identificadores `BR` son **de esta unidad**, como en las demás: el `BR1.1` de
U2 es otra regla distinta, y lo que los desambigua es el campo `unit` de su
`traceability.json`.

**Fuentes consumidas.** Las mismas que `entities.md`, más las respuestas de
`functional-design-questions.md` (Q1 a Q3).

## Reglas

```yaml
rules:
  # --- Grupo 1: el punto único de salida (US4.12) --------------------------

  - id: BR1.1
    statement: >
      Todo texto que sale del aplicativo hacia una transcripción, un log, una
      traza, una exportación, el reporte de evaluaciones o la transcripción en
      vivo pasa antes por el punto único de redacción.
    category: policy
    applies_to: Todo módulo del aplicativo
    trigger: Cualquier escritura hacia una de las seis superficies declaradas
    logic: >
      SI un módulo va a escribir texto en una superficie de salida ENTONCES ese
      texto es un `Redacted`, y `Redacted` solo lo fabrica `compliance.redaction`.
    violation: El código no compila, y la regla de importación falla antes que eso
    source: FR7.3, AC4.12.2, C-13

  - id: BR1.2
    statement: >
      Un punto de salida nuevo que no pase por la redacción es imposible de
      escribir, no meramente detectable al revisarlo.
    category: constraint
    applies_to: Los seis puntos de salida declarados
    trigger: Alguien añade un escritor
    logic: >
      SI un escritor acepta `str` en vez de `Redacted` ENTONCES no es un punto de
      salida declarado, y la regla de importación prohíbe que escriba hacia
      afuera.
    violation: La prueba con el escritor plantado a propósito falla la entrega
    source: project.md (Forbidden), AC4.12.2, PRD 12.2
    note: >
      El tipo es la señal; el control es BR1.8. `NewType` no existe en tiempo de
      ejecución y no impide que alguien escriba `Redacted(texto_sin_tapar)`.
      Decirlo aquí, y no dejar la garantía apoyada en el tipo, es el hallazgo
      R-02 de la revisión.

  - id: BR1.3
    statement: >
      La lista de puntos de salida vive declarada en un solo sitio, con su
      superficie y su unidad dueña.
    category: constraint
    applies_to: El registro de puntos de salida
    trigger: La comprobación de la regla de importación
    logic: >
      SI un módulo escribe hacia una superficie de salida Y no está en el
      registro ENTONCES la comprobación falla nombrando el módulo.
    violation: Entrega detenida
    source: AC4.12.2

  - id: BR1.4
    statement: >
      La redacción ocurre **antes de persistir**, no solo antes de exportar.
    category: policy
    applies_to: Transcripción, log y traza
    trigger: Se guarda un turno
    logic: >
      SI un turno se persiste ENTONCES su transcripción, su traza y su log ya
      llevan los datos personales tapados.
    violation: La prueba que siembra teléfono, cédula, placa y póliza en un turno y lee lo guardado falla
    source: AC4.12.1, project.md (Mandated)

  - id: BR1.5
    statement: >
      Los campos estructurados del caso y el punto de control **no** se redactan:
      guardan el dato en claro con la protección que fija la tabla de almacenes.
    category: constraint
    applies_to: Campos del caso, punto de control del grafo
    trigger: Se escribe un campo estructurado
    logic: >
      SI el destino es un campo estructurado del caso ENTONCES no pasa por la
      redacción, porque el caso necesita el dato para trabajar y su protección es
      la del almacén, no la del tapado.
    violation: Un caso sin dato utilizable; la prueba de extremo a extremo de U4 falla
    source: AC4.12.1

  - id: BR1.6
    statement: >
      El tapado es irreversible. No existe bóveda de tokens ni correspondencia
      guardada que permita recuperar el original desde el texto redactado.
    category: constraint
    applies_to: El módulo entero
    trigger: Diseño y revisión del módulo
    logic: >
      SI existiera una forma de deshacer el tapado ENTONCES existiría un único
      sitio con todos los datos personales juntos, que es peor que no tapar.
    violation: >
      Un chequeo de analisis estatico falla si aparece cualquier estructura que
      relacione un valor detectado con su etiqueta o con su original: un
      diccionario, una tabla, un indice o un campo que guarde el texto de
      entrada. La regla no se verifica leyendo el codigo con atencion.
    source: Decisión FD-U3-2, con su verificación fijada tras el hallazgo R-04 de la revisión

  - id: BR1.7
    statement: >
      Si el detector no puede cargar sus reconocedores, el punto de salida **no
      emite texto**: responde con la clave de degradación del catálogo.
    category: policy
    applies_to: Los seis puntos de salida
    trigger: El detector falla al cargar o al ejecutar
    logic: >
      SI la redacción no se puede ejecutar ENTONCES no sale texto, sale la frase
      de degradación. Fallar cerrado es la única opción admitida.
    violation: La prueba que rompe la carga de reconocedores a propósito y exige silencio falla
    source: C-13, phases/construction.md

  - id: BR1.8
    statement: >
      El constructor de `Redacted` solo se invoca dentro de
      `compliance/redaction/api.py`. En ningún otro archivo del aplicativo
      aparece `Redacted(` seguido de algo que no venga del detector.
    category: constraint
    applies_to: Todo el código del aplicativo
    trigger: El chequeo de análisis estático del guion de verificación
    logic: >
      SI cualquier archivo fuera de `compliance/redaction/api.py` invoca el
      constructor ENTONCES el chequeo falla nombrando el archivo y la línea.
      Es necesario porque `NewType` **no existe en tiempo de ejecución**:
      `Redacted(texto_sin_tapar)` es una llamada legal que el comprobador de
      tipos acepta, y sin este chequeo la garantía de BR1.2 se apoyaría en que a
      nadie se le ocurra escribirla.
    violation: >
      La prueba planta esa llamada en un archivo cualquiera y exige que el
      chequeo falle; y una segunda prueba comprueba que el árbol correcto pasa,
      para que un fallo del andamiaje no se confunda con un chequeo que funciona.
    source: Hallazgo R-02 de la revisión; regla dura de C-13

  # --- Grupo 2: los reconocedores (US4.13) --------------------------------

  - id: BR2.1
    statement: >
      Los cuatro tipos propios del dominio —placa, cédula, teléfono y número de
      póliza— se detectan en español y en inglés.
    category: validation
    applies_to: El juego de reconocedores
    trigger: Pasa un texto por el detector
    logic: >
      SI el texto contiene uno de los cuatro tipos en cualquiera de los dos
      idiomas ENTONCES se detecta y se tapa.
    violation: Entrega detenida; es un Must (M6)
    source: AC4.13.1, FR7.3

  - id: BR2.2
    statement: >
      También se detectan dictados en palabras ("tres cero cero cinco", "five
      five five") y escritos con espacios o guiones.
    category: validation
    applies_to: Los cuatro reconocedores propios
    trigger: El asegurado dicta un dato por voz, o lo escribe separado
    logic: >
      SI el dato aparece deletreado, con espacios o con guiones ENTONCES se
      detecta igual que en su forma compacta.
    violation: La prueba con las tres formas del mismo dato falla
    source: AC4.13.2

  - id: BR2.3
    statement: >
      Un dato dictado en un idioma dentro de un turno del otro idioma se tapa
      igual. Cambiar de idioma no es una vía para sacar un dato en claro.
    category: validation
    applies_to: El juego de reconocedores
    trigger: Turno mixto (RT-15)
    logic: >
      SI el turno está en inglés Y el dato viene dictado en español, o al revés,
      ENTONCES se detecta y se tapa.
    violation: Compuerta dura. Un solo caso detiene la entrega
    source: AC4.13.4 [bloquea], RT-15

  - id: BR2.4
    statement: >
      Los reconocedores de cédula y teléfono apuntan a los **formatos reales** de
      Colombia y de Estados Unidos, además de los de la demostración.
    category: validation
    applies_to: Reconocedores de national_id y phone
    trigger: Entra texto por una superficie pública
    logic: >
      SI un visitante escribe un documento o un teléfono real ENTONCES se detecta,
      porque desde el día en que el chat es público entran datos de personas
      reales aunque el corpus sea sintético.
    violation: Un dato real sin tapar en una traza; es un hallazgo de NFR11
    source: Decisión de Miguel en Q2, project.md (Mandated), M10

  - id: BR2.5
    statement: >
      Además de los reconocedores, una regla de respaldo tapa secuencias largas
      de dígitos cuando el texto alrededor habla de un dato personal.
    category: validation
    applies_to: El detector
    trigger: Hay dígitos que ningún reconocedor reclama
    logic: >
      SI una secuencia de dígitos aparece junto a una frase de contexto declarada
      ("mi número es", "my ID is") Y ningún reconocedor la reclamó ENTONCES se
      tapa como `unclassified`.
    violation: Un formato no previsto sale en claro y nadie se entera
    source: Decisión de Miguel en Q3

  - id: BR2.6
    statement: >
      Cada reconocedor declara su identificador, su tipo de entidad, su idioma,
      su mecanismo y la procedencia de su formato.
    category: constraint
    applies_to: La configuración de reconocedores
    trigger: Se carga el juego de reconocedores
    logic: >
      SI a un reconocedor le falta cualquiera de los cinco campos ENTONCES no
      carga y el arranque falla nombrándolo.
    violation: El aplicativo no arranca
    source: AC4.14.1, Decisión FD-U3-3

  - id: BR2.7
    statement: >
      Un reconocedor sirve a **un** idioma. No existe el reconocedor que dice
      servir a los dos.
    category: constraint
    applies_to: La configuración de reconocedores
    trigger: Se carga el juego de reconocedores
    logic: >
      SI un reconocedor declarara dos idiomas ENTONCES su medición por idioma
      sería un promedio, y un idioma roto quedaría escondido tras el otro.
      Esto gobierna **cómo se declara y se mide** un reconocedor, no cuáles
      corren: los dos juegos corren siempre (BR2.9).
    violation: No carga
    source: P12, AC4.13.3

  - id: BR2.8
    statement: >
      Añadir un formato nuevo es añadir una entrada de configuración versionada,
      sin tocar el código de detección.
    category: constraint
    applies_to: El juego de reconocedores
    trigger: Aparece un formato nuevo
    logic: >
      SI un formato nuevo exigiera cambiar lógica ENTONCES el juego dejaría de
      ser revisable de un vistazo, que es su única defensa contra el olvido.
    violation: La prueba que añade un reconocedor de prueba solo con configuración falla
    source: team.md (convención 9), Decisión FD-U3-3
    location: >
      `app/backend/src/untangle/compliance/redaction/recognizers/<idioma>.yaml`,
      un archivo por idioma, versionado. Es YAML porque lo escribe una persona
      (CD-4). La ruta se declara aquí porque U21 la lee **como archivo**, sin
      importar este módulo (BR4.6), y sin ella esa comprobación no se puede
      implementar: hallazgos R-05 y R-06 de la revisión.

  - id: BR2.9
    statement: >
      En cada llamada corren **los reconocedores por formato de los dos
      idiomas**, sea cual sea el idioma de la conversación. Los que vienen del
      modelo de lenguaje —nombre, lugar, organización— corren solo en el idioma
      del turno. El idioma decide en qué idioma se escribe la etiqueta, y qué
      modelo se consulta, pero nunca qué formatos se buscan.
    category: constraint
    applies_to: El detector
    trigger: Cada llamada al punto de redacción
    logic: >
      SI solo corriera el juego del idioma del turno ENTONCES una cédula dictada
      en español dentro de un turno en inglés no se detectaría, y BR2.3 —que es
      compuerta dura y existe precisamente para eso— fallaría por construcción y
      no por un error de configuración.
    violation: >
      La prueba de RT-15 alimenta el dato en un idioma dentro de un turno del
      otro y exige que se tape. Una segunda prueba comprueba que el informe
      atribuye el hallazgo al reconocedor que lo encontró y no al idioma del
      turno: si no, la medición por idioma diría que el español funciona cuando
      quien atrapó el dato fue el juego inglés.
    source: AC4.13.4 [bloquea], RT-15; añadida en la revisión a fondo del 2026-09-20
    note: >
      **Acotada al construirla, con medición.** La primera redacción de esta
      regla hacía correr también el modelo del otro idioma sobre el turno. Sobre
      los mismos tres turnos realistas en español: sin acotar, 8 hallazgos
      falsos; con la acotación, 1. Y los hallazgos **verdaderos son los mismos
      cinco** en los dos casos: el modelo inglés leyendo prosa española no
      aportó ni un dato personal que el juego español no tuviera ya. Los siete
      que desaparecen son cosas como `lo cobran`, `si lo cubre la` y `misma
      mia`, marcadas como nombres de persona.

      La razón por la que esta regla existe no se toca: un **formato** pertenece
      a un idioma, y por eso los de los dos corren siempre, que es lo que cierra
      RT-15. Un nombre de persona no cambia de forma porque el turno cambie de
      idioma. Los cuatro tipos que RT-14 y RT-15 miden son todos por formato, y
      las treinta semillas pasan igual, incluidas las seis de turno mixto.

  # --- Grupo 3: las etiquetas (Q1) ----------------------------------------

  - id: BR3.1
    statement: >
      En lugar del dato aparece la etiqueta de su tipo, nunca sus dígitos ni una
      parte de ellos.
    category: policy
    applies_to: Las seis superficies de salida
    trigger: Se tapa un dato
    logic: >
      SI se tapa un dato ENTONCES lo que queda es su etiqueta completa; no se
      deja un prefijo, un sufijo ni una longitud.
    violation: La prueba que compara lo guardado contra el dato sembrado falla
    source: AC4.12.3, D20

  - id: BR3.2
    statement: >
      La etiqueta se escribe en el **idioma de la conversación**, desde el
      catálogo de textos, y se guarda ya escrita.
    category: policy
    applies_to: El punto de redacción
    trigger: Se tapa un dato
    logic: >
      SI la conversación es en español ENTONCES la etiqueta es `[TELÉFONO n]`; si
      es en inglés, `[PHONE n]`. Se guarda escrita para que un renglón de log o
      una traza exportada se entiendan fuera del aplicativo, sin catálogo que
      resolver.
    violation: Paridad de idiomas rota; el chequeo de claves del catálogo falla
    source: Decisión de Q1, team.md (convención 4)

  - id: BR3.3
    statement: >
      La etiqueta lleva un número por tipo **dentro del texto que se redacta en
      una llamada**, de modo que dos datos distintos del mismo tipo se
      distingan. La numeración empieza de nuevo en cada llamada y no se mantiene
      entre turnos.
    category: policy
    applies_to: El punto de redacción
    trigger: Hay más de un dato del mismo tipo en el mismo texto
    logic: >
      SI en un turno aparecen el teléfono del asegurado y el del testigo ENTONCES
      son `[TELÉFONO 1]` y `[TELÉFONO 2]`, y el mismo valor repetido dentro de
      ese mismo texto conserva su número.
      SI el mismo teléfono reaparece en otro turno ENTONCES puede llevar otro
      número, y eso es deliberado: mantenerlo exigiria guardar la
      correspondencia entre el valor real y su numero, que es exactamente la
      bóveda que BR1.6 prohíbe.
    violation: La prueba que redacta un texto con dos telefonos distintos y uno repetido falla
    source: Decisión de Q1, acotada por BR1.6 tras el hallazgo R-01 de la revisión

  - id: BR3.4
    statement: >
      Cada tipo de entidad tiene su clave en el catálogo de textos, en los dos
      idiomas.
    category: constraint
    applies_to: El catálogo de textos
    trigger: El chequeo de paridad del catálogo
    logic: >
      SI un tipo no tiene clave en alguno de los dos idiomas ENTONCES el chequeo
      falla, igual que con cualquier otro texto visible.
    violation: Entrega detenida
    source: P12, team.md

  - id: BR3.5
    statement: >
      En la transcripción en vivo, un fragmento no se muestra hasta que la
      redacción lo ha visto completo. La consola muestra lo acumulado solo hasta
      el último punto donde ningún hallazgo quedaría cortado por la mitad.
    category: policy
    applies_to: La superficie `live_partial`
    trigger: Llega un fragmento parcial mientras el asegurado habla
    logic: >
      SI un fragmento podría contener el principio de un dato que todavía no
      tiene forma reconocible ENTONCES esa porción no se muestra; se acumula y se
      vuelve a redactar con lo anterior de la misma frase. Un número mostrado y
      tapado medio segundo después ya se leyó, y la captura de pantalla lo
      conserva.
    violation: >
      La prueba alimenta un teléfono dígito a dígito y exige que **ningún**
      fotograma intermedio de la salida contenga dos o más dígitos consecutivos
      del número sembrado.
    source: AC4.12.3, Decisión FD-U3-6; añadida tras el hallazgo R-03 de la revisión

  # --- Grupo 4: la medición y las compuertas ------------------------------

  - id: BR4.1
    statement: >
      La detección se mide y se publica **por idioma y por tipo de entidad**,
      nunca como promedio combinado.
    category: policy
    applies_to: El informe de redacción
    trigger: Se publica un resultado de RT-14
    logic: >
      SI el reporte mostrara un promedio ENTONCES un idioma o un tipo rotos
      quedarían escondidos tras los que funcionan.
    violation: Entrega detenida
    source: AC4.13.3, NFR11, P12

  - id: BR4.2
    statement: >
      Los hallazgos de la regla de respaldo se reportan en su propia cifra y no
      se suman a los de ningún tipo.
    category: policy
    applies_to: El informe de redacción
    trigger: Se produce el informe
    logic: >
      SI el respaldo tapa mucho ENTONCES es la señal de que un reconocedor dejó
      de funcionar; sumarlo a su tipo borraría esa señal.
    violation: Una caída de reconocedor invisible durante semanas
    source: Decisión de Q3, Decisión FD-U3-4

  - id: BR4.3
    statement: >
      Los datos ficticios se tapan igual que los reales.
    category: policy
    applies_to: Las seis superficies
    trigger: Se exportan las trazas de una corrida de DS-2
    logic: >
      SI un nombre, una placa o un teléfono provienen del corpus sintético
      ENTONCES se tapan igual: una excepción para datos de prueba es una
      excepción que alguien terminará aplicando a datos que no lo son.
    violation: La prueba sobre las trazas exportadas de DS-2 falla
    source: AC4.12.4

  - id: BR4.4
    statement: >
      El reporte de evaluaciones tampoco muestra datos personales, y describe la
      diferencia entre lo esperado y lo obtenido sin mostrar el valor completo.
    category: policy
    applies_to: El reporte por caso
    trigger: Un caso de DS-2 falla en un campo que contiene un dato personal
    logic: >
      SI el reporte tuviera que mostrar la diferencia ENTONCES la describe —tipo,
      longitud, en qué difiere— sin imprimir el valor.
    violation: El reporte se convierte en un punto de fuga
    source: AC4.12.5

  - id: BR4.5
    statement: >
      Cero datos personales en trazas, logs, exportaciones y reporte. Un solo
      hallazgo detiene la entrega.
    category: policy
    applies_to: La compuerta
    trigger: Cada corrida de la compuerta
    logic: >
      SI aparece un hallazgo ENTONCES la entrega se detiene; no hay umbral que
      bajar ni promedio que lo diluya.
    violation: Compuerta dura de NFR11
    source: NFR11 [bloquea], PRD 11.2

  - id: BR4.6
    statement: >
      Esta unidad **no importa** el segundo detector ni comparte reconocedores
      con él.
    category: constraint
    applies_to: El módulo entero
    trigger: La regla de importación
    logic: >
      SI los dos detectores compartieran mecanismo o biblioteca ENTONCES un error
      común los haría fallar a la vez, y el segundo dejaría de ser una
      comprobación independiente.
    violation: El contrato de importación falla
    source: AC4.14.1, ADR-013, C-13
```

## Resumen

Veintiocho reglas en cuatro grupos. **El grupo 1 es el que sostiene todo lo
demás**: si el punto único de salida no es obligatorio por construcción, los
otros tres grupos son buenas intenciones. De ahí que BR1.1 y BR1.2 no digan
"hay que acordarse de redactar" sino que el tipo que los puntos de salida exigen
solo lo fabrique el punto de redacción.

El grupo 2 es donde vive el trabajo de verdad: cuatro tipos, dos idiomas, tres
formas de escribir cada dato y un turno que mezcla los dos idiomas a propósito.
**BR2.3 es la única compuerta dura del grupo** y es la que más veces se rompe en
un detector real, porque casi todos se configuran por idioma y se prueban con
texto de un solo idioma.

El grupo 3 sale de la norma de legibilidad: lo que queda escrito lo lee una
persona, y tiene que entenderlo sin descifrar nada. El grupo 4 existe para que
la medición no mienta: **por idioma, por tipo, y con el respaldo contado
aparte**, que es la fila que avisa cuando un reconocedor se rompió.
