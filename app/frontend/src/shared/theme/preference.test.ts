import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyTheme,
  DEFAULT_THEME,
  parseThemeMode,
  readStoredTheme,
  resolveTheme,
  storeTheme,
  THEME_STORAGE_KEY,
  themeFromDocument,
} from "./preference";
import { DARK_QUERY, stubMatchMedia } from "./testing";

// BR1.1 (enmendada 2026-10-06), BR1.4, REL-U6.2: el modo sale de la eleccion
// guardada o, sin ella, es el oscuro de la landing --nunca el del dispositivo--,
// y un almacenamiento roto nunca produce un error visible.

function almacenamientoQueLanza(): Storage {
  return {
    getItem: () => {
      throw new DOMException("blocked", "SecurityError");
    },
    setItem: () => {
      throw new DOMException("blocked", "SecurityError");
    },
  } as unknown as Storage;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("la preferencia de modo", () => {
  it("sin eleccion guardada abre en oscuro aunque el dispositivo prefiera claro", () => {
    // El modo por defecto es el de la landing, y la landing es oscura.
    expect(DEFAULT_THEME).toBe("dark");
    stubMatchMedia({ [DARK_QUERY]: false });
    expect(resolveTheme(readStoredTheme())).toEqual({ mode: "dark", source: "default" });
  });

  it("con eleccion guardada manda la guardada", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "light");

    expect(resolveTheme(readStoredTheme())).toEqual({
      mode: "light",
      source: "user",
    });
  });

  it("un valor corrupto se trata como ausente y lo dice solo la consola", () => {
    const consola = vi.spyOn(console, "info").mockImplementation(() => undefined);
    window.localStorage.setItem(THEME_STORAGE_KEY, "sepia");

    expect(readStoredTheme()).toBeNull();
    expect(consola).toHaveBeenCalledOnce();
    expect(parseThemeMode("dark")).toBe("dark");
    expect(parseThemeMode(undefined)).toBeNull();
  });

  it("un almacenamiento bloqueado no rompe la lectura ni la escritura", () => {
    vi.spyOn(console, "info").mockImplementation(() => undefined);

    expect(readStoredTheme(almacenamientoQueLanza)).toBeNull();
    expect(storeTheme("dark", almacenamientoQueLanza)).toBe(false);
  });

  it("guardar escribe solo la clave del modo", () => {
    expect(storeTheme("dark")).toBe(true);
    expect(Object.keys(window.localStorage)).toEqual([THEME_STORAGE_KEY]);
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
  });

  it("sin matchMedia resuelve igual: el dispositivo ya no participa", () => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: undefined,
    });

    expect(resolveTheme(null)).toEqual({ mode: "dark", source: "default" });
  });
});

describe("el modo en el documento", () => {
  it("lee lo que dejo el paso de modo antes de pintar", () => {
    document.documentElement.setAttribute("data-theme", "dark");
    document.documentElement.setAttribute("data-theme-source", "user");

    expect(themeFromDocument()).toEqual({ mode: "dark", source: "user" });
  });

  it("si el paso de modo no corrio, resuelve con la misma regla", () => {
    stubMatchMedia({ [DARK_QUERY]: false });

    expect(themeFromDocument()).toEqual({ mode: "dark", source: "default" });
  });

  it("aplica el modo a todo el documento y apaga las transiciones solo durante el cambio", () => {
    const cuadros: FrameRequestCallback[] = [];
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
      cuadros.push(callback);
      return cuadros.length;
    });
    const raiz = document.documentElement;

    applyTheme({ mode: "dark", source: "user" });

    expect(raiz.getAttribute("data-theme")).toBe("dark");
    expect(raiz.getAttribute("data-theme-source")).toBe("user");
    expect(raiz.hasAttribute("data-theme-switching")).toBe(true);

    cuadros.forEach((cuadro) => {
      cuadro(0);
    });
    expect(raiz.hasAttribute("data-theme-switching")).toBe(false);
  });
});
