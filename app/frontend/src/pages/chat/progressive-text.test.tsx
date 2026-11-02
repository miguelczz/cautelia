import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  MAX_REVEAL_MS,
  ProgressiveText,
  WORD_MS,
  msPerWord,
  prefersReducedMotion,
} from "./progressive-text";

// Lo que se comprueba es lo que la persona y su lector de pantalla reciben: el texto entero
// siempre, de a poco a la vista, sin pasarse de 1,5 s y sin animacion si la persona la evita.

const FRASE = "Gracias por contarme lo que pasó, ya anoté el lugar";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

/** El texto que se ve (lo que no esta oculto de los lectores de pantalla). */
function visible(contenedor: HTMLElement): string {
  return contenedor.querySelector("[aria-hidden='true']")?.textContent ?? contenedor.textContent;
}

describe("el texto de la agente palabra por palabra", () => {
  it("empieza vacio, crece palabra por palabra y termina como texto plano", () => {
    const { container } = render(<ProgressiveText text={FRASE} animate />);
    const palabras = FRASE.split(" ").length;

    act(() => {
      vi.advanceTimersByTime(30);
    });
    const alPrincipio = visible(container).split(" ").filter(Boolean).length;
    expect(alPrincipio).toBeGreaterThanOrEqual(1);
    expect(alPrincipio).toBeLessThan(palabras);

    act(() => {
      vi.advanceTimersByTime(WORD_MS * 4);
    });
    expect(visible(container).split(" ").filter(Boolean).length).toBeGreaterThan(alPrincipio);

    act(() => {
      vi.advanceTimersByTime(MAX_REVEAL_MS);
    });
    expect(container.querySelector("[aria-hidden='true']")).toBeNull();
    expect(container.textContent).toBe(FRASE);
  });

  it("el lector de pantalla tiene el mensaje entero mientras se revela, y una sola vez", () => {
    const { container } = render(<ProgressiveText text={FRASE} animate />);

    act(() => {
      vi.advanceTimersByTime(60);
    });

    const soloLector = container.querySelector(".sr-only");
    expect(soloLector?.textContent).toBe(FRASE);
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
  });

  it("un mensaje largo no pasa de 1,5 s", () => {
    const largo = Array.from({ length: 200 }, (_, i) => `palabra${String(i)}`).join(" ");
    const { container } = render(<ProgressiveText text={largo} animate />);

    act(() => {
      vi.advanceTimersByTime(MAX_REVEAL_MS + 60);
    });

    expect(container.querySelector("[aria-hidden='true']")).toBeNull();
    expect(container.textContent).toBe(largo);
    expect(msPerWord(200) * 200).toBeLessThanOrEqual(MAX_REVEAL_MS);
    expect(msPerWord(3)).toBe(WORD_MS);
  });

  it("conserva los saltos de linea y los espacios del mensaje", () => {
    const lista = "Me falta esto:\n- qué pasó\n- cuándo y dónde ocurrió";
    const { container } = render(<ProgressiveText text={lista} animate />);

    act(() => {
      vi.advanceTimersByTime(MAX_REVEAL_MS + 60);
    });

    expect(container.textContent).toBe(lista);
  });

  it("avisa cada avance y cuando termina, una sola vez", () => {
    const crece = vi.fn();
    const termina = vi.fn();
    render(<ProgressiveText text={FRASE} animate onGrow={crece} onDone={termina} />);
    expect(termina).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(MAX_REVEAL_MS + 60);
    });

    expect(crece).toHaveBeenCalled();
    expect(termina).toHaveBeenCalledTimes(1);
  });

  it("sin animacion el texto sale entero y ya terminado", () => {
    const termina = vi.fn();
    const { container } = render(<ProgressiveText text={FRASE} animate={false} onDone={termina} />);

    expect(container.querySelector("[aria-hidden='true']")).toBeNull();
    expect(screen.getByText(FRASE)).toBeTruthy();
    expect(termina).toHaveBeenCalledTimes(1);
  });

  it("con movimiento reducido sale entero de una vez", () => {
    const original = Object.getOwnPropertyDescriptor(window, "matchMedia");
    window.matchMedia = ((consulta: string) => ({
      matches: consulta.includes("prefers-reduced-motion"),
    })) as unknown as typeof window.matchMedia;
    try {
      const termina = vi.fn();
      const { container } = render(<ProgressiveText text={FRASE} animate onDone={termina} />);

      expect(prefersReducedMotion()).toBe(true);
      expect(container.querySelector("[aria-hidden='true']")).toBeNull();
      expect(container.textContent).toBe(FRASE);
      expect(termina).toHaveBeenCalledTimes(1);
    } finally {
      if (original === undefined) {
        Reflect.deleteProperty(window, "matchMedia");
      } else {
        Object.defineProperty(window, "matchMedia", original);
      }
    }
  });

  it("una sola palabra no se anima", () => {
    const { container } = render(<ProgressiveText text="Listo." animate />);

    expect(container.querySelector("[aria-hidden='true']")).toBeNull();
    expect(container.textContent).toBe("Listo.");
  });
});
