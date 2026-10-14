// La pagina "Casos" (2026-10-11): que es un caso, el caso propio de quien visita y los
// casos de ejemplo de cada aseguradora.
//
// **Solo dos fuentes, y ninguna muestra casos de otros visitantes.** Los de ejemplo
// los escribe el generador sintetico y el servidor los entrega sin credencial; el
// propio sale de la conversacion de chat de este navegador. Los casos de las llamadas
// no se listan aqui. La regla es de la pagina y no una cortesia: no hay ninguna
// consulta que traiga la lista de la aseguradora.
//
// Corta y de arriba abajo: que es un caso, el tuyo, y los de ejemplo con el selector
// de aseguradora de la pagina de polizas. Los de ejemplo se agrupan por estado, en el
// orden que decide el servidor, y cada estado dice en una linea que esta pasando.

import { CaretRightIcon } from "@phosphor-icons/react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { exampleCaseHref, INSURERS_LINK, tenantSurfaceHref } from "../../app/surfaces";
import {
  exampleCasesQueryOptions,
  ownCaseQueryOptions,
  type ChatCaseStatus,
  type ExampleCaseItem,
} from "../../shared/api-client/examples";
import type { CaseState } from "../../shared/api-client/inbox";
import { toProblemView } from "../../shared/api-client/problems";
import { siteQueryOptions, type TenantPresentation } from "../../shared/api-client/site";
import { useLocale } from "../../shared/i18n/locale-provider";
import { tenantAccentStyle } from "../../shared/theme/tenant-accent";
import { Button } from "../../shared/ui/button";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { Monogram } from "../../shared/ui/monogram";
import { LONG_PAGE_CONTENT, PAGE_TITLE, SECTION_TITLE } from "../../shared/ui/page-layout";
import { PageSkeleton, RowsSkeleton } from "../../shared/ui/page-skeletons";
import { SegmentedToggle } from "../../shared/ui/segmented-toggle";
import { channelLabel, stateLabel } from "../inbox/inbox-labels";
import {
  asCaseState,
  caseKindLabel,
  groupByState,
  missingLabel,
  ownCaseKindLabel,
  stateHint,
} from "./cases-labels";

export function CasesPage({ initialTenantId }: { readonly initialTenantId?: string | undefined }) {
  const sitio = useQuery(siteQueryOptions());

  if (sitio.isPending) {
    return <PageSkeleton kind="cases" />;
  }
  if (sitio.isError) {
    return (
      <div className={LONG_PAGE_CONTENT}>
        <CasesError
          error={sitio.error}
          onRetry={() => {
            void sitio.refetch();
          }}
        />
      </div>
    );
  }
  return <CasesContent tenants={sitio.data.tenants} initialTenantId={initialTenantId} />;
}

function CasesError({ error, onRetry }: { readonly error: unknown; readonly onRetry: () => void }) {
  const { t } = useLocale();
  return (
    <InlineAlert
      tone="danger"
      data-testid="cases-error"
      action={
        <Button variant="secondary" onClick={onRetry}>
          {t("action.retry")}
        </Button>
      }
    >
      <p>{toProblemView(error).message(t)}</p>
    </InlineAlert>
  );
}

function CasesContent({
  tenants,
  initialTenantId,
}: {
  readonly tenants: readonly TenantPresentation[];
  readonly initialTenantId?: string | undefined;
}) {
  const { t } = useLocale();
  return (
    <div className={LONG_PAGE_CONTENT} data-testid="cases">
      <header className="flex max-w-[46rem] flex-col gap-2">
        <h1 className={PAGE_TITLE}>{t("cases.title")}</h1>
        <p className="text-body text-fg-secondary">{t("cases.intro")}</p>
      </header>
      <OwnCases tenants={tenants} />
      <ExampleCases tenants={tenants} initialTenantId={initialTenantId} />
    </div>
  );
}

// --- Tus casos -------------------------------------------------------------------

function OwnCases({ tenants }: { readonly tenants: readonly TenantPresentation[] }) {
  const { t } = useLocale();
  // Una consulta por aseguradora: el chat guarda una conversacion por aseguradora, y
  // preguntar por una sin conversacion responde "nada" sin dar de alta ninguna.
  const consultas = useQueries({
    queries: tenants.map((tenant) => ownCaseQueryOptions(tenant.tenant_id)),
  });
  const propios = tenants.flatMap((tenant, indice) => {
    const caso = consultas.at(indice)?.data;
    return caso === undefined || caso === null ? [] : [{ tenant, caso }];
  });
  const cargando = consultas.some((consulta) => consulta.isPending);

  return (
    <section
      aria-labelledby="cases-mine-title"
      className="flex flex-col gap-4"
      data-testid="cases-mine"
    >
      <header className="flex flex-col gap-1">
        <h2 id="cases-mine-title" className={SECTION_TITLE}>
          {t("cases.mine.title")}
        </h2>
        <p className="text-small text-fg-secondary">{t("cases.mine.hint")}</p>
      </header>
      {propios.length > 0 ? (
        <ul className="flex flex-col border-b border-hairline" data-testid="cases-mine-list">
          {propios.map(({ tenant, caso }) => (
            <OwnCaseRow key={tenant.tenant_id} tenant={tenant} caso={caso} />
          ))}
        </ul>
      ) : cargando ? (
        <RowsSkeleton rows={1} />
      ) : (
        <InlineAlert
          tone="info"
          data-testid="cases-mine-empty"
          action={
            <Button asChild variant="primary">
              <a href={INSURERS_LINK.href}>{t("cases.start")}</a>
            </Button>
          }
        >
          {t("cases.mine.empty")}
        </InlineAlert>
      )}
    </section>
  );
}

function OwnCaseRow({
  tenant,
  caso,
}: {
  readonly tenant: TenantPresentation;
  readonly caso: ChatCaseStatus;
}) {
  const { t } = useLocale();
  const estado = asCaseState(caso.state);
  // En una consulta de cobertura nadie esta dando datos: no se cuenta cuanto falta.
  const conAvance = caso.record_type !== "coverage_inquiry" && caso.total > 0;
  const nombre = tenant.display_name;

  return (
    <li
      data-tenant-scope=""
      data-testid="own-case"
      style={tenantAccentStyle(tenant.brand)}
      className="flex flex-col gap-4 border-t border-hairline py-5 tablet:flex-row tablet:items-center tablet:justify-between"
    >
      <div className="flex min-w-0 items-start gap-4">
        {tenant.brand ? <Monogram shape={tenant.brand.monogram} /> : null}
        <div className="flex min-w-0 flex-col gap-1">
          <h3 className="text-lead font-medium text-tenant">{nombre}</h3>
          <p className="text-body text-fg">{ownCaseKindLabel(caso.record_type)(t)}</p>
          {/* El codigo no es el nombre del caso: es un renglon pequeno que dice para que
              sirve (C10, 2026-10-12). */}
          <p className="text-caption text-fg-secondary" data-testid="own-case-number">
            {t("cases.mine.number", { case_number: caso.case_number })}
          </p>
          <p className="text-small text-fg-secondary" data-testid="own-case-progress">
            {[
              estado === undefined ? null : stateLabel(estado)(t),
              conAvance ? missingLabel(caso.total - caso.complete)(t) : null,
            ]
              .filter((parte) => parte !== null)
              .join(" · ")}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 tablet:justify-end">
        <Button asChild variant="tenant">
          <a
            href={tenantSurfaceHref("chat", tenant.tenant_id)}
            aria-label={t("cases.mine.chat_with", { insurer: nombre })}
          >
            {t("cases.mine.chat")}
          </a>
        </Button>
        {/* El enlace firmado que ya entrega el estado del caso del chat; sin clave de
            enlaces en el despliegue no hay enlace y la accion no se ofrece. */}
        {caso.case_link === null ? null : (
          <Button asChild variant="tenant-outline">
            <a
              href={caso.case_link}
              aria-label={t("cases.mine.view_of", {
                case_number: caso.case_number,
                insurer: nombre,
              })}
            >
              {t("cases.mine.view")}
            </a>
          </Button>
        )}
      </div>
    </li>
  );
}

// --- Casos de ejemplo --------------------------------------------------------------

function ExampleCases({
  tenants,
  initialTenantId,
}: {
  readonly tenants: readonly TenantPresentation[];
  readonly initialTenantId?: string | undefined;
}) {
  const { t } = useLocale();
  const [elegida, setElegida] = useState(
    tenants.find((tenant) => tenant.tenant_id === initialTenantId)?.tenant_id ??
      tenants[0]?.tenant_id ??
      "",
  );
  const aseguradora = tenants.find((tenant) => tenant.tenant_id === elegida);

  return (
    <section
      aria-labelledby="cases-examples-title"
      className="flex flex-col gap-4"
      data-testid="cases-examples"
    >
      <header className="flex max-w-[46rem] flex-col gap-1">
        <h2 id="cases-examples-title" className={SECTION_TITLE}>
          {t("cases.examples.title")}
        </h2>
        <p className="text-small text-fg-secondary">{t("cases.examples.hint")}</p>
      </header>
      {/* La aseguradora elegida, con una linea en su propio acento bajo el nombre. */}
      <SegmentedToggle
        label={t("cases.examples.insurer_label")}
        value={elegida}
        options={tenants.map((tenant) => ({
          value: tenant.tenant_id,
          label: tenant.display_name,
          style: tenantAccentStyle(tenant.brand),
          tenantScope: true,
        }))}
        onChange={setElegida}
        testId="cases-insurers"
        look="underline-tenant"
        className="tablet:self-start"
      />
      {aseguradora === undefined ? null : (
        <TenantExamples key={aseguradora.tenant_id} tenant={aseguradora} />
      )}
    </section>
  );
}

function TenantExamples({ tenant }: { readonly tenant: TenantPresentation }) {
  const { t } = useLocale();
  const consulta = useQuery(exampleCasesQueryOptions(tenant.tenant_id));

  if (consulta.isPending) {
    return <RowsSkeleton rows={5} />;
  }
  if (consulta.isError) {
    return (
      <CasesError
        error={consulta.error}
        onRetry={() => {
          void consulta.refetch();
        }}
      />
    );
  }
  const grupos = groupByState(consulta.data.items);

  return (
    <div
      className="flex flex-col gap-8"
      style={tenantAccentStyle(tenant.brand)}
      data-tenant-scope=""
      data-testid="example-cases"
    >
      {grupos.length === 0 ? (
        <InlineAlert tone="info" data-testid="example-cases-empty">
          {t("cases.examples.empty")}
        </InlineAlert>
      ) : (
        grupos.map((grupo) => (
          <StateGroup
            key={grupo.state}
            tenantId={tenant.tenant_id}
            state={grupo.state}
            items={grupo.items}
          />
        ))
      )}
    </div>
  );
}

function StateGroup({
  tenantId,
  state,
  items,
}: {
  readonly tenantId: string;
  readonly state: CaseState;
  readonly items: readonly ExampleCaseItem[];
}) {
  const { t } = useLocale();
  const titulo = `cases-group-${state}`;
  const nota = stateHint(state);

  return (
    <section aria-labelledby={titulo} className="flex flex-col gap-3" data-testid="example-group">
      <header className="flex flex-col gap-0.5">
        <h3
          id={titulo}
          className="flex flex-wrap items-baseline gap-x-3 text-title font-medium text-fg"
        >
          {stateLabel(state)(t)}
          <span className="text-caption font-normal text-fg-secondary">
            {t("inbox.queue.results", { count: items.length })}
          </span>
        </h3>
        {nota === undefined ? null : <p className="text-small text-fg-secondary">{nota(t)}</p>}
      </header>
      <ul className="flex flex-col divide-y divide-hairline overflow-hidden rounded-surface border border-hairline bg-surface">
        {items.map((fila) => (
          <li key={fila.case_id}>
            <ExampleRow tenantId={tenantId} fila={fila} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function ExampleRow({
  tenantId,
  fila,
}: {
  readonly tenantId: string;
  readonly fila: ExampleCaseItem;
}) {
  const { t } = useLocale();
  // En telefono, el numero y los datos arriba y lo que es debajo; desde tableta, en una
  // sola linea con el numero en una columna fija.
  return (
    <a
      href={exampleCaseHref(tenantId, fila.case_id)}
      data-testid="example-case"
      className="group grid min-h-11 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-0.5 px-4 py-3 text-fg no-underline transition-colors duration-[160ms] ease-out hover:bg-surface-alt tablet:grid-cols-[7.5rem_minmax(0,1fr)_auto]"
    >
      <span className="font-mono text-body tabular-nums">{fila.case_number}</span>
      <span className="col-span-2 row-start-2 flex flex-wrap items-baseline gap-x-3 tablet:col-span-1 tablet:col-start-2 tablet:row-start-1">
        <span className="text-body">{caseKindLabel(fila.record_type)(t)}</span>
        <span className="text-small text-fg-secondary">
          {channelLabel(fila.channel)(t)}
          {" · "}
          {fila.language === "es" ? t("shell.language.es") : t("shell.language.en")}
        </span>
      </span>
      <span className="col-start-2 row-start-1 flex items-center gap-2 text-small text-fg-secondary tabular-nums tablet:col-start-3">
        {fila.record_type === "coverage_inquiry"
          ? null
          : t("inbox.completeness", {
              complete: fila.completeness_complete,
              total: fila.completeness_total,
            })}
        <CaretRightIcon
          aria-hidden="true"
          focusable="false"
          size={16}
          className="shrink-0 transition-colors group-hover:text-tenant"
        />
      </span>
    </a>
  );
}
