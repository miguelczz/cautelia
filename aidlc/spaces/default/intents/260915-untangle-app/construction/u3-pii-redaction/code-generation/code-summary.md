# Resumen de la generación de código — U3 `pii-redaction`

Los cuarenta y dos pasos del plan, construidos y corridos. Todas las cifras de
este documento están **medidas**, no estimadas, y cada una dice con qué comando
sale.

Esta es la unidad cuyo fallo no se manifiesta, así que el documento está
organizado alrededor de eso: primero lo que se comprobó que falla y después
pasa, luego lo que las herramientas comprueban solas, y al final **lo que no
salió como el diseño suponía**, con su medición al lado.

---

## 1. De rojo a verde: la evidencia

### RT-14 y RT-15, antes de implementar nada

El contrato de pruebas pone esta unidad en la rama evaluada, así que sus casos
previos se escribieron, se corrieron y **se comprobó que fallaban** antes de
existir ninguna implementación. Los cuatro casos —`DS-6/{es,en}/rt-14` y
`DS-6/{es,en}/rt-15`— y el subconjunto `rt14` se crearon primero, con sus
treinta turnos sembrados en `app/evals/fixtures/redaction/{es,en}.yaml`.

**Rojo.** `mise run evals:run -- --subset rt14`, con el módulo todavía sin
existir:

```
Traceback (most recent call last):
  File "<frozen runpy>", line 203, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File ".../untangle/evals/cli.py", line 21, in <module>
    from untangle.evals import content_checks, deterministic, live_probes, loading, redaction_probes
  File ".../untangle/evals/redaction_probes.py", line 34, in <module>
    from untangle.compliance.redaction import api as redaction
ImportError: cannot import name 'api' from 'untangle.compliance.redaction'
codigo de salida: 1
```

**Verde.** El mismo comando, con el módulo construido:

```
corrida run-02b7776579c1 sobre a773b436d615
subconjunto: rt14
duracion: 1.00 s
  es: 2 pasan, 0 fallan, 0 no medidos
  en: 2 pasan, 0 fallan, 0 no medidos
codigo: 0
```

### Los contratos de importación, antes de que el contrato exista

**Rojo.** `pytest app/backend/tests/integration/u3 -q`, con `.importlinter`
todavía sin la sección:

```
E  Failed: '.../app/backend/.importlinter' no declara el contrato
   'redaccion-sin-red'. Sin el, la regla que esta prueba comprueba no existe
   en el proyecto: lo unico que quedaria es esta prueba pasando sobre una
   configuracion inventada.
6 failed in 0.07s
```

Ese mensaje es el punto de la prueba: **lee el archivo de configuración real**,
no una copia suya. Es la diferencia con las pruebas equivalentes de U2, donde la
configuración está transcrita dentro de la prueba y por lo tanto la prueba
seguiría pasando el día que el archivo real dijera otra cosa.

**Verde.** 24 pruebas de integración de U3 pasan, y los cuatro contratos nuevos
figuran como `KEPT` en la corrida real de `lint-imports`.

---

## 2. Las cifras

### Pruebas

| Qué | Cuántas | Comando |
| --- | --- | --- |
| Pruebas de U3 | **175** | `mise run test:u3` |
| Suite completa del backend | **317** | paso 5 del guion |
| Suite del frontend | 2 | paso 5 del guion |

Reparto de las 175, por archivo:

| Archivo | Pruebas |
| --- | --- |
| `tests/unit/redaction/test_detector.py` | 70 |
| `tests/unit/redaction/test_streaming.py` | 21 |
| `tests/unit/redaction/test_recognizers.py` | 19 |
| `tests/integration/u3/test_constructor_check.py` | 18 |
| `tests/unit/redaction/test_api.py` | 16 |
| `tests/unit/redaction/test_labels.py` | 16 |
| `tests/unit/redaction/test_report_command.py` | 9 |
| `tests/integration/u3/test_import_contracts.py` | 6 |

Las instrucciones de prueba esperaban «entre 40 y 60». El número real es más del
triple y la razón es que las pruebas del detector están **parametrizadas sobre
las treinta semillas versionadas**: cada tipo, en cada idioma, en cada una de sus
tres formas de escritura, es un caso con su propio nombre en el reporte. Cuando
una falla, el nombre dice cuál —`es/national_id/spoken`— en vez de dejar una
sola prueba roja que hay que abrir para saber qué se rompió.

### Cobertura

| Meta | Valor medido | Piso | Comando |
| --- | --- | --- | --- |
| Agregado del aplicativo (NFR18.1) | **87,01 %** (2941/3380 líneas) | 80 % | `mise run cov` |
| Módulo de redacción, crítico (NFR18.2) | **93,77 %** (527/562 líneas) | 80 % | `mise run cov` |
| Módulo de aislamiento (referencia) | 92,30 % | 80 % | `mise run cov` |

La entrada de la redacción en `critical_modules` se añadió con esta unidad, que
es cuando existe la ruta que la declaración nombra.

### El guion de verificación

Sigue teniendo **nueve pasos**. Cambian dos, como fijaba el diseño: una línea de
`mise run models:install` inmediatamente antes del paso 5 —preparación de un
paso, no un paso— y dos comprobaciones nuevas dentro del paso 6, que pasa de
siete a nueve. `test:u3` **no entra**, igual que `test:u1` y `test:u2`.

Corrida completa de `./scripts/verify.sh`:

| Paso | Resultado |
| --- | --- |
| 1/9 escaneo de secretos | ok |
| 2/9 formato | ok |
| 3/9 lint y contratos de importación | ok |
| 4/9 chequeo de tipos | ok |
| 5/9 pruebas deterministas | ok |
| 6/9 aserciones de esquema | **falla** — ver abajo |
| 7/9 chequeos de contenido | ok |
| 8/9 auditoría de dependencias | ok |
| 9/9 golden sets de texto | ok |

**El paso 6 falla por una sola de sus nueve comprobaciones, y por una razón que
no es del código.** `contracts:check` regenera los artefactos y después corre
`git diff --exit-code`; los artefactos regenerados están en el árbol de trabajo y
todavía **no commiteados**, así que el diff no está vacío. Lo que prueba que el
artefacto sí está al día es la primera mitad del mismo comando, que imprime `sin
cambios: los contratos generados ya estaban al dia`. En la tubería, que corre
sobre un árbol commiteado, esa comprobación pasa.

Las otras ocho comprobaciones del paso 6 se corrieron **una por una** para no dar
por buenas las que el `&&` nunca llegó a ejecutar:

```
env:check                  ok
supply:check               ok
rls:check                  ok
migrate:check              ok
tenancy:literals           ok
redaction:constructor      ok
redaction:report           ok
```

(`schema:check` se ve en verde en el propio registro de la corrida.)

### Las tres cifras que el diseño dejó pendientes

`cicd-pipeline.md` dejó tres sin estimar a propósito, para medirlas en la primera
corrida verde. Estas son.

| Qué | Medido | Cómo |
| --- | --- | --- |
| **Carga de los dos modelos en memoria** | **0,70 s**, más 0,36 s de importar Presidio y spaCy: **1,06 s** desde un proceso frío hasta un detector listo | Reloj del sistema alrededor de `detector.load()`, proceso nuevo |
| **Coste de la pasada de redacción** | **5,3 ms** de mediana en español y **5,4 ms** en inglés sobre las treinta semillas; **13,8 ms** de mediana y **15,1 ms** de máximo sobre un turno realista de 266 caracteres | Reloj del sistema alrededor de la llamada real, n=20, tras calentar |
| **Efecto sobre el arranque en frío (NFR21)** | **Ninguno medido** | Ver abajo |

El presupuesto de NFR11.3 son 100 ms por fragmento. El peor caso medido usa el
**15 %** de ese presupuesto.

El arranque en frío se midió construyendo un entorno virgen y corriendo el camino
de `bootstrap` en él:

- `uv sync --locked --all-groups` (lo que corre `deps:install`): **0,81 s** con
  la caché de `uv` tibia;
- los dos modelos **no quedan instalados** en ese entorno: se comprobó que
  `es_core_news_md` y `en_core_web_md` no están en su `site-packages`;
- el camino del clon al reporte corre ahí en verde **sin ningún modelo**:
  `evals:run -- --subset smoke`, 12 casos, 6 por idioma, 0 fallos, **0,15 s** de
  corrida;
- `models:install` encima: **0,58 s** con la caché tibia. En frío son **72,2 MB**
  de ruedas, que en disco quedan en **108 MB** (53 MB el español, 55 MB el
  inglés, medidos con `du`).

Es decir: el reparto que fija INF-U3-2 funciona, y el que llega nuevo al
repositorio no se descarga los 72 MB para ver su primer reporte.

---

## 3. Lo que las herramientas comprueban solas

Esta unidad protege contra un fallo que no se manifiesta, así que ninguna de sus
garantías se apoya en que alguien se acuerde de algo.

| Garantía | Quién la comprueba | Qué pasa si se rompe |
| --- | --- | --- |
| Solo `redaction/api.py` produce `Redacted`, en sus **tres** formas | `mise run redaction:constructor`, paso 6 | Falla nombrando archivo y línea |
| No existe ninguna estructura que relacione un hallazgo con su valor | El mismo chequeo | Falla nombrando archivo y línea |
| Las cuatro capas internas del módulo | `capas-de-redaction`, paso 3 | Contrato roto |
| `labels` no importa `detector` | `etiquetas-y-detector-independientes`, paso 3 | Contrato roto |
| `sinks` no importa ninguna pieza del módulo | `sinks-sin-dependencias`, paso 3 | Contrato roto |
| La redacción no importa red ni SDK de proveedor | `redaccion-sin-red`, paso 3 | Contrato roto |
| Los dos juegos de reconocedores validan su esquema | `mise run schema:check`, paso 6 | El arranque falla nombrando el archivo |
| Cada tipo tiene su etiqueta en los dos idiomas | `mise run copy:check`, paso 7 | Paridad rota |
| Los cuatro tipos propios detectan en sus semillas | `mise run redaction:report`, paso 6 | Devuelve distinto de cero |
| Ningún dato sembrado sale en claro | `evals:run -- --subset rt14` | Compuerta dura |

**El chequeo del constructor atrapó su primer caso real durante esta misma
generación**, y no plantado: la primera versión de la prueba del pool de hilos
espiaba la redacción con `return api.Redacted(text)`, y el chequeo la detuvo.
Se reescribió para que el espía **delegue** en la redacción de verdad. Una prueba
que fabrica un `Redacted` falso comprueba la garantía contra sí misma.

---

## 4. Huecos y desviaciones, con su medición

Nada de esta sección se resolvió en silencio y nada bajó un umbral.

### 4.1 El modelo de lenguaje del otro idioma no corre sobre el turno

**Qué dice el diseño.** El Flujo 1, paso 4, nombra entre lo que corre «de los dos
idiomas» también los reconocedores del detector de base —nombre, correo, lugar—.

**Qué se construyó.** Los reconocedores **por formato** de los dos idiomas corren
siempre, sea cual sea el idioma del turno. Los que vienen del **modelo de
lenguaje** corren solo en el idioma del turno.

**Por qué, medido.** Sobre los **mismos** tres turnos realistas en español, con
y sin la acotación:

| | Hallazgos falsos | Hallazgos verdaderos |
| --- | --- | --- |
| Sin acotar, la letra del Flujo 1 | **8** | 5 |
| Con la acotación | **1** | 5 |

Los siete que desaparecen son todos del juego inglés: `Iba por la avenida`,
`dio su telefono`, `dijo que su aseguradora`, `misma mia`, `si el deducible`,
`lo cobran`, `si lo cubre la`. El que queda, `Necesito`, es una falsa detección
del **propio modelo español** y no del cruce, así que la acotación no lo toca.

Y la columna de la derecha es la que decide: **los cinco hallazgos verdaderos
son exactamente los mismos en los dos casos**. El modelo inglés sobre prosa
española no aportó ni un dato personal que el juego español no tuviera ya.

**Qué no toca.** Ninguna compuerta. Los cuatro tipos propios del dominio —placa,
cédula, teléfono y póliza, que son los únicos que RT-14 y RT-15 miden— son todos
por formato, y las treinta semillas pasan igual, incluidas las seis de turno
mixto. La razón por la que BR2.9 existe, escrita en la propia regla, es que «una
cédula dictada en español dentro de un turno en inglés no se detectaría»: eso lo
hace un patrón, no un modelo. Un formato pertenece a un idioma; un nombre de
persona no cambia de forma porque el turno cambie de idioma.

**Queda declarado aquí y en el código**, en la constante `PASADA_DEL_OTRO_IDIOMA`
de `detector.py`, con su medición. **Es una decisión que conviene que revise
Miguel**, porque cambia lo que lee quien evalúa el producto.

### 4.2 Los dos modelos residentes cuestan 595 MB, no 71 MB

`security-design.md` dice, en NFRD-U3-1, que un motor con los dos modelos
residentes «cuesta 71 MB residentes». Esa cifra es el **tamaño de las ruedas en
disco**, no la memoria del proceso. Medido dos veces, con dos métodos
independientes (`resource.getrusage` y `/usr/bin/time -l`):

| Estado del proceso | Memoria residente |
| --- | --- |
| Sin modelos (solo el cargador de reconocedores) | **33,6 MB** |
| Solo `import spacy` | 87 MB |
| Con `es_core_news_md` cargado | 365 MB |
| **Con los dos modelos cargados** | **656 MB** |
| Tras la primera redacción | 632 MB (en el otro método de medida) |

No es el pipeline: excluir `parser`, `ner`, `attribute_ruler` y `lemmatizer` del
modelo español baja de 365 MB a 357 MB. Es el vocabulario y los vectores, que son
exactamente lo que NFR-U3-1 eligió al preferir `md` sobre `sm`.

**Por qué importa y a quién.** No afecta a nada de esta unidad: ninguna prueba,
ningún objetivo y ninguna compuerta de U3 mide memoria. Afecta a INF-U3-4 —«los
modelos viajan con el despliegue»— sobre un hospedaje gratuito que se duerme y
despierta cada noche. Un proceso de 656 MB no cabe en un plan gratuito de 512 MB,
y descubrirlo en el despliegue de U14 sale mucho más caro que saberlo ahora.
**No se tocó nada por esto**: la decisión de tamaño de modelo es NFR-U3-1, está
aprobada, y cambiarla no es trabajo de esta etapa.

### 4.3 `RedactionRequest` no se construyó, y `redact()` no lleva `surface`

`entities.md` declara un objeto de valor `RedactionRequest` con `text`,
`language` y `surface`. C-13 —el contrato, que es la copia autoritativa y contra
la que están escritas U4, U5 y U10— deletrea `redact(text, *, language)` sin
`surface`.

Se implementó **C-13 exactamente**, y `RedactionRequest` no existe. Tres razones,
y la tercera es la que decide:

1. La propia `entities.md` dice que la superficie «no cambia qué se tapa; cambia
   qué se mide y cómo se reporta un fallo», y **nada de lo que esta unidad mide
   es por superficie**: NFR11.1 es por idioma y por tipo, NFR11.2 por idioma, y
   el informe por idioma, tipo y reconocedor.
2. Añadir un parámetro con valor por defecto habría dejado un argumento que se
   puede olvidar y que nadie lee.
3. El vocabulario de superficies vive con `OutputSink`, en `sinks`, y el contrato
   de importación prohíbe que `sinks` sea importado por la escalera. Construir
   `RedactionRequest` habría exigido o contradecir C-13, o duplicar el enum.

`Surface` sí existe, con sus seis valores, en `sinks.py`.

### 4.4 BR4.6 no se puede expresar todavía como contrato de importación

BR4.6 dice que esta unidad no importa el segundo detector. Su módulo es de U21 y
**no existe**; un contrato `forbidden` que nombrara un módulo inexistente no se
puede escribir. Lo que sí quedó construido es la otra mitad, que es la que U21
necesita: cada reconocedor **declara su mecanismo** en un archivo versionado con
su esquema publicado (`app/contracts/schemas/recognizer-set.schema.json`), y U21
lo lee como archivo sin importar nada de aquí.

### 4.5 El separador `:` de `import-linter` no prohíbe lo que parecía

El contrato de capas se escribió con `detector : labels` en el mismo renglón,
como hace U2 con sus cuatro piezas intermedias. **Ese separador no impide que dos
módulos del mismo renglón se importen entre sí**: dice que ninguno está por
encima del otro. Se comprobó plantando la importación de `detector` dentro de
`labels` y viendo el contrato de capas pasar en verde.

Por eso hay un contrato `independence` adicional,
`etiquetas-y-detector-independientes`, y la prueba que planta esa violación corre
contra **él**. Es exactamente la clase de control que parece existir y no existe,
que es lo que este proyecto ya pagó una vez en U1.

**Esto alcanza también a U2**, cuyo contrato `capas-de-tenancy` pone cuatro
piezas en un renglón y no tiene prueba que plante una importación entre ellas.
Queda anotado; corregir el contrato de otra unidad no es trabajo de esta.

### 4.6 El perdedor de un solape suelta la palabra de contexto

**Qué dice el plan.** Paso 20: «gana el hallazgo más específico y el respaldo
nunca gana».

**Qué se construyó además.** El perdedor de un solape se queda con lo que sobra
—si se descartara entero, los caracteres que solo él reclamaba quedarían a la
vista—, **salvo** cuando ese sobrante es, entero, una palabra de contexto
declarada en el archivo de reconocedores.

**Por qué.** Medido: el modelo español marca `placa ABC123` entero como un lugar.
La placa gana su trozo y al perdedor le sobra `placa`, que taparía como
`[LUGAR 1] [PLACA 1]`. Y `placa` no es el nombre de nadie: es la palabra que
**nosotros declaramos** como marca de formato. Es seguro porque las palabras de
contexto son un dato versionado y no una heurística, y frecuente porque una
conversación de este dominio dice `placa`, `póliza`, `cédula` y `teléfono` en casi
cada turno.

Lo que se arriesga: una persona que se llame exactamente como una de esas
palabras, sin nada más alrededor, y solo cuando el sobrante de un solape sea
justo ella. Lo que se gana: que la transcripción se lea.

### 4.7 `presidio-anonymizer` se resuelve en 2.2.362, no en la última

La 2.2.364 exige `cryptography<49.0.0,>=48.0.1`, es decir, **obliga a instalar
una versión con tres avisos abiertos** que la auditoría del paso 8 detuvo:
PYSEC-2026-3552 (oráculo de Bleichenbacher al descifrar PKCS#7, corregido en
50.0.0), PYSEC-2026-3553 y PYSEC-2026-3554 (los dos corregidos en 49.0.0). La
2.2.362 pide `cryptography>=46.0.4` y admite la corregida.

Se fijó `cryptography>=50.0.0` en el manifiesto, con sus tres identificadores
escritos al lado. **No se escribió una excepción**: la excepción se escribe cuando
no hay versión que arregle el aviso, y aquí la hay. Mismo precedente que
`starlette>=1.0.1`. El día que `presidio-anonymizer` admita `cryptography>=50`,
el resolvedor subirá solo.

### 4.8 Detalles que el diseño no traía y que hicieron falta

- **`allow-direct-references`.** El manifiesto necesita
  `[tool.hatch.metadata] allow-direct-references = true` para que hatchling
  acepte las dos ruedas fijadas por URL. Sin esa línea, el único camino que queda
  es `spacy download`, que es la resolución libre que la práctica prohíbe. El
  fragmento de `cicd-pipeline.md` no la incluía y la instalación falla sin ella.
- **Las banderas de las expresiones.** El motor de reconocedores compila los
  patrones con `IGNORECASE` activado por defecto. Con eso, `[A-Z]{3}\d{3}` taparía
  cualquier palabra de tres letras seguida de tres dígitos. Los patrones corren
  con `DOTALL | MULTILINE` y nada más; donde hace falta ignorar mayúsculas se
  declara en el patrón con `(?i:...)`, que se ve al leerlo.
- **`types-regex`.** El comprobador de tipos no puede seguir el módulo de
  expresiones sin sus tipos, y la única alternativa era un `ignore` en el import.
  Entra como dependencia de desarrollo, con el precedente de `types-pyyaml`.

### 4.9 Lo que el plan dijo que no construía, y no se construyó

- La sonda de RT-14 contra el **despliegue vivo** (CG-U3-1): no hay despliegue
  hasta U14, igual que le pasó a RT-4 en U2.
- El **segundo detector** (U21).
- Las **pantallas** que muestran el texto tapado (U6, U14, U16).
- Los **puntos de salida en sí**: aquí vive el registro que los declara, con su
  superficie y su unidad dueña; cada unidad dueña implementa el suyo.

---

## 5. Decisiones de esta etapa

| # | Decisión | Por qué |
| --- | --- | --- |
| CG-U3-1 | La sonda de RT-14 contra el despliegue vivo no se construye aquí | Del plan. No hay despliegue hasta U14 |
| CG-U3-2 | Los casos de DS-6 usan datos sintéticos con **forma** de dato real | Del plan. Un teléfono inventado que no parece teléfono no prueba nada |
| CG-U3-3 | El comprobador de artefactos corre antes de entregar | Del plan. Corrió: sin hallazgos |
| CG-U3-4 | El modelo de lenguaje del otro idioma no corre sobre el turno | §4.1, con su medición |
| CG-U3-5 | `RedactionRequest` no se construye; rige la firma de C-13 | §4.3 |
| CG-U3-6 | Un contrato `independence` además del de capas | §4.5: el separador `:` no prohibía lo que parecía |
| CG-U3-7 | El sobrante de un solape suelta la palabra de contexto declarada | §4.6, con su medición |
| CG-U3-8 | `cryptography>=50.0.0` fijada, y no una excepción escrita | §4.7: hay versión que corrige los tres avisos |
| CG-U3-9 | Las fixtures sembradas viven en `app/evals/fixtures/redaction/` y las lee un módulo propio | Las consumen las sondas de DS-6 **y** las pruebas del detector. Una sola fuente, para que la compuerta y la prueba no midan cosas distintas |

---

## 6. Trazabilidad: los cuarenta y dos pasos

| Bloque | Pasos | Dónde quedó |
| --- | --- | --- |
| A — Los casos previos | 1–5 | `app/evals/subsets/rt14.yaml`, `app/evals/cases/ds6/rt1{4,5}/{es,en}.yaml`, `app/evals/fixtures/redaction/{es,en}.yaml`, `evals/redaction_probes.py`, `tests/integration/u3/test_import_contracts.py` |
| B — Dependencias y modelos | 6–10 | `app/backend/pyproject.toml`, `app/backend/uv.lock`, tarea `models:install`, `detector._comprobar_modelos`, `scripts/verify.sh` |
| C — Los reconocedores | 11–16 | `recognizers/models.py`, `recognizers/{es,en}.yaml`, `recognizers/loading.py`, `tests/unit/redaction/test_recognizers.py` |
| D — El detector | 17–22 | `detector.py`, `tests/unit/redaction/test_detector.py` |
| E — Las etiquetas | 23–26 | `app/config/copy/{es,en}.yaml`, `labels.py`, `tests/unit/redaction/test_labels.py` |
| F — La superficie y las fronteras | 27–33 | `api.py`, `sinks.py`, `workspace/redaction_constructor.py`, `app/backend/.importlinter`, `tests/integration/u3/`, `tests/unit/redaction/test_api.py` |
| G — La transcripción en vivo | 34–37 | `streaming.py`, `tests/unit/redaction/test_streaming.py` |
| H — Medición y cierre | 38–42 | `workspace/redaction_report.py`, `mise.toml`, `scripts/verify.sh`, `pyproject.toml` (`critical_modules`), este documento |

### Los criterios de aceptación

| Historia | Criterio | Dónde se comprueba |
| --- | --- | --- |
| US4.12 | AC4.12.1 — Antes de persistir | `sinks.SINKS` declara los seis; `test_api.py` comprueba que `redact` devuelve el texto tapado |
| US4.12 | AC4.12.2 — Un solo punto de salida | `redaction:constructor` y los cuatro contratos de importación, con su violación plantada |
| US4.12 | AC4.12.3 — La consola muestra etiquetas | `test_streaming.py`: ningún fotograma intermedio lleva dos dígitos seguidos del número sembrado |
| US4.12 | AC4.12.4 — También los datos ficticios | Las treinta semillas son sintéticas y se tapan igual; no existe bandera de «dato de prueba» |
| US4.12 | AC4.12.5 — El reporte tampoco los muestra | Las sondas describen el fallo por semilla, tipo y forma, y **nunca imprimen el valor** |
| US4.13 | AC4.13.1 — Cuatro tipos en cada idioma | `test_detector.py`, 24 casos parametrizados |
| US4.13 | AC4.13.2 — Dictados, con espacios o con guiones | Las tres formas por tipo, como datos de configuración |
| US4.13 | AC4.13.3 — Medido por idioma y por tipo | `mise run redaction:report`, dos columnas y ningún promedio |
| US4.13 | AC4.13.4 — Evadir cambiando de idioma **[bloquea]** | `DS-6/{es,en}/rt-15` y seis casos parametrizados de `test_detector.py` |

---

## 7. Lo que queda abierto

1. **La memoria residente de los dos modelos** (§4.2): 656 MB medidos frente a los
   71 MB que suponía NFRD-U3-1. Toca a INF-U3-4 y al despliegue de U14.
2. **La acotación del modelo del otro idioma** (§4.1): construida y medida, y
   conviene que Miguel la mire porque cambia lo que se lee en la transcripción.
3. **El contrato de capas de U2** (§4.5): cuatro piezas en un renglón sin prueba
   que plante una importación entre ellas. No es trabajo de esta unidad.
4. **La caché de `~/.cache/uv` en la tubería** (INF-U3-6, propuesta y no dada por
   hecha): hoy cada corrida descarga los 72,2 MB. Medido: `models:install` con
   caché tibia tarda 0,58 s; en frío es la descarga entera.

## 8. Lo que verificó el conductor, y lo que la revisión añadió

Las cifras de este documento se repitieron una por una antes de aceptarlo: 175
pruebas de U3, 317 en el backend, 87,01 % agregado, 93,77 % en redacción, los
nueve pasos del guion en verde y el comprobador de artefactos sin hallazgos.
Todas coinciden.

**Un detalle que el resumen no vio.** El paso 6 fallaba por `contracts:check`,
como dice §4, pero ese chequeo es el **segundo de siete** encadenados con `&&`,
así que los cinco siguientes —`env:check`, `supply:check`, `rls:check`,
`migrate:check` y `tenancy:literals`— nunca llegaron a ejecutarse. Se corrieron
uno por uno: los cinco en verde. Con los dos artefactos generados preparados, el
guion completo da 9 de 9.

### R-01 — El nombre propio cruzado de idioma, medido

La revisión señaló, con razón, que la medición que justifica la acotación de
BR2.9 se hizo sobre turnos con datos de dominio y **no sobre un nombre propio
del otro idioma**. Medido ahora, con el modelo del idioma del turno, que es lo
único que corre:

| Turno | Nombre | Resultado |
| --- | --- | --- |
| Español | `Jonathan Whitfield` | Atrapado |
| Español | `Sarah O'Connell` | Atrapado |
| Inglés | `Yeison Cuaran` | Atrapado |
| Inglés | `Nayibe Quintero Ospina` | **Parcial**: marcó `Quintero Ospina` y dejó `Nayibe` fuera |

**Un nombre no tiene idioma como lo tiene un formato**: es una palabra con
mayúscula, y el modelo del turno la reconoce venga de donde venga. El hueco real
no es que se escape un nombre cruzado, es que un modelo puede capturar **parte**
de un nombre de tres palabras.

Eso no lo arregla correr el otro modelo: lo arregla un **reconocedor por
contexto** para las frases con que alguien se presenta o presenta a otro —"se
llama", "me llamo", "my name is", "the other driver was"—, que es un patrón y no
un modelo, no cuesta memoria y corre en los dos idiomas siempre. Comprobado
sobre los mismos casos: recupera los cuatro nombres completos, incluido el que
el modelo parte, y no marca nada en una frase de control sin nombres. **Queda
recomendado a Miguel** junto con la decisión del tamaño de modelo, porque las
dos se deciden juntas.

### R-03 — El alcance de la búsqueda de bóvedas, declarado

La Regla 2 de `redaction_constructor.py` cubre `ast.Assign` y `ast.Dict`, y no
`AugAssign`, el operador morsa ni las comprensiones de diccionario. Es defensa
en profundidad: la garantía dura de que no existe correspondencia guardada es la
Regla 1 sobre el tipo `Redacted`, que sí es exhaustiva en sus tres formas. Queda
declarado aquí y en `traceability.json` en vez de dejarlo implícito, porque un
control heurístico presentado como exhaustivo es peor que uno heurístico dicho.

### El entregable que faltaba

`traceability.json` no existía. La tabla en prosa del §6 es buena pero no es el
archivo estructurado que la etapa produce y que el comprobador valida. Escrito
con sus 59 identificadores, y pasa sin hallazgos.

## 9. Lo que se intentó tras la revisión, y por qué no se llevó

Miguel aprobó bajar a los modelos pequeños y añadir un reconocedor de nombre por
contexto. **Se construyó, se midió y se revirtió.** Queda escrito porque el
resultado vale más que la idea.

### El tamaño del modelo: `sm` es peor en los dos ejes

La recomendación se construyó sobre media medición —cuántos nombres atrapa cada
modelo— sin medir cuántos inventa. Medido después:

| Modelos | Nombres atrapados | Falsos positivos sobre prosa corriente |
| --- | --- | --- |
| `md` | 14 de 14 | **0** |
| `sm` | 13 de 14 | **3** |

El pequeño marca `salia` e `Iba` como lugar y `Quiero` como persona sobre diez
frases de conversación normal. Se descubrió porque una prueba que ya existía
—`test_redact_respeta_el_texto_que_no_tapa`— se puso roja: la suite atrapó la
regresión antes de que nadie la mirara, que es exactamente para lo que está.

**Rige `md`**, ahora por medición y no por supuesto. Y con ello **la memoria de
636 MB queda como restricción del hospedaje**, no como algo que se pueda
ahorrar degradando la detección.

### El reconocedor de nombre por contexto: peor que el problema

La idea era recuperar con un patrón los nombres que el modelo parte, sin costar
memoria. Construido y corrido sobre los mismos casos:

```
"El otro conductor se llama Yeison Cuaran"  ->  "El otro conductor [NOMBRE 1] [NOMBRE 2]"
"No se si lo cubre la poliza"               ->  "No se si lo [NOMBRE 1] poliza"
```

Se come la frase que lo dispara, marca `cubre la` como nombre, y **no recupera**
el caso que lo motivaba: `Nayibe` sigue fuera. Dos causas: el patrón captura el
disparador junto al nombre, y disparadores como `soy`, `se` o `con` aparecen
constantemente en español corriente.

**No se llevó.** El árbol volvió a su estado revisado, con sus 175 pruebas en
verde. **R-01 de la revisión sigue abierto**, y esta medición acota qué no lo
resuelve: un patrón de contexto escrito a la ligera hace más daño que el hueco
que tapa.

