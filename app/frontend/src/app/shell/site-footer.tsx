// El pie de las pantallas: que es una demostracion de portafolio con datos
// sinteticos, quien la hizo y, solo si estan configurados, los enlaces externos
// (BR4.4). Ninguno apunta al repositorio mientras sea privado (D-017).
//
// Sin color propio: hereda el fondo de la pagina (decision de Miguel, 2026-10-06)
// y solo conserva la linea que lo separa del contenido. El credito y sus perfiles
// viven en `AuthorCredit`.

import type { SiteLinks } from "../../shared/api-client/site";
import { useLocale } from "../../shared/i18n/locale-provider";
import { AuthorCredit } from "./author-credit";

const ENLACE = "inline-flex min-h-11 items-center gap-1.5 text-link";

export function SiteFooter({ links }: { readonly links: SiteLinks }) {
  const { t } = useLocale();
  const enlaces = [
    links.readme_url ? { href: links.readme_url, label: t("site.link.readme") } : null,
    links.video_url ? { href: links.video_url, label: t("site.link.video") } : null,
  ].filter((enlace) => enlace !== null);

  return (
    <footer className="border-t border-hairline" data-testid="site-footer">
      <div className="mx-auto flex max-w-content flex-col gap-x-6 gap-y-1 px-4 py-2 text-small text-fg-secondary tablet:flex-row tablet:flex-wrap tablet:items-center tablet:justify-between tablet:px-8">
        <p>{t("shell.footer.demo")}</p>
        <div className="flex flex-wrap items-center gap-x-5">
          {enlaces.length > 0 ? (
            <ul className="flex flex-wrap gap-x-4">
              {enlaces.map((enlace) => (
                <li key={enlace.href}>
                  <a href={enlace.href} className={ENLACE}>
                    {enlace.label}
                  </a>
                </li>
              ))}
            </ul>
          ) : null}
          <AuthorCredit />
        </div>
      </div>
    </footer>
  );
}
