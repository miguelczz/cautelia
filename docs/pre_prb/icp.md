# Perfil de Cliente Ideal (ICP) — Untangle

Untangle tiene dos "clientes" y conviene no mezclarlos. El **cliente real** del proyecto es quien evalúa el portafolio y decide contratar: líderes técnicos, ingenieros senior y reclutadores técnicos de empresas que construyen o compran sistemas agénticos. El **cliente del producto** es ficticio pero debe ser verosímil: la aseguradora o agencia (tenant) que operaría Untangle y el asegurado que llama. El primero decide el éxito del proyecto; el segundo decide si el proyecto parece real. Los principales tomadores de decisión del cliente real son el **Engineering Manager o Head of AI** que abre la vacante, el **Staff o Senior AI Engineer** que hace la revisión técnica, y el **reclutador técnico** que hace el primer filtro en menos de dos minutos.

A continuación, se detalla el ICP, junto con sus principales dolores y deseos.

## A. Cliente real: quien evalúa el portafolio

**Perfil de Cliente Ideal (Segmentos Principales)**

* **Equipos de producto de IA en empresas medianas y grandes (cualquier industria):** contratan "AI Engineer" o "Agentic AI Engineer" para llevar agentes a producción; el mercado estadounidense registró unas 90.000 ofertas de agentic AI en 2026 (crecimiento de 280% interanual) y LinkedIn puso "AI Engineer" como el título de más rápido crecimiento (ver `idea.md`, fuente 67). Evalúan pensamiento de producción: manejo de fallos, observabilidad, evals, control de acceso.
* **Consultoras y proveedores de servicios de IA (forward-deployed engineers):** venden implementaciones a clientes regulados; buscan gente que sepa integrar voz, RAG y reglas con trazabilidad. Su prueba favorita: "muéstrame cómo falla".
* **Insurtechs y aseguradoras con equipos de innovación:** conocen FNOL, ACORD y la frontera de adjudicación; detectan en segundos si un proyecto de seguros es ingenuo. Son minoría numérica pero el segmento donde Untangle más destaca si está bien hecho.
* **Reclutadores técnicos y agencias de talento en IA:** no leen código; leen el README, ven el video y buscan el enlace en vivo. Deciden si el perfil pasa al equipo técnico.

**Principales Dolores (Pain Points)**

* **Portafolios de tutoriales:** "un proyecto RAG de producción con evals apropiadas vale más que cinco clones de tutorial"; la mayoría de los portafolios son demos que funcionan porque ignoran límites de tasa, alucinaciones con entradas raras y costos (fuentes 66 de `idea.md` y J de `critica.md`).
* **Reclamos sin línea base:** "40% mejor" sin decir mejor que qué; proyectos que nombran cumplimiento sin mecanismos.
* **Sin evidencia de fallos:** "casi ningún candidato mide si su app funciona"; falta un golden set, una puntuación y una lista honesta de lo que se rompe.
* **Tiempo de evaluación:** unos 90 segundos para decidir si vale la pena seguir; sin enlace en vivo ni video claro, el perfil se descarta.
* **Ruido de "multiagente":** la comunidad técnica desconfía por defecto de sistemas multiagente sin justificación (MAST, Cognition); un proyecto que lo usa como palabra de moda pierde puntos.

**Principales Deseos (Desires)**

* **Ver producción, no promesa:** manejo de fallos definido, trazas por decisión, costo y latencia medidos, degradación elegante.
* **Ver evals con números y fallos:** un reporte por caso, aprobado o fallido, con la distribución del golden set declarada.
* **Ver una frontera clara entre modelo y reglas:** el modelo extrae y redacta; las decisiones de cobertura y dinero van a reglas y a una persona.
* **Poder correrlo:** enlace en vivo del modo texto, video de la voz, y ejecución local en un comando.
* **Conversar con el autor sobre trade-offs:** un README que explique por qué LangGraph y no CrewAI, por qué cascada y no voz a voz, por qué RLS y no Keycloak. El objetivo final del ICP es pedir la demo de veinte minutos que ofrece la landing.

## B. Cliente del producto: la aseguradora ficticia y su asegurado

**Perfil de Cliente Ideal (Segmentos Principales)**

* **Aseguradora regional de auto personal (tenant 1) y agencia independiente con varias aseguradoras (tenant 2 y 3):** volumen alto de FNOL y cotizaciones por teléfono, clientes bilingües (más de 41 millones de personas hablan español en casa en Estados Unidos, fuente 69 de `idea.md`), presión por actualizaciones digitales que hoy entregan solo el 22% de las veces (J.D. Power 2025).
* **El asegurado que llama:** acaba de tener un choque leve o quiere cotizar; está nervioso o apurado; interrumpe; no sabe el número de póliza de memoria; habla inglés o español.
* **El ajustador o suscriptor humano:** recibe casos derivados con el registro completo, la traza y las cláusulas citadas; aprueba o rechaza.
* **El administrador del tenant:** configura políticas de cumplimiento, reglas de elegibilidad y el corpus de pólizas de su aseguradora.

**Principales Dolores (Pain Points)**

* **FNOL incompleto a la primera:** llamadas de vuelta para pedir datos que faltaron; registro disperso entre notas y sistemas.
* **Respuestas de cobertura sin respaldo:** un agente humano o un bot que "cree" que algo está cubierto sin señalar la cláusula; riesgo de mala fe si la cita no existe.
* **Sin continuidad de canal:** el cliente repite el accidente al pasar de teléfono a chat o a un ajustador.
* **Cumplimiento manual:** divulgación de IA y grabación, manejo de datos personales, ruta a persona, todo dependiente de que cada operador lo recuerde.
* **Aislamiento entre marcas o clientes de la agencia:** un error de filtrado mezcla pólizas de dos aseguradoras.

**Principales Deseos (Desires)**

* **Registro estructurado y completo durante la llamada,** con los campos del aviso de siniestro estándar y un porcentaje de completitud visible.
* **Cada respuesta de cobertura con su cláusula,** o un "no encuentro cláusula que lo cubra" honesto y derivación.
* **Decisiones explicables:** qué regla se aplicó, con qué entradas, y por qué se derivó a una persona.
* **Servicio en el idioma del cliente,** con la misma calidad en inglés y español.
* **Aislamiento por tenant verificable** y políticas propias por aseguradora.

---

## Checklist antes de publicar

- [x] Buyer Personas identificados y descritos en el párrafo inicial (cliente real y cliente del producto).
- [x] Segmentos de cliente alineados con el producto/servicio.
- [x] Dolores redactados desde la perspectiva del cliente (no del producto).
- [x] Deseos vinculados a resultados o capacidades, no solo a funciones.
- [x] Tono y lenguaje coherentes con el resto de la documentación del proyecto.
