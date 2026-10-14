import { describe, expect, it } from "vitest";

import EN from "../../shared/copy/copy-texts.en";
import ES from "../../shared/copy/copy-texts.es";

const COPY_TEXTS = new Map<Locale, typeof ES>([
  ["es", ES],
  ["en", EN],
]);
import type { CopyKey, Locale } from "../../shared/copy/copy-keys";
import type { Translate } from "../../shared/i18n/translate";
import { isKnownKey, KNOWN_KEYS, phraseFor } from "./chat-copy";

// La tabla es la lista de lo que el chat puede recibir. Lo que se comprueba es
// que cada entrada apunte a una frase que existe en los dos idiomas, y que una
// clave desconocida no deje la conversacion con un hueco.

function frases(locale: Locale): ReadonlyMap<CopyKey, string> {
  const mapa = COPY_TEXTS.get(locale);
  if (mapa === undefined) {
    throw new Error(`el catalogo no trae el idioma ${locale}`);
  }
  return mapa;
}

const traducir: Translate = (key) => frases("es").get(key) ?? key;

describe("las frases que el servidor pide por su clave", () => {
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
    const frase = phraseFor("chat.limit.rate")(traducir);

    expect(frase).not.toBe("chat.limit.rate");
    expect(frase).toBe(frases("es").get("chat.limit.rate"));
  });

  it("una clave desconocida cae en la frase de error y no en un hueco", () => {
    // Un hueco deja la conversacion sin decir nada, que es el modo de fallo que
    // REL-U13.1 existe para impedir.
    const frase = phraseFor("una.clave.que.el.navegador.no.conoce")(traducir);

    expect(frase).toBe(frases("es").get("chat.turn.error"));
  });

  it.each([
    // La derivacion de una consulta: el servidor la estreno y la tabla no la tenia, y
    // quien pidio un ajustador leyo la frase de error con el caso ya derivado.
    "compliance.handoff.adjuster_review_inquiry",
    "compliance.handoff.adjuster_review",
    // El cierre por insultos.
    "intake.tone.closing_abuse",
  ])("%s se dice con su propia frase y no con la de error", (clave) => {
    expect(isKnownKey(clave)).toBe(true);
    const frase = phraseFor(clave)(traducir);

    expect(frase).not.toBe(frases("es").get("chat.turn.error"));
    expect(frase).toBe(frases("es").get(clave as CopyKey));
  });

  it("sabe decir cuando no conoce una clave", () => {
    expect(isKnownKey("una.clave.que.el.navegador.no.conoce")).toBe(false);
    expect(isKnownKey("chat.turn.error")).toBe(true);
  });
});
