import { describe, expect, it } from "vitest";

import { VISITABLE_ROUTES } from "../../e2e/visitable-routes";
import { frameModeForKind, skeletonKindForPath } from "./skeleton-kinds";

// La espera se dibuja antes del enrutador y solo sabe la direccion: de ella sale el
// esqueleto de la pantalla que la persona pidio (plan de estilos, seccion 4).
//
// `una-aseguradora` y no un identificador real: el chequeo de identificadores de
// aseguradora escritos a mano (BR4.2) cuenta tambien las pruebas, y aqui el nombre
// no importa, solo la forma de la direccion.

describe("que esqueleto le toca a cada direccion", () => {
  it.each([
    ["/", "home"],
    ["/home", "home"],
    ["/home?x=1", "home"],
    ["/how-it-works", "guide"],
    ["/policies", "policies"],
    ["/policies?tenant=una-aseguradora", "policies"],
    ["/metrics", "panel"],
    ["/spend", "panel"],
    ["/telemetry", "panel"],
    ["/telemetry?view=quality", "panel"],
    ["/cases", "cases"],
    ["/cases?tenant=una-aseguradora", "cases"],
    ["/cases/una-aseguradora/caso-1", "case"],
    ["/compare", "compare"],
    ["/t/una-aseguradora/chat", "chat"],
    ["/t/una-aseguradora/call", "call"],
    ["/t/una-aseguradora/inbox", "inbox"],
    ["/t/una-aseguradora/inbox?state=derived", "inbox"],
    ["/t/una-aseguradora/inbox/case-1", "case"],
    ["/c", "case"],
    ["/c/una-aseguradora/case-1", "case"],
    ["/t/una-aseguradora/trace/abc", "generic"],
    ["/status/link_expired", "generic"],
    ["/no/existe", "generic"],
  ] as const)("%s es %s", (ruta, esperado) => {
    expect(skeletonKindForPath(ruta)).toBe(esperado);
  });

  it("toda pantalla visitable con forma propia tiene un esqueleto propio, no el generico", () => {
    // Las que sí son genericas por diseno: paginas cortas de estado y la traza.
    const GENERICAS = new Set([
      "/status/$kind",
      "/t/$tenantId/trace/$traceId",
      "(not-found)",
      "(readiness)",
    ]);
    const sinEsqueletoPropio = VISITABLE_ROUTES.filter(
      (pantalla) =>
        !GENERICAS.has(pantalla.route) &&
        pantalla.route !== "/" &&
        skeletonKindForPath(pantalla.path) === "generic",
    ).map((pantalla) => pantalla.routeId);

    expect(
      sinEsqueletoPropio,
      `pantallas sin esqueleto propio en app/skeleton-kinds.ts: ${sinEsqueletoPropio.join(", ")}`,
    ).toEqual([]);
  });
});

describe("como se asienta el marco para cada familia", () => {
  it("el chat llena la vista; el inicio, la guia y las polizas caben en una sola; el resto fluye", () => {
    expect(frameModeForKind("chat")).toEqual({ fill: true, onePage: false });
    expect(frameModeForKind("home")).toEqual({ fill: false, onePage: true });
    expect(frameModeForKind("guide")).toEqual({ fill: false, onePage: true });
    expect(frameModeForKind("policies")).toEqual({ fill: false, onePage: true });
    for (const otra of ["panel", "cases", "compare", "call", "inbox", "case", "generic"] as const) {
      expect(frameModeForKind(otra)).toEqual({ fill: false, onePage: false });
    }
  });
});
