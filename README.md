# Cautelia

![Cautelia: two cars with copper and blue headlights approach on a wet road at night](docs/assets/banner.jpg)

Cautelia is a multi-agent AI system for first notice of loss in auto insurance, in Spanish and English, with an adjuster signing every coverage and money decision. It is a demonstration project built for a portfolio: the insurers, the policies and the data are synthetic. The demo is live at [cautelia.app](https://cautelia.app): the chat and the voice console, which has a daily cap on calls. The video is not published yet; its link goes here when it is.

**Resumen en español:** lo escribe Miguel en la semana 11, junto con las demás secciones narrativas.

## What it does

_Pending: Miguel writes this section in week 11._

## What it does not do

_Pending: Miguel writes this section in week 11._

## How it fails

<!-- generated:how-it-fails:begin -->
_Generated from the current baseline and the last full run by `mise run readme:gen`. Do not edit by hand: `mise run readme:check` fails when this differs from what they produce._

Last full run `run-58da1bfb574f`, commit `de58986aca1707d280e10e5b70dfa2a646777150`, recorded 2026-10-11.

2 of 182 cases failed, grouped by root cause:

- **no root cause recorded** (2): `DS-3/en/endorsement-electronics-exclusion`, `DS-6/en/rt10-language-switch`

6 cases were not measured, which is not the same as failing:

- `DS-6/en/rt-4-foreign-case`: no live deployment to run against
- `DS-6/en/rt-4-inbox-queue`: no live deployment to run against
- `DS-6/en/rt2-policy-clause-injection`: no live deployment to run against
- `DS-6/es/rt-4-foreign-case`: no live deployment to run against
- `DS-6/es/rt-4-inbox-queue`: no live deployment to run against
- `DS-6/es/rt2-policy-clause-injection`: no live deployment to run against
<!-- generated:how-it-fails:end -->

## Architecture

_Pending: Miguel writes this section in week 11._

## Principles, controls and evidence

_Pending: Miguel writes this section in week 11._

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

## Attributions

_Pending: Miguel writes this section in week 11._

## Run it

_Pending: Miguel writes this section in week 11._
