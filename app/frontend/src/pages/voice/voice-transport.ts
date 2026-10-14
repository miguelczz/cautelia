// El transporte de la llamada en el navegador: microfono, socket y los dos nodos
// de audio (C-29, BR1.2, BR1.3, BR4.2, BR4.3).
//
// Todo lo impuro de esta pantalla vive aqui. El reductor de `voice-events.ts` es
// puro y se prueba sin navegador; esto es lo que no se puede probar asi, y por
// eso se mantiene delgado: abre, conecta, reparte y cierra.
//
// **El orden de arranque es la regla, no un detalle** (BR1.2):
//
//   1. el microfono,
//   2. la sesion,
//   3. el socket.
//
// Al reves, un permiso negado dejaria un caso vacio en la bandeja de una
// ajustadora. Ese orden **no se cumple aqui**, y por eso este modulo no lo
// promete: cruza las tres cosas y solo la pantalla las ve todas. Lo que este
// archivo hace es imponerlo por la forma de sus funciones --`requestMicrophone`
// esta aparte y `startCall` **exige** el micro ya concedido, no se lo busca--, de
// modo que abrir el socket sin haber pedido el permiso ni siquiera compila.
//
// **El `AudioContext` se crea al pulsar el boton**, aunque despues de pedir el
// microfono y abrir la sesion, y por eso se reanuda a mano: Firefox y Safari lo
// entregan suspendido fuera del gesto (medido el 2026-10-07).
//
// **El audio de salida puede quedar detenido sin que nada falle** (2026-10-11). La politica
// de reproduccion automatica del navegador --sobre todo en iPhone y Safari-- deja el
// `AudioContext` en `suspended` hasta que la persona toque la pantalla, y la llamada
// parece muda. `watchPlayback` lo vigila: al conectar y cada vez que llega audio intenta
// reanudarlo, y si no lo logra avisa a la pantalla, que ofrece un boton cuyo toque es el
// gesto que el navegador pide.
//
// **La cola de reproduccion se vacia aqui y no en React** (BR4.3). Pasar
// `stop_audio` por un estado y esperar al siguiente pintado metería un cuadro de
// dibujo entero en el camino de lo unico que NFR2 mide. El cuadro se reenvia
// ademas a la pantalla, para que la linea interrumpida se marque.

import { parseFrame, type WireFrame } from "./voice-events";

/** Las direcciones de los dos nodos, servidas como estaticos. */
const CAPTURA = "/voice-capture-worklet.js";
const REPRODUCCION = "/voice-playback-worklet.js";

/** Cuanto se espera, tras colgar, a que el servidor cierre el socket. */
export const ESPERA_DE_CIERRE_MS = 2_000;

/**
 * Cuanto se espera, como mucho, a que termine de sonar la despedida antes de cerrar
 * el audio. La mas larga --paso siguiente, numero de caso y adios-- dura unos once
 * segundos.
 */
export const ESPERA_DE_LA_DESPEDIDA_MS = 15_000;

/** El unico formato del aplicativo: PCM de 16 bits, mono, a 24 kHz. */
export const SAMPLE_RATE = 24000;

/**
 * Cuanto se espera a que `resume()` conteste antes de decidir si el audio sigue
 * detenido. Safari deja esa promesa **pendiente** cuando no hay gesto de la persona, asi
 * que esperarla sin tope seria no avisar nunca.
 */
export const ESPERA_A_REANUDAR_MS = 400;

/** El navegador no dio el microfono. No hay llamada y no hay caso (BR1.2). */
export class MicrophoneDeniedError extends Error {
  constructor() {
    super("microphone denied");
    this.name = "MicrophoneDeniedError";
  }
}

export interface CallHandlers {
  /** Un cuadro de texto del servidor, ya tipado. */
  readonly onFrame: (frame: WireFrame) => void;
  /**
   * El audio de salida quedo detenido (`true`) o volvio a correr (`false`). Se dice solo
   * cuando cambia. Opcional: lo que no lo necesita no tiene por que escucharlo.
   */
  readonly onAudioBlocked?: (blocked: boolean) => void;
  /** El nivel del microfono de este trozo, entre 0 y 1. No sale del navegador. */
  readonly onLevel: (level: number) => void;
  /** El socket se cerro, por la razon que sea. */
  readonly onClosed: () => void;
}

export interface StartOptions {
  /** El microfono **ya concedido**. Que sea obligatorio es la mitad de BR1.2. */
  readonly stream: MediaStream;
  readonly socketUrl: string;
  readonly token: string;
  readonly handlers: CallHandlers;
  /** Solo para las pruebas: sin esto, el socket de verdad. */
  readonly socket?: (url: string) => WebSocket;
}

/**
 * Pide el microfono con las tres correcciones del navegador puestas (BR4.2).
 *
 * Las tres no son cosmetica: sin cancelacion de eco, la propia voz de la agente
 * vuelve por el microfono y la interrumpe a si misma, que es el defecto mas
 * ridiculo que puede tener una llamada.
 *
 * **Es lo primero que ocurre al pulsar llamar** (BR1.2), y esta aparte de
 * `startCall` para que ese orden se pueda ver --y probar-- desde la pantalla.
 */
export async function requestMicrophone(): Promise<MediaStream> {
  const elegido = chosenMicrophone();
  try {
    return await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        // El que la persona eligio al probar el microfono, si eligio uno
        // (2026-10-09): el navegador puede tener elegido otro que entrega silencio.
        ...(elegido === null ? {} : { deviceId: { exact: elegido } }),
      },
    });
  } catch (error) {
    // Solo un permiso negado es "denegado". Un microfono que no existe o que otra
    // aplicacion tiene tomado es otra cosa, y decirle a la persona que lo permita
    // desde la barra del navegador --cuando ya lo permitio-- es mandarla a buscar
    // un ajuste que no arregla nada (defecto del 2026-10-06).
    const nombre = error instanceof DOMException ? error.name : "";
    if (elegido !== null && (nombre === "OverconstrainedError" || nombre === "NotFoundError")) {
      // El microfono elegido ya no esta (se desconecto, cambio su identificador):
      // se olvida y se usa el del navegador, en vez de dejar la llamada sin voz.
      chooseMicrophone(null);
      return requestMicrophone();
    }
    if (
      nombre === "NotAllowedError" ||
      nombre === "SecurityError" ||
      nombre === "PermissionDeniedError"
    ) {
      throw new MicrophoneDeniedError();
    }
    throw error;
  }
}

/**
 * `resume()` con tope: devuelve cuando el contexto contesta o pasa `ESPERA_A_REANUDAR_MS`,
 * lo primero. Sin tope, un Safari que deja la promesa pendiente colgaria al que espera.
 */
function reanudarSinEsperarDeMas(contexto: AudioContext): Promise<unknown> {
  // `resume()` primero y de forma sincrona: tiene que salir dentro del gesto de la persona.
  const respuesta = contexto.resume().catch(() => undefined);
  let temporizador = 0;
  const tope = new Promise<void>((resolver) => {
    temporizador = window.setTimeout(resolver, ESPERA_A_REANUDAR_MS);
  });
  return Promise.race([respuesta, tope]).finally(() => {
    window.clearTimeout(temporizador);
  });
}

/** Lo que la pantalla y el transporte usan para vigilar el audio de salida. */
export interface PlaybackWatch {
  /** Mira el estado: si esta detenido intenta reanudarlo, y avisa de lo que quede. */
  readonly check: () => void;
  /** Reanuda ya y avisa. Se llama **dentro del gesto de la persona**. */
  readonly resume: () => Promise<void>;
}

/** Detenido: la politica del navegador o una interrupcion del sistema (Safari). */
function estaDetenido(contexto: AudioContext): boolean {
  // `interrupted` es de Safari y todavia no esta en todos los tipos del DOM.
  const estado: string = contexto.state;
  return estado === "suspended" || estado === "interrupted";
}

/**
 * Vigila que el audio de salida corra, y avisa cuando cambia.
 *
 * Solo se publica el cambio. `closed` no cuenta como detenido: es el final de la
 * llamada, no un audio que haya que activar.
 */
export function watchPlayback(
  contexto: AudioContext,
  onBlocked: (blocked: boolean) => void,
): PlaybackWatch {
  let publicado: boolean | null = null;
  let intentando = false;

  const publicar = (): void => {
    const detenido = estaDetenido(contexto);
    if (detenido !== publicado) {
      publicado = detenido;
      onBlocked(detenido);
    }
  };
  // Si algo mas lo reanuda --un toque en otra parte de la pagina-- el aviso se va solo.
  contexto.onstatechange = publicar;

  const reanudar = async (): Promise<void> => {
    await reanudarSinEsperarDeMas(contexto);
    publicar();
  };

  return {
    check: () => {
      if (!estaDetenido(contexto)) {
        publicar();
        return;
      }
      // Un intento a la vez: el audio llega cada 20 ms, y un intento por cada trozo
      // apilaria promesas pendientes en Safari.
      if (intentando) {
        return;
      }
      intentando = true;
      void reanudar().finally(() => {
        intentando = false;
      });
    },
    resume: reanudar,
  };
}

const CLAVE_DEL_MICROFONO = "cautelia.voice.microphone";

/** El microfono que la persona eligio al probarlo, o `null` para el del navegador. */
export function chosenMicrophone(): string | null {
  try {
    return window.localStorage.getItem(CLAVE_DEL_MICROFONO);
  } catch {
    return null;
  }
}

/** Recuerda el microfono elegido; `null` vuelve al del navegador. */
export function chooseMicrophone(deviceId: string | null): void {
  try {
    if (deviceId === null) {
      window.localStorage.removeItem(CLAVE_DEL_MICROFONO);
    } else {
      window.localStorage.setItem(CLAVE_DEL_MICROFONO, deviceId);
    }
  } catch {
    // Sin almacenamiento se usa el del navegador: no es un error.
  }
}

/** La ruta del procesador de captura: la prueba del microfono usa la misma. */
export const CAPTURE_WORKLET = CAPTURA;

/** Una llamada viva: el microfono tomado, el socket abierto y los dos nodos. */
/**
 * Arranca la llamada con el microfono ya concedido.
 *
 * Es una funcion suelta y no un metodo estatico: un estatico referenciado sin
 * ligar --que es como lo recibe la pantalla-- arrastra el `this` de la clase, y
 * la regla del linter que lo marca tiene razon. Ademas, una funcion se sustituye
 * en una prueba sin tener que fingir una clase entera.
 */
export function startCall(options: StartOptions): Promise<CallTransport> {
  return CallTransport.crear(options);
}

export class CallTransport {
  private readonly contexto: AudioContext;
  private readonly stream: MediaStream;
  private readonly socket: WebSocket;
  private readonly reproduccion: AudioWorkletNode;
  private readonly vigilante: PlaybackWatch;
  private cerrado = false;

  private constructor(
    contexto: AudioContext,
    stream: MediaStream,
    socket: WebSocket,
    reproduccion: AudioWorkletNode,
    vigilante: PlaybackWatch,
  ) {
    this.contexto = contexto;
    this.stream = stream;
    this.socket = socket;
    this.reproduccion = reproduccion;
    this.vigilante = vigilante;
  }

  static async crear(options: StartOptions): Promise<CallTransport> {
    const stream = options.stream;
    const contexto = new AudioContext({ sampleRate: SAMPLE_RATE });
    // Creado despues de pedir el microfono y abrir la sesion, ya fuera del gesto:
    // Firefox y Safari lo entregan suspendido. Sin reanudarlo, ni la captura ni la
    // reproduccion corren y la llamada no oye ni suena.
    if (contexto.state === "suspended") {
      // Con tope: si el navegador no deja reanudarlo sin un toque, la llamada igual
      // arranca, y el vigilante de abajo avisa a la pantalla para que lo pida.
      await reanudarSinEsperarDeMas(contexto);
    }
    await contexto.audioWorklet.addModule(CAPTURA);
    await contexto.audioWorklet.addModule(REPRODUCCION);

    const vigilante = watchPlayback(contexto, options.handlers.onAudioBlocked ?? (() => undefined));
    const captura = new AudioWorkletNode(contexto, "voice-capture");
    const reproduccion = new AudioWorkletNode(contexto, "voice-playback");
    contexto.createMediaStreamSource(stream).connect(captura);
    reproduccion.connect(contexto.destination);

    const socket = (options.socket ?? ((url) => new WebSocket(url)))(options.socketUrl);
    socket.binaryType = "arraybuffer";

    socket.addEventListener("open", () => {
      // **El primer cuadro, siempre** (BR1.4). El token no viaja en la URL.
      socket.send(JSON.stringify({ type: "auth", token: options.token }));
    });

    socket.addEventListener("message", (evento: MessageEvent<unknown>) => {
      if (evento.data instanceof ArrayBuffer) {
        reproduccion.port.postMessage({ type: "audio", buffer: evento.data }, [evento.data]);
        // Despues de entregar el trozo: vigilar no retrasa el audio.
        vigilante.check();
        return;
      }
      if (typeof evento.data !== "string") {
        return;
      }
      const cuadro = parseFrame(evento.data);
      if (cuadro === null) {
        return;
      }
      if (cuadro.type === "stop_audio") {
        // Antes de avisar a la pantalla: lo que NFR2 mide es esta linea.
        reproduccion.port.postMessage({ type: "flush" });
      }
      options.handlers.onFrame(cuadro);
    });

    socket.addEventListener("close", options.handlers.onClosed);
    socket.addEventListener("error", options.handlers.onClosed);

    captura.port.onmessage = (evento: MessageEvent<{ buffer: ArrayBuffer; level: number }>) => {
      options.handlers.onLevel(evento.data.level);
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(evento.data.buffer);
      }
    };

    // Al conectar: si el navegador entrego el contexto detenido y `resume()` no alcanzo,
    // la persona lo sabe antes de que la agente empiece a hablar sin que se oiga.
    vigilante.check();

    return new CallTransport(contexto, stream, socket, reproduccion, vigilante);
  }

  /**
   * Reactiva el sonido. **Se llama desde el toque de la persona**: es el gesto que
   * Safari y Chrome piden para dejar sonar un audio que arranco solo.
   */
  resumeAudio(): Promise<void> {
    return this.vigilante.resume();
  }

  /**
   * Colgar: el cuadro va primero, para que el servidor cierre el caso bien.
   *
   * **El microfono se suelta ya, el socket no.** Cerrar el socket en el mismo
   * instante que se manda el cuadro le quitaba al servidor el canal por el que
   * contesta `ended`, y la pantalla se quedaba en llamada con el boton de colgar
   * muerto (defecto del 2026-10-07, visto en produccion). El socket lo cierra el
   * servidor al terminar; si no lo hace en `ESPERA_DE_CIERRE_MS`, se cierra aqui.
   */
  hangup(): void {
    for (const pista of this.stream.getTracks()) {
      pista.stop();
    }
    if (this.socket.readyState !== WebSocket.OPEN) {
      this.close();
      return;
    }
    this.socket.send(JSON.stringify({ type: "hangup" }));
    this.reproduccion.port.postMessage({ type: "flush" });
    window.setTimeout(() => {
      this.close();
    }, ESPERA_DE_CIERRE_MS);
  }

  /**
   * La llamada termino por decision del servidor: se suelta el microfono ya y **se
   * deja sonar lo que queda** antes de cerrar el audio (2026-10-10).
   *
   * Lo que queda en la cola es la despedida, con el numero de caso. Cerrar al
   * recibir `ended` la cortaba: la sintesis va mas rapido que la voz, asi que el
   * aviso de fin llega mientras la frase todavia suena. El nodo avisa cuando la
   * cola queda vacia; si no avisa, se cierra igual al pasar el tope.
   */
  finish(): void {
    if (this.cerrado) {
      return;
    }
    for (const pista of this.stream.getTracks()) {
      pista.stop();
    }
    const cerrar = () => {
      this.close();
    };
    const tope = window.setTimeout(cerrar, ESPERA_DE_LA_DESPEDIDA_MS);
    this.reproduccion.port.onmessage = (evento: MessageEvent<{ type?: string }>) => {
      if (evento.data.type === "drained") {
        window.clearTimeout(tope);
        cerrar();
      }
    };
    this.reproduccion.port.postMessage({ type: "drain" });
  }

  /**
   * Suelta todo: el socket, el microfono y el contexto de audio.
   *
   * **La pista del microfono se para explicitamente.** Cerrar el contexto no
   * apaga el indicador de grabacion del navegador, y dejarlo encendido despues de
   * colgar es la clase de cosa que hace desconfiar de una demostracion.
   */
  close(): void {
    if (this.cerrado) {
      return;
    }
    this.cerrado = true;
    this.reproduccion.port.postMessage({ type: "flush" });
    if (this.socket.readyState !== WebSocket.CLOSED) {
      this.socket.close();
    }
    for (const pista of this.stream.getTracks()) {
      pista.stop();
    }
    void this.contexto.close();
  }
}
