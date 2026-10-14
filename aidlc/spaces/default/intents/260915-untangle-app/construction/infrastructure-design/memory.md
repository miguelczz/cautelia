<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-09-20T20:10:00Z — U3: la unidad es `library` y no despliega nada, asi que `infrastructure-specification` y `monitoring-design` se declaran N/A con su razon en vez de inventarles contenido. Lo observable de esta unidad lo publica el reporte de evaluaciones, que es de U21.
2026-09-19T03:05:00Z — la revisión mostró que una fila de trazabilidad puede quedar en `OK` citando un mecanismo parecido pero distinto: los filtros de ruta deciden si la corrida se dispara, no qué entra en el cálculo de cobertura. Cuando el mecanismo que pide un criterio no es de esta etapa, la fila honesta es `N/A` con su dueño, no `OK` con la cita más cercana.
2026-09-19T02:50:00Z — "versión exacta de imagen, no etiqueta móvil" admitía dos lecturas (etiqueta precisa o huella de contenido); se llevó a Miguel como decisión porque solo la huella resiste una etiqueta reescrita, que es lo que movería la medición de los 15 minutos.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-09-20T20:10:00Z — U3: los modelos de spaCy NO se instalan con `python -m spacy download`, que es la forma que documentan spaCy y Presidio. Es una resolucion libre sin lockfile ni hash, y la practica afirmada exige instalacion reproducible que falle si el lockfile no coincide. Entran como dependencias fijadas por URL: ruedas de 40,3 MB y 31,9 MB publicadas como recursos de version.
2026-09-19T02:50:00Z — la etapa pide topología de red, dimensionamiento y estrategia de despliegue; U1 no se despliega, así que la especificación describe el entorno local y la tubería, y remite el despliegue al intent `infra` en lugar de inventarlo.
2026-09-19T02:50:00Z — los sensores de esta etapa se eligieron para infraestructura en la nube (CDK, IAM, VPC); aquí no hay ninguna, y se dice en el documento en vez de rellenar tablas vacías.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-09-20T20:10:00Z — U3: los modelos viven en un extra y no en el juego principal, comprobado en la herramienta (`--all-groups` no incluye extras). Cuesta un comando mas (`models:install`) y un modo de fallo nuevo que hubo que hacer legible; compra que el camino del clon al reporte no se descargue 72 MB y que NFR21 no empeore por esta unidad.
2026-09-19T02:50:00Z — la tubería levanta la misma definición de docker compose que la máquina de quien desarrolla: se paga medio minuto de arranque a cambio de que no existan dos descripciones de la base de datos que puedan separarse.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-09-20T20:10:00Z — U3: tres cifras quedan sin estimar a proposito y se miden en la primera corrida verde de la generacion de codigo: cuanto tarda cargar los dos modelos en memoria, cuanto cuesta de verdad la pasada de redaccion, y el efecto medido sobre el arranque en frio.
2026-09-19T02:50:00Z — Miguel preguntó si lo que hay que instalar es global o del proyecto; se respondió que `mise` y Docker son globales y todo lo demás vive dentro de la carpeta. Conviene que esa distinción quede en el README cuando U1 lo escriba.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->

## Interpretations

- 2026-09-20T16:26:05Z — U2: para una unidad de tipo `library` esta etapa produce dos artefactos en vez de cuatro. `infrastructure-specification` y `monitoring-design` los asigna `produces_kinds` a `service`, `ui` y `packaging`. Se declara en el propio documento y en la trazabilidad para que la ausencia no se lea como olvido; es la primera vez que el tipo de unidad recorta esta etapa.
- 2026-09-20T16:26:05Z — U2: la base de datos de las pruebas no se monta como contenedor de servicio del flujo sino con testcontainers desde la suite, porque el contrato C-10 ya lo fija textualmente. La razon de fondo es que asi hay un solo camino: lo que corre en la maquina de Miguel es lo mismo que corre en la tuberia, con el mismo rol y la misma imagen.

## Tradeoffs

- 2026-09-20T16:26:05Z — U2: se mantiene el camino "del clon al reporte" sin base de datos aunque eso signifique dos caminos de arranque distintos. La alternativa era mas facil de explicar y empeoraba de golpe una cifra publicada (NFR21) por algo que no es calidad del producto. Decision Q1 de Miguel.
- 2026-09-20T16:26:05Z — U2: el coste del contenedor en la corrida no se estima, se mide en la primera corrida verde y entra en el resumen de la generacion de codigo. Poner una estimacion al lado de metricas medidas seria exactamente lo que el proyecto declara que no hace.

## Interpretations

- 2026-09-20T23:40:00Z — U4: la unidad añade tres tareas y ninguna más, y el documento lista expresamente las siete comprobaciones que **ya existen** y cubren obligaciones suyas (aislamiento, migraciones, contratos generados, esquemas versionados, entorno, secretos, cobertura). Escribir esa lista es la mitad del valor del documento: duplicar una comprobación crea dos sitios donde arreglarla y uno donde olvidarla.
- 2026-09-20T23:40:00Z — U4: se escribe que el `downgrade()` de la revisión **borra las tablas del caso**. Es vuelta atrás de esquema, no de datos, y en esta demostración eso es lo correcto porque los datos son sintéticos o de visitante. Un paso de vuelta atrás cuyo alcance no está escrito se ejecuta un día creyendo que preserva algo.

## Deviations

- 2026-09-20T23:40:00Z — U4: la etapa produce `cicd-pipeline.md` y su trazabilidad, no los tres documentos de infraestructura. La unidad es de tipo `library` dentro del proceso único: no despliega, no añade servicio ni puerto, y `infrastructure-specification.md` y `monitoring-design.md` están asignados a otros tipos.

## Open questions

- 2026-09-20T23:40:00Z — U4, hallazgo del sensor de trazabilidad, real y pendiente de la compuerta: los documentos de `nfr-design` de esta unidad **no nombran ningún identificador `NFRx.y` en su prosa**; los objetivos solo aparecen en su `traceability.json`. Por eso el sensor de esta etapa no puede resolver los identificadores que declara y devuelve "NFR design artifacts contain no NFRx.y IDs". U3 sí los lleva inline (NFR11.3 y NFR11.4). Es además un defecto de lectura: el documento explica cuatro capas y nunca dice qué objetivo medible sostiene cada una. `nfr-design` quedó congelado por su revisión, así que la corrección se aplica en la compuerta de esa etapa, junto con el recuento de "siete operaciones".
- 2026-09-20T23:45:00Z — U4, hallazgo de la revisión, comprobado y real: escribí "Cuatro comprobaciones cubren obligaciones de esta unidad sin tarea nueva" y la tabla de debajo tiene **siete** filas, que es además lo que dice la decisión INF-U4-1 tres pantallas más abajo. Contadas con un comando. No se puede corregir ahora —el registrador rechaza un veredicto cuyos bytes cambiaron— así que viaja a la compuerta. **Es el cuarto recuento mal escrito del proyecto**, y el patrón ya es visible: escribo la cifra en el párrafo introductorio, después la tabla crece, y la cifra se queda atrás. La regla que funciona no es "contar con cuidado": es **escribir el párrafo introductorio al final**, cuando la tabla ya está cerrada, o no poner cifra en él. Conviene además que `scripts/check-artifacts.py` aprenda este caso: una cifra en prosa inmediatamente seguida de una tabla, comparada contra el número de filas de esa tabla.

## Interpretations

- 2026-09-21T04:40:00Z — U5: el contrato de importacion que ya existia, `sdk-solo-en-su-adaptador`, deja el paquete `untangle.providers` **entero** fuera de su lista de fuentes, asi que hoy el SDK de un proveedor se puede importar desde `ports.py` y desde `factory.py`. ADR-018 dice "solo dentro de su adaptador". No es un contrato roto --nunca hubo un adaptador-- pero si mas suelto de lo que el ADR pide, y `ports.py` es lo que ven seis unidades. U5 anade un contrato acotado que lo aprieta, con la misma forma que `tenancy` y `redaction` ya usan para sus fronteras internas.
- 2026-09-21T04:40:00Z — U5: el chequeo de "nadie emite un tramo por su cuenta" **no** necesita un tercer analisis estatico hermano de los de U3 y U4. Aquellos existen porque su tipo se borra en tiempo de ejecucion (`NewType`), asi que un `cast` o una anotacion con `type: ignore` no dejan rastro que un contrato de importacion pueda ver. Aqui no hay tipo que se borre: hay un import, y los imports son exactamente lo que `import-linter` mira. Distinguir los dos casos ahorro una tarea, un paso y un mecanismo.

## Deviations

- 2026-09-21T04:40:00Z — U5: es la primera unidad cuyo paso 6 del guion **no crece**. U2 encadeno tres comprobaciones ahi, U3 dos y U4 dos; U5 ninguna, porque sus obligaciones caen en contratos de importacion (paso 3), en el comprobador de tipos (paso 4) y en dos comprobaciones que ya existen y crecen por dentro. Se escribio la tabla completa de donde cae cada obligacion para que la ausencia no se lea como olvido.

## Tradeoffs

- 2026-09-21T04:40:00Z — U5: `spend:report` no entra en el guion de verificacion aunque produzca el valor real de una meta publicada. Una compuerta sobre el costo por caso sin linea base solo podria fallar por ruido; la comparacion contra la linea base versionada es trabajo de U21. Se acepta que la cifra se produzca a peticion y al publicar, no en cada empujon.

## Open questions

- 2026-09-21T04:40:00Z — U5: bajar la migracion de esta unidad borra el acumulado del presupuesto y el registro de gasto, que son justo lo que AC5.14.4 exige que sobreviva a todo. Es la primera unidad del proyecto en la que la vuelta atras del esquema y la del codigo dejan de ser la misma cosa. Queda escrito en `cicd-pipeline.md` con su alcance; si algun dia hay un entorno donde el acumulado signifique dinero de verdad, esa vuelta atras necesita un paso previo de exportacion.

- 2026-09-21T04:40:00Z — U5, hallazgo R-04 del revisor, comprobado y real y el que mas habria costado: decir que `rls:check` y `schema:check` "crecen por dentro" escondia que ese crecimiento es **codigo nuevo en archivos ajenos** --`rls_assertion.py` es de U2 y `schema_check.py` es de U1--, y ninguno de los dos aparecia en la tabla meticulosa de archivos que la unidad toca. Leccion: "el comando crece" no es lo mismo que "no cuesta codigo", y la tabla de archivos tocados tiene que incluir los ajenos, con su dueña al lado, o el plan de generacion de codigo nace corto.
- 2026-09-21T04:40:00Z — U5, hallazgos R-01 y R-02: dos superlativos falsos en la misma etapa ("solo U1 y U2 ofrecen mas, cinco cada una" y "la primera unidad en la que bajar la migracion y volver atras el codigo no son lo mismo"). El segundo tenia debajo una distincion verdadera --lo de U4 se regenera y el acumulado de U5 no-- que es mas util que el superlativo. Leccion reforzada: un superlativo es una cifra disfrazada; o se cuenta, o se cambia por la distincion concreta que se queria hacer.
- 2026-09-21T04:40:00Z — U5: la comprobacion propia que se corrio **antes** de despachar --cada comando citado por un control de la etapa anterior tiene que aparecer en alguna de las tres tablas del documento-- encontro dos huecos y los cerro antes de la revision. Los cuatro hallazgos que quedaron son de cosas que esa comprobacion no puede ver: copropiedad de contratos, superlativos y codigo en archivos ajenos. Ese es el reparto que se buscaba, y la comprobacion se repite en las unidades que faltan.
