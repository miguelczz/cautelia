# Requisitos de calidad — U4 `case-record`

**Fuentes consumidas.** `../functional-design/functional-spec.md` (los doce
pasos de la tabla de transiciones y los flujos F7 y F8),
`../functional-design/rules.md` (las 42 reglas, en especial las familias BR2,
BR6 y BR7), `../../../inception/requirements-analysis/requirements.md` (FR1.1 a
FR1.7, NFR7, NFR10, NFR18, NFR19 y la restricción de costo C1),
`../../../inception/contract-design/contract-summary.md` (C-12, la superficie de
esta unidad; C-11, el borrado de datos de visitante; C-13, la redacción),
`../../../../codekb/untangle/technology-stack.md`, y las respuestas de
`nfr-requirements-questions.md`.

U4 es el único sitio del aplicativo donde un dato personal se guarda **en
claro**. No es un descuido: el PRD lo decidió así —*"el caso guarda los datos
personales que la operación necesita, cifrados en reposo y bajo RLS; lo que sale
a trazas, logs y evals va redactado"*— y U3 lo dejó escrito como regla, que los
campos estructurados del caso no se redactan. La redacción protege las salidas;
el almacén lo protege esta etapa.

De ahí que el peso de este documento esté en tres sitios y no repartido por
igual: **que el dato guardado no se pueda leer** aunque alguien alcance la base,
**que un caso no se llegue a ver desde otra aseguradora**, y **que un caso de
visitante desaparezca de verdad** en el reinicio de esa noche.

Los objetivos de latencia, escalabilidad y disponibilidad no aparecen aquí
porque esta unidad es una biblioteca dentro del proceso: no atiende peticiones,
no llama a proveedores y no está en el camino del turno. El contrato de la etapa
lo refleja, y por eso U4 produce tres documentos y no siete.

## Qué puede salir mal

| Categoría | Cómo se materializa aquí | Controles |
| --- | --- | --- |
| Divulgación de información | Alguien alcanza el almacén —un volcado, una copia de seguridad, la consola del proveedor— y lee el nombre del testigo, el teléfono del otro conductor o la descripción del accidente tal cual se dijeron | SEC-U4.8, SEC-U4.9, SEC-U4.10 |
| Elevación de privilegio | Una consulta escapa del punto único de sesión, o una tabla nueva nace sin su aislamiento, y un caso se vuelve visible desde otra aseguradora | SEC-U4.1, SEC-U4.2, SEC-U4.3 |
| Divulgación por sondeo | Quien prueba números de caso distingue "no existe" de "no es suyo" y confirma que un caso ajeno existe | SEC-U4.3, SEC-U4.14 |
| Manipulación | Un caso llega a cerrado por un camino que nadie diseñó, o se cierra sin que nadie mirara sus adjuntos | SEC-U4.12, SEC-U4.13 |
| Repudio | Un campo cambia y no se puede decir quién lo cambió, o un intento rechazado no deja rastro y nadie sabe que alguien lo intentó | SEC-U4.11, SEC-U4.12 |
| Divulgación por la transcripción | Un turno se guarda sin pasar por la redacción, o U4 declara un punto de salida propio fuera del registro único | SEC-U4.6, SEC-U4.7 |
| Retención no acotada | Un caso de visitante sobrevive al reinicio nocturno porque su tabla nació sin la marca, o porque el purgador borra el caso y deja huérfanos sus campos, partes, turnos e historial | SEC-U4.4, SEC-U4.5 |
| Divulgación por la interfaz | Una pantalla imprime el valor interno de un estado o de una resolución en lugar de su etiqueta | SEC-U4.15 |

## Objetivos medibles

Siete filas, cada una con su valor esperado y el comando que produce su valor
real. Van a la matriz de verificación de `build-and-test` tal cual.

Dos avisos, los mismos que dejó U3 y por la misma razón:

- **`mise run test:u4` no existe todavía.** Lo crea la generación de código de
  esta unidad, igual que `test:u1`, `test:u2` y `test:u3` los crearon las suyas.
  No entra en el guion de verificación: `mise run cov` ya corre la suite entera
  en el paso 5.
- **Lo que se mide sobre DS-2 se declara igual y se reporta "no medida" con su
  causa**, nunca `N/A`. DS-2 está declarado `built: false` en el manifiesto de
  conjuntos, y no existe todavía ningún subconjunto declarado para él: hoy solo
  hay `smoke`, `rt14` y `rt4-live`. La práctica afirmada prohíbe omitir un
  objetivo porque su dato aún no exista.

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| PA-8 | El dato personal sembrado, leído en crudo desde la columna por el punto único de sesión | **No aparece**, en ninguna de las columnas cifradas: ni entero, ni por fragmentos, ni con otra codificación | `mise run test:u4` |
| NFR7.1 | La completitud calculada, contra los campos que el esquema declara para el tipo de registro del caso | **Exactamente 5/7** en el siniestro sembrado con cinco campos; la consulta de cobertura cuenta sobre sus dos, nunca sobre siete | `mise run test:u4` |
| NFR7.2 | Casos completos de DS-2 que terminan cerrados o derivados, sin quedarse en "esperando al asegurado" | **100 %**, por idioma, nunca promediado (AC1.14.4) | `mise run evals:run` sobre DS-2; **hoy no medida**, porque DS-2 no está construido |
| NFR10.4 | Casos de otra aseguradora obtenidos por la superficie del caso, y si la respuesta de un caso ajeno se distingue de la de uno inexistente | **Exactamente 0** casos ajenos, y las dos respuestas **indistinguibles** entre sí | `mise run test:u4` |
| NFR18.2 | Cobertura de líneas del módulo del registro del caso, que NFR18 nombra como crítico | **80 % o más** | `mise run cov` |
| NFR19.2 | Casos de origen público anteriores al corte que sobreviven al reinicio nocturno, con todo lo que cuelga de ellos | **Exactamente 0** casos, campos, partes, turnos y entradas de historial | `mise run test:u4` para el purgador de esta unidad; la comprobación de que ninguna tabla marcada quedó sin purgador la corre `mise run test:u2`, que interroga al catálogo vivo |
| AC4.10.5 | Estado y resolución finales de cada caso de DS-2 frente a su registro esperado | **Coinciden**, en cada idioma | `mise run evals:run` sobre DS-2; **hoy no medida**, misma causa |

**La entrada de la compuerta de cobertura no se añade todavía.** La declaración
lleva una ruta —`app/backend/src/untangle/case_record`— y esa ruta hoy contiene
un único archivo vacío. La fila entra en `[tool.untangle.coverage]` en el mismo
paso que crea el módulo, igual que `tenancy` entró con U2 y la redacción con U3.
Hasta entonces el piso del 80 % de este módulo no lo mide nadie, y decirlo aquí
es preferible a que se descubra cuando ya no se note.

## Controles

| ID | Control | Cómo se comprueba que existe |
| --- | --- | --- |
| SEC-U4.1 | Toda consulta de esta unidad pasa por el punto único de sesión de U2; U4 no abre ninguna conexión propia ni construye SQL por concatenación | `mise run lint`: el contrato de importación falla ante cualquier apertura de conexión plantada en este módulo |
| SEC-U4.2 | Cada tabla de U4 nace con aislamiento habilitado, forzado y su política de aseguradora, en la misma revisión que la crea | `mise run rls:check` pregunta al catálogo vivo; `mise run migrate:check` falla si una revisión creó una tabla sin su aislamiento en esa misma revisión |
| SEC-U4.3 | Pedir un caso de otra aseguradora y pedir uno inexistente producen la misma respuesta, sin diferencia de contenido ni de camino | `mise run test:u4`: los dos casos sembrados, comparados entre sí |
| SEC-U4.4 | Las tablas de U4 que guardan dato de visitante nacen con la marca `visitor-data` en la misma revisión, y su purgador queda registrado en la raíz de composición | `mise run test:u2`: la prueba compara el registro de purgadores contra las tablas que el catálogo dice que llevan la marca, y nombra la que se olvide |
| SEC-U4.5 | El purgador borra el caso completo: sus campos, sus partes, sus turnos y su historial, sin dejar huérfanos | `mise run test:u4`: se siembra un caso público con las cinco tablas pobladas y se cuenta lo que queda |
| SEC-U4.6 | La transcripción solo acepta texto ya redactado, y el tipo lo impide antes de ejecutar | `mise run types`, más `mise run redaction:constructor`, que falla si U4 fabrica el tipo redactado por su cuenta |
| SEC-U4.7 | U4 implementa el punto de salida `case_transcript` que el registro único ya declara con su unidad dueña; no declara uno nuevo | `mise run lint`: el registro de puntos de salida está cerrado y un séptimo lo hace fallar |
| SEC-U4.8 | Los atributos personales de las otras partes y los valores de los campos del caso se cifran **antes** de persistir, no antes de exportar | `mise run test:u4`: se siembra el caso y se lee la columna cruda |
| SEC-U4.9 | La clave de cifrado sale de una variable de entorno declarada en la plantilla, separada por uso de las dos de firma que ya existen, y nunca del código | `mise run env:check`, que compara la plantilla con lo que el código lee; `mise run secrets`, que escanea lo que se commitea y el historial |
| SEC-U4.10 | Un fallo de cifrado o de descifrado no deja el valor en claro en un log, en una traza ni en el mensaje de error | `mise run test:u4`: se provoca el fallo y se inspecciona lo emitido |
| SEC-U4.11 | El historial es de solo anexar: no existe ninguna ruta del código que edite o borre una entrada | `mise run test:u4`, más la ausencia de esa operación en la superficie pública del módulo |
| SEC-U4.12 | Un intento de transición rechazado y un cierre rechazado dejan su entrada en el historial, con lo que se intentó, aunque el caso no cambie | `mise run test:u4`: se intenta cada transición fuera de la tabla y se cuenta lo escrito |
| SEC-U4.13 | Cerrar exige los cinco adjuntos, y un adjunto vacío se distingue de uno no evaluado | `mise run test:u4`: los dos casos, el del conjunto vacío que cierra y el del no evaluado que no |
| SEC-U4.14 | El número de caso no es credencial: adivinarlo no da acceso, porque el acceso lo decide el enlace firmado de U2 | `mise run test:u4`: se pide un caso existente con un número correcto y sin enlace válido |
| SEC-U4.15 | Ninguna salida imprime el valor interno de un estado, una resolución, un tipo de registro o un motivo de derivación: la etiqueta sale del catálogo por idioma | `mise run copy:check`: paridad de claves y claves sin consumidor |

## El cifrado en reposo, en concreto

Es la decisión que tres documentos aprobados llevaban esperando, y conviene que
quede escrita con su costo a la vista y no solo con su beneficio.

**Qué se cifra.** Los atributos personales de las otras partes —nombre, contacto
y placa del otro conductor, del testigo o del lesionado— y los valores de los
campos del caso, donde viven la descripción de lo que pasó, el lugar y las
lesiones. La transcripción **no**, porque ya va redactada: el dato sensible no
está dentro, y cifrar lo que ya está tapado añade costo sin añadir protección.

**Con qué.** Con la biblioteca de criptografía que el backend ya tiene como
dependencia directa, fijada por una auditoría de seguridad. No entra ninguna
dependencia nueva, así que la justificación que el equipo exige para cada
dependencia de runtime ya está dada.

**Dónde vive la clave.** En una variable de entorno, separada por uso, la tercera
del aplicativo junto a las dos de firma que U2 ya separa. Es la diferencia con
cifrar dentro de la base: allí la clave tendría que viajar hasta el proceso de la
base en cada sentencia, es decir, hasta el mismo sitio del que se quiere
proteger el dato.

**Qué cuesta, dicho sin adornos.** Una columna cifrada así **no se puede filtrar
ni ordenar en SQL**. Hoy ninguna consulta aprobada lo necesita: la bandeja lista
casos por número, estado y prioridad, y ningún criterio de aceptación pide buscar
por el nombre del testigo. Si mañana aparece uno, esta decisión se reabre; no se
resuelve escribiendo una excepción.

**Contra qué protege y contra qué no.** Protege contra quien alcance el almacén
sin alcanzar el proceso: un volcado, una copia de seguridad, la consola del
proveedor de base. **No** protege contra quien tenga el proceso y su variable de
entorno, porque entonces tiene la clave. Decirlo importa: un control que se cree
más fuerte de lo que es acaba sustituyendo a los que sí harían falta.

**Lo que queda encargado al intent `infra`.** Que el proveedor de base gestionada
que elija ofrezca cifrado del almacenamiento en reposo. Es la segunda capa, la
que sí cubre el disco entero, y no se puede fijar aquí porque no hay proveedor
elegido: la elección sigue siendo pregunta abierta de ese intent. U1 ya le dejó
por escrito un encargo de la misma forma —"el proveedor tiene que soportar
aislamiento por fila"—, así que este va al mismo sitio.

**Una asimetría que conviene señalar antes de que se herede.** PA-8 cubre dos
almacenes: los campos del caso y los puntos de control del grafo. El catálogo de
componentes describe el primero "con RLS y cifrado en reposo" y el segundo solo
"con RLS". U4 decide el suyo y **no decide por U12**, pero deja escrito aquí que
la diferencia existe, para que U12 la vea al llegar en vez de heredarla sin
notarla.

## Decisiones de esta etapa

| # | Decisión | Por qué | Quién |
| --- | --- | --- | --- |
| NFR-U4-1 | Se cifra desde el aplicativo, con la biblioteca ya instalada y la clave en variable de entorno separada por uso | Es la única opción que no añade dependencia, que produce hoy un valor real con un comando, y que no pone la clave en el mismo sitio que el dato. Cifrar dentro de la base dependía de una extensión que no está comprobada en la imagen anclada | Miguel |
| NFR-U4-2 | Se cifran los atributos de las otras partes y los valores de los campos del caso; la transcripción no | La descripción del accidente y el lugar son tan personales como el nombre del testigo, y dejarlos fuera sería proteger la mitad. La transcripción ya va redactada | Miguel |
| NFR-U4-3 | El objetivo del cifrado se registra con el identificador `PA-8` y no con un `NFRx.y` | No cuelga de ningún requisito de la tabla de Incepción: esa tabla no contiene ningún requisito de cifrado en reposo, y el revisor de calidad ya lo había señalado como hueco. `PA-8` es el identificador estable que los documentos aprobados ya usan para esta decisión; inventar un número de NFR sería crear trazabilidad falsa | Claude |
| NFR-U4-4 | U4 **no** registra la fila del criterio que bloquea por validez del esquema (AC1.16.3): la registra U10 `compliance`, dueña de esa historia | La regla UG-13 dice que cada meta se registra una sola vez, en su unidad dueña, para que tenga una sola fila en la matriz. U4 aporta el esquema y el control que lo sostiene; la fila de la compuerta es de quien posee el criterio | Claude, aplicando UG-13 |
| NFR-U4-5 | U4 no declara ningún objetivo de latencia | Es una biblioteca dentro del proceso: no atiende peticiones ni está en el camino del turno. Además, hoy ningún comando del proyecto mide latencia de conducta, así que un objetivo así no tendría cómo producir su valor real | Claude |
| NFR-U4-6 | La fila de la compuerta de cobertura se añade en la generación de código, no ahora | La declaración lleva una ruta que todavía no existe. Es el mismo razonamiento que dejaron escrito U2 y U3 para sus propios módulos | Claude, con precedente doble |
| NFR-U4-7 | Se acepta que las columnas cifradas dejen de poder filtrarse y ordenarse en la base | Ninguna consulta aprobada lo necesita hoy. Queda escrito como condición: si aparece un criterio que pida buscar por uno de esos campos, la decisión se reabre en vez de resolverse con una excepción | Claude |
