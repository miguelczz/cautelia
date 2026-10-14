// Las frases que el servidor pide por su clave, resueltas con la clave escrita
// literal (BR3.4 de U13, C-21, C-29).
//
// Misma forma que `chat-copy.ts` y por la misma razon: el protocolo manda **la
// clave y no el texto**, para que una misma frase no acabe diciendose de dos
// maneras segun quien la resuelva. `t()` exige la clave literal, porque una clave
// armada en ejecucion no aparece en el chequeo de claves sin consumidor y
// entonces nadie sabe si una frase del catalogo sigue usandose.
//
// Es ademas **la lista de lo que la consola puede recibir**, que no existe en
// ningun otro sitio de este lado: el cuadro `notice` lleva una clave y esta tabla
// es todo lo que puede llevar.

import type { VoiceOffCode } from "../../shared/api-client/voice";
import type { CopyKey } from "../../shared/copy/copy-keys";
import type { Message } from "../../shared/i18n/translate";
import type { EndReason } from "./voice-events";

const AVISOS: Partial<Record<CopyKey, Message>> = {
  // La voz apagada por configuracion (U15, BR2.2). Llega como `reason_key` de la
  // disponibilidad, antes de que nadie pulse llamar.
  "voice.availability.not_configured": (t) => t("voice.availability.not_configured"),
  "voice.availability.misconfigured": (t) => t("voice.availability.misconfigured"),
  // El techo de gasto y los dos carriles diarios (C-08), cada uno con su frase
  // (2026-10-11). Los carriles tienen frase propia de la voz y no las `spend.quota.*`
  // de U5, que hablan del chat ("llegaste al limite de hoy"): el techo conserva la de
  // AC5.14.3, que ya era de la voz.
  "spend.quota.budget_exhausted": (t) => t("spend.quota.budget_exhausted"),
  "voice.availability.rate_limited_daily": (t) => t("voice.availability.rate_limited_daily"),
  "voice.availability.rate_limited_site": (t) => t("voice.availability.rate_limited_site"),
  // El aviso de que la llamada se acerca a su duracion maxima (U16).
  "voice.notice.time_running_out": (t) => t("voice.notice.time_running_out"),
  // Pasaron 24 horas sin un reinicio nocturno exitoso, asi que la demostracion
  // no acepta casos nuevos (BR3.2 de U20). Lo que ya estaba abierto termina: una
  // llamada que retoma su caso se sigue admitiendo, asi que esta frase solo
  // aparece antes de empezar una nueva.
  "demo.reset.surfaces_closed": (t) => t("demo.reset.surfaces_closed"),
};

/**
 * La frase de una clave que llego del servidor, o `null` si no se conoce.
 *
 * `null` y no una frase de repuesto: los avisos de esta pantalla son un conjunto
 * cerrado, asi que una clave desconocida es un contrato roto y no un caso de
 * ejecucion. Poner en su lugar la frase de error diria que la llamada se rompio
 * cuando lo que pasa es que el navegador va una version por detras.
 */
export function phraseFor(key: string): Message | null {
  return AVISOS[key as CopyKey] ?? null;
}

/** Las claves que la consola sabe decir. La usa su prueba para no copiarlas. */
export const KNOWN_KEYS = Object.keys(AVISOS) as readonly CopyKey[];

/**
 * La clave de cada motivo cerrado por el que no hay llamada, para cuando **abrirla**
 * es lo que se rechaza: el 503 trae el motivo como `code` y no como `reason_key`, que
 * es lo que trae la disponibilidad. Tabla sobre la union cerrada del servidor, asi que
 * un motivo nuevo que nadie anada aqui es un error de tipos y no una pantalla que
 * vuelve a decir "la voz esta apagada".
 *
 * Espeja `OFF_CODE_KEYS` del servidor, y una prueba del servidor comprueba que las dos
 * tablas digan lo mismo. `provider_unavailable` no tiene clave: la configuracion que
 * apago la voz la sabe la disponibilidad, no la apertura, y sin ella queda la frase
 * general.
 */
const CLAVE_DEL_MOTIVO: Readonly<Record<VoiceOffCode, CopyKey | null>> = {
  rate_limited_daily: "voice.availability.rate_limited_daily",
  rate_limited_site: "voice.availability.rate_limited_site",
  budget_exhausted: "spend.quota.budget_exhausted",
  provider_unavailable: null,
  demo_closed: "demo.reset.surfaces_closed",
};

/** La clave de la frase de un motivo de rechazo, o `null` si no hay una especifica. */
export function reasonKeyFor(code: string | null): CopyKey | null {
  if (code === null || !Object.hasOwn(CLAVE_DEL_MOTIVO, code)) {
    return null;
  }
  return CLAVE_DEL_MOTIVO[code as VoiceOffCode];
}

/**
 * Como se explica cada final (BR1.6).
 *
 * Cada motivo nombra su clave **en su propia rama**: una clave armada con
 * `` `voice.ended.${motivo}` `` seria mas corta y dejaria las cinco fuera del
 * chequeo de claves sin consumidor, que busca literales. Es la misma razon por la
 * que la tabla de motivos de cuota del servidor se escribe entera.
 */
export function endedPhrase(reason: EndReason): Message | null {
  switch (reason) {
    case "hangup":
      // Colgo la propia persona: el estado "Llamada terminada" ya lo dice, y avisarle
      // de lo que acaba de hacer era ruido (decision de Miguel, 2026-10-09).
      return null;
    case "silence":
      return (t) => t("voice.ended.silence");
    case "max_duration":
      return (t) => t("voice.ended.max_duration");
    case "dropped":
      return (t) => t("voice.ended.dropped");
    case "error":
      return (t) => t("voice.ended.error");
    case "completed":
      return (t) => t("voice.ended.completed");
    case "handed_off":
      return (t) => t("voice.ended.handed_off");
    case "saved":
      return (t) => t("voice.ended.saved");
  }
}
