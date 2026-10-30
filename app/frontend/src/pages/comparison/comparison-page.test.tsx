import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import siteExample from "../../../../contracts/examples/site-directory.json";
import { renderWithProviders } from "../../app/testing";
import { installFakeServer, jsonResponse } from "../../shared/api-client/fake-server";
import type { SiteDirectory, TenantPresentation } from "../../shared/api-client/site";
import type { Locale } from "../../shared/copy/copy-keys";
import { createTranslate } from "../../shared/i18n/translate";
import { ComparisonPage } from "./comparison-page";
import type { ColumnOutcome, ComparisonInsurer } from "./comparison-state";
import { forgetInFlight, loadComparison, saveComparison, VIGENCIA_MS } from "./comparison-storage";

const EJEMPLO = siteExample as SiteDirectory;

/** La marca de una aseguradora del directorio de ejemplo, para probar el acento sin escribir colores. */
/** La marca de una aseguradora del ejemplo del contrato, por su posicion: ninguna se nombra. */
function marca(posicion: number): ComparisonInsurer["brand"] {
  return EJEMPLO.tenants.at(posicion)?.brand ?? null;
}

const ASEGURADORAS: readonly ComparisonInsurer[] = [
  {
    tenantId: "una-aseguradora",
    displayName: "Una Aseguradora",
    kind: "carrier",
    examplePolicy: "POL-21",
    issuedBy: null,
    brand: marca(2),
  },
  {
    tenantId: "otra-aseguradora",
    displayName: "Otra Aseguradora",
    kind: "carrier",
    examplePolicy: "POL-11",
    issuedBy: null,
    brand: marca(1),
  },
  {
    tenantId: "una-agencia",
    displayName: "Una Agencia",
    kind: "agency",
    examplePolicy: "POL-31",
    issuedBy: "Una Aseguradora",
    brand: marca(0),
  },
];

/** El nombre de la agente de cada una: distinto en las tres. */
const AGENTES = new Map([
  ["una-aseguradora", "Valeria"],
  ["otra-aseguradora", "Catalina"],
  ["una-agencia", "Isabel"],
]);

const DIRECTORIO: SiteDirectory = {
  ...EJEMPLO,
  tenants: ASEGURADORAS.map((aseguradora): TenantPresentation => ({
    tenant_id: aseguradora.tenantId,
    display_name: aseguradora.displayName,
    kind: aseguradora.kind,
    default_language: "es",
    example_policy: aseguradora.examplePolicy,
    ...(aseguradora.issuedBy === null ? {} : { example_policy_issuer: aseguradora.issuedBy }),
    brand: aseguradora.brand,
    agent_name: AGENTES.get(aseguradora.tenantId) ?? "",
  })),
};

let quitarServidor: (() => void) | undefined;

beforeEach(() => {
  // El nombre de cada agente sale del directorio del sitio, igual que en la pagina.
  quitarServidor = installFakeServer((ruta) =>
    ruta === "/api/site" ? jsonResponse(DIRECTORIO) : jsonResponse({}, 404),
  );
});

afterEach(() => {
  quitarServidor?.();
  quitarServidor = undefined;
  // Cada prueba empieza sin preguntas en vuelo de otra, como una pagina recien abierta.
  forgetInFlight();
  vi.restoreAllMocks();
});

const CITADA = (texto: string, clausula: string): ColumnOutcome => ({
  kind: "answered",
  answer: {
    kind: "cited",
    language: "es",
    text: texto,
    citations: [
      {
        clause_id: clausula,
        clause_version: "2026.1",
        part: "Parte D",
        text: "Texto literal de la clausula.",
        clause_language: "es",
        amount_deferred: false,
        trace_ref: "",
      },
    ],
  },
});

/** Un `ask` cuyas tres respuestas se resuelven cuando la prueba lo decide. */
function askControlado() {
  const pendientes = new Map<string, (r: ColumnOutcome) => void>();
  const llamadas: { tenantId: string; question: string }[] = [];
  const ask = vi.fn((tenantId: string, question: string) => {
    llamadas.push({ tenantId, question });
    return new Promise<ColumnOutcome>((resolver) => {
      pendientes.set(tenantId, resolver);
    });
  });
  return {
    ask,
    llamadas,
    async resolver(tenantId: string, resultado: ColumnOutcome) {
      await act(async () => {
        pendientes.get(tenantId)?.(resultado);
        await Promise.resolve();
      });
    },
  };
}

function columna(tenantId: string): HTMLElement {
  const encontrada = screen
    .getAllByTestId("comparison-column")
    .find((nodo) => nodo.getAttribute("data-tenant") === tenantId);
  if (encontrada === undefined) {
    throw new Error(`no hay columna de ${tenantId}`);
  }
  return encontrada;
}

const tEs = createTranslate("es");
const tEn = createTranslate("en");

function dibujar(ask: ReturnType<typeof askControlado>["ask"], locale: Locale = "es") {
  return renderWithProviders(<ComparisonPage insurers={ASEGURADORAS} ask={ask} />, locale);
}

async function preguntar(texto = "¿Me pagan un carro de alquiler?") {
  await userEvent.type(screen.getByLabelText(tEs("comparison.composer.label")), texto);
  await userEvent.click(screen.getByRole("button", { name: tEs("comparison.composer.send") }));
}

function estados(): (string | undefined)[] {
  return screen.getAllByTestId("comparison-column").map((c) => c.dataset.state);
}

describe("lo que la pantalla dice antes de preguntar (BR1.1, BR1.2)", () => {
  it("arriba dice para que sirve, en una o dos frases", () => {
    dibujar(askControlado().ask);

    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      tEs("comparison.page.title"),
    );
    expect(screen.getByText(tEs("comparison.page.lead"))).toBeTruthy();
  });

  it("cada columna dice quien responde con el nombre de SU agente, antes de que se pregunte nada", async () => {
    dibujar(askControlado().ask);

    for (const [tenantId, agente] of AGENTES) {
      expect(
        await within(columna(tenantId)).findByText(
          tEs("comparison.disclosure.assistant", { agent: agente }),
        ),
      ).toBeTruthy();
    }
    expect(new Set(AGENTES.values()).size).toBe(AGENTES.size);
  });

  it("ya no hay caja de divulgacion, ni aclaracion de que no es una persona, ni lista de polizas aparte", () => {
    dibujar(askControlado().ask);
    const pagina = screen.getByTestId("comparison-page");

    expect(screen.queryByTestId("comparison-disclosure")).toBeNull();
    expect(screen.queryByTestId("comparison-policies")).toBeNull();
    expect(pagina.textContent).not.toMatch(/no una persona|Antes de preguntar/);
    expect(pagina.textContent).not.toMatch(/Cada columna responde con esta póliza/);
  });

  it("el aviso de demostracion y el de los tres mensajes son una sola linea, antes del campo", () => {
    dibujar(askControlado().ask);
    const aviso = screen.getByTestId("comparison-notice");
    const campo = screen.getByLabelText(tEs("comparison.composer.label"));

    expect(aviso.textContent).toBe(tEs("comparison.disclosure.demo"));
    expect(aviso.textContent).toMatch(/demostración[\s\S]*datos personales[\s\S]*tres mensajes/i);
    // Que responden asistentes de IA se dice aqui, una vez: la columna ya no lo dice.
    expect(aviso.textContent).toMatch(/asistentes de IA/);
    expect(aviso.compareDocumentPosition(campo) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // Y quien usa un lector de pantalla lo oye al entrar al campo.
    expect(campo.getAttribute("aria-describedby")).toBe(aviso.id);
  });

  it("el encabezado dice quien responde sin 'asistente de IA' y sin la poliza", async () => {
    dibujar(askControlado().ask);

    for (const [tenantId, agente] of AGENTES) {
      const nodo = columna(tenantId);
      expect(await within(nodo).findByText(`Responde ${agente}`)).toBeTruthy();
      expect(nodo.textContent).not.toMatch(/asistente de IA/);
      // Antes de preguntar no hay clausulas, y la poliza solo se dice sobre ellas.
      expect(within(nodo).queryByTestId("comparison-policy")).toBeNull();
    }
  });

  it("la poliza va al pie de la tarjeta, justo encima de las clausulas, y la de la agencia nombra a quien la emitio", async () => {
    const cable = askControlado();
    dibujar(cable.ask);
    await preguntar();
    await cable.resolver("otra-aseguradora", CITADA("Si cubre.", "SA-PAP-4.1"));
    await cable.resolver("una-agencia", CITADA("Si cubre.", "AC-PAP-4.1"));
    await cable.resolver("una-aseguradora", {
      kind: "answered",
      answer: { kind: "no_clause", language: "es" },
    });

    const otra = columna("otra-aseguradora");
    expect(within(otra).getByTestId("comparison-policy").textContent).toBe(
      tEs("comparison.column.policy", { policy: "POL-11" }),
    );
    const agencia = columna("una-agencia");
    expect(within(agencia).getByTestId("comparison-policy").textContent).toBe(
      tEs("comparison.column.policy_issued_by", {
        policy: "POL-31",
        issuer: "Una Aseguradora",
      }),
    );
    // Fuera del encabezado, antes de la clausula, y las dos en el mismo contenedor del pie.
    const encabezado = within(agencia).getByRole("banner");
    expect(encabezado.contains(within(agencia).getByTestId("comparison-policy"))).toBe(false);
    const linea = within(agencia).getByTestId("comparison-policy");
    const boton = within(agencia).getByRole("button", { name: /Ver la cláusula exacta/ });
    expect(linea.compareDocumentPosition(boton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(linea.parentElement?.contains(boton)).toBe(true);
    // Una respuesta sin clausulas no nombra la poliza: no hay nada a lo que anteponerla.
    expect(within(columna("una-aseguradora")).queryByTestId("comparison-policy")).toBeNull();
  });

  it("antes de preguntar cada columna es un esbozo con intencion y no una caja gris con un titulo", () => {
    dibujar(askControlado().ask);

    expect(estados()).toEqual(["idle", "idle", "idle"]);
    for (const nodo of screen.getAllByTestId("comparison-column")) {
      expect(within(nodo).getByText(tEs("comparison.column.idle"))).toBeTruthy();
      // Sin etiqueta de estado: lo que dice el texto de arriba ya es el estado.
      expect(within(nodo).queryByText(tEs("comparison.state.loading"))).toBeNull();
    }
  });

  it("si una agencia no dice su emisor, no ofrece la pregunta", () => {
    const sinEmisor = ASEGURADORAS.map((a) => (a.kind === "agency" ? { ...a, issuedBy: null } : a));
    renderWithProviders(<ComparisonPage insurers={sinEmisor} ask={askControlado().ask} />);

    expect(screen.queryByLabelText(tEs("comparison.composer.label"))).toBeNull();
    expect(screen.getByTestId("comparison-incomplete")).toBeTruthy();
  });

  it("dice lo mismo en ingles, desde el catalogo", async () => {
    dibujar(askControlado().ask, "en" satisfies Locale);

    expect(screen.getByText(tEn("comparison.page.lead"))).toBeTruthy();
    expect(screen.getByLabelText(tEn("comparison.composer.label"))).toBeTruthy();
    expect(screen.getByTestId("comparison-notice").textContent).toBe(
      tEn("comparison.disclosure.demo"),
    );
    expect(
      await within(columna("una-agencia")).findByText(
        tEn("comparison.disclosure.assistant", { agent: "Isabel" }),
      ),
    ).toBeTruthy();
    expect(columna("una-agencia").textContent).not.toMatch(/AI assistant/);
  });
});

describe("la identidad de cada columna", () => {
  it("cada una lleva el acento y el monograma de su aseguradora, y el titulo en su color", () => {
    dibujar(askControlado().ask);
    const acentos = new Set<string>();

    for (const aseguradora of ASEGURADORAS) {
      const nodo = columna(aseguradora.tenantId);
      acentos.add(nodo.style.getPropertyValue("--tenant-accent"));
      expect(nodo.hasAttribute("data-tenant-scope")).toBe(true);
      expect(nodo.style.getPropertyValue("--tenant-accent")).toBe(aseguradora.brand?.accent);
      expect(nodo.style.getPropertyValue("--tenant-accent-on-dark")).toBe(
        aseguradora.brand?.accent_on_dark,
      );
      expect(nodo.querySelector("[data-monogram]")?.getAttribute("data-monogram")).toBe(
        aseguradora.brand?.monogram,
      );
      expect(within(nodo).getByRole("heading", { level: 2 }).className).toContain("text-tenant");
    }
    // Las tres son distintas: eso es lo que deja ver que son tres polizas.
    expect(acentos.size).toBe(3);
  });

  it("sin marca, la columna sigue siendo legible y no dibuja monograma", () => {
    const sinMarca = ASEGURADORAS.map((a) => ({ ...a, brand: null }));
    renderWithProviders(<ComparisonPage insurers={sinMarca} ask={askControlado().ask} />);

    expect(columna("una-agencia").querySelector("[data-monogram]")).toBeNull();
    expect(within(columna("una-agencia")).getByRole("heading", { level: 2 }).textContent).toBe(
      "Una Agencia",
    );
  });
});

describe("las preguntas de ejemplo y lo que queda fuera de proposito (BR1.3, AC2.9.6)", () => {
  it("ofrece ocho y al elegir una la pone en el campo sin mandarla", async () => {
    const cable = askControlado();
    dibujar(cable.ask);
    const grupo = screen.getByRole("group", { name: tEs("comparison.examples.title") });

    expect(within(grupo).getAllByRole("button")).toHaveLength(8);
    await userEvent.click(
      within(grupo).getByRole("button", { name: tEs("comparison.examples.hail") }),
    );

    expect(screen.getByLabelText(tEs("comparison.composer.label"))).toHaveProperty(
      "value",
      tEs("comparison.examples.hail"),
    );
    expect(cable.ask).not.toHaveBeenCalled();
    // Elegir otra reemplaza a la anterior.
    await userEvent.click(
      within(grupo).getByRole("button", { name: tEs("comparison.examples.stolen_keys") }),
    );
    expect(screen.getByLabelText(tEs("comparison.composer.label"))).toHaveProperty(
      "value",
      tEs("comparison.examples.stolen_keys"),
    );
  });

  it("las ocho existen tambien en ingles", () => {
    dibujar(askControlado().ask, "en");
    const grupo = screen.getByRole("group", { name: tEn("comparison.examples.title") });

    expect(within(grupo).getAllByRole("button")).toHaveLength(8);
    expect(
      within(grupo).getByRole("button", { name: tEn("comparison.examples.lend_car") }),
    ).toBeTruthy();
  });

  it("las sugerencias y el cuadro se quitan en cuanto hay una pregunta en curso", async () => {
    dibujar(askControlado().ask);
    await preguntar();

    expect(screen.queryByRole("button", { name: tEs("comparison.examples.hail") })).toBeNull();
    expect(screen.queryByText(tEs("comparison.examples.title"))).toBeNull();
    expect(screen.queryByLabelText(tEs("comparison.composer.label"))).toBeNull();
  });

  it("una pregunta fuera de proposito se explica y enlaza el chat de cada aseguradora", async () => {
    // **Lo decide el servidor** (Q3 de U23), asi que llega como resultado de la
    // pregunta y no como una heuristica de este lado. La pregunta **si se manda**:
    // es la otra mitad de la decision, y es lo que hace que descuente sus tres
    // mensajes de los limites (BR2.3).
    const cable = askControlado();
    dibujar(cable.ask);
    await preguntar("Choqué ayer y quiero reportarlo");

    expect(cable.llamadas.map((l) => l.tenantId)).toEqual([
      "una-aseguradora",
      "otra-aseguradora",
      "una-agencia",
    ]);
    for (const { tenantId } of cable.llamadas) {
      await cable.resolver(tenantId, {
        kind: "out_of_scope",
        copyKey: "comparison.out_of_scope.explanation",
      });
    }

    const aviso = screen.getByTestId("comparison-out-of-scope");
    expect(within(aviso).getByText(tEs("comparison.out_of_scope.explanation"))).toBeTruthy();
    const enlaces = within(aviso).getAllByRole("link");
    expect(enlaces.map((e) => e.getAttribute("href"))).toEqual([
      "/t/una-aseguradora/chat",
      "/t/otra-aseguradora/chat",
      "/t/una-agencia/chat",
    ]);
    // Y las tres columnas vuelven a vacio: no hubo nada que comparar. Dibujarlas
    // como fallidas diria que no se pudo revisar la poliza, y lo que paso es que no
    // se pregunto por una cobertura.
    expect(estados()).toEqual(["idle", "idle", "idle"]);
    // La pregunta no queda como hecha: el cuadro vuelve para escribir otra.
    expect(screen.queryByTestId("comparison-asked")).toBeNull();
    expect(screen.getByLabelText(tEs("comparison.composer.label"))).toBeTruthy();
  });

  it("con la demo estrechada dice la frase una vez y no ofrece el chat", async () => {
    // BR3.2 de U20. **Sin enlaces al chat**, a diferencia del aviso de fuera de
    // proposito: el chat se estrecha igual, asi que mandar alli a quien pregunta
    // seria mandarlo a la misma puerta cerrada.
    const cable = askControlado();
    dibujar(cable.ask);
    await preguntar("¿Cubre granizo?");

    for (const { tenantId } of cable.llamadas) {
      await cable.resolver(tenantId, {
        kind: "demo_closed",
        copyKey: "demo.reset.surfaces_closed",
      });
    }

    const aviso = screen.getByTestId("comparison-demo-closed");
    expect(within(aviso).getByText(tEs("demo.reset.surfaces_closed"))).toBeTruthy();
    expect(within(aviso).queryAllByRole("link")).toEqual([]);
    expect(screen.queryByTestId("comparison-out-of-scope")).toBeNull();
  });
});

describe("las tres respuestas (BR2.2)", () => {
  it("manda la misma pregunta a las tres aseguradoras, una vez cada una", async () => {
    const cable = askControlado();
    dibujar(cable.ask);
    await preguntar("¿Cubre el granizo?");

    expect(cable.llamadas).toEqual([
      { tenantId: "una-aseguradora", question: "¿Cubre el granizo?" },
      { tenantId: "otra-aseguradora", question: "¿Cubre el granizo?" },
      { tenantId: "una-agencia", question: "¿Cubre el granizo?" },
    ]);
  });

  it("muestra la pregunta hecha, con su hora y cuanto se guarda", async () => {
    dibujar(askControlado().ask);
    await preguntar("¿Cubre el granizo?");
    const hecha = screen.getByTestId("comparison-asked");

    expect(within(hecha).getByText("¿Cubre el granizo?")).toBeTruthy();
    expect(hecha.textContent).toMatch(/Preguntada: .+Se guarda en este navegador por 24 horas/);
    // El foco no se pierde con el boton que desaparecio: va a la pregunta.
    expect(document.activeElement).toBe(hecha);
  });

  it("una columna que responde aparece sin esperar a las otras dos", async () => {
    const cable = askControlado();
    dibujar(cable.ask);
    await preguntar();

    expect(estados()).toEqual(["loading", "loading", "loading"]);

    await cable.resolver("otra-aseguradora", CITADA("Cubre el alquiler.", "PAP-STO-4.1"));

    expect(columna("otra-aseguradora").dataset.state).toBe("answered");
    expect(within(columna("otra-aseguradora")).getByText("Cubre el alquiler.")).toBeTruthy();
    expect(columna("una-aseguradora").dataset.state).toBe("loading");
    expect(columna("una-agencia").dataset.state).toBe("loading");
  });

  it("una columna que falla dice que no pudo revisar la poliza y no borra las otras", async () => {
    const cable = askControlado();
    dibujar(cable.ask);
    await preguntar();

    await cable.resolver("una-aseguradora", CITADA("Respuesta de Sunmeadow.", "PAP-SUN-4.1"));
    await cable.resolver("una-agencia", { kind: "failed" });
    await cable.resolver("otra-aseguradora", CITADA("Respuesta de Stonecroft.", "PAP-STO-4.1"));

    expect(columna("una-agencia").dataset.state).toBe("failed");
    expect(
      within(columna("una-agencia")).getByText(
        tEs("comparison.column.failed", { insurer: "Una Agencia" }),
      ),
    ).toBeTruthy();
    expect(within(columna("una-aseguradora")).getByText("Respuesta de Sunmeadow.")).toBeTruthy();
    expect(within(columna("otra-aseguradora")).getByText("Respuesta de Stonecroft.")).toBeTruthy();
  });

  it("una columna fallida deja volver a preguntar solo a esa aseguradora", async () => {
    const cable = askControlado();
    dibujar(cable.ask);
    await preguntar("¿Cubre el granizo?");
    await cable.resolver("una-aseguradora", CITADA("Respuesta.", "PAP-SUN-4.1"));
    await cable.resolver("una-agencia", { kind: "failed" });
    cable.ask.mockClear();

    await userEvent.click(
      within(columna("una-agencia")).getByRole("button", { name: tEs("comparison.column.retry") }),
    );

    expect(cable.ask).toHaveBeenCalledTimes(1);
    expect(cable.ask).toHaveBeenCalledWith("una-agencia", "¿Cubre el granizo?");
    expect(columna("una-agencia").dataset.state).toBe("loading");
    expect(columna("una-aseguradora").dataset.state).toBe("answered");
    await cable.resolver("una-agencia", CITADA("Ahora si.", "AP-PAP-4.1"));
    expect(within(columna("una-agencia")).getByText("Ahora si.")).toBeTruthy();
  });

  it("un `ask` que lanza cierra solo su columna como fallida", async () => {
    const respuestas = new Map<string, () => Promise<ColumnOutcome>>([
      ["una-aseguradora", () => Promise.resolve(CITADA("Respuesta.", "PAP-SUN-4.1"))],
      ["otra-aseguradora", () => Promise.reject(new Error("se cayo el proveedor"))],
      ["una-agencia", () => Promise.resolve(CITADA("Otra respuesta.", "AP-PAP-4.1"))],
    ]);
    renderWithProviders(
      <ComparisonPage
        insurers={ASEGURADORAS}
        ask={(tenantId) => respuestas.get(tenantId)?.() ?? Promise.resolve({ kind: "failed" })}
      />,
    );
    await preguntar();

    await waitFor(() => {
      expect(estados()).toEqual(["answered", "failed", "answered"]);
    });
  });

  it("el rechazo por limite dice cual fue, con la frase del catalogo, y las otras siguen", async () => {
    const cable = askControlado();
    dibujar(cable.ask);
    await preguntar();

    await cable.resolver("otra-aseguradora", {
      kind: "rejected",
      limit: "rate",
      copyKey: "chat.limit.rate",
    });
    await cable.resolver("una-aseguradora", CITADA("Respuesta.", "PAP-SUN-4.1"));

    const rechazada = columna("otra-aseguradora");
    expect(rechazada.dataset.state).toBe("rejected");
    expect(within(rechazada).getByText(tEs("comparison.column.rejected_title"))).toBeTruthy();
    expect(within(rechazada).getByText(tEs("chat.limit.rate"))).toBeTruthy();
    expect(within(rechazada).getByTestId("comparison-rejected").dataset.limit).toBe("rate");
    expect(columna("una-aseguradora").dataset.state).toBe("answered");
    expect(columna("una-agencia").dataset.state).toBe("loading");
  });

  it("failed y rejected no se dibujan igual", async () => {
    const cable = askControlado();
    dibujar(cable.ask);
    await preguntar();
    await cable.resolver("una-aseguradora", { kind: "failed" });
    await cable.resolver("otra-aseguradora", {
      kind: "rejected",
      limit: "session",
      copyKey: "spend.quota.rate_limited_session",
    });

    const fallida = columna("una-aseguradora");
    const rechazada = columna("otra-aseguradora");
    expect(fallida.dataset.state).toBe("failed");
    expect(rechazada.dataset.state).toBe("rejected");
    expect(within(fallida).queryByText(tEs("comparison.column.rejected_title"))).toBeNull();
    expect(within(rechazada).queryByText(/No se pudo revisar la póliza/)).toBeNull();
    expect(within(fallida).getByText(tEs("comparison.state.failed"))).toBeTruthy();
    expect(within(rechazada).getByText(tEs("comparison.state.rejected"))).toBeTruthy();
    expect(within(fallida).getByTestId("comparison-failed")).toBeTruthy();
    expect(within(rechazada).queryByTestId("comparison-failed")).toBeNull();
    // Un limite no se arregla preguntando otra vez: no ofrece el boton.
    expect(
      within(rechazada).queryByRole("button", { name: tEs("comparison.column.retry") }),
    ).toBeNull();
  });

  it("'no encuentro una clausula' se dice distinto de 'no se pudo revisar'", async () => {
    const cable = askControlado();
    dibujar(cable.ask);
    await preguntar();
    await cable.resolver("una-aseguradora", {
      kind: "answered",
      answer: { kind: "no_clause", language: "es" },
    });
    await cable.resolver("otra-aseguradora", { kind: "failed" });

    expect(
      within(columna("una-aseguradora")).getByText(tEs("policy_rag.coverage.no_clause_found")),
    ).toBeTruthy();
    expect(columna("una-aseguradora").dataset.state).toBe("answered");
    expect(columna("otra-aseguradora").dataset.state).toBe("failed");
    expect(within(columna("una-aseguradora")).queryByTestId("comparison-failed")).toBeNull();
  });

  it("no deja mandar una segunda pregunta mientras alguna columna carga", async () => {
    const cable = askControlado();
    dibujar(cable.ask);
    await preguntar();

    // No hay cuadro donde escribir y empezar otra espera a que terminen las tres.
    expect(screen.queryByLabelText(tEs("comparison.composer.label"))).toBeNull();
    expect(screen.getByRole("button", { name: tEs("comparison.asked.new") })).toHaveProperty(
      "disabled",
      true,
    );
    expect(cable.ask).toHaveBeenCalledTimes(3);
  });

  it("muestra la cita de cada columna con su propia clausula", async () => {
    const cable = askControlado();
    dibujar(cable.ask);
    await preguntar();
    await cable.resolver("una-aseguradora", CITADA("Una.", "AP-PAP-4.1"));
    await cable.resolver("otra-aseguradora", CITADA("Otra.", "SA-PAP-4.1"));
    // El codigo de la clausula se ve con la tarjeta abierta (2026-10-08).
    for (const id of ["una-aseguradora", "otra-aseguradora"]) {
      await userEvent.click(
        within(columna(id)).getByRole("button", { name: /Ver la cláusula exacta/ }),
      );
    }

    expect(within(columna("una-aseguradora")).getByText(/AP-PAP-4.1/)).toBeTruthy();
    expect(within(columna("una-aseguradora")).queryByText(/SA-PAP-4.1/)).toBeNull();
    expect(within(columna("otra-aseguradora")).getByText(/SA-PAP-4.1/)).toBeTruthy();
  });
});

describe("lo que se recuerda en el navegador", () => {
  /** Pregunta y deja una respuesta de cada clase: citada, sin clausula y fallida. */
  async function preguntarYResponder() {
    const cable = askControlado();
    const pagina = dibujar(cable.ask);
    await preguntar("¿Cubre el granizo?");
    await cable.resolver("una-aseguradora", CITADA("Si cubre el granizo.", "AP-PAP-4.1"));
    await cable.resolver("otra-aseguradora", {
      kind: "answered",
      answer: { kind: "no_clause", language: "es" },
    });
    await cable.resolver("una-agencia", { kind: "failed" });
    return pagina;
  }

  const IDS = ASEGURADORAS.map((a) => a.tenantId);

  it("recargar o volver a la pagina trae la pregunta y lo que contesto cada aseguradora", async () => {
    const primera = await preguntarYResponder();
    primera.unmount();
    forgetInFlight();

    const despues = askControlado();
    dibujar(despues.ask);

    const hecha = screen.getByTestId("comparison-asked");
    expect(within(hecha).getByText("¿Cubre el granizo?")).toBeTruthy();
    expect(screen.queryByLabelText(tEs("comparison.composer.label"))).toBeNull();
    expect(estados()).toEqual(["answered", "answered", "failed"]);
    expect(within(columna("una-aseguradora")).getByText("Si cubre el granizo.")).toBeTruthy();
    await userEvent.click(
      within(columna("una-aseguradora")).getByRole("button", { name: /Ver la cláusula exacta/ }),
    );
    expect(within(columna("una-aseguradora")).getByText(/AP-PAP-4.1/)).toBeTruthy();
    expect(
      within(columna("otra-aseguradora")).getByText(tEs("policy_rag.coverage.no_clause_found")),
    ).toBeTruthy();
    // Restaurar no pregunta nada: no gasta mensajes.
    expect(despues.ask).not.toHaveBeenCalled();
    // No toma el foco: la persona no hizo nada todavia.
    expect(document.activeElement).not.toBe(hecha);
  });

  it("guarda cuando se pregunto y en que idioma", async () => {
    const antes = Date.now();
    dibujar(askControlado().ask, "en");
    await userEvent.type(
      screen.getByLabelText(tEn("comparison.composer.label")),
      "Does it cover hail?",
    );
    await userEvent.click(screen.getByRole("button", { name: tEn("comparison.composer.send") }));

    const guardada = loadComparison(Date.now(), IDS);
    expect(guardada?.locale).toBe("en");
    expect(guardada?.question).toBe("Does it cover hail?");
    expect(guardada?.askedAt).toBeGreaterThanOrEqual(antes);
    expect(guardada?.askedAt).toBeLessThanOrEqual(Date.now());
  });

  it("si la persona sale a otra pagina mientras carga, la respuesta que llega despues la espera al volver", async () => {
    const cable = askControlado();
    const primera = dibujar(cable.ask);
    await preguntar("¿Cubre el granizo?");
    primera.unmount();

    // Con la pagina desmontada, una de las tres termina.
    await cable.resolver(
      "otra-aseguradora",
      CITADA("Respondio mientras no mirabas.", "SA-PAP-4.1"),
    );

    dibujar(cable.ask);
    expect(estados()).toEqual(["loading", "answered", "loading"]);
    expect(
      within(columna("otra-aseguradora")).getByText("Respondio mientras no mirabas."),
    ).toBeTruthy();
    // Y las que seguian en vuelo se enganchan: no quedan esperando para siempre.
    await cable.resolver("una-aseguradora", CITADA("Esta llego despues de volver.", "AP-PAP-4.1"));
    expect(
      within(columna("una-aseguradora")).getByText("Esta llego despues de volver."),
    ).toBeTruthy();
    expect(cable.ask).toHaveBeenCalledTimes(3);
  });

  it("al recargar con una columna sin respuesta la dice como es y no la deja girando", async () => {
    const cable = askControlado();
    const primera = dibujar(cable.ask);
    await preguntar("¿Cubre el granizo?");
    await cable.resolver("una-aseguradora", CITADA("Esta si llego.", "AP-PAP-4.1"));
    primera.unmount();
    // Recargar: la pagina nueva no tiene nada en vuelo.
    forgetInFlight();

    dibujar(askControlado().ask);

    expect(estados()).toEqual(["answered", "interrupted", "interrupted"]);
    for (const id of ["otra-aseguradora", "una-agencia"]) {
      const pendiente = columna(id);
      expect(within(pendiente).getByText(tEs("comparison.column.interrupted"))).toBeTruthy();
      expect(within(pendiente).getByText(tEs("comparison.state.interrupted"))).toBeTruthy();
      expect(pendiente.querySelector('[aria-busy="true"]')).toBeNull();
      // No es un fallo de la poliza: son dos cosas distintas.
      expect(within(pendiente).queryByTestId("comparison-failed")).toBeNull();
    }
    // Y se puede seguir: otra pregunta no esta bloqueada por una espera que ya no existe.
    expect(screen.getByRole("button", { name: tEs("comparison.asked.new") })).toHaveProperty(
      "disabled",
      false,
    );
  });

  it("volver a preguntar a una columna interrumpida manda solo esa, con la misma pregunta", async () => {
    const primera = dibujar(askControlado().ask);
    await preguntar("¿Cubre el granizo?");
    primera.unmount();
    forgetInFlight();
    const otra = askControlado();
    dibujar(otra.ask);

    await userEvent.click(
      within(columna("otra-aseguradora")).getByRole("button", {
        name: tEs("comparison.column.retry"),
      }),
    );

    expect(otra.ask).toHaveBeenCalledTimes(1);
    expect(otra.ask).toHaveBeenCalledWith("otra-aseguradora", "¿Cubre el granizo?");
    expect(estados()).toEqual(["interrupted", "loading", "interrupted"]);
    await otra.resolver("otra-aseguradora", CITADA("Ahora si llego.", "SA-PAP-4.1"));
    expect(estados()).toEqual(["interrupted", "answered", "interrupted"]);
    // Y queda guardada: recargar de nuevo la trae.
    expect(loadComparison(Date.now(), IDS)?.columns.map((c) => c.state)).toEqual([
      "loading",
      "answered",
      "loading",
    ]);
  });

  it("vence a las 24 horas: la pagina arranca limpia y borra lo guardado", () => {
    saveComparison({
      askedAt: Date.now() - VIGENCIA_MS - 1,
      locale: "es",
      question: "¿Cubre el granizo?",
      columns: IDS.map((tenantId) => ({
        tenantId,
        state: "answered",
        answer: { kind: "no_clause", language: "es" },
      })),
    });

    dibujar(askControlado().ask);

    expect(screen.queryByTestId("comparison-asked")).toBeNull();
    expect(screen.getByLabelText(tEs("comparison.composer.label"))).toBeTruthy();
    expect(estados()).toEqual(["idle", "idle", "idle"]);
    expect(window.localStorage.getItem("cautelia.comparison.v2")).toBeNull();
  });

  it("lo que todavia no vence se conserva", () => {
    saveComparison({
      askedAt: Date.now() - VIGENCIA_MS + 120_000,
      locale: "es",
      question: "¿Cubre el granizo?",
      columns: IDS.map((tenantId) => ({
        tenantId,
        state: "answered",
        answer: { kind: "no_clause", language: "es" },
      })),
    });

    dibujar(askControlado().ask);

    expect(screen.getByTestId("comparison-asked")).toBeTruthy();
    expect(estados()).toEqual(["answered", "answered", "answered"]);
  });

  it("'Nueva pregunta' borra lo guardado, deja las columnas vacias y pone el foco en el cuadro", async () => {
    await preguntarYResponder();
    expect(loadComparison(Date.now(), IDS)).not.toBeNull();

    await userEvent.click(screen.getByRole("button", { name: tEs("comparison.asked.new") }));

    expect(window.localStorage.getItem("cautelia.comparison.v2")).toBeNull();
    expect(screen.queryByTestId("comparison-asked")).toBeNull();
    expect(estados()).toEqual(["idle", "idle", "idle"]);
    const cuadro = screen.getByLabelText(tEs("comparison.composer.label"));
    expect(cuadro).toHaveProperty("value", "");
    expect(document.activeElement).toBe(cuadro);
  });

  it("una pregunta fuera de proposito no deja nada guardado", async () => {
    const cable = askControlado();
    dibujar(cable.ask);
    await preguntar("Choqué ayer");
    expect(loadComparison(Date.now(), IDS)).not.toBeNull();

    for (const { tenantId } of cable.llamadas) {
      await cable.resolver(tenantId, {
        kind: "out_of_scope",
        copyKey: "comparison.out_of_scope.explanation",
      });
    }

    expect(window.localStorage.getItem("cautelia.comparison.v2")).toBeNull();
  });

  it("lo guardado de otras aseguradoras o dañado no se pinta: arranca limpia", () => {
    window.localStorage.setItem("cautelia.comparison.v2", '{"askedAt":"ayer"}');

    dibujar(askControlado().ask);

    expect(screen.queryByTestId("comparison-asked")).toBeNull();
    expect(screen.getByLabelText(tEs("comparison.composer.label"))).toBeTruthy();
    expect(estados()).toEqual(["idle", "idle", "idle"]);
  });

  it("sin localStorage la pagina funciona igual: pregunta, responde y no recuerda", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("denegado", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("sin cupo", "QuotaExceededError");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new DOMException("denegado", "SecurityError");
    });
    const cable = askControlado();
    const primera = dibujar(cable.ask);

    await preguntar("¿Cubre el granizo?");
    await cable.resolver("una-aseguradora", CITADA("Cubre.", "AP-PAP-4.1"));

    expect(columna("una-aseguradora").dataset.state).toBe("answered");
    expect(within(columna("una-aseguradora")).getByText("Cubre.")).toBeTruthy();
    // Y "Nueva pregunta" tambien funciona.
    await cable.resolver("otra-aseguradora", { kind: "failed" });
    await cable.resolver("una-agencia", { kind: "failed" });
    await userEvent.click(screen.getByRole("button", { name: tEs("comparison.asked.new") }));
    expect(screen.getByLabelText(tEs("comparison.composer.label"))).toBeTruthy();

    primera.unmount();
    dibujar(askControlado().ask);
    expect(screen.queryByTestId("comparison-asked")).toBeNull();
  });
});

describe("lo que la vista no redacta (BR3.2)", () => {
  it("cuando dos columnas difieren, no escribe nada propio sobre la diferencia", async () => {
    const cable = askControlado();
    dibujar(cable.ask);
    await preguntar();

    /** Todo el texto de la pagina menos las columnas y la pregunta repetida. */
    const propio = () => {
      const pagina = screen.getByTestId("comparison-page").cloneNode(true) as HTMLElement;
      pagina.querySelector('[data-testid="comparison-columns"]')?.remove();
      pagina.querySelector('[data-testid="comparison-asked"]')?.remove();
      return pagina.textContent;
    };
    const antes = propio();

    await cable.resolver("una-aseguradora", CITADA("Si cubre el alquiler.", "AP-PAP-4.1"));
    await cable.resolver("otra-aseguradora", {
      kind: "answered",
      answer: { kind: "no_clause", language: "es" },
    });
    await cable.resolver("una-agencia", CITADA("Si, segun la emisora.", "AP-PAP-4.1"));

    expect(propio()).toBe(antes);
  });
});
