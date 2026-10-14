import { afterEach, describe, expect, it, vi } from "vitest";

import { recallAll, restoreTurns } from "../../shared/own-text/own-text";
import { callMemory } from "./call-memory";
import type { WireFrame } from "./voice-events";

// Lo que se dice en la llamada se guarda en este navegador para que "Ver mi caso" lo
// devuelva sin tapar (C5, 2026-10-12).

const final = (speaker: "insured" | "agent", text: string): WireFrame => ({
  type: "transcript",
  speaker,
  text,
  final: true,
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("lo que la llamada recuerda de lo que se dijo", () => {
  it("guarda lo que dijo la persona y lo que dijo la agente, cada uno en su lista", () => {
    const recordar = callMemory("una-aseguradora");

    recordar(final("agent", "Hola, ¿en qué te ayudo?"));
    recordar(final("insured", "Soy Natalia Henao"));

    expect(recallAll("una-aseguradora")).toEqual({
      visitor: ["Soy Natalia Henao"],
      agent: ["Hola, ¿en qué te ayudo?"],
    });
  });

  it("un parcial, un cuadro vacio o uno que no es de transcripcion no se guarda", () => {
    const recordar = callMemory("una-aseguradora");

    recordar({ type: "transcript", speaker: "insured", text: "Soy Nata", final: false });
    recordar(final("insured", "   "));
    recordar({ type: "state", value: "live" });
    recordar({ type: "ended", reason: "hangup" });

    expect(recallAll("una-aseguradora")).toEqual({ visitor: [], agent: [] });
  });

  it("los finales seguidos de la persona tambien se guardan como un solo turno, que es como los guarda la base", () => {
    const recordar = callMemory("una-aseguradora");

    recordar(final("insured", "Soy Natalia Henao,"));
    recordar(final("insured", "mi póliza es POL-100042"));

    expect(recallAll("una-aseguradora").visitor).toEqual([
      "Soy Natalia Henao,",
      "mi póliza es POL-100042",
      "Soy Natalia Henao, mi póliza es POL-100042",
    ]);
  });

  it("cuando habla la agente el turno de la persona se cierra: el siguiente empieza de nuevo", () => {
    const recordar = callMemory("una-aseguradora");

    recordar(final("insured", "Hola"));
    recordar(final("agent", "¿En qué te ayudo?"));
    recordar(final("insured", "Quiero reportar"));

    expect(recallAll("una-aseguradora").visitor).toEqual(["Hola", "Quiero reportar"]);
  });

  it("lo guardado destapa el turno que la base guardo con etiquetas", () => {
    const recordar = callMemory("una-aseguradora");
    recordar(final("agent", "Hola, ¿en qué te ayudo?"));
    recordar(final("insured", "Soy Natalia Henao,"));
    recordar(final("insured", "mi póliza es POL-100042"));

    const restaurados = restoreTurns(
      [
        { id: "t1", speaker: "agent", text: "Hola, ¿en qué te ayudo?" },
        { id: "t2", speaker: "visitor", text: "Soy [NOMBRE 1], mi póliza es [PÓLIZA 1]" },
      ],
      recallAll("una-aseguradora"),
    );

    expect(restaurados.get("t2")).toBe("Soy Natalia Henao, mi póliza es POL-100042");
  });

  it("lo que dijo la agente, ya sin tapar en el cable, destapa su turno de la base (2026-10-13)", () => {
    const recordar = callMemory("una-aseguradora");
    recordar(final("agent", "Gracias Natalia, tengo tu placa ABC123."));

    const restaurados = restoreTurns(
      [{ id: "t1", speaker: "agent", text: "Gracias [NOMBRE 1], tengo tu placa [PLACA 1]." }],
      recallAll("una-aseguradora"),
    );

    expect(restaurados.get("t1")).toBe("Gracias Natalia, tengo tu placa ABC123.");
  });

  it("sin almacenamiento la llamada sigue: no se guarda y no falla", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("cuota", "QuotaExceededError");
    });
    const recordar = callMemory("una-aseguradora");

    expect(() => {
      recordar(final("insured", "Soy Natalia"));
    }).not.toThrow();
  });
});
