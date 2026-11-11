import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithProviders } from "../../app/testing";
import type { CaseDetailOut } from "../../shared/api-client/inbox";
import { ResponseBlock } from "./evidence-blocks";

// "Como se respondio": solo el tiempo y el costo medidos. El enlace a Langfuse se quito el
// 2026-11-11 (la traza publica no mostraba nada legible): aunque el servidor mande una direccion,
// la pantalla no pinta ningun enlace.

const ENLACE =
  "https://us.cloud.langfuse.com/project/proyecto-local/traces/48215069371502846913720465183927";

function caso(extra: Partial<CaseDetailOut> = {}): CaseDetailOut {
  return {
    case_id: "case-1",
    case_number: "CA-1",
    state: "derived",
    record_type: "claim",
    channel: "chat",
    language: "es",
    priority: "normal",
    derivation_reason: "rule",
    completeness_complete: 5,
    completeness_total: 7,
    fields: [],
    transcript: [],
    coverage_answers: [],
    rule_category: null,
    fired_rules: [],
    controls_ok: null,
    control_findings: [],
    trace_status: "ready",
    trace_cost_usd: "0.0031",
    trace_cost_status: "measured",
    trace_latency_ms: 1800,
    updated_at: "2026-10-14T12:01:00+00:00",
    resolution: null,
    available_actions: [],
    can_correct_fields: false,
    explanation: {
      asked: "none",
      cited: "none",
      rule: "none",
      decided_by: "pending",
      decided_at: "pending",
      decided_by_kind: null,
      decided_by_id: null,
      decided_at_iso: null,
    },
    ...extra,
  };
}

describe("'Como se respondio'", () => {
  it("pinta el tiempo y el costo, y ningun enlace aunque el servidor mande una direccion", () => {
    renderWithProviders(<ResponseBlock detail={caso({ trace_url: ENLACE })} />, "es");

    const bloque = screen.getByTestId("block-trace");
    expect(within(bloque).getByTestId("trace-latency")).toBeTruthy();
    expect(within(bloque).getByTestId("trace-cost")).toBeTruthy();
    expect(screen.queryByRole("link")).toBeNull();
    expect(bloque.textContent).not.toContain("Langfuse");
  });

  it("sin tiempo ni costo medidos, el bloque no se pinta ni con direccion", () => {
    renderWithProviders(
      <ResponseBlock
        detail={caso({ trace_cost_usd: null, trace_latency_ms: null, trace_url: ENLACE })}
      />,
      "es",
    );

    expect(screen.queryByTestId("block-trace")).toBeNull();
  });
});
