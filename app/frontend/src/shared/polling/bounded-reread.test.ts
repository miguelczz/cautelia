import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { startBoundedReread } from "./bounded-reread";

// Volver a leer unas cuantas veces y parar: con tope, con corte y con cancelacion.

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

function armar(valores: readonly string[], opciones: { maxReads?: number } = {}) {
  let siguiente = 0;
  const read = vi.fn(() => {
    const valor = valores[Math.min(siguiente, valores.length - 1)] ?? "";
    siguiente += 1;
    return Promise.resolve(valor);
  });
  const recibido: string[] = [];
  const cancelar = startBoundedReread({
    read,
    onResult: (valor) => recibido.push(valor),
    keepGoing: (valor) => valor === "pendiente",
    everyMs: 2000,
    maxReads: opciones.maxReads ?? 8,
  });
  return { read, recibido, cancelar };
}

describe("volver a leer de forma acotada", () => {
  it("no lee de inmediato: espera el intervalo antes de la primera relectura", async () => {
    const { read } = armar(["pendiente"]);

    await vi.advanceTimersByTimeAsync(1999);
    expect(read).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    expect(read).toHaveBeenCalledTimes(1);
  });

  it("relee mientras el valor lo pida y se detiene en cuanto deja de pedirlo", async () => {
    const { read, recibido } = armar(["pendiente", "pendiente", "listo"]);

    await vi.advanceTimersByTimeAsync(2000 * 3);
    expect(recibido).toEqual(["pendiente", "pendiente", "listo"]);

    // Pasa mucho mas tiempo y no se vuelve a pedir nada.
    await vi.advanceTimersByTimeAsync(2000 * 20);
    expect(read).toHaveBeenCalledTimes(3);
  });

  it("se detiene en el tope aunque el valor siga pidiendo otra lectura", async () => {
    const { read } = armar(["pendiente"], { maxReads: 8 });

    await vi.advanceTimersByTimeAsync(2000 * 30);

    expect(read).toHaveBeenCalledTimes(8);
  });

  it("cancelar limpia el temporizador: no vuelve a leer", async () => {
    const { read, cancelar } = armar(["pendiente"]);
    await vi.advanceTimersByTimeAsync(2000);
    expect(read).toHaveBeenCalledTimes(1);

    cancelar();
    await vi.advanceTimersByTimeAsync(2000 * 20);

    expect(read).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("una lectura en vuelo cuando se cancela no entrega su resultado", async () => {
    let resolver: (valor: string) => void = () => undefined;
    const read = vi.fn(
      () =>
        new Promise<string>((resolve) => {
          resolver = resolve;
        }),
    );
    const onResult = vi.fn();
    const cancelar = startBoundedReread({
      read,
      onResult,
      keepGoing: () => true,
      everyMs: 2000,
      maxReads: 8,
    });
    await vi.advanceTimersByTimeAsync(2000);
    expect(read).toHaveBeenCalledTimes(1);

    cancelar();
    resolver("tarde");
    await vi.advanceTimersByTimeAsync(2000 * 5);

    expect(onResult).not.toHaveBeenCalled();
    expect(read).toHaveBeenCalledTimes(1);
  });

  it("con tope cero no programa nada", () => {
    const { read } = armar(["pendiente"], { maxReads: 0 });

    expect(vi.getTimerCount()).toBe(0);
    expect(read).not.toHaveBeenCalled();
  });
});
