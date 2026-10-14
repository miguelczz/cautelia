# Plan de Bolts — Untangle

El orden en que se construyen las 22 unidades de trabajo y qué se espera de cada
una. Un **Bolt** es una pasada de construcción sobre una pieza del trabajo que
termina en algo que corre y se puede probar: aquí cada Bolt es exactamente una
unidad, porque la práctica afirmada del equipo es construir una pieza completa a
la vez y no dejar ninguna a medias.

**Fuentes consumidas.**

- **Requisitos** (`../requirements-analysis/requirements.md`): los grupos FR1 a
  FR14 y los NFR con su valor esperado, que fijan qué tiene que ser cierto para
  que un Bolt cuente como terminado.
- **Historias** (`../user-stories/stories.md`): las 87 historias con su prioridad
  Must o Should, de donde sale qué se puede cortar.
- **Maquetas** (`../refined-mockups/mockups.md`): las doce pantallas y sus
  estados, que definen la demostración esperada de los Bolts con interfaz.
- **Componentes** (`../domain-design/components.md`): los 23 componentes y la
  propiedad de cada entidad.
- **Unidades de trabajo** (`../units-generation/unit-of-work.md`): las 22
  unidades con su tipo, complejidad, rama de pruebas e historias.
- **Dependencias entre unidades**
  (`../units-generation/unit-of-work-dependency.md`): las 89 aristas que ninguna
  secuencia puede romper, y las condiciones externas por unidad.
- **Mapa de historias** (`../units-generation/unit-of-work-story-map.md`): qué
  historia se acepta en qué unidad.
- **Contratos** (`../contract-design/contract-summary.md`): los 30 contratos;
  una unidad puede construirse contra el contrato de otra sin esperar a que
  exista, y las preguntas abiertas de contrato marcan qué Bolt no puede empezar.
- **Prácticas del equipo** (`../practices-discovery/team-practices.md`, ya en
  `team.md`): una pieza completa a la vez, sin esqueleto delgado, commit directo
  a `main` con GitHub Actions como compuerta.
- **Plan de entrega del PRD** (`docs/specs/prd.md`, Segmento 13): el calendario
  de 90 días con sus compuertas y la regla de corte.

## Decisiones de esta etapa

| # | Decisión | Qué se decidió |
| --- | --- | --- |
| DP-1 | Orden de construcción | Por capas, como el plan del PRD: base → corpus, citas, reglas y cumplimiento → captura y grafo → evaluación → chat y bandeja → operación y evidencia → voz en inglés → enlace público → voz en español → cotización |
| DP-2 | Experimento de voz | Corre apenas termine Incepción, en paralelo con los primeros Bolts, que no dependen de la voz |
| DP-3 | Compuerta del día 30 | Se mantiene el **contenido** de la compuerta (las 17 unidades antes de tocar la voz) y, en su momento, su fecha. **Reemplazada en parte por DP-8:** la fecha dejó de ser compromiso; el contenido sigue en pie |
| DP-4 | Atención de la construcción | Una sola sesión, unidad por unidad, con aprobación de Miguel en el camino |
| DP-5 | Preocupaciones a atender temprano | La voz, la calidad de las respuestas y el costo (respuesta de Miguel: "Las 3 ultimas") |
| DP-6 | Un Bolt es una unidad | Se aplica la práctica afirmada de construir una pieza completa a la vez; 22 Bolts, ninguno en paralelo |
| DP-7 | Recorrido por unidad | Cada unidad atraviesa su diseño funcional, sus requisitos y diseño no funcionales, su infraestructura y su código antes de que empiece la siguiente. Es la regla de `project.md`: "Construcción recorre el trabajo por componente y no por etapa" |
| DP-9 | El README se escribe tarde, y se nombra | Decisión de Miguel del 2026-09-19, literal: *"Es ilogico crear un documento que despues toca actualizar, asi que no crearemos nada hasta que hayan cosas solidas"*. Es coherente con la regla del proyecto de que la documentación describe lo construido. Lo que cambia es que deja de ser una mención suelta del calendario y pasa a ser trabajo nombrado con su definición de terminado, en la tabla de abajo |
| DP-10 | La línea base v0 se publica al cerrar B14, no en B12 | Un caso de conversación necesita un conductor de canal, y el primero llega con el chat. El orden de los Bolts no cambia; lo que cambia es qué promete cada uno |
| DP-8 | Las fechas son referencia, no compromiso | Decisión de Miguel del 2026-09-18, después de aprobar esta etapa, literal: "nadie me pone un corte de fecha, podemos ir a nuestro ritmo". El **orden** de los Bolts manda; el calendario del PRD queda como guía de secuencia y de agrupación, no como plazo. La regla de corte sigue disponible, pero la dispara Miguel cuando quiera reducir alcance, no el vencimiento de una fecha |
| DP-11 | El orden lo aplica la herramienta del flujo, y así lo aplica | Enmienda del 2026-09-21. La herramienta que recorre la construcción **no lee este plan**: cuando varias unidades pueden empezar a la vez, las ordena por su nombre como texto, y como texto "u10" va antes que "u6". El orden real es U1 → U2 → U3 → U4 → U5 → U6 → U10 → U15 → U7 → U9 → U21 → U8 → U11 → U20 → U22 → U12 → U13 → U14 → U16 → U17 → U18 → U19; los Bolts B1 a B22 de abajo conservan su contenido y su definición de terminado, pero no su turno. Por decisión de Miguel, U6 se renombró `u06-web-shell` para que el flujo la entregue primera de su grupo: quiere ver la interfaz antes que las unidades sin pantalla. El cero no significa nada más. Las demás unidades conservan su nombre: las cinco cerradas perderían su registro de cierre, y ninguna otra gana nada con el cambio. El orden respeta todas las dependencias del mapa. Una tensión que **no** crea el cambio de nombre, porque ya existía: U15 (adaptadores de transcripción y síntesis) cae antes de que el camino en texto esté completo, contra el contenido de la compuerta de DP-3. U15 no produce una llamada de voz, que es U16, y U16 sí queda después de U12 |
| DP-12 | Construcción en modo ligero | Decisión de Miguel del 2026-09-21, al pasar a un plan con menos uso: "Si, deja anotada la decision para que no tengamos desalineacion a futuro". Desde U6 (a mitad de su recorrido) la construcción corre sin revisión automática por etapa, con profundidad Minimal y sin las etapas `nfr-design` e `infrastructure-design`; lo que fijaban para una unidad se decide en su plan de generación de código. La razón es medida: las dos revisiones de U6 costaron 227.709 y 209.505 tokens, y quedaban 83 etapas por unidad, unos 18 millones de tokens solo en revisiones. **Ninguna compuerta baja**: pruebas, piso de cobertura del 80 %, `scripts/verify.sh`, GitHub Actions y golden sets siguen iguales. Registrada también en `project.md` (Decided) |
| DP-13 | Qué modelo escribe el código | Decisión de Miguel del 2026-09-21, que complementa DP-12. **Mientras Miguel tenga el plan Max, el agente que escribe el código usa Opus**; **cuando pase al plan Pro, usa Sonnet**, en tandas más cortas y con cada tanda revisada antes de subirla. La razón: con margen de uso, lo que decide la velocidad es cuántas tandas salen en verde a la primera en un código con muchas reglas propias, y ahí Opus repite menos (la primera mitad del código de U6 quedó en verde a la primera en 48 minutos); en Pro, el cuello de botella pasa a ser el límite de uso, que Opus gasta mucho más rápido. No hay medición de Sonnet en este proyecto: la regla sale del tipo de trabajo. El diseño, el plan que Miguel aprueba, la revisión de cada entrega y el diagnóstico de fallos siguen en la sesión principal. El cambio lo dispara Miguel avisando que cambió de plan. **Enmienda del 2026-09-21, al cerrar U7:** Miguel se queda en Max, pero el límite semanal pasó a ser el cuello de botella (U7 gastó unos 2,2 millones de tokens solo en el agente de código), así que el agente usa **Sonnet desde U9** en cualquier plan, con tandas más cortas revisadas antes de subirlas. Además, comentarios solo donde la razón no es obvia, y la suite completa una sola vez al final de cada tanda. Ninguna compuerta ni práctica de calidad cambia (`project.md`, Decided y Code Style) |
| DP-14 | El núcleo ahora, lo de publicar después | Decisión de Miguel del 2026-09-21, que reemplaza para lo que falta la regla de construir cada pieza completa: *"Apliquemosla, no creo que dos dias de trabajo seguido valgan la pena para algo tan pobre como esto"*. Dos partes. **(1)** U17, U20 y U22 solo sirven para abrir la demo al público y pasan al final, en la **pasada de publicación**, con una arista de orden de entrega hacia U18 marcada como no técnica (`unit-of-work-dependency.md`). El orden queda U10, U15, U7, U9, U21, U8, U11, U12, U13, U14, U16, U18, U19 y después U17, U20 y U22: el chat pasa de la unidad 11 a la 9 y la voz en inglés de la 13 a la 11. **(2)** Dentro de cada unidad se construye el núcleo —su conducta con sus pruebas— y se difiere lo que solo importa al publicar: límites públicos por sesión y por día, topes en el proveedor, telemetría de uso, chequeo periódico, reinicio nocturno, paneles públicos, mediciones contra el despliegue en vivo y el checklist del segundo día. Cada criterio diferido queda con su identificador en `pasada-de-publicacion.md` y como `Deferred` en la trazabilidad de su unidad. **Nunca se difiere** una compuerta dura de lo que se construye (aislamiento, datos personales, promesas de cobertura, citas), ni las pruebas, el piso del 80 % o `scripts/verify.sh`, y **nada se publica antes de terminar la pasada**. La demostración de U15 (B18) pasa a ser oír a Catalina decir una frase desde el propio aplicativo |
| DP-15 | U23 llegó después del plan y no tiene Bolt | Enmienda del 2026-09-29. Este plan se escribió con 22 unidades y B1 a B22 las cubren una a una. El 2026-09-28, al integrar la revisión de U13, la historia US2.9 —la vista de comparación entre aseguradoras— salió de esa unidad y nació **U23 `comparison-view`**, que ningún Bolt nombra. Se deja dicho en vez de renumerar: los Bolts son el registro de lo que se planificó y renumerarlos borraría de qué se decidió cada uno. **U23 va al final, después de la pasada de publicación**: es una sola historia Should, depende del chat, de la bandeja y del corpus —las tres ya construidas— y nada depende de ella. Los documentos de esta etapa que dicen "22 unidades" se dejan como están: describen la decisión que se tomó el 2026-09-18 con la información de ese día, y reescribirlos falsearía el registro. El catálogo vivo, `unit-of-work.md`, sí se corrigió a 23 |

## Calendario de referencia

**Las fechas de esta tabla son referencia, no compromiso** (DP-8). Nadie impone
un plazo al proyecto, así que lo que manda es el **orden** de los Bolts; las
semanas están aquí porque el PRD las usa para ordenar los hitos de medición
(líneas base, red-team, video) y porque dan una idea de tamaño relativo, no
porque haya que llegar a una de ellas.

Fechas del PRD con inicio el 2026-09-16: día 30 el 2026-10-15, día 60 el
2026-11-14, día 90 el 2026-12-14. Las semanas 8 y 12 no llevan entregables
nuevos.

| Semana | Fechas | Bolts | Hito |
| --- | --- | --- | --- |
| 1 | 16 a 22 sep | — (Incepción 2.1 a 2.9) | Incepción cerrada |
| 2 | 23 a 29 sep | B1 a B5 | Base terminada |
| 3 | 30 sep a 6 oct | B6 a B11 | Camino en texto completo |
| 4 | 7 a 13 oct | B12 a B17 | Chat y bandeja en vivo |
| — | 14 y 15 oct | — | Primera compuerta de contenido y validación externa |
| 5 | 16 a 22 oct | B18, B19 | Llamada de voz en inglés |
| 6 | 23 a 29 oct | B19 (cierre), DS-5 inglés, red-team 1 | Línea base v1 |
| 7 | 30 oct a 5 nov | B20, video v1, landing pasada 1 | Enlace público de voz |
| 8 | 6 a 12 nov | Amortiguador; piloto cerrado | — |
| — | 13 y 14 nov | — | Segunda compuerta de contenido |
| 9 | 15 a 21 nov | B21, DS-5 español, red-team 2 | Línea base v2 |
| 10 | 22 a 28 nov | B22 | Cotización |
| 11 | 29 nov a 5 dic | Corrida final, red-team 3, README, video final | Evidencia |
| 12 | 6 a 12 dic | Amortiguador y publicación | — |
| — | 13 y 14 dic | — | Tercera compuerta de contenido |

**Qué significa esto en la práctica.** Si la tabla se leyera como plazo, los
Bolts B1 a B17 exigirían unas cinco unidades por semana contra las dos y media
del resto del plan, y esa diferencia obligaría a cortar alcance. Como las fechas
son referencia (DP-8), la consecuencia es otra: los bloques se cumplen **en
orden** y cada uno tarda lo que tarde. Lo que sí conserva su fuerza es el
contenido de cada compuerta —qué tiene que ser cierto antes de seguir— y la
regla de corte, que queda como herramienta de alcance a decisión de Miguel.

## Secuencia de Bolts

Cada Bolt nombra su unidad, lo que tiene que ser cierto para darlo por terminado,
qué prueba que no sabíamos antes, y qué se puede enseñar cuando termina.

### B1 — Base del repositorio (U1 `workspace`)

- **Semana:** 2. **Complejidad:** L. **Rama de pruebas:** evaluada.
- **Terminado cuando:** existe el primer commit de código con manifiesto,
  lockfile con hashes, formatter, linter con reglas de seguridad, tipos y
  cobertura con su alcance en `app/`; `mise.toml` con las tareas;
  `scripts/verify.sh` en el orden de `team.md`; el flujo de GitHub Actions que lo
  invoca con el escaneo de secretos como primer trabajo; el árbol de módulos
  vacío con los contratos de `import-linter`; la raíz de composición con su
  endpoint de salud; el catálogo de textos con sus chequeos de paridad; y el
  corredor de evaluaciones de un comando.
- **Qué prueba:** que el andamiaje completo entra en un solo commit y que
  `verify.sh` corre en verde en GitHub Actions sobre `main`, que es la única
  compuerta que tendremos.
- **Demostración:** clonar el repositorio y llegar al reporte de evaluación con
  un comando, en menos de 15 minutos (NFR21).

### B2 — Aseguradoras e identidad (U2 `tenancy`)

- **Semana:** 2. **Complejidad:** L. **Rama de pruebas:** evaluada.
- **Terminado cuando:** el punto único de sesión fija la aseguradora, cada tabla
  tiene RLS con `FORCE ROW LEVEL SECURITY` y su política, la aserción de esquema
  falla si alguna no la tiene, existen las credenciales firmadas y los enlaces de
  una hora, y está declarado en un solo lugar qué es un dato de visitante con su
  contrato de borrado.
- **Qué prueba:** que el aislamiento vive en la base de datos y no en el código,
  con una prueba que se conecta con el rol del aplicativo y no con el
  superusuario.
- **Demostración:** la batería de colisiones de DS-8 en verde y una consulta
  cruzada que devuelve vacío.

### B3 — Redacción de datos personales (U3 `pii-redaction`)

- **Semana:** 2. **Complejidad:** M. **Rama de pruebas:** evaluada.
- **Terminado cuando:** los reconocedores de placa, cédula, teléfono y número de
  póliza funcionan en los dos idiomas, y el tipo de salida solo acepta contenido
  redactado, de modo que una salida sin redactar no compila.
- **Qué prueba:** que la redacción se puede hacer imposible de esquivar por
  construcción, no por disciplina.
- **Demostración:** RT-14 y RT-15 medidos por idioma y por tipo de entidad, sin
  promedio.

### B4 — Registro del caso (U4 `case-record`)

- **Semana:** 2. **Complejidad:** L. **Rama de pruebas:** evaluada.
- **Terminado cuando:** el esquema valida los siete campos centrales y los grupos
  repetibles, la completitud se calcula por campo, el modelo de estados rechaza
  toda transición no declarada dejando evento, y la transcripción se guarda
  redactada.
- **Qué prueba:** que el caso puede ser la fuente de verdad sin que ningún otro
  módulo escriba en sus tablas.
- **Demostración:** un caso de ejemplo con dos lesionados y dos terceros que
  valida y se recupera íntegro.

### B5 — Proveedores, gasto y trazas (U5 `provider-platform`)

- **Semana:** 2. **Complejidad:** L. **Rama de pruebas:** determinista.
- **Terminado cuando:** el adaptador de Gemini está detrás de los puertos, la
  fábrica construye un cliente por uso con su clave y su proyecto, el registro de
  gasto usa la tabla de precios versionada con alerta en 3 USD y techo en 5 USD
  en la ventana de 90 días, y las trazas salen con las convenciones GenAI.
- **Qué prueba:** que el costo es observable desde el primer día y que el corte
  funciona aunque la observación falle. **Atiende la preocupación del costo**
  (DP-5): sin este Bolt temprano, el gasto no se ve hasta que ya ocurrió.
- **Demostración:** el panel de gasto con un acumulado forzado en pruebas
  llegando al tope y cortando, sin gastar dinero real.

### B6 — Generador de datos sintéticos (U7 `synthetic-data`)

- **Semana:** 3. **Complejidad:** L. **Rama de pruebas:** determinista.
- **Terminado cuando:** el generador produce con la misma semilla bytes
  idénticos, con su manifiesto de hashes, para el corpus de las tres
  aseguradoras, las pólizas emitidas, un caso en cada estado, las colisiones de
  DS-8 y las relaciones entre cláusulas.
- **Qué prueba:** que el corpus es reproducible y que la estructura se puede
  imitar sin copiar texto de terceros.
- **Demostración:** dos corridas del mismo commit produciendo el mismo corpus, y
  el chequeo de contenido de ISO y ACORD en verde.
- **Dependencia humana:** Miguel revisa una muestra de textos fuente por idioma.

### B7 — Pólizas, recuperación y citas verificadas (U8 `policy-rag`)

- **Semana:** 3. **Complejidad:** XL. **Rama de pruebas:** evaluada.
- **Terminado cuando:** la recuperación filtra por aseguradora y póliza antes de
  ordenar, el verificador distingue `verified`, `rejected`, `no_clause_found` y
  `unverifiable`, rechaza la cita que ignora un endoso vigente, y el nodo
  `policy_verification` es puro y no escribe en la base.
- **Qué prueba:** que se puede sostener cero citas inexistentes con un
  verificador exacto y no con un prompt. **Atiende la preocupación de la
  calidad** (DP-5): es la unidad donde se gana o se pierde la precisión de
  citación.
- **Demostración:** DS-3 con distractores, y una pregunta sin cláusula que
  responde "no encuentro una cláusula que lo cubra" en vez de inventar.

### B8 — Motor de reglas y nodo de decisión (U9 `rules-decision`)

- **Semana:** 3. **Complejidad:** M. **Rama de pruebas:** evaluada.
- **Terminado cuando:** cada aseguradora tiene entre 10 y 20 reglas versionadas
  con su prueba unitaria, la evaluación devuelve categoría con reglas disparadas
  e insumos, y la agencia deriva por su regla sin ninguna rama de código.
- **Qué prueba:** que ninguna categoría pasa por el modelo.
- **Demostración:** el mismo caso evaluado en las tres aseguradoras dando tres
  categorías distintas, solo por configuración.

### B9 — Controles de cumplimiento y nodo de cierre (U10 `compliance`)

- **Semana:** 3. **Complejidad:** L. **Rama de pruebas:** evaluada.
- **Terminado cuando:** la guardia de salida sustituye por frase del catálogo, la
  petición de persona y la emergencia se detectan en cualquier idioma, la
  divulgación queda registrada y la revisión completa corre al cierre.
- **Qué prueba:** que se puede sostener cero respuestas fuera de alcance.
- **Demostración:** los casos adversariales RT-1, RT-2, RT-3, RT-5, RT-6, RT-8 y
  RT-15 en verde.

### B10 — Nodo de captura (U11 `intake`)

- **Semana:** 3. **Complejidad:** L. **Rama de pruebas:** evaluada.
- **Terminado cuando:** identifica sin revelar datos ajenos, extrae solo lo dicho
  con su evidencia por campo, normaliza lo dictado, pregunta en el orden fijo de
  la guía y lee la confirmación de cada bloque.
- **Qué prueba:** la exactitud de extracción por campo, que es la otra mitad de
  la preocupación de la calidad.
- **Demostración:** un relato desordenado con correcciones que termina en un caso
  con los siete campos y su evidencia.

### B11 — Runtime del grafo (U12 `graph-runtime`)

- **Semana:** 3. **Complejidad:** L. **Rama de pruebas:** evaluada.
- **Terminado cuando:** el estado tipado se compone de los contratos de los
  nodos, la transición es pura y cerrada, el ejecutor común aplica la política de
  fallo, hay puntos de control por caso con su aislamiento resuelto, `interrupt()`
  pausa hacia la bandeja, y el punto único de salida aplica los tres controles
  del turno.
- **Qué prueba:** que el orquestador es código y que el turno nunca espera al
  trabajo de fondo.
- **Demostración:** matar el proceso a mitad de conversación y reanudar sin
  repetir preguntas confirmadas.
- **Decisión pendiente que se resuelve aquí:** PA-3, el aislamiento de las tablas
  de puntos de control.

### B12 — Compuertas y reporte de evaluación (U21 `eval-gates`)

- **Semana:** 4. **Complejidad:** L. **Rama de pruebas:** evaluada.
- **Terminado cuando:** el reporte sale por caso, criterio e idioma con
  diferencia contra una línea base, comprobado con corridas de prueba; el
  segundo detector de datos personales es de mecanismo distinto y encuentra sus
  canarios; un cambio en los archivos de reglas dispara la compuerta; y el juez
  está construido con sus prompts versionados por criterio y su procedimiento de
  calibración, **ejecutable pero todavía sin calibrar**.
- **Qué prueba:** que las evaluaciones miden lo que importa y que una regresión
  se ve por caso y no escondida en un promedio. **Cierra la preocupación de la
  calidad** (DP-5).
- **Demostración:** una regresión inyectada en una corrida de prueba que el
  reporte señala por caso, nombrando su identificador.
- **Dependencia humana:** las etiquetas de DS-7 las pone Miguel.

**Lo que este Bolt no puede terminar, y por qué** (corrección del 2026-09-19).
Un caso de conversación se ejecuta por un **conductor de canal**, y el primero
llega con el chat en B14: en B12 no existe ninguno. Por eso, dos cosas que antes
figuraban aquí se mueven al cierre de B14, sin cambiar el orden de los Bolts:

| Se mueve | A cuándo | Por qué no cabe en B12 |
| --- | --- | --- |
| Calibrar el juez con TPR y TNR sobre DS-7 | Cierre de B14 | Calibrar exige conversaciones etiquetadas, y para producirlas hace falta un conductor |
| Publicar la línea base v0 | Cierre de B14 | Una línea base sin un solo caso de conversación ejecutado no es una línea base |

El contenido de la primera compuerta no cambia: la línea base v0 sigue siendo
condición para pasar a la voz, y sigue estando dentro del mismo bloque.

### B13 — Base de la aplicación web (U6 `web-shell`)

- **Semana:** 4. **Complejidad:** L. **Rama de pruebas:** determinista.
- **Terminado cuando:** están el sistema de diseño de la maqueta aprobada con sus
  modos claro y oscuro y su selector, el cliente tipado generado desde OpenAPI
  con su chequeo de deriva, las páginas de estado y el arnés de accesibilidad que
  corre cada pantalla visitable.
- **Qué prueba:** que las pantallas comparten una sola base y que ninguna impone
  su tema.
- **Demostración:** la página de espera con la instancia dormida en menos de
  3 segundos.

### B14 — Chat público y vista de comparación (U13 `chat`)

- **Semana:** 4. **Complejidad:** XL. **Rama de pruebas:** evaluada.
- **Terminado cuando:** el chat transmite por SSE, la divulgación y el aviso de
  no escribir datos reales salen antes de cualquier texto del visitante, los
  límites tienen modo degradado honesto, la cita es expandible con su resumen de
  traza, y el conductor de texto registra en el corredor de evaluaciones.
- **Qué prueba:** que la misma conducta sale por un canal real, y que desde aquí
  los casos de DS-2 y DS-6 corren por el adaptador de texto.
- **Demostración:** una conversación completa en cada idioma, con su cita
  expandida.
- **Al cerrar este Bolt** (corrección del 2026-09-19), y solo entonces, es
  posible lo que B12 dejó pendiente: calibrar el juez contra las etiquetas de
  DS-7 y **publicar la línea base v0** con su commit y su fecha. Es el primer
  momento del plan en que un caso de conversación se puede ejecutar de verdad.
- **Lo que la regla de corte quita primero:** US1.20 (continuidad de voz a chat,
  S2) y US2.9 (vista de comparación, S5) son historias de este Bolt; cortarlas lo
  adelgaza sin eliminarlo.

### B15 — Bandeja y vistas de caso (U14 `inbox`)

- **Semana:** 4. **Complejidad:** XL. **Rama de pruebas:** evaluada.
- **Terminado cuando:** la cola filtra por estado, canal, idioma y prioridad; la
  vista de caso muestra completitud, transcripción, cláusulas, regla, controles y
  traza; la corrección deja rastro; la decisión con comentario reanuda el grafo; y
  el enlace firmado abre solo su caso y nunca la lista.
- **Qué prueba:** que la persona decide, que es el principio que más diferencia
  al proyecto.
- **Demostración:** un caso derivado que se aprueba en la bandeja y se cierra, con
  su actualización llegando al chat.

### B16 — Operación de la demo (U20 `demo-operations`)

- **Semana:** 4. **Complejidad:** M. **Rama de pruebas:** evaluada.
- **Terminado cuando:** un comando aprovisiona una aseguradora desde su carpeta
  con el corpus ingerido, siembra un caso en cada estado, y el reinicio nocturno
  ejecuta el contrato de borrado de cada dueño dejando su `ResetRun`.
- **Qué prueba:** que se puede publicar una superficie pública sin acumular datos
  de personas reales.
- **Demostración:** el reinicio corriendo y la bandeja pública quedando sin casos
  de visitantes, con el registro de gasto intacto.
- **Por qué va antes de publicar:** ninguna superficie pública se publica sin el
  reinicio funcionando (`team.md`, Deployment).

### B17 — Evidencia pública (U22 `public-evidence`)

- **Semana:** 4. **Complejidad:** M. **Rama de pruebas:** determinista.
- **Terminado cuando:** el panel publica las cinco cifras con su fecha y su
  commit, el panel de gasto muestra por caso, proveedor, mes y ventana, y las
  secciones generadas del README incluyen "Cómo falla".
- **Qué prueba:** que las cifras que se publican salen del último reporte y no de
  una diapositiva.
- **Demostración:** el panel de cifras con la línea base v0.

> **Primera compuerta de contenido (el "día 30" del PRD).** No se sigue a la voz
> hasta que sea cierto: línea base v0 publicada con las compuertas duras en
> verde, chat y bandeja en vivo con el checklist del segundo día cumplido, y
> validación con dos o tres personas del perfil hecha o agendada. Es una
> condición, no una fecha (DP-8).

### B18 — Adaptadores de transcripción y síntesis (U15 `speech-providers`)

- **Semana:** 5. **Complejidad:** M. **Rama de pruebas:** determinista.
- **Terminado cuando:** los adaptadores de Deepgram, Cartesia y la voz de
  respaldo están detrás de sus puertos con prueba de contrato y de latencia, y la
  configuración de voz por aseguradora se valida.
- **Qué prueba:** que cambiar proveedor, voz o modelo es configuración.
- **Demostración:** oír a Catalina decir una frase desde el propio aplicativo, a través del adaptador de síntesis (DP-14); y una configuración rota que apaga la voz y deja vivo el chat.
- **No empieza sin:** el experimento de voz (DP-2).

### B19 — Llamada de voz desde el navegador (U16 `voice-call`)

- **Semanas:** 5 y 6. **Complejidad:** XL. **Rama de pruebas:** evaluada.
- **Terminado cuando:** la llamada entra por el navegador con su apertura
  declarando que es inteligencia artificial y que queda transcrita, el reporte
  hablado funciona, la agente para en menos de 300 ms ante interrupción, los
  silencios y la retoma tras corte están cubiertos, y los cuatro eventos de
  latencia llegan a la traza.
- **Qué prueba:** los dos números que el proyecto publica: fin del habla a primer
  audio por debajo de 800 ms p95, y parada por debajo de 300 ms. **Atiende la
  preocupación de la voz** (DP-5).
- **Demostración:** una llamada completa en inglés con interrupción marcada y su
  gráfica de latencias.
- **No empieza sin:** el experimento de voz. **Dependencia humana:** grabaciones
  de DS-5 con consentimiento.

### B20 — Enlace público de la voz (U17 `voice-public-link`)

- **Semana:** 7. **Complejidad:** M. **Rama de pruebas:** determinista.
- **Terminado cuando:** los límites (3 minutos, 1 llamada por visitante al día,
  15 en el sitio) están en la aplicación **y** en el proveedor, el aviso a los 30
  segundos y la derivación al límite funcionan, la voz se decide antes de cada
  llamada y no cambia a mitad, y el techo rechaza llamadas nuevas con el mensaje
  del catálogo.
- **Qué prueba:** que la voz se puede publicar sin que un visitante agote el
  presupuesto. **Cierra la preocupación del costo** (DP-5).
- **Demostración:** el enlace en vivo con sus límites, probado con clave de tope
  mínimo y acumulado forzado, sin gastar el presupuesto real.

### B21 — Voz en español y cambio de idioma (U18 `voice-spanish`)

- **Semana:** 9. **Complejidad:** L. **Rama de pruebas:** evaluada.
- **Terminado cuando:** la apertura y el reporte en español cumplen las mismas
  metas que en inglés con la misma voz, el cambio de idioma funciona en los dos
  sentidos y la detección automática atiende el idioma mixto.
- **Qué prueba:** la paridad por idioma, reportada lado a lado y nunca como
  promedio.
- **Demostración:** una llamada en español con las mismas latencias publicadas.
- **Dependencia humana:** DS-5 en español con tres voces paisas, y la sesión de
  escucha de la semana 9.
- **Lo que la regla de corte quita:** US1.32 (S4) es historia de este Bolt.

### B22 — Cotización con elegibilidad (U19 `quote`)

- **Semana de referencia:** 10, después de la voz.
- **Complejidad:** M. **Rama de pruebas:** evaluada.
- **Terminado cuando:** la solicitud se captura en la misma conversación sin
  añadir nodos al grafo, las reglas dan elegible, no elegible o derivación, y la
  banda indicativa no contiene ningún importe.
- **Qué prueba:** que el mismo grafo atiende un segundo flujo sin crecer.
- **Demostración:** una cotización elegible y una derivada, en los dos idiomas.
- **Es el primer Bolt completo que la regla de corte elimina** (S1), si Miguel
  decide reducir alcance.

## Lo que no es un Bolt

Trabajo del plan que no es construcción de software y que se ejecuta junto a los
Bolts:

| Actividad | Cuándo | Por qué no es un Bolt |
| --- | --- | --- |
| Experimento de voz (librería, transporte, voz de respaldo) | Semana 2, en paralelo | Es una decisión con datos; su resultado actualiza ADR-008 y ADR-009 |
| Validación externa con dos o tres personas | Cuando el chat y la bandeja estén en vivo | Actividad con personas; su resultado entra como ajustes al PRD |
| Piloto cerrado con tres a cinco personas del perfil | Semana 8 | Actividad con personas; sus objeciones entran al README |
| Sesión de escucha de la voz con tres personas de Medellín | Semana 9 | Confirma o cambia la voz principal por configuración |
| Red-team 1, 2 y 3 | Semanas 6, 9 y 11 | Cada hallazgo se convierte en caso de DS-6 dentro de la unidad que lo arregla |
| **README narrativo** (las seis secciones que no se generan: qué hace, qué no hace, arquitectura, diagrama del grafo, decisiones, y la tabla de principio a control a evidencia) | Semana 11, cuando ya existe todo lo que describe | No es conducta del sistema. **Añadido el 2026-09-19:** antes solo se mencionaba de pasada en el calendario, sin dueño ni definición de terminado. Lo escribe Miguel con esta sesión; se da por hecho cuando las seis secciones existen, cada afirmación tiene su artefacto detrás (P7) y ninguna describe algo que no esté construido. Las otras dos secciones —"Cómo falla" y las cinco cifras— las **genera** U22 desde el último reporte y se actualizan solas |
| Video v1 y video final | Semanas 7 y 11 | Entregable de MOD-15, marcado N/A en la trazabilidad |
| Landing pasadas 1 y 2 | Semanas 7 y 11 | Entregable de MOD-15, fuera del alcance del aplicativo |
| Intent `infra` (tubería de despliegue, entornos, observabilidad de plataforma) | Semanas 3 y 4 | Otro intent, que invoca el mismo `verify.sh` |
