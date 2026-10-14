import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../app/testing";
import type { CaseDetailOut, InboxResult, TriageNoteIn } from "../../shared/api-client/inbox";
import type { ProblemView } from "../../shared/api-client/problems";
import { createTranslate } from "../../shared/i18n/translate";
import { formatPesos } from "../policies/policies-page";
import { CaseDetailPage } from "./case-page";

// Lo que el ajustador anota para las reglas, dentro de la vista del caso: los tres
// controles, el estado «sin anotar» que se puede volver a dejar, el monto leido en pesos y
// lo que pasa al guardar. Sin jerga del sistema y sin que la pantalla decida cuando se
// ofrece: eso llega resuelto del servidor.

const pedido = vi.hoisted(() =>
  vi.fn<(tenantId: string, caseId: string) => Promise<InboxResult<CaseDetailOut>>>(),
);
const anotado = vi.hoisted(() =>
  vi.fn<
    (
      tenantId: string,
      caseId: string,
      note: TriageNoteIn,
      key: string,
    ) => Promise<InboxResult<{ receipt_id: string }>>
  >(),
);

vi.mock("../../shared/api-client/inbox", async (original) => {
  const real = await original<typeof import("../../shared/api-client/inbox")>();
  return { ...real, caseDetail: pedido, annotateTriage: anotado };
});

const t = createTranslate("es");

function caso(extra: Partial<CaseDetailOut> = {}): CaseDetailOut {
  return {
    case_id: "case-1",
    case_number: "CAS-000001",
    state: "derived",
    record_type: "claim",
    channel: "chat",
    language: "es",
    priority: "high",
    derivation_reason: "rule",
    completeness_complete: 3,
    completeness_total: 7,
    fields: [],
    transcript: [],
    coverage_answers: [],
    rule_category: "standard_review",
    fired_rules: ["R-POR-DEFECTO"],
    controls_ok: null,
    control_findings: [],
    trace_status: null,
    trace_cost_usd: null,
    trace_cost_status: null,
    trace_latency_ms: null,
    updated_at: "2026-09-28T12:01:00+00:00",
    resolution: null,
    available_actions: ["approve", "reject"],
    can_correct_fields: true,
    explanation: {
      asked: "none",
      cited: "none",
      rule: "present",
      decided_by: "pending",
      decided_at: "pending",
      decided_by_kind: null,
      decided_by_id: null,
      decided_at_iso: null,
    },
    triage_note: null,
    can_annotate_triage: true,
    ...extra,
  };
}

function dibujar(locale: "es" | "en" = "es") {
  renderWithProviders(
    <CaseDetailPage
      tenantId="una-aseguradora"
      caseId="case-1"
      queueHref="/t/una-aseguradora/inbox"
      openStream={() => ({ close: () => undefined }) as unknown as EventSource}
    />,
    locale,
  );
}

async function bloque() {
  return within(await screen.findByTestId("block-triage"));
}

beforeEach(() => {
  pedido.mockReset();
  anotado.mockReset();
  pedido.mockResolvedValue({ ok: true, value: caso() });
  anotado.mockResolvedValue({ ok: true, value: { receipt_id: "rec-1" } });
});

describe("cuando se ofrece anotar", () => {
  it("dibuja los tres controles con «sin anotar» donde nadie ha anotado nada", async () => {
    dibujar();

    const dentro = await bloque();
    const monto = dentro.getByLabelText<HTMLInputElement>(t("inbox.triage.amount_label"));
    const cobertura = dentro.getByLabelText<HTMLSelectElement>(t("inbox.triage.coverage_label"));
    const fraude = dentro.getByLabelText<HTMLSelectElement>(t("inbox.triage.fraud_label"));

    expect(monto.value).toBe("");
    expect(cobertura.value).toBe("unset");
    expect(fraude.value).toBe("unset");
    // Las tres respuestas de cada selector, con su texto del catalogo y nunca el valor.
    expect(
      within(cobertura)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual([t("inbox.triage.unset"), t("inbox.triage.answer_yes"), t("inbox.triage.answer_no")]);
    expect(dentro.getByRole("button", { name: t("inbox.triage.save") })).toBeTruthy();
  });

  it("arranca con lo ya anotado, y un «no» no se confunde con «sin anotar»", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        triage_note: { claim_amount: 2500, coverage_disputed: false, fraud_suspected: null },
      }),
    });
    dibujar();

    const dentro = await bloque();

    expect(dentro.getByLabelText<HTMLInputElement>(t("inbox.triage.amount_label")).value).toBe(
      "2500",
    );
    expect(dentro.getByLabelText<HTMLSelectElement>(t("inbox.triage.coverage_label")).value).toBe(
      "no",
    );
    expect(dentro.getByLabelText<HTMLSelectElement>(t("inbox.triage.fraud_label")).value).toBe(
      "unset",
    );
  });

  it("lee el monto en pesos con el mismo formateador de las polizas", async () => {
    const usuario = userEvent.setup();
    dibujar();
    const dentro = await bloque();

    await usuario.type(dentro.getByLabelText(t("inbox.triage.amount_label")), "1500");

    const lectura = await dentro.findByTestId("triage-amount-preview");
    expect(lectura.textContent).toBe(
      t("inbox.triage.amount_preview", { amount: formatPesos(1500, "es") }),
    );
    // Independiente del formateador: 1.500 miles de pesos son 1.500.000 pesos.
    expect(lectura.textContent.replace(/\D/g, "")).toBe("1500000");
  });

  it("manda lo anotado, con una clave de intento, y vuelve a leer el caso", async () => {
    const usuario = userEvent.setup();
    dibujar();
    const dentro = await bloque();

    await usuario.type(dentro.getByLabelText(t("inbox.triage.amount_label")), "1500");
    await usuario.selectOptions(dentro.getByLabelText(t("inbox.triage.coverage_label")), "yes");
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        rule_category: "referral",
        fired_rules: ["R-DE-MONTO", "R-DE-COBERTURA"],
        triage_note: { claim_amount: 1500, coverage_disputed: true, fraud_suspected: null },
      }),
    });
    await usuario.click(dentro.getByRole("button", { name: t("inbox.triage.save") }));

    await waitFor(() => {
      expect(anotado).toHaveBeenCalledTimes(1);
    });
    const [aseguradora, idDelCaso, nota, clave] = anotado.mock.calls[0] ?? [];
    expect(aseguradora).toBe("una-aseguradora");
    expect(idDelCaso).toBe("case-1");
    expect(nota).toEqual({
      claim_amount: 1500,
      coverage_disputed: true,
      fraud_suspected: null,
    });
    expect(clave).toMatch(/^note-/);
    // El bloque de las reglas se actualiza con la evaluacion nueva.
    const reglas = await screen.findByTestId("block-rule");
    await waitFor(() => {
      expect(within(reglas).getByTestId("rule-reference").textContent).toContain("R-DE-MONTO");
    });
    expect(pedido.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(await screen.findByTestId("triage-saved")).toBeTruthy();
  });

  it("puede volver a dejar cada dato sin anotar y manda null, no cero ni falso", async () => {
    const usuario = userEvent.setup();
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        triage_note: { claim_amount: 2500, coverage_disputed: true, fraud_suspected: false },
      }),
    });
    dibujar();
    const dentro = await bloque();

    await usuario.clear(dentro.getByLabelText(t("inbox.triage.amount_label")));
    await usuario.selectOptions(dentro.getByLabelText(t("inbox.triage.coverage_label")), "unset");
    await usuario.selectOptions(dentro.getByLabelText(t("inbox.triage.fraud_label")), "unset");
    await usuario.click(dentro.getByRole("button", { name: t("inbox.triage.save") }));

    await waitFor(() => {
      expect(anotado).toHaveBeenCalledTimes(1);
    });
    expect(anotado.mock.calls[0]?.[2]).toEqual({
      claim_amount: null,
      coverage_disputed: null,
      fraud_suspected: null,
    });
  });

  it("un monto cero se manda como cero: es una estimacion, no un dato sin anotar", async () => {
    const usuario = userEvent.setup();
    dibujar();
    const dentro = await bloque();

    await usuario.type(dentro.getByLabelText(t("inbox.triage.amount_label")), "0");
    await usuario.click(dentro.getByRole("button", { name: t("inbox.triage.save") }));

    await waitFor(() => {
      expect(anotado).toHaveBeenCalledTimes(1);
    });
    expect(anotado.mock.calls[0]?.[2]).toMatchObject({ claim_amount: 0 });
  });

  it.each([
    ["con coma", "12,5"],
    ["con puntos", "1.500"],
    ["con letras", "mil"],
    ["con signo", "-3"],
    // Un numero que JavaScript no puede representar se volveria `null` al serializarse, y
    // eso borraria lo anotado sin avisar: no se manda.
    ["desmedido", "9".repeat(40)],
  ])("un monto %s no se manda y se dice por que", async (_nombre, escrito) => {
    const usuario = userEvent.setup();
    dibujar();
    const dentro = await bloque();

    await usuario.type(dentro.getByLabelText(t("inbox.triage.amount_label")), escrito);
    await usuario.click(dentro.getByRole("button", { name: t("inbox.triage.save") }));

    expect((await dentro.findByRole("alert")).textContent).toBe(t("inbox.triage.amount_invalid"));
    expect(anotado).not.toHaveBeenCalled();
    expect(dentro.getByLabelText<HTMLInputElement>(t("inbox.triage.amount_label")).value).toBe(
      escrito,
    );
  });

  it("si el servidor rechaza, lo escrito se queda y se puede reintentar", async () => {
    const usuario = userEvent.setup();
    const rechazo: ProblemView = {
      code: "validation_failed",
      message: (tt) => tt("problem.validation_failed"),
    };
    anotado.mockResolvedValueOnce({ ok: false, problem: rechazo });
    dibujar();
    const dentro = await bloque();

    await usuario.type(dentro.getByLabelText(t("inbox.triage.amount_label")), "99999999");
    await usuario.selectOptions(dentro.getByLabelText(t("inbox.triage.fraud_label")), "yes");
    await usuario.click(dentro.getByRole("button", { name: t("inbox.triage.save") }));

    expect((await dentro.findByTestId("triage-problem")).textContent).toBe(
      t("problem.validation_failed"),
    );
    expect(dentro.getByLabelText<HTMLInputElement>(t("inbox.triage.amount_label")).value).toBe(
      "99999999",
    );
    expect(dentro.getByLabelText<HTMLSelectElement>(t("inbox.triage.fraud_label")).value).toBe(
      "yes",
    );
    expect(dentro.queryByTestId("triage-saved")).toBeNull();
    // Y el boton sigue vivo para reintentar.
    const boton = dentro.getByRole("button", { name: t("inbox.triage.save") });
    expect((boton as HTMLButtonElement).disabled).toBe(false);
    await usuario.click(boton);
    await waitFor(() => {
      expect(anotado).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(dentro.queryByTestId("triage-problem")).toBeNull();
    });
  });

  it("el aviso de «guardado» se apaga en cuanto se toca un control", async () => {
    const usuario = userEvent.setup();
    dibujar();
    const dentro = await bloque();
    await usuario.click(dentro.getByRole("button", { name: t("inbox.triage.save") }));
    expect(await dentro.findByTestId("triage-saved")).toBeTruthy();

    await usuario.selectOptions(dentro.getByLabelText(t("inbox.triage.fraud_label")), "no");

    expect(dentro.queryByTestId("triage-saved")).toBeNull();
  });

  it("no se oculta nada detras de jerga: el bloque dice «ajustador» y no el nombre de los datos", async () => {
    dibujar();

    const dentro = await bloque();

    expect(dentro.getByText(t("inbox.triage.intro"))).toBeTruthy();
    const texto = (await screen.findByTestId("block-triage")).textContent;
    for (const crudo of ["claim_amount", "coverage_disputed", "fraud_suspected", "triage"]) {
      expect(texto).not.toContain(crudo);
    }
  });

  it("dice lo mismo en ingles", async () => {
    const ingles = createTranslate("en");
    dibujar("en");

    const dentro = await bloque();

    expect(dentro.getByLabelText(ingles("inbox.triage.amount_label"))).toBeTruthy();
    expect(dentro.getByRole("button", { name: ingles("inbox.triage.save") })).toBeTruthy();
  });
});

describe("cuando no se ofrece anotar", () => {
  it("sin anotaciones el bloque no se dibuja", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ can_annotate_triage: false, triage_note: null }),
    });
    dibujar();

    await screen.findByTestId("inbox-case");

    expect(screen.queryByTestId("block-triage")).toBeNull();
  });

  it("un cable sin los campos nuevos tampoco lo dibuja", async () => {
    const sin = caso();
    delete sin.triage_note;
    delete sin.can_annotate_triage;
    pedido.mockResolvedValue({ ok: true, value: sin });
    dibujar();

    await screen.findByTestId("inbox-case");

    expect(screen.queryByTestId("block-triage")).toBeNull();
  });

  it("con anotaciones se leen, en pesos, sin ningun control", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        state: "closed",
        resolution: "approved",
        available_actions: [],
        can_annotate_triage: false,
        triage_note: { claim_amount: 2500, coverage_disputed: false, fraud_suspected: null },
      }),
    });
    dibujar();

    const dentro = await bloque();

    expect(dentro.getByTestId("triage-amount-value").textContent).toBe(formatPesos(2500, "es"));
    expect(dentro.getByTestId("triage-amount-value").textContent.replace(/\D/g, "")).toBe(
      "2500000",
    );
    expect(dentro.getByTestId("triage-coverage-value").textContent).toBe(
      t("inbox.triage.answer_no"),
    );
    expect(dentro.getByTestId("triage-fraud-value").textContent).toBe(t("inbox.triage.unset"));
    expect(dentro.getByText(t("inbox.triage.read_only"))).toBeTruthy();
    expect(dentro.queryByRole("textbox")).toBeNull();
    expect(dentro.queryByRole("combobox")).toBeNull();
    expect(dentro.queryByRole("button")).toBeNull();
  });
});
