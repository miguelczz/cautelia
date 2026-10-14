# Piezas lógicas — U4 `case-record`

En qué se parte el módulo del registro del caso, qué puede importar qué, y dónde
cae cada control.

**Fuentes consumidas.** `../nfr-requirements/security-requirements.md` y
`../nfr-requirements/tech-stack-decisions.md`,
`../functional-design/functional-spec.md`, `../functional-design/rules.md` y
`../functional-design/entities.md`, y
`../../../inception/contract-design/contract-summary.md` (C-12).

## Las siete piezas

| Pieza | Qué contiene | Por qué está separada |
| --- | --- | --- |
| `api.py` | La superficie congelada del contrato C-12: la vista del caso y las siete operaciones | Es lo único que ven las siete unidades que consumen esta. Todo lo demás puede cambiar sin avisar a nadie |
| `models.py` | Las cinco entidades, los enums cerrados y los siete objetos de valor | No importa nada del módulo. Es la base sobre la que se apoyan las otras seis, y tenerla aislada es lo que permite probar cada pieza sin levantar la base |
| `schema/` | Archivos versionados, no código: los campos declarados por tipo de registro y la tabla de transiciones | Añadir un campo o una transición es editar un archivo de datos, no una rama de código. Es lo que hace el juego auditable de un vistazo |
| `rules.py` | La aplicación de transiciones, el cálculo de completitud y la evidencia por campo | Es la lógica de decisión de la unidad, y es pura: recibe estado y devuelve estado, sin tocar la base. Por eso se prueba entera sin contenedor |
| `crypto.py` | El punto único de cifrado: fabrica el tipo sellado, lo abre, y lee la clave del entorno | Una sola puerta hacia el almacén para el dato personal. Con dos, la afirmación "todo lo personal se cifra" habría que revisarla cada vez que alguien añade una |
| `repository.py` | La persistencia, por el punto único de sesión de U2 | Es la única pieza que sabe que hay una base de datos. No conoce la clave ni el algoritmo: recibe valores ya sellados |
| `purge.py` | El purgador de datos de visitante que implementa el contrato de U2 | Lo llama el reinicio nocturno de U20, no el aplicativo. Separarlo deja visible que el borrado tiene un dueño y un contrato |

## Qué puede importar qué

```
                 api.py
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
     rules.py            repository.py ◄── purge.py
        │                     │
        │                     ▼
        │                 crypto.py
        │                     │
        └────────┬────────────┘
                 ▼
             models.py
                 ▲
                 │
             schema/  (datos, no código)
```

**Cuatro reglas de dirección**, y cada una es un contrato de importación que el
linter comprueba:

1. **`models.py` no importa nada del módulo.** Es el suelo. Si algún día importa
   a `repository.py`, probar una regla exigiría levantar una base.
2. **`crypto.py` no importa `repository.py`, y nadie fuera de `crypto.py`
   importa la biblioteca de criptografía.** Es lo que sostiene que hay una sola
   puerta.
3. **`rules.py` no importa `repository.py` ni `crypto.py`.** La lógica de
   transiciones y completitud es pura; el día que necesite leer de la base, algo
   se diseñó mal.
4. **Ninguna pieza abre una conexión.** Toda consulta pasa por el punto único de
   sesión de U2, y el contrato de importación falla ante cualquier apertura
   plantada en este módulo.

## Dónde caen los fallos

Esta unidad vive dentro del proceso, así que no tiene dominios de fallo en el
sentido de la infraestructura: no hay instancias que caigan por separado. Lo que
sí tiene son **radios de daño distintos según qué pieza falle**, y conviene
tenerlos escritos porque no son iguales.

| Si falla | Qué se rompe | Qué sigue funcionando | Cómo se manifiesta |
| --- | --- | --- | --- |
| `crypto.py` al arrancar (sin clave) | Todo: el proceso no arranca | Nada | A gritos, y a propósito |
| `crypto.py` al leer una fila | Ese campo de ese caso | El resto del caso, y todos los demás casos | El campo aparece marcado como no disponible, con su evento |
| `rules.py` | La transición o el cálculo pedidos | El caso guardado, que no cambia | Error propio que el llamador no captura para seguir |
| `repository.py` | La lectura o la escritura pedida | El resto del proceso | Error de frontera, traducido a la taxonomía cerrada |
| `purge.py` | El borrado de esa noche | El aplicativo entero | El reinicio se reporta en rojo y se reintenta; ninguna superficie pública se publica con un reinicio en rojo |
| `schema/` mal formado | El arranque | Nada | El arranque falla nombrando el archivo y la diferencia |

**El caso que más importa es el segundo**, y por eso está diseñado aparte: es el
único donde la unidad elige seguir en vez de parar, y la razón está escrita en
`security-design.md`.

## Recursos compartidos

Tres, y ninguno es propiedad de esta unidad:

- **La sesión de base de datos con la aseguradora fijada**, de U2. Esta unidad la
  pide y la usa; no la crea ni la configura.
- **La redacción**, de U3. Esta unidad la llama antes de guardar cada turno, y el
  tipo impide saltársela.
- **El catálogo de textos**, de U1. De ahí salen las etiquetas de los estados,
  las resoluciones, los tipos de registro, los motivos de derivación y la marca
  del campo no disponible.

Lo que esta unidad sí posee y otras usan: **el esquema del caso y su tabla de
transiciones**. Siete unidades cuelgan de ellos, así que un cambio aquí no es
local; por eso viven en archivos versionados y no repartidos en código.

## Lo que este módulo no contiene

- **La decisión de cuándo transitar.** La tabla dice qué transiciones existen;
  quién las dispara es U12 `graph-runtime`.
- **Las reglas de la aseguradora.** El caso guarda la categoría y la explicación
  que le entregan; evaluarlas es de U9.
- **El esquema de la solicitud de cotización.** El tipo existe aquí; sus campos
  los aporta U19.
- **El reinicio nocturno.** Esta unidad aporta su purgador; quién lo llama y con
  qué corte es de U20.
