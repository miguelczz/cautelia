# Investigación 3: seguridad de IA, guardas, jueces, evals, observabilidad, pruebas y cadena de suministro

Fecha de corte: 2026-09-17. Alcance: preguntas 1 a 9 del encargo. Postura: desafiar el
diseño aprobado (ADR-002, ADR-011 a ADR-015 y PRD Segmentos 11 y 12), no confirmarlo.

Convenciones del informe:

- Cada afirmación lleva fuente con URL y fecha en la lista final (`[Sn]`). Las versiones de
  paquetes salen de las API públicas de PyPI, npm y GitHub consultadas el 2026-09-17.
- **No verificado** marca lo que no pude confirmar con fuente primaria. El presupuesto de
  búsquedas web de la sesión se agotó a mitad del trabajo; lo restante se verificó con
  lecturas directas de documentación oficial y de las API de los registros.
- **Riesgo curricular** marca lo que se añadiría para lucir, sin necesidad real, y que un
  Staff Engineer castigaría.
- Recomendaciones posibles: `adoptar en el runtime`, `adoptar solo en desarrollo/pruebas`,
  `rechazar y documentarlo en un ADR`, `diferir (trabajo futuro)`.

---

## Resumen ejecutivo

1. **El marco de referencia cambió en agosto de 2026.** Existe la edición 2026 del OWASP
   Top 10 for LLM Applications (publicada el 2026-08-04) y reemplaza a la de 2025:
   Excessive Agency sube al puesto 3 y System Prompt Leakage pasa a llamarse **Hidden
   Context Exposure** (LLM08:2026). El README debe mapear contra la edición 2026, más las
   pocas entradas aplicables del OWASP Top 10 for Agentic Applications 2026 (ASI).
2. **El diseño ya aplica los patrones buenos** (el LLM no enruta, las reglas deciden, el
   verificador exacto), pero tiene **huecos concretos**: la guarda de salida frente al
   streaming hacia TTS y SSE, los campos extraídos por el LLM que alimentan las reglas, la
   bandeja del ajustador como vector de manipulación de un humano (ASI09), el renderizado
   de la salida en el navegador (LLM10:2026) y un RT-5 formulado como algo imposible de
   ganar.
3. **Sin guardas de ML en el turno.** Los clasificadores de inyección caen por encima del
   90 % de éxito frente a ataques adaptativos (Prompt Guard, Protect AI, Model Armor). LLM
   Guard quedó archivado el 2026-07-09 y no instala en Python 3.13. Guardrails AI fue
   comprada por Harvey el 2026-09-09. El conjunto mínimo creíble son controles
   deterministas bilingües más patrones de diseño, y un ADR que explique por qué no hay
   guardas de ML.
4. **El umbral del juez está mal planteado.** Un "85 % de acuerdo" sobre 20 transcripciones
   por idioma tiene un intervalo del 95 % de [64 %, 95 %], y un juez puede dar 90 % de
   acuerdo detectando solo la mitad de los fallos. Hay que cambiarlo por TPR y TNR por
   criterio y por idioma, sobre una partición de prueba separada, con intervalo y con una
   corrección de la tasa reportada.
5. **Hay que activar ya la salida que ADR-014 dejó prevista.** DeepEval sacó 46 versiones
   en 2026, pasó a la 4.0 en mayo con otro enfoque ("harness for vibe coding agents") y
   arrastra 29 dependencias base, entre ellas `posthog` y `pytest-rerunfailures`, que
   contradice la política de casos inestables. Un juez binario propio detrás de la misma
   interfaz da una señal más fuerte y menos superficie. Ragas está parado desde febrero de
   2026.
6. **Promptfoo es de OpenAI** (anuncio del 2026-03-09) y sigue con licencia MIT. Sirve
   para red-team exploratorio por hito, con una sola herramienta. PyRIT, garak y DeepTeam
   a la vez serían riesgo curricular.
7. **Observabilidad.** Las convenciones GenAI de OpenTelemetry siguen en estado
   *Development* y se movieron a un repositorio propio en mayo de 2026. Langfuse (comprada
   por ClickHouse el 2026-01-16) exige Postgres, ClickHouse, Redis, S3, web y worker, con
   un mínimo de 4 núcleos y 16 GiB en docker compose: no corre en CI privado (2 vCPU y
   8 GB). Los enlaces "a su traza en Langfuse" del reporte de CI no resolverán.
8. **Cadena de suministro.** En marzo de 2026 comprometieron `trivy-action` reescribiendo
   76 de 77 etiquetas (CVE-2026-33634) y publicaron `litellm` malicioso en PyPI. Hay que
   fijar Actions por SHA, pasar zizmor y aplicar enfriamiento de versiones (cooldown de
   Dependabot, `exclude-newer` de uv, `minimumReleaseAge` de pnpm). La protección de
   inserción de GitHub **no está disponible** en un repositorio privado de cuenta personal:
   hasta la semana 12, gitleaks.

---

## 1. Marcos de seguridad para mapear controles en el README

### Hallazgos

| Marco | Estado al 2026-09-17 | Evidencia |
| --- | --- | --- |
| OWASP Top 10 for LLM Applications **2026** | Publicado el 2026-08-04 (v1.0), CC BY-SA 4.0. Lista: LLM01 Prompt Injection, LLM02 Sensitive Information Disclosure, LLM03 Excessive Agency, LLM04 Supply Chain, LLM05 Data and Model Poisoning, LLM06 Unbounded Consumption, LLM07 Misinformation, LLM08 Hidden Context Exposure, LLM09 Vector and Embedding Weaknesses, LLM10 Improper Output Handling. Por primera vez pondera datos de incidentes. | [S1] repo oficial, [S2] página OWASP, [S3], [S4]. Varios medios secundarios publicaron órdenes distintos en los puestos 4 a 8; manda el repositorio oficial. |
| OWASP Top 10 for LLM Applications 2025 | Sustituida por la de 2026. Citarla hoy delata desactualización. | [S1] |
| OWASP Top 10 for Agentic Applications 2026 | Publicado el 2025-12-09, v1.0. ASI01 Agent Goal Hijack, ASI02 Tool Misuse & Exploitation, ASI03 Agent Identity & Privilege Abuse, ASI04 Agentic Supply Chain Compromise, ASI05 Unexpected Code Execution, ASI06 Memory & Context Poisoning, ASI07 Insecure Inter-Agent Communication, ASI08 Cascading Agent Failures, ASI09 Human-Agent Trust Exploitation, ASI10 Rogue Agents. | [S5], [S6] |
| OWASP Agent Control Standard | v0.1, 2026-09-01/02: puntos de aplicación en runtime, observabilidad con OpenTelemetry y OCSF, "Agent Bill of Materials". Está muy verde para citarlo. | [S4] (nota de investigación de CSA; no leí el documento primario) |
| OWASP AI Testing Guide | v1, 2025-11-26. Cuatro pilares (aplicación, modelo, infraestructura, datos) con identificadores `AITG-APP-xx`. | [S7] |
| NIST AI 600-1 (perfil de IA generativa) | Sigue siendo la versión del 2024-07-26; no hay revisión en 2026 (en abril de 2026 hubo una nota conceptual de otro perfil). Es un perfil de **gobernanza** con 12 categorías de riesgo, no un catálogo de controles técnicos. | [S8], [S9] |
| MITRE ATLAS | Versionado mensual desde mayo de 2026. v2026.09 (2026-09-15): 16 tácticas, 120 técnicas, 88 subtécnicas, 73 casos. Muy orientado a agentes. | [S10] |

### Qué espera un evaluador senior

Un Staff Engineer o un Head of AI reconoce de inmediato el **OWASP Top 10 for LLM
Applications** y espera **la edición vigente**. Lo que castiga no es la ausencia de un
marco, sino la tabla que nombra un marco sin un control y una prueba detrás (el dolor
"compliance named without controls" del encargo). NIST AI 600-1 en un README de portfolio
casi siempre cae en ese patrón: es gobernanza organizacional y un proyecto de una persona no
tiene cómo sostener sus acciones GOVERN y MAP.

### Recomendación

- **Adoptar** (README y `docs/`): una tabla "inspirado en" contra **LLM Top 10 2026**, una
  fila por riesgo, con tres columnas obligatorias: control en código, prueba o caso que lo
  verifica (identificador de DS-6, DS-8 o prueba unitaria) y estado. Las filas que no
  apliquen se marcan `N/A` con razón (por ejemplo, LLM05 poisoning: no hay
  entrenamiento ni ajuste fino).
- **Adoptar**: una segunda tabla corta con **ASI** solo para lo aplicable: ASI01 (secuestro
  del objetivo, RT-1 y RT-2), ASI06 (envenenamiento de contexto en los puntos de control y
  la retoma, ADR-005), ASI08 (fallos en cascada, degradación del Segmento 12.3) y ASI09
  (confianza del ajustador en la bandeja; ver el hueco G3). ASI02, ASI05 y ASI07 van `N/A`
  con su razón: no hay herramientas con efectos arbitrarios, no se ejecuta código generado
  y no hay comunicación entre agentes. Esa franqueza puntúa.
- **Diferir**: identificadores de técnica de MITRE ATLAS como metadato opcional de cada caso
  de DS-6 (una columna `atlas:`). Es barato, pero la numeración cambia cada mes desde mayo
  de 2026, así que se anota con la versión.
- **Diferir**: identificadores `AITG-APP-xx` del AI Testing Guide en las instrucciones de
  prueba de seguridad de `build-and-test`. Aportan si se usan como nombre de prueba, no como
  tabla aparte.
- **Rechazar y documentarlo en el ADR** (una línea): mapear NIST AI 600-1 en el README. Es
  gobernanza sin controles técnicos verificables en este alcance; nombrarlo sería
  exactamente el antipatrón que penalizan los evaluadores.
- **Corrección de redacción**: toda mención a "OWASP 2025" en artefactos futuros pasa a
  "OWASP Top 10 for LLM Applications 2026". RT-5 ("extracción del prompt") se mapea a
  LLM08:2026 *Hidden Context Exposure*, cuyo planteamiento cambia la conducta esperada
  (ver el hueco G7).

---

## 2. Defensas contra inyección de instrucciones: patrones y huecos del diseño

### Hallazgos (literatura)

- **Design Patterns for Securing LLM Agents against Prompt Injections** (arXiv 2506.08837,
  v2 del 2025-06-11; Beurer-Kellner, Tramèr y otros 12 autores). Seis
  patrones: Action-Selector, Plan-Then-Execute, LLM Map-Reduce, Dual LLM, Code-Then-Execute
  y Context-Minimization. Casos de estudio que aplican aquí: *Customer Service Chatbot*
  (recomienda action-selector o context-minimization) y *Medical Diagnosis via LLM
  Intermediary*, donde un resumen hecho por el LLM y leído por un humano es el vector de
  inyección [S11], [S12].
- **CaMeL** (arXiv 2503.18813, 2025-03, v2 del 2025-06-24; Google, Google DeepMind y ETH):
  extrae el flujo de control de la petición confiable, de modo que los datos no confiables
  nunca alteran el programa, y añade capacidades contra la exfiltración. Resuelve el 77 %
  de las tareas de AgentDojo con seguridad demostrable, frente al 84 % sin defensa [S13].
- **Spotlighting** (arXiv 2403.14720, 2024-03-20; Microsoft): delimitación, *datamarking* y
  codificación. En modelos GPT bajó la tasa de éxito de ataque de más del 50 % a menos del
  2 % [S14]. Es probabilística y no es una frontera.
- **The Attacker Moves Second** (arXiv 2510.09023, 2025-10-10; autores de OpenAI,
  Anthropic y Google DeepMind): ataques adaptativos rompen 12 defensas publicadas, con más
  del 90 % de éxito contra Protect AI, PromptGuard y Model Armor [S15].
- **Agents Rule of Two** (Meta, 2025-10-31): en una sesión, como máximo dos de tres
  propiedades (procesar entrada no confiable, acceder a datos sensibles, cambiar estado o
  comunicarse hacia fuera). Si hacen falta las tres, supervisión humana [S16].
- **Defensas fuera de banda con evaluación adaptativa** (arXiv 2606.26479, 2026-06-25): las
  defensas deterministas de aplicación de políticas (CaMeL, Progent y otras) aguantan mejor
  la evaluación adaptativa que las defensas dentro del modelo [S17].

### Mapeo del diseño de Untangle

| Decisión aprobada | Patrón al que corresponde | Qué garantiza | Qué **no** garantiza |
| --- | --- | --- | --- |
| Transiciones en código; el LLM nunca enruta (ADR-003, convención 5c) | Code-Then-Execute con programa escrito por humanos (más fuerte que Plan-Then-Execute) | El texto no confiable no cambia el grafo | Los **valores** que el LLM extrae sí entran al programa (G2) |
| Las reglas deciden categoría y derivación | Action-Selector sobre un conjunto cerrado | La categoría sale de un conjunto cerrado | Las reglas son tan confiables como los campos de entrada (G2) |
| Verificador exacto: solo identificadores recuperados (ADR-011) | Validación de salida por referencia | Cero citas inventadas o de otra aseguradora | El "respaldo" con una segunda pasada del LLM sigue siendo probabilístico (G5) |
| Texto externo como campo delimitado del estado | Spotlighting, variante de delimitación (la más débil) | Reduce la inyección indirecta | No es una frontera de seguridad; no debe presentarse así (G6) |
| Guardia de salida por turno | Filtro determinista de salida | Bloquea frases prohibidas conocidas | Paráfrasis, mezcla de idiomas y **contenido ya emitido por streaming** (G1, G10) |
| `interrupt()` antes de afirmar cobertura o montos | Humano en el bucle (Rule of Two) | La decisión de alto impacto la firma una persona | La persona puede ser manipulada por lo que le muestra el sistema (G3) |
| RLS y sesión ligada a la aseguradora; enlace de visitante limitado al caso (ADR-012) | Mínimo privilegio y confinamiento de datos | El atacante no alcanza datos ajenos aunque el modelo sea engañado | Nada; es el control más fuerte del diseño |

**Análisis Rule of Two.** Una sesión de chat o voz reúne las tres propiedades: entrada no
confiable del visitante, acceso a su póliza y su caso, y cambios de estado (crear o
actualizar el caso, derivar). El diseño cumple el espíritu de la regla porque (a) el dato
sensible alcanzable está confinado al caso del propio visitante por RLS y por el enlace
firmado, (b) los cambios de estado automáticos son de bajo impacto y reversibles, y (c) lo de
alto impacto pasa por `interrupt()`. **Conviene escribir este razonamiento en el ADR**: es
corto, verificable y reconocible para un evaluador senior.

### Huecos encontrados

- **G1. Streaming antes de la guarda.** Si la voz transmite tokens del LLM a TTS, o el chat a
  SSE, la frase prohibida se pronuncia o se pinta antes de que la guardia la vea. La guardia
  tiene que operar sobre **frases completas almacenadas en búfer** antes de TTS y antes de
  enviar al navegador, con un presupuesto de latencia medido. No encontré esta condición
  explícita en los ADR que leí (ADR-011 a ADR-015; la librería de voz sigue pendiente en
  ADR-009). **Debe ser un requisito de NFR Design y un caso de DS-5 y DS-6.**
- **G2. Los campos extraídos son el conducto.** "Las reglas deciden" vale lo que valen sus
  entradas, y las entradas las extrae un LLM de texto no confiable: heridos, fecha del
  accidente, tercero, relato. Mitigación con el patrón Dual LLM (salida del LLM en
  cuarentena restringida a símbolos): solo campos tipados con enum o formato alimentan
  reglas, ningún texto libre las alimenta; lo declarado por el asegurado se marca
  `declared` frente a `verified` (vigencia desde la base de datos, nunca desde el relato);
  las inconsistencias derivan (RT-7). Añadir un caso de DS-6 en el que la inyección intenta
  fijar un campo que cambia la categoría.
- **G3. La bandeja del ajustador como vector (ASI09).** Es el caso *Medical Diagnosis via LLM
  Intermediary* del artículo de patrones: un resumen redactado por el modelo y leído por una
  persona puede llevar persuasión inyectada ("verificado, aprobar de inmediato").
  Mitigación: la bandeja muestra primero campos estructurados, resultados de reglas y
  transcripción literal con procedencia; todo resumen del modelo va etiquetado como tal y
  después de los hechos. Añadir un caso RT dirigido al ajustador.
- **G4. Renderizado de la salida (LLM10:2026).** En el chat web y en la bandeja, la salida
  del modelo se renderiza como texto plano: sin markdown de imágenes ni enlaces
  automáticos, con CSP `img-src 'self'`. Esto cierra la exfiltración por URL de imagen.
  Cuesta poco y debe tener su prueba de Playwright.
- **G5. Minimizar contexto en respuestas de cobertura.** Opción a evaluar en Functional
  Design, no un cambio impuesto: el LLM **elige identificadores de cláusula** del conjunto
  recuperado (Action-Selector) y la respuesta **cita literalmente** el texto de la cláusula
  desde la base de datos, con plantilla del catálogo de copy; el modelo no parafrasea la
  cobertura. Esto elimina el vector de desinformación (LLM07:2026) y reduce el papel de la
  "segunda pasada del modelo" de ADR-011. Es compatible con P1, que ya prohíbe afirmar
  cobertura.
- **G6. No vender la delimitación como defensa.** En el README se describe como "reducción de
  riesgo medida por DS-6 RT-2", nunca como frontera. Para el texto del corpus en la segunda
  pasada, *datamarking* es barato; su efecto se mide, no se supone.
- **G7. RT-5 está planteado para perder.** Con LLM08:2026 OWASP asume que el contexto oculto
  **se va a filtrar** y pide no guardar ahí secretos ni lógica sensible. Además, el
  repositorio será público en la semana 12, así que los prompts ya lo son. Propuesta:
  revelar las instrucciones pasa a severidad baja y a métrica informativa; lo que
  **bloquea** es que el contexto contenga secretos, configuración de otra aseguradora o
  datos personales de otro caso. Hoy RT-5 sería un caso eternamente inestable.
- **G8. DS-6 estático no mide robustez.** Por *The Attacker Moves Second*, pasar DS-6 solo
  prueba resistencia a ataques conocidos. El README lo dice así, y el red-team por hito usa
  estrategias adaptativas multi-turno (ver la sección 4).
- **G9. Consumo sin límite (LLM06:2026).** RT-13 ya lo cubre. Conviene añadir que el techo
  cuenta también los tokens de **entrada** de conversaciones largas (inflado de contexto),
  no solo el número de mensajes.
- **G10. Evasión entre idiomas en guardas léxicas (RT-15).** La guardia determinista necesita
  léxico por idioma **y** patrones independientes del idioma (cifras, monedas, porcentajes,
  números escritos con letras) y normalización (NFKD, tildes, mayúsculas, homoglifos
  básicos). Pruebas de propiedades con Hypothesis que generen variantes (ver la sección 8).

### Recomendación

- **Adoptar en el runtime**: G1 (búfer por frase antes de TTS y SSE), G2 (solo campos
  tipados alimentan reglas; `declared` frente a `verified`), G4 (texto plano y CSP) y G10
  (normalización y patrones independientes del idioma).
- **Adoptar en diseño y pruebas**: G3 (orden y etiquetado en la bandeja, caso RT nuevo), G7
  (reformular RT-5) y G8 (redacción honesta del README).
- **Diferir para evaluarlo en Functional Design**: G5 (cita literal en lugar de paráfrasis).
- **Rechazar y documentarlo en un ADR**: implementar CaMeL. El grafo ya fija el flujo de
  control en código y el agente no tiene herramientas con efectos que capabilidades
  protegerían. Sería **riesgo curricular**; basta citarlo como el patrón del que el diseño
  toma la idea.
- **Nuevo ADR recomendado** (o adenda a ADR-011 y ADR-013): "Defensa contra inyección por
  diseño", con la tabla de mapeo, el análisis Rule of Two y los rechazos de la sección 3.

---

## 3. Herramientas de guardas: cuáles, dónde y con qué latencia

### Hallazgos

| Herramienta | Estado al 2026-09-17 | Encaje con Untangle |
| --- | --- | --- |
| **NeMo Guardrails** (NVIDIA) | Activo: 0.24.1 (2026-09-16), `requires_python <3.14`. Desde 0.22 (2026-05-22) LangChain es opcional, y trae *rails* de entrada en paralelo o especulativos; 0.23 añadió clasificadores ligeros de Hugging Face y captura OpenTelemetry [S18], [S19]. Licencia `NOASSERTION` en la API de GitHub (**no verificada**; históricamente Apache-2.0). | Sus *dialog rails* en Colang compiten con LangGraph como orquestador y sus *self-check rails* son llamadas extra al LLM, con latencia y cuota. Choca con "el LLM nunca enruta". |
| **Guardrails AI** | Comprada por **Harvey**, anunciado el **2026-09-09**; el anuncio no dice qué pasa con el framework abierto [S20], [S21]. PyPI 0.11.0 (2026-08-14), Apache-2.0. Muchos validadores del Hub llaman a modelos o a inferencia remota. | Futuro del código abierto incierto desde hace ocho días. |
| **LLM Guard** (Protect AI, hoy Palo Alto Networks) | **Archivado el 2026-07-09**; su propio aviso dice que el proyecto y sus modelos en Hugging Face ya no se mantienen [S22]. Última versión 0.3.16 (2025-05-19) con `requires_python <3.13` [PyPI]. | **Incompatible con Python 3.13 (ADR-002)** y sin mantenimiento. |
| **Llama Prompt Guard 2** (22M y 86M) | Licencia Llama 4 Community (acceso con formulario y datos personales), del 2025-04 [S23]. Ventana de 512 tokens; 86M multilingüe (evaluado en español), 22M no (AUC multilingüe 0,942 frente a 0,995). Latencia publicada solo en A100 (92,4 ms el 86M y 19,3 ms el 22M, según la tarjeta) [S24]. Su tarjeta reconoce la limitación frente a ataques adaptativos, y [S15] obtuvo más del 90 % de éxito contra PromptGuard. Groq lo sirve gratis (30 RPM, 14,4 mil RPD) [S25]. | **Latencia en CPU compartida no publicada: no verificada.** PyTorch añade cientos de MB a la imagen. |
| **Llama Guard 4** (12B), **ShieldGemma** (2B/9B/27B), **Qwen3Guard** (4B), **gpt-oss-safeguard** (20B), **Granite Guardian** (8B) | Clasificadores de *seguridad de contenido* (violencia, odio, sexual). En un benchmark de 2026 el mejor recall fue 84 % (Qwen Guard 4B) y gpt-oss-safeguard perdió el 75 % [S26]. Artificial Analysis (2026-06-11) los midió en GPU clase B200 [S27]. | Su taxonomía no cubre los riesgos del dominio (prometer cobertura, consejo legal, culpa). Necesitan GPU. |
| **Google Model Armor** | Detecta inyección y jailbreak, "probado" en español entre otros; residencia de datos por región [S28]. Precio (**secundario, no verificado**): 2 M tokens/mes gratis y luego 0,10 USD por millón [S29]. Exige proyecto de Google Cloud con facturación (**no verificado** con fuente primaria). [S15] obtuvo más del 90 % de éxito contra él. | Datos del visitante a otro servicio; cuenta con facturación contra la regla de no renovaciones ni excedentes; latencia de red dentro del turno. |
| **LlamaFirewall** (Meta) | 1.0.3 (2025-05-29), sin versiones desde entonces [PyPI]. | Orientado a agentes con código y herramientas. |

### Latencia dentro del turno de voz

Con un objetivo de p50 < 500 ms y p95 < 800 ms, y con STT, LLM y TTS consumiendo casi todo
ese presupuesto, cualquier clasificador neuronal en CPU compartida de hospedaje gratuito es
una apuesta sin datos: no hay cifras publicadas de CPU para Prompt Guard 2. Mi estimación,
**no verificada**, es de decenas a cientos de milisegundos por fragmento de 512 tokens en
una fracción de vCPU, más el arranque en frío de PyTorch. Una llamada remota (Groq, Model
Armor) añade una ida y vuelta de red en cada turno y una dependencia más en el camino
caliente.

Los tres controles del turno aprobados admiten implementación determinista en
milisegundos:

- **Guardia de salida:** léxico bilingüe normalizado, patrones independientes del idioma
  (montos, porcentajes, "cubierto/covered", "culpa/fault", "le recomiendo/you should") y
  búfer por frase. Presupuesto propuesto: p95 ≤ 5 ms por frase, **a medir**.
- **Pide una persona:** léxico por idioma más señal del canal (botón, DTMF simulado, palabra
  clave).
- **Emergencia:** léxico bilingüe de heridos y peligro, con red de respaldo en el ritmo de
  fondo (extracción del LLM) que dispara la derivación como mucho un turno después.

### Recomendación: conjunto mínimo creíble

- **Adoptar en el runtime**: solo controles deterministas propios (los tres del turno) más
  los patrones de la sección 2. Añadir al diseño la medición de su latencia en la traza
  (span propio por control).
- **Rechazar y documentarlo en un ADR** (el nuevo ADR de la sección 2):
  - NeMo Guardrails: segundo orquestador, llamadas extra al LLM y choque con P3.
  - Guardrails AI: adquisición en curso y validadores remotos.
  - LLM Guard: archivado y no instala en Python 3.13.
  - Llama Guard 4, ShieldGemma, Qwen3Guard y gpt-oss-safeguard: taxonomía equivocada y GPU.
  - Model Armor: facturación, datos a terceros y latencia; además, bypass adaptativo
    documentado.

  **El argumento central del ADR** es que el diseño no depende de *detectar* la inyección,
  sino de que un modelo engañado no pueda hacer nada importante. Es la misma tesis con la
  que abre el OWASP LLM Top 10 2026 [S3].
- **Diferir (trabajo futuro)**: Llama Prompt Guard 2 86M **fuera del turno**, como señal
  asíncrona registrada en la traza para análisis de red-team, o para escanear el corpus al
  ingerirlo (práctica ya adoptada en Practices Discovery). Hoy el corpus es sintético y lo
  escribe Miguel, así que el escaneo tendría poco que encontrar. Adoptarlo sin que cambie
  ninguna decisión sería **riesgo curricular**. Si se adopta, registrar la licencia Llama 4
  y su atribución.

---

## 4. Herramientas de red-team

### Hallazgos

| Herramienta | Propiedad y licencia | Estado | Utilidad para DS-6 |
| --- | --- | --- | --- |
| **promptfoo** (red team) | **OpenAI anunció su compra el 2026-03-09**; la empresa se compromete a mantener el código abierto y el soporte multiproveedor [S30], [S31]. MIT. npm 0.123.0 (2026-09-10). | Muy activo (41 versiones en 2026). Presets `owasp:llm` y `owasp:agentic`; estrategias multi-turno Crescendo, GOAT, Hydra y Mischievous User; proveedor propio en Python (`file://`, `call_api`) [S32]. **La generación de ataques usa por defecto un servicio remoto de promptfoo**; se desactiva con `PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION=true`, con peor calidad según su documentación [S32]. La telemetría se desactiva con `PROMPTFOO_DISABLE_TELEMETRY=1` y no incluye prompts ni salidas [S33]. **No verificado**: si las respuestas del objetivo viajan al servicio remoto en las estrategias multi-turno. | Alta: genera ataques adaptativos multi-turno contra el adaptador de texto y deja resultados en archivos. Los ataques exitosos se convierten a mano en casos de DS-6. |
| **PyRIT** (Microsoft) | MIT. `microsoft/PyRIT` activo; el repositorio antiguo `Azure/PyRIT` está archivado. | 1.0.0 (2026-07-24) y 1.1.0 (2026-09-04) [PyPI]. Orquestadores multi-turno (Crescendo, TAP) y más de 20 evaluadores [S34]. | Media: potente pero con curva de aprendizaje alta y sin presets de marcos listos. |
| **garak** (NVIDIA) | Apache-2.0. | 0.17.0 (2026-09-09); más de 50 módulos de sondas; en 2026 añadió sondas multi-turno GOAT y de extracción del prompt de sistema [S35]. | Baja: escanea **modelos** con sondas genéricas; los riesgos de Untangle son de **aplicación** (promesas de cobertura, cruce entre aseguradoras). |
| **DeepTeam** (Confident AI) | Apache-2.0; mismo proveedor que DeepEval (depende de `deepeval>=3.6.2`). | 1.0.9 (2026-08-12). Más de 40 vulnerabilidades, marcos OWASP y ATLAS, ataques multi-turno; el simulador y el juez usan OpenAI por defecto (configurable); resultados en local o en Confident AI con clave [S36]. | Media: integración sencilla en Python, pero hereda la dependencia de DeepEval que la sección 6 propone quitar. |

### Recomendación

- **Adoptar solo en desarrollo/pruebas: una sola herramienta, promptfoo red team**, en las
  sesiones por hito (semanas 6, 9 y 12), con versión exacta, telemetría desactivada, la
  configuración YAML versionada en el repositorio y como objetivo el endpoint de texto del
  despliegue local o vivo. Razones: es la más reconocible para los evaluadores, trae
  estrategias adaptativas (responde a G8) y mapea contra OWASP 2026. Anotar en el ADR que
  su dueño es OpenAI y decidir por escrito si se usa la generación remota: los datos son
  sintéticos, pero consume un servicio de terceros. **Nunca en CI por cada push**: consume
  cuota y no es determinista. Lo que corre en CI es DS-6, en archivos.
- **Rechazar y documentarlo en el ADR**: PyRIT, garak y DeepTeam **en paralelo** a promptfoo.
  Tener cuatro herramientas de red-team es **riesgo curricular** claro. DeepTeam queda
  como alternativa si Miguel prefiere todo en Python y mantiene DeepEval.
- **Adoptar en el proceso**: plantilla de conversión "hallazgo de red-team → caso DS-6" con
  campos `source: redteam`, `tool`, `tool_version`, `strategy`, `rt_id` y `atlas` opcional,
  para que el origen quede trazado.

---

## 5. Práctica de LLM como juez (2025-2026)

### Hallazgos

- **Binario antes que Likert.** Husain y Shankar recomiendan etiquetas pasa/falla; las
  escalas Likert son "avanzadas y normalmente innecesarias" y exigen más muestra. **Análisis
  de errores antes de métricas**: codificación abierta, luego axial, hasta saturación; al
  menos 30 trazas revisadas en persona y unas 100 en total. Etiquetar de 100 a 200 ejemplos
  **por modo de fallo**, repartidos en train (10-20 %), dev (40-45 %) y test (40-45 %). Las
  métricas genéricas "crean falsa confianza". En CI, preferir comprobaciones deterministas
  (FAQ actualizado el 2026-09-13) [S37].
- **El acuerdo bruto es una métrica trampa.** Con fallos poco frecuentes, un juez que siempre
  dice "pasa" obtiene acuerdo alto. Hay que medir **TPR y TNR** sobre un conjunto etiquetado
  separado [S37], [S38]. La librería `judgy` corrige la tasa observada con
  θ = (p_obs + TNR − 1)/(TPR + TNR − 1) y da intervalo por bootstrap [S39].
- **Validar a los validadores** (Shankar et al., arXiv 2404.12272, 2024-04-18, UIST 2024):
  los criterios cambian mientras se califican salidas ("criteria drift"), así que la rúbrica
  no se congela antes de ver trazas [S40].
- **Sesgos.** De autopreferencia: los LLM reconocen y favorecen sus propias salidas
  (Panickssery et al., arXiv 2404.13076, 2024-04-15) [S41]. De posición y verbosidad
  (Zheng et al., MT-Bench, arXiv 2306.05685, 2023) [S42] (**no re-verificado en esta
  sesión**). **Multilingüe**: los evaluadores GPT-4 inflan las puntuaciones fuera del
  inglés y hay que calibrar con hablantes nativos por idioma (Hada et al., EACL Findings
  2024) [S43].
- **¿Mismo modelo como juez?** Husain lo considera "usually fine" si TPR y TNR contra
  etiquetas humanas son buenos (FAQ del 2025-05-28, modificado el 2025-09-22) [S44].
- **pass^k** (τ-bench, arXiv 2406.12045, 2024-06-17): la probabilidad de que las k
  corridas pasen. GPT-4o pasó de 61 % en pass@1 a 25 % en pass^8 en comercio [S45]. Inspect
  AI trae el reductor `pass_k`, además de `at_least`, `pass_at` y `krippendorff_alpha`
  [S46].
- **Usuario simulado.** τ-bench simula al usuario con un LLM. El respondedor por reglas
  indexado por campo del PRD es una elección defendible para CI, porque evita el ruido del
  simulador.

### ¿Es sólido el umbral del 85 % de acuerdo?

**No, por tres razones que se pueden calcular:**

1. **Tamaño.** DS-7 tiene 40 transcripciones, 20 por idioma. Con 17 de 20 aciertos (85 %),
   el intervalo de Wilson del 95 % es **[64 %, 95 %]**; con 34 de 40, [71 %, 93 %]. Con esa
   muestra no se distingue un juez del 85 % de uno del 65 %.
2. **Desbalance.** Si en 20 turnos hay 18 buenos y 2 malos, un juez que acierta 17 de 18
   buenos y 1 de 2 malos obtiene **90 % de acuerdo** con **TNR = 50 %** (se le escapa la
   mitad de los fallos) y κ de Cohen = 0,44. Un juez que siempre dice "pasa" obtiene 90 % y
   κ = 0.
3. **Mismo conjunto para ajustar y medir.** Si la rúbrica se ajusta mirando los desacuerdos
   con DS-7 (PRD 11.3: "los desacuerdos alimentan la rúbrica") y luego se mide contra el
   mismo DS-7, la cifra está sobreajustada.

La κ de Cohen corrige el azar pero sufre la paradoja de la κ con clases desbalanceadas y no
dice **qué tipo** de error comete el juez. TPR y TNR sí lo dicen, y cada uno se liga a una
consecuencia: un TNR bajo deja pasar fallos a la compuerta; un TPR bajo genera falsas
alarmas y revisión humana innecesaria.

### Recomendación

- **Adoptar solo en desarrollo/pruebas** (cambia PRD 11.3 y ADR-014):
  - Criterio del juez **por criterio y por idioma**: **TNR ≥ 0,90 y TPR ≥ 0,85** (valores
    iniciales a fijar en `nfr-requirements`), medidos **sobre la partición de prueba** de
    DS-7 y publicados con n e intervalo de Wilson. κ se reporta como dato secundario, nunca
    como compuerta. Si el límite inferior del intervalo queda por debajo del umbral, el
    criterio se reporta "no medida" (misma mecánica ya aprobada para el juez
    descalibrado).
  - **Etiquetar por turno, no por transcripción.** 20 transcripciones por idioma con unos 10
    turnos dan unas 200 etiquetas binarias por idioma sin grabar nada nuevo. Particiones
    train/dev/test fijas y versionadas.
  - **Fallos sembrados** cuando falten negativos reales (turnos editados a mano para que
    violen el criterio), marcados como sembrados; su TNR se reporta aparte del TNR sobre
    fallos reales.
  - **Corrección de la tasa reportada** con TPR y TNR, al estilo `judgy`: diez líneas de
    código propio, sin dependencia.
  - **Análisis de errores antes de congelar rúbricas** (semanas 3 y 4): codificación
    abierta y axial sobre las primeras corridas de DS-2 v0. La taxonomía de causa raíz del
    PRD 11.3 es el resultado, no el punto de partida.
  - **pass^k por hito**, con k = 3 sobre DS-2 y DS-6, no por push (cuota). Un caso con
    0 < c < k se marca **inestable automáticamente**, lo que convierte la política de casos
    inestables en una métrica y no en un juicio.
- **Adoptar solo en desarrollo/pruebas**: un **segundo juez de otra familia solo para
  calibración**, no en CI. Opción viable sin tarjeta: `openai/gpt-oss-120b` en el plan
  gratuito de Groq (30 RPM, 1 mil RPD, 8 mil TPM, 200 mil TPD) [S25]. Alcanza para DS-7
  (unas 400 llamadas en dos días) pero **no** para CI por push: a 8 mil TPM, unas 180
  llamadas de juez sobre DS-2 tardarían más de 30 minutos (estimación, con unos 1.500 tokens por llamada). Sirve para medir la
  autopreferencia del juez de Gemini sobre las salidas de Gemini y publicarla. Registrar
  en el ADR el flujo de datos: solo transcripciones sintéticas y redactadas.
- **Diferir**: jueces con puntuación 1 a 5 (el PRD admite "1 a 5 o pasa/falla" en DS-7). Se
  recomienda quedarse solo con pasa/falla.
- **No verificado**: los límites del plan gratuito de Gemini para `gemini-3.1-flash-lite`.
  La página oficial remite a AI Studio [S47]. Hay que medirlos antes de fijar qué parte del
  juez corre en CI.

---

## 6. Frameworks de evaluación (septiembre de 2026)

### Hallazgos

| Framework | Estado | Observación para Untangle |
| --- | --- | --- |
| **DeepEval** | Apache-2.0. 4.2.3 (2026-09-14); **46 versiones en 2026**; major 4.0 el 2026-05-08, reposicionado como "evaluation harness for vibe coding agents" [S48]. Telemetría a PostHog, desactivable con `DEEPEVAL_TELEMETRY_OPT_OUT=1` [S49]. **29 dependencias base**, entre ellas `posthog`, `openai`, `grpcio`, `pytest-rerunfailures`, `pytest-repeat`, `pytest-xdist`, `setuptools` y `wheel` [PyPI]. | `pytest-rerunfailures` en el entorno de pruebas facilita **reintentar hasta pasar**, que contradice "inestable, nunca oculto". El churn obliga a fijar versión y vigilar. Sus métricas de marca (G-Eval, answer relevancy) son las "genéricas" que desaconseja [S37]. |
| **promptfoo** (runner) | MIT, de OpenAI (ver la sección 4). | ADR-014 ya lo rechaza como runner principal, con razón: conversaciones con respondedor por reglas y grafo en proceso. Se mantiene para red-team. |
| **Inspect AI** (UK AISI) | MIT. 0.3.264 (2026-09-17); 86 versiones en 2026. Solvers, scorers, epochs, reductores `pass_k` y `krippendorff_alpha`, visor de logs [S46], [S50]. **41 dependencias base** (boto3, s3fs, fastapi, textual, tiktoken…) [PyPI]. | Muy reconocible entre Staff AI Engineers. Adoptarlo **además** del runner propio sería duplicación. Su peso de dependencias es alto para CI. |
| **Ragas** | Apache-2.0. Última versión 0.4.3 (**2026-01-13**); último commit en `vibrantlabsai/ragas` (antes `explodinggradients`) el **2026-02-24** [GitHub API]. | Sin actividad en siete meses. El recall de recuperación sobre DS-3 se calcula a mano en pocas líneas, como ya prevé el PRD. |
| **OpenAI Evals** | Repositorio sin cambios desde 2026-04-14 [GitHub API]; la versión alojada está atada a la plataforma de OpenAI. | No aplica. |
| **Langfuse datasets/experiments** | MIT (todo el producto es abierto desde 2025-06-04) [S51]. Los experimentos por SDK **requieren una instancia de Langfuse** incluso con datos locales [S52]. | Útil en local para anotación y comparación; no sirve como compuerta de CI sin servidor (ver la sección 7). |
| **Pydantic Evals** | MIT, 2.44.0 (2026-09-17), 6 dependencias base; casos en YAML o JSON, `LLMJudge`, evaluadores sobre spans de OpenTelemetry, funciona sin Logfire [S53]. | Alternativa ligera y reconocible. No aporta frente al runner propio ya decidido. |
| **Braintrust**, **LangSmith** | SaaS (SDK MIT). | ADR-014 ya los rechaza: los datos salen del repositorio y tienen costo. |

### ¿Sigue siendo correcto "runner propio sobre pytest + métricas de DeepEval"?

**El runner propio sí**, y es la mejor señal posible para el perfil de evaluador. La lógica de
la compuerta (compuertas duras, regresión por caso, "no comparable", "no medida",
calibración) no la expresa ningún framework, y ADR-014 ya lo argumenta bien.

**DeepEval para el juez, no.** ADR-014 ya previó "un arnés propio detrás de la misma
interfaz" si la telemetría daba problemas. Las razones para **activar esa salida desde el
principio** son distintas pero más fuertes:

1. Los criterios del PRD son **binarios y de dominio** ("¿afirma cobertura?", "¿la cláusula
   sostiene la afirmación?"). Implementarlos es un prompt versionado más salida estructurada
   de Gemini más un parser: unas 150 a 300 líneas con pruebas.
2. Un Staff Engineer valora ver **el prompt del juez, su versión, su TPR/TNR por idioma y
   la corrección**, no un `GEval(...)` de librería.
3. Menos superficie de cadena de suministro, justo el año del compromiso de `litellm` en
   PyPI (sección 9), y sin plugins de pytest que alteren la semántica de las pruebas.
4. La cadencia y el reposicionamiento de DeepEval 4 son un riesgo de mantenimiento para un
   proyecto de 90 días.

**Matiz honesto:** el PRD (Segmento 11) pide "un framework ligero para la compuerta en CI
(promptfoo o DeepEval)". Quitar DeepEval es una **desviación del PRD** y se registra como tal.
Si Miguel prefiere respetar la letra, la alternativa mínima es mantener DeepEval con versión
exacta, en un grupo de dependencias aislado, sin cargar su plugin de pytest (`-p
no:rerunfailures`) y con telemetría desactivada y verificada por una prueba.

### Recomendación

- **Adoptar solo en desarrollo/pruebas**: runner propio sobre pytest (sin cambios) más
  **módulo de juez propio** (prompts versionados, salida estructurada, TPR/TNR, corrección,
  pass^k por hito).
- **Rechazar y documentarlo en el ADR** (enmienda de ADR-014): DeepEval como dependencia
  (con la alternativa mínima anterior si Miguel lo prefiere), Ragas por inactividad, OpenAI
  Evals y SaaS.
- **Diferir**: Inspect AI, citado en el ADR como la alternativa reconocible descartada por
  duplicación y peso. Revaluar si algún día se publican los golden sets como benchmark
  reutilizable.
- **Riesgo curricular**: sumar Inspect, Pydantic Evals o Langfuse experiments "para mostrar"
  junto al runner propio.

---

## 7. Observabilidad

### Hallazgos

- **Convenciones GenAI de OpenTelemetry**: estado **Development** en todos los atributos,
  spans, métricas y eventos; se trasladaron al repositorio
  `open-telemetry/semantic-conventions-genai`, creado el **2026-05-05**. Cubren spans de
  modelo, **spans de agente**, eventos, métricas, excepciones y MCP. El contenido
  (`gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`,
  `gen_ai.retrieval.documents`) es **Opt-In** [S54], [S55].
- **Instrumentaciones**:
  - `opentelemetry-instrumentation-google-genai` (contrib de OTel): 1.1b1 (2026-08-21),
    beta.
  - `openinference-instrumentation-langchain` (Arize, convención OpenInference, distinta de
    GenAI): 0.1.76 (2026-09-10).
  - `traceloop-sdk` (OpenLLMetry): 0.62.3; **Traceloop fue adquirida por ServiceNow en
    marzo de 2026** [S56], [S57].
  - El SDK de Gemini usa `httpx` y `websockets` [PyPI].
- **Langfuse**: **adquirida por ClickHouse el 2026-01-16**; sigue siendo abierta y
  autoalojable [S58]. Todas las funciones de producto (jueces, colas de anotación,
  experimentos) son MIT desde el 2025-06-04 [S51]. El autoalojamiento v4 exige **Postgres,
  ClickHouse, Redis o Valkey, almacenamiento S3 (MinIO), web y worker** [S59]. Docker
  compose: **al menos 4 núcleos y 16 GiB**, unos 100 GiB de disco, sin alta disponibilidad
  ni copias de seguridad [S60]. SDK de Python 4.15.4; ingesta OTLP en
  `/api/public/otel`; la nube retira las rutas de ingesta antiguas el 2026-11-16 [S61].
  **Plan Hobby**: 50 mil unidades al mes, 30 días, sin tarjeta [S62]; qué ocurre al
  superarlo **no está verificado**.
- **Arize Phoenix**: un contenedor con SQLite por defecto o PostgreSQL 14+ para producción;
  autenticación OAuth2, LDAP y local [S63], [S64]. **Licencia Elastic-2.0**, que no es OSI
  [PyPI]. 20.13.0 (2026-09-16).
- **Pydantic Logfire**: plan Personal gratis, **10 M de registros al mes con tope duro en
  0 USD**, 30 días, sin tarjeta; el autoalojamiento es solo Enterprise; SDK MIT, backend
  cerrado [S65].
- **CI**: los runners estándar de repositorios **privados** tienen **2 vCPU y 8 GB**; los
  públicos, 4 vCPU y 16 GB [S66]. Cuenta Free: 2.000 minutos al mes en privados y
  **bloqueo** al agotarlos si no hay medio de pago [S67].

### Desafío a ADR-015

1. **Rechazo de Phoenix mal justificado.** "Equivalente, pero el PRD eligió Langfuse" es
   circular, y un Engineering Manager que lee ADRs lo nota. El trade-off real es: Langfuse
   (MIT, colas de anotación útiles para la revisión semanal y DS-7, pila de 6 servicios con
   4 núcleos y 16 GiB) frente a Phoenix (un contenedor con SQLite, licencia Elastic-2.0 no
   OSI, anotaciones más simples). **Langfuse sigue siendo defendible** por las colas de
   anotación que el PRD usa de verdad, pero el ADR debe decirlo así.
2. **Los enlaces a trazas del reporte de CI no resolverán.** PRD 11.3 pide que el reporte
   enlace "a su traza en Langfuse". En GitHub Actions no hay Langfuse (y no cabe en 2 vCPU y
   8 GB). Alternativa: **exportador OTLP a archivo JSON** en CI, subido como artefacto de la
   corrida e importable al Langfuse local; el reporte enlaza al artefacto y al identificador
   de traza.
3. **Declarar el estado Development.** El ADR debe fijar la versión de las convenciones
   (commit o etiqueta del repositorio nuevo) y asumir renombres; los nombres propios de span
   (convención 3: `intake`, `policy_verification`…) aíslan del cambio.
4. **Contenido solo redactado.** Los atributos de contenido son Opt-In: se activan solo tras
   PiiRedaction (coherente con ADR-013) y nunca a través de la captura automática de una
   instrumentación de terceros, que escribiría el contenido sin redactar. Prueba: con la
   captura desactivada, ningún span contiene texto del usuario (el canario del segundo
   detector de ADR-013 lo verifica).
5. **Evitar dos convenciones.** Mezclar OpenInference (`llm.*`, `openinference.span.kind`)
   con GenAI (`gen_ai.*`) duplica atributos y confunde el panel. Mejor spans propios de
   turno, nodo y proveedor con atributos `gen_ai.*`, más la instrumentación contrib de
   google-genai si su captura de contenido se puede apagar (**verificar al crear el
   andamiaje**).

### Qué cabe en local y qué puede exportar un despliegue público gratuito

| Opción | Local (docker compose) | CI privado (2 vCPU, 8 GB) | Despliegue público gratuito |
| --- | --- | --- | --- |
| Langfuse autoalojado | Sí, en la máquina de Miguel (4 núcleos, 16 GiB) | No | No (pila de 6 servicios) |
| Langfuse Cloud Hobby | — | Posible, pero los datos salen | Sí, con muestreo: 50 mil unidades se agotan rápido con varios spans por turno |
| Phoenix | Sí, un contenedor | Sí, pero innecesario | Posible en un contenedor pequeño; Elastic-2.0 |
| Logfire Personal | — | — | Sí, con tope duro en 0 USD, backend cerrado |
| Archivo OTLP JSON | — | **Sí, como artefacto** | — |
| Solo `TraceSummary` en la base del aplicativo (ADR-015) | Sí | Sí | **Sí, sin tercero** |

### Recomendación

- **Adoptar en el runtime**: OTel con atributos `gen_ai.*` fijados a una versión, spans
  propios, contenido solo redactado y Opt-In.
- **Adoptar solo en desarrollo/pruebas**: Langfuse autoalojado en local (anotación y
  exploración) y exportador OTLP a archivo en CI como artefacto.
- **Diferir al intent `infra`**: exportación del despliegue público. Mi preferencia es no
  exportar trazas crudas del chat público (solo `TraceSummary` y una muestra redactada) o,
  si se exporta, Langfuse Cloud Hobby con muestreo. Logfire solo si se acepta un backend
  cerrado.
- **Rechazar y documentarlo en el ADR**: OpenLLMetry/`traceloop-sdk` (duplicaría la
  instrumentación; cambio de dueño) y la mezcla de convenciones OpenInference y GenAI.
- **Cambia ADR-015**: redacción del rechazo de Phoenix, estado Development, enlaces de CI y
  captura de contenido.

---

## 8. Pila de pruebas para una persona

### Hallazgos (herramientas)

- **Playwright** 1.63.0 (2026-09-04) y `@axe-core/playwright` 4.13.0 (2026-08-11).
  Prácticas oficiales: aislamiento, localizadores por rol, aserciones *web-first*,
  `trace: 'on-first-retry'` en CI, instalar solo Chromium en CI y la regla
  `no-floating-promises` [S68]. Las **comparaciones visuales** dependen de sistema operativo,
  navegador, fuentes y hardware; las líneas base se generan en el mismo entorno donde se
  comparan [S69].
- **Schemathesis** 4.27.3 (2026-09-17), MIT: OpenAPI 2.0 a 3.2, pruebas con estado por
  `links`, reproducción con `curl`, pytest contra la app ASGI con
  `schemathesis.openapi.from_asgi` sin servidor levantado [S70], [S71].
- **Hypothesis** 6.168.0 (2026-09-08), MPL-2.0: estrategias y pruebas con estado
  (`RuleBasedStateMachine`) [S72].
- **mutmut** 3.8.0 (2026-09-12), BSD-3: requiere `fork` (en macOS y Linux funciona; en
  Windows, WSL), solo pytest, reanuda corridas, restringe con `source_paths` y
  `only_mutate`, exporta estadísticas para CI [S73]. **cosmic-ray** 8.7.0: más
  configuración, pensado para distribución.
- **testcontainers-python** 4.15.0 (2026-07-24), Apache-2.0.
- **PostgreSQL 18**: los superusuarios, los roles con `BYPASSRLS` y **los dueños de la
  tabla** se saltan RLS salvo `ALTER TABLE ... FORCE ROW LEVEL SECURITY` [S74].
- **Grabación de proveedores**: `vcrpy` 8.3.0 (2026-07-04), activo; `pytest-recording`
  0.13.4 (**2025-05-08**, sin versiones en 16 meses aunque el repositorio tiene commits);
  `respx` 0.23.1 (2026-04-08) para `httpx`. El SDK de Gemini usa `httpx` (grabable) y
  `websockets` para la API Live (**no** grabable con vcrpy) [PyPI].
- **Carga**: Locust (MIT, Python) y k6 (AGPL-3.0, JavaScript).
- **Voz**:
  - LiveKit Agents trae pruebas **en modo texto** con pytest (aserciones `is_message`,
    `judge`); el audio solo en simulaciones beta o con terceros (Bluejay, Hamming) [S75].
  - LangWatch Scenario (Apache-2.0) simula usuarios.
  - Plataformas comerciales: Hamming, Coval, Cekura, Roark.
  - La librería de voz sigue pendiente (ADR-009).

### Pirámide propuesta para una persona

De abajo arriba, con el criterio "¿protege una compuerta dura o una convención verificable?":

| Capa | Qué | Herramienta | Frecuencia | ¿Vale la pena? |
| --- | --- | --- | --- | --- |
| 0. Estática | Formato, lint con reglas `S`, tipos, frases prohibidas, paridad de claves | Ruff, mypy, ESLint, tsc y chequeos propios (ya aprobados) | Cada push | Sí (ya decidido) |
| 1. Unitarias y de propiedades | Motor de reglas, función de transición (conjunto cerrado de nodos), normalizadores (fechas relativas, placas, dígitos), resultados cerrados del verificador, **reconocedores de PII generados con Hypothesis por formato e idioma** (toda placa o cédula generada queda redactada, incluidas variantes con espacios, guiones y mezcla de idiomas) y **máquina de estados del caso con `RuleBasedStateMachine`** (ninguna secuencia de eventos llega a un estado ilegal; la retoma conserva los campos) | pytest y **Hypothesis** | Cada push | **Sí**: encuentra casos límite que los ejemplos escritos a mano no cubren y es la forma barata de probar RT-15 |
| 2. Integración con Postgres real | RLS y políticas en cada tabla (aserción de esquema), **rol del aplicativo sin `BYPASSRLS` y no dueño de las tablas, o `FORCE ROW LEVEL SECURITY`**, tenant fijado con alcance de **transacción** (`set_config(..., true)`) para que no se filtre entre conexiones del pool, fixtures de colisión de DS-8 | **testcontainers** (Postgres 18 con pgvector si ADR-010 lo usa) | Cada push | **Sí**: RLS no se puede probar con SQLite ni con mocks; el dueño que se salta RLS es el error clásico |
| 3. Contrato de API | Schemathesis sobre FastAPI en proceso, con fixtures de autenticación por aseguradora y rol; **chequeo propio**: ninguna respuesta contiene identificadores de las fixtures de otra aseguradora (DS-8); sin errores 5xx; respuestas conformes al esquema | **Schemathesis** | Cada push (presupuesto de ejemplos acotado) | **Sí**: protege el cliente generado desde OpenAPI (ADR-002) y RT-4 de forma genérica |
| 4. Adaptadores de proveedor | Fakes en el puerto propio (ADR-018) para el núcleo; **pruebas de contrato del adaptador** con respuestas grabadas; **inyección de errores** (timeout, 429, 5xx, JSON inválido) → taxonomía cerrada de la convención 8 | **vcrpy** con `filter_headers` para las claves, **respx** para errores; websockets de voz con fakes | Cada push | Sí. `pytest-recording`: **diferir** (sin versiones desde 2025-05) |
| 5. Golden sets | DS-2, DS-3 y DS-6 con compuertas duras | Runner propio | Cada push (subconjunto declarado si hace falta) | Sí (ya decidido) |
| 6. E2E de interfaz | 4 a 6 recorridos críticos: FNOL por chat con divulgación en la primera frase, petición de persona, aprobación en la bandeja (`interrupt()`), el enlace de una hora no abre la lista, **salida renderizada como texto plano (G4)**; axe en cada pantalla, modos claro y oscuro | **Playwright** con axe, traza en el primer reintento | Cada push (solo Chromium) | Sí, acotado |
| 7. Mutación | Módulos críticos solamente: motor de reglas, verificador de citas, función de transición, punto de sesión | **mutmut** | Por hito; puntuación publicada | **Sí, acotado**: es la herramienta que hace cumplir la regla de fase "no generar pruebas que pasen con independencia de la implementación". En todo el código sería riesgo curricular |
| 8. Latencia y carga | Latencias por etapa (red, STT, LLM, TTS, guardas) sacadas de **spans** sobre DS-5; límites de RT-13 con pruebas concurrentes en pytest y `httpx`; duración de la corrida de evals | Arnés propio sobre trazas | Por hito (DS-5); RT-13 en cada push | Sí. **Locust y k6: diferir**; la meta es latencia por turno, no rendimiento bajo carga |
| 9. Voz | Pruebas en modo texto del framework (si se elige LiveKit); **arnés de repetición de DS-5** que inyecta WAV al adaptador STT y mide con spans y marcas de interrupción | Framework elegido en ADR-009 y arnés propio | Por hito | Sí. Plataformas comerciales: **rechazar** (cuentas y costo). LangWatch Scenario: **diferir** (exploratorio) |
| 10. Regresión visual | Capturas de 2 o 3 pantallas clave en el contenedor de CI | Playwright `toHaveScreenshot` | Por hito | **Diferir**: duplica en claro y oscuro, falla por fuentes y ya hay línea base de accesibilidad |

**Nota de CI:** con el repositorio privado, 2.000 minutos al mes y bloqueo al agotarlos: con
unos 15 minutos por push, caben unos 130 pushes al mes. Recomiendo `concurrency` con
cancelación de la corrida anterior y filtros de rutas **solo para trabajos que no sean la
compuerta** (la compuerta de evals nunca se apaga, según las prácticas aprobadas). Al hacerse
público, los minutos son gratis y los runners duplican recursos.

### Recomendación

- **Adoptar solo en desarrollo/pruebas**: Hypothesis (incluido el modo con estado),
  testcontainers, Schemathesis, vcrpy y respx, Playwright con axe (ya aprobados), mutmut por
  hito sobre 4 módulos, y el arnés de latencia sobre spans.
- **Adoptar en el runtime** (derivado de las pruebas): rol del aplicativo sin `BYPASSRLS` y
  con `FORCE ROW LEVEL SECURITY`, y tenant con alcance de transacción. Es un detalle de
  ADR-012, no un cambio.
- **Diferir**: regresión visual, Locust y k6, LangWatch Scenario, pytest-recording.
- **Rechazar y documentarlo en el ADR**: cosmic-ray (mutmut basta) y plataformas comerciales
  de evaluación de voz.
- **Riesgo curricular**: mutación en todo el código, k6 "para tener pruebas de carga" o
  regresión visual en cada push.

---

## 9. Cadena de suministro

### Hallazgos

- **Incidentes de 2026 que justifican cada control:**
  - **Trivy** (CVE-2026-33634, 2026-03-19 al 23): credenciales comprometidas; reescribieron
    **76 de 77 etiquetas** de `aquasecurity/trivy-action` y las 7 de `setup-trivy`, y
    publicaron binarios e imágenes troyanizados. El aviso oficial recomienda fijar Actions
    por SHA completo y rotar secretos [S76].
  - **LiteLLM en PyPI** (2026-03-24): versiones 1.82.7 y 1.82.8 con robo de credenciales
    mediante un archivo `.pth`, atribuido a la misma campaña, que tocó GitHub Actions,
    Docker Hub, npm, OpenVSX y PyPI [S77], [S78].
- **Fijar por SHA**: desde el 2025-08-15 la política de Actions permite **exigir SHA
  completo** y bloquear acciones concretas, también a nivel de repositorio [S79].
- **zizmor** 1.30.1 (2026-09-09), MIT: auditorías offline `unpinned-uses`,
  `template-injection`, `excessive-permissions`, `artipacked`, `dangerous-triggers`,
  `cache-poisoning`; online `impostor-commit` y `known-vulnerable-actions` [S80].
- **Escaneo de secretos**:
  - **GitHub secret scanning y push protection**: gratis y activos en repositorios
    **públicos**. En repositorios **privados de cuenta personal no están disponibles**; se
    venden como GitHub Secret Protection (19 USD por usuario) para organizaciones [S81],
    [S82], [S83] (disponibilidad por cuenta personal confirmada solo con fuentes
    secundarias y la discusión de la comunidad).
  - **gitleaks**: MIT, activo (push del 2026-09-09); `gitleaks-action` no pide licencia
    para cuentas personales [S84].
  - **Betterleaks**: el 2026-03-19 el creador de gitleaks dijo que ya no controla del todo
    el repositorio ni la marca y lanzó este sucesor MIT, patrocinado por Aikido, compatible
    con la CLI y la configuración de gitleaks [S85]. Su recall del 98,6 % frente al 70,4 % es
    **dato del proveedor, no verificado**.
  - **trufflehog**: AGPL-3.0; verifica en vivo si un secreto sigue activo.
- **Enfriamiento de versiones**:
  - Dependabot `cooldown` (`default-days` y días por nivel semver) admite `uv`, `npm/pnpm` y
    `github-actions` (solo `default-days`); no aplica a actualizaciones de seguridad [S86].
  - uv `exclude-newer` acepta duraciones relativas como `"7 days"` [S87].
  - pnpm `minimumReleaseAge` en minutos desde **10.16.0**; **el valor por defecto es 1440
    (24 h) desde pnpm 11** [S88]. **Dato fuera de mi carril**: pnpm va por **12.4.2**
    (2026-09-15) y la 11.0.0 salió el 2026-04-28; ADR-002 fija pnpm 10 [npm].
- **OpenSSF Scorecard**: en privados requiere GitHub Advanced Security; útil al hacerse
  público [S89].
- **Atestaciones y SBOM**: GitHub genera atestaciones con Sigstore (instancia pública para
  repositorios públicos) [S90]. `cyclonedx-bom` (`cyclonedx-py`) 7.4.0 (2026-09-15).
  Practices Discovery **ya descartó** SBOM firmado, atestación de procedencia y firma de
  commits.
- **Dependabot frente a Renovate**: Dependabot es nativo y soporta `uv`, `pnpm`,
  `github-actions` y `cooldown`; Renovate es AGPL-3.0, más configurable, y requiere
  instalar una app.

### Recomendación: conjunto mínimo creíble para un repositorio que será público

1. **Primer trabajo de CI: gitleaks** (binario fijado con checksum o `gitleaks-action` por
   SHA) sobre el diff y, por hito, sobre **todo el historial**. Configuración compatible con
   Betterleaks para poder cambiar sin coste si la gobernanza de gitleaks se degrada.
   → `adoptar solo en desarrollo/pruebas`.
2. **Antes de publicar (semana 12)**: una pasada única de **trufflehog `--only-verified`**
   sobre el historial completo, para saber si algún secreto filtrado sigue vivo; después,
   **activar GitHub secret scanning y push protection** (gratis al ser público). Esto
   cumple la práctica "activar la protección de inserción si está disponible", que hoy no
   lo está. → `diferir` hasta la publicación.
3. **Todas las Actions fijadas por SHA completo**, política de repositorio que lo exige,
   `permissions: {}` por defecto con permisos por trabajo, y `persist-credentials: false`
   en `checkout`. → `adoptar solo en desarrollo/pruebas`.
4. **zizmor** en CI (auditorías offline) y en local desde el archivo de tareas.
   → `adoptar solo en desarrollo/pruebas`.
5. **Dependabot** para `uv`, `pnpm` y `github-actions`, con `cooldown.default-days: 7` en
   actualizaciones de versión; las de seguridad no esperan. **uv `exclude-newer = "7 days"`**
   y **pnpm `minimumReleaseAge: 10080`**, con excepciones anotadas. Frena exactamente la
   ventana de horas de los incidentes de Trivy y LiteLLM. → `adoptar solo en
   desarrollo/pruebas`. Renovate → `rechazar` (Dependabot basta).
6. `pip-audit` y `pnpm audit` (ya aprobados).
7. **SBOM CycloneDX sin firma** generado por hito como artefacto: su valor real es alimentar
   el **registro de licencias** obligatorio de las prácticas, no lucir. → `adoptar solo en
   desarrollo/pruebas` (por hito).
8. **OpenSSF Scorecard** → `diferir` hasta la publicación. Es barato y su insignia es
   reconocible, pero en privado no funciona sin GHAS.
9. **Sigstore/cosign y atestaciones** → `rechazar` (ya rechazado en Practices Discovery). No
   se distribuyen paquetes ni imágenes a terceros: sería **riesgo curricular**.

---

## Tabla final de recomendaciones

| Tecnología | Recomendación | Razón | ¿Cambia un ADR aprobado? |
| --- | --- | --- | --- |
| OWASP Top 10 LLM **2026** | Adoptar (README y docs) | Edición vigente desde el 2026-08-04; la de 2025 queda desactualizada | No (README y PRD); nuevo ADR de defensa por diseño |
| OWASP Agentic Top 10 2026 | Adoptar (solo filas aplicables, el resto `N/A` con razón) | ASI09 descubre el hueco de la bandeja | No |
| MITRE ATLAS | Diferir (metadato opcional en DS-6) | Versionado mensual; útil, no esencial | No |
| OWASP AI Testing Guide v1 | Diferir | Solo si se usan sus identificadores como nombre de prueba | No |
| NIST AI 600-1 | Rechazar y documentarlo en el ADR | Gobernanza sin controles verificables en este alcance | No |
| Patrones de diseño (Action-Selector, Dual LLM, Context-Minimization, Rule of Two) | Adoptar en el runtime (G1, G2, G4, G10) y en diseño (G3, G7, G8); G5 a evaluar | El diseño ya los aplica en parte; faltan el streaming, los campos extraídos, la bandeja y el renderizado | Sí: **nuevo ADR** o adenda a ADR-011 y ADR-013 |
| CaMeL | Rechazar y documentarlo en el ADR | El grafo ya fija el flujo de control; implementarlo sería curricular | No |
| Spotlighting (delimitación o datamarking) | Adoptar en el runtime, sin venderlo como frontera | Reduce riesgo, es probabilístico; se mide con RT-2 | No |
| Guardas deterministas bilingües del turno | Adoptar en el runtime | Milisegundos; no dependen de detectar ataques adaptativos | No (precisa NFR Design) |
| NeMo Guardrails | Rechazar y documentarlo en el ADR | Segundo orquestador y llamadas extra al LLM | Sí (nuevo ADR) |
| Guardrails AI | Rechazar y documentarlo en el ADR | Comprada por Harvey el 2026-09-09; validadores remotos | Sí (nuevo ADR) |
| LLM Guard | Rechazar y documentarlo en el ADR | Archivado el 2026-07-09; no instala en Python 3.13 | Sí (nuevo ADR) |
| Llama Prompt Guard 2 | Diferir (solo fuera del turno) | Latencia en CPU sin datos; bypass adaptativo > 90 %; licencia Llama 4 | No |
| Llama Guard 4, ShieldGemma, Qwen3Guard, gpt-oss-safeguard | Rechazar y documentarlo en el ADR | Taxonomía de contenido, no de dominio; GPU | Sí (nuevo ADR) |
| Google Model Armor | Rechazar y documentarlo en el ADR | Facturación, datos a terceros, latencia, bypass documentado | Sí (nuevo ADR) |
| promptfoo red team | Adoptar solo en desarrollo/pruebas (por hito) | Reconocible, estrategias adaptativas, presets OWASP; ahora de OpenAI | Sí: adenda a ADR-014 |
| PyRIT, garak, DeepTeam | Rechazar y documentarlo en el ADR | Duplicación: riesgo curricular | Sí: adenda a ADR-014 |
| Umbral del juez: 85 % de acuerdo | Rechazar; reemplazar por TPR y TNR por criterio e idioma con IC | n = 20 da IC [64 %, 95 %]; el acuerdo esconde un TNR bajo | **Sí: ADR-014 y PRD 11.3** |
| Etiquetas por turno, particiones fijas y corrección de tasa | Adoptar solo en desarrollo/pruebas | Muestra suficiente sin grabar más; evita sobreajuste | Sí: ADR-014 |
| pass^k (k = 3) por hito | Adoptar solo en desarrollo/pruebas | Hace medible la inestabilidad | Sí: ADR-014 |
| Segundo juez de otra familia (gpt-oss-120b en Groq gratis) | Adoptar solo para calibración | Mide la autopreferencia; no cabe en CI por límites de TPM | Sí: ADR-014 |
| Runner propio sobre pytest | Adoptar (sin cambios) | La lógica de la compuerta no la expresa ningún framework | No |
| DeepEval | Rechazar como dependencia; juez propio detrás de la interfaz (alternativa mínima: versión exacta y plugin desactivado) | 46 versiones en 2026, v4 reposicionada, 29 dependencias con `posthog` y `pytest-rerunfailures` | **Sí: ADR-014** (y desviación del PRD 11) |
| Inspect AI | Diferir | Reconocible pero duplicaría el runner; 41 dependencias | No (citar como alternativa) |
| Ragas | Rechazar y documentarlo en el ADR | Sin versiones desde 2026-01-13 ni commits desde 2026-02-24 | Sí: ADR-014 (alternativas) |
| Langfuse experiments, Pydantic Evals, Braintrust, LangSmith, OpenAI Evals | Rechazar como compuerta | Requieren servidor, SaaS o duplican | No (ADR-014 ya rechaza SaaS) |
| OTel GenAI semconv | Adoptar en el runtime, versión fijada y contenido solo redactado | Estado Development; repositorio nuevo desde 2026-05-05 | **Sí: ADR-015** (declarar estado y captura) |
| OpenInference, OpenLLMetry | Rechazar y documentarlo en el ADR | Mezcla de convenciones; Traceloop comprada por ServiceNow | Sí: ADR-015 |
| Langfuse autoalojado | Adoptar solo en desarrollo (local) | Colas de anotación reales; 4 núcleos, 16 GiB, 6 servicios; no cabe en CI | **Sí: ADR-015** (justificar frente a Phoenix y resolver enlaces de CI) |
| Exportador OTLP a archivo en CI | Adoptar solo en desarrollo/pruebas | Los enlaces del reporte a Langfuse no resuelven en CI | Sí: ADR-015 |
| Phoenix, Logfire | Diferir (opción del intent `infra`) | Phoenix: Elastic-2.0; Logfire: backend cerrado con tope en 0 USD | Sí: ADR-015 (redactar bien el rechazo) |
| Hypothesis (con estado) | Adoptar solo en desarrollo/pruebas | Reglas, transición, máquina de estados, reconocedores de PII por idioma | Sí: adenda a ADR-002 (pruebas) |
| testcontainers con Postgres real | Adoptar solo en desarrollo/pruebas | RLS solo se prueba en Postgres; `BYPASSRLS` y dueño | Sí: adenda a ADR-002; detalle en ADR-012 |
| Schemathesis | Adoptar solo en desarrollo/pruebas | Contrato OpenAPI y chequeo de cruce entre aseguradoras | Sí: adenda a ADR-002 |
| vcrpy y respx | Adoptar solo en desarrollo/pruebas | Contrato del adaptador e inyección de errores | Sí: adenda a ADR-002 |
| pytest-recording | Diferir | Sin versiones desde 2025-05-08 | No |
| mutmut (4 módulos, por hito) | Adoptar solo en desarrollo/pruebas | Hace cumplir "sin pruebas que siempre pasan" | Sí: adenda a ADR-002 |
| cosmic-ray | Rechazar | mutmut basta | No |
| Playwright con axe | Adoptar (ya aprobado) más prueba de texto plano (G4) | Recorridos críticos acotados | No |
| Regresión visual de Playwright | Diferir | Frágil entre entornos; duplica con temas | No |
| Locust, k6 | Diferir | La meta es latencia por turno desde spans | No |
| Plataformas de evaluación de voz (Hamming, Coval, Cekura) | Rechazar | Cuentas y costo | No |
| gitleaks (primer trabajo de CI) | Adoptar solo en desarrollo/pruebas | Push protection no disponible en privado personal | No (concreta team.md) |
| GitHub secret scanning y push protection | Diferir hasta publicar (semana 12) | Gratis solo en públicos | No |
| trufflehog `--only-verified` | Adoptar una vez antes de publicar | Saber si una clave filtrada sigue viva | No |
| Actions por SHA más política de repositorio | Adoptar solo en desarrollo/pruebas | Trivy 2026 (CVE-2026-33634) | No |
| zizmor | Adoptar solo en desarrollo/pruebas | Auditoría offline barata de workflows | No |
| Dependabot con cooldown; uv `exclude-newer`; pnpm `minimumReleaseAge` | Adoptar solo en desarrollo/pruebas | Ventana de horas de LiteLLM y Trivy | Sí: adenda a ADR-002 (y revisar pnpm 10 frente a 12) |
| Renovate | Rechazar | Dependabot basta | No |
| SBOM CycloneDX sin firma | Adoptar por hito | Alimenta el registro de licencias obligatorio | No |
| OpenSSF Scorecard | Diferir hasta publicar | Requiere GHAS en privado | No |
| Sigstore, cosign, atestaciones | Rechazar (ya rechazado) | No se distribuyen artefactos: riesgo curricular | No |

### ADR que deberían cambiar

- **ADR-014 (evaluación)**:
  - Juez propio por defecto en lugar de DeepEval, registrando la desviación del PRD 11.
  - TPR y TNR por criterio e idioma con IC, en lugar del 85 % de acuerdo (también PRD 11.3).
  - Etiquetas por turno con particiones fijas.
  - pass^k por hito.
  - Segundo juez de otra familia para calibración.
  - Adenda de red-team con una sola herramienta.
  - Ragas e Inspect en alternativas.
- **ADR-015 (telemetría)**:
  - Convenciones en Development con versión fijada.
  - Contenido Opt-In solo tras redacción.
  - Rechazo de Phoenix justificado con trade-offs reales.
  - Trazas de CI como artefacto OTLP.
  - Rechazo de OpenInference y OpenLLMetry.
- **Nuevo ADR (o adenda a ADR-011 y ADR-013)**, "Defensa contra inyección por diseño y
  guardas del turno":
  - Mapeo de patrones y análisis Rule of Two.
  - G1 a G10.
  - Rechazo razonado de las guardas de ML.
- **ADR-002 (herramientas)**: adenda de pruebas (Hypothesis, testcontainers, Schemathesis,
  vcrpy, respx, mutmut) y de cadena de suministro (SHA, zizmor, enfriamiento de versiones).
  Revisar la versión de pnpm (fuera de mi carril).
- **ADR-012**: sin cambio de decisión; añadir en NFR Design `FORCE ROW LEVEL SECURITY` o rol
  no dueño, y tenant con alcance de transacción.

---

## No verificado o con fuente solo secundaria

- Latencia en CPU de Llama Prompt Guard 2; mis cifras son estimaciones.
- Precio de Model Armor y si exige facturación (fuente secundaria).
- Límites del plan gratuito de Gemini para `gemini-3.1-flash-lite` (la documentación
  oficial remite a AI Studio).
- Si promptfoo envía las respuestas del objetivo al servicio remoto en estrategias
  multi-turno.
- Comportamiento del plan Hobby de Langfuse al superar las 50 mil unidades.
- Cifras de recall de Betterleaks (del proveedor).
- Disponibilidad de push protection en privados de cuenta personal (fuentes secundarias y
  discusión de la comunidad; coherente con la página de producto de GitHub).
- Adquisición de Traceloop por ServiceNow (prensa y mención en el newsroom de ServiceNow, sin
  comunicado dedicado leído).
- Licencia actual de NeMo Guardrails (la API de GitHub devuelve `NOASSERTION`).
- Sesgos de posición y verbosidad de Zheng et al. (referencia conocida, no re-leída en esta
  sesión).
- OWASP Agent Control Standard v0.1 (solo nota de CSA).
- Si la instrumentación contrib de google-genai permite apagar la captura de contenido.

---

## Fuentes

Consultadas el 2026-09-17. Las versiones de paquetes marcadas [PyPI], [npm] o [GitHub API]
salen de `https://pypi.org/pypi/<paquete>/json`, `https://registry.npmjs.org/<paquete>` y
`https://api.github.com/repos/<repo>` consultadas ese día.

- [S1] OWASP GenAI Security Project, repositorio GenAI-LLM-Top10 (edición 2026 publicada el 2026-08-04). https://github.com/GenAI-Security-Project/GenAI-LLM-Top10
- [S2] OWASP, "OWASP GenAI LLM Top 10 2026" (2026-08-03). https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/
- [S3] Help Net Security, "OWASP 2026 LLM Top 10: The model will be fooled" (2026-08-06). https://www.helpnetsecurity.com/2026/08/06/owasp-2026-llm-top-10-released/
- [S4] Cloud Security Alliance Labs, "OWASP's 2026 LLM Top 10 and New Agent Control Standard" (2026-09). https://labs.cloudsecurityalliance.org/research/csa-research-note-owasp-genai-top10-2026-agent-control-stand/
- [S5] OWASP, "OWASP Top 10 for Agentic Applications for 2026" (2025-12-09). https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- [S6] DeepTeam docs, lista ASI01-ASI10 (consultado el 2026-09-17). https://www.trydeepteam.com/docs/frameworks-owasp-top-10-for-agentic-applications
- [S7] OWASP AI Testing Guide v1 (2025-11-26). https://owasp.org/www-project-ai-testing-guide/
- [S8] NIST AI 600-1 (2024-07-26). https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- [S9] NIST AI RMF (consultado el 2026-09-17). https://www.nist.gov/itl/ai-risk-management-framework
- [S10] MITRE ATLAS data releases, v2026.09 (2026-09-15). https://github.com/mitre-atlas/atlas-data/releases
- [S11] Beurer-Kellner et al., "Design Patterns for Securing LLM Agents against Prompt Injections", arXiv 2506.08837v2 (2025-06-11). https://arxiv.org/abs/2506.08837
- [S12] S. Willison, resumen del artículo (2025-06-13). https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/
- [S13] Debenedetti et al., "Defeating Prompt Injections by Design" (CaMeL), arXiv 2503.18813 (2025-03; v2 del 2025-06-24). https://arxiv.org/abs/2503.18813
- [S14] Hines et al., "Defending Against Indirect Prompt Injection Attacks With Spotlighting", arXiv 2403.14720 (2024-03-20). https://arxiv.org/abs/2403.14720
- [S15] "The Attacker Moves Second: Stronger Adaptive Attacks Bypass Defenses Against LLM Jailbreaks and Prompt Injections", arXiv 2510.09023 (2025-10-10). https://arxiv.org/abs/2510.09023
- [S16] Meta AI, "Agents Rule of Two: A Practical Approach to AI Agent Security" (2025-10-31). https://ai.meta.com/blog/practical-ai-agent-security/
- [S17] Narisetty et al., "Adaptive Evaluation of Out-of-Band Defenses Against Prompt Injection in LLM Agents", arXiv 2606.26479 (2026-06-25). https://arxiv.org/abs/2606.26479
- [S18] NVIDIA NeMo Guardrails releases (0.22 del 2026-05-22 al 0.24.1 del 2026-09-16, fechas de PyPI). https://github.com/NVIDIA-NeMo/Guardrails/releases
- [S19] PyPI nemoguardrails. https://pypi.org/project/nemoguardrails/
- [S20] Harvey, "Guardrails AI Joins Harvey" (2026-09-09). https://www.harvey.ai/blog/guardrails-ai-joins-harvey
- [S21] Unite.AI, "Harvey Acquires Guardrails AI" (2026-09). https://www.unite.ai/harvey-acquires-guardrails-ai-its-fourth-acquisition-of-2026/
- [S22] protectai/llm-guard, archivado (2026-07-09). https://github.com/protectai/llm-guard
- [S23] Hugging Face, meta-llama/Llama-Prompt-Guard-2-86M (licencia Llama 4, 2025-04). https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M
- [S24] PurpleLlama, tarjeta de Prompt Guard 2 86M. https://github.com/meta-llama/PurpleLlama/blob/main/Llama-Prompt-Guard-2/86M/MODEL_CARD.md
- [S25] Groq, rate limits (consultado el 2026-09-17). https://console.groq.com/docs/rate-limits
- [S26] "Benchmarking Open-Source Safety Guard Models", arXiv 2605.28830 (2026-05, taller de ICLR 2026). https://arxiv.org/html/2605.28830v1
- [S27] Artificial Analysis, "Benchmarking guardrail models" (2026-06-11). https://artificialanalysis.ai/articles/guardrail-safety-benchmark
- [S28] Google Cloud, Model Armor overview (consultado el 2026-09-17). https://docs.cloud.google.com/model-armor/overview
- [S29] promptinjectioncost.com, precio de Model Armor (sin fecha; secundaria). https://promptinjectioncost.com/model-armor-pricing
- [S30] OpenAI, "OpenAI to acquire Promptfoo" (2026-03-09). https://openai.com/index/openai-to-acquire-promptfoo/
- [S31] Promptfoo, "Promptfoo is joining OpenAI" (2026-03-09). https://www.promptfoo.dev/blog/promptfoo-joining-openai/
- [S32] Promptfoo, configuración de red team (consultado el 2026-09-17). https://www.promptfoo.dev/docs/red-team/configuration/
- [S33] Promptfoo, telemetría (consultado el 2026-09-17). https://www.promptfoo.dev/docs/configuration/telemetry/
- [S34] Microsoft PyRIT (1.1.0 del 2026-09-04 en PyPI). https://github.com/microsoft/PyRIT
- [S35] NVIDIA garak (0.17.0 del 2026-09-09 en PyPI). https://github.com/NVIDIA/garak
- [S36] DeepTeam, getting started (consultado el 2026-09-17). https://www.trydeepteam.com/docs/getting-started
- [S37] H. Husain y S. Shankar, "AI Evals: Everything You Need to Know" (actualizado el 2026-09-13). https://hamel.dev/blog/posts/evals-faq/
- [S38] H. Husain, "Using LLM-as-a-Judge For Evaluation: A Complete Guide". https://hamel.dev/blog/posts/llm-judge/
- [S39] ai-evals-course/judgy. https://github.com/ai-evals-course/judgy
- [S40] Shankar et al., "Who Validates the Validators?", arXiv 2404.12272 (2024-04-18), UIST 2024. https://arxiv.org/abs/2404.12272
- [S41] Panickssery, Bowman y Feng, "LLM Evaluators Recognize and Favor Their Own Generations", arXiv 2404.13076 (2024-04-15). https://arxiv.org/abs/2404.13076
- [S42] Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena", arXiv 2306.05685 (2023-06; no re-leído en esta sesión). https://arxiv.org/abs/2306.05685
- [S43] Hada et al., "Are Large Language Model-based Evaluators the Solution to Scaling Up Multilingual Evaluation?", Findings of EACL 2024 (2024-03). https://aclanthology.org/2024.findings-eacl.71/
- [S44] H. Husain, "Can I use the same model for both the main task and evaluation?" (2025-05-28, modificado el 2025-09-22). https://hamel.dev/blog/posts/evals-faq/can-i-use-the-same-model-for-both-the-main-task-and-evaluation.html
- [S45] Yao et al., "τ-bench", arXiv 2406.12045 (2024-06-17). https://arxiv.org/abs/2406.12045
- [S46] Inspect AI, referencia de `inspect_ai.scorer` (`pass_k`, `krippendorff_alpha`; consultado el 2026-09-17). https://inspect.aisi.org.uk/reference/inspect_ai.scorer.html
- [S47] Google AI for Developers, Gemini API rate limits (actualizado el 2026-09-02). https://ai.google.dev/gemini-api/docs/rate-limits
- [S48] DeepEval, "Introducing DeepEval 4.0" (2026; 4.0 en PyPI el 2026-05-08). https://deepeval.com/blog/introducing-deepeval-4
- [S49] DeepEval, data privacy y telemetría (consultado el 2026-09-17). https://deepeval.com/docs/data-privacy
- [S50] Inspect AI (UK AISI), documentación. https://inspect.aisi.org.uk/
- [S51] Langfuse, "Open Sourcing all Product Features" (2025-06-04). https://langfuse.com/changelog/2025-06-04-open-sourcing-langfuse
- [S52] Langfuse, experiments via SDK (consultado el 2026-09-17). https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk
- [S53] Pydantic Evals docs (consultado el 2026-09-17). https://pydantic.dev/docs/ai/evals/evals/
- [S54] open-telemetry/semantic-conventions-genai, docs/gen-ai/README.md (Status: Development; repositorio creado el 2026-05-05). https://github.com/open-telemetry/semantic-conventions-genai
- [S55] OpenTelemetry, página GenAI con aviso de traslado (consultado el 2026-09-17). https://opentelemetry.io/docs/specs/semconv/gen-ai/
- [S56] Calcalist CTech, "ServiceNow buys Traceloop" (2026-03). https://www.calcalistech.com/ctechnews/article/sjghwiqf11e
- [S57] ServiceNow Newsroom, ampliación de AI Control Tower con Traceloop (2026). https://newsroom.servicenow.com/press-releases/details/2026/ServiceNow-expands-AI-Control-Tower-to-discover-observe-govern-secure-and-measure-AI-deployed-across-any-system-in-the-enterprise/default.aspx
- [S58] ClickHouse, "ClickHouse welcomes Langfuse" (2026-01-16). https://clickhouse.com/blog/clickhouse-acquires-langfuse-open-source-llm-observability
- [S59] Langfuse, self-hosting (v4; consultado el 2026-09-17). https://langfuse.com/self-hosting
- [S60] Langfuse, docker compose (consultado el 2026-09-17). https://langfuse.com/self-hosting/deployment/docker-compose
- [S61] Langfuse, OpenTelemetry integration y migración de APIs. https://langfuse.com/integrations/native/opentelemetry
- [S62] Langfuse, pricing (consultado el 2026-09-17). https://langfuse.com/pricing
- [S63] Arize Phoenix, self-hosting (consultado el 2026-09-17). https://arize.com/docs/phoenix/self-hosting
- [S64] Arize Phoenix, arquitectura. https://arize.com/docs/phoenix/self-hosting/architecture
- [S65] Pydantic, pricing de Logfire (consultado el 2026-09-17). https://pydantic.dev/pricing
- [S66] GitHub Docs, GitHub-hosted runners (consultado el 2026-09-17). https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- [S67] GitHub Docs, facturación de Actions (consultado el 2026-09-17). https://docs.github.com/en/billing/concepts/product-billing/github-actions
- [S68] Playwright, best practices. https://playwright.dev/docs/best-practices
- [S69] Playwright, visual comparisons. https://playwright.dev/docs/test-snapshots
- [S70] Schemathesis docs (4.x). https://schemathesis.readthedocs.io/en/stable/
- [S71] Schemathesis, testing Python apps (ASGI). https://schemathesis.readthedocs.io/en/stable/guides/python-apps/
- [S72] Hypothesis, stateful testing. https://hypothesis.readthedocs.io/en/latest/stateful.html
- [S73] boxed/mutmut README (3.8.0 del 2026-09-12 en PyPI). https://github.com/boxed/mutmut
- [S74] PostgreSQL 18, Row Security Policies. https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- [S75] LiveKit, Testing and evaluation (consultado el 2026-09-17). https://docs.livekit.io/agents/start/testing/
- [S76] Aqua Security, GHSA-69fq-xp46-6x23 / CVE-2026-33634 (2026-03-19 al 23). https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23
- [S77] LiteLLM, "Security Update: Suspected Supply Chain Incident" (2026-03). https://docs.litellm.ai/blog/security-update-march-2026
- [S78] Datadog Security Labs, "LiteLLM and Telnyx compromised on PyPI" (2026-03). https://securitylabs.datadoghq.com/articles/litellm-compromised-pypi-teampcp-supply-chain-campaign/
- [S79] GitHub Changelog, "GitHub Actions policy now supports blocking and SHA pinning actions" (2025-08-15). https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/
- [S80] zizmor, audits. https://docs.zizmor.sh/audits/
- [S81] GitHub Docs, push protection. https://docs.github.com/en/code-security/concepts/secret-security/push-protection
- [S82] GitHub, Secret Protection (producto). https://github.com/security/advanced-security/secret-protection
- [S83] GitHub Community Discussion #197712, "Push Protection for Private Repos". https://github.com/orgs/community/discussions/197712
- [S84] gitleaks/gitleaks-action (licenciamiento). https://github.com/gitleaks/gitleaks-action
- [S85] Help Net Security, "Betterleaks: Open-source secrets scanner" (2026-03-19). https://www.helpnetsecurity.com/2026/03/19/betterleaks-open-source-secrets-scanner/
- [S86] GitHub Docs, Dependabot options reference (`cooldown`). https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference
- [S87] uv, settings (`exclude-newer`). https://docs.astral.sh/uv/reference/settings/
- [S88] pnpm, dependency resolution settings (`minimumReleaseAge`). https://pnpm.io/settings/dependency-resolution
- [S89] ossf/scorecard-action README. https://github.com/ossf/scorecard-action
- [S90] GitHub Docs, artifact attestations. https://docs.github.com/en/actions/concepts/security/artifact-attestations
