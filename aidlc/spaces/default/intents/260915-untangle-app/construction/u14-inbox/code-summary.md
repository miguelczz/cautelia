# Resumen de código — U14 `inbox`

La persona en el ciclo. Todo lo que este proyecto afirma sobre cobertura, montos o
culpa pasa por aquí antes de llegar a alguien: la bandeja es donde una persona lo
firma. Y es también donde quien evalúa el proyecto decide su propio caso con un
enlace, que es la parte que se ve desde fuera.

**109 archivos, 10.889 líneas, cuatro tandas.** 102 pruebas propias en el servidor y
82 en las pantallas; 2.363 pruebas del backend y 268 de la interfaz en verde; cobertura
agregada 89 % sobre un piso del 80 %; el arnés de accesibilidad recorre 109 pantallas en
39 s de un presupuesto de 240; `scripts/verify.sh` los nueve pasos en verde.

Las **tres compuertas duras** de la unidad quedaron cerradas en las tandas 1 y 3, no
en la última: una compuerta dejada para el final es una que se descubre roja cuando ya
no hay tiempo de arreglarla.

| Compuerta | Qué asegura | Dónde |
| --- | --- | --- |
| BR1.4 | Una credencial nunca ve casos de otra aseguradora | `test_queue_isolation.py`, tanda 1 |
| BR5.1 | Un enlace abre su caso y **nunca la lista** | `test_visitor_link.py`, tanda 3 |
| BR5.2 | Una firma alterada se responde igual que un caso que no existe | `test_visitor_link.py`, tanda 3 |

Las dos últimas comparan **respuestas enteras**, no que falte un dato ajeno, y en las
tres el control positivo va delante: sin él, las dos mitades pasan igual contra una
bandeja que no entrega nada nunca.

## Lo que construyó

| Pieza | Dónde | Qué resuelve |
| --- | --- | --- |
| La cola y su cursor | `inbox/queue.py` | Orden por prioridad y espera, cuatro filtros y un cursor opaco; el orden lo decide el servidor (BR1.1, BR1.2) |
| Las dos tablas | `migrations/versions/u14_inbox_0001_tables.py` | Los avisos y los recibos de decisión, cada una con su aislamiento por fila |
| La vista de caso | `inbox/case_view.py` | Los seis bloques pedidos a quien los guarda, **sin copia**, en diez consultas contadas por su prueba (BR2.2) |
| Los avisos en vivo | `inbox/events.py` | Un evento por cambio con su identificador creciente, redactado al escribirse, y reanudación por `Last-Event-ID` (BR6.1 a BR6.3) |
| Los recibos | `inbox/receipts.py` | La misma clave devuelve la primera decisión; una clave reciclada con otra petición es conflicto (BR4.4) |
| La corrección | `inbox/correction.py` | El campo y su entrada de historial en una transacción de U4; la transcripción no cambia (BR3.1, BR3.2) |
| Las acciones | `inbox/actions.py` | Las decide la configuración de la aseguradora y el estado del caso; ningún identificador de aseguradora vive en ese código (BR4.5, BR4.3) |
| La decisión | `inbox/decision.py` | Se registra **antes** de reanudar el grafo, responde `202` y no espera (BR4.1, BR4.2) |
| La explicación | `inbox/explanation.py` | Las cinco preguntas con su respuesta, y "pendiente de decisión" donde todavía no hay decisión (BR2.4) |
| El enlace del visitante | `inbox/visitor.py` | El canje busca en cada aseguradora bajo su política de fila; una sola vía de rechazo (BR5.1, BR5.2) |
| Las rutas y la superficie | `inbox/api.py` | Cinco rutas con credencial más el canje, y la superficie **no pública**: las credenciales no se publican |
| La cola en pantalla | `pages/inbox/queue-page.tsx` | Filtros **en la dirección**, filtro sin resultados con su salida, y la lista que se actualiza sola |
| La vista en pantalla | `pages/inbox/case-page.tsx` | Encabezado pegajoso con las acciones al lado, tres bloques abiertos y tres plegados con su resultado en el titular |
| La pantalla del visitante | `pages/inbox/visitor-page.tsx` | Su propia pantalla, sin jerga del sistema, con el token en el fragmento y la dirección limpia |
| Los casos de evaluación | `evals/inbox_probes.py`, `app/evals/cases/ds2/inbox-*` | La explicación y las acciones, medidas en cada entrega sin base de datos ni modelo |

## Las decisiones de la unidad

**La tercera decisión del contrato no se construye.** C-05 declara `request_more` y
ninguna historia la describe, ningún criterio la ejercita y ninguna de las cuatro
resoluciones de U4 le corresponde: construirla sería inventar su conducta. Un caso que
necesita más información ya tiene camino probado, que es quedarse esperando al
asegurado. El contrato se enmendó con esa razón y añadirla después es aditivo
(decisión de Miguel, 2026-09-28).

**El visitante tiene su propia pantalla, no la del ajustador con un interruptor.**
Comparten los bloques de evidencia y nada más. La regla U-07 prohíbe la jerga del
sistema en cualquier pantalla de visitante —"bandeja" no significa nada para quien
reporta— y sostener dos juegos de etiquetas sobre una sola pantalla es la forma segura
de que un día se cruce uno (decisión de Miguel, 2026-09-28).

**Nada se decide dos veces.** Las acciones disponibles, si se puede corregir un campo y
el estado de la explicación llegan **resueltos del servidor**. Una pantalla que
preguntara "¿es una agencia?" o "¿está cerrado?" escribiría esas reglas por segunda vez
en otro lenguaje, y el día que una cambiara la otra seguiría diciendo lo de antes. Lo
que impide la acción sigue siendo la ruta; lo que la pantalla recibe es la cortesía de
no dibujar un botón que va a ser rechazado.

**Un bloque plegado muestra su resultado en el titular**, y el titular no tiene valor
por omisión. Plegar oculta el detalle, nunca el dato: sin esa condición, plegar tres de
los seis bloques sería esconder un tercio de la evidencia detrás de un clic que nadie
da. Dejar el titular opcional habría hecho que la forma prohibida fuera la más fácil de
escribir.

**El identificador de caso es único en toda la base, no por aseguradora.** DS-8 sembraba
una colisión de identificador entre dos aseguradoras y el esquema de U4 no la admite: su
llave primaria es el identificador solo. Se llevó como decisión en vez de debilitar una
prueba, y Miguel eligió conservar la fila con su propio identificador; la colisión de
número de póliza y de nombre, que es la que de verdad ejercita el aislamiento, sigue
sembrada.

**El token viaja en el fragmento de la dirección**, que el navegador nunca manda al
servidor ni en `Referer`. La pantalla lo lee, lo canjea una vez por carga y limpia la
dirección dejando la aseguradora y el caso, para que recargar siga funcionando con la
cookie. Un token en un registro es un enlace que cualquiera que lea ese registro puede
usar durante su hora.

**Quién decidió sale del historial y no de una copia en la fila del caso.** Es la última
transición aplicada de un caso cerrado, y eso la identifica sin ambigüedad porque
`closed` es terminal. La alternativa era que U4 añadiera el actor del cierre a su fila, y
serían dos sitios guardando lo que el historial ya guarda.

**Las etiquetas de los ocho campos viven junto a las de los enums, en U4.** El juego de
campos lo declara su esquema, y su prueba compara los dos conjuntos en los dos sentidos:
un campo nuevo sin etiqueta falla ahí, y una etiqueta sin campo también. La pantalla
recibe la clave por el cable y solo la resuelve.

**El arnés de accesibilidad sirve respuestas declaradas para estas pantallas.** Corre
contra el proceso real sobre una base **vacía**, así que sin eso las tres pantallas se
dibujarían como "no hay nada aquí" y lo que entraría en la línea base sería una página de
estado. Lo que el arnés mide es el dibujo —contraste, encabezados, orden de tabulación,
objetivos táctiles— y las reglas de acceso se prueban contra la base de verdad, en las
pruebas de integración. Es el mismo recurso que ya usaban las dos páginas de la espera.

## Lo que hacía falta para usarlo con las manos

Tres comandos que no existían, cada uno nombrado en el archivo de tareas como pide la
convención 10, porque la bandeja es la primera pantalla que se trabaja y no solo se mira:

| Comando | Qué hace |
| --- | --- |
| `mise run dev` | El **proceso real** contra la base local, con los estáticos compilados y las cabeceras de verdad; sube las migraciones antes de servir, porque una base sin migrar deja la interfaz en "la demo está despertando". Imprime en qué dirección escucha y toma otro puerto si el 8000 está ocupado —en esta máquina lo tiene Docker—; con `--port` explícito, ocupado es un error |
| `mise run migrate` | El mismo camino, aparte, para cuando solo hace falta migrar. `migrate:check` es otra cosa: sube, baja y vuelve a subir contra una base efímera, y es la que corre en la compuerta |
| `mise run tenancy:case-link` | Emite el enlace de un caso a la salida estándar, con el token **en el fragmento** de la dirección. Existe porque nada lo emite todavía en producción —el enlace que el chat entrega al cerrar es de U13 y U17— y sin él la pantalla del visitante, que es la que entra en la línea base de accesibilidad, no se puede abrir |

Y `mise run test:u14`, que corre las dos mitades de la unidad: la integración con base y
las pantallas con el runner de la interfaz.

El recorrido completo queda escrito en el comentario de `dev`, en orden y con el paso de
la credencial, que sale por la salida estándar y no se guarda en ningún archivo (D23).

## Las fronteras que no construyó

- **La emisión y validación de enlaces y credenciales** es de U2 (C-07). Aquí se canjean
  y se consumen. U2 ganó `verify_case_link`, idéntica a la de canje pero sin subir el
  contador, porque comprobar una cookie en cada petición no es canjear otra vez.
- **El enlace que entrega el chat o la consola al cerrar** es de U13 y U17.
- **La decisión de una solicitud de cotización** la agrega U19.
- **El traspaso real a la aseguradora emisora** está fuera de esta versión (W1). El caso
  queda cerrado con resolución *enviado a la aseguradora*, sigue en la agencia, y nada
  de lo que ve el asegurado promete que la emisora lo llame.
- **La vista de comparación** es U23, y va después de esta unidad.

## Cabos con dueño

- El vocabulario de errores de C-01 vive en `untangle.server`, que está por encima de
  las unidades en el contrato de capas, así que una ruta no puede elegir su código:
  levanta un `HTTPException` y la raíz lo traduce. Anotado para U6, su dueña, igual que
  lo dejó U13.
- Nadie llama a `record_trace` todavía (U5 y U12).
- DS-7 espera transcripciones reales, que el conductor de texto de U13 ya puede producir.
- Faltan **ocho guiones por idioma** para las 30 conversaciones de DS-2 que pide
  `team.md`; hoy hay 22 por idioma, contadas del árbol y no de la prosa.
