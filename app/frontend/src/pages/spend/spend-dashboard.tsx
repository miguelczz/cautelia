// El tablero de gasto: la pestana "Cuanto cuesta" de la telemetria (2026-10-09).
//
// Publico. Responde, de arriba abajo, las preguntas que se hace quien llega: cuanto
// se ha gastado, cuanto cuesta una llamada y un chat, en que dias, en que se va,
// quien cobra, cuanto queda del presupuesto y cuanto costo un caso concreto.
//
// Tres reglas que no se rompen. **Lo que no tiene precio publicado nunca se escribe
// como cero**: sale en tokens, que es lo que el proveedor si cuenta, y solo si ni eso
// hay, como "Sin precio" (BR3.5, 2026-10-11). **La pantalla no decide nada**: el
// estado del techo y cuanto queda son lo que manda el servidor (BR3.3). Y **ningun
// caso se identifica**: se describe por lo que fue, y el del propio navegador sale
// como "Tuyo". Las consultas de un mismo clic en "Comparar" son una sola entrada.
//
// Arriba va el acceso a Langfuse (2026-10-14), y es solo de **este navegador**: Langfuse
// pide iniciar sesion salvo para una traza que se abre por su direccion, y quien llega no
// tiene cuenta. La direccion la manda el servidor (`langfuse_url`, y `trace_url` en el caso
// propio) o no hay enlace: esta pantalla no la arma, y solo pinta una que empiece por https.

import { useQuery } from "@tanstack/react-query";
import { useId, useState, type ReactNode } from "react";

import { toProblemView } from "../../shared/api-client/problems";
import { siteQueryOptions } from "../../shared/api-client/site";
import {
  spendQueryOptions,
  type CaseSpendItem,
  type ComparisonSpendItem,
  type CountedSpend,
  type SpendPanel,
} from "../../shared/api-client/spend";
import { useLocale } from "../../shared/i18n/locale-provider";
import { Button } from "../../shared/ui/button";
import { cn } from "../../shared/ui/cn";
import { isSafeExternalLink } from "../../shared/ui/external-link";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { PanelBodySkeleton } from "../../shared/ui/page-skeletons";
import { SECTION_TITLE } from "../../shared/ui/page-layout";
import { Select } from "../../shared/ui/select";
import {
  ActivityDonut,
  Amount,
  BudgetMeter,
  DailyBars,
  InsurerBars,
  ProviderBars,
  Swatch,
} from "./spend-charts";
import { CONTENEDOR_DE_CIFRA, Figure } from "./spend-figure";
import { useAmount, useLongDay, useMoment, usePercent, useUsd } from "./spend-format";
import {
  ACTIVITIES,
  activityHelp,
  activityName,
  caseTypeName,
  channelName,
  statusText,
} from "./spend-labels";

// La tarjeta es un contenedor: su cifra se adapta a su ancho (`spend-figure.tsx`).
const TARJETA = `${CONTENEDOR_DE_CIFRA} flex flex-col gap-2 rounded-surface border border-hairline bg-surface p-5`;
const SECCION =
  "flex flex-col gap-5 rounded-surface border border-hairline bg-surface p-5 tablet:p-6";
const ETIQUETA = "text-small text-fg-secondary";
/** Cuando en el lugar de la cifra va una frase: "todavia sin datos", "sin precio". */
const CIFRA_EN_PALABRAS =
  "font-display text-title font-light text-fg-secondary [overflow-wrap:anywhere]";

function SectionHeader({ title, lead }: { readonly title: string; readonly lead: string }) {
  return (
    <header className="flex flex-col gap-1">
      <h2 className={SECTION_TITLE}>{title}</h2>
      <p className="text-body text-fg-secondary">{lead}</p>
    </header>
  );
}

function Kpi({
  label,
  value,
  hint,
  testId,
  children,
  wordy = false,
}: {
  readonly label: string;
  readonly value: string;
  readonly hint: string;
  readonly testId: string;
  readonly children?: ReactNode;
  /** El valor es una frase y no una cifra. */
  readonly wordy?: boolean;
}) {
  return (
    <div className={TARJETA} data-testid={testId}>
      <span className={ETIQUETA}>{label}</span>
      {wordy ? <span className={CIFRA_EN_PALABRAS}>{value}</span> : <Figure>{value}</Figure>}
      {children}
      <span className="text-small text-fg-secondary">{hint}</span>
    </div>
  );
}

function AverageKpi({
  label,
  hintKey,
  counted,
  testId,
}: {
  readonly label: string;
  readonly hintKey: "spend_panel.kpi.per_call_hint" | "spend_panel.kpi.per_chat_hint";
  readonly counted: CountedSpend;
  readonly testId: string;
}) {
  const { t } = useLocale();
  const usd = useUsd();
  if (counted.count === 0) {
    return (
      <Kpi
        label={label}
        value={t("spend_panel.kpi.none_yet")}
        hint={t("spend_panel.kpi.none_hint")}
        testId={testId}
        wordy
      />
    );
  }
  const hint =
    hintKey === "spend_panel.kpi.per_call_hint"
      ? t("spend_panel.kpi.per_call_hint", { count: String(counted.count) })
      : t("spend_panel.kpi.per_chat_hint", { count: String(counted.count) });
  return (
    <Kpi
      label={label}
      value={usd(Number(counted.total.measured_usd) / counted.count)}
      hint={hint}
      testId={testId}
    />
  );
}

/**
 * El acceso a Langfuse para ver, paso a paso, como trabajo la agente en la ultima
 * conversacion de este navegador. Sin conversacion (o sin Langfuse) no hay boton: una
 * linea discreta dice cuando lo habra.
 */
function LangfuseAccess({ url }: { readonly url: string | null | undefined }) {
  const { t } = useLocale();
  const notaId = useId();
  const enlace = isSafeExternalLink(url) ? url : null;
  if (enlace === null) {
    return (
      <p className="text-small text-fg-secondary" data-testid="spend-langfuse-empty">
        {t("spend_panel.langfuse.empty")}
      </p>
    );
  }
  return (
    <div className="flex flex-col items-start gap-2" data-testid="spend-langfuse">
      <Button asChild variant="secondary">
        <a
          href={enlace}
          target="_blank"
          rel="noopener noreferrer"
          aria-describedby={notaId}
          data-testid="spend-langfuse-link"
        >
          {t("spend_panel.langfuse.link")}
        </a>
      </Button>
      <p id={notaId} className="max-w-[46rem] text-small text-fg-secondary">
        {t("inbox.trace.langfuse_note")}
      </p>
    </div>
  );
}

function Headline({ panel }: { readonly panel: SpendPanel }) {
  const { t } = useLocale();
  const usd = useUsd();
  const pct = usePercent();
  const largo = useLongDay();
  const ventana = panel.window;
  return (
    <div className="grid gap-4 tablet:grid-cols-2 wide:grid-cols-4">
      <Kpi
        label={t("spend_panel.kpi.total")}
        value={usd(panel.total.measured_usd)}
        hint={t("spend_panel.kpi.total_hint", {
          date: largo(ventana?.window_start ?? "2026-09-16"),
        })}
        testId="spend-total"
      />
      {ventana === null ? (
        <Kpi
          label={t("spend_panel.kpi.budget")}
          value={t("spend_panel.not_measured")}
          hint={t("spend_panel.window.none")}
          testId="spend-budget"
          wordy
        />
      ) : (
        <Kpi
          label={t("spend_panel.kpi.budget")}
          value={pct(Number(ventana.spent.measured_usd) / Number(ventana.cap_usd))}
          hint={t("spend_panel.kpi.budget_hint", {
            spent: usd(ventana.spent.measured_usd),
            cap: usd(ventana.cap_usd),
            alert: usd(ventana.alert_usd),
          })}
          testId="spend-budget"
        >
          <BudgetMeter
            spent={Number(ventana.spent.measured_usd)}
            cap={Number(ventana.cap_usd)}
            alert={Number(ventana.alert_usd)}
          />
        </Kpi>
      )}
      <AverageKpi
        label={t("spend_panel.kpi.per_call")}
        hintKey="spend_panel.kpi.per_call_hint"
        counted={panel.calls}
        testId="spend-per-call"
      />
      <AverageKpi
        label={t("spend_panel.kpi.per_chat")}
        hintKey="spend_panel.kpi.per_chat_hint"
        counted={panel.chats}
        testId="spend-per-chat"
      />
    </div>
  );
}

function WhereItGoes({ panel }: { readonly panel: SpendPanel }) {
  const { t } = useLocale();
  const usd = useUsd();
  const pct = usePercent();
  const amountOf = useAmount();
  const partes = ACTIVITIES.flatMap((actividad) => {
    const fila = panel.by_activity.find((a) => a.activity === actividad);
    return fila === undefined
      ? []
      : [{ activity: actividad, total: fila.total, unpriced: fila.unpriced }];
  });
  const total = Number(panel.total.measured_usd);
  return (
    <section className={SECCION} data-testid="spend-activity">
      <SectionHeader
        title={t("spend_panel.activity.title")}
        lead={t("spend_panel.activity.lead")}
      />
      {/* La dona en el centro y, debajo, la leyenda a todo el ancho: sin hueco a un lado. */}
      <div className="flex flex-col items-center gap-6">
        <ActivityDonut
          parts={partes.map((p) => ({ activity: p.activity, value: Number(p.total.measured_usd) }))}
          center={usd(total)}
          centerLabel={t("spend_panel.kpi.total")}
        />
        <ul className="flex w-full flex-col gap-4">
          {partes.map((parte) => {
            const valor = Number(parte.total.measured_usd);
            return (
              <li key={parte.activity} className="flex gap-3">
                <span className="mt-1.5">
                  <Swatch activity={parte.activity} />
                </span>
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <div className="flex items-baseline justify-between gap-4">
                    <span className="font-medium text-fg">{activityName(parte.activity)(t)}</span>
                    {/* Solo la cifra: sin "plan gratuito" ni "+ N consultas" debajo (E4). */}
                    <Amount view={amountOf(parte.total, parte.unpriced)} withNote={false} />
                  </div>
                  <span className="text-small text-fg-secondary">
                    {activityHelp(parte.activity)(t)}
                    {total > 0 && valor > 0
                      ? ` ${t("spend_panel.activity.share", { percent: pct(valor / total) })}`
                      : null}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}

function Budget({ panel }: { readonly panel: SpendPanel }) {
  const { t } = useLocale();
  const usd = useUsd();
  const largo = useLongDay();
  const ventana = panel.window;
  return (
    <section className={SECCION} data-testid="spend-window">
      <SectionHeader title={t("spend_panel.window.title")} lead={t("spend_panel.window.lead")} />
      {ventana === null ? (
        <p className="text-body text-fg-secondary">{t("spend_panel.window.none")}</p>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="text-lead font-medium text-fg">{statusText(ventana.status)(t)}</span>
            <span className="text-small text-fg-secondary">
              {t("spend_panel.window.range", {
                start: largo(ventana.window_start),
                end: largo(ventana.window_end),
              })}
            </span>
          </div>
          <BudgetMeter
            spent={Number(ventana.spent.measured_usd)}
            cap={Number(ventana.cap_usd)}
            alert={Number(ventana.alert_usd)}
          />
          <div className="flex flex-wrap justify-between gap-2 text-small text-fg-secondary tabular-nums">
            <span>
              {ventana.public_remaining_usd.amount_usd == null
                ? t("spend_panel.status_value.unmeasured")
                : t("spend_panel.window.remaining", {
                    amount: usd(ventana.public_remaining_usd.amount_usd),
                  })}
            </span>
            <span className="flex gap-4">
              <span>{t("spend_panel.window.alert_label", { amount: usd(ventana.alert_usd) })}</span>
              <span>{t("spend_panel.window.cap_label", { amount: usd(ventana.cap_usd) })}</span>
            </span>
          </div>
        </div>
      )}
    </section>
  );
}

/** Una entrada del selector: un caso suelto, o las consultas de un mismo clic en "Comparar". */
type Entrada =
  | { readonly kind: "case"; readonly item: CaseSpendItem }
  | { readonly kind: "comparison"; readonly item: ComparisonSpendItem };

/** Todas las entradas, la mas reciente primero (el orden estable respeta el del servidor). */
function entradasDe(panel: SpendPanel): Entrada[] {
  const entradas: Entrada[] = [
    ...panel.cases.map((item): Entrada => ({ kind: "case", item })),
    ...(panel.comparisons ?? []).map((item): Entrada => ({ kind: "comparison", item })),
  ];
  return entradas.sort((a, b) => Date.parse(b.item.started_at) - Date.parse(a.item.started_at));
}

/** El nombre de una aseguradora como lo ve quien mira: el del directorio del sitio. */
function useInsurerName(): (tenantId: string) => string {
  const sitio = useQuery(siteQueryOptions());
  return (tenantId) =>
    sitio.data?.tenants.find((tenant) => tenant.tenant_id === tenantId)?.display_name ?? tenantId;
}

/** Como se nombra una entrada en la lista: por lo que fue, nunca por su numero. */
function useEntryLabel(): (entrada: Entrada) => string {
  const { t } = useLocale();
  const momento = useMoment();
  const nombre = useInsurerName();
  return (entrada) => {
    const cuando = momento(entrada.item.started_at);
    let descripcion: string;
    if (entrada.kind === "case") {
      descripcion = t("spend_panel.cases.describe", {
        type: caseTypeName(entrada.item.record_type)(t),
        channel: channelName(entrada.item.channel)(t),
        insurer: nombre(entrada.item.tenant_id),
        when: cuando,
      });
    } else {
      const partes = entrada.item.parts;
      descripcion =
        partes.length === 1 && partes[0] !== undefined
          ? t("spend_panel.cases.describe_comparison_one", {
              insurer: nombre(partes[0].tenant_id),
              when: cuando,
            })
          : t("spend_panel.cases.describe_comparison", {
              count: String(partes.length),
              when: cuando,
            });
    }
    return entrada.item.yours ? `${t("spend_panel.cases.mine")} · ${descripcion}` : descripcion;
  };
}

function CaseDetail({ entrada }: { readonly entrada: Entrada }) {
  const { t } = useLocale();
  const amountOf = useAmount();
  const nombre = useInsurerName();
  const importe = amountOf(entrada.item.total, entrada.item.unpriced);
  const partes = entrada.kind === "comparison" ? entrada.item.parts : [];
  // Solo el caso propio, y solo con la direccion que manda el servidor.
  const enlaceDelCaso =
    entrada.kind === "case" && entrada.item.yours && isSafeExternalLink(entrada.item.trace_url)
      ? entrada.item.trace_url
      : null;
  return (
    <div
      className={cn(
        // Dos columnas con reparto fijo y no "la que mida el contenido": la cifra se
        // adapta al ancho de la suya, y una columna que creciera con ella lo anularia.
        "grid items-center gap-6 rounded-surface p-5 tablet:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]",
        entrada.item.yours ? "bg-selected" : "bg-surface-alt",
      )}
      data-testid="spend-case-detail"
    >
      <div className={cn(CONTENEDOR_DE_CIFRA, "flex min-w-0 flex-col gap-2")}>
        {entrada.item.yours ? (
          <span className="w-fit rounded-pill bg-brand px-2.5 py-0.5 text-caption font-medium text-on-brand">
            {t("spend_panel.cases.yours")}
          </span>
        ) : null}
        <Figure>{importe.main}</Figure>
        {importe.note === null ? null : (
          <span className="text-small text-fg-secondary" data-testid="spend-case-note">
            {importe.note}
          </span>
        )}
        {partes.length > 1 ? (
          <span className="text-small text-fg-secondary" data-testid="spend-comparison-hint">
            {t("spend_panel.cases.comparison_hint", { count: String(partes.length) })}
          </span>
        ) : null}
        {enlaceDelCaso === null ? null : (
          <a
            href={enlaceDelCaso}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-11 items-center self-start text-small text-link underline underline-offset-4"
            data-testid="spend-case-langfuse-link"
          >
            {t("spend_panel.langfuse.case_link")}
          </a>
        )}
      </div>
      {entrada.kind === "comparison" ? (
        <InsurerBars parts={entrada.item.parts} nameOf={nombre} />
      ) : (
        <ProviderBars providers={entrada.item.by_provider} compact />
      )}
    </div>
  );
}

function Cases({ panel }: { readonly panel: SpendPanel }) {
  const { t } = useLocale();
  const entradas = entradasDe(panel);
  const primera = entradas.find((e) => e.item.yours) ?? entradas[0];
  const [elegida, setElegida] = useState<string | undefined>(primera?.item.key);
  const entrada = entradas.find((e) => e.item.key === elegida) ?? primera;
  const etiqueta = useEntryLabel();

  return (
    <section className={SECCION} data-testid="spend-cases">
      <SectionHeader title={t("spend_panel.cases.title")} lead={t("spend_panel.cases.lead")} />
      {entrada === undefined ? (
        <p className="text-body text-fg-secondary">{t("spend_panel.cases.empty")}</p>
      ) : (
        <div className="flex flex-col gap-5">
          <label className="flex max-w-[40rem] flex-col gap-1.5">
            <span className={ETIQUETA}>{t("spend_panel.cases.label")}</span>
            <Select
              value={entrada.item.key}
              onChange={(evento) => {
                setElegida(evento.target.value);
              }}
              data-testid="spend-case-select"
            >
              {entradas.map((e) => (
                <option key={e.item.key} value={e.item.key}>
                  {etiqueta(e)}
                </option>
              ))}
            </Select>
          </label>
          <CaseDetail entrada={entrada} />
        </div>
      )}
    </section>
  );
}

function Dashboard({ panel }: { readonly panel: SpendPanel }) {
  const { t } = useLocale();
  return (
    <div className="flex flex-col gap-6" data-testid="spend-dashboard">
      <LangfuseAccess url={panel.langfuse_url} />
      <Headline panel={panel} />
      <section className={SECCION} data-testid="spend-days">
        <SectionHeader title={t("spend_panel.daily.title")} lead={t("spend_panel.daily.lead")} />
        <DailyBars days={panel.by_day} />
      </section>
      <div className="grid gap-6 desktop:grid-cols-2">
        <WhereItGoes panel={panel} />
        <section className={SECCION} data-testid="spend-providers">
          <SectionHeader
            title={t("spend_panel.provider.title")}
            lead={t("spend_panel.provider.lead")}
          />
          {/* Junto a la dona, que es mas alta: los proveedores se reparten el alto del panel. */}
          <ProviderBars providers={panel.by_provider} fill />
        </section>
      </div>
      <Cases panel={panel} />
      <Budget panel={panel} />
    </div>
  );
}

export function SpendDashboard() {
  const { t } = useLocale();
  const consulta = useQuery(spendQueryOptions());

  if (consulta.isPending) {
    return <PanelBodySkeleton label={t("spend_panel.loading")} />;
  }
  if (consulta.isError) {
    return (
      <InlineAlert
        tone="danger"
        data-testid="spend-error"
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
        <p>{toProblemView(consulta.error).message(t)}</p>
      </InlineAlert>
    );
  }
  return <Dashboard panel={consulta.data} />;
}
