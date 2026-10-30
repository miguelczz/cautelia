// El reductor del flujo de cuadros, probado sin navegador y sin socket.
//
// Cada cuadro del protocolo tiene su prueba, incluido el que no cambia nada
// visible. Lo que se comprueba no es que el reductor "funcione" sino las cuatro
// reglas que sostiene: un parcial se sustituye y no se acumula, la interrupcion
// marca la linea **de la agente**, el final fija su motivo, y un cuadro que no se
// conoce se descarta sin romper la pantalla.

import { describe, expect, it } from "vitest";

import { EMPTY, parseFrame, reduce, type Call, type WireFrame } from "./voice-events";

function tras(...cuadros: readonly WireFrame[]): Call {
  return cuadros.reduce(reduce, EMPTY);
}

describe("los estados de la llamada", () => {
  it("empieza conectando y pasa a lo que diga el servidor", () => {
    expect(EMPTY.state).toBe("connecting");
    expect(tras({ type: "state", value: "listening" }).state).toBe("listening");
  });

  it("el final fija el estado sin esperar otro cuadro", () => {
    // El servidor cierra el socket justo despues: una consola que siguiera
    // diciendo "escuchando" sobre una llamada terminada estaria mintiendo.
    const llamada = tras(
      { type: "state", value: "listening" },
      { type: "ended", reason: "hangup" },
    );

    expect(llamada.state).toBe("ended");
    expect(llamada.endedBy).toBe("hangup");
  });

  it("el final se lleva por delante el parcial a medias", () => {
    const llamada = tras(
      { type: "transcript", speaker: "insured", text: "mi placa es", final: false },
      { type: "ended", reason: "dropped" },
    );

    expect(llamada.partial).toBeNull();
  });
});

describe("la transcripcion", () => {
  it("un final entra al historial y un parcial no", () => {
    const llamada = tras(
      { type: "transcript", speaker: "agent", text: "Hola, buenas.", final: true },
      { type: "transcript", speaker: "insured", text: "me chocaron", final: false },
    );

    expect(llamada.turns).toHaveLength(1);
    expect(llamada.turns[0]?.text).toBe("Hola, buenas.");
    expect(llamada.partial?.text).toBe("me chocaron");
  });

  it("el final de un parcial lo sustituye, no se suma", () => {
    // Un parcial que quedara en el historial dejaria la frase a medias escrita
    // encima de la frase entera, que es como se lee una conversacion duplicada.
    const llamada = tras(
      { type: "transcript", speaker: "insured", text: "me cho", final: false },
      { type: "transcript", speaker: "insured", text: "me chocaron por detras", final: true },
    );

    expect(llamada.partial).toBeNull();
    expect(llamada.turns.map((turno) => turno.text)).toEqual(["me chocaron por detras"]);
  });

  it("lo que la persona dice de corrido sale en una sola intervencion aunque haga pausas", () => {
    // Pedido de Miguel (2026-10-15): cada pausa corta abria otra linea con su nombre.
    const llamada = tras(
      { type: "transcript", speaker: "agent", text: "¿En qué te ayudo?", final: true },
      { type: "transcript", speaker: "insured", text: "Hola,", final: true },
      { type: "transcript", speaker: "insured", text: "quería saber", final: false },
      { type: "transcript", speaker: "insured", text: "quería saber si me cubren", final: true },
      { type: "transcript", speaker: "insured", text: "  ", final: true },
    );

    expect(llamada.turns.map((turno) => [turno.speaker, turno.text])).toEqual([
      ["agent", "¿En qué te ayudo?"],
      ["insured", "Hola, quería saber si me cubren"],
    ]);
    expect(llamada.partial).toBeNull();
  });

  it("si la agente habla en medio, lo siguiente de la persona es otra intervencion", () => {
    const llamada = tras(
      { type: "transcript", speaker: "insured", text: "Me chocaron.", final: true },
      { type: "transcript", speaker: "agent", text: "¿Hay heridos?", final: true },
      { type: "transcript", speaker: "insured", text: "No.", final: true },
    );

    expect(llamada.turns.map((turno) => turno.text)).toEqual([
      "Me chocaron.",
      "¿Hay heridos?",
      "No.",
    ]);
  });

  it("las lineas seguidas de la agente no se juntan: son frases distintas", () => {
    const llamada = tras(
      { type: "transcript", speaker: "agent", text: "Tu póliza cubre la grúa.", final: true },
      { type: "transcript", speaker: "agent", text: "Volviendo al reporte...", final: true },
    );

    expect(llamada.turns).toHaveLength(2);
  });

  it("cada turno lleva identificador propio y ninguno se repite", () => {
    const llamada = tras(
      { type: "transcript", speaker: "agent", text: "uno", final: true },
      { type: "transcript", speaker: "insured", text: "dos", final: true },
      { type: "transcript", speaker: "agent", text: "tres", final: true },
    );

    expect(new Set(llamada.turns.map((turno) => turno.id)).size).toBe(3);
  });
});

describe("la interrupcion", () => {
  it("marca la linea de la agente y no la ultima a secas", () => {
    // Cuando la interrupcion llega, lo que la persona dijo para interrumpir ya
    // puede estar pintado delante. Marcar la ultima sin mas pondria la marca en
    // la linea de quien interrumpio, que es exactamente al reves.
    const llamada = tras(
      { type: "transcript", speaker: "agent", text: "Entonces la placa...", final: true },
      { type: "transcript", speaker: "insured", text: "espere, me equivoque", final: true },
      { type: "stop_audio" },
    );

    expect(llamada.turns[0]?.interrupted).toBe(true);
    expect(llamada.turns[1]?.interrupted).toBe(false);
  });

  it("sin nada dicho todavia no rompe nada", () => {
    expect(tras({ type: "stop_audio" }).turns).toEqual([]);
  });
});

describe("el caso y los avisos", () => {
  it("el numero de caso se guarda para mostrarlo", () => {
    const llamada = tras({ type: "case", case_id: "case-1", case_number: "AP-123456" });

    expect(llamada.caseNumber).toBe("AP-123456");
  });

  it("el aviso llega como clave y **no** como texto", () => {
    const llamada = tras({ type: "notice", copy_key: "voice.notice.time_running_out" });

    expect(llamada.notice).toBe("voice.notice.time_running_out");
  });
});

describe("lo que llega por el cable", () => {
  it("un cuadro conocido se tipa", () => {
    expect(parseFrame('{"type":"state","value":"listening"}')).toEqual({
      type: "state",
      value: "listening",
    });
  });

  it("un cuadro que este protocolo no conoce se descarta sin romper la pantalla", () => {
    // Del lado del servidor la union cerrada obliga a cubrir todas las ramas; de
    // este lado lo que hay es un navegador que puede ir una version por detras.
    // Lo que no se hace es adivinar que significaba.
    expect(parseFrame('{"type":"sing"}')).toBeNull();
  });

  it("algo que no es JSON tampoco", () => {
    expect(parseFrame("no soy json")).toBeNull();
    expect(parseFrame("null")).toBeNull();
  });
});

describe("la latencia del ultimo turno (U17, BR3.3)", () => {
  it("se guarda tal como el servidor la midio", () => {
    // **No se calcula de este lado.** La cifra es la misma que quedo en la traza
    // de ese turno, y medirla aqui daria dos numeros con el mismo nombre que un
    // dia no coinciden.
    const estado = tras({ type: "latency", turn_id: "t-1", elapsed_ms: 640 });

    expect(estado.lastLatencyMs).toBe(640);
  });

  it("la del turno siguiente reemplaza a la anterior", () => {
    const estado = tras(
      { type: "latency", turn_id: "t-1", elapsed_ms: 640 },
      { type: "latency", turn_id: "t-2", elapsed_ms: 910 },
    );

    expect(estado.lastLatencyMs).toBe(910);
  });

  it("con la medida desde la ultima palabra, es esa la que se muestra", () => {
    // La que la persona vive: el reconocedor y la tolerancia de fin de habla pasan antes
    // de que llegue el final. Una sola cifra en pantalla.
    const estado = tras({
      type: "latency",
      turn_id: "t-1",
      elapsed_ms: 640,
      from_last_word_ms: 1490,
    });

    expect(estado.lastLatencyMs).toBe(1490);
  });

  it("sin ella, o nula, se queda la de siempre", () => {
    expect(
      tras({ type: "latency", turn_id: "t-1", elapsed_ms: 640, from_last_word_ms: null })
        .lastLatencyMs,
    ).toBe(640);
    expect(tras({ type: "latency", turn_id: "t-1", elapsed_ms: 640 }).lastLatencyMs).toBe(640);
  });

  it("un cero desde la ultima palabra es una cifra, no una ausencia", () => {
    expect(
      tras({ type: "latency", turn_id: "t-1", elapsed_ms: 640, from_last_word_ms: 0 })
        .lastLatencyMs,
    ).toBe(0);
  });

  it("un cuadro de latencia se reconoce al leerlo del socket", () => {
    // Si el protocolo lo manda y este lado no lo conoce, se descarta en silencio:
    // la consola se queda sin la cifra que quien evalua va a comprobar.
    expect(parseFrame('{"type":"latency","turn_id":"t-1","elapsed_ms":640}')).toEqual({
      type: "latency",
      turn_id: "t-1",
      elapsed_ms: 640,
    });
  });
});
