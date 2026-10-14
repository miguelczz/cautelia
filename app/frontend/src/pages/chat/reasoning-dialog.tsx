// El pensamiento de la agente sobre el caso, en una ventana (2026-10-09).
//
// Lo que el caso ya guarda, dicho por pasos y en palabras llanas: que entendio, que
// poliza confirmo, que busco y verifico por cada pregunta, que anoto y en que quedo.
// Es el `<dialog>` del navegador, como el panel de documentos: atrapa el foco, cierra
// con Escape y deja quieta la pagina de atras.

import { CheckIcon, CircleDashedIcon } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { caseReasoning, type ChatReasoning } from "../../shared/api-client/chat";
import { useLocale } from "../../shared/i18n/locale-provider";
import type { Translate } from "../../shared/i18n/translate";
import { recall, restoreAll } from "../../shared/own-text/own-text";
import { useAgentName } from "../../shared/site/agent-name";
import { Button } from "../../shared/ui/button";
import { cn } from "../../shared/ui/cn";
import { PanelBodySkeleton } from "../../shared/ui/page-skeletons";
import { lockPageScroll } from "../../shared/ui/scroll-lock";
import { fieldLabel } from "../inbox/inbox-labels";

type Answer = ChatReasoning["answers"][number];

function whatIUnderstood(recordType: string, t: Translate): string {
  if (recordType === "coverage_inquiry") {
    return t("chat.reasoning.wants_question");
  }
  if (recordType === "quote_request") {
    return t("chat.reasoning.wants_quote");
  }
  return t("chat.reasoning.wants_claim");
}

function whereItStands(state: string, t: Translate): string {
  if (state === "derived") {
    return t("chat.reasoning.state_derived");
  }
  // Mientras la agente aun evalua el caso no esta con un ajustador ni sigue «abierto»:
  // se dice lo que esta haciendo, con las frases que ya usa la pagina de casos.
  if (state === "verifying") {
    return t("cases.group.verifying");
  }
  if (state === "deciding") {
    return t("cases.group.deciding");
  }
  if (state === "closed") {
    return t("chat.reasoning.state_closed");
  }
  return t("chat.reasoning.state_open");
}

function howItWasAnswered(answer: Answer, t: Translate): string {
  const verificadas = (answer.clauses ?? []).filter((c) => c.verified).length;
  if (answer.outcome === "verified") {
    return t("chat.reasoning.outcome_verified", { count: String(verificadas) });
  }
  if (answer.outcome === "no_clause_found") {
    return t("chat.reasoning.outcome_no_clause");
  }
  if (answer.outcome === "rejected") {
    return t("chat.reasoning.outcome_rejected");
  }
  return t("chat.reasoning.outcome_unverifiable");
}

/** Lo anotado; si no se puede mostrar, que se anoto; y si no, si falta o es opcional. */
function notedText(campo: ChatReasoning["fields"][number], t: Translate): string {
  const anotado = campo.value ?? null;
  if (anotado !== null) {
    return anotado;
  }
  if (campo.done) {
    return t("chat.reasoning.noted");
  }
  return campo.optional === true ? t("chat.reasoning.optional") : t("chat.reasoning.missing");
}

function Step({ title, children }: { readonly title: string; readonly children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2 border-t border-hairline pt-4 first:border-t-0 first:pt-0">
      <h3 className="text-small font-medium text-fg-secondary">{title}</h3>
      <div className="flex flex-col gap-2 text-body text-fg">{children}</div>
    </section>
  );
}

function ReasoningBody({
  reasoning,
  tenantId,
}: {
  readonly reasoning: ChatReasoning;
  readonly tenantId: string;
}) {
  const { t } = useLocale();
  // La pregunta llega tapada de la base; quien la hizo la lee como la escribio
  // (C5, 2026-10-12). Lo que no tiene copia que encaje se queda como llego.
  const preguntas = useMemo(
    () =>
      restoreAll(
        reasoning.answers.map((respuesta) => respuesta.question),
        recall(tenantId),
      ),
    [reasoning.answers, tenantId],
  );
  return (
    <div className="flex flex-col gap-4">
      <Step title={t("chat.reasoning.step_understood")}>
        <p>{whatIUnderstood(reasoning.record_type, t)}</p>
      </Step>
      <Step title={t("chat.reasoning.step_policy")}>
        <p>
          {reasoning.policy_ref === null
            ? t("chat.reasoning.policy_missing")
            : t("chat.reasoning.policy_confirmed", { policy: reasoning.policy_ref })}
        </p>
      </Step>
      {reasoning.answers.map((respuesta, indice) => (
        <Step
          key={`${String(indice)}-${respuesta.question}`}
          title={t("chat.reasoning.step_checked")}
        >
          <p className="text-fg-secondary">
            {t("chat.reasoning.you_asked", {
              question: preguntas.at(indice) ?? respuesta.question,
            })}
          </p>
          <p>{howItWasAnswered(respuesta, t)}</p>
          {(respuesta.clauses ?? []).length === 0 ? null : (
            <ul className="flex flex-col gap-2" data-testid="reasoning-clauses">
              {(respuesta.clauses ?? []).map((clausula) => (
                <li key={clausula.clause_id} className="flex gap-2">
                  {clausula.verified ? (
                    <CheckIcon aria-hidden="true" size={18} className="mt-1 shrink-0 text-tenant" />
                  ) : (
                    <CircleDashedIcon
                      aria-hidden="true"
                      size={18}
                      className="mt-1 shrink-0 text-fg-secondary"
                    />
                  )}
                  <span>
                    <span className="font-medium">{clausula.part}</span>
                    {clausula.claim === "" ? null : `: ${clausula.claim}`}
                    <span className="sr-only">
                      {" "}
                      {clausula.verified
                        ? t("chat.reasoning.clause_verified")
                        : t("chat.reasoning.clause_not_verified")}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Step>
      ))}
      {reasoning.fields.length === 0 ? null : (
        <Step title={t("chat.reasoning.step_noted")}>
          {/* Cada dato con lo que quedo anotado, no solo "Anotado" (2026-10-11). */}
          <dl className="grid gap-x-6 gap-y-3 tablet:grid-cols-2" data-testid="reasoning-fields">
            {reasoning.fields.map((campo) => (
              <div key={campo.field_key} className="flex min-w-0 flex-col">
                <dt className="text-small text-fg-secondary">{fieldLabel(campo.label_key)(t)}</dt>
                <dd
                  className={cn(
                    "whitespace-pre-line break-words",
                    campo.done ? "text-fg" : "text-fg-secondary",
                  )}
                >
                  {notedText(campo, t)}
                </dd>
              </div>
            ))}
          </dl>
        </Step>
      )}
      <Step title={t("chat.reasoning.step_next")}>
        <p>{whereItStands(reasoning.state, t)}</p>
        <p className="text-small text-fg-secondary">{t("chat.reasoning.adjuster_decides")}</p>
      </Step>
    </div>
  );
}

function ReasoningPanel({
  tenantId,
  onClose,
}: {
  readonly tenantId: string;
  readonly onClose: () => void;
}) {
  const { t, locale } = useLocale();
  const agente = useAgentName(tenantId);
  // Se vuelve a leer cada vez que se abre: el caso avanza con la conversacion.
  const consulta = useQuery({
    queryKey: ["chat", "reasoning", tenantId, locale],
    queryFn: () => caseReasoning(tenantId, locale),
    staleTime: 0,
  });

  return (
    <div className="flex flex-col">
      <header className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-hairline bg-page px-4 py-3 tablet:px-6">
        <h2 id={`${tenantId}-reasoning-title`} className="text-lead font-medium text-fg">
          {t("chat.reasoning.title", { agent: agente })}
        </h2>
        <Button variant="secondary" className="shrink-0" onClick={onClose}>
          {t("documents.close")}
        </Button>
      </header>
      <div className="px-4 py-5 tablet:px-6">
        {consulta.isPending ? (
          <PanelBodySkeleton />
        ) : consulta.data === null || consulta.data === undefined ? (
          <p className="text-body text-fg-secondary">{t("chat.reasoning.empty")}</p>
        ) : (
          <ReasoningBody reasoning={consulta.data} tenantId={tenantId} />
        )}
      </div>
    </div>
  );
}

interface ReasoningButtonProps {
  readonly tenantId: string;
  /** Lo que se ve en el boton: icono y nombre, como los de al lado. */
  readonly children: ReactNode;
  readonly className?: string;
  /** El nombre accesible completo, para cuando en telefono solo se ve el icono. */
  readonly label: string;
}

/** El boton que abre el pensamiento, con la ventana dentro. */
export function ReasoningButton({ tenantId, children, className, label }: ReasoningButtonProps) {
  const ventana = useRef<HTMLDialogElement>(null);
  const [abierta, setAbierta] = useState(false);

  useEffect(() => {
    const dialogo = ventana.current;
    if (dialogo !== null && abierta && !dialogo.open) {
      dialogo.showModal();
    }
  }, [abierta]);

  useEffect(() => (abierta ? lockPageScroll() : undefined), [abierta]);

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="compact"
        className={className}
        aria-label={label}
        data-testid="chat-reasoning"
        onClick={() => {
          setAbierta(true);
        }}
      >
        {children}
      </Button>
      <dialog
        ref={ventana}
        aria-labelledby={`${tenantId}-reasoning-title`}
        onClose={() => {
          setAbierta(false);
        }}
        className={cn(
          "m-auto w-[min(44rem,calc(100vw-2rem))] max-h-[calc(100dvh-2rem)] overflow-y-auto overscroll-contain",
          "rounded-surface border border-hairline bg-page p-0 text-fg shadow-raised backdrop:bg-scrim",
        )}
        data-testid="reasoning-dialog"
      >
        {abierta ? (
          <ReasoningPanel tenantId={tenantId} onClose={() => ventana.current?.close()} />
        ) : null}
      </dialog>
    </>
  );
}
