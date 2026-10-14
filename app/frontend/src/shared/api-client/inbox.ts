// Las puertas de la bandeja hacia el servidor (C-05, C-06, C-07).
//
// Igual que `chat.ts` y `site.ts`: ninguna pantalla importa el cliente generado,
// todo pasa por aqui. Las cinco primeras van por el cliente generado; **el flujo
// no**, porque `EventSource` es del navegador y no tiene cliente que generar. Lo
// unico que se construye aqui es su direccion, para que no quede escrita en una
// pantalla.
//
// **La aseguradora viaja en la direccion y no elige nada** (BR1.4). El servidor la
// toma de la credencial y solo comprueba que coincida; una credencial de otra
// aseguradora recibe exactamente lo que recibe una ilegible. Esta capa no intenta
// compensarlo ni adivinar de quien es la credencial: lo que llega, llega.

import {
  annotateInboxCaseTriage,
  correctInboxCaseField,
  decideInboxCase,
  getInboxCase,
  listInboxCases,
  redeemCaseLink,
  type Answer,
  type CaseDetailOut,
  type CaseFieldView,
  type CaseState,
  type Channel,
  type CitationView,
  type CoverageAnswerOut,
  type ExplanationOut,
  type InboxAction,
  type Priority,
  type QueueItem,
  type QueuePage,
  type RecordType,
  type RedeemOut,
  type TranscriptTurnView,
  type TriageNoteIn,
  type TriageNoteOut,
  type TriageNoteView,
} from "../api";
import { toProblemView, type ProblemView } from "./problems";

// Los tipos del cable se reexportan desde aqui y las pantallas los toman de aqui:
// el contrato de fronteras prohibe que una pantalla importe el cliente generado, y
// con razon --toda llamada tiene que pasar por la tabla que convierte un error en
// texto del catalogo--. Reexportar el **tipo** no abre esa puerta y evita copiar la
// forma del cable a mano, que es como una copia se queda atras.
export type {
  Answer,
  CaseDetailOut,
  CaseFieldView,
  CaseState,
  Channel,
  CitationView,
  CoverageAnswerOut,
  ExplanationOut,
  InboxAction,
  Priority,
  QueueItem,
  QueuePage,
  RecordType,
  RedeemOut,
  TranscriptTurnView,
  TriageNoteIn,
  TriageNoteOut,
  TriageNoteView,
};

/** Lo que devuelve una llamada de la bandeja: el dato, o el error ya en palabras. */
export type InboxResult<T> =
  { readonly ok: true; readonly value: T } | { readonly ok: false; readonly problem: ProblemView };

function fallo<T>(error: unknown): InboxResult<T> {
  return { ok: false, problem: toProblemView(error) };
}

/** Los cuatro filtros de la cola, tal como viven en la direccion (C-05). */
export interface QueueFilters {
  readonly state?: string;
  readonly channel?: string;
  readonly language?: string;
  readonly priority?: string;
}

/**
 * Una pagina de la cola (BR1.1, BR1.2).
 *
 * El orden lo decide el servidor y esta capa no lo toca: dos personas mirando la
 * misma cola tienen que ver lo mismo, y una pantalla que reordenara por su cuenta
 * seria una segunda regla de orden escrita en otro sitio.
 */
export async function listCases(
  tenantId: string,
  filters: QueueFilters,
  cursor?: string,
): Promise<InboxResult<QueuePage>> {
  const { data, error } = await listInboxCases({
    path: { tenant_id: tenantId },
    query: {
      ...(filters.state === undefined ? {} : { state: filters.state }),
      ...(filters.channel === undefined ? {} : { channel: filters.channel }),
      ...(filters.language === undefined ? {} : { language: filters.language }),
      ...(filters.priority === undefined ? {} : { priority: filters.priority }),
      ...(cursor === undefined ? {} : { cursor }),
    },
  });
  return error === undefined ? { ok: true, value: data } : fallo(error);
}

/** El caso con sus seis bloques (BR2.2). Sirve a las dos puertas: credencial y enlace. */
export async function caseDetail(
  tenantId: string,
  caseId: string,
): Promise<InboxResult<CaseDetailOut>> {
  const { data, error } = await getInboxCase({
    path: { tenant_id: tenantId, case_id: caseId },
  });
  return error === undefined ? { ok: true, value: data } : fallo(error);
}

/**
 * Corrige un campo (BR3.1 a BR3.4).
 *
 * La clave de idempotencia es **obligatoria** y la pone quien llama: un segundo
 * envio del formulario sin ella escribiria una segunda correccion, que es el dano
 * real que la idempotencia existe para evitar.
 */
export async function correctField(
  tenantId: string,
  caseId: string,
  fieldKey: string,
  value: string,
  idempotencyKey: string,
): Promise<InboxResult<{ readonly receipt_id: string }>> {
  const { data, error } = await correctInboxCaseField({
    path: { tenant_id: tenantId, case_id: caseId, field_key: fieldKey },
    headers: { "Idempotency-Key": idempotencyKey },
    body: { value },
  });
  return error === undefined ? { ok: true, value: data } : fallo(error);
}

/**
 * Anota el monto estimado, la cobertura disputada y la sospecha de fraude (2026-10-13).
 *
 * Manda los tres datos siempre: `null` es «sin anotar», y es lo que permite quitar algo
 * ya anotado. La clave de idempotencia es **obligatoria** y la pone quien llama, igual que
 * al corregir un campo: un segundo envio del formulario sin ella escribiria otra evaluacion.
 * El servidor guarda lo anotado, deja su entrada en el historial y vuelve a evaluar las
 * reglas; esta capa no hace nada de eso. Sirve a las dos puertas, igual que `decideCase`: la
 * credencial de personal y la cookie del caso del visitante, que anota solo el suyo.
 *
 * Devuelve lo que las reglas dijeron con la anotacion (`rule_category`, `fired_rules`) para
 * que la pantalla del visitante lo diga en su sitio. `receipt_id` es `null` cuando quien
 * guardo es un visitante y guardo lo que ya estaba: no se escribio nada.
 */
export async function annotateTriage(
  tenantId: string,
  caseId: string,
  note: TriageNoteIn,
  idempotencyKey: string,
): Promise<InboxResult<TriageNoteOut>> {
  const { data, error } = await annotateInboxCaseTriage({
    path: { tenant_id: tenantId, case_id: caseId },
    headers: { "Idempotency-Key": idempotencyKey },
    body: note,
  });
  return error === undefined ? { ok: true, value: data } : fallo(error);
}

/**
 * Decide un caso (BR4.1 a BR4.6).
 *
 * Responde `202`: la decision queda escrita y la reanudacion del grafo corre de
 * fondo. Esperarla colgaria la pantalla de quien decidio por el tiempo que tarde
 * una conversacion en continuar.
 */
export async function decideCase(
  tenantId: string,
  caseId: string,
  decision: InboxAction,
  comment: string,
  idempotencyKey: string,
): Promise<InboxResult<{ readonly decision_id: string; readonly resolution: string }>> {
  const { data, error } = await decideInboxCase({
    path: { tenant_id: tenantId, case_id: caseId },
    headers: { "Idempotency-Key": idempotencyKey },
    body: { decision, comment },
  });
  return error === undefined ? { ok: true, value: data } : fallo(error);
}

/**
 * Canjea el token del enlace por la cookie de caso (C-07, BR5.2, BR5.6).
 *
 * Las cuatro causas de rechazo responden lo mismo, asi que aqui tampoco se
 * distinguen: un mensaje distinto por causa le diria a quien prueba enlaces cual
 * de sus intentos acerto el identificador.
 */
export async function redeemLink(token: string): Promise<InboxResult<RedeemOut>> {
  const { data, error } = await redeemCaseLink({ body: { token } });
  return error === undefined ? { ok: true, value: data } : fallo(error);
}

/** La direccion del flujo de avisos de una aseguradora. La credencial viaja sola. */
export function inboxStreamUrl(tenantId: string): string {
  return `/api/inbox/${encodeURIComponent(tenantId)}/stream`;
}

/**
 * Abre el flujo de avisos (C-06, BR6.1, BR6.2).
 *
 * `EventSource` y no una peticion en streaming, por lo mismo que el chat: es lo que
 * reconecta solo con `Last-Event-ID` cuando la red se cae, que es lo que BR6.2 pide
 * y lo que el `retry:` del servidor configura. El navegador lo manda **solo**, sin
 * que esta capa lo administre.
 */
export function openInboxStream(tenantId: string): EventSource {
  return new EventSource(inboxStreamUrl(tenantId));
}
