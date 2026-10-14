// Una columna de la comparacion: una aseguradora, con su acento, su agente, su
// poliza de ejemplo y lo que contesto.
//
// El acento sale de la marca que sirve el directorio (`data-tenant-scope`), igual
// que en el inicio y en el chat: aqui no se sabe que aseguradora usa que color. Que
// las tres respuestas vienen de polizas distintas se ve sin que la vista lo
// redacte (BR3.2): el color, el monograma, el numero de poliza y las clausulas
// citadas, que son las de cada una.

import { FileTextIcon } from "@phosphor-icons/react";
import { useLocale } from "../../shared/i18n/locale-provider";
import { useAgentName } from "../../shared/site/agent-name";
import { tenantAccentStyle } from "../../shared/theme/tenant-accent";
import { Button } from "../../shared/ui/button";
import { cn } from "../../shared/ui/cn";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { Monogram } from "../../shared/ui/monogram";
import { Skeleton } from "../../shared/ui/skeleton";
import { Tag } from "../../shared/ui/tag";
import { phraseFor } from "../chat/chat-copy";
import { Citation, withPositions } from "../chat/citation";
import { stateName } from "./comparison-labels";
import type { ComparisonColumn, ComparisonInsurer } from "./comparison-state";

export interface ColumnProps {
  readonly insurer: ComparisonInsurer;
  readonly column: ComparisonColumn;
  /** Vuelve a mandar la pregunta solo a esta aseguradora. */
  readonly onAskAgain: () => void;
}

export function Column({ insurer, column, onAskAgain }: ColumnProps) {
  const { t } = useLocale();
  const agente = useAgentName(insurer.tenantId);
  const titulo = `comparison-col-${insurer.tenantId}`;

  return (
    <section
      aria-labelledby={titulo}
      data-testid="comparison-column"
      data-tenant={insurer.tenantId}
      data-state={column.state}
      data-tenant-scope=""
      style={tenantAccentStyle(insurer.brand)}
      className="flex min-w-0 flex-col overflow-hidden rounded-surface border border-hairline bg-surface"
    >
      {/* La franja de su color: decorativa, el nombre ya dice quien es. */}
      <div aria-hidden="true" className="h-1 bg-tenant" />
      <header className="flex flex-col gap-3 p-4 tablet:p-5">
        <div className="flex items-start gap-3">
          {insurer.brand === null ? null : (
            <Monogram shape={insurer.brand.monogram} className="size-10" />
          )}
          <div className="flex min-w-0 flex-1 flex-col">
            <h2 id={titulo} className="font-display text-lead font-medium text-balance text-tenant">
              {insurer.displayName}
            </h2>
            <p className="text-small text-fg-secondary">
              {t("comparison.disclosure.assistant", { agent: agente })}
            </p>
          </div>
          {column.state === "idle" ? null : (
            <Tag tone={tagTone(column.state)} className="shrink-0">
              {stateName(column.state)(t)}
            </Tag>
          )}
        </div>
      </header>
      {/* Cada columna anuncia la suya: una que llega no obliga a releer las otras. */}
      <div
        aria-live="polite"
        aria-busy={column.state === "loading"}
        className="flex flex-1 flex-col gap-3 border-t border-hairline p-4 tablet:p-5"
      >
        <ColumnBody insurer={insurer} column={column} onAskAgain={onAskAgain} />
      </div>
    </section>
  );
}

function tagTone(
  state: Exclude<ComparisonColumn["state"], "idle">,
): "neutral" | "brand" | "success" | "danger" | "warning" {
  switch (state) {
    case "loading":
      return "neutral";
    case "answered":
      return "success";
    case "failed":
      return "danger";
    case "interrupted":
    case "rejected":
      return "warning";
  }
}

/**
 * De que poliza son las clausulas de abajo (E2, 2026-10-12). Antes iba en el encabezado,
 * lejos de lo que explica; aqui va justo encima de las clausulas, que es donde dice algo.
 */
function PolicyLine({ insurer }: { readonly insurer: ComparisonInsurer }) {
  const { t } = useLocale();
  return (
    <p
      data-testid="comparison-policy"
      className="flex items-start gap-1.5 text-caption text-fg-secondary"
    >
      <FileTextIcon
        aria-hidden="true"
        focusable="false"
        size={16}
        className="mt-px shrink-0 text-tenant"
      />
      <span className="min-w-0 break-words">
        {insurer.issuedBy === null
          ? t("comparison.column.policy", { policy: insurer.examplePolicy })
          : t("comparison.column.policy_issued_by", {
              policy: insurer.examplePolicy,
              issuer: insurer.issuedBy,
            })}
      </span>
    </p>
  );
}

/** Una barra del esbozo: quieta sin pregunta, latiendo con ella. */
function Bar({ pulse, className }: { readonly pulse: boolean; readonly className: string }) {
  if (pulse) {
    return <Skeleton className={cn("rounded-pill", className)} />;
  }
  return <div aria-hidden="true" className={cn("rounded-pill bg-surface-alt", className)} />;
}

/**
 * El esbozo de una respuesta: unas lineas de texto y una tarjeta de clausula. Sin
 * pregunta esta quieto y con pregunta late; es la misma forma, asi que pasar de uno a
 * otro no mueve nada.
 */
function AnswerOutline({ pulse }: { readonly pulse: boolean }) {
  return (
    <div aria-hidden="true" className="flex flex-col gap-4">
      <div className="flex flex-col gap-2.5">
        <Bar pulse={pulse} className="h-2.5 w-full" />
        <Bar pulse={pulse} className="h-2.5 w-11/12" />
        <Bar pulse={pulse} className="h-2.5 w-2/3" />
      </div>
      <div className="flex items-center gap-3 rounded-control border border-dashed border-hairline p-3">
        <div
          className={cn(
            "size-5 shrink-0 rounded-pill bg-tenant/25",
            pulse && "motion-safe:animate-pulse",
          )}
        />
        <div className="flex flex-1 flex-col gap-2">
          <Bar pulse={pulse} className="h-2.5 w-1/2" />
          <Bar pulse={pulse} className="h-2 w-1/3" />
        </div>
      </div>
    </div>
  );
}

function ColumnBody({ insurer, column, onAskAgain }: ColumnProps) {
  const { t } = useLocale();

  switch (column.state) {
    case "idle":
      return (
        <>
          <p className="text-fg-secondary">{t("comparison.column.idle")}</p>
          <AnswerOutline pulse={false} />
        </>
      );
    case "loading":
      return (
        <>
          <p className="text-fg-secondary">
            {t("comparison.column.loading", { insurer: insurer.displayName })}
          </p>
          <AnswerOutline pulse />
        </>
      );
    case "answered":
      return column.answer.kind === "no_clause" ? (
        <p>{phraseFor("policy_rag.coverage.no_clause_found")(t)}</p>
      ) : (
        <>
          <p className="whitespace-pre-line">{column.answer.text}</p>
          {/* La clausula va al pie de la tarjeta: las tres columnas tienen la misma altura y
              asi su "Ver la clausula exacta" queda a un mismo nivel, diga lo que diga cada
              respuesta. Encima de las clausulas, de que poliza son. */}
          <div className="mt-auto flex flex-col gap-3">
            {column.answer.citations.length === 0 ? null : <PolicyLine insurer={insurer} />}
            {withPositions(column.answer.citations).map(({ citation: cita, position }) => (
              <Citation
                key={cita.clause_id}
                citation={cita}
                conversationLocale={column.answer.language}
                position={position}
              />
            ))}
          </div>
        </>
      );
    case "failed":
      // Se arregla en el proveedor de la verificacion, no en una cuota.
      return (
        <InlineAlert
          tone="danger"
          data-testid="comparison-failed"
          action={<AskAgain onClick={onAskAgain} />}
        >
          <p>{t("comparison.column.failed", { insurer: insurer.displayName })}</p>
        </InlineAlert>
      );
    case "interrupted":
      // No es un fallo de la poliza: la respuesta se perdio al salir de la pagina.
      return (
        <InlineAlert
          tone="warning"
          data-testid="comparison-interrupted"
          action={<AskAgain onClick={onAskAgain} />}
        >
          <p>{t("comparison.column.interrupted")}</p>
        </InlineAlert>
      );
    case "rejected":
      // Se arregla en la cuota. La frase sale de la clave que mando el chat.
      return (
        <InlineAlert tone="warning" data-testid="comparison-rejected" data-limit={column.limit}>
          <div className="flex flex-col gap-1">
            <p className="font-medium">{t("comparison.column.rejected_title")}</p>
            <p>{phraseFor(column.copyKey)(t)}</p>
          </div>
        </InlineAlert>
      );
  }
}

function AskAgain({ onClick }: { readonly onClick: () => void }) {
  const { t } = useLocale();
  return (
    <Button variant="tenant-outline" size="compact" onClick={onClick}>
      {t("comparison.column.retry")}
    </Button>
  );
}
