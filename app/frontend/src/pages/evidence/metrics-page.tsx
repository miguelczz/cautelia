// El panel de cifras (U22, US4.16): las cinco cifras del sistema, cada una con su
// fecha, su commit y su corrida, o con la causa de que no se haya medido.
//
// Tres reglas que la pantalla no puede romper y por eso las dibuja de una sola
// forma: una celda sin medir dice "No medida" y su causa, nunca un cero ni un
// hueco (BR1.2); los dos idiomas van lado a lado y no hay celda combinada
// (BR1.4); y lo unico que llega aqui es lo que el servidor manda, que no trae
// ningun identificador de caso (BR2.1).

import { useQuery } from "@tanstack/react-query";

import { toProblemView } from "../../shared/api-client/problems";
import {
  metricsQueryOptions,
  type Figure,
  type FigureSource,
  type LatencyMeasure,
  type LatencyReading,
  type Measurement,
} from "../../shared/api-client/metrics";
import { useLocale } from "../../shared/i18n/locale-provider";
import { Button } from "../../shared/ui/button";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { PanelBodySkeleton } from "../../shared/ui/page-skeletons";
import {
  causeText,
  channelName,
  eventName,
  figureHelp,
  figureName,
  formatDuration,
  languageName,
} from "./metrics-labels";

const CONTENIDO = "mx-auto flex max-w-content flex-col gap-10 px-4 py-12 tablet:px-8 tablet:py-16";
const TITULO = "font-display text-title font-light text-fg tablet:text-figure";
const IDIOMAS = ["es", "en"] as const;

export function MetricsPage() {
  const { t } = useLocale();
  return (
    <div className={CONTENIDO} data-testid="metrics-page">
      <header className="flex max-w-[46rem] flex-col gap-4">
        <h1 className={TITULO}>{t("metrics.title")}</h1>
        <p className="text-lead text-fg-secondary">{t("metrics.lead")}</p>
      </header>
      <MetricsBody />
    </div>
  );
}

/** Las cifras sin el encabezado: la pestana "Que tan bien funciona" de la telemetria. */
export function MetricsBody() {
  const { t } = useLocale();
  const consulta = useQuery(metricsQueryOptions());

  if (consulta.isPending) {
    return <PanelBodySkeleton label={t("metrics.loading")} />;
  }
  if (consulta.isError) {
    return (
      <InlineAlert
        tone="danger"
        data-testid="metrics-error"
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
  return (
    <>
      {consulta.data.baseline_id == null ? (
        <InlineAlert tone="info" data-testid="metrics-no-baseline">
          <p>{t("metrics.no_baseline")}</p>
        </InlineAlert>
      ) : null}
      <div className="flex flex-col">
        {consulta.data.figures.map((figura) => (
          <FigureSection key={figura.key} figure={figura} />
        ))}
      </div>
    </>
  );
}

function FigureSection({ figure }: { readonly figure: Figure }) {
  const { t } = useLocale();
  const titulo = `metrics-${figure.key}`;
  const porIdioma = figure.by_language ?? {};
  const conIdiomas = Object.keys(porIdioma).length > 0;

  return (
    <section
      aria-labelledby={titulo}
      data-testid="metrics-figure"
      data-figure={figure.key}
      data-state={figure.state}
      className="flex flex-col gap-4 border-t border-hairline py-6"
    >
      <h2 id={titulo} className="text-title font-medium text-fg">
        {figureName(figure.key)(t)}
      </h2>
      <p className="text-small text-fg-secondary">{figureHelp(figure.key)(t)}</p>

      {figure.key === "latency" ? (
        // Cada canal dice lo suyo: la causa de la cifra entera es la de la voz (por hito) y
        // pintarla arriba mandaria a esperar un hito por algo que el chat ya midio.
        <LatencyDetail measures={figure.latency ?? []} />
      ) : conIdiomas ? (
        <LanguageTable figure={figure} />
      ) : (
        <NotMeasuredNote cause={figure.not_measured_cause} />
      )}

      {figure.source != null ? <SourceLine source={figure.source} /> : null}
    </section>
  );
}

function LanguageTable({ figure }: { readonly figure: Figure }) {
  const { t } = useLocale();
  const celdas = Object.entries(figure.by_language ?? {});
  return (
    <table className="w-full max-w-[36rem] text-left text-body">
      <thead>
        <tr className="text-small text-fg-secondary">
          {IDIOMAS.map((idioma) => (
            <th key={idioma} scope="col" className="pb-2 font-medium">
              {languageName(idioma)(t)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        <tr>
          {IDIOMAS.map((idioma) => (
            <td key={idioma} data-lang={idioma} className="align-top pr-4">
              <Cell measurement={celdas.find(([clave]) => clave === idioma)?.[1]} />
            </td>
          ))}
        </tr>
      </tbody>
    </table>
  );
}

function Cell({ measurement }: { readonly measurement: Measurement | undefined }) {
  const { locale } = useLocale();
  if (measurement?.state === "measured" && measurement.value != null) {
    const texto = new Intl.NumberFormat(locale, {
      style: "percent",
      maximumFractionDigits: 1,
    }).format(measurement.value);
    return (
      <span data-cell-state="measured" className="text-figure font-light text-fg">
        {texto}
      </span>
    );
  }
  return (
    <div data-cell-state="not_measured">
      <NotMeasuredNote cause={measurement?.not_measured_cause} />
    </div>
  );
}

function NotMeasuredNote({ cause }: { readonly cause: Figure["not_measured_cause"] }) {
  const { t } = useLocale();
  return (
    <div data-testid="metrics-cause" className="flex flex-col gap-1">
      <p className="text-body font-medium text-fg-secondary">{t("metrics.not_measured")}</p>
      {cause != null ? <p className="text-small text-fg-secondary">{causeText(cause)(t)}</p> : null}
    </div>
  );
}

function LatencyDetail({ measures }: { readonly measures: readonly LatencyMeasure[] }) {
  const { t } = useLocale();
  return (
    <ul data-testid="metrics-latency-detail" className="flex flex-col gap-6 text-small">
      {measures.map((medida) => {
        const lecturas = medida.by_language ?? {};
        const conLecturas = Object.keys(lecturas).length > 0;
        return (
          <li
            key={medida.channel}
            data-channel={medida.channel}
            className="flex flex-col gap-3 text-fg-secondary"
          >
            <p>
              <span className="font-medium text-fg">{channelName(medida.channel)(t)}</span>
              {" · "}
              {t("metrics.latency.between", {
                start: eventName(medida.start)(t),
                end: eventName(medida.end)(t),
              })}
              {" · "}
              {t("metrics.latency.dataset", { dataset: medida.dataset })}
              {" · "}
              {t("metrics.latency.percentiles")}
            </p>
            {/* La causa **de este canal**, y no solo la de la cifra. Las dos latencias no
                estan sin medir por lo mismo: la de la voz es una decision (por hito, contra
                proveedores de verdad) y la del chat sale de la linea base, asi que le falta
                una linea base, o una que traiga latencias. Sin esta nota el panel decia "por
                hito" de las dos y mandaba a esperar un hito donde hay que publicar una linea
                base. */}
            {medida.not_measured_cause != null ? (
              <NotMeasuredNote cause={medida.not_measured_cause} />
            ) : null}
            {conLecturas ? <LatencyTable readings={lecturas} /> : null}
            {conLecturas && medida.channel === "chat" ? (
              <p data-testid="metrics-latency-environment">
                {t("metrics.latency.environment_chat")}
              </p>
            ) : null}
            {medida.source != null ? <SourceLine source={medida.source} /> : null}
          </li>
        );
      })}
    </ul>
  );
}

function LatencyTable({
  readings,
}: {
  readonly readings: Readonly<Record<string, LatencyReading>>;
}) {
  const { t } = useLocale();
  const lecturas = Object.entries(readings);
  return (
    <table className="w-full max-w-[36rem] text-left text-body">
      <thead>
        <tr className="text-small text-fg-secondary">
          {IDIOMAS.map((idioma) => (
            <th key={idioma} scope="col" className="pb-2 font-medium">
              {languageName(idioma)(t)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        <tr>
          {IDIOMAS.map((idioma) => (
            <td key={idioma} data-lang={idioma} className="align-top pr-4">
              <LatencyCell reading={lecturas.find(([clave]) => clave === idioma)?.[1]} />
            </td>
          ))}
        </tr>
      </tbody>
    </table>
  );
}

/**
 * Una lectura: las dos cifras en palabras llanas y, siempre al lado, cuantos turnos las
 * sostienen. Una no medida dice su causa y el recuento que si hubo, nunca un tiempo.
 */
function LatencyCell({ reading }: { readonly reading: LatencyReading | undefined }) {
  const { t, locale } = useLocale();
  if (reading?.state === "measured" && reading.p50_ms != null && reading.p95_ms != null) {
    return (
      <div data-cell-state="measured" className="flex flex-col gap-1">
        <p className="text-fg">
          {t("metrics.latency.half", { time: formatDuration(reading.p50_ms, locale) })}
        </p>
        <p className="text-fg">
          {t("metrics.latency.most", { time: formatDuration(reading.p95_ms, locale) })}
        </p>
        <p className="text-small text-fg-secondary">
          {t("metrics.latency.turns", { count: reading.turns ?? 0 })}
        </p>
      </div>
    );
  }
  return (
    <div data-cell-state="not_measured" className="flex flex-col gap-1">
      <NotMeasuredNote cause={reading?.not_measured_cause} />
      {reading != null ? (
        <p className="text-small text-fg-secondary">
          {t("metrics.latency.turns", { count: reading.turns ?? 0 })}
        </p>
      ) : null}
    </div>
  );
}

function SourceLine({ source }: { readonly source: FigureSource }) {
  const { t, locale } = useLocale();
  const fecha = new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(
    new Date(source.published_at),
  );
  return (
    <dl data-testid="metrics-source" className="flex flex-wrap gap-x-6 gap-y-1 text-small">
      <div className="flex gap-2">
        <dt className="text-fg-secondary">{t("metrics.source.date")}</dt>
        <dd className="text-fg">{fecha}</dd>
      </div>
      <div className="flex gap-2">
        <dt className="text-fg-secondary">{t("metrics.source.commit")}</dt>
        <dd className="font-mono text-fg">{source.commit_sha.slice(0, 7)}</dd>
      </div>
      <div className="flex gap-2">
        <dt className="text-fg-secondary">{t("metrics.source.run")}</dt>
        <dd className="text-fg">
          {source.run_url != null ? (
            <a href={source.run_url} className="underline">
              {source.run_id}
            </a>
          ) : (
            source.run_id
          )}
        </dd>
      </div>
    </dl>
  );
}
