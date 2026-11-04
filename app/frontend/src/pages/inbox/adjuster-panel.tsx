// El panel «Cómo decidió el ajustador» (plan 09, fase 5, tanda 3, 2026-11-04).
//
// Cuenta, con lo que el servidor ya guardó, cómo decidió el ajustador de IA un caso derivado:
// la decisión con su etiqueta, el resumen, la explicación y los seis pasos con las fuentes de
// cada uno. Lo comparten la pantalla del visitante y la del personal, y **en las dos es de solo
// lectura**: quien mira no decide ni anota aquí.
//
// **Cuatro estados, y ninguno cuenta lo que no pasó.**
// - En curso: los pasos que ya existen y, donde faltan, el lugar que ocuparán (esqueleto con la
//   forma de la pantalla, sin palabras de implementación). La pantalla lo vuelve a leer sola.
// - Decidido: decisión, resumen, explicación, aviso de que la escribió una IA y los pasos.
// - En espera de cupo (`capped`): el ajustador de hoy ya atendió lo que puede; el caso espera.
// - Falló: dice «sigue en revisión». **Nunca** el motivo técnico del fallo ni una decisión que
//   no se tomó, y los pasos que llegaron a existir tampoco se enseñan.
//
// **Las fuentes se ven con nombre legible.** Una cláusula, con la parte de la póliza y su cita;
// una regla, como «Regla 1 de la aseguradora» (el identificador versionado es de quien audita,
// no de quien lee); una página externa, como enlace que solo se abre si es `https`.
//
// **El estado se anuncia sin ser ruidoso:** una sola línea (`aria-live="polite"`,
// `aria-atomic`) que cambia cuando llega un paso o cuando termina; los pasos no son región viva.
// El esqueleto pulsa solo si la persona no pidió menos movimiento (`motion-safe`).

import { useId } from "react";

import type { AdjusterRunOut, AdjusterSourceOut, InboxAction } from "../../shared/api-client/inbox";
import { useLocale } from "../../shared/i18n/locale-provider";
import type { Message } from "../../shared/i18n/translate";
import { cn } from "../../shared/ui/cn";
import { isSafeExternalLink } from "../../shared/ui/external-link";
import { BLOCK_TITLE } from "../../shared/ui/page-layout";
import { Skeleton } from "../../shared/ui/skeleton";
import { Tag } from "../../shared/ui/tag";
import { resolutionLabel } from "./inbox-labels";
import { StepHeading } from "./step-heading";

type StepId = NonNullable<AdjusterRunOut["steps"]>[number]["id"];

/** Los seis pasos, en el orden en que el ajustador los da. */
const STEP_ORDER: readonly StepId[] = [
  "case_read",
  "policy_read",
  "clauses",
  "rules",
  "vehicle_value",
  "decision",
];

/**
 * El titular de cada paso, por su identificador y con la clave escrita literal. Es un `switch`
 * exhaustivo y no un objeto indexado: un paso nuevo del contrato falla aqui al compilar en vez de
 * salir sin titular.
 */
function stepTitle(id: StepId): Message {
  switch (id) {
    case "case_read":
      return (t) => t("adjuster.step.case_read.title");
    case "policy_read":
      return (t) => t("adjuster.step.policy_read.title");
    case "clauses":
      return (t) => t("adjuster.step.clauses.title");
    case "rules":
      return (t) => t("adjuster.step.rules.title");
    case "vehicle_value":
      return (t) => t("adjuster.step.vehicle_value.title");
    case "decision":
      return (t) => t("adjuster.step.decision.title");
  }
}

/** La resolucion que deja cada accion: la etiqueta de la decision es la de la resolucion. */
function resolutionOf(action: InboxAction): string {
  switch (action) {
    case "approve":
      return "approved";
    case "reject":
      return "rejected";
    case "mark_sent":
      return "sent_to_insurer";
  }
}

type Panel = "running" | "decided" | "capped" | "failed";

/**
 * Qué estado dibuja el panel. Una corrida `decided` sin decisión, titular o explicación se trata
 * como fallida: es mejor decir «sigue en revisión» que enseñar un hueco como si fuera decisión.
 * Sin corrida --el caso acaba de derivarse y el servidor la está abriendo-- es «en curso».
 */
export function panelState(run: AdjusterRunOut | null | undefined): Panel {
  if (run === null || run === undefined) {
    return "running";
  }
  if (run.status === "decided") {
    const completa =
      run.decision !== null &&
      run.decision !== undefined &&
      typeof run.headline === "string" &&
      run.headline !== "" &&
      typeof run.explanation === "string" &&
      run.explanation !== "";
    return completa ? "decided" : "failed";
  }
  return run.status;
}

function SourceView({
  source,
  ruleNumber,
}: {
  readonly source: AdjusterSourceOut;
  /** Para una regla, su número entre las del paso. */
  readonly ruleNumber: number;
}) {
  const { t } = useLocale();
  switch (source.kind) {
    case "clause":
      return (
        <>
          <span className="text-caption text-fg-secondary">{t("adjuster.source.kind.clause")}</span>{" "}
          <span>{source.label}</span>{" "}
          <span className="font-mono text-caption text-fg-secondary">{source.ref}</span>
        </>
      );
    case "rule":
      return <span>{t("adjuster.source.rule", { number: ruleNumber })}</span>;
    case "web": {
      const direccion = source.url ?? source.ref;
      if (!isSafeExternalLink(direccion)) {
        return (
          <>
            <span className="text-caption text-fg-secondary">{t("adjuster.source.kind.web")}</span>{" "}
            <span>{source.label}</span>
          </>
        );
      }
      return (
        <>
          <span className="text-caption text-fg-secondary">{t("adjuster.source.kind.web")}</span>{" "}
          <a
            href={direccion}
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2"
          >
            {source.label}
            <span className="sr-only"> {t("adjuster.source.new_tab")}</span>
          </a>
        </>
      );
    }
    case "policy":
    case "case":
      return <span>{source.label}</span>;
  }
}

function Sources({ sources }: { readonly sources: readonly AdjusterSourceOut[] }) {
  const { t } = useLocale();
  if (sources.length === 0) {
    return null;
  }
  return (
    <ul
      aria-label={t("adjuster.panel.sources")}
      className="flex flex-col gap-1 text-small"
      data-testid="adjuster-sources"
    >
      {sources.map((fuente, indice) => (
        <li key={`${fuente.kind}:${fuente.ref}`}>
          <SourceView
            source={fuente}
            // El numero de una regla es su lugar entre las reglas del paso.
            ruleNumber={sources.slice(0, indice + 1).filter((otra) => otra.kind === "rule").length}
          />
        </li>
      ))}
    </ul>
  );
}

export interface AdjusterPanelProps {
  /** La corrida que manda el servidor, o nada cuando el caso acaba de derivarse. */
  readonly run: AdjusterRunOut | null | undefined;
  /** Para la prueba del orden del documento y para que la pantalla lo coloque. */
  readonly className?: string | undefined;
  /** El identificador del encabezado, por si la pantalla necesita apuntarlo. */
  readonly idPrefix?: string | undefined;
}

export function AdjusterPanel({ run, className, idPrefix = "adjuster" }: AdjusterPanelProps) {
  const { t } = useLocale();
  const generado = useId();
  const titleId = `${idPrefix}-title-${generado}`;
  const estado = panelState(run);
  const pasos = estado === "decided" || estado === "running" ? (run?.steps ?? []) : [];
  const decidido = estado === "decided";

  const linea: string = (() => {
    switch (estado) {
      case "running":
        return t("adjuster.panel.running", { done: pasos.length, total: STEP_ORDER.length });
      case "decided":
        return t("adjuster.panel.decided");
      case "capped":
        return t("adjuster.panel.capped");
      case "failed":
        return t("adjuster.panel.failed");
    }
  })();

  return (
    <section
      aria-labelledby={titleId}
      data-testid="adjuster-panel"
      data-status={estado}
      // La raya de la marca y el título en la marca, como el panel de antes: es el panel de la
      // pantalla donde el ajustador cuenta lo que hizo. Los tokens de la marca ya evitan el cobre
      // como letra sobre fondo claro.
      className={cn(
        "flex flex-col gap-4 rounded-surface border border-hairline border-l-4 border-l-brand bg-surface p-4",
        className,
      )}
    >
      <div className="flex flex-col gap-1">
        <h2 id={titleId} className={cn(BLOCK_TITLE, "text-brand")}>
          {decidido ? t("adjuster.panel.title") : t("adjuster.panel.title_pending")}
        </h2>
        {/* La única región viva del panel: una línea que cambia cuando llega un paso o termina. */}
        <p
          aria-live="polite"
          aria-atomic="true"
          className="text-small text-fg-secondary"
          data-testid="adjuster-status"
        >
          {linea}
        </p>
      </div>

      {decidido && run?.decision !== undefined && run.decision !== null ? (
        <div className="flex flex-col gap-3" data-testid="adjuster-decision">
          <p className="flex flex-wrap items-center gap-2">
            <span className="text-caption text-fg-secondary">{t("adjuster.panel.decision")}</span>
            <Tag
              tone={
                run.decision === "approve"
                  ? "success"
                  : run.decision === "reject"
                    ? "danger"
                    : "neutral"
              }
              data-testid="adjuster-decision-label"
            >
              {resolutionLabel(resolutionOf(run.decision))(t)}
            </Tag>
          </p>
          <p className="text-lead font-medium" data-testid="adjuster-headline">
            {run.headline}
          </p>
          <p className="whitespace-pre-line" data-testid="adjuster-explanation">
            {run.explanation}
          </p>
          <p className="text-caption text-fg-secondary" data-testid="adjuster-ai-notice">
            {t("adjuster.panel.ai_notice")}
          </p>
        </div>
      ) : null}

      {estado === "running" || decidido ? (
        <ol
          aria-label={t("adjuster.panel.steps")}
          className="flex flex-col gap-5"
          data-testid="adjuster-steps"
        >
          {pasos.map((paso, indice) => (
            <li
              key={paso.id}
              className="flex flex-col gap-2"
              data-testid={`adjuster-step-${paso.id}`}
            >
              <StepHeading id={`${titleId}-${paso.id}`} step={indice + 1}>
                {stepTitle(paso.id)(t)}
              </StepHeading>
              <p className="whitespace-pre-line">{paso.text}</p>
              <Sources sources={paso.sources ?? []} />
            </li>
          ))}
          {/* Los pasos que faltan: su lugar y su titular, ocultos al lector (la línea viva ya
              dice cuántos van). Con movimiento reducido el esqueleto no pulsa. */}
          {estado === "running"
            ? STEP_ORDER.slice(pasos.length).map((id, indice) => (
                <li
                  key={id}
                  aria-hidden="true"
                  className="flex flex-col gap-2"
                  data-testid="adjuster-step-pending"
                >
                  <p className={cn(BLOCK_TITLE, "flex items-center gap-3 text-fg-secondary")}>
                    <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-pill border border-hairline font-body text-small">
                      {pasos.length + indice + 1}
                    </span>
                    {stepTitle(id)(t)}
                  </p>
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-2/3" />
                </li>
              ))
            : null}
        </ol>
      ) : null}
    </section>
  );
}
