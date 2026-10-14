# Preguntas — Delivery Planning

Esta es la última etapa de Incepción. Decide **en qué orden se construyen las 22
unidades** y qué entra en los 90 días. Cada unidad se construye como un **Bolt**:
una pasada de construcción sobre una pieza del trabajo que termina en algo que
corre y se puede probar.

Casi todo el marco ya está decidido y esas decisiones las aplico yo con su razón
escrita:

- **Una pieza completa a la vez.** Tu práctica afirmada, en tus palabras: "haremos
  la creación de componente Uno A uno ... en lugar de dejar un componente a
  medias". Así que hay **22 Bolts, uno por unidad**, y cada uno atraviesa su
  diseño, su código y sus pruebas antes de que empiece el siguiente. No se
  construyen dos en paralelo.
- **Sin esqueleto delgado.** El scope `classic` no corre la ceremonia de
  esqueleto, y tu práctica la reemplaza por "primero una base sólida y terminada".
- **El orden respeta las dependencias.** El mapa de Units Generation tiene 90
  aristas sin ciclos; ninguna secuencia puede romperlas.
- **La regla de corte ya está escrita** en el PRD: se corta en orden S2, S1, C1,
  S5, S4; M1 a M20 nunca se cortan y el español se reduce pero no se elimina.
- **El calendario viene del PRD:** inicio el 2026-09-16, día 30 el 2026-10-15,
  día 60 el 2026-11-14, día 90 el 2026-12-14. Las semanas 8 y 12 son
  amortiguadores sin entregables nuevos.

Quedan cinco decisiones que sí cambian el plan.

**Fuentes consumidas.** `../requirements-analysis/requirements.md` (los NFR con su
valor esperado), `../user-stories/stories.md` (prioridad Must o Should de cada
historia), `../refined-mockups/mockups.md` (las pantallas comprometidas),
`../domain-design/components.md` (los 23 componentes),
`../units-generation/unit-of-work.md` (las 22 unidades con su complejidad),
`../units-generation/unit-of-work-dependency.md` (las 90 aristas),
`../units-generation/unit-of-work-story-map.md` (la asignación de historias),
`../contract-design/contract-summary.md` (los 30 contratos) y
`../practices-discovery/team-practices.md` (las prácticas afirmadas).

## Q1 — En qué orden se construyen las 22 unidades

El mapa de dependencias permite muchos órdenes válidos. Elegir uno es una
decisión de valor y de riesgo, no de geometría.

A. **Por capas, como el plan del PRD** (recomendada): base del repositorio,
   aislamiento, caso, proveedores e interfaz → corpus, citas, reglas y
   cumplimiento → captura y grafo → evaluación → chat y bandeja → operación de la
   demo y evidencia → voz en inglés → enlace público de voz → voz en español →
   cotización. Es el orden que el PRD ya aprobó, respeta las dependencias y deja
   el camino completo en texto antes de tocar la voz, que es la mitigación del
   riesgo R1
B. **Riesgo primero:** adelantar la voz (adaptadores y llamada) apenas exista el
   grafo, antes del chat y la bandeja, porque la voz es lo más incierto. Choca
   con la mitigación de R1 del PRD y deja la validación del día 30 sin bandeja
C. **Valor primero:** adelantar chat y bandeja apenas exista el caso, antes de
   reglas y cumplimiento, para tener algo demostrable lo antes posible. Deja
   salidas sin la guardia de cumplimiento, que es compuerta dura
X. Other (please specify)

[Answer]: A

## Q2 — Cuándo corre el experimento de voz

El experimento 1 elige la librería de voz y el transporte (ADR-009) y la voz de
respaldo (ADR-008). Sin él, dos unidades no pueden empezar. El PRD lo puso en la
semana 1 y todavía no ha corrido.

A. **Apenas termine Incepción, en paralelo con las primeras unidades**
   (recomendada): las primeras cinco unidades no dependen de la voz, así que el
   experimento corre mientras se construyen. Si su resultado obliga a cambiar un
   ADR, el cambio llega cuando todavía no hay código de voz escrito
B. **Cuando toque la voz** (semana 5 del PRD): menos cambio de contexto ahora,
   pero si el resultado obliga a cambiar la arquitectura de la voz, el cambio
   llega con la semana 5 encima
C. **Antes de escribir cualquier código**: la decisión más informada, a costa de
   perder los primeros días de construcción esperando un experimento que no
   bloquea nada de lo que viene primero
X. Other (please specify)

[Answer]: A

## Q3 — Qué se promete para el día 30

El PRD fija esta compuerta para el 15 de octubre: chat en vivo y bandeja
desplegados, línea base v0 de evaluación publicada y validación con dos o tres
personas del perfil. Llegar a eso exige **17 de las 22 unidades** terminadas
(todo menos las cuatro de voz y la cotización), y hoy es 18 de septiembre: quedan
27 días, y las tres unidades más grandes (corpus y citas, chat, bandeja) están
entre esas 17.

Te lo pongo sobre la mesa ahora y no en octubre.

A. **Mantener la fecha y usar la regla de corte si aprieta** (recomendada): el
   plan apunta al 15 de octubre con las 17 unidades; si a mitad de camino el
   ritmo no da, se corta por la regla ya escrita y se protege lo que el día 30
   valida de verdad: el camino en texto con citas verificadas y la línea base v0
B. **Mover la validación externa al día 37** y dejar el día 30 con el camino en
   texto y la línea base v0, con el chat corriendo en local en vez de desplegado.
   Menos presión, pero la validación externa —que es la que más te puede cambiar
   el producto— llega una semana más tarde
C. **Reducir el alcance del día 30 ahora:** dejar la bandeja para después del día
   30 y validar solo con el chat. El riesgo es que la bandeja es la que muestra
   "la persona decide", que es el principio que más te diferencia
X. Other (please specify)

> **Corrección posterior a la respuesta (2026-09-18).** Al escribir el plan
> comprobé que la opción A decía que S2 y S1 "son unidades enteras", y solo S1 lo
> es. S2 (continuidad de voz a chat, US1.20) y S5 (vista de comparación, US2.9)
> son **historias dentro** de la unidad del chat: cortarlas adelgaza ese Bolt, no
> lo elimina. El primer Bolt completo que desaparece por la regla de corte es la
> cotización (U19), que ya es el último de la secuencia. No cambia la decisión de
> Miguel —mantener la fecha— pero sí lo que significa cortar, así que queda
> escrito aquí y en `risk-and-sequencing-rationale.md`.

[Answer]: A

> **Cambio posterior de Miguel (2026-09-18), después de aprobar la etapa,
> literal:** "nadie me pone un corte de fecha, podemos ir a nuestro ritmo". La
> respuesta A sigue en pie en lo que decide —no se reduce el alcance ni se mueve
> la validación— pero la fecha deja de ser un compromiso. Queda recogido como
> DP-8 en `bolt-plan.md`, y el riesgo R-A de
> `risk-and-sequencing-rationale.md` se reescribió: sin plazo, el riesgo no es
> llegar tarde sino que el alcance se ensanche sin que nadie lo note.

## Q4 — Cómo se atiende la construcción

A. **Una sola sesión, unidad por unidad, con tu aprobación en el camino**
   (recomendada): construyo cada unidad completa aquí mismo y tú apruebas. Es lo
   que corresponde a un proyecto de una persona
B. **Varios equipos, cada uno dueño de una unidad**, aprobando su trabajo por
   separado. Solo tiene sentido con más de una persona construyendo a la vez
X. Other (please specify)

[Answer]: A

## Q5 — Qué es lo que más te preocupa de esta construcción

Lo que elijas se atiende temprano: la unidad que lo toca se adelanta dentro de lo
que permitan las dependencias, y el plan deja escrito qué señal lo delataría a
tiempo.

A. **El ritmo**: 22 unidades en diez semanas con una sola persona
B. **La voz**: latencia, interrupciones y que la librería elegida no cumpla
C. **La calidad de las respuestas**: citas, extracción y que las evaluaciones no
   midan lo que importa
D. **El costo**: que el techo de 5 USD se agote antes de tiempo
E. **Terminar con algo que no se ve bien** ante quien evalúa el repositorio
X. Other (please specify)

> Respuesta de Miguel, literal: "Las 3 ultimas", sobre las cuatro opciones que se
> le presentaron en pantalla (el ritmo, la voz, la calidad, el costo): elige la
> voz, la calidad y el costo.

[Answer]: B, C, D
