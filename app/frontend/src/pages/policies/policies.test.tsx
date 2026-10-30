import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import sitio from "../../../../contracts/examples/site-directory.json";
import { renderWithProviders } from "../../app/testing";
import { installFakeServer, jsonResponse } from "../../shared/api-client/fake-server";
import type { PolicyCatalog } from "../../shared/api-client/policies";
import type { SiteDirectory } from "../../shared/api-client/site";
import { createTranslate } from "../../shared/i18n/translate";
import { formatPesos, PoliciesPage } from "./policies-page";

// La pestana de polizas (fase 2, 2026-10-08): que se ve de cada poliza, los montos en
// pesos multiplicando por mil y las preguntas que abren el chat ya enviadas.

const directorio = sitio as SiteDirectory;
const primera = directorio.tenants[0];
if (primera === undefined) {
  throw new Error("el ejemplo del directorio no trae aseguradoras");
}

const CATALOGO: PolicyCatalog = {
  tenant_id: primera.tenant_id,
  example_policy: "POL-11",
  policies: [
    {
      policy_number: "POL-11",
      holder_name: "Natalia Henao Rendón",
      issuer_name: "Seguros Aburrá",
      vehicles: ["Renault Logan 2024"],
      period_start: "2026-01-02",
      period_end: "2027-01-02",
      limits: { "a.bodily_injury_per_person": 100000, "d.collision_deductible": 250 },
      endorsements: [{ form_id: "SA-PAP-2026-END-3", clause_keys: ["D.EXCL.3"] }],
      questions: ["hail"],
    },
    {
      policy_number: "POL-14",
      holder_name: "Julián Posada Arango",
      issuer_name: "Seguros Aburrá",
      vehicles: ["Nissan Versa 2020"],
      period_start: "2026-05-04",
      period_end: "2027-05-04",
      limits: {},
      endorsements: [],
      questions: [],
    },
  ],
};

let quitar: (() => void) | undefined;

afterEach(() => {
  quitar?.();
  quitar = undefined;
});

async function dibujar(inicial?: string) {
  quitar = installFakeServer((ruta) => {
    if (ruta === "/api/site") {
      return jsonResponse(directorio);
    }
    if (ruta === `/api/policies/${primera?.tenant_id ?? ""}`) {
      return jsonResponse(CATALOGO);
    }
    return jsonResponse({}, 404);
  });
  renderWithProviders(<PoliciesPage initialTenantId={inicial} />, "es");
  await waitFor(() => {
    expect(screen.getByTestId("policy-detail")).toBeDefined();
  });
  return createTranslate("es");
}

describe("la pestana de polizas", () => {
  it("abre en la poliza de ejemplo, con sus montos en pesos por mil", async () => {
    const t = await dibujar();

    const detalle = screen.getByTestId("policy-detail");
    expect(within(detalle).getByRole("heading", { level: 2 }).textContent).toBe("POL-11");
    const montos = within(screen.getByTestId("policy-limits"));
    expect(montos.getByText(t("policies.limit.a_bodily_injury_per_person"))).toBeDefined();
    expect(montos.getAllByRole("definition").map((celda) => celda.textContent)).toContain(
      formatPesos(100000, "es"),
    );
    expect(formatPesos(100000, "es").replace(/\D/g, "")).toBe("100000000");
    expect(
      within(screen.getByTestId("policy-endorsements")).getByText(
        t("policies.endorsement.d_excl_3"),
      ),
    ).toBeDefined();
  });

  it("cada pregunta abre el chat con la poliza, el titular y la pregunta ya escritos", async () => {
    const t = await dibujar();

    const boton = within(screen.getByTestId("policy-questions")).getByRole("link", {
      name: t("policies.question.hail"),
    });
    const destino = new URL(boton.getAttribute("href") ?? "", "https://x.test");
    expect(destino.pathname).toBe(`/t/${primera.tenant_id}/chat`);
    expect(destino.searchParams.get("ask")).toBe(
      t("policies.ask_question", {
        name: "Natalia Henao Rendón",
        policy: "POL-11",
        question: t("policies.question.hail"),
      }),
    );
  });

  it("elegir otra poliza cambia el detalle, y sin endosos lo dice", async () => {
    const t = await dibujar();

    fireEvent.click(screen.getByRole("button", { name: /POL-14/ }));

    const detalle = screen.getByTestId("policy-detail");
    expect(within(detalle).getByRole("heading", { level: 2 }).textContent).toBe("POL-14");
    expect(within(detalle).getByText(t("policies.no_endorsements"))).toBeDefined();
  });

  it("abre en la aseguradora que pide la direccion, y en la primera si no existe", async () => {
    const segunda = directorio.tenants[1];
    if (segunda === undefined) {
      throw new Error("el ejemplo del directorio no trae una segunda aseguradora");
    }
    quitar = installFakeServer((ruta) =>
      ruta === "/api/site" ? jsonResponse(directorio) : jsonResponse({}, 404),
    );
    renderWithProviders(<PoliciesPage initialTenantId={segunda.tenant_id} />, "es");

    const grupo = await screen.findByTestId("policies-insurers");
    const elegida = within(grupo).getByRole("button", { name: segunda.display_name });
    expect(elegida.getAttribute("aria-pressed")).toBe("true");
  });

  it("en escritorio la pagina no se desplaza: la lista y el detalle se reparten el alto de la ventana y cada uno se desplaza por dentro", async () => {
    await dibujar();

    // El contenido mide lo que queda de la ventana y sus dos paneles no lo pasan.
    expect(screen.getByTestId("policies").className).toContain("roomy:flex-1");
    expect(screen.getByTestId("policies").className).toContain("roomy:min-h-0");
    const lista = screen.getByTestId("policy-list");
    expect(lista.className).toContain("roomy:overflow-y-auto");
    // Si la ventana es baja y no caben las seis, el borde que sigue se funde con el fondo:
    // ninguna tarjeta queda cortada a ras.
    expect(lista.className).toContain("ut-scroll-fade-y");
    expect(lista.parentElement?.className).toContain("roomy:grid-rows-[minmax(0,1fr)]");
    const celda = screen.getByTestId("policy-detail-cell");
    expect(celda.className).toContain("roomy:relative");
    const detalle = screen.getByTestId("policy-detail");
    expect(celda.contains(detalle)).toBe(true);
    expect(detalle.className).toContain("roomy:absolute");
    expect(detalle.className).toContain("roomy:inset-0");
    // El marco del detalle queda quieto y lo que se desplaza es lo de dentro, con su desvanecido.
    const interior = detalle.firstElementChild;
    expect(interior?.className).toContain("roomy:overflow-y-auto");
    expect(interior?.className).toContain("ut-scroll-fade-y");
  });

  it("la aseguradora elegida lleva una linea en su acento y ningun fondo", async () => {
    await dibujar();

    const grupo = screen.getByTestId("policies-insurers");
    const elegida = within(grupo).getByRole("button", { pressed: true });
    expect(elegida.hasAttribute("data-tenant-scope")).toBe(true);
    expect(elegida.className).not.toContain("bg-selected");
    expect(elegida.querySelector("[aria-hidden]")?.className).toContain("bg-tenant");
    expect(elegida.querySelector("[aria-hidden]")?.className).toContain("scale-x-100");
  });
});
