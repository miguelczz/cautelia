# Hallazgos — U22 `public-evidence`, tanda 1

Lo que se construyó, lo que se rompió a propósito para comprobar las pruebas, y lo
que la sesión local tiene que decidir o revisar. Escrito en la sesión de la nube
(sin `mise`, sin base de datos, sin navegadores).

## Qué se construyó

- `evals/evidence/models.py`: `MetricsSnapshot`, `Figure`, `Measurement`,
  `FigureSource`, `LatencyMeasure`. Los invariantes están en el tipo: una celda sin
  medir **no se puede construir** sin causa ni con valor (BR1.2), una cifra medida
  exige fecha, commit y corrida (BR1.3), y el panel lleva exactamente las cinco.
- `evals/evidence/snapshot.py`: `build_snapshot` (pura) y `current_snapshot` (lee
  `current.json`). Sin línea base, las cinco salen `not_measured`; con ella se
  llenan completitud y precisión de citación, y las otras tres siguen sin medir.
- `evals/evidence/api.py`: superficie del módulo, sin lógica.
- `server/evidence_routes.py`: `GET /api/metrics`, sin credencial, y la superficie
  `metrics_panel` (pública, única, con sonda). Montada en `MODULOS`.
- Interfaz: `/metrics` (`pages/evidence/`), tabla español/inglés lado a lado,
  "No medida" con su causa, y fecha, commit y corrida por cifra. Claves `metrics.*`
  en `es.yaml` y `en.yaml`; contratos regenerados.
- `app/contracts/examples/metrics-snapshot.json`: la respuesta real sin línea base,
  que escribe `contracts:gen` y usan las pruebas de la pantalla.
- Tarea `test:u22` en `mise.toml`.

## Qué se rompió y qué se cayó

Cada mutación se aplicó, se corrió la suite de la tanda y se revirtió. Ninguna cayó
por `ImportError` o error de sintaxis.

| Regla | Rotura | Prueba que se cayó |
| --- | --- | --- |
| BR1.1 | Ignorar la línea base (`build_snapshot(None)`) | `test_las_cifras_salen_del_archivo_versionado_y_no_del_ultimo_reporte` |
| BR1.1 | La ruta devuelve el panel vacío | `test_con_linea_base_sembrada_se_llenan_dos_…` (ruta) |
| BR1.2 | Quitar el validador de la celda | `test_una_celda_no_puede_afirmar_ni_un_cero_ni_un_hueco[sin-causa]` |
| BR1.2 | Una celda ausente sale como `0.0` | `test_un_idioma_medido_y_el_otro_no_deja_cada_celda_en_su_estado` |
| BR1.2 (UI) | La celda sin medir dibuja "0 %" | `sin linea base, las cinco salen no medidas…` (es y en) |
| BR1.2 (UI) | Quitar la causa | la misma prueba |
| BR1.3 | La cifra medida pierde su origen | `test_con_linea_base_se_llenan_las_dos_…` |
| BR1.3 | El tipo deja de exigir el origen | `test_una_cifra_medida_exige_su_origen` |
| BR1.3 (UI) | Quitar fecha, commit y corrida | `cada cifra medida lleva fecha, commit corto y corrida…` |
| BR1.4 | Añadir una entrada "combined" | `test_con_linea_base_se_llenan_las_dos_…` |
| BR1.4 (UI) | Dibujar un 85 % en la celda del inglés | `los dos idiomas van lado a lado…` (es y en) |
| BR1.5 | Cambiar un extremo de la latencia | `test_las_latencias_dicen_entre_que_eventos_…` |
| BR2.1 / SEC-U22.1 | Añadir los `case_verdicts` a la respuesta (tipo) | `test_la_respuesta_no_trae_ningun_identificador_de_caso_sembrado` |
| BR2.1 / SEC-U22.1 | Lo mismo, poblado desde la línea base | `test_con_linea_base_se_llenan_las_dos_…` |
| Criterios | Intercambiar `field_extraction` y `citation_precision` | `test_con_linea_base_se_llenan_las_dos_…` |
| Idiomas | Intercambiar es y en | la misma |
| PERF-U22.1 | `sleep(0.25)` en el armado | `test_armar_las_cinco_cifras_cabe_en_el_presupuesto` |
| C-24 | Quitar el módulo de `MODULOS` | `test_la_raiz_de_composicion_monta_el_panel_por_defecto…` |
| Contrato | Quitar la arista de `.importlinter` | `produccion-sin-evals` BROKEN |
| Catálogo | Quitar una clave del inglés | `copy_catalog.checks` |
| Rutas | Quitar `/metrics` del enrutador | `visitable-routes.test.ts` (dos pruebas) |

**Dos veces la mutación no rompía nada, y era la prueba la que estaba mal:**

1. La primera versión de la prueba de las dos cifras llenas tomaba la clave de la
   constante del módulo y comparaba contra la misma fábrica de pruebas; intercambiar
   los criterios la habría dejado en verde. Se reescribió con claves a mano y
   valores distintos por criterio e idioma.
2. La prueba de que el módulo se monta armaba la aplicación con su propia lista de
   módulos, no con `MODULOS`: quitarlo de la raíz no la tocaba. Ahora usa la lista
   de verdad.

La prueba de SEC-U22.1 lleva además **control positivo**: exige que la respuesta
sí leyó la línea base sembrada (`baseline_id == "base-0001"`) antes de afirmar la
ausencia de identificadores; sin él, una ruta que no entregara nada la pasaría.

## Lo que la sesión local tiene que decidir o revisar

1. **Enmienda de `.importlinter` (contrato `produccion-sin-evals`).** La ruta tiene
   que vivir en `untangle.server` (`untangle.evals` no puede importar FastAPI) y
   leer la línea base, que es del corredor. Se añadió una segunda arista al
   `ignore_imports`: `untangle.server.evidence_routes -> untangle.evals.evidence.**`,
   razonada en el archivo con el mismo argumento que `voice_cli`. Es una
   modificación de una compuerta de arquitectura: conviene que la mires.
2. **Nombres de criterio supuestos.** Completitud sale de `field_extraction` y
   precisión de citación de `citation_precision` (los nombres que ya usan las
   pruebas de `gates`). No existe todavía ningún caso de DS-2 ni de DS-3 que
   declare esos criterios en `expected_verdicts`; cuando U21 publique la primera
   línea base hay que confirmar que los trae con esa grafía, o las dos cifras
   seguirán en `criterion_absent`. Las constantes están en `snapshot.py`.
3. **Eventos de latencia del chat.** La voz tiene `voice.speech_end` y
   `voice.first_audio` (`voice/latency.py`); el chat **no emite** ningún evento
   de "envío" ni "primera palabra". El panel los nombra como extremos porque
   AC4.16.3 lo pide, pero la cifra es "no medida" y nada la produce hoy. Los
   conjuntos (DS-5 para voz, DS-2 para chat) son una lectura mía del PRD 11.2.
4. **El enlace a la corrida.** `run_url` viaja como `null`: `Baseline` solo trae
   `run_id`, y el repositorio es privado hasta la pasada de publicación. La
   pantalla muestra el identificador como texto y, si algún día hay enlace, como
   enlace. AC4.16.2 pide el enlace: queda abierto hasta que exista a dónde llevar.
5. **La superficie `metrics_panel` ya está montada.** Por eso el inicio local
   muestra el enlace "Resultados medidos" y `site-directory.json` cambió. No
   publica nada (FD-U22-7), pero la barra ya apunta a `/metrics`. La superficie
   de gasto sigue sin montarse (tanda 2).
6. **Semántica de `Figure.state`.** Es `measured` solo si **todas** sus celdas lo
   están. Si la línea base trae un criterio en un solo idioma, la cifra queda
   `not_measured` (`criterion_absent`), la celda medida conserva su valor y no se
   cita corrida. Es una lectura de `entities.md` (que solo conoce dos estados);
   si prefieres un tercer estado "parcial", es un cambio pequeño.

## Qué no se corrió (no corre en este entorno)

`tests/integration`, `mise run cov` (y por tanto el piso del 80 %), `scripts/verify.sh`,
el arnes de accesibilidad (`mise run a11y`, que ahora recorre `/metrics`) y las
pruebas con base de datos. `mise` tampoco estaba: se corrieron los comandos
equivalentes de `docs/reference/sesiones-en-la-nube.md`.

Corrieron y pasan: formato, lint (con reglas de seguridad), los 36 contratos de
importación, mypy, el catálogo de textos, las aserciones de esquema, los chequeos de
contenido, la deriva de los contratos generados (regenerar no cambia nada), `tsc`,
`prettier`, `eslint` (0 errores; las 17 advertencias son previas), las 315 pruebas de
`vitest` y las de `tests/unit/{web,evals,copy_catalog,server}` (287) más las 18 nuevas
de las cifras.

**Falla previa, no de esta tanda:** la suite unitaria completa tiene 59 fallos y 3
errores en este entorno (faltan los modelos de spaCy que instala `models:install`, y
otros). Son idénticos con y sin los cambios de esta tanda (`git stash -u`).

## Para la tanda 2

- `cost_per_case` y `cases_by_tenant` salen `not_connected`. Cuando se conecten, la
  prueba de SEC-U22.1 tiene que sembrar **casos reales en la base** con
  identificadores reconocibles y mirar la respuesta del servidor; la de esta tanda
  solo puede sembrar identificadores en la línea base.
- `test_el_tipo_de_la_respuesta_no_puede_cargar_un_caso` impide que
  `MetricsSnapshot` admita campos como `case_id` o `case_number`; el recuento por
  aseguradora tendrá que ser un mapa aseguradora → entero.

---

# Revisión local de la tanda 1 (2026-09-30)

La tanda se escribió en una sesión de la nube y se revisó aquí antes de llevarla a
`main`. Lo de arriba es su propio informe; esto es lo que la revisión encontró y
cambió. **Cinco cosas, y dos de ellas eran defectos de verdad.**

Verificado aquí, que es lo que allá no se podía correr: 2.099 pruebas unitarias,
663 de integración, 315 del navegador, y las diez compuertas baratas.

## 1. Dos nombres de criterio inventados, y el fallo era silencioso

El módulo apuntaba las dos cifras medibles a `field_extraction` y
`citation_precision`. **Ninguno de los dos existe.** Se comprobó sobre
`app/evals/cases/`: los criterios reales son otros treinta, y los casos de citación
(DS-3) declaran `expected_verdicts: {}` a propósito, porque el verificador de citas
todavía no tiene conductor de evaluaciones.

La consecuencia no se veía: las dos cifras quedaban "no medidas" **con la causa
equivocada** —"la línea base no trae el criterio"—, que se lee como un problema de
la línea base y manda a arreglar el sitio equivocado. Y sus pruebas pasaban porque
sembraban una línea base con esos mismos nombres inventados: la prueba y el código
compartían el error.

El informe de la nube lo marcó como cosa a confirmar, que está bien. Lo que no
estaba bien es que el código afirmara mientras tanto.

**Arreglo.** El mapa de cifra a criterio es dato, en un solo sitio, y hoy los dos
son **nulos**, con una causa nueva que dice la verdad: `criterion_not_built`, "no
existe todavía un criterio que mida esto". Un nulo dice la verdad y obliga a volver
aquí; un nombre supuesto no. El camino "medida" sigue probado porque el mapa entra
por argumento en las pruebas, que es donde los nombres inventados sí valen.

## 2. Dos pruebas de U16 rotas, que allá no se podían correr

`test_el_proceso_servido_sigue_sin_poder_ver_el_corredor` y
`test_el_comando_a_mano_puede_llegar_al_conductor_de_voz`. Las dos plantan un árbol
de mentira y corren el contrato **real** contra él; la arista nueva nombra un
módulo que ese árbol no tenía, y el contrato declara que una exclusión sin
coincidencia es un error, así que fallaban por el andamiaje.

**Arreglo.** El árbol gana los tres archivos, igual que ya tenía los de `voice_cli`.
Se resistió la salida fácil —poner `unmatched_ignore_imports_alerting = none`—
porque eso silenciaría también una exclusión que un día quede obsoleta de verdad.

Esto es el costo medido del entorno de la nube: allá no corren las pruebas de
integración, y la tanda volvió con dos rojas sin que nadie pudiera verlas.

## 3. El comentario del contrato decía algo que dejó de ser cierto

El párrafo que cierra el contrato `produccion-sin-evals` decía que el proceso
servido sigue sin ver el corredor "ni directo ni por cadena", y que lo que se
permite es "un comando a mano que no corre en ninguna compuerta". Eso era verdad
con **una** arista. Con la segunda ya no: `composition` monta la ruta del panel, y
por esa cadena el proceso servido importa hoy **diez módulos** de `untangle.evals`.
Medido, no supuesto.

**Arreglo.** El comentario dice ahora las dos aristas por separado, cuáles son los
diez módulos, y qué sigue protegido —el corredor, los conductores, el juez y la
lógica de la compuerta—. Y deja escrita la medida con la que se juzga una tercera:
*¿mete en el proceso servido algo que decida, corra o puntúe una evaluación?*

La arista en sí se acepta: el catálogo de unidades pone este código bajo
`evals/evidence/` y la ruta tiene que vivir en `server`, así que la obligan dos
documentos aprobados. Inventar un segundo modelo de la línea base para esquivarla
dejaría dos esquemas que un día divergen, que es peor.

Se añadió una prueba con sus dos mitades: el panel **sí** llega a la evidencia, y
**no** llega al corredor. La segunda es la que se pierde en silencio.

## 4. Las dos latencias no estaban sin medir por lo mismo

Las dos salían con la causa "se mide por hito". Para la voz es cierto: se mide
contra Deepgram y Cartesia de verdad, y eso gasta del tope. Para el chat no: sus
dos eventos —envío y primera palabra— **no existen todavía**, así que decir "por
hito" manda a esperar un hito en vez de a construirlos.

**Arreglo.** Cada latencia lleva su propia causa, y hay una causa nueva,
`source_not_built`. Seis causas en total, y cada una manda a un sitio distinto:
publicar una línea base, mirar la línea base, cablear el criterio, esperar el hito,
conectar el panel, o construir la fuente. Una distinción que no cambia lo que hay
que hacer no vale su nombre; estas seis sí.

## 5. Lo que se rompió aquí, y qué se cayó

Cinco roturas propias, además de las veinticuatro que hizo la nube. Todas tumbaron
conducta.

| Regla | Qué se rompió | Qué se cayó |
| --- | --- | --- |
| BR1.2 | Una celda no medida puede llevar un cero | 3, las tres formas del caso |
| BR1.3 | Una cifra medida no necesita fecha ni commit | `test_una_cifra_medida_exige_su_origen` |
| AC4.16.1 | El panel puede traer menos de las cinco | `test_el_panel_lleva_exactamente_las_cinco_cifras` |
| Causa correcta | El criterio no construido se confunde con la línea base ausente | 5 |
| SEC-U22.1 | La ruta copia los veredictos por caso | 6 |

**Lo mejor de esta tanda, y conviene decirlo:** los invariantes están en el tipo y
no en quien lo construye. Una celda no medida **no se puede construir** con un cero
ni sin causa. Eso convierte la regla `[bloquea]` de un acuerdo en algo imposible de
escribir, que es exactamente lo que el proyecto pide de sus compuertas duras.

## 6. Lo que queda apuntado, no arreglado

- **El enlace a la corrida** viaja en nulo: el repositorio es privado y no hay
  adónde llevar. Es media AC4.16.2 y queda en `pasada-de-publicacion.md`, con su
  fecha: la semana 12, cuando se decida publicar el repositorio.
- **La latencia del chat** necesita que el chat emita sus dos eventos. También
  queda en la pasada, porque construirlos no es de esta unidad.
- **Las dos cifras de la base** —costo por caso y casos por aseguradora— son la
  tanda 2, y su prueba de SEC-U22.1 tendrá que sembrar casos en la base de verdad:
  esta solo puede sembrarlos en la línea base.
