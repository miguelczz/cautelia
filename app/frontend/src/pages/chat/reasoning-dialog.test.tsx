import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import siteExample from "../../../../contracts/examples/site-directory.json";
import { renderWithProviders } from "../../app/testing";
import type { ChatReasoning } from "../../shared/api-client/chat";
import { installFakeServer, jsonResponse } from "../../shared/api-client/fake-server";
import type { Locale } from "../../shared/copy/copy-keys";
import EN_TEXTOS from "../../shared/copy/copy-texts.en";
import ES_TEXTOS from "../../shared/copy/copy-texts.es";
import { createTranslate } from "../../shared/i18n/translate";
import { ReasoningButton } from "./reasoning-dialog";

// La ventana "Pensamiento de la agente": redactada en impersonal (E1, 2026-10-12) y con la
// pregunta como la escribio quien la hizo (C5, 2026-10-12).

const pensamiento = vi.hoisted(() =>
  vi.fn<(tenantId: string, locale: string) => Promise<ChatReasoning | null>>(),
);

vi.mock("../../shared/api-client/chat", async (original) => {
  const real = await original<typeof import("../../shared/api-client/chat")>();
  return { ...real, caseReasoning: pensamiento };
});

const es = createTranslate("es");

function razonamiento(extra: Partial<ChatReasoning> = {}): ChatReasoning {
  return {
    case_number: "SA-140",
    record_type: "coverage_inquiry",
    state: "capturing",
    policy_ref: "POL-11",
    derivation_reason: null,
    fields: [],
    answers: [
      {
        question: "¿Mi póliza [PÓLIZA 1] cubre el granizo?",
        outcome: "no_clause_found",
        clauses: [],
      },
    ],
    ...extra,
  };
}

async function abrir(locale: Locale = "es") {
  // jsdom no trae `showModal`: el navegador si, y es lo que usa la ventana.
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  renderWithProviders(
    <ReasoningButton tenantId="una-aseguradora" label="Pensamiento de Catalina">
      Pensamiento
    </ReasoningButton>,
    locale,
  );
  await userEvent.click(screen.getByTestId("chat-reasoning"));
  return screen.getByTestId("reasoning-dialog");
}

beforeEach(() => {
  pensamiento.mockReset();
  installFakeServer((ruta) =>
    ruta === "/api/site" ? jsonResponse(siteExample) : jsonResponse({}, 404),
  );
});

/**
 * Si un texto habla en primera o segunda persona, de la agente o de quien lee.
 *
 * No es una gramatica: son los pronombres y las formas verbales que tenia la ventana
 * antes de redactarla en impersonal (entendi, confirme, busque, preguntaste, quieres,
 * verás...), mas el patron general de la primera persona del pasado (terminada en e o i
 * acentuadas) con las palabras corrientes que lo parecen.
 */
const NO_ES_PRIMERA_PERSONA = new Set(["sí", "así", "aquí", "ahí", "allí", "qué", "té"]);

function hablaEnPersona(texto: string, idioma: Locale): boolean {
  const palabras = texto.toLowerCase().match(/[\p{L}']+/gu) ?? [];
  if (idioma === "en") {
    return palabras.some((p) =>
      ["i", "me", "my", "we", "you", "your", "you'll", "i'm"].includes(p),
    );
  }
  const pronombres = [
    "yo",
    "me",
    "mi",
    "mis",
    "te",
    "tu",
    "tus",
    "tuya",
    "tuyo",
    "ti",
    "tú",
    "usted",
  ];
  const formasViejas = [
    "quieres",
    "tienes",
    "verás",
    "preguntaste",
    "pienso",
    "busco",
    "tengo",
    "sigo",
    "cuentes",
  ];
  return palabras.some(
    (p) =>
      pronombres.includes(p) ||
      formasViejas.includes(p) ||
      (/^[\p{L}]{3,}[éí]$/u.test(p) && !NO_ES_PRIMERA_PERSONA.has(p)),
  );
}

describe("el pensamiento esta redactado en impersonal (E1, 2026-10-12)", () => {
  const CLAVES_DE_LA_VENTANA = [...ES_TEXTOS.keys()].filter(
    (clave) =>
      clave.startsWith("chat.reasoning.") &&
      // El titulo es el nombre de la agente, y la pregunta lleva lo que escribio quien pregunto.
      clave !== "chat.reasoning.title",
  );

  it("la ventana tiene frases que revisar", () => {
    expect(CLAVES_DE_LA_VENTANA.length).toBeGreaterThan(20);
  });

  it.each(["es", "en"] as const)(
    "ninguna frase de la ventana habla en primera ni segunda persona, en %s",
    (idioma) => {
      const textos = idioma === "es" ? ES_TEXTOS : EN_TEXTOS;
      const personales = CLAVES_DE_LA_VENTANA.filter((clave) =>
        hablaEnPersona(textos.get(clave) ?? "", idioma),
      ).map((clave) => `${clave}: ${textos.get(clave) ?? ""}`);

      expect(personales).toEqual([]);
    },
  );

  it("el detector reconoce la redaccion de antes, para no pasar por vacio", () => {
    for (const vieja of [
      "Cuando me cuentes algo, aquí verás cómo lo pienso.",
      "Lo que entendí",
      "Quieres reportar un accidente.",
      "Tu póliza",
      "Confirmé que la póliza es tuya, así que busco solo en ella.",
      "Preguntaste: «algo»",
      "Si algo aplica a tu caso, lo decide un ajustador, no yo.",
    ]) {
      expect(hablaEnPersona(vieja, "es")).toBe(true);
    }
    expect(hablaEnPersona("Aquí se verá cómo razona la agente cada mensaje.", "es")).toBe(false);
    expect(hablaEnPersona("I confirmed that your policy is valid.", "en")).toBe(true);
  });

  it.each(["es", "en"] as const)(
    "el vacio de la ventana dice como se vera el razonamiento, en %s",
    async (idioma) => {
      pensamiento.mockResolvedValue(null);
      const ventana = await abrir(idioma);

      const t = createTranslate(idioma);
      const vacio = await within(ventana).findByText(t("chat.reasoning.empty"));
      if (idioma === "es") {
        expect(vacio.textContent).toBe("Aquí se verá cómo razona la agente cada mensaje.");
      }
    },
  );

  it("la ventana abierta con un caso muestra las frases impersonales", async () => {
    pensamiento.mockResolvedValue(razonamiento({ state: "derived" }));
    const ventana = await abrir();

    expect(await within(ventana).findByText(es("chat.reasoning.wants_question"))).toBeTruthy();
    expect(within(ventana).getByText(es("chat.reasoning.state_derived"))).toBeTruthy();
    expect(within(ventana).getByText(es("chat.reasoning.adjuster_decides"))).toBeTruthy();
  });

  // Los segundos de evaluacion y el cierre directo (US1.17, 2026-10-13): ninguno de los dos
  // es un caso «pasado a un ajustador», y el cierre directo no tiene una decision de nadie.
  it.each([
    ["verifying", "cases.group.verifying"],
    ["deciding", "cases.group.deciding"],
    ["closed", "chat.reasoning.state_closed"],
  ] as const)(
    "en %s dice donde quedo sin decir que esta con un ajustador",
    async (estado, clave) => {
      pensamiento.mockResolvedValue(razonamiento({ state: estado }));
      const ventana = await abrir();

      expect(await within(ventana).findByText(es(clave))).toBeTruthy();
      expect(within(ventana).queryByText(es("chat.reasoning.state_derived"))).toBeNull();
      expect(within(ventana).queryByText(es("chat.reasoning.state_open"))).toBeNull();
      expect(within(ventana).queryByText(/ya tiene una decisión/)).toBeNull();
    },
  );
});

describe("la pregunta, como la escribio quien la hizo (C5)", () => {
  it("con copia en este navegador no se ven etiquetas", async () => {
    window.localStorage.setItem(
      "cautelia.own-text.una-aseguradora",
      JSON.stringify(["¿Mi póliza POL-11 cubre el granizo?"]),
    );
    pensamiento.mockResolvedValue(razonamiento());
    const ventana = await abrir();

    const pregunta = await within(ventana).findByText(/Pregunta:/);
    expect(pregunta.textContent).toBe("Pregunta: «¿Mi póliza POL-11 cubre el granizo?»");
    expect(ventana.textContent).not.toContain("[PÓLIZA 1]");
  });

  it("sin copia (otro navegador) queda como la guardo la base", async () => {
    pensamiento.mockResolvedValue(razonamiento());
    const ventana = await abrir();

    const pregunta = await within(ventana).findByText(/Pregunta:/);
    expect(pregunta.textContent).toBe("Pregunta: «¿Mi póliza [PÓLIZA 1] cubre el granizo?»");
  });

  it("una copia que no encaja con la pregunta no se usa", async () => {
    window.localStorage.setItem(
      "cautelia.own-text.una-aseguradora",
      JSON.stringify(["¿Y el robo de mi carro cubre el granizo?"]),
    );
    pensamiento.mockResolvedValue(razonamiento());
    const ventana = await abrir();

    const pregunta = await within(ventana).findByText(/Pregunta:/);
    expect(pregunta.textContent).toContain("[PÓLIZA 1]");
    expect(pregunta.textContent).not.toContain("robo");
  });
});
