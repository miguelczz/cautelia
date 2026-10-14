# Product Vision Board — Untangle

**Versión:** 1.1
**Fecha:** 2026-09-15
**Basado en:** idea.md, critica.md, overview.md, mercado.md, icp.md, brief con adenda (puntos 1 a 11), evaluación del brief, respuestas_critica_pvb.md (9 puntos aceptados por Miguel)
**Naturaleza:** Proyecto de portafolio de nivel producción, funcional en su totalidad, datos 100% sintéticos, costo cero salvo el LLM (tope de 5 USD). Sistema de agentes de producción con evidencia verificable, demostrado en seguros de auto: voz bilingüe en tiempo real, chat con RAG, grafo multiagente con persona en el bucle, reglas deterministas, telemetría, evals, multi-tenant.

Cambios respecto a la v1.0: visión en dos frases; veto holder y estrategia "Cómo falla"; dolores de workflow primero y Discovery Debt Log; paradigma Agent y diseño de expectativas; lista de corte corregida (el español se reduce, nunca se corta); LLM de pago barato con tope; costo por caso exitoso; North Star medible; moat de confianza; arena Enhancer y respuestas a las preguntas 2, 3 y 5; validación del día 30 y checklist de día 2; métricas de fuera de alcance y regresión; mapa de componentes demostrables.

---

## 1. Visión

**Visión del proyecto**

> **Demostrar, con un sistema que funciona de punta a punta y se puede auditar, cómo se llevan agentes de IA a producción: orquestación explícita, evidencia verificable, personas en las decisiones que importan, telemetría de cada paso y evals con fallos a la vista.**

**Visión del producto**

> **Que cada respuesta de cobertura tenga una cláusula verificada detrás, cada decisión una regla explicable, y cada caso que toque cobertura o dinero una persona. La voz bilingüe y el chat son las puertas de entrada; el valor durable es el sistema de evidencia y gobierno.**

Durabilidad (3-Lens Discovery Test del marco): Durabilidad 4/5 (workflow, integración y cumplimiento persisten aunque los modelos de voz mejoren), Data 2/5 (datos sintéticos, sin flywheel: es un portafolio), Trust 5/5 (todo el diseño es para confianza verificable). Promedio 3,7, por encima del umbral de 3,5.

---

## 2. Usuarios Objetivo (Target Group)

### Usuarios Primarios (cliente real): Evaluadores técnicos del portafolio

| Dimensión | Detalle |
| --- | --- |
| **Rol** | Engineering Manager o Head of AI, Staff o Senior AI Engineer, forward-deployed engineer, en empresas de Estados Unidos y Europa |
| **Contexto** | Contratan ingenieros de agentes en un mercado con unas tres vacantes por candidato calificado (`idea.md`, 67) |
| **Dolor principal** | Portafolios de tutoriales sin evals, sin manejo de fallos, sin enlace en vivo |
| **Qué necesitan** | Ver producción: trazas, evals con fallos, frontera entre modelo y reglas, poder correrlo |
| **Poder de decisión** | Deciden la entrevista y la contratación |

### Usuarios Secundarios (cliente real): Reclutadores técnicos

| Dimensión | Detalle |
| --- | --- |
| **Rol** | Primer filtro; no leen código |
| **Dolor principal** | 90 segundos para decidir; sin video ni enlace, descartan |
| **Qué necesitan** | README claro, video de 3 a 5 minutos, enlace en vivo, un mensaje de LinkedIn fácil |
| **Poder de decisión** | Deciden si el perfil llega al equipo técnico |

### Veto holder: el revisor senior de la entrevista técnica

Puede matar la contratación aunque al reclutador le haya gustado el video: basta un fallo no declarado o una afirmación inflada. Estrategia para convertirlo en aliado: darle antes de que pregunte lo que va a buscar. El README tendrá una sección **"Cómo falla"** (casos fallidos del golden set con causa raíz), una sección **"Lo que no hace"** (sin integración real, sin cumplimiento certificado, sin pricing), ADRs con opciones descartadas, y un comando para reproducir las evals en su máquina. Pasa de buscar fallos a verificar que los declarados son los que hay.

### Personas del producto (ficticias, para diseñar y evaluar)

| Persona | Rol | Necesidad en el producto |
| --- | --- | --- |
| Asegurado que llama o escribe (EN y ES) | Reporta un choque leve o pide cotización; nervioso; interrumpe; no recuerda la póliza | Que lo entiendan, no repetir, saber qué sigue |
| Ajustador o suscriptor humano | Recibe casos derivados | Registro completo, traza, cláusulas citadas, aprobar o rechazar en un clic |
| Administrador del tenant | Aseguradora regional o agencia con varias aseguradoras | Reglas, políticas y corpus propios; aislamiento verificable |
| Área legal o de cumplimiento del tenant (veto holder del producto) | Aprueba el despliegue | Tabla principio → control → evidencia |

### Gate del sector

**Alguien de seguros que revise el proyecto.** Necesita: campos del aviso de siniestro estándar (estructura ACORD 2 y 90), póliza con estructura reconocible (ISO PP 00 01), reglas inspiradas en guías de suscripción públicas, y la frontera de adjudicación respetada.

---

## 3. Necesidades (Needs / Pains)

Ordenadas de más durable a menos durable, según el test del marco: primero los dolores de workflow, integración y cumplimiento; al final los de output, que la próxima generación de modelos atenúa.

### Dolores de workflow (durables)

| Pain | Quién lo sufre | Evidencia |
| --- | --- | --- |
| **Respuestas de cobertura sin respaldo** | Producto y evaluador | Citas a cláusulas inexistentes generan exposición a mala fe (`idea.md`, 44) |
| **Decisiones sin explicación ni traza** | Producto y evaluador | Reguladores exigen explicabilidad y evitar información engañosa (`critica.md`, I) |
| **"Multiagente" sin justificación** | Evaluador | MAST, Cognition y LangChain cuestionan el multiagente por defecto (`critica.md`, C1) |
| **Demos que funcionan solo cuando todo sale bien** | Evaluador | Banderas rojas publicadas: sin límites de tasa, alucinaciones, costos (`critica.md`, J) |
| **Reclamos sin línea base ni lista de fallos** | Evaluador | "Casi ningún candidato mide si su app funciona" (`idea.md`, 66) |
| **Aislamiento entre tenants no verificable** | Producto | "Tu cláusula WHERE no es un límite de seguridad" (`idea.md`, 49) |
| **Cumplimiento como texto, no como control** | Evaluador y legal del tenant | Nombrar NAIC sin controles produce el efecto contrario (`critica.md`, C7) |

### Dolores de experiencia (importantes, menos durables)

| Pain | Quién lo sufre | Evidencia |
| --- | --- | --- |
| **FNOL incompleto y actualizaciones pobres** | Producto | 22% de actualizaciones digitales adecuadas; 52% de riesgo de fuga (`idea.md`, 5) |
| **Sin continuidad entre voz y chat** | Producto | El cliente repite el accidente al cambiar de canal (`idea.md`, 2) |
| **Servicio en español de segunda** | Producto | 41 millones de hispanohablantes en casa en EE. UU. (`idea.md`, 69) |
| **Sin enlace en vivo ni video** | Reclutador | Guías de portafolio 2026 (`idea.md`, 66) |

### JTBD (Jobs To Be Done)

> **Cuando** un líder técnico evalúa candidatos para construir agentes de producción, **quiere** ver un sistema completo que maneje voz, chat, verificación con evidencia, reglas, personas y fallos, con evals y telemetría que pueda revisar en minutos, **para** decidir con confianza que ese ingeniero sabe llevar agentes a producción y pedirle la conversación.

JTBD del producto: **Cuando** un asegurado llama o escribe tras un choque, **quiere** que le entiendan a la primera, en su idioma, y que cada respuesta de cobertura tenga respaldo, **para** no repetir el accidente ni recibir promesas que la póliza no sostiene.

### Discovery Debt Log (suposiciones y cuándo se vuelven a revisar)

| Suposición | Evidencia | Método de validación | Riesgo si está mal | Recheck |
| --- | --- | --- | --- | --- |
| Los evaluadores premian evals y fallos publicados | Media (guías 2026, no un estudio) | Mostrar capas 1 y 2 a 2 o 3 ingenieros senior el día 30 | Alto | Día 30 |
| Gemini 2.5 Flash-Lite da latencia y extracción suficientes para voz | Débil (benchmarks de terceros) | Medir turn latency p95 y precisión de extracción en el esqueleto, semana 1 | Alto: subir solo el nodo que falle a 3.1 Flash-Lite | Semana 1 |
| El español diferencia el portafolio | Débil | Preguntar a los revisores del día 30 | Medio | Día 30 |
| El corpus sintético con estructura ISO parece real | Media | Que una persona del sector lea una póliza sintética | Medio | Día 45 |
| Las citas verificadas son el diferenciador percibido | Media | Reacción de los revisores a la vista de caso | Alto | Día 30 |
| El tope de 5 USD alcanza | Media (estimación de tokens) | Costo por caso en trazas desde el esqueleto; alerta en 3 USD | Medio: mover más trabajo al tier gratuito en texto | Continuo |

---

## 4. Producto (Product / Solution)

### One-Liner

**Untangle** es un sistema de agentes de producción con evidencia verificable, demostrado en seguros de auto: un asegurado llama o escribe, en inglés o español, y un flujo multiagente sobre un grafo explícito convierte la conversación en un caso completo, verifica la cobertura citando la cláusula exacta, aplica reglas deterministas y deriva a una persona con la traza adjunta; todo con telemetría por paso, evals públicas y aislamiento por tenant. Proyecto de portafolio, datos sintéticos, costo cero salvo el LLM.

### Paradigma

**Agent con límites**, según el marco: la IA ejecuta tareas dentro de rutas explícitas (capturar, verificar con cita, aplicar reglas, derivar). No es Autonomous: nada que toque cobertura o dinero se cierra sin una persona. No es un Assistant pasivo: el sistema lleva el caso de principio a fin.

### Mapa de componentes demostrables

Untangle no es "un agente de voz". La voz es uno de once componentes que un evaluador puede ver funcionando por separado. Cada uno demuestra una capacidad de ingeniería distinta.

| # | Componente | Qué demuestra ante un evaluador | Capa |
| --- | --- | --- | --- |
| 1 | **Caso estructurado** (esquema inspirado en ACORD 2 y 90, siete campos centrales, completitud visible) | Modelado de dominio y extracción estructurada bajo conversación | 1 |
| 2 | **Grafo multiagente con persona en el bucle** (Intake, Verificación, Decisión, Cumplimiento como nodos; `interrupt()` y checkpoints) | Orquestación explícita, estado durable, HITL real | 1 |
| 3 | **RAG con citación verificada** sobre pólizas sintéticas (pgvector, embeddings multilingües, búsqueda híbrida, verificación exacta del identificador) | RAG de producción, no de tutorial | 1 |
| 4 | **Chat web con RAG** (modo texto en vivo sobre el mismo grafo; enlace público) | El "chatbot con RAG integrado", hospedado y usable por cualquiera | 2 |
| 5 | **Motor de reglas por tenant** (10 a 20 reglas por flujo, salida referral, sin tarifas) | Frontera modelo / reglas; decisiones explicables | 1 |
| 6 | **Telemetría y observabilidad** (OpenTelemetry con convenciones GenAI, Langfuse; costo, latencia y tokens por caso y por agente; dashboard visible) | Observabilidad de agentes con estándar de industria | 1 |
| 7 | **Evals** (golden set en texto en CI; golden set de audio por idioma; precisión de citación; reporte con lista de fallos; regresión que bloquea el merge) | Rigor de evaluación, honestidad | 1 y 3 |
| 8 | **Bandeja del ajustador** (casos derivados con registro, traza y cláusulas; aprobar o rechazar reanuda el grafo) | Superficie humana, UX de HITL | 2 |
| 9 | **Voz bilingüe en tiempo real** (cascada STT → grafo → TTS; detección de turno; interrupciones; dos ritmos; inglés y español) | Voz de producción: latencia medida, barge-in | 3 y 4 |
| 10 | **Multi-tenant con RLS** (`tenant_id`, políticas y corpus por aseguradora, tests de aislamiento) | Seguridad de datos, arquitectura SaaS | 1 |
| 11 | **Guardrails y datos personales** (divulgación de IA, ruta a persona, PII redactada con Presidio, explicabilidad) | Cumplimiento como controles verificables | 1 y 3 |
| 12 | **Generador de datos sintéticos** (pólizas con estructura ISO, clientes, siniestros, golden sets con matriz de ejes) | Ingeniería de datos y de pruebas | 1 |
| 13 | **Cotización con elegibilidad** (segundo flujo sobre los mismos agentes) | Reutilización de la arquitectura | 5 |
| 14 | **Continuidad voz a chat** (reanudar un caso por chat con el mismo identificador) | Estado compartido entre canales | 6 (should) |
| 15 | **Documentos al caso** (subir un estimado o reporte policial sintético y extraerlo al registro) | Document AI integrado al flujo | Could |

### Principios no negociables

1. **Las personas deciden cobertura y dinero** — Los agentes capturan, verifican con cita, aplican reglas y derivan; nunca deciden cobertura.
2. **Ninguna cita sin cláusula existente** — Cada respuesta de cobertura lleva identificador de cláusula verificado, o dice que no encuentra cláusula y deriva.
3. **El orquestador es código** — Rutas explícitas en el grafo; ninguna acción sobre el caso fuera de una ruta; el grafo corre sin voz.
4. **Dos latencias, medidas y publicadas** — Turno conversacional (p95 < 800 ms) y decisión de fondo; el trabajo pesado nunca corre dentro del turno.
5. **Evals con fallos a la vista** — Golden sets en texto y audio con distribución declarada y lista pública de casos que fallan; una regresión bloquea el merge.
6. **Cumplimiento como controles** — Divulgación de IA y grabación por idioma, ruta a persona, PII redactada, explicabilidad por caso; "inspirado en", nunca "cumple con".
7. **Diseño de expectativas** — La landing promete solo lo construido; el README abre con "lo que hace, lo que no hace, cómo falla"; la primera frase de cada llamada dice qué puede y qué no puede hacer el agente.
8. **Datos y texto limpios** — Datos 100% sintéticos; pólizas originales con estructura ISO; sin formularios ni texto de terceros con derechos.
9. **Costo cero salvo el LLM** — Stack abierto y tiers gratuitos; el LLM se paga barato con tope de 5 USD y alerta en 3; cualquier otro gasto es una excepción escrita.

### Mapa de fallos (FTCEM) como artefacto del PRD

El PRD incluirá una tabla modo de fallo → disparador → consecuencia → alerta temprana → mitigación para, al menos: cita inexistente, alucinación bajo latencia del backend, extracción errónea de un campo central, interrupción no manejada, STT en español degradado, límite de tasa o cuota del LLM, fuga entre tenants, llamada cortada a mitad.

---

## 5. Valor (Business Value)

### Modelo de costos (no hay modelo de negocio: es un portafolio)

| Componente | Costo | Notas |
| --- | --- | --- |
| Frameworks y modelos abiertos | $0 | LangGraph, LiveKit Agents o Pipecat, Langfuse, promptfoo, Presidio, pgvector, Whisper, Kokoro |
| **LLM: Gemini 2.5 Flash-Lite, tier de pago (D-015)** | ~0,01 USD por llamada de 4 min | Sin límites del tier gratuito; los datos del tier de pago no se usan para entrenar; si un nodo falla en las evals, sube solo ese nodo a 3.1 Flash-Lite |
| Evals y desarrollo en texto | $0 | Tier gratuito de Gemini (proyecto y clave separados), donde la latencia no importa |
| STT comercial (Deepgram) | $0 | 200 USD de crédito gratuito, asignados al español |
| TTS: la voz paisa (D-016) | $0 con Cartesia gratuito; o unos 12 USD si la prueba ciega elige una voz de ElevenLabs (Starter dos meses) | La voz paisa solo en evals de audio, demos y video; iteración diaria con TTS barato. Pendiente de Miguel si sube el tope |
| Transporte de voz, base de datos, hosting del chat | $0 | Tiers gratuitos o auto-hospedado |
| **Tope de gasto del proyecto** | **5 USD en 90 días, alerta en 3** | Único gasto previsto: el LLM en voz y en la grabación. Equivale a unas 400 llamadas de 4 minutos |

### AI Decision Triangle (explícito)

| Componente | Optimiza | Trade-off aceptado |
| --- | --- | --- |
| Turno conversacional (Intake) | **Speed** | Modelo pequeño y prompts cortos pueden extraer peor; la eval de extracción por campo lo mide |
| Verificación y Cumplimiento (fondo) | **Capability** | Corren fuera del turno; toleran cola y reintento |
| Proyecto entero | **Cost** | Tope de 5 USD; el tier gratuito absorbe todo lo que no sea voz |

### North Star Metric

**Solicitudes de la demo de veinte minutos recibidas por LinkedIn, por mes.**
_(Medible desde el primer día; la analítica de la landing es una mejora posterior si existe un tier gratuito.)_

North Star del producto (interna): **porcentaje de conversaciones del golden set que llegan al registro final con todas las compuertas pasadas** (completitud ≥ 95%, citas verificadas, derivación correcta, cero respuestas fuera de alcance).

### KPIs clave (metas al cierre de los 90 días)

| Categoría | KPI | Meta |
| --- | --- | --- |
| **Producto** | Completitud del FNOL en los siete campos centrales (golden set) | ≥ 95% |
| **Producto** | Precisión de citación (cláusula existe y sostiene la afirmación) | ≥ 95%, con lista de fallos |
| **Producto** | Derivaciones correctas a persona | 100% de los casos que deben derivarse |
| **Producto** | Latencia de turno p95 (por idioma) | < 800 ms |
| **Producto** | Recuperación tras interrupción sin perder estado | > 90% |
| **IA** | Tasa de respuestas fuera de alcance (opina sobre cobertura o dinero) | 0 en el golden set |
| **IA** | Regresión entre versiones (evals en CI en cada cambio de código, modelo o proveedor) | Ninguna caída sin explicación; una caída bloquea el merge |
| **Economía** | Costo por caso exitoso (tokens y USD a precio de lista) | Publicado por caso; tendencia decreciente |
| **Portafolio** | Entregables visibles | Video, enlace en vivo del chat, repo ejecutable en un comando |
| **Portafolio** | Landing realineada al producto | Antes del video final |
| **Portafolio** | Solicitudes de demo por mes | Línea base en el primer mes; meta al tercero |

### Propuesta de impacto (Antes / Después)

| Métrica | Antes (portafolio típico) | Después (Untangle) |
| --- | --- | --- |
| Evidencia de producción | Demo que funciona en el camino feliz | Trazas, evals, fallos publicados, degradación definida |
| Justificación de "multiagente" | Palabra de moda | Grafo explícito con responsabilidades evaluables |
| Cobertura | El modelo "cree" | Cláusula citada y verificada, o derivación |
| Canales | Uno | Voz bilingüe y chat sobre el mismo grafo |
| Costo | Desconocido | Medido por caso; tope de 5 USD |

---

## 6. Diferenciación

### Moat primario: confianza vía evidencia verificable

> **Lo que otro candidato no copia en seis semanas con las mismas APIs no es la arquitectura, que es copiable, sino el rastro de evidencia: golden sets en texto y audio en dos idiomas con distribución declarada, la lista de fallos con causa raíz, las trazas con costo y latencia por caso, los ADRs con opciones descartadas y las lecciones aprendidas de construirlo con AIDLC.**

Posicionamiento: Untangle no se presenta como "agente de voz para seguros" sino como **"sistema de agentes de producción con evidencia verificable, demostrado en seguros con voz y chat"**. La voz es el gancho del video; la evidencia es el argumento.

### Comparación con las alternativas del evaluador

| Opción | Qué muestra | Qué no muestra |
| --- | --- | --- |
| Tutorial de voz (demo de LiveKit o Pipecat) | Pipeline STT-LLM-TTS | Dominio, evidencia, reglas, personas, evals |
| Tutorial de RAG o chatbot | Recuperación y respuesta | Citación verificada, corpus duro, multi-tenant |
| Ejemplo de tres capas (Pipecat + LangGraph) | Barreras de política | Dominio, evals, bilingüe, trazas con costo |
| Plataforma comercial (Parloa, PolyAI) | Producto cerrado | Nada del cómo |
| **Untangle** | La combinación completa, ejecutable y evaluada | Integración real con un carrier; cumplimiento certificado (a propósito) |

### Ejes

```
Eje 1: Demo del camino feliz ← → Producción evaluada con fallos públicos
Eje 2: Una pieza (voz, o RAG, o agentes) ← → Sistema completo con frontera modelo/reglas/personas

Untangle ocupa: producción evaluada + sistema completo
```

---

## 7. Contexto Estratégico

### Arena

**Enhancer** en lo técnico: mejora un workflow existente con patrones conocidos, hechos bien y con evidencia. No hay gigante enfrente porque no vende nada; las plataformas comerciales de voz para seguros se complementan citándolas como referencia de criterios.

### ¿Por qué ahora?

| Tendencia | Implicación |
| --- | --- |
| Demanda de ingenieros de agentes muy por encima de la oferta (`idea.md`, 67) | La ventana para diferenciarse con un proyecto completo está abierta |
| Los evaluadores ya piden evals, fallos y trazas (`idea.md`, 66) | Lo que Untangle muestra es lo que se evalúa |
| Frameworks de voz y agentes abiertos con detección de turno en español (`idea.md`, 29, 30) | Voz bilingüe de calidad es posible casi sin costo |
| Modelos rápidos a fracciones de centavo por llamada | Un tope de 5 USD cubre el proyecto |
| Escepticismo público sobre "multiagente" (`critica.md`, C1) | Justificar la arquitectura es una oportunidad de destacar |

### Decisiones estratégicas fundamentales

| Decisión | Resolución |
| --- | --- |
| Producto de seguro | Auto; FNOL como camino pulido; cotización con elegibilidad como segundo flujo delgado |
| Canales | Voz (inglés y español) y chat web sobre el mismo grafo; continuidad entre ellos como should |
| Idiomas | Inglés y español, ambos obligatorios; selección al inicio de la llamada en la primera versión; español con proveedores comerciales (créditos), inglés con stack local si hace falta ahorrar |
| Framework de agentes | LangGraph (grafo explícito, checkpoints, `interrupt()`); se confirma como ADR en Incepción |
| Framework de voz | LiveKit Agents o Pipecat; ADR en Incepción con criterios de integración con el grafo y costo |
| LLM | **Gemini 2.5 Flash-Lite en tier de pago para voz y trabajo de fondo; tier gratuito para desarrollo y evals en texto; 3.1 Flash-Lite solo para el nodo que falle en las evals; Groq si la latencia medida lo exige. Tope 5 USD, alerta 3 (D-015)** |
| Datos y vectores | Postgres con pgvector y RLS; un solo mecanismo de aislamiento |
| Observabilidad | OpenTelemetry con convenciones GenAI; Langfuse self-host; dashboard visible en la demo |
| Evals | promptfoo o DeepEval en CI; golden set de audio propio por idioma; regresión bloquea el merge |
| Multi-tenant | RLS y RAG por tenant en la primera versión; Keycloak en "Could" |
| Cumplimiento | Cuatro controles verificables; "inspirado en" |
| Entregables | Video, enlace en vivo del chat, repo ejecutable; landing realineada |
| Propiedad intelectual | Estructura de ACORD e ISO, texto original; nada de terceros en el repo |
| Metodología | AIDLC 2.9.0 (perfil `classic` para Incepción y Construcción; `infra` para despliegue) |

### Plan B de plataforma (trampa de plataforma del marco)

Cada proveedor externo tiene un sustituto declarado: Whisper por Deepgram, Kokoro o Chatterbox por Cartesia, LiveKit o Pipecat auto-hospedados por sus nubes, Postgres en Docker por Neon o Supabase, Langfuse self-host por su nube, y el tier gratuito de Gemini o Groq por el tier de pago. El grafo no depende del framework de voz: corre igual en el chat.

### Riesgos críticos (preguntas incómodas del marco)

| Pregunta | Respuesta |
| --- | --- |
| **¿Qué si el problema desaparece en 12 meses?** | La voz y la extracción se commoditizan; el sistema de evidencia y gobierno (citas verificadas, reglas, HITL, multi-tenant, evals) es un problema de workflow y persiste |
| **¿Quién es dueño de la data?** | Es sintética y propia; ningún tercero puede revocarla; las pólizas son originales |
| **¿Se avergonzaría un regulador si falla en público?** | Un fallo público sería una cita falsa o una promesa de cobertura; por eso la verificación exacta de citas, la regla "nunca decide cobertura" y el mapa FTCEM |
| **¿Puede otro replicarlo en seis semanas?** | La arquitectura sí; el rastro de evidencia y la honestidad acumulada no (sección 6) |
| **¿Cómo se rompe la confianza a escala?** | Primero por alucinación bajo latencia del backend y por límites de tasa que degradan en silencio; mitigación: el turno nunca espera al backend, respuestas de espera explícitas, alertas de tasa de error y de latencia de decisión en las trazas |

### Top 3 riesgos operativos

| Riesgo | Mitigación |
| --- | --- |
| **Demo-ware: alcance de equipo para una persona** (`critica.md`, C11) | Capas demostrables con lista de corte; el video se graba en la capa 3; esqueleto andante en texto primero |
| **Latencia de turno con trabajo pesado dentro** (`critica.md`, C2) | Dos ritmos; prefetch y llamadas especulativas; dos métricas publicadas |
| **Tope de 5 USD agotado** (`critica.md`, C3 actualizada) | Tier gratuito para todo lo que no sea voz; prompt caching y prompts cortos; costo por caso en trazas; alerta en 3 USD |

---

## 8. Roadmap de Alto Nivel (90 días)

| Fase | Entregable principal | Hito |
| --- | --- | --- |
| **Días 1–30** | Cierre de pre-incepción (PVB v1.1, PRD) e Incepción AIDLC 2.9.0 (requisitos, stories, mockups de la bandeja, ADRs, units, contratos, plan). Capa 1: FNOL en texto con caso, RAG con citación verificada, reglas, compuerta, telemetría y golden set en CI. Capa 2: bandeja del ajustador y chat web en vivo | **Validación del día 30:** mostrar capas 1 y 2 a 2 o 3 personas del perfil (un ingeniero senior de agentes, alguien de seguros si es posible) con tres preguntas fijas: qué buscarías primero, qué no te creerías, qué te haría pedir la demo; ajustar el PRD con las respuestas |
| **Días 31–60** | Capa 3: voz en inglés con detección de turno e interrupciones, dos ritmos, golden set de audio en inglés, dos latencias medidas. Video v1. **Checklist de día 2 del chat en vivo:** monitoreo de errores y latencia, cada caso fallido enrutado al golden set, alerta de consumo de cuota, rollback documentado | Llamada de voz de punta a punta grabada; latencias publicadas; chat en vivo con día 2 cumplido |
| **Días 61–90** | Capa 4: voz en español con golden set propio. Capa 5: cotización con elegibilidad. Realineación de la landing. README final con "lo que hace, lo que no hace, cómo falla", arquitectura, ADRs, evals. Video final de 3 a 5 minutos | Los tres entregables en línea; la landing apunta a ellos; empieza la medición del North Star |

**Lista de corte si el tiempo no alcanza, en este orden:** continuidad voz a chat (capa 6), cotización (capa 5), documentos al caso (Could). **El español nunca se corta:** si falta tiempo se reduce su alcance (menos casos en el golden set de audio, una sola voz), no su existencia. **Nunca se corta:** capas 1 a 3, evals, telemetría, README.

---
