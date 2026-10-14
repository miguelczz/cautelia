# Quién construye cada Bolt — Untangle

Un **Bolt** es una pasada de construcción sobre una pieza del trabajo que termina
en algo que corre; aquí cada Bolt es exactamente una unidad de trabajo. Este
documento dice quién lo construye y quién lo aprueba.

**Fuentes consumidas.** `../requirements-analysis/requirements.md` (los NFR que
fijan las metas de cada unidad), `../user-stories/stories.md` (las historias
asignadas), `../refined-mockups/mockups.md` (las pantallas que cada Bolt con
interfaz entrega), `../domain-design/components.md` (los componentes de cada
unidad), `../units-generation/unit-of-work.md` y
`../units-generation/unit-of-work-dependency.md` (las 22 unidades y sus 90
aristas), `../units-generation/unit-of-work-story-map.md` (qué historia se acepta
en qué unidad), `../contract-design/contract-summary.md` (los 30 contratos que
permiten construir una unidad contra otra que aún no existe) y
`../practices-discovery/team-practices.md` (las prácticas afirmadas, ya en
`team.md`).

## El equipo

| Rol | Quién | Qué hace |
| --- | --- | --- |
| Persona que decide y aprueba | Miguel | Aprueba cada etapa de cada unidad, responde las preguntas de diseño, pone las etiquetas humanas de DS-7, revisa la muestra de textos fuente, escucha la voz y decide el gasto |
| Constructor | Esta sesión (el agente desarrollador de AI-DLC) | Diseña, programa y prueba cada unidad completa, una a la vez |
| Revisor | El agente revisor de arquitectura y el de calidad, según la etapa | Revisión independiente antes de cada compuerta de aprobación |

No hay **mob** (varias personas en el mismo teclado a la vez) ni reparto entre
equipos: el proyecto tiene una sola persona. La etapa 1.5 de formación de equipo
no corrió en este scope, así que no hay equipos que referenciar y no existe
Program Board (el tablero que coordina varios equipos en paralelo).

## Reparto

**Los 22 Bolts los construye la misma sesión, uno a la vez, en el orden de
`bolt-plan.md`.** Ninguno corre en paralelo: la práctica afirmada del equipo es
terminar una pieza antes de empezar la siguiente, y con un solo constructor el
paralelismo solo produciría piezas a medias.

| Bolts | Unidades | Constructor | Aprobación |
| --- | --- | --- | --- |
| B1 a B22 | U1 a U22, una por Bolt | Esta sesión | Miguel, en cada etapa de cada unidad |

## Cómo se atiende cada unidad

Cada unidad atraviesa sus etapas de Construcción **antes de que empiece la
siguiente**: diseño funcional, requisitos no funcionales, diseño no funcional,
diseño de infraestructura y generación de código, y al final del bloque la
construcción y las pruebas. Es la regla de `project.md`: "Construcción recorre el
trabajo por componente y no por etapa". La consecuencia práctica es que el primer
código que corre llega después del diseño de **una** unidad, no después del
diseño de las 22.

Miguel aprueba en cada etapa. La alternativa —una sola aprobación al final de
cada unidad— se descartó: con una etapa equivocada aprobada de largo, las
siguientes se construyen encima antes de que nadie lo note.

## Quién responde por qué contrato

El reparto de propiedad de los 30 contratos está en
`../contract-design/contract-summary.md`. Aquí solo importa la consecuencia
operativa: cuando un Bolt necesita algo de otra unidad que todavía no existe, se
construye **contra su contrato** y no espera. Cuando el contrato mismo no
alcanza, el Bolt no empieza: eso ocurre con los dos Bolts de voz, que esperan el
resultado del experimento de voz (ver `external-dependency-map.md`).

## Carga y señal

Con un solo constructor, la carga no se reparte: se secuencia, y el proyecto no
tiene fecha de corte externa (DP-8 en `bolt-plan.md`: "nadie me pone un corte de
fecha, podemos ir a nuestro ritmo"). Así que la señal que importa no es el
atraso, sino el ensanchamiento: si al cerrar un Bolt se hizo algo que no estaba
en su criterio de terminado, se anota en el diario de esa unidad. El riesgo R-A
de `risk-and-sequencing-rationale.md` lo desarrolla.
