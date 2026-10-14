# Preguntas — Diseño no funcional de U1 `workspace`

Esta etapa convierte las metas de `nfr-requirements` en decisiones de diseño: qué
patrón se aplica, dónde vive y qué pasa cuando falla. U1 no atiende tráfico, así
que la mayor parte del diseño trata de dos cosas: **el guion único de
verificación** y **el corredor de evaluaciones**.

**Fuentes consumidas.**
`../nfr-requirements/performance-requirements.md` (NFR21.1, NFR21.2, NFR17.1 y el
presupuesto por paso), `../nfr-requirements/security-requirements.md` (la tabla
STRIDE y SEC-U1.1 a SEC-U1.8), `../nfr-requirements/scalability-requirements.md`
(qué crece y la válvula del subconjunto),
`../nfr-requirements/reliability-requirements.md` (REL-U1.1 a REL-U1.5),
`../nfr-requirements/observability-requirements.md` (OBS-U1.1 a OBS-U1.4),
`../nfr-requirements/tech-stack-decisions.md` (lo que U1 instala y NFR18),
`../functional-design/functional-spec.md` (los tres flujos y los estados de una
corrida), `../functional-design/rules.md` (las 21 reglas) y
`../../../inception/contract-design/contract-summary.md` (C-21, C-22, C-24, C-27
y C-28).

## Lo que se aplica sin preguntar

Lo resuelven documentos aprobados o prácticas afirmadas, así que se aplica y se
registra en la tabla de decisiones de la etapa, no aquí:

- **El escaneo de secretos no se escribe dos veces.** La práctica afirmada dice a
  la vez que el escaneo es el primer trabajo del flujo y que el flujo invoca el
  guion único en lugar de mantener su propia lista. La única lectura que cumple
  las dos es que el primer trabajo invoque el guion **acotado a ese paso** y el
  segundo corra el resto: una sola definición del escaneo, y nada corre dos
  veces.
- **Sin SLO de disponibilidad.** La unidad no se despliega; ya está escrito en
  `reliability-requirements.md`.
- **Sin caché ni cola ni escalado horizontal.** No hay tráfico que amortiguar.
- **Permisos vacíos por defecto en la tubería y acciones fijadas por commit**
  (SEC-U1.5).

Quedan **cuatro decisiones** que ningún documento resuelve y que cambian lo que
se construye.

## Q1 — Qué hace el guion de verificación cuando un paso se pone rojo

El guion corre nueve pasos en orden. Falta decidir si se detiene en el primero
que falla o si sigue y reporta todo junto.

A. **Todo corre hasta el final, menos el escaneo de secretos** (recomendada): el
   escaneo es el primer paso y detiene la corrida en el acto, porque una clave
   filtrada es un incidente y lo último que se quiere es seguir trabajando y
   publicando registros encima. De ahí en adelante cada paso corre y al final
   aparece una sola lista de lo que falló. Una corrida te dice todo lo que hay
   que arreglar
B. **Se detiene en el primer paso rojo**: lo más simple y lo más barato en
   minutos de integración continua; el costo es que cada arreglo cuesta otra
   vuelta completa, y con nueve pasos eso son varias vueltas por cambio
C. **Todo corre hasta el final, incluido el escaneo**: la máxima información de
   una sola vez, y sigue trabajando después de encontrar una clave, que es
   justo el momento en que todo debería parar
X. Other (please specify)

[Answer]: A

## Q2 — Qué hace el corredor cuando el proveedor falla a mitad de la corrida

BR1.4 ya dice que un caso que no se puede ejecutar queda **no medido con su
causa** y la corrida sigue. Falta decidir cuánto se insiste antes de declararlo,
y esto toca el tope de gasto directamente.

A. **Un reintento para lo pasajero, cero para la cuota, y corte tras tres fallos
   seguidos de cuota o presupuesto** (recomendada): un tiempo agotado o un
   "demasiadas peticiones" se reintenta una vez con espera; una cuota o un
   presupuesto agotados no se reintentan nunca, porque no son pasajeros. Tras
   tres de esos seguidos la corrida se detiene y marca el resto de los casos
   como no medidos con esa causa, en lugar de recorrer ciento treinta casos
   fallando uno por uno
B. **Tres reintentos con espera creciente en todo fallo**: aguanta mejor un
   proveedor inestable; el costo es que reintentar una cuota agotada gasta
   tiempo, y en un proveedor de pago gastaría dinero
C. **Sin reintentos**: cada fallo se declara no medido de inmediato. Lo más
   barato y lo más honesto, y también lo más frágil: un parpadeo de red
   convierte una corrida comparable en una no comparable
X. Other (please specify)

[Answer]: A

## Q3 — Quién declara el subconjunto que corre en los 15 minutos

El camino de los 15 minutos corre "el subconjunto declarado". El subconjunto de
la compuerta lo decide U21 más adelante (PA-11), así que hay que decidir si el
arranque espera a esa decisión o lleva la suya.

A. **U1 declara su propio subconjunto de arranque, pequeño y fijo**
   (recomendada): una lista corta, elegida para que el camino quepa en el
   presupuesto, distinta de la de la compuerta. Así la meta de los 15 minutos se
   puede medir desde el primer día y no depende de una decisión que todavía no
   existe. Los dos subconjuntos conviven: uno para enseñar que funciona, otro
   para bloquear
B. **Un solo subconjunto para las dos cosas, declarado por U21**: una sola lista
   que mantener; el costo es que U1 no puede medir su propia meta hasta que
   exista U21, y que la lista de la compuerta se elige por cobertura, no por
   velocidad
C. **Sin subconjunto: el arranque corre todo**: la medición más honesta de lo que
   el proyecto hace; hoy no hay ningún caso, y cuando los haya la corrida
   completa deja de caber en el presupuesto, que es exactamente el problema que
   el subconjunto resuelve
X. Other (please specify)

[Answer]: A

## Q4 — Cada cuánto corre la medición de los 15 minutos en la tubería

NFR21.2 pide un número producido sin intervención humana. El trabajo que lo
produce parte de un entorno limpio y tarda unos catorce minutos, y el plan del
repositorio trae 2.000 minutos de integración continua al mes.

A. **Semanal y antes de cada hito, más a mano cuando alguien lo pida**
   (recomendada): el número se produce solo y queda fechado, y los minutos de
   integración continua se quedan para la compuerta, que sí corre en cada
   cambio. Lo que mide —la experiencia de quien llega al repositorio— se mueve
   por semanas, no por commit
B. **En cada entrega**: el número siempre fresco; catorce minutos por cambio
   sobre un presupuesto de 2.000 al mes se come el margen y alarga cada entrega
   para medir algo que casi nunca cambia
C. **Solo a mano**: cero costo y el riesgo conocido: una medición que hay que
   acordarse de lanzar deja de lanzarse, y el criterio queda escrito sin número
X. Other (please specify)

[Answer]: A
