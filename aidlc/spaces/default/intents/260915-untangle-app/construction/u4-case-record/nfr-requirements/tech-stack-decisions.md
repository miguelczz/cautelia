# Decisiones de herramienta — U4 `case-record`

U4 no elige lenguaje, ni base de datos, ni marco de trabajo: todo eso lo fijó
Domain Design y lo construyó U1. Esta unidad toma **una** decisión de
herramienta, y es la que llevaba esperando desde Incepción: con qué se cifra en
reposo el dato personal del caso.

## El cifrado en reposo

### Lo que había que decidir

Tres documentos aprobados asignan la decisión a esta etapa por nombre —la tabla
de preguntas abiertas de Incepción (PA-8), el contrato C-12 y el propio diseño
funcional de U4— y ninguno dice el mecanismo. Y la decisión no se podía
posponer más: U3 dejó escrito como regla que **los campos del caso no se
redactan**, así que el dato viaja al almacén en claro y el cifrado es la única
protección propia que van a tener.

### Por qué no un servicio de gestión de claves

Porque no cabe. La restricción de costo vigente es **5 USD en noventa días** para
proveedores de pago, con todo lo demás en plan gratuito o auto-hospedado. Un
servicio gestionado de claves o un módulo de seguridad por hardware son la
respuesta correcta en un proyecto con presupuesto; aquí son la respuesta que
consume el presupuesto entero antes de escribir la primera línea.

### Por qué no el cifrado de disco del proveedor, que sería lo más barato

Porque **no hay proveedor**. La elección del hospedaje sigue siendo una pregunta
abierta delegada al intent `infra`. No se puede fijar como objetivo medible algo
cuyo valor real no puede producir ningún comando hoy, y la regla afirmada
prohíbe cerrar un umbral con `N/A`.

Lo que sí se puede hacer, y se hace, es **dejarlo encargado**: el proveedor de
base gestionada que ese intent elija tiene que ofrecer cifrado del almacenamiento
en reposo. Va al mismo sitio y con la misma forma que el encargo que U1 ya le
dejó —"el aislamiento es por seguridad a nivel de fila, así que el proveedor
tiene que soportarla"—, y es la segunda capa: esa cubre el disco entero, esta
cubre las columnas.

### Por qué no `pgcrypto`, que es lo que suena más natural

Es la lectura más literal de "cifrado en reposo" en PostgreSQL, y cuesta cero.
Dos cosas pesan en contra, y la segunda es la que decide:

1. **No está comprobado que la imagen traiga la extensión.** El motor es
   PostgreSQL con `pgvector`, anclado por huella digital. Esa imagen no es la
   oficial de PostgreSQL y ningún artefacto del proyecto declara qué extensiones
   incluye. Apoyar la decisión en que la traiga sería apoyarla en una suposición.
2. **La clave tendría que viajar a la base en cada sentencia.** Cifrar dentro del
   motor significa pasarle la clave como parámetro, es decir, llevarla hasta el
   mismo proceso del que se quiere proteger el dato, y crear un camino nuevo por
   el que puede acabar en un log del servidor. Protege contra quien lee el disco
   y no contra quien lee la base, que es un adversario más cercano.

### Lo elegido

**Cifrar desde el aplicativo, con `cryptography`.** Tres razones, en orden de
peso:

1. **No añade nada.** `cryptography` ya es dependencia directa del backend,
   fijada en `>=50.0.0` por una auditoría de seguridad; entró arrastrada por la
   biblioteca de anonimización de U3. La regla del equipo de justificar en una
   línea cada dependencia nueva de runtime **ya está satisfecha** para esta: no
   hay dependencia nueva, ni superficie de cadena de suministro nueva, ni
   licencia nueva que registrar.
2. **Se comprueba con un comando.** Es lo que convierte PA-8 de principio en
   objetivo medible: se siembra un caso con dato personal, se lee la columna
   cruda por el punto único de sesión, y se exige que el valor sembrado no
   aparezca. Es exactamente la forma de prueba que U3 ya usa para comprobar que
   la redacción ocurre antes de persistir, así que el patrón existe en el
   proyecto y no hay que inventarlo.
3. **La clave no vive donde vive el dato.** Sale de una variable de entorno,
   separada por uso, y el proceso de la base nunca la ve.

### Qué cuesta

Una columna cifrada así **no se puede filtrar ni ordenar en SQL**. Es el precio
real y conviene tenerlo escrito, no descubierto: hoy ninguna consulta aprobada lo
necesita —la bandeja lista casos por número, estado y prioridad—, pero si
aparece un criterio que pida buscar por el nombre de una parte, esta decisión se
reabre.

### Qué **no** depende de esta elección

- **El aislamiento por aseguradora.** Lo da la seguridad a nivel de fila de U2, y
  seguiría igual con cualquiera de las cuatro opciones.
- **La redacción de las salidas.** La transcripción va redactada por
  construcción, y el tipo lo impide antes de ejecutar. Son dos protecciones
  distintas sobre dos cosas distintas, y ninguna sustituye a la otra.
- **Los puntos de control del grafo.** Son de U12, y PA-8 los cubre aparte. Esta
  unidad decide su mitad y deja señalada la asimetría del catálogo, donde el
  almacén del caso figura "con RLS y cifrado en reposo" y el de los puntos de
  control solo "con RLS".

## Dependencias nuevas

**Ninguna.** Es el resultado de la decisión anterior y vale la pena decirlo
aparte: U4 no añade un solo paquete al manifiesto. Lo que añade son tablas, una
revisión de migración y un módulo, todo sobre lo que ya está instalado.

| Qué usa | De dónde sale | Por qué no la biblioteca estándar |
| --- | --- | --- |
| Cifrado simétrico de columna | `cryptography`, ya dependencia directa, fijada `>=50.0.0` | La biblioteca estándar de Python no trae cifrado autenticado; escribirlo a mano es exactamente lo que la guía de seguridad prohíbe |
| Migraciones | Alembic, ya instalado y con una revisión viva de U2 | Es el patrón del proyecto, y `mise run migrate:check` ya comprueba que cada revisión sube, baja y vuelve a subir |
| Aislamiento por fila | El punto único de sesión de U2 | U4 no abre conexión propia; el contrato de importación lo impide |

## Lo que esta unidad no añade al stack

- **Ningún servicio externo.** Ni gestión de claves, ni almacenamiento aparte, ni
  cola. El caso vive en la misma base que todo lo demás.
- **Ninguna tarea nueva en el guion de verificación como paso propio.** Si U4
  necesita una comprobación de esquema, se encadena **dentro del paso 6**, que es
  como lo hicieron U2 con sus tres y U3 con sus dos. El guion sigue teniendo
  nueve pasos y el flujo de GitHub Actions no se toca.
- **Ningún punto de salida nuevo.** El registro único ya declara
  `case_transcript` con U4 como unidad dueña: esta unidad lo implementa, no lo
  declara.
