# Análisis de contexto y justificación del proyecto Untangle

> **Nota de contexto:** Este documento NO es un análisis de mercado para vender un producto. Es la justificación de por qué construir Untangle como proyecto de portafolio de nivel producción, funcional en su totalidad, con datos sintéticos, a costo cero, y por qué el dominio elegido (seguros de auto: FNOL y cotización con voz bilingüe en tiempo real) es el que mejor demuestra ingeniería de IA agéntica ante empleadores internacionales. Las cifras vienen de `idea.md` (se cita `[idea n]`) y de `critica.md` (`[critica X]`).

---

La convergencia de tres fuerzas crea el momento para Untangle: la demanda de ingenieros que sepan llevar agentes a producción supera con mucho la oferta (unas 90.000 ofertas de agentic AI en Estados Unidos en 2026, crecimiento de 280% interanual, y un salto de 151 a más de 16.500 ofertas que mencionan "agentic systems" entre 2024 y 2025 según el AI Index de Stanford [idea 67]); las herramientas para construir voz, agentes, RAG y observabilidad maduraron y tienen tiers gratuitos o son abiertas [idea 60][idea 61]; y los empleadores aprendieron a distinguir demos de producción y hoy piden evals, manejo de fallos y trazabilidad como prueba [idea 66]. La viabilidad está condicionada por tres tensiones reales: la latencia de voz frente al trabajo de verificación, los límites de los tiers gratuitos de LLM para voz, y el alcance de un proyecto que en una empresa haría un equipo [critica C2, C3, C11]. A continuación, se presenta el análisis que sustenta la decisión de construirlo.

**1. El problema que Untangle demuestra saber resolver**

El primer aviso de siniestro es la interacción más frecuente y más emocional entre un asegurado y su aseguradora, y sigue mal resuelta: las aseguradoras entregan actualizaciones digitales adecuadas solo el 22% de las veces, y el 52% de los clientes con una experiencia digital pobre se plantea irse [idea 5]. Seguros es ya el tercer vertical de IA de voz, con FNOL como el primer flujo en producción [idea 1]. El sector formula una frontera clara: "la IA reúne hechos y no decide cobertura" [idea 2]. El problema técnico detrás es genuinamente multicomponente: capturar hechos por voz con interrupciones, verificar cobertura citando la cláusula correcta, aplicar reglas, cumplir divulgaciones, escalar a una persona con el contexto completo, y demostrar todo con trazas. No hay forma de resolverlo bien con un chatbot alrededor de una API, y eso es lo que un evaluador quiere ver.

**2. Los dolores del cliente real (quien contrata)**

Los equipos que contratan describen los mismos dolores: portafolios de tutoriales sin enlace en vivo, reclamos sin línea base, proyectos que "funcionan porque ignoran todo lo que se rompe" (límites de tasa, alucinaciones, costos), READMEs vacíos y ausencia de barreras [critica J]. Lo que piden es pensamiento de producción: manejo de errores, observabilidad, control de acceso, degradación elegante, y "si el proyecto maneja modos de fallo o solo funciona cuando todo sale bien" [idea 66]. Untangle se diseña para responder exactamente a esa lista.

**3. Panorama de proyectos de referencia y por qué construir uno propio**

Existen ejemplos abiertos que resuelven partes: el demo oficial de LangChain con tres backends de voz, adaptadores de LangGraph a LiveKit, y un ejemplo de tres capas con Twilio, Pipecat y LangGraph para barreras de política [idea 68][idea 21]. Ninguno de los encontrados combina, a la vez, un corpus de dominio con citación verificable, reglas deterministas separadas del modelo, una compuerta de cumplimiento con bandeja humana, aislamiento multi-tenant, golden sets con reporte honesto y bilingüismo [idea, sección 11.2]. Las plataformas comerciales de voz para seguros (Parloa, PolyAI, Replicant, Sierra, Lorikeet) existen, pero son cajas cerradas: sirven para calibrar los criterios (profundidad del flujo FNOL, continuidad de canal, frontera de adjudicación, evidencia en regulados) [idea 2][idea 3], no para aprender a construirlas.

**Por qué construirlo (y no clonar un tutorial):**

* **Demuestra la combinación, no las partes:** cualquier parte por separado es un tutorial; la integración con evals es lo que casi nadie muestra [idea 66].
* **Dominio con estándares públicos:** ACORD 2 y ACORD 90 dan la estructura de datos; la póliza ISO da la estructura de cláusulas; las guías de suscripción públicas dan reglas realistas [idea 7][idea 9][idea 11][idea 14]. El proyecto puede ser realista sin datos reales.
* **Bilingüe con sentido:** un canal en español es un caso real del mercado estadounidense [idea 69] y diferencia el portafolio.
* **Costo cero alcanzable:** frameworks abiertos (LangGraph, LiveKit Agents o Pipecat, Langfuse, promptfoo, Presidio, pgvector), modelos abiertos en local para STT y TTS, y tiers gratuitos para lo demás [idea, sección 10]. La excepción documentada es el LLM en voz, que exige modelo local o un presupuesto de emergencia mínimo para la grabación [critica C3].
* **Propiedad intelectual limpia:** estructura de formularios y pólizas, nunca su texto [critica C14].

**4. Factores clave de éxito**

Para que Untangle cumpla su objetivo (que un evaluador técnico lo tome en serio y pida la demo), debe cumplir con:

* **Un camino feliz pulido de punta a punta antes que amplitud:** FNOL de auto por voz, desde la llamada hasta la bandeja del ajustador, con trazas y evals. La cotización es el segundo flujo, delgado. Esto responde al riesgo bloqueante de quedar en demo-ware [critica C11].
* **Evals como componente, no como sección:** golden set en texto en CI, golden set de audio propio por idioma, precisión de citación con verificación exacta, distribución del set declarada y lista de fallos publicada [critica C5, C10, C16].
* **Separación verificable entre modelo, reglas y personas:** el orquestador es código; el modelo extrae y redacta; las reglas deciden elegibilidad y triage; la compuerta deriva a una persona; todo explicable por caso [critica C1, C6].
* **Latencia honesta:** dos métricas (turno conversacional y decisión de fondo), medidas y publicadas; el trabajo pesado sale del turno [critica C2].
* **Cumplimiento como controles, no como texto:** divulgación de IA y grabación por idioma, ruta a persona, PII redactada, explicabilidad; y una tabla que los mapea a los principios que los inspiran (NAIC, TCPA, EU AI Act) sin afirmar cumplimiento [critica C7].
* **Tres entregables visibles:** video de la voz, enlace en vivo del modo texto y repo ejecutable en local; landing realineada al producto real [critica C12, C13].
* **Costo cero con plan B declarado:** stack local por defecto, créditos gratuitos donde más aportan (español), y un presupuesto de emergencia explícito solo para grabar si el modelo local no da la calidad [critica C3, C4].

**Conclusión**

Construir Untangle es la opción correcta porque el problema es real y está bien documentado, el dominio ofrece estándares públicos que lo hacen creíble sin datos reales, las herramientas necesarias son abiertas o gratuitas, y los evaluadores hoy premian exactamente lo que el proyecto se propone mostrar: producción, evals y honestidad sobre los fallos. La urgencia también es real: la ventana de demanda de ingenieros de agentes está abierta ahora, y un portafolio que enseñe la combinación completa, con un video de tres a cinco minutos y un enlace que funcione, es la forma más directa de que una empresa quiera la conversación de veinte minutos.

---
