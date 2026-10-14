# Hallazgos de la tanda 3 — U14 `inbox`

## 1. El `409` y el `400` que el contrato declara respondían "algo se rompió"

C-05 declara `400` para una decisión sin comentario y `409` para una repetida. El
mapa de estados a códigos de C-01 solo tenía `404` y `405`, así que cualquier otro
estado salía con código `internal`: el esquema decía una cosa y el servidor
respondía otra. Nadie lo había visto porque **U14 es la primera unidad que devuelve
esos códigos**.

Arreglado añadiendo `400`, `409` y `422` al mapa, y `conflict_state` a la lista
cerrada de códigos: un caso ya decidido no es una clave de idempotencia reciclada, y
llamar a los dos `conflict_idempotency` habría mentido en tres de cada cuatro. Una
ruta todavía no puede **elegir** su código —el vocabulario vive en `untangle.server`
y las unidades están por debajo en el contrato de capas—, y eso sigue anotado para
U6, que es su dueña.

## 2. La tabla de permisos y BR4.6 se contradecían

La tabla de U2 dice que un agente de cuenta "nunca cierra" el caso; BR4.6 dice que
marcarlo como enviado **lo cierra** con esa resolución. Las dos aprobadas.

La propia tabla dice cómo resolverlo: *"una acción nueva la añade la unidad que la
introduce, con su fila y su prueba"*. U14 añadió `mark_sent`, con `account_agent:
true` y `adjuster: false`. `decide_case` sigue en `false` para la agencia, así que
AC5.7.3 no se movió: la agencia no aprueba ni rechaza cobertura, y lo que hace es
cerrar con **su** resolución.

Darle `decide_case` habría sido el atajo, y le habría dado también aprobar y
rechazar.

## 3. Cuatro guardias de más, encontradas rompiendo

Cuatro roturas no tumbaron ninguna prueba, y las cuatro por la misma razón: **había
dos comprobaciones para la misma regla y la de fuera siempre gana.**

| Lo que se rompió | Por qué no cayó nada |
| --- | --- |
| El `WHERE` por aseguradora del contador de avisos (tanda 2) | La política de fila ya filtró |
| El argumento de aseguradora de la consulta de la cola (tanda 1) | La credencial ya se comparó |
| La comprobación de "caso ya cerrado" en la decisión | `require_allowed` ya rechaza todo estado que no sea `derived` |
| `require_alive` sobre la sesión del enlace | `verify_case_link` ya compara la caducidad en cada llamada |

Las dos primeras son **capas** legítimas y se quedan, escritas como lo que son. Las
dos últimas eran **copias** dentro de la misma capa y se borraron: dos guardias para
lo mismo significan que el día que una cambie, la otra seguirá diciendo lo de antes,
y nadie sabrá cuál manda.

Distinguirlas es la parte que cuesta, y la regla que sale de aquí es: *una rotura
que no tumba nada obliga a decidir si lo que se rompió era una capa o una copia*.

## 4. Una ruta leyendo el entorno, otra vez

La tanda 1 arregló que la ruta de la cola construyera `Settings()` dentro de la
petición. La tanda 3 lo repitió con la clave del enlace firmado, en la misma unidad
y dos tandas después. Ahora las dos claves se enchufan en **un solo punto**
(`install_keys`), porque con un enchufe por clave la siguiente se añade y alguien
vuelve a escribir `Settings()` "por ahora".

## 5. El enlace no dice de quién es, y eso hay que respetarlo

El token no nombra su aseguradora **a propósito**: si la nombrara, quien tuviera uno
sabría de quién es antes de canjearlo. El canje pregunta a cada aseguradora bajo su
propia política de fila y la primera que lo reconoce se lo queda. Cuesta tres
consultas y no filtra nada, porque cuántas aseguradoras hay es público.

Las alternativas eran peores y quedan escritas: meter la aseguradora en el token
cambia un formato ya emitido y lo revela; buscar sin aseguradora fijada saltaría la
política de fila justo en la consulta que más la necesita.

## Ocho roturas, seis caídas

| Rotura | Qué se cayó |
| --- | --- |
| Se reanuda antes de registrar | Dos pruebas, una de ellas la del orden |
| El comentario deja de ser obligatorio | Dos de las tres variantes de comentario vacío |
| El comentario se persiste sin redactar | Su prueba |
| Un caso ya decidido se vuelve a decidir | **Nada** — guardia de más, borrada |
| Cualquier estado se puede decidir (tras borrarla) | Dos pruebas |
| El enlace también abre la cola | Dieciséis, incluida la de la compuerta |
| El enlace abre cualquier caso | Su prueba |
| El enlace vencido sí abre | Dos, incluida la de los dos bordes |
| `require_alive` desaparece | **Nada** — copia de más, borrada |
| La credencial deja de mandar sobre la cookie | Su prueba |
