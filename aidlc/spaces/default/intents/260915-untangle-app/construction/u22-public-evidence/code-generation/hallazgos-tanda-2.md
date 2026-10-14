# Hallazgos — U22 `public-evidence`, tanda 2 (el panel de gasto)

Escrito en la sesión de la nube. **Corrección al encargo: aquí sí se pudo correr
la base.** El contenedor trae un PostgreSQL 16 de sistema (sin Docker y sin
pgvector), así que las pruebas de integración de esta tanda **se ejecutaron**, contra
un servidor local y no contra la imagen anclada. Ver «Qué no se comprobó».

## Qué se construyó

- `server/spend_routes.py`: `GET /api/spend` (ventana, proveedores, meses) y
  `GET /api/spend/cases/{case_ref}`, detrás de la cookie `untangle_operator`. Las
  cuatro consultas de `telemetry/spend/repository.py` se usan tal cual; el estado del
  techo lo calcula `budget.state`, la misma función que consulta el corte (BR3.3).
- `Settings.operator_key` (`UNTANGLE_OPERATOR_KEY`, mínimo 32 caracteres, vacía =
  ausente) y `.env.example`.
- `ModuleSpec.requires_setting` en la raíz de composición: **sin la clave, el módulo
  no se monta** (ni ruta ni sonda), y la omisión queda en el rastro
  (`server.module_not_mounted`, sin valores).
- `problems.unknown_route_error()`: una sola construcción del error de ruta
  inexistente, usada por la rama `/api/...` de `web.py` y por el rechazo del panel.
- `openapi_export` construye la app con una clave-marca para que el esquema describa
  el panel aunque quien regenere no tenga clave.
- Interfaz: `/spend` (`pages/spend/`), `api-client/spend.ts`, claves `spend_panel.*`
  en es/en, contratos regenerados, entrada `spend` (audiencia `staff`, con respuesta
  simulada) en el arnés de accesibilidad.
- `test:u22` incluye las pruebas nuevas.

## Decisiones que tomé y que conviene que revises

1. **SEC-U22.3 cambió de significado.** Decía «cada quien ve el gasto de la suya».
   Con FD-U22-8 y un registro sin política de fila (BR7.1 de U5: `spend_entry` es dato
   del proyecto, `tenant_ref` es solo atribución) no hay «la suya» que filtrar. Lo
   probado es lo que sí se sostiene: ninguna credencial de aseguradora abre el panel, y
   la respuesta no trae ni casos ni aseguradoras que solo estén en el registro.
   Conviene enmendar el texto de SEC-U22.3 en `security-requirements.md`.
2. **«Por caso» es una búsqueda, no una lista.** `spend_by_case` responde por un
   `case_ref`; una lista exigiría una quinta consulta (y un panel que lista
   identificadores es justo el riesgo de SEC-U22.1). Si quieres lista, es decisión tuya.
3. **Transporte de la clave: cookie `untangle_operator`**, como la credencial de la
   bandeja (no hay pantalla de entrada: se pega en el navegador). Una cabecera o un
   parámetro no abren (probado).
4. **Un identificador de caso mal formado** devuelve `400` solo *con* clave; sin ella
   responde como ruta inexistente (validar antes filtraría que la ruta existe).
5. **`hide_input_in_errors=True` en `Settings`**: encontrado al probar que una clave
   corta no se repite en el error de arranque. Por defecto pydantic imprime
   `input_value=…`. Afecta a todos los campos (es lo más seguro).
6. **La entrada `spend_panel` de `NAV_LINKS` (U6) queda inerte**: la barra solo dibuja
   superficies públicas y esta no lo es. No lo toqué.
7. Sin base, el panel responde `500` genérico (no hay causa `unavailable` propia).

## Qué se rompió y qué se cayó

Cada rotura se aplicó, se corrió `tests/integration/u22` + `tests/unit/web/test_spend_routes.py`
(o `vitest src/pages/spend`) y se revirtió. Todas tumbaron conducta.

| Regla | Rotura | Prueba que se cayó |
| --- | --- | --- |
| SEC-U22.2 | Rechazo con título distinto al de ruta inexistente | `test_todas_las_causas_de_rechazo_responden_igual…` |
| SEC-U22.2 | Clave equivocada pasa | la misma |
| SEC-U22.2 | Clave ausente pasa | la misma |
| SEC-U22.2 | Despliegue sin clave pasa | `test_la_ruta_usa_la_clave_que_resolvio_la_raiz…` |
| BR3.1 | Se monta sin clave | `test_un_despliegue_sin_clave_responde_igual…` |
| BR3.1 | El módulo pierde `requires_setting` | la misma |
| BR3.1 | Superficie pública | `test_con_clave_la_superficie_esta_montada_y_no_es_publica` |
| BR3.5 de U5 | Conteo sin medir a 0 en proveedores | `test_las_cuatro_vistas_salen_del_registro…` |
| BR3.3 | Estado forzado a `ok` | `test_las_cuatro_vistas…` |
| BR3.3 | El panel compara contra el techo | `test_el_panel_no_nombra_ninguna_de_las_piezas_que_deciden_el_corte` |
| D11 | Acumulado = último mes | `test_las_cuatro_vistas…` |
| BR3.2 | Ventana siempre nula | `test_las_cuatro_vistas…` |
| Alerta | `alert_sent_at` siempre nulo | `test_la_alerta_dice_si_ya_se_emitio_y_cuando` |
| Privacidad | Sin `no-store` | `test_ninguna_respuesta_del_panel_se_guarda…` |
| Entrada | Forma del caso sin validar | `test_una_ruta_de_caso_mal_formada…` |
| Arranque | Clave mínima = 1 | `test_una_clave_corta_impide_arrancar…` |
| Arranque | El error repite la clave | la misma |
| PERF-U22.2 | `sleep(0,6)` en el armado | `test_armar_las_cuatro_vistas_cabe_en_el_presupuesto_p95` |
| Pantalla, BR3.5 de U5 | No dibuja «sin medir» | 2 pruebas de `spend.test.tsx` |
| Pantalla BR1.2 | Restante sin medir como 0 | `un restante que no se pudo calcular…` (es, en) |
| Pantalla BR3.3 | Estado deducido en el navegador | 2 pruebas (es, en) |
| Pantalla | Alerta inferida del acumulado | `la alerta dice si ya se emitio…` |
| Pantalla | Sin ventana dibuja cero | `sin ventana, lo dice…` |
| Pantalla | Sin `trim` / busca sin escribir | 1 prueba cada una |

**Dos veces la prueba estaba mal, o el código:**
1. El rechazo con `HTTPException(404)` **no era idéntico** a una ruta inexistente
   (`title` distinto): defecto de código, lo destapó la prueba de integración. Arreglado
   con `unknown_route_error()`.
2. `ValidationError` de pydantic repetía la clave corta (ver decisión 5). Arreglado.
3. Mi prueba de «sin despliegue» nunca ejercía `key_not_configured` (con `build_app`
   sin clave el módulo ni se monta); se reescribió para montar y luego desenchufar.
4. Una aserción `… or True` (vacua) se borró antes de terminar.

Una rotura que probé (`spend.consume_quota` en el panel) cayó por `AttributeError`
(ese símbolo no está en `api`), no por conducta: no cuenta; la cubre la de `cap_usd`.

## Qué corrió y qué no

En verde aquí: `ruff format/check`, `mypy`, los 36 contratos de importación, catálogo de
textos, esquemas, chequeos de contenido, `env_check`, literales de aseguradora, deriva
de contratos (regenerar no cambia nada), `tsc`, `prettier`, `eslint` (0 errores),
`vitest` (335 = 315 + 20 nuevas), 21 pruebas de integración nuevas y 25 unitarias.
También u5, u6, u14 y `u16/test_import_contracts` contra la base local (los 45 fallos de
u13/u14 son `ModelsMissingError` de spaCy, ajenos).

**No comprobado:**
- La base fue PostgreSQL 16 de sistema **con un `DOMAIN vector` de mentira** para que
  suba la migración de U8, no la imagen `pgvector` anclada. Las tablas del gasto no usan
  `vector`, pero conviene repetir `tests/integration/u22` con `mise run test:u22`.
- `mise run cov` y el piso del 80 % (módulo nuevo, bien cubierto, pero no medido), `scripts/verify.sh`,
  `mise run a11y` (la ruta `/spend` entra con respuesta simulada; no se ejecutó el arnés),
  y `test:u22` completo (falta `mise`).
- Suite unitaria completa: 91 fallos y 234 errores **idénticos con y sin la tanda**
  (spaCy, voz, etc.); solo suben los 25 pasados.
- Nada contra un navegador real ni contra el despliegue vivo.

## Para la sesión local

- `.importlinter` no se tocó (`spend_routes` no añade aristas a `evals`).
- Enmendar SEC-U22.3 y decidir lista-vs-búsqueda por caso.
- Añadir `UNTANGLE_OPERATOR_KEY` al entorno local y a la pasada de publicación (no
  publicar `/spend` sin ella; la superficie ya no se monta sin clave).

---

# Revisión local de la tanda 2 (2026-09-30)

Escrita en la nube, revisada aquí. **Lo que vino es notablemente mejor que la tanda
1**: sus dos defectos los encontró ella misma con sus pruebas, y las 26 roturas
tumbaron conducta. Lo que la revisión cambió fue una cosa, y es de alcance, no de
corrección.

Verificado aquí, con base de datos de verdad y la imagen anclada: 2.124 pruebas
unitarias, 684 de integración, 337 del navegador y las ocho compuertas baratas.

## 1. «Por caso» era una búsqueda, y el criterio pide una lista

La tanda entregó `GET /api/spend/cases/{caso}`: responde por un identificador. Eso
cumple la letra de AC5.14.1 —"veo el costo por caso"— y no su propósito, que la
propia historia escribe: *"para no gastar un dólar que no decidí gastar"*. **Quien
mira el gasto para no gastar de más es justo quien no sabe qué identificador
preguntar.**

Se añadió la quinta consulta, `top_cases_by_spend`: los casos que más costaron, de
mayor a menor, con desempate por identificador para que dos corridas sobre los
mismos datos devuelvan el mismo orden. Los casos sin nada medido entran igual, con
su conteo de no medidos: **un caso que solo tiene llamadas sin medir no cuesta
cero, cuesta "no se sabe"**.

Y el orden lo pone la consulta, no la pantalla ni la ruta. Una rotura lo comprueba:
reordenar en el panel tumba dos pruebas.

## 2. Una prueba protegía una frontera que no existe

La tanda escribió `test_el_panel_no_devuelve_casos_ni_aseguradoras...`, con un
razonamiento cuidadoso: como SEC-U22.3 no se puede cumplir tal como estaba escrita,
lo que hay que sostener es que el panel no exponga los casos que causaron el gasto.

**La segunda mitad de esa conclusión no protege nada.** No existe nadie que tenga
la clave de operador y no deba ver un identificador de caso: con esa clave ya puede
consultar cualquiera que conozca, y con la credencial de la bandeja ve los casos
enteros. La prueba se quedó con la mitad que sí importa —que el panel no invente un
reparto por aseguradora, y que ninguna clave se repita en la respuesta— y ganó una
hermana para la lista.

Es la forma de defecto contraria a la habitual: una prueba que exige **más** de lo
que la regla pide, y que habría bloqueado el criterio.

## 3. SEC-U22.3 decía algo que no se puede cumplir

Lo detectó la tanda y tenía razón: el registro de gasto es dato del proyecto y no
lleva política de fila por aseguradora, así que "cada quien ve el gasto de la suya"
no existe. El texto del requisito quedó enmendado con las dos cosas que sí son
comprobables, y con lo que **no** exige, para que nadie vuelva a deducir de ahí que
la lista de casos está prohibida.

## 4. Lo que la tanda hizo bien y conviene no perder

- **La condición de montaje es un dato del módulo, no un `if` en el arranque.**
  `requires_setting="operator_key"` va en la lista de módulos, así que se ve donde
  se ve todo lo demás. Romperlo tumba dos pruebas, una de ellas estructural.
- **El rechazo es el mismo objeto**, no dos literales que alguien mantenga iguales:
  `unknown_route_error()` lo construyen la rama de ruta desconocida y el panel. Que
  el panel responda distinto —403, o 404 con su propio título— tumba entre cuatro y
  seis pruebas.
- **Los dos defectos que encontró sola**: el título del error no era idéntico al de
  una ruta inexistente, y una clave demasiado corta se repetía en el error de
  arranque de pydantic. El segundo es exactamente el tipo de fuga que el proyecto
  persigue: el secreto en el registro del despliegue.

## 5. Lo que se rompió aquí, y qué se cayó

Cinco roturas propias, además de las 26 de la tanda.

| Regla | Qué se rompió | Qué se cayó |
| --- | --- | --- |
| BR3.1 | El panel se monta sin clave de operador | 2, una estructural |
| SEC-U22.2 | El panel responde 403 en vez del rechazo compartido | 6 |
| SEC-U22.2 | El panel responde 404 con su propio título | 4 |
| AC5.14.1 | La lista deja de ordenar por lo que costó | 1 |
| BR3.5 de U5 | La lista pierde el conteo de lo no medido | 1 |
| AC5.14.1 | El panel reordena la lista por su cuenta | 2 |

**Una rotura mía no tumbó nada, y estaba bien así:** cambiar el título dentro de
`unknown_route_error()` no rompe la regla, porque cambia las dos respuestas a la
vez y siguen siendo idénticas. La violación de verdad es que el panel responda algo
distinto del rechazo compartido, y esa sí cae.

## 6. Lo que queda apuntado

- **Sin pantalla de entrada para la clave**: se pega como cookie. Es lo mismo que
  hace la bandeja —tampoco tiene pantalla de entrada— así que queda consistente con
  lo que existe, no como deuda propia de esta unidad.
- **La base de la nube no era la imagen anclada**: allá se usó un PostgreSQL del
  sistema con un `vector` de mentira para que subiera la migración de U8. Se repitió
  aquí con la imagen anclada y las 22 pruebas de integración pasan. Nada de eso
  quedó en el repositorio.
