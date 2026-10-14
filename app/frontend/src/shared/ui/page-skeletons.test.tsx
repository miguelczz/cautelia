import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LocaleProvider } from "../i18n/locale-provider";
import { createTranslate } from "../i18n/translate";
import { PageSkeleton, PanelBodySkeleton, RowsSkeleton, type SkeletonKind } from "./page-skeletons";

// Plan de estilos, seccion 4: toda pantalla tiene un esqueleto con su forma, ocupado
// para el lector y sin una sola palabra a la vista.

const FAMILIAS: readonly SkeletonKind[] = [
  "home",
  "guide",
  "policies",
  "panel",
  "cases",
  "compare",
  "chat",
  "call",
  "inbox",
  "case",
  "generic",
];

function dibujar(ui: React.ReactNode, locale: "es" | "en" = "es") {
  return render(<LocaleProvider initial={{ locale, source: "device" }}>{ui}</LocaleProvider>);
}

describe("los esqueletos de pantalla", () => {
  it.each(FAMILIAS)("%s: una region de estado ocupada, con su familia y con bloques", (familia) => {
    dibujar(<PageSkeleton kind={familia} />);
    const region = screen.getByTestId("page-skeleton");

    expect(region.getAttribute("role")).toBe("status");
    expect(region.getAttribute("aria-busy")).toBe("true");
    expect(region.getAttribute("data-skeleton-kind")).toBe(familia);
    // Bloques que se dibujan; ocultos al lector, que solo lee el texto de la region.
    expect(region.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(2);
  });

  it.each(FAMILIAS)("%s: ninguna palabra a la vista, solo el aviso para el lector", (familia) => {
    dibujar(<PageSkeleton kind={familia} />);
    const region = screen.getByTestId("page-skeleton");

    expect(region.textContent).toBe(createTranslate("es")("shell.loading"));
    expect(within(region).getByText(createTranslate("es")("shell.loading")).className).toContain(
      "sr-only",
    );
    expect(screen.queryByRole("heading")).toBeNull();
  });

  it("el aviso sale en el idioma de la pagina y se puede nombrar", () => {
    dibujar(<PageSkeleton kind="panel" label="Loading the figures" />, "en");
    expect(screen.getByTestId("page-skeleton").textContent).toBe("Loading the figures");

    dibujar(<PageSkeleton kind="generic" />, "en");
    expect(screen.getAllByText(createTranslate("en")("shell.loading"))).toHaveLength(1);
  });

  it("el esqueleto del inicio reserva las tres filas de aseguradora", () => {
    const { container } = dibujar(<PageSkeleton kind="home" />);
    // Las filas usan la rejilla de la fila real: mismo lugar, sin saltos al llegar.
    expect(container.querySelectorAll(".border-t.border-hairline")).toHaveLength(3);
  });

  it("el cuerpo de un panel y las filas de una lista se pueden usar dentro de una pantalla", () => {
    dibujar(
      <>
        <PanelBodySkeleton label="Cargando las cifras" />
        <RowsSkeleton rows={4} />
      </>,
    );
    const regiones = screen.getAllByTestId("page-skeleton");
    expect(regiones).toHaveLength(2);
    expect(regiones[0]?.textContent).toBe("Cargando las cifras");
    expect(regiones[1]?.querySelectorAll('[aria-hidden="true"]')).toHaveLength(4);
  });
});
