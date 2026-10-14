// Las frases que el servidor pide por su clave, resueltas con la clave escrita
// literal (BR3.4, C-21).
//
// C-04 manda **la clave y no el texto** de la espera, de la derivacion, del error
// y de los limites, para que una misma frase no acabe diciendose de dos maneras
// segun quien la resuelva. Del otro lado hace falta traducirla, y `t()` exige la
// clave literal: una clave armada en ejecucion no aparece en el chequeo de claves
// sin consumidor, y entonces nadie sabe si una frase del catalogo sigue usandose.
//
// De ahi esta tabla. Es ademas **la lista de lo que el chat puede recibir**, que
// no existia en ningun sitio: ahora se lee de un vistazo.
//
// Una clave que no este aqui cae en la frase de error. No es un descarte
// silencioso: la conversacion dice algo en vez de quedarse con un hueco, que es
// el modo de fallo que REL-U13.1 existe para impedir.
//
// **Desde el 2026-10-12 la clave ya no viaja sola**: la espera, la derivacion y el
// error traen tambien su texto, resuelto por el servidor en el idioma del turno. La
// pantalla usa esta tabla cuando conoce la clave --una frase no se dice de dos
// maneras-- y ese texto cuando no la conoce, y solo si el evento no lo trae cae en
// la frase de error. Antes una clave nueva del servidor se leia como "tuve un
// problema para responder eso" aunque el caso ya estuviera derivado. El chequeo
// `mise run chat:frases` falla ademas si el servidor puede mandar una clave que esta
// tabla no tiene.

import type { CopyKey } from "../../shared/copy/copy-keys";
import type { Message } from "../../shared/i18n/translate";

const FRASES: Partial<Record<CopyKey, Message>> = {
  // El ritmo del turno (U12).
  "chat.turn.waiting": (t) => t("chat.turn.waiting"),
  "chat.turn.error": (t) => t("chat.turn.error"),
  // La frase de degradacion que declara el nodo de captura
  // (`INTAKE_SPEC.degraded_copy_key`). Hasta el 2026-10-06 era la de calma de
  // BR5.4, que habla de insultos: ante un modelo lento la persona leia un reproche
  // y ninguna salida. Ahora es una frase propia que dice lo que paso y pide
  // repetir. Un chequeo del catalogo compara esta tabla contra lo que los cuatro
  // nodos declaran, para que cambiar la frase de un nodo sin decirla aqui falle
  // en la compuerta y no en pantalla (es lo que paso al cambiarla, y lo atrapo).
  "intake.degraded": (t) => t("intake.degraded"),
  "intake.tone.calm": (t) => t("intake.tone.calm"),
  // La derivacion y la guardia de salida (U10, U12).
  "compliance.handoff.adjuster_review": (t) => t("compliance.handoff.adjuster_review"),
  // La misma derivacion en una consulta, donde nadie "conto" nada (2026-10-08).
  "compliance.handoff.adjuster_review_inquiry": (t) =>
    t("compliance.handoff.adjuster_review_inquiry"),
  // El cierre por insultos: el caso queda para un ajustador.
  "intake.tone.closing_abuse": (t) => t("intake.tone.closing_abuse"),
  "compliance.guard.degraded": (t) => t("compliance.guard.degraded"),
  "compliance.closure.direct": (t) => t("compliance.closure.direct"),
  "compliance.emergency.local": (t) => t("compliance.emergency.local"),
  "compliance.emergency.public": (t) => t("compliance.emergency.public"),
  // La respuesta de cobertura que no cito nada (U8).
  "policy_rag.coverage.no_clause_found": (t) => t("policy_rag.coverage.no_clause_found"),
  "policy_rag.coverage.unverifiable": (t) => t("policy_rag.coverage.unverifiable"),
  // Los cinco limites del chat (BR3.1). Los mismos que la tabla cerrada del
  // servidor, que es donde se decide cual sale.
  "spend.quota.rate_limited_session": (t) => t("spend.quota.rate_limited_session"),
  "spend.quota.rate_limited_daily": (t) => t("spend.quota.rate_limited_daily"),
  "chat.limit.site_day": (t) => t("chat.limit.site_day"),
  "chat.limit.rate": (t) => t("chat.limit.rate"),
  "chat.limit.size": (t) => t("chat.limit.size"),
  // La demostracion estrechada: 24 horas sin un reinicio nocturno exitoso, asi
  // que no se abren casos nuevos (BR3.2 de U20). Sin esta linea el visitante
  // leeria "tuve un problema para responder eso", que es la frase de error y
  // ademas no es cierta: el chat esta en pie y lo que no se puede es empezar.
  "demo.reset.surfaces_closed": (t) => t("demo.reset.surfaces_closed"),
};

/** La frase de una clave que llego del servidor, o la de error si no se conoce. */
export function phraseFor(key: string): Message {
  return FRASES[key as CopyKey] ?? ((t) => t("chat.turn.error"));
}

/** Si esta pantalla sabe decir esa clave con su propio catalogo. */
export function isKnownKey(key: string): boolean {
  return key in FRASES;
}

/** Las claves que el chat sabe decir. La usa su prueba para no copiarlas. */
export const KNOWN_KEYS = Object.keys(FRASES) as readonly CopyKey[];
