// Un caso de ejemplo "como lo ve un ajustador", solo lectura (2026-10-11).
//
// **Comparte los bloques de evidencia con la bandeja y con el caso del visitante y nada
// mas** (`evidence-blocks.tsx`): datos, conversacion, clausulas citadas, regla, controles
// y traza. No monta el formulario de decision ni la correccion de campos, y el servidor
// tampoco ofrece ninguna accion para estos casos: lo que se ve es lo que hay, y para
// decidir uno como ajustador el visitante crea el suyo en el chat.
//
// **Un caso que no es de ejemplo se ve igual que uno que no existe.** El servidor
// responde lo mismo ante un caso de visitante, uno de otra aseguradora y un
// identificador inventado, y esta pantalla no intenta distinguirlos tampoco.

import { ArrowLeftIcon } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";

import { casesHref, INSURERS_LINK } from "../../app/surfaces";
import { exampleCaseQueryOptions } from "../../shared/api-client/examples";
import { toProblemView } from "../../shared/api-client/problems";
import { siteQueryOptions } from "../../shared/api-client/site";
import { useLocale } from "../../shared/i18n/locale-provider";
import { tenantAccentStyle } from "../../shared/theme/tenant-accent";
import { Button } from "../../shared/ui/button";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { CASE_COLUMN_WIDTH, CASE_PAGE_TITLE, DETAIL_TITLE } from "../../shared/ui/page-layout";
import { PageSkeleton } from "../../shared/ui/page-skeletons";
import { Tag } from "../../shared/ui/tag";
import {
  CitationList,
  ControlsBlock,
  DecisionSummary,
  FieldCompleteness,
  OpenBlock,
  ResponseBlock,
  RuleBlock,
  TranscriptView,
} from "../inbox/evidence-blocks";
import {
  caseReasonLabel,
  resolutionLabel,
  ruleCategoryLabel,
  stateLabel,
} from "../inbox/inbox-labels";
import { caseKindLabel } from "./cases-labels";

const CONTENEDOR = `mx-auto flex w-full ${CASE_COLUMN_WIDTH} flex-col gap-4 px-4 py-6 tablet:py-10`;

export function ExampleCasePage({
  tenantId,
  caseId,
}: {
  readonly tenantId: string;
  readonly caseId: string;
}) {
  const { t } = useLocale();
  const consulta = useQuery(exampleCaseQueryOptions(tenantId, caseId));
  // El nombre y el acento de la aseguradora vienen del directorio del sitio. Si todavia
  // no llego, la pagina se dibuja igual: el caso no depende de el.
  const sitio = useQuery(siteQueryOptions());
  const aseguradora = sitio.data?.tenants.find((tenant) => tenant.tenant_id === tenantId);
  const volver = (
    <Button asChild variant="ghost" size="compact" className="-ml-4 self-start">
      <a href={casesHref(tenantId)} data-testid="example-back">
        <ArrowLeftIcon aria-hidden="true" focusable="false" size={16} />
        {t("cases.example.back")}
      </a>
    </Button>
  );

  if (consulta.isPending) {
    return <PageSkeleton kind="case" />;
  }

  if (consulta.isError) {
    const problema = toProblemView(consulta.error);
    return (
      <main className={CONTENEDOR} data-testid="example-case-problem">
        {volver}
        {problema.code === "not_found" ? (
          <h1 className={DETAIL_TITLE}>{t("inbox.case.not_found")}</h1>
        ) : (
          <InlineAlert
            tone="danger"
            role="alert"
            action={
              <Button
                variant="secondary"
                onClick={() => {
                  void consulta.refetch();
                }}
              >
                {t("action.retry")}
              </Button>
            }
          >
            {problema.message(t)}
          </InlineAlert>
        )}
      </main>
    );
  }

  const caso = consulta.data;
  return (
    <main
      className={CONTENEDOR}
      style={tenantAccentStyle(aseguradora?.brand)}
      data-tenant-scope=""
      data-testid="example-case"
    >
      <header className="flex flex-col gap-4">
        {volver}
        <div className="flex flex-col gap-1">
          <h1 className={CASE_PAGE_TITLE}>
            {t("cases.example.title", { case_number: caso.case_number })}
          </h1>
          <p className="text-body text-fg-secondary">
            {aseguradora === undefined ? null : (
              <span className="font-medium text-tenant" data-testid="example-insurer">
                {aseguradora.display_name}
                {" · "}
              </span>
            )}
            {caseKindLabel(caso.record_type)(t)}
          </p>
        </div>

        {/* Que es esta pantalla, y a donde ir para decidir un caso de verdad. */}
        <InlineAlert
          tone="info"
          data-testid="example-note"
          action={
            <Button asChild variant="primary" className="shrink-0 self-start whitespace-nowrap">
              <a href={INSURERS_LINK.href}>{t("cases.start")}</a>
            </Button>
          }
        >
          {t("cases.example.note")}
        </InlineAlert>

        {/* Los datos del caso en una cuadricula de dos columnas: cada dato con su rotulo
            arriba, alineados por fila. Sueltos y en renglones que se acomodaban solos, cada
            uno empezaba donde lo dejaba el anterior. */}
        <dl className="grid grid-cols-1 gap-x-6 gap-y-4 rounded-surface border border-hairline bg-surface p-4 tablet:grid-cols-2">
          <div className="flex min-w-0 flex-col gap-0.5">
            <dt className="text-caption text-fg-secondary">{t("inbox.case.reason")}</dt>
            <dd data-testid="example-reason">{caseReasonLabel(caso)(t)}</dd>
          </div>
          <div className="flex min-w-0 flex-col gap-0.5">
            <dt className="text-caption text-fg-secondary">{t("inbox.case.category")}</dt>
            <dd className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <Tag>{stateLabel(caso.state)(t)}</Tag>
              {caso.rule_category === null ? (
                <span className="text-caption text-fg-secondary">
                  {t("inbox.case.no_category")}
                </span>
              ) : (
                <Tag tone="brand">{ruleCategoryLabel(caso.rule_category)(t)}</Tag>
              )}
            </dd>
          </div>
          <div className="flex min-w-0 flex-col gap-0.5">
            <dt className="text-caption text-fg-secondary">{t("inbox.case.completeness")}</dt>
            <dd className="tabular-nums" data-testid="example-completeness">
              {t("inbox.completeness", {
                complete: caso.completeness_complete,
                total: caso.completeness_total,
              })}
            </dd>
          </div>
          <div className="flex min-w-0 flex-col gap-0.5">
            <dt className="text-caption text-fg-secondary">{t("inbox.explanation.title")}</dt>
            <dd className="flex flex-wrap gap-x-2">
              <DecisionSummary detail={caso} />
            </dd>
          </div>
          {caso.resolution === null ? null : (
            <div className="flex min-w-0 flex-col gap-0.5">
              <dt className="text-caption text-fg-secondary">{t("inbox.case.resolution")}</dt>
              <dd>{resolutionLabel(caso.resolution)(t)}</dd>
            </div>
          )}
        </dl>
      </header>

      {/* Los mismos bloques que ve un ajustador, sin corregir campos ni decidir. */}
      <OpenBlock title={t("inbox.block.fields")} testId="block-fields">
        <FieldCompleteness fields={caso.fields} />
      </OpenBlock>

      <OpenBlock title={t("inbox.block.transcript")} testId="block-transcript">
        <TranscriptView detail={caso} />
      </OpenBlock>

      <OpenBlock title={t("inbox.block.citations")} testId="block-citations">
        <CitationList answers={caso.coverage_answers} conversationLocale={caso.language} />
      </OpenBlock>

      <RuleBlock detail={caso} />
      <ControlsBlock detail={caso} />
      {/*
        Un caso de ejemplo es publico: la direccion de una traza no se muestra aqui aunque
        el servidor la mandara. El servidor no la manda en esta ruta; esto es la segunda llave.
      */}
      <ResponseBlock detail={{ ...caso, trace_url: null }} />
    </main>
  );
}
