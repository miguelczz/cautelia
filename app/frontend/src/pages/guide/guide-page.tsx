// La guia "Como funciona" (decision de Miguel, 2026-10-06): el recorrido paso a paso
// y el instructivo para quien quiera probar la demostracion. Es la pagina a la que
// lleva el boton bajo las aseguradoras del inicio, y recoge lo que el inicio dejo de
// decir (plan-estilos-2026-10.md, seccion 9).
//
// Lo que cuenta sale de lo construido, igual que en el inicio (BR4.1): cada paso y
// cada linea de "Que puedes probar" solo aparece si su superficie esta montada, y
// las aseguradoras vienen del directorio del sitio con el texto de su caracter, el
// mismo de su fila. Nada de esto se lista en el codigo.
//
// Reorganizada el 2026-10-11 (Miguel: "desorganizada y un poco confusa"): primero que
// es Cautelia, en tres frases; despues el recorrido en una fila de pasos; y al final,
// lado a lado, lo que mas se puede probar --con su enlace-- y lo que cambia entre
// aseguradoras. En un computador con espacio cabe en una sola vista.

import { ArrowRightIcon } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";

import { toProblemView } from "../../shared/api-client/problems";
import { siteQueryOptions, type SiteDirectory } from "../../shared/api-client/site";
import { TENANT_CHARACTERS } from "../../shared/copy/tenant-characters";
import { useLocale } from "../../shared/i18n/locale-provider";
import type { Message } from "../../shared/i18n/translate";
import { tenantAccentStyle } from "../../shared/theme/tenant-accent";
import { Button } from "../../shared/ui/button";
import { cn } from "../../shared/ui/cn";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { Monogram } from "../../shared/ui/monogram";
import {
  GUIDE_CONTENT,
  PAGE_CONTENT,
  PAGE_TITLE,
  SECTION_TITLE,
} from "../../shared/ui/page-layout";
import { PageSkeleton } from "../../shared/ui/page-skeletons";
import { COMPARISON_HREF, mountedChannels } from "../../app/surfaces";

// Las dos paginas que la guia enlaza y que no dependen de una aseguradora.
const CASES_HREF = "/cases";
const TELEMETRY_HREF = "/telemetry";

interface Paso {
  readonly title: Message;
  readonly body: Message;
}

export function GuidePage() {
  const consulta = useQuery(siteQueryOptions());
  const { t } = useLocale();

  if (consulta.isPending) {
    return <PageSkeleton kind="guide" />;
  }
  if (consulta.isError) {
    return (
      <div className={PAGE_CONTENT} data-testid="guide" data-guide-state="error">
        <InlineAlert
          tone="danger"
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
      </div>
    );
  }
  return <GuideContent directory={consulta.data} />;
}

/** El recorrido: solo los pasos que lo construido permite hacer (BR4.1). */
function stepsFor(directory: SiteDirectory): readonly Paso[] {
  const canales = mountedChannels(directory.surfaces);
  const pasos: Paso[] = [
    {
      title: (t) => t("guide.steps.choose.title"),
      body: (t) => t("guide.steps.choose.body"),
    },
  ];
  if (!canales.chat && !canales.voice) {
    return pasos;
  }
  const canal: Message =
    canales.chat && canales.voice
      ? (t) => t("guide.steps.report.both")
      : canales.chat
        ? (t) => t("guide.steps.report.chat")
        : (t) => t("guide.steps.report.voice");
  pasos.push({
    title: (t) => t("guide.steps.report.title"),
    body: (t) => `${canal(t)} ${t("guide.steps.report.policy")}`,
  });
  if (directory.surfaces.includes("case_link")) {
    pasos.push(
      {
        title: (t) => t("guide.steps.link.title"),
        body: (t) => t("guide.steps.link.body"),
      },
      {
        title: (t) => t("guide.steps.decide.title"),
        body: (t) => t("guide.steps.decide.body"),
      },
    );
  }
  return pasos;
}

interface Prueba {
  readonly text: Message;
  /** A donde lleva, cuando lo que se propone probar tiene su propia pagina. */
  readonly href?: string;
}

/** "Que mas puedes probar": cada linea solo si su superficie esta montada (BR4.1). */
function triesFor(directory: SiteDirectory): readonly Prueba[] {
  const canales = mountedChannels(directory.surfaces);
  const pruebas: Prueba[] = [];
  if (canales.chat) {
    pruebas.push({ text: (t) => t("guide.try.ask_coverage") });
  }
  if (canales.voice) {
    pruebas.push({ text: (t) => t("guide.try.interrupt") });
  }
  if (directory.surfaces.includes("comparison")) {
    pruebas.push({ text: (t) => t("guide.try.compare"), href: COMPARISON_HREF });
  }
  pruebas.push({ text: (t) => t("guide.try.cases"), href: CASES_HREF });
  if (directory.surfaces.includes("metrics_panel")) {
    pruebas.push({ text: (t) => t("guide.try.telemetry"), href: TELEMETRY_HREF });
  }
  return pruebas;
}

function GuideContent({ directory }: { readonly directory: SiteDirectory }) {
  const { t } = useLocale();
  const pasos = stepsFor(directory);
  const pruebas = triesFor(directory);

  // Las tres franjas comparten la misma rejilla de seis pulgadas de intercolumna: los
  // pasos son cuatro columnas y el contexto y los dos bloques de abajo son dos, de modo
  // que la segunda mitad empieza justo donde empieza el tercer paso.
  return (
    <div className={GUIDE_CONTENT} data-testid="guide" data-guide-state="ready">
      {/* Que es esto, antes de como se usa: el titulo y, al lado, lo que es de ejemplo y
          lo que la agente no hace. Tres frases; nadie tiene que leer mas para ubicarse. */}
      <header className="grid gap-x-6 gap-y-4 desktop:grid-cols-2 desktop:items-end">
        <div className="flex flex-col gap-3 roomy:gap-[clamp(0.25rem,1.2dvh,0.75rem)]">
          <h1 className={PAGE_TITLE}>{t("guide.title")}</h1>
          <p
            className="max-w-[40rem] text-lead text-fg-secondary desktop:max-w-none roomy:text-[length:clamp(0.9375rem,2dvh,1.2rem)]"
            data-testid="guide-about"
          >
            {t("guide.about.what")}
          </p>
        </div>
        <ul className="flex flex-col gap-2 border-l-2 border-brand pl-4 text-body text-fg roomy:text-[length:clamp(0.9375rem,2dvh,1rem)]">
          <li>{t("guide.about.limit")}</li>
          <li className="text-fg-secondary">{t("guide.about.sample")}</li>
        </ul>
      </header>

      {/* Una secuencia real, por eso numerada y de izquierda a derecha. */}
      <section aria-labelledby="guide-steps" className="flex flex-col gap-3 roomy:gap-2">
        {/* El boton para empezar va junto al recorrido, que es lo que invita a hacer:
            al final de la pagina quedaba fuera de la vista. */}
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
          <h2 id="guide-steps" className={SECTION_TITLE}>
            {t("guide.steps.title")}
          </h2>
          <Button asChild variant="primary">
            <a href="/home">{t("guide.start")}</a>
          </Button>
        </div>
        <ol
          className={cn(
            "grid gap-x-6 gap-y-4 tablet:grid-cols-2",
            pasos.length >= 4 ? "desktop:grid-cols-4" : "desktop:grid-cols-2",
          )}
          data-testid="guide-steps"
        >
          {pasos.map((paso, indice) => (
            <li key={indice} className="flex flex-col gap-1 border-t-2 border-hairline pt-3">
              {/* El numero y el titulo en un renglon: ahorra uno por paso y se lee igual. */}
              <div className="flex items-baseline gap-2.5">
                <span aria-hidden="true" className="font-mono text-small text-brand tabular-nums">
                  {String(indice + 1).padStart(2, "0")}
                </span>
                <h3 className="text-lead font-medium text-fg">{paso.title(t)}</h3>
              </div>
              <p className="text-small text-fg-secondary">{paso.body(t)}</p>
            </li>
          ))}
        </ol>
      </section>

      <div className="grid gap-x-6 gap-y-8 desktop:grid-cols-2">
        <section
          aria-labelledby="guide-try"
          className="flex flex-col gap-3 roomy:gap-2"
          data-testid="guide-try"
        >
          <h2 id="guide-try" className={SECTION_TITLE}>
            {t("guide.try.title")}
          </h2>
          <ul className="flex flex-col">
            {pruebas.map((prueba, indice) => (
              <li key={indice} className="border-t border-hairline">
                {prueba.href === undefined ? (
                  <p className="py-2.5 text-body text-fg roomy:py-[clamp(0.25rem,0.75dvh,0.625rem)]">
                    {prueba.text(t)}
                  </p>
                ) : (
                  <a
                    href={prueba.href}
                    className="group flex items-center justify-between gap-4 rounded-control py-2.5 text-body text-fg no-underline hover:text-brand roomy:py-[clamp(0.25rem,0.75dvh,0.625rem)]"
                  >
                    <span>{prueba.text(t)}</span>
                    <ArrowRightIcon
                      aria-hidden="true"
                      focusable="false"
                      size={18}
                      className="shrink-0 text-brand motion-safe:transition-transform motion-safe:duration-[160ms] motion-safe:group-hover:translate-x-0.5"
                    />
                  </a>
                )}
              </li>
            ))}
          </ul>
        </section>

        <section
          aria-labelledby="guide-differences"
          className="flex flex-col gap-3 roomy:gap-2"
          data-testid="guide-differences"
        >
          <h2 id="guide-differences" className={SECTION_TITLE}>
            {t("guide.differences.title")}
          </h2>
          {/* La frase de que todas hacen lo mismo y el consejo para notarlo van juntos, en
              un solo parrafo bajo el titulo: leidos de corrido dicen "esto es lo que
              cambia y asi lo ves". */}
          <p className="text-small text-fg-secondary">
            {t("guide.differences.same")} {t("guide.differences.tip")}
          </p>
          <ul className="flex flex-col">
            {directory.tenants.map((aseguradora) => {
              const caracter =
                aseguradora.character_key === undefined || aseguradora.character_key === null
                  ? undefined
                  : TENANT_CHARACTERS.get(aseguradora.character_key);
              return (
                <li
                  key={aseguradora.tenant_id}
                  data-tenant-scope=""
                  data-testid="guide-insurer"
                  style={tenantAccentStyle(aseguradora.brand)}
                  className="flex items-start gap-3 border-t border-hairline py-2.5 roomy:py-[clamp(0.25rem,0.75dvh,0.625rem)]"
                >
                  {aseguradora.brand ? (
                    <Monogram shape={aseguradora.brand.monogram} className="size-10" />
                  ) : null}
                  <div className="flex min-w-0 flex-col">
                    <h3 className="text-body font-medium text-tenant">
                      {aseguradora.display_name}
                    </h3>
                    <p className="text-small text-fg-secondary">
                      {t("guide.differences.agent", { agent: aseguradora.agent_name })}
                      {caracter === undefined ? "" : ` ${caracter(t)}`}
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      </div>
    </div>
  );
}
