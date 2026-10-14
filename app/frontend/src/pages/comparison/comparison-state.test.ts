import { describe, expect, it } from "vitest";

import {
  anyLoading,
  disclosureComplete,
  idleColumns,
  restoreColumns,
  settleColumn,
  startColumns,
  startQuestion,
  type ColumnOutcome,
  type ComparisonInsurer,
} from "./comparison-state";

const SUNMEADOW: ComparisonInsurer = {
  tenantId: "a",
  displayName: "A",
  kind: "carrier",
  examplePolicy: "POL-1",
  issuedBy: null,
  brand: null,
};
const STONECROFT: ComparisonInsurer = { ...SUNMEADOW, tenantId: "b", displayName: "B" };
const AGENCIA: ComparisonInsurer = {
  ...SUNMEADOW,
  tenantId: "c",
  displayName: "C",
  kind: "agency",
  issuedBy: "A",
};

const CITADA: ColumnOutcome = {
  kind: "answered",
  answer: { kind: "no_clause", language: "es" },
};

describe("el estado por columna (BR2.2)", () => {
  it("empieza sin pregunta y una pregunta pone las tres a cargar", () => {
    const inicial = idleColumns([SUNMEADOW, STONECROFT, AGENCIA]);
    expect(inicial.map((c) => c.state)).toEqual(["idle", "idle", "idle"]);
    expect(anyLoading(inicial)).toBe(false);

    const cargando = startQuestion(inicial);
    expect(cargando.map((c) => c.state)).toEqual(["loading", "loading", "loading"]);
    expect(anyLoading(cargando)).toBe(true);
  });

  it("cerrar una columna deja las otras dos como estaban", () => {
    const cargando = startQuestion(idleColumns([SUNMEADOW, STONECROFT, AGENCIA]));
    const despues = settleColumn(cargando, "b", CITADA);

    expect(despues.map((c) => c.state)).toEqual(["loading", "answered", "loading"]);
    expect(despues[0]).toBe(cargando[0]);
    expect(despues[2]).toBe(cargando[2]);
  });

  it("un fallo de una columna no toca a las que ya respondieron", () => {
    const cargando = startQuestion(idleColumns([SUNMEADOW, STONECROFT, AGENCIA]));
    const conUna = settleColumn(cargando, "a", CITADA);
    const conFallo = settleColumn(conUna, "b", { kind: "failed" });

    expect(conFallo.map((c) => c.state)).toEqual(["answered", "failed", "loading"]);
  });

  it("failed y rejected son estados distintos y el rechazo conserva su limite", () => {
    const cargando = startQuestion(idleColumns([SUNMEADOW, STONECROFT]));
    const cerradas = settleColumn(settleColumn(cargando, "a", { kind: "failed" }), "b", {
      kind: "rejected",
      limit: "rate",
      copyKey: "chat.limit.rate",
    });

    expect(cerradas[0]?.state).toBe("failed");
    expect(cerradas[1]).toEqual({
      tenantId: "b",
      state: "rejected",
      limit: "rate",
      copyKey: "chat.limit.rate",
    });
    // El fallo no arrastra un limite que no tuvo.
    expect(cerradas[0]).not.toHaveProperty("limit");
  });

  it("'no encuentro una clausula' es una respuesta y no un fallo", () => {
    const cerrada = settleColumn(startQuestion(idleColumns([SUNMEADOW])), "a", CITADA);
    expect(cerrada[0]?.state).toBe("answered");
  });
});

describe("volver a preguntar y restaurar lo guardado", () => {
  it("volver a preguntar a una columna no toca las demas", () => {
    const cerradas = settleColumn(
      settleColumn(startQuestion(idleColumns([SUNMEADOW, STONECROFT, AGENCIA])), "a", CITADA),
      "b",
      { kind: "failed" },
    );
    const otraVez = startColumns(cerradas, ["b"]);

    expect(otraVez.map((c) => c.state)).toEqual(["answered", "loading", "loading"]);
    expect(otraVez[0]).toBe(cerradas[0]);
  });

  it("una columna que cargaba y ya no tiene pregunta en vuelo queda interrumpida, no fallida", () => {
    const guardadas = settleColumn(
      startQuestion(idleColumns([SUNMEADOW, STONECROFT, AGENCIA])),
      "a",
      CITADA,
    );
    const restauradas = restoreColumns(guardadas, () => false);

    expect(restauradas.map((c) => c.state)).toEqual(["answered", "interrupted", "interrupted"]);
    expect(restauradas[0]).toBe(guardadas[0]);
    expect(anyLoading(restauradas)).toBe(false);
  });

  it("la que sigue en vuelo en esta pestana sigue cargando", () => {
    const guardadas = startQuestion(idleColumns([SUNMEADOW, STONECROFT]));
    const restauradas = restoreColumns(guardadas, (tenantId) => tenantId === "b");

    expect(restauradas.map((c) => c.state)).toEqual(["interrupted", "loading"]);
  });
});

describe("la divulgacion completa (BR1.1, BR1.2)", () => {
  it("una agencia sin emisor la deja incompleta", () => {
    expect(disclosureComplete([SUNMEADOW, { ...AGENCIA, issuedBy: null }])).toBe(false);
  });

  it("una agencia con emisor y emisoras sin emisor la completan", () => {
    expect(disclosureComplete([SUNMEADOW, STONECROFT, AGENCIA])).toBe(true);
  });

  it("sin aseguradoras no hay nada que divulgar", () => {
    expect(disclosureComplete([])).toBe(false);
  });
});
