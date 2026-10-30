import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../app/testing";
import {
  installFakeServer,
  jsonResponse,
  problemResponse,
} from "../../shared/api-client/fake-server";
import type {
  BudgetState,
  CaseSpendItem,
  ComparisonSpendItem,
  SpendPanel,
  UnpricedUsage,
} from "../../shared/api-client/spend";
import type { Locale } from "../../shared/copy/copy-keys";
import { createTranslate } from "../../shared/i18n/translate";
import { SpendDashboard } from "./spend-dashboard";

// El tablero de gasto en la pantalla (2026-10-09). Lo que se comprueba es lo que
// no se puede romper: los promedios salen de total entre cuantos, lo que no tiene
// precio nunca se dibuja como cero (sale en tokens), el estado del techo es el que
// manda el servidor, las cifras caben en su tarjeta, una comparacion es una sola
// entrada y **ningun caso se identifica**: se describe, y el del navegador es "Tuyo".

const GRATIS: UnpricedUsage = { tokens: 12345, uncounted: 0, free_plan: true };

let quitar: (() => void) | undefined;

function ventana(cambios: Partial<BudgetState> = {}): BudgetState {
  return {
    window_start: "2026-09-16",
    window_end: "2026-12-15",
    spent: { measured_usd: "10.00", unmeasured_count: 0 },
    cap_usd: "40.00",
    alert_usd: "24.00",
    recording_reserve_usd: { amount_usd: "1.49", status: "measured" },
    recording_spent: { measured_usd: "0", unmeasured_count: 0 },
    public_remaining_usd: { amount_usd: "28.51", status: "measured" },
    recording_remaining_usd: { amount_usd: "1.49", status: "measured" },
    status: "ok",
    ...cambios,
  };
}

function caso(cambios: Partial<CaseSpendItem>): CaseSpendItem {
  return {
    key: "0",
    tenant_id: "una-aseguradora",
    record_type: "claim",
    channel: "voice",
    started_at: "2026-10-09T20:20:00Z",
    yours: false,
    total: { measured_usd: "0.03", unmeasured_count: 0 },
    by_provider: [{ provider: "cartesia", total: { measured_usd: "0.03", unmeasured_count: 0 } }],
    ...cambios,
  };
}

function panel(cambios: Partial<SpendPanel> = {}): SpendPanel {
  return {
    window: ventana(),
    alert_sent_at: null,
    total: { measured_usd: "0.60", unmeasured_count: 7 },
    by_activity: [
      { activity: "calls", total: { measured_usd: "0.30", unmeasured_count: 0 } },
      { activity: "chat", total: { measured_usd: "0.30", unmeasured_count: 0 } },
      {
        activity: "policy_reading",
        total: { measured_usd: "0", unmeasured_count: 7 },
        unpriced: GRATIS,
      },
    ],
    by_provider: [
      {
        provider: "anthropic",
        total: { measured_usd: "0.40", unmeasured_count: 0 },
        models: [
          { model: "claude-haiku-5-5", total: { measured_usd: "0.40", unmeasured_count: 0 } },
        ],
      },
      {
        provider: "gemini",
        total: { measured_usd: "0", unmeasured_count: 7 },
        unpriced: GRATIS,
      },
    ],
    by_day: [
      { day: "2026-10-07", activities: [] },
      {
        day: "2026-10-08",
        activities: [{ activity: "calls", total: { measured_usd: "0.20", unmeasured_count: 0 } }],
      },
      {
        day: "2026-10-09",
        activities: [{ activity: "chat", total: { measured_usd: "0.05", unmeasured_count: 0 } }],
      },
    ],
    calls: { count: 4, total: { measured_usd: "0.12", unmeasured_count: 0 } },
    chats: { count: 0, total: { measured_usd: "0", unmeasured_count: 0 } },
    cases: [
      caso({
        key: "0",
        tenant_id: "otra-aseguradora",
        record_type: "coverage_inquiry",
        channel: "chat",
      }),
      caso({
        key: "1",
        yours: true,
        total: { measured_usd: "0.05", unmeasured_count: 2 },
        by_provider: [
          { provider: "deepgram", total: { measured_usd: "0.05", unmeasured_count: 0 } },
        ],
      }),
    ],
    ...cambios,
  };
}

const DIRECTORIO = {
  tenants: [
    {
      tenant_id: "una-aseguradora",
      display_name: "Autos Poblado",
      kind: "carrier",
      default_language: "en",
      example_policy: "POL-21",
    },
    {
      tenant_id: "otra-aseguradora",
      display_name: "Seguros Aburrá",
      kind: "carrier",
      default_language: "es",
      example_policy: "POL-11",
    },
    {
      tenant_id: "tercera-aseguradora",
      display_name: "Agencia Castilla",
      kind: "agency",
      default_language: "es",
      example_policy: "POL-31",
    },
  ],
  surfaces: ["metrics_panel", "spend_panel"],
  links: {},
};

function servir(respuesta: SpendPanel): void {
  quitar = installFakeServer((ruta) => {
    if (ruta === "/api/spend") {
      return jsonResponse(respuesta);
    }
    if (ruta === "/api/site") {
      return jsonResponse(DIRECTORIO);
    }
    return jsonResponse({}, 404);
  });
}

async function dibujar(locale: Locale = "es") {
  renderWithProviders(<SpendDashboard />, locale);
  await waitFor(() => {
    expect(screen.queryByTestId("spend-dashboard")).not.toBeNull();
  });
  return createTranslate(locale);
}

afterEach(() => {
  quitar?.();
  quitar = undefined;
  vi.restoreAllMocks();
});

describe.each<Locale>(["es", "en"])("el tablero de gasto en %s", (idioma) => {
  it("el promedio por llamada es el total entre cuantas fueron, y sin llamadas no inventa uno", async () => {
    servir(panel());
    const t = await dibujar(idioma);

    // 0,12 entre 4 llamadas: 0,03.
    expect(screen.getByTestId("spend-per-call").textContent).toMatch(/0[.,]03/);
    expect(screen.getByTestId("spend-per-call").textContent).toContain(
      t("spend_panel.kpi.per_call_hint", { count: "4" }),
    );
    // Sin conversaciones no hay promedio: ni cero ni una division por cero.
    const chat = screen.getByTestId("spend-per-chat").textContent;
    expect(chat).toContain(t("spend_panel.kpi.none_yet"));
    expect(chat).not.toMatch(/NaN|Infinity/);
  });

  it("el presupuesto usado es lo gastado de la ventana sobre el techo", async () => {
    servir(panel());
    await dibujar(idioma);

    // 10 de 40: 25 %.
    expect(screen.getByTestId("spend-budget").textContent).toMatch(/25\s?%/);
  });

  it("lo que no tiene precio sale en tokens y nunca como cero, y ya no se explica con una frase", async () => {
    servir(panel());
    const t = await dibujar(idioma);

    const actividad = within(screen.getByTestId("spend-activity"));
    const lectura = actividad.getByText(t("spend_panel.activity.policy_reading")).closest("li");
    expect(lectura?.textContent).toMatch(/12[.,]345/);
    // En "En que se va" solo va la cifra: ni "plan gratuito" ni "+ N consultas" (E4).
    expect(lectura?.textContent).not.toContain(t("spend_panel.tokens.free_plan"));
    expect(lectura?.textContent).not.toContain(t("spend_panel.not_measured"));
    const gemini = within(screen.getByTestId("spend-providers"))
      .getByText(t("spend_panel.provider.gemini"))
      .closest("li");
    expect(gemini?.textContent).toMatch(/12[.,]345/);
    // La frase que contaba las consultas sin precio salio del tablero (2026-10-11).
    expect(screen.queryByTestId("spend-unmeasured")).toBeNull();
    expect(document.body.textContent).not.toMatch(/sin precio publicado|no published price/i);
  });

  it("si el proveedor no reporta tokens dice cuantas consultas fueron, y sin plan gratuito que no se respalde", async () => {
    // El servicio de vectores de Google no devuelve recuento de tokens (2026-10-11).
    const sinRecuento: UnpricedUsage = { tokens: 0, uncounted: 7, free_plan: false };
    const deLaTabla = panel();
    servir(
      panel({
        by_activity: deLaTabla.by_activity.map((a) =>
          a.activity === "policy_reading" ? { ...a, unpriced: sinRecuento } : a,
        ),
        by_provider: deLaTabla.by_provider.map((p) =>
          p.provider === "gemini"
            ? { ...p, unpriced: { tokens: 500, uncounted: 0, free_plan: false } }
            : p,
        ),
      }),
    );
    const t = await dibujar(idioma);

    const actividad = within(screen.getByTestId("spend-activity"));
    const lectura = actividad.getByText(t("spend_panel.activity.policy_reading")).closest("li");
    expect(lectura?.textContent).toContain(t("spend_panel.tokens.lookups", { count: "7" }));
    expect(lectura?.textContent).not.toContain(t("spend_panel.not_measured"));
    expect(within(lectura as HTMLElement).queryByTestId("spend-amount-note")).toBeNull();
    const gemini = within(screen.getByTestId("spend-providers"))
      .getByText(t("spend_panel.provider.gemini"))
      .closest("li");
    expect(gemini?.textContent).toContain("500");
    // "Plan gratuito" solo cuando el servidor lo respalda: ni una nota que lo diga.
    expect(within(gemini as HTMLElement).queryByTestId("spend-amount-note")).toBeNull();
  });

  it("sin tokens ni consultas que contar dice que no tiene precio; con el plan gratuito respaldado, lo dice", async () => {
    const deLaTabla = panel();
    servir(
      panel({
        by_activity: deLaTabla.by_activity.map((a) =>
          a.activity === "policy_reading"
            ? { ...a, unpriced: { tokens: 0, uncounted: 0, free_plan: false } }
            : a,
        ),
        by_provider: deLaTabla.by_provider.map((p) =>
          p.provider === "gemini"
            ? {
                ...p,
                total: { measured_usd: "0", unmeasured_count: 1 },
                unpriced: { tokens: 0, uncounted: 1, free_plan: true },
              }
            : p,
        ),
      }),
    );
    const t = await dibujar(idioma);

    const actividad = within(screen.getByTestId("spend-activity"));
    const lectura = actividad.getByText(t("spend_panel.activity.policy_reading")).closest("li");
    expect(lectura?.textContent).toContain(t("spend_panel.not_measured"));
    const gemini = within(screen.getByTestId("spend-providers"))
      .getByText(t("spend_panel.provider.gemini"))
      .closest("li");
    expect(gemini?.textContent).toContain(t("spend_panel.tokens.lookup_one"));
    expect(within(gemini as HTMLElement).getByTestId("spend-amount-note").textContent).toBe(
      t("spend_panel.tokens.free_plan"),
    );
  });

  it("si una parte tiene precio y otra no, dice el importe y suma los tokens aparte", async () => {
    const deLaTabla = panel();
    servir(
      panel({
        by_provider: deLaTabla.by_provider.map((p) =>
          p.provider === "gemini"
            ? { ...p, total: { measured_usd: "0.25", unmeasured_count: 3 } }
            : p,
        ),
      }),
    );
    const t = await dibujar(idioma);

    const gemini = within(screen.getByTestId("spend-providers"))
      .getByText(t("spend_panel.provider.gemini"))
      .closest("li");
    expect(gemini?.textContent).toMatch(/0[.,]25/);
    expect(gemini?.textContent).toMatch(/\+\s*12[.,]345/);
  });

  it("cada proveedor dice con que modelo trabaja, y el que no trae modelos no deja la etiqueta sola", async () => {
    servir(panel());
    const t = await dibujar(idioma);

    const proveedores = within(screen.getByTestId("spend-providers"));
    const modelos = proveedores.getAllByTestId("spend-models");
    expect(modelos).toHaveLength(1);
    expect(modelos[0]?.textContent).toContain(t("spend_panel.provider.models"));
    expect(modelos[0]?.textContent).toContain(idioma === "es" ? "Modelos:" : "Models:");
    expect(modelos[0]?.textContent).not.toContain("Usamos");
    expect(modelos[0]?.textContent).toContain("claude-haiku-5-5");
  });

  it("el estado del techo es el que manda el servidor", async () => {
    servir(panel({ window: ventana({ status: "exhausted" }) }));
    const t = await dibujar(idioma);

    expect(screen.getByTestId("spend-window").textContent).toContain(
      t("spend_panel.status_value.exhausted"),
    );
  });

  it("la grafica abre en el ultimo dia con gasto y las flechas cambian de dia", async () => {
    servir(panel());
    await dibujar(idioma);

    const detalle = () => screen.getByTestId("spend-daily-detail").textContent;
    expect(detalle()).toMatch(/0[.,]05/);
    const grafica = within(screen.getByTestId("spend-daily")).getByRole("slider");
    fireEvent.keyDown(grafica, { key: "ArrowLeft" });
    expect(detalle()).toMatch(/0[.,]20/);
  });

  it("los casos se describen sin numero, y el del navegador sale primero elegido como suyo", async () => {
    servir(panel());
    const t = await dibujar(idioma);

    const selector = screen.getByTestId<HTMLSelectElement>("spend-case-select");
    await waitFor(() => {
      expect(selector.textContent).toContain("Seguros Aburrá");
    });
    const opciones = Array.from(selector.options).map((o) => o.textContent);
    // El propio se marca como tuyo; el ajeno es solo su descripcion, sin numero ni
    // identificador: que fue, con quien, por donde y cuando.
    expect(opciones[1]?.startsWith(`${t("spend_panel.cases.mine")} · `)).toBe(true);
    expect(opciones[0]).toBe(
      t("spend_panel.cases.describe", {
        type: t("spend_panel.cases.type_coverage_inquiry"),
        insurer: "Seguros Aburrá",
        channel: t("spend_panel.cases.channel_chat"),
        when: opciones[0]?.split(" · ").pop() ?? "",
      }),
    );
    expect(opciones[0]).not.toContain(t("spend_panel.cases.mine"));
    expect(opciones[0]).not.toMatch(/#|\bSTO-|\bcase-/i);
    // El elegido al abrir es el suyo, con su desglose.
    expect(selector.value).toBe("1");
    const detalle = screen.getByTestId("spend-case-detail");
    expect(detalle.textContent).toContain(t("spend_panel.provider.deepgram"));
    expect(detalle.textContent).toContain(t("spend_panel.cases.yours"));

    fireEvent.change(selector, { target: { value: "0" } });
    const ajeno = screen.getByTestId("spend-case-detail");
    expect(ajeno.textContent).toContain(t("spend_panel.provider.cartesia"));
    // Un caso ajeno no se marca como tuyo ni muestra ningun numero de caso.
    expect(ajeno.textContent).not.toContain(t("spend_panel.cases.yours"));
    expect(ajeno.textContent).not.toMatch(/#|\bSTO-/);
  });

  it("los tokens de un caso salen donde antes decia que no tenia precio", async () => {
    const delCaso = caso({
      key: "0",
      yours: true,
      total: { measured_usd: "0", unmeasured_count: 3 },
      by_provider: [
        {
          provider: "gemini",
          total: { measured_usd: "0", unmeasured_count: 3 },
          unpriced: GRATIS,
        },
      ],
      unpriced: GRATIS,
    });
    servir(panel({ cases: [delCaso] }));
    const t = await dibujar(idioma);

    const detalle = screen.getByTestId("spend-case-detail");
    // La cifra grande y la fila de Gemini dicen los tokens, no "Sin precio".
    expect(within(detalle).getByTestId("spend-figure").textContent).toMatch(/12[.,]345/);
    expect(detalle.textContent).toContain(t("spend_panel.tokens.free_plan"));
    expect(detalle.textContent).not.toContain(t("spend_panel.not_measured"));
  });

  it("las consultas de un clic en Comparar son una sola entrada, con la parte de cada aseguradora", async () => {
    const comparacion: ComparisonSpendItem = {
      key: "c0",
      started_at: "2026-10-11T20:02:00Z",
      yours: true,
      total: { measured_usd: "0.03", unmeasured_count: 3 },
      unpriced: GRATIS,
      parts: [
        { tenant_id: "otra-aseguradora", total: { measured_usd: "0.01", unmeasured_count: 1 } },
        { tenant_id: "tercera-aseguradora", total: { measured_usd: "0.02", unmeasured_count: 1 } },
        { tenant_id: "una-aseguradora", total: { measured_usd: "0", unmeasured_count: 1 } },
      ],
    };
    servir(panel({ cases: [caso({ key: "0", channel: "chat" })], comparisons: [comparacion] }));
    const t = await dibujar(idioma);

    const selector = screen.getByTestId<HTMLSelectElement>("spend-case-select");
    await waitFor(() => {
      expect(selector.textContent).toContain("Autos Poblado");
    });
    // Dos entradas y no cuatro: el caso suelto y la comparacion.
    expect(selector.options).toHaveLength(2);
    const etiqueta = Array.from(selector.options).find((o) => o.value === "c0")?.textContent ?? "";
    expect(etiqueta.startsWith(`${t("spend_panel.cases.mine")} · `)).toBe(true);
    expect(etiqueta).toContain("3");
    // La comparacion es mia, asi que abre elegida, con el total y la parte de cada una.
    expect(selector.value).toBe("c0");
    const detalle = within(screen.getByTestId("spend-case-detail"));
    const partes = within(detalle.getByTestId("spend-insurer-parts"));
    await waitFor(() => {
      expect(partes.queryByText("Seguros Aburrá")).not.toBeNull();
    });
    for (const nombre of ["Seguros Aburrá", "Agencia Castilla", "Autos Poblado"]) {
      expect(partes.getByText(nombre)).toBeTruthy();
    }
    expect(detalle.getByTestId("spend-figure").textContent).toMatch(/0[.,]03/);
    expect(detalle.getByTestId("spend-comparison-hint").textContent).toBe(
      t("spend_panel.cases.comparison_hint", { count: "3" }),
    );
    // Sin identificador de ninguna de las tres consultas.
    expect(screen.getByTestId("spend-case-detail").textContent).not.toMatch(/#|\bSTO-/);
  });

  it("una comparacion de una sola aseguradora se nombra con ella y no promete otras", async () => {
    const unica: ComparisonSpendItem = {
      key: "c0",
      started_at: "2026-10-11T20:02:00Z",
      yours: false,
      total: { measured_usd: "0.01", unmeasured_count: 0 },
      parts: [
        { tenant_id: "otra-aseguradora", total: { measured_usd: "0.01", unmeasured_count: 0 } },
      ],
    };
    servir(panel({ cases: [], comparisons: [unica] }));
    await dibujar(idioma);

    const selector = screen.getByTestId<HTMLSelectElement>("spend-case-select");
    await waitFor(() => {
      expect(selector.options[0]?.textContent).toContain("Seguros Aburrá");
    });
    expect(screen.queryByTestId("spend-comparison-hint")).toBeNull();
  });

  it("sin casos con gasto, invita a probar en vez de mostrar una lista vacia", async () => {
    servir(panel({ cases: [] }));
    const t = await dibujar(idioma);

    expect(screen.getByTestId("spend-cases").textContent).toContain(t("spend_panel.cases.empty"));
    expect(screen.queryByTestId("spend-case-select")).toBeNull();
  });
});

// El acceso a Langfuse (2026-10-14): arriba un boton-enlace a la ultima conversacion de este
// navegador, y en el caso propio un enlace a su traza. Lo que manda el servidor se pinta
// tal cual si es https y en ningun otro caso: esta pantalla no arma direcciones.

const TRAZA = "https://us.cloud.langfuse.com/project/proyecto-local/traces/48215069371502846913";
const TRAZA_DEL_CASO = "https://us.cloud.langfuse.com/project/proyecto-local/traces/7777777777";

describe.each<Locale>(["es", "en"])("el acceso a Langfuse, en %s", (idioma) => {
  it("con la direccion que manda el servidor, un boton-enlace que abre otra pestana sin pasar el origen y la nota debajo", async () => {
    servir(panel({ langfuse_url: TRAZA }));
    const t = await dibujar(idioma);

    const enlace = screen.getByTestId<HTMLAnchorElement>("spend-langfuse-link");
    expect(enlace.textContent).toBe(t("spend_panel.langfuse.link"));
    expect(enlace.getAttribute("href")).toBe(TRAZA);
    expect(enlace.getAttribute("target")).toBe("_blank");
    expect(enlace.getAttribute("rel")).toBe("noopener noreferrer");
    // La nota es la de la bandeja: dice que Langfuse es externa y que no muestra la conversacion.
    const nota = screen.getByTestId("spend-langfuse").querySelector("p");
    expect(nota?.textContent).toBe(t("inbox.trace.langfuse_note"));
    expect(enlace.getAttribute("aria-describedby")).toBe(nota?.id);
    expect(screen.queryByTestId("spend-langfuse-empty")).toBeNull();
  });

  it("sin direccion no hay boton: una linea discreta dice cuando lo habra", async () => {
    servir(panel({ langfuse_url: null }));
    const t = await dibujar(idioma);

    expect(screen.queryByTestId("spend-langfuse-link")).toBeNull();
    expect(screen.queryByTestId("spend-langfuse")).toBeNull();
    expect(screen.getByTestId("spend-langfuse-empty").textContent).toBe(
      t("spend_panel.langfuse.empty"),
    );
  });

  it("un servidor que no conoce el campo se trata como sin direccion", async () => {
    servir(panel());
    await dibujar(idioma);

    expect(screen.queryByTestId("spend-langfuse-link")).toBeNull();
    expect(screen.queryByTestId("spend-langfuse-empty")).not.toBeNull();
  });

  it.each([
    "javascript:alert(1)",
    "http://us.cloud.langfuse.com/project/p/traces/t",
    "//us.cloud.langfuse.com/project/p/traces/t",
    "data:text/html,hola",
    "https://con espacio/x",
    "",
  ])("una direccion que no es https no llega a un href: %s", async (direccion) => {
    servir(
      panel({ langfuse_url: direccion, cases: [caso({ yours: true, trace_url: direccion })] }),
    );
    await dibujar(idioma);

    expect(screen.queryByTestId("spend-langfuse-link")).toBeNull();
    expect(screen.queryByTestId("spend-case-langfuse-link")).toBeNull();
    expect(document.querySelectorAll("a[target='_blank']")).toHaveLength(0);
    // Lo que no se puede abrir se dice igual que cuando no hay nada que abrir.
    expect(screen.queryByTestId("spend-langfuse-empty")).not.toBeNull();
  });

  it("el caso propio con traza lleva su enlace pequeno, y uno ajeno no, aunque el servidor lo mandara", async () => {
    servir(
      panel({
        langfuse_url: TRAZA,
        cases: [
          // Esto el servidor no lo hace (el tipo lo impide); la pantalla tampoco lo pinta.
          caso({ key: "0", yours: false, trace_url: TRAZA_DEL_CASO }),
          caso({ key: "1", yours: true, trace_url: TRAZA_DEL_CASO }),
        ],
      }),
    );
    const t = await dibujar(idioma);

    const selector = screen.getByTestId<HTMLSelectElement>("spend-case-select");
    expect(selector.value).toBe("1");
    const propio = screen.getByTestId<HTMLAnchorElement>("spend-case-langfuse-link");
    expect(propio.textContent).toBe(t("spend_panel.langfuse.case_link"));
    expect(propio.getAttribute("href")).toBe(TRAZA_DEL_CASO);
    expect(propio.getAttribute("target")).toBe("_blank");
    expect(propio.getAttribute("rel")).toBe("noopener noreferrer");
    expect(within(screen.getByTestId("spend-case-detail")).queryByRole("link")).toBe(propio);

    fireEvent.change(selector, { target: { value: "0" } });
    expect(screen.queryByTestId("spend-case-langfuse-link")).toBeNull();
  });

  it("el caso propio sin traza lista no lleva enlace, y una comparacion tampoco", async () => {
    const comparacion: ComparisonSpendItem = {
      key: "c0",
      started_at: "2026-10-11T20:02:00Z",
      yours: true,
      total: { measured_usd: "0.03", unmeasured_count: 3 },
      unpriced: GRATIS,
      parts: [
        { tenant_id: "otra-aseguradora", total: { measured_usd: "0.01", unmeasured_count: 1 } },
        { tenant_id: "tercera-aseguradora", total: { measured_usd: "0.02", unmeasured_count: 1 } },
      ],
    };
    servir(
      panel({
        langfuse_url: TRAZA,
        cases: [caso({ key: "0", yours: true, trace_url: null })],
        comparisons: [comparacion],
      }),
    );
    await dibujar(idioma);

    const selector = screen.getByTestId<HTMLSelectElement>("spend-case-select");
    // La comparacion propia abre elegida y no tiene enlace propio.
    expect(selector.value).toBe("c0");
    expect(screen.queryByTestId("spend-case-langfuse-link")).toBeNull();
    fireEvent.change(selector, { target: { value: "0" } });
    expect(screen.queryByTestId("spend-case-langfuse-link")).toBeNull();
    // El de arriba sigue donde estaba.
    expect(screen.queryByTestId("spend-langfuse-link")).not.toBeNull();
  });
});

describe.each<Locale>(["es", "en"])("las cifras caben en su tarjeta, en %s", (idioma) => {
  const TARJETAS = ["spend-total", "spend-budget", "spend-per-call", "spend-per-chat"] as const;

  it("la cifra se adapta al ancho de la tarjeta y no tiene un tamano fijo que se desborde", async () => {
    servir(
      panel({
        total: { measured_usd: "38.33", unmeasured_count: 0 },
        chats: { count: 1, total: { measured_usd: "0.000684", unmeasured_count: 0 } },
      }),
    );
    await dibujar(idioma);

    for (const id of ["spend-total", "spend-per-chat"]) {
      const tarjeta = screen.getByTestId(id);
      const cifra = within(tarjeta).getByTestId("spend-figure");
      // La tarjeta es el contenedor; el tamano sale de su ancho y de cuantos
      // caracteres tiene la cifra, con un techo y un piso, y nunca de un valor fijo.
      expect(tarjeta.className).toContain("@container");
      expect(cifra.className).toContain("cqi");
      expect(cifra.className).toContain("clamp(");
      expect(cifra.className).not.toMatch(/(^|\s)text-figure(\s|$)/);
      expect(cifra.style.getPropertyValue("--figure-chars")).toBe(String(cifra.textContent.length));
    }
    // La mas larga mide mas, asi que se le pide un tamano menor que a la corta.
    const larga = within(screen.getByTestId("spend-per-chat")).getByTestId("spend-figure");
    const corta = within(screen.getByTestId("spend-total")).getByTestId("spend-figure");
    expect(larga.textContent).toMatch(/0[.,]000684/);
    expect(Number(larga.style.getPropertyValue("--figure-chars"))).toBeGreaterThan(
      Number(corta.style.getPropertyValue("--figure-chars")),
    );
  });

  it("la cifra nunca se recorta con puntos suspensivos: si no cabe, parte la linea", async () => {
    servir(
      panel({ chats: { count: 1, total: { measured_usd: "0.000684", unmeasured_count: 0 } } }),
    );
    await dibujar(idioma);

    for (const id of TARJETAS) {
      const tarjeta = screen.getByTestId(id);
      expect(tarjeta.innerHTML).not.toMatch(/truncate|text-ellipsis|overflow-hidden/);
      expect(tarjeta.className).toContain("@container");
    }
    const cifra = within(screen.getByTestId("spend-per-chat")).getByTestId("spend-figure");
    expect(cifra.className).toContain("[overflow-wrap:anywhere]");
  });

  it("la frase de 'todavia sin datos' parte la linea en vez de salirse", async () => {
    servir(panel({ calls: { count: 0, total: { measured_usd: "0", unmeasured_count: 0 } } }));
    const t = await dibujar(idioma);

    const tarjeta = screen.getByTestId("spend-per-call");
    const frase = within(tarjeta).getByText(t("spend_panel.kpi.none_yet"));
    expect(frase.className).toContain("[overflow-wrap:anywhere]");
  });

  it("el hueco de la dona tambien adapta la cifra del centro", async () => {
    servir(panel());
    await dibujar(idioma);

    const centro = screen.getByTestId("spend-donut-center");
    expect(centro.className).toContain("cqi");
    expect(centro.style.getPropertyValue("--figure-chars")).toBe(String(centro.textContent.length));
  });
});

describe("el panel 'En que se va'", () => {
  it("pone la dona en el centro y la leyenda debajo, a todo el ancho", async () => {
    servir(panel());
    await dibujar("es");

    const panelDeActividad = screen.getByTestId("spend-activity");
    const leyenda = panelDeActividad.querySelector("ul");
    const dona = screen
      .getByTestId("spend-donut-center")
      .closest("svg, div[class*='aspect-square']");
    const contenedor = leyenda?.parentElement;
    expect(contenedor).not.toBeNull();
    // Una columna centrada, y no dona a un lado con la leyenda al otro.
    expect(contenedor?.className).toContain("flex-col");
    expect(contenedor?.className).toContain("items-center");
    expect(contenedor?.className).not.toMatch(/flex-row/);
    expect(leyenda?.className).toContain("w-full");
    expect(contenedor?.contains(dona)).toBe(true);
  });
});

describe("las aclaraciones de los importes (E4, 2026-10-12)", () => {
  /** Chat con una aclaracion ("+ 2 consultas · plan gratuito") y lectura de polizas con la suya. */
  function conAclaraciones(): SpendPanel {
    const base = panel();
    return panel({
      by_activity: base.by_activity.map((a) =>
        a.activity === "chat"
          ? { ...a, unpriced: { tokens: 0, uncounted: 2, free_plan: true } }
          : a,
      ),
      by_provider: base.by_provider.map((p) =>
        p.provider === "anthropic"
          ? { ...p, unpriced: { tokens: 0, uncounted: 761, free_plan: true } }
          : p,
      ),
    });
  }

  it("'En que se va' deja solo la cifra de cada fila: sin 'plan gratuito' ni '+ N consultas' debajo", async () => {
    servir(conAclaraciones());
    const t = await dibujar("es");

    const actividad = screen.getByTestId("spend-activity");
    expect(within(actividad).queryByTestId("spend-amount-note")).toBeNull();
    expect(actividad.textContent).not.toContain(t("spend_panel.tokens.free_plan"));
    expect(actividad.textContent).not.toMatch(/consultas/);
    // Y cada fila sigue diciendo su cifra: la de lectura de polizas en tokens, como siempre.
    const lectura = within(actividad)
      .getByText(t("spend_panel.activity.policy_reading"))
      .closest("li");
    expect(lectura?.textContent).toMatch(/12[.,]345/);
  });

  it("'Quien cobra' pone la aclaracion por ENCIMA de la cifra y no debajo", async () => {
    servir(conAclaraciones());
    const t = await dibujar("es");

    const fila = within(screen.getByTestId("spend-providers"))
      .getByText(t("spend_panel.provider.anthropic"))
      .closest("li");
    const nota = within(fila as HTMLElement).getByTestId("spend-amount-note");
    // La cifra es el importe en dolares de la fila: va despues de la nota en el documento.
    const cifra = Array.from((fila as HTMLElement).querySelectorAll("span")).find((nodo) =>
      /0[.,]4/.test(nodo.textContent),
    );
    expect(nota.textContent).toContain(t("spend_panel.tokens.free_plan"));
    expect(cifra).toBeDefined();
    expect(
      (cifra as HTMLElement).compareDocumentPosition(nota) & Node.DOCUMENT_POSITION_PRECEDING,
    ).toBeTruthy();
    // Y no se repite debajo de la cifra.
    expect(within(fila as HTMLElement).getAllByTestId("spend-amount-note")).toHaveLength(1);
  });

  it("si alguna fila de 'Quien cobra' tiene aclaracion, las demas guardan su renglon: las filas miden igual por dentro", async () => {
    servir(conAclaraciones());
    const t = await dibujar("es");

    const filas = within(screen.getByTestId("spend-providers"))
      .getAllByRole("listitem")
      .filter((nodo) => nodo.parentElement?.tagName === "UL" && nodo.querySelector("div"));
    expect(filas.length).toBeGreaterThanOrEqual(2);
    // Todas empiezan con un renglon de aclaracion --real o vacio-- antes de la fila del nombre.
    for (const fila of filas) {
      const primero = fila.firstElementChild;
      expect(primero?.tagName).toBe("SPAN");
      const nombre = primero?.nextElementSibling?.textContent ?? "";
      expect(
        [t("spend_panel.provider.anthropic"), t("spend_panel.provider.gemini")].some((esperado) =>
          nombre.includes(esperado),
        ),
      ).toBe(true);
    }
  });

  it("sin ninguna aclaracion no se reserva renglon alguno", async () => {
    servir(
      panel({
        by_provider: [
          {
            provider: "anthropic",
            total: { measured_usd: "0.40", unmeasured_count: 0 },
          },
          {
            provider: "gemini",
            total: { measured_usd: "0.20", unmeasured_count: 0 },
          },
        ],
      }),
    );
    const t = await dibujar("es");

    const fila = within(screen.getByTestId("spend-providers"))
      .getByText(t("spend_panel.provider.anthropic"))
      .closest("li");
    expect(fila?.firstElementChild?.tagName).toBe("DIV");
  });

  it("el detalle de un caso suelto conserva su aclaracion debajo de la cifra", async () => {
    // El cambio es de los dos paneles de arriba; el detalle de un caso no se toca.
    const base = panel();
    servir(
      panel({
        cases: [
          caso({
            key: "0",
            yours: true,
            total: { measured_usd: "0", unmeasured_count: 1 },
            by_provider: [
              {
                provider: "gemini",
                total: { measured_usd: "0", unmeasured_count: 1 },
                unpriced: { tokens: 500, uncounted: 0, free_plan: true },
              },
            ],
          }),
        ],
        by_provider: base.by_provider,
      }),
    );
    const t = await dibujar("es");

    const detalle = within(screen.getByTestId("spend-case-detail"));
    expect(detalle.getByTestId("spend-amount-note").textContent).toBe(
      t("spend_panel.tokens.free_plan"),
    );
  });
});

describe("cuando el tablero no carga", () => {
  it("lo dice y ofrece reintentar", async () => {
    quitar = installFakeServer(() => problemResponse("internal", 500));
    renderWithProviders(<SpendDashboard />, "es");
    await waitFor(() => {
      expect(screen.queryByTestId("spend-error")).not.toBeNull();
    });
    expect(within(screen.getByTestId("spend-error")).getByRole("button")).toBeTruthy();
  });
});
