# Diseño de escalabilidad — U1 `workspace`

Esta unidad no tiene tráfico que escalar. Lo que crece es **el conjunto de casos
de prueba, el historial del repositorio y los minutos de integración continua**,
y este documento dice qué se hace cuando cada uno se sale del presupuesto.

**Fuentes consumidas.** `../nfr-requirements/scalability-requirements.md` (qué
crece y hasta dónde), `../nfr-requirements/performance-requirements.md`
(restricciones de recursos), `../functional-design/functional-spec.md` (Flujo 1
paso 3), `../functional-design/rules.md` (BR1.6, BR1.7, BR1.9),
`../../../inception/contract-design/contract-summary.md` (C-27, un archivo por
caso) y `nfr-design-questions.md` (decisiones Q3 y Q4 de esta etapa).

## Lo que no se diseña, y por qué

| Patrón | Por qué no aplica |
| --- | --- |
| Escalado horizontal | La corrida es un proceso que termina; su unidad de crecimiento son los casos, no las máquinas |
| Balanceo de carga | No hay peticiones que repartir |
| Partición o fragmentación de datos | El registro de corridas es local y pequeño; el corpus lo ingiere U8 |
| Colas y desacople por eventos | No hay productores ni consumidores; hay un comando |
| Auto-escalado | No hay nada desplegado que escalar |

Escribirlos igual sería decorar el documento. Lo que sí hay son **tres válvulas**,
y cada una tiene dueño, disparador y consecuencia escrita.

## Válvula 1 — El subconjunto declarado

**Qué crece:** los casos de golden set, de cero hoy a unos 130 entre los
conjuntos que corren por entrega (DS-2 con 60, DS-3 con 40, DS-6 con 30).

**Cuándo se abre la válvula:** cuando la corrida completa deja de caber en el
presupuesto de tiempo o en los límites del plan gratuito.

**Qué se hace:** la compuerta corre el **subconjunto declarado**. Nunca se apaga,
nunca se baja un umbral y nunca se salta un caso en silencio. La corrida completa
pasa a ser obligatoria por hito y antes de publicar cualquier línea base.

**Cómo está construido para que eso sea posible:**

- El subconjunto es una lista versionada con nombre y razón, en el mismo commit
  que los casos, y el reporte **declara** que corrió un subconjunto (BR1.6,
  campo `subset_declared` de la corrida). Un reporte parcial que no se anuncia
  como parcial es peor que no tenerlo.
- Mismo commit y mismo subconjunto ejecutan los mismos casos en el mismo orden
  (BR1.7). Eso es lo que hace comparable una corrida parcial con la anterior.
- Un identificador de la lista que no exista como archivo de caso **detiene la
  corrida**: una lista que apunta a un caso borrado es una compuerta que
  silenciosamente mide menos.

**Dos listas, dos criterios** (decisión Q3):

| Lista | Dueño | Se elige por | Para qué |
| --- | --- | --- | --- |
| `smoke` | U1 | Velocidad | El camino de los 15 minutos |
| La de la compuerta | U21 (PA-11) | Cobertura | Bloquear la entrega |

## Válvula 2 — El alcance del escaneo del historial

**Qué crece:** el historial del repositorio, hoy solo la landing, mañana con
corpus, datos generados y líneas base versionadas.

**Qué se hace:** el escaneo del cambio corre en cada corrida; el del historial
completo, por hito y antes de publicar. Es la decisión Q3 de `nfr-requirements`,
y su razón es de costo: el escaneo del historial crece con el historial, el del
cambio no.

**El disparador que la vuelve a cerrar:** la decisión de publicar el repositorio
en la semana 12. Ahí el historial completo vuelve a ser obligatorio, y no como
una corrida más sino como condición.

## Válvula 3 — Los minutos de integración continua

**Qué crece:** el uso, contra un tope de 2.000 minutos al mes con bloqueo al
agotarse.

**Qué se hace, en este orden:**

1. **Cancelar la corrida anterior** sobre el mismo cambio. Dos corridas sobre el
   mismo trabajo son minutos regalados.
2. **Filtros de ruta**: un cambio que solo toca `docs/` o `aidlc/` no dispara la
   corrida completa.
3. **La medición de los 15 minutos corre semanal y por hito**, no en cada entrega
   (decisión Q4). Catorce minutos por cambio sobre 2.000 al mes es la mayor
   fuente de gasto evitable que tiene el proyecto.
4. **Caché del gestor de paquetes** en los trabajos que no miden el arranque
   limpio.

**Lo que los filtros nunca apagan:** la compuerta de evaluaciones. Un filtro de
ruta que la desactive convierte la compuerta en una sugerencia, y el fallo sería
invisible: las corridas siguen saliendo verdes porque no corren.

**Qué pasa cuando se agotan** (decisión del 2026-09-19): **toma el relevo un
runner propio**, en la máquina de Miguel. Minutos ilimitados y gratis, así que la
compuerta no se detiene a mitad de mes. No es contratar nada ni recargar nada: es
una máquina que ya existe.

Tres condiciones que vienen con él, y la primera no es negociable:

| Condición | Por qué |
| --- | --- |
| **Se apaga antes de hacer público el repositorio** | Con el repositorio público, cualquiera que haga un fork puede ejecutar código arbitrario en esa máquina a través de un pull request. Es la advertencia explícita de GitHub, y es la razón por la que esta decisión queda atada a la de visibilidad |
| **La máquina tiene que estar despierta** | Si está dormida, la corrida se queda en cola. Para un `main` en rojo que es un incidente, un aviso que llega horas después no sirve |
| **No corre la medición de los 15 minutos** | Un runner propio acumula caché entre corridas, así que por definición no es una máquina limpia. Esa medición se queda en los runners de GitHub o el número deja de significar lo que dice |

Las cuatro medidas de arriba **no se relajan** por tener la reserva: los minutos
de GitHub siguen siendo el camino normal y el runner propio es lo que evita que
un mes malo apague la compuerta, no una excusa para gastarlos sin cuidado.

## Umbrales, en una tabla

| Dimensión | Hoy | Umbral que abre la válvula | Qué se hace |
| --- | --- | --- | --- |
| Casos por entrega | 0 | La corrida no cabe en el presupuesto de tiempo o del plan gratuito | La compuerta corre el subconjunto declarado |
| Tamaño de `smoke` | 0 | Un caso por conjunto por entrega y por idioma | Se comprueba en el guion; crecer más rompe el arranque |
| Historial del repositorio | Solo la landing | Costo del escaneo completo | Por hito, no por cambio |
| Minutos al mes | 0 | 2.000 | Cancelación, filtros y medición semanal; agotados, releva el runner propio |

## Qué se degrada primero, y qué nunca

**Se degrada primero:** la corrida completa se convierte en subconjunto, y el
escaneo del historial se espacia.

**Nunca se degrada:**

- Las compuertas duras.
- La publicación de la duración real de la corrida.
- La declaración de que se corrió un subconjunto.
- La paridad por idioma del reporte: los dos lados a lado, nunca un promedio.

## Lo que no le toca a esta unidad

La concurrencia del proceso servido, los límites por visitante y por día, y el
gasto por llamada son de U5, U13 y U17. U1 no tiene tráfico que escalar y no
puede protegerlos.
