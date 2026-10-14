import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { installFakeServer } from "../shared/api-client/fake-server";
import { renderRoute } from "./testing";

// Plan de estilos, seccion 4: ninguna pantalla se queda sin algo que diga "esto se esta
// haciendo". Con un servidor que nunca responde, cada pantalla de datos muestra su
// esqueleto, y las que tienen titulo fijo lo conservan.

let quitar: (() => void) | undefined;

afterEach(() => {
  quitar?.();
  quitar = undefined;
});

function sinRespuesta(): void {
  quitar = installFakeServer(() => new Promise<Response>(() => undefined));
}

describe("las pantallas de datos mientras esperan al servidor", () => {
  it.each([
    ["/home", "home"],
    ["/how-it-works", "guide"],
    ["/compare", "compare"],
  ] as const)("%s dibuja el esqueleto %s", async (ruta, familia) => {
    sinRespuesta();
    renderRoute(ruta);

    const carga = await screen.findByTestId("page-skeleton");
    expect(carga.getAttribute("data-skeleton-kind")).toBe(familia);
    expect(carga.getAttribute("aria-busy")).toBe("true");
  });

  it.each([
    ["/telemetry", "telemetry-page"],
    ["/telemetry?view=quality", "metrics-page"],
    ["/metrics", "metrics-page"],
    ["/spend", "telemetry-page"],
  ] as const)(
    "%s conserva su titulo y dibuja el cuerpo del panel como esqueleto",
    async (ruta, pantalla) => {
      sinRespuesta();
      renderRoute(ruta);

      const carga = await screen.findByTestId("page-skeleton");
      expect(carga.getAttribute("data-skeleton-kind")).toBe("panel");
      expect(screen.getByRole("heading", { level: 1 })).toBeDefined();
      expect(screen.getByTestId(pantalla)).toBeDefined();
    },
  );

  it("el marco no espera a nadie: la barra, sus enlaces y el pie estan desde el primer cuadro", async () => {
    sinRespuesta();
    renderRoute("/home");

    expect(await screen.findByTestId("language-selector")).toBeDefined();
    expect(screen.getByTestId("theme-toggle")).toBeDefined();
    expect(screen.getByTestId("site-footer")).toBeDefined();
    expect(screen.getByTestId("surface-nav").querySelectorAll("a").length).toBeGreaterThan(0);
  });
});
