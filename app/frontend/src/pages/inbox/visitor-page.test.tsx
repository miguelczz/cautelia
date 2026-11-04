import { act, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../app/testing";
import type {
  AdjusterRunOut,
  CaseDetailOut,
  InboxResult,
  RedeemOut,
} from "../../shared/api-client/inbox";
import type { ProblemView } from "../../shared/api-client/problems";
import { createTranslate } from "../../shared/i18n/translate";
import { statusKindForCaseProblem } from "../status/case-link-status";
import { StatusPage } from "../status/status-page";
import { callMemory } from "../voice/call-memory";
import type { WireFrame } from "../voice/voice-events";
import { VisitorCasePage, type CaseSession } from "./visitor-page";

// La pantalla propia del visitante (BR5.1 a BR5.7). Sin jerga del sistema: quien lee
// esto es la persona que reporto.

const canjeado = vi.hoisted(() => vi.fn<(token: string) => Promise<InboxResult<RedeemOut>>>());
const pedido = vi.hoisted(() =>
  vi.fn<(tenantId: string, caseId: string) => Promise<InboxResult<CaseDetailOut>>>(),
);

vi.mock("../../shared/api-client/inbox", async (original) => {
  const real = await original<typeof import("../../shared/api-client/inbox")>();
  return {
    ...real,
    redeemLink: canjeado,
    caseDetail: pedido,
  };
});

const t = createTranslate("es");

const SESION: RedeemOut = {
  case_id: "case-1",
  tenant: "una-aseguradora",
  access: "view_and_decide",
  expires_at: "2026-09-28T13:00:00+00:00",
};

/**
 * La corrida del ajustador de IA ya decidida, con los seis pasos y fuentes de cada tipo: una
 * clausula, dos reglas, la poliza, el reporte y una pagina externa. El identificador versionado
 * de una regla viaja en la fuente (`STO-R-12`) y la pantalla **no** lo enseña.
 */
function corrida(extra: Partial<AdjusterRunOut> = {}): AdjusterRunOut {
  return {
    status: "decided",
    attempt: 1,
    steps: [
      {
        id: "case_read",
        title_key: "adjuster.step.case_read.title",
        text: "Lei el reporte del caso CA-1: tiene 5 datos anotados.",
        sources: [{ kind: "case", ref: "CA-1", label: "Reporte del caso CA-1" }],
      },
      {
        id: "policy_read",
        title_key: "adjuster.step.policy_read.title",
        text: "Lei la poliza POL-1: esta vigente hoy.",
        sources: [{ kind: "policy", ref: "POL-1", label: "Póliza POL-1" }],
      },
      {
        id: "clauses",
        title_key: "adjuster.step.clauses.title",
        text: "Busque en la poliza y encontre 1 clausula.",
        sources: [{ kind: "clause", ref: "D.INS.COLLISION", label: "Parte D - Daños propios" }],
      },
      {
        id: "rules",
        title_key: "adjuster.step.rules.title",
        text: "Las reglas de la aseguradora no marcaron nada especial.",
        sources: [
          { kind: "rule", ref: "STO-R-12@1", label: "STO-R-12" },
          { kind: "rule", ref: "STO-R-15@2", label: "STO-R-15" },
        ],
      },
      {
        id: "vehicle_value",
        title_key: "adjuster.step.vehicle_value.title",
        text: "Busque el valor de referencia del vehiculo.",
        sources: [
          {
            kind: "web",
            ref: "https://guia.example.com/valores",
            label: "Guía de valores",
            url: "https://guia.example.com/valores",
          },
        ],
      },
      { id: "decision", title_key: "adjuster.step.decision.title", text: "Apruebo.", sources: [] },
    ],
    decision: "approve",
    headline: "Aprobado: el choque esta cubierto",
    explanation:
      "El choque esta cubierto por la clausula de dano propio.\nLa poliza estaba vigente.",
    searches_used: 1,
    updated_at: "2026-09-28T12:05:00+00:00",
    ...extra,
  };
}

/** Un caso que el ajustador de IA ya decidio: cerrado, aprobado y sin nada que decidir. */
const DECIDIDO_POR_IA: Partial<CaseDetailOut> = {
  state: "closed",
  resolution: "approved",
  derivation_reason: "rule",
  available_actions: [],
  can_correct_fields: false,
  adjuster: corrida(),
  explanation: {
    asked: "none",
    cited: "none",
    rule: "present",
    decided_by: "present",
    decided_at: "present",
    decided_by_kind: "adjuster_ai",
    decided_by_id: null,
    decided_at_iso: "2026-09-28T12:05:00+00:00",
  },
};

/** El caso derivado mientras el ajustador de IA trabaja: `pasos` ya llegaron de los seis. */
function enCurso(pasos: number): Partial<CaseDetailOut> {
  return {
    state: "derived",
    available_actions: [],
    adjuster: corrida({
      status: "running",
      decision: null,
      headline: null,
      explanation: null,
      steps: corrida().steps?.slice(0, pasos) ?? [],
    }),
  };
}

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
    available_actions: [],
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
    // Por omision el caso ya lo decidio el ajustador de IA: es lo que lee quien abre su caso.
    ...DECIDIDO_POR_IA,
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
        control_findings: ["attachment_missing"],
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
    expect(controles.textContent).toContain(t("inbox.controls.finding.attachment_missing"));
    expect(controles.textContent).not.toContain("attachment_missing");
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
    adjuster: null,
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

  it("sin ajustador que contar, el panel dice el estado del caso y no es el del ajustador", async () => {
    pedido.mockResolvedValue({ ok: true, value: caso(cierreDirecto) });
    dibujar();
    const panel = await screen.findByTestId("visitor-adjuster");

    expect(within(panel).getByRole("heading", { level: 2 }).textContent).toBe(
      t("visitor.status.title"),
    );
    expect(panel.textContent).not.toContain(t("adjuster.panel.title"));
    expect(panel.textContent).not.toContain(t("adjuster.panel.title_pending"));
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
          adjuster: null,
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

  it("un caso derivado sigue contando lo de siempre, con el panel del ajustador y sin botones", async () => {
    // El control positivo: sin el, las frases nuevas podrian estar pintandose siempre.
    pedido.mockResolvedValue({ ok: true, value: caso(DECIDIDO_POR_IA) });
    dibujar();
    await screen.findByTestId("visitor-case");

    expect(screen.getByTestId("visitor-intro").textContent).toBe(t("visitor.intro"));
    expect(screen.getByTestId("adjuster-panel")).toBeTruthy();
    expect(screen.queryByTestId("decision-form")).toBeNull();
  });
});

// Mientras la agente evalua el caso, la pagina lo vuelve a leer: cada 3 s, como mucho 10
// veces, y se detiene al salir de revision, al tope y al dejar la pantalla (2026-10-13).
describe("«Ver mi caso» abierto mientras la agente evalua el caso", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  const EN_REVISION = () =>
    caso({ state: "deciding", derivation_reason: null, available_actions: [], adjuster: null });

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
    expect(screen.queryByTestId("adjuster-panel")).toBeNull();
    expect(pedido).toHaveBeenCalledTimes(1);
    await pasar(2999);
    expect(pedido).toHaveBeenCalledTimes(1);
    await pasar(1);

    expect(pedido).toHaveBeenCalledTimes(2);
    expect(pedido).toHaveBeenLastCalledWith("una-aseguradora", "case-1");
    expect(screen.getByTestId("visitor-intro").textContent).toBe(t("visitor.intro"));
    expect(screen.getByTestId("adjuster-panel")).toBeTruthy();
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
        adjuster: null,
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

// El visitante ya no decide ni anota (plan 09, fase 5, 2026-11-04): las rutas le devuelven 403 y la
// pantalla ya no las llama. Lo que lee es como decidio el ajustador de IA.
describe("el visitante no decide ni anota", () => {
  it("aunque el cable trajera acciones, no hay formulario ni botones de decision", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ state: "derived", adjuster: null, available_actions: ["approve", "reject"] }),
    });
    dibujar();
    await screen.findByTestId("visitor-case");

    expect(screen.queryByTestId("decision-form")).toBeNull();
    expect(screen.queryByRole("button", { name: t("inbox.decision.approve") })).toBeNull();
    expect(screen.queryByRole("button", { name: t("inbox.decision.reject") })).toBeNull();
  });

  it("aunque el servidor ofreciera anotar, no hay formulario de anotaciones ni nota del visitante", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ can_annotate_triage: true, triage_amount_steps: [1000, 10000] }),
    });
    dibujar();
    await screen.findByTestId("visitor-case");

    expect(screen.queryByTestId("visitor-triage")).toBeNull();
    expect(screen.queryByRole("button", { name: /guardar/i })).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("un caso que espera al asegurado lo dice, sin panel del ajustador ni formulario", async () => {
    pedido.mockResolvedValue({
      ok: true,
      value: caso({ state: "awaiting_insured", available_actions: [], adjuster: null }),
    });
    dibujar();
    await screen.findByTestId("visitor-case");

    expect(screen.queryByTestId("decision-form")).toBeNull();
    expect(screen.queryByTestId("adjuster-panel")).toBeNull();
    expect(screen.getByTestId("visitor-no-actions").textContent).toBe(
      t("inbox.decision.none_awaiting"),
    );
  });
});

describe("el panel «Cómo decidió el ajustador»", () => {
  const panel = () => screen.getByRole("region", { name: t("adjuster.panel.title") });

  async function abrir(extra: Partial<CaseDetailOut> = {}) {
    pedido.mockResolvedValue({ ok: true, value: caso(extra) });
    dibujar();
    await screen.findByTestId("visitor-case");
  }

  it("decidido: la decision con su etiqueta, el titular, la explicacion y el aviso de que lo escribio una IA", async () => {
    await abrir();

    const region = panel();
    expect(within(region).getByRole("heading", { level: 2 }).textContent).toBe(
      t("adjuster.panel.title"),
    );
    // Dice quien decidio, con las palabras «ajustador de IA»: nunca una persona.
    expect(within(region).getByTestId("adjuster-status").textContent).toBe(
      t("adjuster.panel.decided"),
    );
    expect(within(region).getByTestId("adjuster-decision-label").textContent).toBe(
      t("case.resolution.approved"),
    );
    expect(within(region).getByTestId("adjuster-headline").textContent).toBe(
      "Aprobado: el choque esta cubierto",
    );
    expect(within(region).getByTestId("adjuster-explanation").textContent).toContain(
      "La poliza estaba vigente.",
    );
    expect(within(region).getByTestId("adjuster-ai-notice").textContent).toBe(
      t("adjuster.panel.ai_notice"),
    );
    // Lo que no se puede hacer aqui: ningun control.
    expect(within(region).queryAllByRole("button")).toEqual([]);
  });

  it.each([
    ["approve", "approved", (tt: typeof t) => tt("case.resolution.approved")],
    ["reject", "rejected", (tt: typeof t) => tt("case.resolution.rejected")],
    ["mark_sent", "sent_to_insurer", (tt: typeof t) => tt("case.resolution.sent_to_insurer")],
  ] as const)(
    "la etiqueta de la decision %s es la de su resolucion",
    async (accion, resolucion, etiqueta) => {
      await abrir({ adjuster: corrida({ decision: accion }), resolution: resolucion });

      expect(screen.getByTestId("adjuster-decision-label").textContent).toBe(etiqueta(t));
    },
  );

  it("los seis pasos, en una lista ordenada con su titular y su marca numerica", async () => {
    await abrir();

    const lista = within(panel()).getByRole("list", { name: t("adjuster.panel.steps") });
    expect(lista.tagName).toBe("OL");
    // El nombre accesible no cuenta la marca numerica, que va oculta para el lector de pantalla.
    const titulos = within(lista).getAllByRole("heading", { level: 3 });
    expect(titulos).toHaveLength(6);
    [
      t("adjuster.step.case_read.title"),
      t("adjuster.step.policy_read.title"),
      t("adjuster.step.clauses.title"),
      t("adjuster.step.rules.title"),
      t("adjuster.step.vehicle_value.title"),
      t("adjuster.step.decision.title"),
    ].forEach((nombre, indice) => {
      expect(within(lista).getByRole("heading", { level: 3, name: nombre })).toBe(
        titulos.at(indice),
      );
    });
    expect(
      within(lista)
        .getAllByTestId("step-mark")
        .map((marca) => marca.textContent),
    ).toEqual(["1", "2", "3", "4", "5", "6"]);
    expect(screen.getByTestId("adjuster-step-case_read").textContent).toContain(
      "Lei el reporte del caso CA-1",
    );
  });

  it("las fuentes se leen con nombre legible: la clausula con su cita, la regla numerada, la poliza y la pagina externa", async () => {
    await abrir();

    const clausulas = within(screen.getByTestId("adjuster-step-clauses"));
    const fuenteClausula = clausulas.getByRole("listitem");
    expect(fuenteClausula.textContent).toContain(t("adjuster.source.kind.clause"));
    expect(fuenteClausula.textContent).toContain("Parte D - Daños propios");
    expect(fuenteClausula.textContent).toContain("D.INS.COLLISION");

    const reglas = within(screen.getByTestId("adjuster-step-rules")).getAllByRole("listitem");
    expect(reglas.map((regla) => regla.textContent)).toEqual([
      t("adjuster.source.rule", { number: 1 }),
      t("adjuster.source.rule", { number: 2 }),
    ]);

    expect(
      within(screen.getByTestId("adjuster-step-policy_read")).getByRole("listitem").textContent,
    ).toBe("Póliza POL-1");

    const enlace = within(screen.getByTestId("adjuster-step-vehicle_value")).getByRole("link", {
      name: /Guía de valores/,
    });
    expect(enlace.getAttribute("href")).toBe("https://guia.example.com/valores");
    expect(enlace.getAttribute("target")).toBe("_blank");
    expect(enlace.getAttribute("rel")).toContain("noopener");
    // Quien usa lector de pantalla oye que se abre en otra pestana.
    expect(enlace.textContent).toContain(t("adjuster.source.new_tab"));
  });

  it("una pagina que no es https se nombra pero no se convierte en enlace", async () => {
    const base = corrida();
    await abrir({
      adjuster: corrida({
        steps: (base.steps ?? []).map((paso) =>
          paso.id === "vehicle_value"
            ? {
                ...paso,
                sources: [
                  {
                    kind: "web" as const,
                    ref: "javascript:alert(1)",
                    label: "Pagina rara",
                    url: "javascript:alert(1)",
                  },
                ],
              }
            : paso,
        ),
      }),
    });

    const paso = within(screen.getByTestId("adjuster-step-vehicle_value"));
    expect(paso.queryByRole("link")).toBeNull();
    expect(paso.getByText("Pagina rara")).toBeTruthy();
  });

  it("no ensena identificadores de regla, ni el aviso de la IA habla de una persona", async () => {
    await abrir();

    const texto = panel().textContent;
    expect(texto).not.toMatch(/STO-R|@\d|FNOL|tenant|endoso/i);
    // El ajustador de IA nunca se presenta como una persona.
    expect(texto).not.toMatch(/una persona|un humano|person/i);
  });

  it("al decidirse el caso ofrece volver a la conversacion", async () => {
    await abrir();

    const volver = screen.getByRole("link", { name: t("action.back_to_conversation") });
    expect(volver.getAttribute("href")).toBe("/t/una-aseguradora/chat");
  });

  it("en curso: los pasos que ya llegaron, el lugar de los que faltan y una sola linea que anuncia el avance", async () => {
    await abrir(enCurso(2));

    const region = screen.getByRole("region", { name: t("adjuster.panel.title_pending") });
    expect(region.getAttribute("data-status")).toBe("running");
    const estado = within(region).getByTestId("adjuster-status");
    expect(estado.textContent).toBe(t("adjuster.panel.running", { done: 2, total: 6 }));
    // La unica region viva del panel: cortes de a una frase, sin repetir lo ya dicho.
    expect(estado.getAttribute("aria-live")).toBe("polite");
    expect(estado.getAttribute("aria-atomic")).toBe("true");
    expect(region.querySelectorAll("[aria-live]")).toHaveLength(1);

    expect(within(region).getAllByTestId("step-mark")).toHaveLength(2);
    // Los cuatro que faltan: su titular y su esqueleto, ocultos para el lector de pantalla.
    const faltan = within(region).getAllByTestId("adjuster-step-pending");
    expect(faltan).toHaveLength(4);
    for (const fila of faltan) {
      expect(fila.getAttribute("aria-hidden")).toBe("true");
    }
    expect(faltan[0]?.textContent).toContain(t("adjuster.step.clauses.title"));
    // Ni decision ni explicacion antes de tiempo.
    expect(within(region).queryByTestId("adjuster-decision")).toBeNull();
    expect(screen.queryByRole("link", { name: t("action.back_to_conversation") })).toBeNull();
  });

  it("el esqueleto solo pulsa si la persona no pidio menos movimiento", async () => {
    await abrir(enCurso(0));

    const esqueleto = screen
      .getByTestId("adjuster-panel")
      .querySelectorAll('[data-testid="adjuster-step-pending"] div');
    expect(esqueleto.length).toBeGreaterThan(0);
    for (const bloque of esqueleto) {
      const clases = bloque.className.split(/\s+/);
      expect(clases).toContain("motion-safe:animate-pulse");
      expect(clases).not.toContain("animate-pulse");
    }
  });

  it("el caso recien derivado, sin corrida todavia, ya se ve en curso: 0 de 6", async () => {
    await abrir({ state: "derived", adjuster: null, available_actions: [], resolution: null });

    const region = screen.getByRole("region", { name: t("adjuster.panel.title_pending") });
    expect(within(region).getByTestId("adjuster-status").textContent).toBe(
      t("adjuster.panel.running", { done: 0, total: 6 }),
    );
    expect(within(region).getAllByTestId("adjuster-step-pending")).toHaveLength(6);
  });

  it("en espera de cupo: lo dice, sin pasos ni decision", async () => {
    await abrir({
      state: "derived",
      resolution: null,
      adjuster: corrida({ status: "capped", decision: null, headline: null, explanation: null }),
    });

    const region = screen.getByRole("region", { name: t("adjuster.panel.title_pending") });
    expect(region.getAttribute("data-status")).toBe("capped");
    expect(within(region).getByTestId("adjuster-status").textContent).toBe(
      t("adjuster.panel.capped"),
    );
    expect(within(region).queryByTestId("adjuster-steps")).toBeNull();
    expect(within(region).queryByTestId("adjuster-decision")).toBeNull();
  });

  it("si fallo dice que sigue en revision: ni decision inventada, ni pasos, ni el motivo tecnico", async () => {
    await abrir({
      state: "derived",
      resolution: null,
      adjuster: corrida({
        status: "failed",
        // Aunque el cable trajera restos de lo que el modelo alcanzo a escribir, no se ensenan.
        decision: "approve",
        headline: "Aprobado por error",
        explanation: "timeout llamando al modelo",
      }),
    });

    const region = screen.getByRole("region", { name: t("adjuster.panel.title_pending") });
    expect(region.getAttribute("data-status")).toBe("failed");
    expect(within(region).getByTestId("adjuster-status").textContent).toBe(
      t("adjuster.panel.failed"),
    );
    expect(region.textContent).not.toContain("Aprobado por error");
    expect(region.textContent).not.toMatch(/timeout|failed|error/i);
    expect(within(region).queryByTestId("adjuster-decision-label")).toBeNull();
    expect(within(region).queryByTestId("adjuster-steps")).toBeNull();
  });

  it("una corrida «decidida» sin titular o sin explicacion se trata como «sigue en revision»", async () => {
    await abrir({
      state: "derived",
      resolution: null,
      adjuster: corrida({ headline: "", explanation: null }),
    });

    const region = screen.getByRole("region", { name: t("adjuster.panel.title_pending") });
    expect(region.getAttribute("data-status")).toBe("failed");
    expect(within(region).queryByTestId("adjuster-decision-label")).toBeNull();
  });

  it("en ingles el panel se lee en ingles", async () => {
    const en = createTranslate("en");
    renderWithProviders(
      <VisitorCasePage token="un-token" conversationHref={() => "/"} renderRejected={rechazo} />,
      "en",
    );

    const region = await screen.findByRole("region", { name: en("adjuster.panel.title") });
    expect(within(region).getByTestId("adjuster-status").textContent).toBe(
      en("adjuster.panel.decided"),
    );
    expect(within(region).getByTestId("adjuster-decision-label").textContent).toBe(
      en("case.resolution.approved"),
    );
    expect(within(region).getByTestId("adjuster-ai-notice").textContent).toBe(
      en("adjuster.panel.ai_notice"),
    );
    expect(
      within(region).getByRole("heading", { level: 3, name: en("adjuster.step.clauses.title") }),
    ).toBeTruthy();
    expect(within(region).getAllByRole("link")[0]?.textContent).toContain(
      en("adjuster.source.new_tab"),
    );
  });
});

// Mientras el ajustador de IA decide el caso, la pagina lo vuelve a leer cada 3 s: los pasos
// aparecen a medida que llegan, y se detiene al decidirse, al tope (30 lecturas) y al dejar la
// pantalla.
describe("«Ver mi caso» abierto mientras el ajustador de IA decide", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

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

  it("los pasos aparecen a medida que llegan y, al decidirse, muestra la decision", async () => {
    pedido
      .mockResolvedValueOnce({ ok: true, value: caso(enCurso(1)) })
      .mockResolvedValueOnce({ ok: true, value: caso(enCurso(3)) })
      .mockResolvedValue({ ok: true, value: caso() });

    await abrirConFechasFalsas();
    expect(screen.getByTestId("adjuster-status").textContent).toBe(
      t("adjuster.panel.running", { done: 1, total: 6 }),
    );

    await pasar(3000);
    expect(screen.getByTestId("adjuster-status").textContent).toBe(
      t("adjuster.panel.running", { done: 3, total: 6 }),
    );
    expect(screen.getAllByTestId("step-mark")).toHaveLength(3);

    await pasar(3000);
    expect(screen.getByTestId("adjuster-status").textContent).toBe(t("adjuster.panel.decided"));
    expect(screen.getByTestId("adjuster-decision-label")).toBeTruthy();
    expect(pedido).toHaveBeenCalledTimes(3);
    // Y no canjea otra vez el enlace: solo vuelve a pedir el caso.
    expect(canjeado).toHaveBeenCalledTimes(1);
  });

  it("se detiene en cuanto el ajustador decide: no vuelve a pedir", async () => {
    pedido
      .mockResolvedValueOnce({ ok: true, value: caso(enCurso(2)) })
      .mockResolvedValue({ ok: true, value: caso() });

    await abrirConFechasFalsas();
    await pasar(3000);
    await pasar(3000 * 40);

    expect(pedido).toHaveBeenCalledTimes(2);
  });

  it("un caso ya decidido se pide una sola vez", async () => {
    await abrirConFechasFalsas();
    await pasar(3000 * 40);

    expect(pedido).toHaveBeenCalledTimes(1);
  });

  it("sigue leyendo mientras espera cupo o fallo --leer el caso lo reintenta-- y se queda en el tope, sin aviso", async () => {
    pedido.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        value: caso({
          state: "derived",
          resolution: null,
          adjuster: corrida({
            status: "capped",
            decision: null,
            headline: null,
            explanation: null,
          }),
        }),
      }),
    );

    await abrirConFechasFalsas();
    await pasar(3000 * 100);

    // La primera lectura y treinta mas: el tope de la espera del ajustador.
    expect(pedido).toHaveBeenCalledTimes(1 + 30);
    expect(screen.getByTestId("adjuster-status").textContent).toBe(t("adjuster.panel.capped"));
  });

  it("limpia el temporizador al dejar la pantalla: no vuelve a pedir", async () => {
    pedido.mockImplementation(() => Promise.resolve({ ok: true, value: caso(enCurso(1)) }));

    const dibujo = await abrirConFechasFalsas();
    await pasar(3000);
    expect(pedido).toHaveBeenCalledTimes(2);

    dibujo.unmount();
    await pasar(3000 * 40);

    expect(pedido).toHaveBeenCalledTimes(2);
  });

  it("si una lectura falla --el enlace vencio-- se queda como esta y no insiste", async () => {
    pedido
      .mockResolvedValueOnce({ ok: true, value: caso(enCurso(1)) })
      .mockResolvedValue({ ok: false, problem: { code: "not_found", message: () => "" } });

    await abrirConFechasFalsas();
    await pasar(3000 * 40);

    expect(pedido).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("adjuster-status").textContent).toBe(
      t("adjuster.panel.running", { done: 1, total: 6 }),
    );
  });
});

// Los dos paneles (Miguel, 2026-10-14): a la izquierda el del ajustador y a la derecha los datos del
// reporte con las reglas; debajo de los dos, a todo el ancho, la conversacion y lo demas. jsdom no
// calcula estilos ni puntos de quiebre: lo que aqui se prueba es el orden del documento (que es el
// de pantalla angosta), la estructura y las clases que arman la rejilla en escritorio. Que la
// rejilla se vea como se dice, en claro y en oscuro y sin desbordar, solo se comprueba en el
// navegador (`e2e/a11y.spec.ts`, rutas `visitor-case*`).
describe("los dos paneles: el del ajustador y los datos del reporte", () => {
  /** Verdadero si `a` queda antes que `b` en el orden del documento. */
  const antes = (a: Node, b: Node): boolean =>
    (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;

  async function abrir(extra: Partial<CaseDetailOut> = {}) {
    pedido.mockResolvedValue({ ok: true, value: caso(extra) });
    dibujar();
    await screen.findByTestId("visitor-case");
  }

  const panelDelAjustador = () => screen.getByTestId("adjuster-panel");
  const panelDeDatos = () => screen.getByRole("region", { name: t("visitor.block.fields") });

  it("cada panel es una region con nombre, y los datos no se llaman «completitud por campo»", async () => {
    await abrir();

    expect(
      within(screen.getByRole("region", { name: t("adjuster.panel.title") })).getByRole("heading", {
        level: 2,
      }).textContent,
    ).toBe(t("adjuster.panel.title"));
    expect(within(panelDeDatos()).getByRole("heading", { level: 2 }).textContent).toBe(
      t("visitor.block.fields"),
    );
    // «Completitud por campo» es la jerga de quien decide con credencial.
    expect(screen.getByTestId("visitor-case").textContent).not.toContain(t("inbox.block.fields"));
    expect(panelDeDatos()).toBe(screen.getByTestId("block-fields"));
  });

  it("los encabezados bajan de a un nivel: titulo, paneles y pasos", async () => {
    await abrir();

    const niveles = within(screen.getByTestId("visitor-case"))
      .getAllByRole("heading")
      .map((titulo) => Number(titulo.tagName.slice(1)));
    expect(niveles[0]).toBe(1);
    niveles.slice(1).forEach((nivel, indice) => {
      // Cada encabezado es, como mucho, un nivel mas hondo que el anterior.
      expect(nivel).toBeLessThanOrEqual((niveles.at(indice) ?? 0) + 1);
    });
    // Los seis pasos cuelgan del panel del ajustador, como encabezados de nivel 3.
    expect(within(panelDelAjustador()).getAllByRole("heading", { level: 3 })).toHaveLength(6);
  });

  it("en el orden del documento --el de pantalla angosta-- los datos y las reglas van antes que el panel del ajustador", async () => {
    await abrir();

    const datos = screen.getByTestId("visitor-data");
    const ajustador = panelDelAjustador();
    expect(antes(datos, ajustador)).toBe(true);
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
    await abrir();

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
    expect(rejilla.contains(screen.getByTestId("block-rule"))).toBe(true);
  });

  it("en escritorio: 7/12 para el ajustador a la izquierda y 5/12 para los datos a la derecha, alineados arriba", async () => {
    await abrir();

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
    await abrir();

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
    await abrir();

    const clasesDe = (elemento: HTMLElement) => elemento.className.split(/\s+/);
    const panel = panelDelAjustador();
    expect(clasesDe(panel)).toEqual(
      expect.arrayContaining(["border-l-4", "border-l-brand", "bg-surface"]),
    );
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
    await abrir();

    const clasesDe = (elemento: HTMLElement) => elemento.className.split(/\s+/);
    for (const bloque of [panelDeDatos(), screen.getByTestId("block-rule")]) {
      expect(clasesDe(bloque)).toContain("bg-surface-alt");
      expect(clasesDe(bloque)).not.toContain("bg-surface");
      expect(bloque.className).not.toMatch(/brand|selected/);
    }
    expect(clasesDe(panelDelAjustador())).not.toContain("bg-surface-alt");
  });

  it("ningun elemento de la pantalla escribe un color a mano ni usa el cobre como letra", async () => {
    // En los cuatro estados del panel: decidido, en curso, en espera y fallido.
    for (const extra of [
      {},
      enCurso(2),
      { state: "derived" as const, adjuster: corrida({ status: "capped" as const }) },
      { state: "derived" as const, adjuster: corrida({ status: "failed" as const }) },
    ]) {
      pedido.mockResolvedValue({ ok: true, value: caso(extra) });
      const { unmount } = renderWithProviders(
        <VisitorCasePage token="un-token" conversationHref={() => "/"} renderRejected={rechazo} />,
      );
      await screen.findByTestId("visitor-case");
      for (const elemento of screen.getByTestId("visitor-case").querySelectorAll("[class]")) {
        const clases = elemento.getAttribute("class") ?? "";
        expect(clases, clases).not.toMatch(/copper|\[#|\[rgb|\[hsl|\[oklch|text-\[color/);
      }
      unmount();
    }
  });
});
