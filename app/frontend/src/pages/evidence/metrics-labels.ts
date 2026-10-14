// Los textos del panel de cifras que dependen de un dato cerrado: cada uno con su
// clave literal dentro de un `switch` exhaustivo, como las paginas de estado.

import type {
  FigureKey,
  LatencyEvent,
  LatencyMeasure,
  NotMeasuredCause,
} from "../../shared/api-client/metrics";
import type { Locale } from "../../shared/copy/copy-keys";
import type { Message } from "../../shared/i18n/translate";

export function figureName(key: FigureKey): Message {
  switch (key) {
    case "completeness":
      return (t) => t("metrics.figure.completeness");
    case "citation_precision":
      return (t) => t("metrics.figure.citation_precision");
    case "latency":
      return (t) => t("metrics.figure.latency");
    case "cost_per_case":
      return (t) => t("metrics.figure.cost_per_case");
    case "cases_by_tenant":
      return (t) => t("metrics.figure.cases_by_tenant");
  }
}

/** Que mide cada cifra, en palabras llanas (D5, fase 3, 2026-10-08). */
export function figureHelp(key: FigureKey): Message {
  switch (key) {
    case "completeness":
      return (t) => t("metrics.figure_help.completeness");
    case "citation_precision":
      return (t) => t("metrics.figure_help.citation_precision");
    case "latency":
      return (t) => t("metrics.figure_help.latency");
    case "cost_per_case":
      return (t) => t("metrics.figure_help.cost_per_case");
    case "cases_by_tenant":
      return (t) => t("metrics.figure_help.cases_by_tenant");
  }
}

export function causeText(cause: NotMeasuredCause): Message {
  switch (cause) {
    case "no_baseline":
      return (t) => t("metrics.cause.no_baseline");
    case "criterion_absent":
      return (t) => t("metrics.cause.criterion_absent");
    case "criterion_not_built":
      return (t) => t("metrics.cause.criterion_not_built");
    case "measured_per_milestone":
      return (t) => t("metrics.cause.measured_per_milestone");
    case "not_connected":
      return (t) => t("metrics.cause.not_connected");
    case "latency_not_in_baseline":
      return (t) => t("metrics.cause.latency_not_in_baseline");
    case "too_few_turns":
      return (t) => t("metrics.cause.too_few_turns");
  }
}

export function languageName(language: "es" | "en"): Message {
  return language === "es" ? (t) => t("metrics.language.es") : (t) => t("metrics.language.en");
}

export function eventName(event: LatencyEvent): Message {
  switch (event) {
    case "speech_end":
      return (t) => t("metrics.latency.event.speech_end");
    case "first_audio":
      return (t) => t("metrics.latency.event.first_audio");
    case "message_sent":
      return (t) => t("metrics.latency.event.message_sent");
    case "first_word":
      return (t) => t("metrics.latency.event.first_word");
  }
}

export function channelName(channel: LatencyMeasure["channel"]): Message {
  return channel === "voice" ? (t) => t("metrics.latency.voice") : (t) => t("metrics.latency.chat");
}

/**
 * Un tiempo como lo dice el panel: milisegundos bajo el segundo y decimas de segundo desde ahi.
 *
 * Redondea la mitad hacia arriba y con aritmetica sobre enteros, igual que el README generado
 * (`evidence/readme.py::_duration`): las dos superficies muestran el mismo texto para el mismo
 * tiempo, tambien en los empates.
 */
export function formatDuration(ms: number, locale: Locale): string {
  if (ms < 1000) {
    return `${String(ms)} ms`;
  }
  const decimas = Math.round(ms / 100) / 10;
  const segundos = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(decimas);
  return `${segundos} s`;
}
