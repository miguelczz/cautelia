// Solo para pruebas: un servidor falso detras del cliente generado.
//
// Las pruebas de componentes hablan con el servidor **por el mismo camino** que la
// aplicacion --el cliente generado, con su manejo de errores--, y lo unico falso
// es la respuesta. Vive en `api-client/` porque es el unico modulo al que la
// regla de fronteras le deja tocar el cliente generado (BR3.1). Ninguna pantalla
// lo importa, asi que no llega al paquete que se sirve.

import type { Problem } from "../api";
import { client } from "../api/client.gen";

/** Una respuesta del servidor falso para una peticion. */
export type FakeHandler = (path: string, request: Request) => Response | Promise<Response>;

/**
 * El origen del servidor falso. Hace falta uno absoluto: fuera del navegador, una
 * peticion con ruta relativa no se puede construir.
 */
export const FAKE_ORIGIN = "http://untangle.test";

/** Instala el servidor falso; devuelve como quitarlo. */
export function installFakeServer(handler: FakeHandler): () => void {
  client.setConfig({
    baseUrl: FAKE_ORIGIN,
    fetch: async (input: RequestInfo | URL) => {
      const peticion = input instanceof Request ? input : new Request(input);
      return handler(new URL(peticion.url).pathname, peticion);
    },
  });
  // Al quitarlo, no queda red: una llamada sin servidor falso falla como una red
  // caida, que es lo que veria la pagina sin servidor.
  return () => {
    client.setConfig({
      baseUrl: "",
      fetch: () => Promise.reject(new TypeError("no fake server is installed")),
    });
  };
}

/** Una respuesta JSON. */
export function jsonResponse(body: unknown, status = 200, headers: HeadersInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...Object.fromEntries(new Headers(headers)) },
  });
}

/** Un error con la forma de C-01, con titulo y detalle que **no** deben verse. */
export function problemResponse(
  code: string,
  status: number,
  extra: Partial<Problem> = {},
): Response {
  return new Response(
    JSON.stringify({
      type: "about:blank",
      title: "Technical title that must never be shown",
      status,
      detail: "Technical detail that must never be shown",
      trace_id: "0123456789abcdef0123456789abcdef",
      code,
      ...extra,
    }),
    { status, headers: { "content-type": "application/problem+json" } },
  );
}

/** Una falla de red: `fetch` rechaza sin respuesta. */
export function networkFailure(): never {
  throw new TypeError("Failed to fetch");
}
