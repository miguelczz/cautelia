# Entidades — U17 `voice-public-link`

Esta unidad añade **dos campos de configuración, dos contadores y una tabla
versionada**. Ninguna entidad nueva del dominio, y ningún tipo nuevo de decisión.

## Lo que ya existe y solo se llena o se cablea

| Qué | Dónde | Estado hoy |
| --- | --- | --- |
| `CallConfig` con tres campos | `tenancy/models.py` | Corte, aviso y ventana de retoma, con su validador. **Se queda con tres**: los carriles son del sitio |
| `VoiceLimits` | `providers/config.py` | **Ya declaraba los dos carriles**, sin valor por omisión a propósito |
| `ProviderCapConfig` | `providers/config.py`, `prices.yaml` | **Ya era la tabla de topes**, con fecha obligatoria |
| `VoiceOffCode` | `voice/availability.py` | Los cuatro motivos con su frase. Los dos carriles están declarados y **nadie los emite todavía** |
| `quota.voice_mode` y `covers_primary_voice` | `telemetry/spend/quota.py` | **Ya existen y son puras.** Producción no las llama |
| El corte y el aviso | `voice/loop.py` | Construidos y probados por U16 |
| La reserva de la voz principal | `telemetry/spend/` | `reserve_primary_voice(call_id)` y `CallReserve` |

## Los dos carriles: dónde viven, y por qué no en `CallConfig`

**No son campos nuevos: ya existían.** `VoiceLimits`, en `providers.yaml`, declara
`calls_per_visitor_per_day` y `site_daily_cap` **sin valor por omisión a propósito**, con
esta razón escrita: *un límite que el archivo no escribe es un límite que nadie decidió,
y este es el archivo que se revisa cuando hay que explicar por qué se rechazó una
llamada*.

**Y no podían ir a `CallConfig`**, que es por aseguradora: «quince llamadas del sitio»
escrito en tres carpetas son cuarenta y cinco, o las que toque leer. Además el cupo del
sitio se **deriva** cada día de lo que queda del presupuesto (BR5.6 de U5), así que una
copia fija por aseguradora discreparía del cálculo que de verdad protege el dinero.

**Corrige FD-U17-2**, que decía que los dos campos iban a `CallConfig`. Lo encontró la
tanda 1, que los construyó así porque el diseño lo pedía.

## `CallLanes` — los tres números, ya reunidos

Lo que recibe la decisión: los **dos carriles del sitio** (de `VoiceLimits`) y la
**ventana de retoma de la aseguradora** (de `CallConfig`). Reunirlos en un tipo propio es
lo que deja la decisión sin depender de ninguna de las dos configuraciones, y lo que
impide confundir tres enteros en la llamada.

Cuánto se puede volver a una conversación es una decisión de cómo conversa cada
aseguradora; cuántas llamadas caben al día es una cuenta del dinero del proyecto. Por eso
vienen de archivos distintos y se juntan aquí.

## `PublicCallDecision` — lo que devuelve la decisión pura

| Campo | Qué es |
| --- | --- |
| `admitted` | Si la llamada se puede abrir |
| `off_code` | Cuál carril la rechazó, de la lista cerrada que ya existe. Presente solo cuando no se admite |
| `resumes_case` | El caso que retoma, cuando la llamada cae dentro de la ventana |

**Devuelve el código y nunca la frase** (BR1.2). La frase sale del catálogo en el punto
único de salida, igual que el rechazo del chat: una frase resuelta en dos sitios acaba
diciéndose de dos maneras.

**`resumes_case` es un dato de la decisión y no un efecto.** Quien decide no abre nada;
dice qué caso retomaría, y el contador del día no se toca cuando lo hay (BR1.3).

## Los dos contadores

Llamadas de hoy por conexión y de hoy del sitio. Son lo que la decisión recibe como
argumento, no lo que consulta: eso es lo que la deja pura y medible.

**Una retoma dentro de la ventana no incrementa el contador del visitante**, y **sí** el
del sitio. La asimetría está en el contador, no en la decisión, para que la decisión no
tenga que saber qué es una retoma dos veces.

## La tabla de topes del proveedor — **ya existía**

`ProviderCapConfig`, en `prices.yaml`, entregada por U5, con su fecha obligatoria y su
comprobación de vigencia. **Corrige FD-U17-8 y TECH-U17.4**, que la describían como nueva.
Lo encontró la tanda 1, que hizo lo correcto: no creó una segunda y solo mejoró el
mensaje de error para que una fila sin fecha nombre la fila.

La razón por la que la fecha importa sigue siendo la que estaba escrita: un tope
configurado hace tres meses y no comprobado no es un tope, es un recuerdo, y el simulacro
del checklist del segundo día existe para convertirlo otra vez en un tope.

## Lo que esta unidad no añade

- **Ningún motivo nuevo de `VoiceOffCode`**: los cuatro están, y dos de ellos esperaban
  a esta unidad.
- **Ninguna decisión nueva de la voz**: se cablea la que hay.
- **Ninguna tabla de la base**, más allá de donde vivan los dos contadores.

## Sources

- `rules.md` — BR1.1 a BR4.1
- El código: `tenancy/models.py`, `voice/availability.py`, `telemetry/spend/quota.py`,
  `voice/loop.py`

## Assumptions & Open Questions

None.
