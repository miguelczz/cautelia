import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithProviders } from "../../app/testing";
import type { CaseDetailOut } from "../../shared/api-client/inbox";
import { createTranslate } from "../../shared/i18n/translate";
import { isSafeExternalLink, ResponseBlock } from "./evidence-blocks";

// El enlace para ver en Langfuse como trabajo la agente (2026-10-14). El servidor lo manda solo
// por las dos puertas con dueno; aqui se comprueba como se pinta, y que una direccion que no sea
// https nunca llegue a un `href`.

const ENLACE =
  "https://us.cloud.langfuse.com/project/proyecto-local/traces/48215069371502846913720465183927";

function caso(extra: Partial<CaseDetailOut> = {}): CaseDetailOut {
  return {
    case_id: "case-1",
    case_number: "CAS-000001",
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

describe("el enlace a la traza en 'Como se respondio'", () => {
  it("con direccion del servidor, el enlace abre en otra pestana sin pasar el origen y la nota lo explica", () => {
    const t = createTranslate("es");
    renderWithProviders(<ResponseBlock detail={caso({ trace_url: ENLACE })} />, "es");

    const bloque = screen.getByTestId("block-trace");
    const enlace = within(bloque).getByRole("link", {
      name: t("inbox.trace.langfuse_link"),
    });
    expect(enlace.getAttribute("href")).toBe(ENLACE);
    expect(enlace.getAttribute("target")).toBe("_blank");
    expect(enlace.getAttribute("rel")).toBe("noopener noreferrer");
    // La nota va atada al enlace para quien lo oye con un lector de pantalla.
    const nota = within(bloque).getByText(t("inbox.trace.langfuse_note"));
    expect(enlace.getAttribute("aria-describedby")).toBe(nota.id);
    expect(nota.textContent).toContain("Langfuse");
    expect(nota.textContent).toContain("No muestra lo que se escribió en la conversación");
  });

  it("los dos idiomas tienen el enlace y la nota", () => {
    const t = createTranslate("en");
    renderWithProviders(<ResponseBlock detail={caso({ trace_url: ENLACE })} />, "en");

    expect(screen.getByRole("link", { name: "See in Langfuse how the agent worked" })).toBeTruthy();
    expect(screen.getByText(t("inbox.trace.langfuse_note"))).toBeTruthy();
  });

  it("sin direccion no hay enlace ni nota, y el tiempo y el costo siguen", () => {
    renderWithProviders(<ResponseBlock detail={caso()} />, "es");
    renderWithProviders(<ResponseBlock detail={caso({ trace_url: null })} />, "es");

    expect(screen.queryByTestId("trace-langfuse")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getAllByTestId("trace-latency").length).toBe(2);
  });

  it("con la direccion y sin tiempo ni costo medidos, el bloque se pinta por el enlace", () => {
    renderWithProviders(
      <ResponseBlock
        detail={caso({ trace_cost_usd: null, trace_latency_ms: null, trace_url: ENLACE })}
      />,
      "es",
    );

    const bloque = screen.getByTestId("block-trace");
    expect(within(bloque).queryByTestId("trace-latency")).toBeNull();
    expect(within(bloque).queryByTestId("trace-cost")).toBeNull();
    expect(within(bloque).getByTestId("trace-langfuse-link")).toBeTruthy();
  });

  it("sin nada que decir, el bloque entero no se pinta", () => {
    renderWithProviders(
      <ResponseBlock detail={caso({ trace_cost_usd: null, trace_latency_ms: null })} />,
      "es",
    );

    expect(screen.queryByTestId("block-trace")).toBeNull();
  });

  it.each([
    "http://us.cloud.langfuse.com/project/x/traces/1",
    "javascript:alert(1)",
    "//us.cloud.langfuse.com/project/x/traces/1",
    "https://",
    "https://con espacio/x",
    "",
  ])("una direccion que no es https no llega a un href: %s", (direccion) => {
    renderWithProviders(<ResponseBlock detail={caso({ trace_url: direccion })} />, "es");

    expect(screen.queryByRole("link")).toBeNull();
  });

  it("solo una direccion https es segura", () => {
    expect(isSafeExternalLink(ENLACE)).toBe(true);
    expect(isSafeExternalLink(null)).toBe(false);
    expect(isSafeExternalLink(undefined)).toBe(false);
    expect(isSafeExternalLink("http://x.test/")).toBe(false);
  });
});
