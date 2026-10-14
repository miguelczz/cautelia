// La navegacion de la barra: botones a la derecha, junto a los selectores (decision de
// Miguel, 2026-10-06): los paneles que el servidor declara montados y el enlace "Como
// esta hecho" si esta configurado (BR4.1, BR4.4). Sin nada que enlazar, no hay
// navegacion. El icono que vuelve a la landing no es de esta lista: va al final de la
// barra (`LandingLink`).
//
// Son texto en la fuente de titulos, en negrita y sin caja, con una linea de cobre que
// crece bajo la palabra al pasar el puntero (`NavLink`, decision de Miguel, 2026-10-09).
// En telefono viven en el panel del menu (`phone-menu.tsx`, decision de Miguel,
// 2026-10-08): ahi son una lista de filas a todo el ancho con el texto a la izquierda. El
// de la pagina actual se marca con `aria-current` y con la linea entera, no solo con
// color (BR7.6).
//
// **Sin esqueleto de carga** (Miguel, 2026-10-11): mientras el directorio del sitio no
// llega --`pending`-- los paneles se suponen montados y se pintan ya, que es lo normal;
// si el servidor dice despues que alguno no lo esta, ese enlace se retira. Asi la barra
// no muestra una caja de espera ni se mueve al cargar.

import type { SiteLinks, SurfaceId } from "../../shared/api-client/site";
import { useLocale } from "../../shared/i18n/locale-provider";
import { NavLink } from "../../shared/ui/nav-link";
import { CASES_LINK, INSURERS_LINK, NAV_LINKS } from "../surfaces";

interface SurfaceNavProps {
  readonly surfaces: readonly SurfaceId[];
  readonly links: SiteLinks;
  /** La ruta actual, para marcar el boton activo. */
  readonly currentPath: string;
  /** El directorio del sitio todavia no llego. */
  readonly pending?: boolean;
}

// En el panel del menu: la fila ocupa todo el ancho y el texto arranca a la izquierda.
const FILA_EN_TELEFONO = "max-tablet:flex max-tablet:justify-start";

/** El enlace de la pagina actual o de una pagina que cuelga de ella (un caso, bajo "Casos"). */
function esLaActual(href: string, ruta: string): boolean {
  return ruta === href || ruta.startsWith(`${href}/`);
}

export function SurfaceNav({ surfaces, links, currentPath, pending = false }: SurfaceNavProps) {
  const { t } = useLocale();

  const enlaces = [
    { href: INSURERS_LINK.href, label: INSURERS_LINK.label(t) },
    { href: CASES_LINK.href, label: CASES_LINK.label(t) },
    ...NAV_LINKS.filter((enlace) => pending || surfaces.includes(enlace.surface)).map((enlace) => ({
      href: enlace.href,
      label: enlace.label(t),
    })),
    ...(links.readme_url ? [{ href: links.readme_url, label: t("site.link.readme") }] : []),
  ];

  if (enlaces.length === 0) {
    return null;
  }

  return (
    <nav aria-label={t("shell.nav_label")} data-testid="surface-nav">
      <ul className="flex flex-wrap items-center justify-end gap-2 max-tablet:flex-col max-tablet:items-stretch max-tablet:gap-1">
        {enlaces.map((enlace) => (
          <li key={enlace.href}>
            <NavLink
              href={enlace.href}
              current={esLaActual(enlace.href, currentPath)}
              className={FILA_EN_TELEFONO}
            >
              {enlace.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
