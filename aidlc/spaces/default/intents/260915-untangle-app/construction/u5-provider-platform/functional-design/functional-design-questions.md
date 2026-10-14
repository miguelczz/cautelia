# Preguntas — Diseño funcional de U5 `provider-platform`

U5 es todo lo que cuesta dinero: la llamada al modelo, su costo con precio de
lista, el techo con corte, las cuotas de la demostración y la traza. Quince
unidades posteriores la consumen, y una de ellas —la voz— solo se publica si
este corte funciona.

Casi todo está decidido. El modelo y los planes por uso los fija ADR-006, los
puertos y la taxonomía de errores los fija ADR-018, la superficie la fijan los
contratos C-16, C-17 y C-23, el techo acumulado de 5 USD en 90 días desde el
2026-09-16 lo fija D11, y los límites de la voz los fija FR3.9. Lo que sigue son
los seis huecos que quedaron: cada uno tiene dos respuestas legítimas y cada uno
cambia algo que se ve.

**Cómo se respondieron.** Miguel delegó estas seis en la recomendación
("procede con U5 [...] me voy por las recomendaciones que haces, analiza lo
lógico y vete por ello", 2026-09-21). Cada respuesta es la opción marcada como
recomendada, y la razón de la recomendación está escrita antes de la respuesta
para que se pueda discutir después.

---

## Q1 — El techo es uno solo y el aislamiento exige que toda tabla tenga dueña

Dos reglas del proyecto chocan aquí por primera vez.

La primera: **toda tabla del aplicativo lleva aislamiento por aseguradora y su
política**, y la aserción de U2 interroga el catálogo vivo de la base y falla si
encuentra una que no lo tenga. Su lista de exclusión hoy tiene una sola entrada
—la tabla de versiones de migraciones— y cada entrada lleva su razón escrita.

La segunda: **el techo de gasto es uno solo para el proyecto entero**. Son 5 USD
en 90 días de Miguel, no 5 USD de Stonecroft. Y AC5.14.1 pide ver el costo
**por proveedor y por mes**, que son agregaciones de todas las aseguradoras a la
vez, más el gasto que no tiene aseguradora ninguna: las evaluaciones, la
generación de datos y la operación.

Una tabla con aislamiento por aseguradora no se puede sumar entera. Si el
registro de gasto llevara política, el corte dependería de poder leer todas las
aseguradoras a la vez, que es exactamente lo que la política existe para
impedir.

- A. **(Recomendada)** El dinero y las cuotas son dato **del proyecto**, no de
  una aseguradora, y sus tres tablas —registro de gasto, contadores de cuota y
  acumulado de la ventana— entran en la lista de exclusión con su razón escrita.
  A cambio aceptan una restricción dura que la aserción de aislamiento no
  comprueba y **una aserción nueva de esta unidad sí**: ninguna tabla excluida
  puede tener una columna de texto libre ni una columna de dato personal, y la
  comprobación se hace contra el catálogo vivo, igual que la de U2. El resumen
  de traza, que sí es dato de un visitante, se queda con su aseguradora y su
  política como cualquier otra tabla.
- B. Las tres tablas llevan aseguradora y política, y el acumulado se suma por
  aseguradora. Rompe AC5.14.1, porque por proveedor y por mes son cifras del
  proyecto, y deja sin sitio el gasto que no tiene aseguradora.
- C. Un rol aparte que se salta las políticas para calcular el corte. La
  aserción de U2 falla si el rol vivo puede saltarse las políticas, y falla con
  razón: con ese rol, todas las tablas podrían estar perfectas y la suite de
  aislamiento no mediría nada.
- X. Other (please specify)

**Por qué la A.** La exclusión no es un permiso, es un cambio de control: se
pierde el aislamiento por aseguradora y se gana, a cambio, una prohibición más
fuerte y comprobable —que ahí no hay nada personal que aislar—. La entrada de la
lista y la aserción nueva nacen en el mismo commit, así que la exclusión nunca
existe sola.

[Answer]: A

---

## Q2 — Cómo se guarda "no medido" para que ninguna suma lo convierta en cero

AC4.8.4 y AC5.14.6 dicen lo mismo dos veces: una llamada sin precio declarado
registra su costo como "no medido", **nunca como cero**. La razón es la misma
que la convención 8c del equipo ya obliga a mantener entre "no hay cláusula" y
"no pude verificar": un cero se suma y desaparece; un hueco se ve y se pregunta.

El problema no es guardarlo, es que **sobreviva a la suma**. Una columna de
dinero que admite nulos se suma sin avisar en cualquier motor de base de datos:
el total sale más bajo y nadie lo nota.

- A. **(Recomendada)** El costo se guarda en dos columnas que viajan siempre
  juntas: el valor y su estado (`measured` o `not_measured`). Ninguna suma
  devuelve un número solo: toda agregación devuelve **el par** —lo medido y
  cuántas llamadas no se midieron—, y la pantalla y el reporte están obligados a
  mostrar el segundo junto al primero. Una cifra publicada sin su conteo de no
  medidas es un fallo de la prueba, no una decisión de la pantalla.
- B. Una sola columna que admite nulos, y que cada consumidor se acuerde de
  contarlos aparte. Es la forma en que este error se comete siempre.
- C. Las llamadas sin precio van a otra tabla. El total queda limpio, y a cambio
  la traza de un caso tiene que mirar en dos sitios para contar sus llamadas.
- X. Other (please specify)

**Por qué la A.** Es la única que hace imposible el fallo en vez de detectable.
El tipo que devuelve la agregación lleva el conteo dentro, así que un consumidor
que quiera ignorarlo tiene que escribirlo a propósito.

[Answer]: A

---

## Q3 — Qué gasto cuenta contra el techo: el precio de lista o lo que de verdad se factura

ADR-006 reparte los usos entre dos planes: el chat público, las evaluaciones y
la generación de datos corren en el **plan gratuito**, y solo la voz y su trabajo
de fondo corren en plan de pago prepagado. La misma decisión dice, entre sus
consecuencias, que "el chat público no gasta el techo".

Pero NFR14 pide publicar el **costo por caso exitoso a precio de lista**, y una
llamada del plan gratuito tiene precio de lista: es cero dólares facturados y no
es cero dólares de valor. Si el precio de lista contara contra el techo, un día
de tráfico en el chat se comería el presupuesto de la voz sin que nadie hubiera
pagado un centavo.

- A. **(Recomendada)** Cada fila de gasto lleva las dos cifras: el **costo a
  precio de lista**, que se registra siempre y es el que publica NFR14, y una
  marca de **si esa llamada se factura**, que depende del plan del uso. El techo,
  la alerta y el corte suman solo las facturables. La pantalla de gasto muestra
  las dos y dice cuál es cuál.
- B. Solo se registran las llamadas facturables. El techo queda exacto y el costo
  por caso del chat deja de existir, que es justo la cifra que NFR14 publica.
- C. Todo cuenta contra el techo. Es la lectura literal de "gasto acumulado del
  proyecto" y contradice ADR-006 y el reparto de planes que ya se decidió.
- X. Other (please specify)

**Por qué la A.** Las dos cifras responden dos preguntas distintas —"¿cuánto
cuesta esto?" y "¿cuánto llevo pagado?"— y colapsarlas hace que una de las dos
mienta. El día que el chat pase a plan de pago, lo que cambia es la
configuración del uso, no el código del corte.

[Answer]: A

---

## Q4 — Cómo se calcula el cupo diario del sitio para la voz

FR3.9, con la enmienda del 2026-09-19, pide "un cupo diario del sitio derivado
del presupuesto que queda y los días que faltan, con un tope máximo de 15", y su
criterio exige que "con el presupuesto a la mitad y la ventana a la mitad, el
cupo permite llegar al día 90". La fórmula no está escrita en ninguna parte.

- A. **(Recomendada)** El cupo del día es
  `min(15, piso(presupuesto_restante ÷ (días_restantes × reserva_por_llamada)))`,
  donde la **reserva por llamada** es un valor de la configuración versionada:
  la duración máxima de llamada por el precio de lista del minuto del modo de
  voz más caro. Nunca baja de cero: presupuesto agotado da cupo cero, que es el
  corte. Con la mitad del presupuesto y la mitad de la ventana el cociente da lo
  mismo que el primer día, así que el cupo alcanza para llegar al día 90.
- B. Quince fijo todos los días. Es lo que dice el tope máximo y nada más; un mal
  día se lleva el presupuesto y los días siguientes no tienen cupo.
- C. Repartir el presupuesto en partes iguales por día desde el principio. No
  recupera lo que no se gastó ayer, así que la demostración queda más apretada de
  lo que hace falta.
- X. Other (please specify)

**Por qué la A.** Es la única que cumple el criterio escrito, y tiene una
propiedad que las otras no: se **recalcula** cada día con lo que de verdad queda,
así que un día flojo devuelve su cupo a los siguientes en vez de perderlo.

[Answer]: A

---

## Q5 — Cuándo se consume la llamada del día de un visitante

FR3.9 da a cada visitante **una llamada al día**. Falta decir en qué momento se
gasta: al abrir la llamada o al terminarla.

Al final es más justo y abre la puerta a abrir diez llamadas a la vez, que es
justo lo que RT-13 prueba. Al principio es seguro y castiga a quien se le cae la
conexión antes de decir una palabra.

- A. **(Recomendada)** Se consume **al abrir**, en la misma transacción que crea
  la sesión, y se devuelve solo si la llamada terminó **sin un solo segundo de
  audio facturable**. Esa condición se comprueba con el registro de gasto, no
  con lo que diga la consola: una llamada que no generó gasto no gastó cupo.
- B. Se consume al terminar. Diez pestañas abiertas a la vez pasan el límite,
  que es el escenario de RT-13.
- C. Se consume al abrir y nunca se devuelve. Es el más simple y el más injusto:
  una caída de red antes del primer turno le quita el día al visitante.
- X. Other (please specify)

**Por qué la A.** Mantiene la propiedad que importa —dos llamadas simultáneas no
pueden pasar el límite, porque la que pierde la carrera no encuentra cupo— y
paga la injusticia con una condición objetiva y comprobable.

[Answer]: A

---

## Q6 — Qué pasa con el gasto de un caso que el reinicio nocturno borra

AC5.14.4 exige que el acumulado de la ventana **no se borre ni vuelva a cero**
cuando corre el reinicio nocturno. Pero el reinicio borra los casos de
visitantes, y cada fila de gasto nombra el caso al que se atribuye. Todas las
tablas hijas del caso en U4 cuelgan de él con borrado en cascada; si el gasto
colgara igual, el reinicio se llevaría el historial de costos cada noche.

- A. **(Recomendada)** La fila de gasto **no cuelga** del caso: lo nombra. Cuando
  el reinicio borra el caso, esa columna queda en nulo y la fila sobrevive con su
  proveedor, su uso, su costo y su fecha. La atribución por caso se pierde —el
  caso ya no existe— y el costo por proveedor, por mes y el acumulado siguen
  completos.
- B. La fila de gasto se borra con el caso. Cumple el borrado de datos de
  visitante de la forma más simple y vacía el registro de costos cada noche,
  contra AC5.14.4.
- C. El caso no se borra del registro de gasto y queda el identificador
  apuntando a un caso que ya no existe. Deja una referencia rota que nadie
  puede resolver y que un día alguien va a intentar.
- X. Other (please specify)

**Por qué la A.** El identificador del caso es lo único que liga la fila con un
visitante; quitarlo es exactamente lo que el contrato de borrado pide, y deja
intacta la única cifra que no puede perderse. Es también la razón de que esta
tabla sea la única de la unidad que no cuelga en cascada de nada.

[Answer]: A
