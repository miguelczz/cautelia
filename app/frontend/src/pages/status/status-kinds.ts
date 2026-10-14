// Los seis tipos de pagina de estado de M11, con una sola plantilla (entidad
// StatusPageKind; BR5.5). Cada uno tiene su titulo, su explicacion y una accion,
// y ninguno muestra un codigo, una traza ni el nombre de una aseguradora.
//
// "La demo esta despertando" ya no es una pagina de estado: mientras el proceso
// despierta se dibuja el esqueleto de la pantalla pedida, sin texto (decision de
// Miguel, 2026-10-06). "No disponible" si queda: es una falla de verdad.

import type { Message } from "../../shared/i18n/translate";

export type StatusPageKind =
  | "unavailable"
  | "link_invalid"
  | "link_expired"
  | "data_reset"
  | "not_found"
  | "service_unavailable";

export type StatusAction =
  "external_links" | "go_home" | "back_to_conversation" | "start_over" | "retry";

export interface StatusCopy {
  readonly title: Message;
  readonly body: Message;
  readonly action: StatusAction;
}

/**
 * El titulo, la explicacion y la accion de cada tipo. Un `switch` exhaustivo y no
 * un objeto indexado por el tipo: el compilador exige los siete casos, y ninguna
 * propiedad se busca con una clave calculada.
 */
export function statusCopy(kind: StatusPageKind): StatusCopy {
  switch (kind) {
    case "unavailable":
      return {
        title: (t) => t("status.unavailable.title"),
        body: (t) => t("status.unavailable.body"),
        action: "external_links",
      };
    case "link_invalid":
      return {
        title: (t) => t("status.link_invalid.title"),
        body: (t) => t("status.link_invalid.body"),
        action: "go_home",
      };
    case "link_expired":
      return {
        title: (t) => t("status.link_expired.title"),
        body: (t) => t("status.link_expired.body"),
        action: "back_to_conversation",
      };
    case "data_reset":
      return {
        title: (t) => t("status.data_reset.title"),
        body: (t) => t("status.data_reset.body"),
        action: "start_over",
      };
    case "not_found":
      return {
        title: (t) => t("status.not_found.title"),
        body: (t) => t("status.not_found.body"),
        action: "go_home",
      };
    case "service_unavailable":
      return {
        title: (t) => t("status.service_unavailable.title"),
        body: (t) => t("status.service_unavailable.body"),
        action: "retry",
      };
  }
}

export const STATUS_PAGE_KINDS = [
  "unavailable",
  "link_invalid",
  "link_expired",
  "data_reset",
  "not_found",
  "service_unavailable",
] as const satisfies readonly StatusPageKind[];

/**
 * Los tipos a los que se llega por una ruta (`/status/$kind`). "No disponible" **no**:
 * es un estado de la espera del proceso, y abrirlo por una direccion mostraria
 * "Reintentar" en una pagina que no espera nada.
 */
export const ROUTED_STATUS_KINDS = [
  "link_invalid",
  "link_expired",
  "data_reset",
  "not_found",
  "service_unavailable",
] as const satisfies readonly StatusPageKind[];

export type RoutedStatusKind = (typeof ROUTED_STATUS_KINDS)[number];

export function parseRoutedStatusKind(value: string): RoutedStatusKind | null {
  return (ROUTED_STATUS_KINDS as readonly string[]).includes(value)
    ? (value as RoutedStatusKind)
    : null;
}
