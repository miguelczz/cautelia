import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { voiceSocketUrl } from "../../shared/api-client/voice";
import {
  chooseMicrophone,
  chosenMicrophone,
  ESPERA_A_REANUDAR_MS,
  ESPERA_DE_CIERRE_MS,
  ESPERA_DE_LA_DESPEDIDA_MS,
  MicrophoneDeniedError,
  requestMicrophone,
  startCall,
  watchPlayback,
} from "./voice-transport";

// Lo que se comprueba aqui es lo que no se ve en la pantalla y sin embargo decide
// como suena una llamada: con que se pide el microfono, y como se compone la
// direccion del socket.
//
// El resto del transporte --los dos nodos de audio, la cola, el vaciado-- no se
// prueba aqui: `AudioWorklet` no existe en el documento de pruebas, y un doble de
// `AudioContext` mediria el doble. Lo que sostiene esa parte es la prueba de la
// consola con el transporte sustituido y, para el vaciado, el reloj del cliente
// que NFR2 mide contra el despliegue vivo.

const pedido = vi.fn<(constraints: MediaStreamConstraints) => Promise<MediaStream>>();

beforeEach(() => {
  pedido.mockReset();
  pedido.mockResolvedValue({ getTracks: () => [] } as unknown as MediaStream);
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: pedido },
  });
});

describe("como se pide el microfono", () => {
  it("con las tres correcciones del navegador activadas", async () => {
    // **BR4.2, y ninguna de las tres es cosmetica.** Sin cancelacion de eco, la
    // propia voz de la agente vuelve por el microfono y la interrumpe a si misma:
    // el piso de palabras de la interrupcion no lo salva, porque lo que vuelve es
    // una frase entera y bien pronunciada. Es el defecto mas ridiculo que puede
    // tener una llamada y no se ve en ninguna pantalla.
    await requestMicrophone();

    expect(pedido).toHaveBeenCalledWith({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  });

  it("un permiso negado levanta su propio error, no uno cualquiera", async () => {
    // La pantalla distingue "no me dieron el microfono" --que tiene su explicacion
    // y su oferta de chat-- de "algo fallo", que se reintenta. Con un error
    // generico las dos saldrian por la misma puerta. El navegador niega con una
    // DOMException cuyo **nombre** es NotAllowedError; el mensaje es libre.
    pedido.mockRejectedValue(new DOMException("Permission denied", "NotAllowedError"));

    await expect(requestMicrophone()).rejects.toBeInstanceOf(MicrophoneDeniedError);
  });

  it("un microfono que no existe o esta ocupado no se cuenta como negado", async () => {
    // Decirle a la persona que permita el microfono desde la barra del navegador,
    // cuando ya lo permitio, la manda a un ajuste que no arregla nada (defecto
    // del 2026-10-06). Esa falla sale por la puerta general.
    pedido.mockRejectedValue(new DOMException("Requested device not found", "NotFoundError"));

    const fallo = await requestMicrophone().catch((error: unknown) => error);
    expect(fallo).toBeInstanceOf(DOMException);
    expect(fallo).not.toBeInstanceOf(MicrophoneDeniedError);
  });
});

describe("el microfono elegido al probarlo (2026-10-09)", () => {
  it("la llamada pide ese microfono exacto", async () => {
    chooseMicrophone("mac");

    await requestMicrophone();

    expect(pedido).toHaveBeenCalledWith({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        deviceId: { exact: "mac" },
      },
    });
  });

  it("si ese microfono ya no esta, se olvida y se usa el del navegador", async () => {
    chooseMicrophone("desconectado");
    pedido.mockRejectedValueOnce(new DOMException("gone", "OverconstrainedError"));

    await requestMicrophone();

    expect(chosenMicrophone()).toBeNull();
    expect(pedido).toHaveBeenLastCalledWith({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  });
});

describe("la direccion del socket", () => {
  it("sobre https sale wss, que es lo unico que el navegador acepta desde ahi", () => {
    expect(voiceSocketUrl("/api/voice/una-aseguradora/socket", "https://demo.untangle.test")).toBe(
      "wss://demo.untangle.test/api/voice/una-aseguradora/socket",
    );
  });

  it("sobre http sale ws", () => {
    expect(voiceSocketUrl("/api/voice/una-aseguradora/socket", "http://localhost:8051")).toBe(
      "ws://localhost:8051/api/voice/una-aseguradora/socket",
    );
  });

  it("no lleva token ni ninguna otra cosa en la cadena de consulta", () => {
    // BR1.4: un token en la direccion acaba en los registros del servidor y en el
    // historial del navegador, y de ahi no se saca. Va en el primer cuadro.
    const url = voiceSocketUrl("/api/voice/una-aseguradora/socket", "https://demo.untangle.test");

    expect(url).not.toContain("?");
    expect(url).not.toContain("token");
  });
});

// --- El presupuesto del vaciado (PERF-U16.2) ----------------------------------

/** Un nodo de audio de mentira: guarda lo que se le manda por su puerto. */
function nodoDeMentira(orden?: string[]) {
  const mensajes: { type: string }[] = [];
  return {
    mensajes,
    nodo: {
      port: {
        postMessage: (mensaje: { type: string }) => {
          mensajes.push(mensaje);
          orden?.push(`puerto:${mensaje.type}`);
        },
        onmessage: null as ((evento: MessageEvent<unknown>) => void) | null,
      },
      connect: () => undefined,
    },
  };
}

/** Un socket de mentira con la forma que el transporte usa. */
function socketDeMentira() {
  const oyentes = new Map<string, ((evento: unknown) => void)[]>();
  return {
    enviados: [] as unknown[],
    socket: {
      binaryType: "arraybuffer",
      readyState: WebSocket.OPEN,
      addEventListener(tipo: string, oyente: (evento: unknown) => void) {
        oyentes.set(tipo, [...(oyentes.get(tipo) ?? []), oyente]);
      },
      send: ((): void => undefined) as (dato: unknown) => void,
      close: (): void => undefined,
    },
    emitir(tipo: string, evento: unknown) {
      for (const oyente of oyentes.get(tipo) ?? []) {
        oyente(evento);
      }
    },
  };
}

describe("el vaciado de la cola de reproduccion", () => {
  it("sale antes que el aviso a la pantalla y cabe en su presupuesto", async () => {
    // **PERF-U16.2: p95 ≤ 50 ms del cuadro `stop_audio` al vaciado.** Es el
    // ultimo tramo de NFR2 --menos de 300 ms de la marca de interrupcion a que la
    // reproduccion pare-- y el unico que vive en el navegador: el servidor no
    // puede retirar el audio que ya mando.
    //
    // Se mide **hasta que la orden sale por el puerto del nodo**, que es lo que
    // este archivo controla. Lo que pasa dentro del `AudioWorklet` --tirar la cola
    // y el trozo a medio consumir-- corre en el hilo de audio y el documento de
    // pruebas no lo tiene; eso se mide contra el despliegue vivo, por hito.
    //
    // Y el **orden** importa tanto como el numero: si el aviso a la pantalla
    // saliera primero, el vaciado esperaria un cuadro de dibujo entero.
    // La secuencia real de lo que pasa, no dos listas que se comparan por tamano:
    // con `some(...)` la prueba pasaba igual con el vaciado **despues** del aviso,
    // porque los dos ocurren en el mismo tick. Se comprobo invirtiendolos.
    const orden: string[] = [];
    const captura = nodoDeMentira(orden);
    const reproduccion = nodoDeMentira(orden);
    const nodos = [captura.nodo, reproduccion.nodo];
    let creados = 0;

    vi.stubGlobal(
      "AudioContext",
      class {
        destination = {};
        audioWorklet = { addModule: () => Promise.resolve() };
        createMediaStreamSource() {
          return { connect: () => undefined };
        }
        close() {
          return Promise.resolve();
        }
      },
    );
    vi.stubGlobal(
      "AudioWorkletNode",
      class {
        port;
        connect;
        constructor() {
          const elegido = nodos.at(creados) ?? captura.nodo;
          creados += 1;
          this.port = elegido.port;
          this.connect = elegido.connect;
        }
      },
    );

    const cable = socketDeMentira();
    const avisos: string[] = [];
    await startCall({
      stream: { getTracks: () => [] } as unknown as MediaStream,
      socketUrl: "wss://demo.untangle.test/api/voice/una-aseguradora/socket",
      token: "un-token",
      handlers: {
        onFrame: (cuadro) => {
          avisos.push(cuadro.type);
          orden.push(`pantalla:${cuadro.type}`);
        },
        onLevel: () => undefined,
        onClosed: () => undefined,
      },
      socket: () => cable.socket as unknown as WebSocket,
    });

    const muestras: number[] = [];
    for (let i = 0; i < 20; i += 1) {
      reproduccion.mensajes.length = 0;
      orden.length = 0;
      const inicio = performance.now();
      cable.emitir("message", { data: JSON.stringify({ type: "stop_audio" }) });
      muestras.push(performance.now() - inicio);
      // El vaciado primero y el aviso despues, **en ese orden**.
      expect(orden).toEqual(["puerto:flush", "pantalla:stop_audio"]);
    }

    muestras.sort((a, b) => a - b);
    const p95 = muestras[Math.floor(muestras.length * 0.95) - 1] ?? 0;
    expect(p95, `p95 de ${p95.toFixed(2)} ms`).toBeLessThanOrEqual(50);
    expect(avisos).toContain("stop_audio");

    vi.unstubAllGlobals();
  });
});

describe("colgar", () => {
  function montar() {
    vi.stubGlobal(
      "AudioContext",
      class {
        state = "running";
        destination = {};
        audioWorklet = { addModule: () => Promise.resolve() };
        createMediaStreamSource() {
          return { connect: () => undefined };
        }
        resume() {
          return Promise.resolve();
        }
        close() {
          return Promise.resolve();
        }
      },
    );
    vi.stubGlobal(
      "AudioWorkletNode",
      class {
        port = { postMessage: () => undefined, onmessage: null };
        connect = () => undefined;
      },
    );
  }

  it("suelta el microfono ya y deja el socket abierto para que el servidor conteste", async () => {
    // Cerrar el socket junto con el cuadro de colgar le quitaba al servidor el
    // canal del `ended`, y la pantalla se quedaba en llamada (2026-10-07).
    vi.useFakeTimers();
    montar();
    const cable = socketDeMentira();
    const enviados: string[] = [];
    let cerrado = false;
    cable.socket.send = (dato: unknown) => {
      enviados.push(String(dato));
    };
    cable.socket.close = () => {
      cerrado = true;
    };
    const pista = { stop: vi.fn() };
    const llamada = await startCall({
      stream: { getTracks: () => [pista] } as unknown as MediaStream,
      socketUrl: "wss://demo.untangle.test/api/voice/una-aseguradora/socket",
      token: "un-token",
      handlers: { onFrame: () => undefined, onLevel: () => undefined, onClosed: () => undefined },
      socket: () => cable.socket as unknown as WebSocket,
    });

    llamada.hangup();

    expect(enviados).toContain(JSON.stringify({ type: "hangup" }));
    expect(pista.stop).toHaveBeenCalled();
    expect(cerrado).toBe(false);

    vi.advanceTimersByTime(ESPERA_DE_CIERRE_MS);
    expect(cerrado).toBe(true);

    vi.useRealTimers();
    vi.unstubAllGlobals();
  });
});

describe("cuando el servidor termina la llamada (2026-10-10)", () => {
  // La despedida lleva el numero de caso y todavia esta sonando cuando llega el
  // aviso de fin: cerrar el audio entonces la cortaba.
  interface Puerto {
    postMessage: (mensaje: { type: string }) => void;
    onmessage: ((evento: { data: { type: string } }) => void) | null;
  }

  async function llamadaConPuerto() {
    let cerroElAudio = false;
    const mensajes: string[] = [];
    const puertos: Puerto[] = [];
    vi.stubGlobal(
      "AudioContext",
      class {
        state = "running";
        destination = {};
        audioWorklet = { addModule: () => Promise.resolve() };
        createMediaStreamSource() {
          return { connect: () => undefined };
        }
        resume() {
          return Promise.resolve();
        }
        close() {
          cerroElAudio = true;
          return Promise.resolve();
        }
      },
    );
    vi.stubGlobal(
      "AudioWorkletNode",
      class {
        port: Puerto = {
          postMessage: (mensaje) => {
            mensajes.push(mensaje.type);
          },
          onmessage: null,
        };
        connect = () => undefined;
        constructor() {
          puertos.push(this.port);
        }
      },
    );
    const cable = socketDeMentira();
    const pista = { stop: vi.fn() };
    const llamada = await startCall({
      stream: { getTracks: () => [pista] } as unknown as MediaStream,
      socketUrl: "wss://demo.untangle.test/api/voice/una-aseguradora/socket",
      token: "un-token",
      handlers: { onFrame: () => undefined, onLevel: () => undefined, onClosed: () => undefined },
      socket: () => cable.socket as unknown as WebSocket,
    });
    return {
      llamada,
      pista,
      mensajes,
      // El nodo de reproduccion es el segundo que se crea, despues del de captura.
      avisarColaVacia: () => {
        for (const puerto of puertos) {
          puerto.onmessage?.({ data: { type: "drained" } });
        }
      },
      cerroElAudio: () => cerroElAudio,
    };
  }

  it("suelta el microfono ya, y no cierra el audio hasta que la cola queda vacia", async () => {
    vi.useFakeTimers();
    const escena = await llamadaConPuerto();

    escena.llamada.finish();

    expect(escena.pista.stop).toHaveBeenCalled();
    expect(escena.mensajes).toContain("drain");
    // No vacia la cola: lo que queda en ella es justo lo que tiene que sonar.
    expect(escena.mensajes).not.toContain("flush");
    expect(escena.cerroElAudio()).toBe(false);

    escena.avisarColaVacia();
    expect(escena.cerroElAudio()).toBe(true);

    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("si la cola nunca avisa, cierra igual al pasar el tope", async () => {
    vi.useFakeTimers();
    const escena = await llamadaConPuerto();

    escena.llamada.finish();
    vi.advanceTimersByTime(ESPERA_DE_LA_DESPEDIDA_MS - 1);
    expect(escena.cerroElAudio()).toBe(false);
    vi.advanceTimersByTime(1);
    expect(escena.cerroElAudio()).toBe(true);

    vi.useRealTimers();
    vi.unstubAllGlobals();
  });
});

// --- El audio de salida detenido por el navegador (2026-10-11) ------------------------

/** Un contexto de audio de mentira: solo lo que el vigilante le pide. */
function contextoDeMentira(estado: string) {
  const contexto = {
    state: estado,
    onstatechange: null as (() => void) | null,
    resume: vi.fn<() => Promise<void>>(),
  };
  /** Un `resume()` que funciona: el contexto pasa a correr. */
  const funciona = () => {
    contexto.resume.mockImplementation(() => {
      contexto.state = "running";
      return Promise.resolve();
    });
  };
  /** El de Safari fuera de un gesto: la promesa queda pendiente para siempre. */
  const quedaPendiente = () => {
    contexto.resume.mockImplementation(() => new Promise<void>(() => undefined));
  };
  return {
    contexto: contexto as unknown as AudioContext,
    bruto: contexto,
    funciona,
    quedaPendiente,
  };
}

describe("el vigilante del audio de salida", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("con el audio corriendo no avisa de nada ni intenta reanudar", () => {
    const { contexto, bruto } = contextoDeMentira("running");
    const avisos: boolean[] = [];

    const vigilante = watchPlayback(contexto, (bloqueado) => avisos.push(bloqueado));
    vigilante.check();
    vigilante.check();

    expect(bruto.resume).not.toHaveBeenCalled();
    // Solo cambios: el estado de partida se dice una vez, y es "corre".
    expect(avisos).toEqual([false]);
  });

  it("detenido, intenta reanudar y, si lo consigue, nunca avisa de un bloqueo", async () => {
    const { contexto, bruto, funciona } = contextoDeMentira("suspended");
    funciona();
    const avisos: boolean[] = [];

    const vigilante = watchPlayback(contexto, (bloqueado) => avisos.push(bloqueado));
    vigilante.check();
    await vi.advanceTimersByTimeAsync(0);

    expect(bruto.resume).toHaveBeenCalledTimes(1);
    expect(avisos).toEqual([false]);
  });

  it("si el navegador no contesta, avisa del bloqueo tras la espera, y el toque lo quita", async () => {
    // Safari fuera de un gesto deja la promesa de `resume()` pendiente: sin tope, el
    // aviso no saldria nunca y la llamada parecería muda.
    const { contexto, bruto, quedaPendiente, funciona } = contextoDeMentira("suspended");
    quedaPendiente();
    const avisos: boolean[] = [];
    const vigilante = watchPlayback(contexto, (bloqueado) => avisos.push(bloqueado));

    vigilante.check();
    await vi.advanceTimersByTimeAsync(ESPERA_A_REANUDAR_MS - 1);
    expect(avisos).toEqual([]);
    await vi.advanceTimersByTimeAsync(1);
    expect(avisos).toEqual([true]);

    // El toque de la persona: ahora si se deja.
    funciona();
    await vigilante.resume();
    expect(bruto.resume).toHaveBeenCalledTimes(2);
    expect(avisos).toEqual([true, false]);
  });

  it("llegando audio muchas veces seguidas se intenta de a uno, no uno por trozo", async () => {
    // El audio llega cada 20 ms: un intento por trozo apilaria promesas pendientes.
    const { contexto, bruto, quedaPendiente } = contextoDeMentira("suspended");
    quedaPendiente();
    const vigilante = watchPlayback(contexto, () => undefined);

    for (let i = 0; i < 25; i += 1) {
      vigilante.check();
    }
    expect(bruto.resume).toHaveBeenCalledTimes(1);

    // Pasada la espera se puede volver a intentar: otro trozo, otro intento.
    await vi.advanceTimersByTimeAsync(ESPERA_A_REANUDAR_MS);
    vigilante.check();
    expect(bruto.resume).toHaveBeenCalledTimes(2);
  });

  it("si algo mas lo reanuda, el aviso se va solo", async () => {
    const { contexto, bruto, quedaPendiente } = contextoDeMentira("suspended");
    quedaPendiente();
    const avisos: boolean[] = [];
    const vigilante = watchPlayback(contexto, (bloqueado) => avisos.push(bloqueado));
    vigilante.check();
    await vi.advanceTimersByTimeAsync(ESPERA_A_REANUDAR_MS);
    expect(avisos).toEqual([true]);

    bruto.state = "running";
    bruto.onstatechange?.();

    expect(avisos).toEqual([true, false]);
  });

  it.each([
    ["interrupted", true],
    ["suspended", true],
    ["running", false],
    ["closed", false],
  ])("el estado %s cuenta como detenido: %s", async (estado, detenido) => {
    // `interrupted` es de Safari; `closed` es el final de la llamada, no un audio que
    // haya que activar.
    const { contexto, quedaPendiente } = contextoDeMentira(estado);
    quedaPendiente();
    const avisos: boolean[] = [];

    watchPlayback(contexto, (bloqueado) => avisos.push(bloqueado)).check();
    await vi.advanceTimersByTimeAsync(ESPERA_A_REANUDAR_MS);

    expect(avisos).toEqual([detenido]);
  });
});

describe("la llamada y el audio de salida detenido", () => {
  function montarSuspendido() {
    const resume = vi.fn<() => Promise<void>>(() => new Promise<void>(() => undefined));
    const instancias: { state: string; onstatechange: (() => void) | null }[] = [];
    vi.stubGlobal(
      "AudioContext",
      class {
        state = "suspended";
        onstatechange: (() => void) | null = null;
        destination = {};
        audioWorklet = { addModule: () => Promise.resolve() };
        constructor() {
          instancias.push(this);
        }
        createMediaStreamSource() {
          return { connect: () => undefined };
        }
        resume = resume;
        close() {
          return Promise.resolve();
        }
      },
    );
    vi.stubGlobal(
      "AudioWorkletNode",
      class {
        port = { postMessage: () => undefined, onmessage: null };
        connect = () => undefined;
      },
    );
    return { resume, instancias };
  }

  it("arranca aunque el navegador no deje reanudar, y avisa a la pantalla", async () => {
    // Antes la llamada esperaba `resume()` sin tope: con la promesa pendiente, la
    // llamada no llegaba a empezar y nadie podia tocar nada.
    vi.useFakeTimers();
    const { resume } = montarSuspendido();
    const cable = socketDeMentira();
    const avisos: boolean[] = [];

    const arranque = startCall({
      stream: { getTracks: () => [] } as unknown as MediaStream,
      socketUrl: "wss://demo.untangle.test/api/voice/una-aseguradora/socket",
      token: "un-token",
      handlers: {
        onFrame: () => undefined,
        onLevel: () => undefined,
        onClosed: () => undefined,
        onAudioBlocked: (bloqueado) => avisos.push(bloqueado),
      },
      socket: () => cable.socket as unknown as WebSocket,
    });
    await vi.advanceTimersByTimeAsync(ESPERA_A_REANUDAR_MS);
    const llamada = await arranque;
    // Al conectar vuelve a intentarlo, y de nuevo sin respuesta.
    await vi.advanceTimersByTimeAsync(ESPERA_A_REANUDAR_MS);

    expect(resume.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(avisos).toEqual([true]);
    expect(typeof llamada.resumeAudio).toBe("function");

    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("cada trozo de audio que llega con el contexto detenido vuelve a intentarlo", async () => {
    vi.useFakeTimers();
    const { resume } = montarSuspendido();
    const cable = socketDeMentira();
    const arranque = startCall({
      stream: { getTracks: () => [] } as unknown as MediaStream,
      socketUrl: "wss://demo.untangle.test/api/voice/una-aseguradora/socket",
      token: "un-token",
      handlers: { onFrame: () => undefined, onLevel: () => undefined, onClosed: () => undefined },
      socket: () => cable.socket as unknown as WebSocket,
    });
    await vi.advanceTimersByTimeAsync(ESPERA_A_REANUDAR_MS * 2);
    await arranque;
    const antes = resume.mock.calls.length;

    cable.emitir("message", { data: new ArrayBuffer(480) });

    expect(resume.mock.calls.length).toBe(antes + 1);

    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("el boton llama a resume() en el acto, dentro del gesto, y no despues de un await", async () => {
    // Safari solo deja reanudar si `resume()` se llama dentro del toque. Si el vigilante
    // esperara algo antes, el gesto ya habria pasado.
    vi.useFakeTimers();
    const { resume } = montarSuspendido();
    const cable = socketDeMentira();
    const arranque = startCall({
      stream: { getTracks: () => [] } as unknown as MediaStream,
      socketUrl: "wss://demo.untangle.test/api/voice/una-aseguradora/socket",
      token: "un-token",
      handlers: { onFrame: () => undefined, onLevel: () => undefined, onClosed: () => undefined },
      socket: () => cable.socket as unknown as WebSocket,
    });
    await vi.advanceTimersByTimeAsync(ESPERA_A_REANUDAR_MS * 2);
    const llamada = await arranque;
    const antes = resume.mock.calls.length;

    void llamada.resumeAudio();

    expect(resume.mock.calls.length).toBe(antes + 1);

    vi.useRealTimers();
    vi.unstubAllGlobals();
  });
});
