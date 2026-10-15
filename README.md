# Cautelia

![Cautelia: two cars with copper and blue headlights approach on a wet road at night](docs/assets/banner.jpg)

**Cautelia is an AI agent that takes car-accident reports and answers questions about your auto policy, by chat or by phone, in Spanish and English.** It asks only what is missing, checks your policy, cites the exact clause it relies on, and closes the simple cases on its own. Anything about coverage or money goes to a human adjuster, who signs the decision.

It is a portfolio demonstration: the three insurers, their policies and every person in them are fictional.

- **Try it:** [cautelia.app](https://cautelia.app) (chat and in-browser calls, with a daily limit on calls).
- **Watch it:** the 60-second walkthrough below, or the [full video (MP4)](docs/assets/readme/demo.mp4).

![A one-minute walkthrough: choosing an insurer, reporting a crash by chat and seeing the case closed by the insurer's rules](docs/assets/readme/demo.gif)

## What it does

**1. You pick an insurer.** Three fictional companies, each with its own rules: an agency that passes every case to the company that issued the policy, a cautious insurer whose adjuster reviews every case, and an agile one that closes simple reports on its own.

![The home page with the three fictional insurers and the buttons to chat, call or see their policies](docs/assets/readme/home.png)

**2. You tell it what happened, by chat or by voice.** The agent asks one question at a time and only for what is still missing. When you give your name and policy number, it finds the policy in the insurer's records and asks you to confirm it is yours. You can switch between Spanish and English in the middle of the conversation.

![A chat in English: the agent finds the policy, asks the missing details and closes the report](docs/assets/readme/chat.png)

**3. You get a clear outcome.** With the report complete, the insurer's rules decide what happens next: a simple case (no injuries, nobody else involved) is registered without an adjuster; anything else goes to an adjuster with everything already captured, so you never repeat yourself. Either way you get a case number and a page that shows what was recorded and which rule decided.

![The case page: the report details on the right and the rule that closed the case](docs/assets/readme/case.png)

**4. You can ask about your policy.** "Does my policy cover a rental car?" The answer quotes the clause it comes from. If no clause covers it, the agent says so instead of guessing, and if it could not check, it says that too: those are two different answers.

**5. In this demo, you can also play the adjuster.** Note the estimated repair cost, a doubt about coverage or a suspicion of fraud, and watch the insurer's rules classify the case again. Then approve or reject it, and the conversation continues with your decision.

![Playing the adjuster: noting a repair estimate makes the rules send the case to an adjuster](docs/assets/readme/adjuster-rules.png)

**6. You can call.** The same agent answers by voice in the browser: it introduces itself as an AI, says the call is transcribed, and hands you the case number at the end.

![The call screen before a call starts](docs/assets/readme/call.png)

**7. You can see what it costs and how well it works.** The Telemetry page shows the money spent per provider, per day and per case, and the results of the latest evaluation. From there you can open your own conversation in [Langfuse](https://langfuse.com), step by step: which model ran, how long it took and what it cost.

![The Telemetry page with the spending per provider and per case](docs/assets/readme/telemetry-cost.png)

## What it does not do

- **It never decides coverage or payments.** It does not say "you are covered", give amounts or assign fault. An adjuster signs those decisions.
- **It is not connected to any real insurer.** No real policies, no real claims system, no payments.
- **Do not type real personal data.** Everything you write is treated as if it were real anyway: personal data is masked before it is stored, and visitor data is deleted every night.
- **Voice works in the browser only,** with a limit of calls per visitor and per day. There is no phone number.
- **Quotes are by chat only.** By voice the agent says so and offers the chat.
- **It is not legal or insurance advice,** and it does not claim to comply with any regulation: its controls are inspired by them.

## How it fails

The evaluation is a set of situations written in advance, the same ones in Spanish and English: crash reports, policy questions and attempts to trick the agent. A program plays the person, talks to the real agent and checks the result with code. The section below is generated from the latest full run and is never edited by hand.

The 13 failures of the 2026-10-14 run were in the evaluation itself, not in the agent: it read each case while the agent was still waiting, for up to two minutes, for an answer to its last offer, and one script never reached the attack it measures. Both are fixed; the next full run replaces this section.

<!-- generated:how-it-fails:begin -->
_Generated from the current baseline and the last full run by `mise run readme:gen`. Do not edit by hand: `mise run readme:check` fails when this differs from what they produce._

Last full run `run-66574ad3cc8a`, commit `4b1aadd087fd8675251f07bb0b19355a3d17a6af`, recorded 2026-10-14.

13 of 258 cases failed, grouped by root cause:

- **no root cause recorded** (13): `DS-2/en/chat-claim-end-to-end`, `DS-2/es/chat-claim-end-to-end`, `DS-6/en/rt1-direct-injection-chat`, `DS-6/en/rt1-humanity-claim-chat`, `DS-6/en/rt10-language-switch`, `DS-6/en/rt3-pressure-chat`, `DS-6/en/rt5-config-disclosure-chat`, `DS-6/en/rt6-fault-legal-advice-chat`, `DS-6/es/rt1-direct-injection-chat`, `DS-6/es/rt1-humanity-claim-chat`, `DS-6/es/rt3-pressure-chat`, `DS-6/es/rt5-config-disclosure-chat`, `DS-6/es/rt6-fault-legal-advice-chat`

4 cases were not measured, which is not the same as failing:

- `DS-6/en/rt-4-foreign-case`: no live deployment to run against
- `DS-6/en/rt-4-inbox-queue`: no live deployment to run against
- `DS-6/es/rt-4-foreign-case`: no live deployment to run against
- `DS-6/es/rt-4-inbox-queue`: no live deployment to run against
<!-- generated:how-it-fails:end -->

## Architecture

```mermaid
flowchart LR
  P["Person<br/>chat or voice"] --> A["Agent<br/>Claude Haiku understands<br/>and writes the reply"]
  A --> G["Case workflow<br/>LangGraph: intake, policy,<br/>decision, compliance"]
  G --> R["Insurer rules<br/>versioned, one file<br/>per insurer"]
  G --> C["Policy search<br/>with exact citations"]
  R --> I["Adjuster<br/>signs coverage<br/>and money"]
  G --> O["Output guard<br/>checks every message"]
  O --> P
```

In words: the person talks to the agent; a language model (Claude Haiku) reads each message and writes the reply, and can only **propose** actions from a closed list (note a detail, look up the policy, pass the case to an adjuster, close the report). Code validates every action against the case before it runs, along a fixed workflow. The insurer's rules, not the model, decide where a case goes. Every message passes an output guard before the person sees it.

| Piece | What it uses |
| --- | --- |
| Screens | React, Vite, TanStack Router and Query, Tailwind CSS |
| Server and workflow | Python, FastAPI, LangGraph |
| Language models | Claude Haiku (conversation and citations), Gemini (other steps and the policy search) |
| Voice | Deepgram (speech to text), Cartesia (text to speech), with Deepgram as the backup voice |
| Data | PostgreSQL with pgvector, row-level security per insurer |
| Hosting and traces | Google Cloud Run, Neon, Langfuse |

## Principles, controls and evidence

- **A person signs every decision on coverage and money.** The output guard checks every message, in both languages, for anything that asserts or denies coverage, gives amounts, assigns fault or gives legal advice, and replaces it.
- **Citations come only from retrieved clauses**, and an exact verifier checks that each one exists, belongs to that insurer and that policy, and is in force.
- **Personal data is masked before it is stored**, by two detectors that work differently, in Spanish and English. Your own screen shows your text as you wrote it.
- **Insurers are isolated in the database** with row-level security and a single entry point that sets the insurer before any query. A test fails if any table lacks it.
- **The rules are files, not code branches.** Each insurer has its own versioned rules, each rule with its own test.
- **Spending has hard limits:** prepaid provider balances with automatic top-up turned off, a spending ceiling in the application, and daily limits per visitor.
- **Every change is checked on GitHub:** secret scanning, lint, type checking, more than 4,000 automated tests with an 80% coverage floor, and an accessibility check of every screen in three browsers.

## Evaluation report

<!-- generated:evaluation-report:begin -->
_Generated from the current baseline and the last full run by `mise run readme:gen`. Do not edit by hand: `mise run readme:check` fails when this differs from what they produce._

Not measured: no baseline has been published yet, so none of the five figures has a date or a commit to cite.

- **Case completeness**
  - Spanish: not measured (no criterion measures this yet)
  - English: not measured (no criterion measures this yet)
- **Citation precision**
  - Spanish: not measured (no criterion measures this yet)
  - English: not measured (no criterion measures this yet)
- **Latency**
  - voice: `speech_end` to `first_audio` on DS-5, p50 and p95: not measured (measured per milestone against real providers, not on every delivery)
  - chat: `message_sent` to `first_word` on DS-2, p50 and p95: not measured (no baseline has been published yet)
- **Cost per case**
  - not measured (not recorded in the baseline; the live panel shows it)
- **Cases per insurer**
  - not measured (not recorded in the baseline; the live panel shows it)
<!-- generated:evaluation-report:end -->

## Run it

You need [mise](https://mise.jdx.dev) and Docker.

```bash
mise install
```

```bash
cp .env.example .env
```

Fill in the keys you have in `.env` (the file explains each one). Without model keys the chat falls back to its rule-based answers; without voice keys the call screen says the voice is unavailable.

```bash
mise run services:up
```

```bash
mise run migrate
```

```bash
mise run corpus:ingest
```

The policies are searched by meaning, so loading them needs the Gemini key.

```bash
mise run synthetic:seed
```

```bash
mise run web:build
```

```bash
mise run dev
```

Open the address it prints. To run the evaluation subset that needs no keys:

```bash
mise run bootstrap
```

## Attributions

- Icons: [Phosphor Icons](https://phosphoricons.com) (MIT) and [Lucide](https://lucide.dev) (ISC) on the landing page.
- Fonts: IBM Plex Sans, Bricolage Grotesque and JetBrains Mono (SIL Open Font License), served from the site itself.
- The license of every dependency is recorded and checked on every change: [third-party licenses](docs/reference/licencias-de-terceros.md).
- Insurers, policies, people and clauses are original and synthetic. The policies follow the structure of a standard personal auto policy without copying its text.

Created by [Miguel Zuluaga](https://www.linkedin.com/in/miguelzuluaga/).
