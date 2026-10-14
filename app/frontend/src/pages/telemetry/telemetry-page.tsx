// La telemetria: un solo lugar con dos vistas, lo que cuesta y que tan bien
// funciona (decision de Miguel del 2026-10-09). Es uno de los tres atractivos del
// proyecto, con el chat y las llamadas, y antes eran dos enlaces cuya diferencia
// habia que adivinar.
//
// Las dos vistas son **direcciones** (`?view=quality`) y por eso se eligen con
// enlaces con forma de pestana, no con pestanas de Radix: un enlace se comparte, se
// abre en otra pestana del navegador y "atras" vuelve a la vista anterior.

import { Link } from "@tanstack/react-router";

import { useLocale } from "../../shared/i18n/locale-provider";
import { cn } from "../../shared/ui/cn";
import { LONG_PAGE_CONTENT, PAGE_TITLE } from "../../shared/ui/page-layout";
import { QualityDashboard } from "../quality/quality-dashboard";
import { SpendDashboard } from "../spend/spend-dashboard";

export type TelemetryView = "cost" | "quality";

/** El aspecto de las pestanas de `shared/ui/tabs`, para un enlace. */
const PESTANA =
  "-mb-px inline-flex min-h-11 min-w-11 items-center justify-center rounded-t-button border-b-2 px-4 text-center font-body text-body max-tablet:flex-1 max-tablet:px-2 transition-colors duration-[160ms] ease-out hover:bg-surface-alt hover:text-fg";

function ViewLink({
  view,
  current,
  label,
}: {
  readonly view: TelemetryView;
  readonly current: TelemetryView;
  readonly label: string;
}) {
  const actual = view === current;
  return (
    <Link
      to="/telemetry"
      search={view === "quality" ? { view: "quality" } : {}}
      aria-current={actual ? "page" : undefined}
      data-testid={`telemetry-tab-${view}`}
      className={cn(
        PESTANA,
        actual
          ? "border-brand bg-selected font-medium text-fg"
          : "border-transparent text-fg-secondary",
      )}
    >
      {label}
    </Link>
  );
}

export function TelemetryPage({ view }: { readonly view: TelemetryView }) {
  const { t } = useLocale();

  return (
    <div className={LONG_PAGE_CONTENT} data-testid="telemetry-page">
      <header className="flex max-w-[46rem] flex-col gap-4">
        <h1 className={PAGE_TITLE}>{t("telemetry.title")}</h1>
        <p className="text-lead text-fg-secondary">{t("telemetry.lead")}</p>
      </header>
      <div className="flex flex-col gap-6">
        <nav aria-label={t("telemetry.title")} className="flex gap-1 border-b border-hairline">
          <ViewLink view="cost" current={view} label={t("telemetry.tab_cost")} />
          <ViewLink view="quality" current={view} label={t("telemetry.tab_quality")} />
        </nav>
        {view === "cost" ? (
          <SpendDashboard />
        ) : (
          // La ultima corrida completa de evaluacion, como salio (2026-10-11). Antes
          // iban aqui cinco cifras leidas de la linea base, que nunca se publico:
          // todo decia "No medida".
          <div className="flex flex-col gap-6" data-testid="metrics-page">
            <QualityDashboard />
          </div>
        )}
      </div>
    </div>
  );
}
