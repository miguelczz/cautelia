import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import siteExample from "../../../../contracts/examples/site-directory.json";
import { renderRoute, renderWithProviders } from "../../app/testing";
import {
  installFakeServer,
  jsonResponse,
  networkFailure,
  problemResponse,
} from "../../shared/api-client/fake-server";
import type { SiteDirectory, SurfaceId } from "../../shared/api-client/site";
import type { Locale } from "../../shared/copy/copy-keys";
import { createTranslate } from "../../shared/i18n/translate";
import { GuidePage } from "./guide-page";

// La guia "Como funciona" (plan-estilos-2026-10.md, seccion 9): cada paso solo si
// lo construido lo permite, y las aseguradoras salen del directorio, con la
// configuracion real de las tres.

const EJEMPLO = siteExample as SiteDirectory;

let quitar: (() => void) | undefined;

function servir(directorio: SiteDirectory): void {
  quitar = installFakeServer((ruta) =>
    ruta === "/api/site" ? jsonResponse(directorio) : jsonResponse({}, 404),
  );
}

function conSuperficies(superficies: SurfaceId[]): SiteDirectory {
  return { ...EJEMPLO, surfaces: superficies };
}

async function dibujar(locale: Locale = "es") {
  renderWithProviders(<GuidePage />, locale);
  await waitFor(() => {
    expect(screen.getByTestId("guide").getAttribute("data-guide-state")).not.toBe("loading");
  });
  return createTranslate(locale);
}

afterEach(() => {
  quitar?.();
  quitar = undefined;
  vi.restoreAllMocks();
});

describe("la guia con todo montado", () => {
  it.each(["es", "en"] as const)(
    "en %s cuenta los cuatro pasos en orden, numerados",
    async (idioma) => {
      servir(conSuperficies(["chat", "voice_console", "case_link"]));
      const t = await dibujar(idioma);

      expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(t("guide.title"));
      const pasos = within(screen.getByTestId("guide-steps")).getAllByRole("listitem");
      expect(
        pasos.map((paso) => within(paso).getByRole("heading", { level: 3 }).textContent),
      ).toEqual([
        t("guide.steps.choose.title"),
        t("guide.steps.report.title"),
        t("guide.steps.link.title"),
        t("guide.steps.decide.title"),
      ]);
      // El paso de contar lo que paso dice los dos canales y que hacer con la poliza.
      expect(pasos[1]?.textContent).toContain(t("guide.steps.report.both"));
      expect(pasos[1]?.textContent).toContain(t("guide.steps.report.policy"));
    },
  );

  it("empieza diciendo que es Cautelia, que no hace la agente y que todo es de ejemplo", async () => {
    servir(conSuperficies(["chat"]));
    const t = await dibujar("es");

    expect(screen.getByTestId("guide-about").textContent).toBe(t("guide.about.what"));
    expect(screen.getByText(t("guide.about.limit"))).toBeDefined();
    expect(screen.getByText(t("guide.about.sample"))).toBeDefined();
  });

  it("lista que mas se puede probar, con enlace a lo que tiene pagina propia, y cada aseguradora con su agente", async () => {
    servir(conSuperficies(["chat", "voice_console", "case_link", "comparison", "metrics_panel"]));
    const t = await dibujar("es");

    const pruebas = within(screen.getByTestId("guide-try")).getAllByRole("listitem");
    expect(pruebas.map((li) => li.textContent)).toEqual([
      t("guide.try.ask_coverage"),
      t("guide.try.interrupt"),
      t("guide.try.compare"),
      t("guide.try.cases"),
      t("guide.try.telemetry"),
    ]);
    expect(pruebas.map((li) => li.querySelector("a")?.getAttribute("href") ?? null)).toEqual([
      null,
      null,
      "/compare",
      "/cases",
      "/telemetry",
    ]);

    const filas = screen.getAllByTestId("guide-insurer");
    expect(filas).toHaveLength(EJEMPLO.tenants.length);
    expect(filas.map((fila) => within(fila).getByRole("heading").textContent)).toEqual(
      EJEMPLO.tenants.map((aseguradora) => aseguradora.display_name),
    );
    // Cada aseguradora tiene su agente (Miguel, 2026-10-11) y la fila la nombra.
    const textos = filas.map((fila) => fila.textContent);
    for (const aseguradora of EJEMPLO.tenants) {
      const frase = t("guide.differences.agent", { agent: aseguradora.agent_name });
      expect(textos.filter((texto) => texto.includes(frase))).toHaveLength(1);
    }
    expect(new Set(EJEMPLO.tenants.map((aseguradora) => aseguradora.agent_name)).size).toBe(
      EJEMPLO.tenants.length,
    );
    // Y el boton para empezar vuelve al inicio.
    expect(screen.getByRole("link", { name: t("guide.start") }).getAttribute("href")).toBe("/home");
  });

  it("dice lo que de verdad cambia entre las aseguradoras: que pasa con el reporte", async () => {
    servir(conSuperficies(["chat"]));
    const t = await dibujar("es");

    const caracteres = [
      t("insurer.character.agency"),
      t("insurer.character.conservative"),
      t("insurer.character.flexible"),
    ];
    const diferencias = screen.getByTestId("guide-differences").textContent;
    for (const caracter of caracteres) {
      expect(diferencias).toContain(caracter);
    }
    // No dice en que idioma "empieza": eso solo era cierto para una llamada sin idioma
    // elegido, y la pantalla lo afirmaba para todo (auditoria del 2026-10-10).
    expect(diferencias).not.toMatch(/Empieza en/);
    expect(t("insurer.character.agency")).toContain("aseguradora que emitió la póliza");
    expect(t("insurer.character.conservative")).toContain("un ajustador revisa todos los casos");
    expect(t("insurer.character.flexible")).toContain("cierra por su cuenta");
  });
});

describe("la guia solo cuenta lo construido (BR4.1)", () => {
  it("con solo el chat: sin el paso del enlace, sin llamada en lo que se puede probar", async () => {
    servir(conSuperficies(["chat"]));
    const t = await dibujar("es");

    const pasos = within(screen.getByTestId("guide-steps")).getAllByRole("listitem");
    expect(pasos).toHaveLength(2);
    expect(pasos[1]?.textContent).toContain(t("guide.steps.report.chat"));
    expect(screen.queryByText(t("guide.steps.link.title"))).toBeNull();
    expect(
      within(screen.getByTestId("guide-try"))
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual([t("guide.try.ask_coverage"), t("guide.try.cases")]);
  });

  it("sin canales: solo elegir aseguradora, y de lo demas solo los casos de ejemplo", async () => {
    servir(conSuperficies([]));
    const t = await dibujar("en");

    expect(within(screen.getByTestId("guide-steps")).getAllByRole("listitem")).toHaveLength(1);
    expect(
      within(screen.getByTestId("guide-try"))
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual([t("guide.try.cases")]);
  });
});

describe("la guia mientras carga o cuando falla", () => {
  it("mientras carga dibuja el esqueleto de la guia, ocupado para el lector", () => {
    quitar = installFakeServer(() => new Promise<Response>(() => undefined));
    renderWithProviders(<GuidePage />, "es");
    const t = createTranslate("es");

    const carga = screen.getByTestId("page-skeleton");
    expect(carga.getAttribute("data-skeleton-kind")).toBe("guide");
    expect(carga.getAttribute("aria-busy")).toBe("true");
    expect(within(carga).getByText(t("shell.loading")).className).toContain("sr-only");
  });

  it("si el directorio falla, dice el problema y deja reintentar", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    let fallar = true;
    quitar = installFakeServer(() => {
      if (fallar) {
        networkFailure();
      }
      return jsonResponse(conSuperficies(["chat"]));
    });
    const t = await dibujar("es");
    expect(screen.getByTestId("guide").getAttribute("data-guide-state")).toBe("error");

    fallar = false;
    await userEvent.click(screen.getByRole("button", { name: t("action.retry") }));

    expect(await screen.findByTestId("guide-steps")).toBeDefined();
  });

  it("un error del servidor se dice con el texto del catalogo", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    quitar = installFakeServer(() => problemResponse("internal", 500));
    const t = await dibujar("en");

    expect(screen.getByTestId("guide").textContent).toContain(t("problem.service_unavailable"));
  });
});

describe("la ruta de la guia", () => {
  it("se llega por /how-it-works y cabe en una sola pantalla en un computador", async () => {
    servir(conSuperficies(["chat"]));
    const { router } = renderRoute("/how-it-works");

    await screen.findByTestId("guide-steps");
    expect(router.state.location.pathname).toBe("/how-it-works");
    expect(router.state.matches.some((c) => c.staticData.onePage === true)).toBe(true);
  });
});
