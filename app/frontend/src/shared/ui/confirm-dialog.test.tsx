import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./confirm-dialog";

// `jsdom` no trae `showModal` ni `close`. Estos dobles hacen lo que el navegador hace con
// lo que el componente observa: marcar la ventana abierta, y al cerrar --sea por la
// prop o por Escape-- avisar con el evento `close`. Que el foco quede atrapado dentro
// y que Escape cierre es del `<dialog>` del navegador; lo que se comprueba aqui es que
// el componente use `showModal` (y no `show`, que no atrapa nada) y que haga su parte.
const showModal = vi.fn(function showModal(this: HTMLDialogElement) {
  this.setAttribute("open", "");
});

beforeEach(() => {
  showModal.mockClear();
  HTMLDialogElement.prototype.showModal = showModal;
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
});

afterEach(() => {
  document.documentElement.style.overflow = "";
});

/** Un disparador y su ventana, como los usa una pantalla. */
function Caso({
  alConfirmar = vi.fn(),
  pending = false,
}: {
  readonly alConfirmar?: () => void;
  readonly pending?: boolean;
}) {
  const [abierta, setAbierta] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => {
          setAbierta(true);
        }}
      >
        Abrir
      </button>
      <ConfirmDialog
        open={abierta}
        title="¿Seguro?"
        description="Esto cierra la conversación."
        cancelLabel="Cancelar"
        confirmLabel="Reiniciar"
        pending={pending}
        testId="confirmacion"
        onCancel={() => {
          setAbierta(false);
        }}
        onConfirm={alConfirmar}
      />
    </>
  );
}

describe("la ventana de confirmacion", () => {
  it("se abre como modal, con su titulo y su descripcion como nombre accesible", async () => {
    render(<Caso />);
    const ventana = screen.getByTestId("confirmacion");
    expect(showModal).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));

    expect(showModal).toHaveBeenCalledTimes(1);
    expect(ventana.hasAttribute("open")).toBe(true);
    expect(ventana.getAttribute("aria-labelledby")).toBe(
      screen.getByRole("heading", { name: "¿Seguro?" }).id,
    );
    expect(ventana.getAttribute("aria-describedby")).toBe(
      screen.getByText("Esto cierra la conversación.").id,
    );
  });

  it("deja quieta la pagina de atras mientras esta abierta, y la suelta al cerrar", async () => {
    render(<Caso />);

    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));
    expect(document.documentElement.style.overflow).toBe("hidden");

    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(document.documentElement.style.overflow).toBe("");
  });

  it("Cancelar cierra sin confirmar y devuelve el foco al boton que la abrio", async () => {
    const alConfirmar = vi.fn();
    render(<Caso alConfirmar={alConfirmar} />);
    const disparador = screen.getByRole("button", { name: "Abrir" });
    await userEvent.click(disparador);

    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(alConfirmar).not.toHaveBeenCalled();
    expect(screen.getByTestId("confirmacion").hasAttribute("open")).toBe(false);
    expect(document.activeElement).toBe(disparador);
  });

  it("Escape la cierra --el navegador cierra el dialogo sin pasar por la prop-- y el foco vuelve", async () => {
    const alConfirmar = vi.fn();
    render(<Caso alConfirmar={alConfirmar} />);
    const disparador = screen.getByRole("button", { name: "Abrir" });
    await userEvent.click(disparador);
    const ventana = screen.getByTestId("confirmacion");

    // Lo que hace el navegador con Escape: cierra el dialogo y avisa.
    act(() => {
      ventana.removeAttribute("open");
      ventana.dispatchEvent(new Event("close"));
    });

    expect(alConfirmar).not.toHaveBeenCalled();
    // Y el padre se entera: puede volver a abrirla.
    await userEvent.click(disparador);
    expect(showModal).toHaveBeenCalledTimes(2);
  });

  it("confirmar llama a quien la usa, que decide cuando cerrar", async () => {
    const alConfirmar = vi.fn();
    render(<Caso alConfirmar={alConfirmar} />);
    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));

    await userEvent.click(screen.getByRole("button", { name: "Reiniciar" }));

    expect(alConfirmar).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("confirmacion").hasAttribute("open")).toBe(true);
  });

  it("mientras el gesto esta en curso, los botones esperan y Escape no cierra", async () => {
    render(<Caso pending />);
    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));

    expect(screen.getByRole("button", { name: "Cancelar" }).hasAttribute("disabled")).toBe(true);
    const confirmar = screen.getByRole("button", { name: "Reiniciar" });
    expect(confirmar.hasAttribute("disabled")).toBe(true);
    expect(confirmar.getAttribute("aria-busy")).toBe("true");

    const escape = new Event("cancel", { cancelable: true });
    screen.getByTestId("confirmacion").dispatchEvent(escape);
    expect(escape.defaultPrevented).toBe(true);
  });

  it("anima la entrada solo con movimiento permitido", () => {
    render(<Caso />);
    const clases = screen.getByTestId("confirmacion").className.split(/\s+/);

    // Ni una animacion que no pase por `motion-safe:`: con movimiento reducido no hay ninguna.
    const animaciones = clases.filter((c) => c.includes("animate-"));
    expect(animaciones.length).toBeGreaterThan(0);
    for (const clase of animaciones) {
      expect(clase.startsWith("motion-safe:")).toBe(true);
    }
    expect(clases.some((c) => c.includes("ut-dialog-in"))).toBe(true);
  });
});
