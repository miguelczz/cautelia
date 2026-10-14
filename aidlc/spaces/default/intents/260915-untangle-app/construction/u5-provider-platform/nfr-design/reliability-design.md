# Diseño de confiabilidad — U5 `provider-platform`

La pregunta de esta unidad no es si sigue en pie: es si **sigue cortando**. Lo
que sigue reparte los mecanismos de resiliencia entre esta unidad y el ejecutor
de nodos de U12, que es donde la práctica del equipo los pone, y dice con qué
números corre cada uno.

## El reparto con el ejecutor de nodos

| Mecanismo | Quién lo lleva | Por qué ahí |
| --- | --- | --- |
| Tiempo máximo de la llamada | Esta unidad, por uso | Es una propiedad del transporte hacia ese proveedor |
| Traducción del error a los cuatro tipos | Esta unidad | El tipo del proveedor no cruza al núcleo |
| **Cortacircuitos** | **Esta unidad**, por proveedor y por uso | La salud de una dependencia externa es una sola para todos los nodos |
| Reintento y cuántas veces | El ejecutor de nodos (U12) | Depende de lo que tolere *ese* nodo, no *ese* proveedor |
| Texto de degradación | El ejecutor de nodos, desde el catálogo | Es lo que ve una persona, y sale por el punto único de salida |
| Parada sin reintento ante saldo agotado | Esta unidad | No es un fallo del nodo: es una señal de que hay que parar |

La línea que separa las dos columnas es simple de enunciar: **lo que depende del
proveedor es de aquí; lo que depende del nodo es de allí.** El cortacircuitos cae
de este lado porque si Gemini está caído lo está para los cuatro nodos, y un
mecanismo por nodo obligaría a que cada uno lo descubriera por su cuenta —cuatro
esperas por turno en vez de una—.

## El cortacircuitos, con sus números

- **Alcance:** uno por pareja (proveedor, uso). Por uso y no solo por proveedor
  porque las claves están separadas justamente para que una cuota agotada en el
  chat no apague la voz; un cortacircuitos compartido lo haría igualmente.
- **Umbral de apertura:** cinco fallos consecutivos de tipo `timeout`,
  `unavailable` o `rate_limited`. Un `invalid_response` **no cuenta**: es un
  problema del contenido, no de la salud del proveedor, y contarlo abriría el
  circuito por un prompt mal hecho.
- **Tiempo abierto:** treinta segundos. Con el circuito abierto, la llamada falla
  en el acto con `unavailable` y el nodo aplica su política sobre esa respuesta,
  igual que sobre cualquier otra.
- **Cierre:** una llamada de prueba. Si pasa, cierra; si falla, vuelve a abrir.
- **Dónde viven los números:** en configuración versionada, no en el código, para
  poder cambiarlos sin un despliegue de lógica.
- **Qué deja en la traza:** cada cambio de estado emite su evento con el
  proveedor, el uso y el estado nuevo. Un cortacircuitos que se abre en silencio
  es indistinguible de un proveedor lento.

## La parada, que no es un fallo

Saldo o cuota agotados **no** entran en los cuatro tipos de error a propósito.
Los cuatro admiten política de reintento; este es el único que significa "para".

- No hay reintento, y tampoco degradación automática a otro proveedor: la regla
  del proyecto dice que cuando se acaba un saldo, el trabajo se detiene, se
  identifica qué se acabó y Miguel decide.
- La señal nombra qué se agotó —el techo del proyecto o la cuota de un
  proveedor— para que esa identificación no haya que deducirla.
- El cortacircuitos **no** se abre por esto: el proveedor está sano; lo que se
  acabó es el dinero.

## El corte que falla cerrado

- La lectura del presupuesto lleva **tiempo máximo de sentencia**. Si la base no
  responde dentro de él, la lectura falla en vez de esperar, porque esperar
  también consumiría el presupuesto de latencia del endpoint que la llamó.
- Con la lectura fallida, la llamada facturable se rechaza con el motivo de
  presupuesto. El chat en plan gratuito sigue: no consulta el presupuesto porque
  sus llamadas no son facturables.
- La asimetría no es una rama de código que alguien pueda invertir: sale del
  carril, no de un `if`.

## Degradación, en orden

1. El cupo del sitio baja, porque la fórmula reparte lo que queda entre los días
   que faltan.
2. El carril público de la voz se cierra, antes de pedir el micrófono.
3. La reserva de grabación sigue intacta: es la única que no se puede volver a
   llenar cuando hace falta.
4. El chat entra en modo degradado al alcanzar su propio límite, con mensaje
   honesto.

Ninguno es una caída. Los cuatro son respuestas, y las cuatro salen del catálogo
de textos en el idioma de la conversación.

## Salud, respaldo y recuperación

**Salud.** Esta unidad aporta a la salud del proceso dos señales: si el cifrador
de precios cargó y si el exportador de trazas tiene destino. Ninguna de las dos
es motivo para declarar el proceso no apto: sin destino de trazas el aplicativo
funciona, y eso ya está decidido.

**Respaldo y recuperación.** No se diseñan aquí. La base es una sola y su
respaldo es del intent `infra`; lo que esta unidad aporta a esa conversación es
qué **no se puede perder**: la fila del acumulado y el registro de gasto, que son
las únicas que no se pueden reconstruir desde ningún otro sitio. Los contadores
de cuota se reconstruyen solos al día siguiente y los resúmenes de traza se
borran cada noche de todos modos.

## Sources

- `../nfr-requirements/reliability-requirements.md` — NFR15.1 a NFR15.6 y REL-U5.1
- `../nfr-requirements/security-requirements.md` — la decisión NFR-U5-3
- `../functional-design/rules.md` — BR2.1 a BR2.5, BR4.1 a BR4.10, BR5.6, BR5.7
- `<record>/inception/contract-design/contract-summary.md` — C-16 y C-17
- `aidlc/spaces/default/memory/{team,project}.md` — la política de fallo por nodo
  aplicada por un ejecutor común, y la regla de cero renovaciones
- `nfr-design-questions.md` — Q1

## Assumptions & Open Questions

- El ejecutor común de políticas de fallo por nodo es de U12 `graph-runtime` y
  todavía no existe. Este documento declara qué espera de él —que aplique su
  política sobre los cuatro tipos de error— y no lo diseña.
- El respaldo de la base y la recuperación del proceso los decide el intent
  `infra`. Lo que esta unidad aporta es la lista de lo que no se puede perder.
