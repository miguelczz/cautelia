# Untangle: Design Package (Tier 1, trimmed)

Single deliverable of the creative loop. Every line of copy below ships verbatim. Band ranges and pacing numbers are starting points, validated by the flick test.

Deploy folder: `site/` (index.html + assets/). Raws and review files: `review/`. Neither the skill zip nor this document ships.

Site is bilingual. English is the default; a nav toggle switches to Spanish. Both versions are authored here. The choice is remembered per visitor; first visit follows the browser language.

## 1. The brand premise

The knot. Every claim starts as a knot of calls, documents and decisions, and every quote starts as a knot of questions. Untangle is the act of pulling that knot into one straight line: a multi-agent system that gathers, structures, drafts and refers, with a person on every decision that matters. The whole site teaches and sells that one idea: the hero video is a knot of light coming undone, the signature element is a thread that runs the length of the page and straightens as the visitor scrolls, and the interactive moment has the visitor pull the thread themselves.

Audience: recruiters and engineering teams evaluating the builder. Buyer language gathered in Phase 3: "not another wrapper", "production signals", "how you handle failures", "a golden set, a score and an honest list of failures", "end-of-turn detection is the long pole", "barge-in is the feature nobody measures", "FNOL is intake and coordination, not judgment", "agent systems degrade silently", "summarize between handoffs".

One call to action: message the builder on LinkedIn. Every section funnels to `#contact`.

## 2. The palette as CSS tokens (starting values; finalized from the approved footage)

The user briefed the palette after the first frame: a copper-to-indigo duotone on near-black. That is one of the looks the skill avoids as a default reach; here it is the user's explicit choice and the tones are sampled from the approved frame (v3), so it is the brand's own world. No high-contrast serif anywhere; the display face stays a grotesk.

```css
:root{
  --canvas:#0B0B12;        /* near-black with the footage's faint indigo tint, never pure black */
  --canvas-deep:#07070C;   /* the hero's shadow floor */
  --panel:#13131D;         /* cards and raised surfaces */
  --panel-edge:#2A2A3C;    /* card borders */
  --accent:#E0873A;        /* the cord's copper: CTA and rare emphasis */
  --accent-hover:#F0A35C;
  --accent-muted:rgba(224,135,58,.16);  /* glows, whisper borders */
  --indigo:#4A57E0;        /* the loose tips: second tone, tiny doses (focus rings, one readout) */
  --indigo-muted:rgba(74,87,224,.18);
  --thread:#E9C29A;        /* the warm cord highlight for the signature thread */
  --text-primary:#F0ECE6;  /* warm bone white */
  --text-secondary:#A9A7B3; /* about 8.5:1 on canvas */
  --ink-on-accent:#120B06;  /* button label on the accent */
}
```

## 3. The type trio

- Display: Bricolage Grotesque, weights 300 and 500. Character without noise.
- Body: IBM Plex Sans, weights 400 and 500. Engineering heritage, quiet.
- Mono: JetBrains Mono, weight 400. Small labels, readouts, chips.

## 4. The band map (hero: 400vh, scroll range 300vh)

Footage: a knot of luminous threads in the right third loosens from the top down and the strands drop straight into a curtain of parallel vertical lines on the right. Captions live in the calm haze on the left two thirds. The settle sits center-left over the resting curtain.

| Band | Range (start) | Footage moment | Copy EN (verbatim) | Copy ES (verbatim) | Entrance |
|---|---|---|---|---|---|
| 1 | 0.00 to 0.20 | Knot tight, a few strands loose | "Every claim starts as a knot." | "Cada siniestro empieza como un nudo." | Weave: characters arrive alternating from above and below, echoing threads crossing. Opens settled with the one-time load ramp. |
| 2 | 0.26 to 0.48 | Loops opening, strands sliding free | "Calls. Documents. Decisions." / "A team of agents pulls the same thread." | "Llamadas. Documentos. Decisiones." / "Un equipo de agentes tira del mismo hilo." | Drift-down: each word starts above its resting spot and drops into place, echoing the strands dropping. |
| 3 | 0.54 to 0.76 | Strands falling straight, aligning | "Voice in real time. Answers in seconds." / "A person on every decision that matters." | "Voz en tiempo real. Respuestas en segundos." / "Una persona en cada decisión que importa." | Grid snap-align: characters slide horizontally into reading order, echoing the threads aligning. |
| 4 | 0.82 to 1.00 | The curtain at rest | Headline "Untangle." Subline "A multi-agent AI system for insurance quoting, underwriting and claims, with voice in real time. Built as a portfolio project to show how production agents are actually made." CTA "Message me on LinkedIn" | Headline "Untangle." Subline "Un sistema multiagente de IA para cotización, suscripción y siniestros de seguros, con voz en tiempo real. Construido como proyecto de portafolio para mostrar cómo se hacen los agentes de producción de verdad." CTA "Escríbeme en LinkedIn" | Word-by-word rise into a staged settle: headline words, then the subline, then the CTA. Skips the ease-out. |

Scrims: band 1 peak alpha .68 (the hook), bands 2 and 3 .64, band 4 .62. Audited against the worst frame of each band: every band measures above 15:1 at peak alpha, the settle subline 8:1, floor 3.5:1.

Delivered footage note (law 7 in reverse): the two leftward strands did not stay horizontal; they dropped and joined the vertical curtain, so the ending is five straight cords on the right and a clean left two thirds. The settle band sits center-left over calm haze, nothing under it. Hero height 600vh (up from the 400vh default) so each of the four beats gets an 80vh-plus plateau; validated by the flick test at 120 and 360px steps.

## 5. The static-hero copy block (landscape phones and reduced motion; changed 2026-09-14)

Mobile decision, revised at the user's request after the launch: portrait phones and tablets now run the scrub too. The video is 5.4 MB, the action lane is pinned to the right edge with `object-position: 100% 50%`, and the captions move to the bottom of the frame over a rising gradient scrim. The static hero remains for reduced motion and for phones held sideways, where the journey has no room. The user verifies on their own phone.

Over the poster (the knot, positioned toward the top right so the cover crop keeps it), copy at the bottom left over a rising gradient:

- EN: "Every claim starts as a knot." / "Untangle is a multi-agent AI system for insurance quoting, underwriting and claims, with voice in real time. A portfolio project built to show how production agents are actually made." / CTA "Message me on LinkedIn"
- ES: "Cada siniestro empieza como un nudo." / "Untangle es un sistema multiagente de IA para cotización, suscripción y siniestros de seguros, con voz en tiempo real. Un proyecto de portafolio hecho para mostrar cómo se hacen los agentes de producción de verdad." / CTA "Escríbeme en LinkedIn"

## 6. The below-fold outline

Nav: mark + "Untangle", links (How it works, Voice, Guardrails, Evals, FAQ) / (Cómo funciona, Voz, Barreras, Evals, Preguntas), EN | ES toggle, button "LinkedIn".

### S1. Why this exists (split: text left, proof chips right, the thread passes between)

- Kicker EN "Why this exists" / ES "Por qué existe"
- Headline EN "Not another wrapper." / ES "No es otro wrapper."
- Lede EN "Reviewers have seen the chatbot around an API a hundred times. Untangle was built to show the parts that project skips: failure handling, structured state, real integrations, and proof that it works." / ES "Quien revisa portafolios ha visto cien veces el chatbot envuelto en una API. Untangle existe para mostrar lo que ese proyecto se salta: manejo de fallos, estado estructurado, integraciones reales y pruebas de que funciona."
- Chips EN: "Handles interruptions" · "Structured handoffs" · "Golden-set evals" · "Human on every decision" / ES: "Aguanta interrupciones" · "Handoffs estructurados" · "Evals con golden set" · "Una persona en cada decisión"
- Living element: the chips' borders breathe on a 6s cycle.

### S2. How it works (full-width hand-drawn SVG diagram, nodes light in sequence on entrance; agent list below in a 3-column grid)

- Kicker EN "How it works" / ES "Cómo funciona"
- Headline EN "One orchestrator. Specialist agents. Small shared state." / ES "Un orquestador. Agentes especialistas. Estado compartido pequeño."
- Lede EN "Each turn goes to the right specialist. Agents hand back structured results, never raw reasoning, so the context stays small and the trace stays readable." / ES "Cada turno va al especialista correcto. Los agentes devuelven resultados estructurados, nunca razonamiento crudo, así el contexto se mantiene pequeño y la traza se puede leer."
- Diagram nodes EN: Voice layer → Orchestrator → Intake, Quote, Underwriting, Claims (FNOL), Documents → Tools: rating rules, policy data, claims records → Human handoff. ES: Capa de voz → Orquestador → Captura, Cotización, Suscripción, Siniestros (FNOL), Documentos → Herramientas: reglas de tarifa, datos de póliza, registros de siniestros → Handoff humano.
- Agent cards (EN / ES):
  - Orchestrator: "Routes each turn, keeps the shared state small, and decides when a person needs to step in." / Orquestador: "Enruta cada turno, mantiene el estado compartido pequeño y decide cuándo debe entrar una persona."
  - Intake: "Gathers the facts of a call, who, what, when, where, and fills the structured record while the person talks." / Captura: "Reúne los hechos de una llamada, quién, qué, cuándo, dónde, y llena el registro estructurado mientras la persona habla."
  - Quote: "Turns a profile into a priced quote using the carrier's rating rules, not the model's opinion." / Cotización: "Convierte un perfil en una cotización con precio usando las reglas de tarifa de la aseguradora, no la opinión del modelo."
  - Underwriting: "Checks eligibility, flags what needs a human, and drafts the referral with the evidence attached." / Suscripción: "Revisa elegibilidad, marca lo que necesita una persona y redacta la derivación con la evidencia adjunta."
  - Claims (FNOL): "Captures a first notice of loss completely the first time, so nobody has to call back." / Siniestros (FNOL): "Registra el primer aviso de siniestro completo a la primera, para que nadie tenga que volver a llamar."
  - Documents: "Reads policies, estimates and reports into structured fields the other agents can reason over." / Documentos: "Lee pólizas, presupuestos e informes y los convierte en campos estructurados sobre los que los demás agentes pueden razonar."

### S3. Voice in real time (horizontal pipeline timeline with a latency lane, then a scripted example turn rendered as a conversation timeline; layout differs from S2: timeline over a two-column text block)

- Kicker EN "Voice" / ES "Voz"
- Headline EN "Fast enough to feel like a call. Patient enough not to interrupt." / ES "Tan rápido que se siente como una llamada. Tan paciente que no interrumpe."
- Pipeline stages EN: Streaming speech to text → End-of-turn detection → Orchestrator → Tool calls → Streaming text to speech. ES: Voz a texto en streaming → Detección de fin de turno → Orquestador → Llamadas a herramientas → Texto a voz en streaming.
- Points (EN / ES):
  - "End-of-turn detection is the long pole. Untangle waits for meaning, not for silence." / "La detección de fin de turno es el cuello de botella. Untangle espera el sentido, no el silencio."
  - "The caller can interrupt. The agent stops mid-sentence, keeps the state, and picks up where the caller left it." / "Quien llama puede interrumpir. El agente se detiene a mitad de frase, conserva el estado y retoma donde la persona lo dejó."
  - "Every stage streams. Nothing waits for the whole answer." / "Cada etapa transmite en streaming. Nada espera la respuesta completa."
- Example turn, labeled EN "Scripted example, not a recording" / ES "Ejemplo guionizado, no es una grabación":
  - Caller EN "Hi, I had a fender bender this morning, nobody's hurt." / ES "Hola, tuve un choque leve esta mañana, nadie salió herido."
  - Agent EN "Glad everyone's okay. I'll open the claim while we talk. Where did it happen?" / ES "Me alegra que estén bien. Abro el siniestro mientras hablamos. ¿Dónde ocurrió?"
  - Caller EN "On the highway, near exit 12, around eight." / ES "En la autopista, cerca de la salida 12, sobre las ocho."
  - Agent EN "Got it: highway, exit 12, about 8 a.m. Was the other driver's information exchanged?" / ES "Anotado: autopista, salida 12, sobre las 8. ¿Intercambiaron datos con el otro conductor?"
  - Side readout (mono): EN "record: location ✓ time ✓ injuries: none ✓ other party: pending" / ES "registro: lugar ✓ hora ✓ heridos: ninguno ✓ otra parte: pendiente"
- Living element: a whisper-level waveform line under the timeline, 8s cycle.

### S4. Guardrails (full-bleed band using the hero's ending frame as the image, text on the calm left side)

- Kicker EN "Guardrails" / ES "Barreras"
- Headline EN "The agents gather. People decide." / ES "Los agentes reúnen. Las personas deciden."
- Lede EN "A first notice of loss is intake and coordination, not judgment. Coverage and money decisions belong to the carrier's rules and its adjusters. Untangle is built on that line." / ES "El primer aviso de siniestro es captura y coordinación, no juicio. Las decisiones de cobertura y dinero son de las reglas de la aseguradora y de sus ajustadores. Untangle está construido sobre esa línea."
- Three rails (EN / ES):
  - "Before the model: input checks, personal data handling, scope limits." / "Antes del modelo: validación de entradas, manejo de datos personales, límites de alcance."
  - "In flight: every tool call is validated against a schema. No free-form writes." / "Durante: cada llamada a herramienta se valida contra un esquema. Sin escrituras libres."
  - "After the model: anything that touches coverage or money goes to a person, with the trace attached." / "Después del modelo: todo lo que toca cobertura o dinero va a una persona, con la traza adjunta."

### S5. Evals and traces (asymmetric two-column: a large headline column and a checklist column; no cards, to break from S2's grid)

- Kicker EN "Evals" / ES "Evals"
- Headline EN "A golden set, a score, and an honest list of failures." / ES "Un golden set, una puntuación y una lista honesta de fallas."
- Lede EN "Every change runs against scripted calls with known right answers. The report is a pass or a fail per case, and the cases that broke stay in the open." / ES "Cada cambio se corre contra llamadas guionizadas con respuestas correctas conocidas. El reporte es aprobado o fallo por caso, y los casos que se rompen quedan a la vista."
- What gets measured (EN / ES): "Latency per turn, end to end" / "Latencia por turno, de punta a punta" · "Interruptions handled without losing state" / "Interrupciones manejadas sin perder estado" · "Completeness of the FNOL record" / "Completitud del registro FNOL" · "Correct handoffs to a person" / "Derivaciones correctas a una persona"
- Traces EN "Every call leaves a trace: each model call, each tool call, each handoff, nested so one claim can be followed from the first word to the final record." / ES "Cada llamada deja una traza: cada llamada al modelo, cada herramienta, cada handoff, anidados para seguir un siniestro desde la primera palabra hasta el registro final."
- Living element: none beyond the entrance. (A case-id ticker was built and removed on 2026-09-14: invented case ids read as data in a section about honesty.)

### S6. The interactive moment (centered stage, the knot drawn in SVG)

- Kicker EN "Try it" / ES "Pruébalo"
- Headline EN "Hold to untangle." / ES "Mantén pulsado para desenredar."
- Instruction EN "Press and hold the knot." / ES "Mantén pulsado el nudo."
- Mechanics: progress builds while holding (about 1.8s to complete), releasing early eases it back down, completing lights the sequence in order. Reduced motion: final state shown, no hold needed. Keyboard: Space or Enter held on the focused knot.
- Sequence EN: "Call received" → "Facts captured" → "Quote drafted" → "Referred to a person" → "Record complete". ES: "Llamada recibida" → "Hechos registrados" → "Cotización redactada" → "Derivado a una persona" → "Registro completo".
- Completion line EN "That's the whole product." / ES "Eso es todo el producto."

### S7. FAQ (single column, accordion; answers in the reviewers' language)

EN:
1. "Is this just a wrapper around a model?" / "No. The model is one component. The work is in the orchestration, the structured state, the tools, the voice pipeline, the guardrails and the evals. All of it is on the table in a walkthrough."
2. "Does it work when people interrupt or talk over it?" / "That is the point of the voice layer. The caller can interrupt, the agent stops, keeps the state and picks up where the caller left it. It is also the hardest part, and the eval set tracks it."
3. "Who decides coverage?" / "People do. The agents gather facts, draft and refer. Anything that touches coverage or money goes to a person with the trace attached."
4. "Is this a real insurer's product?" / "No. Untangle is a demonstration project built for a portfolio. The insurance flows are real patterns. The carrier, the data and the imagery are not."
5. "Can I see the code or a live run?" / "Yes. Message me on LinkedIn and I will walk you through a live call, the traces behind it and the code."

ES:
1. "¿Es solo un wrapper de un modelo?" / "No. El modelo es un componente. El trabajo está en la orquestación, el estado estructurado, las herramientas, la capa de voz, las barreras y las evals. Todo eso está sobre la mesa en una demo."
2. "¿Funciona cuando la gente interrumpe o habla encima?" / "Para eso existe la capa de voz. Quien llama puede interrumpir, el agente se detiene, conserva el estado y retoma donde la persona lo dejó. También es la parte más difícil, y el set de evals la mide."
3. "¿Quién decide la cobertura?" / "Las personas. Los agentes reúnen hechos, redactan y derivan. Todo lo que toca cobertura o dinero va a una persona con la traza adjunta."
4. "¿Es el producto de una aseguradora real?" / "No. Untangle es un proyecto de demostración hecho para un portafolio. Los flujos de seguros son patrones reales. La aseguradora, los datos y las imágenes no lo son."
5. "¿Puedo ver el código o una corrida en vivo?" / "Sí. Escríbeme en LinkedIn y te muestro una llamada en vivo, las trazas detrás y el código."

### S8. Final call to action (`#contact`)

- Headline EN "See it run." / ES "Míralo correr."
- Copy EN "A twenty-minute walkthrough: a live call, the traces behind it, and the code." / ES "Una demo de veinte minutos: una llamada en vivo, las trazas detrás y el código."
- Button EN "Message me on LinkedIn" / ES "Escríbeme en LinkedIn". Links to the builder's LinkedIn profile (URL to be supplied; marked `<!-- LINKEDIN URL -->` in the build).
- Form handling: no form. The CTA links straight to LinkedIn.

### Footer

- EN "Untangle is a demonstration project built for a portfolio. It is not an insurance product and is not affiliated with any carrier. Imagery generated with AI." / ES "Untangle es un proyecto de demostración hecho para un portafolio. No es un producto de seguros ni está afiliado a ninguna aseguradora. Imágenes generadas con IA."
- Language toggle repeated. Mark + year.

## 7. The vector layer plan

- The signature thread: one SVG path running the full page height in a fixed-width lane, tangled in loops beside the hero's settle and straightening to a plain vertical line by the FAQ. Drawn with `stroke-dashoffset` driven by scroll (delta-gated), whisper glow. Reduced motion: fully drawn.
- The mark (final, user's pick on 2026-09-15): "scribble-loop" from Phosphor Icons, regular weight, MIT licensed (license text ships as `site/PHOSPHOR-LICENSE.txt`). One solid color, the copper accent, inline SVG in the nav and footer, cropped to the glyph's bounds (viewBox 22 38 236 180). The favicon is the same glyph, no background, filling the icon. The hand-drawn loop-to-line mark, the two-strand mark and the trefoil knots were all reviewed and set aside.
- S2 diagram: nodes and connectors drawn by hand, connectors self-draw on entrance, nodes light in sequence.
- S3 pipeline: five stages on a rail with a latency lane, plus the whisper waveform.
- S6 knot: an SVG knot path whose `stroke-dashoffset` and a second straight path crossfade under the hold progress.
- Fixed background environment: one layer behind everything, a slow ink-blue radial drift plus faint particles, 80s cycle, paused off-screen and on hidden tabs.
- Dividers: thin thread-like rules between sections, drawn on entrance.

## 8. The engineering list

Everything in `scrub-pipeline.md`: Blob fetch (plain form under 8 MB, streamed with the ring above), poster set from JS inside the gated path, dt-normalized lerp that rests, gated seeks with the error escape, delta-gated DOM writes, bands paced in scroll distance and validated by the flick test, the four-layer legibility system with the worst-frame audit at 3.5:1, the five static-hero gates identical in CSS and JS with live change listeners, complete without the video, reduced motion honored live in both directions, `overflow-x: clip` on html and body, the quality floor (font weights trimmed with preconnect, `ch` on text elements, computed contrast, landmarks and skip link, decorative video out of the tab order, focus-visible in the accent, 44px touch targets, title, description, theme-color, inline SVG favicon, DEPLOY STEP comment for og tags), and the whole-site-animated standard from Phase 8.

Bilingual mechanics: a dictionary of every string keyed by id, `data-i18n` on elements, hero headlines re-split after a language switch, `<html lang>` updated, choice stored in localStorage, first visit follows `navigator.language`.

## 9. The copy gate line

Every viewer-facing line above ships verbatim. The built page must pass the Phase 9 gate before anyone sees it: zero em dashes, zero of the stock words (leverage, seamless, empower, unlock, robust, actionable, data-driven, solutions), plus the body-copy sweep for AI tells. Deliberate devices written here stay: the triplet "Calls. Documents. Decisions.", the staccato "Voice in real time. Answers in seconds.", and the closing "That's the whole product."
