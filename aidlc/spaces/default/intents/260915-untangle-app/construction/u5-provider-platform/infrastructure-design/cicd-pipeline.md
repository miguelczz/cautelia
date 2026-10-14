# Tubería — U5 `provider-platform`

Qué cambia en la compuerta cuando entra lo que cuesta dinero, y qué no cambia.

**Fuentes consumidas.** `../nfr-design/security-design.md`,
`../nfr-design/observability-design.md` y `../nfr-design/logical-components.md`,
`../nfr-requirements/tech-stack-decisions.md`,
`../functional-design/functional-spec.md`,
`../../../inception/domain-design/components.md`, y
`../../../inception/contract-design/contract-summary.md` (C-16, C-17, C-23,
C-24, C-28). Contrastado contra `scripts/verify.sh`, `mise.toml`,
`app/backend/.importlinter`, `app/backend/pyproject.toml`, `.env.example` y
`docker-compose.yml`.

## Lo que no cambia

El guion único de verificación **sigue teniendo nueve pasos** y el flujo de
GitHub Actions no se toca: invoca `scripts/verify.sh` y no mantiene su propia
lista.

Tampoco cambia el despliegue. Esta unidad corre embebida en el proceso único: no
añade servicio, ni contenedor, ni puerto, ni variable de escalado. El backend de
trazas ya está en `docker-compose.yml` desde el primer commit, con su perfil
`traces`, su base propia y las dos imágenes ancladas por huella digital. U5 lo
usa; no lo introduce.

## El paso 6 no crece, y eso es noticia

U2 encadenó tres comprobaciones dentro del paso 6, U3 dos y U4 dos. **U5 no
encadena ninguna**, y conviene decir por qué, porque parece un descuido y no lo
es:

| Obligación de U5 | Dónde se comprueba | Paso |
| --- | --- | --- |
| El SDK del proveedor solo dentro de su adaptador | Contrato de importación | 3 |
| El SDK de trazas solo dentro del módulo de trazas | Contrato de importación | 3 |
| La contabilidad no importa las trazas | Contrato de importación | 3 |
| Las piezas internas del módulo respetan su orden | Contrato de importación | 3 |
| Ningún atributo de tramo fuera de la lista cerrada | Comprobador de tipos | 4 |
| El dinero no se calcula con coma flotante | Comprobador de tipos | 4 |
| Ninguna tabla excluida del aislamiento tiene columna de texto ni de dato personal | `rls:check`, que **crece por dentro** | 6 |
| Los archivos de configuración de proveedores y precios son válidos | `schema:check`, que ya recorre los versionados | 6 |
| Las tres variables nuevas están declaradas y se leen | `env:check` | 6 |
| Ninguna clave llega a un commit | `secrets` | 1 |

Las dos del paso 6 **ya existen**: `rls:check` gana una consulta y
`schema:check` gana archivos que recorrer. Ninguna de las dos es una tarea
nueva, y encadenar una tercera sería duplicar lo que ya se hace.

## Las tareas nuevas del archivo de tareas

Dos, y ninguna más.

| Tarea | Qué hace | Dónde corre |
| --- | --- | --- |
| `test:u5` | Las pruebas acotadas a la unidad | No entra en el guion: `mise run cov` del paso 5 ya corre la suite entera. Existe para poder correr solo lo de esta unidad mientras se construye |
| `spend:report` | Las cuatro agregaciones de gasto con su conteo de no medidas, y el costo por caso exitoso | A petición y al publicar una versión. **No** en el guion: es el productor del valor real de NFR14.1, no una compuerta |

`spend:report` no se encadena a propósito. Una compuerta que fallara porque el
costo por caso subió sería una compuerta sobre una cifra que todavía no tiene
línea base; lo que hace la práctica del equipo con eso es publicarla y compararla
contra la línea base versionada, que es trabajo de U21.

## Los contratos de importación nuevos

Cuatro, todos en `app/backend/.importlinter`, todos comprobados en el paso 3.

| Contrato | Qué prohíbe | Por qué hace falta |
| --- | --- | --- |
| SDK de proveedor solo en `adapters` | `google` y los demás SDK en `untangle.providers.ports` y `untangle.providers.factory` | El contrato que ya existe deja el paquete `untangle.providers` **entero** fuera de su lista, así que hoy el SDK se podría importar en los puertos. ADR-018 dice "dentro de su adaptador", y `ports.py` es lo que ven seis unidades |
| SDK de trazas solo en `telemetry.traces` | `opentelemetry` en cualquier otro módulo | Es lo que sostiene que ningún tramo se emita saltándose la lista cerrada de atributos, que es la capa 4 del diseño de seguridad |
| La contabilidad no importa las trazas | `untangle.telemetry.traces` desde `untangle.telemetry.spend` | Es lo que hace verdadera la frase "el corte funciona aunque la observación falle". La flecha contraria sí existe y sigue permitida |
| Capas internas de `telemetry` | Que una pieza importe a otra por encima suyo | Mismo patrón que `tenancy` y `redaction` ya tienen: el contrato general vigila las fronteras entre paquetes, este las de dentro |

El primero es una corrección de un contrato que existía desde el primer commit y
que resultó más suelto de lo que el ADR pedía. Se deja escrito como tal, no como
añadido: descubrirlo al leerlo es distinto de no haberlo tenido.

## Lo que ya existe y U5 solo usa

| Obligación de U5 | Lo cubre | Cómo |
| --- | --- | --- |
| Las cuatro tablas nacen con lo que les toca: tres excluidas con su razón, el resumen de traza con su aislamiento y su política | `mise run rls:check` | Le pregunta al catálogo vivo; la lista de exclusión vive en el manifiesto y cada entrada lleva su razón |
| La revisión sube, baja y vuelve a subir | `mise run migrate:check` | Contra una base efímera que levanta el propio comando |
| Las tres variables nuevas están en la plantilla y el código las lee | `mise run env:check` | Compara `.env.example` con lo que el código lee, en las dos direcciones |
| Ninguna clave llega a un commit ni al historial | `mise run secrets` | Primer trabajo del flujo, así que un descuido se sabe en minutos |
| Los textos del corte, de los cuatro motivos de rechazo y del estado "registrándose" salen del catálogo en los dos idiomas | `mise run copy:check` | Paridad de claves y claves sin consumidor |
| Los archivos de proveedores, precios, planes, topes y reserva son válidos | `mise run schema:check` | Valida los versionados contra sus JSON Schema, generados desde los modelos (C-28) |
| Los esquemas generados no se editan a mano | `mise run contracts:check` | Regenera y falla ante la deriva |
| El agregado del 80 % cubre los módulos nuevos | `mise run cov` | El agregado incluye todo el código del aplicativo; U5 no añade fila de módulo crítico |
| Los cuatro contratos de importación nuevos, y los que ya había | `mise run lint` | Es el paso 3; `lint-imports` lee `app/backend/.importlinter` y falla nombrando el contrato roto |
| U5 no fabrica por su cuenta el tipo redactado que exige el punto de salida | `mise run redaction:constructor` | El análisis estático que U3 instaló; cubre a esta unidad sin cambiar nada |
| Las dependencias nuevas no traen vulnerabilidades conocidas | `mise run audit` | Sobre el lockfile, en cada corrida |
| La espera de tres días antes de adoptar una versión sigue viva | `mise run supply:check` | Le pregunta a cada gestor qué valor tiene de verdad |

## Lo que U5 añade a archivos que ya existen

| Archivo | Qué se añade | Cuándo |
| --- | --- | --- |
| `app/backend/pyproject.toml` | Tres dependencias de runtime (`google-genai`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp`) y dos de desarrollo (`vcrpy`, `respx`), cada una con su línea de razón y su licencia | En la generación de código |
| `app/backend/pyproject.toml` | Tres entradas en `[tool.untangle.rls] excluded`, cada una con su razón, y la lista versionada de nombres de columna considerados dato personal al lado | En la generación de código |
| `app/backend/.importlinter` | Los cuatro contratos de arriba | En la generación de código |
| `app/backend/migrations/versions/` | Una revisión con las cuatro tablas: tres del proyecto sin política, una con su aseguradora, su aislamiento habilitado y forzado, su política y su marca de dato de visitante; con su `downgrade()` completo | En la generación de código |
| `app/backend/src/untangle/server/composition.py` | La construcción de los cuatro clientes por uso, la instalación del cifrador de precios y la línea del purgador de U5 en la tupla de purgadores | En la generación de código |
| `app/config/providers/` | La carpeta nueva: proveedores y modelos, tabla de precios con su versión y su fecha, planes por uso, topes declarados con su figura y su fecha de comprobación, reserva de grabación en minutos y parámetros del cortacircuitos | En la generación de código |
| `.env.example` | Los nombres de las tres variables nuevas, **nunca sus valores** | En la generación de código |
| `mise.toml` | Las dos tareas nuevas | En la generación de código |
| `app/backend/src/untangle/tenancy/rls_assertion.py` | **Código nuevo en un archivo de U2**: una segunda consulta al catálogo por las columnas de las tablas excluidas, un modelo para su resultado, y un cambio en la evaluación para que una tabla excluida pase de "saltada" a "comprobada de otra manera" | En la generación de código |
| `app/backend/src/untangle/workspace/schema_check.py` | **Código nuevo en un archivo de U1**: los archivos de `app/config/providers/` a la lista que recorre, y la comprobación de vigencia de los topes —los treinta días— que ningún JSON Schema puede expresar por ser relativa a la fecha de hoy | En la generación de código |

`scripts/verify.sh` **no aparece en esta tabla**, y es la primera unidad de la
que se puede decir eso.

**Dos de las filas tocan archivos ajenos**, y conviene no esconderlo detrás de la
frase "el comando crece por dentro". `rls:check` y `schema:check` absorben dos
obligaciones de U5 sin que nazca una tarea nueva, pero eso no significa que no
cueste código: cuesta código **en módulos cuyas dueñas son U2 y U1**. Las dos
filas de arriba lo dicen con lo que hay que escribir en cada uno, para que
aparezca en el plan de generación de código y no como sorpresa al abrir el
archivo.

## Las claves de proveedor en la tubería

- **No entran.** La compuerta no llama a ningún proveedor: las pruebas de
  contrato de los adaptadores corren contra respuestas grabadas con `vcrpy`, y
  los fallos se inyectan con `respx`. El subconjunto `smoke` del paso 9 tampoco
  necesita clave, y eso es lo que sostiene la cifra publicada de "del clon al
  reporte sin cuenta en ningún proveedor".
- **En la plantilla va el nombre, nunca el valor.** `mise run env:check`
  comprueba las dos direcciones: que no falte ninguna que el código lee y que no
  sobre ninguna que nadie lee.
- **La prueba contra el proveedor real corre por hito**, a mano, con la clave de
  quien la corre. Es lo que ADR-018 pide y no necesita vivir en la tubería.
- **Si una clave llegara a un commit**, la regla del proyecto no cambia aquí: se
  considera comprometida y **se rota en el proveedor**. Con cuatro claves
  separadas por uso, rotar una no toca a las otras tres, que es justo para lo que
  están separadas.
- **La grabación de `vcrpy` filtra las claves** antes de escribirse. Una
  respuesta grabada con su cabecera de autorización dentro sería una clave en el
  repositorio con otro nombre.

## El archivo de trazas de la corrida

En la tubería no hay backend de trazas: no cabe en su máquina. Las trazas de cada
corrida se exportan a un archivo OTLP que se sube como artefacto, y el reporte
enlaza a ese archivo y al identificador de traza.

- **Sale por el mismo punto único** que el envío al backend, así que **va
  redactado**. No hay una vía "interna" de exportación: una segunda vía sin
  redacción sería un punto de salida nuevo, con el agravante de que nadie lo
  llamaría así.
- **Retención corta.** Es el artefacto de una corrida, no un archivo histórico, y
  el repositorio es candidato a publicarse en la semana doce.
- **No contiene claves** por la misma razón que no contiene texto: los atributos
  salen de una lista cerrada y la clave no está en ella.

## Vuelta atrás

La unidad no despliega nada, así que la vuelta atrás es la de la migración: el
`downgrade()` de la revisión, que `mise run migrate:check` ejercita en cada
corrida bajando hasta la base y volviendo a subir.

**Su alcance, dicho antes de que alguien lo ejecute creyendo otra cosa.** Bajar
la revisión borra las cuatro tablas, y dos de ellas son el acumulado del
presupuesto y el registro de gasto.

U4 ya dejó escrito que su `downgrade()` borra las tablas del caso y que no es una
vuelta atrás que preserve datos, así que el fenómeno no es nuevo. **Lo que sí es
nuevo es la consecuencia**, y es de otra naturaleza: los datos de U4 son
sintéticos o de visitante y se regeneran —el reinicio nocturno se los lleva de
todos modos—, mientras que el acumulado de U5 es la única cifra del proyecto que
un criterio de aceptación exige que sobreviva a todo, incluido el reinicio y el
cambio de mes. Un `downgrade()` la borraría, y no hay de dónde reconstruirla.

De ahí lo que hay que escribir y U4 no necesitaba: donde el acumulado signifique
dinero de verdad, bajar esta revisión exige **exportar antes** el acumulado y el
registro. La vuelta atrás del código no tiene ese problema: la revisión puede
quedarse aplicada mientras el código vuelve.

## Decisiones de esta etapa

| # | Decisión | Por qué |
| --- | --- | --- |
| INF-U5-1 | Dos tareas nuevas y ninguna más; el paso 6 no crece | Las obligaciones de esta unidad caen en contratos de importación (paso 3), en el comprobador de tipos (paso 4) y en dos comprobaciones que ya existen y crecen por dentro. Encadenar una tercera sería duplicar |
| INF-U5-2 | El chequeo de emisión de tramos es un contrato de importación, no un tercer análisis estático propio | Los de U3 y U4 existen porque su tipo se borra en ejecución; aquí solo hay un import, que es lo que `import-linter` mira |
| INF-U5-3 | Se aprieta el contrato del SDK del proveedor para dejarlo solo en `adapters` | El contrato que existía dejaba fuera el paquete entero, y `ports.py` es lo que ven seis unidades |
| INF-U5-4 | `spend:report` no entra en el guion de verificación | Es el productor del valor real de una meta, no una compuerta. Compararlo contra la línea base es trabajo de U21 |
| INF-U5-5 | Las tres claves nuevas no entran al entorno de la tubería | La compuerta no llama a ningún proveedor. Una clave ahí es una clave más donde puede filtrarse, y no compra nada |
| INF-U5-6 | El archivo OTLP de la corrida va redactado y con retención corta | Un artefacto de un repositorio candidato a público no es interno, y "interno" es la palabra que precede a las fugas de este tipo |
| INF-U5-7 | Se escribe que bajar la migración de U5 **no** es una vuelta atrás aceptable donde el acumulado signifique algo | Es la primera unidad donde la vuelta atrás del esquema y la del código dejan de ser la misma cosa |
| INF-U5-8 | U5 no añade fila de módulo crítico a la configuración de cobertura | No está en la lista afirmada; el agregado del 80 % ya cubre sus módulos. Añadir la fila sería decidir por Miguel una ampliación de esa lista |

## Sources

- `../nfr-design/` — los siete documentos de la etapa anterior
- `../nfr-requirements/tech-stack-decisions.md` — las cinco dependencias y los
  dos comandos
- `../functional-design/functional-spec.md` y `../functional-design/rules.md`
- `<record>/inception/contract-design/contract-summary.md` — C-16, C-17, C-23,
  C-24, C-28
- `<record>/inception/domain-design/decisions.md` — ADR-001 con su enmienda,
  ADR-002, ADR-018
- `scripts/verify.sh`, `mise.toml`, `app/backend/.importlinter`,
  `app/backend/pyproject.toml`, `.env.example`, `docker-compose.yml` — el estado
  real contra el que se escribió cada fila
- `infrastructure-design-questions.md` — las cuatro decisiones delegadas

## Assumptions & Open Questions

- El destino público del backend de trazas, el canal de la alerta y la retención
  del artefacto de la corrida los decide el intent `infra` (PA-10). Esta unidad
  deja el exportador con sus dos caminos y el evento de alerta emitido.
- La prueba de contrato contra el proveedor real corre por hito y a mano. Si
  algún día se quisiera en la tubería, exigiría una clave ahí y una cuota
  dedicada, y sería una decisión con su costo escrito.
- El dimensionado del proceso y de la base lo decide el intent `infra`. Lo que
  esta unidad aporta a esa conversación está en `infrastructure-specification.md`.
