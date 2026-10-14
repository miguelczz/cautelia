import { afterEach, describe, expect, it, vi } from "vitest";

import { COPY_KEYS, type CopyKey } from "../copy/copy-keys";
import type { Locale } from "../copy/copy-keys";
import EN from "../copy/copy-texts.en";
import ES from "../copy/copy-texts.es";

const COPY_TEXTS = new Map<Locale, typeof ES>([
  ["es", ES],
  ["en", EN],
]);
import { createTranslate, formatCopy, MissingCopyVariableError } from "./translate";

// BR2.3 y C-21: todo texto sale del catalogo por una clave tipada, en los dos
// idiomas; lo que falta se nota, nunca es una cadena vacia.

afterEach(() => {
  vi.restoreAllMocks();
});

describe("t()", () => {
  it("devuelve la frase del catalogo en cada idioma", () => {
    expect(createTranslate("es")("status.not_found.title")).toBe(
      COPY_TEXTS.get("es")?.get("status.not_found.title"),
    );
    expect(createTranslate("en")("status.not_found.title")).toBe(
      COPY_TEXTS.get("en")?.get("status.not_found.title"),
    );
    expect(createTranslate("es")("status.not_found.title")).not.toBe(
      createTranslate("en")("status.not_found.title"),
    );
  });

  it("los dos idiomas tienen frase para cada clave del modulo tipado (paridad)", () => {
    for (const idioma of ["es", "en"] as const) {
      const frases = COPY_TEXTS.get(idioma);
      const faltan = COPY_KEYS.filter((clave) => !frases?.has(clave));
      expect(faltan).toEqual([]);
    }
  });

  it("sustituye las variables de la frase", () => {
    expect(createTranslate("es")("home.action.chat_with", { insurer: "Seguros Aburrá" })).toBe(
      "Abrir chat con Seguros Aburrá",
    );
  });

  it("una variable que falta falla ruidosamente, nombrando la clave", () => {
    expect(() => createTranslate("en")("home.action.chat_with")).toThrow(MissingCopyVariableError);
    expect(() => formatCopy("home.action.voice_with", "Call {insurer}", { otra: "x" })).toThrow(
      /home\.action\.voice_with/,
    );
  });

  it("una entrada que falta devuelve la clave misma y lo dice en la consola", () => {
    const consola = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const inexistente = "shell.no_existe" as CopyKey;

    expect(createTranslate("es")(inexistente)).toBe("shell.no_existe");
    expect(consola).toHaveBeenCalledOnce();
  });
});
