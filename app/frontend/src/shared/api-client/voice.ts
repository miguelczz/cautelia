// Las tres puertas de la llamada hacia el servidor, y la direccion del socket
// (C-08, C-29).
//
// Igual que `chat.ts`: ninguna pantalla importa el cliente generado, todo pasa
// por aqui. **El socket no va por el cliente generado** y no por descuido:
// `WebSocket` es del navegador y no hay nada que generar. Lo unico que se
// construye aqui es su direccion, para que no quede escrita en una pantalla.
//
// **El token no entra en esa direccion.** Lo manda el primer cuadro de texto una
// vez abierta (BR1.4): un token en la cadena de consulta acaba en los registros
// del servidor y en el historial del navegador, y de ahi no se saca.

import {
  endVoiceCall,
  handOffVoiceCase,
  openVoiceCall,
  voiceAvailability,
  voiceCallOutcome,
  type Availability,
  type CallOpened,
  type CallOutcome,
  type ProblemCode,
  type VoiceOffCode,
} from "../api";

export type { Availability, CallOpened, CallOutcome, VoiceOffCode };

/**
 * La direccion del socket de una aseguradora, **absoluta y con el esquema del
 * documento**.
 *
 * `WebSocket` no admite una ruta relativa, asi que hay que componerla; se compone
 * del origen actual y no de una configuracion, porque el socket es del mismo
 * origen que la interfaz por contrato (ADR-001). Sobre una pagina servida por
 * `https` sale `wss`, que es lo unico que los navegadores aceptan desde ahi.
 */
export function voiceSocketUrl(path: string, origin?: string): string {
  const base = origin ?? globalThis.location.origin;
  const url = new URL(path, base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

/** Si hay voz ahora mismo, con que modo y con que limites (BR1.1). */
export async function availability(tenantId: string): Promise<Availability | null> {
  const { data, error } = await voiceAvailability({ path: { tenant_id: tenantId } });
  return error === undefined ? data : null;
}

/** Lo que devolvio abrir la llamada: la sesion, o por que no se pudo. */
export type OpenOutcome =
  | { readonly outcome: "opened"; readonly call: CallOpened }
  /**
   * `code` es el motivo cerrado que dijo el servidor (`rate_limited_daily`,
   * `rate_limited_site`, `budget_exhausted`, `provider_unavailable`, `demo_closed`), o
   * `null` si el cuerpo del error no traia uno que esta version conozca.
   */
  | { readonly outcome: "unavailable"; readonly code: ProblemCode | null }
  | { readonly outcome: "failed" };

/**
 * El `code` de un error, si el cuerpo es un problema de C-01. Un 503 de un proxy llega
 * como HTML y no trae ninguno: entonces es `null`, y la pantalla dice lo general.
 */
function problemCodeOf(error: unknown): ProblemCode | null {
  if (typeof error !== "object" || error === null || !("code" in error)) {
    return null;
  }
  return typeof error.code === "string" ? (error.code as ProblemCode) : null;
}

/**
 * Abre la llamada. **Se llama despues de tener el microfono**, nunca antes
 * (BR1.2): al reves, un permiso negado dejaria un caso vacio en la bandeja de una
 * ajustadora.
 */
export async function openCall(tenantId: string, language?: string): Promise<OpenOutcome> {
  const { data, error, response } = await openVoiceCall({
    path: { tenant_id: tenantId },
    // Sin idioma cuando nadie eligio: el servidor usa el de la aseguradora
    // (BR1.1). Mandar el idioma que la pestana adopto por defecto seria decirle
    // "eligio esto", y desde ese momento el servidor no podria distinguir una
    // eleccion de una omision.
    body: language === undefined ? {} : { language: language as "es" | "en" },
  });
  if (error !== undefined) {
    // 503 es "hoy no hay voz" y tiene su propia pantalla; cualquier otra cosa es
    // un fallo. Distinguirlos importa: uno se explica y el otro se reintenta. Y el
    // **motivo** viaja con el: antes se tiraba y toda negativa se leia "la voz esta
    // apagada", fuera un limite diario, el cupo del sitio o el techo de gasto.
    return response?.status === 503
      ? { outcome: "unavailable", code: problemCodeOf(error) }
      : { outcome: "failed" };
  }
  return { outcome: "opened", call: data };
}

/**
 * Cierra la llamada desde fuera del socket.
 *
 * Es el camino de respaldo: colgar manda su cuadro por el socket, que es lo que
 * deja al servidor cerrar el caso con el motivo correcto. Esto existe para cuando
 * el socket ya no esta.
 */
export async function endCall(tenantId: string, callId: string): Promise<void> {
  await endVoiceCall({ path: { tenant_id: tenantId, call_id: callId } });
}

/**
 * Donde quedo el caso de esta llamada (BR3.4), o `null` si no se puede saber.
 *
 * `null` y no un error: la llamada puede no ser de este navegador, y entonces
 * responde lo mismo que una que no existe. La consola no distingue las dos
 * porque el servidor tampoco.
 */
export async function callOutcome(tenantId: string, callId: string): Promise<CallOutcome | null> {
  const { data, error } = await voiceCallOutcome({
    path: { tenant_id: tenantId, call_id: callId },
  });
  return error !== undefined ? null : data;
}

/**
 * Pasa el caso a una persona, a peticion de quien llamo (BR3.4).
 *
 * Devuelve donde quedo, que es lo que la consola dibuja. `null` cuando no se
 * pudo: la pantalla sigue ofreciendo la salida en vez de decir que ya esta hecha.
 */
export async function handOffCase(tenantId: string, callId: string): Promise<CallOutcome | null> {
  const { data, error } = await handOffVoiceCase({
    path: { tenant_id: tenantId, call_id: callId },
  });
  return error !== undefined ? null : data;
}
