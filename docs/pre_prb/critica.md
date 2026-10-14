# Crítica técnica y de viabilidad: Untangle

**Paso 2 de la pre-incepción.** Posición crítica sobre la idea descrita en [idea.md](idea.md) y en el [brief con su adenda](../00-brief-untangle.md). El propósito es atacar la idea con evidencia antes de que el PVB la fije, no elogiarla.
**Fecha:** 2026-09-15. **Método:** las fuentes de `idea.md` se citan como `[idea n]`; las fuentes nuevas de este documento van con letras `[A]` a `[K]` y se listan al final.

Escala de severidad:

- **Bloqueante**: si no se resuelve, el proyecto no cumple su objetivo (que un evaluador técnico lo tome en serio).
- **Alta**: compromete un componente obligatorio o el diferenciador.
- **Media**: compromete calidad, tiempo o credibilidad de forma recuperable.
- **Baja**: detalle que hay que cerrar, sin riesgo estructural.

---

## Resumen ejecutivo

La idea es sólida en dominio y en instintos, pero tiene cinco puntos donde puede fallar frente a un evaluador serio: (1) la palabra "multiagente" es hoy una bandera roja en la comunidad técnica si no se justifica con precisión; (2) el objetivo de latencia de voz es incompatible con hacer RAG, reglas y cumplimiento dentro del mismo turno; (3) el tier gratuito de LLM no aguanta una llamada de voz con varios agentes, así que "costo cero" y "voz en tiempo real" chocan; (4) el diferenciador (citar la cláusula) se vuelve trivial si el corpus sintético es pequeño y limpio; (5) el alcance es el de un equipo, y el riesgo número uno del portafolio es quedar en demo-ware. Ninguno es fatal; todos exigen decisiones antes del PVB.

---

## C1. "Multiagente" es una afirmación que hoy se cuestiona por defecto

**Severidad: Alta (credibilidad).**

**Lo que dice la idea.** Cuatro agentes con responsabilidades y herramientas propias, "no un LLM con prompts distintos disfrazado de equipo".

**Lo que dice la evidencia.** El estudio MAST analizó más de 1.600 trazas de 7 frameworks multiagente y clasificó 14 modos de fallo en tres categorías: problemas de diseño del sistema, desalineación entre agentes y verificación de la tarea; su conclusión es que el margen de mejora está en el diseño del sistema, no en modelos más grandes [A]. Resúmenes derivados reportan tasas de fallo entre 41% y 86,7% en los frameworks evaluados [B]. Cognition publicó "Don't Build Multi-Agents" con dos principios: "comparte contexto, y comparte las trazas completas del agente, no solo mensajes individuales" y "las acciones llevan decisiones implícitas, y las decisiones en conflicto producen malos resultados"; recomienda un agente lineal de un solo hilo para la mayoría de casos [C]. LangChain, que vende un framework multiagente, matiza: los sistemas multiagente funcionan "para consultas breadth-first que persiguen múltiples direcciones independientes en paralelo", y "los dominios que requieren que todos los agentes compartan el mismo contexto o tienen muchas dependencias entre agentes no son buen encaje hoy" [D].

**Consecuencia.** El flujo de Untangle es secuencial sobre un solo caso y todos los "agentes" necesitan el mismo contexto. Según la literatura, eso es exactamente el caso donde multiagente es fragilidad sin beneficio. Un evaluador que conozca estos textos preguntará: "¿por qué no un solo agente con cuatro herramientas?". Si la respuesta es "porque el brief pedía cuatro agentes", el proyecto pierde.

**Mitigación.** Cambiar la justificación, no necesariamente la arquitectura. La razón válida para separar Intake, Verificación, Decisión y Cumplimiento no es "colaboración emergente" sino separación de responsabilidades verificable: prompts distintos, herramientas distintas, esquemas de salida distintos, evals distintas y trazas distintas, todo sobre un grafo explícito con estado compartido (el caso) que se pasa completo, no en resúmenes. Eso cumple los dos principios de Cognition (contexto compartido íntegro, decisiones no conflictivas porque cada nodo escribe campos distintos del caso) y evita las categorías de fallo de MAST (el grafo fija roles, el estado tipado evita desalineación, la compuerta verifica). Además, la separación tiene un beneficio medible: se puede evaluar la extracción sin la verificación, y la verificación sin la decisión.

**Decisión para el PVB.** Describir a Untangle como "flujo multiagente sobre un grafo explícito con estado compartido" y escribir en el README por qué no es un solo agente: aislamiento de fallos y evals por responsabilidad. Nunca usar "los agentes colaboran" ni "equipo de agentes" sin esa explicación.

---

## C2. La latencia de voz y el trabajo dentro del turno son incompatibles

**Severidad: Alta (componente obligatorio).**

**Lo que dice la idea.** Voz en tiempo real con round-trip bajo unos 700 ms, y en el mismo flujo: verificación por RAG, reglas y una compuerta de cumplimiento.

**Lo que dice la evidencia.** Un turno de menos de 800 ms se gasta casi entero en STT (100 a 300 ms), primer token del LLM (200 a 600 ms) y primer audio del TTS (150 a 400 ms) [idea 33]. Una consulta a RAG o una llamada a herramienta dentro del turno añade cientos de milisegundos o segundos; la industria lo resuelve con "frases de relleno" que esconden la espera, con llamadas a herramientas especulativas en paralelo, y con prefetch de RAG basado en la predicción de la siguiente pregunta (VoiceAgentRAG, arquitecturas de dos agentes) [F]. Las revisiones de fallos en producción ponen la latencia como el fallo más visible y las alucinaciones como el más peligroso; un agente financiero "alucinó saldos de cuenta durante períodos de latencia del backend" [E].

**Consecuencia.** Si la Verificación y el Cumplimiento corren dentro del turno de voz, el objetivo de 700 ms es falso desde el diseño. Si el evaluador ve la traza y encuentra turnos de 2 a 3 segundos, la promesa de la landing se cae.

**Mitigación.** Separar dos ritmos: el turno conversacional (Intake responde rápido con lo que ya sabe, con el modelo más rápido disponible) y el trabajo de fondo (Verificación y Decisión corren de forma asíncrona sobre el caso mientras el llamante sigue hablando, y sus resultados entran a la conversación cuando están listos, con una frase de transición). Cumplimiento corre una sola vez, al cierre, fuera del turno. Además: prefetch de la póliza del tenant al identificar al llamante, y medición separada de "latencia de turno" y "latencia de decisión".

**Decisión para el PVB.** Dos métricas de latencia, no una: turn latency p95 (conversación) y decision latency (trabajo de fondo). El objetivo de 700 ms aplica solo a la primera.

---

## C3. "Costo cero" y "voz en tiempo real" chocan en el LLM

**Severidad: Alta (restricción del autor).**

**Lo que dice la idea.** El proyecto debe salir gratis. La sección 10 de `idea.md` muestra que casi todo tiene tier gratuito.

**Lo que dice la evidencia.** Las guías de 2026 sitúan el tier gratuito de Gemini Flash en el orden de 10 solicitudes por minuto y 250 por día, con errores 429 al superarlos y reinicio de la cuota diaria a medianoche del Pacífico; el consejo es enrutar pasos baratos a un modelo Lite, cachear y encolar [G]. Groq ofrece para llama-3.3-70b unos 30 RPM, 1.000 RPD y 12.000 tokens por minuto [idea 60]. Una llamada de 4 minutos tiene entre 25 y 35 turnos del usuario; con un agente de Intake por turno, más Verificación y Decisión en algunos turnos, más Cumplimiento al cierre, son entre 40 y 60 llamadas al LLM por conversación. Con 10 RPM la llamada se corta; con 250 RPD caben cuatro o cinco llamadas al día; con 12.000 TPM y prompts de 2.000 a 4.000 tokens caben tres a seis llamadas por minuto.

**Consecuencia.** El tier gratuito sirve para desarrollar en texto y correr evals con paciencia, pero no para iterar en voz ni para grabar una demo fluida. "Costo cero" es verdad para la mayor parte del stack y falso para el LLM en voz, salvo que el modelo corra en local.

**Mitigación.** Tres capas: (1) un modelo abierto pequeño en local (Ollama en la máquina de desarrollo) para los turnos de Intake, que son extracción corta y respuesta breve; su latencia depende del hardware y hay que medirla en el esqueleto; (2) Gemini o Groq gratuitos para Verificación y Cumplimiento, que corren fuera del turno y toleran cola y reintento con backoff; (3) un presupuesto de emergencia declarado (del orden de unos pocos dólares) solo para grabar el video si el modelo local no da la calidad, documentado como excepción a D-011. Failover entre proveedores compatibles con OpenAI por cambio de URL base [G].

**Decisión para el PVB.** Aceptar que el "costo cero" se cumple con modelo local para voz, y definir si se admite el presupuesto de emergencia para la grabación.

**Actualización 2026-09-15:** Miguel descartó el modelo local (demasiado exigente para el computador) y decidió pagar un LLM barato y rentable con tope de gasto. La crítica se mantiene para el resto del stack; para el LLM la respuesta es D-015 en el plan (Gemini 2.5 Flash-Lite en tier de pago, alrededor de 1 centavo por llamada de 4 minutos, tope de 5 USD en 90 días con alerta en 3; desarrollo y evals en texto con el tier gratuito).

---

## C4. El español es el idioma donde el stack gratuito es más débil

**Severidad: Media.**

**Lo que dice la idea.** Voz bilingüe obligatoria (D-009).

**Lo que dice la evidencia.** Los proveedores comerciales cubren español bien (Nova-3 con cambio de idioma, Cartesia con varios locales) [idea 37][idea 42], pero sus créditos gratuitos se agotan. En código abierto, Kokoro tiene tres voces en español, todas de pronunciación latinoamericana, y sus voces en inglés americano son "claramente las más pulidas" [K]; Parakeet está centrado en inglés [idea 40]; Whisper cubre español pero no es streaming nativo y su latencia depende del hardware [idea 39]. La calidad de STT es el techo de todo lo demás: "si la transcripción está mal, la intención está mal y el cliente se enfada sin importar la sofisticación del LLM" [E].

**Consecuencia.** El camino de costo cero en español pasa por Whisper y Kokoro en local; la calidad puede ser aceptable para una demo, pero nadie lo sabe hasta medirlo con acento colombiano y vocabulario de seguros ("deducible", "póliza", "siniestro", direcciones y placas).

**Mitigación.** Golden set de audio en español grabado por el autor y una o dos personas más; medir WER por proveedor y modelo local antes de decidir; usar los créditos comerciales primero en español (donde más aportan) y el stack local en inglés (donde menos se nota). Confirmar que el acento latinoamericano de Kokoro es el deseado; sí lo es para un autor colombiano.

**Decisión para el PVB.** El español es el idioma "de calidad probada con proveedores"; el inglés puede correr en local. Definirlo así evita gastar créditos donde no hace falta.

---

## C5. El diferenciador se vuelve trivial si el corpus es pequeño y limpio

**Severidad: Alta (diferenciador).**

**Lo que dice la idea.** RAG sobre pólizas con citación de la cláusula exacta.

**Lo que dice la evidencia.** Citar cláusulas que no existen o que no sostienen la respuesta es el fallo documentado en triage de siniestros con RAG [idea 44], y corrección no implica fidelidad [idea 46]. Pero el reverso también es cierto: con dos pólizas de veinte cláusulas cada una, cualquier recuperador acierta, y un evaluador lo notará. Además, el texto de la póliza ISO PP 00 01 es material con derechos de ISO y los formularios ACORD son licenciados (no vendidos) por ACORD; agentes y vendors necesitan acuerdo de licencia para usarlos [H].

**Consecuencia.** Dos riesgos opuestos: un corpus copiado (problema legal y de originalidad) o un corpus de juguete (problema de credibilidad).

**Mitigación.** Escribir pólizas originales con la estructura del formulario ISO (Acuerdo, Definiciones, Partes A a F, exclusiones numeradas, deberes tras el siniestro) sin copiar su texto, con diferencias deliberadas entre aseguradoras ficticias: exclusiones que un endoso reabre, definiciones distintas de "auto cubierto", deducibles y límites distintos, cláusulas casi idénticas que obligan a distinguir. Diseñar el golden set de citación con casos donde la cláusula correcta compite con una parecida, y con preguntas que no tienen cláusula ("no encuentro cláusula que lo cubra" debe ser una respuesta evaluada, no un fallo). Verificar cada cita por identificador exacto además del juez LLM, porque el juez tiene sesgos publicados [idea 54].

**Decisión para el PVB.** Tamaño y dureza mínimos del corpus: al menos 3 aseguradoras, 40 a 60 cláusulas por póliza, 2 endosos por aseguradora, y un golden set de citación con distractores. Declarar en el README que las pólizas son originales e "inspiradas en la estructura ISO".

---

## C6. Las reglas deterministas pueden hacer que el modelo parezca prescindible, o pueden ser triviales

**Severidad: Media.**

**Lo que dice la idea.** Reglas de elegibilidad y triage deterministas; el modelo extrae y redacta (ajuste 2, D-012).

**Lo que dice la evidencia.** Las guías reales de suscripción tienen decenas de reglas de aceptación y derivación [idea 14][idea 15]; una versión con tres reglas ("si DUI, derivar") parece un ejercicio de clase. Por otro lado, el discurso de la industria coincide en que "la IA reúne hechos y no decide cobertura" [idea 2], así que reglas fuera del modelo es la posición correcta.

**Consecuencia.** Si las reglas son triviales, el evaluador concluye que el proyecto es un extractor con un `if`. Si las reglas son complejas pero la extracción es mala, las reglas fallan por entradas incorrectas y la culpa parece del motor.

**Mitigación.** Reglas como tabla versionada por tenant (10 a 20 reglas por flujo, inspiradas en guías públicas), con tests unitarios y con "referral" como salida explícita cuando la regla no decide. Medir la calidad de extracción por campo (precisión y cobertura contra el golden set) para separar fallos de extracción de fallos de reglas. Mostrar en la vista del caso qué regla se aplicó con qué entradas.

**Decisión para el PVB.** El valor que se mide es la extracción estructurada bajo voz; las reglas son el "motor de reglas" y se presentan como tal, no como IA.

---

## C7. Cumplimiento: el riesgo es parecer que se cumple

**Severidad: Media (reputación).**

**Lo que dice la idea.** "Inspirado en" patrones reales; nunca afirmar certificación.

**Lo que dice la evidencia.** Reguladores estadounidenses exigen a las aseguradoras gobierno documentado, explicabilidad y evitar "provisión de información engañosa a los clientes" por sistemas de IA (NAIC, NY DFS Circular Letter 2024-7) [I]. La divulgación de IA y el consentimiento de grabación varían por estado [idea 58]. Los proyectos de portafolio que mencionan cumplimiento sin mecanismos concretos aparecen como "reclamos inflados" y "barreras ausentes" en las listas de banderas rojas [J].

**Consecuencia.** Nombrar NAIC o TCPA en el README sin un control implementado detrás produce el efecto contrario al buscado.

**Mitigación.** Una tabla en el README: principio → control implementado → dónde se ve en la traza o en el código. Divulgación de IA y grabación al inicio de cada llamada en el idioma del llamante; ruta a persona siempre disponible; PII redactada en trazas con Presidio; explicabilidad por caso (regla, entradas, cláusula citada). Nada más y nada menos.

**Decisión para el PVB.** Cumplimiento se formula como cuatro controles verificables, no como una sección de texto.

---

## C8. Multi-tenant puede comerse el tiempo sin aportar a la demo

**Severidad: Media.**

**Lo que dice la idea.** 2 a 3 tenants con aislamiento; posible reutilización de Keycloak.

**Lo que dice la evidencia.** RLS en Postgres es el patrón recomendado, pero con trampas conocidas: pooling de sentencias que pierde la variable de sesión, funciones no `LEAKPROOF`, versiones de pgvector [idea 49]. Keycloak es una pieza de infraestructura con su propio ciclo de configuración.

**Consecuencia.** Un fin de semana de RLS y Keycloak que no aparece en el video de 3 a 5 minutos.

**Mitigación.** RLS sí, porque es barato y demostrable ("misma llamada, dos aseguradoras, dos respuestas"). Keycloak no en la primera versión: un emisor de tokens simple con `tenant_id` como claim, y un ADR que documente cuándo entraría Keycloak. Tests de aislamiento en CI (un tenant no puede leer las cláusulas del otro).

**Decisión para el PVB.** Multi-tenant en el MoSCoW como "Must" solo en su forma mínima (RLS y RAG por tenant); Keycloak en "Could".

---

## C9. La observabilidad puede quedar en logs bonitos sin evals que los usen

**Severidad: Media.**

**Lo que dice la idea.** Trazas de cada decisión con costo y latencia, con Langfuse o Phoenix.

**Lo que dice la evidencia.** Las convenciones GenAI de OpenTelemetry siguen en desarrollo y cambian [idea 53]; el plan gratuito de Langfuse Cloud tiene 50.000 unidades al mes [idea 52], y una llamada de voz con decenas de turnos y varios agentes genera cientos de spans; los equipos que despliegan sin monitoreo descubren fallos "por quejas de clientes" [E].

**Consecuencia.** Dos fallos posibles: agotar la cuota gratuita en una semana de iteración, o tener trazas que nadie consume salvo para la captura de pantalla del README.

**Mitigación.** Self-host de Langfuse en Docker desde el esqueleto (MIT, sin cuota); instrumentación propia con OpenTelemetry para que el destino sea reemplazable; y, sobre todo, que las evals lean las trazas: la latencia de turno y de decisión, el costo por caso y la tasa de derivación se calculan desde los spans, no desde logs aparte.

**Decisión para el PVB.** Las métricas de la sección de evals se derivan de las trazas; observabilidad y evals son un solo sistema.

---

## C10. Sin audio, las evals de voz no miden lo que la landing promete

**Severidad: Alta (promesa pública).**

**Lo que dice la idea y la landing.** "Interrupciones manejadas sin perder estado", "latencia por turno de punta a punta".

**Lo que dice la evidencia.** El stack abierto de evaluación no tiene audio: "una transcripción perfectamente limpia puede representar una llamada con una pausa p95 de 4 segundos, el agente hablando cuando el usuario interrumpe, o ruido degradando el ASR" [idea 55]. Las plataformas que sí simulan audio con barge-in y ruido son de pago [idea 55]. La guía de FNOL de Roark exige probar ejes de emoción, entorno y bordes de cumplimiento con audio [idea 4].

**Consecuencia.** Si las evals son solo de texto, las dos métricas de voz de la landing quedan sin medir, y un evaluador de voz lo detecta en un minuto.

**Mitigación.** Un golden set de audio pequeño y propio por idioma (10 a 20 grabaciones con interrupciones deliberadas, ruido de fondo y silencios), reproducido contra el agente en un entorno controlado, con las métricas tomadas de los eventos del framework de voz (fin de turno, primer token, primer audio, parada por interrupción) y de las trazas. Sin plataforma de pago. Reportar honestamente lo que no se mide (por ejemplo, acentos que no están en el set).

**Decisión para el PVB.** El golden set de audio es un entregable con dueño y fecha, no una intención.

---

## C11. El alcance es de equipo; el riesgo número uno es el demo-ware

**Severidad: Bloqueante si no se gestiona.**

**Lo que dice la idea.** Voz bilingüe, cuatro agentes, RAG con citas, reglas, cumplimiento, multi-tenant, observabilidad, evals, bandeja humana, continuidad voz a chat, video y README.

**Lo que dice la evidencia.** Las banderas rojas más citadas por quienes evalúan portafolios: "portafolios llenos de prototipos, demos o POCs sin URL en vivo", proyectos que "funcionan porque ignoran todo lo que se rompe: límites de tasa, condiciones de carrera, alucinaciones con entradas inusuales, sobrecostos", mejoras "sin línea base", READMEs vacíos y "barreras ausentes" [J]. Gartner atribuye el 57% de las iniciativas de IA fallidas a expectativas irreales [E].

**Consecuencia.** Un proyecto a medio construir con seis tecnologías nuevas es exactamente el perfil que las guías describen como descartable.

**Mitigación.** Definir "hecho" por capas y cerrarlas en orden, cada una demostrable sola: (1) FNOL en texto con caso, RAG con citas, reglas, compuerta, trazas y golden set en CI; (2) bandeja del ajustador; (3) voz en un idioma; (4) segundo idioma; (5) cotización; (6) continuidad voz a chat. El video se puede grabar desde la capa 3. Lista de corte escrita: qué se sacrifica primero si el tiempo no alcanza (6, luego 5, luego 4).

**Decisión para el PVB.** El roadmap de 90 días se escribe por capas demostrables, con la capa 3 como hito del video.

---

## C12. La landing ya promete cosas que el aplicativo puede no cumplir

**Severidad: Media.**

**Lo que dice la idea.** La landing fue una base (D-013) y se realineará.

**Lo que dice la evidencia.** La landing publicada describe seis agentes por dominio, una sección de evals con cuatro métricas y manejo de interrupciones; los evaluadores leen la landing antes que el código.

**Consecuencia.** Mientras la landing y el aplicativo difieran, cada visita de un reclutador es una oportunidad de perder credibilidad.

**Mitigación.** Realinear la landing en dos momentos: una pasada mínima después de Incepción (nombres de agentes, promesas de evals ajustadas a lo planificado) y la pasada final con el video. Mientras tanto, la landing ya tiene la frase honesta "proyecto de demostración construido para un portafolio"; conviene mantenerla.

**Decisión para el PVB.** Añadir "realinear la landing" como hito explícito del roadmap.

---

## C13. Un enlace en vivo de voz es caro; un video no basta para algunos evaluadores

**Severidad: Media.**

**Lo que dice la idea.** Video o demo en vivo de 3 a 5 minutos.

**Lo que dice la evidencia.** Las guías piden "URL en vivo" [idea 66][J]. Los hostings gratuitos duermen la instancia a los 15 minutos (Render) o son de prueba (Fly, Railway) [idea 64], y un agente de voz dormido significa una primera llamada de un minuto de espera.

**Consecuencia.** El enlace en vivo de voz gratuito es poco fiable; sin enlace, algunos evaluadores no pasan del README.

**Mitigación.** Enlace en vivo del modo texto (chat sobre el mismo grafo, barato de hospedar y sin latencia crítica) más video de la voz, más instrucciones de ejecución local en un comando. La landing enlaza los tres.

**Decisión para el PVB.** El "entregable" son tres cosas: video, enlace en vivo del modo texto, y repo ejecutable en local.

---

## C14. Propiedad intelectual de formularios y pólizas

**Severidad: Baja, pero obligatoria.**

**Lo que dice la evidencia.** Los formularios ACORD requieren licencia escrita con ACORD; el material ISO es propietario y su uso está limitado a aseguradoras participantes y licenciatarios [H].

**Mitigación.** Usar solo la estructura de campos de ACORD 2 y ACORD 90 con nombres propios de Untangle; escribir pólizas originales; no incluir specímenes ni formularios en el repositorio; declararlo en el README.

**Decisión para el PVB.** Principio no negociable: ningún texto de terceros con derechos en el corpus ni en el repo.

---

## C15. Riesgo de integración y de versiones

**Severidad: Media.**

**Lo que dice la evidencia.** El adaptador oficial de LangGraph para LiveKit tiene incidencias abiertas de streaming de subgrafos y de compatibilidad [idea 23]; el ecosistema cambia de versión mayor con frecuencia.

**Mitigación.** Probar la integración voz y grafo en la primera semana del esqueleto, con versiones fijadas (lockfile) y un adaptador propio de reserva si el oficial falla; el grafo nunca depende del framework de voz (el mismo grafo sirve al modo texto).

**Decisión para el PVB.** "El grafo corre sin voz" es un principio de diseño, no una consecuencia.

---

## C16. Datos sintéticos demasiado cómodos

**Severidad: Media.**

**Lo que dice la evidencia.** La guía de pruebas de FNOL exige variar tipo de siniestro, estado emocional del llamante, línea de negocio, entorno acústico y bordes de cumplimiento (el llamante admite culpa, pregunta por cobertura, rechaza la grabación) [idea 4].

**Consecuencia.** Si los casos sintéticos son todos "choque leve, nadie herido, datos completos", el 100% en el golden set no dice nada.

**Mitigación.** Generar el golden set con una matriz de ejes (peril, emoción, completitud de datos, idioma, borde de cumplimiento) y con casos que deben terminar en derivación o en "no puedo confirmar cobertura". Publicar la distribución del set en el README.

**Decisión para el PVB.** El golden set tiene una matriz de cobertura declarada; los casos fáciles no pueden ser mayoría.

---

## Tabla resumen

| # | Crítica | Severidad | Mitigación principal | Qué fija el PVB |
|---|---|---|---|---|
| C1 | "Multiagente" cuestionado por defecto | Alta | Justificar por separación verificable sobre grafo con estado compartido | Vocabulario y argumento del README |
| C2 | Latencia frente a trabajo en el turno | Alta | Dos ritmos: turno conversacional y trabajo de fondo | Dos métricas de latencia |
| C3 | Costo cero frente a LLM en voz | Alta | Modelo local para Intake; gratuito con cola para fondo; presupuesto de emergencia | Excepción a D-011 sí o no |
| C4 | Español débil en stack gratuito | Media | Créditos comerciales en español; medir WER con acento propio | Idioma "de proveedor" e idioma "local" |
| C5 | Corpus trivial o copiado | Alta | Pólizas originales con estructura ISO y distractores; check exacto de citas | Tamaño y dureza mínimos del corpus |
| C6 | Reglas triviales o culpables | Media | 10 a 20 reglas por flujo, referral explícito, calidad de extracción medida | Qué se mide: extracción |
| C7 | Parecer que se cumple | Media | Tabla principio → control → evidencia | Cuatro controles verificables |
| C8 | Multi-tenant come tiempo | Media | RLS mínimo; Keycloak a "Could" | MoSCoW de multi-tenant |
| C9 | Trazas sin uso | Media | Langfuse self-host; evals derivadas de trazas | Observabilidad y evals como un sistema |
| C10 | Evals de voz sin audio | Alta | Golden set de audio propio por idioma, métricas del framework | Entregable con dueño y fecha |
| C11 | Demo-ware | Bloqueante | Capas demostrables y lista de corte | Roadmap por capas; video en capa 3 |
| C12 | Landing desalineada | Media | Dos pasadas de realineación | Hito explícito |
| C13 | Enlace en vivo de voz | Media | Enlace en vivo del modo texto más video más local | Tres entregables |
| C14 | Propiedad intelectual | Baja | Estructura, no texto; declaración | Principio no negociable |
| C15 | Integración y versiones | Media | Probar en semana 1; grafo independiente de la voz | Principio "el grafo corre sin voz" |
| C16 | Datos cómodos | Media | Matriz de ejes en el golden set | Distribución declarada |

---

## Lo que debería cambiar en la idea antes del PVB

1. Reescribir la afirmación central: de "sistema multiagente" a "flujo multiagente sobre un grafo explícito, con un caso como estado compartido y responsabilidades evaluables por separado".
2. Dividir la latencia en dos métricas y sacar Verificación, Decisión y Cumplimiento del turno de voz.
3. Aceptar que "costo cero" exige un modelo local para la conversación, y decidir si existe un presupuesto de emergencia para grabar el video.
4. Asignar los créditos comerciales de voz al español y el stack local al inglés, y medir antes de decidir.
5. Fijar el tamaño y la dureza del corpus sintético y del golden set de citación, con distractores y casos sin respuesta.
6. Convertir cumplimiento en cuatro controles con evidencia en traza.
7. Reducir multi-tenant a RLS y RAG por tenant; Keycloak fuera de la primera versión.
8. Unificar observabilidad y evals: las métricas salen de las trazas.
9. Comprometer un golden set de audio propio por idioma.
10. Planificar por capas demostrables con lista de corte; el video se graba en la capa 3 (voz en un idioma).
11. Añadir "realinear la landing" y "enlace en vivo del modo texto" como entregables.
12. Prohibir texto de terceros con derechos en corpus y repo.

---

## Fuentes nuevas de este documento

- [A] Cemri, Pan, Yang et al., "Why Do Multi-Agent LLM Systems Fail?" (arXiv 2503.13657, NeurIPS 2025): https://arxiv.org/abs/2503.13657
- [B] Augment Code, "Multi-Agent AI Systems: Why They Fail and How to Fix Coordination Issues (2026)": https://www.augmentcode.com/guides/why-multi-agent-llm-systems-fail-and-how-to-fix-them
- [C] Cognition, "Don't Build Multi-Agents": https://cognition.com/blog/dont-build-multi-agents
- [D] LangChain, "How and when to build multi-agent systems": https://www.langchain.com/blog/how-and-when-to-build-multi-agent-systems
- [E] Bluejay, "7 Reasons Voice Agents Fail in Production"; Tuner, "The 7 Most Common Voice AI Failures in Production"; Bantech, "Why AI Voice Agents Fail in Production": https://getbluejay.ai/resources/voice-agent-production-failures , https://usetuner.ai/blog/the-7-most-common-voice-ai-failures-in-production , https://www.bantechsolutions.com/why-ai-voice-agents-fail-in-production/
- [F] Stream, "How Do You Prevent Voice Gaps with Speculative Tool Calling?"; "VoiceAgentRAG" (arXiv 2603.02206); "Speculative Interaction Agents" (arXiv 2605.13360): https://getstream.io/blog/speculative-tool-calling-voice/ , https://arxiv.org/html/2603.02206v1 , https://arxiv.org/pdf/2605.13360
- [G] YingTu, "Google Gemini API Free Tier 2026: Complete Limits Guide + 429 Error Solutions"; tinkerllm, "Gemini API Rate Limits: Free Tier Quotas 2026"; pecollective, "Gemini API Free Tier 2026": https://yingtu.ai/en/blog/google-gemini-api-free-tier , https://tinkerllm.com/blog/gemini-api-free-tier-limits-rate-quotas/ , https://pecollective.com/tools/gemini-free-tier-guide/
- [H] ACORD, "Forms Subscriptions & Licensing"; Vertafore, "Third-Party Terms" (material ISO y ACORD); Big "I", "Members Receive ACORD Forms Licenses": https://www.acord.org/forms-pages/forms-participation-programs , https://online.vertafore.com/ThirdPartyTerms , https://www.independentagent.com/big-i-members-receive-acord-forms-licenses/
- [I] Hinshaw & Culbertson, "AI Governance Expectations on the Rise for Insurers"; PCMI, "The regulatory clock on AI claims is already running"; Fenwick, "Tracking the Evolution of AI Insurance Regulation": https://www.hinshawlaw.com/en/insights/privacy-cyber-and-ai-decoded-alert/ai-governance-expectations-on-the-rise-for-insurers-amid-new-regulatory-activity , https://www.pcmicorp.com/2026/04/the-regulatory-clock-on-ai-claims-is-already-running/ , https://www.fenwick.com/insights/publications/tracking-the-evolution-of-ai-insurance-regulation
- [J] Learnist, "12 Red Flags in AI Case Studies" y "10 Mistakes to Avoid When Using Open-Source LLMs in Portfolio Demos"; Abbacus, "How to Hire an AI Developer in 2026: Portfolio Red Flags"; Utkrusht, "Evaluating developer portfolio: 7 red flags": https://www.learnist.org/ai-case-study-red-flags-portfolio-2026/ , https://www.learnist.org/llm-portfolio-demo-mistakes-2026/ , https://www.abbacustechnologies.com/how-to-hire-an-ai-developer-in-2026-portfolio-red-flags-and-technical-must-haves/ , https://utkrusht.ai/blog/evaluting-developer-portfolio
- [K] fal, "Kokoro TTS (Spanish)"; hexgrad/kokoro, issue #246 "Spanish voices"; VisionStory, "Kokoro TTS Review": https://fal.ai/models/fal-ai/kokoro/spanish , https://github.com/hexgrad/kokoro/issues/246 , https://www.visionstory.ai/open-source/kokoro-tts
