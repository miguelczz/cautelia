# De la Idea al Product Vision Board para Productos Agénticos

## Documento Base para Presentación

---

# SECCIÓN 1: EL NUEVO PARADIGMA

## Tiempo estimado: 10 minutos

---

## 1.1 Por qué AI es Diferente a Cualquier Ola Tecnológica Anterior

### El Cambio de Paradigma

AI no es simplemente otra tecnología que puedes "agregar" a tu producto. Es un cambio fundamental en cómo se construyen, escalan y monetizan los productos de software.

**Las reglas del juego han cambiado:**

| Aspecto                     | SaaS Tradicional | Productos AI                                   |
| --------------------------- | ---------------- | ---------------------------------------------- |
| Costo marginal por usuario  | Casi cero        | Real y significativo (tokens, GPU, inferencia) |
| Tiempo para copiar features | Meses a años     | Semanas                                        |
| Márgenes brutos típicos     | 70-90%           | 20-60%                                         |
| Ventana de oportunidad      | Años             | Quarters                                       |
| Comportamiento del producto | Determinístico   | Probabilístico                                 |

### La Compresión del Tiempo

En la era SaaS:

- Salesforce tomó años en dominar CRM
- Atlassian escaló Jira en una década
- Zoom tardó media década en volverse mainstream

En la era AI:

- ChatGPT alcanzó 100M usuarios en 2 meses
- Si esperas 6 meses para distribuir, tu competidor ya clonó tu feature
- Las ventanas de distribución se miden en quarters, no años

### Casos de Estudio: El Costo de Equivocarse

**Chegg: El que no actuó**

- Perdió 90% de su valuación en 9 meses
- Mientras estudiantes migraban a ChatGPT para ayuda instantánea y personalizada
- Chegg dudó, reaccionó tarde, y el mercado los castigó brutalmente

**Jasper: El wrapper sin moat**

- Levantó $125M a valuación de $1.2B
- Se posicionó como "AI writing tool"
- Sin moat real y con pricing estilo SaaS que no alineaba con costos de inferencia
- Cuando ChatGPT ganó adopción, los usuarios churnearon masivamente
- Ya no es el favorito de la categoría

**Duolingo: El que ejecutó mal**

- Empujó tutores AI y despidió staff
- La implementación se sintió forzada y extractiva
- Resultado: daño reputacional, cientos de miles de usuarios en churn, 300,000 seguidores perdidos en semanas

**La lección:** No es sobre SI usar AI, es sobre CÓMO construir una estrategia que sobreviva.

---

## 1.2 LLMs vs Agentes: El Cambio Fundamental

### De Oráculos a Trabajadores

La distinción más importante que deben entender:

**LLM (Large Language Model):**

- Es un "cerebro en un frasco"
- Responde preguntas
- Genera contenido
- Pero no ACTÚA en el mundo

**Agente AI:**

- Es un trabajador autónomo
- Observa, decide, y actúa
- Tiene acceso a herramientas
- Puede completar tareas multi-paso

**Ejemplo concreto:**

- Le preguntas a un LLM: "¿Cuáles son los pasos para reservar un vuelo de SFO a JFK para el próximo martes?"
- Le dices a un Agente: "Resérvame el vuelo directo más barato de SFO a JFK para el próximo martes."

### La Historia de los Agentes: 6 Innovaciones en 24 Meses

**Octubre 2022:**

1. **ReAct Framework** (Google) - El principio Reason → Act → Observe se convirtió en la base de los agentes actuales
2. **Frameworks LLM** - Resolvieron el problema práctico de conectar LLMs al mundo real

**Noviembre 2022:** 3. **ChatGPT** - Catalizó el interés masivo en LLMs

**Marzo 2023:** 4. **GPT-4** - Game changer. Los agentes GPT-3.5 estaban mayormente rotos (loops, errores lógicos, ignoraban instrucciones). GPT-4 podía seguir planes multi-paso complejos sin descarrilarse 5. **AutoGPT** - Se volvió viral, 100,000 GitHub stars en semanas. El mundo se dio cuenta que AI ya no era solo chatbots

**Junio 2023:** 6. **Function Calling** (OpenAI) - Los modelos podían generar JSON estructurado para llamar funciones externas directamente

**Noviembre 2024:** 7. **Model Context Protocol (MCP)** (Anthropic) - El "USB-C para AI". Proveedores de herramientas como Gong o Salesforce integran una vez, y cualquier agente puede usarlas

### Taxonomía de Agentes AI

Hay 4 categorías principales que deben conocer:

**Categoría 1: Consumer Agents (Built-In)**

- Ejemplos: ChatGPT Agent, Claude 4, Grok, Gemini
- Los LLMs más recientes tienen agentes integrados
- Mejores para: tareas rápidas, research, crear contenido (PRDs, docs de estrategia)

**Categoría 2: No-Code Agent Builders**

- Ejemplos: Zapier Agents, Lindy, Relay.app, Make.com, n8n
- Piensen en Zapier pero con un cerebro AI tomando decisiones
- Drag-and-drop workflows, el LLM maneja las partes inteligentes
- Perfectos para: automatizar triage de emails, generar reportes, monitorear competidores

**Categoría 3: Developer-First Platforms**

- Ejemplos: CrewAI, AutoGen, Swarm
- Las herramientas de poder para equipos de ingeniería
- Para construir agentes custom desde cero
- Úsalas cuando: construyes features de agentes para clientes o necesitas integración profunda

**Categoría 4: Specialized Agent Apps**

- Ejemplos: Cursor (coding), Lovable (prototyping), Perplexity (research), Notion AI (writing), Otter.ai (meetings)
- Agentes construidos para un job-to-be-done específico
- No solo automatizan, aumentan capacidades

### Árbol de Decisión para PMs/Founders

```
¿Necesitas algo rápido? → Consumer Agents
¿Quieres automatizar workflows? → No-Code Builders
¿Estás construyendo un feature de producto? → Developer-First
¿Tienes un job-to-be-done específico? → Encuentra una Specialized App
```

---

# SECCIÓN 2: ENCONTRANDO TU "ONLY"

## Tiempo estimado: 15 minutos

---

## 2.1 El AI PMF Paradox

### La Paradoja

Lograr Product-Market Fit en la era AI es simultáneamente MÁS FÁCIL y MÁS DIFÍCIL que nunca.

**Es más fácil porque:**

- AI te ayuda a iterar más rápido
- Puedes entender mejor a los usuarios
- Puedes construir soluciones más personalizadas
- Puedes prototipar en días, no meses
- Puedes analizar patrones de comportamiento que antes requerían ejércitos de analistas

**Es más difícil porque:**

- Las expectativas de los usuarios se dispararon
- Los usuarios comparan CADA producto AI con ChatGPT, sin importar el caso de uso
- El estándar de "suficientemente bueno" nunca ha sido más alto
- El PMF es un objetivo móvil: la definición de "suficientemente inteligente" de tus usuarios cambia cada mes

### Los 3 Breaks del Framework Tradicional de PMF

**1. El Problema Evoluciona Mientras los Usuarios Aprenden**

- Los productos tradicionales resuelven problemas conocidos
- Los productos AI frecuentemente resuelven problemas que los usuarios no sabían que tenían
- O crean workflows completamente nuevos que nunca imaginaron
- Tu hipótesis inicial del problema puede estar completamente equivocada, no porque no entendiste el mercado, sino porque AI desbloqueó un caso de uso más valioso

**2. El Espacio de Soluciones es Infinito**

- En software tradicional, estás limitado por recursos de desarrollo y complejidad técnica
- En AI, las restricciones son diferentes: datos de entrenamiento, capacidades del modelo, prompt engineering
- Tu MVP puede ser increíblemente poderoso en algunas áreas y sorprendentemente limitado en otras
- Esto crea experiencias de usuario impredecibles

**3. Las Expectativas del Usuario se Componen Exponencialmente**

- Una vez que los usuarios experimentan AI que funciona bien en un contexto, lo esperan en todas partes
- Si ChatGPT puede entender requests complejos, ¿por qué no puede tu herramienta AI específica de industria?
- Esto crea una barra constantemente creciente para lo que constituye PMF

---

## 2.2 Opportunity Spotting para Productos AI

### El Error Más Grande

El error más grande que cometen los founders de AI es tomar un workflow existente y ponerle AI encima. Eso no es innovación, es feature augmentation.

El verdadero AI PMF comienza identificando pain points que **SOLO pueden ser resueltos** a través de las capacidades únicas de AI.

### Las 5 Preguntas para Rankear Pain Points (con Lens AI)

**1. Magnitud: ¿Cuántas personas tienen este dolor?**

- Consideración AI: ¿Este dolor existe a través de industrias donde AI podría aplicarse horizontalmente?

**2. Frecuencia: ¿Qué tan seguido experimentan este dolor?**

- Consideración AI: ¿Es este dolor suficientemente frecuente para generar los datos necesarios para que AI aprenda y mejore?

**3. Severidad: ¿Qué tan malo es este dolor?**

- Consideración AI: ¿Este dolor involucra carga cognitiva, reconocimiento de patrones, o toma de decisiones donde AI sobresale?

**4. Competencia: ¿Quién más está resolviendo este dolor?**

- Consideración AI: ¿Las soluciones actuales están limitadas por restricciones humanas que AI podría trascender?

**5. Contraste: ¿Hay una gran queja contra cómo la competencia resuelve este dolor?**

- Consideración AI: ¿Los usuarios se quejan de falta de personalización, velocidad, o inteligencia en soluciones existentes?

### Identificando "Invisible Pain Points"

Los mejores oportunidades de AI frecuentemente parecen problemas que no deberían necesitar resolverse. Los usuarios han desarrollado workarounds complejos para limitaciones que AI puede eliminar completamente.

**Ejemplo: Klarna AI Assistant**

- No empezaron tratando de "mejorar servicio al cliente con AI"
- Identificaron un pain point invisible: clientes esperaban 11 minutos promedio para issues de pago simples que no requerían creatividad humana, solo acceso a información de cuenta y procedimientos estándar
- Su AI assistant ahora resuelve encargos en menos de 2 minutos
- Maneja 2.3 millones de conversaciones mensuales con la efectividad de 700 agentes full-time
- Eso es AI-native opportunity spotting: encontrar workflows que solo parecen complejos porque carecen de automatización inteligente

### El Test de Durabilidad: ¿Tu Problema Sobrevive a GPT-5?

Antes de comprometerte con cualquier problema, pregunta:

**"¿Este problema seguirá existiendo después de las próximas 2-3 actualizaciones de modelos foundation?"**

**Ejemplos de problemas NO durables:**

- "AI text summarizer" - buena idea en 2021, trivial dentro de ChatGPT para 2023
- "AI grammar fixer" - commoditizado a feature gratuita
- "AI meeting transcription" - múltiples soluciones gratuitas

**Ejemplos de problemas durables:**

- Problemas de WORKFLOW, no de OUTPUT
- Problemas de INTEGRACIÓN, no de GENERACIÓN
- Problemas de CONTEXTO específico de industria
- Ejemplo: "Ayudar a doctores a tomar decisiones de facturación en compliance con reglas de seguro"

### El Discovery Debt Log

La mayoría de equipos trackean backlog de producto, pero muy pocos trackean las ASUNCIONES debajo de su estrategia.

**Cómo usarlo:**

| Campo              | Descripción                                                                                                   |
| ------------------ | ------------------------------------------------------------------------------------------------------------- |
| Hypothesis Capture | Escribe el claim exacto en el que estás apostando. Ej: "Legal teams pagarán $200/seat por AI contract review" |
| Evidence Strength  | Weak (feedback anecdótico), Medium (piloto con usuarios pagando), Strong (data de retención)                  |
| Validation Method  | ¿Cómo se validó? Entrevistas, shadowing, surveys, logs de uso, data de revenue                                |
| Risk If Wrong      | Low-impact (perdiste una semana) o Existential (tu startup muere)                                             |
| Owner              | Quién es responsable de re-validar periódicamente                                                             |
| Recheck Date       | Las asunciones decaen. Cada item necesita fecha de re-interrogación                                           |

---

## 2.3 Las 3 Trampas Mortales

### Trampa 1: The Red Ocean Trap (La Pelea que No Puedes Ganar)

AI no está creando vastos mercados nuevos de la noche a la mañana. Mayormente está amplificando competencia en mercados existentes.

Los startups están entrando en estos océanos rojos con wrappers AI cleveres, solo para ser aplastados cuando líderes como Microsoft o Adobe replican su feature y lo envían a millones en una sola actualización.

**Caso de estudio: Kite**

- Pionero en AI code completion
- Fue cabeza a cabeza contra GitHub Copilot
- Microsoft tenía mejor data, distribución, y economics
- Kite no tenía oportunidad. Murieron.

**La lección:** No puedes superar a un gigante en puñetazos. Tienes que superarlos en pensamiento.

### Trampa 2: The "Cool Demo" Trap (La Ilusión de Progreso)

Generative AI hace peligrosamente fácil shipear demos mágicas. Unas pocas llamadas API y tienes un feature que parece el futuro.

Pero la mayoría mueren en el "último 20%": el gap entre un demo cool y un producto confiable y valioso.

**El patrón:**

- El output es 80% bueno
- Pero ese 20% faltante lo hace inutilizable a escala
- Los usuarios lo abandonan después de que la novedad se desvanece

**Caso de estudio: Jasper AI**

- Construyeron una de las herramientas AI de marketing más hot
- Levantaron $100M+
- Su core value se commoditizó cuando OpenAI lanzó ChatGPT con capacidades similares

### Trampa 3: The Platform Trap (Construyendo sobre Arena Movediza)

AI ha creado un gold rush de "wrappers": productos delgados construidos sobre APIs de modelos foundation como GPT-4, Claude, Gemini.

Lanzan rápido, se sienten mágicos, y levantan capital rápidamente. Pero la mayoría están construyendo sobre terreno inestable sin saberlo.

**La realidad brutal:**

- Las mismas plataformas que potencian tu producto son también tus mayores competidores
- Tu diferenciación se evapora overnight: una sola actualización de API puede replicar 80% del valor de tu producto
- Estás expuesto a platform risk: cuando OpenAI ajustó pricing y rate limits, docenas de startups AI vieron sus unit economics implosionar en un solo quarter
- No eres dueño de tu moat: si todo lo que has construido es una capa delgada de UX sobre el modelo de otro y data pública, no estás construyendo un producto. Estás corriendo un experimento en tierra rentada.

---

# SECCIÓN 3: EL MOAT ES LA ESTRATEGIA

## Tiempo estimado: 15 minutos

---

## 3.1 Features vs Moats

### La Verdad Brutal

**Features son temporales. Moats son permanentes.**

El mercado no te recompensa por construir un wrapper clever alrededor de GPT-5, porque alguien más puede construir el mismo wrapper mañana.

Lo que el mercado recompensa es si tu producto **se vuelve más fuerte cada vez que un nuevo usuario se registra.**

### Los 3 Moats que Realmente Importan en AI

**1. Data Moat (El más durable y defensible)**

Si tu producto genera datos únicos, defensibles y estructurados cada vez que se usa, con cada usuario adicional estás tirando más adelante de una manera que los competidores no pueden copiar ni comprar.

_Ejemplo: Duolingo_

- No solo agregaron AI y lo llamaron un día
- Fine-tunearon sus modelos con años de datos propietarios de aprendizaje de estudiantes
- Qué ejercicios causaban dificultades, qué correcciones funcionaban, cómo evolucionaban los paths de aprendizaje a través de geografías y demografías
- Ese dataset es un tesoro que ningún nuevo entrante puede replicar, sin importar cuánto capital levante

_Por qué importa:_ Los data moats se componen. Cada nuevo usuario → más data única → modelos más inteligentes, baratos, personalizados → mejor UX → más usuarios. Eso es un flywheel.

**2. Distribution Moat**

La distribución siempre ha sido un moat en negocios, pero en AI es TODO.

_Ejemplo: Notion_

- Cuando agregaron AI, no necesitaron gastar millones en adquisición de clientes
- Ya tenían decenas de millones de usuarios embebidos en workflows
- Prender el switch creó adopción instantánea a escala

_Ejemplo: Canva_

- No trataron de marketear "AI image generation" como un gimmick separado
- Lo embebieron directamente en el proceso de diseño donde los usuarios ya vivían
- Se siente como extensión natural del producto

_Por qué importa:_ Si no eres dueño de la distribución, estás peleando por migajas contra ChatGPT, Gemini, o cualquier modelo foundation que lance después.

**3. Trust Moat (El más subestimado)**

Los usuarios no solo quieren AI poderoso; quieren AI predecible, seguro y confiable. En muchas industrias, trust no es opcional — es toda la propuesta de valor.

_Ejemplo: Anthropic_

- No trataron de vencer a OpenAI en escala raw o conteo de parámetros
- Se posicionaron como la compañía obsesionada con safety y alignment
- Esa única decisión de posicionamiento les ganó clientes enterprise que no podían permitirse el riesgo reputacional de deployar modelos no-alineados

_Ejemplo: Los deals enterprise de OpenAI_

- Muchas compañías técnicamente podrían hacer sus propios modelos o comprar alternativas más baratas
- Pero pagan millones a OpenAI porque trust en governance, compliance, y reliability es más valioso que los weights del modelo

_Por qué importa:_ Trust se compone lentamente, pero una vez ganado, se convierte en un moat más fuerte que features. Una sola alucinación o breach puede romperlo, pero reliability consistente crea lock-in que los competidores no pueden disruptar con un modelo ligeramente más rápido o barato.

---

## 3.2 The AI Strategic Lens Framework

### Visión General

El framework AI Strategic Lens es un modelo de 3 pasos que te fuerza a hacer las preguntas correctas en el orden correcto, moviéndote desde el landscape de mercado amplio hasta los específicos de tu ejecución.

### Lens 1: The Market Lens (Dónde Jugar)

El primer lens te fuerza a mirar hacia afuera. Antes de enamorarte de tu solución, debes entender la arena competitiva.

**Principio 1: Identifica Tu Arena**

Cada producto AI compite en una de tres arenas. Tu estrategia cambia dramáticamente dependiendo de cuál estés:

| Arena                        | Descripción                                                                                  | Desafío Principal                                  | Ejemplo                                                  |
| ---------------------------- | -------------------------------------------------------------------------------------------- | -------------------------------------------------- | -------------------------------------------------------- |
| **Pioneer (AI-Native)**      | Estás creando un mercado completamente nuevo que no podría existir antes de AI               | Creación de categoría                              | Cognition's Devin (el ingeniero de software AI autónomo) |
| **Disruptor (AI-Disrupted)** | Estás usando AI para reimaginar fundamentalmente un workflow existente, haciéndolo 10x mejor | Atacar mercado establecido con nueva arma          | Descript (edita video editando texto)                    |
| **Enhancer (AI-Enhanced)**   | Eres un incumbent aprovechando AI para fortalecer un producto existente                      | Fortifica market share, defiende contra disruptors | Adobe integrando Firefly en Photoshop                    |

**Principio 2: Sobrevive a los Gigantes**

No puedes superar a un gigante en puñetazos. Debes superarlos en pensamiento. Competir cabeza a cabeza es una misión suicida.

_Historia de precaución: Kite_

- Pionero en AI code completion
- Fue cabeza a cabeza con GitHub Copilot de Microsoft
- Perdieron. Badly. Microsoft tenía data superior, distribución, y capacidad de subsidiar el producto.

_Historia de éxito: CodiumAI_

- Eligieron un path diferente
- En lugar de competir con Copilot en code generation, se enfocaron en el trabajo tedioso alrededor: escribir tests y documentación
- Encontraron un nicho complementario y prosperaron, levantando $65 millones

**Pregunta del Lens para tu equipo:** ¿Nuestra estrategia nos posiciona como Pioneer, Disruptor, o Enhancer? ¿Estamos peleando con un gigante cabeza a cabeza o complementándolo?

### Lens 2: The Value Lens (Cómo Ganar)

Una vez que sabes dónde jugar, el Value Lens enfoca hacia adentro en cómo ganar.

**Principio 1: Deja de Espolvear "AI Fairy Dust"**

Demasiados equipos simplemente "espolvorean AI" sobre workflows viejos y esperan magia. Este es el camino más rápido a la mediocridad.

_Ejemplo de "Fairy Dust": Google AI Overviews_

- Es un feature AI atornillado a la página de resultados de búsqueda existente
- Útil a veces, pero no cambia el paradigma core de filtrar links

_Ejemplo de Experiencia Reimaginada: Perplexity_

- Empezaron desde cero y preguntaron: "¿Cómo debería verse search en un mundo AI-first?"
- El resultado es un "answer engine" conversacional que provee respuestas directas y citadas
- Es un nuevo workflow, no solo un nuevo feature

**Principio 2: Construye Tu Moat con Data que Posees**

Si tu producto AI está construido enteramente sobre una API pública como GPT-4 y entrenado con data pública, no tienes moat. Tu ventaja competitiva es cero.

Tu única defensa verdadera y durable es aprovechar data propietaria y workflows que tus competidores no pueden acceder.

_La regla es simple:_ La data más valiosa es específica del usuario y generada a través de tu workflow único.

_Ejemplo: Spotify_

- Su moat no es su librería de 100 millones de canciones (que es pública)
- Su moat es TU historial de escucha personal — cada canción que has skipped, saved, o agregado a playlist
- Esta data propietaria permite que su AI cree un Discover Weekly que se siente como magia y que ningún competidor puede replicar

**Pregunta del Lens para tu equipo:** ¿Cuál es nuestro moat defensible? ¿Está basado en workflow único y data propietaria, o solo un uso clever de una API pública?

### Lens 3: The Execution Lens (Cómo Entregar)

Una estrategia brillante es inútil si no puedes entregarla.

**Principio 1: Domina el AI Decision Triangle**

Cada feature AI fuerza un trade-off entre tres cosas: **Cost, Capability, y Speed.**

No puedes maximizar las tres. Una forma simple de pensarlo: "Puedes tener el modelo más inteligente, el más rápido, o el más barato. Elige uno."

Tu trabajo como líder de producto es decidir cuál importa más para tu caso de uso.

| Optimizado para | Ejemplo                        | Por qué funciona                                                                                                                                       |
| --------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Speed           | GitHub Copilot autocomplete    | Sugiere código en milisegundos. No siempre el más brillante, pero es lo que developers necesitan en su flow                                            |
| Capability      | Harvey (legal AI)              | Necesita proveer análisis de contratos altamente preciso y matizado. Puede tomar más tiempo y costar más, pero usuarios valoran correctness sobre todo |
| Cost            | Routing layers, classification | Tareas que no necesitan el modelo más caro                                                                                                             |

**Principio 2: Planea para Fallas Silenciosas**

A diferencia del software viejo que crashea con un error 404, el software AI falla silenciosamente. No se rompe; solo se pone quietly worse. Esto se llama "model drift."

El AI fue entrenado en un snapshot del mundo, pero el mundo sigue cambiando. Con el tiempo, sus recomendaciones se vuelven menos relevantes, sus predicciones menos precisas.

**Ten en cuenta:**

- Los usuarios raramente reportan esto. Simplemente dejan de usar tu producto.
- Esto hace que el monitoreo continuo sea una función de negocio no-negociable
- Necesitas sistemas para evaluar constantemente la calidad de los outputs de tu AI para atrapar estas fallas silenciosas antes de que tus clientes lo hagan

**Pregunta del Lens para tu equipo:** ¿Cómo estamos balanceando el triángulo Cost-Capability-Speed para nuestro core feature? ¿Y qué sistemas tenemos para detectar fallas silenciosas?

---

## 3.3 Casos Reales de Moats Exitosos

### Caso 1: Perplexity - Trust Moat via Citations

**El problema que identificaron:**

- Search tradicional te da links
- Tienes que hacer click, leer, evaluar, sintetizar
- LLMs pueden responder pero alucinan sin verificación

**Su wedge único:**

- Retrieval-first workflow
- Citations y fuentes visibles
- Trust loops: cada respuesta viene con referencias verificables

**Su distribución:**

- Los outputs eran tan útiles que la gente los compartía en X, Reddit, TikTok
- Cada vez que alguien posteaba una respuesta de Perplexity, adquirían nuevos usuarios gratis
- Viral artifacts como estrategia de distribución

### Caso 2: Clay - Category Creation Moat

**Lo que hicieron diferente:**

- No solo construyeron una herramienta de CRM enrichment
- INVENTARON UN ROL: "GTM Engineer"
- Escribieron el handbook, definieron la identidad del operador

**Por qué funciona:**

- Cuando defines el rol, también defines el toolset
- Cada startup que contrata un GTM Engineer lista Clay como el sistema operativo obvio
- Eso no es suerte — es distribución a través de category creation

**Distribución en capas:**

- Partners con databases de influencers como Modash
- Agencies como Influencer Club
- Comunidad (Slack, Claybooks visibles, playbooks)
- Los prospectos no necesitan un sales deck — pueden ver el schema exacto y API calls que otros usan

### Caso 3: Harvey - Prestige Moat

**La estrategia contraintuitiva:**

- La mayoría de startups tratan de escalar bottom-up
- Harvey fue directo al top
- Partnered con Allen & Overy (ahora A&O Shearman), uno de los law firms más grandes del mundo

**Lo que lograron:**

- No solo consiguieron un cliente — co-construyeron ContractMatrix, una herramienta AI respaldada por Microsoft embebida en los workflows diarios del firm
- Credibilidad instantánea

**Por qué funciona en mercados jerárquicos:**

- En law (un mercado jerárquico), la adopción fluye downstream
- Cuando firms pequeños ven a un apex player usando una herramienta, la adoptan por prestigio tanto como por utilidad
- La adopción cascadea downstream del top

### Caso 4: ElevenLabs - Output-as-Distribution Moat

**Su insight:**

- No compraron ads para escalar
- Diseñaron su producto para que los OUTPUTS fueran la distribución

**Cómo funciona:**

- Cuando creators empezaron a usar ElevenLabs para generar voice clones para TikTok, YouTube, podcasts, el producto se esparció orgánicamente
- Cada clip entretenido, cada meme, cada AI-dubbed narration era tanto contenido como marketing

**Amplificación:**

- Optimizaron voces para plataformas short-form
- Incentivaron outputs con watermark bajando costos de créditos
- Creators se convirtieron en el equipo de onboarding — tutoriales en YouTube y X enseñaban a otros cómo usarlo
- Cada power user se convirtió en un nodo de distribución

### Caso 5: Lovable - Vibe-Native Growth Moat

**Su posicionamiento:**

- Podían haberse posicionado como "la forma más rápida de construir apps con AI"
- En cambio, literalmente se adueñaron de un meme cultural: "vibe coding"
- Construyeron su marca alrededor de "anyone can build"

**Por qué funciona:**

- Esa única frase reenmarca coding de algo técnico e intimidante a algo playful, creativo, y aspiracional
- Una vez que "vibe coding" entró en la cultura, la marca empezó a esparcirse casi independientemente de ads

**Proof loops:**

- Sus ads muestran builders diciendo "Construí este proyecto de $6,000 en Lovable para mi cliente"
- Vinculando directamente la herramienta con income
- En TikTok y YouTube, creators postean demos de "construí esto en una hora con Lovable"
- Son tutoriales Y ads no pagados

---

# SECCIÓN 4: LA ECONOMÍA BRUTAL DE AI

## Tiempo estimado: 10 minutos

---

## 4.1 El Costo Marginal NO es Cero

### El Mito de SaaS que Mata Startups AI

En SaaS, una vez que construyes el producto, servir a un usuario extra cuesta centavos — a veces nada. Por eso los márgenes de SaaS son 70-80%.

**AI es diferente.**

Cada vez que un usuario envía un prompt, procesa un documento, o corre un agente, la compañía paga por compute.

| Tipo de Usuario                                   | Costo para la Compañía                                      |
| ------------------------------------------------- | ----------------------------------------------------------- |
| Usuario casual de Claude enviando 10 mensajes/día | Centavos                                                    |
| Developer corriendo Claude Code 8 horas/día       | Decenas de miles de dólares/mes en el plan original de $200 |

### La Tensión Core del Pricing en AI

**Tus mejores usuarios son tus usuarios más caros.**

Esto crea una paradoja que no existe en SaaS:

- Quieres más engagement
- Pero más engagement = más costo
- Si no alineas pricing con uso, cada usuario exitoso te desangra

### Ejemplos Reales del Problema

**GitHub Copilot:** Reportadamente perdía dinero por usuario al launch

**OpenAI:** A $13B+ de revenue, quemó $8 billion en compute en 2025 y proyecta $14 billion en pérdidas acumuladas para fin de 2026

**Replit:** Sus gross margins oscilaron de 36% a -14% negativo en meses mientras su AI agent consumía más recursos LLM de lo que su pricing cubría

**Cursor - El caso del invoice de $7,225:**

- Un tweet obtuvo 797,000 views en una semana
- "We paid $7k yesterday for a yearly subscription. One of our devs just used all 500 requests in a single day. Is that even legal?"
- El CEO tuvo que publicar una disculpa pública
- Ofrecieron refunds a todos los usuarios afectados entre Junio 16 y Julio 4, 2025

---

## 4.2 Los 6 Modelos de Pricing en AI

### Modelo 1: Hybrid Tiered Subscriptions

**Cómo funciona:** Múltiples tiers con límites de uso crecientes, acceso a modelos, y features.

**El modelo dominante de consumer AI**, también el más probable de cambiar en los próximos 12 meses.

**Ejemplos:**

- Claude: Free → Pro $17/mo → Max $100/mo → Max $200/mo
- ChatGPT: Free → Plus $20/mo → Business $30/mo → Pro $200/mo
- Perplexity, Gemini, Grok todos cluster alrededor del mismo $20 entry point

**La parte clever:** Tanto Anthropic como OpenAI deliberadamente evitan publicar límites de uso exactos. Esta opacidad intencional les permite manejar costos de compute dinámicamente sin establecer expectativas duras que se convierten en liabilities.

**Trade-off:** Obtienes flexibilidad de márgenes, pero también usuarios que se sienten "gaslit" cuando tocan un límite que nadie les dijo que existía.

### Modelo 2: Usage-Based / Per-Token

**Cómo funciona:** Paga proporcionalmente al compute consumido.

**El modelo de infraestructura.**

**Ejemplos:**

- Anthropic API: $3 por millón de input tokens, $15 por millón de output tokens para Sonnet 4.5
- Cruzas el threshold de 200K tokens de input y todo el request salta a $6/$22.50, efectivamente duplicando tu costo

**Fortalezas:**

- Cada API call cuesta compute Y genera revenue
- Gross margins se mantienen consistentes sin importar escala

**Debilidades:**

- Nadie quiere una factura sorpresa
- Forums de developers llenos de gente que corrió un batch job y despertó con invoice de 4 cifras
- El moat competitivo es delgado: costos de inference cayeron 78% en 2025. Si un competidor baja su precio per-token, los clientes pueden cambiar con casi cero fricción

**Mejor para:** Cuando tus clientes son developers construyendo sobre tu plataforma. Ellos lo esperan, pueden optimizar para ello, y tienen recursos de ingeniería para monitorearlo.

### Modelo 3: Credit / Token Pools

**Cómo funciona:** Suscripción flat, pero usuarios obtienen un pool de créditos que se depletan a diferentes tasas dependiendo de lo que hacen.

**El modelo causando más drama ahora mismo.**

**Ejemplo: Cursor**

- Su plan Pro te da $20/mes en créditos
- Eso compra aproximadamente 225 Claude Sonnet 4 requests, o 500 GPT-5 requests, o 550 Gemini requests
- Un tab completion simple cuesta fracciones de centavo
- Un multi-file refactor con un modelo caro puede quemar $5 en un prompt

**Antes de Junio 2025:** Cursor cobraba flat 500 requests/mes. Sin sorpresas.

**El switch a credit pools causó una revuelta de developers tan feroz que el CEO publicó disculpa pública el 4 de Julio 2025.**

**Trade-off:** La confianza del usuario. El backlash de la comunidad de Cursor muestra qué pasa cuando conviertes un modelo predecible a uno variable sin sobre-comunicar.

### Modelo 4: Outcome-Based

**Cómo funciona:** Cobra basado en lo que el AI logra, no en el uso.

**El modelo que más emociona a los VCs.**

**Ejemplo: Intercom Fin**

- Cuesta $0.99 por resolución
- Una "resolución" significa que el cliente confirma que la respuesta ayudó, o sale sin pedir asistencia adicional
- Solo pagas cuando Fin resuelve un problema
- Si falla y escala a un humano, no hay cargo

**La matemática a escala:**

- Una compañía manejando 30,000 conversaciones/mes donde Fin resuelve 60%
- Paga $17,820/mes solo en fees de resolución
- Encima de la suscripción seat-based de Intercom
- Un análisis de un setup de 15 agentes puso el gasto mensual total en aproximadamente $32,734

**El contra-argumento de Intercom:** Si Fin resuelve 18,000 conversaciones que habrían requerido agentes humanos a $15-25/hora, el cliente aún sale ganando.

**Por qué la mayoría no puede usarlo:** La infraestructura de medición de outcomes no existe para la mayoría de categorías todavía.

### Modelo 5: Seat-Based + AI Add-On

**Cómo funciona:** El path de "AI upgrade" de menor resistencia para SaaS establecido. Tu producto base cobra per seat, features AI van en tiers premium o add-ons.

**Ejemplos:**

- Notion bundled AI features en planes de precio más alto
- Canva subió pricing de Teams hasta 300%, explícitamente citando expansión de features AI
- GitHub Copilot: $10/month Individual, $19/user/month Business, $39/user/month Enterprise

**Fortalezas:** Operacionalmente simple. Ya tienes billing per-seat y motion de ventas.

**Debilidades:** Tus usuarios de mayor uso son los más caros de servir, y están pagando lo mismo que usuarios ligeros. Esta es la misma dinámica que empujó a Cursor a credit pools y Replit a effort-based pricing.

**Recomendación:** Trata seat-based + AI como un puente, no un destino. Trackea costos de compute per-user desde día uno.

### Modelo 6: Freemium / Reverse Trial

**Cómo funciona:** Regala AI para crear hábito, monetiza a través de upgrades.

**Ejemplos:**

- El tier gratis de ChatGPT de OpenAI sirve a más de 900 millones de usuarios semanales
- Dan GPT-5.2 gratis con límites estrictos, luego convierten a Plus ($20) y Pro ($200)
- En Febrero 2026, empezaron a testear ads para usuarios free y Go tier en USA

**La economía es brutal:** OpenAI quemó $8 billion anualmente en compute en 2025. La mayoría de startups no pueden permitirse esa apuesta.

**Recomendación:** Si tu conversión free-to-paid está bajo 2-3%, tu tier gratis es demasiado generoso. Considera "reverse trial" en su lugar: acceso completo por 14 días, luego downgrade.

---

## 4.3 El Test de 10x

### La Pregunta que Debes Responder

Antes de lanzar cualquier feature AI, modela las economics a 100x escala.

**Si los costos no se doblan hacia abajo, no tienes distribución — tienes un liability.**

### Experimento Mental

Supón que cobras $29/mes por usuario:

- Tu usuario promedio hace 500 queries/mes
- Cada query te cuesta $0.002 en tokens
- Eso es $1.00 en costo de inference raw por usuario/mes
- Gross margin = ~97%. Hermoso.

**Ahora escala:**

- Creces de 1,000 usuarios → 100,000 usuarios
- Queries ballonan de 500,000 → 50 millones/mes
- Costos = $100K/mes → $10M/año en inference

**De repente tu AWS bill se ve pequeño en comparación.**

### La Trampa

Los márgenes se ven bien a 1,000 usuarios. Se desmoronan a 100,000 a menos que:

1. **Batches o cachees inteligentemente** - No re-generes los mismos outputs 50 veces
2. **Uses model routing** - Corre modelos baratos para tareas simples, caros solo cuando sea necesario
3. **Construyas infra propietaria** - Entrena modelos pequeños domain-specific que son más baratos de correr

### El Framework de los 3 Multipliers de Costo

**1. The Compute Multiplier**

- Cada inference call representa una cadena de eventos: prompt construction, encoding, network traversal, inference, decoding, y a veces múltiples tool calls
- Los equipos usualmente optimizan un step (el modelo) mientras ignoran los otros

**2. The Context Multiplier**

- Equipos unknowingly inflan costo cuando incluyen historiales de conversación enteros en lugar de memorias destiladas
- Pegan raw documents en lugar de snippets selectivamente retrieved
- Duplican metadata
- Cada 1,000 tokens adicionales, repetidos a través de millones de calls/mes, se convierte en waste de 6-7 figuras anuales

**3. The Error Multiplier**

- Los errores de AI no solo hieren UX; queman dinero
- Cada alucinación triggerea retries y fallbacks a modelos más caros
- Lo que ultimadamente significa ventanas de contexto más largas para "estabilidad"
- Y trabajo de corrección manual que infla overhead operacional

---

# SECCIÓN 5: CONSTRUYENDO TU PRODUCT VISION BOARD

## Tiempo estimado: 10 minutos

---

## 5.1 El 4D Method

### Overview del Framework

El 4D Method es un framework reimaginado para las realidades de productos AI:

**Discovery → Design → Develop → Deploy**

No puedes confiar en los mismos steps lineares que funcionaron para SaaS. Necesitas una manera de continuamente descubrir verdad, diseñar para trust, engineerear para drift, y deployar con moats.

### Phase 1: DISCOVERY (Truth Hunting)

**Por qué es diferente en AI:**

- El problema superficial que los usuarios describen puede ser real hoy pero desaparecer mañana cuando los modelos foundation expandan capacidades
- Discovery en AI no es un momento snapshot único, sino un proceso de truth hunting a través de landscapes cambiantes

**Las 5 Preguntas Incómodas:**

1. ¿Qué si el problema desaparece en 12 meses por commoditización de modelos?
2. ¿Quién realmente es dueño de la data, y podrían revocar acceso?
3. ¿Los reguladores, aseguradores, u oficiales de riesgo se sentirían avergonzados si nuestro producto fallara públicamente?
4. ¿Puede un competidor replicar este producto con la misma API en menos de 6 semanas?
5. Si tenemos éxito a escala, ¿cuál es la primera forma en que trust se rompe?

**El 3-Lens Discovery Test:**

| Lens       | Pregunta Core                                                                                 | Score 1-5 |
| ---------- | --------------------------------------------------------------------------------------------- | --------- |
| Durability | ¿Este problema seguirá existiendo después de las próximas 2-3 upgrades de modelos foundation? |           |
| Data       | ¿Podemos asegurar pipelines de data exclusivos o defensibles con el tiempo?                   |           |
| Trust      | ¿Quién controla el veto power sobre trust? (puede no ser el end-user)                         |           |

Si tu problema promedia menos de 3.5, no es un problema en el que deberías apostar una compañía.

### Phase 2: DESIGN (System Architecture for Trust)

**Design en AI es más que UX:**

- Se extiende a la arquitectura de cómo el sistema se comporta bajo stress, drift, y abuso
- Una UI puede ser hermosa, pero si el AI produce outputs inseguros, consume tokens impredeciblemente, o establece falsas expectativas sobre reliability, ninguna cantidad de gradientes de color lo salvará

**El trabajo real de AI design es engineerear para trust.**

**El FTCEM Framework:**

| Elemento          | Descripción                                                                                                                                       |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| **F**ailure Mode  | Identifica fallas catastróficas específicas (ej: alucinar advice legal, producir imágenes dañinas, correr un millón de API calls inesperadamente) |
| **T**rigger       | Documenta qué causa esta falla (prompts maliciosos, instrucciones ambiguas, dataset bias)                                                         |
| **C**onsequence   | Lista el daño downstream (pérdida de user trust, liability legal, colapso de infraestructura)                                                     |
| **E**arly Warning | Define qué telemetría o señal UX te alertará (spike en inputs out-of-distribution, tickets de soporte crecientes)                                 |
| **M**itigation    | Pre-define qué harás (shut down gracefully, escalar a human review, degradar funcionalidad)                                                       |

**Los 3 Layers de AI Design:**

1. **Interaction Design (Layer visible):** Prompts, responses, chat interfaces, explicaciones. Donde usuarios forman modelos mentales de "qué puede hacer este AI"

2. **Constraint Design (Layer invisible):** Filtros, monitoreo, paths de escalación, guardrails rule-based que mantienen al AI de volverse rogue

3. **Expectation Design (Meta-layer):** Los cues que das a usuarios antes de que empiecen a usar tu producto. Pricing comunica si es premium copilot o casual helper. Onboarding copy dice qué tan cauteloso o aventurero es el sistema.

### Phase 3: DEVELOP (Engineering for Drift)

**Por qué el desarrollo AI nunca termina:**

- En desarrollo de producto tradicional, la línea de llegada era clara: scoped un feature, lo construiste, QA'd, shipped, y seguiste adelante
- En AI, no hay línea de llegada porque el ambiente en el que vive tu sistema está constantemente shifteando
- Inputs cambian, modelos foundation evolucionan, costos fluctúan con escala, comportamiento de usuarios estira tu sistema a territorios inesperados

**No estás "shipeando features"; estás engineereando resiliencia contra drift.**

**El Drift Management Loop:**

| Tipo de Drift      | Qué es                                                                                   | Cómo Manejarlo                                                                                                |
| ------------------ | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Model Drift**    | Cuando la distribución de inputs se aleja de tu training data                            | Mantén golden dataset de casos representativos, corre regression tests, trackea alertas "out-of-distribution" |
| **Cost Drift**     | Costos de infra rara vez se mantienen constantes                                         | Monitorea costo por outcome exitoso (no solo por API call), establece thresholds de alerta                    |
| **Behavior Drift** | Aunque el modelo sea técnicamente "preciso", su comportamiento puede sutilmente shiftear | Implementa UX regression testing, colecta señales de user trust (NPS, variance de satisfacción)               |

**El Drift Triangle:**

- Performance ↔ Cost ↔ Trust
- Optimizar una esquina frecuentemente stresea las otras
- Maximizar performance agregando context windows más largos incrementa costo dramáticamente
- Reducir costos comprimiendo prompts puede bajar trust si outputs se vuelven unreliable

### Phase 4: DEPLOY (Defending the Moat)

**Por qué Deployment es malentendido:**

- La mayoría de equipos piensan que deployment es sinónimo de "launch"
- Planean un ciclo de prensa, ponen el producto live, y celebran
- En AI, deployment es exactamente lo opuesto de un ending; es el comienzo de tu survival test

**El Day 2 Checklist:**

| Item                           | ¿Está listo?                                                                                    |
| ------------------------------ | ----------------------------------------------------------------------------------------------- |
| Monitoring Dashboards Live     | Watching usage, drift, costs, error rates en real time                                          |
| Compliance Reporting Automated | Para industrias reguladas, pipelines de reporting deben estar live desde Day 2                  |
| Retraining Cadence Defined     | Schedule (weekly, monthly) para retraining o updating modelos                                   |
| Feedback Routing               | Cada ticket, complaint, o output flaggeado capturado y routeado de vuelta al evaluation dataset |
| Billing & Infra Alerts         | Alertas para runaway costs o token spikes                                                       |
| Rollback Protocols Rehearsed   | Saber cómo hacer rollback a safe state en horas si aparece bug catastrófico                     |

**Los 3 Moats del Deployment:**

1. **Distribution Moat:** Dónde lanzas importa más que qué lanzas. Productos que se embeben en workflows se defienden mejor que standalone apps.

2. **Trust Moat:** Usuarios perdonarán errores tempranos si confían en tu proceso. Construir safeguards, explicaciones transparentes, y escalación humana crea un moat que competidores no pueden copiar fácilmente.

3. **Adaptation Moat:** La única certeza en AI es el cambio. Las compañías que sobreviven son las que retrainan, iteran, y shipean más rápido que competidores.

---

## 5.2 Template: AI Product Vision Board

### El Canvas

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AI PRODUCT VISION BOARD                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  PROBLEMA (que persiste post-GPT-5)                                │
│  ________________________________________________________________  │
│  ________________________________________________________________  │
│  ________________________________________________________________  │
│                                                                     │
│  Durability Score (1-5): ___                                       │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  SEGMENTO TARGET                                                    │
│  ________________________________________________________________  │
│                                                                     │
│  ¿Quién controla el veto de confianza?                             │
│  ________________________________________________________________  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  MOAT PRIMARIO                                                      │
│  [ ] Data Moat    [ ] Distribution Moat    [ ] Trust Moat          │
│                                                                     │
│  ¿Qué data/distribución/trust única poseemos o podemos construir? │
│  ________________________________________________________________  │
│  ________________________________________________________________  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ARENA COMPETITIVA                                                  │
│  [ ] Pioneer (AI-Native)                                           │
│  [ ] Disruptor (AI-Disrupted)                                      │
│  [ ] Enhancer (AI-Enhanced)                                        │
│                                                                     │
│  ¿Cómo sobrevivimos/complementamos a los gigantes?                 │
│  ________________________________________________________________  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  UX PARADIGM                                                        │
│  [ ] Assistant (helper embebido)                                   │
│  [ ] Agent (actor autónomo que ejecuta tareas)                     │
│  [ ] Autonomous (fully automated outcomes)                          │
│  [ ] Embedded Intelligence (AI invisible mejorando core workflows) │
│                                                                     │
│  ¿Por qué este paradigma para nuestro caso de uso?                 │
│  ________________________________________________________________  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  AI DECISION TRIANGLE                                               │
│  Optimizamos primariamente para:                                   │
│  [ ] Cost    [ ] Capability    [ ] Speed                           │
│                                                                     │
│  Trade-offs aceptados:                                             │
│  ________________________________________________________________  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  MODELO ECONÓMICO                                                   │
│  Pricing model:                                                     │
│  [ ] Hybrid Tiered    [ ] Usage-Based    [ ] Credit Pools          │
│  [ ] Outcome-Based    [ ] Seat+AI        [ ] Freemium              │
│                                                                     │
│  ¿El pricing escala si tenemos 10x usuarios?                       │
│  [ ] Sí    [ ] No    [ ] Necesita ajuste                           │
│                                                                     │
│  Costo estimado por usuario/mes: $_______                          │
│  Revenue por usuario/mes: $_______                                 │
│  Gross margin proyectado: _______%                                 │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  MÉTRICAS DE ÉXITO                                                  │
│                                                                     │
│  User Metrics:                                                      │
│  1. ____________________________________________                    │
│  2. ____________________________________________                    │
│                                                                     │
│  AI-Specific Metrics:                                               │
│  1. ____________________________________________                    │
│  2. ____________________________________________                    │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  RIESGOS CRÍTICOS                                                   │
│                                                                     │
│  1. ¿Qué si el problema desaparece en 12 meses?                    │
│     Respuesta: ______________________________________________       │
│                                                                     │
│  2. ¿Puede un competidor replicar en 6 semanas?                    │
│     Respuesta: ______________________________________________       │
│                                                                     │
│  3. Si tenemos éxito a escala, ¿cómo se rompe trust primero?       │
│     Respuesta: ______________________________________________       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Guía de Llenado

**PROBLEMA:**

- No escribas "queremos usar AI para X"
- Escribe el dolor específico que resuelves
- Pregúntate: ¿este dolor existirá cuando GPT-5 salga? ¿Y GPT-6?
- Buenos ejemplos: "Doctores pasan 6 horas/semana en billing compliance" (workflow específico)
- Malos ejemplos: "La gente necesita resúmenes de documentos" (commoditizado)

**SEGMENTO TARGET:**

- Sé específico: no "empresas", sino "equipos de legal en startups Series A-B con 2-5 abogados in-house"
- Identifica el VETO HOLDER: ¿quién puede matar la adopción aunque el end-user ame el producto?
    - Puede ser: compliance officer, CFO, regulador, CISO

**MOAT PRIMARIO:**

- Solo puedes elegir UNO como primario
- Data Moat: ¿Qué data única generamos que competidores no pueden comprar?
- Distribution Moat: ¿Dónde estamos embebidos que es difícil de replicar?
- Trust Moat: ¿Qué reliability/safety/compliance ofrecemos que otros no pueden?

**UX PARADIGM:**

- Assistant: El usuario está en control, AI sugiere (ej: GitHub Copilot)
- Agent: AI ejecuta tareas autónomamente dentro de límites (ej: AI SDR que envía emails)
- Autonomous: AI corre sin supervisión (ej: fraud detection que auto-bloquea)
- Embedded: AI mejora el producto sin que el usuario sepa que es AI (ej: Netflix recommendations)

**MODELO ECONÓMICO:**

- Haz la matemática ANTES de construir
- Si no sabes el costo por query, estima conservadoramente
- La regla: si AI costs > 30% del revenue por usuario, estás en danger zone

---

## 5.3 El Checklist de 5 Preguntas Incómodas

Antes de comprometerte con tu vision board, siéntate con tu equipo fundador y responde estas preguntas honestamente:

### Pregunta 1: ¿Qué si el problema desaparece en 12 meses por commoditización de modelos?

**Cómo evaluar:**

- ¿Tu problema es sobre OUTPUTS (resúmenes, traducciones, captions) o sobre WORKFLOWS (integraciones, contexto, compliance)?
- Los problemas de output se commoditizan. Los problemas de workflow persisten.

**Red flag:** Si tu respuesta es "bueno, pivotearemos", no tienes una estrategia.

### Pregunta 2: ¿Quién realmente es dueño de la data, y podrían revocar acceso?

**Cómo evaluar:**

- ¿Tu data viene de: usuarios (propio), third parties (riesgoso), scraping (muy riesgoso)?
- ¿Tienes contratos que aseguran acceso?
- ¿Qué pasa si tu fuente de data te corta?

**Red flag:** Si dependes de data de una sola fuente que no controlas.

### Pregunta 3: ¿Los reguladores, aseguradores, u oficiales de riesgo se sentirían avergonzados si nuestro producto fallara públicamente?

**Cómo evaluar:**

- ¿Qué pasa si tu AI da advice médico malo?
- ¿Qué pasa si alucina en un contexto legal?
- ¿Qué pasa si leakea PII?

**Red flag:** Si no has mapeado tus failure modes y sus consecuencias.

### Pregunta 4: ¿Puede un competidor replicar este producto con la misma API en menos de 6 semanas?

**Cómo evaluar:**

- Si tu producto es "wrapper de GPT + UI bonita", la respuesta es sí
- ¿Qué tienes que competidores NO pueden copiar? (data, distribución, trust, integraciones profundas)

**Red flag:** Si tu única defensa es "ejecutaremos mejor", no tienes moat.

### Pregunta 5: Si tenemos éxito a escala, ¿cuál es la primera forma en que trust se rompe?

**Cómo evaluar:**

- ¿Cuál es el failure mode más probable a 100x usuarios?
- ¿Cuándo empiezan las alucinaciones a ser peligrosas?
- ¿Cuándo los costos se vuelven insostenibles?
- ¿Cuándo los competidores nos atacan?

**Red flag:** Si no puedes articular cómo fallas a escala, no estás listo para escalar.

---

# CIERRE: CALL TO ACTION

## Tiempo estimado: 5 minutos

---

## La Ventana es Ahora

### Los Próximos 12 Meses Definen los Próximos 12 Años

En cada ola de tecnología, hay dos tipos de product builders:

1. Los que cabalgan el hype y son aplastados bajo sus propios costos
2. Los que convierten la ola en un moat y dominan un mercado por una década

AI no es diferente... excepto que los stakes son más altos.

### Por Qué AI No Perdona

- **Los costos no se comportan como SaaS:** En SaaS, una vez que construyes el producto, costos marginales por usuario tienden a cero. En AI, cada query, cada generation, cada inference tiene un precio real attached.

- **La commoditización pasa overnight:** En SaaS, features pueden tomar años en copiarse. En AI, se clonan en semanas.

- **El hype atrae competencia:** Cada nuevo AI feature obtiene 100 clones en Product Hunt. La mayoría desaparecen. Pero algunos toman tu mercado si no lo defiendes con estrategia.

- **Los inversores son más inteligentes ahora:** En 2021, "AI" en un deck levantaba millones. En 2025, VCs preguntan: ¿Cuál es tu moat cuando GPT-5 lance? ¿Cómo sobrevives costos de inference a 100M queries/mes?

### Su Misión en las 4 Semanas

**Semana 1-2: Discovery + Vision Board**

- Completar el Product Vision Board
- Responder las 5 preguntas incómodas
- Validar asunciones críticas

**Semana 3: Design + Prototype**

- Definir UX paradigm
- Mapear failure modes (FTCEM)
- Construir MVP/prototype

**Semana 4: Validate + Iterate**

- Testear con usuarios reales
- Medir contra métricas definidas
- Iterar basado en feedback

### El Mensaje Final

AI no va a esperar por ustedes.

Cada día, competidores están compounding su data, feedback loops, y user trust.

Cada día que esperan, el gap se hace más grande.

La diferencia entre las compañías que ganan y las que mueren no será quién tiene el mejor modelo o el feature más flashy.

Será quién construyó una ESTRATEGIA que escala, defiende, y compone.

---

## Recursos Adicionales

### Frameworks Mencionados

1. **AI Strategic Lens Framework** (3 Lenses: Market, Value, Execution)
2. **4D Method** (Discovery, Design, Develop, Deploy)
3. **FTCEM Framework** (Failure mode, Trigger, Consequence, Early warning, Mitigation)
4. **AI Decision Triangle** (Cost, Capability, Speed)
5. **The 3 Moats** (Data, Distribution, Trust)

### Casos de Estudio para Profundizar

- **Perplexity:** Trust moat via citations
- **Clay:** Category creation (GTM Engineer)
- **Harvey:** Prestige-first distribution
- **ElevenLabs:** Output-as-distribution
- **Lovable:** Vibe-native growth
- **Cursor:** Pricing crisis case study
- **Chegg/Jasper/Duolingo:** Failure cases

### Preguntas de Auto-Evaluación

1. ¿Mi problema sobrevive a GPT-5?
2. ¿Qué moat estoy construyendo?
3. ¿Mi pricing funciona a 10x escala?
4. ¿Tengo respuestas para las 5 preguntas incómodas?
5. ¿Puedo llenar el Product Vision Board con confianza?

---

_Documento preparado para Hardcore AI - Estación 2_
_De la Idea al Product Vision Board para Productos Agénticos_
