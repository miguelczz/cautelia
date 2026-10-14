import { afterEach, describe, expect, it, vi } from "vitest";

import type { WireCitation } from "../chat/chat-events";
import type { ColumnOutcome, ComparisonColumn } from "./comparison-state";
import {
  clearComparison,
  forgetInFlight,
  inFlight,
  loadComparison,
  saveComparison,
  trackInFlight,
  updateComparison,
  VIGENCIA_MS,
  type SavedComparison,
} from "./comparison-storage";

const CLAVE = "cautelia.comparison.v2";
const IDS = ["a", "b", "c"] as const;

const CITA: WireCitation = {
  clause_id: "PAP-A-4.1",
  clause_version: "2026.1",
  part: "Parte D",
  text: "Texto literal.",
  clause_language: "es",
  amount_deferred: false,
  trace_ref: "t-1",
};

const COLUMNAS: readonly ComparisonColumn[] = [
  {
    tenantId: "a",
    state: "answered",
    answer: { kind: "cited", language: "es", text: "Cubre.", citations: [CITA] },
  },
  { tenantId: "b", state: "answered", answer: { kind: "no_clause", language: "en" } },
  { tenantId: "c", state: "rejected", limit: "rate", copyKey: "chat.limit.rate" },
];

// Leido una sola vez: `consulta()` se llama dos veces en una misma prueba --al guardar y
// al comparar-- y con el reloj leido en cada llamada las dos podian caer en milisegundos
// distintos (fallo en GitHub el 2026-10-13).
const HACE_UN_MINUTO = Date.now() - 60_000;

function consulta(extra: Partial<SavedComparison> = {}): SavedComparison {
  return {
    askedAt: HACE_UN_MINUTO,
    locale: "es",
    question: "¿Cubre el granizo?",
    columns: COLUMNAS,
    ...extra,
  };
}

afterEach(() => {
  forgetInFlight();
  vi.restoreAllMocks();
});

describe("lo guardado de la comparacion", () => {
  it("guarda la pregunta, la hora, el idioma y lo que contesto cada aseguradora", () => {
    const guardada = consulta({ locale: "en" });
    saveComparison(guardada);

    expect(loadComparison(Date.now(), IDS)).toEqual(guardada);
  });

  it("conserva la traduccion de la clausula y de que condicion especial es", () => {
    const traducida: WireCitation = {
      ...CITA,
      clause_language: "en",
      translated_text: "Texto traducido.",
      translated_part: "Parte D — Daños a tu vehículo",
      special_condition_number: 5,
    };
    const guardada = consulta({
      columns: [
        {
          tenantId: "a",
          state: "answered",
          answer: { kind: "cited", language: "es", text: "Cubre.", citations: [traducida] },
        },
        ...COLUMNAS.slice(1),
      ],
    });
    saveComparison(guardada);

    expect(loadComparison(Date.now(), IDS)).toEqual(guardada);
  });

  it("lo opcional de una cita con otra forma no se recuerda", () => {
    const rara = { ...CITA, translated_part: 7, special_condition_number: "5" };
    saveComparison(
      consulta({
        columns: [
          {
            tenantId: "a",
            state: "answered",
            answer: {
              kind: "cited",
              language: "es",
              text: "Cubre.",
              citations: [rara as unknown as WireCitation],
            },
          },
          ...COLUMNAS.slice(1),
        ],
      }),
    );

    expect(loadComparison(Date.now(), IDS)).toEqual(consulta());
  });

  it("devuelve las columnas en el orden que la pagina pide", () => {
    saveComparison(consulta());

    const columnas = loadComparison(Date.now(), ["c", "a", "b"])?.columns;

    expect(columnas?.map((c) => c.tenantId)).toEqual(["c", "a", "b"]);
  });

  it("vence a las 24 horas: un milisegundo antes sirve, a las 24 horas no", () => {
    const askedAt = 1_000_000;
    saveComparison(consulta({ askedAt }));

    expect(loadComparison(askedAt + VIGENCIA_MS - 1, IDS)).not.toBeNull();
    expect(loadComparison(askedAt + VIGENCIA_MS, IDS)).toBeNull();
    // Y lo vencido se borra: no se vuelve a leer.
    expect(window.localStorage.getItem(CLAVE)).toBeNull();
  });

  it("una hora del futuro no se acepta: no podria vencer nunca", () => {
    const ahora = 5_000_000;
    saveComparison(consulta({ askedAt: ahora + 3_600_000 }));

    expect(loadComparison(ahora, IDS)).toBeNull();
  });

  it("lo guardado con el formato viejo (v1) se descarta entero y se borra, sin mostrarse a medias", () => {
    // Antes de que las citas trajeran su rotulo traducido y el numero de la condicion
    // especial (2026-10-12): se veian con rotulos en ingles y "Endosos".
    const viejo = JSON.stringify({
      askedAt: Date.now() - 60_000,
      locale: "es",
      question: "¿Cubre el granizo?",
      columns: [
        {
          tenantId: "a",
          state: "answered",
          answer: { kind: "cited", language: "es", text: "Cubre.", citations: [CITA] },
        },
        { tenantId: "b", state: "answered", answer: { kind: "no_clause", language: "es" } },
        { tenantId: "c", state: "failed" },
      ],
    });
    window.localStorage.setItem("cautelia.comparison.v1", viejo);

    expect(loadComparison(Date.now(), IDS)).toBeNull();
    expect(window.localStorage.getItem("cautelia.comparison.v1")).toBeNull();
  });

  it("guardar con el formato nuevo no deja rastro de la clave vieja", () => {
    window.localStorage.setItem("cautelia.comparison.v1", "{}");
    saveComparison(consulta());

    expect(loadComparison(Date.now(), IDS)).toEqual(consulta());
    expect(Object.keys(window.localStorage)).toEqual([CLAVE]);
  });

  it("clearComparison olvida todo", () => {
    saveComparison(consulta());
    clearComparison();

    expect(loadComparison(Date.now(), IDS)).toBeNull();
    expect(window.localStorage.getItem(CLAVE)).toBeNull();
  });

  it("si las aseguradoras ya no son las mismas, no sirve", () => {
    saveComparison(consulta());

    expect(loadComparison(Date.now(), ["a", "b"])).toBeNull();
    expect(window.localStorage.getItem(CLAVE)).toBeNull();
  });

  it.each([
    ["no es JSON", "{no es json"],
    ["no es un objeto", JSON.stringify([1, 2])],
    ["le falta la pregunta", JSON.stringify({ ...consulta(), question: "  " })],
    ["tiene un idioma desconocido", JSON.stringify({ ...consulta(), locale: "fr" })],
    [
      "una columna tiene un estado desconocido",
      JSON.stringify({ ...consulta(), columns: [{ tenantId: "a", state: "idle" }] }),
    ],
    [
      "una cita no trae su texto",
      JSON.stringify({
        ...consulta(),
        columns: [
          {
            tenantId: "a",
            state: "answered",
            answer: { kind: "cited", language: "es", text: "x", citations: [{ clause_id: "x" }] },
          },
          ...COLUMNAS.slice(1),
        ],
      }),
    ],
    [
      "un limite desconocido",
      JSON.stringify({
        ...consulta(),
        columns: [
          { tenantId: "a", state: "rejected", limit: "inventado", copyKey: "x" },
          ...COLUMNAS.slice(1),
        ],
      }),
    ],
  ])("descarta entero lo guardado que %s", (_motivo, crudo) => {
    window.localStorage.setItem(CLAVE, crudo);

    expect(loadComparison(Date.now(), IDS)).toBeNull();
    expect(window.localStorage.getItem(CLAVE)).toBeNull();
  });

  it("updateComparison cambia las columnas solo si la consulta guardada es la misma", () => {
    saveComparison(consulta({ askedAt: 111 }));

    updateComparison(222, () => [{ tenantId: "a", state: "failed" }]);
    expect(loadComparison(111, IDS)?.columns).toEqual(COLUMNAS);

    updateComparison(111, (columnas) =>
      columnas.map((c) => ({ tenantId: c.tenantId, state: "failed" })),
    );
    expect(loadComparison(111, IDS)?.columns.map((c) => c.state)).toEqual([
      "failed",
      "failed",
      "failed",
    ]);
  });
});

describe("sin almacenamiento", () => {
  it("si leer, escribir o borrar lanza, nada se rompe y no se recuerda nada", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("denegado", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("sin cupo", "QuotaExceededError");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new DOMException("denegado", "SecurityError");
    });

    expect(() => {
      saveComparison(consulta());
    }).not.toThrow();
    expect(() => {
      updateComparison(1, (c) => c);
    }).not.toThrow();
    expect(() => {
      clearComparison();
    }).not.toThrow();
    expect(loadComparison(Date.now(), IDS)).toBeNull();
  });

  it("si ni siquiera existe `localStorage`, tampoco", () => {
    vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
      throw new DOMException("bloqueado", "SecurityError");
    });

    expect(() => {
      saveComparison(consulta());
      clearComparison();
    }).not.toThrow();
    expect(loadComparison(Date.now(), IDS)).toBeNull();
  });
});

describe("lo que sigue en vuelo", () => {
  const CITADA: ColumnOutcome = {
    kind: "answered",
    answer: { kind: "no_clause", language: "es" },
  };

  it("guarda la respuesta en cuanto llega, aunque nadie la este mirando", async () => {
    const askedAt = Date.now();
    saveComparison(
      consulta({
        askedAt,
        columns: IDS.map((tenantId) => ({ tenantId, state: "loading" }) as const),
      }),
    );
    const respuesta = Promise.resolve(CITADA);

    trackInFlight(askedAt, "b", respuesta);
    expect(inFlight(askedAt, "b")).toBe(respuesta);
    await respuesta;
    await Promise.resolve();

    expect(inFlight(askedAt, "b")).toBeUndefined();
    expect(loadComparison(Date.now(), IDS)?.columns.map((c) => c.state)).toEqual([
      "loading",
      "answered",
      "loading",
    ]);
  });

  it("una pregunta fuera de proposito no deja nada que recordar", async () => {
    const askedAt = Date.now();
    saveComparison(consulta({ askedAt }));

    trackInFlight(
      askedAt,
      "a",
      Promise.resolve({ kind: "out_of_scope", copyKey: "comparison.out_of_scope.explanation" }),
    );
    await Promise.resolve();
    await Promise.resolve();

    expect(window.localStorage.getItem(CLAVE)).toBeNull();
  });

  it("una respuesta de una consulta anterior no pisa a la nueva", async () => {
    saveComparison(consulta({ askedAt: 2_000 }));

    trackInFlight(1_000, "a", Promise.resolve({ kind: "failed" }));
    await Promise.resolve();
    await Promise.resolve();

    expect(loadComparison(2_000, IDS)?.columns).toEqual(COLUMNAS);
  });
});
