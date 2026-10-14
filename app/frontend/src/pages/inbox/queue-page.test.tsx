import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../app/testing";
import type { InboxResult, QueueItem, QueuePage } from "../../shared/api-client/inbox";
import { createTranslate } from "../../shared/i18n/translate";
import type { WireInboxEvent } from "./inbox-events";
import { CasesQueuePage } from "./queue-page";

// La cola: su orden, su fila, sus filtros y su aviso en vivo (BR1.1 a BR1.3, BR6.1).

const pedidos = vi.hoisted(() =>
  vi.fn<(tenantId: string, filters: object, cursor?: string) => Promise<InboxResult<QueuePage>>>(),
);

vi.mock("../../shared/api-client/inbox", async (original) => {
  const real = await original<typeof import("../../shared/api-client/inbox")>();
  return { ...real, listCases: pedidos };
});

const AHORA = new Date("2026-09-28T12:00:00Z");
const t = createTranslate("es");

function fila(caseId: string, extra: Partial<QueueItem> = {}): QueueItem {
  return {
    case_id: caseId,
    case_number: `CAS-${caseId}`,
    state: "derived",
    record_type: "claim",
    channel: "chat",
    language: "es",
    priority: "normal",
    completeness: 0.43,
    completeness_complete: 3,
    completeness_total: 7,
    derivation_reason: "rule",
    updated_at: "2026-09-28T11:30:00+00:00",
    ...extra,
  };
}

function pagina(items: readonly QueueItem[], next: string | null = null): InboxResult<QueuePage> {
  return { ok: true, value: { items: [...items], next_cursor: next } };
}

/** Un flujo de mentira con la forma de `EventSource`. */
function flujoDeMentira() {
  const flujo = {
    onopen: null,
    onmessage: null as ((evento: MessageEvent<string>) => void) | null,
    onerror: null,
    cerrado: false,
    close() {
      this.cerrado = true;
    },
  };
  return {
    flujo,
    abrir: () => flujo as unknown as EventSource,
    empujar(evento: WireInboxEvent) {
      act(() => {
        flujo.onmessage?.(new MessageEvent("message", { data: JSON.stringify(evento) }));
      });
    },
  };
}

function dibujar(
  filtros: Record<string, string> = {},
  cambio: (f: Record<string, string>) => void = () => undefined,
  cable = flujoDeMentira(),
) {
  renderWithProviders(
    <CasesQueuePage
      tenantId="una-aseguradora"
      insurerLabel="Una Aseguradora"
      filters={filtros}
      onFiltersChange={cambio as (f: object) => void}
      caseHref={(caseId) => `/t/una-aseguradora/inbox/${caseId}`}
      openStream={cable.abrir}
      now={() => AHORA}
    />,
  );
  return cable;
}

/**
 * La fila numero `n` de la tabla, o un fallo que la nombra.
 *
 * La primera es el encabezado. Existe porque el proyecto comprueba los indices: sin
 * esto, cada acceso llevaria un `!` y una fila que no esta se veria como un `undefined`
 * en el mensaje de la prueba en vez de como su nombre.
 */
function filaNumero(filas: readonly HTMLElement[], n: number): HTMLElement {
  const fila = filas.at(n);
  if (fila === undefined) {
    throw new Error(`la tabla no tiene la fila ${String(n)}: llegaron ${String(filas.length)}`);
  }
  return fila;
}

beforeEach(() => {
  pedidos.mockReset();
  pedidos.mockResolvedValue(pagina([fila("a")]));
});

describe("la cola de casos", () => {
  it("dice que es una pagina para el personal de la aseguradora (fase 3)", async () => {
    dibujar();

    expect((await screen.findByTestId("staff-note")).textContent).toMatch(/personal/);
  });

  it("dibuja las filas en el orden en que el servidor las devolvio (BR1.1)", async () => {
    // El orden lo decide el servidor: prioridad primero y, dentro de cada prioridad,
    // espera mas larga delante. La prueba manda una prioridad alta **detras** de una
    // normal: si la pantalla ordenara por su cuenta, las cambiaria de sitio.
    pedidos.mockResolvedValue(pagina([fila("normal"), fila("alta", { priority: "high" })]));
    dibujar();

    const filas = await screen.findAllByRole("row");
    // La primera es el encabezado de la tabla.
    expect(within(filaNumero(filas, 1)).getByRole("link").textContent).toContain("CAS-normal");
    expect(within(filaNumero(filas, 2)).getByRole("link").textContent).toContain("CAS-alta");
  });

  it("cada fila lleva sus seis datos (BR1.2)", async () => {
    pedidos.mockResolvedValue(
      pagina([
        fila("a", {
          priority: "high",
          channel: "voice",
          language: "en",
          state: "awaiting_insured",
        }),
      ]),
    );
    dibujar();

    const filas = await screen.findAllByRole("row");
    const texto = filaNumero(filas, 1).textContent;
    expect(texto).toContain(t("inbox.completeness", { complete: 3, total: 7 }));
    expect(texto).toContain(t("case.record_type.claim"));
    expect(texto).toContain(t("case.channel.voice"));
    expect(texto).toContain(t("shell.language.en"));
    expect(texto).toContain(t("inbox.priority.high"));
    expect(texto).toContain(t("inbox.waited.minutes", { value: 30 }));
  });

  it("una solicitud de cotizacion se lee como tal en la cola (U19, BR4.2)", async () => {
    // La bandeja del suscriptor es esta misma pantalla: lo que cambia es lo que el
    // servidor le entrega. Si la fila dijera "siniestro", quien decide cotizaciones
    // estaria leyendo la etiqueta equivocada en todas sus filas.
    pedidos.mockResolvedValue(pagina([fila("a", { record_type: "quote_request" })]));
    dibujar();

    const filas = await screen.findAllByRole("row");
    const texto = filaNumero(filas, 1).textContent;
    expect(texto).toContain(t("case.record_type.quote_request"));
    expect(texto).not.toContain(t("case.record_type.claim"));
  });

  it("un caso que espera al asegurado aparece con su completitud (BR1.5)", async () => {
    // Un caso a medias que no aparece es un caso perdido.
    pedidos.mockResolvedValue(
      pagina([fila("a", { state: "awaiting_insured", completeness_complete: 3 })]),
    );
    dibujar();

    const filas = await screen.findAllByRole("row");
    expect(filaNumero(filas, 1).textContent).toContain(t("case.state.awaiting_insured"));
    expect(filaNumero(filas, 1).textContent).toContain(
      t("inbox.completeness", { complete: 3, total: 7 }),
    );
  });

  it("un filtro sin resultados lo dice y ofrece quitarlos (BR1.3)", async () => {
    // Una lista vacia sin explicacion se lee como una bandeja vacia, que es lo
    // contrario de lo que paso.
    pedidos.mockResolvedValue(pagina([]));
    const quitados: Record<string, string>[] = [];
    dibujar({ priority: "high" }, (f) => quitados.push(f));

    const aviso = await screen.findByTestId("queue-empty");
    expect(aviso.textContent).toContain(t("inbox.queue.empty_filtered"));

    await userEvent.click(
      within(aviso).getByRole("button", { name: t("inbox.queue.filter_clear") }),
    );
    expect(quitados).toEqual([{}]);
  });

  it("una bandeja vacia sin filtros dice otra cosa", async () => {
    // Sin esta mitad, la frase de "ningun caso coincide" saldria en una bandeja que de
    // verdad esta vacia, y diria que hay casos escondidos detras de un filtro.
    pedidos.mockResolvedValue(pagina([]));
    dibujar();

    const aviso = await screen.findByTestId("queue-empty");
    expect(aviso.textContent).toContain(t("inbox.queue.empty"));
    expect(aviso.textContent).not.toContain(t("inbox.queue.empty_filtered"));
  });

  it("los filtros salen de la direccion y volver a filtrar la cambia", async () => {
    // Viven en la direccion y no en memoria: una cola filtrada que se pierde al
    // recargar obliga a volver a filtrar en cada vuelta.
    const cambios: Record<string, string>[] = [];
    dibujar({ state: "derived" }, (f) => cambios.push(f));

    const selector = await screen.findByLabelText(t("inbox.queue.filter_state"));
    expect((selector as HTMLSelectElement).value).toBe("derived");

    await userEvent.selectOptions(screen.getByLabelText(t("inbox.queue.filter_priority")), "high");
    expect(cambios).toEqual([{ state: "derived", priority: "high" }]);
  });

  it("elegir 'todos' quita ese filtro de la direccion", async () => {
    const cambios: Record<string, string>[] = [];
    dibujar({ state: "derived", priority: "high" }, (f) => cambios.push(f));

    await screen.findByTestId("queue-filters");
    await userEvent.selectOptions(screen.getByLabelText(t("inbox.queue.filter_state")), "");

    expect(cambios).toEqual([{ priority: "high" }]);
  });

  it("los filtros viajan al servidor tal como estan en la direccion", async () => {
    dibujar({ state: "derived", channel: "chat", language: "es", priority: "high" });

    await screen.findAllByRole("row");
    expect(pedidos).toHaveBeenCalledWith("una-aseguradora", {
      state: "derived",
      channel: "chat",
      language: "es",
      priority: "high",
    });
  });

  it("anuncia cuantos casos quedaron, para quien no ve la lista cambiar", async () => {
    pedidos.mockResolvedValue(pagina([fila("a"), fila("b")]));
    dibujar();

    // Se **espera** el anuncio en vez de leerlo justo despues de las filas: el
    // anuncio lo pone el anunciador compartido, que vive en la raiz, asi que llega en
    // un dibujo posterior al de la lista. Leerlo en el mismo instante es una carrera,
    // y pasaba sola pero fallaba en la suite completa, donde la maquina va mas
    // cargada. Lo encontro la corrida entera de la tanda 4.
    await waitFor(() => {
      expect(screen.getByTestId("announcer-status").textContent).toBe(
        t("inbox.queue.results", { count: 2 }),
      );
    });
  });

  it("un aviso de decision saca el caso de la lista (BR6.1)", async () => {
    pedidos.mockResolvedValue(pagina([fila("a"), fila("b")]));
    const cable = dibujar();

    await screen.findAllByRole("row");
    cable.empujar({
      kind: "case_decided",
      case_id: "a",
      summary: "decidido: approved",
      at: "2026-09-28T12:05:00+00:00",
    });

    const filas = screen.getAllByRole("row");
    expect(filas).toHaveLength(2);
    expect(filaNumero(filas, 1).textContent).toContain("CAS-b");
  });

  it("un aviso de un caso que no esta en la pagina ofrece traer lo nuevo", async () => {
    const cable = dibujar();
    await screen.findAllByRole("row");

    cable.empujar({
      kind: "case_created",
      case_id: "nuevo",
      summary: "creado",
      at: "2026-09-28T12:05:00+00:00",
    });

    expect(screen.getByTestId("queue-stale")).toBeTruthy();
    await userEvent.click(within(screen.getByTestId("queue-stale")).getByRole("button"));
    expect(pedidos).toHaveBeenCalledTimes(2);
  });

  it("cierra el flujo al salir, para no aplicar cada aviso dos veces", async () => {
    const cable = flujoDeMentira();
    const { unmount } = renderWithProviders(
      <CasesQueuePage
        tenantId="una-aseguradora"
        insurerLabel="Una Aseguradora"
        filters={{}}
        onFiltersChange={() => undefined}
        caseHref={(id) => `/${id}`}
        openStream={cable.abrir}
        now={() => AHORA}
      />,
    );
    await screen.findAllByRole("row");

    unmount();

    expect(cable.flujo.cerrado).toBe(true);
  });

  it("un rechazo del servidor se dice con el texto del catalogo y no con su codigo", async () => {
    // Una credencial de otra aseguradora recibe exactamente lo que recibe una
    // ilegible, y esta pantalla no intenta distinguirlo: lo dice como cualquier otro
    // error.
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    pedidos.mockResolvedValue({
      ok: false,
      problem: { code: "not_found", message: (tt) => tt("problem.not_found") },
    });
    dibujar();

    const aviso = await screen.findByTestId("queue-problem");
    expect(aviso.textContent).toBe(t("problem.not_found"));
  });

  it("la pagina siguiente se anade al final", async () => {
    pedidos.mockResolvedValueOnce(pagina([fila("a")], "cursor-1"));
    dibujar();
    await screen.findAllByRole("row");

    pedidos.mockResolvedValueOnce(pagina([fila("b")]));
    await userEvent.click(screen.getByRole("button", { name: t("inbox.queue.more") }));

    const filas = screen.getAllByRole("row");
    expect(filaNumero(filas, 1).textContent).toContain("CAS-a");
    expect(filaNumero(filas, 2).textContent).toContain("CAS-b");
    expect(pedidos).toHaveBeenLastCalledWith("una-aseguradora", {}, "cursor-1");
  });

  it("la tabla se desplaza dentro de su contenedor y no arrastra la pagina", async () => {
    // D25: es una consecuencia concreta de la linea base de accesibilidad.
    dibujar();
    const filas = await screen.findAllByRole("row");
    const tabla = filaNumero(filas, 0).closest("table");

    expect(tabla?.parentElement?.className).toContain("overflow-x-auto");
  });
});
