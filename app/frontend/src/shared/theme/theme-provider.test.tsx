import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { THEME_STORAGE_KEY } from "./preference";
import { DARK_QUERY, stubMatchMedia } from "./testing";
import { ThemeProvider, useTheme } from "./theme-provider";

// F3 y la maquina 2.2 (BR1.1 enmendada 2026-10-06): sin eleccion, el modo es el
// oscuro de la landing y no sigue al dispositivo; la eleccion de la persona se
// aplica al instante y se guarda.

function Sonda() {
  const { mode, source, setMode } = useTheme();
  return (
    <div>
      <p data-testid="modo">{`${mode}/${source}`}</p>
      <button
        type="button"
        onClick={() => {
          setMode(mode === "dark" ? "light" : "dark");
        }}
      >
        cambiar
      </button>
    </div>
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("el proveedor de modo", () => {
  it("sin eleccion abre en oscuro y no cambia aunque el dispositivo cambie con la pagina abierta", () => {
    const medios = stubMatchMedia({ [DARK_QUERY]: false });
    render(
      <ThemeProvider>
        <Sonda />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("modo").textContent).toBe("dark/default");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    act(() => {
      medios.set(DARK_QUERY, true);
    });
    act(() => {
      medios.set(DARK_QUERY, false);
    });

    expect(screen.getByTestId("modo").textContent).toBe("dark/default");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("la eleccion de la persona manda, se guarda y el dispositivo no la toca", () => {
    const medios = stubMatchMedia({ [DARK_QUERY]: true });
    render(
      <ThemeProvider>
        <Sonda />
      </ThemeProvider>,
    );

    act(() => {
      screen.getByRole("button").click();
    });
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");

    act(() => {
      medios.set(DARK_QUERY, false);
    });
    expect(screen.getByTestId("modo").textContent).toBe("light/user");
  });

  it("con el almacenamiento bloqueado el cambio vale para la pestana y no hay error visible", () => {
    vi.spyOn(console, "info").mockImplementation(() => undefined);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("blocked", "QuotaExceededError");
    });
    render(
      <ThemeProvider>
        <Sonda />
      </ThemeProvider>,
    );

    act(() => {
      screen.getByRole("button").click();
    });

    expect(screen.getByTestId("modo").textContent).toBe("light/user");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("fuera del proveedor falla nombrando lo que falta", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<Sonda />)).toThrow(/ThemeProvider/);
  });
});
