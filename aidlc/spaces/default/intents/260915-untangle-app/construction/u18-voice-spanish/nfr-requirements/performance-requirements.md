# Rendimiento — U18 `voice-spanish`

Esta unidad **no relaja ninguna meta y no añade ninguna propia de punta a punta**.
Su trabajo de rendimiento es que las de U16 se cumplan igual en el segundo idioma,
y que lo que añade no las mueva.

| Identificador | Qué mide | Meta | Cómo se obtiene su valor |
| --- | --- | --- | --- |
| NFR1 (es) | Del fin del habla al primer audio, **en español** | **p50 < 500 ms y p95 < 800 ms** | `mise run voice:call-live`, de hito, sobre DS-5 en español |
| NFR2 (es) | De la marca de interrupción a que la reproducción pare | **< 300 ms** | El mismo comando de hito |
| NFR3 (es) | Turnos que siguen tras una interrupción sin perder estado | **> 90 %** | El mismo comando de hito |
| PERF-U18.1 | Lo que el reconocimiento de idioma añade al turno | **p95 ≤ 15 ms** | `mise run test:u18` (cronometrado) |
| PERF-U18.2 | El cambio de idioma pedido, de la petición a la respuesta en el idioma nuevo | **cero turnos de retraso** | `mise run test:u18` |

## Por qué PERF-U18.1 y por qué ese número

El presupuesto propio de la llamada es PERF-U16.1: **60 ms** para todo lo que esa
unidad añade entre el fin del habla y el primer audio, medido hoy en 3,9 ms. Esta
unidad mete trabajo nuevo en ese mismo camino —el reconocedor de peticiones y, si
está activa, la detección de idioma— y ese trabajo se cobra del mismo presupuesto.

Quince milisegundos es un cuarto de lo que queda libre. Si se pasa, no es que el
español vaya lento: es que alguien metió el detector en un sitio donde se llama más
veces de las que hace falta, y eso es lo que el número está ahí para atrapar.

**El detector amplio es el caro.** Distinguir "no hay señal" de "esto es portugués"
recorre setenta y cinco idiomas, y por eso solo corre cuando el de dos ya dijo que
no hay señal suficiente, nunca antes.

## PERF-U18.2 no es un tiempo

Es un **conteo**: cero turnos entre la petición y la respuesta en el idioma nuevo.
Está aquí y no en las reglas porque la forma de medirlo es la misma que la de un
presupuesto —se cuenta en una prueba y se publica— y porque el modo de fallo que
vigila es de rendimiento percibido: una petición que tarda un turno en aplicarse se
siente como que no se escuchó.

## Lo que se difiere

Las tres metas de punta a punta en español necesitan **grabaciones de DS-5 en
español**, que llegan en la semana 9 con voluntarios y consentimiento. Hasta
entonces se declaran **no medidas**, nunca se omiten y nunca se rellenan con la
cifra del inglés. Queda con su fila en `pasada-de-publicacion.md`.

## Sources

- `../functional-design/functional-design-questions.md` — D1, D2
- `../../u16-voice-call/nfr-requirements/performance-requirements.md` — PERF-U16.1, de cuyo presupuesto sale este
- `../../../inception/user-stories/stories.md` — AC1.29.x, AC1.30.5

## Assumptions & Open Questions

None.
