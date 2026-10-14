# Preguntas — Units Generation

Esta etapa parte el aplicativo en **unidades**: las piezas que en Construcción
se diseñan, se programan y se prueban una a la vez. Para cada unidad dice qué
componentes y qué historias contiene, de qué otras unidades depende y qué tipo
de pieza es (servicio, interfaz, librería o empaquetado), porque eso decide qué
documentos de diseño le tocan. No decide en qué orden se construyen: eso es de
Delivery Planning, la etapa 2.9.

Casi todo ya lo fijan los documentos aprobados, y esas decisiones las tomo yo
con su razón y las verás en la aprobación:

- **Un solo despliegue.** El aplicativo es un monolito modular que corre en un
  solo proceso, con la interfaz servida desde el mismo origen (decisiones de
  arquitectura 1, 2 y 4). No hay unidades que se desplieguen por separado.
- **Cómo se hablan las unidades.** Por llamadas dentro del proceso, por la base
  de datos a través del punto único de sesión con aislamiento por aseguradora, y
  por la API tipada entre el servidor y las pantallas. No hay colas ni eventos.
- **Una a la vez.** Tu regla de Practices Discovery, en tus palabras: "haremos
  la creación de componente Uno A uno ... en lugar de dejar un componente a
  medias". El mapa de dependencias muestra qué unidades no dependen entre sí,
  pero no se construyen en paralelo.
- **Lo que los documentos obligan a separar.** El corredor de evaluaciones
  existe antes del primer caso de prueba (práctica de pruebas); la voz de
  respaldo y la librería de voz esperan al experimento 1; la voz en español es
  una capa aparte de la voz en inglés (así se escribieron las historias); la
  cotización es un Should que la regla de corte del PRD quita primero; y el
  borrado nocturno de datos de visitantes tiene que funcionar antes de publicar
  el chat, aunque la voz todavía no exista.

Quedan dos decisiones con más de una respuesta razonable, que cambian cómo
avanza la construcción y cuándo se puede usar cada cosa.

## Q1 — De qué tamaño son las piezas que se construyen una a la vez

Tu regla dice que primero va una base sólida y después cada pieza completa antes
de empezar la siguiente, pero no fija el tamaño de la pieza. Hay 87 historias y
23 componentes. Cada unidad recorre en Construcción su diseño funcional, sus
requisitos y diseño no funcionales, su diseño de infraestructura y su código,
cada paso con tu aprobación. Unidades pequeñas dan revisiones cortas y más
libertad para ordenar; unidades grandes dan pocas revisiones, pero cada diseño
cubre muchas historias a la vez.

A. Piezas pequeñas por capacidad: 22 unidades de 1 a 7 historias. Siguen los
   componentes de Domain Design, juntan los que siempre se construyen y se
   prueban juntos (por ejemplo, el motor de reglas con el nodo que le pide la
   categoría) y separan lo que los documentos aprobados obligan a hacer en
   momentos distintos (por ejemplo, la voz en inglés y la voz en español). Cada
   pieza termina probada por sí sola y cada revisión es corta (recomendada)
B. Piezas medianas: unas 15 unidades. Además juntan capacidades vecinas, como
   la captura con el grafo (11 historias), las reglas con el cumplimiento, o la
   redacción de datos personales con el caso. Menos aprobaciones, cada una más
   larga, y menos libertad para ordenar
C. Las piezas grandes del plan del PRD: unas 9 unidades (base, pólizas y citas,
   agentes, bandeja y chat, evaluaciones y observabilidad, voz en inglés, voz en
   español, cotización y operación de la demo). Pocas aprobaciones, pero cada
   diseño cubre entre 10 y 20 historias
X. Other (please specify)

[Answer]: A

## Q2 — Dónde se construyen las pantallas

La interfaz es una sola aplicación de React con las pantallas de las maquetas
aprobadas: chat, consola de llamada, comparación, bandeja, vistas de caso,
paneles y páginas de estado. Se puede construir cada pantalla con la capacidad
que muestra o todas juntas. El plan del PRD publica el chat y la bandeja
alrededor del día 30, antes de que exista la voz.

A. Cada pantalla con la capacidad que muestra: el chat con su página, la bandeja
   con sus vistas, la voz con su consola y las evaluaciones con su panel de
   cifras. Una unidad aparte arma lo común a todas: colores y modos claro y
   oscuro, cliente de la API, textos por idioma, páginas de estado y la revisión
   automática de accesibilidad. Cada capacidad termina usable en el navegador, y
   el chat y la bandeja se pueden publicar sin esperar a la voz (recomendada)
B. Todas las pantallas en una sola unidad, construida cuando ya existen el chat,
   la bandeja, la voz y los paneles: un solo diseño de interfaz, pero nada se
   puede usar en el navegador hasta que exista también la voz
C. Pantallas en unidades de interfaz separadas de su servidor (por ejemplo,
   "servidor del chat" y "pantallas del chat") que la planificación junta
   después: cada unidad es de un solo tipo, pero la mayoría de las historias
   quedan partidas entre dos unidades
X. Other (please specify)

[Answer]: A
