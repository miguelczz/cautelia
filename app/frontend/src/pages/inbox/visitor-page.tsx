// La pantalla del visitante que abre su propio caso con un enlace (BR5.1 a BR5.7).
//
// **Es una pantalla propia y no la del ajustador con un interruptor** (decision de
// Miguel, 2026-09-28). Comparten los bloques de evidencia y nada mas:
// `interaction-spec.md` prohibe la jerga del sistema en cualquier pantalla de
// visitante --"bandeja" no significa nada para quien reporta-- y sostener dos juegos
// de etiquetas sobre una sola pantalla es la forma segura de que un dia se cruce uno.
//
// **El token viaja en el fragmento de la direccion** (`/c#<token>`), que el navegador
// nunca manda en la peticion ni en `Referer` (C-07, BR5.6). La pantalla lo lee, lo
// canjea una vez al cargar y **limpia la direccion**, dejando el identificador del
// caso: asi recargar sigue funcionando con la cookie, y el token no aparece en la
// barra, ni en `Referer`, ni en ningun registro del servidor.
//
// **Las cuatro causas de rechazo se ven igual.** Firma alterada, vencido, revocado y
// de otro caso muestran la misma pagina de enlace no valido: un mensaje distinto por
// causa le diria a quien prueba enlaces cual de sus intentos acerto el identificador.
// Quien decide eso no es esta pantalla, es la funcion que U6 ya tiene para ello.
//
// **El visitante ya no decide ni anota** (plan 09, fase 5, 2026-11-04): el caso derivado lo
// decide el ajustador de IA, que explica su decision con sus fuentes. La pantalla solo lo
// cuenta, en el panel «Como decidio el ajustador» (`adjuster-panel.tsx`): en curso mientras
// trabaja --la pagina lo vuelve a leer cada 3 s--, la decision con sus seis pasos cuando termina,
// «en espera de cupo» si hoy ya no cabe, y «sigue en revision» si fallo, sin el motivo tecnico.
// Las rutas de decidir y anotar devuelven 403 a esta puerta; aqui ya no se llaman.
//
// **Dos paneles lado a lado** (Miguel, 2026-10-14: quien lee tenia que bajar y subir para ver
// los datos): a la izquierda el panel del ajustador y a la derecha los datos del reporte con las
// reglas, que se quedan a la vista al desplazar. Debajo de los dos, a todo el ancho, la
// conversacion, las citas, los controles y la respuesta. En pantalla angosta es una columna con
// los datos primero.

import { useEffect, useMemo, useState, type ReactNode } from "react";

import { caseDetail, redeemLink, type CaseDetailOut } from "../../shared/api-client/inbox";
import type { ProblemView } from "../../shared/api-client/problems";
import { useLocale } from "../../shared/i18n/locale-provider";
import { recallAll } from "../../shared/own-text/own-text";
import { startBoundedReread } from "../../shared/polling/bounded-reread";
import { Button } from "../../shared/ui/button";
import { cn } from "../../shared/ui/cn";
import { InlineAlert } from "../../shared/ui/inline-alert";
import {
  BLOCK_TITLE,
  CASE_ADJUSTER_PANE,
  CASE_COLUMN_WIDTH,
  CASE_DATA_PANE,
  CASE_PAGE_TITLE,
  CASE_WORKSPACE_PANES,
  CASE_WORKSPACE_WIDTH,
} from "../../shared/ui/page-layout";
import { PageSkeleton } from "../../shared/ui/page-skeletons";
import { AdjusterPanel, panelState } from "./adjuster-panel";
import {
  CitationList,
  ControlsBlock,
  FieldCompleteness,
  formatTime,
  OpenBlock,
  ResponseBlock,
  RuleBlock,
  TranscriptView,
} from "./evidence-blocks";
import {
  isAdjusterPending,
  isClosedByRules,
  isUnderReview,
  ownCaseTitle,
  reviewHint,
} from "./inbox-labels";

/**
 * Si el caso se abre mientras la agente lo evalua, la pagina lo vuelve a leer cada 3 s y,
 * como mucho, 10 veces (2026-10-13): unos 30 s, lo que tarda la evaluacion con holgura. Mientras
 * el ajustador de IA decide el caso --varias llamadas y hasta tres busquedas-- el tope es de 30
 * lecturas, unos 90 s (2026-11-04); pasado eso la pagina se queda como esta.
 */
const REREAD_MS = 3000;
const REREAD_MAX = 10;
const REREAD_MAX_ADJUSTER = 30;

/**
 * La superficie de los bloques de datos del reporte (2026-10-14): la de segundo nivel, que en
 * modo claro es un gris suave y en oscuro la mas clara, para que el panel donde se decide --en
 * la superficie normal, con la raya de la marca-- se distinga de lo que se mira.
 */
const SUPERFICIE_DE_DATOS = "bg-surface-alt";

/** Lo que el canje deja: el caso al que da acceso y hasta cuando. */
export interface CaseSession {
  readonly tenantId: string;
  readonly caseId: string;
  readonly expiresAt: string;
}

type Estado =
  | { readonly paso: "opening" }
  | { readonly paso: "rejected"; readonly problem: ProblemView }
  | {
      readonly paso: "ready";
      readonly session: CaseSession;
      readonly detail: CaseDetailOut;
    };

export interface VisitorCasePageProps {
  /** El token del fragmento, o nada cuando la direccion ya se limpio. */
  readonly token?: string;
  /**
   * La aseguradora y el caso de la direccion, cuando ya se canjeo y la pagina se
   * recargo. Los dos o ninguno: sin la aseguradora no hay ruta a la que pedir el
   * caso, y con una vacia se pediria a una direccion que no existe.
   *
   * Que la aseguradora quede en la direccion **no es una fuga**: quien acaba de
   * canjear su enlace estuvo conversando con ella. Lo que el token no revela es de
   * quien es **antes** de canjearlo, y eso sigue siendo cierto.
   */
  readonly tenantId?: string;
  readonly caseId?: string;
  /** Lo que la ruta hace para limpiar la direccion despues del canje (BR5.6). */
  readonly onRedeemed?: (session: CaseSession) => void;
  /** Como volver a la conversacion. */
  readonly conversationHref: (session: CaseSession) => string;
  /** Lo que la pantalla dibuja cuando el enlace no vale. Lo aporta la ruta (U6). */
  readonly renderRejected: (problem: ProblemView) => ReactNode;
}

export function VisitorCasePage({
  token,
  tenantId,
  caseId,
  onRedeemed,
  conversationHref,
  renderRejected,
}: VisitorCasePageProps) {
  const { t, locale } = useLocale();
  const [estado, setEstado] = useState<Estado>({ paso: "opening" });

  useEffect(() => {
    let vigente = true;

    const abrir = async (): Promise<void> => {
      // Con token: se canjea **una vez por carga**. No es un token de un solo uso;
      // mientras no haya caducado ni este revocado, el mismo enlace se puede volver a
      // abrir y quien cierre la pestana vuelve a entrar (aclaracion de C-07).
      let sesion: CaseSession | null = null;
      if (token !== undefined && token !== "") {
        const canje = await redeemLink(token);
        if (!vigente) {
          return;
        }
        if (!canje.ok) {
          setEstado({ paso: "rejected", problem: canje.problem });
          return;
        }
        sesion = {
          tenantId: canje.value.tenant,
          caseId: canje.value.case_id,
          expiresAt: canje.value.expires_at,
        };
        onRedeemed?.(sesion);
      } else if (
        tenantId !== undefined &&
        tenantId !== "" &&
        caseId !== undefined &&
        caseId !== ""
      ) {
        // Sin token pero con caso en la direccion: la cookie sigue viva y no hace
        // falta canjear otra vez. Lo que no se sabe por esta via es hasta cuando vale
        // el enlace, y **no se inventa**: la cookie no vive mas que el enlace, asi
        // que el vencimiento se descubre cuando el servidor deja de servir el caso.
        sesion = { tenantId, caseId, expiresAt: "" };
      }

      if (sesion === null) {
        // Ni token ni caso: la direccion no dice a que caso se entra, y eso se
        // responde igual que un enlace que no vale.
        setEstado({
          paso: "rejected",
          problem: { code: "link_invalid", message: (tt) => tt("problem.link_invalid") },
        });
        return;
      }

      const vista = await caseDetail(sesion.tenantId, sesion.caseId);
      if (!vigente) {
        return;
      }
      if (!vista.ok) {
        setEstado({ paso: "rejected", problem: vista.problem });
        return;
      }
      setEstado({ paso: "ready", session: sesion, detail: vista.value });
    };

    void abrir();
    return () => {
      vigente = false;
    };
  }, [token, tenantId, caseId, onRedeemed]);

  // Lo que este navegador recuerda de la conversacion de este caso: la base lo guarda con
  // los datos personales tapados, pero quien abre **su** caso lo lee como lo escribio y
  // como se lo dijeron (2026-10-12, cuarta vez que Miguel lo pide). Va antes de los
  // retornos de abajo porque es un gancho.
  const tenantPropio = estado.paso === "ready" ? estado.session.tenantId : null;
  const propios = useMemo(
    () => (tenantPropio === null ? undefined : recallAll(tenantPropio)),
    [tenantPropio],
  );

  // **Mientras la agente evalua el caso o el ajustador de IA lo decide, la pagina lo vuelve a
  // leer** (2026-10-13, ampliado el 2026-11-04): cada 3 s y con un tope, sin texto de espera
  // aparte --el panel del ajustador ya muestra los pasos a medida que llegan--. Se detiene al
  // salir de ahi, al llegar al tope (y se queda como esta), si una lectura falla, y al dejar la
  // pantalla. Va antes de los retornos porque es un gancho.
  const sesionPendiente =
    estado.paso === "ready" &&
    (isUnderReview(estado.detail.state) || isAdjusterPending(estado.detail))
      ? estado.session
      : null;
  const tenantPendiente = sesionPendiente?.tenantId;
  const casoPendiente = sesionPendiente?.caseId;
  const esperaAjustador = estado.paso === "ready" && isAdjusterPending(estado.detail);
  useEffect(() => {
    if (tenantPendiente === undefined || casoPendiente === undefined) {
      return undefined;
    }
    return startBoundedReread({
      read: () => caseDetail(tenantPendiente, casoPendiente),
      onResult: (vista) => {
        if (vista.ok) {
          const nuevo = vista.value;
          setEstado((previo) => (previo.paso === "ready" ? { ...previo, detail: nuevo } : previo));
        }
      },
      keepGoing: (vista) =>
        vista.ok && (isUnderReview(vista.value.state) || isAdjusterPending(vista.value)),
      everyMs: REREAD_MS,
      maxReads: esperaAjustador ? REREAD_MAX_ADJUSTER : REREAD_MAX,
    });
    // Al pasar de la evaluacion de la agente a la decision del ajustador la espera se reabre con
    // el tope largo: son dos esperas distintas.
  }, [tenantPendiente, casoPendiente, esperaAjustador]);

  if (estado.paso === "opening") {
    // El mismo esqueleto del caso que se va a abrir; "Abriendo tu caso" lo lee solo el
    // lector de pantalla.
    return <PageSkeleton kind="case" label={t("visitor.opening")} />;
  }

  if (estado.paso === "rejected") {
    return renderRejected(estado.problem);
  }

  const { session: sesion, detail: caso } = estado;

  // Cuatro situaciones que la pantalla cuenta de maneras distintas: el ajustador de IA tiene (o
  // va a tener) el caso, la agente aun lo evalua, lo cerraron las reglas sin ajustador, o espera
  // al asegurado o sigue en la conversacion. En ninguna hay botones: el visitante no decide.
  const cerradoPorReglas = isClosedByRules(caso);
  const enRevision = reviewHint(caso.state);

  // El panel del ajustador existe cuando el caso tiene corrida o esta derivado --el servidor la
  // abre al leerlo--. Con el caso en revision de la agente no hay panel: la introduccion ya dice
  // que se evalua, y la pagina se actualiza sola al salir de ahi.
  const conCorrida = caso.adjuster !== null && caso.adjuster !== undefined;
  const conPanelDelAjustador = conCorrida || caso.state === "derived";
  const decididoPorIA = panelState(caso.adjuster) === "decided";

  // Sin ajustador que contar, el panel solo dice como esta el caso (2026-10-14): cerrado por las
  // reglas, espera al asegurado, ya decidido por el personal o sigue en la conversacion.
  const conPanelDeEstado = !conPanelDelAjustador && enRevision === undefined;
  const conPanel = conPanelDelAjustador || conPanelDeEstado;

  // Los datos del reporte y la evaluacion de las reglas: es lo que se mira mientras se lee la
  // decision. Van en la superficie neutra de segundo nivel, distinta a la del panel del ajustador.
  const datos = (
    <>
      <OpenBlock
        title={t("visitor.block.fields")}
        testId="block-fields"
        className={SUPERFICIE_DE_DATOS}
      >
        <FieldCompleteness fields={caso.fields} />
      </OpenBlock>
      <RuleBlock detail={caso} className={SUPERFICIE_DE_DATOS} />
    </>
  );

  return (
    <main
      className={`mx-auto flex w-full ${CASE_WORKSPACE_WIDTH} flex-col gap-4 px-4 py-6`}
      data-testid="visitor-case"
    >
      <header className="flex flex-col gap-2">
        <h1 className={CASE_PAGE_TITLE}>{ownCaseTitle(caso.record_type)(t)}</h1>
        {/* El codigo no es el titulo: es un renglon pequeno que dice para que sirve (C10). */}
        <p className="text-caption text-fg-secondary" data-testid="visitor-case-number">
          {t("visitor.number", { case_number: caso.case_number })}
        </p>
        <p data-testid="visitor-intro">
          {cerradoPorReglas
            ? t("inbox.closed_by_rules.intro")
            : enRevision !== undefined
              ? enRevision(t)
              : t("visitor.intro")}
        </p>
        {/* Decidido el caso, la conversacion sigue: el aviso con la decision llega al chat. */}
        {decididoPorIA ? (
          <Button asChild variant="primary" className="self-start">
            <a href={conversationHref(sesion)}>{t("action.back_to_conversation")}</a>
          </Button>
        ) : null}
        {/*
          Hasta cuando vale el enlace. Solo se dice cuando se sabe: al recargar la
          pagina ya limpia, el canje no volvio a ocurrir y el dato no esta, y
          escribir una hora inventada seria peor que no escribirla.
        */}
        {sesion.expiresAt === "" ? null : (
          <p className="text-caption text-fg-secondary" data-testid="visitor-valid-until">
            {t("visitor.valid_until", { time: formatTime(sesion.expiresAt, locale) })}
          </p>
        )}
      </header>

      {/*
        Los dos paneles (2026-10-14): quien lee la decision necesita ver los datos al lado.
        **El orden del documento es el de pantalla angosta --los datos primero, despues el panel
        del ajustador--** y desde `desktop` la rejilla pone el del ajustador a la izquierda (ver
        `CASE_WORKSPACE_PANES`).
      */}
      <div
        className={conPanel ? CASE_WORKSPACE_PANES : "flex flex-col gap-4"}
        data-testid="visitor-panes"
      >
        {conPanel ? (
          <div
            // Una region que se desplaza tiene que poder recibir el foco (la regla
            // `scrollable-region-focusable` del arnes); el linter opina lo contrario y aqui manda
            // el arnes. El nombre es el del bloque de dentro: dice que se esta leyendo.
            // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- region desplazable, exigido por axe
            tabIndex={0}
            role="group"
            aria-label={t("visitor.block.fields")}
            className={CASE_DATA_PANE}
            data-testid="visitor-data"
          >
            {datos}
          </div>
        ) : (
          <div
            className={`flex w-full flex-col gap-4 ${CASE_COLUMN_WIDTH}`}
            data-testid="visitor-data"
          >
            {datos}
          </div>
        )}

        {conPanelDelAjustador ? (
          <AdjusterPanel run={caso.adjuster} className={CASE_ADJUSTER_PANE} idPrefix="visitor" />
        ) : null}

        {conPanelDeEstado ? (
          <section
            aria-labelledby="visitor-adjuster-title"
            data-testid="visitor-adjuster"
            className={cn(
              "flex flex-col gap-5 rounded-surface border border-hairline bg-surface p-4",
              CASE_ADJUSTER_PANE,
            )}
          >
            <h2 id="visitor-adjuster-title" className={BLOCK_TITLE}>
              {t("visitor.status.title")}
            </h2>
            <InlineAlert tone="info" data-testid="visitor-no-actions">
              {caso.state === "awaiting_insured"
                ? t("inbox.decision.none_awaiting")
                : cerradoPorReglas
                  ? t("inbox.closed_by_rules.note")
                  : caso.state === "closed"
                    ? t("inbox.decision.none_closed")
                    : t("inbox.decision.none_in_conversation")}
            </InlineAlert>
          </section>
        ) : null}
      </div>

      {/* Debajo de los dos paneles y a todo el ancho: la conversacion, las citas, lo que se
          reviso y como se respondio. Sin corregir campos: eso es de quien decide con credencial.
          Los dos ultimos dicen en una frase lo que tienen, y el que no tiene nada que decir no
          se pinta (E3, 2026-10-12). */}
      <OpenBlock title={t("inbox.block.transcript")} testId="block-transcript">
        <TranscriptView detail={caso} own={propios} />
      </OpenBlock>

      <OpenBlock title={t("inbox.block.citations")} testId="block-citations">
        <CitationList
          answers={caso.coverage_answers}
          conversationLocale={caso.language}
          own={propios}
        />
      </OpenBlock>

      <ControlsBlock detail={caso} />
      <ResponseBlock detail={caso} />
    </main>
  );
}
