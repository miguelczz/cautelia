import { describe, expect, it } from "vitest";

import {
  forget,
  isMasked,
  recallAgent,
  recallAll,
  remember,
  rememberAgent,
  restore,
  restoreAll,
  restoreTurns,
} from "./own-text";

describe("el texto propio en su burbuja (fase 0, 2026-10-07)", () => {
  it("pone de vuelta el texto que encaja con la forma del tapado", () => {
    const usados = new Set<number>();

    expect(restore("Soy [NOMBRE 1], placa [PLACA 1]", ["Soy Ana Ruiz, placa ABC123"], usados)).toBe(
      "Soy Ana Ruiz, placa ABC123",
    );
  });

  it("nunca pone un texto que no encaja letra por letra fuera de las etiquetas", () => {
    expect(restore("Soy [NOMBRE 1]", ["Me llamo Ana", "Soy"], new Set())).toBeNull();
    expect(restore("[NOMBRE 1] y [NOMBRE 2]", ["Ana y "], new Set())).toBeNull();
  });

  it("un mensaje sin etiquetas no se toca", () => {
    expect(restore("Ayer en la tarde", ["Ayer en la tarde"], new Set())).toBeNull();
    expect(isMasked("Ayer en la tarde")).toBe(false);
    expect(isMasked("Soy [NOMBRE 1]")).toBe(true);
  });

  it("dos mensajes con la misma forma se reparten del mas nuevo al mas viejo", () => {
    const usados = new Set<number>();
    const propios = ["Soy Ana", "Soy Beto"];

    expect(restore("Soy [NOMBRE 1]", propios, usados)).toBe("Soy Beto");
    expect(restore("Soy [NOMBRE 1]", propios, usados)).toBe("Soy Ana");
    expect(restore("Soy [NOMBRE 1]", propios, usados)).toBeNull();
  });
});

describe("lo guardado en este navegador", () => {
  it("guarda lo escrito y lo respondido por aseguradora, con las claves de siempre", () => {
    remember("una-aseguradora", "Soy Ana");
    rememberAgent("una-aseguradora", "Hola Ana");

    expect(recallAll("una-aseguradora")).toEqual({ visitor: ["Soy Ana"], agent: ["Hola Ana"] });
    expect(recallAll("otra-aseguradora")).toEqual({ visitor: [], agent: [] });
    expect(Object.keys(window.localStorage).sort()).toEqual([
      "cautelia.agent-text.una-aseguradora",
      "cautelia.own-text.una-aseguradora",
    ]);
  });

  it("recuerda solo los 60 mensajes mas recientes", () => {
    for (let i = 0; i < 65; i += 1) {
      rememberAgent("una-aseguradora", `mensaje ${String(i)}`);
    }

    const recordados = recallAgent("una-aseguradora");
    expect(recordados).toHaveLength(60);
    expect(recordados[0]).toBe("mensaje 5");
    expect(recordados.at(-1)).toBe("mensaje 64");
  });

  it("empezar de cero olvida las dos listas", () => {
    remember("una-aseguradora", "Soy Ana");
    rememberAgent("una-aseguradora", "Hola Ana");

    forget("una-aseguradora");

    expect(recallAll("una-aseguradora")).toEqual({ visitor: [], agent: [] });
  });

  it("un valor guardado que no es una lista se ignora", () => {
    window.localStorage.setItem("cautelia.own-text.una-aseguradora", '{"no":"una lista"}');
    window.localStorage.setItem("cautelia.agent-text.una-aseguradora", "no es json");

    expect(recallAll("una-aseguradora")).toEqual({ visitor: [], agent: [] });
  });
});

describe("destapar un caso guardado (2026-10-12)", () => {
  const propios = {
    visitor: ["Hola", "Soy Natalia Henao, mi póliza es POL-100042"],
    agent: ["Gracias Natalia, ya tengo la póliza POL-100042."],
  };

  it("cada turno recupera su texto segun quien lo dijo", () => {
    const restaurados = restoreTurns(
      [
        { id: "t1", speaker: "visitor", text: "Hola" },
        { id: "t2", speaker: "visitor", text: "Soy [NOMBRE 1], mi póliza es [PÓLIZA 1]" },
        { id: "t3", speaker: "agent", text: "Gracias [NOMBRE 1], ya tengo la póliza [PÓLIZA 1]." },
      ],
      propios,
    );

    expect(restaurados.get("t1")).toBeUndefined();
    expect(restaurados.get("t2")).toBe("Soy Natalia Henao, mi póliza es POL-100042");
    expect(restaurados.get("t3")).toBe("Gracias Natalia, ya tengo la póliza POL-100042.");
  });

  it("lo que dijo la agente nunca se busca entre lo que escribio la persona", () => {
    const restaurados = restoreTurns(
      [{ id: "t1", speaker: "agent", text: "Soy [NOMBRE 1], mi póliza es [PÓLIZA 1]" }],
      propios,
    );

    expect(restaurados.size).toBe(0);
  });

  it("un turno de otra voz no se toca aunque encaje", () => {
    const restaurados = restoreTurns(
      [{ id: "t1", speaker: "other", text: "Soy [NOMBRE 1], mi póliza es [PÓLIZA 1]" }],
      propios,
    );

    expect(restaurados.size).toBe(0);
  });

  it("una copia que no encaja no se usa", () => {
    const restaurados = restoreTurns(
      [{ id: "t1", speaker: "visitor", text: "Me llamo [NOMBRE 1]" }],
      propios,
    );

    expect(restaurados.size).toBe(0);
  });

  it("las preguntas tapadas recuperan su copia y las demas quedan como llegaron", () => {
    const preguntas = restoreAll(
      ["¿Cubre el granizo?", "¿Cubre el robo de [PLACA 1]?", "¿Y la grúa de [PLACA 1]?"],
      ["¿Cubre el robo de ABC123?", "¿Y la grúa de ABC123?"],
    );

    expect(preguntas).toEqual([
      "¿Cubre el granizo?",
      "¿Cubre el robo de ABC123?",
      "¿Y la grúa de ABC123?",
    ]);
  });
});
