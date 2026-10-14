# Diseño de monitoreo — U1 `workspace`

Qué se vigila cuando no hay nada desplegado. La respuesta corta: **el estado del
tronco y lo que deja cada corrida**. La respuesta larga tiene una decisión que
importa más que todas las tablas juntas: por dónde llega el aviso.

**Fuentes consumidas.** `../nfr-design/observability-design.md` (los tres
niveles, los campos obligatorios y las causas cerradas),
`../nfr-design/performance-design.md` (los dos relojes),
`../nfr-design/reliability-design.md` (la política de fallo del corredor),
`../../../inception/domain-design/decisions.md` (ADR-015, telemetría) y
`infrastructure-design-questions.md` (decisiones Q3 y Q4 de esta etapa).

## Lo que esta unidad no monitorea

No hay percentiles de latencia, ni tasa de error de un servicio, ni uso de CPU,
ni saturación, ni disponibilidad. **No hay servicio.** Rellenar esas tablas con
valores plausibles produciría un documento que se lee como si alguien vigilara
algo, y no vigilaría nada.

Lo que sí hay son cuatro señales, y las cuatro son reales.

## Métricas

| Métrica | De dónde sale | Umbral | Por qué importa |
| --- | --- | --- | --- |
| Estado de la corrida sobre `main` | El flujo de GitHub Actions | Verde. Un rojo es un incidente | Es la compuerta; corre después de que el cambio ya entró, así que un rojo bloquea todo lo demás |
| Duración de la corrida de evaluación | Campo `duration_seconds` de la corrida | Se publica siempre; la meta de 10 minutos la fija U21 | Sin medirla desde el principio no hay contra qué comparar cuando empiece a crecer |
| Proporción de casos no medidos | Resultados de la corrida, por causa | Cualquier valor distinto de cero se mira | **La señal más fácil de ignorar y la más importante:** una corrida verde con el treinta por ciento sin medir no es una corrida verde, y lo parece |
| Tiempo del clon al reporte | El trabajo semanal, por paso | Menos de 15 minutos | Es la meta que mide la experiencia de quien llega al repositorio |
| Minutos de integración continua consumidos | El panel de facturación de GitHub | 2.000 al mes, con bloqueo | Agotarlos apaga la compuerta entera |

**Ninguna de estas métricas se recolecta con un servicio de monitoreo.** Las
cuatro primeras viven en el artefacto de la corrida; la quinta, en el panel que
GitHub ya trae. Montar un recolector para cinco números de una unidad que no se
despliega sería infraestructura buscando un problema.

## Alertas

| Alerta | Condición | Severidad | Por dónde llega |
| --- | --- | --- | --- |
| `main` en rojo | Una corrida falla sobre `main` | **Incidente**: se arregla antes que cualquier otra cosa | Notificaciones de GitHub: correo y aviso en la aplicación móvil (decisión Q4) |
| Clave filtrada | El escaneo de secretos encuentra algo | **Incidente, y además la clave se rota en el proveedor** | El mismo canal, y llega en minutos porque es el primer trabajo |
| Minutos de integración por agotarse | GitHub avisa al acercarse al tope del plan | Se mira ese día | Correo de GitHub |

**Por qué las notificaciones propias de GitHub y no un canal aparte** (decisión
Q4): no hay nada que instalar, nada que pagar, ninguna credencial nueva y ningún
servicio más que se pueda romper en silencio. Un canal de mensajería sería más
visible, y también una pieza más cuya caída se nota tarde y precisamente cuando
se la necesita.

**Qué hay que configurar una vez**, y es todo lo que hay que configurar: en las
notificaciones de GitHub, activar las de Actions para las corridas fallidas.

## Indicadores y objetivos

No son SLI ni SLO en el sentido de un servicio —no hay servicio—, pero sí son lo
que el proyecto va a mirar, y conviene que estén escritos una vez:

| Indicador | Objetivo | Ventana |
| --- | --- | --- |
| Corridas verdes sobre `main` | La inmensa mayoría; un rojo se arregla o se revierte en 30 minutos | Por corrida |
| Tiempo con `main` en rojo | Menos de 30 minutos (decisión Q3) | Por incidente |
| Duración de la corrida de evaluación | Se mide y se publica siempre | Por corrida |
| Tiempo del clon al reporte | Menos de 15 minutos | Semanal |

**Sin porcentaje de disponibilidad, a propósito.** Un número de disponibilidad
para algo que no está desplegado es una métrica inventada, y este proyecto tiene
prohibido publicar una métrica sin lo que la sostiene.

## Registros y trazas

**Registro de la corrida.** El corredor escribe a la salida estándar en formato
estructurado, una línea por evento, con el identificador de la corrida y el del
caso en cada línea. El evento de apertura lleva los mismos campos obligatorios
que el registro de la corrida —incluido el hash del prompt de cada nodo—, porque
un prompt cambiado sin cambiar el modelo produce el mismo efecto que un cambio de
modelo y no se vería. En la tubería eso es lo que se lee sin descargar el
artefacto; en local, lo que se sigue mientras corre.

| Evento | Qué lleva |
| --- | --- |
| Corrida abierta | Commit, subconjunto, identificadores exactos de modelo por uso y **hash del prompt de cada nodo** |
| Caso iniciado y terminado | Identificador, estado, duración |
| Reintento | Clase de error e intento |
| Cortacircuitos abierto | La causa; es el evento que explica una corrida corta |
| Corrida cerrada | Duración, recuento por estado, marca de comparable |

**Retención.** Los artefactos de la corrida los guarda GitHub el tiempo que fije
el plan; el diff contra la línea base **no depende de ellos**, porque se hace
entre archivos versionados. Eso es deliberado: un historial que vive solo en un
proveedor es un historial que caduca.

**Trazas.** Son de U5, y en esta unidad son opcionales por construcción: sin
backend, el reporte sale con los enlaces marcados como no disponibles y la
corrida sigue siendo comparable. Ninguna traza sale sin pasar por la redacción,
sin excepción por origen: los casos son sintéticos y aun así se redactan, porque
una excepción por origen es el agujero que después nadie encuentra.

## Paneles

**Ninguno en esta unidad.** El panel de cifras y el de gasto son de U22, y el
panel de trazas lo trae Langfuse cuando se levanta. Lo que U1 produce es el
reporte de la corrida, que es un archivo y no un panel: se lee igual dentro de
seis meses, y un panel de hace seis meses ya no está.
