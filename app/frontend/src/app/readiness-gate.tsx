// La puerta de la espera (`ReadinessGate`): dibuja el enrutador solo con el proceso
// listo, y mientras tanto el marco de siempre con el esqueleto de la pantalla que la
// persona pidio (functional-spec 2.1, BR5.4, AC5.16.4).
//
// - `checking` y `waking`: el marco real --marca, navegacion en espera, selectores y
//   pie-- con el esqueleto de la ruta pedida y un hilo de progreso bajo la barra, **desde
//   el primer cuadro**. Sin texto: a quien llega no le sirve saber que el proceso
//   estaba dormido, solo que nada se quedo sin cargar (decision de Miguel,
//   2026-10-06). Antes habia un segundo en blanco y despues una pagina que lo
//   contaba con palabras.
// - `unavailable`: "no disponible", con los enlaces configurados y "Reintentar". Es
//   una falla de verdad, y ahi si hay algo que decir y algo que hacer.
// - `ready`: la ruta pedida, sin que la persona haga nada.

import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, type ReactNode } from "react";

import { useReadiness, type ReadinessDeps } from "../shared/api-client/readiness";
import { siteQueryOptions } from "../shared/api-client/site";
import { useLocale } from "../shared/i18n/locale-provider";
import { BrandMark } from "../shared/ui/brand-mark";
import { PageSkeleton, type SkeletonKind } from "../shared/ui/page-skeletons";
import { StatusPage } from "../pages/status/status-page";
import { BRAND_CLASSES, Frame } from "./shell/frame";
import { LandingLink } from "./shell/landing-link";
import { SiteFooter } from "./shell/site-footer";
import { SurfaceNav } from "./shell/surface-nav";
import { frameModeForKind, skeletonKindForPath } from "./skeleton-kinds";

const cargarEnrutador = () => import("./routed-app");
const RoutedApp = lazy(cargarEnrutador);

/**
 * El marco antes del enrutador: el mismo que dibuja el enrutador --marca, selectores y
 * pie--, con el lugar de la navegacion reservado, para que al llegar la pantalla solo
 * cambie lo de dentro.
 */
function GateFrame({
  kind,
  busy = false,
  children,
}: {
  readonly kind: SkeletonKind;
  readonly busy?: boolean;
  readonly children: ReactNode;
}) {
  const { t } = useLocale();
  return (
    <Frame
      brand={
        <a href="/home" className={BRAND_CLASSES}>
          <BrandMark />
          {t("shell.brand_name")}
        </a>
      }
      nav={<SurfaceNav surfaces={[]} links={{}} currentPath="" pending />}
      trailing={<LandingLink />}
      footer={<SiteFooter links={{}} />}
      busy={busy}
      {...frameModeForKind(kind)}
    >
      {children}
    </Frame>
  );
}

function Waiting({ kind }: { readonly kind: SkeletonKind }) {
  // Con el esqueleto ya pintado, el resto de la aplicacion se trae en segundo plano
  // para que, al estar lista la demo, la pantalla se dibuje sin esperar.
  useEffect(() => {
    const reloj = setTimeout(() => {
      cargarEnrutador().catch((error: unknown) => {
        console.info("untangle: the app could not be prefetched while waiting", error);
      });
    }, 0);
    return () => {
      clearTimeout(reloj);
    };
  }, []);
  return (
    <GateFrame kind={kind} busy>
      <PageSkeleton kind={kind} />
    </GateFrame>
  );
}

function Unavailable({ onRetry }: { readonly onRetry: () => void }) {
  // Los enlaces externos, si el directorio responde y estan configurados. Si no
  // responde, la pagina va sin ellos (BR4.4).
  const directorio = useQuery(siteQueryOptions());
  return (
    <GateFrame kind="generic">
      <StatusPage kind="unavailable" onRetry={onRetry} links={directorio.data?.links ?? {}} />
    </GateFrame>
  );
}

export function ReadinessGate({ deps }: { readonly deps?: ReadinessDeps }) {
  const { watch, retry } = useReadiness(deps);
  const kind = skeletonKindForPath(watch.requestedRoute);

  switch (watch.state) {
    case "checking":
    case "waking":
      return <Waiting kind={kind} />;
    case "unavailable":
      return <Unavailable onRetry={retry} />;
    case "ready":
      return (
        <Suspense
          fallback={
            <GateFrame kind={kind} busy>
              <PageSkeleton kind={kind} />
            </GateFrame>
          }
        >
          <RoutedApp />
        </Suspense>
      );
  }
}
