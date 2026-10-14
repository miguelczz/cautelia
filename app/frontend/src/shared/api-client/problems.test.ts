import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProblemCode } from "../api";
import { createTranslate } from "../i18n/translate";
import { isConnectivityFailure, problemMessage, toProblemView } from "./problems";

// REL-U6.1, BR3.2 a BR3.4: todo codigo de C-01, mas uno desconocido, una red
// caida y un cuerpo ilegible, termina en un texto del catalogo con su accion;
// nunca en el titulo ni el detalle tecnicos.

const CODIGOS: readonly ProblemCode[] = [
  "validation_failed",
  "not_found",
  "forbidden_origin",
  "link_invalid",
  "conflict_idempotency",
  "rate_limited_session",
  "rate_limited_daily",
  "rate_limited_site",
  "budget_exhausted",
  "provider_timeout",
  "provider_unavailable",
  "unverifiable",
  "internal",
];

const TITULO = "Technical title that must never be shown";
const DETALLE = "Technical detail that must never be shown";

function problema(code: string, extra: Record<string, unknown> = {}) {
  return { title: TITULO, detail: DETALLE, status: 400, trace_id: "trace-123", code, ...extra };
}

const es = createTranslate("es");
const en = createTranslate("en");
// Al usarse y no al cargar el archivo: las frases llegan en `beforeAll` (2026-10-09).
const NO_DISPONIBLE = {
  get es() {
    return es("problem.service_unavailable");
  },
  get en() {
    return en("problem.service_unavailable");
  },
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("la tabla unica de errores", () => {
  it.each(CODIGOS)("el codigo %s se dice con texto del catalogo en los dos idiomas", (codigo) => {
    const consola = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const vista = toProblemView(problema(codigo));

    expect(vista.code).toBe(codigo);
    for (const t of [es, en]) {
      const texto = vista.message(t);
      expect(texto.length).toBeGreaterThan(0);
      expect(texto).not.toContain(TITULO);
      expect(texto).not.toContain(DETALLE);
      expect(texto).not.toContain(codigo);
    }
    // El detalle tecnico va a la consola, con la traza, para quien depura.
    expect(JSON.stringify(consola.mock.calls)).toContain("trace-123");
    expect(JSON.stringify(consola.mock.calls)).toContain(DETALLE);
  });

  it("los limites de uso reutilizan las frases de U5", () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    expect(toProblemView(problema("budget_exhausted")).message(es)).toBe(
      es("spend.quota.budget_exhausted"),
    );
  });

  it("un codigo que esta version no conoce cae en la rama por defecto y se registra", () => {
    const consola = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const vista = toProblemView(problema("teapot_overflow"));

    expect(vista.code).toBe("unknown");
    expect(vista.message(es)).toBe(NO_DISPONIBLE.es);
    expect(JSON.stringify(consola.mock.calls)).toContain("teapot_overflow");
    expect(problemMessage("teapot_overflow")(en)).toBe(NO_DISPONIBLE.en);
  });

  it.each([
    ["una red caida", new TypeError("Failed to fetch")],
    ["un cuerpo HTML en lugar de JSON", "<!doctype html><title>Bad gateway</title>"],
    ["un cuerpo vacio", {}],
    ["un tiempo agotado", new DOMException("timed out", "TimeoutError")],
  ])("%s es servicio no disponible con codigo unknown", (_, error) => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const vista = toProblemView(error);

    expect(vista.code).toBe("unknown");
    expect(vista.message(en)).toBe(NO_DISPONIBLE.en);
  });

  it("conserva cuando reintentar si el servidor lo dijo", () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    expect(toProblemView(problema("rate_limited_daily", { retry_after_s: 30 })).retryAfterS).toBe(
      30,
    );
    expect(toProblemView(problema("rate_limited_daily")).retryAfterS).toBeUndefined();
  });
});

describe("la perdida de conexion", () => {
  it("es una red caida o una espera agotada, no una respuesta del servidor", () => {
    expect(isConnectivityFailure(new TypeError("Failed to fetch"))).toBe(true);
    expect(isConnectivityFailure(new DOMException("x", "AbortError"))).toBe(true);
    expect(isConnectivityFailure(new DOMException("x", "TimeoutError"))).toBe(true);
    expect(isConnectivityFailure(new DOMException("x", "SyntaxError"))).toBe(false);
    expect(isConnectivityFailure(problema("internal"))).toBe(false);
  });
});
