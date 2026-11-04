# Ajustador de IA (fase 5 del plan 09)

Decisión de Miguel del 2026-11-02 (puntos 3, 3a y 3b de `09-correcciones-revisor-2026-11-02.md`):
cuando un caso llega al ajustador, lo decide **un subagente de IA** que explica su
decisión con fuentes reales y un proceso visible. El visitante solo ve la decisión y su
explicación; se quita la parte de la demo en la que juega a ser ajustador.

Este documento es el diseño. El mapa del código en que se apoya es de la sesión del
2026-11-03; lo que el mapa encontró y cambia el planteamiento está en «Lo que cambia respecto a
lo que se creía».

## Lo que cambia respecto a lo que se creía

- **No hay `interrupt()` en producción.** El caso espera en la base de datos, en el estado
  `derived`, hasta que alguien llame a `close_case`. No hay grafo que reanudar. Por eso el
  ajustador de IA es un trabajo de fondo que cierra el caso por la misma vía que hoy usa una
  persona, sin tocar el grafo.
- **El adaptador de Claude es de un solo disparo** (sin herramientas, sin búsqueda web). La
  búsqueda web hay que agregarla al adaptador, que es el único lugar que puede importar el SDK.
- **No existe nada de «valor comercial» ni de Fasecolda en el código**; solo cláusulas que lo
  nombran. Ni la póliza guarda el código Fasecolda del vehículo (solo «marca modelo año»).
- **Quién firma:** hoy el actor de una decisión es `staff` o el visitante. Hace falta un actor
  nuevo (`adjuster_ai`) para que «quién decidió» diga la verdad.

## Decisiones de diseño

| # | Decisión | Por qué |
| --- | --- | --- |
| A1 | El ajustador de IA es un trabajo de fondo disparado cuando el caso se deriva, con reintento al leer el caso | No hay nada que reanudar; un proceso que se cae entre derivar y decidir deja el caso en `derived`, y el reintento al leer lo recoge |
| A2 | Son **dos llamadas** a Claude Haiku por caso, como mucho: una de investigación (con búsqueda web, hasta 3) y una de decisión (salida estructurada). Todo lo que se pueda resolver con código sale de código: relato, vigencia, vehículos, conductores, límites y deducibles, reglas, recuperación y verificación de cláusulas | Ahorra consumo y deja la decisión sobre hechos exactos, no sobre lo que el modelo recuerde |
| A3 | La decisión sale del mismo conjunto de acciones de hoy y se valida con la misma regla: una aseguradora **aprueba o rechaza**; la agencia solo **envía a la aseguradora** (`actions.allowed_for`) | No se abre una vía nueva; la agencia sigue sin decidir cobertura |
| A4 | Cada cláusula que cite la explicación la verifica el verificador exacto (existe, es de la aseguradora y de la póliza, está vigente, no es señuelo). Una cita que no pasa se quita de la explicación | Principio P2 del proyecto: una cita solo sale de una cláusula recuperada y verificada |
| A5 | La explicación y la decisión se **guardan antes de registrar el cierre**, y el cierre se registra con ese texto fijo | La huella del recibo (`digest_of`) incluye el comentario; un texto generado de nuevo en un reintento daría `RecycledKeyError` |
| A6 | La explicación sale por **su propia superficie** (la pantalla del caso), no por la transcripción del chat. El chat recibe solo el aviso de plantilla «tu caso ya tiene una decisión, míralo en Ver mi caso» | Mantiene intacta la compuerta dura «cero turnos de la agente que afirmen cobertura, montos o culpa» (`transcript_guard_clean`) |
| A7 | El texto de la explicación pasa por la guardia de salida con una clave propia (`adjuster.decision`) que exime **solo** promesas de cobertura y montos. Culpa, consejo legal, revelación de configuración y afirmar ser una persona siguen vigiladas | Es la decisión misma lo que puede decir «cubre» y cifras; lo demás sigue prohibido |
| A8 | `coverage_disputed`, `fraud_suspected` y `claim_amount` siguen siendo de una persona con credencial: el ajustador de IA no los escribe y no cambia la categoría de las reglas | Enmendar esa decisión no se pidió |
| A9 | Los casos de **agencia** (siempre derivan) los atiende el ajustador de IA con la acción «enviar a la aseguradora», con el análisis y las fuentes en la explicación | La agencia no decide cobertura |
| A10 | Tope diario de casos en la demo pública (por defecto 20), contado en el cupo que ya existe, con su mensaje honesto cuando se alcanza; el caso queda en espera y lo recoge el reintento al día siguiente | El gasto de búsqueda es variable (1 centavo por búsqueda, 3 por caso) |
| A11 | Uso nuevo `adjuster` con **clave propia** y su propio tope en el proveedor, como cualquier otro uso | Regla de claves separadas por uso |
| A12 | Un fallo (modelo, búsqueda, cita) nunca inventa una decisión: el caso queda `derived`, la pantalla dice que sigue en revisión y el reintento lo vuelve a intentar hasta 3 veces | «No pude verificar» no es una decisión |

## Cómo decide (el proceso que ve la persona)

Seis pasos con identificador estable. Cada uno guarda su texto y sus fuentes apenas termina,
para que la pantalla los muestre llegando (la pantalla consulta cada 3 segundos).

1. **Lee el reporte** (`case_read`): campos anotados, relato y reglas disparadas. Código.
2. **Lee la póliza** (`policy_read`): vigencia, vehículo, conductores, límites y deducibles,
   condiciones especiales. Código (`policy_rag.facts`).
3. **Busca las cláusulas** (`clauses`): recuperación de cláusulas de la póliza y verificación
   exacta de las que cite. Código más embeddings.
4. **Mira las reglas** (`rules`): qué reglas se dispararon y por qué derivaron el caso. Código.
5. **Valor de referencia del vehículo** (`vehicle_value`): una llamada con búsqueda web, hasta 3
   búsquedas, sobre una lista de dominios de la configuración (Guía de Valores de Fasecolda y
   avisos de venta). Devuelve valor, fuente (URL) y qué tan firme es; fuera de un rango plausible
   se descarta y se dice «no pude verificar el valor». Solo corre si la póliza trae el vehículo.
6. **Decide** (`decision`): una llamada de salida estructurada con todo lo anterior como datos
   delimitados. Devuelve decisión, resumen, razones y cláusulas citadas. El código valida la
   acción contra el tipo de aseguradora, quita las citas no verificadas y pasa el texto por la
   guardia.

## Datos nuevos

- `ActorType.ADJUSTER_AI`: migración del CHECK `case_change_actor_valido`, el modelo `Actor`, las
  etiquetas de «quién decidió» y `isClosedByRules` en la interfaz.
- Tabla `adjuster_run` (tenant, caso, estado `running|decided|capped|failed`, intento, pasos como
  JSON con sus fuentes, decisión, resumen, modelo, búsquedas usadas, error). Aislada por
  aseguradora, con su prueba de aislamiento; se borra con el caso en el reinicio nocturno.
- `Use.ADJUSTER`, con su clave `UNTANGLE_ANTHROPIC_API_KEY_ADJUSTER`, su fila en `prices.yaml`,
  su cupo diario en `providers.yaml` y una unidad nueva del libro, `web_searches`, con su
  precio de lista.
- Configuración versionada del ajustador: modelo, máximo de búsquedas (3), dominios permitidos,
  tope diario, intentos.

## Dónde vive el código

- Paquete nuevo `untangle.adjuster`, en la capa justo encima de `inbox` (llama a su `decide`) y
  por debajo de `server`. No importa el SDK: recibe la investigación y la decisión como puertos
  que enchufa la raíz de composición (`raiz-de-composicion`).
- Puerto nuevo `WebResearcher` en `providers/ports.py` y su implementación en el adaptador de
  Anthropic (herramienta de búsqueda web del servidor, con `max_uses` y dominios permitidos).
  La salida estructurada y la búsqueda van en llamadas separadas.
- `orchestration` dispara por un puerto (patrón de `install_resume_handler`) al derivar el caso;
  `orchestration` no importa `inbox` ni `adjuster`.
- `inbox/decision.decide` acepta el actor `adjuster_ai`; el visitante deja de poder decidir y de
  anotar (las rutas devuelven 403 al visitante; el personal con credencial conserva las suyas).
- `chat/notice.py`: para el actor `adjuster_ai`, el aviso es la plantilla sin el comentario.

## Interfaz

- La pantalla del visitante (`visitor-page.tsx`) pierde el panel «Haz de ajustador» (el triaje y
  el formulario de decisión) y gana un panel **«Cómo decidió el ajustador»**: estado en curso con
  los pasos apareciendo, decisión con su etiqueta, resumen, los seis pasos con sus fuentes
  (cláusulas con su cita, reglas, enlace a la fuente del valor) y un aviso de que lo escribió una
  IA.
- Se retiran el enlace «Decidir este caso como ajustador» del chat, el paso «Decide como
  ajustador» de la guía y las notas de los casos de ejemplo que lo mencionan.
- La pantalla del personal muestra el mismo panel, de solo lectura.

## Pruebas y evaluaciones (primero los casos)

- Subconjunto nuevo `ajustador` de DS-2, en español e inglés, que corre el proceso entero contra el
  corpus y Claude (centavos, a mano y por hito): choque cubierto → aprueba y cita
  `D.INS.COLLISION`; uso en plataforma de viajes sin el endoso → rechaza citando la exclusión;
  póliza vencida → rechaza por vigencia; agencia → solo envía a la aseguradora; el valor del
  vehículo no se encuentra → lo dice y decide igual.
- Criterios medidos por código: la acción es de las permitidas para ese tipo de aseguradora; toda
  cláusula citada está recuperada y verificada; el idioma de la explicación es el del caso; no hay
  más de 3 búsquedas; la guardia no sustituye nada por culpa o consejo legal; la decisión y la
  vigencia concuerdan con los hechos de la póliza.
- Pruebas unitarias del proceso con dobles del modelo y de la búsqueda; de integración, la
  idempotencia (dos arranques, un solo cierre), el aislamiento de `adjuster_run` y las rutas que
  ahora devuelven 403 al visitante.
- Los casos de DS-6 y la compuerta de transcripción siguen midiendo solo a la agente que
  conversa.

## Textos que cambian en la misma tanda

README y `README.es.md`, la landing, el catálogo de textos (`guide.*`, `visitor.*`, `cases.*`,
`chat.page.decide_as_adjuster`), la regla de `PENDIENTES-MIGUEL.md` sobre quién anota los datos de
triaje, y el diagrama de la arquitectura. La agente que conversa sigue sin afirmar cobertura ni
montos, y eso es lo que sigue diciendo la landing de ella.

## Entregas

| Tanda | Contenido | Se sube cuando |
| --- | --- | --- |
| 1 | Cimientos: uso `adjuster`, configuración, unidad de búsquedas, tope diario, actor `adjuster_ai`, tabla `adjuster_run`, puerto y adaptador de búsqueda web, herramienta del valor de referencia. Con pruebas | Verde en GitHub |
| 2 | El proceso, el disparo al derivar, el reintento al leer, la decisión con el actor nuevo, el aviso del chat, la guardia, los 403, los casos de golden set y su corrida | Verde en GitHub y `ajustador` en verde |
| 3 | Interfaz, textos, README, landing, pruebas de interfaz y accesibilidad | Verde en GitHub; Miguel prueba en local |

Nada se publica a producción hasta que Miguel pruebe. La publicación necesita además la clave
propia del uso en el entorno y su tope en el proveedor.

## Riesgos que quedan

- Una búsqueda web puede traer un valor equivocado: por eso se pide la fuente y un rango
  plausible, y la decisión no depende de él.
- El enlace del visitante vive una hora; la decisión llega en menos de un minuto, pero quien lo
  abra después ya no la ve. No cambia en esta fase.
- La clave del uso comparte el crédito prepagado de la cuenta de Claude con el chat. El tope diario
  protege ese saldo.
- `PERSON_REQUESTED` (la persona pidió hablar con alguien) también lo atiende el ajustador de IA:
  en esta demo el ajustador es el de IA y así se dice en todos los textos.

## Estado (2026-11-03, pausa por límite de uso)

| Tanda | Estado |
| --- | --- |
| 1 Cimientos | Hecha y subida (`91985498`). Las migraciones u24 aún no se han aplicado contra una base: la primera vez es la corrida de GitHub |
| 2a Proceso que decide | **Sin empezar el código.** Hay seis archivos de pruebas escritos primero y sin commitear en `app/backend/tests/unit/adjuster/` (`conftest.py`, `support.py`, `test_pipeline.py`, `test_prompting.py`, `test_validation.py`, `test_vehicle_value.py`): fallan hasta que exista la implementación. Falta `gather.py`, `vehicle_value.py`, `schema.py`, `validation.py`, `pipeline.py`, los prompts `app/config/prompts/adjuster.{es,en}.md`, las claves `adjuster.step.*` del catálogo y la exención `adjuster.decision` en la guardia |
| 2b Cableado | Pendiente: disparo al derivar (puerto en `orchestration`, patrón de `install_resume_handler`), `inbox.decision.decide` con el actor `adjuster_ai`, aviso del chat sin comentario, 403 al visitante en `decide_case` y `annotate_triage`, reintento al leer, bloque del ajustador en `CaseDetailOut`, enchufes en `server/composition.py`, retiro de `demo_adjuster_link.py` |
| 2c Golden set | Casos, sondas y corredor escritos (2026-11-04): diez casos `adjuster-*` de DS-2 (cinco parejas), subconjunto `ajustador`, ocho criterios por codigo y `mise run evals:ajustador`. **Falta la corrida con el modelo real**, que se hace a mano con aprobacion de Miguel: `UNTANGLE_ANTHROPIC_API_KEY_ADJUSTER="$(grep -m1 '^UNTANGLE_ANTHROPIC_API_KEY_EVALS=' .env \| cut -d= -f2-)" mise run evals:ajustador` (la clave de evaluaciones prestada solo en ese comando). No corre en la compuerta de cada entrega (`subset_only`) |
| 3 Interfaz y textos | Pendiente: panel «Cómo decidió el ajustador», sacar el panel de jugar a ser ajustador, README, landing, guía y catálogo |

Lo subido hasta aquí es inerte: nada dispara el ajustador, así que el producto se comporta como antes y los textos públicos siguen siendo ciertos.

Cómo seguir sin gastar de más: sesión nueva (esta carga unos 700.000 tokens de historial), un solo agente a la vez, sin informes largos, y subir 2b y 2c juntos y 3 aparte. Mapa del código y decisiones: este documento y `09-correcciones-revisor-2026-11-02.md`.
