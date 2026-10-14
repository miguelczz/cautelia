# Untangle: Sistema multiagente de IA para seguros

(cotización, suscripción y gestión de siniestros con voz en tiempo real)

Fuente: brief escrito por el autor del proyecto, entregado el 2026-09-15.

## Contexto y objetivo

Estoy construyendo un proyecto de portafolio de nivel producción, NO un clon de tutorial, para demostrar ante empleadores internacionales (cualquier industria) capacidad real de ingeniería de IA agencial full-stack. El dominio elegido es seguros (cotización, suscripción y FNOL, First Notice of Loss / primer reporte de siniestro) porque combina alta demanda de contratación, arquitectura multiagente genuina (no forzada) y encaje natural con voz, telemetría y RAG.

## Flujo funcional (camino feliz de la demo, 3-5 min)

1. Un usuario llama (voz en tiempo real) para reportar un accidente O para pedir una cotización de una póliza.
2. Un agente de intake conversa por voz, extrae los datos relevantes (identidad, tipo de evento, detalles del siniestro o del riesgo a cotizar) y los estructura.
3. Un agente de verificación confirma la cobertura/elegibilidad consultando (vía RAG) la póliza y las guías de suscripción reales del "carrier" simulado.
4. Un agente de decisión (suscripción o triage de siniestro) aplica reglas de negocio y genera una recomendación o un caso abierto.
5. Un agente de cumplimiento/orquestador revisa que la interacción completa cumpla las políticas del tenant (aseguradora/agencia) antes de cerrar el caso.
6. Todo el recorrido queda trazado en un dashboard de observabilidad: qué agente decidió qué, con qué datos, en cuánto tiempo, con qué costo.

## Componente 1: Sistema multiagente (obligatorio)

Mínimo 4 agentes con responsabilidad y herramientas propias, NO un solo LLM con prompts distintos disfrazado de "equipo":

- Agente de Intake (conversación por voz, extracción estructurada)
- Agente de Verificación/Elegibilidad (RAG sobre pólizas)
- Agente de Decisión (suscripción o triage de siniestro, reglas de negocio + score de riesgo)
- Agente Orquestador/Cumplimiento (coordina, aplica políticas por tenant, decide escalar a humano)

Framework sugerido: LangGraph o CrewAI, con estado/contexto compartido entre canales (si el usuario retoma por chat lo que empezó por voz, el contexto persiste).

## Componente 2: Voz en tiempo real (obligatorio)

Pipeline STT → LLM → TTS con manejo de interrupciones y turno de palabra. No construir el pipeline desde cero: usar un framework de orquestación de voz (LiveKit Agents o Pipecat) sobre un proveedor de STT/TTS de baja latencia. Meta de latencia razonable para demo: round-trip bajo ~700ms.

## Componente 3: Telemetría y observabilidad (obligatorio)

Trazabilidad completa de cada decisión de agente: qué agente actuó, qué input recibió, qué herramienta invocó, qué output produjo, cuánto costó/tardó. Usar una herramienta estándar de la industria (Langfuse o Arize Phoenix, ambas con tier gratuito/self-host) en vez de logs caseros. Debe incluir un dashboard visible en la demo, no solo logs internos.

## Componente 4 (diferenciador elegido): RAG sobre pólizas

Base de conocimiento propia con documentos sintéticos de pólizas, exclusiones de cobertura y guías de suscripción (varias por "carrier"/producto simulado). El agente de verificación debe CITAR la cláusula específica que sustenta su respuesta, no inventar condiciones de cobertura. Esto es lo que hace la decisión verificable y defendible frente a un evaluador técnico.

## Arquitectura multi-tenant (soporte, no es el diferenciador principal)

Simular 2-3 "agencias/aseguradoras" como tenants con aislamiento de datos entre ellas (reutilizable de mi experiencia previa con Keycloak/row-level security), aunque el foco central del proyecto sigue siendo el componente 4 (RAG).

## Datos

100% sintéticos: pólizas, clientes y siniestros ficticios generados para la demo. Cero datos reales de personas o aseguradoras. Declarar esto explícitamente en el README.

## Fuera de alcance (a propósito)

- No integrar con un carrier o sistema bancario/asegurador real.
- No afirmar cumplimiento regulatorio certificado (SOC2, HIPAA-style, etc.). Solo "inspirado en" patrones reales, documentado como tal.
- No intentar cubrir todos los productos de seguro (auto, hogar, vida...); un solo producto bien resuelto > cobertura superficial de varios.

## Riesgos a vigilar durante el build

- No sobrevender el nivel de cumplimiento en el copy del proyecto.
- Fundamentar el flujo de negocio en estándares reales publicados (p. ej. formularios ACORD) para que no se vea ingenuo ante alguien del sector.
- Priorizar un solo camino feliz pulido de principio a fin sobre cobertura amplia y a medias.

## Entregable de la demo

Video o demo en vivo de 3-5 min: llamada de voz completa desde el reporte inicial hasta la decisión, con el dashboard de observabilidad y una vista del agente citando la cláusula de la póliza que usó. README con arquitectura, diagrama de agentes, y aclaración explícita de alcance/datos sintéticos.

---

## Adenda del autor (2026-09-15, sesión 1)

Aclaraciones dadas por Miguel después del brief, registradas para que el deep research, el PVB y el PRD las respeten:

1. **Naturaleza**: proyecto demostrativo de portafolio. El objetivo es que las empresas se interesen en contratar al autor. Eso no cambia que el aplicativo debe ser **funcional en su totalidad**: lo único de prueba son los datos; todo lo demás (voz, agentes, RAG, reglas, trazas, aislamiento por tenant) funciona de verdad.
2. **Lógica de negocio proporcional a una demo**: no habrá tarifas reales. La cotización, si existe, produce elegibilidad y un valor indicativo calculado por reglas sintéticas declaradas como ficticias, nunca pricing actuarial.
3. **Producto de seguro único**: auto. El camino pulido es FNOL (primer aviso de siniestro) de auto.
4. **Idioma de la demo de voz**: inglés y español, ambos. Puede ser por selección al inicio de la llamada o por dos configuraciones distintas; lo importante es que existan los dos.
5. **Ajustes aceptados**: los 12 ajustes de [01-evaluacion-brief.md](01-evaluacion-brief.md) quedan aprobados como lineamientos.
6. **Deep research**: aprobado para ejecutarse desde Claude Code con búsqueda web y fuentes citadas.
7. **Framework AIDLC**: se usa la versión actual de AWS (2.9.0), no la v0.1.5 de la guía. La guía del equipo tiene más de seis meses y debe actualizarse a la versión actual como parte de este proyecto.
8. **Costo cero**: el proyecto debe salir gratis. Se eligen opciones con tier gratuito o self-host; donde no exista opción gratuita, se elige la mejor y se documenta. La selección concreta se hace en su momento dentro de la metodología (diseño de aplicación y ADRs).
9. **Landing**: se construyó aparte, con un tutorial, como base. Se alineará a lo que el aplicativo sea realmente a medida que se avance. El aplicativo define la verdad; la landing la refleja.
10. **LLM de pago, barato y rentable (decisión del 2026-09-15, enmienda al punto 8):** un modelo local es demasiado exigente para el computador del autor. El LLM se paga; el criterio es que sea barato y rentable para la funcionalidad. El resto del stack sigue en costo cero. La selección concreta y el tope de gasto quedan en el plan (D-015).
11. **LLM y tope (decisión del 2026-09-15):** Gemini 2.5 Flash-Lite en tier de pago para voz y trabajo de fondo; tope de gasto de **5 USD** en los 90 días con **alerta en 3 USD**. Desarrollo y evals en texto con el tier gratuito. Los 9 puntos de la crítica del PVB quedaron aceptados; el PVB v1.1 los incorpora.
