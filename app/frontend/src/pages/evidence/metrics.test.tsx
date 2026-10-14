import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import sinLineaBase from "../../../../contracts/examples/metrics-snapshot.json";
import { renderWithProviders } from "../../app/testing";
import {
  installFakeServer,
  jsonResponse,
  problemResponse,
} from "../../shared/api-client/fake-server";
import type {
  Figure,
  FigureSource,
  LatencyMeasure,
  LatencyReading,
  Measurement,
  MetricsSnapshot,
  NotMeasuredCause,
} from "../../shared/api-client/metrics";
import type { Locale } from "../../shared/copy/copy-keys";
import { createTranslate } from "../../shared/i18n/translate";
import { formatDuration } from "./metrics-labels";
import { MetricsPage } from "./metrics-page";

// BR1.2 a BR1.5 y BR2.1 en la pantalla: una celda sin medir dice "No medida" y su
// causa, los dos idiomas van lado a lado sin promedio, y cada cifra medida lleva
// fecha, commit y corrida. El servidor se prueba aparte, con la linea base real.

let quitar: (() => void) | undefined;

function sinMedir(causa: NotMeasuredCause): Measurement {
  return { state: "not_measured", value: null, not_measured_cause: causa };
}

function figuraSinMedir(key: Figure["key"], causa: NotMeasuredCause, idiomas: boolean): Figure {
  return {
    key,
    state: "not_measured",
    not_measured_cause: causa,
    by_language: idiomas ? { es: sinMedir(causa), en: sinMedir(causa) } : {},
    latency:
      key === "latency"
        ? [
            {
              channel: "voice",
              start: "speech_end",
              end: "first_audio",
              dataset: "DS-5",
              percentiles: ["p50", "p95"],
              // Una decision: se mide por hito contra proveedores de verdad.
              not_measured_cause: "measured_per_milestone",
            },
            {
              channel: "chat",
              start: "message_sent",
              end: "first_word",
              dataset: "DS-2",
              percentiles: ["p50", "p95"],
              // Sale de la linea base: sin ninguna, esa es su causa. La causa de este
              // canal **no** es la de la cifra, y el panel tiene que decirlo.
              not_measured_cause: "no_baseline",
            },
          ]
        : [],
    source: null,
  };
}

// La respuesta real del servidor sin linea base (la escribe `mise run contracts:gen`).
const SIN_LINEA_BASE = sinLineaBase as MetricsSnapshot;

function conLineaBase(runUrl: string | null): MetricsSnapshot {
  return {
    baseline_id: "base-0001",
    commit_sha: "0123456789abcdef",
    published_at: "2026-10-01T12:00:00Z",
    run_id: "run-7",
    figures: [
      {
        key: "completeness",
        state: "measured",
        not_measured_cause: null,
        by_language: {
          es: { state: "measured", value: 0.9, not_measured_cause: null },
          en: { state: "measured", value: 0.8, not_measured_cause: null },
        },
        latency: [],
        source: {
          baseline_id: "base-0001",
          published_at: "2026-10-01T12:00:00Z",
          commit_sha: "0123456789abcdef",
          run_id: "run-7",
          run_url: runUrl,
        },
      },
      ...SIN_LINEA_BASE.figures
        .slice(1)
        .map((f) =>
          f.key === "citation_precision"
            ? figuraSinMedir("citation_precision", "criterion_absent", true)
            : f,
        ),
    ],
  };
}

const LECTURAS: Record<"es" | "en", LatencyReading> = {
  es: { state: "measured", p50_ms: 1180, p95_ms: 2810, turns: 52, not_measured_cause: null },
  en: { state: "measured", p50_ms: 420, p95_ms: 3090, turns: 47, not_measured_cause: null },
};

function medidaDeChat(resto: Partial<LatencyMeasure>): LatencyMeasure {
  return {
    channel: "chat",
    start: "message_sent",
    end: "first_word",
    dataset: "DS-2, DS-6",
    percentiles: ["p50", "p95"],
    ...resto,
  };
}

/** El panel con una linea base publicada; `lecturas` es la latencia del chat que trae, o ninguna. */
function conLatencias(lecturas: Record<"es" | "en", LatencyReading> | null): MetricsSnapshot {
  const origen: FigureSource = {
    baseline_id: "base-0001",
    published_at: "2026-10-01T12:00:00Z",
    commit_sha: "0123456789abcdef",
    run_id: "run-7",
    run_url: null,
  };
  const chat =
    lecturas === null
      ? medidaDeChat({ not_measured_cause: "latency_not_in_baseline" })
      : medidaDeChat({ by_language: lecturas, source: origen });
  const base = conLineaBase(null);
  return {
    ...base,
    figures: base.figures.map((f): Figure =>
      f.key === "latency"
        ? { ...f, latency: [...(f.latency ?? []).filter((m) => m.channel === "voice"), chat] }
        : f,
    ),
  };
}

function servir(snapshot: MetricsSnapshot): void {
  quitar = installFakeServer((ruta) =>
    ruta === "/api/metrics" ? jsonResponse(snapshot) : jsonResponse({}, 404),
  );
}

async function dibujar(locale: Locale = "es") {
  renderWithProviders(<MetricsPage />, locale);
  await waitFor(() => {
    expect(screen.queryAllByTestId("metrics-figure").length).toBeGreaterThan(0);
  });
  return createTranslate(locale);
}

function figura(key: string): HTMLElement {
  const encontrada = screen
    .getAllByTestId("metrics-figure")
    .find((nodo) => nodo.getAttribute("data-figure") === key);
  if (encontrada === undefined) {
    throw new Error(`no hay cifra ${key}`);
  }
  return encontrada;
}

/** El renglon de un canal dentro de la cifra de latencias. */
function canal(channel: "voice" | "chat"): HTMLElement {
  const detalle = within(figura("latency")).getByTestId("metrics-latency-detail");
  const encontrado = within(detalle)
    .getAllByRole("listitem")
    .find((nodo) => nodo.getAttribute("data-channel") === channel);
  if (encontrado === undefined) {
    throw new Error(`no hay latencia del canal ${channel}`);
  }
  return encontrado;
}

afterEach(() => {
  quitar?.();
  quitar = undefined;
  vi.restoreAllMocks();
});

describe.each<Locale>(["es", "en"])("el panel de cifras en %s", (idioma) => {
  it("sin linea base, las cinco salen no medidas con su causa y ninguna en cero", async () => {
    servir(SIN_LINEA_BASE);
    const t = await dibujar(idioma);

    expect(screen.getAllByTestId("metrics-figure")).toHaveLength(5);
    expect(screen.getByTestId("metrics-no-baseline").textContent).toContain(
      t("metrics.no_baseline"),
    );
    for (const nodo of screen.getAllByTestId("metrics-figure")) {
      expect(nodo.getAttribute("data-state")).toBe("not_measured");
      expect(nodo.textContent).toContain(t("metrics.not_measured"));
      expect(within(nodo).getAllByTestId("metrics-cause").length).toBeGreaterThan(0);
      expect(nodo.textContent).not.toMatch(/\b0(?:[.,]0)?\s?%/);
      expect(within(nodo).queryByTestId("metrics-source")).toBeNull();
    }
    expect(figura("latency").textContent).toContain(t("metrics.cause.measured_per_milestone"));
    expect(figura("cost_per_case").textContent).toContain(t("metrics.cause.not_connected"));
  });

  it("los dos idiomas van lado a lado y no hay un tercer valor combinado", async () => {
    servir(conLineaBase(null));
    await dibujar(idioma);

    const celdas = within(figura("completeness")).getAllByRole("cell");
    expect(celdas.map((celda) => celda.getAttribute("data-lang"))).toEqual(["es", "en"]);
    const valores = celdas.map((celda) => celda.textContent);
    expect(valores[0]).toMatch(/90/);
    expect(valores[1]).toMatch(/80/);
    // El promedio de los dos seria 85 %: no aparece en ninguna parte.
    expect(figura("completeness").textContent).not.toMatch(/85/);
  });

  it("cada cifra medida lleva fecha, commit corto y corrida; sin enlace, la corrida es texto", async () => {
    servir(conLineaBase(null));
    const t = await dibujar(idioma);

    const origen = within(figura("completeness")).getByTestId("metrics-source");
    expect(origen.textContent).toContain(t("metrics.source.date"));
    expect(origen.textContent).toContain("0123456");
    expect(origen.textContent).not.toContain("0123456789");
    expect(origen.textContent).toContain("run-7");
    expect(within(origen).queryByRole("link")).toBeNull();
  });

  it("con enlace a la corrida, la corrida es un enlace", async () => {
    servir(conLineaBase("https://example.test/runs/run-7"));
    await dibujar(idioma);

    const enlace = within(figura("completeness")).getByRole("link", { name: "run-7" });
    expect(enlace.getAttribute("href")).toBe("https://example.test/runs/run-7");
  });

  it("una cifra con una sola medida mezcla: la medida sale como valor y la otra no medida con causa", async () => {
    servir(conLineaBase(null));
    const t = await dibujar(idioma);

    const citacion = figura("citation_precision");
    expect(citacion.getAttribute("data-state")).toBe("not_measured");
    expect(citacion.textContent).toContain(t("metrics.cause.criterion_absent"));
  });

  it("las latencias dicen entre que eventos, sobre que conjunto y con p50 y p95", async () => {
    servir(SIN_LINEA_BASE);
    const t = await dibujar(idioma);

    const detalle = within(figura("latency")).getByTestId("metrics-latency-detail");
    const voz = within(detalle).getAllByRole("listitem")[0];
    const chat = within(detalle).getAllByRole("listitem")[1];
    expect(voz?.textContent).toContain(
      t("metrics.latency.between", {
        start: t("metrics.latency.event.speech_end"),
        end: t("metrics.latency.event.first_audio"),
      }),
    );
    expect(voz?.textContent).toContain("DS-5");
    expect(voz?.textContent).toContain(t("metrics.latency.percentiles"));
    expect(chat?.textContent).toContain(
      t("metrics.latency.between", {
        start: t("metrics.latency.event.message_sent"),
        end: t("metrics.latency.event.first_word"),
      }),
    );
    // Y cada canal con **su** causa. La de la cifra es "por hito"; la del chat sale de la
    // linea base, y decirle "por hito" manda a esperar un hito donde lo que hay que hacer
    // es publicar una linea base.
    expect(voz?.textContent).toContain(t("metrics.cause.measured_per_milestone"));
    expect(chat?.textContent).toContain(t("metrics.cause.no_baseline"));
    expect(chat?.textContent).not.toContain(t("metrics.cause.measured_per_milestone"));
  });

  it("una linea base que no trae latencias lo dice con su causa verdadera", async () => {
    servir(conLatencias(null));
    const t = await dibujar(idioma);

    const chat = canal("chat");
    expect(chat.textContent).toContain(t("metrics.cause.latency_not_in_baseline"));
    expect(chat.textContent).not.toContain(t("metrics.cause.no_baseline"));
    expect(within(chat).queryAllByRole("cell")).toHaveLength(0);
  });

  it("con latencias en la linea base, el chat muestra la mitad y 95 de cada 100 por idioma, con su recuento", async () => {
    servir(conLatencias(LECTURAS));
    const t = await dibujar(idioma);

    const chat = canal("chat");
    const celdas = within(chat).getAllByRole("cell");
    expect(celdas.map((celda) => celda.getAttribute("data-lang"))).toEqual(["es", "en"]);
    const [es, en] = celdas;
    // Los tiempos con la unidad que corresponde: bajo el segundo en milisegundos, y desde
    // ahi en segundos con una decimal (la mitad hacia arriba, como el README).
    expect(es?.textContent).toContain(
      t("metrics.latency.half", { time: idioma === "es" ? "1,2 s" : "1.2 s" }),
    );
    expect(es?.textContent).toContain(
      t("metrics.latency.most", { time: idioma === "es" ? "2,8 s" : "2.8 s" }),
    );
    expect(es?.textContent).toContain(t("metrics.latency.turns", { count: 52 }));
    expect(en?.textContent).toContain(t("metrics.latency.half", { time: "420 ms" }));
    expect(en?.textContent).toContain(t("metrics.latency.turns", { count: 47 }));
    // Nunca un promedio de los dos idiomas.
    expect(chat.textContent).not.toMatch(/800 ms/);
    // De donde sale y que no cuenta, y la corrida de la que sale.
    expect(within(chat).getByTestId("metrics-latency-environment").textContent).toContain(
      t("metrics.latency.environment_chat"),
    );
    expect(within(within(chat).getByTestId("metrics-source")).getByText("run-7")).toBeTruthy();
    // La voz sigue sin medir, con su causa (no la del chat).
    expect(canal("voice").textContent).toContain(t("metrics.cause.measured_per_milestone"));
  });

  it("con pocos turnos no hay cifra: dice la causa y cuantos turnos hubo", async () => {
    servir(
      conLatencias({
        ...LECTURAS,
        en: {
          state: "not_measured",
          p50_ms: null,
          p95_ms: null,
          turns: 9,
          not_measured_cause: "too_few_turns",
        },
      }),
    );
    const t = await dibujar(idioma);

    const en = within(canal("chat")).getAllByRole("cell")[1];
    expect(en?.querySelector('[data-cell-state="not_measured"]')).not.toBeNull();
    expect(en?.textContent).toContain(t("metrics.cause.too_few_turns"));
    expect(en?.textContent).toContain(t("metrics.latency.turns", { count: 9 }));
    // Ni un tiempo ni un cero donde lo cierto es "no medida".
    expect(en?.textContent).not.toMatch(/\d+(?:[.,]\d)? ?(?:ms|s)\b/);
    expect(en?.textContent).not.toContain(t("metrics.latency.half", { time: "0 ms" }));
  });
});

describe("un tiempo se dice igual en el panel y en el README", () => {
  // La misma tabla que `test_los_tiempos_se_dicen_como_el_panel_los_dice` del README: la
  // mitad hacia arriba, y milisegundos bajo el segundo.
  it.each<[number, string, string]>([
    [0, "0 ms", "0 ms"],
    [999, "999 ms", "999 ms"],
    [1000, "1.0 s", "1,0 s"],
    [1249, "1.2 s", "1,2 s"],
    [1250, "1.3 s", "1,3 s"],
    [12_340, "12.3 s", "12,3 s"],
  ])("%i ms", (ms, ingles, espanol) => {
    expect(formatDuration(ms, "en")).toBe(ingles);
    expect(formatDuration(ms, "es")).toBe(espanol);
  });
});

describe("el panel de cifras no lleva identificadores de caso en las latencias", () => {
  it("lo unico que dibuja es lo que el servidor manda, sin ninguno", async () => {
    servir(conLatencias(LECTURAS));
    await dibujar("es");

    expect(figura("latency").textContent).not.toMatch(/DS-\d\/(es|en)\//);
  });
});

describe("el panel de cifras cuando el servidor falla", () => {
  it("muestra el error del catalogo y deja reintentar, sin cifras inventadas", async () => {
    quitar = installFakeServer(() => problemResponse("internal", 500));
    renderWithProviders(<MetricsPage />, "es");

    await waitFor(() => {
      expect(screen.getByTestId("metrics-error")).toBeTruthy();
    });
    expect(screen.queryAllByTestId("metrics-figure")).toHaveLength(0);
    expect(within(screen.getByTestId("metrics-error")).getByRole("button")).toBeTruthy();
  });
});
