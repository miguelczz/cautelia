import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import siteExample from "../../../../contracts/examples/site-directory.json";
import { renderRoute, renderWithProviders } from "../../app/testing";
import { toProblemView } from "../../shared/api-client/problems";
import type { Locale } from "../../shared/copy/copy-keys";
import { createTranslate } from "../../shared/i18n/translate";
import { statusKindForCaseProblem } from "./case-link-status";
import { StatusPage } from "./status-page";
import { parseRoutedStatusKind, STATUS_PAGE_KINDS, statusCopy } from "./status-kinds";

// BR5.5 a BR5.7 y NFR20.1: las seis paginas, con una plantilla, en los dos
// idiomas, sin detalles tecnicos ni nombres de aseguradoras.

const IDIOMAS: readonly Locale[] = ["es", "en"];
const COMBINACIONES = STATUS_PAGE_KINDS.flatMap((tipo) =>
  IDIOMAS.map((idioma) => [tipo, idioma] as const),
);

afterEach(() => {
  vi.restoreAllMocks();
});

describe("las seis paginas de estado", () => {
  it.each(COMBINACIONES)(
    "%s en %s: titulo y explicacion del catalogo, y el foco en el titulo",
    (tipo, idioma) => {
      const t = createTranslate(idioma);
      const copia = statusCopy(tipo);
      renderWithProviders(<StatusPage kind={tipo} />, idioma);

      const titulo = screen.getByRole("heading", { level: 1 });
      expect(titulo.textContent).toBe(copia.title(t));
      expect(document.activeElement).toBe(titulo);
      const pagina = screen.getByTestId("status-page");
      expect(pagina.textContent).toContain(copia.body(t));
      for (const aseguradora of siteExample.tenants) {
        expect(pagina.textContent).not.toContain(aseguradora.display_name);
      }
      expect(pagina.textContent).not.toMatch(/\b(trace|code|500|503|404)\b/i);
    },
  );

  it("los dos idiomas dicen cosas distintas en cada pagina", () => {
    for (const tipo of STATUS_PAGE_KINDS) {
      expect(statusCopy(tipo).title(createTranslate("es"))).not.toBe(
        statusCopy(tipo).title(createTranslate("en")),
      );
    }
  });

  it("despertando ya no es una pagina de estado: el proceso que despierta se ve como esqueleto", () => {
    expect(STATUS_PAGE_KINDS).not.toContain("waking");
    expect(parseRoutedStatusKind("waking")).toBeNull();
  });

  it("no disponible ofrece reintentar y solo los enlaces configurados", async () => {
    const reintentar = vi.fn();
    const t = createTranslate("en");
    const { unmount } = renderWithProviders(
      <StatusPage
        kind="unavailable"
        onRetry={reintentar}
        links={{ video_url: "https://example.org/v" }}
      />,
      "en",
    );

    await userEvent.click(screen.getByRole("button", { name: t("action.retry") }));
    expect(reintentar).toHaveBeenCalledOnce();
    expect(screen.getAllByRole("link").map((enlace) => enlace.textContent)).toEqual([
      t("site.link.video"),
    ]);
    unmount();

    renderWithProviders(<StatusPage kind="unavailable" onRetry={reintentar} links={{}} />, "en");
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("enlace vencido vuelve a la conversacion; los datos reiniciados empiezan de nuevo", async () => {
    const volver = vi.fn();
    const t = createTranslate("es");
    const { unmount } = renderWithProviders(
      <StatusPage kind="link_expired" onBack={volver} />,
      "es",
    );
    await userEvent.click(screen.getByRole("button", { name: t("action.back_to_conversation") }));
    expect(volver).toHaveBeenCalledOnce();
    unmount();

    renderWithProviders(<StatusPage kind="data_reset" />, "es");
    expect(screen.getByRole("link", { name: t("action.start_over") }).getAttribute("href")).toBe(
      "/home",
    );
  });
});

describe("una ruta de caso que no sirve (F6, SEC-U6.6)", () => {
  it("un enlace manipulado y un caso que no existe muestran exactamente la misma pagina", () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const problema = (code: string) => ({ title: "x", status: 404, trace_id: "t", code });
    const manipulado = statusKindForCaseProblem(toProblemView(problema("link_invalid")));
    const inexistente = statusKindForCaseProblem(toProblemView(problema("not_found")));

    expect(manipulado).toBe("link_invalid");
    expect(inexistente).toBe(manipulado);

    const primera = renderWithProviders(<StatusPage kind={manipulado} />, "es");
    const textoManipulado = screen.getByTestId("status-page").textContent;
    primera.unmount();
    renderWithProviders(<StatusPage kind={inexistente} />, "es");
    expect(screen.getByTestId("status-page").textContent).toBe(textoManipulado);
  });

  it("cualquier otro error de la ruta de caso es servicio no disponible", () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    expect(statusKindForCaseProblem(toProblemView(new TypeError("Failed to fetch")))).toBe(
      "service_unavailable",
    );
  });
});

describe("las rutas de estado", () => {
  it("solo se llega por direccion a los cinco tipos navegables", () => {
    expect(parseRoutedStatusKind("link_invalid")).toBe("link_invalid");
    expect(parseRoutedStatusKind("unavailable")).toBeNull();
    expect(parseRoutedStatusKind("cualquier_cosa")).toBeNull();
  });

  it("una direccion de estado dibuja su pagina, y una desconocida es no encontrada", async () => {
    const t = createTranslate("es");
    renderRoute("/status/link_expired", "es");
    expect((await screen.findByRole("heading", { level: 1 })).textContent).toBe(
      t("status.link_expired.title"),
    );
  });

  it("despertando por direccion es no encontrada", async () => {
    const t = createTranslate("en");
    renderRoute("/status/waking", "en");
    expect((await screen.findByRole("heading", { level: 1 })).textContent).toBe(
      t("status.not_found.title"),
    );
  });

  it("cualquier otra ruta es no encontrada, con el enlace al inicio", async () => {
    const t = createTranslate("es");
    renderRoute("/esta/ruta/no/existe", "es");
    expect((await screen.findByRole("heading", { level: 1 })).textContent).toBe(
      t("status.not_found.title"),
    );
    expect(screen.getByRole("link", { name: t("action.go_home") }).getAttribute("href")).toBe(
      "/home",
    );
  });

  it("volver y reintentar llevan al inicio si se llego directo", async () => {
    const t = createTranslate("es");
    const { router } = renderRoute("/status/service_unavailable", "es");

    await userEvent.click(await screen.findByRole("button", { name: t("action.retry") }));

    expect(router.state.location.pathname).toBe("/home");
  });
});
