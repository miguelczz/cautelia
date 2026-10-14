import { afterEach, describe, expect, it } from "vitest";

import { installFakeServer, jsonResponse, networkFailure, problemResponse } from "./fake-server";
import { checkReady, siteQueryOptions } from "./site";

// La consulta de listo por el cliente generado (BR3.1): 200 es listo; un 503 y
// una falta de respuesta son lo mismo para la espera.

let quitar: (() => void) | undefined;

afterEach(() => {
  quitar?.();
  quitar = undefined;
});

describe("la consulta de listo", () => {
  it("responde listo con un 200", async () => {
    quitar = installFakeServer((ruta) =>
      ruta === "/api/health/ready" ? jsonResponse({ status: "ready" }) : jsonResponse({}, 404),
    );
    expect(await checkReady(new AbortController().signal)).toBe("ready");
  });

  it("responde no listo con el 503 del proceso sin base", async () => {
    quitar = installFakeServer(() => problemResponse("provider_unavailable", 503));
    expect(await checkReady(new AbortController().signal)).toBe("not_ready");
  });

  it("responde no listo si no hay respuesta", async () => {
    quitar = installFakeServer(() => networkFailure());
    expect(await checkReady(new AbortController().signal)).toBe("not_ready");
  });

  it("la consulta del directorio es la del cliente generado", () => {
    expect(siteQueryOptions().queryKey[0]._id).toBe("getSite");
  });
});
