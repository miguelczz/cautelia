import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import siteExample from "../../../../contracts/examples/site-directory.json";
import { renderWithProviders } from "../../app/testing";
import { installFakeServer, jsonResponse } from "../../shared/api-client/fake-server";
import type {
  ChatCaseStatus,
  ChatHistory,
  ChatReasoning,
  SendOutcome,
} from "../../shared/api-client/chat";
import { createTranslate } from "../../shared/i18n/translate";
import { ChatPage, REVIEW_CEILING_MS } from "./chat-page";
import type { WireEvent } from "./chat-events";

const es = createTranslate("es");

const enviado = vi.hoisted(() => vi.fn<(tenantId: string, text: string) => Promise<SendOutcome>>());
const historial = vi.hoisted(() => vi.fn<(tenantId: string) => Promise<ChatHistory | null>>());
const estadoDelCaso = vi.hoisted(() =>
  vi.fn<(tenantId: string) => Promise<ChatCaseStatus | null>>(),
);
const reinicio = vi.hoisted(() => vi.fn<(tenantId: string) => Promise<ChatHistory | null>>());
const pensamiento = vi.hoisted(() =>
  vi.fn<(tenantId: string, locale: string) => Promise<ChatReasoning | null>>(),
);

vi.mock("../../shared/api-client/chat", async (original) => {
  const real = await original<typeof import("../../shared/api-client/chat")>();
  return {
    ...real,
    sendMessage: enviado,
    history: historial,
    caseStatus: estadoDelCaso,
    resetConversation: reinicio,
    caseReasoning: pensamiento,
  };
});

/** Un flujo de mentira con la forma de `EventSource`: se le empujan eventos. */
function flujoDeMentira() {
  const flujo = {
    onopen: null as ((evento: Event) => void) | null,
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
    /** El servidor acepto la conexion: es cuando la pantalla pide el historial. */
    conectar() {
      act(() => {
        flujo.onopen?.(new Event("open"));
      });
    },
    empujar(evento: WireEvent) {
      // Dentro de `act`: el evento llega de fuera de React, como en la pagina, y
      // sin esto la actualizacion queda pendiente y la prueba mira una pantalla
      // que todavia no se dibujo.
      act(() => {
        flujo.onmessage?.(new MessageEvent("message", { data: JSON.stringify(evento) }));
      });
    },
  };
}

let quitarServidor: (() => void) | undefined;

afterEach(() => {
  quitarServidor?.();
  quitarServidor = undefined;
});

beforeEach(() => {
  // jsdom no trae `showModal` ni `close`: el navegador si, y es lo que usan las ventanas.
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
  enviado.mockReset();
  enviado.mockResolvedValue({
    outcome: "accepted",
    accepted: { session_id: "chat-1", language: "es" },
  });
  historial.mockReset();
  historial.mockResolvedValue({ opening: null, turns: [], case_number: null, language: "es" });
  estadoDelCaso.mockReset();
  estadoDelCaso.mockResolvedValue(null);
  reinicio.mockReset();
  reinicio.mockResolvedValue({
    opening: { message_id: "opening-chat-9", text: "Hola, soy Catalina.", language: "es" },
    turns: [],
    case_number: null,
    language: "es",
  });
});

describe("la pantalla del chat", () => {
  it("manda lo escrito y lo muestra en la conversacion", async () => {
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );

    await userEvent.type(screen.getByLabelText("Tu mensaje"), "Me chocaron por detrás");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));

    // Con el idioma de la pantalla (P2): la agente contesta en el salvo senal clara.
    expect(enviado).toHaveBeenCalledWith("una-aseguradora", "Me chocaron por detrás", {
      locale: "es",
    });
    expect(screen.getByText("Me chocaron por detrás")).toBeTruthy();
  });

  it("manda con Enter, y con Mayus+Enter salta de linea sin mandar", async () => {
    // Los dos lados, porque con uno solo la prueba pasa igual contra un codigo que
    // mande con cualquier Enter -- que es peor que no tener el atajo: quien quiera
    // separar un parrafo manda el mensaje a medias.
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    const escrito = screen.getByLabelText("Tu mensaje");

    await userEvent.type(escrito, "Primera línea{Shift>}{Enter}{/Shift}segunda línea");
    expect(enviado).not.toHaveBeenCalled();

    await userEvent.type(escrito, "{Enter}");
    expect(enviado).toHaveBeenCalledWith("una-aseguradora", "Primera línea\nsegunda línea", {
      locale: "es",
    });
  });

  it("dibuja la respuesta que llega por el flujo, con su cita", async () => {
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );

    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "Su póliza lo cubre.",
      language: "es",
      case_id: "caso-1",
      citations: [
        {
          clause_id: "RC-04",
          clause_version: "2026.4",
          part: "Responsabilidad civil",
          text: "La compañía responde por los daños a terceros.",
          clause_language: "es",
          amount_deferred: false,
          trace_ref: "tr-1",
        },
      ],
    });

    // Dentro de la conversacion: la misma frase esta ademas en la region que
    // anuncia al lector de pantalla, y buscarla suelta encontraria las dos.
    const conversacion = within(screen.getByTestId("chat-transcript"));
    expect(await conversacion.findByText("Su póliza lo cubre.")).toBeTruthy();
    // La tarjeta de la cita, cerrada: el codigo solo se ve al abrirla (2026-10-08).
    expect(conversacion.getByRole("button", { name: /Ver la cláusula exacta/ })).toBeTruthy();
    // Y dice en que idioma esta respondiendo, que es lo que AC1.2.x deja ver.
    expect(screen.getByText(/Respondiendo en/)).toBeTruthy();
  });

  it("dos clausulas de la misma parte se rotulan distinto, y una condicion especial se llama asi", async () => {
    // C17 de la auditoria del 2026-10-10: dos tarjetas "Parte D — Daños a su vehiculo"
    // sin forma de distinguirlas. El corpus no trae un titulo por clausula.
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    const clausula = {
      clause_version: "2026.1",
      part: "Parte D — Daños a su vehículo",
      text: "No cubrimos los daños sufridos en carreras.",
      clause_language: "es" as const,
      amount_deferred: false,
      trace_ref: "tr-1",
    };

    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "Encontré estas cláusulas.",
      language: "es",
      case_id: "caso-1",
      citations: [
        { ...clausula, clause_id: "STO-PAP-2026-D.EXCL.3" },
        { ...clausula, clause_id: "STO-PAP-2026-D.EXCL.4" },
        {
          ...clausula,
          clause_id: "STO-PAP-2026-END-5-F.TERMINATION",
          part: "Endosos",
          special_condition_number: 5,
        },
      ],
    });

    const conversacion = within(screen.getByTestId("chat-transcript"));
    const tarjetas = await conversacion.findAllByRole("button", { name: /Ver la cláusula exacta/ });
    const rotulos = tarjetas.map((tarjeta) => tarjeta.textContent);
    expect(rotulos).toHaveLength(3);
    expect(new Set(rotulos).size).toBe(3);
    expect(rotulos[0]).toContain("cláusula 1 de 2");
    expect(rotulos[1]).toContain("cláusula 2 de 2");
    // Sola en su rotulo: sin numero. Y nunca la palabra "endoso".
    expect(rotulos[2]).toContain("Condición especial 5");
    expect(rotulos[2]).not.toMatch(/cláusula \d de|endoso/i);
  });

  it("un limite alcanzado dice su frase, no un error generico", async () => {
    // BR3.1: el servidor manda **la clave** del limite y esta pantalla la
    // resuelve. Es el defecto que esta tanda arreglo por el otro lado: las cinco
    // claves que se mandaban no existian en el catalogo, asi que aqui no se veia
    // nada.
    enviado.mockResolvedValue({
      outcome: "rejected",
      rejected: {
        limit: "session",
        copy_key: "spend.quota.rate_limited_session",
        retry_after: null,
      },
    });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );

    await userEvent.type(screen.getByLabelText("Tu mensaje"), "Otro más");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText(/llegó a su límite de mensajes/)).toBeTruthy();
  });

  it("con la demo estrechada dice su frase, no la de error", async () => {
    // BR3.2 de U20: no se aceptan casos nuevos porque el reinicio nocturno no se
    // completo. **La frase es la de la demo y no la de error**: el chat esta en
    // pie, y decir "tuve un problema para responder eso" seria mentir sobre lo
    // que paso. Una conversacion que ya tiene caso no llega aqui (BR3.3).
    enviado.mockResolvedValue({
      outcome: "demo_closed",
      closed: { kind: "demo_closed", copy_key: "demo.reset.surfaces_closed" },
    });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );

    await userEvent.type(screen.getByLabelText("Tu mensaje"), "Me chocaron");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText(/no acepta casos nuevos por ahora/)).toBeTruthy();
    expect(screen.queryByText(/tuve un problema/i)).toBeNull();
  });

  it("firma con el nombre de la agente y muestra que escribe hasta que llega la respuesta", async () => {
    // Decision de Miguel (2026-10-06): "Catalina", no "la agente"; y mientras el
    // turno esta en curso se ve que esta escribiendo, que desaparece con la
    // respuesta. La ventana de la conversacion es una caja con su propio
    // desplazamiento, no la pagina.
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    expect(screen.getByTestId("chat-window")).toBeTruthy();
    expect(screen.queryByTestId("chat-typing")).toBeNull();

    await userEvent.type(screen.getByLabelText("Tu mensaje"), "Hola");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(screen.getByTestId("chat-typing")).toBeTruthy();
    expect(screen.getByRole("status", { name: /Catalina está escribiendo/ })).toBeTruthy();
    // Y no se manda un segundo turno encima del primero: el boton espera.
    await userEvent.type(screen.getByLabelText("Tu mensaje"), "otra cosa{Enter}");
    expect(enviado).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Enviar" }).hasAttribute("disabled")).toBe(true);

    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "Hola, soy Catalina.",
      language: "es",
      case_id: null,
      citations: [],
    });
    expect(screen.queryByTestId("chat-typing")).toBeNull();
    const conversacion = within(screen.getByTestId("chat-transcript"));
    expect(conversacion.getByText("Catalina")).toBeTruthy();
    expect(conversacion.queryByText("La agente")).toBeNull();
  });

  it("cierra el flujo al salir: una pestana, un flujo", () => {
    const cable = flujoDeMentira();
    const { unmount } = renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );

    expect(cable.flujo.cerrado).toBe(false);
    unmount();
    // Sin esto, volver a entrar deja dos abiertos y cada respuesta se ve dos veces.
    expect(cable.flujo.cerrado).toBe(true);
  });

  it("al conectar pide lo guardado y lo dibuja antes de que la persona escriba", async () => {
    // Decision de Miguel (2026-10-06): quien sale a mirar su poliza vuelve a lo que
    // dejo, y la agente se presenta al cargar y no despues del primer mensaje. Lo
    // guardado viene redactado, y la pantalla lo dice.
    historial.mockResolvedValue({
      opening: { message_id: "opening-chat-1", text: "Hola, soy Catalina.", language: "es" },
      turns: [
        {
          turn_id: "turn-1",
          speaker: "visitor",
          text: "Mi póliza es [PÓLIZA 1]",
          language: "es",
          channel: "chat",
          at: "2026-10-06T21:00:01+00:00",
        },
        {
          turn_id: "turn-2",
          speaker: "agent",
          text: "Anotado. ¿Hay heridos?",
          language: "es",
          channel: "chat",
          at: "2026-10-06T21:00:04+00:00",
        },
      ],
      case_number: "STO-000007",
      language: "es",
    });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    // Antes de conectar no se pide nada: la galleta la pone la primera respuesta.
    expect(historial).not.toHaveBeenCalled();

    cable.conectar();

    expect(historial).toHaveBeenCalledWith("una-aseguradora", "es");
    const conversacion = within(screen.getByTestId("chat-transcript"));
    expect(await conversacion.findByText("Hola, soy Catalina.")).toBeTruthy();
    expect(conversacion.getByText("Mi póliza es [PÓLIZA 1]")).toBeTruthy();
    expect(conversacion.getByText("Anotado. ¿Hay heridos?")).toBeTruthy();
    expect(screen.getByTestId("chat-history-note").textContent).toMatch(/tapados/);
    // Con caso guardado se pide donde va, y se dibuja la linea del caso.
    expect(estadoDelCaso).toHaveBeenCalledWith("una-aseguradora");
    // Y sigue lista para escribir: lo recuperado no deja ningun turno en vuelo.
    expect(screen.getByRole("button", { name: "Enviar" }).hasAttribute("disabled")).toBe(true);
    await userEvent.type(screen.getByLabelText("Tu mensaje"), "Sí, dos");
    expect(screen.getByRole("button", { name: "Enviar" }).hasAttribute("disabled")).toBe(false);
  });

  it("una conversacion nueva recibe solo la apertura, sin nota de recuperacion", async () => {
    historial.mockResolvedValue({
      opening: { message_id: "opening-chat-2", text: "Hola, soy Catalina.", language: "es" },
      turns: [],
      case_number: null,
      language: "es",
    });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );

    cable.conectar();

    const conversacion = within(screen.getByTestId("chat-transcript"));
    expect(await conversacion.findByText("Hola, soy Catalina.")).toBeTruthy();
    expect(screen.queryByTestId("chat-history-note")).toBeNull();
    // Y dice en que idioma responde y donde se cambia (P2).
    expect(screen.getByText(es("chat.page.speaking_in"))).toBeTruthy();
    // El titulo es el nombre de la aseguradora y nada mas, sin el circulo con la inicial.
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Stonecroft");
    expect(
      screen.getByTestId("chat-window").querySelector("header > span[aria-hidden]"),
    ).toBeNull();
  });

  it("muestra donde va el caso en cuanto nace: que es, cuanto falta y, al final, su numero", async () => {
    // Decision de Miguel (2026-10-06): ver el caso mientras avanza, no al final. Y
    // (2026-10-11) en palabras que cualquiera entienda: antes "Caso STO-000123 · 1 de 7
    // datos" no decia que era ni cuanto faltaba.
    estadoDelCaso.mockResolvedValue({
      case_number: "STO-000123",
      record_type: "claim",
      state: "capturing",
      complete: 5,
      total: 7,
      case_link: "/c#token-de-prueba",
    });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.conectar();
    // Antes de que exista un caso no se ve nada de esto, ni un hueco ni un enlace.
    expect(screen.queryByTestId("chat-case")).toBeNull();
    expect(screen.queryByRole("link", { name: "Ver mi caso" })).toBeNull();

    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "¿Hubo alguien herido?",
      language: "es",
      case_id: "caso-1",
      citations: [],
    });

    const linea = await screen.findByTestId("chat-case");
    expect(linea.textContent).toContain("Reporte de accidente");
    expect(linea.textContent).toContain("Faltan 2 datos");
    expect(linea.textContent).toContain("Número de tu caso: STO-000123");
    // El numero va al final, como referencia, y dice que es (C10, 2026-10-12).
    expect(linea.lastElementChild?.textContent).toBe("Número de tu caso: STO-000123");
    // Ya no se lee "5 de 7": cuanto falta se dice, no se calcula.
    expect(linea.textContent).not.toContain("de 7");
  });

  it.each([
    { tipo: "claim", total: 7, complete: 6, dice: ["Reporte de accidente", "Falta 1 dato"] },
    { tipo: "claim", total: 7, complete: 7, dice: ["Reporte de accidente", "Datos completos"] },
    { tipo: "quote_request", total: 17, complete: 4, dice: ["Cotización", "Faltan 13 datos"] },
    { tipo: undefined, total: 3, complete: 1, dice: ["Tu caso", "Faltan 2 datos"] },
  ])(
    "dice que es el caso y cuanto falta: $tipo con $complete de $total",
    async ({ tipo, total, complete, dice }) => {
      estadoDelCaso.mockResolvedValue({
        case_number: "STO-000130",
        ...(tipo === undefined ? {} : { record_type: tipo }),
        state: "capturing",
        complete,
        total,
        case_link: "/c#token",
      });
      const cable = flujoDeMentira();
      renderWithProviders(
        <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
      );
      cable.conectar();
      cable.empujar({
        kind: "turn.final",
        message_id: "m1",
        text: "Listo.",
        language: "es",
        case_id: "caso-1",
        citations: [],
      });

      const linea = await screen.findByTestId("chat-case");
      for (const frase of dice) {
        expect(linea.textContent).toContain(frase);
      }
    },
  );

  it("en una consulta de poliza no cuenta datos: nadie los esta dando", async () => {
    // Decision del 2026-10-08, que la linea sin caja habia perdido.
    estadoDelCaso.mockResolvedValue({
      case_number: "STO-000131",
      record_type: "coverage_inquiry",
      state: "capturing",
      complete: 2,
      total: 2,
      case_link: "/c#token",
    });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.conectar();
    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "Si, te cubre.",
      language: "es",
      case_id: "caso-1",
      citations: [],
    });

    const linea = await screen.findByTestId("chat-case");
    expect(linea.textContent).toContain("Consulta de póliza");
    expect(linea.textContent).toContain("Número de tu caso: STO-000131");
    expect(linea.textContent).not.toMatch(/datos|Datos/);
  });

  it("ver el caso es una accion del encabezado, junto a las demas y no suelta en otra fila", async () => {
    estadoDelCaso.mockResolvedValue({
      case_number: "STO-000123",
      record_type: "claim",
      state: "capturing",
      complete: 1,
      total: 7,
      case_link: "/c#token-de-prueba",
    });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.conectar();
    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "¿Hubo alguien herido?",
      language: "es",
      case_id: "caso-1",
      citations: [],
    });

    const enlace = await screen.findByRole("link", { name: "Ver mi caso" });
    expect(enlace.getAttribute("href")).toBe("/c#token-de-prueba");
    // En el mismo grupo que documentos, pensamiento y reiniciar; no en la linea del caso.
    const grupo = enlace.parentElement;
    expect(grupo).toBe(screen.getByTestId("chat-reasoning").parentElement);
    expect(grupo).toBe(screen.getByTestId("chat-reset").parentElement);
    expect(within(screen.getByTestId("chat-case")).queryByRole("link")).toBeNull();
  });

  it("bajo la ultima respuesta, con el caso derivado, ofrece decidirlo; la traza va en el encabezado", async () => {
    // 2026-10-09: las dos puertas a lo que pasa por dentro, sin salir a buscarlas.
    estadoDelCaso.mockResolvedValue({
      case_number: "STO-000124",
      state: "derived",
      complete: 7,
      total: 7,
      case_link: "/c#token-derivado",
    });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage
        tenantId="una-aseguradora"
        insurerLabel="Stonecroft"
        openStream={cable.abrir}
        traceHref={(ref) => `/traza/${ref}`}
      />,
    );
    cable.conectar();
    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "Le paso su caso a un ajustador.",
      language: "es",
      case_id: "caso-1",
      citations: [],
      trace_ref: "tr-1",
    });

    const fila = await screen.findByTestId("chat-inside");
    // Ya no se repite la traza bajo la respuesta: vive en el boton del encabezado.
    expect(within(fila).queryByRole("link", { name: /pensó|pensamiento/ })).toBeNull();
    expect(
      within(fila)
        .getByRole("link", { name: "Decidir este caso como ajustador" })
        .getAttribute("href"),
    ).toBe("/c#token-derivado");
  });

  it.each(["verifying", "deciding", "closed"] as const)(
    "con el caso en %s ofrece abrirlo, pero no decidirlo ni dice que esta con un ajustador (US1.17)",
    async (estado) => {
      // Despues de la captura el caso pasa unos segundos evaluandose y puede cerrarse solo
      // (cierre directo): ninguno de esos estados es «derivado», y el boton de decidir como
      // ajustador es solo del derivado.
      estadoDelCaso.mockResolvedValue({
        case_number: "STO-000124",
        state: estado,
        complete: 7,
        total: 7,
        case_link: "/c#token-de-prueba",
      });
      const cable = flujoDeMentira();
      renderWithProviders(
        <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
      );
      cable.conectar();
      cable.empujar({
        kind: "turn.final",
        message_id: "m1",
        text: "Su siniestro quedó registrado.",
        language: "es",
        case_id: "caso-1",
        citations: [],
      });

      const enlace = await screen.findByRole("link", { name: "Ver mi caso" });
      expect(enlace.getAttribute("href")).toBe("/c#token-de-prueba");
      expect(screen.queryByRole("link", { name: "Decidir este caso como ajustador" })).toBeNull();
      expect(screen.queryByTestId("chat-inside")).toBeNull();
      // La linea del caso no pinta el estado con palabras del derivado ni uno en crudo.
      const linea = screen.getByTestId("chat-case").textContent;
      expect(linea).not.toMatch(/ajustador|verifying|deciding|closed/i);
    },
  );

  // El resultado del cierre llega segundos despues y sin turno de la persona: es un
  // `turn.final` de fondo (`message_id` «background-…») que se publica cuando el caso ya cambio de
  // estado (2026-10-13). La pantalla relee el estado del caso con ese evento, una vez por evento.
  it("el aviso de fondo con el resultado relee el estado del caso: aparece el boton de decidir", async () => {
    estadoDelCaso
      .mockResolvedValueOnce({
        case_number: "STO-000124",
        state: "deciding",
        complete: 7,
        total: 7,
        case_link: "/c#token",
      })
      .mockResolvedValue({
        case_number: "STO-000124",
        state: "derived",
        complete: 7,
        total: 7,
        case_link: "/c#token-derivado",
      });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.conectar();
    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "Estoy revisando su caso.",
      language: "es",
      case_id: "caso-1",
      citations: [],
    });
    await screen.findByTestId("chat-case");
    // Con el caso evaluandose no hay boton de decidir, pero si el enlace a su caso.
    expect(screen.queryByRole("link", { name: "Decidir este caso como ajustador" })).toBeNull();
    expect(screen.getByRole("link", { name: "Ver mi caso" }).getAttribute("href")).toBe("/c#token");
    expect(estadoDelCaso).toHaveBeenCalledTimes(1);

    cable.empujar({
      kind: "turn.final",
      message_id: "background-caso-1-ab12cd34",
      text: "Le paso su caso a un ajustador.",
      language: "es",
      case_id: "caso-1",
      citations: [],
    });

    expect(
      (await screen.findByRole("link", { name: "Decidir este caso como ajustador" })).getAttribute(
        "href",
      ),
    ).toBe("/c#token-derivado");
    // Una relectura por evento: la del turno y la del aviso, ni una mas.
    expect(estadoDelCaso).toHaveBeenCalledTimes(2);
  });

  it("el aviso de fondo de un cierre directo deja el enlace al caso y ningun boton de decidir", async () => {
    estadoDelCaso
      .mockResolvedValueOnce({
        case_number: "STO-000124",
        state: "deciding",
        complete: 7,
        total: 7,
        case_link: "/c#token",
      })
      .mockResolvedValue({
        case_number: "STO-000124",
        state: "closed",
        complete: 7,
        total: 7,
        case_link: "/c#token-cerrado",
      });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.conectar();
    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "Estoy revisando su caso.",
      language: "es",
      case_id: "caso-1",
      citations: [],
    });
    await screen.findByTestId("chat-case");
    cable.empujar({
      kind: "turn.final",
      message_id: "background-caso-1-ab12cd34",
      text: "Su siniestro quedó registrado.",
      language: "es",
      case_id: "caso-1",
      citations: [],
    });

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "Ver mi caso" }).getAttribute("href")).toBe(
        "/c#token-cerrado",
      );
    });
    expect(screen.queryByRole("link", { name: "Decidir este caso como ajustador" })).toBeNull();
    expect(estadoDelCaso).toHaveBeenCalledTimes(2);
  });

  it("una lectura vieja que llega tarde no pisa la del aviso de fondo", async () => {
    // La del turno tarda mas que la del aviso: sin numerarlas, el estado «evaluando» de la
    // primera pisaria al «derivado» de la segunda y el boton de decidir nunca aparecia.
    let resolverLaVieja: (valor: ChatCaseStatus) => void = () => undefined;
    estadoDelCaso
      .mockImplementationOnce(
        () =>
          new Promise<ChatCaseStatus>((resolve) => {
            resolverLaVieja = resolve;
          }),
      )
      .mockResolvedValue({
        case_number: "STO-000124",
        state: "derived",
        complete: 7,
        total: 7,
        case_link: "/c#token-derivado",
      });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.conectar();
    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "Estoy revisando su caso.",
      language: "es",
      case_id: "caso-1",
      citations: [],
    });
    cable.empujar({
      kind: "turn.final",
      message_id: "background-caso-1-ab12cd34",
      text: "Le paso su caso a un ajustador.",
      language: "es",
      case_id: "caso-1",
      citations: [],
    });
    await screen.findByRole("link", { name: "Decidir este caso como ajustador" });

    await act(async () => {
      resolverLaVieja({
        case_number: "STO-000124",
        state: "deciding",
        complete: 7,
        total: 7,
        case_link: "/c#token-viejo",
      });
      await Promise.resolve();
    });

    expect(
      screen.getByRole("link", { name: "Decidir este caso como ajustador" }).getAttribute("href"),
    ).toBe("/c#token-derivado");
    expect(screen.getByTestId("chat-case-link").getAttribute("href")).toBe("/c#token-derivado");
  });

  it("cuando el caso se deriva, el boton de decidir aparece a la vista: la conversacion baja hasta mostrarlo", async () => {
    // C12 de la auditoria del 2026-10-10. El estado del caso se pide despues de la
    // respuesta: la conversacion ya habia bajado, y el boton nacia debajo de lo visible,
    // oculto tras el cuadro de escribir hasta que la persona desplazaba.
    estadoDelCaso
      .mockResolvedValueOnce({
        case_number: "STO-000124",
        state: "capturing",
        complete: 6,
        total: 7,
        case_link: "/c#token",
      })
      .mockResolvedValue({
        case_number: "STO-000124",
        state: "derived",
        complete: 7,
        total: 7,
        case_link: "/c#token-derivado",
      });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.conectar();
    // jsdom no mide: el alto del contenido crece cuando el boton esta dibujado.
    const conversacion = screen.getByTestId("chat-transcript");
    Object.defineProperty(conversacion, "scrollHeight", {
      configurable: true,
      get: () => (screen.queryByTestId("chat-inside") === null ? 500 : 560),
    });

    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "¿Hubo alguien herido?",
      language: "es",
      case_id: "caso-1",
      citations: [],
    });
    await screen.findByTestId("chat-case");
    cable.empujar({
      kind: "turn.final",
      message_id: "m2",
      text: "Listo, le paso su caso a un ajustador.",
      language: "es",
      case_id: "caso-1",
      citations: [],
    });

    await screen.findByTestId("chat-inside");
    await waitFor(() => {
      expect(conversacion.scrollTop).toBe(560);
    });
  });

  it("el boton del encabezado abre el pensamiento de la agente sobre el caso", async () => {
    // 2026-10-09: antes abria la traza tecnica, que en una consulta salia vacia.
    pensamiento.mockResolvedValue({
      case_number: "STO-000127",
      record_type: "coverage_inquiry",
      state: "capturing",
      policy_ref: "POL-100042",
      derivation_reason: null,
      fields: [
        {
          field_key: "injuries",
          label_key: "case.field.injuries",
          done: true,
          optional: false,
          value: "nadie salió herido",
        },
        {
          field_key: "location",
          label_key: "case.field.location",
          done: false,
          optional: false,
          value: null,
        },
        {
          field_key: "other_parties",
          label_key: "case.field.other_parties",
          done: false,
          optional: true,
          value: null,
        },
      ],
      answers: [
        {
          question: "¿Me cubren el granizo?",
          outcome: "verified",
          clauses: [
            {
              clause_id: "STO-D.INS.OTC",
              part: "Parte D",
              verified: true,
              claim: "paga los daños por granizo",
            },
          ],
        },
      ],
    });
    // jsdom no trae `showModal`: el navegador si, y es lo que usa la ventana.
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.setAttribute("open", "");
    };
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.conectar();

    await userEvent.click(await screen.findByTestId("chat-reasoning"));

    const ventana = screen.getByTestId("reasoning-dialog");
    expect(await within(ventana).findByText(es("chat.reasoning.wants_question"))).toBeTruthy();
    expect(within(ventana).getByText(/POL-100042/)).toBeTruthy();
    expect(within(ventana).getByTestId("reasoning-clauses").textContent).toContain(
      "Parte D: paga los daños por granizo",
    );
    expect(pensamiento).toHaveBeenCalledWith("una-aseguradora", "es");
    // Lo anotado se muestra, no solo "Anotado" (decision de Miguel del 2026-10-11);
    // lo que no cuenta para la completitud se dice opcional.
    const datos = within(ventana).getByTestId("reasoning-fields").textContent;
    expect(datos).toContain("nadie salió herido");
    expect(datos).toContain(es("chat.reasoning.missing"));
    expect(datos).toContain(es("chat.reasoning.optional"));
  });

  it("las acciones del encabezado comparten un solo estilo, con el icono y el titulo en el acento", async () => {
    estadoDelCaso.mockResolvedValue({
      case_number: "STO-000140",
      record_type: "claim",
      state: "capturing",
      complete: 1,
      total: 7,
      case_link: "/c#token",
    });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage
        tenantId="una-aseguradora"
        insurerLabel="Stonecroft"
        openStream={cable.abrir}
        traceHref={(ref) => `/traza/${ref}`}
      />,
    );
    cable.conectar();
    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "¿Hubo alguien herido?",
      language: "es",
      case_id: "caso-1",
      citations: [],
    });

    expect(screen.getByRole("heading", { level: 1 }).className).toContain("text-tenant");
    const pensamiento = await screen.findByTestId("chat-reasoning");
    const verCaso = await screen.findByRole("link", { name: "Ver mi caso" });
    const documentos = screen.getByRole("button", { name: /documentos|documents/i });
    const reiniciar = screen.getByRole("button", { name: es("chat.page.reset") });
    expect(pensamiento.textContent).toContain(es("chat.page.see_reasoning", { agent: "Catalina" }));
    expect(es("chat.page.see_reasoning", { agent: "Catalina" })).toBe("Pensamiento de Catalina");
    for (const boton of [pensamiento, documentos, verCaso, reiniciar]) {
      expect(boton.className).toContain("text-fg-secondary");
      expect(boton.className).not.toMatch(/(^|\s)border(\s|$|-)/);
      expect(boton.querySelector("svg")?.getAttribute("class")).toContain("text-tenant");
    }
    // Una sola fila, en este orden: ver el caso, documentos, pensamiento, reiniciar. "Ver mi
    // caso" va primero porque aparece despues del primer mensaje: en el extremo izquierdo de un
    // grupo pegado a la derecha, al llegar no corre a los otros botones.
    const grupo = reiniciar.parentElement;
    const enOrden = [verCaso, documentos, pensamiento, reiniciar];
    for (const boton of enOrden) {
      expect(boton.parentElement).toBe(grupo);
    }
    const posiciones = enOrden.map((boton) =>
      Array.from(grupo?.children ?? []).indexOf(boton as Element),
    );
    expect(posiciones).toEqual([...posiciones].sort((a, b) => a - b));
  });

  it("reiniciar es solo un icono, con nombre accesible y title", () => {
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.conectar();

    const reiniciar = screen.getByRole("button", { name: "Reiniciar conversación" });
    // El nombre accesible va en `aria-label` y no solo en `title`: este ultimo no lo
    // anuncia todo lector de pantalla.
    expect(reiniciar.getAttribute("aria-label")).toBe("Reiniciar conversación");
    expect(reiniciar.getAttribute("title")).toBe("Reiniciar conversación");
    // Ninguna palabra a la vista, ni siquiera escondida en telefono: solo el icono.
    expect(reiniciar.textContent).toBe("");
    expect(reiniciar.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("el nombre de la agente es el de la aseguradora, en el encabezado y en su pensamiento", async () => {
    // Cada aseguradora tiene la suya (decision de Miguel, 2026-10-11): sale del directorio.
    quitarServidor = installFakeServer((ruta) =>
      ruta === "/api/site" ? jsonResponse(siteExample) : jsonResponse({}, 404),
    );
    // Una aseguradora del directorio cuya agente no sea la del catalogo: asi la prueba
    // distingue "sale del directorio" de "sale del nombre por omision".
    const propia = siteExample.tenants.find(
      (tenant) => tenant.agent_name !== es("insurer.agent.name"),
    );
    if (propia === undefined) {
      throw new Error("el ejemplo del directorio no trae una agente con nombre propio");
    }
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage
        tenantId={propia.tenant_id}
        insurerLabel={propia.display_name}
        openStream={cable.abrir}
      />,
    );
    cable.conectar();

    expect(
      await screen.findByRole("button", {
        name: es("chat.page.see_reasoning", { agent: propia.agent_name }),
      }),
    ).toBeTruthy();
    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "Hola.",
      language: "es",
      case_id: null,
      citations: [],
    });
    // Firma sus mensajes con su nombre.
    expect(await screen.findByText("Isabel")).toBeTruthy();
    expect(screen.queryByText("Catalina")).toBeNull();

    pensamiento.mockResolvedValue(null);
    await userEvent.click(screen.getByTestId("chat-reasoning"));
    const titulo = await within(screen.getByTestId("reasoning-dialog")).findByRole("heading", {
      level: 2,
    });
    expect(titulo.textContent).toBe(es("chat.reasoning.title", { agent: "Isabel" }));
  });

  it("sin caso derivado no ofrece decidirlo, y sin traza no ofrece nada", async () => {
    estadoDelCaso.mockResolvedValue({
      case_number: "STO-000125",
      state: "capturing",
      complete: 1,
      total: 7,
      case_link: "/c#token-en-curso",
    });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage
        tenantId="una-aseguradora"
        insurerLabel="Stonecroft"
        openStream={cable.abrir}
        traceHref={(ref) => `/traza/${ref}`}
      />,
    );
    cable.conectar();
    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "¿Hubo alguien herido?",
      language: "es",
      case_id: "caso-1",
      citations: [],
    });

    await screen.findByTestId("chat-case");
    expect(screen.queryByTestId("chat-inside")).toBeNull();
  });

  /** Una conversacion con un turno ya cerrado, para tener algo que reiniciar. */
  function conUnTurno(caso: ChatCaseStatus | null) {
    estadoDelCaso.mockResolvedValue(caso);
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.conectar();
    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "¿Hubo alguien herido?",
      language: "es",
      case_id: caso === null ? null : "caso-1",
      citations: [],
    });
    return cable;
  }

  it("reiniciar abre una ventana que dice que pasa; cancelar no reinicia y devuelve el foco", async () => {
    // Decision de Miguel (2026-10-11): una ventana modal en lugar de la linea de
    // confirmacion; lo de antes queda guardado con su numero de caso.
    conUnTurno(null);
    const boton = screen.getByRole("button", { name: "Reiniciar conversación" });
    const ventana = screen.getByTestId("chat-reset-confirm");
    expect(ventana.hasAttribute("open")).toBe(false);

    await userEvent.click(boton);

    expect(ventana.hasAttribute("open")).toBe(true);
    const dentro = within(ventana);
    expect(dentro.getByRole("heading", { name: "¿Reiniciar la conversación?" })).toBeTruthy();
    expect(dentro.getByText(es("chat.page.reset_body"))).toBeTruthy();
    expect(reinicio).not.toHaveBeenCalled();

    await userEvent.click(dentro.getByRole("button", { name: "Cancelar" }));

    expect(ventana.hasAttribute("open")).toBe(false);
    expect(reinicio).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(boton);
    expect(
      within(screen.getByTestId("chat-transcript")).getByText("¿Hubo alguien herido?"),
    ).toBeTruthy();
  });

  it("al confirmar, deja solo la apertura nueva y se olvida del caso", async () => {
    conUnTurno({
      case_number: "STO-000150",
      record_type: "claim",
      state: "capturing",
      complete: 2,
      total: 7,
      case_link: "/c#token",
    });
    await screen.findByTestId("chat-case");

    await userEvent.click(screen.getByRole("button", { name: "Reiniciar conversación" }));
    const ventana = screen.getByTestId("chat-reset-confirm");
    // Con caso, la ventana dice la verdad sobre el: queda guardado, pero ya no se ve aqui.
    expect(
      within(ventana).getByText(/STO-000150.*queda guardado.*ya no lo verás aquí/),
    ).toBeTruthy();
    await userEvent.click(within(ventana).getByRole("button", { name: "Reiniciar" }));

    expect(reinicio).toHaveBeenCalledWith("una-aseguradora", "es");
    const conversacion = within(screen.getByTestId("chat-transcript"));
    expect(await conversacion.findByText("Hola, soy Catalina.")).toBeTruthy();
    expect(conversacion.queryByText("¿Hubo alguien herido?")).toBeNull();
    await waitFor(() => {
      expect(ventana.hasAttribute("open")).toBe(false);
    });
    expect(screen.queryByTestId("chat-case")).toBeNull();
    expect(screen.queryByRole("link", { name: "Ver mi caso" })).toBeNull();
  });

  it("Escape cierra la ventana sin reiniciar", async () => {
    conUnTurno(null);
    const boton = screen.getByRole("button", { name: "Reiniciar conversación" });
    await userEvent.click(boton);
    const ventana = screen.getByTestId("chat-reset-confirm");

    // Lo que hace el navegador con Escape: cierra el dialogo y avisa.
    act(() => {
      ventana.removeAttribute("open");
      ventana.dispatchEvent(new Event("close"));
    });

    expect(reinicio).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(boton);
    // Y se puede volver a abrir.
    await userEvent.click(boton);
    expect(ventana.hasAttribute("open")).toBe(true);
  });

  it("si no se pudo reiniciar, la ventana se cierra y lo dice la frase de error", async () => {
    reinicio.mockResolvedValue(null);
    conUnTurno(null);

    await userEvent.click(screen.getByRole("button", { name: "Reiniciar conversación" }));
    await userEvent.click(
      within(screen.getByTestId("chat-reset-confirm")).getByRole("button", { name: "Reiniciar" }),
    );

    expect(await screen.findByText(es("chat.turn.error"))).toBeTruthy();
    expect(screen.getByTestId("chat-reset-confirm").hasAttribute("open")).toBe(false);
    expect(
      within(screen.getByTestId("chat-transcript")).getByText("¿Hubo alguien herido?"),
    ).toBeTruthy();
  });

  it("dibuja los botones que eligio el servidor, y tocar uno lo manda como mensaje", async () => {
    // Fase 0 (2026-10-07): escribir nunca es obligatorio. Los botones los decide el
    // servidor segun la pregunta; la pantalla solo los dibuja.
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.conectar();
    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "¿Me dice su nombre y el número de su póliza?",
      language: "es",
      case_id: "caso-1",
      citations: [],
      suggestions: ["Usar la póliza de ejemplo POL-100042"],
    });

    const fila = await screen.findByTestId("chat-suggestions");
    await userEvent.click(
      within(fila).getByRole("button", { name: "Usar la póliza de ejemplo POL-100042" }),
    );

    expect(enviado).toHaveBeenCalledWith(
      "una-aseguradora",
      "Usar la póliza de ejemplo POL-100042",
      { locale: "es" },
    );
    // Con el turno en vuelo no se ofrece nada mas: un turno a la vez.
    expect(screen.queryByTestId("chat-suggestions")).toBeNull();
  });

  it("sin botones en la ultima respuesta no dibuja la fila", async () => {
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.conectar();
    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "¿Qué pasó?",
      language: "es",
      case_id: "caso-1",
      citations: [],
      suggestions: [],
    });

    await within(screen.getByTestId("chat-transcript")).findByText("¿Qué pasó?");
    expect(screen.queryByTestId("chat-suggestions")).toBeNull();
  });

  it("al volver, lo que la persona escribio en este navegador vuelve a su burbuja", async () => {
    // E6 (2026-10-07): la base guarda tapado; la burbuja muestra lo escrito.
    window.localStorage.setItem(
      "cautelia.own-text.una-aseguradora",
      JSON.stringify(["Hola", "Soy Natalia Henao, póliza POL-100042"]),
    );
    historial.mockResolvedValue({
      opening: { message_id: "opening-chat-3", text: "Hola, soy Catalina.", language: "es" },
      turns: [
        {
          turn_id: "turn-1",
          speaker: "visitor",
          text: "Soy [NOMBRE 1], póliza [PÓLIZA 1]",
          language: "es",
          channel: "chat",
          at: "2026-10-07T21:00:01+00:00",
        },
      ],
      case_number: "STO-000008",
      language: "es",
    });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.conectar();

    const conversacion = within(screen.getByTestId("chat-transcript"));
    expect(await conversacion.findByText("Soy Natalia Henao, póliza POL-100042")).toBeTruthy();
    expect(conversacion.queryByText("Soy [NOMBRE 1], póliza [PÓLIZA 1]")).toBeNull();
    // Ya no queda nada tapado, asi que el aviso de las etiquetas sobra.
    expect(screen.queryByTestId("chat-history-note")).toBeNull();
    window.localStorage.clear();
  });
});

describe("el mensaje que llega desde la pestana de polizas", () => {
  it("sale solo, una vez, cuando la conversacion ya cargo su historial", async () => {
    // Fase 2 (2026-10-08): las preguntas para probar abren el chat con la poliza y la
    // pregunta ya enviadas. Antes del historial no sale, y un segundo dibujo no lo
    // repite: recargar la pagina ya no lo tiene en la direccion.
    const cable = flujoDeMentira();
    const quitado = vi.fn();
    renderWithProviders(
      <ChatPage
        tenantId="una-aseguradora"
        insurerLabel="Stonecroft"
        openStream={cable.abrir}
        initialMessage="Soy Natalia, mi póliza es POL-100042. ¿Me cubre el granizo?"
        onInitialMessageSent={quitado}
      />,
    );
    expect(enviado).not.toHaveBeenCalled();

    cable.conectar();

    await vi.waitFor(() => {
      expect(enviado).toHaveBeenCalledTimes(1);
    });
    expect(enviado.mock.calls[0]?.[1]).toBe(
      "Soy Natalia, mi póliza es POL-100042. ¿Me cubre el granizo?",
    );
    expect(quitado).toHaveBeenCalledTimes(1);
    // Otro dibujo --llega la respuesta-- no lo vuelve a enviar.
    cable.empujar({
      kind: "turn.final",
      message_id: "m-1",
      text: "Déjeme revisar su póliza.",
      language: "es",
      case_id: null,
      citations: [],
      suggestions: [],
      coverage_outcome: null,
    } as unknown as WireEvent);
    expect(enviado).toHaveBeenCalledTimes(1);
  });
});

describe("la frase de una derivacion o un error que el servidor manda (2026-10-12)", () => {
  // Visto: tras «Que lo revise un ajustador» el caso quedaba derivado y la pantalla decia
  // «Tuve un problema para responder eso», porque la clave era nueva para la tabla.
  it("la derivacion de una consulta se dice con su frase y no con la de error", async () => {
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );

    cable.empujar({
      kind: "turn.handoff",
      reason_code: "human_request",
      copy_key: "compliance.handoff.adjuster_review_inquiry",
      text: "Listo: un ajustador revisa tu consulta con la cláusula que encontramos.",
      case_id: "caso-1",
      case_link: null,
    });

    const conversacion = within(screen.getByTestId("chat-transcript"));
    expect(
      await conversacion.findByText(es("compliance.handoff.adjuster_review_inquiry")),
    ).toBeTruthy();
    expect(conversacion.queryByText(es("chat.turn.error"))).toBeNull();
  });

  it("una clave que la pantalla no conoce se dice con el texto que trajo el servidor", async () => {
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );

    cable.empujar({
      kind: "turn.handoff",
      reason_code: "rule",
      copy_key: "compliance.handoff.una_clave_nueva",
      text: "Tu caso queda con un ajustador.",
      case_id: "caso-1",
      case_link: null,
    });

    const conversacion = within(screen.getByTestId("chat-transcript"));
    expect(await conversacion.findByText("Tu caso queda con un ajustador.")).toBeTruthy();
    expect(conversacion.queryByText(es("chat.turn.error"))).toBeNull();
  });
});

describe("mientras el fondo revisa la poliza (2026-10-12)", () => {
  const ESPERA = {
    kind: "turn.final",
    message_id: "m1",
    text: "Déjame revisar tu póliza; te respondo en un momento.",
    language: "es",
    case_id: "caso-1",
    citations: [],
    answer_pending: true,
  } as const;

  afterEach(() => {
    vi.useRealTimers();
  });

  it("la conversacion muestra que se esta revisando hasta que llega la respuesta", () => {
    // Antes quedaba quieta hasta doce segundos despues de «te respondo en un momento».
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    expect(screen.queryByTestId("chat-typing")).toBeNull();

    cable.empujar(ESPERA);

    expect(screen.getByTestId("chat-typing")).toBeTruthy();
    expect(screen.getByRole("status", { name: /Catalina está revisando tu póliza/ })).toBeTruthy();
    // Ya se puede escribir: el turno cerro, solo falta lo que trae el fondo.
    expect(screen.getByRole("button", { name: "Enviar" })).toBeTruthy();

    cable.empujar({
      kind: "turn.final",
      message_id: "background-caso-1-ab12",
      text: "La cláusula RC-04 de tu póliza trata ese daño.",
      language: "es",
      case_id: "caso-1",
      citations: [],
    });

    expect(screen.queryByTestId("chat-typing")).toBeNull();
  });

  it("un final sin la marca no muestra nada", () => {
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );

    cable.empujar({ ...ESPERA, answer_pending: false });

    expect(screen.queryByTestId("chat-typing")).toBeNull();
  });

  it("si el fondo falla, el error tambien quita el indicador", () => {
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.empujar(ESPERA);

    cable.empujar({ kind: "turn.error", code: "internal_error", copy_key: "chat.turn.error" });

    expect(screen.queryByTestId("chat-typing")).toBeNull();
  });

  it("pasado el tope sin respuesta, el indicador se quita en vez de girar para siempre", () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.empujar(ESPERA);
    expect(screen.getByTestId("chat-typing")).toBeTruthy();

    act(() => {
      vi.advanceTimersByTime(REVIEW_CEILING_MS - 1);
    });
    expect(screen.getByTestId("chat-typing")).toBeTruthy();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.queryByTestId("chat-typing")).toBeNull();
  });
});

describe("el borrador del cuadro de escribir (2026-10-12)", () => {
  it("lo escrito y no enviado vuelve al regresar a la pagina", async () => {
    // Visto: quien copiaba algo en el chat y salia de la pagina lo perdia.
    const cable = flujoDeMentira();
    const primera = renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    await userEvent.type(screen.getByLabelText("Tu mensaje"), "Mi póliza es la POL-100042");
    primera.unmount();

    const otraVez = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={otraVez.abrir} />,
    );

    expect(screen.getByLabelText<HTMLTextAreaElement>("Tu mensaje").value).toBe(
      "Mi póliza es la POL-100042",
    );
  });

  it("es de cada aseguradora", async () => {
    const cable = flujoDeMentira();
    const primera = renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    await userEvent.type(screen.getByLabelText("Tu mensaje"), "Para la primera");
    primera.unmount();

    const otra = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="otra-aseguradora" insurerLabel="Sunmeadow" openStream={otra.abrir} />,
    );

    expect(screen.getByLabelText<HTMLTextAreaElement>("Tu mensaje").value).toBe("");
  });

  it("al enviar se borra, y no vuelve", async () => {
    const cable = flujoDeMentira();
    const primera = renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    await userEvent.type(screen.getByLabelText("Tu mensaje"), "Me chocaron");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(enviado).toHaveBeenCalledTimes(1);
    primera.unmount();

    const otraVez = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={otraVez.abrir} />,
    );

    expect(screen.getByLabelText<HTMLTextAreaElement>("Tu mensaje").value).toBe("");
  });

  it("tocar una respuesta rapida no borra lo que se estaba escribiendo", async () => {
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    cable.empujar({
      kind: "turn.final",
      message_id: "m1",
      text: "¿Hubo alguien herido?",
      language: "es",
      case_id: "caso-1",
      citations: [],
      suggestions: ["Nadie salió herido"],
    });
    await userEvent.type(screen.getByLabelText("Tu mensaje"), "Estaba apuntando la placa");

    await userEvent.click(screen.getByRole("button", { name: "Nadie salió herido" }));

    expect(enviado).toHaveBeenCalledWith("una-aseguradora", "Nadie salió herido", {
      locale: "es",
    });
    expect(screen.getByLabelText<HTMLTextAreaElement>("Tu mensaje").value).toBe(
      "Estaba apuntando la placa",
    );
  });

  it("al empezar de cero se borra", async () => {
    const cable = flujoDeMentira();
    const primera = renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );
    await userEvent.type(screen.getByLabelText("Tu mensaje"), "Algo a medias");

    await userEvent.click(screen.getByTestId("chat-reset"));
    await userEvent.click(
      within(screen.getByTestId("chat-reset-confirm")).getByRole("button", {
        name: es("chat.page.reset_confirm"),
      }),
    );

    await vi.waitFor(() => {
      expect(screen.getByLabelText<HTMLTextAreaElement>("Tu mensaje").value).toBe("");
    });
    primera.unmount();
    const otraVez = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={otraVez.abrir} />,
    );
    expect(screen.getByLabelText<HTMLTextAreaElement>("Tu mensaje").value).toBe("");
  });

  it("sin almacenamiento el cuadro sigue funcionando", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("sin almacenamiento");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("sin almacenamiento");
    });
    const cable = flujoDeMentira();
    renderWithProviders(
      <ChatPage tenantId="una-aseguradora" insurerLabel="Stonecroft" openStream={cable.abrir} />,
    );

    await userEvent.type(screen.getByLabelText("Tu mensaje"), "Hola");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));

    expect(enviado).toHaveBeenCalledWith("una-aseguradora", "Hola", { locale: "es" });
    vi.restoreAllMocks();
  });
});
