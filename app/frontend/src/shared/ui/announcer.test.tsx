import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AnnouncerProvider, useAnnouncer, type AnnouncerContextValue } from "./announcer";

// BR7.5, AC1.33.4: un solo anunciador cortes y uno de alerta; lo transmitido por
// partes se anuncia una sola vez, completo.

function montar(): { anunciador: () => AnnouncerContextValue; cambios: () => string[] } {
  let valor: AnnouncerContextValue | undefined;
  function Captura() {
    valor = useAnnouncer();
    return null;
  }
  render(
    <AnnouncerProvider>
      <Captura />
    </AnnouncerProvider>,
  );
  const region = screen.getByTestId("announcer-status");
  const anunciados: string[] = [];
  new MutationObserver(() => {
    const texto = region.textContent;
    if (texto !== "") {
      anunciados.push(texto);
    }
  }).observe(region, { childList: true, subtree: true, characterData: true });
  return {
    anunciador: () => {
      if (valor === undefined) {
        throw new Error("the announcer was not captured");
      }
      return valor;
    },
    cambios: () => anunciados,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("el anunciador compartido", () => {
  it("hay exactamente una region cortes y una de alerta", () => {
    montar();
    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.getByRole("status").getAttribute("aria-live")).toBe("polite");
    expect(screen.getByRole("alert").getAttribute("aria-live")).toBe("assertive");
  });

  it("un texto transmitido en diez partes se anuncia una sola vez, completo", async () => {
    const { anunciador, cambios } = montar();
    const flujo = anunciador().stream();

    await act(async () => {
      for (const parte of [
        "Uno ",
        "dos ",
        "tres ",
        "cuatro ",
        "cinco ",
        "seis ",
        "siete ",
        "ocho ",
        "nueve ",
        "diez",
      ]) {
        flujo.push(parte);
      }
      flujo.end();
      flujo.end();
      await Promise.resolve();
    });

    expect(cambios()).toEqual(["Uno dos tres cuatro cinco seis siete ocho nueve diez"]);
  });

  it("la alerta va a su propia region y un texto vacio no se anuncia", () => {
    const { anunciador } = montar();

    act(() => {
      anunciador().announce("   ");
      anunciador().announce("Emergencia", "alert");
    });

    expect(screen.getByTestId("announcer-alert").textContent).toBe("Emergencia");
    expect(screen.getByTestId("announcer-status").textContent).toBe("");
  });

  it("el mismo texto dos veces se vuelve a decir", async () => {
    const { anunciador, cambios } = montar();

    await act(async () => {
      anunciador().announce("Listo");
      await Promise.resolve();
    });
    await act(async () => {
      anunciador().announce("Listo");
      await Promise.resolve();
    });

    expect(cambios()).toEqual(["Listo", "Listo"]);
  });

  it("fuera del proveedor falla nombrando lo que falta", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    function Suelto() {
      useAnnouncer();
      return null;
    }
    expect(() => render(<Suelto />)).toThrow(/AnnouncerProvider/);
  });
});
