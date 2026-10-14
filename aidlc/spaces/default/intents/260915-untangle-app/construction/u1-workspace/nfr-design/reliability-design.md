# Diseño de confiabilidad — U1 `workspace`

La confiabilidad de esta unidad no se mide en porcentaje de disponibilidad: no
hay nada desplegado. Se mide en **que la misma entrada produzca el mismo
resultado**, y en que un fallo ajeno al código no se disfrace de fallo de
calidad.

**Fuentes consumidas.** `../nfr-requirements/reliability-requirements.md`
(REL-U1.1 a REL-U1.5 y la tabla de recuperación),
`../nfr-requirements/security-requirements.md` (SEC-U1.7, el tope de gasto),
`../functional-design/functional-spec.md` (los estados de una corrida y el Flujo
2), `../functional-design/rules.md` (BR1.2, BR1.3, BR1.4, BR1.5, BR1.7, BR1.11,
BR2.4), `../../../inception/contract-design/contract-summary.md` (C-22 el
corredor y sus conductores, C-27 el reporte) y `nfr-design-questions.md`
(decisiones Q1 y Q2 de esta etapa).

## Sin SLA ni SLO de disponibilidad

Esta unidad no se despliega y no atiende tráfico. Ponerle un porcentaje de
disponibilidad sería inventar una métrica, y una métrica inventada contamina el
mismo reporte que intenta dar confianza. Lo que sí tiene metas numéricas es el
determinismo, y está abajo.

## REL-U1.1 y REL-U1.2 — Determinismo

Dos corridas del mismo commit con el mismo subconjunto tienen que ejecutar los
mismos casos, en el mismo orden, y el asegurado simulado tiene que responder lo
mismo. Cómo se construye:

| Fuente de azar | Cómo se elimina |
| --- | --- |
| Orden de los casos | El subconjunto es una lista **ordenada**; sin subconjunto, el orden es el de los identificadores, que son estables |
| Descubrimiento de archivos | El listado del sistema de archivos se ordena explícitamente antes de usarse; el orden del sistema de archivos no es una garantía |
| El asegurado simulado | Responde por índice de campo, sin ninguna fuente de azar (BR2.4) y **sin llamar a ningún modelo** (BR1.11) |
| Parámetros del modelo | Temperatura en cero y semilla fija donde el proveedor lo permita; identificador de modelo exacto, nunca un alias móvil |
| Reloj y ruta | La hora y las rutas absolutas no entran en ninguna comparación; solo en los campos de la corrida |

**Cómo se comprueba, no cómo se promete:**

- Una prueba corre el corredor dos veces sobre el mismo subconjunto con un
  conductor de prueba y compara la lista de casos ejecutados.
- Otra repite la misma secuencia de campos pedidos contra el respondedor y
  compara la secuencia de respuestas.

**Que un conductor de prueba exista es parte del diseño.** El corredor descubre
sus conductores por registro (C-22), así que una prueba puede registrar uno que
no llama a ningún proveedor. Sin eso, probar el determinismo del corredor
exigiría gastar cuota, y una prueba que cuesta dinero es una prueba que se deja
de correr.

## REL-U1.4 — Fallo cerrado sin clave del modelo

El paso 1 del Flujo 1 valida el entorno **antes de construir ningún cliente de
proveedor**. La validación mira qué necesita **el conjunto que va a correr**, no
la lista entera de variables posibles (enmienda del 2026-09-19):

| Situación | Qué hace |
| --- | --- |
| Falta una variable y algún caso seleccionado la necesita | Termina con código distinto de cero nombrando la variable, sin llamar a nadie |
| Falta y ningún caso seleccionado la necesita | Corre con normalidad |
| Falta y solo la necesitan algunos | Esos quedan no medidos con `provider_key_missing`; la corrida termina y queda no comparable |

La tercera fila es la que sostiene la meta de los 15 minutos: el subconjunto de
arranque no lleva casos que llamen a un modelo, así que quien clona sin cuenta en
ningún proveedor llega al reporte.

El orden importa y es parte del diseño: la validación vive en la construcción del
objeto de configuración, que es lo primero que hace la raíz de composición. Un
diseño que validara al primer uso fallaría a mitad de la corrida, con cuota ya
gastada y con la mitad de los casos ejecutados.

## REL-U1.3 — Degradación honesta sin backend de trazas

El backend de trazas es una dependencia **opcional** del corredor, y el diseño lo
trata como tal:

- El reporte se genera igual.
- Los enlaces de traza salen **marcados como no disponibles**, no vacíos ni
  inventados (`trace_ref` ausente con su marca).
- La corrida **sigue siendo comparable**: la falta de trazas no es un caso no
  medido. Es información perdida sobre por qué pasó algo, no sobre qué pasó.

Es la misma distinción que hace C-23 para el resto del sistema: si el backend de
trazas cae, nada del caso se detiene.

## REL-U1.5 y el corte por cuota — Política de fallo del corredor

Aquí vive el único patrón de resiliencia real de la unidad. La decisión Q2 fija
tres capas:

### Capa 1 — Taxonomía cerrada en la frontera, y cómo se traduce

El corredor no ve tipos de error del proveedor. Los ve traducidos a la taxonomía
cerrada de cuatro valores que fija la convención 8(a) del equipo, y decide sobre
ella. Esa taxonomía describe **qué clase de fallo fue**; lo que el resultado del
caso guarda es **por qué no se pudo medir**, que es un vocabulario distinto y más
grueso: los cinco valores de `not_measured_cause` que fija `entities.md`. La
traducción entre los dos no puede quedar implícita:

| Clase de frontera | ¿Pasajero? | Qué escribe el corredor si vuelve a fallar |
| --- | --- | --- |
| `timeout` | Sí | No medido, con causa `provider_timeout` |
| `rate_limited` | Sí | No medido, con causa `provider_unavailable` |
| `unavailable` | Sí | No medido, con causa `provider_unavailable` |
| `invalid_response` | No | **No es un caso no medido: el caso queda `failed`** |

Y tres causas más que el corredor levanta por su cuenta, sin que haya un error de
proveedor detrás:

| Causa | Cuándo | ¿Cuenta para el cortacircuitos? |
| --- | --- | --- |
| `budget_exhausted` | El registro de gasto alcanza el techo del proyecto **antes** de la llamada; el corredor no llama | Sí |
| `runner_timeout` | El caso supera el tiempo máximo que el propio corredor le da | No: es un límite nuestro, no del proveedor |
| `provider_key_missing` | La clave del proveedor no está en el entorno y el caso la necesita; el corredor no llama | No: no es un fallo del proveedor, es una corrida sin clave a propósito (enmienda del 2026-09-19) |

**Por qué `invalid_response` no es un caso no medido.** El proveedor respondió;
lo que devolvió no sirve. Eso es exactamente lo que la evaluación mide, y
declararlo "no medido" convertiría un fallo de calidad en un problema de
infraestructura. Es la misma línea que el proyecto traza entre "no hay cláusula"
y "no pude verificar": la que separa "esto está mal" de "no lo sé".

**El bit que falta, y quién lo trae.** Un proveedor señala con el mismo código
"demasiadas peticiones ahora mismo" y "tu cuota se acabó", y la taxonomía de
cuatro valores no puede distinguirlos: hablan de la clase del fallo, no de si se
repondrá solo. Hace falta un dato más en la frontera —si el proveedor señaló un
límite agotado o una tasa momentánea— y esa frontera es de **U5
`provider-platform`**, no de U1.

**Qué hace U1 mientras ese dato no exista:** un `rate_limited` persistente se
registra como `provider_unavailable` y **no** cuenta para el cortacircuitos. El
tope de gasto sigue protegido, porque `budget_exhausted` sale del registro de
gasto y no de la respuesta del proveedor. La consecuencia de no tenerlo es
acotada y dicha: una cuota agotada que llegue disfrazada de tasa momentánea
gasta un reintento por caso hasta que el techo de gasto corte.

### Capa 2 — Un reintento para lo pasajero, cero para la cuota

```text
fallo de un caso
  ├─ pasajero        → un reintento, con espera y algo de dispersión
  │                    ├─ pasa  → resultado normal
  │                    └─ falla → no medido, con su causa; la corrida sigue
  └─ no pasajero     → no medido, con su causa; sin reintento
```

Un reintento y no tres: el segundo intento cubre el parpadeo de red, que es el
fallo que de verdad ocurre; del tercero en adelante se paga tiempo por un caso
que casi nunca se recupera. La espera lleva dispersión para que varios casos no
reintenten sincronizados.

**Nunca se reintenta una cuota agotada.** No es un fallo pasajero: reintentarlo
gasta exactamente lo que se está intentando proteger.

### Capa 3 — Corte de la corrida tras tres fallos seguidos de cuota

Es un cortacircuitos, con la forma mínima que el problema pide:

| Parámetro | Valor | Por qué |
| --- | --- | --- |
| Qué lo abre | Tres fallos **seguidos** con causa `quota_exhausted` o `budget_exhausted` | Uno puede ser un caso raro; tres seguidos es que se acabó |
| Qué hace al abrirse | Detiene la corrida y marca **todos los casos restantes** como no medidos con esa causa | Recorrer 130 casos fallando uno por uno gasta tiempo y no añade información |
| Qué no hace | No se vuelve a cerrar dentro de la misma corrida | No hay nada que sondear: una cuota agotada no se repone en segundos |
| Qué deja escrito | La corrida queda **no comparable**, con la causa y su identificador | Es exactamente el caso que la práctica llama "no comparable" |

**Un caso no medido no produce por sí solo un código de fallo.** La corrida
termina, el reporte se genera con lo que hay, y la marca de no comparable es la
que dice que esta corrida no se puede usar para juzgar una regresión.

### Lo que esto significa para la compuerta

U1 entrega resultados por caso y el código de salida de la ejecución. **Quién
bloquea la entrega lo decide U21.** Una compuerta que no se pudo ejecutar se
declara "no medida", jamás se omite: es la diferencia entre "esto está bien" y
"no lo sé", y colapsarlas es cómo un proyecto se convence de que algo funciona.

## REL — El guion de verificación (decisión Q1)

| Paso | Qué hace al fallar |
| --- | --- |
| Escaneo de secretos | **Detiene todo en el acto** |
| Los ocho restantes | Registran el fallo y el guion sigue; al final, una sola lista y código distinto de cero |

El orden de los nueve lo fija `team.md` y este diseño lo transcribe entero, para
que quien escriba el guion no tenga que reconstruirlo:

| # | Paso | Al fallar |
| --- | --- | --- |
| 1 | Escaneo de secretos | Detiene todo |
| 2 | Formato | Sigue |
| 3 | Lint, con sus reglas de seguridad activadas | Sigue |
| 4 | Chequeo de tipos | Sigue |
| 5 | Pruebas deterministas | Sigue |
| 6 | Aserciones de esquema, incluido el chequeo de deriva de los contratos generados (C-28) | Sigue |
| 7 | Chequeos de contenido: frases prohibidas, ausencia de texto de cláusula, paridad de claves y claves sin consumidor | Sigue |
| 8 | Auditoría de dependencias | Sigue |
| 9 | Golden sets de texto | Sigue |

El orden no es indiferente: **lo barato primero**, lo caro al final. Quien rompió
el formato lo sabe en segundos aunque el guion siga corriendo, y el paso que
puede gastar cuota es el último.

**Lo que hace que esto no sea un desastre en la tubería:** el paso 9 es el último
y es el que puede gastar cuota. Si algo anterior ya
falló, el guion lo dice al final igual, pero el gasto ya ocurrió. Es el costo
aceptado de la opción A, y la contrapartida de correr el subconjunto en el plan
gratuito.

## Recuperación

| Situación | Qué se pierde | Qué se hace |
| --- | --- | --- |
| La corrida se interrumpe a mitad | Los resultados de esa corrida | Se vuelve a correr; nada queda a medias porque el reporte se escribe al final |
| El registro local de corridas se pierde | El historial local | Nada bloqueante: los casos y la línea base viven versionados |
| Una corrida se pone roja por causa ajena | Nada | Se marca no comparable con su causa, se repite, y el umbral no se toca |
| El backend de trazas está caído | Los enlaces de traza | El reporte se genera con los enlaces marcados como no disponibles |

**Las corridas no se reanudan a mitad.** Reanudar exigiría un registro parcial
persistente, que es estado nuevo y una fuente de diferencias entre dos corridas
del mismo commit. Es un intercambio consciente: se paga volver a correr a cambio
de que el determinismo sea cierto.

## Metas de esta unidad

| ID | Meta | Cómo se comprueba |
| --- | --- | --- |
| REL-U1.1 | Mismos casos, mismo orden | Prueba que corre dos veces y compara |
| REL-U1.2 | Misma secuencia de respuestas | Prueba que repite la secuencia de campos |
| REL-U1.3 | Reporte sin backend de trazas | Prueba con el backend apagado |
| REL-U1.4 | Corte antes de la primera llamada cuando el conjunto la necesita, y corrida normal cuando no | Dos pruebas sin la variable: una con el subconjunto de arranque, que pasa; otra con casos de conversación, que corta |
| REL-U1.5 | Un caso no medible no rompe la corrida | Prueba con un error de proveedor inyectado |
| — | El corte por cuota se abre a los tres | Prueba con tres respuestas de cuota agotada inyectadas, sin tocar una clave real |
