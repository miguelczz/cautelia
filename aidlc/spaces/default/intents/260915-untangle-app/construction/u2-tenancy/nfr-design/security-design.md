# Diseño de seguridad — U2 `tenancy`

Cómo se consigue cada control que fijó la etapa anterior. Es diseño: patrones y
decisiones, no implementación. El código llega en la etapa siguiente.

**Fuentes consumidas.** `../nfr-requirements/security-requirements.md` (los
catorce controles y los objetivos medibles),
`../nfr-requirements/correcciones-tras-revision.md` (**rige donde contradiga al
anterior**: los nombres de las tres tareas nuevas y la retirada de `NFR12.1`),
`../nfr-requirements/tech-stack-decisions.md`,
`../functional-design/functional-spec.md` (los siete flujos) y
`../../../inception/contract-design/contract-summary.md` (C-07, C-10, C-30).

## El principio que ordena este diseño

**Un control se comprueba interrogando a la herramienta, no leyendo el archivo
donde se escribió.** No es una preferencia de estilo: el 2026-09-20 dos ajustes
de cadena de suministro estaban escritos en un archivo que la herramienta no
leía, nada avisaba, y el control no existía aunque el archivo se viera bien.

En U2 ese principio decide tres piezas del diseño, y son justo las tres que
sostienen la compuerta dura:

| Lo que hay que garantizar | Lo que **no** basta | Lo que se hace |
| --- | --- | --- |
| Toda tabla está aislada | Leer una lista de tablas de un archivo | Preguntar al catálogo vivo qué tablas hay |
| El rol no puede saltarse el aislamiento | Leer cómo se creó el rol en la migración | Preguntar al motor qué privilegios tiene el rol vivo de esta conexión |
| Las dos claves de firma están separadas | Comprobar que hay dos variables de entorno | Probar que una clave **no** valida lo firmado por la otra |

## Capa 1 — Aislamiento en la base de datos

### Punto único de sesión

Una sola función asíncrona de contexto abre la transacción, fija la aseguradora
en la variable de sesión y la cierra. Nadie más construye motores ni sesiones.

```python
# Forma del acuerdo, no codigo final
@asynccontextmanager
async def session_for(tenant_id: TenantId) -> AsyncIterator[AsyncSession]:
    ...  # resuelve el tenant; falla si no existe (BR1.5)
```

Cómo se hace cumplir, sin depender de que nadie lo recuerde:

- **Contrato de importación**: ningún módulo fuera de `tenancy` importa el
  cliente de base de datos ni el mapeador. Es una regla de herramienta, no una
  convención (SEC-U2.2).
- **Regla de seguridad del linter** para el SQL construido por concatenación.
- La variable de sesión se lee siempre tolerando el valor vacío, de modo que
  **sin aseguradora fijada las políticas no ven nada** en vez de fallar abierto
  (BR1.4).

### La política, literal en cada migración

Decisión Q1 de esta etapa: cada migración que crea una tabla escribe sus propias
tres líneas —habilitar el aislamiento, forzarlo, declarar la política—, iguales
salvo el nombre de la tabla. Nada de una función compartida que las migraciones
invoquen.

La razón es de lectura, no de gusto: una migración tiene que decir por sí sola
qué aislamiento dejó. Con una función compartida hay que ir a otro archivo para
saberlo, y cambiar esa función altera en silencio el aislamiento de tablas
escritas meses antes. La duplicación aquí es deliberada: son veintiuna unidades
copiando un patrón de tres líneas que cualquiera revisa de un vistazo.

Que nadie se salte el patrón no lo garantiza la disciplina, lo garantiza
`rls:check`.

### La aserción, contra el catálogo vivo

`rls:check` hace dos preguntas al motor, no a un archivo:

1. Qué tablas tiene el esquema del aplicativo. De cada una exige aislamiento
   habilitado, aislamiento forzado y al menos una política de aseguradora.
2. Qué privilegios tiene el rol vivo de esta conexión. Si ese rol puede saltarse
   las políticas, la aserción falla **aunque todas las tablas estén bien**,
   porque en ese caso las pruebas de aislamiento pasarían sin que exista
   aislamiento.

La lista de exclusión es versionada, corta y con su razón por entrada. Hoy tiene
una sola: la tabla de versiones de migraciones, que no guarda datos del
aplicativo.

**Al arrancar el proceso, la aserción es una condición de arranque.** Decisión
Q2 de esta etapa: si no se puede ejecutar —base caída o inalcanzable— el proceso
**no arranca**, lo dice nombrando la causa y reintenta. Arrancar sin haber
podido comprobar el aislamiento es exactamente el estado en el que una fuga pasa
desapercibida, y este aplicativo es una demostración que se duerme y se
despierta: esperar a que la base responda es conducta normal, no una caída.

### Migraciones

`migrate:check` sube, baja y vuelve a subir contra una base efímera con la misma
imagen anclada por huella del entorno local, conectándose con **el rol del
aplicativo** y no con el superusuario. Falla ante dos cabezas y ante una
revisión que cree una tabla sin su aislamiento en la misma revisión.

## Capa 2 — Identidad y permisos

### Dos claves, dos mecanismos

| Qué se firma | Con qué | Por qué |
| --- | --- | --- |
| Credencial de la bandeja | PyJWT, con su propia variable de entorno | Es el camino documentado del ecosistema y el formato que cualquiera reconoce |
| Enlace de caso | Firma con la biblioteca estándar, con **otra** variable de entorno | Nadie externo lo interpreta y su fila se busca por el resumen del token: un formato estándar añadiría carga útil y superficie sin comprar nada |

La separación se **prueba**, no se declara: hay un caso que presenta lo firmado
con una clave al verificador de la otra y exige rechazo. Sin esa prueba, "las
claves están separadas" es una frase en un documento.

**Rotar invalida en el acto.** No hay ventana de gracia ni clave anterior
aceptada: las credenciales duran doce horas y los enlaces una, así que el costo
real de rotar es volver a emitir con un comando, y una clave comprometida deja
de servir en el instante en que se rota.

### Verificación, en cada petición

Cinco pasos, en este orden, antes de tocar la base:

1. Leer la credencial de su cookie. Sin cookie, responder como si el recurso no
   existiera.
2. Firma. 3. Caducidad. 4. Que la aseguradora de la credencial sea la de los
   datos que se piden.
5. Consultar la tabla de permisos con la pareja (rol, acción). **Lo que no está
   declarado se deniega**; no hay valor por defecto permisivo.

Los pasos 2, 3 y 4 producen **una respuesta idéntica**. No idéntica en
significado: idéntica en bytes, mismo código y mismo cuerpo, para que la
diferencia no sirva de oráculo. La prueba compara las tres respuestas entre sí,
no contra una plantilla.

El paso 5 no vive en ninguna ruta: vive en un punto por el que pasan todas, para
que una ruta nueva no pueda olvidarse de él.

### El rastro

Cada rechazo deja un evento con la aseguradora que se intentó abrir, el rol que
afirmaba la credencial y la **causa real** —la que no se dice hacia afuera—.
Sale por el punto único de salida, como todo lo demás. Es la diferencia entre
detectar un sondeo y enterarse por casualidad.

## Capa 3 — Acceso del visitante

- **El token viaja en el fragmento**, que el navegador nunca manda al servidor:
  no aparece en la barra, ni en la cabecera de procedencia, ni en los registros.
  La pantalla lo lee, lo canjea y limpia la dirección.
- **De la fila se guarda el resumen del token, nunca el token.** La comparación
  del resumen se hace en tiempo constante.
- **Reutilizable mientras valga** (reconciliado con CD-5 el 2026-09-20): cada
  canje entrega una credencial nueva con el tiempo que le quede al enlace, nunca
  más.
- **Las cuatro causas de rechazo responden igual** —inválido, caducado,
  revocado, de otro caso— y ninguna dice cuál fue.
- **La clave del navegador lleva aseguradora** y no guarda nada que identifique
  a una persona.

## Capa 4 — Configuración

- Cada carpeta valida contra su esquema antes de que su aseguradora quede
  disponible. Una rota apaga **solo la suya**, nombrando archivo y clave; una
  configuración de voz rota apaga la voz y deja vivo el chat.
- `tenancy:literals` busca identificadores de aseguradora literales fuera del
  cargador y de las fixtures.
- Las credenciales **no viven en la configuración**: se emiten con un comando.

## Cómo se comprueba cada control

| Control | Comando |
| --- | --- |
| SEC-U2.1, SEC-U2.4 | `mise run rls:check` |
| SEC-U2.2 | `mise run lint` (contrato de importación y regla de seguridad) |
| SEC-U2.3, SEC-U2.5, SEC-U2.6, SEC-U2.7, SEC-U2.8, SEC-U2.10, SEC-U2.11, SEC-U2.13 | `mise run test:u2` |
| SEC-U2.9 | `mise run secrets` y `mise run content:check` |
| SEC-U2.12 | `mise run migrate:check` |
| SEC-U2.14 | `mise run tenancy:literals` |

Los tres comandos nuevos —`rls:check`, `migrate:check`, `tenancy:literals`— los
crea la generación de código de U2 y se invocan desde el paso 6 del guion de
verificación, que ya existe. El guion sigue teniendo nueve pasos.

## Lo que este diseño deja abierto

El mecanismo de aislamiento de las tablas de puntos de control del grafo lo
elige U12, entre un pool por aseguradora y un almacén propio con transacción. En
los dos casos con columna de aseguradora, aislamiento habilitado y forzado, así
que `rls:check` las cubrirá sin cambiar de forma.
