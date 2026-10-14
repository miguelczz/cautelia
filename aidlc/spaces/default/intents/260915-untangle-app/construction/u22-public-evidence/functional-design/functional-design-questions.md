# Preguntas de diseño funcional — U22 `public-evidence`

Tres preguntas para Miguel y siete decisiones que tomé yo. Las tres preguntas
tienen dos respuestas legítimas y cambian lo que ve quien evalúa el proyecto; las
siete decisiones las resuelve un criterio aprobado, una práctica afirmada o una
convención que ya existe en el código.

## Sources

- `../../../inception/user-stories/stories.md` — US4.16 (las cinco cifras), US4.1
  (el README), AC5.14.1 (las vistas del gasto)
- `../../../inception/units-generation/unit-of-work.md` — U22, sus componentes y su
  árbol
- `../../../inception/delivery-planning/bolt-plan.md` — B17 y su definición de
  terminado
- `../../../inception/delivery-planning/pasada-de-publicacion.md` — U22 entera es
  de publicación
- El código: `evals/gates/` (la línea base), `telemetry/spend/` (el gasto),
  `app/frontend/src/pages/` (las seis pantallas que ya existen)

## Assumptions & Open Questions

Las tres de abajo. Ninguna bloquea empezar: cada una lleva la opción con la que
construiría si no contestas, y cambiarla después cuesta poco.

---

## Q1 — El panel de gasto, ¿público o tuyo?

**Por qué hay pregunta.** AC5.14.1 pide ver el costo **por caso**, por proveedor,
por mes y el acumulado. Pero el panel de cifras es público y AC4.16.5 le prohíbe
mostrar identificadores de caso; hay además una regla del proyecto, aprendida en
Refined Mockups, que dice que ninguna superficie pública del aplicativo muestra
números ni identificadores de casos de visitantes.

"Costo por caso" es, literalmente, una fila por caso.

| | Qué se ve | Qué cuesta |
| --- | --- | --- |
| **A. El de cifras público, el de gasto con credencial** *(recomendada)* | Quien evalúa ve las cinco cifras; tú ves el gasto con su detalle por caso | Una pantalla más detrás de credencial, que ya existe para la bandeja |
| B. Los dos públicos, el de gasto solo con agregados | Quien evalúa ve también cuánto cuesta | Se pierde el detalle por caso, que es justo lo que te sirve para no gastar de más |

**Recomiendo A.** El gasto por caso es información tuya de operación, no evidencia
para quien evalúa; y la cifra que sí es evidencia —el costo por caso **promedio**—
ya está entre las cinco del panel público.

---

## Q2 — El chequeo del README, ¿en cada entrega o por hito?

**Por qué hay pregunta.** AC4.1.3 dice que el chequeo **falla** si la sección
"Cómo falla" publicada no coincide con la que produce el último reporte. Eso es
claro. Lo que el criterio no dice es cada cuánto corre, y ahí hay dos respuestas
con consecuencias distintas.

| | Cuándo corre | Qué cuesta |
| --- | --- | --- |
| **A. En cada entrega, dentro del guion de verificación** *(recomendada)* | En cada corrida de GitHub Actions | Cualquier cambio en qué casos fallan obliga a regenerar el README y commitearlo, o `main` se pone rojo |
| B. Por hito, como un comando que corres tú | Semanas 6, 9 y 12 | El README puede quedarse desactualizado entre hitos, que es exactamente lo que el criterio existe para impedir |

**Recomiendo A**, con un matiz que quita casi toda la fricción: el arreglo es **un
comando** que regenera la sección, igual que `contracts:gen`. Y mientras no exista
línea base, la sección dice "no medida" con su causa y el chequeo compara contra
eso, así que no se pone rojo por no haber medido todavía.

---

## Q3 — El panel de cifras, ¿pantalla del aplicativo o página generada?

**Por qué hay pregunta.** Las cinco cifras salen de un archivo versionado. Se
pueden servir de dos maneras y las dos son defendibles.

| | Cómo se sirve | Qué cuesta |
| --- | --- | --- |
| **A. Una pantalla más del aplicativo** *(recomendada)* | Lee la línea base vigente al abrirse, como las otras seis pantallas | Si el aplicativo está dormido, la primera visita espera a que despierte |
| B. Una página estática generada en el commit | Se publica sola, sin servidor | Un segundo camino de compilación y de despliegue, para una sola pantalla |

**Recomiendo A.** El aplicativo ya se sirve desde el mismo origen y ya tiene su
selector de idioma, su tema y su base visual; una página aparte tendría que
repetir las tres o verse distinta, y verse distinta es lo que hace dudar a quien
evalúa.

---

## Las diez decisiones que tomé yo

| # | Qué | Por qué no es pregunta |
| --- | --- | --- |
| FD-U22-1 | Las cifras salen de la **línea base vigente versionada** (`app/evals/baselines/current.json`, que **todavía no existe**: lo crea la primera corrida completa que se publique), no del último reporte, que vive en `tmp/` y no se versiona | AC4.16.2 pide fecha, commit y enlace al reporte que la produjo: solo un archivo versionado los tiene |
| FD-U22-2 | Sin línea base publicada, **cada cifra aparece como "no medida" con su causa**, nunca vacía ni en cero, y el panel existe igual | AC4.16.4, literal. Hoy no existe ninguna línea base, así que este es el estado con el que el panel nace |
| FD-U22-3 | Las pantallas viven en `app/frontend/src/pages/`, no en `src/modules/` como decía el catálogo de unidades | El árbol del catálogo se escribió antes de que existiera el frontend; las seis pantallas construidas están en `pages/`, y abrir una segunda convención por una unidad es peor que la desviación. Queda anotado |
| FD-U22-4 | Todo el texto visible sale del **catálogo por idioma**, en español y en inglés | Regla del proyecto; ninguna cadena visible se escribe en línea |
| FD-U22-5 | El **README** va en inglés con resumen en español, y solo dos de sus ocho secciones las genera esta unidad: "Cómo falla" y las cinco cifras | D24 de User Stories y el reparto escrito en `bolt-plan.md`: las otras seis las escribes tú en la semana 11 |
| FD-U22-6 | Las latencias se publican **por idioma y con p50 y p95**, diciendo entre qué eventos se miden y sobre qué conjunto; nunca un promedio combinado | AC4.16.3 y el principio P12 |
| FD-U22-8 | El panel de gasto lleva **su propia clave de operador**, declarada en el despliegue, y sin ella no se monta. No sirve la credencial de la bandeja | El gasto es del proyecto y los dos roles que existen son **de una aseguradora**: darle a uno el gasto del proyecto dejaría que la credencial de una aseguradora alcance datos de las otras. Tomada el 2026-09-30, al escribir el encargo de la tanda 2: el diseño decía "con credencial" sin decir cuál, y la nube habría tenido que inventarlo |
| FD-U22-9 | La tanda 3 **crea `README.md`** con sus ocho encabezados en el orden que fija AC4.1.1, las dos secciones generadas entre marcas, y las seis narrativas con una línea que dice que las escribe Miguel en la semana 11. El chequeo comprueba **solo las dos generadas** | Hoy no existe ningún README, y "Cómo falla" tiene que ser el tercer encabezado **dentro** de él (AC4.1.1): no puede vivir en un archivo aparte. Un esqueleto con las seis pendientes declaradas no promete ninguna capacidad —no es P7— y el repositorio es privado hasta la semana 12. Un chequeo que exigiera las ocho se pondría rojo por trabajo que es de Miguel |
| FD-U22-10 | «Cómo falla» sale del **resumen de la última corrida completa**, un archivo versionado nuevo, que todavía no existe (`app/evals/last-run.json`), y que escribe `mise run evals:baseline` siempre, en verde y en rojo, antes de decidir si publica. Las cinco cifras siguen saliendo de la línea base. `Baseline.root_causes`, añadido en la tanda 3, se retira | **Corrige FD-U22-1 para esta sección.** BR2.1 rechaza publicar una línea base con un caso en rojo, así que una línea base publicada nunca trae fallos: la sección diría siempre «No case failed» y `Baseline.root_causes` no podría llenarse por ninguna ruta de producción. AC4.1.3 dice «el último reporte de evaluación» y el resumen es eso, reducido y versionado. Decisión de Miguel el 2026-09-30, opción B, con la revisión de la tanda 3 delante |
| FD-U22-7 | La unidad **no publica nada**: construye las pantallas y el comando. Publicarlas es la pasada de publicación, con su checklist del segundo día | `pasada-de-publicacion.md`: nada se publica antes de cerrarla |

## Lo que esta unidad no construye

- **Las seis secciones narrativas del README**: las escribes tú en la semana 11.
- **El video y la landing**: no son unidades (US4.2, US4.3).
- **La alerta y el corte del techo de gasto**: ya están construidos en U15 y U16.
  Aquí solo se **muestra** lo que esos ya registran.
- **El hospedaje y el chequeo periódico**: son del intent `infra`.
