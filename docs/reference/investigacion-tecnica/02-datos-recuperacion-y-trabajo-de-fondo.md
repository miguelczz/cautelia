# Investigación 2: datos, recuperación, grafos, trabajo de fondo, caché y transporte

- **Fecha:** 2026-09-17
- **Alcance:** preguntas 1 a 7 del encargo. No cubre runtime de IA ni orquestación, seguridad y evals, ni arquitectura del repositorio (los ven otras investigaciones), salvo donde un hallazgo de datos las toca.
- **Postura:** se cuestiona el diseño aprobado (ADR-004, ADR-010, ADR-011, ADR-012 y ADR-015 en `aidlc/spaces/default/intents/260915-untangle-app/inception/domain-design/decisions.md`), no se confirma.
- **Método:** documentación oficial, código fuente, notas de versión, artículos con metodología y el índice JSON de PyPI consultado el 2026-09-17. Cada afirmación lleva su fuente `[S#]` (lista al final). Lo que no pude abrir o comprobar lleva la marca **(no verificado)**.
- **Límite de esta sesión:** el presupuesto de búsquedas web se agotó cerca del final. Las últimas comprobaciones se hicieron abriendo URL conocidas. Algunas cifras vienen solo de resúmenes de búsqueda y están marcadas.
- **Cifras propias:** los tamaños de corpus y las latencias sin fuente son **estimaciones no medidas**. Cada una propone cómo medirla.

---

## Resumen ejecutivo

1. **La recuperación híbrida en PostgreSQL sigue siendo la opción correcta, pero el ADR-010 debe cambiar en cuatro puntos.**
   - **Sin índice aproximado (HNSW) mientras el corpus sea pequeño:** con unos pocos miles de cláusulas, un recorrido exacto da recall perfecto y resultados deterministas, y evita la trampa de HNSW con filtros y RLS.
   - **Contexto estructural determinista antepuesto a cada cláusula.**
   - **Expansión por relaciones entre cláusulas,** con tablas relacionales y CTE recursivo.
   - **Desempate estable en la fusión (RRF).**
2. **Grafo de conocimiento: rechazar cualquier base de grafos o framework GraphRAG en el runtime.** Las relaciones que importan (endoso que modifica una exclusión, definición usada por una cláusula) las conoce el generador sintético y caben en dos tablas. La evidencia en QA legal no muestra una ganancia que pague el costo.
3. **Trabajo de fondo: mantener "sin broker", pero el ADR-004 está incompleto.**
   - No dice quién relanza el trabajo tras un reinicio ni cómo se evita ejecutarlo dos veces.
   - Tampoco considera que en varios hospedajes gratuitos el proceso se duerme, se reinicia en cualquier momento o se queda sin CPU fuera de una petición.
   - La solución es un arrendamiento sobre `NodeRun` con `FOR UPDATE SKIP LOCKED` y un barrido al arrancar. No hace falta una cola nueva.
4. **Caché: nada de Redis ni caché semántica.**
   - La caché de contexto de Gemini no aplica al plan gratuito.
   - Sí vale ordenar el prompt con prefijo estable y cachear embeddings de consultas curadas, nunca los de texto libre de visitantes.
5. **Límites de uso: contadores atómicos en PostgreSQL.** Hallazgo que afecta a una práctica afirmada: en Gemini los límites son **por proyecto, no por clave**, y los topes de gasto solo existen en el plan de pago, son mensuales y tardan unos 10 minutos en aplicarse. "Claves separadas por uso" no aísla nada si las claves comparten proyecto.
6. **Transporte: SSE para el chat y la bandeja.** FastAPI lo trae de forma nativa desde 0.135.0 (2026-03-01). LISTEN/NOTIFY y Redis pub/sub quedan diferidos.
7. **Acceso a datos: SQLAlchemy 2 asíncrono con psycopg 3 como único driver.**
   - El checkpointer de LangGraph exige psycopg 3.
   - Ese checkpointer trabaja en autocommit, así que la variable de aseguradora local a la transacción no lo cubre. Es evidencia directa para PA-3 y el ADR-012.

---

## 1. Recuperación

### Hallazgos

**1.1 pgvector está maduro, y a este tamaño no hace falta índice aproximado.**
- La versión vigente es 0.8.6 (2026-07-29). La línea 0.8 trae recorridos iterativos para consultas filtradas, `halfvec` y construcción paralela de HNSW. La 0.8.2 corrigió un desbordamiento en la construcción paralela de HNSW (CVE-2026-3172) [S1][S2][S3].
- El README dice que sin índice pgvector hace búsqueda exacta "which provides perfect recall", y que en tablas pequeñas un recorrido completo puede ser más rápido [S2].
- También recomienda, para consultas con `WHERE`, empezar por un índice B-tree sobre la columna del filtro: "This can provide fast, exact nearest neighbor search in many cases" [S2].
- **Tamaño estimado del corpus (no medido):**
  - 3 aseguradoras, unas 200 a 400 cláusulas por formulario con sus versiones, más las copias de Knotwell: unas 1.500 a 4.000 filas en total.
  - Tras el filtro por aseguradora (RLS) y por póliza emitida (formulario, versión y endosos vigentes), quedan unas 100 a 400 filas candidatas por consulta.
  - Con ese volumen, la distancia exacta sobre `vector(768)` debería costar unos pocos milisegundos. **Estimación, hay que medirla.**

**1.2 La trampa de HNSW con filtros y RLS es real, y a este tamaño basta con no crear el índice.**
- Con índices aproximados, el filtro se aplica *después* de recorrer el índice. Con el `hnsw.ef_search` por defecto (40) y un filtro que cumple el 10 % de las filas, "only 4 rows will match on average" [S2].
- La política RLS se comporta como un filtro más: el índice no sabe de aseguradoras. Con varias aseguradoras en la misma tabla, una consulta puede devolver menos de k cláusulas o ninguna [S2][S20].
- Los recorridos iterativos (`hnsw.iterative_scan = strict_order | relaxed_order`, con `hnsw.max_scan_tuples = 20000` por defecto) mitigan el problema, pero no garantizan k resultados [S2].
- Otro motivo propio del proyecto: las prácticas exigen **corridas de evals deterministas** (team.md, "Determinismo de la corrida").
  - Un índice aproximado tiene recall menor al 100 % por definición, y su resultado depende del grafo construido **(inferencia)**.
  - La búsqueda exacta elimina esa fuente de variación en DS-3.
- Detalle de almacenamiento: un `vector(768)` ocupa `4 * 768 + 8 = 3.080` bytes y un `halfvec(768)` ocupa 1.544 [S2].
  - El README advierte que el planificador no cuenta el almacenamiento fuera de línea (TOAST) y ofrece `ALTER TABLE ... ALTER COLUMN embedding SET STORAGE PLAIN` [S2].
  - A este tamaño es irrelevante. Queda anotado para cuando se mida el recorrido exacto.

**1.3 RLS y rendimiento de índices.**
- La documentación de PostgreSQL 18 dice que solo las funciones `leakproof` pueden evaluarse antes del chequeo de RLS [S20].
- Por eso, con RLS activo, un índice sobre un operador no `leakproof` puede quedar sin usar. Es el caso típico con índices GIN y GiST. **Que `@@` de tsvector esté afectado no lo comprobé contra el catálogo.**
- A este tamaño no importa: un recorrido secuencial de unos cientos de filas es barato.
- Sí importan dos reglas de rendimiento de políticas:
  - Envolver la lectura del tenant en `(select ...)` para que se evalúe una vez por sentencia (initPlan).
  - Indexar la columna del filtro [S19].

**1.4 Búsqueda léxica: `ts_rank` no es BM25, y las extensiones BM25 no encajan aquí.**
- PostgreSQL documenta que sus funciones de ranking "do not use any global information" (no hay IDF) [S10]. Aun así, para fragmentos cortos de una cláusula, el lado léxico solo aporta un *orden* a RRF. Sirve sobre todo para términos exactos: identificadores, "Parte D", "granizo", nombres de endosos.
- **ParadeDB `pg_search`:**
  - Licencia AGPL-3.0 o comercial [S8].
  - Neon lo marcó obsoleto para proyectos nuevos el 2026-03-19 y lo retira el **2026-09-21** [S4].
- **`pg_textsearch` (Tiger Data):**
  - v1.0 publicada el 2026-04-03 con licencia PostgreSQL [S6].
  - Solo PostgreSQL 17 y 18. No aparece en la lista de extensiones de Neon [S5][S7].
  - Su README advierte que, con RLS, **las estadísticas del corpus incluyen todas las filas indexadas**, lo que puede filtrar frecuencias de datos inaccesibles, y que en tablas particionadas el IDF es local a cada partición [S7].
  - En una tabla con tres aseguradoras, el ranking de una dependería del corpus de las otras. Eso rompe el espíritu de M9 y hace que los resultados cambien al agregar datos de otra aseguradora.
- **VectorChord-bm25:** no está en la lista de Neon [S5]. En Supabase **no verificado**.
- **Español:** PostgreSQL trae la configuración `spanish` con Snowball. `unaccent` se integra creando una configuración propia que mapea `unaccent` antes del stemmer. La documentación trae el ejemplo con `french_stem` [S11].

**1.5 RRF sigue siendo la fusión razonable.**
- Cormack, Clarke y Büttcher (SIGIR 2009) muestran que RRF supera a los sistemas individuales y a Condorcet sin necesidad de entrenamiento [S12].
- Con dos listas y un corpus pequeño no hay datos para aprender pesos, así que RRF con k = 60 es la elección defendible.
- Para que la fusión sea reproducible, el orden final necesita un desempate estable, por ejemplo `ORDER BY score DESC, clause_id` **(recomendación propia)**.

**1.6 Recuperación contextual (Anthropic): conviene la idea, no su implementación con LLM.**
- Anthropic (2024-09-19) midió con qué frecuencia la cláusula correcta queda fuera de las 20 primeras recuperadas [S13]:
  - Embeddings contextuales la reducen un 35 %.
  - Añadir BM25 contextual la reduce un 49 %.
  - Con reordenamiento, un 67 %.
  - Generar el contexto con un LLM cuesta unos 1,02 USD por millón de tokens de documento, con caché de prompts.
- El mismo artículo dice que con una base de conocimiento de menos de 200.000 tokens "you can just include the entire knowledge base in the prompt" [S13].
- Sus conjuntos de datos no son pólizas. La mejora no se puede trasladar tal cual.
- En Untangle el contexto de cada cláusula **ya se conoce**, porque el corpus es sintético y estructurado (ADR-016): aseguradora, formulario y versión, parte, título de sección, tipo de cláusula, términos definidos que usa y endoso que la modifica.
- Anteponer ese encabezado al texto que se embebe y al que se indexa en FTS reproduce la técnica sin costo, sin llamadas al modelo y de forma determinista.

**1.7 Reordenadores: ninguno encaja hoy sin una señal medida que lo justifique.**

| Opción | Estado verificado | Encaje en Untangle |
| --- | --- | --- |
| Local, `BAAI/bge-reranker-v2-m3` | 0.6B parámetros, multilingüe, Apache-2.0 [S14] | Un modelo de 0,6B no cabe con holgura en la RAM de una instancia gratuita, y en CPU compite con el turno de voz (ADR-004). Rechazar. |
| Cohere Rerank con clave de prueba | 10 peticiones por minuto y 1.000 llamadas al mes con la clave de prueba [S15]. Las claves de prueba son de evaluación, no de producción (según su documentación). | La demo pública es producción a efectos de esos términos. Rechazar. |
| Voyage `rerank-2.5` o `rerank-3` | 0,05 USD por millón de tokens, con 200 millones gratis por cuenta [S16]. Límites sin método de pago: **no verificado**. | Suma un tercero que recibe texto del chat público. project.md exige revisar sus condiciones de uso de datos antes. Diferir. |
| Ranking API de Vertex AI | 1 USD por cada 1.000 consultas de hasta 100 documentos **(no verificado: solo resumen de búsqueda)** [S17] | Exige facturación en GCP. Diferir. |
| El propio `gemini-3.1-flash-lite` como reordenador | Sin costo extra en el plan gratuito, pero es una llamada más en el ritmo de fondo | Solo si DS-3 lo pide. Diferir. |

Un reordenador sube la **precisión** en los primeros k, pero no el recall del conjunto candidato. Solo se justifica si DS-3 muestra que la cláusula correcta está en el top-20 pero cae fuera del top-k que se entrega al modelo.

**1.8 Embeddings: dos detalles operativos.**
- Con `gemini-embedding-001` y dimensiones distintas de 3072 hay que **normalizar a mano** [S18].
  - Con distancia coseno (`<=>`) la normalización no cambia el orden.
  - Con producto interno (`<#>`) sí es obligatoria.
- `gemini-embedding-001` admite `task_type`. La ingesta debe usar `RETRIEVAL_DOCUMENT` y la consulta `RETRIEVAL_QUERY` [S18].
- Ya existe `gemini-embedding-2`, que no admite `task_type` y cuyo espacio es **incompatible** con el de 001 [S18]. Cambiar de modelo obliga a reindexar, cosa que el ADR-010 ya prevé. La elección de modelo corresponde a la investigación de runtime de IA.

**1.9 Cómo se mide la recuperación.**
- El PRD fija "la cláusula correcta está entre las recuperadas", recall en DS-3 ≥ 95 % (PRD 11.2).
- Con 20 preguntas por idioma, cada caso mueve 5 puntos (team.md). Hay que reportar conteos por caso, no solo porcentajes.
- Métricas recomendadas, todas calculables en pocas líneas dentro del corredor de evals:
  - **Recall@k** con k ∈ {5, 10, 20}, por idioma y por tipo de pregunta.
  - **MRR**: en qué posición aparece la primera cláusula correcta.
  - **Cierre@k**: fracción de las cláusulas modificadoras que la respuesta necesita (endosos que reabren o restringen, definiciones) y que están en el contexto entregado. Métrica propia, ligada a la sección 2.
  - **Intrusión de distractores@k**: cláusulas de otra versión del formulario en el top-k. Las de otra aseguradora deben ser **cero por construcción**; si aparece una, es un fallo de aislamiento y no de ranking.
  - **Subconjunto entre idiomas**: preguntas en un idioma sobre una póliza escrita en el otro, reportado aparte. El ADR-010 reconoce que ahí solo trabaja el lado vectorial.
  - **Ablación** en cada corrida de hito: solo léxico, solo vectorial, híbrido, e híbrido más cierre. Con el corpus ya embebido y las consultas de DS-3 cacheadas (sección 4), la ablación no gasta cuota.
- `ranx` implementa estas métricas y la fusión (ECIR 2022) [S22]. Su última versión es 0.3.21, de 2025-08-07 [S34]. Para 40 preguntas no compensa la dependencia (usa Numba).
- **Línea base de contexto largo (opcional, por hito):**
  - La póliza emitida de un caso completa (formulario más endosos vigentes) probablemente ocupa decenas de miles de tokens **(estimación)**.
  - Anthropic sugiere meter la base entera cuando es menor de 200.000 tokens [S13].
  - Comparar "póliza completa en contexto" contra la recuperación híbrida en DS-3 muestra si la recuperación aporta algo más que ahorro de tokens.
  - No debe sustituir la recuperación en el runtime: M4 exige recuperación híbrida con distractores, el verificador depende del "conjunto recuperado" y el costo por pregunta se multiplica.

### Recomendación

**Adoptar en el runtime, como enmienda del ADR-010:**

1. **Tabla de cláusulas sin índice aproximado.**
   - Índice B-tree sobre `(tenant_id, form_id, form_version)` y la clave de cláusula.
   - La búsqueda vectorial es exacta (`ORDER BY embedding <=> $q LIMIT 50`) dentro del conjunto filtrado.
   - **Umbral para reabrir la decisión:** p95 de la subconsulta vectorial mayor que 20 ms en `EXPLAIN (ANALYZE, BUFFERS)` con el corpus sembrado, o más de 50.000 filas por aseguradora **(umbrales propios, a fijar en NFR)**.
   - Si se reabre:
     - HNSW **parcial por aseguradora**, que el README sugiere para pocos valores distintos [S2].
     - `hnsw.iterative_scan = strict_order` para no perder el orden.
     - Una prueba que compare el resultado aproximado con el exacto, como indica el propio README: "Monitor recall by comparing results from approximate search with exact search" [S2].
2. **FTS por idioma de la fila.**
   - Columna `fts_config regconfig` con `tsvector` generado mediante `to_tsvector(fts_config, texto_con_encabezado)`.
   - Configuración propia con `unaccent` más stemmer español o inglés [S11].
   - Consulta con `websearch_to_tsquery` en la configuración del documento.
3. **RRF con k = 60** sobre dos listas de hasta 50 elementos cada una, con desempate estable por `clause_id`.
4. **Encabezado estructural determinista** antepuesto al texto que se embebe y se indexa, generado por el mismo generador del ADR-016.
5. **Normalizar los vectores truncados a 768** y usar `task_type` diferenciado [S18].
6. **Fijar pgvector ≥ 0.8.2**, y preferir 0.8.6 [S1]. En el proveedor gestionado, elegir la versión de PostgreSQL que traiga la más reciente. Neon ofrece de 0.8.0 a 0.8.6 según la versión de PostgreSQL [S5].

**Rechazar y documentarlo en el ADR-010:** extensiones BM25 (ParadeDB, `pg_textsearch`, VectorChord-bm25), reordenador local y recuperación contextual generada por LLM.

**Diferir:** reordenador por API o por LLM, solo si DS-3 muestra la brecha descrita en 1.7. La línea base de contexto largo queda como experimento de hito.

---

## 2. Grafos de conocimiento

### Hallazgos

**2.1 La evidencia en QA legal no justifica GraphRAG para este caso.**
- **Ongris et al., RAGE-KG en ISWC 2025** [S23]: corpus legal multilingüe (directivas UE y reglamentos de Indonesia), GPT-4o-mini y la métrica de exactitud de respuesta de Ragas.
  - RAG ingenuo: exactitud media 0,82 y 86,51 % de respuestas buenas.
  - LightRAG Mix: 0,86 y 89,23 %.
  - LlamaIndex Hybrid: 0,85 y 85,31 %.
  - LlamaIndex solo con grafo de propiedades: 0,57 y 51,22 %.
  - Costo: indexar tomó 5,9 s con RAG ingenuo frente a 397 s con LightRAG, y cada consulta 1,76 s frente a 9,31 s de media.
  - Conclusión de los autores: los sistemas solo con grafo "often underperform", y los híbridos ganan poco a cambio de mucho más cómputo.
- **Han et al., "RAG vs. GraphRAG"** (arXiv 2502.11371, v3 2026-03-04) [S24]: fortalezas distintas según la tarea; recomiendan combinar en lugar de reemplazar.
- **"When to use Graphs in RAG"** (arXiv 2506.05690, revisado 2026-02-22) [S25]: "GraphRAG frequently underperforms vanilla RAG on many real-world tasks". Las ventajas aparecen en razonamiento jerárquico o profundo, no en recuperación de hechos.
- **Microsoft GraphRAG** [S27]: advierte que indexar "can be an expensive operation", y el propio repositorio se declara "largely in maintenance mode" y "not an officially supported Microsoft offering".

**2.2 Sí existe evidencia a favor de seguir referencias explícitas, que es otra cosa.**
- Ju y Lee, "Citation-Closure Retrieval" (arXiv 2605.29742, v2 2026-08-31) [S26]: en QA de cumplimiento normativo proponen recorrer citas entre documentos y cerrar el conjunto de evidencia, con atribución por regla.
- Reportan mejoras sustanciales de recall y de exactitud de citas. **Las cifras no aparecen en el resumen**.
- Es exactamente el problema de Untangle: una exclusión citada sin el endoso que la reabre produce una respuesta falsa con cita "verificada".
- Lo que ayuda es el **cierre por relaciones conocidas**, no la extracción de entidades por LLM.

**2.3 Costo operativo de las bases de grafos frente a las restricciones.**

| Opción | Estado verificado | Problema para Untangle |
| --- | --- | --- |
| Neo4j AuraDB Free | 50.000 nodos y 175.000 relaciones; se pausa tras 3 días de inactividad [S31] | Otro servicio y otro mecanismo de aislamiento sin RLS; la pausa rompe la demo. |
| FalkorDB Cloud Free | 100 MB de RAM, **sin TLS**, "no persistence and no backups", se detiene tras 1 día y se borra tras 7 de inactividad [S32]. Licencia SSPLv1 (según su documentación). | Inaceptable para cualquier dato. |
| Apache AGE | Soporta PG17 y prepara PG18. Los mantenedores dicen que tienen "limited resources" (2026-01-16) [S30]. No está en la lista de extensiones de Neon [S5]. | Requiere un Postgres donde se pueda instalar; interacción con RLS **no verificada**. |
| LightRAG sobre Postgres | Grafo sobre AGE; el aislamiento es un campo `workspace` en tablas o un prefijo en el grafo; hay issues abiertos sobre aislamiento por instancia y multi-tenant [S29] **(issues no leídos en detalle)** | El aislamiento sería lógico en código, justo lo que prohíbe el ADR-012 ("filtrar solo en el código"). |
| Microsoft GraphRAG / LazyGraphRAG | Indexación costosa y proyecto en mantenimiento [S27]. LazyGraphRAG reduce el costo de indexar **(blog no abierto)** [S28]. | Presupuesto de 5 USD; extracción por LLM no determinista. |

**2.4 Extraer el grafo con LLM es un riesgo específico para las citas.**
- Un grafo extraído por modelo introduce errores de relación en el camino que el verificador (ADR-011) debería volver infalible.
- En Untangle el generador sintético **crea** las relaciones, así que son la verdad de base: se versionan y se prueban.
- Un grafo inferido sería menos exacto que el que ya se tiene gratis.

### Recomendación

**Adoptar en el runtime una "recuperación consciente de la estructura", relacional:**

- **Tabla `clause_relation`:**
  - Columnas: `tenant_id`, `src_clause_id`, `dst_clause_id`, `rel_type` y `form_version`.
  - `rel_type` pertenece a un conjunto cerrado: `modifies_exclusion`, `reopens`, `restricts`, `replaces`, `defines_term_used_by`, `references`.
  - RLS igual que el resto, generada por el generador del ADR-016 junto al corpus.
- **Cierre tras RRF:**
  - Se expanden las semillas del top-k con un CTE recursivo de profundidad ≤ 2, con detección de ciclos (`CYCLE`, disponible desde PostgreSQL 14 [S33]).
  - La expansión queda restringida a los endosos **vigentes en la póliza emitida**.
  - El contexto se entrega anotado, por ejemplo "D.EXCL.7, modificada por END.SUN.03.2".
- **Enmienda del ADR-011, con decisión humana:**
  - Además de existencia, pertenencia y vigencia, el verificador comprueba que ninguna relación vigente modifica la cláusula citada sin que el modificador también esté citado o considerado.
  - Si no lo está, el resultado es `rejected`.
  - Es una regla por código, así que no depende del juez.
- **Medición:** métrica de cierre@k en DS-3 y casos del estilo del journey de Sunmeadow, con una cláusula de gastos de transporte modificada por un endoso (PRD línea 560).
- **Nombre honesto:** llamarlo "relaciones entre cláusulas" y no "GraphRAG" ni "knowledge graph". Quien evalúa y lee el ADR castiga el término de moda sin base de grafos real.

**Rechazar y documentarlo en un ADR:** Neo4j, FalkorDB, Apache AGE, LightRAG, Microsoft GraphRAG y LazyGraphRAG. Usar las razones de 2.1 a 2.4 y la tabla anterior.

---

## 3. Trabajo de fondo y durabilidad

### Hallazgos

**3.1 Lo que el ADR-004 no dice.** "Si el proceso muere, la reanudación relanza lo pendiente desde el punto de control" deja abiertas cuatro preguntas:

1. **Quién dispara el relanzamiento.** LangGraph persiste estado según el modo de durabilidad, pero no relanza hilos por sí mismo.
   - `sync` persiste antes del paso siguiente, `async` mientras se ejecuta y `exit` solo al salir [S37].
   - Con `exit` no hay recuperación a mitad de ejecución. Para el trabajo de fondo hay que fijar `sync` o `async` a propósito.
2. **Cómo se evita la doble ejecución** si hay reinicio, varias instancias o una tarea lenta que parece muerta. Esto cuenta doble porque un `SpendEntry` duplicado falsea el techo de gasto (ADR-015).
3. **Qué pasa con la tarea asíncrona en memoria.** Python advierte que el bucle de eventos guarda solo referencias débiles a las tareas: "A task that isn't referenced elsewhere may get garbage collected at any time, even before it's done". Además, las excepciones de tareas no esperadas se pierden, salvo con `TaskGroup` [S35].
4. **Cómo afecta el hospedaje gratuito:**
   - **Render gratuito:** se apaga tras 15 minutos sin tráfico entrante, tarda "about one minute" en volver y "Render might restart a Free web service at any time". Su Postgres gratuito **expira a los 30 días** [S46].
   - **Cloud Run con facturación por petición:** "CPU is only allocated during request processing". Una tarea asíncrona lanzada después de responder se queda sin CPU [S45].
   - **FastAPI `BackgroundTasks`:** corre en el mismo proceso después de responder, y la documentación remite a herramientas mayores para trabajo pesado [S36]. No aporta durabilidad.

**3.2 Opciones basadas en Postgres, sin servicio nuevo.**

| Opción | Versión (PyPI, 2026-09-17) [S34] | Qué aporta | Problema aquí |
| --- | --- | --- | --- |
| Procrastinate | 3.9.0 (2026-06-20) | Worker dentro del proceso con `run_worker_async(install_signal_handlers=False)` [S39]; detecta trabajos colgados por latido cada 10 s y los reintenta con una tarea periódica [S39]; LISTEN/NOTIFY con `SKIP LOCKED` | Esquema propio fuera del modelo del aplicativo, así que la aserción de RLS necesita una excepción documentada; LISTEN no pasa por poolers en modo transacción [S47]. |
| PgQueuer | 1.4.0 (2026-09-14) | asyncpg o psycopg, reintentos, cron, límites por punto de entrada, LISTEN/NOTIFY con respaldo por sondeo [S40] | Las mismas dos objeciones. |
| DBOS Transact | **3.0.0 publicada el 2026-09-16** | Flujos durables sobre Postgres que se reanudan solos al reiniciar, colas con concurrencia y límites [S41] | **Segundo modelo de durabilidad** encima de los checkpoints de LangGraph: dos sistemas de reanudación para el mismo caso. Versión mayor de hace un día. |
| Absurd (Earendil) | `absurd-sdk` 0.5.0 (2026-08-04) | Un único archivo SQL con procedimientos; unos 5 meses en producción según su autor; sin planificador ni particionado [S42] | Joven; mismo solapamiento con LangGraph. |
| pgmq | 1.1.3 (2026-08-18) | Cola estilo SQS; instalable solo con SQL [S44] | Es una primitiva de cola: faltan arrendamiento con latido y reintentos con semántica de trabajo. No está en Neon como extensión [S5]. |
| Hatchet | SDK 1.40.1 | Durabilidad completa | Exige un motor propio; Hatchet Lite es "designed for development and low-volume use-cases" [S43]. Es un servicio más. |
| Celery, RQ, arq, Taskiq, Dramatiq | 5.6.3 / 2.12.0 / 0.28.0 / 0.12.6 / 2.2.1 | Colas maduras | Broker Redis o RabbitMQ. El ADR-004 ya los rechaza con razón. |

**3.3 Lo que falta cabe en la tabla que ya existe.**
- `NodeRun` ya es un registro de dominio ligado a la traza. Añadirle un **arrendamiento** resuelve 3.1 sin dependencia nueva:
  - Columnas: `status`, `attempt`, `max_attempts`, `lease_owner`, `lease_expires_at`, `heartbeat_at`, `idempotency_key`, `last_error_type`.
  - Reclamo con `UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING`.
- Es el mismo patrón que usan Procrastinate y PgQueuer [S39][S40], sin sus esquemas y sin LISTEN.
- Mantiene **un solo modelo de durabilidad**: checkpoint de LangGraph más registro `NodeRun`.

### Recomendación

**Mantener sin broker** y enmendar el ADR-004 con este diseño, a detallar en Functional Design:

1. **Bandeja transaccional:** el `NodeRun` pendiente se inserta en la misma transacción que la actualización de estado que lo origina. Después se lanza la tarea en proceso por la vía rápida.
2. **Supervisor en proceso:** conjunto con referencias fuertes y *callback* que registra la excepción en el `NodeRun` [S35]. Concurrencia de fondo acotada con un semáforo para proteger el turno de voz; el valor sale del experimento 1.
3. **Arrendamiento con latido:** por ejemplo, arrendamiento de 60 s renovado cada 10 s **(valores propios, a fijar en NFR)**.
4. **Barrido al arrancar y periódico:**
   - Reclama `pending` y `running` con arrendamiento vencido y relanza desde el checkpoint del `thread_id`.
   - **Barrido por aseguradora:** fija el tenant, barre, pasa al siguiente. Así el barrido respeta RLS y no necesita un rol con `BYPASSRLS`.
5. **Idempotencia:**
   - `SpendEntry` con clave única `(node_run_id, attempt)`.
   - Durabilidad `sync` para los pasos de fondo cuyo resultado se entrega a la persona [S37].
6. **Agotamiento:**
   - Al superar `max_attempts`, el resultado es `unverifiable` (ADR-011) y el caso se deriva.
   - El fallo queda visible, lo que alimenta "Cómo falla".
7. **Apagado ordenado:** en el `lifespan` se deja de reclamar, se espera un margen y lo que no termina queda para el siguiente barrido.
8. **Trabajos programados:** el reinicio nocturno y el borrado de enlaces no pueden depender de un proceso que duerme [S46].
   - Opción A: disparador externo autenticado.
   - Opción B: "ponerse al día al despertar", ejecutándolo al arrancar si pasaron más de 24 h.
   - **Opciones de diseño no verificadas en esta sesión.** Las decide el intent `infra`.
9. **Prueba de "cómo falla":** matar el proceso con `SIGKILL` a mitad de un trabajo de fondo y comprobar que se relanza, que termina una sola vez y que el gasto no se duplica.

**Alternativa documentada:** Procrastinate con worker en proceso, si el código propio supera unas 200 líneas o aparecen trabajos periódicos que no quepan en el punto 8.

**Rechazar:** DBOS y Absurd (duplican la durabilidad de LangGraph), Hatchet y Temporal (servicio aparte), pgmq (primitiva insuficiente), y Celery, RQ, arq, Taskiq y Dramatiq (broker).

**Señales concretas que justificarían Redis más adelante** (cualquiera, medida y no supuesta):
1. **Más de una instancia o proceso** que comparte estado efímero caliente, y el chequeo de límites en Postgres aporta más de 5 a 10 ms al p95 del turno **(umbral propio)**.
2. **La voz se separa en un proceso o servicio propio** (resultado posible del ADR-009) que necesita leer estado de sesión con latencia submilisegundo, o la librería de voz elegida exige Redis para despachar entre workers **(no verificado para ninguna librería)**.
3. **Contención medible por LISTEN/NOTIFY.** Con muchos escritores concurrentes, `NOTIFY` toma un bloqueo global al hacer commit: fue la causa de las caídas de Recall.ai en 2025 **(artículo no abierto; resumen de búsqueda)** [S62]. A la escala de la demo no aplica.
4. **Las horas de cómputo del Postgres gratuito se agotan** porque los contadores de alta frecuencia mantienen despierta la base (sección 7). Mover solo los contadores a un Redis gratuito podría ser más barato. Upstash gratuito: 500.000 comandos al mes y 256 MB, con posible limitación al excederse [S70].
5. **Rendimiento de la cola:** trabajos de fondo sostenidos que `SKIP LOCKED` con sondeo no despacha dentro del presupuesto de latencia de NFR.

---

## 4. Caché

### Hallazgos

**4.1 La caché de contexto de Gemini no rinde en este proyecto.**
- `gemini-3.1-flash-lite` es estable desde mayo de 2026 y admite caché [S69].
- En el **plan gratuito** la caché de contexto figura como "Not available" [S68]. El chat público corre en ese plan (ADR-006), así que no ahorra nada ahí.
- En el plan de pago [S68]:
  - Entrada: 0,25 USD por millón de tokens de texto; salida: 1,50 USD.
  - Tokens en caché: 0,025 USD por millón.
  - Almacenamiento de caché explícita: 1,00 USD por millón de tokens **por hora**.
- La caché implícita está activa por defecto desde Gemini 2.5 [S67].
  - El mínimo de tokens es 4.096 para los Flash 3.5 a 3.8 y 3.1 Pro, y 2.048 para 2.5 [S67].
  - **Flash-Lite no aparece en esa tabla (no verificado)**.
  - Consejo oficial: poner el contenido grande y común al principio y enviar peticiones con el mismo prefijo en poco tiempo [S67].
- Un prompt de sistema con catálogo y unas pocas cláusulas probablemente queda por debajo de 4.096 tokens **(estimación)**.
- Con tráfico esporádico de demo, la caché explícita pagaría almacenamiento por hora sin aciertos que lo compensen.

**4.2 La caché semántica de respuestas es peligrosa para este producto.**
- Una caché por similitud devuelve la respuesta de otra pregunta "parecida". En Untangle, dos preguntas casi idénticas pueden tener respuestas opuestas según la aseguradora, la versión del formulario o un endoso vigente.
- Además, esa respuesta saltaría el verificador de citas (ADR-011).
- Hay trabajos que muestran colisiones adversariales de clave en cachés semánticas **(arXiv 2601.23088, resumen de búsqueda, no abierto)** [S71].

**4.3 Los embeddings también son datos personales.**
- Morris et al. (EMNLP 2023) recuperan exactamente el 92 % de textos de 32 tokens a partir de su embedding, y extraen nombres completos de notas clínicas [S72].
- Cachear el embedding de un mensaje libre de un visitante equivale a guardar el mensaje.

### Recomendación

- **Adoptar en el runtime, sin infraestructura:**
  - **Prefijo estable en los prompts:** instrucciones y catálogo primero, datos del caso al final. Registrar en la traza los tokens cacheados que devuelva la respuesta [S67]. En el plan gratuito no ahorra, pero en el de pago lo hace sin trabajo extra.
  - **Caché de embeddings de consulta en PostgreSQL** con clave `(model_id, dims, task_type, sha256(texto_normalizado))`, **solo** para textos curados: preguntas de DS-3 y DS-2, preguntas sugeridas de la interfaz y el corpus.
    - Ahorra cuota diaria del plan gratuito en cada corrida de CI.
    - Estabiliza la corrida.
    - El reporte de evals debe indicar qué consultas vinieron de caché, para que una caída del proveedor no quede oculta.
  - **Caché en memoria del proceso** para la configuración por aseguradora y los metadatos del corpus, que son inmutables por despliegue.
- **Rechazar y documentarlo:**
  - Redis como caché o almacén de sesión: la sesión es la cookie firmada más el checkpoint de LangGraph (ADR-003 y ADR-012).
  - Caché semántica de respuestas.
  - Caché explícita de Gemini.
  - Persistir embeddings de mensajes libres de visitantes.
- **Diferir:** revisar la caché implícita si NFR o los datos de latencia muestran prompts de voz por encima de 4.096 tokens en el plan de pago.

---

## 5. Límites de uso en superficies públicas

### Hallazgos

**5.1 Las bibliotecas habituales no tienen almacenamiento en Postgres.**
- `limits` soporta memoria, Memcached, Redis (con Sentinel y Cluster), MongoDB y Valkey. **No hay backend SQL** [S63].
- `slowapi` 0.1.10 (2026-06-13) [S34]:
  - Exige declarar `request` en cada endpoint.
  - No soporta WebSocket.
  - Con almacenamiento en memoria, cada proceso lleva sus propios contadores [S64].
- **En memoria no sirve como límite diario:** Render puede reiniciar el servicio "at any time" [S46], y un reinicio pone los contadores a cero. El límite por día quedaría abierto.

**5.2 Los límites del proveedor no funcionan como se asumió.**
- **Gemini aplica los límites por proyecto:** "Rate limits are applied per project, not per API key". La cuota diaria se reinicia a medianoche del Pacífico [S65].
  - La práctica afirmada de "claves separadas por uso (voz, chat, evals)" **no separa cuotas** si las claves viven en el mismo proyecto.
  - Hacen falta **proyectos separados por uso**.
- **Topes de gasto de Gemini:** se anunciaron el 2026-03-16 **(blog, resumen de búsqueda)** [S66].
  - Son **mensuales** y solo para proyectos de pago.
  - Tienen una latencia de unos 10 minutos durante la cual se cobra el exceso [S66].
  - No pueden expresar el techo acumulado de 5 USD en 90 días (project.md, decisión D11). El techo sigue siendo responsabilidad del aplicativo (ADR-015), y el tope del proveedor es solo una segunda red.
- **Un proyecto del plan gratuito sin facturación es el tope más fuerte:** no puede generar cargos. Es coherente con el chat en plan gratuito del ADR-006 **(inferencia desde [S68], que no lista cobro en el plan gratuito)**.
- **Deepgram:** el presupuesto sería por organización, no por clave **(fuente de terceros, no verificado)**.
- **Cartesia:** tope por clave **no verificado**.

### Recomendación

**Adoptar en el runtime contadores en PostgreSQL:**
- **Tabla `usage_counter`:**
  - Columnas `tenant_id`, `scope`, `key_hash`, `window_start` y `count`.
  - `scope` pertenece a un conjunto cerrado: `session`, `origin_day`, `tenant_day`, `global_day`, `voice_call`.
  - Clave primaria `(scope, key_hash, window_start)`.
- **Incremento atómico:** `INSERT ... ON CONFLICT DO UPDATE SET count = usage_counter.count + 1 RETURNING count`, antes de cada uso del modelo.
  - Es correcto con uno o varios procesos, y sobrevive a reinicios.
  - Se consulta junto a `UsageBudget` (ADR-015).
- **Origen:**
  - La IP es dato personal: se guarda como hash con sal que rota en el reinicio nocturno.
  - Solo se confía en `X-Forwarded-For` si viene del proxy del hospedaje. La opción exacta del servidor ASGI queda **por verificar en Functional Design**.
- **Ventana diaria:**
  - Documentar que la cuota diaria de Gemini se reinicia a medianoche del Pacífico [S65].
  - Fijar el límite global diario del aplicativo por debajo de esa cuota, para que la degradación sea el mensaje honesto del catálogo y no un 429 del proveedor.
- **Voz:**
  - Una llamada por visitante, con duración máxima aplicada en el proceso y también en el proveedor, según exige team.md.
  - La verificación del tope en cada proveedor queda en la tabla versionada del ADR-015.
- **Proyectos:** un proyecto de Gemini por uso (voz, chat, evals). **Enmienda de práctica y del ADR-015/ADR-018.**
- **Limpieza:** las filas vencidas se borran en el reinicio nocturno.

**Rechazar:** `slowapi` y `limits` como autoridad (sin backend SQL, contadores por proceso), y Redis para contadores (ver las señales de la sección 3).

**Aceptable como complemento:** un semáforo en proceso por sesión que limite streams simultáneos. No sustituye los contadores.

---

## 6. Transporte en tiempo real

### Hallazgos

**6.1 FastAPI trae SSE nativo.**
- 0.135.0 (2026-03-01): "Add support for Server Sent Events" [S59].
- `from fastapi.sse import EventSourceResponse, ServerSentEvent` [S59]:
  - Envía un ping cada 15 s, fija `Cache-Control: no-cache` y `X-Accel-Buffering: no`.
  - Admite `id` y `retry`, y la reanudación con `Last-Event-ID`.
  - "SSE works with any HTTP method".
- La versión actual es 0.141.1 (2026-07-29) [S34]. `sse-starlette` ya no hace falta.

**6.2 Límites del navegador.**
- El constructor `EventSource` solo acepta `url` y `withCredentials`: no permite cambiar el método ni añadir cabeceras [S60].
- Sin HTTP/2, el máximo es **6 conexiones por navegador y dominio**, sumando todas las pestañas [S60].
- Si el chat se consume con `POST`, hay que leer el stream con `fetch` y se pierde la reconexión automática de `EventSource` **(inferencia)**.

**6.3 LISTEN/NOTIFY.**
- **Semántica:**
  - Se entrega al hacer commit.
  - Carga útil de hasta 8.000 bytes.
  - Cola de 8 GB; si se llena, el commit que notifica falla.
  - El oyente necesita la conexión viva para recibir [S61].
- **Con Neon:**
  - El endpoint con pool es PgBouncer en modo transacción, sin LISTEN, SET ni PREPARE de SQL [S47].
  - Si la base se suspende, "NOTIFY/LISTEN subscriptions" se pierden [S47].
- **Escala:** la contención del bloqueo global al hacer commit con `NOTIFY` aparece con muchos escritores [S62], no a escala de demo.

**6.4 Redis pub/sub** añade un servicio y no resuelve la reanudación tras reinicio: los mensajes no se persisten.

### Recomendación

- **Chat: SSE nativo de FastAPI, en dos pasos.**
  - `POST /messages` guarda el mensaje y devuelve su id.
  - `GET /stream?after=<id>` con cookie `HttpOnly` y `EventSource` con `withCredentials`, que emite eventos con `id` monotónico.
  - La reconexión es nativa del navegador y la reanudación usa `Last-Event-ID` [S59][S60].
  - Fijar FastAPI ≥ 0.135.0 en el lockfile.
- **Bandeja:** SSE sobre una tabla `inbox_event` con id monotónico, bajo RLS.
  - Al conectar o reconectar, se reproducen los eventos posteriores a `Last-Event-ID`.
  - Después se espera un `asyncio.Condition` que despiertan las escrituras del propio proceso.
  - Como red de seguridad, se vuelve a consultar la tabla cada 5 a 10 s. Esto cubre reinicios y varias instancias sin LISTEN.
- **Presupuesto de conexiones:** como mucho un stream por pestaña (chat, bandeja o panel de traza), cerrado cuando la pestaña se oculta [S60].
- **Rechazar:** WebSocket para el chat (no hay tráfico bidireccional que lo justifique; la voz usa el transporte de su propia librería, fuera de este alcance) y Redis pub/sub.
- **Diferir:** LISTEN/NOTIFY, solo con más de un proceso y con una conexión directa dedicada, nunca por el pool [S47][S61].
- **No verificado:** si un stream SSE abierto cuenta como "inbound traffic" para Render y evita el apagado a los 15 min [S46]. Lo resuelve el intent `infra`.

---

## 7. Herramientas de acceso a datos y Postgres gestionado

### Hallazgos

**7.1 Driver y ORM.**
- **LangGraph y psycopg 3:**
  - `langgraph-checkpoint-postgres` 3.1.2 (2026-08-07) usa psycopg 3 y exige `autocommit=True` y `row_factory=dict_row` [S38].
  - El constructor `from_conn_string` abre la conexión con `prepare_threshold=0`, es decir, sentencias preparadas desde la primera ejecución [S38].
  - Usar asyncpg para el aplicativo obligaría a mantener **dos drivers**.
- **SQLAlchemy:**
  - Documenta `postgresql+psycopg` con `create_async_engine` [S54].
  - Para asyncpg detrás de PgBouncer exige desactivar la caché de sentencias preparadas [S54].
- **pgvector-python** soporta SQLAlchemy, psycopg 3 asíncrono (`register_vector_async`), asyncpg y SQLModel, y `HALFVEC` en SQLAlchemy [S55].
- **SQLModel** sigue en 0.0.42 (2026-08-28) [S34]. Sigue sin versión 1.0, y mezcla modelos de API con modelos de tabla.

**7.2 Migraciones con RLS.**
- Alembic 1.20.0 (2026-09-11) no autogenera políticas [S34].
- `alembic_utils` sí tiene `PGPolicy` [S56], pero su última versión es de 2025-04-10 [S34] y no cubre `ENABLE/FORCE ROW LEVEL SECURITY`.
- La garantía real es la aserción de esquema que ya exige el ADR-012.

**7.3 Trampas de RLS verificadas.**
1. **Quién salta RLS:** superusuarios y roles con `BYPASSRLS` siempre. El **dueño de la tabla** también, salvo con `FORCE ROW LEVEL SECURITY`. Con RLS activo y sin política, no se ve nada [S20].
2. **La imagen oficial de Postgres crea `POSTGRES_USER` como superusuario** [S57]. Una prueba de aislamiento con testcontainers (4.15.0) que se conecte con ese usuario **pasa aunque no haya aislamiento**. Las pruebas de DS-8 deben conectarse con el rol del aplicativo.
3. **Variable de aseguradora:**
   - `set_config(name, value, is_local => true)` solo dura la transacción [S51].
   - Al terminar esa transacción, una variable propia vuelve a **cadena vacía y no a NULL**, y `current_setting(..., true)` no protege de eso **(hilo de pgsql y artículo, vistos en resumen de búsqueda)** [S50].
   - La política debe usar `NULLIF(current_setting('app.tenant_id', true), '')::uuid`, envuelta en `(select ...)` [S19].
4. **Poolers:**
   - `SET LOCAL` o `set_config(..., true)` dentro de una transacción explícita es seguro con poolers en modo transacción, porque PostgreSQL revierte el valor antes de devolver la conexión **(respuesta comunitaria, no oficial, 2026-07-15)** [S49].
   - El `SET` de sesión y las consultas en autocommit fuera de la transacción rompen la garantía [S49].
   - El endpoint con pool de Neon no admite `SET`, LISTEN ni PREPARE de SQL, pero sí sentencias preparadas de protocolo (`max_prepared_statements=1000`) [S47]. PgBouncer las soporta desde 1.21.0 (2023-10-16) [S53].
5. **El checkpointer de LangGraph no pasa por el punto único de sesión** [S38]:
   - `_cursor` toma una conexión del pool por operación, en autocommit.
   - Las lecturas se ejecutan sin transacción explícita.
   - Las tablas `checkpoints`, `checkpoint_blobs` y `checkpoint_writes` no tienen columna de aseguradora, solo `thread_id`.
   - Un `set_config(..., true)` fijado por el punto único **no cubre** esas consultas.
   - **Opciones para PA-3:**
     - (a) Un pool por aseguradora (son tres, fijas). El callback `configure` fija la variable de **sesión** al crear la conexión y `reset` la reafirma [S52]. Conexión directa o pooler en modo sesión, política sobre `split_part(thread_id, ':', 1)`.
     - (b) Checkpointer propio que envuelve cada operación en una transacción con `set_config`.
   - Lo decide la investigación de orquestación y Functional Design. Aquí queda la evidencia.

**7.4 Postgres gestionado gratuito.** La elección es del intent `infra`; estos datos le sirven.

| Proveedor | Plan gratuito verificado | Riesgo para Untangle |
| --- | --- | --- |
| Neon | 0,5 GB de almacenamiento, 100 horas de cómputo al mes por proyecto, suspensión tras 5 min que **no se puede desactivar** en el plan gratuito; al agotar el cupo, el cómputo se suspende hasta el mes siguiente; sin tarjeta [S47]. Reactivación "generally takes a few hundred milliseconds", con buffers fríos [S47]. pgvector hasta 0.8.6, `unaccent`, `pg_trgm` y `pg_cron` [S5]. | (1) La primera consulta tras 5 min de inactividad añade cientos de ms: el turno de voz no debe tocar la base en frío, así que conviene precargar al identificar a la persona (ADR-004) y leer del estado en memoria. (2) Mantener la base despierta con pings consume horas: con un mínimo supuesto de 0,25 unidades de cómputo, un mes despierto serían unas 180 horas, por encima de las 100 **(tamaño mínimo no verificado)**. Choca con el "ping periódico" del checklist si ese ping llega a la base. (3) `pg_search` se retira el 2026-09-21 [S4]. |
| Supabase | 500 MB de base, 500 MB de RAM compartida, 2 proyectos, pausa tras 1 semana de inactividad, sin copias de seguridad automáticas [S48]. | (1) La conexión directa es solo IPv6. Desde un hospedaje sin IPv6 hay que usar Supavisor en modo sesión (puerto 5432, admite sentencias preparadas); el modo transacción (6543) no las admite [S48]. (2) La Data API (PostgREST) expone el esquema `public` por defecto. Si Supabase se usa solo como Postgres, **desactivarla** [S48]. |
| Render Postgres | 1 GB y **expira a los 30 días** [S46]. | Rechazar para un proyecto de 90 días. |
| Aiven gratuito | 1 CPU, 1 GB de RAM, 1 GB de almacenamiento, se apaga por inactividad **(resumen de búsqueda; pgvector en el plan gratuito no verificado)** [S58]. | Verificar pgvector antes de considerarlo. |

**Espacio estimado (no medido):**
- Unas 4.000 cláusulas × (3 KB de vector + 1 a 2 KB de texto) ≈ 20 MB.
- Los checkpoints de LangGraph crecen por paso y deben podarse en el reinicio nocturno para caber en 0,5 GB.

### Recomendación

- **Adoptar en el runtime:**
  - SQLAlchemy 2.0 asíncrono (Core para la consulta híbrida con CTE; ORM opcional) con **psycopg 3 como único driver**, en un ADR nuevo o una enmienda del ADR-002.
  - Alembic con `op.execute` explícito para `ENABLE`, `FORCE` y `CREATE POLICY`.
  - **Roles:**
    - El rol dueño corre las migraciones.
    - El rol del aplicativo no es dueño, tiene `NOBYPASSRLS` y trabaja con `FORCE RLS`.
    - La aserción de esquema lee `pg_class.relrowsecurity`, `relforcerowsecurity` y `pg_policies`, e incluye las tablas de checkpoints.
  - **Punto único de sesión:**
    - `BEGIN`, luego `SELECT set_config('app.tenant_id', $1, true)`, y todas las consultas dentro de esa transacción.
    - Políticas con `NULLIF(...)` y `(select ...)`.
    - Una prueba que falle si una consulta del aplicativo corre en autocommit.
  - **Conexión:** con un solo proceso de larga vida, conexión directa en Neon o Supavisor en modo sesión en Supabase, con un pool pequeño. No hace falta modo transacción.
- **Adoptar solo en pruebas:** testcontainers 4.15.0 con la imagen `pgvector/pgvector:pg18-trixie` [S2], conectando las pruebas de aislamiento **con el rol del aplicativo** [S57].
- **Rechazar y documentarlo:**
  - asyncpg: dos drivers, y la caché de sentencias preparadas complica los poolers [S38][S54].
  - SQLModel (0.0.x).
  - `alembic_utils`: mantenimiento incierto y no cubre ENABLE/FORCE.
  - Render Postgres gratuito (expira).
- **Evidencia para PA-3 y ADR-012:** el checkpointer oficial en autocommit no queda cubierto por la variable local a la transacción (7.3, trampa 5).

---

## Señales de "currículum" detectadas

Tecnologías que, en este proyecto, parecerían añadidas para lucir y no por necesidad. Quien evalúa las castiga.

| Tecnología | Por qué parece de currículum aquí |
| --- | --- |
| GraphRAG, LightRAG, Neo4j, FalkorDB, Apache AGE | Unas pocas miles de cláusulas cuyas relaciones ya se conocen; la evidencia legal no muestra ganancia proporcional [S23][S25]. Es el "multi-agent como palabra de moda" que el PRD menciona, en versión grafos. |
| Índice HNSW | En unas miles de filas es imitación de "base vectorial": empeora el recall con RLS y el determinismo sin ganar latencia [S2]. |
| Reordenador "porque el RAG de producción lo lleva" | Sin una brecha medida en DS-3, es una dependencia y un tercero más. |
| Recuperación contextual con LLM | El contexto ya lo conoce el generador; pagar tokens por él es teatro. |
| BM25 de ParadeDB o `pg_textsearch` | Sin métrica que lo pida; en tabla multi-tenant mezcla estadísticas entre aseguradoras [S7]. |
| Redis (caché semántica, sesiones, pub/sub, límites) | Un proceso, tráfico de demo y un techo de 5 USD. Hay señales de salida concretas en la sección 3. |
| Celery, Hatchet, Temporal, DBOS | Un proceso; DBOS además duplicaría la durabilidad de LangGraph. |
| WebSocket para el chat | No hay tráfico bidireccional. |
| `ranx` o RAGAS para 40 preguntas | Las métricas son de pocas líneas. |

---

## Tabla final de recomendaciones

| Tecnología | Recomendación | Razón | ¿Cambia un ADR aprobado? |
| --- | --- | --- | --- |
| PostgreSQL + pgvector (búsqueda exacta, sin HNSW) | adoptar en el runtime | Recall perfecto y determinista a este tamaño; evita la trampa de filtros y RLS [S2] | Sí, enmienda del ADR-010 (índice y umbral de reapertura) |
| HNSW con recorridos iterativos, `halfvec` | diferir (trabajo futuro) | Solo si el p95 del recorrido exacto supera el umbral; entonces parcial por aseguradora y `strict_order` [S2] | Sí, se anota en el ADR-010 |
| FTS de Postgres por idioma con `unaccent` y RRF (k = 60, desempate estable) | adoptar en el runtime | Suficiente para términos exactos; RRF sin entrenamiento [S10][S11][S12] | Sí, precisión del ADR-010 |
| ParadeDB `pg_search`, `pg_textsearch`, VectorChord-bm25 | rechazar y documentarlo en un ADR | AGPL o retirada en Neon, solo PG17/18, estadísticas mezcladas entre aseguradoras [S4][S7][S8] | Sí, alternativas rechazadas del ADR-010 |
| Base vectorial dedicada | rechazar y documentarlo en un ADR | Ya rechazada; sin cambios | No |
| Encabezado estructural determinista (recuperación contextual sin LLM) | adoptar en el runtime | La técnica reduce fallos en los datos de Anthropic [S13] y aquí cuesta cero | Sí, ADR-010 y ADR-016 |
| Recuperación contextual generada por LLM | rechazar y documentarlo en un ADR | Costo y no determinismo sin necesidad | Sí, ADR-010 |
| Reordenador local (`bge-reranker-v2-m3`) | rechazar y documentarlo en un ADR | 0,6B parámetros en instancia gratuita, compite con la voz [S14] | Sí, ADR-010 |
| Reordenador por API (Voyage, Cohere, Vertex) o por LLM | diferir (trabajo futuro) | Solo con brecha medida entre top-20 y top-k en DS-3; nuevo tercero con datos públicos [S15][S16] | No |
| Línea base "póliza completa en contexto" | diferir (trabajo futuro) | Experimento de hito que prueba el valor de la recuperación [S13] | No |
| Relaciones entre cláusulas en tablas + CTE recursivo (cierre) | adoptar en el runtime | Endosos que reabren exclusiones; evidencia de cierre de citas [S26]; relaciones exactas del generador | Sí, ADR-010 y enmienda del ADR-011 (chequeo de modificadores) |
| Neo4j, FalkorDB, Apache AGE, LightRAG, Microsoft GraphRAG | rechazar y documentarlo en un ADR | Ganancia marginal o negativa [S23][S25], servicio extra, aislamiento sin RLS, planes gratuitos que pausan o borran [S31][S32] | Sí, alternativas rechazadas (ADR-010 o uno nuevo) |
| Tareas asyncio en proceso + arrendamiento en `NodeRun` + barrido | adoptar en el runtime | Cierra el hueco de relanzamiento y doble ejecución sin servicio nuevo [S35][S37][S46] | Sí, enmienda del ADR-004 |
| Procrastinate (worker en proceso) | diferir (trabajo futuro) | Alternativa documentada si el código propio crece [S39] | Sí, alternativa en el ADR-004 |
| DBOS, Absurd | rechazar y documentarlo en un ADR | Segundo modelo de durabilidad sobre LangGraph; DBOS 3.0.0 de hace un día [S34][S41][S42] | Sí, ADR-004 |
| PgQueuer, pgmq | rechazar y documentarlo en un ADR | Esquema o primitiva extra sin ganancia frente al arrendamiento en `NodeRun` [S40][S44] | Sí, ADR-004 |
| Hatchet, Temporal, Celery, RQ, arq, Taskiq, Dramatiq + Redis | rechazar y documentarlo en un ADR | Servicio o broker aparte [S43] | No (ya rechazados); añadir Hatchet |
| FastAPI `BackgroundTasks` | rechazar y documentarlo en un ADR | Sin durabilidad ni reintento [S36] | Sí, ADR-004 |
| Redis (caché, sesiones, pub/sub, límites) | diferir (trabajo futuro) | Con las 5 señales de salida de la sección 3 | No |
| Caché semántica de respuestas | rechazar y documentarlo en un ADR | Falsos aciertos entre aseguradoras o endosos; salta el verificador [S71] | Sí, ADR-011 o ADR-015 |
| Caché de contexto explícita de Gemini | rechazar y documentarlo en un ADR | No disponible en el plan gratuito; almacenamiento por hora [S68] | No (nota en ADR-006) |
| Prefijo estable para la caché implícita | adoptar en el runtime | Gratis; ahorra en el plan de pago [S67] | No |
| Caché de embeddings de consultas curadas en Postgres | adoptar solo en desarrollo/pruebas | Ahorra cuota de CI y estabiliza evals; nunca texto libre de visitantes [S72] | No |
| Contadores de uso atómicos en Postgres | adoptar en el runtime | Correctos con varios procesos y reinicios; sin Redis [S46][S63] | Sí, ADR-015 |
| `slowapi` o `limits` como autoridad | rechazar y documentarlo en un ADR | Sin backend SQL; memoria por proceso [S63][S64] | No |
| Un proyecto de Gemini por uso | adoptar en el runtime | Límites por proyecto, no por clave; topes solo de pago, mensuales, unos 10 min de latencia [S65][S66] | Sí, ADR-015/ADR-018 y práctica de team.md |
| SSE nativo de FastAPI (chat en dos pasos, bandeja con `Last-Event-ID`) | adoptar en el runtime | Nativo desde 0.135.0; reconexión del navegador [S59][S60] | No (hoy no hay ADR de transporte; conviene uno) |
| WebSocket para chat, Redis pub/sub | rechazar y documentarlo en un ADR | Sin necesidad bidireccional; servicio extra | No |
| LISTEN/NOTIFY | diferir (trabajo futuro) | Solo con varios procesos y conexión directa; se pierde al suspender en Neon [S47][S61] | No |
| SQLAlchemy 2 asíncrono + psycopg 3 | adoptar en el runtime | Un solo driver, compartido con el checkpointer [S38][S54][S55] | No (completa el ADR-002; conviene un ADR) |
| asyncpg, SQLModel | rechazar y documentarlo en un ADR | Dos drivers; SQLModel 0.0.x [S34][S54] | No |
| Alembic con SQL explícito de RLS + aserción de esquema | adoptar en el runtime | ENABLE/FORCE/POLICY auditables [S20] | Sí, precisión del ADR-012 |
| `alembic_utils` | rechazar y documentarlo en un ADR | Sin versión desde 2025-04; no cubre ENABLE/FORCE [S34][S56] | No |
| `set_config(..., true)` + `NULLIF` + `FORCE RLS` + rol sin `BYPASSRLS` | adoptar en el runtime | Trampas verificadas de cadena vacía, dueño y superusuario [S20][S50][S51] | Sí, enmienda del ADR-012 |
| testcontainers con imagen pgvector y rol del aplicativo | adoptar solo en desarrollo/pruebas | Con el superusuario por defecto, las pruebas de aislamiento pasan falsamente [S57] | Sí, precisión del ADR-012 (DS-8) |
| Neon o Supabase gratuitos | diferir (decisión del intent `infra`) | Neon: arranque en frío y horas de cómputo; Supabase: IPv6 y Data API [S47][S48] | No |
| Render Postgres gratuito | rechazar y documentarlo en un ADR | Expira a los 30 días [S46] | No |

---

## ADR que deberían cambiar

1. **ADR-004, enmienda obligatoria.**
   - Arrendamiento, latido y barrido sobre `NodeRun`, con bandeja transaccional y supervisor con referencias fuertes.
   - Idempotencia de `SpendEntry` y modo de durabilidad explícito de LangGraph.
   - Agotamiento hacia `unverifiable`.
   - Restricción de hospedaje: CPU fuera de petición y reinicios.
   - Trabajos programados con disparador externo o puesta al día al arrancar.
   - Añadir DBOS, Absurd, Procrastinate, PgQueuer, pgmq, Hatchet y `BackgroundTasks` a las alternativas.
2. **ADR-010, enmienda.**
   - Sin HNSW con umbral de reapertura, FTS por idioma con `unaccent`, RRF con desempate estable.
   - Encabezado estructural determinista, normalización y `task_type`.
   - Tabla de relaciones y cierre por CTE.
   - Nuevas alternativas rechazadas: extensiones BM25, reordenadores, recuperación contextual con LLM, bases y frameworks de grafos.
   - Métricas de recuperación de la sección 1.9.
3. **ADR-011, enmienda propuesta.** El verificador comprueba modificadores vigentes (sección 2). Cambia la aplicación de un criterio aprobado, así que requiere visto bueno de Miguel.
4. **ADR-012, enmienda.**
   - `set_config` local con `NULLIF` e initPlan, `FORCE RLS` y roles.
   - Pruebas con el rol del aplicativo.
   - Pooler en modo sesión o conexión directa.
   - Evidencia de que el checkpointer en autocommit no queda cubierto, con las opciones de pool por aseguradora o checkpointer propio (junto a PA-3 del ADR-003).
5. **ADR-015, y práctica de team.md sobre claves.**
   - Contadores de uso en Postgres.
   - Proyectos de Gemini separados por uso.
   - Los topes del proveedor son mensuales, de pago y con latencia: segunda red, nunca la primera.
6. **ADR nuevo, o sección de Functional Design:** transporte en tiempo real (SSE en dos pasos, bandeja por cursor, LISTEN/NOTIFY diferido) y pila de acceso a datos (SQLAlchemy 2 + psycopg 3, Alembic explícito).

---

## Fuentes

Fechas de publicación cuando la fuente las muestra; en otro caso, fecha de consulta (2026-09-17). "(resumen)" indica que solo vi el resumen del buscador y no abrí la página.

- [S1] pgvector CHANGELOG, 0.8.6 (2026-07-29), 0.8.3–0.8.5 (junio y julio de 2026), 0.8.2 (2026-02-25). https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md
- [S2] pgvector README (v0.8.6; búsqueda exacta, filtros, recorridos iterativos, índices parciales, almacenamiento, monitoreo de recall; imagen `pgvector/pgvector:pg18-trixie`). Consultado 2026-09-17. https://github.com/pgvector/pgvector
- [S3] "pgvector 0.8.2 Released" (CVE-2026-3172), 2026-02-26 (resumen). https://www.postgresql.org/about/news/pgvector-082-released-3245
- [S4] Neon Docs, extensión `pg_search`: obsoleta desde 2026-03-19, se retira el 2026-09-21. https://neon.com/docs/extensions/pg_search
- [S5] Neon Docs, extensiones soportadas. Consultado 2026-09-17. https://neon.com/docs/extensions/pg-extensions
- [S6] PostgreSQL News, "pg_textsearch v1.0", 2026-04-03. https://www.postgresql.org/about/news/pg_textsearch-v10-3264
- [S7] `timescale/pg_textsearch` README (PG17/18, limitaciones con RLS y particiones, v1.4.0). Consultado 2026-09-17. https://github.com/timescale/pg_textsearch
- [S8] ParadeDB, licencia AGPL-3.0/comercial (resumen); `pg_search` 0.22.5 en PGXN, 2026-04-02. https://github.com/paradedb/paradedb , https://pgxn.org/dist/pg_search/
- [S9] VectorChord-bm25 (resumen). https://github.com/tensorchord/VectorChord-bm25
- [S10] PostgreSQL 18, "Controlling Text Search". https://www.postgresql.org/docs/current/textsearch-controls.html
- [S11] PostgreSQL 18, `unaccent`. https://www.postgresql.org/docs/current/unaccent.html
- [S12] Cormack, Clarke y Büttcher, "Reciprocal Rank Fusion outperforms Condorcet and Individual Rank Learning Methods", SIGIR 2009. https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/
- [S13] Anthropic, "Contextual Retrieval", 2024-09-19. https://www.anthropic.com/engineering/contextual-retrieval
- [S14] BAAI, `bge-reranker-v2-m3` (0.6B, Apache-2.0). https://huggingface.co/BAAI/bge-reranker-v2-m3
- [S15] Cohere Docs, "Different Types of API Keys and Rate Limits". Consultado 2026-09-17. https://docs.cohere.com/docs/rate-limits
- [S16] Voyage AI, precios. Consultado 2026-09-17. https://docs.voyageai.com/docs/pricing
- [S17] Google Cloud, Ranking API y precios de Agent Search (resumen). https://docs.cloud.google.com/generative-ai-app-builder/docs/ranking , https://cloud.google.com/generative-ai-app-builder/pricing
- [S18] Gemini API, "Embeddings" (001 frente a 2, normalización, `task_type`, incompatibilidad). https://ai.google.dev/gemini-api/docs/embeddings
- [S19] Supabase Docs, "Row Level Security", sección de rendimiento. https://supabase.com/docs/guides/database/postgres/row-level-security
- [S20] PostgreSQL 18, "Row Security Policies". https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- [S22] Bassani, "ranx", ECIR 2022; repositorio. https://github.com/AmenRa/ranx
- [S23] Ongris et al., "Benchmarking KG-based RAG Systems: A Case Study of Legal Documents", RAGE-KG en ISWC 2025, CEUR Vol-4079. https://ceur-ws.org/Vol-4079/paper6.pdf
- [S24] Han et al., "RAG vs. GraphRAG: A Systematic Evaluation and Key Insights", arXiv 2502.11371 (v1 2025-02-17; v3 2026-03-04). https://arxiv.org/abs/2502.11371
- [S25] "When to use Graphs in RAG: A Comprehensive Analysis for Graph Retrieval-Augmented Generation", arXiv 2506.05690 (2025-06-06; revisado 2026-02-22). https://arxiv.org/abs/2506.05690
- [S26] Ju y Lee, "Citation-Closure Retrieval and Per-Rule Attribution for Real-World Regulatory Compliance Question Answering", arXiv 2605.29742 (v1 2026-05-28; v2 2026-08-31). https://arxiv.org/abs/2605.29742
- [S27] Microsoft GraphRAG, README (costo de indexación, modo mantenimiento). Consultado 2026-09-17. https://github.com/microsoft/graphrag
- [S28] Microsoft Research, "LazyGraphRAG" (resumen). https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/
- [S29] HKUDS/LightRAG, issues #1927 y #2133 sobre aislamiento por workspace y multi-tenant (resumen). https://github.com/HKUDS/LightRAG/issues/1927 , https://github.com/HKUDS/LightRAG/issues/2133
- [S30] apache/age, discusión #2305, "2026 roadmap…", 2026-01-16. https://github.com/apache/age/discussions/2305
- [S31] Neo4j, "Free graph database" (AuraDB Free). Consultado 2026-09-17. https://neo4j.com/free-graph-database/
- [S32] FalkorDB Docs, plan gratuito; licencia SSPLv1 (resumen). https://docs.falkordb.com/cloud/free-tier.html , https://docs.falkordb.com/References/license.html
- [S33] PostgreSQL, "WITH Queries" (`WITH RECURSIVE`, cláusula `CYCLE`); no reabierta en esta sesión. https://www.postgresql.org/docs/current/queries-with.html
- [S34] Índice JSON de PyPI, consultado 2026-09-17: procrastinate 3.9.0 (2026-06-20); pgqueuer 1.4.0 (2026-09-14); dbos 3.0.0 (2026-09-16); pgmq 1.1.3 (2026-08-18); taskiq 0.12.6 (2026-08-29); arq 0.28.0 (2026-04-16); dramatiq 2.2.1 (2026-09-02); celery 5.6.3 (2026-03-26); rq 2.12.0 (2026-08-30); hatchet-sdk 1.40.1 (2026-09-09); langgraph 1.2.11 (2026-08-11); langgraph-checkpoint-postgres 3.1.2 (2026-08-07); fastapi 0.141.1 (2026-07-29); sqlmodel 0.0.42 (2026-08-28); sqlalchemy 2.0.54 (2026-09-15); alembic 1.20.0 (2026-09-11); asyncpg 0.31.0 (2025-11-24); psycopg 3.3.5 (2026-08-31); slowapi 0.1.10 (2026-06-13); limits 5.8.0 (2026-02-05); sse-starlette 3.4.11 (2026-09-05); testcontainers 4.15.0 (2026-07-24); ranx 0.3.21 (2025-08-07); absurd-sdk 0.5.0 (2026-08-04); alembic-utils 0.8.8 (2025-04-10). https://pypi.org/pypi/<paquete>/json
- [S35] Python 3, "Coroutines and Tasks" (`create_task`, `TaskGroup`). https://docs.python.org/3/library/asyncio-task.html
- [S36] FastAPI, "Background Tasks". https://fastapi.tiangolo.com/tutorial/background-tasks/
- [S37] LangChain Reference, `langgraph.types.Durability`. https://reference.langchain.com/python/langgraph/types/Durability
- [S38] `langgraph-checkpoint-postgres`, README y código `aio.py` (autocommit, `prepare_threshold=0`, `_cursor`, DDL), leído 2026-09-17. https://github.com/langchain-ai/langgraph/tree/main/libs/checkpoint-postgres
- [S39] Procrastinate Docs, "Launch a worker" y "Retry stalled jobs". https://procrastinate.readthedocs.io/en/stable/howto/basics/worker.html , https://procrastinate.readthedocs.io/en/stable/howto/production/retry_stalled_jobs.html
- [S40] PgQueuer, README. https://github.com/janbjorge/pgqueuer
- [S41] DBOS Transact (Python), README. https://github.com/dbos-inc/dbos-transact-py
- [S42] Armin Ronacher, "Absurd In Production", 2026-04-04; "Absurd Workflows", 2025-11-03. https://lucumr.pocoo.org/2026/4/4/absurd-in-production/ , https://lucumr.pocoo.org/2025/11/3/absurd-workflows/
- [S43] Hatchet Docs, "Hatchet Lite Deployment". https://docs.hatchet.run/self-hosting/hatchet-lite
- [S44] pgmq, instalación como extensión o solo SQL (resumen). https://github.com/pgmq/pgmq
- [S45] Google Cloud Run, "Billing settings for services". https://docs.cloud.google.com/run/docs/configuring/billing-settings
- [S46] Render Docs, "Deploy for Free". Consultado 2026-09-17. https://render.com/docs/free
- [S47] Neon: precios https://neon.com/pricing ; ciclo de vida del cómputo https://neon.com/docs/introduction/compute-lifecycle ; connection pooling https://neon.com/docs/connect/connection-pooling ; scale to zero https://neon.com/docs/introduction/scale-to-zero . Consultados 2026-09-17.
- [S48] Supabase: precios https://supabase.com/pricing ; conexión e IPv4/IPv6 (resumen) https://supabase.com/docs/guides/database/connecting-to-postgres ; seguridad de la Data API (resumen) https://supabase.com/docs/guides/api/securing-your-api
- [S49] Supabase Discussion #47946, "Transaction-mode pooler: are SET LOCAL GUCs … isolated", 2026-07-14/15 (respuesta comunitaria). https://github.com/orgs/supabase/discussions/47946
- [S50] pgsql-bugs y hilo "Transaction local custom settings set to '' rather than removed" (resumen). https://www.postgresql.org/message-id/CA+Q86ij0KDCB0G45G509-8q0DNR611gcKG-sSM83GA1EBL7boA@mail.gmail.com
- [S51] PostgreSQL 18, "System Administration Functions" (`set_config`, `current_setting`). https://www.postgresql.org/docs/current/functions-admin.html
- [S52] psycopg 3, API de `psycopg_pool` (`configure`, `reset`, `check`). https://www.psycopg.org/psycopg3/docs/api/pool.html
- [S53] PgBouncer changelog: 1.21.0 (2023-10-16) con sentencias preparadas de protocolo; última 1.25.2 (2026-05-08). https://www.pgbouncer.org/changelog.html
- [S54] SQLAlchemy 2.0, dialecto PostgreSQL (asyncpg, psycopg). https://docs.sqlalchemy.org/en/20/dialects/postgresql.html
- [S55] pgvector-python, README. https://github.com/pgvector/pgvector-python
- [S56] alembic_utils, README (`PGPolicy`). https://github.com/olirice/alembic_utils
- [S57] Docker Official Images, documentación de `postgres` (`POSTGRES_USER` con poderes de superusuario). https://github.com/docker-library/docs/blob/master/postgres/content.md
- [S58] Aiven, "Free PostgreSQL Database" (resumen). https://aiven.io/free-postgresql-database
- [S59] FastAPI, "Server-Sent Events (SSE)"; notas de versión 0.135.0 (2026-03-01). https://fastapi.tiangolo.com/tutorial/server-sent-events/ , https://fastapi.tiangolo.com/release-notes/
- [S60] MDN, "Using server-sent events" y constructor `EventSource()`. https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events , https://developer.mozilla.org/en-US/docs/Web/API/EventSource/EventSource
- [S61] PostgreSQL 18, `NOTIFY`. https://www.postgresql.org/docs/current/sql-notify.html
- [S62] Recall.ai, "Postgres LISTEN/NOTIFY does not scale", julio de 2025 (resumen). https://www.recall.ai/blog/postgres-listen-notify-does-not-scale
- [S63] `limits`, "Storage backends". https://limits.readthedocs.io/en/stable/storage.html
- [S64] `slowapi`, README. https://github.com/laurentS/slowapi
- [S65] Gemini API, "Rate limits". https://ai.google.dev/gemini-api/docs/rate-limits
- [S66] Gemini API, "Billing" (topes de gasto por proyecto); Google Keyword, anuncio del 2026-03-16 (resumen). https://ai.google.dev/gemini-api/docs/billing , https://blog.google/innovation-and-ai/technology/developers-tools/more-control-over-gemini-api-costs/
- [S67] Gemini API, "Context caching". https://ai.google.dev/gemini-api/docs/caching
- [S68] Gemini API, precios. Consultado 2026-09-17. https://ai.google.dev/gemini-api/docs/pricing
- [S69] Gemini API, modelo `gemini-3.1-flash-lite` (estable, mayo de 2026). https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite
- [S70] Upstash Docs, "Pricing & Limits" (Redis). https://upstash.com/docs/redis/overall/pricing
- [S71] "From Similarity to Vulnerability: Key Collision Attack on LLM Semantic Caching", arXiv 2601.23088 (resumen). https://arxiv.org/abs/2601.23088
- [S72] Morris, Kuleshov, Shmatikov y Rush, "Text Embeddings Reveal (Almost) As Much As Text", EMNLP 2023, arXiv 2310.06816 (2023-10-10). https://arxiv.org/abs/2310.06816
