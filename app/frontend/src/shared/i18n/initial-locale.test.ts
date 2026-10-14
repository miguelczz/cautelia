import { afterEach, describe, expect, it, vi } from "vitest";

import {
  browserLanguages,
  deviceLocale,
  initialLanguageChoice,
  LOCALE_STORAGE_KEY,
  readSharedLocale,
  readStoredLocale,
  SHARED_LOCALE_KEY,
  storeLocale,
} from "./initial-locale";

// BR2.1: una pagina sin aseguradora se abre en espanol si el primer idioma del
// navegador empieza por espanol, y en ingles en cualquier otro caso.

afterEach(() => {
  vi.restoreAllMocks();
});

describe("el idioma inicial de una pagina sin aseguradora", () => {
  it.each([
    [["es-CO", "en-US"], "es"],
    [["es"], "es"],
    [["ES-mx"], "es"],
    [["en-US", "es-CO"], "en"],
    [["fr-FR"], "en"],
    [[], "en"],
  ] as const)("con %j es %s", (idiomas, esperado) => {
    expect(deviceLocale(idiomas)).toBe(esperado);
  });

  it("lee los idiomas preferidos del navegador en su orden", () => {
    vi.spyOn(navigator, "languages", "get").mockReturnValue(["es-CO", "en"]);
    expect(browserLanguages()).toEqual(["es-CO", "en"]);
    expect(initialLanguageChoice(browserLanguages())).toEqual({ locale: "es", source: "device" });

    vi.spyOn(navigator, "languages", "get").mockReturnValue([]);
    vi.spyOn(navigator, "language", "get").mockReturnValue("fr-FR");
    expect(browserLanguages()).toEqual(["fr-FR"]);
  });
});

describe("el idioma recordado", () => {
  it("guarda y lee solo es o en", () => {
    expect(storeLocale("es")).toBe(true);
    expect(readStoredLocale()).toBe("es");

    window.localStorage.setItem(LOCALE_STORAGE_KEY, "pt");
    expect(readStoredLocale()).toBeNull();
  });

  it("al guardar tambien deja el idioma para la landing", () => {
    storeLocale("en");
    expect(readSharedLocale()).toBe("en");
    window.localStorage.setItem(SHARED_LOCALE_KEY, "fr");
    expect(readSharedLocale()).toBeNull();
  });

  it("abre en la eleccion, si no en la landing, si no en el dispositivo", () => {
    expect(initialLanguageChoice(["es-CO"])).toEqual({ locale: "es", source: "device" });

    window.localStorage.setItem(SHARED_LOCALE_KEY, "en");
    expect(initialLanguageChoice(["es-CO"])).toEqual({ locale: "en", source: "device" });

    window.localStorage.setItem(LOCALE_STORAGE_KEY, "es");
    window.localStorage.removeItem(SHARED_LOCALE_KEY);
    expect(initialLanguageChoice(["en-US"])).toEqual({ locale: "es", source: "persisted" });
  });

  it("con eleccion, manda el valor compartido: es el mas reciente", () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "es");
    window.localStorage.setItem(SHARED_LOCALE_KEY, "en");
    expect(initialLanguageChoice(["es-CO"])).toEqual({ locale: "en", source: "persisted" });
  });

  it("un almacenamiento bloqueado no rompe nada", () => {
    vi.spyOn(console, "info").mockImplementation(() => undefined);
    const bloqueado = () =>
      ({
        getItem: () => {
          throw new DOMException("blocked", "SecurityError");
        },
        setItem: () => {
          throw new DOMException("blocked", "SecurityError");
        },
      }) as unknown as Storage;

    expect(readStoredLocale(bloqueado)).toBeNull();
    expect(storeLocale("en", bloqueado)).toBe(false);
  });
});
