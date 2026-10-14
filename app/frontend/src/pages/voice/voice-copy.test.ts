import { describe, expect, it } from "vitest";

import type { CopyKey, Locale } from "../../shared/copy/copy-keys";
import EN from "../../shared/copy/copy-texts.en";
import ES from "../../shared/copy/copy-texts.es";

const COPY_TEXTS = new Map<Locale, typeof ES>([
  ["es", ES],
  ["en", EN],
]);
import type { Translate } from "../../shared/i18n/translate";
import { endedPhrase, KNOWN_KEYS, phraseFor, reasonKeyFor } from "./voice-copy";
import type { EndReason } from "./voice-events";

// La tabla es la lista de lo que la consola puede recibir. Lo que se comprueba es
// que cada entrada apunte a una frase que existe en los dos idiomas, que los seis
// motivos de final tengan la suya, y que una clave desconocida no invente nada.
//
// Que la tabla cubra **todo** lo que el servidor manda no se comprueba aqui: eso
// lo mira `mise run voice:frases`, que lee las tablas del servidor y este archivo.
// Una lista copiada a mano en los dos sitios se separa.

function frases(locale: Locale): ReadonlyMap<CopyKey, string> {
  const mapa = COPY_TEXTS.get(locale);
  if (mapa === undefined) {
    throw new Error(`el catalogo no trae el idioma ${locale}`);
  }
  return mapa;
}

const traducir: Translate = (key) => frases("es").get(key) ?? key;

const MOTIVOS: readonly EndReason[] = [
  "silence",
  "max_duration",
  "dropped",
  "error",
  "completed",
  "handed_off",
  "saved",
];

describe("los avisos que el servidor pide por su clave", () => {
  it("cada clave de la tabla existe en el catalogo, en los dos idiomas", () => {
    const faltan = KNOWN_KEYS.filter(
      (clave) => !frases("es").has(clave) || !frases("en").has(clave),
    );

    expect(faltan).toEqual([]);
    // La lista no esta vacia: si lo estuviera, lo de arriba no probaria nada.
    expect(KNOWN_KEYS.length).toBeGreaterThan(0);
  });

  it("resuelve la frase de una clave conocida, y no la clave", () => {
    // El catalogo devuelve la clave misma cuando falta, asi que una prueba que
    // solo mirara que devuelve algo pasaria con cualquier cosa.
    const frase = phraseFor("voice.notice.time_running_out")?.(traducir);

    expect(frase).not.toBe("voice.notice.time_running_out");
    expect(frase).toBe(frases("es").get("voice.notice.time_running_out"));
  });

  it("una clave desconocida devuelve nulo y no una frase de repuesto", () => {
    // Los avisos de esta pantalla son un conjunto cerrado: una clave que no esta
    // es un contrato roto, no un caso de ejecucion. Poner la frase de error en su
    // lugar diria que la llamada se rompio cuando lo que pasa es que el navegador
    // va una version por detras.
    expect(phraseFor("una.clave.que.el.navegador.no.conoce")).toBeNull();
  });
});

describe("el motivo de un rechazo al abrir la llamada", () => {
  const MOTIVOS = [
    "rate_limited_daily",
    "rate_limited_site",
    "budget_exhausted",
    "demo_closed",
  ] as const;

  function claveDe(motivo: string): CopyKey {
    const clave = reasonKeyFor(motivo);
    if (clave === null) {
      throw new Error(`el motivo ${motivo} no tiene clave propia`);
    }
    return clave;
  }

  it("cada motivo con frase propia apunta a una clave que existe en los dos idiomas", () => {
    for (const motivo of MOTIVOS) {
      const clave = claveDe(motivo);
      expect(frases("es").has(clave), motivo).toBe(true);
      expect(frases("en").has(clave), motivo).toBe(true);
      // Y la consola sabe decir esa clave cuando llega como `reason_key`.
      expect(phraseFor(clave), motivo).not.toBeNull();
    }
  });

  it("los cuatro dicen cosas distintas, en los dos idiomas", () => {
    for (const idioma of ["es", "en"] as const) {
      const dichas = MOTIVOS.map((motivo) => frases(idioma).get(claveDe(motivo)));
      expect(new Set(dichas).size, idioma).toBe(MOTIVOS.length);
    }
  });

  it("la voz apagada por configuracion y lo desconocido no tienen frase propia", () => {
    // La configuracion que apago la voz la sabe la disponibilidad, no la apertura.
    expect(reasonKeyFor("provider_unavailable")).toBeNull();
    expect(reasonKeyFor("internal")).toBeNull();
    expect(reasonKeyFor("un_motivo_que_este_navegador_no_conoce")).toBeNull();
    expect(reasonKeyFor(null)).toBeNull();
    // Y un nombre del prototipo no se confunde con un motivo.
    expect(reasonKeyFor("constructor")).toBeNull();
  });
});

describe("como se explica cada final", () => {
  it("los siete motivos con aviso tienen su frase, en los dos idiomas", () => {
    for (const motivo of MOTIVOS) {
      const frase = endedPhrase(motivo)?.(traducir);
      expect(frase, motivo).not.toBe("");
      expect(frase, motivo).toBe(frases("es").get(`voice.ended.${motivo}` as CopyKey));
      expect(frases("en").has(`voice.ended.${motivo}` as CopyKey), motivo).toBe(true);
    }
  });

  it("colgar no lleva aviso: lo hizo la propia persona", () => {
    expect(endedPhrase("hangup")).toBeNull();
  });

  it("los siete dicen cosas distintas", () => {
    // Una llamada que se corta y una que se completa no pueden explicarse igual:
    // con dos motivos compartiendo frase, el conjunto cerrado dejaria de servir
    // para lo unico que existe, que es decir **por que** termino.
    const dichas = MOTIVOS.map((motivo) => endedPhrase(motivo)?.(traducir));

    expect(new Set(dichas).size).toBe(MOTIVOS.length);
  });
});
