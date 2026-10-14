import { describe, expect, it } from "vitest";

import { createMemoryHistory } from "@tanstack/react-router";

import { VISITABLE_ROUTES } from "../../e2e/visitable-routes";
import { createAppRouter } from "./router";

// BR7.1: toda ruta del enrutador esta en el registro del arnes. `mise run a11y`
// corre esta prueba **antes** del arnes, y la falla nombra la ruta que falta.

/** Las rutas que el enrutador resuelve, tal como las construye la aplicacion. */
function rutasDelEnrutador(): string[] {
  const enrutador = createAppRouter(createMemoryHistory());
  return Object.keys(enrutador.routesByPath).sort();
}

describe("el registro de pantallas visitables", () => {
  it("cubre cada ruta del enrutador", () => {
    const registradas = new Set(VISITABLE_ROUTES.map((pantalla) => pantalla.route));
    const faltan = rutasDelEnrutador().filter((ruta) => !registradas.has(ruta));

    expect(
      faltan,
      `rutas del enrutador sin registrar en e2e/visitable-routes.ts: ${faltan.join(", ")}`,
    ).toEqual([]);
    // La lista del enrutador no esta vacia: si lo estuviera, lo de arriba no
    // probaria nada.
    expect(rutasDelEnrutador()).toEqual([
      "/",
      "/c",
      "/c/$tenantId/$caseId",
      "/cases",
      "/cases/$tenantId/$caseId",
      "/compare",
      "/home",
      "/how-it-works",
      "/metrics",
      "/policies",
      "/spend",
      "/status/$kind",
      "/t/$tenantId/call",
      "/t/$tenantId/chat",
      "/t/$tenantId/inbox",
      "/t/$tenantId/inbox/$caseId",
      "/t/$tenantId/trace/$traceId",
      "/telemetry",
    ]);
  });

  it("no registra rutas que el enrutador no tiene", () => {
    const delEnrutador = new Set(rutasDelEnrutador());
    const sobran = VISITABLE_ROUTES.filter(
      (pantalla) => !pantalla.route.startsWith("(") && !delEnrutador.has(pantalla.route),
    );
    expect(sobran).toEqual([]);
  });

  it("cada pantalla tiene un identificador unico y una direccion concreta", () => {
    const ids = VISITABLE_ROUTES.map((pantalla) => pantalla.routeId);
    expect(new Set(ids).size).toBe(ids.length);
    for (const pantalla of VISITABLE_ROUTES) {
      expect(pantalla.path).not.toContain("$");
    }
  });
});
