# Hallazgos de la tanda 1 — U19 `quote`

La solicitud de cotización y su elegibilidad: esquema, cuatro bloques de captura, reglas de
Sunmeadow, salida y banda, frases del catálogo y DS-4. Sesión en la nube, rama
`claude/new-session-nufj42`.

## Sources

- `../functional-design/rules.md` — BR1.1 a BR3.2
- `../functional-design/functional-design-questions.md` — las respuestas Q1, Q2 y Q3
- `docs/reference/estructura-solicitud-cotizacion.md` — los cuatro bloques
- `docs/encargos/u19-tanda-1.md`

## Assumptions & Open Questions

None. Las decisiones que tomé yo están en «Decisiones que conviene revisar»; ninguna cambia lo que
Miguel contestó.

## Entorno

- **Python 3.13.14** (`/usr/bin/python3.13`) con el lockfile tal cual. `mise` no pudo bajar 3.13.15
  (el túnel rechaza `objects.githubusercontent.com`), así que corrí los comandos de `mise.toml`
  directamente con `uv run --project app/backend`.
- **Los modelos de spaCy sí bajaron**, con `uv sync --locked --project app/backend --all-groups
  --extra models`. Las pruebas de redacción corren.

## Qué quedó verde

| Qué | Resultado |
| --- | --- |
| `ruff format --check`, `prettier --check` | verde |
| `ruff check`, `lint-imports` (36 contratos), `eslint` | verde (eslint: 17 avisos que ya estaban, ninguno en archivos tocados) |
| `mypy` (653 archivos), `tsc --noEmit` | verde |
| `copy:check`, `content:check`, `schema:check`, `tenancy:literals`, `voice:frases`, `chat:frases` | verde |
| `contracts:check` (regenerado y comparado tras commitear), `synthetic:check`, `readme:check`, `case:transitions`, `case:constructor`, `redaction:constructor`, `env:check` | verde |
| Pruebas unitarias del backend | 2.394+ pasan |
| Pruebas del frontend (`vitest`) | 337 pasan |
| `evals:gate --subset smoke` | verde: 86 casos, 43 por idioma (los 12 nuevos de DS-4 incluidos) |
| PERF-U19.1 (p95 ≤ 20 ms) y PERF-U19.2 | verde |

## Roturas: qué se cayó

Para cada regla nueva rompí el código o los datos, corrí las pruebas de la unidad y restauré. **Las 24
hicieron caer al menos una prueba.**

| # | Rotura | Prueba que se cayó |
| --- | --- | --- |
| M01 | Un campo de elegibilidad que ningún bloque escribe | `test_cada_campo_de_elegibilidad_tiene_su_tipo` (y la que compara contra el esquema) |
| M02 | El tipo admite una derivación con banda afirmada | `test_una_derivacion_con_banda_afirmada_no_se_construye` |
| M02b | El YAML declara una derivación con `elevated_risk` | las cinco condiciones de Q3 (el conjunto no carga) |
| M03 | Una regla compara la antigüedad contra 2001 | las cinco condiciones de Q3 (el conjunto no carga) |
| M03b | El cargador deja de vigilar el año del calendario | `..._compara_la_antiguedad_contra_un_anio_del_calendario_no_carga[1900]` |
| M04 | Un importe (`$450`) en una frase del catálogo, español | `test_ninguna_frase_de_la_cotizacion_la_toca_la_guardia[es]` |
| M04b | Un porcentaje (`15%`) en una frase, inglés | `test_ninguna_frase_de_la_cotizacion_la_toca_la_guardia[en]` |
| M05 | `turn.py` importa el motor de reglas | `test_br2_5_el_camino_del_turno_no_llega_al_motor_de_reglas...` (y el contrato de `.importlinter`) |
| M06 | Un quinto nodo del grafo | `test_el_grafo_sigue_teniendo_cuatro_nodos` |
| M07 | Un bloque se da por leído sin confirmarlo | `test_node.py::..._no_se_vuelve_a_preguntar_...` |
| M08 | La antigüedad se calcula en un segundo sitio | `test_la_antiguedad_se_calcula_en_un_solo_sitio_del_codigo` |
| M09 | Umbral puesto por uno (25 en vez de 26) | las cinco condiciones de Q3 |
| M10 | El motor evalúa con datos que faltan | `test_sin_un_campo_que_el_conjunto_lee_no_se_evalua` |
| M11 | El modelo puede escribir el campo derivado | `test_el_modelo_no_puede_escribir_un_campo_derivado` |
| M12 | Un valor que no se convierte se escribe tal cual | `test_un_valor_que_no_se_puede_convertir_no_se_escribe` |
| M13 | La lectura vuelve a elegir «el bloque ya debido» | `test_case_context_readback.py` |
| M14 | El reconocedor de presión deja de ver «precio» | `test_la_insistencia_en_un_precio_recibe_la_negativa_fija` |
| M15 | Stonecroft enciende la cotización sin conjunto | `..._siguen_apagadas_y_sin_conjunto` |
| M16 | La lectura imprime el valor del enum | `test_las_lecturas_nombran_todo_lo_dicho_y_con_etiqueta_no_con_enum[es]` |
| M17 | «No tengo idea» se lee como un no | `test_un_valor_que_no_se_puede_convertir_no_se_escribe[salvage_title-no idea-en]` |
| M18 | El triage puede leer campos de elegibilidad | `test_el_triage_no_puede_leer_un_campo_de_elegibilidad` |
| M19 | Una razón del YAML que las frases no saben decir | `test_gana_la_salida_mas_prudente...` (el conjunto no carga) |
| M20 | Se abre una solicitud donde la cotización está apagada | `test_case_opening.py::..._donde_esta_apagada_no_abre_una_solicitud` |
| M21 | Un campo ya dicho se vuelve a preguntar (BR3.3 de U11) | `test_node.py::..._no_se_vuelve_a_preguntar_...` |
| M22 | El nodo acepta claves de otro tipo de caso | `test_una_clave_de_otro_tipo_de_caso_no_tumba_el_turno` |
| M23 | Dos preguntas en una frase del catálogo | `test_el_recorrido_completo_pregunta_de_a_un_campo...[en]` |

Dos de las pruebas que primero escribí **no se caían** y las corregí: el recorrido de lectura por
bloque (ver el defecto de abajo) y un `«no idea»` leído como `false`.

## Defectos que encontré en código existente

1. **`stated_values_for_readback` dejaba la lectura de un bloque con el resto en blanco.** Elegía «el
   primer bloque cuya lectura está debida», pero un bloque de varios campos se completa en el turno
   que trae el último, y en el turno anterior aún no estaba debido: devolvía nada. Con «cuándo y
   dónde» del siniestro pasaba casi siempre desapercibido; con los cuatro o seis campos de un bloque
   de la solicitud, preguntados de a uno, habría pasado siempre. Corregido (`case_context.py`) y
   cubierto. **Toca también el flujo de siniestros**: sus pruebas de integración no corrieron aquí.
2. **Una clave de otro tipo de caso tumbaba el turno.** El prompt de extracción es uno para todos los
   tipos, y si el modelo devolvía `injuries` en una solicitud, guardarlo lanzaba `CaseSchemaError`.
   Ahora se descarta. Mismo cambio para siniestros: lo que antes lanzaba, ahora se ignora.

## Decisiones que conviene revisar

- **Los diecisiete campos exigen lectura** (`requires_readback: true`): la confirmación es por bloque
  y el mecanismo que confirma un bloque es la lectura de sus campos. Un bloque sin ningún campo con
  lectura no se podría confirmar.
- **`lapse_months` se deriva en 0 para quien tiene cobertura vigente.** El campo es «meses sin
  cobertura, cuando no tiene»; preguntárselo a quien sí la tiene no terminaría el bloque. Es una
  deducción mía, no del documento.
- **`annual_mileage_band` son tres tramos relativos** (`low`, `medium`, `high`), sin números: el
  documento dice «tramos, no un número» y fijar cifras obligaba a elegir entre millas y kilómetros.
- **Las conversiones son tablas cerradas y bilingües** (conteos, sí/no, uso, recorrido), acotadas a lo
  que DS-4 necesita, como el reconocedor de cobertura. Son heurísticas: «personal, y a veces
  entregas» se lee como comercial a propósito (lo más restrictivo). Un valor que no convierten **no se
  escribe** y se vuelve a preguntar.
- **Separé el vocabulario de reglas en dos familias** (`TRIAGE_FIELDS` y `ELIGIBILITY_FIELDS`;
  `KNOWN_FIELDS` es la unión) y cada cargador solo deja leer la suya. El triage no cambia.
- **Extendí el contrato `ritmo-del-turno-sin-verificacion-ni-reglas`** a `orchestration.turn` y
  `orchestration.quote_reply`. Si el cableado del grafo de fondo (PENDIENTES 1.8) necesita que
  `turn.py` llegue a `rules`, este contrato lo va a frenar, y es lo que BR2.5 pide.
- **Agregué los diecisiete `case.field.*` a `inbox-labels.ts`**: una prueba del frontend exige que
  cubra cada clave del catálogo. No es la bandeja del suscriptor, solo las etiquetas.
- **El cierre de la solicitud** (`intake.closing.summary_quote`) es a la vez resumen y frase de espera.
  No pide confirmación final: cada bloque ya se confirmó.

## Riesgos que dejo dichos

1. **La cotización queda encendida en Sunmeadow y no termina.** Tras la captura la agente dice «reviso
   si su solicitud puede seguir y le cuento», pero la elegibilidad corre en el ritmo de fondo, que no
   está cableado (PENDIENTES 1.8), y la bandeja del suscriptor es la tanda 2. `compose_eligibility_reply`
   existe y está probada, pero nadie la llama todavía. Nada se publica antes de la pasada de
   publicación; hasta entonces es un compromiso pendiente.
2. **La apertura de voz de Sunmeadow ofrece cotizar** (`voice/opening.py` lee `quote_enabled`) y la
   voz no abre solicitudes: solo el chat. Es lo que `NEVER prometer ... una capacidad que no está
   construida` prohíbe. No lo toqué (no era del encargo). Decisión de Miguel: separar la bandera por
   canal o apagar la oferta de voz hasta que exista.
3. **Reconocedores deterministas.** «Quiero cotizar» y «cuánto cuesta» se detectan con expresiones
   cerradas. Un giro que no esté en DS-4 pasa de largo y lo atiende el flujo normal; el remedio es un
   caso nuevo, no ensanchar a ciegas.

## Lo que no pude correr

- `scripts/verify.sh` entero, `mise run cov` (el piso del 80 %), las pruebas de integración y las
  unitarias que levantan base: el entorno no tiene motor de contenedores. Fallan 1 prueba y 21 errores
  de `tests/unit/tenancy/`, todos por `docker`; ya fallaban antes de mi primer cambio.
- Las **evaluaciones contra proveedores**. Los dos casos de canal de DS-4 (`quote-end-to-end` y
  `quote-price-pressure-conversation`, por idioma) están **escritos y validados de forma, sin
  ejecutar**. Su `expected_record` (17 de 17, estado `capturing`) es mi lectura de lo que dejaría la
  captura; la primera corrida real puede pedir ajustarlo.
- `audit` y `licenses:check` (red): no añadí ninguna dependencia.
- **Cobertura del 80 %** de los módulos críticos: no medida aquí. El código nuevo está cubierto por
  las pruebas de arriba, pero la cifra la da `mise run cov` en GitHub Actions.

## Archivos de datos nuevos

`rules/eligibility.yaml` de Sunmeadow (7 reglas), 65 frases por idioma en el catálogo,
`app/evals/fixtures/quote/{es,en}.yaml`, `app/evals/cases/ds4/` (16 casos), manifiesto (DS-4:
`built: true`, 16), 12 casos nuevos en `smoke` y la tarea `test:u19`. `app/data/manifest.json` se
regeneró porque `tenant.yaml` es una de sus fuentes.

---

## La revisión local de la tanda 1

Escrita en la sesión local el 2026-09-30. Corrí **la suite unitaria entera del backend
(2.499) y la del frontend (383)**, las once compuertas baratas sin recortes, y rompí tres
reglas más.

### Lo que la tanda hizo mejor de lo que el diseño pedía

**Dos reglas que el diseño enunciaba como convención, la tanda las convirtió en
comprobaciones del cargador**, que es la diferencia entre una regla y un deseo:

- **BR1.4, la comparación contra un año del calendario.** El diseño decía que la
  antigüedad fuera un campo derivado. La tanda añadió `_no_compara_contra_un_anio`: una
  regla cuyo valor sea un número de aspecto de año **no carga**, y el mensaje explica que
  envejecería sola sin que falle nada. Romperla tumba cuatro pruebas, incluida la del
  combinador anidado.
- **BR2.4, los casos de prueba de cada regla.** No es que existan: es que **se corren al
  cargar**, cada `{given, expect}` contra su propia condición. Una regla cuyo caso falla no
  carga. Romperlo tumba dos pruebas.

Y la pareja salida–banda vive en un validador: una derivación solo admite
`pending_review`, y las cuatro parejas válidas son una tabla.

### Las tres roturas propias

| Rotura | Qué se cayó |
| --- | --- |
| La guarda del año del calendario no comprueba nada | 4 pruebas |
| Los casos de prueba de cada regla no se corren al cargar | 2 pruebas |
| *(ver abajo: la decisión de la voz, que no era una rotura sino un hallazgo)* | — |

### El hallazgo que cambió código: la voz ofrecía cotizar

La tanda lo dejó dicho como riesgo y tenía razón, pero es más que un riesgo: **es una
promesa que ese canal no puede cumplir ni después de la tanda 2**. `voice/opening.py` leía
`quote_enabled` y ofrecía cotizar; la solicitud se captura en el chat —`chat.case_opening`
es quien abre un caso `quote_request`— y **la voz no abre ninguno**. La tanda 2 construye
la bandeja del suscriptor, no la captura por voz, así que esperar a la tanda 2 no lo
arregla.

`quote_enabled` dice que **la aseguradora** cotiza, no que lo haga **por este canal**. La
apertura de la voz deja de ofrecerlo, con la razón escrita y con su prueba —que exige que
el texto sea idéntico con la bandera en `true` y en `false`—, y la clave
`voice.opening.capability_quote` se retira de los dos catálogos: una clave que nada emite
pasa el chequeo de claves sin consumidor solo porque su constante existe.

El día que la voz capture solicitudes, esto vuelve con su prueba. Mientras tanto, la
diferencia entre «esta aseguradora cotiza» y «este canal cotiza» es real y ahora se nota
en el código.

### El otro riesgo: Sunmeadow ofrece cotizar y no termina

También cierto, y **no se resuelve apagando la bandera**. Hoy no se nota porque nada está
publicado; el día que se publique, un visitante de Sunmeadow contaría diecisiete campos en
cuatro bloques y no recibiría respuesta nunca, porque el cableado del grafo de fondo y la
bandeja del suscriptor no existen y el único consumidor de `compose_eligibility_reply` es
el conductor de evaluaciones.

Apagarla ahora costaría rehacer las expectativas de DS-4 —el conductor lee la
configuración real— para proteger de un riesgo que todavía no existe. Así que queda como
**criterio bloqueante de la pasada de publicación**: `quote_enabled` no puede estar en
`true` al publicar sin la tanda 2 y el cableado. Es el sitio donde ya viven los otros
cinco criterios de ese tipo, y el que se revisa antes de publicar.

### Las cinco decisiones de la tanda

Las cinco están bien y no las cambio. La que más miré fue **`lapse_months` derivado en 0
cuando hay cobertura vigente**: podría parecer que inventa un dato, y no lo hace —es la
lectura correcta de «no hubo interrupción»— y además ninguna regla de elegibilidad lo
lee hoy, así que no decide nada.

### Los dos defectos que encontró en código existente

Los dos son reales y su arreglo toca también el flujo de siniestros:
`stated_values_for_readback` dejaba la lectura de un bloque con el resto de campos en
blanco, y una clave de otro tipo de caso tumbaba el turno. Las 2.499 pruebas unitarias
pasan con los dos arreglos; **sus pruebas de integración no se corrieron aquí** y quedan
para la corrida de la tubería, que sí las ejecuta.
