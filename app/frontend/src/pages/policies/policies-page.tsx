// La pestana de polizas (fase 2, 2026-10-08): las polizas de ejemplo de cada
// aseguradora, para que quien visita sepa con que poliza probar y que preguntar.
//
// Se elige la aseguradora con pestanas y la poliza en una lista; el detalle muestra
// lo que la poliza trae --titular, vehiculos, vigencia, limites y endosos-- y las
// preguntas para probar, que abren el chat con la poliza y la pregunta ya enviadas.
// Los montos llegan en las unidades del corpus y se muestran en pesos colombianos
// multiplicando por mil (decision de Miguel del 2026-10-07).

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { toProblemView } from "../../shared/api-client/problems";
import { policiesQueryOptions, type PolicyView } from "../../shared/api-client/policies";
import { siteQueryOptions, type TenantPresentation } from "../../shared/api-client/site";
import { useLocale } from "../../shared/i18n/locale-provider";
import { tenantAccentStyle } from "../../shared/theme/tenant-accent";
import { Button } from "../../shared/ui/button";
import { cn } from "../../shared/ui/cn";
import { InlineAlert } from "../../shared/ui/inline-alert";
import {
  PAGE_TITLE,
  POLICIES_CARD_SPACE,
  POLICIES_CONTENT,
  POLICIES_LIST,
  POLICIES_PANES,
  SECTION_TITLE,
} from "../../shared/ui/page-layout";
import { PageSkeleton, PoliciesBodySkeleton } from "../../shared/ui/page-skeletons";
import { SegmentedToggle } from "../../shared/ui/segmented-toggle";
import { tenantSurfaceHref } from "../../app/surfaces";
import { DocumentsButton } from "./documents-dialog";
import { endorsementLabel, LIMIT_ORDER, limitLabel, questionLabel } from "./policies-labels";

/** Los montos del corpus son miles de pesos (decision de Miguel del 2026-10-07). */
export const PESOS_POR_UNIDAD = 1000;

export function formatPesos(valor: number, locale: string): string {
  return new Intl.NumberFormat(locale === "es" ? "es-CO" : "en-US", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(valor * PESOS_POR_UNIDAD);
}

function formatDate(iso: string, locale: string): string {
  const [anio, mes, dia] = iso.split("-").map(Number);
  if (anio === undefined || mes === undefined || dia === undefined) {
    return iso;
  }
  return new Intl.DateTimeFormat(locale === "es" ? "es-CO" : "en-US", {
    dateStyle: "long",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(anio, mes - 1, dia)));
}

/** El chat de la aseguradora con un mensaje que se envia solo al abrir. */
export function chatWithMessage(tenantId: string, message: string): string {
  return `${tenantSurfaceHref("chat", tenantId)}?ask=${encodeURIComponent(message)}`;
}

export function PoliciesPage({
  initialTenantId,
}: {
  readonly initialTenantId?: string | undefined;
}) {
  const { t } = useLocale();
  const sitio = useQuery(siteQueryOptions());

  if (sitio.isPending) {
    return <PageSkeleton kind="policies" label={t("policies.loading")} />;
  }
  if (sitio.isError) {
    return (
      <PoliciesError
        error={sitio.error}
        onRetry={() => {
          void sitio.refetch();
        }}
      />
    );
  }
  return <PoliciesContent tenants={sitio.data.tenants} initialTenantId={initialTenantId} />;
}

function PoliciesError({
  error,
  onRetry,
}: {
  readonly error: unknown;
  readonly onRetry: () => void;
}) {
  const { t } = useLocale();
  return (
    <InlineAlert
      tone="danger"
      data-testid="policies-error"
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

function PoliciesContent({
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
    <div className={POLICIES_CONTENT} data-testid="policies">
      {/* En un computador el titulo y el selector comparten renglon: el alto que se
          ahorra es el que deja ver las seis polizas sin desplazar nada. */}
      <div className="flex flex-col gap-6 roomy:flex-row roomy:items-end roomy:justify-between roomy:gap-8">
        <header className="flex max-w-[46rem] flex-col gap-2">
          <h1 className={PAGE_TITLE}>{t("policies.title")}</h1>
          <p className="text-body text-fg-secondary">{t("policies.intro")}</p>
        </header>
        {/* La aseguradora elegida, con una linea en su propio acento bajo el nombre. */}
        <SegmentedToggle
          label={t("policies.title")}
          value={elegida}
          options={tenants.map((tenant) => ({
            value: tenant.tenant_id,
            label: tenant.display_name,
            style: tenantAccentStyle(tenant.brand),
            tenantScope: true,
          }))}
          onChange={setElegida}
          testId="policies-insurers"
          look="underline-tenant"
          className="tablet:self-start"
        />
      </div>
      {aseguradora === undefined ? null : (
        <TenantPolicies key={aseguradora.tenant_id} tenant={aseguradora} />
      )}
    </div>
  );
}

function TenantPolicies({ tenant }: { readonly tenant: TenantPresentation }) {
  const { t } = useLocale();
  const consulta = useQuery(policiesQueryOptions(tenant.tenant_id));
  const [numero, setNumero] = useState<string | null>(null);

  if (consulta.isPending) {
    return <PoliciesBodySkeleton label={t("policies.loading")} />;
  }
  if (consulta.isError) {
    return (
      <PoliciesError
        error={consulta.error}
        onRetry={() => {
          void consulta.refetch();
        }}
      />
    );
  }
  const { policies, example_policy: ejemplo } = consulta.data;
  const actual =
    policies.find((poliza) => poliza.policy_number === (numero ?? ejemplo)) ?? policies[0];

  return (
    <div className={POLICIES_PANES} style={tenantAccentStyle(tenant.brand)} data-tenant-scope="">
      <ul className={POLICIES_LIST} data-testid="policy-list">
        {policies.map((poliza) => {
          const elegida = poliza.policy_number === actual?.policy_number;
          return (
            <li key={poliza.policy_number} className="roomy:flex">
              <button
                type="button"
                aria-pressed={elegida}
                onClick={() => {
                  setNumero(poliza.policy_number);
                }}
                className={cn(
                  "flex min-h-11 w-full flex-col gap-1 rounded-surface border text-left roomy:justify-center roomy:gap-0",
                  POLICIES_CARD_SPACE,
                  "transition-colors duration-[160ms] ease-out",
                  elegida
                    ? "border-tenant bg-selected"
                    : "border-hairline bg-surface hover:border-tenant",
                )}
              >
                <span className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-mono text-body text-fg tabular-nums roomy:leading-5">
                    {poliza.policy_number}
                  </span>
                  {poliza.policy_number === ejemplo ? (
                    <span className="text-caption text-fg-secondary roomy:leading-5">
                      {t("policies.example")}
                    </span>
                  ) : null}
                </span>
                <span className="text-small text-fg">{poliza.holder_name}</span>
                <span className="text-small text-fg-secondary">{poliza.vehicles.join(" · ")}</span>
              </button>
            </li>
          );
        })}
      </ul>
      {/* En escritorio la celda mide el alto que queda de la ventana y no aporta altura
          propia: el detalle se despliega sobre ella y se desplaza por dentro. */}
      <div className="min-w-0 roomy:relative" data-testid="policy-detail-cell">
        {actual === undefined ? null : (
          <PolicyDetail
            tenantId={tenant.tenant_id}
            insurerName={tenant.display_name}
            policy={actual}
          />
        )}
      </div>
    </div>
  );
}

function PolicyDetail({
  tenantId,
  insurerName,
  policy,
}: {
  readonly tenantId: string;
  readonly insurerName: string;
  readonly policy: PolicyView;
}) {
  const { t, locale } = useLocale();
  const identidad = { name: policy.holder_name, policy: policy.policy_number };
  const montos = new Map(Object.entries(policy.limits));
  const limites = [
    ...LIMIT_ORDER.filter((clave) => montos.has(clave)),
    ...[...montos.keys()].filter((clave) => !LIMIT_ORDER.includes(clave)),
  ];
  const preguntas = policy.questions.flatMap((id) => {
    const etiqueta = questionLabel(id);
    return etiqueta === undefined ? [] : [{ id, text: etiqueta(t) }];
  });

  return (
    <section
      aria-labelledby="policy-detail-title"
      className="min-w-0 rounded-surface border border-hairline bg-surface roomy:absolute roomy:inset-0 roomy:overflow-hidden"
      data-testid="policy-detail"
    >
      {/* El marco queda quieto y lo que se desplaza es lo de dentro, con el desvanecido del
          borde que sigue: el titulo de abajo no queda cortado a ras. */}
      <div className="flex min-w-0 flex-col gap-5 p-4 tablet:p-6 roomy:h-full roomy:overflow-y-auto ut-scroll-fade-y">
        <header className="flex flex-col gap-1">
          <h2 id="policy-detail-title" className="font-mono text-title text-fg tabular-nums">
            {policy.policy_number}
          </h2>
          <p className="text-body text-fg">{t("policies.holder", { name: policy.holder_name })}</p>
          <p className="text-small text-fg-secondary">
            {t("policies.issued_by", { issuer: policy.issuer_name })}
            {" · "}
            {t("policies.period", {
              start: formatDate(policy.period_start, locale),
              end: formatDate(policy.period_end, locale),
            })}
          </p>
        </header>

        <div className="flex flex-col gap-1">
          <h3 className="text-small font-medium text-fg-secondary">{t("policies.vehicles")}</h3>
          <p className="text-body text-fg">{policy.vehicles.join(" · ")}</p>
        </div>

        <div className="flex flex-col gap-2">
          <h3 className={SECTION_TITLE}>{t("policies.coverage_title")}</h3>
          <dl className="flex flex-col divide-y divide-hairline" data-testid="policy-limits">
            {limites.map((clave) => {
              const etiqueta = limitLabel(clave);
              const valor = montos.get(clave);
              return valor === undefined ? null : (
                <div
                  key={clave}
                  className="flex flex-col gap-0.5 py-2 tablet:flex-row tablet:justify-between tablet:gap-4"
                >
                  <dt className="text-small text-fg-secondary">
                    {etiqueta === undefined ? clave : etiqueta(t)}
                  </dt>
                  <dd className="font-mono text-body text-fg tabular-nums">
                    {formatPesos(valor, locale)}
                  </dd>
                </div>
              );
            })}
          </dl>
          <p className="text-caption text-fg-secondary">{t("policies.money_note")}</p>
        </div>

        <div className="flex flex-col gap-2">
          <h3 className={SECTION_TITLE}>{t("policies.endorsements_title")}</h3>
          {policy.endorsements.length === 0 ? (
            <p className="text-body text-fg-secondary">{t("policies.no_endorsements")}</p>
          ) : (
            <ul className="flex list-disc flex-col gap-1 pl-5" data-testid="policy-endorsements">
              {policy.endorsements.flatMap((endoso) =>
                endoso.clause_keys.map((clave) => {
                  const etiqueta = endorsementLabel(clave);
                  return (
                    <li key={`${endoso.form_id}-${clave}`} className="text-body text-fg">
                      {etiqueta === undefined ? endoso.form_id : etiqueta(t)}
                    </li>
                  );
                }),
              )}
            </ul>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <h3 className={SECTION_TITLE}>{t("policies.questions_title")}</h3>
          <p className="text-small text-fg-secondary">{t("policies.questions_hint")}</p>
          <ul className="flex flex-wrap gap-2" data-testid="policy-questions">
            {preguntas.map((pregunta) => (
              <li key={pregunta.id}>
                <Button
                  asChild
                  variant="secondary"
                  className="h-auto py-2 whitespace-normal text-left"
                >
                  <a
                    href={chatWithMessage(
                      tenantId,
                      t("policies.ask_question", { ...identidad, question: pregunta.text }),
                    )}
                  >
                    {pregunta.text}
                  </a>
                </Button>
              </li>
            ))}
          </ul>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button asChild variant="tenant" className="h-auto py-2 whitespace-normal">
            <a href={chatWithMessage(tenantId, t("policies.ask_identity", identidad))}>
              {t("policies.ask_chat")}
            </a>
          </Button>
          <DocumentsButton tenantId={tenantId} insurerName={insurerName} />
        </div>
      </div>
    </section>
  );
}
