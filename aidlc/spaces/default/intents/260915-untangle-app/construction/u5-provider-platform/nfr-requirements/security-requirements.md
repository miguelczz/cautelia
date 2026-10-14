# Requisitos de seguridad — U5 `provider-platform`

**Fuentes consumidas.** `../functional-design/functional-spec.md` (los dos
ciclos de vida y los siete flujos), `../functional-design/rules.md` (las 53
reglas, en especial BR1, BR2, BR4, BR5 y BR7),
`../../../inception/requirements-analysis/requirements.md` (FR3.9 a FR3.11,
FR4.6, FR10.1 a FR10.5, NFR11, NFR14, NFR15),
`../../../inception/contract-design/contract-summary.md` (C-16, C-17 y C-23,
las tres superficies de esta unidad; C-08, los límites de la voz; C-13, la
redacción; C-11, el borrado), `../../../../codekb/untangle/technology-stack.md`,
y las cinco respuestas de `nfr-requirements-questions.md`.

U5 es la única unidad cuyo fallo no produce un error: produce una factura. Un
corte que no corta no rompe ninguna pantalla, no levanta ninguna excepción y no
hace fallar ninguna prueba de funcionamiento. Se nota cuando llega el cobro, y
para entonces el dinero ya se gastó.

Por eso el peso de este documento está en tres sitios: **que las claves estén
separadas y cada una acotada en su proveedor**, **que el techo corte de verdad
aunque falle lo que hay alrededor**, y **que las tres tablas que salen del
aislamiento por aseguradora no puedan ganar un dato personal sin que algo falle
en rojo**.

## Qué puede salir mal

| Categoría | Cómo se materializa aquí | Controles |
| --- | --- | --- |
| Suplantación | Un visitante marca su llamada como grabación y se come la reserva del video final, que no se puede volver a grabar cuando el presupuesto se acabó | SEC-U5.9, SEC-U5.10 |
| Divulgación de información | Una clave de proveedor aparece en un log de arranque, en un mensaje de error o en un tramo de traza | SEC-U5.1, SEC-U5.2, SEC-U5.14 |
| Divulgación de información | Un dato personal sale hacia el backend de trazas porque un tramo llevaba el texto del asegurado sin redactar | SEC-U5.11, SEC-U5.12 |
| Divulgación de información | Un resumen de traza se le muestra a un navegador que no lo produjo, y ese visitante lee lo que preguntó otro | SEC-U5.13 |
| Elevación de privilegio | Una de las tres tablas excluidas del aislamiento gana una columna con un dato personal, y la exclusión pasa de ser un cambio de control a ser un agujero | SEC-U5.6, SEC-U5.7 |
| Denegación de servicio, contra el bolsillo | Un solo visitante agota el cupo del sitio, o abre diez llamadas a la vez porque el contador se consume al terminar | SEC-U5.3, SEC-U5.4 |
| Denegación de servicio, contra el proyecto | La base no responde y las llamadas de pago siguen pasando porque el corte falla abierto | SEC-U5.5 |
| Manipulación | Una llamada consume presupuesto y no deja fila, o deja una fila con el carril o la marca de facturable cambiados, y el acumulado se separa de la realidad | SEC-U5.8, SEC-U5.15 |
| Repudio | Un tope del proveedor se da por puesto sin que nadie lo haya mirado, y nadie puede decir cuándo se comprobó | SEC-U5.2 |
| Inyección | El texto del asegurado llega al proveedor concatenado al prompt de sistema en vez de como campo delimitado | SEC-U5.16 |

## Objetivos medibles

Cuatro filas, cada una con su valor esperado y el comando que produce su valor
real. Van a la matriz de verificación de `build-and-test` tal cual.

**Solo cuatro, y a propósito.** U5 es dueña de tres metas de Incepción —NFR11,
NFR14 y NFR15— y la tabla de metas de `unit-of-work.md` dice en qué documento se
registra cada una: NFR11 aquí, NFR14 en `performance-requirements.md` y NFR15 en
`reliability-requirements.md`. Registrar la misma meta en dos documentos de la
misma unidad produciría dos filas para una sola fila de la matriz, que es lo que
la regla UG-13 evita. Las metas de costo y de techo están en sus documentos y no
se repiten aquí.

**`mise run test:u5` no existe todavía.** Lo crea la generación de código de esta
unidad, igual que `test:u1` a `test:u4` los crearon las suyas. No entra en el
guion de verificación: `mise run cov` ya corre la suite entera.

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| NFR11.5 | Datos personales sembrados en el texto de un turno, buscados en los atributos de los tramos exportados y en los resúmenes guardados | **Exactamente 0** hallazgos, por idioma y por tipo de entidad, nunca promediado | `mise run test:u5` |
| NFR11.6 | Fragmentos de una clave de proveedor sembrada, buscados en todo lo que el proceso emite al arrancar y al fallar: logs, mensajes de error y atributos de tramo | **Exactamente 0** apariciones, ni entera ni por fragmentos | `mise run test:u5` |
| PA-9.1 | Usos declarados en la tabla de topes cuya figura es `none_available` sin decir qué la sustituye, y usos cuya última comprobación tiene más de treinta días | **Exactamente 0** en los dos casos | `mise run schema:check`. La primera mitad es una restricción del esquema; la segunda **no lo es** —la vigencia se mide contra la fecha de hoy y ningún JSON Schema la expresa—, así que es lógica añadida a `schema_check.py`, como las comprobaciones a medida que ese archivo ya tiene |
| SEC-U5.7 | Columnas de las tablas excluidas del aislamiento que son de texto sin longitud acotada, o cuyo nombre coincide con la lista versionada de nombres de dato personal | **Exactamente 0**, preguntado al catálogo vivo | `mise run rls:check` |

**La fila de la compuerta de cobertura no se añade todavía.** La declaración
llevaría las rutas `app/backend/src/untangle/providers` y
`app/backend/src/untangle/telemetry`, que hoy contienen únicamente archivos
vacíos. La fila entra en `[tool.untangle.coverage]` en el mismo paso que crea los
módulos, igual que `tenancy` entró con U2, la redacción con U3 y el registro del
caso con U4.

**Una observación que no es una decisión de esta etapa.** U5 **no** está en la
lista afirmada de módulos críticos con piso propio del 80 % —motor de reglas,
verificador de citas, aislamiento por aseguradora, esquema del caso y redacción
de datos personales—, así que hereda solo el piso agregado (NFR18.1). Se deja
escrito que su fallo tiene la misma forma que el de la redacción, que sí entró a
esa lista por decisión de Miguel del 2026-09-20: silencioso, sin pantalla rota y
sin excepción. Añadir un sexto módulo a esa lista es decisión suya, no de esta
etapa, y por eso queda como observación y no como requisito.

## Controles

| ID | Control | Cómo se comprueba que existe |
| --- | --- | --- |
| SEC-U5.1 | Cada uso —voz, chat, evaluaciones y operación— lee su propia clave de su propia variable de entorno, declarada en la plantilla, y el cliente se construye en un único sitio por uso | `mise run env:check`, que compara la plantilla con lo que el código lee en las dos direcciones; `mise run secrets`, sobre lo que se commitea y sobre el historial |
| SEC-U5.2 | Cada uso declara en la tabla versionada qué tope rige en su proveedor y cuándo se comprobó por última vez; una alerta de presupuesto no se anota como tope | `mise run schema:check`: la tabla valida contra su esquema, que exige la figura y la fecha, y rechaza la figura "alerta" |
| SEC-U5.3 | La llamada del día de un visitante se consume al abrir la sesión, en la misma transacción que la crea | `mise run test:u5`: dos aperturas simultáneas con el mismo sujeto, una pasa y una recibe su motivo |
| SEC-U5.4 | El cupo diario del sitio se deriva del presupuesto público restante y los días que faltan, con tope de quince y piso de cero | `mise run test:u5`: reloj inyectado y acumulado forzado en los bordes —presupuesto a la mitad con la ventana a la mitad, y presupuesto agotado— |
| SEC-U5.5 | Sin poder leer el acumulado, una llamada facturable se rechaza y el chat en plan gratuito sigue atendiendo | `mise run test:u5`: se corta la base y se piden las dos cosas |
| SEC-U5.6 | Las tres tablas de dinero y cuotas están en la lista de exclusión del aislamiento, cada una con su razón escrita, y ninguna otra se añade sin razón | `mise run rls:check`, que lee la lista del manifiesto y falla si una entrada no lleva razón |
| SEC-U5.7 | Ninguna tabla excluida tiene una columna de texto sin longitud acotada ni una cuyo nombre coincida con la lista versionada de nombres de dato personal | `mise run rls:check`, preguntando al catálogo vivo por las columnas, no leyendo la migración |
| SEC-U5.8 | Toda llamada a un proveedor deja su fila de gasto, también la que falló consumiendo unidades | `mise run test:u5`: se inyecta un fallo después de consumir tokens y se cuenta lo escrito |
| SEC-U5.9 | El carril de grabación solo se concede a quien presenta credencial de la aseguradora; una petición del enlace público siempre recibe el carril público | `mise run test:u5`: la misma petición con credencial y sin ella |
| SEC-U5.10 | La reserva de grabación no la puede consumir el carril público ni cuando le queda presupuesto propio | `mise run test:u5`: acumulado forzado al borde y una llamada pública |
| SEC-U5.11 | Toda exportación de trazas y todo resumen guardado pasan por la redacción de U3 antes de salir o de escribirse | `mise run redaction:constructor`, que falla si U5 fabrica el tipo redactado por su cuenta; `mise run lint`, con el registro cerrado de puntos de salida |
| SEC-U5.12 | Ningún atributo de tramo lleva el texto del asegurado, la respuesta del modelo ni el contenido de una cláusula: los tramos llevan identificadores, conteos y tiempos | `mise run test:u5`: se siembra un turno con datos personales y se inspecciona cada atributo emitido |
| SEC-U5.13 | Un resumen de traza pedido por un navegador distinto del que lo produjo responde igual que si no existiera | `mise run test:u5`: los dos casos, comparados entre sí |
| SEC-U5.14 | Un fallo del proveedor no deja en el evento ni el prompt, ni la respuesta, ni la clave: deja el nodo, el tipo de error y el número de intento | `mise run test:u5`: se inyecta cada uno de los cuatro tipos y se inspecciona lo emitido |
| SEC-U5.15 | El acumulado de la ventana y la fila de gasto se escriben en la misma transacción; si una falla, ninguna queda | `mise run test:u5`: se provoca el fallo del segundo paso y se comprueba que el primero se revirtió |
| SEC-U5.16 | El texto de origen externo entra al proveedor como campo delimitado del estado tipado, nunca concatenado al prompt de sistema | `mise run test:u5`: un turno sembrado con una instrucción inyectada, comprobando la posición en la petición que el adaptador arma |

## Las claves, en concreto

Esta unidad multiplica por cuatro las claves del proyecto, así que conviene
escribir la razón antes de que la cantidad parezca ceremonia.

**Cuántas y por qué.** Hoy el aplicativo tiene una clave de proveedor
(`UNTANGLE_EVALS_MODEL_API_KEY`) y dos de firma. U5 añade tres más de proveedor:
chat, voz y operación. No es una por gusto: ADR-006 reparte los usos entre dos
planes distintos —el chat y las evaluaciones en el gratuito, la voz en uno de
pago prepagado— y la enmienda del 2026-09-17 añadió que cada uso vive además en
**su propio proyecto** del proveedor, porque Gemini limita por proyecto y no por
clave. Compartir una clave entre el chat público y la voz haría que un día de
tráfico en el chat agotara la cuota de la voz, que es el modo de fallo que la
separación existe para impedir.

**Qué compra la separación, exactamente.** Tres cosas, en orden de importancia:
una cuota agotada no tumba los otros usos; una clave filtrada agota el
presupuesto de un uso y no del proyecto entero; y el gasto queda atribuido por
uso sin tener que deducirlo.

**Lo que la separación no compra.** No protege contra quien tenga el proceso y su
entorno: ahí tiene las cuatro. Decirlo importa, porque un control que se cree
más fuerte de lo que es acaba sustituyendo a los que sí harían falta.

**Dónde falla, y qué lo sustituye (PA-9).** La práctica pide un tope por clave
configurado en el proveedor. Esa figura no existe en todos: lo que casi siempre
existe es una **alerta de presupuesto**, que avisa mientras el gasto sigue. Aquí
se decide que una alerta **no cuenta como tope** y no se anota como tal. Donde no
hay tope duro, lo que lo sustituye es un **saldo prepagado con la recarga
automática desactivada**: el gasto se detiene cuando el saldo llega a cero, y eso
ocurre con la aplicación detenida, que es lo que FR3.10 pide. La tabla versionada
declara por uso cuál de las cuatro figuras rige —saldo prepagado, tope mensual,
límite de tasa o ninguna disponible— y **cuándo se comprobó por última vez**; un
uso con `none_available` y sin decir qué lo sustituye, o con una comprobación de
más de treinta días, hace fallar `mise run schema:check`.

**Lo que ofrece Gemini, en concreto, porque ya está investigado.** La
investigación previa a Contract Design lo dejó medido y conviene no volver a
deducirlo: los topes de gasto de Gemini **solo existen en el plan de pago**, son
**mensuales** y reaccionan en ventanas de unos diez minutos. Es decir: no
expresan el techo acumulado de 5 USD en noventa días y no cortan en el acto. De
ahí se sigue el reparto que la tabla declara —el plan gratuito del chat y de las
evaluaciones va con `rate_limit`, que es lo que Gemini aplica **por proyecto** y
no por clave; el plan de pago de la voz va con `monthly_cap` más el saldo
prepagado sin recarga automática— y se sigue también lo que ya decía ADR-015: **el
techo sigue siendo del aplicativo, y el del proveedor es la segunda red**, no la
primera. Escribirlo así evita el error de creer que el tope del proveedor hace el
trabajo del corte.

**Qué hereda U15 y qué le queda por decidir.** PA-9 está asignado a las etapas
`nfr-requirements` de **dos** unidades, U5 y U15, y esta es la primera de las
dos. Lo que se decide aquí es **la política y el esquema**, y U15 los hereda sin
volver a abrirlos: que una alerta de presupuesto nunca cuenta como tope, que
donde no hay tope duro lo sustituye un saldo prepagado sin recarga automática, y
que la tabla declara por uso la figura vigente con la fecha de su última
comprobación, con la compuerta de los treinta días. Lo que le queda a U15 es
**llenar sus filas**: sus proveedores de transcripción y de síntesis son otros,
con otras figuras, y solo esa unidad puede decir cuál ofrece cada uno. Si alguno
no ofreciera ninguna de las cuatro, U15 no inventa una quinta: lo declara
`none_available` con lo que lo sustituye, que es lo que esta política ya prevé.

**Lo que queda encargado a Miguel, no al código.** Desactivar la recarga
automática y fijar el prepago son acciones en la consola del proveedor, con su
cuenta. El aplicativo no las puede hacer ni comprobar directamente: lo que
comprueba es que **alguien las declaró y con qué fecha**. Esa distinción está
escrita a propósito, para que la tabla no se lea como evidencia de algo que no
midió.

## La exclusión del aislamiento, y lo que la paga

Tres tablas de esta unidad —el registro de gasto, los contadores de cuota y el
acumulado de la ventana— salen del aislamiento por aseguradora. La razón está en
el diseño funcional: el techo es uno solo para el proyecto y para el gasto que no
tiene aseguradora ninguna, y las agregaciones que AC5.14.1 pide —por proveedor y
por mes— cruzan las tres aseguradoras a la vez. Una tabla con política no se
puede sumar entera.

Hasta hoy esa lista tenía **una sola entrada**: la tabla de versiones de
migraciones, que no guarda datos del aplicativo. Pasar de una a cuatro no es un
detalle, y por eso la exclusión se paga con un control que no existía:

**La aserción de columnas.** `mise run rls:check` crece para preguntarle al
catálogo vivo, por cada tabla de la lista de exclusión, qué columnas tiene. Falla
si encuentra una de tipo texto sin longitud acotada, o una cuyo nombre contiene
—sin distinguir mayúsculas— una entrada de la lista versionada de nombres de
dato personal. Esa lista vive en el manifiesto, al lado de la lista de exclusión
que paga, para que una revisión las lea juntas.

**Por qué esa forma y no otra.** Se le pregunta al motor, no al archivo donde se
escribió: es la misma lección que U2 dejó con su aserción de aislamiento, y la
misma que la cadena de suministro dejó con `supply:check`. Una tabla que nazca
mañana con una columna `visitor_email` y entre a la lista de exclusión hace
fallar la compuerta el día que nace, sin que nadie tenga que acordarse.

**Lo que este control no cubre.** No impide que alguien guarde un dato personal
en una columna con nombre inocente —`note`, `detail`— si además esa columna tiene
longitud acotada. Contra eso no hay aserción de esquema que valga; lo que hay es
que ninguna de las tres tablas tiene una columna de texto libre en su diseño, y
que añadir una se ve en la revisión del cambio de esquema.

## Decisiones de esta etapa

| # | Decisión | Por qué | Quién |
| --- | --- | --- | --- |
| NFR-U5-1 | Donde el proveedor no ofrece tope duro, lo sustituye un saldo prepagado sin recarga automática, y una alerta de presupuesto **no** cuenta como tope | Es lo único que produce la conducta que FR3.10 describe: con la aplicación detenida, el gasto para. Contar la alerta sería anotar como control algo que falla abierto | Q1, delegada |
| NFR-U5-2 | La tabla de topes lleva la fecha de la última comprobación, y una de más de treinta días hace fallar la compuerta | Un tope que nadie miró en dos meses es una creencia. Es lo único de la consola del proveedor que el aplicativo sí puede vigilar | Q1, delegada |
| NFR-U5-3 | El corte falla **cerrado** para lo facturable y **abierto** para lo que no consume el techo | Cierra donde hay dinero y abre donde no lo hay. Un límite que falla abierto cuando lo que falla es la aplicación no es un límite, y apagar el chat gratuito no protege nada | Q5, delegada |
| NFR-U5-4 | La aserción de columnas sobre tablas excluidas se añade a `rls:check` en vez de crear un comando nuevo | Es la misma familia de aserciones y la misma dueña (U2). Un comando nuevo se olvidaría de correr; este ya está en el guion de verificación | Claude |
| NFR-U5-5 | Los tramos llevan identificadores, conteos y tiempos, nunca el texto del turno ni la respuesta del modelo | La redacción protege lo que sale, pero un tramo sin texto no necesita que la redacción funcione para ser seguro. Es defensa en profundidad y cuesta cero | Claude |
| NFR-U5-6 | U5 no registra la fila de la compuerta de NFR11: la registra U3, dueña de esa meta; U5 registra sus dos filas propias sobre trazas y claves | La regla UG-13 dice que cada meta se registra una sola vez, en su unidad dueña. U5 aporta el camino de las trazas, que es donde NFR11 se ejercita de punta a punta | Claude, aplicando UG-13 |
| NFR-U5-7 | Se deja escrito que U5 no está en la lista afirmada de módulos críticos, y que su fallo tiene la misma forma que el de la redacción | Añadir un sexto módulo a esa lista es decisión de Miguel, con precedente del 2026-09-20. Callarlo sería decidir por él que no | Claude |

## Sources

- `<record>/construction/u5-provider-platform/functional-design/functional-spec.md`
  — los dos ciclos de vida, los siete flujos y las trece decisiones FD-U5
- `<record>/construction/u5-provider-platform/functional-design/rules.md` — las
  53 reglas, en especial BR1.2, BR1.3, BR2.3, BR4.5, BR4.9, BR4.10, BR5.4,
  BR5.8, BR6.5, BR7.1 y BR7.2
- `<record>/inception/requirements-analysis/requirements.md` — FR3.9, FR3.10,
  FR3.11, FR4.6, FR10.1 a FR10.5, NFR11, NFR14, NFR15, NFR18
- `<record>/inception/contract-design/contract-summary.md` — C-08, C-11, C-13,
  C-16, C-17, C-23
- `<record>/inception/domain-design/decisions.md` — ADR-006 y su reparto de
  planes por uso, ADR-018 con su enmienda del 2026-09-17, ADR-019
- `aidlc/spaces/default/codekb/untangle/technology-stack.md`
- `docs/reference/arquitectura-y-tecnologia.md` — §10 y §11: los límites de
  Gemini por proyecto, la forma de sus topes de gasto, y la observabilidad con
  `gen_ai.*`
- `app/backend/src/untangle/tenancy/rls_assertion.py` y
  `app/backend/pyproject.toml` — la aserción de aislamiento viva, su lista de
  exclusión de una sola entrada y la configuración de cobertura
- `app/backend/src/untangle/settings.py` y `.env.example` — las cuatro variables
  que hoy existen, y la forma en que se declaran
- `<record>/construction/u5-provider-platform/nfr-requirements/nfr-requirements-questions.md`
  — las cinco decisiones delegadas

## Assumptions & Open Questions

- Desactivar la recarga automática y fijar el prepago son acciones de Miguel en
  la consola de cada proveedor. El aplicativo comprueba que alguien las declaró y
  con qué fecha, no que estén puestas. La comprobación real es del checklist del
  segundo día.
- El canal por el que sale la alerta de los 3 USD lo fija el intent `infra`
  (PA-10). Esta unidad emite el evento y escribe la marca de enviada.
- Si U5 debe entrar a la lista de módulos críticos con piso propio de cobertura
  es decisión de Miguel. Queda como observación con su razón, no como requisito.
- El destino público de las trazas lo decide el intent `infra`. En local corre
  con los servicios del repositorio y el endpoint ya es una variable opcional:
  sin él, el aplicativo sigue funcionando y los resúmenes se declaran perdidos.
