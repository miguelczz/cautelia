import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import siteExample from "../../../contracts/examples/site-directory.json";
import { installFakeServer, jsonResponse } from "../shared/api-client/fake-server";
import chatSource from "../pages/chat/chat-page.tsx?raw";
import voiceSource from "../pages/voice/voice-page.tsx?raw";
import { renderRoute } from "./testing";

// La conversacion y la llamada se pintan con el acento de la aseguradora en la que esta
// la persona, no con el cobre de Cautelia (decision de Miguel, 2026-10-07): asi se ve de
// un vistazo con cual esta hablando. La barra y el pie, que son del aplicativo, no
// cambian.

// Las pantallas de verdad abren flujos y conexiones que no son lo que se mide aqui: se
// sustituyen por una sonda, y lo que importa es en que ambito de acento quedan.
vi.mock("../pages/chat/chat-page", () => ({
  ChatPage: () => <p data-testid="sonda-chat">chat</p>,
}));
vi.mock("../pages/voice/voice-page", () => ({
  VoicePage: () => <p data-testid="sonda-voz">llamada</p>,
}));

const UNA = "una-aseguradora";

let quitar: (() => void) | undefined;

afterEach(() => {
  quitar?.();
  quitar = undefined;
});

function servirConAcento(accent: string, accentOnDark: string): void {
  const [primera] = siteExample.tenants;
  if (primera === undefined) {
    throw new Error("the example has no insurer");
  }
  const directorio = {
    ...siteExample,
    tenants: [
      {
        ...primera,
        tenant_id: UNA,
        brand: { ...primera.brand, accent, accent_on_dark: accentOnDark },
      },
    ],
  };
  quitar = installFakeServer((ruta) =>
    ruta === "/api/site" ? jsonResponse(directorio) : jsonResponse({}, 404),
  );
}

describe("el acento de la aseguradora en sus pantallas", () => {
  it.each([
    ["el chat", `/t/${UNA}/chat`, "sonda-chat"],
    ["la llamada", `/t/${UNA}/call`, "sonda-voz"],
  ] as const)("%s queda dentro del ambito del acento de su aseguradora", async (_, ruta, sonda) => {
    servirConAcento("#112233", "#aabbcc");
    renderRoute(ruta);

    const dentro = await screen.findByTestId(sonda);
    await vi.waitFor(() => {
      const ambito = dentro.closest<HTMLElement>("[data-tenant-scope]");
      expect(ambito?.style.getPropertyValue("--tenant-accent")).toBe("#112233");
    });
    const ambito = dentro.closest<HTMLElement>("[data-tenant-scope]");
    expect(ambito?.style.getPropertyValue("--tenant-accent-on-dark")).toBe("#aabbcc");
  });

  it("la barra sigue con el cobre de Cautelia, y el chat no lleva pie", async () => {
    servirConAcento("#112233", "#aabbcc");
    renderRoute(`/t/${UNA}/chat`);
    await screen.findByTestId("sonda-chat");

    for (const id of ["language-selector", "theme-toggle"]) {
      expect(screen.getByTestId(id).closest("[data-tenant-scope]")).toBeNull();
    }
    expect(screen.queryByTestId("site-footer")).toBeNull();
  });
});

describe("lo que era naranja en la conversacion y la llamada", () => {
  // Una convencion que solo se sostiene en la memoria de quien escribe no es una
  // practica del equipo: se comprueba por texto, como los colores de `tokens.test.ts`.
  it.each([
    ["el chat", chatSource],
    ["la llamada", voiceSource],
  ] as const)("%s no usa el cobre de la marca: usa el acento de la aseguradora", (_, fuente) => {
    expect(fuente).not.toMatch(/\b(bg|text|border|ring|outline)-brand\b/);
    expect(fuente).not.toContain("on-brand");
    expect(fuente).not.toContain('variant="primary"');
  });

  it("el chat si pinta su avatar, sus burbujas y su boton de enviar con el acento", () => {
    expect(chatSource).toMatch(/bg-tenant[^"]*text-on-tenant/);
    expect(chatSource).toContain('variant="tenant"');
    expect(chatSource).toContain("text-tenant");
  });
});
