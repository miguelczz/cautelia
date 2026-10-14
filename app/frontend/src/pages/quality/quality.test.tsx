import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { renderWithProviders } from "../../app/testing";
import { installFakeServer, jsonResponse } from "../../shared/api-client/fake-server";
import type { QualityBoard } from "../../shared/api-client/quality";
import type { Locale } from "../../shared/copy/copy-keys";
import { createTranslate } from "../../shared/i18n/translate";
import { QualityDashboard } from "./quality-dashboard";

// El tablero "Que tan bien funciona" (2026-10-11). Lo que no se puede romper: los dos
// idiomas van lado a lado y no se suman; una regla dura que no se midio no sale en
// verde; un fallo que detiene la entrega se marca; y sin corrida guardada no se
// inventa ninguna cifra.

let quitar: (() => void) | undefined;

function tablero(cambios: Partial<QualityBoard> = {}): QualityBoard {
  return {
    run_id: "run-1",
    commit_sha: "abc1234def",
    produced_at: "2026-10-11T17:30:00Z",
    duration_seconds: 372,
    comparable: false,
    dirty_tree: false,
    models: ["claude-haiku-5-5", "gemini-embedding-001"],
    totals: {
      es: { passed: 80, failed: 5, not_measured: 4 },
      en: { passed: 82, failed: 3, not_measured: 4 },
    },
    datasets: [
      {
        dataset: "DS-3",
        by_language: {
          es: { passed: 17, failed: 3, not_measured: 0 },
          en: { passed: 19, failed: 1, not_measured: 0 },
        },
      },
    ],
    gates: [
      {
        family: "citations",
        by_language: {
          es: { passed: 20, failed: 0, not_measured: 0 },
          en: { passed: 19, failed: 1, not_measured: 0 },
        },
      },
      {
        family: "isolation",
        by_language: {
          es: { passed: 0, failed: 0, not_measured: 0 },
          en: { passed: 0, failed: 0, not_measured: 0 },
        },
      },
    ],
    failures: [
      {
        case_key: "DS-3/en/no-clause-earthquake",
        dataset: "DS-3",
        language: "en",
        criteria: ["citation_exists_no_clause_earthquake"],
        blocking: true,
        root_cause: null,
      },
      {
        case_key: "DS-3/es/endorsement-electronics",
        dataset: "DS-3",
        language: "es",
        criteria: ["citation_endorsement_electronics"],
        blocking: false,
        root_cause: "retrieval",
      },
    ],
    not_measured: [{ cause: "target_unavailable", count: 8 }],
    ...cambios,
  };
}

function servir(respuesta: QualityBoard | null): void {
  quitar = installFakeServer((ruta) =>
    ruta === "/api/quality" ? jsonResponse(respuesta) : jsonResponse({}, 404),
  );
}

async function dibujar(locale: Locale = "es") {
  renderWithProviders(<QualityDashboard />, locale);
  await waitFor(() => {
    expect(
      screen.queryByTestId("quality-dashboard") ?? screen.queryByTestId("quality-empty"),
    ).not.toBeNull();
  });
  return createTranslate(locale);
}

afterEach(() => {
  quitar?.();
  quitar = undefined;
});

describe("el tablero de la ultima evaluacion", () => {
  it("muestra cada idioma con su propio recuento y nunca uno combinado", async () => {
    servir(tablero());
    const t = await dibujar();

    const espanol = screen.getByTestId("quality-total-es").textContent;
    const ingles = screen.getByTestId("quality-total-en").textContent;
    expect(espanol).toContain(t("quality.totals.passed", { passed: "80", total: "89" }));
    expect(ingles).toContain(t("quality.totals.passed", { passed: "82", total: "89" }));
    // 162 de 178 seria el promedio de los dos: no se dibuja en ninguna parte.
    expect(screen.getByTestId("quality-dashboard").textContent).not.toContain("162");
  });

  it("una regla dura dice si paso, cuantas fallan, o que no se midio", async () => {
    servir(tablero());
    const t = await dibujar();

    const reglas = within(screen.getByTestId("quality-gates")).getAllByRole("listitem");
    const citas = reglas.find((r) => r.textContent.includes(t("quality.gate.citations")));
    const aislamiento = reglas.find((r) => r.textContent.includes(t("quality.gate.isolation")));
    expect(citas?.textContent).toContain(t("quality.gate.all_passed", { total: "20" }));
    expect(citas?.textContent).toContain(
      t("quality.gate.some_failed", { failed: "1", total: "20" }),
    );
    // No medida no es verde: es lo que distingue "paso" de "nadie lo miro".
    expect(aislamiento?.textContent).toContain(t("quality.gate.not_measured"));
    expect(aislamiento?.textContent).not.toContain(t("quality.gate.all_passed", { total: "0" }));
  });

  it("empieza diciendo en una frase que se mide y con cuantas situaciones", async () => {
    servir(tablero());
    const t = await dibujar();

    // 89 en espanol y 89 en ingles: el examen completo, no un promedio de resultados.
    expect(screen.getByTestId("quality-intro").textContent).toContain(
      t("quality.intro", { total: "178" }),
    );
  });

  it("los fallos se dicen en palabras, con su referencia, y el que rompe una regla dura se marca", async () => {
    servir(tablero());
    const t = await dibujar();

    const fallos = within(screen.getByTestId("quality-failures")).getAllByRole("listitem");
    expect(fallos).toHaveLength(2);
    // Primero que tipo de prueba y en que idioma; el identificador, como referencia.
    expect(fallos[0]?.textContent).toContain(t("quality.dataset.ds3.name"));
    expect(fallos[0]?.textContent).toContain(t("quality.lang.en"));
    expect(fallos[0]?.textContent).toContain("DS-3/en/no-clause-earthquake");
    expect(fallos[0]?.textContent).toContain(t("quality.failures.blocking"));
    expect(fallos[1]?.textContent).not.toContain(t("quality.failures.blocking"));
    expect(fallos[1]?.textContent).toContain(t("quality.cause.retrieval"));
  });

  it("lo que no se midio se dice con su motivo, en palabras", async () => {
    servir(tablero());
    const t = await dibujar();

    const pendiente = screen.getByTestId("quality-pending").textContent;
    expect(pendiente).toContain(t("quality.pending.count", { count: "8" }));
    expect(pendiente).toContain(t("quality.pending.target_unavailable"));
    expect(pendiente).not.toContain("target_unavailable");
  });

  it("dice cuanto duro a la vista y, al abrir los detalles tecnicos, con que modelos corrio", async () => {
    servir(tablero());
    const t = await dibujar();

    expect(screen.getByTestId("quality-intro").textContent).toContain(
      t("quality.run.duration", { minutes: "6" }),
    );
    // Lo tecnico no estorba a quien llega: esta plegado hasta que alguien lo pide.
    expect(screen.queryByText("claude-haiku-5-5")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: t("quality.run.details") }));

    const corrida = screen.getByTestId("quality-run").textContent;
    expect(corrida).toContain("claude-haiku-5-5");
    expect(corrida).toContain(t("quality.run.commit", { commit: "abc1234" }));
    expect(corrida).toContain(t("quality.run.not_comparable"));
  });

  it("el desglose por tipo de prueba esta plegado y se abre a pedido", async () => {
    servir(tablero());
    const t = await dibujar();

    const desglose = screen.getByTestId("quality-datasets");
    expect(within(desglose).queryAllByRole("listitem")).toHaveLength(0);

    await userEvent.click(screen.getByRole("button", { name: t("quality.datasets.title") }));

    expect(within(desglose).getAllByRole("listitem").length).toBeGreaterThan(0);
  });

  it("sin ninguna corrida guardada lo dice, sin inventar cifras", async () => {
    servir(null);
    const t = await dibujar();

    expect(screen.getByTestId("quality-empty").textContent).toBe(t("quality.empty"));
    expect(screen.queryByTestId("quality-totals")).toBeNull();
  });

  it("sin fallos lo dice en vez de dejar la lista vacia", async () => {
    servir(tablero({ failures: [] }));
    const t = await dibujar("en");

    expect(screen.getByTestId("quality-failures").textContent).toContain(
      t("quality.failures.none"),
    );
  });
});
