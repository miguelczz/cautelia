# Respuestas a la Crítica del PVB — Untangle

**Paso 4 de la pre-incepción.** Crítica del [PVB v1.0](pvb.md) usando como referencia [ai-product-base.md](../ai-product-base.md) (paradigma, "only", moats, economía, 4D method, checklist de 5 preguntas incómodas). Se analiza punto por punto.

**Estado:** los 9 puntos fueron aceptados por Miguel el 2026-09-15 y están incorporados en el [PVB v1.1](pvb.md). Este archivo queda como registro de la crítica y de las decisiones.

Nota de adaptación: el marco está escrito para startups (mercado, pricing, moat). Untangle es un portafolio; donde el marco habla de "mercado" se lee "quien contrata", donde habla de "moat" se lee "lo que otro candidato no puede copiar en seis semanas", y donde habla de "pricing" se lee "costo cero y su excepción".

---

## PUNTO 1 — Visión

**Crítica:** El marco advierte que "el error más grande es tomar un workflow existente y ponerle AI encima; eso no es innovación, es feature augmentation". La visión del PVB describe un flujo FNOL con IA encima. Además mezcla dos cosas en una frase: lo que el producto hace (capturar, verificar, derivar) y lo que el proyecto busca (demostrar cómo se construyen agentes de producción). Un lector no sabe cuál de las dos es la visión.

**Pregunta incómoda (1 del marco):** ¿Qué pasa con la idea si en 12 meses los modelos voz a voz (OpenAI Realtime, Gemini Live) hacen el pipeline de voz trivial y un LLM extrae un FNOL completo con un solo prompt?

**Respuesta propuesta:** La parte que se commoditiza es la voz y la extracción; la parte durable es el sistema de evidencia y gobierno: cláusula citada y verificada, reglas separadas del modelo, compuerta con persona, aislamiento por tenant, evals con fallos. Son problemas de workflow, integración y cumplimiento, que el marco clasifica como durables. La visión debe decirlo explícitamente y separar las dos frases:

> **Visión del proyecto:** demostrar, con un sistema que funciona de punta a punta y se puede auditar, cómo se llevan agentes a producción.
> **Visión del producto:** que cada respuesta de cobertura tenga una cláusula verificada detrás, cada decisión una regla explicable, y cada caso que toque dinero una persona; la voz bilingüe es la puerta de entrada, no el valor.

Durability score propuesto (3-Lens Discovery Test): Durabilidad 4/5 (workflow y cumplimiento persisten; la voz no), Data 2/5 (datos sintéticos, sin flywheel; es un portafolio), Trust 5/5 (todo el diseño es para confianza verificable). Promedio 3,7: pasa el umbral de 3,5 del marco, con la voz como parte perecedera.

**Decisión de Miguel (2026-09-15):** acepto.

---

## PUNTO 2 — Usuarios y el veto de confianza

**Crítica:** El marco exige identificar al veto holder: "quién puede matar la adopción aunque el end-user ame el producto". El PVB pone como gate "alguien de seguros", pero el veto real en una contratación lo tiene el ingeniero senior de la revisión técnica: si encuentra un fallo no declarado o una afirmación inflada, el proceso termina aunque al reclutador le haya gustado el video. El PVB no tiene estrategia para convertir a ese veto holder en aliado.

**Pregunta incómoda:** ¿Qué le damos al revisor senior para que certifique el proyecto en diez minutos en vez de buscar dónde falla?

**Respuesta propuesta:** Tratarlo como aliado: darle antes de que pregunte lo que va a buscar. Una sección del README "Cómo falla" con la lista de casos fallidos del golden set y su causa; una sección "Lo que no hace" (sin integración real, sin cumplimiento certificado, sin pricing); ADRs con opciones descartadas y por qué; y un comando para reproducir las evals en su máquina. El veto holder pasa de buscar fallos a verificar que los declarados son los que hay. En el producto ficticio, el veto holder es el área legal o de cumplimiento de la aseguradora, y su aliado es la tabla principio → control → evidencia.

**Decisión de Miguel (2026-09-15):** acepto.

---

## PUNTO 3 — Necesidades: cuáles sobreviven y qué suposiciones cargan

**Crítica:** El marco separa problemas de output (se commoditizan) de problemas de workflow (persisten). En la sección 3 del PVB conviven los dos sin jerarquía: "FNOL incompleto" y "servicio en español de segunda" son dolores que la próxima generación de modelos de voz atenúa; "respuestas de cobertura sin respaldo", "decisiones sin explicación" y "aislamiento entre tenants" son dolores de workflow. Además, el PVB descansa en suposiciones que nadie ha validado y el marco pide un Discovery Debt Log para eso.

**Pregunta incómoda:** ¿Cuáles de nuestras suposiciones tienen evidencia débil y qué pasa si están mal?

**Respuesta propuesta:** Reordenar la sección 3 con los dolores de workflow primero y añadir al PVB un Discovery Debt Log:

| Suposición | Evidencia | Método de validación | Riesgo si está mal | Recheck |
| --- | --- | --- | --- | --- |
| Los evaluadores premian evals y fallos publicados | Media (guías de portafolio 2026, no un estudio) | Mostrar capas 1 y 2 a 2 o 3 ingenieros senior en el día 30 y preguntar qué buscarían | Alto: el esfuerzo en evals no convence | Día 30 |
| Un modelo abierto local da latencia de turno aceptable | Débil (depende del hardware del autor) | Medir p95 en el esqueleto, semana 1 | Alto: obliga a presupuesto | Semana 1 |
| El español diferencia el portafolio | Débil (inferido del mercado hispano) | Preguntar a los mismos revisores del día 30 | Medio: cuesta tiempo sin ganar puntos | Día 30 |
| El corpus sintético con estructura ISO parece real | Media (structura pública) | Que una persona del sector lea una póliza sintética | Medio: se ve ingenuo | Día 45 |
| Las citas verificadas son el diferenciador percibido | Media (fallo documentado en el sector) | Reacción de los revisores a la vista de caso | Alto: el centro del proyecto no se valora | Día 30 |

**Decisión de Miguel (2026-09-15):** acepto.

---

## PUNTO 4 — Producto: paradigma, capas de diseño, trampa del demo y una contradicción

**Crítica:** Tres cosas. (a) El marco pide elegir un paradigma UX; el PVB no lo nombra: Untangle es **Agent** (ejecuta dentro de límites), no Autonomous; decirlo evita que un revisor lo lea como "automatización de siniestros". (b) El marco pide tres capas de diseño: interacción, restricción y expectativa. El PVB cubre interacción (voz, bandeja) y restricción (reglas, compuerta), pero la capa de expectativa está descuidada: hoy la landing pública fija expectativas que el producto aún no cumple (seis agentes, evals), y no está definido qué se le dice al llamante al inicio ni qué promete el README. (c) La trampa del "cool demo" es el último 20%: interrupciones, español, casos raros. El roadmap lo mitiga con capas y lista de corte, pero la lista de corte contradice la decisión D-009: dice que el español (capa 4) se corta antes que la cotización, mientras la adenda dice que ambos idiomas son obligatorios.

**Pregunta incómoda:** Si el tiempo no alcanza, ¿se corta el español o se corta otra cosa? Y ¿qué expectativa fija cada superficie (landing, README, primera frase de la llamada)?

**Respuesta propuesta:** (a) Declarar paradigma Agent con límites explícitos. (b) Añadir "diseño de expectativas" como principio: la landing promete solo lo construido; el README abre con "lo que hace, lo que no hace, cómo falla"; la primera frase de cada llamada divulga IA y grabación y dice qué puede y qué no puede hacer el agente. (c) Corregir la lista de corte: nunca se corta el español; se recorta su alcance (menos casos en el golden set de audio, una sola voz) antes de cortar la cotización y la continuidad voz a chat. Orden de corte: continuidad (6), cotización (5), y solo después reducir, no eliminar, el español (4). Añadir además un mapa FTCEM (modo de fallo, disparador, consecuencia, alerta temprana, mitigación) como artefacto del PRD para al menos ocho fallos: cita inexistente, alucinación bajo latencia, extracción errónea de un campo central, interrupción no manejada, STT en español degradado, límite de tasa del LLM, fuga entre tenants, y llamada cortada a mitad.

**Decisión de Miguel (2026-09-15):** acepto. El español es intocable: se reduce su alcance, nunca se corta.

---

## PUNTO 5 — Valor: costo cero, triángulo de decisión y una métrica difícil de medir

> **Actualización 2026-09-15:** Miguel decidió pagar un LLM barato y rentable (D-015). El "presupuesto de emergencia de 10 USD" de la versión anterior desaparece; lo sustituye un tope de gasto del proyecto (decisión de Miguel: 5 USD en 90 días, alerta en 3; el LLM es Gemini 2.5 Flash-Lite). El resto del punto sigue vigente.

**Crítica:** El marco insiste en que "el costo marginal no es cero" y en medir "costo por outcome exitoso". El PVB dice costo cero y con eso esconde dos cosas: el costo real del proyecto es el tiempo del autor, y el tier gratuito de Gemini usa los datos para mejorar productos de Google (aceptable con datos sintéticos, pero hay que declararlo). También falta el AI Decision Triangle: el PVB no dice para qué optimiza cada componente. Y la North Star ("solicitudes de demo por cada 100 visitas") no se puede medir sin analítica en la landing, que hoy no existe.

**Pregunta incómoda:** ¿Cómo demostramos alfabetización económica en un proyecto que no cobra, y cómo medimos el North Star?

**Respuesta propuesta:** (a) Añadir el KPI "costo por caso exitoso" medido en tokens y en dólares equivalentes a precio de lista aunque se pague cero; eso demuestra que el autor sabe lo que costaría en producción y detecta cost drift. (b) Declarar el triángulo: turno conversacional optimiza Speed (modelo pequeño, prompts cortos); Verificación y Cumplimiento optimizan Capability (modelo más fuerte, fuera del turno); el proyecto entero optimiza Cost (cero). Trade-off aceptado y medido: el modelo pequeño puede extraer peor; la eval de extracción por campo lo cuantifica. (c) Cambiar la North Star a algo medible desde el día 1: "solicitudes de demo recibidas por LinkedIn por mes", con la analítica de la landing como mejora posterior si existe un tier gratuito. (d) Declarar en el README el uso de datos por el tier gratuito y que solo circulan datos sintéticos.

**Decisión de Miguel (2026-09-15):** acepto.

---

## PUNTO 6 — Diferenciación: cuál es el moat de un portafolio

**Crítica:** El marco dice que solo se elige un moat primario y que "si tu única defensa es ejecutar mejor, no tienes moat". El PVB apoya la diferenciación en "la combinación completa", que es exactamente "ejecutar mejor". La pregunta incómoda 4 del marco es directa: otro candidato con las mismas APIs puede replicar la arquitectura de Untangle en seis semanas. También hay riesgo de océano rojo: existen cientos de portafolios de "agente de voz"; si Untangle se presenta como agente de voz, compite en el peor lugar.

**Pregunta incómoda (4 del marco):** ¿Qué tiene Untangle que otro candidato no pueda copiar en seis semanas?

**Respuesta propuesta:** Elegir **Trust moat** como primario, en el sentido del caso Perplexity del marco (confianza vía citas verificables): lo que no se copia en seis semanas es el rastro de evidencia: golden sets en texto y audio en dos idiomas con distribución declarada, la lista de fallos con causa raíz, las trazas con costo y latencia por caso, los ADRs con opciones descartadas, y las lecciones aprendidas de construirlo con AIDLC. La arquitectura es copiable; la evidencia y la honestidad acumuladas no. Consecuencia de posicionamiento: Untangle no se presenta como "agente de voz para seguros" sino como "sistema de agentes de producción con evidencia verificable, demostrado en seguros con voz". La voz es el gancho del video; la evidencia es el argumento.

**Decisión de Miguel (2026-09-15):** acepto.

---

## PUNTO 7 — Contexto estratégico: arena, trampa de plataforma y las preguntas 2, 3 y 5

**Crítica:** El marco pide nombrar la arena (Pioneer, Disruptor, Enhancer) y advierte de la trampa de plataforma (construir sobre APIs que pueden cambiar precio o límites de la noche a la mañana). El PVB depende de tiers gratuitos que ya cambiaron sin aviso este año (Oracle) y de APIs de voz de terceros. Las preguntas 2 (¿quién es dueño de la data?), 3 (¿los reguladores se avergonzarían si falla en público?) y 5 (¿cómo se rompe la confianza a escala?) no están respondidas en el PVB.

**Preguntas incómodas (2, 3 y 5 del marco):** ¿Quién es dueño de la data? ¿Qué pasa si el sistema falla en público? ¿Cuál es la primera forma en que se rompe la confianza a 100x?

**Respuesta propuesta:** Arena: **Enhancer** en lo técnico (mejora un workflow existente con patrones conocidos, hechos bien) y sin gigante enfrente porque no vende nada; el "gigante" son las plataformas comerciales de voz para seguros, que se complementan citándolas como referencia de criterios, no como competencia. Trampa de plataforma: cada proveedor externo tiene un sustituto local declarado (Whisper, Kokoro, modelo local, Postgres en Docker), y el grafo no depende del framework de voz; ese es el plan B escrito. Pregunta 2: la data es sintética y propia; ningún tercero puede revocarla; las pólizas son originales. Pregunta 3: un fallo público sería una cita falsa o una promesa de cobertura; por eso la verificación exacta de citas y la regla "nunca decide cobertura"; el mapa FTCEM del punto 4 documenta el resto. Pregunta 5: a escala, la confianza se rompe primero por alucinación bajo latencia del backend (el agente inventa mientras espera) y por límites de tasa que degradan silenciosamente; mitigación: el turno nunca espera al backend (dos ritmos), respuestas de espera explícitas, y alertas de tasa de error y de latencia de decisión en las trazas. Añadir estas tres respuestas al PVB en "Riesgos críticos".

**Decisión de Miguel (2026-09-15):** acepto.

---

## PUNTO 8 — Roadmap: sin validación temprana y sin "día 2"

**Crítica:** El 4D Method del marco es Discovery → Design → Develop → Deploy con validación con usuarios reales en la semana 4, y un "Day 2 checklist" para el despliegue (monitoreo vivo, enrutamiento de feedback al dataset de evaluación, alertas de costo, rollback ensayado). El roadmap del PVB no valida con evaluadores reales hasta el día 90 y no tiene día 2 para el enlace en vivo del modo texto.

**Pregunta incómoda:** ¿Cuándo se entera el autor de que algo no convence, y qué pasa la semana después de publicar el enlace en vivo?

**Respuesta propuesta:** Añadir dos hitos: (a) **Validación del día 30**: mostrar las capas 1 y 2 (FNOL en texto, bandeja, evals) a 2 o 3 personas del ICP (un ingeniero senior de agentes, alguien de seguros si es posible) con tres preguntas fijas: qué buscarías primero, qué no te creerías, qué te haría pedir la demo; ajustar el PRD con las respuestas. (b) **Día 2 del enlace en vivo**: monitoreo de errores y latencia, cada caso fallido enrutado al golden set, alerta de consumo de cuota gratuita, y rollback documentado (redeploy de la versión anterior). Ambos entran al roadmap de 90 días y a las user stories de Incepción.

**Decisión de Miguel (2026-09-15):** acepto.

---

## PUNTO 9 — Métricas AI-specific que el marco pide y el PVB no tiene

**Crítica:** El canvas del marco separa métricas de usuario de métricas específicas de IA (factualidad, seguridad, drift). El PVB tiene métricas de producto (completitud, citación, latencia) pero no nombra el drift ni la seguridad: qué pasa cuando cambia el modelo gratuito o el proveedor de voz, y cuántas veces el agente dice algo fuera de su alcance.

**Pregunta incómoda:** ¿Cómo sabremos que el sistema empeoró sin que nadie lo reporte?

**Respuesta propuesta:** Añadir dos métricas: **tasa de respuestas fuera de alcance** (el agente opina sobre cobertura o dinero; objetivo 0 en el golden set, con eval de juez más patrones) y **regresión entre versiones** (el golden set corre en CI en cada cambio y ante cada cambio de modelo o proveedor; cualquier caída en completitud o citación bloquea el merge). Con eso, el "model drift" del marco tiene un detector.

**Decisión de Miguel (2026-09-15):** acepto.

---

## Resumen de cambios propuestos para el PVB v1.1

| # | Cambio | Sección del PVB |
| --- | --- | --- |
| 1 | Separar visión del proyecto y visión del producto; nombrar la parte durable (evidencia y gobierno) y la perecedera (voz) | 1 |
| 2 | Veto holder: revisor senior; estrategia "Cómo falla" y "Lo que no hace" en el README | 2 |
| 3 | Reordenar dolores (workflow primero) y añadir Discovery Debt Log con fechas de recheck | 3 |
| 4 | Paradigma Agent; principio de diseño de expectativas; corregir lista de corte (el español se reduce, no se corta); mapa FTCEM como artefacto del PRD | 4, 8 |
| 5 | KPI de costo por caso exitoso; triángulo de decisión explícito; North Star medible (solicitudes por mes); declarar uso de datos del tier gratuito | 5 |
| 6 | Moat primario: Trust vía evidencia verificable; posicionamiento "sistema de agentes de producción con evidencia, demostrado en seguros con voz" | 6 |
| 7 | Arena Enhancer; plan B de plataforma explícito; respuestas a las preguntas 2, 3 y 5 en "Riesgos críticos" | 7 |
| 8 | Hito de validación del día 30 y checklist de día 2 para el enlace en vivo | 8 |
| 9 | Métricas de fuera de alcance y de regresión entre versiones | 5 |

---
