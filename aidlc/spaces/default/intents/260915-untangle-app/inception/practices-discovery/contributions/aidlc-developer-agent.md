**Collaborator:** aidlc-developer-agent

## Contribution

Reviso lo que vive dentro del código que se va a escribir: nombres, fronteras
entre capas, manejo de errores, organización de archivos y convenciones de
estilo. La posture de pruebas, la cobertura y las compuertas de CI las deja a
otro revisor; el lint como herramienta, SAST, secretos y cadena de suministro
también. La frontera está declarada al final (§7).

### 1. Diagnóstico: `## Code Style` es hoy una sección sobre herramientas, y la herramienta es justo la parte que debe esperar

La sección tiene cinco párrafos. El primero (formatter y linter) depende del
ADR de lenguaje y por eso queda en promesa. El segundo (manifiesto, lockfile,
versiones fijadas) es correcto y accionable. El tercero y el cuarto (frases
prohibidas, ISO/ACORD, paridad de claves, secretos) son del revisor de
seguridad. El quinto (comentarios que describen lo construido) es correcto.

Lo que no aparece en ninguna parte del borrador —ni en `## Code Style`, ni en
`## Way of Working`, ni en `discovered-rules.md`— es **dónde vive cada archivo,
qué puede importar cada módulo y qué pasa cuando algo falla**. Son tres de las
cinco cosas que deciden si P3 ("el orquestador es código") y F2.7 ("política de
fallo por nodo: tiempo máximo, reintento único, degradación honesta") son
propiedades del código o frases de un documento. Hoy están escritas como
intención y no hay una sola convención que permita comprobarlas.

El efecto práctico: la sección más diferida del borrador es también la menos
útil, y quien abra el primer Bolt no tiene respuesta a las dos preguntas que se
hacen antes de escribir la primera línea —"¿dónde va este archivo?" y "¿qué me
está permitido importar desde aquí?".

Propongo reorganizar `## Code Style` en tres bloques: **(a)** lo que se afirma
hoy porque no depende del lenguaje (§2), **(b)** lo que fija el ADR y qué tiene
que traer ese ADR para que (a) sea aplicable (§3), y **(c)** el momento exacto
en que (b) aterriza: el mismo commit que introduce el primer archivo de código
del aplicativo (§4.1).

Criterio que apliqué en todo lo que propongo, por el equipo de una persona y los
90 días: **cada convención tiene que ser un grep, una regla de importación o una
decisión de directorio**. Ninguna pide un framework, una ceremonia ni un
refactor. Lo que deliberadamente **no** propongo está en §3.3.

### 2. Lo que se puede afirmar hoy y sigue siendo verdad con Python o con Node

Ocho convenciones. Todas sobreviven al ADR porque hablan de estructura, de
nombres y de fronteras, no de sintaxis ni de herramientas. Doy la redacción para
que el lead la pegue.

#### 2.1 Un solo prefijo de ruta para el código del aplicativo

> El código del aplicativo vive bajo **un único directorio de primer nivel** en
> la raíz del repositorio, hermano de `site/`, `docs/`, `.claude/` y `aidlc/`.
> El nombre y la mecánica interna (paquete, workspace, `src`-layout) los fija el
> ADR de lenguaje; lo que se afirma hoy es el invariante: **un prefijo**. Todo
> alcance de herramienta —formatter, linter, type checker, runner de pruebas,
> cobertura— se declara como ese prefijo y nunca como una lista de exclusiones.

Por qué importa más de lo que parece: el repositorio ya contiene 1.011 líneas de
JavaScript inline en `site/index.html` y 91 archivos `.ts` del engine bajo
`.claude/`. Con un prefijo, "la landing no entra en el piso de cobertura"
(D-005, D-013) es una propiedad de la configuración y no un juicio que alguien
tiene que recordar; sin él, es una lista de exclusiones que crece cada vez que
aparece un directorio nuevo. Esto además hace mecánicamente implementable la
regla de cobertura que afirme el otro revisor, sin que él tenga que pedir nada.

#### 2.2 Un módulo del PRD es un módulo del árbol, con el nombre del PRD

> Cada módulo funcional del Segmento 9 (`MOD-01` a `MOD-15`) tiene **un
> directorio propio** bajo el prefijo del aplicativo, nombrado por el módulo y
> no por la capa técnica. Un archivo pertenece a exactamente un módulo. Cuando
> un archivo necesitaría pertenecer a dos, la razón se escribe en el ADR de la
> unit, igual que el PRD ya exige para las units ("ninguna unit cruzará dos
> módulos sin una razón escrita en un ADR", Segmento 9 introducción).

Esto no es preferencia estética: el PRD ya trae quince módulos con features
identificadas (`F<módulo>.<n>`), `units-generation` va a producir units a partir
de ellos y las evals reportan por nodo. Si el árbol se organiza por capa
técnica en vez de por módulo, la trazabilidad de 9.6 deja de leerse en el
sistema de archivos y hay que reconstruirla a mano en cada revisión.

#### 2.3 Los cuatro nodos tienen una sola grafía, en cuatro lugares

> Los nodos del grafo se llaman `intake`, `policy_verification`, `decision` y
> `compliance` (con la convención de mayúsculas y separadores que fije el
> lenguaje, pero con esas mismas palabras y en ese orden). **El mismo token**
> nombra el directorio del módulo, el valor del enum de transición, el nombre
> del span en la traza y la etiqueta por nodo del reporte de evals y del
> dashboard.

El PRD pide costo, latencia y tokens "por caso y por nodo" (M7, F10.1), fallos
por nodo en el dashboard (F10.2) y la ruta recorrida visible en la traza (P3.b).
Si el nodo se llama de una manera en el código y de otra en la traza, cada una
de esas tres promesas exige una tabla de traducción que alguien mantiene a mano
—exactamente el patrón que produjo TD-04 y TD-02 en la landing.

#### 2.4 Tres registros de idioma, declarados una vez

> - **Identificadores, nombres de archivo, enums, campos del esquema, claves de
>   configuración, nombres de tenant (`tenant_id`) y mensajes de log técnico**:
>   inglés.
> - **Todo texto que lee una persona no técnica** (asegurado, ajustador,
>   visitante): catálogo de copy por idioma, español e inglés, nunca en línea.
> - **Artefactos del flujo AI-DLC, comentarios y ADR**: español, según la
>   corrección ya aprendida en `project.md`.

Hay una ambigüedad concreta que esto resuelve y que el desarrollador encuentra
el primer día: el PRD escribe los roles en inglés (`adjuster`, `underwriter`,
`account_agent`, 9.3) pero los estados del caso (F1.3: abierto, en captura, en
verificación, en decisión, derivado, esperando al asegurado, cerrado) y las
categorías de decisión (F6.2: cierre directo, revisión estándar, derivación) en
prosa española. Sin esta regla, la mitad del enum queda en un idioma y la otra
mitad en otro. Con ella:

> Los estados del caso y las categorías de decisión se escriben como enum en
> inglés; la **tabla de correspondencia** entre el término del PRD y el valor
> del enum vive en un solo archivo, junto a la definición del enum. La etiqueta
> que ve una persona se resuelve por el catálogo de copy, nunca imprimiendo el
> valor del enum.

Encaja con lo que el PRD ya decidió: interfaz de la bandeja y del dashboard en
inglés, contenido del caso en el idioma del asegurado (9.4 MOD-08, Paso 0
decisión 9).

#### 2.5 Dirección de dependencias: lo que hace verificable a P3

Esta es la respuesta directa a la segunda pregunta del encargo. P3 prohíbe tres
cosas ("que un LLM decida a qué nodo ir con texto libre", "cualquier acción
sobre el caso fuera de una ruta", "que el grafo dependa del framework de voz") y
`discovered-rules.md` las recoge bien como `NEVER`. Pero una prohibición no se
verifica sola: hace falta la estructura que la vuelve comprobable por
herramienta. Propongo cuatro reglas de importación, todas expresables en
cualquiera de los dos lenguajes (`import-linter` o `flake8-tidy-imports` en
Python; `eslint no-restricted-imports` o `dependency-cruiser` en Node) y todas
grepeables mientras la herramienta no exista:

> 1. **El núcleo no importa canales.** El módulo de orquestación no importa nada
>    de los módulos de voz ni de chat. Los canales importan el núcleo, nunca al
>    revés (P3.c, F2.6).
> 2. **El núcleo no importa proveedores.** El SDK de STT, LLM, TTS o del almacén
>    vectorial se importa únicamente dentro del adaptador de ese proveedor; el
>    núcleo depende de un puerto propio. Sin esto, "proveedores externos
>    intercambiables" (9.2) y los planes B declarados (Whisper por Deepgram,
>    Kokoro por Cartesia) son una intención de documento: el día que haya que
>    cambiar, el SDK está importado en doce archivos.
> 3. **La función de transición es pura y cerrada.** Recibe solo campos del
>    estado tipado y devuelve un valor del conjunto cerrado de nombres de nodo.
>    Ningún cliente de LLM aparece en su cadena de llamadas. Esto es P3.a y
>    P3.c convertido en algo que una prueba y una regla de importación
>    comprueban.
> 4. **El camino del turno no llama al trabajo de fondo.** El manejador de turno
>    de voz no importa ni invoca sincrónicamente Policy Verification, el motor
>    de reglas ni la revisión completa de cumplimiento: lee lo que ya está en el
>    estado (precarga) o emite una frase de espera. P4.a lo dice
>    ("Verificación, reglas y cumplimiento nunca corren dentro del turno") y
>    F2.3 lo diseña; una regla de importación lo hace incumplible por descuido.

Las cuatro juntas son, en mi opinión, lo más valioso que esta etapa puede dejar
escrito hoy, porque son exactamente lo que no se puede añadir después: revertir
una dirección de dependencia a la semana 8 cuesta un Bolt entero.

#### 2.6 Estado tipado: cada nodo declara qué campos escribe

> Cada nodo declara su **conjunto de campos de escritura** sobre el estado
> tipado. El estado se modifica solo por el valor de retorno del nodo; ningún
> nodo muta el objeto compartido en el lugar. Dos nodos no escriben el mismo
> campo.

P3.a ya lo dice en una frase ("los nodos escriben campos distintos") y el
borrador no la recoge. Convertida en convención se vuelve comprobable con una
sola aserción por nodo, y evita el modo de fallo más caro de un grafo con
estado compartido: dos nodos que se pisan un campo y un caso que llega a la
bandeja con datos que nadie escribió a propósito.

#### 2.7 Un solo punto de entrada a la base de datos, y es el que fija el tenant

> Toda consulta del aplicativo pasa por **un único punto de adquisición de
> sesión** que fija el `tenant_id` de la sesión de base de datos antes de
> devolverla. Ningún otro módulo abre una conexión.

F9.1 exige literalmente que "la aplicación fija el tenant de la sesión de base
de datos antes de cualquier consulta", y esa mitad no está en el borrador: la
regla dura de `discovered-rules.md` cubre RLS en la base de datos pero no el
lado del código. La consecuencia es real: con RLS configurada y sin punto de
entrada único, cualquier módulo puede abrir una sesión que nunca fija el tenant
—y entonces, según el rol con que se conecte, o no ve nada (fallo ruidoso, el
caso bueno) o lo ve todo (fuga entre tenants, la fila más grave del mapa FTCEM
de 12.2). Es también la convención que hace que el test de aislamiento de F9.4
pruebe algo: sin punto único, el test verifica la política de una tabla, no el
comportamiento del aplicativo.

#### 2.8 Manejo de errores: cuatro convenciones, todas atadas a una fila del PRD

Esta es la otra mitad de la segunda pregunta del encargo. F2.7 y toda la tabla
de degradación de 12.3 son hoy intención; estas cuatro las vuelven código.

> **(a) Taxonomía cerrada en la frontera del proveedor.** Cada adaptador traduce
> los errores de su SDK a un conjunto cerrado y pequeño que el núcleo entiende:
> `timeout`, `rate_limited`, `unavailable`, `invalid_response`. El tipo de error
> del proveedor no cruza hacia el núcleo.
>
> **(b) La política de fallo de cada nodo es un dato, no un `try` disperso.**
> Cada nodo declara tiempo máximo, reintento único y texto de degradación; un
> ejecutor común aplica la política. Un nodo no captura su propio fallo para
> seguir adelante.
>
> **(c) "No hay cláusula" y "no pude verificar" son valores distintos.** El
> resultado verificado `no encuentro una cláusula que lo cubra` (F5.6) y el
> fallo `no pude verificar` (12.3, fila "Corpus o recuperación caídos") nunca se
> colapsan en el mismo valor del estado, de la traza ni del reporte de evals.
>
> **(d) Ningún camino de error llega al asegurado sin pasar por la guardia de
> salida.** El texto de degradación sale del catálogo de copy (§2.4) y atraviesa
> la guardia de salida por turno de F7.5 como cualquier otro texto.

Justificación de cada una, porque son las que más fácil se discuten:

- **(a)** sin taxonomía, el núcleo no puede distinguir `rate_limited` de
  `unavailable`, y el mapa FTCEM pide justo esa distinción: cuota agotada →
  reintento único con mensaje honesto y evals reprogramadas, **nunca marcadas
  como fallo del agente**; proveedor caído → cambio al plan B por
  configuración. Con la excepción del SDK cruzando hacia arriba, esas dos filas
  del PRD no se pueden implementar.
- **(b)** es F2.7 palabra por palabra, pero como datos. La diferencia es que
  así se puede afirmar que **los cuatro** nodos tienen política —una aserción
  sobre la tabla— en vez de auditar a ojo cuatro cuerpos de función.
- **(c)** es la que más me preocupa del borrador actual. Si los dos casos
  comparten valor, la métrica de "respuestas *no hay cláusula* correctas"
  (F5.6, contada y evaluada; F11.7) se contamina con fallos de infraestructura,
  y la compuerta dura de citación empieza a medir la disponibilidad del corpus
  en lugar de la calidad de la citación. Es corrupción silenciosa de una
  métrica publicada, que es exactamente lo que P5 prohíbe.
- **(d)** es un hueco de frontera concreto: la regla dura del borrador manda
  pasar por `interrupt()` "antes de que cualquier salida afirme cobertura", y el
  texto degradado no afirma cobertura, así que no la dispara. Pero la
  degradación es una ruta de salida al asegurado como cualquier otra, y hoy
  ninguna convención impide que sea la única que se salta la guardia de F7.5.

Añado una quinta, más barata, que cierra el círculo con la telemetría:

> **(e) Un fallo siempre deja rastro doble**: un valor distinguible en el estado
> del caso y un evento en la traza con el nodo, el tipo de error y el intento.
> Un fallo silencioso que deja el caso con aspecto de completo está prohibido
> —es la fila "alucinación bajo latencia del backend" del mapa FTCEM vista desde
> el código.

#### 2.9 Las diferencias entre tenants viven en configuración, no en ramas

> Ningún archivo del aplicativo contiene un `tenant_id` literal fuera del
> cargador de configuración y de las fixtures de prueba. Toda diferencia entre
> tenants —idioma por defecto, voz, reglas, políticas de cumplimiento, corpus,
> póliza de ejemplo— se expresa en la carpeta de configuración versionada del
> tenant (F9.2).

El PRD trae una trampa concreta aquí: F6.3 dice "política de la agencia:
derivación siempre". Es la frase que invita a escribir una rama por Knotwell
dentro de Decision. Si esa rama se escribe, `Decision` deja de ser
"determinista y por reglas" (M5, P1) y el aprovisionamiento de un tenant nuevo
con un comando (F9.6) deja de ser cierto. Es una regla grepeable: buscar los
tres slugs en el árbol del aplicativo.

#### 2.10 Un solo archivo de tareas, y es el contrato entre local y CI

> Toda acción que ejecuta una persona o la CI —arrancar, correr pruebas, correr
> evals, generar datos, aprovisionar un tenant, formatear, analizar— tiene un
> comando nombrado en **un solo archivo de tareas** en la raíz. La CI, cuando
> exista, invoca esos mismos comandos y no mantiene su propia lista en línea.

Dos razones, las dos específicas de este proyecto. Primera: M17 exige "comando
único para correr evals y app" y F11.4 un corredor de un comando; si el comando
vive en el README como prosa, es una promesa, y si vive en un archivo de tareas,
es un archivo. Segunda, y más importante hoy: la CI no existe todavía (D-014 la
manda al intent `infra`, semanas 3 y 4), y el propio `evidence.md` reconoce que
"durante las primeras semanas la rama no protege nada". Con el archivo de
tareas, lo que se ejecuta a mano en la semana 1 es literalmente lo que la CI
ejecutará en la semana 4, sin traducción y sin deriva. `make` sirve igual para
Python y para Node, así que la convención sobrevive al ADR.

### 3. Lo que debe esperar al ADR

#### 3.1 Lo que genuinamente depende del lenguaje

Formatter y su configuración; linter y su conjunto de reglas; comprobador de
tipos; runner de pruebas y su forma de medir cobertura; convención de
mayúsculas y separadores en los identificadores (`snake_case` frente a
`camelCase`); mecánica del árbol (paquete con `src`-layout frente a workspace);
herramienta concreta que impone las reglas de importación de §2.5; gestor de
dependencias y formato del lockfile.

Todo eso se nombra como obligación hoy —como ya hace el borrador— y se
materializa en el commit de §4.1.

#### 3.2 Lo que el ADR tiene que traer para que estas prácticas sean aplicables

Un ADR que diga solo "Python" o solo "Node" deja `practices-discovery` sin
aterrizar. Para que el commit de §4.1 sea escribible, el ADR de `domain-design`
tiene que fijar además, en la misma decisión: **versión del runtime** (hoy no
hay `.nvmrc` ni `.python-version`), **gestor de dependencias y formato del
lockfile**, y **comprobador de tipos**, porque §2.6 (estado tipado con conjunto
de escritura por nodo) y §2.8(a) (taxonomía cerrada) presuponen que hay tipos
que alguien comprueba. Lo señalo como requisito sobre esta práctica, no como
instrucción al arquitecto: si el ADR no los trae, `## Code Style` queda
bloqueada un segundo turno.

#### 3.3 Lo que deliberadamente no propongo

- **Nada de arquitectura hexagonal completa.** Puertos y adaptadores solo donde
  el PRD ya prometió sustituibilidad: proveedores externos y canales. En el
  resto, llamada directa. Con una persona y 90 días, la ceremonia se paga cada
  día y se cobra una sola vez.
- **Ningún límite numérico de tamaño de función o de archivo.** `org.md` dice
  que la sugerencia del agente solo aplica si el linter no lo cubre ya, y esos
  límites son valores por defecto de cualquier linter. Inventar los nuestros
  sería ruido.
- **Ninguna regla de renombrado propia** más allá de §2.3 y §2.4, que no son
  estilo sino contrato con la traza, las evals y el PRD.

### 4. Correcciones puntuales al texto del borrador

#### 4.1 `## Code Style`, párrafo 1: "configurados en la raíz del repositorio" va a fallar tal como está escrito

Texto actual: *"Adoptamos el formatter y el linter del lenguaje elegido,
configurados en la raíz del repositorio, corriendo en CI y bloqueando el merge
cuando fallan."*

El problema es concreto. Si el ADR elige Node, un linter configurado en la raíz
sin alcance declarado intentará analizar `.claude/` (91 archivos `.ts` del
engine, que no son nuestros) y el JavaScript inline de `site/index.html` (fuera
del alcance por D-005 y D-013). El resultado es una compuerta en rojo el primer
día por código que no escribimos, o una carrera de exclusiones improvisadas en
el peor momento. El mismo riesgo, menor, existe con Python y `review/`.

Redacción propuesta:

> Adoptamos el formatter, el linter y el comprobador de tipos del lenguaje
> elegido. Su configuración vive en la raíz del repositorio y **declara su
> alcance en el mismo commit en que se crea**: el prefijo del aplicativo, y solo
> ese. `site/`, `.claude/`, `aidlc/`, `docs/` y `review/` quedan fuera por
> construcción, no por una lista de excepciones que crece. Los tres se invocan
> por el archivo de tareas (§2.10), corren en CI cuando la CI exista y bloquean
> el merge cuando fallan; hasta entonces corren en local con el mismo comando.

#### 4.2 Inconsistencia entre los dos artefactos: "mismo Bolt" frente a "primer commit"

`team-practices.md` dice que la configuración de estilo "entra en el mismo Bolt
que el primer código de aplicación"; `discovered-rules.md` exige manifiesto,
lockfile y toolchain "desde su primer commit". Para una persona, un Bolt es una
semana. Propongo alinear ambos en el commit:

> El **mismo commit** que introduce el primer archivo de código del aplicativo
> introduce también: manifiesto y lockfile, configuración de formatter, linter y
> tipos con su alcance declarado, archivo de tareas, y el esqueleto de
> directorios por módulo. No hay un commit intermedio con código y sin
> andamiaje.

Es el único momento barato: TD-09 dice que no hay nada que heredar, y la deuda
de andamiaje se paga a precio de refactor a partir del segundo día.

#### 4.3 `## Way of Working`: falta una línea sobre qué se revisa cuando no hay revisor

El párrafo diagnostica bien que "la rama existe para que la CI mire el código
antes que `main`". Le falta la consecuencia para el código: con un solo
integrante, lo que sustituye a la revisión por pares en las convenciones de
código no es la disciplina, es que **la convención sea comprobable por
herramienta**. Propongo cerrar el párrafo con:

> Por eso toda convención de código que afirmemos tiene que ser comprobable por
> una herramienta o por un grep. Una convención que solo se sostiene en la
> memoria del autor no es una práctica del equipo: es una intención, y a la
> semana seis no está.

#### 4.4 `## Code Style`, último párrafo: la lección de TD-02 está a medias

El borrador recoge el chequeo de paridad de claves entre español e inglés, pero
no la convención que lo hace significativo. Un chequeo de paridad sobre un
catálogo pasa siempre si la mitad de las cadenas está escrita en línea en el
código: no hay nada que comparar. TD-02 (la clave `hud1` sin consumidor) y TD-01
(el copy duplicado entre `design-package.md` y el diccionario `I18N`) son el
mismo fallo visto dos veces. Propongo añadir:

> Todo texto dirigido a una persona sale del catálogo de copy por idioma, con
> un solo espacio de claves: apertura con divulgación, frases de espera, frases
> de derivación, mensajes de degradación y de error, etiquetas de la bandeja.
> Ninguna cadena visible se escribe en línea en un nodo o en un adaptador. La
> paridad EN↔ES y las claves sin consumidor se comprueban sobre ese catálogo.

#### 4.5 Consecuencia de código de las llaves separadas por uso

El borrador exige llaves separadas por uso (voz, chat, evals), que es del
revisor de seguridad. Anoto solo su consecuencia estructural, que sí es mía:
esas tres llaves son un hecho del entorno hasta que el código las respeta. Para
que lo haga, **el cliente del proveedor se construye en un único lugar por uso**
(una fábrica que recibe el uso y devuelve el cliente ya configurado). Si
cualquier módulo construye su propio cliente, toma la llave que encuentre, y el
enlace público del chat empieza a consumir el tope de 5 USD de la voz —que es
exactamente lo que 9.4 MOD-04 decidió evitar.

### 5. Reglas duras propuestas para `discovered-rules.md`

Todas con el formato del archivo y con fuente dura. Las tres primeras son
enmiendas a reglas existentes; las cuatro últimas son nuevas.

**Enmienda a la regla de RLS** (hoy cubre solo el lado de la base de datos):

- ALWAYS aislar por `tenant_id` con Row Level Security en la base de datos, no solo en el código, **y fijar el tenant de la sesión de base de datos en un único punto de entrada por el que pasa toda consulta del aplicativo**; ningún otro módulo abre una conexión. Cada tabla nueva llega con su test de aislamiento. *(M9, F9.1, F9.4, R8, PRD 12.2)*

**Enmienda a la regla de redacción de PII** (para que "cada punto de salida" sea una lista cerrada y no un juicio):

- ALWAYS redactar los datos personales en cada punto de salida —transcripción parcial y final, logs, trazas, exportaciones y reporte de evals—, **y declarar esos puntos de salida en un solo lugar del código**, de modo que añadir uno nuevo sea un cambio visible en ese archivo. *(M6, P6, F7.3, RT-14)*

**Enmienda a la regla de manifiesto y lockfile** (para fijar el alcance desde el inicio):

- ALWAYS crear el código de aplicación con manifiesto, lockfile y toolchain fijados desde su primer commit, **y con la configuración de formatter, linter y tipos declarando su alcance al prefijo del aplicativo en ese mismo commit**. *(TD-09; `dependencies.md`, riesgo 3)*

**Nuevas**:

- ALWAYS decidir la transición entre nodos en código: una función que recibe solo campos del estado tipado y devuelve un valor de un conjunto cerrado de nombres de nodo, sin ningún cliente de LLM en su cadena de llamadas; el módulo de orquestación no importa canales ni SDK de proveedores. *(P3, M2, F2.1, F2.6, R10)* — no sustituye a la regla `NEVER` de P3 que ya está en el archivo: la hace verificable.
- ALWAYS distinguir el resultado verificado "no encuentro una cláusula que lo cubra" del fallo "no pude verificar": son dos valores distintos en el estado, en la traza y en el reporte de evals, y nunca se colapsan en uno. *(M4, F5.6, P5, PRD 12.3)*
- ALWAYS declarar la política de fallo de cada nodo como dato —tiempo máximo, un reintento, texto de degradación— aplicada por un ejecutor común; un nodo no captura su propio fallo para continuar, y todo fallo deja un valor distinguible en el caso y un evento en la traza. *(M2, F2.7, PRD 12.2, 12.3)*
- ALWAYS hacer pasar por la guardia de salida todo texto que llegue al asegurado, incluidos los caminos de degradación y de error, y emitirlo desde el catálogo de copy por idioma. *(M6, F7.5, P1, P12)*
- NEVER escribir un `tenant_id` literal en el código del aplicativo fuera del cargador de configuración y de las fixtures: las diferencias entre tenants viven en su carpeta de configuración versionada, incluida la política de derivación siempre de la agencia. *(M9, F9.2, F9.6, F6.3)*
- NEVER importar el SDK de un proveedor externo (STT, LLM, TTS, almacén vectorial) fuera de su adaptador, ni construir su cliente fuera de la fábrica que separa las llaves por uso. *(P3, P9, M20, PRD 12.2 "proveedor de voz caído", plan B de plataforma en `pvb.md` §7)*

### 6. Ajuste a `evidence.md`

**Q6 se queda corta.** Tal como está redactada, sus tres opciones son "afirmar
la obligación sin la herramienta", "decidir el lenguaje ahora" y "no decidir
nada". Ninguna pregunta por lo que sí se puede decidir hoy, así que la respuesta
más probable (A) deja fuera §2.1 a §2.10 y esas decisiones no caen en ninguna
etapa: `domain-design` decide tecnología, no organización de archivos. Propongo
enmendar la recomendación de A para que incluya explícitamente el bloque
independiente del lenguaje, y añadir a la pregunta una sola sub-elección real
—la única de §2 que tiene alternativa legítima y consecuencia visible:

> **Sub-pregunta de Q6 — dónde vive el código del aplicativo.** El repositorio
> ya tiene `site/`, `docs/`, `.claude/` y `aidlc/` en la raíz. ¿El código del
> aplicativo cuelga de **un solo directorio de primer nivel** (todo el tooling
> apunta a un prefijo), o se reparte en varios directorios de raíz según el
> lenguaje lo sugiera?
>
> - `A.` Un solo directorio de primer nivel, decidido ahora; el nombre y la
>   mecánica interna los fija el ADR.
> - `B.` Se decide con el ADR de lenguaje, junto con el resto del árbol.
> - `X. Other (please specify)`
>
> **Recomendación: A.** Es lo que hace que "la landing no entra en el piso de
> cobertura" sea una propiedad de la configuración en vez de una lista de
> exclusiones, y no compromete nada de lo que el ADR tiene que decidir.

No propongo una séptima pregunta: seis ya son muchas para una sola persona, y
todo lo demás de §2 se deriva del PRD sin que haya alternativa que ofrecer.

**"Lo que la evidencia no puede decidir"** gana un punto 6: *la organización del
árbol del aplicativo y el alcance de las herramientas de estilo. No depende del
ADR de lenguaje (el invariante es un prefijo), pero sí de una decisión que nadie
ha tomado todavía.*

**Un supuesto que hay que declarar** y hoy no está: el borrador asume que las
convenciones de código se pueden diferir enteras al ADR. Mi lectura es la
contraria —la herramienta se difiere, la frontera no— y si el lead la comparte,
conviene registrarla como supuesto revocable en vez de dejarla implícita.

### 7. Frontera con los otros dos revisores

Tres líneas, sin desarrollar:

- **Posture de pruebas, cobertura y compuertas de CI**: del otro revisor. Solo
  dejo dicho que §2.1 (un prefijo) hace que el piso de cobertura sea
  configurable sin lista de exclusiones, y que §2.8(a) y §2.8(c) son
  precondición de dos métricas que el PRD publica —si el tipo de error no llega
  al reporte, las evals reprogramadas por cuota se cuentan como fallos del
  agente, contra lo que manda el mapa FTCEM.
- **Elección del linter, SAST, secretos y cadena de suministro**: del revisor de
  seguridad. Mi único cruce es §4.5: llaves separadas por uso solo se sostiene
  si el cliente se construye en un único lugar.
- **Qué debe fijar el ADR de lenguaje** (§3.2) toca al arquitecto; lo enuncio
  como condición para que esta práctica sea aplicable, no como instrucción de
  diseño.

## Positions

- AGREE: nombrar la obligación y no la herramienta mientras el lenguaje no esté elegido — es la única forma de que la práctica escrita hoy siga siendo verdad mañana, y el borrador la aplica con consistencia.
- AGREE: manifiesto, lockfile y toolchain fijados desde el primer commit del aplicativo — con TD-09 diciendo que no hay nada que heredar, es la única ventana en que el andamiaje es gratis.
- AGREE: la landing no es estándar ni insumo de diseño del aplicativo (D-005, D-013) — y, bien organizado el árbol, deja de ser siquiera una excepción que alguien tiene que recordar.
- AGREE: los comentarios y la documentación describen lo construido, con TD-03 como ejemplo local de lo contrario — barato, concreto y con evidencia en el propio repositorio.
- OBJECT: `## Code Style` no dice nada sobre organización de archivos, fronteras entre capas ni manejo de errores — son tres de las cinco cosas que deciden si P3 y F2.7 son código o intención, y ninguna depende del lenguaje elegido (§2.1 a §2.10).
- OBJECT: "formatter y linter configurados en la raíz del repositorio", sin alcance declarado, va a analizar `.claude/` y el JavaScript inline de `site/` — la compuerta se pone en rojo el primer día por código que no escribimos (§4.1).
- OBJECT: la regla dura de aislamiento cubre RLS en la base de datos pero omite la mitad que F9.1 exige del código —fijar el tenant de la sesión en un único punto de entrada— y sin ella el test de aislamiento prueba la política de una tabla, no el comportamiento del aplicativo (§2.7).
- OBJECT: nada distingue "no hay cláusula" (resultado verificado, contado y evaluado) de "no pude verificar" (fallo de infraestructura), y colapsarlos contamina una métrica publicada, que es justo lo que P5 prohíbe (§2.8c).
- OBJECT: ninguna convención impide que el camino de degradación sea la única salida al asegurado que se salta la guardia de F7.5, porque no afirma cobertura y por tanto no dispara la regla de `interrupt()` (§2.8d).
- OBJECT: falta la regla que impide ramas por tenant en el código; F6.3 ("la agencia deriva siempre") es precisamente la frase que invita a escribir un `if` por Knotwell dentro de Decision y a romper M5 y F9.6 (§2.9).
