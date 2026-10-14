import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../app/testing";
import { createTranslate } from "../../shared/i18n/translate";
import type { Availability, CallOutcome, OpenOutcome } from "../../shared/api-client/voice";
import type { WireFrame } from "./voice-events";
import { VoicePage } from "./voice-page";
import type { CallTransport, startCall } from "./voice-transport";

// La consola con el microfono y el socket de mentira. Lo que aqui se comprueba es
// lo que solo se ve por la pantalla: que negar el microfono **no abre ninguna
// llamada**, que todo lo que se oye tambien se lee, que la linea interrumpida se
// marca y que un final dice por que lo fue.

const disponibilidad = vi.hoisted(() =>
  vi.fn<(tenantId: string) => Promise<Availability | null>>(),
);
const abrir = vi.hoisted(() =>
  vi.fn<(tenantId: string, language: string) => Promise<OpenOutcome>>(),
);

const desenlace = vi.hoisted(() =>
  vi.fn<(tenantId: string, callId: string) => Promise<CallOutcome | null>>(),
);
const traspasar = vi.hoisted(() =>
  vi.fn<(tenantId: string, callId: string) => Promise<CallOutcome | null>>(),
);

vi.mock("../../shared/api-client/voice", async (original) => {
  const real = await original<typeof import("../../shared/api-client/voice")>();
  return {
    ...real,
    availability: disponibilidad,
    openCall: abrir,
    callOutcome: desenlace,
    handOffCase: traspasar,
  };
});

//: Las frases en espanol, para no escribirlas a mano en las aserciones.
const tEs = createTranslate("es");

const DISPONIBLE: Availability = {
  available: true,
  reason_code: null,
  reason_key: null,
  voice_mode: "primary",
  limits: {
    max_call_seconds: 180,
    warn_at_seconds: 30,
    resume_window_seconds: 900,
    calls_per_visitor_day: null,
    calls_per_site_day: null,
  },
  resume_until: null,
};

const ABIERTA: OpenOutcome = {
  outcome: "opened",
  call: {
    call_id: "call-1",
    case_id: "case-1",
    voice_mode: "primary",
    max_call_seconds: 180,
    transport: {
      kind: "websocket",
      url: "/api/voice/una-aseguradora/socket",
      token: "un-token-de-prueba",
      encoding: "pcm_s16le",
      sample_rate_hz: 24000,
      channels: 1,
      frame_ms: 20,
    },
  },
};

/** Un microfono que el navegador concede, con una pista que se puede parar. */
function microfonoConcedido(): MediaStream {
  const pista = { stop: vi.fn() };
  return { getTracks: () => [pista] } as unknown as MediaStream;
}

/** Un transporte de mentira: guarda los manejadores para empujarles cuadros. */
function transporteDeMentira() {
  const estado: {
    colgado: boolean;
    cerrado: boolean;
    terminado: boolean;
    /** Cuantas veces la persona toco "Activar el sonido". */
    reanudado: number;
    /** Lo que el contexto de audio hace al tocar: por omision, correr. */
    alReanudar: () => boolean;
    empujar: (cuadro: WireFrame) => void;
    nivel: (valor: number) => void;
    cortar: () => void;
    /** El contexto de audio queda detenido (`true`) o vuelve a correr (`false`). */
    bloquear: (bloqueado: boolean) => void;
  } = {
    colgado: false,
    cerrado: false,
    terminado: false,
    reanudado: 0,
    alReanudar: () => false,
    bloquear: () => {
      throw new Error("todavia no arranco");
    },
    empujar: () => {
      throw new Error("todavia no arranco");
    },
    nivel: () => {
      throw new Error("todavia no arranco");
    },
    cortar: () => {
      throw new Error("todavia no arranco");
    },
  };
  const start: typeof startCall = (opciones) => {
    estado.empujar = (cuadro) => {
      // Dentro de `act`: el cuadro llega de fuera de React, como en la pagina.
      act(() => {
        opciones.handlers.onFrame(cuadro);
      });
    };
    estado.cortar = () => {
      act(() => {
        opciones.handlers.onClosed();
      });
    };
    estado.nivel = (valor) => {
      act(() => {
        opciones.handlers.onLevel(valor);
      });
    };
    estado.bloquear = (bloqueado) => {
      act(() => {
        opciones.handlers.onAudioBlocked?.(bloqueado);
      });
    };
    return Promise.resolve({
      hangup: () => {
        estado.colgado = true;
      },
      close: () => {
        estado.cerrado = true;
      },
      // Lo que la pagina llama cuando el servidor termina: deja sonar la despedida.
      finish: () => {
        estado.terminado = true;
      },
      // El toque de "Activar el sonido": el contexto vuelve a correr, o no.
      resumeAudio: () => {
        estado.reanudado += 1;
        opciones.handlers.onAudioBlocked?.(estado.alReanudar());
        return Promise.resolve();
      },
    } as unknown as CallTransport);
  };
  return { estado, start };
}

function conMicrofono(stream: MediaStream | null): void {
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: {
      getUserMedia: () =>
        stream === null
          ? // Como niega el navegador: una DOMException con ese nombre (BR1.2).
            Promise.reject(new DOMException("Permission denied", "NotAllowedError"))
          : Promise.resolve(stream),
    },
  });
}

beforeEach(() => {
  disponibilidad.mockReset();
  disponibilidad.mockResolvedValue(DISPONIBLE);
  abrir.mockReset();
  abrir.mockResolvedValue(ABIERTA);
  desenlace.mockReset();
  desenlace.mockResolvedValue(null);
  traspasar.mockReset();
  traspasar.mockResolvedValue(null);
  conMicrofono(microfonoConcedido());
});

describe("el arranque de la llamada", () => {
  it("un microfono negado no abre ninguna llamada", async () => {
    // **BR1.2, y el orden es la regla.** Si la sesion se abriera primero, un
    // permiso negado dejaria un caso vacio en la bandeja de una ajustadora. Por
    // eso no basta con mirar que salga el aviso: hay que mirar que **no** se
    // llamo a abrir.
    conMicrofono(null);
    const cable = transporteDeMentira();
    renderWithProviders(
      <VoicePage
        tenantId="una-aseguradora"
        insurerLabel="Una Aseguradora"
        chatHref="/t/una-aseguradora/chat"
        start={cable.start}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));

    expect(abrir).not.toHaveBeenCalled();
    expect(screen.getByText(/no dio acceso al micrófono/)).toBeTruthy();
    // Y ofrece el chat, que es la otra mitad de BR1.2.
    expect(screen.getByRole("link", { name: /chat/ }).getAttribute("href")).toBe(
      "/t/una-aseguradora/chat",
    );
  });

  it("con el microfono concedido abre la sesion y el boton pasa a colgar", async () => {
    const cable = transporteDeMentira();
    renderWithProviders(
      <VoicePage
        tenantId="una-aseguradora"
        insurerLabel="Una Aseguradora"
        chatHref="/t/una-aseguradora/chat"
        start={cable.start}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));

    expect(abrir).toHaveBeenCalledWith("una-aseguradora", "es");
    expect(screen.getByRole("button", { name: "Colgar" })).toBeTruthy();
  });

  it("durante la llamada se ve el estado, lo que queda y el boton de colgar (BR3.2)", async () => {
    // Los tres juntos, porque la regla es que **los tres** esten a la vista: con
    // dos de ellos, quien tiene tres minutos y una sola llamada al dia tiene que
    // adivinar el tercero.
    const cable = transporteDeMentira();
    renderWithProviders(
      <VoicePage
        tenantId="una-aseguradora"
        insurerLabel="Una Aseguradora"
        chatHref="/t/una-aseguradora/chat"
        start={cable.start}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));

    // **Los tres dentro de la misma region**, que es la que esta pegada al borde de
    // abajo. Lo que jsdom no puede ver es la disposicion --que a 360 px siguen a la
    // vista con la transcripcion llena--, y eso lo comprueba el arnes en la
    // tubería; lo que si se puede fijar aqui es que ninguno de los tres se salga de
    // esa region, que es como dejarian de estar siempre visibles.
    const controles = screen.getByTestId("voice-controls");
    expect(within(controles).getByTestId("voice-state")).toBeTruthy();
    expect(within(controles).getByRole("button", { name: "Colgar" })).toBeTruthy();
    // La duracion maxima de la disponibilidad declarada son 180 s.
    expect(within(controles).getByTestId("voice-time-left").textContent).toContain("3:00");
  });

  it("seis segundos de llamada sin nivel avisan que el microfono no entra", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const cable = transporteDeMentira();
      renderWithProviders(
        <VoicePage
          tenantId="una-aseguradora"
          insurerLabel="Una Aseguradora"
          chatHref="/t/una-aseguradora/chat"
          start={cable.start}
        />,
      );
      await userEvent.click(screen.getByRole("button", { name: "Llamar" }));
      cable.estado.empujar({ type: "state", value: "listening" });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(6_500);
      });

      expect(screen.getByTestId("voice-no-audio").textContent).toBe(tEs("voice.console.no_audio"));
      // Se queda aunque la agente hable: el microfono sigue sin entrar. Se va en
      // cuanto llega sonido.
      cable.estado.empujar({ type: "state", value: "speaking" });
      expect(screen.getByTestId("voice-no-audio")).toBeTruthy();
      act(() => {
        cable.estado.nivel(0.2);
      });
      expect(screen.queryByTestId("voice-no-audio")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("avisa aunque la agente pregunte si sigues ahi antes de seis segundos", async () => {
    // 2026-10-09: con el permiso del microfono perdido, la agente preguntaba
    // "¿Sigues ahi?" antes de seis segundos, la escucha volvia a empezar y el aviso
    // no salia nunca. Ahora se cuenta desde que empieza la llamada.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const cable = transporteDeMentira();
      renderWithProviders(
        <VoicePage
          tenantId="una-aseguradora"
          insurerLabel="Una Aseguradora"
          chatHref="/t/una-aseguradora/chat"
          start={cable.start}
        />,
      );
      await userEvent.click(screen.getByRole("button", { name: "Llamar" }));
      cable.estado.empujar({ type: "state", value: "listening" });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(4_000);
      });
      cable.estado.empujar({ type: "state", value: "speaking" });
      cable.estado.empujar({ type: "state", value: "listening" });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2_500);
      });

      expect(screen.getByTestId("voice-no-audio")).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it("con nivel en el microfono no se avisa nada, aunque la persona haga pausas", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const cable = transporteDeMentira();
      renderWithProviders(
        <VoicePage
          tenantId="una-aseguradora"
          insurerLabel="Una Aseguradora"
          chatHref="/t/una-aseguradora/chat"
          start={cable.start}
        />,
      );
      await userEvent.click(screen.getByRole("button", { name: "Llamar" }));
      cable.estado.empujar({ type: "state", value: "listening" });
      cable.estado.nivel(0.2);
      cable.estado.nivel(0);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(6_500);
      });

      expect(screen.queryByTestId("voice-no-audio")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("el ruido de fondo de un microfono vivo, sin hablar, no dispara el aviso", async () => {
    // Medido el 2026-10-07: un microfono que funciona, en un cuarto callado, da un
    // maximo de 0,0013 en seis segundos. El umbral anterior lo leia como un
    // microfono muerto y el aviso salia antes de que la persona dijera nada.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const cable = transporteDeMentira();
      renderWithProviders(
        <VoicePage
          tenantId="una-aseguradora"
          insurerLabel="Una Aseguradora"
          chatHref="/t/una-aseguradora/chat"
          start={cable.start}
        />,
      );
      await userEvent.click(screen.getByRole("button", { name: "Llamar" }));
      cable.estado.empujar({ type: "state", value: "listening" });
      cable.estado.nivel(0.0013);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(6_500);
      });

      expect(screen.queryByTestId("voice-no-audio")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("lo que queda baja con el reloj y desaparece al terminar", async () => {
    // El cronometro es del navegador y no pretende medir nada: el servidor corta
    // la llamada por su cuenta. Lo que esta prueba fija es que la cuenta avanza y
    // que no sigue corriendo sobre una llamada acabada, que diria algo que ya no
    // pasa.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const cable = transporteDeMentira();
      renderWithProviders(
        <VoicePage
          tenantId="una-aseguradora"
          insurerLabel="Una Aseguradora"
          chatHref="/t/una-aseguradora/chat"
          start={cable.start}
        />,
      );

      await userEvent.click(screen.getByRole("button", { name: "Llamar" }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(11_000);
      });
      expect(screen.getByTestId("voice-time-left").textContent).toContain("2:49");

      cable.estado.empujar({ type: "ended", reason: "hangup" });

      expect(screen.queryByTestId("voice-time-left")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("sin voz no se ofrece el boton activo, y se dice por que", async () => {
    // BR1.1: ofrecer un boton que va a fallar es peor que no ofrecerlo. La frase
    // sale de la clave que manda el servidor, nunca de un texto escrito aqui.
    disponibilidad.mockResolvedValue({
      ...DISPONIBLE,
      available: false,
      reason_code: "budget_exhausted",
      reason_key: "spend.quota.budget_exhausted",
    });
    const cable = transporteDeMentira();
    renderWithProviders(
      <VoicePage
        tenantId="una-aseguradora"
        insurerLabel="Una Aseguradora"
        chatHref="/t/una-aseguradora/chat"
        start={cable.start}
      />,
    );

    // El motivo dice todo: "la voz esta apagada" ante un tope de gasto era decir algo
    // distinto de lo que paso (V15, 2026-10-11).
    expect(await screen.findByText(/presupuesto/)).toBeTruthy();
    expect(screen.queryByText("La voz está apagada ahora mismo")).toBeNull();
    expect(screen.getByRole("button", { name: "Llamar" })).toHaveProperty("disabled", true);
  });
});

describe("lo que se oye tambien se lee", () => {
  async function enLlamada() {
    const cable = transporteDeMentira();
    renderWithProviders(
      <VoicePage
        tenantId="una-aseguradora"
        insurerLabel="Una Aseguradora"
        chatHref="/t/una-aseguradora/chat"
        start={cable.start}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));
    return cable;
  }

  it("la transcripcion en vivo trae lo que dijeron los dos", async () => {
    const cable = await enLlamada();

    cable.estado.empujar({
      type: "transcript",
      speaker: "agent",
      text: "Para empezar, ¿hubo alguien herido?",
      final: true,
    });
    cable.estado.empujar({
      type: "transcript",
      speaker: "insured",
      text: "sí, todos bien",
      final: true,
    });

    const lista = screen.getByTestId("voice-transcript");
    expect(lista.textContent).toContain("Para empezar, ¿hubo alguien herido?");
    expect(lista.textContent).toContain("sí, todos bien");
  });

  it("lo que se dice en la llamada queda en este navegador, para leerlo sin tapar en 'Ver mi caso' (C5)", async () => {
    const cable = await enLlamada();

    cable.estado.empujar({ type: "transcript", speaker: "agent", text: "Hola.", final: true });
    cable.estado.empujar({
      type: "transcript",
      speaker: "insured",
      text: "Soy Natalia Henao, mi póliza es POL-100042",
      final: true,
    });
    // Un parcial no se guarda: se sustituye por su final.
    cable.estado.empujar({ type: "transcript", speaker: "insured", text: "me cho", final: false });

    expect(
      JSON.parse(window.localStorage.getItem("cautelia.own-text.una-aseguradora") ?? "[]"),
    ).toEqual(["Soy Natalia Henao, mi póliza es POL-100042"]);
    expect(
      JSON.parse(window.localStorage.getItem("cautelia.agent-text.una-aseguradora") ?? "[]"),
    ).toEqual(["Hola."]);
  });

  it("un parcial se pinta aparte y no entra en la lista", async () => {
    const cable = await enLlamada();

    cable.estado.empujar({
      type: "transcript",
      speaker: "insured",
      text: "me choca",
      final: false,
    });

    expect(screen.getByTestId("voice-partial").textContent).toContain("me choca");
    expect(screen.getByTestId("voice-transcript").textContent).not.toContain("me choca");
  });

  it("la linea interrumpida se marca", async () => {
    // Verlo importa: sin marca, quien prueba la demostracion no distingue "la
    // interrumpi" de "se cayo el audio".
    const cable = await enLlamada();

    cable.estado.empujar({
      type: "transcript",
      speaker: "agent",
      text: "Entonces la placa es...",
      final: true,
    });
    cable.estado.empujar({ type: "stop_audio" });

    expect(screen.getByTestId("voice-transcript").textContent).toContain("interrumpida");
  });

  it("el final dice por que lo fue", async () => {
    // Una llamada que se corta sin decir por que es la peor pantalla posible.
    const cable = await enLlamada();

    cable.estado.empujar({ type: "ended", reason: "dropped" });

    expect(screen.getByText(/se cortó/)).toBeTruthy();
    expect(screen.getByTestId("voice-state").textContent).toBe("Llamada terminada");
  });

  it("cuando el servidor termina la llamada, deja sonar la despedida en vez de cerrar el audio", async () => {
    // La despedida lleva el numero de caso y todavia suena cuando llega el aviso de
    // fin: cerrar el audio ahi la cortaba (2026-10-10).
    const cable = await enLlamada();

    cable.estado.empujar({ type: "ended", reason: "completed" });

    expect(cable.estado.terminado).toBe(true);
    expect(cable.estado.cerrado).toBe(false);
  });

  it("colgar no muestra aviso de final: lo hizo la persona", async () => {
    const cable = await enLlamada();

    cable.estado.empujar({ type: "ended", reason: "hangup" });

    expect(screen.getByTestId("voice-state").textContent).toBe("Llamada terminada");
    expect(screen.queryByText(/Colgaste/)).toBeNull();
    expect(screen.queryByText(/queda guardado/)).toBeNull();
  });

  it("antes de llamar la pantalla va centrada, y con la llamada se parte en dos columnas, tambien al terminar", async () => {
    const cable = transporteDeMentira();
    const { container } = renderWithProviders(
      <VoicePage
        tenantId="una-aseguradora"
        insurerLabel="Una Aseguradora"
        chatHref="/t/una-aseguradora/chat"
        start={cable.start}
      />,
    );
    const marco = () => container.querySelector("[data-voice-layout]");

    expect(marco()?.getAttribute("data-voice-layout")).toBe("centered");
    await userEvent.click(await screen.findByRole("button", { name: "Llamar" }));
    expect(marco()?.getAttribute("data-voice-layout")).toBe("split");
    // La llamada a un lado y la transcripcion en su propia columna.
    expect(
      screen.getByTestId("voice-call-column").contains(screen.getByTestId("voice-controls")),
    ).toBe(true);
    expect(
      screen
        .getByTestId("voice-transcript-column")
        .contains(screen.getByTestId("voice-transcript")),
    ).toBe(true);

    cable.estado.empujar({ type: "ended", reason: "hangup" });
    expect(marco()?.getAttribute("data-voice-layout")).toBe("split");
  });

  it("la latencia del ultimo turno se lee en la consola (BR3.3)", async () => {
    // La cifra viene del servidor y la consola solo la dice: es la misma que quedo
    // en la traza de ese turno, y es la que quien evalua va a comprobar.
    const cable = transporteDeMentira();
    renderWithProviders(
      <VoicePage
        tenantId="una-aseguradora"
        insurerLabel="Una Aseguradora"
        chatHref="/t/una-aseguradora/chat"
        start={cable.start}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));

    cable.estado.empujar({ type: "latency", turn_id: "t-1", elapsed_ms: 640 });

    expect(screen.getByTestId("voice-latency").textContent).toContain("640");
  });

  it("la cifra de la pantalla es la contada desde la ultima palabra, cuando viene", async () => {
    const cable = await enLlamada();

    cable.estado.empujar({
      type: "latency",
      turn_id: "t-1",
      elapsed_ms: 640,
      from_last_word_ms: 1490,
    });

    const cifra = screen.getByTestId("voice-latency").textContent;
    expect(cifra).toContain("1490");
    expect(cifra).not.toContain("640");
  });

  it("el aviso del servidor se resuelve por su clave", async () => {
    const cable = await enLlamada();

    cable.estado.empujar({ type: "notice", copy_key: "voice.notice.time_running_out" });

    expect(screen.getByText(/límite de tiempo/)).toBeTruthy();
  });
});

describe("colgar", () => {
  it("manda el cuadro de colgar por el socket, no una peticion", async () => {
    // El cuadro es lo que deja al servidor cerrar el caso con el motivo correcto;
    // la ruta de cerrar es el camino de respaldo para cuando el socket ya no esta.
    const cable = transporteDeMentira();
    renderWithProviders(
      <VoicePage
        tenantId="una-aseguradora"
        insurerLabel="Una Aseguradora"
        chatHref="/t/una-aseguradora/chat"
        start={cable.start}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));

    await userEvent.click(screen.getByRole("button", { name: "Colgar" }));

    expect(cable.estado.colgado).toBe(true);
  });

  it("la pantalla sale de la llamada al pulsar, sin esperar al servidor", async () => {
    // Defecto del 2026-10-07 en produccion: tras colgar, el boton seguia diciendo
    // "Colgar" y no hacia nada, porque la pantalla esperaba un `ended` que el
    // socket cerrado ya no podia traer.
    const cable = transporteDeMentira();
    renderWithProviders(
      <VoicePage
        tenantId="una-aseguradora"
        insurerLabel="Una Aseguradora"
        chatHref="/t/una-aseguradora/chat"
        start={cable.start}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));
    cable.estado.empujar({ type: "state", value: "listening" });

    await userEvent.click(screen.getByRole("button", { name: "Colgar" }));

    expect(screen.queryByRole("button", { name: "Colgar" })).toBeNull();

    // Lo que el servidor tenia en curso sigue llegando y no revive la llamada.
    cable.estado.empujar({ type: "state", value: "speaking" });
    expect(screen.queryByRole("button", { name: "Colgar" })).toBeNull();
  });

  it("un socket que se cierra sin aviso tambien saca a la pantalla de la llamada", async () => {
    const cable = transporteDeMentira();
    renderWithProviders(
      <VoicePage
        tenantId="una-aseguradora"
        insurerLabel="Una Aseguradora"
        chatHref="/t/una-aseguradora/chat"
        start={cable.start}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));
    cable.estado.empujar({ type: "state", value: "listening" });
    expect(screen.queryByRole("button", { name: "Colgar" })).not.toBeNull();

    cable.estado.cortar();

    expect(screen.queryByRole("button", { name: "Colgar" })).toBeNull();
  });
});

// --- U17: lo que se dice antes de pedir el microfono (BR3.1, BR1.4, BR2.3) -------

function renderizar(extra: { examplePolicy?: string; exampleHolder?: string } = {}) {
  const cable = transporteDeMentira();
  renderWithProviders(
    <VoicePage
      tenantId="una-aseguradora"
      insurerLabel="Una Aseguradora"
      chatHref="/t/una-aseguradora/chat"
      start={cable.start}
      {...extra}
    />,
  );
  return cable;
}

/** El microfono como espia: lo que se comprueba es que **no** se pidio. */
function microfonoEspiado() {
  const pedir = vi.fn(() => Promise.resolve(microfonoConcedido()));
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: pedir },
  });
  return pedir;
}

const CON_LIMITES: Availability = {
  ...DISPONIBLE,
  limits: { ...DISPONIBLE.limits, calls_per_visitor_day: 1, calls_per_site_day: 15 },
};

describe("antes de pedir el microfono", () => {
  it("mientras no se sabe si hay voz, el boton no hace nada y el microfono no se pide", async () => {
    // BR3.1 y PERF-U17.2: es un orden. La respuesta se retiene a proposito: con
    // una disponibilidad que tarda, pulsar no puede abrir el permiso.
    const pedir = microfonoEspiado();
    let responder: (valor: Availability | null) => void = () => undefined;
    disponibilidad.mockReturnValue(
      new Promise<Availability | null>((resolver) => {
        responder = resolver;
      }),
    );
    renderizar();

    const boton = screen.getByRole("button", { name: "Llamar" });
    expect(boton).toHaveProperty("disabled", true);
    await userEvent.click(boton);
    expect(pedir).not.toHaveBeenCalled();
    expect(abrir).not.toHaveBeenCalled();
    expect(screen.getByTestId("voice-state").textContent).toBe("Comprobando si hay voz");

    act(() => {
      responder(DISPONIBLE);
    });
    await userEvent.click(await screen.findByRole("button", { name: "Llamar" }));
    expect(pedir).toHaveBeenCalledTimes(1);
  });

  it("si la disponibilidad no llega, tampoco se pide el microfono, y se ofrece el chat", async () => {
    const pedir = microfonoEspiado();
    disponibilidad.mockResolvedValue(null);
    renderizar();

    expect(await screen.findByText("La voz está apagada ahora mismo")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));

    expect(pedir).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: /chat/ }).getAttribute("href")).toBe(
      "/t/una-aseguradora/chat",
    );
  });

  it("si la peticion de disponibilidad falla, acaba en el mismo sitio que una sin voz", async () => {
    // Un fallo de red es tambien "sin respuesta". Sin el `catch`, la conducta no
    // era insegura --el boton quedaba deshabilitado-- pero la consola se quedaba
    // en "comprobando" para siempre, sin motivo y sin la oferta del chat: peor
    // que una indisponibilidad declarada.
    const pedir = microfonoEspiado();
    disponibilidad.mockRejectedValue(new Error("la red es la red"));
    renderizar();

    expect(await screen.findByText("La voz está apagada ahora mismo")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));

    expect(pedir).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: /chat/ })).toBeTruthy();
  });

  it.each([
    [
      "rate_limited_daily",
      "voice.availability.rate_limited_daily",
      /Ya usaste tus llamadas de hoy desde esta conexión/,
    ],
    [
      "rate_limited_site",
      "voice.availability.rate_limited_site",
      /Hoy ya se hicieron todas las llamadas de la demostración/,
    ],
    // BR3.2 de U20: 24 horas sin un reinicio nocturno exitoso. La consola lo dice
    // con la frase de U20 y no con una de cuota: lo que falta no es cupo.
    ["demo_closed", "demo.reset.surfaces_closed", /no acepta casos nuevos por ahora/],
  ] as const)(
    "sin voz por %s dice el motivo, ofrece el chat y no pide el microfono",
    async (codigo, clave, frase) => {
      const pedir = microfonoEspiado();
      disponibilidad.mockResolvedValue({
        ...DISPONIBLE,
        available: false,
        reason_code: codigo,
        reason_key: clave,
      });
      renderizar();

      expect(await screen.findByText(frase)).toBeTruthy();
      // Ni "la voz esta apagada": el limite no es eso (V15).
      expect(screen.queryByText("La voz está apagada ahora mismo")).toBeNull();
      expect(screen.getByRole("link", { name: /chat/ })).toBeTruthy();
      expect(screen.getByRole("button", { name: "Llamar" })).toHaveProperty("disabled", true);
      expect(pedir).not.toHaveBeenCalled();
      expect(screen.queryByTestId("voice-before-call")).toBeNull();
    },
  );

  it("cada motivo de rechazo dice una cosa distinta", async () => {
    // V15: la consola decia lo mismo ante cualquiera. Con dos motivos que compartieran
    // frase, saber **cual** fue seria imposible.
    const dichas = new Set<string>();
    for (const [codigo, clave] of [
      ["rate_limited_daily", "voice.availability.rate_limited_daily"],
      ["rate_limited_site", "voice.availability.rate_limited_site"],
      ["budget_exhausted", "spend.quota.budget_exhausted"],
      ["demo_closed", "demo.reset.surfaces_closed"],
    ] as const) {
      disponibilidad.mockResolvedValue({
        ...DISPONIBLE,
        available: false,
        reason_code: codigo,
        reason_key: clave,
      });
      const { unmount } = renderWithProviders(
        <VoicePage
          tenantId="una-aseguradora"
          insurerLabel="Una Aseguradora"
          chatHref="/t/una-aseguradora/chat"
        />,
      );
      const alerta = (await screen.findByRole("link", { name: /chat/ })).closest("div");
      dichas.add(alerta?.textContent ?? "");
      unmount();
    }

    expect(dichas.size).toBe(4);
  });

  it.each([
    ["rate_limited_daily", /Ya usaste tus llamadas de hoy desde esta conexión/],
    ["rate_limited_site", /Hoy ya se hicieron todas las llamadas de la demostración/],
    ["budget_exhausted", /presupuesto/],
    ["demo_closed", /no acepta casos nuevos por ahora/],
  ] as const)(
    "si abrir la llamada se rechaza por %s, lo dice, suelta el microfono y deja el boton quieto",
    async (codigo, frase) => {
      // El rechazo llega en el 503 de abrir, no en la disponibilidad: el cupo se gasta
      // entre las dos peticiones. Antes toda negativa se leia "la voz esta apagada".
      const pista = { stop: vi.fn() };
      conMicrofono({ getTracks: () => [pista] } as unknown as MediaStream);
      abrir.mockResolvedValue({ outcome: "unavailable", code: codigo });
      renderizar();

      await userEvent.click(await screen.findByRole("button", { name: "Llamar" }));

      expect(await screen.findByText(frase)).toBeTruthy();
      expect(screen.queryByText("La voz está apagada ahora mismo")).toBeNull();
      expect(pista.stop).toHaveBeenCalled();
      expect(screen.getByRole("link", { name: /chat/ })).toBeTruthy();
      expect(screen.getByRole("button", { name: "Llamar" })).toHaveProperty("disabled", true);
      // Y los limites de antes del boton no se quedan al lado de un "no".
      expect(screen.queryByTestId("voice-before-call")).toBeNull();
    },
  );

  it.each(["provider_unavailable", null] as const)(
    "si abrir la llamada se rechaza sin un motivo que la pantalla sepa decir (%s), dice lo general",
    async (codigo) => {
      abrir.mockResolvedValue({ outcome: "unavailable", code: codigo });
      renderizar();

      await userEvent.click(await screen.findByRole("button", { name: "Llamar" }));

      expect(await screen.findByText("La voz está apagada ahora mismo")).toBeTruthy();
      expect(screen.getByRole("link", { name: /chat/ })).toBeTruthy();
    },
  );

  it("dice los dos limites antes del boton, y dice 'desde esta conexion'", async () => {
    // BR1.4: nunca "por persona". Un visitante cambia de navegador, asi que este
    // carril no controla el gasto y la pantalla no puede insinuar que si.
    const pedir = microfonoEspiado();
    disponibilidad.mockResolvedValue(CON_LIMITES);
    renderizar();

    const antes = await screen.findByTestId("voice-before-call");

    expect(antes.textContent).toContain("Duración máxima de cada llamada: 3 min.");
    expect(antes.textContent).toContain("Llamadas al día desde esta conexión: 1.");
    expect(antes.textContent).not.toMatch(/por persona/i);
    expect(pedir).not.toHaveBeenCalled();
    // Y va **antes** del boton en el orden del documento.
    const boton = screen.getByRole("button", { name: "Llamar" });
    expect(antes.compareDocumentPosition(boton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("con una duracion que no es de minutos enteros la dice en segundos", async () => {
    disponibilidad.mockResolvedValue({
      ...CON_LIMITES,
      limits: { ...CON_LIMITES.limits, max_call_seconds: 90 },
    });
    renderizar();

    expect((await screen.findByTestId("voice-before-call")).textContent).toContain(
      "Duración máxima de cada llamada: 90 s.",
    );
  });

  it("mientras el servidor no sirva el carril diario, no lo promete", async () => {
    // Un limite que nada aplica es la promesa que P7 prohibe: con el valor nulo la
    // linea no sale, y la de la duracion, que si se aplica, si.
    disponibilidad.mockResolvedValue(DISPONIBLE);
    renderizar();

    const antes = await screen.findByTestId("voice-before-call");

    expect(antes.textContent).toContain("Duración máxima");
    expect(antes.textContent).not.toContain("Llamadas al día");
  });

  it("con la voz de respaldo avisa que puede sonar distinta en cada idioma, antes de llamar", async () => {
    // BR2.3: el aviso va antes de la primera frase, y nombra el idioma.
    disponibilidad.mockResolvedValue({ ...CON_LIMITES, voice_mode: "fallback" });
    renderizar();

    expect((await screen.findByTestId("voice-before-call")).textContent).toMatch(
      /voz de respaldo.*distinta en español y en inglés/,
    );
  });

  it("con la voz principal no hay aviso de respaldo", async () => {
    disponibilidad.mockResolvedValue(CON_LIMITES);
    renderizar();

    expect((await screen.findByTestId("voice-before-call")).textContent).not.toMatch(/respaldo/);
  });

  it("la ayuda de la poliza da el nombre y el numero para decirlos, solo al tocarla", async () => {
    disponibilidad.mockResolvedValue(CON_LIMITES);
    renderizar({ examplePolicy: "POL-100042", exampleHolder: "Natalia Henao Rendón" });

    const ayuda = await screen.findByRole("button", { name: tEs("voice.console.sample_button") });
    // Cerrada: ni el numero ni el nombre estan a la vista.
    expect(ayuda.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByTestId("sample-policy-say")).toBeNull();

    await userEvent.click(ayuda);

    expect(ayuda.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByTestId("sample-policy-say").textContent).toBe(
      tEs("voice.console.sample_say", { name: "Natalia Henao Rendón", policy: "POL-100042" }),
    );
  });

  it("sin titular conocido da solo el numero, sin inventar un nombre", async () => {
    disponibilidad.mockResolvedValue(CON_LIMITES);
    renderizar({ examplePolicy: "POL-100042" });

    await userEvent.click(
      await screen.findByRole("button", { name: tEs("voice.console.sample_button") }),
    );

    expect(screen.getByTestId("sample-policy-say").textContent).toBe(
      tEs("voice.console.sample_say_number", { policy: "POL-100042" }),
    );
  });

  it("ya no explica que probar ni repite el aviso sobre la poliza de ejemplo", async () => {
    disponibilidad.mockResolvedValue(CON_LIMITES);
    renderizar({ examplePolicy: "POL-100042" });

    const antes = await screen.findByTestId("voice-before-call");

    expect(antes.textContent).not.toMatch(/Qué puedes probar|póliza de ejemplo\./);
    expect(screen.queryByText(/Interrumpir a la agente/)).toBeNull();
  });

  it("sin poliza de ejemplo no se dibuja la ayuda ni se inventa una", async () => {
    disponibilidad.mockResolvedValue(CON_LIMITES);
    renderizar();

    await screen.findByTestId("voice-before-call");

    expect(screen.queryByTestId("sample-policy-helper")).toBeNull();
  });

  it("la ayuda sigue a mano durante la llamada, que es cuando la agente pide la poliza", async () => {
    disponibilidad.mockResolvedValue(CON_LIMITES);
    renderizar({ examplePolicy: "POL-100042" });
    await userEvent.click(await screen.findByRole("button", { name: "Llamar" }));

    expect(screen.getByTestId("sample-policy-helper")).toBeTruthy();
  });

  it("durante la llamada el bloque de antes desaparece", async () => {
    disponibilidad.mockResolvedValue(CON_LIMITES);
    renderizar();
    await userEvent.click(await screen.findByRole("button", { name: "Llamar" }));

    expect(screen.queryByTestId("voice-before-call")).toBeNull();
  });
});

describe("donde quedo el caso (U17, BR3.4)", () => {
  async function terminarLlamada(cable: ReturnType<typeof transporteDeMentira>) {
    renderWithProviders(
      <VoicePage
        tenantId="una-aseguradora"
        insurerLabel="Una Aseguradora"
        chatHref="/t/una-aseguradora/chat"
        start={cable.start}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));
    cable.estado.empujar({ type: "ended", reason: "hangup" });
    // El desenlace llega en una promesa: se deja correr una vuelta.
    await act(async () => {
      await Promise.resolve();
    });
  }

  it("al terminar dice el numero del caso y donde quedo", async () => {
    desenlace.mockResolvedValue({
      case_number: "SUN482913",
      state: "derived",
      case_link: "/c#un-token",
    });

    await terminarLlamada(transporteDeMentira());

    const bloque = screen.getByTestId("voice-outcome");
    expect(bloque.textContent).toContain("SUN482913");
    // El numero es un renglon pequeno que dice para que sirve, y va despues de donde quedo
    // el caso: ya no es el titular (C10, 2026-10-12).
    const numero = within(bloque).getByTestId("voice-outcome-number");
    expect(numero.textContent).toBe(tEs("voice.console.outcome_number", { number: "SUN482913" }));
    expect(numero.textContent).toMatch(/retomarlo o consultarlo/);
    expect(bloque.textContent).not.toMatch(/^Caso SUN482913/m);
    expect(bloque.textContent).toContain(tEs("voice.console.outcome_derived"));
    // Y el enlace, que es la salida de un caso que ya esta con una persona.
    expect(within(bloque).getByRole("link").getAttribute("href")).toBe("/c#un-token");
  });

  it.each([
    ["verifying", "cases.group.verifying"],
    ["deciding", "cases.group.deciding"],
  ] as const)(
    "un caso que la agente aun evalua (%s) no se cuenta como si estuviera con un ajustador",
    async (estado, clave) => {
      // US1.17: despues de colgar el caso pasa unos segundos evaluandose y puede cerrarse
      // solo. Decir «quedo con un ajustador» o «falta informacion» seria contar lo que no es.
      desenlace.mockResolvedValue({
        case_number: "SUN482913",
        state: estado,
        case_link: "/c#un-token",
      });

      await terminarLlamada(transporteDeMentira());

      const bloque = screen.getByTestId("voice-outcome");
      expect(bloque.textContent).toContain(tEs(clave));
      expect(bloque.textContent).not.toContain(tEs("voice.console.outcome_derived"));
      expect(bloque.textContent).not.toContain(tEs("voice.console.outcome_in_progress"));
      expect(within(bloque).getByRole("link").getAttribute("href")).toBe("/c#un-token");
    },
  );

  it("un caso cerrado dice que quedo cerrado, sin hablar de un ajustador", async () => {
    desenlace.mockResolvedValue({
      case_number: "SUN482913",
      state: "closed",
      case_link: "/c#un-token",
    });

    await terminarLlamada(transporteDeMentira());

    const bloque = screen.getByTestId("voice-outcome");
    expect(bloque.textContent).toContain(tEs("voice.console.outcome_closed"));
    expect(bloque.textContent).not.toContain(tEs("voice.console.outcome_derived"));
  });

  it("un caso que espera datos ofrece pasarlo ya a una persona", async () => {
    // Es la salida que BR3.4 exige: un caso esperando que no la ofrezca deja a
    // quien llamo sin saber que hacer.
    desenlace.mockResolvedValue({
      case_number: "SUN482913",
      state: "awaiting_insured",
      case_link: null,
    });
    traspasar.mockResolvedValue({
      case_number: "SUN482913",
      state: "derived",
      case_link: "/c#otro-token",
    });

    await terminarLlamada(transporteDeMentira());

    const boton = screen.getByRole("button", { name: tEs("voice.console.outcome_hand_off") });
    await userEvent.click(boton);

    expect(traspasar).toHaveBeenCalledWith("una-aseguradora", "call-1");
    const bloque = screen.getByTestId("voice-outcome");
    expect(bloque.textContent).toContain(tEs("voice.console.outcome_derived"));
    expect(within(bloque).getByRole("link").getAttribute("href")).toBe("/c#otro-token");
  });

  it("un caso derivado no ofrece pasarlo: ya esta con una persona", async () => {
    desenlace.mockResolvedValue({
      case_number: "SUN482913",
      state: "derived",
      case_link: "/c#un-token",
    });

    await terminarLlamada(transporteDeMentira());

    expect(
      screen.queryByRole("button", { name: tEs("voice.console.outcome_hand_off") }),
    ).toBeNull();
  });

  it("un caso que se puede seguir por chat lo dice en una frase, con el numero que hay que escribir", async () => {
    // US1.20: lo decide el servidor (continuidad encendida y caso en captura), y la consola
    // solo lo repite.
    desenlace.mockResolvedValue({
      case_number: "SUN482913",
      state: "capturing",
      case_link: null,
      chat_continuation: true,
    });

    await terminarLlamada(transporteDeMentira());

    const frase = within(screen.getByTestId("voice-outcome")).getByTestId("voice-outcome-chat");
    expect(frase.textContent).toBe(tEs("voice.console.outcome_chat"));
  });

  it("si el servidor no dice que el chat puede retomarlo, no lo promete", async () => {
    // Con la continuidad apagada, o con el caso ya en manos de una persona (AC1.19.5).
    desenlace.mockResolvedValue({
      case_number: "SUN482913",
      state: "capturing",
      case_link: null,
      chat_continuation: false,
    });

    await terminarLlamada(transporteDeMentira());

    expect(screen.getByTestId("voice-outcome")).toBeTruthy();
    expect(screen.queryByTestId("voice-outcome-chat")).toBeNull();
  });

  it("si no se puede saber donde quedo, no se inventa nada", async () => {
    // La llamada puede no ser de este navegador, y entonces responde lo mismo que
    // una que no existe. Lo honesto es no dibujar el bloque.
    desenlace.mockResolvedValue(null);

    await terminarLlamada(transporteDeMentira());

    expect(screen.queryByTestId("voice-outcome")).toBeNull();
  });
});

// Colgo antes del resultado (2026-10-13): el caso sigue en revision unos segundos y puede
// cerrarse solo. El desenlace se vuelve a pedir cada 2 s, como mucho 8 veces, y se detiene.
describe("el desenlace que sigue en revision al colgar", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  const EN_REVISION: CallOutcome = {
    case_number: "SUN482913",
    state: "deciding",
    case_link: null,
  };
  const FINAL: CallOutcome = {
    case_number: "SUN482913",
    state: "derived",
    case_link: "/c#un-token",
  };

  /** Cuelga con solo `setTimeout` falso: el reloj de la llamada sigue siendo el de verdad. */
  async function colgar(cable: ReturnType<typeof transporteDeMentira>) {
    const dibujo = renderWithProviders(
      <VoicePage
        tenantId="una-aseguradora"
        insurerLabel="Una Aseguradora"
        chatHref="/t/una-aseguradora/chat"
        start={cable.start}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    cable.estado.empujar({ type: "ended", reason: "hangup" });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    return dibujo;
  }

  async function pasar(ms: number) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ms);
    });
  }

  it("lo vuelve a pedir y, cuando sale de revision, muestra el estado final y el enlace", async () => {
    desenlace.mockResolvedValueOnce(EN_REVISION).mockResolvedValue(FINAL);

    await colgar(transporteDeMentira());

    const bloque = screen.getByTestId("voice-outcome");
    expect(bloque.textContent).toContain(tEs("cases.group.deciding"));
    expect(within(bloque).queryByRole("link")).toBeNull();
    expect(desenlace).toHaveBeenCalledTimes(1);

    await pasar(1999);
    expect(desenlace).toHaveBeenCalledTimes(1);
    await pasar(1);

    expect(desenlace).toHaveBeenCalledTimes(2);
    expect(desenlace).toHaveBeenLastCalledWith("una-aseguradora", "call-1");
    const final = screen.getByTestId("voice-outcome");
    expect(final.textContent).toContain(tEs("voice.console.outcome_derived"));
    expect(within(final).getByRole("link").getAttribute("href")).toBe("/c#un-token");
  });

  it("se detiene en cuanto el estado sale de revision: no vuelve a pedir", async () => {
    desenlace.mockResolvedValueOnce(EN_REVISION).mockResolvedValue(FINAL);

    await colgar(transporteDeMentira());
    await pasar(2000);
    await pasar(2000 * 20);

    expect(desenlace).toHaveBeenCalledTimes(2);
  });

  it("se detiene en el tope: la primera lectura y ocho mas, ni una de mas", async () => {
    desenlace.mockResolvedValue(EN_REVISION);

    await colgar(transporteDeMentira());
    await pasar(2000 * 30);

    expect(desenlace).toHaveBeenCalledTimes(1 + 8);
    // Tras los intentos se queda como esta, sin un mensaje nuevo.
    expect(screen.getByTestId("voice-outcome").textContent).toContain(tEs("cases.group.deciding"));
  });

  it("limpia el temporizador al dejar la pantalla: no vuelve a pedir", async () => {
    desenlace.mockResolvedValue(EN_REVISION);

    const dibujo = await colgar(transporteDeMentira());
    await pasar(2000);
    expect(desenlace).toHaveBeenCalledTimes(2);

    dibujo.unmount();
    await pasar(2000 * 20);

    expect(desenlace).toHaveBeenCalledTimes(2);
  });

  it("si una relectura falla, se queda lo que ya se dijo y no insiste", async () => {
    desenlace.mockResolvedValueOnce(EN_REVISION).mockResolvedValue(null);

    await colgar(transporteDeMentira());
    await pasar(2000 * 20);

    expect(desenlace).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("voice-outcome").textContent).toContain(tEs("cases.group.deciding"));
  });

  it("un desenlace que no esta en revision se pide una sola vez", async () => {
    desenlace.mockResolvedValue(FINAL);

    await colgar(transporteDeMentira());
    await pasar(2000 * 20);

    expect(desenlace).toHaveBeenCalledTimes(1);
  });
});

describe("el sonido de la llamada bloqueado por el navegador (2026-10-11)", () => {
  async function enLlamada() {
    const cable = renderizar();
    await userEvent.click(await screen.findByRole("button", { name: "Llamar" }));
    return cable;
  }

  // En una funcion y no en una constante: el catalogo del idioma llega despues de
  // armar la prueba, y una constante se resolveria con la clave sin texto.
  const boton = () => tEs("voice.console.audio_enable");

  it("con el audio corriendo no hay aviso", async () => {
    const cable = await enLlamada();

    cable.estado.bloquear(false);

    expect(screen.queryByTestId("voice-audio-blocked")).toBeNull();
    expect(screen.queryByRole("button", { name: boton() })).toBeNull();
  });

  it("con el contexto suspendido sale el aviso, visible, con su boton", async () => {
    const cable = await enLlamada();

    cable.estado.bloquear(true);

    const aviso = screen.getByTestId("voice-audio-blocked");
    expect(aviso.textContent).toContain(tEs("voice.console.audio_blocked"));
    expect(within(aviso).getByRole("button", { name: boton() })).toBeTruthy();
  });

  it("al pulsar el boton se reanuda el audio y el aviso se va", async () => {
    const cable = await enLlamada();
    cable.estado.bloquear(true);

    await userEvent.click(screen.getByRole("button", { name: boton() }));

    expect(cable.estado.reanudado).toBe(1);
    expect(screen.queryByTestId("voice-audio-blocked")).toBeNull();
  });

  it("si al pulsar sigue detenido, el aviso se queda para volver a intentarlo", async () => {
    const cable = await enLlamada();
    cable.estado.alReanudar = () => true;
    cable.estado.bloquear(true);

    await userEvent.click(screen.getByRole("button", { name: boton() }));

    expect(cable.estado.reanudado).toBe(1);
    expect(screen.getByTestId("voice-audio-blocked")).toBeTruthy();
  });

  it("si el audio vuelve a correr por otro lado, el aviso se va solo", async () => {
    const cable = await enLlamada();
    cable.estado.bloquear(true);

    cable.estado.bloquear(false);

    expect(screen.queryByTestId("voice-audio-blocked")).toBeNull();
  });

  it("el aviso no sobrevive a la llamada: ni terminada ni en la siguiente", async () => {
    const cable = await enLlamada();
    cable.estado.bloquear(true);

    cable.estado.empujar({ type: "ended", reason: "hangup" });
    expect(screen.queryByTestId("voice-audio-blocked")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));
    expect(screen.queryByTestId("voice-audio-blocked")).toBeNull();
  });
});

describe("lo que la pantalla dice antes de llamar (2026-10-11)", () => {
  it("no le pide audifonos a nadie: que la agente no se oiga es cosa del sistema (2026-10-13)", async () => {
    renderizar();

    const antes = await screen.findByTestId("voice-before-call");
    expect(screen.queryByTestId("voice-headphones")).toBeNull();
    expect(antes.textContent).not.toContain("audífonos");
  });

  it("dice en que idioma sera la llamada, en su renglon, debajo de los limites", async () => {
    renderizar();

    const idioma = await screen.findByTestId("voice-call-language");
    expect(idioma.textContent).toBe("Llamada en español.");
    // Dos renglones: los limites juntos y el idioma aparte, los dos antes del microfono.
    expect(idioma.closest("ul")).toBeNull();
    const antes = screen.getByTestId("voice-before-call");
    expect(antes.querySelector("ul")?.textContent).toContain("Duración máxima de cada llamada");
    expect(antes.contains(idioma)).toBe(true);
  });

  it("el idioma que dice es el que la apertura manda: el elegido, o el de la aseguradora", async () => {
    // Pagina en ingles: la llamada se abre en ingles, y la linea lo dice en ingles. Es lo
    // mismo que decide `openCall` (el idioma de la pagina), asi que si una cambia la otra
    // tambien tiene que cambiar.
    const cable = transporteDeMentira();
    renderWithProviders(
      <VoicePage
        tenantId="una-aseguradora"
        insurerLabel="Una Aseguradora"
        chatHref="/t/una-aseguradora/chat"
        start={cable.start}
      />,
      "en",
    );

    expect((await screen.findByTestId("voice-call-language")).textContent).toBe("Call in English.");
    await userEvent.click(screen.getByRole("button", { name: "Call" }));
    expect(abrir).toHaveBeenCalledWith("una-aseguradora", "en");
  });
});

describe("al empezar otra llamada (2026-10-11)", () => {
  const OTRO_DESENLACE: CallOutcome = {
    case_number: "SUN482913",
    state: "derived",
    case_link: "/c#un-token",
  };

  async function llamadaTerminadaConDesenlace(reason: "hangup" | "dropped" = "hangup") {
    desenlace.mockResolvedValue(OTRO_DESENLACE);
    const cable = renderizar();
    await userEvent.click(await screen.findByRole("button", { name: "Llamar" }));
    cable.estado.empujar({ type: "ended", reason });
    await act(async () => {
      await Promise.resolve();
    });
    return cable;
  }

  it("el recuadro de donde quedo el caso anterior desaparece al pulsar Llamar", async () => {
    await llamadaTerminadaConDesenlace();
    expect(screen.getByTestId("voice-outcome")).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));

    expect(screen.queryByTestId("voice-outcome")).toBeNull();
  });

  it("y el de la llamada anterior no vuelve si su respuesta llega tarde", async () => {
    // La respuesta de `callOutcome` es una promesa: si llega despues de pulsar Llamar,
    // volveria a pintar el recuadro que se acaba de quitar.
    let responder: (valor: CallOutcome | null) => void = () => undefined;
    desenlace.mockReturnValue(
      new Promise<CallOutcome | null>((resolver) => {
        responder = resolver;
      }),
    );
    const cable = renderizar();
    await userEvent.click(await screen.findByRole("button", { name: "Llamar" }));
    cable.estado.empujar({ type: "ended", reason: "hangup" });
    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));

    await act(async () => {
      responder(OTRO_DESENLACE);
      await Promise.resolve();
    });

    expect(screen.queryByTestId("voice-outcome")).toBeNull();
  });

  it("la hora hasta la que se podia retomar tampoco se queda: la siguiente no hereda un plazo", async () => {
    // La primera llamada se corto y quedo retomable hasta una hora. La segunda tambien se
    // corta, pero esta vez el servidor no contesta: la hora vieja no puede volver a
    // decirse como si fuera de esta.
    disponibilidad.mockResolvedValueOnce(DISPONIBLE);
    disponibilidad.mockResolvedValueOnce({ ...DISPONIBLE, resume_until: "2026-10-11T20:45:00Z" });
    disponibilidad.mockRejectedValue(new Error("la red"));
    const cable = renderizar();
    await userEvent.click(await screen.findByRole("button", { name: "Llamar" }));
    cable.estado.empujar({ type: "ended", reason: "dropped" });
    expect(await screen.findByTestId("voice-resume-until")).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: "Llamar" }));
    cable.estado.empujar({ type: "ended", reason: "dropped" });
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText(/se cortó/)).toBeTruthy();
    expect(screen.queryByTestId("voice-resume-until")).toBeNull();
  });
});

describe("hasta cuando se puede retomar (2026-10-11)", () => {
  const HASTA = "2026-10-11T20:45:00Z";
  /** La hora como la lee la persona, en la zona del navegador de la prueba. */
  const horaEsperada = new Intl.DateTimeFormat("es", { timeStyle: "short" }).format(
    new Date(HASTA),
  );

  async function terminar(reason: "dropped" | "error" | "saved" | "silence") {
    const cable = renderizar();
    await userEvent.click(await screen.findByRole("button", { name: "Llamar" }));
    cable.estado.empujar({ type: "ended", reason });
    await act(async () => {
      await Promise.resolve();
    });
  }

  it.each(["dropped", "error", "saved"] as const)(
    "tras %s dice hasta que hora, con la que da el servidor",
    async (motivo) => {
      disponibilidad.mockResolvedValue({ ...DISPONIBLE, resume_until: HASTA });

      await terminar(motivo);

      const linea = await screen.findByTestId("voice-resume-until");
      expect(linea.textContent).toBe(`Tienes hasta ${horaEsperada} para retomarlo.`);
    },
  );

  it("sin la hora del servidor no afirma que se pueda retomar", async () => {
    // El servidor no la dio: la llamada no quedo retomable, o no se pudo leer. Decir
    // "puedes retomarlo" sin saberlo es prometer lo que quiza no es verdad.
    disponibilidad.mockResolvedValue({ ...DISPONIBLE, resume_until: null });

    await terminar("dropped");

    expect(screen.getByText(/se cortó/)).toBeTruthy();
    expect(screen.queryByTestId("voice-resume-until")).toBeNull();
    expect(screen.queryByText(/retomar/i)).toBeNull();
  });

  it("si la disponibilidad falla, tampoco se inventa un plazo", async () => {
    disponibilidad.mockResolvedValueOnce(DISPONIBLE).mockRejectedValue(new Error("la red"));

    await terminar("error");

    expect(screen.queryByTestId("voice-resume-until")).toBeNull();
    expect(screen.queryByText(/retomar/i)).toBeNull();
  });

  it.each(["silence"] as const)(
    "tras %s, que no deja la llamada retomable, no dice nada de retomar",
    async (motivo) => {
      disponibilidad.mockResolvedValue({ ...DISPONIBLE, resume_until: HASTA });

      await terminar(motivo);

      expect(screen.queryByTestId("voice-resume-until")).toBeNull();
    },
  );

  it("dejarlo guardado dice que lo dejo guardado", async () => {
    disponibilidad.mockResolvedValue({ ...DISPONIBLE, resume_until: HASTA });

    await terminar("saved");

    expect(screen.getByText(tEs("voice.ended.saved"))).toBeTruthy();
  });
});
