import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";

import { renderWithProviders } from "../../app/testing";
import { installFakeServer, jsonResponse } from "../../shared/api-client/fake-server";
import type { DocumentDetail, DocumentsCatalog } from "../../shared/api-client/policies";
import { createTranslate } from "../../shared/i18n/translate";
import { DocumentsButton } from "./documents-dialog";

// El panel de documentos (fase 2, 2026-10-08): el documento vigente primero, la
// version vieja marcada como no vigente, que endoso modifica cada clausula, cuantas
// veces se cito y un buscador que filtra.

const DOCUMENTOS: DocumentsCatalog = {
  tenant_id: "una-aseguradora",
  documents: [
    {
      form_id: "SA-PAP-2025",
      form_version: "2025.1",
      kind: "base",
      language: "es",
      clause_count: 1,
      in_force: false,
    },
    {
      form_id: "SA-PAP-2026",
      form_version: "2026.1",
      kind: "base",
      language: "es",
      clause_count: 2,
      in_force: true,
    },
    {
      form_id: "SA-PAP-2026-END-3",
      form_version: "2026.1",
      kind: "endorsement",
      language: "es",
      clause_count: 1,
      in_force: true,
    },
  ],
};

const DETALLE: DocumentDetail = {
  tenant_id: "una-aseguradora",
  form_id: "SA-PAP-2026",
  clauses: [
    {
      clause_id: "SA-PAP-2026-D.EXCL.3",
      clause_key: "D.EXCL.3",
      part: "Parte D — Daños a su vehículo",
      text: "No cubrimos equipos electrónicos no instalados de fábrica.",
      amended_by: ["SA-PAP-2026-END-3"],
      cited_last_week: 4,
      language: "es",
    },
    {
      clause_id: "SA-PAP-2026-A.INS",
      clause_key: "A.INS",
      part: "Parte A — Responsabilidad civil",
      text: "Pagamos los daños que usted cause a otras personas.",
      amended_by: [],
      cited_last_week: 0,
      language: "es",
    },
  ],
};

let quitar: (() => void) | undefined;

beforeAll(() => {
  // jsdom no trae `showModal`: el navegador si, y es lo que usa el panel.
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
});

afterEach(() => {
  quitar?.();
  quitar = undefined;
});

async function abrir() {
  quitar = installFakeServer((ruta) => {
    if (ruta === "/api/policies/una-aseguradora/documents") {
      return jsonResponse(DOCUMENTOS);
    }
    if (ruta === "/api/policies/una-aseguradora/documents/SA-PAP-2026") {
      return jsonResponse(DETALLE);
    }
    return jsonResponse({}, 404);
  });
  renderWithProviders(
    <DocumentsButton tenantId="una-aseguradora" insurerName="Seguros Aburrá" />,
    "es",
  );
  const t = createTranslate("es");
  fireEvent.click(
    screen.getByRole("button", {
      name: t("documents.open", { agent: t("insurer.agent.name") }),
    }),
  );
  await waitFor(() => {
    expect(screen.getByTestId("document-clauses")).toBeDefined();
  });
  return t;
}

describe("el panel de documentos", () => {
  it("abre en la poliza vigente y dice que endoso modifica y cuantas veces se cito", async () => {
    const t = await abrir();

    const clausulas = within(screen.getByTestId("document-clauses"));
    expect(clausulas.getByRole("heading", { level: 3 }).textContent).toBe(
      t("documents.kind_base", { year: "2026" }),
    );
    expect(
      clausulas.getByText(
        t("documents.amended_by", { names: t("documents.kind_endorsement", { number: "3" }) }),
      ),
    ).toBeDefined();
    expect(clausulas.getByText(t("documents.cited", { count: 4 }))).toBeDefined();
    expect(
      within(screen.getByTestId("documents-list")).getByText(
        new RegExp(t("documents.not_in_force")),
      ),
    ).toBeDefined();
  });

  it("mientras esta abierto la pagina de atras no se desplaza, y al cerrar vuelve como estaba", async () => {
    // La rueda sobre el fondo oscurecido movia la pagina (2026-10-08): `showModal()`
    // no bloquea el desplazamiento del documento, y esta ventana lo hace por su cuenta.
    document.documentElement.style.overflow = "clip";
    const t = await abrir();
    expect(document.documentElement.style.overflow).toBe("hidden");

    fireEvent.click(screen.getByRole("button", { name: t("documents.close") }));
    await waitFor(() => {
      expect(document.documentElement.style.overflow).toBe("clip");
    });
    document.documentElement.style.overflow = "";
  });

  it("el buscador deja solo las clausulas que coinciden", async () => {
    const t = await abrir();

    fireEvent.change(screen.getByLabelText(t("documents.search_label")), {
      target: { value: "electrónicos" },
    });

    const clausulas = within(screen.getByTestId("document-clauses"));
    expect(clausulas.queryByText(/otras personas/)).toBeNull();
    expect(clausulas.getByText(/equipos electrónicos/)).toBeDefined();

    fireEvent.change(screen.getByLabelText(t("documents.search_label")), {
      target: { value: "granizo" },
    });
    expect(clausulas.getByText(t("documents.no_match"))).toBeDefined();
  });
});

describe("el panel de documentos con traduccion", () => {
  it("muestra la traduccion de referencia y el original a un clic", async () => {
    quitar = installFakeServer((ruta) => {
      if (ruta === "/api/policies/una-aseguradora/documents") {
        return jsonResponse(DOCUMENTOS);
      }
      if (ruta === "/api/policies/una-aseguradora/documents/SA-PAP-2026") {
        return jsonResponse({
          ...DETALLE,
          clauses: [
            {
              ...DETALLE.clauses[0],
              language: "en",
              text: "We do not cover electronic equipment.",
              translated_text: "No cubrimos equipos electrónicos.",
              translated_part: "Parte D — Daños a su vehículo",
            },
          ],
        });
      }
      return jsonResponse({}, 404);
    });
    renderWithProviders(
      <DocumentsButton tenantId="una-aseguradora" insurerName="Autos Poblado" />,
      "es",
    );
    const t = createTranslate("es");
    fireEvent.click(
      screen.getByRole("button", { name: t("documents.open", { agent: t("insurer.agent.name") }) }),
    );
    await waitFor(() => {
      expect(screen.getByText("No cubrimos equipos electrónicos.")).toBeDefined();
    });

    fireEvent.click(screen.getByRole("button", { name: t("documents.show_original") }));

    expect(screen.getByText("We do not cover electronic equipment.")).toBeDefined();
    expect(screen.queryByText("No cubrimos equipos electrónicos.")).toBeNull();
  });
});
