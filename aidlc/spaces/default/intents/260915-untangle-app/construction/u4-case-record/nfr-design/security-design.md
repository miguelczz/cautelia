# Diseño de seguridad — U4 `case-record`

Cómo se construye cada uno de los quince controles.
`security-requirements.md` dice **qué** tiene que cumplirse y con qué comando se
mide; aquí está **cómo**.

**Fuentes consumidas.** `../nfr-requirements/security-requirements.md` y
`../nfr-requirements/tech-stack-decisions.md`,
`../functional-design/functional-spec.md`, `../functional-design/rules.md` y
`../functional-design/entities.md`, y
`../../../inception/contract-design/contract-summary.md` (C-12, C-11 y C-13).

## El principio que ordena todo lo demás

Esta unidad falla de dos maneras muy distintas, y el diseño está hecho para la
segunda.

Una **transición mal hecha falla a gritos**: el modelo la rechaza, lanza su error
y deja su evento. Nadie puede no enterarse.

Un **campo personal guardado sin cifrar no falla en absoluto**. La pantalla se
dibuja, el caso se abre, el ajustador decide, las pruebas pasan. Lo único que
cambia es que el nombre del testigo quedó legible para quien alcance el almacén,
y eso no lo nota nadie hasta que ya pasó.

De ahí la regla que ordena las cuatro capas: **lo que falla en silencio se
impide por construcción, no por disciplina**. Un desarrollador que escriba mal
el código de cifrado tiene que encontrarse un error del compilador, no una fila
mal guardada.

## Cuatro capas

### Capa 1 — La frontera del tipo: que no se pueda escribir el error

El valor cifrado tiene un tipo propio, y la persistencia **solo acepta ese
tipo** en las columnas con dato personal. Guardar una cadena cualquiera en la
columna del nombre de una parte no es un error de ejecución: no compila.

Es el mismo mecanismo con el que U3 protege la transcripción —el tipo redactado,
que `api.py` es el único que fabrica— y se elige por la misma razón: convierte
una regla que alguien tiene que recordar en una que la herramienta comprueba
antes de correr.

```python
# case_record/crypto.py  (forma, no implementación)
Sealed = NewType("Sealed", bytes)

def seal(value: str) -> Sealed: ...
def unseal(value: Sealed) -> str | Unavailable: ...
```

El constructor de `Sealed` solo se invoca dentro de este archivo. Un análisis
estático lo comprueba, igual que `mise run redaction:constructor` lo comprueba
para el tipo redactado, y falla si aparece un `cast`, una anotación con
`type: ignore` o una llamada al constructor en cualquier otro sitio.

### Capa 2 — El punto único de cifrado: que no haya una segunda vía

Un solo archivo del módulo sabe cifrar y descifrar. El repositorio no conoce la
clave ni el algoritmo: recibe valores ya sellados y los escribe.

Eso deja **una sola puerta** por la que puede pasar un dato personal hacia el
almacén, que es lo que hace comprobable la afirmación "todo lo personal se cifra
antes de persistir". Con dos puertas, la afirmación habría que revisarla cada vez
que alguien añade una.

La regla de importación lo sostiene: ningún archivo del módulo fuera de
`crypto.py` importa la biblioteca de criptografía, y `crypto.py` no importa el
repositorio. La dirección es una sola y el linter la comprueba.

### Capa 3 — El aislamiento por debajo: que la clave no sea suficiente

El cifrado no sustituye al aislamiento por aseguradora, lo complementa. Una
sesión fijada en Stonecroft no ve una fila de Sunmeadow **aunque tenga la
clave**, porque la política de fila la filtra antes.

Las dos capas protegen contra adversarios distintos y ninguna cubre al otro:

| Quién | Lo para el aislamiento | Lo para el cifrado |
| --- | --- | --- |
| Una consulta del aplicativo con la aseguradora equivocada fijada | Sí | No |
| Un volcado de la base, una copia de seguridad, la consola del proveedor | No | Sí |
| Quien tiene el proceso y su variable de entorno | No | No |

La tercera fila está escrita a propósito. Un control que se cree más fuerte de lo
que es acaba sustituyendo a los que sí harían falta.

### Capa 4 — El borrado: que la ventana se cierre

Lo que no existe no se puede leer. Los casos de origen público se borran enteros
en el reinicio nocturno —con sus campos, sus partes, sus turnos y su historial—,
así que el dato de un visitante real vive como mucho hasta esa noche.

El purgador de esta unidad implementa el contrato que U2 ya definió, y sus tablas
nacen con la marca de dato de visitante en la misma revisión que las crea. La
comprobación no es una lista contra otra lista: una prueba le pregunta al
catálogo de la base qué tablas llevan la marca y falla nombrando la que no tenga
purgador. Comparar dos listas escritas a mano no comprobaría nada, porque quien
olvida una olvida las dos.

## Fallar cerrado al arrancar, fallar visible al leer

La postura no es la misma en los dos momentos, y la diferencia es deliberada.

**Al arrancar, cerrado.** Si la clave de cifrado no está en el entorno, o no
tiene la forma esperada, **el proceso no arranca**. No hay modo degradado que
guarde en claro "mientras tanto": ese modo es exactamente cómo un dato personal
acaba sin cifrar sin que nadie lo decida. Es la misma postura con la que U3 trata
un detector que no carga.

**Al leer, visible.** Si una fila no se puede descifrar —clave equivocada, dato
corrupto, una fila que viajó de una máquina a otra— **el caso se abre igual** y
ese campo aparece marcado como no disponible, con su evento en la traza.

La asimetría tiene una razón: al arrancar, el fallo afecta a lo que todavía no ha
pasado y cerrarse no cuesta nada. Al leer, el caso ya existe y alguien tiene que
decidirlo; un caso que no abre solo dice que algo pasó, mientras que un caso con
un hueco señalado se puede seguir trabajando **y el hueco se ve**. Ocultar el
resto del caso para proteger un campo que ya está ilegible no protege nada.

El valor que ve quien lee nunca es el dato: es la marca del catálogo de textos en
su idioma. El fallo deja rastro doble, igual que todo fallo de esta unidad: un
valor distinguible en la respuesta y un evento en la traza con la fila y la causa.

## La clave, y qué pasa si cambia

**Dónde vive.** En una variable de entorno, declarada en la plantilla, separada
por uso de las dos de firma que U2 ya separa. Nunca en el código, nunca en un
archivo del repositorio, y nunca en el mismo sitio que el dato.

**Cada fila guarda qué clave la cifró.** Una columna pequeña al lado del dato con
el identificador de la clave. Hoy hay una sola y no cambia nada. El día que haya
que rotar, las filas viejas se siguen leyendo con la clave vieja y las nuevas
nacen con la nueva, sin una migración que reescriba el almacén entero ni una
ventana en la que los casos no se puedan abrir.

Es barato —una columna— y abre el camino sin construirlo. La alternativa, una
sola clave sin identificador, obliga a elegir entre no rotar nunca o reescribir
todo de golpe, y las dos son decisiones que nadie quiere tomar el día que se
descubre una clave filtrada.

## Dónde encaja cada control

| Control | Capa | Cómo queda construido |
| --- | --- | --- |
| SEC-U4.1 | 3 | Regla de importación: ningún archivo del módulo abre conexión |
| SEC-U4.2 | 3 | Las tres líneas de aislamiento en la misma revisión que crea la tabla |
| SEC-U4.3 | 3 | Un solo camino de lectura, que no distingue "no existe" de "no es suyo" |
| SEC-U4.4 | 4 | La marca en la revisión, el purgador en el registro explícito |
| SEC-U4.5 | 4 | El borrado en cascada desde el caso, probado con las cinco tablas pobladas |
| SEC-U4.6 | 1 | El tipo redactado de U3 en la firma de la transcripción |
| SEC-U4.7 | 2 | El punto de salida ya declarado, implementado y no duplicado |
| SEC-U4.8 | 1 y 2 | El tipo sellado más el punto único que lo fabrica |
| SEC-U4.9 | — | Variable de entorno en la plantilla; el chequeo de entorno y el de secretos |
| SEC-U4.10 | 2 | El error de cifrado no lleva el valor: lleva la fila y la causa |
| SEC-U4.11 | — | El historial no expone operación de edición ni de borrado en su superficie |
| SEC-U4.12 | — | El ejecutor de transiciones anexa antes de rechazar |
| SEC-U4.13 | — | La evidencia de cierre se valida y se guarda en la misma operación |
| SEC-U4.14 | 3 | El número no es credencial: el acceso lo decide el enlace firmado de U2 |
| SEC-U4.15 | — | Las etiquetas salen del catálogo; el chequeo de paridad lo comprueba |

## Lo que este diseño no cubre

- **Los puntos de control del grafo.** PA-8 los incluye y son de U12. Aquí se
  deja señalado que el catálogo describe el almacén del caso "con RLS y cifrado
  en reposo" y el de los puntos de control solo "con RLS", para que U12 vea la
  diferencia al llegar en vez de heredarla.
- **El cifrado del almacenamiento del proveedor.** Es la segunda capa, la que
  cubre el disco entero, y va encargada al intent `infra` porque no hay proveedor
  elegido.
- **La búsqueda por campos cifrados.** No existe y no se diseña: ninguna consulta
  aprobada la necesita. Si aparece, se reabre la decisión del mecanismo.

## Decisiones de esta etapa

| # | Decisión | Por qué | Quién |
| --- | --- | --- | --- |
| NFRD-U4-1 | Cada fila guarda el identificador de la clave que la cifró | Abre el camino de rotación sin construirlo, por el precio de una columna. Sin él, rotar obliga a elegir entre no rotar nunca y reescribir el almacén de golpe | Miguel |
| NFRD-U4-2 | Un fallo de descifrado no impide abrir el caso: marca el campo y deja su evento | El caso ya existe y alguien tiene que decidirlo. Un hueco señalado se puede trabajar y se ve; un caso que no abre solo dice que algo pasó | Miguel |
| NFRD-U4-3 | El valor cifrado tiene tipo propio y un solo archivo lo fabrica | Es el mecanismo que ya usa U3 para la transcripción, y convierte la regla en algo que el comprobador de tipos aplica antes de correr, en vez de algo que alguien tiene que recordar | Claude |
| NFRD-U4-4 | Sin clave en el entorno, el proceso no arranca | Un modo degradado que guarde en claro "mientras tanto" es exactamente cómo un dato personal acaba sin cifrar sin que nadie lo haya decidido | Claude |
| NFRD-U4-5 | Se escribe explícitamente contra qué **no** protege el cifrado | Quien tenga el proceso y su variable de entorno tiene la clave. Decirlo evita que este control sustituya a los que sí harían falta | Claude |
