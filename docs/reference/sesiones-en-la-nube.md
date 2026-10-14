# Sesiones en la nube de Claude Code

Cómo se usa el crédito de sesiones en la nube para construir este proyecto, qué
trae esa máquina y qué no, y cómo se reparte el trabajo con la sesión local para
que dos agentes no se pisen.

Escrito el 2026-09-24, después de medir el entorno con dos sesiones de
diagnóstico.

## Qué es y para qué lo usamos

Una sesión en la nube es Claude Code corriendo en un contenedor de Anthropic, no
en la máquina de Miguel. Clona el repositorio en una rama propia (`claude/...`),
trabaja aunque el portátil esté cerrado y empuja su rama a GitHub.

El crédito de 250 USD (reclamado el 2026-09-24, **vence el 5 de noviembre**) se
gasta solo ahí y no toca el límite semanal del plan mientras quede saldo; cuando
se agote, esas sesiones vuelven a consumir del plan. El saldo se mira en la
ventana del crédito de claude.ai; no hay forma de consultarlo por programa, así
que se anota a mano en el registro de abajo.

**Qué se manda a la nube:** las tandas de código de una unidad, escritas por
Sonnet con un encargo cerrado. Sirve para unidades que no llaman a ningún
proveedor (U9, U11, U12, U21).

**Qué se queda en la sesión local:** el diseño, las compuertas de aprobación, la
revisión del código, todo lo que necesita base de datos, `mise run cov`,
`scripts/verify.sh`, el flujo AI-DLC (`aidlc` es un binario de macOS) y cualquier
unidad que necesite claves de proveedor. Las claves **no salen de la máquina de
Miguel**: el editor del entorno advierte que sus variables son visibles para
quien use ese entorno.

## Qué trae el contenedor

Medido el 2026-09-24 en el entorno `Cloud environment`:

| Hay | No hay |
| --- | --- |
| `curl`, `git`, `python3` (3.13.12) | **Docker**: el cliente existe, el demonio no corre |
| `uv` (0.8.17 de fábrica), `pnpm` y `node` 22 | **mise**: no se puede instalar (ver la red) |
| El repositorio clonado en `/home/user/untangle` | **aidlc**: es un binario de macOS |
| Usuario `root`, con `/root/.local/bin` en el PATH | |

**La red está restringida por política del entorno.** Solo responden
`pypi.org` y `registry.npmjs.org`. `mise.jdx.dev` lo rechaza el proxy de salida
("connect_rejected", 403 en el túnel) y `github.com` no devuelve descargas
útiles. Por eso no hay mise: su instalador no se puede descargar. Se puede
ampliar en el editor del entorno → "Acceso a la red", agregando `mise.jdx.dev`,
`github.com` y `objects.githubusercontent.com` a los dominios permitidos;
mientras eso no pase, se trabaja sin mise.

**El `uv` de fábrica es viejo y reescribe el lockfile.** Con 0.8.17,
`exclude-newer = "3 days ago"` (una fecha relativa, deliberada, SEC-U1.4) no
parsea, así que descarta el corte temporal y vuelve a resolver. No es un defecto
del repositorio: el `uv` que fija `mise.toml` (0.12.16) lo entiende. En la nube
se corrige al empezar, desde PyPI, que sí está permitido:

```bash
uv tool install --force uv==0.12.16
```

## Los comandos, sin el archivo de tareas

Sin mise no hay `mise run`. Estos son los mismos pasos, invocados a mano desde la
raíz del repositorio:

| Qué | Comando |
| --- | --- |
| Dependencias | `uv sync --locked --project app/backend --all-groups` |
| Pruebas de una unidad | `uv run --project app/backend pytest -c app/backend/pyproject.toml app/backend/tests/unit/<modulo>` |
| Formato | `uv run --project app/backend ruff format app/backend` |
| Lint | `uv run --project app/backend ruff check app/backend` |
| Contratos de importación | `uv run --project app/backend lint-imports --config app/backend/.importlinter --cache-dir tmp/import-linter` |
| Tipos | `uv run --project app/backend mypy --config-file app/backend/pyproject.toml` |
| Catálogo de textos | `uv run --project app/backend python -m untangle.copy_catalog.checks` |
| Esquemas | `uv run --project app/backend python -m untangle.workspace.schema_check` |

Lo que **no** corre allá: `tests/integration`, cobertura, evaluaciones y
`scripts/verify.sh`, porque todos necesitan la base de datos en contenedor.

## Cómo se reparte el trabajo sin pisarse

Un solo dueño por rama, y la compuerta sigue siendo GitHub Actions sobre `main`.

1. La sesión local escribe el encargo y lo pega en la sesión de la nube. El
   encargo señala los documentos del repositorio; la nube no comparte la memoria
   de la conversación local, y no la necesita, porque lo decidido está escrito.
2. Mientras la tanda corre, **la sesión local no toca los archivos de esa
   unidad**. Puede escribir documentación o registro del flujo, nada más.
3. La nube hace commit **en su rama** y la empuja. Nunca a `main`.
4. La sesión local trae la rama (`git fetch origin`), revisa el cambio contra el
   diseño, corre las compuertas completas y lo lleva a `main` en un solo commit
   con la práctica de tronco de siempre.
5. Si `main` avanzó mientras tanto, la rama se reordena sobre `main` antes de
   revisar, para que lo que se mide sea lo que va a quedar.

Esta rama de la nube es el mismo dispositivo mecánico que el worktree de un Bolt
(`team.md`, "Way of Working"): aísla el trabajo, no introduce revisión por pares
ni pull request.

## Registro del crédito

Se anota el saldo antes y después de cada tanda. Con dos tandas medidas se sabe
cuántas caben en lo que queda.

| Fecha | Para qué | Saldo después |
| --- | --- | --- |
| 2026-09-24 | Cuatro sesiones de diagnóstico del entorno y de la red | ~246 USD de 250 |
| 2026-09-24 | U9, tanda 2 (pasos 6 y 7), con Sonnet | **235 USD de 250** |
| 2026-09-26 | U21, tandas 1 y 2, las dos en la misma sesión de la nube | **190 USD de 250** |
| 2026-09-27 | U8, tanda 1 (migración, los 40 casos de DS-3 e ingesta), sesión limpia | ~145 USD de 250 |
| 2026-09-27 | U8, tanda 2 (correcciones, recuperación y verificador), sesión limpia | 130 USD de 250 |
| 2026-09-27 | U8, tanda 3 (uso `corpus`, nodo y respaldo), sesión limpia | **103 USD de 250** |
| 2026-09-27 | U11, tandas 1 y 2, cada una en sesión limpia | **54 USD de 250** |
| 2026-09-30 | U22, tanda 1 (las cinco cifras y su panel), sesión limpia | **48 USD de 250** |
| 2026-09-30 | U22, tanda 3 (el README que se regenera y su chequeo), sesión limpia | **37 USD de 250** |
| 2026-09-30 | U22 tanda 4, y las tandas 1 de U19, U23, U17 y U20: **cinco sesiones limpias** | **4 USD de 250** |

**Lo que enseñó U21:** sus dos tandas juntas costaron 45 USD, cuatro veces la de
U9, porque corrieron en la misma sesión con la ventana ya al 70 % de 1M y cada
mensaje vuelve a pagar lo acumulado. De ahí la regla que sigue vigente: **una
sesión de la nube por tanda**, nueva cada vez.

**Lo que enseñó U8, que corrige la estimación anterior:** una sesión limpia no
cuesta 11 USD fijos, cuesta lo que pese la tanda. Sus dos primeras tandas, las
dos en sesión nueva, costaron 60 USD entre las dos: unos **45 la primera** y
**15 la segunda**. La primera no escribió más código que la segunda — escribió
menos — pero tuvo que **leer el corpus entero** para sacar los identificadores
reales de las 40 preguntas de DS-3: 414 cláusulas repartidas en decenas de
archivos JSON. Lo que cuesta no es escribir código, es leer datos.

**Consecuencia práctica:** cuando una tanda necesite buscar algo dentro de
`app/data/` o de otro árbol de datos grande, el encargo le dice que lo consulte
con un guion corto y mire solo lo que ese guion devuelva, en vez de abrir los
archivos uno por uno.

Las tres tandas de U8 costaron **87 USD**: 45, 15 y 27. La primera fue la cara
por leer el corpus entero; las otras dos, que escribieron mucho más código,
costaron menos de la mitad entre las dos.

**Lo que costó U11:** 49 USD entre sus dos tandas. Y esa cifra hay que leerla con
lo que la revisión encontró: la tanda 2 volvió con seis defectos, dos de ellos en
compuertas duras, y **sin el nodo** —sin la especificación ni el punto de entrada
que su propio diseño prometía—, que hubo que escribir aquí. El crédito no compró
una unidad terminada; compró un borrador caro.

**Lo que enseñó U22, y corrige otra vez la estimación:** su tanda costó **6 USD**,
la más barata del proyecto, y escribió 2.500 líneas entre servidor, pantalla,
catálogo y pruebas. Ni la más barata ni la más cara tienen que ver con cuánto
código se escribe. Las dos caras —U8 con 45 y U11 con 30— tuvieron que **buscar**:
una leyó el corpus entero y la otra fue a entender un nodo que ya existía. Esta no
buscó nada, porque el encargo traía la lista de archivos que hacía falta leer y en
qué orden.

**La regla que sale de ahí:** lo que cuesta no es escribir, es leer. Un encargo que
nombra los archivos —los de diseño y los del código— cuesta una fracción de uno que
dice "mira cómo funciona X". Con 37 USD y este precio caben muchas tandas, pero
solo si se escriben así.

**Lo que enseñó la tanda 3 de U22:** costó **11 USD**, casi el doble de la tanda 1
con la mitad de código (1.225 líneas frente a 2.500). La diferencia no está en lo
que escribió: está en que **tuvo que buscar algo que el encargo no le dio**. El
encargo mandaba agrupar los fallos por causa raíz leyendo la línea base, y la línea
base no guardaba la causa raíz; la sesión tuvo que recorrer el corredor, el reporte y
la compuerta para entender de dónde salía, preguntar, y añadir un campo a otra
unidad. Once dólares por una respuesta que el diseño debía traer resuelta.

**La regla se afina:** el encargo no solo nombra los archivos, también **comprueba
que el dato que pide existe donde dice**. El precio de no comprobarlo se paga dos
veces: en la tanda que busca y en la que hay que añadir después (aquí, una tanda 4).

**Y la medida final, del 2026-09-30:** cinco sesiones —la tanda 4 de U22 y las cuatro
tandas 1— costaron **33 USD entre todas**, unos **6,6 cada una**, y escribieron más de
quince mil líneas. Son las más baratas del proyecto y la confirmación de la regla: las
cinco llevaban encargo con su lista de archivos y su orden de lectura. Comparadas con los
45 de la primera tanda de U8, que tuvo que buscar, la diferencia es de casi siete veces.

**Queda 4 USD**, así que no cabe otra sesión. No bloquea nada: las cuatro tandas 2 que
faltan son locales por diseño, porque todas necesitan base de datos. El crédito vence el
5 de noviembre y lo que no se gaste se pierde; si apareciera trabajo de dato y lógica pura
antes de esa fecha, cabe una sesión corta y nada más.

## Qué pasa cuando se acabe el crédito, medido el 2026-09-30

Las sesiones de la nube dejan de gastar del crédito y **vuelven a consumir del plan**.
No se renueva nada, no se recarga nada y **no hay cobro por exceso**: el uso adicional
está desactivado en la cuenta. Cuando el límite semanal se llena, el trabajo **se pausa
hasta el reinicio**; no se factura. Eso es consistente con la regla del proyecto de que
ninguna cuenta queda con recarga automática ni cobro de excedentes.

**Y el número que decide cómo usar el crédito no es el saldo.** Medido el 2026-09-30:

| | Valor |
| --- | --- |
| Límite semanal, todos los modelos | **70 % usado**, reinicio el sábado 4 de octubre |
| Ventana de 5 horas | 6 % |
| Uso adicional | desactivado |

**Esto corrige el razonamiento del 2026-09-27**, que midió el semanal en **4 %** y
concluyó que el límite ya no era el cuello de botella. Tres días después está en 70 %, y
la conclusión se da la vuelta: los 37 USD de crédito **no son el presupuesto escaso, son
el único que no sale del 30 % que queda de la semana**.

De ahí la forma correcta de gastarlos, que es la contraria a ahorrarlos: **cada tanda que
corre en la nube es una que no se come la semana**. Lo que se queda en local —las
revisiones y las tandas que necesitan base de datos— compite con el mismo 30 %, así que
se paga dos veces la costumbre de reconstruir en el informe el razonamiento entero de una
revisión.

## Dos trampas del entorno que ya costaron tres sesiones

**1. El clon viejo.** Una sesión de la nube arranca con una copia del repositorio tomada
cuando se creó, no cuando empieza a trabajar. Tres sesiones han concluido que sus
documentos de diseño "no existen" cuando estaban en `main` desde hacía una hora. El
encargo lo dice ahora en su primera línea: `git fetch origin` y comprobar que la rama
desciende del commit que trae los documentos, **antes** de leer nada.

La forma del error engaña, y por eso cuesta: la sesión no falla, razona bien y llega a
una conclusión falsa —"los documentos quedaron sin commitear en la máquina local"— que
suena plausible. Y hace lo correcto: se detiene en vez de inventar.

**2. Las descargas de GitHub.** `mise` baja Python 3.13.15 y los modelos de spaCy desde
las descargas de GitHub, que resuelven a `objects.githubusercontent.com`. Ese dominio es
el que el túnel rechaza, y es **uno solo para los dos problemas**: sin él no hay Python
anclado y no hay modelos, así que `deps:install` y `models:install` fallan los dos.

PyPI y npm sí alcanzan. Las tres sesiones que lo encontraron se apañaron distinto: una
instaló 3.13.15 con `uv`, otra usó el 3.13.14 del sistema con el lockfile. Las dos
corrieron los comandos de `mise.toml` directamente, y las dos lo anotaron, que es lo que
se pide: **una versión de Python distinta es un dato de la corrida, no un detalle.**

Los modelos no tienen apaño: sin ellos, las pruebas de redacción quedan rojas con
`ModelsMissingError`. **No se arreglan tocando el código**, y el encargo ahora lo dice
para que nadie lo intente.

## Lo que alcanza el saldo, y la decisión del 2026-09-27

Con **4 USD** (2026-09-30, después de las cinco últimas sesiones) **no cabe otra
sesión**. Y no bloquea nada: las cuatro tandas 2 que faltan son locales por diseño. La aritmética sigue sin admitir lectura optimista
—el crédito no alcanza para todo lo que queda—, pero la horquilla cambió mucho desde
que los encargos nombran los archivos: la estimación de 15 a 45 por tanda era de
antes de eso.

**Y lo que va a la nube ya no son unidades enteras, es la mitad de cada una**
(2026-09-30, al leer U19 y U23): la mitad de dato y lógica pura —esquemas, reglas
versionadas, detectores, pantallas con respuestas declaradas— se encarga; la que
necesita base de datos, proveedores o el arnés se queda aquí.

Pero el dato que cambia la decisión es otro. **El motivo por el que el código se
fue a la nube ya no se cumple.** La enmienda de DP-13, del 2026-09-22, lo dice con
esas palabras: *"el cuello de botella pasó a ser el límite semanal de uso"*. Hoy,
tras una sesión larga en la que se construyó el nodo de captura de U11, el control
de licencias, dos etapas completas de U12 y la revisión entera de una tanda, el
límite semanal del plan está en **4 %** y la ventana de cinco horas en **12 %**.

Así que desde el 2026-09-27 **la generación de código vuelve al agente
desarrollador del propio flujo**, despachado desde la sesión principal con Sonnet.
Es lo que la etapa `code-generation` declara —`mode: subagent`, `lead_agent:
aidlc-developer-agent`— y lo que la enmienda de DP-13 decidió: el agente que
escribe el código usa Sonnet, las tandas son más cortas y la sesión principal
revisa cada una antes de subirla.

El crédito que queda se reserva para lo que la nube hace mejor: una tanda larga y
mecánica que se pueda encargar de una sola vez. Lo que cambia es **dónde corre el
desarrollador**, no quién decide: el diseño, el plan, la revisión y el commit
siguen aquí, y **no cambia ninguna compuerta, ni el piso de cobertura, ni el ritual
de aprobación del plan**. Se revierte el día que el límite semanal vuelva a ser el
cuello de botella, que es lo único que justificaba la nube.

**Corrección del mismo día, y conviene que quede escrita porque fue un error de la
sesión principal:** los dos primeros pasos de U12 se escribieron inline, sin
despachar al agente desarrollador. Funcionó, pero gasta el modelo caro en escribir
código que Sonnet escribe igual de bien bajo revisión, y se salta la topología que
la etapa declara. Lo notó Miguel antes que yo.

### Para qué se reserva lo que queda: completar DS-2 hasta sus 60 conversaciones

Decidido el 2026-09-27, después de buscarlo a propósito. El PRD pide **60
conversaciones (30 por idioma)** en el golden set de texto y hoy hay **34**: faltan
**trece casos, en los dos idiomas**. Es el único trabajo pendiente que cumple las
cuatro condiciones a la vez:

- **Largo y mecánico.** Veintiséis archivos con un esquema ya fijado y quince
  ejemplos delante.
- **Leer mucho y decidir poco.** Hay que leer las pólizas de las tres
  aseguradoras, la guía de voz y tono, las reglas de normalización y los casos que
  ya existen, y de ahí sale cada archivo. Leer es justo lo que esa sesión hace bien
  y lo que aquí cuesta contexto.
- **Sin base de datos y sin proveedor.** Son archivos de datos; el corredor los
  mide con sondas deterministas.
- **Se encarga de una vez.** Un solo encargo, con un criterio de cierre que se
  comprueba solo: `mise run evals:run` lista 60 casos de DS-2, el chequeo de
  esquema pasa y el manifiesto cuadra.

**Los ejes que faltan** los nombra el propio PRD y no hay que inventarlos: campo
difícil (placa, fecha relativa, lugar ambiguo), corrección a mitad del relato,
idioma mixto y canal de voz transcrita. Los de esta lista que dependen de la
conducta de U12 —pregunta de cobertura durante el reporte, llamada cortada y
reanudación— se escriben aquí, con la unidad delante.

**Lo que hay que construir antes de encargarlo, y va aquí:** una sonda genérica que
recorra el guion de una conversación por los nodos reales y compruebe lo que el
caso declara. Sin ella, cada caso nuevo necesitaría su propia sonda, que es
precisamente el trabajo de juicio que esa sesión hace peor. Con ella, el encargo es
volumen sobre un arnés que ya corre.

**Si llega el 5 de noviembre y el arnés no está**, el crédito se vence sin gastarse,
y está bien: vencerse cuesta menos que comprar un borrador que había que reescribir.

Hay una segunda razón, y conviene decirla porque se ve en el registro de arriba:
las cuatro últimas tandas de la nube volvieron cada una con al menos un defecto
que solo vio la revisión, y buena parte de ellos solo aparecen con base de datos
delante o en la primera llamada real al proveedor —que es justo lo que esa sesión
no tiene. Escribir aquí no es solo más barato: es escribir donde se puede
comprobar.
