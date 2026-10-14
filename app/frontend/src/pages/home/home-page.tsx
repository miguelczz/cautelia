// El inicio de la demo (M1; F2; BR4.1 a BR4.5).
//
// Cuatro estados:
// - Cargando: el esqueleto del inicio.
// - Sin canales: la linea de demostracion, la linea honesta de que todavia no
//   hay canales abiertos (BR4.3) y las filas sin botones de canal.
// - Con canales: el titulo corto, las filas con las acciones montadas y, abajo a
//   la derecha, los botones a la comparacion (si esta montada) y a la guia "Como
//   funciona", donde viven el paso a paso y lo que se puede probar. Menos texto a
//   la vista, por decision de Miguel (2026-10-06): la seccion de aseguradoras se
//   titula con la accion que se pide, y nada de lo que se decia se pierde: pasa a
//   la guia.
// - Error: el mensaje del catalogo y "Reintentar", sin filas inventadas (F2
//   paso 5, BR3.2).
//
// Nada de lo que se ve aqui sale de una lista escrita en el codigo: las
// aseguradoras vienen de su configuracion y las superficies del servidor.

import { ArrowRightIcon } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { toProblemView } from "../../shared/api-client/problems";
import { siteQueryOptions, type SiteDirectory } from "../../shared/api-client/site";
import { useLocale } from "../../shared/i18n/locale-provider";
import type { Message } from "../../shared/i18n/translate";
import { useAnnouncer } from "../../shared/ui/announcer";
import { Button } from "../../shared/ui/button";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { cn } from "../../shared/ui/cn";
import {
  HOME_HEADER_SPACE,
  PAGE_CONTENT,
  PAGE_TITLE,
  SECTION_TITLE,
} from "../../shared/ui/page-layout";
import { PageSkeleton } from "../../shared/ui/page-skeletons";
import { COMPARISON_HREF, GUIDE_HREF, mountedChannels } from "../../app/surfaces";
import { InsurerRow } from "./insurer-row";

export function HomePage() {
  const consulta = useQuery(siteQueryOptions());

  if (consulta.isPending) {
    return <HomeLoading />;
  }
  if (consulta.isError) {
    return (
      <HomeError
        error={consulta.error}
        onRetry={() => {
          void consulta.refetch();
        }}
      />
    );
  }
  return <HomeContent directory={consulta.data} />;
}

function HomeLoading() {
  const { t } = useLocale();
  return <PageSkeleton kind="home" label={t("home.loading")} />;
}

function HomeError({ error, onRetry }: { readonly error: unknown; readonly onRetry: () => void }) {
  const { t } = useLocale();
  const { announce } = useAnnouncer();
  const vista = toProblemView(error);
  const mensaje = vista.message(t);
  const anunciado = useRef(false);

  // El error se anuncia una vez, como mensaje de estado (interaction-spec.md).
  useEffect(() => {
    if (!anunciado.current) {
      anunciado.current = true;
      announce(mensaje);
    }
  }, [announce, mensaje]);

  return (
    <div className={PAGE_CONTENT} data-testid="home" data-home-state="error">
      <header className="flex max-w-[46rem] flex-col gap-4">
        <h1 className={PAGE_TITLE}>{t("home.title_neutral")}</h1>
      </header>
      <InlineAlert
        tone="danger"
        data-testid="home-error"
        action={
          <Button variant="secondary" onClick={onRetry}>
            {t("action.retry")}
          </Button>
        }
      >
        <p>{mensaje}</p>
      </InlineAlert>
    </div>
  );
}

/** El titulo de la seccion de aseguradoras: la accion que se pide, segun los canales montados. */
function insurersTitle(canales: { readonly chat: boolean; readonly voice: boolean }): Message {
  if (canales.chat && canales.voice) {
    return (t) => t("home.how.report_both");
  }
  if (canales.chat) {
    return (t) => t("home.how.report_chat");
  }
  if (canales.voice) {
    return (t) => t("home.how.report_voice");
  }
  return (t) => t("home.insurers.title");
}

function HomeContent({ directory }: { readonly directory: SiteDirectory }) {
  const { t } = useLocale();
  const canales = mountedChannels(directory.surfaces);
  const conCanales = canales.chat || canales.voice;

  return (
    <div
      className={PAGE_CONTENT}
      data-testid="home"
      data-home-state={conCanales ? "with_channels" : "no_channels"}
    >
      <header className={cn("flex max-w-[46rem] flex-col gap-3", HOME_HEADER_SPACE)}>
        <h1 className={PAGE_TITLE}>{conCanales ? t("home.title") : t("home.title_neutral")}</h1>
        <p className="text-body text-fg-secondary" data-testid="home-demo-line">
          {t("home.demo_line")}
        </p>
        {conCanales ? null : (
          <p className="text-body text-fg" data-testid="home-no-channels">
            {t("home.no_channels")}
          </p>
        )}
      </header>

      <section aria-labelledby="home-insurers" className="flex flex-col gap-3">
        <h2 id="home-insurers" className={SECTION_TITLE}>
          {insurersTitle(canales)(t)}
        </h2>
        <ul className="flex flex-col border-b border-hairline" data-testid="insurer-list">
          {directory.tenants.map((aseguradora) => (
            <InsurerRow
              key={aseguradora.tenant_id}
              tenant={aseguradora}
              surfaces={directory.surfaces}
            />
          ))}
        </ul>
      </section>

      {/* A la derecha, bajo las filas: la comparacion, si esta montada, y la guia. */}
      <div className="flex flex-wrap items-center justify-end gap-3" data-testid="home-actions">
        {directory.surfaces.includes("comparison") ? (
          <Button asChild variant="secondary">
            <a href={COMPARISON_HREF}>{t("surface.comparison")}</a>
          </Button>
        ) : null}
        <Button asChild variant="secondary">
          <a href={GUIDE_HREF}>
            {t("home.how.title")}
            <ArrowRightIcon aria-hidden="true" focusable="false" size={18} />
          </a>
        </Button>
      </div>
    </div>
  );
}
