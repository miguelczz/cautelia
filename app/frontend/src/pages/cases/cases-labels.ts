// Lo que la pagina "Casos" dice de un valor cerrado, en palabras llanas.
//
// Las etiquetas de estado, canal e idioma son las de la bandeja (`inbox-labels.ts`) y
// no se repiten aqui. Lo propio de esta pagina es lo que dice quien llega sin saber
// que es un caso: el tipo de caso en las palabras del chat ("Reporte de accidente" y
// no "Siniestro"), una linea por estado que cuenta que esta pasando, y cuanto falta.
//
// Son `switch` exhaustivos, como en la bandeja: un valor nuevo del esquema falla al
// compilar en vez de salir vacio en pantalla.

import type { CaseState, RecordType } from "../../shared/api-client/inbox";
import type { Message } from "../../shared/i18n/translate";

/** El tipo de caso en las palabras del chat. */
export function caseKindLabel(kind: RecordType): Message {
  switch (kind) {
    case "claim":
      return (t) => t("chat.page.case_kind_claim");
    case "coverage_inquiry":
      return (t) => t("chat.page.case_kind_inquiry");
    case "quote_request":
      return (t) => t("chat.page.case_kind_quote");
  }
}

/** Lo mismo para el caso propio, que el chat entrega como cadena: lo que no se conoce es "Tu caso". */
export function ownCaseKindLabel(kind: string | null | undefined): Message {
  switch (kind) {
    case "claim":
    case "coverage_inquiry":
    case "quote_request":
      return caseKindLabel(kind);
    default:
      return (t) => t("chat.page.case_kind_other");
  }
}

/** Los estados que la lista de ejemplos ofrece, en el camino de un caso. */
export const LISTED_STATES = [
  "capturing",
  "verifying",
  "deciding",
  "derived",
  "awaiting_insured",
  "closed",
] as const satisfies readonly CaseState[];

/** El estado de una cadena del cable, o nada si esta version no lo conoce. */
export function asCaseState(value: string): CaseState | undefined {
  const conocidos: readonly string[] = [...LISTED_STATES, "open"];
  return conocidos.includes(value) ? (value as CaseState) : undefined;
}

/**
 * Una linea que cuenta que esta pasando en ese estado. `open` no la tiene porque la
 * lista no lo ofrece: un caso recien abierto, sin nada dentro, no ensena que es un caso.
 */
export function stateHint(state: CaseState): Message | undefined {
  switch (state) {
    case "open":
      return undefined;
    case "capturing":
      return (t) => t("cases.group.capturing");
    case "verifying":
      return (t) => t("cases.group.verifying");
    case "deciding":
      return (t) => t("cases.group.deciding");
    case "derived":
      return (t) => t("cases.group.derived");
    case "awaiting_insured":
      return (t) => t("cases.group.awaiting_insured");
    case "closed":
      return (t) => t("cases.group.closed");
  }
}

/** Cuanto falta, dicho en palabras (las del chat). */
export function missingLabel(missing: number): Message {
  if (missing <= 0) {
    return (t) => t("chat.page.case_complete");
  }
  return missing === 1
    ? (t) => t("chat.page.case_missing_one")
    : (t) => t("chat.page.case_missing_many", { count: String(missing) });
}

/** Agrupa las filas por estado sin reordenarlas: el orden lo decide el servidor. */
export function groupByState<T extends { readonly state: CaseState }>(
  items: readonly T[],
): readonly { readonly state: CaseState; readonly items: readonly T[] }[] {
  const grupos: { state: CaseState; items: T[] }[] = [];
  for (const fila of items) {
    const ultimo = grupos.find((grupo) => grupo.state === fila.state);
    if (ultimo === undefined) {
      grupos.push({ state: fila.state, items: [fila] });
    } else {
      ultimo.items.push(fila);
    }
  }
  return grupos;
}
