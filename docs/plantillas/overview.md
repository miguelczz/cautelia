# **Análisis Profundo: Sistema Multiagente para Autocuración de Nuestra Red Telecom — Arquitectura, Viabilidad y Marco Regulatorio (2025-2026)**

> **Contexto del proyecto:** Este análisis sustenta el desarrollo interno de un sistema multiagente de AIOps por nuestro equipo de desarrolladores y funcionales (talento local) dentro del operador. No es un producto comercial ni compite externamente. Se despliega sobre servidores propios con GPU externa para inferencia (AWS Bedrock inicialmente, migrable a otras opciones). Los costos relevantes son exclusivamente GPU de inferencia y herramientas de vibe engineering.

---

## **1. Introducción al paradigma agéntico en nuestras operaciones de red**

Nuestra red ha alcanzado un nivel de complejidad que supera la capacidad de gestión con los modelos operativos actuales. La combinación de redes 5G, expansión FTTH/GPON, transporte MPLS, servicios críticos (DNS, DHCP) y plataformas de seguridad genera volúmenes de telemetría y alarmas que nuestros equipos de NOC no pueden procesar de forma reactiva. Los tiempos de diagnóstico se miden en horas o días para incidentes cross-dominio, mientras los SLAs exigen resolución en minutos.

El punto de inflexión no es solo la presión operativa, sino la disponibilidad de una nueva generación de herramientas: los Sistemas Multiagente (MAS) basados en modelos de lenguaje, accesibles mediante APIs de inferencia como AWS Bedrock, que permiten construir agentes especializados capaces de razonar sobre nuestra red, invocar herramientas y coordinar diagnósticos cross-dominio. La diferencia con la automatización basada en reglas que ya tenemos es estructural: en lugar de flujos predefinidos "si X entonces Y", los agentes pueden descomponer problemas no vistos previamente, investigar múltiples hipótesis y correlacionar evidencia de dominios técnicos diferentes. Al ser un proyecto interno, tenemos la ventaja única de acceso directo a la telemetría real, al conocimiento tribal de nuestros ingenieros y a la infraestructura de servidores para desplegar sin dependencia de vendors.

Este documento desglosa la arquitectura técnica propuesta, el impacto operativo esperado, la viabilidad de implementación con nuestros recursos (servidores propios + GPU Bedrock + vibe engineering), y las consideraciones regulatorias. Se busca un equilibrio riguroso entre la ambición técnica y las limitaciones reales: los LLMs actuales tienen brechas de precisión significativas (11.34% en benchmarks complejos de RCA), nuestros sistemas OSS son legacy y fragmentados, y las exigencias regulatorias de 2026 requieren trazabilidad y supervisión humana desde el diseño.

## **2. Definición y delimitación conceptual: AIOps Agéntico Multiagente**

El sistema que proponemos construir se diferencia de nuestras herramientas actuales de monitoreo en un aspecto fundamental: los agentes no solo detectan anomalías mediante umbrales o correlación estadística, sino que poseen la capacidad de razonar sobre las dependencias causales de nuestra red, invocar herramientas programáticamente (APIs de nuestros sistemas, CLIs de equipos, capturas de paquetes), coordinar acciones con otros agentes y proponer remediaciones fundamentadas en evidencia. A diferencia de los scripts y runbooks que hoy usamos, un agente puede descomponer un problema nuevo en subtareas, investigar múltiples hipótesis simultáneamente y combinar evidencia de dominios que hoy nuestros equipos manejan en silos.

En la práctica, el sistema funcionaría así dentro de nuestra operación: (1) un agente de métricas detecta un aumento anómalo de latencia en el transporte; (2) el orquestador abre una "sala de diagnóstico" virtual y convoca a agentes especializados en nuestros dominios (fibra, MPLS, seguridad); (3) el agente de logs extrae patrones de error de nuestros sistemas, el agente de paquetes analiza tráfico PCAP de nuestras capturas, y el agente de topología reconstruye dependencias usando nuestro inventario; (4) los agentes "debaten" causas raíz ponderando evidencia; (5) se propone un plan de remediación que nuestro ingeniero aprueba o modifica. Lo que hace a este enfoque "agéntico" es la capacidad de razonamiento dinámico y coordinación emergente, y lo que lo hace viable para nosotros es que se construye sobre nuestros datos, nuestros servidores y el conocimiento de nuestro equipo.

La arquitectura de inferencia es deliberadamente desacoplada: los agentes corren en nuestros servidores propios (orquestación, memoria, herramientas, integraciones) y solo las llamadas al modelo de lenguaje van a GPU externa via AWS Bedrock. Esto significa que si Bedrock no resulta óptimo (por latencia, costo o disponibilidad de modelos), podemos migrar a Azure OpenAI, Google Cloud Vertex, o incluso GPUs dedicadas sin rediseñar el sistema.

## **3. Eje A: Velocidad de diagnóstico e impacto operativo**

El impacto más directo del sistema en nuestra operación es eliminar los cuellos de botella del ciclo de diagnóstico y remediación manual. Hoy, nuestros analistas de NOC dedican la mayor parte de su tiempo a saltar entre herramientas, correlacionar alarmas mentalmente y buscar a los expertos de dominio correctos. El análisis de paquetes PCAP, esencial para RCA detallado de protocolos (DHCP, DNS, SSL/TLS, MPLS), depende de 2-3 personas con experiencia específica.

Los resultados reportados por implementaciones tempranas de sistemas similares en la industria son significativos: reducción de MTTR de horas a menos de 60 segundos, eliminación del 98% de falsos positivos, ahorro de hasta 45 horas semanales por equipo de ingeniería. Sin embargo, debemos ser honestos con las expectativas: el benchmark OpenRCA muestra que los LLMs actuales solo resuelven correctamente el 11.34% de los casos de falla complejos con volúmenes masivos de telemetría. Esto no invalida el proyecto, pero sí define la estrategia: necesitamos una arquitectura híbrida donde los modelos de lenguaje se complementen con validación simbólica contra la telemetría real de nuestra red, y donde las metas iniciales sean realistas (>70% de RCA útil para el ingeniero) en lugar de prometer un 95% que no se puede sostener.

| Métrica de impacto | Situación actual en nuestra operación | Meta del proyecto |
| :---- | :---- | :---- |
| **Tiempo de diagnóstico (MTTR)** | Horas a días para incidentes cross-dominio | <5 minutos con asistencia agéntica |
| **Falsos positivos en alarmas** | >60% del tiempo del analista en alarmas irrelevantes | Reducción progresiva, meta >80% de filtrado útil |
| **Horas de ingeniería en correlación manual** | ~45 horas/semana por equipo | <10 horas/semana |
| **Dependencia de expertos escasos para PCAP** | 2-3 personas en toda la organización | Cualquier analista con asistencia del agente |
| **Conocimiento tribal documentado** | Fragmentado y en la cabeza de individuos | Capturado en los modelos y la memoria del sistema |

La viabilidad en este eje es alta porque no necesitamos que el sistema sea perfecto: necesitamos que sea útil. Si el agente acorta el diagnóstico de 4 horas a 20 minutos presentando la evidencia correcta al ingeniero (que sigue tomando la decisión), el impacto operativo ya es transformador.

## **4. Eje B: Consistencia, captura de conocimiento y reducción del ruido**

Más allá de la velocidad, nuestro problema cualitativo es la inconsistencia y la pérdida de conocimiento. Cada ingeniero aplica su propio "árbol mental" de diagnóstico, la evidencia se recolecta de forma fragmentada entre herramientas, y cuando un experto se va, su método de trabajo desaparece con él. El "ruido" operativo consume entre el 60-80% del tiempo de nuestros analistas.

El sistema multiagente aborda esto mediante la estandarización del razonamiento. Las "salas de diagnóstico" virtuales implementan un flujo riguroso y repetible: percepción, investigación de evidencia, correlación topológica, síntesis de RCA y propuesta de acción. Cada diagnóstico es trazable y auditable. Pero lo más valioso para nosotros como equipo interno es que el sistema se convierte en un repositorio vivo del conocimiento de nuestra red: cada incidente resuelto, cada correlación descubierta, cada particularidad de nuestra topología queda capturada y accesible para todo el equipo.

La crítica técnica nos advierte sobre el riesgo de alucinaciones: un agente podría inventar métricas o proponer soluciones basadas en información que parece correcta pero no lo es. Al ser un equipo interno, tenemos una ventaja para mitigar esto: podemos validar las salidas del sistema contra la realidad de nuestra propia red, y nuestros ingenieros conocen suficientemente bien la infraestructura para detectar cuando una respuesta del agente "no tiene sentido". El mecanismo de defensa es doble: anti-alucinación técnica (RAG con nuestra documentación real, validación contra ground truth) y anti-alucinación humana (nuestros ingenieros como verificadores).

## **5. Eje C: Adopción por el equipo y experiencia del ingeniero**

La tensión fundamental en nuestro proyecto no es técnica sino humana: nuestros ingenieros de red deben confiar en el sistema lo suficiente para usarlo, pero no tanto como para dejar de verificar. La historia de la industria muestra que la sobre-confianza en sistemas autónomos lleva a "fallas catastróficas por desatención", mientras que la desconfianza excesiva genera evasión del sistema y lo hace irrelevante.

El diseño que necesitamos se basa en tres principios internos: transparencia radical (el ingeniero ve qué evidencia usó cada agente y cómo llegó a su conclusión, usando datos de NUESTRA red que el ingeniero puede verificar), autonomía graduable (nuestro equipo de operaciones ajusta el nivel de autonomía por dominio y tipo de acción), y fail-safe verificable (ante cualquier anomalía, la red revierte a un estado conocido). La ventaja de ser un equipo interno es que podemos iterar rápido: si los ingenieros de NOC nos dicen "esto no sirve para nada en incidentes de GPON", podemos ajustar en días, no en meses de ciclo comercial con un vendor.

El caso del apagón de AT&T (2024) es nuestra advertencia interna: un mecanismo automático de "protección" causó más daño que la falla original. Nuestro sistema debe ser percibido como una herramienta que amplifica la capacidad del ingeniero, no como una caja negra que podría tumbar la red.

## **6. Arquitectura técnica y paradigma HITL**

La arquitectura se divide en dos capas claramente separadas por razones de costo y control:

**Capa local (nuestros servidores):** Orquestación multiagente, memoria y estado de conversación, integraciones con nuestros sistemas (APIs de EMS, GIS, CRM, ticketing, plataformas de monitoreo), herramientas de diagnóstico (parsers de logs, análisis PCAP, consultas a inventario), motor de políticas y gobernanza HITL, bases de conocimiento RAG con nuestra documentación técnica.

**Capa externa (GPU de inferencia):** Únicamente las llamadas al modelo de lenguaje para razonamiento. Inicialmente AWS Bedrock (acceso a Claude, Llama y otros modelos). La arquitectura es agnóstica al proveedor de GPU: si necesitamos migrar a Azure OpenAI, Google Cloud Vertex, o GPUs dedicadas (por costo, latencia o modelos disponibles), solo cambia el endpoint de inferencia, no el resto del sistema.

### **6.1. Orquestación y escuadrones especializados en nuestra red**

El agente orquestador descompone incidentes y asigna tareas a escuadrones especializados en los dominios de nuestra red: Acceso/FTTH-GPON (degradación óptica, saturación de puertos OLT, incidencias de CPE), Core/MPLS (túneles L3, ingeniería de tráfico, enrutamiento), Móvil/5G RAN (parámetros de celda, cobertura, handover), Servicios Críticos (DNS/DHCP, conflictos IP, saturación de scopes), y Seguridad (detección de amenazas, auditoría de configuraciones). La comunicación inter-agéntica puede usar MCP (Model Context Protocol) para descubrimiento dinámico de herramientas, o un bus de mensajes más simple si la complejidad de MCP no se justifica en la fase inicial.

### **6.2. Procesamiento de telemetría de nuestra red**

Los agentes de ingesta se conectan a las fuentes de datos que ya tenemos: APIs REST de nuestras plataformas (Cisco Network Registrar para DNS/DHCP, plataformas de monitoreo por dominio), logs de equipos de red procesados con NLP, capturas PCAP con análisis contra especificaciones RFC, y flujos NetFlow/IPFIX. El desafío de latencia es real: las llamadas a Bedrock para inferencia añaden latencia que puede ser inaceptable para diagnóstico en tiempo real. La mitigación es caché semántica para consultas recurrentes (<50ms) y modelos ligeros (SLM) para monitoreo continuo, reservando los modelos pesados via Bedrock para razonamiento profundo en incidentes críticos.

### **6.3. HITL y gobernanza adaptada a nuestra organización**

Las acciones se clasifican por riesgo: lectura y correlación (autónomo), reconfiguración de parámetros (notificación + reversa posible), cambios en core y seguridad (aprobación humana obligatoria). Las "salas de diagnóstico" exigen que los agentes presenten evidencia antes de proponer acciones. El sandboxing en entornos de prueba o gemelos digitales es obligatorio antes de tocar producción. Nuestro equipo de seguridad y cumplimiento define las políticas del motor de gobernanza.

## **7. Consideraciones regulatorias (2025-2026)**

Aunque somos un proyecto interno, cualquier sistema autónomo que interactúe con infraestructura crítica de telecomunicaciones está sujeto a escrutinio regulatorio creciente. Es más barato diseñar el cumplimiento desde el inicio que retrofitearlo.

### **7.1. EU AI Act**

Si nuestro operador opera en jurisdicciones europeas o sirve a clientes europeos, el AI Act (obligaciones desde 2026) clasifica los sistemas de IA en infraestructura crítica como "alto riesgo". Obligaciones: transparencia, supervisión humana, trazabilidad de decisiones, auditorías independientes. La Directiva de Responsabilidad de Productos establece responsabilidad objetiva del operador.

### **7.2. Normativa de EE.UU.**

Regulación fragmentada por estados. Precedente Moffatt v. Air Canada (2024): responsabilidad de la empresa por información errónea de sistemas autónomos. Ley AB 316 de California (2026): prohíbe usar autonomía como defensa legal.

### **7.3. Normativa local (LATAM)**

Marcos en desarrollo con principios de auditabilidad, transparencia y no discriminación. Al diseñar para los estándares más estrictos (EU AI Act), automáticamente cumplimos con los marcos menos maduros.

### **7.4. Implicación práctica para nuestro proyecto**

La trazabilidad y el HITL no son "features opcionales": son requisitos legales. Cada diagnóstico y cada acción del sistema deben generar logs de auditoría que nuestro equipo de cumplimiento pueda presentar ante reguladores. La ventaja de construir internamente es que podemos diseñar esto desde la primera línea de código en lugar de depender de que un vendor externo lo implemente correctamente.

## **8. Análisis de viabilidad con nuestros recursos**

| Dimensión de funcionalidad | Viabilidad con nuestros recursos | Riesgo principal |
| :---- | :---- | :---- |
| **Detección y correlación de anomalías** | Alta — conectores a nuestros sistemas + modelos via Bedrock | Calidad de datos en sistemas legacy |
| **RCA asistido con razonamiento multiagente** | Media — LLMs tienen brecha de precisión; nuestro equipo funcional compensa con conocimiento de dominio | Alucinaciones en diagnósticos complejos |
| **Salas de diagnóstico virtuales** | Alta — orquestación en nuestros servidores; inferencia en Bedrock | Latencia de Bedrock para interacción en tiempo real |
| **Autocuración en acceso (FTTH/GPON)** | Media-Alta — acciones bien definidas con bajo riesgo | Requiere sandboxing riguroso |
| **Autocuración en core/MPLS** | Media — mayor riesgo de impacto cascada | Solo con madurez demostrada en acceso primero |
| **Análisis PCAP automatizado** | Alta — comparación contra RFC es determinista | Volumen de capturas en tiempo real |
| **Integración con OSS legacy** | Media — nuestros sistemas son fragmentados y propietarios | Conectores frágiles; requiere capa de abstracción |
| **Cumplimiento regulatorio** | Alta — lo diseñamos nosotros desde el inicio | Mantener actualizado con evolución normativa |

**Análisis de costos reales del proyecto:**

| Componente | Costo estimado | Notas |
| :---- | :---- | :---- |
| **Servidores (orquestación, memoria, integraciones)** | $0 incremental | Usamos infraestructura propia existente |
| **GPU de inferencia (AWS Bedrock)** | Variable por consumo | ~$0.003-$0.015 por 1K tokens según modelo; escalable |
| **Herramientas de vibe engineering** | ~$50-$200/mes por desarrollador | Cursor, Claude Code, suscripciones de modelos, frameworks |
| **Talento (desarrolladores + funcionales)** | $0 incremental | Equipo interno existente reasignado al proyecto |
| **Migración futura de GPU (si necesario)** | $0 diseño / variable consumo | Arquitectura agnóstica permite cambiar solo endpoint |

## **9. Requisitos mínimos para una implementación defendible**

Para que nuestro sistema pueda desplegarse en producción sin riesgo operativo ni contingencias regulatorias, debe integrar:

**I. HITL explícito con autonomía graduable**
Nuestros ingenieros aprueban acciones de riesgo. El sistema recomienda, no decide. La autonomía es ajustable por dominio y por nuestro equipo de operaciones, no hardcodeada.

**II. Trazabilidad y explicabilidad completa**
Cada diagnóstico vinculado a evidencia de nuestra telemetría real. Logs de auditoría para cumplimiento y para que nuestro equipo de seguridad pueda revisar cada acción del sistema. Alineación con EU AI Act desde el diseño.

**III. Anti-alucinación con validación contra nuestra red real**
RAG con nuestra documentación técnica, manuales de equipos y configuraciones. Validación de salidas contra ground truth de nuestra telemetría. Regla "si no sé, escalo al ingeniero". Nuestro equipo funcional revisa y corrige las bases de conocimiento continuamente.

**IV. Seguridad en la comunicación con GPU externa**
Cifrado de extremo a extremo en las llamadas a Bedrock. Nunca enviar datos sensibles de suscriptores al modelo externo (solo telemetría técnica anonimizada). Validación de que los datos que salen a la GPU cumplen con nuestras políticas de privacidad.

**V. Arquitectura de GPU desacoplada y migrable**
El endpoint de inferencia es un componente intercambiable. Si Bedrock resulta caro, lento o limitado en modelos, podemos migrar a Azure OpenAI, Google Cloud Vertex, GPUs dedicadas en colocation, o incluso modelos open-source (Llama, Mistral) en GPU propia cuando sea económicamente viable. Esto se decide en el camino, no al inicio.

El éxito de este proyecto no se mide por alcanzar "Nivel 5 de autonomía" sino por resolver los problemas concretos de nuestros equipos de NOC e ingeniería con las herramientas y el talento que ya tenemos, complementados con GPU de inferencia y las mejores prácticas de vibe engineering. La red autónoma definitiva para nosotros será aquella donde nuestros ingenieros trabajen mejor, no aquella donde sean reemplazados.

---
