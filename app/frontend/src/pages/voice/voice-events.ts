// Los cuadros de C-29 tal como llegan por el socket, y como se convierten en lo
// que la consola dibuja.
//
// Vive aparte de la pantalla a proposito, igual que `chat-events.ts`: es logica
// pura --un cuadro y un estado entran, un estado sale-- y se prueba sin montar
// nada ni abrir un socket. Lo que la pantalla hace con el resultado --dibujarlo,
// anunciarlo, vaciar la cola de audio-- es otro archivo.
//
// **El audio no pasa por aqui.** Viaja en cuadros binarios y lo consume el nodo
// de reproduccion; lo que este reductor ve son los cuadros de texto, que son los
// que cambian lo que se ve.
//
// **Aqui no se redacta ni se destapa nada.** La transcripcion llega del servidor tal
// como la persona la dijo y la oyo, sin etiquetas: es su propia pantalla (decisiones de
// Miguel del 2026-10-09 y del 2026-10-13, que cambian BR7.2), y la base guarda tapado
// aparte. Lo unico que hace esta pantalla con el texto es pintarlo, y `call-memory.ts`
// guardarlo para que "Ver mi caso" lo devuelva.

import type { CopyKey } from "../../shared/copy/copy-keys";

/** Los cinco estados que la consola dibuja. Tres son de la llamada y dos de la
 * conversacion: `listening` y `speaking` no se guardan en ninguna tabla, viajan
 * para que esta pantalla los pueda mostrar. */
export type CallStateValue = "connecting" | "live" | "listening" | "speaking" | "ended";

/** Por que termino una llamada (BR1.6). El mismo conjunto cerrado del servidor:
 * un motivo que la consola no supiera decir dejaria la peor pantalla posible,
 * que es una llamada que se corta sin explicar por que. */
export type EndReason =
  | "hangup"
  | "silence"
  | "max_duration"
  | "dropped"
  | "error"
  | "completed"
  | "handed_off"
  | "saved";

export type Speaker = "insured" | "agent";

/** Un cuadro de texto del servidor (C-29). Union cerrada, como del otro lado. */
export type WireFrame =
  | { readonly type: "state"; readonly value: CallStateValue }
  | {
      readonly type: "transcript";
      readonly speaker: Speaker;
      readonly text: string;
      readonly final: boolean;
    }
  | { readonly type: "stop_audio" }
  | { readonly type: "case"; readonly case_id: string; readonly case_number: string }
  | { readonly type: "notice"; readonly copy_key: string }
  | {
      readonly type: "latency";
      readonly turn_id: string;
      /** Desde el ultimo transcrito final: la definicion de la meta. */
      readonly elapsed_ms: number;
      /**
       * Desde la ultima palabra que la persona dijo, que es lo que vive (2026-10-12).
       * Opcional: el servidor no la manda si no pudo calcularla.
       */
      readonly from_last_word_ms?: number | null;
    }
  | { readonly type: "ended"; readonly reason: EndReason };

/** Algo que ya se dijo, listo para dibujar. */
export interface Turn {
  readonly id: string;
  readonly speaker: Speaker;
  readonly text: string;
  /** La agente se quedo a mitad porque la interrumpieron (BR4.3).
   *
   * Se marca porque verlo importa: sin marca, quien prueba la demostracion no
   * distingue "la interrumpi" de "se cayo el audio". */
  readonly interrupted: boolean;
}

/** Lo que se esta diciendo ahora mismo. Se pinta en gris y **no** entra al
 * historial: un parcial se sustituye por su final, no se acumula. */
export interface Partial {
  readonly speaker: Speaker;
  readonly text: string;
}

export interface Call {
  readonly state: CallStateValue;
  readonly turns: readonly Turn[];
  readonly partial: Partial | null;
  /** El numero de caso, cuando el servidor lo ato. */
  readonly caseNumber: string | null;
  /** La clave de la ultima cosa que la consola tiene que decir, sin resolver. */
  readonly notice: CopyKey | null;
  /** El motivo del final. Nulo mientras la llamada vive. */
  readonly endedBy: EndReason | null;
  /**
   * Lo que tardo la respuesta del ultimo turno, tal como el servidor lo midio
   * (BR3.3). **No se calcula de este lado**: la cifra es la misma que quedo en la
   * traza, y medirla aqui daria dos numeros con el mismo nombre que un dia no
   * coinciden.
   *
   * Es una sola cifra: la contada desde la ultima palabra de la persona cuando el
   * servidor la manda --es la que vive-- y, si no, la de siempre.
   */
  readonly lastLatencyMs: number | null;
  /** Cuantos turnos van, para dar identificadores estables sin reloj. */
  readonly counter: number;
}

export const EMPTY: Call = {
  state: "connecting",
  turns: [],
  partial: null,
  caseNumber: null,
  notice: null,
  endedBy: null,
  lastLatencyMs: null,
  counter: 0,
};

/** Dos trozos de lo que dijo la persona, como una sola frase. */
function unir(antes: string, despues: string): string {
  const resto = despues.trim();
  return resto === "" ? antes : `${antes.trimEnd()} ${resto}`;
}

function conTurno(state: Call, speaker: Speaker, text: string): Call {
  const ultimo = state.turns.at(-1);
  // **La persona dicta de corrido** (pedido de Miguel, 2026-10-15): una pausa corta hace
  // que el reconocedor cierre un final y empiece otro, y cada uno salia con su nombre
  // encima como si fuera otro mensaje. Mientras la agente no hable en medio, es la misma
  // intervencion. La agente no se junta: sus lineas seguidas son frases distintas.
  if (speaker === "insured" && ultimo?.speaker === "insured") {
    return {
      ...state,
      partial: null,
      turns: [...state.turns.slice(0, -1), { ...ultimo, text: unir(ultimo.text, text) }],
    };
  }
  return {
    ...state,
    counter: state.counter + 1,
    partial: null,
    turns: [
      ...state.turns,
      { id: `turn-${String(state.counter + 1)}`, speaker, text, interrupted: false },
    ],
  };
}

function marcarInterrumpido(turns: readonly Turn[]): readonly Turn[] {
  // **El ultimo de la agente**, no el ultimo a secas: cuando la interrupcion
  // llega, lo que la persona dijo para interrumpir ya puede estar pintado
  // delante. Marcar el ultimo sin mas pondria la marca en la linea equivocada.
  const indice = turns.findLastIndex((turno) => turno.speaker === "agent");
  if (indice === -1) {
    return turns;
  }
  return turns.map((turno, i) => (i === indice ? { ...turno, interrupted: true } : turno));
}

/** El estado de la consola despues de un cuadro. Cada tipo tiene su rama. */
export function reduce(state: Call, frame: WireFrame): Call {
  switch (frame.type) {
    case "state":
      return { ...state, state: frame.value };
    case "transcript":
      return frame.final
        ? conTurno(state, frame.speaker, frame.text)
        : { ...state, partial: { speaker: frame.speaker, text: frame.text } };
    case "stop_audio":
      return { ...state, turns: marcarInterrumpido(state.turns) };
    case "case":
      return { ...state, caseNumber: frame.case_number };
    case "notice":
      return { ...state, notice: frame.copy_key as CopyKey };
    case "latency":
      return { ...state, lastLatencyMs: frame.from_last_word_ms ?? frame.elapsed_ms };
    case "ended":
      // El estado se fija aqui y no se espera a un `state` posterior: el
      // servidor cierra el socket justo despues, y una consola que siguiera
      // diciendo "escuchando" sobre una llamada terminada estaria mintiendo.
      return { ...state, state: "ended", endedBy: frame.reason, partial: null };
  }
}

/** Lo que llego por el socket, si es un cuadro que este protocolo conoce.
 *
 * Un cuadro desconocido se **descarta** y no rompe la pantalla: del lado del
 * servidor la union cerrada es lo que obliga a cubrir todas las ramas, y de este
 * lado lo que hay es un navegador que puede estar una version por detras. Lo que
 * no se hace es adivinar que significaba. */
export function parseFrame(raw: string): WireFrame | null {
  let cuerpo: unknown;
  try {
    cuerpo = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof cuerpo !== "object" || cuerpo === null || !("type" in cuerpo)) {
    return null;
  }
  const { type: tipo } = cuerpo;
  const conocidos = ["state", "transcript", "stop_audio", "case", "notice", "latency", "ended"];
  return typeof tipo === "string" && conocidos.includes(tipo) ? (cuerpo as WireFrame) : null;
}
