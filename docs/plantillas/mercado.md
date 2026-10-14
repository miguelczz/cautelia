# Análisis de contexto y justificación del proyecto

> **Nota de contexto:** Este documento NO es un análisis de mercado para competir externamente. Es la justificación interna de por qué construir un sistema multiagente de AIOps dentro de nuestro operador de telecomunicaciones, desarrollado por nuestro propio equipo de desarrolladores y funcionales (talento local), usando servidores propios y GPU externa (AWS Bedrock inicialmente) únicamente para inferencia. Los únicos costos a considerar son la GPU de inferencia y las herramientas de vibe engineering.

---

La convergencia de tres fuerzas —la complejidad creciente de nuestra propia red heterogénea (5G, FTTH, MPLS), la madurez de los modelos de lenguaje y sistemas multiagente accesibles mediante APIs de inferencia (AWS Bedrock), y la presión regulatoria del EU AI Act (2026)— crea el momento oportuno para que nuestro equipo interno construya una plataforma de AIOps Agéntico sobre nuestra propia infraestructura. La viabilidad está condicionada por las limitaciones reales de los LLMs actuales (11.34% de precisión en RCA complejo en benchmarks como OpenRCA vs. el 95% teórico) y la fragmentación de nuestros propios sistemas OSS, pero al ser un proyecto interno tenemos la ventaja de acceso directo a la red, al conocimiento tribal de nuestros ingenieros y a la telemetría real. A continuación, se presenta el análisis que sustenta esta viabilidad:

**1. Contexto operativo y complejidad de nuestra red**

Nuestra infraestructura es una red heterogénea multi-dominio que combina acceso FTTH/GPON, transporte MPLS, core IP, redes móviles 5G, servicios críticos (DNS, DHCP) y plataformas de seguridad. Esta complejidad genera volúmenes de telemetría que desbordan la capacidad de supervisión manual de nuestros equipos de NOC. Las redes modernas de nuestra escala pueden generar miles de alarmas por hora, con tormentas de eventos que dificultan la identificación de la causa raíz real.

Operamos en un momento de transición: nuestros procesos actuales corresponden aproximadamente a un Nivel 2-3 de autonomía (según la taxonomía del TM Forum), con automatización en dominios específicos pero decisiones humanas para casos complejos. El "abismo de complejidad" hacia el Nivel 4 (autogestión predictiva con gobernanza humana) es exactamente el problema que este proyecto busca resolver, no desde afuera como producto comercial, sino desde adentro con el conocimiento privilegiado que solo nuestro equipo tiene sobre cómo funciona nuestra red.

**2. El Problema a Resolver (Dolores internos)**

Nuestros equipos de NOC e ingeniería de red enfrentan una crisis operativa que se agrava con cada nueva tecnología desplegada. Los tiempos de diagnóstico se miden en horas o días para incidentes cross-dominio, mientras los SLAs exigen resolución en minutos. La correlación manual de alarmas entre sistemas aislados (EMS, GIS, CRM, ticketing) consume la mayor parte del tiempo de nuestros analistas, dejando poco margen para análisis proactivo o mejora continua.

La pérdida de conocimiento tribal por rotación de personal es un riesgo operativo real: cuando un ingeniero senior con 10 años de experiencia en nuestra topología GPON o MPLS se va, ese conocimiento desaparece. El análisis forense de paquetes (PCAP), esencial para RCA detallado de protocolos, sigue siendo una tarea artesanal que depende de pocos expertos. Y el riesgo de errores humanos en remediación es concreto: el apagón de AT&T en febrero de 2024 (125 millones de dispositivos desconectados por un error de configuración rutinario) ilustra lo que puede salir mal en cualquier operador, incluyendo el nuestro.

**3. Panorama de soluciones existentes y por qué construir internamente**

Hemos evaluado las soluciones disponibles en el mercado y ninguna resuelve nuestro problema de forma integral:

- **Nokia AVA / AI Solutions:** Plataforma monolítica centralizada sin arquitectura multiagente distribuida. No se adapta a la especificidad de nuestra topología ni permite personalización profunda por nuestro equipo. Costo de licenciamiento elevado y dependencia del vendor.

- **Ericsson Agentic AI:** Enfoque predominantemente mobile-first que no aborda de forma integral nuestras redes FTTH/GPON ni el core MPLS. Requiere adopción de su ecosistema completo.

- **Plataformas genéricas de AIOps (Datadog, Splunk, etc.):** Diseñadas para IT/DevOps, sin conocimiento profundo de protocolos telecom (GPON, MPLS, 5G RAN). Requieren personalización extensiva que termina siendo equivalente a construir internamente, pero con costos de licenciamiento recurrentes.

- **AutonomOps AI / HealR:** Lo más cercano al concepto de "war rooms" virtuales, pero orientado a DevOps/SRE genérico y sin especialización en nuestra infraestructura telecom.

**Por qué construir internamente es la mejor opción:**

- **Acceso privilegiado a nuestra red real:** Ningún vendor externo tiene acceso directo a nuestra telemetría, topología, configuraciones y conocimiento tribal. Nuestro equipo funcional conoce las particularidades de nuestra red que ningún producto genérico puede modelar.
- **Infraestructura propia:** Tenemos servidores donde montar toda la plataforma. Solo necesitamos GPU externa para inferencia (AWS Bedrock inicialmente, con flexibilidad de migrar a otras opciones como Azure OpenAI, Google Cloud, o GPUs dedicadas cuando sea conveniente).
- **Costos controlados y predecibles:** En lugar de licenciamientos anuales de cientos de miles de dólares, nuestros costos se reducen a: (1) GPU de inferencia via AWS Bedrock (~consumo por token/request), y (2) herramientas de vibe engineering para acelerar el desarrollo. El talento ya existe dentro de la organización.
- **Personalización total:** Podemos entrenar y ajustar los agentes con datos de nuestra propia red, crear escuadrones especializados en nuestros dominios específicos, e iterar rápidamente según las necesidades reales de nuestros ingenieros.
- **Propiedad intelectual interna:** Todo el conocimiento generado, los modelos ajustados y las integraciones quedan como activo de la organización, no como dependencia de un tercero.

**4. Factores Clave de Éxito (para el despliegue interno)**

Para que este proyecto sea exitoso dentro de nuestra organización, debe cumplir con requisitos específicos:

- **Integración con nuestros sistemas existentes sin reemplazo:** El sistema debe conectarse a nuestras plataformas actuales (EMS, GIS, CRM, ticketing, plataformas de monitoreo) mediante APIs y conectores, creando una capa de unificación sin exigir migración masiva de infraestructura OSS. Debe trabajar CON lo que tenemos, no en lugar de.

- **Adopción gradual por dominio empezando por bajo riesgo:** Comenzar con dominios donde el impacto de un error sea menor y la estandarización sea mayor (por ejemplo, diagnóstico en acceso FTTH), validar resultados con nuestros propios ingenieros, y expandir progresivamente a core MPLS y 5G RAN solo cuando la confianza esté demostrada.

- **Confianza del equipo humano como prerequisito:** Nuestros ingenieros de red deben percibir el sistema como una herramienta que amplifica su capacidad, no como una amenaza a su rol. La transparencia en el razonamiento del sistema, la autonomía graduable y los mecanismos de fail-safe son esenciales para que el equipo lo adopte en lugar de resistirlo.

- **Arquitectura de costos ligera y escalable:** Iniciar con AWS Bedrock para inferencia permite escalar el consumo de GPU según la demanda sin inversión de capital en hardware de cómputo AI. Las herramientas de vibe engineering (Cursor, Claude Code, frameworks de agentes) permiten al equipo desarrollar rápido con costos de suscripción mensuales modestos. Si Bedrock no resulta óptimo, la arquitectura debe permitir migrar a otras GPUs sin rediseñar el sistema.

- **Cumplimiento regulatorio desde el diseño:** Aunque somos un proyecto interno, cualquier sistema autónomo que toque nuestra red de producción debe ser auditable, trazable y alineado con EU AI Act y normativas locales. Es más fácil diseñar esto desde el inicio que retrofitearlo después de una auditoría.

**Conclusión**

Construir un sistema de AIOps Agéntico multiagente internamente es la opción más viable y eficiente para nuestra organización porque combina el acceso privilegiado a nuestra red real con un modelo de costos ligero (GPU de inferencia + herramientas de vibe engineering), aprovechando el talento de desarrolladores y funcionales que ya conocen nuestra infraestructura. La urgencia es real (MTTR insostenible, pérdida de conocimiento tribal, presión regulatoria), la infraestructura de servidores ya existe, y el enfoque gradual (FTTH primero, core después) mitiga el riesgo. No necesitamos competir con nadie ni vender nada: necesitamos resolver nuestro propio problema operativo, y nuestro equipo es quien mejor posicionado está para hacerlo.

---
