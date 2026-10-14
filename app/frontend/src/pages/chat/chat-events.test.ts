import { describe, expect, it } from "vitest";

import {
  EMPTY,
  reduce,
  withHistory,
  withVisitorMessage,
  type StoredHistory,
  type WireCitation,
  type WireEvent,
} from "./chat-events";

// Lo que se comprueba aqui es la conducta de la conversacion, no su dibujo: que
// los fragmentos se junten en orden, que la espera desaparezca cuando llega la
// respuesta, y que los tres finales dejen la pantalla lista para escribir otra vez.

const CITA: WireCitation = {
  clause_id: "RC-04",
  clause_version: "2026.4",
  part: "Responsabilidad civil",
  text: "La compañía responde por los daños a terceros.",
  clause_language: "es",
  amount_deferred: false,
  trace_ref: "tr-1",
};

function final(overrides: Partial<Extract<WireEvent, { kind: "turn.final" }>> = {}): WireEvent {
  return {
    kind: "turn.final",
    message_id: "m1",
    text: "Su póliza lo cubre.",
    language: "es",
    case_id: "caso-1",
    citations: [],
    ...overrides,
  };
}

describe("la conversacion del chat", () => {
  it("junta los fragmentos de una respuesta larga en un solo mensaje", () => {
    const uno = reduce(EMPTY, {
      kind: "turn.partial",
      message_id: "m1",
      seq: 0,
      text: "La cláusula ",
    });
    const dos = reduce(uno, {
      kind: "turn.partial",
      message_id: "m1",
      seq: 1,
      text: "dice que sí.",
    });

    expect(dos.messages).toHaveLength(1);
    expect(dos.messages[0]?.text).toBe("La cláusula dice que sí.");
  });

  it("reemplaza la frase de espera por la respuesta en vez de dejar las dos", () => {
    const esperando = reduce(EMPTY, { kind: "turn.waiting", copy_key: "chat.turn.waiting" });
    expect(esperando.messages).toHaveLength(1);
    expect(esperando.messages[0]?.copyKey).toBe("chat.turn.waiting");
    expect(esperando.idle).toBe(false);

    const respondido = reduce(esperando, final());

    // Una sola: dejar la espera debajo de la respuesta escribiria "un momento"
    // para siempre bajo algo que ya llego.
    expect(respondido.messages).toHaveLength(1);
    expect(respondido.messages[0]?.text).toBe("Su póliza lo cubre.");
    expect(respondido.idle).toBe(true);
  });

  it("la respuesta final trae sus citas y la traza de su turno", () => {
    const estado = reduce(EMPTY, final({ citations: [CITA] }));

    expect(estado.messages[0]?.citations).toEqual([CITA]);
    expect(estado.messages[0]?.traceRef).toBe("tr-1");
    expect(estado.answeringIn).toBe("es");
  });

  it("una respuesta sin citas no inventa un enlace de traza", () => {
    // Un enlace a un resumen que no existe lleva a "no hay nada que mostrar", que
    // es la misma respuesta que recibe quien no es dueno: parece una fuga donde
    // no la hay.
    const estado = reduce(EMPTY, final());

    expect(estado.messages[0]?.traceRef).toBeNull();
  });

  it.each([
    [
      "derivacion",
      {
        kind: "turn.handoff",
        reason_code: "rule",
        copy_key: "compliance.handoff.rule",
        case_id: null,
        case_link: null,
      },
    ],
    ["error", { kind: "turn.error", code: "provider_unavailable", copy_key: "chat.turn.error" }],
  ] as const)("el %s cierra el turno y deja escribir otra vez", (_nombre, evento) => {
    const estado = reduce(
      reduce(EMPTY, { kind: "turn.waiting", copy_key: "chat.turn.waiting" }),
      evento,
    );

    expect(estado.idle).toBe(true);
    expect(estado.messages).toHaveLength(1);
    expect(estado.messages[0]?.copyKey).toBe(evento.copy_key);
  });

  it("el mensaje del visitante entra antes de que llegue nada", () => {
    const estado = withVisitorMessage(EMPTY, "v1", "Me chocaron");

    expect(estado.messages[0]).toMatchObject({ speaker: "visitor", text: "Me chocaron" });
    expect(estado.idle).toBe(false);
  });
});

describe("la frase de un evento que viaja con su clave y su texto (2026-10-12)", () => {
  // El servidor estreno una derivacion que la tabla de la pantalla no tenia y quien pidio
  // un ajustador leyo "tuve un problema para responder eso" con el caso ya derivado.

  const DERIVACION = {
    kind: "turn.handoff",
    reason_code: "human_request",
    case_id: "caso-1",
    case_link: null,
  } as const;

  it("una clave que la pantalla no conoce se dice con el texto que trajo el evento", () => {
    const estado = reduce(EMPTY, {
      ...DERIVACION,
      copy_key: "compliance.handoff.una_clave_nueva",
      text: "Listo: un ajustador revisa tu caso.",
    });

    expect(estado.messages[0]).toMatchObject({
      text: "Listo: un ajustador revisa tu caso.",
      copyKey: null,
    });
    expect(estado.idle).toBe(true);
  });

  it("una clave conocida se dice con el catalogo de la pantalla y no con el texto del servidor", () => {
    // Una frase no se dice de dos maneras: el catalogo de este lado es el que manda
    // mientras conozca la clave.
    const estado = reduce(EMPTY, {
      ...DERIVACION,
      copy_key: "compliance.handoff.adjuster_review_inquiry",
      text: "Otra redaccion distinta.",
    });

    expect(estado.messages[0]).toMatchObject({
      text: null,
      copyKey: "compliance.handoff.adjuster_review_inquiry",
    });
  });

  it("sin texto, una clave desconocida sigue cayendo en la frase de error y no en un hueco", () => {
    const estado = reduce(EMPTY, {
      kind: "turn.error",
      code: "internal_error",
      copy_key: "chat.una_clave_nueva",
    });

    expect(estado.messages[0]).toMatchObject({ text: null, copyKey: "chat.una_clave_nueva" });
  });

  it.each([
    ["la espera", { kind: "turn.waiting", copy_key: "chat.una_clave_nueva", text: "Un momento." }],
    [
      "el error",
      { kind: "turn.error", code: "x", copy_key: "chat.una_clave_nueva", text: "Un momento." },
    ],
  ] as const)(
    "%s tambien usa el texto del servidor cuando no conoce la clave",
    (_nombre, evento) => {
      const estado = reduce(EMPTY, evento);

      expect(estado.messages[0]?.text).toBe("Un momento.");
    },
  );
});

describe("la respuesta que el fondo todavia tiene que traer (2026-10-12)", () => {
  const PENDIENTE = final({ text: "Déjame revisar tu póliza.", answer_pending: true });

  it("un final que anuncia la respuesta deja la conversacion revisando, y ya lista para escribir", () => {
    const estado = reduce(EMPTY, PENDIENTE);

    expect(estado.reviewing).toBe(true);
    expect(estado.idle).toBe(true);
  });

  it("un final sin la marca no deja nada pendiente", () => {
    expect(reduce(EMPTY, final()).reviewing).toBe(false);
  });

  it.each([
    ["la respuesta", final({ message_id: "background-1", text: "La cláusula RC-04 lo cubre." })],
    ["un error", { kind: "turn.error", code: "x", copy_key: "chat.turn.error" }],
    [
      "una derivacion",
      {
        kind: "turn.handoff",
        reason_code: "rule",
        copy_key: "compliance.handoff.adjuster_review",
        case_id: null,
        case_link: null,
      },
    ],
  ] as const)("%s deja de revisar", (_nombre, evento) => {
    const revisando = reduce(EMPTY, PENDIENTE);

    expect(reduce(revisando, evento).reviewing).toBe(false);
  });

  it("un fragmento no cambia lo pendiente", () => {
    const revisando = reduce(EMPTY, PENDIENTE);

    const estado = reduce(revisando, { kind: "turn.partial", message_id: "m2", seq: 0, text: "x" });

    expect(estado.reviewing).toBe(true);
  });
});

describe("la conversacion recuperada del servidor", () => {
  const GUARDADO: StoredHistory = {
    opening: { message_id: "opening-chat-1", text: "Hola, soy Catalina.", language: "es" },
    turns: [
      { turn_id: "turn-1", speaker: "visitor", text: "Mi póliza es [PÓLIZA 1]", language: "es" },
      { turn_id: "turn-2", speaker: "agent", text: "Anotado. ¿Hay heridos?", language: "en" },
    ],
  };

  it("pone lo guardado delante, en su orden, sin tocar el idioma de la respuesta en curso", () => {
    const estado = withHistory(EMPTY, GUARDADO);

    expect(estado.messages.map((mensaje) => mensaje.id)).toEqual([
      "opening-chat-1",
      "turn-1",
      "turn-2",
    ]);
    expect(estado.messages[1]?.speaker).toBe("visitor");
    // Tal como se guardo: redactado. Aqui no se destapa nada.
    expect(estado.messages[1]?.text).toBe("Mi póliza es [PÓLIZA 1]");
    // Lo recuperado es pasado: "respondiendo en" habla de la respuesta de ahora.
    expect(estado.answeringIn).toBeNull();
    expect(estado.idle).toBe(true);
  });

  it("conserva detras lo que ya habia llegado por el flujo, sin repetir la apertura", () => {
    // La apertura puede llegar por las dos puertas con el mismo identificador; y un
    // aviso que llego mientras el historial venia de camino no se pierde.
    const previa = reduce(
      reduce(EMPTY, final({ message_id: "opening-chat-1", text: "Hola, soy Catalina." })),
      final({ message_id: "background-caso-1", text: "Un ajustador revisó su caso." }),
    );

    const estado = withHistory(previa, GUARDADO);

    expect(estado.messages.map((mensaje) => mensaje.id)).toEqual([
      "opening-chat-1",
      "turn-1",
      "turn-2",
      "background-caso-1",
    ]);
  });

  it("lo que dijo la agente vuelve como se leyo, no con las etiquetas de la base", () => {
    // 2026-10-09: "Abajo te dejo el texto exacto" volvia como "[LUGAR 1] te dejo...".
    const tapado: StoredHistory = {
      opening: null,
      turns: [
        {
          turn_id: "turn-9",
          speaker: "agent",
          text: "En tu póliza esto lo trata la Parte D. [LUGAR 1] te dejo el texto exacto.",
          language: "es",
        },
      ],
    };

    const estado = withHistory(
      EMPTY,
      tapado,
      [],
      [
        "Otra respuesta cualquiera.",
        "En tu póliza esto lo trata la Parte D. Abajo te dejo el texto exacto.",
      ],
    );

    expect(estado.messages[0]?.text).toBe(
      "En tu póliza esto lo trata la Parte D. Abajo te dejo el texto exacto.",
    );
  });

  it("sin apertura ni turnos deja la conversacion como estaba", () => {
    const estado = withHistory(EMPTY, { opening: null, turns: [] });

    expect(estado).toEqual(EMPTY);
  });
});
