# Diseño de observabilidad — U5 `provider-platform`

Esta unidad produce la telemetría de todas las demás, así que su diseño tiene una
obligación que las otras no: **lo que emite tiene que ser imposible de
contaminar**, no solo difícil.

## El ayudante de tramos, con lista cerrada

La única forma de emitir un tramo en este aplicativo es un ayudante de esta
unidad. Nadie llama al SDK de trazas directamente, y eso no se pide: se comprueba.

```python
# telemetry/traces/api.py  (forma, no implementacion)
Atributo = Literal[
    "gen_ai.system", "gen_ai.request.model", "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens", "untangle.node", "untangle.use",
    "untangle.case_id", "untangle.turn_id", "untangle.prompt_id",
    "untangle.prompt_hash", "untangle.cost_usd", "untangle.cost_status",
    "untangle.error_kind", "untangle.attempt", "untangle.provider",
    "untangle.decided_by",
]

def span(name: str, attrs: Atributos) -> AbstractContextManager[Span]: ...
```

> **Corrección del 2026-09-21, aplicada en la compuerta de la unidad.** Esta
> firma se escribió como `span(name, **attrs: Unpack[Atributos])`, y **no puede
> existir**: un nombre con punto —`gen_ai.request.model`— no es un argumento con
> nombre válido en Python, así que ningún llamador podría pasar un solo atributo
> de los quince. Lo que cambió es la **forma del argumento**, no los nombres: los
> atributos viajan como un mapa. Los nombres son el contrato con las convenciones
> GenAI de OpenTelemetry y no se tocan; la forma del argumento no es contrato de
> nadie.
>
> La implementación añadió además una mitad que este documento no tenía:
> **comprobación de forma en ejecución**. Una lista cerrada de *nombres* no
> impide texto libre dentro de un atributo de tipo `str` —el turno entero del
> asegurado pasado como "hash" compila—, así que el resumen tiene que tener sus
> sesenta y cuatro hexadecimales y los identificadores no admiten espacios ni
> saltos de línea. La lista cerrada cierra una puerta, no la puerta.

Tres propiedades:

- **El comprobador de tipos rechaza un nombre fuera de la lista.** No hace falta
  esperar a la prueba de canarios: no compila.
- **Ningún atributo admite texto libre.** Los valores son identificadores,
  nombres de conjuntos cerrados, números y marcas de tiempo. El texto del
  asegurado, la respuesta del modelo y el contenido de una cláusula no tienen
  dónde entrar.
- **Un chequeo estático** —hermano de `redaction:constructor` y de
  `case:constructor`, que ya existen— falla si algún archivo fuera de este módulo
  importa el SDK de trazas. Es la misma forma que encontró agujeros reales dos
  veces en este proyecto.

**La prueba de canarios se hace igual**, como segunda capa: se siembra un turno
con los cuatro tipos de dato personal propios y se inspecciona cada atributo de
cada tramo. Dos capas, no una.

> **Corrección del 2026-09-21, aplicada en la compuerta de la unidad.** La lista
> son **dieciséis** atributos y no quince: falta el decimosexto,
> `untangle.decided_by`. No es un añadido de comodidad; es que **este documento y
> BR6.4 se contradecían entre sí**. La regla exige que la reanudación de un caso
> lleve quién decidió, y en una lista de quince eso no tiene dónde ponerse: un
> consumidor que lo intentara recibía un error de atributo, así que ninguna
> unidad posterior podía cumplir la regla. El valor es el identificador del
> principal de la credencial de personal, **nunca el nombre de nadie**, y está
> además en el conjunto de atributos cuya forma se comprueba en ejecución, por
> la misma razón que los otros cuatro.

## Los tres niveles y su anidamiento

```
tramo del turno
└── tramo del nodo (intake | policy_verification | decision | compliance)
    └── tramo de la llamada al proveedor
```

> **Segunda corrección del 2026-09-21.** Los tres niveles del turno siguen siendo
> tres, y el diagrama de arriba no cambia. Pero los **dos momentos del caso** que
> pide BR6.4 —la pausa hacia la bandeja y la reanudación— ocurren fuera de
> cualquier turno, horas después, así que no son ninguno de los tres y no pueden
> heredar un contexto que ya no existe: reciben el identificador de traza por
> argumento y son tramos raíz de su propio nivel. Darles el nivel del turno
> habría permitido que un nodo colgara de una pausa, que es una traza que
> describe algo que no ocurrió. El vocabulario lo pone esta unidad; quien emite
> cada momento es U12 `graph-runtime` al derivar y U14 `inbox` al reanudar.

El identificador de correlación nace con el turno y baja por el contexto; no se
pasa por argumento, para que no se pueda olvidar en una rama. La ruta del grafo,
la pausa hacia la bandeja con su hora y la reanudación con quién decidió cuelgan
del **mismo** identificador de caso.

## La exportación

- **Con destino declarado**: se exporta por OTLP al backend de trazas, por lotes,
  fuera del camino de la respuesta.
- **Sin destino**: se escribe el archivo OTLP de la corrida. Es lo que hace la
  tubería, donde no cabe un backend de trazas, y el reporte enlaza a ese archivo
  y al identificador de traza.
- **Antes de salir**, todo pasa por la redacción de U3. No porque quede texto
  —la lista cerrada ya lo impide— sino porque la regla dice que ninguna salida
  esquiva ese punto, y una excepción "porque aquí no hace falta" es como se
  pierde esa propiedad.
- **Si el destino no responde**: se registra la pérdida y nada más se detiene. Ni
  el caso, ni el gasto, ni el corte. Es una regla, no una aspiración: el módulo
  de gasto **no importa** el de trazas, y la regla de importación lo comprueba.

## El resumen de traza

| Momento | Estado | Qué ve el visitante |
| --- | --- | --- |
| Sale la respuesta | `recording` | "Registrándose" |
| Llega el rastro | `ready` | Nodos, cláusulas recuperadas y verificadas, latencia y costo |
| Pasan diez segundos | `lost` | Que se perdió |

El plazo está atado a la meta del chat —p95 menor que 3 s del envío a la primera
palabra—, así que diez segundos son más del triple de la respuesta entera. El día
que esa meta cambie, este plazo se recalcula en vez de quedarse viejo.

Se muestra solo al navegador que lo produjo, comparando el resumen de la clave.
A cualquier otro se responde igual que si no existiera: no "prohibido", que
confirmaría que existe.

## Indicadores y su lectura

| Indicador | Cómo se calcula | Para qué |
| --- | --- | --- |
| Costo por caso, por proveedor y por mes | Del registro de gasto, siempre con su conteo de no medidas | Las cifras publicadas |
| Acumulado de la ventana | De la fila única, nunca sumando | El corte y la alerta |
| Llamadas por tipo de error | De los eventos de intento | Ver si un proveedor se está degradando antes de que el circuito abra |
| Aperturas de cortacircuitos | De sus eventos de cambio de estado | Distinguir "el proveedor está lento" de "el proveedor está caído" |
| Resúmenes perdidos | De los que llegan a `lost` | Ver si el backend de trazas está sano, sin que eso detenga nada |

**Ninguno se publica como promedio combinado de los dos idiomas.** Es la regla de
paridad del proyecto y se aplica aquí igual que en el reporte de evaluaciones.

## La alerta, y lo que no se alerta

Una sola alerta: al cruzar los 3 USD acumulados, una vez, con la marca escrita en
la misma transacción. Lleva cuánto se lleva gastado, cuánto queda, cuántos días
faltan de la ventana y **cuántas llamadas no se pudieron medir**, porque un
acumulado con veinte llamadas sin precio no significa lo mismo que uno sin
ninguna.

**No se alerta** el techo alcanzado: el sistema ya respondió por sí mismo
—cerrando el carril público con el texto del catálogo— y alertar de algo ya
resuelto es el ruido que hace que las alertas dejen de leerse.

## Sources

- `../nfr-requirements/observability-requirements.md` — OBS-U5.1 a OBS-U5.6
- `../nfr-requirements/security-requirements.md` — NFR11.5 y NFR11.6
- `../functional-design/rules.md` — BR6.1 a BR6.7, BR7.3, BR4.8
- `<record>/inception/contract-design/contract-summary.md` — C-23 y C-13
- `docs/reference/arquitectura-y-tecnologia.md` — §11: OpenTelemetry con
  `gen_ai.*`, Langfuse en local, archivo OTLP en la tubería
- `nfr-design-questions.md` — Q4

## Assumptions & Open Questions

- La versión exacta de las convenciones `gen_ai.*` se fija en la generación de
  código: están en estado de desarrollo y anclarla es lo que impide que un cambio
  del estándar mueva los nombres de los atributos sin avisar.
- El destino público de las trazas y el canal de la alerta los decide el intent
  `infra` (PA-10).
- El tamaño del lote de exportación y su intervalo se fijan en la generación de
  código; lo que esta etapa decide es que la exportación no está en el camino de
  la respuesta.
