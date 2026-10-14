# Prompts versionados

Un archivo por **nodo** y por **idioma**. El nombre es el contrato:

```
<prompt_id>.<locale>.md      p. ej.  intake.es.md, intake.en.md
```

`prompt_id` usa la misma grafía que el nodo del grafo (`intake`,
`policy_verification`, `decision`, `compliance`), igual que el directorio del
módulo, el enum de transición, el nombre del tramo en la traza y la etiqueta por
nodo del reporte de evaluaciones. `locale` es `es` o `en`.

## Qué contiene un archivo

El texto de la **instrucción de sistema**, y nada más. Sin huecos, sin
variables, sin plantilla: lo que el modelo necesite saber del caso entra por la
otra posición de la petición, la de **contenido**, que es donde va todo el texto
de origen externo (`SEC-U5.16`). Un prompt con huecos que se rellenan en tiempo
de ejecución es justo el punto donde se cuela una instrucción ajena.

Una variante es **otro archivo** con su propio identificador, no una rama dentro
de uno existente: así el cambio se ve en un diff y el hash lo distingue.

## Su hash

`untangle.providers.prompts.load_system_instruction` calcula el SHA-256 de los
bytes del archivo y lo devuelve dentro de `PromptRef`. Ese hash viaja en la
traza (`untangle.prompt_hash`) y en el registro de la corrida de evaluaciones.
**Editar un archivo de esta carpeta es un cambio de código**: mueve el hash,
dispara la compuerta de evaluaciones y se anota en el diff contra la línea base.

## Los prompts del chat y la llamada

`conversation` no es de un nodo: es la instrucción de **la llamada que entiende y contesta**
en cada turno, la misma en el chat y en la llamada de voz (2026-10-12). El modelo recibe, como
datos delimitados, la conversación y el estado del caso, y devuelve un formulario cerrado: qué
quiere la persona, los datos que dio, y lo que le responde. El código valida todo lo que ese
formulario propone y la guardia de salida revisa la respuesta antes de que llegue.

Reemplazó a dos instrucciones que se retiraron: `intake_understanding` (entender un mensaje
sin ver la conversación) e `intake_reply` (reescribir con otras palabras una frase del
catálogo). Las etiquetas del contenido que `conversation` nombra viven en
`server/composition.py` (`_ETIQUETAS_DE_COMPRENSION`), y una prueba comprueba que las dos
coincidan.

## Quién escribe los archivos

Las unidades que tienen nodos: U11 `intake-capture` y U12 `graph-runtime`. U5
`provider-platform` fija el formato, la ruta y el cálculo del hash — no inventa
el contenido de un prompt que todavía no tiene dueño, que por eso hoy esta
carpeta solo trae este archivo.
