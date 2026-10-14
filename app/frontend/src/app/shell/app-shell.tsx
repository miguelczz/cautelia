// El marco de las pantallas del enrutador (`AppShell`): la marca que vuelve al
// inicio, los dos selectores con la navegacion de superficies montadas, el contenido
// de la ruta y el pie.
//
// Pide el directorio del sitio para la navegacion y el pie; es la misma consulta
// del inicio, asi que viaja una sola vez. Si falla, el marco se dibuja sin
// navegacion ni enlaces: lo que no llego no se inventa (BR4.4), y el error lo
// cuenta la pantalla que necesita los datos.

import { useQuery } from "@tanstack/react-query";
import { Link, Outlet, useRouterState } from "@tanstack/react-router";

import { siteQueryOptions } from "../../shared/api-client/site";
import { useLocale } from "../../shared/i18n/locale-provider";
import { BrandMark } from "../../shared/ui/brand-mark";
import { BRAND_CLASSES, Frame } from "./frame";
import { LandingLink } from "./landing-link";
import { SiteFooter } from "./site-footer";
import { SurfaceNav } from "./surface-nav";

export function AppShell() {
  const { t } = useLocale();
  const directorio = useQuery(siteQueryOptions());
  const ruta = useRouterState({ select: (estado) => estado.location.pathname });
  // Como se asienta la pantalla en la ventana lo declara la ruta, en su
  // `staticData`; el marco solo lo lee. Con un `if` sobre la direccion aqui, la forma
  // de esas rutas quedaria escrita en dos sitios y el dia que una cambie la otra
  // seguiria igual. `fill`: llena la vista y solo se desplaza lo de dentro (el chat).
  // `onePage`: cabe en una sola vista en un computador con espacio.
  const llenaLaVista = useRouterState({
    select: (estado) =>
      estado.matches.some((coincidencia) => coincidencia.staticData.fill === true),
  });
  const enUnaPantalla = useRouterState({
    select: (estado) =>
      estado.matches.some((coincidencia) => coincidencia.staticData.onePage === true),
  });
  const superficies = directorio.data?.surfaces ?? [];
  const enlaces = directorio.data?.links ?? {};

  return (
    <Frame
      brand={
        <Link to="/home" className={BRAND_CLASSES}>
          <BrandMark />
          {t("shell.brand_name")}
        </Link>
      }
      nav={
        <SurfaceNav
          surfaces={superficies}
          links={enlaces}
          currentPath={ruta}
          pending={directorio.isPending}
        />
      }
      trailing={<LandingLink />}
      footer={<SiteFooter links={enlaces} />}
      fill={llenaLaVista}
      onePage={enUnaPantalla}
    >
      <Outlet />
    </Frame>
  );
}
