// Los errores de la API dichos en palabras (entidad ProblemView; BR3.2 a BR3.4).
//
// **Una sola tabla** lleva cada codigo de C-01 a su texto del catalogo, y tiene
// una rama por defecto obligatoria: un codigo que esta version de la interfaz no
// conoce se muestra como "servicio no disponible", nunca como pantalla vacia ni
// como texto crudo (BR3.3). Lo que no es un error de C-01 --red caida, tiempo
// agotado, un cuerpo HTML en lugar de JSON-- es `unknown` con el mismo texto
// (BR3.4).
//
// El titulo, el detalle y la traza del error **solo** van a la consola del
// navegador (BR3.2): son para quien depura, no para quien usa la demo.

import type { Problem, ProblemCode } from "../api";
import type { Message } from "../i18n/translate";

export type ProblemViewCode = ProblemCode | "unknown";

export interface ProblemView {
  readonly code: ProblemViewCode;
  /** El texto del catalogo que se muestra, con su clave escrita literal. */
  readonly message: Message;
  /** Cuando reintentar, si el servidor lo dijo. */
  readonly retryAfterS?: number;
}

const SERVICE_UNAVAILABLE: Message = (t) => t("problem.service_unavailable");

/**
 * La tabla. Es un `Record` sobre la union cerrada de C-01, asi que un codigo
 * nuevo en el esquema que nadie anada aqui es un error de tipos, no un texto que
 * falta. Los cuatro limites de uso reutilizan las frases de U5.
 */
const PROBLEM_MESSAGES: Readonly<Record<ProblemCode, Message>> = {
  validation_failed: (t) => t("problem.validation_failed"),
  not_found: (t) => t("problem.not_found"),
  forbidden_origin: (t) => t("problem.forbidden_origin"),
  link_invalid: (t) => t("problem.link_invalid"),
  conflict_idempotency: (t) => t("problem.conflict"),
  // Distinto de la de arriba a proposito: "ya lo hiciste" y "esto ya no se
  // puede" son dos cosas, y decirle la primera a quien llego tarde a decidir
  // le diria que su decision se aplico.
  conflict_state: (t) => t("problem.conflict_state"),
  rate_limited_session: (t) => t("spend.quota.rate_limited_session"),
  rate_limited_daily: (t) => t("spend.quota.rate_limited_daily"),
  rate_limited_site: (t) => t("spend.quota.rate_limited_site"),
  budget_exhausted: (t) => t("spend.quota.budget_exhausted"),
  provider_timeout: SERVICE_UNAVAILABLE,
  provider_unavailable: SERVICE_UNAVAILABLE,
  unverifiable: (t) => t("problem.unverifiable"),
  // La demostracion no acepta casos nuevos: pasaron 24 horas sin un reinicio
  // nocturno exitoso (BR3.2 de U20). Lleva **la frase de U20** y no la de
  // servicio no disponible, porque el servicio esta en pie: lo que no se puede
  // es empezar un caso nuevo, y lo que ya estaba abierto sigue.
  demo_closed: (t) => t("demo.reset.surfaces_closed"),
  internal: SERVICE_UNAVAILABLE,
};

const PROBLEM_TABLE: ReadonlyMap<string, Message> = new Map(Object.entries(PROBLEM_MESSAGES));

function isProblem(error: unknown): error is Problem {
  if (typeof error !== "object" || error === null) {
    return false;
  }
  const candidato = error as Partial<Record<keyof Problem, unknown>>;
  return (
    typeof candidato.code === "string" &&
    typeof candidato.trace_id === "string" &&
    typeof candidato.status === "number"
  );
}

/** El texto de un codigo de la tabla, o la rama por defecto. */
export function problemMessage(code: string): Message {
  return PROBLEM_TABLE.get(code) ?? SERVICE_UNAVAILABLE;
}

/**
 * Lo que ve la persona de un error cualquiera del cliente. Nunca lanza: el
 * error ya ocurrio, y esta funcion solo decide como decirlo.
 */
export function toProblemView(error: unknown): ProblemView {
  if (!isProblem(error)) {
    console.warn("untangle: an API call failed without a C-01 error body", error);
    return { code: "unknown", message: SERVICE_UNAVAILABLE };
  }

  console.warn(
    `untangle: API error ${error.code} (${String(error.status)}), trace ${error.trace_id}`,
    { title: error.title, detail: error.detail },
  );

  const conocido = PROBLEM_TABLE.get(error.code);
  if (conocido === undefined) {
    // BR3.3: el codigo se registra en la consola y la persona ve la rama por
    // defecto.
    console.warn(`untangle: unknown C-01 code "${error.code}", shown as service unavailable`);
  }

  const vista: ProblemView = {
    code: conocido === undefined ? "unknown" : error.code,
    message: conocido ?? SERVICE_UNAVAILABLE,
  };
  return typeof error.retry_after_s === "number"
    ? { ...vista, retryAfterS: error.retry_after_s }
    : vista;
}

/**
 * Si un error dice que se perdio la conexion con el proceso: una red caida o una
 * espera agotada, no una respuesta del servidor. Es lo que devuelve la espera a
 * "comprobando" (functional-spec 2.1).
 */
export function isConnectivityFailure(error: unknown): boolean {
  if (error instanceof TypeError) {
    return true;
  }
  return (
    error instanceof DOMException && (error.name === "TimeoutError" || error.name === "AbortError")
  );
}
