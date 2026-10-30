import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../app/testing";
import type { CaseDetailOut, InboxResult } from "../../shared/api-client/inbox";
import type { Locale } from "../../shared/copy/copy-keys";
import { createTranslate } from "../../shared/i18n/translate";
import { CaseDetailPage } from "./case-page";
import type { WireInboxEvent } from "./inbox-events";

// La vista de caso: su encabezado pegajoso, sus seis bloques, su correccion y su
// decision (BR2.1 a BR2.6, BR3.3, BR3.4, BR4.1, BR4.3, BR4.5).

const pedido = vi.hoisted(() =>
  vi.fn<(tenantId: string, caseId: string) => Promise<InboxResult<CaseDetailOut>>>(),
);
const decidido = vi.hoisted(() =>
  vi.fn<
    (
      tenantId: string,
      caseId: string,
      decision: string,
      comment: string,
      key: string,
    ) => Promise<InboxResult<{ decision_id: string; resolution: string }>>
  >(),
);
const corregido = vi.hoisted(() =>
  vi.fn<
    (
      tenantId: string,
      caseId: string,
      fieldKey: string,
      value: string,
      key: string,
    ) => Promise<InboxResult<{ receipt_id: string }>>
  >(),
);

vi.mock("../../shared/api-client/inbox", async (original) => {
  const real = await original<typeof import("../../shared/api-client/inbox")>();
  return { ...real, caseDetail: pedido, decideCase: decidido, correctField: corregido };
});

const t = createTranslate("es");

function caso(extra: Partial<CaseDetailOut> = {}): CaseDetailOut {
  return {
    case_id: "case-1",
    case_number: "CA-1",
    state: "derived",
    record_type: "claim",
    channel: "chat",
    language: "es",
    priority: "high",
    derivation_reason: "rule",
    completeness_complete: 3,
    completeness_total: 7,
    fields: [
      {
        field_key: "injuries",
        status: "not_stated",
        complete: false,
        label_key: "case.field.injuries",
      },
    ],
    transcript: [
      {
        turn_id: "t1",
        speaker: "insured",
        text_redacted: "Choque mi carro, placa [PLACA 1].",
        started_at: "2026-09-28T12:00:00+00:00",
      },
    ],
    coverage_answers: [],
    rule_category: "referral",
    fired_rules: ["injuries-present"],
    controls_ok: true,
    control_findings: [],
    trace_status: "ready",
    trace_cost_usd: "0.0031",
    trace_cost_status: "measured",
    trace_latency_ms: 1800,
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
    ...extra,
  };
}

function flujoDeMentira() {
  const flujo = {
    onopen: null,
    onmessage: null as ((evento: MessageEvent<string>) => void) | null,
    onerror: null,
    cerrado: false,
    close() {
      this.cerrado = true;
    },
  };
  return {
    flujo,
    abrir: () => flujo as unknown as EventSource,
    empujar(evento: WireInboxEvent) {
      act(() => {
        flujo.onmessage?.(new MessageEvent("message", { data: JSON.stringify(evento) }));
      });
    },
  };
}

function dibujar(cable = flujoDeMentira(), locale: Locale = "es") {
  renderWithProviders(
    <CaseDetailPage
      tenantId="una-aseguradora"
      caseId="case-1"
      queueHref="/t/una-aseguradora/inbox"
      openStream={cable.abrir}
    />,
    locale,
  );
  return cable;
}

beforeEach(() => {
  pedido.mockReset();
  decidido.mockReset();
  corregido.mockReset();
  pedido.mockResolvedValue({ ok: true, value: caso() });
});

describe("el encabezado del caso", () => {
  it("lleva juntos el motivo, la categoria, la completitud y las acciones (BR2.1)", async () => {
    const encabezado = await dibujarYEsperarEncabezado();

    expect(encabezado.textContent).toContain(t("case.derivation_reason.rule"));
    expect(encabezado.textContent).toContain(t("case.record_type.claim"));
    expect(encabezado.textContent).toContain(t("inbox.completeness", { complete: 3, total: 7 }));
    // Las acciones **dentro** del encabezado: es lo que la regla nombra en la misma
    // frase que el motivo, y una barra de accion abajo deja ver el boton sin ver el
    // motivo.
    expect(within(encabezado).getByTestId("decision-form")).toBeTruthy();
  });

  it.each([
    ["referral", () => t("inbox.rule.category.referral")],
    ["standard_review", () => t("inbox.rule.category.standard_review")],
    ["direct_close", () => t("inbox.rule.category.direct_close")],
    ["categoria_nueva", () => t("inbox.rule.category.other")],
  ] as const)(
    "la categoria %s sale con su etiqueta del catalogo y nunca el valor en crudo",
    async (categoria, etiqueta) => {
      pedido.mockResolvedValue({ ok: true, value: caso({ rule_category: categoria }) });
      const encabezado = await dibujarYEsperarEncabezado();

      expect(encabezado.textContent).toContain(etiqueta());
      expect(encabezado.textContent).not.toContain(categoria);
    },
  );

  it("se queda arriba al desplazar", async () => {
    const encabezado = await dibujarYEsperarEncabezado();

    // En el telefono es lo unico que garantiza que las acciones esten al alcance sin
    // recorrer seis bloques.
    expect(encabezado.className).toContain("sticky");
    expect(encabezado.className).toContain("top-0");
  });

  it("dice quien decidio y cuando, y en un caso sin decidir dice pendiente (BR2.4)", async () => {
    dibujar();

    // **Las dos por separado.** La version anterior de esta prueba miraba el texto de
    // las dos juntas, y entonces no podia distinguir cual de las dos hablo: vaciar
    // "pendiente de decision" de una de ellas la pasaba igual. Un campo vacio se lee
    // como un dato que se perdio, y eso es lo que la regla prohibe **en cada una**.
    const quien = await screen.findByTestId("case-decided-by");
    const cuando = screen.getByTestId("case-decided-at");

    expect(quien.textContent).toBe(t("inbox.explanation.pending"));
    expect(cuando.textContent).toBe(t("inbox.explanation.pending"));
  });

  it("una decision tomada con el enlace se atribuye a un visitante (BR5.5)", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        state: "closed",
        resolution: "approved",
        available_actions: [],
        can_correct_fields: false,
        explanation: {
          asked: "none",
          cited: "none",
          rule: "present",
          decided_by: "present",
          decided_at: "present",
          decided_by_kind: "insured",
          decided_by_id: null,
          decided_at_iso: "2026-09-28T12:30:00+00:00",
        },
      }),
    });
    dibujar();

    const quien = await screen.findByTestId("case-decided-by");
    expect(quien.textContent).toBe(t("inbox.explanation.by_visitor"));
    // Y **cuando**: sin esta mitad, una explicacion que dijera la hora y no el autor
    // pasaria igual.
    expect(screen.getByTestId("case-decided-at").textContent).not.toBe("");
    expect(screen.getByTestId("case-resolution").textContent).toBe(t("case.resolution.approved"));
  });

  it("una decision con credencial nombra a quien la firmo", async () => {
    // La otra mitad: sin ella, una pantalla que dijera siempre "un visitante" pasaria
    // la prueba de arriba.
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        state: "closed",
        resolution: "approved",
        available_actions: [],
        explanation: {
          asked: "none",
          cited: "none",
          rule: "present",
          decided_by: "present",
          decided_at: "present",
          decided_by_kind: "staff",
          decided_by_id: "diana-ruiz",
          decided_at_iso: "2026-09-28T12:30:00+00:00",
        },
      }),
    });
    dibujar();

    const quien = await screen.findByTestId("case-decided-by");
    expect(quien.textContent).toBe(t("inbox.explanation.by_staff", { who: "diana-ruiz" }));
  });
});

describe("los seis bloques de evidencia", () => {
  it("los seis bloques van abiertos: ninguno esconde su contenido detras de un clic", async () => {
    // Los tres ultimos iban plegados y mostraban codigos; ahora dicen una frase y, sin
    // plegar, el titulo y lo de abajo quedan en la misma vertical (E3, 2026-10-12).
    dibujar();
    await screen.findByTestId("case-header");

    for (const bloque of [
      "block-fields",
      "block-transcript",
      "block-citations",
      "block-rule",
      "block-controls",
      "block-trace",
    ]) {
      // Un boton que pliega tiene `aria-expanded`: ninguno de los seis lo tiene.
      expect(
        within(screen.getByTestId(bloque)).queryByRole("button", { expanded: false }),
      ).toBeNull();
      expect(
        within(screen.getByTestId(bloque)).queryByRole("button", { expanded: true }),
      ).toBeNull();
    }
  });

  it("la regla dice por que paso a un ajustador en una frase, con su identificador como referencia", async () => {
    dibujar();
    await screen.findByTestId("case-header");

    const bloque = screen.getByTestId("block-rule");
    expect(within(bloque).getByRole("heading").textContent).toBe(t("inbox.block.rule"));
    expect(bloque.textContent).toContain(t("inbox.rule.reason.referral"));
    expect(within(bloque).getByTestId("rule-reference").textContent).toBe(
      t("inbox.rule.reference", { rules: "injuries-present" }),
    );
    // La categoria cruda no es texto para una persona.
    expect(bloque.textContent).not.toContain("referral");
  });

  it("los controles dicen que se reviso y que se encontro, y un codigo desconocido no se pinta", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        controls_ok: false,
        control_findings: ["human_route_missed", "un_codigo_nuevo"],
      }),
    });
    dibujar();
    await screen.findByTestId("case-header");

    const bloque = screen.getByTestId("block-controls");
    expect(bloque.textContent).toContain(t("inbox.controls.reviewed"));
    const hallazgos = within(within(bloque).getByTestId("control-findings"))
      .getAllByRole("listitem")
      .map((fila) => fila.textContent);
    expect(hallazgos).toEqual([
      t("inbox.controls.finding.human_route_missed"),
      t("inbox.controls.finding.other"),
    ]);
    expect(bloque.textContent).not.toContain("human_route_missed");
    expect(bloque.textContent).not.toContain("un_codigo_nuevo");
  });

  it("sin hallazgos lo dice con palabras", async () => {
    dibujar();
    await screen.findByTestId("case-header");

    const bloque = screen.getByTestId("block-controls");
    expect(bloque.textContent).toContain(t("inbox.controls.all_clear"));
    expect(within(bloque).queryByTestId("control-findings")).toBeNull();
  });

  it("la respuesta dice su tiempo y su costo con rotulos, sin el bloque de siempre en un solo renglon", async () => {
    dibujar();
    await screen.findByTestId("case-header");

    const bloque = screen.getByTestId("block-trace");
    expect(within(bloque).getByTestId("trace-latency").textContent).toBe(
      t("trace.page.milliseconds", { value: 1800 }),
    );
    expect(within(bloque).getByTestId("trace-cost").textContent).toContain("0.0031");
  });

  it("los controles que no han corrido no se pintan: no se dice 'sin hallazgos' de lo que nadie reviso", async () => {
    // Tres resultados y no dos: colapsarlos diria que se comprobo algo que nadie comprobo.
    pedido.mockResolvedValue({ ok: true, value: caso({ controls_ok: null }) });
    dibujar();
    await screen.findByTestId("case-header");

    expect(screen.queryByTestId("block-controls")).toBeNull();
    expect(document.body.textContent).not.toContain(t("inbox.controls.all_clear"));
  });

  it("un costo o un tiempo no medido no se pinta, y sin ninguno el bloque entero tampoco", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ trace_cost_usd: null, trace_latency_ms: 900 }),
    });
    dibujar();
    await screen.findByTestId("case-header");

    const bloque = screen.getByTestId("block-trace");
    expect(within(bloque).getByTestId("trace-latency")).toBeTruthy();
    expect(within(bloque).queryByTestId("trace-cost")).toBeNull();
    expect(bloque.textContent).not.toContain(t("trace.page.not_measured"));
  });

  it("la pantalla del personal ensena el enlace a Langfuse solo cuando el servidor manda la direccion", async () => {
    const direccion = "https://us.cloud.langfuse.com/project/p1/traces/123";
    pedido.mockResolvedValue({ ok: true, value: caso({ trace_url: direccion }) });
    dibujar();
    await screen.findByTestId("case-header");

    const enlace = within(screen.getByTestId("block-trace")).getByTestId("trace-langfuse-link");
    expect(enlace.getAttribute("href")).toBe(direccion);
    expect(enlace.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("sin direccion del servidor la pantalla del personal no ensena enlace a Langfuse", async () => {
    pedido.mockResolvedValue({ ok: true, value: caso() });
    dibujar();
    await screen.findByTestId("case-header");

    expect(screen.queryByTestId("trace-langfuse-link")).toBeNull();
  });

  it("sin tiempo ni costo medidos no hay bloque 'Como se respondio'", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ trace_cost_usd: null, trace_latency_ms: null }),
    });
    dibujar();
    await screen.findByTestId("case-header");

    expect(screen.queryByTestId("block-trace")).toBeNull();
    expect(document.body.textContent).not.toContain(t("trace.page.not_measured"));
  });

  it("sin categoria de reglas no hay bloque de la regla", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ rule_category: null, fired_rules: [] }),
    });
    dibujar();
    await screen.findByTestId("case-header");

    expect(screen.queryByTestId("block-rule")).toBeNull();
  });

  it("a quien abrio su propio caso le muestra lo que quedo anotado en cada dato", async () => {
    // Decision de Miguel del 2026-10-11: decia "Completo" y no se veia que se anoto.
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        fields: [
          {
            field_key: "injuries",
            status: "confirmed",
            complete: true,
            optional: false,
            value: "nadie salió herido",
            label_key: "case.field.injuries",
          },
          {
            field_key: "other_parties",
            status: "not_stated",
            complete: false,
            optional: true,
            value: null,
            label_key: "case.field.other_parties",
          },
          {
            field_key: "location",
            status: "not_stated",
            complete: false,
            optional: false,
            value: null,
            label_key: "case.field.location",
          },
        ],
      }),
    });
    dibujar();
    const filas = within(await screen.findByTestId("case-fields")).getAllByRole("listitem");
    const fila = (indice: number): HTMLElement => {
      const encontrada = filas.at(indice);
      if (encontrada === undefined) {
        throw new Error(`falta la fila ${String(indice)}`);
      }
      return encontrada;
    };
    const [heridos, otros, lugar] = [fila(0), fila(1), fila(2)];

    expect(within(heridos).getByTestId("field-value").textContent).toBe("nadie salió herido");
    expect(heridos.textContent).toContain(t("inbox.fields.complete"));
    // Lo que no cuenta para la completitud se dice opcional, no que falta.
    expect(otros.textContent).toContain(t("inbox.fields.optional"));
    expect(lugar.textContent).toContain(t("inbox.fields.incomplete"));
    expect(within(lugar).queryByTestId("field-value")).toBeNull();
  });

  it("la transcripcion muestra las etiquetas de redaccion y dice donde esta el valor (BR2.3)", async () => {
    dibujar();
    const bloque = await screen.findByTestId("block-transcript");

    expect(bloque.textContent).toContain("[PLACA 1]");
    expect(bloque.textContent).toContain(t("inbox.transcript.redacted_hint"));
  });

  it("la bandeja del ajustador sigue tapada aunque este navegador recuerde lo que se escribio (C5)", async () => {
    // El texto propio es de quien escribio la conversacion. Quien entra con credencial de
    // personal puede estar en el mismo navegador, y para el la base se lee como se guardo.
    window.localStorage.setItem(
      "cautelia.own-text.una-aseguradora",
      JSON.stringify(["Choque mi carro, placa ABC123."]),
    );
    dibujar();
    const bloque = await screen.findByTestId("block-transcript");

    expect(bloque.textContent).toContain("Choque mi carro, placa [PLACA 1].");
    expect(bloque.textContent).not.toContain("ABC123");
  });

  it("'sin clausula' y 'no pude verificar' llevan etiquetas distintas (BR2.5)", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        coverage_answers: [
          {
            answer_id: "sin",
            outcome: "no_clause_found",
            question_redacted: "Cubre el vidrio?",
            citations: [],
          },
          {
            answer_id: "nopude",
            outcome: "unverifiable",
            question_redacted: "Cubre el granizo?",
            citations: [],
          },
        ],
      }),
    });
    dibujar();
    await screen.findByTestId("block-citations");

    const sin = screen.getByTestId("coverage-outcome-sin").textContent;
    const nopude = screen.getByTestId("coverage-outcome-nopude").textContent;
    expect(sin).toBe(t("inbox.coverage.no_clause_found"));
    expect(nopude).toBe(t("inbox.coverage.unverifiable"));
    expect(sin).not.toBe(nopude);
  });

  it("cada clausula citada dice quien la emitio (BR2.6)", async () => {
    // En una agencia, quien coloco la poliza no es quien la expidio: sin este dato las
    // clausulas parecen de la agencia.
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        coverage_answers: [
          {
            answer_id: "a1",
            outcome: "verified",
            question_redacted: "Cubre el vidrio?",
            citations: [
              {
                clause_id: "PAP-2026-SUN-001-4.1",
                clause_version: "2026.1",
                part: "Part D",
                text: "La compania responde por los danos al vehiculo.",
                clause_language: "es",
                amount_deferred: false,
                issuer_label: "Quien Emitio S.A.",
              },
            ],
          },
        ],
      }),
    });
    dibujar();
    const bloque = await screen.findByTestId("block-citations");

    expect(bloque.textContent).toContain(
      t("inbox.coverage.issuer", { insurer: "Quien Emitio S.A." }),
    );
  });
});

describe("el nombre de la parte de cada clausula (C17, 2026-10-13)", () => {
  const EN_INGLES = "Part D — Coverage for Damage to Your Auto";
  const EN_ESPANOL = "Parte D — Daños a su vehículo";

  function conUnaClausula(
    idioma: "es" | "en",
    parte: string,
    enElOtro: string | null,
  ): CaseDetailOut {
    return caso({
      coverage_answers: [
        {
          answer_id: "a1",
          outcome: "verified",
          question_redacted: "Cubre el vidrio?",
          citations: [
            {
              clause_id: "PAP-2026-SUN-001-4.1",
              clause_version: "2026.1",
              part: parte,
              text: "El texto de la clausula, en su idioma.",
              clause_language: idioma,
              amount_deferred: false,
              issuer_label: "Quien Emitio S.A.",
              part_in_other_language: enElOtro,
            },
          ],
        },
      ],
    });
  }

  it("una poliza en ingles se rotula en espanol en una pantalla en espanol", async () => {
    pedido.mockResolvedValue({ ok: true, value: conUnaClausula("en", EN_INGLES, EN_ESPANOL) });
    dibujar(flujoDeMentira(), "es");

    const bloque = await screen.findByTestId("block-citations");

    expect(bloque.textContent).toContain(EN_ESPANOL);
    expect(bloque.textContent).not.toContain(EN_INGLES);
  });

  it("y en ingles en una pantalla en ingles: el rotulo sigue a la pantalla, no a la poliza", async () => {
    pedido.mockResolvedValue({ ok: true, value: conUnaClausula("en", EN_INGLES, EN_ESPANOL) });
    dibujar(flujoDeMentira(), "en");

    const bloque = await screen.findByTestId("block-citations");

    expect(bloque.textContent).toContain(EN_INGLES);
    expect(bloque.textContent).not.toContain(EN_ESPANOL);
  });

  it("una poliza en espanol se rotula en ingles en una pantalla en ingles", async () => {
    pedido.mockResolvedValue({ ok: true, value: conUnaClausula("es", EN_ESPANOL, EN_INGLES) });
    dibujar(flujoDeMentira(), "en");

    const bloque = await screen.findByTestId("block-citations");

    expect(bloque.textContent).toContain(EN_INGLES);
    expect(bloque.textContent).not.toContain(EN_ESPANOL);
  });

  it("una parte sin traduccion conserva su nombre original, sin inventar uno", async () => {
    pedido.mockResolvedValue({ ok: true, value: conUnaClausula("en", "Territory", null) });
    dibujar(flujoDeMentira(), "es");

    const bloque = await screen.findByTestId("block-citations");

    expect(bloque.textContent).toContain("Territory");
  });
});

describe("la decision", () => {
  it("sin comentario, el servidor rechaza y lo elegido y lo escrito siguen en pantalla (BR4.1)", async () => {
    // La validacion no se reimplementa aqui: se envia, el servidor responde y la
    // pantalla dice lo que respondio. Perder lo escrito por un error de validacion es
    // la forma mas barata de que alguien decida sin comentario a la segunda.
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    decidido.mockResolvedValue({
      ok: false,
      problem: { code: "validation_failed", message: (tt) => tt("problem.validation_failed") },
    });
    dibujar();
    await screen.findByTestId("case-header");

    await userEvent.type(screen.getByLabelText(t("inbox.decision.comment_label")), "Cubierto");
    await userEvent.click(screen.getByRole("button", { name: t("inbox.decision.approve") }));

    expect(screen.getByTestId("decision-problem").textContent).toBe(t("problem.validation_failed"));
    expect(
      screen.getByLabelText<HTMLTextAreaElement>(t("inbox.decision.comment_label")).value,
    ).toBe("Cubierto");
    expect(
      screen
        .getByRole("button", { name: t("inbox.decision.approve") })
        .getAttribute("data-attempted"),
    ).toBe("true");
  });

  it("con comentario, la decision se manda con su clave de idempotencia", async () => {
    decidido.mockResolvedValue({ ok: true, value: { decision_id: "d1", resolution: "approved" } });
    dibujar();
    await screen.findByTestId("case-header");

    await userEvent.type(screen.getByLabelText(t("inbox.decision.comment_label")), "Cubierto");
    await userEvent.click(screen.getByRole("button", { name: t("inbox.decision.approve") }));

    expect(decidido).toHaveBeenCalledWith(
      "una-aseguradora",
      "case-1",
      "approve",
      "Cubierto",
      expect.stringMatching(/^dec-/),
    );
    // Esperado y no leido en el acto, por la misma razon que en la cola: el anuncio
    // llega en un dibujo posterior al de la accion.
    await waitFor(() => {
      expect(screen.getByTestId("announcer-status").textContent).toBe(t("inbox.decision.recorded"));
    });
  });

  it("ofrece solo las acciones que el servidor dice, y ninguna se deduce aqui (BR4.5)", async () => {
    // Una agencia ve marcar como enviado y no ve aprobar ni rechazar. La pantalla no
    // pregunta que tipo de aseguradora es: lo recibe resuelto.
    pedido.mockResolvedValue({ ok: true, value: caso({ available_actions: ["mark_sent"] }) });
    dibujar();
    await screen.findByTestId("case-header");

    expect(screen.getByRole("button", { name: t("inbox.decision.mark_sent") })).toBeTruthy();
    expect(screen.queryByRole("button", { name: t("inbox.decision.approve") })).toBeNull();
  });

  it("un caso que espera al asegurado no ofrece decidir, y dice por que (BR4.3)", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ state: "awaiting_insured", available_actions: [] }),
    });
    dibujar();
    await screen.findByTestId("case-header");

    expect(screen.queryByTestId("decision-form")).toBeNull();
    expect(screen.getByTestId("case-no-actions").textContent).toBe(
      t("inbox.decision.none_awaiting"),
    );
    // Y dice **que falta**, que es la otra mitad de la regla.
    expect(screen.getByTestId("block-fields").textContent).toContain(t("inbox.fields.awaiting"));
  });

  it("un caso cerrado dice que ya esta decidido", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ state: "closed", resolution: "approved", available_actions: [] }),
    });
    dibujar();
    await screen.findByTestId("case-header");

    expect(screen.getByTestId("case-no-actions").textContent).toBe(t("inbox.decision.none_closed"));
  });
});

// El cierre directo (US1.17, 2026-10-13): lo aplican las reglas, el actor de la ultima
// transicion es `system` y nadie decidio. La pantalla no puede decir «decidido por system»
// ni «ya esta decidido»: dice que se cerro sin ajustador y por que.
describe("un caso que cerraron las reglas sin ajustador (US1.17)", () => {
  const cierreDirecto: Partial<CaseDetailOut> = {
    state: "closed",
    resolution: "registered",
    derivation_reason: null,
    rule_category: "direct_close",
    fired_rules: ["R-CIERRE-DIRECTO"],
    available_actions: [],
    can_correct_fields: false,
    explanation: {
      asked: "none",
      cited: "none",
      rule: "present",
      decided_by: "present",
      decided_at: "present",
      decided_by_kind: "system",
      decided_by_id: null,
      decided_at_iso: "2026-09-28T12:30:00+00:00",
    },
  };

  it("dice que no hubo ajustador, no nombra al sistema y no ofrece decidir ni corregir", async () => {
    pedido.mockResolvedValue({ ok: true, value: caso(cierreDirecto) });
    dibujar();

    const quien = await screen.findByTestId("case-decided-by");
    expect(quien.textContent).toBe(t("inbox.explanation.by_rules"));
    // Y **cuando**, que es la otra mitad de la explicacion.
    expect(screen.getByTestId("case-decided-at").textContent).not.toBe("");
    expect(screen.getByTestId("case-resolution").textContent).toBe(t("case.resolution.registered"));
    const sin = screen.getByTestId("case-no-actions");
    expect(sin.textContent).toBe(t("inbox.decision.none_closed_by_rules"));
    expect(screen.queryByTestId("decision-form")).toBeNull();
    // Ni un actor en crudo ni «decidido» en ningun renglon del encabezado.
    const encabezado = screen.getByTestId("case-header").textContent;
    expect(encabezado).not.toMatch(/system/i);
    expect(encabezado).not.toContain(t("inbox.decision.none_closed"));
    // Sin acciones de correccion: el caso esta cerrado.
    expect(screen.getByTestId("block-fields").textContent).toContain(t("inbox.correction.closed"));
  });

  it("«por que llego aqui» dice que no paso por un ajustador, no que falta el motivo", async () => {
    pedido.mockResolvedValue({ ok: true, value: caso(cierreDirecto) });
    dibujar();

    const motivo = await screen.findByTestId("case-reason");
    expect(motivo.textContent).toBe(t("inbox.case.not_handed_off"));
    expect(motivo.textContent).not.toBe(t("inbox.case.no_reason"));
  });

  it("la regla que lo permitio aparece con su titulo y su referencia", async () => {
    pedido.mockResolvedValue({ ok: true, value: caso(cierreDirecto) });
    dibujar();
    await screen.findByTestId("case-header");

    const regla = screen.getByTestId("block-rule");
    expect(within(regla).getByRole("heading").textContent).toBe(t("inbox.block.rule_closed"));
    expect(regla.textContent).toContain(t("inbox.rule.reason.direct_close"));
    expect(within(regla).getByTestId("rule-reference").textContent).toBe(
      t("inbox.rule.reference", { rules: "R-CIERRE-DIRECTO" }),
    );
  });

  it("un actor del sistema en un caso aprobado no se presenta como cierre directo", async () => {
    // Los ejemplos sembrados antes del 2026-10-13 cerraron todos con el sistema como autor,
    // tambien los aprobados: «sin ajustador» solo vale para la resolucion que ninguna persona
    // firma, y esos casos viejos no se presentan como cierre directo.
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ ...cierreDirecto, resolution: "approved" }),
    });
    dibujar();

    const quien = await screen.findByTestId("case-decided-by");
    expect(quien.textContent).not.toBe(t("inbox.explanation.by_rules"));
    expect(screen.getByTestId("case-no-actions").textContent).toBe(t("inbox.decision.none_closed"));
  });
});

// Un caso que la agente aun evalua (`verifying`, `deciding`): el personal lo puede tomar y
// se le dice que tomarlo le quita el cierre a las reglas (2026-10-13).
describe("un caso que la agente aun evalua", () => {
  it.each(["verifying", "deciding"] as const)(
    "en %s el personal puede tomarlo, y la pantalla le dice que cuesta algo",
    async (estado) => {
      pedido.mockResolvedValue({
        ok: true,
        value: caso({
          state: estado,
          derivation_reason: null,
          rule_category: null,
          fired_rules: [],
        }),
      });
      dibujar();
      await screen.findByTestId("case-header");

      expect(screen.getByTestId("case-takeover-note").textContent).toBe(
        t("inbox.decision.takeover_note"),
      );
      expect(screen.getByRole("button", { name: t("inbox.decision.approve") })).toBeTruthy();
      expect(screen.getByRole("button", { name: t("inbox.decision.reject") })).toBeTruthy();
    },
  );

  it.each([
    ["verifying", () => t("cases.group.verifying")],
    ["deciding", () => t("cases.group.deciding")],
  ] as const)(
    "en %s «por que llego aqui» dice que la agente aun lo esta revisando",
    async (estado, frase) => {
      pedido.mockResolvedValue({
        ok: true,
        value: caso({ state: estado, derivation_reason: null, rule_category: null }),
      });
      dibujar();

      const motivo = await screen.findByTestId("case-reason");
      expect(motivo.textContent).toBe(frase());
      expect(motivo.textContent).not.toBe(t("inbox.case.no_reason"));
    },
  );

  it("un caso derivado sin motivo registrado sigue diciendo que no hay motivo", async () => {
    pedido.mockResolvedValue({ ok: true, value: caso({ derivation_reason: null }) });
    dibujar();

    const motivo = await screen.findByTestId("case-reason");
    expect(motivo.textContent).toBe(t("inbox.case.no_reason"));
  });

  it("un caso derivado no lleva ese aviso: ya esta con un ajustador", async () => {
    pedido.mockResolvedValue({ ok: true, value: caso() });
    dibujar();
    await screen.findByTestId("case-header");

    expect(screen.queryByTestId("case-takeover-note")).toBeNull();
    expect(screen.getByRole("button", { name: t("inbox.decision.approve") })).toBeTruthy();
  });

  it("aunque la categoria ya este guardada, no cuenta por que paso a un ajustador", async () => {
    // Las reglas corrieron y el caso aun no se movio: decir «por que paso a un ajustador»
    // seria contar un resultado que todavia no ocurrio.
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ state: "deciding", rule_category: "referral", derivation_reason: null }),
    });
    dibujar();
    await screen.findByTestId("case-header");

    expect(screen.queryByTestId("block-rule")).toBeNull();
  });
});

describe("la correccion de un campo", () => {
  it("un valor invalido se rechaza con el mensaje del servidor y lo escrito se queda (BR3.3)", async () => {
    // Conservar lo escrito es lo que impide que un intento fallido borre un dato bueno
    // y obligue a teclearlo otra vez.
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    corregido.mockResolvedValue({
      ok: false,
      problem: { code: "validation_failed", message: (tt) => tt("problem.validation_failed") },
    });
    dibujar();
    await screen.findByTestId("case-header");

    await userEvent.click(
      screen.getByRole("button", {
        name: t("inbox.correction.edit", { field: t("case.field.injuries") }),
      }),
    );
    await userEvent.type(screen.getByLabelText(t("inbox.correction.value_label")), "32 de febrero");
    await userEvent.click(screen.getByRole("button", { name: t("inbox.correction.save") }));

    expect(screen.getByTestId("correction-problem-injuries").textContent).toBe(
      t("problem.validation_failed"),
    );
    expect(screen.getByLabelText<HTMLInputElement>(t("inbox.correction.value_label")).value).toBe(
      "32 de febrero",
    );
  });

  it("un valor valido se guarda con su clave de idempotencia y se avisa", async () => {
    corregido.mockResolvedValue({ ok: true, value: { receipt_id: "r1" } });
    dibujar();
    await screen.findByTestId("case-header");

    await userEvent.click(
      screen.getByRole("button", {
        name: t("inbox.correction.edit", { field: t("case.field.injuries") }),
      }),
    );
    await userEvent.type(screen.getByLabelText(t("inbox.correction.value_label")), "ninguno");
    await userEvent.click(screen.getByRole("button", { name: t("inbox.correction.save") }));

    expect(corregido).toHaveBeenCalledWith(
      "una-aseguradora",
      "case-1",
      "injuries",
      "ninguno",
      expect.stringMatching(/^fix-/),
    );
    await waitFor(() => {
      expect(screen.getByTestId("announcer-status").textContent).toBe(t("inbox.correction.saved"));
    });
  });

  it("un caso cerrado no ofrece corregir, y dice por que (BR3.4)", async () => {
    // La pantalla que no ofrece la accion es cortesia; el rechazo del servidor es lo
    // que de verdad lo impide, y eso lo prueba la integracion de U14.
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ state: "closed", resolution: "approved", can_correct_fields: false }),
    });
    dibujar();
    const bloque = await screen.findByTestId("block-fields");

    expect(within(bloque).queryByRole("button")).toBeNull();
    expect(bloque.textContent).toContain(t("inbox.correction.closed"));
  });
});

// El rediseno de la pantalla del visitante (2026-10-14) comparte con esta pantalla las piezas
// `OpenBlock` y `DecisionForm` y la frase del comentario. La del personal no cambia de diseno:
// una sola columna ancha, el encabezado pegajoso con las acciones y los seis bloques en su
// orden de siempre.
describe("la pantalla del personal no cambio de diseno", () => {
  const antes = (a: Node, b: Node): boolean =>
    (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;

  it("sigue siendo una columna de 75 rem, sin los dos paneles ni los pasos del visitante", async () => {
    await dibujarYEsperarEncabezado();

    const pantalla = screen.getByTestId("inbox-case");
    expect(pantalla.className).toContain("max-w-content");
    expect(pantalla.className).not.toContain("max-w-[76rem]");
    for (const propio of [
      "visitor-panes",
      "visitor-data",
      "visitor-adjuster",
      "visitor-decision",
      "step-mark",
    ]) {
      expect(screen.queryByTestId(propio), propio).toBeNull();
    }
    // Ninguna region del visitante: ni el panel del ajustador ni los datos de su reporte.
    expect(screen.queryByRole("region", { name: t("visitor.adjuster.title") })).toBeNull();
    expect(screen.queryByRole("region", { name: t("visitor.block.fields") })).toBeNull();
  });

  it("los seis bloques van en su orden de siempre, y el de los campos conserva su nombre", async () => {
    await dibujarYEsperarEncabezado();

    const orden = [
      "block-fields",
      "block-transcript",
      "block-citations",
      "block-rule",
      "block-controls",
      "block-trace",
    ].map((id) => screen.getByTestId(id));
    orden.slice(1).forEach((bloque, indice) => {
      const previo = orden.at(indice);
      expect(previo !== undefined && antes(previo, bloque)).toBe(true);
    });
    // Y su superficie de siempre: la de segundo nivel es solo de los datos del visitante.
    for (const bloque of orden) {
      expect(bloque.className.split(/\s+/)).toContain("bg-surface");
      expect(bloque.className.split(/\s+/)).not.toContain("bg-surface-alt");
    }
    // «Completitud por campo» es del personal; «Datos de tu reporte» es del visitante.
    expect(within(screen.getByTestId("block-fields")).getByRole("heading").textContent).toBe(
      t("inbox.block.fields"),
    );
    expect(screen.queryByText(t("visitor.block.fields"))).toBeNull();
  });

  it("las acciones siguen en el encabezado pegajoso, con la nota nueva del comentario", async () => {
    const encabezado = await dibujarYEsperarEncabezado();

    expect(encabezado.className).toContain("sticky");
    const formulario = within(encabezado).getByTestId("decision-form");
    // La frase de la nota la comparten las dos pantallas.
    expect(formulario.textContent).toContain(t("inbox.decision.comment_hint"));
    expect(t("inbox.decision.comment_hint")).toBe("Queda en el registro del caso.");
    // El titulo del grupo de botones es el de siempre, no el paso del visitante.
    expect(within(formulario).getByRole("group", { name: t("inbox.decision.title") })).toBeTruthy();
    expect(within(formulario).queryByRole("heading")).toBeNull();
  });
});

describe("el aviso en vivo de la vista", () => {
  it("vuelve a pedir el caso cuando un aviso habla de el (BR6.1)", async () => {
    const cable = dibujar();
    await screen.findByTestId("case-header");

    cable.empujar({
      kind: "case_updated",
      case_id: "case-1",
      summary: "cambio",
      at: "2026-09-28T12:05:00+00:00",
    });

    expect(pedido).toHaveBeenCalledTimes(2);
  });

  it("un aviso de otro caso no lo vuelve a pedir", async () => {
    // Sin esta mitad, cualquier actividad de la aseguradora recargaria la vista
    // abierta, que es una consulta por aviso.
    const cable = dibujar();
    await screen.findByTestId("case-header");

    cable.empujar({
      kind: "case_updated",
      case_id: "otro",
      summary: "cambio",
      at: "2026-09-28T12:05:00+00:00",
    });

    expect(pedido).toHaveBeenCalledTimes(1);
  });
});

describe("un caso que no se puede abrir", () => {
  it("lo inexistente y lo ajeno se ven igual, y no se dice cual fue", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    pedido.mockResolvedValue({
      ok: false,
      problem: { code: "not_found", message: (tt) => tt("problem.not_found") },
    });
    dibujar();

    const titulo = await screen.findByRole("heading", { level: 1 });
    expect(titulo.textContent).toBe(t("inbox.case.not_found"));
    expect(document.body.textContent).not.toContain("una-aseguradora");
  });
});

async function dibujarYEsperarEncabezado(): Promise<HTMLElement> {
  dibujar();
  return screen.findByTestId("case-header");
}
