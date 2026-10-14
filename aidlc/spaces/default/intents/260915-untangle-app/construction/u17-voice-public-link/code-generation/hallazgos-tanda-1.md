# Hallazgos — U17 `voice-public-link`, tanda 1 (nube)

Tanda hecha: la decisión pura de admisión, los dos campos de `CallConfig`, el mensaje de
la tabla de topes que nombra la fila, los avisos de la consola antes del micrófono y las
claves del catálogo. Cierra, en lo que toca a esta tanda, BR1.2, BR1.3, BR1.5, BR2.3,
BR3.1 y BR4.1.

## Sources

- `../functional-design/` (`rules.md`, `entities.md`, `functional-spec.md`) y
  `../nfr-requirements/performance-requirements.md`
- El código: `voice/admission.py` (nuevo), `tenancy/models.py`, `providers/config.py`,
  `app/frontend/src/pages/voice/`, `app/config/copy/{es,en}.yaml`
- `docs/encargos/u17-tanda-1.md`

## Assumptions & Open Questions

None. Las cuatro decisiones que tomé están en «Decisiones», y las dos que le tocan a la
tanda 2 en «Para la tanda 2».

## Lo que se construyó

| Pieza | Dónde |
| --- | --- |
| `calls_per_visitor_day` (1) y `calls_per_site_day` (15), aditivos y sin subir `config_version`; el del sitio no puede ser menor que el de la conexión | `tenancy/models.py` |
| `decide(config, counters, now) -> PublicCallDecision`, con `CallCounters`, `CutCall`; exportada como `decide_admission` en `voice/api.py` | `voice/admission.py` |
| La fila de topes sin fecha no carga y el mensaje dice `(fila 'deepgram' del uso 'voice')` | `providers/config.py` |
| Consola: comprobación previa, demostración con pólizas de ejemplo, los dos límites, aviso de voz de respaldo, póliza de ejemplo y qué probar | `pages/voice/voice-page.tsx`, `voice-routes.tsx` |
| 11 claves nuevas en `voice.console.*`, con paridad | `es.yaml`, `en.yaml` (+ `copy-keys.ts` / `copy-texts.ts` regenerados) |
| `mise run test:u17` | `mise.toml` |

## Roturas: cada regla rota y la prueba que cae

| # | Rotura | Prueba que cae |
| --- | --- | --- |
| R1 | Una retoma gasta la llamada del día | `test_una_retoma_dentro_de_la_ventana_no_gasta_la_llamada_del_dia` |
| R2 | Una retoma no cuenta contra el sitio | `test_una_retoma_dentro_de_la_ventana_si_cuenta_contra_el_sitio` |
| R3 | Ventana comparada con `<=` en el borde exacto | `test_en_el_borde_exacto_la_ventana_ya_se_cerro` |
| R4 | La decisión mira el reloj del proceso | `test_la_decision_sigue_al_reloj_que_se_le_pasa…` |
| R5 | Carril de la conexión con `>` en vez de `>=` | `test_el_carril_de_la_conexion_rechaza_al_llegar_a_su_limite` |
| R6 | Carril del sitio con `>` en vez de `>=` | `test_el_carril_del_sitio_rechaza_al_llegar_a_su_limite` |
| R7 | La decisión devuelve texto en vez de código | `test_el_carril_de_la_conexion_rechaza_al_llegar_a_su_limite` |
| R8 | Una fila de topes sin fecha carga igual | `test_una_fila_de_tope_sin_fecha_no_carga_y_el_mensaje_nombra_la_fila` |
| R9 | El mensaje de la fila sin fecha no la nombra | la misma |
| R10 | La consola pide el micrófono sin tener la disponibilidad (quitados el botón cerrado y la guarda) | `mientras no se sabe si hay voz, el boton no hace nada y el microfono no se pide` |
| R11 | La consola dice «por persona» | `dice los dos limites antes del boton, y dice 'desde esta conexion'` |
| R12 | El aviso de la voz de respaldo no se muestra | `con la voz de respaldo avisa que puede sonar distinta…` |
| R13 | El aviso de respaldo no nombra el idioma | la misma |
| R14 | El carril diario aparece aunque el servidor lo mande nulo | `mientras el servidor no sirva el carril diario, no lo promete` |

Las 14 roturas hicieron caer al menos una prueba. En R10 quité **las dos** protecciones a
la vez (el `disabled` del botón y la guarda de `llamar()`); cada una por separado deja la
prueba en verde, y eso es lo esperado: son dos cerrojos para la misma puerta (BR3.1).

## Decisiones que tomé yo

1. **La tabla de topes no se construyó: ya existía.** U5 la entregó como
   `ProviderCapConfig` en `app/config/providers/prices.yaml`: una fila por (proveedor,
   uso) con `cap_kind`, `cap_value` o `substitute`, y `last_checked_at` **obligatorio**;
   `schema:check` ya exige la fila de cada proveedor de voz (`missing_speech_caps`) y que
   ninguna pase de 30 días (`stale_caps`). `entities.md` y TECH-U17.4 la describen como
   nueva (`ProviderCap`); crear una segunda habría dejado dos tablas autoritativas del
   mismo dato. Lo que **sí** faltaba era el requisito de la tanda: el mensaje de una fila
   sin fecha decía `caps.1.last_checked_at` y no nombraba la fila. Ahora la nombra.
   **Conviene corregir `entities.md` y TECH-U17.4** para que digan «reutiliza
   `ProviderCapConfig`».
2. **Borde de la ventana: abierto.** A los 900 s exactos ya no hay retoma. Es lo que hace
   `session.find_resumable` (`resume_until > :ahora`); si la decisión usara `<=`, la
   disponibilidad ofrecería una retoma que la admisión tomaría por llamada nueva. El
   encargo pedía fijar el borde con una prueba: está fijado.
3. **Con los dos carriles agotados responde el de la conexión.** Es el que la persona
   entiende como suyo; el orden está probado.
4. **Sin respuesta de disponibilidad tampoco hay voz.** Antes, un fallo de red dejaba el
   botón activo. Ahora se trata como «no hay voz» (frase genérica y oferta del chat), por
   la misma razón que `voice_mode` responde «respaldo» cuando falta un dato: lo que
   cuesta dinero se cierra ante la duda.
5. **Los dos límites que la consola dice** son los del Flujo 1: duración por llamada y
   llamadas al día **desde esta conexión**. El carril del sitio no se muestra: es del
   sitio, no de quien mira. Las frases no llevan plural (`{minutes} min.`, `{count}`)
   para no componer texto en el código.

## Para la tanda 2

- **Tres sitios declaran los mismos números.** Además de los campos nuevos de
  `CallConfig`, `providers.yaml` ya trae `voice_limits` (`calls_per_visitor_per_day: 1`,
  `site_daily_cap: 15`) y `quota.site_daily_quota` deriva el cupo real como
  `min(site_daily_cap, lo que alcanza el presupuesto)`. Hay que decidir **cuál manda**
  antes de cablear: lo natural es que `calls_per_site_day` de la aseguradora sea su tope
  y que `site_daily_quota` lo recorte, no que compitan. Lo mismo ocurre ya entre
  `ChatConfig` y `chat_limits`.
- **Nadie emite todavía los dos códigos.** `decide` devuelve `RATE_LIMITED_DAILY` y
  `RATE_LIMITED_SITE`, y `OFF_CODE_KEYS` los mapea a su frase, pero la ruta de
  disponibilidad sigue sin llamarla. `_limites()` en `server/voice_routes.py` también
  sigue sirviendo `calls_per_*` en nulo; **la consola ya los pinta en cuanto lleguen**
  (y los omite mientras sean nulos).
- **El contador del visitante no debe sumar una retoma; el del sitio sí.** La decisión ya
  lo supone (BR1.3) y recibe los contadores como argumento.

## Lo que no pude correr

- **`scripts/verify.sh` entero, `mise run cov`, integración, `a11y` y el arnés**: sin base
  de datos, sin motor de contenedores y sin navegadores.
- **22 pruebas de `tests/unit/tenancy`** (`test_cli`, `test_purge`, `test_visitor_access`,
  `test_rls_assertion`): piden el motor de contenedores
  (`FileNotFoundError` al abrir el socket de Docker). Ninguna toca esta tanda. Resultado
  de la suite unitaria del backend: **2178 pasan, 1 falla y 21 errores, todos de ese grupo**.
- `gitleaks` y `mise run …` directo: `mise` no baja las herramientas (GitHub devuelve 403
  por el proxy).

## Entorno

- **Python 3.13.14**, descargado por `uv` (el `mise.toml` fija 3.13.15; `mise` no pudo
  bajarlo). `uv sync --locked --project app/backend --all-groups --extra models`
  funcionó, así que **los modelos de spaCy están instalados** y las pruebas de redacción
  corren. Los comandos se corrieron directamente, no con `mise run`.
- Frontend: `pnpm 12.4.2` ya estaba en el entorno; `pnpm install --frozen-lockfile`.
- La rama partía de un clon anterior a `ad7791f`; la puse sobre `origin/main` antes de
  tocar nada, como pide el encargo.

## Resultado de las compuertas

`ruff format --check` · `ruff check` · `lint-imports` (36 contratos, 0 rotos) · `mypy` ·
`prettier --check` · `eslint` (0 errores; los avisos son anteriores) · `tsc --noEmit` ·
`copy:check` (siete chequeos) · `content:check` · `schema:check` · `voice:frases` ·
`contracts:check` · `vitest` completo (350) · pruebas de la unidad (`test:u17`: 39 de
backend y 46 de la consola).

---

## La revisión local de la tanda 1

Escrita en la sesión local el 2026-09-30. Corrí las pruebas de la unidad, **las once
compuertas baratas sin recortes**, y rompí tres reglas más.

### Lo que la tanda hizo bien

- **Leyó antes de construir, y encontró dos errores de mi diseño.** Los dos eran ciertos
  y están corregidos en los documentos, no en el código.
- **No creó una segunda tabla de topes** al descubrir que ya existía. Un diseño que pide
  construir algo que ya está es una invitación a duplicarlo, y la tanda no la aceptó.
- **La decisión de admisión está muy bien escrita**: pura, con la asimetría de la retoma
  explicada en el docstring, el borde de la ventana alineado a propósito con
  `find_resumable` —si discreparan en un segundo, la disponibilidad ofrecería una retoma
  que la admisión trataría como llamada nueva—, y los contadores como dato de entrada con
  la razón de por qué no incluyen la llamada que se intenta.

### Los dos errores de mi diseño, y lo que costaron

**1. `calls_per_site_day` no puede vivir en la configuración de una aseguradora.**
FD-U17-2 decía que los dos carriles iban a `CallConfig`, que es por aseguradora: «quince
llamadas del sitio» escrito en tres carpetas son cuarenta y cinco, o las que toque leer.
Y `VoiceLimits` ya los declaraba, sin valor por omisión a propósito, en el archivo que se
revisa cuando hay que explicar un rechazo. Además el cupo del sitio **se deriva** cada día
de lo que queda del presupuesto, así que una copia fija discreparía del cálculo que
protege el dinero.

Corregido: la decisión recibe un `CallLanes` con los tres números ya reunidos —los dos
carriles del sitio, la ventana de retoma de la aseguradora— y `CallConfig` vuelve a tener
tres campos. Dos pruebas nuevas fijan el reparto: una se cae si alguien vuelve a poner los
carriles en `CallConfig`, y otra exige que los de la plataforma sigan sin valor por
omisión.

**2. La tabla de topes ya existía** (`ProviderCapConfig` en `prices.yaml`). FD-U17-8 y
TECH-U17.4 la describían como nueva. Corregidos.

### Lo que la revisión encontró

**Una rotura que no cayó nada: la disponibilidad que falla.** La tanda arregló que un
fallo de red dejara el botón activo —y lo arregló bien—, pero `availability(...)` no tenía
`.catch`. La conducta no era insegura: la fase se quedaba en `checking` y el botón
deshabilitado. Lo que pasaba es peor de lo que parece: **quien abría la consola se quedaba
en «comprobando» para siempre**, sin motivo y sin la oferta del chat, que es peor
experiencia que una indisponibilidad declarada. Y una promesa sin atrapar deja un error de
consola, que es justo lo que el arnés vigila.

Corregido: una petición que falla acaba en el mismo sitio que una respuesta vacía, con su
prueba.

Las otras dos roturas sí cayeron: que la retoma se saltara también el carril del sitio
(`test_una_retoma_dentro_de_la_ventana_si_cuenta_contra_el_sitio`) y que el borde de la
ventana pasara a cerrado (`test_en_el_borde_exacto_la_ventana_ya_se_cerro`).

### La primera entrada de la lista de excepciones de `copy:check`

Al mover la validación de los carriles desde `tenancy/models.py` hasta `voice/`, su
mensaje de error entró en el alcance del chequeo de cadenas en línea. No es copy: es el
mensaje de un `ValueError` sobre una configuración mal escrita, en un módulo que **por
construcción no emite texto hacia nadie**. Se usó la válvula que existe para eso, con su
razón escrita, y es la primera entrada que tiene.

Se deja el mensaje largo a propósito —que es por lo que la heurística lo caza—: nombrar la
condición es la diferencia entre un error que se arregla en un minuto y uno que se
investiga una hora.

### Lo que queda para la tanda 2

Además de lo que el plan ya decía, dos cosas que la tanda 1 dejó dichas y conviene no
perder:

- **Nadie emite todavía los dos códigos de carril**: `_limites()` sigue sirviendo
  `calls_per_*` en nulo. La consola ya los pinta en cuanto lleguen.
- **`max_call_seconds` está declarado en dos sitios**: `CallConfig` (que es el que corta
  hoy, de U16) y `VoiceLimits`. No se tocó porque es conducta construida y probada de otra
  unidad, pero la contradicción queda nombrada aquí para que se reconcilie y no se
  descubra sola.
