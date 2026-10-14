import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderRoute } from "../../app/testing";
import type {
  CaseDetailOut,
  InboxResult,
  QueuePage,
  RedeemOut,
} from "../../shared/api-client/inbox";
import { readStoredLocale } from "../../shared/i18n/initial-locale";

// Las cuatro rutas de la bandeja: los filtros en la direccion, el idioma que se
// recuerda y el token que no queda en la barra (BR5.6).

const pedidos = vi.hoisted(() => vi.fn<() => Promise<InboxResult<QueuePage>>>());
const detalle = vi.hoisted(() => vi.fn<() => Promise<InboxResult<CaseDetailOut>>>());
const canjeado = vi.hoisted(() => vi.fn<(token: string) => Promise<InboxResult<RedeemOut>>>());

vi.mock("../../shared/api-client/inbox", async (original) => {
  const real = await original<typeof import("../../shared/api-client/inbox")>();
  return { ...real, listCases: pedidos, caseDetail: detalle, redeemLink: canjeado };
});

vi.mock("../../shared/api-client/site", async (original) => {
  const real = await original<typeof import("../../shared/api-client/site")>();
  return {
    ...real,
    siteQueryOptions: () => ({
      queryKey: ["site"],
      queryFn: () => Promise.resolve({ tenants: [], surfaces: [], links: {} }),
    }),
  };
});

// `EventSource` no existe en jsdom y las pantallas de la bandeja abren su flujo al
// montarse. Se pone uno que no hace nada: lo que estas pruebas miden son las rutas
// --los filtros, el idioma que se recuerda y el token que deja la barra--, y el aviso
// en vivo tiene sus propias pruebas.
class FlujoDeMentira {
  onmessage: ((evento: MessageEvent<string>) => void) | null = null;
  onerror: ((evento: Event) => void) | null = null;
  onopen: ((evento: Event) => void) | null = null;
  close() {
    return undefined;
  }
}

beforeEach(() => {
  vi.stubGlobal("EventSource", FlujoDeMentira);
  pedidos.mockReset();
  detalle.mockReset();
  canjeado.mockReset();
  pedidos.mockResolvedValue({ ok: true, value: { items: [], next_cursor: null } });
  detalle.mockResolvedValue({
    ok: false,
    problem: { code: "not_found", message: (t) => t("problem.not_found") },
  });
  canjeado.mockResolvedValue({
    ok: false,
    problem: { code: "link_invalid", message: (t) => t("problem.link_invalid") },
  });
  window.localStorage.clear();
  vi.spyOn(console, "warn").mockImplementation(() => undefined);
});

describe("la cola dentro del enrutador", () => {
  it("lee los filtros de la direccion", async () => {
    renderRoute("/t/una-aseguradora/inbox?state=derived&priority=high");

    await screen.findByTestId("inbox-queue");
    expect(pedidos).toHaveBeenCalledWith("una-aseguradora", {
      state: "derived",
      priority: "high",
    });
  });

  it("descarta de la direccion lo que no es uno de los cuatro filtros", async () => {
    // Lo que la ruta no reconoce no viaja hasta la consulta: un parametro cualquiera
    // en la direccion no se arrastra al servidor.
    renderRoute("/t/una-aseguradora/inbox?state=derived&cualquiera=otra-cosa");

    await screen.findByTestId("inbox-queue");
    expect(pedidos).toHaveBeenCalledWith("una-aseguradora", { state: "derived" });
  });

  it("la cola mientras llega dibuja las filas como esqueleto, no una palabra", async () => {
    pedidos.mockReturnValue(new Promise(() => undefined));
    renderRoute("/t/una-aseguradora/inbox");

    const carga = await screen.findByTestId("page-skeleton");
    expect(carga.getAttribute("data-skeleton-kind")).toBe("inbox");
    expect(carga.getAttribute("aria-busy")).toBe("true");
  });

  it("el caso mientras llega dibuja su esqueleto", async () => {
    detalle.mockReturnValue(new Promise(() => undefined));
    renderRoute("/t/una-aseguradora/inbox/caso-1");

    const carga = await screen.findByTestId("page-skeleton");
    expect(carga.getAttribute("data-skeleton-kind")).toBe("case");
  });

  it("el idioma elegido en la bandeja se recuerda, como en cualquier otra pantalla", async () => {
    renderRoute("/t/una-aseguradora/inbox", "es");
    await screen.findByTestId("inbox-queue");

    await userEvent.click(screen.getByRole("button", { name: "English" }));

    expect(readStoredLocale()).toBe("en");
  });
});

describe("el canje del enlace", () => {
  it("un enlace que no vale muestra la pagina de estado, sin decir la causa", async () => {
    window.location.hash = "#un-token-que-no-vale";
    renderRoute("/c");

    const pagina = await screen.findByTestId("status-page");
    expect(pagina.getAttribute("data-status-kind")).toBe("link_invalid");
  });

  it("el token deja la barra en cuanto se canja, y la ruta pasa al caso (BR5.6)", async () => {
    canjeado.mockResolvedValue({
      ok: true,
      value: {
        case_id: "case-1",
        tenant: "una-aseguradora",
        access: "view_and_decide",
        expires_at: "2026-09-28T13:00:00+00:00",
      },
    });
    window.location.hash = "#el-token";
    const { router } = renderRoute("/c");

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/c/una-aseguradora/case-1");
    });
    // Un token en la barra queda en cada captura de pantalla y en cada registro que la
    // vea pasar, y vale una hora.
    expect(window.location.hash).toBe("");
    expect(router.state.location.pathname).not.toContain("el-token");
  });
});
