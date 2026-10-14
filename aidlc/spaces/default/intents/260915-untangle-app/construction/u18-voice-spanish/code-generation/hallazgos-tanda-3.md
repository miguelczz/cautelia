# Revisión de la tanda 3 — U18 `voice-spanish`

"La paridad, que son pruebas". Y lo fue: **casi no escribió código de producción**
y encontró el defecto más visible que ha tenido el español en este proyecto.

94 pruebas en `mise run test:u18`, 2.069 unitarias en verde, 373 de integración
sobre las cinco unidades que este cambio alcanza, y las nueve compuertas baratas.

## 1. La redacción estaba mutilando las frases de la propia agente

Lo encontró la primera prueba de paridad que miró la apertura en español. Salía así:

> *"Le habla Catalina... **[NOMBRE 1]** ayudarle a reportar un siniestro"*

La palabra tachada es **"Puedo"**. El detector de nombres en español etiqueta como
persona el verbo con que arranca la frase, y la guardia de salida le pasaba el
detector a **todo** lo que llega al asegurado, incluido el texto del propio
catálogo.

Medido sobre las 131 frases de voz y chat del catálogo:

| | frases que el detector altera |
| --- | --- |
| español | **7 de 131** |
| inglés | 0 de 131 |

Las que de verdad se oían mal en producción: la apertura, la respuesta de
cobertura (*"**Encontré** la cláusula dentro de..."* → *"[LUGAR 1] la cláusula"*) y
la frase del monto diferido. Las otras cuatro son etiquetas de la interfaz, que se
resuelven en el navegador y nunca pasan por el detector: **mi primera medición las
contó igual, y eso era medir de más**. La cifra honesta de lo que se oía roto es
tres.

### La decisión, y de quién fue

Se llevó a Miguel porque acota una regla que dice "siempre" —hacer pasar por la
guardia de salida todo texto que llegue al asegurado— y porque cambia lo que oye
quien prueba el producto. Eligió **acotar el catálogo** sobre la alternativa, una
lista de palabras permitidas que habría arreglado estas siete y se habría roto con
la frase número ocho.

**La regla que queda:** una frase del catálogo no pasa por el detector de datos
personales; lo que se **mete** en ella, sí. La guardia de salida sigue siendo el
único punto de salida: lo que cambia es qué se le hace al texto, no por dónde sale.

### Por qué el texto que llega por ese camino es de verdad del catálogo

No lo garantiza el tipo ni el módulo: lo garantiza **otra compuerta que ya
existía**. `copy:check` falla ante cualquier frase visible escrita en línea, así
que un módulo no tiene de dónde sacar una frase que no sea del catálogo. Lo que
ninguna máquina cierra es que alguien pase por ahí una variable con texto de
fuera; eso lo cierra la revisión, y es la razón por la que los huecos existen.

### El origen del texto es un dato y no una adivinanza

La primera versión dedujo la procedencia de si el evento traía clave del catálogo.
Funcionaba para tres de los cinco eventos de C-14 y **fallaba justo en el que
importa**: `FinalText`, que es por donde llegan la respuesta de cobertura y la
pregunta del nodo de captura, y que no lleva clave porque se compone de varias
frases.

Así que `FinalText` gana un campo aditivo, `from_catalog`, que llega en `False` por
omisión: una rama nueva que lo olvide tapa de más —se ve— en vez de tapar de menos.

## 2. Lo que se rompió, y qué se cayó

Seis roturas, seis conductas caídas. **Una no tumbó nada a la primera**, y es la
que más valía la pena.

| Regla | Qué se rompió | Qué se cayó |
| --- | --- | --- |
| Catálogo sin detector | La frase vuelve a pasar por el detector | `test_la_apertura_en_espanol_no_sale_mutilada_por_la_redaccion` |
| Lo de fuera se tapa | El texto del modelo deja de taparse | `test_lo_que_escribe_un_modelo_si_se_tapa` |
| Los huecos se tapan | El valor entra sin pasar por el detector | 2, entre ellas la de fallar cerrado |
| Origen declarado | La cobertura deja de declararlo | **0 a la primera** → ahora `test_br4_2...` |
| Origen declarado | La captura deja de declararlo | **0 a la primera** → ahora `test_un_turno_normal...` |
| BR4.4 | (ya cubierta en la tanda 2) | — |

**Las dos que no tumbaban nada** son la forma de defecto más repetida de este
proyecto: el mecanismo estaba puesto y ninguna prueba lo nombraba. Quitar
`from_catalog=True` de la respuesta de cobertura dejaba las 469 pruebas en verde y
el español volvía a salir con una palabra tachada. Ahora lo nombran dos
aserciones, cada una en la prueba de su conducta, con la razón escrita al lado.

## 3. La paridad en español: 14 pruebas y ningún `if` por idioma

El recorrido armado, que hasta ahora solo corría en inglés: la apertura con su
divulgación, el turno marcado en español al llegar al grafo, la frase de espera, la
placa leída de vuelta con la tabla española, la escalera de tres, los tres
silencios, la oferta de retomar, el cierre con su número dígito a dígito y la
interrupción por el ciclo completo.

Dos hallazgos menores de las propias pruebas, los dos por mirar la palabra del
idioma equivocado:

- **`transcrib` no está en español**: la palabra es "transcrita". La prueba de la
  divulgación buscaba el tallo inglés y fallaba como si faltara la divulgación.
- **La tabla de deletreo española no es la de la OTAN traducida**: dice "a de
  ábaco", no "alfa". Ninguna prueba lo habría dicho, porque en U16 no existía.

Y **BR5.2 se comprueba sobre los archivos de la unidad**: ninguna comparación con
un idioma literal en el código de producción de U18. Pasar el idioma por argumento
es lo que hace que no haya ramas, y esa prueba es la que avisa el día que aparezca
una.

## 4. El idioma de arranque: la consola puede decir "nadie eligió"

`language` pasa a ser opcional en el cuerpo de abrir la llamada (BR1.1, D5), y su
ausencia significa algo: manda el idioma de la aseguradora. La consola lo omite
cuando la procedencia del selector es `tenant_default`, porque mandar el idioma que
la pestaña adoptó por su cuenta sería indistinguible de una elección.

Es un cambio aditivo del contrato —un campo obligatorio pasa a opcional— así que la
API no cambia de versión.

**Dos campos dicen lo mismo y hoy coinciden:** `default_language` de la aseguradora
y `voice.language_default` de su bloque de voz. La voz usa el primero, igual que el
chat, para que los dos canales no puedan discrepar sobre la misma aseguradora.

## 5. El chequeo del registro del usted

La mitad de AC1.28.3 que se puede comprobar por código: ninguna forma de tuteo y
"pues" como mucho una vez por frase, con cinco reglas de identificador estable
(pronombres, verbos, imperativos, enclíticos y **subjuntivos**).

**El alcance es `surface: voice`, y eso es una decisión con su razón escrita:** la
landing y la interfaz hablan de tú a propósito —"Reporta un accidente", "Tu
mensaje"— y ese es otro registro, decidido en el diseño del producto. Meterlos aquí
obligaría a cambiar la voz del producto para que pase un chequeo de la voz de la
agente.

Dos cosas que este chequeo **no** cubre, dichas para que nadie las suponga:

- **Lo que el modelo escribe libremente en una corrida.** El reporte de la corrida
  no guarda los turnos, solo el enlace a su traza, así que no hay nada que
  recorrer. Esa mitad es del juez por D8. Si el reporte gana los turnos, se
  recorren aquí.
- **La calidez del usted y el registro paisa ligero**, que es del juez y se reporta
  "no medida" si se descalibra.

El quinto patrón —los subjuntivos— nació de una rotura: "cuando quieras" al lado de
un usted suena natural y es el desliz más fácil de colar. Y su primera versión
tenía las llaves **dobles** por un escape del guion que lo escribió, así que no
podía casar con nada: un patrón que nunca coincide pasa en verde para siempre. Lo
atrapó el paso de romper y correr.

## 6. Lo que no se debilitó

- Ningún umbral, ningún piso de cobertura, ninguna compuerta dura.
- La guardia de salida sigue siendo el único punto de salida, y el chequeo
  `redaction:constructor` sigue viendo un solo productor del tipo.
- Lo que escribe un modelo, lo que dice el asegurado y lo que vuelve del corpus se
  siguen tapando enteros, y hay una prueba por cada uno.
- Las dos pruebas de U12 que se tocaron **ganaron** una aserción; ninguna se
  relajó.
- `mise run contracts:gen` se corrió y su salida entra en el commit.
