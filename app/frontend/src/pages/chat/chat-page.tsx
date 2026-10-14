// La pantalla del chat publico de una aseguradora (U13, F8).
//
// **El mensaje sale por una puerta y la respuesta entra por otra.** El envio es un
// `POST` que vuelve en cuanto se admite; lo que la agente dice llega por el flujo
// que la pestana ya tiene abierto. Es la forma de C-04, y la razon es que un turno
// puede tardar: esperar la respuesta con la conexion del envio colgada dejaria la
// pantalla sin poder decir siquiera "un momento".
//
// **Ningun texto se escribe aqui.** Todo sale del catalogo, incluidas las frases
// de espera, de derivacion, de error y de limite: el servidor manda su clave y
// esta pantalla la resuelve. Una frase resuelta en los dos lados acaba diciendose
// de dos maneras.
//
// **La forma, desde el 2026-10-06 (decision de Miguel).** Una ventana que llena la
// vista con la conversacion desplazandose por dentro, no una pagina que crece con
// cada turno; la agente firma con su nombre y no con "la agente"; mientras
// responde se ve que esta escribiendo; y el cuadro de escribir va pegado abajo,
// con el envio en un boton de icono. La indicacion de que es una demostracion se
// queda, porque es regla (M10); la de como se manda con el teclado se fue.
//
// **Sin caja, desde el 2026-10-08 (decision de Miguel).** La ventana era una tarjeta
// en medio de la pantalla y se sentia apretada. Ahora la conversacion ocupa la
// pagina: una columna de lectura centrada, la agente en texto corrido sin burbuja, lo
// de la persona en una burbuja suave a la derecha, y el cuadro de escribir abajo en
// la misma columna. Sigue desplazandose solo la conversacion, nunca la pagina.
//
// **Y la conversacion vuelve** (misma fecha, misma decision). Al abrir, la pantalla
// pide al servidor lo que guardo de este navegador --la apertura, los turnos, el
// numero del caso-- y lo dibuja antes de que la persona escriba nada. Asi la
// agente se presenta al cargar y no despues del primer mensaje, y quien sale a
// mirar su poliza vuelve a lo que dejo. Lo recuperado viene **redactado**, porque
// asi se guarda, y una nota lo dice en vez de dejar que una etiqueta parezca un
// error.
//
// **Una sola fila de acciones, desde el 2026-10-11 (decision de Miguel).** Documentos,
// pensamiento, ver el caso y reiniciar van juntos en el encabezado, y reiniciar es solo
// un icono que abre una ventana para confirmar. Bajo el encabezado, la linea del caso
// dice que es y cuanto falta; su numero queda al final, como referencia. La columna es
// un poco mas ancha, y el nombre de la agente es el de cada aseguradora.

import {
  ArrowCounterClockwiseIcon,
  BrainIcon,
  FolderOpenIcon,
  GavelIcon,
  PaperPlaneRightIcon,
} from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";

import {
  caseStatus as loadCaseStatusFromServer,
  history as loadHistoryFromServer,
  openChatStream,
  resetConversation as resetConversationOnServer,
  sendMessage,
  type ChatCaseStatus,
  type ChatHistory,
  type Locale,
} from "../../shared/api-client/chat";
import { useLocale } from "../../shared/i18n/locale-provider";
import type { Translate } from "../../shared/i18n/translate";
import { useAgentName } from "../../shared/site/agent-name";
import { useAnnouncer } from "../../shared/ui/announcer";
import { Button } from "../../shared/ui/button";
import { cn } from "../../shared/ui/cn";
import { ConfirmDialog } from "../../shared/ui/confirm-dialog";
import { CHAT_COLUMN, CHAT_TRANSCRIPT_GUTTER } from "../../shared/ui/page-layout";
import { Textarea } from "../../shared/ui/textarea";
import { phraseFor } from "./chat-copy";
import { DocumentsButton } from "../policies/documents-dialog";
import { Citation, withPositions } from "./citation";
import {
  EMPTY,
  reduce,
  withHistory,
  withVisitorMessage,
  type Conversation,
  type WireEvent,
} from "./chat-events";
import { clearDraft, recallDraft, saveDraft } from "./draft";
import { ReasoningButton } from "./reasoning-dialog";
import { forget, isMasked, recall, recallAgent, remember, rememberAgent } from "./own-text";

/**
 * Cuanto se espera, como mucho, a que el fondo traiga la respuesta que el turno anuncio.
 * Pasado este tiempo el indicador de "revisando" se quita aunque no haya llegado nada:
 * un indicador que gira para siempre dice mas de lo que se sabe. Es el doble de lo que la
 * revision tarda hoy con el plan gratuito del modelo en un mal momento.
 */
export const REVIEW_CEILING_MS = 60_000;

export interface ChatPageProps {
  readonly tenantId: string;
  /** El nombre de la aseguradora, para el titulo. */
  readonly insurerLabel: string;
  /** Como enlazar al resumen de una traza. */
  readonly traceHref?: (traceRef: string) => string;
  /** Solo para las pruebas: sin esto, el flujo real del navegador. */
  readonly openStream?: (tenantId: string) => EventSource;
  /** Solo para las pruebas: sin esto, la ruta real del historial. */
  readonly loadHistory?: (tenantId: string, locale: Locale) => Promise<ChatHistory | null>;
  /** Solo para las pruebas: sin esto, la ruta real del estado del caso. */
  readonly loadCaseStatus?: (tenantId: string) => Promise<ChatCaseStatus | null>;
  /** Solo para las pruebas: sin esto, la ruta real de empezar de cero. */
  readonly reset?: (tenantId: string, locale: Locale) => Promise<ChatHistory | null>;
  /**
   * Un mensaje que se envia solo, una vez, cuando la conversacion esta lista: lo usan
   * las preguntas para probar de la pestana de polizas (fase 2, 2026-10-08).
   */
  readonly initialMessage?: string | undefined;
  /** Se llama cuando el mensaje inicial ya salio, para quitarlo de la direccion. */
  readonly onInitialMessageSent?: () => void;
}

function idDeVisitante(): string {
  return `visitor-${String(Date.now())}-${Math.random().toString(36).slice(2, 8)}`;
}

/** La inicial de la agente, para el avatar de cada mensaje. Decorativo: el nombre va al lado. */
function inicial(nombre: string): string {
  return nombre.trim().charAt(0).toUpperCase();
}

/**
 * El estilo unico de las acciones del encabezado --documentos, pensamiento, ver el caso
 * y reiniciar-- (2026-10-09): botones sin borde ni fondo, con el icono en el acento de la
 * aseguradora. Documentos lo repite en `documents-dialog.tsx`.
 */
const ACCION_DEL_ENCABEZADO = "shrink-0 gap-1.5 px-3 text-fg-secondary hover:text-fg tablet:px-4";

/** Que es el caso, en palabras de quien lo reporto: sale del tipo que ya entrega la API. */
function caseKind(recordType: string | null | undefined, t: Translate): string {
  if (recordType === "claim") {
    return t("chat.page.case_kind_claim");
  }
  if (recordType === "coverage_inquiry") {
    return t("chat.page.case_kind_inquiry");
  }
  if (recordType === "quote_request") {
    return t("chat.page.case_kind_quote");
  }
  return t("chat.page.case_kind_other");
}

/** Cuanto falta, dicho en palabras; la barra de al lado repite la cifra sin reemplazarla. */
function caseMissing(faltan: number, t: Translate): string {
  if (faltan <= 0) {
    return t("chat.page.case_complete");
  }
  return faltan === 1
    ? t("chat.page.case_missing_one")
    : t("chat.page.case_missing_many", { count: String(faltan) });
}

/**
 * La linea del caso: que es, cuanto falta y --al final, como referencia-- su numero.
 * En una consulta no hay avance que contar: nadie esta dando datos (2026-10-08).
 */
function CaseLine({ caso }: { readonly caso: ChatCaseStatus }) {
  const { t } = useLocale();
  const conAvance = caso.record_type !== "coverage_inquiry" && caso.total > 0;
  return (
    <div
      data-testid="chat-case"
      className={cn(
        CHAT_COLUMN,
        "flex flex-wrap items-center gap-x-4 gap-y-1 pb-2 text-small text-fg-secondary",
      )}
    >
      <p className="font-medium text-fg">{caseKind(caso.record_type, t)}</p>
      {conAvance ? (
        <p className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="h-1.5 w-16 overflow-hidden rounded-pill bg-hairline tablet:w-24"
          >
            <span
              className="block h-full rounded-pill bg-tenant"
              style={{ width: `${String(Math.round((caso.complete / caso.total) * 100))}%` }}
            />
          </span>
          {caseMissing(caso.total - caso.complete, t)}
        </p>
      ) : null}
      {/* En telefono baja a su propio renglon, a la izquierda; desde tableta, al final de la linea. */}
      <p className="w-full font-mono text-caption tablet:ml-auto tablet:w-auto">
        {t("chat.page.case_number", { case_number: caso.case_number })}
      </p>
    </div>
  );
}

/** El icono y el nombre del boton que abre el pensamiento de la agente; en telefono, solo el icono. */
function ReasoningLabel({ agent }: { readonly agent: string }) {
  const { t } = useLocale();
  return (
    <>
      <BrainIcon aria-hidden="true" focusable="false" size={18} className="text-tenant" />
      <span className="sr-only tablet:not-sr-only">{t("chat.page.see_reasoning", { agent })}</span>
    </>
  );
}

export function ChatPage({
  tenantId,
  insurerLabel,
  traceHref,
  openStream,
  loadHistory,
  loadCaseStatus,
  reset,
  initialMessage,
  onInitialMessageSent,
}: ChatPageProps) {
  const { t, locale } = useLocale();
  const [conversacion, setConversacion] = useState<Conversation>(EMPTY);
  // Lo escrito y no enviado vuelve al regresar a la pagina (2026-10-12): se guarda en este
  // navegador por aseguradora, se borra al enviar y al empezar de cero.
  const [borrador, setBorrador] = useState(() => recallDraft(tenantId));
  const aseguradoraDelBorrador = useRef(tenantId);
  useEffect(() => {
    // Otra aseguradora sin desmontar la pagina: su cuadro es el suyo.
    if (aseguradoraDelBorrador.current !== tenantId) {
      aseguradoraDelBorrador.current = tenantId;
      setBorrador(recallDraft(tenantId));
    }
  }, [tenantId]);
  const [limite, setLimite] = useState<string | null>(null);
  const [conectado, setConectado] = useState(false);
  // Lo que el servidor guardo y esta pantalla volvio a dibujar: cuantos turnos y
  // el numero del caso. `null` mientras no llego, o cuando no habia nada antes.
  const [recuperado, setRecuperado] = useState<{
    readonly turns: number;
    readonly caseNumber: string | null;
  } | null>(null);
  // Donde va el caso: numero, avance y enlace, visible desde que nace y al dia
  // con cada respuesta (decision de Miguel, 2026-10-06: ver el flujo mientras
  // avanza, no al final). `null` mientras no hay caso.
  const [caso, setCaso] = useState<ChatCaseStatus | null>(null);
  // Empezar de cero (decision de Miguel, 2026-10-06): el boton abre una ventana que pide
  // confirmar antes de cerrar la conversacion; el caso anterior queda con su numero.
  const [confirmandoReinicio, setConfirmandoReinicio] = useState(false);
  const [reiniciando, setReiniciando] = useState(false);
  const transcripcion = useRef<HTMLOListElement>(null);
  const { announce } = useAnnouncer();
  const agente = useAgentName(tenantId);
  // El idioma de la pantalla **al abrir**, para pedir el historial en el sin que
  // cambiar el selector vuelva a abrir el flujo: el flujo es uno por pestana.
  const idiomaAlAbrir = useRef(locale);
  // El historial ya llego: antes, un mensaje inicial quedaria detras de lo guardado.
  const [historialListo, setHistorialListo] = useState(false);
  const inicialEnviado = useRef(false);

  useEffect(() => {
    const flujo = (openStream ?? openChatStream)(tenantId);
    const historial = loadHistory ?? loadHistoryFromServer;
    const estadoDelCaso = loadCaseStatus ?? loadCaseStatusFromServer;
    let vigente = true;
    // Cada lectura lleva su numero y una vieja que llega tarde no pisa a una mas nueva ya
    // aplicada (2026-10-13): con el cierre en dos tiempos hay dos relecturas seguidas --la
    // del turno, con el caso aun evaluandose, y la del aviso de fondo, con el resultado--
    // y la primera puede tardar mas que la segunda.
    let pedidas = 0;
    let aplicada = 0;
    const actualizarCaso = () => {
      pedidas += 1;
      const mia = pedidas;
      void estadoDelCaso(tenantId).then((estado) => {
        if (vigente && estado !== null && mia > aplicada) {
          aplicada = mia;
          setCaso(estado);
        }
      });
    };
    flujo.onopen = () => {
      setConectado(true);
      // **Despues de que el flujo abrio**, y no antes: la galleta del visitante la
      // pone la primera respuesta que llega, y dos peticiones sin galleta acabarian
      // en dos conversaciones distintas. Lo recuperado se pone delante de lo que ya
      // haya llegado por el flujo mientras tanto.
      void historial(tenantId, idiomaAlAbrir.current).then((guardado) => {
        if (vigente) {
          setHistorialListo(true);
        }
        if (!vigente || guardado === null) {
          return;
        }
        // Lo que la persona escribio en esta pestana vuelve a su burbuja en vez de
        // las etiquetas con que se guardo (fase 0, 2026-10-07).
        setConversacion((previa) =>
          withHistory(previa, guardado, recall(tenantId), recallAgent(tenantId)),
        );
        setRecuperado(
          guardado.turns.length > 0
            ? { turns: guardado.turns.length, caseNumber: guardado.case_number }
            : null,
        );
        if (guardado.case_number !== null) {
          actualizarCaso();
        }
      });
    };
    flujo.onmessage = (evento: MessageEvent<string>) => {
      const cable = JSON.parse(evento.data) as WireEvent;
      if (cable.kind === "turn.final" && cable.text !== "") {
        rememberAgent(tenantId, cable.text);
      }
      setConversacion((previa) => reduce(previa, cable));
      // Cada respuesta cerrada con caso puede haber movido el avance: se vuelve a
      // leer. La apertura y los avisos de fondo tambien traen `case_id`, y pedirlo
      // de mas solo cuesta una lectura. **El resultado del cierre llega por aqui**: es un
      // `turn.final` de fondo (`message_id` «background-…»), publicado cuando el caso ya
      // cambio de estado, asi que esta lectura es la que trae el boton de decidir o el
      // cierre directo (2026-10-13). Una lectura por evento, sin sondeo.
      if (
        (cable.kind === "turn.final" || cable.kind === "turn.handoff") &&
        cable.case_id !== null
      ) {
        actualizarCaso();
      }
    };
    // Una pestana, un flujo: al salir se cierra. Sin esto, volver a entrar deja
    // dos abiertos y cada respuesta se ve dos veces.
    return () => {
      vigente = false;
      flujo.close();
    };
  }, [tenantId, openStream, loadHistory, loadCaseStatus]);

  // La conversacion se desplaza **dentro de su ventana**, nunca la pagina: con
  // cada mensaje, y tambien con cada fragmento que alarga el ultimo. Tambien cuando
  // aparece la linea del caso, que le quita altura por arriba y taparia el final.
  const hayCaso = caso !== null;
  useEffect(() => {
    const caja = transcripcion.current;
    if (caja !== null) {
      caja.scrollTop = caja.scrollHeight;
    }
  }, [conversacion.messages, hayCaso]);

  // Lo ultimo que dijo la agente, anunciado una vez. Quien no ve la pantalla se
  // entera de la respuesta sin tener que ir a buscarla, que es de lo que sirve
  // que la conversacion sea una lista y no un flujo de texto suelto.
  const ultimo = conversacion.messages.at(-1);
  const ultimoTexto = ultimo?.speaker === "agent" ? (ultimo.text ?? "") : "";
  useEffect(() => {
    if (ultimoTexto !== "") {
      announce(ultimoTexto);
    }
  }, [ultimoTexto, announce]);

  // Un turno a la vez: mientras la agente responde, lo escrito espera. Dos turnos
  // en vuelo sobre el mismo caso chocan en el servidor (una transicion del caso
  // que ya hizo el otro turno), y la persona leia "tuve un problema para
  // responder eso" sin haber hecho nada raro (visto el 2026-10-06).
  const enVuelo = !conversacion.idle;

  async function enviar(mensaje?: string): Promise<void> {
    const texto = (mensaje ?? borrador).trim();
    if (texto === "" || enVuelo) {
      return;
    }
    // Lo que se manda desde un boton no es el borrador: quien tenia algo escrito y toca
    // una respuesta rapida no lo pierde.
    if (mensaje === undefined) {
      setBorrador("");
      clearDraft(tenantId);
    }
    setLimite(null);
    setConversacion((previa) => withVisitorMessage(previa, idDeVisitante(), texto));
    remember(tenantId, texto);
    // Con el idioma de la pantalla (P2): la agente contesta en el salvo que el
    // texto diga claramente otro.
    const resultado = await sendMessage(tenantId, texto, { locale });
    if (resultado.outcome !== "accepted") {
      // Sin turno en curso no hay respuesta que esperar: los puntos de "escribiendo"
      // se quedaban para siempre y el boton de enviar seguia deshabilitado.
      setConversacion((previa) => ({ ...previa, idle: true }));
    }
    if (resultado.outcome === "rejected") {
      // Un limite no es un error: lleva su frase, y la pantalla la dice tal cual.
      setLimite(resultado.rejected.copy_key);
    } else if (resultado.outcome === "demo_closed") {
      // Tampoco es un error: la demostracion no acepta **casos nuevos** porque
      // pasaron 24 horas sin reinicio (BR3.2 de U20), y su frase lo dice. Una
      // conversacion que ya tiene caso no llega aqui: esa sigue entera (BR3.3).
      setLimite(resultado.closed.copy_key);
    } else if (resultado.outcome === "failed") {
      setLimite("chat.turn.error");
    }
  }

  useEffect(() => {
    const texto = initialMessage?.trim() ?? "";
    if (!historialListo || texto === "" || inicialEnviado.current) {
      return;
    }
    inicialEnviado.current = true;
    void enviar(texto);
    onInitialMessageSent?.();
    // `enviar` cambia en cada dibujo; lo que decide es que el historial este listo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historialListo, initialMessage]);

  async function reiniciar(): Promise<void> {
    setReiniciando(true);
    const nueva = await (reset ?? resetConversationOnServer)(tenantId, locale);
    setReiniciando(false);
    setConfirmandoReinicio(false);
    if (nueva === null) {
      setLimite("chat.turn.error");
      return;
    }
    // La conversacion nueva, como la devuelve el servidor: solo la apertura.
    forget(tenantId);
    setConversacion(withHistory(EMPTY, nueva));
    setRecuperado(null);
    setCaso(null);
    setLimite(null);
    setBorrador("");
    clearDraft(tenantId);
  }

  // "Esta escribiendo" mientras el turno esta en curso y todavia no llego ni un
  // fragmento ni la frase de espera: en cuanto hay algo que leer, se lee eso.
  //
  // Y los mismos puntos mientras el fondo revisa la poliza (2026-10-12): el turno ya
  // dijo "dejame revisar" y la conversacion quedaba quieta hasta que llegaba la
  // respuesta, doce segundos en la prueba de Miguel. Lo sabe por el evento final, que
  // trae `answer_pending`, y no por el texto.
  const revisando = conversacion.reviewing && conversacion.idle;
  const escribiendo =
    revisando || (!conversacion.idle && (ultimo === undefined || ultimo.speaker === "visitor"));
  // Un tope: si la respuesta no llega, el indicador no gira para siempre.
  const sigueRevisando = conversacion.reviewing;
  useEffect(() => {
    if (!sigueRevisando) {
      return;
    }
    const plazo = window.setTimeout(() => {
      setConversacion((previa) => ({ ...previa, reviewing: false }));
    }, REVIEW_CEILING_MS);
    return () => {
      window.clearTimeout(plazo);
    };
  }, [sigueRevisando]);
  // Los botones solo de la ultima respuesta, y solo cuando se puede contestar.
  const botones = !enVuelo && ultimo?.speaker === "agent" ? ultimo.suggestions : [];
  // Bajo la ultima respuesta, decidir el caso como ajustador cuando espera esa decision.
  const ultimaDeLaAgente = !enVuelo && ultimo?.speaker === "agent" ? ultimo : undefined;
  const enlaceParaDecidir =
    caso !== null && caso.case_link !== null && caso.state === "derived" ? caso.case_link : null;
  // El boton aparece cuando llega el estado del caso, que se pide **despues** de la
  // respuesta: el desplazamiento de arriba ya paso, el boton nace debajo del ultimo
  // mensaje y el cuadro de escribir lo dejaba fuera de la ventana hasta que la persona
  // desplazara (auditoria del 2026-10-10, C12). Al aparecer, se baja hasta mostrarlo.
  const decidirVisible = ultimaDeLaAgente !== undefined && enlaceParaDecidir !== null;
  useEffect(() => {
    const caja = transcripcion.current;
    if (decidirVisible && caja !== null) {
      caja.scrollTop = caja.scrollHeight;
    }
  }, [decidirVisible]);
  // El aviso de lo tapado solo si queda algo tapado: lo escrito en esta pestana ya
  // volvio a su burbuja.
  const quedaTapado = conversacion.messages.some(
    (mensaje) => mensaje.speaker === "visitor" && isMasked(mensaje.text ?? ""),
  );

  // Debajo del titulo: en que idioma responde, si ya lo dijo; si no, que responde
  // en el idioma de la pantalla y donde se cambia (P2); y mientras no conecta,
  // que se esta conectando. La aseguradora ya esta en el titulo.
  const nombreDelIdioma = (idioma: Locale) =>
    idioma === "es" ? t("shell.language.es") : t("shell.language.en");
  const subtitulo =
    conversacion.answeringIn !== null
      ? t("chat.page.answering_in", { language: nombreDelIdioma(conversacion.answeringIn) })
      : conectado
        ? t("chat.page.speaking_in")
        : t("chat.page.connecting");

  return (
    <section
      aria-label={t("chat.page.title", { insurer: insurerLabel })}
      data-testid="chat-window"
      className="flex min-h-0 w-full flex-1 flex-col"
    >
      {/* Lo de arriba, sin caja: quien atiende, en que idioma, las acciones --documentos,
          pensamiento, ver el caso y reiniciar, en una sola fila-- y, si ya hay caso, su
          linea. Un velo corto bajo este bloque deja que la conversacion se pierda
          debajo en vez de cortarse en seco. */}
      <div className="relative z-10 bg-page after:pointer-events-none after:absolute after:inset-x-0 after:top-full after:h-6 after:bg-linear-to-b after:from-page after:to-transparent">
        <header className={cn(CHAT_COLUMN, "flex items-center gap-3 pt-4 pb-2 tablet:pt-6")}>
          <div className="flex min-w-0 flex-1 flex-col">
            <h1 className="font-display text-body font-medium text-balance text-tenant tablet:text-lead">
              {insurerLabel}
            </h1>
            <p className="line-clamp-2 text-caption text-fg-secondary">{subtitulo}</p>
          </div>
          {/* Las acciones, en un solo grupo (2026-10-11): en telefono, solo iconos con su
              nombre accesible; desde tableta, con su nombre y un marco comun. */}
          <div className="flex shrink-0 items-center tablet:gap-0.5 tablet:rounded-control tablet:border tablet:border-hairline tablet:p-0.5">
            {/* "Ver mi caso" va primero: aparece tras el primer mensaje y, al ir en el extremo
                izquierdo de un grupo pegado a la derecha, no corre a los demas botones. */}
            {caso !== null && caso.case_link !== null ? (
              // Abrir el caso y decidirlo: el mismo enlace que la llamada da al colgar.
              <Button asChild variant="ghost" size="compact" className={ACCION_DEL_ENCABEZADO}>
                <a href={caso.case_link} data-testid="chat-case-link">
                  <FolderOpenIcon
                    aria-hidden="true"
                    focusable="false"
                    size={18}
                    className="text-tenant"
                  />
                  <span className="sr-only tablet:not-sr-only">{t("chat.page.case_link")}</span>
                </a>
              </Button>
            ) : null}
            <DocumentsButton tenantId={tenantId} insurerName={insurerLabel} variant="compact" />
            {/* El pensamiento sobre el caso, en su ventana (2026-10-09): lo que el caso
                guarda dicho por pasos. Antes abria la traza tecnica, que en una
                consulta salia vacia. */}
            <ReasoningButton
              tenantId={tenantId}
              className={ACCION_DEL_ENCABEZADO}
              label={t("chat.page.see_reasoning", { agent: agente })}
            >
              <ReasoningLabel agent={agente} />
            </ReasoningButton>
            <span aria-hidden="true" className="mx-0.5 hidden h-5 w-px bg-hairline tablet:block" />
            {/* Solo el icono: lo que reinicia lo dice el nombre accesible, el `title` y la
                ventana que abre. */}
            <Button
              type="button"
              variant="ghost"
              size="compact"
              className={cn(ACCION_DEL_ENCABEZADO, "size-11 px-0 tablet:px-0")}
              aria-label={t("chat.page.reset")}
              title={t("chat.page.reset")}
              data-testid="chat-reset"
              disabled={enVuelo || reiniciando}
              onClick={() => {
                setConfirmandoReinicio(true);
              }}
            >
              <ArrowCounterClockwiseIcon
                aria-hidden="true"
                focusable="false"
                size={18}
                className="text-tenant"
              />
            </Button>
          </div>
        </header>

        {caso === null ? null : <CaseLine caso={caso} />}
      </div>

      <ol
        ref={transcripcion}
        // Una region que se desplaza tiene que poder recibir el foco, o quien
        // navega con teclado no puede leer lo que quedo arriba: es la regla
        // `scrollable-region-focusable` del arnes de accesibilidad, que puso
        // `main` en rojo el 2026-10-06 al estrenar la ventana. El linter opina lo
        // contrario para una lista --que no es interactiva-- y aqui manda el
        // arnes, que mide lo que le pasa a una persona con teclado.
        //
        // Va a todo el ancho (la barra queda en el borde de la ventana) y su relleno
        // deja los mensajes en la columna de lectura; el anillo de foco se dibuja por
        // dentro, porque por fuera caeria fuera de la ventana.
        // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- region desplazable, exigido por axe
        tabIndex={0}
        aria-label={t("chat.page.transcript_label")}
        className={cn(
          "flex min-h-48 flex-1 flex-col gap-6 overflow-y-auto py-6 focus-visible:-outline-offset-2 tablet:min-h-0 tablet:gap-7 tablet:py-8",
          CHAT_TRANSCRIPT_GUTTER,
        )}
        data-testid="chat-transcript"
      >
        {recuperado === null || !quedaTapado ? null : (
          // Lo recuperado viene redactado porque asi se guarda; sin esta linea una
          // etiqueta donde la persona escribio su poliza parece un error.
          <li
            className="self-center px-4 text-center text-caption text-fg-secondary"
            data-testid="chat-history-note"
          >
            {t("chat.page.history_restored")}
          </li>
        )}
        {conversacion.messages.map((mensaje, indice) => {
          const deLaAgente = mensaje.speaker === "agent";
          // El nombre de la agente se ve una vez por tanda de mensajes suyos, como en
          // cualquier conversacion; en los siguientes queda solo para el lector.
          const sigueLaTanda = conversacion.messages[indice - 1]?.speaker === mensaje.speaker;
          const texto =
            mensaje.text ?? (mensaje.copyKey === null ? "" : phraseFor(mensaje.copyKey)(t));
          if (!deLaAgente) {
            // Lo de la persona, a la derecha en una burbuja suave con el acento de la
            // aseguradora; quien habla lo dice el lado y, para el lector, la etiqueta.
            return (
              <li
                key={mensaje.id}
                className={cn(
                  "flex max-w-[85%] flex-col items-end self-end tablet:max-w-[min(75%,36rem)]",
                  sigueLaTanda && "-mt-4 tablet:-mt-5",
                )}
              >
                <p className="sr-only">{t("chat.page.speaker_visitor")}</p>
                <div className="rounded-bubble rounded-br-control border border-tenant/35 bg-tenant/18 px-4 py-2.5 text-body break-words whitespace-pre-line text-fg">
                  {texto}
                </div>
              </li>
            );
          }
          // Lo de la agente, sin burbuja: texto de lectura en la columna, como una
          // pagina, con su nombre y su inicial arriba.
          return (
            <li key={mensaje.id} className={cn("flex flex-col gap-2.5", sigueLaTanda && "-mt-3")}>
              {sigueLaTanda ? (
                <p className="sr-only">{agente}</p>
              ) : (
                <p className="flex items-center gap-2 text-small font-medium text-fg">
                  <span
                    aria-hidden="true"
                    className="flex size-6 shrink-0 items-center justify-center rounded-pill bg-tenant font-display text-caption font-medium text-on-tenant"
                  >
                    {inicial(agente)}
                  </span>
                  {agente}
                </p>
              )}
              <div
                className={cn(
                  "max-w-[72ch] text-body break-words whitespace-pre-line text-fg",
                  mensaje.transient && "text-fg-secondary italic",
                )}
              >
                {texto}
              </div>
              {mensaje.citations.length === 0 ? null : (
                <div className="flex max-w-xl flex-col gap-2">
                  {withPositions(mensaje.citations).map(({ citation: cita, position }) => (
                    <Citation
                      key={`${mensaje.id}-${cita.clause_id}`}
                      citation={cita}
                      conversationLocale={locale}
                      position={position}
                      {...(traceHref !== undefined && mensaje.traceRef !== null
                        ? { traceHref: traceHref(mensaje.traceRef) }
                        : {})}
                    />
                  ))}
                </div>
              )}
              {mensaje !== ultimaDeLaAgente || enlaceParaDecidir === null ? null : (
                <div className="flex flex-wrap gap-2" data-testid="chat-inside">
                  <Button asChild variant="secondary" size="compact" className="gap-1.5">
                    <a href={enlaceParaDecidir}>
                      <GavelIcon
                        aria-hidden="true"
                        focusable="false"
                        size={18}
                        className="text-tenant"
                      />
                      {t("chat.page.decide_as_adjuster")}
                    </a>
                  </Button>
                </div>
              )}
            </li>
          );
        })}
        {escribiendo ? (
          <li className="flex flex-col gap-2.5" data-testid="chat-typing">
            <p className="flex items-center gap-2 text-small font-medium text-fg">
              <span
                aria-hidden="true"
                className="flex size-6 shrink-0 items-center justify-center rounded-pill bg-tenant font-display text-caption font-medium text-on-tenant"
              >
                {inicial(agente)}
              </span>
              {agente}
            </p>
            <div
              role="status"
              aria-label={
                revisando
                  ? t("chat.page.reviewing", { agent: agente })
                  : t("chat.page.typing", { agent: agente })
              }
              className="flex h-6 items-center gap-1.5"
            >
              {[0, 1, 2].map((punto) => (
                <span
                  key={punto}
                  aria-hidden="true"
                  className="size-2 rounded-pill bg-fg-tertiary motion-safe:animate-bounce"
                  style={{ animationDelay: `${String(punto * 150)}ms` }}
                />
              ))}
            </div>
          </li>
        ) : null}
      </ol>

      {/* El cuadro de escribir, abajo y en la misma columna. El velo de encima hace
          que los mensajes se pierdan bajo el en vez de cortarse contra su borde. */}
      <div className="relative z-10 bg-page before:pointer-events-none before:absolute before:inset-x-0 before:bottom-full before:h-8 before:bg-linear-to-t before:from-page before:to-transparent">
        <form
          className={cn(CHAT_COLUMN, "flex flex-col gap-2 pt-1 pb-3 tablet:pb-4")}
          onSubmit={(evento) => {
            evento.preventDefault();
            void enviar();
          }}
        >
          {limite === null ? null : (
            <p role="status" className="text-small text-fg">
              {phraseFor(limite)(t)}
            </p>
          )}
          {botones.length === 0 ? null : (
            // Los botones de respuesta rapida que eligio el servidor para la ultima
            // pregunta (fase 0, 2026-10-07): escribir nunca es obligatorio. Tocar uno
            // lo manda como mensaje, igual que escribirlo.
            <div className="flex flex-wrap gap-2" data-testid="chat-suggestions">
              {botones.map((boton) => (
                <Button
                  key={boton}
                  type="button"
                  variant="secondary"
                  size="compact"
                  // Con el acento de la aseguradora, como la ficha de la poliza que
                  // reemplazan: se distinguen de la respuesta de la agente.
                  className="border-tenant/40 text-caption text-tenant hover:bg-tenant/10"
                  onClick={() => {
                    void enviar(boton);
                  }}
                >
                  {boton}
                </Button>
              ))}
            </div>
          )}
          {/* Un solo campo con el boton de enviar dentro, en su esquina: el campo es
              la caja, y su propio borde marca el foco. */}
          <div className="relative">
            <label htmlFor="chat-composer" className="sr-only">
              {t("chat.page.composer_label")}
            </label>
            <Textarea
              id="chat-composer"
              rows={1}
              value={borrador}
              placeholder={t("chat.page.composer_label")}
              className="block max-h-48 min-h-14 resize-none rounded-bubble bg-surface py-3.5 pr-16 pl-4 shadow-raised field-sizing-content"
              onChange={(evento) => {
                setBorrador(evento.target.value);
                saveDraft(tenantId, evento.target.value);
              }}
              onKeyDown={(evento) => {
                // Enter envia; Mayus+Enter hace un salto de linea. Es lo que hace
                // cualquier chat, y sin ello escribir un mensaje pide ir al raton.
                //
                // **`isComposing` no es un adorno**: mientras se compone un caracter
                // con teclado de acentos o de otro alfabeto, Enter confirma la
                // composicion. Sin esta guardia, quien escriba "anos" con tilde manda
                // el mensaje a medias al elegir la n. El evento de React no lo trae
                // tipado, asi que se lee del nativo, que es donde el navegador lo pone.
                if (evento.key !== "Enter" || evento.shiftKey || evento.nativeEvent.isComposing) {
                  return;
                }
                evento.preventDefault();
                void enviar();
              }}
            />
            <Button
              type="submit"
              variant="tenant"
              aria-label={t("chat.page.send")}
              disabled={borrador.trim() === "" || enVuelo}
              className="absolute right-1.5 bottom-1.5 size-11 px-0"
            >
              <PaperPlaneRightIcon aria-hidden="true" focusable="false" size={20} weight="fill" />
            </Button>
          </div>
          <p className="text-center text-caption text-fg-secondary">
            {t("chat.page.composer_hint")}
          </p>
        </form>
      </div>

      {/* Reiniciar pide confirmar en una ventana, con lo que de verdad pasa: la
          conversacion se cierra, y el caso --si ya hay-- queda guardado con su numero. */}
      <ConfirmDialog
        open={confirmandoReinicio}
        title={t("chat.page.reset_title")}
        description={
          caso === null
            ? t("chat.page.reset_body")
            : t("chat.page.reset_body_with_case", { case_number: caso.case_number })
        }
        cancelLabel={t("chat.page.reset_cancel")}
        confirmLabel={t("chat.page.reset_confirm")}
        pending={reiniciando}
        icon={<ArrowCounterClockwiseIcon focusable="false" size={22} />}
        testId="chat-reset-confirm"
        onCancel={() => {
          setConfirmandoReinicio(false);
        }}
        onConfirm={() => {
          void reiniciar();
        }}
      />
    </section>
  );
}
