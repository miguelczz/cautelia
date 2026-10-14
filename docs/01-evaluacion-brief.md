# Evaluación del brief de Untangle

Fecha: 2026-09-15. Autor: Claude (sesión 1), a petición de Miguel antes de iniciar el paso 1.
Insumos: [00-brief-untangle.md](00-brief-untangle.md), [`design-package.md`](../design-package.md) (lo que la landing ya promete en público), y la aclaración de Miguel: proyecto demostrativo de portafolio, pero funcional en su totalidad; lo único de prueba son los datos.

Este documento no reemplaza al brief. Es la lista de ajustes que propongo llevar al deep research (paso 1), al PVB (paso 3) y al PRD (paso 5).

---

## 1. Veredicto

El brief es una base buena, mejor que la mayoría de los briefs de portafolio: tiene objetivo claro, dominio justificado, componentes obligatorios, fuera de alcance explícito, riesgos y entregable. Los instintos correctos ya están: datos sintéticos declarados, no sobrevender cumplimiento, un solo camino feliz pulido.

Lo que necesita pulirse no es la idea sino tres cosas: (a) el brief y la landing cuentan dos arquitecturas distintas, (b) faltan dos componentes que un evaluador senior busca primero (evals y manejo de fallos), y (c) el alcance sigue siendo amplio para una persona, aunque el brief diga lo contrario.

---

## 2. Lo que está bien y no se toca

- Objetivo: producción, no tutorial. Cada decisión de abajo se juzga contra eso.
- Dominio: seguros con FNOL es multiagente de verdad, tiene estándares públicos (ACORD) y un evaluador del sector lo reconoce.
- RAG con citación de cláusula como diferenciador. Es lo que hace la decisión defendible.
- Datos 100% sintéticos y declarados. Cero datos reales.
- Cumplimiento "inspirado en", nunca "certificado".
- Un solo producto de seguro.
- Entregable concreto: demo de 3 a 5 minutos, README con arquitectura y alcance.

---

## 3. Desalineación entre la landing y el brief

La landing ya está publicada y un evaluador la va a leer antes que el código. Lo que diga el aplicativo tiene que coincidir.

| Tema | Landing (público) | Brief | Qué propongo |
|---|---|---|---|
| Agentes | 6 por dominio: Orchestrator, Intake, Quote, Underwriting, Claims (FNOL), Documents | 4 por función: Intake, Verificación/Elegibilidad, Decisión, Orquestador/Cumplimiento | Arquitectura real por función (brief), porque demuestra responsabilidad y herramientas propias. Documents pasa a ser una herramienta, no un agente. Después se ajusta el copy de la landing para que coincida; es barato. |
| Orquestador | "Routes each turn, keeps the shared state small, decides when a person needs to step in" | Combinado con cumplimiento | Separar: el orquestador es código (el grafo), no un prompt. Cumplimiento es una compuerta aparte. Ver ajuste 1. |
| Evals | Sección completa: golden set, puntuación, lista honesta de fallas, cuatro métricas | No aparece | Agregar como componente obligatorio. Ver ajuste 3. |
| Reglas | "Priced quote using the carrier's rating rules, not the model's opinion" | "reglas de negocio + score de riesgo" | Reglas y tarifas deterministas en código o configuración por tenant. El modelo extrae hechos y redacta; no puntúa riesgo. Ver ajuste 2. |
| Handoff humano | "Anything that touches coverage or money goes to a person, with the trace attached" | "decide escalar a humano", sin superficie para ese humano | Agregar una bandeja mínima del ajustador. Ver ajuste 4. |
| Registro estructurado | Readout en vivo: "location ✓ time ✓ injuries: none ✓ other party: pending" | Implícito en "extrae y estructura" | Hacer del registro del caso la columna vertebral del sistema. Ver ajuste 5. |
| Interrupciones | "The caller can interrupt. The agent stops mid-sentence, keeps the state" | "manejo de interrupciones y turno de palabra" | Coinciden. Falta definir la métrica. Ver ajuste 6. |

---

## 4. Ajustes recomendados

### Ajuste 1. El orquestador es código, no un agente con prompt

Un evaluador senior desconfía de "un agente orquestador" porque suele ser un LLM decidiendo rutas de forma opaca. Propongo que la orquestación sea el grafo de estados (LangGraph o equivalente): nodos, transiciones, checkpoints y puntos de interrupción para humano, todo explícito y testeable. Los cuatro agentes con responsabilidad propia quedan así:

1. **Intake**: conversa por voz, llena el registro del caso, pregunta solo lo que falta.
2. **Verificación de póliza**: busca en la póliza y guías del tenant, responde siempre con cláusula citada o con "no encuentro cláusula que lo cubra".
3. **Decisión**: aplica reglas deterministas (elegibilidad, triage del siniestro, tarifa) y produce una recomendación con la evidencia adjunta.
4. **Cumplimiento**: compuerta previa al cierre. Verifica contra las políticas del tenant (qué se prometió, qué se citó, qué datos personales se manejaron) y decide cerrar o derivar a una persona.

Cada uno con herramientas distintas, esquema de salida distinto y trazas separadas. Eso es lo que responde a "no es un LLM con cuatro prompts".

### Ajuste 2. Reglas deterministas, modelo para extraer y redactar

Un "score de riesgo" generado por un modelo es una bandera roja para alguien de seguros y contradice la landing. Propongo: tablas de tarifa y reglas de elegibilidad y triage como código o configuración versionada por tenant, con tests unitarios. El modelo extrae hechos del habla, consulta la póliza y redacta explicaciones. Cada decisión queda con: regla aplicada, entradas, cláusula citada. Esto es más simple de construir y mucho más defendible.

### Ajuste 3. Evals como componente obligatorio (componente 5)

Para contratación es la señal más fuerte, y la landing ya lo promete. Propongo:

- Golden set de llamadas guionizadas en modo texto (deterministas, corren en CI), más un subconjunto en voz.
- Métricas mínimas: completitud del registro FNOL, precisión de citación (la cláusula citada sostiene la respuesta), derivaciones correctas a persona, interrupciones manejadas sin perder estado, latencia por turno.
- Reporte por caso, aprobado o fallido, y una lista pública de casos que fallan. Va en el README.

### Ajuste 4. Bandeja del ajustador (la superficie humana)

Sin esto, "escalar a humano" es un log. Con una vista mínima (casos pendientes, registro completo, traza, cláusulas citadas, aprobar o rechazar con comentario), la demo cierra el ciclo y se ve el HITL de verdad. Es pequeño y de alto valor en el video.

### Ajuste 5. El registro del caso es la columna vertebral

Un solo esquema de caso, basado en los campos del formulario ACORD 2 (Automobile Loss Notice) para FNOL y del ACORD 90 (Personal Auto Application) para cotización. Se usa la estructura de campos, no los formularios (tienen licencia). La completitud del registro dirige las preguntas de Intake y es la métrica principal de la eval. Así el sistema tiene un objetivo medible en cada turno.

### Ajuste 6. Definir la métrica de latencia

"Round-trip bajo 700 ms" necesita definición para que sea creíble: tiempo desde el fin del habla del usuario hasta el primer audio de respuesta, medido p50 y p95 en el golden set de voz. Además, dos métricas que la landing ya nombra: tiempo de detección de fin de turno y tasa de interrupciones manejadas. Sin definición, un evaluador de voz lo descarta.

### Ajuste 7. Manejo de fallos como requisito explícito

El brief no lo lista y es lo primero que un evaluador pregunta ("how you handle failures"). Propongo que el PRD tenga una sección con comportamiento definido para: salida inválida del modelo, herramienta que expira, RAG sin resultados, silencio del usuario, caída del proveedor de voz (degradar a texto), llamada cortada a mitad (el caso queda reanudable), y reintentos idempotentes. Cada uno con su eval.

### Ajuste 8. Un camino feliz, dos flujos con prioridad clara

El brief pide un camino feliz, pero abre dos puertas (siniestro o cotización). Propongo: **FNOL de auto** es el camino pulido de punta a punta (voz, RAG, decisión, cumplimiento, bandeja, traza). **Cotización con elegibilidad** es el segundo flujo, más delgado, que reutiliza los mismos agentes y demuestra que la arquitectura no es de un solo caso. Suscripción se presenta como "elegibilidad y derivación", no como decisión de suscripción, que es lo que dice la landing.

### Ajuste 9. Esqueleto andante en texto antes que voz

Orden de construcción: primero el flujo FNOL completo en modo texto (registro, RAG con citas, reglas, cumplimiento, trazas, evals). Luego la capa de voz encima. Así hay algo demostrable temprano y la voz no bloquea todo lo demás. Esto se refleja en las Units de Incepción.

### Ajuste 10. Multi-tenant proporcional

Es soporte, no diferenciador. Propongo: `tenant_id` con aislamiento en base de datos (RLS), colecciones de RAG por tenant y políticas de cumplimiento por tenant como configuración. Keycloak solo si tu experiencia previa lo hace barato; si no, un emisor de tokens simple basta y se documenta como decisión. La ganancia de demo está en mostrar que dos aseguradoras ficticias reciben respuestas distintas con la misma llamada.

### Ajuste 11. Continuidad voz a chat como "should", no "must"

Es una buena señal de estado compartido, pero agrega una segunda interfaz. Propongo mantenerla como objetivo secundario: reanudar un caso por chat con el mismo identificador. Si el tiempo alcanza, se demuestra en el video en diez segundos.

### Ajuste 12. Datos personales aunque sean sintéticos

Demostrar redacción de datos personales en las trazas y en los logs, y retención definida. No cuesta mucho y responde a la línea de la landing "before the model: input checks, personal data handling".

---

## 5. Alcance propuesto para discutir (alimenta el PVB y el MoSCoW del PRD)

Propuesta inicial, no definitiva. Se decide en los pasos 3 y 5.

- **Must**: FNOL de auto por voz de punta a punta; registro del caso con esquema ACORD 2; cuatro agentes con herramientas propias sobre un grafo explícito; RAG con citación de cláusula sobre pólizas sintéticas de 2 tenants; reglas deterministas de triage; compuerta de cumplimiento; bandeja del ajustador; trazas con costo y latencia en Langfuse o Phoenix; golden set con reporte; manejo de fallos definido; README con arquitectura, diagrama, evals y declaración de datos sintéticos; video de 3 a 5 minutos.
- **Should**: cotización con elegibilidad y derivación (ACORD 90); continuidad voz a chat; tercer tenant; redacción de datos personales en trazas.
- **Could**: métricas de calidad de voz por proveedor; vista de comparación entre tenants; despliegue público de la demo de voz (costo).
- **Won't (por ahora)**: integración con sistemas reales; varios productos de seguro; certificaciones; suscripción real con pricing actuarial; app móvil.

---

## 6. Decisiones que necesito de Miguel

1. Producto de seguro: **auto** (propuesto).
2. Idioma de la demo de voz: inglés (empleadores internacionales) con español opcional, o al revés. Afecta la elección de proveedores de voz.
3. Aceptas los ajustes 1 a 12 como lineamientos para el deep research y el PVB, o quieres discutir alguno antes.
4. Keycloak: reutilizar tu experiencia o simplificar (ajuste 10).

---

## 7. Cómo entra esto al flujo AIDLC

- Paso 1 (deep research): se investiga con estos ajustes como hipótesis a confirmar o refutar, no como decisiones cerradas.
- Paso 3 (PVB): los principios no negociables salen de los ajustes 1, 2, 3 y 7.
- Paso 5 (PRD): el MoSCoW de la sección 5 es el punto de partida; los ajustes 6 y 7 se vuelven requisitos con métrica.
- Incepción (Application Design): las decisiones de framework (LangGraph o CrewAI, LiveKit o Pipecat, Langfuse o Phoenix, vector store) se toman como ADRs con opciones y consecuencias, no aquí.
