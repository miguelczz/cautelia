// Las tres puertas del chat hacia el servidor (C-04, C-23).
//
// Igual que `site.ts`: ninguna pantalla importa el cliente generado, todo pasa
// por aqui. Las dos primeras van por el cliente generado; **el flujo no**, porque
// `EventSource` es del navegador y no tiene cliente que generar. Lo unico que se
// construye aqui es su direccion, para que no quede escrita en una pantalla.

import {
  chatCaseStatus,
  chatHistory,
  chatReasoning,
  chatTraceSummary,
  resetChatConversation,
  sendChatMessage,
  type ChatCaseStatus,
  type ChatHistory,
  type ChatReasoning,
  type DemoClosed,
  type MessageAccepted,
  type MessageOutOfScope,
  type MessageRejected,
  type TraceView,
} from "../api";

export type {
  ChatCaseStatus,
  ChatHistory,
  ChatReasoning,
  DemoClosed,
  MessageAccepted,
  MessageOutOfScope,
  MessageRejected,
  TraceView,
};

/** Desde que pantalla se conversa (U23, FD-U23-8). El chat no manda nada. */
export type ChatSurface = "chat" | "comparison";

/** La direccion del flujo de una aseguradora. La cookie viaja sola. */
export function chatStreamUrl(tenantId: string): string {
  return `/api/chat/${encodeURIComponent(tenantId)}/stream`;
}

/**
 * Abre el flujo de eventos de una conversacion (C-04).
 *
 * `EventSource` y no una peticion en streaming: es lo que reconecta solo con
 * `Last-Event-ID` cuando la red se cae, que es lo que ADR-021 pide y lo que el
 * `retry:` del servidor configura. Vive aqui, en la puerta, y no en la pantalla:
 * es la misma regla que el resto de las llamadas.
 */
export function openChatStream(tenantId: string): EventSource {
  return new EventSource(chatStreamUrl(tenantId));
}

/**
 * La conversacion de este navegador como el servidor la guardo (la apertura, los
 * turnos redactados y el numero del caso), para dibujarla al abrir la pantalla.
 *
 * **Se pide despues de que el flujo abrio**, no a la vez: la galleta del visitante
 * la pone la primera respuesta que llega, y dos peticiones sin galleta acabarian
 * en dos conversaciones distintas. `null` cuando no se pudo leer; la pantalla
 * sigue sin historial, que es lo que hacia antes de que esta ruta existiera.
 */
export async function history(tenantId: string, locale: Locale): Promise<ChatHistory | null> {
  // Con el idioma de la pantalla: una conversacion que no ha dicho nada se abre
  // en el, y la apertura sale en el (decision de Miguel, 2026-10-06).
  const { data, error } = await chatHistory({ path: { tenant_id: tenantId }, query: { locale } });
  return error !== undefined ? null : data;
}

/**
 * Donde va el caso de esta conversacion: numero, avance y enlace para abrirlo
 * (decision de Miguel, 2026-10-06: verlo mientras avanza, no al final). `null`
 * cuando todavia no hay caso o no se pudo leer; la pantalla no dibuja la linea.
 */
export async function caseStatus(tenantId: string): Promise<ChatCaseStatus | null> {
  const { data, error } = await chatCaseStatus({ path: { tenant_id: tenantId } });
  return error !== undefined ? null : (data ?? null);
}

/**
 * El pensamiento de la agente sobre el caso de este navegador (2026-10-09): que
 * entendio, que poliza confirmo, que anoto y que clausulas cito y verifico. `null`
 * sin caso o si no se pudo leer.
 */
export async function caseReasoning(
  tenantId: string,
  locale: Locale,
): Promise<ChatReasoning | null> {
  const { data, error } = await chatReasoning({
    path: { tenant_id: tenantId },
    query: { language: locale },
  });
  return error !== undefined ? null : (data ?? null);
}

/**
 * Empezar de cero (decision de Miguel, 2026-10-06): el servidor cierra la
 * conversacion --el caso queda guardado con su numero-- y devuelve la nueva, con
 * su apertura, en la misma forma que el historial. `null` si no se pudo.
 */
export async function resetConversation(
  tenantId: string,
  locale: Locale,
): Promise<ChatHistory | null> {
  const { data, error } = await resetChatConversation({
    path: { tenant_id: tenantId },
    query: { locale },
  });
  return error !== undefined ? null : data;
}

/** Lo que devolvio el envio: admitido, el limite que lo paro, o fuera de proposito. */
export type SendOutcome =
  | { readonly outcome: "accepted"; readonly accepted: MessageAccepted }
  | { readonly outcome: "rejected"; readonly rejected: MessageRejected }
  | { readonly outcome: "out_of_scope"; readonly outOfScope: MessageOutOfScope }
  /**
   * La demostracion no acepta casos nuevos: pasaron 24 horas sin un reinicio
   * nocturno exitoso (BR3.2 de U20). Lo que ya estaba abierto sigue, asi que esto
   * solo llega cuando el mensaje abriria un caso.
   */
  | { readonly outcome: "demo_closed"; readonly closed: DemoClosed }
  | { readonly outcome: "failed" };

/** El idioma de la pantalla, el que el selector de arriba tiene elegido. */
export type Locale = "es" | "en";

/** Lo que el envio puede llevar ademas del texto. Sin nada, es el chat de siempre. */
export interface SendOptions {
  readonly surface?: ChatSurface;
  /**
   * El idioma de la pantalla, como respaldo cuando el texto no trae senal. Desde
   * el 2026-10-06 lo manda tambien el chat (P2): la agente habla el idioma del
   * selector salvo que el mensaje diga claramente otro.
   */
  readonly locale?: Locale;
}

/**
 * Los tres rechazos se distinguen por su forma y no por su codigo: adivinarlo por
 * el estado obligaria a leer un numero que el cliente generado no entrega.
 *
 * **El de la demo cerrada se mira primero, y lleva `kind` justamente por eso.**
 * Los tres traen `copy_key`, asi que sin un campo propio el ultimo en llegar
 * seria indistinguible del de fuera de proposito: la pantalla diria "esa no es
 * una pregunta de cobertura" cuando lo que pasa es que la demo se estrecho.
 */
function _rechazo(cuerpo: MessageRejected | MessageOutOfScope | DemoClosed): SendOutcome {
  if ("kind" in cuerpo) {
    return { outcome: "demo_closed", closed: cuerpo };
  }
  return "limit" in cuerpo
    ? { outcome: "rejected", rejected: cuerpo }
    : { outcome: "out_of_scope", outOfScope: cuerpo };
}

/**
 * Manda un mensaje. Un limite alcanzado **no es un fallo**: vuelve con su clave
 * de catalogo, y la pantalla dice la frase del limite y no un error generico. Lo
 * mismo con un texto que no es pregunta de cobertura cuando se pregunta desde la
 * vista de comparacion (U23, Q3).
 */
export async function sendMessage(
  tenantId: string,
  text: string,
  options: SendOptions = {},
): Promise<SendOutcome> {
  const { data, error } = await sendChatMessage({
    path: { tenant_id: tenantId },
    body: { text, ...options },
  });
  // El 429 y el 409 llegan por `error` porque no son 2xx, y **estan declarados en
  // el esquema**: por eso se pueden distinguir por su forma en vez de adivinarlos.
  if (error !== undefined) {
    return "copy_key" in error ? _rechazo(error) : { outcome: "failed" };
  }
  return "copy_key" in data ? _rechazo(data) : { outcome: "accepted", accepted: data };
}

/**
 * El resumen de traza de una respuesta (BR4.3, BR4.4).
 *
 * `null` es la unica forma de decir que no hay nada que mostrar, y cubre las tres
 * causas: no existe, es de otra conversacion, es de otra aseguradora. La pantalla
 * no las distingue porque el servidor tampoco.
 */
export async function traceSummary(tenantId: string, traceId: string): Promise<TraceView | null> {
  const { data, error } = await chatTraceSummary({
    path: { tenant_id: tenantId, trace_id: traceId },
  });
  if (error !== undefined) {
    return null;
  }
  // `null` es lo que el propio contrato declara para las tres causas: no existe,
  // es de otra conversacion, es de otra aseguradora.
  return data ?? null;
}
