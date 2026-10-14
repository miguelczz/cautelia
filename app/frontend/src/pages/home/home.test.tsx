import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import siteExample from "../../../../contracts/examples/site-directory.json";
import { renderWithProviders } from "../../app/testing";
import {
  installFakeServer,
  jsonResponse,
  networkFailure,
  problemResponse,
} from "../../shared/api-client/fake-server";
import type { SiteDirectory, SurfaceId } from "../../shared/api-client/site";
import type { Locale } from "../../shared/copy/copy-keys";
import { createTranslate } from "../../shared/i18n/translate";
import { HomePage } from "./home-page";

// F2 y BR4.1 a BR4.5, con la configuracion **real** de las tres aseguradoras
// (`app/contracts/examples/site-directory.json`, que regenera
// `mise run contracts:gen`): ninguna fila escrita a mano.

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
  renderWithProviders(<HomePage />, locale);
  await waitFor(() => {
    expect(screen.getByTestId("home").getAttribute("data-home-state")).not.toBe("loading");
  });
  return createTranslate(locale);
}

/** El titulo de la seccion de aseguradoras: hay otro h2, el de la tira de tres pasos. */
function tituloDeAseguradoras(): HTMLElement {
  const titulo = document.getElementById("home-insurers");
  if (titulo === null) {
    throw new Error("missing insurers title");
  }
  return titulo;
}

afterEach(() => {
  quitar?.();
  quitar = undefined;
  vi.restoreAllMocks();
});

describe("el inicio mientras carga", () => {
  it("dibuja el esqueleto del inicio, con las tres filas, ocupado para el lector y sin texto a la vista", () => {
    quitar = installFakeServer(() => new Promise<Response>(() => undefined));
    renderWithProviders(<HomePage />, "es");
    const t = createTranslate("es");

    const carga = screen.getByTestId("page-skeleton");
    expect(carga.getAttribute("data-skeleton-kind")).toBe("home");
    expect(carga.getAttribute("aria-busy")).toBe("true");
    // "Cargando las aseguradoras" lo lee el lector de pantalla; a la vista no hay texto.
    expect(within(carga).getByText(t("home.loading")).className).toContain("sr-only");
    expect(carga.querySelectorAll("[data-testid=insurer-row]")).toHaveLength(0);
    expect(screen.queryByRole("heading")).toBeNull();
  });
});

// Hasta el 2026-09-28 este bloque servia el ejemplo versionado tal cual, porque
// no habia ninguna superficie montada y "sin canales" era la configuracion de hoy.
// U13 monto la primera, asi que ahora el estado se siembra a proposito con
// `conSuperficies([])`: lo que se prueba es la pantalla sin canales, que sigue
// siendo un estado real --el primer arranque de un clon-- y no el que el
// aplicativo tiene ahora.
describe("el inicio sin canales", () => {
  it.each(["es", "en"] as const)(
    "en %s dice una linea honesta y no promete ningun canal",
    async (idioma) => {
      servir(conSuperficies([]));
      const t = await dibujar(idioma);

      expect(screen.getByTestId("home").getAttribute("data-home-state")).toBe("no_channels");
      expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(t("home.title_neutral"));
      expect(screen.getByTestId("home-demo-line").textContent).toBe(t("home.demo_line"));
      expect(screen.getByTestId("home-no-channels").textContent).toBe(t("home.no_channels"));
      expect(tituloDeAseguradoras().textContent).toBe(t("home.insurers.title"));
      expect(screen.queryByText(t("home.title"))).toBeNull();
      // Sin canales no hay botones de canal; quedan el de las polizas de cada fila y el de
      // la guia, que no dependen de ninguna superficie.
      expect(screen.getAllByRole("link").map((enlace) => enlace.getAttribute("href"))).toEqual([
        ...EJEMPLO.tenants.map(
          (aseguradora) => `/policies?tenant=${encodeURIComponent(aseguradora.tenant_id)}`,
        ),
        "/how-it-works",
      ]);
      expect(screen.queryAllByRole("button")).toHaveLength(0);
    },
  );

  it("dibuja una fila por aseguradora con solo lo que su configuracion trae", async () => {
    servir(conSuperficies([]));
    const t = await dibujar("en");

    const filas = screen.getAllByTestId("insurer-row");
    expect(filas).toHaveLength(EJEMPLO.tenants.length);
    // La columna con el numero de la poliza de ejemplo se cambio por un boton a las polizas.
    expect(screen.queryByTestId("sample-policy")).toBeNull();
    EJEMPLO.tenants.forEach((aseguradora, indice) => {
      const fila = filas.at(indice);
      if (fila === undefined) {
        throw new Error("missing row");
      }
      const dentro = within(fila);
      expect(dentro.getByRole("heading", { level: 3 }).textContent).toBe(aseguradora.display_name);
      expect(fila.querySelector("svg")?.getAttribute("data-monogram")).toBe(
        aseguradora.brand?.monogram,
      );
      expect(fila.getAttribute("style")).toContain(aseguradora.brand?.accent ?? "none");
      expect(fila.textContent).not.toContain(aseguradora.example_policy);
      const polizas = dentro.getByRole("link", {
        name: t("home.action.policies_of", { insurer: aseguradora.display_name }),
      });
      expect(polizas.textContent).toBe(t("home.action.policies"));
      expect(polizas.getAttribute("href")).toBe(
        `/policies?tenant=${encodeURIComponent(aseguradora.tenant_id)}`,
      );
    });
  });

  it("escribe el caracter de cada aseguradora por su clave, en el idioma de la pagina", async () => {
    servir(EJEMPLO);
    const t = await dibujar("es");

    expect(screen.getByText(t("insurer.character.conservative"))).toBeDefined();
    expect(screen.getByText(t("insurer.character.flexible"))).toBeDefined();
    expect(screen.getByText(t("insurer.character.agency"))).toBeDefined();
  });

  it("sin marca ni caracter, la fila se dibuja sin monograma y sin esa linea", async () => {
    const [primera] = EJEMPLO.tenants;
    if (primera === undefined) {
      throw new Error("the example has no insurer");
    }
    servir({
      ...EJEMPLO,
      tenants: [
        {
          tenant_id: primera.tenant_id,
          display_name: primera.display_name,
          kind: primera.kind,
          default_language: primera.default_language,
          example_policy: primera.example_policy,
          agent_name: "Catalina",
          character_key: "insurer.character.no_existe",
        },
      ],
    });
    await dibujar("es");

    const fila = screen.getByTestId("insurer-row");
    expect(fila.querySelector("svg")).toBeNull();
    expect(fila.getAttribute("style")).toBeNull();
    expect(within(fila).queryAllByText(/./, { selector: "h3 + p" })).toHaveLength(0);
  });
});

describe("el inicio con canales montados", () => {
  it("con solo el chat: el titulo pide la accion, abrir chat por fila y ninguna llamada", async () => {
    servir(conSuperficies(["chat"]));
    const t = await dibujar("es");

    expect(screen.getByTestId("home").getAttribute("data-home-state")).toBe("with_channels");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(t("home.title"));
    // El titulo de la seccion es la frase que antes repetia la tira de pasos.
    expect(tituloDeAseguradoras().textContent).toBe(t("home.how.report_chat"));
    const [primera] = EJEMPLO.tenants;
    if (primera === undefined) {
      throw new Error("the example has no insurer");
    }
    const abrir = screen.getByRole("link", {
      name: t("home.action.chat_with", { insurer: primera.display_name }),
    });
    expect(abrir.textContent).toBe(t("home.action.chat"));
    expect(abrir.getAttribute("href")).toBe(`/t/${primera.tenant_id}/chat`);
    expect(screen.queryByText(t("home.action.voice"))).toBeNull();
  });

  it("ya no repite lo que el titulo dice: ni tira de pasos, ni primera vez, ni ayuda de la poliza", async () => {
    servir(conSuperficies(["chat", "voice_console", "case_link"]));
    await dibujar("es");

    expect(screen.queryByTestId("home-how")).toBeNull();
    expect(screen.queryByText(/primera vez/)).toBeNull();
    expect(screen.queryByText(/Cuando la agente te pida la póliza/)).toBeNull();
    // Lo que antes era "Que puedes probar", plegable, ya no esta en el inicio.
    expect(screen.queryByText("Qué puede probar")).toBeNull();
  });

  it("con todo montado: las dos acciones por fila, la comparacion y la guia a la derecha", async () => {
    servir(conSuperficies(["chat", "voice_console", "case_link", "comparison"]));
    const t = await dibujar("en");

    expect(tituloDeAseguradoras().textContent).toBe(t("home.how.report_both"));
    expect(screen.getAllByText(t("home.action.voice"))).toHaveLength(EJEMPLO.tenants.length);
    const acciones = within(screen.getByTestId("home-actions")).getAllByRole("link");
    expect(acciones.map((enlace) => enlace.getAttribute("href"))).toEqual([
      "/compare",
      "/how-it-works",
    ]);
    expect(acciones[0]?.textContent).toBe(t("surface.comparison"));
    expect(acciones[1]?.textContent).toBe(t("home.how.title"));
    // Alineados a la derecha, bajo las filas.
    expect(screen.getByTestId("home-actions").className).toContain("justify-end");
  });

  it("con solo la voz, el titulo dice voz y no chat", async () => {
    servir(conSuperficies(["voice_console"]));
    const t = await dibujar("es");

    expect(tituloDeAseguradoras().textContent).toBe(t("home.how.report_voice"));
  });

  it("Llamar lleva solo el acento de la aseguradora y Abrir chat lo lleva de relleno", async () => {
    servir(conSuperficies(["chat", "voice_console"]));
    const t = await dibujar("es");
    const [fila] = screen.getAllByTestId("insurer-row");
    if (fila === undefined) {
      throw new Error("missing row");
    }

    const chat = within(fila).getByRole("link", { name: /Abrir chat con/ });
    const llamar = within(fila).getByRole("link", { name: /Llamar a/ });

    expect(chat.className).toMatch(/(^|\s)bg-tenant(\s|$)/);
    expect(llamar.className).toContain("border-tenant");
    expect(llamar.className).toContain("text-tenant");
    expect(llamar.className).not.toMatch(/(^|\s)bg-tenant(\s|$)/);
    expect(llamar.textContent).toBe(t("home.action.voice"));
  });
});

describe("el inicio cuando el directorio falla", () => {
  it.each(["es", "en"] as const)(
    "en %s muestra el texto del catalogo, reintentar y ninguna fila",
    async (idioma) => {
      vi.spyOn(console, "warn").mockImplementation(() => undefined);
      quitar = installFakeServer(() => problemResponse("internal", 500));
      const t = await dibujar(idioma);

      expect(screen.getByTestId("home").getAttribute("data-home-state")).toBe("error");
      expect(screen.getByTestId("home-error").textContent).toContain(
        t("problem.service_unavailable"),
      );
      expect(screen.getByTestId("home-error").textContent).not.toContain("Technical");
      expect(screen.queryAllByTestId("insurer-row")).toHaveLength(0);
      await waitFor(() => {
        expect(screen.getByTestId("announcer-status").textContent).toBe(
          t("problem.service_unavailable"),
        );
      });
    },
  );

  it("reintentar vuelve a pedir el directorio y dibuja las filas", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    let fallar = true;
    quitar = installFakeServer((ruta) => {
      if (fallar) {
        networkFailure();
      }
      return ruta === "/api/site" ? jsonResponse(EJEMPLO) : jsonResponse({}, 404);
    });
    const t = await dibujar("es");
    expect(screen.getByTestId("home").getAttribute("data-home-state")).toBe("error");

    fallar = false;
    await userEvent.click(screen.getByRole("button", { name: t("action.retry") }));

    expect(await screen.findAllByTestId("insurer-row")).toHaveLength(EJEMPLO.tenants.length);
  });
});

describe("la linea de presentacion", () => {
  it('es solo "Demostración con compañías ficticias." y no hay tira de pasos', async () => {
    servir(conSuperficies(["chat"]));
    const t = await dibujar("es");

    expect(screen.getByTestId("home-demo-line").textContent).toBe(t("home.demo_line"));
    expect(t("home.demo_line")).toBe("Demostración con compañías ficticias.");
    expect(screen.queryByText(/tres pasos/)).toBeNull();
  });
});
