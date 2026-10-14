// La consola de llamada de una aseguradora (U16, F8).
//
// Una pantalla donde no se escribe nada: dos gestos --llamar y colgar-- y todo lo
// demas es ver en que esta la llamada y leer lo que se esta diciendo.
//
// Es tambien la pantalla mas dificil de hacer honesta, porque una llamada tiene
// estados que no se ven: el microfono puede estar tomado y la agente sin oir, la
// red puede estar retrasando el audio, la sintesis puede haberse detenido. La
// regla de esta consola es que **cada uno de esos estados tiene su forma en
// pantalla**.
//
// **Ningun texto se escribe aqui.** Todo sale del catalogo, incluidos los avisos
// y el motivo del final: el servidor manda su clave y esta pantalla la resuelve.
//
// **Y no se redacta nada.** Lo que llega por el socket ya viene redactado
// (BR7.2); redactar de este lado daria dos implementaciones de la misma regla, de
// las cuales una se quedaria atras.

import { PhoneCallIcon, PhoneDisconnectIcon } from "@phosphor-icons/react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import {
  availability,
  callOutcome,
  handOffCase,
  openCall,
  voiceSocketUrl,
  type Availability,
  type CallOutcome,
} from "../../shared/api-client/voice";
import { useLocale } from "../../shared/i18n/locale-provider";
import type { Translate } from "../../shared/i18n/translate";
import { startBoundedReread } from "../../shared/polling/bounded-reread";
import { useAgentName } from "../../shared/site/agent-name";
import { useAnnouncer } from "../../shared/ui/announcer";
import { Button } from "../../shared/ui/button";
import { cn } from "../../shared/ui/cn";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { isUnderReview } from "../inbox/inbox-labels";
import { callMemory } from "./call-memory";
import { MicCheck } from "./mic-check";
import { SamplePolicyHelper } from "./sample-policy-helper";
import { endedPhrase, phraseFor, reasonKeyFor } from "./voice-copy";
import { EMPTY, reduce, type Call, type WireFrame } from "./voice-events";
import {
  CallTransport,
  MicrophoneDeniedError,
  requestMicrophone,
  startCall,
} from "./voice-transport";

/**
 * En que esta la pantalla, que no es lo mismo que en que esta la llamada.
 *
 * Arranca en `checking`: **el boton no hace nada hasta saber si hay voz** (BR3.1).
 * Pedir el microfono para despues decir que no hay es la peor pantalla posible.
 */
type Phase = "checking" | "idle" | "starting" | "live" | "mic_denied" | "unavailable" | "failed";

/**
 * Si al colgar el caso sigue en revision (la agente aun evalua), el desenlace se vuelve a
 * pedir cada 2 s y, como mucho, 8 veces (2026-10-13): lo que tarda la evaluacion con holgura,
 * y ni una lectura mas.
 */
const OUTCOME_REREAD_MS = 2000;
const OUTCOME_REREAD_MAX = 8;

export interface VoicePageProps {
  readonly tenantId: string;
  /** El nombre de la aseguradora, para el titulo. */
  readonly insurerLabel: string;
  /** La poliza de ejemplo de la aseguradora, del directorio del sitio. Sin ella no se dibuja. */
  readonly examplePolicy?: string | undefined;
  /** El titular de esa poliza, si se conoce: lo trae la lista de polizas, no el directorio. */
  readonly exampleHolder?: string | undefined;
  /** A donde lleva la oferta de usar el chat cuando no hay microfono. */
  readonly chatHref: string;
  /** Solo para las pruebas: sin esto, el socket de verdad. */
  readonly start?: typeof startCall;
}

/**
 * Lo que se dice de cada estado al terminar (BR3.4). **Tabla cerrada**: un estado
 * nuevo del caso obliga a decidir que se le dice, en vez de caer en silencio.
 *
 * Los tres primeros son los que el final de una llamada puede dejar; los dos de
 * captura se agrupan en "en curso", porque para quien llamo son lo mismo: falta
 * informacion.
 *
 * `verifying` y `deciding` (2026-10-13) son los segundos en que la agente comprueba la
 * poliza y evalua las reglas despues de cerrar la captura: el caso todavia no esta con un
 * ajustador --puede cerrarse solo--, ni le falta informacion. Se dicen con las frases que
 * ya usa la pagina de casos.
 */
function _frasePorEstado(estado: CallOutcome["state"]): (t: Translate) => string {
  switch (estado) {
    case "derived":
      return (t) => t("voice.console.outcome_derived");
    case "verifying":
      return (t) => t("cases.group.verifying");
    case "deciding":
      return (t) => t("cases.group.deciding");
    case "closed":
      return (t) => t("voice.console.outcome_closed");
    case "awaiting_insured":
      return (t) => t("voice.console.outcome_awaiting");
    case "open":
    case "capturing":
      return (t) => t("voice.console.outcome_in_progress");
  }
}

/**
 * El tiempo que queda, como `m:ss`. Los digitos no se traducen: lo que sale del
 * catalogo es la frase que los rodea.
 */
function relojDe(segundos: number): string {
  const minutos = Math.floor(segundos / 60);
  const resto = segundos % 60;
  return `${String(minutos)}:${String(resto).padStart(2, "0")}`;
}

/**
 * La hora de un instante en el idioma de la pantalla y en la zona del navegador, que es
 * donde la lee la persona: el servidor no sabe en que zona esta, asi que da el instante
 * y no la hora escrita.
 */
function horaDe(instante: string, locale: string): string {
  const momento = new Date(instante);
  if (Number.isNaN(momento.getTime())) {
    return instante;
  }
  return new Intl.DateTimeFormat(locale, { timeStyle: "short" }).format(momento);
}

/** Cuanto se escucha sin nivel antes de avisar que el microfono no entra. */
const SIN_AUDIO_TRAS_MS = 6_000;
/**
 * El nivel por debajo del cual un trozo cuenta como silencio absoluto.
 *
 * **Es el silencio digital, no el silencio de la habitacion.** Medido el
 * 2026-10-07 con el microfono de un portatil en un cuarto callado y la
 * supresion de ruido del navegador: seis segundos sin hablar dan un maximo de
 * 0,0013 a 0,0036. Con el umbral anterior, 0,003, el aviso de que el microfono
 * no entraba salia con el microfono funcionando y la persona todavia sin hablar.
 * Un microfono silenciado o un dispositivo muerto entrega ceros exactos.
 */
const NIVEL_MINIMO_AUDIBLE = 0.0003;

export function VoicePage({
  tenantId,
  insurerLabel,
  examplePolicy,
  exampleHolder,
  chatHref,
  start,
}: VoicePageProps) {
  const { t, locale, source } = useLocale();
  const agente = useAgentName(tenantId);
  const [fase, setFase] = useState<Phase>("checking");
  // Lo que dijo la disponibilidad, o `null` mientras no ha llegado o si fallo.
  const [disponibilidad, setDisponibilidad] = useState<Availability | null>(null);
  const [llamada, setLlamada] = useState<Call>(EMPTY);
  const [nivel, setNivel] = useState(0);
  // Si en la llamada no ha entrado nada por el microfono. La llamada del 7 de octubre
  // se cayo por silencio sin que nadie supiera que el audio no salia del navegador.
  // **Se cuenta desde que empieza la llamada, no por cada escucha** (2026-10-09): la
  // agente pregunta "¿Sigues ahi?" antes de seis segundos de silencio, la escucha
  // volvia a empezar y el aviso no alcanzaba a salir nunca (visto con un Mac al que
  // la actualizacion del sistema le quito el permiso del microfono). Se retira en
  // cuanto entra sonido.
  const [sinAudio, setSinAudio] = useState(false);
  // El audio de salida detenido por el navegador (2026-10-11): en iPhone y Safari el
  // contexto de audio puede quedar suspendido hasta que la persona toque la pantalla, y la
  // llamada parece muda. El transporte lo avisa; la pantalla ofrece el boton que lo activa.
  const [sonidoBloqueado, setSonidoBloqueado] = useState(false);
  // Hasta cuando puede retomarse el caso de una llamada que quedo retomable, tal como lo
  // da la disponibilidad al terminar. Nulo mientras no se sepa: sin la hora no se afirma.
  const [retomableHasta, setRetomableHasta] = useState<string | null>(null);
  const nivelMaximo = useRef(0);
  const alNivel = useCallback((valor: number) => {
    setNivel(valor);
    if (valor > nivelMaximo.current) {
      nivelMaximo.current = valor;
    }
    if (valor >= NIVEL_MINIMO_AUDIBLE) {
      setSinAudio(false);
    }
  }, []);
  // Cuando empezo la llamada, para contar lo que queda (BR3.2). Es el reloj del
  // navegador y no pretende ser la medida de nada: el servidor corta la llamada
  // por su cuenta al llegar al limite, y esto es lo que la persona mira para no
  // tener que adivinarlo.
  const [empezoEn, setEmpezoEn] = useState<number | null>(null);
  // El identificador de la llamada, que hace falta al terminar para preguntar
  // donde quedo el caso (BR3.4).
  const [llamadaId, setLlamadaId] = useState<string | null>(null);
  const [desenlace, setDesenlace] = useState<CallOutcome | null>(null);
  // El reloj que hace avanzar la cuenta atras. Se guarda el instante y lo que
  // queda se **deriva** al dibujar: con un estado propio para el numero habria
  // que escribirlo desde el efecto, y eso es una cascada de renderes.
  const [ahora, setAhora] = useState(() => Date.now());
  // La clave del motivo por el que no hay voz, cuando la disponibilidad lo dijo.
  const [sinVoz, setSinVoz] = useState<string | null>(null);
  const transporte = useRef<CallTransport | null>(null);
  // Lo que se dice en la llamada se guarda en este navegador para devolverlo sin tapar en
  // "Ver mi caso" (C5, 2026-10-12). Se arma de nuevo en cada llamada.
  const memoria = useRef(callMemory(tenantId));
  // La columna de la transcripcion: sigue la ultima linea a medida que llega.
  const transcripcion = useRef<HTMLDivElement>(null);
  // La columna de la llamada, para animar su paso de centro a izquierda (FLIP).
  const columnaLlamada = useRef<HTMLDivElement>(null);
  const cajaCentrada = useRef<DOMRect | null>(null);
  const yaPartida = useRef(false);

  // Una llamada abierta se cierra al salir de la pantalla. Sin esto, irse deja el
  // microfono tomado y el socket vivo, y el servidor lo cuenta como un corte que
  // nadie provoco.
  useEffect(
    () => () => {
      transporte.current?.close();
      transporte.current = null;
    },
    [],
  );

  useEffect(() => {
    const columna = transcripcion.current;
    if (columna !== null) {
      columna.scrollTop = columna.scrollHeight;
    }
  }, [llamada.turns, llamada.partial]);

  const { announce } = useAnnouncer();
  // Los cambios de estado se anuncian: es lo que sustituye a ver el medidor para
  // quien no ve la pantalla.
  const estado = llamada.state;
  useEffect(() => {
    if (estado === "listening" || estado === "speaking") {
      announce(estado === "listening" ? t("voice.state.listening") : t("voice.state.speaking"));
    }
  }, [estado, announce, t]);

  // Seis segundos de llamada sin nivel alguno: el microfono no esta entrando. Se mira
  // el **maximo** desde que empezo, no el nivel de ahora: quien habla hace pausas, y
  // una pausa no es un microfono muerto. El efecto va despues de `enLlamada`.

  const alCuadro = useCallback((cuadro: WireFrame) => {
    // **Una llamada terminada no revive.** Tras colgar, el servidor todavia manda
    // lo que tenia en curso --la respuesta al ultimo turno, un "hablando"-- y
    // eso devolvia la pantalla a la llamada con el boton de colgar (visto en
    // produccion el 2026-10-07).
    memoria.current(cuadro);
    setLlamada((previa) => (previa.state === "ended" ? previa : reduce(previa, cuadro)));
    if (cuadro.type === "ended") {
      // No `close()`: la despedida todavia esta sonando, y cerrar el audio aqui
      // cortaba el numero de caso (2026-10-10).
      transporte.current?.finish();
      transporte.current = null;
    }
  }, []);

  async function llamar(): Promise<void> {
    // Sin disponibilidad que diga que si, no se pide nada: ni microfono ni sesion.
    if (disponibilidad?.available !== true) {
      return;
    }
    setFase("starting");
    setLlamada(EMPTY);
    memoria.current = callMemory(tenantId);
    setSinVoz(null);
    // Lo de la llamada anterior no se queda a la vista en la siguiente (2026-10-11): el
    // recuadro de donde quedo su caso, la hora hasta la que se podia retomar y el aviso
    // del sonido.
    setDesenlace(null);
    setLlamadaId(null);
    setRetomableHasta(null);
    setSonidoBloqueado(false);

    // **El microfono primero, y la sesion despues** (BR1.2). Al reves, negarlo
    // dejaria un caso vacio en la bandeja de una ajustadora. El orden lo impone
    // `CallTransport.start`, que pide el microfono antes de nada; aqui se abre la
    // sesion despues de que eso haya salido bien.
    const arrancar = start ?? startCall;
    let microfono: MediaStream;
    try {
      microfono = await requestMicrophone();
    } catch (error) {
      // Negado, con su ayuda para permitirlo; cualquier otra falla del microfono,
      // la frase general de que la llamada no pudo abrirse.
      setFase(error instanceof MicrophoneDeniedError ? "mic_denied" : "failed");
      return;
    }

    // Se manda el idioma **solo si alguien lo eligio** (BR1.1, D5). Con la
    // procedencia `tenant_default` la pestana no eligio nada: adopto el idioma de
    // la aseguradora, y mandarlo seria indistinguible de una eleccion.
    const abierta = await openCall(tenantId, source === "tenant_default" ? undefined : locale);
    if (abierta.outcome !== "opened") {
      for (const pista of microfono.getTracks()) {
        pista.stop();
      }
      if (abierta.outcome === "unavailable") {
        // El motivo que dijo el servidor: un limite diario, el cupo del sitio o el techo
        // de gasto no son "la voz esta apagada".
        setSinVoz(reasonKeyFor(abierta.code));
        setFase("unavailable");
      } else {
        setFase("failed");
      }
      return;
    }

    try {
      transporte.current = await arrancar({
        stream: microfono,
        socketUrl: voiceSocketUrl(abierta.call.transport.url),
        token: abierta.call.transport.token,
        handlers: {
          onFrame: alCuadro,
          onLevel: alNivel,
          onAudioBlocked: setSonidoBloqueado,
          onClosed: () => {
            transporte.current = null;
            // Un socket que se cierra sin `ended` es una llamada que se corto: la
            // pantalla no puede quedarse en llamada con un boton que ya no hace
            // nada (defecto del 2026-10-07).
            setLlamada((previa) =>
              previa.state === "ended"
                ? previa
                : reduce(previa, { type: "ended", reason: "dropped" }),
            );
          },
        },
      });
      setLlamadaId(abierta.call.call_id);
      setEmpezoEn(Date.now());
      setAhora(Date.now());
      setFase("live");
    } catch {
      // El socket no llego a abrirse: se suelta el microfono, porque dejar el
      // indicador de grabacion encendido despues de un fallo es la clase de cosa
      // que hace desconfiar de una demostracion.
      for (const pista of microfono.getTracks()) {
        pista.stop();
      }
      setFase("failed");
    }
  }

  function colgar(): void {
    transporte.current?.hangup();
    // **La pantalla sale de la llamada al pulsar**, sin esperar al servidor: el
    // boton de colgar que no responde es lo peor que puede tener esta pantalla.
    // El `ended` del servidor llega despues y no cambia nada.
    setLlamada((previa) =>
      previa.state === "ended" ? previa : reduce(previa, { type: "ended", reason: "hangup" }),
    );
  }

  useEffect(() => {
    // La disponibilidad se pregunta **antes** de ofrecer el boton activo (BR1.1,
    // BR3.1): ofrecer un boton que va a fallar es peor que no ofrecerlo.
    const resolver = (estado: Availability | null) => {
      setDisponibilidad(estado);
      // **Sin respuesta tampoco hay voz**: no se sabe si cuesta dinero, y entre
      // pedir el microfono a ciegas y decir "ahora no" se elige lo segundo.
      const hayVoz = estado?.available === true;
      if (!hayVoz) {
        setSinVoz(estado?.reason_key ?? null);
      }
      // **Solo si nadie ha cambiado de fase todavia.** La respuesta puede llegar
      // tarde --la red es la red-- y no puede pisar una llamada viva.
      setFase((previa) => (previa === "checking" ? (hayVoz ? "idle" : "unavailable") : previa));
    };
    // **Una peticion que falla es tambien "sin respuesta", y acaba en el mismo
    // sitio.** Sin esto la conducta no era insegura --la fase se quedaba en
    // `checking` y el boton deshabilitado-- pero quien abria la consola se
    // quedaba en "comprobando" para siempre, sin motivo y sin la oferta del chat:
    // peor que una indisponibilidad declarada. Y la promesa sin atrapar deja un
    // error de consola, que es lo que el arnes vigila.
    void availability(tenantId)
      .then(resolver)
      .catch(() => {
        resolver(null);
      });
  }, [tenantId]);

  const enLlamada = fase === "live" && llamada.state !== "ended";
  useEffect(() => {
    if (!enLlamada) {
      return undefined;
    }
    nivelMaximo.current = 0;
    const temporizador = window.setTimeout(() => {
      if (nivelMaximo.current < NIVEL_MINIMO_AUDIBLE) {
        setSinAudio(true);
      }
    }, SIN_AUDIO_TRAS_MS);
    return () => {
      window.clearTimeout(temporizador);
      // La llamada siguiente empieza sin el aviso de esta.
      setSinAudio(false);
    };
  }, [enLlamada]);
  const avisoDelServidor = llamada.notice === null ? null : phraseFor(llamada.notice);
  // Colgar lo hizo la persona: no se le explica. Los demas finales si dicen por que.
  const avisoDelFinal = llamada.endedBy === null ? null : endedPhrase(llamada.endedBy);
  // La llamada en curso o ya terminada: la pantalla se parte en dos columnas en escritorio.
  const dosColumnas = fase === "live";

  // Al empezar la llamada la pantalla pasa de centrada a dos columnas, y ese cambio se
  // anima (2026-10-09): el bloque de la llamada se desliza de donde estaba al centro hasta
  // su lugar a la izquierda y la transcripcion entra desde la derecha. Se mide donde estaba
  // mientras la pantalla esta centrada --es raro que se dibuje, y asi no se mide durante la
  // llamada, que se dibuja muchas veces por segundo-- y al partirse se anima la diferencia.
  // Sin movimiento reducido, o sin soporte, el cambio es instantaneo como antes.
  useLayoutEffect(() => {
    const llamadaEl = columnaLlamada.current;
    if (llamadaEl === null) {
      return;
    }
    if (!dosColumnas) {
      cajaCentrada.current = llamadaEl.getBoundingClientRect();
      yaPartida.current = false;
      return;
    }
    if (yaPartida.current) {
      return;
    }
    yaPartida.current = true;
    const previa = cajaCentrada.current;
    const sinMovimiento =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (previa === null || sinMovimiento || typeof llamadaEl.animate !== "function") {
      return;
    }
    const ahoraEn = llamadaEl.getBoundingClientRect();
    const dx = previa.left - ahoraEn.left;
    const dy = previa.top - ahoraEn.top;
    const opciones = { duration: 380, easing: "cubic-bezier(0.23, 1, 0.32, 1)" } as const;
    if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
      llamadaEl.animate(
        [{ transform: `translate(${String(dx)}px, ${String(dy)}px)` }, { transform: "none" }],
        opciones,
      );
    }
    transcripcion.current?.animate(
      [
        { opacity: 0, transform: "translateX(2rem)" },
        { opacity: 1, transform: "none" },
      ],
      { ...opciones, delay: 100, fill: "backwards" },
    );
  }, [dosColumnas]);
  const frasePorLaQueNoHayVoz = sinVoz === null ? null : phraseFor(sinVoz);
  // Lo que se dice antes de pedir el microfono, solo cuando hay voz y no se esta
  // en la llamada.
  const antesDelMicrofono =
    disponibilidad?.available === true && fase !== "live" && fase !== "unavailable";
  const segundos = disponibilidad?.limits.max_call_seconds ?? 0;

  // El latido de la cuenta atras, un segundo a la vez. Se apaga en cuanto la
  // llamada termina: un cronometro corriendo sobre una llamada acabada dice algo
  // que ya no pasa.
  useEffect(() => {
    if (!enLlamada) {
      return undefined;
    }
    const reloj = setInterval(() => {
      setAhora(Date.now());
    }, 1000);
    return () => {
      clearInterval(reloj);
    };
  }, [enLlamada]);

  // **Al terminar se pregunta donde quedo el caso** (BR3.4), una sola vez. No se
  // pregunta durante la llamada: mientras habla, el caso se esta moviendo, y lo
  // que la persona necesita saber es donde quedo, no donde iba.
  const termino = llamada.endedBy !== null;
  useEffect(() => {
    if (!termino || llamadaId === null) {
      return undefined;
    }
    // La respuesta de una llamada que ya no es la de la pantalla se descarta: si llega
    // despues de pulsar llamar de nuevo, volveria a pintar el recuadro que se acaba de quitar.
    let vigente = true;
    let cancelarRelectura: (() => void) | undefined;
    void callOutcome(tenantId, llamadaId).then((donde) => {
      if (!vigente) {
        return;
      }
      setDesenlace(donde);
      // Colgo antes del resultado (2026-10-13): el caso sigue en revision unos segundos y
      // puede cerrarse solo. Se vuelve a pedir, con tope, con la misma llamada; las
      // relecturas que fallan (`null`) no borran lo que ya se dijo.
      if (donde !== null && isUnderReview(donde.state)) {
        cancelarRelectura = startBoundedReread({
          read: () => callOutcome(tenantId, llamadaId),
          onResult: (nuevo) => {
            if (nuevo !== null) {
              setDesenlace(nuevo);
            }
          },
          keepGoing: (nuevo) => nuevo !== null && isUnderReview(nuevo.state),
          everyMs: OUTCOME_REREAD_MS,
          maxReads: OUTCOME_REREAD_MAX,
        });
      }
    });
    return () => {
      vigente = false;
      cancelarRelectura?.();
    };
  }, [termino, llamadaId, tenantId]);

  // **Hasta cuando se puede retomar** (2026-10-11). "Puedes retomarlo" sin decir hasta
  // cuando obligaba a adivinarlo. La hora es la que el servidor dejo escrita al terminar
  // la llamada y la disponibilidad la devuelve; si no la da --la llamada no quedo
  // retomable, o no se pudo leer-- no se afirma nada.
  const quedoRetomable =
    llamada.endedBy === "dropped" || llamada.endedBy === "error" || llamada.endedBy === "saved";
  useEffect(() => {
    if (!quedoRetomable) {
      return undefined;
    }
    let vigente = true;
    void availability(tenantId)
      .then((estado) => {
        if (vigente) {
          setRetomableHasta(estado?.resume_until ?? null);
        }
      })
      .catch(() => undefined);
    return () => {
      vigente = false;
    };
  }, [quedoRetomable, tenantId]);

  // El aviso del sonido bloqueado se anuncia: es la unica pista para quien no ve la
  // pantalla de que la agente habla y no se oye.
  const avisarSonido = sonidoBloqueado && fase === "live" && llamada.state !== "ended";
  useEffect(() => {
    if (avisarSonido) {
      announce(t("voice.console.audio_blocked"));
    }
  }, [avisarSonido, announce, t]);

  // Lo que queda, derivado: `null` cuando no hay llamada o no se sabe la duracion.
  const restante =
    empezoEn === null || segundos <= 0 || !enLlamada
      ? null
      : Math.max(0, segundos - Math.floor((ahora - empezoEn) / 1000));

  const llamadasAlDia = disponibilidad?.limits.calls_per_visitor_day ?? null;

  return (
    <div
      className={cn(
        "mx-auto flex w-full flex-col gap-6 px-4 py-8 tablet:py-12",
        // Antes de llamar, la pantalla centrada de siempre; con la llamada en curso o
        // terminada, en escritorio la llamada va a la izquierda y la transcripcion a la
        // derecha, y cada columna se desplaza por dentro para que la pagina no crezca.
        dosColumnas
          ? "max-w-6xl desktop:grid desktop:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] desktop:items-start desktop:gap-10 roomy:min-h-0 roomy:flex-1 roomy:grid-rows-[minmax(0,1fr)] roomy:items-stretch roomy:py-6"
          : "max-w-xl roomy:my-auto",
      )}
      data-voice-layout={dosColumnas ? "split" : "centered"}
    >
      <div
        ref={columnaLlamada}
        className={cn(
          "flex flex-col gap-6",
          dosColumnas && "desktop:min-w-0 roomy:min-h-0 roomy:overflow-y-auto roomy:pr-1",
        )}
        data-testid="voice-call-column"
      >
        {/*
        La cabecera, corta y centrada: una marca de llamada, el nombre de la aseguradora
        y una sola frase. Lo que antes se explicaba aqui --datos reales, poliza de
        ejemplo, que probar-- se quito (decision de Miguel, 2026-10-09); lo unico que
        queda son los avisos que la demostracion debe dar antes del microfono.
      */}
        <header className="flex flex-col items-center gap-3 text-center">
          <span
            aria-hidden="true"
            className="flex size-16 items-center justify-center rounded-surface bg-selected text-tenant"
          >
            <PhoneCallIcon size={32} weight="duotone" />
          </span>
          <h1
            className={cn(
              "font-display text-title font-light text-fg tablet:text-figure",
              dosColumnas && "desktop:text-title",
            )}
          >
            {t("voice.console.title", { insurer: insurerLabel })}
          </h1>
          <p className="text-body text-fg-secondary">{t("voice.console.intro")}</p>
        </header>

        {antesDelMicrofono ? (
          <section
            className="flex flex-col items-center gap-2 text-center"
            data-testid="voice-before-call"
          >
            {disponibilidad.voice_mode === "fallback" ? (
              <InlineAlert tone="warning">{t("voice.console.fallback_voice")}</InlineAlert>
            ) : null}
            {/*
            Aqui iba ademas el aviso de "es una demostracion, no digas datos reales":
            Miguel lo quito de esta pantalla el 2026-10-11. Que es una demostracion lo
            dicen el inicio y el pie de pagina; lo que se dice en la llamada se sigue
            tapando antes de guardarse.

            Los dos limites, dichos antes del microfono: lo que dura la llamada y
            cuantas caben al dia **desde esta conexion**. Nunca "por persona": un
            visitante cambia de navegador, asi que este carril no controla el gasto
            y la pantalla no puede insinuar que si (BR1.4). El limite diario se omite
            mientras el servidor no lo sirva: no se promete un limite que nada
            aplica.
          */}
            {/* Dos renglones centrados, nada mas (Miguel, 2026-10-13): los dos limites en
                uno y el idioma en otro. */}
            <ul className="flex flex-wrap justify-center gap-x-1.5 gap-y-1 text-body text-fg-secondary tablet:w-max tablet:flex-nowrap">
              <li>
                {segundos % 60 === 0
                  ? t("voice.console.limit_minutes", { minutes: segundos / 60 })
                  : t("voice.console.limit_seconds", { seconds: segundos })}
              </li>
              {llamadasAlDia === null ? null : (
                <li>{t("voice.console.limit_daily", { count: llamadasAlDia })}</li>
              )}
            </ul>
            {/* El idioma de la llamada es el de la pagina: el que la persona eligio o,
                si no eligio, el de la aseguradora, que es lo que decide `openCall`. */}
            <p className="text-body text-fg-secondary" data-testid="voice-call-language">
              {t("voice.console.call_language")}
            </p>
          </section>
        ) : null}

        {/*
        **Los tres siempre visibles** (BR3.2): el estado, lo que queda y el boton de
        colgar. En reposo es el centro de la pantalla --el boton de llamar es lo unico
        grande--; durante la llamada se pega al borde de abajo, asi que a 360 px sigue
        ahi cuando la transcripcion ya ocupa la pantalla: quien tiene una sola llamada
        al dia y tres minutos necesita ver cuanto le queda sin buscarlo, y colgar no
        puede quedar debajo del pliegue.
      */}
        <section
          className={cn(
            "flex flex-col items-center gap-4",
            // En reposo es solo el boton; con la llamada en curso gana su tarjeta y se pega abajo.
            enLlamada &&
              "sticky bottom-3 z-10 rounded-surface border border-hairline bg-surface p-6 shadow-raised desktop:static",
          )}
          aria-label={t("voice.console.title", { insurer: insurerLabel })}
          data-testid="voice-controls"
        >
          {llamada.lastLatencyMs === null ? null : (
            <p className="text-caption text-fg-secondary" data-testid="voice-latency">
              {t("voice.console.last_latency", { ms: String(llamada.lastLatencyMs) })}
            </p>
          )}
          {restante === null ? null : (
            <p
              className="font-mono text-title text-fg tabular-nums"
              data-testid="voice-time-left"
              aria-label={t("voice.console.time_left_label")}
            >
              {t("voice.console.time_left", { clock: relojDe(restante) })}
            </p>
          )}
          <Button
            type="button"
            variant="tenant"
            size="lg"
            className="w-full max-w-xs"
            loading={fase === "starting"}
            disabled={fase === "checking" || fase === "unavailable"}
            onClick={() => {
              if (enLlamada) {
                colgar();
              } else {
                void llamar();
              }
            }}
          >
            {enLlamada ? (
              <PhoneDisconnectIcon aria-hidden="true" focusable="false" size={24} />
            ) : (
              <PhoneCallIcon aria-hidden="true" focusable="false" size={24} />
            )}
            {enLlamada ? t("voice.console.hangup") : t("voice.console.call")}
          </Button>

          {/*
          El estado en palabras. `role="status"` y no solo color: el estado es la
          unica pista de que el microfono entra, y quien no ve la pantalla se queda
          sin ella si vive en un tinte.
        */}
          <p role="status" className="text-small text-fg-secondary" data-testid="voice-state">
            {fase === "checking"
              ? t("voice.console.checking")
              : fase === "starting"
                ? t("voice.console.connecting")
                : llamada.state === "listening"
                  ? t("voice.state.listening")
                  : llamada.state === "speaking"
                    ? t("voice.state.speaking")
                    : llamada.state === "ended"
                      ? t("voice.state.ended")
                      : ""}
          </p>

          {/*
          El medidor de nivel. Es **decorativo y esta oculto** para el lector de
          pantalla: lo que informa de verdad es el estado de arriba, que si se
          anuncia. El numero sale de las mismas muestras que ya se estan mandando
          --no pide nada al servidor y no es telemetria-- y existe porque sin el,
          quien tiene el microfono silenciado por el sistema habla dos minutos
          contra una pared.
        */}
          {enLlamada ? (
            <div aria-hidden="true" className="h-1.5 w-full max-w-xs rounded-pill bg-surface-alt">
              <div
                className="h-1.5 rounded-pill bg-tenant transition-[width] duration-100"
                style={{ width: `${String(Math.min(100, Math.round(nivel * 400)))}%` }}
                data-testid="voice-level"
              />
            </div>
          ) : null}
          {sinAudio && enLlamada ? (
            <InlineAlert tone="warning">
              <span data-testid="voice-no-audio">{t("voice.console.no_audio")}</span>
            </InlineAlert>
          ) : null}
          {sonidoBloqueado && enLlamada ? (
            <InlineAlert
              tone="warning"
              data-testid="voice-audio-blocked"
              action={
                <Button
                  type="button"
                  variant="secondary"
                  size="compact"
                  onClick={() => {
                    // El toque es el gesto que el navegador pide para dejar sonar el audio.
                    void transporte.current?.resumeAudio();
                  }}
                >
                  {t("voice.console.audio_enable")}
                </Button>
              }
            >
              {t("voice.console.audio_blocked")}
            </InlineAlert>
          ) : null}
        </section>

        {/* Las dos ayudas de antes de llamar, con el mismo boton, una bajo la otra y al
            centro: la poliza de ejemplo para decirla cuando la agente la pida --tambien
            durante la llamada-- y probar el microfono sin llamar (gratis, por el mismo
            camino de audio que la llamada, con la opcion de elegir otro microfono). */}
        <div className="flex flex-col items-center gap-3" data-testid="voice-helpers">
          {examplePolicy === undefined || fase === "unavailable" ? null : (
            <SamplePolicyHelper policy={examplePolicy} holder={exampleHolder} />
          )}
          {fase === "live" || fase === "unavailable" || fase === "checking" ? null : <MicCheck />}
        </div>

        {fase === "mic_denied" ? (
          <InlineAlert tone="warning">
            <div className="flex flex-col gap-2">
              <p>{t("voice.console.mic_denied")}</p>
              <p>{t("voice.console.mic_help")}</p>
              <a href={chatHref} className="underline">
                {t("voice.console.use_chat")}
              </a>
            </div>
          </InlineAlert>
        ) : null}

        {fase === "unavailable" || fase === "failed" ? (
          <InlineAlert tone="warning">
            <div className="flex flex-col gap-2">
              {/* La frase general solo cuando no se sabe mas: con un motivo cerrado, la
                  frase del motivo lo dice todo, y decir ademas "la voz esta apagada" era
                  decir algo falso ante un limite diario (2026-10-11). */}
              <p>
                {frasePorLaQueNoHayVoz === null
                  ? t("voice.console.unavailable")
                  : frasePorLaQueNoHayVoz(t)}
              </p>
              <a href={chatHref} className="underline">
                {t("voice.console.use_chat")}
              </a>
            </div>
          </InlineAlert>
        ) : null}

        {avisoDelServidor === null ? null : (
          <InlineAlert tone="info">{avisoDelServidor(t)}</InlineAlert>
        )}

        {avisoDelFinal === null ? null : (
          <InlineAlert tone="info">
            <p>{avisoDelFinal(t)}</p>
            {quedoRetomable && retomableHasta !== null ? (
              <p data-testid="voice-resume-until">
                {t("voice.ended.resume_until", { time: horaDe(retomableHasta, locale) })}
              </p>
            ) : null}
          </InlineAlert>
        )}

        {/*
        **Donde quedo el caso** (BR3.4). El numero y el estado, y una salida: el
        enlace cuando hay algo que abrir, y cuando el caso quedo esperando datos,
        la de pasarlo ya a una persona. Un caso que espera y no ofrece salida deja
        a quien llamo sin saber que hacer.
      */}
        {desenlace === null ? null : (
          <section
            className="flex flex-col gap-2 rounded-surface border border-hairline bg-surface p-4"
            aria-labelledby="voice-outcome"
            data-testid="voice-outcome"
          >
            <h2 id="voice-outcome" className="text-title font-medium text-fg">
              {t("voice.console.outcome_title")}
            </h2>
            <p className="text-fg-secondary">{_frasePorEstado(desenlace.state)(t)}</p>
            {desenlace.case_link === null || desenlace.case_link === undefined ? null : (
              <Button asChild variant="secondary" size="compact" className="gap-1.5 self-start">
                <a href={desenlace.case_link}>{t("voice.console.outcome_open_case")}</a>
              </Button>
            )}
            {desenlace.state === "awaiting_insured" ? (
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  if (llamadaId === null) {
                    return;
                  }
                  void handOffCase(tenantId, llamadaId).then((donde) => {
                    // Si no se pudo, la salida sigue ofrecida: decir que ya esta
                    // hecha cuando no lo esta es peor que dejar el boton.
                    if (donde !== null) {
                      setDesenlace(donde);
                    }
                  });
                }}
              >
                {t("voice.console.outcome_hand_off")}
              </Button>
            ) : null}
            {/* El numero, al final y en un renglon pequeno que dice para que sirve (C10,
                2026-10-12): ya no es el titular de nada. */}
            <p className="text-caption text-fg-secondary" data-testid="voice-outcome-number">
              {t("voice.console.outcome_number", { number: desenlace.case_number })}
            </p>
            {/* Solo cuando el servidor dice que el chat va a poder retomarlo (US1.20): la
                aseguradora tiene encendida la continuidad y el caso sigue en captura. */}
            {desenlace.chat_continuation === true ? (
              <p className="text-caption text-fg-secondary" data-testid="voice-outcome-chat">
                {t("voice.console.outcome_chat")}
              </p>
            ) : null}
          </section>
        )}
      </div>

      <div
        ref={transcripcion}
        className={cn(
          "flex flex-col gap-3",
          !dosColumnas && "hidden",
          dosColumnas &&
            "desktop:min-w-0 desktop:rounded-surface desktop:border desktop:border-hairline desktop:bg-surface desktop:p-6 roomy:min-h-0 roomy:overflow-y-auto",
        )}
        data-testid="voice-transcript-column"
      >
        {/*
        La transcripcion en vivo: el equivalente textual de la llamada, que es lo
        que hace que esta pantalla se pueda usar sin oir nada. Zona en vivo
        **cortes**: interrumpir al lector de pantalla en cada palabra haria la
        llamada imposible de seguir.
      */}
        <ol
          aria-label={t("voice.console.transcript_label")}
          aria-live="polite"
          className="flex flex-col gap-5"
          data-testid="voice-transcript"
        >
          {llamada.turns.map((turno) => (
            <li key={turno.id} className="flex flex-col gap-1">
              <p className="text-caption text-fg-secondary">
                {turno.speaker === "insured" ? t("voice.console.speaker_insured") : agente}
                {turno.interrupted ? ` · ${t("voice.console.interrupted")}` : ""}
              </p>
              <p className="whitespace-pre-line">{turno.text}</p>
            </li>
          ))}
        </ol>

        {/*
        Lo que se esta diciendo ahora, en gris y **fuera de la lista**: un parcial
        se sustituye por su final y no se acumula. Fuera del `ol` porque esa lista
        solo admite `li` como hijo, que es el mismo detalle que el arnes de
        accesibilidad le encontro al chat.
      */}
        {llamada.partial === null ? null : (
          <p className="text-fg-secondary italic" data-testid="voice-partial">
            {llamada.partial.text}
          </p>
        )}
      </div>
    </div>
  );
}
