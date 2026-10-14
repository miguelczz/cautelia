// El tablero "Que tan bien funciona": la ultima corrida completa de evaluacion, como
// salio (decision de Miguel del 2026-10-09). No es la linea base --que solo se publica
// en verde y diria siempre 100 %--: trae sus fallos y lo que no se midio.
//
// Tres reglas que la pantalla sostiene: los dos idiomas van lado a lado y nunca se
// suman (P12); "no se midio" se dice con su motivo y nunca como cero ni como bien; y
// todo en palabras de quien llega, que no sabe que es un conjunto de prueba.

import { CheckCircleIcon, MinusCircleIcon, XCircleIcon } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";

import {
  qualityQueryOptions,
  type QualityBoard,
  type Tally,
  type TallyByLanguage,
} from "../../shared/api-client/quality";
import { toProblemView } from "../../shared/api-client/problems";
import { useLocale } from "../../shared/i18n/locale-provider";
import type { Translate } from "../../shared/i18n/translate";
import { Button } from "../../shared/ui/button";
import { cn } from "../../shared/ui/cn";
import { Disclosure, DisclosureContent, DisclosureTrigger } from "../../shared/ui/disclosure";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { SECTION_TITLE } from "../../shared/ui/page-layout";
import { PanelBodySkeleton } from "../../shared/ui/page-skeletons";
import { useMoment } from "../spend/spend-format";
import { datasetHelp, datasetName, gateName, notMeasuredReason, rootCause } from "./quality-labels";

const SECCION =
  "flex flex-col gap-5 rounded-surface border border-hairline bg-surface p-5 tablet:p-6";
const TARJETA = "flex flex-col gap-3 rounded-surface border border-hairline bg-surface p-5";
const ETIQUETA = "text-small text-fg-secondary";
const CIFRA = "font-display text-figure leading-none font-light text-fg tabular-nums";

type Idioma = "es" | "en";
const IDIOMAS: readonly Idioma[] = ["es", "en"];

function languageLabel(idioma: Idioma, t: Translate): string {
  return idioma === "es" ? t("quality.lang.es") : t("quality.lang.en");
}

function total(conteo: Tally): number {
  return (conteo.passed ?? 0) + (conteo.failed ?? 0) + (conteo.not_measured ?? 0);
}

function tallyOf(porIdioma: TallyByLanguage, idioma: Idioma): Tally {
  return (idioma === "es" ? porIdioma.es : porIdioma.en) ?? {};
}

function SectionHeader({ title, lead }: { readonly title: string; readonly lead: string }) {
  return (
    <header className="flex flex-col gap-1">
      <h2 className={SECTION_TITLE}>{title}</h2>
      <p className="text-body text-fg-secondary">{lead}</p>
    </header>
  );
}

/** La barra de un recuento: bien, fallo y no medido, cada uno con su ancho. */
function TallyBar({ tally, label }: { readonly tally: Tally; readonly label: string }) {
  const suma = total(tally);
  const partes = [
    { clave: "passed", valor: tally.passed ?? 0, clase: "bg-success" },
    { clave: "failed", valor: tally.failed ?? 0, clase: "bg-danger" },
    { clave: "not_measured", valor: tally.not_measured ?? 0, clase: "bg-fg-tertiary" },
  ];
  return (
    <div
      role="img"
      aria-label={label}
      className="flex h-2 w-full overflow-hidden rounded-pill bg-surface-alt"
    >
      {suma === 0
        ? null
        : partes
            .filter((parte) => parte.valor > 0)
            .map((parte) => (
              <span
                key={parte.clave}
                className={parte.clase}
                style={{ width: `${String((parte.valor / suma) * 100)}%` }}
              />
            ))}
    </div>
  );
}

/** "12 de 14", y debajo cuantos fallan y cuantos no se midieron, si los hay. */
function TallyLine({ tally }: { readonly tally: Tally }) {
  const { t } = useLocale();
  const fallan = tally.failed ?? 0;
  const sinMedir = tally.not_measured ?? 0;
  const resumen = t("quality.totals.passed", {
    passed: String(tally.passed ?? 0),
    total: String(total(tally)),
  });
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <span className="text-fg tabular-nums">{resumen}</span>
        <span className="flex gap-3 text-small tabular-nums">
          {fallan > 0 ? (
            <span className="text-danger">
              {t("quality.count.failed", { count: String(fallan) })}
            </span>
          ) : null}
          {sinMedir > 0 ? (
            <span className="text-fg-secondary">
              {t("quality.count.not_measured", { count: String(sinMedir) })}
            </span>
          ) : null}
        </span>
      </div>
      <TallyBar tally={tally} label={resumen} />
    </div>
  );
}

function Legend() {
  const { t } = useLocale();
  const partes = [
    { clase: "bg-success", texto: t("quality.legend.passed") },
    { clase: "bg-danger", texto: t("quality.legend.failed") },
    { clase: "bg-fg-tertiary", texto: t("quality.legend.not_measured") },
  ];
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-small text-fg-secondary">
      {partes.map((parte) => (
        <li key={parte.texto} className="flex items-center gap-2">
          <span aria-hidden="true" className={cn("size-2.5 rounded-pill", parte.clase)} />
          {parte.texto}
        </li>
      ))}
    </ul>
  );
}

/** Que es esto, en una frase, y de cuando es. Lo unico que hay que leer para ubicarse. */
function Intro({ board }: { readonly board: QualityBoard }) {
  const { t } = useLocale();
  const momento = useMoment();
  const situaciones = IDIOMAS.reduce(
    (suma, idioma) => suma + total(tallyOf(board.totals, idioma)),
    0,
  );
  const minutos =
    board.duration_seconds === null || board.duration_seconds === undefined
      ? null
      : Math.max(1, Math.round(board.duration_seconds / 60));
  return (
    <div className="flex max-w-[46rem] flex-col gap-2" data-testid="quality-intro">
      <p className="text-body text-fg">{t("quality.intro", { total: String(situaciones) })}</p>
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-small text-fg-secondary">
        <span>{t("quality.run.when", { when: momento(board.produced_at) })}</span>
        {minutos === null ? null : (
          <span>{t("quality.run.duration", { minutes: String(minutos) })}</span>
        )}
      </p>
    </div>
  );
}

/** Lo tecnico de la corrida, plegado: quien lo busca lo abre; quien no, no lo carga. */
function RunDetails({ board }: { readonly board: QualityBoard }) {
  const { t } = useLocale();
  return (
    <Disclosure data-testid="quality-run">
      <DisclosureTrigger className="-ml-2">{t("quality.run.details")}</DisclosureTrigger>
      <DisclosureContent className="flex flex-col gap-2 pt-2 text-small text-fg-secondary">
        <p>{t("quality.run.commit", { commit: board.commit_sha.slice(0, 7) })}</p>
        {(board.models ?? []).length === 0 ? null : (
          <p className="flex flex-wrap items-center gap-2">
            <span>{t("quality.run.models")}</span>
            {(board.models ?? []).map((modelo) => (
              <code key={modelo} className="rounded-button bg-surface-alt px-2 py-0.5 text-fg">
                {modelo}
              </code>
            ))}
          </p>
        )}
        {board.comparable === false ? <p>{t("quality.run.not_comparable")}</p> : null}
        {board.dirty_tree === true ? <p>{t("quality.run.dirty")}</p> : null}
      </DisclosureContent>
    </Disclosure>
  );
}

function Totals({ board }: { readonly board: QualityBoard }) {
  const { t } = useLocale();
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-4 tablet:grid-cols-2" data-testid="quality-totals">
        {IDIOMAS.map((idioma) => {
          const conteo = tallyOf(board.totals, idioma);
          const fallan = conteo.failed ?? 0;
          const sinMedir = conteo.not_measured ?? 0;
          const resumen = t("quality.totals.passed", {
            passed: String(conteo.passed ?? 0),
            total: String(total(conteo)),
          });
          return (
            <div key={idioma} className={TARJETA} data-testid={`quality-total-${idioma}`}>
              <span className={ETIQUETA}>{languageLabel(idioma, t)}</span>
              <span className={CIFRA}>{resumen}</span>
              <span className="text-small text-fg-secondary">{t("quality.totals.hint")}</span>
              <TallyBar tally={conteo} label={resumen} />
              <span className="flex flex-wrap gap-x-4 text-small tabular-nums">
                <span className={fallan > 0 ? "text-danger" : "text-fg-secondary"}>
                  {t("quality.count.failed", { count: String(fallan) })}
                </span>
                <span className="text-fg-secondary">
                  {t("quality.count.not_measured", { count: String(sinMedir) })}
                </span>
              </span>
            </div>
          );
        })}
      </div>
      <Legend />
    </div>
  );
}

function Datasets({ board }: { readonly board: QualityBoard }) {
  const { t } = useLocale();
  return (
    <Disclosure data-testid="quality-datasets">
      <DisclosureTrigger className="-ml-2">{t("quality.datasets.title")}</DisclosureTrigger>
      <DisclosureContent className="pt-3">
        <ul className="flex flex-col gap-6">
          {(board.datasets ?? []).map((conjunto) => (
            <li key={conjunto.dataset} className="flex flex-col gap-3">
              <div className="flex flex-col gap-0.5">
                <span className="font-medium text-fg">{datasetName(conjunto.dataset)(t)}</span>
                <span className="text-small text-fg-secondary">
                  {datasetHelp(conjunto.dataset)(t)}
                </span>
              </div>
              <div className="grid gap-x-8 gap-y-3 tablet:grid-cols-2">
                {IDIOMAS.map((idioma) => (
                  <div key={idioma} className="flex flex-col gap-1">
                    <span className={ETIQUETA}>{languageLabel(idioma, t)}</span>
                    <TallyLine tally={tallyOf(conjunto.by_language, idioma)} />
                  </div>
                ))}
              </div>
            </li>
          ))}
        </ul>
      </DisclosureContent>
    </Disclosure>
  );
}

/** Lo que dice una regla dura en un idioma: todas bien, cuantas fallan, o no se midio.
 *  El icono dice lo mismo que el texto: nadie depende del color para entenderlo. */
function GateCell({ tally }: { readonly tally: Tally }) {
  const { t } = useLocale();
  const medidas = (tally.passed ?? 0) + (tally.failed ?? 0);
  const icono = { "aria-hidden": true, focusable: false, size: 18, className: "shrink-0" } as const;
  if (medidas === 0) {
    return (
      <span className="inline-flex items-center gap-1.5 text-fg-secondary">
        <MinusCircleIcon {...icono} />
        {t("quality.gate.not_measured")}
      </span>
    );
  }
  if ((tally.failed ?? 0) > 0) {
    return (
      <span className="inline-flex items-center gap-1.5 font-medium text-danger tabular-nums">
        <XCircleIcon {...icono} weight="fill" />
        {t("quality.gate.some_failed", {
          failed: String(tally.failed ?? 0),
          total: String(medidas),
        })}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-success tabular-nums">
      <CheckCircleIcon {...icono} weight="fill" />
      {t("quality.gate.all_passed", { total: String(medidas) })}
    </span>
  );
}

/**
 * Las columnas de las reglas, en una rejilla de una regla y dos idiomas. Las columnas de
 * idioma miden lo mismo en el encabezado y en cada fila, para que el rotulo caiga sobre
 * su cifra.
 */
const REJILLA_DE_REGLAS =
  "tablet:grid-cols-[minmax(0,1fr)_repeat(2,minmax(0,11rem))] tablet:gap-x-6";

function Gates({ board }: { readonly board: QualityBoard }) {
  const { t } = useLocale();
  return (
    <section className={SECCION} data-testid="quality-gates">
      <SectionHeader title={t("quality.gates.title")} lead={t("quality.gates.lead")} />
      <div className="flex flex-col">
        {/* Desde tableta, "En espanol" y "En ingles" se dicen una sola vez, arriba de las dos
            columnas. Es decorativo para el lector de pantalla: en cada celda sigue su rotulo
            (oculto a la vista), asi que cada resultado se lee con su regla y su idioma. En
            telefono no hay columnas y cada celda lleva el suyo a la vista. */}
        <div
          aria-hidden="true"
          data-testid="quality-gates-columns"
          className={cn("hidden border-b border-hairline pb-2 tablet:grid", REJILLA_DE_REGLAS)}
        >
          <span />
          {IDIOMAS.map((idioma) => (
            <span key={idioma} className={ETIQUETA}>
              {languageLabel(idioma, t)}
            </span>
          ))}
        </div>
        <ul className="flex flex-col divide-y divide-hairline">
          {(board.gates ?? []).map((regla) => (
            <li
              key={regla.family}
              className={cn(
                "grid gap-x-6 gap-y-2 py-3 first:pt-0 last:pb-0 tablet:items-center tablet:first:pt-3",
                REJILLA_DE_REGLAS,
              )}
            >
              <span className="font-medium text-fg">{gateName(regla.family)(t)}</span>
              {IDIOMAS.map((idioma) => (
                <span key={idioma} className="flex flex-col gap-0.5">
                  <span className={cn(ETIQUETA, "tablet:sr-only")}>{languageLabel(idioma, t)}</span>
                  <GateCell tally={tallyOf(regla.by_language, idioma)} />
                </span>
              ))}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function Failures({ board }: { readonly board: QualityBoard }) {
  const { t } = useLocale();
  const fallos = board.failures ?? [];
  return (
    <section className={SECCION} data-testid="quality-failures">
      <h2 className={SECTION_TITLE}>{t("quality.failures.title")}</h2>
      {fallos.length === 0 ? (
        <p className="text-body text-fg-secondary">{t("quality.failures.none")}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-hairline">
          {fallos.map((fallo) => (
            <li key={fallo.case_key} className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0">
              {/* Primero en palabras: que tipo de prueba y en que idioma. El
                  identificador del conjunto queda como referencia, en pequeno. */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-fg">
                  {datasetName(fallo.dataset)(t)} ·{" "}
                  {languageLabel(fallo.language === "en" ? "en" : "es", t)}
                </span>
                {fallo.blocking === true ? (
                  <span className="rounded-pill bg-danger px-2.5 py-0.5 text-caption font-medium text-page">
                    {t("quality.failures.blocking")}
                  </span>
                ) : null}
              </div>
              {/* Sin causa anotada no se escribe "sin causa": es ruido para quien lee. */}
              {fallo.root_cause === null || fallo.root_cause === undefined ? null : (
                <span className="text-small text-fg-secondary">
                  {t("quality.failures.cause")}: {rootCause(fallo.root_cause)(t)}
                </span>
              )}
              <span className="text-caption text-fg-secondary">
                {t("quality.failures.reference")}:{" "}
                <code className="break-all">{fallo.case_key}</code>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Pending({ board }: { readonly board: QualityBoard }) {
  const { t } = useLocale();
  const grupos = board.not_measured ?? [];
  return (
    <section className={SECCION} data-testid="quality-pending">
      <SectionHeader title={t("quality.pending.title")} lead={t("quality.pending.lead")} />
      <ul className="flex flex-col gap-2 text-body text-fg">
        {grupos.length === 0 ? (
          <li className="text-fg-secondary">{t("quality.pending.none")}</li>
        ) : (
          grupos.map((grupo) => (
            <li key={grupo.cause}>
              <span className="tabular-nums">
                {t("quality.pending.count", { count: String(grupo.count) })}
              </span>{" "}
              {notMeasuredReason(grupo.cause)(t)}
            </li>
          ))
        )}
        <li className="text-fg-secondary">{t("quality.pending.always.voice")}</li>
        <li className="text-fg-secondary">{t("quality.pending.always.chat")}</li>
      </ul>
    </section>
  );
}

/** De lo que cualquiera entiende a lo que solo busca quien revisa: que es, como le fue,
 *  las reglas que no se pueden romper, que fallo y que no se midio; el desglose y lo
 *  tecnico quedan plegados al final (Miguel, 2026-10-11: clara, corta, sin enredos). */
function Board({ board }: { readonly board: QualityBoard }) {
  return (
    <div className="flex flex-col gap-6" data-testid="quality-dashboard">
      <Intro board={board} />
      <Totals board={board} />
      <Gates board={board} />
      <Failures board={board} />
      <Pending board={board} />
      <div className="flex flex-col gap-1">
        <Datasets board={board} />
        <RunDetails board={board} />
      </div>
    </div>
  );
}

export function QualityDashboard() {
  const { t } = useLocale();
  const consulta = useQuery(qualityQueryOptions());

  if (consulta.isPending) {
    return <PanelBodySkeleton label={t("quality.loading")} />;
  }
  if (consulta.isError) {
    return (
      <InlineAlert
        tone="danger"
        data-testid="quality-error"
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
  if (consulta.data === null) {
    return (
      <p className="text-body text-fg-secondary" data-testid="quality-empty">
        {t("quality.empty")}
      </p>
    );
  }
  return <Board board={consulta.data} />;
}
