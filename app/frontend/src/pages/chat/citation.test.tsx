import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderWithProviders } from "../../app/testing";
import { Citation, withPositions } from "./citation";
import type { WireCitation } from "./chat-events";

// AC2.3.1 y AC2.3.4. Lo que aqui se comprueba es lo que la regla protege: que el
// texto que la persona compara contra su poliza sea **el de su poliza**, en su
// idioma, sin traducir ni resumir, y que se diga cuando no esta en el idioma de
// la conversacion.

const EN_INGLES: WireCitation = {
  clause_id: "LI-09",
  clause_version: "2026.4",
  part: "Liability",
  text: "The company pays for damage to third parties.",
  clause_language: "en",
  amount_deferred: false,
  trace_ref: "tr-1",
};

const EN_ESPANOL: WireCitation = {
  ...EN_INGLES,
  clause_id: "RC-04",
  part: "Responsabilidad civil",
  text: "La compañía responde por los daños a terceros.",
  clause_language: "es",
};

describe("la cita expandible", () => {
  it("cerrada no muestra codigos; al abrirla, el identificador y la version al final", async () => {
    // Decision de Miguel del 2026-10-08: el codigo y la version, solo con la tarjeta
    // abierta (AC2.3.1 movido adentro).
    renderWithProviders(<Citation citation={EN_ESPANOL} conversationLocale="es" />);
    expect(screen.queryByText(/RC-04/)).toBeNull();

    await userEvent.click(screen.getByRole("button"));

    expect(screen.getByText(/RC-04/)).toBeTruthy();
    expect(screen.getByText(/2026\.4/)).toBeTruthy();
  });

  it("con traduccion muestra la traduccion y el original a un clic", async () => {
    renderWithProviders(
      <Citation
        citation={{ ...EN_INGLES, translated_text: "Texto traducido.", translated_part: "Parte D" }}
        conversationLocale="es"
      />,
    );
    expect(screen.getByText("Parte D")).toBeTruthy();

    const [primero] = screen.getAllByRole("button");
    if (primero === undefined) {
      throw new Error("la tarjeta no dibujo ningun boton");
    }
    await userEvent.click(primero);
    expect(screen.getByText("Texto traducido.")).toBeTruthy();
    expect(screen.queryByText(EN_INGLES.text)).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Ver el texto original" }));
    expect(screen.getByText(EN_INGLES.text)).toBeTruthy();
  });

  it("al abrirla muestra el texto completo, literal", async () => {
    renderWithProviders(<Citation citation={EN_ESPANOL} conversationLocale="es" />);
    await userEvent.click(screen.getByRole("button"));

    expect(screen.getByText(EN_ESPANOL.text)).toBeTruthy();
    // Sin etiqueta sobre el texto de la clausula (2026-10-09).
    expect(screen.queryByText(/tal como está en la póliza/)).toBeNull();
  });

  it("todo va a la izquierda: el disparador arranca a la izquierda y la flecha va junto al titulo", () => {
    renderWithProviders(<Citation citation={EN_ESPANOL} conversationLocale="es" />);
    const disparador = screen.getByRole("button");

    expect(disparador.className).toContain("justify-start");
    expect(disparador.className).toContain("text-left");
    // La flecha esta dentro de la fila del titulo, no suelta al final del boton.
    const titulo = screen.getByText("Ver la cláusula exacta").parentElement;
    expect(titulo?.querySelector("svg")).not.toBeNull();
  });

  it("una clausula en otro idioma se etiqueta y se deja en el suyo", async () => {
    renderWithProviders(<Citation citation={EN_INGLES} conversationLocale="es" />);
    await userEvent.click(screen.getByRole("button"));

    // El texto literal, **sin traducir**: es lo que su poliza dice.
    const literal = screen.getByText(EN_INGLES.text);
    expect(literal.getAttribute("lang")).toBe("en");
    // Y se dice en que idioma esta, en el idioma de la conversacion.
    // El idioma de la clausula en el de la conversacion: "inglés", no "English".
    expect(screen.getByText(/escrita en inglés/)).toBeTruthy();
  });

  it("una clausula en el idioma de la conversacion no lleva ese aviso", async () => {
    // El control que distingue: sin el, la prueba de arriba pasaria con una
    // implementacion que pusiera el aviso siempre.
    renderWithProviders(<Citation citation={EN_ESPANOL} conversationLocale="es" />);
    await userEvent.click(screen.getByRole("button"));

    expect(screen.queryByText(/está escrita en/)).toBeNull();
    expect(screen.getByText(EN_ESPANOL.text).getAttribute("lang")).toBe("es");
  });

  it("avisa cuando un cambio posterior afecta al monto de la clausula", async () => {
    renderWithProviders(
      <Citation citation={{ ...EN_ESPANOL, amount_deferred: true }} conversationLocale="es" />,
    );
    await userEvent.click(screen.getByRole("button"));

    expect(screen.getByText(/lo confirma un ajustador/)).toBeTruthy();
  });

  it("sin traza no dibuja el enlace al resumen", async () => {
    renderWithProviders(<Citation citation={EN_ESPANOL} conversationLocale="es" />);
    await userEvent.click(screen.getByRole("button"));

    expect(screen.queryByRole("link")).toBeNull();
  });
});

// Dos tarjetas de una misma respuesta no pueden leerse igual (C17 de la auditoria del
// 2026-10-10). El corpus no trae un titulo por clausula: lo que las distingue es el
// numero de su condicion especial o, si comparten parte, su lugar entre las que la
// comparten.
/** Solo la posicion de cada cita, en el orden en que llegaron. */
function posicionesDe(citas: readonly WireCitation[]) {
  return withPositions(citas).map(({ position }) => position);
}

describe("el rotulo de cada tarjeta", () => {
  const PARTE_D: WireCitation = {
    ...EN_ESPANOL,
    clause_id: "STO-PAP-2026-D.EXCL.3",
    part: "Parte D — Daños a su vehículo",
  };
  const OTRA_PARTE_D: WireCitation = { ...PARTE_D, clause_id: "STO-PAP-2026-D.EXCL.4" };
  const PARTE_F: WireCitation = {
    ...PARTE_D,
    clause_id: "STO-PAP-2026-F.TERMINATION",
    part: "Parte F — Disposiciones generales",
  };
  const CONDICION_5: WireCitation = {
    ...PARTE_D,
    clause_id: "STO-PAP-2026-END-5-F.TERMINATION",
    part: "Endosos",
    special_condition_number: 5,
  };

  it("dos clausulas de la misma parte se numeran y el boton de cada una se distingue", () => {
    renderWithProviders(
      <>
        {withPositions([PARTE_D, OTRA_PARTE_D]).map(({ citation, position }) => (
          <Citation
            key={citation.clause_id}
            citation={citation}
            conversationLocale="es"
            position={position}
          />
        ))}
      </>,
    );

    const [primera, segunda] = screen.getAllByRole("button");
    expect(primera?.textContent).toContain("Parte D — Daños a su vehículo");
    expect(primera?.textContent).toContain("cláusula 1 de 2");
    expect(segunda?.textContent).toContain("cláusula 2 de 2");
    expect(primera?.textContent).not.toBe(segunda?.textContent);
  });

  it("una clausula que no comparte rotulo no lleva numero", () => {
    renderWithProviders(<Citation citation={PARTE_D} conversationLocale="es" />);

    expect(screen.queryByText(/cláusula \d de \d/)).toBeNull();
  });

  it("numera por rotulo: partes distintas, o condiciones especiales distintas, no se numeran", () => {
    const otraCondicion = { ...CONDICION_5, special_condition_number: 3 };

    expect(posicionesDe([PARTE_D, PARTE_F, CONDICION_5, otraCondicion])).toEqual([
      undefined,
      undefined,
      undefined,
      undefined,
    ]);
    expect(posicionesDe([PARTE_D, PARTE_F, OTRA_PARTE_D])).toEqual([
      { index: 1, total: 2 },
      undefined,
      { index: 2, total: 2 },
    ]);
    expect(posicionesDe([CONDICION_5, { ...CONDICION_5, clause_id: "otra" }])).toEqual([
      { index: 1, total: 2 },
      { index: 2, total: 2 },
    ]);
  });

  it("agrupa por la parte que se ve: la traducida, si la hay", () => {
    const traducida = { ...EN_INGLES, translated_part: "Parte D" };
    const otra = { ...EN_INGLES, clause_id: "LI-10", translated_part: "Parte D" };

    expect(posicionesDe([traducida, otra])).toEqual([
      { index: 1, total: 2 },
      { index: 2, total: 2 },
    ]);
  });

  it("una condicion especial se llama asi y no por la parte del corpus", () => {
    renderWithProviders(<Citation citation={CONDICION_5} conversationLocale="es" />);

    expect(screen.getByText("Condición especial 5")).toBeTruthy();
    expect(screen.queryByText(/endoso/i)).toBeNull();
  });

  it('en ingles dice "Special condition" y numera con su palabra', () => {
    renderWithProviders(
      <Citation citation={CONDICION_5} conversationLocale="en" position={{ index: 2, total: 3 }} />,
      "en",
    );

    expect(screen.getByText("Special condition 5")).toBeTruthy();
    expect(screen.getByText("clause 2 of 3")).toBeTruthy();
  });

  it("el identificador queda como referencia dentro de la tarjeta abierta, no como titulo", async () => {
    renderWithProviders(<Citation citation={PARTE_D} conversationLocale="es" />);
    expect(screen.queryByText(/D\.EXCL\.3/)).toBeNull();

    await userEvent.click(screen.getByRole("button"));

    expect(screen.getByText(/D\.EXCL\.3/)).toBeTruthy();
  });
});
