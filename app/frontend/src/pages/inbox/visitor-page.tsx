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
// **La decision se atribuye a un visitante de demostracion y nunca a una persona de
// la aseguradora** (BR5.5). No es una decision de esta pantalla: el servidor lo
// decide por la puerta con la que se entro, y aqui solo se lee lo que dijo.
//
// **Antes de decidir puede anotar, con ayuda, lo que revisaria un ajustador** (2026-10-13):
// monto, cobertura en duda y sospecha de fraude (`visitor-triage.tsx`). Es opcional; el
// servidor dice si se ofrece (`can_annotate_triage`) y desde que montos cambian las reglas de
// esta aseguradora (`triage_amount_steps`), y al guardar la pagina vuelve a leer el caso para
// que el bloque de las reglas muestre la evaluacion nueva.
//
// **Dos paneles lado a lado** (Miguel, 2026-10-14: quien decide tenia que bajar y subir para ver
// los datos): a la izquierda el panel del ajustador --anotar y decidir-- y a la derecha los
// datos del reporte con las reglas, que se quedan a la vista al desplazar. Debajo de los dos, a
// todo el ancho, la conversacion, las citas, los controles y la respuesta. En pantalla angosta
// es una columna con los datos primero.

import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  annotateTriage,
  caseDetail,
  decideCase,
  redeemLink,
  type CaseDetailOut,
  type InboxAction,
  type TriageNoteIn,
} from "../../shared/api-client/inbox";
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
import { DecisionForm } from "./decision-form";
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
  isClosedByRules,
  isUnderReview,
  ownCaseTitle,
  resolutionLabel,
  reviewHint,
} from "./inbox-labels";
import { StepHeading } from "./step-heading";
import { VisitorTriageBlock, type TriageSaveResult } from "./visitor-triage";

/**
 * Si el caso se abre mientras la agente lo evalua, la pagina lo vuelve a leer cada 3 s y,
 * como mucho, 10 veces (2026-10-13): unos 30 s, lo que tarda la evaluacion con holgura.
 */
const REREAD_MS = 3000;
const REREAD_MAX = 10;

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
    }
  | {
      readonly paso: "decided";
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
  const tenantPropio =
    estado.paso === "ready" || estado.paso === "decided" ? estado.session.tenantId : null;
  const propios = useMemo(
    () => (tenantPropio === null ? undefined : recallAll(tenantPropio)),
    [tenantPropio],
  );

  // **Mientras la agente evalua el caso, la pagina lo vuelve a leer** (2026-10-13): cada 3 s y
  // como mucho 10 veces, sin indicador ni texto de espera --la introduccion ya dice que se
  // evalua--. Se detiene al salir de revision, al llegar al tope (y se queda como esta), si
  // una lectura falla, y al dejar la pantalla. Va antes de los retornos porque es un gancho.
  const sesionEnRevision =
    estado.paso === "ready" && isUnderReview(estado.detail.state) ? estado.session : null;
  const tenantEnRevision = sesionEnRevision?.tenantId;
  const casoEnRevision = sesionEnRevision?.caseId;
  useEffect(() => {
    if (tenantEnRevision === undefined || casoEnRevision === undefined) {
      return undefined;
    }
    return startBoundedReread({
      read: () => caseDetail(tenantEnRevision, casoEnRevision),
      onResult: (vista) => {
        if (vista.ok) {
          const nuevo = vista.value;
          setEstado((previo) => (previo.paso === "ready" ? { ...previo, detail: nuevo } : previo));
        }
      },
      keepGoing: (vista) => vista.ok && isUnderReview(vista.value.state),
      everyMs: REREAD_MS,
      maxReads: REREAD_MAX,
    });
  }, [tenantEnRevision, casoEnRevision]);

  if (estado.paso === "opening") {
    // El mismo esqueleto del caso que se va a abrir; "Abriendo tu caso" lo lee solo el
    // lector de pantalla.
    return <PageSkeleton kind="case" label={t("visitor.opening")} />;
  }

  if (estado.paso === "rejected") {
    return renderRejected(estado.problem);
  }

  const { session: sesion, detail: caso } = estado;

  const decidir = async (accion: InboxAction, comentario: string): Promise<ProblemView | null> => {
    const resultado = await decideCase(
      sesion.tenantId,
      sesion.caseId,
      accion,
      comentario,
      `visitor-${String(Date.now())}-${Math.random().toString(36).slice(2, 10)}`,
    );
    if (!resultado.ok) {
      // BR5.4: si el enlace vencio mientras se escribia, el texto **sigue en
      // pantalla** --el formulario no lo limpia al fallar-- y el mensaje lo dice, para
      // que se copie antes de salir. Perderlo convierte un vencimiento en trabajo
      // perdido, y lo sufre justo quien estaba terminando de decidir.
      //
      // El mensaje generico se cambia por este solo aqui y solo para las dos causas
      // del enlace: quien llego hasta el formulario ya tenia una sesion valida, asi
      // que decirle que su enlace vencio no le confirma nada que no supiera.
      //
      // **Solo cuando de verdad vencio** (2026-10-12): el servidor responde lo mismo a un
      // enlace vencido y a una decision que no pudo aceptar, y llamar "vencido" a lo
      // segundo mandaba a copiar la nota y salir a quien aun podia reintentar. Se
      // comprueba preguntando por el caso de nuevo: si el enlace sigue sirviendolo, no
      // vencio.
      if (resultado.problem.code === "link_invalid" || resultado.problem.code === "not_found") {
        const sigueVigente = (await caseDetail(sesion.tenantId, sesion.caseId)).ok;
        return {
          ...resultado.problem,
          message: (tt) =>
            tt(sigueVigente ? "visitor.decision_not_saved" : "visitor.expired_with_comment"),
        };
      }
      return resultado.problem;
    }
    const vista = await caseDetail(sesion.tenantId, sesion.caseId);
    setEstado({
      paso: "decided",
      session: sesion,
      detail: vista.ok ? vista.value : caso,
    });
    return null;
  };

  const volverALeer = async (): Promise<void> => {
    const vista = await caseDetail(sesion.tenantId, sesion.caseId);
    if (vista.ok) {
      const nuevo = vista.value;
      setEstado((previo) => (previo.paso === "ready" ? { ...previo, detail: nuevo } : previo));
    }
  };

  // Anotar para las reglas: se guarda y se vuelve a leer el caso, para que el bloque de las
  // reglas de abajo --y el propio bloque de anotar, si el tope se alcanzo-- cuenten lo nuevo.
  const anotar = async (nota: TriageNoteIn): Promise<TriageSaveResult> => {
    const resultado = await annotateTriage(
      sesion.tenantId,
      sesion.caseId,
      nota,
      `visitor-note-${String(Date.now())}-${Math.random().toString(36).slice(2, 10)}`,
    );
    if (resultado.ok) {
      const { receipt_id: recibo, rule_category: categoria, fired_rules: reglas } = resultado.value;
      // Sin recibo no se escribio nada (guardo lo que ya estaba): no hay nada que releer.
      if (recibo !== null) {
        await volverALeer();
      }
      return {
        ok: true,
        outcome: { ruleCategory: categoria, firedRules: reglas, changed: recibo !== null },
      };
    }
    const problema = resultado.problem;
    // Un `409` es que ya no se puede anotar (tope, nota del personal, otro estado del caso): la
    // frase lo dice, y se vuelve a leer para que la pantalla deje de ofrecer el formulario.
    if (problema.code === "conflict_state") {
      await volverALeer();
      return { ok: false, problem: { ...problema, message: (tt) => tt("visitor.triage.limit") } };
    }
    // Un enlace vencido se dice como al decidir, y solo si de verdad vencio: se comprueba
    // preguntando por el caso. Lo escrito sigue en pantalla en los dos casos.
    if (problema.code === "link_invalid" || problema.code === "not_found") {
      const sigueVigente = (await caseDetail(sesion.tenantId, sesion.caseId)).ok;
      return sigueVigente
        ? { ok: false, problem: problema }
        : {
            ok: false,
            problem: { ...problema, message: (tt) => tt("visitor.triage.expired") },
          };
    }
    return { ok: false, problem: problema };
  };

  // Tres situaciones que la pantalla no puede contar con las frases del caso derivado: la
  // agente aun lo evalua, o lo cerraron las reglas sin ajustador. En ninguna hay botones.
  const cerradoPorReglas = isClosedByRules(caso);
  const enRevision = reviewHint(caso.state);
  const decidido = estado.paso === "decided";

  // El paso de decidir existe cuando hay botones o cuando hay que decir por que no los hay. En
  // revision no hay aviso aparte: la introduccion ya dice que la agente evalua, y la pagina se
  // actualiza sola al salir de ahi.
  const conSeccionDeDecidir = !decidido && caso.available_actions.length > 0;
  const avisoSinDecision = !decidido && !conSeccionDeDecidir && enRevision === undefined;
  const hayPasoDeDecidir = conSeccionDeDecidir || avisoSinDecision;

  // Lo anotado para las reglas: lo que el servidor ofrece y lo que el visitante dejo escrito.
  const ofreceAnotar = caso.can_annotate_triage === true;
  const hayNota = caso.triage_note !== null && caso.triage_note !== undefined;
  const hayAnotaciones = ofreceAnotar || hayNota;

  // El panel del ajustador existe mientras tenga algo que ofrecer o que leer. Sin el, los datos
  // quedan solos y no se pegan a una columna vacia.
  const conPanel = hayPasoDeDecidir || hayAnotaciones;
  // Sin nada que decidir ni que anotar --lo cerraron las reglas, ya se decidio, espera al
  // asegurado-- el panel no invita a hacer de ajustador: dice como esta el caso (2026-10-14).
  const soloEstado = avisoSinDecision && !hayAnotaciones;

  // Los datos del reporte y la evaluacion de las reglas: es lo que el ajustador mira mientras
  // decide, y lo que cambia al guardar las anotaciones. Van en la superficie neutra de segundo
  // nivel, distinta a la del panel donde se decide.
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
        <h1 className={CASE_PAGE_TITLE}>
          {decidido ? t("visitor.done_title") : ownCaseTitle(caso.record_type)(t)}
        </h1>
        {/* El codigo no es el titulo: es un renglon pequeno que dice para que sirve (C10). */}
        <p className="text-caption text-fg-secondary" data-testid="visitor-case-number">
          {t("visitor.number", { case_number: caso.case_number })}
        </p>
        {decidido ? (
          <>
            <p>{t("visitor.done_body")}</p>
            {caso.resolution === null ? null : (
              <p data-testid="visitor-resolution">{resolutionLabel(caso.resolution)(t)}</p>
            )}
            <Button asChild variant="primary">
              <a href={conversationHref(sesion)}>{t("action.back_to_conversation")}</a>
            </Button>
          </>
        ) : (
          <>
            <p data-testid="visitor-intro">
              {cerradoPorReglas
                ? t("inbox.closed_by_rules.intro")
                : enRevision !== undefined
                  ? enRevision(t)
                  : t("visitor.intro")}
            </p>
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
          </>
        )}
      </header>

      {/*
        Los dos paneles (2026-10-14): quien decide necesita ver los datos mientras responde.
        **El orden del documento es el de pantalla angosta --los datos primero, despues el panel
        del ajustador--** y desde `desktop` la rejilla pone el del ajustador a la izquierda (ver
        `CASE_WORKSPACE_PANES`). El precio: en escritorio el lector de pantalla y el teclado
        pasan por los datos antes de llegar al formulario, que es tambien el orden en que se lee
        para decidir.
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

        {conPanel ? (
          <section
            aria-labelledby="visitor-adjuster-title"
            data-testid="visitor-adjuster"
            // La raya de la marca a la izquierda, el titulo y las marcas de los pasos en la marca:
            // es el unico panel de la pantalla que pide algo, y el resto son superficies neutras.
            // Sin tinte de fondo a proposito: un campo sobre un fondo con tinte de cobre bajaba el
            // borde del campo a 2,6 a 1 en oscuro, por debajo de los 3 a 1 que pide un control.
            className={cn(
              "flex flex-col gap-5 rounded-surface border border-hairline bg-surface p-4",
              !soloEstado && "border-l-4 border-l-brand",
              CASE_ADJUSTER_PANE,
            )}
          >
            <div className="flex flex-col gap-1">
              <h2
                id="visitor-adjuster-title"
                className={cn(BLOCK_TITLE, !soloEstado && "text-brand")}
              >
                {soloEstado ? t("visitor.status.title") : t("visitor.adjuster.title")}
              </h2>
              {conSeccionDeDecidir ? (
                <p className="text-small text-fg-secondary">{t("visitor.decide_intro")}</p>
              ) : null}
            </div>

            {/* Paso 1, antes de decidir: lo que revisaria un ajustador. El bloque no se pinta
                si el servidor no lo ofrece y no hay nada anotado. */}
            <VisitorTriageBlock
              note={caso.triage_note}
              canAnnotate={ofreceAnotar}
              amountSteps={caso.triage_amount_steps}
              onSave={anotar}
              step={hayPasoDeDecidir ? 1 : undefined}
            />

            {hayPasoDeDecidir ? (
              <section
                aria-labelledby={soloEstado ? "visitor-adjuster-title" : "visitor-decision-title"}
                data-testid="visitor-decision"
                className={cn(
                  "flex flex-col gap-3",
                  hayAnotaciones && "border-t border-hairline pt-5",
                )}
              >
                {soloEstado ? null : (
                  <StepHeading id="visitor-decision-title" step={hayAnotaciones ? 2 : undefined}>
                    {t("visitor.decision.title")}
                  </StepHeading>
                )}
                {conSeccionDeDecidir ? (
                  <DecisionForm
                    actions={caso.available_actions}
                    onSubmit={decidir}
                    idPrefix="visitor"
                  />
                ) : (
                  <InlineAlert tone="info" data-testid="visitor-no-actions">
                    {caso.state === "awaiting_insured"
                      ? t("inbox.decision.none_awaiting")
                      : cerradoPorReglas
                        ? t("inbox.closed_by_rules.note")
                        : caso.state === "closed"
                          ? t("inbox.decision.none_closed")
                          : t("inbox.decision.none_in_conversation")}
                  </InlineAlert>
                )}
              </section>
            ) : null}
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
