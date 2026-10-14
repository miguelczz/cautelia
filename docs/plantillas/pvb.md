# Product Vision Board — NetHeal MAS (Proyecto Interno)

**Versión:** 1.1
**Fecha:** 2026-03-09
**Basado en:** Idea.md, critica.md, overview.md, mercado.md, icp.md
**Naturaleza:** Proyecto interno del operador — desarrollado por talento local (desarrolladores + funcionales)

---

## 1. Visión

> **Construir un sistema interno de AIOps Agéntico multiagente que reduzca el tiempo de diagnóstico de horas a minutos en nuestra red heterogénea (5G, FTTH, MPLS), capture y escale el conocimiento de nuestros mejores ingenieros, y habilite la autocuración verificable con supervisión humana, usando servidores propios, GPU de inferencia externa (AWS Bedrock) y herramientas de vibe engineering, sin dependencia de vendors externos ni costos de licenciamiento.**

---

## 2. Usuarios Internos (Target Group)

### Usuarios Primarios: Equipos de NOC

| Dimensión             | Detalle                                                                  |
| --------------------- | ------------------------------------------------------------------------ |
| **Rol**               | Analistas y operadores de NOC 24/7                                       |
| **Tamaño del equipo** | [Según nuestra organización]                                             |
| **Dolor principal**   | Sobrecarga de alarmas, correlación manual entre silos, MTTR de horas     |
| **Qué necesitan**     | Diagnóstico asistido que filtre ruido y presente evidencia cross-dominio |
| **Poder de decisión** | No compran pero su adopción o rechazo determina el éxito                 |

### Usuarios Secundarios: Ingenieros de Red especializados

| Dimensión             | Detalle                                                                           |
| --------------------- | --------------------------------------------------------------------------------- |
| **Rol**               | Expertos en FTTH/GPON, Core/MPLS, 5G RAN, DNS/DHCP, Seguridad                     |
| **Dolor principal**   | Tiempo excesivo en investigación forense manual; conocimiento tribal no escalable |
| **Qué necesitan**     | Herramienta que amplifique su expertise y lo haga accesible al equipo             |
| **Poder de decisión** | Pueden vetar la adopción si no confían en el sistema                              |

### Stakeholders: Gerencia de Operaciones / Dirección Técnica

| Dimensión             | Detalle                                                                      |
| --------------------- | ---------------------------------------------------------------------------- |
| **Rol**               | Toman decisiones sobre recursos, prioridades y continuidad del proyecto      |
| **Dolor principal**   | Costos operativos, incumplimiento de SLAs, rotación de talento especializado |
| **Qué necesitan**     | Métricas claras de impacto operativo y ROI del proyecto                      |
| **Poder de decisión** | Aprueban recursos y definen alcance                                          |

### Gate Obligatorio: Equipo de Seguridad y Cumplimiento

**Responsables de seguridad y regulación interna** — No usan el sistema diariamente pero su aprobación es prerequisito para producción. Necesitan: trazabilidad, auditabilidad, cumplimiento regulatorio, y garantías de que datos sensibles no se envían a GPUs externas sin anonimización.

---

## 3. Necesidades (Needs / Pains)

### Equipos de NOC

| Pain                                                             | Evidencia interna                                                                      |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| **Correlación manual de alarmas entre sistemas aislados**        | Nuestros sistemas (EMS, GIS, CRM, ticketing) no se hablan entre sí                     |
| **MTTR inaceptable para incidentes cross-dominio**               | Horas a días cuando el problema cruza dominios (fibra + core + servicios)              |
| **Fatiga de alertas por ruido excesivo**                         | >60% del tiempo en alarmas irrelevantes o duplicadas                                   |
| **Dependencia de 2-3 expertos para PCAP y diagnóstico profundo** | Cuello de botella en incidentes complejos; si el experto no está disponible, se espera |

### Ingenieros especializados

| Pain                                        | Evidencia interna                                                          |
| ------------------------------------------- | -------------------------------------------------------------------------- |
| **Conocimiento tribal no documentado**      | Se pierde con rotación; nuevos ingenieros tardan meses en ser productivos  |
| **Investigación forense manual repetitiva** | Las mismas correlaciones se hacen una y otra vez sin aprendizaje sistémico |

### Gerencia

| Pain                                                     | Evidencia                                                       |
| -------------------------------------------------------- | --------------------------------------------------------------- |
| **SLAs en riesgo por tiempos de resolución**             | Incidentes cross-dominio exceden ventanas de SLA                |
| **Presión regulatoria sin herramientas de cumplimiento** | EU AI Act 2026 exigirá trazabilidad si usamos IA en operaciones |

### JTBD (Jobs To Be Done)

> **Cuando** nuestro NOC enfrenta un incidente cross-dominio con cientos de alarmas simultáneas, **quiero** un sistema interno que correlacione automáticamente la telemetría de todos nuestros dominios y presente a nuestros ingenieros una hipótesis de causa raíz fundamentada con evidencia de nuestra propia red, **para** reducir el tiempo de resolución de horas a minutos y liberar a nuestros expertos de la correlación manual repetitiva.

---

## 4. Producto (Product / Solution)

### One-Liner

**NetHeal MAS** es un sistema interno de AIOps Agéntico multiagente que diagnostica fallas en nuestra red heterogénea (5G, FTTH, MPLS) mediante escuadrones de agentes especializados en nuestros dominios, corriendo sobre nuestros servidores con inferencia via AWS Bedrock, con autocuración verificable y supervisión humana, construido por nuestro propio equipo de desarrolladores y funcionales.

### Capacidades clave del MVP

| #   | Capacidad                                         | Descripción                                                                                                                                             |
| --- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Salas de diagnóstico virtuales**                | Convocatoria automática de agentes especializados de nuestra red ante anomalía; debate inter-agéntico con evidencia de nuestra telemetría; RCA trazable |
| 2   | **Escuadrones por dominio de nuestra red**        | Agentes entrenados con conocimiento específico de nuestro acceso FTTH/GPON, core MPLS, 5G RAN, DNS/DHCP y seguridad                                     |
| 3   | **Ingesta de telemetría desde nuestros sistemas** | Conectores a nuestras plataformas existentes (EMS, GIS, monitoreo, ticketing) + análisis de logs y PCAP contra RFC                                      |
| 4   | **Captura de conocimiento tribal**                | El sistema aprende de las resoluciones de nuestros ingenieros y hace accesible ese conocimiento a todo el equipo                                        |
| 5   | **Autocuración con sandboxing**                   | Remediaciones validadas en entorno de prueba antes de producción; aprobación humana para acciones de riesgo                                             |
| 6   | **Anti-alucinación con ground truth**             | RAG con nuestra documentación técnica real; validación contra telemetría de nuestra red; "si no sé, escalo"                                             |
| 7   | **Arquitectura de GPU desacoplada**               | Inferencia via AWS Bedrock inicialmente; migrable a cualquier proveedor sin rediseño del sistema                                                        |

### Principios no negociables

1. **Nuestros ingenieros deciden** — El sistema recomienda, nunca ejecuta acciones críticas sin aprobación humana de nuestro equipo
2. **Construido con nuestros datos** — Los agentes razonan sobre nuestra red real, nuestra topología y nuestro inventario, no sobre modelos genéricos
3. **Trazabilidad para auditoría** — Cada diagnóstico y acción es explicable, vinculable a evidencia y presentable ante reguladores y auditoría interna
4. **GPU como servicio intercambiable** — Bedrock hoy, cualquier proveedor mañana; nunca dependencia de un solo vendor de inferencia
5. **Seguridad de datos hacia GPU** — Nunca enviar datos de suscriptores al modelo externo; solo telemetría técnica anonimizada

---

## 5. Valor de Negocio (Business Value)

### Modelo de costos (NO hay modelo de negocio — es proyecto interno)

**Costos del proyecto:**

| Componente                           | Costo                 | Notas                                           |
| ------------------------------------ | --------------------- | ----------------------------------------------- |
| **Servidores**                       | $0 incremental        | Infraestructura propia existente                |
| **GPU de inferencia (AWS Bedrock)**  | Variable por consumo  | ~$0.003-$0.015/1K tokens; escala con uso        |
| **Herramientas de vibe engineering** | ~$50-$200/mes por dev | Cursor, Claude Code, frameworks de agentes      |
| **Talento**                          | $0 incremental        | Nuestro equipo de desarrolladores y funcionales |
| **Total mensual estimado MVP**       | ~$500-$2,000/mes      | Principalmente GPU + herramientas               |

### North Star Metric

**Incidentes cross-dominio resueltos en <5 minutos con asistencia del sistema (vs. horas en baseline)**
_(Mide impacto directo en la operación; si sube, el sistema está funcionando para nuestros equipos)_

### KPIs clave (metas MVP a 6 meses)

| Categoría     | KPI                                                      | Meta                               |
| ------------- | -------------------------------------------------------- | ---------------------------------- |
| **Adopción**  | Ingenieros de NOC usando el sistema activamente          | >50% del equipo de turno           |
| **Adopción**  | Dominios de red conectados al sistema                    | ≥2 (FTTH + MPLS)                   |
| **Impacto**   | MTTR medio en incidentes cubiertos                       | <5 minutos (vs. horas en baseline) |
| **Calidad**   | % de RCA que el ingeniero califica como "útil"           | >70%                               |
| **Confianza** | % de ingenieros que recomiendan el sistema a sus colegas | >75%                               |

### Propuesta de impacto operativo (Antes/Después)

| Métrica                                              | Antes (situación actual)                     | Después (con el sistema)            |
| ---------------------------------------------------- | -------------------------------------------- | ----------------------------------- |
| **Tiempo de diagnóstico cross-dominio**              | 2-8 horas                                    | <5 minutos                          |
| **Horas de ingeniería en correlación manual/semana** | ~45 horas/equipo                             | <10 horas/equipo                    |
| **Accesibilidad del conocimiento de expertos**       | Solo cuando el experto está disponible       | Disponible 24/7 via los agentes     |
| **Tiempo de onboarding de nuevo ingeniero**          | 3-6 meses para ser productivo en diagnóstico | Semanas con asistencia del sistema  |
| **Costo adicional del proyecto**                     | N/A                                          | ~$500-$2,000/mes (GPU + vibe tools) |

---

## 6. Diferenciación (¿Por qué construir internamente?)

### No es diferenciación competitiva — es justificación de build vs. buy

> **Ningún producto externo combina: conocimiento profundo de NUESTRA topología específica + acceso directo a NUESTRA telemetría + personalización por NUESTRO equipo funcional + costos de solo GPU+herramientas (vs. licenciamientos de $100K-$500K/año de vendors de AIOps). Construir internamente es más barato, más personalizado y genera propiedad intelectual propia.**

### Comparación Build vs. Buy

| Opción                              | Costo anual estimado       | Personalización                         | Dependencia                           |
| ----------------------------------- | -------------------------- | --------------------------------------- | ------------------------------------- |
| **Nokia AVA**                       | $200K-$500K licenciamiento | Limitada a configuración                | Vendor lock-in completo               |
| **Ericsson AI**                     | $150K-$400K                | Mobile-first; no cubre toda nuestra red | Ecosistema Ericsson                   |
| **AIOps genérico (Datadog/Splunk)** | $100K-$300K                | Requiere personalización extensiva      | Licenciamiento recurrente             |
| **Nuestro proyecto interno**        | ~$6K-$24K/año (GPU+tools)  | Total — construido por y para nosotros  | Solo endpoint de GPU (intercambiable) |

### Ventajas únicas de build interno

```
Eje 1: Genérico ← → Específico para nuestra red
Eje 2: Dependiente de vendor ← → Autónomo (solo GPU como servicio)

Nuestro proyecto ocupa: Máxima especificidad + Máxima autonomía
```

---

## 7. Contexto Estratégico

### ¿Por qué ahora?

| Tendencia                                                          | Implicación para nuestro proyecto                                                                                      |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| **AWS Bedrock ofrece GPU de inferencia por consumo**               | Podemos empezar sin inversión de capital en hardware AI; pagamos lo que usamos                                         |
| **Herramientas de vibe engineering maduras**                       | Cursor, Claude Code, Frameworks de agentes permiten a nuestro equipo construir agentes sofisticados rápido             |
| **EU AI Act entra en vigor (2026)**                                | Si vamos a usar IA en operaciones, necesitamos diseñar cumplimiento ahora                                              |
| **MCP se consolida como estándar**                                 | Protocolo abierto para conectar agentes con herramientas sin integraciones rígidas                                     |
| **Nuestra red crece en complejidad más rápido que nuestro equipo** | El gap operativo se amplía; la alternativa es contratar más gente (caro) o amplificar al equipo con IA (este proyecto) |

### Decisiones estratégicas fundamentales

| Decisión                   | Resolución                                                                 |
| -------------------------- | -------------------------------------------------------------------------- |
| Build vs. Buy              | Build interno — costos 10-20x menores, personalización total, propiedad IP |
| GPU de inferencia          | AWS Bedrock inicialmente; arquitectura migrable a cualquier proveedor      |
| Stack de desarrollo        | Vibe engineering: Cursor/Claude Code + Python + Frameworks de Agentes      |
| Dominio de inicio          | Acceso FTTH/GPON (bajo riesgo, alta estandarización, impacto visible)      |
| Nivel de autonomía inicial | Asistencia al ingeniero (Nivel 3); autocuración solo con aprobación humana |
| Datos hacia GPU externa    | Solo telemetría técnica anonimizada; nunca datos de suscriptores           |

### Top 3 riesgos

| Riesgo                                                              | Mitigación                                                                                                                                                                             |
| ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Precisión del RCA insuficiente (11% en benchmarks complejos)**    | Arquitectura híbrida: SLMs para monitoreo + modelos pesados via Bedrock para razonamiento profundo + validación contra ground truth de nuestra red. Metas realistas (>70% útil)        |
| **Equipo de NOC no adopta el sistema**                              | Involucrar ingenieros de NOC como co-diseñadores desde día 1; transparencia en el razonamiento; autonomía graduable que ellos controlan; iterar según su feedback                      |
| **Latencia de Bedrock inaceptable para diagnóstico en tiempo real** | Caché semántica para consultas recurrentes; modelos ligeros locales para monitoreo continuo; Bedrock solo para razonamiento profundo. Si persiste, migrar a GPU más cercana o dedicada |

---

## 8. Roadmap de Alto Nivel (90 días)

| Fase           | Entregable principal                                                                                                                                        | Hito                                                                                              |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| **Días 1–30**  | Prototipo con 1 escuadrón (FTTH) conectado a telemetría real de nuestra red via Bedrock; sala de diagnóstico funcional; stack de vibe engineering operativo | Demo interna con un RCA real de nuestra red en <5 minutos                                         |
| **Días 31–60** | Segundo escuadrón (MPLS); integración con 2+ sistemas internos (monitoreo + ticketing); gobernanza HITL validada por equipo de seguridad                    | Piloto con equipo de NOC en turno real usando el sistema en paralelo                              |
| **Días 61–90** | Métricas de MTTR y utilidad validadas por ingenieros; captura de conocimiento tribal de 2-3 expertos; evaluación de costos reales de Bedrock                | Decisión Go/No-Go para expandir a más dominios basada en feedback real del equipo y costos de GPU |

---
