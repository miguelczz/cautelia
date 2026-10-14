# Deep Research: Untangle, sistema multiagente de seguros con voz en tiempo real

**Paso 1 de la pre-incepción.** Investigación sobre la idea, sin posición crítica (esa es el paso 2).
**Fecha:** 2026-09-15. **Método:** búsqueda web y lectura de unas 70 fuentes (documentación oficial, formularios del sector, estudios de mercado, benchmarks y comparativas de 2025 y 2026). Las referencias van entre corchetes `[n]` y se listan al final.
**Insumos:** [brief y adenda del autor](../00-brief-untangle.md), [evaluación del brief](../01-evaluacion-brief.md), copy de la landing publicada (`design-package.md`).

Convención de marcas:

- **Hecho verificado**: dato de documentación oficial, formulario del sector o estudio con metodología pública.
- **Cifra de vendor**: número publicado por un proveedor sobre su propio producto; se cita como dirección, no como verdad.
- **Hipótesis para el PVB**: conclusión de esta investigación que el Product Vision Board debe confirmar o rechazar.

---

## 1. Identidad del proyecto

Untangle es un proyecto de portafolio, funcional en su totalidad, que demuestra ingeniería de IA agéntica de nivel producción en el dominio de seguros de auto: un asegurado llama por voz (inglés o español) para reportar un siniestro (FNOL, primer aviso de siniestro) o pedir una cotización; un equipo de agentes con responsabilidades separadas captura los hechos en un registro estructurado, verifica la cobertura citando la cláusula exacta de la póliza, aplica reglas deterministas de elegibilidad o triage, y una compuerta de cumplimiento decide si el caso cierra o va a una persona. Todo queda trazado (qué agente hizo qué, con qué datos, en cuánto tiempo, a qué costo) y evaluado contra un golden set. Los datos son 100% sintéticos y el proyecto debe salir gratis.

Lo que existe hoy: la landing (`site/`, publicada). Todo lo demás está por construir. Esta investigación decide con qué.

---

## 2. El problema real: FNOL y cotización en seguros de auto

### 2.1 Por qué FNOL es el caso canónico

El primer aviso de siniestro es la interacción más frecuente, más emocional y más estructurada de la relación entre un asegurado y su aseguradora. Es captura y coordinación, no juicio: la propia industria de plataformas de IA para seguros lo formula como "la frontera de adjudicación: la IA reúne hechos y no decide cobertura" [2]. Esa frontera coincide con el principio de la landing ("los agentes reúnen, las personas deciden") y con los ajustes aprobados del brief.

La experiencia digital de siniestros es un problema abierto y medido. El estudio J.D. Power 2025 de experiencia digital en siniestros (5.958 evaluaciones de clientes de auto y hogar) encontró que recibir actualizaciones digitales adecuadas es uno de los principales impulsores de satisfacción, pero las aseguradoras lo logran solo el 22% de las veces; solo el 36% de los clientes de auto recibe actualizaciones por app; y entre quienes califican su experiencia digital como "pobre" o "regular", el 52% se plantea irse, frente al 4% de quienes la califican "excelente" [5]. En el estudio 2026 de siniestros de propiedad, el 38% reportó el FNOL por canal digital [6]. **Hecho verificado.** Implicación: un registro de caso completo, actualizable y visible (la bandeja del ajustador y la vista de caso) ataca el dolor medido, no uno inventado.

### 2.2 Estado de la voz con IA en seguros (2026)

Según FutureAGI, seguros es el tercer vertical más grande de IA de voz después de soporte y banca, y en 2026 hay seis flujos "listos para producción": intake FNOL (auto, hogar, salud), estado de siniestros y documentos, preguntas de suscripción, despacho y agendamiento de ajustadores, renovaciones y venta cruzada, y triage de fraude por patrones de lenguaje [1]. **Cifra de vendor.** El mismo texto fija umbrales operativos útiles como referencia: completitud del FNOL "por encima del 95% en los siete campos centrales es sano, por debajo del 90% el agente está perdiendo bucles de captura"; eco de datos personales por encima de 1 por 10.000 es señal de arreglo inmediato; y una latencia de primera respuesta p50 cercana a 600 ms en un pipeline hospedado [1].

Las plataformas comerciales que dominan el nicho (Parloa, PolyAI, Replicant, Sierra, Lorikeet, Floatbot, entre otras) publican métricas propias: 71,4% de automatización de tareas en interacciones de siniestros en un asegurador de salud (Inoria), 90% de reconocimiento en intake de daños con 20 tipos de siniestro (DOMCURA), 391% de retorno en tres años en un estudio encargado por PolyAI [3]. **Cifras de vendor.** Los criterios con los que esas plataformas se comparan entre sí sí son transferibles a Untangle: profundidad real del flujo FNOL (no un formulario con piel de chat), continuidad entre canales (el cliente no repite el accidente), coordinación con terceros durante la llamada, la frontera de adjudicación, y evidencia en despliegues regulados [2]; más capacidad de manejar habla superpuesta y tono emocional, integración con la plataforma de siniestros durante la llamada, y soporte multilingüe de producción [3].

### 2.3 Cotización y elegibilidad

El segundo flujo, más delgado, es la cotización. En el sector, la solicitud de auto personal se captura con el ACORD 90 (agencia, solicitante, residencia, conductores del hogar, vehículos, coberturas deseadas, historial de conducción hasta 39 meses) [9][10]. Las guías de suscripción reales de programas de auto personal definen riesgos inaceptables y casos que requieren derivación a un suscriptor: uso comercial del vehículo, conductores con DUI o conducción temeraria en los últimos tres años, pólizas canceladas por fraude, dos o más condenas por conducir bajo influencia, y "derivación requerida" para combinaciones que la guía no resuelve sola [14][15]. **Hecho verificado.** Esto valida la decisión D-012: la cotización de Untangle produce elegibilidad y derivación con reglas deterministas inspiradas en estas guías, sin tarifas actuariales.

### 2.4 Bilingüe no es un adorno

Más de 41 millones de personas hablan español en casa en Estados Unidos, y aseguradoras y agencias ya ofrecen servicio de siniestros en español; en el sector se reconoce que "un servicio de traducción telefónica no sustituye a un agente que habla español" [69]. **Hecho verificado.** Una aseguradora ficticia con canal bilingüe es un escenario realista para un evaluador del sector, y además diferencia el portafolio: casi ningún proyecto de referencia (sección 11) es bilingüe.

---

## 3. Estándares que dan credibilidad al flujo

### 3.1 ACORD 2: el esqueleto del registro FNOL

El ACORD 2 (Automobile Loss Notice) es el aviso estándar de siniestro de auto en Estados Unidos, para líneas personales y comerciales [7][8]. Sus secciones y campos, tal como los extrae un lector de documentos comercial [7]:

- Identificación: fecha, agencia, contacto, código, ID de cliente.
- Fecha y hora del siniestro.
- Aseguradora: nombre, código NAIC, número y tipo de póliza.
- Asegurado: nombre, fecha de nacimiento, teléfonos (casa, trabajo, celular), dirección, correos.
- Contacto alternativo.
- Siniestro: calle, ciudad, estado, país, descripción del lugar, descripción del accidente, si se contactó policía o bomberos, número de reporte.
- Vehículo asegurado: año, marca, modelo, tipo, VIN, placa, estado; propietario y conductor con relación al asegurado, licencia, propósito de uso, permiso; descripción del daño, silla de niño, estimado, dónde y cuándo se puede ver el vehículo, otra aseguradora.
- Otro vehículo o propiedad dañada: mismos campos más aseguradora del tercero.
- Lesionados (grupo repetible): nombre, contacto, peatón o vehículo, edad, extensión de la lesión.
- Testigos o pasajeros (grupo repetible).
- Reportado por, reportado a, observaciones.

**Hecho verificado.** **Hipótesis para el PVB:** el esquema del caso de Untangle es un subconjunto de estos campos, agrupado en "siete campos centrales" (quién, qué póliza, cuándo, dónde, qué pasó, quién más, lesiones) que el agente de Intake debe completar antes de cerrar, más los grupos repetibles. Los formularios ACORD tienen licencia; se usa la estructura de datos, no el formulario.

### 3.2 La póliza de auto personal ISO: la fuente de las cláusulas a citar

La póliza estándar de auto personal en Estados Unidos es el formulario ISO PP 00 01 (Personal Auto Policy). Hay specímenes públicos en reguladores estatales [11]. Su estructura, que el corpus sintético de Untangle debe imitar para que las citas sean verificables:

- Acuerdo y Definiciones (asegurado, auto cubierto, daño a la propiedad, lesión corporal, etc.).
- Parte A, Responsabilidad civil: acuerdo de cobertura, pagos suplementarios, exclusiones, límite de responsabilidad, otras coberturas.
- Parte B, Pagos médicos.
- Parte C, Motoristas sin seguro.
- Parte D, Cobertura por daño al auto asegurado: colisión y "otra que colisión", gastos de transporte, exclusiones, límite, pago de la pérdida, tasación. "Colisión" es el vuelco o impacto con otro vehículo u objeto; "otra que colisión" cubre objetos que caen, incendio, robo, explosión, terremoto, viento, granizo, agua, vandalismo, animales y vidrios [12][13].
- Parte E, Deberes después de un accidente o pérdida: aviso oportuno de cómo, cuándo y dónde, nombres de lesionados y testigos, cooperación, envío de documentos, proteger el vehículo, permitir inspección.
- Parte F, Disposiciones generales: fraude, acción legal, subrogación, período y territorio, terminación.

**Hecho verificado en estructura; el detalle de exclusiones se toma del specimen al diseñar el corpus.** **Hipótesis para el PVB:** cada póliza sintética se escribe con esta estructura y con numeración estable de cláusulas (por ejemplo `PART-D.EXCL.3`), de modo que el agente de verificación cite `Parte D, Exclusión 3` y una eval pueda comprobar que la cláusula existe y sostiene la respuesta. Dos o tres aseguradoras ficticias varían límites, deducibles, exclusiones y endosos, y así la misma llamada produce respuestas distintas por tenant.

---

## 4. Arquitectura multiagente: estado del arte y elección

### 4.1 Los tres frameworks que el brief menciona y uno más

Las comparativas de 2026 coinciden en el reparto: LangGraph modela agentes como máquinas de estados explícitas sobre un grafo, con control total de cada transición; CrewAI usa la metáfora de equipo con roles y tareas declarativas; el OpenAI Agents SDK es la abstracción más delgada, con handoffs imperativos [16][17][18]. LangGraph es el más probado en producción, con casos públicos de Klarna (asistente para 85 millones de usuarios, 80% menos tiempo de resolución), Uber (red de agentes para migraciones de código, unas 21.000 horas de desarrollador ahorradas) y LinkedIn (SQL Bot multiagente) [19]. **Hecho verificado en los casos oficiales; los porcentajes son cifras de las empresas.** La migración más común es de CrewAI a LangGraph cuando el prototipo choca con el techo de control de flujo de CrewAI [18].

Lo que decide para Untangle no es la popularidad sino el ajuste 1 aprobado: "el orquestador es código, no un agente con prompt". LangGraph permite pausar el grafo con `interrupt()`, guardar el estado exacto con un checkpointer y reanudar con `Command(resume=...)` usando el mismo `thread_id` como cursor persistente; la documentación lo describe como ejecución durable, con patrones de aprobación (aprobar o rechazar antes de una acción), revisión y edición de estado, y aprobación de llamadas a herramientas [20]. **Hecho verificado.** Eso es exactamente la compuerta de cumplimiento y la bandeja del ajustador: un `interrupt()` antes de cerrar el caso, y el humano reanuda con aprobación o rechazo.

### 4.2 Un patrón de referencia: tres capas

Un ejemplo publicado en enero de 2026 combina Twilio, Pipecat y LangGraph para un agente de voz con barreras de política, en tres capas: la capa de voz maneja audio y turnos sin autoridad de decisión; el modelo "interpreta, no actúa" (sin herramientas ni ejecución); y LangGraph aplica las políticas: "las acciones están bloqueadas por defecto; si una ruta no está explícitamente enrutada, es inalcanzable" [21]. **Hecho verificado.** **Hipótesis para el PVB:** Untangle adopta esta separación. Los cuatro agentes (Intake, Verificación, Decisión, Cumplimiento) son nodos con herramientas y esquemas de salida propios; el grafo decide rutas; ninguna acción sobre el caso ocurre fuera de una ruta explícita.

### 4.3 Integración voz y grafo

LiveKit publica un plugin oficial (`livekit-plugins-langchain`) cuyo `LLMAdapter` envuelve un grafo compilado de LangGraph como LLM del agente de voz, convirtiendo el contexto de chat de LiveKit en mensajes de LangChain y transmitiendo los tokens del grafo al pipeline de voz [22]. Hay incidencias abiertas sobre streaming de subgrafos y compatibilidad de versiones [23], así que la integración es viable pero debe probarse temprano (esqueleto andante). Existen además adaptadores comunitarios y un demo oficial de LangChain con tres backends de voz (LiveKit, OpenAI Realtime, Google ADK Live) instrumentados para LangSmith [68]. **Hecho verificado.**

---

## 5. Voz en tiempo real

### 5.1 Cascada frente a voz a voz

Hay dos arquitecturas: la cascada STT → LLM → TTS, y los modelos nativos de voz a voz (OpenAI Realtime, Gemini Live). En 2026 la cascada domina los despliegues de producción; da transparencia, permite cambiar cada capa por la mejor disponible y, sobre todo, conserva acceso total al prompt, a las definiciones de herramientas y al proceso de decisión del LLM, lo que los modelos voz a voz vuelven opaco [24][25]. Una cascada bien construida, con TTS que emite el primer audio en 100 a 250 ms, puede igualar o superar a modelos extremo a extremo en latencia voz a voz; el LLM domina el presupuesto [25]. **Hecho verificado.** Para Untangle la cascada es obligatoria: sin acceso al texto no hay citación de cláusulas, ni reglas deterministas, ni trazas por agente.

### 5.2 LiveKit Agents frente a Pipecat

Ambos son frameworks abiertos que aportan la orquestación de voz (VAD, endpointing, barge-in, streaming entre etapas) y dejan que tú elijas STT, LLM y TTS como plugins intercambiables [27]. Diferencias que importan aquí [26][28][27]:

- LiveKit Agents se apoya en el servidor WebRTC de LiveKit: estado de sesión, reconexión y transporte de baja latencia vienen de la capa RTC; incluye un modelo abierto de detección de turno; es la opción natural para WebRTC nativo, multiparticipante y auto-hospedado.
- Pipecat modela el agente como un pipeline de procesadores por el que fluyen audio y texto; da más control a nivel de pipeline para afinar latencia y calidad; es más verboso; es la opción natural para agentes telefónicos o de un solo usuario donde se quiere "ser dueño del pipeline".

La recomendación general de la literatura: "por defecto, el framework de código abierto: conservas control de datos, proveedores y lógica sin reconstruir la fontanería" [27]. **Hipótesis para el PVB:** la decisión LiveKit o Pipecat se toma como ADR en Incepción, con dos criterios dominantes: la integración con LangGraph (LiveKit tiene plugin oficial; Pipecat tiene el ejemplo de tres capas) y el costo cero (ambos tienen nube con tier gratuito y ambos se auto-hospedan; ver sección 10).

### 5.3 Detección de fin de turno e interrupciones

La detección de fin de turno es el cuello de botella real, como dice la landing. Dos modelos abiertos lo resuelven con señal semántica encima del VAD:

- El turn detector de LiveKit codifica el audio del usuario para capturar significado y señales acústicas (entonación, ritmo) y evitar interrumpir en pausas naturales; soporta 14 idiomas incluido español; permite acortar el endpointing mínimo de 0,5 s a 0,3 s [29].
- Smart Turn v3 de Pipecat es un modelo abierto (BSD-2) con inferencia en CPU en 12 ms en un CPU moderno y unos 60 ms en una instancia barata; soporta 23 idiomas incluido español; corre local sin red [30].

**Hecho verificado.** Ambos cubren los dos idiomas del proyecto (D-009).

Métricas de interrupción que la industria usa: latencia de parada (el agente debe callarse en unos 200 ms desde que el usuario habla) y tasa de recuperación (reconocer y atender la interrupción más del 90% de las veces) [55]. La guía de pruebas de FNOL de Roark añade fallos concretos a testear: el agente "habla encima del llamante tres veces", "4,2 segundos de silencio después de una pregunta sobre lesiones", tono plano ante alguien que llora, y "un agente FNOL que se niega a escalar es peor que uno que nunca contesta" [4]. **Hecho verificado como práctica del sector.**

### 5.4 Presupuesto de latencia

Los umbrales que la industria repite: por debajo de 500 ms el agente se siente ágil, por debajo de 800 ms aceptable, por encima de 1 s se siente mal, por encima de 1,5 s la conversación "se rompe" [31][34]. La brecha humana entre turnos (transition relevance place) ronda 200 a 250 ms en todas las lenguas [31]. Un turno típico bajo 800 ms se descompone en red 20 a 100 ms, primer parcial de STT 100 a 300 ms, primer token del LLM 200 a 600 ms, primer audio del TTS 150 a 400 ms, y orquestación 20 a 50 ms [33]. Métricas formales: tiempo al primer audio desde el fin del silencio del usuario (turn latency), con "P95 < 800 ms bueno, 800 a 1.500 ms alerta, > 1.500 ms crítico" [32]. **Hecho verificado como consenso de la industria.** Esto convierte el "round-trip bajo 700 ms" del brief en una métrica definida: turn latency p50 y p95 sobre el golden set de voz, por idioma.

### 5.5 Proveedores STT con español

- Deepgram Nova-3: soporta español y transcribe conversaciones con cambio de idioma en tiempo real entre 10 lenguas (incluidas inglés y español) sin enrutamiento explícito; una actualización de 2026 redujo el WER medio en streaming alrededor de 21% relativo, con las mayores ganancias en cambio de idioma; time-to-final por debajo de 300 ms; streaming multilingüe alrededor de 0,0058 dólares por minuto; 200 dólares de crédito gratis sin tarjeta [37][35][61]. **Hecho verificado en documentación de Deepgram; los WER son cifras del proveedor.**
- ElevenLabs Scribe v2 Realtime: unos 150 ms de primer parcial en más de 90 idiomas [35][36].
- AssemblyAI streaming: unos 760 ms de time-to-final en datasets mixtos, con mejor inteligencia de transcripción [35].
- Código abierto: Whisper large-v3 y su variante turbo cubren bien español (un ajuste fino sobre Common Voice bajó el WER de 6,91% a 5,34%) [39]; NVIDIA Parakeet TDT es el estándar abierto de baja latencia pero centrado en inglés; Canary y Nemotron soportan streaming con latencia configurable desde 80 ms [40]. **Hecho verificado.**

### 5.6 Proveedores TTS con español

- Cartesia Sonic: 40 a 90 ms de tiempo al primer audio en condiciones óptimas, p99 alrededor de 110 ms bajo carga; 44 idiomas con varios locales de español; streaming por WebSocket; plan gratuito [41][42][61]. **Cifras de vendor y benchmarks de terceros.**
- ElevenLabs Flash: 75 a 120 ms; la mayor cobertura de voces; el tier gratuito (10.000 caracteres al mes) es no comercial [41][62].
- Código abierto: Kokoro (82M parámetros, español entre 9 idiomas, corre en CPU, Apache 2.0) y Chatterbox Turbo (350M, español entre 9 idiomas, unos 75 ms, MIT) [43]. **Hecho verificado.**

### 5.7 Diseño bilingüe

Dos opciones compatibles con D-009: (a) selección de idioma al inicio de la llamada ("para español, diga español"), que fija STT, TTS y prompts por idioma y simplifica las evals; (b) detección automática con un STT que soporte cambio de idioma (Nova-3) y voz TTS por idioma. **Hipótesis para el PVB:** empezar con (a) por control y medición; dejar (b) como mejora. En cualquier caso: dos golden sets (uno por idioma), dos voces, prompts localizados, y la divulgación legal (sección 9) en el idioma de la llamada.

---

## 6. RAG sobre pólizas con citación de cláusula

### 6.1 Por qué la citación es el diferenciador y dónde falla

En seguros, un sistema de triage con RAG "puede fallar citando cláusulas de póliza que no existen, creando exposición a litigio de mala fe cuando las citas no se pueden reconciliar con los fragmentos recuperados", y debe verificarse "si la respuesta usa la póliza recuperada o la ignora en favor de suposiciones del modelo" [44]. La investigación distingue corrección de fidelidad: una respuesta puede ser correcta y aun así no estar sostenida por lo recuperado [46]. La evaluación práctica descompone la respuesta en afirmaciones y comprueba cada una contra el contexto recuperado; la lista de afirmaciones no soportadas dice si el fallo es de generación (el contexto tenía el dato y el modelo lo ignoró) o de recuperación (el contexto nunca lo tuvo) [45]. **Hecho verificado.**

**Hipótesis para el PVB:** tres controles en cascada: (1) el índice guarda cada cláusula con identificador estable; (2) el agente de verificación solo puede responder con identificadores de cláusula recuperados, o con "no encuentro cláusula que lo cubra"; (3) una eval de precisión de citación comprueba que cada cláusula citada existe y sostiene la afirmación (LLM como juez con rúbrica, más verificación exacta del identificador). Esto es lo que convierte una decisión en "defendible" ante un evaluador técnico.

### 6.2 Embeddings bilingües

Para un corpus en inglés con consultas en español (o viceversa) hacen falta embeddings multilingües. BGE-M3 (abierto) cubre más de 100 idiomas y combina recuperación densa, dispersa y multivector en un solo modelo con contexto de 8K, adecuado para documentos legales y sistemas translingües [47]; multilingual-E5 es la alternativa abierta consolidada [47]; Gemini Embedding soporta más de 100 idiomas, se puede usar sin costo en AI Studio y cuesta 0,15 dólares por millón de tokens en producción [48]. **Hecho verificado.** Búsqueda híbrida (denso más disperso) y un reranker son práctica estándar; BGE-M3 ofrece ambos vectores sin segundo modelo.

### 6.3 Dónde guardar los vectores

pgvector con índice HNSW cierra la brecha con bases vectoriales dedicadas para cargas por debajo de unos pocos millones de vectores, y Postgres es la única opción que da aislamiento por filas con garantías ACID de serie [50][49]. Qdrant Cloud ofrece un clúster gratuito de 1 GB [63]. **Hecho verificado.** Para un corpus de decenas de pólizas por tenant, pgvector en el mismo Postgres del caso es la opción más simple y la que hace del aislamiento multi-tenant un solo mecanismo (sección 7).

---

## 7. Multi-tenant proporcional

La literatura de RAG multi-tenant en Postgres converge en un principio: "tu cláusula WHERE no es un límite de seguridad"; el aislamiento se lleva a la base de datos con políticas de Row-Level Security que restringen cada fila a `current_setting('app.tenant_id')`, de modo que un WHERE olvidado no devuelve filas de otro tenant [49]. Trampas documentadas: no usar statement pooling con RLS (la variable de sesión se pierde o se mezcla), marcar funciones confiables como `LEAKPROOF`, y usar pgvector 0.8 o superior para escaneos iterativos de índice con filtros [49]. **Hecho verificado.** **Hipótesis para el PVB:** `tenant_id` en todas las tablas (casos, pólizas, cláusulas, vectores, políticas de cumplimiento), RLS activo, y un contexto de tenant que se fija por conexión desde el token de la llamada. Sin Keycloak en la primera versión salvo que resulte barato; la ganancia demostrable es que dos aseguradoras ficticias reciben respuestas distintas con la misma llamada.

---

## 8. Observabilidad y evals

### 8.1 Trazas: Langfuse frente a Arize Phoenix

Ambos son abiertos y gratuitos de auto-hospedar. Langfuse creció como plataforma de ingeniería LLM de producción (trazas, gestión de prompts, datasets, evals, dashboards de costo), MIT sin funciones bloqueadas, con nube que tiene un plan gratuito (50.000 unidades al mes, 30 días de acceso a datos, 2 usuarios, sin tarjeta) [51][52]. Phoenix nació de la observabilidad de ML de Arize, es local-first, corre con un `pip install`, y su fortaleza es la evaluación de RAG y la comparación de experimentos, sobre las convenciones OpenInference [51][53]. La pregunta que decide es: "¿necesitas monitoreo de producción y gobierno de prompts (Langfuse) o evaluación profunda y comparación de experimentos (Phoenix)?" [51]. **Hecho verificado.**

Estándares: las convenciones semánticas GenAI de OpenTelemetry (v1.40.0, febrero de 2026) siguen en estado "Development", con los atributos centrales estables desde v1.37 y spans de agente y MCP como novedad; Langfuse acepta trazas por un endpoint OTLP completo; Phoenix usa OpenInference y traduce [53]. **Hecho verificado.** **Hipótesis para el PVB:** instrumentar con OpenTelemetry y convenciones GenAI, para que el destino (Langfuse o Phoenix) sea un ADR reversible. El dashboard visible en la demo puede ser el de la herramienta; la vista de caso de Untangle muestra la traza por agente con costo y latencia.

### 8.2 Evals de agentes y RAG

Tres herramientas abiertas dominan el lado práctico: promptfoo (YAML, gating en CI), DeepEval (estilo pytest) y RAGAS (métricas de RAG como fidelidad y relevancia); Inspect AI se especializa en evaluación de agentes a escala [54]. El patrón experimentado es usar dos: un framework ligero para gating en CI y una plataforma para anotación humana y seguimiento de regresiones [54]. LLM como juez tiene sesgos publicados que hay que diseñar alrededor [54]. **Hecho verificado.**

### 8.3 Evals de voz

Las plataformas de simulación de voz (Coval, Hamming, Cekura, Bluejay, Roark) generan llamantes sintéticos con ruido, acento y barge-in a mitad de frase, y detectan problemas de tiempo invisibles en evaluación solo de texto [55]. Son de pago. La práctica recomendada es un golden set de 50 o más llamadas con resultados esperados, corrido completo antes de cada despliegue [55]. La limitación de un stack abierto es la ausencia de audio: "una transcripción limpia puede representar una llamada con una pausa p95 de 4 segundos" [55]. **Hecho verificado.** **Hipótesis para el PVB:** golden set en texto (determinista, en CI) para completitud del registro, precisión de citación, reglas y derivaciones; más un golden set pequeño de audio grabado por idioma para latencia de turno, latencia de parada y recuperación tras interrupción, medido con las trazas propias. Métricas y umbrales de referencia: turn latency p95 < 800 ms, tiempo al primer audio < 400 ms, WER < 10%, tasa de alucinación < 1%, tasa de éxito de tarea > 85% [32].

---

## 9. Cumplimiento y ética: qué se afirma y qué no

- **NAIC.** El Model Bulletin sobre uso de sistemas de IA por aseguradoras (diciembre de 2023) pide un programa documentado de gobierno de IA en suscripción, tarifación, siniestros, fraude y marketing; lo han adoptado 25 estados y el Distrito de Columbia, y en 2026 corre un piloto en 12 estados de una herramienta de evaluación de sistemas de IA [56]. California, Colorado, Nueva York y Texas tienen marcos propios [56]. **Hecho verificado.**
- **EU AI Act.** El Anexo III clasifica como alto riesgo los sistemas de "evaluación de riesgo y fijación de precios de personas naturales en seguros de vida y salud"; auto no está en esa lista, pero las obligaciones de transparencia y supervisión humana son el patrón a imitar; las fechas de aplicación de alto riesgo (2 de agosto de 2026) podrían moverse a 2027 y 2028 si se adopta el Digital Omnibus [57]. **Hecho verificado.**
- **Divulgación y grabación.** La FCC clasificó las voces de IA como robocalls bajo TCPA (febrero de 2024); California exige divulgación verbal de IA en llamadas automatizadas desde el 1 de enero de 2025 y es estado de consentimiento de todas las partes; alrededor de 11 estados exigen consentimiento de todas las partes para grabar; Utah exige divulgar IA si el consumidor pregunta y de forma proactiva en profesiones reguladas; la Ley de IA de Colorado (1 de febrero de 2026) extiende obligaciones a sistemas de decisión automatizada de alto riesgo [58]. **Hecho verificado en resúmenes legales; se citará como "inspirado en", no como asesoría.**
- **Datos personales.** Microsoft Presidio (abierto, 49 idiomas incluido español, reconocedores configurables) es el estándar de facto para detección y redacción de PII; se puede enganchar como guardrail de LiteLLM en modo "solo logging" para enmascarar antes de enviar a Langfuse [59]. Los datos de voz se replican en transcripciones parciales, transcripción final, grabaciones, logs, trazas y contexto del LLM, y hay que redactar en cada punto [59]. **Hecho verificado.**

**Hipótesis para el PVB (principios no negociables):** (1) el agente se presenta como IA y anuncia la grabación al inicio, en el idioma de la llamada; (2) nunca decide cobertura ni dinero; (3) siempre existe una ruta a una persona; (4) PII redactada en trazas y logs aunque sea sintética; (5) el README declara "inspirado en NAIC, TCPA y EU AI Act", nunca "cumple con".

---

## 10. Costo cero: mapa de tiers gratuitos (septiembre de 2026)

Todo lo siguiente son condiciones publicadas por los proveedores en la fecha de esta investigación; cambian sin aviso (Oracle recortó su Always Free ARM de 4 OCPU/24 GB a 2 OCPU/12 GB en junio de 2026 sin anunciarlo [64]). Se verifica de nuevo en los ADRs.

| Capa | Opción gratuita | Condición | Alternativa abierta (costo cero en tu máquina) |
|---|---|---|---|
| LLM | Google AI Studio (Gemini Flash) | Sin tarjeta; los datos del tier gratuito se usan para mejorar productos de Google; límites visibles en el panel de AI Studio [60] | Modelos abiertos por Groq (llama-3.3-70b: 30 RPM, 1.000 RPD, 12K TPM, 100K TPD), OpenRouter (modelos `:free`, 20 RPM, 50 RPD sin crédito), Mistral Experiment (~1B tokens/mes con opt-in de entrenamiento) [60] |
| STT | Deepgram, 200 dólares de crédito sin tarjeta [61] | Español y cambio de idioma en Nova-3 [37] | Whisper large-v3 turbo local [39] |
| TTS | Cartesia, plan gratuito con todas las funciones [61][62] | Español con varios locales [42] | Kokoro (CPU, Apache 2.0) o Chatterbox Turbo (MIT) [43] |
| Transporte de voz | LiveKit Cloud Build: 5.000 minutos WebRTC, 1.000 minutos de agente, 2,50 dólares de inferencia [61]. Daily: 10.000 minutos-participante al mes; Pipecat Cloud: minutos gratis para 1 humano y 1 bot con la clave de Daily de la cuenta [61] | Ambos frameworks se auto-hospedan | LiveKit server o Pipecat en local |
| Detección de turno | Modelo de LiveKit o Smart Turn v3 | Ambos abiertos, español incluido [29][30] | Local, CPU |
| Base de datos | Neon: 100 proyectos de 0,5 GB, 100 CU-h/mes, scale-to-zero. Supabase: 2 proyectos de 500 MB con auth y storage [63] | pgvector disponible en ambos [50] | Postgres en Docker local |
| Vectores | pgvector en la misma base; Qdrant Cloud 1 GB gratis si se prefiere dedicado [63] | | pgvector |
| Embeddings | Gemini Embedding en AI Studio [48] | | BGE-M3 local [47] |
| Trazas | Langfuse Cloud Hobby: 50.000 unidades/mes, 30 días, 2 usuarios [52]. Phoenix local gratis [51] | | Langfuse self-host (MIT) |
| Evals | promptfoo, DeepEval, RAGAS, Inspect (abiertos) [54] | El juez LLM consume cuota del LLM gratuito | |
| PII | Presidio (abierto) [59] | | |
| Hosting | Render: 750 horas de instancia al mes, se duerme a los 15 minutos; Google Cloud Run tier gratuito; Hugging Face Spaces; Oracle Always Free (2 OCPU/12 GB, con escasez de capacidad) [64] | Fly.io y Railway ya solo tienen prueba [64] | Para el video demo basta correr en local |

Referencia de costo si algo se paga: un stack crudo STT más LLM más TTS cuesta entre 0,007 y 0,091 dólares por minuto de conversación, y telefonía unos 0,014 dólares por minuto [65]. Un golden set de 60 llamadas de 4 minutos cuesta centavos; el riesgo de costo está en desarrollar con iteración intensiva sobre APIs de pago, no en la demo. **Hecho verificado en precios publicados.** **Hipótesis para el PVB:** desarrollo y evals en texto con LLM gratuito y modelos abiertos locales; voz con créditos gratuitos de Deepgram y Cartesia y el tier de LiveKit o Daily; grabación del video en local. Cero gasto obligatorio.

---

## 11. Qué buscan los empleadores y cómo se diferencia Untangle

### 11.1 Señales que revisan

Las guías de portafolio de 2026 repiten lo mismo: "un proyecto RAG de producción con evals apropiadas vale más que cinco clones de tutorial"; los gerentes de contratación escanean en unos 90 segundos buscando observabilidad, manejo de errores, rigor de evals y un enlace en vivo; los entrevistadores de forward-deployed engineers buscan "pensamiento de producción: manejo de errores, observabilidad, control de acceso, degradación elegante, y si el proyecto maneja modos de fallo o solo funciona cuando todo sale bien"; y "casi ningún candidato mide si su app funciona, así que un proyecto con un pequeño golden set, una puntuación de aprobado o fallo y una lista honesta de fallos destaca de inmediato" [66]. **Hecho verificado como consenso de guías; no es un estudio.** La demanda existe: las ofertas de "agentic AI" crecieron 280% interanual hasta unas 90.000 en Estados Unidos; el AI Index 2026 de Stanford registró un salto de 151 a más de 16.500 ofertas que mencionan "agentic systems" entre 2024 y 2025; LinkedIn puso "AI Engineer" como el título de más rápido crecimiento en 2026 [67]. **Cifras de informes de terceros.**

### 11.2 Lo que ya existe en abierto y lo que no hace

Proyectos de referencia: el demo oficial de LangChain con tres backends de voz [68]; adaptadores LangGraph a LiveKit comunitarios [68][23]; el ejemplo de tres capas con Twilio, Pipecat y LangGraph [21]; y la colección de ejemplos de LiveKit [68]. Ninguno de los encontrados tiene, al mismo tiempo: un corpus de dominio con citación verificable de cláusulas, reglas deterministas separadas del modelo, una compuerta de cumplimiento con bandeja humana, aislamiento multi-tenant, golden sets con reporte honesto, y bilingüismo. **Hecho verificado por ausencia en la búsqueda; puede existir algo no indexado.** Esa combinación, y no cualquiera de sus partes, es la diferenciación de Untangle.

---

## 12. Riesgos que esta investigación deja a la vista

Se desarrollan en el paso 2 (crítica). Aquí solo se enumeran:

1. La integración voz y grafo (LLMAdapter) tiene incidencias abiertas; puede forzar un adaptador propio.
2. Los tiers gratuitos cambian sin aviso; el proyecto necesita un modo "todo local" como red de seguridad.
3. Un LLM gratuito con límites de RPM y RPD puede ser demasiado lento o escaso para voz en tiempo real; puede hacer falta un modelo rápido de pago para la grabación de la demo.
4. La calidad en español de STT y TTS abiertos es inferior a la comercial; hay que medirla, no asumirla.
5. LLM como juez tiene sesgos; la precisión de citación necesita un check exacto además del juez.
6. El corpus sintético debe parecer una póliza real (estructura ISO) sin copiar texto con derechos.
7. Sin audio en las evals, la latencia y las interrupciones solo se miden con trazas propias; hay que instrumentarlas bien desde el esqueleto.
8. El alcance sigue siendo grande para una persona; el esqueleto andante en texto es la protección.

---

## 13. Decisiones que el PVB debe tomar

| # | Decisión | Opciones que deja esta investigación |
|---|---|---|
| 1 | Framework de agentes | LangGraph (hipótesis) frente a CrewAI u OpenAI Agents SDK |
| 2 | Framework de voz | LiveKit Agents frente a Pipecat; criterio: integración con el grafo y costo cero |
| 3 | Detección de turno | LiveKit turn detector o Smart Turn v3 (ligado a la anterior) |
| 4 | STT y TTS por idioma | Deepgram Nova-3 y Cartesia (créditos gratuitos) con fallback local Whisper y Kokoro |
| 5 | Selección de idioma | Al inicio de la llamada (hipótesis) o detección automática |
| 6 | Almacenamiento | Postgres con pgvector y RLS (hipótesis) frente a Qdrant separado |
| 7 | Embeddings | BGE-M3 local (hipótesis) o Gemini Embedding |
| 8 | Trazas | Langfuse (hipótesis) o Phoenix; instrumentación OpenTelemetry en ambos casos |
| 9 | Evals | promptfoo o DeepEval en CI, más golden set de audio propio |
| 10 | Esquema del caso | Subconjunto de ACORD 2 con siete campos centrales y grupos repetibles |
| 11 | Corpus | 2 a 3 aseguradoras ficticias con pólizas de estructura ISO PP 00 01 y cláusulas numeradas |
| 12 | Superficie humana | Bandeja del ajustador con aprobar o rechazar sobre `interrupt()` |
| 13 | LLM | Gemini Flash gratuito para desarrollo y evals; decidir el modelo de la demo grabada |
| 14 | Hosting de la demo | Local para el video; opcional Render o Cloud Run para un enlace en vivo |

---

## Fuentes

1. FutureAGI, "Voice AI for Insurance: Claims Intake, Underwriting Calls, and Compliance in 2026": https://futureagi.com/blog/voice-ai-insurance-claims-underwriting-2026/
2. Lorikeet, "Best AI Platforms for Insurance Claims and FNOL (2026)": https://www.lorikeetcx.ai/articles/best-ai-insurance-claims-fnol-2026
3. Parloa, "Best Voice AI for Claim Intake Automation in 2026": https://www.parloa.com/knowledge-hub/best-voice-ai-claim-intake-automation/
4. Roark, "Testing voice agents for FNOL: a QA playbook for insurance claims intake": https://roark.ai/blog/testing-voice-agents-fnol-insurance-claims-intake
5. J.D. Power, "2025 U.S. Claims Digital Experience Study": https://www.jdpower.com/business/press-releases/2025-us-claims-digital-experience-study
6. Claims Journal, "JD Power: Homeowners Claims Satisfaction Rises as Repair Times Improve" (estudio 2026): https://www.claimsjournal.com/news/national/2026/03/18/336327.htm
7. ABBYY, "ACORD 2 Automobile Loss Notice - Document Skill" (lista de campos): https://docs.abbyy.com/vantage/documentation/skill-catalog/built-in-skills/acord-2
8. Florida CFO, formulario ACORD 2 (specimen público): https://myfloridacfo.com/docs-sf/rehabilitation-and-liquidation-libraries/rehab-static/acord-form-2-automobile-loss-notice.pdf?sfvrsn=d233d94a_2
9. Infrrd, "ACORD 90 Explained: Personal Auto Insurance Application": https://www.infrrd.ai/blog/acord-90-form
10. Docsumo, "Definition of Acord 90": https://www.docsumo.com/blog/acord-90-processing
11. Virginia SCC, specimen ISO PP 00 01 09 18: https://www.scc.virginia.gov/media/sccvirginiagov-home/regulated-industries/insurance/insurance-companies/property-casualty-companies/personal-commercial-auto-forms/pp-00-01-09-18.pdf
12. PropertyCasualty360, "Personal Auto Policy Contract Analysis Part 5 - Coverage for Damage to Your Auto": https://www.propertycasualty360.com/fcs/2022/10/10/personal-auto-policy-contract-analysis-part-5-coverage-for-damage-to-your-auto/
13. Rough Notes, "PF&M at a Glance: Personal auto policy": https://roughnotes.com/rnmagazine/2005/january05/01p72.htm
14. GAINSCO, "Indiana Private Passenger Automobile Underwriting Guidelines": https://www.gainsco.com/wp-content/uploads/2021/12/IN-MGA-Personal-Auto-Program-Rules-Manual.pdf
15. National General, "North Carolina Private Passenger Auto Underwriting Guide" (2026): https://uwguides.nationalgeneral.com/ppa/nc/uwg_nc_ig_ii_ip_ppa.pdf
16. Requesty, "Best AI Agent SDKs Compared (2026)": https://www.requesty.ai/blog/best-ai-agent-sdks-compared-2026-langchain-crewai-openai-anthropic-google
17. Codebridge, "LangGraph vs CrewAI vs OpenAI Agents SDK: 2026 Guide": https://www.codebridge.tech/articles/choosing-a-multi-agent-framework-langgraph-crewai-microsoft-agent-framework-or-openai-agents-sdk
18. Particula, "LangGraph vs CrewAI vs OpenAI Agents SDK: 2026 Comparison": https://particula.tech/blog/langgraph-vs-crewai-vs-openai-agents-sdk-2026
19. LangChain, "Case studies" y "Built with LangGraph": https://docs.langchain.com/oss/python/langgraph/case-studies y https://www.langchain.com/built-with-langgraph
20. LangChain, "Interrupts" (LangGraph): https://docs.langchain.com/oss/python/langgraph/interrupts
21. WebRTC.ventures, "Building a Voice AI Agent with Policy Guardrails Using Twilio, Pipecat, and LangGraph" (enero 2026): https://webrtc.ventures/2026/01/building-a-voice-ai-agent-with-policy-guardrails-using-twilio-pipecat-and-langgraph/
22. LiveKit, "LangChain integration guide": https://docs.livekit.io/agents/models/llm/langchain/
23. LiveKit Agents, incidencias #3111 y #3634: https://github.com/livekit/agents/issues/3111 y https://github.com/livekit/agents/issues/3634
24. AssemblyAI, "Speech-to-Speech Voice Agents: Cascaded vs End-to-End": https://www.assemblyai.com/blog/speech-to-speech-for-voice-agents
25. Gradium, "Cascaded Voice Agents vs Speech-to-Speech: Architecture Tradeoffs in 2026": https://gradium.ai/content/cascaded-voice-agent-vs-speech-to-speech-2026
26. Forasoft, "Pipecat vs LiveKit vs OpenAI: Voice Agent Frameworks": https://www.forasoft.com/blog/article/pipecat-vs-livekit-agents
27. Soniox, "Voice agent frameworks: Pipecat, LiveKit Agents, and friends": https://soniox.com/wiki/voice-agent-frameworks
28. Cekura, "Pipecat vs. LiveKit - Key Differences": https://www.cekura.ai/blogs/pipecat-vs-livekit-the-real-difference
29. LiveKit, "Turn detector" (documentación): https://docs.livekit.io/agents/build/turns/turn-detector/
30. Daily, "Announcing Smart Turn v3, with CPU inference in just 12ms" y repositorio: https://www.daily.co/blog/announcing-smart-turn-v3-with-cpu-inference-in-just-12ms/ y https://github.com/pipecat-ai/smart-turn
31. Hamming, "Voice AI Latency: What's Fast, What's Slow, and How to Fix It": https://hamming.ai/resources/voice-ai-latency-whats-fast-whats-slow-how-to-fix-it
32. Hamming, "Voice Agent Evaluation Metrics: Definitions, Formulas & Benchmarks": https://hamming.ai/resources/voice-agent-evaluation-metrics-guide
33. Twilio, "Core Latency in AI Voice Agents": https://www.twilio.com/en-us/blog/developers/best-practices/guide-core-latency-ai-voice-agents
34. DEV, "Your voice agent has 300ms before users bail": https://dev.to/kenimo49/your-voice-agent-has-300ms-before-users-bail-the-three-latency-cliffs-that-kill-voice-ux-416c
35. FutureAGI, "Speech-to-Text APIs in 2026: Benchmarks, Pricing, and a Developer's Decision Guide": https://futureagi.com/blog/speech-to-text-apis-in-2026-benchmarks-pricing-developer-s-decision-guide/
36. Gradium, "STT API Benchmark 2026: Latency and Accuracy for Voice Agents": https://gradium.ai/content/stt-api-benchmark-2026-latency-accuracy
37. Deepgram, "Nova-3 with 10 New Languages and Multilingual Keyterm Prompting", "Nova-3 Multilingual: Major WER Improvements" y precios: https://deepgram.com/learn/deepgram-expands-nova-3-with-10-new-languages-and-multilingual-keyterm-prompting , https://deepgram.com/learn/nova-3-multilingual-major-wer-improvements-across-languages , https://convertaudiototext.com/blog/deepgram-nova-3-explained
38. Deepgram, discusión "Optimizing Streaming Accuracy for Spanish/Bilingual Voice Agents": https://github.com/orgs/deepgram/discussions/1605
39. Hugging Face, "whisper-large-v3-turbo-es" (ajuste fino en español): https://huggingface.co/adriszmar/whisper-large-v3-turbo-es
40. Seven Labs, "Best Open Source Speech-to-Text Models in 2026" y Northflank, "Best open source STT model in 2026": https://www.sevenlabs.site/blogs/best-open-source-speech-to-text-models-2026 y https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks
41. Gradium, "TTS Latency Benchmark 2026" y DEV, "Benchmarking Real-Time Voice AI APIs: Cartesia vs Deepgram vs ElevenLabs (2026)": https://gradium.ai/content/tts-latency-benchmark-2026 y https://dev.to/mrzitoun/benchmarking-real-time-voice-ai-apis-cartesia-vs-deepgram-vs-elevenlabs-2026-2n8c
42. Cartesia, "All languages" y "Sonic": https://cartesia.ai/all-languages y https://www.cartesia.ai/sonic
43. Pinggy, "Best Open Source Self-Hosted Text-to-Speech Models in 2026" y Seven Labs, "Best Self-Hosted TTS Models in 2026": https://pinggy.io/blog/best_open_source_self_hosted_text_to_speech_models/ y https://www.sevenlabs.site/blogs/best-self-hosted-tts-models-2026
44. FutureAGI, "Best 5 RAG Evaluation Tools for Insurance AI Applications in 2026" y "What Is RAG Faithfulness?": https://futureagi.com/blog/best-insurance-rag-evaluation-2026/ y https://futureagi.com/glossary/rag-faithfulness/
45. Langfuse, "How to evaluate RAG faithfulness with LLM-as-a-judge": https://langfuse.com/resources/engineering/rag-faithfulness-evaluation
46. Wallat et al., "Correctness is not Faithfulness in Retrieval Augmented Generation Attributions" (2025): https://staff.fnwi.uva.nl/m.derijke/wp-content/papercite-data/pdf/wallat-2025-correctness.pdf
47. BGE M3-Embedding (arXiv), Multilingual E5 Technical Report (arXiv) y FutureAGI, "Best Embedding Models 2026": https://arxiv.org/html/2402.03216v3 , https://arxiv.org/pdf/2402.05672 , https://futureagi.com/blog/best-embedding-models-2025/
48. Google Developers Blog, "Gemini Embedding now generally available in the Gemini API": https://developers.googleblog.com/gemini-embedding-available-gemini-api/
49. TigerData, "Building Multi-Tenant RAG Applications With PostgreSQL"; DEV, "Your WHERE clause is not a security boundary"; Bhandari, "Hard Multi-Tenancy for pgvector": https://www.tigerdata.com/blog/building-multi-tenant-rag-applications-with-postgresql-choosing-the-right-approach , https://dev.to/virginiamwega2svg/your-where-clause-is-not-a-security-boundary-multi-tenant-rag-with-pgvector-rls-28fk , https://pradeepbhandari.com/blog/pgvector-multi-tenancy-postgresql-rls-guide
50. Week One Labs, "Vector Database Comparison 2026" y Khorana, "pgvector vs Pinecone vs Weaviate vs Qdrant 2026": https://weekonelabs.com/blog/vector-database-comparison-2026 y https://gautamkhorana.com/blog/vector-databases-2026-pgvector-pinecone-weaviate-qdrant-chroma/
51. ZenML, "Langfuse vs Phoenix" y Langfuse, "Langfuse vs. Arize AX and Arize Phoenix": https://www.zenml.io/blog/langfuse-vs-phoenix y https://langfuse.com/faq/all/best-phoenix-arize-alternatives
52. Langfuse, "Pricing": https://langfuse.com/pricing
53. DEV, "OpenTelemetry's GenAI semantic conventions are NOT stable yet" y Arthur, "OpenInference vs OpenTelemetry GenAI for Agent Tracing": https://dev.to/azena-ai/opentelemetrys-genai-semantic-conventions-are-not-stable-yet-heres-what-actually-shipped-in-2026-3mke y https://www.arthur.ai/column/openinference-vs-opentelemetry-genai-conventions-agent-tracing
54. FutureAGI, "Best Open-Source LLM Eval Frameworks in 2026"; AgentsCamp, "Best LLM & RAG Evaluation Tools in 2026"; MachineLearningMastery, "LLM Evaluation Frameworks Compared": https://futureagi.com/blog/best-open-source-eval-frameworks-2026/ , https://agentscamp.com/guides/evaluation/best-llm-eval-tools-2026 , https://machinelearningmastery.com/llm-evaluation-frameworks-compared-how-to-actually-measure-what-your-model-does/
55. Cekura, "7 AI Voice Agent Testing Tools"; FutureAGI, "Voice AI Simulation in 2026"; Hamming, "How to Evaluate and Test Voice Agents": https://www.cekura.ai/blogs/ai-voice-agent-testing-tools , https://futureagi.com/blog/voice-ai-simulation-cekura-hamming-bluejay-coval-2025/ , https://hamming.ai/resources/guide-to-ai-voice-agents-quality-assurance
56. NAIC, mapa de adopción del Model Bulletin; actuary.info, "AI Regulation in Insurance 2026"; aipmo, "NAIC AI Bulletin Adoption: Q2 2026": https://content.naic.org/sites/default/files/legal-adoption-map-ai-model-bulletin.pdf , https://actuary.info/insights/ai-regulation-insurance-naic-2026 , https://aipmo.co/naic-ai-bulletin-q2-2026-status/
57. EU AI Act, Anexo III; aiactblog, "Life and health insurance risk assessment/pricing"; euaicompass, "EU AI Act for Insurance": https://artificialintelligenceact.eu/annex/3/ , https://www.aiactblog.nl/en/annex-iii/essentiele-diensten-voordelen/life-health-insurance-pricing , https://euaicompass.com/eu-ai-act-for-insurance.html
58. JustCall, "AI Voice Agent Disclosure Laws 2026"; Henson Legal, "AI Voice Agent Compliance"; Thoughtly, "AI Disclosure Requirements for Voice Agents": https://justcall.io/blog/ai-voice-agent-disclosure-laws.html , https://www.henson-legal.com/ai-voice-compliance , https://thoughtly.com/blog/ai-disclosure-requirements-what-to-tell-callers
59. Hamming, "PII Redaction for Voice Agent Transcripts"; LiteLLM, "PII, PHI Masking - Presidio"; AI/TLDR, "Presidio": https://hamming.ai/resources/pii-redaction-voice-agents-compliance-architecture-guide , https://docs.litellm.ai/docs/proxy/guardrails/pii_masking_v2 , https://ai-tldr.dev/tools/microsoft-presidio/
60. OpenRouter, "Free LLM API in 2026: 13 Options Ranked"; continuumcode, "Free LLM API: real limits and catches"; wetheflywheel, "Best Free LLM API Tiers in 2026": https://openrouter.ai/blog/tutorials/free-llm-apis-compared/ , https://continuumcode.ai/guides/free-llm-api/ , https://wetheflywheel.com/en/ai-model-access/free-llm-api-tiers-2026/
61. LiveKit, "Pricing"; Daily, "Pricing"; Daily, "Pipecat Cloud Pricing"; Cekura, "ElevenLabs alternatives" (créditos de Deepgram y Cartesia): https://livekit.com/pricing , https://www.daily.co/pricing/ , https://www.daily.co/pricing/pipecat-cloud/ , https://www.cekura.ai/blogs/elevenlabs-alternative
62. Cekura, "ElevenLabs Pricing in 2026": https://www.cekura.ai/blogs/elevenlabs-pricing
63. agentdeals, "Neon vs Supabase Free Tier Comparison 2026" y dreaming.press, "Best Open-Source Vector Database in 2026" (Qdrant Cloud 1 GB): https://agentdeals.dev/neon-vs-supabase y https://dreaming.press/posts/best-open-source-vector-database-2026.html
64. Hatchable, "Free web hosting in 2026"; snapdeploy, "7 Free Backend Hosting Platforms for APIs"; InfoQ, "Oracle Quietly Halves Free Tier Ampere A1 Compute Limits": https://hatchable.com/articles/state-of-free-web-hosting-in-2026 , https://snapdeploy.dev/blog/free-backend-hosting-2026-apis-servers , https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/
65. Retell, "AI Voice Agent Pricing in 2026: Full Cost Breakdown" e Inworld, "Voice Agent Cost Per Minute 2026": https://www.retellai.com/blog/ai-voice-agent-pricing-full-cost-breakdown-platform-comparison-roi-analysis y https://inworld.ai/resources/voice-agent-cost-per-minute-2026
66. Landed, "ai-engineer-portfolio-projects"; AI Codex, "The 5 portfolio projects that actually signal FDE readiness"; DEV, "5 AI Portfolio Projects That Actually Get You Hired in 2026": https://github.com/landedjobs/ai-engineer-portfolio-projects , https://www.aicodex.to/articles/fde-portfolio-projects , https://dev.to/klement_gunndu/5-ai-portfolio-projects-that-actually-get-you-hired-in-2026-5bpl
67. KORE1, "Agentic AI Engineering Hiring Survey 2026"; jobsbyculture, "Agentic AI Jobs Grew 280% in 2026"; futureproofing.dev, "AI Engineer Demand 2026": https://www.kore1.com/agentic-ai-hiring-2026/ , https://jobsbyculture.com/blog/agentic-ai-hiring-boom-2026 , https://www.futureproofing.dev/resources/ai-talent-gap/ai-engineer-demand-2026
68. langchain-ai/voice-demo; ahmad2b/langgraph-voice-call-agent; dqbd/langgraph-livekit-agents; livekit-examples: https://github.com/langchain-ai/voice-demo , https://github.com/ahmad2b/langgraph-voice-call-agent , https://github.com/dqbd/langgraph-livekit-agents , https://github.com/livekit-examples
69. EverQuote, "5 Tips for Engaging Spanish Speaking Insurance Customers" y Confie, "Building a More Accessible Insurance Landscape": https://learn.everquote.com/5-tips-spanish-insurance-customers y https://www.confie.com/insights/accessible-multilingual-insurance-landscape/
70. GFT Engineering, "Towards generating realistic synthetic insurance data" y SynthETIC (CRAN): https://medium.com/gft-engineering/towards-generating-realistic-synthetic-insurance-data-78bdd717d9a8 y https://cran.r-project.org/web/packages/SynthETIC/vignettes/SynthETIC-demo.html
71. Anyreach, "AI Voice Agents for Insurance (2026): Use Cases, Compliance & ROI": https://blog.anyreach.ai/ai-voice-agents-insurance-2026/
