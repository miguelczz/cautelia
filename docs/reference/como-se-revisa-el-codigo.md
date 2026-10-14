# Cómo se revisa el código de este proyecto

Escrito el 2026-09-28, después de U12 y de las tres primeras tandas de U13, y ampliado
el mismo día tras revisar el historial completo de `main`, que tenía siete formas más
sin escribir. Es el compañero de `como-se-escribe-el-codigo.md`: aquel dice **quién**
escribe y en cuántas tandas, y este dice **qué buscar** cuando ya está escrito.

No es teoría. Cada forma de abajo salió de un defecto real de este repositorio, y cada
una lleva el caso que la enseñó.

El procedimiento que usa este catálogo está en la skill `revisar-tanda`
(`.claude/skills/revisar-tanda/`), que lo lee cuando hace falta en vez de cargarlo
siempre.

## La regla de la que todo cuelga

**Rompe la conducta y mira si alguna prueba se cae.**

No leer la prueba y asentir. No confiar en el informe de quien la escribió —ni en el
mío—. Cambiar el valor, invertir la comparación, saltarse el paso, y correr. Si al
romper una regla no se cae ninguna prueba, la prueba está escrita a la medida del
código y no del criterio.

Y el corolario, que cuesta más: **el rojo que cuenta es la conducta rota, no un
`ImportError`**. Un símbolo que todavía no existe no es evidencia de nada. En U12 una
tanda entregó dos `ImportError` como prueba de que sus pruebas fallaban primero; su
conducta real pasaba intacta.

## La regla que mantiene vivo este documento

**Toda cosa nueva que sirva —lección o buena práctica— se escribe en el momento en que
aparece, no al final.** Decisión de Miguel del 2026-09-28. Una lección que espera al
cierre de la unidad se escribe con la mitad del detalle, y la mitad que se pierde es
siempre la misma: el caso concreto que la hizo evidente.

Escribirla no es elegir este archivo: es elegir **dónde vive**, y la pregunta que lo
decide es una sola —*¿qué pasa si me la salto?*—.

| Si al saltarla… | Va a | Ejemplo nuestro |
| --- | --- | --- |
| pasa algo que no debía pasar nunca | un **hook**, que es lo único que bloquea de verdad | empujar a `main` sin correr las compuertas |
| se saltan pasos de un procedimiento que se repite | la **skill** `revisar-tanda` | el catálogo de este documento |
| queda una regla que aplica siempre | `project.md`, por el ritual de aprendizajes | el reparto del trabajo, cómo se reporta |
| hace falta el caso y el razonamiento | **este documento**, o el de proceso | las formas de abajo, con su defecto |

Las reglas van cortas a `project.md`; el razonamiento y el caso se quedan aquí. Si se
invierte, `project.md` crece hasta que nadie lo lee entero y la regla deja de cumplirse
por el peso de las demás.

### El único hook que evaluamos, y por qué no está

La primera fila de esa tabla pide un hook para *"no empujar a `main` sin correr las
compuertas"*: cumple el criterio, porque un `main` en rojo es un incidente. Se evaluó
el 2026-09-28 y **Miguel decidió que no**.

La razón no es el costo de escribirlo. Es que protege contra un fallo que este
proyecto no ha tenido: en quince unidades, lo que ha encontrado defectos no ha sido
la compuerta llegando antes —siempre llegó— sino la revisión, que en U13 sola
encontró dieciséis con las nueve compuertas en verde. A cambio le cobraría varios
minutos a cada empuje, el de cualquiera, para evitar un incidente que se arregla en
minutos.

Queda escrito aquí y no en `team.md` para no tocar a mano una práctica afirmada: lo
que `team.md` ya dice —*"la compuerta autoritativa, y la única, es GitHub
Actions"*— sigue vigente, y esto es el registro de que se volvió a mirar y se
sostuvo. Si dentro de tres meses alguien lo vuelve a proponer, esta sección es la
respuesta.

## Las dieciséis formas de prueba que no prueban

Cada una pasó todas las compuertas automáticas antes de que alguien la mirara.

### 1. La que no pasa por la pieza

Comprobar el aislamiento con una consulta SQL directa prueba la política de fila de la
base, que ya está probada, **no el código nuevo**. La pieza tiene que estar en el
camino de lo que se afirma.

> U12, paso 2. La prueba de aislamiento del checkpointer consultaba la tabla desde la
> otra aseguradora. Al romper la pieza —haciendo que asumiera el inquilino— no se caía.

### 2. La aserción que no puede distinguir

Si se afirma que un valor sale de la configuración, hay que usar un valor **distinto**
del que la fábrica de pruebas pone por omisión. Con el mismo, un literal en duro pasa
igual.

> U12, paso 4. La prueba de la clave de degradación afirmaba contra el mismo literal
> que el `_spec` de las pruebas. Poner la clave en duro en el ejecutor dejaba las 38
> pruebas en verde.

**El caso más limpio de esta forma, de U14.** El encabezado de un caso dibujaba "quién
decidió" y "cuándo" en un solo elemento, separados por un punto, y la prueba pedía que
el texto **contuviera** "pendiente de decisión". Vaciar una de las dos mitades la pasa
igual, porque la otra sigue diciéndolo. Cada vez que una pantalla junta dos datos en
una frase, la prueba que la mire entera pierde la mitad de su poder: se separan en
elementos con su propio identificador y se compara por igualdad.

### 3. La decisión sobre el conjunto en vez de sobre el elemento

Cuando el código elige un camino, hay que preguntarse **qué caso mixto lo recorre** y
escribirlo.

> U12, paso 2. La sentencia de las escrituras pendientes se elegía mirando el lote
> entero: con una sola escritura normal, todo el lote perdía la semántica de reemplazo,
> y un nodo que interrumpía después de haber escrito algo perdía en silencio el nuevo
> motivo de la pausa.

### 4. La defensa que solo mira el salto directo

Cuando se prohíbe algo, hay que preguntarse si se prohíbe **a un salto** o **de verdad**.

> U12, paso 5. El contrato de importación del ritmo del turno permitía los saltos
> indirectos. Un módulo puente de una línea llegaba a la verificación de póliza con las
> 35 reglas en verde.

La misma forma en análisis estático: un chequeo que mira el nombre del constructor deja
abiertas las demás vías de llamarlo.

> U4. El chequeo del tipo sellado tenía cuatro vías abiertas —argumento solo posicional,
> solo por palabra clave, de resto variable, y el alias de importación—. La grave era la
> última: `import Sealed as S` y luego `S(b"en claro")` fabricaba un sellado de verdad
> que el repositorio habría escrito en la columna cifrada.

### 5. La prueba que afirma más de lo que comprueba

Si cubre una parte de un criterio, tiene que decirlo en su docstring. Una compuerta
dura que parezca cerrada estando a medias es peor que una que se declare a medias.

> U12, paso 6. La prueba de la compuerta dura decía cerrar "texto y estado" y solo
> cerraba el estado.

### 6. La que comprueba ausencia en vez de identidad

En aislamiento, **la filtración no es el dato, es la distinción**. Comprobar que el
dato ajeno no aparece no basta: recibir algo *distinto* de lo que recibe un desconocido
ya dice que ese caso existe, aunque la frase sea inofensiva.

La forma correcta es **comparar** contra la respuesta ante lo inexistente, campo por
campo, con el **control positivo delante**: sin él, las dos aserciones pasan igual con
una implementación que no entregue nunca nada.

> U12, paso 7, y las dos compuertas duras de U13.

### 7. La que mide dentro de una sola ventana

Los bordes de tiempo no se ven desde dentro del intervalo. Un límite diario se prueba
**un minuto antes y un minuto después** de su reinicio.

> U13, tanda 1. Ensanché la ventana diaria del contador a veintiséis años y las catorce
> pruebas siguieron verdes: ninguna miraba el reinicio.

### 8. La que se escribió desde la lectura equivocada del criterio

Es la forma 2 subida un nivel, y la más cara de todas: cuando el **caso de evaluación**
se deriva de lo que el código hace, la compuerta deja de ser compuerta. Por eso un caso
existente nunca es la evidencia de que algo está bien; la evidencia es el criterio
aprobado, leído otra vez.

> U11, tanda 2. Los umbrales de insultos llegaban un insulto antes de lo que pide
> AC1.13.3, y terminar la sesión al segundo le colgaba la llamada a quien todavía tenía
> un turno. El caso de DS-2 venía de la tanda 1 con la lectura equivocada y la
> configuración de las tres aseguradoras se escribió para que ese caso pasara.

### 9. La que solo se comprueba en un idioma

Toda regla sobre texto se prueba con **la misma frase en los dos idiomas**. Un umbral
que cuenta signos, palabras o caracteres casi nunca significa lo mismo a los dos lados.

> U11, tanda 2. BR3.4 contaba `?` y `¿` juntos con umbral de dos signos, así que
> "Are you hurt? Where did it happen?" pasaba y la misma pregunta en español fallaba.
> Ahora cuenta solo el signo de cierre, que es el que los dos idiomas comparten.

### 10. La medición que se incluye a sí misma

Una cifra publicada se comprueba preguntando **qué entró en el denominador**.

> U1 publicó 90,05 % de cobertura. El real era 85,83 %: el corredor medía con los
> archivos de prueba dentro, y las pruebas se cubren a sí mismas enteras.

### 11. La que lee el efecto en el mismo instante que lo provoca

Una prueba de pantalla que provoca algo y lee el resultado **en la línea siguiente**
compite con el dibujo. Se ve sola: pasa cien veces en el archivo suyo y falla en la
suite completa, donde la máquina va cargada y el segundo dibujo llega más tarde.

De U14: la cola anuncia cuántos casos quedaron para quien no ve la lista cambiar, y el
anuncio lo pone el anunciador compartido, que vive en la raíz. Llega en un dibujo
**posterior** al de la lista. La prueba esperaba las filas y leía el anuncio en el acto:

```ts
await screen.findAllByRole("row");
expect(screen.getByTestId("announcer-status").textContent).toBe("2 casos");
```

Verde en su archivo, roja en la corrida entera. La forma correcta espera el hecho, no el
instante:

```ts
await waitFor(() => {
  expect(screen.getByTestId("announcer-status").textContent).toBe("2 casos");
});
```

**No es lo mismo que una prueba inestable.** Una inestable falla a veces por algo que no
se controla; esta falla siempre que el segundo dibujo tarde, y eso depende de la
máquina, no del azar. Se arregla esperando, no reintentando, y **nunca** subiendo un
tiempo de espera fijo: lo que hay que esperar es el hecho.

La señal para buscarla: todo lo que atraviesa un proveedor compartido —un anunciador,
una caché, un contexto de la raíz— cambia de estado en un dibujo distinto del que lo
provocó.

### 12. El doble que acepta lo que la pieza real rechaza

Un doble más permisivo que la pieza que sustituye no prueba nada: prueba el doble. Y no
falla nunca, porque el doble no tiene reglas que romper. **Es la forma más cara de este
catálogo**: dejó el chat público sin poder atender a un solo visitante desde el día en
que se construyó, con 2.363 pruebas en verde.

La costura tenía tres unidades. U11 escribió `open_case` —"abre el caso en el primer
turno"— y nadie la llamaba. U12 escribió `handle_turn`, que **exige** `case_id` y levanta
si falta, con la razón en el docstring de su error: "cablear cuándo nace un caso es de
U13/U16". U13 entregaba el turno con `case_id` en nulo, confiando en que "el grafo lo
dirá por su cuenta si lo necesitaba". Cada unidad correcta por dentro; la costura, de
nadie.

Lo que la tapó fue el doble. Todas las pruebas del canal enchufan un `handle_turn`
falso, y el falso aceptaba el turno sin caso:

```python
def _grafo_que_devuelve(*eventos):
    async def falso(entrante):
        del entrante          # <- aquí está el defecto: ni lo mira
        for evento in eventos:
            yield evento
    return falso
```

El de verdad empieza con `if turn.case_id is None: raise`. El doble no. Peor: **un doble
abría su propio caso** cuando el turno llegaba sin uno, que es justo lo que el real no
hace, y con eso el conductor de evaluaciones recorría conversaciones enteras en verde.

La regla que sale de aquí: **un doble tiene que rechazar todo lo que la pieza real
rechaza.** Sus precondiciones no son detalle de implementación, son parte de su
contrato, y un doble que las relaja convierte cada prueba que lo usa en una que mide
otra cosa. Cuesta tres líneas:

```python
async def falso(entrante):
    assert entrante.case_id is not None, "el canal abre el caso antes de entregar (BR1.1)"
    ...
```

La señal para buscarla: **un `del argumento` o un `_` en la firma de un doble**. Dice, en
el código, "no miro lo que me dan"; y lo que le dan es exactamente el contrato que nadie
está comprobando.

Y su compañera, la que explica por qué nadie lo vio antes: **al menos una prueba tiene
que recorrer la costura con la pieza real**. No hace falta que sea caro. La que cerró
esta entra en la suite determinista y no llama a ningún proveedor: el visitante pide
hablar con una persona, la señal la reconocen los patrones versionados, y el turno deriva
sin llegar al nodo que llama al modelo. El caso de golden set de punta a punta sí
necesita clave y queda fuera del subconjunto de arranque —por eso no cubría nada en cada
entrega—, pero la mitad barata de ese recorrido siempre se puede escribir.

### 13. La respuesta declarada que no envejece con el contrato

Una respuesta de ejemplo escrita a mano, sin el tipo del contrato, se queda vieja el día
que el contrato crece, y **nada lo dice**: no es una prueba que se cae, es un cuerpo de
datos que sigue pareciendo válido.

> U22, tanda 2. La revisión añadió `top_cases` a `SpendPanel` y a la pantalla del gasto.
> El único sitio que alimenta esa pantalla con un cuerpo fijo es el registro de pantallas
> del arnés, y su campo era `body: unknown`. La pantalla hacía `top_cases.length` sobre un
> `undefined` y `main` se puso en rojo con siete fallos —cuatro de accesibilidad y tres de
> dibujo, uno por motor—, todos el mismo error. Las 2.810 pruebas de la suite estaban en
> verde: el cuerpo solo lo usa el arnés, que corre en la tubería y no en local.

Lo que lo cierra no es acordarse: es el tipo. `const CUERPO: SpendPanel = {...}` hace que
el próximo campo del contrato rompa el comprobador de tipos, que sí se corre antes de
empujar. La señal para buscar esta forma: **un `unknown`, un `any` o un `as` en la
declaración de un dato de prueba**. Dice, en el código, "aquí el contrato no llega".

Y su regla general: cuando un cambio toca un tipo de respuesta, hay que buscar **todos**
los sitios que construyen ese tipo a mano, no solo los que el compilador señala.

### 14. La que se apoya en un estado temporal del mundo

Una prueba que necesita que algo **siga estando vacío, ausente o apagado** para poder
fallar. Mientras lo esté, es verde y parece sólida; el día que alguien lo llene, deja de
poder fallar y se cae — y lo que se rompió no es el código, es que la prueba nunca
construyó la situación que afirmaba comprobar.

> U19, tanda 1. Una prueba de integración de U4 exigía que crear un caso de un tipo sin
> campos fallara. El único tipo sin campos era `quote_request`, **vacío a propósito
> esperando a U19**, con el docstring de la guarda diciéndolo con esas palabras. U19 le dio
> sus diecisiete campos y la prueba se cayó con `DID NOT RAISE`: no quedaba ningún tipo
> vacío con el que ejercer la regla.

La guarda era correcta y no se tocó. Lo que había que cambiar es la prueba: **vaciar ese
tipo en el esquema** para ejercer la regla, en vez de apoyarse en que alguno siga vacío. Lo
que se protege es que un tipo sin campos no abra caso, no que un tipo concreto esté vacío.

La señal para encontrarla: **un comentario que dice "por ahora", "hasta que", "todavía no"
o "a propósito" cerca de una prueba o de la guarda que prueba.** Ese comentario es la fecha
de caducidad escrita, y nadie la mira.

Y la regla de revisión que sale: **cuando una tanda llena algo que estaba vacío a
propósito, hay que buscar quién se apoyaba en que lo estuviera.** Es un grep del nombre, y
cuesta menos que un `main` en rojo. En este caso la sesión de la nube ya había corregido la
gemela unitaria de esa misma prueba, con el razonamiento correcto escrito; se le escapó la
de integración porque su entorno no tiene motor de contenedores, y a la revisión local se
le escapó el grep.

### 15. El umbral calibrado en una máquina distinta de la que lo comprueba

Una prueba cronometrada cuyo umbral se fijó midiendo en el portátil de quien la escribió,
y que la compuerta corre en otra máquina. Mientras la segunda sea parecida, pasa; el día
que no, se cae **sin que el código haya cambiado**, y lo que la prueba estaba midiendo
resulta ser cuál de las dos máquinas tocó.

> PERF-U12.2, el 2026-10-03. El umbral eran 1 ms, diez veces los 0,098 ms medidos en la
> Mac de desarrollo. El flujo de GitHub Actions midió 1,0507 ms con los dos controles
> intactos: su procesador es compartido y entre seis y diez veces más lento. `main` en
> rojo por aritmética, no por conducta.

Lo que distingue este caso del umbral que de verdad hay que respetar es **de dónde salió
el número**. Un umbral derivado de un presupuesto —PERF-U12.3 son 50 ms porque son el 6 %
de los 800 ms del turno— se respeta aunque la máquina apriete, y si no cabe, lo que se
abarata es el código. Un umbral derivado de una medición es instrumentación: su trabajo
es caer cuando el control cambia de naturaleza, y se recalibra contra **la máquina que
corre la compuerta**, con las dos mediciones escritas al lado.

La señal para encontrarla antes de que caiga: **un umbral con la frase "diez veces lo
medido" y una sola medición escrita.** Si solo hay una, está hecha en la máquina
equivocada.

### 16. La prueba anclada a un dato que se refresca por su cuenta

Una prueba que escribe como literal un valor que el proyecto actualiza por un camino
legítimo y periódico. No se cae por un defecto: se cae porque alguien hizo exactamente lo
que el proceso le pide hacer, y la reparación obvia —correr el literal— es escribir la
prueba a la medida del archivo.

> La misma sesión. `test_el_tope_de_la_voz_caduca_como_cualquier_otro` pasaba
> `today=date(2026, 10, 22)` para comprobar que una fila de tope caduca a los treinta
> días. Miguel leyó las consolas de los proveedores y refrescó `last_checked_at` al
> 2026-10-02 —que es justo lo que el chequeo de los treinta días existe para provocar— y
> la prueba cayó.

La regla que se comprueba no es "el 22 de octubre esta fila está vencida": es "treinta
días después de comprobada, cualquier fila está vencida". Así que el día se **deriva** de
la fila más reciente más el máximo declarado, y se añade la mitad que faltaba: que el día
antes **no** se queja. Sin esa segunda mitad, un chequeo que se quejara siempre pasaría.

La señal: **una fecha, un identificador o una cifra escritos a mano en una prueba que
también vive en un archivo versionado que alguien actualiza.** Si el archivo tiene un
proceso de refresco, la prueba tiene que leer de él.

## Las dieciocho formas de hallazgo que no están en ninguna prueba

Estas no se encuentran rompiendo: se encuentran leyendo con desconfianza.

### 1. El mecanismo que se da por bueno sin medirlo

Antes de apoyarse en una pieza existente —una exención, un flag, una lista
versionada— hay que **medir qué hace de verdad**, no qué dice su nombre.

> U13, tanda 4. Iba a usar la lista de claves exentas de la guardia para el aviso del
> ajustador. Medido: la plantilla no disparaba ningún patrón, así que la exención era
> configuración muerta; y peor, eximía **el texto entero con el comentario libre del
> ajustador dentro**, de modo que un "su póliza cubre el choque y le vamos a pagar 900
> dólares" pasaba sin intervención. La firma de una persona autoriza su decisión, no
> cualquier frase que escriba.

### 2. El linter que señala un problema de diseño, no de estilo

Cuando una regla de estilo se queja, la pregunta es si hay una firma mejor detrás. Casi
siempre la hay, y silenciarla la esconde.

> U12, paso 4 y U13, tandas 2 y 4. "Demasiados argumentos" tres veces, y las tres la
> respuesta correcta fue agrupar lo que **ya viajaba junto**: el turno de C-14, la
> decisión del ajustador. Desarmarlos daba siete sitios donde equivocarse al rearmarlos.

### 3. El contrato que obliga a invertir una dependencia

Cuando un contrato de arquitectura se rompe, la primera hipótesis es que el contrato
tiene razón.

> U13, tanda 2. Consumir C-14 desde el módulo del runtime arrastraba LangGraph a un
> canal por transitividad. La respuesta no fue relajar la regla: fue bajar el
> vocabulario del contrato a un módulo hoja y declarar un puerto. Ahora es **cierto**
> que cambiar el framework del grafo no toca ningún canal, en vez de ser una intención
> escrita en un ADR. Las pruebas ganaron de paso: inyectar un doble es pasar un
> argumento, no parchear un módulo.

### 4. El módulo que miente sobre sí mismo

Un docstring, un comentario o un encabezado que **afirma una propiedad** es una
afirmación por comprobar, no documentación. Es la forma que más veces ha aparecido, y
la que ninguna compuerta puede ver: nada falla cuando un archivo se describe mal.

> Cuatro casos. `budget.py` decía que su cuenta de palabras es un límite inferior
> conservador que "casi nunca" cuenta de menos, y es al revés: un tokenizador de
> subpalabras parte las palabras largas y en español da más tokens que palabras. Un
> docstring de U4 decía seis operaciones habiendo ocho. El encabezado del registro
> prohibido de U11 decía que los patrones se comparan plegados, y el código no plegaba,
> así que "¿qué más?" con tildes no coincidía. Un comentario de U9 decía que la
> explicación de Knotwell sale siempre de su regla de agencia, falso cuando dispara una
> regla de dinero.

### 5. El criterio declarado fuera de alcance porque ningún caso lo mira

**Un criterio aprobado no se cae porque el golden set no lo cubra.** La cobertura del
conjunto de casos dice qué se está midiendo, no qué hay que construir.

> U11, tanda 2. `compose_question` levantaba `ValueError` para el último bloque del
> orden fijo —o sea que un reporte completo terminaba en una excepción— y la tanda lo
> declaró fuera de alcance "porque ninguno de los dieciséis casos lo ejercita".

### 6. Lo indivisible escrito en dos transacciones

Cuando dos escrituras tienen que valer juntas o no valer, la pregunta es qué queda si
falla la segunda. Y se comprueba **provocando ese fallo**, no razonándolo.

> U4. El campo y su entrada de historial se escribían por separado: un fallo del
> anexado dejaba un campo sin rastro de quién lo cambió —lo que BR5.1 llama una
> pérdida— y un fallo del movimiento dejaba en el historial una transición que no
> ocurrió. Van en una sola, con dos pruebas que provocan el fallo del segundo paso y
> comprueban que el primero se revirtió.

### 7. El dato que el dueño puede derivar y llega por argumento

Si un módulo puede calcular un dato de lo suyo, recibirlo por parámetro le entrega al
consumidor el poder de falsearlo. Vale doble cuando ese dato abre una ventana o
concede un permiso.

> U4. La ventana para retomar una llamada cortada la aportaba entera quien llamaba,
> aunque U4 es dueño del historial que sabe cuándo se derivó el caso: un consumidor que
> pasara la hora actual la abría siempre. Ahora sale de su propio historial.

### 8. El respaldo que borra la distinción que protege

Un respaldo razonable —"si no sé decir esto, digo algo en vez de dejar un hueco"—
puede acabar diciendo **lo contrario** de lo que el emisor quiso. Y no falla nunca:
por definición, su trabajo es no fallar.

> La pantalla del chat resuelve por su clave lo que el servidor le manda, y una
> clave que no conoce cae en la frase de error. La regla es buena: un hueco deja la
> conversación muda, que es el modo de fallo que REL-U13.1 prohíbe. Lo que nadie
> miró es la lista: `intake.tone.calm` —la frase de degradación que el nodo de
> captura **declara en su propio `NodeSpec`**— no estaba. Así que cada turno que se
> degradaba le decía a la persona *"Tuve un problema para responder eso"* en vez de
> *"Quiero ayudarle con calma"*, y en pantalla un fallo y una degradación se veían
> exactamente igual.

Es la convención 8 del equipo —"no hay cláusula" y "no pude verificar" son valores
distintos y nunca se colapsan— cometida en el último metro, donde ya no se mira. El
servidor conservaba la distinción entera: en el estado, en la traza y en el cable. La
perdió el consumidor.

**Cómo se caza.** Un respaldo que traduce N valores a 1 necesita que **alguien
compruebe que la lista está completa**, y esa comprobación tiene que mirar hacia la
fuente, no hacia el catálogo. El chequeo que había —"toda clave escrita se usa en
algún sitio"— mira la dirección contraria y nunca podía verlo. El que faltaba recorre
los cuatro `NodeSpec`, lee su `degraded_copy_key` y comprueba que la tabla del chat la
tenga; añadir un nodo sin su frase ahora falla en la compuerta.

La señal para buscarla: **un `??`, un `.get(x, POR_OMISION)` o un `except` que
convierta un conjunto abierto en un valor fijo**, donde el conjunto abierto es en
realidad cerrado y está declarado en otro archivo.

### 9. La regla que solo vive en el tipo

Una regla apoyada en el sistema de tipos parece cumplida de una manera más fuerte
que una apoyada en una prueba: no es que alguien la compruebe, es que lo contrario
**no compila**. Es cierto, y es una buena barrera. Lo que no es cierto es que baste.

> El puerto de síntesis de C-16 recibe `Redacted` y no `str`, precisamente para
> que un texto sin redactar no pueda llegar al altavoz: un puerto que aceptara
> texto crudo sería un punto de salida sin redacción. El motor de la llamada lo
> respetaba. La rotura fue de una línea:
>
> ```python
> def _redactado(self, text: str) -> Redacted:
>     return text  # type: ignore[return-value]
> ```
>
> `Success: no issues found in 594 source files`. Las 123 pruebas de la unidad, en
> verde. Y la agente habría dicho en voz alta la placa de una persona.

Un tipo no es una compuerta: es una compuerta **con interruptor**, y el interruptor
cabe en un comentario. El proyecto ya exige que toda supresión lleve su razón escrita
al lado, pero eso lo hace cumplir una persona revisando, no una corrida.

**Cómo se caza.** En el paso de romper y correr, a una regla que el diseño declara
"garantizada por tipos" se le aplica la rotura que un tipo no puede parar: el
`type: ignore`, el `cast`, el `Any` en medio de la cadena. Si con eso no se cae
ninguna prueba, la regla no está protegida —está declarada—, y le falta una prueba
de conducta que mire **el valor que de verdad sale**, no su anotación.

La señal para buscarla: **una regla cuya justificación en el diseño dice "el
comprobador de tipos lo impide" y ninguna prueba nombra**.

### 10. La herramienta corrida fuera de su alcance

**El caso.** En U18, con una advertencia del linter delante, se corrió
`ruff check --fix src tests` desde `app/backend` en vez de la compuerta del proyecto,
`mise run lint`, que lo invoca desde la raíz sobre `app/backend`. Los dos son el
mismo linter y la misma versión. Pero las exclusiones por archivo del proyecto están
escritas con rutas relativas a la raíz, así que desde dentro no casan con nada: la
corrida de dentro vio dieciocho problemas donde la de fuera veía uno, y **"arregló"
dos**. Uno de esos dos arreglos borró un `# noqa: S608` con su razón escrita al lado
—una consulta construida con una constante del módulo, no con una entrada— y dejó
`main` a un commit de ponerse rojo por una regla que nadie había decidido cambiar.

Lo peligroso no es la falla: es que el resultado **se ve igual que un arreglo**. La
salida dice "2 fixed" y el diff es pequeño y plausible.

**Cómo se caza.** Los chequeos se corren siempre por el nombre de la tarea del
proyecto y nunca invocando la herramienta a mano, porque la tarea es la que lleva el
alcance. Cuando ya se corrió a mano, la comprobación es leer el diff **completo** de
la corrida automática antes de seguir: un cambio en un archivo que la tanda no toca
es la señal.

La señal para buscarla: **un archivo modificado que no tiene nada que ver con lo que
se está construyendo**, y en particular una supresión del linter que desaparece sin
que nadie escribiera por qué.

### 11. El campo que ninguna ruta puede llenar

Una agrupación, un campo o una sección cuyo dato de entrada **ninguna ruta de producción
puede producir** está tan vacía como si no existiera, y las pruebas no lo dicen: las
pruebas siembran el estado escribiendo el archivo, y el estado sembrado es imposible.

> U22, tanda 3. «Cómo falla» agrupa los casos fallidos por causa raíz y lee la línea base
> vigente. Pero `publish()` se niega a publicar una línea base con algún caso en `failed`
> (BR2.1, y está bien que se niegue), así que una línea base publicada **nunca** trae
> fallos: la sección dirá «No case failed» con cualquiera. El campo `Baseline.root_causes`,
> añadido en esa misma tanda para que la sección agrupara, tampoco puede llenarse nunca
> por esa vía. Hoy el reporte tiene 42 de 100 casos con causa `NOT_BUILT` y ninguno llega
> a la sección.

La pregunta que la encuentra es una sola: **¿qué ruta de producción construye el estado
que esta prueba siembra?** Si la respuesta es "ninguna", el hallazgo no es la prueba: es
que la fuente elegida en el diseño no puede tener el dato que el criterio pide. Aquí el
criterio aprobado (AC4.1.3) decía «el último reporte de evaluación» y la regla de la
unidad lo cambió por «la línea base vigente» sin notar que eso lo vaciaba.

### 12. La distinción que llega al dato y muere en la pantalla

Construir una distinción en el modelo y no dibujarla es peor que no tenerla: el código
demuestra que alguien entendió la diferencia, y la superficie sigue afirmando la versión
equivocada.

> U22, tanda 1. `LatencyMeasure` lleva su propia causa de no medida a propósito, porque
> las dos latencias no están sin medir por lo mismo: la de la voz es una decisión (se mide
> por hito contra proveedores de verdad) y la del chat es trabajo pendiente (sus dos
> eventos no se emiten). El panel dibujaba canal, extremos, conjunto y percentiles, y
> **no la causa**: mostraba la de la cifra, «por hito», para las dos. Quien leyera el
> panel quedaba mandado a esperar un hito donde lo que hay que hacer es construir dos
> eventos. Lo destapó la tanda 3, que en el README sí la escribió.

La señal: **un campo del contrato que ninguna pantalla lee**. Se busca con un grep del
nombre del campo; si solo aparece donde se construye, la distinción no llegó a nadie.

### 13. La decisión pura que producción no llama

Una función que decide bien, con sus pruebas en verde, **y a la que nadie llama desde el
camino real**. Es la más difícil de ver de este catálogo, porque todo lo que se mira está
correcto: la función, sus pruebas, su docstring. Lo que falta no está en ningún archivo.

> Aparece tres veces en este proyecto, y las tres se encontraron leyendo para diseñar y
> no revisando código. `ComplianceNode` se construye en la raíz de composición y nunca se
> le entrega al runtime. `quota.voice_mode(remaining, reserve)` decide entre la voz
> principal y la de respaldo, es pura, responde "respaldo" cuando falta un dato —y
> `server/voice_routes.py` tiene `VoiceMode.PRIMARY` escrito a mano en cuatro sitios—. Y
> seis campos del vocabulario del motor de reglas están declarados y nadie los escribe,
> así que las reglas que los nombran **no se disparan**: un campo ausente no satisface
> ninguna condición, y nada se pone rojo.

Las tres comparten la firma del defecto: **la conducta no falla, no ocurre.** Y ninguna
prueba unitaria puede encontrarla, porque cada pieza cumple su contrato.

Lo que la encuentra son dos greps, y valen los dos minutos:

- del nombre de la función de decisión, para ver si su único consumidor es su propia
  prueba;
- del valor que la decisión devolvería, para ver si alguien lo escribió a mano.

`VoiceMode.PRIMARY` escrito en una ruta es la forma visible de este defecto: alguien
puso el valor por omisión "hasta que se cablee", y eso se lee igual el día uno y el día
noventa.

La regla que sale de aquí: **cuando una unidad entrega una decisión que otra tiene que
cablear, el cable es trabajo declarado de alguien y se escribe en el plan.** Aquí los
tres casos lo tenían escrito en un docstring —"quien elige el modo es U17"— y un
docstring no aparece en ninguna lista de pendientes.

### 14. El permiso nuevo que no separa nada

Un diseño dice «el rol nuevo es un valor más del enum y su permiso una fila más en la
tabla». Se añade el valor, se añade la fila, las pruebas del rol pasan —puede lo suyo— y
la regla que la fila existía para hacer cumplir **sigue sin cumplirse**, porque el punto
que decide no mira la fila nueva.

> U19 lo pedía así: el suscriptor decide las solicitudes de cotización. La tabla de
> permisos de U2 ya tenía `decide_case` en `true` para el ajustador, y la ruta de
> decisión es **una sola**, que resolvía siempre esa acción. Con el rol y su fila
> añadidos, un ajustador seguía decidiendo solicitudes por la misma ruta: el nombre nuevo
> no tocaba nada. Lo que faltaba no era una fila, era **que el punto de decisión eligiera
> la acción por el tipo del caso**.

La señal para encontrarlo, antes de escribir código: **cuando un diseño dice «añade una
fila a esa tabla», hay que leer la tabla y el punto que la consulta.** Dos preguntas:

- ¿la acción que el diseño quiere usar ya está concedida a alguien a quien la regla nueva
  se la niega? Entonces no puede ser la misma acción.
- ¿el punto que consulta la tabla puede distinguir el caso nuevo del viejo con lo que
  tiene a mano? Si para distinguirlos hace falta un dato que no ha leído todavía, el
  cambio no es una fila: es el orden de lo que lee.

Y la prueba que lo demuestra **no es la del permiso concedido, es la de su contraria**:
que el titular del permiso nuevo *no* puede hacer lo viejo. Sin ella, un permiso
«nuevo» que en realidad fuera el viejo con otro nombre pasaría igual, porque lo que
separa a dos roles no se ve en lo que cada uno puede: se ve en lo que cada uno **no**
puede.

### 15. La comprobación que no puede coincidir

Una comprobación de unicidad, de pertenencia o de igualdad, escrita entre dos piezas que
guardan **el mismo dato con dos formas distintas**. Cada lado es coherente consigo mismo,
sus pruebas pasan, y la comparación del medio es verdad siempre.

> U4 acuñaba el número de caso al azar y lo comparaba contra los ya tomados: `if serial
> not in taken`. `taken` lo traía el repositorio como la columna entera —`STO-123456`— y
> `serial` eran los seis dígitos —`123456`—. **La condición no podía ser falsa nunca.**
> Las pruebas del acuñador le pasaban seriales a mano y pasaban; las del repositorio
> comprobaban que devolvía los números y pasaban. La frontera no la cruzaba ninguna.

Es más difícil de ver que un error de tipos porque no hay error de tipos: los dos lados
son `str`. Y es más difícil de ver que un fallo porque **no falla**: una comparación que
nunca coincide se comporta igual que una que coincide pocas veces, y aquí "pocas veces"
era una entre un millón.

Dónde buscarla:

- **Una comprobación cuya única consecuencia es rara.** Un choque de números, una clave
  repetida, un reintento. Si la consecuencia nunca se ha visto, nadie sabe si el código
  que la evita funciona.
- **Un nombre que nombra el dato y no su forma.** `taken_numbers` devolviendo números
  completos y `taken` comparándose contra seriales. Renombrarlo a `issued_serials` es lo
  que hace que el siguiente que lo lea vea el desajuste sin ejecutarlo.
- **Dos pruebas que no se tocan.** Cada lado probado con su propia forma es exactamente
  el estado en el que la frontera queda sin comprobar. Lo que la cubre es una prueba que
  **atraviesa** las dos piezas: emitir, y exigir que el segundo intento no repita.

### 16. El registro indexado por lo que desaparece primero

Dos identidades conviven en un camino y una vive menos que la otra. El registro que las
conecta se indexa por la corta, y el día que esa desaparece —por diseño, no por error—
quien sigue vivo deja de encontrar su entrada, y lo que se le iba a entregar se publica
donde nadie escucha.

> El chat guardaba la cola de eventos **por conversación**. El flujo lo abre la pestaña y
> vive mientras esté abierta; la conversación se la lleva el reinicio nocturno. Con la
> cola atada a la conversación, el mensaje siguiente abría una conversación nueva, buscaba
> su cola, no la encontraba, y **el visitante no volvía a recibir nada** hasta recargar la
> página: el `POST` respondía 202 y el turno se entregaba a una cola sin consumidor. Había
> un evento que lo decía —`chat.message_without_stream`— y su comentario decía «esto solo
> pasa si se cayó».

La señal: **preguntar por cada registro en memoria de qué es la llave y cuánto vive lo que
la llave nombra.** Si lo que la nombra puede desaparecer mientras el consumidor sigue ahí,
la llave está mal elegida. Aquí la identidad correcta era el navegador, que es de quien es
el flujo; y re-indexar además dejó sitio donde avisar de que la conversación anterior ya
no existe, que era otra regla sin cumplir.

Y una pista que vale para cualquier módulo: **un comentario que explica por qué una rama
"no debería pasar" es un buen sitio donde mirar.** El de este decía que solo pasaba si el
navegador se había caído; pasaba todas las noches.

### 17. El bloque que no abarca lo que su comentario dice

Un `with` --un tramo de traza, una transacción, un bloqueo-- cuyo comentario dice que
cubre tres pasos y cuya indentación cubre uno. El código compila, las pruebas directas
pasan, y lo que falla es **lo que entra por el camino real**.

> El cableado del ritmo de fondo encadenó `decision` y `compliance` detrás de la
> cobertura, con su comentario escrito: «dentro del mismo tramo de traza, porque son el
> mismo trabajo de fondo de este caso». La llamada quedó **fuera** del `with`. Los
> tramos de nodo cuelgan de uno de turno por regla escrita, así que el primer nodo de la
> cadena levantaba `SpanNestingError` y la tarea de fondo moría. Las cinco pruebas
> directas pasaban: abrían el tramo ellas mismas, como hace producción, y por eso no
> podían verlo.

Lo encontró **la prueba que pregunta quién llama a esto**: la que entra por el camino
real --`preload`-- en vez de llamar a la función nueva. Es la misma pregunta que cierra
la forma 13 de esta lista, y aquí cerró dos cosas a la vez: que la cadena tenga llamador
y que el llamador la llame **desde dentro** de lo que necesita.

La señal, al revisar un diff: **leer la indentación de cada `with` nuevo contra su
comentario.** Si el comentario habla en plural y el bloque abarca una línea, una de las
dos cosas está mal, y la barata de comprobar es la indentación.

### 18. El campo de nombre genérico que carga dos responsabilidades

Un campo cuyo nombre dice **qué tipo de cosa es** y no **para qué sirve** —`signing_key`,
`client`, `url`, `timeout`— por el que pasan dos usos distintos. Mientras los dos usos
compartan el valor, funciona y nadie lo nota. El daño llega el día que se separan: quien
separa cambia el campo pensando en uno de los dos usos, y el otro se lleva el valor
equivocado en silencio.

> U17 y el cierre de 1.16. `VoiceDeps.signing_key` firmaba el token de socket **y** el
> enlace de caso que la ruta entrega al colgar. Darle a la voz su propia clave sin
> separar antes los dos campos habría firmado el enlace con la clave de la voz: mismo
> formato, misma forma `/c#…`, y la bandeja rechazándolo al canjearlo. La comprobación
> que existía —que el enlace empieza por `/c#`— no distingue con qué clave se firmó.

Lo que lo delata es el **conteo de usos del campo dentro del módulo**: tres sitios leían
`deps.signing_key` y uno de los tres no hablaba de lo mismo que los otros dos. Antes de
separar un valor compartido, se cuentan sus lectores y se lee qué hace cada uno; si dos
hacen cosas distintas, son dos campos y cada uno se llama por su trabajo.

Y la prueba que lo cubre no comprueba el cableado, que es mirar dónde quedó guardado un
valor: comprueba **lo que sale por la puerta**. El enlace se canjea de verdad y se exige
que la otra clave no lo abra; el token que el navegador recibe se verifica contra las dos
claves. Rompiendo cada cableado por separado cae la suya y solo la suya.

## Cinco reglas sobre quien revisa

**Comparar con lo que ya funciona antes de diagnosticar.** El recibo de aprobación de
U13 se rechazó cinco veces con un mensaje que nombraba seis causas posibles, y ninguna
era la real: al archivo de preguntas le faltaba el encabezado `## Plan Approval`. La
respuesta estaba a una lectura de distancia del archivo equivalente de U12, y en vez de
eso probé el mismo comando una y otra vez.

**Parar al segundo rechazo del mismo comando.** Insistir convierte un fallo en diez. Se
para, se compara, y si no aparece, se dice en voz alta que está atascado.

**Verificar cada hallazgo ejecutando, antes de tocar nada.** Un hallazgo es una
hipótesis, venga del revisor o mío. En las etapas de diseño de U4, dos de cada diez
hallazgos resultaron falsos; en su generación de código, los once eran ciertos. La
diferencia solo se sabe comprobando, y arreglar un hallazgo falso es peor que no
arreglarlo: deja el código torcido y una prueba que defiende lo torcido.

**El veredicto se escribe sin lavarlo.** Un `NOT-READY` queda registrado tal cual, con
los hallazgos dentro y su evidencia debajo. Un registro que solo guarda los verdes no
sirve para nada, porque nadie lo consulta para confirmar que todo salió bien.

**Romper el punto que impone la regla, no el que la nombra.** En la tanda 1 de U14
rompí la línea que le pasa la aseguradora a la consulta —`credencial.tenant_id` por el
identificador de la dirección— esperando que se cayera la compuerta dura del
aislamiento. No se cayó ninguna prueba, y la primera lectura fue "la prueba está
escrita a la medida del código". Era al revés: llegados a esa línea los dos valores
valen lo mismo, porque la comparación que rechaza ya pasó antes. El cerrojo estaba en
`verify_credential`, un módulo más abajo; desactivar esa comparación tumbó tres
pruebas.

De ahí dos cosas. Una, **una rotura que no tumba nada puede ser una reescritura
equivalente y no una prueba floja**: antes de acusar a la prueba hay que preguntarse si
de verdad se rompió algo. Y dos, **encontrar dónde vive la regla es parte de la
revisión**, y lo que se encuentra se escribe junto al código: la línea que parece el
cerrojo y no lo es se va a leer como el cerrojo la próxima vez.

## Una rotura que no tumba nada: las cuatro respuestas

Es el momento más útil de la revisión y el que más fácil se despacha mal. En U14
pasó ocho veces en cuatro tandas, y cada vez la respuesta fue distinta. Hay cuatro, y
la pregunta se hace en este orden:

**1. ¿Se rompió algo de verdad?** Puede que la rotura sea una reescritura equivalente
—el caso del `credencial.tenant_id` de arriba— y entonces no hay nada que arreglar
salvo escribir junto al código dónde está el cerrojo de verdad.

**2. ¿Era una capa o una copia?** Si se rompió algo y nada se cayó, o lo roto era una
capa legítima de defensa que otra capa cubre, o era una **segunda copia de la misma
regla**. En la tanda 3 de U14 hubo dos de cada: la política de fila y la comparación
de la credencial son dos capas y se quedaron, escritas como lo que son; la
comprobación propia de "ya está decidido" y `require_alive` eran copias dentro de la
misma capa y se borraron. **Dos guardias para la misma regla significan que el día que
una cambie, la otra seguirá diciendo lo de antes**, y entonces hay dos versiones de la
regla y ninguna es la autoritativa.

**3. ¿La prueba no puede distinguir?** En la tanda 4, vaciar "pendiente de decisión"
de una de las dos mitades de una frase no tumbó nada, porque la prueba miraba el texto
**junto** y la otra mitad seguía diciéndolo. La regla estaba bien y el guardia era
único: lo que fallaba era la aserción. Se separan los datos en elementos propios y se
compara **por igualdad, no por contención**.

**4. ¿La prueba cubre un camino de varios?** La misma tanda: la pantalla del visitante
podía distinguir la causa del rechazo por una de sus dos puertas, y las pruebas solo
cubrían la otra. **Una regla que se aplica en más de un camino necesita una prueba por
camino**, y el número de caminos es un producto que hay que contar: dos puertas por dos
códigos son cuatro, no dos.

Las dos primeras respuestas cambian el código; las dos últimas cambian la prueba. El
error caro es aplicar la segunda cuando la respuesta era la tercera o la cuarta: se
borra un guardia que sí hacía falta, y la prueba que no podía verlo sigue sin poder.

## Lo que esta disciplina cuesta y lo que devuelve

Medido en U12: el agente escribía 31 minutos por tanda y la revisión con las nueve
compuertas costaba 10 a 15. Un sexto del tiempo.

A cambio, **en las siete tandas de U12 encontró un defecto real en cada una**, todos
con las compuertas automáticas en verde, y cinco de los ocho estaban en la prueba. En
la tanda 2 de U11 encontró seis, dos en compuertas duras, y cuatro tenían su prueba
escrita a la medida del código. En U13 encontró, entre otros, un hueco de seguridad que
estaba a punto de abrirse.

Ninguno se habría visto leyendo el informe de entrega.
