// El puerto de la comparación, ya cableado (U23, tanda 2).
//
// Dos cosas se comprueban aquí y ninguna se ve desde la pantalla: que las tres
// respuestas del servidor se traduzcan a lo que cada columna muestra **sin
// colapsar ninguna distinción**, y que el flujo se abra antes de mandar el
// mensaje, que es lo que hace que la respuesta tenga dónde llegar.
//
// El invariante de la tanda 1 sigue aquí: la revisión local encontró que el puerto
// podía devolver el nombre de la propia agencia como su emisor --"la póliza de
// Knotwell la emitió Knotwell", que es falso-- y ninguna prueba se caía.

import { beforeEach, describe, expect, it, vi } from "vitest";

import type { TenantPresentation } from "../../shared/api-client/site";
import type { WireCitation } from "../chat/chat-events";

vi.mock("../../shared/api-client/chat", () => ({
  openChatStream: vi.fn(),
  sendMessage: vi.fn(),
}));

const { openChatStream, sendMessage } = await import("../../shared/api-client/chat");
const { askInsurer, exampleIssuerName, forgetFirstOpening, PLAZO_DE_RESPUESTA_MS } =
  await import("./comparison-port");

const KNOTWELL: TenantPresentation = {
  tenant_id: "una-agencia",
  display_name: "Una Agencia",
  kind: "agency",
  default_language: "en",
  example_policy: "POL-31",
  agent_name: "Catalina",
};

const CITA: WireCitation = {
  clause_id: "PAP-2026-A-1",
  clause_version: "2026.1",
  part: "a",
  text: "Pagamos el carro de alquiler mientras el suyo está en reparación.",
  clause_language: "es",
  amount_deferred: false,
  trace_ref: "tr-1",
};

/** Un `EventSource` de mentira: lo justo para emitir y cerrarse. */
function flujoDeMentira() {
  const flujo = {
    onmessage: null as ((evento: MessageEvent<string>) => void) | null,
    onerror: null as (() => void) | null,
    onopen: null as (() => void) | null,
    // Abierto desde el principio, salvo en la prueba que mira justo la apertura.
    readyState: 1,
    cerrado: false,
    close() {
      this.cerrado = true;
    },
  };
  return {
    flujo,
    emitir(cable: unknown) {
      flujo.onmessage?.({ data: JSON.stringify(cable) } as MessageEvent<string>);
    },
    caerse() {
      flujo.onerror?.();
    },
    abrir() {
      flujo.readyState = 1;
      flujo.onopen?.();
    },
  };
}

/** El orden de las llamadas, que es la mitad de lo que esta costura promete. */
let orden: string[] = [];

function montar(): ReturnType<typeof flujoDeMentira> {
  const doble = flujoDeMentira();
  vi.mocked(openChatStream).mockImplementation((): EventSource => {
    orden.push("flujo");
    return doble.flujo as unknown as EventSource;
  });
  return doble;
}

function respondeEnvio(resultado: Awaited<ReturnType<typeof sendMessage>>): void {
  vi.mocked(sendMessage).mockImplementation(async () => {
    orden.push("envio");
    return Promise.resolve(resultado);
  });
}

beforeEach(() => {
  orden = [];
  vi.clearAllMocks();
  forgetFirstOpening();
});

describe("preguntarle a una aseguradora (U23, tanda 2)", () => {
  it("abre el flujo antes de mandar el mensaje, y lo cierra al terminar", async () => {
    const doble = montar();
    respondeEnvio({ outcome: "accepted", accepted: { session_id: "chat-1", language: "es" } });

    const pregunta = askInsurer("una-aseguradora", "¿cubre el carro de alquiler?", {
      locale: "es",
    });
    doble.emitir({
      kind: "turn.final",
      message_id: "m1",
      text: "Sí, con límite.",
      language: "es",
      case_id: "c1",
      citations: [CITA],
      coverage_outcome: "verified",
    });
    await pregunta;

    // Al revés, el servidor admite el mensaje y no lo entrega: no hay cola donde
    // publicar la respuesta, y la columna se quedaría cargando para siempre.
    expect(orden).toEqual(["flujo", "envio"]);
    expect(doble.flujo.cerrado).toBe(true);
  });

  it("manda la superficie de la comparacion y el idioma de la pantalla", async () => {
    const doble = montar();
    respondeEnvio({ outcome: "accepted", accepted: { session_id: "chat-1", language: "en" } });

    const pregunta = askInsurer("una-aseguradora", "does it cover hail?", { locale: "en" });
    doble.emitir({
      kind: "turn.final",
      message_id: "m1",
      text: "Yes.",
      language: "en",
      case_id: "c1",
      citations: [CITA],
      coverage_outcome: "verified",
    });
    await pregunta;

    expect(vi.mocked(sendMessage).mock.calls[0]?.[2]).toEqual({
      surface: "comparison",
      locale: "en",
    });
  });

  it("una respuesta con citas es una respuesta citada", async () => {
    const doble = montar();
    respondeEnvio({ outcome: "accepted", accepted: { session_id: "chat-1", language: "es" } });

    const pregunta = askInsurer("una-aseguradora", "¿cubre granizo?", { locale: "es" });
    doble.emitir({
      kind: "turn.final",
      message_id: "m1",
      text: "Sí, con límite.",
      language: "es",
      case_id: "c1",
      citations: [CITA],
      coverage_outcome: "verified",
    });

    await expect(pregunta).resolves.toEqual({
      kind: "answered",
      answer: { kind: "cited", language: "es", text: "Sí, con límite.", citations: [CITA] },
    });
  });

  it("una respuesta sin citas es `no_clause`, y nunca un fallo", async () => {
    // Es la distinción que el proyecto no colapsa en ningún sitio: "no encuentro
    // una cláusula que lo cubra" es un resultado **verificado**, y "no pude
    // verificar" es un fallo. Dibujarlos igual contaminaría una métrica publicada
    // con fallos de infraestructura.
    const doble = montar();
    respondeEnvio({ outcome: "accepted", accepted: { session_id: "chat-1", language: "es" } });

    const pregunta = askInsurer("una-aseguradora", "¿cubre granizo?", { locale: "es" });
    doble.emitir({
      kind: "turn.final",
      message_id: "m1",
      text: "No encuentro una cláusula que lo cubra.",
      language: "es",
      case_id: "c1",
      citations: [],
      coverage_outcome: "no_clause_found",
    });

    await expect(pregunta).resolves.toEqual({
      kind: "answered",
      answer: { kind: "no_clause", language: "es" },
    });
  });

  it("un error del turno es un fallo de esa columna", async () => {
    const doble = montar();
    respondeEnvio({ outcome: "accepted", accepted: { session_id: "chat-1", language: "es" } });

    const pregunta = askInsurer("una-aseguradora", "¿cubre granizo?", { locale: "es" });
    doble.emitir({ kind: "turn.error", code: "delivery_failed", copy_key: "chat.error.delivery" });

    await expect(pregunta).resolves.toEqual({ kind: "failed" });
  });

  it("si el flujo se cae, la columna falla en vez de quedarse cargando", async () => {
    const doble = montar();
    respondeEnvio({ outcome: "accepted", accepted: { session_id: "chat-1", language: "es" } });

    const pregunta = askInsurer("una-aseguradora", "¿cubre granizo?", { locale: "es" });
    doble.caerse();

    await expect(pregunta).resolves.toEqual({ kind: "failed" });
  });

  it("la espera no se cierra con una frase de espera", async () => {
    // `turn.waiting` no cierra el turno: cerrarlo ahí dejaría la columna mostrando
    // una espera como si fuera la respuesta.
    const doble = montar();
    respondeEnvio({ outcome: "accepted", accepted: { session_id: "chat-1", language: "es" } });

    const pregunta = askInsurer("una-aseguradora", "¿cubre granizo?", { locale: "es" });
    doble.emitir({ kind: "turn.waiting", copy_key: "chat.waiting.checking" });
    let resuelta = false;
    void pregunta.then(() => {
      resuelta = true;
    });
    await Promise.resolve();
    expect(resuelta).toBe(false);

    doble.emitir({
      kind: "turn.final",
      message_id: "m1",
      text: "Sí.",
      language: "es",
      case_id: "c1",
      citations: [CITA],
      coverage_outcome: "verified",
    });
    await expect(pregunta).resolves.toMatchObject({ kind: "answered" });
  });

  it("la frase de 'dejeme revisar su poliza' no cierra la columna (fase 1)", async () => {
    // La pregunta cierra su turno con esa frase, sin resultado de cobertura, y la
    // respuesta llega despues, sola. Cerrar la columna con la frase la mostraria
    // como si fuera la respuesta.
    const doble = montar();
    respondeEnvio({ outcome: "accepted", accepted: { session_id: "chat-1", language: "es" } });

    const pregunta = askInsurer("una-aseguradora", "¿cubre granizo?", { locale: "es" });
    doble.emitir({
      kind: "turn.final",
      message_id: "m1",
      text: "Déjeme revisar su póliza; le respondo en un momento.",
      language: "es",
      case_id: "c1",
      citations: [],
    });
    let resuelta = false;
    void pregunta.then(() => {
      resuelta = true;
    });
    await Promise.resolve();
    expect(resuelta).toBe(false);

    doble.emitir({
      kind: "turn.final",
      message_id: "background-c1-1",
      text: "No encuentro una cláusula que lo cubra.",
      language: "es",
      case_id: "c1",
      citations: [],
      coverage_outcome: "no_clause_found",
    });
    await expect(pregunta).resolves.toEqual({
      kind: "answered",
      answer: { kind: "no_clause", language: "es" },
    });
  });

  it("no pude verificar es un fallo de la columna, nunca 'no hay clausula'", async () => {
    const doble = montar();
    respondeEnvio({ outcome: "accepted", accepted: { session_id: "chat-1", language: "es" } });

    const pregunta = askInsurer("una-aseguradora", "¿cubre granizo?", { locale: "es" });
    doble.emitir({
      kind: "turn.final",
      message_id: "background-c1-1",
      text: "No puedo revisar su póliza en este momento.",
      language: "es",
      case_id: "c1",
      citations: [],
      coverage_outcome: "unverifiable",
    });

    await expect(pregunta).resolves.toEqual({ kind: "failed" });
  });

  it("un limite alcanzado dice cual fue y su frase, sin esperar el flujo", async () => {
    const doble = montar();
    respondeEnvio({
      outcome: "rejected",
      rejected: { limit: "site_day", copy_key: "chat.limit.site_day", retry_after: null },
    });

    await expect(
      askInsurer("una-aseguradora", "¿cubre granizo?", { locale: "es" }),
    ).resolves.toEqual({ kind: "rejected", limit: "site_day", copyKey: "chat.limit.site_day" });
    expect(doble.flujo.cerrado).toBe(true);
  });

  it("la demo estrechada vuelve como demo cerrada, no como fuera de proposito", async () => {
    // Los dos traen `copy_key` y ninguno trae `limit`, asi que sin el campo
    // propio del cuarto el puerto los confundiria y la vista diria "esa no es una
    // pregunta de cobertura" cuando lo que pasa es que la demo no acepta casos
    // nuevos (BR3.2 de U20).
    montar();
    respondeEnvio({
      outcome: "demo_closed",
      closed: { kind: "demo_closed", copy_key: "demo.reset.surfaces_closed" },
    });

    await expect(
      askInsurer("una-aseguradora", "¿cubre granizo?", { locale: "es" }),
    ).resolves.toEqual({
      kind: "demo_closed",
      copyKey: "demo.reset.surfaces_closed",
    });
  });

  it("un texto que no es pregunta de cobertura vuelve como fuera de proposito", async () => {
    // Y no como un fallo: la póliza no se pudo revisar porque no se preguntó por una
    // cobertura, que es otra cosa y se dice distinto.
    montar();
    respondeEnvio({
      outcome: "out_of_scope",
      outOfScope: { copy_key: "comparison.out_of_scope.explanation" },
    });

    await expect(askInsurer("una-aseguradora", "choqué ayer", { locale: "es" })).resolves.toEqual({
      kind: "out_of_scope",
      copyKey: "comparison.out_of_scope.explanation",
    });
  });
});

describe("quien emitio la poliza de ejemplo (BR1.2)", () => {
  it("nunca devuelve el nombre de la propia agencia como su emisor", () => {
    // Una agencia no emite. Decir que emitió su propia póliza es afirmar algo
    // falso, y es el atajo que un cableado apurado tomaría.
    expect(exampleIssuerName(KNOTWELL)).not.toBe(KNOTWELL.display_name);
  });

  it("nombra a quien el contrato dice que emitio", () => {
    expect(exampleIssuerName({ ...KNOTWELL, example_policy_issuer: "Otra Aseguradora" })).toBe(
      "Otra Aseguradora",
    );
  });

  it("dice que no sabe quien emitio, en vez de adivinar", () => {
    // Si el directorio no lo trae, lo honesto es `null`: con él, la divulgación
    // queda incompleta y la vista no ofrece la pregunta.
    expect(exampleIssuerName(KNOTWELL)).toBeNull();
  });
});

describe("la apertura del flujo (2026-10-10)", () => {
  const ACEPTADO = {
    outcome: "accepted",
    accepted: { session_id: "chat-1", language: "es" },
  } as const;
  const RESPUESTA = {
    kind: "turn.final",
    message_id: "m1",
    text: "Sí, con límite.",
    language: "es",
    case_id: "c1",
    citations: [CITA],
    coverage_outcome: "verified",
  };

  it("no manda la pregunta hasta que el flujo abrio de verdad", async () => {
    // Crear el flujo no es que haya abierto: el mensaje llegaba primero al servidor,
    // se perdia, y la columna se quedaba en "Revisando" para siempre.
    const doble = montar();
    doble.flujo.readyState = 0;
    respondeEnvio(ACEPTADO);

    const pregunta = askInsurer("una-aseguradora", "¿me pagan la grúa?", { locale: "es" });
    await Promise.resolve();
    await Promise.resolve();
    expect(orden).toEqual(["flujo"]);

    doble.abrir();
    await vi.waitFor(() => {
      expect(orden).toEqual(["flujo", "envio"]);
    });
    doble.emitir(RESPUESTA);
    expect((await pregunta).kind).toBe("answered");
  });

  it("un flujo que se cae antes de abrir no manda nada y dice que no se pudo", async () => {
    const doble = montar();
    doble.flujo.readyState = 0;
    respondeEnvio(ACEPTADO);

    const pregunta = askInsurer("una-aseguradora", "¿me pagan la grúa?", { locale: "es" });
    doble.caerse();

    expect(await pregunta).toEqual({ kind: "failed" });
    expect(orden).toEqual(["flujo"]);
  });

  it("las demas columnas esperan a la primera apertura antes de abrir su flujo", async () => {
    // La primera apertura deja la galleta del visitante. Abriendo las tres a la vez
    // sin galleta, cada una recibia una distinta.
    const primero = flujoDeMentira();
    primero.flujo.readyState = 0;
    const segundo = flujoDeMentira();
    const dobles = [primero, segundo];
    vi.mocked(openChatStream).mockImplementation((): EventSource => {
      orden.push("flujo");
      const siguiente = dobles.shift();
      return (siguiente ?? segundo).flujo as unknown as EventSource;
    });
    respondeEnvio(ACEPTADO);

    const a = askInsurer("una", "¿me pagan la grúa?", { locale: "es" });
    const b = askInsurer("otra", "¿me pagan la grúa?", { locale: "es" });
    await Promise.resolve();
    await Promise.resolve();
    // Solo se abrio uno: el segundo espera.
    expect(orden).toEqual(["flujo"]);

    primero.abrir();
    await vi.waitFor(() => {
      expect(orden.filter((paso) => paso === "flujo")).toHaveLength(2);
    });
    primero.emitir(RESPUESTA);
    segundo.emitir(RESPUESTA);
    await Promise.all([a, b]);
  });

  it("si la respuesta nunca llega, la columna dice que no se pudo en vez de girar para siempre", async () => {
    vi.useFakeTimers();
    try {
      montar();
      respondeEnvio(ACEPTADO);

      const pregunta = askInsurer("una-aseguradora", "¿me pagan la grúa?", { locale: "es" });
      await vi.advanceTimersByTimeAsync(PLAZO_DE_RESPUESTA_MS);

      expect(await pregunta).toEqual({ kind: "failed" });
    } finally {
      vi.useRealTimers();
    }
  });
});
