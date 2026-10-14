# Preguntas — Requisitos no funcionales de U1 `workspace`

Esta unidad registra dos metas medibles del proyecto, según la tabla de Units
Generation: **NFR18** (piso de cobertura del 80 %) y **NFR21** (de clonar el
repositorio a ver el reporte de evaluación en menos de 15 minutos). Cada una
necesita su valor esperado y **el comando que produce su valor real**, para que
aparezca como fila propia en la matriz de verificación de Build and Test.

**Fuentes consumidas.**
`../functional-design/functional-spec.md` (los tres flujos de la unidad) y
`../functional-design/rules.md` (las 21 reglas, en particular BR1.1, BR1.2 y
BR1.8), `../../../inception/requirements-analysis/requirements.md` (NFR17, NFR18
y NFR21 con su valor esperado),
`../../../inception/contract-design/contract-summary.md` (C-27 y C-28, que fijan
los artefactos generados y su chequeo de deriva) y
`../../../../codekb/untangle/technology-stack.md` (lo que ya existe en el
repositorio: la landing, sin código de aplicativo).

Casi todo lo fijan documentos aprobados y lo aplico sin preguntar: el escaneo de
secretos como primer trabajo del flujo, la lista de exclusión de la cobertura
(`site/`, corpus y datasets generados, migraciones), que el umbral vive en el
manifiesto y hace fallar el comando, y que el guion único de verificación corre
en el orden que fija `team.md`.

Quedan **cuatro decisiones** que ningún documento resuelve y que cambian lo que
se construye o lo que la compuerta mide.

## Q1 — Cómo se suma la cobertura de dos lenguajes en un solo número

`unit-of-work.md` dejó esta pregunta explícitamente a esta etapa. El proyecto
tiene dos proyectos con herramientas distintas (Python y TypeScript), y el piso
del 80 % está escrito como **agregado sobre el código del aplicativo**.

A. **Un solo número, ponderado por líneas** (recomendada): cada herramienta
   produce su reporte en un formato común, un paso los combina sumando líneas
   cubiertas sobre líneas totales de los dos proyectos, y ese número es el que se
   compara contra el 80 %. Es literalmente lo que dice la regla, y una pieza
   grande y bien probada no puede tapar a una pequeña y descuidada... pero
   tampoco al revés, así que hay que mirar también el piso por módulo crítico
B. **Dos umbrales separados**, uno por lenguaje, ambos al 80 %: más simple de
   montar y más estricto, porque ninguno puede compensar al otro. El costo es que
   deja de existir "el número" del proyecto, que es el que se publica
C. **Un solo número, promediando los dos porcentajes**: el más fácil de calcular
   y el que engaña, porque un proyecto de 200 líneas pesa igual que uno de 20.000
X. Other (please specify)

[Answer]: A

## Q2 — Qué entra dentro de los 15 minutos de NFR21

El criterio AC4.4.1 dice "de clonar el repositorio a ver el reporte, en menos de
15 minutos, en una máquina limpia". Falta decidir qué se cuenta, porque eso
cambia si la meta es alcanzable o no.

A. **Desde el clon hasta el reporte, con todo lo que haga falta dentro**
   (recomendada): instalar herramientas y dependencias, levantar los servicios
   locales, correr el subconjunto declarado y ver el reporte. Es lo que vive una
   persona que llega al repositorio, que es justamente a quien mide el criterio.
   La consecuencia es dura y conviene saberla desde hoy: la descarga de
   dependencias y de los modelos de detección de datos personales entra en el
   cronómetro
B. **Desde el clon, excluyendo descargas de red**: mide lo que controlamos y no
   la conexión de quien prueba. Más estable entre máquinas y menos honesto con la
   experiencia real
C. **Solo la corrida de evaluaciones**, con el entorno ya montado: es la métrica
   más fácil de cumplir y ya está cubierta por NFR17 (10 minutos), así que
   duplicaría una meta en vez de medir otra
X. Other (please specify)

[Answer]: A

## Q3 — Sobre qué corre el escaneo de secretos en cada entrega

La práctica afirmada pide escanear "lo que se commitea **y** el historial
completo". Con el repositorio creciendo y 2.000 minutos de integración continua
al mes, la frecuencia del escaneo del historial importa.

A. **El cambio en cada corrida, el historial completo por hito** (recomendada):
   cada entrega escanea lo que trae el commit —que es donde puede aparecer una
   clave nueva— y el historial completo corre en cada hito y antes de publicar el
   repositorio. Cubre el riesgo real sin pagar el historial completo cada vez
B. **El historial completo en cada corrida**: la cobertura máxima y el costo
   crece con el repositorio, hasta volverse el trabajo más lento de la tubería
C. **Solo el cambio**: barato y deja sin mirar el historial justo antes de
   publicar, que es cuando una clave vieja se vuelve un incidente
X. Other (please specify)

[Answer]: A

## Q4 — Qué deja registrado una corrida cuando corre en la tubería

El corredor registra cada corrida y cada resultado por caso. Falta decidir qué
sobrevive a la corrida de integración continua, donde no hay base de datos
persistente.

A. **El reporte como archivo publicado por la corrida, y el registro en base solo
   en local** (recomendada): en la tubería, el reporte y el resumen por caso se
   publican como artefacto de la corrida, con su commit y su fecha; el registro
   en base de datos existe cuando se corre contra la base local. Así la compuerta
   no necesita infraestructura y el diff contra la línea base se hace entre
   archivos versionados
B. **Registrar siempre en base de datos**, también en la tubería: consulta más
   cómoda a cambio de que la compuerta dependa de una base disponible, y esa
   dependencia es exactamente la que convierte un fallo de infraestructura en un
   fallo de entrega
C. **Solo la salida en pantalla**: cero infraestructura y cero historial; el diff
   contra la línea base tendría que reconstruirse a mano
X. Other (please specify)

[Answer]: A
