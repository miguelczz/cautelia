import { describe, expect, it, vi } from "vitest";

import type { QueueItem } from "../../shared/api-client/inbox";
import {
  EMPTY_QUEUE,
  parseEvent,
  reduceQueue,
  touchesCase,
  withMore,
  withPage,
  type WireInboxEvent,
} from "./inbox-events";

// C-06, BR6.1 y BR6.2: los avisos se aplican sobre lo que la pantalla ya tiene, y
// lo que el aviso no dice no se inventa.

function fila(caseId: string, extra: Partial<QueueItem> = {}): QueueItem {
  return {
    case_id: caseId,
    case_number: `SA-${caseId}`,
    state: "derived",
    record_type: "claim",
    channel: "chat",
    language: "es",
    priority: "normal",
    completeness: 0.5,
    completeness_complete: 3,
    completeness_total: 7,
    derivation_reason: "rule",
    updated_at: "2026-09-28T12:00:00+00:00",
    ...extra,
  };
}

function aviso(kind: WireInboxEvent["kind"], caseId: string): WireInboxEvent {
  return { kind, case_id: caseId, summary: "algo cambio", at: "2026-09-28T12:05:00+00:00" };
}

describe("los avisos en vivo de la bandeja", () => {
  it("saca de la cola un caso que se decidio", () => {
    // La cola es de casos esperando decision: dejarlo con su fila vieja diria que
    // sigue esperando, que es lo contrario de lo que paso.
    const cola = withPage([fila("a"), fila("b")], null);

    const despues = reduceQueue(cola, aviso("case_decided", "a"));

    expect(despues.items.map((f) => f.case_id)).toEqual(["b"]);
    expect(despues.staleCaseIds).toEqual([]);
  });

  it("marca atrasado el caso que cambio, sin dibujar media fila", () => {
    // El aviso no trae la fila nueva. Dibujarla con lo que el aviso trae seria media
    // fila, y media fila es peor que ninguna.
    const cola = withPage([fila("a")], null);

    const despues = reduceQueue(cola, aviso("case_updated", "a"));

    expect(despues.items).toEqual(cola.items);
    expect(despues.staleCaseIds).toEqual(["a"]);
  });

  it("marca atrasado un caso nuevo que esta pagina no tiene", () => {
    const despues = reduceQueue(EMPTY_QUEUE, aviso("case_created", "z"));

    expect(despues.items).toEqual([]);
    expect(despues.staleCaseIds).toEqual(["z"]);
  });

  it("no repite el mismo caso en la lista de atrasados", () => {
    // Varios avisos seguidos del mismo caso son lo normal mientras alguien lo
    // trabaja: contarlos todos diria que hay mas casos atrasados que casos.
    const cola = reduceQueue(withPage([fila("a")], null), aviso("case_updated", "a"));

    const despues = reduceQueue(cola, aviso("case_updated", "a"));

    expect(despues.staleCaseIds).toEqual(["a"]);
  });

  it("una decision de un caso que esta pagina no tiene solo lo marca", () => {
    // Sin la comprobacion de que la pagina lo tiene, este caso saldria de una lista
    // en la que no estaba y el aviso se perderia sin dejar rastro.
    const despues = reduceQueue(withPage([fila("a")], null), aviso("case_decided", "z"));

    expect(despues.items.map((f) => f.case_id)).toEqual(["a"]);
    expect(despues.staleCaseIds).toEqual(["z"]);
  });

  it("la pagina siguiente se anade al final, sin reordenar nada", () => {
    // El orden lo decide el servidor (BR1.1). Una pantalla que ordenara por su cuenta
    // seria una segunda regla de orden escrita en otro sitio.
    const primera = withPage([fila("a"), fila("b")], "cursor-1");

    const juntas = withMore(primera, withPage([fila("c")], null));

    expect(juntas.items.map((f) => f.case_id)).toEqual(["a", "b", "c"]);
    expect(juntas.nextCursor).toBeNull();
  });

  it("una pagina nueva borra lo que los avisos habian marcado", () => {
    const atrasada = reduceQueue(withPage([fila("a")], null), aviso("case_updated", "a"));

    const fresca = withPage(atrasada.items, null);

    expect(fresca.staleCaseIds).toEqual([]);
  });

  it("dice si un aviso habla del caso abierto", () => {
    expect(touchesCase(aviso("case_updated", "a"), "a")).toBe(true);
    expect(touchesCase(aviso("case_updated", "a"), "b")).toBe(false);
  });
});

describe("leer un aviso del cable", () => {
  it("lee los tres tipos de C-06", () => {
    for (const tipo of ["case_created", "case_updated", "case_decided"] as const) {
      const leido = parseEvent(JSON.stringify(aviso(tipo, "a")));
      expect(leido?.kind).toBe(tipo);
    }
  });

  it("descarta un aviso con un tipo que el contrato no declara", () => {
    // El conjunto es cerrado: un cuarto tipo es un cambio de contrato, y aplicarlo a
    // ciegas seria inventarle conducta.
    vi.spyOn(console, "warn").mockImplementation(() => undefined);

    expect(
      parseEvent(JSON.stringify({ ...aviso("case_updated", "a"), kind: "case_burned" })),
    ).toBeNull();
  });

  it("descarta lo que no tiene la forma de C-06, y no lanza", () => {
    // Un aviso mal formado no puede tumbar la pantalla de quien esta decidiendo.
    vi.spyOn(console, "warn").mockImplementation(() => undefined);

    expect(parseEvent("no es json")).toBeNull();
    expect(parseEvent("null")).toBeNull();
    expect(parseEvent(JSON.stringify({ kind: "case_updated" }))).toBeNull();
  });
});
