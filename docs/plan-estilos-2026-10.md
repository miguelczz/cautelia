# Plan: pulido de estilos del aplicativo

Decisiones de Miguel del 2026-10-06, a partir de dos capturas de producción
(`cautelia.app/home` y `cautelia.app/metrics` con la demo dormida). Este documento
fija **qué se cambia, por qué y cómo se comprueba**, antes de tocar código. Lo que
cambia criterios ya aprobados está en su propia sección, con fecha, como decisión
de Miguel.

## Lo que pidió, punto por punto

| # | Pedido | Dónde se resuelve |
| --- | --- | --- |
| 1 | En computador, cada pantalla cabe en una sola vista, sin scroll de página; en tablet y teléfono puede ser distinto | §1 |
| 2 | El pie, del mismo color que el fondo; con el crédito «Miguel Zuluaga» y su LinkedIn, ordenado y bonito | §2 |
| 3 | El idioma elegido no se pierde: persiste | §3 |
| 4 | Esqueleto de carga en **todas** las páginas, y un loader donde corresponda; la persona no tiene que saber que la demo despertaba | §4 |
| 5 | «Resultados medidos» pasa a botón, a la derecha de la barra | §5 |
| 6 | Bajo las tres aseguradoras, el enlace «Qué puedes probar» pasa a botón a la derecha y lleva a una **página nueva** con el paso a paso y el instructivo | §6, §9 |
| 7 | Se borra «Si es tu primera vez…» y «Cuando la agente te pida la póliza…»; el título pasa a «Elige una aseguradora y cuenta lo que pasó, por chat o por voz», y se borra la línea que lo repetía | §6 |
| 8 | El botón «Llamar» con borde y letra del color de cada aseguradora | §7 |
| 9 | Los textos de cada aseguradora, más claros y cortos; si los chats no se diferencian, decirlo | §8 |

## Principios con los que decido lo que no dijo

1. **Quien llega no descifra** (norma permanente de Miguel, 2026-09-20). Si hay
   que detenerse a entender qué es algo, está mal, aunque sea defendible técnicamente.
2. **Nada queda sin cargar, y nada se explica con palabras de implementación.**
   «La demo está despertando» cuenta un detalle de infraestructura que a la
   persona no le sirve y que, además, suena a que algo falló. Lo que necesita saber
   es solo que el sistema está en proceso. Eso lo dice un esqueleto con la forma de
   lo que viene, no una frase.
3. **La landing manda** (2026-10-06). El aplicativo copia su diseño y comparte con
   ella lo que comparten un mismo dominio y una misma identidad; el idioma es una de
   esas cosas.
4. **Una pantalla en computador donde el contenido cabe; scroll honesto donde no.**
   Una tabla de cifras o una cola de casos no caben en una vista sin recortar datos,
   y recortar es peor que desplazar. El criterio es: nunca se corta contenido.
5. **Nada se promete que no está construido.** Las descripciones de las
   aseguradoras salen de sus reglas reales (`app/config/tenants/*/rules`), no de lo
   que suena bien.
6. **La accesibilidad no baja.** Contraste AA en los dos modos, foco visible,
   objetivos de 44 px, movimiento reducido respetado, lector de pantalla informado.

## Decisiones que cambian criterios aprobados

| Antes | Ahora | Razón |
| --- | --- | --- |
| BR1.6: solo la bandeja recuerda el idioma; «ninguna otra pantalla lo hace» | Todas las pantallas lo recuerdan | Pedido expreso; además, los enlaces del inicio recargan la página y el idioma se perdía |
| BR3.5 / SEC-U6.5: la interfaz guarda solo `untangle.theme` y `untangle.locale` | Guarda `untangle.theme` y el idioma, que se comparte con la landing (`cautelia-lang`) | Mismo dominio, una sola identidad; ver §3 |
| Espera del proceso: página de estado «La demo está despertando» con texto, y 1 s en blanco antes (`CHECKING_GRACE_MS`) | Esqueleto de la página pedida desde el primer cuadro, más un hilo de progreso; sin texto visible | Principio 2 |
| NFR16.3: el **título** de la espera pinta en menos de 3 s | El **esqueleto** de la espera pinta en menos de 3 s (mismo umbral) | Ya no hay título que pintar; el umbral no baja |
| «Qué puedes probar» plegable en el inicio | Página propia «Cómo funciona» | Pedido expreso |
| Navegación del teléfono detrás de un botón «Menú» | Los botones de la barra se ven siempre | Con uno o dos destinos, un menú cuesta un toque y no ahorra nada |
| Inicio: tira numerada «Cómo funciona» bajo el título | Sale del inicio y vive en la página nueva | Pedido expreso (punto 7) |

Se escribe también en `project.md` como corrección cuando Miguel apruebe el plan
(el ritual de aprendizajes es el único camino para tocar esa memoria).

## §1 Una sola pantalla en computador

**Hoy.** El marco usa `min-h-dvh`: el pie queda debajo del contenido y, con la
altura de un portátil, la página se desplaza unos píxeles.

**Cambio.**
- Una variante de Tailwind, `roomy`: ancho ≥ 64 rem **y** alto ≥ 42 rem. Es el
  «computador con espacio»; por debajo (teléfono, tablet vertical, ventana baja) la
  página fluye y se desplaza como siempre.
- Una marca de ruta, `staticData: { onePage: true }`, igual que `fill` y
  `persistLocale` hoy: la ruta lo declara y el marco lo lee. En `roomy`, el marco
  mide `h-dvh`, el contenido ocupa el espacio entre barra y pie y se centra
  verticalmente; los espacios y el tamaño del título se calculan con `clamp()` sobre
  la altura de la ventana, para que lo mismo quepa en 1080, 900 y 720 px de alto.
- Si aun así no cabe (alto entre 42 rem y lo que el contenido pida, o zoom del
  navegador), el contenido se desplaza **dentro de `main`**, con barra y pie
  visibles: no se recorta nada (WCAG 1.4.10, reflujo).
- Pantallas con `onePage`: inicio y «Cómo funciona». Las páginas de estado son tan
  cortas que ya caben sin marca. El chat ya llena la vista (`fill`). **Sin
  `onePage`, y por el principio 4**: cifras, gasto, comparación, bandeja, caso y traza.

**Se comprueba.** Prueba de la ruta (`staticData`), y captura real a 1440×900,
1366×650, 1920×1080 y 1024×768 con el navegador integrado: sin barra de
desplazamiento de página donde debe haber una sola vista.

## §2 Pie

**Hoy.** `bg-bar` (más oscuro que el fondo) y una sola línea.

**Cambio.**
- Sin color propio: el pie hereda el fondo de la página y conserva solo su línea
  superior (`border-hairline`).
- Una fila ordenada: a la izquierda «Demostración de portafolio con datos
  sintéticos.»; a la derecha, «Creado por **Miguel Zuluaga**» y un enlace con el
  icono de LinkedIn. En teléfono se apilan, alineados a la izquierda.
- El enlace es el mismo de la landing (`https://www.linkedin.com/in/miguelzuluaga/`),
  se abre en pestaña nueva con `rel="noopener noreferrer"`, mide 44 px y su nombre
  accesible dice «Miguel Zuluaga en LinkedIn». El nombre y la dirección son datos de
  autoría, no copy: viven en `shared/site/author.ts`; las palabras («Creado por»)
  salen del catálogo en los dos idiomas.
- El pie de la espera (antes de que exista el enrutador) lo lleva también: así no
  aparece de golpe al cargar.

**No se toca** la barra superior (conserva su tono propio): el pedido fue solo el pie.

## §3 El idioma persiste

**Hoy.** El idioma vive en el estado de la pestaña y solo se guarda en la bandeja.
Los botones «Abrir chat» y «Llamar» son enlaces comunes: recargan la página y el
idioma elegido se pierde.

**Cambio.**
- Cada elección con el selector se guarda, en cualquier pantalla.
- Al abrir, el idioma se resuelve así: **elección guardada → idioma de la landing →
  idioma del dispositivo**. La elección explícita gana a la predeterminada de una
  aseguradora (BR2.2 sigue valiendo para quien no ha elegido).
- La landing guarda su idioma en `cautelia-lang` desde su primer arranque (también el
  detectado, no solo el elegido). Comparten dominio, así que el aplicativo lo lee
  como **semilla** —no como elección explícita, para que la predeterminada de una
  aseguradora siga aplicando— y, cuando la persona elige, escribe en las dos claves
  (`untangle.locale` y `cautelia-lang`): quien elige inglés en la landing entra en
  inglés, y quien lo cambia aquí lo encuentra así al volver.
- Se retira la opción `persist` del selector, la marca `persistLocale` de las rutas
  y la prueba que exigía que el chat **no** recordara el idioma.
- Almacenamiento bloqueado (navegación privada): la elección vale para la pestaña y
  no hay error visible, como hoy con el modo.

**Se comprueba.** Pruebas del proveedor de idioma (orden de resolución, escritura en
las dos claves, almacenamiento bloqueado), la lista de claves permitidas del arnes
(`ALLOWED_STORAGE_KEYS`) y una prueba de recorrido: elegir inglés, navegar con
recarga, seguir en inglés.

## §4 Esqueletos y loaders: la regla y su porqué

**La regla.** *Toda pantalla tiene, desde el primer cuadro, algo que dice «esto se
está haciendo» con la forma de lo que viene.* Un esqueleto no es decoración: es la
promesa de la estructura. Si la forma coincide con la de la página real, el paso de
esqueleto a contenido no mueve nada y la persona no percibe una espera, sino un
llenado.

**Qué usar en cada caso** (la tabla que sigo cuando aparezca un caso nuevo):

| Situación | Patrón | Porqué |
| --- | --- | --- |
| Una pantalla espera sus datos y conozco su forma | **Esqueleto** de esa pantalla, con título y descripciones reales si son estáticos | Mantiene la estructura y dice dónde está la persona |
| El proceso aún no responde (arranque en frío) | El **mismo esqueleto** de la ruta pedida + un **hilo de progreso** bajo la barra; sin texto visible | La espera puede durar segundos; el hilo dice «sigue vivo» sin contar el porqué |
| La persona hizo algo y espera el resultado (enviar, llamar, reintentar, decidir) | **Spinner dentro del botón** (ya existe: `loading`) | La acción es suya; el control que pulsó responde |
| La agente prepara su respuesta | **Indicador de escritura** en la conversación | La forma de la respuesta no se conoce |
| Contenido ya visible que se refresca | Nada que sustituya el contenido | Cambiar contenido por esqueleto sería un retroceso |
| Falla de verdad (60 s sin respuesta, error) | Página de estado con texto y «Reintentar» | Aquí sí hay algo que decir y algo que hacer |

**Cambio.**
- `shared/ui/page-skeletons.tsx`: un esqueleto por familia de pantalla —inicio,
  paneles (cifras y gasto), comparación, chat, llamada, bandeja, caso, genérico— y
  una función pura `skeletonKindForPath(ruta)` que dice cuál corresponde a una
  dirección. Cada uno es una región `role="status"` con `aria-busy` y un texto solo
  para lectores de pantalla («Cargando»); con movimiento reducido no late.
- **La espera del proceso** deja de ser una página de estado. `checking` y `waking`
  dibujan el marco real (marca, selectores, pie) con el esqueleto de la ruta pedida y
  el hilo de progreso, desde el primer cuadro; se quita el segundo en blanco
  (`CHECKING_GRACE_MS`). Solo `unavailable` (60 s) conserva texto, porque ahí sí hay
  una falla y una acción. Se retiran el tipo `waking` y sus textos.
- **Las pantallas** dibujan ese mismo esqueleto mientras piden sus datos: se
  sustituyen los «Cargando» sueltos de la traza, la bandeja y el caso, y el
  `Suspense` que carga el trozo de la ruta usa el esqueleto de la ruta, no uno
  genérico.
- **La barra** reserva el lugar del botón de navegación con un esqueleto mientras el
  directorio del sitio llega, para que no aparezca de golpe.
- **Orden:** esqueleto de la ruta pedida → esqueleto de la pantalla → contenido: es
  el mismo dibujo las dos primeras veces.

**Riesgo que declaro.** Sin texto, una espera de 40 segundos puede parecer una
página rota a quien evalúa. Mantengo tu criterio (no contar el porqué), y dejo
anotado que, si ocurre, la opción es un mensaje neutral a partir de los 20 s
(«Está tardando un poco más de lo normal»), que no habla de infraestructura. No se
incluye salvo que lo pidas.

**Se comprueba.** Pruebas por esqueleto y de `skeletonKindForPath` (cada ruta del
enrutador tiene el suyo: el registro de completitud falla si una ruta queda sin
esqueleto), el reductor de espera sin el estado en blanco, y el arnes de
accesibilidad sobre la espera. La medición NFR16.3 pasa a medir el esqueleto.

## §5 Barra superior

**Hoy.** «Resultados medidos» es un enlace de texto a la izquierda, junto a la marca.

**Cambio.** La marca queda sola a la izquierda. A la derecha, en este orden:
**botón de navegación** (secundario, con icono de gráfica, 44 px), selector de
idioma, selector de modo. Si hay más de un destino (p. ej. «Cómo está hecho»),
son botones iguales. El botón de la página actual lleva `aria-current="page"` y
estado activo. En teléfono los botones pasan a una segunda fila y no hay «Menú».

## §6 Inicio

- El título de la sección pasa a ser la frase pedida, con las tres variantes que ya
  existen según los canales montados («por chat o por voz» / solo chat / solo voz).
  Sin canales montados queda «Las aseguradoras de la demostración».
- Se borran: la tira numerada, «Si es tu primera vez, empieza por el chat.» y «Cuando
  la agente te pida la póliza…». La indicación de usar la póliza de ejemplo no se
  pierde: pasa a la página nueva, y cada fila sigue mostrando su «Póliza de ejemplo»
  con el número.
- Bajo las filas, a la derecha: botón **«Cómo funciona»** hacia la página nueva y, si
  está montada, el botón de comparación. Se retira el plegable «Qué puedes probar»
  (su contenido va a la página nueva).
- El estado de carga del inicio usa el esqueleto de §4.

## §7 Botón «Llamar»

Variante nueva del botón, `tenant-outline`: fondo transparente, borde y texto en el
acento de la aseguradora (`--ut-tenant`, que ya cambia con el modo), y velo del 10 %
del mismo color al pasar el puntero. «Abrir chat» sigue relleno: es la acción
principal. Contraste del acento sobre el fondo, medido en los seis casos (tres
aseguradoras × dos modos): todos ≥ 4,5:1; se fija con una prueba.

## §8 Descripciones de las aseguradoras

**Qué encontré.** Los tres chats **sí difieren**, y no solo en el idioma. Lo que es
igual: la agente (Catalina), las preguntas y que las respuestas citan la póliza de
esa aseguradora. Lo que cambia, según sus reglas reales:

| Aseguradora | Idioma con que abre | Qué pasa con tu reporte | Algo propio |
| --- | --- | --- | --- |
| Agencia Castilla | inglés | Es una agencia: no decide; **lo pasa a la aseguradora que emitió la póliza** | — |
| Seguros Aburrá | español | **Una persona revisa todos los casos**; ninguno se cierra solo | — |
| Autos Poblado | inglés | **Cierra sin revisión los reportes simples** (sin heridos ni datos de terceros pendientes) | Cotiza un seguro |

**Textos nuevos** (una frase corta cada una; el mismo contenido, en los dos idiomas):

- Agencia Castilla: «Agencia: no decide los casos, los pasa a la aseguradora que
  emitió la póliza. Atiende en inglés primero.»
- Seguros Aburrá: «Prudente: una persona revisa todos los casos antes de cerrarlos.
  Atiende en español primero.»
- Autos Poblado: «Ágil: cierra sin revisión los reportes simples, y también cotiza.
  Atiende en inglés primero.»

Se cambian las tres claves `insurer.character.*` del catálogo; la tabla completa
(lo igual y lo que cambia) va en la página nueva (§9).

## §9 Página «Cómo funciona»

Ruta `/how-it-works`, `onePage`, en los dos idiomas. Cada paso aparece **solo si lo
construido lo permite** (BR4.1): se lee del directorio del sitio qué canales y
enlaces están montados, como el inicio.

1. **Qué es.** Una frase: una agente atiende a quien tuvo un choque y deja el caso
   listo para que una persona lo decida; aseguradoras y pólizas ficticias.
2. **El recorrido, en cuatro pasos** (en fila en computador): elige una
   aseguradora → cuenta lo que pasó, por chat o por voz (aquí va la indicación de
   la póliza de ejemplo) → recibes un enlace a tu caso → decides tu caso como lo
   haría un ajustador.
3. **Qué puedes probar** (la lista de hoy): reportar por chat, por voz, preguntar si
   tu póliza cubre algo y ver la cláusula, interrumpir a la agente, decidir tu caso.
4. **Qué cambia entre aseguradoras**: las tres filas con el texto de §8, tomadas del
   mismo directorio, y la línea de lo que es igual en las tres.
5. **Antes de empezar**: es una demostración; no escribas datos reales.
6. Un botón principal «Elegir una aseguradora» que vuelve al inicio.

Se registra en el enrutador **y** en el registro del arnes (`e2e/visitable-routes.ts`),
que es lo que exige la comprobación de completitud.

## Tandas y orden

Cada tanda termina con sus pruebas de unidad y un commit a `main`, sin apilar la
siguiente sobre una roja (práctica del equipo).

1. **Marco:** §2 pie, §3 idioma, §5 barra, §7 variante del botón, `roomy` (§1).
2. **Inicio y guía:** §6, §8, §9, `onePage` en las rutas.
3. **Esqueletos:** §4 completo, retiro de la página «despertando», arnes y medición.

Los textos nuevos entran al catálogo en español e inglés en la misma tanda que su
consumidor (el chequeo del catálogo exige paridad y consumidor literal), y las
claves que dejan de usarse se borran con él.

## Cómo se comprueba

- Pruebas de unidad de lo tocado, por tanda (`vitest` de `src/app`, `src/pages` y
  `src/shared`), y el chequeo del catálogo.
- `mise run verify:rapido` **antes de cada empuje** (práctica de Miguel, 2026-10-06).
- Captura real en el navegador integrado, en claro y oscuro, en computador y
  teléfono, de cada pantalla tocada.
- Lo que solo ve GitHub Actions (accesibilidad con tres motores, cobertura,
  tiempos) lo mira la compuerta tras el empuje; si se pone en rojo, es un incidente
  y se arregla hacia adelante.

## Fuera de esta tanda

- La barra superior conserva su tono; el pedido fue el pie.
- Las pantallas de cifras, gasto, comparación y bandeja siguen desplazándose.
- No se toca la landing.
- No se añaden mensajes de espera (ver el riesgo de §4).

## Estado (2026-10-06)

Las tres tandas están hechas y commiteadas en `main`. Las dos primeras ya están en
`origin/main`: la otra sesión las empujó junto con su trabajo. La tercera y este
documento siguen solo en local:

| Tanda | Commit | Qué quedó |
| --- | --- | --- |
| 0 | `c494190` | Este plan |
| 1 · Marco | `33cfd38` | Pie sin color propio con el crédito, idioma que persiste y se comparte con la landing, botones de navegación a la derecha, `tenant-outline`, `roomy` y `onePage` |
| 2 · Inicio y guía | `5b6b815` | Título nuevo, sin los textos viejos, «Cómo funciona» a la derecha, descripciones por lo que cambia, página `/how-it-works` |
| 3 · Esqueletos | `0e5bacd` | Un esqueleto por familia de pantalla, espera sin texto con hilo de progreso, `waking` retirado, arnés y medición NFR16.3 |

**Comprobado.** 493 pruebas de pantalla, tipos, lint (sin errores nuevos), formato y
los siete chequeos del catálogo. A mano, en el navegador integrado y con una API de
mentira: el inicio cabe sin desplazamiento a 1440×800, 1366×680 y 1024×672 (el
mínimo de `roomy`); la guía cabe a 1440×800 y a 1366×768 en español con los cuatro
pasos; el esqueleto de la espera mide, en el alto de cada bloque, lo mismo que el
inicio real (diferencia de 10 px en el total, de 5 px arriba); el teléfono pasa los
botones a su propia fila. Lo medido del peso antes de pintar: unos 164 KB con
brotli, bajo los 200 KB de PERF-U6.1.

**Lo que no se pudo comprobar aquí y mira GitHub Actions** (la práctica del equipo:
nada de verificación pesada en el portátil): el arnés de accesibilidad con los tres
motores (`mise run a11y`), la medición NFR16.3 con red y CPU lentas, la cobertura y
el resto del guion.

**Decisiones que tomé donde el pedido no decía** (se pueden vetar):

1. El idioma de la landing entra como semilla y no como elección, para que el idioma
   por defecto de una aseguradora siga aplicando a quien nunca eligió; la elección de
   la persona gana a todo.
2. Los destinos de la barra pasan a botones visibles también en teléfono, sin «Menú».
3. Las descripciones de las aseguradoras salen de sus reglas reales; «Atiende en … primero»
   pasó a «Empieza en …» porque se entiende sin explicación.
4. La guía lee del directorio qué canales y enlaces están montados, igual que el
   inicio: no promete lo que no hay.
5. No se añadió ningún mensaje de espera (ver el riesgo de §4).
6. Se creó `shared/site/author.ts` para el nombre y la dirección de LinkedIn. El
   `.dockerignore` tragaba esa carpeta por llamarse `site`; la otra sesión lo corrigió
   en `f6735ed`.

**Pendiente de Miguel:** que apruebe empujar la tercera tanda y que confirme las correcciones
que van a `project.md` por el ritual de aprendizajes (BR1.6 reemplazada, la espera sin
texto y el idioma compartido con la landing).
