# Resumen de la generación de código — U4 `case-record`

Todas las cifras de este documento están **medidas**, y cada una dice con qué
comando sale. Ninguna se escribió de memoria.

Esta es la unidad de la que cuelgan otras nueve, así que el documento está
organizado alrededor de lo que esas nueve van a apoyarse: primero **lo que una
herramienta comprueba** —y no la disciplina de quien escriba después—, luego lo
que se midió, y al final **lo que apareció y el diseño no había previsto**, que
es la parte que vale la pena leer.

---

## 1. Lo que dejó de depender de la disciplina

Cuatro garantías que antes eran una frase en un documento y ahora son un comando
que falla.

| Garantía | Qué la comprueba | Qué pasaba sin ella |
| --- | --- | --- |
| Solo `crypto.py` fabrica un valor sellado | `mise run case:constructor` | `NewType` se borra al ejecutar, así que `Sealed(nombre)` es una llamada legal que el comprobador de tipos acepta |
| El diagrama del ciclo de vida dice lo que dice la tabla | `mise run case:transitions` | Un diagrama editado a mano describe un ciclo que el código no aplica, y nadie lo nota porque el dibujo se ve bien |
| Toda condición nombrada en la tabla tiene implementación | `mise run test:u4` | Una condición mal escrita no se evalúa nunca y la transición pasa siempre: el fallo que se parece a que todo funciona |
| Cada tabla de dato de visitante tiene quien la borre | `mise run test:u2` | Cinco tablas nuevas sin purgador, que es exactamente lo que pasó y lo que la compuerta detuvo |

Las dos primeras corren dentro del paso 6 del guion único de verificación, que
**crece por dentro** y sigue teniendo nueve pasos. Las dos últimas son pruebas,
así que corren en el paso 5 con todas las demás.

## 2. Lo que se midió

| Qué | Cuánto | Comando |
| --- | --- | --- |
| Pruebas de la unidad | 161 | `mise run test:u4` |
| Funciones de prueba escritas | 142 | conteo sobre `tests/unit/case_record` y `tests/integration/u4` |
| Pruebas del proyecto | 481 | `mise run test` |
| Cobertura agregada | 87,47 % sobre piso del 80 % | `mise run cov` |
| Cobertura del módulo del caso | 93,73 % sobre piso del 80 % | `mise run cov` |
| Líneas del módulo | 2 901 en 13 archivos con código  más el `__init__.py` vacío | conteo sobre `src/untangle/case_record` |
| Archivos tocados | 54 | Sale del historial de git y está enumerado en `source-manifest.json` |
| Reglas de negocio impuestas | 42 de 42 | `traceability.json` |
| Pasos del guion de verificación en verde | 9 de 9 | `scripts/verify.sh` |

El módulo del caso entra a la lista de módulos críticos de cobertura, donde
`team.md` ya lo tenía por nombre. Su fallo es silencioso igual que el de la
redacción: un caso que llega a cerrado por un camino que nadie diseñó no rompe
ninguna pantalla ni levanta ninguna excepción.

## 3. Lo que apareció y el diseño no había previsto

Seis cosas. Las dos primeras son defectos de unidades ya cerradas que solo se
vieron construyendo esta.

### 3.1 El chequeo hermano de U3 llevaba vivo y roto

`redaction_constructor` comprueba tres formas de fabricar el tipo redactado. La
tercera —anotar el tipo en la **firma** de una función y callar al comprobador
con `type: ignore`— **no disparaba nunca**: le preguntaba el número de línea a
un nodo del árbol sintáctico que no lo lleva, así que miraba un tramo vacío.

El control existía, se leía bien y no miraba nada. Apareció al escribir la
misma prueba para el chequeo de U4, que U3 no tenía. Arreglado en los dos, con
esa prueba.

### 3.2 El comprobador del catálogo aprobaba catálogos que no cargan

Los seis chequeos de `copy:check` leen el YAML crudo, así que una entrada con un
`surface` fuera del conjunto cerrado los pasaba todos y hacía fallar el
aplicativo al arrancar. Se descubrió añadiendo las etiquetas del caso con
`surface: staff`, que no existe.

Un comprobador que aprueba algo que no carga es peor que no tenerlo: el fallo
aparece lejos de su causa —en la redacción, que falla cerrado y deja de emitir
texto— y ahí no dice de dónde viene. Ahora son siete chequeos.

### 3.3 `model_copy` no vuelve a validar

El ejecutor de transiciones construía el caso movido con `model_copy(update=)`,
que entrega un objeto del tipo correcto **sin pasar por sus validadores**. En un
modelo cuyo valor entero está en sus invariantes, esa es la forma más silenciosa
de perderlas: el código se lee igual y los tipos pasan.

Se añadió `evolve` a la base común, que reconstruye y valida. En cuanto el tipo
empezó a validar de verdad, apareció lo siguiente.

### 3.4 El cierre construía un caso a medias para comprobarlo

`attempt_close` ponía la resolución y los adjuntos sobre el caso todavía sin
cerrar, y **eso viola BR3.5**. Reescrito: los adjuntos se comprueban antes, el
caso cerrado se arma de una sola vez, y las condiciones de la fila se evalúan
sobre el caso que se guardaría. Comprobar sobre un objeto que no podría existir
es comprobar sobre algo que no va a pasar.

### 3.5 BR3.8 no estaba impuesta en ningún sitio

«Un caso derivado porque la persona pidió hablar con alguien lleva prioridad
alta» estaba escrita en las reglas y no la aplicaba nada. Ahora la impone el
tipo y la base. Alguien que pide hablar con una persona ya pidió ayuda una vez,
y que su caso quede detrás de otros en la bandeja es el fallo que se siente como
que no lo escucharon.

### 3.6 El historial no tenía orden

Ordenaba por fecha, así que dos entradas del mismo instante —que las hay, porque
fijar un campo deja su entrada en el mismo milisegundo— quedaban en orden
arbitrario. Lleva ahora una columna de orden de inserción. Un rastro que alguien
audita tiene que poder leerse en el orden en que ocurrió.

## 4. Decisiones de construcción que el plan no tenía

| # | Decisión | Razón |
| --- | --- | --- |
| CG-U4-1 | `from_storage` es la segunda puerta del tipo sellado, en el mismo archivo | Leer es la otra mitad del viaje y la base no sabe de tipos de Python. Sin ella, el repositorio necesitaría un `cast` que el análisis estático prohíbe |
| CG-U4-2 | El purgador se construyó en el bloque 4 y no en el 8 | La prueba de U2 se puso roja en cuanto nacieron las cinco tablas. Dejarla así hasta el bloque 8 era dejar `main` en rojo |
| CG-U4-3 | Los valores de los campos y sus copias del historial se sellan | SEC-U4.8 los cifra igual que el nombre del testigo, y dejar el historial en claro desharía el cifrado para todo lo que alguna vez se corrigió |
| CG-U4-4 | El texto del turno es `str` en el modelo, no el tipo redactado | Importar ese tipo cuesta medio segundo frente a los cincuenta milisegundos del modelo, y el modelo es la hoja que permite probar una regla sin levantar nada. Quien exige el tipo es la puerta |
| CG-U4-5 | Un disparador de la base rechaza editar el historial, pero no borrarlo | La asimetría es deliberada: el reinicio nocturno tiene que poder borrar un caso de visitante entero |
| CG-U4-6 | La columna de orden se añadió a la revisión existente, no en una nueva | Nació en la misma sesión, no está desplegada en ningún sitio, y `migrate:check` reconstruye desde cero en cada corrida |

## 5. Lo que queda para su dueño

Cinco criterios se aplazan, cada uno con la unidad que lo va a cumplir escrita
al lado en `traceability.json`. Ninguno dice «pendiente» a secas:

- **AC1.14.1 a AC1.14.3** — U11 `intake`. Cuándo cierra un bloque, cuándo se
  pide la lectura de confirmación y cómo se reintenta un campo que no se
  confirmó son decisiones del nodo de captura; U4 guarda el resultado.
- **AC1.14.4** — U14 `inbox`. La corrección desde la bandeja usa la superficie
  de U4, que ya existe y ya distingue su evidencia.
- **NFR10.4** — U21 `eval-gates`. U4 aporta las operaciones que se miden; quien
  publica la latencia es el reporte.

## 5 bis. Lo que encontró la revisión asesora

Once hallazgos, seis mayores, **los once arreglados antes de cerrar la etapa**.
Los verifiqué uno por uno ejecutando antes de tocar nada: de los hallazgos de
las etapas de diseño de esta misma unidad, dos de cada diez resultaron falsos, y
darlos por buenos sin comprobarlos habría sido cambiar código correcto.

Los cuatro que más importaban:

**BR2.2 no estaba impuesta.** Un campo que exige lectura de confirmación
—lesiones, lugar, vehículo y conductor— llegaba a `confirmed` sin ella y la
completitud lo contaba. Lo reproduje: construí el campo, `validate_field` lo
aceptó y la cifra subió a 1/7. `fields.py` imponía el umbral de la completitud
(BR2.6) y nadie imponía **cómo se alcanza el estado** (BR2.2). Es la clase de
hueco que no rompe nada: la cifra sube sin que nadie haya leído nada.

**El análisis estático del tipo sellado tenía cuatro vías abiertas.** Un
argumento solo posicional, uno solo por palabra clave, uno de resto variable, y
—la grave— llamar al constructor por un alias de importación:
`from ... import Sealed as S` y después `S(b"en claro")` fabrica un sellado de
verdad que el repositorio escribiría en la columna cifrada. Lo comprobé con
árboles sintéticos: cero hallazgos en las cuatro. Ahora las cuatro se atrapan, y
el chequeo hermano de U3 también.

**El campo y su entrada del historial se escribían en dos transacciones.** Cada
llamada al repositorio abría la suya, así que un fallo del anexado dejaba un
campo escrito sin rastro de quién lo cambió, que es literalmente lo que BR5.1
llama una pérdida. Y en la transición la asimetría era la inversa: la entrada se
anexaba antes del `UPDATE`, así que un fallo del movimiento dejaba en el
historial una transición que no ocurrió. Las dos van ahora en una sola
transacción, y hay dos pruebas que provocan el fallo del segundo paso y
comprueban que el primero se revirtió.

**La ventana para retomar la aportaba entera quien llamaba.** Las cuatro
condiciones de T12 —la única vuelta atrás del modelo— se evaluaban sobre datos
del consumidor, y U4 no leía el suyo propio. Un consumidor que pasara la hora
actual abría la ventana siempre. Ahora U4 saca de su propio historial cuándo
entró el caso en derivado; lo que sigue a cargo del consumidor está escrito en
el contrato.

Los otros siete: la evidencia de cierre se podía reescribir, un caso cerrado
aceptaba cambios en sus campos, faltaba la consulta por número que BR7.3 declara
—y con ella la verificación de SEC-U4.14—, una prueba comprobaba nombres en vez
de conducta, un mensaje de error mandaba a un método que no existe, el docstring
decía seis operaciones cuando hay ocho, y las firmas reales de C-12 divergían
del contrato sin que nadie lo registrara. El contrato quedó enmendado con sus
firmas y su razón, igual que se hizo con FD-U4-5.

Lo que la revisión **no** encontró roto, y lo comprobó en vivo: el aislamiento
por aseguradora, la redacción de la transcripción, el disparador de solo anexar
y el diagrama generado desde la tabla.

## 6. Lo que este documento no dice

No dice que la unidad esté probada contra un despliegue vivo: no hay despliegue
hasta U14, y los escenarios adversariales que lo exigen corren por hito.

No dice que el cifrado proteja contra quien tenga el proceso. Protege contra
quien alcance el almacén sin alcanzar el proceso —un volcado, una copia de
seguridad, la consola del proveedor— y eso está escrito en `crypto.py` con esas
palabras. Un control que se cree más fuerte de lo que es acaba sustituyendo a
los que sí harían falta.
