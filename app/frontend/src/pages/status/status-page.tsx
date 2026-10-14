// La plantilla unica de las seis paginas de estado (M11, BR5.5 a BR5.7).
//
// Titulo, explicacion y una accion, todo del catalogo. El titulo es el
// encabezado de primer nivel y **recibe el foco al aparecer**, para que el lector
// de pantalla diga el estado sin buscarlo (frontend-components.md).
//
// La pagina no sabe si vive dentro del enrutador o antes de el ("no disponible", que
// la espera del proceso dibuja sin enrutador): quien la usa le da como volver al
// inicio y como reintentar.

import { ArrowClockwiseIcon } from "@phosphor-icons/react";
import { useEffect, useRef, type ReactNode } from "react";

import type { SiteLinks } from "../../shared/api-client/site";
import { useLocale } from "../../shared/i18n/locale-provider";
import { Button } from "../../shared/ui/button";
import { statusCopy, type StatusPageKind } from "./status-kinds";

export interface StatusPageProps {
  readonly kind: StatusPageKind;
  /** "Reintentar": en "no disponible" y en "servicio no disponible". */
  readonly onRetry?: () => void;
  /** "Volver a la conversacion", en "enlace vencido". */
  readonly onBack?: () => void;
  /** Los enlaces externos configurados; los que faltan no se dibujan (BR4.4). */
  readonly links?: SiteLinks;
  /**
   * Como dibujar el enlace al inicio. Dentro del enrutador es su `Link`; antes de
   * el, un enlace comun.
   */
  readonly homeLink?: (label: string) => ReactNode;
}

function enlaceComun(label: string): ReactNode {
  return (
    <Button asChild variant="primary">
      <a href="/home">{label}</a>
    </Button>
  );
}

function volverAtras(): void {
  window.history.back();
}

function recargar(): void {
  window.location.reload();
}

export function StatusPage({
  kind,
  onRetry,
  onBack,
  links,
  homeLink = enlaceComun,
}: StatusPageProps) {
  const { t } = useLocale();
  const titulo = useRef<HTMLHeadingElement>(null);
  const pagina = statusCopy(kind);

  useEffect(() => {
    titulo.current?.focus();
  }, [kind]);

  const accion = (() => {
    switch (pagina.action) {
      case "go_home":
        return homeLink(t("action.go_home"));
      case "start_over":
        return homeLink(t("action.start_over"));
      case "back_to_conversation":
        return (
          <Button variant="primary" onClick={onBack ?? volverAtras}>
            {t("action.back_to_conversation")}
          </Button>
        );
      case "retry":
      case "external_links":
        return (
          <Button variant="primary" onClick={onRetry ?? recargar}>
            <ArrowClockwiseIcon aria-hidden="true" focusable="false" size={20} />
            {t("action.retry")}
          </Button>
        );
    }
  })();

  const externos =
    pagina.action === "external_links" && links !== undefined
      ? [
          links.readme_url ? { href: links.readme_url, label: t("site.link.readme") } : null,
          links.video_url ? { href: links.video_url, label: t("site.link.video") } : null,
        ].filter((enlace) => enlace !== null)
      : [];

  return (
    <section
      data-testid="status-page"
      data-status-kind={kind}
      aria-labelledby="status-title"
      className="mx-auto flex w-full max-w-measure flex-col gap-4 px-4 py-16 tablet:px-8 tablet:py-24"
    >
      <h1
        id="status-title"
        ref={titulo}
        tabIndex={-1}
        elementtiming="status-title"
        className="font-body text-title font-medium text-fg focus:outline-none"
      >
        {pagina.title(t)}
      </h1>
      <p className="text-lead text-fg-secondary">{pagina.body(t)}</p>

      {accion !== null || externos.length > 0 ? (
        <div className="flex flex-wrap items-center gap-3 pt-4">
          {accion}
          {externos.map((enlace) => (
            <Button key={enlace.href} asChild variant="secondary">
              <a href={enlace.href}>{enlace.label}</a>
            </Button>
          ))}
        </div>
      ) : null}
    </section>
  );
}
