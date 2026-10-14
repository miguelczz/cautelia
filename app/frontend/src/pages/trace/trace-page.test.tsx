import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../app/testing";
import type { TraceView } from "../../shared/api-client/chat";
import { TracePage } from "./trace-page";

// AC2.3.2 y AC2.3.3. La conducta que importa: una traza en curso **no** es "no
// encontrado", y lo que no hay que ver se ve exactamente igual venga de donde
// venga, porque el servidor responde lo mismo a las tres causas.

const LISTA: TraceView = {
  status: "ready",
  nodes: [{ node: "intake", duration_ms: 120, cost_usd: null, cost_status: "not_measured" }],
  clauses_retrieved: 3,
  clauses_verified: 2,
  latency_ms: 840,
  cost_usd: null,
  cost_status: "not_measured",
};

describe("el resumen de traza", () => {
  it("mientras carga dibuja un esqueleto, no una palabra suelta", () => {
    renderWithProviders(
      <TracePage
        tenantId="una-aseguradora"
        traceId="tr-1"
        load={() => new Promise(() => undefined)}
      />,
    );

    const carga = screen.getByTestId("page-skeleton");
    expect(carga.getAttribute("aria-busy")).toBe("true");
    expect(carga.textContent).toBe("Cargando");
  });

  it("muestra nodos, clausulas, latencia y costo, sin credencial", async () => {
    renderWithProviders(
      <TracePage tenantId="una-aseguradora" traceId="tr-1" load={() => Promise.resolve(LISTA)} />,
    );

    // El paso por lo que hizo, no por su nombre interno (fase 3, 2026-10-08).
    expect(await screen.findByText(/Entender lo que contaste y anotarlo/)).toBeTruthy();
    expect(screen.queryByText(/intake/)).toBeNull();
    expect(screen.getByRole("link", { name: "Volver a la conversación" })).toBeTruthy();
    expect(screen.getByText("3 / 2")).toBeTruthy();
    expect(screen.getByText("840 ms")).toBeTruthy();
    // Sin precio se dice "no medido", **nunca cero**: un cero se suma despues
    // como si fuera cierto.
    expect(screen.getAllByText(/No medido/).length).toBeGreaterThan(0);
  });

  it("una traza en curso lo dice y nunca dice que no existe", async () => {
    renderWithProviders(
      <TracePage
        tenantId="una-aseguradora"
        traceId="tr-1"
        load={() => Promise.resolve({ ...LISTA, status: "recording", nodes: [], latency_ms: null })}
      />,
    );

    expect(await screen.findByText(/se está registrando/i)).toBeTruthy();
    expect(screen.queryByText(/No hay nada que mostrar/)).toBeNull();
  });

  it("lo que no existe y lo de otro navegador se ven igual", async () => {
    // No se comparan dos pantallas distintas: el servidor devuelve `null` en los
    // dos casos, asi que lo que se comprueba es que esta pantalla **no tiene**
    // una rama que los separe. Una frase distinta aqui confirmaria que existe.
    renderWithProviders(
      <TracePage
        tenantId="una-aseguradora"
        traceId="tr-de-otro"
        load={() => Promise.resolve(null)}
      />,
    );

    expect(await screen.findByText(/No hay nada que mostrar/)).toBeTruthy();
  });

  it("mientras se registra vuelve a preguntar sola, y deja de hacerlo al terminar", async () => {
    vi.useFakeTimers();
    const respuestas: (TraceView | null)[] = [
      { ...LISTA, status: "recording", nodes: [], latency_ms: null },
      LISTA,
    ];
    const load = vi.fn(() => Promise.resolve(respuestas.shift() ?? LISTA));

    renderWithProviders(<TracePage tenantId="una-aseguradora" traceId="tr-1" load={load} />);
    await vi.advanceTimersByTimeAsync(0);
    expect(load).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(3000);
    expect(load).toHaveBeenCalledTimes(2);

    // Ya esta lista: una traza terminada no cambia, y seguir preguntando seria
    // trabajo que nadie mira.
    await vi.advanceTimersByTimeAsync(9000);
    expect(load).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
});
