# Hallazgos — U22 `public-evidence`, tanda 3 (el README que se regenera)

Escrito en la sesión de la nube. `mise` no pudo descargar Python (el túnel lo
rechazó), así que se instaló con `uv python install 3.13.15` y `uv sync --locked`:
mismas versiones ancladas, y los comandos de `mise.toml` se corrieron directamente.

## Qué se construyó

- `evals/evidence/readme.py` (módulo **puro**): `render_how_it_fails`,
  `render_evaluation_report`, `regenerate` y `check`. Lee la línea base por el mismo
  camino que el panel (`build_snapshot`); no hay un segundo lector.
- `workspace/readme_check.py`: el comando con dos modos, `gen` y `check`.
  Tareas `readme:gen` y `readme:check` en `mise.toml`; `readme:check` entra en el
  paso 7 de `scripts/verify.sh`.
- `README.md` (no existía): párrafo inicial, los ocho encabezados de segundo nivel en
  el orden de AC4.1.1, las dos secciones generadas entre marcas y las seis narrativas
  con una línea que dice que las escribe Miguel en la semana 11 (FD-U22-9).
- `paths.readme_path()`, y `test:u22` incluye las pruebas nuevas.

## Una decisión que tomé con Miguel y que toca U21

**La línea base no guardaba la causa raíz.** `Baseline` solo tenía `case_verdicts`
(caso → passed/failed/not_measured); la causa vive en el reporte, que está en `tmp/` y
no se versiona (BR1.1). Sin ella «Cómo falla» no podía agrupar por la taxonomía
(BR4.1). Se preguntó y Miguel eligió la opción recomendada: **`Baseline.root_causes`**,
un campo aditivo y opcional (una línea base anterior sigue validando), que
`build_baseline` llena desde el reporte y cuyo validador rechaza una causa de un caso
que la línea base no trae. Es lo único que esta tanda cambió fuera de U22 y el encargo
decía «solo se leen»: queda aquí dicho.

## Un hallazgo que conviene decidir

**`publish()` (BR2.1) se niega a publicar una línea base con algún caso en `failed`.**
Entonces una línea base publicada de verdad **nunca** trae fallos, y «Cómo falla»
dirá «No case failed» con cualquiera. Lo único que trae son casos `not_measured`, que
se listan aparte y **no se cuentan como fallo**, y de esos la línea base no guarda
causa raíz. Hoy hay 42 de 100 casos con causa `NOT_BUILT` en el reporte, y ninguno
llegaría a la sección. El generador agrupa correctamente lo que reciba (las pruebas
siembran fallos escribiendo el archivo), pero **con las reglas actuales la sección
nunca tendrá nada que agrupar**. Para Miguel: o BR2.1 admite fallos de causa conocida
en la línea base, o «Cómo falla» lee de otra fuente versionada. No lo resolví: es
decisión de alcance.

## Otras decisiones menores

1. **El párrafo inicial no enlaza el chat, la consola de voz ni el video**, porque
   ninguno está publicado; dice que sus enlaces entran al cerrar la pasada de
   publicación. AC4.1.1 pide los enlaces: queda sin cumplir hasta entonces, a
   propósito, y no se inventó ninguno (P7).
2. **El resumen en español** es una sola línea que dice que lo escribe Miguel (AC4.1.6).
3. **Las cifras de costo por caso y casos por aseguradora** salen «no medidas (no
   registradas en la línea base; el panel en vivo las muestra)»: el README se comprueba
   en GitHub Actions sin base de datos, y es la misma vista que el panel público.
4. Los textos de las causas y cifras viven en el módulo y no en el catálogo de copy:
   es documentación en inglés, no texto de producto. Una prueba exige que no falte
   ninguna causa de las tres taxonomías cerradas.

## Qué se rompió y qué se cayó

Cada rotura se aplicó, se corrió la suite de la tanda y se revirtió.

| Regla | Rotura | Prueba que se cayó |
| --- | --- | --- |
| BR4.1 | Quitar los identificadores de los grupos | `test_como_falla_agrupa_por_causa_raiz_nombra_los_casos_y_cita_el_commit` |
| BR4.1 | Quitar el commit completo | la misma |
| BR4.1 | Invertir el orden de la taxonomía | `test_los_grupos_salen_en_el_orden_de_la_taxonomia…` |
| OBS-U1.3 | Contar un caso no medido como fallo | la de BR4.1 (el grupo «sin causa» pasa a 2) |
| BR4.2 | `check` siempre verde | `test_editar_a_mano_una_seccion_falla_nombrandola` |
| BR4.2 | `check` solo mira que haya algo | la misma |
| BR4.2 | El mensaje no nombra la sección | la misma |
| BR4.2 | Las cifras ignoran la línea base | `test_una_linea_base_nueva_deja_el_readme_publicado_obsoleto` |
| BR4.2 | Quitar `readme:check` del guion | `test_el_chequeo_esta_en_el_guion_de_verificacion…` |
| BR1.2 | «0.0 %» donde no hay medición | `test_sin_linea_base_las_dos_secciones_dicen_no_medida…` |
| BR1.4 | Añadir un promedio combinado | `test_las_cifras_por_idioma_salen_lado_a_lado…` |
| FD-U22-9 | `regenerate` toca una narrativa | `test_regenerar_reemplaza_solo_entre_las_marcas…` |
| Baseline | `build_baseline` no guarda las causas | `test_la_linea_base_guarda_la_causa_raiz…` |

Dos sobrevivieron y se atendieron: quitar el commit **corto** no cae porque el sha
completo ya lo contiene (texto redundante: se dejó solo el completo en «Cómo falla»),
y cambiar `value` por `value or 0` en una celda ya medida es un mutante equivalente.

## Qué corrió y qué no

En verde aquí: `ruff format` y `ruff check`, `mypy` (641 archivos), los 36 contratos de
importación, catálogo de textos, esquemas, chequeos de contenido (el README entra en su
alcance y no da hallazgos), ciclo de vida, frases del chat y de la voz, literales de
aseguradora, regeneración de contratos y OpenAPI (sin cambios), y **`readme:gen`
seguido de `readme:check`**. 213 pruebas unitarias de `evals`, `workspace` y la ruta de
cifras; los dos módulos nuevos con 100 % y 93 % de líneas.

**No comprobado:** `scripts/verify.sh` entero, `mise run cov` y el piso del 80 %
agregado, las pruebas con base de datos, `vitest`/`tsc` (la interfaz no se tocó), el
arnés de accesibilidad y el generador del cliente de TypeScript (no cambió ninguna
ruta). `readme:check` se probó invocando su módulo, no a través de `mise run`.

## Para la sesión local

- Decidir lo de BR2.1 frente a «Cómo falla» (arriba).
- Correr `mise run cov` y `scripts/verify.sh` completos.
- El día que se publique la primera línea base, `readme:check` se pone rojo hasta que
  se corra `mise run readme:gen` y se commitee: es el comportamiento pedido.

---

## La revisión local de la tanda 3

Escrita en la sesión local el 2026-09-30, después de correr las pruebas de la unidad,
las once compuertas baratas, `readme:gen` y `readme:check` **a través de `mise`** (la
nube solo pudo llamar al módulo), y de romper cuatro reglas más que las trece de
arriba.

### Lo que la tanda hizo bien, y conviene no perder

- **La agrupación es dato y no prosa.** `NOT_MEASURED_TEXT`, `ROOT_CAUSE_TEXT` y
  `FIGURE_TEXT` son tablas de las tres taxonomías cerradas, y una prueba exige que no
  falte ninguna clave. El día que alguien añada un valor a un `StrEnum`, se cae esa
  prueba y no la compuerta con un `KeyError`.
- **Un solo lector de la línea base.** Las cifras del README salen de
  `build_snapshot`, el mismo camino que el panel. Dos lectores serían dos esquemas.
- **El módulo es puro y el archivo lo toca otro.** `readme.py` recibe texto y
  devuelve texto o problemas; `workspace/readme_check.py` es el único que lee y
  escribe. Por eso las dieciséis pruebas del generador corren en 50 ms y sin archivo.
- **La regeneración solo toca lo que hay entre las marcas**, y hay una prueba que
  cambia una sección narrativa y exige que el chequeo siga en verde.

### Lo que se corrigió aquí

1. **Dos aserciones que no podían distinguir** (forma 2 del catálogo). Quitar la línea
   de procedencia por cifra —fecha, commit y corrida, que es BR1.3— **no caía ninguna
   prueba**, porque la aserción buscaba `commit \`0123456\`` y el encabezado de la
   sección ya lo contiene. Y dibujar toda celda no medida como un guion, en vez de su
   causa, tampoco caía nada del generador: lo único que se caía era la comparación
   contra el README del repositorio, que vuelve al verde en cuanto alguien corre
   `readme:gen`. Las dos aserciones ahora nombran la línea exacta, y las dos roturas
   vuelven a caerse.
2. **Una prueba que exigía más que la regla.** La estructura del README se comprobaba
   con `len(encabezados) == 8`. FD-U22-9 dice que el chequeo mira solo las dos
   generadas, y las seis narrativas las escribe Miguel en la semana 11: el día que
   añada una sección suya, trabajo legítimo, esa prueba se pone roja. Ahora comprueba
   que las ocho piezas de AC4.1.2 están **y en orden**, admitiendo secciones entre
   ellas, y sigue cayéndose si falta una.
3. **La distinción que muere en la pantalla** (forma 12, nueva). `LatencyMeasure` lleva
   su causa por canal a propósito, y el panel público no la dibujaba: mostraba la de la
   cifra, «por hito», para las dos latencias. Eso manda a esperar un hito donde lo que
   hay que hacer es construir los dos eventos del chat. El panel ahora la dibuja, con
   los textos del catálogo que ya existían, y la prueba exige que la del chat **no**
   sea la de la voz. Es un defecto de la tanda 1 que la tanda 3 destapó por hacerlo
   bien en el README.
4. **El párrafo inicial sin sus tres enlaces** quedó registrado como criterio diferido
   en `inception/delivery-planning/pasada-de-publicacion.md`, con AC4.1.1 nombrado. Sin
   esa fila era un criterio aprobado sin cumplir y sin rastro, que es distinto de uno
   diferido a propósito.

### Las cuatro roturas propias

| Regla | Rotura | Qué se cayó |
| --- | --- | --- |
| BR1.3 | Quitar la procedencia de cada cifra | **nada** → aserción corregida |
| BR1.2 | Toda celda no medida como un guion | solo la comparación con el README → aserción corregida |
| BR4.2 | Quitar el aviso de «no editar a mano» del bloque | la comparación con el README del repositorio |
| OBS-U1.3 | Contar los no medidos entre los fallos | dos pruebas del generador |

### El incidente que salió de esta revisión

La tubería de la tanda 2 (`918855b`) estaba en rojo cuando empezó esta revisión, y la
causa era **de la revisión de la tanda 2, no de la nube**: al añadir `top_cases` a
`SpendPanel` y a la pantalla no se actualizó la respuesta declarada del arnés, que era
el único sitio que la alimenta con un cuerpo fijo y estaba tipada como `unknown`. Siete
fallos, el mismo `undefined.length`. Arreglado en `1af6260`, solo y sin nada apilado
encima, y el cuerpo ahora lleva el tipo del contrato para que el próximo campo rompa
`tsc` en vez del arnés. Es la forma 13 del catálogo de revisión.

### Lo que sigue abierto

**De dónde sale «Cómo falla»** (lo que la nube dejó para decidir, y es decisión de
diseño porque cambia lo que lee quien evalúa el proyecto). El hallazgo se confirmó y es
más fuerte de lo que decía: no solo la sección dirá siempre «No case failed», sino que
`Baseline.root_causes` —el campo que la tanda añadió a U21 para agruparla— **no puede
llenarse por ninguna ruta de producción**, porque `publish()` rechaza toda línea base
con un caso en `failed` y la causa raíz solo se pone en casos fallidos. Es la forma 11
del catálogo. La causa está identificada: AC4.1.3 dice «el último reporte de
evaluación» y BR4.1 lo cambió por «la línea base vigente» sin notar que eso lo vaciaba.
Va a Miguel con sus tres opciones y su recomendación.
