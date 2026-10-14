import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import siteExample from "../../../../contracts/examples/site-directory.json";
import { TenantScope } from "./tenant-scope";

// El ambito de una aseguradora lleva su acento a lo que haya dentro, sin ser una caja:
// el chat llena la vista y depende de que no estorbe (decision de Miguel, 2026-10-07).

describe("el ambito de una aseguradora", () => {
  it.each(siteExample.tenants.map((aseguradora) => [aseguradora.display_name, aseguradora.brand]))(
    "%s: deja sus dos valores de acento como variables de lo que contiene",
    (_, marca) => {
      render(
        <TenantScope brand={marca}>
          <p data-testid="dentro">contenido</p>
        </TenantScope>,
      );
      const ambito = screen.getByTestId("dentro").closest<HTMLElement>("[data-tenant-scope]");

      expect(ambito).not.toBeNull();
      expect(ambito?.style.getPropertyValue("--tenant-accent")).toBe(marca.accent);
      expect(ambito?.style.getPropertyValue("--tenant-accent-on-dark")).toBe(marca.accent_on_dark);
    },
  );

  it("no es una caja: no altera la distribucion de lo que contiene", () => {
    render(
      <TenantScope brand={siteExample.tenants[0]?.brand}>
        <p data-testid="dentro">contenido</p>
      </TenantScope>,
    );

    expect(screen.getByTestId("dentro").closest("[data-tenant-scope]")?.className).toContain(
      "contents",
    );
  });

  it("sin marca no inyecta nada y queda el cobre de Cautelia", () => {
    render(
      <TenantScope brand={undefined}>
        <p data-testid="dentro">contenido</p>
      </TenantScope>,
    );
    const ambito = screen.getByTestId("dentro").closest<HTMLElement>("[data-tenant-scope]");

    expect(ambito?.style.getPropertyValue("--tenant-accent")).toBe("");
  });
});
