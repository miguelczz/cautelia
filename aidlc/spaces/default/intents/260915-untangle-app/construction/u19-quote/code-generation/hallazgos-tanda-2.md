# Hallazgos de la tanda 2 — U19 `quote`

La bandeja del suscriptor: el rol, su permiso, la lista filtrada y la decisión que
reanuda. Escrita en la sesión principal el 2026-10-02, porque el guardián del motor
no deja delegar código de una unidad que no es la que él cree activa (PENDIENTES
1.13, segunda vez que estorba).

**Reglas que cierra:** BR4.1 `[bloquea]`, BR4.2, BR4.3.

## Lo que el diseño no había visto, y cambió la forma de la tanda

**`decide_case` ya estaba en `true` para el ajustador.** FD-U19-5 decía que el
permiso del suscriptor era «una fila más en la tabla», y lo es, pero la acción
**no podía ser la que ya existía**: un ajustador decide la cobertura de los
siniestros de su aseguradora, y reusar esa acción habría hecho imposible lo que
AC6.3.3 comprueba sin quitarle lo que sí le toca. Así que la tanda añade la acción
`decide_quote`.

**Y una acción nueva no basta.** La ruta de decisión es una sola, así que sin nada
más el ajustador seguiría decidiendo solicitudes por ella: el permiso que pide una
decisión **depende del tipo del caso**, y eso es una tabla cerrada
(`_PERMISO_DE_DECISION`) sobre los tres tipos de registro de U4. Es lo único que
separa BR4.1 de U19 de BR4.1 de U14, y la prueba que lo demuestra es la de su
contraria: **el suscriptor tampoco decide un siniestro**. Sin ella, `decide_quote`
sería un permiso *adicional* y no una separación.

**`ListingFilters` no tenía filtro por tipo de caso.** BR4.2 exige que el recorte
sea del servidor, así que entró en la consulta y en su `WHERE`, no después de traer
la página: filtrado fuera de la consulta, el límite y el cursor cuentan filas que la
lista no muestra, y una peticion directa ve lo que la pantalla esconde.

## Las seis piezas

1. `Role.UNDERWRITER` y `Action.DECIDE_QUOTE` en el enum de U2, con la razón escrita.
2. Las nueve filas nuevas de `role-permissions.yaml`: las siete del suscriptor y la
   negativa de los otros dos. Se declararon **todas** las parejas, incluidas las
   denegadas: omitirlas las deniega igual, pero entonces la tabla no dice si se
   pensó, y es el archivo que se lee para explicar un rechazo. La prueba de
   completitud ya existía (`test_la_tabla_declara_cada_pareja_de_rol_y_accion`) y
   las exigía.
3. El filtro `record_type` en `ListingFilters` y en `LISTAR_CASOS`.
4. `ALCANCE_DE_ROL` en `inbox/queue.py`: a qué casos se limita **siempre** la
   bandeja de cada rol. Tabla cerrada con fila para los tres roles, incluidos los
   dos que no se limitan a nada, porque el valor por omisión de un recorte de
   seguridad no puede ser «ninguno». `page()` recibe el rol y aplica el alcance; la
   ruta no acota por su cuenta.
5. La decisión: el permiso se resuelve por el tipo del caso, y la solicitud se
   registra antes de reanudar por el puerto que ya existía (sin tocar
   `decision.py`).
6. `nadia-ferris`, suscriptora de la única aseguradora con `quote_enabled: true`.

**La pantalla no necesitó código.** Es la misma bandeja: el servidor le entrega lo
que el rol puede ver y las acciones que el caso ofrece, y `recordTypeLabel` ya
traía la etiqueta de la tanda 1. Queda su prueba —una fila de tipo
`quote_request` se lee como tal y no como siniestro—, que es lo que faltaba para
que el reuso signifique algo.

## Las siete roturas, y qué se cayó con cada una

| Rotura | Qué se cayó |
| --- | --- |
| El ajustador cotiza (`decide_quote: true` en su fila) | 3 pruebas |
| Decidir una solicitud pide el permiso del siniestro | 7 pruebas |
| El alcance del suscriptor deja de acotar por tipo | 3 pruebas |
| La consulta deja de filtrar por tipo (predicado a `TRUE`) | 2 pruebas |
| El visitante puede decidir su propia solicitud | 1 prueba |
| Se reanuda antes de registrar | 2 pruebas, una de ellas de U14 |
| Un filtro que no se cruza con el alcance se ignora | 2 pruebas |

Las siete son conducta rota, no símbolos que falten. Ninguna prueba hubo que
corregir: las siete cayeron donde debían.

## Lo que encontró el grep de la forma 14

Llené algo que estaba en uno: Sunmeadow pasó de una persona a dos. **Una prueba se
apoyaba en eso** —`test_las_tres_aseguradoras_reales_cargan_con_sus_nombres_y_sus_personas`
fijaba la lista entera— y se puso roja. Se corrigió la expectativa, que es lo
correcto: la configuración ganó una persona a propósito.

Los otros tres consumidores de `staff[0]` siguen apuntando al ajustador porque la
persona nueva se **añadió al final** y no al principio.

## Decisiones que tomé

1. **Una solicitud decidida sale de la lista del suscriptor.** BR4.2 dice «solo
   solicitudes derivadas» y se implementó literal: al decidirla queda cerrada y
   deja de aparecer. Si al verla en uso resulta que hace falta repasar lo decidido,
   es un filtro más y es aditivo.
2. **Un filtro que no se cruza con el alcance devuelve la página vacía**, no lo
   derivado. Devolver lo derivado respondería filas que nadie pidió, y quien las
   lea creerá que eso es lo que hay en el estado que pidió.
3. **El visitante con su enlace no decide su propia solicitud.** El diseño no lo
   nombra. El enlace deja ver el caso propio y, en un siniestro, decidirlo como
   visitante (BR5.5 de U14); en una solicitud de cotización, quien la pidió
   aprobándose a sí misma no es una decisión. Se tomó la lectura más restrictiva,
   con su prueba.
4. **El aislamiento se prueba con un solo suscriptor.** La credencial sale de la
   configuración versionada, así que una segunda aseguradora con suscriptor
   significaría declarar el rol donde la cotización está apagada. Las dos
   solicitudes se siembran **con el mismo contenido** —mismo tipo, estado, idioma,
   canal y motivo—, así que nada en la fila distingue una de otra salvo su
   aseguradora: a una consulta sin el filtro se le caen las aserciones. Y la
   credencial del suscriptor contra la otra aseguradora se rechaza, que es el otro
   lado.
5. **La credencial del agente de cuenta se prueba en su propia agencia.** Desde
   otra aseguradora se rechazaría por no ser de esa aseguradora, y eso no diría
   nada sobre su permiso. Que la agencia no tenga la cotización activa no cambia la
   regla: el permiso no depende de la configuración de quien pide.

## Riesgos que dejo dichos

1. **La sonda viva de aislamiento emite para `staff[0]`** (`evals/live_probes.py`).
   Hoy acierta —y además **falla cerrado**: una cola vacía hace fallar su control
   positivo con un mensaje claro—, pero su significado depende del orden del
   archivo de configuración. No lo toqué: no es de esta unidad y no falla abierto.
2. **La solicitud todavía no llega derivada por sí sola.** La elegibilidad corre en
   el ritmo de fondo, que sigue sin cablear (PENDIENTES 1.8). La bandeja decide lo
   que haya derivado; quien lo deriva es lo que falta.

## Lo que no pude correr

- `scripts/verify.sh`, `mise run cov` (el piso del 80 %) y la suite completa: es la
  máquina de Miguel y la regla del proyecto lo prohíbe. GitHub Actions es la
  compuerta autoritativa.
- Las evaluaciones contra proveedores: no añadí ni toqué casos de DS-4.
- `audit` y `licenses:check` (red): no añadí ninguna dependencia.

## Lo que corrí

- `mise run test:u19`: **389 pruebas**, en verde. La tarea ahora incluye las
  unitarias de `inbox` y las de integración de U19, y su comentario dice que la
  tanda 2 necesita motor de contenedores.
- `mise run test:u14`: 102 del backend y 83 del frontend, en verde. Toqué sus
  archivos.
- Las **once compuertas baratas, las once**. Dos salieron rojas y se arreglaron:
  `lint` por el orden de los imports de la prueba nueva, y `schema:check` porque
  `tenant.yaml` es fuente del manifiesto generado (se regeneró con
  `mise run synthetic:generate`: 1 archivo escrito, 159 sin cambios).

## Lo que le falta a U19 para cerrarse

El cableado del grafo de fondo (PENDIENTES 1.8). Con la bandeja construida, el
criterio bloqueante de la pasada de publicación —`quote_enabled` no puede estar en
`true` al publicar sin la tanda 2 y el cableado— queda a medias: la mitad de la
bandeja está hecha, la del cableado no.
