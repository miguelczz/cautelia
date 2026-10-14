# Hallazgos — U20 `demo-operations`, tanda 1

Tanda en la nube. Construye la validación de la carpeta de una aseguradora, la
orquestación del reinicio sobre el contrato `VisitorDataPurger`, `ResetRun`, la regla
de las 24 horas y las dos claves del catálogo. Todo puro: archivos y dobles, sin base.

## Qué se construyó

| Pieza | Dónde |
| --- | --- |
| Validación de la carpeta (`validate_tenant_folder`, `TenantFolderReport`, `TenantFault`) | `demo_operations/folder.py`, `models.py` |
| Orquestación (`run_reset`) y regla de 24 horas (`accepts_new_cases`, `last_successful_reset`) | `demo_operations/reset.py` |
| `ResetRun`, `PurgerRow`, `ResetOutcome` con validadores que impiden estados imposibles | `demo_operations/models.py` |
| Claves `demo.reset.conversation_notice` y `demo.reset.surfaces_closed`, es y en | `app/config/copy/{es,en}.yaml`, módulos generados del frontend |
| Tarea `test:u20` | `mise.toml` |
| 54 pruebas, cobertura del módulo 99 % | `tests/unit/demo_operations/` |

Reglas que cierra: BR1.1, BR2.4, BR3.1, BR3.2. BR3.3 queda cerrada solo **por
construcción** (ver decisión 5): su cumplimiento real es de la tanda 2.

## Roturas: cada regla rota, y qué prueba se cae

Se rompió el código de producción uno a uno y se corrió la unidad. **Una rotura
sobrevivió en la primera pasada** (fila marcada): la prueba estaba hecha a la medida
del código, se corrigió y ahora cae.

| Rotura | Prueba que cae |
| --- | --- |
| La validación devuelve solo la primera falta | `test_una_carpeta_sin_dos_cosas_reporta_las_dos_con_archivo_y_campo` |
| `partial` colapsado en `failed` | `test_siete_que_borran_y_dos_que_fallan_es_partial` |
| `partial` colapsado en `succeeded` | `test_siete_que_borran_y_dos_que_fallan_es_partial` |
| Contador atado al último intento | `test_tres_intentos_fallidos_seguidos_no_reinician_el_contador` |
| Un `partial` reciente cuenta como éxito | `test_un_parcial_reciente_no_reinicia_el_contador` |
| La orquestación mira el reloj del proceso (inicio) | `test_los_instantes_salen_del_reloj_inyectado_y_no_del_del_proceso` (aislada, además de la caída incidental de otra) |
| Idem, en la duración por purgador | `test_los_instantes_salen_del_reloj_inyectado_y_no_del_del_proceso` |
| Un purgador que levanta detiene a los siguientes | `test_un_purgador_que_levanta_queda_en_el_registro_y_no_detiene_a_los_demas` |
| Un purgador que levanta no queda en el registro | `test_un_purgador_que_levanta_queda_en_el_registro_y_no_detiene_a_los_demas` |
| Límite inclusivo a las 24 h exactas | `test_el_limite_es_exacto_a_las_24_horas` |
| Un éxito con fecha futura mantiene abierta la demo | `test_un_exito_en_el_futuro_no_mantiene_la_demo_abierta` |
| Sin éxito conocido, abre | `test_sin_ningun_reinicio_exitoso_conocido_cierra` |
| Un fallo no levanta alerta | `test_un_fallo_sale_como_alerta_con_el_identificador_de_la_corrida` |
| La alerta no lleva el identificador de la corrida | ídem |
| Registro recorrido fuera de orden | `test_llama_a_los_purgadores_en_el_orden_del_registro` |
| La fila de un fallo declara `deleted=0` | `test_un_purgador_que_levanta_queda_en_el_registro...` |
| La fila guarda el mensaje del error | ídem |
| Registro vacío permitido | `test_un_registro_vacio_no_es_una_corrida_exitosa` |
| No se pasa el corte / no se pasa `dry_run` | `test_pasa_el_corte_y_el_ensayo_a_cada_purgador` |
| `ResetRun` acepta resultado que contradice sus filas | `test_una_corrida_no_puede_declararse_exitosa_con_un_purgador_caido` |
| `ResetRun` acepta relojes sin zona / terminar antes de empezar | `test_los_relojes_de_una_corrida_traen_zona_y_van_en_orden` |
| `ResetRun` acepta purgadores repetidos | `test_un_purgador_aparece_una_sola_vez` |
| `now` sin zona aceptado | `test_el_instante_sin_zona_se_rechaza` |
| Último éxito elegido por posición en la lista | `test_el_orden_de_la_lista_no_decide_cual_es_el_ultimo_exito` |
| Voz: no exige respaldo / los dos idiomas / transcripción | `test_una_voz_sin_un_bloque...`, `test_una_voz_sin_uno_de_los_dos_idiomas...`, `test_reporta_todas_las_faltas...` |
| No exige personas | `test_reporta_todas_las_faltas_y_no_la_primera` |
| No valida reglas (existencia, significado) | `test_una_carpeta_sin_dos_cosas...`, `test_un_conjunto_de_reglas_roto_se_nombra_por_archivo` |
| No valida el corpus / no busca la póliza de ejemplo | `test_reporta_todas_las_faltas...`, `test_una_poliza_de_ejemplo_que_no_esta_en_el_corpus_se_nombra` |
| No compara `policy_number` | `test_una_poliza_de_ejemplo_que_no_es_la_que_dice_ser_se_nombra` |
| El identificador no nombra la carpeta | `test_el_identificador_tiene_que_nombrar_la_carpeta` |
| No valida el esquema / carpeta sin `tenant.yaml` sin reportar | `test_una_carpeta_sin_dos_cosas...` |
| **La póliza de ejemplo se sale de su carpeta** | **Sobrevivió.** La prueba pasaba porque el archivo inexistente ya daba otra falta en el mismo campo. Se reescribió plantando un archivo existente fuera de `issued_policies`; ahora cae `test_una_poliza_de_ejemplo_no_puede_salirse_de_su_carpeta` |

## Decisiones que tomé y Miguel debería ver

1. **"Políticas" = el conjunto de reglas `rules/triage.yaml`**, validado en forma y en
   significado con `rules.loading.validate_ruleset`. Las políticas de cumplimiento
   (`config/compliance`) no son por aseguradora, así que no hay nada que validarles.
2. **Voz completa = transcripción + principal + respaldo, en es y en en.** El esquema las
   deja opcionales a propósito (una voz incompleta apaga la voz de una aseguradora ya
   viva, BR2.2), pero dar de alta una nueva sin voz no es aprovisionarla. Las tres
   aseguradoras reales pasan.
3. **Sin ningún reinicio exitoso conocido, las superficies cierran** (fail-closed). Es
   coherente con "no pude verificar ≠ no hay", pero tiene una consecuencia para la tanda
   2: **un despliegue nuevo no acepta casos hasta que corra un primer `demo:reset`
   exitoso**. Hay que correrlo al desplegar, o decidir otra línea base. No lo decidí yo.
4. **Un éxito con fecha posterior a `now` también cierra** (relojes en desacuerdo): un
   dato corrupto hacia el futuro mantendría la demo abierta para siempre.
5. **BR3.3 (lo abierto termina normalmente)** se cumple porque `accepts_new_cases` solo
   recibe el historial y `now`: no sabe de conversaciones abiertas, no puede cortarlas.
   Que quien la llame solo la use al **abrir** un caso nuevo es de la tanda 2, y no hay
   prueba de eso aquí (no hay quién la llame todavía).
6. **El reloj de 24 horas cuenta desde `finished_at` del último `succeeded`.** Un
   `partial` no cuenta.
7. **`ResetRun.failure` (singular, de `entities.md`) es `failures` y se deriva de las
   filas**: con dos purgadores caídos (el caso 7+2) un campo singular no cabe, y una
   segunda copia podría contradecirlas.
8. **Una fila de purgador caído lleva `deleted=None, kept=None`**, no cero: no se sabe
   cuánto borró. Guarda el **nombre del tipo** del error, nunca su mensaje.
9. **El reintento es volver a llamar `run_reset` con el registro completo.** Los
   purgadores borran lo anterior al corte, así que repetir no empeora (probado). No
   construí una ruta de "reintentar solo lo que falta": si la tanda 2 la quiere, una
   corrida de subconjunto que salga `succeeded` **reiniciaría el contador de 24 horas sin
   haber cubierto los nueve**, y esa corrida necesitaría su propio tipo.
10. **La alerta es un evento `demo_operations.reset_alert`** por el punto único de salida,
    con el identificador de la corrida. El canal real (a quién llega) es de la tanda 2 o
    de `infra`.
11. **Un registro de purgadores vacío levanta `EmptyRegistryError`** en vez de devolver una
    corrida `succeeded` sobre cero purgadores.

## Lo que no pude correr, y el entorno

- **Python 3.13.14** (de `uv`), con el lockfile tal cual. `mise run deps:install` /
  `models:install` **fallaron**: mise intenta bajar Python 3.13.15 de GitHub y el túnel lo
  rechaza (403). Corrí los comandos de `mise.toml` directamente:
  `uv sync --locked --project app/backend --all-groups --extra models`. Los modelos de
  spaCy sí bajaron por ese camino y las pruebas de redacción pasan.
- **No corrió `scripts/verify.sh`, `mise run cov` ni `tests/integration`**: necesitan la
  base en contenedor. Tampoco **`tests/unit/tenancy/`** (levanta una base con Docker, que
  no hay): `docker.errors.DockerException`. Es del entorno, no del código.
- Sí corrieron y quedaron en verde: `ruff format --check`, `ruff check`, `lint-imports`
  (36 contratos), `mypy`, `copy:check`, `content:check`, `schema:check`,
  `tenancy:literals`, `contracts:check` (equivalente a mano: regenerar y comprobar que no
  queda nada sin seguimiento fuera de los dos módulos de claves, que van en el commit),
  `prettier --check` de los generados y **2153 pruebas unitarias** sin `tests/unit/tenancy/`.
- Cobertura medida solo sobre `demo_operations`: 99 % (queda la rama defensiva de la voz
  cuando `voice` no es un mapa, que el esquema ya reporta). El **piso agregado del 80 %**
  de la suite no se midió aquí.

---

## La revisión local de la tanda 1

Escrita en la sesión local el 2026-09-30. Corrí las 54 pruebas de la unidad y **las once
compuertas baratas sin recortes**, y rompí tres reglas más. Las tres cayeron, y no hubo
que corregir ninguna prueba.

### Lo que la tanda hizo bien

- **La orquestación es pura de verdad**, no de nombre: recibe los purgadores, el reloj y
  el corte, y no abre sesión ni escribe una sola sentencia de borrado. Es lo que permite
  probar el camino del fallo con dobles en vez de rompiendo una base.
- **Un purgador que levanta no detiene a los siguientes ni se traga.** Queda en su fila
  con el tipo de su error y la corrida sigue. Las dos alternativas son peores y están
  escritas: detener deja sin borrar lo que sí se podía, y seguir sin rastro deja una
  corrida que parece limpia.
- **`accepts_new_cases` recibe el historial y elige ella la corrida**, en vez de recibir
  «la última». Es la diferencia entre una regla que se puede escribir mal desde fuera y
  una que no: atar el reloj al último intento no es expresable con esta firma.
- **El reloj en desacuerdo cierra.** Si el último reinicio exitoso es posterior a `now`,
  la función cierra en vez de abrir: un dato corrupto hacia el futuro mantendría la demo
  abierta para siempre. Eso no estaba en el diseño y es correcto.
- **El registro vacío es un error y no una corrida vacía.** Un `succeeded` sobre cero
  purgadores diría que la demo está limpia sin haber borrado nada.

### Las tres roturas propias

| Rotura | Qué se cayó |
| --- | --- |
| Llamar a los purgadores en orden inverso al del registro | 6 pruebas |
| Una corrida que no termina limpia no levanta alerta | `test_un_fallo_sale_como_alerta_con_el_identificador_de_la_corrida` |
| La validación devuelve solo la primera falta | 8 pruebas |

### Las cinco decisiones de la tanda, revisadas

Las cinco están bien. Una la comprobé en vez de darla por buena, porque parecía chocar
con una práctica afirmada:

**«Políticas» leídas como las reglas de la aseguradora.** La práctica del equipo dice que
las políticas de cumplimiento viven en la carpeta versionada de cada aseguradora, así que
parecía que la validación estaba mirando el archivo equivocado. No lo está: **la carpeta
no tiene sección de políticas de cumplimiento**, y la diferencia que existe —que la
agencia nunca cierra un siniestro y siempre deriva— se expresa como **una regla**
(`always: true`). El propio `tenant.yaml` de Knotwell lo dice con esas palabras: *«su
regla única es derivar al ajustador de la aseguradora emisora. Esa diferencia vive en su
configuración y en sus reglas»*. La lectura de la tanda era correcta.

### La decisión del primer despliegue

La tanda la planteó bien: **sin ningún reinicio exitoso conocido, las superficies
cierran**, así que un despliegue nuevo no aceptaría casos hasta que corra un primer
`demo:reset`.

**Se resuelve en el despliegue, no en la regla.** `accepts_new_cases` está bien como
está: cerrar cuando no se puede afirmar que la retención está acotada es lo correcto, y
la alternativa —tratar «ninguna corrida» como abierto— sería indistinguible de «el
reinicio lleva tres días sin correr», que es justo el caso que la regla existe para
atrapar.

Lo que falta es un paso del despliegue: **correr `demo:reset` como último paso**. Sobre
una base recién creada no hay nada que borrar, la corrida sale `succeeded` en milisegundos
y deja el reloj en marcha. Es una línea en el checklist del segundo día, y no una
excepción en una regla que protege datos de personas. Queda para la tanda 2, que es la que
construye el comando de verdad.

### Lo que queda dicho para la tanda 2

- **`accepts_new_cases` solo decide sobre lo nuevo.** Quien la llame tiene que usarla al
  abrir un caso, nunca para cortar una conversación viva (BR3.3). Está en su docstring y
  se comprueba cuando exista quien la llame.
- **El reintento vuelve a correr el registro completo.** Una corrida de subconjunto que
  saliera `succeeded` reiniciaría el contador sin haber cubierto los nueve purgadores.
