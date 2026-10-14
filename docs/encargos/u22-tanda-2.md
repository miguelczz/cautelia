# Encargo para una sesión en la nube — U22 `public-evidence`, tanda 2

Pega este archivo entero como primer mensaje de una **sesión nueva**. No se
comparte la memoria de la sesión local: todo lo decidido está en el repositorio y
este encargo dice dónde.

---

## Antes de nada

```bash
uv tool install --force uv==0.12.16
mise run deps:install
```

Si `mise` no está disponible, los comandos equivalentes a mano están en
`docs/reference/sesiones-en-la-nube.md`.

## Qué se construye

La segunda tanda de U22: **el panel de gasto**. Cuatro vistas sobre consultas que
ya existen, detrás de su propia clave, con su pantalla.

Lee estos, en este orden, y no escribas nada antes de haberlos leído:

1. `aidlc/spaces/default/intents/260915-untangle-app/construction/u22-public-evidence/functional-design/functional-spec.md` — el flujo 2
2. `.../functional-design/rules.md` — BR3.1, BR3.2 y BR3.3
3. `.../nfr-requirements/security-requirements.md` — SEC-U22.2 y SEC-U22.3
4. `.../code-generation/code-generation-plan.md` — la tanda 2 es la tuya
5. `.../code-generation/hallazgos-tanda-1.md` — lo que la revisión local corrigió de la tanda 1, para no repetirlo

Y estos del código, que es de lo que se lee:

- `app/backend/src/untangle/telemetry/spend/repository.py` — las cuatro consultas: `spend_by_case`, `spend_by_provider`, `spend_by_month`, `load_window`. **Ya existen: no se reescriben.**
- `app/backend/src/untangle/telemetry/spend/models.py` — `SpendTotal` y `BudgetWindow`
- `app/backend/src/untangle/server/evidence_routes.py` — la ruta hermana, de la tanda 1
- `app/backend/src/untangle/inbox/api.py` — cómo se rechaza una credencial: `_rechazo()`, `install_keys()`, y por qué un despliegue sin clave responde igual que una credencial ilegible
- `app/frontend/src/pages/evidence/` — la pantalla hermana, para el estilo

## La decisión que ya está tomada, y que no hay que reabrir

**El panel lleva su propia clave de operador, no la credencial de la bandeja**
(FD-U22-8). El gasto es del proyecto entero; los dos roles que existen
—`adjuster` y `account_agent`— son **de una aseguradora**, y darle a uno de ellos
el gasto del proyecto dejaría que la credencial de una aseguradora alcance datos
de las otras.

Concretamente:

- Una variable de entorno declara la clave del operador, al lado de las que ya
  instala `install_keys` en la bandeja.
- **Sin esa variable, la superficie no se monta.** Una superficie que existe sin
  poder autenticar a nadie invita a probar.
- Con ella, la ruta exige la clave y **responde igual ante una clave ausente, una
  equivocada y un despliegue sin clave**: una respuesta distinta por causa le dice
  a quien prueba cuál de sus intentos se acercó.
- `SurfaceId.SPEND_PANEL` ya existe en la lista cerrada: `public=False`,
  `per_tenant=False`.

## Las cuatro vistas

| Vista | De dónde |
| --- | --- |
| Por caso | `spend_by_case` |
| Por proveedor | `spend_by_provider` |
| Por mes | `spend_by_month` |
| Acumulado de la ventana | `load_window`, con su techo y su alerta |

`SpendTotal` lleva dentro `unmeasured_count`. **No se descarta**: publicar un total
sin decir cuánto no se midió exige desarmar el tipo a propósito, y el tipo está
hecho así para que no se pueda por descuido.

La ventana es **acumulada de 90 días desde el 2026-09-16**, nunca mensual, y su
mensaje no menciona el mes.

## Las tres cosas que no se pueden hacer mal

1. **Sin clave, todo responde lo mismo** (SEC-U22.2, `[bloquea]`). Ausente,
   equivocada y despliegue sin clave: la misma respuesta, el mismo código.
2. **El panel no decide cortar** (BR3.3). La alerta de los 3 USD y el corte de los
   5 los construyeron U15 y U16, con sus pruebas. Aquí solo se muestra lo que ya
   está decidido. Un segundo sitio que decida cuándo cortar es un segundo umbral
   que un día discrepa del primero.
3. **Ninguna cadena visible escrita en línea.** Todo texto sale del catálogo por
   idioma, con su clave. Hay un chequeo que lo hace cumplir.

## Lo que no puedes correr, y qué hacer al respecto

**En este entorno no hay base de datos**, así que **las pruebas de este trabajo no
se pueden ejecutar aquí**: las de la ruta, las de aislamiento y las de las cuatro
vistas necesitan una base efímera. Las corro yo cuando traiga la rama.

Eso cambia dos cosas y conviene que las hagas a propósito:

- **Escribe las pruebas igual, y con cuidado**, siguiendo el estilo de
  `app/backend/tests/integration/u14/` (que sí usan base). Una prueba que no se
  puede correr allá sigue siendo el sitio donde se dice qué tiene que pasar.
- **Di en tu informe qué no corriste.** La tanda 1 volvió con dos pruebas rojas que
  allá no se veían; eso está bien y es el modo de fallo esperado. Lo que no está
  bien es no decirlo.

Lo que **sí** corre aquí y tiene que quedar en verde: `ruff format`, `ruff check`,
`mypy`, los contratos de importación, el catálogo de textos, los esquemas, la
regeneración de contratos, `tsc`, `prettier`, `eslint` y `vitest`.

## Antes de terminar

1. Corre todo lo de arriba.
2. **Rompe cada regla que dices cumplir y comprueba que se cae una prueba.** Si no
   se cae ninguna, la prueba está escrita a la medida del código: se corrige la
   prueba. Un `ImportError` no cuenta como rotura. Para las que necesitan base,
   di cuál romperías y qué esperarías que se cayera.
3. Escribe `hallazgos-tanda-2.md` en `code-generation/` con lo que rompiste, qué se
   cayó, y qué quedó sin comprobar aquí.
4. Commit **en tu rama**, nunca a `main`.

## Lo que no se toca

- Las cuatro consultas del registro de gasto: ya existen y están probadas.
- La alerta y el corte: son de U15 y U16.
- El panel de cifras de la tanda 1: no se modifica.
- El README: es la tanda 3.
