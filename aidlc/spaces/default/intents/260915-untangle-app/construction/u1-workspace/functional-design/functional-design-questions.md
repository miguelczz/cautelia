# Preguntas — Diseño funcional de U1 `workspace`

Primera unidad: la base del repositorio, el catálogo de textos y el corredor de
evaluaciones. Este documento diseña **qué hace**, no cómo se programa: entidades,
reglas de negocio y comportamiento. El código llega dos etapas más adelante.

**Fuentes consumidas.** `../../../inception/units-generation/unit-of-work.md`
(qué contiene y qué no contiene U1),
`../../../inception/units-generation/unit-of-work-story-map.md` (sus tres
historias: US4.4, US5.8 y US4.7),
`../../../inception/requirements-analysis/requirements.md` (FR11.1, FR11.3,
NFR17 y NFR21), `../../../inception/domain-design/components.md` (las entidades
`CopyEntry`, `GoldenCase`, `EvalRun` y `CaseResult`) y
`../../../inception/contract-design/contract-summary.md` (los contratos C-21
catálogo de textos, C-22 registro de objetivos y conductores, y C-27 casos de
golden set y líneas base).

Casi todo lo fijan documentos aprobados y lo aplico sin preguntar: los formatos
de archivo (YAML para los casos, JSON para líneas base y reporte), el registro de
objetivos y conductores, la regla de que el corredor no llama al modelo, y que el
código de producción nunca importa el módulo de evaluaciones.

Quedan **cinco decisiones de comportamiento** que ningún documento aprobado
resuelve y que cambian lo que se construye.

## Q1 — Cómo sabe el respondedor simulado qué campo le están preguntando

El criterio AC4.7.1 dice que, si la agente pregunta los campos **en un orden
distinto al del guion**, el respondedor tiene que entregar la respuesta del campo
preguntado. Y AC4.7.5 prohíbe que un modelo participe. Así que hace falta una
forma determinista de emparejar "¿en qué dirección ocurrió?" con el campo
`incident.location`.

A. **El turno del sistema declara qué campo pide** (recomendada): el nodo de
   captura ya sabe qué campo está preguntando, así que lo expone como un dato del
   turno y el respondedor lo lee. Cero adivinación, cero mantenimiento; a cambio,
   el conductor de evaluaciones lee un dato que la persona real no ve
B. **Palabras clave por campo en el archivo del caso**: cada campo trae una lista
   de disparadores ("dirección", "dónde", "lugar") y el respondedor empareja por
   texto. No depende del sistema, pero cada cambio de redacción de una pregunta
   puede romper casos, y eso se confunde con una regresión real
C. **Orden fijo**: el respondedor entrega las respuestas en el orden del guion,
   sin emparejar. Es lo más simple y contradice el criterio, que existe
   justamente porque el orden cambia
X. Other (please specify)

[Answer]: A

## Q2 — Qué forma tiene el "subconjunto declarado" de la corrida

AC4.4.4 pide que correr el subconjunto dos veces sobre el mismo commit ejecute
exactamente los mismos casos, y que el reporte diga que es un subconjunto y cuál.
Falta decidir cómo se declara.

A. **Un archivo versionado con la lista de identificadores** (recomendada):
   `DS-2/es/017`, uno por línea, con un nombre por subconjunto (`smoke`,
   `gate`). Reproducible por construcción: la lista es el commit. El costo es
   mantenerla a mano cuando se agregan casos
B. **Un selector por ejes** (idioma, dataset, etiqueta): más corto de escribir y
   se actualiza solo cuando se agregan casos, pero dos corridas del mismo commit
   solo son iguales si nadie tocó los casos, y eso es exactamente lo que el
   criterio quiere garantizar
C. **Un porcentaje o un tope de casos**: el más simple y el que rompe la
   reproducibilidad, porque la selección depende del orden
X. Other (please specify)

[Answer]: A

## Q3 — Cómo se nombran las claves del catálogo y cómo se detecta una clave sin uso

AC5.8.1 pide que ninguna clave carezca de consumidor en el código. Para poder
comprobarlo, las claves tienen que ser rastreables.

A. **Claves jerárquicas con punto y siempre literales** (recomendada):
   `voice.opening.disclosure`, `inbox.action.approve`. Nunca se construye una
   clave concatenando en tiempo de ejecución, así que un chequeo puede buscar
   cada clave por texto y decir cuál no aparece. En la interfaz, el módulo
   generado hace que una clave inexistente sea un error de tipos
B. **Claves jerárquicas pero con familias construidas en ejecución** (por
   ejemplo `error.<code>`): menos repetición en el código, a cambio de que el
   chequeo de claves sin consumidor deje de ser exacto y haya que mantener una
   lista de excepciones
C. **Claves planas** (`voice_opening_disclosure`): igual de comprobables y más
   difíciles de agrupar por superficie cuando el catálogo crezca
X. Other (please specify)

[Answer]: A

## Q4 — Qué guarda la versión de una frase y cómo se registra la que cambió

La entidad del catálogo tiene un atributo `version`, y AC5.8.3 pide que una frase
que difiere de la guía de voz **nombre la decisión que la cambió** y aparezca en
una lista de cambios pendientes de llevar a la guía.

A. **Versión entera por clave, más un campo con el identificador de la decisión**
   (recomendada): `version: 2` y `decision: D26`. El chequeo puede exigir que
   toda frase con versión mayor que 1 tenga decisión, y la lista de pendientes se
   genera sola desde el catálogo. Es un dato, no una convención que alguien
   recuerde
B. **Solo el commit de git**: cero campos nuevos, pero la lista de pendientes hay
   que armarla leyendo el historial, y nadie la va a armar
C. **Un archivo aparte con los cambios pendientes**: explícito y se desincroniza
   del catálogo en cuanto alguien edite una frase sin tocar el archivo
X. Other (please specify)

[Answer]: A

## Q5 — Qué hace el corredor cuando un caso no se puede medir

AC4.4.6 ya fija dos casos: sin clave del modelo se detiene antes de la primera
llamada nombrando la variable, y sin backend de trazas el reporte se genera
igual. Falta el caso intermedio: la corrida empezó y **un caso** falla por algo
ajeno al código (el proveedor responde con error, se agota la cuota, se acaba el
tiempo).

A. **El caso se marca "no medido" con su causa y la corrida sigue**
   (recomendada): el reporte separa aprobados, fallidos y no medidos, y una
   corrida con no medidos se marca como **no comparable** contra la línea base.
   Así un fallo de infraestructura nunca se cuenta como fallo de calidad, que es
   lo que la regla del proyecto exige
B. **La corrida se detiene en el primer caso no medible**: la señal es más fuerte
   y se pierde toda la información de los casos que sí corrieron
C. **El caso se reintenta hasta que pase**: esconde el problema y puede gastar
   presupuesto sin límite
X. Other (please specify)

[Answer]: A
