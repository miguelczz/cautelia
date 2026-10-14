import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { reportConnectivityLost } from "./connectivity";
import {
  ATTEMPT_TIMEOUT_MS,
  GIVE_UP_AFTER_MS,
  POLL_INTERVAL_MS,
  reduceReadiness,
  startReadiness,
  useReadiness,
  type ReadinessWatch,
} from "./readiness";
import type { ReadyOutcome } from "./site";

// NFR16.5, BR5.4: la espera consulta cada 5 s, pasa a "no disponible" a los 60 y
// vuelve sola a la ruta pedida al despertar. Con reloj simulado, sin esperar de
// verdad.

function consultas(respuestas: (ReadyOutcome | "cuelga")[]) {
  const llamadas: AbortSignal[] = [];
  const check = vi.fn((signal: AbortSignal): Promise<ReadyOutcome> => {
    llamadas.push(signal);
    const respuesta = respuestas.shift() ?? "not_ready";
    if (respuesta === "cuelga") {
      return new Promise((_, rechazar) => {
        signal.addEventListener("abort", () => {
          rechazar(new DOMException("the attempt was aborted", "AbortError"));
        });
      });
    }
    return Promise.resolve(respuesta);
  });
  return { check, llamadas };
}

async function avanzar(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers({ now: 1_000_000 });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("la maquina de estados de la espera", () => {
  const inicio: ReadinessWatch = startReadiness(0, "/status/link_expired");

  it("empieza comprobando y guarda la ruta pedida", () => {
    expect(inicio).toEqual({
      state: "checking",
      startedAt: 0,
      attempts: 0,
      requestedRoute: "/status/link_expired",
    });
  });

  it("un evento que no aplica no cambia nada", () => {
    expect(reduceReadiness(inicio, { type: "retry", now: 1 })).toBe(inicio);
    expect(reduceReadiness(inicio, { type: "connectivity_lost", now: 1 })).toBe(inicio);
    expect(reduceReadiness(inicio, { type: "tick", now: GIVE_UP_AFTER_MS })).toBe(inicio);
    const lista = reduceReadiness(inicio, { type: "ready" });
    expect(reduceReadiness(lista, { type: "not_ready", now: 1 })).toBe(lista);
    expect(reduceReadiness(lista, { type: "ready" })).toBe(lista);
  });

  it("un fallo despues de los 60 s va directo a no disponible", () => {
    const despertando = reduceReadiness(inicio, { type: "not_ready", now: 1 });
    expect(reduceReadiness(despertando, { type: "not_ready", now: GIVE_UP_AFTER_MS }).state).toBe(
      "unavailable",
    );
  });
});

describe("la espera con reloj simulado", () => {
  it("con el proceso listo pasa a listo con una sola consulta", async () => {
    const { check } = consultas(["ready"]);
    const { result } = renderHook(() => useReadiness({ check }));

    await avanzar(0);

    expect(result.current.watch.state).toBe("ready");
    expect(check).toHaveBeenCalledOnce();
  });

  it("dormido: despierta, consulta cada 5 s y vuelve solo al estar listo", async () => {
    const { check } = consultas(["not_ready", "not_ready", "ready"]);
    const { result } = renderHook(() => useReadiness({ check }));

    await avanzar(0);
    expect(result.current.watch.state).toBe("waking");
    expect(check).toHaveBeenCalledTimes(1);

    await avanzar(POLL_INTERVAL_MS - 1);
    expect(check).toHaveBeenCalledTimes(1);
    await avanzar(1);
    expect(check).toHaveBeenCalledTimes(2);
    expect(result.current.watch.attempts).toBe(2);

    await avanzar(POLL_INTERVAL_MS);
    expect(check).toHaveBeenCalledTimes(3);
    expect(result.current.watch.state).toBe("ready");
    expect(result.current.watch.requestedRoute).toBe(window.location.pathname);
  });

  it("a los 60 s sin estar listo pasa a no disponible y deja de consultar", async () => {
    const { check } = consultas([]);
    const { result } = renderHook(() => useReadiness({ check }));

    await avanzar(0);
    await avanzar(GIVE_UP_AFTER_MS - 1);
    expect(result.current.watch.state).toBe("waking");

    await avanzar(1);
    expect(result.current.watch.state).toBe("unavailable");
    const consultasHechas = check.mock.calls.length;

    await avanzar(POLL_INTERVAL_MS * 3);
    expect(check).toHaveBeenCalledTimes(consultasHechas);
  });

  it("desde no disponible, Reintentar vuelve a comprobar", async () => {
    const respuestas: (ReadyOutcome | "cuelga")[] = [];
    const { check } = consultas(respuestas);
    const { result } = renderHook(() => useReadiness({ check }));
    await avanzar(0);
    await avanzar(GIVE_UP_AFTER_MS);
    expect(result.current.watch.state).toBe("unavailable");

    respuestas.push("ready");
    act(() => {
      result.current.retry();
    });
    expect(result.current.watch.state).toBe("checking");
    await avanzar(0);

    expect(result.current.watch.state).toBe("ready");
  });

  it("una consulta que no responde cuenta como sin respuesta a los 4 s", async () => {
    const { check, llamadas } = consultas(["cuelga", "ready"]);
    const { result } = renderHook(() => useReadiness({ check }));

    await avanzar(ATTEMPT_TIMEOUT_MS - 1);
    expect(result.current.watch.state).toBe("checking");
    await avanzar(1);

    expect(llamadas[0]?.aborted).toBe(true);
    expect(result.current.watch.state).toBe("waking");
  });

  it("con el proceso listo, una llamada que pierde la conexion vuelve a comprobar", async () => {
    const { check } = consultas(["ready", "not_ready"]);
    const { result } = renderHook(() => useReadiness({ check }));
    await avanzar(0);
    expect(result.current.watch.state).toBe("ready");

    act(() => {
      reportConnectivityLost();
    });
    expect(result.current.watch.state).toBe("checking");
    await avanzar(0);
    expect(result.current.watch.state).toBe("waking");
  });
});
