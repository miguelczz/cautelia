# Textos de la landing — borrador para aprobar

Escritos el 2026-10-05, después de aprobar el concepto de portada. **Todavía no
están en `site/`**: esto es el borrador que Miguel revisa antes de que se toque
una línea de la página.

**Dos reglas gobiernan cada frase de aquí.** La primera: no se promete nada que no
esté construido, así que cada afirmación de abajo se comprobó contra el código y
no contra el recuerdo. La segunda: no se dice «cumple con» ninguna norma.

**Una corrección que salió al escribirlos.** El diagrama de la página de hoy
dibuja cinco agentes especialistas —Captura, Cotización, Suscripción, Siniestros
y Documentos— y el sistema tiene **cuatro nodos**, que son `intake`,
`policy_verification`, `decision` y `compliance`. Ni «Suscripción» ni
«Documentos» existen como nodos. El diagrama hay que redibujarlo con los cuatro
reales; los textos de abajo ya van con ellos.

---

## Portada

El recorrido lo mueve el scroll y no lleva texto hasta el final. Lo único escrito
es el cierre:

> **Cautelia.**
> Toma el reporte. Comprueba qué dice su póliza. Pasa a una persona.

**EN**

> **Cautelia.**
> Takes the report. Checks what the policy says. Hands it to a person.

**Versión estática**, para quien llegue sin que el recorrido pueda correr:

> **Alguien acaba de chocar y no sabe qué cubre su póliza.**
>
> Cautelia toma el reporte por voz o por texto, busca la respuesta en la póliza
> de esa aseguradora y deja la decisión en manos de una persona. Es un proyecto
> de portafolio, construido para mostrar cómo se hacen de verdad los agentes que
> salen a producción.

**EN**

> **Someone just had a crash and doesn't know what their policy covers.**
>
> Cautelia takes the report by voice or text, finds the answer in that insurer's
> policy, and leaves the decision to a person. A portfolio project, built to show
> how production agents are actually made.

---

## 1 · Por qué existe

**Antetítulo:** Por qué existe · *Why this exists*

**Título:** No es otro envoltorio. · *Not another wrapper.*

**Entrada:**

> Quien revisa portafolios ha visto cien veces un chat alrededor de una API.
> Llamar al modelo es la parte fácil y la que ya sabe hacer todo el mundo.
> Cautelia está construido para enseñar lo que ese proyecto se salta: qué pasa
> cuando el proveedor falla, dónde vive el estado, de dónde sale cada cifra, y
> cómo se demuestra que funciona en vez de afirmarlo.

**EN**

> Anyone reviewing portfolios has seen a chat wrapper around an API a hundred
> times. Calling the model is the easy part, and the part everyone already knows.
> Cautelia is built to show what that project skips: what happens when the
> provider fails, where the state lives, where each figure comes from, and how
> you prove it works instead of claiming it.

**Las cuatro etiquetas** (reemplazan a las de hoy, que se escribieron antes de
construirlo):

| Español | English |
| --- | --- |
| Cada cita, verificada contra la póliza | Every citation checked against the policy |
| Aislamiento entre aseguradoras, con prueba | Tenant isolation, with a test |
| Datos personales tapados antes de guardar | Personal data redacted before storage |
| Ninguna cobertura decidida sin una persona | No coverage decided without a person |

---

## 2 · Cómo funciona

**Antetítulo:** Cómo funciona · *How it works*

**Título:** Un orquestador. Cuatro nodos. Estado compartido pequeño. ·
*One orchestrator. Four nodes. A small shared state.*

**Entrada:**

> A qué nodo va cada turno lo decide **código**, no el modelo: una función que
> recibe campos del estado y devuelve uno de cuatro nombres. Cada nodo declara
> qué campos escribe y ninguno escribe los de otro. Lo que los nodos devuelven
> son resultados con forma, nunca razonamiento en bruto, así el contexto se
> mantiene pequeño y la traza se puede leer de arriba abajo.

**EN**

> Which node each turn goes to is decided in **code**, not by the model: a
> function that takes fields from the state and returns one of four names. Each
> node declares which fields it writes, and no node writes another's. What nodes
> return is structured results, never raw reasoning, so the context stays small
> and the trace reads top to bottom.

**Las etiquetas del diagrama**, con los nombres reales:

| Pieza | Español | English |
| --- | --- | --- |
| Entrada | Capa de voz | Voice layer |
| Centro | Orquestador | Orchestrator |
| Nodo 1 | Captura | Intake |
| Nodo 2 | Verificación de póliza | Policy verification |
| Nodo 3 | Decisión | Decision |
| Nodo 4 | Cumplimiento | Compliance |
| Herramienta | Corpus de pólizas | Policy corpus |
| Herramienta | Motor de reglas | Rules engine |
| Salida | Bandeja del ajustador | Adjuster inbox |

**Las cuatro tarjetas:**

> **Captura.** Reúne los hechos mientras la persona habla —quién, qué, cuándo,
> dónde— y va llenando el expediente con forma, sin pedirlos en orden.
>
> **Verificación de póliza.** Busca en las pólizas de esa aseguradora y solo cita
> cláusulas que existen, que son de esa póliza y que están vigentes. Cuando no
> encuentra nada lo dice; cuando no pudo comprobarlo, dice otra cosa distinta.
>
> **Decisión.** Aplica las reglas versionadas de la aseguradora, cada una con su
> prueba. El modelo no decide la categoría.
>
> **Cumplimiento.** Revisa el caso antes de cerrarlo y deja constancia de lo que
> revisó.

**EN**

> **Intake.** Gathers the facts while the person talks — who, what, when, where —
> filling the structured record without asking in a fixed order.
>
> **Policy verification.** Searches that insurer's policies and only cites clauses
> that exist, belong to that policy and are in force. When it finds nothing it
> says so; when it could not check, it says something different.
>
> **Decision.** Applies the insurer's versioned rules, each with its own test. The
> model does not pick the category.
>
> **Compliance.** Reviews the case before it closes and records what it reviewed.

**Y una frase que conviene que esté, porque es la diferencia entera:**

> «No encuentro una cláusula que lo cubra» y «no pude verificarlo» son dos
> valores distintos en el expediente, en la traza y en el reporte. Juntarlos
> ensuciaría una métrica publicada con fallos de infraestructura.

**EN**

> "I find no clause covering this" and "I could not verify" are two different
> values in the record, in the trace and in the report. Collapsing them would
> contaminate a published metric with infrastructure failures.

---

## 3 · Voz

**Antetítulo:** Voz · *Voice*

**Título:** Rápida para parecer una llamada. Paciente para no interrumpir. ·
*Fast enough to feel like a call. Patient enough not to interrupt.*

**Entrada:**

> Saber cuándo alguien terminó de hablar es la parte difícil. Cautelia espera
> significado, no silencio: quien está dictando una placa hace pausas, y cortarle
> ahí arruina la llamada. Se puede interrumpir a la agente — para a mitad de
> frase, conserva el estado y retoma donde la persona lo dejó.

**EN**

> Knowing when someone has finished speaking is the hard part. Cautelia waits for
> meaning, not for silence: someone dictating a plate number pauses, and cutting
> them off there ruins the call. The agent can be interrupted — it stops
> mid-sentence, keeps the state and picks up where the caller left it.

**La frase que nadie más pone, y que conviene poner:**

> El trabajo pesado —verificar la póliza, correr las reglas, revisar
> cumplimiento— **nunca ocurre dentro del turno**. Si ocurriera, lo que tarda en
> responder dependería de cuántas reglas tenga esa aseguradora.

**EN**

> The heavy work — verifying the policy, running the rules, reviewing compliance —
> **never happens inside the turn**. If it did, how long the agent takes to answer
> would depend on how many rules that insurer has.

---

## 4 · Barandas

**Antetítulo:** Barandas · *Guardrails*

**Título:** Los agentes reúnen. Las personas deciden. ·
*The agents gather. People decide.*

**Entrada:**

> Un reporte de siniestro es tomar datos y coordinar, no juzgar. Lo que toca
> cobertura o dinero es de la aseguradora y de sus ajustadores. Cautelia no
> afirma que algo esté cubierto, no lo niega y no menciona montos: lo pasa a una
> persona con la traza enganchada.

**EN**

> A first notice of loss is intake and coordination, not judgment. Anything
> touching coverage or money belongs to the carrier and its adjusters. Cautelia
> does not claim something is covered, does not deny it and does not mention
> amounts: it hands the case to a person with the trace attached.

**Los tres momentos:**

| | Español | English |
| --- | --- | --- |
| Antes del modelo | El texto de fuera entra como dato, nunca pegado a las instrucciones | External text enters as data, never concatenated into the prompt |
| Durante | Cada llamada a una herramienta se valida contra su esquema | Every tool call is validated against its schema |
| Antes de salir | Todo lo que llega a la persona pasa por una sola guardia, incluidos los mensajes de error | Everything reaching the person passes one exit guard, error messages included |

**Y una cuarta, que merece su línea:**

> Si alguien dice que hay un herido grave, la agente deja de tomar datos y
> responde con la frase de emergencia. Es la única vez que el sistema interrumpe
> su propio trabajo.

**EN**

> If someone says there is a serious injury, the agent stops collecting data and
> answers with the emergency phrase. It is the only time the system interrupts
> its own work.

---

## 5 · Evaluaciones

**Antetítulo:** Evaluaciones · *Evals*

**Título:** Un conjunto dorado, un resultado y la lista honesta de lo que falla. ·
*A golden set, a score, and an honest list of failures.*

**Entrada:**

> Cada cambio corre contra conversaciones guionadas con respuestas conocidas. El
> reporte es pasa o falla **por caso**, en español y en inglés por separado, nunca
> un promedio de los dos. Un caso que empieza a fallar se queda a la vista: nunca
> se retira del conjunto para que suba una cifra.

**EN**

> Every change runs against scripted conversations with known answers. The report
> is pass or fail **per case**, in Spanish and English separately, never averaged
> across the two. A case that starts failing stays visible: it is never removed
> from the set to make a number go up.

**Lo que se mide:**

| Español | English |
| --- | --- |
| Cero citas que no existen | Zero citations that do not exist |
| Cero turnos que afirmen cobertura, montos o culpa | Zero turns claiming coverage, amounts or fault |
| Cero fugas entre aseguradoras | Zero leaks between insurers |
| Latencia por turno, y la parada al interrumpir | Latency per turn, and stop time on interruption |
| Qué tan completo queda el expediente | How complete the record ends up |
| Si la derivación a una persona ocurrió cuando debía | Whether the handoff happened when it should |

**Y la traza:**

> Cada llamada deja su rastro: cada llamada al modelo, cada herramienta, cada
> derivación, anidadas, de modo que un siniestro se sigue desde la primera
> palabra hasta el expediente cerrado.

**EN**

> Every call leaves a trace: each model call, each tool call, each handoff,
> nested, so one claim can be followed from the first word to the closed record.

---

## 6 · Pruébalo

**Antetítulo:** Pruébalo · *Try it*

**Título:** Mantén pulsado para verificar. · *Press and hold to verify.*

Reemplaza al nudo. Misma interacción, y los cinco pasos se mantienen porque son
ciertos:

| Español | English |
| --- | --- |
| Llamada recibida | Call received |
| Hechos capturados | Facts captured |
| Póliza consultada | Policy checked |
| Derivado a una persona | Handed to a person |
| Expediente completo | Record complete |

**Cierre:** Eso es el producto entero. · *That's the whole product.*

---

## 7 · Preguntas

**Antetítulo:** Preguntas · *FAQ*

**Título:** Lo que de verdad preguntan. · *The questions people actually ask.*

> **¿Esto es un envoltorio alrededor de un modelo?**
> No. El modelo es una pieza. El trabajo está en la orquestación, el estado con
> forma, las herramientas, la voz, las barandas y las evaluaciones. El modelo es
> intercambiable; lo demás es lo que hace que sirva.
>
> **¿Funciona cuando la gente interrumpe o habla encima?**
> Para eso existe la capa de voz. Se puede interrumpir: la agente para, conserva
> el estado y retoma donde se quedó. Es también lo que miden las evaluaciones de
> audio.
>
> **¿Quién decide la cobertura?**
> Las personas. Los agentes reúnen hechos, redactan y derivan. Todo lo que toca
> cobertura o dinero va a una persona con la traza enganchada.
>
> **¿Es el producto de una aseguradora real?**
> No. Cautelia es una demostración construida para un portafolio. Los flujos son
> patrones reales del sector; las aseguradoras, las pólizas y los datos son
> inventados y sintéticos.
>
> **¿Puedo ver el código o una llamada en vivo?**
> Escríbame y se lo muestro: una llamada de verdad, las trazas que deja y el
> código detrás.

**EN**

> **Is this a wrapper around a model?**
> No. The model is one component. The work is in the orchestration, the structured
> state, the tools, the voice layer, the guardrails and the evals. The model is
> swappable; the rest is what makes it useful.
>
> **Does it work when people interrupt or talk over it?**
> That is what the voice layer is for. You can interrupt: the agent stops, keeps
> the state and picks up where it left off. It is also what the audio evals
> measure.
>
> **Who decides coverage?**
> People do. The agents gather facts, draft and refer. Anything touching coverage
> or money goes to a person with the trace attached.
>
> **Is this a real insurer's product?**
> No. Cautelia is a demonstration built for a portfolio. The flows are real
> industry patterns; the insurers, the policies and the data are invented and
> synthetic.
>
> **Can I see the code or a live run?**
> Message me and I will show you: a real call, the traces it leaves and the code
> behind it.

**Nota sobre la última.** Hoy dice «escríbeme y te muestro el código». El
repositorio es privado hasta que se decida publicarlo, así que la respuesta se
queda como está. **El día que el aplicativo esté en vivo, cambia** y en su lugar
entra un enlace para probarlo.

---

## 8 · Contacto

**Título:** Véalo funcionando. · *See it run.*

**Entrada:**

> Veinte minutos: una llamada en vivo, las trazas que deja y el código detrás.

**EN**

> Twenty minutes: a live call, the traces it leaves and the code behind it.

**Botón:** Escríbame por LinkedIn · *Message me on LinkedIn*

**Lo que falta aquí, y por qué no está.** Cuando el aplicativo esté publicado,
este botón deja de ser el único: el principal pasa a ser **entrar y probarlo**, y
LinkedIn queda de segundo. Hoy no se pone porque no hay adónde llevar, y un botón
que lleva a un 404 es peor que no tenerlo.
