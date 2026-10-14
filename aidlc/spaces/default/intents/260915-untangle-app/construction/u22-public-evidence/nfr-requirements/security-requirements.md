# Requisitos de seguridad — U22 `public-evidence`

Versión corta, por el modo ligero de Construcción del 2026-09-21. Lo que aquí se
protege es de una sola clase: **una pantalla pública que muestra datos de la
demo**, y la demo la usan personas reales.

| Identificador | Qué exige | Cómo se comprueba |
| --- | --- | --- |
| SEC-U22.1 `[bloquea]` | El panel de cifras no sirve ningún identificador de caso, número de caso ni dato de un visitante. Los casos por aseguradora son recuentos | Una prueba que llama al endpoint del panel con casos sembrados y exige que ningún identificador sembrado aparezca en la respuesta |
| SEC-U22.2 `[bloquea]` | El panel de gasto exige credencial, y sin ella responde igual que una ruta inexistente | Una prueba sin credencial y otra con credencial de otra aseguradora: las dos reciben la misma respuesta |
| SEC-U22.3 | El panel de gasto **no reparte el gasto por aseguradora**, y ninguna credencial de aseguradora lo abre | Fixtures con dos aseguradoras y gasto en las dos: la respuesta no nombra ninguna, y las dos credenciales reciben el mismo rechazo que una ruta inexistente |
| SEC-U22.4 | Ningún texto del panel sale sin pasar por el punto único de salida | El chequeo del productor único de la redacción, que ya existe |

**SEC-U22.3 cambió de significado el 2026-09-30, al construirla.** Decía "cada
quien ve el gasto de la suya", y eso no existe: el registro de gasto es dato **del
proyecto** y no lleva política de fila por aseguradora (BR7.1 de U5), así que no
hay "la suya" que filtrar. Lo que sí hay que sostener, y es lo que dice ahora, son
dos cosas comprobables: que el panel no invente un reparto por aseguradora que el
registro no tiene, y que ninguna credencial de aseguradora lo abra.

Lo que **no** exige, y una primera versión de su prueba llegó a exigir: que la
respuesta no traiga identificadores de caso. Este panel pide clave de operador y
AC5.14.1 pide ver el costo por caso; esconder la lista no protege a nadie, porque
quien tiene la clave ya puede consultar cualquier caso que conozca. Que los
identificadores no salgan en la superficie **pública** es otra regla, y la sostiene
SEC-U22.1.

**SEC-U22.1 es la que de verdad importa y es fácil de perder.** Un panel de
"casos por aseguradora" se implementa naturalmente devolviendo la lista de casos y
contándola en el navegador; eso pasaría todas las pruebas de la cifra y filtraría
la lista entera. La prueba está escrita para atrapar justo eso: mira la respuesta
del servidor, no lo que la pantalla dibuja.

## Lo que no aplica, y por qué

- **Límites de tasa propios**: el panel no invoca al modelo. Los límites de la
  superficie pública son de U17 y U20.
- **Entrada de datos**: las dos pantallas son de lectura; no hay formulario.
