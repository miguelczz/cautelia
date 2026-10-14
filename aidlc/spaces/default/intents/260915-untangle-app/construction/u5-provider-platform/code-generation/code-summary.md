# Resumen de la generación de código — U5 `provider-platform`

Todas las cifras de este documento están **medidas**, y cada una dice con qué
comando sale. Ninguna se escribió de memoria.

Esta es la primera unidad del proyecto que **cuesta dinero de verdad**, y la
única que decide cuándo se deja de gastar. Así que el documento está organizado
alrededor de eso: primero lo que una herramienta comprueba —y no la disciplina
de quien escriba después—, luego lo que se midió, y al final **lo que apareció y
el diseño no había previsto**, que es la parte que vale la pena leer.

---

## 1. Lo que dejó de depender de la disciplina

Cinco garantías que antes eran una frase en un documento y ahora son un comando
que falla.

| Garantía | Qué la comprueba | Qué pasaba sin ella |
| --- | --- | --- |
| El SDK de un proveedor solo se importa dentro de su adaptador | `mise run lint` (23 contratos de importación) | El núcleo acaba hablando con el cliente del proveedor y cambiar de proveedor deja de ser configuración |
| La contabilidad no importa las trazas | `mise run lint` | El corte de gasto se cae con el panel de trazas, y el techo deja de cortar justo cuando más hace falta |
| Ninguna tabla excluida del aislamiento tiene columna de texto libre ni de dato personal | `mise run rls:check` | Cuatro tablas fuera del aislamiento son cuatro sitios donde un dato de una aseguradora se ve desde otra |
| Ningún atributo de tramo lleva texto del asegurado | `mise run test:u5` (lista cerrada + forma en ejecución) | Un dato personal en una traza es RT-14, que es compuerta dura |
| Un tope del proveedor que nadie miró en treinta días falla el chequeo | `mise run schema:check` | Un tope sin comprobar es una creencia, no un control |

Las dos primeras y la última corren dentro del paso 6 del guion único de
verificación, que **crece por dentro** y sigue teniendo nueve pasos. Las otras
dos son pruebas, así que corren en el paso 5 con todas las demás.

## 2. Lo que se midió

| Qué | Cuánto | Comando |
| --- | --- | --- |
| Pruebas de la unidad | 196 | `mise run test:u5` |
| Pruebas del proyecto | 677 | `mise run test` |
| Cobertura agregada | 89,53 % sobre piso del 80 % | `mise run cov` |
| Cobertura de `providers` | 93,86 % | `mise run cov` |
| Cobertura de `telemetry` | 93,88 % | `mise run cov` |
| Contratos de importación | 23, ninguno roto | `mise run lint` |
| Archivos tocados | 81 | Sale del historial de git y está enumerado en `source-manifest.json` |
| Reglas de negocio impuestas | 52 de 53 | `traceability.json` |
| Controles de seguridad con prueba | 15 de 16 | `traceability.json` |
| Pasos del guion de verificación en verde | 9 de 9 | `scripts/verify.sh` |

Las dos filas que no llegan al total dicen por qué en `traceability.json`, y
ninguna de las dos se cerró con un "sí" cómodo:

- **BR1.6** pide prueba de contrato con **respuesta grabada**, y grabar una
  exige una clave y algo de cuota. Las pruebas de esta entrega inyectan los
  errores sin clave y sin costo; la grabación se hace la primera vez que haya
  clave y corre por hito.
- **SEC-U5.9** son dos mitades. La de esta unidad está hecha: el carril por
  omisión es el público, así que una petición que no lo pide explícitamente
  nunca toca la reserva de grabación. Comprobar la credencial de quien **sí** lo
  pide es de U16 y U17, porque se comprueba donde se abre la llamada; lo dice la
  sección 7 del `functional-spec.md`.

## 2 bis. Lo que la revisión encontró, y por qué la más seria no era un defecto

El revisor plantó **catorce mutaciones** en el código del dinero, las cuotas, el
aislamiento y las trazas. Doce las atrapó la suite y una más el comprobador de
tipos —quitar la redacción del exportador no lo ve ninguna prueba, pero el tipo
del transporte exige texto ya redactado, así que el paso 4 del guion lo caza—.
Las dos que quedaron en pie eran reales y están cerradas:

- **La frontera entre los dos carriles de presupuesto no tenía prueba.** Se podía
  sustituir la función que elige cuál de los dos restantes se entrega por "usa
  siempre el público" y las 177 pruebas seguían pasando. Es lo único de esta
  unidad que protege la reserva del video de la semana doce. Ahora hay dos casos
  que piden los dos carriles contra **la misma ventana**, para que la respuesta
  opuesta sea la afirmación.
- **El techo no veía el gasto facturable que no se pudo valorar**, y ese es el
  hallazgo que más caro habría salido. Una llamada facturable sin precio sumaba
  cero al acumulado y solo incrementaba un contador que alimentaba la pantalla,
  así que los 5 USD y la alerta de los 3 se podían cruzar con el estado diciendo
  `OK`. No violaba ninguna regla escrita —el registro y lo publicado sí decían
  "no medido"— pero contradecía la prohibición del proyecto de incurrir en gasto
  que no esté escrito como excepción. Y el caso está vivo hoy:
  `gemini-embedding-001` ya no tiene precio de lista.

  **Se resolvió cerrando**, que es como esta unidad falla siempre que hay dinero
  de por medio, y con **una sola regla**: el restante público queda "no medido"
  cuando la ventana cuenta llamadas facturables sin valorar. Todo lo demás sale
  por los caminos que ya existían —el estado, el rechazo de cuota, el cupo del
  sitio y el modo de voz—, sin un quinto estado y sin una segunda decisión que
  después se olvide de actualizar. Queda como objetivo medible NFR15.7, gemelo
  del que mide el mismo cero con la base caída.

  El corte alcanza **solo al carril público**, y eso es deliberado: la fila de la
  ventana cuenta cuántas llamadas no se valoraron pero no de qué carril salieron,
  así que cerrar también la grabación gastaría la reserva del video por una
  llamada que pudo venir del enlace público.

## 2 ter. La contabilidad del carril de grabación, que quedó a medias y ahora no

Cerrar el hallazgo del techo destapó que el **otro** carril tenía los mismos dos
defectos, uno de ellos invertido. Los dos están cerrados.

- **Una llamada de grabación con la reserva agotada no podía registrarse.** La
  entidad y la base impedían que lo gastado superara la reserva, así que la
  escritura levantaba y **la fila se perdía**. Eso enfrentaba dos reglas
  aprobadas: BR4.5 acepta el exceso de la llamada en vuelo, BR3.1 exige la fila
  sin excepción. Manda BR3.1, y la razón no es de jerarquía: una fila de gasto
  perdida falsea una cifra publicada y no deja rastro de que falta, mientras que
  un restante que llega a cero y se queda ahí no falsea nada, porque el restante
  ya se informa con piso en cero.
- **El conteo de llamadas sin valorar no distinguía carril**, así que una
  llamada de grabación sin precio inflaba el restante de su carril sin que nada
  lo dijera —el mismo defecto que la revisión encontró enfrente—. Ahora tiene su
  propia columna y su propio corte.
- **Y la mitad inversa, que era la más cara.** Con el conteo indistinto, una
  llamada de grabación sin valorar cerraba también el carril **público**. La
  aritmética dice que no debe: el gasto público no se guarda, se deriva restando
  lo de grabación del facturable, así que el cero de esa llamada se cancela y el
  restante público sigue siendo una medición exacta. No es aflojar el techo —el
  techo sigue en su cifra y el carril que sí queda impreciso se cierra por su
  propia causa—: es mirar la imprecisión del lado de la resta donde está.

  Importa hoy y no en abstracto: **el precio que falta en la tabla es justo el
  del minuto de voz**, que es lo que consume una grabación. Sin ese descuento, la
  primera grabación de la semana doce apagaría el chat y la voz públicos durante
  el resto de la ventana de noventa días, que es exactamente la demostración que
  la grabación existe para mostrar.

## 3. Lo que apareció y el diseño no había previsto

Cada uno de estos salió de correr algo, no de leer. Están por orden de lo que
costaba si nadie los veía.

### 3.1 Un cupo de **cero** dejaba pasar la primera llamada del día

La sentencia que consulta y consume la cuota en un solo acto tenía la condición
del límite **solo en la rama de conflicto**. El inserto inicial —el de la
primera llamada del período— no la miraba.

Cero no es un límite raro: es exactamente lo que devuelve el cupo del sitio
cuando el presupuesto público se agota, o sea **el corte del enlace público**.
Con el techo alcanzado pasaba una llamada de voz al día, y el rastro que dejaba
era una fila con conteo 1 sobre límite 0, que se lee como si todo estuviera
bien.

La lección general vale para las unidades que faltan: **una guarda escrita solo
en la rama de conflicto no gobierna la rama de inserto**, y el límite cero es
justo el caso en que las dos ramas se separan.

### 3.2 Dos reglas que nadie podía cumplir

La comprobación de coherencia previa a la revisión —grepear los 53
identificadores de regla contra los archivos de la unidad— encontró **dos reglas
sin imposición en ningún archivo**. Ninguna de las dos se podía ver leyendo el
código, porque lo que faltaba no estaba escrito en ninguna parte.

- **La devolución del cupo no existía.** La cuota se consumía al abrir la
  llamada y no había ninguna vía de vuelta. La consecuencia es la que la propia
  regla nombra: una caída de red antes del primer turno le quitaba el día entero
  al visitante.
- **La pausa hacia la bandeja y la reanudación eran imposibles de escribir.**
  Las dos ocurren **fuera de un turno**, y el ayudante de tramos exigía turno
  abierto; además no había nombre de tramo para esos dos momentos ni atributo
  para quién decidió, y la lista de atributos es cerrada y de esta unidad. Un
  consumidor que lo intentara recibía un error de atributo. La lista cerrada
  protege contra el texto libre **y a la vez** impedía lo que la regla pide, y
  solo su dueña podía resolver las dos cosas a la vez.

### 3.2 bis Cerrar las dos reglas obligó a tocar el esquema y a contradecir tres documentos

Ninguno de los dos huecos se pudo tapar sin ampliar algo que un documento
aprobado declaraba cerrado, y las tres ampliaciones están escritas con su razón
en vez de heredadas en silencio.

- **Una quinta tabla.** La devolución del cupo tiene que ser idempotente, porque
  U16 cierra la sesión siempre —también cuando la llamada se cae—, así que el
  doble cierre es el caso normal. La guarda de "no bajar de cero" protege al
  contador del visitante, cuyo límite es uno, pero **no** al del sitio, cuyo
  conteo es grande: sin marca durable, el segundo cierre le devuelve al sitio un
  cupo que sí se gastó. No cabía en ninguna tabla existente.
- **Un decimosexto atributo de tramo.** Aquí los documentos se contradecían
  entre sí: `observability-design.md` fijaba quince y BR6.4 exige que la
  reanudación lleve quién decidió. El valor es el identificador del principal,
  nunca el nombre de nadie, y su forma se comprueba en ejecución.
- **Un cuarto nivel de tramo.** Los tres niveles del turno siguen siendo tres.
  Los dos momentos del caso son otro eje: ocurren fuera de cualquier turno y son
  tramos raíz. Darles el nivel del turno habría permitido que un nodo colgara de
  una pausa, que es una traza que describe algo que no ocurrió.

Y una pregunta que ni la regla ni el flujo contestaban: **de qué día se devuelve
el cupo**. Una llamada que empieza a las 23:58 y se cae a las 00:03 tomó el cupo
de ayer, así que el periodo sale de cuándo se abrió y nunca del reloj del
cierre.

### 3.3 Encadenar el error de validación habría metido la respuesta del modelo en la traza

El objeto de la excepción de la biblioteca de validación **lleva dentro el valor
que no validó**, así que cualquiera que registre la traza completa lo imprime; y
una respuesta del modelo puede llevar el dato personal que el asegurado acaba de
dictar. El error sale ahora sin encadenar y su mensaje no nombra ni el campo.

Esto no estaba escrito en ningún documento, y es exactamente el modo de fallo
que NFR11 declara compuerta dura. **Ningún punto único de redacción vigila esa
vía**, porque la excepción no pasa por ningún punto de salida.

### 3.4 Una lista cerrada de **nombres** no cierra la puerta

`untangle.prompt_hash` y `untangle.case_id` son los dos cadenas, así que el
turno entero del asegurado pasado como "hash" compilaba sin protestar. La capa
de tipos no ve eso. La mitad que faltaba es **comprobación de forma en
ejecución**: el resumen son sesenta y cuatro hexadecimales y los identificadores
no admiten espacios ni saltos de línea.

### 3.5 Un contrato de importación no vale hasta que se ha plantado su violación

Se plantó una violación de cada contrato nuevo. Tres fallaron; el de la
superficie de trazas contra su repositorio **pasó en verde**, porque el
separador de la herramienta no prohíbe lo que parece. Se añadieron dos contratos
de independencia y se volvió a plantar. De 16 contratos a 23.

Escribir un contrato y verlo verde no prueba nada.

### 3.6 Ni el SDK del proveedor ni el de trazas se instalan, y por razones distintas

- El de Gemini, porque la frontera ya estaba cerrada contra la **API REST** y
  adoptarlo exigía rehacer petición, lectura y traducción de errores ya
  revisadas. En su lugar el cliente HTTP pasa de desarrollo a runtime, que son
  **cero paquetes nuevos** en el árbol.
- El de OpenTelemetry, por una razón que no es de trabajo: **su exportador
  entrega tramos por su cuenta**, y aquí el orden es serializar, redactar y
  entregar. Instalarlo abriría un punto de salida sin redacción, que es
  precisamente lo que `project.md` prohíbe: "imposible por construcción, no
  detectable por disciplina".

El punto de extensión sigue marcado, ahora con la condición escrita en el tipo:
lo que se instale tiene que aceptar texto ya redactado.

### 3.7 Un 429 de Gemini es a la vez límite de ritmo y cuota agotada

De esa distinción depende reintentar o detener el trabajo, y ningún documento
dice cómo distinguirlos. El valor por omisión es `rate_limited`, que es el lado
seguro: tratar un límite pasajero como "se acabó el dinero" pararía la
demostración en vivo, y equivocarse al revés solo produce reintentos que no
cuestan y que abren el circuito a los cinco. **Es una suposición hasta que haya
una respuesta real grabada.**

## 4. Lo que queda abierto y quién lo recoge

| Qué | Quién |
| --- | --- |
| El número de intento en la traza: el reintento es del ejecutor de nodos y la firma del adaptador no lo lleva | U12 `graph-runtime`, al construirse |
| Una parada por saldo agotado no se puede marcar en el tramo: la lista cerrada de tipos de error solo admite los cuatro, y la parada no es uno a propósito | Queda escrito en vez de hecho |
| `responseSchema` de Gemini acepta un subconjunto de OpenAPI y rechaza las referencias que genera el validador para modelos anidados. El esquema plano funciona; uno anidado probablemente no | U11 `intake`, que es quien pide salida estructurada de verdad |
| `gemini-embedding-001` ya no aparece en la página de precios; sus llamadas quedan "no medidas" | U8 `policy-rag`, que es quien consume los embeddings |
| Comprobar la credencial de quien pide el carril de grabación | U16 `voice-call` y U17 `voice-public-link`, donde se abre la llamada |
| Cerrar la sesión de voz siempre, también cuando la llamada se cae, para que el cupo se pueda devolver | U16 `voice-call` |
| El canal por el que sale la alerta de los 3 USD | Intent `infra` |

## 5. Lo que este resumen no dice

- **El adaptador no se probó contra Gemini.** Grabar una respuesta real exige
  una clave y algo de cuota; las pruebas de esta entrega inyectan los errores sin
  clave y sin costo. La grabación se hace la primera vez que haya clave y esa
  prueba corre por hito. Está declarado así en `traceability.json`.
- **Ningún umbral, piso de cobertura ni lista de exclusión se tocó.**
