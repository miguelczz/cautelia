import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import sitio from "../../../../contracts/examples/site-directory.json";
import { renderWithProviders } from "../../app/testing";
import type {
  CaseDetailOut,
  ChatCaseStatus,
  ExampleCaseList,
} from "../../shared/api-client/examples";
import {
  installFakeServer,
  jsonResponse,
  problemResponse,
} from "../../shared/api-client/fake-server";
import type { SiteDirectory } from "../../shared/api-client/site";
import { createTranslate } from "../../shared/i18n/translate";
import { formatMoment } from "../inbox/evidence-blocks";
import { CasesPage } from "./cases-page";
import { ExampleCasePage } from "./example-case-page";

// La pagina "Casos" (2026-10-11): el caso propio, los casos de ejemplo por aseguradora y un
// caso de ejemplo en solo lectura. Que NO muestre casos de otros visitantes es de la
// pagina y del servidor: aqui se comprueba que la pagina no pide nada que los traiga.

const t = createTranslate("es");
const directorio = sitio as SiteDirectory;
const [primera, segunda] = directorio.tenants;
if (primera === undefined || segunda === undefined) {
  throw new Error("el ejemplo del directorio no trae dos aseguradoras");
}

const UNA = primera.tenant_id;

function propio(extra: Partial<ChatCaseStatus> = {}): ChatCaseStatus {
  return {
    case_number: "AA-7",
    state: "derived",
    complete: 5,
    total: 7,
    case_link: "/c#un-token-firmado",
    record_type: "claim",
    ...extra,
  };
}

const EJEMPLOS: Record<string, ExampleCaseList> = {
  [primera.tenant_id]: {
    items: [
      {
        case_id: "caso-captura",
        case_number: "AA-3",
        record_type: "claim",
        state: "capturing",
        channel: "chat",
        language: "es",
        completeness_complete: 2,
        completeness_total: 7,
      },
      {
        case_id: "caso-uno",
        case_number: "AA-1",
        record_type: "claim",
        state: "derived",
        channel: "chat",
        language: "es",
        completeness_complete: 5,
        completeness_total: 7,
      },
      {
        case_id: "caso-dos",
        case_number: "AA-2",
        record_type: "coverage_inquiry",
        state: "derived",
        channel: "voice",
        language: "en",
        completeness_complete: 1,
        completeness_total: 1,
      },
    ],
  },
  [segunda.tenant_id]: {
    items: [
      {
        case_id: "caso-cerrado",
        case_number: "BB-9",
        record_type: "quote_request",
        state: "closed",
        channel: "chat",
        language: "en",
        completeness_complete: 17,
        completeness_total: 17,
      },
    ],
  },
};

interface Servidor {
  /** El caso propio por aseguradora; las que no estan responden `null`. */
  readonly propios?: Record<string, ChatCaseStatus>;
  readonly ejemplos?: Record<string, ExampleCaseList | "fallo">;
}

/** El elemento de una lista, o un fallo claro: indexar una lista vacia no es una prueba. */
function en<T>(lista: readonly T[], indice: number): T {
  const valor = lista.at(indice);
  if (valor === undefined) {
    throw new Error(`la lista no tiene el elemento ${String(indice)}`);
  }
  return valor;
}

let quitar: (() => void) | undefined;
let pedidas: string[] = [];

afterEach(() => {
  quitar?.();
  quitar = undefined;
  pedidas = [];
});

function servir({ propios = {}, ejemplos = EJEMPLOS }: Servidor = {}): void {
  quitar = installFakeServer((ruta) => {
    pedidas.push(ruta);
    if (ruta === "/api/site") {
      return jsonResponse(directorio);
    }
    const propia = /^\/api\/chat\/([^/]+)\/case$/.exec(ruta);
    if (propia?.[1] !== undefined) {
      return jsonResponse(propios[propia[1]] ?? null);
    }
    const lista = /^\/api\/examples\/([^/]+)\/cases$/.exec(ruta);
    if (lista?.[1] !== undefined) {
      const respuesta = ejemplos[lista[1]];
      if (respuesta === "fallo") {
        return problemResponse("internal", 500);
      }
      return respuesta === undefined ? problemResponse("not_found", 404) : jsonResponse(respuesta);
    }
    return problemResponse("not_found", 404);
  });
}

describe("la pagina de casos", () => {
  it("dice que es un caso y que se ve aqui", async () => {
    servir();
    renderWithProviders(<CasesPage />, "es");

    await screen.findByTestId("cases");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(t("cases.title"));
    expect(screen.getByText(t("cases.intro"))).toBeDefined();
  });

  describe("tus casos", () => {
    it("sin caso propio dice que no hay ninguno y ofrece empezar uno", async () => {
      servir();
      renderWithProviders(<CasesPage />, "es");

      const vacio = await screen.findByTestId("cases-mine-empty");
      expect(within(vacio).getByText(t("cases.mine.empty"))).toBeDefined();
      expect(
        within(vacio)
          .getByRole("link", { name: t("cases.start") })
          .getAttribute("href"),
      ).toBe("/home");
      expect(screen.queryByTestId("own-case")).toBeNull();
    });

    it("con un caso propio muestra su fila, como va, y las dos acciones", async () => {
      servir({ propios: { [primera.tenant_id]: propio() } });
      renderWithProviders(<CasesPage />, "es");

      const fila = await screen.findByTestId("own-case");
      expect(within(fila).getByRole("heading", { level: 3 }).textContent).toBe(
        primera.display_name,
      );
      // Que es, en las palabras del chat, y su numero en un renglon que dice para que sirve
      // (C10, 2026-10-12): ya no es una etiqueta suelta junto al nombre.
      expect(within(fila).getByText(t("chat.page.case_kind_claim"))).toBeDefined();
      expect(within(fila).getByTestId("own-case-number").textContent).toBe(
        t("cases.mine.number", { case_number: "AA-7" }),
      );
      expect(within(fila).queryByText(t("inbox.case.title", { case_number: "AA-7" }))).toBeNull();
      // Como va, en palabras: el estado y cuanto falta.
      expect(within(fila).getByTestId("own-case-progress").textContent).toBe(
        `${t("case.state.derived")} · ${t("chat.page.case_missing_many", { count: "2" })}`,
      );
      // Seguir en el chat y ver el caso con el enlace firmado que entrega el chat.
      const chat = within(fila).getByRole("link", {
        name: t("cases.mine.chat_with", { insurer: primera.display_name }),
      });
      expect(chat.getAttribute("href")).toBe(`/t/${primera.tenant_id}/chat`);
      const ver = within(fila).getByRole("link", {
        name: t("cases.mine.view_of", { case_number: "AA-7", insurer: primera.display_name }),
      });
      expect(ver.getAttribute("href")).toBe("/c#un-token-firmado");
      expect(ver.textContent).toBe(t("cases.mine.view"));
      // Con un caso, el vacio no se dibuja.
      expect(screen.queryByTestId("cases-mine-empty")).toBeNull();
    });

    it("una fila por aseguradora con conversacion, y solo esas", async () => {
      servir({
        propios: {
          [primera.tenant_id]: propio(),
          [segunda.tenant_id]: propio({
            case_number: "BB-2",
            state: "capturing",
            complete: 1,
          }),
        },
      });
      renderWithProviders(<CasesPage />, "es");

      await waitFor(() => {
        expect(screen.getAllByTestId("own-case")).toHaveLength(2);
      });
      const nombres = screen
        .getAllByTestId("own-case")
        .map((fila) => within(fila).getByRole("heading", { level: 3 }).textContent);
      expect(nombres).toEqual([primera.display_name, segunda.display_name]);
    });

    it("sin enlace de caso en el despliegue solo ofrece seguir en el chat", async () => {
      servir({ propios: { [primera.tenant_id]: propio({ case_link: null }) } });
      renderWithProviders(<CasesPage />, "es");

      const fila = await screen.findByTestId("own-case");
      expect(within(fila).getAllByRole("link")).toHaveLength(1);
      expect(within(fila).queryByText(t("cases.mine.view"))).toBeNull();
    });

    it("una consulta de cobertura no cuenta cuanto falta: nadie esta dando datos", async () => {
      servir({
        propios: {
          [primera.tenant_id]: propio({
            record_type: "coverage_inquiry",
            state: "capturing",
            complete: 0,
            total: 1,
          }),
        },
      });
      renderWithProviders(<CasesPage />, "es");

      const fila = await screen.findByTestId("own-case");
      expect(within(fila).getByText(t("chat.page.case_kind_inquiry"))).toBeDefined();
      expect(within(fila).getByTestId("own-case-progress").textContent).toBe(
        t("case.state.capturing"),
      );
    });
  });

  describe("casos de ejemplo", () => {
    it("abre en la primera aseguradora, agrupados por estado en el orden del servidor, con su linea", async () => {
      servir();
      renderWithProviders(<CasesPage />, "es");

      await screen.findByTestId("example-cases");
      const grupos = screen.getAllByTestId("example-group");
      expect(grupos.map((g) => within(g).getByRole("heading", { level: 3 }).textContent)).toEqual([
        `${t("case.state.capturing")}${t("inbox.queue.results", { count: 1 })}`,
        `${t("case.state.derived")}${t("inbox.queue.results", { count: 2 })}`,
      ]);
      // Cada estado cuenta, en una linea, que esta pasando.
      expect(within(en(grupos, 1)).getByText(t("cases.group.derived"))).toBeDefined();
      // El orden dentro del grupo es el que mando el servidor.
      expect(
        within(en(grupos, 1))
          .getAllByTestId("example-case")
          .map((fila) => /^AA-\d+/.exec(fila.textContent)?.[0]),
      ).toEqual(["AA-1", "AA-2"]);
    });

    it("cada fila dice el tipo, el canal, el idioma y los datos, y abre el caso", async () => {
      servir();
      renderWithProviders(<CasesPage />, "es");

      await screen.findByTestId("example-cases");
      const filas = within(en(screen.getAllByTestId("example-group"), 1)).getAllByTestId(
        "example-case",
      );
      const uno = en(filas, 0);
      const dos = en(filas, 1);
      expect(uno.getAttribute("href")).toBe(`/cases/${primera.tenant_id}/caso-uno`);
      expect(uno.textContent).toContain(t("chat.page.case_kind_claim"));
      expect(uno.textContent).toContain(`${t("case.channel.chat")} · ${t("shell.language.es")}`);
      expect(uno.textContent).toContain(t("inbox.completeness", { complete: 5, total: 7 }));
      // Una consulta no cuenta datos, y su canal e idioma son los suyos.
      expect(dos.textContent).toContain(t("chat.page.case_kind_inquiry"));
      expect(dos.textContent).toContain(`${t("case.channel.voice")} · ${t("shell.language.en")}`);
      expect(dos.textContent).not.toContain("campos");
    });

    it("la lista cambia con la aseguradora que se elige", async () => {
      servir();
      renderWithProviders(<CasesPage />, "es");
      await screen.findByTestId("example-cases");

      fireEvent.click(
        within(screen.getByTestId("cases-insurers")).getByRole("button", {
          name: segunda.display_name,
        }),
      );

      await waitFor(() => {
        expect(screen.getByText("BB-9")).toBeDefined();
      });
      expect(screen.queryByText("AA-1")).toBeNull();
      expect(screen.getByText(t("case.state.closed"))).toBeDefined();
      expect(screen.getByTestId("example-case").getAttribute("href")).toBe(
        `/cases/${segunda.tenant_id}/caso-cerrado`,
      );
    });

    it("abre en la aseguradora que pide la direccion", async () => {
      servir();
      renderWithProviders(<CasesPage initialTenantId={segunda.tenant_id} />, "es");

      await waitFor(() => {
        expect(screen.getByText("BB-9")).toBeDefined();
      });
      expect(screen.queryByText("AA-1")).toBeNull();
    });

    it("una aseguradora sin casos de ejemplo lo dice", async () => {
      servir({ ejemplos: { [primera.tenant_id]: { items: [] } } });
      renderWithProviders(<CasesPage />, "es");

      const vacio = await screen.findByTestId("example-cases-empty");
      expect(within(vacio).getByText(t("cases.examples.empty"))).toBeDefined();
    });

    it("un fallo del servidor se dice y se puede reintentar", async () => {
      servir({ ejemplos: { [primera.tenant_id]: "fallo" } });
      renderWithProviders(<CasesPage />, "es");

      const alerta = await screen.findByTestId("cases-error");
      expect(within(alerta).getByText(t("problem.service_unavailable"))).toBeDefined();
      expect(within(alerta).getByRole("button", { name: t("action.retry") })).toBeDefined();
    });
  });

  it("nunca pide la cola de la bandeja ni los casos de una aseguradora sin elegirla", async () => {
    // La regla dura de la pagina: ninguna consulta trae la lista de casos de la
    // aseguradora. Solo se piden los de ejemplo de la que esta elegida.
    servir({ propios: { [primera.tenant_id]: propio() } });
    renderWithProviders(<CasesPage />, "es");
    await screen.findByTestId("example-cases");
    await screen.findByTestId("own-case");

    expect(pedidas.filter((ruta) => ruta.startsWith("/api/inbox"))).toEqual([]);
    expect(pedidas.filter((ruta) => ruta.startsWith("/api/examples/"))).toEqual([
      `/api/examples/${primera.tenant_id}/cases`,
    ]);
  });

  it("en ingles sale en ingles", async () => {
    servir();
    renderWithProviders(<CasesPage />, "en");

    await screen.findByTestId("cases-mine-empty");
    const en = createTranslate("en");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(en("cases.title"));
    expect(screen.getByText(en("cases.mine.empty"))).toBeDefined();
  });
});

// --- Un caso de ejemplo ---------------------------------------------------------

function ejemplo(extra: Partial<CaseDetailOut> = {}): CaseDetailOut {
  return {
    case_id: "caso-uno",
    case_number: "AA-1",
    state: "derived",
    record_type: "claim",
    channel: "chat",
    language: "es",
    priority: "high",
    derivation_reason: "person_requested",
    completeness_complete: 3,
    completeness_total: 7,
    fields: [
      {
        field_key: "injuries",
        status: "confirmed",
        complete: true,
        label_key: "case.field.injuries",
        value: "Nadie salió herido",
      },
      {
        field_key: "location",
        status: "not_stated",
        complete: false,
        label_key: "case.field.location",
      },
    ],
    transcript: [
      {
        turn_id: "t1",
        speaker: "insured",
        text_redacted: "Me rayaron el carro.",
        started_at: "2026-10-01T12:00:00+00:00",
      },
    ],
    coverage_answers: [],
    rule_category: "referral",
    fired_rules: ["AAA-R-01"],
    controls_ok: true,
    control_findings: [],
    trace_status: "ready",
    trace_cost_usd: "0.0021",
    trace_cost_status: "measured",
    trace_latency_ms: 1200,
    updated_at: "2026-10-01T12:01:00+00:00",
    resolution: null,
    available_actions: [],
    can_correct_fields: false,
    explanation: {
      asked: "present",
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

function servirCaso(respuesta: () => Response): void {
  quitar = installFakeServer((ruta) => {
    pedidas.push(ruta);
    if (ruta === "/api/site") {
      return jsonResponse(directorio);
    }
    if (ruta === `/api/examples/${UNA}/cases/caso-uno`) {
      return respuesta();
    }
    return problemResponse("not_found", 404);
  });
}

describe("un caso de ejemplo", () => {
  it("se lee como lo ve un ajustador: sus bloques, la nota y la vuelta a Casos", async () => {
    servirCaso(() => jsonResponse(ejemplo()));
    renderWithProviders(<ExampleCasePage tenantId={primera.tenant_id} caseId="caso-uno" />, "es");

    const pagina = await screen.findByTestId("example-case");
    expect(within(pagina).getByRole("heading", { level: 1 }).textContent).toBe(
      t("cases.example.title", { case_number: "AA-1" }),
    );
    await waitFor(() => {
      expect(within(pagina).getByTestId("example-insurer").textContent).toContain(
        primera.display_name,
      );
    });
    expect(within(pagina).getByTestId("example-note").textContent).toContain(
      t("cases.example.note"),
    );
    // Los mismos bloques de la bandeja, con lo anotado en claro.
    for (const bloque of ["fields", "transcript", "citations", "rule", "controls", "trace"]) {
      expect(within(pagina).getByTestId(`block-${bloque}`)).toBeDefined();
    }
    expect(within(pagina).getByText("Nadie salió herido")).toBeDefined();
    expect(within(pagina).getByText("Me rayaron el carro.")).toBeDefined();
    // Vuelve a Casos con la aseguradora que se estaba mirando.
    expect(within(pagina).getByTestId("example-back").getAttribute("href")).toBe(
      `/cases?tenant=${primera.tenant_id}`,
    );
    // Y ofrece empezar el propio, que es donde se decide un caso de verdad.
    expect(
      within(pagina)
        .getByRole("link", { name: t("cases.start") })
        .getAttribute("href"),
    ).toBe("/home");
  });

  it("la categoria de las reglas sale con su etiqueta y nunca el valor en crudo", async () => {
    servirCaso(() => jsonResponse(ejemplo({ rule_category: "direct_close" })));
    renderWithProviders(<ExampleCasePage tenantId={primera.tenant_id} caseId="caso-uno" />, "es");

    const pagina = await screen.findByTestId("example-case");
    expect(within(pagina).getByText(t("inbox.rule.category.direct_close"))).toBeDefined();
    expect(pagina.textContent).not.toContain("direct_close");
  });

  // Quien cerro un ejemplo (2026-10-13). El servidor manda el tipo de actor y, sin credencial,
  // nunca su identificador: la pagina dice que lo decidio un ajustador de la aseguradora (o que
  // la agencia lo envio a la emisora, que no decide), que no hubo ajustador si lo cerraron las
  // reglas, y jamas «Sin decision registrada» de un caso que si la tiene.
  it.each([
    ["approved", "staff", () => t("inbox.explanation.by_adjuster")],
    ["rejected", "staff", () => t("inbox.explanation.by_adjuster")],
    ["sent_to_insurer", "staff", () => t("inbox.explanation.by_agency")],
    ["registered", "system", () => t("inbox.explanation.by_rules")],
  ] as const)(
    "un ejemplo cerrado como %s por %s dice quien lo cerro, sin nombrar a nadie",
    async (resolucion, tipo, decir) => {
      servirCaso(() =>
        jsonResponse(
          ejemplo({
            state: "closed",
            resolution: resolucion,
            derivation_reason: resolucion === "registered" ? null : "rule",
            explanation: {
              asked: "present",
              cited: "none",
              rule: "present",
              decided_by: "present",
              decided_at: "present",
              decided_by_kind: tipo,
              decided_by_id: null,
              decided_at_iso: "2026-10-13T09:05:00+00:00",
            },
          }),
        ),
      );
      renderWithProviders(<ExampleCasePage tenantId={primera.tenant_id} caseId="caso-uno" />, "es");

      const pagina = await screen.findByTestId("example-case");
      const frase = decir();
      expect(within(pagina).getByText(frase)).toBeDefined();
      expect(pagina.textContent).not.toContain(t("inbox.explanation.nobody"));
      // Ni el tipo de actor en crudo, ni «persona»: se dice ajustador o agencia.
      expect(pagina.textContent).not.toMatch(/\b(staff|system)\b/);
      expect(frase).not.toMatch(/persona/i);
      // Y la hora sigue ahi: la otra mitad de la pregunta.
      expect(
        within(pagina).getByText(formatMoment("2026-10-13T09:05:00+00:00", "es")),
      ).toBeDefined();
    },
  );

  // «Por que llego aqui» (2026-10-13): «sin motivo registrado» se leia como un dato que faltaba
  // en un ejemplo que nunca llego a un ajustador, justo al lado de «sin ajustador».
  it("un ejemplo que cerraron las reglas dice que no paso por un ajustador", async () => {
    servirCaso(() =>
      jsonResponse(
        ejemplo({
          state: "closed",
          resolution: "registered",
          derivation_reason: null,
          explanation: {
            asked: "present",
            cited: "none",
            rule: "present",
            decided_by: "present",
            decided_at: "present",
            decided_by_kind: "system",
            decided_by_id: null,
            decided_at_iso: "2026-10-13T09:05:00+00:00",
          },
        }),
      ),
    );
    renderWithProviders(<ExampleCasePage tenantId={primera.tenant_id} caseId="caso-uno" />, "es");

    const pagina = await screen.findByTestId("example-case");
    expect(within(pagina).getByTestId("example-reason").textContent).toBe(
      t("inbox.case.not_handed_off"),
    );
    expect(pagina.textContent).not.toContain(t("inbox.case.no_reason"));
  });

  it("un ejemplo derivado dice su motivo", async () => {
    servirCaso(() => jsonResponse(ejemplo()));
    renderWithProviders(<ExampleCasePage tenantId={primera.tenant_id} caseId="caso-uno" />, "es");

    expect((await screen.findByTestId("example-reason")).textContent).toBe(
      t("case.derivation_reason.person_requested"),
    );
  });

  it("un ejemplo derivado que no trae motivo sigue diciendo que no hay", async () => {
    servirCaso(() => jsonResponse(ejemplo({ derivation_reason: null })));
    renderWithProviders(<ExampleCasePage tenantId={primera.tenant_id} caseId="caso-uno" />, "es");

    expect((await screen.findByTestId("example-reason")).textContent).toBe(
      t("inbox.case.no_reason"),
    );
  });

  it("un ejemplo que la agente aun evalua dice que la esta revisando", async () => {
    servirCaso(() => jsonResponse(ejemplo({ state: "deciding", derivation_reason: null })));
    renderWithProviders(<ExampleCasePage tenantId={primera.tenant_id} caseId="caso-uno" />, "es");

    expect((await screen.findByTestId("example-reason")).textContent).toBe(
      t("cases.group.deciding"),
    );
  });

  it("un caso de ejemplo no ensena el enlace a Langfuse aunque el servidor mandara una direccion", async () => {
    // El servidor no la manda en esta ruta; la pagina es publica y esta es la segunda llave.
    servirCaso(() =>
      jsonResponse(ejemplo({ trace_url: "https://us.cloud.langfuse.com/project/p1/traces/123" })),
    );
    renderWithProviders(<ExampleCasePage tenantId={primera.tenant_id} caseId="caso-uno" />, "es");

    const pagina = await screen.findByTestId("example-case");
    expect(within(pagina).getByTestId("block-trace")).toBeTruthy();
    expect(within(pagina).queryByTestId("trace-langfuse-link")).toBeNull();
    expect(pagina.textContent).not.toContain("Langfuse");
  });

  it("lo que no tiene dato no se pinta, y el ancho de la columna es el del caso del visitante", async () => {
    servirCaso(() =>
      jsonResponse(
        ejemplo({
          rule_category: null,
          fired_rules: [],
          controls_ok: null,
          trace_status: null,
          trace_cost_usd: null,
          trace_latency_ms: null,
        }),
      ),
    );
    renderWithProviders(<ExampleCasePage tenantId={primera.tenant_id} caseId="caso-uno" />, "es");

    const pagina = await screen.findByTestId("example-case");
    for (const bloque of ["rule", "controls", "trace"]) {
      expect(within(pagina).queryByTestId(`block-${bloque}`)).toBeNull();
    }
    expect(pagina.className).toContain("max-w-[52rem]");
  });

  it("la conversacion de un caso de ejemplo no se destapa con lo que este navegador recuerde", async () => {
    // El caso de ejemplo no es de quien lo mira: lo escrito en este navegador no le pertenece.
    window.localStorage.setItem(
      `cautelia.own-text.${primera.tenant_id}`,
      JSON.stringify(["Me rayaron el carro en la calle 80."]),
    );
    servirCaso(() =>
      jsonResponse(
        ejemplo({
          transcript: [
            {
              turn_id: "t1",
              speaker: "insured",
              text_redacted: "Me rayaron el carro en [LUGAR 1].",
              started_at: "2026-10-01T12:00:00+00:00",
            },
          ],
        }),
      ),
    );
    renderWithProviders(<ExampleCasePage tenantId={primera.tenant_id} caseId="caso-uno" />, "es");

    const pagina = await screen.findByTestId("example-case");
    expect(within(pagina).getByText("Me rayaron el carro en [LUGAR 1].")).toBeDefined();
    expect(pagina.textContent).not.toContain("calle 80");
  });

  it("no tiene ningun control de decision ni de correccion, aunque el servidor ofreciera acciones", async () => {
    // Un servidor que ofreciera acciones por error no debe producir botones: la pantalla de
    // un caso de ejemplo no monta el formulario de decision ni la correccion de campos.
    servirCaso(() =>
      jsonResponse(ejemplo({ available_actions: ["approve", "reject"], can_correct_fields: true })),
    );
    const { container } = renderWithProviders(
      <ExampleCasePage tenantId={primera.tenant_id} caseId="caso-uno" />,
      "es",
    );

    await screen.findByTestId("example-case");
    expect(container.querySelector("form, textarea, input, select")).toBeNull();
    for (const nombre of [
      t("inbox.decision.approve"),
      t("inbox.decision.reject"),
      t("inbox.decision.mark_sent"),
    ]) {
      expect(screen.queryByRole("button", { name: nombre })).toBeNull();
    }
    expect(screen.queryByText(t("inbox.decision.title"))).toBeNull();
    expect(screen.queryByTestId("decision-form")).toBeNull();
    expect(screen.queryByTestId("correction-injuries")).toBeNull();
    expect(screen.queryByTestId("correction-location")).toBeNull();
  });

  it("un caso que no existe --o que no es de ejemplo-- dice que no hay nada y vuelve a Casos", async () => {
    servirCaso(() => problemResponse("not_found", 404));
    renderWithProviders(<ExampleCasePage tenantId={primera.tenant_id} caseId="caso-uno" />, "es");

    const problema = await screen.findByTestId("example-case-problem");
    expect(within(problema).getByRole("heading", { level: 1 }).textContent).toBe(
      t("inbox.case.not_found"),
    );
    expect(
      within(problema)
        .getByRole("link", { name: t("cases.example.back") })
        .getAttribute("href"),
    ).toBe(`/cases?tenant=${primera.tenant_id}`);
    expect(screen.queryByTestId("example-case")).toBeNull();
  });

  it("un fallo del servidor se dice y se puede reintentar", async () => {
    servirCaso(() => problemResponse("internal", 500));
    renderWithProviders(<ExampleCasePage tenantId={primera.tenant_id} caseId="caso-uno" />, "es");

    const problema = await screen.findByTestId("example-case-problem");
    expect(within(problema).getByRole("alert").textContent).toContain(
      t("problem.service_unavailable"),
    );
    expect(within(problema).getByRole("button", { name: t("action.retry") })).toBeDefined();
  });
});
