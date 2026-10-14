# Reglas de negocio — U7 `synthetic-data`

Son 30 reglas en ocho familias:
- determinismo;
- redacción y revisión;
- estructura del corpus;
- Knotwell;
- texto propio;
- casos sembrados;
- datos personales ficticios;
- fronteras.

## Reglas

El bloque siguiente es la fuente de verdad; la tabla resumen se deriva de él.

```yaml
rules:

  - id: BR1.1
    statement: Con la misma semilla y los mismos textos fuente, el generador produce archivos idénticos byte a byte.
    category: constraint
    applies_to: "Comando de generar y todo lo que escribe bajo app/data/"
    trigger: "En cada generación."
    logic: "SI la semilla y los hashes de entrada coinciden ENTONCES cada archivo de salida coincide byte a byte. Para lograrlo, el JSON se escribe con claves ordenadas, UTF-8, saltos LF, sangría fija y sin nada que dependa del reloj, del sistema de archivos o del orden de un conjunto."
    violation: "La prueba que genera dos veces en directorios distintos y compara byte a byte falla."
    source: AC5.3.1, FR11.2

  - id: BR1.2
    statement: El azar solo sale de la semilla, derivada por salida.
    category: constraint
    applies_to: "Toda elección aleatoria del generador"
    trigger: "Cada vez que el generador elige."
    logic: "El generador de números de cada salida se siembra con el hash de la semilla más la ruta de esa salida. Así, añadir un archivo nuevo no cambia los demás."
    violation: "La prueba que añade una salida y comprueba que las otras no cambian falla."
    source: AC5.3.1, FR11.2

  - id: BR1.3
    statement: Un solo comando regenera todo el conjunto, y nada lo regenera sin ese comando.
    category: policy
    applies_to: "Tarea nueva mise run synthetic:generate, que se crea con la generación de código"
    trigger: "Solo cuando alguien corre el comando."
    logic: "El comando produce formularios, endosos, distractores, jurisdicción, pólizas emitidas con personas y vehículos, casos sembrados y DS-8, para las tres aseguradoras. Importar el paquete, arrancar el servidor o correr las pruebas no escribe en app/data/."
    violation: "La prueba de la lista de salidas falla, o una prueba detecta escritura en app/data/ fuera del comando."
    source: AC5.3.2, FR12.1

  - id: BR1.4
    statement: El manifiesto registra semilla, versión del generador y el hash de cada entrada y de cada salida.
    category: validation
    applies_to: "GenerationManifest"
    trigger: "Al terminar cada generación, y en schema:check."
    logic: "SI un archivo de app/data/ no está en el manifiesto, o su hash no coincide ENTONCES la validación falla nombrando el archivo."
    violation: "schema:check falla; U8 se niega a ingerir un corpus que no casa con su manifiesto (C-26)."
    source: AC5.3.1, C-26

  - id: BR1.5
    statement: Generar no llama a ningún modelo ni necesita ninguna clave.
    category: constraint
    applies_to: "Comando de generar"
    trigger: "Siempre."
    logic: "El generador solo lee SourceText revisados y configuración versionada. El paquete de composición no importa providers."
    violation: "La prueba que genera con el entorno vacío y un espía en la fábrica de proveedores falla; el contrato de importación falla."
    source: AC5.3.3

  - id: BR2.1
    statement: La redacción con el modelo es un comando aparte cuya salida es un borrador que el generador no lee.
    category: policy
    applies_to: "Tarea nueva mise run synthetic:draft, que se crea con la generación de código"
    trigger: "Solo por comando, una vez por parte, aseguradora e idioma."
    logic: "El comando pide el texto a Gemini con la clave del uso operations, pasando por la fábrica, el techo y el registro de gasto de U5, y escribe en tmp/synthetic-drafts/, que git ignora. El generador no tiene ninguna ruta hacia esa carpeta."
    violation: "La prueba que planta un borrador y genera comprueba que la salida no cambia; si cambia, falla."
    source: AC5.3.4, ADR-016, Q1

  - id: BR2.2
    statement: Un texto fuente sin marca de revisión no entra al corpus.
    category: validation
    applies_to: "SourceText"
    trigger: "Al generar."
    logic: "SI un SourceText no tiene reviewed_at, reviewed_by o drafted_with ENTONCES el generador se detiene nombrando el archivo y la clave."
    violation: "El comando termina con error y no escribe nada."
    source: AC5.3.4, ADR-016

  - id: BR2.3
    statement: El prompt de redacción lleva la estructura de referencia y la prohibición de copiar texto de terceros, y nunca un texto de tercero.
    category: constraint
    applies_to: "Comando de redacción"
    trigger: "En cada llamada."
    logic: "El prompt se arma desde la referencia de estructura y una plantilla versionada. Ningún archivo de tmp/specimens/ es legible para el comando de redacción."
    violation: "La prueba del armado del prompt falla si aparece contenido de specimens."
    source: FR12.2, P8

  - id: BR3.1
    statement: Cada formulario base de una emisora tiene todas las partes de la póliza de auto personal de la referencia, con sus numerales.
    category: validation
    applies_to: "STO-PAP-2026 y SUN-PAP-2026"
    trigger: "Al generar y en schema:check."
    logic: "El formulario tiene acuerdo, definiciones y las partes A a F de docs/reference/estructura-poliza-iso-pap.md, cada una con al menos una cláusula, y la referencia al documento de jurisdicción de Corvane."
    violation: "La validación nombra la parte que falta."
    source: AC5.4.1, AC5.5.1, FR5.1

  - id: BR3.2
    statement: Cada cláusula tiene identificador único y versión; el identificador es el del formulario más la numeración estructural.
    category: validation
    applies_to: "ClauseRecord"
    trigger: "Al generar."
    logic: "clause_id = <form_id>-<clause_key>, único dentro del espacio de la aseguradora; form_version con forma AAAA.n."
    violation: "El generador se detiene nombrando el identificador repetido o sin versión."
    source: AC5.4.2, AC5.5.2, FR5.2

  - id: BR3.3
    statement: Cada emisora tiene al menos cuatro endosos; se construyen cinco.
    category: validation
    applies_to: "Endosos de Stonecroft y de Sunmeadow"
    trigger: "Al generar."
    logic: "SI una emisora tiene menos de cuatro endosos ENTONCES la validación falla. Sunmeadow incluye el que amplía la cobertura de transporte; Stonecroft no lo tiene, a propósito."
    violation: "La validación nombra la emisora."
    source: AC5.4.1, AC5.5.1, Q2

  - id: BR3.4
    statement: Cada emisora tiene distractores declarados, cada uno ligado a la cláusula con la que se confunde.
    category: validation
    applies_to: "SourceText de tipo distractor y ClauseRecord con is_distractor"
    trigger: "Al generar."
    logic: "Cada distractor lleva distractor_of y distractor_reason (superseded_version o near_duplicate); se construyen ocho por emisora. Una versión anterior queda indexable pero no vigente en ninguna póliza emitida."
    violation: "La validación nombra el distractor sin destino o el destino inexistente."
    source: AC5.4.1, AC5.5.1, Q2

  - id: BR3.5
    statement: Las relaciones entre cláusulas apuntan a cláusulas que existen en el mismo espacio.
    category: validation
    applies_to: "clause_relations.json"
    trigger: "Al generar."
    logic: "Cada relación es endorsement_modifies, defines o refers_to, y sus dos extremos existen en el espacio de esa aseguradora."
    violation: "La validación nombra la relación rota."
    source: ADR-010, C-26

  - id: BR3.6
    statement: Una póliza emitida referencia formulario, versión y endosos vigentes, y usa la forma única de número.
    category: validation
    applies_to: "IssuedPolicyRecord"
    trigger: "Al generar y en schema:check."
    logic: "SI falta form_version, un endoso no existe o el número no es POL- con seis dígitos ENTONCES la póliza no valida. Cada ejemplo de tenant.yaml (example_policy) existe como póliza emitida de esa aseguradora."
    violation: "La validación nombra la póliza y el campo."
    source: AC5.4.2, AC5.5.2, FR5.2, C-25

  - id: BR3.7
    statement: El manifiesto declara las diferencias puestas a propósito entre emisoras.
    category: validation
    applies_to: "GenerationManifest.declared_differences"
    trigger: "Al generar."
    logic: "Cada diferencia nombra dónde está y dónde falta, y lo declarado coincide con el corpus: el endoso de transporte está en Sunmeadow y no en Stonecroft."
    violation: "La prueba que contrasta la declaración con el corpus falla."
    source: AC5.4.3

  - id: BR4.1
    statement: Knotwell guarda en su propio espacio los formularios y endosos de sus dos emisoras, con los mismos identificadores, versiones y textos.
    category: constraint
    applies_to: "app/data/tenants/knotwell/"
    trigger: "Al generar."
    logic: "Knotwell recibe una copia de cada formulario, endoso y distractor de Stonecroft y de Sunmeadow, etiquetada con la emisora."
    violation: "La validación nombra la pieza que falta en Knotwell."
    source: AC5.5.3, ADR-010

  - id: BR4.2
    statement: Las copias de Knotwell salen del original en la misma generación y nunca de un texto propio.
    category: constraint
    applies_to: "Copias de Knotwell"
    trigger: "Al generar y en schema:check."
    logic: "El generador copia desde el SourceText de la emisora; SI una copia difiere de su original ENTONCES la validación falla."
    violation: "schema:check falla nombrando la copia desalineada."
    source: AC5.5.4

  - id: BR4.3
    statement: Cada póliza de un cliente de Knotwell declara qué aseguradora la emitió.
    category: validation
    applies_to: "IssuedPolicyRecord de Knotwell"
    trigger: "Al generar."
    logic: "issuer_tenant es stonecroft o sunmeadow, y form_id pertenece a esa emisora."
    violation: "La validación nombra la póliza."
    source: AC5.5.3

  - id: BR5.1
    statement: Las huellas de los formularios de terceros se guardan solo como hashes; el texto nunca entra al repositorio.
    category: constraint
    applies_to: "Tarea nueva mise run synthetic:fingerprints y FingerprintSet"
    trigger: "Por comando, cuando Miguel deja los specimens en tmp/specimens/."
    logic: "El comando normaliza el texto (minúsculas, sin puntuación, espacios colapsados), quita los encabezados y la numeración de la referencia, corta secuencias de ocho palabras y guarda solo su SHA-256, con la edición, el publicador, la fecha y el hash del archivo de origen."
    violation: "La prueba comprueba que el archivo de huellas no contiene ninguna secuencia legible; el escaneo de secretos y el chequeo de contenido corren sobre él."
    source: AC5.4.4, AC5.5.5, Q3

  - id: BR5.2
    statement: Ninguna cláusula del corpus comparte una sola secuencia de ocho palabras con los formularios de terceros.
    category: validation
    applies_to: "content:check sobre app/data/tenants/"
    trigger: "En cada corrida del guion de verificación."
    logic: "Se normaliza cada cláusula como las huellas, sin encabezados ni numeración, y se buscan sus hashes. El umbral es cero: una coincidencia falla y nombra la cláusula."
    violation: "Compuerta dura: el guion de verificación falla."
    source: AC5.4.4, AC5.5.5, FR12.2

  - id: BR5.3
    statement: Sin archivo de huellas, el chequeo de texto propio no pasa.
    category: policy
    applies_to: "content:check"
    trigger: "Cuando el corpus existe y el archivo de huellas no, o está vacío."
    logic: "El chequeo se declara 'no medido' y falla; nunca se omite en silencio."
    violation: "El guion de verificación falla con el motivo."
    source: AC5.4.4, team.md (una compuerta que no se pudo ejecutar se declara no medida)

  - id: BR5.4
    statement: La muestra humana son diez cláusulas por emisora elegidas con una semilla registrada, y su revisión queda con fecha y commit.
    category: policy
    applies_to: "ReviewSample"
    trigger: "Una vez por emisora, después de la primera generación."
    logic: "Un comando elige diez cláusulas no distractoras con la semilla y escribe la muestra; Miguel anota el veredicto, y el generador copia al manifiesto la fecha, el commit y el veredicto."
    violation: "Sin veredicto own_text_structure_ok de Miguel, el criterio humano queda abierto y se reporta así."
    source: AC5.4.5, AC5.5.6

  - id: BR6.1
    statement: Hay al menos un caso sembrado en cada estado, en cada aseguradora y en cada idioma, y uno cerrado con cada resolución.
    category: validation
    applies_to: "SeededCaseRecord"
    trigger: "Al generar."
    logic: "Siete estados por tres aseguradoras por dos idiomas, más un cerrado con registered, approved, rejected y sent_to_insurer; sent_to_insurer solo en Knotwell, porque es lo que hace una agencia (D18)."
    violation: "La validación nombra la combinación que falta."
    source: AC5.6.1

  - id: BR6.2
    statement: Cada caso sembrado tiene identificador estable y nombra los criterios que parten de él.
    category: validation
    applies_to: "SeededCaseRecord.used_by"
    trigger: "Al generar."
    logic: "El case_key no cambia entre generaciones. Un caso que describe un criterio, como el derivado por solicitud de persona con completitud 3/7, lista ese criterio en used_by."
    violation: "La validación nombra el criterio sin caso."
    source: AC5.6.2

  - id: BR6.3
    statement: Los casos sembrados se cargan por la API pública de U4 con origen generator.
    category: policy
    applies_to: "Tarea nueva mise run synthetic:seed, con su código en untangle.server y no en synthetic_data (FD-U7-9)"
    trigger: "Por comando, o desde la fixture de una prueba."
    logic: "El comando lee los archivos de cases/ y crea cada caso con create_case y las transiciones de U4, nunca con SQL directo. El origen generator es el que el borrado de datos de visitantes no toca (la regla de U4 que decide qué borra el reinicio)."
    violation: "El contrato de importación falla si synthetic_data abre una sesión fuera de la API de U4."
    source: AC5.6.4, Q4

  - id: BR6.4
    statement: Dos pruebas que parten del mismo caso sembrado no se ven.
    category: constraint
    applies_to: "Fixture de pruebas que siembra"
    trigger: "En cada prueba."
    logic: "La fixture carga el caso dentro de la transacción de la prueba y la revierte al terminar."
    violation: "La prueba que corre dos pruebas en paralelo sobre el mismo caso y compara falla."
    source: AC5.6.3

  - id: BR7.1
    statement: Todo dato con forma de dato personal es ficticio y reconocible como tal.
    category: constraint
    applies_to: "PersonaRef, VehicleRef, pólizas y casos"
    trigger: "Al generar."
    logic: "Teléfonos del rango 555-01XX, correos de example.com o example.org, VIN que falla su dígito de control, y nombres, placas y cédulas compuestos desde la semilla y nunca desde un registro."
    violation: "La validación nombra el valor fuera de rango."
    source: FR12.3, ADR-016, P8

  - id: BR7.2
    statement: Los valores personales ficticios se exportan para los canarios y la redacción los encuentra.
    category: policy
    applies_to: "app/data/personal_values.json, una salida más con su hash en el manifiesto (FD-U7-8)"
    trigger: "Al generar."
    logic: "El generador publica la lista de valores sembrados por tipo e idioma. Una prueba pasa cada valor por la redacción de U3 y exige que lo encuentre."
    violation: "La prueba nombra el valor que la redacción no encuentra."
    source: FR12.3, ADR-013

  - id: BR7.3
    statement: El generador regenera DS-8 con la misma semilla y los mismos identificadores que la versión escrita a mano en U2.
    category: constraint
    applies_to: "app/data/fixtures/ds8_isolation.json"
    trigger: "Al generar."
    logic: "El contenido del archivo es el contrato; el generador lo produce con generated true y el resto igual. Las pruebas de aislamiento de U2 no cambian."
    violation: "La prueba compara las filas y las colisiones con las de U2 y falla si difieren."
    source: DS-8, AC4.11.3

  - id: BR8.1
    statement: El corredor de evaluaciones lee los datos versionados y nunca invoca el generador.
    category: constraint
    applies_to: "evals y synthetic_data"
    trigger: "En cada corrida del guion de verificación."
    logic: "Un contrato de importación prohíbe que evals importe synthetic_data."
    violation: "El paso de reglas de importación falla."
    source: AC5.3.5
```

## Resumen

| ID | Regla |
| --- | --- |
| BR1.1 | Misma semilla y mismas fuentes, mismos bytes |
| BR1.2 | Azar sembrado por salida |
| BR1.3 | Un comando regenera todo; nada más lo hace |
| BR1.4 | Manifiesto con hashes de entradas y salidas |
| BR1.5 | Generar sin modelo ni claves |
| BR2.1 | Redacción aparte, a borrador no versionado |
| BR2.2 | Sin marca de revisión, no entra |
| BR2.3 | El prompt nunca lleva texto de terceros |
| BR3.1 | Todas las partes de la referencia |
| BR3.2 | Identificador único y versión por cláusula |
| BR3.3 | Al menos cuatro endosos; cinco construidos |
| BR3.4 | Distractores declarados y ligados |
| BR3.5 | Relaciones con extremos que existen |
| BR3.6 | Póliza con formulario, versión, endosos y número único |
| BR3.7 | Diferencias declaradas y comprobadas |
| BR4.1 | Knotwell con las piezas de sus dos emisoras |
| BR4.2 | Copias desde el original, en la misma generación |
| BR4.3 | Cada póliza de Knotwell dice su emisora |
| BR5.1 | Huellas solo como hashes |
| BR5.2 | Cero secuencias compartidas |
| BR5.3 | Sin huellas, no medido y falla |
| BR5.4 | Muestra de diez con semilla, fecha y commit |
| BR6.1 | Cada estado, aseguradora e idioma, y cada resolución |
| BR6.2 | Casos con identificador estable y sus criterios |
| BR6.3 | Carga por la API de U4 con origen generator |
| BR6.4 | Pruebas aisladas por transacción |
| BR7.1 | Datos personales ficticios y reconocibles |
| BR7.2 | Valores exportados a los canarios y redactables |
| BR7.3 | DS-8 regenerado igual |
| BR8.1 | El corredor nunca invoca el generador |
