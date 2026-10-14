# **Análisis Profundo: Untangle, flujo multiagente para seguros de auto con voz bilingüe en tiempo real — Arquitectura, viabilidad y estado real del proyecto (2026)**

> **Contexto del proyecto:** Untangle es un proyecto de portafolio, funcional en su totalidad, que demuestra ingeniería de IA agéntica de nivel producción: un asegurado llama por voz (inglés o español) para reportar un siniestro de auto o pedir una cotización; un flujo de agentes con responsabilidades separadas captura los hechos en un registro estructurado, verifica la cobertura citando la cláusula exacta de la póliza, aplica reglas deterministas, y una compuerta de cumplimiento decide si el caso cierra o va a una persona. Todo queda trazado y evaluado contra un golden set. Datos 100% sintéticos, costo cero, aseguradoras ficticias. Este análisis distingue lo que existe hoy (la landing), lo que se construye, y lo que queda como evolución. Fuentes: `[idea n]` y `[critica X]`.

---

## **1. El problema que Untangle resuelve: capturar, verificar y derivar sin decidir**

Un primer aviso de siniestro combina tres cosas difíciles de hacer a la vez: escuchar a una persona nerviosa que interrumpe, llenar un registro con decenas de campos (el ACORD 2 tiene identificación, siniestro, vehículo asegurado, otro vehículo o propiedad, lesionados, testigos [idea 7]), y responder preguntas de cobertura sin inventar condiciones. La industria ha fijado la frontera: "la IA reúne hechos y no decide cobertura" [idea 2]. La experiencia digital sigue siendo mala en la práctica (22% de actualizaciones adecuadas, 52% de riesgo de fuga con experiencias pobres [idea 5]).

Untangle transforma la llamada en un caso estructurado que crece turno a turno, con cada respuesta de cobertura sostenida por una cláusula identificable, cada decisión explicada por una regla y sus entradas, y cada derivación a una persona con la traza adjunta. La diferencia con un chatbot sobre una API no es incremental: es la separación entre lo que el modelo interpreta y lo que el sistema decide [idea 21].

## **2. Arquitectura propuesta: lo que se construye y por qué**

### Estado real por componente

| Componente | Estado | Detalle |
| :---- | :---- | :---- |
| **Landing bilingüe** | ✅ Existe (publicada) | `site/`, Vercel. Se realineará al producto real después de Incepción [critica C12] |
| **Registro del caso (esquema ACORD 2 y 90)** | 🔧 Por construir | Subconjunto con siete campos centrales y grupos repetibles; completitud medible [idea 7][idea 9] |
| **Grafo de orquestación** | 🔧 Por construir | LangGraph como hipótesis: máquina de estados explícita, checkpoints, `interrupt()` para la persona [idea 20] |
| **Agentes: Intake, Verificación, Decisión, Cumplimiento** | 🔧 Por construir | Nodos con herramientas, esquemas de salida y evals propios; estado compartido íntegro [critica C1] |
| **Corpus de pólizas con cláusulas numeradas** | 🔧 Por construir | 3 aseguradoras ficticias, estructura ISO PP 00 01, endosos y distractores [critica C5] |
| **RAG con citación verificada** | 🔧 Por construir | pgvector con BGE-M3 o Gemini Embedding; búsqueda híbrida; verificación exacta de identificadores [idea 47][idea 50] |
| **Motor de reglas por tenant** | 🔧 Por construir | 10 a 20 reglas por flujo inspiradas en guías públicas; salida "referral" explícita [idea 14][critica C6] |
| **Capa de voz bilingüe** | 🔧 Por construir | Cascada STT → grafo → TTS; LiveKit Agents o Pipecat (ADR); detección de turno abierta con español [idea 29][idea 30] |
| **Bandeja del ajustador** | 🔧 Por construir | Casos pendientes con registro, traza y cláusulas; aprobar o rechazar reanuda el grafo [idea 20] |
| **Multi-tenant** | 🔧 Por construir | `tenant_id` con RLS en Postgres y RAG por tenant; Keycloak fuera de la primera versión [idea 49][critica C8] |
| **Observabilidad** | 🔧 Por construir | OpenTelemetry con convenciones GenAI; Langfuse self-host; costo y latencia por caso [idea 52][idea 53] |
| **Evals** | 🔧 Por construir | Golden set en texto en CI (promptfoo o DeepEval), golden set de audio propio por idioma, reporte con fallos [idea 54][critica C10] |
| **Continuidad voz a chat** | 🔮 Evolución | Reanudar un caso por chat con el mismo identificador; "should", no "must" |
| **Modo texto en vivo** | 🔧 Por construir | El mismo grafo sin voz, hospedado gratis; es el enlace en vivo del portafolio [critica C13] |

### 2.1 Orquestación: el orquestador es código

La literatura reciente es dura con los sistemas multiagente: MAST encontró 14 modos de fallo en 1.600 trazas y concluye que el margen está en el diseño del sistema [critica A]; Cognition recomienda un solo hilo con contexto completo [critica C]; LangChain reserva el multiagente para tareas paralelas e independientes [critica D]. Untangle no es un enjambre: es un grafo explícito donde cada nodo (Intake, Verificación, Decisión, Cumplimiento) recibe el caso completo, escribe campos distintos, usa herramientas distintas y se evalúa por separado. Las rutas están definidas; "si una ruta no está explícitamente enrutada, es inalcanzable" [idea 21]. La pausa para la persona es un `interrupt()` con checkpoint durable y reanudación por `thread_id` [idea 20].

### 2.2 Dos ritmos: turno conversacional y trabajo de fondo

El turno de voz se gasta en STT, primer token y primer audio [idea 33]; una consulta de RAG o una regla dentro del turno rompe el presupuesto [critica C2]. Por eso Intake responde con lo que ya sabe y pide lo que falta; Verificación y Decisión corren de fondo sobre el caso (con prefetch de la póliza al identificar al llamante y llamadas especulativas [critica F]) y sus resultados entran a la conversación cuando están listos; Cumplimiento corre una vez, al cierre. Se publican dos métricas: latencia de turno (p50 y p95, objetivo p95 < 800 ms) y latencia de decisión.

### 2.3 Voz: cascada, no voz a voz

La cascada domina la producción en 2026 y conserva acceso al texto, a las herramientas y a las decisiones [idea 24][idea 25]; sin ese acceso no hay citación, ni reglas, ni trazas por agente. Ambos frameworks candidatos son abiertos, intercambian proveedores y traen detección de turno con español (LiveKit turn detector, 14 idiomas; Smart Turn v3, 23 idiomas, 12 ms en CPU) [idea 29][idea 30]. La decisión LiveKit o Pipecat es un ADR de Incepción con dos criterios: integración con el grafo (LiveKit tiene `LLMAdapter` oficial con incidencias abiertas [idea 22][idea 23]; Pipecat tiene el ejemplo de tres capas [idea 21]) y costo cero (LiveKit Cloud Build, Daily y Pipecat Cloud tienen minutos gratuitos; ambos se auto-hospedan [idea 61]).

### 2.4 Bilingüe por diseño

Selección de idioma al inicio de la llamada como primera versión (control y medición), detección automática como evolución. Proveedores: Deepgram Nova-3 (español y cambio de idioma) y Cartesia (locales de español) con créditos gratuitos, asignados primero al español; Whisper y Kokoro en local para inglés [idea 37][idea 42][idea 39][idea 43]. Kokoro tiene tres voces en español de pronunciación latinoamericana, lo que encaja con el autor [critica K]. Dos golden sets, dos voces, prompts localizados, divulgación legal en el idioma de la llamada.

### 2.5 RAG con citación verificada

Tres controles: cláusulas indexadas con identificador estable; el agente de Verificación responde solo con identificadores recuperados o con "no encuentro cláusula que lo cubra"; una eval comprueba que cada cita existe y sostiene la afirmación (juez LLM con rúbrica más verificación exacta) [idea 44][idea 45][idea 46]. El corpus se escribe original con la estructura ISO (Acuerdo, Definiciones, Partes A a F, exclusiones numeradas, deberes tras el siniestro) y con distractores entre aseguradoras [critica C5][critica C14].

## **3. Eje A: velocidad y completitud del FNOL**

| Métrica | Referencia del sector | Meta de Untangle |
| :---- | :---- | :---- |
| **Completitud del registro FNOL** | > 95% en campos centrales es sano; < 90% hay bucles de captura perdidos [idea 1] | ≥ 95% en los siete campos centrales sobre el golden set |
| **Latencia de turno (fin del habla → primer audio)** | < 500 ms ágil; < 800 ms aceptable; > 1.500 ms roto [idea 31][idea 32] | p95 < 800 ms; p50 < 500 ms (medido por idioma) |
| **Latencia de parada por interrupción** | ~200 ms [idea 55] | < 300 ms medido en golden set de audio |
| **Recuperación tras interrupción** | > 90% [idea 55] | > 90% sin perder estado |
| **Derivaciones correctas a persona** | Un FNOL que no escala es peor que uno que no contesta [idea 4] | 100% de los casos del set que deben derivarse, derivados |

La viabilidad en este eje es alta si el trabajo pesado sale del turno; si no, la latencia de turno es imposible y el evaluador lo verá en la traza.

## **4. Eje B: verificabilidad y honestidad**

El valor defendible de Untangle es que cada decisión se puede auditar: cláusula citada y verificada, regla aplicada con entradas, derivación con traza. La crítica técnica advierte de dos fallos simétricos: citar cláusulas inexistentes [idea 44] y hacer trivial la citación con un corpus de juguete [critica C5]. Por eso el golden set de citación tiene distractores y casos sin respuesta, y el README publica precisión de citación, distribución del set y la lista de casos que fallan. Sin lista de fallos no hay honestidad, y sin honestidad el proyecto es otra demo.

## **5. Eje C: adopción por el evaluador**

El "usuario" que decide es quien evalúa el portafolio en 90 segundos y luego, si pasa, en una revisión técnica [idea 66]. Tres principios: transparencia radical (README con arquitectura, diagrama, ADRs, evals y fallos), ejecutable (enlace en vivo del modo texto, video de la voz, un comando para correrlo en local) y frontera clara entre modelo, reglas y personas. La landing enlaza los tres entregables y no promete nada que el aplicativo no haga [critica C12].

## **6. Arquitectura técnica y HITL**

**Capa de voz (LiveKit Agents o Pipecat):** transporte WebRTC o telefonía, VAD, detección de turno, barge-in, STT y TTS por idioma. Sin autoridad de decisión.

**Capa de razonamiento (LLM):** Intake extrae y responde; Verificación redacta con cláusulas recuperadas; Cumplimiento juzga contra políticas del tenant. El modelo interpreta; no ejecuta acciones sobre el caso fuera del grafo.

**Capa de política y ejecución (grafo):** rutas explícitas, estado tipado (el caso), motor de reglas, `interrupt()` para la persona, checkpoints en Postgres.

**Datos:** Postgres con `tenant_id` y RLS en todas las tablas (casos, pólizas, cláusulas, vectores, políticas); pgvector para la recuperación; RAG por tenant.

**Observabilidad y evals:** OpenTelemetry con convenciones GenAI; Langfuse self-host; las métricas de evals se derivan de las trazas; promptfoo o DeepEval en CI; golden set de audio propio.

### 6.1 HITL y gobernanza

Acciones por riesgo: capturar y estructurar (autónomo), verificar con cita (autónomo con verificación exacta), triage y elegibilidad (reglas deterministas), cualquier cosa que toque cobertura o dinero (persona, vía bandeja). Cuatro controles de cumplimiento verificables: divulgación de IA y grabación al inicio en el idioma de la llamada; ruta a persona siempre disponible; PII redactada en trazas y logs con Presidio (soporta español) [idea 59]; explicabilidad por caso. Se presentan como "inspirados en" NAIC, TCPA y EU AI Act, nunca como cumplimiento certificado [idea 56][idea 57][idea 58][critica C7].

### 6.2 Costo cero y plan B

Por defecto: modelos abiertos en local para STT, TTS e Intake; Gemini o Groq gratuitos con cola y backoff para Verificación y Cumplimiento; Langfuse y Postgres en Docker local; enlace en vivo del modo texto en hosting gratuito. Créditos gratuitos de Deepgram y Cartesia reservados al español [idea, sección 10]. Excepción declarada: un presupuesto mínimo solo para grabar el video si el modelo local no da la calidad [critica C3].

## **7. Consideraciones regulatorias (inspiración, no cumplimiento)**

NAIC Model Bulletin (25 estados y DC; gobierno documentado, explicabilidad, evitar información engañosa) [idea 56]; NY DFS Circular Letter 2024-7 [critica I]; EU AI Act Anexo III (alto riesgo en vida y salud, no en auto; transparencia y supervisión humana como patrón) [idea 57]; divulgación de IA y consentimiento de grabación por estado, FCC y TCPA [idea 58]. Implicación práctica: los cuatro controles de 6.1 y una tabla en el README que mapea principio → control → evidencia.

## **8. Análisis de viabilidad**

| Dimensión | Viabilidad | Riesgo principal |
| :---- | :---- | :---- |
| **FNOL en texto con caso, RAG, reglas, compuerta, trazas** | Alta | Alcance; se mitiga construyéndolo primero como esqueleto andante |
| **Voz en inglés con stack local** | Media-Alta | Latencia del modelo local en la máquina del autor; medir en semana 1 |
| **Voz en español** | Media | Calidad de STT y TTS abiertos; créditos comerciales asignados aquí |
| **Citación verificable** | Alta | Corpus trivial o copiado; se mitiga con estructura ISO original y distractores |
| **Multi-tenant mínimo (RLS)** | Alta | Trampas de pooling y funciones; tests de aislamiento en CI |
| **Observabilidad y evals unificadas** | Alta | Convenciones OTel en cambio; instrumentación propia reemplazable |
| **Evals de voz con audio** | Media | Sin plataforma de pago; golden set de audio propio y métricas del framework |
| **Enlace en vivo de voz** | Baja | Hosting gratuito duerme la instancia; se sustituye por modo texto en vivo más video |
| **Costo cero** | Alta salvo LLM en voz | Modelo local o presupuesto de emergencia declarado |

**Costos del proyecto:**

| Componente | Costo | Notas |
| :---- | :---- | :---- |
| Frameworks (LangGraph, LiveKit Agents o Pipecat, Langfuse, promptfoo, Presidio, pgvector) | $0 | Abiertos |
| Modelos locales (Whisper, Kokoro o Chatterbox, LLM pequeño) | $0 | Hardware del autor |
| LLM gratuito (Gemini AI Studio, Groq) | $0 | Límites de tasa; datos del tier gratuito usados por el proveedor |
| Voz comercial (Deepgram, Cartesia) | $0 | Créditos gratuitos, asignados al español |
| Transporte de voz (LiveKit Cloud, Daily o Pipecat Cloud) | $0 | Minutos gratuitos; o auto-hospedado |
| Base de datos (Neon o Supabase) y hosting del modo texto (Render, Cloud Run) | $0 | Tiers gratuitos |
| Presupuesto de emergencia para la grabación | Por decidir | Excepción a D-011 |

## **9. Requisitos mínimos para un proyecto defendible**

**I. Un camino feliz completo antes que amplitud.** FNOL de auto por voz de punta a punta, en capas demostrables, con lista de corte [critica C11].

**II. Separación verificable entre modelo, reglas y personas.** Grafo explícito, estado compartido, evals por responsabilidad, `interrupt()` para la persona [critica C1].

**III. Citación verificada y corpus no trivial.** Identificadores estables, "no encuentro cláusula" como respuesta válida, distractores, propiedad intelectual limpia [critica C5][critica C14].

**IV. Dos latencias medidas y publicadas.** Turno conversacional y decisión de fondo, por idioma [critica C2].

**V. Evals con audio propio y lista de fallos.** Golden set en texto en CI, golden set de audio por idioma, distribución declarada [critica C10][critica C16].

**VI. Tres entregables visibles.** Video, enlace en vivo del modo texto, repo ejecutable; landing realineada [critica C12][critica C13].

El éxito de Untangle no se mide por la cantidad de agentes ni de tecnologías, sino por que un evaluador técnico pueda seguir un siniestro desde la primera palabra hasta el registro final, ver cada decisión sostenida por una cláusula o una regla, ver dónde falla, y querer la conversación de veinte minutos.

---
