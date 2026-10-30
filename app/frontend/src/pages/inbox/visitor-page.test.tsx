import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../app/testing";
import type {
  CaseDetailOut,
  InboxResult,
  RedeemOut,
  TriageNoteIn,
  TriageNoteOut,
} from "../../shared/api-client/inbox";
import type { ProblemView } from "../../shared/api-client/problems";
import { createTranslate } from "../../shared/i18n/translate";
import { statusKindForCaseProblem } from "../status/case-link-status";
import { StatusPage } from "../status/status-page";
import { formatPesos } from "../policies/policies-page";
import { callMemory } from "../voice/call-memory";
import type { WireFrame } from "../voice/voice-events";
import { VisitorCasePage, type CaseSession } from "./visitor-page";

// La pantalla propia del visitante (BR5.1 a BR5.7). Sin jerga del sistema: quien lee
// esto es la persona que reporto.

const canjeado = vi.hoisted(() => vi.fn<(token: string) => Promise<InboxResult<RedeemOut>>>());
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
const anotado = vi.hoisted(() =>
  vi.fn<
    (
      tenantId: string,
      caseId: string,
      note: TriageNoteIn,
      key: string,
    ) => Promise<InboxResult<TriageNoteOut>>
  >(),
);

vi.mock("../../shared/api-client/inbox", async (original) => {
  const real = await original<typeof import("../../shared/api-client/inbox")>();
  return {
    ...real,
    redeemLink: canjeado,
    caseDetail: pedido,
    decideCase: decidido,
    annotateTriage: anotado,
  };
});

const t = createTranslate("es");

const SESION: RedeemOut = {
  case_id: "case-1",
  tenant: "una-aseguradora",
  access: "view_and_decide",
  expires_at: "2026-09-28T13:00:00+00:00",
};

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
    fields: [
      {
        field_key: "injuries",
        status: "confirmed",
        complete: true,
        label_key: "case.field.injuries",
      },
    ],
    transcript: [],
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

/** La misma pagina de estado que dibuja la ruta cuando el enlace no vale. */
function rechazo(problem: ProblemView) {
  return <StatusPage kind={statusKindForCaseProblem(problem)} />;
}

function dibujar(props: Partial<React.ComponentProps<typeof VisitorCasePage>> = {}) {
  const canjes: CaseSession[] = [];
  renderWithProviders(
    <VisitorCasePage
      token="un-token"
      onRedeemed={(sesion) => canjes.push(sesion)}
      conversationHref={(sesion) => `/t/${sesion.tenantId}/chat`}
      renderRejected={rechazo}
      {...props}
    />,
  );
  return canjes;
}

beforeEach(() => {
  canjeado.mockReset();
  pedido.mockReset();
  decidido.mockReset();
  anotado.mockReset();
  canjeado.mockResolvedValue({ ok: true, value: SESION });
  pedido.mockResolvedValue({ ok: true, value: caso() });
});

describe("abrir el caso con el enlace", () => {
  it("canja el token una vez y avisa con que caso quedo (BR5.6)", async () => {
    const canjes = dibujar();

    await screen.findByTestId("visitor-case");
    expect(canjeado).toHaveBeenCalledTimes(1);
    expect(canjeado).toHaveBeenCalledWith("un-token");
    // Quien limpia la direccion es la ruta; esta pantalla le dice con que caso.
    expect(canjes).toEqual([
      { tenantId: "una-aseguradora", caseId: "case-1", expiresAt: "2026-09-28T13:00:00+00:00" },
    ]);
  });

  it("dice hasta cuando vale el enlace (BR5.3)", async () => {
    dibujar();

    const hasta = await screen.findByTestId("visitor-valid-until");
    expect(hasta.textContent).not.toBe("");
    expect(hasta.textContent).not.toContain("2026-09-28T13:00");
  });

  it("recargada sin token entra con su cookie y no vuelve a canjear", async () => {
    // El canje es por carga de pantalla y no un token de un solo uso; aqui no hay token
    // porque la direccion ya se limpio.
    dibujar({ token: "", tenantId: "una-aseguradora", caseId: "case-1" });

    await screen.findByTestId("visitor-case");
    expect(canjeado).not.toHaveBeenCalled();
    expect(pedido).toHaveBeenCalledWith("una-aseguradora", "case-1");
    // Y **no inventa** una hora de vencimiento que no conoce.
    expect(screen.queryByTestId("visitor-valid-until")).toBeNull();
  });

  it("no dice una palabra de la jerga del sistema (U-07)", async () => {
    dibujar();
    const pantalla = await screen.findByTestId("visitor-case");

    for (const jerga of ["bandeja", "derivado", "cola", "inbox", "tenant"]) {
      expect(pantalla.textContent.toLowerCase()).not.toContain(jerga);
    }
  });

  it("no ofrece corregir campos: eso es de quien decide con credencial", async () => {
    dibujar();
    const bloque = await screen.findByTestId("block-fields");

    expect(bloque.querySelector(`button[name], button[type="submit"]`)).toBeNull();
    expect(bloque.textContent).not.toContain(t("inbox.correction.save"));
  });
});

describe("el caso se nombra por lo que es, no por su codigo (C10, 2026-10-12)", () => {
  // Las frases se piden dentro de la prueba, no al armar la tabla: el catalogo se carga antes
  // de cada prueba y no antes de reunirlas.
  it.each([
    ["claim", (tt: typeof t) => tt("visitor.title_claim")],
    ["coverage_inquiry", (tt: typeof t) => tt("visitor.title_inquiry")],
    ["quote_request", (tt: typeof t) => tt("visitor.title_quote")],
  ] as const)("un caso %s se titula con palabras", async (tipo, titulo_esperado) => {
    pedido.mockResolvedValue({ ok: true, value: caso({ record_type: tipo }) });
    dibujar();

    const titulo = (await screen.findByRole("heading", { level: 1 })).textContent;
    expect(titulo).toBe(titulo_esperado(t));
    // El codigo ya no es el titulo: no aparece en el.
    expect(titulo).not.toContain("CA-1");
  });

  it("el codigo va en un renglon pequeno que dice para que sirve", async () => {
    dibujar();

    const renglon = await screen.findByTestId("visitor-case-number");
    expect(renglon.textContent).toBe(t("visitor.number", { case_number: "CA-1" }));
    expect(renglon.textContent).toMatch(/retomarlo o consultarlo/);
  });

  it("una consulta de poliza no se llama reporte", async () => {
    pedido.mockResolvedValue({ ok: true, value: caso({ record_type: "coverage_inquiry" }) });
    dibujar();

    await screen.findByTestId("visitor-case");
    expect(screen.getByRole("heading", { level: 1 }).textContent).not.toMatch(/reporte/i);
  });

  it("el contenedor es el de dos paneles (76 rem), y en telefono sigue ocupando el ancho", async () => {
    dibujar();

    // 2026-10-14: la columna de 52 rem de antes no alcanzaba para dos paneles lado a lado.
    // Esa columna sigue siendo la del caso de ejemplo (`cases.test.tsx`).
    const pantalla = await screen.findByTestId("visitor-case");
    expect(pantalla.className).toContain("max-w-[76rem]");
    expect(pantalla.className).not.toContain("max-w-[52rem]");
    expect(pantalla.className).not.toContain("max-w-2xl");
    expect(pantalla.className).toContain("w-full");
    // El mismo relleno lateral de antes.
    expect(pantalla.className).toContain("px-4");
  });
});

describe("lo que la persona escribio, sin tapar en su propia pantalla (C5, 2026-10-12)", () => {
  const TAPADA = "Soy [NOMBRE 1], mi póliza es [PÓLIZA 1]";
  const ESCRITA = "Soy Natalia Henao, mi póliza es POL-11";

  function conversacion(extra: Partial<CaseDetailOut> = {}): CaseDetailOut {
    return caso({
      transcript: [
        {
          turn_id: "t1",
          speaker: "agent",
          text_redacted: "Hola, ¿en qué te ayudo?",
          started_at: "x",
        },
        { turn_id: "t2", speaker: "insured", text_redacted: TAPADA, started_at: "x" },
        {
          turn_id: "t3",
          speaker: "agent",
          text_redacted: "Gracias [NOMBRE 1], ya tengo la póliza [PÓLIZA 1].",
          started_at: "x",
        },
      ],
      ...extra,
    });
  }

  it("con copia en este navegador la conversacion se lee como se escribio, sin etiquetas ni nota", async () => {
    window.localStorage.setItem("cautelia.own-text.una-aseguradora", JSON.stringify([ESCRITA]));
    window.localStorage.setItem(
      "cautelia.agent-text.una-aseguradora",
      JSON.stringify(["Gracias Natalia, ya tengo la póliza POL-11."]),
    );
    pedido.mockResolvedValue({ ok: true, value: conversacion() });
    dibujar();

    const bloque = await screen.findByTestId("block-transcript");
    expect(bloque.textContent).toContain(ESCRITA);
    expect(bloque.textContent).toContain("Gracias Natalia, ya tengo la póliza POL-11.");
    expect(bloque.textContent).not.toMatch(/\[[^\]]+ \d+\]/);
    // Sin etiquetas a la vista, la nota que las explica sobra.
    expect(within(bloque).queryByTestId("transcript-redacted-hint")).toBeNull();
    expect(bloque.textContent).not.toContain(t("inbox.transcript.redacted_hint"));
  });

  it("sin copia (otro navegador) se ven las etiquetas y la nota que las explica", async () => {
    pedido.mockResolvedValue({ ok: true, value: conversacion() });
    dibujar();

    const bloque = await screen.findByTestId("block-transcript");
    expect(bloque.textContent).toContain(TAPADA);
    expect(within(bloque).getByTestId("transcript-redacted-hint").textContent).toBe(
      t("inbox.transcript.redacted_hint"),
    );
  });

  it("una copia que no encaja con la forma del mensaje no se usa", async () => {
    window.localStorage.setItem(
      "cautelia.own-text.una-aseguradora",
      JSON.stringify(["Me llamo Natalia y mi póliza es POL-11"]),
    );
    pedido.mockResolvedValue({ ok: true, value: conversacion() });
    dibujar();

    const bloque = await screen.findByTestId("block-transcript");
    expect(bloque.textContent).toContain(TAPADA);
    expect(bloque.textContent).not.toContain("Natalia");
    expect(within(bloque).getByTestId("transcript-redacted-hint")).toBeTruthy();
  });

  it("lo que dijo la agente no se busca entre lo que escribio la persona, ni al reves", async () => {
    // La misma frase guardada del lado equivocado no destapa nada.
    window.localStorage.setItem("cautelia.agent-text.una-aseguradora", JSON.stringify([ESCRITA]));
    window.localStorage.setItem(
      "cautelia.own-text.una-aseguradora",
      JSON.stringify(["Gracias Natalia, ya tengo la póliza POL-11."]),
    );
    pedido.mockResolvedValue({ ok: true, value: conversacion() });
    dibujar();

    const bloque = await screen.findByTestId("block-transcript");
    expect(bloque.textContent).not.toContain("Natalia");
  });

  it("la pregunta de cobertura tambien se lee como se escribio", async () => {
    window.localStorage.setItem(
      "cautelia.own-text.una-aseguradora",
      JSON.stringify(["¿Mi póliza POL-11 cubre el granizo?"]),
    );
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        coverage_answers: [
          {
            answer_id: "a1",
            outcome: "no_clause_found",
            question_redacted: "¿Mi póliza [PÓLIZA 1] cubre el granizo?",
            citations: [],
          },
        ],
      }),
    });
    dibujar();

    const bloque = await screen.findByTestId("block-citations");
    expect(bloque.textContent).toContain("¿Mi póliza POL-11 cubre el granizo?");
    expect(bloque.textContent).not.toContain("[PÓLIZA 1]");
  });
});

describe("lo que se dijo en la llamada, sin tapar en 'Ver mi caso' (2026-10-13)", () => {
  // La consola recibe los dos lados sin tapar y la base los guarda tapados. Aqui se hace el
  // recorrido entero: los cuadros que llegaron por el cable pasan por la memoria de la
  // llamada (`callMemory`) y la pantalla del caso destapa cada turno que la base guardo.
  const dicho = (speaker: "insured" | "agent", text: string): WireFrame => ({
    type: "transcript",
    speaker,
    text,
    final: true,
  });

  it("con el cable limpio, el caso se lee sin etiquetas ni nota, de los dos lados", async () => {
    const recordar = callMemory("una-aseguradora");
    recordar(dicho("agent", "Hola, ¿en qué te ayudo?"));
    recordar(dicho("insured", "Soy Natalia Henao,"));
    recordar(dicho("insured", "mi póliza es POL-11"));
    recordar(dicho("agent", "Gracias Natalia, tengo tu póliza POL-11."));
    // La respuesta de cobertura llega en dos lineas: la que la base guarda, y la vuelta al
    // reporte con su pregunta, que es de un turno anterior.
    recordar(dicho("agent", "En tu póliza, esto lo trata la parte A: cubre daños en Colombia."));
    recordar(dicho("agent", "Volviendo al reporte: ¿Cuál es tu placa?"));
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        transcript: [
          {
            turn_id: "t1",
            speaker: "agent",
            text_redacted: "Hola, ¿en qué te ayudo?",
            started_at: "x",
          },
          {
            turn_id: "t2",
            speaker: "insured",
            text_redacted: "Soy [NOMBRE 1], mi póliza es [PÓLIZA 1]",
            started_at: "x",
          },
          {
            turn_id: "t3",
            speaker: "agent",
            text_redacted: "Gracias [NOMBRE 1], tengo tu póliza [PÓLIZA 1].",
            started_at: "x",
          },
          {
            turn_id: "t4",
            speaker: "agent",
            text_redacted: "En tu póliza, esto lo trata la parte A: cubre daños en [LUGAR 1].",
            started_at: "x",
          },
        ],
      }),
    });
    dibujar();

    const bloque = await screen.findByTestId("block-transcript");
    expect(bloque.textContent).toContain("Soy Natalia Henao, mi póliza es POL-11");
    expect(bloque.textContent).toContain("Gracias Natalia, tengo tu póliza POL-11.");
    expect(bloque.textContent).toContain("cubre daños en Colombia.");
    expect(bloque.textContent).not.toMatch(/\[[^\]]+ \d+\]/);
    expect(within(bloque).queryByTestId("transcript-redacted-hint")).toBeNull();
  });

  it("una respuesta pegada a la vuelta al reporte, en una sola linea, no se destaparia", async () => {
    // Es lo que hacia el servidor antes de partirla en dos: la copia no encajaba con el
    // turno entero que guarda la base, y el caso mostraba la etiqueta.
    const recordar = callMemory("una-aseguradora");
    recordar(
      dicho(
        "agent",
        "En tu póliza, esto lo trata la parte A: cubre daños en Colombia. Volviendo al reporte: ¿Cuál es tu placa?",
      ),
    );
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        transcript: [
          {
            turn_id: "t4",
            speaker: "agent",
            text_redacted: "En tu póliza, esto lo trata la parte A: cubre daños en [LUGAR 1].",
            started_at: "x",
          },
        ],
      }),
    });
    dibujar();

    const bloque = await screen.findByTestId("block-transcript");
    expect(bloque.textContent).toContain("[LUGAR 1]");
  });
});

describe("los tres bloques del final dicen cada cosa en palabras (E3, 2026-10-12)", () => {
  it("por que paso a un ajustador, que se reviso y como se respondio, sin codigos crudos", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        rule_category: "referral",
        fired_rules: ["KNO-R-01"],
        controls_ok: false,
        control_findings: ["pii_found"],
      }),
    });
    dibujar();
    await screen.findByTestId("visitor-case");

    const regla = screen.getByTestId("block-rule");
    expect(within(regla).getByRole("heading").textContent).toBe(t("inbox.block.rule"));
    expect(regla.textContent).toContain(t("inbox.rule.reason.referral"));
    expect(within(regla).getByTestId("rule-reference").textContent).toBe(
      t("inbox.rule.reference", { rules: "KNO-R-01" }),
    );
    const controles = screen.getByTestId("block-controls");
    expect(controles.textContent).toContain(t("inbox.controls.finding.pii_found"));
    expect(controles.textContent).not.toContain("pii_found");
    expect(screen.getByTestId("block-trace").textContent).toContain(t("trace.page.latency"));
    // Ni la categoria cruda ni "No medido" aparecen en ningun bloque.
    const pantalla = screen.getByTestId("visitor-case").textContent;
    expect(pantalla).not.toContain("referral");
    expect(pantalla).not.toContain(t("trace.page.not_measured"));
  });

  it("un caso cerrado por las reglas lo dice con el titulo que le corresponde", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ rule_category: "direct_close", fired_rules: [] }),
    });
    dibujar();
    await screen.findByTestId("visitor-case");

    const regla = screen.getByTestId("block-rule");
    expect(within(regla).getByRole("heading").textContent).toBe(t("inbox.block.rule_closed"));
    expect(regla.textContent).toContain(t("inbox.rule.reason.direct_close"));
    expect(within(regla).queryByTestId("rule-reference")).toBeNull();
  });

  it("la pantalla del visitante ensena el enlace a Langfuse solo cuando el servidor manda la direccion", async () => {
    const direccion = "https://us.cloud.langfuse.com/project/p1/traces/123";
    pedido.mockResolvedValue({ ok: true, value: caso({ trace_url: direccion }) });
    dibujar();
    await screen.findByTestId("visitor-case");

    const bloque = screen.getByTestId("block-trace");
    const enlace = within(bloque).getByTestId("trace-langfuse-link");
    expect(enlace.getAttribute("href")).toBe(direccion);
    expect(enlace.getAttribute("target")).toBe("_blank");
    expect(bloque.textContent).toContain(t("inbox.trace.langfuse_note"));
  });

  it("sin direccion del servidor la pantalla del visitante no ensena enlace a Langfuse", async () => {
    pedido.mockResolvedValue({ ok: true, value: caso() });
    dibujar();
    await screen.findByTestId("visitor-case");

    expect(screen.queryByTestId("trace-langfuse-link")).toBeNull();
  });

  it("lo que no tiene dato no se pinta: ni reglas, ni controles, ni respuesta", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        rule_category: null,
        fired_rules: [],
        controls_ok: null,
        trace_cost_usd: null,
        trace_latency_ms: null,
      }),
    });
    dibujar();
    await screen.findByTestId("visitor-case");

    for (const bloque of ["block-rule", "block-controls", "block-trace"]) {
      expect(screen.queryByTestId(bloque)).toBeNull();
    }
  });
});

// El cierre directo y los segundos de evaluacion (US1.17, AC1.17.4, 2026-10-13). Ninguno de
// los dos es un caso con un ajustador: la pantalla no puede usar las frases del derivado ni
// ofrecer decidir, y no puede nombrar al sistema ni a su estado interno.
describe("un caso que cerraron las reglas, o que la agente aun evalua", () => {
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

  it("un cierre directo dice que se cerro sin ajustador y la regla que lo permitio (AC1.17.4)", async () => {
    pedido.mockResolvedValue({ ok: true, value: caso(cierreDirecto) });
    dibujar();
    await screen.findByTestId("visitor-case");

    expect(screen.getByTestId("visitor-intro").textContent).toBe(t("inbox.closed_by_rules.intro"));
    const regla = screen.getByTestId("block-rule");
    expect(within(regla).getByRole("heading").textContent).toBe(t("inbox.block.rule_closed"));
    expect(regla.textContent).toContain(t("inbox.rule.reason.direct_close"));
    expect(within(regla).getByTestId("rule-reference").textContent).toBe(
      t("inbox.rule.reference", { rules: "R-CIERRE-DIRECTO" }),
    );
  });

  it("un cierre directo no ofrece decidir ni corregir, y no afirma cobertura ni montos", async () => {
    pedido.mockResolvedValue({ ok: true, value: caso(cierreDirecto) });
    dibujar();
    await screen.findByTestId("visitor-case");

    expect(screen.queryByTestId("decision-form")).toBeNull();
    expect(screen.getByTestId("visitor-no-actions").textContent).toBe(
      t("inbox.closed_by_rules.note"),
    );
    // Es el mismo caso que «ya esta decidido»: aqui nadie decidio.
    const pantalla = screen.getByTestId("visitor-case").textContent;
    expect(pantalla).not.toContain(t("inbox.decision.none_closed"));
    expect(pantalla).not.toContain(t("visitor.intro"));
    expect(pantalla).not.toContain(t("inbox.explanation.by_visitor"));
    expect(pantalla).not.toMatch(/system|deciding|direct_close|registered/i);
    expect(pantalla.toLowerCase()).not.toContain("bandeja");
  });

  it("sin nada que decidir ni anotar, el panel dice el estado del caso y no invita a hacer de ajustador", async () => {
    pedido.mockResolvedValue({ ok: true, value: caso(cierreDirecto) });
    dibujar();
    const panel = await screen.findByTestId("visitor-adjuster");

    expect(within(panel).getByRole("heading", { level: 2 }).textContent).toBe(
      t("visitor.status.title"),
    );
    expect(panel.textContent).not.toContain(t("visitor.adjuster.title"));
    expect(panel.textContent).not.toContain(t("visitor.decision.title"));
    expect(panel.className).not.toContain("border-l-brand");
  });

  it.each(["verifying", "deciding"] as const)(
    "en %s se ve como en revision: ni con un ajustador ni con botones para decidir",
    async (estado) => {
      pedido.mockResolvedValue({
        ok: true,
        value: caso({
          state: estado,
          derivation_reason: null,
          // La categoria puede estar guardada antes de que el caso se mueva: decir ya
          // por que «paso a un ajustador» seria contar lo que no ha ocurrido.
          rule_category: "referral",
          available_actions: [],
          can_correct_fields: true,
        }),
      });
      dibujar();
      await screen.findByTestId("visitor-case");

      const frase = estado === "verifying" ? t("cases.group.verifying") : t("cases.group.deciding");
      expect(screen.getByTestId("visitor-intro").textContent).toBe(frase);
      expect(screen.getByTestId("visitor-intro").textContent).not.toContain("ajustador");
      // Ningun aviso aparte: la introduccion ya dice que la agente evalua.
      expect(screen.queryByTestId("visitor-no-actions")).toBeNull();
      expect(screen.queryByTestId("decision-form")).toBeNull();
      expect(screen.queryByTestId("block-rule")).toBeNull();
      const pantalla = screen.getByTestId("visitor-case").textContent;
      expect(pantalla).not.toContain(t("visitor.intro"));
      expect(pantalla).not.toContain(t("inbox.decision.none_in_conversation"));
      expect(pantalla).not.toMatch(/deciding|verifying/i);
    },
  );

  it("un caso derivado sigue contando lo de siempre", async () => {
    // El control positivo: sin el, las frases nuevas podrian estar pintandose siempre.
    dibujar();
    await screen.findByTestId("visitor-case");

    expect(screen.getByTestId("visitor-intro").textContent).toBe(t("visitor.intro"));
    expect(screen.getByTestId("decision-form")).toBeTruthy();
  });
});

// Mientras la agente evalua el caso, la pagina lo vuelve a leer: cada 3 s, como mucho 10
// veces, y se detiene al salir de revision, al tope y al dejar la pantalla (2026-10-13).
describe("«Ver mi caso» abierto mientras la agente evalua el caso", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  const EN_REVISION = () =>
    caso({ state: "deciding", derivation_reason: null, available_actions: [] });

  /** Solo `setTimeout` falso: el resto de la pantalla sigue con el reloj de verdad. */
  async function abrirConFechasFalsas() {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const dibujo = renderWithProviders(
      <VisitorCasePage
        token="un-token"
        conversationHref={(sesion) => `/t/${sesion.tenantId}/chat`}
        renderRejected={rechazo}
      />,
    );
    await pasar(0);
    await pasar(0);
    return dibujo;
  }

  async function pasar(ms: number) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ms);
    });
  }

  it("lo vuelve a leer cada 3 s y, al salir de revision, muestra el caso como siempre", async () => {
    pedido
      .mockResolvedValueOnce({ ok: true, value: EN_REVISION() })
      .mockResolvedValue({ ok: true, value: caso() });

    await abrirConFechasFalsas();

    expect(screen.getByTestId("visitor-intro").textContent).toBe(t("cases.group.deciding"));
    expect(screen.queryByTestId("decision-form")).toBeNull();
    expect(pedido).toHaveBeenCalledTimes(1);
    await pasar(2999);
    expect(pedido).toHaveBeenCalledTimes(1);
    await pasar(1);

    expect(pedido).toHaveBeenCalledTimes(2);
    expect(pedido).toHaveBeenLastCalledWith("una-aseguradora", "case-1");
    expect(screen.getByTestId("visitor-intro").textContent).toBe(t("visitor.intro"));
    expect(screen.getByTestId("decision-form")).toBeTruthy();
    // Y no canjea otra vez el enlace: solo vuelve a pedir el caso.
    expect(canjeado).toHaveBeenCalledTimes(1);
  });

  it("si lo que sale es un cierre directo, lo cuenta como tal", async () => {
    pedido.mockResolvedValueOnce({ ok: true, value: EN_REVISION() }).mockResolvedValue({
      ok: true,
      value: caso({
        state: "closed",
        resolution: "registered",
        derivation_reason: null,
        rule_category: "direct_close",
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
      }),
    });

    await abrirConFechasFalsas();
    await pasar(3000);

    expect(screen.getByTestId("visitor-intro").textContent).toBe(t("inbox.closed_by_rules.intro"));
    expect(screen.getByTestId("block-rule")).toBeTruthy();
  });

  it("se detiene en cuanto sale de revision: no vuelve a pedir", async () => {
    pedido
      .mockResolvedValueOnce({ ok: true, value: EN_REVISION() })
      .mockResolvedValue({ ok: true, value: caso() });

    await abrirConFechasFalsas();
    await pasar(3000);
    await pasar(3000 * 20);

    expect(pedido).toHaveBeenCalledTimes(2);
  });

  it("se detiene en el tope --la primera lectura y diez mas-- y se queda como esta, sin aviso", async () => {
    pedido.mockImplementation(() => Promise.resolve({ ok: true, value: EN_REVISION() }));

    await abrirConFechasFalsas();
    await pasar(3000 * 40);

    expect(pedido).toHaveBeenCalledTimes(1 + 10);
    expect(screen.getByTestId("visitor-intro").textContent).toBe(t("cases.group.deciding"));
    expect(screen.queryByTestId("visitor-no-actions")).toBeNull();
  });

  it("limpia el temporizador al dejar la pantalla: no vuelve a pedir", async () => {
    pedido.mockImplementation(() => Promise.resolve({ ok: true, value: EN_REVISION() }));

    const dibujo = await abrirConFechasFalsas();
    await pasar(3000);
    expect(pedido).toHaveBeenCalledTimes(2);

    dibujo.unmount();
    await pasar(3000 * 20);

    expect(pedido).toHaveBeenCalledTimes(2);
  });

  it("si una lectura falla --el enlace vencio-- se queda como esta y no insiste", async () => {
    pedido
      .mockResolvedValueOnce({ ok: true, value: EN_REVISION() })
      .mockResolvedValue({ ok: false, problem: { code: "not_found", message: () => "" } });

    await abrirConFechasFalsas();
    await pasar(3000 * 20);

    expect(pedido).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("visitor-intro").textContent).toBe(t("cases.group.deciding"));
  });

  it("un caso que no esta en revision se pide una sola vez", async () => {
    await abrirConFechasFalsas();
    await pasar(3000 * 20);

    expect(pedido).toHaveBeenCalledTimes(1);
  });
});

describe("un enlace que no vale", () => {
  it("la firma alterada y el caso inexistente muestran la misma pagina (BR5.2)", async () => {
    // Un mensaje distinto por causa le diria a quien prueba enlaces cual de sus
    // intentos acerto el identificador.
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const vistas: string[] = [];
    for (const codigo of ["link_invalid", "not_found"] as const) {
      canjeado.mockResolvedValue({
        ok: false,
        problem: { code: codigo, message: (tt) => tt(`problem.${codigo}` as "problem.not_found") },
      });
      const { unmount } = renderWithProviders(
        <VisitorCasePage token="un-token" conversationHref={() => "/"} renderRejected={rechazo} />,
      );
      const pagina = await screen.findByTestId("status-page");
      vistas.push(pagina.textContent);
      unmount();
    }

    expect(vistas[0]).toBe(vistas[1]);
  });

  it("sin token y sin caso en la direccion se responde igual", async () => {
    // Una direccion que no dice a que caso se entra no es distinta de un enlace que no
    // vale: distinguirlas seria un oraculo mas.
    dibujar({ token: "" });

    const pagina = await screen.findByTestId("status-page");
    expect(pagina.getAttribute("data-status-kind")).toBe("link_invalid");
    expect(canjeado).not.toHaveBeenCalled();
  });

  it("un caso que el servidor no sirve se ve igual por las dos puertas", async () => {
    // Las dos puertas son el canje y la lectura del caso, y **los dos codigos** son
    // `link_invalid` y `not_found`: las cuatro combinaciones tienen que mostrar la
    // misma pagina. Con una sola de las cuatro, esta pantalla podia traducir uno de los
    // codigos a otra pagina sin que se cayera nada --se comprobo rompiendolo-- y ese
    // "servicio no disponible" frente a "enlace no valido" ya dice que el caso existe.
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const vistas: string[] = [];
    for (const puerta of ["redeem", "detail"] as const) {
      for (const codigo of ["link_invalid", "not_found"] as const) {
        const fallo = {
          ok: false as const,
          problem: {
            code: codigo,
            message: (tt: import("../../shared/i18n/translate").Translate) =>
              tt(`problem.${codigo}` as "problem.not_found"),
          },
        };
        canjeado.mockResolvedValue(puerta === "redeem" ? fallo : { ok: true, value: SESION });
        pedido.mockResolvedValue(puerta === "detail" ? fallo : { ok: true, value: caso() });
        const { unmount } = renderWithProviders(
          <VisitorCasePage
            token="un-token"
            conversationHref={() => "/"}
            renderRejected={rechazo}
          />,
        );
        const pagina = await screen.findByTestId("status-page");
        vistas.push(`${pagina.getAttribute("data-status-kind") ?? ""}|${pagina.textContent}`);
        unmount();
      }
    }

    expect(new Set(vistas).size).toBe(1);
    expect(vistas[0]).toContain("link_invalid|");
  });
});

describe("decidir su propio caso", () => {
  it("la decision se manda y la pantalla muestra que el caso se retomo", async () => {
    decidido.mockResolvedValue({ ok: true, value: { decision_id: "d1", resolution: "approved" } });
    pedido.mockResolvedValueOnce({ ok: true, value: caso() }).mockResolvedValueOnce({
      ok: true,
      value: caso({ state: "closed", resolution: "approved", available_actions: [] }),
    });
    dibujar();
    await screen.findByTestId("visitor-case");

    await userEvent.type(
      screen.getByLabelText(t("inbox.decision.comment_label")),
      "Me parece bien",
    );
    await userEvent.click(screen.getByRole("button", { name: t("inbox.decision.approve") }));

    expect(decidido).toHaveBeenCalledWith(
      "una-aseguradora",
      "case-1",
      "approve",
      "Me parece bien",
      expect.stringMatching(/^visitor-/),
    );
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(t("visitor.done_title"));
    expect(screen.getByTestId("visitor-resolution").textContent).toBe(
      t("case.resolution.approved"),
    );
    // Y la vuelta a la conversacion, que es por donde llego.
    expect(screen.getByRole("link", { name: t("action.back_to_conversation") })).toBeTruthy();
  });

  it("si el enlace vence mientras escribe, la nota sigue en pantalla (BR5.4)", async () => {
    // Perderla convierte un vencimiento en trabajo perdido, y lo sufre justo quien
    // estaba terminando de decidir.
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    decidido.mockResolvedValue({
      ok: false,
      problem: { code: "link_invalid", message: (tt) => tt("problem.link_invalid") },
    });
    // Vencio de verdad: el caso ya no se sirve (2026-10-12; antes se daba por vencido
    // cualquier rechazo de la decision).
    pedido.mockResolvedValueOnce({ ok: true, value: caso() }).mockResolvedValue({
      ok: false,
      problem: { code: "link_invalid", message: (tt) => tt("problem.link_invalid") },
    });
    dibujar();
    await screen.findByTestId("visitor-case");

    await userEvent.type(
      screen.getByLabelText(t("inbox.decision.comment_label")),
      "No estoy de acuerdo con esto",
    );
    await userEvent.click(screen.getByRole("button", { name: t("inbox.decision.reject") }));

    // No el mensaje generico de enlace no valido: **la frase que dice que la nota se
    // queda**. Sin ella, quien ve "enlace no valido" cierra la pestana y pierde lo
    // escrito, que es exactamente lo que la regla existe para evitar.
    expect(await screen.findByTestId("decision-problem")).toBeTruthy();
    expect(screen.getByTestId("decision-problem").textContent).toBe(
      t("visitor.expired_with_comment"),
    );
    expect(
      screen.getByLabelText<HTMLTextAreaElement>(t("inbox.decision.comment_label")).value,
    ).toBe("No estoy de acuerdo con esto");
  });

  it("si el enlace sigue vigente, el rechazo no se llama vencimiento", async () => {
    // 2026-10-12: el servidor rechazaba la decision con un enlace de una hora que no habia
    // vencido, y la pantalla decia "el enlace vencio mientras escribias". El caso se sigue
    // sirviendo --`pedido` responde bien--, asi que lo que falto fue guardar la decision.
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    decidido.mockResolvedValue({
      ok: false,
      problem: { code: "not_found", message: (tt) => tt("problem.not_found") },
    });
    dibujar();
    await screen.findByTestId("visitor-case");

    await userEvent.type(screen.getByLabelText(t("inbox.decision.comment_label")), "Lo apruebo");
    await userEvent.click(screen.getByRole("button", { name: t("inbox.decision.approve") }));

    expect(await screen.findByTestId("decision-problem")).toBeTruthy();
    expect(screen.getByTestId("decision-problem").textContent).toBe(
      t("visitor.decision_not_saved"),
    );
    expect(screen.getByTestId("decision-problem").textContent).not.toBe(
      t("visitor.expired_with_comment"),
    );
    // La nota sigue ahi para reintentar.
    expect(
      screen.getByLabelText<HTMLTextAreaElement>(t("inbox.decision.comment_label")).value,
    ).toBe("Lo apruebo");
  });

  it("ofrece solo las acciones que su aseguradora permite (BR4.5)", async () => {
    pedido.mockResolvedValue({ ok: true, value: caso({ available_actions: ["mark_sent"] }) });
    dibujar();
    await screen.findByTestId("visitor-case");

    expect(screen.getByRole("button", { name: t("inbox.decision.mark_sent") })).toBeTruthy();
    expect(screen.queryByRole("button", { name: t("inbox.decision.approve") })).toBeNull();
  });

  it("un caso que no admite decision lo dice, sin ofrecer el formulario", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ state: "awaiting_insured", available_actions: [] }),
    });
    dibujar();
    await screen.findByTestId("visitor-case");

    expect(screen.queryByTestId("decision-form")).toBeNull();
    expect(screen.getByTestId("visitor-no-actions").textContent).toBe(
      t("inbox.decision.none_awaiting"),
    );
  });
});

// Los dos paneles (Miguel, 2026-10-14): a la izquierda el del ajustador --anotar y decidir-- y a la
// derecha los datos del reporte con las reglas; debajo de los dos, a todo el ancho, la conversacion
// y lo demas. jsdom no calcula estilos ni puntos de quiebre: lo que aqui se prueba es el orden del
// documento (que es el de pantalla angosta), la estructura y las clases que arman la rejilla en
// escritorio. Que la rejilla se vea como se dice solo se comprueba en el navegador.
describe("los dos paneles: el del ajustador y los datos del reporte", () => {
  const OFRECE: Partial<CaseDetailOut> = {
    can_annotate_triage: true,
    triage_amount_steps: [1000, 10000],
  };

  /** Verdadero si `a` queda antes que `b` en el orden del documento. */
  const antes = (a: Node, b: Node): boolean =>
    (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;

  async function abrir(extra: Partial<CaseDetailOut> = {}) {
    pedido.mockResolvedValue({ ok: true, value: caso(extra) });
    dibujar();
    await screen.findByTestId("visitor-case");
  }

  const panelDelAjustador = () => screen.getByRole("region", { name: t("visitor.adjuster.title") });
  const panelDeDatos = () => screen.getByRole("region", { name: t("visitor.block.fields") });

  it("cada panel es una region con nombre, y los datos no se llaman «completitud por campo»", async () => {
    await abrir(OFRECE);

    expect(within(panelDelAjustador()).getByRole("heading", { level: 2 }).textContent).toBe(
      t("visitor.adjuster.title"),
    );
    expect(within(panelDeDatos()).getByRole("heading", { level: 2 }).textContent).toBe(
      t("visitor.block.fields"),
    );
    // «Completitud por campo» es la jerga de quien decide con credencial.
    expect(screen.getByTestId("visitor-case").textContent).not.toContain(t("inbox.block.fields"));
    expect(panelDeDatos()).toBe(screen.getByTestId("block-fields"));
  });

  it("los encabezados bajan de a un nivel: titulo, paneles y pasos", async () => {
    await abrir(OFRECE);

    const niveles = within(screen.getByTestId("visitor-case"))
      .getAllByRole("heading")
      .map((titulo) => Number(titulo.tagName.slice(1)));
    expect(niveles[0]).toBe(1);
    niveles.slice(1).forEach((nivel, indice) => {
      // Cada encabezado es, como mucho, un nivel mas hondo que el anterior.
      expect(nivel).toBeLessThanOrEqual((niveles.at(indice) ?? 0) + 1);
    });
    // Los dos pasos cuelgan del panel del ajustador, como encabezados de nivel 3.
    // El nombre accesible no cuenta la marca numerica, que va oculta para el lector de pantalla.
    const panel = panelDelAjustador();
    expect(within(panel).getAllByRole("heading", { level: 3 })).toHaveLength(2);
    for (const paso of [t("visitor.triage.title"), t("visitor.decision.title")]) {
      expect(within(panel).getByRole("heading", { level: 3, name: paso })).toBeTruthy();
    }
  });

  it("en el orden del documento --el de pantalla angosta-- los datos y las reglas van antes que el panel del ajustador", async () => {
    await abrir(OFRECE);

    const datos = screen.getByTestId("visitor-data");
    const ajustador = panelDelAjustador();
    expect(antes(datos, ajustador)).toBe(true);
    // Las reglas viven en la columna de los datos, despues de ellos y antes del ajustador.
    expect(datos.contains(screen.getByTestId("block-fields"))).toBe(true);
    expect(datos.contains(screen.getByTestId("block-rule"))).toBe(true);
    expect(antes(screen.getByTestId("block-fields"), screen.getByTestId("block-rule"))).toBe(true);
    expect(antes(screen.getByTestId("block-rule"), ajustador)).toBe(true);
    // Y cada panel es hermano del otro, en el mismo contenedor de la rejilla.
    const rejilla = screen.getByTestId("visitor-panes");
    expect(datos.parentElement).toBe(rejilla);
    expect(ajustador.parentElement).toBe(rejilla);
  });

  it("la conversacion, las citas, los controles y la respuesta van despues de los dos, en ese orden", async () => {
    await abrir(OFRECE);

    const rejilla = screen.getByTestId("visitor-panes");
    const debajo = ["block-transcript", "block-citations", "block-controls", "block-trace"].map(
      (id) => screen.getByTestId(id),
    );
    for (const bloque of debajo) {
      expect(rejilla.contains(bloque)).toBe(false);
      expect(antes(panelDelAjustador(), bloque)).toBe(true);
      expect(antes(screen.getByTestId("visitor-data"), bloque)).toBe(true);
    }
    debajo.slice(1).forEach((bloque, indice) => {
      const previo = debajo.at(indice);
      expect(previo !== undefined && antes(previo, bloque)).toBe(true);
    });
    // Las reglas ya no estan abajo: subieron junto a los datos.
    expect(rejilla.contains(screen.getByTestId("block-rule"))).toBe(true);
  });

  it("en escritorio: 7/12 para el ajustador a la izquierda y 5/12 para los datos a la derecha, alineados arriba", async () => {
    await abrir(OFRECE);

    const rejilla = screen.getByTestId("visitor-panes").className;
    expect(rejilla).toContain("grid");
    expect(rejilla).toContain("desktop:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]");
    expect(rejilla).toContain("desktop:items-start");
    // Por debajo de `desktop` no hay columnas: una sola, con el orden del documento.
    expect(rejilla.split(/\s+/).filter((clase) => clase.startsWith("grid-cols"))).toEqual([]);

    const ajustador = panelDelAjustador().className;
    expect(ajustador).toContain("desktop:col-start-1");
    expect(ajustador).toContain("desktop:row-start-1");
    const datos = screen.getByTestId("visitor-data").className;
    expect(datos).toContain("desktop:col-start-2");
    expect(datos).toContain("desktop:row-start-1");
    // El orden visual lo pone la rejilla, no un `order` que separe el orden del teclado.
    for (const clases of [rejilla, ajustador, datos]) {
      expect(clases).not.toMatch(/(^|\s)(desktop:|max-desktop:)?order-/);
    }
  });

  it("la columna de los datos se queda a la vista: pegajosa bajo la cabecera, con alto maximo y desplazamiento propio", async () => {
    await abrir(OFRECE);

    const datos = screen.getByTestId("visitor-data");
    expect(datos.className).toContain("desktop:sticky");
    expect(datos.className).toContain("desktop:top-[4.5rem]");
    expect(datos.className).toContain("desktop:max-h-[calc(100dvh_-_5.5rem)]");
    expect(datos.className).toContain("desktop:overflow-y-auto");
    // Una region que se desplaza se alcanza con el teclado (`scrollable-region-focusable`), y
    // tiene nombre.
    expect(datos.getAttribute("tabindex")).toBe("0");
    expect(datos.getAttribute("role")).toBe("group");
    expect(datos.getAttribute("aria-label")).toBe(t("visitor.block.fields"));
  });

  it("el panel del ajustador lleva el color de la marca con tokens: raya, titulo y marcas", async () => {
    await abrir(OFRECE);

    const clasesDe = (elemento: HTMLElement) => elemento.className.split(/\s+/);
    const panel = panelDelAjustador();
    expect(clasesDe(panel)).toEqual(
      expect.arrayContaining(["border-l-4", "border-l-brand", "bg-surface"]),
    );
    // Sin tinte de fondo: un campo sobre un fondo con tinte de cobre baja el borde del campo de
    // los 3 a 1 que pide un control (2,6 a 1 medido en oscuro).
    expect(clasesDe(panel)).not.toContain("bg-selected");
    // El titulo va en el token de la marca --la tinta en modo claro, nunca el cobre sobre claro--.
    const titulo = within(panel).getByRole("heading", { level: 2 });
    expect(clasesDe(titulo)).toContain("text-brand");
    expect(clasesDe(titulo)).not.toContain("text-fg");
    for (const marca of within(panel).getAllByTestId("step-mark")) {
      expect(clasesDe(marca)).toEqual(expect.arrayContaining(["bg-brand", "text-on-brand"]));
      // La marca es decoracion: el lector de pantalla lee el titulo del paso.
      expect(marca.getAttribute("aria-hidden")).toBe("true");
    }
  });

  it("los datos van en una superficie neutra distinta a la del panel, sin nada de la marca", async () => {
    await abrir(OFRECE);

    const clasesDe = (elemento: HTMLElement) => elemento.className.split(/\s+/);
    for (const bloque of [panelDeDatos(), screen.getByTestId("block-rule")]) {
      expect(clasesDe(bloque)).toContain("bg-surface-alt");
      expect(clasesDe(bloque)).not.toContain("bg-surface");
      expect(bloque.className).not.toMatch(/brand|selected/);
    }
    // El panel del ajustador, en cambio, usa la superficie normal: es la que distingue a los dos.
    expect(clasesDe(panelDelAjustador())).not.toContain("bg-surface-alt");
  });

  it("ningun elemento de la pantalla escribe un color a mano ni usa el cobre como letra", async () => {
    await abrir(OFRECE);

    for (const elemento of screen.getByTestId("visitor-case").querySelectorAll("[class]")) {
      const clases = elemento.getAttribute("class") ?? "";
      expect(clases, clases).not.toMatch(/copper|\[#|\[rgb|\[hsl|\[oklch|text-\[color/);
    }
  });

  it("dos pasos numerados: revisa (1) y decide (2), y el formulario va dentro del segundo", async () => {
    await abrir(OFRECE);

    const panel = panelDelAjustador();
    expect(
      within(panel)
        .getAllByTestId("step-mark")
        .map((marca) => marca.textContent),
    ).toEqual(["1", "2"]);
    const revisa = screen.getByTestId("visitor-triage");
    const decide = screen.getByTestId("visitor-decision");
    expect(
      within(revisa).getByRole("heading", { level: 3, name: t("visitor.triage.title") }),
    ).toBeTruthy();
    expect(
      within(decide).getByRole("heading", { level: 3, name: t("visitor.decision.title") }),
    ).toBeTruthy();
    expect(decide.contains(screen.getByTestId("decision-form"))).toBe(true);
    expect(antes(revisa, decide)).toBe(true);
    // La introduccion del panel dice que hacer; la del paso 1, para que sirve anotar.
    expect(panel.textContent).toContain(t("visitor.decide_intro"));
    expect(revisa.textContent).toContain(t("visitor.triage.intro"));
  });

  it("sin que el servidor ofrezca anotar, el paso de decidir va solo y sin numero", async () => {
    await abrir({ can_annotate_triage: false, triage_note: null });

    const panel = panelDelAjustador();
    expect(within(panel).queryByTestId("step-mark")).toBeNull();
    expect(screen.queryByTestId("visitor-triage")).toBeNull();
    expect(
      within(panel).getByRole("heading", { level: 3, name: t("visitor.decision.title") }),
    ).toBeTruthy();
    expect(within(panel).getByTestId("decision-form")).toBeTruthy();
  });

  it("un caso que espera al asegurado: el paso de decidir dice por que no se decide, dentro del panel", async () => {
    await abrir({ ...OFRECE, state: "awaiting_insured", available_actions: [] });

    const panel = panelDelAjustador();
    expect(within(panel).getByTestId("visitor-no-actions").textContent).toBe(
      t("inbox.decision.none_awaiting"),
    );
    expect(within(panel).queryByTestId("decision-form")).toBeNull();
    // Se anota (paso 1) y se lee por que no se decide (paso 2).
    expect(
      within(panel)
        .getAllByTestId("step-mark")
        .map((marca) => marca.textContent),
    ).toEqual(["1", "2"]);
    // Sin botones no se invita a decidir.
    expect(panel.textContent).not.toContain(t("visitor.decide_intro"));
  });

  it("mientras la agente evalua no hay panel del ajustador, y los datos quedan solos, sin pegarse a nada", async () => {
    await abrir({ state: "deciding", derivation_reason: null, available_actions: [] });

    expect(screen.queryByRole("region", { name: t("visitor.adjuster.title") })).toBeNull();
    const datos = screen.getByTestId("visitor-data");
    expect(datos.contains(screen.getByTestId("block-fields"))).toBe(true);
    // Sin otra columna no hay nada a lo que pegarse: ni rejilla, ni pegajosa, ni foco.
    expect(screen.getByTestId("visitor-panes").className).not.toContain("grid");
    expect(datos.className).not.toContain("sticky");
    expect(datos.hasAttribute("tabindex")).toBe(false);
    // Y no se estiran a los 76 rem: conservan la columna de lectura.
    expect(datos.className).toContain("max-w-[52rem]");
  });

  it("decidido el caso no hay paso de decidir ni marcas, y lo que anoto se lee en el panel", async () => {
    decidido.mockResolvedValue({ ok: true, value: { decision_id: "d1", resolution: "approved" } });
    pedido.mockResolvedValueOnce({ ok: true, value: caso(OFRECE) }).mockResolvedValueOnce({
      ok: true,
      value: caso({
        state: "closed",
        resolution: "approved",
        available_actions: [],
        can_annotate_triage: false,
        triage_note: { claim_amount: 2500, coverage_disputed: false, fraud_suspected: true },
      }),
    });
    dibujar();
    await screen.findByTestId("visitor-triage-form");

    await userEvent.type(screen.getByLabelText(t("inbox.decision.comment_label")), "Lo apruebo");
    await userEvent.click(screen.getByRole("button", { name: t("inbox.decision.approve") }));
    await screen.findByTestId("visitor-resolution");

    const panel = panelDelAjustador();
    expect(within(panel).getByTestId("visitor-triage-readonly")).toBeTruthy();
    expect(screen.queryByTestId("visitor-decision")).toBeNull();
    expect(screen.queryByTestId("step-mark")).toBeNull();
    // Los datos siguen a la vista, y siguen antes que el panel.
    expect(antes(screen.getByTestId("visitor-data"), panel)).toBe(true);
  });

  it("en ingles los dos paneles se leen en ingles", async () => {
    const en = createTranslate("en");
    pedido.mockResolvedValue({ ok: true, value: caso(OFRECE) });
    renderWithProviders(
      <VisitorCasePage token="un-token" conversationHref={() => "/"} renderRejected={rechazo} />,
      "en",
    );
    await screen.findByTestId("visitor-case");

    expect(screen.getByRole("region", { name: en("visitor.adjuster.title") })).toBeTruthy();
    expect(screen.getByRole("region", { name: en("visitor.block.fields") })).toBeTruthy();
    expect(
      screen.getByRole("heading", { level: 3, name: en("visitor.decision.title") }),
    ).toBeTruthy();
    expect(screen.getByTestId("visitor-case").textContent).not.toContain(en("inbox.block.fields"));
  });
});

describe("lo que anota el personal para las reglas", () => {
  it("la pantalla del personal no se dibuja aqui, aunque el cable trajera lo mismo", async () => {
    // El servidor no le manda al visitante la nota del personal (`triage_note` en null y
    // `can_annotate_triage` en false), y lo que el cable traiga lo dibuja la pantalla
    // guiada del visitante, nunca el formulario del personal ni su lectura.
    pedido.mockResolvedValue({
      ok: true,
      value: caso({
        can_annotate_triage: true,
        triage_note: { claim_amount: 7318, coverage_disputed: true, fraud_suspected: true },
      }),
    });
    dibujar();

    const pantalla = await screen.findByTestId("visitor-case");

    expect(screen.queryByTestId("block-triage")).toBeNull();
    expect(screen.queryByTestId("triage-form")).toBeNull();
    expect(pantalla.textContent).not.toContain(t("inbox.triage.title"));
    expect(pantalla.textContent).not.toContain(t("inbox.triage.intro"));
  });

  it("sin que el servidor ofrezca anotar y sin nota del visitante, no hay bloque", async () => {
    // Lo que manda el servidor cuando la nota es del personal, el caso esta cerrado o el
    // visitante llego al tope: ni formulario ni lectura, ni un hueco donde estaban.
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ can_annotate_triage: false, triage_note: null, triage_amount_steps: [] }),
    });
    dibujar();

    await screen.findByTestId("visitor-case");

    expect(screen.queryByTestId("visitor-triage")).toBeNull();
    expect(screen.queryByText(t("visitor.triage.title"))).toBeNull();
  });
});

// El visitante que hace de ajustador anota, con ayuda, lo que revisaria un ajustador
// (2026-10-13). Lo que se pinta lo decide el servidor; aqui se prueba la pantalla entera.
describe("anotar antes de decidir", () => {
  const OFRECE: Partial<CaseDetailOut> = {
    can_annotate_triage: true,
    triage_amount_steps: [1000, 10000],
  };
  const RESPUESTA: TriageNoteOut = {
    receipt_id: "rec-1",
    rule_category: "referral",
    fired_rules: ["SUN-R-03", "SUN-R-07"],
  };

  const bloque = () => within(screen.getByTestId("visitor-triage"));

  beforeEach(() => {
    pedido.mockResolvedValue({ ok: true, value: caso(OFRECE) });
    anotado.mockResolvedValue({ ok: true, value: RESPUESTA });
  });

  it("se pinta dentro del panel del ajustador, antes del formulario de la decision", async () => {
    dibujar();
    const triage = await screen.findByTestId("visitor-triage");

    const seccion = screen.getByRole("region", { name: t("visitor.adjuster.title") });
    expect(seccion.contains(triage)).toBe(true);
    expect(seccion.textContent).toContain(t("visitor.decide_intro"));
    expect(seccion.contains(screen.getByTestId("decision-form"))).toBe(true);
    expect(
      triage.compareDocumentPosition(screen.getByTestId("decision-form")) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // Y trae la ayuda de esta aseguradora, con las cifras del servidor.
    expect(screen.getByTestId("visitor-triage-examples").textContent).toContain(
      formatPesos(20000, "es"),
    );
  });

  it("no dice una palabra de la jerga del sistema (U-07)", async () => {
    dibujar();
    const pantalla = await screen.findByTestId("visitor-case");

    for (const jerga of ["bandeja", "derivado", "cola", "inbox", "tenant", "triage", "triaje"]) {
      expect(pantalla.textContent.toLowerCase()).not.toContain(jerga);
    }
  });

  it("guarda con una clave por intento, vuelve a leer el caso y el bloque de las reglas cambia", async () => {
    pedido
      .mockResolvedValueOnce({
        ok: true,
        value: caso({ ...OFRECE, rule_category: "standard_review", fired_rules: ["SUN-R-10"] }),
      })
      .mockResolvedValue({
        ok: true,
        value: caso({
          ...OFRECE,
          rule_category: "referral",
          fired_rules: ["SUN-R-03", "SUN-R-07"],
          triage_note: { claim_amount: 2500, coverage_disputed: null, fraud_suspected: true },
        }),
      });
    dibujar();
    await screen.findByTestId("visitor-triage");
    expect(screen.getByTestId("rule-reference").textContent).toBe(
      t("inbox.rule.reference", { rules: "SUN-R-10" }),
    );

    await userEvent.type(screen.getByLabelText(t("visitor.triage.amount_label")), "2500000");
    await userEvent.selectOptions(screen.getByLabelText(t("visitor.triage.fraud_label")), "yes");
    await userEvent.click(screen.getByRole("button", { name: t("visitor.triage.save") }));

    expect(anotado).toHaveBeenCalledTimes(1);
    expect(anotado).toHaveBeenCalledWith(
      "una-aseguradora",
      "case-1",
      { claim_amount: 2500, coverage_disputed: null, fraud_suspected: true },
      expect.stringMatching(/^visitor-note-/),
    );
    // El caso se volvio a leer y el bloque de las reglas cuenta lo nuevo --el que vive en la
    // columna de los datos, a la vista mientras se anota--.
    expect(pedido).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("rule-reference").textContent).toBe(
      t("inbox.rule.reference", { rules: "SUN-R-03, SUN-R-07" }),
    );
    expect(
      within(screen.getByTestId("visitor-data")).getByTestId("rule-reference").textContent,
    ).toBe(t("inbox.rule.reference", { rules: "SUN-R-03, SUN-R-07" }));
    // Y el bloque de anotar dice, en su sitio, como quedo clasificado.
    const estado = bloque().getByTestId("visitor-triage-result");
    expect(estado.textContent).toContain(t("visitor.triage.result"));
    expect(estado.textContent).toContain(t("inbox.rule.reason.referral"));
    // El formulario sigue ahi con lo escrito: no se remonto al volver a leer.
    expect(screen.getByLabelText<HTMLInputElement>(t("visitor.triage.amount_label")).value).toBe(
      "2500000",
    );
  });

  it("dos guardados llevan dos claves distintas: uno por intento", async () => {
    dibujar();
    await screen.findByTestId("visitor-triage");

    await userEvent.click(screen.getByRole("button", { name: t("visitor.triage.save") }));
    await userEvent.selectOptions(screen.getByLabelText(t("visitor.triage.fraud_label")), "no");
    await userEvent.click(screen.getByRole("button", { name: t("visitor.triage.save") }));

    expect(anotado).toHaveBeenCalledTimes(2);
    expect(anotado.mock.calls[0]?.[3]).not.toBe(anotado.mock.calls[1]?.[3]);
  });

  it("si guardo lo que ya estaba no vuelve a leer el caso ni dice que evaluo otra vez", async () => {
    anotado.mockResolvedValue({
      ok: true,
      value: { receipt_id: null, rule_category: "standard_review", fired_rules: ["SUN-R-10"] },
    });
    dibujar();
    await screen.findByTestId("visitor-triage");

    await userEvent.click(screen.getByRole("button", { name: t("visitor.triage.save") }));

    expect(pedido).toHaveBeenCalledTimes(1);
    const estado = bloque().getByTestId("visitor-triage-result");
    expect(estado.textContent).not.toContain(t("visitor.triage.result"));
    expect(estado.textContent).toContain(t("inbox.rule.reason.standard_review"));
  });

  it("si el tope se alcanzo (409), lo dice, vuelve a leer y deja de ofrecer el formulario", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    anotado.mockResolvedValue({
      ok: false,
      problem: { code: "conflict_state", message: (tt) => tt("problem.conflict_state") },
    });
    pedido.mockResolvedValueOnce({ ok: true, value: caso(OFRECE) }).mockResolvedValue({
      ok: true,
      value: caso({
        can_annotate_triage: false,
        triage_amount_steps: [],
        triage_note: { claim_amount: null, coverage_disputed: null, fraud_suspected: true },
      }),
    });
    dibujar();
    await screen.findByTestId("visitor-triage-form");

    await userEvent.selectOptions(screen.getByLabelText(t("visitor.triage.fraud_label")), "yes");
    await userEvent.click(screen.getByRole("button", { name: t("visitor.triage.save") }));

    expect((await screen.findByTestId("visitor-triage-problem")).textContent).toBe(
      t("visitor.triage.limit"),
    );
    expect(pedido).toHaveBeenCalledTimes(2);
    // Lo que anoto se sigue leyendo, y el formulario ya no esta.
    expect(screen.queryByTestId("visitor-triage-form")).toBeNull();
    expect(screen.getByTestId("visitor-triage-fraud-value").textContent).toBe(
      t("inbox.triage.answer_yes"),
    );
    // La decision, que es otra cosa, sigue disponible.
    expect(screen.getByTestId("decision-form")).toBeTruthy();
  });

  it("si el enlace vencio mientras anotaba, lo dice con su propia frase y lo escrito sigue", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    anotado.mockResolvedValue({
      ok: false,
      problem: { code: "link_invalid", message: (tt) => tt("problem.link_invalid") },
    });
    pedido.mockResolvedValueOnce({ ok: true, value: caso(OFRECE) }).mockResolvedValue({
      ok: false,
      problem: { code: "link_invalid", message: (tt) => tt("problem.link_invalid") },
    });
    dibujar();
    await screen.findByTestId("visitor-triage-form");

    await userEvent.type(screen.getByLabelText(t("visitor.triage.amount_label")), "800000");
    await userEvent.click(screen.getByRole("button", { name: t("visitor.triage.save") }));

    expect((await screen.findByTestId("visitor-triage-problem")).textContent).toBe(
      t("visitor.triage.expired"),
    );
    expect(screen.getByLabelText<HTMLInputElement>(t("visitor.triage.amount_label")).value).toBe(
      "800000",
    );
  });

  it("si el enlace sigue vigente, un rechazo no se llama vencimiento", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    anotado.mockResolvedValue({
      ok: false,
      problem: { code: "not_found", message: (tt) => tt("problem.not_found") },
    });
    dibujar();
    await screen.findByTestId("visitor-triage-form");

    await userEvent.click(screen.getByRole("button", { name: t("visitor.triage.save") }));

    const aviso = await screen.findByTestId("visitor-triage-problem");
    expect(aviso.textContent).toBe(t("problem.not_found"));
    expect(aviso.textContent).not.toBe(t("visitor.triage.expired"));
  });

  it("un caso que espera al asegurado no se decide pero si se anota, aparte", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ ...OFRECE, state: "awaiting_insured", available_actions: [] }),
    });
    dibujar();

    await screen.findByTestId("visitor-triage-form");

    expect(screen.queryByTestId("decision-form")).toBeNull();
    expect(screen.getByTestId("visitor-no-actions").textContent).toBe(
      t("inbox.decision.none_awaiting"),
    );
  });

  it("decidido el caso, lo que anoto se sigue leyendo, sin formulario", async () => {
    decidido.mockResolvedValue({ ok: true, value: { decision_id: "d1", resolution: "approved" } });
    pedido.mockResolvedValueOnce({ ok: true, value: caso(OFRECE) }).mockResolvedValueOnce({
      ok: true,
      value: caso({
        state: "closed",
        resolution: "approved",
        available_actions: [],
        can_annotate_triage: false,
        triage_note: { claim_amount: 2500, coverage_disputed: false, fraud_suspected: true },
      }),
    });
    dibujar();
    await screen.findByTestId("visitor-triage-form");

    await userEvent.type(screen.getByLabelText(t("inbox.decision.comment_label")), "Lo apruebo");
    await userEvent.click(screen.getByRole("button", { name: t("inbox.decision.approve") }));

    expect(await screen.findByTestId("visitor-resolution")).toBeTruthy();
    expect(screen.queryByTestId("visitor-triage-form")).toBeNull();
    expect(screen.getByTestId("visitor-triage-amount-value").textContent).toBe(
      formatPesos(2500, "es"),
    );
  });

  it("en ingles el bloque se lee en ingles", async () => {
    const en = createTranslate("en");
    renderWithProviders(
      <VisitorCasePage token="un-token" conversationHref={() => "/"} renderRejected={rechazo} />,
      "en",
    );

    expect((await screen.findByTestId("visitor-triage")).textContent).toContain(
      en("visitor.triage.title"),
    );
  });
});
