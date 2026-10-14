// Los textos del tablero de gasto que dependen de un dato cerrado: cada uno con su
// clave literal dentro de un `switch` exhaustivo, como el panel de cifras.

import type { BudgetStatus, ProviderName, SpendActivity } from "../../shared/api-client/spend";
import type { Message } from "../../shared/i18n/translate";

export function providerName(provider: ProviderName): Message {
  switch (provider) {
    case "gemini":
      return (t) => t("spend_panel.provider.gemini");
    case "deepgram":
      return (t) => t("spend_panel.provider.deepgram");
    case "cartesia":
      return (t) => t("spend_panel.provider.cartesia");
    case "anthropic":
      return (t) => t("spend_panel.provider.anthropic");
  }
}

/** Para que sirve cada proveedor, en palabras de quien usa la demo. */
export function providerRole(provider: ProviderName): Message {
  switch (provider) {
    case "gemini":
      return (t) => t("spend_panel.provider.gemini_role");
    case "deepgram":
      return (t) => t("spend_panel.provider.deepgram_role");
    case "cartesia":
      return (t) => t("spend_panel.provider.cartesia_role");
    case "anthropic":
      return (t) => t("spend_panel.provider.anthropic_role");
  }
}

/** Lo que dice el estado del techo. El estado lo decide el servidor, no esta pantalla (BR3.3). */
export function statusText(status: BudgetStatus): Message {
  switch (status) {
    case "ok":
      return (t) => t("spend_panel.status_value.ok");
    case "alerted":
      return (t) => t("spend_panel.status_value.alerted");
    case "exhausted":
      return (t) => t("spend_panel.status_value.exhausted");
    case "unmeasured":
      return (t) => t("spend_panel.status_value.unmeasured");
  }
}

export function activityName(activity: SpendActivity): Message {
  switch (activity) {
    case "calls":
      return (t) => t("spend_panel.activity.calls");
    case "chat":
      return (t) => t("spend_panel.activity.chat");
    case "quality_tests":
      return (t) => t("spend_panel.activity.quality_tests");
    case "policy_reading":
      return (t) => t("spend_panel.activity.policy_reading");
    case "operations":
      return (t) => t("spend_panel.activity.operations");
  }
}

export function activityHelp(activity: SpendActivity): Message {
  switch (activity) {
    case "calls":
      return (t) => t("spend_panel.activity.calls_help");
    case "chat":
      return (t) => t("spend_panel.activity.chat_help");
    case "quality_tests":
      return (t) => t("spend_panel.activity.quality_tests_help");
    case "policy_reading":
      return (t) => t("spend_panel.activity.policy_reading_help");
    case "operations":
      return (t) => t("spend_panel.activity.operations_help");
  }
}

/** El color de cada actividad en las graficas: un token del tema, nunca un valor suelto. */
export function activityColor(activity: SpendActivity): string {
  switch (activity) {
    case "calls":
      return "var(--ut-chart-calls)";
    case "chat":
      return "var(--ut-chart-chat)";
    case "quality_tests":
      return "var(--ut-chart-tests)";
    case "policy_reading":
    case "operations":
      return "var(--ut-chart-reading)";
  }
}

/** El orden fijo de las series: el mismo en la grafica, la leyenda y la dona. */
export const ACTIVITIES: readonly SpendActivity[] = [
  "calls",
  "chat",
  "quality_tests",
  "policy_reading",
  "operations",
];

/** Que fue el caso. El valor viene del servidor como texto; uno desconocido se dice como reclamo. */
export function caseTypeName(recordType: string): Message {
  if (recordType === "coverage_inquiry") {
    return (t) => t("spend_panel.cases.type_coverage_inquiry");
  }
  if (recordType === "quote_request") {
    return (t) => t("spend_panel.cases.type_quote_request");
  }
  return (t) => t("spend_panel.cases.type_claim");
}

export function channelName(channel: string): Message {
  return channel === "voice"
    ? (t) => t("spend_panel.cases.channel_voice")
    : (t) => t("spend_panel.cases.channel_chat");
}
