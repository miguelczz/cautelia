import { afterEach, describe, expect, it, vi } from "vitest";

import { clearDraft, recallDraft, saveDraft } from "./draft";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("el borrador del cuadro de escribir", () => {
  it("vuelve tal como quedo, con sus saltos de linea", () => {
    saveDraft("una-aseguradora", "Primera línea\nsegunda línea");

    expect(recallDraft("una-aseguradora")).toBe("Primera línea\nsegunda línea");
  });

  it("es de cada aseguradora: el de una no aparece en la otra", () => {
    saveDraft("una-aseguradora", "para la primera");
    saveDraft("otra-aseguradora", "para la segunda");

    expect(recallDraft("una-aseguradora")).toBe("para la primera");
    expect(recallDraft("otra-aseguradora")).toBe("para la segunda");
  });

  it("sin nada guardado devuelve vacio", () => {
    expect(recallDraft("una-aseguradora")).toBe("");
  });

  it("borrarlo no toca el de la otra aseguradora", () => {
    saveDraft("una-aseguradora", "uno");
    saveDraft("otra-aseguradora", "dos");

    clearDraft("una-aseguradora");

    expect(recallDraft("una-aseguradora")).toBe("");
    expect(recallDraft("otra-aseguradora")).toBe("dos");
  });

  it("un cuadro vacio no deja ni la clave en el navegador", () => {
    saveDraft("una-aseguradora", "algo");
    saveDraft("una-aseguradora", "");

    expect(window.localStorage.length).toBe(0);
  });

  it("un valor ilegible se lee como vacio y no rompe", () => {
    window.localStorage.setItem("cautelia.chat-drafts", "esto no es json");
    expect(recallDraft("una-aseguradora")).toBe("");

    window.localStorage.setItem("cautelia.chat-drafts", '["una", "lista"]');
    expect(recallDraft("una-aseguradora")).toBe("");

    // Y escribir encima de un valor ilegible lo arregla en vez de propagarlo.
    saveDraft("una-aseguradora", "nuevo");
    expect(recallDraft("una-aseguradora")).toBe("nuevo");
  });

  it("sin almacenamiento nada falla: no recuerda y listo", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("sin almacenamiento");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("sin almacenamiento");
    });

    expect(() => {
      saveDraft("una-aseguradora", "algo");
      clearDraft("una-aseguradora");
    }).not.toThrow();
    expect(recallDraft("una-aseguradora")).toBe("");
  });
});
