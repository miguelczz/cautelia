import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import siteExample from "../../../contracts/examples/site-directory.json";
import { installFakeServer, jsonResponse, problemResponse } from "../shared/api-client/fake-server";
import { GIVE_UP_AFTER_MS } from "../shared/api-client/readiness";
import type { ReadyOutcome } from "../shared/api-client/site";
import { LOCALE_STORAGE_KEY, SHARED_LOCALE_KEY } from "../shared/i18n/initial-locale";
import { createTranslate } from "../shared/i18n/translate";
import { THEME_STORAGE_KEY } from "../shared/theme/preference";
import { App } from "./App";
import { ReadinessGate } from "./readiness-gate";
import { Providers } from "./testing";

// F1, la espera (functional-spec 2.1) y BR3.5: la aplicacion entera, con el
// servidor falso detras del cliente generado.

let quitar: (() => void) | undefined;

function servidor(listo: () => boolean): void {
  quitar = installFakeServer((ruta) => {
    if (ruta === "/api/health/ready") {
      return listo()
        ? jsonResponse({ status: "ready" })
        : problemResponse("provider_unavailable", 503);
    }
    if (ruta === "/api/site") {
      return jsonResponse(siteExample);
    }
    return problemResponse("not_found", 404);
  });
}

beforeEach(() => {
  vi.spyOn(console, "warn").mockImplementation(() => undefined);
});

afterEach(() => {
  quitar?.();
  quitar = undefined;
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("la puerta de la espera", () => {
  function puerta(check: (signal: AbortSignal) => Promise<ReadyOutcome>) {
    return render(
      <Providers locale="es">
        <ReadinessGate deps={{ check }} />
      </Providers>,
    );
  }

  it("desde el primer cuadro dibuja el marco real con el esqueleto de la pantalla pedida y un hilo", () => {
    vi.useFakeTimers();
    const t = createTranslate("es");
    puerta(() => new Promise<ReadyOutcome>(() => undefined));

    // Sin segundo en blanco: nada espera para dibujarse.
    const esqueleto = screen.getByTestId("page-skeleton");
    expect(esqueleto.getAttribute("aria-busy")).toBe("true");
    expect(esqueleto.getAttribute("data-skeleton-kind")).toBe("home");
    expect(screen.getByTestId("progress-thread")).toBeDefined();
    expect(screen.getByRole("link", { name: t("shell.skip_to_content") })).toBeDefined();
    expect(screen.getByTestId("language-selector")).toBeDefined();
    expect(screen.getByTestId("theme-toggle")).toBeDefined();
    expect(screen.getByTestId("site-footer")).toBeDefined();
    // La barra ya trae sus enlaces: no hay caja de espera en ella (Miguel, 2026-10-11).
    expect(screen.getByRole("link", { name: t("surface.telemetry") })).toBeDefined();
  });

  it("el esqueleto es el de la pantalla que la persona pidio", () => {
    window.history.pushState({}, "", "/how-it-works");
    try {
      puerta(() => new Promise<ReadyOutcome>(() => undefined));
      expect(screen.getByTestId("page-skeleton").getAttribute("data-skeleton-kind")).toBe("guide");
    } finally {
      window.history.pushState({}, "", "/");
    }
  });

  it("dormido sigue mostrando el esqueleto, sin contar que despierta; a los 60 s, no disponible con reintentar", async () => {
    vi.useFakeTimers();
    servidor(() => false);
    const t = createTranslate("es");
    puerta(() => Promise.resolve("not_ready"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    // Ninguna palabra sobre lo que pasa por dentro: ni titulo ni explicacion.
    expect(screen.getByTestId("page-skeleton")).toBeDefined();
    expect(screen.queryByRole("heading")).toBeNull();
    expect(document.body.textContent).not.toMatch(/despiert|waking/i);
    expect(screen.getByTestId("progress-thread")).toBeDefined();
    expect(screen.getByTestId("language-selector")).toBeDefined();
    expect(screen.getByTestId("theme-toggle")).toBeDefined();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(GIVE_UP_AFTER_MS);
    });
    // Esto si es una falla de verdad, y ahi si se dice y se ofrece reintentar.
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      t("status.unavailable.title"),
    );
    expect(screen.getByRole("button", { name: t("action.retry") })).toBeDefined();
    expect(screen.queryByTestId("progress-thread")).toBeNull();
  });

  it("listo dibuja la ruta pedida sin que la persona haga nada", async () => {
    servidor(() => true);
    puerta(() => Promise.resolve("ready"));

    expect(await screen.findAllByTestId("insurer-row")).toHaveLength(siteExample.tenants.length);
  });
});

describe("la aplicacion entera", () => {
  it("con el proceso listo dibuja el inicio, y el navegador guarda solo el modo y el idioma elegidos", async () => {
    servidor(() => true);
    render(<App />);
    const en = createTranslate("en");

    await waitFor(() => {
      expect(screen.getAllByTestId("insurer-row")).toHaveLength(siteExample.tenants.length);
    });
    expect(document.documentElement.lang).toBe("en");

    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    await userEvent.click(screen.getByRole("button", { name: en("shell.theme.light") }));
    await userEvent.click(screen.getByRole("button", { name: "Español" }));

    expect(document.documentElement.lang).toBe("es");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    // BR3.5 y SEC-U6.5: el navegador guarda solo el modo y el idioma (el propio y el
    // que comparte con la landing); nada del directorio ni de ningun dato llega al
    // almacenamiento.
    expect(Object.keys(window.localStorage).sort()).toEqual(
      [THEME_STORAGE_KEY, LOCALE_STORAGE_KEY, SHARED_LOCALE_KEY].sort(),
    );
    expect(window.sessionStorage.length).toBe(0);
  });
});
