# Tubería — U4 `case-record`

Qué cambia en la compuerta cuando entra el registro del caso, y qué no cambia.

**Fuentes consumidas.** `../nfr-design/security-design.md` y
`../nfr-design/logical-components.md`,
`../functional-design/functional-spec.md`,
`../../../inception/domain-design/components.md`, y
`../../../inception/contract-design/contract-summary.md` (C-12, C-11, C-28).

## Lo que no cambia

El guion único de verificación **sigue teniendo nueve pasos** y el flujo de
GitHub Actions no se toca: invoca `scripts/verify.sh` y no mantiene su propia
lista. El paso 6 crece por dentro, igual que creció con las tres comprobaciones
de U2 y las dos de U3.

Tampoco cambia el despliegue. Esta unidad es una biblioteca dentro del proceso
único: no añade servicio, ni contenedor, ni puerto, ni variable de escalado. Lo
único que añade al entorno de ejecución es **una variable**, la de la clave de
cifrado.

## Las tareas nuevas del archivo de tareas

Tres, y ninguna más.

| Tarea | Qué hace | Dónde corre |
| --- | --- | --- |
| `test:u4` | Las pruebas acotadas a la unidad | No entra en el guion: `mise run cov` del paso 5 ya corre la suite entera. Existe para poder correr solo lo de esta unidad mientras se construye |
| `case:constructor` | El análisis estático del tipo sellado: quién fabrica un valor cifrado, y si alguien lo hace con un `cast`, con una anotación más `type: ignore` o llamando al constructor fuera de `crypto.py` | Encadenada **dentro del paso 6** |
| `case:transitions` | Regenera el diagrama del ciclo de vida desde la tabla versionada de transiciones y falla si no coincide con el que está escrito | Encadenada **dentro del paso 6** |

`case:constructor` es hermana de `redaction:constructor`, que U3 ya instaló para
su tipo redactado, y existe por la misma razón: la capa 1 del diseño —que no se
pueda escribir el error— solo es una capa si algo la comprueba. Sin ella vuelve
a ser disciplina.

`case:transitions` no es un capricho de formato. La enmienda de ADR-005 pide que
el diagrama se genere desde la tabla y se compare con el versionado, y la razón
es concreta: un diagrama que se edita a mano se desincroniza de la tabla, y
entonces el documento que la gente lee describe un ciclo de vida que el código
no aplica.

## Lo que ya existe y U4 solo usa

Cuatro comprobaciones cubren obligaciones de esta unidad **sin tarea nueva**, y
conviene decirlo para que nadie las duplique:

| Obligación de U4 | Lo cubre | Cómo |
| --- | --- | --- |
| Las cinco tablas nacen con su aislamiento habilitado, forzado y su política | `mise run rls:check` | Le pregunta al catálogo vivo de la base, no a una lista. Una tabla nueva queda cubierta el día que nace |
| La revisión sube, baja y vuelve a subir, y ninguna tabla queda sin aislamiento en su propia revisión | `mise run migrate:check` | Contra una base efímera y virgen que levanta el propio comando |
| El esquema del caso se publica como contrato y no se edita a mano | `mise run contracts:gen` y `mise run contracts:check` | El segundo regenera y falla ante la deriva (C-28) |
| Los archivos versionados del esquema y de las transiciones son válidos | `mise run schema:check` | Valida los archivos versionados contra sus JSON Schema |
| La variable de la clave de cifrado está declarada en la plantilla y el código la lee | `mise run env:check` | Compara `.env.example` contra lo que el código lee, en las dos direcciones |
| Ninguna clave llega a un commit | `mise run secrets` | Primer trabajo del flujo, sobre lo que se commitea y sobre el historial |
| El módulo del caso alcanza su piso propio del 80 % | `mise run cov` | Lee el umbral y la lista de módulos críticos del manifiesto |

## Lo que U4 añade a archivos que ya existen

| Archivo | Qué se añade | Cuándo |
| --- | --- | --- |
| `app/backend/pyproject.toml` | La fila `{ path = "app/backend/src/untangle/case_record", floor = 80.0, reason = "Esquema del caso (NFR18.2)" }` en `critical_modules` | En la generación de código, no antes: la declaración lleva una ruta que todavía no existe |
| `app/backend/migrations/versions/` | Una revisión con las cinco tablas, cada una con su columna de aseguradora, su aislamiento habilitado y forzado, su política, y la marca de dato de visitante donde aplique; con su `downgrade()` completo | En la generación de código |
| `app/backend/src/untangle/server/composition.py` | La línea del purgador de U4 en la tupla de purgadores | En la generación de código |
| `.env.example` | El nombre de la variable de la clave de cifrado, **nunca su valor** | En la generación de código |
| `scripts/verify.sh`, línea del paso 6 | `case:constructor` y `case:transitions`, encadenadas | En la generación de código |
| `mise.toml` | Las tres tareas nuevas | En la generación de código |

## La clave de cifrado en la tubería

Es lo único de esta unidad que toca al manejo de secretos, así que va con sus
límites escritos:

- **En la plantilla va el nombre, nunca el valor.** `.env.example` lista
  variables requeridas; `mise run env:check` comprueba las dos direcciones —que
  no falte ninguna que el código lee, y que no sobre ninguna que nadie lee.
- **En la corrida de la compuerta no hace falta la clave real.** Las pruebas de
  cifrado generan la suya en el arranque del caso de prueba. Una clave de
  producción en el entorno de la tubería sería una clave más donde puede
  filtrarse, sin comprar nada.
- **Si la clave llegara a un commit**, la regla del proyecto es la de siempre y
  no cambia aquí: se considera comprometida y **se rota en el proveedor** —en
  este caso, se genera una nueva y se rotan las filas por su identificador de
  clave—. Borrarla del archivo no cierra el incidente.
- **El escaneo de secretos es el primer trabajo del flujo**, así que un descuido
  con la clave se sabe en minutos, no al final de la corrida.

## Vuelta atrás

La unidad no despliega nada, así que la vuelta atrás es la de la migración: el
`downgrade()` de la revisión, que `mise run migrate:check` ejercita en cada
corrida bajando hasta la base y volviendo a subir. Es lo que convierte "tiene
paso de vuelta atrás" en algo comprobado en vez de declarado.

Una advertencia honesta sobre su alcance: bajar la revisión **borra las tablas
del caso**. En desarrollo y en la demostración es lo correcto —los datos son
sintéticos o de visitante y se regeneran—, pero no es una vuelta atrás que
preserve datos. Decirlo aquí evita que alguien la ejecute creyendo otra cosa.

## Decisiones de esta etapa

| # | Decisión | Por qué |
| --- | --- | --- |
| INF-U4-1 | Tres tareas nuevas y ninguna más; el resto de obligaciones se cubre con comprobaciones que ya existen | Duplicar una comprobación crea dos sitios donde arreglarla y uno donde olvidarla. Se listan expresamente las siete que ya cubren obligaciones de U4 |
| INF-U4-2 | `case:constructor` y `case:transitions` se encadenan dentro del paso 6, no como pasos nuevos | El guion sigue teniendo nueve pasos por construcción, y el propio guion lo deja escrito como regla para las unidades que llegan |
| INF-U4-3 | `test:u4` no entra en el guion de verificación | `mise run cov` ya corre la suite entera en el paso 5; encadenarla sería correr las mismas pruebas dos veces en cada corrida |
| INF-U4-4 | La tubería no recibe la clave de cifrado real | Las pruebas generan la suya. Una clave de producción en el entorno de la tubería es una clave más donde puede filtrarse, y no compra nada |
| INF-U4-5 | Se escribe que el `downgrade()` borra las tablas del caso | Es una vuelta atrás de esquema, no de datos. Un paso de vuelta atrás cuyo alcance no está escrito se ejecuta un día creyendo que preserva algo |
