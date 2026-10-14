// Lo que la persona escribio y lo que la agente le dijo, guardado en su propio
// navegador (fase 0, 2026-10-07; movido a `shared/` el 2026-10-12).
//
// La base guarda cada mensaje con los datos personales tapados --es una regla de
// seguridad del proyecto: el chat es publico y alguien puede escribir datos reales
// aunque se le pida que no--. Al recargar, el historial llega tapado y la persona
// veia "[NOMBRE 1]" en su propia burbuja (E6 de los hallazgos). El navegador guarda
// una copia de lo que escribio, solo en este navegador, y la pone de vuelta en su
// burbuja. Desde el 2026-10-08 la copia sobrevive a cerrar la pestana y volver otro
// dia (decision de Miguel): en otro dispositivo se sigue viendo tapado.
//
// **Es de toda pantalla propia** (2026-10-12, cuarta vez que lo pide Miguel): el chat,
// la llamada que lo escribe, "Ver mi caso" y el pensamiento de la agente leen de aqui.
// La bandeja del ajustador, que entra con credencial de personal, no: ahi sigue tapado.
//
// **Nunca se pone un texto en la burbuja equivocada**: una copia solo reemplaza un
// mensaje tapado si encaja con su forma, letra por letra fuera de las etiquetas.

/** Una etiqueta de la redaccion: `[NOMBRE 1]`, `[PLATE 2]`. */
const ETIQUETA = /\[[^[\]]+? \d+\]/g;

/** Cuantos mensajes se recuerdan por aseguradora: los de una conversacion larga. */
const MAXIMO = 60;

function clave(tenantId: string): string {
  return `cautelia.own-text.${tenantId}`;
}

function leerLista(llave: string): string[] {
  try {
    const crudo = window.localStorage.getItem(llave);
    const valor: unknown = crudo === null ? [] : JSON.parse(crudo);
    return Array.isArray(valor) ? valor.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function anotar(llave: string, texto: string): void {
  try {
    const todos = [...leerLista(llave), texto].slice(-MAXIMO);
    window.localStorage.setItem(llave, JSON.stringify(todos));
  } catch {
    // Sin almacenamiento se muestra lo guardado, tapado: no es un error.
  }
}

/** Lo que la persona escribio en este navegador, del mas viejo al mas nuevo. */
export function recall(tenantId: string): string[] {
  return leerLista(clave(tenantId));
}

/** Anota un mensaje recien enviado. Si el navegador no deja guardar, no pasa nada. */
export function remember(tenantId: string, text: string): void {
  anotar(clave(tenantId), text);
}

// **Lo que dijo la agente, tambien** (2026-10-09). La base guarda tapado lo que
// redacta el modelo, y el detector confunde palabras corrientes con datos ("Abajo te
// dejo el texto" volvia como "[LUGAR 1] te dejo"). Al volver, la conversacion se lee
// como se leyo: este navegador ya la vio entera. La base sigue tapada.
function claveDeLaAgente(tenantId: string): string {
  return `cautelia.agent-text.${tenantId}`;
}

/** Lo que la agente dijo en este navegador, del mas viejo al mas nuevo. */
export function recallAgent(tenantId: string): string[] {
  return leerLista(claveDeLaAgente(tenantId));
}

/** Anota una respuesta recien recibida. Si el navegador no deja guardar, no pasa nada. */
export function rememberAgent(tenantId: string, text: string): void {
  anotar(claveDeLaAgente(tenantId), text);
}

/** Olvida lo escrito y lo respondido: la conversacion empezo de cero. */
export function forget(tenantId: string): void {
  try {
    window.localStorage.removeItem(clave(tenantId));
    window.localStorage.removeItem(claveDeLaAgente(tenantId));
  } catch {
    // Igual que arriba.
  }
}

/** Si el mensaje guardado trae alguna etiqueta de la redaccion. */
export function isMasked(text: string): boolean {
  return /\[[^[\]]+? \d+\]/.test(text);
}

/**
 * Si un texto encaja con la forma de un mensaje tapado: los trozos de fuera de las
 * etiquetas aparecen en orden y tal cual, y cada etiqueta cubre al menos un
 * caracter. Sin expresiones armadas con el texto de fuera: se recorre con indices.
 */
function fits(masked: string, candidate: string): boolean {
  const trozos = masked.split(ETIQUETA);
  const primero = trozos[0] ?? "";
  const ultimo = trozos.at(-1) ?? "";
  if (!candidate.startsWith(primero) || !candidate.endsWith(ultimo)) {
    return false;
  }
  let desde = primero.length;
  const fin = candidate.length - ultimo.length;
  for (const trozo of trozos.slice(1, -1)) {
    const donde = candidate.indexOf(trozo, desde + 1);
    if (donde === -1 || donde + trozo.length > fin) {
      return false;
    }
    desde = donde + trozo.length;
  }
  return fin - desde >= 1;
}

/**
 * El texto propio que corresponde a un mensaje tapado, o `null`.
 *
 * Entre varias copias que encajen se toma la mas reciente que no se haya usado:
 * dos mensajes iguales se reparten en orden.
 */
export function restore(
  masked: string,
  candidates: readonly string[],
  used: Set<number>,
): string | null {
  if (!isMasked(masked)) {
    return null;
  }
  for (const [i, candidato] of [...candidates.entries()].reverse()) {
    if (!used.has(i) && fits(masked, candidato)) {
      used.add(i);
      return candidato;
    }
  }
  return null;
}

// --- Para las pantallas que leen un caso guardado (2026-10-12) -------------------------

/** Las dos listas de este navegador para una aseguradora. */
export interface OwnTexts {
  /** Lo que la persona escribio o dijo. */
  readonly visitor: readonly string[];
  /** Lo que la agente le contesto. */
  readonly agent: readonly string[];
}

/** Lo que este navegador recuerda de la conversacion de una aseguradora. */
export function recallAll(tenantId: string): OwnTexts {
  return { visitor: recall(tenantId), agent: recallAgent(tenantId) };
}

/** Un turno de un caso guardado, con quien lo dijo. `other` nunca se destapa. */
export interface StoredTurn {
  readonly id: string;
  readonly speaker: "visitor" | "agent" | "other";
  /** El texto como lo guardo la base: con las etiquetas de la redaccion. */
  readonly text: string;
}

/**
 * El texto propio de cada turno tapado que tenga copia, por identificador del turno.
 *
 * Se recorre del ultimo al primero porque lo guardado en este navegador es lo mas
 * reciente: el caso puede traer mensajes de antes que este navegador nunca vio. Lo
 * que dijo la persona se busca en lo que ella escribio, y lo que dijo la agente en lo
 * que la agente contesto; un turno de otra voz no se toca.
 */
export function restoreTurns(
  turns: readonly StoredTurn[],
  own: OwnTexts,
): ReadonlyMap<string, string> {
  const usadosDeLaPersona = new Set<number>();
  const usadosDeLaAgente = new Set<number>();
  const restaurados = new Map<string, string>();
  for (const turno of [...turns].reverse()) {
    const propio =
      turno.speaker === "visitor"
        ? restore(turno.text, own.visitor, usadosDeLaPersona)
        : turno.speaker === "agent"
          ? restore(turno.text, own.agent, usadosDeLaAgente)
          : null;
    if (propio !== null) {
      restaurados.set(turno.id, propio);
    }
  }
  return restaurados;
}

/**
 * Cada texto tapado de una lista de preguntas, con su copia propia si la hay.
 *
 * Devuelve una lista del mismo largo y en el mismo orden: lo que no tiene copia que
 * encaje queda como llego. Cada pregunta usa una copia distinta (las mas nuevas
 * primero), igual que los turnos.
 */
export function restoreAll(masked: readonly string[], candidates: readonly string[]): string[] {
  const usados = new Set<number>();
  const restaurados = new Map<number, string>();
  for (const [i, original] of [...masked.entries()].reverse()) {
    restaurados.set(i, restore(original, candidates, usados) ?? original);
  }
  return masked.map((original, i) => restaurados.get(i) ?? original);
}
