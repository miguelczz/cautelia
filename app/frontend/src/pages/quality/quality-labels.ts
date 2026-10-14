// Los textos del tablero de calidad que dependen de un dato cerrado: cada uno con su
// clave literal dentro de un `switch`, como el de gasto. Lo que el servidor manda
// fuera del conjunto conocido tiene su frase generica, nunca el valor crudo.

import type { GateFamily } from "../../shared/api-client/quality";
import type { Message } from "../../shared/i18n/translate";

export function datasetName(dataset: string): Message {
  switch (dataset) {
    case "DS-2":
      return (t) => t("quality.dataset.ds2.name");
    case "DS-3":
      return (t) => t("quality.dataset.ds3.name");
    case "DS-4":
      return (t) => t("quality.dataset.ds4.name");
    case "DS-6":
      return (t) => t("quality.dataset.ds6.name");
    case "DS-8":
      return (t) => t("quality.dataset.ds8.name");
    default:
      return (t) => t("quality.dataset.other.name");
  }
}

export function datasetHelp(dataset: string): Message {
  switch (dataset) {
    case "DS-2":
      return (t) => t("quality.dataset.ds2.help");
    case "DS-3":
      return (t) => t("quality.dataset.ds3.help");
    case "DS-4":
      return (t) => t("quality.dataset.ds4.help");
    case "DS-6":
      return (t) => t("quality.dataset.ds6.help");
    case "DS-8":
      return (t) => t("quality.dataset.ds8.help");
    default:
      return (t) => t("quality.dataset.other.help");
  }
}

export function gateName(family: GateFamily): Message {
  switch (family) {
    case "citations":
      return (t) => t("quality.gate.citations");
    case "no_promises":
      return (t) => t("quality.gate.no_promises");
    case "personal_data":
      return (t) => t("quality.gate.personal_data");
    case "isolation":
      return (t) => t("quality.gate.isolation");
    case "conduct":
      return (t) => t("quality.gate.conduct");
    case "content":
      return (t) => t("quality.gate.content");
  }
}

export function rootCause(cause: string | null | undefined): Message {
  switch (cause) {
    case "extraction":
      return (t) => t("quality.cause.extraction");
    case "retrieval":
      return (t) => t("quality.cause.retrieval");
    case "verification":
      return (t) => t("quality.cause.verification");
    case "rules":
      return (t) => t("quality.cause.rules");
    case "style":
      return (t) => t("quality.cause.style");
    case "latency":
      return (t) => t("quality.cause.latency");
    case "provider_error":
      return (t) => t("quality.cause.provider_error");
    case "infrastructure":
      return (t) => t("quality.cause.infrastructure");
    case "not_built":
      return (t) => t("quality.cause.not_built");
    default:
      return (t) => t("quality.cause.unknown");
  }
}

export function notMeasuredReason(cause: string): Message {
  switch (cause) {
    case "provider_unavailable":
      return (t) => t("quality.pending.provider_unavailable");
    case "provider_timeout":
      return (t) => t("quality.pending.provider_timeout");
    case "quota_exhausted":
      return (t) => t("quality.pending.quota_exhausted");
    case "budget_exhausted":
      return (t) => t("quality.pending.budget_exhausted");
    case "runner_timeout":
      return (t) => t("quality.pending.runner_timeout");
    case "provider_key_missing":
      return (t) => t("quality.pending.provider_key_missing");
    case "target_unavailable":
      return (t) => t("quality.pending.target_unavailable");
    default:
      return (t) => t("quality.pending.other");
  }
}
