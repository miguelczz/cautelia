import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import siteExample from "../../../../contracts/examples/site-directory.json";
import type { Locale } from "../copy/copy-keys";
import { LOCALE_STORAGE_KEY, SHARED_LOCALE_KEY } from "./initial-locale";
import { LocaleProvider, useLocale, useTenantDefaultLocale } from "./locale-provider";

// BR2.2 y BR2.4: el documento declara su idioma; una pagina de aseguradora se
// abre en el suyo salvo eleccion hecha en la pestana.

function Sonda({ tenantDefault }: { readonly tenantDefault?: Locale }) {
  const { locale, source, t, setLocale } = useLocale();
  return (
    <div>
      {tenantDefault === undefined ? null : <PaginaDeAseguradora idioma={tenantDefault} />}
      <p data-testid="idioma">{`${locale}/${source}`}</p>
      <p data-testid="texto">{t("status.not_found.title")}</p>
      <button
        type="button"
        onClick={() => {
          setLocale(locale === "es" ? "en" : "es");
        }}
      >
        cambiar
      </button>
    </div>
  );
}

function PaginaDeAseguradora({ idioma }: { readonly idioma: Locale }) {
  useTenantDefaultLocale(idioma);
  return null;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("el proveedor de idioma", () => {
  it("declara el idioma en el documento y lo cambia con la eleccion", () => {
    render(
      <LocaleProvider initial={{ locale: "es", source: "device" }}>
        <Sonda />
      </LocaleProvider>,
    );
    expect(document.documentElement.lang).toBe("es");

    act(() => {
      screen.getByRole("button", { name: "cambiar" }).click();
    });

    expect(document.documentElement.lang).toBe("en");
    expect(screen.getByTestId("idioma").textContent).toBe("en/user");
  });

  it("sin eleccion toma el idioma del dispositivo", () => {
    vi.spyOn(navigator, "languages", "get").mockReturnValue(["es-CO"]);
    render(
      <LocaleProvider>
        <Sonda />
      </LocaleProvider>,
    );
    expect(screen.getByTestId("idioma").textContent).toBe("es/device");
  });

  it("cada eleccion se recuerda, en la clave propia y en la que comparte con la landing", () => {
    render(
      <LocaleProvider initial={{ locale: "es", source: "device" }}>
        <Sonda />
      </LocaleProvider>,
    );
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBeNull();

    act(() => {
      screen.getByRole("button", { name: "cambiar" }).click();
    });

    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("en");
    expect(window.localStorage.getItem(SHARED_LOCALE_KEY)).toBe("en");
    expect(screen.getByTestId("idioma").textContent).toBe("en/user");
  });

  it("una visita nueva abre en lo que la persona eligio, aunque el dispositivo diga otra cosa", () => {
    vi.spyOn(navigator, "languages", "get").mockReturnValue(["es-CO"]);
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "en");
    render(
      <LocaleProvider>
        <Sonda tenantDefault="es" />
      </LocaleProvider>,
    );
    // La eleccion manda tambien sobre el idioma por defecto de la aseguradora.
    expect(screen.getByTestId("idioma").textContent).toBe("en/persisted");
  });

  it("el idioma que dejo la landing es una semilla: la aseguradora todavia puede aplicar el suyo", () => {
    window.localStorage.setItem(SHARED_LOCALE_KEY, "en");
    render(
      <LocaleProvider>
        <Sonda />
      </LocaleProvider>,
    );
    expect(screen.getByTestId("idioma").textContent).toBe("en/device");
  });

  it("sin permiso para guardar, la eleccion vale para la pestana", () => {
    vi.spyOn(console, "info").mockImplementation(() => undefined);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    render(
      <LocaleProvider initial={{ locale: "es", source: "device" }}>
        <Sonda />
      </LocaleProvider>,
    );

    act(() => {
      screen.getByRole("button", { name: "cambiar" }).click();
    });

    expect(screen.getByTestId("idioma").textContent).toBe("en/user");
  });

  it.each(
    siteExample.tenants.map((aseguradora) => [
      aseguradora.display_name,
      aseguradora.default_language,
    ]),
  )("la pagina de %s se abre en su idioma por defecto (%s)", (_, idioma) => {
    const otro: Locale = idioma === "es" ? "en" : "es";
    render(
      <LocaleProvider initial={{ locale: otro, source: "device" }}>
        <Sonda tenantDefault={idioma as Locale} />
      </LocaleProvider>,
    );
    expect(screen.getByTestId("idioma").textContent).toBe(`${idioma}/tenant_default`);
    expect(document.documentElement.lang).toBe(idioma);
  });

  it("una eleccion hecha en la pestana manda sobre el idioma de la aseguradora", () => {
    render(
      <LocaleProvider initial={{ locale: "en", source: "user" }}>
        <Sonda tenantDefault="es" />
      </LocaleProvider>,
    );
    expect(screen.getByTestId("idioma").textContent).toBe("en/user");
  });

  it("fuera del proveedor falla nombrando lo que falta", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<Sonda />)).toThrow(/LocaleProvider/);
  });
});
