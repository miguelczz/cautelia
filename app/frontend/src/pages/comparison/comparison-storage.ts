// Lo que la comparacion recuerda en este navegador: la pregunta y lo que contesto
// cada aseguradora, para que recargar o ir a otra pagina y volver no lo pierda.
//
// **Solo en el navegador de quien pregunto**, igual que el texto propio del chat
// (`own-text.ts`): la pregunta la escribio esa persona y las respuestas ya llegaron
// redactadas. Vence a las 24 horas porque los datos de la demostracion se reinician
// cada noche: una comparacion que sobreviviera al reinicio citaria clausulas de un
// caso que ya no existe.
//
// **Sin almacenamiento la pagina funciona igual**: cada acceso va dentro de un
// `try`, y un registro que no se puede leer, que esta vencido o que no encaja con la
// forma esperada se descarta entero. Nunca se pinta a medias.
//
// Lo que sigue en vuelo vive aparte, en memoria (`inFlight`): una pregunta que
// termina mientras la persona esta en otra pagina se guarda igual, y al volver la
// columna la encuentra respondida en vez de "interrumpida".

import type { Locale } from "../../shared/copy/copy-keys";
import type { MessageRejected } from "../../shared/api-client/chat";
import type { WireCitation } from "../chat/chat-events";
import {
  settleColumn,
  type ColumnAnswer,
  type ColumnOutcome,
  type ComparisonColumn,
} from "./comparison-state";

/**
 * La clave lleva su version: si cambia la forma de lo guardado, se cambia aqui.
 *
 * **v2 (2026-10-12).** Lo guardado con `v1` tiene las citas sin su rotulo traducido ni el
 * numero de condicion especial: se veia con rotulos en ingles y "Endosos". Se sube la
 * version para que lo viejo se descarte entero y no se muestre a medias. Las versiones
 * anteriores se borran en cuanto se lee (`CLAVES_VIEJAS`): sin eso quedarian en el
 * navegador para siempre.
 */
const CLAVE = "cautelia.comparison.v2";

/** Las claves de versiones anteriores, que ya no se leen y se borran. */
const CLAVES_VIEJAS = ["cautelia.comparison.v1"];

/** Cuanto dura lo guardado. */
export const VIGENCIA_MS = 24 * 60 * 60 * 1000;

/** Cuanto adelanto se tolera en la hora guardada antes de darla por corrupta. */
const TOLERANCIA_RELOJ_MS = 60_000;

export interface SavedComparison {
  /** Cuando se pregunto, en milisegundos; ademas es el identificador de la consulta. */
  readonly askedAt: number;
  /** El idioma de la pantalla cuando se pregunto. */
  readonly locale: Locale;
  readonly question: string;
  readonly columns: readonly ComparisonColumn[];
}

// --- Lectura con forma comprobada --------------------------------------------------

type Registro = Readonly<Record<string, unknown>>;

function esRegistro(valor: unknown): valor is Registro {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

function esIdioma(valor: unknown): valor is Locale {
  return valor === "es" || valor === "en";
}

const LIMITES: readonly MessageRejected["limit"][] = [
  "session",
  "origin",
  "site_day",
  "rate",
  "size",
];

function leerLimite(valor: unknown): MessageRejected["limit"] | null {
  return LIMITES.find((limite) => limite === valor) ?? null;
}

function leerCita(valor: unknown): WireCitation | null {
  if (!esRegistro(valor)) {
    return null;
  }
  const { clause_id, clause_version, part, text, clause_language, amount_deferred, trace_ref } =
    valor;
  if (
    typeof clause_id !== "string" ||
    typeof clause_version !== "string" ||
    typeof part !== "string" ||
    typeof text !== "string" ||
    !esIdioma(clause_language) ||
    typeof amount_deferred !== "boolean"
  ) {
    return null;
  }
  // Lo opcional tambien se guarda: sin esto, al recargar la clausula de una poliza en
  // otro idioma perdia su traduccion y una condicion especial volvia a rotularse por la
  // parte del corpus.
  const { translated_text, translated_part, special_condition_number } = valor;
  return {
    clause_id,
    clause_version,
    part,
    text,
    clause_language,
    amount_deferred,
    trace_ref: typeof trace_ref === "string" ? trace_ref : "",
    ...(typeof translated_text === "string" ? { translated_text } : {}),
    ...(typeof translated_part === "string" ? { translated_part } : {}),
    ...(typeof special_condition_number === "number" ? { special_condition_number } : {}),
  };
}

function leerRespuesta(valor: unknown): ColumnAnswer | null {
  if (!esRegistro(valor) || !esIdioma(valor.language)) {
    return null;
  }
  const language = valor.language;
  if (valor.kind === "no_clause") {
    return { kind: "no_clause", language };
  }
  if (valor.kind !== "cited" || typeof valor.text !== "string" || !Array.isArray(valor.citations)) {
    return null;
  }
  const citations: WireCitation[] = [];
  for (const cruda of valor.citations as unknown[]) {
    const cita = leerCita(cruda);
    if (cita === null) {
      return null;
    }
    citations.push(cita);
  }
  return { kind: "cited", language, text: valor.text, citations };
}

function leerColumna(valor: unknown): ComparisonColumn | null {
  if (!esRegistro(valor) || typeof valor.tenantId !== "string") {
    return null;
  }
  const tenantId = valor.tenantId;
  switch (valor.state) {
    // `idle` no se guarda nunca: una consulta guardada ya tiene su pregunta.
    case "loading":
      return { tenantId, state: "loading" };
    case "failed":
      return { tenantId, state: "failed" };
    case "interrupted":
      return { tenantId, state: "interrupted" };
    case "rejected": {
      const limit = leerLimite(valor.limit);
      return limit === null || typeof valor.copyKey !== "string"
        ? null
        : { tenantId, state: "rejected", limit, copyKey: valor.copyKey };
    }
    case "answered": {
      const answer = leerRespuesta(valor.answer);
      return answer === null ? null : { tenantId, state: "answered", answer };
    }
    default:
      return null;
  }
}

/** Lo guardado como objeto de la pagina, o `null` si no tiene la forma esperada. */
function leerConsulta(valor: unknown): SavedComparison | null {
  if (
    !esRegistro(valor) ||
    typeof valor.askedAt !== "number" ||
    !Number.isFinite(valor.askedAt) ||
    !esIdioma(valor.locale) ||
    typeof valor.question !== "string" ||
    valor.question.trim() === "" ||
    !Array.isArray(valor.columns) ||
    valor.columns.length === 0
  ) {
    return null;
  }
  const columns: ComparisonColumn[] = [];
  for (const cruda of valor.columns as unknown[]) {
    const columna = leerColumna(cruda);
    if (columna === null) {
      return null;
    }
    columns.push(columna);
  }
  return { askedAt: valor.askedAt, locale: valor.locale, question: valor.question, columns };
}

// --- Acceso al almacenamiento ---------------------------------------------------------

function leer(): SavedComparison | null {
  try {
    for (const vieja of CLAVES_VIEJAS) {
      window.localStorage.removeItem(vieja);
    }
    const crudo = window.localStorage.getItem(CLAVE);
    return crudo === null ? null : leerConsulta(JSON.parse(crudo));
  } catch {
    return null;
  }
}

function escribir(consulta: SavedComparison): void {
  try {
    window.localStorage.setItem(CLAVE, JSON.stringify(consulta));
  } catch {
    // Sin almacenamiento o sin cupo la pagina sigue: solo no se recuerda.
  }
}

/** Olvida lo guardado: la persona empezo otra comparacion, o lo guardado ya no sirve. */
export function clearComparison(): void {
  try {
    window.localStorage.removeItem(CLAVE);
  } catch {
    // Igual que arriba.
  }
}

/**
 * Lo guardado que todavia sirve, o `null`.
 *
 * No sirve si esta vencido, si su hora viene del futuro, o si no habla de las
 * mismas aseguradoras que la pagina muestra ahora: las columnas se ordenan como la
 * pagina las ordena. Lo que no sirve se borra, para no volver a leerlo.
 */
export function loadComparison(now: number, tenantIds: readonly string[]): SavedComparison | null {
  const guardada = leer();
  if (guardada === null) {
    clearComparison();
    return null;
  }
  const edad = now - guardada.askedAt;
  const mismas =
    guardada.columns.length === tenantIds.length &&
    tenantIds.every((id) => guardada.columns.some((columna) => columna.tenantId === id));
  if (edad >= VIGENCIA_MS || edad < -TOLERANCIA_RELOJ_MS || !mismas) {
    clearComparison();
    return null;
  }
  const columns = tenantIds.flatMap((id) => guardada.columns.filter((c) => c.tenantId === id));
  return { ...guardada, columns };
}

export function saveComparison(consulta: SavedComparison): void {
  escribir(consulta);
}

/**
 * Cambia las columnas de la consulta guardada, **si sigue siendo la misma**. Una
 * respuesta que llega despues de que la persona empezo otra comparacion no pisa a
 * la nueva.
 */
export function updateComparison(
  askedAt: number,
  cambiar: (columns: readonly ComparisonColumn[]) => readonly ComparisonColumn[],
): void {
  const guardada = leer();
  if (guardada?.askedAt === askedAt) {
    escribir({ ...guardada, columns: cambiar(guardada.columns) });
  }
}

/** Lo que una respuesta deja en lo guardado. */
function saveOutcome(askedAt: number, tenantId: string, outcome: ColumnOutcome): void {
  if (outcome.kind === "out_of_scope" || outcome.kind === "demo_closed") {
    // No hubo nada que comparar: no queda una comparacion que recordar.
    if (leer()?.askedAt === askedAt) {
      clearComparison();
    }
    return;
  }
  updateComparison(askedAt, (columns) => settleColumn(columns, tenantId, outcome));
}

// --- Lo que sigue en vuelo ---------------------------------------------------------------

const enVuelo = new Map<string, Promise<ColumnOutcome>>();

function claveDeVuelo(askedAt: number, tenantId: string): string {
  return `${askedAt.toString()}:${tenantId}`;
}

/**
 * Anota una pregunta en vuelo y guarda su resultado en cuanto llega, **este la
 * pagina montada o no**. Quien la dibuja se engancha a la misma promesa aparte.
 */
export function trackInFlight(
  askedAt: number,
  tenantId: string,
  outcome: Promise<ColumnOutcome>,
): void {
  const clave = claveDeVuelo(askedAt, tenantId);
  enVuelo.set(clave, outcome);
  void outcome.then((resultado) => {
    if (enVuelo.get(clave) === outcome) {
      enVuelo.delete(clave);
    }
    saveOutcome(askedAt, tenantId, resultado);
  });
}

/** La pregunta de esa columna que todavia no termina, si la hay. */
export function inFlight(askedAt: number, tenantId: string): Promise<ColumnOutcome> | undefined {
  return enVuelo.get(claveDeVuelo(askedAt, tenantId));
}

/** Solo las pruebas: cada una empieza sin preguntas en vuelo de otra. */
export function forgetInFlight(): void {
  enVuelo.clear();
}
