# Por qué este orden y qué lo puede romper — Untangle

El razonamiento detrás de la secuencia de `bolt-plan.md`: qué heurística se usó,
dónde el orden se aparta de lo que la geometría del mapa permitiría, qué riesgos
tiene el plan y cuál es la señal temprana de cada uno.

**Fuentes consumidas.** `../requirements-analysis/requirements.md` (los NFR y sus
valores esperados), `../user-stories/stories.md` (prioridad Must o Should de cada
historia, que decide qué se puede cortar), `../refined-mockups/mockups.md` (las
pantallas comprometidas), `../domain-design/components.md` (los componentes y sus
dependencias), `../units-generation/unit-of-work.md` (complejidad y rama de
pruebas por unidad), `../units-generation/unit-of-work-dependency.md` (las 90
aristas y las condiciones externas), `../units-generation/unit-of-work-story-map.md`
(la asignación de historias), `../contract-design/contract-summary.md` (los 30
contratos y sus 10 preguntas abiertas) y
`../practices-discovery/team-practices.md` (las prácticas afirmadas).

## La heurística elegida

**Dependencias primero, y dentro de lo que las dependencias permiten, el orden
por capas del PRD.** No se usó un modelo de puntaje formal como WSJF (*Weighted
Shortest Job First*: ordenar por valor y urgencia divididos por tamaño) porque
con 22 unidades, 89 aristas y un orden por capas ya aprobado, el puntaje no
habría cambiado el orden: la geometría del mapa deja muy poco margen y el PRD ya fijó
las capas. Inventar un puntaje para justificar un orden que las dependencias ya
imponen sería decoración.

La heurística de capas es, en el vocabulario de la literatura, **riesgo primero
acotado por dependencias**: se construye el camino completo en texto antes de
tocar la voz, que es la parte más incierta, porque así la voz se enfrenta con
todo lo demás ya probado y medido. Es la mitigación del riesgo R1 del PRD, y no
es lo mismo que "lo más fácil primero": las dos unidades más grandes del
proyecto (corpus con citas verificadas, y la bandeja) están en las primeras
cuatro semanas.

**No hay esqueleto delgado.** El scope `classic` no corre esa ceremonia, y la
práctica afirmada del equipo la reemplaza a propósito: "primero una base sólida
y terminada... después los componentes uno a uno". La consecuencia es que el
primer Bolt no atraviesa todas las capas del sistema; atraviesa todo el
andamiaje, que es lo que el equipo decidió que hacía falta antes.

## Dónde el orden se aparta del orden topológico

El mapa de dependencias admite muchos órdenes válidos y este plan elige uno; no
se rompe ninguna arista. Tres elecciones merecen explicación porque otra
secuencia igual de válida habría puesto esas unidades en otro lugar:

| Elección | Qué permitía el mapa | Por qué esta |
| --- | --- | --- |
| Las compuertas de evaluación (B12) van antes del chat y la bandeja | Podían ir en cualquier punto después del generador y las reglas | La línea base v0 es condición para seguir a la voz, y el juez calibrado necesita las etiquetas de Miguel, que es una dependencia humana: cuanto antes se pida, mejor |
| La operación de la demo (B16) va antes de publicar, no al final | Podía ir en cualquier punto después del corpus | Ninguna superficie pública se publica sin el reinicio nocturno funcionando; el chat en vivo lo exige |
| Los adaptadores de voz (B18) van después del chat, no junto a la plataforma de proveedores | Podían construirse desde la semana 2, porque solo dependen de la plataforma | Esperan el experimento de voz, y adelantarlos habría significado construir contra una decisión no tomada |

## Riesgos del plan

R-A sale de la decisión de trabajar sin fecha de corte (DP-8); R-B, R-C y R-D son
las tres preocupaciones que eligió Miguel; R-E y R-F salen de lo que no depende
de nosotros.

### R-A — El alcance se estira sin que nadie lo note

Sin fecha de corte (DP-8 en `bolt-plan.md`: "nadie me pone un corte de fecha,
podemos ir a nuestro ritmo"), el riesgo deja de ser llegar tarde y pasa a ser
otro: que cada Bolt crezca un poco más de lo que necesita y el conjunto no
termine nunca. Es el riesgo real de un proyecto sin plazo externo.

- **Qué puede pasar:** un Bolt se alarga añadiendo lo que "ya que estamos"
  conviene, y como no hay fecha, nada lo delata.
- **Probabilidad:** alta. **Impacto:** alto: el proyecto existe para estar
  terminado y publicado, no para ser perfecto.
- **Señal temprana:** el criterio de terminado de cada Bolt está escrito en
  `bolt-plan.md` **antes** de empezarlo. Si al cerrar un Bolt se hizo algo que no
  estaba en ese criterio, eso es el aviso, y se anota en el diario de la unidad.
- **Qué se hace:** lo que no estaba en el criterio y aun así parece necesario se
  trata como trabajo nuevo: entra al Bolt que le corresponde o se anota, no se
  cuela en el que está abierto. Y la regla de corte del PRD sigue disponible como
  herramienta de alcance, ahora a decisión de Miguel y no por vencimiento de una
  fecha. **Cortar no es lo mismo que quitar Bolts:** los dos primeros cortes (S2,
  continuidad de voz a chat; y S5, vista de comparación) son historias **dentro**
  del Bolt del chat y lo adelgazan sin eliminarlo. El primer Bolt que desaparece
  entero es el de cotización (S1), que ya es el último de la secuencia. Lo que
  nunca se corta: M1 a M20, y el español se reduce en alcance pero no se
  elimina.

### R-B — La voz no cumple sus números

- **Qué puede pasar:** la librería elegida no sostiene 800 ms p95 de fin del
  habla a primer audio, o no para en 300 ms ante una interrupción.
- **Probabilidad:** media. **Impacto:** alto: son dos de las cifras que el
  proyecto publica.
- **Señal temprana:** el experimento de voz, que corre al empezar Construcción y
  antes de que exista una línea de código de voz. Es el motivo de que corra en
  paralelo con los primeros Bolts y no cuando toque la voz.
- **Qué se hace:** el experimento actualiza ADR-008 y ADR-009 antes de B18. Si
  ninguna opción cumple, la latencia se publica como es, con su causa
  documentada: el PRD permite eso explícitamente y prohíbe bajar el umbral.

### R-C — La calidad de las respuestas no se sostiene

- **Qué puede pasar:** la precisión de citación no llega al 95 %, la extracción
  falla por campo, o las evaluaciones miden algo distinto de lo que importa.
- **Probabilidad:** media. **Impacto:** alto: es el corazón de la demostración.
- **Señal temprana:** la línea base v0 del Bolt 12, con sus compuertas duras. Antes de eso, los casos de DS-3 que el Bolt 7 escribe y
  comprueba que fallan.
- **Qué se hace:** las compuertas duras bloquean la entrega; un caso que pasa a
  fallar exige explicación que nombre identificadores. El juez solo cuenta
  calibrado: si sus tasas caen, sus criterios se reportan como "no medida" y no
  bloquean, mientras las compuertas juzgadas por código siguen bloqueando.

### R-D — El costo se agota antes de tiempo

- **Qué puede pasar:** el techo de 5 USD en la ventana de 90 días se consume
  antes de terminar, y la voz queda cortada durante la evaluación del proyecto.
  Sin fecha de corte el riesgo **crece**: la ventana de 90 días del presupuesto
  sí tiene fecha, aunque el plan de trabajo ya no la tenga.
- **Probabilidad:** media. **Impacto:** medio: el chat sigue vivo en plan
  gratuito aunque la voz se corte.
- **Señal temprana:** la alerta en 3 USD, que existe desde el Bolt 5.
  El panel de gasto del Bolt 17 la hace visible.
- **Qué se hace:** al llegar al techo, la voz rechaza llamadas nuevas con el
  mensaje del catálogo y el chat sigue. La decisión de recargar es de Miguel y
  nunca automática: ninguna cuenta del proyecto queda con renovación o recarga
  automática.

### R-E — Una dependencia humana llega tarde

- **Qué puede pasar:** las grabaciones de DS-5, las etiquetas de DS-7, la sesión
  de escucha o los revisores de la validación no aparecen cuando hacen falta.
- **Probabilidad:** media. **Impacto:** medio a alto según cuál.
- **Señal temprana:** cada una tiene fecha límite en
  `external-dependency-map.md`.
- **Qué se hace:** cada una tiene su plan B escrito allí; ninguna detiene la
  construcción, todas retrasan una medición.

### R-F — El experimento de voz obliga a cambiar la arquitectura

- **Qué puede pasar:** la librería elegida exige un proceso de voz aparte, y el
  despliegue deja de ser un solo proceso.
- **Probabilidad:** baja. **Impacto:** medio.
- **Señal temprana:** el mismo experimento de voz, al empezar Construcción.
- **Qué se hace:** las unidades ya lo contemplan ("embebida en el proceso único,
  o en el proceso de la voz si el experimento lo exige"), y el contrato del
  transporte de audio está escrito como pendiente con lo que ya es cierto gane
  quien gane.

## Compuertas de salida

Son **condiciones, no fechas** (DP-8): cada una dice qué tiene que ser cierto
antes de seguir al bloque siguiente. La columna de fecha queda como referencia
del PRD.

| Compuerta | Fecha de referencia | Qué tiene que ser cierto antes de seguir | Si no se cumple |
| --- | --- | --- | --- |
| Antes de la voz (día 30 del PRD) | 2026-10-15 | Línea base v0 publicada con compuertas duras en verde; chat y bandeja en vivo con el checklist del segundo día; validación externa hecha o agendada | No se empieza la voz: se termina lo que falte. Si Miguel decide reducir alcance, se cortan S5 y S4 antes de tocar nada Must |
| Antes del español (día 60 del PRD) | 2026-11-14 | Voz en inglés de punta a punta con latencias publicadas; línea base v1; gasto acumulado por debajo de 3 USD; video v1 grabado | No se empieza el español. El video v1 puede moverse; si hay que reducir, S1 sale antes que el español |
| Antes de publicar (día 90 del PRD) | 2026-12-14 | Video final, chat en vivo y repositorio ejecutable con un comando, los tres enlazados; M1 a M20 hechos; tabla de métricas y "Cómo falla" publicados | No se publica. Si Miguel reduce alcance, el orden es S2, S1, C1, S5, S4; el español se reduce, nunca se elimina |

## Lo que este plan no decide

- **Qué etapas de AI-DLC corren y a qué profundidad:** lo fija el scope del
  flujo, no este documento.
- **Cómo se agrupan las unidades en lotes de ejecución concurrente:** no hay
  concurrencia, porque hay un solo constructor.
- **El orden interno de las etapas de cada unidad:** lo fija el propio flujo de
  Construcción.
