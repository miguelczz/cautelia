import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../app/testing";
import type { TriageNoteIn, TriageNoteView } from "../../shared/api-client/inbox";
import type { ProblemView } from "../../shared/api-client/problems";
import { createTranslate } from "../../shared/i18n/translate";
import { formatPesos } from "../policies/policies-page";
import {
  exampleAmounts,
  internalAmount,
  VisitorTriageBlock,
  type TriageSaveResult,
} from "./visitor-triage";

// La version guiada de «anotar para las reglas», para el visitante que hace de ajustador: el
// monto en pesos con su ayuda y sus ejemplos, dos preguntas con una linea de ayuda cada una, y
// lo que las reglas dijeron al guardar. Los montos de la ayuda llegan del servidor; la pantalla
// no escribe ninguna cifra.

const t = createTranslate("es");

const guardar = vi.hoisted(() => vi.fn<(note: TriageNoteIn) => Promise<TriageSaveResult>>());

const GUARDADO: TriageSaveResult = {
  ok: true,
  outcome: { ruleCategory: "referral", firedRules: ["SUN-R-03", "SUN-R-07"], changed: true },
};

function dibujar(
  props: Partial<React.ComponentProps<typeof VisitorTriageBlock>> = {},
  locale: "es" | "en" = "es",
) {
  return renderWithProviders(
    <VisitorTriageBlock
      note={null}
      canAnnotate
      amountSteps={[1000, 10000]}
      onSave={guardar}
      {...props}
    />,
    locale,
  );
}

/** El bloque, sin los avisos compartidos que la aplicacion monta alrededor. */
const bloque = () => within(screen.getByTestId("visitor-triage"));
const monto = () => screen.getByLabelText<HTMLInputElement>(t("visitor.triage.amount_label"));
const cobertura = () =>
  screen.getByLabelText<HTMLSelectElement>(t("visitor.triage.coverage_label"));
const fraude = () => screen.getByLabelText<HTMLSelectElement>(t("visitor.triage.fraud_label"));
const guardarBoton = () => screen.getByRole("button", { name: t("visitor.triage.save") });

/** Lo que un lector de pantalla lee como descripcion de un control. */
function descripcionDe(control: HTMLElement): string {
  return (control.getAttribute("aria-describedby") ?? "")
    .split(" ")
    .filter((id) => id !== "")
    .map((id) => document.getElementById(id)?.textContent ?? "")
    .join(" | ");
}

beforeEach(() => {
  guardar.mockReset();
  guardar.mockResolvedValue(GUARDADO);
});

describe("los ejemplos y la cifra interna", () => {
  it("con dos umbrales: la mitad del primero, el punto medio y el doble del ultimo", () => {
    expect(exampleAmounts([1000, 10000])).toEqual([500, 5500, 20000]);
  });

  it("con un solo umbral no hay punto medio", () => {
    expect(exampleAmounts([1000])).toEqual([500, 2000]);
  });

  it("con varios umbrales usa el primero y el ultimo, no los de en medio", () => {
    expect(exampleAmounts([1000, 4000, 10000])).toEqual([500, 5500, 20000]);
  });

  it("sin umbrales no hay ejemplos", () => {
    expect(exampleAmounts([])).toEqual([]);
  });

  it.each([
    [2_500_000, 2500],
    [2_500_499, 2500],
    [2_500_500, 2501],
    [499, 0],
    [500, 1],
    [0, 0],
  ])("%i pesos se anotan como %i, en miles redondeados", (pesos, interna) => {
    expect(internalAmount(pesos)).toBe(interna);
  });
});

describe("cuando se ofrece anotar", () => {
  it("dibuja el titulo, la introduccion y las tres preguntas con «No lo he revisado» por omision", () => {
    dibujar();

    expect(screen.getByRole("heading", { name: t("visitor.triage.title") })).toBeTruthy();
    expect(screen.getByTestId("visitor-triage").textContent).toContain(t("visitor.triage.intro"));
    expect(monto().value).toBe("");
    expect(cobertura().value).toBe("unset");
    expect(fraude().value).toBe("unset");
    expect(
      within(cobertura())
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual([
      t("visitor.triage.unset"),
      t("inbox.triage.answer_yes"),
      t("inbox.triage.answer_no"),
    ]);
  });

  it("arranca con lo ya anotado, el monto en pesos, y un «no» no se confunde con «sin anotar»", () => {
    const nota: TriageNoteView = {
      claim_amount: 2500,
      coverage_disputed: false,
      fraud_suspected: null,
    };
    dibujar({ note: nota });

    expect(monto().value).toBe("2500000");
    expect(cobertura().value).toBe("no");
    expect(fraude().value).toBe("unset");
  });

  it("cada pregunta lleva su ayuda, asociada al control", () => {
    dibujar();

    expect(descripcionDe(cobertura())).toBe(t("visitor.triage.coverage_help"));
    expect(descripcionDe(fraude())).toBe(t("visitor.triage.fraud_help"));
    expect(descripcionDe(monto())).toContain(
      t("visitor.triage.amount_help", {
        first: formatPesos(1000, "es"),
        last: formatPesos(10000, "es"),
      }),
    );
  });

  it("con dos o mas umbrales la ayuda dice el primero y el ultimo, escritos por el servidor", () => {
    dibujar({ amountSteps: [2000, 5000, 30000] });

    const ayuda = descripcionDe(monto());
    expect(ayuda).toContain(formatPesos(2000, "es"));
    expect(ayuda).toContain(formatPesos(30000, "es"));
    expect(ayuda).not.toContain(formatPesos(5000, "es"));
  });

  it("con un umbral lo dice una vez, y con ninguno la ayuda no lleva cifras", () => {
    const { unmount } = dibujar({ amountSteps: [3000] });
    expect(descripcionDe(monto())).toBe(
      t("visitor.triage.amount_help_one", { first: formatPesos(3000, "es") }),
    );
    unmount();

    dibujar({ amountSteps: [] });
    expect(descripcionDe(monto())).toBe(t("visitor.triage.amount_help_none"));
    expect(screen.queryByTestId("visitor-triage-examples")).toBeNull();
  });

  it("sin la lista de umbrales (el servidor no la mando) tampoco inventa cifras", () => {
    dibujar({ amountSteps: undefined });

    expect(descripcionDe(monto())).toBe(t("visitor.triage.amount_help_none"));
    expect(screen.queryByTestId("visitor-triage-examples")).toBeNull();
  });

  it("ofrece tres ejemplos con dos umbrales y dos con uno, y tocar uno llena el campo en pesos", async () => {
    const { unmount } = dibujar();

    const ejemplos = within(screen.getByTestId("visitor-triage-examples"));
    expect(ejemplos.getByText(t("visitor.triage.amount_examples"))).toBeTruthy();
    expect(ejemplos.getAllByRole("button").map((b) => b.textContent)).toEqual([
      formatPesos(500, "es"),
      formatPesos(5500, "es"),
      formatPesos(20000, "es"),
    ]);
    await userEvent.click(ejemplos.getByRole("button", { name: formatPesos(5500, "es") }));
    expect(monto().value).toBe("5500000");
    // Y no envia nada: un ejemplo llena el campo, guardar es otra decision.
    expect(guardar).not.toHaveBeenCalled();
    unmount();

    dibujar({ amountSteps: [1000] });
    expect(
      within(screen.getByTestId("visitor-triage-examples"))
        .getAllByRole("button")
        .map((b) => b.textContent),
    ).toEqual([formatPesos(500, "es"), formatPesos(2000, "es")]);
  });

  it("debajo del monto se lee como se va a anotar, redondeado al millar", async () => {
    dibujar();

    await userEvent.type(monto(), "2500400");

    expect(screen.getByTestId("visitor-triage-amount-preview").textContent).toBe(
      t("visitor.triage.amount_preview", { amount: formatPesos(2500, "es") }),
    );
    expect(descripcionDe(monto())).toContain(
      t("visitor.triage.amount_preview", { amount: formatPesos(2500, "es") }),
    );
  });

  it("sin monto escrito no hay vista previa", () => {
    dibujar();

    expect(screen.queryByTestId("visitor-triage-amount-preview")).toBeNull();
  });
});

describe("guardar", () => {
  it("manda el monto en miles, las respuestas y deja en null lo que no se reviso", async () => {
    dibujar();

    await userEvent.type(monto(), "2500400");
    await userEvent.selectOptions(fraude(), "yes");
    await userEvent.click(guardarBoton());

    expect(guardar).toHaveBeenCalledTimes(1);
    expect(guardar).toHaveBeenCalledWith({
      claim_amount: 2500,
      coverage_disputed: null,
      fraud_suspected: true,
    });
  });

  it("con todo sin revisar manda los tres en null, que es dejar de anotar", async () => {
    dibujar({ note: { claim_amount: 2500, coverage_disputed: true, fraud_suspected: false } });

    await userEvent.clear(monto());
    await userEvent.selectOptions(cobertura(), "unset");
    await userEvent.selectOptions(fraude(), "unset");
    await userEvent.click(guardarBoton());

    expect(guardar).toHaveBeenCalledWith({
      claim_amount: null,
      coverage_disputed: null,
      fraud_suspected: null,
    });
  });

  it("un «No» es una respuesta y se manda como falso, no como sin revisar", async () => {
    dibujar();

    await userEvent.selectOptions(cobertura(), "no");
    await userEvent.click(guardarBoton());

    expect(guardar).toHaveBeenCalledWith({
      claim_amount: null,
      coverage_disputed: false,
      fraud_suspected: null,
    });
  });

  it("dice como quedo clasificado el caso: que se evaluo otra vez, la frase de la categoria y las reglas", async () => {
    dibujar();

    await userEvent.type(monto(), "2500000");
    await userEvent.click(guardarBoton());

    const linea = await screen.findByText(
      t("inbox.rule.reference", { rules: "SUN-R-03, SUN-R-07" }),
      {
        exact: false,
      },
    );
    const estado = screen.getByTestId("visitor-triage-result");
    expect(estado.getAttribute("role")).toBe("status");
    expect(estado.contains(linea)).toBe(true);
    expect(estado.textContent).toContain(t("visitor.triage.result"));
    expect(estado.textContent).toContain(t("inbox.rule.reason.referral"));
    expect(estado.textContent).toContain(
      t("inbox.rule.reference", { rules: "SUN-R-03, SUN-R-07" }),
    );
    // Ni la categoria cruda ni un identificador interno sin su frase.
    expect(estado.textContent).not.toContain("referral");
  });

  it("la region de estado existe antes de guardar, para que se anuncie lo que llegue", () => {
    dibujar();

    expect(screen.getByTestId("visitor-triage-result").getAttribute("role")).toBe("status");
    expect(screen.getByTestId("visitor-triage-result").textContent).toBe("");
  });

  it("si se guardo lo que ya estaba no dice que las reglas volvieron a evaluar", async () => {
    guardar.mockResolvedValue({
      ok: true,
      outcome: { ruleCategory: "standard_review", firedRules: ["SUN-R-10"], changed: false },
    });
    dibujar();

    await userEvent.click(guardarBoton());

    const estado = await screen.findByText(t("inbox.rule.reason.standard_review"), {
      exact: false,
    });
    expect(estado.textContent).not.toContain(t("visitor.triage.result"));
    expect(estado.textContent).toContain(t("inbox.rule.reference", { rules: "SUN-R-10" }));
  });

  it("sin evaluacion que contar (nada anotado todavia) la region sigue vacia", async () => {
    guardar.mockResolvedValue({
      ok: true,
      outcome: { ruleCategory: null, firedRules: [], changed: false },
    });
    dibujar();

    await userEvent.click(guardarBoton());

    await screen.findByTestId("visitor-triage-result");
    expect(guardar).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("visitor-triage-result").textContent).toBe("");
  });

  it("al cambiar cualquier control, la linea de la vez anterior se apaga", async () => {
    dibujar();
    await userEvent.click(guardarBoton());
    await screen.findByText(t("visitor.triage.result"), { exact: false });

    await userEvent.selectOptions(fraude(), "yes");

    expect(screen.getByTestId("visitor-triage-result").textContent).toBe("");
  });

  it("un monto con puntos, comas o letras no se manda: avisa en una alerta y lo escrito sigue", async () => {
    dibujar();

    await userEvent.type(monto(), "2.500.000");
    await userEvent.click(guardarBoton());

    const alerta = bloque().getByRole("alert");
    expect(alerta.textContent).toBe(t("visitor.triage.amount_invalid"));
    expect(guardar).not.toHaveBeenCalled();
    expect(monto().value).toBe("2.500.000");
    expect(monto().getAttribute("aria-invalid")).toBe("true");
    expect(descripcionDe(monto())).toContain(t("visitor.triage.amount_invalid"));
    // Y se apaga en cuanto se corrige.
    await userEvent.clear(monto());
    await userEvent.type(monto(), "2500000");
    expect(bloque().queryByRole("alert")).toBeNull();
  });

  it("si falla, el error sale del catalogo, lo escrito se queda y no hay linea de resultado", async () => {
    const problema: ProblemView = {
      code: "conflict_state",
      message: (tt) => tt("visitor.triage.limit"),
    };
    guardar.mockResolvedValue({ ok: false, problem: problema });
    dibujar();

    await userEvent.type(monto(), "2500000");
    await userEvent.selectOptions(fraude(), "yes");
    await userEvent.click(guardarBoton());

    expect((await screen.findByTestId("visitor-triage-problem")).textContent).toBe(
      t("visitor.triage.limit"),
    );
    expect(bloque().getByRole("alert").textContent).toBe(t("visitor.triage.limit"));
    expect(monto().value).toBe("2500000");
    expect(fraude().value).toBe("yes");
    expect(screen.getByTestId("visitor-triage-result").textContent).toBe("");
  });
});

describe("cuando ya no se puede anotar", () => {
  it("lee lo que el visitante anoto con las mismas etiquetas llanas, sin formulario", () => {
    dibujar({
      canAnnotate: false,
      note: { claim_amount: 2500, coverage_disputed: false, fraud_suspected: null },
    });

    const bloque = within(screen.getByTestId("visitor-triage"));
    expect(bloque.getByTestId("visitor-triage-amount-value").textContent).toBe(
      formatPesos(2500, "es"),
    );
    expect(bloque.getByTestId("visitor-triage-coverage-value").textContent).toBe(
      t("inbox.triage.answer_no"),
    );
    expect(bloque.getByTestId("visitor-triage-fraud-value").textContent).toBe(
      t("visitor.triage.unset"),
    );
    expect(bloque.getByText(t("visitor.triage.coverage_label"))).toBeTruthy();
    expect(screen.queryByTestId("visitor-triage-form")).toBeNull();
    expect(screen.queryByRole("button", { name: t("visitor.triage.save") })).toBeNull();
  });

  it("un monto sin anotar se lee «No lo he revisado» y no cero", () => {
    dibujar({
      canAnnotate: false,
      note: { claim_amount: null, coverage_disputed: true, fraud_suspected: null },
    });

    expect(screen.getByTestId("visitor-triage-amount-value").textContent).toBe(
      t("visitor.triage.unset"),
    );
  });

  it("sin nada anotado y sin nada que avisar, el bloque no existe", () => {
    dibujar({ canAnnotate: false, note: null });

    expect(screen.queryByTestId("visitor-triage")).toBeNull();
  });

  it("si el servidor dejo de ofrecerlo tras un rechazo, conserva el aviso con lo anotado", async () => {
    guardar.mockResolvedValue({
      ok: false,
      problem: { code: "conflict_state", message: (tt) => tt("visitor.triage.limit") },
    });
    // La pagina, que tras el rechazo vuelve a leer el caso y deja de ofrecer anotar.
    function Pagina() {
      const [puede, setPuede] = useState(true);
      return (
        <VisitorTriageBlock
          note={{ claim_amount: null, coverage_disputed: null, fraud_suspected: true }}
          canAnnotate={puede}
          amountSteps={puede ? [1000] : undefined}
          onSave={async (nota) => {
            const respuesta = await guardar(nota);
            setPuede(false);
            return respuesta;
          }}
        />
      );
    }
    renderWithProviders(<Pagina />);

    await userEvent.selectOptions(fraude(), "no");
    await userEvent.click(guardarBoton());

    expect((await screen.findByTestId("visitor-triage-problem")).textContent).toBe(
      t("visitor.triage.limit"),
    );
    expect(screen.queryByTestId("visitor-triage-form")).toBeNull();
    expect(screen.getByTestId("visitor-triage-fraud-value").textContent).toBe(
      t("inbox.triage.answer_yes"),
    );
  });
});

// El bloque es el primer paso del panel del ajustador (2026-10-14): su titulo es un encabezado de
// nivel 3 --cuelga del titulo del panel-- y lleva una marca numerica solo cuando el panel tiene
// mas de un paso.
describe("el titulo como paso del panel", () => {
  it("con numero de paso lleva su marca, oculta para el lector de pantalla, y el titulo es de nivel 3", () => {
    dibujar({ step: 1 });

    // El nombre accesible es el titulo solo: la marca no se lee.
    const titulo = screen.getByRole("heading", { level: 3, name: t("visitor.triage.title") });
    const marca = within(titulo).getByTestId("step-mark");
    expect(marca.textContent).toBe("1");
    expect(marca.getAttribute("aria-hidden")).toBe("true");
    expect(marca.className).toContain("bg-brand");
    expect(marca.className).toContain("text-on-brand");
    expect(screen.queryByRole("heading", { level: 2 })).toBeNull();
  });

  it("sin numero de paso el titulo no lleva marca", () => {
    dibujar();

    expect(screen.queryByTestId("step-mark")).toBeNull();
    expect(screen.getByRole("heading", { level: 3, name: t("visitor.triage.title") })).toBeTruthy();
  });

  it("la lectura de lo anotado, sin formulario, es el mismo paso con el mismo titulo y su marca", () => {
    dibujar({
      canAnnotate: false,
      note: { claim_amount: 2500, coverage_disputed: false, fraud_suspected: true },
      step: 1,
    });

    expect(screen.queryByTestId("visitor-triage-form")).toBeNull();
    const titulo = screen.getByRole("heading", { level: 3, name: t("visitor.triage.title") });
    expect(within(titulo).getByTestId("step-mark").textContent).toBe("1");
  });
});

describe("lo que lee quien reporto", () => {
  it("no dice una palabra de la jerga del sistema (U-07)", () => {
    dibujar();
    const pantalla = screen.getByTestId("visitor-triage").textContent.toLowerCase();

    for (const jerga of ["bandeja", "derivado", "cola", "inbox", "tenant", "triage", "triaje"]) {
      expect(pantalla).not.toContain(jerga);
    }
  });

  it("en ingles se lee en ingles, con el mismo orden de datos", () => {
    const en = createTranslate("en");
    dibujar({}, "en");

    expect(screen.getByRole("heading", { name: en("visitor.triage.title") })).toBeTruthy();
    expect(screen.getByLabelText(en("visitor.triage.amount_label"))).toBeTruthy();
    expect(screen.getByRole("button", { name: en("visitor.triage.save") })).toBeTruthy();
    expect(screen.getByTestId("visitor-triage-examples").textContent).toContain(
      formatPesos(500, "en"),
    );
  });
});
