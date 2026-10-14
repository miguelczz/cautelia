import { afterEach, describe, expect, it, vi } from "vitest";

import { onConnectivityLost } from "./connectivity";
import { installFakeServer, jsonResponse, networkFailure, problemResponse } from "./fake-server";
import { createQueryClient } from "./query-client";
import { siteQueryOptions } from "./site";

// BR3.5 y la maquina 2.1: la cache vive solo en memoria, y una red caida (no un
// error del servidor) avisa a la espera.

let quitar: (() => void) | undefined;

afterEach(() => {
  quitar?.();
  quitar = undefined;
  vi.restoreAllMocks();
});

describe("la cache de datos", () => {
  it("una red caida avisa que se perdio la conexion", async () => {
    quitar = installFakeServer(() => networkFailure());
    const aviso = vi.fn();
    const baja = onConnectivityLost(aviso);

    await createQueryClient()
      .query(siteQueryOptions())
      .catch(() => undefined);

    expect(aviso).toHaveBeenCalledOnce();
    baja();
  });

  it("un error del servidor no es una perdida de conexion", async () => {
    quitar = installFakeServer(() => problemResponse("internal", 500));
    const aviso = vi.fn();
    const baja = onConnectivityLost(aviso);

    await createQueryClient()
      .query(siteQueryOptions())
      .catch(() => undefined);

    expect(aviso).not.toHaveBeenCalled();
    baja();
  });

  it("los datos quedan solo en memoria: nada se escribe en el almacenamiento", async () => {
    quitar = installFakeServer(() => jsonResponse({ tenants: [], surfaces: [], links: {} }));
    const cache = createQueryClient();

    await cache.query(siteQueryOptions());

    expect(cache.getQueryData(siteQueryOptions().queryKey)).toEqual({
      tenants: [],
      surfaces: [],
      links: {},
    });
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });
});
