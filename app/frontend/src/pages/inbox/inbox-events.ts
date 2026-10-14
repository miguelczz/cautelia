// Los avisos en vivo de la bandeja, aplicados sobre lo que la pantalla ya tiene
// (C-06, BR6.1, BR6.2).
//
// **Se aplica el cambio, no se vuelve a pedir todo.** Un aviso dice que un caso
// cambio; la cola mueve ese caso y deja los demas donde estan. Volver a pedir la
// pagina entera con cada aviso convertiria una bandeja con actividad en una
// pantalla que parpadea.
//
// **Lo que el aviso no dice, no se inventa.** Un `case_created` de un caso que la
// pagina no tiene no se dibuja a medias con los campos que el evento trae: se
// marca que la cola quedo atras, y la pantalla ofrece traer lo nuevo. La
// alternativa era pedir la pagina sola en cuanto llega el aviso, y con varios
// avisos seguidos eso es una peticion por aviso.
//
// La reconexion la hace el navegador con `Last-Event-ID`, no este archivo: el
// servidor reproduce lo posterior a ese identificador, asi que no hace falta
// guardar nada aqui para no perder lo ocurrido mientras la conexion estuvo caida.

import type { QueueItem } from "../../shared/api-client/inbox";

/** Los tres tipos de aviso de C-06. Conjunto cerrado. */
export type InboxEventKind = "case_created" | "case_updated" | "case_decided";

/** Un aviso tal como llega por el cable. */
export interface WireInboxEvent {
  readonly kind: InboxEventKind;
  readonly case_id: string;
  /** Ya redactado al escribirse (BR6.3). La pantalla no lo destapa. */
  readonly summary: string;
  readonly at: string;
}

/** Lo que la cola tiene en pantalla, mas lo que los avisos han dicho de ella. */
export interface QueueState {
  readonly items: readonly QueueItem[];
  readonly nextCursor: string | null;
  /** Casos de los que llego un aviso y que esta pagina no tiene. */
  readonly staleCaseIds: readonly string[];
}

export const EMPTY_QUEUE: QueueState = { items: [], nextCursor: null, staleCaseIds: [] };

/** La cola tal como la devolvio el servidor. Borra lo que los avisos habian marcado. */
export function withPage(items: readonly QueueItem[], nextCursor: string | null): QueueState {
  return { items, nextCursor, staleCaseIds: [] };
}

/** Anade la pagina siguiente al final, sin tocar el orden que decidio el servidor. */
export function withMore(state: QueueState, page: QueueState): QueueState {
  return {
    items: [...state.items, ...page.items],
    nextCursor: page.nextCursor,
    staleCaseIds: state.staleCaseIds,
  };
}

/**
 * Aplica un aviso a la cola.
 *
 * Un caso que la pagina tiene y que **se decidio** sale de la lista: la cola es de
 * casos esperando decision, y dejarlo con su fila vieja diria que sigue esperando.
 * Un caso que la pagina tiene y que cambio queda marcado como atrasado por su
 * identificador, porque el aviso no trae la fila nueva. Y uno que la pagina no
 * tiene se marca igual, sin dibujarse: media fila es peor que ninguna.
 */
export function reduceQueue(state: QueueState, event: WireInboxEvent): QueueState {
  const tiene = state.items.some((fila) => fila.case_id === event.case_id);
  if (event.kind === "case_decided" && tiene) {
    return {
      ...state,
      items: state.items.filter((fila) => fila.case_id !== event.case_id),
      staleCaseIds: state.staleCaseIds.filter((id) => id !== event.case_id),
    };
  }
  if (state.staleCaseIds.includes(event.case_id)) {
    return state;
  }
  return { ...state, staleCaseIds: [...state.staleCaseIds, event.case_id] };
}

/** Si un aviso habla del caso que la vista tiene abierto. */
export function touchesCase(event: WireInboxEvent, caseId: string): boolean {
  return event.case_id === caseId;
}

/**
 * Lee un aviso del cable. Devuelve `null` si no tiene la forma de C-06.
 *
 * Nunca lanza: un aviso mal formado no puede tumbar la pantalla de quien esta
 * decidiendo un caso. Queda en la consola, que es donde sirve.
 */
export function parseEvent(data: string): WireInboxEvent | null {
  let crudo: unknown;
  try {
    crudo = JSON.parse(data);
  } catch {
    console.warn("untangle: an inbox event arrived that is not JSON");
    return null;
  }
  if (typeof crudo !== "object" || crudo === null) {
    return null;
  }
  const candidato = crudo as Partial<WireInboxEvent>;
  const conocidos: readonly InboxEventKind[] = ["case_created", "case_updated", "case_decided"];
  if (
    typeof candidato.case_id !== "string" ||
    typeof candidato.summary !== "string" ||
    typeof candidato.at !== "string" ||
    candidato.kind === undefined ||
    !conocidos.includes(candidato.kind)
  ) {
    console.warn("untangle: an inbox event arrived without the shape of C-06", crudo);
    return null;
  }
  return {
    kind: candidato.kind,
    case_id: candidato.case_id,
    summary: candidato.summary,
    at: candidato.at,
  };
}
