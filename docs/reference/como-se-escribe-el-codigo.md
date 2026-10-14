# Cómo se escribe el código, y por qué U12 tardó siete horas

Registro de decisión del 2026-09-27, escrito después de cerrar U12 y a petición de
Miguel. Todas las cifras salen de `git log` y de los contadores de las tandas de
este mismo repositorio; ninguna es una estimación.

## Las cinco unidades comparables

| Unidad | Tamaño | Cómo se escribió | Tandas de código | Líneas | Tiempo | Costo |
| --- | --- | --- | --- | --- | --- | --- |
| U8 | XL | Nube, sesión limpia por tanda | 3 | 12.934 | ~5 h | 87 USD |
| U10 | L | Sesión principal, directo | **2** | 12.240 | **1 h 38** | 0 |
| U11 | L | Nube, sesión limpia por tanda | 2 | 8.609 | ~10 h | 49 USD |
| U12 | L | Agente local despachado | **7** | 13.051 | ~7 h | 0 USD, 2,46 M tokens del plan |

U10 y U12 produjeron prácticamente el mismo volumen. U10 tardó **una cuarta parte**
del tiempo. Esa es la comparación que hay que explicar, y no la de la nube.

## La variable que manda no es dónde se escribe: es cuántas veces

U10 entregó **catorce pasos del plan en dos tandas**. U12 entregó **ocho pasos en
siete despachos**. Cada tanda paga un costo fijo que no baja con su tamaño:

- **Un agente despachado arranca sin contexto.** Tiene que releer el repositorio
  desde cero: entre 137 y 367 llamadas a herramientas y **entre 395.000 y 773.000
  tokens por tanda**. Siete tandas son 2,46 millones de tokens, y la mayor parte es
  volver a descubrir lo mismo.
- **Cada tanda cuesta además unos 15 minutos de la sesión principal**: escribir el
  brief, leer el informe, revisar código que no escribió, correr las nueve
  compuertas y hacer el commit.

De ahí sale el dato que a Miguel le saltó a la vista: tres unidades en la nube
consumieron 10 % de su límite semanal, porque allí los tokens caros iban al crédito
de 250 USD y la sesión local solo escribía briefs. Una unidad L con el agente local
consumió 13 %, porque esos mismos tokens salen de su plan.

**Esto invalida en la práctica la enmienda de DP-13**, que puso al desarrollador en
Sonnet precisamente porque el cuello de botella era el límite semanal. Se hizo cada
token más barato y se multiplicó la cantidad de tokens.

## La nube no era más rápida: era asíncrona

U11 fue L, igual que U12, y tardó **diez horas** con la nube ayudando. Su primera
tanda corrió de la 1:26 a las 8:18: **siete horas, de noche**. No costaba atención,
y por eso no se notaba el reloj. Lo que hay que recuperar de ese modelo no es la
velocidad —no la tenía— sino que el trabajo no consuma la atención de Miguel.

Y tenía su precio en calidad: de las cuatro últimas tandas de la nube, cada una
volvió con al menos un defecto, y la segunda de U11 con seis, dos en compuertas
duras.

## La revisión no es el problema

Se midió por separado. En U12 el agente escribió durante **31 minutos de promedio
por paso** y la revisión con las compuertas costó **10 a 15**. Quitar la revisión
ahorraría un sexto del tiempo y dejaría intacto el tramo que manda.

Y la revisión encontró **un defecto real en cada una de las siete tandas**, todos
después de que las compuertas automáticas estuvieran en verde. Cinco de los ocho
defectos estaban **en la prueba**, escrita a la medida de lo que el código hacía en
vez del criterio que debía comprobar; uno de ellos era la mitad sin cerrar de la
única compuerta dura de la unidad. La tabla completa está en el resumen de código
de U12.

## La decisión

**El código se escribe en la sesión principal, en dos tandas por unidad.** Las dos
palancas juntas: sin el costo de redescubrimiento de un agente sin contexto, y sin
pagar siete veces el costo fijo de una tanda.

La disciplina de romper la conducta y ver si alguna prueba se cae **se queda**, y se
aplica mientras se escribe en vez de como una pasada aparte. Es lo que hizo U10, que
es el punto de comparación rápido.

Lo que se acepta a cambio: el contexto de la sesión principal se llena y hay que
compactar entre tandas. Cuesta menos que 400.000 tokens de redescubrimiento por
tanda.

**Cuándo volver a despachar un agente:** cuando una tanda sea tan grande que no
quepa en una sesión, o cuando dos unidades independientes puedan correr a la vez. La
regla no es "nunca despachar": es "no despachar siete veces lo que cabe en dos".

**Lo que no cambia:** ninguna compuerta, ningún piso de cobertura, ninguna prueba
que aísle una regla, y ninguna compuerta dura. Se reduce el costo, no el estándar.

## Cómo se planifica U13

U13 es XL. Su plan de generación de código va en **cuatro tandas** de unas mil
líneas, no en ocho pasos de doscientas. La partición de U12 en ocho pasos fue el
único error de proceso que esta evaluación encuentra en ella, y fue una decisión de
planificación, no de ejecución.

## Una cifra corregida

El commit `579d94a`, que cierra U12 en el registro del flujo, dice "quince unidades
construidas de veintidós". Son **catorce**: los eventos `UNIT_COMPLETED` del propio
registro listan u1, u2, u3, u4, u5, u06, u7, u8, u9, u10, u11, u12, u15 y u21. El
error viene de un recuento anterior que ya contaba U12 como construida mientras
todavía estaba en curso, y se arrastró. No se reescribe el commit —la historia de
`main` ya está empujada y reescribirla es peor que la cifra— y queda corregido aquí,
que es donde alguien iría a buscarla.

Con U13 serán quince.
