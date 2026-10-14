// Los eventos de C-04 tal como llegan por el flujo, y como se convierten en lo
// que la pantalla dibuja.
//
// Vive aparte de la pantalla a proposito: es logica pura --un evento y un estado
// entran, un estado sale-- y se prueba sin montar nada. Lo que la pantalla hace
// con el resultado (dibujarlo, anunciarlo, desplazarse) es otro archivo.
//
// **La espera, la derivacion y el error viajan con su clave y con su texto.** El
// catalogo de este lado resuelve la clave cuando la conoce --una frase resuelta en
// los dos lados acaba diciendose de dos maneras--; el texto del servidor, en el idioma
// del turno, es el respaldo para una clave que esta pantalla no conoce, que antes se
// leia como "tuve un problema para responder eso" (2026-10-12).

import type { CopyKey } from "../../shared/copy/copy-keys";
import type { Locale } from "../../shared/copy/copy-keys";
import { isKnownKey } from "./chat-copy";
import { restore } from "./own-text";

/** Una cita ya completa, como el servidor la pone en el cable (C-04). */
export interface WireCitation {
  readonly clause_id: string;
  readonly clause_version: string;
  readonly part: string;
  readonly text: string;
  readonly clause_language: Locale;
  readonly amount_deferred: boolean;
  readonly trace_ref: string;
  /** La traduccion de referencia, cuando la clausula esta en otro idioma (2026-10-08). */
  readonly translated_text?: string | null;
  readonly translated_part?: string | null;
  /** De que condicion especial (endoso) es la clausula, si es de una (2026-10-11). */
  readonly special_condition_number?: number | null;
}

export type WireEvent =
  | {
      readonly kind: "turn.partial";
      readonly message_id: string;
      readonly seq: number;
      readonly text: string;
    }
  | {
      readonly kind: "turn.final";
      readonly message_id: string;
      readonly text: string;
      readonly language: Locale;
      readonly case_id: string | null;
      readonly citations: readonly WireCitation[];
      /** Los botones de respuesta rapida que el servidor eligio (fase 0). */
      readonly suggestions?: readonly string[];
      /**
       * Cuando es una respuesta de cobertura, su resultado (fase 1): `verified`,
       * `no_clause_found`, `unverifiable` o `rejected`. Lo lee la comparacion.
       */
      readonly coverage_outcome?: string | null;
      /** La traza del turno, con o sin citas (2026-10-09). */
      readonly trace_ref?: string | null;
      /**
       * El turno dijo "dejame revisar" y el fondo va a traer la respuesta (2026-10-12): la
       * pantalla muestra que se esta revisando hasta que llegue otra cosa.
       */
      readonly answer_pending?: boolean;
    }
  | {
      readonly kind: "turn.waiting";
      readonly copy_key: string;
      /** La frase ya resuelta en el idioma del turno, por si la clave no se conoce. */
      readonly text?: string;
    }
  | {
      readonly kind: "turn.handoff";
      readonly reason_code: string;
      readonly copy_key: string;
      readonly text?: string;
      readonly case_id: string | null;
      readonly case_link: string | null;
    }
  | {
      readonly kind: "turn.error";
      readonly code: string;
      readonly copy_key: string;
      readonly text?: string;
    };

export type Speaker = "visitor" | "agent";

/** Un mensaje de la conversacion, ya listo para dibujar. */
export interface Message {
  readonly id: string;
  readonly speaker: Speaker;
  /** El texto ya resuelto, o `null` cuando lo que llego fue una clave. */
  readonly text: string | null;
  /** La clave del catalogo, cuando el texto se resuelve de este lado. */
  readonly copyKey: CopyKey | null;
  readonly citations: readonly WireCitation[];
  readonly traceRef: string | null;
  /** La espera se reemplaza en cuanto llega la respuesta: no es un mensaje mas. */
  readonly transient: boolean;
  /** Los botones de respuesta rapida de este mensaje; solo se ven en el ultimo. */
  readonly suggestions: readonly string[];
}

export interface Conversation {
  readonly messages: readonly Message[];
  /** El idioma en que la agente esta respondiendo, cuando ya lo dijo. */
  readonly answeringIn: Locale | null;
  /** Falso mientras se espera la respuesta de un turno. */
  readonly idle: boolean;
  /**
   * Cierto mientras el fondo revisa la poliza y la respuesta no llega (2026-10-12): desde
   * un final que dice `answer_pending` hasta el siguiente final, derivacion o error.
   */
  readonly reviewing: boolean;
}

export const EMPTY: Conversation = {
  messages: [],
  answeringIn: null,
  idle: true,
  reviewing: false,
};

/** Lo que el servidor guardo de esta conversacion, como lo devuelve su ruta de historial. */
export interface StoredHistory {
  readonly opening: {
    readonly message_id: string;
    readonly text: string;
    readonly language: Locale;
    readonly suggestions?: readonly string[];
  } | null;
  readonly turns: readonly {
    readonly turn_id: string;
    readonly speaker: Speaker;
    readonly text: string;
    readonly language: Locale;
    /** Las clausulas de una respuesta de cobertura, para que vuelvan con ella. */
    readonly citations?: readonly Omit<WireCitation, "trace_ref">[];
  }[];
}

/**
 * La conversacion como estaba, puesta **delante** de lo que la pantalla ya tenga.
 *
 * Lo recuperado va primero porque paso antes; lo que llego por el flujo mientras
 * el historial venia de camino --un aviso de fondo, una respuesta-- se conserva
 * detras. Un mensaje que este en los dos lados se queda una sola vez, en su sitio
 * del historial: la apertura viaja con el mismo identificador por las dos puertas
 * y sin esto se leeria dos veces.
 */
export function withHistory(
  state: Conversation,
  history: StoredHistory,
  ownTexts: readonly string[] = [],
  agentTexts: readonly string[] = [],
): Conversation {
  const propios = restoredTexts(history, ownTexts, agentTexts);
  const recuperados: Message[] = [
    ...(history.opening === null
      ? []
      : [
          {
            id: history.opening.message_id,
            speaker: "agent" as const,
            text: history.opening.text,
            copyKey: null,
            citations: [],
            traceRef: null,
            transient: false,
            suggestions: history.opening.suggestions ?? [],
          },
        ]),
    ...history.turns.map((turno) => ({
      id: turno.turn_id,
      speaker: turno.speaker,
      text: propios.get(turno.turn_id) ?? turno.text,
      copyKey: null,
      // Al volver al chat, la respuesta de cobertura trae otra vez sus tarjetas.
      citations: (turno.citations ?? []).map((cita) => ({ ...cita, trace_ref: "" })),
      traceRef: null,
      transient: false,
      suggestions: [],
    })),
  ];
  const vistos = new Set(recuperados.map((mensaje) => mensaje.id));
  // `answeringIn` no se toca: dice en que idioma responde la agente **ahora**, y lo
  // recuperado es pasado. Mientras no haya respuesta nueva, el subtitulo muestra
  // el numero del caso, que es lo util al volver.
  return {
    ...state,
    messages: [...recuperados, ...state.messages.filter((mensaje) => !vistos.has(mensaje.id))],
  };
}

/**
 * Lo que la persona escribio, puesto de vuelta en sus mensajes tapados (fase 0).
 *
 * Se recorre del ultimo al primero porque lo guardado en esta pestana es lo mas
 * reciente: el historial puede traer mensajes de antes que esta pestana nunca vio.
 */
function restoredTexts(
  history: StoredHistory,
  ownTexts: readonly string[],
  agentTexts: readonly string[],
): Map<string, string> {
  const usados = new Set<number>();
  const usadosDeLaAgente = new Set<number>();
  const propios = new Map<string, string>();
  for (const turno of [...history.turns].reverse()) {
    const propio =
      turno.speaker === "visitor"
        ? restore(turno.text, ownTexts, usados)
        : restore(turno.text, agentTexts, usadosDeLaAgente);
    if (propio !== null) {
      propios.set(turno.turn_id, propio);
    }
  }
  return propios;
}

/**
 * Como se dice la frase de un evento que viaja con su clave: con el catalogo de esta
 * pantalla si conoce la clave, y con el texto del servidor si no. Sin texto, la clave
 * desconocida cae en la frase de error (`phraseFor`).
 */
function phraseOf(event: {
  readonly copy_key: string;
  readonly text?: string;
}): Pick<Message, "text" | "copyKey"> {
  if (!isKnownKey(event.copy_key) && event.text !== undefined && event.text !== "") {
    return { text: event.text, copyKey: null };
  }
  return { text: null, copyKey: event.copy_key as CopyKey };
}

function sinTransitorios(messages: readonly Message[]): Message[] {
  return messages.filter((mensaje) => !mensaje.transient);
}

/** Lo que el visitante acaba de escribir, puesto en la conversacion. */
export function withVisitorMessage(state: Conversation, id: string, text: string): Conversation {
  return {
    ...state,
    idle: false,
    messages: [
      ...sinTransitorios(state.messages),
      {
        id,
        speaker: "visitor",
        text,
        copyKey: null,
        citations: [],
        traceRef: null,
        transient: false,
        suggestions: [],
      },
    ],
  };
}

/**
 * El estado despues de un evento del flujo.
 *
 * Los fragmentos se acumulan por `message_id`, que es para lo que `seq` existe:
 * sin el, dos fragmentos que lleguen fuera de orden dejarian la frase al reves.
 */
export function reduce(state: Conversation, event: WireEvent): Conversation {
  switch (event.kind) {
    case "turn.partial": {
      const previos = sinTransitorios(state.messages);
      const existente = previos.find((mensaje) => mensaje.id === event.message_id);
      if (existente === undefined) {
        return {
          ...state,
          idle: false,
          messages: [
            ...previos,
            {
              id: event.message_id,
              speaker: "agent",
              text: event.text,
              copyKey: null,
              citations: [],
              traceRef: null,
              transient: false,
              suggestions: [],
            },
          ],
        };
      }
      return {
        ...state,
        idle: false,
        messages: previos.map((mensaje) =>
          mensaje.id === event.message_id
            ? { ...mensaje, text: `${mensaje.text ?? ""}${event.text}` }
            : mensaje,
        ),
      };
    }
    case "turn.final": {
      const previos = sinTransitorios(state.messages).filter(
        (mensaje) => mensaje.id !== event.message_id,
      );
      const traceRef = event.trace_ref ?? event.citations[0]?.trace_ref ?? null;
      return {
        answeringIn: event.language,
        idle: true,
        reviewing: event.answer_pending === true,
        messages: [
          ...previos,
          {
            id: event.message_id,
            speaker: "agent",
            text: event.text,
            copyKey: null,
            citations: event.citations,
            traceRef: traceRef === "" ? null : traceRef,
            transient: false,
            suggestions: event.suggestions ?? [],
          },
        ],
      };
    }
    case "turn.waiting":
      // Transitoria: la reemplaza la respuesta. Dejarla en la conversacion
      // dejaria "un momento" escrito para siempre debajo de la respuesta.
      return {
        ...state,
        idle: false,
        messages: [
          ...sinTransitorios(state.messages),
          {
            id: `waiting-${String(state.messages.length)}`,
            speaker: "agent",
            ...phraseOf(event),
            citations: [],
            traceRef: null,
            transient: true,
            suggestions: [],
          },
        ],
      };
    case "turn.handoff":
    case "turn.error":
      return {
        ...state,
        idle: true,
        reviewing: false,
        messages: [
          ...sinTransitorios(state.messages),
          {
            id: `${event.kind}-${String(state.messages.length)}`,
            speaker: "agent",
            ...phraseOf(event),
            citations: [],
            traceRef: null,
            transient: false,
            suggestions: [],
          },
        ],
      };
  }
}
