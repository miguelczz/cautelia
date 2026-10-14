# Diseño de seguridad — U3 `pii-redaction`

Cómo se construye cada uno de los quince controles. `security-requirements.md`
dice **qué** tiene que cumplirse y con qué comando se mide; aquí está **cómo**.

**Fuentes consumidas.** `../nfr-requirements/security-requirements.md` y
`../nfr-requirements/tech-stack-decisions.md`,
`../functional-design/functional-spec.md` y `../functional-design/rules.md`, y
`../../../inception/contract-design/contract-summary.md` (C-13).

## El principio que ordena todo lo demás

Esta unidad protege contra un fallo que **no se manifiesta**. Una redacción rota
no rompe ninguna pantalla, no levanta ninguna excepción y no hace fallar ninguna
prueba de funcionamiento: sigue saliendo texto, solo que con el dato dentro. Por
eso el diseño no se apoya en ningún sitio en que alguien se acuerde de algo, y
cada capa de abajo **le pregunta a una herramienta** en vez de confiar en lo que
un documento afirma.

Es la lección que este proyecto ya pagó una vez, en U1: dos ajustes de seguridad
estaban escritos en un archivo que el gestor no leía, el archivo se veía bien y
el control no existía.

## Cuatro capas

### Capa 1 — La frontera del tipo: que no se pueda escribir el error

Los seis puntos de salida exigen `Redacted`. Ningún otro módulo puede
fabricarlo. Pero el tipo solo **no** lo garantiza, y esto es lo que la revisión
del diseño funcional corrigió: `Redacted` es un `NewType`, que **se borra en
tiempo de ejecución**, así que `Redacted(texto_sin_tapar)` es una llamada legal
que el comprobador de tipos acepta sin queja.

La frontera son, entonces, dos piezas que trabajan juntas:

| Pieza | Qué aporta | Qué no aporta |
| --- | --- | --- |
| El tipo `Redacted` en las firmas | La **señal**: un punto de salida que acepte `str` se ve mal a simple vista, y el comprobador de tipos rechaza pasarle texto crudo | Nada en tiempo de ejecución |
| El chequeo `redaction:constructor` | El **control**: análisis del árbol sintáctico que falla si **el tipo se produce** fuera de `compliance/redaction/api.py` | Nada sobre módulos que ni siquiera importan el tipo — de eso se ocupa la capa 2 |

**"Producir el tipo" son tres formas, no una, y esto es una corrección de la
revisión.** Buscar solo la llamada `Redacted(...)` dejaba abierta la puerta de
al lado: como el tipo se borra en tiempo de ejecución, `cast(Redacted, texto)`
entrega un valor que el comprobador acepta sin invocar nunca el constructor. El
chequeo falla ante las tres:

| Forma | Qué haría |
| --- | --- |
| `Redacted(texto)` | Invocar el constructor |
| `cast(Redacted, texto)` | Afirmar el tipo sin construirlo |
| Una anotación `: Redacted` con `# type: ignore` al lado | Silenciar al comprobador para lo mismo |

Un control que solo cubre la forma obvia de saltárselo es un control que atrapa
los descuidos y no los atajos.

El mismo chequeo cubre `SEC-U3.7` y `SEC-U3.8`, porque busca también cualquier
estructura que relacione un hallazgo con su valor: un diccionario, un atributo
o un campo que guarde el texto de entrada. Si aparece una, falla nombrando el
archivo y la línea. **La irreversibilidad deja así de ser una promesa y pasa a
ser algo que una herramienta comprueba.**

### Capa 2 — El registro de puntos de salida: que no se pueda añadir un agujero

Los seis puntos de salida están declarados en un solo sitio, con su superficie y
su unidad dueña. El contrato de importación prohíbe que cualquier módulo fuera
de ese registro escriba hacia una de esas superficies.

Las dos pruebas que lo sostienen son las que le dan valor:

1. Una **planta un escritor** que no pasa por la redacción y exige que el
   contrato falle.
2. Otra comprueba que el árbol correcto pasa, **para que un fallo del andamiaje
   no se confunda con un contrato que funciona**.

Sin la primera, sería un contrato que nadie ha visto fallar nunca. Sin la
segunda, un error de configuración que hiciera fallar todo se leería como éxito.

### Capa 3 — El detector: que no se pueda evadir

| Control | Cómo se construye |
| --- | --- |
| `SEC-U3.4` | **Los dos juegos de reconocedores se cargan y corren siempre**, sea cual sea el idioma del turno. Es un motor de Presidio con los dos modelos residentes, no uno que se reconfigure por llamada: reconfigurarlo sería reintroducir la posibilidad de que corra uno solo |
| `SEC-U3.5` | Cada reconocedor propio declara sus formatos: compacto, con espacios, con guiones y dictado en palabras. Los cuatro son datos de configuración, no ramas de código |
| `SEC-U3.6` | La regla de respaldo corre **después** de los reconocedores y solo reclama lo que ninguno reclamó. Su lista de frases de contexto es configuración versionada por idioma, junto a los reconocedores |
| Solapes | Gana el hallazgo **más específico**; el respaldo nunca gana. Sin esta regla, una póliza dentro de una secuencia larga se etiquetaría como dato sin clasificar y la medición por tipo perdería un acierto real |

**Que los dos juegos corran siempre es el control, no una optimización
rechazada.** Cargar solo el juego del turno es la forma natural de escribirlo y
es exactamente lo que abre el agujero de RT-15: dictar el dato en el otro
idioma. Queda escrito aquí porque es el atajo que alguien tomará al optimizar.

### Capa 4 — La salida: que lo que queda escrito sea legible y medible

| Control | Cómo se construye |
| --- | --- |
| Etiquetas | Se escriben desde el catálogo de textos, en el idioma de la conversación, numeradas por tipo dentro del texto de la llamada. Se guardan **ya escritas**, para que un renglón de log se entienda fuera del aplicativo |
| `SEC-U3.9` | El campo `recognizer_id` de cada hallazgo lo transporta, y el informe agrupa dos veces sobre la misma lista de hallazgos: una por tipo y otra por identificador de reconocedor. Dos agrupaciones sobre la misma fuente, nunca dos recuentos independientes que puedan divergir |
| `SEC-U3.14` | El reporte no recibe los dos valores para compararlos: recibe el tipo de entidad, la longitud de cada uno y en qué posición difieren. La comparación la hace quien tiene los valores, y lo que cruza hacia el reporte es ya su resultado |
| `SEC-U3.13` | No hay camino distinto para datos sintéticos. **No existe la bandera "esto es de prueba"**, porque en el momento de escribir el sistema no puede saber si un número vino del corpus o lo escribió una persona |

## Fallar cerrado, que atraviesa las cuatro capas

`SEC-U3.10` no es una capa: es una propiedad de todas.

- Si los modelos no cargan al arrancar, **el proceso no arranca**. Un aplicativo
  vivo con la redacción muerta es peor que uno caído, porque parece que funciona.
- Si una llamada falla, `redact` **levanta el fallo** en vez de devolver texto.
  El punto de salida responde con la clave de degradación del catálogo, y queda
  un valor distinguible en el caso y un evento en la traza con la causa.
- No existe ninguna ruta en la que un fallo del detector produzca texto sin
  tapar. La prueba que lo comprueba rompe la carga a propósito y **exige
  silencio**.

## Los dos relojes, y por qué son dos

`SEC-U3.11` se comprueba con dos métodos distintos, y confundirlos fue un
hallazgo de la revisión de la etapa anterior:

| Qué se mide | Con qué | Por qué |
| --- | --- | --- |
| El coste de la pasada de redacción (NFR11.3, 100 ms) | El **reloj del sistema** alrededor de la llamada real | Es trabajo de cómputo real. Con el reloj simulado, una implementación que tarde medio segundo pasaría igual |
| Cuándo aparece el aviso de la consola (NFR11.4, 1 s) | El **reloj controlado** | Es lógica de temporización. Esperar un segundo de verdad en cada corrida es tiempo tirado |

## Dónde corre la redacción, que no es donde parecía

ADR-004 nombra la **redacción** por su nombre entre el trabajo de CPU que "va a
un hilo o a un pool, con semáforos por uso (voz, chat y fondo)". La primera
versión de este documento no lo decía en ninguna parte, y la revisión lo
encontró: medir el coste de la pasada no es lo mismo que decir dónde se ejecuta.

**Rige lo que ADR-004 ya había decidido**, escrito aquí porque el Flujo 2 es
exactamente su caso: redactar un fragmento parcial ocurre mientras la persona
está hablando, dentro del turno de voz.

- La llamada a `redact()` **no corre en el bucle de eventos**: va a un hilo del
  pool, y el camino del turno la espera de forma asíncrona.
- El pool tiene **semáforo por uso** —voz, chat y fondo—, de modo que una
  corrida de evaluaciones en segundo plano no puede quedarse con los hilos que
  necesita una llamada en curso.
- Por eso el presupuesto de NFR11.3 son 100 ms **de la pasada**, no del turno:
  lo que el turno no puede permitirse es quedarse bloqueado, y eso lo resuelve
  el pool. Los 100 ms son para que el texto no se acumule más rápido de lo que
  se procesa.

## La frontera con U21

El segundo detector es de U21 y **no importa este módulo**: si compartieran
mecanismo o biblioteca, un mismo error los tumbaría a la vez y el segundo
dejaría de comprobar nada. Lo hace cumplir un contrato de importación
(`SEC-U3.15`).

Lo que U3 le entrega a U21 no es una interfaz, es **un archivo**: la
configuración de reconocedores en
`app/backend/src/untangle/compliance/redaction/recognizers/<idioma>.yaml`, donde
cada entrada declara su mecanismo. Eso permite a U21 comprobar `AC4.14.1` —que
los dos detectores no comparten mecanismo— sin importar nada de aquí.

## Decisiones de esta etapa

| # | Decisión | Por qué |
| --- | --- | --- |
| NFRD-U3-1 | Un motor con los dos modelos residentes, no uno que se reconfigure por llamada | Reconfigurarlo reintroduce la posibilidad de que corra un solo juego, que es el agujero de RT-15. Cuesta **636 MB residentes** --no los 71 MB que esta fila decia, que eran el tamano de las ruedas en disco-- y ahorra la carga en cada llamada |
| NFRD-U3-2 | Si los modelos no cargan, el proceso no arranca | Un aplicativo vivo con la redacción muerta parece que funciona, y ese es el peor estado posible para un control silencioso |
| NFRD-U3-3 | El chequeo del constructor cubre también la ausencia de bóveda | Son la misma búsqueda sobre el árbol sintáctico: quién construye el tipo, y quién guarda un valor junto a su etiqueta. Un solo chequeo con dos reglas es más barato de mantener que dos |
| NFRD-U3-4 | Las frases de contexto del respaldo viven junto a los reconocedores, no en el catálogo de textos | El catálogo es para lo que lee una persona, y estas son patrones de detección. Meterlas ahí las sometería al chequeo de paridad, que mide otra cosa |
| NFRD-U3-6 | La redacción del parcial corre en el pool de hilos con semáforo por uso | ADR-004 lo decidió y este documento no lo decía. Medir el coste de la pasada no dice dónde se ejecuta, y en el turno de voz esa diferencia es la que bloquea o no el bucle de eventos |
| NFRD-U3-7 | El chequeo del tipo cubre constructor, `cast` y `type: ignore` | Como el tipo se borra en tiempo de ejecución, `cast` entrega un `Redacted` sin construirlo. Un control que solo cubre la forma obvia atrapa descuidos, no atajos |
| NFRD-U3-5 | No existe bandera de "dato de prueba" | En el momento de escribir, el sistema no puede distinguir un número del corpus de uno que escribió alguien. Una excepción para datos de prueba es una excepción que alguien aplicará a datos que no lo son |
