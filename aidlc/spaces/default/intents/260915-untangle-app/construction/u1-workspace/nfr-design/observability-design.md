# Diseño de observabilidad — U1 `workspace`

Qué deja una corrida para que alguien entienda qué pasó sin leer el código, y
dónde sobrevive.

**Fuentes consumidas.** `../nfr-requirements/observability-requirements.md`
(OBS-U1.1 a OBS-U1.4 y la decisión Q4 de esa etapa),
`../nfr-requirements/performance-requirements.md` (NFR17.1, la duración),
`../functional-design/functional-spec.md` (Flujo 1, pasos 4 a 7),
`../functional-design/rules.md` (BR1.3, BR1.4, BR1.5, BR1.8, BR2.2),
`../functional-design/entities.md` (`EvalRun` y `CaseResult`) y
`../../../inception/contract-design/contract-summary.md` (C-23 telemetría, C-27
el reporte).

## Los tres niveles, y qué se lee en cada uno

| Nivel | Qué contesta | Dónde vive |
| --- | --- | --- |
| La corrida | ¿Esta corrida se puede comparar con la anterior? | El registro de la corrida y la cabecera del reporte |
| El caso | ¿Qué falló y por qué? | El resultado por caso, en el reporte |
| El turno | ¿Qué pasó dentro de ese caso? | La traza, cuando existe; U5 es su dueño |

U1 construye los dos primeros y **enlaza** el tercero. No construye trazas: las
consume.

## OBS-U1.1 — Lo que registra una corrida

Campos obligatorios, no opcionales, porque sin ellos dos corridas no se pueden
comparar:

| Campo | Por qué es obligatorio |
| --- | --- |
| `commit_sha` | Una cifra sin commit no es reproducible |
| `model_ids` por uso | Identificador **exacto**, nunca un alias móvil: un alias que se mueve convierte un cambio de modelo en una regresión inexplicable |
| Hash del prompt de cada nodo | Un prompt cambiado sin cambiar el modelo produce el mismo efecto y no se vería |
| `subset` y `subset_declared` | Un reporte parcial que no se anuncia como parcial engaña |
| `duration_seconds` | Se mide siempre, con o sin meta cumplida (BR1.8) |
| `comparable` y `non_comparable_cause` | Es el campo que impide comparar contra la línea base algo que no es comparable |
| `started_at`, `finished_at` | El reloj |

**La cabecera del reporte los muestra todos.** No en un apéndice: arriba, antes
de la primera cifra, porque son las condiciones bajo las que esa cifra vale.

## OBS-U1.2 — Lo que registra un resultado por caso

| Campo | Para qué |
| --- | --- |
| `status` (`passed`, `failed`, `not_measured`) | El veredicto |
| `criteria_results` | Qué criterio falló, no solo que el caso falló |
| `off_script_turns` | Cuántas veces el sistema preguntó algo que el guion no tenía: es señal de que el caso se quedó corto, no de que el sistema esté mal |
| `not_measured_cause` | De una lista cerrada; distingue infraestructura de calidad |
| `trace_ref` | El enlace, o su marca de no disponible |
| Duración del caso | El total sin el reparto no dice qué atacar |

**El identificador del caso es la moneda.** `DS-2/es/017` aparece sin traducir en
el reporte, en el diff contra la línea base, en la sección "Cómo falla" del
README y en cualquier conversación sobre el caso. Nada lo renombra en el camino.

## OBS-U1.3 — Causa cerrada de lo no medido

La lista es cerrada a propósito: `provider_unavailable`, `provider_timeout`,
`quota_exhausted`, `budget_exhausted`, `runner_timeout` y `provider_key_missing`
(esta última añadida el 2026-09-19 con el subconjunto de arranque sin clave). Una causa libre se
convierte en cinco redacciones del mismo problema y deja de poder agruparse.

**La distinción que esta lista protege:** "no hay cláusula" y "no pude verificar"
son valores distintos en todo el sistema, y colapsarlos contamina una métrica
publicada con fallos de infraestructura. Aquí es la misma regla aplicada a la
corrida: un caso que falló y un caso que no se pudo medir nunca se suman.

## OBS-U1.4 — Los dos idiomas lado a lado

El reporte muestra español e inglés **en columnas separadas**, nunca un promedio
combinado (P12). No es una preferencia de formato: un promedio esconde que una
capacidad funciona en un idioma y no en el otro, que es precisamente el riesgo de
un producto bilingüe.

El diseño lo hace difícil de romper: la estructura del reporte tiene el idioma
como dimensión, no como etiqueta. No existe un campo donde escribir un promedio
combinado.

## Dónde sobrevive cada cosa (decisión Q4 de `nfr-requirements`)

| Entorno | Reporte | Registro en base |
| --- | --- | --- |
| Tubería | **Artefacto de la corrida**, con su commit y su fecha | No |
| Local | El mismo archivo | Sí, para consultar el historial sin abrir artefactos uno por uno |

**Por qué la compuerta no depende de una base de datos:** porque esa dependencia
es exactamente la que convierte un fallo de infraestructura en un fallo de
entrega. El diff contra la línea base se hace entre archivos versionados.

**Cómo se construye para que no haya dos caminos:** el corredor escribe el
reporte siempre; el registro en base es un **oyente opcional** que se enchufa en
la raíz de composición cuando hay base disponible. El camino de la corrida es el
mismo con base y sin ella.

## Registro estructurado de la corrida

El corredor escribe a la salida estándar en formato estructurado, una línea por
evento, con el identificador de la corrida y el del caso en cada línea. Es lo que
permite seguir una corrida en la tubería sin descargar el artefacto.

| Evento | Cuándo |
| --- | --- |
| Corrida abierta | Con el commit, el subconjunto y los modelos |
| Caso iniciado / terminado | Con su identificador, su estado y su duración |
| Reintento | Con la clase de error y el número de intento |
| Cortacircuitos abierto | Con la causa; es el evento que explica una corrida corta |
| Corrida cerrada | Con la duración, el recuento por estado y la marca de comparable |

**Nada de esto lleva datos de personas.** Los casos son sintéticos, pero la regla
es "todo punto de salida redacta" sin excepción por origen, y el registro de la
corrida es un punto de salida.

## Alertas: ninguna, y por qué

No hay nada corriendo en producción que alertar. La señal es el código de salida
de la corrida y el estado del flujo sobre `main`. Un `main` en rojo es un
incidente por práctica del equipo, no por una alerta que configure U1.

Lo único que se acerca a una alerta es el fallo del escaneo de secretos, y su
diseño ya lo cubre: primer trabajo, corte inmediato, aviso en minutos.

## Definiciones que esta unidad deja escritas

No son SLO —no hay servicio—, pero son los indicadores que el proyecto va a mirar
y conviene nombrarlos una vez:

| Indicador | Cómo se calcula | Quién lo publica |
| --- | --- | --- |
| Duración de la corrida | `duration_seconds` | U1 |
| Proporción de casos no medidos | No medidos / ejecutados, por causa | U1 |
| Corridas no comparables seguidas | Cuenta de corridas con `comparable` falso | U1 mide; investigarlo es trabajo de quien la vea |
| Tiempo del clon al reporte | El trabajo semanal de NFR21.2, por paso | U1 |

**La proporción de casos no medidos es el indicador más fácil de ignorar y el más
importante.** Una corrida verde con el treinta por ciento de los casos sin medir
no es una corrida verde, y si nadie mira ese número, lo parece.

## Lo que no observa esta unidad

Las trazas por turno, nodo y proveedor son de U5, con su costo, su latencia y sus
tokens. El panel de cifras y el de gasto son de U22. U1 solo enlaza la traza de
cada caso cuando existe y marca el enlace como no disponible cuando no (BR1.3).
